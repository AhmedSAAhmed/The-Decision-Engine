# ADR 0002: Hash-chained audit log in SQLite

Status: accepted · 2026-11-10

## Decision
One append-only SQLite table. Each row stores the full decision payload plus `prev_hash` and
`hash = sha256(prev_hash ‖ canonical_json(payload))`. Human verdicts go into the same chain.

## Why
Zero-ops (one file, standard library) and enough to show tamper evidence. The extraction samples are stored
so `replay()` is deterministic even for LLM-based decisions.

## Limits
Tamper-*evident*, not tamper-*proof*: someone with write access can rewrite the whole chain. Production would anchor
the head hash externally (WORM storage, a transparency log, or a periodic signed checkpoint).
