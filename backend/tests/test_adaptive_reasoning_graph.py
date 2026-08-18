import asyncio
from uuid import UUID, uuid4

import pytest

from app.ai.adaptation.contracts import (
    AdaptationContext,
    AdaptationProposal,
)
from app.ai.evaluation.contracts import (
    EvaluationContext,
    EvaluationFeedbackMetrics,
    EvaluationGoalContext,
    EvaluationMetrics,
    EvaluationResult,
    EvaluationTemporalMetrics,
)
from app.ai.orchestration.adaptive_reasoning import (
    AdaptiveReasoningOrchestrator,
)


def evaluation_context() -> EvaluationContext:
    return EvaluationContext(
        goal=EvaluationGoalContext(
            title="Learn backend development",
            current_situation="Python fundamentals",
            expected_outcome="Build production APIs",
            target_timeframe="Three months",
            availability="Five hours per week",
        ),
        metrics=EvaluationMetrics(
            total_tasks=4,
            completed_tasks=3,
            skipped_tasks=0,
            pending_tasks=1,
            resolved_tasks=3,
            progress_percentage=75,
            xp_earned=30,
        ),
        feedback_metrics=EvaluationFeedbackMetrics(
            tasks_with_difficulty_feedback=3,
            easy_count=0,
            normal_count=0,
            difficult_count=3,
            tasks_with_feedback_text=0,
            tasks_without_explicit_feedback=0,
        ),
        temporal_metrics=EvaluationTemporalMetrics(
            resolved_tasks=3,
            first_resolved_at=None,
            last_resolved_at=None,
        ),
        missions=[],
        feedback_samples=[],
        deterministic_signals=[],
    )


def evaluation_result(*, needs_adaptation: bool) -> EvaluationResult:
    return EvaluationResult(
        status="struggling" if needs_adaptation else "on_track",
        summary="Execution evidence was evaluated.",
        signals=[],
        needs_adaptation=needs_adaptation,
    )


def adaptation_context(
    context: EvaluationContext,
    evaluation: EvaluationResult,
) -> AdaptationContext:
    return AdaptationContext(
        goal=context.goal,
        evaluation=evaluation,
        plan_outline=[],
        relevant_tasks=[],
        recent_observed_task_execution_history=(
            context.recent_observed_task_execution_history
        ),
    )


def adaptation_proposal() -> AdaptationProposal:
    return AdaptationProposal.model_validate(
        {
            "decision": "propose_changes",
            "summary": "Add one bounded reinforcement Task.",
            "rationale": "Repeated difficulty supports preparation.",
            "changes": [
                {
                    "type": "add_task",
                    "target": {
                        "stage_order_index": 0,
                        "stage_title": "Backend",
                        "mission_order_index": 0,
                        "mission_title": "API delivery",
                    },
                    "reason": "Observed difficulty supports reinforcement.",
                    "insert_after_task_order_index": None,
                    "task": {
                        "title": "Review API validation",
                        "description": None,
                        "estimated_duration_minutes": 30,
                        "xp_reward": 10,
                    },
                }
            ],
        }
    )


class FakeEvaluationService:
    def __init__(
        self,
        result: EvaluationResult | None = None,
        error: Exception | None = None,
        events: list[str] | None = None,
    ) -> None:
        self.result = result
        self.error = error
        self.events = events if events is not None else []
        self.contexts: list[EvaluationContext] = []

    async def evaluate(self, context: EvaluationContext) -> EvaluationResult:
        self.events.append("evaluate")
        self.contexts.append(context)
        if self.error is not None:
            raise self.error
        assert self.result is not None
        return self.result


class FakeAdaptationService:
    def __init__(
        self,
        result: AdaptationProposal | None = None,
        error: Exception | None = None,
        events: list[str] | None = None,
    ) -> None:
        self.result = result
        self.error = error
        self.events = events if events is not None else []
        self.calls: list[tuple[EvaluationResult, AdaptationContext | None]] = []

    async def propose(
        self,
        evaluation: EvaluationResult,
        context: AdaptationContext | None = None,
    ) -> AdaptationProposal:
        self.events.append("adapt")
        self.calls.append((evaluation, context))
        if self.error is not None:
            raise self.error
        assert self.result is not None
        return self.result


def orchestrator(
    *,
    evaluation: FakeEvaluationService,
    adaptation: FakeAdaptationService,
    events: list[str],
) -> AdaptiveReasoningOrchestrator:
    context = evaluation_context()

    def build_evaluation_context(
        _goal_id: UUID,
        _user_id: UUID,
    ) -> EvaluationContext:
        events.append("build_evaluation_context")
        return context

    def build_adaptation_context(
        _goal_id: UUID,
        _user_id: UUID,
        received_context: EvaluationContext,
        received_evaluation: EvaluationResult,
    ) -> AdaptationContext:
        events.append("build_adaptation_context")
        assert received_context is context
        return adaptation_context(received_context, received_evaluation)

    return AdaptiveReasoningOrchestrator(
        evaluation_service=evaluation,
        adaptation_service=adaptation,
        build_evaluation_context=build_evaluation_context,
        build_adaptation_context=build_adaptation_context,
    )


def test_graph_ends_after_evaluation_when_adaptation_is_not_needed() -> None:
    events: list[str] = []
    evaluation = FakeEvaluationService(
        evaluation_result(needs_adaptation=False), events=events
    )
    adaptation = FakeAdaptationService(events=events)
    graph = orchestrator(
        evaluation=evaluation,
        adaptation=adaptation,
        events=events,
    )

    result = asyncio.run(graph.run(user_id=uuid4(), goal_id=uuid4()))

    assert events == ["build_evaluation_context", "evaluate"]
    assert result["evaluation"] == evaluation.result
    assert "adaptation" not in result
    assert adaptation.calls == []


def test_graph_routes_evaluation_to_adaptation_without_extra_calls() -> None:
    events: list[str] = []
    evaluation = FakeEvaluationService(
        evaluation_result(needs_adaptation=True), events=events
    )
    proposal = adaptation_proposal()
    adaptation = FakeAdaptationService(proposal, events=events)
    graph = orchestrator(
        evaluation=evaluation,
        adaptation=adaptation,
        events=events,
    )

    result = asyncio.run(graph.run(user_id=uuid4(), goal_id=uuid4()))

    assert events == [
        "build_evaluation_context",
        "evaluate",
        "build_adaptation_context",
        "adapt",
    ]
    assert len(evaluation.contexts) == 1
    assert len(adaptation.calls) == 1
    received_evaluation, received_context = adaptation.calls[0]
    assert received_evaluation is evaluation.result
    assert received_context is not None
    assert received_context.evaluation == evaluation.result
    assert result["adaptation"] == proposal
    assert result["adaptation"].decision == "propose_changes"


def test_graph_propagates_evaluation_errors() -> None:
    events: list[str] = []
    error = RuntimeError("Evaluation failed")
    graph = orchestrator(
        evaluation=FakeEvaluationService(error=error, events=events),
        adaptation=FakeAdaptationService(events=events),
        events=events,
    )

    with pytest.raises(RuntimeError, match="Evaluation failed"):
        asyncio.run(graph.run(user_id=uuid4(), goal_id=uuid4()))

    assert events == ["build_evaluation_context", "evaluate"]


def test_graph_propagates_adaptation_errors_without_accepting_changes() -> None:
    events: list[str] = []
    error = RuntimeError("Adaptation failed")
    graph = orchestrator(
        evaluation=FakeEvaluationService(
            evaluation_result(needs_adaptation=True), events=events
        ),
        adaptation=FakeAdaptationService(error=error, events=events),
        events=events,
    )

    with pytest.raises(RuntimeError, match="Adaptation failed"):
        asyncio.run(graph.run(user_id=uuid4(), goal_id=uuid4()))

    assert events == [
        "build_evaluation_context",
        "evaluate",
        "build_adaptation_context",
        "adapt",
    ]
