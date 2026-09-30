# Design summary

## Goal

A local terminal agent answers multi-turn sales questions about the Olist dataset. Every figure shown to the user is computed in Python from SQL result rows. The model (`google/gemma-4-e4b` via LM Studio’s OpenAI-compatible API) returns a single JSON action per turn; it does not write SQL and cannot invent numbers in the reply.

## Architecture

1. **Ingest** loads core CSVs into `data/olist.sqlite` and builds views `sales_lines` (per order item) and `order_reviews` (per order).
2. **Chat** is a read-eval-print loop: user message, session state, and catalog descriptions go to the model; the program validates and executes at most one catalog query per turn.
3. **SQLite** is opened read-only during chat.

Package layout: `catalog` (allowlist), `runner` (validate, bind, execute), `session` (turn history and carry-forward), `llm`, `agent` (prompt, parse, dispatch), `chat`, and `eval`.

## Allowlisted query catalog

Eight fixed SQL templates cover the analytics questions. The model chooses `id` and `params`; free-form SQL is rejected.

| Template | Purpose |
| --- | --- |
| `top_categories_by_revenue` | Top categories by revenue in a year |
| `category_revenue_by_state` | Prior categories split by customer state |
| `compare_category_revenue` | Same categories across two years |
| `place_summary` | Revenue and order count for a state or city |
| `worst_categories_by_reviews` | Lowest average review score (optional year) |
| `top_sellers_by_revenue` | Sellers by revenue |
| `top_sellers_by_orders` | Sellers by distinct orders |
| `top_sellers_by_review` | Sellers by average review score |

Parameters are values only (never SQL fragments). Defaults: `limit` 5, `min_reviews` 30. `year` and `delivered_only` have no catalog default except session carry-forward (below).

## Session carry-forward

The session stores each turn and, after a successful query, the template id, resolved parameters, and category names from the result. On the next `query`:

- If the new template declares `year` or `delivered_only` and the user omitted them, copy from the last successful turn.
- Category names are injected for `category_revenue_by_state` and `compare_category_revenue` when the prior result listed categories.
- `compare_category_revenue` uses `year_a` from session year; `year_b` must appear in the model action or the agent clarifies.
- `worst_categories_by_reviews.year` is optional (omit = all years) and is not filled from session.

A state breakdown with no prior category list triggers clarify, not a query over every category.

## Row-formatted numbers

The formatter builds the user-visible table from result rows only. Model prose may explain context but cannot add or replace numeric cells. Zero rows is a valid answer (“no rows matched”) with SQL still shown for traceability. Execution uses bound parameters; a display copy of SQL with inlined values is shown for the reader.

## Clarify and refuse

The model may return:

- **`clarify`** — ask one question; no database access. Examples: ambiguous “São Paulo” (state `SP` vs city `sao paulo`), “best sellers” without metric, “last quarter” without year/quarter (data is 2016–2018).
- **`refuse`** — explain the catalog cannot answer; no query. Examples: profit, forecasts, customer names, anything outside the eight templates.

Invalid JSON is retried once; unknown template ids, embedded SQL, or bad parameters are ignored without execution.

## Metric definitions

- **Revenue:** `SUM(price)` on `sales_lines`; freight and payment totals are not revenue.
- **Orders:** `COUNT(DISTINCT order_id)`.
- **Delivered:** `order_status = 'delivered'` when `delivered_only` is true; otherwise all statuses.
- **Time:** year and quarter from `order_purchase_timestamp`.
- **Categories:** English name from the translation table, else Portuguese, else `unknown`.
- **Reviews:** order-level average of review scores; category and seller averages use orders that include that category or seller. Rankings with `min_reviews` exclude categories/sellers below the threshold.
- **Places:** state match uppercases `place` to `customer_state`; city match lowercases to `customer_city` (no fuzzy match).

## Evaluation

About twenty scripted questions in `eval/questions.yaml` run via `python -m eval.run_eval` against the full ingested database and the live model. Questions 1–4 share one session (the brief’s four-turn chain). Grading checks action type, template id, and parameters; clarify/refuse must not run SQL. Question 14 expects clarify then a follow-up query. Numeric checks recompute aggregates with test-side SQL. Wording is not graded; `eval/results.md` is committed.

Deterministic `pytest` tests use a small fixture database: catalog validation, session rules, parsing, formatting, and per-template golden results—without LM Studio or Kaggle.

## Error handling (summary)

Missing ingest DB prompts the user to run ingest. LM errors (missing token, timeout, unreachable server) stop the turn without substituting numbers. Parameter bounds: years 2016–2018, quarters 1–4, limits 1–20.
