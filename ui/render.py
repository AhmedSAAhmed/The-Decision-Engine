"""HTML renderers for decisions, audit rows and evals. Every piece of user text is escaped."""
from __future__ import annotations

from html import escape as e

from decision_engine.models import AuditRecord, Decision

HEADLINES = {
    "execute": "Allowed to act alone",
    "ask": "Needs one more answer from the customer",
    "defer": "Not yet. Waiting on a condition",
    "escalate": "A person should decide",
    "refuse": "Not allowed, whoever asks",
}


def outcome_card(d: Decision) -> str:
    s = d.signals
    cur = "BHD"
    ev_ok = sum(x.verified for x in s.evidence)
    cells = [
        ("Confidence", f"{s.confidence:.2f}",
         " · ".join(f"{k.split('_')[0]} {v:.2f}" for k, v in s.confidence_parts.items()), s.confidence),
        ("Risk", s.risk_tier, f"score {s.risk_score:.2f}", s.risk_score),
        ("Evidence", f"{ev_ok}/{len(s.evidence)}", "verified against system of record", (ev_ok / len(s.evidence)) if s.evidence else 1),
        ("Missing", str(len(s.missing)), ", ".join(s.missing) or "nothing", None),
        ("Reversibility", s.reversibility, f"expected loss {s.expected_loss:g} {cur} · impact {s.impact_if_wrong:g}", None),
    ]
    grid = "".join(
        f"<div><div class='k'>{k}</div><div class='v'>{e(v)}</div><div class='s'>{e(sub)}</div>"
        + (f"<div class='de-bar'><i style='width:{max(0, min(1, bar)) * 100:.0f}%'></i></div>" if bar is not None else "")
        + "</div>" for k, v, sub, bar in cells)
    flags = "".join(f"<span class='de-chip warn'>{e(f)}</span>" for f in s.flags)
    qs = "".join(f"<li>{e(q)}</li>" for q in d.questions)
    return f"""
<div class='de-outcome'>
  <span class='de-badge de-{d.outcome}'>{d.outcome}</span>
  <h2>{HEADLINES[d.outcome]}</h2>
  <p class='next'><b>Next step:</b> {e(d.next_step)}</p>
  {f"<ul class='next'>{qs}</ul>" if qs else ""}
  {f"<div style='margin-top:10px'>{flags}</div>" if flags else ""}
</div>
<div class='de-grid'>{grid}</div>"""


def gate_timeline(d: Decision) -> str:
    winner = d.outcome
    items = []
    for i, g in enumerate(d.gate_trace, 1):
        state = "fired" if g.matched else "not met"
        if g.matched and g.gate != winner:
            state = "fired (lower priority)"
        reasons = "<br>".join(e(r) for r in g.reasons) or "no condition met"
        items.append(f"<li class='{'hit' if g.gate == winner else ''}'><span class='t'>0{i}</span>"
                     f"<span class='g'>{g.gate}</span> · <span class='t'>{state}</span><div class='r'>{reasons}</div></li>")
    items.append(f"<li class='hit'><span class='t'>✓</span><span class='g'>Logged</span>"
                 f"<div class='r'>{e(d.id)} · policy {e(d.policy_id)} v{e(d.policy_version)} · sha256 {e(d.policy_hash[:12])}…</div></li>")
    return "<p class='de-eyebrow'>/// Gate trace</p><ul class='de-timeline'>" + "".join(items) + "</ul>"


def evidence_table(d: Decision) -> str:
    rows = "".join(
        f"<tr><td>{e(x.description)}</td><td>{e(x.source.replace('_', ' '))}</td>"
        f"<td class='{'de-yes' if x.verified else 'de-no'}'>{'verified' if x.verified else 'not verified'}</td>"
        f"<td>{e(x.detail)}</td></tr>" for x in d.signals.evidence)
    risk = "".join(f"<span class='de-chip'>{e(r)}</span>" for r in d.signals.risk_factors) or "<span class='de-chip'>none</span>"
    ex = d.signals.extraction
    exs = (f"<p class='de-eyebrow' style='margin-top:18px'>/// Extraction (untrusted)</p>"
           f"<table class='de-table'><tr><th>reader</th><th>intent</th><th>language</th><th>agreement</th><th>notes</th></tr>"
           f"<tr><td>{e(ex.provider)} · {e(ex.model)}</td><td>{e(ex.consensus.intent)}</td><td>{e(ex.consensus.language)}</td>"
           f"<td>{ex.agreement:.2f} over {len(ex.samples)} samples</td><td>{e('; '.join(ex.errors)[:200]) or '—'}</td></tr></table>"
           ) if ex else ""
    return (f"<p class='de-eyebrow'>/// Evidence</p><table class='de-table'><tr><th>check</th><th>source</th>"
            f"<th>result</th><th>detail</th></tr>{rows}</table>"
            f"<p class='de-eyebrow' style='margin-top:18px'>/// Risk factors</p>{risk}{exs}")


def audit_table(rows: list[AuditRecord]) -> str:
    body = []
    for r in rows:
        p = r.payload
        what = (f"{p['proposal']['domain']} · {p['proposal']['action']} → <b>{p['outcome']}</b>" if r.kind == "decision"
                else f"human {e(p['verdict'])} by {e(p['reviewer'])}: {e(p.get('note', ''))}")
        body.append(f"<tr><td>{r.seq}</td><td>{e(r.kind)}</td><td>{e(r.ref_id)}</td><td>{what}</td>"
                    f"<td><code>{r.prev_hash[:10]}…</code></td><td><code>{r.hash[:10]}…</code></td></tr>")
    if not body:
        body = ["<tr><td colspan=6>No records yet. Make a decision first.</td></tr>"]
    return ("<table class='de-table'><tr><th>seq</th><th>kind</th><th>ref</th><th>event</th><th>prev hash</th>"
            "<th>hash</th></tr>" + "".join(body) + "</table>")


def queue_table(items: list[Decision]) -> str:
    if not items:
        return "<p class='de-eyebrow'>Queue is empty. Every ask/escalate has a human verdict.</p>"
    rows = "".join(f"<tr><td>{e(d.id)}</td><td><span class='de-badge de-{d.outcome}'>{d.outcome}</span></td>"
                   f"<td>{e(d.proposal.domain)} · {e(d.proposal.action)}</td><td>{e(d.route_to or '—')}</td>"
                   f"<td>{e(d.rationale[:160])}</td></tr>" for d in items)
    return ("<table class='de-table'><tr><th>decision</th><th>outcome</th><th>action</th><th>route</th>"
            "<th>why</th></tr>" + rows + "</table>")
