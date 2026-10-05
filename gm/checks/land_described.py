"""The land outside a settlement, as the world wrote it — or not at all.

Two defects, both measured on Bobby's walk out of Vormoor (docs/playtest-2026-09-28.md,
items 19 and 20):

(a) **No land at all.** "With the current narration I would assume there was endless flat
    desert around me." A beat that walks the party out of the settlement, or answers a
    question about which way to go, and carries no word of the land the world describes.
    The repair asks for one physical detail from the world's own list — the opening's
    drawn-from-the-place check, the shape that held (CLAUDE.md: detect mechanically,
    repair with a targeted call).
(b) **Ground that is not there.** Turn 9 walked into "crushed pine and damp earth" and "a
    carpet of rotting needles" around a village whose continent is ash-fields, badlands and
    volcanic ridges. A sentence naming ground the Land lacks is flagged, the repair names
    the ground that is there, and the backstop cuts the sentence.

Only land cover is judged for (b) — forest, jungle, swamp, desert, tundra, hills,
mountain. Grass and fields are everywhere a road is, and "the water" is Vormoor's own
stilts; flagging them would put a false positive in every other beat.
"""
from __future__ import annotations

import re

from gm.narration import Finding

from . import _space

ORDER = 61
KINDS = frozenset({"land-not-described", "absent-ground"})
DOORS = frozenset({"turn", "outcome"})

JUDGED = ("forest", "jungle", "swamp", "desert", "tundra", "hills", "mountain")

# Words a narrator reaches for that the biome table does not list — the trees by name.
# "crushed pine" and "rotting needles" were Bobby's; the rest are the same family.
_EXTRA = {
    "forest": ("pine", "pines", "needles", "canopy", "oak", "oaks", "birch", "birches",
               "fir", "firs", "conifer", "conifers", "undergrowth", "treeline", "boughs"),
    "jungle": ("vines", "liana", "lianas"),
    "swamp": ("reeds", "bulrushes", "peat"),
    "tundra": ("permafrost", "snowfield"),
}
_STOP = frozenset("the and with that this from into over under few some where their "
                  "there held since before long peace within territory".split())


# Biome-table words that are also building stuff or a preposition. "it tastes of salt and
# old timber" (Bobby's turn 5, in a village of driftwood stilts) is a material, not a
# wood; "a heavy timber post" is a post. Measured: two false forests in one beat.
_NOT_LAND = frozenset({"timber", "wood", "down", "plain", "bank"})


def _patterns():
    from rules import biomes

    out = []
    for phrase, biome in biomes._LOOKUP.items():
        if biome in JUDGED and phrase not in _NOT_LAND:
            out.append((re.compile(r"(?<![\w-])" + re.escape(phrase)
                                   + r"(?:s|es|ed|y)?\b"), biome))
    for biome, extra in _EXTRA.items():
        for word in extra:
            out.append((re.compile(r"(?<![\w-])" + re.escape(word) + r"\b"), biome))
    out.append((re.compile(r"(?<![\w-])woods\b"), "forest"))
    return out


_PATTERNS: list = []


def _ground_of(sentence: str) -> set[str]:
    """The land cover a sentence names, by the biome table's words and the trees by name,
    matched compound-aware (as `geography.ground_in` is) so "ash-fields" is no field."""
    if not _PATTERNS:
        _PATTERNS.extend(_patterns())
    text = _space.unquoted(sentence).lower()
    return {biome for pattern, biome in _PATTERNS if pattern.search(text)}


def lexicon_words(ctx, land) -> set[str]:
    """What counts as a word of the land: the brief's own printed lexicon when the section
    ran, else the same list derived — the world's words and the biome phrases."""
    printed = (ctx.brief_facts or {}).get("land_around") or {}
    phrases = printed.get("lexicon")
    if not phrases:
        from gm.brief import land_around

        phrases = land_around.lexicon(land)
    out: set[str] = set()
    for p in phrases:
        for w in _space.words(p):
            for part in w.split("-"):
                if len(part) >= 4 and part not in _STOP:
                    out.add(part)
                    out.add(part.rstrip("s"))
    return out


def _went_out(ctx) -> bool:
    return any(e.get("direction") == "out" for e in _space.effects(ctx, "travel", "biome"))


def find(ctx) -> list[Finding]:
    land = _space.land(ctx)
    if land is None:
        return []
    found: list[Finding] = []
    outside = _space.here_setting(ctx) == "outside"
    asked = bool(((ctx.brief_facts or {}).get("roads_out") or {}).get("bearings_asked"))
    going_out = _went_out(ctx)

    if going_out or asked:
        lex = lexicon_words(ctx, land)
        said = set()
        for w in _space.words(ctx.text):
            for part in (w, *w.split("-")):
                said.add(part)
                said.add(part.rstrip("s"))
        if lex and not (said & lex):
            sample = ", ".join(sorted(lex)[:10])
            found.append(Finding(
                kind="land-not-described",
                detail="the party went outside and the page says nothing of the land",
                fix_hint=(f"Add one physical detail of the land around the settlement, "
                          f"from what the world says is there: {sample}."),
                weight=1))

    if outside or going_out:
        present = set(land.near) | set(land.beyond)
        here = str(getattr(ctx.scene, "at", "") or "")
        from rules import places

        present.add(places.terrain_of(here))
        flagged = []
        for s in _space.sentences(ctx.text):
            absent = sorted(b for b in _ground_of(s) & set(JUDGED) if b not in present)
            if absent:
                flagged.append((s, absent))
        if flagged:
            names = sorted({b for _s, bs in flagged for b in bs})
            there = ", ".join(land.near) or "open ground"
            further = f"; further out, {', '.join(land.beyond)}" if land.beyond else ""
            # The ground underfoot first, when the place has its own. The owner's
            # mountain (2026-10-05): this hint offered "close by, farmland, mountain,
            # desert" and the repair wrote "boulders weathered by the desert sun" — the
            # desert came from this list, not from the model's own invention.
            own = places.terrain_of(here)
            if own and own != places.URBAN:
                hint = (f"There is no {' or '.join(names)} here. The party stands on "
                        f"{own} ground: describe that, and nothing else underfoot.")
            else:
                hint = (f"There is no {' or '.join(names)} here. Describe the ground "
                        f"that is there: close by, {there}{further}.")
            found.append(Finding(
                kind="absent-ground",
                detail=f"the page puts {', '.join(names)} where the world has none",
                fix_hint=hint,
                weight=2, sentences=tuple(s for s, _b in flagged)))
    return found


def backstop(ctx, text: str, findings: list) -> tuple[str, list[str]]:
    """Cut a sentence that puts absent ground on the page. The lack of land (a) has no
    backstop: a missing detail cannot be cut into being."""
    notes: list[str] = []
    for f in findings:
        if f.kind != "absent-ground":
            continue
        for s in f.sentences:
            if s in text:
                text = re.sub(r"\s*" + re.escape(s), "", text, count=1).strip()
                notes.append(f"cut: {s[:80]}")
    return text, notes
