"""Trading strategies, risk, portfolio and execution."""

from .execution import Account, AlpacaAdapter, BrokerAdapter, Fill, LiveTradingDisabledError, SimulatedBroker
from .risk import RiskEngine, RiskLimits


def __getattr__(name: str):
    """Lazy re-export of :class:`SimulatedExchangeBroker`.

    Importing :class:`SimulatedExchangeBroker` at module-init time
    would create a circular import: ``simulation.exchange`` depends
    on ``trading.execution``, and ``trading.execution`` is in this
    package.  ``__getattr__`` defers the resolution until the user
    actually asks for the symbol, by which point the cycle is
    already complete.
    """
    if name == "SimulatedExchangeBroker":
        from ..simulation.exchange import SimulatedExchangeBroker

        return SimulatedExchangeBroker
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "Account",
    "AlpacaAdapter",
    "BrokerAdapter",
    "Fill",
    "LiveTradingDisabledError",
    "RiskEngine",
    "RiskLimits",
    "SimulatedBroker",
    "SimulatedExchangeBroker",
]
