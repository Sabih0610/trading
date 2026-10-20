# Trading bot — development kit

Copy everything in this folder into `E:\trading bot` (keep the hidden `.agents` folder), then:

```powershell
cd "E:\trading bot"
git init
git add . ; git commit -m "Add development kit"
```

## Files
| File | Purpose |
|---|---|
| `AGENTS.md` | Single source of truth: rules, stack, architecture, data splits. Codex reads it automatically. |
| `CLAUDE.md` | Points Claude Code to AGENTS.md and defines Claude's reviewer/stress-tester role. |
| `.agents/skills/trading-bot-rules/` | Project skill that filters every other skill through our rules. |
| `prompts/_PROTOCOL.md` | Research → build → self-test → report protocol used by every phase. |
| `prompts/P00 … P14` | One Codex prompt per phase, run in order. |
| `prompts/REVIEW_CLAUDE.md` | Claude review prompt to run after each phase or at the gates. |
| `prompts/RUN_ALL.md` | Master prompt: runs all phases in order, resumable. |
| `docs/DOCUMENTATION_STANDARD.md` + `docs/templates/` | What gets documented, where, and when. |
| `scripts/install-skills.ps1` | Clones skill repos for review and installs only the approved skills. |
| `docs/research/SOURCES_SEED.md` | Starting list of data sources for Codex to verify. |
| `.env.example` / `.gitignore` | Key names only; `.env` is never committed. |

## Quick start: one prompt runs everything
1. Unzip into `E:\trading bot`, then in PowerShell: `cd "E:\trading bot"; git init; git add .; git commit -m "Kit"`.
2. Open Codex in that folder (GPT-5.6 Sol, web search ON, network access ON) and send:

   `Read prompts/RUN_ALL.md and execute it.`

3. Codex works through P00 → P14 by itself, documenting everything. It stops only at the human
   gates (after P06, P09, P12), when keys are missing, or when its session runs out — it then
   writes `docs/HANDOFF.md`. To resume, send the **same prompt** again.
4. Whenever it stops at a gate, run the Claude review (below), then resume.

**Where to look at any time:** `PROGRESS.md` (status of every phase), `docs/HANDOFF.md` (what it's
doing and what's next), `docs/pending.md` (what it needs from you), `docs/journal/` (step-by-step
log), `docs/decisions/DECISIONS.md` (every decision and why), `reports/phases/` (phase reports),
`docs/how-to/` (how to run each part).

## Manual workflow (one phase at a time, optional)
1. **Codex (GPT-5.6 Sol):** enable web search and network access for the session, then send:
   `Read prompts/_PROTOCOL.md and prompts/P0X-<name>.md and execute the phase completely.`
2. Check `reports/phases/P0X.md` yourself.
3. **Claude Code:** run `prompts/REVIEW_CLAUDE.md` with the phase id.
4. Send any blockers/majors from `reports/reviews/P0X-review.md` back to Codex:
   `Fix every blocker and major in reports/reviews/P0X-review.md, re-run the protocol's Step 5–7.`
5. Commit, then move to the next phase. Never run two phases at once.

## Phases and when keys are needed
| Phase | Topic | Keys needed |
|---|---|---|
| P00 | Bootstrap, tooling, skills | none |
| P01 | Asset registry, Shariah gate, risk config | none |
| P02 | 6 years of market data → bronze | none |
| P03 | Calendar + news research and downloaders | none (keyed sources wired, disabled) |
| P04 | Silver: cleaning, validation, data dictionary | none |
| P05 | Feature engine (backtest = live) | none |
| P06 | Backtester + risk manager | none |
| P07 | Strategies A/B/C + scenario library | none |
| P08 | ML models | none |
| P09 | Decision ledger + AI arena | none (mock + Ollama); AI keys later |
| P10 | Dashboard | none |
| P11 | Live data + paper trading | none (public Binance streams) |
| P12 | Binance Testnet execution | Binance **Testnet** keys |
| P13 | Learning loop | none |
| P14 | Demo month runbook, go/no-go | none |

Optional later keys (FRED, Finnhub, CryptoPanic, AI providers, Jev, Telegram) slot in without code
changes: add them to `.env` and the feature switches on.

## Local AI on your hardware
GTX 1650 Ti (4 GB) + 16 GB RAM: use Ollama with small 4-bit models (~3–4B parameters). Expect
modest speed; fine for a few setups per day. Don't run model training and LLM inference together.

## Golden rules
Spot only · long-only · approved assets only · risk manager has the final say · AI can only veto or
reduce size · secrets only in `.env` · final test set (2025 →) stays locked.
