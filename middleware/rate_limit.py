"""
Rate Limiting Middleware for Enterprise Doc Bot

Prevents users from sending too many requests in a short time.
Protects against abuse and excessive API costs.
"""

import time
from typing import Callable, Dict, Any, Awaitable

from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery, TelegramObject
from loguru import logger


class RateLimitMiddleware(BaseMiddleware):
    """
    Rate limiting middleware that throttles rapid requests.

    Features:
    - Configurable rate limit per user
    - Separate limits for messages and callbacks
    - Silent dropping of excess requests (no error message spam)
    - Automatic cleanup of old entries

    Args:
        message_rate_limit: Minimum seconds between messages (default: 0.5)
        callback_rate_limit: Minimum seconds between callback queries (default: 0.3)
        cleanup_interval: Seconds between cleanup runs (default: 60)
    """

    def __init__(
        self,
        message_rate_limit: float = 0.5,
        callback_rate_limit: float = 0.3,
        cleanup_interval: float = 60.0,
    ):
        self.message_rate_limit = message_rate_limit
        self.callback_rate_limit = callback_rate_limit
        self.cleanup_interval = cleanup_interval

        # Track last request time per user
        # Format: {user_id: {"message": timestamp, "callback": timestamp}}
        self.user_timestamps: Dict[int, Dict[str, float]] = {}
        self.last_cleanup = time.time()

    def _cleanup_old_entries(self) -> None:
        """Remove entries for users who haven't made requests recently."""
        current_time = time.time()

        # Only run cleanup periodically
        if current_time - self.last_cleanup < self.cleanup_interval:
            return

        self.last_cleanup = current_time
        cutoff = current_time - 300  # Remove entries older than 5 minutes

        users_to_remove = []
        for user_id, timestamps in self.user_timestamps.items():
            # Check if all timestamps are old
            if all(ts < cutoff for ts in timestamps.values()):
                users_to_remove.append(user_id)

        for user_id in users_to_remove:
            del self.user_timestamps[user_id]

        if users_to_remove:
            logger.debug(
                f"Rate limiter cleanup: removed {len(users_to_remove)} old entries"
            )

    def _is_rate_limited(self, user_id: int, request_type: str) -> bool:
        """
        Check if user is rate limited for the given request type.

        Args:
            user_id: Telegram user ID
            request_type: "message" or "callback"

        Returns:
            True if rate limited, False otherwise
        """
        current_time = time.time()
        rate_limit = (
            self.message_rate_limit
            if request_type == "message"
            else self.callback_rate_limit
        )

        # Get user's timestamp data
        if user_id not in self.user_timestamps:
            self.user_timestamps[user_id] = {}

        user_data = self.user_timestamps[user_id]
        last_request = user_data.get(request_type, 0)

        # Check if enough time has passed
        elapsed = current_time - last_request
        if elapsed < rate_limit:
            logger.debug(
                f"Rate limited user {user_id} ({request_type}): "
                f"{elapsed:.2f}s < {rate_limit}s"
            )
            return True

        # Update timestamp
        user_data[request_type] = current_time
        return False

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        """
        Process the event through rate limiting.

        Args:
            handler: The next handler in the chain
            event: The incoming event (Message or CallbackQuery)
            data: Additional data dictionary

        Returns:
            Handler result or None if rate limited
        """
        # Periodic cleanup
        self._cleanup_old_entries()

        # Determine user ID and request type
        user_id = None
        request_type = None

        if isinstance(event, Message):
            user_id = event.from_user.id if event.from_user else None
            request_type = "message"
        elif isinstance(event, CallbackQuery):
            user_id = event.from_user.id if event.from_user else None
            request_type = "callback"

        # Skip rate limiting if we can't identify the user
        if user_id is None:
            return await handler(event, data)

        # Check rate limit
        if self._is_rate_limited(user_id, request_type):
            # For callbacks, answer to prevent "loading" indicator
            if isinstance(event, CallbackQuery):
                try:
                    await event.answer()
                except Exception:
                    pass
            # Silently drop the request
            return None

        # Process normally
        return await handler(event, data)


class FileUploadRateLimitMiddleware(BaseMiddleware):
    """
    Additional rate limiting specifically for file uploads.

    Prevents users from uploading too many files in quick succession,
    which could lead to excessive storage usage or API costs.

    Args:
        upload_rate_limit: Minimum seconds between file uploads (default: 5.0)
    """

    def __init__(self, upload_rate_limit: float = 5.0):
        self.upload_rate_limit = upload_rate_limit
        self.user_last_upload: Dict[int, float] = {}

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        """Process file upload events with rate limiting."""

        # Only apply to messages with documents
        if not isinstance(event, Message) or not event.document:
            return await handler(event, data)

        user_id = event.from_user.id if event.from_user else None
        if user_id is None:
            return await handler(event, data)

        current_time = time.time()
        last_upload = self.user_last_upload.get(user_id, 0)
        elapsed = current_time - last_upload

        if elapsed < self.upload_rate_limit:
            logger.warning(
                f"File upload rate limited for user {user_id}: "
                f"{elapsed:.1f}s < {self.upload_rate_limit}s"
            )
            await event.answer("Please wait a moment before uploading another file.")
            return None

        # Update timestamp and proceed
        self.user_last_upload[user_id] = current_time
        return await handler(event, data)
