"""Record real OneMap responses as test fixtures (DESIGN §12).

    python backend/tests/record_onemap.py --record

Needs ONEMAP_EMAIL / ONEMAP_PASSWORD in .env. Without --record it only lists
what would be fetched. The committed fixtures are SYNTHETIC (same response shape)
until this has been run with real credentials.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import get_settings  # noqa: E402
from app.providers.routing.onemap import OneMapAuth, OneMapRouting  # noqa: E402

TZ = ZoneInfo("Asia/Singapore")
OUT = Path(__file__).parent / "fixtures" / "onemap"
ROUTES = [
    ("ntu_changi_drive.json", (1.3483, 103.6831), (1.3644, 103.9915), "drive", (12, 30)),
    ("jurongwest_sultan_pt.json", (1.3402, 103.7070), (1.3023, 103.8588), "transit", (12, 30)),
    ("ntu_sentosa_drive.json", (1.3483, 103.6831), (1.2494, 103.8303), "drive", (12, 30)),
]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--record", action="store_true")
    args = ap.parse_args()
    s = get_settings()
    om = OneMapRouting(OneMapAuth(s.onemap_email, s.onemap_password))
    if args.record and not om.auth.configured:
        sys.exit("ONEMAP_EMAIL / ONEMAP_PASSWORD not set")
    today = datetime.now(TZ).date()
    for name, a, b, mode, (h, m) in ROUTES:
        depart = datetime(today.year, today.month, today.day, h, m, tzinfo=TZ)
        print(f"{name}: {a} -> {b} {mode} @ {depart:%Y-%m-%d %H:%M}")
        if args.record:
            data = om.fetch(a, b, mode, depart)
            data["_recorded"] = {"at": datetime.now(TZ).isoformat(), "depart": depart.isoformat()}
            (OUT / name).write_text(json.dumps(data, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
