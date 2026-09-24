from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Protocol

from ..domain import Asset, MarketQuote, OrderRequest


@dataclass(frozen=True, slots=True)
class Account:
	cash: Decimal
	equity: Decimal


@dataclass(frozen=True, slots=True)
class Fill:
	order_id: str
	asset: Asset
	quantity: Decimal
	price: Decimal
	fee: Decimal = Decimal("0")


class BrokerAdapter(Protocol):
	def get_account(self) -> Account: ...
	def get_positions(self) -> dict[Asset, Decimal]: ...
	def get_market_data(self, asset: Asset) -> MarketQuote: ...
	def place_order(self, order: OrderRequest) -> Fill: ...
	def cancel_order(self, order_id: str) -> None: ...


class SimulatedBroker:
	"""Canonical ORION execution simulator; live connectors cannot bypass risk."""

	def __init__(self, starting_cash: Decimal = Decimal("100000")) -> None:
		self._account = Account(starting_cash, starting_cash)
		self._positions: dict[Asset, Decimal] = {}
		self._quotes: dict[Asset, MarketQuote] = {}
		self.fills: list[Fill] = []

	def set_quote(self, quote: MarketQuote) -> None:
		self._quotes[quote.asset] = quote

	def get_account(self) -> Account:
		return self._account

	def get_positions(self) -> dict[Asset, Decimal]:
		return dict(self._positions)

	def get_market_data(self, asset: Asset) -> MarketQuote:
		if asset not in self._quotes:
			raise LookupError(f"no quote available for {asset.symbol}")
		return self._quotes[asset]

	def place_order(self, order: OrderRequest) -> Fill:
		quote = self.get_market_data(order.asset)
		price = order.limit_price or (quote.ask if order.side.value in {"BUY", "SHORT"} else quote.bid)
		signed_quantity = order.quantity if order.side.value in {"BUY", "CLOSE"} else -order.quantity
		notional = abs(signed_quantity * price)
		if notional > self._account.cash and signed_quantity > 0:
			raise ValueError("insufficient simulated cash")
		self._positions[order.asset] = self._positions.get(order.asset, Decimal("0")) + signed_quantity
		self._account = Account(self._account.cash - signed_quantity * price, self._account.equity)
		fill = Fill(order.client_order_id, order.asset, signed_quantity, price)
		self.fills.append(fill)
		return fill

	def cancel_order(self, order_id: str) -> None:
		if any(fill.order_id == order_id for fill in self.fills):
			raise ValueError("filled orders cannot be cancelled")


class LiveTradingDisabledError(RuntimeError):
	"""Raised whenever code attempts to invoke a deliberately disabled live broker path."""


class AlpacaAdapter:
	def __init__(self, *, enabled: bool = False) -> None:
		if not enabled:
			raise LiveTradingDisabledError("Alpaca adapter is disabled until explicitly enabled")
		raise LiveTradingDisabledError("Alpaca live execution is BLOCKED pending a credential-isolated, audited adapter")
