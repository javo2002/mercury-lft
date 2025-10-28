# In daily_planner.py

from datetime import datetime
from database import SessionLocal, Mailbox, Signal # Import Signal if needed for dict keys
import ai_services
from risk_manager import get_market_condition
# --- NEW: Import text from SQLAlchemy ---
from sqlalchemy import text

def run_daily_planner(screener_results): # Accepts screener results directly now
    """
    Refactored to generate the daily plan.
    --- FIX: Use text() for raw SQL ---
    """
    print("--- Generating Daily Trade Plan ---")
    session = SessionLocal()
    today = datetime.now().strftime('%Y-%m-%d')
    
    try:
        market_condition = get_market_condition()
        
        # Get signals generated earlier in the pipeline
        # --- FIX: Wrap SQL query in text() ---
        signals_query = text(f"SELECT ticker, live_signal FROM signals WHERE date = '{today}' AND live_signal != 'NONE'")
        signals_result = session.execute(signals_query).mappings().fetchall() # Use mappings() for dict-like rows
        signals = [dict(s) for s in signals_result] # Convert to list of dicts
        # -------------------------------------
        
        # --- FIX: Fetch events AFTER getting signals ---
        economic_events = ai_services.get_economic_events() # Uses cache
        
        plan_content = ai_services.generate_daily_trade_plan(
            market_condition, 
            signals, # Pass the list of dicts
            economic_events
        )
        
        mailbox_entry = Mailbox(
            timestamp=datetime.now().isoformat(),
            subject=f"Daily Trade Plan: {today}",
            content=plan_content,
            status='unread'
        )
        session.add(mailbox_entry)
        session.commit()
        print("--- Daily plan saved to mailbox. ---")
        
    except Exception as e:
        print(f"ERROR generating daily plan: {e}")
        session.rollback() # Add rollback on error
    finally:
        session.close()
