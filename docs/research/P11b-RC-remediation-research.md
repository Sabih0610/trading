# RC remediation research

Sources accessed 2026-10-27, public documentation only. No account/provider API used.

| Question | Options | Decision |
|---|---|---|
| Does injected HTTP transport imply owned data? | infer from injection / explicit owned mock | Explicit exact MockTransport interface with process socket denial; production customization retains genuine rights. |
| Can token scope substitute for account rights? | share enum / distinct parser | Reuse existing distinct account parser and refuse NO_LOGIN. |
| Should restart repair missing protections? | IF NOT EXISTS / schema verification | Verify complete pinned sqlite_master before any initializer. |
| Can policy renewal renew old data? | capture clock / original acquisition plus saved deadline | Saved deadline is an upper bound; current grant can shorten it, never extend it. |
| Can a stop be forgotten on rebound? | price condition / durable market-stop activation | Record original activation before fill attempt; fill next eligible bid once. |

References:
- [HTTPX transports](https://www.python-httpx.org/advanced/transports/): custom transports may perform real HTTP; mocks are distinct.
- [cTrader model messages](https://help.ctrader.com/open-api/model-messages/): account FULL_ACCESS/CLOSE_ONLY/NO_TRADING/NO_LOGIN are distinct from client token permissions.
- [SQLite PRAGMA reference](https://www.sqlite.org/pragma.html): schema version counters alone do not validate complete definitions.

No real license, provider consent, profitability or Shariah certification is inferred.
Research operations use owner-created fixtures now. Any licensed dataset requires
documented affirmative scope before import; terms are reviewed per dataset.
