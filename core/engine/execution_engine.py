"""
Orion Execution Engine
Handles all order routing, execution, and fill management
"""

import asyncio
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Callable
try:
    from loguru import logger
except ImportError:
    import logging
    logger = logging.getLogger(__name__)
import numpy as np


class OrderType(Enum):
    MARKET = "MARKET"
    LIMIT = "LIMIT"
    STOP = "STOP"
    STOP_LIMIT = "STOP_LIMIT"
    TRAILING_STOP = "TRAILING_STOP"
    TWAP = "TWAP"
    VWAP = "VWAP"
    ICEBERG = "ICEBERG"
    MOC = "MOC"  # Market on Close
    MOO = "MOO"  # Market on Open


class OrderSide(Enum):
    BUY = "BUY"
    SELL = "SELL"
    BUY_TO_COVER = "BUY_TO_COVER"
    SELL_SHORT = "SELL_SHORT"


class OrderStatus(Enum):
    PENDING = "PENDING"
    SUBMITTED = "SUBMITTED"
    PARTIAL = "PARTIAL"
    FILLED = "FILLED"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"


class AssetClass(Enum):
    EQUITY = "EQUITY"
    CRYPTO = "CRYPTO"
    FOREX = "FOREX"
    FUTURES = "FUTURES"
    OPTIONS = "OPTIONS"
    FIXED_INCOME = "FIXED_INCOME"
    COMMODITY = "COMMODITY"


@dataclass
class Order:
    symbol: str
    side: OrderSide
    quantity: float
    order_type: OrderType
    asset_class: AssetClass
    strategy_id: str
    
    # Optional fields
    limit_price: Optional[float] = None
    stop_price: Optional[float] = None
    trail_percent: Optional[float] = None
    time_in_force: str = "DAY"
    
    # Auto-generated
    order_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: float = field(default_factory=time.time)
    status: OrderStatus = OrderStatus.PENDING
    filled_quantity: float = 0.0
    filled_price: float = 0.0
    commission: float = 0.0
    slippage: float = 0.0
    
    # Risk checks
    risk_approved: bool = False
    risk_score: float = 0.0


@dataclass 
class Fill:
    order_id: str
    symbol: str
    side: OrderSide
    quantity: float
    price: float
    timestamp: float
    commission: float
    exchange: str


class ExecutionEngine:
    """
    Main execution engine that routes orders to appropriate brokers
    and handles execution algorithms
    """
    
    def __init__(self, config: dict, risk_engine=None):
        self.config = config
        self.risk_engine = risk_engine
        self.brokers = {}
        self.active_orders: Dict[str, Order] = {}
        self.order_history: List[Order] = []
        self.fills: List[Fill] = []
        self.callbacks: Dict[str, List[Callable]] = {
            'on_fill': [],
            'on_reject': [],
            'on_cancel': []
        }
        self._running = False
        logger.info("Execution Engine initialized")
    
    def register_broker(self, name: str, broker_instance):
        """Register a broker connection"""
        self.brokers[name] = broker_instance
        logger.info(f"Broker registered: {name}")
    
    def add_callback(self, event: str, callback: Callable):
        """Add event callback"""
        if event in self.callbacks:
            self.callbacks[event].append(callback)
    
    async def submit_order(self, order: Order) -> Optional[str]:
        """
        Submit an order through the full pipeline:
        1. Pre-trade risk checks
        2. Smart order routing
        3. Execution algorithm selection
        4. Order submission
        5. Fill handling
        """
        logger.info(f"Order received: {order.symbol} {order.side.value} {order.quantity}")
        
        # Step 1: Risk checks
        if self.risk_engine:
            risk_check = await self.risk_engine.pre_trade_check(order)
            if not risk_check['approved']:
                logger.warning(f"Order rejected by risk engine: {risk_check['reason']}")
                order.status = OrderStatus.REJECTED
                for cb in self.callbacks['on_reject']:
                    await cb(order, risk_check['reason'])
                return None
            order.risk_approved = True
            order.risk_score = risk_check['score']
        
        # Step 2: Select broker via smart order routing
        broker = await self._smart_order_route(order)
        if not broker:
            logger.error("No broker available for order")
            return None
        
        # Step 3: Apply execution algorithm
        if order.order_type in [OrderType.TWAP, OrderType.VWAP]:
            asyncio.create_task(
                self._execute_algorithmic(order, broker)
            )
            return order.order_id
        
        # Step 4: Submit order
        order.status = OrderStatus.SUBMITTED
        self.active_orders[order.order_id] = order
        
        try:
            result = await broker.submit_order(order)
            logger.success(f"Order submitted: {order.order_id}")
            return order.order_id
        except Exception as e:
            logger.error(f"Order submission failed: {e}")
            order.status = OrderStatus.REJECTED
            return None
    
    async def _smart_order_route(self, order: Order):
        """
        Smart Order Routing (SOR):
        - Route to best execution venue
        - Consider: price, liquidity, fees, latency
        """
        if order.asset_class == AssetClass.CRYPTO:
            return self.brokers.get('binance') or self.brokers.get('ccxt')
        elif order.asset_class == AssetClass.EQUITY:
            return self.brokers.get('alpaca') or self.brokers.get('interactive_brokers')
        elif order.asset_class == AssetClass.FOREX:
            return self.brokers.get('oanda') or self.brokers.get('interactive_brokers')
        elif order.asset_class == AssetClass.FUTURES:
            return self.brokers.get('interactive_brokers')
        
        # Default: return first available
        return next(iter(self.brokers.values()), None)
    
    async def _execute_algorithmic(self, order: Order, broker):
        """Execute large orders using TWAP/VWAP to minimize market impact"""
        total_qty = order.quantity
        
        if order.order_type == OrderType.TWAP:
            # Split order into equal time slices
            num_slices = self.config.get('twap_slices', 10)
            slice_qty = total_qty / num_slices
            interval = self.config.get('twap_interval_seconds', 60)
            
            for i in range(num_slices):
                child_order = Order(
                    symbol=order.symbol,
                    side=order.side,
                    quantity=slice_qty,
                    order_type=OrderType.MARKET,
                    asset_class=order.asset_class,
                    strategy_id=order.strategy_id
                )
                await broker.submit_order(child_order)
                logger.info(f"TWAP slice {i+1}/{num_slices} submitted")
                await asyncio.sleep(interval)
        
        elif order.order_type == OrderType.VWAP:
            # Volume-weighted: submit more during high-volume periods
            # Use historical volume profile
            volume_profile = await self._get_volume_profile(order.symbol)
            
            for period, vol_weight in enumerate(volume_profile):
                slice_qty = total_qty * vol_weight
                child_order = Order(
                    symbol=order.symbol,
                    side=order.side,
                    quantity=slice_qty,
                    order_type=OrderType.LIMIT,
                    asset_class=order.asset_class,
                    strategy_id=order.strategy_id
                )
                await broker.submit_order(child_order)
                await asyncio.sleep(60)
    
    async def _get_volume_profile(self, symbol: str) -> List[float]:
        """Get intraday volume profile for VWAP"""
        # Return normalized historical volume by period
        # Real implementation fetches from data manager
        profile = np.array([0.05, 0.08, 0.10, 0.12, 0.10, 
                            0.08, 0.07, 0.08, 0.10, 0.12,
                            0.05, 0.05])
        return (profile / profile.sum()).tolist()
    
    async def cancel_order(self, order_id: str) -> bool:
        """Cancel an active order"""
        if order_id not in self.active_orders:
            return False
        
        order = self.active_orders[order_id]
        broker = await self._smart_order_route(order)
        
        try:
            result = await broker.cancel_order(order_id)
            if result:
                order.status = OrderStatus.CANCELLED
                del self.active_orders[order_id]
                self.order_history.append(order)
                for cb in self.callbacks['on_cancel']:
                    await cb(order)
                return True
        except Exception as e:
            logger.error(f"Cancel failed: {e}")
        return False
    
    async def handle_fill(self, fill: Fill):
        """Process a fill notification"""
        self.fills.append(fill)
        
        if fill.order_id in self.active_orders:
            order = self.active_orders[fill.order_id]
            order.filled_quantity += fill.quantity
            order.filled_price = fill.price
            order.commission += fill.commission
            
            if order.filled_quantity >= order.quantity:
                order.status = OrderStatus.FILLED
                del self.active_orders[fill.order_id]
                self.order_history.append(order)
            else:
                order.status = OrderStatus.PARTIAL
            
            for cb in self.callbacks['on_fill']:
                await cb(fill)
        
        logger.success(
            f"Fill: {fill.symbol} {fill.side.value} "
            f"{fill.quantity}@{fill.price}"
        )
    
    def get_active_orders(self) -> List[Order]:
        return list(self.active_orders.values())
    
    def get_order_history(self) -> List[Order]:
        return self.order_history
    
    def get_fills(self) -> List[Fill]:
        return self.fills
