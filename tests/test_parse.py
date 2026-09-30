import pytest
from sales_agent.parse import ParseError, parse_action


def test_query_clarify_and_refuse():
    assert parse_action('{"action":"query","id":"place_summary","params":{"year":2017}}')["action"] == "query"
    assert parse_action('{"action":"clarify","question":"State or city?"}')["question"] == "State or city?"
    assert parse_action('{"action":"refuse","reason":"No profit column."}')["reason"] == "No profit column."


def test_discards_sql_and_fences():
    text = '```json\n{"action":"query","id":"place_summary","params":{"year":2017},"sql":"DROP TABLE sales_lines"}\n```'
    action = parse_action(text)
    assert "sql" not in action
    assert action["id"] == "place_summary"


def test_extracts_json_after_a_label_and_fence():
    text = (
        "Query: category_revenue_by_state\n"
        "```json\n"
        '{"action":"query","id":"category_revenue_by_state",'
        '"params":{"year":2017,"delivered_only":false}}\n'
        "```"
    )
    action = parse_action(text)
    assert action["id"] == "category_revenue_by_state"
    assert action["params"]["year"] == 2017


def test_catalog_id_in_action_is_read_as_query():
    text = (
        '{"action":"compare_category_revenue","id":"compare_category_revenue",'
        '"params":{"year_a":2017,"year_b":2018,"delivered_only":true}}'
    )
    action = parse_action(text)
    assert action["action"] == "query"
    assert action["id"] == "compare_category_revenue"
    assert action["params"]["year_b"] == 2018


def test_rejects_unknown_action():
    with pytest.raises(ParseError):
        parse_action('{"action":"sql","statement":"SELECT 1"}')
