from sales_agent.session import Session, resolve_params


def test_copies_year_and_delivered_flag():
    session = Session(last_query_id="top_categories_by_revenue", last_params={"year": 2017, "delivered_only": False, "limit": 5}, last_categories=["watches"])
    params, question = resolve_params(session, "category_revenue_by_state", {"delivered_only": True})
    assert question is None
    assert params["year"] == 2017
    assert params["delivered_only"] is True
    assert params["categories"] == ["watches"]


def test_breakdown_without_categories_asks():
    session = Session()
    params, question = resolve_params(session, "category_revenue_by_state", {"year": 2017, "delivered_only": False})
    assert params == {}
    assert question == "Which categories should I include?"


def test_compare_fills_year_a_and_never_year_b():
    session = Session(last_params={"year": 2017, "delivered_only": True}, last_categories=["toys"])
    params, question = resolve_params(session, "compare_category_revenue", {})
    assert question == "Which year should I compare against?"
    params, question = resolve_params(session, "compare_category_revenue", {"year_b": 2018})
    assert question is None
    assert params["year_a"] == 2017
    assert params["year_b"] == 2018
    assert params["delivered_only"] is True
    assert params["categories"] == ["toys"]


def test_review_year_stays_omitted():
    session = Session(last_params={"year": 2017, "delivered_only": False})
    params, question = resolve_params(session, "worst_categories_by_reviews", {"delivered_only": True})
    assert question is None
    assert "year" not in params


def test_missing_year_asks_when_session_is_empty():
    params, question = resolve_params(Session(), "top_categories_by_revenue", {"delivered_only": False})
    assert question == "Which year? The data covers 2016 through 2018."


def test_model_categories_are_discarded():
    session = Session(last_params={"year": 2017, "delivered_only": False}, last_categories=["watches"])
    params, question = resolve_params(session, "category_revenue_by_state", {"categories": ["toys"]})
    assert question is None
    assert params["categories"] == ["watches"]
