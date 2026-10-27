# cTrader OAuth preparation security boundary

2026-10-27 UTC. Offline readiness only. Real application/account credentials remain in their
original private checkout; validation uses generated owned fixtures. No real auth/code/token was
obtained, transmitted, copied or displayed. No genuine quote or order path is activated.

| Boundary | Implementation / evidence | Remaining limitation |
|---|---|---|
| User initiation | Inert status; separate prepare; explicit after-approval command plus two private human flags; CI real transport denial | Flags express owner attestation, not proof of provider approval. Actual approval must be checked by owner. |
| Callback correlation | 256-bit private one-use path in exact registered redirect; spent marker before browser; bound code/session; five-minute/20-request cap | Must register new exact URI each attempt. Portal acceptance/HTTP loopback behavior unverified. No guessed state, PKCE, wildcard or cookie-only fallback. |
| Local listener | Literal 127.0.0.1, exclusive port, exact Host/path/query, one-use callback, finite socket timeout; no logs | A malicious local administrator or compromised browser can observe memory/history. Keep private URI unshared. |
| HTTP handling | Fixed body, no reflected code/request/error, no-store/referrer/CSP/frame protections, callback address replaced in browser history | Initial browser navigation/history synchronization cannot be proven absent offline. Do not share screens/history. |
| Code lifecycle | Memory only, local 45-second redemption age, clear object value after consume, no replay | Provider code issue time unknown; actual one-minute provider expiry enforced remotely later. Python does not promise physical memory erasure. |
| Token endpoint | Fixed TLS host/path; no redirect/proxy/debug/logger; 10-second timeout, 16-KiB body; bounded fields and safe failures | Provider requires credentials in query. Malicious process instrumentation/provider-side access logs remain outside local control. Genuine refresh GET/POST ambiguity unresolved. |
| Permission proof | Actual permissionScope required; typed token/account enums distinct; exact single demo/broker/server/token binding; hidden owner confirmation | Fake responses prove validation only. No actual returned scope/account grant exists. Missing optional account rights intentionally refuses instead of adopting protobuf default. |
| Persistent credentials | Private root .env; empty owner/SYSTEM staging before secret write, fsync/replace, complete tokens/expiry/pin in one transaction; unrelated entries retained | A process killed mid-write can leave a private ignored staging file; no automatic recovery from it. A malicious same-user/admin process is out of scope. |
| Recovery / concurrency | Compare expected private revision; writer/session OS lease; old or new complete pair on injected interruption; invalid file refuses | Server may rotate/revoke tokens before a local failure. Do not assume old tokens remain valid; revoke/re-authorize manually if state uncertain. |
| Broker / paper separation | Existing facade/allowlist byte semantics unchanged; new protocol requests only 2100,2149,2102,2121; no quotes or paper imports | OAuth alone does not qualify clocks, quote sides, costs/units, data retention, eligibility or capital feasibility. |

## Reproduced and corrected during preparation

1. A code accepted for one local callback could be passed to another local session before server
   rejection. A failing owned test reproduced this; exchange now requires its accepted redirect
   binding, active bounded session and one-use code before any wire call.
2. BaseHTTPRequestHandler's malformed-request error page could echo a request line containing the
   callback path/code. A real malformed loopback HTTP test reproduced this. All parser/verb errors
   now use the same static private-safe body/headers as normal callback handling.

Owned adversarial tests cover extra/live/wrong accounts, missing/escalated permissions, revoked
access, unknown server, malformed tokens, redirects, timeouts, oversized/wrong-type/invalid JSON,
rotation, stale local state, weak ACLs, concurrent preparation, owner refusal and interrupted storage.
No raw provider text or credential-bearing URI enters a report. Public status contains booleans only.

After approval, revocation is an owner action in the cTrader ID Open API authorizations interface.
Stop local helper, disable its private enable flag and remove invalid token values privately.
Do not upload .env/staging files. Do not auto-repair malformed state or automatically refresh tokens.
