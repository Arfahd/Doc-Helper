"""
Unit tests for agents/brain.py

Uses mocking to avoid actual API calls.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

# Import from project
from agents.brain import (
    _extract_fixes_from_response,
    _clean_grammar_response,
    calculate_cost,
    UsageTracker,
)


class TestExtractFixesFromResponse:
    """Tests for _extract_fixes_from_response function."""

    def test_extract_from_code_block(self, sample_ai_response_with_fixes):
        """Test extracting fixes from JSON code block."""
        fixes = _extract_fixes_from_response(sample_ai_response_with_fixes)

        assert len(fixes) == 3
        assert fixes[0]["search"] == "erors"
        assert fixes[0]["replace"] == "errors"

    def test_extract_empty_array(self, sample_ai_response_no_fixes):
        """Test extracting from response with no fixes."""
        fixes = _extract_fixes_from_response(sample_ai_response_no_fixes)

        assert len(fixes) == 0

    def test_extract_raw_json(self):
        """Test extracting from raw JSON without code block."""
        response = 'Issues found: [{"search": "teh", "replace": "the"}]'
        fixes = _extract_fixes_from_response(response)

        assert len(fixes) == 1
        assert fixes[0]["search"] == "teh"

    def test_extract_filters_identical(self):
        """Test that identical search/replace are filtered."""
        response = """```json
[{"search": "same", "replace": "same"}, {"search": "different", "replace": "changed"}]
```"""
        fixes = _extract_fixes_from_response(response)

        assert len(fixes) == 1
        assert fixes[0]["search"] == "different"

    def test_extract_filters_empty_search(self):
        """Test that empty search strings are filtered."""
        response = """```json
[{"search": "", "replace": "something"}, {"search": "valid", "replace": "changed"}]
```"""
        fixes = _extract_fixes_from_response(response)

        assert len(fixes) == 1
        assert fixes[0]["search"] == "valid"

    def test_extract_handles_malformed_json(self):
        """Test handling of malformed JSON."""
        response = """```json
[{"search": "incomplete"
```"""
        fixes = _extract_fixes_from_response(response)

        assert len(fixes) == 0

    def test_extract_handles_no_json(self):
        """Test handling when no JSON is present."""
        response = "This is just text without any JSON."
        fixes = _extract_fixes_from_response(response)

        assert len(fixes) == 0

    def test_extract_multiple_fixes_single_line(self):
        """Test extracting multiple fixes from single line JSON."""
        response = """```json
[{"search": "a", "replace": "b"}, {"search": "c", "replace": "d"}, {"search": "e", "replace": "f"}]
```"""
        fixes = _extract_fixes_from_response(response)

        assert len(fixes) == 3

    def test_extract_multiline_json(self):
        """Test extracting from properly formatted multiline JSON."""
        response = """```json
[
    {"search": "error1", "replace": "fix1"},
    {"search": "error2", "replace": "fix2"},
    {"search": "error3", "replace": "fix3"},
    {"search": "error4", "replace": "fix4"},
    {"search": "error5", "replace": "fix5"}
]
```"""
        fixes = _extract_fixes_from_response(response)

        assert len(fixes) == 5


class TestCleanGrammarResponse:
    """Tests for _clean_grammar_response function."""

    def test_removes_json_code_block(self):
        """Test that JSON code block is removed."""
        response = """Analysis text here.

```json
[{"search": "test", "replace": "fixed"}]
```"""
        cleaned = _clean_grammar_response(response)

        assert "```json" not in cleaned
        assert "search" not in cleaned
        assert "Analysis text here" in cleaned

    def test_preserves_analysis_text(self):
        """Test that analysis text is preserved."""
        response = """Here is my analysis.

Found 2 issues:
1. First issue
2. Second issue

```json
[{"search": "a", "replace": "b"}]
```"""
        cleaned = _clean_grammar_response(response)

        assert "Here is my analysis" in cleaned
        assert "Found 2 issues" in cleaned
        assert "First issue" in cleaned

    def test_handles_no_json(self):
        """Test handling response with no JSON."""
        response = "Just plain analysis text."
        cleaned = _clean_grammar_response(response)

        assert cleaned == "Just plain analysis text."


class TestCalculateCost:
    """Tests for calculate_cost function."""

    def test_calculate_haiku_cost(self):
        """Test cost calculation for Haiku model."""
        from config import MODEL_FAST

        cost = calculate_cost(MODEL_FAST, input_tokens=1000, output_tokens=500)

        # Haiku: $0.25/1M input, $1.25/1M output
        expected = (1000 / 1_000_000) * 0.25 + (500 / 1_000_000) * 1.25
        assert abs(cost - expected) < 0.0001

    def test_calculate_sonnet_cost(self):
        """Test cost calculation for Sonnet model."""
        from config import MODEL_SMART

        cost = calculate_cost(MODEL_SMART, input_tokens=1000, output_tokens=500)

        # Sonnet: $3.0/1M input, $15.0/1M output
        expected = (1000 / 1_000_000) * 3.0 + (500 / 1_000_000) * 15.0
        assert abs(cost - expected) < 0.0001

    def test_zero_tokens_zero_cost(self):
        """Test that zero tokens results in zero cost."""
        from config import MODEL_FAST

        cost = calculate_cost(MODEL_FAST, input_tokens=0, output_tokens=0)

        assert cost == 0


class TestUsageTracker:
    """Tests for UsageTracker class."""

    def test_initial_state(self):
        """Test initial state of tracker."""
        tracker = UsageTracker()

        stats = tracker.get_stats()
        assert stats["requests"] == 0
        assert stats["input_tokens"] == 0
        assert stats["output_tokens"] == 0
        assert stats["total_cost_usd"] == 0

    def test_add_usage(self):
        """Test adding usage."""
        tracker = UsageTracker()

        # Use model name with dash to match expected format in add_usage
        tracker.add_usage(
            model="claude-test-model",
            input_tokens=100,
            output_tokens=50,
            cost=0.01,
            task="test_task",
        )

        stats = tracker.get_stats()
        assert stats["requests"] == 1
        assert stats["input_tokens"] == 100
        assert stats["output_tokens"] == 50
        assert stats["total_cost_usd"] == 0.01

    def test_cumulative_tracking(self):
        """Test that usage accumulates."""
        tracker = UsageTracker()

        # Use model name with dash to match expected format in add_usage
        tracker.add_usage("claude-test-model", 100, 50, 0.01, "task1")
        tracker.add_usage("claude-test-model", 200, 100, 0.02, "task2")

        stats = tracker.get_stats()
        assert stats["requests"] == 2
        assert stats["input_tokens"] == 300
        assert stats["output_tokens"] == 150
        assert abs(stats["total_cost_usd"] - 0.03) < 0.0001


class TestReviewDocumentMocked:
    """Tests for review_document with mocked API calls."""

    @pytest.mark.asyncio
    async def test_review_document_success(self):
        """Test successful review_document call."""
        from agents.brain import review_document

        # Mock response
        mock_content = MagicMock()
        mock_content.text = """Analysis complete.

```json
[{"search": "teh", "replace": "the"}]
```"""

        mock_usage = MagicMock()
        mock_usage.input_tokens = 100
        mock_usage.output_tokens = 50

        mock_response = MagicMock()
        mock_response.content = [mock_content]
        mock_response.usage = mock_usage

        with patch(
            "agents.brain.client.messages.create", new_callable=AsyncMock
        ) as mock_create:
            mock_create.return_value = mock_response

            result, fixes, cost = await review_document("test content", "grammar")

            assert "Analysis complete" in result
            assert len(fixes) == 1
            assert fixes[0]["search"] == "teh"
            assert cost > 0

    @pytest.mark.asyncio
    async def test_review_document_timeout(self):
        """Test review_document timeout handling."""
        import asyncio
        from agents.brain import review_document

        with patch(
            "agents.brain.client.messages.create", new_callable=AsyncMock
        ) as mock_create:
            mock_create.side_effect = asyncio.TimeoutError()

            result, fixes, cost = await review_document("test content", "grammar")

            assert "timed out" in result.lower()
            assert len(fixes) == 0
            assert cost == 0

    @pytest.mark.asyncio
    async def test_review_document_error(self):
        """Test review_document error handling."""
        from agents.brain import review_document

        with patch(
            "agents.brain.client.messages.create", new_callable=AsyncMock
        ) as mock_create:
            mock_create.side_effect = Exception("API Error")

            result, fixes, cost = await review_document("test content", "grammar")

            assert "failed" in result.lower()
            assert len(fixes) == 0


class TestGenerateImprovementsMocked:
    """Tests for generate_improvements with mocked API calls."""

    @pytest.mark.asyncio
    async def test_generate_improvements_success(self):
        """Test successful generate_improvements call."""
        from agents.brain import generate_improvements

        mock_content = MagicMock()
        mock_content.text = '[{"search": "teh", "replace": "the"}, {"search": "erors", "replace": "errors"}]'

        mock_usage = MagicMock()
        mock_usage.input_tokens = 100
        mock_usage.output_tokens = 50

        mock_response = MagicMock()
        mock_response.content = [mock_content]
        mock_response.usage = mock_usage

        with patch(
            "agents.brain.client.messages.create", new_callable=AsyncMock
        ) as mock_create:
            mock_create.return_value = mock_response

            fixes, cost = await generate_improvements("test content")

            assert len(fixes) == 2
            assert cost > 0

    @pytest.mark.asyncio
    async def test_generate_improvements_empty(self):
        """Test generate_improvements with no fixes found."""
        from agents.brain import generate_improvements

        mock_content = MagicMock()
        mock_content.text = "[]"

        mock_usage = MagicMock()
        mock_usage.input_tokens = 100
        mock_usage.output_tokens = 10

        mock_response = MagicMock()
        mock_response.content = [mock_content]
        mock_response.usage = mock_usage

        with patch(
            "agents.brain.client.messages.create", new_callable=AsyncMock
        ) as mock_create:
            mock_create.return_value = mock_response

            fixes, cost = await generate_improvements("clean content")

            assert len(fixes) == 0
            assert cost > 0
