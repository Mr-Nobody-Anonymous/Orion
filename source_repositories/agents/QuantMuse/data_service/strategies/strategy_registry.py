from typing import Dict, List, Any, Type, Optional
import logging
from .strategy_base import StrategyBase

class StrategyRegistry:
    """Registry for managing trading strategies"""
    
    def __init__(self):
        self._strategies: Dict[str, Type[StrategyBase]] = {}
        self._instances: Dict[str, StrategyBase] = {}
        self.logger = logging.getLogger(__name__)
    
    def register_strategy(self, strategy_class: Type[StrategyBase], 
                         strategy_name: Optional[str] = None) -> str:
        """
        Register a strategy class
        
        Args:
            strategy_class: Strategy class to register
            strategy_name: Optional custom name for the strategy
            
        Returns:
            str: Registered strategy name
        """
        if not issubclass(strategy_class, StrategyBase):
            raise ValueError(f"Strategy class must inherit from StrategyBase")
        
        name = strategy_name or strategy_class.__name__
        
        if name in self._strategies:
            self.logger.warning(f"Strategy {name} already registered, overwriting")
        
        self._strategies[name] = strategy_class
        self.logger.info(f"Strategy {name} registered successfully")
        
        return name
    
    def register_instance(self, strategy_instance: StrategyBase, 
                         strategy_name: Optional[str] = None) -> str:
        """
        Register a strategy instance
        
        Args:
            strategy_instance: Strategy instance to register
            strategy_name: Optional custom name for the strategy
            
        Returns:
            str: Registered strategy name
        """
        if not isinstance(strategy_instance, StrategyBase):
            raise ValueError(f"Strategy instance must inherit from StrategyBase")
        
        name = strategy_name or strategy_instance.name
        
        if name in self._instances:
            self.logger.warning(f"Strategy instance {name} already registered, overwriting")
        
        self._instances[name] = strategy_instance
        self.logger.info(f"Strategy instance {name} registered successfully")
        
        return name
    
    def create_strategy(self, strategy_name: str, 
                       parameters: Dict[str, Any] = None) -> StrategyBase:
        """
        Create a strategy instance
        
        Args:
            strategy_name: Name of the registered strategy
            parameters: Strategy parameters
            
        Returns:
            StrategyBase: Strategy instance
        """
        if strategy_name not in self._strategies:
            raise ValueError(f"Strategy {strategy_name} not found in registry")
        
        strategy_class = self._strategies[strategy_name]
        strategy_instance = strategy_class()
        
        if parameters:
            strategy_instance.set_parameters(parameters)
        
        return strategy_instance
    
    def get_strategy(self, strategy_name: str) -> StrategyBase:
        """
        Get a registered strategy instance
        
        Args:
            strategy_name: Name of the registered strategy
            
        Returns:
            StrategyBase: Strategy instance
        """
        if strategy_name not in self._instances:
            raise ValueError(f"Strategy instance {strategy_name} not found in registry")
        
        return self._instances[strategy_name]
    
    def list_strategies(self) -> List[str]:
        """List all registered strategy names"""
        return list(self._strategies.keys())
    
    def list_instances(self) -> List[str]:
        """List all registered strategy instance names"""
        return list(self._instances.keys())
    
    def get_strategy_info(self, strategy_name: str) -> Dict[str, Any]:
        """
        Get information about a registered strategy
        
        Args:
            strategy_name: Name of the strategy
            
        Returns:
            Dict: Strategy information
        """
        if strategy_name in self._strategies:
            strategy_class = self._strategies[strategy_name]
            instance = strategy_class()
            return instance.get_parameter_info()
        elif strategy_name in self._instances:
            return self._instances[strategy_name].get_parameter_info()
        else:
            raise ValueError(f"Strategy {strategy_name} not found")
    
    def remove_strategy(self, strategy_name: str):
        """Remove a strategy from registry"""
        if strategy_name in self._strategies:
            del self._strategies[strategy_name]
            self.logger.info(f"Strategy {strategy_name} removed from registry")
        
        if strategy_name in self._instances:
            del self._instances[strategy_name]
            self.logger.info(f"Strategy instance {strategy_name} removed from registry")
    
    def clear(self):
        """Clear all registered strategies"""
        self._strategies.clear()
        self._instances.clear()
        self.logger.info("All strategies cleared from registry")
    
    def __contains__(self, strategy_name: str) -> bool:
        """Check if strategy is registered"""
        return strategy_name in self._strategies or strategy_name in self._instances
    
    def __len__(self) -> int:
        """Number of registered strategies"""
        return len(self._strategies) + len(self._instances)

# Global strategy registry instance
strategy_registry = StrategyRegistry() 