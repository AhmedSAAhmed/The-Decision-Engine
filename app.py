"""One process: REST API at /api, Gradio UI at /.  Run:  uv run python app.py  → http://localhost:7860"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

import gradio as gr  # noqa: E402
import uvicorn  # noqa: E402
from fastapi import FastAPI, HTTPException, Request  # noqa: E402
from pydantic import BaseModel  # noqa: E402

from decision_engine.engine import DecisionEngine  # noqa: E402
from decision_engine.llm.mock import MockExtractor  # noqa: E402
from decision_engine.models import ActionProposal, Decision  # noqa: E402
from decision_engine.scenarios import load_scenarios  # noqa: E402
from ui.app import RateLimiter, build  # noqa: E402
from ui.theme import CSS, HEAD, THEME  # noqa: E402

engine = DecisionEngine(extractor=MockExtractor())
limiter = RateLimiter(int(os.getenv("DE_RATE_LIMIT_PER_HOUR", "30")))
api = FastAPI(title="The Decision Engine API", version="0.1.0",
              description="POST a proposed agent action, get back execute | ask | defer | escalate | refuse.")


class Resolution(BaseModel):
    reviewer: str
    verdict: str
    note: str = ""


@api.get("/api/health")
def health():
    ok, bad, n = engine.audit.verify()
    return {"status": "ok", "audit_chain_ok": ok, "records": n, "domains": sorted(engine.policies)}


@api.post("/api/decide", response_model=Decision)
def decide(p: ActionProposal, request: Request, llm: bool = False):
    """Decide on a proposal. `?llm=true` uses a real LLM extractor (rate-limited per IP)."""
    if llm and limiter.allow(request.client.host if request.client else "anon"):
        from decision_engine.llm.client import make_extractor
        return _decide_with(p, make_extractor())
    return engine.decide(p)


def _decide_with(p: ActionProposal, extractor) -> Decision:
    d = engine.evaluate(p, extractor=extractor)
    engine.audit.append("decision", d.id, d.model_dump(mode="json"))
    return d


@api.get("/api/decisions/{decision_id}")
def get_decision(decision_id: str):
    recs = engine.audit.get(decision_id)
    if not recs:
        raise HTTPException(404, "unknown decision")
    return [r.model_dump() for r in recs]


@api.post("/api/decisions/{decision_id}/replay")
def replay(decision_id: str):
    return engine.replay(decision_id)


@api.post("/api/decisions/{decision_id}/resolve")
def resolve(decision_id: str, body: Resolution):
    if not engine.audit.get(decision_id):
        raise HTTPException(404, "unknown decision")
    return engine.resolve(decision_id, body.reviewer, body.verdict, body.note)


@api.get("/api/audit/verify")
def verify():
    ok, bad, n = engine.audit.verify()
    return {"ok": ok, "first_bad_seq": bad, "records": n}


@api.get("/api/scenarios")
def scenarios():
    return load_scenarios()


app = gr.mount_gradio_app(api, build(engine, limiter), path="/", theme=THEME, css=CSS, head=HEAD,
                          footer_links=["api"])

if __name__ == "__main__":
    uvicorn.run(app, host=os.getenv("HOST", "0.0.0.0"), port=int(os.getenv("PORT", "7860")))
