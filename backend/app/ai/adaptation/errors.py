class AdaptationError(Exception):
    """Base error for adaptation preview failures."""


class AdaptationProviderTimeoutError(AdaptationError):
    """The adaptation provider did not respond before the timeout."""


class AdaptationProviderAPIError(AdaptationError):
    """The adaptation provider request failed."""


class EmptyAdaptationResponseError(AdaptationError):
    """The adaptation provider returned no usable content."""


class InvalidAdaptationJSONError(AdaptationError):
    """The adaptation provider returned content that is not JSON."""


class InvalidAdaptationProposalError(AdaptationError):
    """The response violates the AdaptationProposal contract."""


class InvalidAdaptationTargetError(AdaptationError):
    """A proposed change references a target absent from the current plan."""
