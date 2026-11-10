# src/decision_engine/: the engine

## Inputs
- Working: an `ActionProposal` (`models.py`): domain, action, params, actor, customer id, conversation
- Reference: `policies/*.yaml`, `data/synthetic/*.json`

## Process
1. `llm/`: extract claims from the untrusted conversation (Groq → Gemini → OpenRouter → offline mock),
   N samples for self-consistency. Prompt: `llm/prompts/extract.md`.
2. `domains/`: verify claims against the system of record (evidence) and evaluate named policy checks.
3. `signals/`: confidence = 0.5·evidence coverage + 0.3·self-consistency + 0.2·rule margin;
   risk score/tier; missing fields; reversibility; expected loss = (1−c)·impact·reversibility multiplier.
4. `policy/engine.py`: ordered gates refuse → ask → defer → escalate → execute, default escalate.
5. `audit/store.py`: append to the SHA-256 hash chain. `engine.py` adds replay and human resolution.

## Outputs
- A `Decision` (outcome, rationale, gate trace, next step, signals, policy id/version/hash)
- One audit row per decision or human verdict in `runs/audit.db`

## Check
`uv run pytest -q`: labelled scenarios, both failure tests, tamper detection, deterministic replay.
