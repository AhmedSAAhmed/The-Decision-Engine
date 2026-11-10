# policies/: what an AI agent may do on its own

One YAML file per business. Read at startup; the SHA-256 of each file goes into every audit record.

## Inputs
- Reference: `src/decision_engine/policy/spec.py` (the schema every file must match)
- Reference: `src/decision_engine/domains/` (every `check:` and evidence key must exist there)

## Process
Per action: `reversibility`, `impact`, `required_fields` (with EN/AR questions), `required_evidence`,
and rule lists `refuse_if` / `defer_if` / `escalate_if` / `risk`. Thresholds: execute confidence,
irreversible confidence, autonomy budget (max expected loss in BHD).

## Outputs
Loaded `Policy` objects; nothing is written here at runtime.

## Check
`uv run pytest -q` (an unknown check name raises) and `uv run python evals/run_evals.py`. Bump `version` on every change.
