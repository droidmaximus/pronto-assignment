from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from sales_agent.catalog import prompt_lines
from sales_agent.format import format_reply
from sales_agent.llm import LLMError, complete
from sales_agent.parse import ParseError, parse_action
from sales_agent.runner import ParamError, run_query
from sales_agent.session import Session, resolve_params

_PARSE_FAILURE = "I couldn't map that question to the catalog."
_MISSING_DB = "The database is missing. Run python -m sales_agent.ingest."
_QUERY_FAILED = "The query failed. No number is available."


def system_prompt() -> str:
    lines = [
        "You are a sales analytics assistant for the Olist Brazilian e-commerce dataset.",
        "Reply with exactly one JSON object and nothing else (no prose, no SQL).",
        "Use these shapes only:",
        '- Query: {"action":"query","id":"<catalog id>","params":{...}}',
        '- Clarify: {"action":"clarify","question":"<your question>"}',
        '- Refuse: {"action":"refuse","reason":"<short reason>"}',
        'The query field names are action and id, never template or name.',
        "Pick id from the catalog list below; params must match that template's fields.",
        "",
        "Metric rules:",
        "- Revenue is the sum of item price on each order line.",
        "- Delivered means order status is delivered.",
        "- Years in the data are 2016 through 2018.",
        "",
        "Behavior rules:",
        "- Set delivered_only to false unless the user asks for delivered orders.",
        "- Include year when the template requires it.",
        "- For a follow-up that only changes a filter, repeat the last template id "
        "shown in the session summary.",
        "- Use compare_category_revenue when the user compares years, and include year_b.",
        "- If the user asks for best sellers without revenue, orders, or review score, "
        "clarify and offer those three.",
        "- If the user names São Paulo without state or city, clarify and include the "
        "literal values SP and sao paulo.",
        "- If the user says last quarter without a year and a quarter number, clarify "
        "and say the data covers 2016 through 2018.",
        "- If no template fits, refuse.",
        "",
        "Catalog templates:",
        prompt_lines(),
    ]
    return "\n".join(lines)


def _session_summary(session: Session) -> str:
    if session.last_query_id is None:
        return ""
    return (
        "\n\nSession summary:\n"
        f"- last_query_id: {session.last_query_id}\n"
        f"- last_params: {session.last_params!r}\n"
    )


def _build_messages(session: Session, user_message: str) -> list[dict]:
    system = system_prompt() + _session_summary(session)
    messages: list[dict] = [{"role": "system", "content": system}]
    messages.extend(session.turns)
    messages.append({"role": "user", "content": user_message})
    return messages


def _parse_with_retry(
    messages: list[dict],
    complete_fn,
) -> tuple[dict | None, str | None]:
    text = complete_fn(messages)
    try:
        return parse_action(text), None
    except (ParseError, json.JSONDecodeError) as first_err:
        retry_messages = messages + [
            {"role": "assistant", "content": text},
            {"role": "user", "content": str(first_err)},
        ]
        text2 = complete_fn(retry_messages)
        try:
            return parse_action(text2), None
        except (ParseError, json.JSONDecodeError):
            return None, _PARSE_FAILURE


def _append_turn(session: Session, user_message: str, assistant_message: str) -> None:
    session.turns.append({"role": "user", "content": user_message})
    session.turns.append({"role": "assistant", "content": assistant_message})


def _remember_categories(session: Session, columns: list[str], rows: list[tuple]) -> None:
    if "category" not in columns:
        session.last_categories = []
        return
    idx = columns.index("category")
    seen: set[str] = set()
    ordered: list[str] = []
    for row in rows:
        name = row[idx]
        if name not in seen:
            seen.add(name)
            ordered.append(name)
    session.last_categories = ordered


def respond(
    session: Session,
    user_message: str,
    db_path: Path,
    complete_fn=complete,
) -> str:
    try:
        messages = _build_messages(session, user_message)
        action, failure = _parse_with_retry(messages, complete_fn)
        if failure is not None:
            _append_turn(session, user_message, failure)
            return failure

        if action["action"] == "clarify":
            question = action["question"]
            _append_turn(session, user_message, question)
            return question

        if action["action"] == "refuse":
            reason = action["reason"]
            _append_turn(session, user_message, reason)
            return reason

        query_id = action["id"]
        model_params = action["params"]
        try:
            params, question = resolve_params(session, query_id, model_params)
        except KeyError:
            _append_turn(session, user_message, _PARSE_FAILURE)
            return _PARSE_FAILURE

        if question is not None:
            _append_turn(session, user_message, question)
            return question

        if not db_path.is_file():
            _append_turn(session, user_message, _MISSING_DB)
            return _MISSING_DB

        try:
            connection = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
            try:
                result = run_query(connection, query_id, params)
            finally:
                connection.close()
        except sqlite3.Error:
            _append_turn(session, user_message, _QUERY_FAILED)
            return _QUERY_FAILED
        except ParamError:
            _append_turn(session, user_message, _QUERY_FAILED)
            return _QUERY_FAILED

        reply = format_reply(result)
        session.last_query_id = query_id
        session.last_params = dict(result.params)
        _remember_categories(session, result.columns, result.rows)
        _append_turn(session, user_message, reply)
        return reply
    except LLMError as exc:
        return str(exc)
