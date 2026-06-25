"""
Unit tests for Transaction Analyzer Lambda.
Tests gastos hormiga analysis and subscription detection logic.

Requirements tested: 2.1-2.5, 3.1-3.5
"""

import json
import os
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import MagicMock, patch

# Set env vars before importing the module
os.environ["TRANSACTIONS_TABLE"] = "test-transactions"
os.environ["CLIENTS_TABLE"] = "test-clients"
os.environ["AWS_DEFAULT_REGION"] = "us-east-1"

# Mock boto3 resource before importing index module
with patch("boto3.resource") as mock_resource:
    mock_dynamodb = MagicMock()
    mock_resource.return_value = mock_dynamodb
    import index  # noqa: E402


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures and helpers
# ─────────────────────────────────────────────────────────────────────────────

def make_event(api_path: str, params: dict) -> dict:
    """Create a Bedrock Agent event."""
    return {
        "actionGroup": "analyze-transactions",
        "apiPath": api_path,
        "httpMethod": "POST",
        "messageVersion": "1.0",
        "parameters": [
            {"name": k, "type": "string", "value": str(v)}
            for k, v in params.items()
        ],
    }


def make_transaction(amount, category="coffee_snacks", merchant="Sweet & Coffee",
                     days_ago=5, tx_type="expense"):
    """Create a transaction dict."""
    date = (datetime.now(timezone.utc) - timedelta(days=days_ago)).strftime("%Y-%m-%dT%H:%M:%SZ")
    return {
        "client_id": "client-002",
        "transaction_id": f"tx-{hash((amount, category, days_ago))}",
        "amount": Decimal(str(amount)),
        "category": category,
        "merchant": merchant,
        "date": date,
        "type": tx_type,
    }


def make_subscription_tx(merchant, amount, month_offset):
    """Create a subscription-like transaction for a given month offset."""
    date = (datetime.now(timezone.utc) - timedelta(days=30 * month_offset + 5))
    return {
        "client_id": "client-002",
        "transaction_id": f"tx-sub-{merchant}-{month_offset}",
        "amount": Decimal(str(amount)),
        "category": "subscriptions",
        "merchant": merchant,
        "date": date.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "type": "expense",
    }


CLIENT_PROFILE = {
    "client_id": "client-002",
    "name": "Carlos Emprendedor",
    "monthly_income": Decimal("1500"),
    "monthly_fixed_expenses": Decimal("1100"),
    "savings_balance": Decimal("1200"),
    "debt_balance": Decimal("4500"),
}


# ─────────────────────────────────────────────────────────────────────────────
# Test: Gastos Hormiga (Req 2.1-2.5)
# ─────────────────────────────────────────────────────────────────────────────


@patch("index.get_transactions")
@patch("index.get_client_profile")
def test_gastos_hormiga_filters_under_10(mock_profile, mock_txns):
    """Req 2.2: Only transactions < $10 should be counted."""
    from index import analyze_gastos_hormiga

    mock_profile.return_value = CLIENT_PROFILE
    mock_txns.return_value = [
        make_transaction(5.00, "coffee_snacks"),   # included
        make_transaction(9.99, "coffee_snacks"),   # included
        make_transaction(10.00, "coffee_snacks"),  # excluded (not < $10)
        make_transaction(25.00, "groceries"),      # excluded
    ]

    result = analyze_gastos_hormiga("client-002")
    assert "error" not in result
    # Total should be 5 + 9.99 = 14.99
    assert result["total_amount"] == 14.99


@patch("index.get_transactions")
@patch("index.get_client_profile")
def test_gastos_hormiga_groups_by_category(mock_profile, mock_txns):
    """Req 2.2: Group by category with total and frequency."""
    from index import analyze_gastos_hormiga

    mock_profile.return_value = CLIENT_PROFILE
    mock_txns.return_value = [
        make_transaction(3.50, "coffee_snacks", "Sweet & Coffee", 1),
        make_transaction(4.00, "coffee_snacks", "Juan Valdez", 2),
        make_transaction(5.00, "transport", "Uber", 3),
        make_transaction(2.00, "entertainment", "Cinemark", 4),
    ]

    result = analyze_gastos_hormiga("client-002")
    categories = result["categories"]

    # Top category should be coffee_snacks (3.50 + 4.00 = 7.50)
    assert categories[0]["name"] == "Cafeterías y snacks"
    assert categories[0]["total"] == 7.50
    assert categories[0]["frequency"] == 2


@patch("index.get_transactions")
@patch("index.get_client_profile")
def test_gastos_hormiga_top_3_only(mock_profile, mock_txns):
    """Req 2.4: Return only top 3 categories."""
    from index import analyze_gastos_hormiga

    mock_profile.return_value = CLIENT_PROFILE
    mock_txns.return_value = [
        make_transaction(8.00, "coffee_snacks"),
        make_transaction(7.00, "transport"),
        make_transaction(6.00, "entertainment"),
        make_transaction(5.00, "health"),
    ]

    result = analyze_gastos_hormiga("client-002")
    assert len(result["categories"]) == 3
    # Sorted desc by total: coffee(8), transport(7), entertainment(6)
    assert result["categories"][0]["total"] == 8.00
    assert result["categories"][1]["total"] == 7.00
    assert result["categories"][2]["total"] == 6.00


@patch("index.get_transactions")
@patch("index.get_client_profile")
def test_gastos_hormiga_percentage_calculation(mock_profile, mock_txns):
    """Req 2.3: Calculate percentage of monthly income."""
    from index import analyze_gastos_hormiga

    mock_profile.return_value = CLIENT_PROFILE  # income = 1500
    # Total gastos hormiga = 150 -> 10% of 1500
    mock_txns.return_value = [make_transaction(5.00) for _ in range(30)]

    result = analyze_gastos_hormiga("client-002")
    assert result["total_amount"] == 150.0
    assert result["percentage_of_income"] == 10.0
    assert result["alert_triggered"] is False


@patch("index.get_transactions")
@patch("index.get_client_profile")
def test_gastos_hormiga_alert_triggered_at_15_percent(mock_profile, mock_txns):
    """Req 2.5: Alert triggered when gastos >= 15% of income."""
    from index import analyze_gastos_hormiga

    mock_profile.return_value = CLIENT_PROFILE  # income = 1500
    # Total = 9.50 * 24 = 228 -> 15.2% of 1500 -> alert!
    mock_txns.return_value = [make_transaction(9.50) for _ in range(24)]

    result = analyze_gastos_hormiga("client-002")
    assert result["percentage_of_income"] >= 15.0
    assert result["alert_triggered"] is True


@patch("index.get_transactions")
@patch("index.get_client_profile")
def test_gastos_hormiga_no_transactions(mock_profile, mock_txns):
    """Edge case: no transactions should return empty results."""
    from index import analyze_gastos_hormiga

    mock_profile.return_value = CLIENT_PROFILE
    mock_txns.return_value = []

    result = analyze_gastos_hormiga("client-002")
    assert result["categories"] == []
    assert result["total_amount"] == 0.0
    assert result["percentage_of_income"] == 0.0
    assert result["alert_triggered"] is False


@patch("index.get_client_profile")
def test_gastos_hormiga_client_not_found(mock_profile):
    """Edge case: client not found should return error."""
    from index import analyze_gastos_hormiga

    mock_profile.return_value = None

    result = analyze_gastos_hormiga("client-999")
    assert "error" in result


# ─────────────────────────────────────────────────────────────────────────────
# Test: Subscription Detection (Req 3.1-3.5)
# ─────────────────────────────────────────────────────────────────────────────


@patch("index.get_transactions")
def test_detect_subscriptions_basic(mock_txns):
    """Req 3.1, 3.2: Detect recurring charges in 2+ months with ±$2 tolerance."""
    from index import detect_subscriptions

    # Netflix at $15.99 for 3 months -> subscription
    mock_txns.return_value = [
        make_subscription_tx("Netflix", 15.99, 0),
        make_subscription_tx("Netflix", 15.99, 1),
        make_subscription_tx("Netflix", 15.99, 2),
    ]

    result = detect_subscriptions("client-002")
    assert len(result["subscriptions"]) == 1
    sub = result["subscriptions"][0]
    assert sub["merchant"] == "Netflix"
    assert sub["monthly_amount"] == 15.99
    assert sub["annual_projection"] == 191.88


@patch("index.get_transactions")
def test_detect_subscriptions_tolerance(mock_txns):
    """Req 3.2: Amounts within ±$2 should still be detected."""
    from index import detect_subscriptions

    # SmartFit with slight variation ($45, $44, $46) - within ±$2
    mock_txns.return_value = [
        make_subscription_tx("SmartFit Gym", 45.00, 0),
        make_subscription_tx("SmartFit Gym", 44.00, 1),
        make_subscription_tx("SmartFit Gym", 46.00, 2),
    ]

    result = detect_subscriptions("client-002")
    assert len(result["subscriptions"]) == 1
    assert result["subscriptions"][0]["merchant"] == "SmartFit Gym"


@patch("index.get_transactions")
def test_detect_subscriptions_amount_too_variable(mock_txns):
    """Req 3.2: Amounts varying more than ±$2 should NOT be detected."""
    from index import detect_subscriptions

    # Supermaxi with high variation - NOT a subscription
    mock_txns.return_value = [
        make_subscription_tx("Supermaxi", 50.00, 0),
        make_subscription_tx("Supermaxi", 30.00, 1),
        make_subscription_tx("Supermaxi", 75.00, 2),
    ]

    result = detect_subscriptions("client-002")
    assert len(result["subscriptions"]) == 0


@patch("index.get_transactions")
def test_detect_subscriptions_category_classification(mock_txns):
    """Req 3.3: Classify subscriptions by category."""
    from index import detect_subscriptions

    mock_txns.return_value = [
        make_subscription_tx("Netflix", 15.99, 0),
        make_subscription_tx("Netflix", 15.99, 1),
        make_subscription_tx("SmartFit Gym", 45.00, 0),
        make_subscription_tx("SmartFit Gym", 45.00, 1),
        make_subscription_tx("iCloud", 2.99, 0),
        make_subscription_tx("iCloud", 2.99, 1),
    ]

    result = detect_subscriptions("client-002")
    subs_by_merchant = {s["merchant"]: s for s in result["subscriptions"]}

    assert subs_by_merchant["Netflix"]["category"] == "streaming"
    assert subs_by_merchant["SmartFit Gym"]["category"] == "gimnasio"
    assert subs_by_merchant["iCloud"]["category"] == "software"


@patch("index.get_transactions")
def test_detect_subscriptions_totals(mock_txns):
    """Req 3.5: Calculate monthly and annual totals."""
    from index import detect_subscriptions

    mock_txns.return_value = [
        make_subscription_tx("Netflix", 15.99, 0),
        make_subscription_tx("Netflix", 15.99, 1),
        make_subscription_tx("Spotify", 9.99, 0),
        make_subscription_tx("Spotify", 9.99, 1),
    ]

    result = detect_subscriptions("client-002")
    assert result["monthly_total"] == 25.98
    assert result["annual_total"] == 311.76


@patch("index.get_transactions")
def test_detect_subscriptions_no_transactions(mock_txns):
    """Edge case: no transactions returns empty subscriptions."""
    from index import detect_subscriptions

    mock_txns.return_value = []

    result = detect_subscriptions("client-002")
    assert result["subscriptions"] == []
    assert result["monthly_total"] == 0.0
    assert result["annual_total"] == 0.0


@patch("index.get_transactions")
def test_detect_subscriptions_single_month_not_detected(mock_txns):
    """Edge case: merchant in only 1 month should NOT be detected."""
    from index import detect_subscriptions

    mock_txns.return_value = [
        make_subscription_tx("Netflix", 15.99, 0),
        # Only 1 month - not a subscription pattern
    ]

    result = detect_subscriptions("client-002")
    assert len(result["subscriptions"]) == 0


# ─────────────────────────────────────────────────────────────────────────────
# Test: Lambda Handler Integration
# ─────────────────────────────────────────────────────────────────────────────


@patch("index.get_transactions")
@patch("index.get_client_profile")
def test_handler_gastos_hormiga_route(mock_profile, mock_txns):
    """Handler routes /analyze-gastos-hormiga correctly."""
    from index import handler

    mock_profile.return_value = CLIENT_PROFILE
    mock_txns.return_value = [make_transaction(5.00)]

    event = make_event("/analyze-gastos-hormiga", {"client_id": "client-002"})
    response = handler(event, None)

    assert response["messageVersion"] == "1.0"
    assert response["response"]["httpStatusCode"] == 200
    body = json.loads(response["response"]["responseBody"]["application/json"]["body"])
    assert "categories" in body
    assert "total_amount" in body
    assert "percentage_of_income" in body
    assert "alert_triggered" in body


@patch("index.get_transactions")
def test_handler_detect_subscriptions_route(mock_txns):
    """Handler routes /detect-subscriptions correctly."""
    from index import handler

    mock_txns.return_value = [
        make_subscription_tx("Netflix", 15.99, 0),
        make_subscription_tx("Netflix", 15.99, 1),
    ]

    event = make_event("/detect-subscriptions", {"client_id": "client-002"})
    response = handler(event, None)

    assert response["response"]["httpStatusCode"] == 200
    body = json.loads(response["response"]["responseBody"]["application/json"]["body"])
    assert "subscriptions" in body
    assert "monthly_total" in body
    assert "annual_total" in body


def test_handler_missing_client_id():
    """Handler returns 400 when client_id is missing."""
    from index import handler

    event = make_event("/analyze-gastos-hormiga", {"client_id": ""})
    response = handler(event, None)

    assert response["response"]["httpStatusCode"] == 400
    body = json.loads(response["response"]["responseBody"]["application/json"]["body"])
    assert "error" in body


def test_handler_unknown_path():
    """Handler returns 400 for unknown api path."""
    from index import handler

    event = make_event("/unknown-path", {"client_id": "client-002"})
    response = handler(event, None)

    assert response["response"]["httpStatusCode"] == 400


# ─────────────────────────────────────────────────────────────────────────────
# Test: classify_subscription_category
# ─────────────────────────────────────────────────────────────────────────────


def test_classify_exact_match():
    """Exact merchant names are classified correctly."""
    from index import classify_subscription_category

    assert classify_subscription_category("Netflix") == "streaming"
    assert classify_subscription_category("SmartFit Gym") == "gimnasio"
    assert classify_subscription_category("iCloud") == "software"


def test_classify_partial_match():
    """Partial merchant names are classified via fuzzy match."""
    from index import classify_subscription_category

    assert classify_subscription_category("Netflix Premium") == "streaming"


def test_classify_unknown_defaults_to_servicios():
    """Unknown merchants default to servicios_digitales."""
    from index import classify_subscription_category

    assert classify_subscription_category("Random Service") == "servicios_digitales"
