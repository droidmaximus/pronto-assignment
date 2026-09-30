from __future__ import annotations

import json
import sqlite3

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

_ORACLE_SQL = {
    "top_categories_by_revenue": _TOP_CATEGORIES_BY_REVENUE_SQL,
    "category_revenue_by_state": _CATEGORY_REVENUE_BY_STATE_SQL,
    "compare_category_revenue": _COMPARE_CATEGORY_REVENUE_SQL,
    "place_summary": _PLACE_SUMMARY_SQL,
    "worst_categories_by_reviews": _WORST_CATEGORIES_BY_REVIEWS_SQL,
    "top_sellers_by_revenue": _TOP_SELLERS_BY_REVENUE_SQL,
    "top_sellers_by_orders": _TOP_SELLERS_BY_ORDERS_SQL,
    "top_sellers_by_review": _TOP_SELLERS_BY_REVIEW_SQL,
}

_DEFAULTS = {
    "top_categories_by_revenue": {"limit": 5},
    "compare_category_revenue": {"limit": 5},
    "worst_categories_by_reviews": {"limit": 5, "min_reviews": 30},
    "top_sellers_by_revenue": {"limit": 5},
    "top_sellers_by_orders": {"limit": 5},
    "top_sellers_by_review": {"limit": 5, "min_reviews": 30},
}


def _bind_params(query_id: str, params: dict) -> dict[str, object]:
    if query_id not in _ORACLE_SQL:
        raise KeyError(query_id)

    bound: dict[str, object] = {}
    merged = dict(_DEFAULTS.get(query_id, {}))
    merged.update(params)

    if query_id == "worst_categories_by_reviews" and "year" not in params:
        bound["year"] = None
    elif "year" in merged:
        bound["year"] = merged["year"]

    if "delivered_only" in merged:
        bound["delivered_only"] = 1 if merged["delivered_only"] else 0

    if "limit" in merged:
        bound["limit"] = merged["limit"]

    if "min_reviews" in merged:
        bound["min_reviews"] = merged["min_reviews"]

    if query_id == "category_revenue_by_state":
        categories = merged.get("categories", [])
        bound["categories_json"] = json.dumps(categories)
        bound["year"] = merged["year"]

    if query_id == "compare_category_revenue":
        bound["year_a"] = merged["year_a"]
        bound["year_b"] = merged["year_b"]
        categories = merged.get("categories")
        if categories:
            bound["use_categories"] = 1
            bound["categories_json"] = json.dumps(categories)
        else:
            bound["use_categories"] = 0
            bound["categories_json"] = json.dumps([])
            if "limit" not in bound:
                bound["limit"] = merged.get("limit", 5)

    if query_id == "place_summary":
        bound["place_type"] = merged["place_type"]
        place = merged["place"]
        if merged["place_type"] == "state":
            place = str(place).upper()
        elif merged["place_type"] == "city":
            place = str(place).lower()
        bound["place"] = place
        bound["year"] = merged["year"]
        bound["quarter"] = merged.get("quarter")

    if query_id in (
        "top_categories_by_revenue",
        "top_sellers_by_revenue",
        "top_sellers_by_orders",
        "top_sellers_by_review",
    ):
        bound["year"] = merged["year"]

    return bound


def oracle_rows(
    connection: sqlite3.Connection,
    query_id: str,
    params: dict,
) -> list[tuple]:
    sql = _ORACLE_SQL[query_id]
    bound = _bind_params(query_id, params)
    cursor = connection.execute(sql, bound)
    return [tuple(row) for row in cursor.fetchall()]
