"""Provider escalation -- re-explore thin branches with progressively stronger models.

Tier 0: Ollama     (local, litellm)
Tier 1: ZAI        (API key, litellm with z.ai endpoint, glm-5.1)
Tier 2: Gemini     (OAuth, shells out to `gemini -p`)
Tier 3: Claude     (OAuth, shells out to `claude -p`)
"""

import json
import os
import subprocess
import sys
from typing import Optional

from .models import PossibilityNode, ExplorationConfig
from .explorer import PossibilityExplorer
from .llm import LLMClient, parse_json_response
from .scorer import compute_fertility


DEFAULT_TIERS = [
    {
        "provider": "ollama",
        "model": "ollama/qwen2.5-coder:14b",
        "label": "Ollama 14B (local, free)",
        "auth": "local",
        "backend": "litellm",
    },
    {
        "provider": "zai",
        "model": "openai/glm-5.1",
        "label": "ZAI glm-5.1 (API)",
        "auth": "api_key",
        "backend": "litellm",
        "env_key": "ZAI_API_KEY",
        "api_base": "https://api.z.ai/api/coding/paas/v4",
    },
    {
        "provider": "gemini",
        "model": "gemini-2.5-flash",
        "label": "Gemini (OAuth)",
        "auth": "oauth",
        "backend": "cli",
        "cli_cmd": "gemini",
    },
    {
        "provider": "claude",
        "model": "claude-sonnet-4-20250514",
        "label": "Claude (OAuth)",
        "auth": "oauth",
        "backend": "cli",
        "cli_cmd": "claude",
    },
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
                    for var in list(need):
                        if line.startswith(f"export {var}="):
                            val = line.split("=", 1)[1].strip().strip('"').strip("'")
                            os.environ[var] = val
                            need.remove(var)
                            break

    os.environ["_POSSIBILITIES_KEYS_LOADED"] = "1"


def _check_available(tier: dict) -> bool:
    """Check if a tier's provider is actually available."""
    if tier["backend"] == "litellm" and tier["auth"] == "local":
        # Ollama -- just check if it's running
        try:
            subprocess.run(
                ["curl", "-s", "http://localhost:11434/api/tags"],
                capture_output=True, timeout=5,
            )
            return True
        except Exception:
            return False

    elif tier["backend"] == "litellm" and tier["auth"] == "api_key":
        _ensure_api_keys()
        return bool(os.environ.get(tier.get("env_key", "")))

    elif tier["backend"] == "cli" and tier["auth"] == "oauth":
        cli = tier.get("cli_cmd", "")
        try:
            result = subprocess.run(
                ["which", cli], capture_output=True, timeout=5,
            )
            return result.returncode == 0
        except Exception:
            return False

    return False


def _generate_with_cli(tier: dict, prompt: str) -> list[dict]:
    """Generate via CLI tool (gemini or claude) using non-interactive mode."""
    cli_cmd = tier["cli_cmd"]

    if cli_cmd == "gemini":
        result = subprocess.run(
            ["gemini", "-p", prompt, "--sandbox"],
            capture_output=True, text=True, timeout=120,
        )
        output = result.stdout
    elif cli_cmd == "claude":
        result = subprocess.run(
            ["claude", "-p", prompt, "--dangerously-skip-permissions"],
            capture_output=True, text=True, timeout=120,
        )
        output = result.stdout
    else:
        return []

    return parse_json_response(output)


def _generate_with_litellm(tier: dict, prompt: str) -> list[dict]:
    """Generate via litellm (ollama or zai)."""
    kwargs = dict(
        model=tier["model"],
        messages=[{"role": "user", "content": prompt}],
        temperature=0.9,
        max_tokens=3000,
    )

    if tier["provider"] == "ollama":
        kwargs["api_base"] = "http://localhost:11434"
    elif tier["auth"] == "api_key":
        _ensure_api_keys()
        api_key = os.environ.get(tier.get("env_key", ""))
        if api_key:
            kwargs["api_key"] = api_key
        if tier.get("api_base"):
            kwargs["api_base"] = tier["api_base"]

    import litellm
    resp = litellm.completion(**kwargs)
    raw = resp.choices[0].message.content
    return parse_json_response(raw)


def generate_for_tier(tier: dict, prompt: str) -> list[dict]:
    """Generate branches using whichever backend the tier specifies."""
    if tier["backend"] == "cli":
        return _generate_with_cli(tier, prompt)
    else:
        return _generate_with_litellm(tier, prompt)


def _get_tier_for_model(model: str) -> Optional[int]:
    """Find which tier index a model corresponds to."""
    for i, tier in enumerate(DEFAULT_TIERS):
        if tier["model"] == model:
            return i
    return None


def find_thin_nodes(
    tree: PossibilityNode,
    min_children: int = 2,
) -> list[PossibilityNode]:
    """Find nodes that could benefit from re-exploration.

    A node is "thin" if it's been explored but has fewer than
    min_children non-pruned children.
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
    max_tiers: int = 3,
    min_children: int = 2,
    decay: float = 0.7,
) -> PossibilityNode:
    """Re-explore thin branches with progressively stronger models.

    Args:
        tree: Existing tree to improve.
        current_model: Model that was used for the initial exploration.
        project_path: Project directory for context.
        max_tiers: How many tiers to escalate (default 3 = try all stronger models).
        min_children: Nodes with fewer non-pruned children are "thin".
        decay: Fertility decay factor.

    Returns:
        The tree with expanded branches from stronger models.
    """
    _ensure_api_keys()

    # Find starting tier
    start_idx = _get_tier_for_model(current_model)
    if start_idx is None:
        start_idx = 0

    # Build escalation chain, skipping unavailable tiers
    candidate_tiers = DEFAULT_TIERS[start_idx + 1 : start_idx + 1 + max_tiers]
    tiers_to_try = []
    for t in candidate_tiers:
        if _check_available(t):
            tiers_to_try.append(t)
        else:
            print(f"  Skipping {t['label']}: not available ({t['auth']})")

    if not tiers_to_try:
        print("  No stronger tiers available. Install or auth a provider.")
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

        # Get project context (same for all nodes in this tier)
        from .context import gather_project_context
        project_context = gather_project_context(project_path)

        # Re-explore each thin node
        improved = 0
        for node in thin:
            node.explored = False
            node.children = []

            try:
                from .prompts import BRANCH_PROMPT, get_depth_guidance
                prompt = BRANCH_PROMPT.format(
                    project_context=project_context,
                    seed_question=node.description or node.title,
                    depth=node.depth,
                    depth_guidance=get_depth_guidance(node.depth),
                    n_min=3,
                    n_max=7,
                )
                branches_raw = generate_for_tier(tier, prompt)
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
                            model_used=f"{tier['provider']}/{tier['model']}",
                        )
                        node.children.append(child)
                    improved += 1
                    print(f"      + {node.title}: {len(node.children)} new branches")
                else:
                    print(f"      [-] {node.title}: no valid branches returned")
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
