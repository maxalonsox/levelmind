from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.orm import Session

from app.ai.evaluation.contracts import EvaluationResult
from app.models.goal import Goal
from app.models.mission import Mission
from app.models.stage import Stage
from app.models.task import Task
from app.services.adaptation_context import build_adaptation_context
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


def persist_plan(db: Session, goal: Goal) -> None:
    first_stage = Stage(
        goal_id=goal.id,
        title="Backend fundamentals",
        description="Stage description must not enter adaptation context.",
        order_index=1,
    )
    difficult_mission = Mission(
        title="Security",
        description="Mission description must stay private.",
        order_index=1,
        estimated_difficulty="normal",
    )
    difficult_mission.tasks = [
        Task(
            title="Implement JWT filter",
            description="Task description must not enter context.",
            order_index=1,
            status="completed",
            difficulty_feedback="difficult",
            feedback_text="x" * 800,
            resolved_at=datetime.now(UTC),
            estimated_duration_minutes=60,
            xp_reward=15,
        ),
        Task(
            title="Test JWT filter",
            order_index=0,
            status="skipped",
            difficulty_feedback="difficult",
            feedback_text="The setup was too broad.",
            resolved_at=datetime.now(UTC),
            estimated_duration_minutes=45,
            xp_reward=10,
        ),
        Task(
            title="Document security flow",
            order_index=2,
            estimated_duration_minutes=30,
            xp_reward=10,
        ),
    ]
    first_stage.missions.append(difficult_mission)

    earlier_stage = Stage(
        goal_id=goal.id,
        title="API foundations",
        order_index=0,
    )
    mission = Mission(title="REST", order_index=0)
    mission.tasks = [
        Task(title="Define contract", order_index=1, xp_reward=10),
        Task(title="Create endpoint", order_index=0, xp_reward=10),
    ]
    earlier_stage.missions.append(mission)
    db.add_all([first_stage, earlier_stage])
    db.commit()


def adaptation_evaluation() -> EvaluationResult:
    return EvaluationResult(
        status="struggling",
        summary="Difficulty is concentrated in one Mission.",
        signals=[
            {
                "type": "difficulty_cluster",
                "description": "Two Security Tasks were marked difficult.",
                "severity": "high",
            },
            {
                "type": "frequent_skips",
                "description": "Skipped Tasks require review.",
                "severity": "medium",
            },
        ],
        needs_adaptation=True,
    )


def test_adaptation_context_is_ordered_minimized_and_uuid_free(
    db_session: Session,
    authenticated_user_id: UUID,
) -> None:
    goal = persist_goal(db_session, authenticated_user_id)
    persist_plan(db_session, goal)
    evaluation_context = build_evaluation_context(
        db_session, goal.id, authenticated_user_id
    )

    context = build_adaptation_context(
        db_session,
        goal.id,
        authenticated_user_id,
        evaluation_context,
        adaptation_evaluation(),
    )

    assert [stage.order_index for stage in context.plan_outline] == [0, 1]
    assert [
        task.order_index
        for task in context.plan_outline[0].missions[0].tasks
    ] == [0, 1]
    assert context.relevant_tasks[0].task_title in {
        "Implement JWT filter",
        "Test JWT filter",
    }
    long_feedback = next(
        task.feedback_text
        for task in context.relevant_tasks
        if task.task_title == "Implement JWT filter"
    )
    assert long_feedback is not None
    assert len(long_feedback) == 500

    serialized = str(context.model_dump(mode="json"))
    assert str(goal.id) not in serialized
    assert str(goal.user_id) not in serialized
    assert "user_id" not in serialized
    assert "created_at" not in serialized
    assert "updated_at" not in serialized
    assert "Stage description must not enter" not in serialized
    assert "Mission description must stay private" not in serialized
    assert "Task description must not enter" not in serialized


def test_adaptation_context_limits_feedback_detail_to_relevant_tasks(
    db_session: Session,
    authenticated_user_id: UUID,
) -> None:
    goal = persist_goal(db_session, authenticated_user_id)
    stage = Stage(goal_id=goal.id, title="Backend", order_index=0)
    mission = Mission(title="Practice", order_index=0)
    mission.tasks = [
        Task(
            title=f"Task {index}",
            order_index=index,
            status="skipped",
            feedback_text=f"Feedback sample {index}",
            resolved_at=datetime.now(UTC),
            xp_reward=10,
        )
        for index in range(20)
    ]
    stage.missions.append(mission)
    db_session.add(stage)
    db_session.commit()
    evaluation_context = build_evaluation_context(
        db_session, goal.id, authenticated_user_id
    )
    evaluation = EvaluationResult(
        status="struggling",
        summary="Skips are repeated.",
        signals=[
            {
                "type": "frequent_skips",
                "description": "Twenty Tasks were skipped.",
                "severity": "high",
            }
        ],
        needs_adaptation=True,
    )

    context = build_adaptation_context(
        db_session,
        goal.id,
        authenticated_user_id,
        evaluation_context,
        evaluation,
    )

    assert len(context.relevant_tasks) == 12
    assert all(task.feedback_text for task in context.relevant_tasks)
