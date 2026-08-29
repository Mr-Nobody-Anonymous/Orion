from typing import Dict, List, Any, Optional, Callable
import pandas as pd
import numpy as np
from datetime import datetime
import logging
from scipy.optimize import minimize, differential_evolution
from .strategy_base import StrategyBase, StrategyResult
from .strategy_runner import StrategyRunner

class StrategyOptimizer:
    """Optimizer for strategy parameters"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.strategy_runner = StrategyRunner()
        self.optimization_history: List[Dict[str, Any]] = []
    
    def optimize_strategy(self, strategy_name: str,
                         factor_data: pd.DataFrame,
                         price_data: pd.DataFrame,
                         parameter_ranges: Dict[str, tuple],
                         objective_function: str = 'sharpe_ratio',
                         optimization_method: str = 'scipy',
                         **kwargs) -> Dict[str, Any]:
        """
        Optimize strategy parameters
        
        Args:
            strategy_name: Name of the strategy to optimize
            factor_data: Factor data
            price_data: Price data
            parameter_ranges: Parameter ranges for optimization
            objective_function: Objective function to optimize
            optimization_method: Optimization method to use
            **kwargs: Additional optimization parameters
            
        Returns:
            Dict: Optimization result
        """
        start_time = datetime.now()
        
        # Define objective function
        if objective_function == 'sharpe_ratio':
            obj_func = lambda params: -self._calculate_sharpe_ratio(
                strategy_name, factor_data, price_data, params
            )
        elif objective_function == 'total_return':
            obj_func = lambda params: -self._calculate_total_return(
                strategy_name, factor_data, price_data, params
            )
        elif objective_function == 'information_ratio':
            obj_func = lambda params: -self._calculate_information_ratio(
                strategy_name, factor_data, price_data, params
            )
        else:
            raise ValueError(f"Unknown objective function: {objective_function}")
        
        # Run optimization
        if optimization_method == 'scipy':
            result = self._optimize_scipy(obj_func, parameter_ranges, **kwargs)
        elif optimization_method == 'genetic':
            result = self._optimize_genetic(obj_func, parameter_ranges, **kwargs)
        else:
            raise ValueError(f"Unknown optimization method: {optimization_method}")
        
        # Create parameter dict from optimized values
        param_names = list(parameter_ranges.keys())
        optimized_params = dict(zip(param_names, result.x))
        
        # Run strategy with optimized parameters
        optimized_result = self.strategy_runner.run_strategy(
            strategy_name, factor_data, price_data, optimized_params
        )
        
        optimization_time = datetime.now() - start_time
        
        # Create optimization result
        opt_result = {
            'strategy_name': strategy_name,
            'optimization_method': optimization_method,
            'objective_function': objective_function,
            'optimized_parameters': optimized_params,
            'objective_value': -result.fun,  # Convert back to positive
            'optimization_success': result.success,
            'optimization_time': optimization_time,
            'iterations': result.nit if hasattr(result, 'nit') else 0,
            'strategy_result': optimized_result
        }
        
        # Log optimization
        self._log_optimization(opt_result)
        
        return opt_result
    
    def _optimize_scipy(self, objective_func: Callable,
                       parameter_ranges: Dict[str, tuple],
                       **kwargs) -> Any:
        """Optimize using scipy.optimize"""
        
        # Convert parameter ranges to bounds
        bounds = list(parameter_ranges.values())
        
        # Initial guess (middle of each range)
        initial_guess = [(low + high) / 2 for low, high in bounds]
        
        # Run optimization
        result = minimize(
            objective_func,
            initial_guess,
            method='L-BFGS-B',
            bounds=bounds,
            options={'maxiter': kwargs.get('maxiter', 1000)}
        )
        
        return result
    
    def _optimize_genetic(self, objective_func: Callable,
                         parameter_ranges: Dict[str, tuple],
                         **kwargs) -> Any:
        """Optimize using genetic algorithm"""
        
        # Convert parameter ranges to bounds
        bounds = list(parameter_ranges.values())
        
        # Run differential evolution
        result = differential_evolution(
            objective_func,
            bounds,
            maxiter=kwargs.get('maxiter', 1000),
            popsize=kwargs.get('popsize', 15),
            seed=kwargs.get('seed', 42)
        )
        
        return result
    
    def _calculate_sharpe_ratio(self, strategy_name: str,
                              factor_data: pd.DataFrame,
                              price_data: pd.DataFrame,
                              parameters: List[float]) -> float:
        """Calculate Sharpe ratio for strategy with given parameters"""
        try:
            # Convert parameters back to dict
            param_names = list(self._get_parameter_ranges().keys())
            param_dict = dict(zip(param_names, parameters))
            
            # Run strategy
            result = self.strategy_runner.run_strategy(
                strategy_name, factor_data, price_data, param_dict
            )
            
            # Extract Sharpe ratio from performance metrics
            return result.performance_metrics.get('sharpe_ratio', 0.0)
            
        except Exception as e:
            self.logger.warning(f"Error calculating Sharpe ratio: {e}")
            return 0.0
    
    def _calculate_total_return(self, strategy_name: str,
                              factor_data: pd.DataFrame,
                              price_data: pd.DataFrame,
                              parameters: List[float]) -> float:
        """Calculate total return for strategy with given parameters"""
        try:
            # Convert parameters back to dict
            param_names = list(self._get_parameter_ranges().keys())
            param_dict = dict(zip(param_names, parameters))
            
            # Run strategy
            result = self.strategy_runner.run_strategy(
                strategy_name, factor_data, price_data, param_dict
            )
            
            # Extract total return from performance metrics
            return result.performance_metrics.get('total_return', 0.0)
            
        except Exception as e:
            self.logger.warning(f"Error calculating total return: {e}")
            return 0.0
    
    def _calculate_information_ratio(self, strategy_name: str,
                                   factor_data: pd.DataFrame,
                                   price_data: pd.DataFrame,
                                   parameters: List[float]) -> float:
        """Calculate information ratio for strategy with given parameters"""
        try:
            # Convert parameters back to dict
            param_names = list(self._get_parameter_ranges().keys())
            param_dict = dict(zip(param_names, parameters))
            
            # Run strategy
            result = self.strategy_runner.run_strategy(
                strategy_name, factor_data, price_data, param_dict
            )
            
            # Extract information ratio from performance metrics
            return result.performance_metrics.get('information_ratio', 0.0)
            
        except Exception as e:
            self.logger.warning(f"Error calculating information ratio: {e}")
            return 0.0
    
    def _get_parameter_ranges(self) -> Dict[str, tuple]:
        """Get parameter ranges - to be overridden by subclasses"""
        return {}
    
    def grid_search_optimization(self, strategy_name: str,
                               factor_data: pd.DataFrame,
                               price_data: pd.DataFrame,
                               parameter_grid: Dict[str, List[Any]],
                               objective_function: str = 'sharpe_ratio') -> Dict[str, Any]:
        """
        Grid search optimization
        
        Args:
            strategy_name: Name of the strategy
            factor_data: Factor data
            price_data: Price data
            parameter_grid: Grid of parameter values to test
            objective_function: Objective function
            
        Returns:
            Dict: Best result from grid search
        """
        best_result = None
        best_objective = float('-inf')
        
        # Generate all parameter combinations
        param_names = list(parameter_grid.keys())
        param_values = list(parameter_grid.values())
        
        total_combinations = 1
        for values in param_values:
            total_combinations *= len(values)
        
        self.logger.info(f"Testing {total_combinations} parameter combinations")
        
        # Test each combination
        for i, combination in enumerate(self._generate_combinations(param_values)):
            parameters = dict(zip(param_names, combination))
            
            try:
                # Run strategy
                result = self.strategy_runner.run_strategy(
                    strategy_name, factor_data, price_data, parameters
                )
                
                # Calculate objective value
                if objective_function == 'sharpe_ratio':
                    objective_value = result.performance_metrics.get('sharpe_ratio', 0.0)
                elif objective_function == 'total_return':
                    objective_value = result.performance_metrics.get('total_return', 0.0)
                else:
                    objective_value = 0.0
                
                # Update best result
                if objective_value > best_objective:
                    best_objective = objective_value
                    best_result = {
                        'strategy_name': strategy_name,
                        'optimization_method': 'grid_search',
                        'objective_function': objective_function,
                        'optimized_parameters': parameters,
                        'objective_value': objective_value,
                        'optimization_success': True,
                        'iterations': i + 1,
                        'strategy_result': result
                    }
                
            except Exception as e:
                self.logger.warning(f"Grid search iteration {i} failed: {e}")
                continue
        
        if best_result:
            self._log_optimization(best_result)
        
        return best_result
    
    def _generate_combinations(self, param_values: List[List[Any]]) -> List[tuple]:
        """Generate all combinations of parameter values"""
        import itertools
        return list(itertools.product(*param_values))
    
    def _log_optimization(self, optimization_result: Dict[str, Any]):
        """Log optimization result"""
        self.optimization_history.append(optimization_result)
    
    def get_optimization_history(self, strategy_name: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get optimization history"""
        if strategy_name:
            return [entry for entry in self.optimization_history 
                   if entry['strategy_name'] == strategy_name]
        return self.optimization_history
    
    def clear_optimization_history(self):
        """Clear optimization history"""
        self.optimization_history.clear()
        self.logger.info("Optimization history cleared") 