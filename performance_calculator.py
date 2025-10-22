import pandas as pd
import numpy as np

def calculate_performance_metrics(trades_df):
    """
    Calculates performance metrics from a DataFrame of trades, focusing on
    closed round-trip trades.
    """
    if trades_df.empty:
        return { 'total_closed_trades': 0, 'net_pnl': 0, 'win_rate': 0, 'avg_win': 0, 'avg_loss': 0, 'sharpe_ratio': 0, 'max_drawdown': 0 }

    trades_df['timestamp'] = pd.to_datetime(trades_df['timestamp'])
    trades_df = trades_df.sort_values(by='timestamp')

    profits = []
    open_positions = {} # To track buys

    for _, trade in trades_df.iterrows():
        ticker = trade['ticker']
        if trade['action'].upper() == 'BUY':
            if ticker not in open_positions:
                open_positions[ticker] = []
            open_positions[ticker].append(trade)
        
        elif trade['action'].upper() == 'SELL':
            if ticker in open_positions and open_positions[ticker]:
                # Simple FIFO logic: pair sell with the oldest buy
                buy_trade = open_positions[ticker].pop(0)
                profit = (trade['price'] - buy_trade['price']) * min(trade['quantity'], buy_trade['quantity'])
                profits.append(profit)

    if not profits:
        return { 'total_closed_trades': 0, 'net_pnl': 0, 'win_rate': 0, 'avg_win': 0, 'avg_loss': 0, 'sharpe_ratio': 0, 'max_drawdown': 0 }

    net_pnl = sum(profits)
    wins = [p for p in profits if p > 0]
    losses = [p for p in profits if p < 0]
    
    win_rate = (len(wins) / len(profits)) * 100 if profits else 0
    avg_win = sum(wins) / len(wins) if wins else 0
    avg_loss = sum(losses) / len(losses) if losses else 0

    daily_returns = pd.Series(profits).pct_change().dropna()
    sharpe_ratio = (daily_returns.mean() / daily_returns.std()) * np.sqrt(252) if not daily_returns.empty and daily_returns.std() != 0 else 0

    equity_curve = pd.Series(profits).cumsum()
    rolling_max = equity_curve.cummax()
    drawdown = equity_curve - rolling_max
    max_drawdown = drawdown.min()

    return {
        'total_closed_trades': len(profits),
        'net_pnl': round(net_pnl, 2),
        'win_rate': round(win_rate, 2),
        'avg_win': round(avg_win, 2),
        'avg_loss': abs(round(avg_loss, 2)),
        'sharpe_ratio': round(sharpe_ratio, 2),
        'max_drawdown': abs(round(max_drawdown, 2)),
    }
