from typing import Dict, List, Any, Optional
import pandas as pd
from datetime import datetime
import logging
from .strategy_base import StrategyBase, StrategyResult
from .strategy_registry import strategy_registry

class StrategyRunner:
    """Runner for executing trading strategies"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.execution_history: List[Dict[str, Any]] = []
    
    def run_strategy(self, strategy_name: str, 
                    factor_data: pd.DataFrame,
                    price_data: pd.DataFrame,
                    parameters: Dict[str, Any] = None) -> StrategyResult:
        """
        Run a single strategy
        
        Args:
            strategy_name: Name of the strategy to run
            factor_data: Factor data
            price_data: Price data
            parameters: Strategy parameters
            
        Returns:
            StrategyResult: Strategy execution result
        """
        start_time = datetime.now()
        
        try:
            # Get strategy instance
            if strategy_name in strategy_registry:
                strategy = strategy_registry.get_strategy(strategy_name)
            else:
                strategy = strategy_registry.create_strategy(strategy_name, parameters)
            
            # Set parameters if provided
            if parameters:
                strategy.set_parameters(parameters)
            
            # Preprocess data
            processed_factor_data, processed_price_data = strategy.preprocess_data(
                factor_data, price_data
            )
            
            # Generate signals
            result = strategy.generate_signals(processed_factor_data, processed_price_data)
            
            # Calculate performance metrics
            performance_metrics = strategy.calculate_performance_metrics(
                result, processed_price_data
            )
            result.performance_metrics.update(performance_metrics)
            
            # Postprocess result
            result = strategy.postprocess_result(result)
            
            execution_time = datetime.now() - start_time
            
            # Log execution
            self._log_execution(strategy_name, result, execution_time, parameters)
            
            self.logger.info(f"Strategy {strategy_name} executed successfully in {execution_time}")
            
            return result
            
        except Exception as e:
            self.logger.error(f"Error executing strategy {strategy_name}: {e}")
            raise
    
    def run_multiple_strategies(self, strategy_configs: List[Dict[str, Any]],
                              factor_data: pd.DataFrame,
                              price_data: pd.DataFrame) -> Dict[str, StrategyResult]:
        """
        Run multiple strategies
        
        Args:
            strategy_configs: List of strategy configurations
            factor_data: Factor data
            price_data: Price data
            
        Returns:
            Dict: Strategy results
        """
        results = {}
        
        for config in strategy_configs:
            strategy_name = config['name']
            parameters = config.get('parameters', {})
            
            try:
                result = self.run_strategy(strategy_name, factor_data, price_data, parameters)
                results[strategy_name] = result
                
            except Exception as e:
                self.logger.error(f"Failed to run strategy {strategy_name}: {e}")
                results[strategy_name] = None
        
        return results
    
    def run_strategy_ensemble(self, strategy_names: List[str],
                            factor_data: pd.DataFrame,
                            price_data: pd.DataFrame,
                            ensemble_method: str = 'equal_weight',
                            ensemble_parameters: Dict[str, Any] = None) -> StrategyResult:
        """
        Run ensemble of strategies
        
        Args:
            strategy_names: List of strategy names
            factor_data: Factor data
            price_data: Price data
            ensemble_method: Method for combining strategies
            ensemble_parameters: Parameters for ensemble method
            
        Returns:
            StrategyResult: Ensemble result
        """
        # Run individual strategies
        individual_results = {}
        for strategy_name in strategy_names:
            try:
                result = self.run_strategy(strategy_name, factor_data, price_data)
                individual_results[strategy_name] = result
            except Exception as e:
                self.logger.warning(f"Strategy {strategy_name} failed: {e}")
        
        if not individual_results:
            raise ValueError("No strategies executed successfully")
        
        # Combine results based on ensemble method
        if ensemble_method == 'equal_weight':
            return self._combine_equal_weight(individual_results)
        elif ensemble_method == 'performance_weight':
            return self._combine_performance_weight(individual_results, ensemble_parameters)
        elif ensemble_method == 'voting':
            return self._combine_voting(individual_results, ensemble_parameters)
        else:
            raise ValueError(f"Unknown ensemble method: {ensemble_method}")
    
    def _combine_equal_weight(self, individual_results: Dict[str, StrategyResult]) -> StrategyResult:
        """Combine strategies with equal weights"""
        all_stocks = set()
        for result in individual_results.values():
            all_stocks.update(result.selected_stocks)
        
        # Equal weight for each stock
        weight_per_stock = 1.0 / len(all_stocks) if all_stocks else 0
        weights = {stock: weight_per_stock for stock in all_stocks}
        
        return StrategyResult(
            strategy_name="Ensemble_EqualWeight",
            selected_stocks=list(all_stocks),
            weights=weights,
            parameters={'ensemble_method': 'equal_weight'},
            execution_time=datetime.now(),
            performance_metrics={'num_strategies': len(individual_results)},
            metadata={'individual_results': individual_results}
        )
    
    def _combine_performance_weight(self, individual_results: Dict[str, StrategyResult],
                                  parameters: Dict[str, Any]) -> StrategyResult:
        """Combine strategies weighted by performance"""
        # This is a simplified implementation
        # In practice, you might want to use historical performance or other metrics
        
        all_stocks = set()
        stock_scores = {}
        
        for strategy_name, result in individual_results.items():
            # Use strategy performance as weight (simplified)
            strategy_weight = 1.0 / len(individual_results)
            
            for stock in result.selected_stocks:
                all_stocks.add(stock)
                stock_scores[stock] = stock_scores.get(stock, 0) + strategy_weight
        
        # Normalize weights
        total_score = sum(stock_scores.values())
        weights = {stock: score / total_score for stock, score in stock_scores.items()}
        
        return StrategyResult(
            strategy_name="Ensemble_PerformanceWeight",
            selected_stocks=list(all_stocks),
            weights=weights,
            parameters={'ensemble_method': 'performance_weight'},
            execution_time=datetime.now(),
            performance_metrics={'num_strategies': len(individual_results)},
            metadata={'individual_results': individual_results}
        )
    
    def _combine_voting(self, individual_results: Dict[str, StrategyResult],
                       parameters: Dict[str, Any]) -> StrategyResult:
        """Combine strategies using voting mechanism"""
        vote_threshold = parameters.get('vote_threshold', 0.5)
        
        stock_votes = {}
        for result in individual_results.values():
            for stock in result.selected_stocks:
                stock_votes[stock] = stock_votes.get(stock, 0) + 1
        
        # Select stocks that receive enough votes
        num_strategies = len(individual_results)
        min_votes = int(num_strategies * vote_threshold)
        
        selected_stocks = [stock for stock, votes in stock_votes.items() 
                          if votes >= min_votes]
        
        # Equal weight for selected stocks
        weight_per_stock = 1.0 / len(selected_stocks) if selected_stocks else 0
        weights = {stock: weight_per_stock for stock in selected_stocks}
        
        return StrategyResult(
            strategy_name="Ensemble_Voting",
            selected_stocks=selected_stocks,
            weights=weights,
            parameters={'ensemble_method': 'voting', 'vote_threshold': vote_threshold},
            execution_time=datetime.now(),
            performance_metrics={'num_strategies': len(individual_results)},
            metadata={'individual_results': individual_results}
        )
    
    def _log_execution(self, strategy_name: str, result: StrategyResult,
                      execution_time: datetime, parameters: Dict[str, Any]):
        """Log strategy execution"""
        log_entry = {
            'strategy_name': strategy_name,
            'execution_time': datetime.now(),
            'duration': execution_time,
            'num_stocks': len(result.selected_stocks),
            'parameters': parameters,
            'performance_metrics': result.performance_metrics
        }
        
        self.execution_history.append(log_entry)
    
    def get_execution_history(self, strategy_name: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get execution history"""
        if strategy_name:
            return [entry for entry in self.execution_history 
                   if entry['strategy_name'] == strategy_name]
        return self.execution_history
    
    def clear_history(self):
        """Clear execution history"""
        self.execution_history.clear()
        self.logger.info("Execution history cleared") 