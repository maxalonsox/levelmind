import asyncio
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy.orm import Session

from app.ai.evaluation.contracts import (
    EvaluationResult,
    EvaluationSignalType,
    EvaluationStatus,
)
from app.models.enums import PlanningStatus
from app.models.goal import Goal
from app.models.memory_entry import MemoryEntry
from app.models.mission import Mission
from app.models.plan_adaptation import PlanAdaptation
from app.models.plan_revision import PlanRevision
from app.models.stage import Stage
from app.models.task import Task
from app.services.evaluation import EvaluationService
from app.services.evaluation_context import build_evaluation_context


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


def add_mission(
    db: Session,
    goal: Goal,
    tasks: list[Task],
    *,
    stage_title: str = "Backend",
    mission_title: str = "API delivery",
    estimated_difficulty: str | None = "normal",
) -> Mission:
    stage = Stage(goal_id=goal.id, title=stage_title, order_index=0)
    mission = Mission(
        title=mission_title,
        order_index=0,
        estimated_difficulty=estimated_difficulty,
    )
    mission.tasks = tasks
    stage.missions.append(mission)
    db.add(stage)
    db.commit()
    return mission


def resolved_task(
    title: str,
    order_index: int,
    *,
    status: str = "completed",
    difficulty: str | None = None,
    feedback: str | None = None,
    xp_reward: int = 10,
    resolved_at: datetime | None = None,
) -> Task:
    return Task(
        title=title,
        description="Task details must not enter EvaluationContext",
        order_index=order_index,
        status=status,
        difficulty_feedback=difficulty,
        feedback_text=feedback,
        xp_reward=xp_reward,
        resolved_at=resolved_at or datetime.now(UTC),
    )


def signal_types(context) -> set[EvaluationSignalType]:
    return {signal.type for signal in context.deterministic_signals}


def persist_reviewed_adaptation(
    db: Session,
    goal: Goal,
    *,
    cutoff: datetime,
    status: str = "accepted",
    base_revision: PlanRevision | None = None,
) -> PlanRevision:
    if base_revision is None:
        base_revision = PlanRevision(
            goal_id=goal.id,
            revision_number=1,
            snapshot={"stages": []},
            created_at=cutoff - timedelta(minutes=1),
        )
        db.add(base_revision)
        db.commit()
    adaptation = PlanAdaptation(
        goal_id=goal.id,
        base_revision_id=base_revision.id,
        proposal={"decision": "propose_changes", "changes": []},
        status=status,
        reviewed_at=cutoff,
    )
    db.add(adaptation)
    db.commit()
    if status != "accepted":
        return base_revision
    revision = PlanRevision(
        goal_id=goal.id,
        revision_number=base_revision.revision_number + 1,
        snapshot={"stages": []},
        base_revision_id=base_revision.id,
        adaptation_id=adaptation.id,
        created_at=cutoff,
    )
    db.add(revision)
    db.commit()
    return revision


class OvereagerProvider:
    def __init__(self, status: EvaluationStatus) -> None:
        self.status = status
        self.calls = 0

    async def evaluate(self, _context):
        self.calls += 1
        return EvaluationResult(
            status=self.status,
            summary="The provider requests another adaptation.",
            signals=[],
            needs_adaptation=True,
        )

    async def close(self) -> None:
        pass


def test_evaluation_context_builds_minimized_metrics_and_summaries(
    db_session: Session,
    authenticated_user_id: UUID,
) -> None:
    goal = persist_goal(db_session, authenticated_user_id)
    first_time = datetime(2026, 8, 1, 12, tzinfo=UTC)
    last_time = first_time + timedelta(days=2)
    first_mission = add_mission(
        db_session,
        goal,
        [
            resolved_task(
                "Completed difficult Task",
                0,
                difficulty="difficult",
                feedback="JWT setup required debugging.",
                xp_reward=10,
                resolved_at=first_time,
            ),
            resolved_task(
                "Skipped Task",
                1,
                status="skipped",
                difficulty="easy",
                xp_reward=50,
                resolved_at=last_time,
            ),
            Task(title="Pending Task", order_index=2, xp_reward=100),
        ],
    )
    second_stage = Stage(goal_id=goal.id, title="Delivery", order_index=1)
    second_mission = Mission(
        title="Deployment",
        order_index=0,
        estimated_difficulty="difficult",
    )
    second_mission.tasks.append(
        resolved_task(
            "Second completed Task",
            0,
            difficulty="normal",
            feedback="Deployment checks passed.",
            xp_reward=15,
            resolved_at=first_time + timedelta(days=1),
        )
    )
    second_stage.missions.append(second_mission)
    db_session.add(second_stage)
    db_session.commit()

    context = build_evaluation_context(
        db_session, goal.id, authenticated_user_id
    )

    assert context.goal.model_dump() == {
        "title": goal.title,
        "current_situation": goal.current_situation,
        "expected_outcome": goal.expected_outcome,
        "target_timeframe": goal.target_timeframe,
        "availability": goal.availability,
    }
    assert context.metrics.model_dump() == {
        "total_tasks": 4,
        "completed_tasks": 2,
        "skipped_tasks": 1,
        "pending_tasks": 1,
        "resolved_tasks": 3,
        "progress_percentage": 50.0,
        "xp_earned": 25,
    }
    assert context.feedback_metrics.model_dump() == {
        "tasks_with_difficulty_feedback": 3,
        "easy_count": 1,
        "normal_count": 1,
        "difficult_count": 1,
        "tasks_with_feedback_text": 2,
        "tasks_without_explicit_feedback": 0,
    }
    assert context.temporal_metrics.first_resolved_at == first_time
    assert context.temporal_metrics.last_resolved_at == last_time
    assert context.temporal_metrics.resolved_tasks == 3
    assert context.missions[0].model_dump() == {
        "stage_title": "Backend",
        "title": first_mission.title,
        "estimated_difficulty": "normal",
        "total_tasks": 3,
        "completed_tasks": 1,
        "skipped_tasks": 1,
        "pending_tasks": 1,
        "difficult_feedback_count": 1,
    }
    assert len(context.feedback_samples) == 2
    assert context.recent_observed_task_execution_history == []

    serialized = context.model_dump(mode="json")
    serialized_text = str(serialized)
    assert "user_id" not in serialized_text
    assert str(goal.id) not in serialized_text
    assert "Task details must not enter EvaluationContext" not in serialized_text
    assert "Completed difficult Task" not in serialized_text


def test_evaluation_context_includes_only_structured_memory_observations(
    db_session: Session,
    authenticated_user_id: UUID,
) -> None:
    goal = persist_goal(db_session, authenticated_user_id)
    add_mission(
        db_session,
        goal,
        [resolved_task("Completed Task", 0, difficulty="difficult")],
    )
    db_session.add(
        MemoryEntry(
            user_id=authenticated_user_id,
            goal_id=goal.id,
            memory_type="observed",
            key="task_execution",
            value={
                "result": "completed",
                "estimated_difficulty": "normal",
                "difficulty_feedback": "difficult",
                "feedback_text": "Must not enter cognitive context.",
            },
            source_type="task",
            source_id=uuid4(),
            confidence=1,
        )
    )
    db_session.commit()

    context = build_evaluation_context(
        db_session, goal.id, authenticated_user_id
    )

    assert [
        observation.model_dump(mode="json")
        for observation in context.recent_observed_task_execution_history
    ] == [
        {
            "result": "completed",
            "estimated_difficulty": "normal",
            "difficulty_feedback": "difficult",
        }
    ]
    assert "feedback_text" not in str(
        context.recent_observed_task_execution_history
    )


@pytest.mark.parametrize(
    ("statuses", "difficulties", "expected_signal"),
    [
        (
            ["skipped", "skipped", "completed"],
            ["normal", "normal", "normal"],
            EvaluationSignalType.FREQUENT_SKIPS,
        ),
        (
            ["completed", "completed", "completed"],
            ["difficult", "difficult", "difficult"],
            EvaluationSignalType.HIGH_DIFFICULTY,
        ),
        (
            ["completed", "completed", "completed"],
            ["easy", "normal", "normal"],
            EvaluationSignalType.CONSISTENT_PROGRESS,
        ),
    ],
)
def test_evaluation_context_detects_global_deterministic_signals(
    statuses: list[str],
    difficulties: list[str],
    expected_signal: EvaluationSignalType,
    db_session: Session,
    authenticated_user_id: UUID,
) -> None:
    goal = persist_goal(db_session, authenticated_user_id)
    tasks = [
        resolved_task(
            f"Task {index}",
            index,
            status=status,
            difficulty=difficulties[index],
        )
        for index, status in enumerate(statuses)
    ]
    add_mission(db_session, goal, tasks)

    context = build_evaluation_context(
        db_session, goal.id, authenticated_user_id
    )

    assert expected_signal in signal_types(context)


def test_evaluation_context_detects_difficulty_cluster_and_missing_feedback(
    db_session: Session,
    authenticated_user_id: UUID,
) -> None:
    goal = persist_goal(db_session, authenticated_user_id)
    add_mission(
        db_session,
        goal,
        [
            resolved_task("Task 1", 0, difficulty="difficult"),
            resolved_task("Task 2", 1, difficulty="difficult"),
            resolved_task("Task 3", 2),
            resolved_task("Task 4", 3),
        ],
        mission_title="Security",
    )

    context = build_evaluation_context(
        db_session, goal.id, authenticated_user_id
    )

    assert EvaluationSignalType.DIFFICULTY_CLUSTER in signal_types(context)
    assert EvaluationSignalType.INSUFFICIENT_FEEDBACK in signal_types(context)


def test_accepted_adaptation_starts_empty_evidence_window_without_losing_history(
    db_session: Session,
    authenticated_user_id: UUID,
) -> None:
    old_time = datetime(2026, 8, 1, 12, tzinfo=UTC)
    cutoff = old_time + timedelta(days=1)
    goal = persist_goal(db_session, authenticated_user_id)
    add_mission(
        db_session,
        goal,
        [
            resolved_task(
                f"Old difficult Task {index}",
                index,
                difficulty="difficult",
                resolved_at=old_time,
            )
            for index in range(3)
        ]
        + [Task(title="Pending revised Task", order_index=3)],
    )
    db_session.add(
        MemoryEntry(
            user_id=authenticated_user_id,
            goal_id=goal.id,
            memory_type="observed",
            key="task_execution",
            value={
                "result": "completed",
                "estimated_difficulty": "normal",
                "difficulty_feedback": "difficult",
            },
            source_type="task",
            source_id=uuid4(),
            confidence=1,
            created_at=old_time,
        )
    )
    persist_reviewed_adaptation(db_session, goal, cutoff=cutoff)

    context = build_evaluation_context(
        db_session, goal.id, authenticated_user_id
    )

    assert context.metrics.resolved_tasks == 3
    assert context.metrics.xp_earned == 30
    assert context.feedback_metrics.difficult_count == 3
    assert len(context.recent_observed_task_execution_history) == 1
    assert context.adaptation_evidence is not None
    assert context.adaptation_evidence.metrics.resolved_tasks == 0
    assert context.adaptation_evidence.metrics.total_tasks == 1
    assert context.adaptation_evidence.feedback_metrics.difficult_count == 0
    assert context.adaptation_evidence.deterministic_signals == []
    assert (
        context.adaptation_evidence.recent_observed_task_execution_history
        == []
    )

    def fail_if_provider_is_built():
        raise AssertionError("Old evidence must not invoke Evaluation")

    result = asyncio.run(
        EvaluationService(fail_if_provider_is_built).evaluate(context)
    )
    assert result.status is EvaluationStatus.INSUFFICIENT_DATA
    assert result.needs_adaptation is False


def test_one_post_revision_result_is_still_insufficient(
    db_session: Session,
    authenticated_user_id: UUID,
) -> None:
    cutoff = datetime(2026, 8, 5, 12, tzinfo=UTC)
    goal = persist_goal(db_session, authenticated_user_id)
    mission = add_mission(
        db_session,
        goal,
        [
            Task(title="New Task", order_index=0),
            Task(title="Still pending", order_index=1),
        ],
    )
    persist_reviewed_adaptation(db_session, goal, cutoff=cutoff)
    mission.tasks[0].status = PlanningStatus.COMPLETED
    mission.tasks[0].difficulty_feedback = "normal"
    mission.tasks[0].resolved_at = cutoff + timedelta(minutes=1)
    db_session.commit()

    context = build_evaluation_context(
        db_session, goal.id, authenticated_user_id
    )

    assert context.adaptation_evidence is not None
    assert context.adaptation_evidence.metrics.resolved_tasks == 1

    def fail_if_provider_is_built():
        raise AssertionError("One new result must not invoke Evaluation")

    result = asyncio.run(
        EvaluationService(fail_if_provider_is_built).evaluate(context)
    )
    assert result.status is EvaluationStatus.INSUFFICIENT_DATA
    assert result.needs_adaptation is False


def test_normal_post_revision_evidence_overrides_old_problematic_history(
    db_session: Session,
    authenticated_user_id: UUID,
) -> None:
    old_time = datetime(2026, 8, 1, 12, tzinfo=UTC)
    cutoff = old_time + timedelta(days=1)
    goal = persist_goal(db_session, authenticated_user_id)
    mission = add_mission(
        db_session,
        goal,
        [
            resolved_task(
                f"Old difficult Task {index}",
                index,
                difficulty="difficult",
                resolved_at=old_time,
            )
            for index in range(3)
        ]
        + [
            Task(title=f"New normal Task {index}", order_index=index + 3)
            for index in range(3)
        ],
    )
    persist_reviewed_adaptation(db_session, goal, cutoff=cutoff)
    for task in mission.tasks[3:]:
        task.status = PlanningStatus.COMPLETED
        task.difficulty_feedback = "normal"
        task.resolved_at = cutoff + timedelta(minutes=task.order_index)
    db_session.commit()

    context = build_evaluation_context(
        db_session, goal.id, authenticated_user_id
    )
    provider = OvereagerProvider(EvaluationStatus.STRUGGLING)
    result = asyncio.run(
        EvaluationService(lambda: provider).evaluate(context)
    )

    assert context.feedback_metrics.difficult_count == 3
    assert context.adaptation_evidence is not None
    assert context.adaptation_evidence.metrics.resolved_tasks == 3
    assert context.adaptation_evidence.feedback_metrics.normal_count == 3
    assert result.status is EvaluationStatus.ON_TRACK
    assert result.needs_adaptation is False
    assert provider.calls == 1


@pytest.mark.parametrize(
    ("statuses", "difficulties", "expected_signal"),
    [
        (
            ["skipped", "skipped", "completed"],
            ["normal", "normal", "normal"],
            EvaluationSignalType.FREQUENT_SKIPS,
        ),
        (
            ["completed", "completed", "completed"],
            ["difficult", "difficult", "normal"],
            EvaluationSignalType.HIGH_DIFFICULTY,
        ),
    ],
)
def test_problematic_post_revision_evidence_can_enable_adaptation_again(
    statuses: list[str],
    difficulties: list[str],
    expected_signal: EvaluationSignalType,
    db_session: Session,
    authenticated_user_id: UUID,
) -> None:
    cutoff = datetime(2026, 8, 5, 12, tzinfo=UTC)
    goal = persist_goal(db_session, authenticated_user_id)
    mission = add_mission(
        db_session,
        goal,
        [Task(title=f"New Task {index}", order_index=index) for index in range(3)],
    )
    persist_reviewed_adaptation(db_session, goal, cutoff=cutoff)
    for index, task in enumerate(mission.tasks):
        task.status = statuses[index]
        task.difficulty_feedback = difficulties[index]
        task.resolved_at = cutoff + timedelta(minutes=index + 1)
    db_session.commit()

    context = build_evaluation_context(
        db_session, goal.id, authenticated_user_id
    )
    provider = OvereagerProvider(EvaluationStatus.STRUGGLING)
    result = asyncio.run(
        EvaluationService(lambda: provider).evaluate(context)
    )

    assert context.adaptation_evidence is not None
    assert expected_signal in {
        signal.type
        for signal in context.adaptation_evidence.deterministic_signals
    }
    assert result.needs_adaptation is True


def test_rejected_adaptation_does_not_create_cutoff_and_latest_acceptance_wins(
    db_session: Session,
    authenticated_user_id: UUID,
) -> None:
    first_cutoff = datetime(2026, 8, 3, 12, tzinfo=UTC)
    second_cutoff = first_cutoff + timedelta(days=1)
    goal = persist_goal(db_session, authenticated_user_id)
    mission = add_mission(
        db_session,
        goal,
        [
            resolved_task(
                "Before latest revision",
                0,
                difficulty="difficult",
                resolved_at=first_cutoff + timedelta(hours=1),
            ),
            resolved_task(
                "After latest revision",
                1,
                difficulty="normal",
                resolved_at=second_cutoff + timedelta(hours=1),
            ),
        ],
    )
    rejected_goal = persist_goal(db_session, uuid4())
    add_mission(
        db_session,
        rejected_goal,
        [resolved_task("Historical evidence", 0, difficulty="difficult")],
    )
    persist_reviewed_adaptation(
        db_session,
        rejected_goal,
        cutoff=first_cutoff,
        status="rejected",
    )
    rejected_context = build_evaluation_context(
        db_session, rejected_goal.id, rejected_goal.user_id
    )

    first_revision = persist_reviewed_adaptation(
        db_session, goal, cutoff=first_cutoff
    )
    latest_revision = persist_reviewed_adaptation(
        db_session,
        goal,
        cutoff=second_cutoff,
        base_revision=first_revision,
    )
    context = build_evaluation_context(
        db_session, goal.id, authenticated_user_id
    )

    assert rejected_context.adaptation_evidence is None
    assert context.adaptation_evidence is not None
    assert context.adaptation_evidence.cutoff_at == latest_revision.created_at
    assert context.adaptation_evidence.metrics.resolved_tasks == 1
    assert context.adaptation_evidence.feedback_metrics.normal_count == 1
    assert mission.tasks[0].status == PlanningStatus.COMPLETED
