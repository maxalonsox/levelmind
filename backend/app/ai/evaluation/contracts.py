from datetime import datetime
from enum import StrEnum
from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import Difficulty, PlanningStatus, TaskResult


class EvaluationStatus(StrEnum):
    INSUFFICIENT_DATA = "insufficient_data"
    ON_TRACK = "on_track"
    STRUGGLING = "struggling"
    PROGRESSING_FAST = "progressing_fast"
    MIXED = "mixed"


class EvaluationSignalType(StrEnum):
    INSUFFICIENT_DATA = "insufficient_data"
    HIGH_DIFFICULTY = "high_difficulty"
    FREQUENT_SKIPS = "frequent_skips"
    FAST_PROGRESS = "fast_progress"
    LOW_PROGRESS = "low_progress"
    CONSISTENT_PROGRESS = "consistent_progress"
    INSUFFICIENT_FEEDBACK = "insufficient_feedback"
    DIFFICULTY_CLUSTER = "difficulty_cluster"


class EvaluationSeverity(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class EvaluationSignal(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    type: EvaluationSignalType
    description: str = Field(min_length=1, max_length=500)
    severity: EvaluationSeverity


class EvaluationResult(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    status: EvaluationStatus
    summary: str = Field(min_length=1, max_length=1000)
    signals: list[EvaluationSignal] = Field(default_factory=list, max_length=10)
    needs_adaptation: bool


class EvaluationGoalContext(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str
    current_situation: str
    expected_outcome: str
    target_timeframe: str | None
    availability: str | None


class EvaluationMetrics(BaseModel):
    model_config = ConfigDict(extra="forbid")

    total_tasks: int = Field(ge=0)
    completed_tasks: int = Field(ge=0)
    skipped_tasks: int = Field(ge=0)
    pending_tasks: int = Field(ge=0)
    resolved_tasks: int = Field(ge=0)
    progress_percentage: float = Field(ge=0, le=100)
    xp_earned: int = Field(ge=0)


class EvaluationFeedbackMetrics(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tasks_with_difficulty_feedback: int = Field(ge=0)
    easy_count: int = Field(ge=0)
    normal_count: int = Field(ge=0)
    difficult_count: int = Field(ge=0)
    tasks_with_feedback_text: int = Field(ge=0)
    tasks_without_explicit_feedback: int = Field(ge=0)


class EvaluationTemporalMetrics(BaseModel):
    model_config = ConfigDict(extra="forbid")

    resolved_tasks: int = Field(ge=0)
    first_resolved_at: datetime | None
    last_resolved_at: datetime | None


class EvaluationMissionSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    stage_title: str
    title: str
    estimated_difficulty: Difficulty | None
    total_tasks: int = Field(ge=0)
    completed_tasks: int = Field(ge=0)
    skipped_tasks: int = Field(ge=0)
    pending_tasks: int = Field(ge=0)
    difficult_feedback_count: int = Field(ge=0)


class EvaluationFeedbackSample(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mission_title: str
    result: PlanningStatus
    difficulty_feedback: Difficulty | None
    feedback_text: str = Field(min_length=1, max_length=2000)


class RecentTaskExecutionObservation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    result: TaskResult
    estimated_difficulty: Difficulty | None
    difficulty_feedback: Difficulty | None


class EvaluationEvidenceWindow(BaseModel):
    model_config = ConfigDict(extra="forbid")

    cutoff_at: datetime
    metrics: EvaluationMetrics
    feedback_metrics: EvaluationFeedbackMetrics
    temporal_metrics: EvaluationTemporalMetrics
    missions: list[EvaluationMissionSummary]
    feedback_samples: list[EvaluationFeedbackSample] = Field(max_length=10)
    deterministic_signals: list[EvaluationSignal]
    recent_observed_task_execution_history: list[
        RecentTaskExecutionObservation
    ] = Field(default_factory=list, max_length=10)


class EvaluationContext(BaseModel):
    model_config = ConfigDict(extra="forbid")

    goal: EvaluationGoalContext
    metrics: EvaluationMetrics
    feedback_metrics: EvaluationFeedbackMetrics
    temporal_metrics: EvaluationTemporalMetrics
    missions: list[EvaluationMissionSummary]
    feedback_samples: list[EvaluationFeedbackSample] = Field(max_length=10)
    deterministic_signals: list[EvaluationSignal]
    recent_observed_task_execution_history: list[
        RecentTaskExecutionObservation
    ] = Field(default_factory=list, max_length=10)
    adaptation_evidence: EvaluationEvidenceWindow | None = None


class EvaluationLLMProvider(Protocol):
    async def evaluate(self, context: EvaluationContext) -> EvaluationResult:
        """Evaluate a minimized execution context without mutating state."""
        ...

    async def close(self) -> None:
        """Release provider resources."""
        ...
