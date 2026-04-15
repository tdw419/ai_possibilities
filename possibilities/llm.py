"""LLM wrapper for generating possibilities."""

import json
import re


class LLMClient:
    """Thin wrapper around litellm for LLM calls."""

    def __init__(self, model: str, temperature: float = 0.9):
        self.model = model
        self.temperature = temperature
        self.api_base = None
        if model.startswith("ollama/"):
            self.api_base = "http://localhost:11434"

    def generate(self, prompt: str) -> str:
        import litellm
        kwargs = dict(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=self.temperature,
            max_tokens=3000,
        )
        if self.api_base:
            kwargs["api_base"] = self.api_base
        resp = litellm.completion(**kwargs)
        return resp.choices[0].message.content

    def generate_json(self, prompt: str) -> list[dict]:
        """Generate a response and parse JSON from it."""
        raw = self.generate(prompt)
        return parse_json_response(raw)


def parse_json_response(text: str) -> list[dict]:
    """Extract JSON array from LLM response, handling markdown fences."""
    text = text.strip()

    # Try to find JSON in markdown code blocks
    if "```" in text:
        blocks = re.findall(r'```(?:json)?\s*\n(.*?)```', text, re.DOTALL)
        for block in blocks:
            try:
                result = json.loads(block.strip())
                if isinstance(result, list):
                    return result
                return [result]
            except json.JSONDecodeError:
                continue

    # Try to find raw JSON array
    bracket_start = text.find("[")
    brace_start = text.find("{")

    if bracket_start != -1 and (brace_start == -1 or bracket_start < brace_start):
        try:
            result = json.loads(text[bracket_start:])
            if isinstance(result, list):
                return result
        except json.JSONDecodeError:
            pass

    # Try the whole thing
    try:
        result = json.loads(text)
        if isinstance(result, list):
            return result
        return [result]
    except json.JSONDecodeError:
        return []
