"""
FSM State Definitions for Enterprise Doc Bot
"""

from aiogram.fsm.state import State, StatesGroup


class BotStates(StatesGroup):
    """All bot states for the conversation flow."""

    # --- Waiting for file upload ---
    wait_for_file = State()  # Generic waiting for file (mode stored in data)

    # --- Edit Flow ---
    edit_wait_find = State()  # Waiting for user to type FIND text
    edit_wait_replace = State()  # Waiting for user to type REPLACE text
    edit_confirm = State()  # Waiting for confirmation button
    replace_step_review = State()  # Reviewing replacements step by step

    # --- Analyze Flow ---
    analyze_select_type = State()  # Waiting for analysis type selection

    # --- Fix Flow ---
    fix_confirm = State()  # Waiting for Apply All / Review Each / Cancel
    fix_review = State()  # Reviewing fixes one by one

    # --- Active Session ---
    file_active = State()  # File loaded, waiting for next action
