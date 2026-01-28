# Doc Helper

A Telegram bot for editing and analyzing DOCX documents using AI (Anthropic Claude).

## Features

- **Find & Replace**: Search and replace text with sentence-level preview
- **AI Analysis**: Grammar Check and Full Document Analysis
- **Auto-Fix**: Apply AI-suggested fixes automatically or review step-by-step

## Commands

- `/start` - Start the bot
- `/restart` - Restart at any time
- `/help` - Show help
- `/cancel` - Cancel current operation

## Setup

1. Clone the repository
2. Create virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # Linux/macOS
   ```
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Copy `.env.example` to `.env` and add your API keys:
   ```bash
   cp .env.example .env
   ```
5. Run the bot:
   ```bash
   python main.py
   ```

## Environment Variables

| Variable | Description |
|----------|-------------|
| `BOT_TOKEN` | Telegram Bot Token from @BotFather |
| `ANTHROPIC_API_KEY` | Anthropic API Key for Claude |
