"""
Custom Exceptions for Enterprise Doc Bot

Provides structured exception handling with clear error categories.
"""


class BotError(Exception):
    """
    Base exception for all bot errors.

    Attributes:
        message: Human-readable error message
        user_message: Message safe to show to users (no sensitive info)
    """

    def __init__(self, message: str, user_message: str = None):
        self.message = message
        self.user_message = user_message or "An error occurred. Please try again."
        super().__init__(self.message)


class ConfigurationError(BotError):
    """
    Configuration related errors.

    Raised when:
    - Required environment variables are missing
    - Invalid configuration values
    """

    def __init__(self, message: str):
        super().__init__(
            message=message,
            user_message="Bot configuration error. Please contact administrator.",
        )


class AIServiceError(BotError):
    """
    AI service related errors.

    Raised when:
    - API calls fail
    - Timeout occurs
    - Rate limits hit
    - Invalid response from AI
    """

    def __init__(self, message: str, user_message: str = None):
        super().__init__(
            message=message,
            user_message=user_message
            or "AI service temporarily unavailable. Please try again.",
        )


class AITimeoutError(AIServiceError):
    """AI request timed out."""

    def __init__(self, timeout_seconds: int = 120):
        super().__init__(
            message=f"AI request timed out after {timeout_seconds}s",
            user_message="Analysis is taking too long. Please try with a smaller document.",
        )


class AIResponseError(AIServiceError):
    """Invalid or unparseable AI response."""

    def __init__(self, message: str):
        super().__init__(
            message=message,
            user_message="Could not process AI response. Please try again.",
        )


class DocumentError(BotError):
    """
    Document processing errors.

    Raised when:
    - File is corrupted or invalid
    - File format not supported
    - Text replacement fails
    """

    def __init__(self, message: str, user_message: str = None):
        super().__init__(
            message=message,
            user_message=user_message
            or "Could not process the document. Please check the file and try again.",
        )


class DocumentValidationError(DocumentError):
    """Document failed validation."""

    def __init__(self, reason: str):
        super().__init__(
            message=f"Document validation failed: {reason}",
            user_message=f"Invalid document: {reason}",
        )


class DocumentProcessingError(DocumentError):
    """Error during document processing (read/write/edit)."""

    def __init__(self, operation: str, details: str = ""):
        message = f"Document {operation} failed"
        if details:
            message += f": {details}"
        super().__init__(
            message=message,
            user_message=f"Could not {operation} the document. Please try again.",
        )


class SessionError(BotError):
    """
    Session management errors.

    Raised when:
    - Session not found
    - Session expired
    - Invalid session state
    """

    def __init__(self, message: str, user_message: str = None):
        super().__init__(
            message=message,
            user_message=user_message
            or "Session error. Please start over with /start.",
        )


class SessionNotFoundError(SessionError):
    """Session does not exist."""

    def __init__(self, user_id: int):
        super().__init__(
            message=f"Session not found for user {user_id}",
            user_message="Your session has expired. Please start over.",
        )


class SessionExpiredError(SessionError):
    """Session has expired due to timeout."""

    def __init__(self, user_id: int):
        super().__init__(
            message=f"Session expired for user {user_id}",
            user_message="Your session has expired due to inactivity. Please start over.",
        )


class FileError(BotError):
    """
    File handling errors.

    Raised when:
    - File download fails
    - File too large
    - File not found
    """

    def __init__(self, message: str, user_message: str = None):
        super().__init__(
            message=message,
            user_message=user_message or "File operation failed. Please try again.",
        )


class FileDownloadError(FileError):
    """Failed to download file from Telegram."""

    def __init__(self, details: str = ""):
        message = "Failed to download file from Telegram"
        if details:
            message += f": {details}"
        super().__init__(
            message=message,
            user_message="Could not download your file. Please try again.",
        )


class FileTooLargeError(FileError):
    """File exceeds size limit."""

    def __init__(self, size_mb: float, max_mb: float):
        super().__init__(
            message=f"File size {size_mb:.1f}MB exceeds limit {max_mb}MB",
            user_message=f"File too large. Maximum size is {max_mb}MB.",
        )


class RateLimitError(BotError):
    """
    Rate limit exceeded.

    Raised when user sends too many requests.
    """

    def __init__(self, wait_seconds: float = 1.0):
        super().__init__(
            message=f"Rate limit exceeded, wait {wait_seconds}s",
            user_message="Please slow down. Try again in a moment.",
        )
