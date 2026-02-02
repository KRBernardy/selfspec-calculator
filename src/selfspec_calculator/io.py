from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

from .stats import SpeculationStats


def load_speculation_stats(path: str | Path) -> SpeculationStats:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(str(path))

    suffix = p.suffix.lower()
    raw: dict[str, Any]
    if suffix in {".yaml", ".yml"}:
        raw = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    elif suffix == ".json":
        raw = json.loads(p.read_text(encoding="utf-8"))
    else:
        raise ValueError(f"Unsupported stats format: {p.suffix} (expected .json/.yaml/.yml)")

    try:
        return SpeculationStats.model_validate(raw)
    except Exception as exc:  # noqa: BLE001
        raise ValueError(f"Invalid speculation stats: {p}") from exc
