"""CLI for the possibility tree explorer."""

import argparse
import json
import sys

from .models import PossibilityNode, ExplorationConfig
from .explorer import PossibilityExplorer
from .scorer import compute_fertility, rank_paths
from .render import render_tree, render_ranked_paths, render_summary


def parse_args(argv=None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="possibilities",
        description="Explore branching possibilities for any project using AI.",
    )
    subparsers = parser.add_subparsers(dest="command")

    # explore
    explore_p = subparsers.add_parser(
        "explore", help="Explore possibilities from a seed question"
    )
    explore_p.add_argument(
        "question", help="Seed question (e.g. 'What should we build next?')"
    )
    explore_p.add_argument(
        "-w", "--workdir", default=".",
        help="Project directory to read for context"
    )
    explore_p.add_argument(
        "-d", "--depth", type=int, default=3,
        help="Max exploration depth (default: 3)"
    )
    explore_p.add_argument(
        "--branch-min", type=int, default=3,
        help="Min branches per node (default: 3)"
    )
    explore_p.add_argument(
        "--branch-max", type=int, default=7,
        help="Max branches per node (default: 7)"
    )
    explore_p.add_argument(
        "-m", "--model", default="ollama/qwen2.5-coder:14b",
        help="LLM model to use (default: ollama/qwen2.5-coder:14b)"
    )
    explore_p.add_argument(
        "--decay", type=float, default=0.7,
        help="Fertility decay factor (default: 0.7)"
    )
    explore_p.add_argument(
        "--max-nodes", type=int, default=80,
        help="Max total nodes in tree (default: 80)"
    )
    explore_p.add_argument(
        "-s", "--strategy", default="bfs",
        choices=["bfs", "fertility_guided"],
        help="Exploration strategy (default: bfs)"
    )
    explore_p.add_argument(
        "--context-files", nargs="*", default=[],
        help="Extra files to include as context"
    )
    explore_p.add_argument(
        "--temperature", type=float, default=0.9,
        help="LLM temperature (default: 0.9)"
    )
    explore_p.add_argument(
        "--show-paths", type=int, default=10,
        help="Number of ranked paths to show (default: 10)"
    )
    explore_p.add_argument(
        "-o", "--export", default=None,
        help="Export tree to JSON file"
    )
    explore_p.add_argument(
        "--show-pruned", action="store_true",
        help="Show pruned (duplicate) nodes in tree"
    )

    # show
    show_p = subparsers.add_parser(
        "show", help="Display a saved tree"
    )
    show_p.add_argument("file", help="JSON file with saved tree")
    show_p.add_argument(
        "--top", type=int, default=10,
        help="Number of ranked paths to show"
    )
    show_p.add_argument(
        "--show-pruned", action="store_true",
        help="Show pruned nodes"
    )

    # resume
    resume_p = subparsers.add_parser(
        "resume", help="Continue exploring an existing tree"
    )
    resume_p.add_argument("file", help="JSON file with saved tree")
    resume_p.add_argument(
        "-d", "--depth", type=int, default=None,
        help="New max depth (default: keep existing)"
    )
    resume_p.add_argument(
        "--max-nodes", type=int, default=None,
        help="New max nodes limit"
    )
    resume_p.add_argument(
        "-m", "--model", default=None,
        help="LLM model override"
    )
    resume_p.add_argument(
        "-o", "--export", default=None,
        help="Export updated tree to file"
    )
    resume_p.add_argument(
        "--show-paths", type=int, default=10,
        help="Number of ranked paths to show"
    )

    return parser.parse_args(argv)


def cmd_explore(args: argparse.Namespace):
    config = ExplorationConfig(
        seed_question=args.question,
        project_path=args.workdir,
        max_depth=args.depth,
        branch_min=args.branch_min,
        branch_max=args.branch_max,
        model=args.model,
        decay=args.decay,
        max_nodes=args.max_nodes,
        explore_strategy=args.strategy,
        context_files=args.context_files,
        temperature=args.temperature,
        show_paths=args.show_paths,
    )

    print(f"Possibility Explorer")
    print(f"  Question: {config.seed_question}")
    print(f"  Project:  {config.project_path}")
    print(f"  Model:    {config.model}")
    print(f"  Depth:    {config.max_depth}")
    print(f"  Strategy: {config.explore_strategy}")
    print()

    explorer = PossibilityExplorer(config)
    tree = explorer.explore()

    # Output
    print("\n" + "=" * 60)
    print(render_tree(tree, show_pruned=args.show_pruned))
    print(render_summary(tree))

    paths = rank_paths(tree, top_n=config.show_paths)
    print(render_ranked_paths(paths))

    if args.export:
        with open(args.export, "w") as f:
            json.dump(tree.to_dict(), f, indent=2)
        print(f"\nTree saved to {args.export}")


def cmd_show(args: argparse.Namespace):
    with open(args.file) as f:
        data = json.load(f)
    tree = PossibilityNode.from_dict(data)
    compute_fertility(tree)

    print(render_tree(tree, show_pruned=args.show_pruned))
    print(render_summary(tree))

    if args.top:
        paths = rank_paths(tree, top_n=args.top)
        print(render_ranked_paths(paths))


def cmd_resume(args: argparse.Namespace):
    with open(args.file) as f:
        data = json.load(f)
    tree = PossibilityNode.from_dict(data)

    # Build config, keeping existing depth unless overridden
    config = ExplorationConfig(
        seed_question=tree.description,
        model=args.model or "ollama/qwen2.5-coder:14b",
        max_depth=args.depth or 3,
        max_nodes=args.max_nodes or 120,
        explore_strategy="bfs",
    )

    print(f"Resuming exploration of: \"{tree.description}\"")
    print(f"  Model: {config.model}")
    print(f"  Max depth: {config.max_depth}")
    print()

    explorer = PossibilityExplorer(config)
    tree = explorer.resume(tree)

    print("\n" + "=" * 60)
    print(render_tree(tree))

    paths = rank_paths(tree, top_n=args.show_paths)
    print(render_ranked_paths(paths))

    if args.export:
        with open(args.export, "w") as f:
            json.dump(tree.to_dict(), f, indent=2)
        print(f"\nTree saved to {args.export}")
    else:
        # Auto-save back to the same file
        with open(args.file, "w") as f:
            json.dump(tree.to_dict(), f, indent=2)
        print(f"\nTree updated in {args.file}")


def main(argv=None):
    args = parse_args(argv)

    if args.command == "explore":
        cmd_explore(args)
    elif args.command == "show":
        cmd_show(args)
    elif args.command == "resume":
        cmd_resume(args)
    else:
        parse_args(["--help"])


if __name__ == "__main__":
    main()
