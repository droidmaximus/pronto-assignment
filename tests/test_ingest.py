from __future__ import annotations

import csv
import sqlite3
from pathlib import Path

import pytest

from sales_agent.ingest import _load_table, build_database
from sales_agent.runner import run_query

ORDERS_HEADER = (
    "order_id,customer_id,order_status,order_purchase_timestamp,order_approved_at,"
    "order_delivered_carrier_date,order_delivered_customer_date,order_estimated_delivery_date"
)
ITEMS_HEADER = (
    "order_id,order_item_id,product_id,seller_id,shipping_limit_date,price,freight_value"
)
PAYMENTS_HEADER = (
    "order_id,payment_sequential,payment_type,payment_installments,payment_value"
)
CUSTOMERS_HEADER = (
    "customer_id,customer_unique_id,customer_zip_code_prefix,customer_city,customer_state"
)
PRODUCTS_HEADER = (
    "product_id,product_category_name,product_name_lenght,product_description_lenght,"
    "product_photos_qty,product_weight_g,product_length_cm,product_height_cm,product_width_cm"
)
SELLERS_HEADER = "seller_id,seller_zip_code_prefix,seller_city,seller_state"
TRANSLATION_HEADER = "product_category_name,product_category_name_english"
REVIEWS_HEADER = (
    "review_id,order_id,review_score,review_comment_title,review_comment_message,"
    "review_creation_date,review_answer_timestamp"
)

CSV_FILES = {
    "olist_orders_dataset.csv": ORDERS_HEADER,
    "olist_order_items_dataset.csv": ITEMS_HEADER,
    "olist_order_payments_dataset.csv": PAYMENTS_HEADER,
    "olist_customers_dataset.csv": CUSTOMERS_HEADER,
    "olist_products_dataset.csv": PRODUCTS_HEADER,
    "olist_sellers_dataset.csv": SELLERS_HEADER,
    "product_category_name_translation.csv": TRANSLATION_HEADER,
    "olist_order_reviews_dataset.csv": REVIEWS_HEADER,
}


def _write_csv(path: Path, header: str, rows: list[list[str]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(header.split(","))
        writer.writerows(rows)


def _blank_order_tail() -> list[str]:
    return ["", "", "", ""]


@pytest.fixture
def csv_dir(tmp_path: Path) -> Path:
    root = tmp_path / "csv"
    root.mkdir()
    for name, header in CSV_FILES.items():
        _write_csv(root / name, header, [])

    _write_csv(
        root / "olist_orders_dataset.csv",
        ORDERS_HEADER,
        [
            ["o1", "c1", "delivered", "2017-02-10 00:00:00", *_blank_order_tail()],
            ["o2", "c2", "shipped", "2017-05-01 00:00:00", *_blank_order_tail()],
        ],
    )
    _write_csv(
        root / "olist_order_items_dataset.csv",
        ITEMS_HEADER,
        [
            ["o1", "1", "p1", "s1", "2017-02-11 00:00:00", "100.00", "10.00"],
            ["o2", "1", "p2", "s1", "2017-05-02 00:00:00", "25.00", "5.00"],
            ["o2", "2", "p3", "s1", "2017-05-02 00:00:00", "15.00", "3.00"],
        ],
    )
    _write_csv(
        root / "olist_order_payments_dataset.csv",
        PAYMENTS_HEADER,
        [
            ["o1", "1", "credit_card", "1", "110.00"],
            ["o2", "1", "boleto", "1", "48.00"],
        ],
    )
    _write_csv(
        root / "olist_customers_dataset.csv",
        CUSTOMERS_HEADER,
        [
            ["c1", "cu1", "01000", "sao paulo", "SP"],
            ["c2", "cu2", "20000", "rio de janeiro", "RJ"],
        ],
    )
    _write_csv(
        root / "olist_products_dataset.csv",
        PRODUCTS_HEADER,
        [
            ["p1", "beleza_saude", "10", "100", "1", "100", "10", "10", "10"],
            ["p2", "informatica_pt", "10", "100", "1", "100", "10", "10", "10"],
            ["p3", "", "10", "100", "1", "100", "10", "10", "10"],
        ],
    )
    _write_csv(
        root / "olist_sellers_dataset.csv",
        SELLERS_HEADER,
        [["s1", "01000", "sao paulo", "SP"]],
    )
    _write_csv(
        root / "product_category_name_translation.csv",
        TRANSLATION_HEADER,
        [["beleza_saude", "health_beauty"]],
    )
    _write_csv(
        root / "olist_order_reviews_dataset.csv",
        REVIEWS_HEADER,
        [
            ["r1", "o1", "3", "", "", "2017-02-11 00:00:00", "2017-02-12 00:00:00"],
            ["r2", "o1", "5", "", "", "2017-02-11 00:00:00", "2017-02-12 00:00:00"],
        ],
    )
    (root / "olist_geolocation_dataset.csv").write_text("geolocation_zip_code_prefix\n00000\n")
    return root


def test_load_table_strips_utf8_bom_from_header(tmp_path: Path) -> None:
    csv_path = tmp_path / "product_category_name_translation.csv"
    csv_path.write_bytes(
        b"\xef\xbb\xbfproduct_category_name,product_category_name_english\n"
        b"beleza_saude,health_beauty\n"
    )
    conn = sqlite3.connect(":memory:")
    try:
        _load_table(conn, "category_translation", csv_path)
        columns = [
            row[1] for row in conn.execute("PRAGMA table_info(category_translation)")
        ]
        assert columns == ["product_category_name", "product_category_name_english"]
        assert all("\ufeff" not in col for col in columns)
    finally:
        conn.close()


def test_build_database_views_and_runner(csv_dir: Path, tmp_path: Path) -> None:
    db_path = tmp_path / "test.sqlite"
    build_database(csv_dir, db_path)

    conn = sqlite3.connect(db_path)
    try:
        tables = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type IN ('table', 'view')"
            )
        }
        assert "payments" in tables
        assert "sales_lines" in tables
        assert "order_reviews" in tables
        assert not any("geolocation" in name for name in tables)

        translated = conn.execute(
            """
            SELECT category_pt, category_en, is_delivered, year, quarter
            FROM sales_lines
            WHERE product_id = 'p1'
            """
        ).fetchone()
        assert translated == ("beleza_saude", "health_beauty", 1, 2017, 1)

        portuguese_only = conn.execute(
            "SELECT category_en FROM sales_lines WHERE product_id = 'p2'"
        ).fetchone()
        assert portuguese_only == ("informatica_pt",)

        unknown_category = conn.execute(
            "SELECT category_en FROM sales_lines WHERE product_id = 'p3'"
        ).fetchone()
        assert unknown_category == ("unknown",)

        delivery_flags = conn.execute(
            "SELECT order_status, is_delivered FROM sales_lines ORDER BY order_id"
        ).fetchall()
        assert delivery_flags == [("delivered", 1), ("shipped", 0), ("shipped", 0)]

        review_row = conn.execute(
            "SELECT review_score, review_count FROM order_reviews WHERE order_id = 'o1'"
        ).fetchone()
        assert review_row == (4.0, 2)

        result = run_query(
            conn,
            "top_categories_by_revenue",
            {"year": 2017, "delivered_only": True, "limit": 5},
        )
        assert result.rows[0][0] == "health_beauty"
    finally:
        conn.close()
