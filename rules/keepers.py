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
    """(what they are called, the words the codex is asked for) for this place.

    By its kind when it has one: "the Driftwood Reach" is a tavern, and a tavern has
    somebody behind the bar whatever it is called."""
    kind = str(getattr(place, "kind", "") or "").strip()
    return places_mod.keeper_of(f"the {kind}" if kind else (getattr(place, "name", "") or ""))


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


def kin_note(scene, actor, at: str = "") -> str:
    """Who else in this town this keeper is related to, as a sentence for the brief.

    The names already cluster — a settlement's keepers are drawn from its own families,
    so Ashwatch's market and its tavern are both kept by Sootspars — and until now
    nothing said so, which left the narrator writing two strangers who happen to share a
    name. A shared surname is only a family if something acknowledges it; otherwise it is
    repetition, and repetition is what lazy generation looks like.

    Ruled 2026-09-16: "1 household can run multiple shops but they should be acknowledged
    by each other as family run stores and should be friendly, unless there is some family
    feud." This is the acknowledgement. Whether they are friendly or feuding is the
    narrator's to play and the attitude track's to record — the engine states the
    relationship and does not invent the sentiment.
    """
    mine = str(getattr(actor, "name", "") or "").split()
    if len(mine) < 2:
        return ""
    family = mine[-1]
    # The place is passed in rather than read off the actor: `staff` writes this note
    # BEFORE `scene.add` stamps `actor.at`, so reading it here found an empty string and
    # the kinship never fired. Caught by driving a town with two Sootspars in it.
    here = places_mod.location_of(str(at or getattr(actor, "at", "") or ""))
    kin = []
    for other in scene.people.values():
        if other is actor or not is_keeper(getattr(other, "world_entity_id", "") or ""):
            continue
        if places_mod.location_of(place_of(other.world_entity_id)) != here:
            continue
        if str(other.name).split()[-1:] == [family]:
            kin.append(other.name)
    if not kin:
        return ""
    who = _and_list(kin)
    return (f" One of the {family}s, and so is {who}: the same household keeps both, "
            f"and they know it.") if len(kin) == 1 else (
        f" One of the {family}s, along with {who} — one household, several counters.")


def _and_list(names) -> str:
    got = [str(n) for n in names if str(n).strip()]
    if len(got) <= 1:
        return got[0] if got else ""
    return ", ".join(got[:-1]) + " and " + got[-1]


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
                   + (f", in {town}" if town else "") + "."
                   + kin_note(scene, actor, at))
    # And a face, here, because nothing downstream can find them one: a keeper's
    # `world_entity_id` is the synthetic `keeper:<place>`, so `names.resident_appearance`
    # looks it up, finds no such resident and returns "". Drenn Ironvale therefore had no
    # appearance, no Looks clause in the brief, and nothing for the description check to
    # enforce even once it ran over everybody (2026-09-19, item 32). Their people's own
    # body line is the right answer: they are a local, and the name they carry was drawn
    # from the local stock already. Their name IS their name — they are not a stranger
    # keeping it back — so `true_name` is stamped too, or `name_the_nameless` would draw
    # a second one for somebody already introduced.
    from . import names as names_mod

    actor.true_name = name
    if not actor.appearance:
        actor.appearance = names_mod.appearance_for(engine.world, scene.location_id,
                                                   ref=actor.ref or wid)
    scene.add(actor)
    return actor


# --- hours ----------------------------------------------------------------------------------
#
# A counter keeps hours (2026-09-27). Researched before building, sources in
# docs/the-population.md "Built: shop hours and calling on people":
#   * OPEN IS WHERE THE KEEPER STANDS, never a second clock: Stardew Valley's shop opens
#     only while its owner is inside the counter's tile area, and Skyrim's vendor faction
#     asks both an hour window and a place. Here a keeper's hours say where they stand,
#     and the counter is open exactly when they stand at it in an open slot.
#   * A SHUT SHOP IS NOT A SHUT BUILDING: Pierre's Wednesday closure shut the building and
#     cut players off from the people inside, and the complaints ran for years. A keeper
#     of a place under a roof lives on the premises (Pierre, Belethor) and can still be
#     talked to; only the counter is shut. A stall in the open is packed up, and its
#     keeper goes home.
#   * THE KEEPER SAYS WHEN TO COME BACK: CircleMUD's keeper speaks one of "Come back
#     later!", "Sorry, we have closed, but come back later." and "Sorry, come back
#     tomorrow."; Stardew's closed shop "does nothing" unless a message is written.
#   * SOMEBODY IS ALWAYS OPEN: Skyrim's innkeepers are; so are these.
# The hours themselves are the town's own: trade from the market bell at first light, most
# counters shut by evening, smiths and taverners working to the curfew bell (the 1345
# Spurriers' ordinance forbade work after it). In residency's three-hour slots, starting
# at midnight: 0, 3, 6, 9, 12, 15, 18, 21.
ALWAYS = frozenset(range(8))
_HOURS: tuple[tuple[tuple[str, ...], frozenset], ...] = (
    (("tavern", "inn", "alehouse", "taproom"), ALWAYS),
    (("smithy", "workshops", "tannery", "brewery", "stables", "carters yard", "mill"),
     frozenset({2, 3, 4, 5, 6})),
)
DAY_TRADE = frozenset({2, 3, 4, 5})
_SLOT_WORDS = {0: "midnight", 1: "the small hours", 2: "first light", 3: "mid-morning",
               4: "noon", 5: "mid-afternoon", 6: "evening", 7: "the curfew bell"}


def kind_of(place_id: str, founded=()) -> str:
    """What a place is, for its hours: a founded place's own `kind`, else its label."""
    for p in founded or ():
        if p.get("id") == place_id and p.get("kind"):
            return str(p["kind"]).lower().removeprefix("the ")
    return label_of(place_id).removeprefix("the ")


def hours_of(place_id: str, founded=()) -> frozenset:
    kind = kind_of(place_id, founded)
    for words, slots in _HOURS:
        if any(kind == w or kind.endswith(" " + w) for w in words):
            return slots
    return DAY_TRADE


def open_now(place_id: str, clock: int, founded=()) -> bool:
    from .residency import slot_of

    return slot_of(clock) in hours_of(place_id, founded)


def shut_line(place_id: str, clock: int, founded=(), who: str = "") -> str:
    """The keeper's answer at a shut counter, or "" when it is open: when to come back.

    Before the first open slot of the day: "opens at first light". Between two open
    slots (none today, but the table allows it): back later. After the last: tomorrow.
    """
    from .residency import slot_of

    if open_now(place_id, clock, founded):
        return ""
    hours = sorted(hours_of(place_id, founded))
    now = slot_of(clock)
    later = [s for s in hours if s > now]
    what = label_of(place_id) or "the counter"
    whose = f"{who}'s counter" if who else f"the counter at {what}"
    if later and any(s < now for s in hours):
        return f"{whose[:1].upper()}{whose[1:]} is shut for now; it opens again at {_SLOT_WORDS[later[0]]}."
    if later:
        return f"{whose[:1].upper()}{whose[1:]} is not open yet; it opens at {_SLOT_WORDS[later[0]]}."
    return (f"{whose[:1].upper()}{whose[1:]} is shut for the day; come back tomorrow, "
            f"from {_SLOT_WORDS[hours[0]]}.")


def lives_in(place_id: str) -> bool:
    """A keeper of a place under a roof lives on the premises; a stall's goes home."""
    return places_mod.is_indoors(place_id)


def shut_here(scene, seller=None) -> str:
    """Why nobody will sell to the party at this counter right now, or "".

    Asked of the seller when the plan named one, else of the keeper of the place the
    party is standing in — whether they are at their counter or have gone home for the
    night. A person who keeps no counter (a peddler, a passer-by) keeps no hours. The one
    door the trade panel, `buy`, `sell` and the brief all ask, so a counter is never shut
    to one of them and open to another.
    """
    keeper = seller if seller is not None and is_keeper(
        getattr(seller, "world_entity_id", "") or "") else None
    if keeper is None and seller is None:
        keeper = keeper_in(scene, str(getattr(scene, "at", "") or ""))
    if keeper is None:
        return ""
    place = place_of(keeper.world_entity_id)
    if place != getattr(scene, "at", None):
        return ""
    return shut_line(place, int(getattr(scene, "clock_minutes", 0) or 0),
                     getattr(scene, "founded", None) or (), who=str(keeper.name or ""))
