"""
YAML model & evaluation rubric configuration loader.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml

from backend.config import settings


@lru_cache(maxsize=1)
def load_model_config(config_path: Path | None = None) -> dict:
    path = config_path or (settings.project_root / "models_config.yaml")
    if not path.is_file():
        return {}
    with path.open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}
