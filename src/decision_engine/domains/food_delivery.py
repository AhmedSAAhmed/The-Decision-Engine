"""Sufra Delivery: refunds and missing-item redelivery for a GCC food-delivery app."""
from __future__ import annotations

from ..models import Evidence
from ..policy.spec import Rule
from .base import Check, Ctx, Domain, register_common, threshold_check


def build(record: dict) -> Domain:
    d = Domain(
        id="food_delivery",
        title="Sufra Delivery · refunds & order fixes",
        record=record,
        id_pattern=r"(?<![\d.\-])\d{4,5}(?![\d.])",  # skips APR-1182 style refs
        intent_keywords={
            "double_charge": ["charged twice", "double charge", "charged me twice", "two charges", "deducted twice",
                              "انخصم مرتين", "خصم مرتين", "مرتين", "ankhasam marten", "marten"],
            "missing_item": ["missing", "didn't get", "did not get", "not in the bag", "incomplete", "forgot",
                             "ناقص", "نقص", "ما وصل", "nagis", "naqis", "ma wasal"],
            "damaged": ["damaged", "spilled", "cold", "crushed", "خربان", "منسكب", "بارد"],
            "late_delivery": ["late", "hours", "still waiting", "متأخر", "تأخر", "ta5ar"],
            "order_status": ["where is my order", "when will", "on the way", "eta", "وين الطلب", "متى يوصل", "wain el order"],
            "refund_request": ["refund", "money back", "استرجاع", "ارجاع", "رجعوا", "refund please"],
        },
        evidence_questions={
            "order_exists": ("Could you share your order number? It starts with # in the app.",
                             "ممكن ترسل لي رقم الطلب؟ تلقاه في التطبيق."),
            "photo_provided": ("Could you send a photo of the item as it arrived?",
                               "ممكن ترسل صورة للطلب مثل ما وصلك؟"),
        },
    )
    register_common(d)

    def order(ctx: Ctx):
        return ctx.record["orders"].get(str(ctx.p.get("order_id", "")))

    # ------------------------------------------------------------ evidence
    @d.ev("order_exists")
    def _(ctx: Ctx) -> Evidence:
        o = order(ctx)
        return Evidence(key="order_exists", description="Order exists in Sufra order system", verified=o is not None,
                        detail=f"order {ctx.p.get('order_id')} {'found' if o else 'not found'}", askable=True)

    @d.ev("order_belongs_to_customer")
    def _(ctx: Ctx) -> Evidence:
        o = order(ctx)
        ok = bool(o and o["customer_id"] == ctx.proposal.customer_id)
        return Evidence(key="order_belongs_to_customer", description="Order belongs to the customer in this conversation",
                        verified=ok, detail=f"owner {o['customer_id'] if o else '—'} vs {ctx.proposal.customer_id}")

    @d.ev("amount_within_order")
    def _(ctx: Ctx) -> Evidence:
        o = order(ctx)
        amt = ctx.num("amount")
        ok = bool(o and 0 < amt <= o["total"] + 1e-9)
        return Evidence(key="amount_within_order", description="Refund amount ≤ order total", verified=ok,
                        detail=f"{amt:g} vs order total {o['total'] if o else '—'}")

    @d.ev("issue_supported")
    def _(ctx: Ctx) -> Evidence:
        o = order(ctx)
        reason = str(ctx.p.get("reason", ""))
        ok, why = False, "no record supports the complaint"
        if o:
            if reason == "double_charge":
                ch = ctx.record["charges"].get(str(ctx.p["order_id"]), [])
                ok = len(ch) >= 2
                why = f"{len(ch)} charge(s) on file: " + ", ".join(f"{c['amount']} {c['status']}" for c in ch)
            elif reason == "missing_item":
                miss = o["delivery_log"]["missing_items"]
                ok = bool(miss)
                why = f"delivery log missing items: {miss or 'none'}; photo proof: {o['delivery_log']['photo_proof']}"
            elif reason in ("damaged", "late_delivery"):
                ok = bool(ctx.p.get("photo_provided")) or reason == "late_delivery" and o["status"] == "delivered"
                why = "customer photo attached" if ctx.p.get("photo_provided") else "no photo on file"
        return Evidence(key="issue_supported", description="System of record supports the complaint", verified=ok, detail=why)

    @d.ev("no_prior_refund")
    def _(ctx: Ctx) -> Evidence:
        prior = ctx.record["refunds"].get(str(ctx.p.get("order_id", "")), [])
        return Evidence(key="no_prior_refund", description="Order not already refunded", verified=not prior,
                        detail=f"{len(prior)} prior refund(s)" + (f": {prior[0]['id']}" if prior else ""))

    @d.ev("item_in_order")
    def _(ctx: Ctx) -> Evidence:
        o = order(ctx)
        item = str(ctx.p.get("item", "")).lower()
        ok = bool(o and any(i["name"].lower() == item for i in o["items"]))
        return Evidence(key="item_in_order", description="Item is part of the order", verified=ok, detail=item or "no item named")

    @d.ev("item_missing_in_log")
    def _(ctx: Ctx) -> Evidence:
        o = order(ctx)
        item = str(ctx.p.get("item", "")).lower()
        ok = bool(o and item in [m.lower() for m in o["delivery_log"]["missing_items"]])
        return Evidence(key="item_missing_in_log", description="Rider's delivery log confirms the item was missing",
                        verified=ok, detail=f"log: {o['delivery_log']['missing_items'] if o else '—'}")

    # ------------------------------------------------------------ rules
    @d.check("destination_mismatch")
    def _(ctx: Ctx, r: Rule) -> Check:
        o = order(ctx)
        dest = str(ctx.p.get("destination_last4", "") or "")
        if not o or not dest:
            return Check(False, "refund goes to original payment method")
        return Check(dest != o["payment"]["last4"], f"destination ****{dest} vs original ****{o['payment']['last4']}")

    @d.check("amount_exceeds_order")
    def _(ctx: Ctx, r: Rule) -> Check:
        o = order(ctx)
        if not o:
            return Check(False, "no order to compare")
        return threshold_check(ctx.num("amount"), o["total"], "amount vs order total", hard=True)

    @d.check("charge_pending")
    def _(ctx: Ctx, r: Rule) -> Check:
        ch = ctx.record["charges"].get(str(ctx.p.get("order_id", "")), [])
        pend = [c for c in ch if c["status"] == "pending"]
        return Check(bool(pend) and ctx.p.get("reason") == "double_charge",
                     f"{len(pend)} pending authorisation(s): {', '.join(c['id'] for c in pend) or 'none'}")

    @d.check("order_in_transit")
    def _(ctx: Ctx, r: Rule) -> Check:
        o = order(ctx)
        return Check(bool(o and o["status"] == "out_for_delivery"), f"status {o['status'] if o else '—'}")

    @d.check("refund_abuse")
    def _(ctx: Ctx, r: Rule) -> Check:
        c = ctx.record["customers"].get(ctx.proposal.customer_id, {})
        n = c.get("refunds_30d", 0)
        return Check(n >= (r.value or 3), f"{n} refunds in last 30 days", None)

    @d.check("new_customer")
    def _(ctx: Ctx, r: Rule) -> Check:
        c = ctx.record["customers"].get(ctx.proposal.customer_id)
        if not c:
            return Check(True, "customer unknown")
        days = ctx.days_since(c["joined"])
        return Check(days < (r.value or 30), f"customer for {days} days")

    return d
