"""Nahla Telecom: plan changes, outage credits, SIM swaps and record disclosure."""
from __future__ import annotations

from ..models import Evidence
from ..policy.spec import Rule
from .base import Check, Ctx, Domain, register_common, threshold_check


def build(record: dict) -> Domain:
    d = Domain(
        id="telecom",
        title="Nahla Telecom · account actions",
        record=record,
        id_pattern=r"(?<!\d)3\d{7}(?!\d)",
        intent_keywords={
            "plan_change": ["upgrade", "change my plan", "switch plan", "new plan", "unlimited", "downgrade",
                            "غير الباقة", "تغيير الباقة", "باقة", "ابي باقة", "baga"],
            "outage_credit": ["no signal", "network down", "outage", "no internet", "compensation", "credit",
                              "ما في شبكة", "انقطاع", "الشبكة طايحة", "تعويض", "ma fi network"],
            "sim_swap": ["new sim", "lost my phone", "replace sim", "sim swap", "phone stolen", "esim",
                         "شريحة جديدة", "ضاع تلفوني", "انسرق تلفوني", "بدل الشريحة", "shareeha"],
            "records_request": ["call records", "call history", "who called", "messages log", "سجل المكالمات", "كشف المكالمات"],
        },
        evidence_questions={
            "identity_verified": ("For your security, please reply with the code we just sent to your registered number, "
                                  "or visit any Nahla branch with your CPR card.",
                                  "لحمايتك، أرسل الرمز اللي وصلك على رقمك المسجل، أو زور أي فرع لنحلة مع بطاقتك السكانية."),
            "fee_acknowledged": ("Your contract has an early-change fee. Do you want to continue?",
                                 "عقدك فيه رسوم تغيير مبكر. تبي تكمل؟"),
        },
    )
    register_common(d)

    def sub(ctx: Ctx):
        return ctx.record["subscribers"].get(str(ctx.p.get("msisdn", "")))

    @d.ev("subscriber_exists")
    def _(ctx: Ctx) -> Evidence:
        s = sub(ctx)
        return Evidence(key="subscriber_exists", description="Number is an active Nahla line", verified=s is not None,
                        detail=f"{ctx.p.get('msisdn')} {'found' if s else 'not found'}", askable=True)

    @d.ev("requester_is_holder")
    def _(ctx: Ctx) -> Evidence:
        s = sub(ctx)
        ok = bool(s and s["holder_id"] == ctx.proposal.customer_id)
        return Evidence(key="requester_is_holder", description="Requester is the account holder", verified=ok,
                        detail=f"holder {s['holder_id'] if s else '—'} vs requester {ctx.proposal.customer_id}")

    @d.ev("identity_verified")
    def _(ctx: Ctx) -> Evidence:
        v = ctx.record["verifications"].get(str(ctx.p.get("msisdn", "")))
        ok = bool(v and v["method"] in ("branch_id_check", "otp_registered_number") and v["date"] == ctx.today.isoformat())
        return Evidence(key="identity_verified", description="Identity verified today (branch ID check or OTP)",
                        verified=ok, detail=f"{v['method']} by {v['by']}" if v else "no verification on record today",
                        askable=True)

    @d.ev("no_recent_swap")
    def _(ctx: Ctx) -> Evidence:
        s = sub(ctx)
        n = s["sim_swaps_90d"] if s else 0
        return Evidence(key="no_recent_swap", description="No SIM swap in the last 90 days", verified=bool(s) and n == 0,
                        detail=f"{n} swap(s) in 90 days")

    @d.ev("no_port_out_pending")
    def _(ctx: Ctx) -> Evidence:
        s = sub(ctx)
        ok = bool(s) and not s["port_out_pending"]
        return Evidence(key="no_port_out_pending", description="No pending port-out to another operator", verified=ok,
                        detail="port-out pending" if s and s["port_out_pending"] else "none")

    @d.ev("plan_exists")
    def _(ctx: Ctx) -> Evidence:
        plan = ctx.p.get("new_plan")
        return Evidence(key="plan_exists", description="Requested plan is in the catalogue",
                        verified=plan in ctx.record["plans"], detail=str(plan))

    @d.ev("fee_acknowledged")
    def _(ctx: Ctx) -> Evidence:
        s = sub(ctx)
        locked = bool(s and s["contract_locked_until"] and s["contract_locked_until"] > ctx.today.isoformat())
        ok = not locked or bool(ctx.p.get("fee_acknowledged"))
        return Evidence(key="fee_acknowledged", description="No contract lock, or customer accepted the change fee",
                        verified=ok, detail=f"locked until {s['contract_locked_until']}" if locked else "no lock",
                        askable=True)

    @d.ev("outage_in_area")
    def _(ctx: Ctx) -> Evidence:
        s = sub(ctx)
        win = ctx.record["credit_formula"]["window_days"]
        hits = [o for o in ctx.record["outages"] if s and o["area"] == s["area"] and ctx.days_since(o["start"]) <= win]
        return Evidence(key="outage_in_area", description=f"Logged outage in the customer's area (last {win} days)",
                        verified=bool(hits), detail=", ".join(f"{o['id']} {o['hours']}h" for o in hits) or
                        f"no outage logged for {s['area'] if s else '—'}")

    @d.ev("amount_within_formula")
    def _(ctx: Ctx) -> Evidence:
        cap = _formula_cap(ctx)
        amt = ctx.num("amount")
        return Evidence(key="amount_within_formula", description="Credit ≤ 0.5 BHD per outage hour",
                        verified=0 < amt <= cap + 1e-9, detail=f"{amt:g} vs entitled {cap:g}")

    @d.ev("no_credit_this_month")
    def _(ctx: Ctx) -> Evidence:
        prior = [c for c in ctx.record["credits"].get(str(ctx.p.get("msisdn", "")), []) if ctx.days_since(c["date"]) <= 30]
        return Evidence(key="no_credit_this_month", description="No goodwill credit in the last 30 days", verified=not prior,
                        detail=f"{len(prior)} credit(s) in 30 days")

    def _formula_cap(ctx: Ctx) -> float:
        s = sub(ctx)
        f = ctx.record["credit_formula"]
        hours = sum(o["hours"] for o in ctx.record["outages"]
                    if s and o["area"] == s["area"] and ctx.days_since(o["start"]) <= f["window_days"])
        return hours * f["per_outage_hour"]

    @d.check("requester_not_holder")
    def _(ctx: Ctx, r: Rule) -> Check:
        s = sub(ctx)
        return Check(bool(s) and s["holder_id"] != ctx.proposal.customer_id,
                     f"line belongs to {s['holder_id'] if s else '—'}, requester is {ctx.proposal.customer_id}")

    @d.check("plan_change_pending")
    def _(ctx: Ctx, r: Rule) -> Check:
        s = sub(ctx)
        pend = s and s["pending_plan_change"]
        return Check(bool(pend), f"change to {pend['to']} already scheduled for {pend['effective']}" if pend else "none")

    @d.check("swap_fraud_pattern")
    def _(ctx: Ctx, r: Rule) -> Check:
        s = sub(ctx)
        hit = bool(s and (s["sim_swaps_90d"] >= 1 or s["port_out_pending"]))
        return Check(hit, f"{s['sim_swaps_90d']} swaps/90d, port-out pending={s['port_out_pending']}" if s else "—")

    @d.check("credit_over_formula")
    def _(ctx: Ctx, r: Rule) -> Check:
        return threshold_check(ctx.num("amount"), max(_formula_cap(ctx), 0.001), "credit vs entitlement")

    return d
