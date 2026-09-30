import sqlite3
from pathlib import Path

import pytest

from eval.oracle import oracle_rows
from eval.run_eval import grade_turn, load_questions
from sales_agent.runner import run_query
from sales_agent.session import Session

FIXTURE_DB = Path(__file__).parent / "fixtures" / "olist_fixture.sqlite"


@pytest.fixture
def fixture_connection():
    conn = sqlite3.connect(FIXTURE_DB)
    try:
        yield conn
    finally:
        conn.close()


def test_load_questions_has_twenty_entries_and_q14_has_two_turns():
    questions = load_questions()
    assert len(questions) == 20
    q14 = next(q for q in questions if q["id"] == 14)
    assert len(q14["turns"]) == 2


def test_grade_turn_passes_question_1(fixture_connection):
    questions = load_questions()
    q1 = questions[0]
    turn = q1["turns"][0]
    session = Session()

    def complete_fn(_messages):
        return (
            '{"action":"query","id":"top_categories_by_revenue",'
            '"params":{"year":2017,"delivered_only":false,"limit":5}}'
        )

    result = grade_turn(
        fixture_connection,
        session,
        turn["user"],
        FIXTURE_DB,
        turn["expect"],
        complete_fn,
    )
    assert result.passed, result.note

    agent = run_query(
        fixture_connection,
        session.last_query_id,
        session.last_params,
    )
    assert oracle_rows(
        fixture_connection,
        session.last_query_id,
        session.last_params,
    ) == agent.rows


def test_stale_query_does_not_satisfy_a_new_turn(fixture_connection):
    session = Session(
        last_query_id="top_categories_by_revenue",
        last_params={"year": 2017, "delivered_only": False, "limit": 5},
        queries_run=1,
    )

    def complete_fn(_messages):
        return '{"action":"clarify","question":"Which categories should I include?"}'

    result = grade_turn(
        fixture_connection,
        session,
        "Break that down by customer state.",
        FIXTURE_DB,
        {
            "action": "query",
            "id": "top_categories_by_revenue",
            "params": {"year": 2017, "delivered_only": False, "limit": 5},
        },
        complete_fn,
    )
    assert not result.passed
    assert session.queries_run == 1


def test_repeating_the_same_template_still_counts(fixture_connection):
    session = Session(
        last_query_id="top_categories_by_revenue",
        last_params={"year": 2017, "delivered_only": False, "limit": 5},
        queries_run=1,
    )

    def complete_fn(_messages):
        return (
            '{"action":"query","id":"top_categories_by_revenue",'
            '"params":{"year":2017,"delivered_only":false,"limit":5}}'
        )

    result = grade_turn(
        fixture_connection,
        session,
        "Top 5 product categories by revenue in 2017.",
        FIXTURE_DB,
        {
            "action": "query",
            "id": "top_categories_by_revenue",
            "params": {"year": 2017, "delivered_only": False, "limit": 5},
        },
        complete_fn,
    )
    assert result.passed, result.note
    assert session.queries_run == 2


def test_grade_turn_fails_on_wrong_template_id(fixture_connection):
    questions = load_questions()
    q1 = questions[0]
    turn = q1["turns"][0]
    session = Session()

    def complete_fn(_messages):
        return (
            '{"action":"query","id":"top_sellers_by_revenue",'
            '"params":{"year":2017,"delivered_only":false,"limit":5}}'
        )

    result = grade_turn(
        fixture_connection,
        session,
        turn["user"],
        FIXTURE_DB,
        turn["expect"],
        complete_fn,
    )
    assert not result.passed
