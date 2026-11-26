"""Parse service: chosen backend → Pydantic validation → fallback to rules (DESIGN §6)."""
from __future__ import annotations

import logging

from app.config import Settings
from app.core.planner import normalize_stop
from app.models import ParseContext, ParseResponse
from app.providers.llm.ollama import OllamaParser
from app.providers.llm.openai_compat import OpenAICompatParser
from app.providers.llm.rules import RulesParser

log = logging.getLogger(__name__)
BACKENDS = ("rules", "ollama", "openai_compat")


class ParseService:
    def __init__(self, settings: Settings):
        self.rules = RulesParser()
        self.backends = {
            "rules": self.rules,
            "ollama": OllamaParser(settings.ollama_url, settings.ollama_model, settings.llm_timeout_s),
            "openai_compat": OpenAICompatParser(settings.llm_base_url, settings.llm_api_key, settings.llm_model,
                                                settings.llm_timeout_s),
        }
        self.default = settings.llm_backend if settings.llm_backend in BACKENDS else "rules"

    def parse(self, text: str, ctx: ParseContext, backend: str | None = None) -> ParseResponse:
        name = backend if backend in BACKENDS else self.default
        warnings: list[str] = []
        unrecognized: list[str] = []
        try:
            if name == "rules":
                stops, unrecognized = self.rules.parse_with_notes(text, ctx)
            else:
                stops = self.backends[name].parse(text, ctx)
            used = name
        except Exception as e:  # validation error, timeout, connection refused...
            if name == "rules":
                raise
            log.warning("parser %s failed, falling back to rules: %s", name, e)
            warnings.append(f"{name} parser failed ({type(e).__name__}); used rules instead")
            stops, unrecognized = self.rules.parse_with_notes(text, ctx)
            used = "rules"
        if not stops and text.strip():
            warnings.append("No stops recognised. Try e.g. 'halal lunch around 1pm, mosque at Asr'.")
        return ParseResponse(backend_used=used, stops=[normalize_stop(s) for s in stops], warnings=warnings,
                             unrecognized=unrecognized)
