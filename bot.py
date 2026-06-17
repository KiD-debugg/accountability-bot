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
    get_goal_by_id,
    record_checkin,
    get_todays_summary,
    get_goal_status_today,
    update_goal_text,
    update_repeating_goal_schedule,
    delete_goal,
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
    """Receives the goal type and saves everything to the database."""
    goal_type = update.message.text.strip().lower()

    if goal_type not in ["daily", "weekly", "monthly"]:
        await update.message.reply_text(
            "That is not valid. Please reply with exactly: daily, weekly, or monthly"
        )
        return WAITING_FOR_GOAL_TYPE

    goal_text = context.user_data.get("goal_text")

    try:
        add_goal(goal_text, goal_type)
        context.user_data["last_action"] = "add_goal"
        await update.message.reply_text(
            f"Goal saved.\n\n"
            f"Goal: {goal_text}\n"
            f"Type: {goal_type.capitalize()}"
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

    for goal_type in ["daily", "weekly", "monthly"]:
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
    for goal_type in ["daily", "weekly", "monthly"]:
        goals = get_goals(goal_type)

        if not goals:
            continue

        any_goals_found = True
        message += f"{'📅' if goal_type == 'daily' else '📆' if goal_type == 'weekly' else '🗓️'} "
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
    match = re.match(r"^(daily|weekly|monthly)\s+goal\s*[:\-]?\s*(.+)$", normalized, re.IGNORECASE)
    if not match:
        return None

    goal_type = match.group(1).lower()
    goal_text = match.group(2).strip()
    if not goal_text:
        return (
            "Please provide a goal after the type. Example: Daily goal: Read 10 pages."
        )

    add_goal(goal_text, goal_type)
    return f"✅ Goal saved: {goal_text} ({goal_type})"


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

    # Recognize direct goal creation like 'Daily goal: Read 10 pages.'
    direct_goal_response = parse_direct_goal_message(user_message)
    if direct_goal_response:
        context.user_data["last_action"] = "add_goal"
        await update.message.reply_text(direct_goal_response)
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