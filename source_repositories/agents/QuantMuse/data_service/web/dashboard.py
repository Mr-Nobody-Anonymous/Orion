#!/usr/bin/env python3
"""
Web Dashboard Component
Provides web-based dashboard functionality
"""

import logging
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
import json

class WebDashboard:
    """Web dashboard for trading system management"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def generate_dashboard_data(self) -> Dict[str, Any]:
        """Generate dashboard data for web interface"""
        try:
            # System overview
            system_overview = {
                "status": "running",
                "uptime": "2 days, 5 hours, 30 minutes",
                "active_strategies": 3,
                "total_trades": 1250,
                "system_health": "excellent"
            }
            
            # Performance metrics
            performance_metrics = {
                "total_return": 0.25,
                "annualized_return": 0.18,
                "sharpe_ratio": 1.8,
                "max_drawdown": -0.12,
                "win_rate": 0.65,
                "profit_factor": 1.45
            }
            
            # Recent activity
            recent_activity = self._generate_recent_activity()
            
            # Portfolio summary
            portfolio_summary = self._generate_portfolio_summary()
            
            # Risk metrics
            risk_metrics = {
                "var_95": -0.02,
                "cvar_95": -0.03,
                "beta": 0.85,
                "correlation": 0.72,
                "volatility": 0.15
            }
            
            return {
                "system_overview": system_overview,
                "performance_metrics": performance_metrics,
                "recent_activity": recent_activity,
                "portfolio_summary": portfolio_summary,
                "risk_metrics": risk_metrics,
                "last_updated": datetime.now().isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"Failed to generate dashboard data: {e}")
            return {}
    
    def _generate_recent_activity(self) -> List[Dict[str, Any]]:
        """Generate recent activity data"""
        activities = []
        
        # Sample activities
        activity_types = [
            {"type": "trade", "description": "Buy order executed", "symbol": "AAPL"},
            {"type": "strategy", "description": "Strategy rebalanced", "symbol": "Momentum"},
            {"type": "alert", "description": "Risk limit warning", "symbol": "Portfolio"},
            {"type": "system", "description": "System backup completed", "symbol": "System"}
        ]
        
        for i, activity in enumerate(activity_types):
            activities.append({
                "id": f"activity_{i}",
                "type": activity["type"],
                "description": activity["description"],
                "symbol": activity["symbol"],
                "timestamp": (datetime.now() - timedelta(hours=i)).isoformat(),
                "severity": "info"
            })
        
        return activities
    
    def _generate_portfolio_summary(self) -> Dict[str, Any]:
        """Generate portfolio summary data"""
        return {
            "total_value": 125000.0,
            "cash": 25000.0,
            "invested": 100000.0,
            "daily_pnl": 1250.0,
            "total_pnl": 4000.0,
            "positions": [
                {"symbol": "AAPL", "quantity": 100, "value": 15000.0, "weight": 0.12},
                {"symbol": "GOOGL", "quantity": 50, "value": 5000.0, "weight": 0.04},
                {"symbol": "MSFT", "quantity": 75, "value": 20000.0, "weight": 0.16},
                {"symbol": "TSLA", "quantity": 200, "value": 30000.0, "weight": 0.24},
                {"symbol": "AMZN", "quantity": 60, "value": 20000.0, "weight": 0.16}
            ]
        }
    
    def get_chart_data(self, chart_type: str, **kwargs) -> Dict[str, Any]:
        """Get chart data for different chart types"""
        try:
            if chart_type == "equity_curve":
                return self._get_equity_curve_data()
            elif chart_type == "returns_distribution":
                return self._get_returns_distribution_data()
            elif chart_type == "drawdown":
                return self._get_drawdown_data()
            elif chart_type == "portfolio_allocation":
                return self._get_portfolio_allocation_data()
            else:
                return {"error": f"Unknown chart type: {chart_type}"}
                
        except Exception as e:
            self.logger.error(f"Failed to get chart data: {e}")
            return {"error": str(e)}
    
    def _get_equity_curve_data(self) -> Dict[str, Any]:
        """Get equity curve data"""
        dates = []
        values = []
        current_date = datetime.now() - timedelta(days=365)
        
        for i in range(252):
            dates.append(current_date.strftime("%Y-%m-%d"))
            values.append(100000 + i * 100 + (i % 20) * 50)
            current_date += timedelta(days=1)
        
        return {
            "type": "line",
            "data": {
                "labels": dates,
                "datasets": [{
                    "label": "Portfolio Value",
                    "data": values,
                    "borderColor": "#1f77b4",
                    "backgroundColor": "rgba(31, 119, 180, 0.1)"
                }]
            }
        }
    
    def _get_returns_distribution_data(self) -> Dict[str, Any]:
        """Get returns distribution data"""
        import numpy as np
        
        # Generate sample returns
        returns = np.random.normal(0.001, 0.02, 1000)
        
        return {
            "type": "histogram",
            "data": {
                "returns": returns.tolist(),
                "bins": np.histogram(returns, bins=30)[0].tolist(),
                "bin_edges": np.histogram(returns, bins=30)[1].tolist()
            }
        }
    
    def _get_drawdown_data(self) -> Dict[str, Any]:
        """Get drawdown data"""
        dates = []
        drawdowns = []
        current_date = datetime.now() - timedelta(days=365)
        
        for i in range(252):
            dates.append(current_date.strftime("%Y-%m-%d"))
            # Generate realistic drawdown pattern
            if i < 50:
                drawdowns.append(0)
            elif i < 100:
                drawdowns.append(-0.05 - (i - 50) * 0.001)
            else:
                drawdowns.append(-0.12 + (i - 100) * 0.0005)
            current_date += timedelta(days=1)
        
        return {
            "type": "area",
            "data": {
                "labels": dates,
                "datasets": [{
                    "label": "Drawdown",
                    "data": drawdowns,
                    "backgroundColor": "rgba(255, 0, 0, 0.3)",
                    "borderColor": "red"
                }]
            }
        }
    
    def _get_portfolio_allocation_data(self) -> Dict[str, Any]:
        """Get portfolio allocation data"""
        return {
            "type": "pie",
            "data": {
                "labels": ["AAPL", "GOOGL", "MSFT", "TSLA", "AMZN", "Cash"],
                "datasets": [{
                    "data": [12, 4, 16, 24, 16, 20],
                    "backgroundColor": [
                        "#FF6384", "#36A2EB", "#FFCE56", 
                        "#4BC0C0", "#9966FF", "#FF9F40"
                    ]
                }]
            }
        } 