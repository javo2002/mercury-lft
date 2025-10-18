import pandas as pd

TRADE_LOG_FILE = 'trade_log.csv'

def analyze_performance():
    """
    Reads the trade log and computes basic performance metrics.
    """
    print("\n--- Running Performance Analyzer ---")
    try:
        trades_df = pd.read_csv(TRADE_LOG_FILE)
    except FileNotFoundError:
        print(f"Error: Trade log file '{TRADE_LOG_FILE}' not found. No trades to analyze.")
        return

    if trades_df.empty:
        print("Trade log is empty. No trades to analyze.")
        return

    # Calculate Profit/Loss for each trade
    trades_df['pnl'] = (trades_df['exit_price'] - trades_df['entry_price']) * trades_df['qty']
    
    print("\n--- Overall Performance ---")
    total_trades = len(trades_df)
    total_pnl = trades_df['pnl'].sum()
    win_rate = (trades_df['pnl'] > 0).mean() * 100
    
    print(f"Total Trades: {total_trades}")
    print(f"Total PnL: ${total_pnl:.2f}")
    print(f"Win Rate: {win_rate:.2f}%")
    
    print("\n--- Performance by Strategy ---")
    strategy_groups = trades_df.groupby('strategy')['pnl'].agg(['sum', 'count', lambda x: (x > 0).mean() * 100])
    strategy_groups.columns = ['Total PnL', 'Trade Count', 'Win Rate %']
    print(strategy_groups)

if __name__ == "__main__":
    analyze_performance()
