from __future__ import annotations

import httpx

from app.config import get_settings

_client: httpx.Client | None = None


def client() -> httpx.Client:
    global _client
    if _client is None:
        _client = httpx.Client(timeout=httpx.Timeout(20.0, connect=8.0),
                               headers={"User-Agent": get_settings().http_user_agent},
                               follow_redirects=True)
    return _client
