from typing import Dict, List, Any
import pandas as pd
from datetime import datetime
from .strategy_base import StrategyBase, StrategyResult
from ..factors import FactorScreener, StockSelector

class MomentumStrategy(StrategyBase):
    """Momentum strategy implementation"""
    
    def __init__(self):
        super().__init__(
            name="MomentumStrategy",
            description="Select stocks with highest momentum"
        )
        self.factor_screener = FactorScreener()
        self.stock_selector = StockSelector()
    
    def get_parameter_schema(self) -> Dict[str, Any]:
        return {
            'lookback_period': {'type': 'int', 'default': 60, 'min': 20, 'max': 252},
            'top_n': {'type': 'int', 'default': 20, 'min': 5, 'max': 100},
            'min_momentum': {'type': 'float', 'default': 5.0, 'min': 0.0, 'max': 50.0},
            'rebalance_frequency': {'type': 'str', 'default': 'monthly', 
                                  'options': ['daily', 'weekly', 'monthly', 'quarterly']}
        }
    
    def validate_parameters(self, parameters: Dict[str, Any]) -> bool:
        schema = self.get_parameter_schema()
        for param_name, param_info in schema.items():
            if param_name in parameters:
                value = parameters[param_name]
                if param_info['type'] == 'int':
                    if not isinstance(value, int) or value < param_info['min'] or value > param_info['max']:
                        return False
                elif param_info['type'] == 'float':
                    if not isinstance(value, (int, float)) or value < param_info['min'] or value > param_info['max']:
                        return False
                elif param_info['type'] == 'str':
                    if value not in param_info['options']:
                        return False
        return True
    
    def generate_signals(self, factor_data: pd.DataFrame, 
                        price_data: pd.DataFrame,
                        **kwargs) -> StrategyResult:
        
        # Get parameters
        lookback_period = self.parameters.get('lookback_period', 60)
        top_n = self.parameters.get('top_n', 20)
        min_momentum = self.parameters.get('min_momentum', 5.0)
        
        # Create momentum screener
        momentum_screener = self.factor_screener.create_momentum_screener(
            min_momentum=min_momentum
        )
        
        # Screen stocks
        screening_results = momentum_screener.screen_stocks(factor_data)
        
        # Select top N stocks
        selection_result = self.stock_selector.select_stocks(
            factor_data, price_data,
            selection_method='top_n',
            n=top_n,
            factor_name=f'momentum_{lookback_period}d'
        )
        
        # Calculate performance metrics
        performance_metrics = self.calculate_performance_metrics(selection_result, price_data)
        
        return StrategyResult(
            strategy_name=self.name,
            selected_stocks=selection_result.selected_stocks,
            weights=selection_result.weights,
            parameters=self.parameters,
            execution_time=datetime.now(),
            performance_metrics=performance_metrics,
            metadata={'screening_results': screening_results}
        )

class ValueStrategy(StrategyBase):
    """Value strategy implementation"""
    
    def __init__(self):
        super().__init__(
            name="ValueStrategy",
            description="Select stocks with low valuation metrics"
        )
        self.factor_screener = FactorScreener()
        self.stock_selector = StockSelector()
    
    def get_parameter_schema(self) -> Dict[str, Any]:
        return {
            'max_pe': {'type': 'float', 'default': 15.0, 'min': 5.0, 'max': 50.0},
            'max_pb': {'type': 'float', 'default': 2.0, 'min': 0.5, 'max': 10.0},
            'min_dividend_yield': {'type': 'float', 'default': 2.0, 'min': 0.0, 'max': 10.0},
            'top_n': {'type': 'int', 'default': 30, 'min': 5, 'max': 100},
            'rebalance_frequency': {'type': 'str', 'default': 'quarterly',
                                  'options': ['monthly', 'quarterly', 'semi_annually']}
        }
    
    def generate_signals(self, factor_data: pd.DataFrame, 
                        price_data: pd.DataFrame,
                        **kwargs) -> StrategyResult:
        
        # Get parameters
        max_pe = self.parameters.get('max_pe', 15.0)
        max_pb = self.parameters.get('max_pb', 2.0)
        min_dividend_yield = self.parameters.get('min_dividend_yield', 2.0)
        top_n = self.parameters.get('top_n', 30)
        
        # Create value screener
        value_screener = self.factor_screener.create_value_screener(
            max_pe=max_pe,
            max_pb=max_pb,
            min_dividend_yield=min_dividend_yield
        )
        
        # Add quality filter
        value_screener.add_criteria({
            'factor_name': 'roe',
            'min_value': 10.0,
            'weight': 0.5
        })
        
        # Screen stocks
        screening_results = value_screener.screen_stocks(factor_data)
        
        # Select stocks with factor-weighted approach
        selection_result = self.stock_selector.select_stocks(
            factor_data, price_data,
            selection_method='factor_weighted',
            factor_name='pe_ratio'
        )
        
        # Calculate performance metrics
        performance_metrics = self.calculate_performance_metrics(selection_result, price_data)
        
        return StrategyResult(
            strategy_name=self.name,
            selected_stocks=selection_result.selected_stocks,
            weights=selection_result.weights,
            parameters=self.parameters,
            execution_time=datetime.now(),
            performance_metrics=performance_metrics,
            metadata={'screening_results': screening_results}
        )

class QualityGrowthStrategy(StrategyBase):
    """Quality growth strategy implementation"""
    
    def __init__(self):
        super().__init__(
            name="QualityGrowthStrategy",
            description="Select high-quality growth stocks"
        )
        self.factor_screener = FactorScreener()
        self.stock_selector = StockSelector()
    
    def get_parameter_schema(self) -> Dict[str, Any]:
        return {
            'min_roe': {'type': 'float', 'default': 15.0, 'min': 5.0, 'max': 50.0},
            'max_debt_equity': {'type': 'float', 'default': 0.5, 'min': 0.0, 'max': 2.0},
            'min_current_ratio': {'type': 'float', 'default': 1.5, 'min': 0.5, 'max': 5.0},
            'min_growth': {'type': 'float', 'default': 10.0, 'min': 0.0, 'max': 50.0},
            'top_n': {'type': 'int', 'default': 25, 'min': 5, 'max': 100}
        }
    
    def generate_signals(self, factor_data: pd.DataFrame, 
                        price_data: pd.DataFrame,
                        **kwargs) -> StrategyResult:
        
        # Get parameters
        min_roe = self.parameters.get('min_roe', 15.0)
        max_debt_equity = self.parameters.get('max_debt_equity', 0.5)
        min_current_ratio = self.parameters.get('min_current_ratio', 1.5)
        min_growth = self.parameters.get('min_growth', 10.0)
        top_n = self.parameters.get('top_n', 25)
        
        # Create quality screener
        quality_screener = self.factor_screener.create_quality_screener(
            min_roe=min_roe,
            max_debt_equity=max_debt_equity,
            min_current_ratio=min_current_ratio
        )
        
        # Add growth criteria
        quality_screener.add_criteria({
            'factor_name': 'momentum_60d',
            'min_value': min_growth,
            'weight': 0.3
        })
        
        # Screen stocks
        screening_results = quality_screener.screen_stocks(factor_data)
        
        # Select stocks
        selection_result = self.stock_selector.select_stocks(
            factor_data, price_data,
            selection_method='factor_weighted',
            factor_name='roe'
        )
        
        # Calculate performance metrics
        performance_metrics = self.calculate_performance_metrics(selection_result, price_data)
        
        return StrategyResult(
            strategy_name=self.name,
            selected_stocks=selection_result.selected_stocks,
            weights=selection_result.weights,
            parameters=self.parameters,
            execution_time=datetime.now(),
            performance_metrics=performance_metrics,
            metadata={'screening_results': screening_results}
        )

class MultiFactorStrategy(StrategyBase):
    """Multi-factor strategy implementation"""
    
    def __init__(self):
        super().__init__(
            name="MultiFactorStrategy",
            description="Combine multiple factors with optimized weights"
        )
        self.factor_screener = FactorScreener()
        self.stock_selector = StockSelector()
    
    def get_parameter_schema(self) -> Dict[str, Any]:
        return {
            'momentum_weight': {'type': 'float', 'default': 0.3, 'min': 0.0, 'max': 1.0},
            'value_weight': {'type': 'float', 'default': 0.2, 'min': 0.0, 'max': 1.0},
            'quality_weight': {'type': 'float', 'default': 0.2, 'min': 0.0, 'max': 1.0},
            'volatility_weight': {'type': 'float', 'default': 0.15, 'min': 0.0, 'max': 1.0},
            'size_weight': {'type': 'float', 'default': 0.15, 'min': 0.0, 'max': 1.0},
            'max_volatility': {'type': 'float', 'default': 30.0, 'min': 10.0, 'max': 50.0},
            'min_market_cap': {'type': 'float', 'default': 1000000000, 'min': 100000000, 'max': 10000000000}
        }
    
    def generate_signals(self, factor_data: pd.DataFrame, 
                        price_data: pd.DataFrame,
                        **kwargs) -> StrategyResult:
        
        # Get parameters
        factor_weights = {
            'momentum_60d': self.parameters.get('momentum_weight', 0.3),
            'pe_ratio': self.parameters.get('value_weight', 0.2),
            'roe': self.parameters.get('quality_weight', 0.2),
            'price_volatility': self.parameters.get('volatility_weight', 0.15),
            'market_cap': self.parameters.get('size_weight', 0.15)
        }
        
        max_volatility = self.parameters.get('max_volatility', 30.0)
        min_market_cap = self.parameters.get('min_market_cap', 1000000000)
        
        # Create multi-factor screener
        multi_screener = self.factor_screener.create_multi_factor_screener(factor_weights)
        
        # Add filters
        multi_screener.add_volatility_filter(max_volatility=max_volatility)
        multi_screener.add_market_cap_filter(min_market_cap=min_market_cap)
        
        # Screen stocks
        screening_results = multi_screener.screen_stocks(factor_data)
        
        # Select stocks with risk parity
        selection_result = self.stock_selector.select_stocks(
            factor_data, price_data,
            selection_method='risk_parity'
        )
        
        # Calculate performance metrics
        performance_metrics = self.calculate_performance_metrics(selection_result, price_data)
        
        return StrategyResult(
            strategy_name=self.name,
            selected_stocks=selection_result.selected_stocks,
            weights=selection_result.weights,
            parameters=self.parameters,
            execution_time=datetime.now(),
            performance_metrics=performance_metrics,
            metadata={'screening_results': screening_results, 'factor_weights': factor_weights}
        )

class MeanReversionStrategy(StrategyBase):
    """Mean reversion strategy implementation"""
    
    def __init__(self):
        super().__init__(
            name="MeanReversionStrategy",
            description="Buy oversold stocks based on technical indicators"
        )
        self.factor_screener = FactorScreener()
        self.stock_selector = StockSelector()
    
    def get_parameter_schema(self) -> Dict[str, Any]:
        return {
            'rsi_oversold': {'type': 'float', 'default': 30.0, 'min': 20.0, 'max': 40.0},
            'rsi_overbought': {'type': 'float', 'default': 70.0, 'min': 60.0, 'max': 80.0},
            'max_volatility': {'type': 'float', 'default': 40.0, 'min': 20.0, 'max': 60.0},
            'momentum_range_min': {'type': 'float', 'default': -20.0, 'min': -50.0, 'max': 0.0},
            'momentum_range_max': {'type': 'float', 'default': 0.0, 'min': -20.0, 'max': 20.0}
        }
    
    def generate_signals(self, factor_data: pd.DataFrame, 
                        price_data: pd.DataFrame,
                        **kwargs) -> StrategyResult:
        
        # Get parameters
        rsi_oversold = self.parameters.get('rsi_oversold', 30.0)
        rsi_overbought = self.parameters.get('rsi_overbought', 70.0)
        max_volatility = self.parameters.get('max_volatility', 40.0)
        momentum_min = self.parameters.get('momentum_range_min', -20.0)
        momentum_max = self.parameters.get('momentum_range_max', 0.0)
        
        # Create custom screener
        mean_reversion_screener = self.factor_screener()
        
        # Add RSI criteria (buy oversold)
        mean_reversion_screener.add_criteria({
            'factor_name': 'rsi',
            'max_value': rsi_oversold,
            'weight': 1.0
        })
        
        # Add momentum criteria
        mean_reversion_screener.add_criteria({
            'factor_name': 'momentum_20d',
            'min_value': momentum_min,
            'max_value': momentum_max,
            'weight': 0.5
        })
        
        # Add volatility filter
        mean_reversion_screener.add_volatility_filter(max_volatility=max_volatility)
        
        # Screen stocks
        screening_results = mean_reversion_screener.screen_stocks(factor_data)
        
        # Select stocks with equal weights
        selection_result = self.stock_selector.select_stocks(
            factor_data, price_data,
            selection_method='equal_weight'
        )
        
        # Calculate performance metrics
        performance_metrics = self.calculate_performance_metrics(selection_result, price_data)
        
        return StrategyResult(
            strategy_name=self.name,
            selected_stocks=selection_result.selected_stocks,
            weights=selection_result.weights,
            parameters=self.parameters,
            execution_time=datetime.now(),
            performance_metrics=performance_metrics,
            metadata={'screening_results': screening_results}
        )

# Register built-in strategies
def register_builtin_strategies():
    """Register all built-in strategies"""
    from .strategy_registry import strategy_registry
    
    strategies = [
        MomentumStrategy,
        ValueStrategy,
        QualityGrowthStrategy,
        MultiFactorStrategy,
        MeanReversionStrategy
    ]
    
    for strategy_class in strategies:
        strategy_registry.register_strategy(strategy_class)
    
    return len(strategies) 