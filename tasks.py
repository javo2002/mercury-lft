import subprocess
from celery_app import celery
from celery.schedules import crontab
from config import settings
from datetime import datetime, timedelta
# ... (other necessary imports) ...

# --- Refactored Imports ---
from research.backtester import run_backtest, SmaCross
from screener import run_screener
from daily_signal_report import run_signal_generation
from news_analyzer import run_news_analysis
from daily_planner import run_daily_planner

# --- CORE PIPELINE TASKS ---
@celery.task
def run_screener_task():
    print("--- [Celery Task] Kicking off screener... ---")
    return run_screener()

@celery.task
def run_signal_report_task(screener_results):
    print("--- [Celery Task] Kicking off signal report... ---")
    run_signal_generation(screener_results)
    return screener_results

@celery.task
def run_news_analyzer_task(screener_results):
    print("--- [Celery Task] Kicking off news analyzer... ---")
    run_news_analysis(screener_results)
    return screener_results

@celery.task
def run_daily_planner_task(screener_results):
    print("--- [Celery Task] Kicking off daily planner... ---")
    run_daily_planner(screener_results)

@celery.task
def run_morning_pipeline():
    print("--- [Celery Task] SUBMITTING MORNING PIPELINE ---")
    (
        run_screener_task.s() |
        run_signal_report_task.s() |
        run_news_analyzer_task.s() |
        run_daily_planner_task.s()
    ).apply_async()

# --- NEW: TRADING BOT TASK ---
@celery.task
def run_master_bot_task():
    """Runs the main trading bot logic."""
    print("--- [Celery Task] Kicking off master bot run... ---")
    # We use subprocess to run it in its own isolated process space,
    # similar to how cron would have worked, ensuring clean state each run.
    subprocess.run(['python', 'master_bot.py'], check=True)
    print("--- [Celery Task] Master bot run finished. ---")


# --- RESEARCH & BACKTESTING TASKS ---
@celery.task
def run_backtest_task(ticker, strategy_name, params):
    # ... (task logic remains the same) ...
    pass

# --- AUTOMATED SCHEDULE ---
celery.conf.beat_schedule = {
    'run-morning-pipeline-daily': {
        'task': 'tasks.run_morning_pipeline',
        # Runs every weekday (Mon-Fri) at 8:00 AM EST (12:00 UTC)
        'schedule': crontab(hour=12, minute=0, day_of_week='1-5'),
    },
    # --- NEW: SCHEDULE FOR MASTER BOT ---
    'run-master-bot-intraday': {
        'task': 'tasks.run_master_bot_task',
        # Runs every 15 minutes during market hours
        # Mon-Fri, 9:30 AM EST (13:30 UTC) to 4:00 PM EST (20:00 UTC)
        'schedule': crontab(minute='*/15', hour='13-19', day_of_week='1-5'),
    },
}
celery.conf.timezone = 'UTC'

