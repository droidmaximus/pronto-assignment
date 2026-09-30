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


def test_rejects_unknown_action():
    with pytest.raises(ParseError):
        parse_action('{"action":"sql","statement":"SELECT 1"}')
