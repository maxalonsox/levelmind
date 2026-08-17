import logging
from collections.abc import Callable
from typing import Any

from pydantic import BaseModel, ValidationError

from app.ai.evaluation.contracts import (
    EvaluationContext,
    EvaluationLLMProvider,
    EvaluationResult,
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

        logger.info(
            "Goal evaluation completed",
            extra={"llm_invoked": True},
        )
        return result
