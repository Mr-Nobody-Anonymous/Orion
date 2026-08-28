"""Entity registry for the ORION world model.

Entities are the nouns of the domain: assets, venues, macro indicators,
portfolios, models. Each attribute carries its epistemic status so unknown
or estimated values can never masquerade as known facts.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class EntityType(str, Enum):
    ASSET = "asset"
    VENUE = "venue"
    MACRO_SERIES = "macro_series"
    PORTFOLIO = "portfolio"
    MODEL = "model"
    AGENT = "agent"
    EVENT = "event"


@dataclass(frozen=True, slots=True)
class AttributeObservation:
    value: Any
    known: bool
    confidence: float
    source: str
    observed_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self) -> None:
        if not 0 <= self.confidence <= 1:
            raise ValueError("confidence must be between 0 and 1")


@dataclass(slots=True)
class Entity:
    identifier: str
    entity_type: EntityType
    attributes: dict[str, AttributeObservation] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def observe(self, attribute: str, value: Any, *, known: bool = True,
                confidence: float = 1.0, source: str = "orion") -> AttributeObservation:
        if not attribute.strip():
            raise ValueError("attribute name is required")
        observation = AttributeObservation(value, known, confidence, source)
        self.attributes[attribute] = observation
        return observation

    def attribute_value(self, attribute: str) -> Any:
        return self.attributes[attribute].value if attribute in self.attributes else None

    def is_known(self, attribute: str) -> bool:
        return attribute in self.attributes and self.attributes[attribute].known

    def unknown_attributes(self) -> tuple[str, ...]:
        return tuple(name for name, obs in self.attributes.items() if not obs.known)


class EntityRegistry:
    """Bounded registry of world entities with typed lookups."""

    def __init__(self) -> None:
        self._entities: dict[str, Entity] = {}

    def register(self, identifier: str, entity_type: EntityType) -> Entity:
        if not identifier.strip():
            raise ValueError("entity identifier is required")
        if identifier in self._entities:
            raise ValueError(f"entity already registered: {identifier}")
        entity = Entity(identifier, entity_type)
        self._entities[identifier] = entity
        return entity

    def get(self, identifier: str) -> Entity | None:
        return self._entities.get(identifier)

    def require(self, identifier: str) -> Entity:
        entity = self._entities.get(identifier)
        if entity is None:
            raise KeyError(f"unknown entity: {identifier}")
        return entity

    def by_type(self, entity_type: EntityType) -> tuple[Entity, ...]:
        return tuple(entity for entity in self._entities.values() if entity.entity_type is entity_type)

    def count(self) -> int:
        return len(self._entities)

    def identifiers(self) -> tuple[str, ...]:
        return tuple(sorted(self._entities))
