"""Somebody behind the counter: the person who stands in a place that sells something.

    "any place that offers services or merchandise needs an NPC to man it"
    (2026-09-15)

The settlement table has said since the day it was written which places want somebody
in them — twenty-five of the forty-two — and until this module nothing built one. A
market with no stallholder is a room with a label: the player walks in, the narrator
invents a trader, the trader has no numbers, no name the world would use, and is gone
by the next beat because nothing anywhere remembers them. `docs/settlement-places.md`
carried that gap as a written promise rather than a silent one, and this is the promise
kept.

**What a keeper is.** An ordinary `Actor` in `Scene.people`, standing at their own
place. Nothing else. `Scene.actors` is the derived view of who is in the party's place,
so a keeper appears in the narrator's WHO IS HERE when the party walks in and is out of
it again when they walk out, with no code in either direction; the codex supplies the
numbers, `states` supplies their attitude, and they can be talked to, bought from,
lied to, robbed and killed by machinery that was all already here.

**Where the name comes from.** The world's own name stock and never a model: the
settlement's own families first (Aurvantis ships four cast members per settlement, two
families between them), the world's given names behind that. A smith in Ashwatch is a
Sootspar or a Halloran because those are the families of Ashwatch — and one of the
ninety-six given names the export actually uses. "Ground every name" (CLAUDE.md), which
here means the keeper is named out of the world rather than about it. The choice is
seeded off the place id — the same SHA-256 that seeds the floor plan, `places._seed` —
so it is the same person in this session and in the next one, and no name is stored to
drift from the rule that made it.

**What was refused.** Ultima Online built shopkeepers with inventory, cash on hand,
sell-through rate and a supply-and-demand price simulation; the shopkeepers went broke,
holding "piles of things no one wanted and no cash", and the simulation was abandoned
rather than tuned. A keeper here owns nothing and prices nothing. What the shelf holds
is `rules/market.py` (drawn, not stored) and what it costs is `rules/pricing.py` out of
the rulebook. The keeper is a person to talk to, not an economy.

CircleMUD is the other precedent, and the useful half of it: a shop is attached to the
SHOPKEEPER — the shop file names a mobile, and a list of rooms it works in, "so trans'ed
shopkeepers can't sell in the desert". The keeper belongs to the place and the trade
belongs to the keeper. That is exactly the shape here, with the place id doing the work
the room list did.

Sources consulted 2026-09-16: CircleMUD Builder's Manual (shop files); Raph Koster and
Zachary Simpson on the UO economy; Pathfinder GameMastery Guide "Settlements", whose
stat block lists NOTABLE NPCS by role and then name — role first, which is the order
this module mints in.
"""
from __future__ import annotations

from . import places as places_mod

# What a keeper is filed under in the codex and in the world. Not a world entity id —
# World Bible did not write this person — so it is stamped with its own prefix, which
# is also what tells a keeper from a cast member anywhere that asks.
PREFIX = "keeper:"


def entity_id(place_id: str) -> str:
    return PREFIX + str(place_id or "").strip()


def is_keeper(world_entity_id: str) -> bool:
    return str(world_entity_id or "").startswith(PREFIX)


def place_of(world_entity_id: str) -> str:
    wid = str(world_entity_id or "")
    return wid[len(PREFIX):] if wid.startswith(PREFIX) else ""


# --- the name -------------------------------------------------------------------------------

def name_stock(world, location_id: str = "") -> tuple[list[str], list[str], set[str]]:
    """The world's own names: given names, family names, and the ones already worn.

    Families are the settlement's own when it has any — a keeper in Ashwatch is one of
    the two families Ashwatch's cast belongs to, which is what makes a small town read
    as a small town — and the rest of the world's when it has none. Given names are
    drawn from the whole world: ninety-six of them in Aurvantis against ten family
    names, and a town of four people cannot supply a first name that is not already a
    specific person's.

    Both lists keep the export's own order, which is stable across runs, so the
    seeded pick below is stable too.
    """
    play = getattr(world, "play", None) or {}
    cast = play.get("cast") or []
    here = str(location_id or "")
    given: list[str] = []
    local: list[str] = []
    other: list[str] = []
    taken: set[str] = set()
    for c in cast:
        if not isinstance(c, dict):
            continue
        parts = str(c.get("name") or "").split()
        if not parts:
            continue
        taken.add(" ".join(parts).lower())
        if parts[0] not in given:
            given.append(parts[0])
        if len(parts) < 2:
            continue
        family = parts[-1]
        if here and str(c.get("home_id") or "") == here:
            if family not in local:
                local.append(family)
        elif family not in other:
            other.append(family)
    return given, (local or other), taken


def name_for(place, world, taken: set[str] | frozenset[str] = frozenset()) -> str:
    """Who the person at this place is called. The same answer every session.

    Falls back to what they are — "the smith" — when the world lends no names, which is
    every world-less engine in the suite and any export that ships no cast. A keeper
    with no name is still a keeper; a keeper with an invented name is a thing the world
    does not contain.
    """
    title = places_mod.keeper_of(getattr(place, "name", "") or "")[0]
    given, families, world_names = name_stock(
        world, places_mod.location_of(getattr(place, "id", "") or ""))
    if not given or not families:
        return title
    spoken = {str(n).lower() for n in taken} | world_names
    # The same seed the floor plan uses, so one place means one person for ever. The
    # family and the given name are drawn off different halves of it: taking both off
    # the same number walks the two lists in lockstep and gives a world of Bregan
    # Sootspar, Halvik Halloran, Karsh Sootspar.
    n = places_mod._seed(getattr(place, "id", "") or "")
    family = families[(n >> 12) % len(families)]
    for i in range(len(given)):
        name = f"{given[(n + i) % len(given)]} {family}"
        # Never a person the world already wrote, and never the keeper next door: two
        # people of one name in one town is a bug the player experiences as a ghost.
        if name.lower() not in spoken:
            return name
    return title


# --- standing them up ------------------------------------------------------------------------

def wanted_at(place) -> tuple[str, tuple[str, ...]]:
    """(what they are called, the words the codex is asked for) for this place."""
    return places_mod.keeper_of(getattr(place, "name", "") or "")


def label_of(place_id: str) -> str:
    """The table's own name for a place, read back off its id: "the market".

    The slug was made by `places._slug` — lower case, spaces to dashes — so the way back
    is dashes to spaces, and a storey suffix is not part of the name. Parsing rather
    than looking up, for the reason the whole module of place ids exists: the id carries
    what it says, and nothing here has a world to ask.
    """
    spot = str(place_id or "").split(":")[-1].split(places_mod.STOREY)[0]
    return spot.replace("-", " ")


def keeps_a_counter(actor) -> bool:
    """Whether this person is somebody the trade panel may open across.

    A keeper of a TRADE place, standing in it. Both halves matter, and the second is
    CircleMUD's: its shop file names the rooms a keeper's shop works in, "so trans'ed
    shopkeepers can't sell in the desert". A smith walking the road is not a smithy.

    Measured 2026-09-16, which is why this exists: `play/views._merchant_here` gates the
    panel on the actor's NAME matching merchant words, so a stallholder named out of the
    world — "Gorvothys Vyrnys" — stood at her own stall while the panel answered "there
    is nobody here to trade with". The keeper was the merchant and the merchant test
    could not see her.
    """
    place = place_of(getattr(actor, "world_entity_id", "") or "")
    if not place or getattr(actor, "at", "") != place:
        return False
    return places_mod.category_of(label_of(place)) == "trade"


def keeper_in(scene, place_id: str):
    """The keeper standing at this place, if one has been stood up and is still here."""
    wanted = entity_id(place_id)
    return next((a for a in scene.people.values()
                 if str(getattr(a, "world_entity_id", "") or "") == wanted), None)


def staff(engine):
    """Put somebody behind the counter where the party is standing. Once, ever.

    Returns the keeper minted, or None — which is the answer for a place that sells
    nothing, a place already staffed, and a fight (nobody strolls out to serve you
    mid-round; the party arrived in the middle of something).

    Once ever, and the ledger is the place rather than the person, because a person is
    not a reliable record of themselves: the smith the party murdered is swept out of
    the scene by `tidy_the_fallen` two turns later, and a check for "is there a keeper
    here" would cheerfully mint a new one on the next visit. The scene remembers which
    counters have had somebody put behind them and never does it twice.
    """
    from . import npcs
    from .bestiary import instantiate

    scene = engine.scene
    if scene.in_encounter:
        return None
    at = str(scene.at or "")
    if not at or at in scene.staffed:
        return None
    here = places_mod.find(engine.places(), at)
    if here is None:
        return None
    title, words = wanted_at(here)
    if not title:
        return None
    # Stamped before anything can fail: a keeper that could not be built is a counter
    # that stays empty, not one that is tried again every turn the party stands there.
    scene.staffed.append(at)
    pc = scene.pc()
    level = int(getattr(pc, "level", 1) or 1)
    name = name_for(here, engine.world,
                    taken={str(a.name) for a in scene.people.values()})
    wid = entity_id(at)
    # The codex, exactly as a scheme's cast member reaches it: a stat block by the
    # role's words near the party's level, remembered under this id in `homebrew/npcs/`
    # so the numbers are the same next session and one file on the bench corrects them.
    template = npcs.block_for(wid, list(words), level, name)
    try:
        actor = instantiate(template, scene=scene, name=name, world_entity_id=wid)
    except Exception:
        # An unknown template is a content problem, not a reason for the turn to fail.
        return None
    # The note is what the narrator is told about them — `gm/prompts.py` prints the
    # first sentence of it beside the name — so it says what they are and where, and
    # nothing about what they sell, which is the market's business and not the prose's.
    where = getattr(here, "name", "") or "here"
    town = str(getattr(engine.world.get(scene.location_id), "name", "") or "") \
        if engine.world is not None else ""
    actor.notes = (f"{title[:1].upper()}{title[1:]} at {where}"
                   + (f", in {town}" if town else "") + ".")
    scene.add(actor)
    return actor
