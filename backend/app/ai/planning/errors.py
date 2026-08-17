from app.ai.errors import AIConfigurationError


class PlanningError(Exception):
    """Base error for plan generation failures."""


class PlanningProviderTimeoutError(PlanningError):
    """The planning provider did not respond before the timeout."""


class PlanningProviderAPIError(PlanningError):
    """The planning provider request failed."""


class EmptyPlanningResponseError(PlanningError):
    """The planning provider returned no usable content."""


class InvalidPlanningJSONError(PlanningError):
    """The planning provider returned content that is not JSON."""


class InvalidGeneratedPlanError(PlanningError):
    """The planning provider response violates the GeneratedPlan contract."""
