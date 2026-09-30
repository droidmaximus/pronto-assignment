from __future__ import annotations

from dataclasses import dataclass, field

from sales_agent.catalog import MISSING, get_template


@dataclass
class Session:
    turns: list[dict] = field(default_factory=list)
    last_query_id: str | None = None
    last_params: dict = field(default_factory=dict)
    last_categories: list[str] = field(default_factory=list)
    queries_run: int = 0


def resolve_params(
    session: Session,
    query_id: str,
    model_params: dict,
) -> tuple[dict, str | None]:
    template = get_template(query_id)
    known = {p.name for p in template.params}
    params: dict = {}
    for key, value in model_params.items():
        if key not in known:
            continue
        param = next(p for p in template.params if p.name == key)
        if param.kind == "list" and not param.model_supplied:
            continue
        params[key] = value

    param_by_name = {p.name: p for p in template.params}

    if "delivered_only" in param_by_name and "delivered_only" not in params:
        if "delivered_only" in session.last_params:
            params["delivered_only"] = session.last_params["delivered_only"]

    if query_id != "worst_categories_by_reviews":
        if "year" in param_by_name and "year" not in params:
            if "year" in session.last_params:
                params["year"] = session.last_params["year"]

    if query_id == "compare_category_revenue":
        if "year_a" not in params:
            if "year_a" in session.last_params:
                params["year_a"] = session.last_params["year_a"]
            elif "year" in session.last_params:
                params["year_a"] = session.last_params["year"]

    if query_id == "category_revenue_by_state":
        if "categories" not in params:
            params["categories"] = list(session.last_categories)
    elif query_id == "compare_category_revenue" and session.last_categories:
        if "categories" not in params:
            params["categories"] = list(session.last_categories)

    if query_id == "category_revenue_by_state":
        categories = params.get("categories", [])
        if not categories:
            return {}, "Which categories should I include?"

    if "year" in param_by_name:
        p = param_by_name["year"]
        if p.required and "year" not in params:
            return {}, "Which year? The data covers 2016 through 2018."

    if "year_a" in param_by_name:
        p = param_by_name["year_a"]
        if p.required and "year_a" not in params:
            return {}, "Which year? The data covers 2016 through 2018."

    if "year_b" in param_by_name:
        p = param_by_name["year_b"]
        if p.required and "year_b" not in params:
            return {}, "Which year should I compare against?"

    if "delivered_only" in param_by_name:
        p = param_by_name["delivered_only"]
        if p.required and "delivered_only" not in params:
            return {}, "Should I count only delivered orders, or all statuses?"

    if "place_type" in param_by_name:
        p = param_by_name["place_type"]
        if p.required and "place_type" not in params:
            return {}, "Do you mean the state or the city?"

    if "place" in param_by_name:
        p = param_by_name["place"]
        if p.required and "place" not in params:
            return {}, "Which state or city?"

    for p in template.params:
        if not p.required or p.name in params:
            continue
        if p.default is not MISSING:
            params[p.name] = p.default

    return params, None
