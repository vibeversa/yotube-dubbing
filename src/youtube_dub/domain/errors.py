class YoutubeDubError(Exception):
    error_code: str = "UNKNOWN_ERROR"

    def __init__(self, message: str, retryable: bool = False) -> None:
        super().__init__(message)
        self.message = message
        self.retryable = retryable


class ConfigurationError(YoutubeDubError):
    error_code = "CONFIGURATION_ERROR"


class DomainValidationError(YoutubeDubError):
    error_code = "DOMAIN_VALIDATION_ERROR"


class ManifestError(YoutubeDubError):
    error_code = "MANIFEST_ERROR"


class ProviderError(YoutubeDubError):
    error_code = "PROVIDER_ERROR"


class ProviderQuotaError(ProviderError):
    error_code = "PROVIDER_QUOTA_EXHAUSTED"


class ProviderRateLimitError(ProviderError):
    error_code = "PROVIDER_RATE_LIMIT"


class ProviderAuthenticationError(ProviderError):
    error_code = "PROVIDER_AUTH_FAILED"


class ProviderTransientError(ProviderError):
    error_code = "PROVIDER_TRANSIENT_ERROR"


class ProviderInvalidRequestError(ProviderError):
    error_code = "PROVIDER_INVALID_REQUEST"


class ProcessError(YoutubeDubError):
    error_code = "PROCESS_ERROR"


class ProcessTimeoutError(ProcessError):
    error_code = "PROCESS_TIMEOUT"


class ProcessCancelledError(ProcessError):
    error_code = "PROCESS_CANCELLED"


class ProcessExitCodeError(ProcessError):
    error_code = "PROCESS_NONZERO_EXIT"


class ArtifactError(YoutubeDubError):
    error_code = "ARTIFACT_ERROR"


class StageError(YoutubeDubError):
    error_code = "STAGE_ERROR"


class JobError(YoutubeDubError):
    error_code = "JOB_ERROR"
