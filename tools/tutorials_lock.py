"""Write content/tutorials/versions.lock from the tutorials as they stand.

Run after raising a tutorial's `v` for a change to its words:

    python tools/tutorials_lock.py

The lock is how tests/test_tutorials.py catches words changed without a version raised
(docs/tutorials-plan.md §3.5): it keeps each tutorial's `v` and the hash of what a player
reads. Refuses to write a hash change whose `v` did not move, which is the mistake the
lock exists to catch.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from play.tutorials import content_hash  # noqa: E402

LOCK = ROOT / "content" / "tutorials" / "versions.lock"


def main() -> int:
    old = json.loads(LOCK.read_text(encoding="utf-8")) if LOCK.exists() else {}
    new, bad = {}, []
    for p in sorted((ROOT / "content" / "tutorials").glob("*.json")):
        for t in json.loads(p.read_text(encoding="utf-8")).get("tutorials") or []:
            h = content_hash(t)
            was = old.get(t["id"])
            if was and was["hash"] != h and was["v"] == t["v"]:
                bad.append(t["id"])
            new[t["id"]] = {"v": t["v"], "hash": h}
    if bad:
        print("Raise `v` (and the changed steps' `since`) first: " + ", ".join(bad))
        return 1
    LOCK.write_text(json.dumps(new, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {LOCK} ({len(new)} tutorials)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
