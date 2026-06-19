# bot.py
# Main bot file - handles all Telegram commands and messages

from asyncio.log import logger

from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
    ConversationHandler,
)
from config import BOT_TOKEN, YOUR_USER_ID
import logging
import re
logger = logging.getLogger(__name__)
from database import (
    initialize_database,
    add_goal,
    get_goals,
    get_repeating_goals,
    get_time_based_goals,
    get_goal_by_id,
    record_checkin,
    get_todays_summary,
    get_goal_status_today,
    update_goal_text,
    update_repeating_goal_schedule,
    delete_goal,
    search_goals_by_keyword,
    get_all_incomplete_daily_goals,
)
# Conversation states - these are just numbers used to track
# where the user is in a multi-step conversation
WAITING_FOR_GOAL_TEXT = 1
WAITING_FOR_GOAL_TYPE = 2
WAITING_FOR_CHECKIN_RESPONSE = 3
WAITING_FOR_REPEATING_GOAL_TEXT = 4
WAITING_FOR_REPEATING_GOAL_DAYS = 5
WAITING_FOR_REPEATING_GOAL_LENGTH = 6
WAITING_FOR_REMOVE_GOAL_ID = 7
WAITING_FOR_EDIT_GOAL_ID = 8
WAITING_FOR_EDIT_ACTION = 9
WAITING_FOR_EDIT_NEW_TEXT = 10
WAITING_FOR_EDIT_NEW_SCHEDULE = 11
WAITING_FOR_EDIT_NEW_LENGTH = 12
WAITING_FOR_GOAL_TIME = 13
WAITING_FOR_GOAL_DATE = 14


def parse_time_input(raw_time: str) -> str | None:
    """
    Parses time input in multiple formats and returns HH:MM in 24-hour format.
    Supports: 14:30, 2:30 PM, 2:30pm, 14.30, 2.30 AM, etc.
    Returns None if format is invalid.
    """
    raw_time = raw_time.strip().lower()
    
    # Try 24-hour format: HH:MM or HH.MM
    match = re.match(r"^([01]?\d|2[0-3])[:.]([0-5]\d)$", raw_time)
    if match:
        hour = int(match.group(1))
        minute = int(match.group(2))
        return f"{hour:02d}:{minute:02d}"
    
    # Try 12-hour format with AM/PM: H:MM AM/PM, HH:MM AM/PM, H.MM AM/PM, etc.
    match = re.match(r"^([1-9]|1[0-2])[:.]([0-5]\d)\s*(am|pm)$", raw_time)
    if match:
        hour = int(match.group(1))
        minute = int(match.group(2))
        meridiem = match.group(3)
        
        if meridiem == "pm" and hour != 12:
            hour += 12
        elif meridiem == "am" and hour == 12:
            hour = 0
        
        return f"{hour:02d}:{minute:02d}"
    
    # Try 12-hour without space: 2:30PM, 2:30pm, etc.
    match = re.match(r"^([1-9]|1[0-2])[:.]([0-5]\d)(am|pm)$", raw_time)
    if match:
        hour = int(match.group(1))
        minute = int(match.group(2))
        meridiem = match.group(3)
        
        if meridiem == "pm" and hour != 12:
            hour += 12
        elif meridiem == "am" and hour == 12:
            hour = 0
        
        return f"{hour:02d}:{minute:02d}"
    
    return None


def parse_date_input(raw_date: str) -> str | None:
    """
    Parses date input in multiple formats and returns YYYY-MM-DD.
    Supports: 2026-06-17, 17-06-2026, 17/06/2026, today, tomorrow, Monday, etc.
    Returns None if format is invalid.
    """
    from datetime import datetime, timedelta
    
    raw_date = raw_date.strip().lower()
    today = datetime.now()
    
    # Skip date if user says no
    if raw_date in ["none", "no", "n", "skip"]:
        return None
    
    # Today
    if raw_date in ["today", "now"]:
        return today.strftime("%Y-%m-%d")
    
    # Tomorrow
    if raw_date == "tomorrow":
        tomorrow = today + timedelta(days=1)
        return tomorrow.strftime("%Y-%m-%d")
    
    # Day of week (Monday, tuesday, etc.)
    day_names = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
    if raw_date in day_names:
        target_day = day_names.index(raw_date)
        current_day = today.weekday()
        days_ahead = target_day - current_day
        if days_ahead <= 0:
            days_ahead += 7
        future_date = today + timedelta(days=days_ahead)
        return future_date.strftime("%Y-%m-%d")
    
    # YYYY-MM-DD format
    match = re.match(r"^(\d{4})-(\d{1,2})-(\d{1,2})$", raw_date)
    if match:
        try:
            year, month, day = int(match.group(1)), int(match.group(2)), int(match.group(3))
            date_obj = datetime(year, month, day)
            return date_obj.strftime("%Y-%m-%d")
        except ValueError:
            return None
    
    # DD-MM-YYYY format
    match = re.match(r"^(\d{1,2})-(\d{1,2})-(\d{4})$", raw_date)
    if match:
        try:
            day, month, year = int(match.group(1)), int(match.group(2)), int(match.group(3))
            date_obj = datetime(year, month, day)
            return date_obj.strftime("%Y-%m-%d")
        except ValueError:
            return None
    
    # DD/MM/YYYY format
    match = re.match(r"^(\d{1,2})/(\d{1,2})/(\d{4})$", raw_date)
    if match:
        try:
            day, month, year = int(match.group(1)), int(match.group(2)), int(match.group(3))
            date_obj = datetime(year, month, day)
            return date_obj.strftime("%Y-%m-%d")
        except ValueError:
            return None
    
    return None


def is_authorized(user_id: int) -> bool:
    """
    Security check - only you can use this bot.
    Rejects anyone else who tries to interact with it.
    """
    return user_id == YOUR_USER_ID


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles the /start command."""
    if not is_authorized(update.effective_user.id):
        await update.message.reply_text("Unauthorized.")
        return

    await update.message.reply_text(
        "Hello Benjamin. I am your accountability bot.\n\n"
        "Here is what I can do:\n"
        "/addgoal - Add a new goal\n"
        "/addrepeatinggoal - Add a repeating goal with reminder days\n"
        "/viewgoals - See all your goals\n"
        "/viewrepeating - See repeating goals\n"
        "/editgoal - Edit a goal by ID\n"
        "/removegoal - Remove a goal by ID\n"
        "/checkin - Do a manual check-in\n"
        "/summary - See today's summary\n\n"
        "I will also check in with you automatically every day."
    )


async def add_goal_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start the add goal conversation - asks for the goal text."""
    if not is_authorized(update.effective_user.id):
        await update.message.reply_text("Unauthorized.")
        return ConversationHandler.END

    await update.message.reply_text(
        "What is your goal? Type it out clearly."
    )
    return WAITING_FOR_GOAL_TEXT


async def add_goal_get_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Receives the goal text and asks for the goal type."""
    # Store the goal text temporarily
    context.user_data["goal_text"] = update.message.text.strip()

    await update.message.reply_text(
        "What type of goal is this?\n\n"
        "Reply with one of these exactly:\n"
        "daily\n"
        "weekly\n"
        "monthly"
    )
    return WAITING_FOR_GOAL_TYPE


async def add_goal_get_type(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Receives the goal type and asks for the reminder time."""
    goal_type = update.message.text.strip().lower()

    if goal_type not in ["daily", "weekly", "monthly"]:
        await update.message.reply_text(
            "That is not valid. Please reply with exactly: daily, weekly, or monthly"
        )
        return WAITING_FOR_GOAL_TYPE

    context.user_data["goal_type"] = goal_type

    await update.message.reply_text(
        "What time should I remind you? Reply in HH:MM format, or type none if you do not want a time reminder."
    )
    return WAITING_FOR_GOAL_TIME


async def add_goal_get_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Receives reminder time and asks for optional date."""
    raw_time = update.message.text.strip()
    goal_text = context.user_data.get("goal_text")
    goal_type = context.user_data.get("goal_type")

    if not goal_text or not goal_type:
        await update.message.reply_text(
            "Something went wrong. Start again with /addgoal."
        )
        return ConversationHandler.END

    goal_time = None
    if raw_time.lower() not in ["none", "no", "n", "skip"] and raw_time:
        goal_time = parse_time_input(raw_time)
        
        if not goal_time:
            await update.message.reply_text(
                "I couldn't parse that time. Please use one of these formats:\n\n"
                "24-hour: 14:30 or 14.30\n"
                "12-hour: 2:30 PM or 2:30pm or 2:30 AM\n"
                "Or type 'none' if you don't want a time reminder."
            )
            return WAITING_FOR_GOAL_TIME

    context.user_data["goal_time"] = goal_time
    
    await update.message.reply_text(
        "When should this goal happen?\n\n"
        "You can reply with:\n"
        "today, tomorrow, Monday, 2026-06-20, 20-06-2026, 20/06/2026\n"
        "Or type 'none' if you don't want to set a date."
    )
    return WAITING_FOR_GOAL_DATE


async def add_goal_get_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Receives optional date and saves the goal."""
    raw_date = update.message.text.strip()
    goal_text = context.user_data.get("goal_text")
    goal_type = context.user_data.get("goal_type")
    goal_time = context.user_data.get("goal_time")

    if not goal_text or not goal_type:
        await update.message.reply_text(
            "Something went wrong. Start again with /addgoal."
        )
        return ConversationHandler.END

    goal_date = None
    if raw_date.lower() not in ["none", "no", "n", "skip"] and raw_date:
        goal_date = parse_date_input(raw_date)
        
        if not goal_date:
            await update.message.reply_text(
                "I couldn't parse that date. Please use one of these formats:\n\n"
                "today, tomorrow, Monday, Friday\n"
                "YYYY-MM-DD (2026-06-20)\n"
                "DD-MM-YYYY (20-06-2026)\n"
                "DD/MM/YYYY (20/06/2026)\n"
                "Or type 'none' to skip the date."
            )
            return WAITING_FOR_GOAL_DATE

    try:
        add_goal(goal_text, goal_type, goal_time=goal_time, goal_date=goal_date)
        context.user_data["last_action"] = "add_goal"
        
        time_display = goal_time if goal_time else "No time set"
        date_display = goal_date if goal_date else "No date set"
        
        await update.message.reply_text(
            f"Goal saved.\n\n"
            f"Goal: {goal_text}\n"
            f"Type: {goal_type.capitalize()}\n"
            f"Time: {time_display}\n"
            f"Date: {date_display}"
        )
    except Exception as e:
        await update.message.reply_text("Something went wrong saving your goal. Please try again.")
        print(f"Error saving goal: {e}")

    return ConversationHandler.END


async def add_repeating_goal_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start the add repeating goal conversation."""
    if not is_authorized(update.effective_user.id):
        await update.message.reply_text("Unauthorized.")
        return ConversationHandler.END

    await update.message.reply_text(
        "What repeating goal do you want to add? Type the goal clearly."
    )
    return WAITING_FOR_REPEATING_GOAL_TEXT


async def add_repeating_goal_get_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["repeating_goal_text"] = update.message.text.strip()
    await update.message.reply_text(
        "Which days should I remind you? Reply with days separated by commas, for example: Monday, Wednesday, Friday."
    )
    return WAITING_FOR_REPEATING_GOAL_DAYS


def normalize_repeat_days(days_raw: str) -> str | None:
    day_map = {
        "monday": "mon",
        "mon": "mon",
        "tuesday": "tue",
        "tue": "tue",
        "wednesday": "wed",
        "wed": "wed",
        "thursday": "thu",
        "thu": "thu",
        "friday": "fri",
        "fri": "fri",
        "saturday": "sat",
        "sat": "sat",
        "sunday": "sun",
        "sun": "sun",
    }
    days = [item.strip().lower() for item in re.split(r"[,:;]+|\\s+", days_raw) if item.strip()]
    normalized = []
    for day in days:
        if day in day_map:
            if day_map[day] not in normalized:
                normalized.append(day_map[day])
        else:
            return None
    return ",".join(normalized) if normalized else None


async def add_repeating_goal_get_days(update: Update, context: ContextTypes.DEFAULT_TYPE):
    repeat_days = normalize_repeat_days(update.message.text.strip())
    if not repeat_days:
        await update.message.reply_text(
            "I couldn't understand the days. Use names like Monday, Wed, Fri separated by commas."
        )
        return WAITING_FOR_REPEATING_GOAL_DAYS

    context.user_data["repeating_goal_days"] = repeat_days
    await update.message.reply_text(
        "How many days should this goal repeat? Reply with a number, or 0 for no limit."
    )
    return WAITING_FOR_REPEATING_GOAL_LENGTH


async def add_repeating_goal_get_length(update: Update, context: ContextTypes.DEFAULT_TYPE):
    raw_length = update.message.text.strip()
    try:
        repeat_length = int(raw_length)
    except ValueError:
        await update.message.reply_text("Please reply with a valid number for the repeat length.")
        return WAITING_FOR_REPEATING_GOAL_LENGTH

    if repeat_length < 0:
        await update.message.reply_text("Please provide zero or a positive number.")
        return WAITING_FOR_REPEATING_GOAL_LENGTH

    goal_text = context.user_data.pop("repeating_goal_text", None)
    repeat_days = context.user_data.pop("repeating_goal_days", None)

    if not goal_text or not repeat_days:
        await update.message.reply_text("Something went wrong. Please try adding the repeating goal again.")
        return ConversationHandler.END

    add_goal(goal_text, "repeating", repeat_days=repeat_days, repeat_length=(repeat_length or None))
    context.user_data["last_action"] = "add_goal"
    await update.message.reply_text(
        f"✅ Repeating goal saved: {goal_text}\n"
        f"Reminders: {repeat_days.replace(',', ', ')}\n"
        f"Repeat length: {repeat_length if repeat_length > 0 else 'no limit'} days"
    )
    return ConversationHandler.END


async def view_repeating_goals(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update.effective_user.id):
        await update.message.reply_text("Unauthorized.")
        return

    goals = get_repeating_goals()
    if not goals:
        await update.message.reply_text(
            "You have no repeating goals yet. Use /addrepeatinggoal to add one."
        )
        return

    message = "REPEATING GOALS\n\n"
    for goal_id, goal_text, repeat_days, repeat_length in goals:
        days_display = repeat_days.replace(",", ", ") if repeat_days else "None"
        length_display = f"{repeat_length} days" if repeat_length else "No limit"
        message += (
            f"ID {goal_id}: {goal_text}\n"
            f"  Days: {days_display}\n"
            f"  Length: {length_display}\n\n"
        )

    context.user_data["last_action"] = "view_repeating"
    await update.message.reply_text(message)


async def remove_goal_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update.effective_user.id):
        await update.message.reply_text("Unauthorized.")
        return ConversationHandler.END

    await update.message.reply_text(
        "Send me the ID of the goal you want to remove. You can get the ID from /viewgoals or /viewrepeating."
    )
    return WAITING_FOR_REMOVE_GOAL_ID


async def remove_goal_by_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        goal_id = int(update.message.text.strip())
    except ValueError:
        await update.message.reply_text("Please send a valid numeric goal ID.")
        return WAITING_FOR_REMOVE_GOAL_ID

    goal = get_goal_by_id(goal_id)
    if not goal:
        await update.message.reply_text("No goal found with that ID.")
        return ConversationHandler.END

    delete_goal(goal_id)
    context.user_data["last_action"] = "remove_goal"
    await update.message.reply_text(f"✅ Goal ID {goal_id} removed.")
    return ConversationHandler.END


async def edit_goal_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update.effective_user.id):
        await update.message.reply_text("Unauthorized.")
        return ConversationHandler.END

    await update.message.reply_text(
        "Send me the ID of the goal you want to edit. Use /viewgoals or /viewrepeating to find the ID."
    )
    return WAITING_FOR_EDIT_GOAL_ID


async def edit_goal_choose(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        goal_id = int(update.message.text.strip())
    except ValueError:
        await update.message.reply_text("Please send a valid numeric goal ID.")
        return WAITING_FOR_EDIT_GOAL_ID

    goal = get_goal_by_id(goal_id)
    if not goal:
        await update.message.reply_text("No goal found with that ID.")
        return ConversationHandler.END

    context.user_data["edit_goal_id"] = goal_id
    goal_type = goal[2]

    if goal_type == "repeating":
        await update.message.reply_text(
            "Do you want to edit the goal text or the reminder schedule? Reply with text or schedule."
        )
        return WAITING_FOR_EDIT_ACTION

    await update.message.reply_text("Send the new text for this goal.")
    return WAITING_FOR_EDIT_NEW_TEXT


async def edit_goal_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    action = update.message.text.strip().lower()
    if action == "text":
        await update.message.reply_text("Send the new text for this goal.")
        return WAITING_FOR_EDIT_NEW_TEXT
    if action == "schedule":
        await update.message.reply_text(
            "Send the new reminder days for this repeating goal, for example: Monday, Wed, Fri."
        )
        return WAITING_FOR_EDIT_NEW_SCHEDULE

    await update.message.reply_text("Please reply with exactly: text or schedule.")
    return WAITING_FOR_EDIT_ACTION


async def edit_goal_new_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    goal_id = context.user_data.get("edit_goal_id")
    if goal_id is None:
        await update.message.reply_text("Something went wrong. Start editing again with /editgoal.")
        return ConversationHandler.END

    new_text = update.message.text.strip()
    if not new_text:
        await update.message.reply_text("Please send a non-empty goal description.")
        return WAITING_FOR_EDIT_NEW_TEXT

    update_goal_text(goal_id, new_text)
    context.user_data["last_action"] = "edit_goal"
    await update.message.reply_text(f"✅ Goal ID {goal_id} text updated.")
    return ConversationHandler.END


async def edit_goal_new_schedule(update: Update, context: ContextTypes.DEFAULT_TYPE):
    goal_id = context.user_data.get("edit_goal_id")
    if goal_id is None:
        await update.message.reply_text("Something went wrong. Start editing again with /editgoal.")
        return ConversationHandler.END

    repeat_days = normalize_repeat_days(update.message.text.strip())
    if not repeat_days:
        await update.message.reply_text(
            "I couldn't understand the days. Use names like Monday, Wed, Fri separated by commas."
        )
        return WAITING_FOR_EDIT_NEW_SCHEDULE

    context.user_data["edit_goal_days"] = repeat_days
    await update.message.reply_text(
        "How many days should this repeating goal continue? Reply with a number, or 0 for no limit."
    )
    return WAITING_FOR_EDIT_NEW_LENGTH


async def edit_goal_schedule_length(update: Update, context: ContextTypes.DEFAULT_TYPE):
    goal_id = context.user_data.get("edit_goal_id")
    repeat_days = context.user_data.get("edit_goal_days")
    if goal_id is None or not repeat_days:
        await update.message.reply_text("Something went wrong. Start editing again with /editgoal.")
        return ConversationHandler.END

    raw_length = update.message.text.strip()
    try:
        repeat_length = int(raw_length)
    except ValueError:
        await update.message.reply_text("Please reply with a valid number for the repeat length.")
        return WAITING_FOR_EDIT_NEW_LENGTH

    if repeat_length < 0:
        await update.message.reply_text("Please provide zero or a positive number.")
        return WAITING_FOR_EDIT_NEW_LENGTH

    update_repeating_goal_schedule(goal_id, repeat_days, (repeat_length or None))
    context.user_data["last_action"] = "edit_goal"
    await update.message.reply_text(
        f"✅ Goal ID {goal_id} schedule updated. Days: {repeat_days.replace(',', ', ')} "
        f"Length: {repeat_length if repeat_length > 0 else 'no limit'} days."
    )
    return ConversationHandler.END


async def view_goals(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Shows all goals organized by type."""
    if not is_authorized(update.effective_user.id):
        await update.message.reply_text("Unauthorized.")
        return

    message = "YOUR GOALS\n\n"

    for goal_type in ["Daily", "Weekly", "Monthly"]:
        goals = get_goals(goal_type)
        message += f"{goal_type.upper()} GOALS:\n"

        if goals:
            for goal_id, goal_text in goals:
                message += f"ID {goal_id}: {goal_text}\n"
        else:
            message += "None added yet.\n"

        message += "\n"

    await update.message.reply_text(message)


async def manual_checkin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Starts a manual check-in for daily goals."""
    if not is_authorized(update.effective_user.id):
        await update.message.reply_text("Unauthorized.")
        return

    goals = get_goals("daily")

    if not goals:
        await update.message.reply_text(
            "You have no daily goals yet. Add some with /addgoal"
        )
        return

    # Store goals in context for the conversation
    context.user_data["checkin_goals"] = goals
    context.user_data["checkin_index"] = 0

    first_goal = goals[0][1]
    context.user_data["last_action"] = "checkin"
    await update.message.reply_text(
        f"Check-in starting.\n\n"
        f"Goal 1: {first_goal}\n\n"
        f"Did you complete this? Reply: done or missed"
    )
    return WAITING_FOR_CHECKIN_RESPONSE


async def checkin_response(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles the response to each check-in question."""
    response = update.message.text.strip().lower()

    if response not in ["done", "missed"]:
        await update.message.reply_text("Please reply with exactly: done or missed")
        return WAITING_FOR_CHECKIN_RESPONSE

    goals = context.user_data["checkin_goals"]
    index = context.user_data["checkin_index"]
    goal_id = goals[index][0]

    record_checkin(goal_id, response)

    # Move to next goal
    index += 1
    context.user_data["checkin_index"] = index

    if index < len(goals):
        next_goal = goals[index][1]
        await update.message.reply_text(
            f"Recorded.\n\n"
            f"Goal {index + 1}: {next_goal}\n\n"
            f"Did you complete this? Reply: done or missed"
        )
        return WAITING_FOR_CHECKIN_RESPONSE
    else:
        context.user_data["last_action"] = "checkin_complete"
        await update.message.reply_text(
            "Check-in complete. Use /summary to see today's results."
        )
        return ConversationHandler.END


async def summary(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Shows today's detailed check-in summary organised by goal category."""
    if not is_authorized(update.effective_user.id):
        await update.message.reply_text("Unauthorized.")
        return

    context.user_data["last_action"] = "summary"
    message = "📋 TODAY'S SUMMARY\n"
    message += "─────────────────\n\n"

    total_done = 0
    total_missed = 0
    any_goals_found = False

    # Go through each category separately
    for goal_type in ["Daily", "Weekly", "Monthly"]:
        goals = get_goals(goal_type)

        if not goals:
            continue

        any_goals_found = True
        message += f"{'📅' if goal_type == 'Daily' else '📆' if goal_type == 'Weekly' else '🗓️'} "
        message += f"{goal_type.upper()} GOALS\n"
        message += "─────────────────\n"

        for goal_id, goal_text in goals:
            # Check if this goal was checked in today
            status = get_goal_status_today(goal_id)

            if status == "done":
                message += f"✅ {goal_text}\n"
                total_done += 1
            elif status == "missed":
                message += f"❌ {goal_text}\n"
                total_missed += 1
            else:
                # Goal exists but was never checked in today
                message += f"⏳ {goal_text} (not checked in yet)\n"

        message += "\n"

    if not any_goals_found:
        await update.message.reply_text(
            "You have no goals saved yet. Use /addgoal to add some."
        )
        return

    # Overall score
    total_checked = total_done + total_missed

    if total_checked == 0:
        await update.message.reply_text(
            message + "You have not done any check-ins today yet. Use /checkin to start."
        )
        return

    percentage = round((total_done / total_checked) * 100)

    message += "─────────────────\n"
    message += f"✅ Completed: {total_done}\n"
    message += f"❌ Missed: {total_missed}\n"
    message += f"📊 Score: {percentage}%\n\n"

    # Strict verdict
    if percentage == 100:
        verdict = "🟢 Excellent. Every goal completed. Keep this standard."
    elif percentage >= 70:
        verdict = "🟡 Decent. But you left goals incomplete. Do better."
    elif percentage >= 40:
        verdict = "🟠 Weak. More than half your goals were missed. Unacceptable."
    else:
        verdict = "🔴 Very poor. You need to take your goals seriously."

    message += verdict

    context.user_data["last_action"] = "view_goals"
    await update.message.reply_text(message)


def parse_direct_goal_message(user_message: str) -> str | None:
    """Parse direct goal messages like 'Daily goal: Read 10 pages.'"""
    normalized = user_message.strip()

    # Accept messages like "Addgoal, monthly goal: Read 10 pages." or "Add goal: daily goal: Read..."
    match = re.match(
        r"^(?:add\s*goal|addgoal|new\s*goal)\s*[.,:\-]?\s*(Daily|Weekly|Monthly)\s+goal\s*[:\-]?\s*(.+)$",
        normalized,
        re.IGNORECASE,
    )
    if not match:
        match = re.match(r"^(Daily|Weekly|Monthly)\s+goal\s*[:\-]?\s*(.+)$", normalized, re.IGNORECASE)
        if not match:
            return None

    goal_type = match.group(1)
    goal_text = match.group(2).strip()
    if not goal_text:
        return (
            "Please provide a goal after the type. Example: Daily goal: Read 10 pages."
        )

    add_goal(goal_text, goal_type)
    return f"✅ Goal saved: {goal_text} ({goal_type})"

def parse_numbered_goals(user_message: str) -> dict:
    """
    Detects and parses a list of goals from a single message.
    Handles numbered lists (1. 2. 3.), word numbers (one, two, three),
    bullet points (- or *), and mixed formats.
    
    Also detects goal type from the message if provided.
    
    Returns a dict with:
        'detected': bool
        'goals': list of goal text strings
        'goal_type': 'daily', 'weekly', 'monthly', or None
        'needs_type': bool — True if goal type was not found in the message
    """
    
    # Word number map
    word_numbers = {
        "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
        "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
        "first": 1, "second": 2, "third": 3, "fourth": 4, "fifth": 5
    }
    
    normalized = user_message.strip()
    lower = normalized.lower()
    
    # --- Detect goal type from message ---
    goal_type = None
    type_patterns = [
        r"\b(daily|day)\b",
        r"\b(weekly|week)\b",
        r"\b(monthly|month)\b"
    ]
    for pattern in type_patterns:
        match = re.search(pattern, lower)
        if match:
            word = match.group(1)
            if word in ["daily", "day"]:
                goal_type = "daily"
            elif word in ["weekly", "week"]:
                goal_type = "weekly"
            elif word in ["monthly", "month"]:
                goal_type = "monthly"
            break
    
    # --- Strip known prefixes before parsing items ---
    # Remove addgoal / add goal / new goal prefixes
    cleaned = re.sub(
        r"^(?:addgoal|add\s+goal|new\s+goal)\s*[,:\-.]?\s*",
        "",
        normalized,
        flags=re.IGNORECASE
    )
    # Remove goal type declaration at the start: "daily goal:", "daily:", etc.
    cleaned = re.sub(
        r"^(?:daily|weekly|monthly)(?:\s+goals?)?\s*[,:\-.]?\s*",
        "",
        cleaned,
        flags=re.IGNORECASE
    )
    cleaned = cleaned.strip()
    
    # --- Try splitting by numeric patterns: "1. item 2. item" or "1) item 2) item" ---
    # This handles: 1. 2. 3.  |  1) 2) 3)  |  1- 2- 3-
    numeric_split = re.split(r"\s*\d+[.):\-]\s*", cleaned)
    # Remove empty strings from split
    numeric_items = [item.strip() for item in numeric_split if item.strip()]
    
    if len(numeric_items) >= 2:
        return {
            "detected": True,
            "goals": numeric_items,
            "goal_type": goal_type,
            "needs_type": goal_type is None
        }
    
    # --- Try splitting by word numbers: "one. item two. item" ---
    # Build a pattern from all word numbers
    word_num_pattern = r"\s*(?:" + "|".join(word_numbers.keys()) + r")[.):\-]?\s+"
    word_split = re.split(word_num_pattern, cleaned, flags=re.IGNORECASE)
    word_items = [item.strip() for item in word_split if item.strip()]
    
    if len(word_items) >= 2:
        return {
            "detected": True,
            "goals": word_items,
            "goal_type": goal_type,
            "needs_type": goal_type is None
        }
    
    # --- Try splitting by bullet points: "- item - item" or "* item * item" ---
    bullet_split = re.split(r"\s*[-*•]\s+", cleaned)
    bullet_items = [item.strip() for item in bullet_split if item.strip()]
    
    if len(bullet_items) >= 2:
        return {
            "detected": True,
            "goals": bullet_items,
            "goal_type": goal_type,
            "needs_type": goal_type is None
        }
    
    # --- Try splitting by comma if it looks like a list ---
    # Only treat as a list if there are at least 2 meaningful comma-separated items
    comma_split = [item.strip() for item in cleaned.split(",") if item.strip()]
    if len(comma_split) >= 2 and all(len(item) > 3 for item in comma_split):
        return {
            "detected": True,
            "goals": comma_split,
            "goal_type": goal_type,
            "needs_type": goal_type is None
        }
    
    # Nothing detected as a list
    return {
        "detected": False,
        "goals": [],
        "goal_type": goal_type,
        "needs_type": False
    }

def detect_goal_addition_intent(user_message: str) -> dict:
    """
    Detects if user wants to add a goal and extracts goal details.
    Returns a dict with keys: 'detected', 'goal_text', 'goal_type', 'response'
    """
    normalized = user_message.strip()
    lower_msg = normalized.lower()
    
    # Pattern 1: "I want to add a goal: <goal_text>"
    match = re.match(r"i\s+want\s+to\s+add\s+(?:a\s+)?goal\s*[:\-]?\s*(.+)", lower_msg)
    if match:
        goal_text = match.group(1).strip()
        if goal_text:
            return {
                "detected": True,
                "goal_text": goal_text,
                "goal_type": None,
                "needs_type": True,
                "response": f"Got it! So your goal is: \"{goal_text}\"\n\nWhat type? Reply: Daily, Weekly, or Monthly"
            }
    
    # Pattern 2: "Addgoal, monthly goal: ..." or "Add goal: daily goal: ..."
    match = re.match(
        r"^(?:add\s*goal|addgoal|new\s*goal)\s*[.,:\-]?\s*(daily|weekly|monthly)\s+goal\s*[:\-]?\s*(.+)$",
        lower_msg,
    )
    if match:
        goal_type = match.group(1).lower()
        goal_text = match.group(2).strip()
        if goal_text:
            return {
                "detected": True,
                "goal_text": goal_text,
                "goal_type": goal_type,
                "needs_type": False,
                "response": f"✅ Goal saved: \"{goal_text}\" ({goal_type})"
            }

    # Pattern 3: "Add a goal: <goal_text>" or "Add goal: <goal_text>"
    match = re.match(r"^(?:add\s*goal|addgoal|new\s*goal)\s*[:\-]?\s*(.+)$", lower_msg)
    if match:
        goal_text = match.group(1).strip()
        if goal_text:
            return {
                "detected": True,
                "goal_text": goal_text,
                "goal_type": None,
                "needs_type": True,
                "response": f"Great! Goal: \"{goal_text}\"\n\nWhat type? Reply: Daily, Weekly, or Monthly"
            }

    # Pattern 4: "I have a new goal: <goal_text>" or "I have a goal: <goal_text>"
    match = re.match(r"i\s+have\s+(?:a\s+)?(?:new\s+)?goal\s*[:\-]?\s*(.+)", lower_msg)
    if match:
        goal_text = match.group(1).strip()
        if goal_text:
            return {
                "detected": True,
                "goal_text": goal_text,
                "goal_type": None,
                "needs_type": True,
                "response": f"Perfect! Goal: \"{goal_text}\"\n\nWhat type? Reply: Daily, Weekly, or Monthly"
            }
    
    # Pattern 4: "I want to: <goal_text>" or "I want to track: <goal_text>"
    match = re.match(r"i\s+want\s+to\s+(?:track\s+)?(?:be\s+)?(?:start\s+)?[:\-]?\s*(.+)", lower_msg)
    if match:
        potential_goal = match.group(1).strip()
        # Make sure this doesn't match too broadly - check for meaningful goal text
        if len(potential_goal) > 5 and "add" not in potential_goal.lower():
            return {
                "detected": True,
                "goal_text": potential_goal,
                "goal_type": None,
                "needs_type": True,
                "response": f"Alright! Goal: \"{potential_goal}\"\n\nWhat type? Reply: Daily, Weekly, or Monthly"
            }
    
    # Pattern 5: "I need to: <goal_text>" or "I should: <goal_text>"
    match = re.match(r"(?:i\s+need\s+to|i\s+should)\s+(?:start\s+)?[:\-]?\s*(.+)", lower_msg)
    if match:
        potential_goal = match.group(1).strip()
        if len(potential_goal) > 5:
            return {
                "detected": True,
                "goal_text": potential_goal,
                "goal_type": None,
                "needs_type": True,
                "response": f"Got it! Goal: \"{potential_goal}\"\n\nWhat type? Reply: Daily, Weekly, or Monthly"
            }
    
    # No goal addition intent detected
    return {
        "detected": False,
        "goal_text": None,
        "goal_type": None,
        "needs_type": False,
        "response": None
    }


def detect_goal_completion_intent(user_message: str) -> dict:
    """
    Detects if user mentions completing a goal and extracts keywords to match.
    Returns a dict with keys: 'detected', 'keywords', 'response'
    """
    normalized = user_message.strip()
    lower_msg = normalized.lower()
    
    # Patterns to detect completion
    completion_patterns = [
        r"(?:i\s+)?(?:just\s+)?(?:completed|finished|done|did)\s+(?:my\s+)?(?:goal\s+)?[:\-]?\s*(.+)",
        r"i\s+(?:completed|finished|did|have done)\s+(?:my\s+)?(?:goal\s+)?(?:of\s+)?[:\-]?\s*(.+)",
        r"(?:done\s+with|finished|completed)\s+(?:my\s+)?[:\-]?\s*(.+)",
        r"i\s+(?:just\s+)?(?:did|completed|finished)\s+[:\-]?\s*(.+)",
        r"(?:accomplished|achieved)\s+(?:my\s+)?[:\-]?\s*(.+)",
        r"completed\s*:\s*(.+)",
        r"finished\s*:\s*(.+)",
    ]
    
    extracted_keywords = None
    for pattern in completion_patterns:
        match = re.search(pattern, lower_msg)
        if match:
            extracted_keywords = match.group(1).strip()
            break
    
    # Detect completion of every goal
    all_goals_match = re.search(
        r"""
        (?:completed|finished|done|accomplished|achieved)\s+(?:all|every)\s+(?:my\s+)?goals?
        |(?:all|every)\s+(?:my\s+)?goals?\s+(?:completed|finished|done|accomplished|achieved)
        |(?:done|completed)\s+with\s+(?:all|every)\s+(?:my\s+)?goals?
        """,
        lower_msg,
        re.IGNORECASE | re.VERBOSE,
    )
    if all_goals_match:
        return {
            "detected": True,
            "all_goals": True,
            "keywords": "all goals",
            "matched_goals": [],
            "response": "✅ Marking all your goals as completed for today."
        }

    if not extracted_keywords or len(extracted_keywords) < 2:
        return {
            "detected": False,
            "keywords": None,
            "matched_goals": [],
            "response": None
        }
    
    # Search for matching goals
    matched_goals = search_goals_by_keyword(extracted_keywords)
    
    if not matched_goals:
        return {
            "detected": True,
            "keywords": extracted_keywords,
            "matched_goals": [],
            "response": f"I couldn't find a goal matching \"{extracted_keywords}\". Can you tell me the exact goal text or use /viewgoals to see your goals?"
        }
    
    if len(matched_goals) == 1:
        # Exact match found
        goal_id, goal_text, goal_type = matched_goals[0]
        return {
            "detected": True,
            "keywords": extracted_keywords,
            "matched_goals": matched_goals,
            "matched_goal_id": goal_id,
            "matched_goal_text": goal_text,
            "response": f"✅ Marked as done: {goal_text}"
        }
    
    # Multiple matches - ask for clarification
    goal_list = "\n".join([f"• {text}" for _, text, _ in matched_goals])
    return {
        "detected": True,
        "keywords": extracted_keywords,
        "matched_goals": matched_goals,
        "response": f"I found multiple matching goals:\n\n{goal_list}\n\nWhich one did you complete? Reply with the exact goal text or use /viewgoals to see IDs."
    }


def complete_all_goals() -> int:
    """
    Marks all active goals as completed for today.
    Returns how many goals were recorded as done.
    """
    all_goals = []
    for goal_type in ["Daily", "Weekly", "Monthly"]:
        all_goals.extend(get_goals(goal_type))

    repeating_goals = get_repeating_goals()
    for goal_id, goal_text, *_ in repeating_goals:
        all_goals.append((goal_id, goal_text))

    completed_count = 0
    for goal_id, _ in all_goals:
        status = get_goal_status_today(goal_id)
        if status != "done":
            record_checkin(goal_id, "done")
            completed_count += 1

    return completed_count


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancels any active conversation."""
    await update.message.reply_text("Cancelled.")
    return ConversationHandler.END


async def post_init(application):
    """
    This runs automatically after the bot starts its event loop.
    It is the correct place to start the scheduler.
    """
    from scheduler import create_scheduler
    scheduler = create_scheduler(application.bot)
    scheduler.start()
    logger.info("Scheduler started successfully with Nairobi timezone.")

async def handle_free_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handles any non-command text message.
    """
    if not is_authorized(update.effective_user.id):
        await update.message.reply_text("Unauthorized.")
        return

    user_message = update.message.text.strip()
    normalized = user_message.lower()

    # Respond to greetings with a prompt to start using commands
    if normalized in [
        "hello", "hi", "hey", "yoh", "yohh", "yooh",
        "good morning", "good afternoon", "good evening",
        "greetings", "how are you", "what's up"
    ]:
        await update.message.reply_text(
            "👋 Hi Benjamin! If you're ready, start with a command like /addgoal, /viewgoals, /checkin, or /summary."
        )
        return

# --- Detect addgoal / add goal keyword trigger (case insensitive) ---
    addgoal_trigger = re.match(
        r"^(?:addgoal|add\s*goal|ADDGOAL|ADD\s*GOAL)\b",
        user_message.strip(),
        re.IGNORECASE
    )

    # --- Check for numbered/bulleted list of goals ---
    # Always attempt list parsing if addgoal trigger is present
    # Also attempt if message contains a number+dot/bracket pattern
    has_list_pattern = bool(re.search(
        r"(?:\d+[.):\-]|\bone\b|\btwo\b|\bthree\b|\bfour\b|\bfive\b)",
        user_message,
        re.IGNORECASE
    ))

    if addgoal_trigger or has_list_pattern:
        parsed = parse_numbered_goals(user_message)

        if parsed["detected"] and len(parsed["goals"]) >= 2:
            goal_type = parsed["goal_type"]
            goals_list = parsed["goals"]

            if goal_type is None:
                # We have goals but no type — store them and ask
                context.user_data["pending_bulk_goals"] = goals_list
                context.user_data["awaiting_bulk_goal_type"] = True

                goals_preview = "\n".join(
                    [f"{i+1}. {g}" for i, g in enumerate(goals_list)]
                )
                await update.message.reply_text(
                    f"I found {len(goals_list)} goals:\n\n{goals_preview}\n\n"
                    f"What type are these? Reply: daily, weekly, or monthly"
                )
                return

            else:
                # We have both goals and type — save everything
                saved = []
                failed = []
                for goal_text in goals_list:
                    try:
                        add_goal(goal_text, goal_type)
                        saved.append(goal_text)
                    except Exception as e:
                        failed.append(goal_text)
                        print(f"Error saving goal '{goal_text}': {e}")

                context.user_data["last_action"] = "add_goal"
                response = f"✅ Saved {len(saved)} {goal_type} goals:\n\n"
                response += "\n".join([f"• {g}" for g in saved])

                if failed:
                    response += f"\n\n⚠️ Could not save: {', '.join(failed)}"

                await update.message.reply_text(response)
                return

    # --- Handle response when bot asked for bulk goal type ---
    if context.user_data.get("awaiting_bulk_goal_type"):
        goal_type = user_message.strip().lower()

        if goal_type not in ["daily", "weekly", "monthly"]:
            await update.message.reply_text(
                "Please reply with exactly: daily, weekly, or monthly"
            )
            return

        bulk_goals = context.user_data.pop("pending_bulk_goals", [])
        context.user_data.pop("awaiting_bulk_goal_type", None)

        if not bulk_goals:
            await update.message.reply_text(
                "Something went wrong. Please try adding your goals again."
            )
            return

        saved = []
        failed = []
        for goal_text in bulk_goals:
            try:
                add_goal(goal_text, goal_type)
                saved.append(goal_text)
            except Exception as e:
                failed.append(goal_text)
                print(f"Error saving goal '{goal_text}': {e}")

        context.user_data["last_action"] = "add_goal"
        response = f"✅ Saved {len(saved)} {goal_type} goals:\n\n"
        response += "\n".join([f"• {g}" for g in saved])

        if failed:
            response += f"\n\n⚠️ Could not save: {', '.join(failed)}"

        await update.message.reply_text(response)
        return

    # Recognize direct goal creation like 'Daily goal: Read 10 pages.'
    direct_goal_response = parse_direct_goal_message(user_message)
    if direct_goal_response:
        context.user_data["last_action"] = "add_goal"
        await update.message.reply_text(direct_goal_response)
        return
    # Detect natural language goal addition intent
    goal_addition = detect_goal_addition_intent(user_message)
    if goal_addition["detected"]:
        context.user_data["last_action"] = "add_goal"
        context.user_data["pending_goal_text"] = goal_addition["goal_text"]
        
        if goal_addition["needs_type"]:
            # We have the goal text but need to ask for type
            await update.message.reply_text(goal_addition["response"])
            # Set state to wait for goal type
            context.user_data["awaiting_goal_type"] = True
            return
    
    # If user is waiting to provide goal type, capture it
    if context.user_data.get("awaiting_goal_type"):
        goal_type = normalized.strip().lower()
        
        if goal_type not in ["Daily", "Weekly", "Monthly"]:
            await update.message.reply_text(
                "Please reply with exactly: Daily, Weekly, or Monthly"
            )
            return
        
        goal_text = context.user_data.pop("pending_goal_text", None)
        context.user_data.pop("awaiting_goal_type", None)
        
        if goal_text:
            try:
                add_goal(goal_text, goal_type)
                await update.message.reply_text(
                    f"✅ Goal saved.\n\n"
                    f"Goal: {goal_text}\n"
                    f"Type: {goal_type.capitalize()}"
                )
                return
            except Exception as e:
                await update.message.reply_text("Something went wrong saving your goal. Please try again.")
                print(f"Error saving goal: {e}")
                return

    # Detect goal completion intent
    goal_completion = detect_goal_completion_intent(user_message)
    if goal_completion["detected"]:
        if goal_completion.get("all_goals"):
            try:
                completed_count = complete_all_goals()
                context.user_data["last_action"] = "goal_completed"
                if completed_count == 0:
                    await update.message.reply_text(
                        "All your goals are already marked done for today."
                    )
                else:
                    await update.message.reply_text(
                        f"✅ Marked {completed_count} goal{'' if completed_count == 1 else 's'} as done for today."
                    )
                return
            except Exception as e:
                await update.message.reply_text(
                    "Something went wrong recording your goals. Please try again."
                )
                print(f"Error recording all goals completion: {e}")
                return

        matched_goals = goal_completion["matched_goals"]
        
        if len(matched_goals) == 1:
            # We have an exact match - record the completion
            goal_id = goal_completion["matched_goal_id"]
            goal_text = goal_completion["matched_goal_text"]
            
            try:
                record_checkin(goal_id, "done")
                context.user_data["last_action"] = "goal_completed"
                await update.message.reply_text(goal_completion["response"])
                return
            except Exception as e:
                await update.message.reply_text("Something went wrong recording your goal completion. Please try again.")
                print(f"Error recording completion: {e}")
                return
        
        else:
            # Multiple matches or no matches - ask for clarification
            context.user_data["last_action"] = "goal_completion"
            context.user_data["completion_keywords"] = goal_completion["keywords"]
            await update.message.reply_text(goal_completion["response"])
            return

    # If user is clarifying which goal they completed
    if context.user_data.get("last_action") == "goal_completion":
        completion_keywords = context.user_data.get("completion_keywords", "")
        
        # Search for goals matching what they said
        matched_goals = search_goals_by_keyword(user_message)
        
        if matched_goals:
            # Use the first match (most recent)
            goal_id, goal_text, goal_type = matched_goals[0]
            
            try:
                record_checkin(goal_id, "done")
                context.user_data.pop("completion_keywords", None)
                context.user_data["last_action"] = "goal_completed"
                await update.message.reply_text(f"✅ Marked as done: {goal_text}")
                return
            except Exception as e:
                await update.message.reply_text("Something went wrong recording your goal completion. Please try again.")
                print(f"Error recording completion: {e}")
                return
        else:
            await update.message.reply_text(
                f"I couldn't find that goal. Use /viewgoals to see all your goals, or try describing it differently."
            )
            return

    # Recognize conversational closers when done with the prompt.
    if normalized in ["cool", "okay", "ok", "thanks", "thank you"]:
        last_action = context.user_data.get("last_action")
        if last_action == "add_goal":
            await update.message.reply_text(
                "Nice one. Goal saved. Use /checkin when you want to log progress, or /viewgoals to review your list."
            )
            return
        if last_action == "checkin_complete":
            await update.message.reply_text(
                "Good work. Check-in finished. Use /summary to review today, or /addgoal to add another."
            )
            return
        if last_action == "summary":
            await update.message.reply_text(
                "Summary noted. Use /addgoal to add a new goal, or /checkin when you're ready to log progress."
            )
            return
        if last_action == "view_goals":
            await update.message.reply_text(
                "Got it. Use /addgoal to add more goals or /checkin to update today."
            )
            return
        if last_action == "goal_completed":
            await update.message.reply_text(
                "Awesome! Goal logged. Use /summary to see your progress, or /addgoal to add another goal."
            )
            return

        await update.message.reply_text(
            "👍 Got it. If you're done, you can use /addgoal to add a goal, /viewgoals to review your goals, or /summary to see progress."
        )
        return

    await update.message.reply_text(
        "I no longer use AI. Please use /addgoal, /viewgoals, /checkin, or /summary."
    )

def main():
    """Starts the bot with the scheduler."""
    # Initialize the database first
    initialize_database()

    # Build the application with post_init hook
    app = (
        ApplicationBuilder()
        .token(BOT_TOKEN)
        .post_init(post_init)
        .build()
    )

    # Conversation handler for adding goals
    add_goal_handler = ConversationHandler(
        entry_points=[CommandHandler("addgoal", add_goal_start)],
        states={
            WAITING_FOR_GOAL_TEXT: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_goal_get_text)],
            WAITING_FOR_GOAL_TYPE: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_goal_get_type)],
            WAITING_FOR_GOAL_TIME: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_goal_get_time)],
            WAITING_FOR_GOAL_DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_goal_get_date)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    # Conversation handler for check-ins
    checkin_handler = ConversationHandler(
        entry_points=[CommandHandler("checkin", manual_checkin)],
        states={
            WAITING_FOR_CHECKIN_RESPONSE: [MessageHandler(filters.TEXT & ~filters.COMMAND, checkin_response)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    # Conversation handler for repeating goals
    repeating_goal_handler = ConversationHandler(
        entry_points=[CommandHandler("addrepeatinggoal", add_repeating_goal_start)],
        states={
            WAITING_FOR_REPEATING_GOAL_TEXT: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_repeating_goal_get_text)],
            WAITING_FOR_REPEATING_GOAL_DAYS: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_repeating_goal_get_days)],
            WAITING_FOR_REPEATING_GOAL_LENGTH: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_repeating_goal_get_length)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    # Conversation handler for removing goals
    remove_goal_handler = ConversationHandler(
        entry_points=[CommandHandler("removegoal", remove_goal_start)],
        states={
            WAITING_FOR_REMOVE_GOAL_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, remove_goal_by_id)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    # Conversation handler for editing goals
    edit_goal_handler = ConversationHandler(
        entry_points=[CommandHandler("editgoal", edit_goal_start)],
        states={
            WAITING_FOR_EDIT_GOAL_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_goal_choose)],
            WAITING_FOR_EDIT_ACTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_goal_action)],
            WAITING_FOR_EDIT_NEW_TEXT: [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_goal_new_text)],
            WAITING_FOR_EDIT_NEW_SCHEDULE: [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_goal_new_schedule)],
            WAITING_FOR_EDIT_NEW_LENGTH: [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_goal_schedule_length)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

# Register all handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("viewgoals", view_goals))
    app.add_handler(CommandHandler("viewrepeating", view_repeating_goals))
    app.add_handler(CommandHandler("summary", summary))
    app.add_handler(add_goal_handler)
    app.add_handler(checkin_handler)
    app.add_handler(repeating_goal_handler)
    app.add_handler(remove_goal_handler)
    app.add_handler(edit_goal_handler)

    # This must be registered LAST
    # It catches any message that is not a command
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_free_text))
    print("Bot is running with scheduler. Press Ctrl+C to stop.")
    app.run_polling()



if __name__ == "__main__":
    main()