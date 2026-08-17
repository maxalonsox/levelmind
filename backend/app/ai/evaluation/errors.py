class EvaluationError(Exception):
    """Base error for evaluation failures."""


class EvaluationProviderTimeoutError(EvaluationError):
    """The evaluation provider did not respond before the timeout."""


class EvaluationProviderAPIError(EvaluationError):
    """The evaluation provider request failed."""


class EmptyEvaluationResponseError(EvaluationError):
    """The evaluation provider returned no usable content."""


class InvalidEvaluationJSONError(EvaluationError):
    """The evaluation provider returned content that is not JSON."""


class InvalidEvaluationResultError(EvaluationError):
    """The evaluation response violates the EvaluationResult contract."""
