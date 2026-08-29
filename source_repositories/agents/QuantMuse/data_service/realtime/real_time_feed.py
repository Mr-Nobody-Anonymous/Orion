#!/usr/bin/env python3
"""
Real-time Data Feed
Manages real-time market data streams and processing
"""

import asyncio
import logging
from typing import Dict, List, Any, Optional, Callable
from datetime import datetime, timedelta
import pandas as pd
from collections import defaultdict
from dataclasses import dataclass

from .websocket_client import WebSocketClient, WebSocketMessage

@dataclass
class MarketTick:
    """Market tick data structure"""
    symbol: str
    price: float
    volume: float
    timestamp: datetime
    exchange: str
    bid: Optional[float] = None
    ask: Optional[float] = None
    high: Optional[float] = None
    low: Optional[float] = None

@dataclass
class MarketSnapshot:
    """Market snapshot data structure"""
    symbol: str
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float
    exchange: str

class RealTimeDataFeed:
    """Real-time market data feed manager"""
    
    def __init__(self, exchanges: List[str] = None):
        self.exchanges = exchanges or ["binance"]
        self.logger = logging.getLogger(__name__)
        
        # WebSocket clients
        self.clients: Dict[str, WebSocketClient] = {}
        
        # Data storage
        self.tick_data: Dict[str, List[MarketTick]] = defaultdict(list)
        self.snapshot_data: Dict[str, List[MarketSnapshot]] = defaultdict(list)
        
        # Callbacks
        self.tick_callbacks: List[Callable] = []
        self.snapshot_callbacks: List[Callable] = []
        self.alert_callbacks: List[Callable] = []
        
        # Configuration
        self.max_ticks_per_symbol = 1000
        self.snapshot_interval = 60  # seconds
        
        # Alerts
        self.price_alerts: Dict[str, Dict[str, float]] = defaultdict(dict)
        self.volume_alerts: Dict[str, Dict[str, float]] = defaultdict(dict)
    
    async def start(self, symbols: List[str] = None):
        """Start real-time data feeds"""
        if symbols is None:
            symbols = ["btcusdt", "ethusdt", "adausdt"]
        
        self.logger.info(f"Starting real-time data feeds for {symbols}")
        
        # Start WebSocket clients for each exchange
        for exchange in self.exchanges:
            try:
                client = WebSocketClient(exchange)
                await client.connect(symbols)
                
                # Add message handler
                client.add_message_handler(self._handle_websocket_message)
                
                self.clients[exchange] = client
                self.logger.info(f"Started {exchange} data feed")
                
            except Exception as e:
                self.logger.error(f"Failed to start {exchange} feed: {e}")
        
        # Start data processing tasks
        asyncio.create_task(self._process_snapshots())
        asyncio.create_task(self._check_alerts())
        asyncio.create_task(self._cleanup_old_data())
    
    async def stop(self):
        """Stop all real-time data feeds"""
        self.logger.info("Stopping real-time data feeds")
        
        for client in self.clients.values():
            await client.disconnect()
        
        self.clients.clear()
    
    async def _handle_websocket_message(self, message: WebSocketMessage):
        """Handle incoming WebSocket message"""
        try:
            # Create market tick
            tick = MarketTick(
                symbol=message.symbol,
                price=message.data.get('price', 0),
                volume=message.data.get('volume', 0),
                timestamp=message.timestamp,
                exchange=message.exchange,
                bid=message.data.get('bid'),
                ask=message.data.get('ask'),
                high=message.data.get('high'),
                low=message.data.get('low')
            )
            
            # Store tick data
            self.tick_data[message.symbol].append(tick)
            
            # Limit data size
            if len(self.tick_data[message.symbol]) > self.max_ticks_per_symbol:
                self.tick_data[message.symbol] = self.tick_data[message.symbol][-self.max_ticks_per_symbol:]
            
            # Notify callbacks
            for callback in self.tick_callbacks:
                try:
                    await callback(tick)
                except Exception as e:
                    self.logger.error(f"Tick callback error: {e}")
            
        except Exception as e:
            self.logger.error(f"Error handling WebSocket message: {e}")
    
    async def _process_snapshots(self):
        """Process tick data into snapshots"""
        while True:
            try:
                for symbol, ticks in self.tick_data.items():
                    if len(ticks) > 0:
                        # Get recent ticks
                        recent_ticks = [t for t in ticks if 
                                       t.timestamp > datetime.now() - timedelta(seconds=self.snapshot_interval)]
                        
                        if recent_ticks:
                            # Create snapshot
                            snapshot = MarketSnapshot(
                                symbol=symbol,
                                timestamp=datetime.now(),
                                open=recent_ticks[0].price,
                                high=max(t.price for t in recent_ticks),
                                low=min(t.price for t in recent_ticks),
                                close=recent_ticks[-1].price,
                                volume=sum(t.volume for t in recent_ticks),
                                exchange=recent_ticks[0].exchange
                            )
                            
                            # Store snapshot
                            self.snapshot_data[symbol].append(snapshot)
                            
                            # Notify callbacks
                            for callback in self.snapshot_callbacks:
                                try:
                                    await callback(snapshot)
                                except Exception as e:
                                    self.logger.error(f"Snapshot callback error: {e}")
                
                await asyncio.sleep(self.snapshot_interval)
                
            except Exception as e:
                self.logger.error(f"Error processing snapshots: {e}")
                await asyncio.sleep(5)
    
    async def _check_alerts(self):
        """Check price and volume alerts"""
        while True:
            try:
                for symbol, ticks in self.tick_data.items():
                    if len(ticks) > 0:
                        latest_tick = ticks[-1]
                        
                        # Check price alerts
                        for alert_type, threshold in self.price_alerts[symbol].items():
                            if alert_type == "high" and latest_tick.price > threshold:
                                await self._trigger_alert(symbol, "price_high", latest_tick.price, threshold)
                            elif alert_type == "low" and latest_tick.price < threshold:
                                await self._trigger_alert(symbol, "price_low", latest_tick.price, threshold)
                        
                        # Check volume alerts
                        for alert_type, threshold in self.volume_alerts[symbol].items():
                            if alert_type == "high" and latest_tick.volume > threshold:
                                await self._trigger_alert(symbol, "volume_high", latest_tick.volume, threshold)
                
                await asyncio.sleep(1)  # Check every second
                
            except Exception as e:
                self.logger.error(f"Error checking alerts: {e}")
                await asyncio.sleep(5)
    
    async def _trigger_alert(self, symbol: str, alert_type: str, current_value: float, threshold: float):
        """Trigger an alert"""
        alert_data = {
            "symbol": symbol,
            "alert_type": alert_type,
            "current_value": current_value,
            "threshold": threshold,
            "timestamp": datetime.now()
        }
        
        for callback in self.alert_callbacks:
            try:
                await callback(alert_data)
            except Exception as e:
                self.logger.error(f"Alert callback error: {e}")
    
    async def _cleanup_old_data(self):
        """Clean up old data"""
        while True:
            try:
                cutoff_time = datetime.now() - timedelta(hours=1)
                
                for symbol in list(self.tick_data.keys()):
                    self.tick_data[symbol] = [
                        tick for tick in self.tick_data[symbol]
                        if tick.timestamp > cutoff_time
                    ]
                
                for symbol in list(self.snapshot_data.keys()):
                    self.snapshot_data[symbol] = [
                        snapshot for snapshot in self.snapshot_data[symbol]
                        if snapshot.timestamp > cutoff_time
                    ]
                
                await asyncio.sleep(300)  # Clean up every 5 minutes
                
            except Exception as e:
                self.logger.error(f"Error cleaning up old data: {e}")
                await asyncio.sleep(60)
    
    def add_tick_callback(self, callback: Callable):
        """Add tick data callback"""
        self.tick_callbacks.append(callback)
    
    def add_snapshot_callback(self, callback: Callable):
        """Add snapshot callback"""
        self.snapshot_callbacks.append(callback)
    
    def add_alert_callback(self, callback: Callable):
        """Add alert callback"""
        self.alert_callbacks.append(callback)
    
    def set_price_alert(self, symbol: str, alert_type: str, threshold: float):
        """Set price alert"""
        self.price_alerts[symbol][alert_type] = threshold
        self.logger.info(f"Set {alert_type} price alert for {symbol} at {threshold}")
    
    def set_volume_alert(self, symbol: str, alert_type: str, threshold: float):
        """Set volume alert"""
        self.volume_alerts[symbol][alert_type] = threshold
        self.logger.info(f"Set {alert_type} volume alert for {symbol} at {threshold}")
    
    def get_latest_tick(self, symbol: str) -> Optional[MarketTick]:
        """Get latest tick for symbol"""
        ticks = self.tick_data.get(symbol, [])
        return ticks[-1] if ticks else None
    
    def get_latest_snapshot(self, symbol: str) -> Optional[MarketSnapshot]:
        """Get latest snapshot for symbol"""
        snapshots = self.snapshot_data.get(symbol, [])
        return snapshots[-1] if snapshots else None
    
    def get_tick_history(self, symbol: str, minutes: int = 60) -> List[MarketTick]:
        """Get tick history for symbol"""
        cutoff_time = datetime.now() - timedelta(minutes=minutes)
        ticks = self.tick_data.get(symbol, [])
        return [tick for tick in ticks if tick.timestamp > cutoff_time]
    
    def get_snapshot_history(self, symbol: str, minutes: int = 60) -> List[MarketSnapshot]:
        """Get snapshot history for symbol"""
        cutoff_time = datetime.now() - timedelta(minutes=minutes)
        snapshots = self.snapshot_data.get(symbol, [])
        return [snapshot for snapshot in snapshots if snapshot.timestamp > cutoff_time]
    
    def get_symbols(self) -> List[str]:
        """Get list of active symbols"""
        return list(self.tick_data.keys())
    
    def get_exchanges(self) -> List[str]:
        """Get list of active exchanges"""
        return list(self.clients.keys()) 