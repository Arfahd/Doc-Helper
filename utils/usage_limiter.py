"""
Usage Limiter - Track per-user AI request limits (rolling 7-day window).

Prevents abuse by limiting how many AI analyses a user can perform per week.
Uses in-memory storage (resets on bot restart).
"""

import time
from typing import Dict, List, Tuple
from loguru import logger

from config import WEEKLY_ANALYSIS_LIMIT, WARNING_THRESHOLD, LIMIT_WINDOW_SECONDS


class UsageLimiter:
    """
    Track per-user AI request limits using a rolling 7-day window.

    Instead of resetting at a fixed time, this tracks timestamps of each request.
    Requests older than 7 days are automatically removed, giving users a fresh
    allowance as their old requests "expire".

    Storage format:
    {user_id: {"requests": [timestamp1, timestamp2, ...]}}
    """

    def __init__(self):
        self._usage: Dict[int, Dict[str, List[float]]] = {}
        self._last_cleanup = time.time()
        self._cleanup_interval = 3600  # Clean up stale users every hour

    def _cleanup_expired(self, user_id: int) -> None:
        """Remove requests older than the window for a specific user."""
        if user_id not in self._usage:
            return

        cutoff = time.time() - LIMIT_WINDOW_SECONDS
        self._usage[user_id]["requests"] = [
            ts for ts in self._usage[user_id]["requests"] if ts > cutoff
        ]

    def _cleanup_stale_users(self) -> None:
        """
        Periodically remove users with no recent requests.
        Prevents memory buildup from inactive users.
        """
        current_time = time.time()

        # Only run cleanup periodically
        if current_time - self._last_cleanup < self._cleanup_interval:
            return

        self._last_cleanup = current_time
        cutoff = current_time - LIMIT_WINDOW_SECONDS

        users_to_remove = []
        for user_id, data in self._usage.items():
            # Remove user if all their requests are expired
            if not data.get("requests") or all(ts <= cutoff for ts in data["requests"]):
                users_to_remove.append(user_id)

        for user_id in users_to_remove:
            del self._usage[user_id]

        if users_to_remove:
            logger.debug(
                f"[LIMIT] Cleanup: removed {len(users_to_remove)} stale user entries"
            )

    def can_use_ai(self, user_id: int) -> Tuple[bool, int, str]:
        """
        Check if user can make an AI request.

        Args:
            user_id: Telegram user ID

        Returns:
            Tuple of (allowed, remaining, message_key)
            - allowed: True if user can make a request
            - remaining: Number of requests remaining
            - message_key: "limit_warning", "limit_reached", or "" (empty)
        """
        self._cleanup_expired(user_id)
        self._cleanup_stale_users()

        current_count = len(self._usage.get(user_id, {}).get("requests", []))
        remaining = WEEKLY_ANALYSIS_LIMIT - current_count

        if remaining <= 0:
            logger.warning(
                f"[LIMIT] User {user_id} blocked: limit reached "
                f"({current_count}/{WEEKLY_ANALYSIS_LIMIT})"
            )
            return False, 0, "limit_reached"

        # Check if warning should be shown (approaching limit)
        if current_count >= WARNING_THRESHOLD:
            logger.info(
                f"[LIMIT] User {user_id} approaching limit: "
                f"{current_count}/{WEEKLY_ANALYSIS_LIMIT} used, {remaining} remaining"
            )
            return True, remaining, "limit_warning"

        return True, remaining, ""

    def record_usage(self, user_id: int) -> int:
        """
        Record an AI request for the user.

        Should be called AFTER a successful AI request.

        Args:
            user_id: Telegram user ID

        Returns:
            New remaining count after recording
        """
        if user_id not in self._usage:
            self._usage[user_id] = {"requests": []}

        self._usage[user_id]["requests"].append(time.time())
        self._cleanup_expired(user_id)

        remaining = WEEKLY_ANALYSIS_LIMIT - len(self._usage[user_id]["requests"])
        used = len(self._usage[user_id]["requests"])

        logger.info(
            f"[LIMIT] User {user_id} used AI. "
            f"Usage: {used}/{WEEKLY_ANALYSIS_LIMIT}, Remaining: {remaining}"
        )

        return remaining

    def get_usage(self, user_id: int) -> Tuple[int, int]:
        """
        Get usage statistics for a user.

        Args:
            user_id: Telegram user ID

        Returns:
            Tuple of (used, limit)
        """
        self._cleanup_expired(user_id)
        used = len(self._usage.get(user_id, {}).get("requests", []))
        return used, WEEKLY_ANALYSIS_LIMIT

    def get_next_expiry(self, user_id: int) -> float:
        """
        Get timestamp of when the user's oldest request will expire.

        Useful for telling users when they'll have capacity again.

        Args:
            user_id: Telegram user ID

        Returns:
            Timestamp when oldest request expires, or 0 if no requests
        """
        self._cleanup_expired(user_id)
        requests = self._usage.get(user_id, {}).get("requests", [])

        if not requests:
            return 0

        oldest = min(requests)
        return oldest + LIMIT_WINDOW_SECONDS


# Global instance
usage_limiter = UsageLimiter()
