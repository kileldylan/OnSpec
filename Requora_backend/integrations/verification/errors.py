class LLMProviderError(Exception):
    """Raised when an LLM provider response cannot be used safely."""

    def __init__(
        self,
        message,
        *,
        status_code=None,
        provider_code=None,
        provider_type=None,
    ):
        self.status_code = status_code
        self.provider_code = provider_code
        self.provider_type = provider_type
        super().__init__(message)


class VerificationProcessingError(Exception):
    """Raised when a verification run fails during an external service step."""

    def __init__(self, *, run_id, stage, reason=None):
        self.run_id = run_id
        self.stage = stage
        self.reason = reason
        super().__init__(
            f"Verification run {run_id} failed during {stage}. "
            "See backend logs for details."
        )
