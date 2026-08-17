from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
from sqlalchemy.orm import Session

from app.ai.evaluation.contracts import EvaluationSignalType
from app.models.enums import PlanningStatus
from app.models.goal import Goal
from app.models.mission import Mission
from app.models.stage import Stage
from app.models.task import Task
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

    serialized = context.model_dump(mode="json")
    serialized_text = str(serialized)
    assert "user_id" not in serialized_text
    assert str(goal.id) not in serialized_text
    assert "Task details must not enter EvaluationContext" not in serialized_text
    assert "Completed difficult Task" not in serialized_text


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
