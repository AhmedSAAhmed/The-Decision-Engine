"""Policy file schema. Policies are YAML (factory material): readable by non-engineers,
versioned, and hashed into every audit record."""
from __future__ import annotations

import hashlib
from pathlib import Path

import yaml
from pydantic import BaseModel, Field

from ..models import Reversibility

POLICY_DIR = Path(__file__).resolve().parents[3] / "policies"


class FieldSpec(BaseModel):
    question_en: str
    question_ar: str = ""


class Rule(BaseModel):
    check: str
    value: float | None = None
    reason: str = ""
    retry: str = ""          # defer rules: when to try again
    weight: float = 0.0      # risk rules: contribution to the risk score
    label: str = ""          # risk rules: human label


class ActionSpec(BaseModel):
    description: str
    reversibility: Reversibility
    allowed_actors: list[str] = Field(default_factory=lambda: ["doo_agent", "agent:*"])
    intents: list[str] = Field(default_factory=list)
    impact: str | float = 0.0          # number, or "param:<name>" to read it from the proposal
    cost_of_delay: float = 0.0
    required_fields: dict[str, FieldSpec] = Field(default_factory=dict)
    required_evidence: list[str] = Field(default_factory=list)
    refuse_if: list[Rule] = Field(default_factory=list)
    defer_if: list[Rule] = Field(default_factory=list)
    escalate_if: list[Rule] = Field(default_factory=list)
    risk: list[Rule] = Field(default_factory=list)
    route_to: str = "human_supervisor"
    approvals_unlock: bool = False     # a verified human approval covers the risk
    execute_confidence: float | None = None
    autonomy_budget: float | None = None
    execute_template: str = "Execute {action}"


class Thresholds(BaseModel):
    execute_confidence: float = 0.8
    irreversible_confidence: float = 0.95
    autonomy_budget: float = 3.0


class Policy(BaseModel):
    id: str
    name: str
    version: str
    currency: str = "BHD"
    org: str = ""
    confidence_weights: dict[str, float] = Field(
        default_factory=lambda: {"evidence": 0.5, "consistency": 0.3, "rule_margin": 0.2}
    )
    thresholds: Thresholds = Field(default_factory=Thresholds)
    reversibility_multiplier: dict[str, float] = Field(
        default_factory=lambda: {"reversible": 1.0, "compensable": 3.0, "irreversible": 10.0}
    )
    risk_tiers: dict[str, float] = Field(
        default_factory=lambda: {"medium": 0.3, "high": 0.6, "critical": 0.85}
    )
    actions: dict[str, ActionSpec]
    sha256: str = ""

    def execute_confidence(self, a: ActionSpec) -> float:
        return a.execute_confidence if a.execute_confidence is not None else self.thresholds.execute_confidence

    def autonomy_budget(self, a: ActionSpec) -> float:
        return a.autonomy_budget if a.autonomy_budget is not None else self.thresholds.autonomy_budget


def load_policy(path: Path) -> Policy:
    raw = path.read_bytes()
    data = yaml.safe_load(raw)
    p = Policy.model_validate(data)
    p.sha256 = hashlib.sha256(raw).hexdigest()
    return p


def load_policies(directory: Path = POLICY_DIR) -> dict[str, Policy]:
    out: dict[str, Policy] = {}
    for f in sorted(directory.glob("*.yaml")):
        p = load_policy(f)
        out[p.id] = p
    return out
