"""Any OpenAI-compatible endpoint (Groq free tier, Gemini's OpenAI-compatible API, ...)."""
from __future__ import annotations

import httpx

from app.models import ParseContext, StopRequest
from app.providers.llm.schema import LLMOutput, extract_json, system_prompt, to_stop_requests, user_prompt


class OpenAICompatParser:
    name = "openai_compat"

    def __init__(self, base_url: str, api_key: str, model: str, timeout_s: float = 20.0):
        self.base, self.key, self.model, self.timeout = base_url.rstrip("/"), api_key, model, timeout_s

    @property
    def configured(self) -> bool:
        return bool(self.base and self.model)

    def parse(self, text: str, ctx: ParseContext) -> list[StopRequest]:
        if not self.configured:
            raise RuntimeError("LLM_BASE_URL / LLM_MODEL not configured")
        body = {"model": self.model, "temperature": 0,
                "messages": [{"role": "system", "content": system_prompt()},
                             {"role": "user", "content": user_prompt(text, ctx)}],
                "response_format": {"type": "json_object"}}
        headers = {"Authorization": f"Bearer {self.key}"} if self.key else {}
        r = httpx.post(f"{self.base}/chat/completions", json=body, headers=headers, timeout=self.timeout)
        if r.status_code == 400:  # some servers reject response_format
            body.pop("response_format")
            r = httpx.post(f"{self.base}/chat/completions", json=body, headers=headers, timeout=self.timeout)
        r.raise_for_status()
        content = r.json()["choices"][0]["message"]["content"]
        return to_stop_requests(LLMOutput.model_validate(extract_json(content)))
