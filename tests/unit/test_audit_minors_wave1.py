"""Owned regressions for J1 risk boundaries, uniform chart lock and startup policy."""

import json
import logging
from datetime import UTC, datetime, timedelta
from decimal import Decimal, localcontext

import polars as pl
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from tb.backtest.costs import CostAssumptions
from tb.core.config import Settings, log_disabled_features
from tb.core.logging import configure_logging
from tb.dashboard.readers import EvidenceUnavailable, marked_drawdown, parquet_rows
from tb.risk.config import PolicyBundle, SpotSymbolRules, load_policy_bundle
from tb.risk.manager import EntryRequest, RejectionCode, RiskManager, RiskState

START = datetime(2024, 1, 2, 12, tzinfo=UTC)


def state(equity=Decimal("10000")):
    return RiskState(
        equity=equity,
        cash=equity,
        current_exposure=0,
        current_holdings=0,
        realized_pnl_day=0,
        start_of_day_equity=equity,
        completed_trades_today=0,
    )


def request(symbol="BTCUSDT", market="spot"):
    return EntryRequest(
        symbol=symbol, market=market, timestamp=START, entry_price=100, stop_price=95
    )


@pytest.mark.parametrize("symbol", ["btcusdt", " BTCUSDT", "BTCUSDT ", " btcusdt ", "", "unknown"])
def test_noncanonical_or_unknown_symbols_return_rejections(symbol):
    decision = RiskManager().evaluate_entry(request(symbol), state())
    assert not decision.approved and decision.quantity == 0
    assert decision.reason_code is RejectionCode.ASSET_POLICY


@pytest.mark.parametrize("market", ["", " ", "\t"])
def test_blank_market_is_a_rejection_not_validation_exception(market):
    decision = RiskManager().evaluate_entry(request(market=market), state())
    assert not decision.approved
    assert decision.reason_code is RejectionCode.MARKET_POLICY


@settings(max_examples=60)
@given(
    equity=st.decimals(min_value="1", max_value="1000000", places=6),
    price=st.decimals(min_value="0.001", max_value="100000", places=6),
)
def test_null_filters_cannot_exceed_exact_risk_cash_or_exposure(equity, price):
    manager = RiskManager()
    asset = manager.bundle.registry.asset("BTCUSDT")
    assert asset is not None and asset.exchange_rules is None
    costs = CostAssumptions.from_asset(asset, stress_multiplier=Decimal("2.37"))
    proposal = request().model_copy(
        update={"entry_price": price, "stop_price": price * Decimal("0.973")}
    )
    decision = manager.evaluate_entry(proposal, state(equity), costs=costs)
    assert decision.approved
    with localcontext() as context:
        context.prec = 100
        entry = costs.entry_price(price)
        stop = costs.exit_price(proposal.stop_price)
        distance = entry - stop + costs.fee(entry) + costs.fee(stop)
        assert decision.quantity * distance <= equity * Decimal("0.5") / 100
        assert decision.quantity * (entry + costs.fee(entry)) <= equity
        assert decision.quantity * entry <= equity


def test_step_floor_cannot_round_almost_three_steps_up():
    bundle = load_policy_bundle()
    rules = SpotSymbolRules(step_size=Decimal("0.1"))
    assets = tuple(
        a.model_copy(update={"exchange_rules": rules}) if a.symbol == "BTCUSDT" else a
        for a in bundle.registry.assets
    )
    manager = RiskManager(
        PolicyBundle(
            registry=bundle.registry.model_copy(update={"assets": assets}), risk=bundle.risk
        )
    )
    proposed = Decimal("0.29999999999999999999999999999")
    decision = manager.constrain_fill("BTCUSDT", proposed, Decimal("100"), market_order=True)
    assert decision.approved and decision.quantity == Decimal("0.2")
    assert decision.quantity <= proposed


def chart(folder, timestamps, *, time_end):
    pl.DataFrame(
        dict(
            timestamp=timestamps,
            equity=[100.0] * len(timestamps),
            cash=[100.0] * len(timestamps),
            holdings=[0.0] * len(timestamps),
        )
    ).write_parquet(folder / "equity.parquet")
    (folder / "equity.manifest.json").write_text(
        json.dumps(
            dict(
                mode="synthetic",
                time_end=time_end,
                source="owned test",
                checksum="a" * 64,
                row_count=len(timestamps),
                code_version="owned",
                series_type="marked",
            )
        )
    )


def test_synthetic_label_never_bypasses_manifest_holdout(tmp_path, monkeypatch):
    chart(tmp_path, [START], time_end="2025-01-01T00:00:00Z")
    monkeypatch.setattr(pl, "scan_parquet", lambda *a, **k: pytest.fail("locked manifest scanned"))
    with pytest.raises(EvidenceUnavailable):
        parquet_rows(tmp_path, "equity", "synthetic")


def test_forged_synthetic_manifest_cannot_hide_late_holdout_after_page(tmp_path):
    timestamps = [START + timedelta(minutes=i) for i in range(2000)] + [
        datetime(2025, 1, 1, tzinfo=UTC)
    ]
    chart(tmp_path, timestamps, time_end="2024-01-04T00:00:00Z")
    with pytest.raises(EvidenceUnavailable):
        parquet_rows(tmp_path, "equity", "synthetic")
    assert marked_drawdown(tmp_path, "synthetic") is None


def test_missing_features_log_once_by_name_without_values(monkeypatch, caplog):
    monkeypatch.setattr("tb.core.config._DISABLED_FEATURES_LOGGED", set())
    caplog.set_level(logging.INFO)
    values = {name: None for name in Settings.model_fields}
    values["openai_api_key"] = "owned-key-must-not-appear"
    configuration = Settings(_env_file=None, **values)
    log_disabled_features(configuration)
    first = list(caplog.records)
    log_disabled_features(configuration)
    assert caplog.records == first
    features = [r.feature for r in first if r.name == "tb.optional_features"]
    assert "fred" in features and "openai" not in features
    assert len(features) == len(set(features))
    assert "owned-key-must-not-appear" not in caplog.text
    assert all(
        r.reason == "missing_configuration" for r in first if r.name == "tb.optional_features"
    )


def test_console_logs_leave_machine_readable_stdout_clean(tmp_path, capfd):
    logger = configure_logging(log_dir=tmp_path, console=True)
    logger.info("owned-startup-status")
    output = capfd.readouterr()
    assert "owned-startup-status" in output.err
    assert "owned-startup-status" not in output.out


def test_null_filter_fill_precision_never_rounds_quantity_up():
    proposed = Decimal("0.29999999999999999999999999999999")
    result = RiskManager().constrain_fill("BTCUSDT", proposed, Decimal("100"), market_order=True)
    assert result.approved and 0 < result.quantity <= proposed
    assert len(result.quantity.as_tuple().digits) <= 28


@pytest.mark.parametrize("stamp", ["invalid", 42])
def test_malformed_chart_timestamp_type_refuses_cleanly(tmp_path, stamp):
    chart(tmp_path, [stamp], time_end="2024-01-04T00:00:00Z")
    with pytest.raises(EvidenceUnavailable):
        parquet_rows(tmp_path, "equity", "synthetic")


def test_null_filter_rounding_to_zero_rejects_instead_of_approving_an_empty_fill():
    result = RiskManager().constrain_fill(
        "BTCUSDT", Decimal("1e-1000030"), Decimal("100"), market_order=True
    )
    assert not result.approved and result.quantity == 0
    assert result.reason_code is RejectionCode.NO_CAPACITY
