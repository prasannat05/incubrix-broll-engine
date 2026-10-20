class EngineError(Exception):
    """Base exception for all B-roll engine failures."""

    def __init__(self, message: str, error_code: str = "ENGINE_ERROR", status_code: int = 500):
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.status_code = status_code


class UnsupportedFileError(EngineError):
    def __init__(self, message: str):
        super().__init__(message, error_code="UNSUPPORTED_FILE", status_code=400)


class AudioTooLongError(EngineError):
    def __init__(self, duration: float, max_duration: float):
        super().__init__(
            f"Audio duration ({duration:.1f}s) exceeds maximum allowed limit ({max_duration:.1f}s).",
            error_code="AUDIO_TOO_LONG",
            status_code=400,
        )


class NoBRollFoundError(EngineError):
    def __init__(self, message: str):
        super().__init__(message, error_code="NO_BROLL_FOUND", status_code=502)


class RenderingFailedError(EngineError):
    def __init__(self, message: str):
        super().__init__(message, error_code="RENDERING_FAILED", status_code=500)


class ExternalAPIFailureError(EngineError):
    def __init__(self, provider: str, message: str):
        super().__init__(
            f"External API failure from {provider}: {message}",
            error_code="API_FAILURE",
            status_code=502,
        )


class JobTimeoutError(EngineError):
    def __init__(self, job_id: str, timeout_seconds: int):
        super().__init__(
            f"Job {job_id} timed out after {timeout_seconds} seconds.",
            error_code="TIMEOUT",
            status_code=504,
        )
