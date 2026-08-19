import logging
from collections.abc import Callable
from typing import Any

from pydantic import BaseModel, ValidationError

from app.ai.evaluation.contracts import (
    EvaluationContext,
    EvaluationFeedbackMetrics,
    EvaluationLLMProvider,
    EvaluationMetrics,
    EvaluationResult,
    EvaluationStatus,
)
from app.ai.evaluation.errors import InvalidEvaluationResultError
from app.services.evaluation_context import (
    has_insufficient_evidence,
    insufficient_data_result,
)

logger = logging.getLogger(__name__)

EvaluationProviderFactory = Callable[[], EvaluationLLMProvider]


class EvaluationService:
    def __init__(self, provider_factory: EvaluationProviderFactory) -> None:
        self._provider_factory = provider_factory

    async def evaluate(self, context: EvaluationContext) -> EvaluationResult:
        logger.info(
            "Goal evaluation started",
            extra={
                "resolved_tasks": context.metrics.resolved_tasks,
                "total_tasks": context.metrics.total_tasks,
            },
        )
        if has_insufficient_evidence(context):
            logger.info(
                "Goal evaluation completed deterministically",
                extra={"llm_invoked": False},
            )
            return insufficient_data_result(context)

        provider = self._provider_factory()
        try:
            provider_result = await provider.evaluate(context)
        finally:
            await provider.close()

        payload: Any = (
            provider_result.model_dump()
            if isinstance(provider_result, BaseModel)
            else provider_result
        )
        try:
            result = EvaluationResult.model_validate(payload)
        except ValidationError as exc:
            raise InvalidEvaluationResultError(
                "Evaluation response does not match EvaluationResult"
            ) from exc

        result = _apply_evidence_guardrails(context, result)

        logger.info(
            "Goal evaluation completed",
            extra={"llm_invoked": True},
        )
        return result


def _apply_evidence_guardrails(
    context: EvaluationContext,
    result: EvaluationResult,
) -> EvaluationResult:
    if _is_normal_execution(context) and (
        result.status is not EvaluationStatus.ON_TRACK
        or result.needs_adaptation
    ):
        return EvaluationResult(
            status=EvaluationStatus.ON_TRACK,
            summary=(
                "La ejecución registrada es consistente y no muestra señales "
                "persistentes que justifiquen cambiar el plan."
            ),
            signals=[],
            needs_adaptation=False,
        )

    if result.status in {
        EvaluationStatus.INSUFFICIENT_DATA,
        EvaluationStatus.ON_TRACK,
    }:
        return result.model_copy(update={"needs_adaptation": False})

    if (
        result.needs_adaptation
        and not _has_persistent_adaptation_evidence(context)
    ):
        return result.model_copy(update={"needs_adaptation": False})

    return result


def _is_normal_execution(context: EvaluationContext) -> bool:
    metrics, feedback = _decision_evidence(context)
    enough_feedback = feedback.tasks_with_difficulty_feedback >= max(
        2, round(metrics.resolved_tasks * 0.5)
    )
    return (
        metrics.resolved_tasks >= 3
        and metrics.completed_tasks == metrics.resolved_tasks
        and metrics.skipped_tasks == 0
        and feedback.difficult_count == 0
        and feedback.easy_count < 3
        and enough_feedback
    )


def _has_persistent_adaptation_evidence(
    context: EvaluationContext,
) -> bool:
    metrics, feedback = _decision_evidence(context)
    if metrics.resolved_tasks < 3:
        return False

    skipped = metrics.skipped_tasks
    difficult = feedback.difficult_count
    easy = feedback.easy_count
    return (
        skipped >= 2
        or difficult >= 2
        or easy >= 3
        or (skipped >= 1 and difficult >= 1)
    )


def _decision_evidence(
    context: EvaluationContext,
) -> tuple[EvaluationMetrics, EvaluationFeedbackMetrics]:
    if context.adaptation_evidence is not None:
        return (
            context.adaptation_evidence.metrics,
            context.adaptation_evidence.feedback_metrics,
        )
    return context.metrics, context.feedback_metrics
