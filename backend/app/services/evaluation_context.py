from uuid import UUID

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.ai.evaluation.contracts import (
    EvaluationContext,
    EvaluationFeedbackMetrics,
    EvaluationFeedbackSample,
    EvaluationGoalContext,
    EvaluationMetrics,
    EvaluationMissionSummary,
    RecentTaskExecutionObservation,
    EvaluationResult,
    EvaluationSeverity,
    EvaluationSignal,
    EvaluationSignalType,
    EvaluationStatus,
    EvaluationTemporalMetrics,
)
from app.models.enums import Difficulty, PlanningStatus
from app.models.mission import Mission
from app.models.stage import Stage
from app.models.task import Task
from app.services.goal import get_owned_goal
from app.services.memory_entry import list_recent_task_execution_memories


def build_evaluation_context(
    db: Session, goal_id: UUID, user_id: UUID
) -> EvaluationContext:
    goal = get_owned_goal(db, goal_id, user_id)
    stages = list(
        db.scalars(
            select(Stage)
            .where(Stage.goal_id == goal_id)
            .options(
                selectinload(Stage.missions).selectinload(Mission.tasks)
            )
            .order_by(Stage.order_index.asc())
        )
    )

    tasks: list[Task] = []
    mission_summaries: list[EvaluationMissionSummary] = []
    feedback_samples: list[EvaluationFeedbackSample] = []

    for stage in stages:
        for mission in sorted(
            stage.missions, key=lambda item: item.order_index
        ):
            mission_tasks = sorted(
                mission.tasks, key=lambda item: item.order_index
            )
            tasks.extend(mission_tasks)
            mission_summaries.append(
                _mission_summary(stage.title, mission, mission_tasks)
            )
            for task in mission_tasks:
                if (
                    len(feedback_samples) < 10
                    and _is_terminal(task)
                    and task.feedback_text
                    and task.feedback_text.strip()
                ):
                    feedback_samples.append(
                        EvaluationFeedbackSample(
                            mission_title=mission.title,
                            result=PlanningStatus(task.status),
                            difficulty_feedback=task.difficulty_feedback,
                            feedback_text=task.feedback_text,
                        )
                    )

    terminal_tasks = [task for task in tasks if _is_terminal(task)]
    completed_tasks = sum(
        PlanningStatus(task.status) is PlanningStatus.COMPLETED
        for task in tasks
    )
    skipped_tasks = sum(
        PlanningStatus(task.status) is PlanningStatus.SKIPPED
        for task in tasks
    )
    total_tasks = len(tasks)
    resolved_tasks = len(terminal_tasks)
    pending_tasks = total_tasks - resolved_tasks
    difficulty_values = [
        Difficulty(task.difficulty_feedback)
        for task in terminal_tasks
        if task.difficulty_feedback is not None
    ]
    feedback_text_count = sum(
        bool(task.feedback_text and task.feedback_text.strip())
        for task in terminal_tasks
    )
    no_explicit_feedback_count = sum(
        task.difficulty_feedback is None
        and not (task.feedback_text and task.feedback_text.strip())
        for task in terminal_tasks
    )
    resolved_timestamps = [
        task.resolved_at
        for task in terminal_tasks
        if task.resolved_at is not None
    ]

    metrics = EvaluationMetrics(
        total_tasks=total_tasks,
        completed_tasks=completed_tasks,
        skipped_tasks=skipped_tasks,
        pending_tasks=pending_tasks,
        resolved_tasks=resolved_tasks,
        progress_percentage=(
            round(completed_tasks / total_tasks * 100, 2)
            if total_tasks
            else 0.0
        ),
        xp_earned=sum(
            task.xp_reward
            for task in tasks
            if PlanningStatus(task.status) is PlanningStatus.COMPLETED
        ),
    )
    feedback_metrics = EvaluationFeedbackMetrics(
        tasks_with_difficulty_feedback=len(difficulty_values),
        easy_count=difficulty_values.count(Difficulty.EASY),
        normal_count=difficulty_values.count(Difficulty.NORMAL),
        difficult_count=difficulty_values.count(Difficulty.DIFFICULT),
        tasks_with_feedback_text=feedback_text_count,
        tasks_without_explicit_feedback=no_explicit_feedback_count,
    )
    temporal_metrics = EvaluationTemporalMetrics(
        resolved_tasks=resolved_tasks,
        first_resolved_at=(
            min(resolved_timestamps) if resolved_timestamps else None
        ),
        last_resolved_at=(
            max(resolved_timestamps) if resolved_timestamps else None
        ),
    )

    return EvaluationContext(
        goal=EvaluationGoalContext(
            title=goal.title,
            current_situation=goal.current_situation,
            expected_outcome=goal.expected_outcome,
            target_timeframe=goal.target_timeframe,
            availability=goal.availability,
        ),
        metrics=metrics,
        feedback_metrics=feedback_metrics,
        temporal_metrics=temporal_metrics,
        missions=mission_summaries,
        feedback_samples=feedback_samples,
        deterministic_signals=_deterministic_signals(
            metrics, feedback_metrics, mission_summaries
        ),
        recent_observed_task_execution_history=(
            _recent_task_execution_history(db, user_id, goal_id)
        ),
    )


def _recent_task_execution_history(
    db: Session,
    user_id: UUID,
    goal_id: UUID,
) -> list[RecentTaskExecutionObservation]:
    observations: list[RecentTaskExecutionObservation] = []
    for memory in list_recent_task_execution_memories(
        db, user_id, goal_id
    ):
        try:
            observations.append(
                RecentTaskExecutionObservation.model_validate(
                    {
                        "result": memory.value.get("result"),
                        "estimated_difficulty": memory.value.get(
                            "estimated_difficulty"
                        ),
                        "difficulty_feedback": memory.value.get(
                            "difficulty_feedback"
                        ),
                    }
                )
            )
        except (AttributeError, ValidationError):
            continue
    return observations


def has_insufficient_evidence(context: EvaluationContext) -> bool:
    resolved = context.metrics.resolved_tasks
    total = context.metrics.total_tasks
    observed_percentage = resolved / total * 100 if total else 0.0
    return resolved < 2 or (resolved < 3 and observed_percentage < 20)


def insufficient_data_result(context: EvaluationContext) -> EvaluationResult:
    resolved = context.metrics.resolved_tasks
    total = context.metrics.total_tasks

    return EvaluationResult(
        status=EvaluationStatus.INSUFFICIENT_DATA,
        summary=(
            f"Only {resolved} of {total} Tasks have terminal results, which is "
            "not enough evidence to evaluate the plan responsibly yet."
        ),
        signals=[
            EvaluationSignal(
                type=EvaluationSignalType.INSUFFICIENT_DATA,
                description=(
                    f"{resolved} of {total} Tasks are resolved; this is below "
                    "the minimum absolute or proportional evidence threshold."
                ),
                severity=EvaluationSeverity.LOW,
            )
        ],
        needs_adaptation=False,
    )


def _mission_summary(
    stage_title: str,
    mission: Mission,
    tasks: list[Task],
) -> EvaluationMissionSummary:
    completed = sum(
        PlanningStatus(task.status) is PlanningStatus.COMPLETED
        for task in tasks
    )
    skipped = sum(
        PlanningStatus(task.status) is PlanningStatus.SKIPPED
        for task in tasks
    )
    difficult = sum(
        task.difficulty_feedback == Difficulty.DIFFICULT
        for task in tasks
        if _is_terminal(task)
    )
    return EvaluationMissionSummary(
        stage_title=stage_title,
        title=mission.title,
        estimated_difficulty=mission.estimated_difficulty,
        total_tasks=len(tasks),
        completed_tasks=completed,
        skipped_tasks=skipped,
        pending_tasks=len(tasks) - completed - skipped,
        difficult_feedback_count=difficult,
    )


def _deterministic_signals(
    metrics: EvaluationMetrics,
    feedback: EvaluationFeedbackMetrics,
    missions: list[EvaluationMissionSummary],
) -> list[EvaluationSignal]:
    signals: list[EvaluationSignal] = []
    resolved = metrics.resolved_tasks

    if resolved >= 3:
        skip_ratio = metrics.skipped_tasks / resolved
        if skip_ratio >= 0.4:
            signals.append(
                EvaluationSignal(
                    type=EvaluationSignalType.FREQUENT_SKIPS,
                    description=(
                        f"{metrics.skipped_tasks} of {resolved} resolved Tasks "
                        "were skipped."
                    ),
                    severity=(
                        EvaluationSeverity.HIGH
                        if skip_ratio >= 0.6
                        else EvaluationSeverity.MEDIUM
                    ),
                )
            )

    difficulty_total = feedback.tasks_with_difficulty_feedback
    if difficulty_total >= 3:
        difficult_ratio = feedback.difficult_count / difficulty_total
        if difficult_ratio >= 0.5:
            signals.append(
                EvaluationSignal(
                    type=EvaluationSignalType.HIGH_DIFFICULTY,
                    description=(
                        f"{feedback.difficult_count} of {difficulty_total} "
                        "Tasks with difficulty feedback were marked difficult."
                    ),
                    severity=(
                        EvaluationSeverity.HIGH
                        if difficult_ratio >= 0.7
                        else EvaluationSeverity.MEDIUM
                    ),
                )
            )

    for mission in missions:
        mission_resolved = (
            mission.completed_tasks + mission.skipped_tasks
        )
        if (
            mission_resolved >= 2
            and mission.difficult_feedback_count >= 2
            and mission.difficult_feedback_count / mission_resolved >= 0.5
        ):
            signals.append(
                EvaluationSignal(
                    type=EvaluationSignalType.DIFFICULTY_CLUSTER,
                    description=(
                        f"Mission '{mission.title}' contains "
                        f"{mission.difficult_feedback_count} difficult ratings "
                        f"among {mission_resolved} resolved Tasks."
                    ),
                    severity=(
                        EvaluationSeverity.HIGH
                        if mission.difficult_feedback_count >= 3
                        else EvaluationSeverity.MEDIUM
                    ),
                )
            )

    if resolved >= 3:
        missing_ratio = feedback.tasks_without_explicit_feedback / resolved
        if missing_ratio >= 0.5:
            signals.append(
                EvaluationSignal(
                    type=EvaluationSignalType.INSUFFICIENT_FEEDBACK,
                    description=(
                        f"{feedback.tasks_without_explicit_feedback} of "
                        f"{resolved} resolved Tasks have no explicit feedback."
                    ),
                    severity=EvaluationSeverity.LOW,
                )
            )

        enough_difficulty_feedback = difficulty_total >= max(
            2, round(resolved * 0.5)
        )
        mostly_not_difficult = (
            difficulty_total > 0
            and feedback.difficult_count / difficulty_total <= 0.25
        )
        if (
            metrics.skipped_tasks == 0
            and metrics.completed_tasks == resolved
            and enough_difficulty_feedback
            and mostly_not_difficult
        ):
            signals.append(
                EvaluationSignal(
                    type=EvaluationSignalType.CONSISTENT_PROGRESS,
                    description=(
                        f"All {resolved} resolved Tasks were completed with no "
                        "skips and difficulty was mostly easy or normal."
                    ),
                    severity=EvaluationSeverity.LOW,
                )
            )

    return signals[:10]


def _is_terminal(task: Task) -> bool:
    return PlanningStatus(task.status) in {
        PlanningStatus.COMPLETED,
        PlanningStatus.SKIPPED,
    }
