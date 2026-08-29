#!/usr/bin/env python3
"""
WebSocket Client for Real-time Market Data
Supports multiple exchanges and data types
"""

import asyncio
import json
import logging
from typing import Dict, List, Any, Optional, Callable
from datetime import datetime
import websockets
import aiohttp
from dataclasses import dataclass
import time

@dataclass
class WebSocketMessage:
    """WebSocket message structure"""
    exchange: str
    symbol: str
    data_type: str
    data: Dict[str, Any]
    timestamp: datetime
    raw_message: str

class WebSocketClient:
    """WebSocket client for real-time market data"""
    
    def __init__(self, exchange: str = "binance"):
        self.exchange = exchange
        self.logger = logging.getLogger(__name__)
        self.websocket = None
        self.is_connected = False
        self.subscriptions = set()
        self.message_handlers: List[Callable] = []
        self.error_handlers: List[Callable] = []
        
        # Exchange-specific configurations
        self.exchange_configs = {
            "binance": {
                "ws_url": "wss://stream.binance.com:9443/ws/",
                "rest_url": "https://api.binance.com/api/v3/",
                "ping_interval": 30,
                "subscription_format": "{symbol}@ticker"
            },
            "coinbase": {
                "ws_url": "wss://ws-feed.pro.coinbase.com",
                "rest_url": "https://api.pro.coinbase.com/",
                "ping_interval": 30,
                "subscription_format": "{symbol}-USD"
            },
            "kraken": {
                "ws_url": "wss://ws.kraken.com",
                "rest_url": "https://api.kraken.com/0/public/",
                "ping_interval": 30,
                "subscription_format": "{symbol}/USD"
            }
        }
        
        self.config = self.exchange_configs.get(exchange, self.exchange_configs["binance"])
    
    async def connect(self, symbols: List[str] = None):
        """Connect to WebSocket and subscribe to symbols"""
        try:
            if self.exchange == "binance":
                await self._connect_binance(symbols)
            elif self.exchange == "coinbase":
                await self._connect_coinbase(symbols)
            elif self.exchange == "kraken":
                await self._connect_kraken(symbols)
            else:
                raise ValueError(f"Unsupported exchange: {self.exchange}")
                
        except Exception as e:
            self.logger.error(f"Failed to connect to {self.exchange}: {e}")
            raise
    
    async def _connect_binance(self, symbols: List[str] = None):
        """Connect to Binance WebSocket"""
        if symbols is None:
            symbols = ["btcusdt", "ethusdt", "adausdt"]
        
        # Create stream names
        streams = [f"{symbol}@ticker" for symbol in symbols]
        stream_url = f"{self.config['ws_url']}{'/'.join(streams)}"
        
        self.logger.info(f"Connecting to Binance WebSocket: {stream_url}")
        
        try:
            self.websocket = await websockets.connect(stream_url)
            self.is_connected = True
            
            # Start message processing
            asyncio.create_task(self._process_messages())
            
            self.logger.info(f"Successfully connected to Binance WebSocket")
            
        except Exception as e:
            self.logger.error(f"Failed to connect to Binance: {e}")
            raise
    
    async def _connect_coinbase(self, symbols: List[str] = None):
        """Connect to Coinbase WebSocket"""
        if symbols is None:
            symbols = ["BTC-USD", "ETH-USD"]
        
        self.logger.info(f"Connecting to Coinbase WebSocket")
        
        try:
            self.websocket = await websockets.connect(self.config["ws_url"])
            self.is_connected = True
            
            # Subscribe to channels
            subscribe_message = {
                "type": "subscribe",
                "product_ids": symbols,
                "channels": ["ticker", "level2"]
            }
            
            await self.websocket.send(json.dumps(subscribe_message))
            
            # Start message processing
            asyncio.create_task(self._process_messages())
            
            self.logger.info(f"Successfully connected to Coinbase WebSocket")
            
        except Exception as e:
            self.logger.error(f"Failed to connect to Coinbase: {e}")
            raise
    
    async def _connect_kraken(self, symbols: List[str] = None):
        """Connect to Kraken WebSocket"""
        if symbols is None:
            symbols = ["XBT/USD", "ETH/USD"]
        
        self.logger.info(f"Connecting to Kraken WebSocket")
        
        try:
            self.websocket = await websockets.connect(self.config["ws_url"])
            self.is_connected = True
            
            # Subscribe to channels
            subscribe_message = {
                "event": "subscribe",
                "pair": symbols,
                "subscription": {"name": "ticker"}
            }
            
            await self.websocket.send(json.dumps(subscribe_message))
            
            # Start message processing
            asyncio.create_task(self._process_messages())
            
            self.logger.info(f"Successfully connected to Kraken WebSocket")
            
        except Exception as e:
            self.logger.error(f"Failed to connect to Kraken: {e}")
            raise
    
    async def _process_messages(self):
        """Process incoming WebSocket messages"""
        try:
            async for message in self.websocket:
                try:
                    # Parse message
                    parsed_message = await self._parse_message(message)
                    
                    if parsed_message:
                        # Notify handlers
                        for handler in self.message_handlers:
                            try:
                                await handler(parsed_message)
                            except Exception as e:
                                self.logger.error(f"Handler error: {e}")
                    
                except Exception as e:
                    self.logger.error(f"Error processing message: {e}")
                    
        except websockets.exceptions.ConnectionClosed:
            self.logger.warning("WebSocket connection closed")
            self.is_connected = False
        except Exception as e:
            self.logger.error(f"WebSocket error: {e}")
            self.is_connected = False
    
    async def _parse_message(self, message: str) -> Optional[WebSocketMessage]:
        """Parse WebSocket message based on exchange"""
        try:
            data = json.loads(message)
            
            if self.exchange == "binance":
                return self._parse_binance_message(data)
            elif self.exchange == "coinbase":
                return self._parse_coinbase_message(data)
            elif self.exchange == "kraken":
                return self._parse_kraken_message(data)
            else:
                return None
                
        except json.JSONDecodeError:
            self.logger.warning(f"Invalid JSON message: {message}")
            return None
        except Exception as e:
            self.logger.error(f"Error parsing message: {e}")
            return None
    
    def _parse_binance_message(self, data: Dict[str, Any]) -> WebSocketMessage:
        """Parse Binance WebSocket message"""
        symbol = data.get('s', '').lower()
        
        return WebSocketMessage(
            exchange="binance",
            symbol=symbol,
            data_type="ticker",
            data={
                'price': float(data.get('c', 0)),
                'volume': float(data.get('v', 0)),
                'high': float(data.get('h', 0)),
                'low': float(data.get('l', 0)),
                'open': float(data.get('o', 0)),
                'change': float(data.get('P', 0)),
                'change_percent': float(data.get('P', 0))
            },
            timestamp=datetime.fromtimestamp(data.get('E', 0) / 1000),
            raw_message=json.dumps(data)
        )
    
    def _parse_coinbase_message(self, data: Dict[str, Any]) -> WebSocketMessage:
        """Parse Coinbase WebSocket message"""
        if data.get('type') == 'ticker':
            product_id = data.get('product_id', '')
            symbol = product_id.lower().replace('-', '')
            
            return WebSocketMessage(
                exchange="coinbase",
                symbol=symbol,
                data_type="ticker",
                data={
                    'price': float(data.get('price', 0)),
                    'volume': float(data.get('volume', 0)),
                    'high': float(data.get('high_24h', 0)),
                    'low': float(data.get('low_24h', 0)),
                    'open': float(data.get('open_24h', 0)),
                    'change': float(data.get('price', 0)) - float(data.get('open_24h', 0)),
                    'change_percent': 0.0  # Calculate if needed
                },
                timestamp=datetime.fromisoformat(data.get('time', '').replace('Z', '+00:00')),
                raw_message=json.dumps(data)
            )
        return None
    
    def _parse_kraken_message(self, data: List[Any]) -> WebSocketMessage:
        """Parse Kraken WebSocket message"""
        if isinstance(data, list) and len(data) > 1:
            symbol = data[3].lower().replace('/', '')
            ticker_data = data[1]
            
            return WebSocketMessage(
                exchange="kraken",
                symbol=symbol,
                data_type="ticker",
                data={
                    'price': float(ticker_data.get('c', [0])[0]),
                    'volume': float(ticker_data.get('v', [0])[1]),
                    'high': float(ticker_data.get('h', [0])[1]),
                    'low': float(ticker_data.get('l', [0])[1]),
                    'open': float(ticker_data.get('o', 0)),
                    'change': 0.0,  # Calculate if needed
                    'change_percent': 0.0
                },
                timestamp=datetime.now(),
                raw_message=json.dumps(data)
            )
        return None
    
    def add_message_handler(self, handler: Callable):
        """Add message handler"""
        self.message_handlers.append(handler)
    
    def add_error_handler(self, handler: Callable):
        """Add error handler"""
        self.error_handlers.append(handler)
    
    async def subscribe(self, symbol: str, data_type: str = "ticker"):
        """Subscribe to additional symbol"""
        if not self.is_connected:
            raise RuntimeError("WebSocket not connected")
        
        subscription = f"{symbol}@{data_type}"
        self.subscriptions.add(subscription)
        
        # Implementation depends on exchange
        self.logger.info(f"Subscribed to {subscription}")
    
    async def unsubscribe(self, symbol: str, data_type: str = "ticker"):
        """Unsubscribe from symbol"""
        subscription = f"{symbol}@{data_type}"
        self.subscriptions.discard(subscription)
        
        # Implementation depends on exchange
        self.logger.info(f"Unsubscribed from {subscription}")
    
    async def disconnect(self):
        """Disconnect from WebSocket"""
        if self.websocket:
            await self.websocket.close()
            self.is_connected = False
            self.logger.info("Disconnected from WebSocket")
    
    async def ping(self):
        """Send ping to keep connection alive"""
        if self.websocket and self.is_connected:
            try:
                await self.websocket.ping()
            except Exception as e:
                self.logger.error(f"Ping failed: {e}")
                self.is_connected = False 