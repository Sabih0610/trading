"""Price-free publication boundary and deterministic gold development phase report."""

from __future__ import annotations

import math
from typing import Any, NoReturn

from tb.research.gold_proxy import PROXY_LABEL
from tb.research.models import ResearchRefused
from tb.strategies.gold_stage3 import (
    GoldTrial,
    GoldVerdict,
    gold_ambiguity_verdict,
    gold_frozen_payload,
    gold_trials,
)

STRATEGIES = ("london_sweep_mss_fvg", "trend_vwap_pullback", "session_orb")
VERDICTS = {"reject", "promising", "insufficient evidence"}
METRICS = {"profit_factor", "expectancy_r", "max_dd_pct", "trade_count", "sharpe", "dsr"}
CHECKS = {
    "both_training_choices",
    "positive_2022",
    "positive_2023",
    "positive_stress_2022",
    "positive_stress_2023",
    "aggregate_pf_1_3",
    "max_dd_15pct",
    "at_least_60_trades",
    "beats_cash",
    "beats_random_95",
}
REASONS = {
    "quality_clock_not_current_completed_bar",
    "quarantined_day",
    "late_week_open",
    "lookback_missing_minutes_over_5pct",
}


def _refuse() -> NoReturn:
    raise ResearchRefused("gold_publication_schema_or_private_metric_refused")


def _object(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict) or not all(isinstance(k, str) for k in value):
        _refuse()
    return dict(value)


def _fields(value: Any, keys: set[str]) -> dict[str, Any]:
    record = _object(value)
    if set(record) != keys:
        _refuse()
    return record


def _items(value: Any) -> list[Any]:
    if not isinstance(value, (list, tuple)):
        _refuse()
    return list(value)


def _integer(value: Any, *, maximum: int | None = None) -> int:
    if type(value) is not int or value < 0 or (maximum is not None and value > maximum):
        _refuse()
    return int(value)


def _number(value: Any, *, optional: bool = False, minimum: float | None = None) -> float | None:
    if value is None and optional:
        return None
    if type(value) not in (int, float) or not math.isfinite(value):
        _refuse()
    result = float(value)
    if minimum is not None and result < minimum:
        _refuse()
    return result


def _hash(value: Any) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(c not in "0123456789abcdef" for c in value)
    ):
        _refuse()
    return str(value)


def _year(value: Any) -> int:
    if type(value) is not int or value not in (2022, 2023):
        _refuse()
    return int(value)


def _verdict(value: Any) -> GoldVerdict:
    if value == "reject":
        return "reject"
    if value == "promising":
        return "promising"
    if value == "insufficient evidence":
        return "insufficient evidence"
    _refuse()


def _bool(value: Any) -> bool:
    if type(value) is not bool:
        _refuse()
    return bool(value)


def _metrics(value: Any) -> dict[str, Any]:
    record = _fields(value, METRICS)
    result = {
        "profit_factor": _number(record["profit_factor"], optional=True, minimum=0),
        "expectancy_r": _number(record["expectancy_r"], optional=True),
        "max_dd_pct": _number(record["max_dd_pct"], minimum=0),
        "trade_count": _integer(record["trade_count"]),
        "sharpe": _number(record["sharpe"], optional=True),
        "dsr": _number(record["dsr"], optional=True, minimum=0),
    }
    if result["dsr"] is not None and result["dsr"] > 1:
        _refuse()
    return result


def _paths(strategy: str) -> tuple[str, ...]:
    fills = ("touch", "through") if strategy == STRATEGIES[0] else ("touch",)
    return tuple(
        f"{f}/{o}/{c}" for f in fills for o in ("stop", "target") for c in ("1", "1.5", "2")
    )


def _trial(index: Any, strategy: str) -> GoldTrial | None:
    if index is None:
        return None
    number = _integer(index, maximum=53)
    trial = gold_trials()[number]
    if trial.strategy != strategy:
        _refuse()
    return trial


def _quality_counts(value: Any) -> dict[str, Any]:
    record = _fields(
        value,
        {
            "candidate_calendar_sessions",
            "sessions_with_complete_inputs",
            "sessions_with_no_eligible_bars",
            "unique_proposal_sessions_vetoed",
            "proposal_sessions_vetoed_by_reason",
            "wall_clock_closures_count_as_missing",
        },
    )
    candidate = _integer(record["candidate_calendar_sessions"])
    result: dict[str, Any] = {"candidate_calendar_sessions": candidate}
    for key in (
        "sessions_with_complete_inputs",
        "sessions_with_no_eligible_bars",
        "unique_proposal_sessions_vetoed",
    ):
        result[key] = _integer(record[key], maximum=candidate)
    reasons = _object(record["proposal_sessions_vetoed_by_reason"])
    if not set(reasons) <= REASONS or record["wall_clock_closures_count_as_missing"] is not True:
        _refuse()
    result["proposal_sessions_vetoed_by_reason"] = {
        name: _integer(reasons[name], maximum=result["unique_proposal_sessions_vetoed"])
        for name in sorted(reasons)
    }
    result["wall_clock_closures_count_as_missing"] = True
    return result


def _quality(value: Any, strategy: str, selections: dict[int, int | None]) -> list[dict[str, Any]]:
    records = _items(value)
    result = []
    seen = set()
    for item in records:
        record = _object(item)
        year = _year(record.get("year"))
        if year in seen:
            _refuse()
        seen.add(year)
        selected = selections[year]
        if selected is not None:
            record = _fields(record, {"year", "timeframe_seconds", "counts"})
            trial = _trial(selected, strategy)
            if trial is None or record["timeframe_seconds"] != int(trial.timeframe.total_seconds()):
                _refuse()
            result.append(
                {
                    "year": year,
                    "timeframe_seconds": record["timeframe_seconds"],
                    "counts": _quality_counts(record["counts"]),
                }
            )
        else:
            record = _fields(record, {"year", "status", "timeframes"})
            if record["status"] != "no eligible training cell":
                _refuse()
            expected: dict[int, int] = {}
            for i, trial in enumerate(gold_trials()):
                if trial.strategy == strategy:
                    expected.setdefault(int(trial.timeframe.total_seconds()), i)
            frames = []
            for frame in _items(record["timeframes"]):
                frame = _fields(
                    frame,
                    {"timeframe_seconds", "diagnostic_trial_index", "selection_status", "counts"},
                )
                seconds = _integer(frame["timeframe_seconds"])
                if (
                    seconds not in expected
                    or frame["diagnostic_trial_index"] != expected[seconds]
                    or frame["selection_status"]
                    != "not selected; first registered cell for coverage"
                ):
                    _refuse()
                frames.append(
                    {
                        "timeframe_seconds": seconds,
                        "diagnostic_trial_index": expected[seconds],
                        "selection_status": frame["selection_status"],
                        "counts": _quality_counts(frame["counts"]),
                    }
                )
            if len(frames) != len(expected) or {f["timeframe_seconds"] for f in frames} != set(
                expected
            ):
                _refuse()
            result.append(
                {
                    "year": year,
                    "status": record["status"],
                    "timeframes": sorted(frames, key=lambda f: f["timeframe_seconds"]),
                }
            )
    if seen != {2022, 2023}:
        _refuse()
    return sorted(result, key=lambda r: r["year"])


def _row(value: Any) -> dict[str, Any]:
    # Explicit extraction discards every extra top/row field, including hidden nested series.
    record = _object(value)
    strategy = record.get("strategy")
    if strategy not in STRATEGIES:
        _refuse()
    strategy = str(strategy)
    if (
        record.get("symbol") != "XAUTUSDT"
        or record.get("proxy") != PROXY_LABEL
        or record.get("status") != "development only: not validated"
    ):
        _refuse()
    selected: dict[int, int | None] = {}
    for item in _items(record.get("selections")):
        item = _fields(item, {"year", "trial_index"})
        year = _year(item["year"])
        if year in selected:
            _refuse()
        _trial(item["trial_index"], strategy)
        selected[year] = item["trial_index"]
    if set(selected) != {2022, 2023}:
        _refuse()
    missing = sorted(_year(y) for y in _items(record.get("missing_training_folds")))
    if missing != [year for year in (2022, 2023) if selected[year] is None]:
        _refuse()
    metrics = _fields(record.get("metrics"), set(_paths(strategy)))
    clean_metrics: dict[str, Any] = {}
    for path in _paths(strategy):
        item = _fields(metrics[path], {"aggregate", "folds"})
        folds: list[dict[str, Any]] = []
        for fold in _items(item["folds"]):
            fold = _fields(
                fold,
                {"year", "status", "metrics", "circuit_trips", "halted_days", "ambiguous_bars"},
            )
            year = _year(fold["year"])
            status = "insufficient evidence" if year in missing else "evaluated"
            if fold["status"] != status:
                _refuse()
            folds.append(
                {
                    "year": year,
                    "status": status,
                    "metrics": _metrics(fold["metrics"]),
                    "circuit_trips": _integer(fold["circuit_trips"], maximum=1),
                    "halted_days": _integer(fold["halted_days"], maximum=365),
                    "ambiguous_bars": _integer(fold["ambiguous_bars"]),
                }
            )
        if len(folds) != 2 or {f["year"] for f in folds} != {2022, 2023}:
            _refuse()
        clean_metrics[path] = {
            "aggregate": _metrics(item["aggregate"]),
            "folds": sorted(folds, key=lambda f: f["year"]),
        }
    assumptions = {path.rsplit("/", 1)[0] for path in _paths(strategy)}
    bounds = _fields(record.get("ambiguity_verdicts"), assumptions)
    bounds = {key: _verdict(bounds[key]) for key in sorted(bounds)}
    checklists = _fields(record.get("checklists"), assumptions)
    clean_checks = {
        key: {
            check: _bool(value) for check, value in sorted(_fields(checklists[key], CHECKS).items())
        }
        for key in sorted(checklists)
    }
    preliminary = _verdict(record.get("preliminary_development_verdict"))
    combined: GoldVerdict = "promising"
    for bound in bounds.values():
        combined = gold_ambiguity_verdict(combined, bound)
    if preliminary != combined:
        _refuse()
    ineligible = _bool(record.get("final_training_ineligible"))
    verdict = _verdict(record.get("verdict"))
    expected_verdict = (
        "insufficient evidence" if ineligible and preliminary != "reject" else preliminary
    )
    if verdict != expected_verdict:
        _refuse()
    return {
        "strategy": strategy,
        "symbol": "XAUTUSDT",
        "proxy": PROXY_LABEL,
        "status": "development only: not validated",
        "verdict": verdict,
        "preliminary_development_verdict": preliminary,
        "final_training_ineligible": ineligible,
        "missing_training_folds": missing,
        "selections": [{"year": y, "trial_index": selected[y]} for y in (2022, 2023)],
        "metrics": clean_metrics,
        "ambiguity_verdicts": bounds,
        "checklists": clean_checks,
        "quality_gate": _quality(record.get("quality_gate"), strategy, selected),
    }


def _frozen(value: Any, identity: dict[str, Any], rows: list[dict[str, Any]]) -> dict[str, object]:
    record = _fields(
        value,
        {
            "kind",
            "status",
            "proxy",
            "training_years",
            "n_trials",
            "registration_sha256",
            "implementation_sha256",
            "strategies",
        },
    )
    if (
        record["kind"] != "gold_proxy_development_parameters"
        or record["status"] != "development_only_not_validated"
        or record["proxy"] != "XAUUSD(histdata,bid)->XAUTUSDT"
        or record["training_years"] != [2021, 2022, 2023]
        or record["n_trials"] != 54
        or record["registration_sha256"] != identity["registration_sha256"]
        or record["implementation_sha256"] != identity["implementation_sha256"]
    ):
        _refuse()
    strategies = _fields(record["strategies"], set(STRATEGIES))
    chosen: dict[str, GoldTrial | None] = {}
    verdicts: dict[str, GoldVerdict] = {}
    by_name = {row["strategy"]: row for row in rows}
    for name in STRATEGIES:
        item = _fields(strategies[name], {"development_verdict", "timeframe_seconds", "config"})
        verdicts[name] = _verdict(item["development_verdict"])
        if verdicts[name] != by_name[name]["verdict"]:
            _refuse()
        if item["config"] is None:
            if (
                item["timeframe_seconds"] is not None
                or not by_name[name]["final_training_ineligible"]
            ):
                _refuse()
            chosen[name] = None
        else:
            matches = [
                trial
                for trial in gold_trials()
                if trial.strategy == name
                and int(trial.timeframe.total_seconds()) == item["timeframe_seconds"]
                and trial.config.model_dump(mode="json") == item["config"]
            ]
            if len(matches) != 1 or by_name[name]["final_training_ineligible"]:
                _refuse()
            chosen[name] = matches[0]
    return gold_frozen_payload(
        chosen,
        verdicts=verdicts,
        registration_sha256=identity["registration_sha256"],
        implementation_sha256=identity["implementation_sha256"],
    )


def _guard_protocol_tags(value: Any) -> None:
    """Reject concealed out-of-scope years or validated verdict labels before copying."""
    if isinstance(value, dict):
        for key, child in value.items():
            if key == "year" and (type(child) is not int or child not in (2021, 2022, 2023)):
                _refuse()
            if key in {"training_years", "evaluation_years", "development_years"}:
                if not isinstance(child, (list, tuple)) or any(
                    type(y) is not int or y not in (2021, 2022, 2023) for y in child
                ):
                    _refuse()
            if key in {"verdict", "development_verdict", "preliminary_development_verdict"}:
                _verdict(child)
            if key == "ambiguity_verdicts":
                for verdict in _object(child).values():
                    _verdict(verdict)
            _guard_protocol_tags(child)
    elif isinstance(value, (list, tuple)):
        for child in value:
            _guard_protocol_tags(child)


def publication_projection(private: dict[str, Any]) -> dict[str, Any]:
    """Copy a closed price-free schema; never serialize the private batch result wholesale."""
    _guard_protocol_tags(private)
    record = _object(private)
    identity = _fields(
        record.get("identity"),
        {"registration_sha256", "implementation_sha256", "data_manifest_sha256", "n_trials"},
    )
    if identity["n_trials"] != 54 or type(identity["n_trials"]) is not int:
        _refuse()
    identity = {
        **{
            key: _hash(identity[key])
            for key in ("registration_sha256", "implementation_sha256", "data_manifest_sha256")
        },
        "n_trials": 54,
    }
    rows = [_row(row) for row in _items(record.get("verdicts"))]
    if len(rows) != 3 or {row["strategy"] for row in rows} != set(STRATEGIES):
        _refuse()
    rows.sort(key=lambda row: STRATEGIES.index(row["strategy"]))
    return {
        "identity": identity,
        "verdicts": rows,
        "frozen_parameters": _frozen(record.get("frozen_parameters"), identity, rows),
        "runtime_seconds": _number(record.get("runtime_seconds"), minimum=0),
        "peak_rss_bytes": _integer(record.get("peak_rss_bytes")),
    }


def _value(value: Any) -> str:
    return (
        "undefined" if value is None else str(value) if isinstance(value, int) else f"{value:.6g}"
    )


def _metric_cells(metrics: dict[str, Any]) -> str:
    return " | ".join(
        _value(metrics[key])
        for key in ("profit_factor", "expectancy_r", "max_dd_pct", "trade_count", "sharpe", "dsr")
    )


def phase_report(public: dict[str, Any]) -> str:
    """Render actual permitted evidence only, with no source observations or trade series."""
    result = publication_projection(public)  # renderer is also a privacy/schema boundary
    rows = result["verdicts"]
    counts = {
        verdict: sum(row["verdict"] == verdict for row in rows) for verdict in sorted(VERDICTS)
    }
    lines = [
        "# P11g — Gold development verdicts (Part B)",
        "",
        "**Development only: not validated.** " + PROXY_LABEL + ".",
        "This registered one-shot batch can reject candidates or identify promising development evidence; no gold strategy is validated by this phase.",
        "",
        "- [x] Apply the approved G-1/G-2 amendments before genuine input and record the amended registration SHA.",
        "- [x] Freeze both training-only fold selectors before evaluation; retain all 54 registered trials.",
        "- [x] Report fixed-cell cost, ambiguity and A trade-through sensitivities, quality diagnostics and 5% circuit observations.",
        "- [x] Freeze final 2021-2023 parameters without prices; submit Part B for Claude review.",
        "",
        "## Verdicts",
        "",
        "| Strategy | Touch stop-first | Touch target-first | Through stop-first | Through target-first | Final development verdict | Final training eligible |",
        "|---|---|---|---|---|---|---|",
    ]
    for row in rows:
        bounds = row["ambiguity_verdicts"]
        lines.append(
            "| "
            + " | ".join(
                [
                    row["strategy"],
                    bounds["touch/stop"],
                    bounds["touch/target"],
                    bounds.get("through/stop", "not applicable"),
                    bounds.get("through/target", "not applicable"),
                    row["verdict"],
                    "no" if row["final_training_ineligible"] else "yes",
                ]
            )
            + " |"
        )
    lines += [
        "",
        "A requires both touch and strict trade-through (`low < limit`) paths and both orderings to be promising. Any registered reject bound means reject. A null final training selector cannot advance; its preliminary OOS ordering verdicts remain recorded in the aggregate JSON.",
        "",
        "## Permitted aggregate metrics and sensitivities",
        "",
        "PF is undefined with no losses or no trades; undefined evidence never promotes a candidate. DSR uses N_trials = 54 and is informational. 1.5x costs are a gate; 2x is diagnostic. Every sensitivity retains its base-cost training-selected cell.",
        "",
        "| Strategy | Fill / ordering / cost multiplier | PF | Expectancy (R) | Max DD (%) | Completed trades | Sharpe | DSR probability |",
        "|---|---|---:|---:|---:|---:|---:|---:|",
    ]
    for row in rows:
        for path in _paths(row["strategy"]):
            lines.append(
                f"| {row['strategy']} | {path} | {_metric_cells(row['metrics'][path]['aggregate'])} |"
            )
    lines += [
        "",
        "## Fold metrics and 5% circuit diagnostics",
        "",
        "Halted days include the trip date through the fold end, including weekends and other flat days. The 2023 calendar retains 31 December without reading a 2024 observation. Ambiguous bars are counted for every ordering and cost path.",
        "",
        "| Strategy | Path | Year | Fold status | PF | Expectancy (R) | Max DD (%) | Trades | Sharpe | DSR | Circuit trips | Halted days | Ambiguous bars |",
        "|---|---|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in rows:
        for path in _paths(row["strategy"]):
            for fold in row["metrics"][path]["folds"]:
                lines.append(
                    f"| {row['strategy']} | {path} | {fold['year']} | {fold['status']} | {_metric_cells(fold['metrics'])} | {fold['circuit_trips']} | {fold['halted_days']} | {fold['ambiguous_bars']} |"
                )
    lines += [
        "",
        "## Quality gate: coverage and proposal vetoes",
        "",
        "Coverage counts describe calendar sessions, usable causal inputs and sessions without eligible bars. Proposal-veto counts describe actual proposed entries and may be zero when a strategy cannot propose; zero vetoes do not establish complete coverage. Overlapping veto reasons remain separate and must not be added as disjoint counts. The fixed wall-clock grid counts scheduled closures and holidays as missing; the >5% gate is unchanged.",
        "",
        "HistData has no observed traded volume or volume-backed VWAP. C's missing-input limitation remains explicit, with all 18 C cells retained in N_trials = 54. For a fold without a training choice, quality diagnostics use the first registered cell of each timeframe and are labelled coverage-only; they do not select or score a replacement.",
        "",
        "| Strategy | Year | TF seconds | Diagnostic scope | Calendar sessions | Complete inputs | No eligible bars | Unique proposal sessions vetoed | Veto reasons (overlap retained) |",
        "|---|---:|---:|---|---:|---:|---:|---:|---|",
    ]
    for row in rows:
        for quality in row["quality_gate"]:
            frames = quality.get("timeframes", [quality])
            for frame in frames:
                qc = frame["counts"]
                reasons = (
                    "; ".join(
                        f"{name}: {count}"
                        for name, count in qc["proposal_sessions_vetoed_by_reason"].items()
                    )
                    or "none observed"
                )
                scope = (
                    "coverage only; no eligible training cell"
                    if "timeframes" in quality
                    else "selected cell"
                )
                lines.append(
                    f"| {row['strategy']} | {quality['year']} | {frame['timeframe_seconds']} | {scope} | {qc['candidate_calendar_sessions']} | {qc['sessions_with_complete_inputs']} | {qc['sessions_with_no_eligible_bars']} | {qc['unique_proposal_sessions_vetoed']} | {reasons} |"
                )
    lines += [
        "",
        "## Registered checks",
        "",
        "| Strategy | Fill / ordering | Checks not met |",
        "|---|---|---|",
    ]
    for row in rows:
        for path, checks in row["checklists"].items():
            failed = ", ".join(name for name, passed in checks.items() if not passed) or "none"
            lines.append(f"| {row['strategy']} | {path} | {failed} |")
    identity = result["identity"]
    lines += [
        "",
        "## Frozen parameters and provenance",
        "",
        "The price-free [frozen parameters](../stage3/P11g-frozen-params.json) contain the fixed final 2021-2023 training choice for each candidate and its development verdict. Future validation requires its own approved registration; no 2024 data was read for G. Parameters were not reselected for costs, ambiguity or trade-through sensitivity.",
        "",
        f"- Registration SHA-256: `{identity['registration_sha256']}`.",
        f"- Implementation/configuration/dependency SHA-256: `{identity['implementation_sha256']}`.",
        f"- Admitted data-manifest identity SHA-256: `{identity['data_manifest_sha256']}`.",
        f"- Registered trials: {identity['n_trials']}; runtime: {_value(result['runtime_seconds'])} seconds; sampled peak RSS: {result['peak_rss_bytes']} bytes.",
        "",
        "Review and validation evidence are recorded in the [journal](../../docs/journal/P11g-journal.md), [research note](../../docs/research/P11g-research.md), [ADR 0025](../../docs/adr/0025-research-only-gold-development-proxy.md) and [runbook](../../docs/how-to/gold-development.md). The source/configuration was tested and frozen before genuine input. Identical-identity technical checkpoints do not authorize re-running, retuning or relabelling evidence.",
        "",
        "## Limitations and conclusion",
        "",
        "The first selector has only 2021 training, shortened further by indicator initialization and the fixed 24-hour purge. It cannot establish parameter stability across several training regimes. The next selector uses 2021-2022; both are frozen before OOS evaluation. Fresh shared features begin in 2021 with no 2020 warm-up.",
        "",
        "HistData is a bid proxy, not XAUT execution or liquidity evidence. G-2 treats that bid as a mid reference while retaining its provenance: full quoted spread 8 bps is halved to 4 bps per fill, with fee 10 bps and slippage 5 bps per side; all components are stressed together. The internal capacity bound is explicitly counterfactual and cannot establish real participation capacity. Existing XAUT 0.25% all-in risk and two-trades-per-day overrides and the deterministic risk manager remain unchanged.",
        "",
        f"The registered evidence yields {counts['reject']} reject, {counts['promising']} promising and {counts['insufficient evidence']} insufficient-evidence candidates. These counts describe development only. No candidate is validated on gold or XAUT, and no result authorizes Stage 4, paper trading, Testnet, orders, holdout access or unsealing.",
        "",
        "## Living-doc entries",
        "",
        f"After review/merge, the separate living-docs PR records G's final development counts ({counts['reject']} reject, {counts['promising']} promising, {counts['insufficient evidence']} insufficient), immutable 54-trial identities, frozen parameters, quality/circuit/sensitivity diagnostics and the short-2021-training limitation. Preserve F's immutable verdicts. J2 begins only after both F and G Part B are merged; K follows the current main master and its independent registration gates. No shared living files are edited on this track branch.",
        "",
        "Ready for Claude review",
        "",
    ]
    return "\n".join(lines)
