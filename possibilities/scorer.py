"""Fertility scoring and path ranking for the possibility tree."""

from typing import Optional
from .models import PossibilityNode


def compute_fertility(node: PossibilityNode, decay: float = 0.7) -> float:
    """
    Compute fertility score for a node and all its descendants.

    Fertility = how many doors this idea opens, weighted toward near-term.
    Leaf: 0 (dead end, no branching)
    Branch: sum over children of (1 + decay * child_fertility)

    Deeper branching cascades score higher. That's the point.
    """
    if not node.children:
        node.fertility_score = 0.0
        node.direct_fertility = 0
        node.total_descendants = 0
        return 0.0

    child_fertilities = []
    for child in node.children:
        if child.pruned:
            continue
        cf = compute_fertility(child, decay)
        child_fertilities.append(cf)

    if not child_fertilities:
        node.fertility_score = 0.0
        node.direct_fertility = 0
        node.total_descendants = 0
        return 0.0

    node.direct_fertility = len([c for c in node.children if not c.pruned])
    node.total_descendants = sum(
        c.total_descendants for c in node.children if not c.pruned
    ) + node.direct_fertility

    node.fertility_score = sum(
        1.0 + decay * cf for cf in child_fertilities
    )
    return node.fertility_score


def rank_paths(
    tree: PossibilityNode, top_n: int = 10
) -> list[tuple[float, list[PossibilityNode]]]:
    """
    Find root-to-leaf paths, score each by cumulative fertility.
    Returns top N paths ranked highest.
    """
    paths = []

    def dfs(node: PossibilityNode, path: list, score: float):
        path.append(node)
        visible_children = [c for c in node.children if not c.pruned]
        if not visible_children:
            # Leaf node -- this is a complete path
            paths.append((score, list(path)))
        else:
            for child in visible_children:
                dfs(child, path, score + child.fertility_score)
        path.pop()

    dfs(tree, [], tree.fertility_score)
    paths.sort(key=lambda x: x[0], reverse=True)
    return paths[:top_n]


def most_fertile_frontier(tree: PossibilityNode) -> Optional[PossibilityNode]:
    """Find the highest-fertility unexplored node (for guided exploration)."""
    best = None
    best_score = -1

    def walk(node: PossibilityNode):
        nonlocal best, best_score
        if not node.explored and not node.pruned and node.fertility_score > best_score:
            best = node
            best_score = node.fertility_score
        for child in node.children:
            walk(child)

    walk(tree)
    return best
