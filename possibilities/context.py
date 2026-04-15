"""Project context gathering for grounding LLM suggestions."""

import os
from pathlib import Path
from collections import Counter


CONTEXT_FILENAMES = [
    "README.md", "README", "README.txt",
    "package.json", "pyproject.toml", "Cargo.toml", "go.mod",
    "Makefile", "docker-compose.yml", "Dockerfile",
    "CHANGELOG.md", "CONTRIBUTING.md",
    "AI_GUIDE.md",
]

SKIP_DIRS = {
    ".git", "node_modules", "__pycache__", ".tox", "venv", ".venv",
    "target", "build", "dist", ".mypy_cache", ".pytest_cache",
    "egg-info", ".eggs",
}


def gather_project_context(
    project_path: str, extra_files: list[str] = None
) -> str:
    """Build a compact project summary for the LLM prompt."""
    parts = []
    root = Path(project_path).resolve()

    if not root.exists():
        return "(No project directory specified or found)"

    # 1. Key config/readme files (most valuable signal)
    for fname in CONTEXT_FILENAMES:
        fpath = root / fname
        if fpath.exists() and fpath.is_file() and fpath.stat().st_size < 20000:
            content = fpath.read_text(errors="replace")[:3000]
            parts.append(f"=== {fname} ===\n{content}")

    # 2. User-specified files
    for f in extra_files or []:
        fpath = root / f
        if fpath.exists() and fpath.is_file() and fpath.stat().st_size < 20000:
            content = fpath.read_text(errors="replace")[:3000]
            parts.append(f"=== {f} ===\n{content}")

    # 3. Directory structure (top 3 levels)
    structure = build_dir_tree(root, max_depth=3)
    if structure:
        parts.append(f"=== Directory Structure ===\n{structure}")

    # 4. File extension census
    exts = count_extensions(root)
    if exts:
        ext_summary = ", ".join(
            f".{ext}: {cnt}" for ext, cnt in exts.most_common(15)
        )
        parts.append(f"=== File Types ===\n{ext_summary}")

    if not parts:
        return f"(Empty or unrecognized project at {root})"

    return "\n\n".join(parts)


def build_dir_tree(
    path: Path, max_depth: int = 3, prefix: str = "", depth: int = 0
) -> str:
    """ASCII directory tree, skipping noise dirs."""
    if depth >= max_depth:
        return ""

    lines = []
    try:
        entries = sorted(path.iterdir(), key=lambda e: (not e.is_dir(), e.name))
    except (PermissionError, OSError):
        return ""

    entries = [
        e for e in entries
        if e.name not in SKIP_DIRS and not e.name.startswith(".")
    ]

    capped = entries[:30]
    for i, entry in enumerate(capped):
        is_last = i == len(capped) - 1
        connector = "--- " if is_last else "|-- "
        lines.append(f"{prefix}{connector}{entry.name}")
        if entry.is_dir():
            extension = "    " if is_last else "|   "
            sub = build_dir_tree(entry, max_depth, prefix + extension, depth + 1)
            if sub:
                lines.append(sub)

    return "\n".join(lines)


def count_extensions(root: Path) -> Counter:
    """Count file extensions in the project."""
    exts = Counter()
    try:
        for dirpath, dirnames, filenames in os.walk(root):
            # Prune skip dirs in-place
            dirnames[:] = [
                d for d in dirnames
                if d not in SKIP_DIRS and not d.startswith(".")
            ]
            for fname in filenames:
                ext = Path(fname).suffix.lstrip(".")
                if ext:
                    exts[ext] += 1
    except (PermissionError, OSError):
        pass
    return exts
