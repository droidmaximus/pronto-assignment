from __future__ import annotations

from sales_agent.runner import QueryResult


def _is_no_rows_body(result: QueryResult) -> bool:
    if not result.rows:
        return True
    if result.query_id != "place_summary":
        return False
    if len(result.rows) != 1:
        return False
    cols = result.columns
    if "revenue" not in cols or "order_count" not in cols:
        return False
    row = result.rows[0]
    revenue = row[cols.index("revenue")]
    order_count = row[cols.index("order_count")]
    return revenue is None and order_count == 0


def _markdown_table(columns: list[str], rows: list[tuple]) -> str:
    header = "| " + " | ".join(columns) + " |"
    sep = "| " + " | ".join("---" for _ in columns) + " |"
    body_lines = [
        "| " + " | ".join(str(cell) for cell in row) + " |" for row in rows
    ]
    return "\n".join([header, sep, *body_lines])


def format_reply(result: QueryResult) -> str:
    parts: list[str] = []
    if _is_no_rows_body(result):
        parts.append("No rows matched.")
    else:
        parts.append(_markdown_table(result.columns, result.rows))

    if "revenue_a" in result.columns:
        year_a = result.params.get("year_a")
        year_b = result.params.get("year_b")
        parts.append(f"revenue_a is {year_a}. revenue_b is {year_b}.")

    parts.append(f"Query: {result.query_id}")
    parts.append(f"```sql\n{result.sql_display}\n```")
    return "\n".join(parts)
