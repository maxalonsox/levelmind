import asyncio
from typing import Any

import pytest

from app.ai.evaluation.contracts import (
    EvaluationContext,
    EvaluationFeedbackMetrics,
    EvaluationGoalContext,
    EvaluationMetrics,
    EvaluationResult,
    EvaluationStatus,
    EvaluationTemporalMetrics,
)
from app.ai.evaluation.errors import InvalidEvaluationResultError
from app.ai.evaluation.prompts import (
    EVALUATION_SYSTEM_PROMPT,
    build_evaluation_prompt,
)
from app.services.evaluation import EvaluationService


def evaluation_context(
    *,
    total_tasks: int = 10,
    completed_tasks: int = 3,
    skipped_tasks: int = 0,
    easy_count: int = 0,
    difficult_count: int = 0,
) -> EvaluationContext:
    resolved_tasks = completed_tasks + skipped_tasks
    return EvaluationContext(
        goal=EvaluationGoalContext(
            title="Learn backend development",
            current_situation="Python fundamentals",
            expected_outcome="Build production APIs",
            target_timeframe="Six months",
            availability="Eight hours per week",
        ),
        metrics=EvaluationMetrics(
            total_tasks=total_tasks,
            completed_tasks=completed_tasks,
            skipped_tasks=skipped_tasks,
            pending_tasks=total_tasks - resolved_tasks,
            resolved_tasks=resolved_tasks,
            progress_percentage=round(
                completed_tasks / total_tasks * 100, 2
            ),
            xp_earned=completed_tasks * 10,
        ),
        feedback_metrics=EvaluationFeedbackMetrics(
            tasks_with_difficulty_feedback=resolved_tasks,
            easy_count=easy_count,
            normal_count=resolved_tasks - easy_count - difficult_count,
            difficult_count=difficult_count,
            tasks_with_feedback_text=0,
            tasks_without_explicit_feedback=0,
        ),
        temporal_metrics=EvaluationTemporalMetrics(
            resolved_tasks=resolved_tasks,
            first_resolved_at=None,
            last_resolved_at=None,
        ),
        missions=[],
        feedback_samples=[],
        deterministic_signals=[],
    )


def valid_result() -> EvaluationResult:
    return EvaluationResult(
        status="on_track",
        summary="Observed execution is consistent with the current plan.",
        signals=[],
        needs_adaptation=False,
    )


def adaptation_result(
    *,
    status: EvaluationStatus = EvaluationStatus.STRUGGLING,
) -> EvaluationResult:
    return EvaluationResult(
        status=status,
        summary="The provider recommends changing the plan.",
        signals=[],
        needs_adaptation=True,
    )


class FakeProvider:
    def __init__(self, result: Any) -> None:
        self.result = result
        self.contexts: list[EvaluationContext] = []
        self.closed = False

    async def evaluate(self, context: EvaluationContext) -> Any:
        self.contexts.append(context)
        return self.result

    async def close(self) -> None:
        self.closed = True


@pytest.mark.parametrize(
    "context",
    [
        evaluation_context(total_tasks=4, completed_tasks=0),
        evaluation_context(total_tasks=4, completed_tasks=1),
        evaluation_context(total_tasks=20, completed_tasks=2),
    ],
)
def test_evaluation_service_returns_insufficient_data_without_provider(
    context: EvaluationContext,
) -> None:
    factory_calls = 0

    def fail_if_provider_is_constructed() -> FakeProvider:
        nonlocal factory_calls
        factory_calls += 1
        raise AssertionError("Insufficient data must not construct a provider")

    result = asyncio.run(
        EvaluationService(fail_if_provider_is_constructed).evaluate(context)
    )

    assert result.status is EvaluationStatus.INSUFFICIENT_DATA
    assert result.needs_adaptation is False
    assert result.signals[0].type == "insufficient_data"
    assert factory_calls == 0


def test_evaluation_service_invokes_provider_when_evidence_is_sufficient() -> None:
    context = evaluation_context(total_tasks=10, completed_tasks=2)
    provider = FakeProvider(valid_result())

    result = asyncio.run(
        EvaluationService(lambda: provider).evaluate(context)
    )

    assert result == valid_result()
    assert provider.contexts == [context]
    assert provider.closed is True


def test_repeated_normal_execution_is_on_track_without_adaptation() -> None:
    context = evaluation_context(completed_tasks=4)
    provider = FakeProvider(adaptation_result())

    result = asyncio.run(
        EvaluationService(lambda: provider).evaluate(context)
    )

    assert result.status is EvaluationStatus.ON_TRACK
    assert result.needs_adaptation is False
    assert result.signals == []
    assert provider.contexts == [context]


def test_one_difficult_task_cannot_trigger_adaptation() -> None:
    context = evaluation_context(completed_tasks=3, difficult_count=1)
    provider = FakeProvider(adaptation_result())

    result = asyncio.run(
        EvaluationService(lambda: provider).evaluate(context)
    )

    assert result.needs_adaptation is False


@pytest.mark.parametrize(
    ("context", "status"),
    [
        (
            evaluation_context(completed_tasks=1, skipped_tasks=2),
            EvaluationStatus.STRUGGLING,
        ),
        (
            evaluation_context(completed_tasks=3, difficult_count=2),
            EvaluationStatus.STRUGGLING,
        ),
        (
            evaluation_context(completed_tasks=3, easy_count=3),
            EvaluationStatus.PROGRESSING_FAST,
        ),
        (
            evaluation_context(
                completed_tasks=2,
                skipped_tasks=1,
                difficult_count=1,
            ),
            EvaluationStatus.MIXED,
        ),
    ],
)
def test_persistent_patterns_still_allow_adaptation(
    context: EvaluationContext,
    status: EvaluationStatus,
) -> None:
    provider = FakeProvider(adaptation_result(status=status))

    result = asyncio.run(
        EvaluationService(lambda: provider).evaluate(context)
    )

    assert result.needs_adaptation is True
    assert result.status is status


@pytest.mark.parametrize(
    "status",
    [EvaluationStatus.INSUFFICIENT_DATA, EvaluationStatus.ON_TRACK],
)
def test_semantically_non_adaptive_status_cannot_request_adaptation(
    status: EvaluationStatus,
) -> None:
    context = evaluation_context(completed_tasks=3, difficult_count=2)
    provider = FakeProvider(adaptation_result(status=status))

    result = asyncio.run(
        EvaluationService(lambda: provider).evaluate(context)
    )

    assert result.status is status
    assert result.needs_adaptation is False


def test_evaluation_service_revalidates_provider_result() -> None:
    context = evaluation_context()
    provider = FakeProvider(
        {
            "status": "unsupported",
            "summary": "Invalid status",
            "signals": [],
            "needs_adaptation": False,
        }
    )

    with pytest.raises(InvalidEvaluationResultError):
        asyncio.run(EvaluationService(lambda: provider).evaluate(context))

    assert provider.closed is True


def test_evaluation_prompt_requires_conservative_non_mutating_analysis() -> None:
    prompt = " ".join(EVALUATION_SYSTEM_PROMPT.lower().split())

    assert "never modify the plan" in prompt
    assert "observed facts from interpretations" in prompt
    assert "not failure" in prompt
    assert "one difficult task is not enough" in prompt
    assert "the default decision is needs_adaptation=false" in prompt
    assert "not to find a change" in prompt
    assert "persistent-pattern criteria" in prompt
    assert "do not diagnose emotions, health, psychology" in prompt
    assert "factual historical evidence" in prompt
    assert "not a declared preference" in prompt
    assert "in spanish" in prompt
    assert "one or two short, direct sentences" in prompt
    assert "never mention internal status or contract names" in prompt
    assert "insufficient_data" in prompt
    assert "do not provide chain-of-thought" in prompt
    assert "return only a json object" in prompt

    user_prompt = build_evaluation_prompt(evaluation_context()).user
    assert "recent_observed_task_execution_history" not in user_prompt
