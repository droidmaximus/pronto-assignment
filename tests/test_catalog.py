from sales_agent.catalog import get_template, list_templates, prompt_lines

EXPECTED_IDS = [
    "top_categories_by_revenue",
    "category_revenue_by_state",
    "compare_category_revenue",
    "place_summary",
    "worst_categories_by_reviews",
    "top_sellers_by_revenue",
    "top_sellers_by_orders",
    "top_sellers_by_review",
]


def test_ids_are_unique_and_complete():
    ids = [template.id for template in list_templates()]
    assert ids == EXPECTED_IDS
    assert len(ids) == len(set(ids))


def test_sql_uses_bound_parameters_only():
    for template in list_templates():
        assert "{" not in template.sql
        assert "%s" not in template.sql
        assert "payments" not in template.sql
        assert "geolocation" not in template.sql


def test_limit_params_have_bounds():
    for template in list_templates():
        for param in template.params:
            if param.name != "limit":
                continue
            assert param.minimum == 1
            assert param.maximum == 20


def test_limit_and_min_reviews_defaults():
    top = get_template("top_categories_by_revenue")
    limit = next(param for param in top.params if param.name == "limit")
    assert limit.default == 5
    assert limit.minimum == 1
    assert limit.maximum == 20
    reviews = get_template("worst_categories_by_reviews")
    minimum = next(param for param in reviews.params if param.name == "min_reviews")
    assert minimum.default == 30
    year = next(param for param in reviews.params if param.name == "year")
    assert year.required is False


def test_prompt_lists_ids_and_hides_session_categories():
    text = prompt_lines()
    for query_id in EXPECTED_IDS:
        assert query_id in text
    breakdown = get_template("category_revenue_by_state")
    categories = next(param for param in breakdown.params if param.name == "categories")
    assert categories.model_supplied is False
    assert "params: categories" not in text
