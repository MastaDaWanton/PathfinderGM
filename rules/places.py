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
                "described_only": self.described_only}


def from_dict(d: dict) -> Place:
    return Place(
        id=str(d.get("id") or ""), name=str(d.get("name") or ""),
        about=str(d.get("about") or ""), terrain=str(d.get("terrain") or ""),
        exits=tuple(str(x) for x in (d.get("exits") or ())),
        described_only=bool(d.get("described_only")),
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


def _slug(label: str) -> str:
    return "-".join(str(label).lower().split())


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
        return _build(here, URBAN, _SETTLEMENT)
    return _build(here, hint or "grassland", _WILD)


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


def for_scene(location, at: str, terrain_hint: str = "") -> tuple[Place, ...]:
    """Every place the party can name from where they stand: home, plus the ground
    they are on if it is not home.

    The ONE derivation. `Engine.places()` and the scene brief both used to compute this
    separately — two copies of a rule, the trap CLAUDE.md names — and now both call here.
    Region places share the `_WILD` names, and only one region is ever current, so a
    name resolves to one place.
    """
    home = home_set(location, terrain_hint)
    ground = terrain_of(at)
    if not ground or ground == home[0].terrain:
        return home
    if home[0].id == "here":
        # No location at all, but the party has been stood on named ground: that
        # ground is all there is.
        return region_set(location_of(at), ground)
    return home + region_set(location_of(at), ground)


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
