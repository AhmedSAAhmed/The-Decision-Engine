# data/: synthetic systems of record

Three fictional GCC businesses of the kind DOO serves: Sufra Delivery (food), Nahla Telecom, Gulf Pearl Bank.
Story records (the ones scenarios point at) plus seeded filler for volume. Demo clock: 2026-11-10.

## Inputs
- Reference: `data/generate.py` (the only source of truth; seed 42)

## Process
Run `uv run python -I data/generate.py`. The same bytes come out every time.

## Outputs
- `data/synthetic/food_delivery.json`, `telecom.json`, `banking.json`

## Check
Never hand-edit the JSON. Change `generate.py`, regenerate, then run tests and evals.
Note: approval `APR-2290` has `created_via: direct_db_write`. It is planted on purpose for failure test 2.
