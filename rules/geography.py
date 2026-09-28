"""The world's geography, read once and handed out in words.

Six designs of the 2026-09-28 fix pass (docs/design-b-space.md, docs/design-c-starts.md)
needed the same handful of readings of an export: what ground lies around a settlement, what
the roads out of it are, where the party is in words the panel can print, what a person
does for a living, and how to strip a scale-blind export of the stock word "city". Written
five times they would drift, which is the error CLAUDE.md names ("when you fix a rule, grep
for every copy of it"), so they are written here once. docs/fix-interfaces.md §2.8 is the
register; nothing here changes shape without the owner.

**Pure and world-agnostic.** Every function takes the loaded world and plain values,
returns frozen values, and writes nothing — not the world (`load_cached` hands every caller
the same object), not the scene. Nothing keys on an Aurvantis name, id or fact label:
fact keys are read through a lexicon, ground comes from `play.travel`'s `crosses` (already
in the engine's biome words in all three test exports), and a settlement is recognised by
its scale, never by `kind == "CITY"`.

**Words, never numbers, for anything a narrator reads.** A journey is "about five days on
foot", never 38 hours or 72 miles: the third law is that no model authors a number, and a
number in the brief is one the model will start doing arithmetic with.

**Phase 1.** `where()` reproduces today's panel byte for byte, and nothing in the app calls
any of this yet; Lane B (the space functions) and Lane C (`role_of`, `in_its_own_words`,
`display_key`) wire it in Phase 2 (§3.2).
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from . import biomes as biomes_mod
from . import journey as journey_mod

# --- reading the world's land words -------------------------------------------------------

# The fact keys that carry ground, matched case-insensitively. The export does not agree
# with itself: Aurvantis and Pangrella write a continent's `Geography`, `Biomes`, `Terrain`
# and `Climate` and a nation's `Region`; the synthetic world writes `Landscape`, on the
# continent AND on each settlement. Pangrella's nations put their only real ground under
# `Region` ("Upper Pangrellan grasslands and Kyropticus deserts"). A fixed key list is the
# defect R0-3 measured in the brief — Landscape never arrived — so this is a lexicon.
LAND_KEYS = ("geography", "terrain", "landscape", "biome", "biomes", "climate", "region",
             "environment", "topography", "land")

# Climate is read for `Land.climate` and never for ground. Measured on Pangrella: the
# Korvathyr climate "temperate near the equator, polar at the edges" reads as tundra, and a
# town in the middle of a continent does not have tundra at its gate because the continent
# has poles. Aurvantis's "storms off the active peaks" adds nothing Terrain has not said.
_CLIMATE_KEYS = ("climate",)

# Aliases that are ground in a bestiary line and a preposition in a sentence. "down" is
# the downs in `biomes.ALIASES`, and "streams running down to the sea" is not hill country.
# The downs themselves are kept through their own two words below.
_NOT_GROUND = frozenset({"down"})
_EXTRA_GROUND = {"downs": "hills", "downland": "hills"}

_GROUND_WORDS: dict[str, str] = {
    **{w: b for w, b in biomes_mod._LOOKUP.items() if w not in _NOT_GROUND},
    **_EXTRA_GROUND,
}

# The compound-aware matcher (docs/fix-interfaces.md §1.3 B4). `biomes.detect` matches a
# leading `\b` only, so "ash-fields" is found as `field` after the hyphen and Drossakar's
# ash reads as grassland — Vormoor's derived biomes were `urban, desert, grassland,
# mountain`, and the grassland was this artefact.
#
# Tried and rejected, as the register records: a bare trailing `\b`. It breaks every
# plural — "canyons", "mountains", "fields", "badlands" — and once plurals are let back in
# with `s?\b`, "ash-fields" matches again. What makes "ash-fields" not a field is the
# hyphen BEFORE it: the word is a compound whose head is "ash". So the look-behind refuses
# a letter or a hyphen, and the tail allows the inflections landscape prose uses ("fields",
# "marshes", "wooded", "hilly") and no other letters, so "mine" is not found in "mineral".
#
# Kept here and NOT in `biomes.detect`: that default feeds the forage and herb tables,
# whose matching has never been measured against this change (§3.4, out of scope).
_SUFFIX = r"(?:s|es|ed|y)?"
_GROUND_PATTERNS: tuple[tuple[re.Pattern, str], ...] = tuple(
    (re.compile(r"(?<![\w-])" + re.escape(phrase) + _SUFFIX + r"\b"), biome)
    for phrase, biome in sorted(_GROUND_WORDS.items(), key=lambda kv: -len(kv[0]))
)


def ground_in(text: str) -> tuple[str, ...]:
    """Every biome a piece of the world's prose names, in the order the prose names them.

    Text order rather than table order, because the order is the world's: "farmland, then
    mountain" is nearest first, and a Land that reads nearest first can say so.
    """
    low = str(text or "").lower()
    hits: list[tuple[int, str]] = []
    for pattern, biome in _GROUND_PATTERNS:
        m = pattern.search(low)
        if m:
            hits.append((m.start(), biome))
    out: list[str] = []
    for _pos, biome in sorted(hits):
        if biome not in out:
            out.append(biome)
    return tuple(out)


def _entity(world, settlement):
    """The settlement entity, given one or its id."""
    if settlement is None or world is None:
        return settlement if not isinstance(settlement, str) else None
    if isinstance(settlement, str):
        return world.get(settlement)
    return settlement


def _settlement_row(world, entity_id: str) -> dict:
    for row in (getattr(world, "play", None) or {}).get("settlements") or []:
        if str(row.get("id") or "") == entity_id:
            return row
    return {}


def _land_facts(entity) -> list[tuple[str, str]]:
    """(key, value) for every fact on this entity whose key is in the lexicon."""
    facts = getattr(entity, "facts", None) or {}
    return [(str(k), str(v)) for k, v in facts.items()
            if str(k).strip().lower() in LAND_KEYS and str(v or "").strip()]


# The words that put a settlement on water, from `places._WATER_WORDS`, split in two.
# "water" alone is weak: Vormoor's export says "water rights" under Tension and Cause, and a
# quarrel over water is not a shoreline. The strong words (stilt, tide, shore, lake…) are
# read in any fact; "water" only where the fact describes the ground.
def _water_words() -> tuple[frozenset, frozenset]:
    from . import places as places_mod

    every = frozenset(places_mod._WATER_WORDS)
    return every - {"water"}, frozenset({"water"})


_TOKENS = re.compile(r"[a-z]+")


def _water_phrase(entity) -> str:
    """The settlement's own words that put it on water, unedited, or "".

    Facts and the summary only, not the prose: the prose is the generator's stock
    sentences, which is where "the city's own leading families" lives.
    """
    strong, weak = _water_words()
    facts = [(str(k), str(v)) for k, v in (getattr(entity, "facts", None) or {}).items()
             if str(v or "").strip()]
    summary = str(getattr(entity, "summary", "") or "").strip()
    everything = facts + ([("summary", summary)] if summary else [])
    for _key, value in everything:
        if set(_TOKENS.findall(value.lower())) & strong:
            return value.strip()
    grounded = [(k, v) for k, v in everything
                if k.strip().lower() in LAND_KEYS or k == "summary"]
    for _key, value in grounded:
        if set(_TOKENS.findall(value.lower())) & weak:
            return value.strip()
    return ""


# --- the land around a settlement ---------------------------------------------------------

@dataclass(frozen=True)
class Land:
    """What ground lies around one settlement, nearest first, in the world's own words.

    `near` and `beyond` are biome words from `biomes.BIOMES`, disjoint, never `urban`.
    `words` is (whose, what they wrote) for every land fact read, nearest first, so a
    brief can quote the world rather than paraphrase it. `source` is three-way, as
    `journey.pace` is: `exact` when the export stated the ground around this settlement,
    `derived` when it was read off routes and ancestors, `unknown` when nothing was said.
    """
    settlement_id: str
    near: tuple[str, ...]
    beyond: tuple[str, ...]
    words: tuple[tuple[str, str], ...]
    climate: str
    water: str
    coast: bool
    source: str


def _canon(word: str) -> str:
    got = biomes_mod.canonical(str(word or ""))
    return got or ""


def land_around(world, settlement) -> Land:
    """The Land around a settlement (an entity or its id).

    - `near` is the first ground of every road and river leg out (`crosses[0]`), then the
      ground the settlement's own land facts name ("a steep wooded combe"), then `coast`
      when the settlement is a port or the export says it is on the coast.
    - `beyond` is the rest of those legs' ground (`crosses[1:]`), then the ground its
      ancestors' land facts name, nearest ancestor first.
    - Sea legs are left out of both: their `crosses` describe the far shore (Vormoor to
      Moldwarren by sea "crosses" forest, and there is no forest near Vormoor).

    When the export ships `near` on the settlement's `play.settlements` row (an ask in
    docs/from-world-bible.md) it replaces the derived `near` outright, as a stated road
    beats a derived sea in `journey.crosses_water`.
    """
    entity = _entity(world, settlement)
    if entity is None:
        return Land(settlement_id=str(settlement or "") if isinstance(settlement, str) else "",
                    near=(), beyond=(), words=(), climate="", water="", coast=False,
                    source="unknown")
    sid = str(getattr(entity, "id", "") or "")
    row = _settlement_row(world, sid)

    near: list[str] = []
    beyond: list[str] = []

    def add(into: list[str], biome: str) -> None:
        if biome and biome != "urban" and biome not in near and biome not in beyond:
            into.append(biome)

    stated_near = [b for b in (_canon(w) for w in (row.get("near") or ())) if b]
    for biome in stated_near:
        add(near, biome)

    legs = journey_mod.legs_from(world, sid) if world is not None else []
    walked = [leg for leg in legs if not leg.by_sea or leg.by == "river"]
    if not stated_near:
        for leg in walked:
            if leg.crosses:
                add(near, _canon(leg.crosses[0]))
    words: list[tuple[str, str]] = []
    climate = ""
    own_ground: list[str] = []
    for key, value in _land_facts(entity):
        if key.strip().lower() in _CLIMATE_KEYS:
            climate = climate or value.strip()
            continue
        if (entity.name, value.strip()) not in words:
            words.append((str(entity.name), value.strip()))
        own_ground.extend(ground_in(value))
    if not stated_near:
        for biome in own_ground:
            add(near, biome)

    # Two shapes of the same ask are read (docs/from-world-bible.md): design B's
    # `coast: true|false` and design C's `water: "coast"|"river"|"lake"|""`. Either one
    # stated beats the port inference.
    said_coast = row.get("coast")
    said_water = row.get("water")
    said_water = (" ".join(said_water.split()).lower()
                  if isinstance(said_water, str) else None)
    if isinstance(said_coast, bool):
        coast = said_coast
    elif said_water is not None:
        coast = said_water == "coast"
    else:
        coast = bool(world is not None and journey_mod.is_port(world, sid))
    if coast:
        add(near, "coast")

    for leg in walked:
        for ground in leg.crosses[1:]:
            add(beyond, _canon(ground))
    for ancestor in (world.ancestors(sid) if world is not None else ()):
        for key, value in _land_facts(ancestor):
            if key.strip().lower() in _CLIMATE_KEYS:
                climate = climate or value.strip()
                continue
            said = (str(ancestor.name), value.strip())
            if said not in words and value.strip() not in {w for _, w in words}:
                words.append(said)
            for biome in ground_in(value):
                add(beyond, biome)

    water = _water_phrase(entity) or (said_water or "")
    if stated_near or isinstance(said_coast, bool) or said_water is not None:
        source = "exact"
    elif near or beyond or words or climate or water:
        source = "derived"
    else:
        source = "unknown"
    return Land(settlement_id=sid, near=tuple(near), beyond=tuple(beyond),
                words=tuple(words), climate=climate, water=water, coast=coast,
                source=source)


def _listed(items) -> str:
    items = [str(i) for i in items if str(i)]
    if len(items) <= 1:
        return "".join(items)
    return ", ".join(items[:-1]) + " and " + items[-1]


def grounded(land: Land, biome: str) -> tuple[str, str]:
    """Whether this ground is around the settlement, and what to say when it is not.

    ("near" | "beyond" | "absent" | "unknown", redirect words). The redirect is "" unless
    the ground is absent, and then names what IS there in the world's own biome words, so a
    refusal can be shown to the player and fixed by them (docs/design-b-space.md, 20.2).

    `unknown` is the three-way honesty `journey.pace` already uses: a world that said
    nothing about the land, or a word this app's biome list does not hold, is accepted
    and recorded rather than refused on a guess.
    """
    want = _canon(biome)
    if not want or land.source == "unknown":
        return "unknown", ""
    if want == "urban" or want in land.near:
        return "near", ""
    # The settlement's own words put it on the water (Vormoor's stilts) without making it
    # a port: the water is at the gate even when no coast is recorded, and `near` stays the
    # ground the roads start on.
    if want in ("water", "coast") and (land.coast or land.water):
        return "near", ""
    if want in land.beyond:
        return "beyond", ""
    if not land.near and not land.beyond:
        return "unknown", ""
    parts = [f"There is no {want} near here."]
    if land.near:
        parts.append(f"Close by it is {_listed(land.near)}.")
    if land.beyond:
        parts.append(f"Further out, {_listed(land.beyond)}.")
    return "absent", " ".join(parts)


# --- the roads out ------------------------------------------------------------------------

_NUMBER_WORDS = ("no", "one", "two", "three", "four", "five", "six", "seven", "eight",
                 "nine", "ten", "eleven", "twelve")


def _count_words(n: int, unit: str) -> str:
    """"a day", "three days" — a number word, never a digit."""
    n = int(n)
    if n <= 1:
        return f"a {unit}"
    said = _NUMBER_WORDS[n] if n < len(_NUMBER_WORDS) else "many"
    return f"{said} {unit}s"


_COMPASS = ("north", "north-east", "east", "south-east", "south", "south-west", "west",
            "north-west")
_COMPASS_ALIASES = {"n": "north", "ne": "north-east", "e": "east", "se": "south-east",
                    "s": "south", "sw": "south-west", "w": "west", "nw": "north-west",
                    "northeast": "north-east", "southeast": "south-east",
                    "southwest": "south-west", "northwest": "north-west"}


def _bearing(said: str, reverse: bool) -> str:
    """One of eight compass words, or "" — never derived, only read off the export."""
    word = " ".join(str(said or "").lower().replace("_", "-").split())
    word = _COMPASS_ALIASES.get(word.replace(" ", "-"), word.replace(" ", "-"))
    if word not in _COMPASS:
        return ""
    if reverse:
        word = _COMPASS[(_COMPASS.index(word) + 4) % len(_COMPASS)]
    return word


def _travel_row(world, here: str, there: str) -> tuple[dict, bool]:
    """The export's own row for this pair, and whether it was written the other way round."""
    for row in (getattr(world, "play", None) or {}).get("travel") or []:
        ends = (str(row.get("from_id") or ""), str(row.get("to_id") or ""))
        if ends == (here, there):
            return row, False
    for row in (getattr(world, "play", None) or {}).get("travel") or []:
        ends = (str(row.get("from_id") or ""), str(row.get("to_id") or ""))
        if ends == (there, here):
            return row, True
    return {}, False


@dataclass(frozen=True)
class Road:
    """One way out of a settlement to another, in words.

    `how` is `road`, `river`, `sea` (from a port), `sea-after-road` (the road to the coast
    and then a ship, `journey.describe`'s own wording) — or "" when the export did not say
    how the route is travelled and it does not cross water, because "by road" there would
    be a road fact this app invented. `bearing` is "" until an export states one: the
    world has no compass directions, and "north to Dustgate" was invented on 2026-09-28.
    """
    to_id: str
    to_name: str
    to_kind: str
    how: str
    time_words: str
    crosses: tuple[str, ...]
    crosses_words: str
    leaves_from: str
    bearing: str
    source: str


# A route without a stated mileage has a time the engine derives from the containment tree
# (`journey._depth_apart`), and the journey op spends it. The brief does not repeat it as a
# distance: "how far, nobody has written down" is the truth, and the ask for miles is in
# docs/from-world-bible.md (design B §4, 17.4).
UNWRITTEN_DISTANCE = "how far, nobody has written down"


def _walk_time_words(hours: int) -> str:
    if hours <= 4:
        return "a few hours on foot"
    if hours < journey_mod.HOURS_PER_DAY:
        return "most of a day on foot"
    return "about " + _count_words(round(hours / journey_mod.HOURS_PER_DAY), "day") + " on foot"


def _sea_time_words(hours: int) -> str:
    from . import ships as ships_mod

    days = max(1, round(max(1, hours) / ships_mod.HOURS_AT_SEA))
    return "about " + _count_words(days, "day") + " aboard"


def roads_out(world, settlement, speed_ft: int = 30) -> tuple[Road, ...]:
    """Every route out of a settlement, as `journey.legs_from` reads it, in words.

    Wraps `legs_from` and `hours_for` rather than re-deriving either, so the days the brief
    states are the days `_op_journey` will spend: when Lane B makes `by: "road"` mean the
    road column (Q12), every Road here follows without a line changing.
    """
    entity = _entity(world, settlement)
    if entity is None or world is None:
        return ()
    sid = str(getattr(entity, "id", "") or "")
    land = land_around(world, entity)
    out: list[Road] = []
    for leg in journey_mod.legs_from(world, sid):
        by = str(leg.by or "").strip().lower()
        sea = leg.by_sea and by != "river"
        if by == "river":
            how = "river"
        elif sea:
            how = "sea" if leg.from_port else "sea-after-road"
        elif by == "road" or leg.road:
            how = "road"
        else:
            how = ""

        hours, _said, _how = journey_mod.hours_for(leg, speed_ft)
        if leg.source != "exact":
            time_words = UNWRITTEN_DISTANCE
        elif leg.by_sea:
            time_words = _sea_time_words(hours)
        else:
            time_words = _walk_time_words(hours)

        # A sea leg's `crosses` is the far shore, not the passage (see `land_around`).
        crosses = () if sea else tuple(str(c) for c in leg.crosses if str(c))
        crosses_words = ", then ".join(crosses)

        row, reverse = _travel_row(world, sid, leg.to_id)
        leaves_from = ""
        said_leaves = str(row.get("leaves_by") or "") if not reverse else ""
        if said_leaves:
            from . import places as places_mod

            found = next((p for p in places_mod.home_set(entity) if p.id == said_leaves),
                         None)
            leaves_from = found.name if found is not None else ""
        if not leaves_from:
            if leg.by_sea and leg.from_port:
                leaves_from = "the docks"
            elif leg.by_sea and (land.coast or land.water):
                leaves_from = "the shore"
            else:
                leaves_from = "the outskirts"

        target = world.get(leg.to_id)
        scale = str(getattr(target, "scale", "") or "").strip()
        if scale:
            from . import places as places_mod

            to_kind = f"a {places_mod.scale_of(target)}"
        else:
            to_kind = ""
        out.append(Road(
            to_id=leg.to_id, to_name=leg.to_name, to_kind=to_kind, how=how,
            time_words=time_words, crosses=crosses, crosses_words=crosses_words,
            leaves_from=leaves_from, bearing=_bearing(row.get("bearing"), reverse),
            source=leg.source))
    return tuple(out)


# --- where the party is -------------------------------------------------------------------

@dataclass(frozen=True)
class Where:
    """The panel's one line: `setting` is in | under | outside | road."""
    setting: str
    label: str
    detail: str


def where(world, scene, here=None) -> Where:
    """Where the party is, as the panel and the brief should both say it.

    PHASE 1 reproduces today's panel exactly (docs/fix-interfaces.md §2.8), so S3 can
    route `/api/state` through it with no visible change: `02-state.js` prints
    "{location} · {scale} · {biome}", with `location` the settlement's name and `scale`
    `places.scale_of` of it. Lane B changes the label outside ("near Vormoor · farmland")
    in Phase 2; `here` is accepted now so that change needs no new signature.
    """
    from . import places as places_mod

    location_id = str(getattr(scene, "location_id", "") or "")
    location = world.get(location_id) if (world is not None and location_id) else None
    name = str(getattr(location, "name", "") or "") if location is not None else ""
    scale = places_mod.scale_of(location) if location is not None else ""
    label = f"{name} · {scale}" if scale else name
    detail = str(getattr(scene, "biome", "") or "")
    setting = "in" if detail == places_mod.URBAN else "outside"
    return Where(setting=setting, label=label, detail=detail)


def walk_words(minutes: int) -> str:
    """A walk's length in words: "a few minutes' walk", "the better part of an hour".

    Never the count. The clock pop-up shows the time to the player; the narrator is told
    how long it felt, which is all prose needs and nothing it can do sums with.
    """
    m = int(minutes or 0)
    if m <= 0:
        return ""
    if m <= 2:
        return "a minute or two's walk"
    if m <= 9:
        return "a few minutes' walk"
    if m <= 20:
        return "a quarter of an hour"
    if m <= 40:
        return "half an hour"
    if m <= 55:
        return "the better part of an hour"
    if m <= 75:
        return "about an hour"
    if m <= 105:
        return "an hour and more"
    hours = round(m / 60)
    if hours < journey_mod.HOURS_PER_DAY:
        return "about " + _count_words(hours, "hour")
    if m <= journey_mod.HOURS_PER_DAY * 60 + 60:
        return "a long day's walk"
    return "more than a day's walk"


# --- people and the world's stock words (Lane C's three) ----------------------------------

# Where a person's work is written, in the order an export is likeliest to mean it. The
# cast list's own `role` is "Person" for all 256 of Aurvantis's cast and all 47 of
# Pangrella's, while every one of their entities says what they do ("Role: healer"). So
# the background tie looking for a healer matched nobody, and the fallback handed every
# campaign Drenn Ironvale (playtest 2026-09-28, item 8).
ROLE_KEYS = ("role", "occupation", "profession", "position", "title")
GENERIC_ROLES = frozenset({"", "person", "character", "npc", "people", "individual"})


def role_of(world, cast_row) -> str:
    """What this person does, in the world's words, or "" when the world never said.

    The entity's own role fact first (any of `ROLE_KEYS`, case-insensitive), then the cast
    row's `role` unless it is a placeholder ("Person"), then "". Returned as the world
    wrote it — Pangrella's "Innovative developer and expert in magnetic shift adaptation"
    stays whole — so a caller matches by word and never against a list of trades.
    """
    row = cast_row if isinstance(cast_row, dict) else {}
    entity_id = str(row.get("id") or row.get("entity_id") or "")
    entity = world.get(entity_id) if (world is not None and entity_id) else None
    facts = getattr(entity, "facts", None) or {}
    by_key = {str(k).strip().lower(): str(v or "").strip() for k, v in facts.items()}
    for key in ROLE_KEYS:
        if by_key.get(key):
            return by_key[key]
    said = " ".join(str(row.get("role") or "").split())
    if said.lower() in GENERIC_ROLES:
        return ""
    return said


# "the city" and "the city's", lower case only: "the City Watch" is a name, and "the city
# of Ledgerwarren" is another place altogether, which the look-ahead leaves alone. A
# hyphenated "the city-state" is left too.
_THE_CITY = re.compile(r"\b(the|The|THE)(\s+)city\b(?!-)(?!\s+of\b)")


def in_its_own_words(text: str, scale: str) -> str:
    """The world's text with its stock "the city('s)" put back to the settlement's scale.

    World Bible's settlement templates are scale-blind: all 64 Aurvantis settlements say
    "drawn… from the city's own leading families", and 48 of them are villages or towns.
    The opening model copied it — Vormoor, a village, became "a sprawling settlement… the
    city's bustling thoroughfares" (playtest 2026-09-28, item 1). Unchanged when the scale
    is "" (unknown: claim nothing) or "city" (the words were right).
    """
    scale = " ".join(str(scale or "").split()).lower()
    if not scale or scale == "city" or not text:
        return text
    return _THE_CITY.sub(lambda m: f"{m.group(1)}{m.group(2)}{scale}", text)


# Fact keys that carry a scale word of their own. "Urban Life" on a village is the same
# stock-template defect as "the city's", one level up, and it reaches the model as a label.
_DISPLAY_KEYS = {"urban life": "Daily life", "city life": "Daily life"}


def display_key(key: str) -> str:
    """A fact key as the brief and the page should show it: "Urban Life" -> "Daily life".

    Every other key is returned exactly as the world wrote it.
    """
    said = str(key or "")
    return _DISPLAY_KEYS.get(" ".join(said.split()).lower(), said)
