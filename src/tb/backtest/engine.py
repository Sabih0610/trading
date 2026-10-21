"""Pessimistic event-driven simulator for approved long-only Spot assets."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from itertools import pairwise

from pydantic import BaseModel, ConfigDict, Field

from tb.backtest.costs import CostAssumptions
from tb.risk.config import AssetDefinition, load_asset_registry
from tb.risk.guards import OrderSide, assert_tradable
from tb.risk.manager import EntryRequest, RejectionCode, RiskManager, RiskState


class EntryOrderType(StrEnum):
    """Entry instructions supported by the bar simulator."""

    MARKET = "market"
    LIMIT = "limit"


class ExitReason(StrEnum):
    """Deterministic position-closing reasons."""

    STOP = "stop"
    TARGET = "target"
    END_OF_DAY = "end_of_day"
    KILL_SWITCH = "kill_switch"


class Bar(BaseModel):
    """One completed OHLCV bar."""

    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)

    timestamp: datetime
    open: Decimal = Field(gt=0)
    high: Decimal = Field(gt=0)
    low: Decimal = Field(gt=0)
    close: Decimal = Field(gt=0)
    volume: Decimal = Field(ge=0)


class EntrySignal(BaseModel):
    """Strategy proposal observed after one completed bar."""

    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)

    timestamp: datetime
    symbol: str
    side: OrderSide = OrderSide.BUY
    order_type: EntryOrderType = EntryOrderType.MARKET
    limit_price: Decimal | None = Field(default=None, gt=0)
    stop_price: Decimal = Field(gt=0)
    target_price: Decimal = Field(gt=0)
    requested_quantity: Decimal | None = Field(default=None, gt=0)
    participation_rate: Decimal = Field(default=Decimal("0.1"), gt=0, le=1)
    expires_after_bars: int = Field(default=1, ge=1, le=100)


class TradeRecord(BaseModel):
    """One completed inventory round trip with all costs included."""

    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)

    symbol: str
    entry_time: datetime
    exit_time: datetime
    quantity: Decimal
    entry_price: Decimal
    exit_price: Decimal
    entry_fee: Decimal
    exit_fee: Decimal
    pnl: Decimal
    exit_reason: ExitReason


class RejectionRecord(BaseModel):
    """One rejected or unfilled proposal with a stable reason."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    timestamp: datetime
    symbol: str
    reason_code: str
    detail: str


class EquityPoint(BaseModel):
    """End-of-bar marked portfolio state."""

    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)

    timestamp: datetime
    cash: Decimal
    holdings: Decimal
    close: Decimal
    equity: Decimal
    exposure: Decimal


class BacktestResult(BaseModel):
    """Complete deterministic in-memory simulation result."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    trades: tuple[TradeRecord, ...]
    rejections: tuple[RejectionRecord, ...]
    equity: tuple[EquityPoint, ...]


@dataclass(slots=True)
class _PendingEntry:
    signal: EntrySignal
    approved_quantity: Decimal
    eligible_index: int
    expires_index: int


@dataclass(slots=True)
class _Position:
    quantity: Decimal
    entry_time: datetime
    entry_price: Decimal
    entry_fee: Decimal
    entry_cash_out: Decimal
    stop_price: Decimal
    target_price: Decimal


class BacktestEngine:
    """Replay bars with next-event entries, OCO exits, and deterministic risk checks."""

    def __init__(
        self,
        symbol: str,
        *,
        initial_cash: Decimal,
        stress_multiplier: Decimal = Decimal("1"),
        risk_manager: RiskManager | None = None,
        kill_switch_at: datetime | None = None,
    ) -> None:
        if initial_cash <= 0:
            raise ValueError("initial_cash must be positive")
        registry = load_asset_registry()
        asset = assert_tradable(symbol, registry)
        self.asset: AssetDefinition = asset
        self.symbol = asset.symbol
        self.initial_cash = initial_cash
        self.costs = CostAssumptions.from_asset(asset, stress_multiplier=stress_multiplier)
        self.risk_manager = RiskManager() if risk_manager is None else risk_manager
        self.kill_switch_at = kill_switch_at

    @staticmethod
    def _validate_bars(bars: list[Bar]) -> None:
        if not bars:
            raise ValueError("At least one bar is required")
        for previous, current in pairwise(bars):
            if current.timestamp <= previous.timestamp:
                raise ValueError("Bars must be strictly increasing")
        for bar in bars:
            if bar.high < max(bar.open, bar.close, bar.low) or bar.low > min(
                bar.open, bar.close, bar.high
            ):
                raise ValueError("OHLC bounds are inconsistent")

    def run(self, bars: list[Bar], signals: list[EntrySignal]) -> BacktestResult:
        """Run one symbol over completed bars without any external side effect."""

        self._validate_bars(bars)
        signal_by_time = {signal.timestamp: signal for signal in signals}
        if len(signal_by_time) != len(signals):
            raise ValueError("Only one entry signal per timestamp is supported")
        cash = self.initial_cash
        position: _Position | None = None
        pending: _PendingEntry | None = None
        trades: list[TradeRecord] = []
        rejections: list[RejectionRecord] = []
        curve: list[EquityPoint] = []
        active_day = bars[0].timestamp.date()
        start_day_equity = self.initial_cash
        realized_day = Decimal("0")
        entries_today = 0

        def reject(timestamp: datetime, code: str, detail: str) -> None:
            rejections.append(
                RejectionRecord(
                    timestamp=timestamp,
                    symbol=self.symbol,
                    reason_code=code,
                    detail=detail,
                )
            )

        def close_position(bar: Bar, raw_price: Decimal, reason: ExitReason) -> None:
            nonlocal cash, position, realized_day
            if position is None:
                return
            self.risk_manager.validate_inventory_sale(
                self.symbol, position.quantity, position.quantity
            )
            exit_price = self.costs.exit_price(raw_price)
            proceeds = position.quantity * exit_price
            exit_fee = self.costs.fee(proceeds)
            cash_in = proceeds - exit_fee
            pnl = cash_in - position.entry_cash_out
            cash += cash_in
            realized_day += pnl
            trades.append(
                TradeRecord(
                    symbol=self.symbol,
                    entry_time=position.entry_time,
                    exit_time=bar.timestamp,
                    quantity=position.quantity,
                    entry_price=position.entry_price,
                    exit_price=exit_price,
                    entry_fee=position.entry_fee,
                    exit_fee=exit_fee,
                    pnl=pnl,
                    exit_reason=reason,
                )
            )
            position = None

        def process_exit(bar: Bar) -> None:
            if position is None:
                return
            if bar.open <= position.stop_price:
                close_position(bar, bar.open, ExitReason.STOP)
            elif bar.low <= position.stop_price:
                close_position(bar, position.stop_price, ExitReason.STOP)
            elif bar.high >= position.target_price:
                close_position(bar, position.target_price, ExitReason.TARGET)

        for index, bar in enumerate(bars):
            if bar.timestamp.date() != active_day:
                active_day = bar.timestamp.date()
                start_day_equity = cash + (
                    Decimal("0") if position is None else position.quantity * bar.open
                )
                realized_day = Decimal("0")
                entries_today = 0
            kill_active = self.kill_switch_at is not None and bar.timestamp >= self.kill_switch_at
            if kill_active:
                if position is not None:
                    close_position(bar, bar.open, ExitReason.KILL_SWITCH)
                if pending is not None:
                    reject(bar.timestamp, "kill_switch", "Pending entry canceled by kill switch")
                    pending = None
            process_exit(bar)

            if pending is not None and position is None and index >= pending.eligible_index:
                if index > pending.expires_index:
                    reject(bar.timestamp, "expired", "Entry expired before a valid fill")
                    pending = None
                else:
                    pending_signal = pending.signal
                    raw_fill = (
                        bar.open
                        if pending_signal.order_type is EntryOrderType.MARKET
                        else pending_signal.limit_price
                    )
                    touched = pending_signal.order_type is EntryOrderType.MARKET or (
                        raw_fill is not None and bar.low <= raw_fill
                    )
                    if touched and raw_fill is not None:
                        fill_price = self.costs.entry_price(raw_fill)
                        fee_rate = self.costs.stressed_fee_bps / Decimal("10000")
                        cash_quantity = cash / (fill_price * (Decimal("1") + fee_rate))
                        volume_quantity = bar.volume * pending_signal.participation_rate
                        quantity = min(pending.approved_quantity, cash_quantity, volume_quantity)
                        if quantity > 0:
                            notional = quantity * fill_price
                            entry_fee = self.costs.fee(notional)
                            cash_out = notional + entry_fee
                            cash -= cash_out
                            position = _Position(
                                quantity=quantity,
                                entry_time=bar.timestamp,
                                entry_price=fill_price,
                                entry_fee=entry_fee,
                                entry_cash_out=cash_out,
                                stop_price=pending_signal.stop_price,
                                target_price=pending_signal.target_price,
                            )
                            entries_today += 1
                            pending = None
                            process_exit(bar)
                        else:
                            reject(bar.timestamp, "no_fill_capacity", "No cash or bar volume")
                            pending = None

            proposed_signal = signal_by_time.get(bar.timestamp)
            if proposed_signal is not None:
                if position is not None or pending is not None:
                    reject(bar.timestamp, "position_busy", "An entry or position already exists")
                elif proposed_signal.symbol.strip().upper() != self.symbol:
                    reject(bar.timestamp, "symbol_mismatch", "Signal symbol differs from engine")
                else:
                    reference = (
                        proposed_signal.limit_price
                        if proposed_signal.order_type is EntryOrderType.LIMIT
                        else bar.close
                    )
                    if reference is None:
                        reject(bar.timestamp, "limit_price_missing", "Limit entry needs a price")
                    else:
                        equity = cash
                        decision = self.risk_manager.evaluate_entry(
                            EntryRequest(
                                symbol=self.symbol,
                                side=proposed_signal.side,
                                timestamp=bar.timestamp,
                                entry_price=reference,
                                stop_price=proposed_signal.stop_price,
                                requested_quantity=proposed_signal.requested_quantity,
                            ),
                            RiskState(
                                equity=equity,
                                cash=cash,
                                current_exposure=Decimal("0"),
                                current_holdings=Decimal("0"),
                                realized_pnl_day=realized_day,
                                start_of_day_equity=start_day_equity,
                                completed_trades_today=entries_today,
                                kill_switch=kill_active,
                            ),
                        )
                        if decision.approved:
                            pending = _PendingEntry(
                                signal=proposed_signal,
                                approved_quantity=decision.quantity,
                                eligible_index=index + 1,
                                expires_index=index + proposed_signal.expires_after_bars,
                            )
                        else:
                            code = decision.reason_code or RejectionCode.NO_CAPACITY
                            reject(bar.timestamp, code.value, decision.detail or "Rejected")

            next_day = index + 1 == len(bars) or bars[index + 1].timestamp.date() != active_day
            if next_day and position is not None:
                close_position(bar, bar.close, ExitReason.END_OF_DAY)
            if next_day and pending is not None:
                reject(bar.timestamp, "end_of_day_cancel", "Pending entry canceled at day end")
                pending = None
            holdings = Decimal("0") if position is None else position.quantity
            exposure = holdings * bar.close
            curve.append(
                EquityPoint(
                    timestamp=bar.timestamp,
                    cash=cash,
                    holdings=holdings,
                    close=bar.close,
                    equity=cash + exposure,
                    exposure=exposure,
                )
            )
        return BacktestResult(
            trades=tuple(trades), rejections=tuple(rejections), equity=tuple(curve)
        )
