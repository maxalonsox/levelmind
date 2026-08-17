import asyncio
import json
import logging
from dataclasses import dataclass
from enum import StrEnum
from time import monotonic
from typing import Any, Generic, TypeVar

from openai import (
    APIConnectionError,
    APIStatusError,
    APITimeoutError,
    AsyncOpenAI,
    OpenAIError,
    RateLimitError,
)
from pydantic import BaseModel, ValidationError

from app.ai.errors import AIConfigurationError
from app.core.config import Settings

logger = logging.getLogger(__name__)

OutputModel = TypeVar("OutputModel", bound=BaseModel)


class _ResponseMode(StrEnum):
    STRUCTURED = "structured"
    JSON_OBJECT = "json_object"
    PLAIN_JSON = "plain_json"


class _StructuredOutputCompatibilityError(Exception):
    def __init__(self, exception_type: str) -> None:
        super().__init__("Structured output parsing is incompatible")
        self.exception_type = exception_type


@dataclass(frozen=True)
class StructuredProviderErrors:
    timeout: type[Exception]
    api: type[Exception]
    empty: type[Exception]
    invalid_json: type[Exception]
    invalid_output: type[Exception]


class OpenAICompatibleStructuredClient(Generic[OutputModel]):
    def __init__(
        self,
        settings: Settings,
        *,
        output_model: type[OutputModel],
        operation: str,
        contract_name: str,
        errors: StructuredProviderErrors,
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
        self._output_model = output_model
        self._operation = operation
        self._contract_name = contract_name
        self._errors = errors
        self._max_attempts = max_attempts
        self._retry_delay_seconds = retry_delay_seconds

    async def generate(
        self, messages: list[dict[str, str]]
    ) -> OutputModel:
        mode = _ResponseMode.STRUCTURED
        started_at = monotonic()
        logger.info(
            "%s generation started",
            self._operation,
            extra={"ai_model": self._model},
        )

        for attempt in range(1, self._max_attempts + 1):
            try:
                result = await self._request(messages, mode)
            except _StructuredOutputCompatibilityError as exc:
                fallback_mode = self._next_mode(mode)
                logger.warning(
                    "%s structured output mode failed; using fallback",
                    self._operation,
                    extra={
                        "ai_model": self._model,
                        "attempt": attempt,
                        "response_mode": "structured_output",
                        "next_response_mode": fallback_mode.value,
                        "error_type": exc.exception_type,
                        "exception_type": exc.exception_type,
                    },
                )
                mode = fallback_mode
                continue
            except APITimeoutError as exc:
                if await self._retry_transient(attempt, exc):
                    continue
                self._log_failure(attempt, exc)
                raise self._errors.timeout(
                    f"{self._operation} provider timed out"
                ) from exc
            except RateLimitError as exc:
                if await self._retry_transient(attempt, exc):
                    continue
                self._log_failure(attempt, exc)
                raise self._errors.api(
                    f"{self._operation} provider is temporarily unavailable"
                ) from exc
            except APIConnectionError as exc:
                if await self._retry_transient(attempt, exc):
                    continue
                self._log_failure(attempt, exc)
                raise self._errors.api(
                    f"{self._operation} provider connection failed"
                ) from exc
            except APIStatusError as exc:
                if self._supports_fallback(exc, mode):
                    fallback_mode = self._next_mode(mode)
                    logger.warning(
                        "%s response mode unsupported; using fallback",
                        self._operation,
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
                raise self._errors.api(
                    f"{self._operation} provider request failed"
                ) from exc
            except OpenAIError as exc:
                self._log_failure(attempt, exc)
                raise self._errors.api(
                    f"{self._operation} provider response could not be processed"
                ) from exc
            except (
                self._errors.empty,
                self._errors.invalid_json,
                self._errors.invalid_output,
            ) as exc:
                self._log_failure(attempt, exc)
                raise

            duration_ms = round((monotonic() - started_at) * 1000)
            logger.info(
                "%s generation completed",
                self._operation,
                extra={
                    "ai_model": self._model,
                    "attempts": attempt,
                    "duration_ms": duration_ms,
                    "response_mode": mode.value,
                },
            )
            return result

        raise self._errors.api(
            f"{self._operation} provider request failed"
        )

    async def close(self) -> None:
        await self._client.close()

    async def _request(
        self,
        messages: list[dict[str, str]],
        mode: _ResponseMode,
    ) -> OutputModel:
        if mode is _ResponseMode.STRUCTURED:
            try:
                completion = await self._client.chat.completions.parse(
                    model=self._model,
                    messages=messages,
                    response_format=self._output_model,
                )
            except (
                AttributeError,
                IndexError,
                KeyError,
                TypeError,
                ValidationError,
            ) as exc:
                raise _StructuredOutputCompatibilityError(
                    type(exc).__name__
                ) from exc
            message = self._first_message(completion)
            if message.parsed is not None:
                return self._validate(message.parsed)
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

    def _first_message(self, completion: Any) -> Any:
        if not completion.choices:
            raise self._errors.empty(
                f"{self._operation} provider returned no choices"
            )
        return completion.choices[0].message

    def _parse_content(self, content: str | None) -> OutputModel:
        if content is None or not content.strip():
            raise self._errors.empty(
                f"{self._operation} provider returned an empty response"
            )
        try:
            payload = json.loads(content)
        except json.JSONDecodeError as exc:
            raise self._errors.invalid_json(
                f"{self._operation} provider returned invalid JSON"
            ) from exc
        return self._validate(payload)

    def _validate(self, payload: Any) -> OutputModel:
        validation_payload = (
            payload.model_dump() if isinstance(payload, BaseModel) else payload
        )
        try:
            return self._output_model.model_validate(validation_payload)
        except ValidationError as exc:
            raise self._errors.invalid_output(
                self._invalid_output_message
            ) from exc

    @property
    def _invalid_output_message(self) -> str:
        return (
            f"{self._operation} response does not match "
            f"{self._contract_name}"
        )

    async def _retry_transient(self, attempt: int, exc: Exception) -> bool:
        if attempt >= self._max_attempts:
            return False
        logger.warning(
            "Retrying transient %s provider error",
            self._operation.lower(),
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
            "%s generation failed",
            self._operation,
            extra={
                "ai_model": self._model,
                "attempts": attempt,
                "error_type": type(exc).__name__,
            },
        )
