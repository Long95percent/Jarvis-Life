"""Episodic memory — event sequence and experience recall.

Stores structured records of past agent executions (episodes),
enabling learning from experience. Each episode captures the
task, strategy used, steps taken, and outcome.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import structlog

logger = structlog.get_logger("memory.episodic")


class Episode:
    """A single episodic memory — a complete task execution record."""

    def __init__(
        self,
        episode_id: str,
        task: str,
        strategy: str,
        steps: list[dict[str, Any]],
        outcome: str,
        success: bool,
        metadata: dict[str, Any] | None = None,
    ):
        self.episode_id = episode_id
        self.task = task
        self.strategy = strategy
        self.steps = steps
        self.outcome = outcome
        self.success = success
        self.metadata = metadata or {}
        self.timestamp = time.time()

    def to_dict(self) -> dict[str, Any]:
        return {
            "episode_id": self.episode_id,
            "task": self.task,
            "strategy": self.strategy,
            "steps": self.steps,
            "outcome": self.outcome,
            "success": self.success,
            "metadata": self.metadata,
            "timestamp": self.timestamp,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Episode:
        ep = cls(
            episode_id=data["episode_id"],
            task=data["task"],
            strategy=data["strategy"],
            steps=data.get("steps", []),
            outcome=data.get("outcome", ""),
            success=data.get("success", True),
            metadata=data.get("metadata", {}),
        )
        ep.timestamp = data.get("timestamp", time.time())
        return ep


class EpisodicMemory:
    """File-based episodic memory store.

    Features:
    - Records complete execution episodes
    - Enables experience-based learning (similar task recall)
    - Supports strategy effectiveness analysis
    """

    def __init__(self, storage_path: str = "./data/memory", max_episodes: int = 500):
        self._storage_path = Path(storage_path)
        self._storage_path.mkdir(parents=True, exist_ok=True)
        self._episodes: list[Episode] = []
        self._max = max_episodes
        self._load()

    def _load(self) -> None:
        ep_file = self._storage_path / "episodic.json"
        if ep_file.exists():
            try:
                data = json.loads(ep_file.read_text(encoding="utf-8"))
                self._episodes = [Episode.from_dict(e) for e in data]
            except (json.JSONDecodeError, KeyError):
                self._episodes = []

    def _save(self) -> None:
        ep_file = self._storage_path / "episodic.json"
        data = [e.to_dict() for e in self._episodes[-self._max:]]
        ep_file.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def record(self, episode: Episode) -> None:
        """Record a new episode."""
        self._episodes.append(episode)
        if len(self._episodes) > self._max:
            self._episodes = self._episodes[-self._max:]
        self._save()

    def recall_similar(self, task: str, limit: int = 5) -> list[Episode]:
        """Find episodes with similar tasks. Phase 2+: semantic similarity."""
        task_lower = task.lower()
        scored = []
        for ep in self._episodes:
            # Simple keyword overlap score
            overlap = sum(1 for w in task_lower.split() if w in ep.task.lower())
            if overlap > 0:
                scored.append((overlap, ep))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [ep for _, ep in scored[:limit]]

    def get_strategy_stats(self) -> dict[str, dict[str, int]]:
        """Compute success/failure counts per strategy."""
        stats: dict[str, dict[str, int]] = {}
        for ep in self._episodes:
            if ep.strategy not in stats:
                stats[ep.strategy] = {"success": 0, "failure": 0}
            if ep.success:
                stats[ep.strategy]["success"] += 1
            else:
                stats[ep.strategy]["failure"] += 1
        return stats

    def to_context(self, task: str) -> dict[str, Any]:
        """Export relevant episodes as context."""
        similar = self.recall_similar(task, limit=3)
        if not similar:
            return {}
        return {
            "episodic": "\n".join(
                f"[{ep.strategy}] Task: {ep.task[:100]} -> {'Success' if ep.success else 'Failed'}"
                for ep in similar
            ),
        }
