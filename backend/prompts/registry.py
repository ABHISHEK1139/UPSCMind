"""
Hermes V2 — Versioned Prompt Registry
═══════════════════════════════════════
Treats prompts as versioned, scored artifacts (YAML files).
Each prompt has metadata: version, author, date, target_model, evaluation_score.
"""

import os
import logging
from typing import Optional
from pathlib import Path
from functools import lru_cache

import yaml

logger = logging.getLogger(__name__)

PROMPTS_DIR = Path(__file__).parent


class PromptVersion:
    """A single versioned prompt loaded from YAML."""

    def __init__(self, filepath: Path):
        self.filepath = filepath
        with open(filepath, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        meta = data.get("metadata", {})
        self.name: str = meta.get("name", filepath.stem)
        self.version: int = meta.get("version", 1)
        self.author: str = meta.get("author", "system")
        self.created: str = meta.get("created", "unknown")
        self.target_model: str = meta.get("target_model", "")
        self.evaluation_score: Optional[float] = meta.get("evaluation_score")

        self.system_prompt: str = data.get("system_prompt", "")
        self.variables: list[str] = data.get("variables", [])

    def render(self, **kwargs) -> str:
        """Render the system prompt with variable substitution."""
        rendered = self.system_prompt
        for var in self.variables:
            placeholder = "{" + var + "}"
            if placeholder in rendered and var in kwargs:
                rendered = rendered.replace(placeholder, str(kwargs[var]))
        return rendered

    def __repr__(self):
        return f"<Prompt '{self.name}' v{self.version} score={self.evaluation_score}>"


class PromptRegistry:
    """
    Loads and manages all versioned prompts from the prompts/ directory.
    Automatically selects the latest or highest-scoring version.
    """

    def __init__(self, prompts_dir: Optional[Path] = None):
        self.prompts_dir = prompts_dir or PROMPTS_DIR
        self._prompts: dict[str, list[PromptVersion]] = {}
        self._load_all()

    def _load_all(self):
        """Scan the prompts directory for YAML files and load them."""
        if not self.prompts_dir.exists():
            logger.warning(f"Prompts directory not found: {self.prompts_dir}")
            return

        for filepath in self.prompts_dir.glob("*.yaml"):
            try:
                pv = PromptVersion(filepath)
                if pv.name not in self._prompts:
                    self._prompts[pv.name] = []
                self._prompts[pv.name].append(pv)
                logger.debug(f"Loaded prompt: {pv}")
            except Exception as e:
                logger.error(f"Failed to load prompt {filepath}: {e}")

        # Sort each prompt's versions by version number (descending)
        for name in self._prompts:
            self._prompts[name].sort(key=lambda p: p.version, reverse=True)

    def get(self, name: str, version: Optional[int] = None) -> Optional[PromptVersion]:
        """
        Get a prompt by name.
        If version is specified, return that exact version.
        Otherwise, return the latest version.
        """
        versions = self._prompts.get(name, [])
        if not versions:
            logger.warning(f"Prompt '{name}' not found in registry.")
            return None

        if version is not None:
            for pv in versions:
                if pv.version == version:
                    return pv
            logger.warning(f"Prompt '{name}' v{version} not found.")
            return None

        # Return latest version (first in sorted list)
        return versions[0]

    def get_best(self, name: str) -> Optional[PromptVersion]:
        """
        Get the highest-scoring version of a prompt.
        Falls back to latest version if no scores are available.
        """
        versions = self._prompts.get(name, [])
        if not versions:
            return None

        scored = [pv for pv in versions if pv.evaluation_score is not None]
        if scored:
            return max(scored, key=lambda p: p.evaluation_score)

        return versions[0]  # Fallback to latest

    def list_all(self) -> dict[str, list[PromptVersion]]:
        """List all registered prompts and their versions."""
        return dict(self._prompts)

    def render(self, name: str, version: Optional[int] = None, **kwargs) -> str:
        """Convenience: get a prompt and render it with variables."""
        pv = self.get(name, version)
        if pv is None:
            raise ValueError(f"Prompt '{name}' not found.")
        return pv.render(**kwargs)


@lru_cache()
def get_prompt_registry() -> PromptRegistry:
    """Cached singleton for the prompt registry."""
    return PromptRegistry()
