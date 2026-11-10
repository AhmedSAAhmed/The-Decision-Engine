"""LLM extraction over OpenAI-compatible endpoints (Groq, Gemini, OpenRouter), with N-sample
self-consistency and a guaranteed fallback to the offline mock extractor.

The LLM only reads the conversation. It never sees the policy thresholds and never returns
an outcome, so a prompt injection can at most distort *claims*, which are then checked
against the system of record.
"""
from __future__ import annotations

import json
import os
import re
from collections import Counter
from pathlib import Path

import httpx
from dotenv import load_dotenv

from ..models import ActionProposal, Extraction, ExtractionRun
from .mock import MockExtractor, _any, INJECTION_PATTERNS, _norm

load_dotenv()

PROMPT = (Path(__file__).parent / "prompts" / "extract.md").read_text(encoding="utf-8")

PROVIDERS = [
    # name, base url, key env, model env, default model
    ("groq", "https://api.groq.com/openai/v1", "GROQ_API_KEY", "GROQ_MODEL", "openai/gpt-oss-120b"),
    ("gemini", "https://generativelanguage.googleapis.com/v1beta/openai", "GEMINI_API_KEY", "GEMINI_MODEL", "gemini-2.5-flash"),
    ("openrouter", "https://openrouter.ai/api/v1", "OPENROUTER_API_KEY", "OPENROUTER_MODEL", "openai/gpt-oss-20b:free"),
]


def _clean_key(v: str | None) -> str:
    # keys pasted from docs often carry smart quotes or whitespace
    return (v or "").strip().strip("\"'“”‘’ ")


def available_providers() -> list[tuple[str, str, str, str]]:
    out = []
    for name, url, key_env, model_env, default in PROVIDERS:
        key = _clean_key(os.getenv(key_env))
        if key and key.isascii():
            out.append((name, url, key, os.getenv(model_env) or default))
    return out


def _parse(text: str) -> Extraction:
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        raise ValueError("no JSON object in reply")
    return Extraction.model_validate(json.loads(m.group(0)))


class LLMExtractor:
    def __init__(self, samples: int | None = None, timeout: float = 20.0):
        self.samples = samples or int(os.getenv("DE_LLM_SAMPLES", "3"))
        self.timeout = timeout
        self.fallback = MockExtractor()
        self.provider, self.model = "mock", MockExtractor.model

    def _call(self, url: str, key: str, model: str, convo: str, intents: list[str]) -> Extraction:
        body = {
            "model": model,
            "temperature": 0.7,
            "messages": [
                {"role": "system", "content": PROMPT.replace("{intents}", ", ".join(intents))},
                {"role": "user", "content": f"<untrusted_conversation>\n{convo}\n</untrusted_conversation>"},
            ],
        }
        r = httpx.post(f"{url}/chat/completions", json=body, timeout=self.timeout,
                       headers={"Authorization": f"Bearer {key}"})
        r.raise_for_status()
        return _parse(r.json()["choices"][0]["message"]["content"])

    def extract(self, proposal: ActionProposal, keywords: dict[str, list[str]], id_pattern: str) -> ExtractionRun:
        convo = "\n".join(f"[{m.role}/{m.channel}] {m.text}" for m in proposal.conversation)
        errors: list[str] = []
        for name, url, key, model in available_providers():
            samples: list[Extraction] = []
            try:
                for _ in range(self.samples):
                    samples.append(self._call(url, key, model, convo, list(keywords) + ["other"]))
            except Exception as e:  # noqa: BLE001 - any provider failure falls through to the next
                errors.append(f"{name}: {type(e).__name__}: {str(e)[:120]}")
                if not samples:
                    continue
            # defence in depth: deterministic injection scan is OR-ed with the model's opinion
            heuristic = bool(_any(INJECTION_PATTERNS, _norm(convo)))
            votes = Counter(s.intent for s in samples)
            intent, n = votes.most_common(1)[0]
            ids = Counter(tuple(sorted(s.ids_mentioned)) for s in samples).most_common(1)[0][1]
            agreement = round(0.7 * n / len(samples) + 0.3 * ids / len(samples), 3)
            consensus = next(s for s in samples if s.intent == intent).model_copy()
            consensus.instructions_to_system = consensus.instructions_to_system or heuristic
            consensus.authority_claims = sorted({c for s in samples for c in s.authority_claims})
            return ExtractionRun(provider=name, model=model, samples=[consensus, *samples], agreement=agreement, errors=errors)
        run = self.fallback.extract(proposal, keywords, id_pattern)
        run.errors = errors + run.errors
        return run


def make_extractor():
    mode = os.getenv("DE_LLM_MODE", "auto").lower()
    if mode == "mock" or not available_providers():
        return MockExtractor()
    return LLMExtractor()
