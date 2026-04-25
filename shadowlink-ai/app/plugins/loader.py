"""Plugin loader — discovers, loads, and manages plugins at runtime.

Scans the builtin plugins directory and optionally external plugin
directories. Manages plugin lifecycle (load, initialize, shutdown).
"""

from __future__ import annotations

import importlib
import pkgutil
from pathlib import Path
from typing import Any

import structlog

from app.models.mcp import PluginInfo, PluginStatus
from app.plugins.interface import PluginInterface

logger = structlog.get_logger("plugins.loader")


class PluginLoader:
    """Dynamic plugin loader and lifecycle manager."""

    def __init__(self) -> None:
        self._plugins: dict[str, PluginInterface] = {}
        self._status: dict[str, PluginStatus] = {}

    async def load_builtin_plugins(self) -> None:
        """Discover and load all built-in plugins from app.plugins.builtin."""
        builtin_path = Path(__file__).parent / "builtin"
        if not builtin_path.exists():
            return

        for finder, name, ispkg in pkgutil.iter_modules([str(builtin_path)]):
            if name.startswith("_"):
                continue
            try:
                module = importlib.import_module(f"app.plugins.builtin.{name}")
                if hasattr(module, "create_plugin"):
                    plugin = module.create_plugin()
                    await self.register(plugin)
            except Exception as exc:
                await logger.aerror("plugin_load_failed", plugin=name, error=str(exc))

    async def register(self, plugin: PluginInterface) -> None:
        """Register and initialize a plugin."""
        info = plugin.get_info()
        try:
            await plugin.initialize()
            self._plugins[info.name] = plugin
            self._status[info.name] = PluginStatus.ACTIVE
            await logger.ainfo("plugin_registered", name=info.name, version=info.version)
        except Exception as exc:
            self._status[info.name] = PluginStatus.ERROR
            await logger.aerror("plugin_init_failed", name=info.name, error=str(exc))

    async def unload(self, name: str) -> None:
        """Shut down and unload a plugin."""
        if name in self._plugins:
            await self._plugins[name].shutdown()
            del self._plugins[name]
            self._status[name] = PluginStatus.DISABLED

    def get_plugin(self, name: str) -> PluginInterface | None:
        """Get a loaded plugin by name."""
        return self._plugins.get(name)

    def list_plugins(self) -> list[PluginInfo]:
        """List all registered plugins with their status."""
        result = []
        for name, plugin in self._plugins.items():
            info = plugin.get_info()
            info.status = self._status.get(name, PluginStatus.LOADED)
            result.append(info)
        return result

    async def shutdown_all(self) -> None:
        """Shut down all loaded plugins."""
        for name in list(self._plugins.keys()):
            await self.unload(name)
