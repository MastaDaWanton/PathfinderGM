"""Where the party is standing, as something the engine can refuse.

The scene had four spatial authorities and none of them was derived from any other:
`location_id` (a World Bible entity), `spot` (free text), `biome` (a closed enum) and the
tactical `zones`/`positions`/`grid`. A merchant's stall and the square outside it are the
same location and the same biome, so walking out of one changed nothing the engine could
see: the merchant stayed in the scene, the brief went on describing his stall, and the
next beat put the player back inside a building they had left. The prose moved and the
state did not.

Every tradition that has solved this — Inform's containment, Diku's `IN_ROOM`, LambdaMOO's
`location`, the Z-machine's single parent pointer, Evennia, Godot's rooms owning their
occupants — holds exactly ONE spatial relation and derives everything else from it. This
module is that one relation's vocabulary.

**A place is generated, never invented.** World Bible describes a city and stops: the
children of a CITY in the export are CHARACTERs, so the rooms genuinely do not exist in
the world data and cannot simply be read. But a model minting place names per turn is
exactly the free-text `spot` this replaces — the narrator establishing a fact rather than
proposing one. So the app generates them: a small closed set per location, seeded off the
location's own durable id, so the same town has the same rooms in every session and after
every reload. The model chooses one that exists and is refused if it does not, which is
the courtesy the ref registry has always extended to people and never to places, though
`gm/prompts.py`'s own docstring has asked for it since it was written.

**The ground is inside the id.** `{location}~urban:the-market`,
`{location}~forest:the-approach`. Stage 8c wanted the biome read off the place and the
place seeded off the biome — a loop — and the review found the other way out: a
`Scene` holds no world by design, so `scene.biome` cannot look anything up, but it can
parse. `terrain_of(scene.at)` is the whole derivation, and the eleven readers that want
the canonical enum string get it from the one coordinate that has one writer.

When World Bible ships towns and the places in them, an authored list replaces a generated
one at `home_set` and nothing else changes.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass

# How many spots a location gets. Fate caps a conflict at "two to four zones"; Inform's
# Recipe Book calls for "a small number of named positions". The ceiling is the point —
# an open-ended list is free text wearing a tuple, and every extra spot is somewhere the
# narrator can strand the player with nothing to do.
MOST_SPOTS = 6

# The character between a location and its ground inside a place id. Never a `:` — that
# already separates the ground from the spot — and never something a World Bible id can
# contain (twelve hex characters, measured against the fixture).
SEP = "~"

# What a settlement is made of, in the order a generated town gets them. Deliberately
# generic: these are read against the location's own facts below, and a name the world
# actually uses beats any of them.
_SETTLEMENT = (
    ("the market", "where the stalls are"),
    ("the gate", "the way in and out"),
    ("the tavern", "somewhere to sit down"),
    ("the temple", "somewhere to be quiet"),
    ("the back streets", "where nobody is watching"),
    ("the workshops", "where the trades are"),
)

# The same for somewhere nobody lives. A ruin or a stretch of forest still needs more than
# one place to stand, or "I go deeper in" is unrepresentable.
_WILD = (
    ("the approach", "the way you came"),
    ("the heart of it", "as far in as this goes"),
    ("the edge", "where it thins out"),
    ("the high ground", "somewhere to see from"),
)

# --- door one: places the world implies ------------------------------------------------------
#
# "why did it not make a docks?" Vyrakon's export says "port access" and "cyclone-prone
# coastlines", and the settlement table had no harbour row, so the facts that justified
# one were never read. Each row: the words that imply the place, in the settlement's own
# facts and paragraphs, and the spot they imply. Read mechanically, deterministic,
# nothing the model authors — the world said it.
IMPLIED = (
    (("port", "harbour", "harbor", "dock", "docks", "quay", "wharf", "fishing", "ships",
      "shipping", "boats"), ("the docks", "where the boats come in")),
    (("river", "bridge", "ferry", "crossing"), ("the bridge", "over the water")),
    (("guild", "guilds", "guildhall"), ("the guildhall", "where the trades meet")),
    (("library", "archive", "archives", "scriptorium", "scribes"),
     ("the library", "where the records are kept")),
    (("walls", "fort", "fortress", "the keep", "a keep", "castle", "citadel", "garrison"),
     ("the keep", "where the soldiers are")),
    (("the mine", "a mine", "mines", "mining", "quarry", "ore"),
     ("the mine head", "where the ore comes up")),
    (("shrine", "temple", "cathedral", "priests", "prayers", "faith"),
     ("the shrine", "somewhere to be quiet")),
    (("the well", "a well", "wells", "wellhead", "cistern", "fountain"),
     ("the well", "where the water is")),
)
# Some cues are phrases, and that is the fix for a word that is also a common verb or
# adverb. Reported from the World Bible side on 2026-09-15 and then measured here against
# its 64-settlement export:
#
#   "well" fired in 64 of 64 — every one of them on "that works well enough in"
#   "keep" fired in 16 of 64 — every one of them on "tax-farmers who keep a cut of"
#
# Not one real well and not one real keep among them. That is worse than noise: a
# settlement is capped at `MOST_SPOTS`, so a phantom place takes a real one's slot.
#
# The reported fix was to swap the words — `well` to `wells`, and drop `keep` because the
# row already has `fortress` and `garrison`. That works and costs two real hits: "the
# well" is how prose names a village's only well, and `keep` is the exact word for the
# building. So the matcher learned phrases instead, which is four lines and keeps both.
# `mine` went the same way pre-emptively: it is also the possessive pronoun, it had not
# fired yet in either world, and finding out later costs a place.

# A settlement may carry this many implied spots over its generated set — a port town
# gets its docks even when the table has filled six — and no more.
MOST_IMPLIED = 2

# --- door three: ground you go into ----------------------------------------------------------
#
# "what if i choose to explore the sewers or i go outside the city to a cave." The
# roguelike answer: not authored, GENERATED ON ENTRY FROM A SEED, so the same stairs lead
# to the same cellar next time. Each kind: the ground it stands on (the engine's own biome
# vocabulary), the spots it is made of, and how many hours the way there costs when it
# lies outside the settlement (0 for something under or inside it).
VENTURES: dict[str, dict] = {
    "sewers": {"label": "the sewers", "terrain": "underground", "hours": 0,
               "spots": (("the outfall", "where it meets the daylight"),
                         ("the main channel", "the way the water goes"),
                         ("the sump", "as low as it goes"))},
    "cellar": {"label": "the cellars", "terrain": "underground", "hours": 0,
               "spots": (("the stair", "the way down"),
                         ("the vaults", "where things are kept"))},
    "crypt": {"label": "the crypt", "terrain": "ruins", "hours": 0,
              "spots": (("the stair", "the way down"),
                        ("the niches", "where the dead are"),
                        ("the deep chamber", "as far in as this goes"))},
    "rooftops": {"label": "the rooftops", "terrain": "urban", "hours": 0,
                 "spots": (("the ridge", "the high way across"),
                           ("the gutter", "where it drops"))},
    "alley": {"label": "the back alley", "terrain": "urban", "hours": 0,
              "spots": ()},
    "cave": {"label": "the cave", "terrain": "underground", "hours": 2,
             "spots": (("the mouth", "the way in and out"),
                       ("the throat", "where the light goes"),
                       ("the deep chamber", "as far in as this goes"))},
    "mine": {"label": "the old mine", "terrain": "underground", "hours": 2,
             "spots": (("the adit", "the way in"),
                       ("the gallery", "where they dug"),
                       ("the flooded level", "as low as it goes"))},
    "ruins": {"label": "the ruins", "terrain": "ruins", "hours": 2,
              "spots": (("the gate", "the way in"),
                        ("the courtyard", "the open middle"),
                        ("the undercroft", "as low as it goes"))},
    "tower": {"label": "the tower", "terrain": "ruins", "hours": 1,
              "spots": (("the foot", "the way in"),
                        ("the top", "somewhere to see from"))},
}
# How many places may hang off one parent, in play. Fate caps a conflict at two to four
# zones and Inform calls for "a small number of named positions"; the ceiling applies per
# parent, not to the world — a town of six, an alley of three, a sewer of four — so the
# model's choice stays small while the world grows.
MOST_CHILDREN = 6

# The ground a settlement stands on, by construction. Four predicates used to answer
# "is this a town" — `biomes.from_world`'s `kind == "CITY"`, `_settled` here,
# `_at_market`'s `== "urban"` and the injector's `_SETTLEMENT_KINDS` — and the review
# measured them disagreeing: a village is settled to three of them and grassland to the
# fourth. The settlement set says `urban` and asks nobody.
URBAN = "urban"


@dataclass
class Place:
    """One spot a party can be standing in, and what leads out of it.

    A KIND, in the `Manifestation` mould — a scene-held dataclass with `as_dict` /
    `from_dict` — and deliberately NOT an `ActiveEffect`. A naive reading of law 2 says
    every change travels as an effect, but a place has no duration, no stacking policy,
    and removing one must not leave the party nowhere. Law 2 governs numbers that change
    and wear off.

    `exits` is the move vocabulary and the whole reason this is not a string: the engine
    can refuse a destination that is not on it. Adjacency only — Fate shipped weighted
    zone borders and then deleted them, and obstruction belongs in states and effects
    rather than in a cost table nobody would tune.
    """

    id: str = ""
    name: str = ""
    about: str = ""
    # For a place minted in play (doors two and three): the place it hangs off, who
    # holds it, and how it came to be — `found` (the player's declaration, with an
    # owner) or `venture` (ground gone into, generated from a seed) — the same
    # provenance rule every number carries. Empty on a generated place.
    parent: str = ""
    owner: str = ""
    origin: str = ""
    # Read off the id, never stored beside it. `biome` as a sibling field on the scene
    # is precisely what let "both are urban" defeat the transition.
    terrain: str = ""
    exits: tuple[str, ...] = ()
    # True when the place is named but cannot be entered — Diku's `<room linked>` of -1,
    # "non-functional exits that display descriptions only". It lets the narrator write
    # "an alley runs east" without minting a node, and keeps the pressure that would
    # otherwise force the enumeration back open.
    described_only: bool = False

    def as_dict(self) -> dict:
        return {"id": self.id, "name": self.name, "about": self.about,
                "terrain": self.terrain, "exits": list(self.exits),
                "described_only": self.described_only,
                "parent": self.parent, "owner": self.owner, "origin": self.origin}


def from_dict(d: dict) -> Place:
    return Place(
        id=str(d.get("id") or ""), name=str(d.get("name") or ""),
        about=str(d.get("about") or ""), terrain=str(d.get("terrain") or ""),
        exits=tuple(str(x) for x in (d.get("exits") or ())),
        described_only=bool(d.get("described_only")),
        parent=str(d.get("parent") or ""), owner=str(d.get("owner") or ""),
        origin=str(d.get("origin") or ""),
    )


# --- the id, and what it says ------------------------------------------------------------

def region_key(location_id: str, terrain: str) -> str:
    """`{location}~{terrain}`: the prefix every place on that ground shares."""
    return f"{str(location_id or '').strip()}{SEP}{str(terrain or '').strip().lower()}"


def terrain_of(place_id: str) -> str:
    """The ground a place id stands on, or "" when the id does not say.

    The parse IS `scene.biome`. No lookup, no world, no table — which is what lets a
    deep-copied Scene answer the question and a save written by an older build
    (`at == ""`) answer honestly with nothing.
    """
    head = str(place_id or "").split(":", 1)[0]
    if SEP not in head:
        return ""
    return head.rsplit(SEP, 1)[1].strip().lower()


def location_of(place_id: str) -> str:
    head = str(place_id or "").split(":", 1)[0]
    return head.rsplit(SEP, 1)[0] if SEP in head else head


# --- storeys ---------------------------------------------------------------------------
#
# A building's floors are PLACES, joined by stairs, and not a third dimension of the
# tactical grid. That is the shape every system that keeps verticality and stays legible
# settled on — Foundry's Levels, Caves of Qud's strata, Dwarf Fortress's z-levels are all
# stacked flat maps with a transition between them — and it is also the shape this app was
# already in: `mint` has had a branch for "a different ground under the same roof: the
# sewers under a town" since places were written. A storey is that, pointing up.
#
# The storey lives in the id, like the ground does, because the id is the one spatial
# authority and a second field would be the fifth one `docs/places-plan.md` refused. `^` is
# safe as the separator: `_slug` strips everything but `[a-z0-9 ]`, a location id is twelve
# hex characters, and a terrain is a single lower-case word, so nothing else can ever
# contain it.
STOREY = "^"

# What a floor is called, by how far it is from the ground one. "The undercroft" rather
# than "the cellar" deliberately: `VENTURES` already offers "the cellars" as somewhere you
# venture into from a town, and two places a player can reach by typing almost the same
# words is a way to pick the wrong one.
_STOREY_NAMES: dict[int, tuple[str, str]] = {
    2: ("the top floor", "as high as the stairs go"),
    1: ("the upper floor", "one flight up"),
    -1: ("the undercroft", "under the boards"),
}


def storey_of(place_id: str) -> int:
    """Which floor this id names, zero being the one you walk in on.

    Parsed, never stored — the same arrangement as `terrain_of`, so a deep-copied Scene
    can answer it and a save written before storeys existed answers 0, which is true.
    """
    tail = str(place_id or "").rsplit(STOREY, 1)
    if len(tail) < 2:
        return 0
    try:
        return int(tail[1])
    except ValueError:
        return 0


def base_of(place_id: str) -> str:
    """The building, with the floor taken off."""
    text = str(place_id or "")
    return text.rsplit(STOREY, 1)[0] if STOREY in text else text


def storey_id(place_id: str, level: int) -> str:
    """The id of a given floor of whatever building this id is in."""
    base = base_of(place_id)
    return base if not level else f"{base}{STOREY}{int(level)}"


def is_indoors(place_id: str, terrain: str = "") -> bool:
    """Whether this place has a roof on it.

    Asked of `floorplan`, which already answers it: a shape with a `ceiling` is a room and
    one without is under the sky. One source, so a tavern cannot be indoors for the
    purposes of stairs and outdoors for the purposes of flying over it.
    """
    from . import floorplan

    return floorplan.shape_for(place_id, terrain).ceiling is not None


def storeys(place_id: str, terrain: str = "") -> tuple[int, ...]:
    """Every floor this building has, in order, ground floor included.

    Deterministic off the building's own id, like everything else about a place: the same
    tavern has the same number of floors for ever, and none of it is saved. Outdoors is
    always the single floor you are standing on — a market has no upstairs.
    """
    if not is_indoors(place_id, terrain):
        return (0,)
    n = _seed(base_of(place_id))
    up = n % 3                 # nothing, one floor, or two
    down = (n >> 5) % 2        # and an undercroft, or not
    return tuple(range(-down, up + 1))


def storey_set(place: "Place") -> tuple["Place", ...]:
    """The floors above and below this one, as places, wired to the stairs.

    The ground floor is `place` itself and is not repeated. Each floor keeps the
    building's ground and parent — an upper room is still `urban` — because the terrain is
    about what the ground is made of and not about how far up it is.
    """
    levels = storeys(place.id, place.terrain)
    out: list[Place] = []
    for level in levels:
        if level == 0 or level not in _STOREY_NAMES:
            continue
        label, about = _STOREY_NAMES[level]
        reachable = [storey_id(place.id, other) for other in levels
                     if abs(other - level) == 1]
        out.append(Place(
            id=storey_id(place.id, level),
            name=f"{label} of {place.name}" if place.name else label,
            about=about, terrain=place.terrain, exits=tuple(reachable),
            parent=place.id, origin="storey"))
    return tuple(out)


def stairs_from(place_id: str, terrain: str = "") -> tuple[str, ...]:
    """The ids one flight up and one flight down, where those floors exist.

    Only adjacent floors: you cannot step from the undercroft to the top of the house
    without passing the room between, which is the whole reason these are places joined by
    stairs rather than a coordinate anybody can name.
    """
    here = storey_of(place_id)
    return tuple(storey_id(place_id, other)
                 for other in storeys(place_id, terrain)
                 if abs(other - here) == 1)


# --- the sets ----------------------------------------------------------------------------

def _seed(location_id: str) -> int:
    """A number that is the same for this location for ever.

    Not `hash()`: Python salts string hashing per process, so the same town would lay
    itself out differently after a restart — the class of bug the campaign save exists to
    prevent, arriving through the back door.
    """
    return int(hashlib.sha256(str(location_id or "nowhere").encode()).hexdigest()[:8], 16)


def _settled(location, terrain: str = "") -> bool:
    """Whether this is somewhere people live, and so which table it is made of.

    Falls back to the ground underfoot when the world entity is not to hand, which is
    derivation rather than a guess: `urban` means streets and yards, and the app's own
    biome table says so. An engine built without a world still has `scene.location_id`
    and the ground its place id carries, and between them that is enough.
    """
    kind = str(getattr(location, "kind", "") or "").upper()
    scale = str(getattr(location, "scale", "") or "").lower()
    if kind or scale:
        return ("CITY" in kind or "SETTLEMENT" in kind or "TOWN" in kind
                or scale in ("city", "town", "village", "hamlet", "settlement"))
    # A bare id with nothing said about its ground is a settlement. Every location a
    # campaign starts in is one (twelve of twelve in the fixture, all CITY), and the
    # alternative — reading the ground the party is CURRENTLY on — is what made a
    # world-less engine forget it had a town to go back to the moment the party
    # walked into the forest. Only an explicit non-urban hint makes a wild site.
    return str(terrain or "").lower() in ("", URBAN)


import re as _re

_WORDS = _re.compile(r"[a-z][a-z'-]+")


def _slug(label: str) -> str:
    return "-".join(_re.sub(r"[^a-z0-9 ]", "", str(label).lower()).split())


def _build(location_id: str, terrain: str, table) -> tuple[Place, ...]:
    n = 3 + _seed(location_id) % (min(MOST_SPOTS, len(table)) - 2)
    chosen = list(table[:n])
    prefix = region_key(location_id, terrain)
    ids = [f"{prefix}:{_slug(label)}" for label, _ in chosen]
    # Everywhere connects to everywhere else on one ground. A settlement is not a maze,
    # and a graph the player has to solve is a different game from the one this is.
    return tuple(
        Place(id=pid, name=label, about=about, terrain=terrain,
              exits=tuple(x for x in ids if x != pid))
        for pid, (label, about) in zip(ids, chosen)
    )


def home_set(location, terrain_hint: str = "") -> tuple[Place, ...]:
    """The location's own places — a settlement's rooms, or a wild site's reaches.

    `location` may be a world entity or a bare id. Only the id is load-bearing: it seeds
    the layout so a town has the same rooms in every session, and the rest sharpens the
    naming when it is available. A settlement is `urban` whatever the continent's facts
    say; a site that is not one stands on `terrain_hint`, which the engine reads off the
    world when it has one and off the party's current place when it does not. With no id
    at all the party still has to be somewhere, so there is exactly one place with no
    exits and no ground — which refuses every move rather than inventing a destination,
    the fail-closed direction.
    """
    here = str(getattr(location, "id", None) or location or "").strip()
    name = str(getattr(location, "name", "") or "").strip()
    if not here:
        return (Place(id="here", name=name or "here", about="", terrain="", exits=()),)
    hint = str(terrain_hint or "").strip().lower()
    if _settled(location, hint):
        return _with_implied(_build(here, URBAN, _SETTLEMENT), location)
    return _build(here, hint or "grassland", _WILD)


def implied_spots(location) -> tuple[tuple[str, str], ...]:
    """The spots a settlement's own facts and paragraphs imply, in table order."""
    facts = getattr(location, "facts", None) or {}
    prose = getattr(location, "prose", "") or ""
    text = " ".join([*(str(v) for v in facts.values()), str(prose)]).lower()
    words = set(_WORDS.findall(text))
    out = []
    for cues, spot in IMPLIED:
        if any(_cue_fires(c, text, words) for c in cues):
            out.append(spot)
    return tuple(out)


def _cue_fires(cue: str, text: str, words: set) -> bool:
    """Whether one cue is in this settlement's words.

    A single word is asked of the word SET, which is what this always did and is why a
    cue can never match half of a longer word. A cue with a space in it is asked of the
    text, because a set of single words cannot answer a two-word question — and two-word
    cues are the whole reason this function exists. See the note under `IMPLIED`.
    """
    if " " in cue:
        return _re.search(rf"\b{_re.escape(cue)}\b", text) is not None
    return cue in words


def _with_implied(home: tuple[Place, ...], location) -> tuple[Place, ...]:
    """A settlement's generated set plus the spots its own words imply — the docks
    for a port town — up to `MOST_IMPLIED`, connected like the rest."""
    if not home:
        return home
    have = {p.name for p in home}
    extra = [s for s in implied_spots(location) if s[0] not in have][:MOST_IMPLIED]
    if not extra:
        return home
    prefix = region_key(location_of(home[0].id), home[0].terrain)
    new_ids = [f"{prefix}:{_slug(label)}" for label, _ in extra]
    all_ids = [p.id for p in home] + new_ids
    rebuilt = [Place(id=p.id, name=p.name, about=p.about, terrain=p.terrain,
                     exits=tuple(x for x in all_ids if x != p.id),
                     described_only=p.described_only, parent=p.parent,
                     owner=p.owner, origin=p.origin) for p in home]
    rebuilt += [Place(id=pid, name=label, about=about, terrain=home[0].terrain,
                      exits=tuple(x for x in all_ids if x != pid), origin="world")
                for pid, (label, about) in zip(new_ids, extra)]
    return tuple(rebuilt)


def region_set(location_id: str, terrain: str) -> tuple[Place, ...]:
    """Open ground of one kind around a location: the forest outside the town.

    Derivable with nothing but the location id and a biome word, so a world-less test
    engine can stand in the forest and a save that predates places can be healed onto
    the ground it recorded.
    """
    # "nowhere" rather than the exitless fallback: a scene with no location can still
    # be stood on real ground for the foraging tables, and the id has to say which.
    here = str(getattr(location_id, "id", None) or location_id or "").strip() or "nowhere"
    return _build(here, str(terrain or "").strip().lower() or "grassland", _WILD)


def for_scene(location, at: str, terrain_hint: str = "",
              founded=()) -> tuple[Place, ...]:
    """Every place the party can name from where they stand: home, plus the ground
    they are on if it is not home, plus what play has minted here (`founded`).

    The ONE derivation. `Engine.places()` and the scene brief both used to compute this
    separately — two copies of a rule, the trap CLAUDE.md names — and now both call here.
    Region places share the `_WILD` names, and only one region is ever current, so a
    name resolves to one place.

    Minted places are the stored exception to "derived, never stored" — they cannot be
    derived, since the player made them — and they join here by parent: a place hangs
    off the one it was made from, the parent gains an exit to it, and a name resolves
    against where the party stands, so "the alley" by the market and "the alley" by the
    library are two places with one word between them (LambdaMOO's rule: a room exists
    because it was dug from somewhere, with an owner and a link).
    """
    home = home_set(location, terrain_hint)
    ground = terrain_of(at)
    if not ground or ground == home[0].terrain:
        base = home
    elif home[0].id == "here":
        # No location at all, but the party has been stood on named ground: that
        # ground is all there is.
        base = region_set(location_of(at), ground)
    else:
        base = home + region_set(location_of(at), ground)
    return with_founded(with_storeys(base), founded, at)


def with_storeys(base: tuple["Place", ...]) -> tuple["Place", ...]:
    """Every place in `base`, plus the floors of any of them that has floors.

    The ground floor gains its stairs as exits so the move vocabulary IS the exit list,
    which is the one thing every tradition surveyed agreed on. Added here rather than in
    `home_set` because a storey is reachable from where the party stands and `for_scene`
    is the one derivation of that — the same reasoning that put founded places here.
    """
    out = list(base)
    for place in base:
        if storey_of(place.id):
            continue                       # already a floor; do not stack floors on it
        upstairs = storey_set(place)
        if not upstairs:
            continue
        out[out.index(place)] = Place(
            id=place.id, name=place.name, about=place.about, terrain=place.terrain,
            exits=tuple(place.exits) + tuple(p.id for p in upstairs
                                             if abs(storey_of(p.id)) == 1),
            described_only=place.described_only, parent=place.parent,
            owner=place.owner, origin=place.origin)
        out.extend(upstairs)
    return tuple(out)


def with_founded(base: tuple[Place, ...], founded, at: str = "") -> tuple[Place, ...]:
    """Graft the minted places whose parent is in `base` — or whose parent is a minted
    place already grafted, or who ARE where the party stands — onto the set, wiring
    exits both ways. Minted places elsewhere in the world stay off the list, which is
    what keeps the model's choice small."""
    minted = [p if isinstance(p, Place) else from_dict(p) for p in (founded or ())]
    if not minted:
        return base
    out = {p.id: p for p in base}
    changed = True
    while changed:
        changed = False
        for m in minted:
            if m.id in out:
                continue
            reachable = (m.parent in out) or (at and (m.id == at or str(at).startswith(m.id + "/")))
            if not reachable:
                continue
            out[m.id] = m
            changed = True
    # Exits both ways between a minted place and its parent, and between a minted
    # place's own children and it; the derived set's exits are left as they were.
    result: dict[str, Place] = {}
    for pid, p in out.items():
        exits = list(p.exits)
        for q in out.values():
            if q.parent == pid and q.id != pid and q.id not in exits:
                exits.append(q.id)
        if p.parent and p.parent in out and p.parent not in exits:
            exits.append(p.parent)
        result[pid] = Place(id=p.id, name=p.name, about=p.about, terrain=p.terrain,
                            exits=tuple(exits), described_only=p.described_only,
                            parent=p.parent, owner=p.owner, origin=p.origin)
    return tuple(result.values())


def children_of(founded, parent_id: str) -> list[Place]:
    minted = [p if isinstance(p, Place) else from_dict(p) for p in (founded or ())]
    return [p for p in minted if p.parent == parent_id]


def child_id(parent_id: str, label: str) -> str:
    """`{parent}/{slug}`: the id of a place made from another. The ground stays the
    parent's unless the child says otherwise — `terrain_of` reads the head."""
    return f"{parent_id}/{_slug(label)}"


def mint(parent: Place, label: str, about: str = "", *, terrain: str = "",
         owner: str = "", origin: str = "found") -> Place:
    """A new place made from `parent`. The id carries the parent; the ground is the
    parent's unless given. `exits` are wired by `with_founded` at read time."""
    ground = str(terrain or "").strip().lower() or parent.terrain
    pid = child_id(parent.id, label)
    if ground and ground != parent.terrain:
        # A different ground under the same roof: the sewers under a town. The head of
        # the id says so, so `scene.biome` parses right when the party is down there.
        pid = f"{region_key(location_of(parent.id), ground)}:{_slug(parent.name)}/{_slug(label)}"
    return Place(id=pid, name=label, about=about, terrain=ground, exits=(),
                parent=parent.id, owner=owner, origin=origin)


def venture_set(parent: Place, kind: str) -> list[Place]:
    """The places a venture of `kind` from `parent` is made of: the venture itself and
    its seeded spots, all hanging off it. Generated on entry from the parent's id, so
    the same stairs lead to the same cellar next time."""
    spec = VENTURES[kind]
    head = mint(parent, spec["label"], f"{kind} off {parent.name}",
                terrain=spec["terrain"], origin="venture")
    spots = list(spec["spots"])
    if spots:
        n = max(1, min(len(spots), 2 + _seed(head.id) % max(1, len(spots) - 1)))
        spots = spots[:n]
    out = [head]
    for label, about in spots:
        out.append(Place(id=child_id(head.id, label), name=label, about=about,
                         terrain=head.terrain, exits=(), parent=head.id, origin="venture"))
    return out


def spots_for(location, terrain: str = "") -> tuple[Place, ...]:
    """The location's own places. Kept as the name stage 8a shipped under; `home_set`
    is the same function and the docstring lives there."""
    return home_set(location, terrain)


def find(places, wanted: str) -> Place | None:
    """The place the GM means, by id or by name, or None.

    Matched leniently on the way in and refused hard on the way out: "market", "the
    market" and the raw id all mean the same place, and anything else means none of them.
    """
    want = " ".join(str(wanted or "").split()).lower()
    if not want:
        return None
    for p in places or ():
        if want in (p.id.lower(), p.name.lower(), p.name.lower().removeprefix("the ")):
            return p
    # The GM's own dressing of a real place: "the merchant's gate" for "the gate", "the
    # old market" for "the market". Measured at the table, 2026-09-06: the plan wrote
    # `travel` to "the merchant's gate", the exact match failed, and the turn was a 502.
    # The last word decides, and only when exactly one place ends in it — "the back
    # streets" and "the street" would otherwise be a coin toss.
    head = want.split()[-1].rstrip("s") if want.split() else ""
    if len(head) >= 3:
        ending = [p for p in places or ()
                  if (p.name.lower().split() or [""])[-1].rstrip("s") == head]
        if len(ending) == 1:
            return ending[0]
    return None
