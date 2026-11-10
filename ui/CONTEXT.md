# ui/: the demo a stranger understands in 90 seconds

## Inputs
- Working: a running `DecisionEngine` (passed in from `app.py`)
- Reference: `evals/scenarios/` (scenario picker)

## Process
Tabs: **Decide** (scenario → outcome card, 5 signals, gate timeline, evidence), **Review queue**
(human verdicts on ask/escalate), **Audit trail** (verify chain, replay), **Evals**, **How it works**.
`theme.py` holds Navy-inspired tokens (Switzer, #FAFBFF / #111428 / #DBDFFF, square corners). Tokens only,
no template code or assets. `render.py` escapes every piece of user text.

## Outputs
HTML at `/` served by `app.py`.

## Check
`uv run python app.py`, open http://localhost:7860, run fd-12 and confirm ESCALATE with both security flags.
