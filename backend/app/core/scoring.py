"""Dietary/category evidence (D9), scoring (§5.6) and dedupe."""
from __future__ import annotations

import math
import re

from app.core import tags as T
from app.models import Evidence

# -------------------------------------------------------------- evidence --


def _yes(v: str | None) -> bool:
    return v in ("yes", "only")


def dietary_evidence(tags: dict[str, str], dietary: list[str]) -> tuple[bool, list[Evidence], bool]:
    """Return (eligible, evidence, only_weak). A place with *no* evidence for a
    required dietary constraint is ineligible (excluded, not penalised)."""
    name = (tags.get("name") or "").lower()
    brand = (tags.get("brand") or "").lower()
    cuisine = [c.strip() for c in (tags.get("cuisine") or "").lower().split(";") if c.strip()]
    evidence: list[Evidence] = []
    any_weak_only = False
    for d in dietary:
        strong: list[Evidence] = []
        weak: list[Evidence] = []
        if d == "halal":
            v = tags.get("diet:halal")
            if v == "no":
                return False, [Evidence(text="OSM diet:halal=no", strength="strong")], False
            if _yes(v):
                strong.append(Evidence(text=f"OSM diet:halal={v}"))
            else:
                hit = next((h for h in T.HALAL_BRAND_HINTS if h in brand or h in name), None)
                if hit:
                    weak.append(Evidence(text=f"brand list: '{hit}' (verify certification)", strength="weak"))
                hit = next((h for h in T.HALAL_NAME_HINTS if T.matches_name(name, (h,))), None)
                if hit:
                    weak.append(Evidence(text=f"name contains '{hit}'", strength="weak"))
                hit = next((c for c in cuisine if c in T.HALAL_CUISINE_HINTS), None)
                if hit:
                    weak.append(Evidence(text=f"cuisine={hit} (hint)", strength="weak"))
        elif d in ("vegetarian", "vegan"):
            keys = ["diet:vegan"] if d == "vegan" else ["diet:vegetarian", "diet:vegan"]
            for k in keys:
                v = tags.get(k)
                if _yes(v):
                    strong.append(Evidence(text=f"OSM {k}={v}"))
                elif v == "limited":
                    weak.append(Evidence(text=f"OSM {k}=limited", strength="weak"))
            if d == "vegetarian" and "vegetarian" in cuisine:
                strong.append(Evidence(text="OSM cuisine=vegetarian"))
            if d == "vegan" and "vegan" in cuisine:
                strong.append(Evidence(text="OSM cuisine=vegan"))
            hints = ("vegan",) if d == "vegan" else T.VEG_NAME_HINTS
            hit = next((h for h in hints if T.matches_name(name, (h,))), None)
            if hit and not strong:
                weak.append(Evidence(text=f"name contains '{hit}'", strength="weak"))
        if strong:
            evidence.extend(strong)
        elif weak:
            evidence.extend(weak)
            any_weak_only = True
        else:
            return False, [], False
    return True, evidence, any_weak_only


def category_evidence(cat: T.CategoryDef, tags: dict[str, str],
                      name_keywords=None) -> tuple[bool, list[Evidence]]:
    """Does the place match the category? Tag match = strong; name hint only = weak.
    `name_keywords` overrides the category's own list (keyword-search stops)."""
    kws = tuple(name_keywords) if name_keywords is not None else cat.name_keywords
    if cat.kind == "prayer" and (tags.get("historic") or T.matches_name(tags.get("name"), T.NOT_PRAYER_HINTS)):
        return False, []  # shrines / tombs (keramat, makam) are not places to pray
    if T.matches_filters(tags, cat.filters):
        ev = []
        for f in cat.filters:
            if T.matches_filters(tags, (f,)):
                ev.append(Evidence(text="OSM " + " + ".join(f"{k}={tags.get(k)}" for k in f)))
                break
        hit = next((k for k in kws if T.matches_name(tags.get("name"), (k,))), None)
        if hit:
            ev.append(Evidence(text=f"name contains '{hit}'", strength="weak"))
        return True, ev
    if T.matches_name(tags.get("name"), kws) and T.name_match_allowed(cat, tags):
        hit = next(k for k in kws if T.matches_name(tags.get("name"), (k,)))
        return True, [Evidence(text=f"name contains '{hit}'", strength="weak")]
    return False, []


# ---------------------------------------------------------------- score --


def score(detour_min: float, open_state, require_open: bool, eta_off_target_min: float | None,
          tolerance_min: float, has_name: bool, weak_dietary: bool, weak_category: bool = False,
          combine_bonus: float = 0.0, push_overflow_min: float = 0.0,
          wait_min: float = 0.0) -> tuple[float, dict[str, float]]:
    """Lower is better; every term is in minutes so the breakdown is explainable."""
    b: dict[str, float] = {"detour": round(detour_min, 1)}
    if wait_min > 0:
        # arriving before the window opens (prayer time): real minutes added
        b["wait"] = round(wait_min, 1)
    if open_state is False and require_open:
        b["closed_at_eta"] = 60.0
    elif open_state == "unknown":
        b["hours_unknown"] = 3.0
    if eta_off_target_min is not None:
        off = abs(eta_off_target_min)
        out = max(0.0, off - tolerance_min)
        if out > 0:
            b["outside_window"] = round(0.5 * out, 1)
        # tie-breaker inside the window: prefer ETAs closer to the target (D12)
        fit = round(0.1 * min(off, tolerance_min), 1)
        if fit > 0:
            b["off_target"] = fit
    if push_overflow_min > 0:
        # pushes an already-chosen timed stop past its window (D12)
        b["pushes_other_stops"] = round(0.5 * push_overflow_min, 1)
    if not has_name:
        b["no_name"] = 2.0
    if weak_dietary:
        b["weak_dietary_evidence"] = 5.0
    if weak_category:
        b["name_hint_only"] = 2.0
    if combine_bonus > 0:
        b["combine_bonus"] = -round(combine_bonus, 1)
    return round(sum(b.values()), 2), b


# ---------------------------------------------------------------- dedupe --

_NORM = re.compile(r"[^a-z0-9]+")


def _norm(name: str | None) -> str:
    return _NORM.sub("", (name or "").lower())


def dedupe(items: list, key_latlng, key_name, key_osm, key_tags, radius_m: float = 30.0) -> list:
    """Drop duplicates: same osm_id, or same normalised name within `radius_m`
    (node + way mapping the same place). Keeps the richer-tagged item."""
    seen_osm: set[str] = set()
    by_name: dict[str, list] = {}
    out: list = []
    for it in sorted(items, key=lambda i: -len(key_tags(i))):
        oid = key_osm(it)
        if oid in seen_osm:
            continue
        nm = _norm(key_name(it))
        lat, lng = key_latlng(it)
        dup = False
        if nm:
            for other in by_name.get(nm, []):
                olat, olng = key_latlng(other)
                dy = (lat - olat) * 111_195
                dx = (lng - olng) * 111_195 * math.cos(math.radians(lat))
                if math.hypot(dx, dy) <= radius_m:
                    dup = True
                    break
        if dup:
            continue
        seen_osm.add(oid)
        if nm:
            by_name.setdefault(nm, []).append(it)
        out.append(it)
    return out
