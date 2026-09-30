# Conversational Sales Analytics Agent

## Purpose

A local terminal agent answers multi-turn questions about the public Olist Brazilian e-commerce dataset (Kaggle `olistbr/brazilian-ecommerce`, about 100,000 orders, 2016–2018). Every number the user sees is formatted in Python from the rows of one allowlisted SQL query. The model chooses which query to run. It does not write SQL, and it does not write the figures in the reply.

The runtime model is `google/gemma-4-e4b` through LM Studio’s OpenAI-compatible API. The default base URL is `http://127.0.0.1:1234/v1` (`LM_API_BASE`). The default model name is `google/gemma-4-e4b` (`LM_MODEL`). The bearer token is read from `LM_API_TOKEN` and is never stored in the repository. The model is an effective 4B model, small enough to run on a 16GB laptop. No hosted LLM API is called at runtime. There is no agent framework: each turn is one chat completion and at most one catalog query.

## Data

`python -m sales_agent.ingest` reads the Olist CSVs from `data/` (or from one subdirectory) and writes `data/olist.sqlite`. Paths can be overridden with `SALES_CSV_DIR` and `SALES_DB`. CSVs are read as UTF-8 with a byte-order mark stripped, so the category-translation header stays a real column name. An empty product category is stored as NULL.

Loaded tables: orders, order items, payments, customers, products, sellers, category translation, and reviews. Payments are loaded and unused. The geolocation file is not loaded, because customer state and city already live on the customer row.

Two views sit on those tables.

`sales_lines` is one row per order item. It carries purchase timestamp, year, quarter, month, order status, a delivered flag, customer id, customer state, customer city, seller id, seller state, product id, Portuguese category, English category, price, and freight. Quarter is `(month + 2) / 3` using integer division of the purchase timestamp. The English category is the translation, otherwise the Portuguese name, otherwise `unknown`.

`order_reviews` is one row per order: the average of that order’s review scores, and how many reviews were averaged.

The dataset and the SQLite file stay out of git. The only committed database is the small test fixture.

## Turn loop

`python -m sales_agent.chat` reads lines until a blank line. Each line goes to `respond` with one session.

The system prompt lists the eight template ids, the parameters the model is allowed to set, and the metric rules below. It does not contain expected answers. The prompt also includes a session summary of the last successful template id and its resolved parameters, when one exists.

The model must return one JSON object:

- `{"action":"query","id":"<catalog id>","params":{...}}`
- `{"action":"clarify","question":"..."}`
- `{"action":"refuse","reason":"..."}`

The parser takes a JSON object out of the reply even when a label or a markdown fence surrounds it. If `action` is itself a catalog id, that reply is read as a query for that id. Extra fields, including any SQL the model wrote, are dropped. A reply that still is not one of those three actions is sent back once, with an instruction to return a single JSON object and no SQL. A second failure tells the user: “I couldn't map that question to the catalog.”

A query runs only when the id is in the catalog and `resolve_params` can fill every required parameter. SQLite is opened read-only (`file:{path}?mode=ro`) only after that. The runner checks types and ranges, binds values, and executes the catalog SQL string. Nothing is concatenated into the SQL.

The user-visible reply is a markdown table built from the result columns and rows, then the query id, then a fenced display of the SQL with bound values inlined for reading. That display string is never what SQLite executes. For a year comparison, the reply also says which year is `revenue_a` and which is `revenue_b`. A place summary whose only row is null revenue and zero orders is shown as “No rows matched.” An empty result is the same sentence. The SQL is still shown.

The model’s own chat history does not receive that table or that SQL. It receives one line: which template ran and which parameters were used, excluding the category list. That keeps a later turn from copying the previous SQL instead of returning a new action.

## Catalog

Parameters are values, never SQL fragments. `limit` defaults to 5 and must be an integer from 1 to 20. `year`, when present, must be an integer from 2016 to 2018. `quarter`, when present, must be an integer from 1 to 4. `delivered_only` must be a boolean. `place_type` must be `state` or `city`. A boolean is not accepted where an integer is required. `min_reviews` defaults to 30.

| Id | What it returns | Model-supplied parameters |
| --- | --- | --- |
| `top_categories_by_revenue` | Categories ranked by revenue | `year`, `delivered_only`, `limit` |
| `category_revenue_by_state` | Those categories split by customer state | `year`, `delivered_only`. Categories come from the session. |
| `compare_category_revenue` | The same categories in two years | `year_a`, `year_b`, `delivered_only`, `limit`. Categories come from the session when a prior result listed them; otherwise the top `limit` categories of `year_a`. |
| `place_summary` | Revenue and distinct order count for one state or one city | `place_type`, `place`, `year`, optional `quarter`, `delivered_only`. An omitted quarter is the whole year. |
| `worst_categories_by_reviews` | Lowest average review score | Optional `year`, `delivered_only`, `limit`, `min_reviews`. Omitting `year` means 2016 through 2018. |
| `top_sellers_by_revenue` | Sellers ranked by revenue | `year`, `delivered_only`, `limit` |
| `top_sellers_by_orders` | Sellers ranked by distinct orders | `year`, `delivered_only`, `limit` |
| `top_sellers_by_review` | Sellers ranked by average review score | `year`, `delivered_only`, `limit`, `min_reviews` |

The model is told to set `delivered_only` to false unless the user asks for delivered orders, and to include that flag on every query. It is told to omit `year` on the worst-review template when the user wants every year, and not to ask which year.

State matching uppercases `place` and compares it to `customer_state`. City matching lowercases `place` and compares it to `customer_city`. There is no fuzzy match and no accent folding. `SP` is the state. `sao paulo` is the city spelling in the data.

## Session

The session keeps the chat transcript, the last successful template id, its resolved parameters, the category names from that result, and a count of queries that actually ran.

On the next query, omitted `delivered_only` is copied when the new template has that parameter and a prior result exists. Omitted `year` is copied the same way, except onto `worst_categories_by_reviews`, where an omitted year stays omitted and means all years. For `compare_category_revenue`, omitted `year_a` is filled from the session’s `year_a` or `year`. `year_b` is never invented. Category names are attached by the session for the state breakdown, and for the year comparison when the previous result had a category column. Names the model types are discarded.

If a required value is still missing, the turn asks and does not query. The questions, in check order, are:

- “Which categories should I include?”
- “Which year? The data covers 2016 through 2018.”
- “Which year should I compare against?”
- “Should I count only delivered orders, or all statuses?”
- “Do you mean the state or the city?”
- “Which state or city?”

A breakdown with no prior category list asks the first of those and does not scan every category. A clarify or a refuse does not change the last successful query.

One session covers this four-turn chain:

1. Top 5 product categories by revenue in 2017. Template `top_categories_by_revenue`, year 2017, all statuses, limit 5.
2. “Break that down by customer state.” Same year and delivered flag, categories copied from step 1, template `category_revenue_by_state`.
3. “Only count orders that were actually delivered.” Same template, `delivered_only` true.
4. “How does that compare with 2018?” Template `compare_category_revenue`, years 2017 and 2018, delivered only, same categories.

## Metrics

Revenue is `SUM(price)` on `sales_lines`. Freight is not revenue. Payment value is not revenue.

Order count is `COUNT(DISTINCT order_id)`.

Delivered means `order_status = 'delivered'`. When `delivered_only` is false, every status is included.

Year and quarter come from `order_purchase_timestamp`.

A category review score averages order-level scores for orders that contain at least one item in that category. An order in two categories counts in both. Several reviews on one order are averaged into that order’s score before the category or seller average. Seller rankings use the same order-level score across orders that include that seller. Rankings with `min_reviews` drop categories or sellers below that many reviewed orders. The default is 30.

Seller identity in an answer is `seller_id`. Customer answers use state and city only. The dataset has no customer or seller personal names.

## Clarify and refuse

The model may clarify instead of querying. The cases that must clarify are: “best sellers” with no choice among revenue, order count, and review score; “São Paulo” with no choice between state `SP` and city `sao paulo`; and “last quarter” with no year and no quarter number. The data covers 2016 through 2018, so “last quarter” cannot be resolved from today’s calendar.

Anything outside the eight templates is a refusal. That includes profit, margin, forecasts, and customer names. The default refusal text is “The catalog cannot answer that.” Clarify and refuse do not open the database.

## Failures

A missing database says “The database is missing. Run python -m sales_agent.ingest.” A SQLite error or a parameter that fails validation says “The query failed. No number is available.” No substitute number is shown.

A missing token, an HTTP failure, a timeout, a response body without a string completion, or a null completion raises one error that starts with “The model is unreachable” or states that `LM_API_TOKEN` is not set. That ends the turn. The user’s message is not stored as a successful exchange.

## Evaluation

`python -m eval.run_eval` runs twenty scripted questions in `eval/questions.yaml` against `data/olist.sqlite` and the live local model. Questions 1–4 share the chain above. Question 14 asks “Who are our best sellers in 2017?”, expects a clarification, then “by revenue” in the same session, and expects `top_sellers_by_revenue` for 2017, all statuses, limit 5. The other questions each start a fresh session: one direct question for each remaining template and filter combination, the São Paulo clarification, the last-quarter clarification, refusals for profit, a 2019 forecast, and a customer name, and a state breakdown with no prior categories, which must clarify.

A query turn passes only when that turn actually executed the expected template. A template id left over from an earlier turn does not count, including when the new turn would have reused the same id. Expected parameters are checked key by key. An extra key such as `categories` does not fail the grade. A missing `year` passes when the expectation says the year is absent. The numeric check reruns the aggregate with SQL in `eval/oracle.py`, which does not import the catalog, so a wrong join fails even if the template id was right. Clarify and refuse pass only when this turn ran no query and the action type matches. Wording is not graded. The runner writes `eval/results.md`. The committed result is a pass on every graded turn.

Deterministic tests use `tests/fixtures/olist_fixture.sqlite`, about twenty hand-built orders, and expected tables in `tests/expected/`. They cover the catalog, the runner, carry-forward, formatting, parsing, the agent loop, ingest including a byte-order mark, chat, the grader, and a malformed model response. They do not call LM Studio or Kaggle. `python -m pytest` runs them.

## Out of scope

Web UI, authentication, deployment, hosted LLM APIs, free-form SQL, geolocation, payment mix, and any dataset other than these Olist files.
