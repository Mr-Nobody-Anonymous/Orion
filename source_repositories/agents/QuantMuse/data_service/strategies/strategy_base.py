from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
import pandas as pd
from datetime import datetime
import logging

@dataclass
class StrategyResult:
    """Strategy execution result"""
    strategy_name: str
    selected_stocks: List[str]
    weights: Dict[str, float]
    parameters: Dict[str, Any]
    execution_time: datetime
    performance_metrics: Dict[str, float]
    metadata: Dict[str, Any]

class StrategyBase(ABC):
    """Base class for all trading strategies"""
    
    def __init__(self, name: str, description: str = ""):
        self.name = name
        self.description = description
        self.logger = logging.getLogger(f"strategy.{name}")
        self.parameters = {}
        self.metadata = {}
    
    @abstractmethod
    def generate_signals(self, factor_data: pd.DataFrame, 
                        price_data: pd.DataFrame,
                        **kwargs) -> StrategyResult:
        """
        Generate trading signals based on strategy logic
        
        Args:
            factor_data: Factor data DataFrame
            price_data: Price data DataFrame
            **kwargs: Additional parameters
            
        Returns:
            StrategyResult: Strategy execution result
        """
        pass
    
    def validate_parameters(self, parameters: Dict[str, Any]) -> bool:
        """Validate strategy parameters"""
        return True
    
    def set_parameters(self, parameters: Dict[str, Any]):
        """Set strategy parameters"""
        if self.validate_parameters(parameters):
            self.parameters.update(parameters)
            self.logger.info(f"Parameters updated: {parameters}")
        else:
            raise ValueError(f"Invalid parameters for strategy {self.name}")
    
    def get_parameter_info(self) -> Dict[str, Any]:
        """Get parameter information for the strategy"""
        return {
            'name': self.name,
            'description': self.description,
            'parameters': self.parameters,
            'parameter_schema': self.get_parameter_schema()
        }
    
    def get_parameter_schema(self) -> Dict[str, Any]:
        """Get parameter schema for validation"""
        return {}
    
    def preprocess_data(self, factor_data: pd.DataFrame, 
                       price_data: pd.DataFrame) -> tuple:
        """Preprocess data for strategy execution"""
        return factor_data, price_data
    
    def postprocess_result(self, result: StrategyResult) -> StrategyResult:
        """Postprocess strategy result"""
        return result
    
    def calculate_performance_metrics(self, result: StrategyResult,
                                    price_data: pd.DataFrame) -> Dict[str, float]:
        """Calculate performance metrics for strategy result"""
        # Default implementation - can be overridden by subclasses
        return {
            'num_stocks': len(result.selected_stocks),
            'total_weight': sum(result.weights.values()),
            'max_weight': max(result.weights.values()) if result.weights else 0,
            'min_weight': min(result.weights.values()) if result.weights else 0
        }
    
    def __str__(self):
        return f"Strategy({self.name})"
    
    def __repr__(self):
        return f"Strategy({self.name}, params={self.parameters})" 