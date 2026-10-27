"""P09.5 offline mechanics examples; all input prices and contracts are synthetic."""

from __future__ import annotations

import argparse
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

from tb.backtest.engine import BacktestEngine, Bar, EntrySignal
from tb.backtest.research import assess_research, load_research_policies
from tb.core.instruments import ContractSpec, CurrencyConversion, MarketQuote
from tb.features.engine import FeatureEngine
from tb.ingest.history.core import atomic_write_json, sha256_file
from tb.ledger.store import DecisionLedger
from tb.paper.simulation import (
    VERSIONS,
    LocalPaperSimulator,
    SimulatedCandidate,
    SimulationResult,
)


def fixture_market(
    symbol: str, *, shock: bool = False
) -> tuple[ContractSpec, list[MarketQuote], list[CurrencyConversion], list[SimulatedCandidate]]:
    """Construct a labelled fixture and a candidate using the existing causal feature engine."""

    start = datetime(2024, 1, 2, 12, tzinfo=UTC)
    settings = {
        "BTCUSDT": ("spot", "100", "1", "0.01", "0.001", "USDT"),
        "XAUUSD": ("gold_contract", "2000", "100", "0.01", "0.01", "USD"),
        "EURUSD": ("fx_contract", "1.10000", "100000", "0.00001", "0.01", "USD"),
    }
    kind, base_text, units, tick_text, step, currency = settings[symbol]
    base, tick = Decimal(base_text), Decimal(tick_text)
    spec = ContractSpec.model_validate(
        dict(
            symbol=symbol,
            instrument_type=kind,
            quote_currency=currency,
            contract_size=units,
            tick_size=tick,
            pip_size="0.0001" if symbol == "EURUSD" else tick_text,
            min_lots=step,
            max_lots="100",
            lot_step=step,
            min_notional="0",
            fee_bps="10" if kind == "spot" else "1",
            slippage_ticks=1,
            observed_at=start,
            source="P09.5 synthetic fixture; no broker data",
            synthetic=True,
        )
    )
    bids = [base, base + tick * 10, base + tick * 10, base + tick * 400]
    if shock:
        bids[-1] = base / 10
    quotes = [
        MarketQuote(
            symbol=symbol, timestamp=start + timedelta(minutes=index), bid=bid, ask=bid + tick * 2
        )
        for index, bid in enumerate(bids)
    ]
    conversions = [
        CurrencyConversion(
            quote_currency=currency,
            account_currency=currency,
            rate=Decimal("1"),
            observed_at=q.timestamp,
            source="fixture identity",
        )
        for q in quotes
    ]
    engine = FeatureEngine()
    candidates: list[SimulatedCandidate] = []
    for index, quote in enumerate(quotes):
        feature = engine.update(
            dict(
                timestamp_utc=quote.timestamp,
                open=float(quote.bid),
                high=float(quote.ask),
                low=float(quote.bid),
                close=float(quote.bid),
                volume=Decimal("100"),
                trading_day_id=quote.timestamp.date().isoformat(),
                session_asia=False,
                session_london=True,
                session_new_york=True,
            )
        )
        if index == 1 and feature["ema20_slope"] is not None and feature["ema20_slope"] > 0:
            candidates.append(
                SimulatedCandidate(
                    symbol=symbol,
                    timestamp=quote.timestamp,
                    stop=base - tick * 100,
                    target=base + tick * 300,
                    requested_lots=Decimal("1"),
                )
            )
    return spec, quotes, conversions, candidates


def create_alignment_smoke(output_root: Path) -> Path:
    """Write reproducible examples, manifests and append-only decision/outcome evidence."""

    output_root.mkdir(parents=True, exist_ok=True)
    examples: dict[str, object] = {}
    fixture_inputs: dict[str, object] = {}
    fixture_row_count = 0
    for symbol, cash, shock in (
        ("BTCUSDT", "100", False),
        ("XAUUSD", "10000", True),
        ("EURUSD", "10000", False),
        ("XAUUSD", "100", False),
        ("EURUSD", "100", False),
    ):
        spec, quotes, conversions, candidates = fixture_market(symbol, shock=shock)
        label = f"{symbol}-{cash}"
        fixture_row_count += len(quotes)
        result: SimulationResult = LocalPaperSimulator(
            symbol,
            spec,
            initial_cash=Decimal(cash),
            account_currency=spec.quote_currency,
            ledger_path=output_root / f"{label}.sqlite",
        ).run(quotes, candidates, conversions)
        examples[label] = result.model_dump(mode="json")
        fixture_inputs[label] = {
            "metadata": spec.model_dump(mode="json"),
            "quotes": [q.model_dump(mode="json") for q in quotes],
        }

    # Exercise the reused P06 Spot backtester separately, including gap-triggered shutdown.
    spec, quotes, _, _ = fixture_market("BTCUSDT")
    bars = [
        Bar(
            timestamp=q.timestamp,
            open=q.bid,
            high=q.ask,
            low=q.bid,
            close=q.bid,
            volume=Decimal("100"),
        )
        for q in quotes
    ]
    bars[-1] = bars[-1].model_copy(
        update={
            "open": Decimal("50"),
            "high": Decimal("50"),
            "low": Decimal("50"),
            "close": Decimal("50"),
        }
    )
    signal = EntrySignal(
        timestamp=bars[1].timestamp,
        symbol="BTCUSDT",
        stop_price=Decimal("99"),
        target_price=Decimal("110"),
    )
    spot = BacktestEngine("BTCUSDT", initial_cash=Decimal("100")).run(bars, [signal])
    ledger = DecisionLedger(output_root / "legacy-spot.sqlite")
    decision_id = ledger.append_decision(
        {"mode": "simulated", "candidate": signal.model_dump(mode="json")}, VERSIONS
    )
    for trade in spot.trades:
        ledger.append_outcome(
            decision_id, {"mode": "simulated", **trade.model_dump(mode="json")}, VERSIONS
        )
    examples["legacy_spot_backtester"] = {"mode": "simulated", **spot.model_dump(mode="json")}
    policies = load_research_policies()
    summary = dict(
        phase="P09.5",
        mode="synthetic",
        empirical_trials=0,
        final_test_reads=0,
        paid_calls=0,
        description="Synthetic accounting/safety examples only; no historical profitability claim",
        examples=examples,
        research={
            p.symbol: assess_research(p, None).model_dump(mode="json") for p in policies.instruments
        },
    )
    inputs_path = output_root / "synthetic-inputs.json"
    atomic_write_json(inputs_path, fixture_inputs)
    atomic_write_json(
        output_root / "_manifest.json",
        dict(
            source="P09.5 synthetic fixtures",
            synthetic=True,
            code_version="p09.5-v1",
            time_start=quotes[0].timestamp.isoformat(),
            time_end=quotes[-1].timestamp.isoformat(),
            row_count=fixture_row_count,
            checksum=sha256_file(inputs_path),
        ),
    )
    destination = output_root / "P09.5.json"
    atomic_write_json(destination, summary)
    return destination


def main() -> None:
    """Run the entirely local example without loading credentials or external providers."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root", type=Path, default=Path("reports/safety/P09.5"))
    args = parser.parse_args()
    print(create_alignment_smoke(args.output_root))


if __name__ == "__main__":
    main()
