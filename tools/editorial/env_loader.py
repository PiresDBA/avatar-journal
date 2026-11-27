"""Safe .env loader without exposing secrets to logs or stdout."""

from __future__ import annotations

import os
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
DEFAULT_ENV_PATH = ROOT_DIR / ".env"


def load_project_env(env_path: Path | None = None, override: bool = False) -> dict[str, bool]:
    """Load key=value pairs from .env into os.environ.

    Returns a dictionary mapping variable names to presence booleans (never values).
    """
    target = env_path or DEFAULT_ENV_PATH
    loaded: dict[str, bool] = {}
    if not target.exists():
        return loaded

    for raw_line in target.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].strip()
        if "=" not in line:
            continue
        key, val = line.split("=", 1)
        key = key.strip()
        val = val.strip().strip('"').strip("'")
        if not key:
            continue
        if override or not os.environ.get(key):
            if val:
                os.environ[key] = val
        loaded[key] = bool(os.environ.get(key))
    return loaded


def token_status(var_name: str = "GITHUB_TOKEN", env_path: Path | None = None) -> dict[str, object]:
    """Return non-secret availability metadata for a token."""
    load_project_env(env_path=env_path, override=False)
    value = os.environ.get(var_name, "")
    return {
        "var": var_name,
        "configured": bool(value.strip()),
        "env_file_exists": (env_path or DEFAULT_ENV_PATH).exists(),
    }
