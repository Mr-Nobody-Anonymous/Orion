"""Immutable Double-Entry Financial Accounting Ledger.

Guarantees accounting equation: Assets = Liabilities + Equity.
Every transaction has balanced debits and credits and is cryptographically chained.
Strictly in the Truth plane.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from typing import Mapping, Sequence


@dataclass(frozen=True, slots=True)
class JournalLine:
    account: str  # e.g., "ASSETS:CASH", "ASSETS:EQUITY:AAPL", "EQUITY:REALIZED_PNL"
    debit: Decimal = Decimal("0")
    credit: Decimal = Decimal("0")

    def __post_init__(self) -> None:
        if self.debit < 0 or self.credit < 0:
            raise ValueError("Debits and credits must be non-negative")
        if (self.debit == 0 and self.credit == 0) or (self.debit > 0 and self.credit > 0):
            raise ValueError("A journal line must have either a positive debit OR a positive credit, not both or neither")


@dataclass(frozen=True, slots=True)
class JournalTransaction:
    tx_id: str
    timestamp: datetime
    description: str
    lines: tuple[JournalLine, ...]
    prev_hash: str
    entry_hash: str

    @property
    def total_debits(self) -> Decimal:
        return sum(line.debit for line in self.lines)

    @property
    def total_credits(self) -> Decimal:
        return sum(line.credit for line in self.lines)


class DoubleEntryLedger:
    """Cryptographically chained double-entry ledger."""

    GENESIS_HASH = "0" * 64

    def __init__(self) -> None:
        self._transactions: list[JournalTransaction] = []
        self._account_balances: dict[str, Decimal] = {}  # Net debits minus credits
        self._latest_hash = self.GENESIS_HASH

    @property
    def transactions_count(self) -> int:
        return len(self._transactions)

    def record_transaction(
        self,
        tx_id: str,
        description: str,
        lines: Sequence[JournalLine],
        timestamp: datetime | None = None,
    ) -> JournalTransaction:
        if not lines:
            raise ValueError("Transaction must have at least two journal lines")

        tot_debits = sum(line.debit for line in lines)
        tot_credits = sum(line.credit for line in lines)

        if tot_debits != tot_credits:
            raise ValueError(f"Unbalanced transaction: Debits ({tot_debits}) != Credits ({tot_credits})")

        ts = timestamp or datetime.now(timezone.utc)
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)

        # Cryptographic block-hash calculation
        line_data = [{"acc": l.account, "d": str(l.debit), "c": str(l.credit)} for l in lines]
        payload = f"{self._latest_hash}|{tx_id}|{ts.isoformat()}|{description}|{json.dumps(line_data, sort_keys=True)}"
        entry_hash = hashlib.sha256(payload.encode("utf-8")).hexdigest()

        tx = JournalTransaction(
            tx_id=tx_id,
            timestamp=ts,
            description=description,
            lines=tuple(lines),
            prev_hash=self._latest_hash,
            entry_hash=entry_hash,
        )

        # Update account balances
        for line in lines:
            # By standard accounting convention: Assets and Expenses increase with Debit
            # Liabilities, Equity, and Revenue increase with Credit
            curr = self._account_balances.get(line.account, Decimal("0"))
            self._account_balances[line.account] = curr + line.debit - line.credit

        self._transactions.append(tx)
        self._latest_hash = entry_hash
        return tx

    def get_account_balance(self, account: str) -> Decimal:
        return self._account_balances.get(account, Decimal("0"))

    def check_trial_balance(self) -> bool:
        """Trial balance check: sum of all net account balances must equal zero."""
        net = sum(self._account_balances.values())
        return net == Decimal("0")

    def verify_integrity(self) -> bool:
        """Verifies the cryptographic hash chain from genesis to head."""
        curr_hash = self.GENESIS_HASH
        for tx in self._transactions:
            if tx.prev_hash != curr_hash:
                return False
            line_data = [{"acc": l.account, "d": str(l.debit), "c": str(l.credit)} for l in tx.lines]
            payload = f"{curr_hash}|{tx.tx_id}|{tx.timestamp.isoformat()}|{tx.description}|{json.dumps(line_data, sort_keys=True)}"
            expected_hash = hashlib.sha256(payload.encode("utf-8")).hexdigest()
            if tx.entry_hash != expected_hash:
                return False
            curr_hash = tx.entry_hash
        return True
