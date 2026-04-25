"""Plugin interface — contract that all plugins must implement.

Plugins extend ShadowLink's capabilities at runtime. Each plugin:
- Declares supported file formats and capabilities
- Provides tools that are registered in the tool registry
- Can be loaded/unloaded dynamically
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from app.models.mcp import PluginInfo, PluginStatus, ToolInfo


class PluginInterface(ABC):
    """Abstract base class for all ShadowLink plugins."""

    @abstractmethod
    def get_info(self) -> PluginInfo:
        """Return plugin metadata."""
        ...

    @abstractmethod
    async def initialize(self, config: dict[str, Any] | None = None) -> None:
        """Initialize the plugin with optional configuration."""
        ...

    @abstractmethod
    async def shutdown(self) -> None:
        """Clean up resources when the plugin is unloaded."""
        ...

    @abstractmethod
    def get_tools(self) -> list[tuple[ToolInfo, Any]]:
        """Return (ToolInfo, handler) pairs for tools this plugin provides."""
        ...

    def get_supported_formats(self) -> list[str]:
        """Return file extensions this plugin can process."""
        return self.get_info().supported_formats
