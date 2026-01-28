"""
Session Management for Enterprise Doc Bot
Handles file storage, cleanup, and timeout tracking.
"""

import os
import time
from typing import Optional, Dict, Any, List, Tuple
from loguru import logger

from config import (
    DOWNLOAD_DIR,
    SESSION_WARNING_SEC,
    SESSION_EXPIRE_SEC,
    IDLE_TIMEOUT_SEC,
)


# Ensure download directory exists
if not os.path.exists(DOWNLOAD_DIR):
    os.makedirs(DOWNLOAD_DIR)


class SessionManager:
    """
    Manages user sessions with file storage and timeout tracking.
    """

    def __init__(self):
        # Store session data: {user_id: {file_path, original_name, last_activity, ...}}
        self._sessions: Dict[int, Dict[str, Any]] = {}

    def create_session(self, user_id: int, mode: str) -> Dict[str, Any]:
        """
        Create a new session for a user.

        Args:
            user_id: Telegram user ID
            mode: Current mode (edit, analyze, fix)
        """
        self._sessions[user_id] = {
            "mode": mode,
            "file_path": None,
            "original_name": None,
            "last_activity": time.time(),
            "find_text": None,
            "replace_text": None,
            "pending_fixes": [],
            "fix_index": 0,
            "applied_fixes": [],
            "skipped_fixes": [],
            "warning_sent": False,  # Track if timeout warning was sent
            "chat_id": None,  # Store chat_id for sending timeout messages
        }
        logger.info(f"Session created for user {user_id}, mode: {mode}")
        return self._sessions[user_id]

    def get_session(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Get session data for a user."""
        return self._sessions.get(user_id)

    def get_all_sessions(self) -> Dict[int, Dict[str, Any]]:
        """Get all active sessions."""
        return self._sessions.copy()

    def update_session(self, user_id: int, **kwargs) -> None:
        """Update session data."""
        if user_id in self._sessions:
            self._sessions[user_id].update(kwargs)
            self._sessions[user_id]["last_activity"] = time.time()
            self._sessions[user_id]["warning_sent"] = False  # Reset warning on activity

    def update_activity(self, user_id: int) -> None:
        """Update last activity timestamp."""
        if user_id in self._sessions:
            self._sessions[user_id]["last_activity"] = time.time()
            self._sessions[user_id]["warning_sent"] = False  # Reset warning on activity

    def set_chat_id(self, user_id: int, chat_id: int) -> None:
        """Store chat_id for sending timeout messages."""
        if user_id in self._sessions:
            self._sessions[user_id]["chat_id"] = chat_id

    def set_file(self, user_id: int, file_path: str, original_name: str) -> None:
        """Store file path for user session."""
        if user_id in self._sessions:
            self._sessions[user_id]["file_path"] = file_path
            self._sessions[user_id]["original_name"] = original_name
            self._sessions[user_id]["last_activity"] = time.time()
            self._sessions[user_id]["warning_sent"] = False
            logger.info(f"File set for user {user_id}: {original_name}")

    def update_file(self, user_id: int, new_file_path: str) -> None:
        """Update file path after edit (for subsequent edits on same file)."""
        if user_id in self._sessions:
            old_path = self._sessions[user_id].get("file_path")
            self._sessions[user_id]["file_path"] = new_file_path
            self._sessions[user_id]["last_activity"] = time.time()
            self._sessions[user_id]["warning_sent"] = False

            # Clean up old file if different
            if old_path and old_path != new_file_path and os.path.exists(old_path):
                try:
                    os.remove(old_path)
                    logger.info(f"Cleaned up old file: {old_path}")
                except Exception as e:
                    logger.error(f"Failed to cleanup old file: {e}")

    def get_file_path(self, user_id: int) -> Optional[str]:
        """Get current file path for user."""
        session = self._sessions.get(user_id)
        return session.get("file_path") if session else None

    def get_original_name(self, user_id: int) -> Optional[str]:
        """Get original filename for user."""
        session = self._sessions.get(user_id)
        return session.get("original_name") if session else None

    def cleanup_session(self, user_id: int) -> None:
        """
        Clean up session - delete files and remove session data.
        """
        session = self._sessions.get(user_id)
        if session:
            # Delete file if exists
            file_path = session.get("file_path")
            if file_path and os.path.exists(file_path):
                try:
                    os.remove(file_path)
                    logger.info(f"Deleted file: {file_path}")
                except Exception as e:
                    logger.error(f"Failed to delete file: {e}")

            # Remove session
            del self._sessions[user_id]
            logger.info(f"Session cleaned up for user {user_id}")

    def has_file(self, user_id: int) -> bool:
        """Check if user has a file in session."""
        session = self._sessions.get(user_id)
        return bool(session and session.get("file_path"))

    def is_session_active(self, user_id: int) -> bool:
        """Check if user has an active session."""
        return user_id in self._sessions

    def mark_warning_sent(self, user_id: int) -> None:
        """Mark that timeout warning has been sent."""
        if user_id in self._sessions:
            self._sessions[user_id]["warning_sent"] = True

    def is_warning_sent(self, user_id: int) -> bool:
        """Check if timeout warning has been sent."""
        session = self._sessions.get(user_id)
        return session.get("warning_sent", False) if session else False

    def get_sessions_needing_warning(self) -> List[Tuple[int, int]]:
        """
        Get sessions that need a timeout warning.

        Returns:
            List of (user_id, chat_id) tuples for sessions needing warning
        """
        current_time = time.time()
        sessions_to_warn = []

        # Use list() to create a snapshot and avoid RuntimeError during iteration
        for user_id, session in list(self._sessions.items()):
            if session.get("warning_sent"):
                continue  # Already warned

            last_activity = session.get("last_activity", 0)
            elapsed = current_time - last_activity

            # Check if past warning threshold
            if elapsed >= SESSION_WARNING_SEC:
                chat_id = session.get("chat_id")
                if chat_id:
                    sessions_to_warn.append((user_id, chat_id))

        return sessions_to_warn

    def get_sessions_to_expire(self) -> List[Tuple[int, int]]:
        """
        Get sessions that should be expired.

        Returns:
            List of (user_id, chat_id) tuples for sessions to expire
        """
        current_time = time.time()
        sessions_to_expire = []

        # Use list() to create a snapshot and avoid RuntimeError during iteration
        for user_id, session in list(self._sessions.items()):
            last_activity = session.get("last_activity", 0)
            has_file = bool(session.get("file_path"))
            elapsed = current_time - last_activity

            # Use different timeout based on whether file is uploaded
            timeout = SESSION_EXPIRE_SEC if has_file else IDLE_TIMEOUT_SEC

            if elapsed >= timeout:
                chat_id = session.get("chat_id")
                if chat_id:
                    sessions_to_expire.append((user_id, chat_id))

        return sessions_to_expire

    def get_timeout_remaining(self, user_id: int) -> int:
        """Get seconds remaining before session timeout."""
        session = self._sessions.get(user_id)
        if not session:
            return 0

        last_activity = session.get("last_activity", 0)
        has_file = bool(session.get("file_path"))

        timeout = SESSION_EXPIRE_SEC if has_file else IDLE_TIMEOUT_SEC
        elapsed = time.time() - last_activity
        remaining = max(0, int(timeout - elapsed))

        return remaining


# Global session manager instance
session_manager = SessionManager()


def sanitize_filename(filename: str) -> str:
    """
    Sanitize filename to prevent path traversal and special character issues.

    Args:
        filename: Original filename

    Returns:
        Safe filename with only allowed characters
    """
    # Remove path separators and null bytes
    filename = filename.replace("/", "").replace("\\", "").replace("\x00", "")

    # Keep only safe ASCII characters: alphanumeric, dot, underscore, hyphen, space
    # Also allow common Unicode letters for international filenames
    safe_chars = []
    for char in filename:
        # Allow ASCII alphanumeric and safe punctuation
        if char.isascii() and (char.isalnum() or char in "._- "):
            safe_chars.append(char)
        # Allow Unicode letters (for international filenames) but not symbols
        elif not char.isascii() and char.isalpha():
            safe_chars.append(char)

    safe_filename = "".join(safe_chars).strip()

    # Ensure we have a valid filename
    if not safe_filename or safe_filename.startswith("."):
        safe_filename = "document.docx"

    # Ensure it has .docx extension
    if not safe_filename.lower().endswith(".docx"):
        safe_filename += ".docx"

    return safe_filename


def generate_unique_filename(user_id: int, original_name: str, unique_id: str) -> str:
    """
    Generate a unique filename for storing user's document.

    Args:
        user_id: Telegram user ID
        original_name: Original filename
        unique_id: Telegram file unique ID

    Returns:
        Full path to store the file
    """
    # Sanitize the original filename to prevent security issues
    safe_original = sanitize_filename(original_name)

    # Use unique_id to prevent collisions
    safe_name = f"{unique_id}_{safe_original}"
    return os.path.join(DOWNLOAD_DIR, safe_name)


def get_clean_output_name(original_name: str) -> str:
    """
    Generate a clean output filename for sending back to user.

    Args:
        original_name: Original filename

    Returns:
        Clean filename with _revisi suffix
    """
    base, ext = os.path.splitext(original_name)
    return f"{base}_revisi{ext}"
