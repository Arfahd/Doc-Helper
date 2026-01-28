"""
Brain Module - AI Analysis and Fix Generation
Uses hybrid model strategy:
- Haiku for simple tasks (grammar)
- Sonnet for complex tasks (full review, summary, fix generation)
"""

import asyncio
import json
from typing import Tuple, List
from anthropic import AsyncAnthropic
from loguru import logger


from config import (
    ANTHROPIC_API_KEY,
    MODEL_FAST,
    MODEL_SMART,
    MODEL_FOR_TASK,
    PRICING,
    MAX_CONTENT_CHARS,
    AI_MAX_TOKENS,
    AI_REQUEST_TIMEOUT,
)

# Initialize client with validation
if not ANTHROPIC_API_KEY:
    logger.error("ANTHROPIC_API_KEY is not set in environment!")
    raise ValueError("ANTHROPIC_API_KEY is required but not set in .env file")

client = AsyncAnthropic(api_key=ANTHROPIC_API_KEY)


# ============================================
# USAGE TRACKER - Logs tokens and cost to terminal
# ============================================


class UsageTracker:
    """Track total API usage across all requests."""

    def __init__(self):
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        self.total_cost_usd = 0.0
        self.request_count = 0

    def add_usage(
        self, model: str, input_tokens: int, output_tokens: int, cost: float, task: str
    ):
        """Add usage from a request and log to terminal."""
        self.total_input_tokens += input_tokens
        self.total_output_tokens += output_tokens
        self.total_cost_usd += cost
        self.request_count += 1

        # Log individual request
        logger.info(
            f"[API] {task} | Model: {model.split('-')[1]} | "
            f"Tokens: {input_tokens}+{output_tokens} | "
            f"Cost: ${cost:.4f}"
        )

        # Log running totals
        logger.info(
            f"[TOTAL] Requests: {self.request_count} | "
            f"Tokens: {self.total_input_tokens}+{self.total_output_tokens} | "
            f"Total Cost: ${self.total_cost_usd:.4f}"
        )

    def get_stats(self) -> dict:
        """Get current usage statistics."""
        return {
            "requests": self.request_count,
            "input_tokens": self.total_input_tokens,
            "output_tokens": self.total_output_tokens,
            "total_cost_usd": self.total_cost_usd,
        }


# Global usage tracker
usage_tracker = UsageTracker()


def calculate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    """Calculate cost in USD based on token usage."""
    pricing = PRICING.get(model, PRICING[MODEL_FAST])
    cost = ((input_tokens / 1e6) * pricing["input"]) + (
        (output_tokens / 1e6) * pricing["output"]
    )
    return cost


def track_usage(model: str, input_tokens: int, output_tokens: int, task: str) -> float:
    """Calculate cost and track usage in terminal."""
    cost = calculate_cost(model, input_tokens, output_tokens)
    usage_tracker.add_usage(model, input_tokens, output_tokens, cost, task)
    return cost


# ============================================
# DOCUMENT REVIEW (Full Review, Grammar, Summary)
# ============================================


async def review_document(
    doc_content: str, analysis_type: str
) -> Tuple[str, List[dict], float]:
    """
    Analyze document content based on analysis type.

    Args:
        doc_content: Full text content of the document
        analysis_type: One of 'full_review', 'grammar', 'summary'

    Returns:
        (analysis_text, pending_fixes, cost_usd)
        - pending_fixes is populated only for grammar type
    """
    # Select model based on task
    model = MODEL_FOR_TASK.get(analysis_type, MODEL_SMART)

    # Define prompts for each analysis type
    prompts = {
        "full_review": """You are a Professional Document Reviewer.
Analyze the document and provide a comprehensive review covering:

1. **Overall Quality**: Rate the document quality (Excellent/Good/Needs Improvement/Poor)
2. **Structure**: Is the document well-organized? Are sections logical?
3. **Content**: Is the content clear, accurate, and complete?
4. **Language**: Grammar, spelling, punctuation issues
5. **Specific Issues & Fixes**: List each issue found with exact text and correction

For each issue, clearly state:
- What's wrong (quote the exact problematic text)
- How to fix it (provide the corrected text)

At the END of your response, output a JSON array of all fixes in this format:
```json
[{"search": "exact wrong text from document", "replace": "corrected text"}, ...]
```

IMPORTANT RULES:
- The 'search' field must contain the EXACT text as it appears in the document (case-sensitive)
- Only include definite errors that need fixing
- The document may be in any language - analyze and fix in the document's language
- If no issues found, return empty array []""",
        "grammar": """You are a Professional Grammar Checker.
Analyze the document for:

1. Spelling errors
2. Grammar mistakes  
3. Punctuation issues
4. Word choice problems

For EACH issue found, provide in this EXACT format:
- Issue: [describe the problem]
- Location: [quote the problematic text]
- Suggestion: [how to fix it]

At the END of your response, output a JSON array of fixes in this format:
```json
[{"search": "exact wrong text", "replace": "corrected text"}, ...]
```

IMPORTANT:
- The 'search' field must contain the EXACT text as it appears in the document
- Only include definite errors, not style preferences
- The document may be in any language - respect the document's language
- If no issues found, return empty array []""",
        "summary": """You are a Professional Document Summarizer.
Provide a concise summary of the document including:

1. **Main Topic**: What is this document about?
2. **Key Points**: List 3-5 main points or arguments
3. **Conclusions**: What are the main takeaways?
4. **Target Audience**: Who is this document intended for?

Keep the summary clear and concise (around 200-300 words).
Summarize in the same language as the document.""",
    }

    system_prompt = prompts.get(analysis_type, prompts["full_review"])

    try:
        # Truncate content if too long
        truncated_content = doc_content[:MAX_CONTENT_CHARS]
        if len(doc_content) > MAX_CONTENT_CHARS:
            truncated_content += "\n\n[Document truncated for analysis...]"

        # Use timeout to prevent hanging on slow API responses
        async with asyncio.timeout(AI_REQUEST_TIMEOUT):
            response = await client.messages.create(
                model=model,
                max_tokens=AI_MAX_TOKENS,
                system=system_prompt,
                messages=[
                    {
                        "role": "user",
                        "content": f"Please analyze this document:\n\n{truncated_content}",
                    }
                ],
            )

        # Calculate cost and track usage
        usage = response.usage
        cost = track_usage(
            model, usage.input_tokens, usage.output_tokens, f"analyze:{analysis_type}"
        )

        # Extract response text
        result_text = response.content[0].text

        # DEBUG: Log full AI response for analysis
        logger.debug(
            f"[REVIEW] Full AI response ({len(result_text)} chars):\n{result_text}"
        )

        # For full_review and grammar, extract fixes JSON and clean up the display text
        pending_fixes = []
        display_text = result_text

        if analysis_type in ("full_review", "grammar"):
            logger.debug(f"[REVIEW] Extracting fixes from {analysis_type} response...")
            pending_fixes = _extract_fixes_from_response(result_text)
            # Remove JSON block from display text (user doesn't need to see it)
            display_text = _clean_grammar_response(result_text)

            if pending_fixes:
                logger.info(
                    f"Extracted {len(pending_fixes)} fixes from {analysis_type}"
                )
            else:
                logger.info(
                    f"[REVIEW] No fixes extracted from {analysis_type} (document may be clean)"
                )

        return display_text, pending_fixes, cost

    except asyncio.TimeoutError:
        logger.error(f"AI request timed out after {AI_REQUEST_TIMEOUT}s")
        return "Analysis timed out. Please try again with a smaller document.", [], 0
    except Exception as e:
        logger.error(f"Review Error: {e}")
        return f"Analysis failed: {str(e)}", [], 0


def _extract_fixes_from_response(response_text: str) -> List[dict]:
    """Extract JSON fixes array from grammar check response."""
    try:
        # Look for JSON block in response
        import re

        # DEBUG: Log the last 2000 chars of response to see the JSON part
        logger.debug(
            f"[EXTRACT] Response tail (last 2000 chars):\n{response_text[-2000:]}"
        )

        # Try to find JSON in code block
        json_match = re.search(r"```json\s*(.*?)\s*```", response_text, re.DOTALL)
        if json_match:
            json_str = json_match.group(1)
            logger.debug(f"[EXTRACT] Found JSON in code block, length: {len(json_str)}")
        else:
            # Try to find raw JSON array - use greedy match to get ALL items
            json_match = re.search(r"\[\s*\{.*\}\s*\]", response_text, re.DOTALL)
            if json_match:
                json_str = json_match.group(0)
                logger.debug(f"[EXTRACT] Found raw JSON array, length: {len(json_str)}")
            else:
                logger.warning("[EXTRACT] No JSON found in response!")
                return []

        # DEBUG: Log the extracted JSON string
        logger.debug(f"[EXTRACT] JSON string:\n{json_str[:1500]}")

        fixes = json.loads(json_str)
        logger.debug(f"[EXTRACT] Parsed {len(fixes)} items from JSON")

        # Validate structure
        if not isinstance(fixes, list):
            logger.warning(f"[EXTRACT] JSON is not a list, got: {type(fixes)}")
            return []

        # Filter valid fixes
        valid_fixes = []
        for i, fix in enumerate(fixes):
            if isinstance(fix, dict) and "search" in fix and "replace" in fix:
                if fix["search"] and fix["search"] != fix["replace"]:
                    valid_fixes.append(
                        {"search": str(fix["search"]), "replace": str(fix["replace"])}
                    )
                else:
                    logger.debug(f"[EXTRACT] Fix {i} skipped: empty or identical")
            else:
                logger.debug(f"[EXTRACT] Fix {i} skipped: invalid structure: {fix}")

        logger.info(
            f"[EXTRACT] Valid fixes: {len(valid_fixes)} out of {len(fixes)} parsed"
        )
        return valid_fixes

    except (json.JSONDecodeError, Exception) as e:
        logger.warning(f"Failed to extract fixes: {e}")
        logger.debug(
            f"[EXTRACT] JSON parse error on: {json_str[:500] if 'json_str' in dir() else 'N/A'}"
        )
        return []


def _clean_grammar_response(response_text: str) -> str:
    """
    Remove JSON block from grammar response for cleaner display to user.
    The JSON is for internal use, user only needs to see the analysis text.
    """
    import re

    # Remove ```json ... ``` blocks
    cleaned = re.sub(r"```json\s*.*?\s*```", "", response_text, flags=re.DOTALL)

    # Remove standalone JSON arrays at the end (in case not in code block)
    cleaned = re.sub(r"\[\s*\{[^]]*\}\s*\]\s*$", "", cleaned, flags=re.DOTALL)

    # Clean up extra whitespace/newlines at the end
    cleaned = cleaned.strip()

    # If everything was removed, return original
    if not cleaned:
        return response_text.strip()

    return cleaned


# ============================================
# AUTO-FIX GENERATION
# ============================================


async def generate_improvements(doc_content: str) -> Tuple[List[dict], float]:
    """
    Scan document and generate list of fixes.

    Args:
        doc_content: Full text content of the document

    Returns:
        (fixes_list, cost_usd)
        - fixes_list: List of {"search": str, "replace": str} dicts
    """
    model = MODEL_FOR_TASK.get("generate_fixes", MODEL_SMART)

    system_prompt = """You are a Professional Copy Editor.
Your job is to find and fix errors in documents.

Scan the document for:
1. Spelling errors and typos
2. Grammar mistakes
3. Punctuation errors
4. Inconsistent capitalization
5. Double spaces or formatting issues
6. Factual inconsistencies within the document (e.g., name spelled differently)

Output ONLY a JSON array of fixes:
[{"search": "exact wrong text", "replace": "correct text"}, ...]

CRITICAL RULES:
1. The 'search' string must be EXACTLY as it appears in the document (case-sensitive)
2. Only fix definite errors - do not change writing style
3. Each 'search' string should be unique enough to not accidentally match correct text
4. If the text around an error helps make it unique, include a few extra words
5. Do not include fixes where search and replace are identical
6. The document may be in any language - fix errors while respecting the document's language
7. Return empty array [] if no errors found
8. Return ONLY the JSON array, no other text"""

    try:
        # Truncate content if too long
        truncated_content = doc_content[:MAX_CONTENT_CHARS]

        # Use timeout to prevent hanging on slow API responses
        async with asyncio.timeout(AI_REQUEST_TIMEOUT):
            response = await client.messages.create(
                model=model,
                max_tokens=AI_MAX_TOKENS,
                system=system_prompt,
                messages=[
                    {
                        "role": "user",
                        "content": f"Find and fix errors in this document:\n\n{truncated_content}",
                    }
                ],
            )

        # Calculate cost and track usage
        usage = response.usage
        cost = track_usage(
            model, usage.input_tokens, usage.output_tokens, "generate_fixes"
        )

        # Parse response
        content = response.content[0].text.strip()

        # Clean up response - remove markdown code blocks if present
        content = content.replace("```json", "").replace("```", "").strip()

        try:
            fixes = json.loads(content)

            # Validate structure
            if not isinstance(fixes, list):
                logger.warning("AI returned non-list response")
                return [], cost

            # Filter and validate fixes
            valid_fixes = []
            for fix in fixes:
                if isinstance(fix, dict) and "search" in fix and "replace" in fix:
                    search = str(fix["search"]).strip()
                    replace = str(fix["replace"]).strip()

                    # Skip if empty or identical
                    if search and search != replace:
                        valid_fixes.append({"search": search, "replace": replace})

            logger.info(f"Generated {len(valid_fixes)} fixes")
            return valid_fixes, cost

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse fixes JSON: {e}")
            logger.debug(f"Raw content: {content[:500]}")
            return [], cost

    except asyncio.TimeoutError:
        logger.error(f"AI request timed out after {AI_REQUEST_TIMEOUT}s")
        return [], 0
    except Exception as e:
        logger.error(f"Generate Improvements Error: {e}")
        return [], 0
