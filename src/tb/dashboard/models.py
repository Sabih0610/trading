"""Evidence contracts and decimal metrics; missing records never become zero profits."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Literal
from zoneinfo import ZoneInfo

from pydantic import AwareDatetime, Field

from tb.core.contracts import EvidenceMode
from tb.risk.account import SafetyState
from tb.risk.config import PolicyModel


class EvidenceSource(PolicyModel):
    """One isolated account/export with explicit currency and evidence mode."""

    id: str = Field(pattern=r"^[a-z0-9_-]{1,64}$")
    title: str = Field(max_length=100)
    path: str
    mode: EvidenceMode
    symbol: str = Field(pattern=r"^[A-Z0-9]{3,20}$")
    currency: str = Field(pattern=r"^[A-Z]{3,5}$")
    strategy: str = "unavailable"


class AccountRecord(PolicyModel):
    """Writer-produced account snapshot, with no inferred starting capital."""

    mode: EvidenceMode
    currency: str
    as_of: AwareDatetime
    initial_cash: Decimal = Field(gt=0)
    equity: Decimal
    cash: Decimal
    realized_pnl: Decimal
    unrealized_pnl: Decimal
    closed_trade_count: int = Field(ge=0)


class RiskObservation(SafetyState):
    """Typed archived observation, distinct from current account health."""

    mode: EvidenceMode
    observed_at: AwareDatetime
    source: str = Field(max_length=200)


class DecisionView(PolicyModel):
    """Only whitelisted, masked journal fields reach the UI."""

    rowid: int
    id: str
    timestamp: AwareDatetime | None = None
    symbol: str | None = None
    strategy: str | None = None
    status: str
    direction: str | None = None
    intended_size: Decimal | None = None
    entry: Decimal | None = None
    stop: Decimal | None = None
    target: Decimal | None = None
    fill: Decimal | None = None
    filled_size: Decimal | None = None
    fill_time: AwareDatetime | None = None
    exit: Decimal | None = None
    exit_time: AwareDatetime | None = None
    fees: Decimal | None = None
    pnl: Decimal | None = None
    reason: str | None = None
    outcome_id: str | None = None


class DecisionPage(PolicyModel):
    """A bounded page with a rowid cursor, independent of account aggregates."""

    rows: tuple[DecisionView, ...] = ()
    next_cursor: int | None = None
    issues: tuple[str, ...] = ()


class LedgerTotals(PolicyModel):
    """Streaming totals over all outcomes, never just the visible decision page."""

    trade_count: int = 0
    wins: int = 0
    gross_profit: Decimal = Decimal("0")
    gross_loss: Decimal = Decimal("0")
    pnl: Decimal = Decimal("0")
    fees: Decimal = Decimal("0")
    invalid_rows: int = 0
    available: bool = False


class AccountMetrics(PolicyModel):
    """Unavailable metrics are null; undefined ratios are never presented as infinity."""

    equity: Decimal | None = None
    cash: Decimal | None = None
    realized_pnl: Decimal | None = None
    unrealized_pnl: Decimal | None = None
    return_pct: Decimal | None = None
    trade_count: int | None = None
    win_rate_pct: Decimal | None = None
    profit_factor: Decimal | None = None
    max_drawdown_pct: Decimal | None = None
    issue: str | None = None


def account_metrics(
    account: AccountRecord | None, totals: LedgerTotals, drawdown: Decimal | None = None
) -> AccountMetrics:
    """Reconcile stored account facts with complete decimal outcome aggregates."""

    if account is None:
        return AccountMetrics(issue="Account snapshot unavailable")
    consistent = (
        totals.available
        and totals.invalid_rows == 0
        and totals.trade_count == account.closed_trade_count
        and abs(totals.pnl - account.realized_pnl) < Decimal("0.000001")
    )
    return AccountMetrics(
        equity=account.equity,
        cash=account.cash,
        realized_pnl=account.realized_pnl,
        unrealized_pnl=account.unrealized_pnl,
        return_pct=(account.equity / account.initial_cash - 1) * 100,
        trade_count=totals.trade_count if consistent else None,
        win_rate_pct=(Decimal(totals.wins) / totals.trade_count * 100)
        if consistent and totals.trade_count
        else None,
        profit_factor=totals.gross_profit / totals.gross_loss
        if consistent and totals.gross_loss > 0
        else None,
        max_drawdown_pct=drawdown,
        issue=None
        if consistent
        else "Outcome evidence incomplete or differs from account snapshot",
    )


def display_time(instant: datetime | None, zone: Literal["UTC", "Asia/Karachi"]) -> str:
    """Convert an aware instant for presentation while storage remains UTC."""

    if instant is None:
        return "Unavailable"
    if instant.tzinfo is None:
        raise ValueError("Display timestamps must be timezone-aware")
    return instant.astimezone(ZoneInfo(zone)).strftime("%Y-%m-%d %H:%M:%S %Z")


def freshness(instant: datetime | None, now: datetime | None = None) -> str:
    """Report observed health freshness; missing evidence is never healthy."""

    if instant is None:
        return "Unavailable"
    age = ((now or datetime.now(UTC)) - instant).total_seconds()
    if age < 0:
        return "Future timestamp; invalid"
    return "Recent observation" if age <= 60 else "Stale observation"
