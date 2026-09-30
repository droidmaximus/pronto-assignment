from pathlib import Path

from sales_agent.agent import respond, system_prompt
from sales_agent.catalog import list_templates
from sales_agent.llm import LLMError
from sales_agent.session import Session

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "olist_fixture.sqlite"
MISSING_DB = Path(__file__).resolve().parent / "fixtures" / "no_such_database.sqlite"


def test_system_prompt_lists_catalog_without_answers():
    text = system_prompt()
    for template in list_templates():
        assert template.id in text
    assert "400.0" not in text
    assert "Expected answer" not in text


def test_query_then_follow_up_breakdown():
    calls: list[list[dict]] = []

    def complete_fn(messages):
        calls.append(messages)
        if len(calls) == 1:
            return (
                '{"action":"query","id":"top_categories_by_revenue",'
                '"params":{"year":2017,"delivered_only":false,"limit":5}}'
            )
        return (
            '{"action":"query","id":"category_revenue_by_state",'
            '"params":{"delivered_only":true}}'
        )

    session = Session()
    reply1 = respond(session, "Top 5 categories in 2017", FIXTURE, complete_fn)
    assert "watches" in reply1
    assert "400.0" in reply1
    assert session.last_categories[0] == "watches"

    reply2 = respond(session, "Break down by state", FIXTURE, complete_fn)
    assert "SP" in reply2
    assert "category_revenue_by_state" in reply2
    assert session.last_params["year"] == 2017


def test_clarify_on_fresh_session():
    session = Session()

    def complete_fn(_messages):
        return (
            '{"action":"clarify","question":'
            '"Do you mean revenue, number of orders, or review score?"}'
        )

    reply = respond(session, "Who are our best sellers?", MISSING_DB, complete_fn)
    assert reply == "Do you mean revenue, number of orders, or review score?"
    assert session.last_query_id is None


def test_refuse():
    session = Session()

    def complete_fn(_messages):
        return (
            '{"action":"refuse","reason":"The catalog has no profit or cost data."}'
        )

    reply = respond(session, "What was profit in 2017?", FIXTURE, complete_fn)
    assert reply == "The catalog has no profit or cost data."


def test_double_parse_failure():
    session = Session()
    responses = iter(["not json", "not json"])

    def complete_fn(_messages):
        return next(responses)

    reply = respond(session, "Something vague", FIXTURE, complete_fn)
    assert reply == "I couldn't map that question to the catalog."


def test_parse_retry_then_valid_query():
    session = Session()
    responses = iter(
        [
            "not json",
            (
                '{"action":"query","id":"top_categories_by_revenue",'
                '"params":{"year":2017,"delivered_only":false,"limit":5}}'
            ),
        ]
    )

    def complete_fn(_messages):
        return next(responses)

    reply = respond(session, "Top categories 2017", FIXTURE, complete_fn)
    assert "watches" in reply


def test_missing_database_on_query():
    session = Session()

    def complete_fn(_messages):
        return (
            '{"action":"query","id":"top_categories_by_revenue",'
            '"params":{"year":2017,"delivered_only":false,"limit":5}}'
        )

    reply = respond(session, "Top categories", MISSING_DB, complete_fn)
    assert reply == "The database is missing. Run python -m sales_agent.ingest."


def test_llm_unreachable():
    session = Session()

    def complete_fn(_messages):
        raise LLMError("The model is unreachable.")

    reply = respond(session, "Hello", FIXTURE, complete_fn)
    assert reply == "The model is unreachable."


def test_clarify_without_database():
    session = Session()

    def complete_fn(_messages):
        return '{"action":"clarify","question":"Which year?"}'

    reply = respond(session, "Revenue?", MISSING_DB, complete_fn)
    assert reply == "Which year?"
