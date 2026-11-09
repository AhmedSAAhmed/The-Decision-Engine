"""Domain plug-in interface.

A domain supplies three things and nothing else:
  * a system of record (the data it may trust),
  * evidence checks: functions that verify a claim against that record,
  * rule checks: named predicates the policy YAML refers to.
The engine owns the decision. A domain never returns an outcome.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, Callable

from ..models import ActionProposal, Evidence, Extraction
from ..policy.spec import ActionSpec, Policy, Rule


@dataclass
class Check:
    matched: bool
    detail: str = ""
    margin: float | None = None  # 0..1 distance from a numeric threshold (None = not numeric)


@dataclass
class Ctx:
    proposal: ActionProposal
    record: dict[str, Any]          # this domain's system of record
    extraction: Extraction
    policy: Policy
    spec: ActionSpec

    @property
    def p(self) -> dict[str, Any]:
        return self.proposal.params

    @property
    def today(self) -> date:
        return self.proposal.requested_at.date()

    def days_since(self, iso: str) -> int:
        return (self.today - datetime.fromisoformat(iso).date()).days

    def num(self, name: str, default: float = 0.0) -> float:
        try:
            return float(self.p.get(name, default))
        except (TypeError, ValueError):
            return default


EvidenceFn = Callable[[Ctx], Evidence]
CheckFn = Callable[[Ctx, Rule], Check]


@dataclass
class Domain:
    id: str
    title: str
    record: dict[str, Any]
    evidence: dict[str, EvidenceFn] = field(default_factory=dict)
    checks: dict[str, CheckFn] = field(default_factory=dict)
    # mock extractor vocabulary: intent -> keywords (English, Arabic, Arabizi)
    intent_keywords: dict[str, list[str]] = field(default_factory=dict)
    id_pattern: str = r"\b\d{4,6}\b"
    evidence_questions: dict[str, tuple[str, str]] = field(default_factory=dict)

    def ev(self, key: str):
        def deco(fn: EvidenceFn) -> EvidenceFn:
            self.evidence[key] = fn
            return fn
        return deco

    def check(self, key: str):
        def deco(fn: CheckFn) -> CheckFn:
            self.checks[key] = fn
            return fn
        return deco


def threshold_check(value: float, limit: float, label: str) -> Check:
    """Shared numeric predicate: matched if value > limit, with a margin for rule certainty."""
    margin = min(1.0, abs(value - limit) / limit) if limit else 1.0
    return Check(value > limit, f"{label} {value:g} vs limit {limit:g}", margin)


def register_common(d: Domain) -> None:
    """Checks every domain gets for free."""

    @d.check("amount_over")
    def _amount_over(ctx: Ctx, r: Rule) -> Check:
        return threshold_check(ctx.num("amount"), float(r.value or 0), "amount")

    @d.check("amount_over_without_approval")
    def _amount_over_wo(ctx: Ctx, r: Rule) -> Check:
        c = threshold_check(ctx.num("amount"), float(r.value or 0), "amount")
        appr = find_approval(ctx)
        if c.matched and appr:
            return Check(False, f"amount above limit but covered by approval {appr['id']}", c.margin)
        return c

    @d.check("customer_urgency_pressure")
    def _urgency(ctx: Ctx, r: Rule) -> Check:
        return Check(ctx.extraction.urgency_pressure, "customer applies urgency pressure")


def find_approval(ctx: Ctx) -> dict[str, Any] | None:
    """A human approval in the system of record that covers this exact action."""
    ref = str(ctx.p.get("order_id") or ctx.p.get("txn_id") or ctx.p.get("msisdn") or "")
    amount = ctx.num("amount")
    for a in ctx.record.get("approvals", []):
        if a.get("ref") == ref and a.get("action") == ctx.proposal.action and float(a.get("amount", 0)) >= amount:
            return a
    return None


def verify_authority_claims(ctx: Ctx) -> list[Evidence]:
    """Turn every 'X already approved this' claim into evidence: verified only if the record agrees."""
    out = []
    appr = find_approval(ctx)
    for claim in ctx.extraction.authority_claims:
        out.append(
            Evidence(
                key="authority_claim",
                description=f"Customer claims: {claim[:120]}",
                source="customer_claim",
                verified=appr is not None,
                detail=(f"matches approval {appr['id']} by {appr['approver']}" if appr
                        else "no matching approval in the system of record"),
            )
        )
    return out
