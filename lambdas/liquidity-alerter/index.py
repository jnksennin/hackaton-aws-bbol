"""
Liquidity Alerter Lambda - Proyección de Liquidez y Evaluación de Compras
Proyecta saldo futuro, genera alertas de liquidez y evalúa compras.

Endpoints:
- /project-liquidity: Proyecta saldo a N días, determina alert_level, calcula deficit_date
- /evaluate-purchase: Evalúa si una compra compromete la liquidez del cliente

Requirements: 4.1, 4.2, 4.3, 4.6
"""

import json
import logging
import os
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import boto3
from boto3.dynamodb.conditions import Key

# Structured JSON logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Environment variables
TRANSACTIONS_TABLE = os.environ.get("TRANSACTIONS_TABLE", "financial-assistant-transactions")
CLIENTS_TABLE = os.environ.get("CLIENTS_TABLE", "financial-assistant-clients")

# DynamoDB resource
dynamodb = boto3.resource("dynamodb")
transactions_table = dynamodb.Table(TRANSACTIONS_TABLE)
clients_table = dynamodb.Table(CLIENTS_TABLE)

# Constants
DEFAULT_PROJECTION_DAYS = 7
ALERT_WARNING_MULTIPLIER = 1.2  # warning if balance < 1.2 * monthly_fixed_expenses
ALERT_NONE_MULTIPLIER = 1.5    # none if balance >= 1.5 * monthly_fixed_expenses


def log_structured(level: str, message: str, **kwargs):
    """Emit structured JSON log entry."""
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "level": level,
        "message": message,
        "service": "liquidity-alerter",
        **kwargs,
    }
    if level == "ERROR":
        logger.error(json.dumps(entry, default=str))
    elif level == "WARNING":
        logger.warning(json.dumps(entry, default=str))
    else:
        logger.info(json.dumps(entry, default=str))


class DecimalEncoder(json.JSONEncoder):
    """Handle Decimal types from DynamoDB."""

    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)
        return super().default(obj)


def get_client_profile(client_id: str) -> dict | None:
    """Retrieve client profile from DynamoDB clients table."""
    try:
        response = clients_table.get_item(Key={"client_id": client_id})
        return response.get("Item")
    except Exception as e:
        log_structured("ERROR", "Failed to get client profile", client_id=client_id, error=str(e))
        return None


def get_transactions(client_id: str, period_days: int) -> list:
    """Query transactions for a client within the specified period using date-index GSI."""
    try:
        end_date = datetime.now(timezone.utc)
        start_date = end_date - timedelta(days=period_days)

        start_date_str = start_date.strftime("%Y-%m-%d")
        end_date_str = end_date.strftime("%Y-%m-%d")

        response = transactions_table.query(
            IndexName="date-index",
            KeyConditionExpression=Key("client_id").eq(client_id)
            & Key("date").between(start_date_str, end_date_str),
        )

        items = response.get("Items", [])

        # Handle pagination
        while "LastEvaluatedKey" in response:
            response = transactions_table.query(
                IndexName="date-index",
                KeyConditionExpression=Key("client_id").eq(client_id)
                & Key("date").between(start_date_str, end_date_str),
                ExclusiveStartKey=response["LastEvaluatedKey"],
            )
            items.extend(response.get("Items", []))

        return items
    except Exception as e:
        log_structured("ERROR", "Failed to query transactions", client_id=client_id, error=str(e))
        return []


def get_current_month_transactions(client_id: str) -> list:
    """Get transactions for the current month."""
    now = datetime.now(timezone.utc)
    first_of_month = now.replace(day=1).strftime("%Y-%m-%d")
    today = now.strftime("%Y-%m-%d")

    try:
        response = transactions_table.query(
            IndexName="date-index",
            KeyConditionExpression=Key("client_id").eq(client_id)
            & Key("date").between(first_of_month, today),
        )

        items = response.get("Items", [])

        while "LastEvaluatedKey" in response:
            response = transactions_table.query(
                IndexName="date-index",
                KeyConditionExpression=Key("client_id").eq(client_id)
                & Key("date").between(first_of_month, today),
                ExclusiveStartKey=response["LastEvaluatedKey"],
            )
            items.extend(response.get("Items", []))

        return items
    except Exception as e:
        log_structured("ERROR", "Failed to query current month transactions", client_id=client_id, error=str(e))
        return []


# ─────────────────────────────────────────────────────────────────────────────
# Task 9.1: Proyección de Liquidez
# Requirements: 4.1, 4.2
# ─────────────────────────────────────────────────────────────────────────────


def calculate_current_balance(client_profile: dict, current_month_transactions: list) -> float:
    """
    Calculate current available balance for the client.

    Formula: savings_balance + (monthly_income - total_expenses_current_month)
    """
    savings_balance = float(client_profile.get("savings_balance", 0))
    monthly_income = float(client_profile.get("monthly_income", 0))

    # Sum expenses this month
    total_expenses_this_month = sum(
        float(tx.get("amount", 0))
        for tx in current_month_transactions
        if tx.get("type", "expense") == "expense"
    )

    current_balance = savings_balance + (monthly_income - total_expenses_this_month)
    return round(current_balance, 2)


def calculate_avg_daily_spend(transactions_30d: list) -> float:
    """Calculate average daily expenses from the last 30 days of transactions."""
    expenses = [
        float(tx.get("amount", 0))
        for tx in transactions_30d
        if tx.get("type", "expense") == "expense"
    ]

    total_expenses = sum(expenses)
    # Use 30 as the divisor (standard month period)
    avg_daily = total_expenses / 30.0 if total_expenses > 0 else 0.0
    return round(avg_daily, 2)


def determine_alert_level(current_balance: float, projected_balance: float, monthly_fixed_expenses: float) -> str:
    """
    Determine alert level based on balance and fixed expenses.

    - critical: projected_balance < 0 (deficit within projection period)
    - warning: current_balance < 1.2 * monthly_fixed_expenses
    - none: current_balance >= 1.5 * monthly_fixed_expenses
    """
    # Critical takes highest priority: deficit projected
    if projected_balance < 0:
        return "critical"

    # Warning: balance is tight relative to fixed expenses
    if current_balance < ALERT_WARNING_MULTIPLIER * monthly_fixed_expenses:
        return "warning"

    # None: balance is comfortable
    if current_balance >= ALERT_NONE_MULTIPLIER * monthly_fixed_expenses:
        return "none"

    # Between 1.2x and 1.5x - still warning territory
    return "warning"


def calculate_deficit_date(current_balance: float, avg_daily_spend: float) -> str | None:
    """
    Calculate the date when balance reaches 0 based on average daily spend.

    Returns ISO date string or None if no deficit projected.
    """
    if avg_daily_spend <= 0 or current_balance <= 0:
        # If no spending or already in deficit, return today or None
        if current_balance <= 0:
            return datetime.now(timezone.utc).strftime("%Y-%m-%d")
        return None

    days_until_deficit = current_balance / avg_daily_spend
    deficit_date = datetime.now(timezone.utc) + timedelta(days=days_until_deficit)
    return deficit_date.strftime("%Y-%m-%d")


def generate_liquidity_recommendations(
    alert_level: str, current_balance: float, projected_balance: float,
    monthly_fixed_expenses: float, avg_daily_spend: float
) -> list[str]:
    """Generate specific recommendations based on alert level and financial situation."""
    recommendations = []

    if alert_level == "critical":
        recommendations.append(
            "⚠️ Tu saldo proyectado es negativo. Reduce gastos variables esta semana en un 30%."
        )
        recommendations.append(
            "Difiere compras no esenciales hasta que tus ingresos se estabilicen."
        )
        savings_needed = abs(projected_balance) + (monthly_fixed_expenses * 0.1)
        recommendations.append(
            f"Considera transferir ${savings_needed:.2f} desde tu cuenta de ahorros para cubrir el déficit."
        )
    elif alert_level == "warning":
        recommendations.append(
            "Tu saldo está por debajo del margen de seguridad recomendado (1.2x gastos fijos)."
        )
        recommendations.append(
            "Reduce gastos variables esta semana en un 20%."
        )
        recommendations.append(
            "Diferir compras no esenciales por 5 días mejorará tu posición de liquidez."
        )
    else:
        recommendations.append(
            "Tu liquidez se encuentra en un nivel saludable. Mantén el ritmo de ahorro actual."
        )

    return recommendations


def project_liquidity(client_id: str, projection_days: int = DEFAULT_PROJECTION_DAYS) -> dict:
    """
    Project liquidity for a client over N days.

    Steps:
    1. Get client profile (monthly_income, monthly_fixed_expenses, savings_balance)
    2. Calculate current balance from this month's transactions
    3. Calculate avg daily spend from last 30 days
    4. Project balance at N days: current_balance - (avg_daily_spend * N)
    5. Determine alert_level: none, warning, critical
    6. Calculate deficit_date if applicable
    7. Generate recommendations
    """
    # Get client profile
    client_profile = get_client_profile(client_id)
    if not client_profile:
        log_structured("WARNING", "Client not found", client_id=client_id)
        return {"error": f"Cliente '{client_id}' no encontrado en el sistema."}

    monthly_fixed_expenses = float(client_profile.get("monthly_fixed_expenses", 0))

    # Get current month transactions for balance calculation
    current_month_txs = get_current_month_transactions(client_id)

    # Calculate current balance
    current_balance = calculate_current_balance(client_profile, current_month_txs)

    # Get last 30 days transactions for avg daily spend
    transactions_30d = get_transactions(client_id, 30)
    avg_daily_spend = calculate_avg_daily_spend(transactions_30d)

    # Project balance
    projected_balance = round(current_balance - (avg_daily_spend * projection_days), 2)

    # Determine alert level
    alert_level = determine_alert_level(current_balance, projected_balance, monthly_fixed_expenses)

    # Calculate deficit date
    deficit_date = calculate_deficit_date(current_balance, avg_daily_spend)

    # Generate recommendations
    recommendations = generate_liquidity_recommendations(
        alert_level, current_balance, projected_balance,
        monthly_fixed_expenses, avg_daily_spend,
    )

    log_structured(
        "INFO", "Liquidity projection completed",
        client_id=client_id, current_balance=current_balance,
        projected_balance=projected_balance, alert_level=alert_level,
        projection_days=projection_days,
    )

    return {
        "current_balance": current_balance,
        "projected_balance": projected_balance,
        "alert_level": alert_level,
        "deficit_date": deficit_date,
        "recommendations": recommendations,
        "avg_daily_spend": avg_daily_spend,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Task 9.2: Evaluación de Compras
# Requirements: 4.3, 4.6
# ─────────────────────────────────────────────────────────────────────────────


def evaluate_purchase(client_id: str, purchase_amount: float) -> dict:
    """
    Evaluate if a purchase compromises the client's liquidity.

    Steps:
    1. Get client profile and current balance
    2. Calculate remaining balance after purchase
    3. Determine if client can afford it (remaining > monthly_fixed_expenses)
    4. Assess impact on liquidity
    5. Generate specific recommendation
    """
    # Get client profile
    client_profile = get_client_profile(client_id)
    if not client_profile:
        log_structured("WARNING", "Client not found for purchase eval", client_id=client_id)
        return {"error": f"Cliente '{client_id}' no encontrado en el sistema."}

    monthly_fixed_expenses = float(client_profile.get("monthly_fixed_expenses", 0))
    savings_balance = float(client_profile.get("savings_balance", 0))

    # Get current month transactions for balance calculation
    current_month_txs = get_current_month_transactions(client_id)
    current_balance = calculate_current_balance(client_profile, current_month_txs)

    # Calculate remaining balance after purchase
    remaining_balance_after = round(current_balance - purchase_amount, 2)

    # Determine if the client can afford the purchase
    # Can afford if remaining balance still covers fixed expenses
    can_afford = remaining_balance_after >= monthly_fixed_expenses

    # Assess impact on liquidity
    if remaining_balance_after < 0:
        impact = "crítico"
    elif remaining_balance_after < monthly_fixed_expenses:
        impact = "alto"
    elif remaining_balance_after < ALERT_WARNING_MULTIPLIER * monthly_fixed_expenses:
        impact = "moderado"
    else:
        impact = "bajo"

    # Generate recommendation based on impact
    recommendation = _generate_purchase_recommendation(
        can_afford, impact, purchase_amount, remaining_balance_after,
        monthly_fixed_expenses, savings_balance,
    )

    log_structured(
        "INFO", "Purchase evaluation completed",
        client_id=client_id, purchase_amount=purchase_amount,
        can_afford=can_afford, impact=impact,
    )

    return {
        "can_afford": can_afford,
        "impact_on_liquidity": impact,
        "remaining_balance_after": remaining_balance_after,
        "recommendation": recommendation,
    }


def _generate_purchase_recommendation(
    can_afford: bool, impact: str, purchase_amount: float,
    remaining_balance: float, monthly_fixed_expenses: float,
    savings_balance: float,
) -> str:
    """Generate specific recommendation for a purchase evaluation."""
    if can_afford and impact == "bajo":
        return (
            f"Puedes realizar esta compra de ${purchase_amount:.2f} sin comprometer tu liquidez. "
            f"Tu saldo restante (${remaining_balance:.2f}) cubre holgadamente tus gastos fijos."
        )

    if can_afford and impact == "moderado":
        return (
            f"Puedes realizar esta compra, pero tu margen de seguridad se reduce. "
            f"Saldo restante: ${remaining_balance:.2f}. "
            f"Considera reducir gastos variables esta semana para compensar."
        )

    # Can't afford or high/critical impact
    if impact == "crítico":
        if savings_balance >= purchase_amount:
            return (
                f"Esta compra de ${purchase_amount:.2f} excede tu saldo disponible. "
                f"Opción: transferir desde tu cuenta de ahorros (saldo: ${savings_balance:.2f}). "
                f"Te recomiendo diferir esta compra si no es urgente."
            )
        return (
            f"Esta compra de ${purchase_amount:.2f} comprometería gravemente tu liquidez. "
            f"No cuentas con fondos suficientes ni en ahorros. "
            f"Te recomiendo diferir esta compra y reducir gastos variables."
        )

    # High impact - can't cover fixed expenses
    if savings_balance >= (monthly_fixed_expenses - remaining_balance):
        return (
            f"Esta compra de ${purchase_amount:.2f} dejaría tu saldo (${remaining_balance:.2f}) "
            f"por debajo de tus gastos fijos mensuales (${monthly_fixed_expenses:.2f}). "
            f"Podrías transferir desde ahorros, pero te recomiendo diferir compras no esenciales."
        )

    return (
        f"Esta compra de ${purchase_amount:.2f} comprometería tu capacidad de cubrir gastos fijos. "
        f"Te recomiendo: reducir gastos variables, diferir esta compra, "
        f"o considerar solo una porción del monto."
    )


# ─────────────────────────────────────────────────────────────────────────────
# Bedrock Agent Response Helpers
# ─────────────────────────────────────────────────────────────────────────────


def build_response(event: dict, status_code: int, body: dict) -> dict:
    """Build Bedrock Agent response format."""
    return {
        "messageVersion": "1.0",
        "response": {
            "actionGroup": event.get("actionGroup", "check-liquidity"),
            "apiPath": event.get("apiPath", ""),
            "httpMethod": event.get("httpMethod", "POST"),
            "httpStatusCode": status_code,
            "responseBody": {
                "application/json": {
                    "body": json.dumps(body, cls=DecimalEncoder)
                }
            },
        },
    }


def build_error_response(event: dict, status_code: int, error_message: str) -> dict:
    """Build error response in Bedrock Agent format."""
    return build_response(event, status_code, {"error": error_message})


# ─────────────────────────────────────────────────────────────────────────────
# Lambda Handler
# ─────────────────────────────────────────────────────────────────────────────


def handler(event, context):
    """Bedrock Agent Action Group handler for liquidity alerting."""
    start_time = datetime.now(timezone.utc)

    log_structured("INFO", "Liquidity alerter request received", event=event)

    # Extract parameters from Bedrock Agent event
    api_path = event.get("apiPath", "")
    parameters = {p["name"]: p["value"] for p in event.get("parameters", [])}
    client_id = parameters.get("client_id", "").strip()

    log_structured("INFO", "Processing request", api_path=api_path, client_id=client_id)

    # Validate client_id
    if not client_id:
        log_structured("WARNING", "Missing client_id parameter")
        return build_error_response(event, 400, "El parámetro client_id es requerido.")

    # Route to the appropriate function
    if api_path == "/project-liquidity":
        projection_days = int(parameters.get("projection_days", str(DEFAULT_PROJECTION_DAYS)))
        result = project_liquidity(client_id, projection_days)
    elif api_path == "/evaluate-purchase":
        purchase_amount_str = parameters.get("purchase_amount", "0")
        try:
            purchase_amount = float(purchase_amount_str)
        except (ValueError, TypeError):
            return build_error_response(event, 400, "El parámetro purchase_amount debe ser un número válido.")

        if purchase_amount <= 0:
            return build_error_response(event, 400, "El monto de compra debe ser mayor a cero.")

        result = evaluate_purchase(client_id, purchase_amount)
    else:
        log_structured("WARNING", "Unknown api_path", api_path=api_path)
        return build_error_response(event, 400, f"Ruta no reconocida: {api_path}")

    # Check if the result contains an error (e.g., client not found)
    if "error" in result:
        return build_error_response(event, 404, result["error"])

    # Log latency
    elapsed_ms = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
    log_structured(
        "INFO", "Liquidity alerter completed",
        api_path=api_path, client_id=client_id, latency_ms=round(elapsed_ms, 2),
    )

    return build_response(event, 200, result)
