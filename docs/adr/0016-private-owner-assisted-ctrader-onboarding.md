# ADR0016 — Private owner-assisted cTrader OAuth preparation

Accepted for offline P11b.1a-Prep, 2026-10-27 UTC. Actual application approval, authentication and
broker qualification remain unverified. No genuine operation is executed by this checkpoint.
Keep existing BrokerQuoteSource, cTrader quote facade, message allowlist, rights and risk unchanged.

Add an optional owner-invoked onboarding package. Default status is inert. Preparation only writes
a new private callback URI; authorization/explicit manual renewal additionally require owner-confirmed
application approval, an enabled private flag and an explicit command flag. CI refuses real transport.
No timer, collector, quote subscription, execution interface or paper-engine consumer is introduced.

No documented state/PKCE support was established. Use an unpredictable exact callback path, registered
by the owner for each attempt. A private spent marker is committed before browser launch; timeout,
denial and crash require fresh preparation/registration. Loopback-only exclusive bind, exact Host,
path/query validation, bounded requests/session, static non-reflecting HTTP errors and code-to-redirect
binding protect local handling. This is not a claim of provider state/PKCE or portal compatibility.

Parse token ClientPermissionScope separately from trader AccessRights. Require actual returned view
scope, exactly one independently selected demo account, exact broker/identity, and hidden-input owner
confirmation. FULL_ACCESS is an account fact, never an OAuth scope. Close the auth channel before
storing tokens; do not start the quote facade. No new message kind or broker server is allowed.

Use root .env exclusively for persistent secrets, with owner/SYSTEM ACLs applied to empty staging
before writing, optimistic revision checks, OS-held session/writer leases, flush/fsync and atomic
complete-pair replacement. Codes are one-use memory only. No secret-bearing URL, raw response,
token backup, recovery journal or dashboard artifact. Read failures refuse without repair.

Fixed TLS token host/path, finite timeout/body, no redirect/proxy/debug logging, safe refusal
categories. GET refresh follows pinned official SDK; documentation's POST example remains a genuine
verification question. Provider rotation followed by local storage failure requires owner recovery,
not assumed rollback. Local malicious administrator/browser compromise remains outside this boundary.

See [research](../research/P11b.1a-prep-research.md), [security](../security/ctrader-oauth-prep.md),
[operator guide](../how-to/ctrader-oauth-after-approval.md) and
[integration plan](../specifications/P11b.1a-prep-integration-plan.md).
