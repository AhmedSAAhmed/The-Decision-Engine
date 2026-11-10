"""Turn a proposal + extraction into the five signals: confidence, risk, evidence,
missing information, reversibility (plus expected loss). Pure functions, no I/O."""
from __future__ import annotations

from dataclasses import dataclass, field

from ..domains.base import Check, Ctx, Domain, verify_authority_claims
from ..models import Evidence, ExtractionRun, Signals
from ..policy.spec import Rule

RISK_FLAG_WEIGHTS = {
    "prompt_injection_suspected": 0.45,
    "authority_claim_unverified": 0.35,
    "intent_mismatch": 0.3,
    "id_mismatch": 0.3,
}
SECURITY_FLAGS = {"prompt_injection_suspected", "authority_claim_unverified"}


@dataclass
class RuleHits:
    refuse: list[tuple[Rule, Check]] = field(default_factory=list)
    defer: list[tuple[Rule, Check]] = field(default_factory=list)
    escalate: list[tuple[Rule, Check]] = field(default_factory=list)
    risk: list[tuple[Rule, Check]] = field(default_factory=list)
    margins: list[float] = field(default_factory=list)


def _impact(ctx: Ctx) -> float:
    imp = ctx.spec.impact
    if isinstance(imp, str) and imp.startswith("param:"):
        return ctx.num(imp.split(":", 1)[1])
    return float(imp)


def evaluate_rules(domain: Domain, ctx: Ctx) -> RuleHits:
    hits = RuleHits()
    for bucket in ("refuse", "defer", "escalate", "risk"):
        for rule in getattr(ctx.spec, f"{bucket}_if" if bucket != "risk" else "risk"):
            fn = domain.checks.get(rule.check)
            if fn is None:
                raise KeyError(f"policy {ctx.policy.id} refers to unknown check '{rule.check}'")
            c = fn(ctx, rule)
            if c.margin is not None and bucket in ("refuse", "escalate"):
                hits.margins.append(c.margin)
            if c.matched:
                getattr(hits, bucket).append((rule, c))
    return hits


def compute(domain: Domain, ctx: Ctx, run: ExtractionRun) -> tuple[Signals, RuleHits]:
    spec, policy, ex = ctx.spec, ctx.policy, run.consensus

    missing = [f for f in spec.required_fields if ctx.p.get(f) in (None, "", [])]

    evidence: list[Evidence] = []
    for key in spec.required_evidence:
        if missing:
            evidence.append(Evidence(key=key, description=key.replace("_", " "), verified=False,
                                     detail=f"cannot check: missing {', '.join(missing)}",
                                     askable=domain.evidence[key](ctx).askable if key in domain.evidence else False))
        else:
            evidence.append(domain.evidence[key](ctx))
    authority = verify_authority_claims(ctx)
    evidence += authority

    flags: list[str] = []
    if ex.instructions_to_system:
        flags.append("prompt_injection_suspected")
    if any(not e.verified for e in authority):
        flags.append("authority_claim_unverified")
    if spec.intents and ex.intent not in spec.intents and ex.intent != "unknown":
        flags.append("intent_mismatch")
    proposed_ids = {str(v) for k, v in ctx.p.items() if k in ("order_id", "msisdn", "txn_id", "card_last4")}
    if proposed_ids and ex.ids_mentioned and not proposed_ids & set(ex.ids_mentioned):
        flags.append("id_mismatch")
    if run.provider == "mock" and run.errors:
        flags.append("llm_unavailable_used_fallback")

    hits = evaluate_rules(domain, ctx) if not missing else RuleHits()

    # ---- confidence: computed, never self-reported
    sor = [e for e in evidence if e.source == "system_of_record"]
    coverage = sum(e.verified for e in sor) / len(sor) if sor else 1.0
    # a conversation that contradicts the proposal, or tries to steer the system, is read with less trust
    consistency = run.agreement * (0.5 if {"intent_mismatch", "id_mismatch", *SECURITY_FLAGS} & set(flags) else 1.0)
    rule_margin = min(hits.margins) if hits.margins else 1.0
    w = policy.confidence_weights
    confidence = round(w["evidence"] * coverage + w["consistency"] * consistency + w["rule_margin"] * rule_margin, 3)

    # ---- risk
    factors, score = [], 0.0
    for rule, c in hits.risk:
        score += rule.weight
        factors.append(f"{rule.label or rule.check} ({c.detail})")
    for f in flags:
        if f in RISK_FLAG_WEIGHTS:
            score += RISK_FLAG_WEIGHTS[f]
            factors.append(f.replace("_", " "))
    if spec.reversibility == "irreversible":
        score += 0.15
        factors.append("irreversible action")
    score = round(min(score, 1.0), 3)
    tiers = policy.risk_tiers
    tier = ("critical" if score >= tiers["critical"] else "high" if score >= tiers["high"]
            else "medium" if score >= tiers["medium"] else "low")

    impact = _impact(ctx)
    mult = policy.reversibility_multiplier[spec.reversibility]
    expected_loss = round((1 - confidence) * impact * mult, 3)

    signals = Signals(
        confidence=confidence,
        confidence_parts={"evidence_coverage": round(coverage, 3), "self_consistency": round(consistency, 3),
                          "rule_margin": round(rule_margin, 3)},
        risk_score=score, risk_tier=tier, risk_factors=factors, evidence=evidence, missing=missing,
        reversibility=spec.reversibility, impact_if_wrong=impact, expected_loss=expected_loss,
        cost_of_delay=spec.cost_of_delay, flags=flags, extraction=run,
    )
    return signals, hits
