import os
import sqlite3
from datetime import datetime
from dotenv import load_dotenv

import ai_services
from risk_manager import get_market_condition

# --- CONFIGURATION ---
load_dotenv()
DATABASE_FILE = 'trading_data.db'

def get_db_connection():
    """Establishes a connection to the SQLite database."""
    conn = sqlite3.connect(DATABASE_FILE, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def generate_and_save_daily_plan():
    """
    Generates the AI daily trade plan and saves it as a new 'unread' message
    in the mailbox table. This script should be run once daily via cron.
    """
    print("--- [ Generating Daily AI Trade Plan ] ---")
    try:
        # 1. Gather data required for the plan
        market_condition = get_market_condition()
        today = datetime.now().strftime('%Y-%m-%d')
        conn = get_db_connection()
        signals = conn.execute(
            "SELECT ticker, live_signal FROM signals WHERE date = ? AND live_signal != 'NONE'",
            (today,)
        ).fetchall()
        
        # We can also get economic events from AI services
        economic_events = ai_services.get_economic_events()

        # 2. Generate the plan using the AI service
        print("Data gathered. Requesting trade plan from AI...")
        plan_content = ai_services.generate_daily_trade_plan(
            market_condition,
            [dict(s) for s in signals],
            economic_events
        )
        print("AI plan generated successfully.")

        # 3. Save the generated plan to the mailbox
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        subject = f"Daily Trade Plan - {datetime.now().strftime('%B %d, %Y')}"
        
        cursor = conn.cursor()
        cursor.execute(
            'INSERT INTO mailbox (timestamp, subject, content, status) VALUES (?, ?, ?, ?)',
            (timestamp, subject, plan_content, 'unread')
        )
        conn.commit()
        conn.close()
        
        print(f"Successfully saved new trade plan to the database mailbox.")
        print("--- [ Daily Plan Generation Complete ] ---")

    except Exception as e:
        print(f"An error occurred during daily plan generation: {e}")

if __name__ == "__main__":
    generate_and_save_daily_plan()
