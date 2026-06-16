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
logger = logging.getLogger(__name__)
from database import initialize_database, add_goal, get_goals, record_checkin, get_todays_summary, get_goal_status_today
from ai_handler import process_message, build_system_context
# Conversation states - these are just numbers used to track
# where the user is in a multi-step conversation
WAITING_FOR_GOAL_TEXT = 1
WAITING_FOR_GOAL_TYPE = 2
WAITING_FOR_CHECKIN_RESPONSE = 3


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
        "/viewgoals - See all your goals\n"
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
        await update.message.reply_text(
            f"Goal saved.\n\n"
            f"Goal: {goal_text}\n"
            f"Type: {goal_type.capitalize()}"
        )
    except Exception as e:
        await update.message.reply_text("Something went wrong saving your goal. Please try again.")
        print(f"Error saving goal: {e}")

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
            for i, (goal_id, goal_text) in enumerate(goals, 1):
                message += f"{i}. {goal_text}\n"
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
        await update.message.reply_text(
            "Check-in complete. Use /summary to see today's results."
        )
        return ConversationHandler.END


async def summary(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Shows today's detailed check-in summary organised by goal category."""
    if not is_authorized(update.effective_user.id):
        await update.message.reply_text("Unauthorized.")
        return

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

    await update.message.reply_text(message)
    """Shows today's check-in summary."""
    if not is_authorized(update.effective_user.id):
        await update.message.reply_text("Unauthorized.")
        return

    results = get_todays_summary()

    if not results:
        await update.message.reply_text(
            "No check-ins recorded today yet. Use /checkin to start."
        )
        return

    done_count = 0
    missed_count = 0

    for status, count in results:
        if status == "done":
            done_count = count
        elif status == "missed":
            missed_count = count

    total = done_count + missed_count
    percentage = round((done_count / total) * 100) if total > 0 else 0

    if percentage == 100:
        verdict = "Excellent. Every goal completed."
    elif percentage >= 70:
        verdict = "Decent. But you can do better."
    elif percentage >= 40:
        verdict = "Weak. You need to do better tomorrow."
    else:
        verdict = "Unacceptable. Serious improvement needed."

    await update.message.reply_text(
        f"TODAY'S SUMMARY\n\n"
        f"Completed: {done_count}\n"
        f"Missed: {missed_count}\n"
        f"Score: {percentage}%\n\n"
        f"{verdict}"
    )


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
    Catches any message that is not a command and sends it to Gemini.
    This makes the bot conversational and interactive.
    """
    if not is_authorized(update.effective_user.id):
        await update.message.reply_text("Unauthorized.")
        return

    user_message = update.message.text.strip()

    # Show typing indicator while Gemini processes
    await context.bot.send_chat_action(
        chat_id=update.effective_chat.id,
        action="typing"
    )

    # Get response from Gemini
    response = process_message(user_message)

    await update.message.reply_text(response)

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

# Register all handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("viewgoals", view_goals))
    app.add_handler(CommandHandler("summary", summary))
    app.add_handler(add_goal_handler)
    app.add_handler(checkin_handler)

    # This must be registered LAST
    # It catches any message that is not a command
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_free_text))
    print("Bot is running with scheduler. Press Ctrl+C to stop.")
    app.run_polling()



if __name__ == "__main__":
    main()