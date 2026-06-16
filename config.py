# config.py
# This file loads all secret values from the .env file
# Never hardcode tokens or IDs directly in your code

import os
from dotenv import load_dotenv

# This line reads your .env file and loads the values
load_dotenv()

# Your Telegram bot token from BotFather
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

# Your personal Telegram user ID
user_id_str = os.getenv("YOUR_TELEGRAM_USER_ID")
YOUR_USER_ID = int(user_id_str) if user_id_str else None

# Gemini API Key
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Safety check — if either value is missing, stop everything immediately
if not BOT_TOKEN:
    raise ValueError("TELEGRAM_BOT_TOKEN is missing from your .env file")

if not YOUR_USER_ID:
    raise ValueError("YOUR_TELEGRAM_USER_ID is missing from your .env file")

if not GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY is missing from your .env file")