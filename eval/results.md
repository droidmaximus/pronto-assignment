| id | result | expected | actual | note |
| --- | --- | --- | --- | --- |
| 1 | pass | query:top_categories_by_revenue | query:top_categories_by_revenue | ok |
| 2 | fail | query:category_revenue_by_state | clarify | unexpected template id |
| 3 | fail | query:category_revenue_by_state | query:top_categories_by_revenue | unexpected template id |
| 4 | fail | query:compare_category_revenue | clarify | unexpected template id |
| 5 | pass | query:top_categories_by_revenue | query:top_categories_by_revenue | ok |
| 6 | pass | query:top_categories_by_revenue | query:top_categories_by_revenue | ok |
| 7 | fail | query:place_summary | query:? | unexpected template id |
| 8 | pass | query:place_summary | query:place_summary | ok |
| 9 | fail | query:worst_categories_by_reviews | clarify | unexpected template id |
| 10 | pass | query:worst_categories_by_reviews | query:worst_categories_by_reviews | ok |
| 11 | pass | query:top_sellers_by_revenue | query:top_sellers_by_revenue | ok |
| 12 | pass | query:top_sellers_by_orders | query:top_sellers_by_orders | ok |
| 13 | pass | query:top_sellers_by_review | query:top_sellers_by_review | ok |
| 14-1 | pass | clarify | clarify | ok |
| 14-2 | pass | query:top_sellers_by_revenue | query:top_sellers_by_revenue | ok |
| 15 | pass | clarify | clarify | ok |
| 16 | pass | clarify | clarify | ok |
| 17 | pass | refuse | refuse | ok |
| 18 | pass | refuse | refuse | ok |
| 19 | pass | refuse | refuse | ok |
| 20 | pass | clarify | clarify | ok |
