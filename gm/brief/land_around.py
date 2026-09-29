"""THE LAND AROUND: what ground lies about the settlement, in the world's own words.

Asked for on 2026-09-28 after the walk out of Vormoor: "With the current narration I
would assume there was endless flat desert around me except for far off mountains"
(docs/playtest-2026-09-28.md, 19). The export knew plenty — Drossakar's Geography is
"ash-fields, iron-rich badlands, geothermal vents", its Terrain "volcanic ridgelines,
black-rock canyons, a few fertile crater basins", Vormoor's roads all cross farmland
and then mountain — and none of it reached the brief. The next beat invented "trees grow
denser to the west", and the one after walked the party into them.

Inform's Recipe Book (§3.4) models the land around a set of rooms as a backdrop: seen and
described, never entered. This is that backdrop, written from `geography.land_around`:
the values are the world's words unedited and only the labels are the app's, so the
narrator describes the real land and a check (`gm/checks/land_described.py`) can read
what it was shown from this section's facts.

Printed when the party is outside, at a way in, or on a turn whose reading leaves, looks
for a bearing, or names ground — never in the middle of the market, where it is noise.
"""
from __future__ import annotations

ORDER = 30
SLOT = "place"
SCAFFOLD = (
    "THE LAND AROUND",
    "(fact; describe from these, in your own words):",
    "underfoot here:",
    "close by:",
    "further out:",
    "the wider land,",
    "weather:",
    "water:",
    "not here:",
    "(there is none near",
)
# The whole section prints only outside, at a way in, or on a turn that leaves or asks;
# every line of it is conditional on the world having said something.
SOMETIMES = SCAFFOLD


def _wanted_ground(reading) -> list[str]:
    """Ground the player's words name for a move: "into the gnarled dense trees"."""
    from rules import geography

    out: list[str] = []
    for a in (reading or {}).get("actions") or []:
        if a.get("act") not in ("go", "leave", "search", "look", "gather"):
            continue
        for slot in ("place", "object"):
            for biome in geography.ground_in(str(a.get(slot) or "")):
                if biome not in out:
                    out.append(biome)
    return out


def _wanted(ctx) -> bool:
    from rules import places

    here = ctx.here
    if here is not None and places.setting_of(getattr(here, "id", "")) == "outside":
        return True
    if here is not None and " ".join(str(here.name or "").split()).lower() \
            in places.ENTRANCES:
        return True
    reading = ctx.reading or {}
    acts = {a.get("act") for a in reading.get("actions") or []}
    if "leave" in acts:
        return True
    from gm.brief.roads_out import asks_a_bearing

    return asks_a_bearing(reading) or bool(_wanted_ground(reading))


def lexicon(land) -> list[str]:
    """The words a beat can use to describe this land: the world's own, split at commas,
    and the biome table's phrases for the ground near and beyond. What `land_described`
    looks for on the page."""
    from rules import biomes

    out: list[str] = []
    for _who, words in land.words:
        for part in str(words).replace(";", ",").split(","):
            part = " ".join(part.split()).strip(" .").lower()
            if part and part not in out and len(part) <= 60:
                out.append(part)
    for ground in (*land.near, *land.beyond):
        for phrase, biome in biomes._LOOKUP.items():
            if biome == ground and phrase not in out:
                out.append(phrase)
    return out


def section(ctx) -> tuple[str, dict]:
    location, world = ctx.location, ctx.world
    if not location or world is None or not _wanted(ctx):
        return "", {}
    from rules import biomes, geography, places

    if not places._settled(location, ""):
        return "", {}
    land = geography.land_around(world, location)
    if land.source == "unknown":
        return "", {}
    lines = [f"  THE LAND AROUND {location.name.upper()} (fact; describe from these, in "
             f"your own words):"]
    here = ctx.here
    if here is not None and places.setting_of(getattr(here, "id", "")) == "outside":
        lines.append(f"    underfoot here: {here.terrain}.")
    if land.near:
        lines.append(f"    close by: {', '.join(land.near)}.")
    if land.beyond:
        lines.append(f"    further out: {', '.join(land.beyond)}.")
    wider = [(who, words) for who, words in land.words if geography.ground_in(words)]
    for who, words in wider[:3]:
        lines.append(f"    the wider land, {who}: {words.rstrip('.')}.")
    if land.climate:
        lines.append(f"    weather: {land.climate.rstrip('.')}.")
    if land.water:
        lines.append(f"    water: {land.water.rstrip('.')}.")
    absent = [b for b in _wanted_ground(ctx.reading)
              if geography.grounded(land, b)[0] == "absent"]
    for b in absent:
        word = biomes.describe(b).split(",")[0].lower()
        lines.append(f"    not here: {word} (there is none near {location.name}).")
    return "\n".join(lines), {
        "near": list(land.near), "beyond": list(land.beyond),
        "words": [list(w) for w in wider[:3]], "climate": land.climate,
        "water": land.water, "absent": absent, "lexicon": lexicon(land),
        "underfoot": here.terrain if here is not None
        and places.setting_of(getattr(here, "id", "")) == "outside" else ""}
