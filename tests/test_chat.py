import io
import sys
from pathlib import Path

from sales_agent.chat import main, run_chat

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "olist_fixture.sqlite"


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


def test_main_prints_replies_from_stdin(monkeypatch, capsys):
    monkeypatch.setenv("SALES_DB", str(FIXTURE))
    monkeypatch.setattr(
        "sales_agent.chat.complete",
        lambda _messages: (
            '{"action":"query","id":"top_categories_by_revenue",'
            '"params":{"year":2017,"delivered_only":false,"limit":5}}'
        ),
    )
    monkeypatch.setattr(sys, "stdin", io.StringIO("Top categories in 2017\n\n"))
    main()
    output = capsys.readouterr().out
    assert "watches" in output
