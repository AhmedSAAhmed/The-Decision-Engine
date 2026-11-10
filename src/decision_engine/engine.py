"""Facade: proposal in, audited decision out. Also replay and human resolution."""
from __future__ import annotations

import os
from typing import Any

from .audit.store import AuditStore
from .domains import load_domains
from .llm.client import make_extractor
from .models import ActionProposal, Decision, ExtractionRun
from .policy.engine import ENGINE_VERSION, _refuse_only, decide
from .policy.spec import load_policies


class RecordedExtractor:
    """Replays the extraction stored in the audit log, so replay is deterministic."""

    def __init__(self, run: ExtractionRun):
        self.run = run

    def extract(self, *_a, **_k) -> ExtractionRun:
        return self.run


class DecisionEngine:
    def __init__(self, audit: AuditStore | None = None, extractor=None, domains=None, policies=None):
        self.audit = audit or AuditStore(os.getenv("DE_AUDIT_DB", "runs/audit.db"))
        self.extractor = extractor or make_extractor()
        self.domains = domains or load_domains()
        self.policies = policies or load_policies()

    def evaluate(self, proposal: ActionProposal, extractor=None) -> Decision:
        """Decide without writing to the audit log (used by evals and replay)."""
        domain = self.domains.get(proposal.domain)
        policy = self.policies.get(proposal.domain)
        if domain is None or policy is None:
            return _refuse_only(proposal, None, f"Unknown domain '{proposal.domain}'", None)
        run = (extractor or self.extractor).extract(proposal, domain.intent_keywords, domain.id_pattern)
        return decide(proposal, domain, policy, run)

    def decide(self, proposal: ActionProposal) -> Decision:
        d = self.evaluate(proposal)
        self.audit.append("decision", d.id, d.model_dump(mode="json"))
        return d

    def replay(self, decision_id: str) -> dict[str, Any]:
        recs = [r for r in self.audit.get(decision_id) if r.kind == "decision"]
        if not recs:
            return {"ok": False, "error": f"no decision {decision_id}"}
        old = Decision.model_validate(recs[0].payload)
        policy = self.policies.get(old.proposal.domain)
        run = old.signals.extraction
        new = self.evaluate(old.proposal, extractor=RecordedExtractor(run)) if run else self.evaluate(old.proposal)
        same = (new.outcome == old.outcome and new.signals.confidence == old.signals.confidence
                and new.signals.expected_loss == old.signals.expected_loss)
        return {"ok": same, "original": old.outcome, "replayed": new.outcome,
                "policy_unchanged": bool(policy and policy.sha256 == old.policy_hash),
                "engine_version": ENGINE_VERSION, "confidence": [old.signals.confidence, new.signals.confidence]}

    def resolve(self, decision_id: str, reviewer: str, verdict: str, note: str = "") -> dict:
        """A human closes an ask/escalate. Written to the same chain, linked by decision id."""
        payload = {"decision_id": decision_id, "reviewer": reviewer, "verdict": verdict, "note": note}
        rec = self.audit.append("human_resolution", decision_id, payload)
        return {"seq": rec.seq, "hash": rec.hash, **payload}

    def open_queue(self) -> list[Decision]:
        resolved = {r.ref_id for r in self.audit.all() if r.kind == "human_resolution"}
        out = []
        for r in self.audit.recent(200):
            if r.kind == "decision" and r.ref_id not in resolved and r.payload["outcome"] in ("ask", "escalate"):
                out.append(Decision.model_validate(r.payload))
        return out
