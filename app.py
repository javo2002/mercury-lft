import os
import time
import logging
from flask import Flask, jsonify, render_template, request, send_file
from flask_sock import Sock
from dotenv import load_dotenv
import alpaca_trade_api as tradeapi
import sqlite3
import pandas as pd
from risk_manager import get_market_condition
import ai_services
import performance_calculator
import json
from io import StringIO
from datetime import datetime, timedelta

# --- FIX: Import Alpaca Data Client ---
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame


# --- CONFIGURATION & LOGGING ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
load_dotenv()
API_KEY = os.getenv('API_KEY'); API_SECRET = os.getenv('API_SECRET')
BASE_URL = 'https://paper-api.alpaca.markets'; DATABASE_FILE = 'trading_data.db'
app = Flask(__name__, template_folder='.'); sock = Sock(app)

# --- HELPER FUNCTIONS ---
def get_db_connection():
    conn = sqlite3.connect(DATABASE_FILE, check_same_thread=False); conn.row_factory = sqlite3.Row
    return conn
def get_alpaca_api():
    try:
        api = tradeapi.REST(API_KEY, API_SECRET, base_url=BASE_URL, api_version='v2'); api.get_account()
        return api
    except Exception as e:
        logging.error(f"Failed to connect to Alpaca API: {e}")
        return None

# --- API ENDPOINTS ---
@app.route('/')
def index(sock=None): return render_template('signal_visualizer.html')

@app.route('/api/trade_history')
def get_trade_history(sock=None):
    logging.info("API call: /api/trade_history")
    try:
        conn = get_db_connection()
        trades = conn.execute("SELECT * FROM trades ORDER BY timestamp DESC").fetchall()
        conn.close()
        logging.info(f"Successfully fetched {len(trades)} trade history records.")
        return jsonify([dict(row) for row in trades])
    except Exception as e:
        logging.error(f"Error in /api/trade_history: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/performance_stats')
def get_performance_stats(sock=None):
    logging.info("API call: /api/performance_stats")
    try:
        conn = get_db_connection()
        trades_df = pd.read_sql_query("SELECT * FROM trades", conn)
        conn.close()
        stats = performance_calculator.calculate_performance_metrics(trades_df)
        logging.info("Successfully calculated performance stats.")
        return jsonify(stats)
    except Exception as e:
        logging.error(f"Error in /api/performance_stats: {e}")
        return jsonify({'error': str(e)}), 500

# --- FIX: Rewritten to use Alpaca API for reliability ---
@app.route('/api/chart_data/<ticker>')
def get_chart_data(ticker, sock=None):
    logging.info(f"API call: /api/chart_data/{ticker}")
    try:
        data_client = StockHistoricalDataClient(API_KEY, API_SECRET)
        request_params = StockBarsRequest(
            symbol_or_symbols=[ticker],
            timeframe=TimeFrame.Day,
            start=datetime.now() - timedelta(days=730) # 2 years of data
        )
        bars = data_client.get_stock_bars(request_params).df
        
        if bars.empty: return jsonify({'error': 'No historical data found'}), 404
        
        # Data is multi-indexed by (symbol, timestamp), reset to get columns
        data = bars.reset_index()
        data.rename(columns={'timestamp': 'time'}, inplace=True)
        data['time'] = data['time'].dt.strftime('%Y-%m-%d') # Format for chart library

        conn = get_db_connection()
        trades = conn.execute("SELECT timestamp, action, price FROM trades WHERE ticker = ?", (ticker,)).fetchall()
        conn.close()
        trade_markers = [{'time': pd.to_datetime(t['timestamp']).strftime('%Y-%m-%d'), 'position': 'aboveBar' if t['action']=='SELL' else 'belowBar', 'color': '#fb7185' if t['action']=='SELL' else '#34d399', 'shape': 'arrowDown' if t['action']=='SELL' else 'arrowUp', 'text': f"{t['action']} @ {t['price']:.2f}"} for t in trades]
        
        logging.info(f"Successfully fetched chart data for {ticker} from Alpaca.")
        return jsonify({
            'candlestick_data': data.to_dict(orient='records'),
            'trade_markers': trade_markers,
            'volume_data': data[['time', 'volume']].to_dict(orient='records')
        })
    except Exception as e:
        logging.error(f"Error in /api/chart_data/{ticker}: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/equity_curve')
def get_equity_curve(sock=None):
    logging.info("API call: /api/equity_curve")
    try:
        api = get_alpaca_api()
        history = api.get_portfolio_history(period='3M', timeframe='1D')
        df = pd.DataFrame({'time': [datetime.fromtimestamp(t).strftime('%Y-%m-%d') for t in history.timestamp], 'value': history.equity})
        logging.info("Successfully fetched equity curve data.")
        return jsonify(df.to_dict(orient='records'))
    except Exception as e:
        logging.error(f"Error in /api/equity_curve: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/export/<data_type>')
def export_data(data_type, sock=None):
    logging.info(f"API call: /api/export/{data_type}")
    try:
        conn = get_db_connection()
        if data_type == 'trades':
            df = pd.read_sql_query("SELECT * FROM trades", conn)
            filename = "trade_history.csv"
        else:
            return "Invalid data type", 400
        conn.close()
        csv_buffer = StringIO()
        df.to_csv(csv_buffer, index=False)
        csv_buffer.seek(0)
        return send_file(csv_buffer, as_attachment=True, download_name=filename, mimetype='text/csv')
    except Exception as e:
        logging.error(f"Error in /api/export/{data_type}: {e}")
        return "Error generating file.", 500

@app.route('/api/daily_trade_plan')
def get_daily_trade_plan(sock=None):
    logging.info("API call: /api/daily_trade_plan")
    try:
        market_condition = get_market_condition()
        today = datetime.now().strftime('%Y-%m-%d')
        conn = get_db_connection()
        signals = conn.execute("SELECT ticker, live_signal FROM signals WHERE date = ? AND live_signal != 'NONE'", (today,)).fetchall()
        conn.close()
        economic_events = ai_services.get_economic_events()
        plan = ai_services.generate_daily_trade_plan(market_condition, [dict(s) for s in signals], economic_events)
        logging.info("Successfully generated daily trade plan.")
        return jsonify({'plan': plan})
    except Exception as e:
        logging.error(f"Error in /api/daily_trade_plan: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/deep_analysis/<ticker>')
def get_deep_analysis_route(ticker, sock=None):
    logging.info(f"API call: /api/deep_analysis/{ticker}")
    try:
        analysis = ai_services.get_deep_analysis(ticker)
        return jsonify({'analysis': analysis})
    except Exception as e:
        logging.error(f"Error in /api/deep_analysis/{ticker}: {e}")
        return jsonify({'error': str(e)}), 500

# --- FIX: Rewritten to use Alpaca API for reliability ---
@app.route('/api/correlation_matrix')
def get_correlation_matrix(sock=None):
    logging.info("API call: /api/correlation_matrix")
    try:
        api = get_alpaca_api()
        positions = api.list_positions()
        tickers = [p.symbol for p in positions]
        if len(tickers) < 2:
            return jsonify({'error': 'Need at least 2 positions to calculate correlation.'})

        data_client = StockHistoricalDataClient(API_KEY, API_SECRET)
        request_params = StockBarsRequest(
            symbol_or_symbols=tickers,
            timeframe=TimeFrame.Day,
            start=datetime.now() - timedelta(days=90) # 3 months of data
        )
        data = data_client.get_stock_bars(request_params).df['close'].unstack(level=0)
        
        returns = data.pct_change().dropna()
        corr_matrix = returns.corr()
        interpretation = ai_services.interpret_correlation_matrix(corr_matrix)
        matrix_html = corr_matrix.style.background_gradient(cmap='coolwarm').set_properties(**{'font-size': '10pt'}).to_html()
        return jsonify({'matrix_html': matrix_html, 'interpretation': interpretation})
    except Exception as e:
        logging.error(f"Error in /api/correlation_matrix: {e}")
        return jsonify({'error': str(e)}), 500
        
@app.route('/api/ask_gemini', methods=['POST'])
def ask_gemini(sock=None):
    user_message = request.json.get('message')
    logging.info(f"API call: /api/ask_gemini with message: {user_message}")
    if not user_message: return jsonify({'error': 'No message provided'}), 400
    try:
        conn = get_db_connection()
        trades_history = conn.execute("SELECT * FROM trades ORDER BY timestamp DESC").fetchall()
        conn.close()
        history_str = "\n".join([f"{row['timestamp']},{row['ticker']},{row['action']},{row['quantity']},{row['price']},{row['trade_type']}" for row in trades_history]) or "No trades yet."
        prompt = f"""You are a trading analyst. Answer the user's question based on the provided trade history.\n\n**Trade History (timestamp,ticker,action,qty,price,type):**\n{history_str}\n\n**Question:** "{user_message}" """
        model = ai_services.genai.GenerativeModel('gemini-pro-latest')
        response = model.generate_content(prompt)
        return jsonify({'reply': response.text})
    except Exception as e:
        logging.error(f"Error in /api/ask_gemini: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/dashboard_data')
def get_dashboard_data(sock=None):
    logging.info("API call: /api/dashboard_data")
    try:
        today = datetime.now().strftime('%Y-%m-%d')
        conn = get_db_connection()
        signals_raw = conn.execute("SELECT * FROM signals WHERE date = ?", (today,)).fetchall()
        sentiment_raw = conn.execute("SELECT * FROM sentiment WHERE date = ?", (today,)).fetchall()
        conn.close()
        signals = [dict(row) for row in signals_raw]
        sentiment = {row['ticker']: dict(row) for row in sentiment_raw}
        watchlist = []
        for signal in signals:
            ticker = signal['ticker']
            ticker_sentiment = sentiment.get(ticker, {})
            watchlist.append({ 'ticker': ticker, 'last_close': signal.get('last_close'), 'live_signal': signal.get('live_signal'), 'sentiment_label': ticker_sentiment.get('sentiment_label'), })
        return jsonify(watchlist)
    except Exception as e:
        logging.error(f"Error in /api/dashboard_data: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/analyze_behavior')
def analyze_behavior(sock=None):
    logging.info("API call: /api/analyze_behavior")
    try:
        conn = get_db_connection()
        manual_trades = conn.execute("SELECT * FROM trades WHERE trade_type = 'MANUAL' ORDER BY timestamp ASC").fetchall()
        conn.close()
        if not manual_trades:
            return jsonify({'analysis': "No manual trades found to analyze."})
        history_str = "\n".join([f"{row['timestamp']},{row['ticker']},{row['action']},{row['quantity']},{row['price']}" for row in manual_trades])
        prompt = f"""
        You are a trading psychologist AI. Analyze the user's manual trades for biases like the Disposition Effect, Revenge Trading, or FOMO.
        **Manual Trades:**\n{history_str}\n
        Provide a concise, bulleted list of constructive observations.
        """
        model = ai_services.genai.GenerativeModel('gemini-pro-latest')
        response = model.generate_content(prompt)
        return jsonify({'analysis': response.text})
    except Exception as e:
        logging.error(f"Error in /api/analyze_behavior: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/portfolio_status')
def get_portfolio_status(sock=None):
    logging.info("API call: /api/portfolio_status")
    try:
        api = get_alpaca_api()
        if not api: raise Exception("Failed to connect to Alpaca API")
        account = api.get_account()
        positions = api.list_positions()
        data = {'portfolio_value': float(account.portfolio_value), 'cash': float(account.cash), 'positions': [{'symbol': p.symbol, 'qty': float(p.qty), 'market_value': float(p.market_value), 'unrealized_pl': float(p.unrealized_pl), 'avg_entry_price': float(p.avg_entry_price), 'current_price': float(p.current_price)} for p in positions]}
        return jsonify(data)
    except Exception as e:
        logging.error(f"Error in /api/portfolio_status: {e}")
        return jsonify({'error': str(e)}), 500

# --- WEBSOCKETS ---
@sock.route('/ws_prices')
def price_stream(ws):
    logging.info("Price streaming client connected.")
    try:
        stream = tradeapi.Stream(API_KEY, API_SECRET)
        async def on_trade(t):
            try: ws.send(json.dumps({'symbol': t.symbol, 'price': t.price}))
            except Exception: pass
        api = get_alpaca_api()
        symbols = [p.symbol for p in api.list_positions()]
        if symbols:
            logging.info(f"Subscribing to live trades for: {', '.join(symbols)}")
            stream.subscribe_trades(on_trade, *symbols)
            stream.run()
    except Exception as e:
        logging.error(f"Price streaming error: {e}")
    finally:
        logging.info("Price streaming client disconnected.")

@sock.route('/ws_logs')
def log_stream(ws):
    logging.info("Log streaming client connected.")
    log_file = 'nohup.out'
    try:
        with open(log_file, 'r') as f:
            f.seek(0, 2)
            while True:
                line = f.readline()
                if not line:
                    time.sleep(0.1)
                    continue
                ws.send(line)
    except Exception as e:
        logging.error(f"Log streaming error: {e}")
    finally:
        logging.info("Log streaming client disconnected.")

# --- MAIN EXECUTION ---
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, debug=False)
