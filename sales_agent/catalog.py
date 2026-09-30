from __future__ import annotations

from dataclasses import dataclass

MISSING = object()


@dataclass(frozen=True, slots=True)
class Param:
    name: str
    kind: str
    required: bool
    default: object
    minimum: int | None
    maximum: int | None
    choices: tuple[str, ...]
    model_supplied: bool


@dataclass(frozen=True, slots=True)
class Template:
    id: str
    description: str
    params: tuple[Param, ...]
    sql: str


def _int(
    name: str,
    *,
    required: bool,
    default: object = MISSING,
    minimum: int | None = None,
    maximum: int | None = None,
    model_supplied: bool = True,
) -> Param:
    return Param(
        name=name,
        kind="int",
        required=required,
        default=default,
        minimum=minimum,
        maximum=maximum,
        choices=(),
        model_supplied=model_supplied,
    )


def _bool(name: str, *, required: bool, model_supplied: bool = True) -> Param:
    return Param(
        name=name,
        kind="bool",
        required=required,
        default=MISSING,
        minimum=None,
        maximum=None,
        choices=(),
        model_supplied=model_supplied,
    )


def _str(name: str, *, required: bool, model_supplied: bool = True) -> Param:
    return Param(
        name=name,
        kind="str",
        required=required,
        default=MISSING,
        minimum=None,
        maximum=None,
        choices=(),
        model_supplied=model_supplied,
    )


def _enum(name: str, *, required: bool, choices: tuple[str, ...]) -> Param:
    return Param(
        name=name,
        kind="enum",
        required=required,
        default=MISSING,
        minimum=None,
        maximum=None,
        choices=choices,
        model_supplied=True,
    )


def _list(
    name: str,
    *,
    required: bool,
    model_supplied: bool,
) -> Param:
    return Param(
        name=name,
        kind="list",
        required=required,
        default=MISSING,
        minimum=None,
        maximum=None,
        choices=(),
        model_supplied=model_supplied,
    )


_TOP_CATEGORIES_BY_REVENUE_SQL = """\
SELECT category_en AS category, ROUND(SUM(price), 2) AS revenue
FROM sales_lines
WHERE year = :year
  AND (:delivered_only = 0 OR is_delivered = 1)
GROUP BY category_en
ORDER BY revenue DESC, category ASC
LIMIT :limit"""

_CATEGORY_REVENUE_BY_STATE_SQL = """\
SELECT category_en AS category, customer_state AS state, ROUND(SUM(price), 2) AS revenue
FROM sales_lines
WHERE year = :year
  AND (:delivered_only = 0 OR is_delivered = 1)
  AND category_en IN (SELECT value FROM json_each(:categories_json))
GROUP BY category_en, customer_state
ORDER BY category ASC, revenue DESC, state ASC"""

_COMPARE_CATEGORY_REVENUE_SQL = """\
WITH base AS (
  SELECT category_en AS category, SUM(price) AS revenue_a
  FROM sales_lines
  WHERE year = :year_a
    AND (:delivered_only = 0 OR is_delivered = 1)
    AND (
      :use_categories = 0
      OR category_en IN (SELECT value FROM json_each(:categories_json))
    )
  GROUP BY category_en
),
picked AS (
  SELECT category, revenue_a
  FROM base
  ORDER BY revenue_a DESC, category ASC
  LIMIT CASE WHEN :use_categories = 1 THEN 100 ELSE :limit END
)
SELECT
  picked.category AS category,
  ROUND(picked.revenue_a, 2) AS revenue_a,
  ROUND(COALESCE((
    SELECT SUM(sales_lines.price)
    FROM sales_lines
    WHERE sales_lines.category_en = picked.category
      AND sales_lines.year = :year_b
      AND (:delivered_only = 0 OR sales_lines.is_delivered = 1)
  ), 0), 2) AS revenue_b
FROM picked
ORDER BY picked.revenue_a DESC, picked.category ASC"""

_PLACE_SUMMARY_SQL = """\
SELECT ROUND(SUM(price), 2) AS revenue, COUNT(DISTINCT order_id) AS order_count
FROM sales_lines
WHERE year = :year
  AND (:quarter IS NULL OR quarter = :quarter)
  AND (:delivered_only = 0 OR is_delivered = 1)
  AND (
    (:place_type = 'state' AND customer_state = :place)
    OR (:place_type = 'city' AND customer_city = :place)
  )"""

_WORST_CATEGORIES_BY_REVIEWS_SQL = """\
WITH order_categories AS (
  SELECT DISTINCT order_id, category_en, year, is_delivered
  FROM sales_lines
),
scored AS (
  SELECT
    order_categories.category_en AS category,
    AVG(order_reviews.review_score) AS avg_review,
    COUNT(DISTINCT order_categories.order_id) AS reviewed_orders
  FROM order_categories
  JOIN order_reviews ON order_reviews.order_id = order_categories.order_id
  WHERE (:year IS NULL OR order_categories.year = :year)
    AND (:delivered_only = 0 OR order_categories.is_delivered = 1)
  GROUP BY order_categories.category_en
)
SELECT category, ROUND(avg_review, 2) AS avg_review, reviewed_orders
FROM scored
WHERE reviewed_orders >= :min_reviews
ORDER BY avg_review ASC, category ASC
LIMIT :limit"""

_TOP_SELLERS_BY_REVENUE_SQL = """\
SELECT seller_id, ROUND(SUM(price), 2) AS revenue
FROM sales_lines
WHERE year = :year
  AND (:delivered_only = 0 OR is_delivered = 1)
GROUP BY seller_id
ORDER BY revenue DESC, seller_id ASC
LIMIT :limit"""

_TOP_SELLERS_BY_ORDERS_SQL = """\
SELECT seller_id, COUNT(DISTINCT order_id) AS order_count
FROM sales_lines
WHERE year = :year
  AND (:delivered_only = 0 OR is_delivered = 1)
GROUP BY seller_id
ORDER BY order_count DESC, seller_id ASC
LIMIT :limit"""

_TOP_SELLERS_BY_REVIEW_SQL = """\
WITH seller_orders AS (
  SELECT DISTINCT seller_id, order_id, year, is_delivered
  FROM sales_lines
),
scored AS (
  SELECT
    seller_orders.seller_id AS seller_id,
    AVG(order_reviews.review_score) AS avg_review,
    COUNT(DISTINCT seller_orders.order_id) AS reviewed_orders
  FROM seller_orders
  JOIN order_reviews ON order_reviews.order_id = seller_orders.order_id
  WHERE seller_orders.year = :year
    AND (:delivered_only = 0 OR seller_orders.is_delivered = 1)
  GROUP BY seller_orders.seller_id
)
SELECT seller_id, ROUND(avg_review, 2) AS avg_review, reviewed_orders
FROM scored
WHERE reviewed_orders >= :min_reviews
ORDER BY avg_review DESC, seller_id ASC
LIMIT :limit"""

TEMPLATES: dict[str, Template] = {
    "top_categories_by_revenue": Template(
        id="top_categories_by_revenue",
        description="Top categories by revenue in a year",
        params=(
            _int("year", required=True, minimum=2016, maximum=2018),
            _bool("delivered_only", required=True),
            _int("limit", required=False, default=5, minimum=1, maximum=20),
        ),
        sql=_TOP_CATEGORIES_BY_REVENUE_SQL,
    ),
    "category_revenue_by_state": Template(
        id="category_revenue_by_state",
        description="Those categories split by customer state",
        params=(
            _int("year", required=True, minimum=2016, maximum=2018),
            _bool("delivered_only", required=True),
            _list("categories", required=True, model_supplied=False),
        ),
        sql=_CATEGORY_REVENUE_BY_STATE_SQL,
    ),
    "compare_category_revenue": Template(
        id="compare_category_revenue",
        description="The same categories in two years",
        params=(
            _int("year_a", required=True, minimum=2016, maximum=2018),
            _int("year_b", required=True, minimum=2016, maximum=2018),
            _bool("delivered_only", required=True),
            _int("limit", required=False, default=5),
            _list("categories", required=False, model_supplied=False),
        ),
        sql=_COMPARE_CATEGORY_REVENUE_SQL,
    ),
    "place_summary": Template(
        id="place_summary",
        description="Revenue and distinct order count for a state or city",
        params=(
            _enum("place_type", required=True, choices=("state", "city")),
            _str("place", required=True),
            _int("year", required=True, minimum=2016, maximum=2018),
            _int("quarter", required=False, default=MISSING, minimum=1, maximum=4),
            _bool("delivered_only", required=True),
        ),
        sql=_PLACE_SUMMARY_SQL,
    ),
    "worst_categories_by_reviews": Template(
        id="worst_categories_by_reviews",
        description="Lowest average review score",
        params=(
            _int("year", required=False, minimum=2016, maximum=2018),
            _bool("delivered_only", required=True),
            _int("limit", required=False, default=5),
            _int("min_reviews", required=False, default=30, minimum=1, maximum=100000),
        ),
        sql=_WORST_CATEGORIES_BY_REVIEWS_SQL,
    ),
    "top_sellers_by_revenue": Template(
        id="top_sellers_by_revenue",
        description="Sellers ranked by revenue",
        params=(
            _int("year", required=True, minimum=2016, maximum=2018),
            _bool("delivered_only", required=True),
            _int("limit", required=False, default=5),
        ),
        sql=_TOP_SELLERS_BY_REVENUE_SQL,
    ),
    "top_sellers_by_orders": Template(
        id="top_sellers_by_orders",
        description="Sellers ranked by distinct orders",
        params=(
            _int("year", required=True, minimum=2016, maximum=2018),
            _bool("delivered_only", required=True),
            _int("limit", required=False, default=5),
        ),
        sql=_TOP_SELLERS_BY_ORDERS_SQL,
    ),
    "top_sellers_by_review": Template(
        id="top_sellers_by_review",
        description="Sellers ranked by average review score",
        params=(
            _int("year", required=True, minimum=2016, maximum=2018),
            _bool("delivered_only", required=True),
            _int("limit", required=False, default=5),
            _int("min_reviews", required=False, default=30),
        ),
        sql=_TOP_SELLERS_BY_REVIEW_SQL,
    ),
}


def list_templates() -> list[Template]:
    return [TEMPLATES[key] for key in (
        "top_categories_by_revenue",
        "category_revenue_by_state",
        "compare_category_revenue",
        "place_summary",
        "worst_categories_by_reviews",
        "top_sellers_by_revenue",
        "top_sellers_by_orders",
        "top_sellers_by_review",
    )]


def get_template(query_id: str) -> Template:
    try:
        return TEMPLATES[query_id]
    except KeyError:
        raise KeyError(query_id) from None


def _format_param_default(param: Param) -> str:
    if param.default is not MISSING:
        return f"{param.name}={param.default!r}"
    return param.name


def prompt_lines() -> str:
    blocks: list[str] = []
    for template in list_templates():
        model_params = [
            _format_param_default(p)
            for p in template.params
            if p.model_supplied
        ]
        param_line = f"params: {', '.join(model_params)}" if model_params else "params: (none)"
        blocks.append(
            f"{template.id}\n{template.description}\n{param_line}"
        )
    return "\n\n".join(blocks)
