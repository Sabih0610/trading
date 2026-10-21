# Run and inspect the AI arena

The P09 acceptance workflow runs entirely with `MockProvider`: it needs no key, makes no paid
request, writes an immutable local ledger, and exports checksummed Gold Parquet snapshots. AI is
decision support only; the resulting multiplier can never exceed 1.

## Run the offline workflow

From the repository root:

```powershell
.\scripts\run-ai-arena.ps1
```

The command writes `reports/arena/P09.json`, keeps operational SQLite files below `.cache/p09/`,
and exports table snapshots below `data/gold/ledger/date=YYYY-MM-DD/`. Data and cache folders are
git-ignored; the small JSON acceptance report is committed.

Run focused tests with:

```powershell
uv run pytest "tests/unit/test_agent_arena.py" "tests/unit/test_agent_providers.py" "tests/unit/test_ledger_store.py" "tests/integration/test_agent_evaluation.py" -q
```

## Optional Ollama adapter

`OllamaProvider` requires a declared model at or below 4 billion parameters and exactly 4-bit
quantization. The adapter uses `OLLAMA_HOST`, native JSON Schema output, a bounded timeout, and local
Pydantic validation. Installing or starting Ollama is not required for the offline workflow.

Do not run local LLM inference while model training is active. Benchmark the selected model on this
host before operational use; the project makes no unmeasured tokens/second claim.

## Paid providers

Every key is optional. A key alone does not enable spending: the matching entry in
`config/ai_budget.yaml` also defaults to `enabled: false`. Before a controlled trial, a human must
set current nonzero token prices, daily/monthly caps, a maximum call cost, and then enable the
provider. Never put a key in YAML; keys remain only in the ignored `.env` file.

If a key or policy is absent, a cap is exhausted, the provider times out, or JSON is invalid, the
attempt is logged and skipped. It cannot enlarge or originate a trade.

## Inspect or resolve evidence

The five ledger tables are `decisions`, `model_calls`, `outcomes`, `hypotheses`, and
`interventions`. Do not update or delete rows; database triggers reject both. When a setup resolves,
append an `outcomes` row referencing its decision. Re-export after appending outcomes so the Gold
snapshot and manifest reflect the new evidence.

## Troubleshooting

- `append-only table`: expected protection; append a superseding event instead of editing.
- `policy_disabled`: set pricing/caps intentionally before `enabled: true`; do not bypass the gate.
- `budget_skipped`: the pre-call reservation would exceed a daily, provider-monthly, or total cap.
- `MALFORMED_RESPONSE`: provider JSON did not match the local frozen schema and had no effect.
- Ollama connection failure: leave it disabled or start the local service; the mock path still runs.
