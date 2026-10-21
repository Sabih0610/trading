from datetime import UTC, datetime
from pathlib import Path

import pytest

from tb.core.config import ConfigLoadError
from tb.strategies.scenarios import load_scenarios, scenario_membership


def test_default_catalog_has_required_scenarios_and_no_final_dates() -> None:
    catalog = load_scenarios()

    assert {scenario.id for scenario in catalog.scenarios} == {
        "crash_2020_03",
        "rate_hike_pressure_2022",
        "banking_stress_2023_03",
        "gold_rally_2024",
        "quiet_ranges",
        "scheduled_news",
        "thin_liquidity",
    }
    assert all(scenario.end is None or scenario.end.year <= 2024 for scenario in catalog.scenarios)


def test_scenario_membership_combines_fixed_and_rule_selected_cases() -> None:
    catalog = load_scenarios()

    matches = scenario_membership(
        catalog,
        datetime(2023, 3, 15, tzinfo=UTC),
        event_type="cpi",
        realized_vol_quantile=0.05,
        thin_liquidity=True,
    )

    assert matches == (
        "banking_stress_2023_03",
        "quiet_ranges",
        "scheduled_news",
        "thin_liquidity",
    )


def test_catalog_rejects_locked_range_duplicate_and_bad_event(tmp_path: Path) -> None:
    locked = tmp_path / "locked.yaml"
    locked.write_text(
        """schema_version: 1
scenarios:
  - id: locked
    label: locked
    kind: fixed
    start: 2024-12-31
    end: 2025-01-01
    expected_availability: "no"
""",
        encoding="utf-8",
    )
    duplicate = tmp_path / "duplicate.yaml"
    duplicate.write_text(
        """schema_version: 1
scenarios:
  - {id: same, label: one, kind: auto_low_vol, expected_availability: "yes"}
  - {id: same, label: two, kind: auto_low_vol, expected_availability: "yes"}
""",
        encoding="utf-8",
    )
    bad_event = tmp_path / "event.yaml"
    bad_event.write_text(
        """schema_version: 1
scenarios:
  - {id: event, label: event, kind: event, expected_availability: "yes"}
""",
        encoding="utf-8",
    )

    with pytest.raises(ConfigLoadError, match="locked"):
        load_scenarios(locked)
    with pytest.raises(ConfigLoadError, match="unique"):
        load_scenarios(duplicate)
    with pytest.raises(ConfigLoadError, match="event_types"):
        load_scenarios(bad_event)


def test_membership_rejects_invalid_inputs() -> None:
    catalog = load_scenarios()
    with pytest.raises(ValueError, match="timezone"):
        scenario_membership(catalog, datetime(2024, 1, 1))
    with pytest.raises(ValueError, match="quantile"):
        scenario_membership(catalog, datetime(2024, 1, 1, tzinfo=UTC), realized_vol_quantile=1.1)
