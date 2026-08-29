import pandas as pd
import numpy as np
from typing import Dict, List, Any, Optional, Tuple
import logging
from datetime import datetime, timedelta
from dataclasses import dataclass

@dataclass
class Portfolio:
    """Portfolio data structure"""
    symbol: str
    weight: float
    entry_date: datetime
    entry_price: float
    current_price: float = 0.0
    current_weight: float = 0.0
    pnl: float = 0.0

@dataclass
class SelectionResult:
    """Stock selection result"""
    date: datetime
    selected_stocks: List[str]
    weights: Dict[str, float]
    portfolio_value: float
    rebalance_cost: float = 0.0

class StockSelector:
    """Stock selection and portfolio management"""
    
    def __init__(self, max_positions: int = 50, 
                 min_weight: float = 0.01,
                 max_weight: float = 0.05,
                 rebalance_frequency: str = 'monthly'):
        self.max_positions = max_positions
        self.min_weight = min_weight
        self.max_weight = max_weight
        self.rebalance_frequency = rebalance_frequency
        self.logger = logging.getLogger(__name__)
        
        # Portfolio tracking
        self.current_portfolio: Dict[str, Portfolio] = {}
        self.portfolio_history: List[SelectionResult] = []
    
    def select_stocks(self, factor_data: pd.DataFrame,
                     price_data: pd.DataFrame,
                     selection_method: str = 'top_n',
                     **kwargs) -> SelectionResult:
        """Select stocks based on factor data"""
        
        if selection_method == 'top_n':
            return self._select_top_n(factor_data, price_data, **kwargs)
        elif selection_method == 'equal_weight':
            return self._select_equal_weight(factor_data, price_data, **kwargs)
        elif selection_method == 'factor_weighted':
            return self._select_factor_weighted(factor_data, price_data, **kwargs)
        elif selection_method == 'risk_parity':
            return self._select_risk_parity(factor_data, price_data, **kwargs)
        else:
            raise ValueError(f"Unknown selection method: {selection_method}")
    
    def _select_top_n(self, factor_data: pd.DataFrame,
                     price_data: pd.DataFrame,
                     n: int = None,
                     factor_name: str = None) -> SelectionResult:
        """Select top N stocks by factor value"""
        
        if n is None:
            n = self.max_positions
        
        if factor_name is None:
            # Use the first available factor
            factor_name = factor_data['factor_name'].iloc[0]
        
        # Get latest factor values
        latest_date = factor_data['date'].max()
        latest_factors = factor_data[
            (factor_data['date'] == latest_date) & 
            (factor_data['factor_name'] == factor_name)
        ].copy()
        
        if latest_factors.empty:
            self.logger.warning(f"No factor data found for {factor_name} on {latest_date}")
            return SelectionResult(
                date=latest_date,
                selected_stocks=[],
                weights={},
                portfolio_value=0.0
            )
        
        # Sort by factor value and select top N
        latest_factors = latest_factors.sort_values('factor_value', ascending=False)
        selected_stocks = latest_factors.head(n)['symbol'].tolist()
        
        # Calculate equal weights
        weights = {symbol: 1.0 / len(selected_stocks) for symbol in selected_stocks}
        
        # Ensure weight constraints
        weights = self._apply_weight_constraints(weights)
        
        return SelectionResult(
            date=latest_date,
            selected_stocks=selected_stocks,
            weights=weights,
            portfolio_value=1.0  # Normalized to 1.0
        )
    
    def _select_equal_weight(self, factor_data: pd.DataFrame,
                           price_data: pd.DataFrame,
                           n: int = None) -> SelectionResult:
        """Select stocks with equal weights"""
        
        if n is None:
            n = self.max_positions
        
        # Get latest factor values
        latest_date = factor_data['date'].max()
        latest_factors = factor_data[factor_data['date'] == latest_date].copy()
        
        if latest_factors.empty:
            return SelectionResult(
                date=latest_date,
                selected_stocks=[],
                weights={},
                portfolio_value=0.0
            )
        
        # Get unique symbols
        symbols = latest_factors['symbol'].unique()
        
        # Select random subset if too many symbols
        if len(symbols) > n:
            symbols = np.random.choice(symbols, n, replace=False)
        
        # Equal weights
        weights = {symbol: 1.0 / len(symbols) for symbol in symbols}
        
        return SelectionResult(
            date=latest_date,
            selected_stocks=symbols.tolist(),
            weights=weights,
            portfolio_value=1.0
        )
    
    def _select_factor_weighted(self, factor_data: pd.DataFrame,
                              price_data: pd.DataFrame,
                              factor_name: str = None) -> SelectionResult:
        """Select stocks with weights proportional to factor values"""
        
        if factor_name is None:
            factor_name = factor_data['factor_name'].iloc[0]
        
        # Get latest factor values
        latest_date = factor_data['date'].max()
        latest_factors = factor_data[
            (factor_data['date'] == latest_date) & 
            (factor_data['factor_name'] == factor_name)
        ].copy()
        
        if latest_factors.empty:
            return SelectionResult(
                date=latest_date,
                selected_stocks=[],
                weights={},
                portfolio_value=0.0
            )
        
        # Select top stocks
        latest_factors = latest_factors.sort_values('factor_value', ascending=False)
        selected_factors = latest_factors.head(self.max_positions)
        
        # Calculate weights proportional to factor values
        total_factor_value = selected_factors['factor_value'].abs().sum()
        weights = {}
        
        for _, row in selected_factors.iterrows():
            weight = abs(row['factor_value']) / total_factor_value
            weights[row['symbol']] = weight
        
        # Apply weight constraints
        weights = self._apply_weight_constraints(weights)
        
        return SelectionResult(
            date=latest_date,
            selected_stocks=list(weights.keys()),
            weights=weights,
            portfolio_value=1.0
        )
    
    def _select_risk_parity(self, factor_data: pd.DataFrame,
                          price_data: pd.DataFrame,
                          lookback_period: int = 252) -> SelectionResult:
        """Select stocks using risk parity approach"""
        
        # Get latest factor values
        latest_date = factor_data['date'].max()
        latest_factors = factor_data[factor_data['date'] == latest_date].copy()
        
        if latest_factors.empty:
            return SelectionResult(
                date=latest_date,
                selected_stocks=[],
                weights={},
                portfolio_value=0.0
            )
        
        # Select top stocks by factor value
        factor_name = latest_factors['factor_name'].iloc[0]
        latest_factors = latest_factors[latest_factors['factor_name'] == factor_name]
        latest_factors = latest_factors.sort_values('factor_value', ascending=False)
        selected_symbols = latest_factors.head(self.max_positions)['symbol'].tolist()
        
        # Calculate volatility for selected stocks
        volatilities = {}
        for symbol in selected_symbols:
            symbol_prices = price_data[price_data['symbol'] == symbol]
            if len(symbol_prices) >= lookback_period:
                returns = symbol_prices['close'].pct_change().dropna()
                volatility = returns.std() * np.sqrt(252)
                volatilities[symbol] = volatility
        
        if not volatilities:
            return SelectionResult(
                date=latest_date,
                selected_stocks=[],
                weights={},
                portfolio_value=0.0
            )
        
        # Calculate risk parity weights
        total_risk = sum(1 / vol for vol in volatilities.values())
        weights = {symbol: (1 / vol) / total_risk for symbol, vol in volatilities.items()}
        
        # Apply weight constraints
        weights = self._apply_weight_constraints(weights)
        
        return SelectionResult(
            date=latest_date,
            selected_stocks=list(weights.keys()),
            weights=weights,
            portfolio_value=1.0
        )
    
    def _apply_weight_constraints(self, weights: Dict[str, float]) -> Dict[str, float]:
        """Apply minimum and maximum weight constraints"""
        
        # Apply maximum weight constraint
        for symbol in weights:
            if weights[symbol] > self.max_weight:
                weights[symbol] = self.max_weight
        
        # Normalize weights
        total_weight = sum(weights.values())
        if total_weight > 0:
            weights = {symbol: weight / total_weight for symbol, weight in weights.items()}
        
        # Remove stocks below minimum weight
        weights = {symbol: weight for symbol, weight in weights.items() 
                  if weight >= self.min_weight}
        
        # Renormalize if needed
        total_weight = sum(weights.values())
        if total_weight > 0:
            weights = {symbol: weight / total_weight for symbol, weight in weights.items()}
        
        return weights
    
    def update_portfolio(self, selection_result: SelectionResult,
                        current_prices: Dict[str, float]) -> Dict[str, float]:
        """Update portfolio with current prices and calculate P&L"""
        
        # Update current portfolio
        for symbol, weight in selection_result.weights.items():
            if symbol in self.current_portfolio:
                # Update existing position
                portfolio = self.current_portfolio[symbol]
                portfolio.current_price = current_prices.get(symbol, portfolio.current_price)
                portfolio.current_weight = weight
                portfolio.pnl = (portfolio.current_price / portfolio.entry_price - 1) * weight
            else:
                # Add new position
                entry_price = current_prices.get(symbol, 0.0)
                self.current_portfolio[symbol] = Portfolio(
                    symbol=symbol,
                    weight=weight,
                    entry_date=selection_result.date,
                    entry_price=entry_price,
                    current_price=entry_price,
                    current_weight=weight,
                    pnl=0.0
                )
        
        # Remove positions no longer in portfolio
        symbols_to_remove = [symbol for symbol in self.current_portfolio.keys() 
                           if symbol not in selection_result.weights]
        for symbol in symbols_to_remove:
            del self.current_portfolio[symbol]
        
        # Calculate total P&L
        total_pnl = sum(portfolio.pnl for portfolio in self.current_portfolio.values())
        
        return {
            'total_pnl': total_pnl,
            'positions': len(self.current_portfolio),
            'portfolio_value': 1.0 + total_pnl
        }
    
    def calculate_portfolio_metrics(self, price_data: pd.DataFrame,
                                  lookback_period: int = 252) -> Dict[str, float]:
        """Calculate portfolio performance metrics"""
        
        if not self.current_portfolio:
            return {}
        
        # Get portfolio returns
        portfolio_returns = []
        dates = sorted(price_data['date'].unique())
        
        for date in dates[-lookback_period:]:
            daily_return = 0.0
            for symbol, portfolio in self.current_portfolio.items():
                symbol_prices = price_data[price_data['symbol'] == symbol]
                symbol_prices = symbol_prices[symbol_prices['date'] <= date]
                
                if not symbol_prices.empty:
                    current_price = symbol_prices['close'].iloc[-1]
                    if portfolio.entry_price > 0:
                        symbol_return = (current_price / portfolio.entry_price - 1) * portfolio.weight
                        daily_return += symbol_return
            
            portfolio_returns.append(daily_return)
        
        if not portfolio_returns:
            return {}
        
        returns_series = pd.Series(portfolio_returns)
        
        # Calculate metrics
        metrics = {
            'total_return': (1 + returns_series).prod() - 1,
            'annualized_return': (1 + returns_series).prod() ** (252 / len(returns_series)) - 1,
            'volatility': returns_series.std() * np.sqrt(252),
            'sharpe_ratio': returns_series.mean() / returns_series.std() * np.sqrt(252) if returns_series.std() > 0 else 0,
            'max_drawdown': self._calculate_max_drawdown(returns_series),
            'win_rate': (returns_series > 0).mean()
        }
        
        return metrics
    
    def _calculate_max_drawdown(self, returns: pd.Series) -> float:
        """Calculate maximum drawdown"""
        cumulative_returns = (1 + returns).cumprod()
        rolling_max = cumulative_returns.expanding().max()
        drawdown = (cumulative_returns - rolling_max) / rolling_max
        return drawdown.min()
    
    def get_portfolio_summary(self) -> Dict[str, Any]:
        """Get current portfolio summary"""
        if not self.current_portfolio:
            return {}
        
        summary = {
            'total_positions': len(self.current_portfolio),
            'total_weight': sum(p.weight for p in self.current_portfolio.values()),
            'total_pnl': sum(p.pnl for p in self.current_portfolio.values()),
            'positions': []
        }
        
        for symbol, portfolio in self.current_portfolio.items():
            summary['positions'].append({
                'symbol': symbol,
                'weight': portfolio.weight,
                'entry_price': portfolio.entry_price,
                'current_price': portfolio.current_price,
                'pnl': portfolio.pnl,
                'pnl_pct': (portfolio.current_price / portfolio.entry_price - 1) * 100
            })
        
        return summary
    
    def export_portfolio(self, filepath: str, format: str = 'csv'):
        """Export portfolio to file"""
        summary = self.get_portfolio_summary()
        
        if not summary:
            self.logger.warning("No portfolio data to export")
            return
        
        # Create DataFrame
        positions_df = pd.DataFrame(summary['positions'])
        
        if format.lower() == 'csv':
            positions_df.to_csv(filepath, index=False)
        elif format.lower() == 'excel':
            positions_df.to_excel(filepath, index=False)
        else:
            raise ValueError(f"Unsupported format: {format}")
        
        self.logger.info(f"Portfolio exported to {filepath}")
    
    def rebalance_portfolio(self, new_selection: SelectionResult,
                          transaction_cost: float = 0.001) -> float:
        """Rebalance portfolio and calculate transaction costs"""
        
        rebalance_cost = 0.0
        
        # Calculate weight changes
        for symbol, new_weight in new_selection.weights.items():
            old_weight = self.current_portfolio.get(symbol, Portfolio(
                symbol=symbol, weight=0.0, entry_date=datetime.now(), entry_price=0.0
            )).weight
            
            weight_change = abs(new_weight - old_weight)
            rebalance_cost += weight_change * transaction_cost
        
        # Update portfolio
        self.current_portfolio.clear()
        for symbol, weight in new_selection.weights.items():
            self.current_portfolio[symbol] = Portfolio(
                symbol=symbol,
                weight=weight,
                entry_date=new_selection.date,
                entry_price=0.0,  # Will be updated with actual price
                current_weight=weight,
                pnl=0.0
            )
        
        return rebalance_cost 