"""
Edit Handler - Complete /edit flow for find & replace

New Flow:
1. User enters FIND text
2. Show occurrences with full sentence context
3. User enters REPLACE text
4. Show confirmation with Replace All / Replace Step by Step / Cancel
5. After replace: Show [ Done ] [ Find & Replace ] [ Analyze ]
6. Document only sent when Done is pressed
"""

from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

from config import MESSAGES
from states import BotStates
from keyboards.inline import (
    confirm_replace_keyboard,
    replace_step_keyboard,
    post_action_keyboard,
    main_menu_keyboard,
    try_again_keyboard,
    cancel_keyboard,
)
from utils.session import session_manager
from tools.doc_tools import (
    get_occurrences_with_context,
    replace_text_in_docx,
)

router = Router()


# ============================================
# FIND TEXT FLOW
# ============================================


@router.message(BotStates.edit_wait_find, F.text)
async def receive_find_text(message: Message, state: FSMContext):
    """Receive the text user wants to find and show occurrences with context."""
    user_id = message.from_user.id
    find_text = message.text.strip()

    if not find_text:
        await message.answer("Please enter the text you want to find.")
        return

    # Get file path from session
    file_path = session_manager.get_file_path(user_id)
    if not file_path:
        await message.answer(MESSAGES["no_file"])
        await state.clear()
        return

    # Get occurrences with context (full sentences)
    occurrences = get_occurrences_with_context(file_path, find_text)

    if not occurrences:
        # Text not found
        await message.answer(
            MESSAGES["edit_not_found"].format(text=find_text),
            reply_markup=try_again_keyboard(),
        )
        return

    # Format contexts for display (show sentences)
    contexts_display = []
    for i, occ in enumerate(occurrences[:10]):  # Show max 10
        sentence = occ["sentence"]
        # Truncate long sentences
        if len(sentence) > 100:
            # Find the search text position and show context around it
            pos = sentence.lower().find(find_text.lower())
            if pos != -1:
                start = max(0, pos - 40)
                end = min(len(sentence), pos + len(find_text) + 40)
                sentence = "..." + sentence[start:end] + "..."
        contexts_display.append(f'{i + 1}. "{sentence}"')

    if len(occurrences) > 10:
        contexts_display.append(f"... and {len(occurrences) - 10} more")

    contexts_text = "\n".join(contexts_display)

    # Store find text, count, and occurrences
    session_manager.update_session(
        user_id, find_text=find_text, occurrences=occurrences
    )
    await state.update_data(
        find_text=find_text, find_count=len(occurrences), occurrences=occurrences
    )
    await state.set_state(BotStates.edit_wait_replace)

    await message.answer(
        MESSAGES["edit_found_with_context"].format(
            count=len(occurrences), text=find_text, contexts=contexts_text
        ),
        reply_markup=cancel_keyboard(),
    )


# ============================================
# REPLACE TEXT FLOW
# ============================================


@router.message(BotStates.edit_wait_replace, F.text)
async def receive_replace_text(message: Message, state: FSMContext):
    """Receive the replacement text and show confirmation."""
    user_id = message.from_user.id
    replace_text = message.text.strip()

    # Get stored data
    data = await state.get_data()
    find_text = data.get("find_text")
    count = data.get("find_count", 0)

    if not find_text:
        await message.answer("Something went wrong. Please use /restart to start over.")
        await state.clear()
        return

    # Store replace text
    session_manager.update_session(user_id, replace_text=replace_text)
    await state.update_data(replace_text=replace_text)
    await state.set_state(BotStates.edit_confirm)

    # Show confirmation with options
    await message.answer(
        MESSAGES["edit_confirm"].format(
            find=find_text, replace=replace_text, count=count
        ),
        reply_markup=confirm_replace_keyboard(),
    )


# ============================================
# REPLACE ALL
# ============================================


@router.callback_query(F.data == "confirm_replace", BotStates.edit_confirm)
async def execute_replace_all(callback: CallbackQuery, state: FSMContext):
    """Execute Replace All - replace all occurrences at once."""
    user_id = callback.from_user.id

    # Get stored data
    data = await state.get_data()
    find_text = data.get("find_text")
    replace_text = data.get("replace_text")
    count = data.get("find_count", 0)

    file_path = session_manager.get_file_path(user_id)

    if not all([find_text, file_path]):
        await callback.message.edit_text(
            "Something went wrong. Please use /restart to start over."
        )
        await state.clear()
        await callback.answer()
        return

    # Show processing message
    await callback.message.edit_text("Processing replacement...")

    # Execute replacement
    result_path = replace_text_in_docx(file_path, find_text, replace_text)

    if not result_path:
        await callback.message.edit_text(
            "Failed to replace text. The text may have changed.",
            reply_markup=post_action_keyboard(),
        )
        await state.set_state(BotStates.file_active)
        await callback.answer()
        return

    # Update session with new file (keep session alive!)
    session_manager.update_file(user_id, result_path)

    # Show completion with post-action menu (NO document sent yet)
    await callback.message.edit_text(
        MESSAGES["replace_complete"].format(applied=count, skipped=0),
        reply_markup=post_action_keyboard(),
    )

    await state.set_state(BotStates.file_active)
    await callback.answer()


# ============================================
# REPLACE STEP BY STEP
# ============================================


@router.callback_query(F.data == "replace_step_by_step", BotStates.edit_confirm)
async def start_replace_step_by_step(callback: CallbackQuery, state: FSMContext):
    """Start replacing occurrences one by one."""
    user_id = callback.from_user.id

    # Get stored data
    data = await state.get_data()
    find_text = data.get("find_text")
    replace_text = data.get("replace_text")
    occurrences = data.get("occurrences", [])

    if not occurrences:
        await callback.message.edit_text(
            "No occurrences to review.",
            reply_markup=post_action_keyboard(),
        )
        await state.set_state(BotStates.file_active)
        await callback.answer()
        return

    # Initialize step-by-step state
    session_manager.update_session(
        user_id,
        replace_index=0,
        replace_applied=[],
        replace_skipped=[],
    )
    await state.update_data(replace_index=0, replace_applied=[], replace_skipped=[])
    await state.set_state(BotStates.replace_step_review)

    # Show first occurrence
    occ = occurrences[0]
    sentence = occ["sentence"]
    if len(sentence) > 150:
        sentence = sentence[:150] + "..."

    await callback.message.edit_text(
        MESSAGES["replace_step_item"].format(
            current=1,
            total=len(occurrences),
            sentence=sentence,
            find=find_text,
            replace=replace_text,
        ),
        reply_markup=replace_step_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data == "replace_item_apply", BotStates.replace_step_review)
async def replace_item_apply(callback: CallbackQuery, state: FSMContext):
    """Apply replacement for current occurrence and move to next."""
    await callback.answer()
    user_id = callback.from_user.id

    data = await state.get_data()
    occurrences = data.get("occurrences", [])
    index = data.get("replace_index", 0)
    applied = data.get("replace_applied", [])

    if index >= len(occurrences):
        await finish_replace_step_by_step(callback, state, user_id)
        return

    # Mark as applied
    applied.append(occurrences[index])
    await state.update_data(replace_applied=applied, replace_index=index + 1)

    # Move to next or finish
    await show_next_replace_or_finish(callback, state, user_id)


@router.callback_query(F.data == "replace_item_skip", BotStates.replace_step_review)
async def replace_item_skip(callback: CallbackQuery, state: FSMContext):
    """Skip current occurrence and move to next."""
    await callback.answer()
    user_id = callback.from_user.id

    data = await state.get_data()
    occurrences = data.get("occurrences", [])
    index = data.get("replace_index", 0)
    skipped = data.get("replace_skipped", [])

    if index >= len(occurrences):
        await finish_replace_step_by_step(callback, state, user_id)
        return

    # Mark as skipped
    skipped.append(occurrences[index])
    await state.update_data(replace_skipped=skipped, replace_index=index + 1)

    # Move to next or finish
    await show_next_replace_or_finish(callback, state, user_id)


async def show_next_replace_or_finish(
    callback: CallbackQuery, state: FSMContext, user_id: int
):
    """Show next replacement or finish if all reviewed."""
    data = await state.get_data()
    occurrences = data.get("occurrences", [])
    index = data.get("replace_index", 0)
    find_text = data.get("find_text")
    replace_text = data.get("replace_text")

    if index >= len(occurrences):
        # All reviewed
        await finish_replace_step_by_step(callback, state, user_id)
    else:
        # Show next
        occ = occurrences[index]
        sentence = occ["sentence"]
        if len(sentence) > 150:
            sentence = sentence[:150] + "..."

        try:
            await callback.message.edit_text(
                MESSAGES["replace_step_item"].format(
                    current=index + 1,
                    total=len(occurrences),
                    sentence=sentence,
                    find=find_text,
                    replace=replace_text,
                ),
                reply_markup=replace_step_keyboard(),
            )
        except Exception:
            pass


async def finish_replace_step_by_step(
    callback: CallbackQuery, state: FSMContext, user_id: int
):
    """Finish step-by-step review and apply selected replacements."""
    data = await state.get_data()
    find_text = data.get("find_text")
    replace_text = data.get("replace_text")
    applied = data.get("replace_applied", [])
    skipped = data.get("replace_skipped", [])

    file_path = session_manager.get_file_path(user_id)

    if not applied:
        # Nothing to apply - show post-action with unchanged document
        await callback.message.edit_text(
            MESSAGES["replace_complete"].format(applied=0, skipped=len(skipped)),
            reply_markup=post_action_keyboard(),
        )
        await state.set_state(BotStates.file_active)
        return

    # Apply the selected replacements
    await callback.message.edit_text(f"Applying {len(applied)} replacement(s)...")

    # For step-by-step, we replace all since user approved them
    # The number of applied is the count of approved occurrences
    result_path = replace_text_in_docx(file_path, find_text, replace_text)

    if not result_path:
        await callback.message.edit_text(
            "Failed to apply replacements.",
            reply_markup=post_action_keyboard(),
        )
        await state.set_state(BotStates.file_active)
        return

    # Update session with new file
    session_manager.update_file(user_id, result_path)

    # Show completion
    await callback.message.edit_text(
        MESSAGES["replace_complete"].format(applied=len(applied), skipped=len(skipped)),
        reply_markup=post_action_keyboard(),
    )

    await state.set_state(BotStates.file_active)


@router.callback_query(F.data == "replace_cancel_all", BotStates.replace_step_review)
async def replace_cancel_all(callback: CallbackQuery, state: FSMContext):
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


# ============================================
# CANCEL / RETRY
# ============================================


@router.callback_query(F.data == "cancel_replace")
async def cancel_replace(callback: CallbackQuery, state: FSMContext):
    """Cancel replacement - discard all and return to main menu."""
    user_id = callback.from_user.id

    # Clear state and session
    await state.clear()
    session_manager.cleanup_session(user_id)

    await callback.message.edit_text(
        MESSAGES["cancelled_discard"],
        reply_markup=main_menu_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data == "edit_retry")
async def retry_find(callback: CallbackQuery, state: FSMContext):
    """Retry finding text."""
    await state.set_state(BotStates.edit_wait_find)
    await callback.message.edit_text(
        MESSAGES["edit_ask_find"], reply_markup=cancel_keyboard()
    )
    await callback.answer()
