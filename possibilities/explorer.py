"""Core exploration engine -- BFS/fertility-guided tree builder."""

import json
import sys
from .models import PossibilityNode, ExplorationConfig
from .llm import LLMClient
from .dedup import Deduplicator
from .context import gather_project_context
from .prompts import BRANCH_PROMPT, get_depth_guidance
from .scorer import compute_fertility


class PossibilityExplorer:
    """Explores a possibility tree using an LLM to generate branches."""

    def __init__(self, config: ExplorationConfig):
        self.config = config
        self.llm = LLMClient(config.model, config.temperature)
        self.deduper = Deduplicator(self.llm, config.dedup_threshold)
        self.root = PossibilityNode(
            title="Root",
            description=config.seed_question,
        )
        self.project_context = gather_project_context(
            config.project_path, config.context_files
        )

    def explore(self) -> PossibilityNode:
        """Run the exploration and return the built tree."""
        frontier = [self.root]
        explored_count = 0

        while frontier and self._count_nodes() < self.config.max_nodes:
            # Sort frontier by strategy
            if self.config.explore_strategy == "fertility_guided":
                compute_fertility(self.root, self.config.decay)
                frontier.sort(key=lambda n: n.fertility_score, reverse=True)

            node = frontier.pop(0)

            if node.depth >= self.config.max_depth:
                continue

            if node.pruned:
                continue

            # Generate branches
            prompt = BRANCH_PROMPT.format(
                project_context=self.project_context,
                seed_question=node.description or node.title,
                depth=node.depth,
                depth_guidance=get_depth_guidance(node.depth),
                n_min=self.config.branch_min,
                n_max=self.config.branch_max,
            )

            print(
                f"  Exploring depth {node.depth}: "
                f"\"{node.title or node.description[:50]}...\""
            )
            sys.stdout.flush()

            try:
                branches_raw = self.llm.generate_json(prompt)
            except Exception as e:
                print(f"    [!] LLM error: {e}")
                node.explored = True
                continue

            if not branches_raw:
                print("    [!] No valid branches returned")
                node.explored = True
                continue

            existing_ideas = self._all_ideas()

            for branch_data in branches_raw:
                branch = PossibilityNode(
                    title=branch_data.get("title", "Untitled"),
                    description=branch_data.get("description", ""),
                    enables=branch_data.get("enables", []),
                    risk=branch_data.get("risk", ""),
                    category=branch_data.get("category", ""),
                    depth=node.depth + 1,
                    parent_id=node.id,
                    model_used=self.config.model,
                )

                # Dedup check
                dup = self.deduper.check(branch, existing_ideas)
                if dup.is_duplicate:
                    branch.pruned = True
                    branch.prune_reason = f"Duplicate of: {dup.duplicate_of}"
                    print(f"    [pruned] {branch.title} (dup of {dup.duplicate_of})")
                else:
                    frontier.append(branch)
                    existing_ideas.append(
                        {"title": branch.title, "description": branch.description}
                    )
                    print(f"    + {branch.title} [{branch.category}]")

                node.children.append(branch)

            node.explored = True
            explored_count += 1
            sys.stdout.flush()

        # Final scoring pass
        compute_fertility(self.root, self.config.decay)
        print(f"\n  Explored {explored_count} nodes, {self._count_nodes()} total")
        return self.root

    def resume(self, existing_tree: PossibilityNode) -> PossibilityNode:
        """Continue exploring an existing tree."""
        self.root = existing_tree

        # Find unexplored frontier nodes
        frontier = []
        def find_frontier(node: PossibilityNode):
            if not node.explored and not node.pruned and node.depth < self.config.max_depth:
                frontier.append(node)
            for child in node.children:
                find_frontier(child)

        find_frontier(self.root)
        return self.explore()

    def _count_nodes(self) -> int:
        count = 0
        def walk(n: PossibilityNode):
            nonlocal count
            count += 1
            for c in n.children:
                walk(c)
        walk(self.root)
        return count

    def _all_ideas(self) -> list[dict]:
        ideas = []
        def walk(n: PossibilityNode):
            ideas.append({"title": n.title, "description": n.description})
            for c in n.children:
                walk(c)
        walk(self.root)
        return ideas
