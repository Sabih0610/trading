# cTrader OAuth — owner steps after approval

**NOT YET EXECUTED.** Application approval is still owner-reported pending. This guide describes
future owner-assisted authorization, not permission to run it now. No real token, demo identity,
view grant, quote qualification or genuine paper integration has been established.

First review/integrate the preparation code following the [integration plan](../specifications/P11b.1a-prep-integration-plan.md).
Run future commands from the reviewed checkout that already owns your private root .env. Do not
copy credentials between worktrees or paste them, callback addresses, codes or tokens into chat.

1. **NOT YET EXECUTED — approval.** Open the [Open API applications portal](https://openapi.ctrader.com)
   yourself and confirm the app is approved. Submitted/pending is insufficient. Do not use Playground
   tokens/redirects as a substitute. Review actual broker/demo and regional terms without accepting
   financial agreements automatically.
2. **NOT YET EXECUTED — private pins.** In your existing root .env, keep the existing application ID
   and secret. Privately configure CTRADER_DEMO_ACCOUNT_ID for exactly one intended demo account
   and CTRADER_DEMO_BROKER_PIN for its exact returned broker title. Independently confirm it is a demo.
   Only after approval/separate owner authorization, set CTRADER_DEMO_APPLICATION_APPROVED and
   CTRADER_DEMO_OAUTH_ENABLED to true. Keep requested scope accounts. Never put values on command lines.
3. **NOT YET EXECUTED — prepare/register exact URI.** Run the command below. It generates a random
   one-use callback and stores it privately in CTRADER_DEMO_OAUTH_REDIRECT_URI. Open .env privately
   and register that exact URI in the application's Redirect URIs section; save it. Do not alter its
   host/port/path or expose it in a screenshot. Each failed/timed-out/used attempt requires a newly
   prepared and registered URI. Portal acceptance of this loopback URI remains unverified; if refused,
   stop for review. Do not guess state/PKCE parameters or broaden to a predictable/wildcard callback.

```powershell
uv run --locked python -m tb.ingest.broker.onboarding.cli prepare
```

4. **NOT YET EXECUTED — owner authorization.** Start the helper below. It binds the configured
   loopback port before opening the browser. The browser must show accounts/view-only permission.
   Select only the independently pinned demo account; do not select live or extra accounts or any
   trading scope. Complete within five minutes. Do not share the callback address/code.

```powershell
uv run --locked python -m tb.ingest.broker.onboarding.cli authorize --after-approval
```

5. **NOT YET EXECUTED — exact account confirmation.** The helper exchanges the code immediately,
   verifies the returned token scope, single demo identity/broker and account access-rights enum,
   then closes that auth channel. Re-enter your expected demo account ID privately when prompted,
   within 30 seconds of verification. FULL_ACCESS is an account-level fact; it does not mean the
   application's token has trading scope. Missing/trading token scope always refuses.
6. **NOT YET EXECUTED — private storage check.** Use inert status below. It reports configuration,
   stored token-pair and stored-view-permission booleans without values. It does not prove current
   server access or quote readiness. Token pair, expiry and pins are stored atomically in private .env,
   with owner/SYSTEM ACLs. No quote session or paper integration starts. Do not print .env contents.

```powershell
uv run --locked python -m tb.ingest.broker.onboarding.cli status
```

7. **NOT YET EXECUTED — renewal/revocation.** Renewal is manual only using the explicit refresh action
   with --after-approval, after separately authorizing it. A fresh returned view grant/pin and hidden
   owner confirmation are required again. If rotation/storage fails, do not assume old tokens work.
   Use the cTrader ID [Open API authorizations](https://help.ctrader.com/ctrader-id/managing-ctid/open-api/)
   interface to review/revoke the app's access. Disable the private enable flag and remove invalid
   token values locally. Never recover tokens from a log/staging artifact or auto-repair malformed .env.
8. **NOT YET EXECUTED — bounded read-only connectivity.** Obtain separate approval for a timed
   quote diagnostic only after actual access/rights, clock, instrument/cost/session and retention
   gates pass. Use the existing [broker evidence guide](broker-quote-research.md); the current
   observation CLI is rights-gated and may refuse. OAuth success alone does not authorize it.
   Genuine inputs to Offline Paper Lab/P11b.2b remain NO-GO. No external order is authorized.

Safe offline rehearsal, already executed with owned generated credentials and a fake local provider:

```powershell
uv run --locked python -m tb.ingest.broker.onboarding.cli rehearsal
```

This uses a fresh owned temporary folder, cleans it afterwards, does not read the real .env and prints
only a synthetic summary. Safe refusal categories identify missing configuration/approval, callback,
grant, confirmation or private storage issues. No raw provider error is displayed. See the
[security boundary](../security/ctrader-oauth-prep.md) and [report](../../reports/phases/P11b.1a-prep.md).
