Design a Python CLI tool called "possibilities" that helps an AI explore branching possibilities for any project.

CORE CONCEPT: Start with a seed question (e.g. "what should we build next for this project?"), use an LLM to generate possible directions, then recursively explore each direction to find which ones open the most doors. Ideas that spawn the most branches are ranked highest because they maximize future optionality.

KEY PRINCIPLE: Not all ideas are equal. An idea that branches into 7 sub-possibilities is more valuable than one that branches into 2, because it opens more doors. The tool should discover and rank ideas by their "fertility" -- how many new possibilities they generate.

REQUIRED FEATURES:
1. Tree data structure where each node is an idea and children are sub-possibilities
2. LLM-driven branching (AI generates 3-7 possible directions per node)
3. Fertility scoring (ideas that branch more = higher score, with decay for depth)
4. Breadth-first exploration (explore wide before going deep, to find the most fertile areas first)
5. Deduplication (detect and prune ideas that are semantically similar to already-explored ones)
6. ASCII tree visualization showing the full possibility tree with scores
7. Export ranked paths from root to the most fertile leaves
8. Project context injection (read project files/dirs to ground exploration in reality)
9. Configurable depth, branching factor, and AI model

DELIVER: A concrete architecture with:
- File structure and module layout
- Data models (classes/dataclasses)
- The LLM seed prompt that drives good exploration (this is critical -- the prompt determines quality)
- CLI interface design
- Scoring algorithm pseudocode
- How to handle the "project context" problem (reading a project to ground suggestions)

Be specific. Include actual code sketches for the data model and scoring. The seed prompt for the LLM is the most important part -- it needs to make the AI think divergently, generate genuinely different possibilities, and explain what each possibility would enable.
