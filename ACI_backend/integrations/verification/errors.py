class LLMProviderError(Exception):
    """Raised when an LLM provider response cannot be used safely."""


class VerificationProcessingError(Exception):
    """Raised when a verification run fails during an external service step."""

    def __init__(self, *, run_id, stage):
        self.run_id = run_id
        self.stage = stage
        super().__init__(
            f"Verification run {run_id} failed during {stage}. "
            "See backend logs for details."
        )
