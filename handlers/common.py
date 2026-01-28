"""
Common Handler - /help, /cancel, file receiver, done, and session management
"""

import os
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.exceptions import TelegramAPIError
from loguru import logger

from config import MESSAGES, MAX_FILE_SIZE_BYTES, SUPPORTED_EXTENSIONS


def escape_markdown(text: str) -> str:
    """Escape special Markdown characters to prevent parsing errors."""
    # Characters that need escaping in Telegram Markdown
    special_chars = [
        "_",
        "*",
        "[",
        "]",
        "(",
        ")",
        "~",
        "`",
        ">",
        "#",
        "+",
        "-",
        "=",
        "|",
        "{",
        "}",
        ".",
        "!",
    ]
    for char in special_chars:
        text = text.replace(char, f"\\{char}")
    return text


from states import BotStates
from keyboards.inline import (
    main_menu_keyboard,
    analysis_type_keyboard,
    cancel_keyboard,
    keep_session_keyboard,
)
from utils.session import (
    session_manager,
    generate_unique_filename,
    get_clean_output_name,
)
from tools.doc_tools import validate_docx
from handlers.fix import start_fix_scan
from aiogram.types import FSInputFile

router = Router()


# --- Commands ---


@router.message(Command("help"))
async def cmd_help(message: Message):
    """Handle /help command."""
    await message.answer(MESSAGES["help"], reply_markup=main_menu_keyboard())


@router.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext):
    """Handle /cancel command."""
    user_id = message.from_user.id

    # Cleanup session
    session_manager.cleanup_session(user_id)
    await state.clear()

    await message.answer(MESSAGES["cancelled"], reply_markup=main_menu_keyboard())


# --- File Receiver ---


@router.message(BotStates.wait_for_file, F.document)
async def receive_file(message: Message, state: FSMContext, bot: Bot):
    """Handle file upload when waiting for file."""
    user_id = message.from_user.id
    document = message.document

    # Validate file extension
    filename = document.file_name or "unknown"
    _, ext = os.path.splitext(filename)

    if ext.lower() not in SUPPORTED_EXTENSIONS:
        await message.answer(
            f"Invalid file type: {ext}\n\nSupported: {', '.join(SUPPORTED_EXTENSIONS)}"
        )
        return

    # Validate file size
    if document.file_size > MAX_FILE_SIZE_BYTES:
        max_mb = MAX_FILE_SIZE_BYTES / (1024 * 1024)
        await message.answer(f"File too large. Maximum size: {max_mb}MB")
        return

    # Download file with error handling
    try:
        file_info = await bot.get_file(document.file_id)
        save_path = generate_unique_filename(user_id, filename, document.file_unique_id)
        await bot.download_file(file_info.file_path, save_path)
    except TelegramAPIError as e:
        logger.error(f"Failed to download file from Telegram: {e}")
        await message.answer("Failed to download file. Please try again.")
        return
    except Exception as e:
        logger.error(f"Unexpected error downloading file: {e}")
        await message.answer("An error occurred. Please try again.")
        return

    # Validate DOCX structure
    is_valid, error_msg = validate_docx(save_path)
    if not is_valid:
        # Clean up invalid file
        if os.path.exists(save_path):
            os.remove(save_path)
        await message.answer(f"Invalid file: {error_msg}")
        return

    # Store file in session
    session_manager.set_file(user_id, save_path, filename)
    session_manager.set_chat_id(
        user_id, message.chat.id
    )  # Store chat_id for timeout messages

    # Get mode and proceed
    data = await state.get_data()
    mode = data.get("mode", "edit")

    # Send confirmation (escape filename to avoid Markdown parsing issues)
    safe_filename = escape_markdown(filename)
    await message.answer(MESSAGES["file_received"].format(filename=safe_filename))

    # Proceed based on mode
    if mode == "edit":
        await state.set_state(BotStates.edit_wait_find)
        await message.answer(MESSAGES["edit_ask_find"], reply_markup=cancel_keyboard())

    elif mode == "analyze":
        await state.set_state(BotStates.analyze_select_type)
        await message.answer(
            MESSAGES["analyze_select"], reply_markup=analysis_type_keyboard()
        )

    elif mode == "fix":
        # Start fix scan directly
        await start_fix_scan(message, state, user_id)


@router.message(BotStates.wait_for_file)
async def wait_for_file_invalid(message: Message):
    """Handle non-document messages when waiting for file."""
    await message.answer("Please send a .docx file.")


# --- Callback Handlers ---


@router.callback_query(F.data == "cancel")
async def cancel_callback(callback: CallbackQuery, state: FSMContext, bot: Bot):
    """Handle cancel button in any state."""
    user_id = callback.from_user.id

    # Cleanup session
    session_manager.cleanup_session(user_id)
    await state.clear()

    # Try to edit message, if it fails (document message), send new message
    try:
        await callback.message.edit_text(
            MESSAGES["cancelled"], reply_markup=main_menu_keyboard()
        )
    except Exception:
        # Message is a document, can't edit text - send new message
        await callback.message.edit_reply_markup(reply_markup=None)
        await bot.send_message(
            chat_id=callback.message.chat.id,
            text=MESSAGES["cancelled"],
            reply_markup=main_menu_keyboard(),
        )
    await callback.answer()


@router.callback_query(F.data == "done")
async def done_callback(callback: CallbackQuery, state: FSMContext, bot: Bot):
    """Handle done button - send document, cleanup, and end session."""
    user_id = callback.from_user.id

    # Get file info from session before cleanup
    file_path = session_manager.get_file_path(user_id)
    original_name = session_manager.get_original_name(user_id)

    # Remove buttons from current message
    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass

    # Send the document if we have one
    if file_path and original_name:
        try:
            clean_name = get_clean_output_name(original_name)
            doc_file = FSInputFile(file_path, filename=clean_name)

            await bot.send_document(
                chat_id=callback.message.chat.id,
                document=doc_file,
                caption=MESSAGES["done"],
                reply_markup=main_menu_keyboard(),
            )
        except Exception as e:
            logger.error(f"Failed to send document: {e}")
            await bot.send_message(
                chat_id=callback.message.chat.id,
                text="Failed to send document.\n\n" + MESSAGES["done"],
                reply_markup=main_menu_keyboard(),
            )
    else:
        # No file to send - just show message
        await bot.send_message(
            chat_id=callback.message.chat.id,
            text=MESSAGES["done"],
            reply_markup=main_menu_keyboard(),
        )

    # Cleanup session AFTER sending document
    session_manager.cleanup_session(user_id)
    await state.clear()
    await callback.answer()


@router.callback_query(F.data == "keep_session")
async def keep_session_callback(callback: CallbackQuery, state: FSMContext, bot: Bot):
    """Handle keep session button - reset timeout."""
    user_id = callback.from_user.id

    session_manager.update_activity(user_id)

    # Try to edit message, if it fails (document message), send new message
    try:
        await callback.message.edit_text(
            "Session extended.\n\nWhat would you like to do?",
            reply_markup=main_menu_keyboard(),
        )
    except Exception:
        # Message is a document, can't edit text - send new message
        await callback.message.edit_reply_markup(reply_markup=None)
        await bot.send_message(
            chat_id=callback.message.chat.id,
            text="Session extended.\n\nWhat would you like to do?",
            reply_markup=main_menu_keyboard(),
        )
    await callback.answer("Session extended")


# --- Catch-all for unexpected messages ---


@router.message(BotStates.file_active)
async def file_active_message(message: Message, state: FSMContext):
    """Handle text messages when file is active."""
    await message.answer(
        "Please use the buttons above, or send /cancel to exit.",
    )


@router.message()
async def catch_all(message: Message, state: FSMContext):
    """Catch any unhandled messages."""
    current_state = await state.get_state()

    if current_state is None:
        # No active state - show main menu
        await message.answer(
            "Send /start to begin, or choose a command:",
            reply_markup=main_menu_keyboard(),
        )
    else:
        await message.answer("Please follow the current flow or send /cancel to exit.")
