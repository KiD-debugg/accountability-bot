# Accountability Bot 🤖

A personal Telegram bot that keeps me strictly accountable to my daily, weekly, and monthly goals.

## What It Does

- Sends a morning briefing at 6:00 AM with all goals for the day
- Sends a check-in reminder at 5:00 PM
- Sends a strict follow-up at 5:30 PM if check-in is missed
- Sends a weekly review every Sunday at 8:00 PM
- Sends a monthly review on the last day of each month
- Tracks goal completion and generates detailed summaries
- Categorises goals into Daily, Weekly, and Monthly

## Commands

| Command | What It Does |
|---|---|
| `/start` | Start the bot and see available commands |
| `/addgoal` | Add a new goal |
| `/viewgoals` | View all your goals by category |
| `/checkin` | Record your progress on each goal |
| `/summary` | See today's detailed summary with scores |

## Tech Stack

- Python 3.12
- python-telegram-bot
- APScheduler
- SQLite
- pytz

## Security

- Bot only responds to the authorized user ID
- Secrets managed via environment variables
- Parameterized SQL queries to prevent injection
- `.env` file never pushed to GitHub

## Setup

1. Clone the repository
2. Create a virtual environment:
```bash
   python -m venv venv
   source venv\Scripts\activate.bat
   venv\Scripts\activate     # Windows
```
3. Install dependencies:
```bash
   pip install -r requirements.txt
```
4. Create a `.env` file with your credentials:
TELEGRAM_BOT_TOKEN=your_token_here
YOUR_TELEGRAM_USER_ID=your_user_id_here
5. Run the bot:
```bash
   python bot.py
```

## Project Structure
accountability-bot/
├── bot.py          # Main bot logic and command handlers
├── database.py     # Database operations
├── scheduler.py    # Scheduled automated messages
├── config.py       # Environment variable loader
├── requirements.txt
└── README.md
## Author

Benjamin Ochieng  
Civil & Structural Engineer transitioning into Data & Analytics  
[GitHub Profile](https://github.com/KiD-debugg)
