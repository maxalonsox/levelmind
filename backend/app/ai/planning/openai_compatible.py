import asyncio
import json
import logging
from enum import StrEnum
from time import monotonic
from typing import Any

from openai import (
    APIConnectionError,
    APIStatusError,
    APITimeoutError,
    AsyncOpenAI,
    OpenAIError,
    RateLimitError,
)
from pydantic import BaseModel, ValidationError

from app.ai.planning.contracts import PlanningGoalInput
from app.ai.planning.errors import (
    AIConfigurationError,
    EmptyPlanningResponseError,
    InvalidGeneratedPlanError,
    InvalidPlanningJSONError,
    PlanningProviderAPIError,
    PlanningProviderTimeoutError,
)
from app.ai.planning.prompts import build_planning_prompt
from app.core.config import Settings
from app.schemas.generated_plan import GeneratedPlan

logger = logging.getLogger(__name__)


class _ResponseMode(StrEnum):
    STRUCTURED = "structured"
    JSON_OBJECT = "json_object"
    PLAIN_JSON = "plain_json"


class OpenAICompatiblePlanningProvider:
    def __init__(
        self,
        settings: Settings,
        *,
        client: AsyncOpenAI | None = None,
        max_attempts: int = 3,
        retry_delay_seconds: float = 0.25,
    ) -> None:
        missing = []
        api_key = (
            settings.ai_api_key.get_secret_value().strip()
            if settings.ai_api_key is not None
            else ""
        )
        model = settings.ai_model.strip() if settings.ai_model else ""
        if not api_key:
            missing.append("AI_API_KEY")
        if not model:
            missing.append("AI_MODEL")
        if missing:
            raise AIConfigurationError(
                f"Missing AI configuration: {', '.join(missing)}"
            )
        if max_attempts < 1:
            raise ValueError("max_attempts must be at least 1")

        client_options: dict[str, Any] = {
            "api_key": api_key,
            "timeout": settings.ai_timeout_seconds,
            "max_retries": 0,
        }
        if settings.ai_base_url is not None:
            client_options["base_url"] = str(settings.ai_base_url)

        self._client = client or AsyncOpenAI(**client_options)
        self._model = model
        self._max_attempts = max_attempts
        self._retry_delay_seconds = retry_delay_seconds

    async def generate_plan(self, goal: PlanningGoalInput) -> GeneratedPlan:
        prompt = build_planning_prompt(goal)
        messages = [
            {"role": "system", "content": prompt.system},
            {"role": "user", "content": prompt.user},
        ]
        mode = _ResponseMode.STRUCTURED
        started_at = monotonic()

        logger.info(
            "Planning generation started",
            extra={"ai_model": self._model},
        )

        for attempt in range(1, self._max_attempts + 1):
            try:
                plan = await self._request_plan(messages, mode)
            except APITimeoutError as exc:
                if await self._retry_transient(attempt, exc):
                    continue
                self._log_failure(attempt, exc)
                raise PlanningProviderTimeoutError(
                    "Planning provider timed out"
                ) from exc
            except RateLimitError as exc:
                if await self._retry_transient(attempt, exc):
                    continue
                self._log_failure(attempt, exc)
                raise PlanningProviderAPIError(
                    "Planning provider is temporarily unavailable"
                ) from exc
            except APIConnectionError as exc:
                if await self._retry_transient(attempt, exc):
                    continue
                self._log_failure(attempt, exc)
                raise PlanningProviderAPIError(
                    "Planning provider connection failed"
                ) from exc
            except APIStatusError as exc:
                if self._supports_fallback(exc, mode):
                    fallback_mode = self._next_mode(mode)
                    logger.warning(
                        "Planning response mode unsupported; using fallback",
                        extra={
                            "ai_model": self._model,
                            "attempt": attempt,
                            "response_mode": mode.value,
                            "next_response_mode": fallback_mode.value,
                            "status_code": exc.status_code,
                        },
                    )
                    mode = fallback_mode
                    continue
                if exc.status_code >= 500 and await self._retry_transient(
                    attempt, exc
                ):
                    continue
                self._log_failure(attempt, exc)
                raise PlanningProviderAPIError(
                    "Planning provider request failed"
                ) from exc
            except OpenAIError as exc:
                self._log_failure(attempt, exc)
                raise PlanningProviderAPIError(
                    "Planning provider response could not be processed"
                ) from exc
            except (
                EmptyPlanningResponseError,
                InvalidPlanningJSONError,
                InvalidGeneratedPlanError,
            ) as exc:
                self._log_failure(attempt, exc)
                raise

            duration_ms = round((monotonic() - started_at) * 1000)
            logger.info(
                "Planning generation completed",
                extra={
                    "ai_model": self._model,
                    "attempts": attempt,
                    "duration_ms": duration_ms,
                    "response_mode": mode.value,
                },
            )
            return plan

        raise PlanningProviderAPIError("Planning provider request failed")

    async def close(self) -> None:
        await self._client.close()

    async def _request_plan(
        self, messages: list[dict[str, str]], mode: _ResponseMode
    ) -> GeneratedPlan:
        if mode is _ResponseMode.STRUCTURED:
            try:
                completion = await self._client.chat.completions.parse(
                    model=self._model,
                    messages=messages,
                    response_format=GeneratedPlan,
                )
            except ValidationError as exc:
                raise InvalidGeneratedPlanError(
                    "Planning response does not match GeneratedPlan"
                ) from exc
            message = self._first_message(completion)
            if message.parsed is not None:
                return self._validate_plan(message.parsed)
            return self._parse_content(message.content)

        request_options: dict[str, Any] = {
            "model": self._model,
            "messages": messages,
        }
        if mode is _ResponseMode.JSON_OBJECT:
            request_options["response_format"] = {"type": "json_object"}

        completion = await self._client.chat.completions.create(
            **request_options
        )
        message = self._first_message(completion)
        return self._parse_content(message.content)

    @staticmethod
    def _first_message(completion: Any) -> Any:
        if not completion.choices:
            raise EmptyPlanningResponseError(
                "Planning provider returned no choices"
            )
        return completion.choices[0].message

    def _parse_content(self, content: str | None) -> GeneratedPlan:
        if content is None or not content.strip():
            raise EmptyPlanningResponseError(
                "Planning provider returned an empty response"
            )
        try:
            payload = json.loads(content)
        except json.JSONDecodeError as exc:
            raise InvalidPlanningJSONError(
                "Planning provider returned invalid JSON"
            ) from exc
        return self._validate_plan(payload)

    @staticmethod
    def _validate_plan(payload: Any) -> GeneratedPlan:
        validation_payload = (
            payload.model_dump() if isinstance(payload, BaseModel) else payload
        )
        try:
            return GeneratedPlan.model_validate(validation_payload)
        except ValidationError as exc:
            raise InvalidGeneratedPlanError(
                "Planning response does not match GeneratedPlan"
            ) from exc

    async def _retry_transient(self, attempt: int, exc: Exception) -> bool:
        if attempt >= self._max_attempts:
            return False
        logger.warning(
            "Retrying transient planning provider error",
            extra={
                "ai_model": self._model,
                "attempt": attempt,
                "error_type": type(exc).__name__,
            },
        )
        await asyncio.sleep(self._retry_delay_seconds * (2 ** (attempt - 1)))
        return True

    @staticmethod
    def _supports_fallback(exc: APIStatusError, mode: _ResponseMode) -> bool:
        return mode is not _ResponseMode.PLAIN_JSON and exc.status_code in {
            400,
            404,
            415,
            422,
        }

    @staticmethod
    def _next_mode(mode: _ResponseMode) -> _ResponseMode:
        if mode is _ResponseMode.STRUCTURED:
            return _ResponseMode.JSON_OBJECT
        return _ResponseMode.PLAIN_JSON

    def _log_failure(self, attempt: int, exc: Exception) -> None:
        logger.warning(
            "Planning generation failed",
            extra={
                "ai_model": self._model,
                "attempts": attempt,
                "error_type": type(exc).__name__,
            },
        )
