"""Data models for the possibility tree explorer."""

import uuid
import time
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class PossibilityNode:
    """A single node in the possibility tree."""
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])
    title: str = ""
    description: str = ""
    enables: list[str] = field(default_factory=list)
    risk: str = ""
    category: str = ""  # obvious | contrarian | wildcard | foundational
    depth: int = 0
    parent_id: Optional[str] = None
    children: list["PossibilityNode"] = field(default_factory=list)

    # Scoring (filled by scorer)
    fertility_score: float = 0.0
    direct_fertility: int = 0
    total_descendants: int = 0

    # Metadata
    model_used: str = ""
    explored: bool = False
    pruned: bool = False
    prune_reason: str = ""
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        """Serialize to dict for JSON export."""
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "enables": self.enables,
            "risk": self.risk,
            "category": self.category,
            "depth": self.depth,
            "parent_id": self.parent_id,
            "children": [c.to_dict() for c in self.children],
            "fertility_score": self.fertility_score,
            "direct_fertility": self.direct_fertility,
            "total_descendants": self.total_descendants,
            "model_used": self.model_used,
            "explored": self.explored,
            "pruned": self.pruned,
            "prune_reason": self.prune_reason,
            "created_at": self.created_at,
        }

    @staticmethod
    def from_dict(d: dict) -> "PossibilityNode":
        """Deserialize from dict."""
        children = [PossibilityNode.from_dict(c) for c in d.get("children", [])]
        return PossibilityNode(
            id=d.get("id", uuid.uuid4().hex[:8]),
            title=d.get("title", ""),
            description=d.get("description", ""),
            enables=d.get("enables", []),
            risk=d.get("risk", ""),
            category=d.get("category", ""),
            depth=d.get("depth", 0),
            parent_id=d.get("parent_id"),
            children=children,
            fertility_score=d.get("fertility_score", 0.0),
            direct_fertility=d.get("direct_fertility", 0),
            total_descendants=d.get("total_descendants", 0),
            model_used=d.get("model_used", ""),
            explored=d.get("explored", False),
            pruned=d.get("pruned", False),
            prune_reason=d.get("prune_reason", ""),
            created_at=d.get("created_at", time.time()),
        )


@dataclass
class ExplorationConfig:
    """Configuration for an exploration run."""
    seed_question: str = "What should we build next?"
    project_path: str = "."
    max_depth: int = 3
    branch_min: int = 3
    branch_max: int = 7
    model: str = "openai/glm-5.1"
    decay: float = 0.7
    dedup_threshold: float = 0.85
    max_nodes: int = 80
    explore_strategy: str = "bfs"  # bfs | fertility_guided
    context_files: list[str] = field(default_factory=list)
    temperature: float = 0.9
    show_paths: int = 10
