import os
import re
import threading
from flask import Flask, jsonify, render_template, request
from flask_sock import Sock
import pandas as pd
from datetime import datetime, timedelta
import logging

# --- Project Imports ---
from config import settings
from database import SessionLocal, Signal, Trade, Sentiment, Mailbox, Feedback, BacktestResult, SystemStatus, PostTradeAnalysis, init_db
import ai_services
import performance_calculator
from tasks import run_backtest_task
from research.backtester import STRATEGY_MAP

# --- Alpaca & Data Clients ---
from alpaca.trading.client import TradingClient
from alpaca.data.historical import StockHistoricalDataClient

# --- App Initialization ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
app = Flask(__name__, template_folder='.', static_folder='static')
sock = Sock(app)
trading_client = TradingClient(settings.API_KEY, settings.API_SECRET, paper=True)
data_client = StockHistoricalDataClient(settings.API_KEY, settings.API_SECRET)


# --- Core API Endpoints ---
@app.route('/')
def index():
    """Serves the main HTML file for the Single Page Application."""
    return render_template('signal_visualizer.html')

@app.route('/api/portfolio_status')
def get_portfolio_status():
    """Fetches the current portfolio status from Alpaca."""
    try:
        account = trading_client.get_account()
        positions = trading_client.get_all_positions()
        data = {
            'portfolio_value': float(account.portfolio_value),
            'cash': float(account.cash),
            'positions': [{
                'symbol': p.symbol, 'qty': float(p.qty), 'market_value': float(p.market_value),
                'unrealized_pl': float(p.unrealized_pl), 'avg_entry_price': float(p.avg_entry_price),
                'current_price': float(p.current_price)
            } for p in positions]
        }
        return jsonify(data)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/equity_curve')
def get_equity_curve():
    """Fetches portfolio equity history, with graceful error handling for new accounts."""
    try:
        history = trading_client.get_portfolio_history(period='3M', timeframe='1D')
        if not hasattr(history, 'equity') or not history.equity:
            return jsonify({'error': 'No equity history available for this account yet.'}), 404
        df = pd.DataFrame({
            'time': [datetime.fromtimestamp(t).strftime('%Y-%m-%d') for t in history.timestamp],
            'value': history.equity
        })
        return jsonify(df.to_dict(orient='records'))
    except Exception:
        logging.warning("Could not fetch portfolio history. This is normal for new paper accounts.")
        return jsonify({'error': 'Portfolio history data not available for new accounts.'}), 503

@app.route('/api/dashboard_data')
def get_dashboard_data():
    """Fetches the daily signal and sentiment data for the watchlist."""
    session = SessionLocal()
    today = datetime.now().strftime('%Y-%m-%d')
    try:
        signals_raw = session.query(Signal).filter(Signal.date == today).all()
        sentiment_raw = session.query(Sentiment).filter(Sentiment.date == today).all()
        signals = [s.as_dict() for s in signals_raw]
        sentiment = {row['ticker']: row for row in [s.as_dict() for s in sentiment_raw]}
        watchlist = []
        for signal in signals:
            ticker = signal['ticker']
            ticker_sentiment = sentiment.get(ticker, {})
            watchlist.append({
                'ticker': ticker, 'last_close': signal.get('last_close'),
                'live_signal': signal.get('live_signal'),
                'sentiment_label': ticker_sentiment.get('sentiment_label'),
            })
        return jsonify(watchlist)
    except Exception as e:
        logging.error(f"DB query failed for dashboard data: {e}")
        return jsonify({"error": f"DB query failed: {e}"}), 500
    finally:
        session.close()

@app.route('/api/trade_history')
def get_trade_history():
    """Fetches all trade records from the database."""
    session = SessionLocal()
    try:
        trades = session.query(Trade).order_by(Trade.timestamp.desc()).all()
        return jsonify([t.as_dict() for t in trades])
    finally:
        session.close()

@app.route('/api/performance_stats')
def get_performance_stats():
    """Calculates and returns performance metrics based on trade history."""
    session = SessionLocal()
    try:
        trades_df = pd.read_sql(session.query(Trade).statement, session.bind)
        if trades_df.empty:
            return jsonify({'error': 'No trade data available to calculate stats.'})
        stats = performance_calculator.calculate_performance_metrics(trades_df)
        return jsonify(stats)
    finally:
        session.close()

@app.route('/api/latest_daily_plan')
def get_latest_daily_plan():
    """Fetches the latest unread daily plan from the mailbox."""
    session = SessionLocal()
    today_str = datetime.now().strftime('%Y-%m-%d')
    try:
        # Find the latest plan for today with status 'unread'
        latest_plan = session.query(Mailbox).filter(
            Mailbox.subject.like(f"Daily Trade Plan: {today_str}%"),
            Mailbox.status == 'unread'
        ).order_by(Mailbox.timestamp.desc()).first()

        if latest_plan:
            plan_data = latest_plan.as_dict()
            # Optionally mark as read after fetching
            # latest_plan.status = 'read'
            # session.commit()
            return jsonify(plan_data)
        else:
            # If no unread plan for today, find the absolute latest plan
            absolute_latest = session.query(Mailbox).filter(
                 Mailbox.subject.like("Daily Trade Plan:%")
            ).order_by(Mailbox.timestamp.desc()).first()
            if absolute_latest:
                 return jsonify(absolute_latest.as_dict())
            else:
                 return jsonify({"subject": "No Plan Available", "content": "The daily plan has not been generated yet."})

    except Exception as e:
        logging.error(f"DB query failed for latest daily plan: {e}")
        session.rollback() # Rollback in case of error during status update
        return jsonify({"error": f"DB query failed: {e}"}), 500
    finally:
        session.close()

# --- AI & Research Endpoints ---
@app.route('/api/ai/chat', methods=['POST'])
def handle_ai_chat():
    """Handles messages for the AI Copilot, routing to deep analysis for tickers."""
    message = request.json.get('message', '').strip().upper()
    if re.match(r'^[A-Z]{1,5}$', message): # Check if it's a ticker symbol
        try:
            response_text = ai_services.get_deep_analysis(message)
            return jsonify({'reply': response_text})
        except Exception as e:
            logging.error(f"AI deep analysis failed for {message}: {e}")
            return jsonify({'error': f"Failed to get AI analysis for {message}."}), 500
    else:
        return jsonify({'reply': "I can provide a deep-dive analysis for any stock ticker. Just enter a symbol like 'AAPL' or 'TSLA'."})

@app.route('/api/research/run_backtest', methods=['POST'])
def run_backtest_endpoint():
    """Triggers a background backtesting job."""
    data = request.json
    ticker = data.get('ticker')
    strategy_name = data.get('strategy_name')
    params = data.get('params', {})
    if not ticker or not strategy_name:
        return jsonify({'error': 'Ticker and strategy_name are required.'}), 400
    run_backtest_task.delay(ticker, strategy_name, params)
    return jsonify({'status': 'Backtest job submitted successfully.'})

@app.route('/api/research/backtest_results')
def get_backtest_results():
    """Fetches the history of backtest results."""
    session = SessionLocal()
    try:
        results = session.query(BacktestResult).order_by(BacktestResult.timestamp.desc()).all()
        return jsonify([r.as_dict() for r in results])
    finally:
        session.close()

@app.route('/api/research/available_tickers')
def get_available_tickers():
    """Gets a list of all tickers with signals for the backtest UI."""
    session = SessionLocal()
    try:
        tickers = session.query(Signal.ticker).distinct().order_by(Signal.ticker).all()
        return jsonify([t[0] for t in tickers])
    finally:
        session.close()

@app.route('/api/research/available_strategies')
def get_available_strategies():
    """Gets a list of all strategies available in the backtester."""
    return jsonify(list(STRATEGY_MAP.keys()))

@app.route('/api/ai_journal')
def get_ai_journal():
    """Fetches the AI's post-trade analysis and critiques."""
    session = SessionLocal()
    try:
        results = (
            session.query(
                Trade.timestamp,
                Trade.ticker,
                Trade.action,
                Trade.reason,
                PostTradeAnalysis.pnl,
                PostTradeAnalysis.ai_summary
            )
            .join(PostTradeAnalysis, Trade.id == PostTradeAnalysis.trade_id)
            .order_by(Trade.timestamp.desc())
            .all()
        )
        
        journal_entries = [
            {
                "timestamp": r.timestamp,
                "ticker": r.ticker,
                "action": r.action,
                "reason": r.reason,
                "pnl": r.pnl,
                "critique": r.ai_summary
            } for r in results
        ]
        return jsonify(journal_entries)
    except Exception as e:
        logging.error(f"DB query failed for AI journal: {e}")
        return jsonify({"error": f"DB query failed: {e}"}), 500
    finally:
        session.close()

# --- System & Operational Endpoints ---
@app.route('/api/system/schedule_status')
def get_schedule_status():
    """Provides the status of the automated trading schedule."""
    session = SessionLocal()
    try:
        status = session.query(SystemStatus).first()
        trading_enabled = status.trading_enabled if status else False

        # Calculate the next run time based on the Celery Beat schedule
        now_utc = datetime.utcnow()
        next_run = now_utc.replace(hour=12, minute=0, second=0, microsecond=0)
        if now_utc.weekday() >= 5 or (now_utc.weekday() == 4 and now_utc.hour >= 12): # Weekend or post-run Friday
            days_until_monday = 7 - now_utc.weekday()
            next_run = (now_utc + timedelta(days=days_until_monday)).replace(hour=12, minute=0, second=0, microsecond=0)
        elif now_utc.hour >= 12: # Post-run weekday
             next_run += timedelta(days=1)
        
        return jsonify({
            'trading_enabled': trading_enabled,
            'last_run': "N/A (System just started)", # This would be logged in a real system
            'next_run': next_run.isoformat() + "Z"
        })
    finally:
        session.close()

# --- MAIN EXECUTION ---
if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=8080, debug=False)
else:
    # This runs when Gunicorn starts the application
    init_db()

