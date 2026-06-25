"""Unit tests for ISF Calculator core logic."""
import sys
from unittest.mock import MagicMock

# Mock boto3 before importing index (boto3 not available locally)
sys.modules["boto3"] = MagicMock()
sys.modules["boto3.dynamodb"] = MagicMock()
sys.modules["boto3.dynamodb.conditions"] = MagicMock()

sys.path.insert(0, ".")
from index import (
    calculate_income_expense_ratio,
    calculate_savings_level,
    calculate_debt_load,
    calculate_income_stability,
    get_interpretation,
    compute_isf,
)


def test_income_expense_ratio():
    # 2:1 ratio => (1800/900)*50 = 100, capped at 100
    assert calculate_income_expense_ratio(1800, 900) == 100.0
    # 1:1 ratio => (900/900)*50 = 50
    assert calculate_income_expense_ratio(900, 900) == 50.0
    # Zero expenses => 100
    assert calculate_income_expense_ratio(1000, 0) == 100.0
    # Very low income => (100/900)*50 = 5.55...
    result = calculate_income_expense_ratio(100, 900)
    assert 5.5 < result < 5.6


def test_savings_level():
    # 180/1800 * 100 = 10
    assert calculate_savings_level(180, 1800) == 10.0
    # No savings
    assert calculate_savings_level(0, 1800) == 0.0
    # Zero income edge case
    assert calculate_savings_level(500, 0) == 0.0
    # High savings capped at 100
    assert calculate_savings_level(2000, 1800) == 100.0


def test_debt_load():
    # No debt => 100
    assert calculate_debt_load(0, 21600) == 100.0
    # Debt exceeds annual income => 0
    assert calculate_debt_load(50000, 21600) == 0.0
    # Zero income edge case
    assert calculate_debt_load(5000, 0) == 0.0
    # Normal case: 2000 debt, 21600 annual => 100 - (2000/21600)*100
    expected = round(100 - (2000 / 21600) * 100, 10)
    assert abs(calculate_debt_load(2000, 21600) - expected) < 0.001


def test_income_stability():
    # Perfect stability (all same values)
    assert calculate_income_stability([1800, 1800, 1800]) == 100.0
    # Single value => default 70
    assert calculate_income_stability([1800]) == 70.0
    # Empty list => default 70
    assert calculate_income_stability([]) == 70.0
    # High variability
    result = calculate_income_stability([800, 2500, 1200])
    assert 0 <= result <= 100


def test_interpretation():
    assert get_interpretation(100) == "Excelente"
    assert get_interpretation(85) == "Excelente"
    assert get_interpretation(80) == "Excelente"
    assert get_interpretation(79) == "Bueno"
    assert get_interpretation(60) == "Bueno"
    assert get_interpretation(59) == "Regular"
    assert get_interpretation(40) == "Regular"
    assert get_interpretation(39) == "Crítico"
    assert get_interpretation(0) == "Crítico"


def test_compute_isf_healthy_profile():
    profile = {
        "client_id": "client-001",
        "monthly_income": 1800,
        "monthly_fixed_expenses": 900,
        "savings_balance": 5000,
        "debt_balance": 2000,
    }
    result = compute_isf(profile, [], 30)
    assert 0 <= result["isf_score"] <= 100
    assert result["interpretation"] in ["Excelente", "Bueno", "Regular", "Crítico"]
    assert "components" in result
    assert all(
        k in result["components"]
        for k in ["income_expense_ratio", "savings_level", "debt_load", "income_stability"]
    )
    print(f"Client-001 ISF: {result['isf_score']} ({result['interpretation']})")
    print(f"Components: {result['components']}")


def test_compute_isf_critical_profile():
    profile = {
        "client_id": "client-003",
        "monthly_income": 600,
        "monthly_fixed_expenses": 550,
        "savings_balance": 100,
        "debt_balance": 1500,
    }
    result = compute_isf(profile, [], 30)
    assert 0 <= result["isf_score"] <= 100
    # With 600 income, 550 expenses, low savings, high relative debt - should be lower score
    print(f"Client-003 ISF: {result['isf_score']} ({result['interpretation']})")
    print(f"Components: {result['components']}")


def test_compute_isf_with_transactions():
    profile = {
        "client_id": "client-002",
        "monthly_income": 1500,
        "monthly_fixed_expenses": 1100,
        "savings_balance": 1200,
        "debt_balance": 4500,
    }
    transactions = [
        {"amount": 1500, "type": "income", "date": "2025-01-15", "category": "salary"},
        {"amount": 50, "type": "expense", "date": "2025-01-16", "category": "groceries"},
        {"amount": 30, "type": "expense", "date": "2025-01-17", "category": "transport"},
        {"amount": 200, "type": "expense", "date": "2025-01-18", "category": "utilities"},
        {"amount": 100, "type": "expense", "date": "2025-01-19", "category": "restaurants"},
    ]
    result = compute_isf(profile, transactions, 30)
    assert 0 <= result["isf_score"] <= 100
    print(f"Client-002 ISF: {result['isf_score']} ({result['interpretation']})")
    print(f"Components: {result['components']}")


if __name__ == "__main__":
    test_income_expense_ratio()
    print("PASS: test_income_expense_ratio")
    test_savings_level()
    print("PASS: test_savings_level")
    test_debt_load()
    print("PASS: test_debt_load")
    test_income_stability()
    print("PASS: test_income_stability")
    test_interpretation()
    print("PASS: test_interpretation")
    test_compute_isf_healthy_profile()
    print("PASS: test_compute_isf_healthy_profile")
    test_compute_isf_critical_profile()
    print("PASS: test_compute_isf_critical_profile")
    test_compute_isf_with_transactions()
    print("PASS: test_compute_isf_with_transactions")
    print("\nAll tests passed!")
