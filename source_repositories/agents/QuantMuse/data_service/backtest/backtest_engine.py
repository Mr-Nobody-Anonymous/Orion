import pandas as pd
import numpy as np
from typing import Dict, List, Any, Optional, Callable
from datetime import datetime, timedelta
import logging
from dataclasses import dataclass

@dataclass
class Trade:
    """Trade record data structure"""
    timestamp: datetime
    symbol: str
    side: str  # 'buy' or 'sell'
    quantity: float
    price: float
    order_id: str
    status: str = 'filled'

@dataclass
class Position:
    """Position data structure"""
    symbol: str
    quantity: float
    avg_price: float
    unrealized_pnl: float = 0.0
    realized_pnl: float = 0.0

class BacktestEngine:
    """Backtesting engine for trading strategies"""
    
    def __init__(self, initial_capital: float = 100000.0, 
                 commission_rate: float = 0.001):
        self.initial_capital = initial_capital
        self.current_capital = initial_capital
        self.commission_rate = commission_rate
        self.positions: Dict[str, Position] = {}
        self.trades: List[Trade] = []
        self.equity_curve: List[Dict[str, Any]] = []
        self.logger = logging.getLogger(__name__)
        
    def reset(self):
        """Reset backtest engine to initial state"""
        self.current_capital = self.initial_capital
        self.positions.clear()
        self.trades.clear()
        self.equity_curve.clear()
        
    def run_backtest(self, data: pd.DataFrame, strategy_func: Callable,
                    strategy_params: Dict[str, Any] = None) -> Dict[str, Any]:
        """Run backtest with given data and strategy"""
        self.reset()
        
        if strategy_params is None:
            strategy_params = {}
            
        # Sort data by timestamp
        data = data.sort_index()
        
        # Initialize strategy
        strategy_func(data, self, **strategy_params)
        
        # Calculate final results
        results = self._calculate_results()
        return results
    
    def place_order(self, symbol: str, side: str, quantity: float, 
                   price: float, timestamp: datetime) -> bool:
        """Place a trade order"""
        try:
            # Calculate commission
            commission = abs(quantity * price * self.commission_rate)
            
            if side.lower() == 'buy':
                # Check if we have enough capital
                total_cost = quantity * price + commission
                if total_cost > self.current_capital:
                    self.logger.warning(f"Insufficient capital for buy order: {symbol}")
                    return False
                
                # Update capital
                self.current_capital -= total_cost
                
                # Update position
                if symbol in self.positions:
                    pos = self.positions[symbol]
                    total_quantity = pos.quantity + quantity
                    total_cost_basis = pos.quantity * pos.avg_price + quantity * price
                    pos.avg_price = total_cost_basis / total_quantity
                    pos.quantity = total_quantity
                else:
                    self.positions[symbol] = Position(
                        symbol=symbol,
                        quantity=quantity,
                        avg_price=price
                    )
                    
            elif side.lower() == 'sell':
                # Check if we have enough position
                if symbol not in self.positions or self.positions[symbol].quantity < quantity:
                    self.logger.warning(f"Insufficient position for sell order: {symbol}")
                    return False
                
                # Update capital
                self.current_capital += quantity * price - commission
                
                # Update position
                pos = self.positions[symbol]
                pos.quantity -= quantity
                
                # Calculate realized P&L
                realized_pnl = (price - pos.avg_price) * quantity - commission
                pos.realized_pnl += realized_pnl
                
                # Remove position if quantity becomes zero
                if pos.quantity <= 0:
                    del self.positions[symbol]
            
            # Record trade
            trade = Trade(
                timestamp=timestamp,
                symbol=symbol,
                side=side,
                quantity=quantity,
                price=price,
                order_id=f"order_{len(self.trades)}"
            )
            self.trades.append(trade)
            
            # Update equity curve
            self._update_equity_curve(timestamp)
            
            self.logger.info(f"Order executed: {side} {quantity} {symbol} @ {price}")
            return True
            
        except Exception as e:
            self.logger.error(f"Order placement error: {e}")
            return False
    
    def _update_equity_curve(self, timestamp: datetime):
        """Update equity curve with current portfolio value"""
        total_value = self.current_capital
        
        # Add unrealized P&L from positions
        for symbol, pos in self.positions.items():
            # Note: In real implementation, you would get current price from data
            # For simplicity, we'll use average price here
            current_price = pos.avg_price
            pos.unrealized_pnl = (current_price - pos.avg_price) * pos.quantity
            total_value += pos.quantity * current_price
        
        self.equity_curve.append({
            'timestamp': timestamp,
            'total_value': total_value,
            'cash': self.current_capital,
            'positions_value': total_value - self.current_capital
        })
    
    def _calculate_results(self) -> Dict[str, Any]:
        """Calculate backtest results and performance metrics"""
        if not self.equity_curve:
            return {}
        
        # Convert equity curve to DataFrame
        equity_df = pd.DataFrame(self.equity_curve)
        equity_df.set_index('timestamp', inplace=True)
        
        # Calculate returns
        equity_df['returns'] = equity_df['total_value'].pct_change()
        
        # Calculate performance metrics
        total_return = (equity_df['total_value'].iloc[-1] - self.initial_capital) / self.initial_capital
        annualized_return = self._calculate_annualized_return(equity_df)
        volatility = equity_df['returns'].std() * np.sqrt(252)  # Annualized
        sharpe_ratio = annualized_return / volatility if volatility > 0 else 0
        max_drawdown = self._calculate_max_drawdown(equity_df['total_value'])
        
        # Calculate trade statistics
        total_trades = len(self.trades)
        winning_trades = len([t for t in self.trades if t.side == 'sell'])
        win_rate = winning_trades / total_trades if total_trades > 0 else 0
        
        return {
            'initial_capital': self.initial_capital,
            'final_value': equity_df['total_value'].iloc[-1],
            'total_return': total_return,
            'annualized_return': annualized_return,
            'volatility': volatility,
            'sharpe_ratio': sharpe_ratio,
            'max_drawdown': max_drawdown,
            'total_trades': total_trades,
            'win_rate': win_rate,
            'equity_curve': equity_df,
            'trades': self.trades,
            'final_positions': self.positions
        }
    
    def _calculate_annualized_return(self, equity_df: pd.DataFrame) -> float:
        """Calculate annualized return"""
        if len(equity_df) < 2:
            return 0.0
        
        total_days = (equity_df.index[-1] - equity_df.index[0]).days
        if total_days == 0:
            return 0.0
        
        total_return = (equity_df['total_value'].iloc[-1] - self.initial_capital) / self.initial_capital
        annualized_return = (1 + total_return) ** (365 / total_days) - 1
        return annualized_return
    
    def _calculate_max_drawdown(self, equity_series: pd.Series) -> float:
        """Calculate maximum drawdown"""
        peak = equity_series.expanding().max()
        drawdown = (equity_series - peak) / peak
        return drawdown.min()
    
    def get_current_positions(self) -> Dict[str, Position]:
        """Get current positions"""
        return self.positions.copy()
    
    def get_trade_history(self) -> List[Trade]:
        """Get trade history"""
        return self.trades.copy() 