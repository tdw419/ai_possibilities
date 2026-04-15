"""Deduplication of similar ideas in the possibility tree."""

from dataclasses import dataclass
from .models import PossibilityNode
from .llm import LLMClient, parse_json_response


@dataclass
class DupResult:
    """Result of a dedup check."""
    is_duplicate: bool
    duplicate_of: str = ""
    similarity: float = 0.0
    reason: str = ""


class Deduplicator:
    """Check new ideas against existing ones to avoid redundant exploration."""

    def __init__(self, llm: LLMClient, threshold: float = 0.85):
        self.llm = llm
        self.threshold = threshold

    def check(
        self, new: PossibilityNode, existing: list[dict]
    ) -> DupResult:
        """Check if a new idea duplicates any existing idea."""
        if not existing:
            return DupResult(is_duplicate=False)

        # Quick: exact title match
        new_title_lower = new.title.lower().strip()
        for e in existing:
            if e["title"].lower().strip() == new_title_lower:
                return DupResult(True, e["title"], 1.0, "Exact title match")

        # Quick: substring check for very similar titles
        for e in existing:
            existing_lower = e["title"].lower().strip()
            if (
                len(new_title_lower) > 10
                and len(existing_lower) > 10
                and (
                    new_title_lower in existing_lower
                    or existing_lower in new_title_lower
                )
            ):
                return DupResult(True, e["title"], 0.9, "Near-identical title")

        # LLM-based semantic check (only check recent to cap token use)
        recent = existing[-20:]
        existing_text = "\n".join(
            f"  - {e['title']}: {e.get('description', '')[:100]}"
            for e in recent
        )

        from .prompts import DEDUP_PROMPT
        prompt = DEDUP_PROMPT.format(
            new_title=new.title,
            new_desc=new.description,
            existing_ideas=existing_text,
        )

        try:
            raw = self.llm.generate(prompt)
            results = parse_json_response(raw)
            if results:
                r = results[0]
                is_dup = r.get("is_duplicate", False)
                similarity = r.get("similarity", 0.0)
                return DupResult(
                    is_duplicate=is_dup and similarity >= self.threshold,
                    duplicate_of=r.get("duplicate_of", ""),
                    similarity=similarity,
                    reason=r.get("reason", ""),
                )
        except Exception:
            pass  # On failure, keep the idea

        return DupResult(is_duplicate=False)
