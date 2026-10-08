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
    """The place a keeper keeps. A counter's keeper at a market (`keeper:<market>#<id>`)
    keeps the market: the suffix names the counter, never a place, so hours, `shut_here`,
    "left behind" and going home at night work for a stallholder exactly as they do for
    any keeper (docs/design-d-people.md §4.8)."""
    wid = str(world_entity_id or "")
    return wid[len(PREFIX):].split(HOLDER, 1)[0] if wid.startswith(PREFIX) else ""


# A market has several counters, each with its own keeper (rules/market.py); the counter
# is named after the place in the keeper's id, so one market is one place with many
# people behind its stalls rather than a place per stall.
HOLDER = "#"


def holder_id(place_id: str, counter_id: str) -> str:
    return f"{entity_id(place_id)}{HOLDER}{counter_id}"


def counter_of(world_entity_id: str) -> str:
    """Which market counter this keeper keeps ("general", "stall-cloth-curios"), or ""
    for the one keeper of a place."""
    wid = str(world_entity_id or "")
    return wid.split(HOLDER, 1)[1] if wid.startswith(PREFIX) and HOLDER in wid else ""


# --- the name -------------------------------------------------------------------------------

def name_stock(world, location_id: str = "") -> tuple[list[str], list[str], set[str]]:
    """The world's own names: given names, family names, and the ones already worn.

    Families are the settlement's own when it has any — its own `play.names` pool
    (`names.town_pool`) and the families its cast belongs to, which is what makes a
    small town read as a small town — then its people's pool, then the rest of the
    world's cast. Given names are the town's or its people's pool, and the whole world's
    cast only for an export with no pools.

    Every list keeps the export's own order, which is stable across runs, so the seeded
    pick below is stable too.
    """
    from . import names as names_mod

    play = getattr(world, "play", None) or {}
    cast = play.get("cast") or []
    here = str(location_id or "")
    cast_given: list[str] = []
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
        if parts[0] not in cast_given:
            cast_given.append(parts[0])
        if len(parts) < 2:
            continue
        family = parts[-1]
        if here and str(c.get("home_id") or "") == here:
            if family not in local:
                local.append(family)
        elif family not in other:
            other.append(family)
    # The town's own pool first, then its cast's families (the playtest's item 8.4:
    # the market was kept by an Ironvale in every game while Vormoor's sixteen pool
    # families went unread), then the people's pool, then the rest of the world's cast.
    own = names_mod.town_pool(world, here) if world is not None else None
    people = names_mod.pool_for(world, here) if (world is not None and here) else None
    families = _merged([str(f) for f in (own or {}).get("family") or []], local)
    if not families:
        families = [str(f) for f in (people or {}).get("family") or []] or other
    # Given names from the people who live here — the town's pool, else their people's —
    # and the cast's only for a world that ships no pools (R0, 2026-09-28: a keeper's
    # given name ignored the people entirely).
    given = ([str(g) for g in (own or {}).get("given") or []]
             or [str(g) for g in (people or {}).get("given") or []] or cast_given)
    return given, families, taken


def _merged(*lists) -> list[str]:
    out: list[str] = []
    for seq in lists:
        for x in seq:
            if x and x not in out:
                out.append(x)
    return out


def name_for(place, world, taken: set[str] | frozenset[str] = frozenset(), *,
             salt=None) -> str:
    """Who the person at this place is called. The same answer every session.

    Falls back to what they are — "the smith" — when the world lends no names, which is
    every world-less engine in the suite and any export that ships no cast. A keeper
    with no name is still a keeper; a keeper with an invented name is a thing the world
    does not contain.

    `salt` is the campaign's story seed. The owner's ruling (Q18, 2026-09-28): a place's
    keeper is the same person for the whole of one campaign and a different person in
    the next, so the market is not an Ashla Ironvale in every game ever played. Without
    it the answer is the place's alone, as it always was.
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
    pid = getattr(place, "id", "") or ""
    n = places_mod._seed(pid if salt is None else f"{salt}:{pid}")
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
    # A place on the outskirts ring carries "@" before its slug ("~forest:@the-tannery",
    # `rules/outskirts.py`); it is not part of the name. Measured 2026-10-08: the tanner
    # at an outskirts tannery read "@the tannery", which is no trade place, so their
    # counter never opened.
    spot = str(place_id or "").split(":")[-1].split(places_mod.STOREY)[0].lstrip("@")
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
    wid = getattr(actor, "world_entity_id", "") or ""
    place = place_of(wid)
    if not place or getattr(actor, "at", "") != place:
        return False
    # Somebody behind one of a market's counters keeps that counter, whatever the place.
    if counter_of(wid):
        return True
    label = label_of(place)
    # The market's own keeper is its master, who sells nothing (`places.RUNNERS`, item 10
    # of the 2026-09-28 playtest); the trade panel never opens across them.
    if places_mod.runs_it(label):
        return False
    return (places_mod.category_of(label) == "trade"
            or label in places_mod.SELLS_OUTSIDE_TRADE)


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
    # The family is read off the TRUE name, and the note names nobody by a name not yet
    # given (owner ruling F1, 2026-09-30): kin are "the one behind the bar", not "Gorm
    # Vesper", until the player has been told. The family word itself is left out while
    # the keeper's own name is kept back — it is half of it.
    mine = str(getattr(actor, "true_name", "") or getattr(actor, "name", "") or "").split()
    if len(mine) < 2:
        return ""
    family = mine[-1]
    introduced = str(getattr(actor, "name", "") or "") == " ".join(mine)
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
        theirs = str(getattr(other, "true_name", "") or other.name).split()
        if theirs[-1:] == [family]:
            kin.append(str(other.name))
    if not kin:
        return ""
    who = _and_list(kin)
    if not introduced:
        return (f" Family to {who}: the same household keeps both, and they know it."
                if len(kin) == 1 else
                f" Family to {who} — one household, several counters.")
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


def seller_in(scene, place_id: str):
    """Whoever sells at this place when nobody has asked for a particular counter: its
    keeper — or, at a market, whose own keeper is its master and sells nothing (I2), the
    keeper of its general store. Wherever they are standing right now (a stallholder goes
    home at night), so it answers "who keeps this counter", not "who is here"."""
    if places_mod.runs_it(label_of(place_id)):
        wid = holder_id(place_id, "general")
        return next((a for a in scene.people.values()
                     if str(getattr(a, "world_entity_id", "") or "") == wid), None)
    return keeper_in(scene, place_id)


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

    **A market** stands up its master (a town or a city; a village's market has none —
    the owner, Q28) and its general store, whose keeper is the one the trade button opens
    across until the player picks another counter. Every other counter's keeper is minted
    when that counter is first wanted (`stand_up`), so walking into a city market does not
    put ten people into the brief at once.
    """
    scene = engine.scene
    if scene.in_encounter:
        return None
    at = str(scene.at or "")
    if not at:
        return None
    here = places_mod.find(engine.places(), at)
    if here is None:
        return None
    if _held(scene, here):
        # Somebody's own place is kept by whoever holds it. Measured 2026-10-04 (lane H,
        # contracts §12 item 3): the player founded "my own forge" (kind forge, owner pc),
        # walked in, and a hired smith was stood behind the anvil of the PC's own smithy —
        # and `places.smithy_here` then named that stranger as its keeper. Not stamped in
        # `staffed`: if the place is sold or seized (the holder's effect removed), it is
        # an ordinary counter again and may be staffed on the next visit.
        return None
    from . import market as market_mod

    location = _location(engine.world, scene.location_id)
    at_market = market_mod.is_market(at, getattr(scene, "founded", None) or ())
    made = None
    if at not in scene.staffed:
        title, words = wanted_at(here)
        if not title:
            return None
        # Stamped before anything can fail: a keeper that could not be built is a counter
        # that stays empty, not one that is tried again every turn the party stands there.
        scene.staffed.append(at)
        if not (at_market and not places_mod.has_a_master(places_mod.scale_of(location))):
            made = _mint(scene, engine.world, at, entity_id(at), title, words,
                         seed_place=here, what=_what(title, here))
    if at_market:
        general = market_mod.counter(location, "general")
        if general is not None:
            first = stand_up(scene, engine.world, at, general, even_when_shut=True)
            made = made or first
    return made


def _held(scene, place) -> bool:
    """Whether a place has a holder: its `owner` is somebody in the store who holds it
    (`holds.place.<slug>`, the `found` door's effect). The owner field is the claim and
    the effect is the fact, as `places.smithy_here` reads it."""
    owner = str(getattr(place, "owner", "") or "")
    if not owner:
        return False
    people = getattr(scene, "people", None) or {}
    holder = people.get(owner)
    if holder is None:
        try:
            holder = (getattr(scene, "actors", None) or {}).get(owner)
        except Exception:  # noqa: BLE001
            holder = None
    slug = str(getattr(place, "id", "") or "").rsplit("/", 1)[-1]
    return holder is not None and bool(slug) and holder.has_state(f"holds.place.{slug}")


def _location(world, location_id: str):
    """The settlement entity when there is a world to ask, else the bare id — which
    `places.scale_of` reads as a town, the app's default everywhere."""
    if world is not None:
        got = world.get(location_id)
        if got is not None:
            return got
    return location_id


def _what(title: str, place) -> str:
    return f"{title} at {getattr(place, 'name', '') or 'here'}"


def stand_up(scene, world, market_id: str, counter, *, even_when_shut: bool = False):
    """The keeper of one of a market's counters (`rules/market.py`), minted the first
    time the counter is wanted and the same person every time after; None when there is
    nobody to be had.

    Nobody, for the same reasons `staff` gives: a fight, a keeper already stood up once
    and since gone (killed, or swept away), and — for a stall wanted after hours — a
    market that is packed up for the night, whose stallholders have gone home
    (`open_now`). Minted through the arrival door like every keeper (`Scene.add`), named
    out of the world on the counter's own id (`keeper:<market>#<counter>`), so one stall
    is one person for the whole campaign and the next stall is somebody else.
    """
    wid = holder_id(market_id, counter.id)
    have = next((a for a in scene.people.values()
                 if str(getattr(a, "world_entity_id", "") or "") == wid), None)
    if have is not None:
        return have
    key = f"{market_id}{HOLDER}{counter.id}"
    if key in scene.staffed or scene.in_encounter:
        return None
    if not even_when_shut and not open_now(
            market_id, int(getattr(scene, "clock_minutes", 0) or 0),
            getattr(scene, "founded", None) or ()):
        return None
    scene.staffed.append(key)
    from types import SimpleNamespace

    what = (counter.title if counter.sort != "stall"
            else f"the stallholder at {counter.label}")
    return _mint(scene, world, market_id, wid, counter.title, counter.words,
                 seed_place=SimpleNamespace(id=key, name=counter.label),
                 what=f"{what}, at the market", descriptor=what)


_PUBLIC = frozenset({"publicly", "public", "by name", "everyone", "widely", "true", "yes"})


def publicly_known(world, place_id: str, wid: str = "") -> str:
    """The keeper's name when the WORLD marks it as one everybody knows, else "".

    Owner ruling F1 (2026-09-30): keepers go by their descriptor until introduced, "unless
    the world marks them as publicly known" — the name over the shop. The marking is the
    world's, never this app's guess, and no export ships it yet (docs/from-world-bible.md,
    "Known gaps"). Read from either of two places the export already has a row for:

      * the place's own row in `play.places[]` — ``"keeper": {"name": "Hal Dunmore",
        "known": "publicly"}``;
      * a `play.cast[]` member who keeps it — ``"keeps": "<place id>", "known":
        "publicly"`` — so a world character who runs the smithy is that smithy's keeper.

    A row with a name and no public marking is NOT public: the name is the world's, the
    knowing of it is the player's to earn."""
    if world is None or not place_id:
        return ""
    play = getattr(world, "play", None) or {}
    if not isinstance(play, dict):
        return ""

    def _public(v) -> bool:
        return str(v if not isinstance(v, bool) else str(v).lower()).strip().lower() in _PUBLIC

    if counter_of(wid):
        return ""                          # a stall's keeper is nobody's sign over a door
    for row in play.get("places") or []:
        if isinstance(row, dict) and str(row.get("id") or "") == place_id:
            k = row.get("keeper")
            if isinstance(k, dict) and str(k.get("name") or "").strip() \
                    and _public(k.get("known")):
                return " ".join(str(k["name"]).split())
    for row in play.get("cast") or []:
        if isinstance(row, dict) and str(row.get("keeps") or "") == place_id \
                and str(row.get("name") or "").strip() and _public(row.get("known")):
            return " ".join(str(row["name"]).split())
    return ""


def _mint(scene, world, at: str, wid: str, title: str, words, *, seed_place, what: str,
          descriptor: str = ""):
    """Build one keeper, name them out of the world, give them a face, and stand them at
    `at` through the arrival door. None when the codex has no block for them.

    `descriptor` is what they go by until they give their name; the title when it is
    not given ("the smith"). A market's stalls pass their own ("the stallholder at the
    cloth stall"), because ten stallholders called "the stallholder" are one word for
    ten people."""
    from . import npcs
    from .bestiary import instantiate

    pc = scene.pc()
    level = int(getattr(pc, "level", 1) or 1)
    # Their name is drawn here and KEPT BACK (owner ruling F1, 2026-09-30): until it is
    # given in play they go by what they are — "the one behind the bar", "the master of
    # the market" — exactly like everybody else the scene makes. Measured on the playtest
    # (item 7): 4 of 4 keepers were shown by full name before any introduction, and the
    # page used "Gorm Vesper" and "Quin Nutmeg" unprompted ("Others, like Gorm Vesper,
    # require a heavy purse", said BY Gorm). The brief's premise (gm/prompts.py, "The true
    # name is NOT shown") had been true of everybody but keepers since 2026-09-19.
    # Evennia's RP system is the precedent: a character is shown by its sdesc ("a tall
    # man") until the viewer `recog`s them, and the name a viewer knows is learned, never
    # read off the character. The exception is the world's to make (`publicly_known`).
    taken = {str(a.name) for a in scene.people.values()} | {
        str(getattr(a, "true_name", "") or "") for a in scene.people.values()} - {""}
    name = name_for(seed_place, world, taken=taken,
                    salt=getattr(scene, "story_seed", 0) or None) or title
    known = publicly_known(world, at, wid)
    if known:
        name = known
    shown = name if known else (descriptor or title)
    # The codex, exactly as a scheme's cast member reaches it: a stat block by the
    # role's words near the party's level, remembered under this id in `homebrew/npcs/`
    # so the numbers are the same next session and one file on the bench corrects them.
    template = npcs.block_for(wid, list(words), level, name)
    try:
        actor = instantiate(template, scene=scene, name=shown, world_entity_id=wid)
    except Exception:
        # An unknown template is a content problem, not a reason for the turn to fail.
        return None
    # The name behind the descriptor: what they answer when asked
    # (`judgement.names_asked_for`), and what the panel takes when they give it
    # (`judgement.apply_introductions`, `narration.settle_introductions`) — the same
    # machinery every other person the scene makes has been named through since
    # 2026-09-18. Stamped before the note, whose kinship reads the family off it.
    actor.true_name = name
    # The note is what the narrator is told about them — `gm/prompts.py` prints the
    # first sentence of it beside the name — so it says what they are and where, and
    # nothing about what they sell, which is the market's business and not the prose's.
    town = str(getattr(world.get(scene.location_id), "name", "") or "") \
        if world is not None else ""
    if places_mod.runs_it(label_of(at)) and not counter_of(wid):
        head = (f"The master of the market" + (f" in {town}" if town else "")
                + ": they run it and sell nothing.")
    else:
        head = (f"{what[:1].upper()}{what[1:]}" + (f", in {town}" if town else "") + ".")
    actor.notes = head + kin_note(scene, actor, at)
    # And a face, here, because nothing downstream can find them one: a keeper's
    # `world_entity_id` is the synthetic `keeper:<place>`, so `names.resident_appearance`
    # looks it up, finds no such resident and returns "". Drenn Ironvale therefore had no
    # appearance, no Looks clause in the brief, and nothing for the description check to
    # enforce even once it ran over everybody (2026-09-19, item 32). Their people's own
    # body line is the right answer — and the people it is drawn from is RECORDED
    # (`person_words.settle_people`; item 10 of 2026-09-30: 8 of 8 NPCs carried a Ratfolk
    # face and no people). A grant at this place binds them (F2): Quin, the chamber's
    # keeper, was promised as "a human woman" two turns before she was minted.
    from . import names as names_mod
    from . import person_words

    person_words.settle_people(scene, world, actor, words=shown, template=template,
                               place=at, keep_name=bool(known))
    if not actor.appearance:
        actor.appearance = names_mod.appearance_for(world, scene.location_id,
                                                   ref=actor.ref or wid)
    if not known and actor.true_name != name:
        # A grant drew them from another people's pool; the family the note reads is
        # theirs, so it is written again.
        actor.notes = head + kin_note(scene, actor, at)
    # Stood at the place itself, not the place the party happens to be: a counter wanted
    # from the market is the market's, and the arrival door records where they stand.
    if str(getattr(scene, "at", "") or "") == at:
        scene.add(actor)
    else:
        scene.arrive(actor, place_id=at)
    return actor


def descriptor_of(scene, world, wid: str) -> str:
    """What a keeper goes by until they give their name, read back off their id — the
    same words `staff` and `stand_up` mint them under. "" when nothing says."""
    place, cid = place_of(wid), counter_of(wid)
    if not place:
        return ""
    if cid:
        from . import market as market_mod

        counter = market_mod.counter(_location(world, places_mod.location_of(place)), cid)
        if counter is None:
            return ""
        return (counter.title if counter.sort != "stall"
                else f"the stallholder at {counter.label}")
    kind = ""
    for f in getattr(scene, "founded", None) or ():
        fid = f.get("id") if isinstance(f, dict) else getattr(f, "id", "")
        if str(fid or "") == place:
            kind = str((f.get("kind") if isinstance(f, dict) else getattr(f, "kind", ""))
                       or "")
            break
    return places_mod.keeper_of(f"the {kind}" if kind else label_of(place))[0]


def _on_the_page(name: str, transcript) -> bool:
    """Whether the page or the player has used this name: the full name, or its given
    name as a word, in any transcript entry."""
    parts = str(name or "").split()
    if not parts:
        return False
    import re

    forms = {" ".join(parts), parts[0]} if len(parts[0]) >= 3 else {" ".join(parts)}
    rx = re.compile(r"(?<![\w'’-])(?:" + "|".join(re.escape(f) for f in forms)
                    + r")(?![\w-])")
    for entry in transcript or ():
        text = entry.get("text") if isinstance(entry, dict) else entry
        if text and rx.search(str(text)):
            return True
    return False


def unname_on_sight(scene, world, transcript) -> list[tuple[str, str]]:
    """On load: a keeper an older build named on sight goes back to their descriptor,
    unless the name has already reached the page. Returns [(ref, "restored"|"kept")].

    Before owner ruling F1 (2026-09-30) every keeper was minted with `name = true_name`
    (since 2026-09-19). Measured on Sam's save: 4 keepers — Oren Bramble (the master of
    the market), Soren Moorcock (the general store), Gorm Vesper and Quin Nutmeg. Oren
    and Soren never appeared in any of the 82 transcript entries; Gorm's and Quin's names
    were on the page (the narrator used them unprompted, from the leaked brief). So:

      * a name never on the page is taken back — the panel shows the descriptor, and the
        name is still theirs to give when asked (2 of 4 on Sam's save);
      * a name the page has already used is kept: the player has read it, and taking back
        a name the story has said is a contradiction the player sees, which is worse than
        the leak that put it there (2 of 4).

    The page, not the player's own words alone, because the transcript is everything the
    player has read. Nothing else on the actor changes, and a world-marked public name
    (`publicly_known`) is left alone."""
    out: list[tuple[str, str]] = []
    for ref, actor in list((getattr(scene, "people", None) or {}).items()):
        wid = str(getattr(actor, "world_entity_id", "") or "")
        if getattr(actor, "is_pc", False) or not is_keeper(wid):
            continue
        name = str(getattr(actor, "name", "") or "")
        if not name or name != str(getattr(actor, "true_name", "") or ""):
            continue                       # already a descriptor, or renamed in play
        if publicly_known(world, place_of(wid), wid):
            continue
        if _on_the_page(name, transcript):
            out.append((ref, "kept"))
            continue
        shown = descriptor_of(scene, world, wid)
        if not shown:
            continue
        actor.name = shown
        out.append((ref, "restored"))
    return out


def retire_stale_masters(scene, world) -> list[str]:
    """On load: a market keeper an older build stood up where I2 says there is none, kept
    as a resident who lives there. Returns the refs retired.

    I2 (merged 2026-09-29) ruled that a village's market has no master (Q28) and that a
    master sells nothing; a save from before it holds the old `keeper:<market>` in a
    village — measured at G3, neither master (the village has none, so `master_here` is
    never asked) nor seller (`seller_in` reads the general store's holder), a person the
    counters could not use and the brief still introduced as "the master of the market".

    Never deleted: they are somebody the player may have met, with a name and a face. The
    keeper's id is taken off them (so no counter or master rule reads them), their note
    says what they are now, and they get a population record at the market as a resident
    who lives in the settlement (`population.keep_as_resident`), so the finder and the
    day's rounds treat them like anybody else who lives there."""
    from . import population

    out: list[str] = []
    for ref, actor in list((getattr(scene, "people", {}) or {}).items()):
        wid = str(getattr(actor, "world_entity_id", "") or "")
        if getattr(actor, "is_pc", False) or not is_keeper(wid) or counter_of(wid):
            continue
        place = place_of(wid)
        if not place or not places_mod.runs_it(label_of(place)):
            continue
        location = _location(world, places_mod.location_of(place))
        if places_mod.has_a_master(places_mod.scale_of(location)):
            continue
        actor.world_entity_id = None
        town = str(getattr(location, "name", "") or "") if not isinstance(location, str) \
            else ""
        actor.notes = ("Lives in " + (town or "the village")
                       + ", and is often about the market; keeps no counter there.")
        population.keep_as_resident(scene, actor, place)
        out.append(ref)
    return out


def master_here(scene):
    """The master of the market the party is standing in, if they are here; else None.
    The market's own keeper (`keeper:<market>`, no counter), at their place."""
    at = str(getattr(scene, "at", "") or "")
    if not at or not places_mod.runs_it(label_of(at)):
        return None
    who = keeper_in(scene, at)
    if who is None or getattr(who, "at", "") != at or who.ref not in scene.actors:
        return None
    return who


# What occupies the master, by the residency slot (midnight = 0, three hours a slot): the
# clerk of the market's day as Colchester's records and the court of piepowder give it —
# the pitches set out and the stall money taken when the market bell rings, the measures
# and the weights walked through the rows, a quarrel heard on the spot, and the day's count
# (docs/design-d-people.md §4.8). Words, never numbers.
_OCCUPATION = {
    2: "setting out the pitches and taking the stall money",
    3: "walking the rows with the measures, weighing what is sold by weight",
    4: "walking the rows with the measures, weighing what is sold by weight",
    5: "hearing a quarrel between two stallholders, on the spot",
    6: "at the day's count, with the takings and the tally sticks",
}
# The slot the master hears people in: the evening count, when the market's business is
# done and a person who waited can be heard. `audience.hearing` grants a hearing then, so
# the brush-off's "come back at the count" is a promise the rules keep.
COUNT_SLOT = 6


def occupation(master, clock: int, world=None, location_id: str = "") -> str:
    """What the master is doing now, in words, flavoured by what the settlement trades
    in when the world says (`play.settlements[].sells`)."""
    from .residency import slot_of

    slot = slot_of(int(clock or 0))
    doing = _OCCUPATION.get(slot, "gone from the rows; the market is shut")
    sells = ""
    if world is not None and location_id:
        row = next((s for s in ((getattr(world, "play", None) or {}).get("settlements") or [])
                    if isinstance(s, dict) and str(s.get("id")) == str(location_id)), None)
        sells = " ".join(str((row or {}).get("sells") or "").split()).rstrip(".")
    if sells and slot in (3, 4):
        doing += f", and keeping an eye on the {sells[:1].lower()}{sells[1:]} coming in"
    return doing


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
        at = str(getattr(scene, "at", "") or "")
        keeper = keeper_in(scene, at)
        if keeper is None and at:
            # A village market has no master (Q28): whoever keeps any of its counters
            # keeps its hours.
            keeper = next((a for a in scene.people.values()
                           if is_keeper(getattr(a, "world_entity_id", "") or "")
                           and place_of(a.world_entity_id) == at), None)
    if keeper is None:
        return ""
    place = place_of(keeper.world_entity_id)
    if place != getattr(scene, "at", None):
        return ""
    return shut_line(place, int(getattr(scene, "clock_minutes", 0) or 0),
                     getattr(scene, "founded", None) or (), who=str(keeper.name or ""))
