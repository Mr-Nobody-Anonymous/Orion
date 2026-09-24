"""Vibe-Trading adapter: Model Context Protocol (MCP) tool integration."""

from __future__ import annotations

from typing import Any, Callable

from ...capabilities.base import (
    BaseCapabilityProvider,
    CapabilityCategory,
    IntegrationClass,
    ProviderHealth,
    ProviderHealthStatus,
)


class VibeTradingAdapter(BaseCapabilityProvider):
    """Adapter for Model Context Protocol (MCP) and tool-calling interfaces."""

    @property
    def name(self) -> str:
        return "vibe_trading"

    @property
    def category(self) -> CapabilityCategory:
        return CapabilityCategory.AGENT_MEMORY

    @property
    def integration_class(self) -> IntegrationClass:
        return IntegrationClass.ADAPTER

    def health(self) -> ProviderHealth:
        return ProviderHealth(
            provider_name=self.name,
            category=self.category,
            status=ProviderHealthStatus.AVAILABLE,
            version="1.0.0",
            latency_ms=1.5,
        )

    def capabilities(self) -> tuple[str, ...]:
        return (
            "mcp_tool_dispatch",
            "json_schema_validation",
            "agent_context_enrichment",
        )

    def format_mcp_manifest(self, tools: list[dict[str, Any]]) -> dict[str, Any]:
        """Format available capabilities into MCP protocol tools definition."""
        return {
            "protocol": "mcp-v1",
            "tools": tools,
            "server": "orion-capability-bus",
        }
