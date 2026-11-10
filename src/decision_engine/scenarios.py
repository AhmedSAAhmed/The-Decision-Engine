"""Load labelled scenarios (evals/scenarios/*.yaml) as proposals on the fixed demo clock."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

import yaml

from .models import ActionProposal, Message

ROOT = Path(__file__).resolve().parents[2]
SCENARIO_DIR = ROOT / "evals" / "scenarios"
DEMO_NOW = datetime.fromisoformat("2026-11-10T10:00:00+03:00")  # matches data/generate.py ANCHOR


def load_scenarios(directory: Path = SCENARIO_DIR) -> list[dict]:
    out = []
    for f in sorted(directory.glob("*.yaml")):
        out += yaml.safe_load(f.read_text(encoding="utf-8"))
    return out


def to_proposal(s: dict) -> ActionProposal:
    ch = s.get("channel", "whatsapp")
    return ActionProposal(
        id=f"prop_{s['id']}", domain=s["domain"], action=s["action"], params=s.get("params") or {},
        actor=s.get("actor", "doo_agent"), customer_id=s["customer_id"], channel=ch,
        conversation=[Message(channel=ch, text=t) for t in s["messages"]], requested_at=DEMO_NOW,
    )
