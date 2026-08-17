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

from app.ai.evaluation.contracts import (
    EvaluationContext,
    EvaluationFeedbackMetrics,
    EvaluationGoalContext,
    EvaluationMetrics,
    EvaluationResult,
    EvaluationTemporalMetrics,
)
from app.ai.evaluation.errors import (
    EvaluationProviderAPIError,
    EvaluationProviderTimeoutError,
    InvalidEvaluationJSONError,
    InvalidEvaluationResultError,
)
from app.ai.evaluation.openai_compatible import (
    OpenAICompatibleEvaluationProvider,
)
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


def evaluation_context() -> EvaluationContext:
    return EvaluationContext(
        goal=EvaluationGoalContext(
            title="Learn backend",
            current_situation="Python fundamentals",
            expected_outcome="Build APIs",
            target_timeframe="Three months",
            availability="Five hours per week",
        ),
        metrics=EvaluationMetrics(
            total_tasks=5,
            completed_tasks=3,
            skipped_tasks=0,
            pending_tasks=2,
            resolved_tasks=3,
            progress_percentage=60,
            xp_earned=30,
        ),
        feedback_metrics=EvaluationFeedbackMetrics(
            tasks_with_difficulty_feedback=3,
            easy_count=1,
            normal_count=2,
            difficult_count=0,
            tasks_with_feedback_text=0,
            tasks_without_explicit_feedback=0,
        ),
        temporal_metrics=EvaluationTemporalMetrics(
            resolved_tasks=3,
            first_resolved_at=None,
            last_resolved_at=None,
        ),
        missions=[],
        feedback_samples=[],
        deterministic_signals=[],
    )


def valid_result_payload() -> dict[str, Any]:
    return {
        "status": "on_track",
        "summary": "Execution evidence is consistent so far.",
        "signals": [
            {
                "type": "consistent_progress",
                "description": "Three resolved Tasks were completed.",
                "severity": "low",
            }
        ],
        "needs_adaptation": False,
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
        self.closed = False

    async def close(self) -> None:
        self.closed = True


def provider_with(
    completions: StubCompletions,
) -> OpenAICompatibleEvaluationProvider:
    return OpenAICompatibleEvaluationProvider(
        settings(),
        client=cast(AsyncOpenAI, StubClient(completions)),
        retry_delay_seconds=0,
    )


def test_evaluation_provider_uses_structured_output_and_configured_model() -> None:
    completions = StubCompletions(
        parse_results=[completion(parsed=valid_result_payload())]
    )

    result = asyncio.run(
        provider_with(completions).evaluate(evaluation_context())
    )

    assert isinstance(result, EvaluationResult)
    assert completions.parse_calls[0]["model"] == "configured-provider-model"
    assert completions.parse_calls[0]["response_format"] is EvaluationResult


def test_evaluation_provider_falls_back_to_json_object() -> None:
    completions = StubCompletions(
        parse_results=[api_error(BadRequestError, 400)],
        create_results=[
            completion(content=json.dumps(valid_result_payload()))
        ],
    )

    result = asyncio.run(
        provider_with(completions).evaluate(evaluation_context())
    )

    assert isinstance(result, EvaluationResult)
    assert completions.create_calls[0]["response_format"] == {
        "type": "json_object"
    }


def test_evaluation_provider_falls_back_to_plain_json() -> None:
    completions = StubCompletions(
        parse_results=[api_error(BadRequestError, 400)],
        create_results=[
            api_error(BadRequestError, 400),
            completion(content=json.dumps(valid_result_payload())),
        ],
    )

    result = asyncio.run(
        provider_with(completions).evaluate(evaluation_context())
    )

    assert isinstance(result, EvaluationResult)
    assert len(completions.parse_calls) + len(completions.create_calls) == 3
    assert "response_format" not in completions.create_calls[1]


def test_evaluation_provider_retries_timeout_and_stops() -> None:
    request = httpx.Request(
        "POST", "https://provider.example/v1/chat/completions"
    )
    completions = StubCompletions(
        parse_results=[
            APITimeoutError(request=request),
            APITimeoutError(request=request),
            APITimeoutError(request=request),
        ]
    )

    with pytest.raises(EvaluationProviderTimeoutError):
        asyncio.run(
            provider_with(completions).evaluate(evaluation_context())
        )

    assert len(completions.parse_calls) == 3


def test_evaluation_provider_transforms_api_error() -> None:
    completions = StubCompletions(
        parse_results=[api_error(AuthenticationError, 401)]
    )

    with pytest.raises(EvaluationProviderAPIError):
        asyncio.run(
            provider_with(completions).evaluate(evaluation_context())
        )


def test_evaluation_provider_rejects_invalid_json() -> None:
    completions = StubCompletions(
        parse_results=[completion(parsed=None, content="not-json")]
    )

    with pytest.raises(InvalidEvaluationJSONError):
        asyncio.run(
            provider_with(completions).evaluate(evaluation_context())
        )


def test_evaluation_provider_rejects_invalid_result() -> None:
    completions = StubCompletions(
        parse_results=[
            completion(
                parsed=None,
                content=json.dumps(
                    {
                        "status": "unsupported",
                        "summary": "Invalid",
                        "signals": [],
                        "needs_adaptation": False,
                    }
                ),
            )
        ]
    )

    with pytest.raises(InvalidEvaluationResultError):
        asyncio.run(
            provider_with(completions).evaluate(evaluation_context())
        )
