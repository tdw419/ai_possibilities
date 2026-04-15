# Possibilities -- AI Possibility Tree Explorer

Find the ideas that open the most doors.

## What It Does

You give it a seed question (e.g. "What should we build next?") and point it at a project directory. It uses an LLM to generate possible directions, then recursively explores each direction to discover which ideas spawn the most sub-possibilities.

Ideas that branch into more paths are ranked higher, because they maximize future optionality.

```
[Root] "What should we build next?" (fertility: 28.3)
|-- [8.1] Visual editor for seed recipes (foundational)
|   |-- [2.8] Live preview with hot-reload
|   --- [3.0] Export recipe as shareable URL
|-- [6.4] Seed-to-executable pipeline (wildcard)
|   |-- [3.2] WASM compilation target
|   --- [3.2] Native binary output via cranelift
|-- [5.5] Biological metaphor API (contrarian)
|   |-- [2.1] Mutation operators on seeds
|   --- [1.7] Crossover / breeding between recipes
--- [4.2] Pixel art gallery (obvious)
    --- [2.1] Community seed sharing
```

## Install

```bash
cd ~/zion/projects/ai_possibilities/ai_possibilities
pip install -e . --break-system-packages
```

Requires Ollama running locally (or set `OPENAI_API_KEY` for cloud models).

## Usage

```bash
# Basic exploration
possibilities explore "What should we build next?" -w /path/to/project

# With options
possibilities explore "What direction should this project go?" \
  -w /path/to/project \
  -d 3 \                      # max depth
  --max-nodes 80 \            # max total nodes
  --branch-min 3 \            # min branches per node
  --branch-max 7 \            # max branches per node
  -m ollama/qwen2.5-coder:14b \  # model to use
  -s bfs \                    # bfs or fertility_guided
  -o tree.json                # export to file

# View a saved tree
possibilities show tree.json

# Resume exploration on an existing tree (go deeper)
possibilities resume tree.json -d 4
```

## How It Works

1. Reads project context (README, directory structure, file types)
2. Sends seed question + context to LLM, asks for 3-7 diverse directions
3. Each direction gets a category: obvious, contrarian, wildcard, foundational
4. Deduplicates similar ideas (LLM-based semantic check)
5. Explores each branch (BFS by default), generating sub-possibilities
6. Scores by **fertility**: how many new doors does each idea open?
7. Ranks root-to-leaf paths by cumulative fertility

### Fertility Scoring

```
leaf node = 0 (dead end)
branch = sum over children of (1 + decay * child_fertility)

Example with decay=0.7:
  - 5 leaf children: score = 5.0
  - 2 children each with 5 leaves: score = 9.0
  - 3 children with varied branching: score = 10.3
```

Deeper cascading branches score higher. The tool surfaces ideas that create the most future optionality.

### Categories

Every generated idea gets tagged:
- **obvious**: What most people would suggest
- **contrarian**: Goes against conventional wisdom
- **wildcard**: Unexpected, potentially transformative
- **foundational**: Infrastructure that enables many other things

The prompt forces at least one contrarian and one wildcard per expansion.

## Architecture

```
possibilities/
  __init__.py
  __main__.py       # python -m possibilities
  cli.py            # argparse CLI
  models.py         # PossibilityNode, ExplorationConfig
  explorer.py       # BFS/fertility-guided exploration engine
  scorer.py         # Fertility scoring + path ranking
  llm.py            # litellm wrapper (supports Ollama, OpenAI, etc.)
  dedup.py          # Semantic dedup (exact match + LLM)
  prompts.py        # Branch generation + dedup prompts
  context.py        # Project context gathering
  render.py         # ASCII tree + ranked paths output
```

~600 LOC, no framework dependencies beyond litellm.

## Models

Works with any litellm-supported model:

```bash
# Local via Ollama (default)
possibilities explore "..." -m ollama/qwen2.5-coder:14b

# OpenAI (requires OPENAI_API_KEY)
possibilities explore "..." -m gpt-4o-mini

# Any litellm-compatible model
possibilities explore "..." -m anthropic/claude-sonnet-4
```

Higher temperature (0.9 default) produces more divergent ideas.
