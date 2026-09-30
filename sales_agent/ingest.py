from __future__ import annotations

import csv
import os
import sqlite3
from pathlib import Path

_TABLE_CSV = {
    "orders": "olist_orders_dataset.csv",
    "order_items": "olist_order_items_dataset.csv",
    "payments": "olist_order_payments_dataset.csv",
    "customers": "olist_customers_dataset.csv",
    "products": "olist_products_dataset.csv",
    "sellers": "olist_sellers_dataset.csv",
    "category_translation": "product_category_name_translation.csv",
    "reviews": "olist_order_reviews_dataset.csv",
}

_SALES_LINES_VIEW = """
CREATE VIEW sales_lines AS
SELECT
  order_items.order_id AS order_id,
  order_items.order_item_id AS order_item_id,
  orders.order_purchase_timestamp AS purchase_at,
  CAST(strftime('%Y', orders.order_purchase_timestamp) AS INTEGER) AS year,
  (CAST(strftime('%m', orders.order_purchase_timestamp) AS INTEGER) + 2) / 3 AS quarter,
  CAST(strftime('%m', orders.order_purchase_timestamp) AS INTEGER) AS month,
  orders.order_status AS order_status,
  CASE WHEN orders.order_status = 'delivered' THEN 1 ELSE 0 END AS is_delivered,
  orders.customer_id AS customer_id,
  customers.customer_state AS customer_state,
  customers.customer_city AS customer_city,
  order_items.seller_id AS seller_id,
  sellers.seller_state AS seller_state,
  order_items.product_id AS product_id,
  products.product_category_name AS category_pt,
  COALESCE(category_translation.product_category_name_english, products.product_category_name, 'unknown') AS category_en,
  CAST(order_items.price AS REAL) AS price,
  CAST(order_items.freight_value AS REAL) AS freight
FROM order_items
JOIN orders ON orders.order_id = order_items.order_id
JOIN customers ON customers.customer_id = orders.customer_id
LEFT JOIN sellers ON sellers.seller_id = order_items.seller_id
LEFT JOIN products ON products.product_id = order_items.product_id
LEFT JOIN category_translation ON category_translation.product_category_name = products.product_category_name;
"""

_ORDER_REVIEWS_VIEW = """
CREATE VIEW order_reviews AS
SELECT order_id, AVG(CAST(review_score AS REAL)) AS review_score, COUNT(*) AS review_count
FROM reviews
GROUP BY order_id;
"""


def find_csv(csv_dir: Path, name: str) -> Path:
    csv_dir = Path(csv_dir)
    direct = csv_dir / name
    if direct.is_file():
        return direct
    for child in csv_dir.iterdir():
        if child.is_dir():
            nested = child / name
            if nested.is_file():
                return nested
    raise FileNotFoundError(name)


def _normalize_cell(table: str, column: str, value: str) -> str | None:
    if value == "" and table == "products" and column == "product_category_name":
        return None
    return value


def _load_table(conn: sqlite3.Connection, table: str, csv_path: Path) -> None:
    with csv_path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.reader(handle)
        header = next(reader)
        columns_sql = ", ".join(f'"{col}" TEXT' for col in header)
        conn.execute(f'DROP TABLE IF EXISTS "{table}"')
        conn.execute(f'CREATE TABLE "{table}" ({columns_sql})')
        placeholders = ", ".join("?" for _ in header)
        insert_sql = f'INSERT INTO "{table}" ({", ".join(header)}) VALUES ({placeholders})'
        rows = [
            tuple(_normalize_cell(table, col, cell) for col, cell in zip(header, row, strict=True))
            for row in reader
        ]
        if rows:
            conn.executemany(insert_sql, rows)


def build_database(csv_dir: Path, db_path: Path) -> None:
    csv_dir = Path(csv_dir)
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    if db_path.exists():
        db_path.unlink()

    conn = sqlite3.connect(db_path)
    try:
        for table, filename in _TABLE_CSV.items():
            _load_table(conn, table, find_csv(csv_dir, filename))
        conn.executescript(_SALES_LINES_VIEW + _ORDER_REVIEWS_VIEW)
        conn.commit()
    finally:
        conn.close()


def main() -> None:
    csv_dir = Path(os.environ.get("SALES_CSV_DIR", "data"))
    db_path = Path(os.environ.get("SALES_DB", "data/olist.sqlite"))
    build_database(csv_dir, db_path)


if __name__ == "__main__":
    main()
