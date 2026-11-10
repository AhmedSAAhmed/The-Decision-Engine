# evals/: does the engine decide like a careful supervisor?

## Inputs
- Reference: `evals/scenarios/food_delivery.yaml`
- Reference: `evals/scenarios/telecom.yaml`
- Reference: `evals/scenarios/banking.yaml`

38 hand-labelled cases in English, Gulf Arabic and Arabizi.

## Process
`uv run python evals/run_evals.py` runs every scenario through the engine and two baselines:
**Yes-man** (always execute) and **Coward** (always escalate).

## Outputs
- `evals/results/report.md`: accuracy, unsafe executes, over-escalations, confusion matrix, every scenario
- `evals/results/results.json`

## Check
Unsafe executes must be 0 except `fd-13` (tagged `known_limitation`, see `docs/failure-tests.md`).
Labels are written from policy text before running. Never relabel to make the engine pass.
