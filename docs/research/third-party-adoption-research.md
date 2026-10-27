# Third-party repository adoption research

Inspected 2026-10-24 UTC for a documentation-only adoption audit.
Compared five requested upstreams and five named methodology candidates at exact commits.
Retain existing code and recommend only an offline Windows CI gate and a bounded local source map.
No source was copied, installed or executed; all recommendations await review.

## Questions and comparison

| Question | Options compared | Finding / decision |
|---|---|---|
| Does a webhook bot supply a safe research boundary? | Reuse its handler; implement a research-only inbox; defer | Handler routes body-passphrase requests to order code, has no durable replay check in that path and no repo license. Defer. |
| Can Aider improve development without a second AI runtime? | Install assistant; copy graph mapper; independent small source map and existing-check CI | Reuse concepts only; stdlib AST and existing test commands fit local limits. Its defaults can skip Git hooks, so do not copy defaults. |
| Would a visual platform simplify the application? | Migrate to Superalgos; embed executable graph; later display-only view | Existing risk/features/journal boundaries would need to be rebuilt. Current master and nightly release dates convey different maintenance signals. No migration. |
| Does Alpaca fill the gold/FX data gap? | New stock SDK adapter now; future scoped stock data; account/paper client | Stock data is a future capability; it does not establish EURUSD/XAUUSD entitlement. Paper mode still exposes order methods. |
| Are named research packages needed now? | New frameworks; optional later parity studies; retain tested mechanics | Existing walk-forward/purge/baselines/stress/journal cover much of the method. PyBroker/vectorbt have Commons Clause; current Nautilus Python and Qlib MLflow constraints conflict with this checkout. |
| Does a public catalogue license its snippets or prove returns? | Copy examples; use links as discovery; subscribe to hosted service | No license found in complete tree; actual BTC example sets 10x leverage. Primary-source discovery only, within existing research practice. |

## Method and evidence

Public unauthenticated GitHub API metadata recorded default branches, five commits, three releases and eight recently updated issues/PRs per repository. Complete recursive trees were untruncated. Selected raw files were fetched by immutable commit SHA, hashed and read as data in an ignored work folder. No upstream package, Git hook, notebook, test or installer ran. Open PR assertions are labelled reports and were not treated as merged fixes or independently reproduced results.

The [audit](../../reports/reviews/third-party-repository-adoption.md) contains the exact SHA/license/maintenance matrix, per-repository source links, risk/dependency/performance/effort comparison, classifications and migration rationale. The [evidence manifest](../../reports/reviews/third-party-repository-evidence.json) records 101 pinned source-file URLs/checksums and snapshot metadata; it contains analysis/metadata, not vendored third-party source. The [backlog](../third-party-adoption-backlog.md) defines acceptance criteria for the two proposals. Effort/resource targets are estimates, not benchmark results.

## Sources — accessed 2026-10-24 UTC

All repository references below point to the exact inspected tree. Individual README, LICENSE, code, tests, workflow and issue/release links appear beside their claims in the audit and evidence manifest.

- [TradingView webhook source](https://github.com/lth-elm/TradingView-Webhook-Trading-Bot/tree/e9efac27c4b5f933442e5248b7e180c176b6c47a)
- [Aider source](https://github.com/Aider-AI/aider/tree/5dc9490bb35f9729ef2c95d00a19ccd30c26339c)
- [Superalgos source](https://github.com/Superalgos/Superalgos/tree/9f0fb59edd4bae7afa08d06c366e0bcb48103aec)
- [Alpaca-py source](https://github.com/alpacahq/alpaca-py/tree/66f2ffd797d3cb0e5202daf36d178b67aff89915)
- [Systematic-trading catalogue](https://github.com/paperswithbacktest/awesome-systematic-trading/tree/ddfee8bb548bd6914191cb8fdb695d533ae16b0d)
- [PyBroker source/license](https://github.com/edtechre/pybroker/tree/01f11fdd42b76ef564a7f550c247a3dfce81330e)
- [vectorbt source/license](https://github.com/polakowo/vectorbt/tree/8e30b8ce102f302bec0c0226e05b59714453bebd)
- [NautilusTrader source](https://github.com/nautechsystems/nautilus_trader/tree/a8b4d7381020981ccda1165f24101e0e9ceedb1e)
- [QuantStats source](https://github.com/ranaroussi/quantstats/tree/9ef4c6d0a4ffe7831f6ebba6a5824fd33a90c05a)
- [Qlib source](https://github.com/microsoft/qlib/tree/54355232463878d2eebb91fe0ee5fa7fa1f5976c)
- [TradingView webhook delivery/authentication constraints](https://www.tradingview.com/support/solutions/43000529348-how-to-configure-webhook-alerts/)
- [Aider Git defaults](https://aider.chat/docs/git.html)
- [Alpaca paper separation and limitations](https://docs.alpaca.markets/us/docs/paper-trading)
- [Alpaca market-data feed FAQ](https://docs.alpaca.markets/us/docs/market-data-faq)
- [GitHub Actions secure use](https://docs.github.com/en/actions/reference/security/secure-use)

## Risks / unknowns retained

No full transitive license review, CVE audit, account/plan test, genuine feed collection, upstream suite execution or runtime benchmark was performed. Sampling recent default-branch commits does not measure all development branches. No data-provider rights, stock approval, model skill or market-execution suitability was granted. Current baseline is P11b.0.1 (`e537d56`), compared explicitly with the requested P11b.0 (`45a6d5f`); existing review/rights gates remain open.
