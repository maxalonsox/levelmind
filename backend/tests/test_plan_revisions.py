from pathlib import Path
from uuid import uuid4

from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.base import Base
from app.models.goal import Goal
from app.models.mission import Mission
from app.models.plan_revision import PlanRevision
from app.models.stage import Stage
from app.models.task import Task
from app.services.plan_revision import ensure_current_plan_revision


def test_existing_plan_gets_one_lazy_current_revision(
    db_session: Session,
) -> None:
    user_id = uuid4()
    goal = Goal(
        user_id=user_id,
        title="Existing goal",
        current_situation="Existing plan without revisions",
        expected_outcome="Keep compatibility",
    )
    stage = Stage(goal=goal, title="Stage", order_index=0)
    mission = Mission(stage=stage, title="Mission", order_index=0)
    mission.tasks.append(
        Task(
            title="Existing Task",
            order_index=0,
            estimated_duration_minutes=30,
            estimated_difficulty="normal",
            difficulty_feedback="difficult",
            feedback_text="Historical feedback must not enter snapshots.",
        )
    )
    db_session.add(goal)
    db_session.commit()

    first = ensure_current_plan_revision(db_session, goal.id, user_id)
    second = ensure_current_plan_revision(db_session, goal.id, user_id)

    assert first.id == second.id
    assert first.revision_number == 1
    assert list(db_session.scalars(select(PlanRevision))) == [first]
    task_snapshot = first.snapshot["stages"][0]["missions"][0]["tasks"][0]
    assert task_snapshot["estimated_difficulty"] == "normal"
    assert "difficulty_feedback" not in task_snapshot
    assert "feedback_text" not in task_snapshot
    assert "resolved_at" not in task_snapshot


def test_revision_metadata_has_one_alembic_head() -> None:
    backend_dir = Path(__file__).resolve().parents[1]
    config = Config(str(backend_dir / "alembic.ini"))
    config.set_main_option("path_separator", "os")
    script = ScriptDirectory.from_config(config)

    assert script.get_heads() == ["b8f1c2d3e4a5"]
    assert "plan_revisions" in Base.metadata.tables
    assert "estimated_difficulty" in Base.metadata.tables["tasks"].columns
    assert (
        "base_revision_id"
        in Base.metadata.tables["plan_adaptations"].columns
    )
