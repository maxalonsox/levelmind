import asyncio
import json
import logging
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

from app.ai import openai_compatible
from app.ai.planning.contracts import PlanningGoalInput
from app.ai.planning.errors import (
    AIConfigurationError,
    EmptyPlanningResponseError,
    InvalidGeneratedPlanError,
    InvalidPlanningJSONError,
    PlanningProviderAPIError,
    PlanningProviderTimeoutError,
)
from app.ai.planning.openai_compatible import OpenAICompatiblePlanningProvider
from app.core.config import Settings
from app.schemas.generated_plan import GeneratedPlan


def settings(**overrides: Any) -> Settings:
    values = {
        "database_url": "postgresql+psycopg://test:test@localhost/test",
        "supabase_url": "https://test.supabase.co",
        "ai_api_key": "test-provider-key",
        "ai_base_url": None,
        "ai_model": "configured-provider-model",
        "ai_timeout_seconds": 12,
    }
    values.update(overrides)
    return Settings(**values)


def goal_input() -> PlanningGoalInput:
    return PlanningGoalInput(
        title="Learn backend development",
        current_situation="Python fundamentals",
        expected_outcome="Build production APIs",
        target_timeframe="Six months",
        availability="Eight hours per week",
    )


def valid_plan_payload() -> dict[str, Any]:
    return {
        "stages": [
            {
                "title": "Foundation",
                "order_index": 0,
                "missions": [
                    {
                        "title": "Build an API",
                        "order_index": 0,
                        "estimated_difficulty": "normal",
                        "tasks": [
                            {
                                "title": "Implement one endpoint",
                                "order_index": 0,
                                "estimated_duration_minutes": 45,
                                "xp_reward": 10,
                            }
                        ],
                    }
                ],
            }
        ]
    }


def completion(*, parsed: Any = None, content: str | None = None) -> Any:
    message = SimpleNamespace(parsed=parsed, content=content)
    return SimpleNamespace(choices=[SimpleNamespace(message=message)])


def api_error(error_type, status_code: int):
    request = httpx.Request("POST", "https://provider.example/v1/chat/completions")
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


def provider_with(completions: StubCompletions) -> OpenAICompatiblePlanningProvider:
    return OpenAICompatiblePlanningProvider(
        settings(),
        client=cast(AsyncOpenAI, StubClient(completions)),
        retry_delay_seconds=0,
    )


@pytest.mark.parametrize(
    "overrides,missing_name",
    [
        ({"ai_api_key": None}, "AI_API_KEY"),
        ({"ai_model": None}, "AI_MODEL"),
    ],
)
def test_provider_rejects_incomplete_configuration(
    overrides: dict[str, Any], missing_name: str
) -> None:
    with pytest.raises(AIConfigurationError, match=missing_name):
        OpenAICompatiblePlanningProvider(settings(**overrides))


def test_provider_uses_alternate_base_url_and_configured_model(monkeypatch) -> None:
    captured_options: dict[str, Any] = {}
    completions = StubCompletions(
        parse_results=[completion(parsed=valid_plan_payload())]
    )

    def create_client(**kwargs: Any) -> StubClient:
        captured_options.update(kwargs)
        return StubClient(completions)

    monkeypatch.setattr(openai_compatible, "AsyncOpenAI", create_client)
    provider = OpenAICompatiblePlanningProvider(
        settings(ai_base_url="https://compatible.example/v1")
    )

    result = asyncio.run(provider.generate_plan(goal_input()))

    assert isinstance(result, GeneratedPlan)
    assert captured_options == {
        "api_key": "test-provider-key",
        "base_url": "https://compatible.example/v1",
        "timeout": 12.0,
        "max_retries": 0,
    }
    assert completions.parse_calls[0]["model"] == "configured-provider-model"


def test_provider_falls_back_to_json_mode() -> None:
    completions = StubCompletions(
        parse_results=[api_error(BadRequestError, 400)],
        create_results=[
            completion(content=json.dumps(valid_plan_payload()))
        ],
    )

    result = asyncio.run(provider_with(completions).generate_plan(goal_input()))

    assert isinstance(result, GeneratedPlan)
    assert len(completions.parse_calls) == 1
    assert completions.create_calls[0]["response_format"] == {
        "type": "json_object"
    }


def test_provider_falls_back_when_sdk_structured_parser_raises_type_error(
    caplog: pytest.LogCaptureFixture,
) -> None:
    parser_error = TypeError("'NoneType' object is not iterable")
    completions = StubCompletions(
        parse_results=[parser_error],
        create_results=[completion(content=json.dumps(valid_plan_payload()))],
    )

    with caplog.at_level(logging.WARNING, logger="app.ai.openai_compatible"):
        result = asyncio.run(
            provider_with(completions).generate_plan(goal_input())
        )

    assert isinstance(result, GeneratedPlan)
    assert len(completions.parse_calls) == 1
    assert len(completions.create_calls) == 1
    assert completions.create_calls[0]["response_format"] == {
        "type": "json_object"
    }
    fallback_record = next(
        record
        for record in caplog.records
        if "structured output mode failed" in record.getMessage()
    )
    assert fallback_record.exception_type == "TypeError"
    assert fallback_record.response_mode == "structured_output"
    assert fallback_record.next_response_mode == "json_object"
    assert "NoneType" not in caplog.text


def test_structured_parser_error_can_continue_through_plain_json() -> None:
    completions = StubCompletions(
        parse_results=[TypeError("'NoneType' object is not iterable")],
        create_results=[
            api_error(BadRequestError, 400),
            completion(content=json.dumps(valid_plan_payload())),
        ],
    )

    result = asyncio.run(provider_with(completions).generate_plan(goal_input()))

    assert isinstance(result, GeneratedPlan)
    assert len(completions.parse_calls) == 1
    assert len(completions.create_calls) == 2
    assert "response_format" not in completions.create_calls[1]


def test_structured_parser_error_never_escapes_when_all_modes_fail() -> None:
    completions = StubCompletions(
        parse_results=[TypeError("'NoneType' object is not iterable")],
        create_results=[
            api_error(BadRequestError, 400),
            completion(content="not-json"),
        ],
    )

    with pytest.raises(InvalidPlanningJSONError) as exc_info:
        asyncio.run(provider_with(completions).generate_plan(goal_input()))

    assert not isinstance(exc_info.value, TypeError)
    assert len(completions.parse_calls) == 1
    assert len(completions.create_calls) == 2


def test_provider_falls_back_to_plain_json_with_three_total_requests() -> None:
    completions = StubCompletions(
        parse_results=[api_error(BadRequestError, 400)],
        create_results=[
            api_error(BadRequestError, 400),
            completion(content=json.dumps(valid_plan_payload())),
        ],
    )

    result = asyncio.run(provider_with(completions).generate_plan(goal_input()))

    assert isinstance(result, GeneratedPlan)
    assert len(completions.parse_calls) + len(completions.create_calls) == 3
    assert "response_format" not in completions.create_calls[1]


def test_provider_retries_timeout_without_sdk_retries() -> None:
    request = httpx.Request("POST", "https://provider.example/v1/chat/completions")
    completions = StubCompletions(
        parse_results=[
            APITimeoutError(request=request),
            completion(parsed=valid_plan_payload()),
        ]
    )

    result = asyncio.run(provider_with(completions).generate_plan(goal_input()))

    assert isinstance(result, GeneratedPlan)
    assert len(completions.parse_calls) == 2


def test_provider_stops_after_three_timeout_attempts() -> None:
    request = httpx.Request("POST", "https://provider.example/v1/chat/completions")
    completions = StubCompletions(
        parse_results=[
            APITimeoutError(request=request),
            APITimeoutError(request=request),
            APITimeoutError(request=request),
        ]
    )

    with pytest.raises(PlanningProviderTimeoutError):
        asyncio.run(provider_with(completions).generate_plan(goal_input()))

    assert len(completions.parse_calls) == 3


def test_provider_transforms_non_transient_api_error() -> None:
    completions = StubCompletions(
        parse_results=[api_error(AuthenticationError, 401)]
    )

    with pytest.raises(
        PlanningProviderAPIError, match="Planning provider request failed"
    ):
        asyncio.run(provider_with(completions).generate_plan(goal_input()))

    assert len(completions.parse_calls) == 1


def test_provider_rejects_empty_response() -> None:
    completions = StubCompletions(
        parse_results=[completion(parsed=None, content="")]
    )

    with pytest.raises(EmptyPlanningResponseError):
        asyncio.run(provider_with(completions).generate_plan(goal_input()))


def test_provider_rejects_invalid_json_without_fragile_extraction() -> None:
    completions = StubCompletions(
        parse_results=[completion(parsed=None, content="```json\n{}\n```")]
    )

    with pytest.raises(InvalidPlanningJSONError):
        asyncio.run(provider_with(completions).generate_plan(goal_input()))


def test_provider_rejects_json_that_violates_generated_plan() -> None:
    completions = StubCompletions(
        parse_results=[completion(parsed=None, content='{"stages": []}')]
    )

    with pytest.raises(InvalidGeneratedPlanError):
        asyncio.run(provider_with(completions).generate_plan(goal_input()))
