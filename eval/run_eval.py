from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path

import yaml

from eval.oracle import oracle_rows
from sales_agent.agent import respond
from sales_agent.llm import complete
from sales_agent.parse import ParseError, parse_action
from sales_agent.runner import run_query
from sales_agent.session import Session

_QUESTIONS_PATH = Path(__file__).resolve().parent / "questions.yaml"
_DEFAULT_DB = Path("data/olist.sqlite")
_RESULTS_PATH = Path(__file__).resolve().parent / "results.md"

_YEAR_ABSENT = "absent"


@dataclass(frozen=True, slots=True)
class GradeResult:
    passed: bool
    expected_action: str
    actual_action: str
    note: str


def load_questions() -> list[dict]:
    data = yaml.safe_load(_QUESTIONS_PATH.read_text())
    return data


def _format_action(parsed_action: dict | None, session: Session, executed: bool) -> str:
    if parsed_action is None:
        return "parse_failure"
    if parsed_action["action"] == "query":
        if executed:
            return f"query:{session.last_query_id}"
        query_id = parsed_action.get("id") or "?"
        return f"query:{query_id} (not run)"
    return parsed_action["action"]


def _format_expected(expect: dict) -> str:
    if expect["action"] == "query":
        return f"query:{expect['id']}"
    return expect["action"]


def _params_match(expected: dict, actual: dict) -> bool:
    for key, value in expected.items():
        if value == _YEAR_ABSENT:
            if key in actual and actual[key] is not None:
                return False
            continue
        if actual.get(key) != value:
            return False
    return True


def _normalize_row(row: tuple) -> tuple:
    out: list = []
    for cell in row:
        if cell is None or isinstance(cell, str):
            out.append(cell)
        else:
            out.append(round(float(cell), 2))
    return tuple(out)


def grade_turn(
    connection: sqlite3.Connection,
    session: Session,
    user_message: str,
    db_path: Path,
    expect: dict,
    complete_fn,
) -> GradeResult:
    expected_action = _format_expected(expect)
    prior_queries = session.queries_run
    parsed_action: dict | None = None

    def wrapping_complete(messages):
        nonlocal parsed_action
        text = complete_fn(messages)
        try:
            parsed_action = parse_action(text)
        except (ParseError, ValueError):
            parsed_action = None
        return text

    respond(session, user_message, db_path, wrapping_complete)
    executed = session.queries_run > prior_queries
    actual_action = _format_action(parsed_action, session, executed)

    if expect["action"] == "query":
        if not executed or session.last_query_id != expect["id"]:
            return GradeResult(
                passed=False,
                expected_action=expected_action,
                actual_action=actual_action,
                note="unexpected template id",
            )
        if not _params_match(expect["params"], session.last_params):
            return GradeResult(
                passed=False,
                expected_action=expected_action,
                actual_action=actual_action,
                note="parameter mismatch",
            )
        agent = run_query(connection, session.last_query_id, session.last_params)
        oracle = oracle_rows(connection, session.last_query_id, session.last_params)
        agent_norm = [_normalize_row(row) for row in agent.rows]
        oracle_norm = [_normalize_row(row) for row in oracle]
        if agent_norm != oracle_norm:
            return GradeResult(
                passed=False,
                expected_action=expected_action,
                actual_action=actual_action,
                note="oracle row mismatch",
            )
        return GradeResult(
            passed=True,
            expected_action=expected_action,
            actual_action=actual_action,
            note="ok",
        )

    if executed:
        return GradeResult(
            passed=False,
            expected_action=expected_action,
            actual_action=actual_action,
            note="query ran when none was expected",
        )
    if parsed_action is None or parsed_action.get("action") != expect["action"]:
        return GradeResult(
            passed=False,
            expected_action=expected_action,
            actual_action=actual_action,
            note="wrong non-query action",
        )
    return GradeResult(
        passed=True,
        expected_action=expected_action,
        actual_action=actual_action,
        note="ok",
    )


def _turn_label(question_id: int, turn_index: int, turn_count: int) -> str:
    if turn_count == 1:
        return str(question_id)
    return f"{question_id}-{turn_index + 1}"


def main() -> None:
    db_path = _DEFAULT_DB
    questions = load_questions()
    sessions: dict[str, Session] = {}
    lines = [
        "| id | result | expected | actual | note |",
        "| --- | --- | --- | --- | --- |",
    ]

    connection = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        for question in questions:
            session_key = question["session"]
            if session_key not in sessions:
                sessions[session_key] = Session()
            session = sessions[session_key]
            turns = question["turns"]
            for index, turn in enumerate(turns):
                result = grade_turn(
                    connection,
                    session,
                    turn["user"],
                    db_path,
                    turn["expect"],
                    complete_fn=complete,
                )
                label = _turn_label(question["id"], index, len(turns))
                status = "pass" if result.passed else "fail"
                lines.append(
                    f"| {label} | {status} | {result.expected_action} | "
                    f"{result.actual_action} | {result.note} |"
                )
    finally:
        connection.close()

    _RESULTS_PATH.write_text("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
