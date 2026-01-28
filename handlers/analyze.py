"""
Analyze Handler - /analyze flow with Grammar Check and Full Analyze

New Flow:
- Grammar Check / Full Analyze: Shows analysis + fixes
- If fixes found: Fix All, Fix Step by Step, Cancel
- If no fixes: Show post-action menu
- After fixes complete: Show [ Done ] [ Find & Replace ] [ Analyze ]
- Document only sent when Done is pressed
"""

from typing import List
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

from config import MESSAGES
from states import BotStates
from keyboards.inline import (
    analysis_type_keyboard,
    post_analyze_keyboard,
    post_action_keyboard,
    main_menu_keyboard,
    fix_review_keyboard,
)
from utils.session import session_manager
from tools.doc_tools import read_docx_full_text, apply_multiple_fixes
from agents.brain import review_document

router = Router()


def format_fix_summary(
    applied_list: List[dict], skipped_list: List[dict], max_items: int = 5
) -> str:
    """
    Format a summary of applied and skipped fixes for display to user.

    Args:
        applied_list: List of fixes that were applied
        skipped_list: List of fixes that were skipped
        max_items: Max items to show per category

    Returns:
        Formatted string
    """
    lines = []

    # Applied fixes
    if applied_list:
        lines.append(f"*Applied ({len(applied_list)}):*")
        for i, fix in enumerate(applied_list[:max_items]):
            search = fix.get("search", "")[:40]
            replace = fix.get("replace", "")[:40]
            lines.append(f"  {i + 1}. `{search}` -> `{replace}`")
        if len(applied_list) > max_items:
            lines.append(f"  ... and {len(applied_list) - max_items} more")

    # Skipped fixes
    if skipped_list:
        lines.append(f"\n*Skipped ({len(skipped_list)}):*")
        for i, fix in enumerate(skipped_list[:max_items]):
            search = fix.get("search", "")[:40]
            lines.append(f"  {i + 1}. `{search}` (not found)")
        if len(skipped_list) > max_items:
            lines.append(f"  ... and {len(skipped_list) - max_items} more")

    return "\n".join(lines)


# ============================================
# ANALYSIS TYPE SELECTION
# ============================================


@router.callback_query(F.data == "analyze_full_review")
async def analyze_full_review(callback: CallbackQuery, state: FSMContext):
    """Run full document review analysis."""
    await run_analysis(callback, state, "full_review")


@router.callback_query(F.data == "analyze_grammar")
async def analyze_grammar(callback: CallbackQuery, state: FSMContext):
    """Run grammar check analysis."""
    await run_analysis(callback, state, "grammar")


async def run_analysis(callback: CallbackQuery, state: FSMContext, analysis_type: str):
    """
    Run AI analysis on the document.

    Args:
        callback: The callback query
        state: FSM context
        analysis_type: One of 'full_review', 'grammar'
    """
    user_id = callback.from_user.id

    # Get file path
    file_path = session_manager.get_file_path(user_id)
    if not file_path:
        await callback.message.edit_text(MESSAGES["no_file"])
        await state.clear()
        await callback.answer()
        return

    # Show processing message
    await callback.message.edit_text(MESSAGES["analyze_processing"])
    await callback.answer()

    # Read document text
    doc_text = read_docx_full_text(file_path)
    if not doc_text:
        await callback.message.edit_text(
            "Failed to read document content.", reply_markup=post_action_keyboard()
        )
        await state.set_state(BotStates.file_active)
        return

    # Run AI analysis
    result, pending_fixes, cost = await review_document(doc_text, analysis_type)

    # Store pending fixes if any
    if pending_fixes:
        session_manager.update_session(user_id, pending_fixes=pending_fixes)
    else:
        session_manager.update_session(user_id, pending_fixes=[])

    # Format type name for display
    type_names = {
        "full_review": "Full Analyze",
        "grammar": "Grammar Check",
    }
    type_display = type_names.get(analysis_type, analysis_type)

    # Choose keyboard and message based on whether fixes are available
    if pending_fixes:
        keyboard = post_analyze_keyboard(has_fixes=True)
        result_message = MESSAGES["analyze_done"].format(
            type=type_display,
            result=result[:3500],  # Truncate if too long
        )
    else:
        keyboard = post_analyze_keyboard(has_fixes=False)
        result_message = (
            MESSAGES["analyze_done"].format(
                type=type_display,
                result=result[:3500],  # Truncate if too long
            )
            + "\n\n---\n\n"
            + MESSAGES["analyze_no_actionable_fixes"]
        )

    # Send result
    await callback.message.edit_text(result_message, reply_markup=keyboard)

    await state.set_state(BotStates.file_active)


# ============================================
# FIX ALL FROM ANALYSIS
# ============================================


@router.callback_query(F.data == "analyze_fix_all")
async def analyze_fix_all(callback: CallbackQuery, state: FSMContext):
    """
    Apply all pending fixes from analysis automatically.
    Document is NOT sent - just updated in session.
    """
    user_id = callback.from_user.id

    # Get session data
    session = session_manager.get_session(user_id)
    if not session:
        await callback.message.edit_text(MESSAGES["no_file"])
        await state.clear()
        await callback.answer()
        return

    file_path = session.get("file_path")
    pending_fixes = session.get("pending_fixes", [])

    if not file_path:
        await callback.message.edit_text(MESSAGES["no_file"])
        await state.clear()
        await callback.answer()
        return

    if not pending_fixes:
        await callback.message.edit_text(
            "No fixes to apply.", reply_markup=post_action_keyboard()
        )
        await state.set_state(BotStates.file_active)
        await callback.answer()
        return

    # Show processing
    await callback.message.edit_text(f"Applying {len(pending_fixes)} fix(es)...")
    await callback.answer()

    # Apply all fixes
    result_path, applied, skipped, applied_list, skipped_list = apply_multiple_fixes(
        file_path, pending_fixes
    )

    if not result_path:
        await callback.message.edit_text(
            "No fixes could be applied. Text may have changed.",
            reply_markup=post_action_keyboard(),
        )
        await state.set_state(BotStates.file_active)
        return

    # Update session with new file (keep session alive!)
    session_manager.update_file(user_id, result_path)
    session_manager.update_session(user_id, pending_fixes=[])

    # Format fix summary
    fix_summary = format_fix_summary(applied_list, skipped_list)

    # Show completion with post-action menu (NO document sent yet)
    await callback.message.edit_text(
        MESSAGES["fix_complete"].format(applied=applied, skipped=skipped)
        + f"\n\n{fix_summary}",
        reply_markup=post_action_keyboard(),
    )

    await state.set_state(BotStates.file_active)


# ============================================
# FIX STEP BY STEP FROM ANALYSIS
# ============================================


@router.callback_query(F.data == "analyze_fix_step")
async def analyze_fix_step(callback: CallbackQuery, state: FSMContext):
    """
    Start reviewing fixes one by one from analysis.
    """
    await callback.answer()

    user_id = callback.from_user.id

    session = session_manager.get_session(user_id)
    if not session:
        try:
            await callback.message.edit_text(MESSAGES["no_file"])
        except Exception:
            pass
        await state.clear()
        return

    pending_fixes = session.get("pending_fixes", [])
    if not pending_fixes:
        try:
            await callback.message.edit_text(
                "No fixes to review.", reply_markup=post_action_keyboard()
            )
        except Exception:
            pass
        await state.set_state(BotStates.file_active)
        return

    # Reset review state
    session_manager.update_session(
        user_id, fix_index=0, applied_fixes=[], skipped_fixes=[]
    )

    # Show first fix
    fix = pending_fixes[0]
    try:
        await callback.message.edit_text(
            MESSAGES["fix_review_item"].format(
                current=1,
                total=len(pending_fixes),
                search=fix["search"],
                replace=fix["replace"],
            ),
            reply_markup=fix_review_keyboard(),
        )
    except Exception:
        pass

    await state.set_state(BotStates.fix_review)
