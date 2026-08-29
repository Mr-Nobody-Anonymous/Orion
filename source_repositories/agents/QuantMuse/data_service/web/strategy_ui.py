#!/usr/bin/env python3
"""
Strategy Management UI Component
Provides web interface for strategy management
"""

import logging
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
import json

class StrategyUI:
    """Strategy management UI for web interface"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def get_strategy_list(self) -> List[Dict[str, Any]]:
        """Get list of available strategies"""
        strategies = [
            {
                "id": "momentum_strategy",
                "name": "Momentum Strategy",
                "description": "Price momentum based strategy using moving averages",
                "category": "Technical",
                "status": "active",
                "performance": {
                    "total_return": 0.25,
                    "sharpe_ratio": 1.8,
                    "max_drawdown": -0.12,
                    "win_rate": 0.65
                },
                "parameters": {
                    "lookback_period": 20,
                    "momentum_threshold": 0.05,
                    "position_size": 0.1
                },
                "last_updated": datetime.now().isoformat()
            },
            {
                "id": "value_strategy",
                "name": "Value Strategy",
                "description": "Value investing strategy based on fundamental ratios",
                "category": "Fundamental",
                "status": "active",
                "performance": {
                    "total_return": 0.18,
                    "sharpe_ratio": 1.2,
                    "max_drawdown": -0.08,
                    "win_rate": 0.58
                },
                "parameters": {
                    "pe_ratio_max": 25,
                    "pb_ratio_max": 3,
                    "min_market_cap": 1000000000
                },
                "last_updated": datetime.now().isoformat()
            },
            {
                "id": "mean_reversion",
                "name": "Mean Reversion Strategy",
                "description": "Mean reversion strategy using Bollinger Bands",
                "category": "Technical",
                "status": "inactive",
                "performance": {
                    "total_return": 0.15,
                    "sharpe_ratio": 1.0,
                    "max_drawdown": -0.10,
                    "win_rate": 0.52
                },
                "parameters": {
                    "lookback_period": 20,
                    "std_dev": 2.0,
                    "reversion_threshold": 0.02
                },
                "last_updated": datetime.now().isoformat()
            },
            {
                "id": "multi_factor",
                "name": "Multi-Factor Strategy",
                "description": "Multi-factor strategy combining momentum, value, and quality",
                "category": "Hybrid",
                "status": "active",
                "performance": {
                    "total_return": 0.22,
                    "sharpe_ratio": 1.5,
                    "max_drawdown": -0.09,
                    "win_rate": 0.62
                },
                "parameters": {
                    "momentum_weight": 0.4,
                    "value_weight": 0.3,
                    "quality_weight": 0.3,
                    "max_positions": 20
                },
                "last_updated": datetime.now().isoformat()
            },
            {
                "id": "risk_parity",
                "name": "Risk Parity Strategy",
                "description": "Risk parity strategy with equal risk contribution",
                "category": "Risk Management",
                "status": "active",
                "performance": {
                    "total_return": 0.16,
                    "sharpe_ratio": 1.3,
                    "max_drawdown": -0.06,
                    "win_rate": 0.55
                },
                "parameters": {
                    "target_volatility": 0.10,
                    "rebalance_frequency": "monthly",
                    "max_positions": 30
                },
                "last_updated": datetime.now().isoformat()
            }
        ]
        
        return strategies
    
    def get_strategy_details(self, strategy_id: str) -> Optional[Dict[str, Any]]:
        """Get detailed information about a specific strategy"""
        strategies = self.get_strategy_list()
        
        for strategy in strategies:
            if strategy["id"] == strategy_id:
                # Add additional details
                strategy["trades"] = self._get_strategy_trades(strategy_id)
                strategy["equity_curve"] = self._get_strategy_equity_curve(strategy_id)
                strategy["risk_metrics"] = self._get_strategy_risk_metrics(strategy_id)
                strategy["positions"] = self._get_strategy_positions(strategy_id)
                return strategy
        
        return None
    
    def create_strategy(self, strategy_config: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new strategy"""
        try:
            # Validate strategy configuration
            required_fields = ["name", "description", "category", "parameters"]
            for field in required_fields:
                if field not in strategy_config:
                    raise ValueError(f"Missing required field: {field}")
            
            # Generate strategy ID
            strategy_id = f"{strategy_config['name'].lower().replace(' ', '_')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            
            # Create strategy object
            strategy = {
                "id": strategy_id,
                "name": strategy_config["name"],
                "description": strategy_config["description"],
                "category": strategy_config["category"],
                "status": "inactive",
                "performance": {
                    "total_return": 0.0,
                    "sharpe_ratio": 0.0,
                    "max_drawdown": 0.0,
                    "win_rate": 0.0
                },
                "parameters": strategy_config["parameters"],
                "created_at": datetime.now().isoformat(),
                "last_updated": datetime.now().isoformat()
            }
            
            self.logger.info(f"Created new strategy: {strategy_id}")
            return {"status": "success", "strategy": strategy}
            
        except Exception as e:
            self.logger.error(f"Failed to create strategy: {e}")
            return {"status": "error", "message": str(e)}
    
    def update_strategy(self, strategy_id: str, updates: Dict[str, Any]) -> Dict[str, Any]:
        """Update strategy configuration"""
        try:
            # Get current strategy
            strategy = self.get_strategy_details(strategy_id)
            if not strategy:
                return {"status": "error", "message": "Strategy not found"}
            
            # Update fields
            allowed_updates = ["name", "description", "parameters", "status"]
            for field, value in updates.items():
                if field in allowed_updates:
                    strategy[field] = value
            
            strategy["last_updated"] = datetime.now().isoformat()
            
            self.logger.info(f"Updated strategy: {strategy_id}")
            return {"status": "success", "strategy": strategy}
            
        except Exception as e:
            self.logger.error(f"Failed to update strategy: {e}")
            return {"status": "error", "message": str(e)}
    
    def delete_strategy(self, strategy_id: str) -> Dict[str, Any]:
        """Delete a strategy"""
        try:
            # Check if strategy exists
            strategy = self.get_strategy_details(strategy_id)
            if not strategy:
                return {"status": "error", "message": "Strategy not found"}
            
            # Check if strategy is active
            if strategy["status"] == "active":
                return {"status": "error", "message": "Cannot delete active strategy"}
            
            self.logger.info(f"Deleted strategy: {strategy_id}")
            return {"status": "success", "message": "Strategy deleted successfully"}
            
        except Exception as e:
            self.logger.error(f"Failed to delete strategy: {e}")
            return {"status": "error", "message": str(e)}
    
    def start_strategy(self, strategy_id: str) -> Dict[str, Any]:
        """Start a strategy"""
        try:
            strategy = self.get_strategy_details(strategy_id)
            if not strategy:
                return {"status": "error", "message": "Strategy not found"}
            
            if strategy["status"] == "active":
                return {"status": "error", "message": "Strategy is already active"}
            
            # Update strategy status
            strategy["status"] = "active"
            strategy["last_updated"] = datetime.now().isoformat()
            
            self.logger.info(f"Started strategy: {strategy_id}")
            return {"status": "success", "strategy": strategy}
            
        except Exception as e:
            self.logger.error(f"Failed to start strategy: {e}")
            return {"status": "error", "message": str(e)}
    
    def stop_strategy(self, strategy_id: str) -> Dict[str, Any]:
        """Stop a strategy"""
        try:
            strategy = self.get_strategy_details(strategy_id)
            if not strategy:
                return {"status": "error", "message": "Strategy not found"}
            
            if strategy["status"] != "active":
                return {"status": "error", "message": "Strategy is not active"}
            
            # Update strategy status
            strategy["status"] = "inactive"
            strategy["last_updated"] = datetime.now().isoformat()
            
            self.logger.info(f"Stopped strategy: {strategy_id}")
            return {"status": "success", "strategy": strategy}
            
        except Exception as e:
            self.logger.error(f"Failed to stop strategy: {e}")
            return {"status": "error", "message": str(e)}
    
    def _get_strategy_trades(self, strategy_id: str) -> List[Dict[str, Any]]:
        """Get recent trades for a strategy"""
        trades = []
        
        # Generate sample trades
        symbols = ["AAPL", "GOOGL", "MSFT", "TSLA", "AMZN"]
        for i in range(20):
            trades.append({
                "id": f"trade_{strategy_id}_{i}",
                "timestamp": (datetime.now() - timedelta(hours=i)).isoformat(),
                "symbol": symbols[i % len(symbols)],
                "side": "buy" if i % 2 == 0 else "sell",
                "quantity": 100 + i * 10,
                "price": 150.0 + i * 0.5,
                "status": "filled",
                "pnl": 50.0 + i * 5 if i % 2 == 1 else 0.0
            })
        
        return trades
    
    def _get_strategy_equity_curve(self, strategy_id: str) -> Dict[str, Any]:
        """Get equity curve data for a strategy"""
        dates = []
        values = []
        current_date = datetime.now() - timedelta(days=365)
        
        for i in range(252):
            dates.append(current_date.strftime("%Y-%m-%d"))
            # Generate different patterns based on strategy
            if "momentum" in strategy_id:
                values.append(100000 + i * 120 + (i % 30) * 20)
            elif "value" in strategy_id:
                values.append(100000 + i * 80 + (i % 50) * 10)
            else:
                values.append(100000 + i * 100 + (i % 20) * 15)
            current_date += timedelta(days=1)
        
        return {
            "dates": dates,
            "values": values
        }
    
    def _get_strategy_risk_metrics(self, strategy_id: str) -> Dict[str, Any]:
        """Get risk metrics for a strategy"""
        # Generate different risk profiles based on strategy
        if "momentum" in strategy_id:
            return {
                "volatility": 0.18,
                "var_95": -0.025,
                "cvar_95": -0.035,
                "beta": 1.1,
                "correlation": 0.75
            }
        elif "value" in strategy_id:
            return {
                "volatility": 0.12,
                "var_95": -0.018,
                "cvar_95": -0.025,
                "beta": 0.8,
                "correlation": 0.65
            }
        else:
            return {
                "volatility": 0.15,
                "var_95": -0.020,
                "cvar_95": -0.030,
                "beta": 0.9,
                "correlation": 0.70
            }
    
    def _get_strategy_positions(self, strategy_id: str) -> List[Dict[str, Any]]:
        """Get current positions for a strategy"""
        positions = []
        
        # Generate sample positions based on strategy
        if "momentum" in strategy_id:
            symbols = ["AAPL", "TSLA", "NVDA", "META"]
        elif "value" in strategy_id:
            symbols = ["JNJ", "PG", "KO", "WMT"]
        else:
            symbols = ["AAPL", "GOOGL", "MSFT", "AMZN"]
        
        for i, symbol in enumerate(symbols):
            positions.append({
                "symbol": symbol,
                "quantity": 100 + i * 50,
                "avg_price": 150.0 + i * 10,
                "current_price": 155.0 + i * 12,
                "market_value": (100 + i * 50) * (155.0 + i * 12),
                "unrealized_pnl": (100 + i * 50) * (5.0 + i * 2),
                "weight": 0.2 + i * 0.05
            })
        
        return positions 