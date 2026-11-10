# AGENTS.md: The Decision Engine

A decision layer for AI customer-service agents. A proposed action plus the conversation go in;
**execute · ask · defer · escalate · refuse** comes out, with signals and a hash-chained audit trail.
Core rule: **the LLM proposes signals, the policy decides.** No model output ever picks the outcome.

## Where everything lives

| Path | Job | Kind |
|---|---|---|
| [policies/](policies/CONTEXT.md) | Versioned YAML rules per business (what the agent may do alone) | factory |
| [data/](data/CONTEXT.md) | Seeded synthetic systems of record (food, telco, bank) | factory |
| [src/decision_engine/](src/decision_engine/CONTEXT.md) | Engine: signals → gates → audit | code |
| [evals/](evals/CONTEXT.md) | Hand-labelled scenarios + runner; `results/` is generated | factory + product |
| [ui/](ui/CONTEXT.md) | Navy-styled Gradio front end | code |
| `app.py` | One process: REST `/api/*` + UI at `/` | code |
| `render.yaml` | Live demo: free Render web service, auto-deploys on push to `main` | deploy |
| `Dockerfile`, [deploy/oracle/](docs/deploy-oracle.md) | Self-hosting: one Oracle Always Free VM, Caddy HTTPS, many apps | deploy |
| `tests/` | pytest: scenarios, failure tests, audit tamper, replay | check |
| [docs/](docs/architecture.md) | Architecture, failure tests, thesis, ADRs, plan | reference |
| `runs/` | Audit DB at runtime (git-ignored) | product |
| `_tools/links.py` | Checks every markdown link and contract input resolves | check |

## Go here for task X

- **Change what an agent may do** → edit `policies/<domain>.yaml`, bump `version`, add or adjust a scenario in `evals/scenarios/`.
- **Add a domain** → `data/generate.py` (records) + `src/decision_engine/domains/<name>.py` (evidence + checks) + register in `domains/__init__.py` + `policies/<name>.yaml` + scenarios.
- **Change how a decision is made** → `src/decision_engine/policy/engine.py` (gates) or `signals/__init__.py` (signals). Record why in `docs/adr/`.
- **Change LLM providers/models** → `src/decision_engine/llm/client.py`, keys in `.env` (see `.env.example`).
- **Change the look** → `ui/theme.py` (tokens), `ui/render.py` (HTML).
- **Deploy / change hosting** → Render: `render.yaml` (keys in the dashboard; pushing to `main` redeploys).
  Own server: `docs/deploy-oracle.md` + `deploy/oracle/` (Compose, Caddyfile, `setup.sh`; keys in `/opt/apps/.env` on the VM).

## Checks before every commit (all must pass)

```bash
uv run pytest -q
uv run python evals/run_evals.py      # 0 unsafe executes except the documented fd-13
python -I _tools/links.py
```

## Invariants

1. The LLM only extracts claims from untrusted text. Claims become evidence only when the system of record agrees.
2. Gate order is fixed: refuse → ask → defer → escalate → execute; nothing cleared = escalate.
3. Every decision and every human verdict is appended to the audit chain. Never rewrite rows.
4. Scenario labels are written from the policy text *before* running the engine. Never relabel to make a test pass.
5. The repo runs offline from a clean clone (mock extractor). Never require a key.
6. Commits carry no AI co-author trailers. Never commit `.env`.
