"""Restricted list (P2-3)."""

from __future__ import annotations

from typing import Iterable


class RestrictedList:
    """Block-list of symbols the system must not trade."""

    def __init__(self, symbols: Iterable[str] = ()) -> None:
        self._symbols: set[str] = {s.upper() for s in symbols}

    def add(self, symbol: str) -> None:
        self._symbols.add(symbol.upper())

    def remove(self, symbol: str) -> None:
        self._symbols.discard(symbol.upper())

    def is_restricted(self, symbol: str) -> bool:
        return symbol.upper() in self._symbols

    def symbols(self) -> frozenset[str]:
        return frozenset(self._symbols)
