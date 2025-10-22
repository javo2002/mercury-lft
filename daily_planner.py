from datetime import datetime
from database import SessionLocal, Mailbox
import ai_services
from risk_manager import get_market_condition

def run_daily_planner(screener_results): # Accepts data
    """
    Refactored to generate the daily plan.
    """
    print("--- Generating Daily Trade Plan ---")
    session = SessionLocal()
    today = datetime.now().strftime('%Y-%m-%d')
    
    try:
        market_condition = get_market_condition()
        
        # Get signals generated earlier in the pipeline
        signals_query = f"SELECT ticker, live_signal FROM signals WHERE date = '{today}' AND live_signal != 'NONE'"
        signals = session.execute(signals_query).fetchall()
        
        economic_events = ai_services.get_economic_events()
        
        plan_content = ai_services.generate_daily_trade_plan(
            market_condition, 
            [dict(s) for s in signals], 
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
    finally:
        session.close()
