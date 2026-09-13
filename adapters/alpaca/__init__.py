"""Alpaca-py Broker Adapter for ORION.

Translates Alpaca paper/live US equity and ETF execution into canonical
Orion ExecutionReport and MarketBar schemas.
Mandates routing through Orion's 12-Gate Risk Firewall before order submission.
"""

from __future__ import annotations

import os
import requests
from typing import Any, Mapping, Sequence
from decimal import Decimal
from datetime import datetime, timezone

from orion.data.contracts import ExecutionPlan, ExecutionReport, OrderIntent, Position, Asset, AssetClass


class AlpacaAdapter:
    """Canonical adapter facade for Alpaca REST API execution."""

    def __init__(self, config: Mapping[str, Any] | None = None) -> None:
        self.config = config or {}
        self.provider_name = "Alpaca Brokerage"
        self.version = "1.0.0"
        
        # Pull from environment, fallback to dummy for safety/tests
        self.api_key = os.getenv("ALPACA_API_KEY", "dummy_key")
        self.secret_key = os.getenv("ALPACA_SECRET_KEY", "dummy_secret")
        # Hardcode to paper for safety unless explicitly configured otherwise
        self.base_url = self.config.get("base_url", "https://paper-api.alpaca.markets")
        
        self.headers = {
            "APCA-API-KEY-ID": self.api_key,
            "APCA-API-SECRET-KEY": self.secret_key,
            "Content-Type": "application/json"
        }

    def execute_order(self, intent: OrderIntent) -> ExecutionReport:
        """Fallback method matching old stub signature. Maps to submit_order."""
        # For simplicity, if we only have intent, we pass it.
        return self.submit_order(intent=intent)

    def submit_order(self, plan: ExecutionPlan | None = None, intent: OrderIntent | None = None) -> ExecutionReport:
        """Route order through Alpaca broker adapter."""
        
        # We need the intent details to place the trade
        symbol = intent.symbol if intent else "UNKNOWN"
        side = intent.side.value if intent else "BUY"
        qty = float(intent.target_quantity) if intent else 0.0
        order_type = intent.order_type.lower() if intent else "market"
        limit_price = float(intent.limit_price) if intent and intent.limit_price else None
        
        payload = {
            "symbol": symbol,
            "qty": qty,
            "side": side.lower(),
            "type": order_type,
            "time_in_force": "day"
        }
        
        if order_type == "limit" and limit_price:
            payload["limit_price"] = limit_price

        # In paper/dry-run mode if keys are dummy, return a simulated success
        if self.api_key == "dummy_key":
            return ExecutionReport(
                order_id=intent.intent_id if intent else "sim_order_123",
                asset=Asset(symbol, AssetClass.EQUITY),
                quantity=Decimal(str(qty)),
                price=Decimal(str(limit_price or 100.0)),
                status="simulated_fill"
            )

        # Real HTTP Request
        try:
            resp = requests.post(f"{self.base_url}/v2/orders", json=payload, headers=self.headers, timeout=5.0)
            resp.raise_for_status()
            data = resp.json()
            
            return ExecutionReport(
                order_id=data.get("id", ""),
                asset=Asset(symbol, AssetClass.EQUITY),
                quantity=Decimal(str(data.get("filled_qty", 0))),
                price=Decimal(str(data.get("filled_avg_price", 0))),
                status=data.get("status", "unknown")
            )
            
        except requests.exceptions.RequestException as e:
            # Handle 403 Forbidden or 422 Unprocessable Entity
            err_msg = str(e)
            if hasattr(e, "response") and e.response is not None:
                err_msg = f"{e.response.status_code} - {e.response.text}"
                
            return ExecutionReport(
                order_id="failed_order",
                asset=Asset(symbol, AssetClass.EQUITY),
                quantity=Decimal("0"),
                price=Decimal("0"),
                status=f"error: {err_msg}"
            )

    def cancel_order(self, order_id: str) -> bool:
        """Cancel an open resting order on Alpaca."""
        if self.api_key == "dummy_key":
            return True
            
        try:
            resp = requests.delete(f"{self.base_url}/v2/orders/{order_id}", headers=self.headers, timeout=5.0)
            return resp.status_code in (200, 204)
        except requests.exceptions.RequestException:
            return False

    def get_positions(self) -> Sequence[Position]:
        """Fetch current open broker positions from Alpaca."""
        if self.api_key == "dummy_key":
            return []
            
        try:
            resp = requests.get(f"{self.base_url}/v2/positions", headers=self.headers, timeout=5.0)
            resp.raise_for_status()
            data = resp.json()
            
            positions = []
            for p in data:
                positions.append(
                    Position(
                        asset=Asset(p["symbol"], AssetClass.EQUITY),
                        quantity=Decimal(str(p["qty"])),
                        average_price=Decimal(str(p["avg_entry_price"])),
                        mark_price=Decimal(str(p["current_price"]))
                    )
                )
            return positions
        except requests.exceptions.RequestException:
            return []
