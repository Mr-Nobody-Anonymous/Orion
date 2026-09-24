"""Alpaca paper broker.

Refuses to construct against the live endpoint. Wraps ``alpaca_trade_api``
so ORION can submit paper orders without accidentally routing to production.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Optional

from ....data.contracts import Asset, Order, OrderRequest
from .config import AlpacaConfig, is_paper_base_url


def _alpaca_available() -> bool:
    try:
        import alpaca_trade_api  # type: ignore  # noqa: F401
    except Exception:  # noqa: BLE001
        return False
    return True


@dataclass(frozen=True, slots=True)
class PaperOrderResult:
    client_order_id: str
    alpaca_order_id: str
    status: str
    symbol: str
    side: str
    quantity: Decimal


class AlpacaPaperBroker:
    """A paper-only broker. **Live trading is impossible by construction.**"""

    def __init__(self, config: AlpacaConfig) -> None:
        if not is_paper_base_url(config.base_url):
            raise ValueError("AlpacaPaperBroker only accepts the paper endpoint")
        if not _alpaca_available():
            self._api = None
        else:
            import alpaca_trade_api as tradeapi  # type: ignore
            self._api = tradeapi.REST(config.api_key, config.secret_key,
                                       config.base_url, api_version="v2")
        self._config = config

    @property
    def is_paper(self) -> bool:
        return is_paper_base_url(self._config.base_url)

    def submit_order(self, order: OrderRequest) -> PaperOrderResult:
        if self._api is None:
            raise RuntimeError("alpaca_trade_api is not installed in this environment")
        if not self.is_paper:
            raise RuntimeError("AlpacaPaperBroker refused: base_url is not the paper endpoint")
        side = order.side.value.lower()
        qty = int(order.quantity)
        result = self._api.submit_order(
            symbol=order.asset.symbol,
            qty=qty,
            side=side,
            type=order.order_type,
            time_in_force=order.time_in_force,
            client_order_id=order.client_order_id,
            limit_price=(float(order.limit_price) if order.limit_price is not None else None),
        )
        return PaperOrderResult(
            client_order_id=order.client_order_id,
            alpaca_order_id=str(result.id),
            status=str(result.status),
            symbol=order.asset.symbol,
            side=side,
            quantity=Decimal(qty),
        )

    def list_positions(self) -> tuple[dict, ...]:
        if self._api is None:
            raise RuntimeError("alpaca_trade_api is not installed in this environment")
        return tuple(dict(position) for position in self._api.list_positions())

    def get_account(self) -> dict:
        if self._api is None:
            raise RuntimeError("alpaca_trade_api is not installed in this environment")
        return dict(self._api.get_account())
