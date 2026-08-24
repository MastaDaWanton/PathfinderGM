"""The materials folder is one shared shelf, and a shelf has one jar per id.

All four craft modules read every file in content/materials, so a duplicate id is not
two entries — it is one entry silently shadowing another, last file in glob order
winning. Measured when the four tracks first landed together: ten substances (brine,
tallow, quicklime...) existed twice with different kinds and tiers, and which craft's
version anyone got depended on filename alphabetics.
"""
from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path


def test_no_id_exists_twice_across_the_shelf():
    seen = defaultdict(list)
    for p in sorted(Path("content/materials").glob("*.json")):
        data = json.loads(p.read_text(encoding="utf-8"))
        for m in data.get("materials", []):
            seen[str(m["id"]).strip().lower()].append(p.stem)
    dups = {k: v for k, v in seen.items() if len(v) > 1}
    assert dups == {}, f"shadowed ids: {dups}"


def test_the_shelf_is_deep_enough_not_to_be_outshined():
    """The brief: herbalism's 161 ingredients must not outshine the new crafts. Each
    catalogue clears 100 and the shared shelf together clears 400."""
    counts = {}
    for p in sorted(Path("content/materials").glob("*.json")):
        counts[p.stem] = len(json.loads(p.read_text(encoding="utf-8"))["materials"])
    assert all(n >= 100 for n in counts.values()), counts
    assert sum(counts.values()) >= 400, counts
