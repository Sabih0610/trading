# P01 research — versioned policy configuration and spot symbol metadata

P01 needs configuration that is readable by humans but impossible for later code to interpret loosely. The chosen design uses frozen Pydantic v2 models with unknown fields forbidden, an explicit integer schema version, deterministic cross-record validation, and hard risk ceilings compiled into Python.

## Questions asked

- How should YAML config be validated, versioned, and made resistant to typos or silent coercion?
- Which validations belong on individual fields versus the complete model?
- Which Binance spot fields must the asset registry be ready to receive from public `exchangeInfo`?
- How can YAML tighten risk without ever widening code-level ceilings?

## Options compared

| Topic | Options | Decision | Why |
|---|---|---|---|
| Unknown YAML keys | Ignore; warn; reject | Reject with `extra="forbid"` | A misspelled risk field must fail closed, not silently use a default. |
| Schema evolution | Infer from fields; filename suffix; explicit version | Required `schema_version: 1` literal | Loaders can later dispatch a migration deliberately; unsupported versions fail visibly. |
| Mutability | Mutable models; frozen validated models | Frozen Pydantic models | Policy objects should not change after validation. A new configuration load is auditable. |
| Cross-field rules | Ad hoc guard checks; model validators | Model validators plus bundle-level override checks | Role/status/strategy coherence is caught at load time; per-asset limits are checked against both code ceilings and the active global config. |
| Numeric type | float; integer basis points; Decimal | Decimal for money, quantities, and percentages | Avoid binary rounding at risk boundaries; YAML numbers and API strings normalize safely. |
| Exchange rules | Hard-code current symbol values; fetch live in P01; nullable metadata structure | Nullable `SpotSymbolRules`, populated later from public spot `exchangeInfo` | Current exchange filters can change. P01 defines the typed shape without turning startup/tests into network operations. |
| Guard result | Boolean; result object; typed exception | Return normalized/effective value on success and raise `RiskViolation` on failure | A caller cannot accidentally ignore a false value; errors remain human-readable and testable. |

## Binance spot metadata shape

The public spot `GET /api/v3/exchangeInfo` endpoint returns symbol identity/status, base and quote assets, permissions, order types, and filter objects. The registry reserves nullable fields for:

- price tick (`PRICE_FILTER.tickSize`);
- regular lot minimum, maximum, and step (`LOT_SIZE`);
- market-lot minimum, maximum, and step (`MARKET_LOT_SIZE`);
- minimum notional and optional maximum notional (`MIN_NOTIONAL` / `NOTIONAL`);
- the UTC time at which the public metadata was synchronized.

The values remain null in P01 because no network data is cached yet. Later ingestion must request only the spot endpoint/public market-data host and validate the response before replacing them.

## Risk authority

Hard ceilings compiled into code are 1% equity risk per trade, 1.0x total exposure, 3% daily loss, and three trades per asset per day. The global YAML may equal or tighten them. Per-asset overrides may equal or tighten both the compiled ceilings and the active global values. `flat_by_end_of_day` must stay true and XAUT weekend entries must stay false.

Exits remain available even when an entry session is closed so risk can always be reduced. A sell is valid only up to owned holdings. The order market field is a plain boundary string so `assert_spot` can explicitly fail closed on every non-spot value.

## Sources

Accessed 2026-10-20 UTC.

- [Pydantic validators](https://docs.pydantic.dev/latest/concepts/validators/) — field versus model validators and explicit validation errors.
- [Pydantic models](https://docs.pydantic.dev/latest/concepts/models/) — nested models, extra-data behavior, validation, and error handling.
- [Pydantic JSON Schema](https://docs.pydantic.dev/latest/concepts/json_schema/) — models as schema-bearing configuration contracts.
- [Binance Spot exchange information](https://developers.binance.com/docs/binance-spot-api-docs/rest-api/general-endpoints#exchange-information) — public symbol metadata, status, assets, permissions, order types, and filters.
- [Binance Spot filters](https://developers.binance.com/docs/binance-spot-api-docs/filters) — `PRICE_FILTER`, `LOT_SIZE`, `MARKET_LOT_SIZE`, `MIN_NOTIONAL`, `NOTIONAL`, and maximum-position semantics.
- [Binance Spot REST overview](https://developers.binance.com/en/docs/products/spot/rest-api) — public market-data host, endpoint security types, and timestamp units.

## Risks and unknowns

- Exchange filter values and even filter presence vary by symbol and can change. Null means “not synchronized,” never “no exchange limit.”
- `ruling_source` records the owner-approved project policy in this phase; the system does not independently issue religious rulings. Human scholarly review can change an asset to pending/rejected without code changes.
- Session names are intentionally small in P01. Later calendar phases may introduce holiday/news closures while preserving the guard interface.
- Cost defaults are conservative configuration assumptions for simulation, not live fee quotes. Later public metadata or account tiers must not silently reduce modeled costs.
