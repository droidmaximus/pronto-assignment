from pathlib import Path
from sales_agent.chat import run_chat

FIXTURE = Path("tests/fixtures/olist_fixture.sqlite")


def test_two_turns_then_blank_line_exits():
    calls = {"n": 0}

    def complete_fn(messages):
        calls["n"] += 1
        if calls["n"] == 1:
            return '{"action":"query","id":"top_categories_by_revenue","params":{"year":2017,"delivered_only":false,"limit":5}}'
        return '{"action":"clarify","question":"Do you mean revenue, number of orders, or review score?"}'

    transcript = run_chat(
        ["Top categories in 2017", "Who are our best sellers?", ""],
        FIXTURE,
        complete_fn,
    )
    assert "watches" in transcript
    assert "review score" in transcript
