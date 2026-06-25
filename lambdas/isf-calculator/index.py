"""
ISF Calculator Lambda - Índice de Salud Financiera
Calcula el ISF del cliente basado en 4 componentes ponderados (score 0-100).

Componentes:
- Ratio ingresos/gastos (30%): min(100, (ingresos / gastos) * 50)
- Nivel de ahorro (25%): min(100, (ahorro_mensual / ingresos) * 100)
- Carga de deuda (25%): max(0, 100 - (deuda_total / ingresos_anuales) * 100)
- Estabilidad de ingresos (20%): max(0, min(100, 100 - (std_dev / mean) * 100))

Interpretación:
- 80-100: Excelente
- 60-79: Bueno
- 40-59: Regular
- 0-39: Crítico

Requirements: 1.1, 1.2, 1.3
"""

import json
import logging
import os
import statistics
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


def log_structured(level: str, message: str, **kwargs):
    """Emit structured JSON log entry."""
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "level": level,
        "message": message,
        "service": "isf-calculator",
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


def calculate_income_expense_ratio(total_income: float, total_expenses: float) -> float:
    """
    Calculate income/expense ratio component (weight: 30%).
    Formula: min(100, (income / expenses) * 50)
    """
    if total_expenses <= 0:
        return 100.0
    ratio = (total_income / total_expenses) * 50
    return min(100.0, ratio)


def calculate_savings_level(savings_monthly: float, monthly_income: float) -> float:
    """
    Calculate savings level component (weight: 25%).
    Formula: min(100, (savings_monthly / income) * 100)
    """
    if monthly_income <= 0:
        return 0.0
    level = (savings_monthly / monthly_income) * 100
    return min(100.0, level)


def calculate_debt_load(total_debt: float, annual_income: float) -> float:
    """
    Calculate debt load component (weight: 25%).
    Formula: max(0, 100 - (debt / annual_income) * 100)
    """
    if annual_income <= 0:
        return 0.0
    load = 100 - (total_debt / annual_income) * 100
    return max(0.0, load)


def calculate_income_stability(income_values: list[float]) -> float:
    """
    Calculate income stability component (weight: 20%).
    Formula: max(0, min(100, 100 - (std_dev / mean) * 100))
    Uses coefficient of variation (CV) to measure stability.
    """
    if len(income_values) < 2:
        # With insufficient data, assume moderate stability
        return 70.0

    mean_income = statistics.mean(income_values)
    if mean_income <= 0:
        return 0.0

    std_dev = statistics.stdev(income_values)
    stability = 100 - (std_dev / mean_income) * 100
    return max(0.0, min(100.0, stability))


def get_interpretation(score: float) -> str:
    """Map ISF score to textual interpretation."""
    if score >= 80:
        return "Excelente"
    elif score >= 60:
        return "Bueno"
    elif score >= 40:
        return "Regular"
    else:
        return "Crítico"


def compute_isf(client_profile: dict, transactions: list, period_days: int) -> dict:
    """
    Compute the ISF score from client profile and transaction data.

    Returns dict with isf_score, interpretation, and component breakdown.
    """
    monthly_income = float(client_profile.get("monthly_income", 0))
    monthly_fixed_expenses = float(client_profile.get("monthly_fixed_expenses", 0))
    savings_balance = float(client_profile.get("savings_balance", 0))
    debt_balance = float(client_profile.get("debt_balance", 0))

    # Calculate totals from transactions
    total_income_from_tx = 0.0
    total_expenses_from_tx = 0.0
    monthly_incomes = []

    for tx in transactions:
        amount = float(tx.get("amount", 0))
        tx_type = tx.get("type", "expense")
        if tx_type == "income":
            total_income_from_tx += amount
        else:
            total_expenses_from_tx += amount

    # Use transaction data if available, otherwise fall back to profile data
    if total_income_from_tx > 0:
        effective_income = total_income_from_tx
    else:
        effective_income = monthly_income * (period_days / 30)

    if total_expenses_from_tx > 0:
        effective_expenses = total_expenses_from_tx
    else:
        effective_expenses = monthly_fixed_expenses * (period_days / 30)

    # Normalize to monthly values for savings/debt calculations
    months_in_period = max(period_days / 30, 1)
    monthly_income_effective = effective_income / months_in_period

    # Calculate monthly savings estimate from savings_balance
    # Use savings_balance as proxy for monthly savings capacity
    savings_monthly = savings_balance / 12 if savings_balance > 0 else 0

    # Annual income for debt load calculation
    annual_income = monthly_income_effective * 12

    # Gather income values for stability calculation (group by month from transactions)
    income_by_month: dict[str, float] = {}
    for tx in transactions:
        if tx.get("type") == "income":
            tx_date = tx.get("date", "")
            month_key = tx_date[:7]  # YYYY-MM
            income_by_month[month_key] = income_by_month.get(month_key, 0) + float(tx.get("amount", 0))

    income_values = list(income_by_month.values()) if income_by_month else [monthly_income]

    # Calculate 4 components
    income_expense_ratio = calculate_income_expense_ratio(effective_income, effective_expenses)
    savings_level = calculate_savings_level(savings_monthly, monthly_income_effective)
    debt_load = calculate_debt_load(debt_balance, annual_income)
    income_stability = calculate_income_stability(income_values)

    # Weighted final score
    isf_score = (
        income_expense_ratio * 0.30
        + savings_level * 0.25
        + debt_load * 0.25
        + income_stability * 0.20
    )

    # Round to 2 decimal places
    isf_score = round(isf_score, 2)
    income_expense_ratio = round(income_expense_ratio, 2)
    savings_level = round(savings_level, 2)
    debt_load = round(debt_load, 2)
    income_stability = round(income_stability, 2)

    interpretation = get_interpretation(isf_score)

    return {
        "isf_score": isf_score,
        "interpretation": interpretation,
        "components": {
            "income_expense_ratio": income_expense_ratio,
            "savings_level": savings_level,
            "debt_load": debt_load,
            "income_stability": income_stability,
        },
        "period_days": period_days,
        "client_id": client_profile.get("client_id", "unknown"),
    }


def build_response(event: dict, status_code: int, body: dict) -> dict:
    """Build Bedrock Agent response format."""
    return {
        "messageVersion": "1.0",
        "response": {
            "actionGroup": event.get("actionGroup", "calculate-isf"),
            "apiPath": event.get("apiPath", "/calculate-isf"),
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
    body = {"error": error_message, "isf_score": None, "interpretation": None}
    return build_response(event, status_code, body)


def handler(event, context):
    """Bedrock Agent Action Group handler for ISF calculation."""
    start_time = datetime.now(timezone.utc)

    log_structured("INFO", "ISF calculation request received", event=event)

    # Extract parameters from Bedrock Agent event
    parameters = {p["name"]: p["value"] for p in event.get("parameters", [])}
    client_id = parameters.get("client_id", "").strip()
    period_days = int(parameters.get("calculation_period_days", "30"))

    log_structured("INFO", "Processing ISF calculation", client_id=client_id, period_days=period_days)

    # Validate input
    if not client_id:
        log_structured("WARNING", "Missing client_id parameter")
        return build_error_response(event, 400, "El parámetro client_id es requerido.")

    # Get client profile
    client_profile = get_client_profile(client_id)
    if not client_profile:
        log_structured("WARNING", "Client not found", client_id=client_id)
        return build_error_response(
            event, 404, f"Cliente '{client_id}' no encontrado en el sistema."
        )

    # Get transactions for the period
    transactions = get_transactions(client_id, period_days)
    log_structured(
        "INFO",
        "Transactions retrieved",
        client_id=client_id,
        transaction_count=len(transactions),
    )

    # Handle edge case: no transactions
    if not transactions:
        log_structured(
            "WARNING",
            "No transactions found, using profile data only",
            client_id=client_id,
        )

    # Compute ISF
    try:
        result = compute_isf(client_profile, transactions, period_days)
    except Exception as e:
        log_structured("ERROR", "ISF calculation failed", client_id=client_id, error=str(e))
        return build_error_response(event, 500, "Error interno al calcular el ISF.")

    # Log latency
    elapsed_ms = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
    log_structured(
        "INFO",
        "ISF calculation completed",
        client_id=client_id,
        isf_score=result["isf_score"],
        interpretation=result["interpretation"],
        latency_ms=round(elapsed_ms, 2),
    )

    return build_response(event, 200, result)
