"""The settlement's own fact fields, by key: "  Urban Life: …".

Moved out of `prompts.scene_brief` unchanged (fix pass S2, docs/fix-interfaces.md §2.2).
R0 measured that these eight keys miss Landscape, Daily Life, Customs and Conflict, which
other exports use; Lane C adds the key lexicon here in Phase 2 (§3.4). Today's bytes first.
"""
from __future__ import annotations

ORDER = 40
SLOT = "place"
# Only the separator is fixed: the keys and their values are the world's own words.
SCAFFOLD = ()

KEYS = ("Urban Life", "Social Classes", "Architecture", "Governance",
        "Formal Power", "Shadow Power", "Tension", "Daily Norms")


def section(ctx) -> tuple[str, dict]:
    location = ctx.location
    if not location:
        return "", {}
    lines, printed = [], {}
    for key in KEYS:
        if location.fact(key):
            lines.append(f"  {key}: {location.fact(key)}")
            printed[key] = location.fact(key)
    return "\n".join(lines), ({"facts": printed} if printed else {})
