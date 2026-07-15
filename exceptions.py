class CloudAuditorError(Exception):
    """Base exception for Cloud Auditor application."""
    pass


class ConfigError(CloudAuditorError):
    """Exception raised when configuration is invalid or missing."""
    pass


class AuthenticationError(CloudAuditorError):
    """Exception raised when authentication with a cloud provider fails."""
    pass


class ThrottlingError(CloudAuditorError):
    """Exception raised when API requests are throttled."""
    pass


class ScannerError(CloudAuditorError):
    """Exception raised when a scan fails."""
    pass


class CleanupError(CloudAuditorError):
    """Exception raised when cleanup of a resource fails."""
    pass
