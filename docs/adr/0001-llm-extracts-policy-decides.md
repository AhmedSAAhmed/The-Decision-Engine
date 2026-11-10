# ADR 0001: The LLM extracts signals; deterministic policy decides

Status: accepted · 2026-11-10

## Context
The challenge asks when an AI system is *allowed* to act. If an LLM decides, the decision inherits every
weakness of the LLM: prompt injection, overconfidence, non-determinism, and no audit trail beyond a transcript.

## Decision
The LLM (or the offline extractor) only returns structured *claims* from untrusted text. Claims become evidence
only after verification against the system of record. The outcome comes from ordered gates in
`policy/engine.py` over numeric signals and versioned YAML policies.

## Alternatives considered
- LLM-as-judge returning the outcome: rejected. It can't be audited or replayed, and it's injectable.
- Pure rules, no LLM: rejected. Can't read Gulf Arabic, Arabizi or messy multi-turn chats. Kept as the offline fallback.

## Consequences
Decisions are reproducible and explainable, and an injection can only lower trust. The cost is that every new
action needs explicit evidence checks in a domain module.
