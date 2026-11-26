"""Local Ollama backend; output constrained with Ollama's JSON-schema `format`."""
from __future__ import annotations

import httpx

from app.models import ParseContext, StopRequest
from app.providers.llm.schema import (LLMOutput, extract_json, json_schema, system_prompt, to_stop_requests,
                                      user_prompt)


class OllamaParser:
    name = "ollama"

    def __init__(self, url: str, model: str, timeout_s: float = 20.0):
        self.url, self.model, self.timeout = url.rstrip("/"), model, timeout_s

    def parse(self, text: str, ctx: ParseContext) -> list[StopRequest]:
        r = httpx.post(f"{self.url}/api/chat", timeout=self.timeout, json={
            "model": self.model, "stream": False, "format": json_schema(),
            "options": {"temperature": 0},
            "messages": [{"role": "system", "content": system_prompt()},
                         {"role": "user", "content": user_prompt(text, ctx)}]})
        r.raise_for_status()
        out = LLMOutput.model_validate(extract_json(r.json()["message"]["content"]))
        return to_stop_requests(out)
