"""Unit coverage for the closed asset and risk policy schemas."""

from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import ValidationError

from tb.core.config import ConfigLoadError
from tb.risk.config import (
    AssetRegistry,
    AssetRole,
    PolicyBundle,
    RiskLimits,
    ShariahStatus,
    SpotSymbolRules,
    effective_risk_limits,
    load_asset_registry,
    load_risk_config,
)


def test_default_registry_has_exact_policy_universe() -> None:
    registry = load_asset_registry()

    assert {asset.symbol for asset in registry.assets} == {
        "XAUTUSDT",
        "BTCUSDT",
        "ETHUSDT",
        "SOLUSDT",
        "XAUUSD",
        "EURUSD",
        "USDJPY",
        "GBPUSD",
        "USDCAD",
        "USDSEK",
        "USDCHF",
        "WTI",
        "US10Y",
        "PAXGUSDT",
    }
    tradable = {asset.symbol for asset in registry.assets if asset.role is AssetRole.TRADABLE}
    assert tradable == {"XAUTUSDT", "BTCUSDT", "ETHUSDT", "SOLUSDT"}
    assert all(
        asset.shariah_status is ShariahStatus.APPROVED
        for asset in registry.assets
        if asset.role is AssetRole.TRADABLE
    )


def test_two_percent_risk_configuration_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "risk.yaml"
    path.write_text(
        """schema_version: 1
limits:
  risk_per_trade_pct: "2"
  max_total_exposure_multiple: "1"
  daily_loss_limit_pct: "3"
  max_trades_per_day_per_asset: 3
  flat_by_end_of_day: true
  allow_xaut_weekend_entries: false
""",
        encoding="utf-8",
    )

    with pytest.raises(ConfigLoadError, match="risk_per_trade_pct=2 exceeds hard ceiling 1"):
        load_risk_config(path)


def test_unknown_risk_field_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "risk.yaml"
    path.write_text(
        """schema_version: 1
limits:
  risk_per_trade_pct: "1"
  max_total_exposure_multiple: "1"
  daily_loss_limit_pct: "3"
  max_trades_per_day_per_asset: 3
  flat_by_end_of_day: true
  allow_xaut_weekend_entries: false
  disable_checks: true
""",
        encoding="utf-8",
    )

    with pytest.raises(ConfigLoadError, match="disable_checks"):
        load_risk_config(path)


def test_stricter_asset_override_is_effective() -> None:
    registry = load_asset_registry()
    global_limits = load_risk_config().limits
    xaut = registry.asset("XAUTUSDT")

    assert xaut is not None
    effective = effective_risk_limits(xaut, global_limits)
    assert effective.risk_per_trade_pct == Decimal("0.25")
    assert effective.max_trades_per_day_per_asset == 2
    assert effective.daily_loss_limit_pct == Decimal("2.0")


def test_override_cannot_be_looser_than_active_global_limit() -> None:
    registry = load_asset_registry()
    configured = load_risk_config()
    strict_limits = configured.limits.model_copy(update={"risk_per_trade_pct": Decimal("0.1")})
    strict_config = configured.model_copy(update={"limits": strict_limits})

    with pytest.raises(ValidationError, match=r"XAUTUSDT override risk_per_trade_pct=0\.25"):
        PolicyBundle(registry=registry, risk=strict_config)


def test_duplicate_symbols_are_rejected() -> None:
    asset = load_asset_registry().assets[0]

    with pytest.raises(ValidationError, match="duplicate asset symbols: XAUTUSDT"):
        AssetRegistry(schema_version=1, assets=(asset, asset))


def test_exchange_rules_allow_unknown_values_but_reject_inverted_ranges() -> None:
    empty = SpotSymbolRules()

    assert empty.tick_size is None
    with pytest.raises(ValidationError, match="min_qty cannot exceed max_qty"):
        SpotSymbolRules(min_qty=Decimal("2"), max_qty=Decimal("1"))


@pytest.mark.parametrize("bad", [11, 0, -1, 1.5, 10.0, True, "10"])
def test_owner_holding_bound_is_strict_and_compiled(bad: object) -> None:
    # test changed because the owner changed the rule (AGENTS.md 2026-11-05)
    with pytest.raises(ValidationError):
        RiskLimits.model_validate(
            {**load_risk_config().limits.model_dump(), "max_holding_days": bad}
        )


def test_owner_allows_overnight_but_preserves_other_hard_switch() -> None:
    limits = load_risk_config().limits
    assert limits.max_holding_days == 10 and limits.flat_by_end_of_day is False
    with pytest.raises(ValidationError, match="allow_xaut_weekend_entries"):
        RiskLimits.model_validate({**limits.model_dump(), "allow_xaut_weekend_entries": True})


@pytest.mark.parametrize("bad", [0, 1, "true", "false", None, 0.0, 1.0, [], {}])
def test_global_eod_mode_refuses_implicit_boolean_coercion(bad: object) -> None:
    with pytest.raises(ValidationError):
        RiskLimits.model_validate(
            {**load_risk_config().limits.model_dump(), "flat_by_end_of_day": bad}
        )


@pytest.mark.parametrize("mode", [True, False])
def test_global_eod_mode_accepts_actual_human_boolean_only(mode: bool) -> None:
    limits = RiskLimits.model_validate(
        {**load_risk_config().limits.model_dump(), "flat_by_end_of_day": mode}
    )
    assert limits.flat_by_end_of_day is mode
    assert limits.max_holding_days == 10
