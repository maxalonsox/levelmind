import asyncio
import json
from collections.abc import Sequence
from types import SimpleNamespace
from typing import Any, cast

import httpx
import pytest
from openai import (
    APITimeoutError,
    AsyncOpenAI,
    AuthenticationError,
    BadRequestError,
)

from app.ai.adaptation.contracts import (
    AdaptationContext,
    AdaptationProposal,
)
from app.ai.adaptation.errors import (
    AdaptationProviderAPIError,
    AdaptationProviderTimeoutError,
    InvalidAdaptationJSONError,
    InvalidAdaptationProposalError,
)
from app.ai.adaptation.openai_compatible import (
    OpenAICompatibleAdaptationProvider,
)
from app.ai.evaluation.contracts import EvaluationGoalContext, EvaluationResult
from app.core.config import Settings


def settings() -> Settings:
    return Settings(
        database_url="postgresql+psycopg://test:test@localhost/test",
        supabase_url="https://test.supabase.co",
        ai_api_key="test-provider-key",
        ai_base_url="https://compatible.example/v1",
        ai_model="configured-provider-model",
        ai_timeout_seconds=12,
    )


def context() -> AdaptationContext:
    evaluation = EvaluationResult(
        status="struggling",
        summary="Repeated difficulty was observed.",
        signals=[
            {
                "type": "high_difficulty",
                "description": "Three Tasks were marked difficult.",
                "severity": "high",
            }
        ],
        needs_adaptation=True,
    )
    return AdaptationContext(
        goal=EvaluationGoalContext(
            title="Learn backend",
            current_situation="Python fundamentals",
            expected_outcome="Build APIs",
            target_timeframe="Three months",
            availability="Five hours per week",
        ),
        evaluation=evaluation,
        plan_outline=[],
        relevant_tasks=[],
    )


def valid_payload() -> dict[str, Any]:
    return {
        "decision": "no_change",
        "summary": "No bounded change can be justified.",
        "rationale": "The evidence does not identify a safe target.",
        "changes": [],
    }


def completion(*, parsed: Any = None, content: str | None = None) -> Any:
    message = SimpleNamespace(parsed=parsed, content=content)
    return SimpleNamespace(choices=[SimpleNamespace(message=message)])


def api_error(error_type, status_code: int):
    request = httpx.Request(
        "POST", "https://provider.example/v1/chat/completions"
    )
    response = httpx.Response(status_code, request=request)
    return error_type("Provider error", response=response, body={})


class StubCompletions:
    def __init__(
        self,
        *,
        parse_results: Sequence[Any],
        create_results: Sequence[Any] = (),
    ) -> None:
        self.parse_results = list(parse_results)
        self.create_results = list(create_results)
        self.parse_calls: list[dict[str, Any]] = []
        self.create_calls: list[dict[str, Any]] = []

    async def parse(self, **kwargs: Any) -> Any:
        self.parse_calls.append(kwargs)
        result = self.parse_results.pop(0)
        if isinstance(result, Exception):
            raise result
        return result

    async def create(self, **kwargs: Any) -> Any:
        self.create_calls.append(kwargs)
        result = self.create_results.pop(0)
        if isinstance(result, Exception):
            raise result
        return result


class StubClient:
    def __init__(self, completions: StubCompletions) -> None:
        self.chat = SimpleNamespace(completions=completions)

    async def close(self) -> None:
        pass


def provider_with(
    completions: StubCompletions,
) -> OpenAICompatibleAdaptationProvider:
    return OpenAICompatibleAdaptationProvider(
        settings(),
        client=cast(AsyncOpenAI, StubClient(completions)),
        retry_delay_seconds=0,
    )


def test_adaptation_provider_uses_structured_output_and_configured_model() -> None:
    completions = StubCompletions(
        parse_results=[completion(parsed=valid_payload())]
    )

    result = asyncio.run(provider_with(completions).propose(context()))

    assert isinstance(result, AdaptationProposal)
    assert completions.parse_calls[0]["model"] == "configured-provider-model"
    assert completions.parse_calls[0]["response_format"] is AdaptationProposal


def test_adaptation_provider_falls_back_to_json_object() -> None:
    completions = StubCompletions(
        parse_results=[api_error(BadRequestError, 400)],
        create_results=[completion(content=json.dumps(valid_payload()))],
    )

    result = asyncio.run(provider_with(completions).propose(context()))

    assert isinstance(result, AdaptationProposal)
    assert completions.create_calls[0]["response_format"] == {
        "type": "json_object"
    }


def test_adaptation_provider_falls_back_to_plain_json() -> None:
    completions = StubCompletions(
        parse_results=[api_error(BadRequestError, 400)],
        create_results=[
            api_error(BadRequestError, 400),
            completion(content=json.dumps(valid_payload())),
        ],
    )

    result = asyncio.run(provider_with(completions).propose(context()))

    assert isinstance(result, AdaptationProposal)
    assert "response_format" not in completions.create_calls[1]


def test_adaptation_provider_retries_timeout_and_stops() -> None:
    request = httpx.Request(
        "POST", "https://provider.example/v1/chat/completions"
    )
    completions = StubCompletions(
        parse_results=[APITimeoutError(request=request)] * 3
    )

    with pytest.raises(AdaptationProviderTimeoutError):
        asyncio.run(provider_with(completions).propose(context()))

    assert len(completions.parse_calls) == 3


def test_adaptation_provider_transforms_api_error() -> None:
    completions = StubCompletions(
        parse_results=[api_error(AuthenticationError, 401)]
    )

    with pytest.raises(AdaptationProviderAPIError):
        asyncio.run(provider_with(completions).propose(context()))


def test_adaptation_provider_rejects_invalid_json() -> None:
    completions = StubCompletions(
        parse_results=[completion(parsed=None, content="not-json")]
    )

    with pytest.raises(InvalidAdaptationJSONError):
        asyncio.run(provider_with(completions).propose(context()))


def test_adaptation_provider_rejects_invalid_schema() -> None:
    completions = StubCompletions(
        parse_results=[
            completion(
                parsed=None,
                content=json.dumps(
                    {
                        "decision": "propose_changes",
                        "summary": "Invalid",
                        "rationale": "No changes.",
                        "changes": [],
                    }
                ),
            )
        ]
    )

    with pytest.raises(InvalidAdaptationProposalError):
        asyncio.run(provider_with(completions).propose(context()))
