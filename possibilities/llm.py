"""LLM wrapper for generating possibilities."""

import json
import os
import re


class LLMClient:
    """Thin wrapper around litellm for LLM calls."""

    # Provider configs for non-ollama backends
    PROVIDERS = {
        "zai": {
            "model_prefix": "openai/",
            "api_base": "https://api.z.ai/api/coding/paas/v4",
            "env_key": "ZAI_API_KEY",
        },
    }

    def __init__(self, model: str, temperature: float = 0.9):
        self.temperature = temperature
        self.api_base = None
        self.api_key = None
        self._provider = None

        # Handle provider prefixes: zai/glm-5.1 -> openai/glm-5.1 with zai config
        if "/" in model:
            prefix, rest = model.split("/", 1)
            if prefix in self.PROVIDERS:
                self._provider = self.PROVIDERS[prefix]
                self.model = f"{self._provider['model_prefix']}{rest}"
                self.api_base = self._provider["api_base"]
                self._load_key(self._provider["env_key"])
            elif prefix == "ollama":
                self.model = model
                self.api_base = "http://localhost:11434"
            else:
                self.model = model
        else:
            self.model = model

    def _load_key(self, env_key: str):
        """Load API key from env or .bashrc."""
        key = os.environ.get(env_key)
        if key:
            self.api_key = key
            return
        bashrc = os.path.expanduser("~/.bashrc")
        if os.path.exists(bashrc):
            with open(bashrc) as f:
                for line in f:
                    line = line.strip()
                    if line.startswith(f"export {env_key}="):
                        val = line.split("=", 1)[1].strip().strip('"').strip("'")
                        os.environ[env_key] = val
                        self.api_key = val
                        return

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
        if self.api_key:
            kwargs["api_key"] = self.api_key
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
