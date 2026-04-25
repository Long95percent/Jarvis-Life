"""Hermes Agent protocol implementation — self-describing, dynamically discoverable agents.

Key features:
  - Self-description: Each agent declares its capabilities and boundaries
  - Dynamic discovery: Agents register/discover at runtime via a registry
  - Async messaging: Agents communicate through message queues
  - Negotiation: Multi-agent consensus via proposal evaluation
"""

from __future__ import annotations

import asyncio
from typing import Any

import structlog
from pydantic import BaseModel, Field

from app.models.agent import AgentDescriptor

logger = structlog.get_logger("agent.hermes")


class AgentRegistry:
    """Global registry for Hermes agents — maps capabilities to agents."""

    def __init__(self) -> None:
        self._agents: dict[str, AgentDescriptor] = {}

    async def register(self, descriptor: AgentDescriptor) -> None:
        """Register an agent with its capabilities."""
        self._agents[descriptor.name] = descriptor
        await logger.ainfo("agent_registered", name=descriptor.name, capabilities=descriptor.capabilities)

    async def unregister(self, name: str) -> None:
        """Remove an agent from the registry."""
        self._agents.pop(name, None)

    async def find_by_capability(self, capability: str) -> list[AgentDescriptor]:
        """Find all agents that declare the given capability."""
        return [a for a in self._agents.values() if capability in a.capabilities]

    async def list_all(self) -> list[AgentDescriptor]:
        """List all registered agents."""
        return list(self._agents.values())


class HermesMessage(BaseModel):
    """Message passed between Hermes agents."""

    from_agent: str
    to_agent: str
    task: str
    payload: dict[str, Any] = Field(default_factory=dict)
    reply: str = ""


class HermesAgent:
    """A self-describing agent following the Hermes protocol.

    Each agent:
    1. Registers with the global AgentRegistry, declaring its capabilities
    2. Can delegate tasks to other agents based on capability matching
    3. Supports async message passing via inbox queues
    4. Can participate in multi-agent negotiation
    """

    def __init__(self, descriptor: AgentDescriptor, registry: AgentRegistry):
        self.descriptor = descriptor
        self.registry = registry
        self.inbox: asyncio.Queue[HermesMessage] = asyncio.Queue()

    @property
    def name(self) -> str:
        return self.descriptor.name

    async def start(self) -> None:
        """Register with the global registry and start listening."""
        await self.registry.register(self.descriptor)

    async def stop(self) -> None:
        """Unregister from the global registry."""
        await self.registry.unregister(self.name)

    async def handle(self, message: HermesMessage) -> str:
        """Handle an incoming message. Override in subclasses."""
        await logger.ainfo("hermes_handle", agent=self.name, task=message.task[:100])
        return f"[{self.name}] Handled: {message.task[:100]} (placeholder)"

    async def delegate(self, task: str, required_capability: str) -> str:
        """Find an agent with the required capability and delegate the task."""
        candidates = await self.registry.find_by_capability(required_capability)
        if not candidates:
            return f"No agent found with capability: {required_capability}"

        # Select the best candidate (simple: first match; Phase 2+: scoring)
        best = candidates[0]
        message = HermesMessage(from_agent=self.name, to_agent=best.name, task=task)

        await logger.ainfo("hermes_delegate", from_a=self.name, to_a=best.name, capability=required_capability)

        # For now, direct invocation; Phase 2+ will use async message queue
        # In production, this would put the message in the target agent's inbox
        return f"Delegated to {best.name}: {task[:100]} (placeholder)"

    async def negotiate(self, agents: list[HermesAgent], task: str) -> str:
        """Collect proposals from multiple agents and find consensus."""
        proposals: dict[str, str] = {}
        for agent in agents:
            msg = HermesMessage(from_agent=self.name, to_agent=agent.name, task=task)
            result = await agent.handle(msg)
            proposals[agent.name] = result

        await logger.ainfo("hermes_negotiation", proposer=self.name, participants=len(agents))
        return f"Consensus from {len(agents)} agents (placeholder)"
