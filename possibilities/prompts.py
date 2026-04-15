"""Prompts for LLM-driven possibility generation."""


BRANCH_PROMPT = """You are a possibility explorer. Your job is NOT to evaluate or rank ideas -- it is to generate diverse, generative directions that maximize future optionality.

PROJECT CONTEXT:
{project_context}

SEED QUESTION: {seed_question}

We are {depth} level(s) deep in exploration. {depth_guidance}

Generate {n_min}-{n_max} possible directions. Each must be a genuinely different KIND of idea, not a variation on the same theme.

For each direction, provide:

1. TITLE: Short name (5-8 words, specific not vague)
2. DESCRIPTION: What this IS (1-2 sentences, concrete)
3. ENABLES: What doors this OPENS. What becomes possible that was not possible before? List 2-3 specific capabilities or opportunities this unlocks. Think second-order: "if we do X, then Y and Z become possible."
4. RISK: What this might foreclose, break, or make harder.
5. CATEGORY: One of:
   - obvious: The natural next step most people would suggest
   - contrarian: Goes against conventional wisdom or the obvious path
   - wildcard: Unexpected, unconventional, potentially transformative
   - foundational: Infrastructure/enablers that make many other things possible

HARD RULES:
- "Improve UX" is not an idea. "Command palette with fuzzy search that learns from usage patterns" is.
- "Better performance" is not an idea. "Replace the rendering loop with a retained-mode scenegraph that supports incremental redraw" is.
- At least one idea MUST be contrarian and one MUST be wildcard.
- Think across dimensions: not just features, but architecture, distribution, community, business model, integration, abstraction level, target audience.
- If the project is a tool, think about: who else could use it? What would it look like as a platform? What if it did LESS? What if it did something adjacent?
- The ENABLES field is the most important part. Ideas that enable more future possibilities are more valuable.

Return a JSON array:
[{{
  "title": "...",
  "description": "...",
  "enables": ["...", "...", "..."],
  "risk": "...",
  "category": "obvious|contrarian|wildcard|foundational"
}}]"""

DEDUP_PROMPT = """Compare a new idea against already-explored ideas in this tree.

NEW IDEA:
  Title: {new_title}
  Description: {new_desc}

EXISTING IDEAS:
{existing_ideas}

Is the new idea substantially the same as any existing idea? Two ideas are duplicates if they would lead to the same exploration path -- even if worded differently. "Build a plugin system" and "add extension support" are duplicates. "Build a plugin system" and "create an API marketplace" are NOT duplicates.

Return JSON:
{{
  "is_duplicate": true or false,
  "duplicate_of": "title of matching idea or null",
  "similarity": 0.0,
  "reason": "one sentence explanation"
}}"""


def get_depth_guidance(depth: int) -> str:
    """Get guidance text for how deep we are in the tree."""
    if depth == 0:
        return "Think broad and diverse. Span multiple dimensions of possibility."
    elif depth == 1:
        return "Get more specific. What are the concrete sub-approaches within this direction?"
    else:
        return "Get very concrete. What are the specific technical or strategic choices at this level?"
