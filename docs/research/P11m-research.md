# Multi-day holding research

2026-11-05. Owner authorizes at most ten calendar days, with existing daily MTM loss/drawdown protections and optional strategy EOD tightening. This is fixture software work, not paper operation or a new strategy experiment.

| Question | Options | Decision |
|---|---|---|
| Holding bound | Count observed bars; elapsed UTC timestamps | Actual fill timestamp + effective days, capped by compiled10 and human global config. Missing/weekend bars cannot extend the holding period. |
| Integer validation | Coerce floats/bools; strict int | Pydantic Field(strict=True,ge=1,le=10); reject11,0,fraction,float,bool/string inputs. |
| UTC rollover | Reset to first new-day mark; previous valid liquidation mark | Persist prior valid equity, retain original peak, and use prior mark as new-day anchor. Gaps then count as that day's loss. |
| Historical EOD | Globally force every position flat; proposal tightening | Global EOD OR proposal EOD; existing proposal defaultsTrue preserve owned intraday fixtures. |
| Reproducibility | Rerun genuine frozen F/G; owned differential regressions | Owned adapters/fixtures only; never replay immutable genuine registered results. |

Primary sources accessed2026-11-05:
- [Pydantic2 strict mode](https://docs.pydantic.dev/2.12/concepts/strict_mode/): per-field strict validation refuses coercion.
- [Pydantic strict types](https://docs.pydantic.dev/2.0/usage/types/strict_types/): strict integers reject booleans despite Python int inheritance.
- [IBKR daily P&L fields](https://www.interactivebrokers.com/docs/web-api/v1/endpoints/market-data/market-data-fields): daily P&L since prior close versus cumulative unrealized P&L; informs accounting semantics only, not broker integration.
- [IBKR P&L guide](https://www.ibkrguides.com/traderworkstation/profit-and-loss.htm): daily P&L includes open positions; project uses its own UTC boundary.

Pinned Python3.12/Pydantic2 environment unchanged. No provider API/order implementation or risk-number change follows from these sources.
