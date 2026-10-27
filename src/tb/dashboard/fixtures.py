"""Explicit offline fixture export command; never imported by the dashboard application."""

from __future__ import annotations

import argparse
import json
from decimal import Decimal
from pathlib import Path
from typing import Any

import polars as pl

from tb.agents.schemas import ArenaAction, ArenaAnswer
from tb.backtest.engine import BacktestEngine, Bar, EntrySignal
from tb.ingest.history.core import atomic_write_json, sha256_file
from tb.ledger.store import DecisionLedger
from tb.paper.simulation import VERSIONS, LocalPaperSimulator
from tb.paper.smoke import create_alignment_smoke, fixture_market
from tb.risk.account import AccountCircuitBreaker, SafetyState
from tb.risk.config import load_policy_bundle


def _chart(folder: Path, name: str, rows: list[dict[str, Any]]) -> None:
    path = folder / (name + ".parquet")
    pl.DataFrame(rows).write_parquet(path)
    atomic_write_json(
        path.with_suffix(".manifest.json"),
        dict(
            mode="synthetic",
            source="P09.5 offline tools; P10 fixture export",
            code_version="p10-v1",
            time_start=rows[0]["timestamp"].isoformat(),
            time_end=rows[-1]["timestamp"].isoformat(),
            row_count=len(rows),
            checksum=sha256_file(path),
            series_type="marked" if name == "equity" else "bid",
        ),
    )


def create_dashboard_fixtures(root: Path) -> Path:
    """Write a fresh, reproducible collection using existing simulation and journal tools."""

    if root.exists():
        raise FileExistsError("Use a fresh fixture directory to preserve existing journals")
    root.mkdir(parents=True)
    raw = json.loads(create_alignment_smoke(root / "raw").read_text(encoding="utf-8"))
    sources: list[dict[str, Any]] = []
    for ident, symbol, capital, shock, veto in (
        ("btc-profit", "BTCUSDT", "100", False, False),
        ("gold-gap", "XAUUSD", "10000", True, False),
        ("eur-profit", "EURUSD", "10000", False, False),
        ("gold-small", "XAUUSD", "100", False, False),
        ("eur-small", "EURUSD", "100", False, False),
        ("ai-veto", "BTCUSDT", "100", False, True),
        ("empty", "BTCUSDT", "100", False, False),
    ):
        folder = root / ident
        folder.mkdir()
        spec, quotes, conversions, candidates = fixture_market(symbol, shock=shock)
        trades: list[dict[str, Any]] = []
        equity: list[dict[str, Any]] = []
        rejection: str | None = None
        if ident == "btc-profit":
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
            proposal = candidates[0]
            result = BacktestEngine(symbol, initial_cash=Decimal(capital)).run(
                bars,
                [
                    EntrySignal(
                        timestamp=proposal.timestamp,
                        symbol=symbol,
                        stop_price=proposal.stop,
                        target_price=proposal.target,
                    )
                ],
            )
            for replay_trade in result.trades:
                trades.append(
                    replay_trade.model_dump(mode="json")
                    | {
                        "lots": str(replay_trade.quantity),
                        "fees": str(replay_trade.entry_fee + replay_trade.exit_fee),
                    }
                )
            ending = result.equity[-1].cash
            equity = [
                dict(
                    timestamp=p.timestamp,
                    equity=float(p.equity),
                    cash=float(p.cash),
                    holdings=float(p.holdings),
                )
                for p in result.equity
            ]
        elif veto:
            answer = ArenaAnswer(
                decision="skip",
                confidence=0.5,
                reason_code="FIXTURE_VETO",
                key_risk="Synthetic advisory fixture",
                action=ArenaAction.VETO,
            )
            simulated = LocalPaperSimulator(
                symbol,
                spec,
                initial_cash=Decimal(capital),
                account_currency=spec.quote_currency,
                ledger_path=folder / "raw.sqlite",
            ).run(quotes, candidates, conversions, advisory=answer)
            assert not simulated.trades
            ending = simulated.ending_cash
            rejection = "FIXTURE_VETO: synthetic advisory declined the prior candidate"
        elif ident == "empty":
            ending = Decimal(capital)
        else:
            example = raw["examples"][f"{symbol}-{capital}"]
            trades = example["trades"]
            ending = Decimal(example["ending_cash"])
            rejection = example["rejections"][0] if example["rejections"] else None
        ledger = DecisionLedger(folder / "journal.sqlite")
        if ident != "empty":
            candidate = candidates[0]
            status = "vetoed" if veto else "rejected" if rejection else "accepted"
            decision_id = ledger.append_decision(
                dict(
                    mode="synthetic",
                    timestamp=candidate.timestamp.isoformat(),
                    symbol=symbol,
                    strategy="fixture_momentum",
                    direction="buy",
                    status=status,
                    intended_size=str(candidate.requested_lots),
                    entry=str(quotes[1].ask),
                    stop=str(candidate.stop),
                    target=str(candidate.target),
                    reason=rejection or "RISK_APPROVED",
                    candidate=candidate.model_dump(mode="json"),
                ),
                VERSIONS,
            )
            for trade in trades:
                ledger.append_outcome(decision_id, dict(trade, mode="synthetic"), VERSIONS)
            if ident == "btc-profit":
                ledger.append_decision(
                    dict(
                        mode="synthetic",
                        timestamp=quotes[-1].timestamp.isoformat(),
                        symbol=symbol,
                        strategy="fixture_momentum",
                        status="skipped",
                        reason="Fixture has no second strategy proposal",
                    ),
                    VERSIONS,
                )
        as_of = quotes[-1].timestamp
        pnl = sum((Decimal(t["pnl"]) for t in trades), Decimal("0"))
        atomic_write_json(
            folder / "account.json",
            dict(
                mode="synthetic",
                currency=spec.quote_currency,
                as_of=as_of.isoformat(),
                initial_cash=capital,
                equity=str(ending),
                cash=str(ending),
                realized_pnl=str(pnl),
                unrealized_pnl="0",
                closed_trade_count=len(trades),
            ),
        )
        _chart(folder, "prices", [dict(timestamp=q.timestamp, price=float(q.bid)) for q in quotes])
        if equity:
            _chart(folder, "equity", equity)
        circuit = AccountCircuitBreaker(
            SafetyState(day=as_of.date(), day_start=Decimal(capital), peak=Decimal(capital)),
            load_policy_bundle().risk.limits,
        )
        for point in equity:
            circuit.observe(point["timestamp"], Decimal(str(point["equity"])))
        circuit.observe(as_of, ending)
        atomic_write_json(
            folder / "risk-state.json",
            dict(
                mode="synthetic",
                observed_at=as_of.isoformat(),
                source="Offline circuit fixture, not a running account",
                **circuit.state.model_dump(mode="json"),
            ),
        )
        sources.append(
            dict(
                id=ident,
                title=f"{symbol} · {ident} · {capital} {spec.quote_currency}",
                path=ident,
                mode="synthetic",
                symbol=symbol,
                currency=spec.quote_currency,
                strategy="fixture_momentum",
            )
        )
    index = root / "index.json"
    atomic_write_json(index, dict(schema_version=1, sources=sources))
    return index


def main() -> None:
    """Generate explicitly labelled demo evidence outside the UI process."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root", type=Path, default=Path("reports/dashboard/P10-demo"))
    args = parser.parse_args()
    print(create_dashboard_fixtures(args.output_root))


if __name__ == "__main__":
    main()
