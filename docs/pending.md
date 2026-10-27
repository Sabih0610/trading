# Pending items

- **P11b.1a-Prep independent review:** [report](../reports/phases/P11b.1a-prep.md), [security](security/ctrader-oauth-prep.md), [ADR0016](adr/0016-private-owner-assisted-ctrader-onboarding.md). 937 pass/3 live deselected; offline milestone only.
- **Owner external OAuth actions — NOT EXECUTED:** check actual app approval, broker/demo eligibility/terms and one account; authorize reviewed code integration without copying .env; prepare/register exact fresh callback; separately authorize accounts-only consent and confirm the returned demo identity privately. [Guide](how-to/ctrader-oauth-after-approval.md). No genuine token/scope/account verified here.
- **Genuine connection remains NO-GO:** separate bounded-diagnostic authorization plus rights/UTC/metadata/cost/retention evidence required. No callback fallback to unsupported state/PKCE or broad predictable URI. P11b.2b unstarted.

- **P11b.2a.1 independent review:** [report](../reports/phases/P11b.2a.1.md), [ADR0015](adr/0015-offline-validation-and-gated-windows-ci.md). 853 tests pass; four reproduced fixes, Decimal/process-death oracles and all 14 owned replays pass. No independent human approval claimed.
- **Hosted CI:** local workflow validated; public origin confirmed but Actions policy endpoint returned 403. Owner review, free standard-runner/policy verification and separate push/activation authorization required before setting OFFLINE_CI_APPROVED_FREE_RUNNER. No hosted pass or branch protection change.
- **Future genuine integration:** [explicit input matrix](specifications/P11b.2b-genuine-input-contract.md) remains NO-GO. No provider or OAuth authentication in this phase.

- **P11b.2a independent review:** [completion report](../reports/phases/P11b.2a.md), [operator guide](how-to/offline-paper-lab.md), [ADR0014](adr/0014-owned-persistent-paper-accounting.md). Offline software milestone complete; 826 tests pass. Review cash/reservations, causal fills, gap/metadata/exposure guards, atomic recovery and source isolation.
- **P11b.1a preserved and unfinished:** original checkout and private credentials untouched. Latest owner update says cTrader app approval pending. No OAuth helper was merged or consent performed. Do not conflate this offline paper milestone with genuine authorization.
- **P11b.2b remains NO-GO/unstarted:** separate future scope requires qualified genuine input, exact broker account/view permissions, rights/retention/display, clock/unit/contract/cost evidence and independent eligibility review. No new genuine source or order is enabled by green owned tests.

- **P11b.1 independent review:** [report](../reports/phases/P11b.1.md),
  [ADR0013](adr/0013-read-only-broker-quote-evidence.md), [how-to](how-to/broker-quote-research.md).
  758 tests pass; cTrader facade and owned evidence complete. Actual genuine qualification is
  unverified independently for EURUSD/XAUUSD. **P11b.2 remains NO-GO and unstarted.**
- **Owner-provisioned broker prerequisites:** legitimate Pakistan/no-funding demo access,
  approved app and exact single-demo accounts-only token; actual returned view scope; fresh
  independent UTC/unit evidence; exact broker contract/tick/product/profit/session/holiday/
  commission/conversion/funding metadata; retention/display rights; independent legal/Shariah
  review and actual fully funded minimum capital. No account/agreement/provider message was
  created on the owner's behalf. Broker examples install no approval; do not use trade tokens.
- **Finite read-only smoke not run:** no credentials or access/rights evidence configured.
  Conditional command is documented; do not automatically collect, widen scope or start a
  simulator. Existing Twelve Data rights blockers and original MT5 clock uncertainty remain.

- **Third-party adoption audit review:** [report](../reports/reviews/third-party-repository-adoption.md)
  and [backlog](third-party-adoption-backlog.md) are complete. Only A1 offline Windows CI and A2
  bounded local source map are proposed. Neither is implemented; no full-framework migration,
  provider/stock integration, webhook endpoint or order authority is authorized by this audit.

- **P11b.0.1 completed offline:** two price-only reference hypotheses now work on ten owned
  scenarios; 685 tests pass. Independent review is queued. Original execution-dependent strategies
  remain blocked. Synthetic direction labels are not market skill, fills or P&L.
- **Provider approval still pending:** active policy unchanged. Use the offline
  [documentary rights workflow](how-to/data-rights-review.md); a support request is not approval.
  Resolve exact cache/history/derived/persistent/AI/ML/display rights and retention/expiry handling
  before genuine use. No provider message, actual approval or automatic record deletion was made.
- **Two-hour trial limitation:** 52 M5 warm-up bars require 260 minutes; a fresh two-hour trial must
  remain warm-up WAIT. A longer finite signal trial needs separate owner scope and continuity/
  retention design; existing 120-minute bounds remain unchanged. See [conditional plan](P11b.0.1-supervised-trial-plan.md).

- **P11b.0 completed offline:** 641 tests pass; owned replay 128 events/512 WAIT decisions,
  recovery 128 duplicate suppressions. Independent review is queued. Genuine M5 collection/watch
  stays blocked by exact usage/retention approvals. Resolve cache/history/derived/persistent,
  AI/ML and display/commercial scope independently; current policy has no genuine approval.
  Follow [rights remediation and conditional trial plan](P11b.0-supervised-trial-plan.md) before
  any new genuine retention. Do not automatically delete prior records or contact a provider.
- **Genuine trial not run:** verify actual M5 headers/weights, source entitlement/finality,
  independent UTC, gaps/restart and finite supervised shutdown only after rights and a new owner
  approval. No raw-price UI, directional skill, P&L or 24h reliability is established.
- **Genuine broker qualification remains pending:** P11b.1 is complete offline. Actual bid/ask,
  contract/cost/session/funding and funded-minimum facts remain unverified; see the
  [completion report](../reports/phases/P11b.1.md). No broker order, EA, account runtime,
  paid upgrade, training, autonomous promotion or unattended Windows task is authorized.

- **P11a.3:** EUR/USD and XAU/USD Basic completed M1 midpoint data passed bounded qualification;
  executable bid/ask and realistic paper fills remain NO-GO. No new key is pending for Twelve Data.
  Confirm exact personal display, raw-retention duration, commercial/ML-use rights before a
  growing archive, raw price UI or wider use. Basic M1 collection for two symbols exceeds daily
  credits if continuous. Independent review and verified genuine-use rights remain pending. P11b.0 and P11b.1 were later authorized and completed offline; genuine broker qualification remains unverified.
  See [P11a.3 report](../reports/phases/P11a.3.md); no paid upgrade or external order is authorized.

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
- Owner completed native trading/dangerous-shell disablement and exact XAUUSD visibility. Verified native trading false and shell-tool absence in that phase. P11a.2 later found XAUUSD hidden again; see current evidence section below. Recheck before each genuine run.
- Windows Time service was stopped; independent HTTPS clocks agreed with host UTC. Owner may review host synchronization separately; no automatic time/service changes were made.
- Complete pip/cost/session/holiday/stop constraints and reconcile XAUUSD tick-value arithmetic. Minimum broker lots indicatively exceed $100 at 1x; sizing remains blocked.
- Sustained genuine acquisition, two consecutive qualified M5 intervals and genuine restart reliability remain unverified. Current admission refuses extended collection.
- Codex's four read-only MCP tools were used earlier. Two existing-session calls refused at handoff while a fresh constrained client and SDK identity succeeded; investigate session renewal before relying on long-lived MCP inspection. Hosted Market Data and MetaEditor availability remain unverified and are unnecessary for this collector.
- Independent P11a/P11a.1 reviews remain queued. MT5-backed executable simulation remains NO-GO. Later P11b.0 is offline reference research only; no paper account runtime, scheduler, soak, broker sender or EA is authorized.

## P11a.2 external evidence needed

- Obtain authoritative MetaQuotes-Demo exact-server/build SDK seconds/milliseconds, tick/candle and historical DST/effective-period semantics. No installed conversion rule; stable+3h alone cannot verify it.
- XAUUSD is currently selected=true but visible=false with no quote. Earlier owner Show action was confirmed; current state changed. Owner may manually show the same exact XAUUSD again if quote inspection is wanted. No automatic selection or GOLD substitution.
- Current independent Microsoft UTC agreed; Cloudflare reference unavailable and W32Time stopped. A verified profile needs repeated measurements with two independent UTC references; no sync/service edits are automated.
- OANDA Practice credentials are absent. Current Pakistan/division/API/metals/no-funding/storage/AI rights are unverified; v20 explicitly excludes Global Markets/TMS. Do not request a token or create/fund an account before provider access/rights are confirmed.
- Conditionally prioritize provider confirmation for a separate Pepperstone MT5 demo: current Pakistan data-only demo/SDK access, exact server/build clock/DST, instruments, expiry and storage/reuse rights. Dated official affiliate material is not current approval. No broker message or registration was sent.
- Costs/pip/session/holiday/stop/conversion and XAUUSD tick-value consistency remain incomplete. Broker minimum lots do not fit$100 at1x on prior indicative prices; current gold price is unavailable. No sizing permission.
- Independent P11a.2 review queued. No MT5/OANDA genuine source qualified in that phase, and no sustained M5/restart soak was measured. Later P11a.3 bounded Twelve Data M1 and offline P11b.0 do not clear those provider-specific gates. No new notification, paid AI, EA or order bridge.
