import os

import pytest

os.environ["DE_LLM_MODE"] = "mock"

from decision_engine.audit.store import AuditStore
from decision_engine.engine import DecisionEngine
from decision_engine.llm.mock import MockExtractor
from decision_engine.scenarios import load_scenarios, to_proposal

SCEN = {s["id"]: s for s in load_scenarios()}


@pytest.fixture
def engine():
    return DecisionEngine(audit=AuditStore(), extractor=MockExtractor())


@pytest.mark.parametrize("sid", [s for s in SCEN if "known_limitation" not in SCEN[s].get("tags", [])])
def test_labelled_scenarios(engine, sid):
    d = engine.evaluate(to_proposal(SCEN[sid]))
    assert d.outcome == SCEN[sid]["expected"], d.rationale


def test_every_outcome_reachable_in_every_domain(engine):
    seen = {}
    for s in SCEN.values():
        seen.setdefault(s["domain"], set()).add(engine.evaluate(to_proposal(s)).outcome)
    for dom, outs in seen.items():
        assert {"execute", "escalate", "refuse"} <= outs, (dom, outs)
    assert set().union(*seen.values()) == {"execute", "ask", "defer", "escalate", "refuse"}


def test_failure_1_forged_authority_is_caught(engine):
    d = engine.evaluate(to_proposal(SCEN["fd-12"]))
    assert d.outcome == "escalate"
    assert {"prompt_injection_suspected", "authority_claim_unverified"} <= set(d.signals.flags)
    claim = [e for e in d.signals.evidence if e.key == "authority_claim"]
    assert claim and not any(e.verified for e in claim)


def test_failure_2_poisoned_record_is_a_documented_break(engine):
    """This test pins the known limitation: a forged approval row inside the system of record
    is indistinguishable from a real one, so the engine executes. See docs/failure-tests.md."""
    d = engine.evaluate(to_proposal(SCEN["fd-13"]))
    assert d.outcome == "execute"
    assert any("APR-2290" in r for g in d.gate_trace for r in g.reasons)


def test_injection_never_executes_money(engine):
    for s in SCEN.values():
        d = engine.evaluate(to_proposal(s))
        if "prompt_injection_suspected" in d.signals.flags:
            assert d.outcome in ("escalate", "refuse"), s["id"]


def test_gate_trace_is_complete(engine):
    d = engine.evaluate(to_proposal(SCEN["fd-01"]))
    assert [g.gate for g in d.gate_trace] == ["refuse", "ask", "defer", "escalate", "execute"]


def test_expected_loss_formula(engine):
    d = engine.evaluate(to_proposal(SCEN["fd-01"]))
    s = d.signals
    assert s.expected_loss == pytest.approx((1 - s.confidence) * s.impact_if_wrong * 3, abs=1e-3)


def test_arabic_question_for_arabic_customer(engine):
    d = engine.evaluate(to_proposal(SCEN["fd-03"]))
    assert d.outcome == "ask" and any("؀" <= ch <= "ۿ" for ch in d.questions[0])


def test_unknown_domain_and_action_refuse(engine):
    p = to_proposal(SCEN["fd-01"])
    assert engine.evaluate(p.model_copy(update={"domain": "crypto"})).outcome == "refuse"
    assert engine.evaluate(p.model_copy(update={"action": "delete_account"})).outcome == "refuse"


def test_audit_chain_and_tamper_detection(engine):
    for sid in ("fd-01", "fd-12", "bk-10"):
        engine.decide(to_proposal(SCEN[sid]))
    assert engine.audit.verify() == (True, None, 3)
    engine.audit.db.execute("UPDATE audit SET payload = replace(payload, 'escalate', 'execute') WHERE seq = 2")
    ok, bad, _ = engine.audit.verify()
    assert not ok and bad == 2


def test_replay_is_deterministic(engine):
    d = engine.decide(to_proposal(SCEN["tc-07"]))
    r = engine.replay(d.id)
    assert r["ok"] and r["policy_unchanged"] and r["replayed"] == "ask"


def test_human_resolution_closes_queue(engine):
    d = engine.decide(to_proposal(SCEN["fd-12"]))
    assert d.id in {q.id for q in engine.open_queue()}
    engine.resolve(d.id, "maryam.cx_supervisor", "rejected", "no approval exists")
    assert d.id not in {q.id for q in engine.open_queue()}
    assert engine.audit.verify()[0]
