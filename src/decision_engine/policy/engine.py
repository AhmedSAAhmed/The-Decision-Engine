"""The decision itself: ordered, deterministic gates over the signals.

    1 refuse    hard constraint broken (unknown action, actor not allowed, refuse rule)
    2 ask       required field or askable evidence missing    (skipped if a security flag is up)
    3 defer     blocked by a time / external condition         (skipped if a security flag is up)
    4 escalate  escalate rule, security flag, high risk, unverifiable evidence,
                irreversible below threshold, or expected loss over the autonomy budget
    5 execute   confidence ≥ threshold and expected loss ≤ budget
    6 default   escalate (fail safe)

Every gate is evaluated and recorded, so the trace shows why the others did not fire.
"""
from __future__ import annotations

import fnmatch

from ..domains.base import Ctx, Domain, find_approval
from ..models import ActionProposal, Decision, ExtractionRun, GateResult, Signals
from ..signals import SECURITY_FLAGS, compute
from .spec import Policy

ENGINE_VERSION = "0.1.0"


class _Fmt(dict):
    def __missing__(self, k):
        return "{" + k + "}"


def _refuse_only(proposal: ActionProposal, policy: Policy | None, reason: str, run: ExtractionRun | None) -> Decision:
    sig = Signals(confidence=0.0, confidence_parts={}, risk_score=1.0, risk_tier="critical", reversibility="irreversible",
                  impact_if_wrong=0.0, expected_loss=0.0, flags=["outside_catalog"], extraction=run)
    return Decision(proposal=proposal, outcome="refuse", rationale=reason,
                    gate_trace=[GateResult(gate="refuse", matched=True, reasons=[reason])],
                    next_step="Tell the customer this cannot be done through this channel.",
                    signals=sig, policy_id=policy.id if policy else "none", policy_version=policy.version if policy else "-",
                    policy_hash=policy.sha256 if policy else "-", engine_version=ENGINE_VERSION)


def decide(proposal: ActionProposal, domain: Domain, policy: Policy, run: ExtractionRun) -> Decision:
    spec = policy.actions.get(proposal.action)
    if spec is None:
        return _refuse_only(proposal, policy, f"Action '{proposal.action}' is not in the {policy.id} catalogue", run)

    ctx = Ctx(proposal=proposal, record=domain.record, extraction=run.consensus, policy=policy, spec=spec)
    sig, hits = compute(domain, ctx, run)
    flags = set(sig.flags)
    # security flags or critical risk pre-empt ask/defer: don't ask a likely attacker for more input
    security = sorted(flags & SECURITY_FLAGS) + (["critical_risk"] if sig.risk_tier == "critical" else [])
    trace: list[GateResult] = []

    # 1 refuse
    r = []
    if not any(fnmatch.fnmatch(proposal.actor, pat) for pat in spec.allowed_actors):
        r.append(f"actor '{proposal.actor}' is not allowed to perform {proposal.action}")
    r += [rule.reason or c.detail for rule, c in hits.refuse]
    trace.append(GateResult(gate="refuse", matched=bool(r), reasons=r))

    # 2 ask
    a, questions = [], []
    ar = run.consensus.language in ("ar", "mixed")
    for f in sig.missing:
        a.append(f"missing field: {f}")
        fs = spec.required_fields[f]
        q = (fs.question_ar if ar and fs.question_ar else fs.question_en)
        if q:
            questions.append(q)
    for e in sig.evidence:
        if not e.verified and e.askable and not sig.missing:
            a.append(f"customer can supply: {e.key}")
            en, arq = domain.evidence_questions.get(e.key, (f"Could you confirm {e.key.replace('_', ' ')}?", ""))
            questions.append(arq if ar and arq else en)
    if a and not questions:  # a field only the upstream agent can fill: that is an agent bug, not a question
        a.append("no customer-facing question exists for the missing data")
    ask_ok = bool(a) and bool(questions) and not security
    trace.append(GateResult(gate="ask", matched=ask_ok, reasons=a + ([f"skipped: {', '.join(security)}"] if a and security else [])))

    # 3 defer
    dfr = [rule.reason or c.detail for rule, c in hits.defer]
    retry = hits.defer[0][0].retry if hits.defer else None
    trace.append(GateResult(gate="defer", matched=bool(dfr) and not security, reasons=dfr))

    # 4 escalate
    e = [rule.reason or c.detail for rule, c in hits.escalate]
    e += [f"security flag: {f}" for f in security if f != "critical_risk"]
    if "intent_mismatch" in flags:
        e.append(f"conversation intent '{run.consensus.intent}' does not support action '{proposal.action}'")
    if "id_mismatch" in flags:
        e.append("customer mentioned a different id than the one in the proposal")
    if sig.risk_tier in ("high", "critical"):
        e.append(f"risk tier {sig.risk_tier} ({sig.risk_score})")
    unverifiable = [ev.key for ev in sig.evidence if not ev.verified and not ev.askable and ev.source == "system_of_record"]
    if unverifiable:
        e.append(f"evidence failed: {', '.join(unverifiable)}")
    if a and not questions:
        e.append("required data missing and the customer cannot be asked for it")
    approval = find_approval(ctx) if spec.approvals_unlock else None
    budget = policy.autonomy_budget(spec)
    if approval:
        budget = max(budget, float(approval["amount"]) * policy.reversibility_multiplier[spec.reversibility])
    if spec.reversibility == "irreversible" and sig.confidence < policy.thresholds.irreversible_confidence:
        e.append(f"irreversible and confidence {sig.confidence} < {policy.thresholds.irreversible_confidence}")
    if sig.expected_loss > budget:
        e.append(f"expected loss {sig.expected_loss:g} {policy.currency} > autonomy budget {budget:g}")
    trace.append(GateResult(gate="escalate", matched=bool(e), reasons=e))

    # 5 execute
    thr = policy.execute_confidence(spec)
    x_ok = sig.confidence >= thr and sig.expected_loss <= budget
    xr = [f"confidence {sig.confidence} {'≥' if sig.confidence >= thr else '<'} {thr}",
          f"expected loss {sig.expected_loss:g} {'≤' if sig.expected_loss <= budget else '>'} budget {budget:g}"]
    if approval:
        xr.append(f"risk carried by human approval {approval['id']} ({approval['approver']})")
    trace.append(GateResult(gate="execute", matched=x_ok, reasons=xr))

    # first matching gate wins; nothing matched = fail-safe escalate
    outcome = next((g.gate for g in trace if g.matched), "escalate")
    winner = next((g for g in trace if g.gate == outcome), None)
    reasons = winner.reasons if winner and winner.matched else ["no gate cleared: fail-safe escalate"]

    fmt = _Fmt({**{k: str(v) for k, v in proposal.params.items()}, "action": proposal.action})
    nxt = {
        "execute": spec.execute_template.format_map(fmt),
        "ask": "Ask the customer: " + " / ".join(questions),
        "defer": f"Hold. {retry or 'Re-check later'}",
        "escalate": f"Hand to {spec.route_to} with full context; tell the customer a specialist will reply",
        "refuse": "Decline politely and explain the policy; offer the right channel",
    }[outcome]
    return Decision(
        proposal=proposal, outcome=outcome, rationale=f"{outcome.upper()}: " + "; ".join(reasons[:3]),
        gate_trace=trace, next_step=nxt, route_to=spec.route_to if outcome == "escalate" else None,
        questions=questions if outcome == "ask" else [], retry_condition=retry if outcome == "defer" else None,
        signals=sig, policy_id=policy.id, policy_version=policy.version, policy_hash=policy.sha256,
        engine_version=ENGINE_VERSION,
    )
