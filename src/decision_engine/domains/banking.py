"""Gulf Pearl Bank: card blocks, transaction disputes, and the money-movement requests
an AI agent must never perform from a chat."""
from __future__ import annotations

from ..models import Evidence
from ..policy.spec import Rule
from .base import Check, Ctx, Domain, register_common


def build(record: dict) -> Domain:
    d = Domain(
        id="banking",
        title="Gulf Pearl Bank · cards & disputes",
        record=record,
        id_pattern=r"T-\d{4}|(?<!\d)\d{4}(?!\d)",
        intent_keywords={
            "card_lost": ["lost my card", "card stolen", "block my card", "freeze", "stolen", "block",
                          "ضاعت بطاقتي", "انسرقت", "اوقف البطاقة", "وقف البطاقة", "سكر البطاقة", "block el card"],
            "dispute": ["didn't make", "did not make", "don't recognise", "don't recognize", "unknown charge", "dispute",
                        "never received", "fraud", "ما سويت", "عملية غريبة", "اعتراض", "ما اعرف هالعملية"],
            "transfer": ["transfer", "send money", "wire", "iban", "حول", "تحويل", "ارسل فلوس"],
            "limit_change": ["raise my limit", "increase limit", "transfer limit", "رفع الحد", "زيادة الحد"],
        },
        evidence_questions={
            "card_belongs_to_customer": ("Which card is it? Please tell me the last 4 digits.",
                                         "أي بطاقة؟ عطني آخر ٤ أرقام."),
            "txn_exists": ("Which transaction is it? The merchant name and date help me find it.",
                           "أي عملية؟ اسم التاجر والتاريخ يساعدوني ألقاها."),
        },
    )
    register_common(d)

    def txn(ctx: Ctx):
        return ctx.record["transactions"].get(str(ctx.p.get("txn_id", "")))

    @d.ev("card_belongs_to_customer")
    def _(ctx: Ctx) -> Evidence:
        c = ctx.record["cards"].get(str(ctx.p.get("card_last4", "")))
        ok = bool(c and c["customer_id"] == ctx.proposal.customer_id)
        return Evidence(key="card_belongs_to_customer", description="Card belongs to this customer", verified=ok,
                        detail=f"card ****{ctx.p.get('card_last4', '—')} " + ("matches" if ok else "not on this customer"),
                        askable=True)

    @d.ev("txn_exists")
    def _(ctx: Ctx) -> Evidence:
        t = txn(ctx)
        return Evidence(key="txn_exists", description="Transaction exists", verified=t is not None,
                        detail=f"{ctx.p.get('txn_id')}: {t['merchant']} {t['amount']} BHD" if t else "not found", askable=True)

    @d.ev("txn_belongs_to_customer")
    def _(ctx: Ctx) -> Evidence:
        t = txn(ctx)
        ok = bool(t and t["customer_id"] == ctx.proposal.customer_id)
        return Evidence(key="txn_belongs_to_customer", description="Transaction is on this customer's card", verified=ok,
                        detail=f"owner {t['customer_id'] if t else '—'}")

    @d.ev("amount_matches_txn")
    def _(ctx: Ctx) -> Evidence:
        t = txn(ctx)
        ok = bool(t and abs(ctx.num("amount") - t["amount"]) < 0.001)
        return Evidence(key="amount_matches_txn", description="Disputed amount equals the transaction amount", verified=ok,
                        detail=f"{ctx.num('amount'):g} vs {t['amount'] if t else '—'}")

    @d.ev("not_already_disputed")
    def _(ctx: Ctx) -> Evidence:
        t = txn(ctx)
        ok = bool(t) and not t["disputed"]
        return Evidence(key="not_already_disputed", description="No open dispute on this transaction", verified=ok,
                        detail="already disputed" if t and t["disputed"] else "none open")

    @d.check("outside_dispute_window")
    def _(ctx: Ctx, r: Rule) -> Check:
        t = txn(ctx)
        if not t:
            return Check(False, "no transaction")
        age, win = ctx.days_since(t["date"]), ctx.record["dispute_window_days"]
        return Check(age > win, f"{age} days old, scheme window {win} days")

    @d.check("txn_pending")
    def _(ctx: Ctx, r: Rule) -> Check:
        t = txn(ctx)
        return Check(bool(t and t["status"] == "pending"), f"status {t['status'] if t else '—'}")

    @d.check("customer_watchlisted")
    def _(ctx: Ctx, r: Rule) -> Check:
        c = ctx.record["customers"].get(ctx.proposal.customer_id, {})
        return Check(bool(c.get("risk_flag")), f"risk flag: {c.get('risk_flag') or 'none'}")

    @d.check("always")
    def _(ctx: Ctx, r: Rule) -> Check:
        return Check(True, r.reason)

    return d
