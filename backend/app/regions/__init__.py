"""Region registry. A new region = one module exposing `REGION` + its own POI DB."""
from __future__ import annotations

from importlib import import_module

from .base import Region


def get_region(key: str) -> Region:
    mod = import_module(f"app.regions.{key}")
    return mod.REGION


__all__ = ["Region", "get_region"]
