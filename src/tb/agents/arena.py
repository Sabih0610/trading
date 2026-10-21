"""Offline-first multi-provider review arena with veto/reduction-only authority."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence
from datetime import UTC, datetime

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from tb.agents.budget import AiBudgetConfig, BudgetDecision, budget_periods
from tb.agents.cache import ResponseCache, cache_key
from tb.agents.providers import Provider, ProviderError
from tb.agents.schemas import (
    ArenaAnswer,
    HypothesisProposal,
    MaskedSnapshot,
    ProviderRequest,
)
from tb.agents.scoring import herding_flag
from tb.ledger import DecisionLedger, LedgerVersions


class ProviderObservation(BaseModel):
    """Arena-visible outcome for one attempted provider call."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    provider: str
    model: str
    status: str
    answer: ArenaAnswer | None = None
    error_code: str | None = None
    cache_hit: bool = False


class ArenaResult(BaseModel):
    """Complete immutable result of independent review and anonymized cross-review."""

    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)

    decision_id: str
    answers: tuple[ProviderObservation, ...]
    cross_reviews: tuple[ProviderObservation, ...]
    hypotheses: tuple[HypothesisProposal, ...]
    veto: bool
    size_multiplier: float = Field(ge=0.0, le=1.0)
    herding: bool


class Arena:
    """Coordinate model opinions after deterministic strategy/risk logic proposes a setup."""

    def __init__(
        self,
        *,
        ledger: DecisionLedger,
        cache: ResponseCache,
        budget: AiBudgetConfig,
        providers: Sequence[Provider],
        versions: LedgerVersions,
    ) -> None:
        self.ledger = ledger
        self.cache = cache
        self.budget = budget
        self.providers = tuple(providers)
        self.versions = versions

    def _budget_decision(self, provider: str, now: datetime) -> BudgetDecision:
        policy = self.budget.providers.get(provider)
        if policy is None:
            return BudgetDecision(allowed=False, reason="unknown_provider")
        if not policy.enabled:
            return BudgetDecision(allowed=False, reason="policy_disabled")
        day, month = budget_periods(now)
        provider_day = self.ledger.usage(provider=provider, since_prefix=day)
        provider_month = self.ledger.usage(provider=provider, since_prefix=month)
        total_month = self.ledger.usage(provider=None, since_prefix=month)
        if provider_day + policy.max_call_usd > policy.daily_usd:
            return BudgetDecision(allowed=False, reason="daily_cap")
        if provider_month + policy.max_call_usd > policy.monthly_usd:
            return BudgetDecision(allowed=False, reason="monthly_cap")
        if total_month + policy.max_call_usd > self.budget.monthly_total_usd:
            return BudgetDecision(allowed=False, reason="total_cap")
        return BudgetDecision(allowed=True, reason="ok")

    def _ask(
        self,
        provider: Provider,
        request: ProviderRequest,
        *,
        decision_id: str,
        now: datetime,
        stage: str,
    ) -> ProviderObservation:
        key = cache_key(
            stage,
            provider.name,
            provider.model,
            self.versions.model_dump(mode="json"),
            request.model_dump(mode="json"),
        )
        cached = self.cache.get(key, now=now)
        if cached is not None:
            try:
                answer = ArenaAnswer.model_validate_json(cached)
            except ValidationError:
                cached = None
            else:
                self.ledger.append_model_call(
                    {"stage": stage},
                    self.versions,
                    decision_id=decision_id,
                    provider=provider.name,
                    model=provider.model,
                    status="cache_hit",
                    cache_key=key,
                    created_at=now,
                )
                return ProviderObservation(
                    provider=provider.name,
                    model=provider.model,
                    status="cache_hit",
                    answer=answer,
                    cache_hit=True,
                )
        if not provider.enabled:
            self.ledger.append_model_call(
                {"stage": stage, "reason": "disabled"},
                self.versions,
                decision_id=decision_id,
                provider=provider.name,
                model=provider.model,
                status="disabled",
                cache_key=key,
                created_at=now,
            )
            return ProviderObservation(
                provider=provider.name,
                model=provider.model,
                status="disabled",
                error_code="PROVIDER_DISABLED",
            )
        allowed = self._budget_decision(provider.name, now)
        if not allowed.allowed:
            self.ledger.append_model_call(
                {"stage": stage, "reason": allowed.reason},
                self.versions,
                decision_id=decision_id,
                provider=provider.name,
                model=provider.model,
                status="budget_skipped",
                cache_key=key,
                created_at=now,
            )
            return ProviderObservation(
                provider=provider.name,
                model=provider.model,
                status="budget_skipped",
                error_code=allowed.reason.upper(),
            )
        try:
            response = provider.generate(request)
            answer = ArenaAnswer.model_validate_json(response.raw_json)
        except ValidationError:
            error_code = "MALFORMED_RESPONSE"
        except ProviderError as exc:
            error_code = type(exc).__name__.upper()
        else:
            policy = self.budget.providers[provider.name]
            configured_cost = policy.cost(response.input_tokens, response.output_tokens)
            cost = max(configured_cost, response.cost_usd)
            if cost > policy.max_call_usd:
                error_code = "CALL_COST_EXCEEDED"
                self.ledger.append_model_call(
                    {"stage": stage, "error_code": error_code},
                    self.versions,
                    decision_id=decision_id,
                    provider=provider.name,
                    model=provider.model,
                    status="cost_exceeded",
                    input_tokens=response.input_tokens,
                    output_tokens=response.output_tokens,
                    cost_usd=cost,
                    cache_key=key,
                    created_at=now,
                )
                return ProviderObservation(
                    provider=provider.name,
                    model=provider.model,
                    status="cost_exceeded",
                    error_code=error_code,
                )
            else:
                self.cache.put(
                    key,
                    answer.model_dump_json(),
                    ttl_seconds=self.budget.cache_ttl_seconds,
                    now=now,
                )
                self.ledger.append_model_call(
                    {
                        "stage": stage,
                        "latency_ms": response.latency_ms,
                        "provider_cache_hit": response.provider_cache_hit,
                        "response_sha256": hashlib.sha256(response.raw_json.encode()).hexdigest(),
                    },
                    self.versions,
                    decision_id=decision_id,
                    provider=provider.name,
                    model=provider.model,
                    status="ok",
                    input_tokens=response.input_tokens,
                    output_tokens=response.output_tokens,
                    cost_usd=cost,
                    cache_key=key,
                    created_at=now,
                )
                return ProviderObservation(
                    provider=provider.name, model=provider.model, status="ok", answer=answer
                )
        self.ledger.append_model_call(
            {"stage": stage, "error_code": error_code},
            self.versions,
            decision_id=decision_id,
            provider=provider.name,
            model=provider.model,
            status="error",
            cache_key=key,
            created_at=now,
        )
        return ProviderObservation(
            provider=provider.name,
            model=provider.model,
            status="error",
            error_code=error_code,
        )

    def _propose(
        self,
        provider: Provider,
        request: ProviderRequest,
        *,
        decision_id: str,
        now: datetime,
    ) -> HypothesisProposal | None:
        key = cache_key(
            "hypothesis",
            provider.name,
            provider.model,
            self.versions.model_dump(mode="json"),
            request.model_dump(mode="json"),
        )
        cached = self.cache.get(key, now=now)
        if cached is not None:
            try:
                return HypothesisProposal.model_validate_json(cached)
            except ValidationError:
                pass
        if not provider.enabled:
            return None
        allowed = self._budget_decision(provider.name, now)
        if not allowed.allowed:
            self.ledger.append_model_call(
                {"stage": "hypothesis", "reason": allowed.reason},
                self.versions,
                decision_id=decision_id,
                provider=provider.name,
                model=provider.model,
                status="budget_skipped",
                cache_key=key,
                created_at=now,
            )
            return None
        try:
            response = provider.generate(request)
            proposal = HypothesisProposal.model_validate_json(response.raw_json)
        except (ProviderError, ValidationError) as exc:
            self.ledger.append_model_call(
                {"stage": "hypothesis", "error_code": type(exc).__name__.upper()},
                self.versions,
                decision_id=decision_id,
                provider=provider.name,
                model=provider.model,
                status="error",
                cache_key=key,
                created_at=now,
            )
            return None
        policy = self.budget.providers[provider.name]
        cost = max(policy.cost(response.input_tokens, response.output_tokens), response.cost_usd)
        status = "ok" if cost <= policy.max_call_usd else "cost_exceeded"
        self.ledger.append_model_call(
            {"stage": "hypothesis"},
            self.versions,
            decision_id=decision_id,
            provider=provider.name,
            model=provider.model,
            status=status,
            input_tokens=response.input_tokens,
            output_tokens=response.output_tokens,
            cost_usd=cost,
            cache_key=key,
            created_at=now,
        )
        if status != "ok":
            return None
        self.cache.put(
            key,
            proposal.model_dump_json(),
            ttl_seconds=self.budget.cache_ttl_seconds,
            now=now,
        )
        return proposal

    def run(
        self,
        snapshot: MaskedSnapshot,
        *,
        questions: Sequence[str],
        now: datetime | None = None,
        collect_hypotheses: bool = True,
    ) -> ArenaResult:
        """Run independent, anonymized cross-review, and optional hypothesis stages."""

        if not questions or any(not question.strip() for question in questions):
            raise ValueError("at least one non-empty question is required")
        instant = datetime.now(UTC) if now is None else now.astimezone(UTC)
        decision_id = self.ledger.append_decision(
            {
                "snapshot_hash": snapshot.content_hash(),
                "questions": list(questions),
                "authority": "veto_or_reduce_only",
            },
            self.versions,
        )
        answer_schema = ArenaAnswer.model_json_schema()
        base = {
            "snapshot": snapshot.model_dump(mode="json"),
            "questions": list(questions),
            "instruction": "Review an existing long-only setup. You may only veto or reduce it.",
        }
        independent_request = ProviderRequest(
            prompt=json.dumps(base, sort_keys=True), json_schema=answer_schema
        )
        answers = tuple(
            self._ask(
                provider,
                independent_request,
                decision_id=decision_id,
                now=instant,
                stage="independent",
            )
            for provider in self.providers
        )
        anonymous = [
            observation.answer.model_dump(mode="json")
            for observation in answers
            if observation.answer is not None
        ]
        review_request = ProviderRequest(
            prompt=json.dumps(
                {
                    **base,
                    "anonymous_peer_answers": anonymous,
                    "instruction": "Cross-review these anonymous answers; only veto or reduce.",
                },
                sort_keys=True,
            ),
            json_schema=answer_schema,
        )
        reviews = tuple(
            self._ask(
                provider,
                review_request,
                decision_id=decision_id,
                now=instant,
                stage="cross_review",
            )
            for provider in self.providers
        )
        hypotheses: list[HypothesisProposal] = []
        if collect_hypotheses:
            hypothesis_request = ProviderRequest(
                prompt=json.dumps(
                    {
                        "snapshot": snapshot.model_dump(mode="json"),
                        "instruction": "Propose one testable veto or reduction hypothesis.",
                    },
                    sort_keys=True,
                ),
                json_schema=HypothesisProposal.model_json_schema(),
            )
            for provider in self.providers:
                proposal = self._propose(
                    provider,
                    hypothesis_request,
                    decision_id=decision_id,
                    now=instant,
                )
                if proposal is None:
                    continue
                hypotheses.append(proposal)
                self.ledger.append_hypothesis(
                    proposal.model_dump(mode="json"), self.versions, decision_id=decision_id
                )
        valid = [
            observation.answer
            for observation in (*answers, *reviews)
            if observation.answer is not None
        ]
        multiplier = min((answer.safe_multiplier() for answer in valid), default=1.0)
        veto = multiplier == 0.0
        fingerprints = [
            answer.model_dump_json(exclude={"confidence"})
            for answer in (observation.answer for observation in answers)
            if answer is not None
        ]
        result = ArenaResult(
            decision_id=decision_id,
            answers=answers,
            cross_reviews=reviews,
            hypotheses=tuple(hypotheses),
            veto=veto,
            size_multiplier=multiplier,
            herding=herding_flag(fingerprints),
        )
        self.ledger.append_intervention(
            {
                "kind": "arena_constraint",
                "veto": result.veto,
                "size_multiplier": result.size_multiplier,
                "herding": result.herding,
            },
            self.versions,
            decision_id=decision_id,
        )
        return result
