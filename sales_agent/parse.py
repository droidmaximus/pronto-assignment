from __future__ import annotations

import json
import re

from sales_agent.catalog import get_template

_VALID_ACTIONS = frozenset({"query", "clarify", "refuse"})


class ParseError(ValueError):
    pass


def _strip_fence(text: str) -> str:
    stripped = text.strip()
    match = re.search(r"```[^\n]*\n(.*?)```", stripped, re.DOTALL)
    if match:
        return match.group(1).strip()
    start = stripped.find("{")
    if start == -1:
        return stripped
    try:
        _obj, end = json.JSONDecoder().raw_decode(stripped[start:])
    except json.JSONDecodeError:
        return stripped
    return stripped[start : start + end]


def _known_template(query_id: object) -> bool:
    if not isinstance(query_id, str):
        return False
    try:
        get_template(query_id)
    except KeyError:
        return False
    return True


def parse_action(text: str) -> dict:
    raw = json.loads(_strip_fence(text))
    if not isinstance(raw, dict):
        raise ParseError("expected a JSON object")

    action = raw.get("action")
    if action not in _VALID_ACTIONS and _known_template(action):
        raw = dict(raw)
        raw.setdefault("id", action)
        action = "query"
    if action not in _VALID_ACTIONS:
        raise ParseError(f"unknown action: {action!r}")

    out: dict = {"action": action}

    if action == "query":
        query_id = raw.get("id")
        if not isinstance(query_id, str):
            raise ParseError("query requires string id")
        params = raw.get("params", {})
        if not isinstance(params, dict):
            raise ParseError("query requires dict params")
        out["id"] = query_id
        out["params"] = params
    elif action == "clarify":
        question = raw.get("question")
        if not isinstance(question, str) or not question:
            raise ParseError("clarify requires non-empty question")
        out["question"] = question
    elif action == "refuse":
        reason = raw.get("reason", "The catalog cannot answer that.")
        if not isinstance(reason, str):
            raise ParseError("refuse requires string reason")
        out["reason"] = reason

    return out
