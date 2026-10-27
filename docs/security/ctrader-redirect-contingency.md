# cTrader redirect acceptance — security contingency review

2026-10-27 UTC. The portal's acceptance of the proposed HTTP 127.0.0.1/random-path URI is
**unverified**, not proven supported or unsupported. App approval is still owner-reported pending.
No portal login, registration, authorization or alternative redirect was attempted or implemented.

[Official registration guidance](https://help.ctrader.com/open-api/api-application/) describes adding
redirects after approval but does not define this loopback scheme/host/path acceptance. The
[authentication guide](https://help.ctrader.com/open-api/account-authentication/) illustrates registered
HTTPS redirects and does not establish state/PKCE or arbitrary local URI support.

## Required first evidence after approval

Owner must privately register the helper's exact freshly prepared URI, confirm it persists unchanged
in the approved application, and then separately authorize a bounded accounts-only consent test.
Registration alone does not prove end-to-end browser/code behavior. A used, failed, expired or crashed
attempt requires another newly prepared and registered URI. Never post the private URI or code in
chat/reports. If the portal rejects it, keep genuine flow stopped; do not edit the stored path to fit.

| Contingency | Provider evidence | Security/operational implications | Decision now |
|---|---|---|---|
| Current exact one-use HTTP loopback URI | General redirect registration documented; exact portal compatibility unverified | Local exclusive port, fresh capability, spent marker, strict callback/code binding and pinned single-demo proof already tested. Re-register every attempt. | Retain unchanged; genuine NO-GO until actual approved evidence. |
| Owner-controlled registered HTTPS callback | HTTPS redirect examples exist; exact owner host/path still requires registration confirmation | Needs a separately reviewed HTTPS receiver/desktop handoff, origin/correlation and replay protection, code privacy, TLS/hosting control, expiry, logging/retention rights and operational ownership. Never transfer app secret/refresh token to a relay by default. Current helper intentionally rejects HTTPS URIs. | Design option only if loopback fails; separate authorization/security/code review and new tests required. No server/tunnel/service installed. |
| Fixed local/public callback with state or PKCE | No provider documentation/support established in this review | Cannot assume unknown parameters are echoed/validated. A fixed callback plus cookie or manual account confirmation alone is not an equivalent code/session binding. | Not an enabled fallback. Require explicit provider specification and reviewed implementation first. |
| Playground/default redirect, arbitrary public relay, pasted callback/code | Playground redirect explicitly unsuitable for app code; no approved relay/handoff contract | Risks scope ambiguity, code disclosure and lost correlation; secret-bearing history/log/clipboard exposure. | Prohibited as a shortcut. |

No fallback may relax view-only scope, exact single-demo/broker/server verification, owner confirmation,
code freshness/single use or private persistence. HTTPS by itself is not callback authentication.
No new cost, service, domain or data-processing agreement is authorized by this review. If no supported
safe redirect is established, genuine onboarding stays blocked rather than using a weaker callback.
