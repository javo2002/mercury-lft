import os
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

# --- CONFIGURATION ---
load_dotenv()
SLACK_BOT_TOKEN = os.getenv('SLACK_BOT_TOKEN')
SLACK_CHANNEL = '#trading-alerts'

TREND_FILE = 'trend_screener_results.txt'
REVERSION_FILE = 'reversion_screener_results.txt'

def read_tickers_from_file(filepath):
    try:
        with open(filepath, 'r') as f:
            return [line.strip() for line in f if line.strip()]
    except FileNotFoundError:
        return ["File not found."]

def send_slack_alert(message):
    try:
        client = WebClient(token=SLACK_BOT_TOKEN)
        client.chat_postMessage(channel=SLACK_CHANNEL, text=message)
        print("Slack alert sent successfully.")
    except SlackApiError as e:
        print(f"Error sending Slack alert: {e.response['error']}")

def run_notifier():
    print("--- Generating Weekly Screener Report ---")
    
    trend_tickers = read_tickers_from_file(TREND_FILE)
    reversion_tickers = read_tickers_from_file(REVERSION_FILE)
    
    message = (
        f"📊 *Weekly Screener Results*\n\n"
        f"*Top Trend-Following Candidates:*\n"
        f"```{', '.join(trend_tickers)}```\n\n"
        f"*Top Mean-Reversion Candidates:*\n"
        f"```{', '.join(reversion_tickers)}```\n\n"
        f"Consider running new backtest optimizations on any promising new tickers."
    )
    
    send_slack_alert(message)

if __name__ == "__main__":
    run_notifier()

