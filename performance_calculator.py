import pandas as pd
import numpy as np

def calculate_performance_metrics(trades_df):
    """
    Calculates a suite of performance metrics from a DataFrame of trades,
    correctly handling both long and short positions.
    """
    if trades_df.empty:
        return {
            'total_trades': 0, 'net_pnl': 0, 'win_rate': 0,
            'avg_win': 0, 'avg_loss': 0, 'sharpe_ratio': 0, 'max_drawdown': 0,
        }

    # Ensure correct data types and sort chronologically
    trades_df['price'] = pd.to_numeric(trades_df['price'])
    trades_df['quantity'] = pd.to_numeric(trades_df['quantity'])
    trades_df['timestamp'] = pd.to_datetime(trades_df['timestamp'])
    trades_df.sort_values(by='timestamp', inplace=True)

    profits = []
    
    # Group by ticker to process trades for each symbol independently
    for ticker, group in trades_df.groupby('ticker'):
        
        # Use lists of dictionaries to easily manipulate trades
        buys = group[group['action'] == 'BUY'].to_dict('records')
        sells = group[group['action'] == 'SELL'].to_dict('records')

        # --- Match LONG trades (BUY then SELL) ---
        # Iterate over a copy of sells because we will modify the list
        sells_for_longs = sells[:] 
        for buy in buys:
            # Find the first sell that occurred after this buy
            corresponding_sell = next((s for s in sells_for_longs if s['timestamp'] > buy['timestamp']), None)
            if corresponding_sell:
                profit = (corresponding_sell['price'] - buy['price']) * min(buy['quantity'], corresponding_sell['quantity'])
                profits.append(profit)
                sells_for_longs.remove(corresponding_sell) # This sell is now matched and cannot be used again

        # --- Match SHORT trades (SELL then BUY) ---
        # Iterate over a copy of buys because we will modify the list
        buys_for_shorts = buys[:]
        for sell in sells:
            # Find the first buy that occurred after this sell (to close the short)
            corresponding_buy = next((b for b in buys_for_shorts if b['timestamp'] > sell['timestamp']), None)
            if corresponding_buy:
                profit = (sell['price'] - corresponding_buy['price']) * min(sell['quantity'], corresponding_buy['quantity'])
                profits.append(profit)
                buys_for_shorts.remove(corresponding_buy) # This buy is now matched
    
    if not profits:
        return {
            'total_trades': 0, 'net_pnl': 0, 'win_rate': 0,
            'avg_win': 0, 'avg_loss': 0, 'sharpe_ratio': 0, 'max_drawdown': 0,
        }
            
    # --- Calculate Final Metrics ---
    net_pnl = sum(profits)
    wins = [p for p in profits if p > 0]
    losses = [p for p in profits if p < 0]
    
    win_rate = (len(wins) / len(profits)) * 100 if profits else 0
    avg_win = sum(wins) / len(wins) if wins else 0
    avg_loss = sum(losses) / len(losses) if losses else 0

    # --- Sharpe Ratio & Max Drawdown Calculation ---
    equity_curve = pd.Series(profits).cumsum()
    daily_returns = equity_curve.pct_change().dropna()
    
    sharpe_ratio = (daily_returns.mean() / daily_returns.std()) * np.sqrt(252) if not daily_returns.empty and daily_returns.std() != 0 else 0

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
