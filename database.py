# database.py
# Handles all database operations for the accountability bot
# Uses SQLite - a lightweight database stored as a local file

import sqlite3

# This is the name of the database file that will be created
DATABASE_FILE = "accountability.db"


def get_connection():
    """Create and return a database connection."""
    return sqlite3.connect(DATABASE_FILE)


def initialize_database():
    """
    Creates the database tables if they don't already exist.
    Safe to run multiple times - won't overwrite existing data.
    """
    conn = get_connection()
    cursor = conn.cursor()

    # Table to store your goals
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS goals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            goal_text TEXT NOT NULL,
            goal_type TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Table to store your daily check-in responses
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS checkins (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            goal_id INTEGER NOT NULL,
            status TEXT NOT NULL,
            checked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (goal_id) REFERENCES goals (id)
        )
    """)

    conn.commit()
    conn.close()
    print("Database initialized successfully.")


def add_goal(goal_text, goal_type):
    """
    Adds a new goal to the database.
    goal_type should be: 'daily', 'weekly', or 'monthly'
    """
    # Input validation - only allow safe goal types
    allowed_types = ["daily", "weekly", "monthly"]
    if goal_type not in allowed_types:
        raise ValueError(f"goal_type must be one of {allowed_types}")

    conn = get_connection()
    cursor = conn.cursor()

    # Using parameterized queries to prevent SQL injection
    cursor.execute(
        "INSERT INTO goals (goal_text, goal_type) VALUES (?, ?)",
        (goal_text, goal_type)
    )

    conn.commit()
    conn.close()


def get_goals(goal_type):
    """
    Retrieves all goals of a specific type.
    goal_type should be: 'daily', 'weekly', or 'monthly'
    """
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT id, goal_text FROM goals WHERE goal_type = ?",
        (goal_type,)
    )

    goals = cursor.fetchall()
    conn.close()
    return goals


def record_checkin(goal_id, status):
    """
    Records whether a goal was completed or not.
    status should be: 'done' or 'missed'
    """
    allowed_statuses = ["done", "missed"]
    if status not in allowed_statuses:
        raise ValueError(f"status must be one of {allowed_statuses}")

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        "INSERT INTO checkins (goal_id, status) VALUES (?, ?)",
        (goal_id, status)
    )

    conn.commit()
    conn.close()


def get_todays_summary():
    """
    Returns a count of completed vs missed goals for today.
    """
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT status, COUNT(*) as count
        FROM checkins
        WHERE DATE(checked_at) = DATE('now')
        GROUP BY status
    """)

    results = cursor.fetchall()
    conn.close()
    return results

def get_goal_status_today(goal_id):
    """
    Checks whether a specific goal was marked done or missed today.
    Returns 'done', 'missed', or None if no check-in exists for today.
    """
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT status FROM checkins
        WHERE goal_id = ?
        AND DATE(checked_at) = DATE('now')
        ORDER BY checked_at DESC
        LIMIT 1
    """, (goal_id,))

    result = cursor.fetchone()
    conn.close()

    if result:
        return result[0]
    return None

# Run this file directly to initialize the database
if __name__ == "__main__":
    initialize_database()