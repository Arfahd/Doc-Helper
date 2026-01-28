"""
Inline Keyboard Builders for Enterprise Doc Bot
All button layouts for the bot interactions.
"""

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder


def main_menu_keyboard() -> InlineKeyboardMarkup:
    """Main menu with Find & Replace, Analyze, Help buttons."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="Find & Replace", callback_data="menu_edit"),
    )
    builder.row(
        InlineKeyboardButton(text="Analyze", callback_data="menu_analyze"),
        InlineKeyboardButton(text="Help", callback_data="menu_help"),
    )
    return builder.as_markup()


def analysis_type_keyboard() -> InlineKeyboardMarkup:
    """Analysis type selection: Grammar Check, Full Analyze."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="Grammar Check", callback_data="analyze_grammar"),
    )
    builder.row(
        InlineKeyboardButton(text="Full Analyze", callback_data="analyze_full_review"),
    )
    builder.row(
        InlineKeyboardButton(text="Cancel", callback_data="cancel"),
    )
    return builder.as_markup()


def confirm_replace_keyboard() -> InlineKeyboardMarkup:
    """Confirmation for text replacement: Replace All, Replace Step by Step, Cancel."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="Replace All", callback_data="confirm_replace"),
    )
    builder.row(
        InlineKeyboardButton(
            text="Replace Step by Step", callback_data="replace_step_by_step"
        ),
    )
    builder.row(
        InlineKeyboardButton(text="Cancel", callback_data="cancel_replace"),
    )
    return builder.as_markup()


def replace_step_keyboard() -> InlineKeyboardMarkup:
    """Review individual replacement: Replace, Skip, Cancel All."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="Replace", callback_data="replace_item_apply"),
        InlineKeyboardButton(text="Skip", callback_data="replace_item_skip"),
    )
    builder.row(
        InlineKeyboardButton(text="Cancel All", callback_data="replace_cancel_all"),
    )
    return builder.as_markup()


def post_action_keyboard() -> InlineKeyboardMarkup:
    """After replace/fix complete: Done, Find & Replace, Analyze."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="Done", callback_data="done"),
    )
    builder.row(
        InlineKeyboardButton(text="Find & Replace", callback_data="post_find_replace"),
        InlineKeyboardButton(text="Analyze", callback_data="post_analyze"),
    )
    return builder.as_markup()


def post_analyze_keyboard(has_fixes: bool = False) -> InlineKeyboardMarkup:
    """
    After analyze complete (Full Analyze / Grammar Check):
    - If fixes found: Fix All, Fix Step by Step, Cancel
    - If no fixes: Show post-action menu
    """
    builder = InlineKeyboardBuilder()

    if has_fixes:
        # Fixes found - show fix options
        builder.row(
            InlineKeyboardButton(text="Fix All", callback_data="analyze_fix_all"),
        )
        builder.row(
            InlineKeyboardButton(
                text="Fix Step by Step", callback_data="analyze_fix_step"
            ),
        )
        builder.row(
            InlineKeyboardButton(text="Cancel", callback_data="cancel"),
        )
    else:
        # No fixes found - show post-action menu
        builder.row(
            InlineKeyboardButton(text="Done", callback_data="done"),
        )
        builder.row(
            InlineKeyboardButton(
                text="Find & Replace", callback_data="post_find_replace"
            ),
            InlineKeyboardButton(text="Analyze", callback_data="post_analyze"),
        )

    return builder.as_markup()


def fix_confirm_keyboard() -> InlineKeyboardMarkup:
    """Confirmation for applying fixes: Fix All, Review Each, Cancel."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="Fix All", callback_data="fix_apply_all"),
    )
    builder.row(
        InlineKeyboardButton(text="Fix Step by Step", callback_data="fix_review_each"),
    )
    builder.row(
        InlineKeyboardButton(text="Cancel", callback_data="cancel"),
    )
    return builder.as_markup()


def fix_review_keyboard() -> InlineKeyboardMarkup:
    """Review individual fix: Apply, Skip, Cancel All."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="Apply", callback_data="fix_item_apply"),
        InlineKeyboardButton(text="Skip", callback_data="fix_item_skip"),
    )
    builder.row(
        InlineKeyboardButton(text="Cancel All", callback_data="fix_cancel_all"),
    )
    return builder.as_markup()


def keep_session_keyboard() -> InlineKeyboardMarkup:
    """Session timeout warning: Keep Session button."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="Keep Session", callback_data="keep_session"),
    )
    return builder.as_markup()


def cancel_keyboard() -> InlineKeyboardMarkup:
    """Simple cancel button."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="Cancel", callback_data="cancel"),
    )
    return builder.as_markup()


def try_again_keyboard() -> InlineKeyboardMarkup:
    """When find text not found - try again or cancel."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="Try Again", callback_data="edit_retry"),
        InlineKeyboardButton(text="Cancel", callback_data="cancel"),
    )
    return builder.as_markup()
