"""Gradio front end: Decide · Review queue · Audit · Evals · How it works."""
from __future__ import annotations

import json
import time
from collections import defaultdict

import gradio as gr

from decision_engine.engine import DecisionEngine
from decision_engine.llm.client import LLMExtractor, available_providers
from decision_engine.llm.mock import MockExtractor
from decision_engine.models import ActionProposal, Message
from decision_engine.scenarios import DEMO_NOW, load_scenarios, to_proposal

from . import render

SCENARIOS = load_scenarios()
BY_ID = {s["id"]: s for s in SCENARIOS}
DOMAIN_LABEL = {"food_delivery": "Sufra Delivery · food", "telecom": "Nahla Telecom · telco", "banking": "Gulf Pearl Bank · bank"}


class RateLimiter:
    def __init__(self, per_hour: int):
        self.per_hour, self.hits = per_hour, defaultdict(list)

    def allow(self, key: str) -> bool:
        now = time.time()
        self.hits[key] = [t for t in self.hits[key] if now - t < 3600]
        if len(self.hits[key]) >= self.per_hour:
            return False
        self.hits[key].append(now)
        return True


def scenario_choices(domain: str) -> list[tuple[str, str]]:
    return [(f"{s['id']} · {s['title']}", s["id"]) for s in SCENARIOS if s["domain"] == domain]


def build(engine: DecisionEngine, limiter: RateLimiter) -> gr.Blocks:
    mock, llm = MockExtractor(), (LLMExtractor() if available_providers() else None)
    providers = ", ".join(p[0] for p in available_providers()) or "none configured"
    actions = {d: list(p.actions) for d, p in engine.policies.items()}

    def load_scenario(sid):
        s = BY_ID[sid]
        return (gr.update(choices=actions[s["domain"]], value=s["action"]), s["customer_id"], s.get("actor", "doo_agent"),
                json.dumps(s.get("params") or {}, ensure_ascii=False, indent=1), "\n".join(s["messages"]),
                f"**Label (hand-written):** `{s['expected']}` · {s['why']}")

    def change_domain(domain):
        ch = scenario_choices(domain)
        return gr.update(choices=ch, value=ch[0][1])

    def run(domain, sid, action, customer_id, actor, params_json, convo, use_llm, request: gr.Request):
        try:
            params = json.loads(params_json or "{}")
        except json.JSONDecodeError as ex:
            raise gr.Error(f"Params must be JSON: {ex}")
        s = BY_ID.get(sid, {})
        prop = ActionProposal(domain=domain, action=action, params=params, actor=actor or "doo_agent",
                              customer_id=customer_id, channel=s.get("channel", "whatsapp"), requested_at=DEMO_NOW,
                              conversation=[Message(channel=s.get("channel", "whatsapp"), text=t)
                                            for t in convo.split("\n") if t.strip()])
        ex = mock
        note = ""
        if use_llm and llm:
            ip = (request.client.host if request and request.client else "anon")
            if limiter.allow(ip):
                ex = llm
            else:
                note = "Real-LLM rate limit reached for your IP. This one used the offline extractor."
        engine.extractor = ex
        d = engine.decide(prop)
        engine.extractor = mock
        raw = json.dumps(d.model_dump(mode="json"), ensure_ascii=False, indent=1)
        return render.outcome_card(d), render.gate_timeline(d), render.evidence_table(d), raw, d.id, note

    def queue_view():
        q = engine.open_queue()
        return render.queue_table(q), gr.update(choices=[d.id for d in q], value=q[0].id if q else None)

    def resolve(did, reviewer, verdict, note):
        if not did:
            raise gr.Error("Pick a decision from the queue")
        engine.resolve(did, reviewer or "reviewer", verdict, note or "")
        return queue_view()

    def audit_view():
        ok, bad, n = engine.audit.verify()
        status = (f"<p class='de-eyebrow'>/// Chain verified · {n} records · every hash matches</p>" if ok else
                  f"<p class='de-eyebrow' style='color:#B42318'>/// Chain BROKEN at seq {bad}</p>")
        return status + render.audit_table(engine.audit.recent(40))

    def replay(did):
        if not did:
            raise gr.Error("Enter a decision id")
        return "```json\n" + json.dumps(engine.replay(did.strip()), indent=1) + "\n```"

    def run_evals():
        from evals.run_evals import build as build_report
        md, _ = build_report(extractor=mock)
        return md

    with gr.Blocks(title="The Decision Engine", fill_width=False) as demo:
        gr.HTML("""
<div class='de-hero'>
  <p class='de-eyebrow'>/// Decision layer for AI customer-service agents</p>
  <h1>Know when your agent is <em>allowed</em> to act</h1>
  <p>An AI agent proposes an action. This engine pulls five signals out of the conversation and checks them against the
  system of record, then returns <b>execute · ask · defer · escalate · refuse</b>, with a hash-chained audit trail.
  The LLM only extracts signals. The policy makes the decision.</p>
  <div class='de-stats'><div><b>3</b><span>GCC domains: food, telco, bank</span></div>
  <div><b>38</b><span>hand-labelled scenarios</span></div><div><b>0</b><span>unsafe executes outside the documented break</span></div>
  <div><b>5</b><span>ordered gates, first match wins</span></div></div>
</div>""")
        with gr.Tabs():
            with gr.Tab("Decide"):
                with gr.Row(equal_height=False):
                    with gr.Column(scale=4, min_width=320):
                        gr.HTML("<p class='de-eyebrow'>/// Proposed action</p>")
                        domain = gr.Dropdown([(v, k) for k, v in DOMAIN_LABEL.items()], value="food_delivery", label="Business")
                        first = scenario_choices("food_delivery")
                        sid = gr.Dropdown(first, value="fd-12", label="Scenario")
                        label = gr.Markdown()
                        convo = gr.Textbox(label="Customer conversation (untrusted, one message per line)", lines=4)
                        with gr.Row():
                            action = gr.Dropdown(actions["food_delivery"], label="Action the agent proposes")
                            customer = gr.Textbox(label="Customer id")
                        actor = gr.Textbox(label="Actor", value="doo_agent")
                        params = gr.Code(label="Action params (JSON)", language="json", lines=5)
                        use_llm = gr.Checkbox(value=False, label=f"Use a real LLM for extraction ({providers})",
                                              interactive=llm is not None)
                        go = gr.Button("Decide", variant="primary")
                        note = gr.Markdown()
                    with gr.Column(scale=6, min_width=360):
                        out = gr.HTML("<div class='de-outcome'><p class='next'>Pick a scenario and press Decide.</p></div>")
                        with gr.Row():
                            trace = gr.HTML()
                        ev = gr.HTML()
                        with gr.Accordion("Full decision record (JSON, as written to the audit log)", open=False):
                            raw = gr.Code(language="json")
                        last_id = gr.Textbox(label="Decision id", interactive=False)
                domain.change(change_domain, domain, sid)
                sid.change(load_scenario, sid, [action, customer, actor, params, convo, label])
                go.click(run, [domain, sid, action, customer, actor, params, convo, use_llm], [out, trace, ev, raw, last_id, note])
                demo.load(load_scenario, sid, [action, customer, actor, params, convo, label])

            with gr.Tab("Review queue"):
                gr.HTML("<p class='de-eyebrow'>/// Human in the loop: every ask and escalate waits here</p>")
                qhtml = gr.HTML()
                with gr.Row():
                    qid = gr.Dropdown(label="Decision", choices=[])
                    reviewer = gr.Textbox(label="Reviewer", value="maryam.cx_supervisor")
                    verdict = gr.Radio(["approved", "rejected", "answered"], value="rejected", label="Verdict")
                qnote = gr.Textbox(label="Note")
                with gr.Row():
                    gr.Button("Refresh").click(queue_view, None, [qhtml, qid])
                    gr.Button("Record verdict", variant="primary").click(resolve, [qid, reviewer, verdict, qnote], [qhtml, qid])

            with gr.Tab("Audit trail"):
                gr.HTML("<p class='de-eyebrow'>/// Append-only · sha256(prev_hash ‖ record) · replayable</p>")
                ahtml = gr.HTML()
                gr.Button("Verify chain & refresh").click(audit_view, None, ahtml)
                with gr.Row():
                    rid = gr.Textbox(label="Decision id to replay")
                    gr.Button("Replay").click(replay, rid, rout := gr.Markdown())

            with gr.Tab("Evals"):
                gr.HTML("<p class='de-eyebrow'>/// Engine vs Yes-man (always execute) vs Coward (always escalate)</p>")
                emd = gr.Markdown()
                gr.Button("Run all 38 scenarios", variant="primary").click(run_evals, None, emd)

            with gr.Tab("How it works"):
                gr.HTML("""
<p class='de-eyebrow'>/// Inputs → signals → decision → audit</p>
<div class='de-flow'>
 <div><p class='de-eyebrow'>01 Input</p><h3>Proposal</h3><p>Action, params, actor and the raw customer conversation
 (WhatsApp, voice, email, Arabic or English). Treated as untrusted.</p></div>
 <div><p class='de-eyebrow'>02 Signals</p><h3>Five signals</h3><p>Confidence (evidence coverage + self-consistency + rule
 margin), risk, evidence verified against the system of record, missing info, reversibility → expected loss.</p></div>
 <div><p class='de-eyebrow'>03 Decision</p><h3>Ordered gates</h3><p>refuse → ask → defer → escalate → execute. Policies are
 versioned YAML. Security flags and critical risk skip ask/defer. Nothing cleared = escalate.</p></div>
 <div><p class='de-eyebrow'>04 Audit</p><h3>Hash chain</h3><p>Every decision and human verdict is appended with
 sha256(prev ‖ record). Tampering breaks the chain; any decision replays deterministically.</p></div>
</div>
<div class='de-section'><p class='de-eyebrow'>/// Where it breaks</p>
<p>The engine is only as trustworthy as its system of record. A forged approval row written straight into the database
(scenario fd-13) looks legitimate, and the engine executes a 180 BHD refund. See <code>docs/failure-tests.md</code>.</p></div>""")
        demo.load(queue_view, None, [qhtml, qid])
        demo.load(audit_view, None, ahtml)
    return demo
