# P11n frozen calendar reference map (pre-data)

The exact policy is `config/swing-calendar.json`. Its initial SHA-256 is
`1abdbbd252a3019c45a073f22728f15a96a43636eb83a84b245dc542094b8f36`.
No genuine source registry, metadata or observations have been opened in N.
Root reviews this policy and exact source/read scope before a genuine build.

All nine intervals are declared research reference closures: prior date17:00
through reference holiday18:00 in `America/New_York`, converted to UTC explicitly.
The provider's approved base clock/rollover remains unchanged. Broker sources
corroborate the holiday date, not HistData's actual quotes or the declared interval.

| Reference day | Exact UTC half-open interval | Date evidence |
|---|---|---|
| 2021-01-01 | 2020-12-31 22:00 → 2021-01-01 23:00 | Generic OANDA operating-hours/holiday rule; dated-source limitation remains explicit |
| 2021-04-02 | 2021-04-01 21:00 → 2021-04-02 22:00 | Tickmill official Easter2021, XAUUSD closed Good Friday |
| 2021-12-24 | 2021-12-23 22:00 → 2021-12-24 23:00 | XM official Christmas2021, gold/silver closedDec24 |
| 2022-04-15 | 2022-04-14 21:00 → 2022-04-15 22:00 | Tickmill official Easter2022, XAUUSD closed Good Friday |
| 2022-12-26 | 2022-12-25 22:00 → 2022-12-26 23:00 | XM official2022 holiday schedule |
| 2023-01-02 | 2023-01-01 22:00 → 2023-01-02 23:00 | XM official2022/23 holiday schedule |
| 2023-04-07 | 2023-04-06 21:00 → 2023-04-07 22:00 | FXChoice official Easter2023, commodities closed |
| 2023-12-25 | 2023-12-24 22:00 → 2023-12-25 23:00 | XM official2023/24 holiday schedule |
| 2024-01-01 | 2023-12-31 22:00 → 2024-01-01 23:00 | XM official2023/24; only the2023 boundary expectation is used, no2024 XAU data |

Exact URLs are stored per interval in the policy. Unlike a hindsight calendar,
this policy is not edited from observed gaps or conflicts. Unknown/early closes
remain conservative incomplete coverage; actual quotes inside a closure are kept
and flag calendar_conflict. Closed expected-zero periods have null OHLC and are not
fabricated complete bars. All genuine quality details remain ignored/private.

Canonical Git LF policy SHA-256 before the clean full gate: `337769b2e0be18e9681b1e8c12b31b95fb5e0035c7b413f982ce5a14be2671f3`.
The initial CRLF hash above is retained as historical pre-data evidence. Line-ending
normalization changes no JSON value, interval, evidence or reference assumption.
