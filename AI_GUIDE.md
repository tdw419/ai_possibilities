# Possibilities -- AI Agent Guide

## What This Is

A CLI tool that explores branching possibilities for any project using an LLM. You give it a seed question, point it at a project directory, and it builds a tree of ideas ranked by "fertility" -- how many future doors each idea opens. Ideas that spawn more sub-possibilities score higher than dead-end ideas.

The tool is installed as `possibilities` and has 5 commands: `explore`, `show`, `resume`, `merge`, `escalate`.

## Quick Reference

```bash
# Install (editable)
cd ~/zion/projects/ai_possibilities/ai_possibilities
pip install -e . --break-system-packages

# Verify
possibilities --help
which possibilities

# Run an exploration
possibilities explore "What should we build next?" -w /path/to/project -d 2 -o tree.json

# View a saved tree
possibilities show tree.json --top 10

# Resume exploration on an existing tree (go deeper)
possibilities resume tree.json -d 4 -o tree_v2.json

# Re-explore thin branches with stronger models
possibilities escalate tree.json --max-tiers 2 -o tree_escalated.json

# Run with a specific model
possibilities explore "..." -m ollama/qwen3.5-27b:latest
possibilities explore "..." -m gpt-4o  # requires OPENAI_API_KEY
```

No test suite. No build step beyond `pip install -e .`.

## Architecture

```
~/zion/projects/ai_possibilities/ai_possibilities/
  possibilities/              # 1300+ lines, 13 files
    cli.py              396   # argparse CLI, 5 subcommands
    explorer.py         145   # BFS/fertility-guided tree builder
    merge.py            130   # Merge multiple trees, cross-tree dedup
    escalate.py         207   # Provider escalation for thin branches
    models.py            96   # PossibilityNode + ExplorationConfig dataclasses
    render.py           104   # ASCII tree + ranked paths + summary
    context.py          114   # Project context gathering (README, dir tree, file types)
    scorer.py            86   # Fertility scoring + path ranking
    llm.py               71   # litellm wrapper (Ollama, OpenAI, any litellm model)
    prompts.py           71   # BRANCH_PROMPT + DEDUP_PROMPT + depth guidance
    dedup.py             80   # Semantic deduplication (exact match + LLM check)
    __init__.py            4   # re-exports main classes
    __main__.py            4   # entry point for python -m possibilities
  pyproject.toml              # setuptools, litellm dependency, CLI entry point
  README.md                   # user-facing docs
  AI_GUIDE.md                 # this file -- agent-facing docs
```

Dependency: `litellm>=1.0` only. No other external deps. Uses `dataclasses`, `json`, `argparse`, `pathlib`, `uuid`, `os`, `re`, `time`, `collections.Counter` from stdlib.

## How to Run It

### explore (the main command)

```bash
possibilities explore "QUESTION" [options]
```

Required positional arg: the seed question (string).

Options (all optional):

| Flag | Short | Default | What it does |
|------|-------|---------|--------------|
| `--workdir` | `-w` | `.` | Project dir to read for context |
| `--depth` | `-d` | `3` | Max tree depth |
| `--branch-min` | | `3` | Min branches per node |
| `--branch-max` | | `7` | Max branches per node |
| `--model` | `-m` | `ollama/qwen2.5-coder:14b` | LLM model |
| `--decay` | | `0.7` | Fertility decay factor |
| `--max-nodes` | | `80` | Max total nodes before stopping |
| `--strategy` | `-s` | `bfs` | `bfs` or `fertility_guided` |
| `--context-files` | | | Extra file paths to include as context |
| `--temperature` | | `0.9` | LLM temperature |
| `--show-paths` | | `10` | Number of ranked paths to display |
| `--export` | `-o` | | JSON file to save the tree |
| `--show-pruned` | | off | Show duplicate/pruned nodes |

What happens step by step:
1. Reads project context from `--workdir`: README.md, pyproject.toml, Cargo.toml, AI_GUIDE.md, directory tree (3 levels), file extension census. Each file capped at 3000 chars.
2. Creates root PossibilityNode with the seed question.
3. BFS loop: pops a node from the frontier, sends BRANCH_PROMPT to the LLM, parses JSON response into child nodes.
4. Each child goes through dedup check (exact title match first, then LLM semantic check). Duplicates get `pruned=True`.
5. Non-pruned children go onto the frontier.
6. Loop ends when frontier is empty or `max_nodes` hit.
7. Final pass: `compute_fertility()` on the whole tree.
8. Prints ASCII tree, summary stats, ranked paths.
9. If `--export`, writes tree as JSON via `PossibilityNode.to_dict()`.

### show

```bash
possibilities show tree.json [--top N] [--show-pruned]
```

Loads a JSON tree, recomputes fertility scores, renders ASCII tree + ranked paths.

### resume

```bash
possibilities resume tree.json [-d 4] [--max-nodes 120] [-m model] [-o output.json]
```

Loads a saved tree, finds unexplored frontier nodes, continues the BFS loop. Writes back to the same file unless `--export` is specified.

### merge

```bash
possibilities merge tree_a.json tree_b.json -o combined.json [--dedup] [-m model]
```

Accepts 2+ JSON tree files. Combines them into a single unified tree.

Options:

| Flag | Short | Default | What it does |
|------|-------|---------|--------------|
| (positional) | | | Two or more tree JSON files |
| `--output` | `-o` | (required) | Output file for merged tree |
| `--dedup` | | off | Run cross-tree dedup (requires LLM) |
| `--model` | `-m` | `ollama/qwen2.5-coder:14b` | LLM for dedup |
| `--decay` | | `0.7` | Fertility decay factor |
| `--top` | | `10` | Number of ranked paths |
| `--show-pruned` | | off | Show pruned duplicates |

Merge strategy (in merge.py):
1. Groups input trees by root question (normalized: lowercase, stripped, trailing `?` removed).
2. If all trees share the same question, their depth-0 children are combined directly under a new synthetic root.
3. If trees have different questions, creates intermediate nodes per question, each containing that group's children (re-parented to depth 2).
4. If `--dedup`: runs Deduplicator across all children of the merged tree. Catches duplicates across different input trees (e.g. "Plugin system" in tree A and "Plugin system" in tree B get deduped).
5. Re-scores with compute_fertility().

Works without an LLM when `--dedup` is not set (pure tree surgery). With `--dedup`, instantiates an LLMClient for semantic similarity checks.

### escalate

```bash
possibilities escalate tree.json -w ./project --max-tiers 2 -o tree_v2.json
```

Takes an existing tree, finds "thin" branches (nodes with few children), and re-explores them with progressively stronger LLM models.

Options:

| Flag | Short | Default | What it does |
|------|-------|---------|--------------|
| (positional) | | | JSON tree file to improve |
| `--workdir` | `-w` | `.` | Project dir for context |
| `--current-model` | `-m` | `ollama/qwen2.5-coder:14b` | Model used for initial run |
| `--max-tiers` | | `2` | How many escalation steps |
| `--min-children` | | `2` | Nodes with fewer children are "thin" |
| `--decay` | | `0.7` | Fertility decay factor |
| `--output` | `-o` | (auto) | Output file |
| `--show-paths` | | `10` | Ranked paths to show |
| `--show-pruned` | | off | Show pruned nodes |

Default escalation chain (in escalate.py `DEFAULT_TIERS`):

| Tier | Provider | Model | Auth | Backend |
|------|----------|-------|------|---------|
| 0 | Ollama | qwen2.5-coder:14b | local | litellm |
| 1 | ZAI | glm-5.1 | API key | litellm (z.ai endpoint) |
| 2 | Gemini | gemini-2.5-flash | OAuth | `gemini -p` CLI |
| 3 | Claude | claude-sonnet-4 | OAuth | `claude -p` CLI |

ZAI uses the OpenAI-compatible endpoint at `https://api.z.ai/api/coding/paas/v4` with `ZAI_API_KEY` from env (loaded from `~/.bashrc`). Available models: glm-4.5, glm-4.6, glm-4.7, glm-5, glm-5-turbo, glm-5.1.

Gemini and Claude use their CLI tools in non-interactive mode (`gemini -p "..." --sandbox` and `claude -p "..." --dangerously-skip-permissions`). These require the user to be logged in via OAuth (run `gemini` or `claude` interactively once to auth).

How it works:
1. Determines current tier from `--current-model`.
2. Finds thin nodes: explored nodes with fewer than `--min-children` non-pruned children.
3. For each tier above current (up to `--max-tiers`):
   - Sends BRANCH_PROMPT to the stronger model for each thin node.
   - Parses new branches, adds them to the node.
   - Re-scores fertility.
   - If fertility improvement < 0.5, stops (plateau).
4. API keys loaded from `~/.bashrc` if not in env (`GEMINI_API_KEY`, `ANTHROPIC_API_KEY`).

Typical workflow:
```bash
# Fast initial exploration with local model
possibilities explore "What next?" -w . -d 2 -o tree.json

# Escalate thin branches to stronger models
possibilities escalate tree.json -w . --max-tiers 2 -o tree_v2.json
```

## Core Concepts

### PossibilityNode (models.py)

```python
class PossibilityNode:
    id: str                    # uuid hex[:8]
    title: str                 # short name (5-8 words)
    description: str           # 1-2 sentence explanation
    enables: list[str]         # what doors this opens (2-3 items)
    risk: str                  # what it might break
    category: str              # "obvious" | "contrarian" | "wildcard" | "foundational"
    depth: int                 # tree depth (root=0)
    parent_id: str | None
    children: list[PossibilityNode]

    # Scoring fields (filled by scorer.py)
    fertility_score: float     # computed recursively
    direct_fertility: int      # count of non-pruned children
    total_descendants: int     # total nodes below this one

    # State
    explored: bool             # True after LLM has generated children
    pruned: bool               # True if dedup flagged it
    prune_reason: str          # e.g. "Duplicate of: ..."
    model_used: str            # which LLM generated this node
    created_at: float          # unix timestamp
```

Serializes via `to_dict()` / `from_dict()` for JSON export/import.

### ExplorationConfig (models.py)

```python
class ExplorationConfig:
    seed_question: str = "What should we build next?"
    project_path: str = "."
    max_depth: int = 3
    branch_min: int = 3
    branch_max: int = 7
    model: str = "ollama/qwen2.5-coder:14b"
    decay: float = 0.7
    dedup_threshold: float = 0.85
    max_nodes: int = 80
    explore_strategy: str = "bfs"    # "bfs" or "fertility_guided"
    context_files: list[str]
    temperature: float = 0.9
    show_paths: int = 10
```

### Fertility Scoring (scorer.py)

`compute_fertility(node, decay=0.7)` -- recursive bottom-up:

- Leaf (no children): score = 0.0
- Branch: score = sum over non-pruned children of (1.0 + decay * child_fertility)
- Also sets `direct_fertility` (non-pruned child count) and `total_descendants`.

`rank_paths(tree, top_n=10)` -- DFS to find all root-to-leaf paths, scores each by cumulative fertility along the path, returns top N sorted descending.

`most_fertile_frontier(tree)` -- finds highest-fertility unexplored node. Used by `fertility_guided` strategy.

### Exploration Strategies

- **bfs**: FIFO frontier. Explores all nodes at depth N before going to depth N+1. Good for broad exploration.
- **fertility_guided**: Sorts frontier by fertility_score descending before popping. Explores the most fertile areas first. Requires intermediate scoring passes.

### Deduplication (dedup.py)

Two-stage check:

1. **Exact match**: lowercase title comparison.
2. **Substring match**: if one title contains the other and both >10 chars, flags as dup.
3. **LLM semantic check**: sends DEDUP_PROMPT comparing the new idea against the last 20 existing ideas. Returns `is_duplicate`, `similarity` (0-1), `duplicate_of`, `reason`. Only flags as duplicate if similarity >= threshold (default 0.85).

On LLM failure, keeps the idea (fails open).

### Project Context (context.py)

`gather_project_context(project_path, extra_files)` reads:

- Files in `CONTEXT_FILENAMES`: README.md, README, README.txt, package.json, pyproject.toml, Cargo.toml, go.mod, Makefile, docker-compose.yml, Dockerfile, CHANGELOG.md, CONTRIBUTING.md, AI_GUIDE.md. Each file capped at 3000 chars, only if under 20KB.
- User-specified `context_files` (same caps).
- Directory tree: 3 levels deep, skips `.git`, `node_modules`, `__pycache__`, `venv`, `target`, `build`, `dist`, and hidden dirs. Max 30 entries per directory.
- File extension census: counts extensions across the whole project (same skip dirs), shows top 15.

Output is a single string, ~2-4KB, injected into BRANCH_PROMPT as `{project_context}`.

### LLM Client (llm.py)

`LLMClient(model, temperature=0.9)` wraps litellm. If model starts with `ollama/`, sets `api_base` to `http://localhost:11434`. Temperature 0.9 by default -- intentionally high for divergent output.

`generate(prompt)` -> raw string. `generate_json(prompt)` -> `parse_json_response()` -> list of dicts.

`parse_json_response(text)` handles: markdown code fences (```json...```), raw JSON arrays, raw JSON objects. Returns empty list on failure.

### Prompts (prompts.py)

**BRANCH_PROMPT**: The critical prompt. Sends project context + seed question + depth guidance. Asks for N ideas as JSON array with title, description, enables, risk, category. Forces at least one contrarian and one wildcard. Requires specific concrete ideas, not vague ones ("Improve UX" is rejected in the prompt itself).

**DEDUP_PROMPT**: Asks LLM to compare a new idea against existing ones. Returns JSON with is_duplicate, duplicate_of, similarity, reason.

**get_depth_guidance(depth)**: Returns guidance string. Depth 0: "Think broad and diverse." Depth 1: "Get more specific." Depth 2+: "Get very concrete."

## Known Issues

1. **No tests.** Zero test files. The tool was verified by running it once against itself. Adding tests for scorer.py (pure functions, easy to test) and render.py would be high value.

2. **Dedup is expensive.** Every non-exact-match branch triggers an LLM call for semantic dedup. With 5 branches per node and 80 nodes, that's potentially hundreds of extra LLM calls. Consider: skip dedup for depth > 1, or batch dedup checks, or add a `--no-dedup` flag.

3. **Qwen 14B generates generic ideas.** The default model (ollama/qwen2.5-coder:14b) produces reasonable but sometimes generic suggestions. Stronger models (qwen3.5-27b, gpt-4o) produce more grounded, project-specific ideas.

4. **No interactive mode.** The tool runs to completion. There's no way to explore a specific branch interactively (prune some, expand others) mid-run. The `resume` command partially addresses this.

5. **JSON export includes pruned nodes.** `to_dict()` serializes everything including pruned children. `render_tree` hides them by default unless `--show-pruned`.

6. **fertility_guided re-scores every iteration.** The fertility_guided strategy calls `compute_fertility` on the entire tree before each frontier pop. For large trees this is wasted work since the tree structure hasn't changed much.

7. **design_seed.md and design_rfl/ are artifacts.** Leftover from the RFL design session. Not part of the package.

## How to Add a New Feature

### Add a new CLI command

1. Add a new subparser in `parse_args()` in cli.py (follow the pattern of `explore_p`, `show_p`, `resume_p`).
2. Add a `cmd_xxx(args)` function.
3. Add an `elif args.command == "xxx"` branch in `main()`.

### Add a new scoring metric

1. Add the function in scorer.py. It should take a PossibilityNode and return a float.
2. Call it in `explorer.py` after `compute_fertility()` in the `explore()` method.
3. Add the metric to `PossibilityNode` in models.py (add field, update `to_dict`/`from_dict`).

### Add a new exploration strategy

1. Add the strategy name to the `choices` in cli.py's `--strategy` arg.
2. Add the sorting logic in `explorer.py`'s `explore()` method where it currently handles "bfs" and "fertility_guided".

### Add a new render format

1. Add a function in render.py.
2. Call it from the relevant `cmd_xxx()` function in cli.py.

### Change the LLM prompt

All prompt text lives in prompts.py. BRANCH_PROMPT is the main one. It uses Python `.format()` with these placeholders: `{project_context}`, `{seed_question}`, `{depth}`, `{depth_guidance}`, `{n_min}`, `{n_max}`.

### Merge flow

The merge command lives in merge.py. `load_tree(path)` deserializes JSON to PossibilityNode. `merge_trees(trees, dedup, model, dedup_threshold, decay)` does the work:
1. Groups trees by normalized root question.
2. Creates synthetic root, re-parents children with `_reparent_subtree()`.
3. Optional cross-tree dedup via Deduplicator.
4. Re-scores with compute_fertility().

Called from `cmd_merge()` in cli.py.
