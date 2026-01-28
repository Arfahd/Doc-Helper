"""
Fix Handler - Fix flow with Fix All and Fix Step by Step options

New Flow:
- After fix scan: Fix All, Fix Step by Step, Cancel
- After fixes complete: Show [ Done ] [ Find & Replace ] [ Analyze ]
- Document only sent when Done is pressed
- Cancel during step-by-step: Discard all changes, return to main menu
"""

from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

from config import MESSAGES
from states import BotStates
from keyboards.inline import (
    fix_confirm_keyboard,
    fix_review_keyboard,
    post_action_keyboard,
    main_menu_keyboard,
)
from utils.session import session_manager
from tools.doc_tools import (
    read_docx_full_text,
    apply_multiple_fixes,
)
from agents.brain import generate_improvements
from handlers.analyze import format_fix_summary

router = Router()


async def start_fix_scan(message: Message, state: FSMContext, user_id: int):
    """
    Start scanning document for issues.
    Called after file upload in fix mode.

    Args:
        message: The Message object (user's file upload message)
        state: FSM context
        user_id: User ID
    """
    file_path = session_manager.get_file_path(user_id)
    if not file_path:
        await message.answer(MESSAGES["no_file"])
        await state.clear()
        return

    # Send scanning message
    msg = await message.answer(MESSAGES["fix_scanning"])

    # Read document
    doc_text = read_docx_full_text(file_path)
    if not doc_text:
        await msg.edit_text(
            "Failed to read document content.", reply_markup=post_action_keyboard()
        )
        await state.set_state(BotStates.file_active)
        return

    # Generate fixes using AI
    fixes, cost = await generate_improvements(doc_text)

    if not fixes:
        # No issues found - show post-action menu
        await msg.edit_text(
            MESSAGES["fix_no_issues"], reply_markup=post_action_keyboard()
        )
        await state.set_state(BotStates.file_active)
        return

    # Store fixes in session
    session_manager.update_session(
        user_id, pending_fixes=fixes, fix_index=0, applied_fixes=[], skipped_fixes=[]
    )

    # Format issues for display
    issues_text = "\n".join(
        [
            f"{i + 1}. `{fix['search']}` -> `{fix['replace']}`"
            for i, fix in enumerate(fixes[:10])
        ]
    )
    if len(fixes) > 10:
        issues_text += f"\n... and {len(fixes) - 10} more"

    text = MESSAGES["fix_found"].format(count=len(fixes), issues=issues_text)
    await msg.edit_text(text, reply_markup=fix_confirm_keyboard())
    await state.set_state(BotStates.fix_confirm)


@router.callback_query(F.data == "fix_apply_all", BotStates.fix_confirm)
async def apply_all_fixes(callback: CallbackQuery, state: FSMContext):
    """Apply all fixes at once. Document is NOT sent - just updated in session."""
    user_id = callback.from_user.id

    session = session_manager.get_session(user_id)
    if not session:
        await callback.message.edit_text(MESSAGES["no_file"])
        await state.clear()
        await callback.answer()
        return

    file_path = session.get("file_path")
    fixes = session.get("pending_fixes", [])

    if not fixes:
        await callback.message.edit_text(
            "No fixes to apply.", reply_markup=post_action_keyboard()
        )
        await state.set_state(BotStates.file_active)
        await callback.answer()
        return

    # Show processing
    await callback.message.edit_text(f"Applying {len(fixes)} fix(es)...")
    await callback.answer()

    # Apply all fixes
    result_path, applied, skipped, applied_list, skipped_list = apply_multiple_fixes(
        file_path, fixes
    )

    if not result_path:
        await callback.message.edit_text(
            "No fixes could be applied.", reply_markup=post_action_keyboard()
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


@router.callback_query(F.data == "fix_review_each", BotStates.fix_confirm)
async def start_review_each(callback: CallbackQuery, state: FSMContext):
    """Start reviewing fixes one by one."""
    user_id = callback.from_user.id

    session = session_manager.get_session(user_id)
    if not session:
        await callback.message.edit_text(MESSAGES["no_file"])
        await state.clear()
        await callback.answer()
        return

    fixes = session.get("pending_fixes", [])
    if not fixes:
        await callback.message.edit_text(
            "No fixes to review.", reply_markup=post_action_keyboard()
        )
        await state.set_state(BotStates.file_active)
        await callback.answer()
        return

    # Reset review state
    session_manager.update_session(
        user_id, fix_index=0, applied_fixes=[], skipped_fixes=[]
    )

    # Show first fix
    fix = fixes[0]
    await callback.message.edit_text(
        MESSAGES["fix_review_item"].format(
            current=1, total=len(fixes), search=fix["search"], replace=fix["replace"]
        ),
        reply_markup=fix_review_keyboard(),
    )

    await state.set_state(BotStates.fix_review)
    await callback.answer()


@router.callback_query(F.data == "fix_item_apply", BotStates.fix_review)
async def apply_single_fix(callback: CallbackQuery, state: FSMContext):
    """Apply current fix and move to next."""
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

    fixes = session.get("pending_fixes", [])
    index = session.get("fix_index", 0)
    applied = session.get("applied_fixes", [])

    if index >= len(fixes):
        await finish_review(callback, state, user_id)
        return

    # Mark as applied
    applied.append(fixes[index])
    session_manager.update_session(user_id, applied_fixes=applied, fix_index=index + 1)

    # Move to next or finish
    await show_next_fix_or_finish(callback, state, user_id)


@router.callback_query(F.data == "fix_item_skip", BotStates.fix_review)
async def skip_single_fix(callback: CallbackQuery, state: FSMContext):
    """Skip current fix and move to next."""
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

    fixes = session.get("pending_fixes", [])
    index = session.get("fix_index", 0)
    skipped = session.get("skipped_fixes", [])

    if index >= len(fixes):
        await finish_review(callback, state, user_id)
        return

    # Mark as skipped
    skipped.append(fixes[index])
    session_manager.update_session(user_id, skipped_fixes=skipped, fix_index=index + 1)

    # Move to next or finish
    await show_next_fix_or_finish(callback, state, user_id)


async def show_next_fix_or_finish(
    callback: CallbackQuery, state: FSMContext, user_id: int
):
    """Show next fix or finish if all reviewed."""
    session = session_manager.get_session(user_id)
    if not session:
        return

    fixes = session.get("pending_fixes", [])
    index = session.get("fix_index", 0)

    if index >= len(fixes):
        await finish_review(callback, state, user_id)
    else:
        fix = fixes[index]
        try:
            await callback.message.edit_text(
                MESSAGES["fix_review_item"].format(
                    current=index + 1,
                    total=len(fixes),
                    search=fix["search"],
                    replace=fix["replace"],
                ),
                reply_markup=fix_review_keyboard(),
            )
        except Exception:
            pass


async def finish_review(callback: CallbackQuery, state: FSMContext, user_id: int):
    """Finish review process and apply selected fixes. Document NOT sent yet."""
    session = session_manager.get_session(user_id)
    file_path = session.get("file_path")
    applied_fixes = session.get("applied_fixes", [])
    skipped_fixes = session.get("skipped_fixes", [])

    if not applied_fixes:
        # Nothing to apply - show post-action with unchanged document
        await callback.message.edit_text(
            MESSAGES["fix_complete"].format(applied=0, skipped=len(skipped_fixes)),
            reply_markup=post_action_keyboard(),
        )
        await state.set_state(BotStates.file_active)
        return

    # Apply selected fixes
    await callback.message.edit_text(f"Applying {len(applied_fixes)} fix(es)...")

    result_path, applied, not_found, applied_list, not_found_list = (
        apply_multiple_fixes(file_path, applied_fixes)
    )

    if not result_path:
        await callback.message.edit_text(
            "Failed to apply fixes.", reply_markup=post_action_keyboard()
        )
        await state.set_state(BotStates.file_active)
        return

    # Update session with new file (keep session alive!)
    session_manager.update_file(user_id, result_path)
    session_manager.update_session(
        user_id, pending_fixes=[], applied_fixes=[], skipped_fixes=[]
    )

    # Build summary
    fix_summary = format_fix_summary(applied_list, not_found_list)
    user_skipped_count = len(skipped_fixes)

    summary_msg = MESSAGES["fix_complete"].format(
        applied=applied, skipped=not_found + user_skipped_count
    )
    if fix_summary:
        summary_msg += f"\n\n{fix_summary}"
    if user_skipped_count > 0:
        summary_msg += f"\n\n*User Skipped: {user_skipped_count}*"

    # Show completion with post-action menu (NO document sent yet)
    await callback.message.edit_text(summary_msg, reply_markup=post_action_keyboard())

    await state.set_state(BotStates.file_active)


@router.callback_query(F.data == "fix_cancel_all", BotStates.fix_review)
async def cancel_all_fixes(callback: CallbackQuery, state: FSMContext):
    """Cancel step-by-step review - discard all changes and return to main menu."""
    user_id = callback.from_user.id

    # Clear state and session (discard all)
    await state.clear()
    session_manager.cleanup_session(user_id)

    await callback.message.edit_text(
        MESSAGES["cancelled_discard"],
        reply_markup=main_menu_keyboard(),
    )
    await callback.answer()
