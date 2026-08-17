from openai import AsyncOpenAI

from app.ai.evaluation.contracts import (
    EvaluationContext,
    EvaluationResult,
)
from app.ai.evaluation.errors import (
    EmptyEvaluationResponseError,
    EvaluationProviderAPIError,
    EvaluationProviderTimeoutError,
    InvalidEvaluationJSONError,
    InvalidEvaluationResultError,
)
from app.ai.evaluation.prompts import build_evaluation_prompt
from app.ai.openai_compatible import (
    OpenAICompatibleStructuredClient,
    StructuredProviderErrors,
)
from app.core.config import Settings


class OpenAICompatibleEvaluationProvider:
    def __init__(
        self,
        settings: Settings,
        *,
        client: AsyncOpenAI | None = None,
        max_attempts: int = 3,
        retry_delay_seconds: float = 0.25,
    ) -> None:
        self._structured_client = OpenAICompatibleStructuredClient(
            settings,
            output_model=EvaluationResult,
            operation="Evaluation",
            contract_name="EvaluationResult",
            errors=StructuredProviderErrors(
                timeout=EvaluationProviderTimeoutError,
                api=EvaluationProviderAPIError,
                empty=EmptyEvaluationResponseError,
                invalid_json=InvalidEvaluationJSONError,
                invalid_output=InvalidEvaluationResultError,
            ),
            client=client,
            max_attempts=max_attempts,
            retry_delay_seconds=retry_delay_seconds,
        )

    async def evaluate(self, context: EvaluationContext) -> EvaluationResult:
        prompt = build_evaluation_prompt(context)
        return await self._structured_client.generate(
            [
                {"role": "system", "content": prompt.system},
                {"role": "user", "content": prompt.user},
            ]
        )

    async def close(self) -> None:
        await self._structured_client.close()
