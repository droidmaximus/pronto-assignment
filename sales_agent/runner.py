from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass

from sales_agent.catalog import MISSING, get_template


class ParamError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class QueryResult:
    query_id: str
    columns: list[str]
    rows: list[tuple]
    sql_display: str
    params: dict


_DISPLAY_PARAM_ORDER = (
    "categories_json",
    "use_categories",
    "delivered_only",
    "min_reviews",
    "place_type",
    "year_a",
    "year_b",
    "quarter",
    "limit",
    "year",
    "place",
)


def _format_display_value(value: object) -> str:
    if value is None:
        return "NULL"
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, str):
        escaped = value.replace("'", "''")
        return f"'{escaped}'"
    return repr(value)


def render_sql(sql: str, bound: dict[str, object]) -> str:
    display = sql
    for name in _DISPLAY_PARAM_ORDER:
        if name not in bound:
            continue
        token = f":{name}"
        display = display.replace(token, _format_display_value(bound[name]))
    return display


def _validate_and_bind(query_id: str, params: dict) -> tuple[dict, dict]:
    try:
        template = get_template(query_id)
    except KeyError:
        raise ParamError(f"unknown query: {query_id}") from None

    bound: dict[str, object] = {}
    resolved: dict[str, object] = {}

    for param in template.params:
        if param.name in params:
            raw = params[param.name]
        elif param.required:
            raise ParamError(f"missing required param: {param.name}")
        elif param.default is not MISSING:
            raw = param.default
        else:
            raw = None

        if param.kind == "int":
            if isinstance(raw, bool):
                raise ParamError(f"invalid type for {param.name}")
            if raw is None:
                if param.required:
                    raise ParamError(f"missing required param: {param.name}")
                bound[param.name] = None
                resolved[param.name] = None
                continue
            if not isinstance(raw, int):
                raise ParamError(f"invalid type for {param.name}")
            if param.minimum is not None and raw < param.minimum:
                raise ParamError(f"{param.name} out of range")
            if param.maximum is not None and raw > param.maximum:
                raise ParamError(f"{param.name} out of range")
            bound[param.name] = raw
            resolved[param.name] = raw
        elif param.kind == "bool":
            if not isinstance(raw, bool):
                raise ParamError(f"invalid type for {param.name}")
            bound[param.name] = 1 if raw else 0
            resolved[param.name] = raw
        elif param.kind == "str":
            if not isinstance(raw, str):
                raise ParamError(f"invalid type for {param.name}")
            resolved[param.name] = raw
            bound[param.name] = raw
        elif param.kind == "enum":
            if not isinstance(raw, str):
                raise ParamError(f"invalid type for {param.name}")
            if raw not in param.choices:
                raise ParamError(f"invalid choice for {param.name}")
            bound[param.name] = raw
            resolved[param.name] = raw
        elif param.kind == "list":
            if param.name not in params:
                if param.required:
                    raise ParamError(f"missing required param: {param.name}")
                if query_id == "compare_category_revenue":
                    bound["use_categories"] = 0
                    bound["categories_json"] = json.dumps([])
                continue
            raw_list = params[param.name]
            if not isinstance(raw_list, list):
                raise ParamError(f"invalid type for {param.name}")
            if not raw_list:
                raise ParamError(f"empty {param.name}")
            if not all(isinstance(item, str) for item in raw_list):
                raise ParamError(f"invalid type for {param.name}")
            resolved[param.name] = raw_list
            bound["categories_json"] = json.dumps(raw_list)
            if query_id == "compare_category_revenue":
                bound["use_categories"] = 1
        else:
            raise ParamError(f"unsupported param kind: {param.kind}")

    if "place_type" in bound and "place" in bound:
        place_type = bound["place_type"]
        place = bound["place"]
        if place_type == "state":
            place = str(place).upper()
        elif place_type == "city":
            place = str(place).lower()
        bound["place"] = place
        resolved["place"] = place

    if query_id == "compare_category_revenue" and "use_categories" not in bound:
        bound["use_categories"] = 0
        bound["categories_json"] = json.dumps([])

    return bound, resolved


def run_query(
    connection: sqlite3.Connection,
    query_id: str,
    params: dict,
) -> QueryResult:
    try:
        template = get_template(query_id)
    except KeyError:
        raise ParamError(f"unknown query: {query_id}") from None
    bound, resolved = _validate_and_bind(query_id, params)
    sql_display = render_sql(template.sql, bound)
    cursor = connection.execute(template.sql, bound)
    columns = [desc[0] for desc in cursor.description]
    rows = [tuple(row) for row in cursor.fetchall()]
    return QueryResult(
        query_id=query_id,
        columns=columns,
        rows=rows,
        sql_display=sql_display,
        params=resolved,
    )
