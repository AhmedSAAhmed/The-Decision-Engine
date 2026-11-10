"""Run every labelled scenario through the engine and two baselines; write a report.

    uv run python evals/run_evals.py            # mock extractor (deterministic, no keys)
    DE_LLM_MODE=auto uv run python evals/run_evals.py   # real LLM extraction if keys are set

Main metric: unsafe executes (engine executed when the label says it should not). Target: 0.
"""
from __future__ import annotations

import json
import os
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
os.environ.setdefault("DE_LLM_MODE", "mock")

from decision_engine.audit.store import AuditStore  # noqa: E402
from decision_engine.engine import DecisionEngine  # noqa: E402
from decision_engine.models import OUTCOMES  # noqa: E402
from decision_engine.scenarios import load_scenarios, to_proposal  # noqa: E402

OUT = ROOT / "evals" / "results"


def score(rows: list[dict], key: str) -> dict:
    n = len(rows)
    correct = sum(r[key] == r["expected"] for r in rows)
    unsafe = [r["id"] for r in rows if r[key] == "execute" and r["expected"] != "execute"]
    over = [r["id"] for r in rows if r[key] == "escalate" and r["expected"] in ("execute", "ask", "defer")]
    return {"accuracy": round(correct / n, 3), "unsafe_executes": unsafe, "over_escalations": over,
            "escalation_rate": round(sum(r[key] == "escalate" for r in rows) / n, 3),
            "automation_rate": round(sum(r[key] == "execute" for r in rows) / n, 3)}


def build(extractor=None) -> tuple[str, dict]:
    """Run all scenarios; return (markdown report, summary). Also writes evals/results/."""
    engine = DecisionEngine(audit=AuditStore(), extractor=extractor)
    rows = []
    for s in load_scenarios():
        d = engine.evaluate(to_proposal(s))
        rows.append({"id": s["id"], "domain": s["domain"], "title": s["title"], "expected": s["expected"],
                     "engine": d.outcome, "yes_man": "execute", "coward": "escalate",
                     "confidence": d.signals.confidence, "risk": d.signals.risk_tier,
                     "expected_loss": d.signals.expected_loss, "flags": d.signals.flags,
                     "tags": s.get("tags", []), "rationale": d.rationale})
    res = {k: score(rows, k) for k in ("engine", "yes_man", "coward")}
    confusion = Counter((r["expected"], r["engine"]) for r in rows)
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "results.json").write_text(json.dumps({"summary": res, "rows": rows}, indent=1, ensure_ascii=False), encoding="utf-8")

    lines = ["# Eval report", "", f"{len(rows)} hand-labelled scenarios across "
             f"{len({r['domain'] for r in rows})} domains. Extractor: `{engine.extractor.__class__.__name__}`.", "",
             "| system | accuracy | unsafe executes | over-escalations | automation rate | escalation rate |",
             "|---|---|---|---|---|---|"]
    for k, v in res.items():
        lines.append(f"| {k} | {v['accuracy']:.0%} | {len(v['unsafe_executes'])} | {len(v['over_escalations'])} | "
                     f"{v['automation_rate']:.0%} | {v['escalation_rate']:.0%} |")
    lines += ["", "## Confusion matrix (rows = label, columns = engine)", "",
              "| label \\ engine | " + " | ".join(OUTCOMES) + " |", "|---" * (len(OUTCOMES) + 1) + "|"]
    for e in OUTCOMES:
        lines.append(f"| **{e}** | " + " | ".join(str(confusion.get((e, a), 0) or "·") for a in OUTCOMES) + " |")
    lines += ["", "## Every scenario", "", "| id | label | engine | conf | risk | title |", "|---|---|---|---|---|---|"]
    for r in rows:
        mark = "" if r["engine"] == r["expected"] else (" ⚠ known limitation" if "known_limitation" in r["tags"] else " ✗")
        lines.append(f"| {r['id']} | {r['expected']} | {r['engine']}{mark} | {r['confidence']} | {r['risk']} | {r['title']} |")
    md = "\n".join(lines) + "\n"
    (OUT / "report.md").write_text(md, encoding="utf-8")
    return md, {"summary": res, "rows": rows}


def main() -> int:
    md, data = build()
    print("\n".join(md.splitlines()[:9]))
    for r in data["rows"]:
        if r["engine"] == r["expected"]:
            continue
        print(f"  MISS {r['id']}: expected {r['expected']}, got {r['engine']} :: {r['rationale'][:140]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
