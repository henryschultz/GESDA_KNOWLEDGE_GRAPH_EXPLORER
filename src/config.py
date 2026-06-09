"""config.py — Minimal config loader for the KG Explorer UI."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_DEFAULT_CONFIG = _PROJECT_ROOT / "config" / "config.yaml"


def load_config(config_path: str | Path | None = None) -> dict[str, Any]:
    path = Path(config_path) if config_path else _DEFAULT_CONFIG
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")

    with open(path, "r", encoding="utf-8") as f:
        cfg: dict[str, Any] = yaml.safe_load(f)

    qdrant_api_key = os.environ.get("QDRANT_API_KEY")
    if qdrant_api_key:
        cfg["qdrant"]["api_key"] = qdrant_api_key

    qdrant_url = os.environ.get("QDRANT_URL")
    if qdrant_url:
        cfg["qdrant"]["url"] = qdrant_url

    return cfg
