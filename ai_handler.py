# ai_handler.py
# Updated to use google-genai (replaces deprecated google-generativeai)

from google import genai
from google.genai import types
import json
import logging
from config import GEMINI_API_KEY
from database import (
    add_goal,
    get_goals,
    get_goal_status_today,
    record_checkin,
    get_todays_summary
)

logger = logging.getLogger(__name__)

# Initialize the client with new library syntax
client = genai.Client(api_key=GEMINI_API_KEY)

# Conversation history storage
conversation_history = []


def build_system_context():
    """Builds current goal state for Gemini context."""
    context = ""
    for goal_type in ["daily", "weekly", "monthly"]:
        goals = get_goals(goal_type)
        if goals:
            context += f"\n{goal_type.upper()} GOALS:\n"
            for goal_id, goal_text in goals:
                status = get_goal_status_today(goal_id)
                status_label = status if status else "not checked in"
                context += f"  - ID:{goal_id} | {goal_text} | Status: {status_label}\n"
    if not context:
        context = "No goals have been added yet."
    return context


def process_message(user_message: str) -> str:
    """
    Sends the user message to Gemini and returns a response.
    Handles action extraction and database updates.
    """
    global conversation_history

    goal_context = build_system_context()

    system_prompt = f"""
You are a strict personal accountability assistant for Benjamin Ochieng,
a Civil and Structural Engineer in Nairobi, Kenya transitioning into Data and Analytics.

Your personality:
- Direct and strict but respectful
- You do not accept excuses
- You celebrate genuine achievements briefly
- You speak plainly and concisely

Current goals:
{goal_context}

You can perform actions by including a JSON block at the end of your response:

1. ADD A GOAL:
ACTION:{{"type": "add_goal", "goal_text": "the goal", "goal_type": "daily/weekly/monthly"}}

2. MARK A GOAL:
ACTION:{{"type": "record_checkin", "goal_id": 1, "status": "done/missed"}}

3. NO ACTION — just conversation, no ACTION block needed.

Rules:
- Respond in plain text first, then ACTION block if needed
- Keep responses short and direct
- If goal type is unclear, ask for clarification
- Match completions to the closest existing goal by name
- Never invent goals that do not exist
- Always respond in English
"""

    # Add user message to history
    conversation_history.append(
        types.Content(role="user", parts=[types.Part(text=user_message)])
    )

    # Keep history to last 20 messages
    if len(conversation_history) > 20:
        conversation_history = conversation_history[-20:]

    try:
        response = client.models.generate_content(
            model="gemini-2.0-flash-lite",
            config=types.GenerateContentConfig(
                system_instruction=system_prompt,
                max_output_tokens=500,
                temperature=0.7,
            ),
            contents=conversation_history
        )

        ai_response = response.text

        # Add response to history
        conversation_history.append(
            types.Content(role="model", parts=[types.Part(text=ai_response)])
        )

        # Check for and execute any action
        if "ACTION:" in ai_response:
            parts = ai_response.split("ACTION:")
            clean_response = parts[0].strip()
            action_json = parts[1].strip()
            action_result = execute_action(action_json)
            if action_result:
                return f"{clean_response}\n\n{action_result}"
            return clean_response

        return ai_response

    except Exception as e:
        logger.error(f"Gemini API error: {e}")
        return "I encountered an error. Please try again in a moment."


def execute_action(action_json: str) -> str:
    """Parses and executes the action from Gemini's response."""
    try:
        action = json.loads(action_json)
        action_type = action.get("type")

        if action_type == "add_goal":
            goal_text = action.get("goal_text")
            goal_type = action.get("goal_type")
            if not goal_text or not goal_type:
                return "Could not save goal — missing information."
            if goal_type not in ["daily", "weekly", "monthly"]:
                return "Could not save goal — invalid goal type."
            add_goal(goal_text, goal_type)
            return f"✅ Goal saved: {goal_text} ({goal_type})"

        elif action_type == "record_checkin":
            goal_id = action.get("goal_id")
            status = action.get("status")
            if not goal_id or not status:
                return "Could not record check-in — missing information."
            if status not in ["done", "missed"]:
                return "Could not record check-in — invalid status."
            record_checkin(goal_id, status)
            emoji = "✅" if status == "done" else "❌"
            return f"{emoji} Check-in recorded."

        return ""

    except json.JSONDecodeError:
        logger.error(f"Could not parse action JSON: {action_json}")
        return ""
    except Exception as e:
        logger.error(f"Error executing action: {e}")
        return "Action could not be completed."