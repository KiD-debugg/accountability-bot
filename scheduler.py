# scheduler.py
# Handles all automatic scheduled messages for the accountability bot
# All times are in East Africa Time (EAT) which is UTC+3

import logging
from datetime import datetime, timedelta
import pytz
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from telegram import Bot
from config import BOT_TOKEN, YOUR_USER_ID
from database import (
    get_goals,
    get_todays_summary,
    get_goal_status_today,
    get_repeating_goals_for_weekday,
    get_time_based_goals,
)

# Set up logging so we can see scheduler activity in the terminal
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Define Nairobi timezone
NAIROBI_TZ = pytz.timezone("Africa/Nairobi")


async def send_morning_briefing(bot: Bot):
    """
    Sent at 6:00 AM EAT every day.
    Lists all goals for the day as a reminder of what Benjamin 
    is expected to accomplish.
    """
    try:
        message = "🌅 GOOD MORNING BENJAMIN\n"
        message += "─────────────────\n\n"
        message += "Here are your goals for today. No excuses.\n\n"

        any_goals = False

        for goal_type in ["daily", "weekly", "monthly"]:
            goals = get_goals(goal_type)

            if not goals:
                continue

            any_goals = True
            emoji = "📅" if goal_type == "daily" else "📆" if goal_type == "weekly" else "🗓️"
            message += f"{emoji} {goal_type.upper()} GOALS\n"
            message += "─────────────────\n"

            for _, goal_text in goals:
                message += f"• {goal_text}\n"

            message += "\n"

        if not any_goals:
            message += "You have no goals set yet. Use /addgoal to add some.\n"
        else:
            message += "─────────────────\n"
            message += "I will check in with you at 5:00 PM.\n"
            message += "Make sure you have something to show."

        await bot.send_message(chat_id=YOUR_USER_ID, text=message)
        logger.info("Morning briefing sent successfully.")

    except Exception as e:
        logger.error(f"Failed to send morning briefing: {e}")


async def send_checkin_reminder(bot: Bot):
    """
    Sent at 5:00 PM EAT every day.
    Reminds Benjamin to do his check-in before leaving work.
    """
    try:
        # Check if he has already checked in today
        all_goals = (
            get_goals("daily") +
            get_goals("weekly") +
            get_goals("monthly")
        )

        today = datetime.now(NAIROBI_TZ).strftime('%A')
        repeated_goals = get_repeating_goals_for_weekday(today)

        if not all_goals and not repeated_goals:
            return

        already_checked = any(
            get_goal_status_today(goal_id) is not None
            for goal_id, _ in all_goals
        ) or any(
            get_goal_status_today(goal_id) is not None
            for goal_id, _, _, _ in repeated_goals
        )

        if already_checked:
            message = (
                "✅ I can see you have already checked in today.\n\n"
                "Use /summary to see your results."
            )
        else:
            message = (
                "⏰ 5:00 PM CHECK-IN REMINDER\n"
                "─────────────────\n\n"
                "It is time to account for your day.\n\n"
                "Use /checkin now to record your progress.\n\n"
                "Do not ignore this."
            )

        await bot.send_message(chat_id=YOUR_USER_ID, text=message)
        logger.info("Check-in reminder sent successfully.")

    except Exception as e:
        logger.error(f"Failed to send check-in reminder: {e}")


async def send_repeating_goal_summary(bot: Bot):
    """
    Sent every day after the morning briefing to review today's repeating goals.
    """
    try:
        today = datetime.now(NAIROBI_TZ).strftime('%A')
        goals = get_repeating_goals_for_weekday(today)

        if not goals:
            return

        message = "🔁 TODAY'S REPEATING GOALS\n"
        message += "─────────────────\n\n"
        message += "These goals are set to remind you today.\n\n"

        for goal_id, goal_text, repeat_days, repeat_length in goals:
            days_display = repeat_days.replace(',', ', ') if repeat_days else "None"
            length_display = f"{repeat_length} days" if repeat_length else "No limit"
            message += (
                f"ID {goal_id}: {goal_text}\n"
                f"  Days: {days_display}\n"
                f"  Length: {length_display}\n\n"
            )

        message += "─────────────────\n"
        message += "Use /checkin when you are ready to log progress."

        await bot.send_message(chat_id=YOUR_USER_ID, text=message)
        logger.info("Repeating goal summary sent successfully.")

    except Exception as e:
        logger.error(f"Failed to send repeating goal summary: {e}")


async def send_timed_goal_reminders(bot: Bot):
    """
    Runs every minute and sends reminders 20 minutes before goals with a set time.
    """
    try:
        now = datetime.now(NAIROBI_TZ)
        reminder_time = (now + timedelta(minutes=20)).strftime('%H:%M')
        goals = get_time_based_goals(reminder_time)

        if not goals:
            return

        for goal_id, goal_text, goal_type, goal_time in goals:
            message = (
                f"⏰ REMINDER: {goal_text}\n"
                f"You asked to be reminded at {goal_time}. This is your 20-minute warning."
            )
            await bot.send_message(chat_id=YOUR_USER_ID, text=message)

        logger.info(f"Sent timed goal reminders for {reminder_time}.")

    except Exception as e:
        logger.error(f"Failed to send timed goal reminders: {e}")


async def send_strict_followup(bot: Bot):
    """
    Sent at 5:30 PM EAT every day.
    If Benjamin has still not checked in, this message is strict.
    """
    try:
        all_goals = (
            get_goals("daily") +
            get_goals("weekly") +
            get_goals("monthly")
        )

        if not all_goals:
            return

        already_checked = any(
            get_goal_status_today(goal_id) is not None
            for goal_id, _ in all_goals
        )

        # Only send if he still has not checked in
        if not already_checked:
            message = (
                "🔴 YOU HAVE NOT CHECKED IN\n"
                "─────────────────\n\n"
                "It is now 5:30 PM and you have not recorded your progress.\n\n"
                "This is exactly the behaviour that keeps people stuck.\n\n"
                "Use /checkin right now.\n"
                "No more delays."
            )

            await bot.send_message(chat_id=YOUR_USER_ID, text=message)
            logger.info("Strict follow-up sent successfully.")
        else:
            logger.info("Follow-up skipped — user already checked in.")

    except Exception as e:
        logger.error(f"Failed to send strict follow-up: {e}")


async def send_weekly_review(bot: Bot):
    """
    Sent every Sunday at 8:00 PM EAT.
    Reviews weekly goals specifically.
    """
    try:
        goals = get_goals("weekly")

        message = "📆 WEEKLY REVIEW — SUNDAY\n"
        message += "─────────────────\n\n"

        if not goals:
            message += "You have no weekly goals set.\n"
            message += "Use /addgoal to set some this week."
        else:
            message += "Your weekly goals:\n\n"

            for _, goal_text in goals:
                message += f"• {goal_text}\n"

            message += "\n─────────────────\n"
            message += "Reflect honestly on this past week.\n"
            message += "Use /checkin to record your weekly progress.\n\n"
            message += "Then plan what you will do differently next week."

        await bot.send_message(chat_id=YOUR_USER_ID, text=message)
        logger.info("Weekly review sent successfully.")

    except Exception as e:
        logger.error(f"Failed to send weekly review: {e}")


async def send_monthly_review(bot: Bot):
    """
    Sent on the last day of each month at 8:00 PM EAT.
    Reviews monthly goals specifically.
    """
    try:
        goals = get_goals("monthly")

        message = "🗓️ MONTHLY REVIEW\n"
        message += "─────────────────\n\n"

        if not goals:
            message += "You have no monthly goals set.\n"
            message += "Use /addgoal to set some next month."
        else:
            message += "Your monthly goals were:\n\n"

            for _, goal_text in goals:
                message += f"• {goal_text}\n"

            message += "\n─────────────────\n"
            message += "A full month has passed.\n"
            message += "Use /checkin to record your monthly progress.\n\n"
            message += "Then set stronger goals for next month."

        await bot.send_message(chat_id=YOUR_USER_ID, text=message)
        logger.info("Monthly review sent successfully.")

    except Exception as e:
        logger.error(f"Failed to send monthly review: {e}")


async def send_noon_check(bot: Bot):
    """
    Sent at 12:00 PM (noon) EAT every day.
    A mid-day reminder to keep Benjamin on track.
    """
    try:
        message = "⏰ MIDDAY CHECK-IN\n"
        message += "─────────────────\n\n"
        message += "It's noon. How is your day going?\n\n"
        message += "Have you made progress on your goals yet?\n\n"
        message += "You still have the rest of the day to achieve something.\n"
        message += "Don't waste it.\n\n"
        message += "Use /summary to see what you've done so far."

        await bot.send_message(chat_id=YOUR_USER_ID, text=message)
        logger.info("Noon check-in sent successfully.")

    except Exception as e:
        logger.error(f"Failed to send noon check-in: {e}")


async def send_evening_reflection(bot: Bot):
    """
    Sent at 9:00 PM EAT every day.
    An evening reflection message to prepare for tomorrow.
    """
    try:
        message = "🌙 EVENING REFLECTION\n"
        message += "─────────────────\n\n"
        message += "It is 9:00 PM. The day is almost over.\n\n"
        message += "Reflect on what you accomplished today.\n"
        message += "What did you do well? What could you have done better?\n\n"
        message += "Use /summary to see your day's performance.\n\n"
        message += "Tomorrow is a fresh start to do better."

        await bot.send_message(chat_id=YOUR_USER_ID, text=message)
        logger.info("Evening reflection sent successfully.")

    except Exception as e:
        logger.error(f"Failed to send evening reflection: {e}")



def create_scheduler(bot: Bot) -> AsyncIOScheduler:
    """
    Creates and configures the scheduler with all jobs.
    Returns the scheduler ready to start.
    """
    scheduler = AsyncIOScheduler(timezone=NAIROBI_TZ)

    # 6:00 AM every day — morning briefing
    scheduler.add_job(
        send_morning_briefing,
        CronTrigger(hour=6, minute=0, timezone=NAIROBI_TZ),
        args=[bot],
        id="morning_briefing",
        name="Morning Briefing"
    )

    # 5:00 PM every day — check-in reminder
    scheduler.add_job(
        send_checkin_reminder,
        CronTrigger(hour=17, minute=0, timezone=NAIROBI_TZ),
        args=[bot],
        id="checkin_reminder",
        name="Check-in Reminder"
    )

    # 5:30 PM every day — strict follow-up
    scheduler.add_job(
        send_strict_followup,
        CronTrigger(hour=17, minute=30, timezone=NAIROBI_TZ),
        args=[bot],
        id="strict_followup",
        name="Strict Follow-up"
    )

    # 8:30 AM every day — repeating goal summary
    scheduler.add_job(
        send_repeating_goal_summary,
        CronTrigger(hour=8, minute=30, timezone=NAIROBI_TZ),
        args=[bot],
        id="repeating_goal_summary",
        name="Repeating Goal Summary"
    )

    # Every minute — timed goal reminders (remind 20 minutes before goal_time)
    scheduler.add_job(
        send_timed_goal_reminders,
        CronTrigger(minute='*', timezone=NAIROBI_TZ),
        args=[bot],
        id="timed_goal_reminders",
        name="Timed Goal Reminders"
    )

    # Every Sunday at 8:00 PM — weekly review
    scheduler.add_job(
        send_weekly_review,
        CronTrigger(day_of_week="sun", hour=20, minute=0, timezone=NAIROBI_TZ),
        args=[bot],
        id="weekly_review",
        name="Weekly Review"
    )

    # Last day of every month at 8:00 PM — monthly review
    scheduler.add_job(
        send_monthly_review,
        CronTrigger(day="last", hour=20, minute=0, timezone=NAIROBI_TZ),
        args=[bot],
        id="monthly_review",
        name="Monthly Review"
    )

    # 12:00 PM every day — noon check-in
    scheduler.add_job(
        send_noon_check,
        CronTrigger(hour=12, minute=0, timezone=NAIROBI_TZ),
        args=[bot],
        id="noon_check",
        name="Noon Check-in"
    )

    # 9:00 PM every day — evening reflection
    scheduler.add_job(
        send_evening_reflection,
        CronTrigger(hour=21, minute=0, timezone=NAIROBI_TZ),
        args=[bot],
        id="evening_reflection",
        name="Evening Reflection"
    )

    return scheduler