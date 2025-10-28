import subprocess
from celery_app import celery
from celery.schedules import crontab
from config import settings
from datetime import datetime, timedelta
import json

# --- FIX: Add all necessary imports ---
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame

from research.backtester import run_backtest, SmaCross
from screener import run_screener
from daily_signal_report import run_signal_generation
from news_analyzer import run_news_analysis
from daily_planner import run_daily_planner
from master_bot import run_master_bot

# --- FIX: Import the AI parameter suggester ---
from parameter_optimizer_ai import suggest_new_parameters
from ai_services import get_post_trade_critique

# --- FIX: Import Trade and PostTradeAnalysis ---
from database import SessionLocal, BacktestResult, Signal, Trade, PostTradeAnalysis
from sqlalchemy import func

# --- Alpaca Data Client ---
data_client = StockHistoricalDataClient(settings.API_KEY, settings.API_SECRET)

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
       # run_news_analyzer_task.s() |
        run_daily_planner_task.s()
    ).apply_async()

@celery.task
def run_master_bot_task():
    """Runs the main trading bot logic."""
    print("--- [Celery Task] Kicking off master bot run... ---")
    try:
        run_master_bot()
    except Exception as e:
        print(f"!!! [Celery Task] Master bot run FAILED: {e} !!!")
    print("--- [Celery Task] Master bot run finished. ---")


# --- RESEARCH & BACKTESTING TASKS ---
@celery.task
def run_backtest_task(ticker, strategy_name, params):
    """
    Fetches data and runs the vectorized backtest.
    """
    print(f"--- [Celery Task] Running backtest for {ticker} | {strategy_name} | {params} ---")
    try:
        request_params = StockBarsRequest(
            symbol_or_symbols=[ticker],
            timeframe=TimeFrame.Day,
            start=datetime.now() - timedelta(days=5*365) # 5 years of data
        )
        barset_df = data_client.get_stock_bars(request_params).df
        
        if barset_df.empty:
            print(f"No data found for {ticker}.")
            return

        # --- FIX: Pass ticker into run_backtest ---
        result_id = run_backtest(
            ticker=ticker,
            data=barset_df,
            strategy_name=strategy_name,
            strategy_params=params
        )
        
        if result_id:
            print(f"--- [Celery Task] Backtest complete. Result ID: {result_id} ---")
        else:
            print("--- [Celery Task] Backtest finished with no result. ---")
            
    except Exception as e:
        print(f"!!! [Celery Task] Backtest FAILED for {ticker}: {e} !!!")


# --- NEW: AI OPTIMIZATION FLYWHEEL (REWRITTEN) ---
@celery.task
def run_ai_optimization_loop():
    """
    --- REWRITTEN ---
    Autonomously optimizes ALL strategies against ALL known tickers.
    """
    print("--- [Celery Task] Kicking off FULL AI Optimization Flywheel ---")
    session = SessionLocal()
    
    try:
        ticker_rows = session.query(Signal.ticker).distinct().all()
        all_tickers = [row[0] for row in ticker_rows]
        print(f"Found {len(all_tickers)} unique tickers to optimize.")

        all_strategies = list(STRATEGY_MAP.keys())
        print(f"Found {len(all_strategies)} strategies to test: {', '.join(all_strategies)}")

        for strategy_name in all_strategies:
            
            # --- FIX: Get the strategy class and its default params ---
            strategy_class = STRATEGY_MAP.get(strategy_name)
            if not strategy_class:
                print(f"Could not find strategy class for {strategy_name}. Skipping.")
                continue
            
            try:
                default_params = strategy_class.get_default_params()
            except Exception as e:
                print(f"Error getting default params for {strategy_name}: {e}. Skipping.")
                continue
            
            # -----------------------------------------------------------

            for ticker in all_tickers:
                print(f"\n--- Optimizing {strategy_name} for {ticker} ---")
                
                best_run = session.query(BacktestResult).filter(
                    BacktestResult.strategy_name == strategy_name,
                    BacktestResult.ticker == ticker
                ).order_by(BacktestResult.sharpe_ratio.desc()).first()
                
                if best_run and best_run.parameters:
                    print(f"  Found best run ({best_run.id}) with Sharpe: {best_run.sharpe_ratio}")
                    try:
                        current_params = eval(best_run.parameters)
                    except:
                        current_params = default_params # Fallback to defaults
                else:
                    print(f"  No previous runs found. Using defaults.")
                    # --- FIX: Use dynamic defaults, not hard-coded ones ---
                    current_params = default_params

                # 5. Ask AI to suggest new parameters
                print(f"  Asking AI for new parameters based on: {current_params}")
                new_params = suggest_new_parameters(
                    strategy_name, 
                    ticker, 
                    current_params
                )
                
                if not new_params:
                    print(f"  AI failed to suggest new parameters for {ticker}. Skipping.")
                    continue

                print(f"  AI suggested new parameters: {new_params}")

                # 6. Trigger a new backtest task
                run_backtest_task.delay(
                    ticker=ticker,
                    strategy_name=strategy_name,
                    params=new_params
                )
        
    except Exception as e:
        print(f"!!! [Celery Task] AI Optimization Loop FAILED: {e} !!!")
    finally:
        session.close()

# --- NEW: POST-TRADE LEARNING LOOP ---
@celery.task
def run_post_trade_analysis_task():
    """
    Reviews all trades from the past 24h that have not been analyzed,
    calculates their P&L, and generates an AI critique.
    """
    print("--- [Celery Task] Kicking off Post-Trade Analysis ---")
    session = SessionLocal()
    
    # Find all trades from the last 24h that don't have an analysis
    one_day_ago = (datetime.now() - timedelta(days=1)).isoformat()
    
    # Find trade IDs that already have an analysis
    analyzed_trade_ids = session.query(PostTradeAnalysis.trade_id).all()
    analyzed_trade_ids = {t_id[0] for t_id in analyzed_trade_ids}

    # Find recent trades that are not in the analyzed list
    trades_to_analyze = session.query(Trade).filter(
        Trade.timestamp >= one_day_ago,
        ~Trade.id.in_(analyzed_trade_ids)
    ).all()
    
    if not trades_to_analyze:
        print("No new trades to analyze.")
        session.close()
        return

    print(f"Found {len(trades_to_analyze)} new trades to analyze.")
    
    for trade in trades_to_analyze:
        # Simple P&L: Check price 24h after the trade (or latest if < 24h)
        # In a real system, you'd match this trade to its closing trade.
        # For simplicity, we'll do a 24h mark-to-market.
        try:
            trade_time = datetime.fromisoformat(trade.timestamp)
            end_time = min(trade_time + timedelta(days=1), datetime.now() - timedelta(minutes=15))

            bars = data_client.get_stock_bars(StockBarsRequest(
                symbol_or_symbols=[trade.ticker],
                timeframe=TimeFrame.Minute,
                start=trade_time,
                end=end_time
            )).df

            if bars.empty:
                print(f"No data to analyze trade {trade.id} for {trade.ticker}")
                continue

            end_price = bars.iloc[-1]['close']
            entry_price = trade.price
            pnl = 0.0

            if trade.action.upper() == 'BUY':
                pnl = (end_price - entry_price) * trade.quantity
            elif trade.action.upper() == 'SELL':
                pnl = (entry_price - end_price) * trade.quantity
            
            print(f"  -> Analyzing {trade.ticker} trade {trade.id}: P&L ~${pnl:.2f}")

            # Get AI critique
            critique = get_post_trade_critique(
                ticker=trade.ticker,
                action=trade.action,
                reason=trade.reason,
                pnl=pnl
            )
            
            # Save to database
            analysis = PostTradeAnalysis(
                trade_id=trade.id,
                pnl=pnl,
                market_comparison_pnl=0.0, # Placeholder
                ai_summary=critique
            )
            session.add(analysis)
            session.commit()
            
        except Exception as e:
            print(f"Failed to analyze trade {trade.id}: {e}")
            session.rollback()

    session.close()
    print("--- [Celery Task] Post-Trade Analysis Finished ---")

# --- AUTOMATED SCHEDULE ---
celery.conf.beat_schedule = {
    'run-morning-pipeline-daily': {
        'task': 'tasks.run_morning_pipeline',
        'schedule': crontab(hour=12, minute=0, day_of_week='1-5'), # 8:00 AM EST
    },
    'run-master-bot-intraday': {
        'task': 'tasks.run_master_bot_task',
        'schedule': crontab(minute='0', hour='13-20', day_of_week='1-5'), # 9:30 AM - 4:00 PM EST
    },
    
    # --- FIX: Renamed and changed schedule from daily to weekly ---
    'run-ai-optimizer-weekly': {
        'task': 'tasks.run_ai_optimization_loop',
        # Runs once per week on Sunday at 3:00 AM UTC
        'schedule': crontab(hour=3, minute=0, day_of_week='sun'),
    },
    
    'run-post-trade-analysis-daily': {
        'task': 'tasks.run_post_trade_analysis_task',
        'schedule': crontab(hour=23, minute=0, day_of_week='1-5'), # 7:00 PM EST
    }
}
celery.conf.timezone = 'UTC'
