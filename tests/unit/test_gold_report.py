"""Owned report fixtures prove a closed publication schema without genuine observations."""

import copy
import json

import pytest

from tb.backtest.gold_report import CHECKS, METRICS, phase_report, publication_projection
from tb.research.gold_proxy import PROXY_LABEL
from tb.research.models import ResearchRefused
from tb.strategies.gold_stage3 import gold_frozen_payload, gold_trials

PRIVATE = "PRIVATE_PROVIDER_OBSERVATION_987654321_DO_NOT_PUBLISH"


def quality_counts():
    return {
        "candidate_calendar_sessions": 260,
        "sessions_with_complete_inputs": 100,
        "sessions_with_no_eligible_bars": 60,
        "unique_proposal_sessions_vetoed": 5,
        "proposal_sessions_vetoed_by_reason": {
            "quarantined_day": 3,
            "lookback_missing_minutes_over_5pct": 5,
        },
        "wall_clock_closures_count_as_missing": True,
    }


def metrics(empty=False):
    return {
        "profit_factor": None if empty else 0.8,
        "expectancy_r": None if empty else -0.1,
        "max_dd_pct": 0 if empty else 5,
        "trade_count": 0 if empty else 30,
        "sharpe": None if empty else -0.4,
        "dsr": None if empty else 0.05,
    }


@pytest.fixture
def private_result():
    trials = gold_trials()
    names = ("london_sweep_mss_fvg", "trend_vwap_pullback", "session_orb")
    rows, selected, verdicts = [], {}, {}
    for name in names:
        index = next(i for i, trial in enumerate(trials) if trial.strategy == name)
        empty = name == "trend_vwap_pullback"
        fills = ("touch", "through") if name == "london_sweep_mss_fvg" else ("touch",)
        bounds = {
            f"{fill}/{order}": "insufficient evidence" if empty else "reject"
            for fill in fills
            for order in ("stop", "target")
        }
        paths = {}
        for bound in bounds:
            for cost in ("1", "1.5", "2"):
                paths[bound + "/" + cost] = {
                    "aggregate": metrics(empty),
                    "folds": [
                        {
                            "year": year,
                            "status": "insufficient evidence" if empty else "evaluated",
                            "metrics": metrics(empty),
                            "circuit_trips": 0 if empty else 1,
                            "halted_days": 0 if empty else 18,
                            "ambiguous_bars": 0 if empty else 2,
                        }
                        for year in (2022, 2023)
                    ],
                }
        quality = []
        for year in (2022, 2023):
            if not empty:
                quality.append(
                    {
                        "year": year,
                        "timeframe_seconds": int(trials[index].timeframe.total_seconds()),
                        "counts": quality_counts(),
                    }
                )
            else:
                first = {}
                for i, trial in enumerate(trials):
                    if trial.strategy == name:
                        first.setdefault(int(trial.timeframe.total_seconds()), i)
                quality.append(
                    {
                        "year": year,
                        "status": "no eligible training cell",
                        "timeframes": [
                            {
                                "timeframe_seconds": seconds,
                                "diagnostic_trial_index": i,
                                "selection_status": "not selected; first registered cell for coverage",
                                "counts": quality_counts(),
                            }
                            for seconds, i in sorted(first.items())
                        ],
                    }
                )
        verdict = "insufficient evidence" if empty else "reject"
        rows.append(
            {
                "strategy": name,
                "symbol": "XAUTUSDT",
                "proxy": PROXY_LABEL,
                "status": "development only: not validated",
                "verdict": verdict,
                "preliminary_development_verdict": verdict,
                "final_training_ineligible": empty,
                "selections": [
                    {"year": year, "trial_index": None if empty else index} for year in (2022, 2023)
                ],
                "missing_training_folds": [2022, 2023] if empty else [],
                "metrics": paths,
                "ambiguity_verdicts": bounds,
                "checklists": {bound: {check: False for check in CHECKS} for bound in bounds},
                "quality_gate": quality,
                "raw_trades": [{"price": PRIVATE}],
                "net_return": PRIVATE,
                "other_private_nesting": {"daily_returns": [PRIVATE], "win_rate": PRIVATE},
            }
        )
        selected[name] = None if empty else trials[index]
        verdicts[name] = verdict
    identity = {
        "registration_sha256": "1" * 64,
        "implementation_sha256": "2" * 64,
        "data_manifest_sha256": "3" * 64,
        "n_trials": 54,
    }
    return {
        "identity": identity,
        "verdicts": rows,
        "frozen_parameters": gold_frozen_payload(
            selected,
            verdicts=verdicts,
            registration_sha256=identity["registration_sha256"],
            implementation_sha256=identity["implementation_sha256"],
        ),
        "private_comparisons": [{"prices": PRIVATE, "daily_returns": [PRIVATE]}],
        "runtime_seconds": 123.5,
        "peak_rss_bytes": 12345678,
        "individual_trades": PRIVATE,
    }


def test_projection_excludes_extra_private_payloads_at_every_public_boundary(private_result):
    original = copy.deepcopy(private_result)
    public = publication_projection(private_result)
    assert private_result == original
    assert set(public) == {
        "identity",
        "verdicts",
        "frozen_parameters",
        "runtime_seconds",
        "peak_rss_bytes",
    }
    encoded = json.dumps(public, sort_keys=True)
    assert PRIVATE not in encoded
    assert all(
        key not in encoded
        for key in (
            '"net_return"',
            '"win_rate"',
            '"daily_returns"',
            '"individual_trades"',
            '"raw_trades"',
        )
    )
    for row in public["verdicts"]:
        for path in row["metrics"].values():
            assert set(path["aggregate"]) == METRICS
            assert all(set(fold["metrics"]) == METRICS for fold in path["folds"])
    assert publication_projection(public) == public
    private_result["verdicts"].reverse()
    assert publication_projection(private_result) == public


@pytest.mark.parametrize(
    "change",
    [
        lambda r: r["verdicts"][0]["metrics"]["touch/stop/1"]["aggregate"].update(net_return=0.2),
        lambda r: r["verdicts"][0]["metrics"]["touch/stop/1"]["folds"][0]["metrics"].update(
            daily_returns=[1]
        ),
        lambda r: r["verdicts"][0]["metrics"]["touch/stop/1"]["folds"][0].update(year=2024),
        lambda r: r["verdicts"][0].update(verdict="pass"),
        lambda r: r["verdicts"][0]["ambiguity_verdicts"].update({"touch/stop": "validated"}),
        lambda r: r["frozen_parameters"].update(training_years=[2021, 2022, 2024]),
        lambda r: r["frozen_parameters"].update(status="validated_on_XAUT"),
        lambda r: r["frozen_parameters"]["strategies"]["session_orb"]["config"].update(
            entry_price=123.45
        ),
        lambda r: r["verdicts"][0]["quality_gate"][0]["counts"][
            "proposal_sessions_vetoed_by_reason"
        ].update(raw_close=1),
        lambda r: r["verdicts"][0]["metrics"]["touch/stop/1"]["aggregate"].update(
            sharpe=float("inf")
        ),
        lambda r: r["verdicts"][0]["metrics"]["touch/stop/1"]["aggregate"].update(
            profit_factor=True
        ),
        lambda r: r["verdicts"][0]["metrics"]["touch/stop/1"]["aggregate"].update(dsr=1.01),
        lambda r: r["identity"].update(n_trials=162),
        lambda r: r["identity"].update(implementation_sha256="bad"),
        lambda r: r["verdicts"][0]["selections"][0].update(trial_index=36),
        lambda r: r["verdicts"][0].update(final_training_ineligible=True),
        lambda r: r["verdicts"][0]["quality_gate"][0]["counts"].update(
            unique_proposal_sessions_vetoed=10000
        ),
        lambda r: r["verdicts"][0]["metrics"]["touch/stop/1"]["folds"][0].update(halted_days=366),
        lambda r: r["verdicts"][0].update(hidden_protocol={"year": 2025}),
        lambda r: r["verdicts"][0].update(hidden_protocol={"development_verdict": "validated"}),
    ],
)
def test_publication_refuses_extra_metrics_invalid_scope_or_false_validation(
    private_result, change
):
    change(private_result)
    with pytest.raises(ResearchRefused, match="publication_schema"):
        publication_projection(private_result)


def test_report_is_complete_deterministic_and_contains_no_private_series(private_result):
    public = publication_projection(private_result)
    report = phase_report(public)
    assert report == phase_report(public)
    assert report.endswith("Ready for Claude review\n")
    for required in (
        "Development only: not validated",
        PROXY_LABEL,
        "N_trials = 54",
        "Through stop-first",
        "through/target/2",
        "Circuit trips",
        "Halted days",
        "Ambiguous bars",
        "coverage-only",
        "Proposal-veto",
        "first selector has only 2021 training",
        "2 reject, 0 promising and 1 insufficient-evidence",
        "P11g-frozen-params.json",
        "Living-doc entries",
        "0.25%",
        "strict trade-through",
    ):
        assert required in report
    for private in (PRIVATE, "net_return", "win_rate", "daily_returns", "individual_trades"):
        assert private not in report
    assert "undefined" in report
    assert "".join(["1" * 64]) in report


def test_renderer_revalidates_metrics_instead_of_blindly_formatting(private_result):
    public = publication_projection(private_result)
    public["verdicts"][0]["metrics"]["touch/stop/1"]["aggregate"]["net_return"] = 100
    with pytest.raises(ResearchRefused, match="publication_schema"):
        phase_report(public)
