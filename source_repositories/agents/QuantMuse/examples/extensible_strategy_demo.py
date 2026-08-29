#!/usr/bin/env python3
"""
Demonstration of the extensible strategy framework
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data_service.strategies import StrategyBase, StrategyResult, strategy_registry, StrategyRunner, StrategyOptimizer
from data_service.strategies.builtin_strategies import register_builtin_strategies
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import logging

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Custom Strategy Example
class CustomMomentumStrategy(StrategyBase):
    """Custom momentum strategy with additional filters"""
    
    def __init__(self):
        super().__init__(
            name="CustomMomentumStrategy",
            description="Custom momentum strategy with volume and volatility filters"
        )
    
    def get_parameter_schema(self) -> Dict[str, Any]:
        return {
            'lookback_period': {'type': 'int', 'default': 60, 'min': 20, 'max': 252},
            'top_n': {'type': 'int', 'default': 15, 'min': 5, 'max': 50},
            'min_momentum': {'type': 'float', 'default': 8.0, 'min': 0.0, 'max': 50.0},
            'min_volume_momentum': {'type': 'float', 'default': 3.0, 'min': 0.0, 'max': 20.0},
            'max_volatility': {'type': 'float', 'default': 25.0, 'min': 10.0, 'max': 50.0}
        }
    
    def generate_signals(self, factor_data: pd.DataFrame, 
                        price_data: pd.DataFrame,
                        **kwargs) -> StrategyResult:
        
        # Get parameters
        lookback_period = self.parameters.get('lookback_period', 60)
        top_n = self.parameters.get('top_n', 15)
        min_momentum = self.parameters.get('min_momentum', 8.0)
        min_volume_momentum = self.parameters.get('min_volume_momentum', 3.0)
        max_volatility = self.parameters.get('max_volatility', 25.0)
        
        # Filter by momentum
        momentum_factor = f'momentum_{lookback_period}d'
        momentum_data = factor_data[factor_data['factor_name'] == momentum_factor]
        high_momentum = momentum_data[momentum_data['factor_value'] >= min_momentum]
        
        # Filter by volume momentum
        volume_data = factor_data[factor_data['factor_name'] == 'volume_momentum_20d']
        high_volume = volume_data[volume_data['factor_value'] >= min_volume_momentum]
        
        # Filter by volatility
        volatility_data = factor_data[factor_data['factor_name'] == 'price_volatility']
        low_volatility = volatility_data[volatility_data['factor_value'] <= max_volatility]
        
        # Get common symbols
        symbols1 = set(high_momentum['symbol'])
        symbols2 = set(high_volume['symbol'])
        symbols3 = set(low_volatility['symbol'])
        
        selected_symbols = list(symbols1 & symbols2 & symbols3)
        
        # Select top N by momentum
        if len(selected_symbols) > top_n:
            symbol_momentum = {}
            for symbol in selected_symbols:
                symbol_data = high_momentum[high_momentum['symbol'] == symbol]
                if not symbol_data.empty:
                    symbol_momentum[symbol] = symbol_data['factor_value'].iloc[0]
            
            # Sort by momentum and select top N
            sorted_symbols = sorted(symbol_momentum.items(), key=lambda x: x[1], reverse=True)
            selected_symbols = [symbol for symbol, _ in sorted_symbols[:top_n]]
        
        # Equal weights
        weights = {symbol: 1.0 / len(selected_symbols) for symbol in selected_symbols}
        
        # Calculate performance metrics
        performance_metrics = {
            'num_stocks': len(selected_symbols),
            'avg_momentum': np.mean([symbol_momentum.get(s, 0) for s in selected_symbols]),
            'momentum_std': np.std([symbol_momentum.get(s, 0) for s in selected_symbols])
        }
        
        return StrategyResult(
            strategy_name=self.name,
            selected_stocks=selected_symbols,
            weights=weights,
            parameters=self.parameters,
            execution_time=datetime.now(),
            performance_metrics=performance_metrics,
            metadata={'filters_applied': ['momentum', 'volume', 'volatility']}
        )

class SectorRotationStrategy(StrategyBase):
    """Sector rotation strategy"""
    
    def __init__(self):
        super().__init__(
            name="SectorRotationStrategy",
            description="Rotate between sectors based on momentum"
        )
    
    def get_parameter_schema(self) -> Dict[str, Any]:
        return {
            'num_sectors': {'type': 'int', 'default': 3, 'min': 2, 'max': 5},
            'stocks_per_sector': {'type': 'int', 'default': 5, 'min': 3, 'max': 10},
            'min_sector_momentum': {'type': 'float', 'default': 5.0, 'min': 0.0, 'max': 20.0}
        }
    
    def generate_signals(self, factor_data: pd.DataFrame, 
                        price_data: pd.DataFrame,
                        **kwargs) -> StrategyResult:
        
        # Get parameters
        num_sectors = self.parameters.get('num_sectors', 3)
        stocks_per_sector = self.parameters.get('stocks_per_sector', 5)
        min_sector_momentum = self.parameters.get('min_sector_momentum', 5.0)
        
        # This is a simplified implementation
        # In practice, you would need sector-level data
        
        # For demonstration, we'll use a simple approach
        momentum_data = factor_data[factor_data['factor_name'] == 'momentum_60d']
        
        # Group by first letter (simulating sectors)
        sector_momentum = {}
        for _, row in momentum_data.iterrows():
            sector = row['symbol'][0]  # Use first letter as sector
            if sector not in sector_momentum:
                sector_momentum[sector] = []
            sector_momentum[sector].append(row['factor_value'])
        
        # Calculate average momentum per sector
        sector_avg_momentum = {}
        for sector, values in sector_momentum.items():
            if len(values) >= stocks_per_sector:
                sector_avg_momentum[sector] = np.mean(values)
        
        # Select top sectors
        sorted_sectors = sorted(sector_avg_momentum.items(), key=lambda x: x[1], reverse=True)
        selected_sectors = [sector for sector, momentum in sorted_sectors[:num_sectors] 
                          if momentum >= min_sector_momentum]
        
        # Select top stocks from each sector
        selected_stocks = []
        weights = {}
        
        for sector in selected_sectors:
            sector_symbols = [s for s in momentum_data['symbol'] if s.startswith(sector)]
            sector_data = momentum_data[momentum_data['symbol'].isin(sector_symbols)]
            
            if len(sector_data) >= stocks_per_sector:
                top_stocks = sector_data.nlargest(stocks_per_sector, 'factor_value')
                
                for _, row in top_stocks.iterrows():
                    selected_stocks.append(row['symbol'])
                    weights[row['symbol']] = 1.0 / (len(selected_sectors) * stocks_per_sector)
        
        # Calculate performance metrics
        performance_metrics = {
            'num_stocks': len(selected_stocks),
            'num_sectors': len(selected_sectors),
            'avg_sector_momentum': np.mean([sector_avg_momentum[s] for s in selected_sectors])
        }
        
        return StrategyResult(
            strategy_name=self.name,
            selected_stocks=selected_stocks,
            weights=weights,
            parameters=self.parameters,
            execution_time=datetime.now(),
            performance_metrics=performance_metrics,
            metadata={'selected_sectors': selected_sectors}
        )

def generate_sample_data():
    """Generate sample data for demonstration"""
    symbols = ['AAPL', 'GOOGL', 'MSFT', 'AMZN', 'TSLA', 'META', 'NVDA', 'NFLX', 'AMD', 'INTC',
               'JNJ', 'PG', 'KO', 'WMT', 'MCD', 'DIS', 'V', 'JPM', 'BAC', 'WFC']
    
    # Generate sample factor data
    factor_data = []
    start_date = datetime(2023, 1, 1)
    
    for symbol in symbols:
        # Generate random factor values
        np.random.seed(hash(symbol) % 1000)
        
        for i in range(20):  # 20 days of data
            date = start_date + timedelta(days=i)
            
            # Momentum factors
            momentum_60d = np.random.uniform(-30, 50)
            momentum_20d = np.random.uniform(-20, 30)
            
            # Volume momentum
            volume_momentum = np.random.uniform(-10, 20)
            
            # Volatility
            volatility = np.random.uniform(10, 40)
            
            # RSI
            rsi = np.random.uniform(20, 80)
            
            # Value factors
            pe_ratio = np.random.uniform(5, 30)
            pb_ratio = np.random.uniform(0.5, 5)
            dividend_yield = np.random.uniform(0, 5)
            
            # Quality factors
            roe = np.random.uniform(5, 25)
            debt_equity = np.random.uniform(0, 1)
            current_ratio = np.random.uniform(0.5, 3)
            
            factors = [
                ('momentum_60d', momentum_60d),
                ('momentum_20d', momentum_20d),
                ('volume_momentum_20d', volume_momentum),
                ('price_volatility', volatility),
                ('rsi', rsi),
                ('pe_ratio', pe_ratio),
                ('pb_ratio', pb_ratio),
                ('dividend_yield', dividend_yield),
                ('roe', roe),
                ('debt_to_equity', debt_equity),
                ('current_ratio', current_ratio)
            ]
            
            for factor_name, factor_value in factors:
                factor_data.append({
                    'symbol': symbol,
                    'date': date,
                    'factor_name': factor_name,
                    'factor_value': factor_value
                })
    
    # Generate sample price data
    price_data = []
    for symbol in symbols:
        np.random.seed(hash(symbol) % 1000)
        base_price = np.random.uniform(50, 500)
        
        for i in range(20):
            date = start_date + timedelta(days=i)
            price = base_price * (1 + np.random.normal(0, 0.02))
            price_data.append({
                'symbol': symbol,
                'date': date,
                'close': price,
                'volume': np.random.randint(1000000, 10000000)
            })
    
    return pd.DataFrame(factor_data), pd.DataFrame(price_data)

def main():
    """Main demonstration function"""
    logger.info("Starting Extensible Strategy Framework Demonstration")
    
    # Register built-in strategies
    num_builtin = register_builtin_strategies()
    logger.info(f"Registered {num_builtin} built-in strategies")
    
    # Register custom strategies
    custom_strategies = [CustomMomentumStrategy, SectorRotationStrategy]
    for strategy_class in custom_strategies:
        strategy_registry.register_strategy(strategy_class)
    
    logger.info(f"Registered {len(custom_strategies)} custom strategies")
    
    # List all registered strategies
    all_strategies = strategy_registry.list_strategies()
    logger.info(f"All registered strategies: {all_strategies}")
    
    # Generate sample data
    factor_data, price_data = generate_sample_data()
    logger.info(f"Generated data: {len(factor_data)} factor records, {len(price_data)} price records")
    
    # Initialize components
    strategy_runner = StrategyRunner()
    strategy_optimizer = StrategyOptimizer()
    
    # Example 1: Run built-in strategy
    logger.info("\n=== Example 1: Running Built-in Strategy ===")
    
    momentum_result = strategy_runner.run_strategy(
        "MomentumStrategy",
        factor_data, price_data,
        parameters={'lookback_period': 60, 'top_n': 10}
    )
    
    logger.info(f"Momentum Strategy Result:")
    logger.info(f"  Selected stocks: {momentum_result.selected_stocks}")
    logger.info(f"  Number of stocks: {momentum_result.performance_metrics['num_stocks']}")
    
    # Example 2: Run custom strategy
    logger.info("\n=== Example 2: Running Custom Strategy ===")
    
    custom_result = strategy_runner.run_strategy(
        "CustomMomentumStrategy",
        factor_data, price_data,
        parameters={'top_n': 8, 'min_momentum': 10.0, 'max_volatility': 20.0}
    )
    
    logger.info(f"Custom Momentum Strategy Result:")
    logger.info(f"  Selected stocks: {custom_result.selected_stocks}")
    logger.info(f"  Average momentum: {custom_result.performance_metrics['avg_momentum']:.2f}")
    
    # Example 3: Run multiple strategies
    logger.info("\n=== Example 3: Running Multiple Strategies ===")
    
    strategy_configs = [
        {'name': 'MomentumStrategy', 'parameters': {'top_n': 10}},
        {'name': 'ValueStrategy', 'parameters': {'top_n': 15}},
        {'name': 'CustomMomentumStrategy', 'parameters': {'top_n': 8}}
    ]
    
    multiple_results = strategy_runner.run_multiple_strategies(
        strategy_configs, factor_data, price_data
    )
    
    for strategy_name, result in multiple_results.items():
        if result:
            logger.info(f"{strategy_name}: {len(result.selected_stocks)} stocks selected")
        else:
            logger.info(f"{strategy_name}: Failed to execute")
    
    # Example 4: Strategy ensemble
    logger.info("\n=== Example 4: Strategy Ensemble ===")
    
    ensemble_result = strategy_runner.run_strategy_ensemble(
        ['MomentumStrategy', 'ValueStrategy'],
        factor_data, price_data,
        ensemble_method='equal_weight'
    )
    
    logger.info(f"Ensemble Result:")
    logger.info(f"  Total stocks: {len(ensemble_result.selected_stocks)}")
    logger.info(f"  Ensemble method: {ensemble_result.parameters['ensemble_method']}")
    
    # Example 5: Strategy optimization
    logger.info("\n=== Example 5: Strategy Optimization ===")
    
    try:
        optimization_result = strategy_optimizer.optimize_strategy(
            "MomentumStrategy",
            factor_data, price_data,
            parameter_ranges={
                'lookback_period': (20, 120),
                'top_n': (5, 30),
                'min_momentum': (0.0, 20.0)
            },
            objective_function='sharpe_ratio',
            optimization_method='scipy'
        )
        
        logger.info(f"Optimization Result:")
        logger.info(f"  Optimized parameters: {optimization_result['optimized_parameters']}")
        logger.info(f"  Objective value: {optimization_result['objective_value']:.4f}")
        logger.info(f"  Optimization time: {optimization_result['optimization_time']}")
        
    except Exception as e:
        logger.warning(f"Optimization failed: {e}")
    
    # Example 6: Grid search optimization
    logger.info("\n=== Example 6: Grid Search Optimization ===")
    
    grid_result = strategy_optimizer.grid_search_optimization(
        "ValueStrategy",
        factor_data, price_data,
        parameter_grid={
            'max_pe': [10.0, 15.0, 20.0],
            'max_pb': [1.5, 2.0, 2.5],
            'top_n': [10, 20, 30]
        },
        objective_function='sharpe_ratio'
    )
    
    if grid_result:
        logger.info(f"Grid Search Result:")
        logger.info(f"  Best parameters: {grid_result['optimized_parameters']}")
        logger.info(f"  Best objective value: {grid_result['objective_value']:.4f}")
        logger.info(f"  Iterations: {grid_result['iterations']}")
    
    # Example 7: Get strategy information
    logger.info("\n=== Example 7: Strategy Information ===")
    
    for strategy_name in ['MomentumStrategy', 'CustomMomentumStrategy']:
        try:
            info = strategy_registry.get_strategy_info(strategy_name)
            logger.info(f"{strategy_name}:")
            logger.info(f"  Description: {info['description']}")
            logger.info(f"  Parameters: {list(info['parameter_schema'].keys())}")
        except Exception as e:
            logger.warning(f"Could not get info for {strategy_name}: {e}")
    
    # Example 8: Execution history
    logger.info("\n=== Example 8: Execution History ===")
    
    history = strategy_runner.get_execution_history()
    logger.info(f"Total executions: {len(history)}")
    
    for entry in history:
        logger.info(f"  {entry['strategy_name']}: {entry['num_stocks']} stocks, "
                   f"duration: {entry['duration']}")
    
    logger.info("Extensible Strategy Framework demonstration completed!")

if __name__ == "__main__":
    main() 