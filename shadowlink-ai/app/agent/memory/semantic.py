"""Semantic memory — knowledge graph using NetworkX.

Stores entity-relationship structures for cross-session reasoning.
Uses NetworkX directed graph with JSON persistence.

Features:
- Entity/concept nodes with typed properties
- Named relation edges (subject --predicate--> object)
- Subgraph extraction for context injection
- File-based persistence (node-link JSON format)
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import structlog

logger = structlog.get_logger("memory.semantic")


class SemanticMemory:
    """NetworkX-based knowledge graph for semantic memory.

    Nodes represent concepts/entities with property dicts.
    Edges represent named relations (predicate labels).
    Persists to data/memory/semantic_graph.json.
    """

    def __init__(self, storage_path: str = "./data/memory") -> None:
        self._storage_path = Path(storage_path)
        self._storage_path.mkdir(parents=True, exist_ok=True)
        self._graph_file = self._storage_path / "semantic_graph.json"

        try:
            import networkx as nx
            self._nx = nx
        except ImportError:
            self._nx = None
            logger.warning("networkx_not_available", msg="pip install networkx for semantic memory")

        self._graph = self._nx.DiGraph() if self._nx else None
        self._load()

    # ── Persistence ──

    def _load(self) -> None:
        if self._graph is None or not self._graph_file.exists():
            return
        try:
            data = json.loads(self._graph_file.read_text(encoding="utf-8"))
            self._graph = self._nx.node_link_graph(data, directed=True)
            logger.info("semantic_graph_loaded", nodes=self._graph.number_of_nodes(), edges=self._graph.number_of_edges())
        except (json.JSONDecodeError, Exception) as exc:
            logger.warning("semantic_graph_load_failed", error=str(exc))

    def _save(self) -> None:
        if self._graph is None:
            return
        data = self._nx.node_link_data(self._graph)
        self._graph_file.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    # ── Node (concept) operations ──

    def add_concept(self, name: str, properties: dict[str, Any] | None = None) -> None:
        """Add or update a concept node with properties."""
        if self._graph is None:
            return
        self._graph.add_node(name, **(properties or {}))
        self._save()

    def get_concept(self, name: str) -> dict[str, Any] | None:
        """Retrieve a concept's properties."""
        if self._graph is None or name not in self._graph:
            return None
        return dict(self._graph.nodes[name])

    def remove_concept(self, name: str) -> bool:
        """Remove a concept and all its edges."""
        if self._graph is None or name not in self._graph:
            return False
        self._graph.remove_node(name)
        self._save()
        return True

    def list_concepts(self, limit: int = 50) -> list[str]:
        """List all concept names."""
        if self._graph is None:
            return []
        return list(self._graph.nodes)[:limit]

    # ── Edge (relation) operations ──

    def add_relation(self, subject: str, predicate: str, obj: str, properties: dict[str, Any] | None = None) -> None:
        """Add a typed relation: subject --predicate--> object."""
        if self._graph is None:
            return
        # Ensure both nodes exist
        if subject not in self._graph:
            self._graph.add_node(subject)
        if obj not in self._graph:
            self._graph.add_node(obj)
        self._graph.add_edge(subject, obj, predicate=predicate, **(properties or {}))
        self._save()

    def find_related(self, concept: str, predicate: str | None = None, direction: str = "both") -> list[tuple[str, str, str]]:
        """Find all relations involving a concept.

        Args:
            concept: The concept to search for.
            predicate: Optional filter by relation type.
            direction: "out" (outgoing), "in" (incoming), or "both".

        Returns:
            List of (subject, predicate, object) tuples.
        """
        if self._graph is None or concept not in self._graph:
            return []

        results: list[tuple[str, str, str]] = []

        if direction in ("out", "both"):
            for _, target, data in self._graph.out_edges(concept, data=True):
                pred = data.get("predicate", "related_to")
                if predicate is None or pred == predicate:
                    results.append((concept, pred, target))

        if direction in ("in", "both"):
            for source, _, data in self._graph.in_edges(concept, data=True):
                pred = data.get("predicate", "related_to")
                if predicate is None or pred == predicate:
                    results.append((source, pred, concept))

        return results

    def get_neighbors(self, concept: str, depth: int = 1) -> dict[str, dict[str, Any]]:
        """Get N-hop neighborhood subgraph as a dict of nodes + their properties."""
        if self._graph is None or concept not in self._graph:
            return {}

        visited: set[str] = set()
        queue = [(concept, 0)]
        result: dict[str, dict[str, Any]] = {}

        while queue:
            node, d = queue.pop(0)
            if node in visited or d > depth:
                continue
            visited.add(node)
            result[node] = dict(self._graph.nodes[node])

            if d < depth:
                for neighbor in self._graph.successors(node):
                    queue.append((neighbor, d + 1))
                for neighbor in self._graph.predecessors(node):
                    queue.append((neighbor, d + 1))

        return result

    # ── Bulk operations ──

    def extract_triplets_from_text(self, text: str, entities: list[str] | None = None) -> list[tuple[str, str, str]]:
        """Simple rule-based triplet extraction from text.

        Extracts (subject, verb/relation, object) patterns.
        For production, use LLM-based extraction.
        """
        triplets: list[tuple[str, str, str]] = []
        sentences = text.replace("\n", ". ").split(". ")

        for sentence in sentences:
            words = sentence.strip().split()
            if len(words) < 3:
                continue
            # Simple: look for "X is/are/has Y" patterns
            for i, w in enumerate(words):
                if w.lower() in ("is", "are", "has", "was", "were", "contains", "includes"):
                    subject = " ".join(words[:i])
                    predicate = w.lower()
                    obj = " ".join(words[i + 1:])
                    if subject and obj:
                        triplets.append((subject.strip(), predicate, obj.strip().rstrip(".")))
                        break

        return triplets

    def ingest_triplets(self, triplets: list[tuple[str, str, str]]) -> int:
        """Bulk-add a list of (subject, predicate, object) triplets."""
        count = 0
        for s, p, o in triplets:
            if s and p and o:
                self.add_relation(s, p, o)
                count += 1
        return count

    # ── Context export ──

    def to_context(self, concepts: list[str] | None = None) -> dict[str, Any]:
        """Export relevant semantic knowledge as context for agent state."""
        if self._graph is None or self._graph.number_of_nodes() == 0:
            return {}

        if concepts:
            parts = []
            for c in concepts:
                relations = self.find_related(c)
                for s, p, o in relations:
                    parts.append(f"{s} --{p}--> {o}")
                props = self.get_concept(c)
                if props:
                    parts.append(f"{c}: {props}")
            if not parts:
                return {}
            return {"semantic": "\n".join(parts[:20])}

        # No specific concepts — return a sample of the graph
        edges = list(self._graph.edges(data=True))[:15]
        if not edges:
            return {}

        lines = []
        for s, o, data in edges:
            pred = data.get("predicate", "related_to")
            lines.append(f"{s} --{pred}--> {o}")

        return {
            "semantic": "\n".join(lines),
            "graph_size": f"{self._graph.number_of_nodes()} nodes, {self._graph.number_of_edges()} edges",
        }

    @property
    def node_count(self) -> int:
        return self._graph.number_of_nodes() if self._graph else 0

    @property
    def edge_count(self) -> int:
        return self._graph.number_of_edges() if self._graph else 0
