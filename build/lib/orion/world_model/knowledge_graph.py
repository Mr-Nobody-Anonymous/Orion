"""Institutional Financial Knowledge Graph.

Models entity relationships (Company -> Supplier -> Customer -> Competitor -> Sector -> Macro)
and computes supply-chain shock propagation.
Strictly in the Truth plane.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum
from typing import Mapping, Sequence

from .entities import Entity, EntityRegistry, EntityType


class RelationType(str, Enum):
    SUPPLIER_TO = "SUPPLIER_TO"
    CUSTOMER_OF = "CUSTOMER_OF"
    COMPETITOR_OF = "COMPETITOR_OF"
    SUBSIDIARY_OF = "SUBSIDIARY_OF"
    PARENT_OF = "PARENT_OF"
    OPERATES_IN_SECTOR = "OPERATES_IN_SECTOR"
    EXPOSED_TO_COMMODITY = "EXPOSED_TO_COMMODITY"
    AFFECTED_BY_MACRO = "AFFECTED_BY_MACRO"


@dataclass(frozen=True, slots=True)
class KnowledgeEdge:
    source_id: str
    relation: RelationType
    target_id: str
    weight: Decimal = Decimal("1.0")  # Relationship strength or revenue dependence fraction (0 to 1)
    metadata: Mapping[str, str] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ShockImpact:
    entity_id: str
    impact_magnitude: Decimal
    path_depth: int
    propagation_path: tuple[str, ...]


class FinancialKnowledgeGraph:
    """Directed graph representing inter-company, macro, and supply-chain linkages."""

    def __init__(self, registry: EntityRegistry | None = None) -> None:
        self.registry = registry or EntityRegistry()
        # Adjacency: source_id -> list of KnowledgeEdge
        self._adj: dict[str, list[KnowledgeEdge]] = {}
        # Inverted adjacency: target_id -> list of KnowledgeEdge
        self._rev_adj: dict[str, list[KnowledgeEdge]] = {}

    def add_relation(
        self,
        source_id: str,
        relation: RelationType,
        target_id: str,
        weight: Decimal = Decimal("1.0"),
        metadata: Mapping[str, str] | None = None,
    ) -> KnowledgeEdge:
        edge = KnowledgeEdge(
            source_id=source_id,
            relation=relation,
            target_id=target_id,
            weight=weight,
            metadata=metadata or {},
        )
        self._adj.setdefault(source_id, []).append(edge)
        self._rev_adj.setdefault(target_id, []).append(edge)
        return edge

    def get_outgoing(self, entity_id: str, relation: RelationType | None = None) -> tuple[KnowledgeEdge, ...]:
        edges = self._adj.get(entity_id, [])
        if relation is not None:
            return tuple(e for e in edges if e.relation == relation)
        return tuple(edges)

    def get_incoming(self, entity_id: str, relation: RelationType | None = None) -> tuple[KnowledgeEdge, ...]:
        edges = self._rev_adj.get(entity_id, [])
        if relation is not None:
            return tuple(e for e in edges if e.relation == relation)
        return tuple(edges)

    def propagate_supply_chain_shock(
        self,
        disrupted_entity_id: str,
        initial_shock: Decimal = Decimal("1.0"),
        max_depth: int = 3,
        damping_factor: Decimal = Decimal("0.7"),
    ) -> list[ShockImpact]:
        """Breadth-first search traversing downstream SUPPLIER_TO linkages to compute shock impact."""
        impacts: list[ShockImpact] = []
        visited = {disrupted_entity_id}
        queue: deque[tuple[str, Decimal, int, tuple[str, ...]]] = deque([(disrupted_entity_id, initial_shock, 0, (disrupted_entity_id,))])

        while queue:
            curr_id, curr_shock, depth, path = queue.popleft()
            if depth > 0:
                impacts.append(ShockImpact(
                    entity_id=curr_id,
                    impact_magnitude=curr_shock,
                    path_depth=depth,
                    propagation_path=path,
                ))

            if depth >= max_depth:
                continue

            # Downstream customers: where curr_id is SUPPLIER_TO target_id
            edges = self.get_outgoing(curr_id, RelationType.SUPPLIER_TO)
            for e in edges:
                target = e.target_id
                if target not in visited:
                    visited.add(target)
                    transmitted_shock = curr_shock * e.weight * damping_factor
                    queue.append((target, transmitted_shock, depth + 1, path + (target,)))

        impacts.sort(key=lambda x: x.impact_magnitude, reverse=True)
        return impacts
