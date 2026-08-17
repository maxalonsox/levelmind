from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.ai.adaptation.contracts import (
    AdaptationContext,
    AdaptationMissionOutline,
    AdaptationStageOutline,
    AdaptationTaskOutline,
    RelevantAdaptationTask,
)
from app.ai.evaluation.contracts import (
    EvaluationContext,
    EvaluationResult,
    EvaluationSignalType,
    EvaluationStatus,
)
from app.models.enums import Difficulty, PlanningStatus
from app.models.mission import Mission
from app.models.stage import Stage
from app.models.task import Task
from app.services.goal import get_owned_goal

MAX_RELEVANT_TASKS = 12
MAX_FEEDBACK_CHARACTERS = 500


@dataclass(frozen=True)
class _TaskLocation:
    stage: Stage
    mission: Mission
    task: Task


def build_adaptation_context(
    db: Session,
    goal_id: UUID,
    user_id: UUID,
    evaluation_context: EvaluationContext,
    evaluation: EvaluationResult,
) -> AdaptationContext:
    get_owned_goal(db, goal_id, user_id)
    stages = _load_plan(db, goal_id)
    locations = _task_locations(stages)

    return AdaptationContext(
        goal=evaluation_context.goal,
        evaluation=evaluation,
        plan_outline=[_stage_outline(stage) for stage in stages],
        relevant_tasks=[
            _relevant_task(location)
            for location in _select_relevant_tasks(
                locations, evaluation_context, evaluation
            )
        ],
    )


def _load_plan(db: Session, goal_id: UUID) -> list[Stage]:
    return list(
        db.scalars(
            select(Stage)
            .where(Stage.goal_id == goal_id)
            .options(
                selectinload(Stage.missions).selectinload(Mission.tasks)
            )
            .order_by(Stage.order_index.asc())
        )
    )


def _task_locations(stages: list[Stage]) -> list[_TaskLocation]:
    return [
        _TaskLocation(stage=stage, mission=mission, task=task)
        for stage in stages
        for mission in sorted(stage.missions, key=lambda item: item.order_index)
        for task in sorted(mission.tasks, key=lambda item: item.order_index)
    ]


def _stage_outline(stage: Stage) -> AdaptationStageOutline:
    return AdaptationStageOutline(
        order_index=stage.order_index,
        title=stage.title,
        missions=[
            AdaptationMissionOutline(
                order_index=mission.order_index,
                title=mission.title,
                tasks=[
                    AdaptationTaskOutline(
                        order_index=task.order_index,
                        title=task.title,
                        status=PlanningStatus(task.status),
                    )
                    for task in sorted(
                        mission.tasks, key=lambda item: item.order_index
                    )
                ],
            )
            for mission in sorted(
                stage.missions, key=lambda item: item.order_index
            )
        ],
    )


def _select_relevant_tasks(
    locations: list[_TaskLocation],
    evaluation_context: EvaluationContext,
    evaluation: EvaluationResult,
) -> list[_TaskLocation]:
    signal_types = {
        signal.type
        for signal in (
            evaluation_context.deterministic_signals + evaluation.signals
        )
    }
    difficult_missions = {
        (mission.stage_title, mission.title)
        for mission in evaluation_context.missions
        if mission.difficult_feedback_count >= 2
    }
    skipped_mission_ids = {
        location.mission.id
        for location in locations
        if PlanningStatus(location.task.status) is PlanningStatus.SKIPPED
    }

    def relevance(location: _TaskLocation) -> int:
        task = location.task
        status = PlanningStatus(task.status)
        score = 0
        mission_key = (location.stage.title, location.mission.title)

        if EvaluationSignalType.DIFFICULTY_CLUSTER in signal_types:
            if mission_key in difficult_missions:
                score = max(score, 80)
                if task.difficulty_feedback == Difficulty.DIFFICULT:
                    score = 110
        if EvaluationSignalType.HIGH_DIFFICULTY in signal_types:
            if task.difficulty_feedback == Difficulty.DIFFICULT:
                score = max(score, 105)
        if EvaluationSignalType.FREQUENT_SKIPS in signal_types:
            if status is PlanningStatus.SKIPPED:
                score = max(score, 110)
            elif location.mission.id in skipped_mission_ids:
                score = max(score, 70)
        if (
            evaluation.status is EvaluationStatus.PROGRESSING_FAST
            or EvaluationSignalType.FAST_PROGRESS in signal_types
        ):
            if status is PlanningStatus.PENDING:
                score = max(score, 85)
            elif task.difficulty_feedback == Difficulty.EASY:
                score = max(score, 75)
        if any(
            signal_type in signal_types
            for signal_type in {
                EvaluationSignalType.LOW_PROGRESS,
                EvaluationSignalType.INSUFFICIENT_FEEDBACK,
            }
        ):
            if status is PlanningStatus.PENDING:
                score = max(score, 65)
        if score == 0:
            score = 40 if status is PlanningStatus.PENDING else 20
        return score

    ranked = sorted(
        locations,
        key=lambda location: (
            -relevance(location),
            location.stage.order_index,
            location.mission.order_index,
            location.task.order_index,
        ),
    )
    return ranked[:MAX_RELEVANT_TASKS]


def _relevant_task(location: _TaskLocation) -> RelevantAdaptationTask:
    task = location.task
    feedback = task.feedback_text.strip() if task.feedback_text else None
    if feedback:
        feedback = feedback[:MAX_FEEDBACK_CHARACTERS]
    return RelevantAdaptationTask(
        stage_order_index=location.stage.order_index,
        stage_title=location.stage.title,
        mission_order_index=location.mission.order_index,
        mission_title=location.mission.title,
        task_order_index=task.order_index,
        task_title=task.title,
        status=PlanningStatus(task.status),
        estimated_duration_minutes=task.estimated_duration_minutes,
        xp_reward=task.xp_reward,
        difficulty_feedback=task.difficulty_feedback,
        feedback_text=feedback,
    )
