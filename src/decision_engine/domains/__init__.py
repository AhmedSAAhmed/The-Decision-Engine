"""Domain registry. Each domain is built over its own synthetic system of record."""
from __future__ import annotations

import copy
import json
from functools import lru_cache
from pathlib import Path

from . import banking, food_delivery, telecom
from .base import Domain

DATA_DIR = Path(__file__).resolve().parents[3] / "data" / "synthetic"
BUILDERS = {"food_delivery": food_delivery.build, "telecom": telecom.build, "banking": banking.build}


@lru_cache(maxsize=None)
def _raw(domain_id: str) -> dict:
    return json.loads((DATA_DIR / f"{domain_id}.json").read_text(encoding="utf-8"))


def load_domains(overrides: dict[str, dict] | None = None) -> dict[str, Domain]:
    """Fresh domains over a deep copy of the data, so tests and demos can mutate records safely."""
    out = {}
    for key, build in BUILDERS.items():
        rec = copy.deepcopy(_raw(key))
        if overrides and key in overrides:
            rec.update(overrides[key])
        out[key] = build(rec)
    return out


__all__ = ["Domain", "load_domains"]
