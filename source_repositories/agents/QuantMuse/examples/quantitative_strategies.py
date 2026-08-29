#!/usr/bin/env python3
"""
Quantitative Trading Strategies using Factor Analysis Framework
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data_service.factors import *
from data_service.storage import DatabaseManager, FileStorage
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import logging

class QuantitativeStrategies:
    """Collection of quantitative trading strategies"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.factor_calculator = FactorCalculator()
        self.factor_screener = FactorScreener()
        self.factor_backtest = FactorBacktest()
        self.stock_selector = StockSelector()
        self.factor_optimizer = FactorOptimizer()
    
    def momentum_strategy(self, factor_data: pd.DataFrame, price_data: pd.DataFrame,
                         lookback_period: int = 60, top_n: int = 20) -> Dict[str, Any]:
        """
        Strategy 1: Momentum Strategy
        - Select stocks with highest momentum
        - Rebalance monthly
        - Equal weight portfolio
        """
        self.logger.info("Running Momentum Strategy")
        
        # Create momentum screener
        momentum_screener = self.factor_screener.create_momentum_screener(
            min_momentum=5.0, min_volume_momentum=2.0
        )
        
        # Screen stocks
        screening_results = momentum_screener.screen_stocks(factor_data)
        
        # Select top N stocks
        selection_result = self.stock_selector.select_stocks(
            factor_data, price_data,
            selection_method='top_n',
            n=top_n,
            factor_name='momentum_60d'
        )
        
        # Backtest strategy
        backtest_result = self.factor_backtest.run_factor_backtest(
            factor_data[factor_data['factor_name'] == 'momentum_60d'],
            price_data,
            rebalance_frequency='monthly'
        )
        
        return {
            'strategy_name': 'Momentum Strategy',
            'selected_stocks': selection_result.selected_stocks,
            'weights': selection_result.weights,
            'backtest_result': backtest_result,
            'screening_results': screening_results
        }
    
    def value_strategy(self, factor_data: pd.DataFrame, price_data: pd.DataFrame,
                      max_pe: float = 15.0, max_pb: float = 2.0, top_n: int = 30) -> Dict[str, Any]:
        """
        Strategy 2: Value Strategy
        - Select stocks with low P/E and P/B ratios
        - High dividend yield
        - Rebalance quarterly
        """
        self.logger.info("Running Value Strategy")
        
        # Create value screener
        value_screener = self.factor_screener.create_value_screener(
            max_pe=max_pe, max_pb=max_pb, min_dividend_yield=2.0
        )
        
        # Add quality filters
        value_screener.add_criteria(ScreeningCriteria(
            factor_name='roe',
            min_value=10.0,
            weight=0.5
        ))
        
        # Screen stocks
        screening_results = value_screener.screen_stocks(factor_data)
        
        # Select stocks with factor-weighted approach
        selection_result = self.stock_selector.select_stocks(
            factor_data, price_data,
            selection_method='factor_weighted',
            factor_name='pe_ratio'  # Lower P/E gets higher weight
        )
        
        # Backtest strategy
        backtest_result = self.factor_backtest.run_factor_backtest(
            factor_data[factor_data['factor_name'] == 'pe_ratio'],
            price_data,
            rebalance_frequency='quarterly'
        )
        
        return {
            'strategy_name': 'Value Strategy',
            'selected_stocks': selection_result.selected_stocks,
            'weights': selection_result.weights,
            'backtest_result': backtest_result,
            'screening_results': screening_results
        }
    
    def quality_growth_strategy(self, factor_data: pd.DataFrame, price_data: pd.DataFrame,
                              min_roe: float = 15.0, min_growth: float = 10.0) -> Dict[str, Any]:
        """
        Strategy 3: Quality Growth Strategy
        - High ROE companies with growth
        - Low debt levels
        - Strong profitability
        """
        self.logger.info("Running Quality Growth Strategy")
        
        # Create quality screener
        quality_screener = self.factor_screener.create_quality_screener(
            min_roe=min_roe, max_debt_equity=0.5, min_current_ratio=1.5
        )
        
        # Add growth criteria
        quality_screener.add_criteria(ScreeningCriteria(
            factor_name='momentum_60d',
            min_value=min_growth,
            weight=0.3
        ))
        
        # Screen stocks
        screening_results = quality_screener.screen_stocks(factor_data)
        
        # Select stocks
        selection_result = self.stock_selector.select_stocks(
            factor_data, price_data,
            selection_method='factor_weighted',
            factor_name='roe'
        )
        
        return {
            'strategy_name': 'Quality Growth Strategy',
            'selected_stocks': selection_result.selected_stocks,
            'weights': selection_result.weights,
            'screening_results': screening_results
        }
    
    def multi_factor_strategy(self, factor_data: pd.DataFrame, price_data: pd.DataFrame,
                            factor_weights: Dict[str, float] = None) -> Dict[str, Any]:
        """
        Strategy 4: Multi-Factor Strategy
        - Combine multiple factors with optimized weights
        - Risk parity approach
        """
        self.logger.info("Running Multi-Factor Strategy")
        
        if factor_weights is None:
            factor_weights = {
                'momentum_60d': 0.3,
                'pe_ratio': 0.2,
                'roe': 0.2,
                'price_volatility': 0.15,
                'market_cap': 0.15
            }
        
        # Create multi-factor screener
        multi_screener = self.factor_screener.create_multi_factor_screener(factor_weights)
        
        # Add risk filters
        multi_screener.add_volatility_filter(max_volatility=30.0)
        multi_screener.add_market_cap_filter(min_market_cap=1000000000)  # $1B
        
        # Screen stocks
        screening_results = multi_screener.screen_stocks(factor_data)
        
        # Optimize factor weights
        optimization_result = self.factor_optimizer.optimize_factor_weights(
            factor_data, price_data,
            objective_function='sharpe_ratio',
            method='scipy'
        )
        
        # Use optimized weights for selection
        optimized_weights = optimization_result.optimal_weights
        
        # Select stocks with risk parity
        selection_result = self.stock_selector.select_stocks(
            factor_data, price_data,
            selection_method='risk_parity'
        )
        
        # Backtest with optimized weights
        backtest_result = self.factor_backtest.run_multi_factor_backtest(
            factor_data, price_data, optimized_weights
        )
        
        return {
            'strategy_name': 'Multi-Factor Strategy',
            'selected_stocks': selection_result.selected_stocks,
            'weights': selection_result.weights,
            'optimized_weights': optimized_weights,
            'backtest_result': backtest_result,
            'screening_results': screening_results
        }
    
    def mean_reversion_strategy(self, factor_data: pd.DataFrame, price_data: pd.DataFrame,
                              rsi_oversold: float = 30.0, rsi_overbought: float = 70.0) -> Dict[str, Any]:
        """
        Strategy 5: Mean Reversion Strategy
        - Buy oversold stocks (low RSI)
        - Sell overbought stocks (high RSI)
        - Technical indicators based
        """
        self.logger.info("Running Mean Reversion Strategy")
        
        # Create custom screener for mean reversion
        mean_reversion_screener = self.factor_screener()
        
        # Add RSI criteria (buy oversold)
        mean_reversion_screener.add_criteria(ScreeningCriteria(
            factor_name='rsi',
            max_value=rsi_oversold,
            weight=1.0
        ))
        
        # Add momentum criteria (avoid strong downtrends)
        mean_reversion_screener.add_criteria(ScreeningCriteria(
            factor_name='momentum_20d',
            min_value=-20.0,  # Not too negative
            max_value=0.0,    # But still negative
            weight=0.5
        ))
        
        # Add volatility filter (avoid extremely volatile stocks)
        mean_reversion_screener.add_volatility_filter(max_volatility=40.0)
        
        # Screen stocks
        screening_results = mean_reversion_screener.screen_stocks(factor_data)
        
        # Select stocks with equal weights
        selection_result = self.stock_selector.select_stocks(
            factor_data, price_data,
            selection_method='equal_weight'
        )
        
        return {
            'strategy_name': 'Mean Reversion Strategy',
            'selected_stocks': selection_result.selected_stocks,
            'weights': selection_result.weights,
            'screening_results': screening_results
        }
    
    def low_volatility_strategy(self, factor_data: pd.DataFrame, price_data: pd.DataFrame,
                              max_volatility: float = 15.0, min_dividend: float = 1.5) -> Dict[str, Any]:
        """
        Strategy 6: Low Volatility Strategy
        - Select low volatility stocks
        - High dividend yield
        - Defensive approach
        """
        self.logger.info("Running Low Volatility Strategy")
        
        # Create custom screener
        low_vol_screener = self.factor_screener()
        
        # Add volatility criteria
        low_vol_screener.add_criteria(ScreeningCriteria(
            factor_name='price_volatility',
            max_value=max_volatility,
            weight=1.0
        ))
        
        # Add dividend criteria
        low_vol_screener.add_criteria(ScreeningCriteria(
            factor_name='dividend_yield',
            min_value=min_dividend,
            weight=0.8
        ))
        
        # Add quality criteria
        low_vol_screener.add_criteria(ScreeningCriteria(
            factor_name='debt_to_equity',
            max_value=0.6,
            weight=0.5
        ))
        
        # Screen stocks
        screening_results = low_vol_screener.screen_stocks(factor_data)
        
        # Select stocks with factor-weighted approach
        selection_result = self.stock_selector.select_stocks(
            factor_data, price_data,
            selection_method='factor_weighted',
            factor_name='price_volatility'  # Lower volatility gets higher weight
        )
        
        return {
            'strategy_name': 'Low Volatility Strategy',
            'selected_stocks': selection_result.selected_stocks,
            'weights': selection_result.weights,
            'screening_results': screening_results
        }
    
    def sector_rotation_strategy(self, factor_data: pd.DataFrame, price_data: pd.DataFrame,
                               sector_data: pd.DataFrame) -> Dict[str, Any]:
        """
        Strategy 7: Sector Rotation Strategy
        - Rotate between sectors based on momentum
        - Top-down approach
        """
        self.logger.info("Running Sector Rotation Strategy")
        
        # This would require sector-level data
        # For demonstration, we'll use a simplified approach
        
        # Create momentum screener for sectors
        sector_screener = self.factor_screener.create_momentum_screener(
            min_momentum=8.0
        )
        
        # Select top performing sectors
        sector_results = sector_screener.screen_stocks(sector_data)
        
        # Within each sector, select top stocks
        selected_stocks = []
        weights = {}
        
        for sector_result in sector_results[:3]:  # Top 3 sectors
            sector_symbols = [s for s in factor_data['symbol'] if s.startswith(sector_result.symbol)]
            sector_factor_data = factor_data[factor_data['symbol'].isin(sector_symbols)]
            
            if not sector_factor_data.empty:
                # Select top stocks in sector
                sector_selection = self.stock_selector.select_stocks(
                    sector_factor_data, price_data,
                    selection_method='top_n',
                    n=5,
                    factor_name='momentum_60d'
                )
                
                selected_stocks.extend(sector_selection.selected_stocks)
                
                # Equal weight within sector
                sector_weight = 1.0 / 3  # Equal weight across sectors
                stock_weight = sector_weight / len(sector_selection.selected_stocks)
                
                for stock in sector_selection.selected_stocks:
                    weights[stock] = stock_weight
        
        return {
            'strategy_name': 'Sector Rotation Strategy',
            'selected_stocks': selected_stocks,
            'weights': weights,
            'sector_results': sector_results
        }
    
    def risk_parity_strategy(self, factor_data: pd.DataFrame, price_data: pd.DataFrame,
                           target_volatility: float = 10.0) -> Dict[str, Any]:
        """
        Strategy 8: Risk Parity Strategy
        - Equal risk contribution from each position
        - Volatility targeting
        """
        self.logger.info("Running Risk Parity Strategy")
        
        # Create quality screener for initial filtering
        quality_screener = self.factor_screener.create_quality_screener(
            min_roe=12.0, max_debt_equity=0.7
        )
        
        # Screen stocks
        screening_results = quality_screener.screen_stocks(factor_data)
        
        # Select stocks with risk parity
        selection_result = self.stock_selector.select_stocks(
            factor_data, price_data,
            selection_method='risk_parity'
        )
        
        # Calculate portfolio volatility
        portfolio_metrics = self.stock_selector.calculate_portfolio_metrics(price_data)
        
        # Adjust weights to target volatility
        current_vol = portfolio_metrics.get('volatility', 15.0)
        if current_vol > 0:
            adjustment_factor = target_volatility / current_vol
            adjusted_weights = {symbol: weight * adjustment_factor 
                              for symbol, weight in selection_result.weights.items()}
        else:
            adjusted_weights = selection_result.weights
        
        return {
            'strategy_name': 'Risk Parity Strategy',
            'selected_stocks': selection_result.selected_stocks,
            'weights': adjusted_weights,
            'target_volatility': target_volatility,
            'current_volatility': current_vol,
            'screening_results': screening_results
        }
    
    def run_strategy_comparison(self, factor_data: pd.DataFrame, price_data: pd.DataFrame) -> Dict[str, Any]:
        """Run all strategies and compare performance"""
        
        strategies = [
            self.momentum_strategy,
            self.value_strategy,
            self.quality_growth_strategy,
            self.multi_factor_strategy,
            self.mean_reversion_strategy,
            self.low_volatility_strategy,
            self.risk_parity_strategy
        ]
        
        results = {}
        
        for strategy_func in strategies:
            try:
                strategy_name = strategy_func.__name__
                self.logger.info(f"Running {strategy_name}")
                
                result = strategy_func(factor_data, price_data)
                results[strategy_name] = result
                
            except Exception as e:
                self.logger.error(f"Error running {strategy_name}: {e}")
                results[strategy_name] = {'error': str(e)}
        
        return results
    
    def generate_strategy_report(self, strategy_results: Dict[str, Any]) -> str:
        """Generate comprehensive strategy comparison report"""
        
        report = []
        report.append("=" * 60)
        report.append("QUANTITATIVE STRATEGY COMPARISON REPORT")
        report.append("=" * 60)
        report.append("")
        
        for strategy_name, result in strategy_results.items():
            if 'error' in result:
                report.append(f"❌ {strategy_name}: {result['error']}")
                continue
            
            report.append(f"📊 {result['strategy_name']}")
            report.append("-" * 40)
            
            # Strategy details
            report.append(f"Selected Stocks: {len(result['selected_stocks'])}")
            report.append(f"Top 5 Stocks: {', '.join(result['selected_stocks'][:5])}")
            
            # Performance metrics (if available)
            if 'backtest_result' in result:
                perf = result['backtest_result'].performance
                report.append(f"Sharpe Ratio: {perf.sharpe_ratio:.3f}")
                report.append(f"Win Rate: {perf.win_rate:.2%}")
                report.append(f"Max Drawdown: {perf.max_drawdown:.2%}")
            
            report.append("")
        
        return "\n".join(report)

def main():
    """Main function to demonstrate strategies"""
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)
    
    logger.info("Starting Quantitative Strategy Demonstration")
    
    # Initialize strategies
    strategies = QuantitativeStrategies()
    
    # Generate sample data (you would use real data in practice)
    from factor_analysis_demo import generate_sample_data
    price_data, factor_data = generate_sample_data()
    
    # Run strategy comparison
    logger.info("Running strategy comparison...")
    strategy_results = strategies.run_strategy_comparison(factor_data, price_data)
    
    # Generate report
    report = strategies.generate_strategy_report(strategy_results)
    logger.info("Strategy Comparison Report:")
    logger.info(report)
    
    # Save results
    with open("data/strategy_comparison_report.txt", "w") as f:
        f.write(report)
    
    logger.info("Strategy demonstration completed")

if __name__ == "__main__":
    main() 