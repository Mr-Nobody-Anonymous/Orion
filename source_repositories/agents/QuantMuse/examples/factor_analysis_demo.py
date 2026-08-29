#!/usr/bin/env python3
"""
Example script demonstrating quantitative factor analysis
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data_service.factors import FactorCalculator, FactorScreener, FactorBacktest, StockSelector, FactorOptimizer
from data_service.storage import DatabaseManager, FileStorage
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import logging

def setup_logging():
    """Setup logging configuration"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

def generate_sample_data():
    """Generate sample factor and price data for demonstration"""
    # Sample symbols
    symbols = ['AAPL', 'GOOGL', 'MSFT', 'AMZN', 'TSLA', 'META', 'NVDA', 'NFLX', 'AMD', 'INTC']
    
    # Generate sample price data
    price_data = []
    start_date = datetime(2023, 1, 1)
    
    for symbol in symbols:
        # Generate random price series
        np.random.seed(hash(symbol) % 1000)  # Consistent random seed per symbol
        base_price = np.random.uniform(50, 500)
        returns = np.random.normal(0.001, 0.02, 252)  # Daily returns
        prices = [base_price]
        
        for i in range(251):
            prices.append(prices[-1] * (1 + returns[i]))
        
        for i, price in enumerate(prices):
            date = start_date + timedelta(days=i)
            price_data.append({
                'symbol': symbol,
                'date': date,
                'close': price,
                'volume': np.random.randint(1000000, 10000000)
            })
    
    price_df = pd.DataFrame(price_data)
    
    # Generate sample factor data
    factor_data = []
    
    for symbol in symbols:
        symbol_prices = price_df[price_df['symbol'] == symbol]['close'].values
        
        # Calculate various factors
        for i in range(20, len(symbol_prices)):  # Start from day 20
            date = start_date + timedelta(days=i)
            
            # Price momentum factors
            momentum_20d = (symbol_prices[i] / symbol_prices[i-20] - 1) * 100
            momentum_60d = (symbol_prices[i] / symbol_prices[i-60] - 1) * 100 if i >= 60 else 0
            
            # Volatility factor
            returns = np.diff(symbol_prices[i-20:i+1]) / symbol_prices[i-20:i]
            volatility = np.std(returns) * np.sqrt(252) * 100
            
            # Technical factors
            ma_20 = np.mean(symbol_prices[i-20:i+1])
            ma_60 = np.mean(symbol_prices[i-60:i+1]) if i >= 60 else ma_20
            price_vs_ma20 = (symbol_prices[i] / ma_20 - 1) * 100
            
            # Add factor data
            factors = [
                ('momentum_20d', momentum_20d),
                ('momentum_60d', momentum_60d),
                ('volatility', volatility),
                ('price_vs_ma20', price_vs_ma20)
            ]
            
            for factor_name, factor_value in factors:
                factor_data.append({
                    'symbol': symbol,
                    'date': date,
                    'factor_name': factor_name,
                    'factor_value': factor_value
                })
    
    factor_df = pd.DataFrame(factor_data)
    
    return price_df, factor_df

def main():
    """Main function demonstrating factor analysis"""
    setup_logging()
    logger = logging.getLogger(__name__)
    
    logger.info("Starting quantitative factor analysis demonstration")
    
    # Generate sample data
    logger.info("Generating sample data...")
    price_data, factor_data = generate_sample_data()
    
    logger.info(f"Generated data for {len(price_data['symbol'].unique())} symbols")
    logger.info(f"Price data: {len(price_data)} records")
    logger.info(f"Factor data: {len(factor_data)} records")
    
    # Initialize components
    factor_calculator = FactorCalculator()
    factor_screener = FactorScreener()
    factor_backtest = FactorBacktest()
    stock_selector = StockSelector()
    factor_optimizer = FactorOptimizer()
    
    # Example 1: Factor Screening
    logger.info("\n=== Example 1: Factor Screening ===")
    
    # Create value screener
    value_screener = factor_screener.create_value_screener(
        max_pe=25.0, max_pb=3.0, min_dividend_yield=1.0
    )
    
    # Create momentum screener
    momentum_screener = factor_screener.create_momentum_screener(
        min_momentum=5.0, min_volume_momentum=2.0
    )
    
    # Screen stocks using momentum factor
    latest_date = factor_data['date'].max()
    latest_factors = factor_data[factor_data['date'] == latest_date]
    
    if not latest_factors.empty:
        # Run momentum screening
        momentum_results = momentum_screener.screen_stocks(latest_factors)
        
        logger.info(f"Momentum screening results: {len(momentum_results)} stocks selected")
        for i, result in enumerate(momentum_results[:5]):  # Show top 5
            logger.info(f"  {i+1}. {result.symbol}: Score={result.score:.3f}")
        
        # Export results
        factor_screener.export_results(momentum_results, "data/momentum_screening_results.csv")
    
    # Example 2: Factor Backtesting
    logger.info("\n=== Example 2: Factor Backtesting ===")
    
    # Run backtest for momentum factor
    momentum_factor_data = factor_data[factor_data['factor_name'] == 'momentum_20d']
    
    if not momentum_factor_data.empty:
        backtest_result = factor_backtest.run_factor_backtest(
            momentum_factor_data, price_data, rebalance_frequency='monthly'
        )
        
        logger.info(f"Backtest completed for {backtest_result.factor_name}")
        logger.info(f"Period: {backtest_result.start_date.date()} to {backtest_result.end_date.date()}")
        logger.info(f"Total periods: {backtest_result.total_periods}")
        
        # Generate performance report
        report = factor_backtest.generate_performance_report(backtest_result)
        logger.info("Performance Report:")
        logger.info(report)
        
        # Plot performance
        factor_backtest.plot_factor_performance(backtest_result, "data/momentum_factor_performance.png")
    
    # Example 3: Stock Selection
    logger.info("\n=== Example 3: Stock Selection ===")
    
    # Select stocks using top N method
    selection_result = stock_selector.select_stocks(
        factor_data, price_data,
        selection_method='top_n',
        n=5,
        factor_name='momentum_20d'
    )
    
    logger.info(f"Selected {len(selection_result.selected_stocks)} stocks:")
    for symbol, weight in selection_result.weights.items():
        logger.info(f"  {symbol}: {weight:.3f}")
    
    # Example 4: Factor Optimization
    logger.info("\n=== Example 4: Factor Optimization ===")
    
    # Optimize factor weights
    factor_names = ['momentum_20d', 'momentum_60d', 'volatility', 'price_vs_ma20']
    
    try:
        optimization_result = factor_optimizer.optimize_factor_weights(
            factor_data, price_data,
            objective_function='sharpe_ratio',
            method='scipy'
        )
        
        logger.info("Factor optimization completed:")
        logger.info(f"  Optimization time: {optimization_result.optimization_time:.2f} seconds")
        logger.info(f"  Convergence: {optimization_result.convergence}")
        logger.info(f"  Objective value: {optimization_result.objective_value:.4f}")
        
        logger.info("Optimal weights:")
        for factor_name, weight in optimization_result.optimal_weights.items():
            logger.info(f"  {factor_name}: {weight:.4f}")
        
        # Generate optimization report
        opt_report = factor_optimizer.generate_optimization_report(optimization_result)
        logger.info("Optimization Report:")
        logger.info(opt_report)
        
    except Exception as e:
        logger.warning(f"Factor optimization failed: {e}")
    
    # Example 5: Multi-Factor Analysis
    logger.info("\n=== Example 5: Multi-Factor Analysis ===")
    
    # Create multi-factor screener
    factor_weights = {
        'momentum_20d': 0.4,
        'momentum_60d': 0.3,
        'volatility': 0.2,
        'price_vs_ma20': 0.1
    }
    
    multi_factor_screener = factor_screener.create_multi_factor_screener(factor_weights)
    
    # Add market cap filter
    multi_factor_screener.add_market_cap_filter(min_market_cap=1000000000)  # $1B
    
    # Run multi-factor screening
    if not latest_factors.empty:
        multi_results = multi_factor_screener.screen_stocks(latest_factors)
        
        logger.info(f"Multi-factor screening results: {len(multi_results)} stocks selected")
        for i, result in enumerate(multi_results[:5]):  # Show top 5
            logger.info(f"  {i+1}. {result.symbol}: Score={result.score:.3f}")
        
        # Get screening summary
        summary = factor_screener.get_screening_summary(multi_results)
        logger.info(f"Screening summary: {summary}")
    
    # Example 6: Portfolio Management
    logger.info("\n=== Example 6: Portfolio Management ===")
    
    # Update portfolio with current prices
    current_prices = {}
    for symbol in selection_result.selected_stocks:
        symbol_prices = price_data[price_data['symbol'] == symbol]
        if not symbol_prices.empty:
            current_prices[symbol] = symbol_prices['close'].iloc[-1]
    
    portfolio_update = stock_selector.update_portfolio(selection_result, current_prices)
    logger.info(f"Portfolio update: {portfolio_update}")
    
    # Get portfolio summary
    portfolio_summary = stock_selector.get_portfolio_summary()
    logger.info(f"Portfolio summary: {portfolio_summary}")
    
    # Calculate portfolio metrics
    portfolio_metrics = stock_selector.calculate_portfolio_metrics(price_data)
    logger.info(f"Portfolio metrics: {portfolio_metrics}")
    
    # Example 7: Data Persistence
    logger.info("\n=== Example 7: Data Persistence ===")
    
    # Save factor data
    file_storage = FileStorage()
    file_storage.save_market_data_csv('factor_data', factor_data, 'daily')
    
    # Save screening results
    if 'momentum_results' in locals():
        factor_screener.export_results(momentum_results, "data/momentum_screening.csv")
    
    # Save portfolio
    stock_selector.export_portfolio("data/portfolio.csv")
    
    logger.info("All data saved to files")
    
    logger.info("Quantitative factor analysis demonstration completed")

if __name__ == "__main__":
    main() 