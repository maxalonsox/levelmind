import asyncio
import logging
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

import httpx
import pytest
from httpx import ASGITransport, AsyncClient, Response
from openai import RateLimitError
from sqlalchemy import event, func, select
from sqlalchemy.orm import Session

from app.ai.adaptation.contracts import AdaptationContext
from app.ai.adaptation.errors import (
    AdaptationProviderAPIError,
    AdaptationProviderTimeoutError,
)
from app.ai.orchestration.adaptive_reasoning import (
    AdaptiveReasoningOrchestrator,
)
from app.ai.errors import AIConfigurationError
from app.ai.evaluation.contracts import EvaluationContext, EvaluationResult
from app.ai.evaluation.errors import EvaluationProviderTimeoutError
from app.api.adaptation_preview import get_adaptation_provider_factory
from app.api.evaluation_preview import get_evaluation_provider_factory
from app.main import app
from app.models.goal import Goal
from app.models.memory_entry import MemoryEntry
from app.models.mission import Mission
from app.models.plan_adaptation import PlanAdaptation
from app.models.plan_revision import PlanRevision
from app.models.stage import Stage
from app.models.task import Task


async def post_adaptation(goal_id: UUID) -> Response:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        return await client.post(f"/goals/{goal_id}/adaptation/preview")


def persist_goal(db: Session, user_id: UUID) -> Goal:
    goal = Goal(
        user_id=user_id,
        title="Become a backend developer",
        current_situation="I know Python fundamentals",
        expected_outcome="Build production APIs",
        target_timeframe="Six months",
        availability="Eight hours per week",
    )
    db.add(goal)
    db.commit()
    return goal


def persist_plan(db: Session, goal: Goal) -> list[Task]:
    stage = Stage(goal_id=goal.id, title="Backend", order_index=0)
    mission = Mission(title="API delivery", order_index=0)
    mission.tasks = [
        Task(
            title=f"Completed {index}",
            order_index=index,
            status="completed",
            difficulty_feedback="difficult",
            feedback_text="This required repeated debugging.",
            xp_reward=10,
        )
        for index in range(3)
    ]
    mission.tasks.append(
        Task(
            title="Implement endpoint",
            order_index=3,
            estimated_duration_minutes=45,
            xp_reward=10,
        )
    )
    stage.missions.append(mission)
    db.add(stage)
    db.commit()
    return mission.tasks


def evaluation_result(*, needs_adaptation: bool) -> EvaluationResult:
    return EvaluationResult(
        status="struggling" if needs_adaptation else "on_track",
        summary="Execution evidence was evaluated.",
        signals=(
            [
                {
                    "type": "high_difficulty",
                    "description": "Three Tasks were marked difficult.",
                    "severity": "high",
                }
            ]
            if needs_adaptation
            else []
        ),
        needs_adaptation=needs_adaptation,
    )


def proposal(*, task_order_index: int = 3) -> dict[str, Any]:
    return {
        "decision": "propose_changes",
        "summary": "Increase one duration estimate.",
        "rationale": "Repeated difficulty supports one bounded adjustment.",
        "changes": [
            {
                "type": "adjust_task_duration",
                "target": {
                    "stage_order_index": 0,
                    "stage_title": "Backend",
                    "mission_order_index": 0,
                    "mission_title": "API delivery",
                    "task_order_index": task_order_index,
                    "task_title": "Implement endpoint",
                },
                "reason": "The existing estimate is optimistic.",
                "estimated_duration_minutes": 90,
            }
        ],
    }


def no_change_proposal() -> dict[str, Any]:
    return {
        "decision": "no_change",
        "summary": "No safe plan change was identified.",
        "rationale": "The evidence does not support a concrete target change.",
        "changes": [],
    }


class FakeEvaluationProvider:
    def __init__(
        self,
        result: EvaluationResult | None = None,
        error: Exception | None = None,
    ) -> None:
        self.result = result
        self.error = error
        self.contexts: list[EvaluationContext] = []
        self.closed = False

    async def evaluate(self, context: EvaluationContext) -> EvaluationResult:
        self.contexts.append(context)
        if self.error is not None:
            raise self.error
        assert self.result is not None
        return self.result

    async def close(self) -> None:
        self.closed = True


class FakeAdaptationProvider:
    def __init__(self, result: Any = None, error: Exception | None = None) -> None:
        self.result = result
        self.error = error
        self.contexts: list[AdaptationContext] = []
        self.closed = False

    async def propose(self, context: AdaptationContext) -> Any:
        self.contexts.append(context)
        if self.error is not None:
            raise self.error
        return self.result

    async def close(self) -> None:
        self.closed = True


def test_adaptation_preview_short_circuits_without_adaptation_provider(
    db_session: Session,
    authenticated_user_id: UUID,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    goal = persist_goal(db_session, authenticated_user_id)
    persist_plan(db_session, goal)
    evaluator = FakeEvaluationProvider(
        evaluation_result(needs_adaptation=False)
    )
    adaptation_factory_calls = 0
    orchestrator_run_calls = 0
    original_run = AdaptiveReasoningOrchestrator.run

    async def tracked_run(
        orchestrator: AdaptiveReasoningOrchestrator,
        *,
        user_id: UUID,
        goal_id: UUID,
    ):
        nonlocal orchestrator_run_calls
        orchestrator_run_calls += 1
        return await original_run(
            orchestrator,
            user_id=user_id,
            goal_id=goal_id,
        )

    monkeypatch.setattr(AdaptiveReasoningOrchestrator, "run", tracked_run)

    def fail_if_constructed() -> FakeAdaptationProvider:
        nonlocal adaptation_factory_calls
        adaptation_factory_calls += 1
        raise AssertionError("Adaptation provider must not be constructed")

    app.dependency_overrides[get_evaluation_provider_factory] = (
        lambda: lambda: evaluator
    )
    app.dependency_overrides[get_adaptation_provider_factory] = (
        lambda: fail_if_constructed
    )
    try:
        response = asyncio.run(post_adaptation(goal.id))
    finally:
        app.dependency_overrides.pop(get_evaluation_provider_factory, None)
        app.dependency_overrides.pop(get_adaptation_provider_factory, None)

    assert response.status_code == 200
    assert response.json()["needs_adaptation"] is False
    assert response.json()["decision"] == "no_change"
    assert response.json()["changes"] == []
    assert response.json()["adaptation"] is None
    assert orchestrator_run_calls == 1
    assert len(evaluator.contexts) == 1
    assert adaptation_factory_calls == 0
    assert (
        db_session.scalar(
            select(func.count()).select_from(PlanAdaptation)
        )
        == 0
    )
    assert (
        db_session.scalar(select(func.count()).select_from(PlanRevision)) == 0
    )


def test_adaptation_preview_does_not_reuse_evidence_before_accepted_revision(
    db_session: Session,
    authenticated_user_id: UUID,
) -> None:
    old_time = datetime(2026, 8, 1, 12, tzinfo=UTC)
    cutoff = old_time + timedelta(days=1)
    goal = persist_goal(db_session, authenticated_user_id)
    tasks = persist_plan(db_session, goal)
    for task in tasks[:3]:
        task.resolved_at = old_time
    base_revision = PlanRevision(
        goal_id=goal.id,
        revision_number=1,
        snapshot={"stages": []},
        created_at=old_time,
    )
    db_session.add(base_revision)
    db_session.commit()
    accepted_adaptation = PlanAdaptation(
        goal_id=goal.id,
        base_revision_id=base_revision.id,
        proposal=proposal(),
        status="accepted",
        reviewed_at=cutoff,
    )
    db_session.add(accepted_adaptation)
    db_session.commit()
    db_session.add(
        PlanRevision(
            goal_id=goal.id,
            revision_number=2,
            snapshot={"stages": []},
            base_revision_id=base_revision.id,
            adaptation_id=accepted_adaptation.id,
            created_at=cutoff,
        )
    )
    db_session.commit()
    evaluation_factory_calls = 0
    adaptation_factory_calls = 0

    def fail_evaluation_factory() -> FakeEvaluationProvider:
        nonlocal evaluation_factory_calls
        evaluation_factory_calls += 1
        raise AssertionError("Old evidence must not invoke Evaluation")

    def fail_adaptation_factory() -> FakeAdaptationProvider:
        nonlocal adaptation_factory_calls
        adaptation_factory_calls += 1
        raise AssertionError("Adaptation Planner must not be invoked")

    app.dependency_overrides[get_evaluation_provider_factory] = (
        lambda: fail_evaluation_factory
    )
    app.dependency_overrides[get_adaptation_provider_factory] = (
        lambda: fail_adaptation_factory
    )
    try:
        response = asyncio.run(post_adaptation(goal.id))
    finally:
        app.dependency_overrides.pop(get_evaluation_provider_factory, None)
        app.dependency_overrides.pop(get_adaptation_provider_factory, None)

    assert response.status_code == 200
    assert response.json()["needs_adaptation"] is False
    assert response.json()["decision"] == "no_change"
    assert response.json()["adaptation"] is None
    assert evaluation_factory_calls == 0
    assert adaptation_factory_calls == 0


def test_adaptation_preview_persists_validated_pending_proposal_without_mutation(
    db_session: Session,
    authenticated_user_id: UUID,
) -> None:
    goal = persist_goal(db_session, authenticated_user_id)
    tasks = persist_plan(db_session, goal)
    db_session.add_all(
        [
            MemoryEntry(
                user_id=authenticated_user_id,
                goal_id=goal.id,
                memory_type="observed",
                key="task_execution",
                value={
                    "result": "completed",
                    "estimated_difficulty": "normal",
                    "difficulty_feedback": "difficult",
                    "feedback_text": "Must not enter either LLM context.",
                },
                source_type="task",
                source_id=uuid4(),
                confidence=1,
            )
            for _ in range(15)
        ]
    )
    db_session.commit()
    evaluator = FakeEvaluationProvider(
        evaluation_result(needs_adaptation=True)
    )
    adapter = FakeAdaptationProvider(proposal())
    before = (
        db_session.scalar(select(func.count()).select_from(Stage)),
        db_session.scalar(select(func.count()).select_from(Mission)),
        db_session.scalar(select(func.count()).select_from(Task)),
        [(task.status, task.estimated_duration_minutes) for task in tasks],
    )

    app.dependency_overrides[get_evaluation_provider_factory] = (
        lambda: lambda: evaluator
    )
    app.dependency_overrides[get_adaptation_provider_factory] = (
        lambda: lambda: adapter
    )
    try:
        response = asyncio.run(post_adaptation(goal.id))
    finally:
        app.dependency_overrides.pop(get_evaluation_provider_factory, None)
        app.dependency_overrides.pop(get_adaptation_provider_factory, None)

    assert response.status_code == 200
    payload = response.json()
    assert payload["needs_adaptation"] is True
    assert {
        key: payload[key]
        for key in ("decision", "summary", "rationale", "changes")
    } == proposal()
    assert payload["adaptation"]["goal_id"] == str(goal.id)
    assert payload["adaptation"]["proposal"] == proposal()
    assert payload["adaptation"]["status"] == "pending"
    assert payload["adaptation"]["reviewed_at"] is None
    assert payload["adaptation"]["created_at"] is not None
    assert payload["adaptation"]["updated_at"] is not None
    assert len(adapter.contexts) == 1
    assert len(evaluator.contexts) == 1
    assert adapter.closed is True
    evaluation_memory = (
        evaluator.contexts[0].recent_observed_task_execution_history
    )
    adaptation_memory = (
        adapter.contexts[0].recent_observed_task_execution_history
    )
    assert adaptation_memory == evaluation_memory
    assert len(adaptation_memory) == 10
    context_text = str(adapter.contexts[0].model_dump(mode="json"))
    assert str(goal.id) not in context_text
    assert str(goal.user_id) not in context_text
    assert "Must not enter either LLM context." not in context_text
    db_session.expire_all()
    persisted_adaptation = db_session.scalar(select(PlanAdaptation))
    assert persisted_adaptation is not None
    assert (
        db_session.scalar(
            select(func.count()).select_from(PlanAdaptation)
        )
        == 1
    )
    assert str(persisted_adaptation.id) == payload["adaptation"]["id"]
    assert persisted_adaptation.goal_id == goal.id
    assert persisted_adaptation.base_revision_id == UUID(
        payload["adaptation"]["base_revision_id"]
    )
    assert persisted_adaptation.status == "pending"
    assert persisted_adaptation.proposal == proposal()
    assert persisted_adaptation.reviewed_at is None
    base_revision = db_session.scalar(select(PlanRevision))
    assert base_revision is not None
    assert base_revision.id == persisted_adaptation.base_revision_id
    assert base_revision.revision_number == 1
    assert (
        db_session.scalar(select(func.count()).select_from(PlanRevision)) == 1
    )
    assert (
        db_session.scalar(select(func.count()).select_from(Stage)),
        db_session.scalar(select(func.count()).select_from(Mission)),
        db_session.scalar(select(func.count()).select_from(Task)),
        [
            (task.status, task.estimated_duration_minutes)
            for task in db_session.scalars(
                select(Task).order_by(Task.order_index)
            )
        ],
    ) == before


def test_adaptation_preview_does_not_persist_provider_no_change_proposal(
    db_session: Session,
    authenticated_user_id: UUID,
) -> None:
    goal = persist_goal(db_session, authenticated_user_id)
    persist_plan(db_session, goal)
    evaluator = FakeEvaluationProvider(
        evaluation_result(needs_adaptation=True)
    )
    adapter = FakeAdaptationProvider(no_change_proposal())

    app.dependency_overrides[get_evaluation_provider_factory] = (
        lambda: lambda: evaluator
    )
    app.dependency_overrides[get_adaptation_provider_factory] = (
        lambda: lambda: adapter
    )
    try:
        response = asyncio.run(post_adaptation(goal.id))
    finally:
        app.dependency_overrides.pop(get_evaluation_provider_factory, None)
        app.dependency_overrides.pop(get_adaptation_provider_factory, None)

    assert response.status_code == 200
    assert response.json() == {
        **no_change_proposal(),
        "needs_adaptation": True,
        "adaptation": None,
    }
    assert (
        db_session.scalar(
            select(func.count()).select_from(PlanAdaptation)
        )
        == 0
    )
    assert (
        db_session.scalar(select(func.count()).select_from(PlanRevision)) == 1
    )


def test_adaptation_preview_requires_authentication(db_session: Session) -> None:
    goal = persist_goal(db_session, uuid4())

    response = asyncio.run(post_adaptation(goal.id))

    assert response.status_code == 401


def test_adaptation_preview_hides_foreign_goal_before_providers(
    db_session: Session,
    authenticated_user_id: UUID,
) -> None:
    goal = persist_goal(db_session, uuid4())
    persist_plan(db_session, goal)
    evaluator_factory_calls = 0

    def evaluator_factory() -> FakeEvaluationProvider:
        nonlocal evaluator_factory_calls
        evaluator_factory_calls += 1
        return FakeEvaluationProvider(evaluation_result(needs_adaptation=True))

    app.dependency_overrides[get_evaluation_provider_factory] = (
        lambda: evaluator_factory
    )
    try:
        response = asyncio.run(post_adaptation(goal.id))
    finally:
        app.dependency_overrides.pop(get_evaluation_provider_factory, None)

    assert response.status_code == 404
    assert response.json() == {"detail": "Goal not found"}
    assert evaluator_factory_calls == 0
    assert (
        db_session.scalar(
            select(func.count()).select_from(PlanAdaptation)
        )
        == 0
    )


def test_adaptation_preview_maps_invalid_target_to_502(
    db_session: Session,
    authenticated_user_id: UUID,
) -> None:
    goal = persist_goal(db_session, authenticated_user_id)
    persist_plan(db_session, goal)
    evaluator = FakeEvaluationProvider(
        evaluation_result(needs_adaptation=True)
    )
    adapter = FakeAdaptationProvider(proposal(task_order_index=99))
    app.dependency_overrides[get_evaluation_provider_factory] = (
        lambda: lambda: evaluator
    )
    app.dependency_overrides[get_adaptation_provider_factory] = (
        lambda: lambda: adapter
    )
    try:
        response = asyncio.run(post_adaptation(goal.id))
    finally:
        app.dependency_overrides.pop(get_evaluation_provider_factory, None)
        app.dependency_overrides.pop(get_adaptation_provider_factory, None)

    assert response.status_code == 502
    assert response.json() == {
        "detail": "Adaptation provider returned an invalid response"
    }
    assert (
        db_session.scalar(
            select(func.count()).select_from(PlanAdaptation)
        )
        == 0
    )


def test_adaptation_preview_exposes_only_safe_rate_limit_detail(
    db_session: Session,
    authenticated_user_id: UUID,
) -> None:
    goal = persist_goal(db_session, authenticated_user_id)
    persist_plan(db_session, goal)
    request = httpx.Request(
        "POST", "https://provider.example/v1/chat/completions"
    )
    response = httpx.Response(429, request=request)
    provider_error = RateLimitError(
        "secret provider response",
        response=response,
        body={"secret": "must not leak"},
    )
    adaptation_error = AdaptationProviderAPIError(
        "Adaptation provider is temporarily unavailable"
    )
    adaptation_error.__cause__ = provider_error
    evaluator = FakeEvaluationProvider(
        evaluation_result(needs_adaptation=True)
    )
    adapter = FakeAdaptationProvider(error=adaptation_error)
    app.dependency_overrides[get_evaluation_provider_factory] = (
        lambda: lambda: evaluator
    )
    app.dependency_overrides[get_adaptation_provider_factory] = (
        lambda: lambda: adapter
    )
    try:
        response = asyncio.run(post_adaptation(goal.id))
    finally:
        app.dependency_overrides.pop(get_evaluation_provider_factory, None)
        app.dependency_overrides.pop(get_adaptation_provider_factory, None)

    assert response.status_code == 502
    assert response.json() == {
        "detail": "AI service rate limit exceeded"
    }
    assert "secret" not in response.text


def test_adaptation_preview_does_not_persist_invalid_provider_response(
    db_session: Session,
    authenticated_user_id: UUID,
    caplog: pytest.LogCaptureFixture,
) -> None:
    goal = persist_goal(db_session, authenticated_user_id)
    persist_plan(db_session, goal)
    evaluator = FakeEvaluationProvider(
        evaluation_result(needs_adaptation=True)
    )
    adapter = FakeAdaptationProvider(
        {
            "decision": "propose_changes",
            "summary": "Invalid proposal",
            "rationale": "The changes required by this decision are absent.",
            "changes": [],
        }
    )
    app.dependency_overrides[get_evaluation_provider_factory] = (
        lambda: lambda: evaluator
    )
    app.dependency_overrides[get_adaptation_provider_factory] = (
        lambda: lambda: adapter
    )
    try:
        with caplog.at_level(logging.WARNING):
            response = asyncio.run(post_adaptation(goal.id))
    finally:
        app.dependency_overrides.pop(get_evaluation_provider_factory, None)
        app.dependency_overrides.pop(get_adaptation_provider_factory, None)

    assert response.status_code == 502
    assert response.json() == {
        "detail": "Adaptation provider returned an invalid response"
    }
    record = next(
        record
        for record in caplog.records
        if record.message == "Adaptation preview cognitive component failed"
    )
    assert record.component == "adaptation"
    assert record.goal_id == str(goal.id)
    assert record.error_type == "InvalidAdaptationProposalError"
    assert record.validation_errors
    assert "Invalid proposal" not in caplog.text
    assert "The changes required by this decision are absent." not in caplog.text
    assert adapter.closed is True
    assert (
        db_session.scalar(
            select(func.count()).select_from(PlanAdaptation)
        )
        == 0
    )


def test_adaptation_preview_logs_evaluation_contract_failure_separately(
    db_session: Session,
    authenticated_user_id: UUID,
    caplog: pytest.LogCaptureFixture,
) -> None:
    goal = persist_goal(db_session, authenticated_user_id)
    persist_plan(db_session, goal)
    evaluator = FakeEvaluationProvider(
        {
            "status": "unexpected_internal_status",
            "summary": "Raw provider content must stay private.",
            "signals": [],
            "needs_adaptation": False,
        }  # type: ignore[arg-type]
    )
    app.dependency_overrides[get_evaluation_provider_factory] = (
        lambda: lambda: evaluator
    )
    try:
        with caplog.at_level(logging.WARNING):
            response = asyncio.run(post_adaptation(goal.id))
    finally:
        app.dependency_overrides.pop(get_evaluation_provider_factory, None)

    assert response.status_code == 502
    assert response.json() == {
        "detail": "Evaluation provider returned an invalid response"
    }
    record = next(
        record
        for record in caplog.records
        if record.message == "Adaptation preview cognitive component failed"
    )
    assert record.component == "evaluation"
    assert record.goal_id == str(goal.id)
    assert record.error_type == "InvalidEvaluationResultError"
    assert record.validation_errors
    assert "unexpected_internal_status" not in caplog.text
    assert "Raw provider content must stay private." not in caplog.text


@pytest.mark.parametrize(
    ("factory", "expected_status", "expected_detail"),
    [
        (
            lambda: (_ for _ in ()).throw(
                AIConfigurationError("Missing AI configuration: AI_API_KEY")
            ),
            503,
            "Missing AI configuration: AI_API_KEY",
        ),
        (
            lambda: FakeAdaptationProvider(
                error=AdaptationProviderTimeoutError("internal timeout")
            ),
            504,
            "Adaptation provider timed out",
        ),
    ],
)
def test_adaptation_preview_maps_adaptation_errors(
    factory,
    expected_status: int,
    expected_detail: str,
    db_session: Session,
    authenticated_user_id: UUID,
) -> None:
    goal = persist_goal(db_session, authenticated_user_id)
    persist_plan(db_session, goal)
    evaluator = FakeEvaluationProvider(
        evaluation_result(needs_adaptation=True)
    )
    app.dependency_overrides[get_evaluation_provider_factory] = (
        lambda: lambda: evaluator
    )
    app.dependency_overrides[get_adaptation_provider_factory] = lambda: factory
    try:
        response = asyncio.run(post_adaptation(goal.id))
    finally:
        app.dependency_overrides.pop(get_evaluation_provider_factory, None)
        app.dependency_overrides.pop(get_adaptation_provider_factory, None)

    assert response.status_code == expected_status
    assert response.json() == {"detail": expected_detail}
    assert (
        db_session.scalar(
            select(func.count()).select_from(PlanAdaptation)
        )
        == 0
    )
    assert (
        db_session.scalar(select(func.count()).select_from(PlanRevision)) == 1
    )


def test_adaptation_preview_evaluation_error_does_not_persist(
    db_session: Session,
    authenticated_user_id: UUID,
) -> None:
    goal = persist_goal(db_session, authenticated_user_id)
    persist_plan(db_session, goal)
    evaluator = FakeEvaluationProvider(
        error=EvaluationProviderTimeoutError("internal timeout")
    )
    adaptation_factory_calls = 0

    def fail_if_constructed() -> FakeAdaptationProvider:
        nonlocal adaptation_factory_calls
        adaptation_factory_calls += 1
        raise AssertionError("Adaptation provider must not be constructed")

    app.dependency_overrides[get_evaluation_provider_factory] = (
        lambda: lambda: evaluator
    )
    app.dependency_overrides[get_adaptation_provider_factory] = (
        lambda: fail_if_constructed
    )
    try:
        response = asyncio.run(post_adaptation(goal.id))
    finally:
        app.dependency_overrides.pop(get_evaluation_provider_factory, None)
        app.dependency_overrides.pop(get_adaptation_provider_factory, None)

    assert response.status_code == 504
    assert response.json() == {"detail": "Evaluation provider timed out"}
    assert len(evaluator.contexts) == 1
    assert evaluator.closed is True
    assert adaptation_factory_calls == 0
    assert (
        db_session.scalar(
            select(func.count()).select_from(PlanAdaptation)
        )
        == 0
    )
    assert (
        db_session.scalar(select(func.count()).select_from(PlanRevision)) == 0
    )


def test_adaptation_preview_rolls_back_failed_pending_persistence(
    db_session: Session,
    authenticated_user_id: UUID,
) -> None:
    goal = persist_goal(db_session, authenticated_user_id)
    persist_plan(db_session, goal)
    evaluator = FakeEvaluationProvider(
        evaluation_result(needs_adaptation=True)
    )
    adapter = FakeAdaptationProvider(proposal())

    def fail_insert(_mapper, _connection, _target: PlanAdaptation) -> None:
        raise RuntimeError("Deliberate PlanAdaptation persistence failure")

    app.dependency_overrides[get_evaluation_provider_factory] = (
        lambda: lambda: evaluator
    )
    app.dependency_overrides[get_adaptation_provider_factory] = (
        lambda: lambda: adapter
    )
    event.listen(PlanAdaptation, "before_insert", fail_insert)
    try:
        with pytest.raises(
            RuntimeError,
            match="Deliberate PlanAdaptation persistence failure",
        ):
            asyncio.run(post_adaptation(goal.id))
    finally:
        event.remove(PlanAdaptation, "before_insert", fail_insert)
        app.dependency_overrides.pop(get_evaluation_provider_factory, None)
        app.dependency_overrides.pop(get_adaptation_provider_factory, None)

    assert len(evaluator.contexts) == 1
    assert len(adapter.contexts) == 1
    assert (
        db_session.scalar(
            select(func.count()).select_from(PlanAdaptation)
        )
        == 0
    )
    assert (
        db_session.scalar(select(func.count()).select_from(PlanRevision)) == 1
    )
