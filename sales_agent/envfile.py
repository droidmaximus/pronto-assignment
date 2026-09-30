from __future__ import annotations

import os
from pathlib import Path

_DEFAULT_PATH = Path(__file__).resolve().parent.parent / ".env"


def load_local_env(path: Path | None = None) -> None:
    """Load KEY=VALUE lines from .env. Existing environment variables win."""
    env_path = _DEFAULT_PATH if path is None else path
    if not env_path.is_file():
        return
    for raw in env_path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export ") :].strip()
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        if key and key not in os.environ:
            os.environ[key] = value
