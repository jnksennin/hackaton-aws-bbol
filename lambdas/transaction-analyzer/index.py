"""
Transaction Analyzer Lambda - Gastos Hormiga & Suscripciones Recurrentes
Analiza transacciones para identificar patrones de gasto y suscripciones.

Endpoints:
- /analyze-gastos-hormiga: Filtra transacciones <$10, agrupa por categoría, top 3, alerta si >=15% del ingreso
- /detect-subscriptions: Detecta patrones recurrentes (mismo merchant, monto ±$2, frecuencia mensual en 3 meses)

Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 3.1, 3.2, 3.3, 3.4, 3.5
"""

import json
import logging
import os
from collections import defaultdict
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
GASTOS_HORMIGA_THRESHOLD = 10.0  # USD - transactions below this are "gastos hormiga"
GASTOS_HORMIGA_ALERT_PERCENTAGE = 15.0  # alert if >= 15% of income
SUBSCRIPTION_AMOUNT_TOLERANCE = 2.0  # USD ±$2
SUBSCRIPTION_MIN_MONTHS = 2  # at least 2 of 3 months required

# Merchant -> subscription category mapping
SUBSCRIPTION_CATEGORIES = {
    "Netflix": "streaming",
    "Spotify": "streaming",
    "Disney+": "streaming",
    "HBO Max": "streaming",
    "Amazon Prime": "streaming",
    "Apple TV+": "streaming",
    "YouTube Premium": "streaming",
    "SmartFit Gym": "gimnasio",
    "SmartFit": "gimnasio",
    "FitLife": "gimnasio",
    "iCloud": "software",
    "Google One": "software",
    "Microsoft 365": "software",
    "Adobe": "software",
    "Dropbox": "software",
    "Uber Pass": "servicios_digitales",
    "Rappi Prime": "servicios_digitales",
}

# Friendly category names for gastos hormiga output
CATEGORY_DISPLAY_NAMES = {
    "coffee_snacks": "Cafeterías y snacks",
    "transport": "Transporte apps",
    "entertainment": "Entretenimiento",
    "groceries": "Compras pequeñas",
    "restaurants": "Restaurantes",
    "health": "Salud",
    "shopping": "Compras varias",
    "education": "Educación",
    "utilities": "Servicios",
    "other": "Otros",
    "otros": "Otros",
}


def log_structured(level: str, message: str, **kwargs):
    """Emit structured JSON log entry."""
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "level": level,
        "message": message,
        "service": "transaction-analyzer",
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


# ─────────────────────────────────────────────────────────────────────────────
# Task 8.1: Análisis de Gastos Hormiga
# Requirements: 2.1, 2.2, 2.3, 2.4, 2.5
# ─────────────────────────────────────────────────────────────────────────────


def analyze_gastos_hormiga(client_id: str, period_months: int = 1) -> dict:
    """
    Analyze small frequent expenses (gastos hormiga) for a client.

    Steps:
    1. Filter transactions < $10 from the last month (Req 2.1, 2.2)
    2. Group by category and calculate total per category (Req 2.2)
    3. Sort by total amount desc, return top 3 with frequency (Req 2.4)
    4. Calculate percentage relative to monthly income (Req 2.3)
    5. Trigger alert if percentage >= 15% of income (Req 2.5)
    """
    period_days = period_months * 30

    # Get client profile for monthly_income
    client_profile = get_client_profile(client_id)
    if not client_profile:
        log_structured("WARNING", "Client not found", client_id=client_id)
        return {"error": f"Cliente '{client_id}' no encontrado en el sistema."}

    monthly_income = float(client_profile.get("monthly_income", 0))

    # Get transactions for the period
    transactions = get_transactions(client_id, period_days)
    log_structured(
        "INFO", "Transactions retrieved for gastos hormiga",
        client_id=client_id, count=len(transactions), period_days=period_days,
    )

    # Filter: expenses < $10
    gastos_hormiga = [
        tx for tx in transactions
        if tx.get("type", "expense") == "expense"
        and float(tx.get("amount", 0)) < GASTOS_HORMIGA_THRESHOLD
    ]

    # Group by category
    category_data: dict[str, dict] = defaultdict(lambda: {"total": 0.0, "frequency": 0})
    for tx in gastos_hormiga:
        category = tx.get("category", "otros")
        amount = float(tx.get("amount", 0))
        category_data[category]["total"] += amount
        category_data[category]["frequency"] += 1

    # Sort by total descending, take top 3
    sorted_categories = sorted(
        category_data.items(), key=lambda x: x[1]["total"], reverse=True
    )
    top_3 = sorted_categories[:3]

    # Build result categories with friendly names
    categories_result = [
        {
            "name": CATEGORY_DISPLAY_NAMES.get(key, key.replace("_", " ").title()),
            "total": round(data["total"], 2),
            "frequency": data["frequency"],
        }
        for key, data in top_3
    ]

    # Total amount across all gastos hormiga
    total_amount = round(sum(d["total"] for _, d in sorted_categories), 2)

    # Percentage of monthly income
    percentage_of_income = round((total_amount / monthly_income) * 100, 2) if monthly_income > 0 else 0.0

    # Alert if >= 15% of income (Req 2.5)
    alert_triggered = percentage_of_income >= GASTOS_HORMIGA_ALERT_PERCENTAGE

    log_structured(
        "INFO", "Gastos hormiga analysis completed",
        client_id=client_id, total=total_amount,
        pct=percentage_of_income, alert=alert_triggered,
    )

    return {
        "categories": categories_result,
        "total_amount": total_amount,
        "percentage_of_income": percentage_of_income,
        "alert_triggered": alert_triggered,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Task 8.2: Detección de Suscripciones Recurrentes
# Requirements: 3.1, 3.2, 3.3, 3.4, 3.5
# ─────────────────────────────────────────────────────────────────────────────


def classify_subscription_category(merchant: str) -> str:
    """Classify merchant into subscription category using mapping + partial match."""
    # Exact match
    if merchant in SUBSCRIPTION_CATEGORIES:
        return SUBSCRIPTION_CATEGORIES[merchant]

    # Partial match (case-insensitive)
    merchant_lower = merchant.lower()
    for known_merchant, category in SUBSCRIPTION_CATEGORIES.items():
        if known_merchant.lower() in merchant_lower or merchant_lower in known_merchant.lower():
            return category

    return "servicios_digitales"


def detect_subscriptions(client_id: str) -> dict:
    """
    Detect recurring subscriptions over last 3 months.

    Algorithm:
    1. Get transactions from last 90 days (3 months)
    2. Group by merchant (expenses only)
    3. For each merchant with charges in at least 2 of 3 months:
       - Check if amounts are consistent (within ±$2 tolerance)
       - If consistent, classify as subscription
    4. Classify category, calculate monthly/annual totals

    Returns: subscriptions list, monthly_total, annual_total
    """
    period_days = 90

    transactions = get_transactions(client_id, period_days)
    log_structured(
        "INFO", "Transactions retrieved for subscription detection",
        client_id=client_id, count=len(transactions), period_days=period_days,
    )

    if not transactions:
        return {"subscriptions": [], "monthly_total": 0.0, "annual_total": 0.0}

    # Group expense transactions by merchant, tracking month and amount
    merchant_months: dict[str, dict[str, list[dict]]] = defaultdict(lambda: defaultdict(list))

    for tx in transactions:
        if tx.get("type", "expense") != "expense":
            continue
        merchant = tx.get("merchant", "Unknown")
        tx_date = tx.get("date", "")
        month_key = tx_date[:7]  # YYYY-MM
        merchant_months[merchant][month_key].append(tx)

    # Detect subscriptions: merchant must appear in at least 2 months with consistent amounts
    subscriptions = []

    for merchant, months_data in merchant_months.items():
        distinct_months = len(months_data)
        if distinct_months < SUBSCRIPTION_MIN_MONTHS:
            continue

        # Get all amounts for this merchant across months
        all_amounts = []
        last_date = ""
        for month_key, txs in months_data.items():
            for tx in txs:
                amount = float(tx.get("amount", 0))
                all_amounts.append(amount)
                tx_date = tx.get("date", "")
                if tx_date > last_date:
                    last_date = tx_date

        if not all_amounts:
            continue

        # Check amount consistency: all amounts within ±$2 of each other
        min_amount = min(all_amounts)
        max_amount = max(all_amounts)
        if (max_amount - min_amount) > SUBSCRIPTION_AMOUNT_TOLERANCE * 2:
            continue

        # This is a subscription - calculate average monthly amount
        avg_amount = round(sum(all_amounts) / len(all_amounts), 2)
        category = classify_subscription_category(merchant)

        subscriptions.append({
            "merchant": merchant,
            "monthly_amount": avg_amount,
            "category": category,
            "last_charge_date": last_date[:10],  # YYYY-MM-DD
            "annual_projection": round(avg_amount * 12, 2),
        })

    # Sort subscriptions by monthly_amount descending
    subscriptions.sort(key=lambda s: s["monthly_amount"], reverse=True)

    # Calculate totals
    monthly_total = round(sum(s["monthly_amount"] for s in subscriptions), 2)
    annual_total = round(monthly_total * 12, 2)

    log_structured(
        "INFO", "Subscription detection completed",
        client_id=client_id, subscriptions_found=len(subscriptions),
        monthly_total=monthly_total, annual_total=annual_total,
    )

    return {
        "subscriptions": subscriptions,
        "monthly_total": monthly_total,
        "annual_total": annual_total,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Bedrock Agent Response Helpers
# ─────────────────────────────────────────────────────────────────────────────


def build_response(event: dict, status_code: int, body: dict) -> dict:
    """Build Bedrock Agent response format."""
    return {
        "messageVersion": "1.0",
        "response": {
            "actionGroup": event.get("actionGroup", "analyze-transactions"),
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
    """Bedrock Agent Action Group handler for transaction analysis."""
    start_time = datetime.now(timezone.utc)

    log_structured("INFO", "Transaction analysis request received", event=event)

    # Extract parameters from Bedrock Agent event
    api_path = event.get("apiPath", "")
    parameters = {p["name"]: p["value"] for p in event.get("parameters", [])}
    client_id = parameters.get("client_id", "").strip()

    log_structured("INFO", "Processing request", api_path=api_path, client_id=client_id)

    # Validate client_id
    if not client_id:
        log_structured("WARNING", "Missing client_id parameter")
        return build_error_response(event, 400, "El parámetro client_id es requerido.")

    # Route to the appropriate analysis function
    if api_path == "/analyze-gastos-hormiga":
        period_months = int(parameters.get("period_months", "1"))
        result = analyze_gastos_hormiga(client_id, period_months)
    elif api_path == "/detect-subscriptions":
        result = detect_subscriptions(client_id)
    else:
        log_structured("WARNING", "Unknown api_path", api_path=api_path)
        return build_error_response(event, 400, f"Ruta no reconocida: {api_path}")

    # Check if the result contains an error (e.g., client not found)
    if "error" in result:
        return build_error_response(event, 404, result["error"])

    # Log latency
    elapsed_ms = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
    log_structured(
        "INFO", "Transaction analysis completed",
        api_path=api_path, client_id=client_id, latency_ms=round(elapsed_ms, 2),
    )

    return build_response(event, 200, result)
