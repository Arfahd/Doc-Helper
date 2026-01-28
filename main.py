"""
Enterprise Doc Bot - Main Entry Point
A Telegram bot for editing, analyzing, and fixing DOCX documents.
"""

import asyncio
import os
import sys
from aiogram import Bot, Dispatcher
from aiogram.types import ErrorEvent, Update
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramAPIError
from loguru import logger

from config import BOT_TOKEN, DOWNLOAD_DIR, MESSAGES
from exceptions import (
    BotError,
    AIServiceError,
    DocumentError,
    SessionError,
    RateLimitError,
)

# Configure loguru for debug output
# Remove default handler and add custom one with DEBUG level
logger.remove()
logger.add(
    sys.stderr,
    level="DEBUG",  # Change to "INFO" in production
    format="<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
)

from keyboards.inline import keep_session_keyboard, main_menu_keyboard
from utils.session import session_manager
from middleware import RateLimitMiddleware
from handlers import (
    start_router,
    edit_router,
    analyze_router,
    fix_router,
    common_router,
)


# Ensure download directory exists
if not os.path.exists(DOWNLOAD_DIR):
    os.makedirs(DOWNLOAD_DIR)


async def session_timeout_checker(bot: Bot, dp: Dispatcher):
    """
    Background task that checks for session timeouts.
    Runs every 30 seconds.

    - At 5 min inactivity: sends warning message
    - At 7 min inactivity: expires session and cleans up
    """
    logger.info("Session timeout checker started")

    while True:
        try:
            await asyncio.sleep(30)  # Check every 30 seconds

            # Get sessions needing warning (5 min passed)
            sessions_to_warn = session_manager.get_sessions_needing_warning()
            for user_id, chat_id in sessions_to_warn:
                try:
                    await bot.send_message(
                        chat_id=chat_id,
                        text=MESSAGES["session_warning"],
                        reply_markup=keep_session_keyboard(),
                    )
                    session_manager.mark_warning_sent(user_id)
                    logger.info(f"Sent timeout warning to user {user_id}")
                except Exception as e:
                    logger.error(f"Failed to send warning to user {user_id}: {e}")

            # Get sessions to expire (7 min passed)
            sessions_to_expire = session_manager.get_sessions_to_expire()
            for user_id, chat_id in sessions_to_expire:
                try:
                    # Clear FSM state for user
                    state = dp.fsm.get_context(bot, user_id, chat_id)
                    await state.clear()

                    # Cleanup session (deletes files)
                    session_manager.cleanup_session(user_id)

                    # Notify user
                    await bot.send_message(
                        chat_id=chat_id,
                        text=MESSAGES["session_expired"],
                        reply_markup=main_menu_keyboard(),
                    )
                    logger.info(f"Expired session for user {user_id}")
                except Exception as e:
                    logger.error(f"Failed to expire session for user {user_id}: {e}")
                    # Still try to cleanup even if message fails
                    session_manager.cleanup_session(user_id)

        except asyncio.CancelledError:
            logger.info("Session timeout checker stopped")
            break
        except Exception as e:
            logger.error(f"Error in session timeout checker: {e}")
            await asyncio.sleep(5)  # Wait before retrying


async def global_error_handler(event: ErrorEvent) -> bool:
    """
    Global error handler for all unhandled exceptions.

    Logs the error and attempts to notify the user with a friendly message.

    Args:
        event: The error event containing exception and update info

    Returns:
        True to indicate the error was handled
    """
    exception = event.exception
    update: Update = event.update

    # Get user info for logging
    user_id = None
    chat_id = None

    if update.message:
        user_id = update.message.from_user.id
        chat_id = update.message.chat.id
    elif update.callback_query:
        user_id = update.callback_query.from_user.id
        chat_id = (
            update.callback_query.message.chat.id
            if update.callback_query.message
            else None
        )

    # Determine user message based on exception type
    if isinstance(exception, BotError):
        # Our custom exceptions have user-friendly messages
        user_message = exception.user_message
        log_level = "warning"
    elif isinstance(exception, TelegramAPIError):
        user_message = "Telegram service error. Please try again."
        log_level = "error"
    else:
        user_message = "An unexpected error occurred. Please try again or use /cancel to start over."
        log_level = "error"

    # Log the error with context
    log_message = f"[User:{user_id}] {type(exception).__name__}: {exception}"
    if log_level == "warning":
        logger.warning(log_message)
    else:
        logger.error(log_message, exc_info=True)

    # Try to notify the user
    if chat_id and event.update.bot:
        try:
            await event.update.bot.send_message(
                chat_id=chat_id,
                text=user_message,
                reply_markup=main_menu_keyboard(),
            )
        except Exception as notify_error:
            logger.error(f"Failed to send error notification: {notify_error}")

    # For callback queries, also answer to prevent "loading" state
    if update.callback_query:
        try:
            await update.callback_query.answer(
                text="An error occurred", show_alert=False
            )
        except Exception:
            pass

    return True  # Error was handled


async def main():
    """Initialize and start the bot."""

    # Validate configuration
    if not BOT_TOKEN:
        logger.error("BOT_TOKEN is not set in .env file!")
        return

    # Initialize bot with default properties
    bot = Bot(
        token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN)
    )

    # Initialize dispatcher with memory storage for FSM
    storage = MemoryStorage()
    dp = Dispatcher(storage=storage)

    # Register global error handler
    dp.errors.register(global_error_handler)

    # Register rate limiting middleware
    # Messages: 0.5s between requests, Callbacks: 0.3s between requests
    dp.message.middleware(
        RateLimitMiddleware(
            message_rate_limit=0.5,
            callback_rate_limit=0.3,
        )
    )
    dp.callback_query.middleware(
        RateLimitMiddleware(
            message_rate_limit=0.5,
            callback_rate_limit=0.3,
        )
    )
    logger.info("Rate limiting middleware enabled")

    # Register routers (order matters - more specific first)
    dp.include_router(start_router)
    dp.include_router(edit_router)
    dp.include_router(analyze_router)
    dp.include_router(fix_router)
    dp.include_router(common_router)  # Catch-all should be last

    # Get bot info
    bot_info = await bot.get_me()
    logger.info(f"Starting Doc Helper @{bot_info.username}")
    logger.info("Bot is ready for personal chat interactions")
    logger.info("Commands: /start, /restart, /help, /cancel")

    # Start background task for session timeout
    timeout_task = asyncio.create_task(session_timeout_checker(bot, dp))

    # Start polling
    try:
        await dp.start_polling(bot)
    finally:
        # Cancel background task on shutdown
        timeout_task.cancel()
        try:
            await timeout_task
        except asyncio.CancelledError:
            pass
        await bot.session.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot shutdown by user")
    except Exception as e:
        logger.error(f"Bot crashed: {e}")
