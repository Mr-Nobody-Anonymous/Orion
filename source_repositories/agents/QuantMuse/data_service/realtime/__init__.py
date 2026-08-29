"""
Real-time Data Module
Provides real-time market data streaming via WebSocket
"""

try:
    from .websocket_client import WebSocketClient
    from .real_time_feed import RealTimeDataFeed
    from .tick_processor import TickProcessor
    from .market_data_stream import MarketDataStream
except ImportError as e:
    WebSocketClient = None
    RealTimeDataFeed = None
    TickProcessor = None
    MarketDataStream = None

__all__ = ['WebSocketClient', 'RealTimeDataFeed', 'TickProcessor', 'MarketDataStream'] 