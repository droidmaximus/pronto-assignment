from __future__ import annotations

import os

import httpx

from sales_agent.envfile import load_local_env


class LLMError(RuntimeError):
    pass


def complete(messages: list[dict], timeout: float = 120) -> str:
    load_local_env()
    token = os.environ.get("LM_API_TOKEN")
    if not token:
        raise LLMError("LM_API_TOKEN is not set.")

    base = os.environ.get("LM_API_BASE", "http://127.0.0.1:1234/v1").rstrip("/")
    model = os.environ.get("LM_MODEL", "google/gemma-4-e4b")
    url = f"{base}/chat/completions"
    payload = {
        "model": model,
        "messages": messages,
        "temperature": 0,
    }
    headers = {"Authorization": f"Bearer {token}"}
    try:
        response = httpx.post(url, json=payload, headers=headers, timeout=timeout)
        response.raise_for_status()
        data = response.json()
        content = data["choices"][0]["message"]["content"]
    except httpx.HTTPError as exc:
        raise LLMError(f"The model is unreachable: {exc}") from exc
    except (KeyError, IndexError, TypeError, ValueError) as exc:
        raise LLMError(f"The model is unreachable: {exc}") from exc

    if not isinstance(content, str):
        raise LLMError("The model is unreachable: empty response.")
    return content
