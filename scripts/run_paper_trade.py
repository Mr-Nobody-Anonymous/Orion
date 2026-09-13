#!/usr/bin/env python
"""Broker Integration & Paper Trade Simulation

Generates an OrderIntent, pushes it through the 12-Gate Risk Firewall,
and executes a paper trade via the Alpaca adapter.
"""

import sys
import os
from dotenv import load_dotenv

load_dotenv()
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import json
from decimal import Decimal
from orion.data.contracts import OrderIntent, Action
from orion.trading.risk_firewall import RiskFirewall
from adapters.alpaca import AlpacaAdapter

def main() -> None:
    print("Initializing Orion Execution Planner...")
    
    intent = OrderIntent(
        intent_id="intent-test-01",
        strategy_id="momentum_test_strat",
        symbol="AAPL",
        side=Action.BUY,
        target_quantity=Decimal("50.0"),
        order_type="MARKET",
        limit_price=Decimal("150.0"),
    )
    
    # 1. Initialize Risk Firewall
    firewall = RiskFirewall()
    
    print(f"\n[1] Submitting OrderIntent for {intent.target_quantity} {intent.symbol} @ {intent.limit_price} to Risk Firewall...")
    
    verdict = firewall.evaluate(
        intent=intent,
        portfolio_equity=Decimal("100000.0"),
        current_positions={"AAPL": Decimal("0")},
        kill_switch_engaged=False,
        venue_healthy=True,
    )
    
    print("\n[2] Risk Firewall Verdict:")
    print(json.dumps(verdict.as_dict(), indent=2))
    
    if verdict.approved:
        print("\n[3] Order Approved. Routing to Alpaca Paper Broker...")
        adapter = AlpacaAdapter()
        report = adapter.execute_order(intent)
        print("\n[4] Execution Report received:")
        print(f"  Order ID: {report.order_id}")
        print(f"  Status:   {report.status}")
        print(f"  Asset:    {report.asset.symbol}")
        print(f"  Price:    ${report.price}")
        print(f"  Quantity: {report.quantity}")
        print("\nPaper trade simulation complete.")
    else:
        print(f"\n[3] Order Rejected by Risk Firewall: {verdict.rejection_reason}")

if __name__ == "__main__":
    main()
