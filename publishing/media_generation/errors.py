"""Media generation errors (local-only policy)."""

from __future__ import annotations


class LocalImageGeneratorUnavailable(RuntimeError):
    """Raised when no safe local image generator is available.

    Code: LOCAL_IMAGE_GENERATOR_UNAVAILABLE
    Never falls back to Agnes.
    """

    code = "LOCAL_IMAGE_GENERATOR_UNAVAILABLE"

    def __init__(self, message: str = "Local image generator is unavailable"):
        super().__init__(f"{self.code}: {message}")


class PendingLocalGeneration(RuntimeError):
    """Images were not produced; prompt packages were written instead."""

    code = "PENDING_LOCAL_GENERATION"

    def __init__(self, message: str, *, job_dir: str = ""):
        self.job_dir = job_dir
        super().__init__(f"{self.code}: {message}")


class AgnesImageGenerationDisabled(RuntimeError):
    """Agnes image generation is deprecated and disabled in production."""

    code = "AGNES_IMAGE_GENERATION_DISABLED"

    def __init__(self, message: str = "Agnes image generation is deprecated"):
        super().__init__(f"{self.code}: {message}")
