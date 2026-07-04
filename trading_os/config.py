"""Central configuration loading (config.yaml)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = PROJECT_ROOT / "config.yaml"


def load_config(path: Path | None = None) -> dict[str, Any]:
    with open(path or CONFIG_PATH, encoding="utf-8") as f:
        return yaml.safe_load(f)


def instrument_spec(cfg: dict, name: str) -> dict:
    try:
        return cfg["instruments"][name]
    except KeyError:
        raise KeyError(f"Instrument inconnu dans config.yaml: {name!r}")
