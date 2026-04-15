"""Merge multiple possibility trees into one."""

import json
from typing import Optional

from .models import PossibilityNode
from .dedup import Deduplicator
from .llm import LLMClient
from .scorer import compute_fertility


def load_tree(path: str) -> PossibilityNode:
    """Load a tree from a JSON file."""
    with open(path) as f:
        data = json.load(f)
    return PossibilityNode.from_dict(data)


def _collect_all_nodes(node: PossibilityNode) -> list[PossibilityNode]:
    """Flatten a tree into a list of all nodes."""
    result = [node]
    for child in node.children:
        result.extend(_collect_all_nodes(child))
    return result


def _reparent_subtree(
    node: PossibilityNode,
    new_parent_id: str,
    new_depth: int,
):
    """Re-parent a node and adjust depth for its entire subtree."""
    node.parent_id = new_parent_id
    node.depth = new_depth
    for child in node.children:
        _reparent_subtree(child, node.id, new_depth + 1)


def _normalize_question(text: str) -> str:
    """Normalize a question for comparison."""
    t = text.lower().strip()
    if t.endswith("?"):
        t = t[:-1].strip()
    return t


def merge_trees(
    trees: list[PossibilityNode],
    dedup: bool = False,
    model: str = "ollama/qwen2.5-coder:14b",
    dedup_threshold: float = 0.85,
    decay: float = 0.7,
) -> PossibilityNode:
    """Merge two or more trees into a single unified tree.

    Strategy:
    - Create a synthetic root whose description describes the merge.
    - Group input trees by their root question. Trees with the same
      question have their depth-0 children merged under one node.
    - Different questions become separate children of the synthetic root.
    - Optionally dedup across all trees using LLM.
    - Re-score the combined tree.
    """
    if not trees:
        raise ValueError("Need at least one tree to merge")

    # Single tree -- just return it (re-scored)
    if len(trees) == 1:
        compute_fertility(trees[0], decay)
        return trees[0]

    # Group trees by normalized root question
    groups: dict[str, list[PossibilityNode]] = {}
    group_order: list[str] = []
    for tree in trees:
        key = _normalize_question(tree.description or tree.title)
        if key not in groups:
            groups[key] = []
            group_order.append(key)
        groups[key].append(tree)

    # Build merged root
    merged = PossibilityNode(
        title="Merged Exploration",
        description=" + ".join(
            t.description or t.title for t in trees
        ),
    )

    # For each group of same-question trees, collect their depth-0 children
    for key in group_order:
        group_trees = groups[key]

        if len(group_trees) == 1 and len(groups) == 1:
            # Only one question, only one tree group -- take children directly
            for tree in group_trees:
                for child in tree.children:
                    _reparent_subtree(child, merged.id, 1)
                    merged.children.append(child)
        else:
            # Multiple questions or multiple trees for same question
            # Create an intermediate node per question
            question_text = group_trees[0].description or group_trees[0].title
            intermediate = PossibilityNode(
                title=question_text[:80] if len(question_text) > 80 else question_text,
                description=question_text,
                category="merged",
                depth=1,
                parent_id=merged.id,
            )
            merged.children.append(intermediate)

            for tree in group_trees:
                for child in tree.children:
                    _reparent_subtree(child, intermediate.id, 2)
                    intermediate.children.append(child)

    # Cross-tree dedup if requested
    if dedup:
        llm = LLMClient(model)
        deduper = Deduplicator(llm, dedup_threshold)
        all_children = [c for c in merged.children]
        # Also collect grandchildren if intermediates were created
        for child in merged.children:
            all_children.extend(child.children)

        existing: list[dict] = []
        for node in all_children:
            dup = deduper.check(node, existing)
            if dup.is_duplicate:
                node.pruned = True
                node.prune_reason = f"Duplicate of: {dup.duplicate_of}"
            existing.append({"title": node.title, "description": node.description})

        print(f"  Dedup: pruned {sum(1 for n in all_children if n.pruned)} duplicates")

    # Re-score
    compute_fertility(merged, decay)
    return merged
