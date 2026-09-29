"""BURNING HERE: a fire a spell lit, standing where the party stands.

Measured on the G2 cast-area run (2026-09-28/29): Burning Hands licked the undergrowth and
the tell said it caught; the next beat's brief said nothing of it, and the prose had the
party standing in a quiet wood. A fire is a fact of the place for as long as it burns
(`Engine._ignite`: 2d4 × 10 minutes, a patch that does not spread — owner, Q33), and the
narrator learns place facts from the brief.

One line, in words (docs/design-e-magic.md §5): what is alight and whether smoke comes off
it. No numbers and no compass — the minutes left, the squares and the save DCs are the
engine's, and the world has no bearings (item 19.5). Read from the scene's standing wards
by their `hazard` and `at` (written by `_ignite`), never from the words of a
manifestation's name, so a fire in a place the party has walked out of is not said here.
"""
from __future__ import annotations

ORDER = 50
SLOT = "place"
SCAFFOLD = (
    "BURNING HERE (fact):",
    "is alight",
    "and smoke drifts from it",
)
# Printed only while a fire stands where the party is.
SOMETIMES = SCAFFOLD


def fires_here(scene) -> list[dict]:
    """[{"what", "smoke": bool}] for each patch alight at the party's place, in the order
    they were lit, one row per thing burning."""
    at = str(getattr(scene, "at", "") or "")
    standing = {m.id for m in getattr(scene, "manifests", None) or []}
    out: dict[str, dict] = {}
    for w in getattr(scene, "wards", None) or []:
        spec = getattr(w, "spec", None) or {}
        rule = spec.get("hazard")
        if rule not in ("burning-brush", "smoke") or spec.get("at", "") != at:
            continue
        if getattr(w, "manifest_id", "") not in standing:
            continue
        what = str(spec.get("what") or "").strip() or "the ground"
        row = out.setdefault(what, {"what": what, "smoke": False, "fire": False})
        if rule == "smoke":
            row["smoke"] = True
        else:
            row["fire"] = True
    return [{"what": r["what"], "smoke": r["smoke"]} for r in out.values() if r["fire"]]


def section(ctx) -> tuple[str, dict]:
    fires = fires_here(ctx.scene)
    if not fires:
        return "", {}
    said = []
    for f in fires:
        where = "overhead" if f["what"] == "canopy" else "nearby"
        line = f"the {f['what']} {where} is alight"
        if f["smoke"]:
            line += ", and smoke drifts from it"
        said.append(line)
    text = "  BURNING HERE (fact): " + "; ".join(said) + "."
    return text, {"fires": fires}
