"""Typed contracts for the whole pipeline: proposal -> signals -> decision -> audit."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field

Outcome = Literal["execute", "ask", "defer", "escalate", "refuse"]
OUTCOMES: tuple[str, ...] = ("execute", "ask", "defer", "escalate", "refuse")
Reversibility = Literal["reversible", "compensable", "irreversible"]
RiskTier = Literal["low", "medium", "high", "critical"]
Channel = Literal["whatsapp", "email", "voice", "webchat", "instagram", "branch"]


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Message(BaseModel):
    role: Literal["customer", "agent"] = "customer"
    channel: Channel = "whatsapp"
    text: str


class ActionProposal(BaseModel):
    """What an upstream AI agent wants to do. The decision layer never trusts it blindly."""

    id: str = Field(default_factory=lambda: f"prop_{uuid.uuid4().hex[:10]}")
    domain: str
    action: str
    params: dict[str, Any] = Field(default_factory=dict)
    actor: str = "doo_agent"
    customer_id: str
    channel: Channel = "whatsapp"
    conversation: list[Message] = Field(default_factory=list)
    requested_at: datetime = Field(default_factory=_now)


class Extraction(BaseModel):
    """What the LLM (or the mock extractors) read out of the untrusted conversation.

    Every field here is a *claim*, never evidence.
    """

    intent: str = "unknown"
    language: str = "en"
    ids_mentioned: list[str] = Field(default_factory=list)
    amounts_mentioned: list[float] = Field(default_factory=list)
    authority_claims: list[str] = Field(default_factory=list)
    instructions_to_system: bool = False
    urgency_pressure: bool = False
    summary: str = ""


class ExtractionRun(BaseModel):
    provider: str
    model: str
    samples: list[Extraction]
    agreement: float  # 0..1, how much the samples / extractors agree
    errors: list[str] = Field(default_factory=list)

    @property
    def consensus(self) -> Extraction:
        return self.samples[0] if self.samples else Extraction()


class Evidence(BaseModel):
    key: str
    description: str
    source: Literal["system_of_record", "customer_claim", "policy"] = "system_of_record"
    verified: bool
    detail: str = ""
    askable: bool = False  # can we get it by asking the customer?


class Signals(BaseModel):
    confidence: float
    confidence_parts: dict[str, float]
    risk_score: float
    risk_tier: RiskTier
    risk_factors: list[str] = Field(default_factory=list)
    evidence: list[Evidence] = Field(default_factory=list)
    missing: list[str] = Field(default_factory=list)
    reversibility: Reversibility
    impact_if_wrong: float
    expected_loss: float
    cost_of_delay: float = 0.0
    flags: list[str] = Field(default_factory=list)
    extraction: ExtractionRun | None = None

    @property
    def evidence_coverage(self) -> float:
        req = [e for e in self.evidence if e.source == "system_of_record"]
        return 1.0 if not req else sum(e.verified for e in req) / len(req)


class GateResult(BaseModel):
    gate: Outcome
    matched: bool
    reasons: list[str] = Field(default_factory=list)


class Decision(BaseModel):
    id: str = Field(default_factory=lambda: f"dec_{uuid.uuid4().hex[:10]}")
    proposal: ActionProposal
    outcome: Outcome
    rationale: str
    gate_trace: list[GateResult]
    next_step: str
    route_to: str | None = None
    questions: list[str] = Field(default_factory=list)
    retry_condition: str | None = None
    signals: Signals
    policy_id: str
    policy_version: str
    policy_hash: str
    engine_version: str
    decided_at: datetime = Field(default_factory=_now)


class AuditRecord(BaseModel):
    seq: int
    kind: Literal["decision", "human_resolution"]
    ref_id: str
    payload: dict[str, Any]
    prev_hash: str
    hash: str
    created_at: str
