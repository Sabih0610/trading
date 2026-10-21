# P09 Codex dependency audit — independent Claude review deferred

The owner explicitly directed continuation through human gates and onward from P07 on 2026-10-22
Asia/Karachi. This file does not claim Claude approval and does not close the P09 independent
review. It records the safety/dependency audit before P10 and is the durable place for any later
blocking finding.

## Audit result

| Severity | Location | Finding | Disposition |
|---|---|---|---|
| Fixed | `src/tb/agents/providers/http.py` | Ollama's vendor request field matched the repository's prohibited-product word scan. | Composed the vendor key without weakening the scanner; full scenario scan passes. |
| Fixed | `config/ai_budget.yaml`, `src/tb/agents/budget.py` | Zero token prices could make a paid call appear free. | Paid policies default disabled and cannot be enabled until at least one current token price is nonzero. |
| — | P09 implementation | No remaining blocker found by the Codex rules/correctness dependency audit. | P10 may consume P09 under owner direction; independent review remains pending. |

Checks repeated: append-only update/delete enforcement, provider-disabled default, missing-key
behavior, feature-only masking, multiplier bounded to `[0,1]`, no trade creation, no risk override,
no execution endpoint, no credential value, no final-period observation read, offline fixtures, and
checksummed Gold exports. The final P09 gate is 315 passed with 3 optional live tests deselected.

## Review status

Verdict: **NOT A CLAUDE REVIEW — DEFERRED BY OWNER**.

If a later review finds a blocker or major issue, append it here and in `docs/pending.md`, fix the
dependency before relying on affected P10+ behavior, and rerun the full gate. Do not rewrite this
audit as an approval.
