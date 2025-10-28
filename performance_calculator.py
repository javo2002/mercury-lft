import pandas as pd
import numpy as np
from collections import defaultdict

def calculate_performance_metrics(trades_df):
    """
    Calculates performance metrics from a DataFrame of trades using
    an average cost basis method for both LONG and SHORT P&L.
    """
    if trades_df.empty:
        return { 'total_closed_trades': 0, 'net_pnl': 0, 'win_rate': 0, 'avg_win': 0, 'avg_loss': 0, 'sharpe_ratio': 0, 'max_drawdown': 0 }

    trades_df['timestamp'] = pd.to_datetime(trades_df['timestamp'])
    trades_df = trades_df.sort_values(by='timestamp')

    realized_profits = []
    # { 'ticker': {'qty': float, 'total_cost': float} }
    # 'qty' is now signed: positive for long, negative for short.
    open_positions = defaultdict(lambda: {'qty': 0.0, 'total_cost': 0.0})

    for _, trade in trades_df.iterrows():
        ticker = trade['ticker']
        action = trade['action'].upper()
        qty = float(trade['quantity'])
        price = float(trade['price'])
        
        pos = open_positions[ticker]
        current_qty = pos['qty']
        
        if action == 'BUY':
            if current_qty < 0: # Covering a short position
                avg_cost_per_share = pos['total_cost'] / abs(current_qty)
                qty_to_cover = min(qty, abs(current_qty))
                
                # Profit = (Sell Price - Buy Price) * Qty
                profit = (avg_cost_per_share - price) * qty_to_cover
                realized_profits.append(profit)
                
                # Update position
                pos['qty'] += qty_to_cover
                pos['total_cost'] += (avg_cost_per_share * qty_to_cover) # Cost basis moves back towards 0
                
                # Check if any part of the buy opens a new long position
                remaining_qty = qty - qty_to_cover
                if remaining_qty > 0:
                    pos['qty'] += remaining_qty
                    pos['total_cost'] += (remaining_qty * price)
            
            else: # Opening or adding to a long position
                pos['qty'] += qty
                pos['total_cost'] += (qty * price)

        elif action == 'SELL':
            if current_qty > 0: # Selling a long position
                avg_cost_per_share = pos['total_cost'] / current_qty
                qty_to_sell = min(qty, current_qty)
                
                # Profit = (Sell Price - Buy Price) * Qty
                profit = (price - avg_cost_per_share) * qty_to_sell
                realized_profits.append(profit)
                
                # Update position
                pos['qty'] -= qty_to_sell
                pos['total_cost'] -= (avg_cost_per_share * qty_to_sell)

                # Check if any part of the sell opens a new short position
                remaining_qty = qty - qty_to_sell
                if remaining_qty > 0:
                    pos['qty'] -= remaining_qty
                    pos['total_cost'] -= (remaining_qty * price) # Cost basis becomes negative
            
            else: # Opening or adding to a short position
                pos['qty'] -= qty
                pos['total_cost'] -= (qty * price) # Cost basis becomes more negative
        
        # Clean up dust
        if abs(pos['qty']) < 1e-6:
            pos['qty'] = 0.0
            pos['total_cost'] = 0.0

    if not realized_profits:
        return { 'total_closed_trades': 0, 'net_pnl': 0, 'win_rate': 0, 'avg_win': 0, 'avg_loss': 0, 'sharpe_ratio': 0, 'max_drawdown': 0 }

    net_pnl = sum(realized_profits)
    wins = [p for p in realized_profits if p > 0]
    losses = [p for p in realized_profits if p < 0]
    
    total_closed_trades = len(realized_profits)
    win_rate = (len(wins) / total_closed_trades) * 100 if total_closed_trades else 0
    avg_win = sum(wins) / len(wins) if wins else 0
    avg_loss = sum(losses) / len(losses) if losses else 0

    equity_curve = pd.Series(realized_profits).cumsum()
    rolling_max = equity_curve.cummax()
    drawdown = equity_curve - rolling_max
    max_drawdown = drawdown.min() if not drawdown.empty else 0

    returns_series = pd.Series(realized_profits)
    sharpe_ratio = (returns_series.mean() / returns_series.std()) if returns_series.std() != 0 else 0

    return {
        'total_closed_trades': total_closed_trades,
        'net_pnl': round(net_pnl, 2),
        'win_rate': round(win_rate, 2),
        'avg_win': round(avg_win, 2),
        'avg_loss': abs(round(avg_loss, 2)),
        'sharpe_ratio': round(sharpe_ratio, 2),
        'max_drawdown': abs(round(max_drawdown, 2)),
    }
