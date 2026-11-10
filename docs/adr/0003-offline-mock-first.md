# ADR 0003: Offline mock extractor is the default; real LLMs are opt-in

Status: accepted · 2026-11-10

## Decision
`MockExtractor` (three deterministic keyword/regex readers over EN, Gulf Arabic, Arabizi and Arabic-Indic digits)
is the default everywhere. Their agreement is the self-consistency signal. With keys in `.env`, `LLMExtractor` runs
N samples on Groq → Gemini → OpenRouter (OpenAI-compatible endpoints) and falls back to the mock on any error.

## Why
Judges must run it from a clean clone with no keys; evals must be deterministic; the public demo must not burn
free-tier quotas (real-LLM calls are rate-limited per IP).

## Consequences
Mock mode has blind spots for phrasings outside its vocabulary. They fail safe: intent `unknown` lowers
confidence and leads to escalation.
