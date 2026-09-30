import httpx
import pytest

from sales_agent.llm import LLMError, complete


def test_malformed_completion_stops_the_turn(monkeypatch):
    monkeypatch.setenv("LM_API_TOKEN", "test-token")

    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            return {"choices": []}

    monkeypatch.setattr(httpx, "post", lambda *args, **kwargs: Response())
    with pytest.raises(LLMError, match="The model is unreachable"):
        complete([{"role": "user", "content": "Hello"}])


def test_null_content_stops_the_turn(monkeypatch):
    monkeypatch.setenv("LM_API_TOKEN", "test-token")

    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            return {"choices": [{"message": {"content": None}}]}

    monkeypatch.setattr(httpx, "post", lambda *args, **kwargs: Response())
    with pytest.raises(LLMError, match="The model is unreachable"):
        complete([{"role": "user", "content": "Hello"}])
