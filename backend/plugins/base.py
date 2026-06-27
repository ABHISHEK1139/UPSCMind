"""
Hermes V2 — Plugin Base & Manager
═══════════════════════════════════════════════════════════════
Extensible plugin architecture for scrapers, retrievers,
evaluators, and models without touching core code.
"""

from __future__ import annotations

import importlib
import logging
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, List, Optional, Type

logger = logging.getLogger(__name__)


class Plugin(ABC):
    """Base class for all plugins."""

    name: str = "base"
    version: str = "1.0.0"

    @abstractmethod
    def initialize(self) -> None:
        """Called when the plugin is loaded."""
        ...

    @abstractmethod
    def shutdown(self) -> None:
        """Called when the plugin is unloaded."""
        ...


class ScraperPlugin(Plugin):
    """Base for scraper plugins."""

    name: str = "base_scraper"

    async def scrape(self, **kwargs) -> list[dict]:
        """Scrape data from a source."""
        return []


class RetrieverPlugin(Plugin):
    """Base for retriever plugins."""

    name: str = "base_retriever"

    async def retrieve(self, query: str, **kwargs) -> list[dict]:
        """Retrieve relevant documents."""
        return []


class EvaluatorPlugin(Plugin):
    """Base for evaluator plugins."""

    name: str = "base_evaluator"

    def evaluate(self, **kwargs) -> dict:
        """Evaluate an answer."""
        return {}


class PluginManager:
    """Discovers, loads, and manages plugins."""

    def __init__(self, plugin_dirs: list[str | Path] | None = None) -> None:
        self._plugins: Dict[str, Plugin] = {}
        self._plugin_dirs = [Path(d) for d in (plugin_dirs or ["plugins/scrapers", "plugins/retrievers", "plugins/evaluators", "plugins/models"])]

    def discover(self) -> List[Type[Plugin]]:
        """Discover plugin classes in plugin directories."""
        discovered: List[Type[Plugin]] = []
        for plugin_dir in self._plugin_dirs:
            if not plugin_dir.exists():
                continue
            for py_file in plugin_dir.glob("*.py"):
                if py_file.name.startswith("_"):
                    continue
                try:
                    module_name = f"{plugin_dir.as_posix().replace('/', '.')}.{py_file.stem}"
                    module = importlib.import_module(module_name)
                    for attr_name in dir(module):
                        attr = getattr(module, attr_name)
                        if (
                            isinstance(attr, type)
                            and issubclass(attr, Plugin)
                            and attr is not Plugin
                            and attr is not ScraperPlugin
                            and attr is not RetrieverPlugin
                            and attr is not EvaluatorPlugin
                        ):
                            discovered.append(attr)
                except Exception as exc:
                    logger.warning("[PLUGIN] Failed to load %s: %s", py_file, exc)
        return discovered

    def register(self, plugin: Plugin) -> None:
        """Register and initialize a plugin."""
        self._plugins[plugin.name] = plugin
        plugin.initialize()
        logger.info("[PLUGIN] Loaded: %s v%s", plugin.name, plugin.version)

    def get(self, name: str) -> Optional[Plugin]:
        """Get a plugin by name."""
        return self._plugins.get(name)

    def list_plugins(self) -> List[str]:
        """List all registered plugin names."""
        return list(self._plugins.keys())

    def shutdown_all(self) -> None:
        """Shutdown all plugins."""
        for plugin in self._plugins.values():
            try:
                plugin.shutdown()
            except Exception as exc:
                logger.error("[PLUGIN] Shutdown error for %s: %s", plugin.name, exc)
        self._plugins.clear()
