from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(REPO_ROOT / ".env", Path.cwd() / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    onemap_email: str = ""
    onemap_password: str = ""
    ors_api_key: str = ""
    # Keyless OSRM (FOSSGIS community server) as a last-resort fallback for
    # drive/walk/cycle when no credentials are configured. Set empty to disable.
    osrm_base_url: str = "https://routing.openstreetmap.de"
    # OSRM demo server (driving only) as a second keyless fallback.
    osrm_demo_url: str = "https://router.project-osrm.org"
    # Keyless Photon geocoder fallback. Set empty to disable.
    photon_url: str = "https://photon.komoot.io/api/"

    llm_backend: str = "rules"
    ollama_url: str = "http://localhost:11434"
    ollama_model: str = "qwen2.5:3b"
    llm_base_url: str = ""
    llm_api_key: str = ""
    llm_model: str = ""
    llm_timeout_s: float = 20.0

    region: str = "singapore"
    poi_db_path: str = "data/pois.sqlite"
    cache_db_path: str = "data/cache.sqlite"
    cors_origins: str = "http://localhost:5173"
    route_cache_ttl_s: int = 6 * 3600
    geocode_cache_ttl_s: int = 7 * 24 * 3600
    http_user_agent: str = "route-stop-planner/0.1 (open-source hobby project)"

    def path(self, p: str) -> Path:
        path = Path(p)
        return path if path.is_absolute() else REPO_ROOT / path

    @property
    def cors_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
