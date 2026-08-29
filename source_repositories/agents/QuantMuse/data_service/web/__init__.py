"""
Web Management Interface Module
Provides user-friendly web interface for trading system management
"""

try:
    from .api_server import APIServer
    from .dashboard import WebDashboard
    from .strategy_ui import StrategyUI
except ImportError:
    APIServer = None
    WebDashboard = None
    StrategyUI = None

__all__ = ['APIServer', 'WebDashboard', 'StrategyUI'] 