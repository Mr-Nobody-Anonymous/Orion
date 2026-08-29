import pandas as pd
import numpy as np
from typing import Dict, List, Any, Optional, Tuple, Callable
import logging
from datetime import datetime, timedelta
from dataclasses import dataclass
from scipy.optimize import minimize, differential_evolution
import itertools

@dataclass
class OptimizationResult:
    """Optimization result data"""
    optimal_weights: Dict[str, float]
    objective_value: float
    constraints_satisfied: bool
    optimization_time: float
    iterations: int
    convergence: bool

class FactorOptimizer:
    """Factor optimization and parameter tuning"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def optimize_factor_weights(self, factor_data: pd.DataFrame,
                              price_data: pd.DataFrame,
                              objective_function: str = 'sharpe_ratio',
                              constraints: Dict[str, Any] = None,
                              method: str = 'scipy') -> OptimizationResult:
        """Optimize factor weights to maximize objective function"""
        
        # Prepare data
        factor_names = factor_data['factor_name'].unique()
        n_factors = len(factor_names)
        
        # Default constraints
        if constraints is None:
            constraints = {
                'min_weight': 0.0,
                'max_weight': 1.0,
                'sum_weights': 1.0
            }
        
        # Define objective function
        if objective_function == 'sharpe_ratio':
            obj_func = lambda weights: -self._calculate_sharpe_ratio(factor_data, price_data, factor_names, weights)
        elif objective_function == 'information_ratio':
            obj_func = lambda weights: -self._calculate_information_ratio(factor_data, price_data, factor_names, weights)
        elif objective_function == 'sortino_ratio':
            obj_func = lambda weights: -self._calculate_sortino_ratio(factor_data, price_data, factor_names, weights)
        else:
            raise ValueError(f"Unknown objective function: {objective_function}")
        
        # Define constraints
        constraint_funcs = self._define_constraints(constraints)
        
        # Initial weights
        initial_weights = np.ones(n_factors) / n_factors
        
        # Run optimization
        start_time = datetime.now()
        
        if method == 'scipy':
            result = self._optimize_scipy(obj_func, initial_weights, constraint_funcs)
        elif method == 'genetic':
            result = self._optimize_genetic(obj_func, n_factors, constraint_funcs)
        else:
            raise ValueError(f"Unknown optimization method: {method}")
        
        optimization_time = (datetime.now() - start_time).total_seconds()
        
        # Create result
        optimal_weights = dict(zip(factor_names, result.x))
        
        return OptimizationResult(
            optimal_weights=optimal_weights,
            objective_value=-result.fun,  # Convert back to positive
            constraints_satisfied=result.success,
            optimization_time=optimization_time,
            iterations=result.nit if hasattr(result, 'nit') else 0,
            convergence=result.success
        )
    
    def _optimize_scipy(self, objective_func: Callable,
                       initial_weights: np.ndarray,
                       constraints: List[Dict]) -> Any:
        """Optimize using scipy.optimize"""
        
        # Bounds for weights
        bounds = [(0.0, 1.0)] * len(initial_weights)
        
        # Run optimization
        result = minimize(
            objective_func,
            initial_weights,
            method='SLSQP',
            bounds=bounds,
            constraints=constraints,
            options={'maxiter': 1000}
        )
        
        return result
    
    def _optimize_genetic(self, objective_func: Callable,
                         n_factors: int,
                         constraints: List[Dict]) -> Any:
        """Optimize using genetic algorithm"""
        
        # Bounds for weights
        bounds = [(0.0, 1.0)] * n_factors
        
        # Run differential evolution
        result = differential_evolution(
            objective_func,
            bounds,
            maxiter=1000,
            popsize=15,
            seed=42
        )
        
        return result
    
    def _define_constraints(self, constraints: Dict[str, Any]) -> List[Dict]:
        """Define optimization constraints"""
        constraint_list = []
        
        # Sum of weights constraint
        if 'sum_weights' in constraints:
            constraint_list.append({
                'type': 'eq',
                'fun': lambda x: np.sum(x) - constraints['sum_weights']
            })
        
        # Minimum weight constraints
        if 'min_weight' in constraints:
            constraint_list.append({
                'type': 'ineq',
                'fun': lambda x: x - constraints['min_weight']
            })
        
        # Maximum weight constraints
        if 'max_weight' in constraints:
            constraint_list.append({
                'type': 'ineq',
                'fun': lambda x: constraints['max_weight'] - x
            })
        
        return constraint_list
    
    def _calculate_sharpe_ratio(self, factor_data: pd.DataFrame,
                              price_data: pd.DataFrame,
                              factor_names: List[str],
                              weights: np.ndarray) -> float:
        """Calculate Sharpe ratio for given factor weights"""
        
        # Calculate composite factor returns
        composite_returns = self._calculate_composite_returns(factor_data, price_data, factor_names, weights)
        
        if len(composite_returns) < 2:
            return 0.0
        
        # Calculate Sharpe ratio
        mean_return = composite_returns.mean()
        std_return = composite_returns.std()
        
        if std_return == 0:
            return 0.0
        
        sharpe_ratio = mean_return / std_return * np.sqrt(252)  # Annualized
        
        return sharpe_ratio
    
    def _calculate_information_ratio(self, factor_data: pd.DataFrame,
                                   price_data: pd.DataFrame,
                                   factor_names: List[str],
                                   weights: np.ndarray) -> float:
        """Calculate Information ratio for given factor weights"""
        
        # Calculate composite factor returns
        composite_returns = self._calculate_composite_returns(factor_data, price_data, factor_names, weights)
        
        if len(composite_returns) < 2:
            return 0.0
        
        # Calculate Information ratio (excess return / tracking error)
        mean_return = composite_returns.mean()
        tracking_error = composite_returns.std()
        
        if tracking_error == 0:
            return 0.0
        
        information_ratio = mean_return / tracking_error * np.sqrt(252)  # Annualized
        
        return information_ratio
    
    def _calculate_sortino_ratio(self, factor_data: pd.DataFrame,
                               price_data: pd.DataFrame,
                               factor_names: List[str],
                               weights: np.ndarray) -> float:
        """Calculate Sortino ratio for given factor weights"""
        
        # Calculate composite factor returns
        composite_returns = self._calculate_composite_returns(factor_data, price_data, factor_names, weights)
        
        if len(composite_returns) < 2:
            return 0.0
        
        # Calculate Sortino ratio (excess return / downside deviation)
        mean_return = composite_returns.mean()
        downside_returns = composite_returns[composite_returns < 0]
        
        if len(downside_returns) == 0:
            return 0.0
        
        downside_deviation = downside_returns.std()
        
        if downside_deviation == 0:
            return 0.0
        
        sortino_ratio = mean_return / downside_deviation * np.sqrt(252)  # Annualized
        
        return sortino_ratio
    
    def _calculate_composite_returns(self, factor_data: pd.DataFrame,
                                   price_data: pd.DataFrame,
                                   factor_names: List[str],
                                   weights: np.ndarray) -> pd.Series:
        """Calculate composite factor returns"""
        
        # Get unique dates
        dates = sorted(factor_data['date'].unique())
        
        composite_returns = []
        
        for i, date in enumerate(dates[:-1]):  # Skip last date (no forward return)
            # Get factor values for current date
            current_factors = factor_data[factor_data['date'] == date]
            
            if current_factors.empty:
                continue
            
            # Calculate composite factor value for each stock
            composite_values = {}
            for symbol in current_factors['symbol'].unique():
                symbol_factors = current_factors[current_factors['symbol'] == symbol]
                
                composite_value = 0.0
                for j, factor_name in enumerate(factor_names):
                    factor_row = symbol_factors[symbol_factors['factor_name'] == factor_name]
                    if not factor_row.empty:
                        composite_value += factor_row['factor_value'].iloc[0] * weights[j]
                
                composite_values[symbol] = composite_value
            
            # Calculate forward returns
            forward_date = dates[i + 1]
            forward_prices = price_data[price_data['date'] == forward_date]
            
            if forward_prices.empty:
                continue
            
            # Calculate weighted return
            total_return = 0.0
            total_weight = 0.0
            
            for symbol, composite_value in composite_values.items():
                symbol_prices = price_data[price_data['symbol'] == symbol]
                symbol_prices = symbol_prices[symbol_prices['date'] <= forward_date]
                
                if len(symbol_prices) >= 2:
                    current_price = symbol_prices['close'].iloc[-2]  # Current date
                    forward_price = symbol_prices['close'].iloc[-1]  # Forward date
                    
                    if current_price > 0:
                        symbol_return = (forward_price / current_price - 1) * composite_value
                        total_return += symbol_return
                        total_weight += abs(composite_value)
            
            if total_weight > 0:
                composite_returns.append(total_return / total_weight)
        
        return pd.Series(composite_returns)
    
    def grid_search_optimization(self, factor_data: pd.DataFrame,
                               price_data: pd.DataFrame,
                               factor_names: List[str],
                               weight_grid: List[float] = None,
                               objective_function: str = 'sharpe_ratio') -> OptimizationResult:
        """Grid search optimization for factor weights"""
        
        if weight_grid is None:
            weight_grid = [0.0, 0.25, 0.5, 0.75, 1.0]
        
        best_result = None
        best_objective = float('-inf')
        
        # Generate all possible weight combinations
        weight_combinations = list(itertools.product(weight_grid, repeat=len(factor_names)))
        
        self.logger.info(f"Testing {len(weight_combinations)} weight combinations")
        
        for weights in weight_combinations:
            # Normalize weights to sum to 1
            weights = np.array(weights)
            if weights.sum() > 0:
                weights = weights / weights.sum()
            else:
                continue
            
            # Calculate objective value
            if objective_function == 'sharpe_ratio':
                objective_value = self._calculate_sharpe_ratio(factor_data, price_data, factor_names, weights)
            elif objective_function == 'information_ratio':
                objective_value = self._calculate_information_ratio(factor_data, price_data, factor_names, weights)
            else:
                objective_value = 0.0
            
            # Update best result
            if objective_value > best_objective:
                best_objective = objective_value
                best_result = OptimizationResult(
                    optimal_weights=dict(zip(factor_names, weights)),
                    objective_value=objective_value,
                    constraints_satisfied=True,
                    optimization_time=0.0,
                    iterations=len(weight_combinations),
                    convergence=True
                )
        
        return best_result
    
    def cross_validation_optimization(self, factor_data: pd.DataFrame,
                                    price_data: pd.DataFrame,
                                    factor_names: List[str],
                                    n_splits: int = 5,
                                    objective_function: str = 'sharpe_ratio') -> OptimizationResult:
        """Cross-validation optimization for factor weights"""
        
        # Split data into time periods
        dates = sorted(factor_data['date'].unique())
        split_size = len(dates) // n_splits
        
        cv_results = []
        
        for i in range(n_splits):
            # Define train and test periods
            start_idx = i * split_size
            end_idx = (i + 1) * split_size
            
            train_dates = dates[start_idx:end_idx]
            test_dates = dates[end_idx:min(end_idx + split_size, len(dates))]
            
            if not test_dates:
                continue
            
            # Split data
            train_data = factor_data[factor_data['date'].isin(train_dates)]
            test_data = factor_data[factor_data['date'].isin(test_dates)]
            
            train_prices = price_data[price_data['date'].isin(train_dates)]
            test_prices = price_data[price_data['date'].isin(test_dates)]
            
            # Optimize on training data
            try:
                train_result = self.optimize_factor_weights(
                    train_data, train_prices, objective_function
                )
                
                # Evaluate on test data
                test_objective = self._evaluate_weights(
                    test_data, test_prices, factor_names, 
                    list(train_result.optimal_weights.values()), 
                    objective_function
                )
                
                cv_results.append({
                    'train_result': train_result,
                    'test_objective': test_objective
                })
                
            except Exception as e:
                self.logger.warning(f"CV iteration {i} failed: {e}")
                continue
        
        if not cv_results:
            raise ValueError("No successful cross-validation iterations")
        
        # Select best result based on test performance
        best_cv = max(cv_results, key=lambda x: x['test_objective'])
        
        return best_cv['train_result']
    
    def _evaluate_weights(self, factor_data: pd.DataFrame,
                         price_data: pd.DataFrame,
                         factor_names: List[str],
                         weights: List[float],
                         objective_function: str) -> float:
        """Evaluate weights on given data"""
        
        weights = np.array(weights)
        
        if objective_function == 'sharpe_ratio':
            return self._calculate_sharpe_ratio(factor_data, price_data, factor_names, weights)
        elif objective_function == 'information_ratio':
            return self._calculate_information_ratio(factor_data, price_data, factor_names, weights)
        elif objective_function == 'sortino_ratio':
            return self._calculate_sortino_ratio(factor_data, price_data, factor_names, weights)
        else:
            return 0.0
    
    def generate_optimization_report(self, result: OptimizationResult) -> str:
        """Generate optimization report"""
        
        report = []
        report.append("=" * 50)
        report.append("FACTOR OPTIMIZATION REPORT")
        report.append("=" * 50)
        report.append(f"Optimization Time: {result.optimization_time:.2f} seconds")
        report.append(f"Iterations: {result.iterations}")
        report.append(f"Convergence: {result.convergence}")
        report.append(f"Constraints Satisfied: {result.constraints_satisfied}")
        report.append("")
        
        report.append("OPTIMAL WEIGHTS:")
        for factor_name, weight in result.optimal_weights.items():
            report.append(f"  {factor_name}: {weight:.4f}")
        report.append("")
        
        report.append(f"OBJECTIVE VALUE: {result.objective_value:.4f}")
        
        return "\n".join(report) 