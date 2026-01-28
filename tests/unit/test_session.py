"""
Unit tests for utils/session.py
"""

import os
import time
import pytest

# Import from project
from utils.session import (
    SessionManager,
    sanitize_filename,
    generate_unique_filename,
    get_clean_output_name,
)


class TestSanitizeFilename:
    """Tests for sanitize_filename function."""

    def test_normal_filename(self):
        """Test normal filename passes through."""
        assert sanitize_filename("document.docx") == "document.docx"

    def test_filename_with_spaces(self):
        """Test filename with spaces is preserved."""
        assert sanitize_filename("my document.docx") == "my document.docx"

    def test_path_traversal_blocked(self):
        """Test path traversal attempts are blocked."""
        assert sanitize_filename("../../../etc/passwd") == "document.docx"
        assert sanitize_filename("..\\..\\windows\\system32") == "document.docx"

    def test_null_bytes_removed(self):
        """Test null bytes are removed."""
        result = sanitize_filename("file\x00name.docx")
        assert "\x00" not in result

    def test_empty_string_returns_default(self):
        """Test empty string returns default filename."""
        assert sanitize_filename("") == "document.docx"

    def test_hidden_file_returns_default(self):
        """Test hidden file (starting with dot) returns default."""
        assert sanitize_filename(".hidden") == "document.docx"

    def test_adds_docx_extension(self):
        """Test .docx extension is added if missing."""
        assert sanitize_filename("document").endswith(".docx")

    def test_preserves_docx_extension(self):
        """Test existing .docx extension is preserved."""
        result = sanitize_filename("myfile.docx")
        assert result == "myfile.docx"
        assert not result.endswith(".docx.docx")

    def test_unicode_letters_allowed(self):
        """Test Unicode letters are allowed."""
        # Indonesian/Malay
        assert "dokumen" in sanitize_filename("dokumen.docx")
        # With Unicode
        result = sanitize_filename("файл.docx")  # Russian
        assert len(result) > 5  # Should have content, not just "document.docx"

    def test_special_characters_removed(self):
        """Test special characters are removed."""
        result = sanitize_filename('file<>:"|?*.docx')
        assert "<" not in result
        assert ">" not in result
        assert ":" not in result
        assert "|" not in result
        assert "?" not in result
        assert "*" not in result


class TestGenerateUniqueFilename:
    """Tests for generate_unique_filename function."""

    def test_generates_path_in_downloads(self):
        """Test generated path is in downloads directory."""
        result = generate_unique_filename(123, "test.docx", "unique123")
        assert "downloads" in result

    def test_includes_unique_id(self):
        """Test generated path includes unique ID."""
        result = generate_unique_filename(123, "test.docx", "unique123")
        assert "unique123" in result

    def test_sanitizes_filename(self):
        """Test filename is sanitized."""
        result = generate_unique_filename(123, "../../../etc/passwd", "unique123")
        assert ".." not in result
        assert "etc" not in result
        assert "passwd" not in result


class TestGetCleanOutputName:
    """Tests for get_clean_output_name function."""

    def test_adds_revisi_suffix(self):
        """Test _revisi suffix is added."""
        result = get_clean_output_name("document.docx")
        assert result == "document_revisi.docx"

    def test_preserves_extension(self):
        """Test extension is preserved."""
        result = get_clean_output_name("myfile.docx")
        assert result.endswith(".docx")

    def test_handles_multiple_dots(self):
        """Test filename with multiple dots."""
        result = get_clean_output_name("my.file.name.docx")
        assert result == "my.file.name_revisi.docx"


class TestSessionManager:
    """Tests for SessionManager class."""

    @pytest.fixture
    def session_manager(self):
        """Create a fresh SessionManager for each test."""
        return SessionManager()

    def test_create_session(self, session_manager):
        """Test creating a new session."""
        session = session_manager.create_session(123, mode="edit")

        assert session is not None
        assert session["mode"] == "edit"
        assert session["file_path"] is None
        assert session["pending_fixes"] == []

    def test_get_session(self, session_manager):
        """Test getting an existing session."""
        session_manager.create_session(123, mode="edit")

        session = session_manager.get_session(123)
        assert session is not None
        assert session["mode"] == "edit"

    def test_get_nonexistent_session(self, session_manager):
        """Test getting a session that doesn't exist."""
        session = session_manager.get_session(999)
        assert session is None

    def test_update_session(self, session_manager):
        """Test updating session data."""
        session_manager.create_session(123, mode="edit")
        session_manager.update_session(123, find_text="hello", replace_text="world")

        session = session_manager.get_session(123)
        assert session["find_text"] == "hello"
        assert session["replace_text"] == "world"

    def test_update_session_resets_warning(self, session_manager):
        """Test that updating session resets warning_sent flag."""
        session_manager.create_session(123, mode="edit")
        session_manager.mark_warning_sent(123)

        assert session_manager.is_warning_sent(123) is True

        session_manager.update_session(123, find_text="test")

        assert session_manager.is_warning_sent(123) is False

    def test_set_file(self, session_manager, temp_docx):
        """Test setting file for session."""
        session_manager.create_session(123, mode="edit")
        session_manager.set_file(123, temp_docx, "test.docx")

        assert session_manager.get_file_path(123) == temp_docx
        assert session_manager.get_original_name(123) == "test.docx"

    def test_has_file(self, session_manager, temp_docx):
        """Test checking if session has file."""
        session_manager.create_session(123, mode="edit")

        assert session_manager.has_file(123) is False

        session_manager.set_file(123, temp_docx, "test.docx")

        assert session_manager.has_file(123) is True

    def test_cleanup_session(self, session_manager, tmp_path):
        """Test cleaning up session."""
        # Create a temp file
        temp_file = tmp_path / "test.docx"
        temp_file.write_bytes(b"test content")

        session_manager.create_session(123, mode="edit")
        session_manager.set_file(123, str(temp_file), "test.docx")

        session_manager.cleanup_session(123)

        # Session should be gone
        assert session_manager.get_session(123) is None
        # File should be deleted
        assert not temp_file.exists()

    def test_is_session_active(self, session_manager):
        """Test checking if session is active."""
        assert session_manager.is_session_active(123) is False

        session_manager.create_session(123, mode="edit")

        assert session_manager.is_session_active(123) is True

    def test_update_activity(self, session_manager):
        """Test updating activity timestamp."""
        session_manager.create_session(123, mode="edit")

        old_activity = session_manager.get_session(123)["last_activity"]
        time.sleep(0.1)

        session_manager.update_activity(123)

        new_activity = session_manager.get_session(123)["last_activity"]
        assert new_activity > old_activity

    def test_set_chat_id(self, session_manager):
        """Test setting chat ID."""
        session_manager.create_session(123, mode="edit")
        session_manager.set_chat_id(123, 456)

        session = session_manager.get_session(123)
        assert session["chat_id"] == 456

    def test_get_all_sessions(self, session_manager):
        """Test getting all sessions."""
        session_manager.create_session(123, mode="edit")
        session_manager.create_session(456, mode="analyze")

        all_sessions = session_manager.get_all_sessions()

        assert len(all_sessions) == 2
        assert 123 in all_sessions
        assert 456 in all_sessions


class TestSessionTimeout:
    """Tests for session timeout functionality."""

    @pytest.fixture
    def session_manager(self):
        """Create a fresh SessionManager for each test."""
        return SessionManager()

    def test_mark_warning_sent(self, session_manager):
        """Test marking warning as sent."""
        session_manager.create_session(123, mode="edit")

        assert session_manager.is_warning_sent(123) is False

        session_manager.mark_warning_sent(123)

        assert session_manager.is_warning_sent(123) is True

    def test_get_timeout_remaining(self, session_manager):
        """Test getting timeout remaining."""
        session_manager.create_session(123, mode="edit")

        remaining = session_manager.get_timeout_remaining(123)

        # Should be close to full timeout since just created
        assert remaining > 0

    def test_get_timeout_remaining_no_session(self, session_manager):
        """Test getting timeout for non-existent session."""
        remaining = session_manager.get_timeout_remaining(999)
        assert remaining == 0
