import os
import json
import logging
from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
from dotenv import load_dotenv
import google.generativeai as genai
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import MarketOrderRequest
from alpaca.trading.enums import OrderSide, TimeInForce
from risk_manager import is_safe_to_trade
from alpaca.data.historical import StockHistoricalDataClient

# --- Load all environment variables from .env file ---
load_dotenv()
API_KEY = os.getenv('API_KEY')
API_SECRET = os.getenv('API_SECRET')
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')

# --- Initialize Flask App and configure logging ---
app = Flask(__name__)
CORS(app)
logging.basicConfig(level=logging.INFO)

# --- Initialize Gemini AI Model ---
try:
    if not GEMINI_API_KEY:
        raise ValueError("GEMINI_API_KEY not found in .env file.")
    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel('gemini-pro-latest')
except Exception as e:
    app.logger.error(f"!!! CRITICAL ERROR: Could not configure Gemini AI. Check your GEMINI_API_KEY. Details: {e}", exc_info=True)
    model = None

# --- API Endpoint for Live Portfolio Data ---
@app.route('/portfolio-data')
def get_portfolio_data():
    try:
        if not API_KEY or not API_SECRET: raise ValueError("Alpaca API keys are not set.")
        trading_client = TradingClient(API_KEY, API_SECRET, paper=True)
        data_client = StockHistoricalDataClient(API_KEY, API_SECRET)
        
        account = trading_client.get_account()
        positions = trading_client.get_all_positions()
        market_safe = is_safe_to_trade(data_client)
        
        positions_data = [{
            "symbol": p.symbol, "qty": float(p.qty), "avg_entry_price": float(p.avg_entry_price),
            "current_price": float(p.current_price), "unrealized_pl": float(p.unrealized_pl),
        } for p in positions]

        data = {
            "equity": float(account.equity),
            "pnl_today": float(account.equity) - float(account.last_equity),
            "market_is_safe": market_safe,
            "positions": positions_data
        }
        return jsonify(data)
    except Exception as e:
        app.logger.error("!!! PORTFOLIO API ERROR !!!", exc_info=True)
        return jsonify({"error": str(e)}), 500

# --- API Endpoint to Securely Execute Trades ---
@app.route('/execute-trade', methods=['POST'])
def execute_trade_endpoint():
    try:
        if not API_KEY or not API_SECRET: raise ValueError("Alpaca API keys are not set.")
        trading_client = TradingClient(API_KEY, API_SECRET, paper=True)
        
        data = request.json
        symbol = data.get('symbol')
        qty = data.get('qty')
        side = data.get('side')

        if not symbol or not qty or not side:
            return jsonify({"status": "error", "message": "Missing symbol, qty, or side"}), 400

        order_data = MarketOrderRequest(
            symbol=symbol,
            qty=qty,
            side=OrderSide.BUY if side.upper() == 'BUY' else OrderSide.SELL,
            time_in_force=TimeInForce.DAY
        )
        trading_client.submit_order(order_data=order_data)
        
        return jsonify({"status": "success", "message": f"Successfully placed {side} order for {qty} shares of {symbol}."})
    except Exception as e:
        app.logger.error("!!! TRADE EXECUTION ERROR !!!", exc_info=True)
        return jsonify({"status": "error", "message": str(e)}), 500

# --- API Endpoint for AI Chatbot ---
@app.route('/ask-ai', methods=['POST'])
def ask_ai():
    if model is None:
        return jsonify({"answer": "AI model not configured. Please check the server logs for errors."}), 500
    try:
        user_question = request.json['question']
        
        with open('signal_report.json', 'r') as f:
            technical_data = json.load(f)
        try:
            with open('sentiment_report.json', 'r') as f:
                sentiment_data = json.load(f)
        except FileNotFoundError:
            sentiment_data = {}

        trading_client = TradingClient(API_KEY, API_SECRET, paper=True)
        positions = trading_client.get_all_positions()
        positions_data = [{"symbol": p.symbol, "qty": p.qty, "avg_entry_price": p.avg_entry_price} for p in positions]

        prompt = f"""
        You are "Mercury AI," an expert trading assistant. Your task is to synthesize technical, sentiment, and live portfolio data to answer a user's question.

        **CRITICAL INSTRUCTIONS:**
        1.  Start with a disclaimer that you cannot give financial advice.
        2.  For any ticker mentioned, you MUST cross-reference its technical signal with its sentiment data and check if the user already holds a position.
        3.  Your analysis MUST reflect ALL available data sources.
        4.  You MUST use the following Markdown template for each highlighted stock:
            ### [Ticker Symbol] (Based on [Strategy Name])
            **Analysis:** [Combine the technical signal and news sentiment. Example: "The stock shows a 'Bullish Crossover', supported by positive news sentiment (+0.8) related to 'new product launch' keywords."]
            **Bot Action:** [Explain what the automated morning bot will do. If the user already holds the stock, explain the BOT'S EXIT STRATEGY. For RSI, the exit is crossing 50. For SMA, it's a bearish crossover. If it's a new signal, explain the entry logic.]
            **Suggested Quantity:** [Calculate quantity using: (100,000 * 0.05) / current_price. Round down. State the 5% risk allocation.]
            **Manual Trade Context:** [Advise whether to let the bot manage the trade or if a manual action is being considered. Example: "Since you hold this position, the bot is already managing it. Its exit rule is X. A manual exit now would override the bot's strategy."]

        Here is the TECHNICAL data: {json.dumps(technical_data, indent=2)}
        Here is the SENTIMENT data: {json.dumps(sentiment_data, indent=2)}
        Here are the user's CURRENTLY HELD POSITIONS: {json.dumps(positions_data, indent=2)}
        User's question: "{user_question}"
        """
        response = model.generate_content(prompt)
        return jsonify({"answer": response.text})
    except Exception as e:
        app.logger.error("!!! CHATBOT ERROR !!!", exc_info=True)
        return jsonify({"answer": "Sorry, an error occurred. Please check the server terminal for details."}), 500

# --- Routes to serve the main HTML and other static files ---
@app.route('/')
def index():
    return send_from_directory('.', 'signal_visualizer.html')

@app.route('/<path:path>')
def serve_files(path):
    return send_from_directory('.', path)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000)
