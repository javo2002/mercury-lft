import pandas as pd
import numpy as np

def calculate_performance_metrics(trades_df):
    """
    Calculates a suite of performance metrics from a DataFrame of trades.
    """
    if trades_df.empty:
        return {}

    # Ensure correct data types
    trades_df['price'] = pd.to_numeric(trades_df['price'])
    trades_df['quantity'] = pd.to_numeric(trades_df['quantity'])
    trades_df['timestamp'] = pd.to_datetime(trades_df['timestamp'])

    total_trades = len(trades_df) // 2
    
    # --- Calculate P/L for each round-trip trade ---
    profits = []
    buys = trades_df[trades_df['action'] == 'BUY'].copy()
    sells = trades_df[trades_df['action'] == 'SELL'].copy()

    # Simple P/L calculation assuming FIFO and full-size exits
    for index, buy in buys.iterrows():
        # Find the corresponding sell for the same ticker that happened after the buy
        corresponding_sell = sells[(sells['ticker'] == buy['ticker']) & (sells['timestamp'] > buy['timestamp'])].sort_values('timestamp').iloc[0] if not sells[(sells['ticker'] == buy['ticker']) & (sells['timestamp'] > buy['timestamp'])].empty else None
        if corresponding_sell is not None:
            profit = (corresponding_sell['price'] - buy['price']) * min(buy['quantity'], corresponding_sell['quantity'])
            profits.append(profit)
            # Remove the used sell to not double-count it
            sells = sells.drop(corresponding_sell.name)

    if not profits:
        return {
            'total_trades': total_trades,
            'net_pnl': 0,
            'win_rate': 0,
            'avg_win': 0,
            'avg_loss': 0,
            'sharpe_ratio': 0,
            'max_drawdown': 0,
        }
            
    # --- Calculate Metrics ---
    net_pnl = sum(profits)
    wins = [p for p in profits if p > 0]
    losses = [p for p in profits if p < 0]
    
    win_rate = (len(wins) / len(profits)) * 100 if profits else 0
    avg_win = sum(wins) / len(wins) if wins else 0
    avg_loss = sum(losses) / len(losses) if losses else 0

    # --- Sharpe Ratio Calculation ---
    # Assuming daily returns and a risk-free rate of 0
    daily_returns = pd.Series(profits).pct_change().dropna()
    sharpe_ratio = (daily_returns.mean() / daily_returns.std()) * np.sqrt(252) if not daily_returns.empty and daily_returns.std() != 0 else 0

    # --- Max Drawdown Calculation ---
    equity_curve = pd.Series(profits).cumsum()
    rolling_max = equity_curve.cummax()
    drawdown = equity_curve - rolling_max
    max_drawdown = drawdown.min()

    return {
        'total_trades': len(profits),
        'net_pnl': net_pnl,
        'win_rate': win_rate,
        'avg_win': avg_win,
        'avg_loss': abs(avg_loss),
        'sharpe_ratio': sharpe_ratio,
        'max_drawdown': abs(max_drawdown),
    }
