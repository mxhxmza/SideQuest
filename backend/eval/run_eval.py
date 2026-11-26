"""Evaluate NL parsing backends on eval/cases.jsonl (DESIGN §6).

    python backend/eval/run_eval.py --backend rules|ollama|openai_compat [-v]

Reports per-field accuracy (aligned by position) and exact-match accuracy per case.
Backends that fail fall back to rules inside the service, so this script calls the
backend directly and counts failures separately.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.config import get_settings  # noqa: E402
from app.models import ParseContext  # noqa: E402
from app.providers.llm.service import ParseService  # noqa: E402

FIELDS = ("category", "dietary", "type", "value")


def norm_expected(e: dict) -> dict:
    return {"category": e["category"], "dietary": sorted(e.get("dietary", [])), "type": e["window"]["type"],
            "value": e["window"].get("value")}


def norm_got(s) -> dict:
    v = s.time_window.value
    if isinstance(v, float) and v.is_integer():
        v = int(v)
    return {"category": s.category, "dietary": sorted(s.constraints.dietary), "type": s.time_window.type,
            "value": v}


def same_value(a, b) -> bool:
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return abs(a - b) < 1e-6
    return a == b


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--backend", default="rules", choices=["rules", "ollama", "openai_compat"])
    ap.add_argument("--cases", type=Path, default=ROOT / "eval" / "cases.jsonl")
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args()

    svc = ParseService(get_settings())
    backend = svc.backends[args.backend]
    cases = [json.loads(l) for l in args.cases.read_text(encoding="utf-8").splitlines() if l.strip()]
    field_ok = {f: 0 for f in FIELDS}
    field_n = 0
    exact = failures = 0
    t0 = time.time()
    for c in cases:
        exp = [norm_expected(e) for e in c["expected"]]
        try:
            got = [norm_got(s) for s in backend.parse(c["text"], ParseContext())]
        except Exception as e:  # noqa: BLE001
            failures += 1
            got = []
            if args.verbose:
                print(f"FAIL  {c['text']!r}: {type(e).__name__}: {e}")
        field_n += len(exp)
        for i, e in enumerate(exp):
            g = got[i] if i < len(got) else None
            for f in FIELDS:
                if g is not None and same_value(g[f], e[f]):
                    field_ok[f] += 1
        ok = len(got) == len(exp) and all(all(same_value(g[f], e[f]) for f in FIELDS) for g, e in zip(got, exp))
        exact += ok
        if args.verbose and not ok:
            print(f"MISS  {c['text']!r}\n      expected {exp}\n      got      {got}")
    dt = time.time() - t0
    print(f"backend={args.backend} cases={len(cases)} stops={field_n} time={dt:.1f}s failures={failures}")
    for f in FIELDS:
        print(f"  {f:9s} {field_ok[f] / field_n:6.1%}")
    print(f"  exact     {exact / len(cases):6.1%}  ({exact}/{len(cases)} cases)")


if __name__ == "__main__":
    main()
