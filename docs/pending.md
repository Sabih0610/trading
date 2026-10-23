# Pending items

- **Deferred by explicit owner direction:** the independent Claude review for P06 remains open.
  A Codex dependency audit found no blocker but is not approval. Record any later blocker in
  `reports/reviews/P06-codex-dependency-audit.md` and fix it before relying on affected results.

- **Deferred by explicit owner direction:** the independent Claude review for P09 remains open.
  The Codex dependency audit fixed the paid-price gate and vendor-key scanner conflict, then found
  no remaining blocker. It is not approval. Record any later blocker in
  `reports/reviews/P09-codex-dependency-audit.md` and fix it before relying on affected results.
- Paid AI providers remain policy-disabled even when keys exist. Before any controlled paid trial,
  a human must set current nonzero token prices and explicit daily/monthly/max-call caps in
  `config/ai_budget.yaml`, then intentionally set that provider's `enabled` field to true.

- Optional: run the Claude review for P00 from `prompts/REVIEW_CLAUDE.md`. P00 is queued but is not a mandatory stop gate.
- Optional: run the Claude review for P01 from `prompts/REVIEW_CLAUDE.md`. P01 is queued but is not a mandatory stop gate.
- Binance spot-specific skills were unavailable at the audited upstream revision. No action is required; later phases will use official documentation unless a compatible skill is reviewed.
- P02 needs an owner/legal scope decision before live FRED data is stored or used: the current FRED services terms restrict using FRED content in development or training of AI/software systems. Fixture-backed adapter work can continue; direct public-domain source alternatives should be preferred for later ML.
- P02's broad six-year Binance/Dukascopy transfer was estimated at 779 GB. This checkout's D:
  volume has approximately 493 GiB free (2026-10-22 review), and no old seven-day sample or market
  volume is attached here. The prior 118 GB free-space figure described another machine. Scope
  a small lawful dataset before downloading; do not begin a bulk transfer from the old estimate.
- P03 automated Fair Economy/Forex Factory storage is disabled pending a verifiable automated-use/reuse terms decision. The current-week endpoint is technically reachable, but P03 will not treat reachability as permission.
- P03's full GDELT headline archive is waiting for the public DOC API cooldown after repeated HTTP 429 responses. Rerun the documented `download-news.ps1 -Sources gdelt ... -Resume` command without reducing its five-second request gate.
- P04 exact DXY/USDX replication needs an owner/licensing decision. ICE's current official brochure says use of its formulation, components, weights, values, or calculation methods requires express written consent. Do not label a generic USD basket as DXY/USDX.
- P07's requested pre-2025 Binance XAUT history cannot exist: the venue opened 2026-03-26 13:30 UTC.
  This is a research-design blocker, not a download backlog. The 2025+ lock remains untouched.
  Freeze a separate prospective protocol before collecting forward evidence; XAUUSD/EURUSD
  research requires its own verified history and is never a substitute for executable XAUT data.
- P08 empirical model comparisons and the filtered-vs-unfiltered validation backtest inherit the
  P07 data blocker. No model was trained on market data: training, calibration, validation, and
  final-test trial counts are all zero. Synthetic tests verify mechanics only. Rerun
  `.\scripts\run-ml-evaluation.ps1` for metadata-only status; only a separately frozen, sufficiently
  sampled research protocol can support future model evaluation.
- P09 provider skill, veto value, hypothesis hit rate, and cost per useful decision are NOT
  EVALUABLE until eligible instrument-specific setups and resolved shadow outcomes exist. The mock run proves
  mechanics only and must not be cited as trading evidence.

- P09.5 independent safety review is queued. Earlier P06/P09 reviews remain deferred and are
  not approvals; resolve blocking findings before any broker-routing phase.
- No independent instrument-specific Shariah approval source or current legal eligibility
  determination is attached. All external demo/live eligibility remains false.
- P11a verifies MT5 demo identity and basic contract metadata; genuine quote time/availability and
  complete sizing/session facts remain unresolved. Alpaca, data-rights review, persistent paper
  reconciliation/notifications and a 30+ day forward run remain future work.

- P10 is read-only; an independent dashboard review is queued. Actual account/feed health,
  calibration, market-trained models and qualified strategy trials remain unavailable/unproven.
- Dashboard manifests preserve declared checksums; ingestion/export release must verify actual
  large-file integrity. No UI action loads raw locked data or recalculates an empirical strategy.
- Current Binance Spot execution policy does not authorize MT5 contract demo routing. The hybrid
  Python/EA recommendation is conditional on a separately approved P12 scope/policy and safety
  review. P11a may implement only a read-only market feed under a new owner instruction.

- P11a.1: both EURUSD and XAUUSD source epochs remain approximately three hours ahead of verified host UTC. Obtain provider-supported UTC/DST semantics or separately review a UTC-explicit data-only Practice source. Do not infer an offset or change old observations.
- Owner completed native trading/dangerous-shell disablement and exact XAUUSD visibility. Verified native trading false and shell-tool absence; no further manual visibility/security request is pending. Recheck before each genuine run.
- Windows Time service was stopped; independent HTTPS clocks agreed with host UTC. Owner may review host synchronization separately; no automatic time/service changes were made.
- Complete pip/cost/session/holiday/stop constraints and reconcile XAUUSD tick-value arithmetic. Minimum broker lots indicatively exceed $100 at 1x; sizing remains blocked.
- Sustained genuine acquisition, two consecutive qualified M5 intervals and genuine restart reliability remain unverified. Current admission refuses extended collection.
- Codex's four read-only MCP tools were used earlier. Two existing-session calls refused at handoff while a fresh constrained client and SDK identity succeeded; investigate session renewal before relying on long-lived MCP inspection. Hosted Market Data and MetaEditor availability remain unverified and are unnecessary for this collector.
- Independent P11a/P11a.1 reviews remain queued. P11b is NO-GO and unstarted; no paper runtime, scheduler, soak, broker sender or EA is authorized. Future work requires separate scope and verified data.
