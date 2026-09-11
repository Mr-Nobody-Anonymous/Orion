"""Mission budget — reservation semantics, not a single number.

Phase 1 ORION 2.0, correction #8. Four distinct quantities:

* ``allocated`` — the total the mission may ever spend
* ``reserved``  — held by in-flight (possibly concurrent) operations
* ``spent``     — committed by completed operations
* ``remaining`` — allocated minus reserved minus spent

The lifecycle is ``reserve() -> commit() / release()``. Money is
never moved outside that lifecycle. All operations are idempotent on
``reservation_id`` so a crash immediately before or after persistence
cannot double-spend. The budget is immutable: every operation returns
a new :class:`Budget` (copy-on-write, like :class:`WorldState`).

All amounts are :class:`decimal.Decimal` (correction #5).
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Mapping


class BudgetError(RuntimeError):
    """A budget operation cannot be performed."""


@dataclass(frozen=True, slots=True)
class Reservation:
    """One reserved slice of the budget."""

    reservation_id: str
    amount: Decimal
    agent_id: str = ""
    status: str = "reserved"  # reserved | committed | released
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self) -> None:
        if not self.reservation_id:
            raise ValueError("reservation_id must be non-empty")
        if not isinstance(self.amount, Decimal):
            raise ValueError("amount must be a Decimal")
        if self.amount < 0:
            raise ValueError("amount must be non-negative")
        if self.status not in ("reserved", "committed", "released"):
            raise ValueError(f"unknown reservation status {self.status!r}")

    def as_dict(self) -> dict[str, Any]:
        return {
            "reservation_id": self.reservation_id,
            "amount": str(self.amount),
            "agent_id": self.agent_id,
            "status": self.status,
            "created_at": self.created_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Reservation":
        return cls(
            reservation_id=str(d["reservation_id"]),
            amount=Decimal(str(d["amount"])),
            agent_id=str(d.get("agent_id", "")),
            status=str(d.get("status", "reserved")),
            created_at=datetime.fromisoformat(str(d["created_at"])),
        )



@dataclass(frozen=True, slots=True)
class Budget:
    """An immutable budget with reserve / commit / release semantics."""

    allocated: Decimal
    reservations: Mapping[str, Reservation] = field(default_factory=dict)
    spent_amount: Decimal = Decimal("0")

    def __post_init__(self) -> None:
        if not isinstance(self.allocated, Decimal):
            raise ValueError("allocated must be a Decimal")
        if self.allocated < 0:
            raise ValueError("allocated must be non-negative")
        if not isinstance(self.spent_amount, Decimal):
            raise ValueError("spent must be a Decimal")

    # ----------------------------------------------------------- invariants

    @property
    def reserved(self) -> Decimal:
        return sum(
            (r.amount for r in self.reservations.values() if r.status == "reserved"),
            Decimal("0"),
        )

    @property
    def spent(self) -> Decimal:
        return self.spent_amount

    @property
    def remaining(self) -> Decimal:
        return self.allocated - self.reserved - self.spent

    # -------------------------------------------------------------- actions

    def reserve(
        self,
        amount: Decimal,
        *,
        reservation_id: str,
        agent_id: str = "",
    ) -> "Budget":
        """Hold ``amount`` of capacity. Idempotent on ``reservation_id``."""
        amount = _check_amount(amount)
        existing = self.reservations.get(reservation_id)
        if existing is not None:
            if existing.amount != amount:
                raise BudgetError(
                    f"reservation {reservation_id!r} already exists "
                    f"with a different amount"
                )
            return self
        if amount > self.remaining:
            raise BudgetError(
                f"cannot reserve {amount}: remaining budget is "
                f"{self.remaining} (allocated {self.allocated}, "
                f"reserved {self.reserved}, spent {self.spent})"
            )
        reservation = Reservation(
            reservation_id=reservation_id, amount=amount, agent_id=agent_id
        )
        reservations = dict(self.reservations)
        reservations[reservation_id] = reservation
        return replace(self, reservations=reservations)

    def commit(self, reservation_id: str, *, actual: Decimal | None = None) -> "Budget":
        """Turn a reservation into spend. Idempotent on ``reservation_id``."""
        reservation = self.reservations.get(reservation_id)
        if reservation is None:
            raise BudgetError(f"unknown reservation {reservation_id!r}")
        if reservation.status == "committed":
            return self
        if reservation.status == "released":
            raise BudgetError(
                f"reservation {reservation_id!r} was released; cannot commit"
            )
        actual_amount = (
            _check_amount(actual) if actual is not None else reservation.amount
        )
        if actual_amount > reservation.amount:
            raise BudgetError(
                f"commit actual {actual_amount} exceeds reserved "
                f"{reservation.amount} for {reservation_id!r}"
            )
        reservations = dict(self.reservations)
        reservations[reservation_id] = replace(reservation, status="committed")
        return replace(
            self,
            reservations=reservations,
            spent_amount=self.spent_amount + actual_amount,
        )

    def release(self, reservation_id: str) -> "Budget":
        """Return a reservation's capacity. Idempotent."""
        reservation = self.reservations.get(reservation_id)
        if reservation is None:
            raise BudgetError(f"unknown reservation {reservation_id!r}")
        if reservation.status == "released":
            return self
        if reservation.status == "committed":
            raise BudgetError(
                f"reservation {reservation_id!r} was committed; cannot release"
            )
        reservations = dict(self.reservations)
        reservations[reservation_id] = replace(reservation, status="released")
        return replace(self, reservations=reservations)

    # --------------------------------------------------------- persistence

    def as_dict(self) -> dict[str, Any]:
        return {
            "allocated": str(self.allocated),
            "spent": str(self.spent_amount),
            "reservations": [r.as_dict() for r in self.reservations.values()],
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Budget":
        reservations = tuple(
            Reservation.from_dict(r) for r in d.get("reservations", ())
        )
        return cls(
            allocated=Decimal(str(d["allocated"])),
            reservations={r.reservation_id: r for r in reservations},
            spent_amount=Decimal(str(d.get("spent", "0"))),
        )


def _check_amount(amount: Decimal) -> Decimal:
    if not isinstance(amount, Decimal):
        raise ValueError("amount must be a Decimal")
    if amount < 0:
        raise ValueError("amount must be non-negative")
    return amount


__all__ = ["Budget", "BudgetError", "Reservation"]
