"""
Doc Helper Configuration
All constants, model configs, pricing, and timeouts.
"""

import os
from dotenv import load_dotenv

load_dotenv()

# --- Bot Credentials ---
BOT_TOKEN = os.getenv("BOT_TOKEN")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")

# --- File Settings ---
MAX_FILE_SIZE_MB = 10
MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024
DOWNLOAD_DIR = "downloads"
SUPPORTED_EXTENSIONS = [".docx"]

# --- AI Models (Hybrid Strategy) ---
MODEL_FAST = "claude-3-haiku-20240307"
MODEL_SMART = "claude-sonnet-4-20250514"

# Model usage mapping per task
MODEL_FOR_TASK = {
    "grammar": MODEL_FAST,
    "full_review": MODEL_SMART,
    "summary": MODEL_SMART,
    "generate_fixes": MODEL_SMART,
}

# --- Pricing (USD per 1M tokens) ---
PRICING = {
    MODEL_FAST: {"input": 0.25, "output": 1.25},
    MODEL_SMART: {"input": 3.0, "output": 15.0},
}

# --- Timeouts (seconds) ---
SESSION_WARNING_SEC = 300  # 5 minutes - send warning
SESSION_EXPIRE_SEC = 420  # 7 minutes total - expire session
IDLE_TIMEOUT_SEC = 600  # 10 minutes - no file uploaded

# --- Content Limits ---
MAX_CONTENT_CHARS = 15000  # Max chars to send to AI (token safety)

# --- AI Settings ---
AI_MAX_TOKENS = 2500  # Max tokens for AI response
AI_REQUEST_TIMEOUT = 120  # Timeout for AI API calls (seconds)

# --- Messages ---
MESSAGES = {
    "welcome": (
        "Welcome to Doc Helper!\n\n"
        "I can help you edit and analyze your DOCX documents.\n\n"
        "Choose an option below or use commands:\n"
        "/restart - Restart the bot\n"
        "/help - Show usage guide"
    ),
    "help": (
        "Help Guide\n\n"
        "Features:\n"
        "- Find & Replace: Search and replace text in your document\n"
        "- Analyze: Get AI review with Grammar Check or Full Analyze\n\n"
        "Commands:\n"
        "/restart - Restart the bot at any time\n"
        "/cancel - Exit current operation\n\n"
        "Tips:\n"
        "- Only .docx files are supported\n"
        "- Max file size: 10MB\n"
        "- Your files are deleted after processing\n"
        "- Session expires after 5 minutes of inactivity"
    ),
    "ask_file": "Send me the DOCX file you want to {action}.\n\n(or /cancel to exit)",
    "file_received": "Received: {filename}",
    "no_file": "Please send a document file first.",
    "session_warning": "Session expiring in 2 minutes.\nClick below to continue or send a command.",
    "session_expired": "Session expired. File deleted.\n\nUse /restart to start again.",
    "cancelled": "Operation cancelled.\n\nUse /restart to start again.",
    "done": "Here is your document.\n\nSession complete. File deleted from server.",
    # Edit flow
    "edit_ask_find": "What text do you want to FIND?\n\n(Type the exact text to search for)",
    "edit_found_with_context": (
        'Found {count} occurrence(s) of "{text}":\n\n'
        "{contexts}\n\n"
        "What should I REPLACE it with?"
    ),
    "edit_not_found": 'Text "{text}" not found in the document.\n\nTry again with different text.',
    "edit_confirm": (
        "Confirm Replacement\n\n"
        "Find: `{find}`\n"
        "Replace: `{replace}`\n"
        "Occurrences: {count}"
    ),
    "replace_step_item": (
        'Replacement {current} of {total}:\n\n"{sentence}"\n\n`{find}` -> `{replace}`'
    ),
    "replace_complete": (
        "Replacement complete!\n\n"
        "Replaced: {applied} | Skipped: {skipped}\n\n"
        "What would you like to do next?"
    ),
    # Analyze flow
    "analyze_select": "Choose analysis type:",
    "analyze_processing": "Analyzing document...",
    "analyze_done": "{type} Analysis\n\n{result}",
    # Fix flow
    "fix_scanning": "Scanning document for issues...",
    "fix_found": "Found {count} issue(s):\n\n{issues}",
    "fix_no_issues": "No issues found. Your document looks good!",
    "fix_review_item": "Fix {current} of {total}:\n\n`{search}` -> `{replace}`",
    "fix_complete": (
        "Fixes complete!\n\n"
        "Applied: {applied} | Skipped: {skipped}\n\n"
        "What would you like to do next?"
    ),
    "analyze_no_actionable_fixes": (
        "Analysis found potential issues, but no actionable fixes could be extracted.\n"
        "The issues may require manual review, or the document may already be correct."
    ),
    # Cancel with discard
    "cancelled_discard": (
        "Operation cancelled. All changes discarded.\n\nWhat would you like to do?"
    ),
    # Common
    "use_buttons": "Please use the buttons above, or send /cancel to exit.",
    "download_failed": "Failed to download file. Please try again.",
    "unexpected_error": "An unexpected error occurred. Please try again.",
    "ai_timeout": "Analysis timed out. Please try again with a smaller document.",
}
