from openai import AsyncOpenAI

from app.ai.adaptation.contracts import (
    AdaptationContext,
    AdaptationProposal,
)
from app.ai.adaptation.errors import (
    AdaptationProviderAPIError,
    AdaptationProviderTimeoutError,
    EmptyAdaptationResponseError,
    InvalidAdaptationJSONError,
    InvalidAdaptationProposalError,
)
from app.ai.adaptation.prompts import build_adaptation_prompt
from app.ai.openai_compatible import (
    OpenAICompatibleStructuredClient,
    StructuredProviderErrors,
)
from app.core.config import Settings


class OpenAICompatibleAdaptationProvider:
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
            output_model=AdaptationProposal,
            operation="Adaptation",
            contract_name="AdaptationProposal",
            errors=StructuredProviderErrors(
                timeout=AdaptationProviderTimeoutError,
                api=AdaptationProviderAPIError,
                empty=EmptyAdaptationResponseError,
                invalid_json=InvalidAdaptationJSONError,
                invalid_output=InvalidAdaptationProposalError,
            ),
            client=client,
            max_attempts=max_attempts,
            retry_delay_seconds=retry_delay_seconds,
        )

    async def propose(
        self, context: AdaptationContext
    ) -> AdaptationProposal:
        prompt = build_adaptation_prompt(context)
        return await self._structured_client.generate(
            [
                {"role": "system", "content": prompt.system},
                {"role": "user", "content": prompt.user},
            ]
        )

    async def close(self) -> None:
        await self._structured_client.close()
