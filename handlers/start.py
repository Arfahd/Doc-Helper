"""
Start Handler - /start command and main menu navigation

Includes:
- /start, /restart commands
- Main menu button callbacks
- Post-action transition callbacks (Find & Replace, Analyze after operations)
"""

from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext

from config import MESSAGES
from states import BotStates
from keyboards.inline import (
    main_menu_keyboard,
    analysis_type_keyboard,
    cancel_keyboard,
)
from utils.session import session_manager

router = Router()


# ============================================
# COMMANDS
# ============================================


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    """Handle /start command - show welcome and main menu."""
    user_id = message.from_user.id

    # Clear any existing state
    await state.clear()

    # Cleanup any existing session
    if session_manager.is_session_active(user_id):
        session_manager.cleanup_session(user_id)

    await message.answer(MESSAGES["welcome"], reply_markup=main_menu_keyboard())


@router.message(Command("restart"))
async def cmd_restart(message: Message, state: FSMContext):
    """Handle /restart command - reset and show main menu."""
    user_id = message.from_user.id

    # Clear any existing state
    await state.clear()

    # Cleanup any existing session
    if session_manager.is_session_active(user_id):
        session_manager.cleanup_session(user_id)

    await message.answer(MESSAGES["welcome"], reply_markup=main_menu_keyboard())


# ============================================
# MAIN MENU BUTTON CALLBACKS
# ============================================


@router.callback_query(F.data == "menu_edit")
async def menu_edit_callback(callback: CallbackQuery, state: FSMContext, bot: Bot):
    """Handle Find & Replace button from main menu."""
    user_id = callback.from_user.id

    # Create new session
    session_manager.create_session(user_id, mode="edit")
    session_manager.set_chat_id(user_id, callback.message.chat.id)

    # Set state to wait for file
    await state.set_state(BotStates.wait_for_file)
    await state.update_data(mode="edit")

    # Handle document message (can't edit_text on document messages)
    if callback.message.document:
        await callback.message.edit_reply_markup(reply_markup=None)
        await bot.send_message(
            chat_id=callback.message.chat.id,
            text=MESSAGES["ask_file"].format(action="edit"),
        )
    else:
        await callback.message.edit_text(MESSAGES["ask_file"].format(action="edit"))

    await callback.answer()


@router.callback_query(F.data == "menu_analyze")
async def menu_analyze_callback(callback: CallbackQuery, state: FSMContext, bot: Bot):
    """Handle Analyze button from main menu."""
    user_id = callback.from_user.id

    # Create new session
    session_manager.create_session(user_id, mode="analyze")
    session_manager.set_chat_id(user_id, callback.message.chat.id)

    # Set state to wait for file
    await state.set_state(BotStates.wait_for_file)
    await state.update_data(mode="analyze")

    # Handle document message
    if callback.message.document:
        await callback.message.edit_reply_markup(reply_markup=None)
        await bot.send_message(
            chat_id=callback.message.chat.id,
            text=MESSAGES["ask_file"].format(action="analyze"),
        )
    else:
        await callback.message.edit_text(MESSAGES["ask_file"].format(action="analyze"))

    await callback.answer()


@router.callback_query(F.data == "menu_help")
async def menu_help_callback(callback: CallbackQuery, state: FSMContext, bot: Bot):
    """Handle Help button from main menu."""
    # Handle document message
    if callback.message.document:
        await callback.message.edit_reply_markup(reply_markup=None)
        await bot.send_message(
            chat_id=callback.message.chat.id,
            text=MESSAGES["help"],
            reply_markup=main_menu_keyboard(),
        )
    else:
        await callback.message.edit_text(
            MESSAGES["help"], reply_markup=main_menu_keyboard()
        )
    await callback.answer()


@router.callback_query(F.data == "back_to_menu")
async def back_to_menu_callback(callback: CallbackQuery, state: FSMContext, bot: Bot):
    """Handle Back to Menu button - return to main menu."""
    user_id = callback.from_user.id

    # Clear any existing state
    await state.clear()

    # Cleanup any existing session
    if session_manager.is_session_active(user_id):
        session_manager.cleanup_session(user_id)

    # Handle document message
    if callback.message.document:
        await callback.message.edit_reply_markup(reply_markup=None)
        await bot.send_message(
            chat_id=callback.message.chat.id,
            text=MESSAGES["welcome"],
            reply_markup=main_menu_keyboard(),
        )
    else:
        await callback.message.edit_text(
            MESSAGES["welcome"], reply_markup=main_menu_keyboard()
        )
    await callback.answer()


# ============================================
# POST-ACTION TRANSITION CALLBACKS
# These are called from post_action_keyboard after replace/fix completes
# ============================================


@router.callback_query(F.data == "post_find_replace")
async def post_find_replace_callback(
    callback: CallbackQuery, state: FSMContext, bot: Bot
):
    """
    Transition to Find & Replace flow with existing document.
    Called from post-action menu after replace/fix completes.
    """
    user_id = callback.from_user.id

    # Check if we have a file in session
    if not session_manager.has_file(user_id):
        # No file - need to upload one
        session_manager.create_session(user_id, mode="edit")
        session_manager.set_chat_id(user_id, callback.message.chat.id)
        await state.set_state(BotStates.wait_for_file)
        await state.update_data(mode="edit")

        if callback.message.document:
            await callback.message.edit_reply_markup(reply_markup=None)
            await bot.send_message(
                chat_id=callback.message.chat.id,
                text=MESSAGES["ask_file"].format(action="edit"),
            )
        else:
            await callback.message.edit_text(MESSAGES["ask_file"].format(action="edit"))
        await callback.answer()
        return

    # We have a file - go directly to Find text input
    session_manager.update_session(user_id, mode="edit")
    await state.set_state(BotStates.edit_wait_find)

    # Handle document message
    if callback.message.document:
        await callback.message.edit_reply_markup(reply_markup=None)
        await bot.send_message(
            chat_id=callback.message.chat.id,
            text=MESSAGES["edit_ask_find"],
            reply_markup=cancel_keyboard(),
        )
    else:
        await callback.message.edit_text(
            MESSAGES["edit_ask_find"], reply_markup=cancel_keyboard()
        )

    await callback.answer()


@router.callback_query(F.data == "post_analyze")
async def post_analyze_callback(callback: CallbackQuery, state: FSMContext, bot: Bot):
    """
    Transition to Analyze flow with existing document.
    Called from post-action menu after replace/fix completes.
    """
    user_id = callback.from_user.id

    # Check if we have a file in session
    if not session_manager.has_file(user_id):
        # No file - need to upload one
        session_manager.create_session(user_id, mode="analyze")
        session_manager.set_chat_id(user_id, callback.message.chat.id)
        await state.set_state(BotStates.wait_for_file)
        await state.update_data(mode="analyze")

        if callback.message.document:
            await callback.message.edit_reply_markup(reply_markup=None)
            await bot.send_message(
                chat_id=callback.message.chat.id,
                text=MESSAGES["ask_file"].format(action="analyze"),
            )
        else:
            await callback.message.edit_text(
                MESSAGES["ask_file"].format(action="analyze")
            )
        await callback.answer()
        return

    # We have a file - go directly to analysis type selection
    session_manager.update_session(user_id, mode="analyze")
    await state.set_state(BotStates.analyze_select_type)

    # Handle document message
    if callback.message.document:
        await callback.message.edit_reply_markup(reply_markup=None)
        await bot.send_message(
            chat_id=callback.message.chat.id,
            text=MESSAGES["analyze_select"],
            reply_markup=analysis_type_keyboard(),
        )
    else:
        await callback.message.edit_text(
            MESSAGES["analyze_select"], reply_markup=analysis_type_keyboard()
        )

    await callback.answer()
