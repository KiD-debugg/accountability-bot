# Accountability Bot 🤖

A personal Telegram bot that keeps me strictly accountable to my daily, weekly, and monthly goals. Built entirely in Python from scratch as a portfolio project.

---

## What It Does

This bot acts as a personal accountability coach running 24/7. It tracks goals across three categories, sends automatic scheduled reminders throughout the day, and responds to natural language — so you can interact with it conversationally instead of memorising commands.

---

## Scheduled Automatic Messages

The bot sends messages automatically at set times every day without any input needed.

| Time (EAT) | Message |
|---|---|
| 6:00 AM | Morning briefing — lists all active goals for the day |
| 8:30 AM | Repeating goals summary — shows which repeating goals are active today |
| 12:00 PM | Midday check-in — prompts progress review halfway through the day |
| 5:00 PM | Check-in reminder — prompts you to log your daily progress |
| 5:30 PM | Strict follow-up — sent only if no check-in has been recorded yet |
| 9:00 PM | Evening reflection — end of day review prompt |
| Sunday 8:00 PM | Weekly review — reviews all weekly goals |
| Last day of month 8:00 PM | Monthly review — reviews all monthly goals |

The bot also checks every minute for goals with a set reminder time and sends a 20-minute advance warning before each one.

---

## Commands

| Command | What It Does |
|---|---|
| `/start` | Start the bot and see all available commands |
| `/addgoal` | Add a new goal with optional reminder time and date |
| `/addrepeatinggoal` | Add a goal that repeats on specific days of the week |
| `/viewgoals` | View all daily, weekly, and monthly goals with their IDs |
| `/viewrepeating` | View all repeating goals with their schedules |
| `/editgoal` | Edit the text or schedule of an existing goal by ID |
| `/removegoal` | Delete a goal permanently by ID |
| `/checkin` | Manually record progress on each daily goal one by one |
| `/summary` | See today's detailed summary with completion status per goal |
| `/cancel` | Cancel any active conversation |

---

## Natural Language Interaction

The bot understands plain English messages without requiring commands.

### Adding Goals Naturally

All of the following formats are recognised:

```
Daily goal: Read 10 pages
addgoal daily: Study Python for 1 hour
ADDGOAL monthly: Pay rent
I want to add a goal: Exercise for 30 minutes
I have a new goal: Review my budget
I need to: Update my CV
```

### Adding Multiple Goals in One Message

Send a numbered list, word-numbered list, or bullet list and the bot saves all goals at once:

```
Daily goal: 1. Finish work report 2. Study Python 3. Exercise
addgoal weekly: one. Review LuxDevHQ notes two. Push code to GitHub
add goal monthly: - Pay rent - Review budget - Update CV
1. Finish homework 2. Make my hair
```

If the goal type is not included, the bot asks once and saves everything after you reply.

### Logging Completions Naturally

```
I finished my Python study today
I completed my exercise goal
Done with reading
I completed all my goals
```

The bot matches your message to the closest goal in the database and marks it as done automatically.

### Conversational Responses

The bot recognises greetings and conversational replies like:

```
Hello / Hi / Hey / Good morning
Okay / Thanks / Cool / Done
```

---

## Goal Types

| Type | Purpose |
|---|---|
| Daily | Goals tracked and checked in every day |
| Weekly | Goals reviewed every Sunday |
| Monthly | Goals reviewed on the last day of each month |
| Repeating | Goals that recur on specific days of the week for a set number of days |

---

## Goal Features

- **Reminder time** — Set a specific time for a goal and receive a 20-minute advance warning
- **Goal date** — Set a target date for a goal in multiple formats (today, tomorrow, Monday, DD/MM/YYYY, YYYY-MM-DD)
- **Repeating schedule** — Set which days of the week a goal repeats and for how long
- **Edit goals** — Update goal text or repeating schedule without deleting and recreating
- **Remove goals** — Delete goals cleanly by ID

---

## Summary Format

The `/summary` command shows a detailed breakdown by category:

```
📋 TODAY'S SUMMARY
─────────────────

📅 DAILY GOALS
─────────────────
✅ Study Python for 1 hour
❌ Exercise for 30 minutes
⏳ Read 10 pages (not checked in yet)

─────────────────
✅ Completed: 1
❌ Missed: 1
📊 Score: 50%

🟠 Weak. More than half your goals were missed. Unacceptable.
```

Verdict levels:
- 🟢 100% — Excellent. Every goal completed.
- 🟡 70–99% — Decent. But you left goals incomplete.
- 🟠 40–69% — Weak. More than half your goals were missed.
- 🔴 Below 40% — Very poor. Serious improvement needed.

---

## Security

- Bot only responds to the authorised Telegram user ID — all other users receive an `Unauthorized` response
- Bot token and user ID stored in environment variables — never hardcoded
- Parameterized SQL queries throughout — prevents SQL injection
- `.env` file excluded from Git via `.gitignore` — secrets never reach GitHub
- Input validation on all goal types and check-in statuses before database writes

---

## Tech Stack

| Technology | Purpose |
|---|---|
| Python 3.12 | Primary programming language |
| python-telegram-bot | Telegram Bot API integration |
| APScheduler | Scheduled automated messages |
| SQLite | Local database for goals and check-in history |
| python-dotenv | Safe loading of environment variables |
| pytz | Timezone handling (Africa/Nairobi — EAT UTC+3) |
| Docker | Container deployment |

---

## Project Structure

```
accountability-bot/
├── bot.py              Main bot logic, command handlers, natural language processing
├── database.py         All database operations and SQL queries
├── scheduler.py        Scheduled automated message jobs
├── config.py           Environment variable loader with safety checks
├── Dockerfile          Container build instructions for deployment
├── requirements.txt    All Python dependencies with locked versions
└── README.md           Project documentation
```

---

## Setup and Installation

### 1. Clone the repository

```bash
git clone https://github.com/KiD-debugg/accountability-bot.git
cd accountability-bot
```

### 2. Create a virtual environment

```bash
python -m venv venv

# Windows
venv\Scripts\activate

# Mac/Linux
source venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Create your `.env` file

```
TELEGRAM_BOT_TOKEN=your_bot_token_here
YOUR_TELEGRAM_USER_ID=your_numeric_user_id_here
```

> Get your bot token from [@BotFather](https://t.me/botfather) on Telegram.
> Get your user ID from [@userinfobot](https://t.me/userinfobot) on Telegram.

### 5. Run the bot

```bash
python bot.py
```

---

## Deployment

The bot is deployed using Docker. The `Dockerfile` is included in the repository.

To deploy on any Docker-compatible platform:

1. Set the environment variables `TELEGRAM_BOT_TOKEN` and `YOUR_TELEGRAM_USER_ID` in your platform's settings
2. Point the platform to this repository
3. The platform builds the image using the `Dockerfile` and runs `python bot.py`

---

## Database Schema

**goals table**

| Column | Type | Description |
|---|---|---|
| id | INTEGER | Auto-incrementing primary key |
| goal_text | TEXT | The goal description |
| goal_type | TEXT | daily, weekly, monthly, or repeating |
| repeat_days | TEXT | Comma-separated days for repeating goals (mon,wed,fri) |
| repeat_length | INTEGER | Number of days the repeating goal is active |
| goal_time | TEXT | Optional reminder time in HH:MM format |
| goal_date | TEXT | Optional target date in YYYY-MM-DD format |
| created_at | TIMESTAMP | When the goal was created |

**checkins table**

| Column | Type | Description |
|---|---|---|
| id | INTEGER | Auto-incrementing primary key |
| goal_id | INTEGER | Foreign key referencing goals.id |
| status | TEXT | done or missed |
| checked_at | TIMESTAMP | When the check-in was recorded |

---

## Author

Benjamin Ochieng
Civil and Structural Engineer transitioning into Data and Analytics
Nairobi, Kenya

[GitHub](https://github.com/KiD-debugg) 