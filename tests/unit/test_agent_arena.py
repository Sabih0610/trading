"""End-to-end offline arena and hostile response scenarios."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from tb.agents.arena import Arena
from tb.agents.budget import AiBudgetConfig, ProviderBudget, load_ai_budget
from tb.agents.cache import ResponseCache
from tb.agents.providers import MockProvider
from tb.agents.schemas import MaskedSnapshot, ProviderRequest, ProviderResponse
from tb.ledger import DecisionLedger, LedgerVersions


def _versions() -> LedgerVersions:
    return LedgerVersions(
        model_version="arena-v1",
        prompt_version="arena-v1",
        question_set_version="risk-review-v1",
        features_version="features-v3",
    )


def _snapshot() -> MaskedSnapshot:
    return MaskedSnapshot(
        features={"trend_score": 0.4, "volatility_zscore": 1.2},
        feature_set_version="features-v3",
    )


def _arena(
    tmp_path: Path, providers: list[MockProvider], budget: AiBudgetConfig | None = None
) -> Arena:
    return Arena(
        ledger=DecisionLedger(tmp_path / "ledger.sqlite"),
        cache=ResponseCache(tmp_path / "cache.sqlite"),
        budget=load_ai_budget() if budget is None else budget,
        providers=providers,
        versions=_versions(),
    )


def _answer(*, multiplier: float = 0.5, decision: str = "take") -> str:
    return json.dumps(
        {
            "decision": decision,
            "confidence": 0.7,
            "reason_code": "FIXTURE_REVIEW",
            "key_risk": "fixture risk",
            "action": "reduce",
            "size_multiplier": multiplier,
        }
    )


def test_mock_arena_runs_all_rounds_and_only_reduces(tmp_path: Path) -> None:
    provider = MockProvider(responses=[_answer(multiplier=0.6), _answer(multiplier=0.4)])
    result = _arena(tmp_path, [provider]).run(
        _snapshot(), questions=["Should this existing setup be reduced?"], collect_hypotheses=False
    )
    assert not result.veto
    assert result.size_multiplier == 0.4
    assert len(result.answers) == len(result.cross_reviews) == 1
    assert len(DecisionLedger(tmp_path / "ledger.sqlite").rows("interventions")) == 1


def test_malformed_increase_and_provider_down_fail_closed_without_crash(tmp_path: Path) -> None:
    providers = [
        MockProvider(model="malformed", responses=["not-json", "not-json"]),
        MockProvider(
            model="increase", responses=[_answer(multiplier=1.2), _answer(multiplier=1.2)]
        ),
        MockProvider(model="down", failure="offline"),
    ]
    result = _arena(tmp_path, providers).run(
        _snapshot(), questions=["Review"], collect_hypotheses=False
    )
    assert result.size_multiplier == 1.0
    assert not result.veto
    assert all(observation.answer is None for observation in result.answers)
    assert {observation.error_code for observation in result.answers} == {
        "MALFORMED_RESPONSE",
        "PROVIDERUNAVAILABLE",
    }


def test_cache_avoids_repeated_provider_calls_and_flags_herding(tmp_path: Path) -> None:
    first = MockProvider(model="a")
    second = MockProvider(model="b")
    arena = _arena(tmp_path, [first, second])
    now = datetime(2026, 10, 22, tzinfo=UTC)
    initial = arena.run(_snapshot(), questions=["Review"], now=now, collect_hypotheses=False)
    calls = first.call_count + second.call_count
    repeated = arena.run(_snapshot(), questions=["Review"], now=now, collect_hypotheses=False)
    assert initial.herding
    assert repeated.herding
    assert first.call_count + second.call_count == calls
    assert all(item.cache_hit for item in repeated.answers)


class _CostProvider:
    name = "paid"
    model = "fixture"
    enabled = True

    def generate(self, request: ProviderRequest) -> ProviderResponse:
        del request
        return ProviderResponse(raw_json=_answer(), cost_usd=0.01)


def test_budget_cap_hit_mid_day_is_logged_and_skipped(tmp_path: Path) -> None:
    policy = ProviderBudget(
        enabled=True,
        daily_usd=0.10,
        monthly_usd=0.20,
        max_call_usd=0.05,
        input_usd_per_million_tokens=1,
        output_usd_per_million_tokens=0,
    )
    budget = AiBudgetConfig(monthly_total_usd=0.20, providers={"paid": policy})
    ledger = DecisionLedger(tmp_path / "ledger.sqlite")
    now = datetime(2026, 10, 22, tzinfo=UTC)
    ledger.append_model_call(
        {},
        _versions(),
        decision_id=None,
        provider="paid",
        model="fixture",
        status="ok",
        cost_usd=0.06,
        created_at=now,
    )
    arena = Arena(
        ledger=ledger,
        cache=ResponseCache(tmp_path / "cache.sqlite"),
        budget=budget,
        providers=[_CostProvider()],
        versions=_versions(),
    )
    result = arena.run(_snapshot(), questions=["Review"], now=now, collect_hypotheses=False)
    assert result.answers[0].status == "budget_skipped"
    assert result.answers[0].error_code == "DAILY_CAP"
    assert any(row["status"] == "budget_skipped" for row in ledger.rows("model_calls"))
