"""
Unit tests for Liquidity Alerter Lambda.
Tests proyección de liquidez (Req 4.1, 4.2) and evaluación de compras (Req 4.3, 4.6).
"""

import json
import os
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

# Set env vars before importing the module
os.environ["TRANSACTIONS_TABLE"] = "test-transactions"
os.environ["CLIENTS_TABLE"] = "test-clients"
os.environ["AWS_DEFAULT_REGION"] = "us-east-1"

# Mock boto3 resource before importing index module
with patch("boto3.resource") as mock_resource:
    mock_dynamodb = MagicMock()
    mock_resource.return_value = mock_dynamodb
    from index import (
        calculate_avg_daily_spend,
        calculate_current_balance,
        calculate_deficit_date,
        determine_alert_level,
        evaluate_purchase,
        generate_liquidity_recommendations,
        handler,
        project_liquidity,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Test Data Fixtures
# ─────────────────────────────────────────────────────────────────────────────

HEALTHY_CLIENT = {
    "client_id": "client-001",
    "name": "María Profesional",
    "monthly_income": Decimal("1800"),
    "monthly_fixed_expenses": Decimal("900"),
    "savings_balance": Decimal("5000"),
    "debt_balance": Decimal("2000"),
}

CRITICAL_CLIENT = {
    "client_id": "client-003",
    "name": "Ana Estudiante",
    "monthly_income": Decimal("600"),
    "monthly_fixed_expenses": Decimal("550"),
    "savings_balance": Decimal("100"),
    "debt_balance": Decimal("1500"),
}

REGULAR_CLIENT = {
    "client_id": "client-002",
    "name": "Carlos Emprendedor",
    "monthly_income": Decimal("1500"),
    "monthly_fixed_expenses": Decimal("1100"),
    "savings_balance": Decimal("1200"),
    "debt_balance": Decimal("4500"),
}


def make_expense_tx(amount, date_str="2025-01-15"):
    """Helper to create an expense transaction."""
    return {
        "client_id": "client-001",
        "transaction_id": "tx-001",
        "amount": Decimal(str(amount)),
        "type": "expense",
        "category": "groceries",
        "merchant": "Supermarket",
        "date": date_str,
    }


def make_income_tx(amount, date_str="2025-01-01"):
    """Helper to create an income transaction."""
    return {
        "client_id": "client-001",
        "transaction_id": "tx-inc-001",
        "amount": Decimal(str(amount)),
        "type": "income",
        "category": "salary",
        "merchant": "Employer",
        "date": date_str,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Task 9.1 Tests: Proyección de Liquidez
# ─────────────────────────────────────────────────────────────────────────────


class TestCalculateCurrentBalance:
    """Tests for calculate_current_balance function."""

    def test_balance_with_no_expenses(self):
        """Balance = savings + monthly_income when no expenses this month."""
        result = calculate_current_balance(HEALTHY_CLIENT, [])
        # savings_balance(5000) + (monthly_income(1800) - expenses(0))
        assert result == 6800.0

    def test_balance_with_expenses(self):
        """Balance subtracts current month expenses."""
        expenses = [make_expense_tx(200), make_expense_tx(300), make_expense_tx(100)]
        result = calculate_current_balance(HEALTHY_CLIENT, expenses)
        # 5000 + (1800 - 600) = 6200
        assert result == 6200.0

    def test_balance_ignores_income_transactions(self):
        """Only expenses reduce the balance."""
        txs = [make_expense_tx(500), make_income_tx(1000)]
        result = calculate_current_balance(HEALTHY_CLIENT, txs)
        # 5000 + (1800 - 500) = 6300
        assert result == 6300.0

    def test_balance_critical_client_high_expenses(self):
        """Critical client with expenses near income."""
        expenses = [make_expense_tx(500)]
        result = calculate_current_balance(CRITICAL_CLIENT, expenses)
        # 100 + (600 - 500) = 200
        assert result == 200.0


class TestCalculateAvgDailySpend:
    """Tests for calculate_avg_daily_spend function."""

    def test_no_transactions(self):
        """No transactions means zero avg spend."""
        result = calculate_avg_daily_spend([])
        assert result == 0.0

    def test_only_income_transactions(self):
        """Income transactions don't count as spending."""
        txs = [make_income_tx(1800)]
        result = calculate_avg_daily_spend(txs)
        assert result == 0.0

    def test_calculates_average_over_30_days(self):
        """Total expenses divided by 30."""
        # 10 expenses of $30 each = $300 total / 30 = $10/day
        txs = [make_expense_tx(30) for _ in range(10)]
        result = calculate_avg_daily_spend(txs)
        assert result == 10.0

    def test_mixed_transactions(self):
        """Only expense types are counted."""
        txs = [make_expense_tx(60), make_expense_tx(90), make_income_tx(1500)]
        result = calculate_avg_daily_spend(txs)
        # (60 + 90) / 30 = 5.0
        assert result == 5.0


class TestDetermineAlertLevel:
    """Tests for determine_alert_level function."""

    def test_critical_when_projected_negative(self):
        """Critical alert when projected balance is negative."""
        result = determine_alert_level(
            current_balance=1000, projected_balance=-100, monthly_fixed_expenses=900
        )
        assert result == "critical"

    def test_warning_when_balance_below_1_2x(self):
        """Warning when current balance < 1.2 * fixed expenses."""
        # 1.2 * 900 = 1080, balance is 1000 (below)
        result = determine_alert_level(
            current_balance=1000, projected_balance=500, monthly_fixed_expenses=900
        )
        assert result == "warning"

    def test_none_when_balance_above_1_5x(self):
        """No alert when current balance >= 1.5 * fixed expenses."""
        # 1.5 * 900 = 1350, balance is 1500 (above)
        result = determine_alert_level(
            current_balance=1500, projected_balance=1000, monthly_fixed_expenses=900
        )
        assert result == "none"

    def test_warning_between_1_2x_and_1_5x(self):
        """Warning when balance is between 1.2x and 1.5x of fixed expenses."""
        # 1.2 * 900 = 1080, 1.5 * 900 = 1350, balance is 1200 (between)
        result = determine_alert_level(
            current_balance=1200, projected_balance=800, monthly_fixed_expenses=900
        )
        assert result == "warning"

    def test_critical_takes_priority_over_warning(self):
        """Critical (projected < 0) overrides warning condition."""
        result = determine_alert_level(
            current_balance=500, projected_balance=-200, monthly_fixed_expenses=900
        )
        assert result == "critical"


class TestCalculateDeficitDate:
    """Tests for calculate_deficit_date function."""

    def test_no_deficit_if_no_spending(self):
        """No deficit date when avg daily spend is 0."""
        result = calculate_deficit_date(current_balance=1000, avg_daily_spend=0)
        assert result is None

    def test_deficit_date_calculated_correctly(self):
        """Deficit date is balance / avg_daily_spend days from now."""
        # $1000 balance / $100 daily = 10 days
        result = calculate_deficit_date(current_balance=1000, avg_daily_spend=100)
        expected = (datetime.now(timezone.utc) + timedelta(days=10)).strftime("%Y-%m-%d")
        assert result == expected

    def test_deficit_today_if_balance_zero(self):
        """Returns today if balance is already 0 or negative."""
        result = calculate_deficit_date(current_balance=0, avg_daily_spend=50)
        expected = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        assert result == expected

    def test_negative_balance_returns_today(self):
        """Negative balance means deficit is already here."""
        result = calculate_deficit_date(current_balance=-100, avg_daily_spend=50)
        expected = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        assert result == expected


class TestGenerateLiquidityRecommendations:
    """Tests for generate_liquidity_recommendations function."""

    def test_critical_generates_three_recommendations(self):
        """Critical alert generates 3 action-oriented recommendations."""
        recs = generate_liquidity_recommendations(
            alert_level="critical", current_balance=500,
            projected_balance=-200, monthly_fixed_expenses=900,
            avg_daily_spend=100,
        )
        assert len(recs) == 3
        assert "30%" in recs[0]  # reduce variables
        assert "Difiere" in recs[1]  # defer purchases
        assert "transferir" in recs[2]  # transfer from savings

    def test_warning_generates_three_recommendations(self):
        """Warning alert generates recommendations."""
        recs = generate_liquidity_recommendations(
            alert_level="warning", current_balance=1000,
            projected_balance=500, monthly_fixed_expenses=900,
            avg_daily_spend=70,
        )
        assert len(recs) == 3
        assert "20%" in recs[1]

    def test_none_generates_positive_recommendation(self):
        """No alert generates positive reinforcement."""
        recs = generate_liquidity_recommendations(
            alert_level="none", current_balance=2000,
            projected_balance=1500, monthly_fixed_expenses=900,
            avg_daily_spend=70,
        )
        assert len(recs) == 1
        assert "saludable" in recs[0]


class TestProjectLiquidity:
    """Integration tests for project_liquidity function."""

    @patch("index.get_transactions")
    @patch("index.get_current_month_transactions")
    @patch("index.get_client_profile")
    def test_healthy_client_no_alert(self, mock_profile, mock_month_txs, mock_txs_30d):
        """Healthy client gets no alert with comfortable balance."""
        mock_profile.return_value = HEALTHY_CLIENT
        mock_month_txs.return_value = [make_expense_tx(300)]
        # 30 days of light spending: 15 txs of $20 = $300 total -> $10/day avg
        mock_txs_30d.return_value = [make_expense_tx(20) for _ in range(15)]

        result = project_liquidity("client-001", projection_days=7)

        assert result["current_balance"] == 6500.0  # 5000 + (1800 - 300)
        assert result["avg_daily_spend"] == 10.0
        assert result["projected_balance"] == 6430.0  # 6500 - (10 * 7)
        assert result["alert_level"] == "none"
        assert len(result["recommendations"]) >= 1

    @patch("index.get_transactions")
    @patch("index.get_current_month_transactions")
    @patch("index.get_client_profile")
    def test_critical_client_gets_critical_alert(self, mock_profile, mock_month_txs, mock_txs_30d):
        """Critical client with high spending gets critical alert."""
        mock_profile.return_value = CRITICAL_CLIENT
        mock_month_txs.return_value = [make_expense_tx(500)]
        # High daily spending: $30/day avg over 30 days = $900 total
        mock_txs_30d.return_value = [make_expense_tx(30) for _ in range(30)]

        result = project_liquidity("client-003", projection_days=7)

        # current_balance: 100 + (600 - 500) = 200
        assert result["current_balance"] == 200.0
        assert result["avg_daily_spend"] == 30.0
        # projected: 200 - (30 * 7) = -10
        assert result["projected_balance"] == -10.0
        assert result["alert_level"] == "critical"

    @patch("index.get_transactions")
    @patch("index.get_current_month_transactions")
    @patch("index.get_client_profile")
    def test_client_not_found(self, mock_profile, mock_month_txs, mock_txs_30d):
        """Returns error when client doesn't exist."""
        mock_profile.return_value = None

        result = project_liquidity("unknown-client")

        assert "error" in result

    @patch("index.get_transactions")
    @patch("index.get_current_month_transactions")
    @patch("index.get_client_profile")
    def test_default_projection_days(self, mock_profile, mock_month_txs, mock_txs_30d):
        """Default projection is 7 days."""
        mock_profile.return_value = HEALTHY_CLIENT
        mock_month_txs.return_value = []
        mock_txs_30d.return_value = [make_expense_tx(60) for _ in range(30)]  # $60/day

        result = project_liquidity("client-001")

        # projected = 6800 - (60 * 7) = 6380
        assert result["projected_balance"] == 6380.0


# ─────────────────────────────────────────────────────────────────────────────
# Task 9.2 Tests: Evaluación de Compras
# ─────────────────────────────────────────────────────────────────────────────


class TestEvaluatePurchase:
    """Integration tests for evaluate_purchase function."""

    @patch("index.get_current_month_transactions")
    @patch("index.get_client_profile")
    def test_affordable_purchase_low_impact(self, mock_profile, mock_month_txs):
        """Small purchase for healthy client is affordable with low impact."""
        mock_profile.return_value = HEALTHY_CLIENT
        mock_month_txs.return_value = [make_expense_tx(300)]

        result = evaluate_purchase("client-001", 100.0)

        assert result["can_afford"] is True
        assert result["impact_on_liquidity"] == "bajo"
        assert result["remaining_balance_after"] == 6400.0  # 6500 - 100
        assert "sin comprometer" in result["recommendation"]

    @patch("index.get_current_month_transactions")
    @patch("index.get_client_profile")
    def test_unaffordable_purchase_critical_impact(self, mock_profile, mock_month_txs):
        """Large purchase that exceeds balance is critical."""
        mock_profile.return_value = CRITICAL_CLIENT
        mock_month_txs.return_value = [make_expense_tx(500)]

        # Current balance: 100 + (600 - 500) = 200
        # Purchase of $300 would leave -100
        result = evaluate_purchase("client-003", 300.0)

        assert result["can_afford"] is False
        assert result["impact_on_liquidity"] == "crítico"
        assert result["remaining_balance_after"] == -100.0

    @patch("index.get_current_month_transactions")
    @patch("index.get_client_profile")
    def test_moderate_purchase_impact(self, mock_profile, mock_month_txs):
        """Purchase that leaves balance between fixed expenses and 1.2x."""
        mock_profile.return_value = REGULAR_CLIENT
        mock_month_txs.return_value = [make_expense_tx(200)]

        # Balance: 1200 + (1500 - 200) = 2500
        # 1.2 * 1100 = 1320
        # Purchase of 1300 leaves 1200 (below 1320) = moderado
        result = evaluate_purchase("client-002", 1300.0)

        assert result["can_afford"] is True
        assert result["impact_on_liquidity"] == "moderado"
        assert result["remaining_balance_after"] == 1200.0

    @patch("index.get_current_month_transactions")
    @patch("index.get_client_profile")
    def test_purchase_leaves_below_fixed_expenses(self, mock_profile, mock_month_txs):
        """Purchase that leaves balance below fixed expenses is high impact."""
        mock_profile.return_value = REGULAR_CLIENT
        mock_month_txs.return_value = [make_expense_tx(200)]

        # Balance: 2500. Purchase of 1500 leaves 1000 (< fixed 1100) = alto
        result = evaluate_purchase("client-002", 1500.0)

        assert result["can_afford"] is False
        assert result["impact_on_liquidity"] == "alto"

    @patch("index.get_current_month_transactions")
    @patch("index.get_client_profile")
    def test_client_not_found(self, mock_profile, mock_month_txs):
        """Returns error for unknown client."""
        mock_profile.return_value = None

        result = evaluate_purchase("unknown", 50.0)

        assert "error" in result


# ─────────────────────────────────────────────────────────────────────────────
# Handler Tests (Bedrock Agent Integration)
# ─────────────────────────────────────────────────────────────────────────────


class TestHandler:
    """Tests for the Lambda handler function."""

    def _make_event(self, api_path, parameters):
        """Helper to create Bedrock Agent event."""
        return {
            "actionGroup": "check-liquidity",
            "apiPath": api_path,
            "httpMethod": "POST",
            "parameters": [{"name": k, "value": v} for k, v in parameters.items()],
        }

    @patch("index.project_liquidity")
    def test_project_liquidity_route(self, mock_project):
        """Routes /project-liquidity to project_liquidity function."""
        mock_project.return_value = {
            "current_balance": 1500.0,
            "projected_balance": 1200.0,
            "alert_level": "none",
            "deficit_date": None,
            "recommendations": ["Todo bien"],
            "avg_daily_spend": 42.86,
        }

        event = self._make_event("/project-liquidity", {
            "client_id": "client-001",
            "projection_days": "7",
        })
        result = handler(event, None)

        assert result["response"]["httpStatusCode"] == 200
        body = json.loads(result["response"]["responseBody"]["application/json"]["body"])
        assert body["alert_level"] == "none"
        mock_project.assert_called_once_with("client-001", 7)

    @patch("index.evaluate_purchase")
    def test_evaluate_purchase_route(self, mock_eval):
        """Routes /evaluate-purchase to evaluate_purchase function."""
        mock_eval.return_value = {
            "can_afford": True,
            "impact_on_liquidity": "bajo",
            "remaining_balance_after": 1400.0,
            "recommendation": "Puedes comprar.",
        }

        event = self._make_event("/evaluate-purchase", {
            "client_id": "client-001",
            "purchase_amount": "100",
        })
        result = handler(event, None)

        assert result["response"]["httpStatusCode"] == 200
        body = json.loads(result["response"]["responseBody"]["application/json"]["body"])
        assert body["can_afford"] is True
        mock_eval.assert_called_once_with("client-001", 100.0)

    def test_missing_client_id_returns_400(self):
        """Returns 400 when client_id is missing."""
        event = self._make_event("/project-liquidity", {"projection_days": "7"})
        result = handler(event, None)

        assert result["response"]["httpStatusCode"] == 400
        body = json.loads(result["response"]["responseBody"]["application/json"]["body"])
        assert "client_id" in body["error"]

    def test_unknown_path_returns_400(self):
        """Returns 400 for unknown API paths."""
        event = self._make_event("/unknown-path", {"client_id": "client-001"})
        result = handler(event, None)

        assert result["response"]["httpStatusCode"] == 400
        body = json.loads(result["response"]["responseBody"]["application/json"]["body"])
        assert "no reconocida" in body["error"]

    def test_invalid_purchase_amount_returns_400(self):
        """Returns 400 for non-numeric purchase amount."""
        event = self._make_event("/evaluate-purchase", {
            "client_id": "client-001",
            "purchase_amount": "abc",
        })
        result = handler(event, None)

        assert result["response"]["httpStatusCode"] == 400
        body = json.loads(result["response"]["responseBody"]["application/json"]["body"])
        assert "número válido" in body["error"]

    def test_zero_purchase_amount_returns_400(self):
        """Returns 400 for zero or negative purchase amount."""
        event = self._make_event("/evaluate-purchase", {
            "client_id": "client-001",
            "purchase_amount": "0",
        })
        result = handler(event, None)

        assert result["response"]["httpStatusCode"] == 400
        body = json.loads(result["response"]["responseBody"]["application/json"]["body"])
        assert "mayor a cero" in body["error"]

    @patch("index.project_liquidity")
    def test_client_not_found_returns_404(self, mock_project):
        """Returns 404 when client not found."""
        mock_project.return_value = {"error": "Cliente 'x' no encontrado en el sistema."}

        event = self._make_event("/project-liquidity", {
            "client_id": "x",
            "projection_days": "7",
        })
        result = handler(event, None)

        assert result["response"]["httpStatusCode"] == 404

    def test_bedrock_response_format(self):
        """Validates response follows Bedrock Agent format."""
        event = self._make_event("/unknown-path", {"client_id": "client-001"})
        result = handler(event, None)

        assert result["messageVersion"] == "1.0"
        assert "response" in result
        assert "actionGroup" in result["response"]
        assert "apiPath" in result["response"]
        assert "httpMethod" in result["response"]
        assert "httpStatusCode" in result["response"]
        assert "responseBody" in result["response"]
        assert "application/json" in result["response"]["responseBody"]
