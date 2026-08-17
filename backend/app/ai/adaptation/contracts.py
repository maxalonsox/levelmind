from enum import StrEnum
from typing import Annotated, Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.ai.evaluation.contracts import (
    EvaluationGoalContext,
    EvaluationResult,
)
from app.models.enums import Difficulty, PlanningStatus


class AdaptationDecision(StrEnum):
    NO_CHANGE = "no_change"
    PROPOSE_CHANGES = "propose_changes"


class AdaptationChangeType(StrEnum):
    ADD_TASK = "add_task"
    SPLIT_TASK = "split_task"
    REPLACE_TASK = "replace_task"
    REORDER_TASK = "reorder_task"
    ADJUST_TASK_DIFFICULTY = "adjust_task_difficulty"
    ADJUST_TASK_DURATION = "adjust_task_duration"


class _AdaptationModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class ProposedTask(_AdaptationModel):
    title: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    estimated_duration_minutes: int = Field(gt=0)
    xp_reward: int = Field(gt=0)


class AdaptationMissionTarget(_AdaptationModel):
    stage_order_index: int = Field(ge=0)
    stage_title: str = Field(min_length=1, max_length=200)
    mission_order_index: int = Field(ge=0)
    mission_title: str = Field(min_length=1, max_length=200)


class AdaptationTaskTarget(AdaptationMissionTarget):
    task_order_index: int = Field(ge=0)
    task_title: str = Field(min_length=1, max_length=200)


class AddTaskChange(_AdaptationModel):
    type: Literal[AdaptationChangeType.ADD_TASK]
    target: AdaptationMissionTarget
    reason: str = Field(min_length=1, max_length=500)
    insert_after_task_order_index: int | None = Field(default=None, ge=0)
    task: ProposedTask


class SplitTaskChange(_AdaptationModel):
    type: Literal[AdaptationChangeType.SPLIT_TASK]
    target: AdaptationTaskTarget
    reason: str = Field(min_length=1, max_length=500)
    replacement_tasks: list[ProposedTask] = Field(min_length=2, max_length=6)


class ReplaceTaskChange(_AdaptationModel):
    type: Literal[AdaptationChangeType.REPLACE_TASK]
    target: AdaptationTaskTarget
    reason: str = Field(min_length=1, max_length=500)
    replacement: ProposedTask


class ReorderTaskChange(_AdaptationModel):
    type: Literal[AdaptationChangeType.REORDER_TASK]
    target: AdaptationTaskTarget
    reason: str = Field(min_length=1, max_length=500)
    destination_order_index: int = Field(ge=0)


class AdjustTaskDifficultyChange(_AdaptationModel):
    type: Literal[AdaptationChangeType.ADJUST_TASK_DIFFICULTY]
    target: AdaptationTaskTarget
    reason: str = Field(min_length=1, max_length=500)
    proposed_difficulty: Difficulty


class AdjustTaskDurationChange(_AdaptationModel):
    type: Literal[AdaptationChangeType.ADJUST_TASK_DURATION]
    target: AdaptationTaskTarget
    reason: str = Field(min_length=1, max_length=500)
    estimated_duration_minutes: int = Field(gt=0)


AdaptationChange = Annotated[
    AddTaskChange
    | SplitTaskChange
    | ReplaceTaskChange
    | ReorderTaskChange
    | AdjustTaskDifficultyChange
    | AdjustTaskDurationChange,
    Field(discriminator="type"),
]


class AdaptationProposal(_AdaptationModel):
    decision: AdaptationDecision
    summary: str = Field(min_length=1, max_length=1000)
    rationale: str = Field(min_length=1, max_length=1500)
    changes: list[AdaptationChange] = Field(default_factory=list, max_length=10)

    @model_validator(mode="after")
    def validate_decision_matches_changes(self) -> "AdaptationProposal":
        if self.decision is AdaptationDecision.NO_CHANGE and self.changes:
            raise ValueError("no_change requires an empty changes list")
        if (
            self.decision is AdaptationDecision.PROPOSE_CHANGES
            and not self.changes
        ):
            raise ValueError("propose_changes requires at least one change")
        return self


class AdaptationTaskOutline(_AdaptationModel):
    order_index: int = Field(ge=0)
    title: str = Field(min_length=1, max_length=200)
    status: PlanningStatus


class AdaptationMissionOutline(_AdaptationModel):
    order_index: int = Field(ge=0)
    title: str = Field(min_length=1, max_length=200)
    tasks: list[AdaptationTaskOutline]


class AdaptationStageOutline(_AdaptationModel):
    order_index: int = Field(ge=0)
    title: str = Field(min_length=1, max_length=200)
    missions: list[AdaptationMissionOutline]


class RelevantAdaptationTask(_AdaptationModel):
    stage_order_index: int = Field(ge=0)
    stage_title: str = Field(min_length=1, max_length=200)
    mission_order_index: int = Field(ge=0)
    mission_title: str = Field(min_length=1, max_length=200)
    task_order_index: int = Field(ge=0)
    task_title: str = Field(min_length=1, max_length=200)
    status: PlanningStatus
    estimated_duration_minutes: int | None = Field(default=None, gt=0)
    xp_reward: int = Field(ge=0)
    difficulty_feedback: Difficulty | None = None
    feedback_text: str | None = Field(default=None, min_length=1, max_length=500)


class AdaptationContext(_AdaptationModel):
    goal: EvaluationGoalContext
    evaluation: EvaluationResult
    plan_outline: list[AdaptationStageOutline]
    relevant_tasks: list[RelevantAdaptationTask] = Field(max_length=12)


class AdaptationLLMProvider(Protocol):
    async def propose(
        self, context: AdaptationContext
    ) -> AdaptationProposal:
        """Propose bounded plan changes without mutating state."""
        ...

    async def close(self) -> None:
        """Release provider resources."""
        ...
