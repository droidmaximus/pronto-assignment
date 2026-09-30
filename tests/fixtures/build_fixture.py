from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path

from tests.fixtures.rows import ROWS


def _quarter(month: int) -> int:
    return (month - 1) // 3 + 1


def build_fixture(path: str | Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        path.unlink()

    conn = sqlite3.connect(path)
    try:
        conn.executescript(
            """
            CREATE TABLE sales_lines (
                order_id TEXT NOT NULL,
                order_item_id INTEGER NOT NULL,
                purchase_at TEXT NOT NULL,
                year INTEGER NOT NULL,
                quarter INTEGER NOT NULL,
                month INTEGER NOT NULL,
                order_status TEXT NOT NULL,
                is_delivered INTEGER NOT NULL,
                customer_id TEXT NOT NULL,
                customer_state TEXT NOT NULL,
                customer_city TEXT NOT NULL,
                seller_id TEXT NOT NULL,
                seller_state TEXT NOT NULL,
                product_id TEXT NOT NULL,
                category_pt TEXT NOT NULL,
                category_en TEXT NOT NULL,
                price REAL NOT NULL,
                freight REAL NOT NULL
            );
            CREATE TABLE order_reviews (
                order_id TEXT NOT NULL PRIMARY KEY,
                review_score REAL NOT NULL,
                review_count INTEGER NOT NULL
            );
            """
        )

        sales_rows: list[tuple] = []
        review_by_order: dict[str, list[int]] = {}
        for row in ROWS:
            purchased = datetime.strptime(row["purchased"], "%Y-%m-%d %H:%M:%S")
            if row["review_scores"] and row["order_id"] not in review_by_order:
                review_by_order[row["order_id"]] = list(row["review_scores"])

            sales_rows.append(
                (
                    row["order_id"],
                    row["item_id"],
                    row["purchased"],
                    purchased.year,
                    _quarter(purchased.month),
                    purchased.month,
                    row["status"],
                    1 if row["status"] == "delivered" else 0,
                    row["order_id"],
                    row["state"],
                    row["city"],
                    row["seller_id"],
                    "",
                    row["order_id"],
                    row["category"],
                    row["category"],
                    float(row["price"]),
                    0.0,
                )
            )

        conn.executemany(
            """
            INSERT INTO sales_lines (
                order_id, order_item_id, purchase_at, year, quarter, month,
                order_status, is_delivered, customer_id, customer_state,
                customer_city, seller_id, seller_state, product_id,
                category_pt, category_en, price, freight
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            sales_rows,
        )

        review_rows = []
        for order_id, scores in review_by_order.items():
            review_rows.append(
                (order_id, sum(scores) / len(scores), len(scores))
            )
        conn.executemany(
            "INSERT INTO order_reviews (order_id, review_score, review_count) VALUES (?, ?, ?)",
            review_rows,
        )
        conn.commit()
    finally:
        conn.close()
