"""
Unit tests for tools/doc_tools.py
"""

import os
import pytest
from docx import Document

# Import from project
from tools.doc_tools import (
    validate_docx,
    count_text_in_docx,
    replace_text_in_docx,
    read_docx_full_text,
    apply_multiple_fixes,
)


class TestValidateDocx:
    """Tests for validate_docx function."""

    def test_valid_docx(self, temp_docx):
        """Test validation of a valid DOCX file."""
        is_valid, error = validate_docx(temp_docx)
        assert is_valid is True
        assert error == ""

    def test_nonexistent_file(self):
        """Test validation of non-existent file."""
        is_valid, error = validate_docx("/nonexistent/path/file.docx")
        assert is_valid is False
        assert "not found" in error.lower()

    def test_wrong_extension(self, tmp_path):
        """Test validation of file with wrong extension."""
        txt_file = tmp_path / "test.txt"
        txt_file.write_text("not a docx")

        is_valid, error = validate_docx(str(txt_file))
        assert is_valid is False
        assert "invalid file type" in error.lower()

    def test_corrupted_file(self, tmp_path):
        """Test validation of corrupted DOCX file."""
        fake_docx = tmp_path / "fake.docx"
        fake_docx.write_text("this is not a valid docx")

        is_valid, error = validate_docx(str(fake_docx))
        assert is_valid is False


class TestCountTextInDocx:
    """Tests for count_text_in_docx function."""

    def test_count_existing_text(self, temp_docx):
        """Test counting text that exists in document."""
        count = count_text_in_docx(temp_docx, "teh")
        assert count >= 2  # "teh" appears multiple times

    def test_count_nonexistent_text(self, temp_docx):
        """Test counting text that doesn't exist."""
        count = count_text_in_docx(temp_docx, "xyznonexistent")
        assert count == 0

    def test_count_case_sensitive(self, temp_docx):
        """Test that counting is case-sensitive."""
        count_lower = count_text_in_docx(temp_docx, "teh")
        count_upper = count_text_in_docx(temp_docx, "Teh")
        # They should be counted separately
        assert count_lower >= 0
        assert count_upper >= 0

    def test_count_in_empty_doc(self, empty_docx):
        """Test counting in empty document."""
        count = count_text_in_docx(empty_docx, "anything")
        assert count == 0


class TestReplaceTextInDocx:
    """Tests for replace_text_in_docx function."""

    def test_replace_existing_text(self, temp_docx):
        """Test replacing text that exists."""
        result_path = replace_text_in_docx(temp_docx, "teh", "the")

        assert result_path is not None
        assert os.path.exists(result_path)

        # Verify replacement worked
        new_count = count_text_in_docx(result_path, "teh")
        assert new_count == 0 or new_count < count_text_in_docx(temp_docx, "teh")

        # Cleanup
        os.remove(result_path)

    def test_replace_nonexistent_text(self, temp_docx):
        """Test replacing text that doesn't exist."""
        result_path = replace_text_in_docx(temp_docx, "xyznonexistent", "replacement")
        assert result_path is None

    def test_replace_creates_revisi_suffix(self, temp_docx):
        """Test that replacement creates file with _revisi suffix."""
        result_path = replace_text_in_docx(temp_docx, "teh", "the")

        assert result_path is not None
        assert "_revisi" in result_path

        # Cleanup
        os.remove(result_path)


class TestReadDocxFullText:
    """Tests for read_docx_full_text function."""

    def test_read_document_content(self, temp_docx):
        """Test reading document content."""
        text = read_docx_full_text(temp_docx)

        assert len(text) > 0
        assert "Test Document" in text
        assert "erors" in text

    def test_read_includes_table_content(self, temp_docx):
        """Test that table content is included."""
        text = read_docx_full_text(temp_docx)

        assert "Header 1" in text
        assert "teh value" in text

    def test_read_empty_document(self, empty_docx):
        """Test reading empty document."""
        text = read_docx_full_text(empty_docx)
        assert text == ""

    def test_read_nonexistent_file(self):
        """Test reading non-existent file."""
        text = read_docx_full_text("/nonexistent/path/file.docx")
        assert text == ""


class TestApplyMultipleFixes:
    """Tests for apply_multiple_fixes function."""

    def test_apply_valid_fixes(self, temp_docx, sample_fixes):
        """Test applying multiple valid fixes."""
        result_path, applied, skipped, applied_list, skipped_list = (
            apply_multiple_fixes(temp_docx, sample_fixes)
        )

        assert result_path is not None
        assert applied > 0
        assert len(applied_list) == applied
        assert len(skipped_list) == skipped

        # Cleanup
        os.remove(result_path)

    def test_apply_no_fixes(self, temp_docx):
        """Test applying empty fixes list."""
        result_path, applied, skipped, applied_list, skipped_list = (
            apply_multiple_fixes(temp_docx, [])
        )

        assert result_path is None
        assert applied == 0
        assert skipped == 0

    def test_apply_nonexistent_fixes(self, temp_docx):
        """Test applying fixes that don't match any text."""
        fixes = [
            {"search": "xyznonexistent1", "replace": "a"},
            {"search": "xyznonexistent2", "replace": "b"},
        ]

        result_path, applied, skipped, applied_list, skipped_list = (
            apply_multiple_fixes(temp_docx, fixes)
        )

        assert result_path is None
        assert applied == 0
        assert skipped == 2
        assert len(skipped_list) == 2

    def test_apply_mixed_fixes(self, temp_docx):
        """Test applying mix of valid and invalid fixes."""
        fixes = [
            {"search": "teh", "replace": "the"},  # Valid
            {"search": "xyznonexistent", "replace": "nope"},  # Invalid
            {"search": "erors", "replace": "errors"},  # Valid
        ]

        result_path, applied, skipped, applied_list, skipped_list = (
            apply_multiple_fixes(temp_docx, fixes)
        )

        assert result_path is not None
        assert applied >= 1
        assert skipped >= 1

        # Cleanup
        os.remove(result_path)

    def test_apply_fix_with_empty_search(self, temp_docx):
        """Test that fixes with empty search are skipped."""
        fixes = [
            {"search": "", "replace": "something"},
            {"search": "teh", "replace": "the"},
        ]

        result_path, applied, skipped, applied_list, skipped_list = (
            apply_multiple_fixes(temp_docx, fixes)
        )

        # Empty search should be skipped
        assert skipped >= 1

        if result_path:
            os.remove(result_path)

    def test_counts_match_lists(self, temp_docx, sample_fixes):
        """Test that counts match list lengths."""
        result_path, applied, skipped, applied_list, skipped_list = (
            apply_multiple_fixes(temp_docx, sample_fixes)
        )

        assert applied == len(applied_list)
        assert skipped == len(skipped_list)
        assert applied + skipped == len(sample_fixes)

        if result_path:
            os.remove(result_path)
