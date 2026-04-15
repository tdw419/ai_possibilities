"""ASCII tree and ranked paths rendering."""

from .models import PossibilityNode


def render_tree(
    node: PossibilityNode,
    prefix: str = "",
    is_last: bool = True,
    show_pruned: bool = False,
) -> str:
    """Render the possibility tree as ASCII art."""
    lines = []

    # Node label
    if node.depth == 0:
        label = f'[Root] "{node.description}" (fertility: {node.fertility_score:.1f})'
    elif node.pruned:
        if not show_pruned:
            return ""
        label = f"[PRUNED] {node.title} -- {node.prune_reason}"
    else:
        cat = f"({node.category})" if node.category else ""
        enables_str = f" [enables: {len(node.enables)}]" if node.enables else ""
        label = f"[{node.fertility_score:.1f}] {node.title} {cat}{enables_str}"

    if node.depth == 0:
        lines.append(label)
    else:
        connector = "--- " if is_last else "|-- "
        lines.append(f"{prefix}{connector}{label}")

    # Children
    if node.depth == 0:
        child_prefix = ""
    else:
        child_prefix = prefix + ("    " if is_last else "|   ")

    visible = [
        c for c in node.children
        if show_pruned or not c.pruned
    ]

    for i, child in enumerate(visible):
        last = i == len(visible) - 1
        child_rendered = render_tree(child, child_prefix, last, show_pruned)
        if child_rendered:
            lines.append(child_rendered)

    return "\n".join(lines)


def render_ranked_paths(
    paths: list[tuple[float, list[PossibilityNode]]],
) -> str:
    """Render ranked paths from root to most fertile leaves."""
    lines = ["", "RANKED PATHS (most to least fertile):", ""]

    for rank, (score, path) in enumerate(paths, 1):
        path_parts = []
        for n in path:
            if n.depth == 0:
                path_parts.append(n.description[:50])
            else:
                path_parts.append(n.title)
        path_str = " -> ".join(path_parts)
        lines.append(f"  #{rank} [score: {score:.1f}] {path_str}")

    return "\n".join(lines)


def render_summary(tree: PossibilityNode) -> str:
    """Render a summary of the exploration."""
    total = 0
    pruned = 0
    explored = 0
    max_depth = 0

    def walk(node: PossibilityNode):
        nonlocal total, pruned, explored, max_depth
        total += 1
        if node.pruned:
            pruned += 1
        if node.explored:
            explored += 1
        if node.depth > max_depth:
            max_depth = node.depth
        for c in node.children:
            walk(c)

    walk(tree)

    lines = [
        "",
        "EXPLORATION SUMMARY:",
        f"  Total nodes:    {total}",
        f"  Explored:       {explored}",
        f"  Pruned (dupes): {pruned}",
        f"  Max depth:      {max_depth}",
        f"  Root fertility: {tree.fertility_score:.1f}",
        f"  Descendants:    {tree.total_descendants}",
        "",
    ]
    return "\n".join(lines)
