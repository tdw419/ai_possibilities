"""Provider escalation -- re-explore thin branches with progressively stronger models."""

import json
import os
import sys
from typing import Optional

from .models import PossibilityNode, ExplorationConfig
from .explorer import PossibilityExplorer
from .llm import LLMClient
from .scorer import compute_fertility
from .render import render_tree


# Default escalation tiers (weakest to strongest)
DEFAULT_TIERS = [
    {"provider": "ollama", "model": "ollama/qwen2.5-coder:14b", "label": "Ollama 14B (local, fast)"},
    {"provider": "ollama", "model": "ollama/qwen3.5-27b:latest", "label": "Ollama 27B (local, strong)"},
    {"provider": "gemini", "model": "gemini/gemini-2.5-flash", "label": "Gemini Flash (API, cheap)"},
    {"provider": "anthropic", "model": "anthropic/claude-sonnet-4-20250514", "label": "Claude Sonnet (API, strongest)"},
]


def _ensure_api_keys():
    """Load API keys from .bashrc if not already in env."""
    if os.environ.get("_POSSIBILITIES_KEYS_LOADED"):
        return

    key_vars = ["GEMINI_API_KEY", "ZAI_API_KEY", "ANTHROPIC_API_KEY"]
    need = [k for k in key_vars if not os.environ.get(k)]

    if need:
        bashrc = os.path.expanduser("~/.bashrc")
        if os.path.exists(bashrc):
            with open(bashrc) as f:
                for line in f:
                    line = line.strip()
                    for var in need:
                        if line.startswith(f"export {var}="):
                            # extract value between quotes
                            val = line.split("=", 1)[1].strip().strip('"').strip("'")
                            os.environ[var] = val
                            need.remove(var)
                            break

    os.environ["_POSSIBILITIES_KEYS_LOADED"] = "1"


def _get_tier_for_model(model: str) -> Optional[int]:
    """Find which tier index a model corresponds to."""
    for i, tier in enumerate(DEFAULT_TIERS):
        if tier["model"] == model:
            return i
    return None


def find_thin_nodes(
    tree: PossibilityNode,
    min_children: int = 2,
    min_fertility: float = 1.0,
) -> list[PossibilityNode]:
    """Find nodes that could benefit from re-exploration.

    A node is "thin" if:
    - It's a leaf (0 children) and not at max depth, OR
    - It has fewer than min_children, OR
    - Its fertility is below min_fertility and it's not a leaf
    """
    thin = []

    def walk(node: PossibilityNode):
        if node.pruned or node.depth == 0:
            pass  # skip root and pruned
        elif not node.children and not node.explored:
            thin.append(node)  # unexplored leaf
        elif node.explored and len([c for c in node.children if not c.pruned]) < min_children:
            thin.append(node)  # too few branches
        for child in node.children:
            walk(child)

    walk(tree)
    return thin


def escalate(
    tree: PossibilityNode,
    current_model: str = "ollama/qwen2.5-coder:14b",
    project_path: str = ".",
    max_tiers: int = 2,
    min_children: int = 2,
    decay: float = 0.7,
) -> PossibilityNode:
    """Re-explore thin branches with progressively stronger models.

    Args:
        tree: Existing tree to improve.
        current_model: Model that was used for the initial exploration.
        project_path: Project directory for context.
        max_tiers: How many tiers to escalate (default 2 = try 2 stronger models).
        min_children: Nodes with fewer non-pruned children are "thin".
        decay: Fertility decay factor.

    Returns:
        The tree with expanded branches from stronger models.
    """
    _ensure_api_keys()

    # Find starting tier
    start_idx = _get_tier_for_model(current_model)
    if start_idx is None:
        start_idx = 0  # unknown model, start from tier 0

    # Build escalation chain from current tier upward
    tiers_to_try = DEFAULT_TIERS[start_idx + 1 : start_idx + 1 + max_tiers]

    if not tiers_to_try:
        print("  Already at strongest tier, no escalation possible.")
        return tree

    # Initial score
    compute_fertility(tree, decay)
    prev_fertility = tree.fertility_score

    print(f"  Current fertility: {prev_fertility:.1f}")
    print(f"  Escalation chain: {' -> '.join(t['label'] for t in tiers_to_try)}")
    print()

    for tier_idx, tier in enumerate(tiers_to_try):
        # Find thin nodes
        thin = find_thin_nodes(tree, min_children=min_children)
        if not thin:
            print(f"  Tier {tier_idx + 1}: No thin nodes found. Tree is healthy.")
            break

        print(f"  Tier {tier_idx + 1}: {tier['label']}")
        print(f"    Found {len(thin)} thin nodes, re-exploring...")

        # Re-explore each thin node with stronger model
        improved = 0
        for node in thin:
            node.explored = False  # allow re-exploration
            node.children = []     # clear old children

            config = ExplorationConfig(
                seed_question=node.description or node.title,
                project_path=project_path,
                model=tier["model"],
                max_depth=1,         # only expand this one node
                branch_min=3,
                branch_max=7,
                max_nodes=len(thin) * 7,  # enough headroom
                temperature=0.9,
            )

            explorer = PossibilityExplorer(config)
            explorer.root = node
            # Just generate branches for this node, not recursive
            try:
                from .prompts import BRANCH_PROMPT, get_depth_guidance
                prompt = BRANCH_PROMPT.format(
                    project_context=explorer.project_context,
                    seed_question=node.description or node.title,
                    depth=node.depth,
                    depth_guidance=get_depth_guidance(node.depth),
                    n_min=config.branch_min,
                    n_max=config.branch_max,
                )
                branches_raw = explorer.llm.generate_json(prompt)
                if branches_raw:
                    for bd in branches_raw:
                        child = PossibilityNode(
                            title=bd.get("title", "Untitled"),
                            description=bd.get("description", ""),
                            enables=bd.get("enables", []),
                            risk=bd.get("risk", ""),
                            category=bd.get("category", ""),
                            depth=node.depth + 1,
                            parent_id=node.id,
                            model_used=tier["model"],
                        )
                        node.children.append(child)
                    improved += 1
                    print(f"      + {node.title}: {len(node.children)} new branches")
                else:
                    print(f"      [-] {node.title}: model returned no valid branches")
            except Exception as e:
                print(f"      [!] {node.title}: {e}")

            node.explored = True

        print(f"    Improved {improved}/{len(thin)} nodes")

        # Re-score
        compute_fertility(tree, decay)
        new_fertility = tree.fertility_score
        delta = new_fertility - prev_fertility

        print(f"    Fertility: {prev_fertility:.1f} -> {new_fertility:.1f} ({'+' if delta >= 0 else ''}{delta:.1f})")
        print()

        if delta < 0.5 and tier_idx > 0:
            print("  Fertility plateau reached, stopping escalation.")
            break

        prev_fertility = new_fertility

    return tree
