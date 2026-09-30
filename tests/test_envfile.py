import os

from sales_agent.envfile import load_local_env


def test_loads_token_without_overriding_existing(tmp_path, monkeypatch):
    env_path = tmp_path / ".env"
    env_path.write_text(
        "LM_API_TOKEN=from-file\n"
        "LM_MODEL=from-file\n"
        "export LM_API_BASE=http://127.0.0.1:9/v1\n"
        "# comment\n"
    )
    monkeypatch.setenv("LM_MODEL", "already-set")
    monkeypatch.delenv("LM_API_TOKEN", raising=False)
    monkeypatch.delenv("LM_API_BASE", raising=False)

    load_local_env(env_path)

    assert os.environ["LM_API_TOKEN"] == "from-file"
    assert os.environ["LM_MODEL"] == "already-set"
    assert os.environ["LM_API_BASE"] == "http://127.0.0.1:9/v1"
