"""Offline extractor: three deterministic readers over the same untrusted conversation.

Their agreement is the self-consistency signal in mock mode, exactly as N LLM samples are in
real mode. Handles English, Gulf Arabic, Arabizi and Arabic-Indic digits.
"""
from __future__ import annotations

import re

from ..models import ActionProposal, Extraction, ExtractionRun

ARABIC_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")

INJECTION_PATTERNS = [
    r"ignore (all |your |the )?(previous|prior|above)?\s*(instructions|rules|policy|policies|limits)",
    r"\bsystem\s*:", r"admin mode", r"developer mode", r"you are now", r"override", r"bypass",
    r"تجاهل (التعليمات|السياسة|القوانين)", r"انت الحين", r"وضع المسؤول",
]
AUTHORITY_PATTERNS = [
    r"(already|has|have) (been )?approv\w*", r"manager (said|approved|agreed)", r"supervisor (said|approved|agreed)",
    r"\bapproval\b.*\b(APR-\d+|ref)", r"\bCEO\b", r"authori[sz]ed by",
    r"وافق (المدير|المشرف)", r"المدير (وافق|قال)", r"تمت الموافقة", r"موافقة",
]
URGENCY_PATTERNS = [r"\burgent\w*", r"right now", r"immediately", r"asap", r"\bnow!", r"lawyer", r"report you",
                    r"ضروري", r"بسرعة", r"الحين الحين", r"فورا"]
AMOUNT_RE = re.compile(r"(?:bhd|bd|د\.?ب|دينار)\s*(\d+(?:\.\d+)?)|(\d+(?:\.\d+)?)\s*(?:bhd|bd|د\.?ب|دينار|dinar)", re.I)


def _norm(text: str) -> str:
    return text.translate(ARABIC_DIGITS)


def detect_language(text: str) -> str:
    ar = len(re.findall(r"[؀-ۿ]", text))
    lat = len(re.findall(r"[A-Za-z]", text))
    if ar and lat:
        return "mixed"
    return "ar" if ar else "en"


def classify(text: str, keywords: dict[str, list[str]]) -> str:
    t = text.lower()
    scores = {intent: sum(t.count(k.lower()) for k in kws) for intent, kws in keywords.items()}
    best = max(scores.items(), key=lambda kv: kv[1], default=("unknown", 0))
    return best[0] if best[1] > 0 else "unknown"


def _any(patterns: list[str], text: str) -> list[str]:
    hits = []
    for p in patterns:
        m = re.search(p, text, re.I)
        if m:
            start = max(0, m.start() - 40)
            hits.append(text[start : m.end() + 40].strip())
    return hits


def read(text: str, keywords: dict[str, list[str]], id_pattern: str) -> Extraction:
    t = _norm(text)
    return Extraction(
        intent=classify(t, keywords),
        language=detect_language(text),
        ids_mentioned=sorted(set(re.findall(id_pattern, t))),
        amounts_mentioned=sorted({float(a or b) for a, b in AMOUNT_RE.findall(t)}),
        authority_claims=_any(AUTHORITY_PATTERNS, t),
        instructions_to_system=bool(_any(INJECTION_PATTERNS, t)),
        urgency_pressure=bool(_any(URGENCY_PATTERNS, t)),
        summary=t[:160],
    )


class MockExtractor:
    provider = "mock"
    model = "keyword-ensemble-v1"

    def extract(self, proposal: ActionProposal, keywords: dict[str, list[str]], id_pattern: str) -> ExtractionRun:
        msgs = [m.text for m in proposal.conversation if m.role == "customer"]
        if not msgs:
            return ExtractionRun(provider=self.provider, model=self.model, samples=[Extraction()], agreement=0.0,
                                 errors=["no customer messages"])
        full = "\n".join(msgs)
        readers = [read(full, keywords, id_pattern), read(msgs[-1], keywords, id_pattern), read(msgs[0], keywords, id_pattern)]
        # consensus = full-conversation reader; agreement = share of readers with a known intent
        # that agree with it (a bare "hi" turn neither helps nor hurts)
        consensus = readers[0]
        known = [r for r in readers if r.intent != "unknown"]
        agreement = sum(r.intent == consensus.intent for r in known) / len(known) if known else 0.0
        if consensus.intent == "unknown":
            agreement = 0.2
        return ExtractionRun(provider=self.provider, model=self.model, samples=readers, agreement=round(agreement, 3))
