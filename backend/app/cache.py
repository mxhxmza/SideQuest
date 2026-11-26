"""SQLite TTL cache for provider responses (route / geocode), keyed by request hash."""
from __future__ import annotations

import hashlib
import json
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any, Optional


class TTLCache:
    def __init__(self, path: str | Path | None):
        self._lock = threading.Lock()
        if path is None:
            self.db = sqlite3.connect(":memory:", check_same_thread=False)
        else:
            Path(path).parent.mkdir(parents=True, exist_ok=True)
            self.db = sqlite3.connect(str(path), check_same_thread=False)
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("CREATE TABLE IF NOT EXISTS cache (k TEXT PRIMARY KEY, v TEXT NOT NULL, exp REAL NOT NULL)")
        self.db.commit()
        self.hits = 0
        self.misses = 0

    @staticmethod
    def key(namespace: str, payload: Any) -> str:
        raw = json.dumps(payload, sort_keys=True, default=str, separators=(",", ":"))
        return namespace + ":" + hashlib.sha256(raw.encode()).hexdigest()[:32]

    def get(self, k: str) -> Optional[str]:
        with self._lock:
            r = self.db.execute("SELECT v, exp FROM cache WHERE k = ?", (k,)).fetchone()
        if r is None or r[1] < time.time():
            self.misses += 1
            return None
        self.hits += 1
        return r[0]

    def set(self, k: str, v: str, ttl_s: float) -> None:
        with self._lock:
            self.db.execute("INSERT OR REPLACE INTO cache VALUES (?,?,?)", (k, v, time.time() + ttl_s))
            self.db.commit()

    def purge(self) -> int:
        with self._lock:
            n = self.db.execute("DELETE FROM cache WHERE exp < ?", (time.time(),)).rowcount
            self.db.commit()
        return n


class TokenBucket:
    """Simple blocking token bucket (stays below a provider's per-minute limit)."""

    def __init__(self, per_minute: float, burst: int | None = None):
        self.rate = per_minute / 60.0
        self.capacity = burst or max(1, int(per_minute // 6))
        self.tokens = float(self.capacity)
        self.t = time.monotonic()
        self._lock = threading.Lock()

    def take(self) -> None:
        while True:
            with self._lock:
                now = time.monotonic()
                self.tokens = min(self.capacity, self.tokens + (now - self.t) * self.rate)
                self.t = now
                if self.tokens >= 1:
                    self.tokens -= 1
                    return
                wait = (1 - self.tokens) / self.rate
            time.sleep(min(wait, 1.0))
