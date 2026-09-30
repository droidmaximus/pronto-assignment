import json
import sqlite3
from pathlib import Path

import pytest

from sales_agent.runner import ParamError, run_query

FIXTURE_DB = Path(__file__).parent / "fixtures" / "olist_fixture.sqlite"
EXPECTED_DIR = Path(__file__).parent / "expected"

QUERY_CASE_FILES = [
    ("top_categories_by_revenue", "top_categories_by_revenue.json"),
    ("category_revenue_by_state", "category_revenue_by_state.json"),
    ("compare_category_revenue", "compare_category_revenue.json"),
    ("place_summary", "place_summary.json"),
    ("worst_categories_by_reviews", "worst_categories_by_reviews.json"),
    ("top_sellers_by_revenue", "top_sellers_by_revenue.json"),
    ("top_sellers_by_orders", "top_sellers_by_orders.json"),
    ("top_sellers_by_review", "top_sellers_by_review.json"),
]


def _load_cases():
    cases = []
    for query_id, filename in QUERY_CASE_FILES:
        data = json.loads((EXPECTED_DIR / filename).read_text())
        for case_name, case in data.items():
            cases.append((query_id, case_name, case))
    return cases


def _normalize(value):
    if value is None:
        return None
    if isinstance(value, str):
        return value
    return round(float(value), 2)


def _normalize_row(row):
    return tuple(_normalize(cell) for cell in row)


@pytest.fixture
def fixture_connection():
    conn = sqlite3.connect(FIXTURE_DB)
    try:
        yield conn
    finally:
        conn.close()


@pytest.mark.parametrize(
    ("query_id", "case_name", "case"),
    _load_cases(),
    ids=[f"{qid}:{name}" for qid, name, _ in _load_cases()],
)
def test_expected_query_results(fixture_connection, query_id, case_name, case):
    result = run_query(fixture_connection, query_id, case["params"])
    assert result.columns == case["columns"]
    expected_rows = [_normalize_row(row) for row in case["rows"]]
    actual_rows = [_normalize_row(row) for row in result.rows]
    assert actual_rows == expected_rows


def test_rejects_bad_params(fixture_connection):
    with pytest.raises(ParamError):
        run_query(
            fixture_connection,
            "top_categories_by_revenue",
            {"year": 2015, "delivered_only": False, "limit": 5},
        )
    with pytest.raises(ParamError):
        run_query(
            fixture_connection,
            "top_categories_by_revenue",
            {"year": 2017, "delivered_only": False, "limit": 21},
        )
    with pytest.raises(ParamError):
        run_query(
            fixture_connection,
            "place_summary",
            {
                "place_type": "zip",
                "place": "SP",
                "year": 2017,
                "delivered_only": False,
            },
        )
    with pytest.raises(ParamError):
        run_query(fixture_connection, "not_a_query", {})


def test_display_sql_is_not_executed_text(fixture_connection):
    result = run_query(
        fixture_connection,
        "top_categories_by_revenue",
        {"year": 2017, "delivered_only": False, "limit": 5},
    )
    assert "2017" in result.sql_display
    assert ":year" not in result.sql_display
