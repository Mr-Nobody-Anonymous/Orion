import pandas as pd
import numpy as np
from typing import Dict, List, Any, Optional, Tuple
import logging
from datetime import datetime, timedelta
from dataclasses import dataclass
import matplotlib.pyplot as plt
import seaborn as sns

@dataclass
class FactorPerformance:
    """Factor performance metrics"""
    factor_name: str
    ic_mean: float  # Information Coefficient mean
    ic_std: float   # Information Coefficient standard deviation
    ic_ir: float    # Information Ratio
    rank_ic_mean: float  # Rank IC mean
    rank_ic_ir: float    # Rank IC IR
    win_rate: float      # Win rate
    avg_return: float    # Average return
    sharpe_ratio: float  # Sharpe ratio
    max_drawdown: float  # Maximum drawdown

@dataclass
class BacktestResult:
    """Backtest result data"""
    factor_name: str
    start_date: datetime
    end_date: datetime
    total_periods: int
    performance: FactorPerformance
    returns: pd.Series
    positions: pd.Series
    factor_values: pd.DataFrame

class FactorBacktest:
    """Factor backtesting engine"""
    
    def __init__(self, lookback_period: int = 252, holding_period: int = 21):
        self.lookback_period = lookback_period
        self.holding_period = holding_period
        self.logger = logging.getLogger(__name__)
    
    def run_factor_backtest(self, factor_data: pd.DataFrame, 
                          price_data: pd.DataFrame,
                          universe: List[str] = None,
                          rebalance_frequency: str = 'monthly') -> BacktestResult:
        """Run backtest for a single factor"""
        
        # Prepare data
        factor_data = self._prepare_factor_data(factor_data, universe)
        price_data = self._prepare_price_data(price_data, universe)
        
        # Calculate returns
        returns = self._calculate_returns(price_data)
        
        # Run factor backtest
        factor_returns = self._calculate_factor_returns(factor_data, returns, rebalance_frequency)
        
        # Calculate performance metrics
        performance = self._calculate_performance_metrics(factor_returns)
        
        # Create backtest result
        result = BacktestResult(
            factor_name=factor_data['factor_name'].iloc[0] if not factor_data.empty else 'unknown',
            start_date=factor_returns.index[0] if not factor_returns.empty else datetime.now(),
            end_date=factor_returns.index[-1] if not factor_returns.empty else datetime.now(),
            total_periods=len(factor_returns),
            performance=performance,
            returns=factor_returns,
            positions=pd.Series(),  # Would be calculated in full implementation
            factor_values=factor_data
        )
        
        return result
    
    def run_multi_factor_backtest(self, factor_data: pd.DataFrame,
                                price_data: pd.DataFrame,
                                factor_weights: Dict[str, float],
                                universe: List[str] = None) -> BacktestResult:
        """Run backtest for multiple factors with weights"""
        
        # Group by date and calculate composite factor
        composite_factor = self._calculate_composite_factor(factor_data, factor_weights)
        
        # Run backtest with composite factor
        return self.run_factor_backtest(composite_factor, price_data, universe)
    
    def _prepare_factor_data(self, factor_data: pd.DataFrame, 
                           universe: List[str] = None) -> pd.DataFrame:
        """Prepare factor data for backtesting"""
        if universe:
            factor_data = factor_data[factor_data['symbol'].isin(universe)]
        
        # Ensure we have required columns
        required_columns = ['symbol', 'date', 'factor_name', 'factor_value']
        missing_columns = [col for col in required_columns if col not in factor_data.columns]
        
        if missing_columns:
            raise ValueError(f"Missing required columns: {missing_columns}")
        
        # Convert date column to datetime
        factor_data['date'] = pd.to_datetime(factor_data['date'])
        
        # Sort by date
        factor_data = factor_data.sort_values('date')
        
        return factor_data
    
    def _prepare_price_data(self, price_data: pd.DataFrame, 
                          universe: List[str] = None) -> pd.DataFrame:
        """Prepare price data for backtesting"""
        if universe:
            price_data = price_data[price_data['symbol'].isin(universe)]
        
        # Ensure we have required columns
        required_columns = ['symbol', 'date', 'close']
        missing_columns = [col for col in required_columns if col not in price_data.columns]
        
        if missing_columns:
            raise ValueError(f"Missing required columns: {missing_columns}")
        
        # Convert date column to datetime
        price_data['date'] = pd.to_datetime(price_data['date'])
        
        # Pivot to wide format (symbols as columns)
        price_pivot = price_data.pivot(index='date', columns='symbol', values='close')
        
        return price_pivot
    
    def _calculate_returns(self, price_data: pd.DataFrame) -> pd.DataFrame:
        """Calculate returns from price data"""
        return price_data.pct_change().dropna()
    
    def _calculate_factor_returns(self, factor_data: pd.DataFrame, 
                                returns: pd.DataFrame,
                                rebalance_frequency: str = 'monthly') -> pd.Series:
        """Calculate factor returns"""
        factor_returns = []
        
        # Get unique dates
        dates = factor_data['date'].unique()
        dates = sorted(dates)
        
        for i, date in enumerate(dates):
            if i < self.lookback_period:
                continue
            
            # Get factor values for current date
            current_factors = factor_data[factor_data['date'] == date]
            
            if current_factors.empty:
                continue
            
            # Calculate forward returns
            forward_date = self._get_forward_date(date, rebalance_frequency)
            if forward_date not in returns.index:
                continue
            
            # Calculate factor-weighted returns
            factor_return = self._calculate_weighted_return(
                current_factors, returns.loc[forward_date]
            )
            
            factor_returns.append({
                'date': forward_date,
                'return': factor_return
            })
        
        if not factor_returns:
            return pd.Series()
        
        result_df = pd.DataFrame(factor_returns)
        return result_df.set_index('date')['return']
    
    def _calculate_weighted_return(self, factors: pd.DataFrame, 
                                 forward_returns: pd.Series) -> float:
        """Calculate factor-weighted return"""
        # Merge factors with forward returns
        merged = factors.merge(
            forward_returns.reset_index().rename(columns={'index': 'symbol', 0: 'return'}),
            on='symbol',
            how='inner'
        )
        
        if merged.empty:
            return 0.0
        
        # Calculate weights (normalized factor values)
        merged['weight'] = merged['factor_value'] / merged['factor_value'].abs().sum()
        
        # Calculate weighted return
        weighted_return = (merged['weight'] * merged['return']).sum()
        
        return weighted_return
    
    def _get_forward_date(self, current_date: datetime, 
                         frequency: str) -> datetime:
        """Get forward date based on rebalancing frequency"""
        if frequency == 'daily':
            return current_date + timedelta(days=1)
        elif frequency == 'weekly':
            return current_date + timedelta(weeks=1)
        elif frequency == 'monthly':
            # Add one month
            if current_date.month == 12:
                return current_date.replace(year=current_date.year + 1, month=1)
            else:
                return current_date.replace(month=current_date.month + 1)
        elif frequency == 'quarterly':
            # Add three months
            new_month = current_date.month + 3
            new_year = current_date.year + (new_month - 1) // 12
            new_month = ((new_month - 1) % 12) + 1
            return current_date.replace(year=new_year, month=new_month)
        else:
            raise ValueError(f"Unsupported frequency: {frequency}")
    
    def _calculate_composite_factor(self, factor_data: pd.DataFrame,
                                  factor_weights: Dict[str, float]) -> pd.DataFrame:
        """Calculate composite factor from multiple factors"""
        composite_data = []
        
        # Group by symbol and date
        for (symbol, date), group in factor_data.groupby(['symbol', 'date']):
            composite_value = 0.0
            total_weight = 0.0
            
            for factor_name, weight in factor_weights.items():
                factor_row = group[group['factor_name'] == factor_name]
                if not factor_row.empty:
                    composite_value += factor_row['factor_value'].iloc[0] * weight
                    total_weight += weight
            
            if total_weight > 0:
                composite_value /= total_weight
                
                composite_data.append({
                    'symbol': symbol,
                    'date': date,
                    'factor_name': 'composite',
                    'factor_value': composite_value
                })
        
        return pd.DataFrame(composite_data)
    
    def _calculate_performance_metrics(self, factor_returns: pd.Series) -> FactorPerformance:
        """Calculate performance metrics for factor returns"""
        if factor_returns.empty:
            return FactorPerformance(
                factor_name='unknown',
                ic_mean=0.0, ic_std=0.0, ic_ir=0.0,
                rank_ic_mean=0.0, rank_ic_ir=0.0,
                win_rate=0.0, avg_return=0.0,
                sharpe_ratio=0.0, max_drawdown=0.0
            )
        
        # Basic return metrics
        avg_return = factor_returns.mean()
        return_std = factor_returns.std()
        sharpe_ratio = avg_return / return_std if return_std > 0 else 0.0
        
        # Win rate
        win_rate = (factor_returns > 0).mean()
        
        # Maximum drawdown
        cumulative_returns = (1 + factor_returns).cumprod()
        rolling_max = cumulative_returns.expanding().max()
        drawdown = (cumulative_returns - rolling_max) / rolling_max
        max_drawdown = drawdown.min()
        
        # Information Coefficient (IC) - simplified calculation
        # In a full implementation, this would compare factor values with forward returns
        ic_mean = 0.0  # Would be calculated from factor-forward return correlation
        ic_std = 0.0
        ic_ir = ic_mean / ic_std if ic_std > 0 else 0.0
        
        # Rank IC
        rank_ic_mean = 0.0  # Would be calculated from rank correlation
        rank_ic_ir = 0.0
        
        return FactorPerformance(
            factor_name='factor',
            ic_mean=ic_mean,
            ic_std=ic_std,
            ic_ir=ic_ir,
            rank_ic_mean=rank_ic_mean,
            rank_ic_ir=rank_ic_ir,
            win_rate=win_rate,
            avg_return=avg_return,
            sharpe_ratio=sharpe_ratio,
            max_drawdown=max_drawdown
        )
    
    def calculate_information_coefficient(self, factor_data: pd.DataFrame,
                                        returns: pd.DataFrame,
                                        forward_period: int = 21) -> pd.Series:
        """Calculate Information Coefficient (IC) for a factor"""
        ic_series = []
        
        dates = factor_data['date'].unique()
        dates = sorted(dates)
        
        for i, date in enumerate(dates):
            if i + forward_period >= len(dates):
                break
            
            # Get current factor values
            current_factors = factor_data[factor_data['date'] == date]
            
            # Get forward returns
            forward_date = dates[i + forward_period]
            if forward_date not in returns.index:
                continue
            
            # Merge factor values with forward returns
            merged = current_factors.merge(
                returns.loc[forward_date].reset_index().rename(columns={'index': 'symbol', 0: 'return'}),
                on='symbol',
                how='inner'
            )
            
            if len(merged) < 10:  # Need minimum number of observations
                continue
            
            # Calculate correlation
            correlation = merged['factor_value'].corr(merged['return'])
            ic_series.append({
                'date': date,
                'ic': correlation
            })
        
        if not ic_series:
            return pd.Series()
        
        result_df = pd.DataFrame(ic_series)
        return result_df.set_index('date')['ic']
    
    def plot_factor_performance(self, backtest_result: BacktestResult,
                              save_path: Optional[str] = None):
        """Plot factor performance charts"""
        fig, axes = plt.subplots(2, 2, figsize=(15, 10))
        
        # Cumulative returns
        cumulative_returns = (1 + backtest_result.returns).cumprod()
        axes[0, 0].plot(cumulative_returns.index, cumulative_returns.values)
        axes[0, 0].set_title('Cumulative Factor Returns')
        axes[0, 0].set_ylabel('Cumulative Return')
        axes[0, 0].grid(True)
        
        # Return distribution
        axes[0, 1].hist(backtest_result.returns, bins=30, alpha=0.7)
        axes[0, 1].set_title('Factor Return Distribution')
        axes[0, 1].set_xlabel('Return')
        axes[0, 1].set_ylabel('Frequency')
        axes[0, 1].grid(True)
        
        # Drawdown
        cumulative_returns = (1 + backtest_result.returns).cumprod()
        rolling_max = cumulative_returns.expanding().max()
        drawdown = (cumulative_returns - rolling_max) / rolling_max
        axes[1, 0].fill_between(drawdown.index, drawdown.values, 0, alpha=0.3, color='red')
        axes[1, 0].set_title('Drawdown')
        axes[1, 0].set_ylabel('Drawdown')
        axes[1, 0].grid(True)
        
        # Rolling Sharpe ratio
        rolling_sharpe = backtest_result.returns.rolling(252).mean() / backtest_result.returns.rolling(252).std()
        axes[1, 1].plot(rolling_sharpe.index, rolling_sharpe.values)
        axes[1, 1].set_title('Rolling Sharpe Ratio (252-day)')
        axes[1, 1].set_ylabel('Sharpe Ratio')
        axes[1, 1].grid(True)
        
        plt.tight_layout()
        
        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
        
        plt.show()
    
    def generate_performance_report(self, backtest_result: BacktestResult) -> str:
        """Generate performance report"""
        perf = backtest_result.performance
        
        report = []
        report.append("=" * 50)
        report.append("FACTOR PERFORMANCE REPORT")
        report.append("=" * 50)
        report.append(f"Factor: {backtest_result.factor_name}")
        report.append(f"Period: {backtest_result.start_date.date()} to {backtest_result.end_date.date()}")
        report.append(f"Total Periods: {backtest_result.total_periods}")
        report.append("")
        
        report.append("RETURN METRICS:")
        report.append(f"Average Return: {perf.avg_return:.4f}")
        report.append(f"Sharpe Ratio: {perf.sharpe_ratio:.3f}")
        report.append(f"Win Rate: {perf.win_rate:.2%}")
        report.append(f"Maximum Drawdown: {perf.max_drawdown:.2%}")
        report.append("")
        
        report.append("INFORMATION COEFFICIENT:")
        report.append(f"IC Mean: {perf.ic_mean:.4f}")
        report.append(f"IC Std: {perf.ic_std:.4f}")
        report.append(f"IC IR: {perf.ic_ir:.3f}")
        report.append(f"Rank IC Mean: {perf.rank_ic_mean:.4f}")
        report.append(f"Rank IC IR: {perf.rank_ic_ir:.3f}")
        
        return "\n".join(report) 