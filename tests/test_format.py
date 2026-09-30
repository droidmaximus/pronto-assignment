from sales_agent.format import format_reply
from sales_agent.runner import QueryResult


def test_numbers_come_from_rows_only():
    result = QueryResult(
        query_id="top_categories_by_revenue",
        columns=["category", "revenue"],
        rows=[("watches", 400.0)],
        sql_display="SELECT 1",
        params={"year": 2017},
    )
    text = format_reply(result)
    assert "watches" in text
    assert "400.0" in text
    assert "top_categories_by_revenue" in text
    assert "SELECT 1" in text


def test_empty_result_keeps_sql():
    result = QueryResult("place_summary", ["revenue", "order_count"], [], "SELECT 0", {"year": 2017})
    text = format_reply(result)
    assert "No rows matched." in text
    assert "SELECT 0" in text


def test_compare_labels_years():
    result = QueryResult(
        "compare_category_revenue",
        ["category", "revenue_a", "revenue_b"],
        [("watches", 400.0, 0.0)],
        "SELECT 1",
        {"year_a": 2017, "year_b": 2018},
    )
    text = format_reply(result)
    assert "revenue_a is 2017" in text
    assert "revenue_b is 2018" in text
