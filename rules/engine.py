"""The rules engine: it owns all state and all rolls.

The GM agent proposes intents; this resolves them. Nothing here asks a model anything, and
nothing here can be talked out of a result — resolution is arithmetic over the sheet.

Resolution is a state machine rather than a function, because a player roll is an
asynchronous human input in the middle of an intent list. `run()` returns either a
finished `Resolution` or one that is `awaiting_player_roll`, and `resume()` continues the
same list from exactly where it stopped.
"""
from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from . import biomes
from . import goods
from . import ontheway
from . import casting
from . import compulsion
from . import consumables
from . import crafting
from . import dc as dc_mod
from . import effectspec
from . import foraging
from . import ingredients as ing_mod
from . import resources
from . import states
from . import survival
from . import troops as troops_mod
from . import water
from . import worldclass
from . import grid as gridmod
from . import guards as guards_mod
from . import reactions
from . import spells as spells_mod
from . import weapons as weapons_mod
from .activeeffect import ActiveEffect
from .guards import Guard, Packet
from .dice import Dice, Modifier, Roll, d20_succeeds, natural_said
from .grid import Grid
from . import hazards
from .intents import AMOUNT_OPS, Intent, IntentError, parse_all
from .sheet import Actor
from .tables import (
    CONDITIONS,
    ABILITY_FULL, MANEUVERS, SAVES, SIZE_ORDER, WEAPONS, maneuver_text,
    normalise_damage_type,
)


# --- Scene state -------------------------------------------------------------------

# How far each zone puts somebody, in five-foot squares. `engaged` is adjacent: within
# reach, which is the whole meaning of the word and the difference between a brawl and
# two people shouting across a room.
SQUARES_BY_ZONE = {"engaged": 1, "near": 3, "far": 8}
FEET_PER_SQUARE = 5


def zone_for_feet(feet: int) -> str:
    """The word for a distance. A bowshot is `far` however far past `far` it is."""
    squares = max(1, int(feet) // FEET_PER_SQUARE)
    if squares <= SQUARES_BY_ZONE["engaged"]:
        return "engaged"
    if squares <= SQUARES_BY_ZONE["near"]:
        return "near"
    return "far"


def _sentence(name: str) -> str:
    """A name at the start of a sentence. Ships and keepers carry their article — "the
    Cold Widow" — and a tell that opens with a lower-case "the" reads as a typo."""
    said = str(name or "")
    return said[:1].upper() + said[1:]


def _and_list(names) -> str:
    got = [str(n) for n in names if str(n).strip()]
    if len(got) <= 1:
        return got[0] if got else ""
    return ", ".join(got[:-1]) + " and " + got[-1]


def _drowning_ground(actor) -> bool:
    """Whether this creature is under water it cannot breathe.

    Two questions, both asked through their own vocabulary: the terrain comes off the
    place id (`places.terrain_of` parses and looks nothing up) and whether the creature
    can breathe the stuff is a tag. A shark is not drowning; a knight in plate is.
    """
    from . import places as places_mod

    if not water.is_under(places_mod.terrain_of(str(getattr(actor, "at", "") or ""))):
        return False
    return not water.breathes_water(actor)


class _Here(Mapping):
    """Who is in the party's place: a read-only view over `Scene.people`.

    Computed on every call and cached nowhere, on purpose. Bevy shipped a hierarchy
    with both `Parent` and `Children` as real components kept level by commands, and
    replaced it in 0.16 with a single source of truth whose other side is derived,
    because writing either side by hand "may result in hierarchy invalidation" — they
    shipped a polling diagnostic to catch the corruption before giving up on the
    design. Inform computes "location of" by walking the tree on every call. At a dozen
    actors the walk costs nothing, and there is nothing for `restore` to invalidate.

    A `Mapping`, not a dict: `.items()`, `.values()`, `.get`, `[ref]`, `in`, `len` and
    iteration are the whole read surface 171 production sites use, and assignment,
    `pop`, `update` and `del` raise — so the five sites that wrote the roster directly
    cannot keep working by accident.
    """

    __slots__ = ("_scene",)

    def __init__(self, scene: "Scene"):
        self._scene = scene

    def __getitem__(self, ref: str) -> "Actor":
        actor = self._scene.people[ref]
        if actor.at != self._scene.at:
            raise KeyError(ref)
        return actor

    def __iter__(self):
        here = self._scene.at
        return (r for r, a in self._scene.people.items() if a.at == here)

    def __len__(self) -> int:
        here = self._scene.at
        return sum(1 for a in self._scene.people.values() if a.at == here)

    def __repr__(self) -> str:
        return f"_Here({dict(self)!r})"


@dataclass
class Scene:
    """Everything the engine owns. The world agent may read this and writes none of it —
    see docs/intent-protocol.md §8."""
    location_id: str | None = None
    # Where inside that location the party is standing: "the taproom", "the market
    # square". The world models a city; it does not model the rooms in it, so a move
    # from a stall to the square changed nothing the engine could see — `travel` is a
    # BIOME transition and both are urban. Found in a live session: the player walked
    # out of a building, the GM narrated the square, and the next beat was back inside
    # by the fire, because nothing had told the engine the room was over.
    #
    # `at` holds the place's ID and nothing else. The list of places a location has is
    # DERIVED — `rules.places.spots_for` is deterministic and seeded off the location's
    # own durable id — so there is no collection to save, nothing to migrate, and no way
    # for a stored list to drift from the generator that made it.
    #
    # It replaced a free-text `spot` written straight from a model param, which was the
    # narrator establishing a fact rather than proposing one, and which gave "where the
    # party is" a second writer beside `thread["where"]`.
    at: str = ""
    # Everyone the campaign holds, wherever they are. THE STORE. `actors` below is the
    # derived view of who is in the party's place, and it is the only thing most of the
    # engine reads; the store is for the world clock (time passes for the merchant in
    # the next room), the ageing loop (a body the party walked away from still leaves),
    # ref minting (a ref worn by somebody elsewhere is not free) and persistence.
    people: dict[str, Actor] = field(default_factory=dict)
    # The high-water mark for `cN` refs. Refs are minted once and never reused — the
    # lowest-free scan that used to hand them out recycled a departed archer's 120-foot
    # spawn distance onto the next `c1`, and under containment it would mint a living
    # creature's ref a second time. Only `Scene.add` advances it; a refused turn's
    # snapshot restores it, so a ref minted by a turn that did not happen is legitimately
    # reissued by the next one.
    minted: int = 0
    zones: dict[str, str] = field(default_factory=dict)
    # The map, and where everybody is standing on it. Both optional: a scene with no grid
    # behaves exactly as it did before there was one, which is what let the grid arrive
    # without changing a line of the intent protocol.
    grid: Grid | None = None
    positions: dict[str, tuple[int, int]] = field(default_factory=dict)
    # Reactions spent this round, by "<ref>:<budget>". Not a pool on the sheet: an attack
    # of opportunity is an allowance for other people's turns, it refills at the top of
    # the round rather than on rest, and it belongs to the encounter rather than the
    # character — a scene that ends takes it with it.
    reacted: dict[str, int] = field(default_factory=dict)
    # Standing arrangements about damage aimed at somebody: who interposes for whom. On
    # the scene rather than on either actor, because a guard is a *relationship* — stored
    # on the guardian it is lost when you look up the protected creature, and stored on
    # both it is two copies to keep level.
    guards: list["Guard"] = field(default_factory=list)
    # Blood the bender has put on the ground and can still reach. Half of Blood Spike
    # and most of Coagulator act on these — siphoning them, detonating them, standing
    # in them, trading places with them — so they have to be things the scene holds
    # rather than a phrase in the narration. A pool knows where it is, whose it is and
    # how much blood is in it; everything else about it is the ability's business.
    pools: list["BloodPool"] = field(default_factory=list)
    # Things put into the scene that are neither creatures nor modifiers: fog, walls,
    # lights, lingering hazards. See `Manifestation`, which explains why the grid does
    # almost all of the work.
    manifests: list["Manifestation"] = field(default_factory=list)
    # Effects waiting for something to happen — a round to pass, a blow to land, a
    # creature to walk in. See `Ward`.
    wards: list["Ward"] = field(default_factory=list)
    initiative: list[tuple[str, int]] = field(default_factory=list)
    # Who has taken a turn this encounter. A combatant who has not acted is flat-footed,
    # which is usually several points of AC and is the thing an ambush is *for*.
    acted: set[str] = field(default_factory=set)
    # Who has already attacked whom this encounter, as "attacker>defender". Swift
    # Strikes keys off it: the passive grants its extra swings only on *subsequent*
    # attacks against the same target, so the fight has to remember first blood.
    attacked: set[str] = field(default_factory=set)
    # The round each combatant last spent its move action walking the grid, by ref. The
    # one piece of action economy the engine keeps, and kept for one reader: the closing
    # step before a blow (`Engine._closing_step`, the owner's ruling of 2026-09-29) is a
    # move action, and "in a normal round, you can perform a standard action and a move
    # action" (aonprd.com/Rules.aspx?ID=129) — a creature that has already walked this round does not walk
    # again for free. A round number rather than a set cleared on the turn, so it needs
    # no second ticker: a stale entry is simply a round that is not this one. Only a
    # square actually changed counts — a zone relabel moves no body (docs/fix-interfaces
    # §3.4) and must not cost the step that would.
    move_spent: dict[str, int] = field(default_factory=dict)
    round: int = 0
    clock_minutes: int = 0
    # The narrative thread: what the player is engaged in when no op carries it —
    # following somebody, questioning somebody, watching a door. Measured live
    # without it: the player followed two guards toward a market, typed "I continue
    # to follow", and the narrator wrote them into a haunted house, because the
    # guards were prose inventions no state anywhere remembered. The thread is
    # state the engine owns: {"doing", "subject", "age"} — the prose layer is fed
    # it as fact and scrubbed against it, first slice of the world-state ledger.
    thread: dict = field(default_factory=dict)
    # The cast ledger, slice 2 of the world state: people the narration has
    # introduced who are not (yet) engine actors. Each entry {"who": the phrase
    # the prose used, "turn": when}. The brief feeds them back as fact so the
    # narrator cannot forget its own cast, and interacting with one promotes it
    # to a real actor through the ordinary spawn machinery. Prose invented them;
    # the ledger just refuses to let prose disinvent them.
    cast: list = field(default_factory=list)
    # Things that are not held by anybody, and things that are — THE PROPS LEDGER.
    # One record per object the fiction has touched, with exactly one of `at` (a place
    # id: it lies there) or `held_by` (a ref: it is in their hands), and beside it
    # `owner` (whose it is, which is not the same question — Creation Kit's per-object
    # owner beside the stolen flag; Inform's containment tree where a dropped thing
    # lands on the room's floor), `from_` (its provenance: "fragments of the
    # challenger's club"), `state` (intact / broken / destroyed / fragments), `turn`.
    # Measured 2026-09-18: a sundered club became "a chunk of wood" the player picked
    # up, then "the smoldering wood of the table" two beats later — no check grounded
    # THINGS the way the cast ledger grounds people. Every transition goes through
    # `Scene.place_prop` / `Scene.hold_prop`, never a direct write.
    props: list[dict] = field(default_factory=list)
    # How long each fallen non-PC has been lying here, ref -> turns. Bodies get a
    # short grace for looting and then the scene lets them go on its own — the
    # live panel carried four corpses and a bleeding man through an entire market
    # visit because nothing but a biome change ever swept the floor.
    fallen: dict = field(default_factory=dict)
    # What bystanders just saw, {"note", "age"}. A public killing the crowd
    # shrugged off — the player murdered a merchant mid-market and the next
    # stall-keeper chatted amiably — because nothing carried the event forward.
    heat: dict = field(default_factory=dict)
    # What each shop has sold, as "place|stall|day|material" -> count. A stall's shelf is
    # drawn rather than stored (see `rules.market`), so this is the only part that has to
    # survive a save: the one legendary on the shelf has to stay sold once it is bought.
    # The day is in the key, so yesterday's sales stop counting without anything sweeping
    # them up.
    market_taken: dict[str, int] = field(default_factory=dict)
    # How far a spawn asked to arrive, in feet, until the layout uses it.
    # `begin_encounter` builds the grid *after* `spawn` runs, so a spawn cannot
    # place anybody itself and its distance was simply lost — every archer
    # opened at the `far` default of forty feet however far they said they were.
    spawn_feet: dict[str, int] = field(default_factory=dict)
    # Checks already paid for, "skill|dc|place" → the day it was paid. A DC beaten once
    # is a challenge; the same DC beaten nine times in a row is a grind, and a ledger
    # that paid for the grind would send the player to climb the same wall all
    # afternoon (`rules/xp.py`, challenge_award).
    rewarded: dict[str, int] = field(default_factory=dict)
    # Finds that are booked but not yet in hand: the vein the cave worm is sitting on.
    # Each is {"guard": ref, "what": ..., "found": {...}, "stock": [...]} and pays out
    # when the guard is dead or gone (`rules/gathering.py`).
    guarded_finds: list[dict] = field(default_factory=list)
    # The situation cards on the table (`rules/cards.py`): the facts of each situation
    # in play, as dicts, kept by the engine and shown to the model when their keys
    # appear in the last few beats. The store; `cards.load`/`cards.save` are the doors.
    cards: list[dict] = field(default_factory=list)
    # Which authored line each pool of the narrator's backstops used last, by pool
    # (`narration.least_recently_used`). Measured before it existed: four kills, four
    # byte-identical death sentences, because the pool had one line and nothing
    # remembered it had been said. Kept on the scene so a reload does not reset the
    # walk and hand the player the first line again.
    said: dict = field(default_factory=dict)
    # Two records that lived in `said` beside the narrator's line rotation until
    # 2026-09-25, in a dict with no schema: what a routed crowd still owes in experience
    # (paid when the fight settles, `_rout` → `_settle_xp`), and the payments agreed in
    # this room (the last five, for the brief). Their own fields now, saved as such; a
    # save written before carries them in `said` and is moved over on load.
    routed_xp: list = field(default_factory=list)
    agreements: list = field(default_factory=list)
    # Everybody the campaign has seen, as records (rules/population.py), keyed by a `pN`
    # id; a person who enters play is ALSO an Actor in `people`, and the record keeps the
    # ref. The user's ruling of 2026-09-25: the database may grow; it must be findable.
    population: dict = field(default_factory=dict)
    # When the party last arrived somewhere, and how many times it has: residency
    # (rules/residency.py) moves people to where their day or their road puts them only
    # when the party arrives, never while it stands with them — the ruling that the woman
    # in the doorway "should stay there until i leave or something moves them".
    # `settled` is the arrival `Engine.settle_people` last answered; `came_along` the
    # people moved WITH the party since, whom the plan moved and who stay moved until
    # the party leaves them.
    arrived: int = 0
    moves: int = 0
    settled: int = 0
    came_along: list = field(default_factory=list)
    # The resolution record, for tests and debugging. Nothing in the app reads it, and it
    # is deep-copied by every snapshot, so it keeps only the last LOG_KEPT outcomes.
    LOG_KEPT = 200
    # Places minted in play (`rules/places.py`, doors two and three): the stored
    # exception to "derived, never stored", since the player made them. Place dicts
    # with a parent and an owner; `places.with_founded` grafts them onto the derived
    # set by parent at read time. `Engine.found`/`Engine.venture` are the doors.
    founded: list[dict] = field(default_factory=list)
    # The schemes running in this campaign (rules/schemes.py): one instance per opened
    # scheme — its filled slots, the steps that fired and when, its outcome. Stored,
    # like `founded`, because play made it; read back through the one ticker.
    schemes: list[dict] = field(default_factory=list)
    # Which counters have had somebody put behind them (`rules/keepers.py`): place ids,
    # once each, for ever. The ledger is the PLACE and not the person on purpose — a
    # keeper who is dead is swept out of the scene two turns later, and a check for
    # "is anybody standing here" would mint the murdered smith a second time.
    staffed: list[str] = field(default_factory=list)
    # When each creature was last talked round, by ref, as the world clock's minute.
    # "You cannot use Diplomacy to influence a given creature's attitude more than once
    # in a 24 hour period" (Core Rulebook) — the limit is on TRYING, so a failed attempt
    # spends the day too. Without it the check is free and a player rolls until the dice
    # agree with them, which is the shape of every social system that stops mattering.
    swayed: dict[str, int] = field(default_factory=dict)
    # The ships this campaign knows, as `ships.Vessel` dicts — the one the party took
    # passage on, the one closing on it. Stored rather than derived, unlike a place: a
    # room does not move and a hull does not heal, so where a ship is and how much of it
    # is left are facts play made and nothing can recompute.
    vessels: list[dict] = field(default_factory=list)
    # The engagement at sea, when there is one: which two ships, how far apart, and
    # whether the grapnels are in. `{"ours", "theirs", "range", "grappled"}`.
    #
    # A band and not a grid. The fast-play rules use a mat at thirty feet to the square;
    # this app has a narrator instead of a picture, and a picture is the thing Pillars of
    # Eternity II's naval combat could not give its players either — they could not tell
    # how the ships were oriented, so the fight was noise before the boarding that decided
    # it. The band is what a player can hold in their head from prose alone.
    sea: dict = field(default_factory=dict)
    # The road left unwalked, when a journey was stopped short of the far end:
    # {"to", "to_name", "hours_left", "from"}. Stored rather than derived, like
    # `founded` and for the same reason — how far along a road a party got is
    # something that HAPPENED, and no amount of looking at the map recovers it.
    # Without it, the second half of an interrupted journey would charge the whole
    # road again, which makes being interrupted a punishment for the dice rather
    # than an event (`rules/ontheway.py`).
    road: dict = field(default_factory=dict)
    # --- the 2026-09-28 fix pass (docs/fix-interfaces.md §2.4) ---------------------------
    # Every one of these is saved only when it differs from what a save without it reads
    # back as, so a campaign written before them round-trips byte for byte. Nothing in
    # Phase 1 writes them; the lanes named beside each do.
    #
    # The number the STORY draws from — which start, which lead, which keeper — and not
    # the dice. `Campaign.engine()` builds `Dice(campaign.seed)` on every one of its call
    # sites, so a fixed dice seed would replay the same rolls every turn
    # (docs/design-c-starts.md §5). On the scene because `rules/` has to reach it.
    # Random at creation; for a campaign made before it, derived from the campaign id
    # on load (`opening._seed_from`), which is stable across processes where `hash()`
    # is not. Lane C.
    story_seed: int = 0
    # Which start document the campaign opened with, and what it bound:
    # {"id", "kind", "where", "slots": {name: ref}, "hand_off": {...}, "tells": [str]}.
    # Empty is the legacy opening, byte-identical. Lane C.
    start: dict = field(default_factory=dict)
    # World entity ids already given a part — by a background tie, a scheme slot, the
    # start's lead — so two stories do not cast one person twice. One set shared by
    # every binder instead of a local `set()` in each. Lane C.
    spoken_for: list[str] = field(default_factory=list)
    # World entity ids a background tie names: people who knew the character before the
    # first turn. The arrival door (`arrive`/`move`) gives each of them `bond.knows-you`
    # when they come in (`backgrounds.recognise`). Lane C writes it; Lane D reads it.
    acquainted: list[str] = field(default_factory=list)
    # Who said what to whom, in order: the conversation panel's store (§2.10's Entry).
    # Entry keys this build does not know are kept, not dropped. Lane F.
    conversation_log: list[dict] = field(default_factory=list)
    conversation_seq: int = 0
    log: list[dict] = field(default_factory=list)

    # Whose turn it is: an index into `initiative`. -1 outside an encounter. Written only
    # by `advance_turn`, the encounter's opening, and the two order-changing doors below
    # (`enrol`, `leave_order`) — because an index silently re-points at somebody else
    # whenever the list it indexes changes.
    turn: int = -1
    # Set when the creature holding the turn left the order: their successor now sits in
    # the slot `turn` points at, so the next advance must land THERE rather than one past
    # it. Saved, because a save between the removal and the advance would otherwise skip
    # that creature on reload.
    turn_is_next: bool = False
    # side name -> refs, as `begin_encounter` declared them. Kept so the engine can tell
    # when a fight is over without guessing who was fighting whom.
    sides: dict[str, list[str]] = field(default_factory=dict)

    # Suspended-resolution state. Non-empty only between a dice prompt and the player's
    # answer.
    pending_intents: list[dict] = field(default_factory=list)
    pending_outcomes: list[dict] = field(default_factory=list)
    pending_partial: dict = field(default_factory=dict)
    awaiting: dict | None = None

    # What the dying did at the top of this round, for the GM to narrate.
    bleeding: list[dict] = field(default_factory=list)
    # What the standing hazards did at the top of this round — the fire in the cloud, the
    # tentacles' squeeze. The same shape as `bleeding` and read the same way: something
    # happening to a character every round with nothing said about it is the thing a
    # player only finds out about when they are dead.
    hazards: list[dict] = field(default_factory=list)
    # The scene owns no randomness of its own; the engine lends it one for the
    # round tick, so stabilisation rolls come from the same seeded stream as
    # everything else and a scene stays reproducible.
    _dice: Any = None

    def snapshot(self) -> dict:
        """Everything the scene is, deep-copied, so a refused turn can be undone.

        Resolution mutates as it goes — `_drive` applies each intent before it
        reaches the next — so an intent list that raises half-way leaves the
        earlier half standing. Measured live on 2026-09-01: a `/api/say` at
        11:08:44 returned 502, and the intents that had already resolved left
        TEN pristine thugs standing engaged in the market. Nothing wrote them to
        disk on that request, but the campaign is held in memory, so the next
        successful turn saved them. The player had killed one thug all game.

        Whole state rather than an inverse per op — the Z-machine's `@save_undo`
        answer, and for its reason: undoing by inversion needs every op to know
        how to unhappen (spawn, damage, effect application, initiative
        bookkeeping, the grid) and each one is a place the pair can drift apart.
        `deepcopy` needs none. Deliberately NOT the save format: that is a
        hand-written field list which has already proved incomplete twice — a
        reload silently deleted every ward and manifestation in the scene for
        months — and a snapshot that forgets a field is worse than none.
        """
        import copy

        # The engine lends the scene its dice for the round tick. It is shared,
        # seeded state that belongs to the engine, not the scene; copying it
        # would restore a rewound random stream along with the board.
        dice, self._dice = self._dice, None
        try:
            return copy.deepcopy(self.__dict__)
        finally:
            self._dice = dice

    def restore(self, snap: dict) -> None:
        """Put the scene back as `snapshot` found it, in place.

        In place, not by rebinding `campaign.scene`: an Engine, a GMAgent and the
        view all hold this same object, and swapping the campaign's reference
        would leave three live readers looking at the half-applied one.
        """
        import copy

        dice = self._dice
        self.__dict__.clear()
        self.__dict__.update(copy.deepcopy(snap))
        self._dice = dice

    @property
    def actors(self) -> Mapping[str, Actor]:
        """Who is in the party's place. Derived; see `_Here`."""
        return _Here(self)

    @property
    def biome(self) -> str:
        """The ground underfoot: a parse of the one coordinate, never a stored field.

        `scene.biome` was a sibling of `scene.at`, written by travel and healed by the
        campaign, and "both are urban" is exactly what let walking out of a stall change
        nothing. The place id carries its ground (`{location}~forest:the-approach`), so
        the question has one answer with one writer. Empty for a scene that has not been
        placed, which the forage and market doors already refuse out loud.
        """
        from . import places as places_mod

        return places_mod.terrain_of(self.at)

    def add(self, actor: Actor, zone: str = "near", at: tuple[int, int] | None = None) -> Actor:
        """Put a creature into the scene, HERE. A thin alias of `arrive`, kept because
        every door written before it (spawn, keepers, schemes, the opening, the
        population, the loader's tests) calls it by this name and positionally."""
        return self.arrive(actor, zone=zone, at=at)

    def arrive(self, actor: Actor, *, zone: str = "near", at: tuple | None = None,
               place_id: str | None = None, source: str = "") -> Actor:
        """Put a creature into the campaign — HERE by default. One of the two writers of
        `Actor.at`, and the one entrance for every arrival (docs/fix-interfaces.md §2.5).

        Stamped unconditionally: a roster sheet carries the place the character last
        stood in, in a campaign that may be in another world, and `if not actor.at`
        would let that id walk in.

        The keyword `at` is a GRID SQUARE and predates the place field of the same
        name on the actor; forty test sites pass it. The two are never confused in
        code because one is a tuple and the other a string, and the name stays.

        `place_id` puts them somewhere other than the party's place: recorded there,
        with a zone and no square, because a square is a fact of the room the party is
        standing in. Absent, or equal to `scene.at`, this is exactly what `add` always
        did. `source` says which door brought them (a scheme, a spawn, the opening) for
        the lanes that record it; nothing reads it yet.

        Every arrival is asked whether the character knew them before the first turn
        (`backgrounds.recognise`), which does nothing until somebody is `acquainted`.
        """
        if place_id and str(place_id).strip() and str(place_id).strip() != self.at:
            actor.at = str(place_id).strip()
            self.people[actor.ref] = actor
            self.zones[actor.ref] = zone
            self._mark_minted(actor.ref)
            self._recognise(actor)
            return actor
        actor.at = self.at
        self.people[actor.ref] = actor
        self.zones[actor.ref] = zone
        if at is not None:
            # The level comes along when one is given. Truncating to two here is what
            # kept the scene flat: every other hop — the save, `resync_zones`,
            # `grid.distance` — has taken a third coordinate since stage 2, and this
            # was the one place it was thrown away.
            self.positions[actor.ref] = (
                (int(at[0]), int(at[1])) if len(at) < 3
                else (int(at[0]), int(at[1]), int(at[2])))
        elif self.grid is not None and not actor.is_pc:
            # Somebody who comes into a room with a map stands somewhere on it, from the
            # moment they come in. The user's ruling, 2026-09-28: "people should already
            # be in the scene which means they should already have a place on the board
            # that shouldn't change unless they move." Measured the same day: in a fresh
            # campaign the foreman the scene introduced had no square at all — the ground
            # was laid before he arrived and nothing placed arrivals — so the first swing
            # at him had the fight invent one, fifteen feet off. `place_by_zone` measures
            # from the player's real square, and does nothing while they have none.
            self.place_by_zone([actor.ref])
        self._mark_minted(actor.ref)
        self._recognise(actor)
        return actor

    def _mark_minted(self, ref: str) -> None:
        # The mark only ever rises. Loading a save, spawning, promoting a cast entry all
        # come through the arrival door, so a save from before the mark existed heals
        # itself to the highest ref it holds on the first load.
        m = re.fullmatch(r"c(\d+)", str(ref))
        if m:
            self.minted = max(self.minted, int(m.group(1)))

    def _recognise(self, actor: Actor) -> str:
        """Somebody a background tie names knows the character on sight. Asked on every
        arrival and every move, answered by `backgrounds.recognise`; inert while
        `acquainted` is empty, which it is until Lane C's `bind` writes it."""
        if actor.is_pc or not getattr(self, "acquainted", None):
            return ""
        from . import backgrounds

        return backgrounds.recognise(self, actor)

    # --- the map, when there is one ------------------------------------------------------

    @property
    def has_grid(self) -> bool:
        """A scene without a map is not a broken scene. Most of them do not need one — a
        conversation in a tavern has no squares — and combat still resolves off zones."""
        return self.grid is not None

    def position(self, ref: str) -> tuple[int, int] | None:
        return self.positions.get(ref)

    def settle_levels(self) -> None:
        """Put everybody at the height of the ground they are standing on.

        The heightmap was inert without this, and inert in the way this whole run of work
        keeps finding: a dais was drawn, saved and measured, and a creature standing on it
        was still at level zero, so it got no higher ground and nothing could tell it was
        up there. A raised square nobody is raised by is scenery.

        The rule is that **a creature which is not flying or climbing is on the floor** —
        not "keeps whatever level it was given" — because that avoids having to tell an
        explicit level 0 from an absent one, which is the empty-versus-absent trap and is
        how a creature would end up standing inside a dais.

        A flier keeps its own height, and never less than the ground beneath it.
        """
        if self.grid is None:
            return
        for ref, spot in list(self.positions.items()):
            actor = self.actors.get(ref)
            if actor is None:
                continue
            ground = self.grid.ground(spot)
            if actor.can_move_vertically():
                now = max(spot[2] if len(spot) > 2 else 0, ground)
            else:
                now = ground
            # A two-tuple when the answer is the ground, because that is what a
            # two-tuple has meant since the third axis was added and it is what every
            # save on disk and every test in the suite is written in. Stamping
            # `(x, y, 0)` on everybody says the same thing in a way nothing else agrees
            # with.
            self.positions[ref] = ((spot[0], spot[1]) if not now
                                   else (spot[0], spot[1], now))

    def occupied(self, ignore: str = "", level: int | None = None) -> set[tuple[int, int]]:
        """Every square something is standing on, for movement to route around.

        `level` filters to the creatures whose own body reaches that level, because a
        body only blocks the ground it is actually on: a spider clinging to a ceiling
        twenty feet up does not stop anybody walking underneath it, and before this it
        did — it held the square beneath it against every route on the floor.

        Overlap rather than equality, so a Large creature standing on the floor still
        blocks the level above its feet, which is where its chest is.
        """
        from .grid import footprint, height_squares

        out: set[tuple[int, int]] = set()
        for ref, anchor in self.positions.items():
            if ref == ignore or ref not in self.actors:
                continue
            actor = self.actors[ref]
            if actor.has_condition("dead"):
                continue
            if level is not None:
                lo = anchor[2] if len(anchor) > 2 else 0
                if not lo <= level <= lo + height_squares(actor.size) - 1:
                    continue
            out.update(footprint(anchor, actor.size))
        return out

    def distance_between(self, a: str, b: str) -> int | None:
        """Feet between two creatures, or None when the scene has no map to measure on.

        None rather than 0 or a guess: "we are not tracking that" and "they are touching"
        are answers a caller has to tell apart, and a silent 0 makes every reach check
        succeed on a mapless scene.
        """
        from .grid import distance_between as gap

        pa, pb = self.positions.get(a), self.positions.get(b)
        if not self.has_grid or pa is None or pb is None:
            return None
        return gap(pa, self.actors[a].size, pb, self.actors[b].size)

    def place_by_zone(self, refs: list[str], feet: int | None = None) -> None:
        """Put these actors on the map at the distance their zone claims.

        Needed because a zone set *after* the board was laid — anything spawned
        mid-fight — had nowhere to be put, and `resync_zones` runs the other way: it
        reads distance off the map and names it, so on its own it simply renamed the
        zone back to whatever the stale position implied.
        """
        pc = self.pc()
        if self.grid is None or pc is None or pc.ref not in self.positions:
            return
        px, py = self.positions[pc.ref]
        taken = set(self.positions.values())
        for ref in refs:
            if ref not in self.actors:
                continue
            away = (max(1, int(feet) // FEET_PER_SQUARE) if feet
                    else SQUARES_BY_ZONE.get(self.zones.get(ref, "near"), 3))
            # The default board is a hundred feet square and a bowshot is not. Grown
            # rather than clamped: clamping put the archer's target at the edge of the
            # map and called it 100 feet, which is a different fight from the one the
            # player described.
            if self.grid is not None and px + away >= self.grid.width:
                self.grid.width = px + away + 2
            spot = self._free_spot_at(px, py, away, taken)
            if spot is not None:
                self.positions[ref] = spot
                taken.add(spot)

    def _free_spot_at(self, px: int, py: int, away: int,
                      taken: set) -> tuple[int, int] | None:
        """A free square about `away` squares from (px, py), spread around it.

        Reported from the table 2026-09-17 with a picture of the board: seven creatures
        in a single vertical line, one per row, all in the same column. The old search
        fixed x at `px + away` and walked y — so every actor placed at one zone landed
        in the same column by construction, and a market brawl looked like a bus queue.

        The ring is walked by offset rather than by angle because the board is squares
        and the distance that matters is `grid.distance`, which counts diagonals
        5-10-5. Candidates are ordered by how far their real distance sits from the one
        the zone asked for, so the first free square is the one that keeps the zone
        honest; ties break by a fixed rotation so the spread is deterministic and a
        seeded test can assert where everybody stood.
        """
        from .grid import distance

        if self.grid is None:
            return None
        want_ft = away * FEET_PER_SQUARE
        anchor = (px, py)
        best: list[tuple[int, int, tuple[int, int]]] = []
        reach = away + 3
        for dx in range(-reach, reach + 1):
            for dy in range(-reach, reach + 1):
                if dx == 0 and dy == 0:
                    continue
                x, y = px + dx, py + dy
                if not (0 <= x < self.grid.width and 0 <= y < self.grid.height):
                    continue
                if (x, y) in taken or (x, y) in self.grid.blocked:
                    continue
                off = abs(distance(anchor, (x, y)) - want_ft)
                # Second key spreads the ring: squares are tried in a rotation around
                # the anchor rather than column by column, which is the whole defect.
                best.append((off, (abs(dx) * 7 + abs(dy) * 13 + (dx < 0) * 3
                                   + (dy < 0) * 5) % 29, (x, y)))
        if not best:
            return None
        best.sort()
        return best[0][2]

    def resync_zones(self) -> dict[str, str]:
        """Re-derive every zone from the map.

        The GM keeps speaking in engaged / near / far and now those words are measured
        rather than asserted. Zones are kept rather than dropped so a scene can lose its
        map — or never have had one — without any of the rest of the engine noticing.
        """
        from .grid import zone_between

        pc = self.pc()
        if not self.has_grid or pc is None or pc.ref not in self.positions:
            return dict(self.zones)
        anchor = self.positions[pc.ref]
        for ref, actor in self.actors.items():
            if ref == pc.ref or ref not in self.positions:
                continue
            self.zones[ref] = zone_between(self.positions[ref], actor.size,
                                           anchor, pc.size)
        return dict(self.zones)

    def refs(self) -> list[str]:
        return list(self.actors)

    def get(self, ref: str) -> Actor | None:
        return self.actors.get(ref)

    def pc(self) -> Actor | None:
        # The STORE, not the view. "Here" is the PC's place and the view is everyone in
        # the PC's place, so finding the PC through the view is circular — and sixty
        # callers dereference this without a guard.
        return next((a for a in self.people.values() if a.is_pc), None)

    # --- turn order -------------------------------------------------------------------

    @property
    def in_encounter(self) -> bool:
        return bool(self.initiative) and self.turn >= 0

    def current_ref(self) -> str | None:
        if not self.in_encounter:
            return None
        return self.initiative[self.turn % len(self.initiative)][0]

    def turn_holder(self) -> str | None:
        """Whoever holds the turn, read BEFORE anything changes the order.

        No modulo, unlike `current_ref`: an out-of-range `turn` answers None, which is how
        `leave_order` tells "the holder left" from "the holder moved"."""
        if not (0 <= self.turn < len(self.initiative)):
            return None
        return self.initiative[self.turn][0]

    def _point_at(self, was: str | None) -> None:
        if not self.initiative:
            self.turn = -1
            self.turn_is_next = False
            return
        at = next((i for i, (r, _) in enumerate(self.initiative) if r == was), None)
        self.turn = at if at is not None else min(self.turn, len(self.initiative) - 1)

    def enrol(self, ref: str, roll: int) -> None:
        """Put a newcomer into the initiative order; the turn stays where it was.

        Measured 2026-09-20 as a flake of `test_a_free_action_does_not_hand_the_round_to
        _the_enemy`: the narrator introduced somebody, `join_fight` rolled them in, their
        unseeded d20 beat the player's, they sorted in ABOVE the player — and the turn the
        player still held went to them. Four sites wrote their own version of this; three
        read `current_ref()` AFTER the append and the sort, so the creature they "kept"
        was already whoever the sort had moved into the slot, and one (a troop arriving)
        adjusted nothing at all. This is the one door now.
        """
        was = self.turn_holder()
        self.initiative.append((ref, roll))
        self.initiative.sort(key=lambda t: -t[1])
        if self.turn >= 0:
            self._point_at(was)

    def leave_order(self, ref: str) -> None:
        """Take `ref` out of the initiative order, and keep the turn honest.

        Somebody else leaving: the turn stays with its holder. The HOLDER leaving (dead on
        their own turn, routed, walked out): their successor slides into the slot and is
        next — measured 2026-09-25, the next `advance_turn` stepped one past the slot and
        skipped them. The last slot leaving wraps to the top, which is the round's end.
        """
        if not any(r == ref for r, _ in self.initiative):
            return
        was = self.turn_holder()
        idx = next(i for i, (r, _) in enumerate(self.initiative) if r == ref)
        self.initiative = [(r, roll) for r, roll in self.initiative if r != ref]
        if not self.initiative:
            self.turn = -1
            self.turn_is_next = False
            return
        if self.turn < 0:
            return
        if was != ref:
            self._point_at(was)
            return
        if idx < len(self.initiative):
            self.turn = idx
            self.turn_is_next = True
        else:
            self.turn = len(self.initiative) - 1
            self.turn_is_next = False

    def conscious(self, ref: str) -> bool:
        """Still up, and still in the fight — which is not the same as able to act now.

        Exactly 0 hit points is *disabled*, not unconscious: you are on your feet and
        may take a single action, at the cost of a hit point. Requiring `hp > 0` here
        dropped a disabled character out of the initiative order and ended the fight
        around them while they were still standing.

        It used to open with `not a.can_act()`, which is the other question, and all
        five of its callers wanted this one: how many sides are still standing, who is
        left to target, who is company, who is marked "out" on the panel. Answering
        them with can-act meant a stunned enemy — no turn, very much still fighting —
        ended the encounter and settled the XP while standing in front of the player.
        """
        a = self.actors.get(ref)
        return a is not None and not a.is_down

    def advance_turn(self) -> str | None:
        """Move to the next combatant who can still act, and return their ref.

        Skips the dead and unconscious rather than stalling on them, and ends the
        encounter when only one side is left standing. Without this a fight had no way
        to proceed past the player's first swing: initiative was rolled and then nothing
        ever consulted it.
        """
        if not self.initiative:
            return None
        # Cleared once per call rather than per rollover, so the lines below can
        # accumulate across however many rounds this one call has to skip through.
        self.hazards = []
        self.bleeding = []
        for _ in range(self.MAX_SKIPPED_ROUNDS):
            ref = self._next_able()
            if ref is not None:
                return ref
            # Nobody could act this round. If anybody is still in the fight the holds
            # are timed and the next round will find them; if the order is empty of
            # the living there is nothing to wait for.
            if not any(self.conscious(r) for r, _ in self.initiative):
                break
            # Park on the last slot so the next pass wraps at its first step, which is
            # what rolls the round over and ticks the holds down. Without this the
            # retry re-walks the same round for ever and expires nothing — the first
            # fix for this returned None just as silently, and only a probe caught it.
            self.turn = len(self.initiative) - 1
        return None                      # nobody left standing

    # How many rounds one call may skip looking for somebody able to act. A single
    # pass returned None the moment every combatant was stunned at once — and the
    # caller reads None as "the fight is over", so a mutual stun ended the encounter
    # with two live enemies upright, paid no XP and printed nothing at all. Holds are
    # timed; ticking through them finds the turn again. Twenty rounds is longer than
    # any hold the game ships.
    MAX_SKIPPED_ROUNDS = 20

    def _next_able(self) -> str | None:
        """One pass down the initiative order from wherever the turn is."""
        # The holder left and their successor sits in this slot (`leave_order`): the pass
        # starts ON it. Step 0 cannot roll the round over — `reached` is `turn` itself —
        # which is right: the successor's turn belongs to the round already running.
        first = 0 if self.turn_is_next else 1
        self.turn_is_next = False
        for step in range(first, len(self.initiative) + first):
            reached = self.turn + step
            nxt = reached % len(self.initiative)
            # Passing the top of the order is the top of a new round — but not the
            # first turn of the fight, which starts from `turn == -1` and is round one
            # already. This used to read `nxt <= self.turn`, which happens to fire once
            # per cycle only because the scan returned early; with nobody able to act
            # it charged the round several times over in a single pass.
            if reached > 0 and nxt == 0:
                self.round += 1
                # Attacks of opportunity refill at the top of the round, not on your own
                # turn: the allowance is what you may do while other people act.
                self.reacted = {}
                # The store: a round is a unit of time, and time passes for the merchant
                # in the next room too. Nothing in any tradition freezes an object because
                # the player is not looking at it, and the survival module has already
                # paid for the version of this that did ("the clock moved and the body
                # did not know"). The hazards below stay scene-local — a cloud in this
                # room does not burn a man in that one.
                for a in self.people.values():
                    # Every one of these returned a list of what it ended, and every
                    # one of those lists was dropped on the floor — so in a fight, a
                    # buff running out, a cooldown coming back and a compulsion
                    # releasing all happened in total silence. Law 3 says the narrator
                    # may only dress what the engine recorded, so an expiry nobody
                    # records is an expiry the player can never be told about.
                    self.hazards.extend(
                        {"kind": "effect_ended", "ref": a.ref, "what": name}
                        for name in a.tick_effects(1))
                    self.hazards.extend(
                        {"kind": "pool_ready", "ref": a.ref, "pool": pid}
                        for pid in a.tick_pools(1))
                    self.hazards.extend(self._drain_periodic(a))
                # Appended, for the reason the next comment gives about `hazards`, and
                # it was left as an assignment when that one was fixed. One call now
                # skips up to twenty rounds looking for somebody able to act, so only
                # the last round's dying survived: measured, a thug bled to death during
                # a skipped round and `scene.bleeding` came back empty, so the player
                # was never told he had stopped moving.
                self.bleeding.extend(r for r in (
                    a.bleed_out(self._dice) for a in self.people.values()
                ) if r)
                # After the dying, because a hazard that finishes somebody should find
                # them where the round left them rather than where it started.
                #
                # Appended rather than assigned, and that is not tidiness. One call to
                # `advance_turn` rolls the round over as many times as it takes to find
                # somebody still standing, so a cloud that drops the last conscious NPC
                # ticks again on the way out — and an assignment here loses the tick that
                # did the dropping. Measured: an incendiary cloud took a thug from 13 hit
                # points to -6 and `scene.hazards` came back empty, so nothing was
                # narrated and the fight simply ended with no reason given.
                self.hazards.extend(self.tick_standing(1))
            ref = self.initiative[nxt][0]
            # The one caller that wants "can act now" rather than "still in the fight":
            # a stunned combatant stays in the initiative order and on the panel, and
            # loses this turn. Asked separately since `conscious` stopped conflating
            # the two.
            if self.conscious(ref) and self.actors[ref].can_act():
                self.turn = nxt
                self.acted.add(ref)
                return ref
        return None                      # nobody able this pass

    def _drain_periodic(self, actor: "Actor") -> list[dict]:
        """Run each standing effect's per-round work — today, pool upkeep.

        Blood Rage burns one rage round per round it holds; when the pool runs dry
        the stance ends and takes its temporary hit points with it, because they were
        the rage's and not the character's. Declared on the effect (`periodic`), so a
        homebrew stance with an upkeep gets the same clock without a line here.
        """
        out: list[dict] = []
        for e in list(actor.effects):
            for p in e.periodic:
                pool = p.get("spend_pool")
                if not pool:
                    continue
                paid = actor.spend_pool(str(pool), int(p.get("amount", 1) or 1))
                if not paid.get("ok") and p.get("or_ends") and e in actor.effects:
                    # Through the applicator, and out loud. This removed the record
                    # directly and cleared the pool beside it, so a stance ending
                    # because its upkeep ran dry was two silent mutations — the exact
                    # shape law 2 forbids, in the function that enforces upkeep.
                    actor.remove_effects(name=e.name or e.key, source=e.source)
                    if e.source:
                        actor.clear_temp_hp(source=e.source)
                    out.append({"kind": "upkeep_failed", "ref": actor.ref,
                                "what": e.name or e.key, "pool": str(pool)})
        return out

    # --- things standing in the scene ------------------------------------------------

    def place(self, made: "Manifestation") -> "Manifestation":
        """Put a manifestation into the scene and write its squares onto the map.

        Only the squares it actually *changes* are recorded, so lifting a fog cloud off a
        stone pillar does not take the pillar's opacity with it. On a scene with no grid
        the thing still exists and still expires — it simply has nowhere to put squares,
        which is honest rather than a refusal: most scenes have no map.
        """
        # One past the highest id anything still names — a live manifestation or a
        # ward's `manifest_id`. It was `len + 1`, and measured 2026-09-25: two fogs, the
        # first lifted, and the next placed was `m2` beside the `m2` still standing —
        # wards find their area by that id, so a ward could fire on the wrong one.
        made.id = made.id or f"m{self._next_manifest_number()}"
        if self.grid is not None and made.terrain in ("obscuring", "blocked", "difficult"):
            already = getattr(self.grid, made.terrain)
            # The GROUND it covers, not the cells it fills. An area knows its own height
            # — a fog cloud is a sphere, and that is what decides who is standing in it —
            # but the grid's terrain sets are flat, because sight and movement in this
            # engine are: a square is opaque or it is not, at every level.
            #
            # Writing cells in here was silent and total: `line_of_sight` compares
            # two-element squares, no three-element cell ever matched one, and sight went
            # straight through a bank of fog that was drawn on the map. The manifest keeps
            # the cells; the map gets the footprint.
            footprint = {(s[0], s[1]) for s in made.squares}
            made.added = [s for s in sorted(footprint)
                          if self.grid.inside(s) and s not in already]
            already.update(made.added)
        self.manifests.append(made)
        return made

    def _next_manifest_number(self) -> int:
        taken = [m.id for m in self.manifests] + [w.manifest_id for w in self.wards]
        numbers = [int(i[1:]) for i in taken if re.fullmatch(r"m\d+", str(i or ""))]
        return max(numbers, default=0) + 1

    def lift(self, made: "Manifestation") -> None:
        """Take one back off the map. Squares another live manifestation also claims stay."""
        self.manifests = [m for m in self.manifests if m is not made]
        if self.grid is None or not made.added:
            return
        still = set()
        for other in self.manifests:
            if other.terrain == made.terrain:
                still.update(other.added)
        getattr(self.grid, made.terrain).difference_update(set(made.added) - still)

    def standing_on(self, ref: str) -> list["Manifestation"]:
        """Every manifestation whose squares this creature is in."""
        from .grid import footprint

        anchor = self.positions.get(ref)
        actor = self.actors.get(ref)
        if anchor is None or actor is None:
            return []
        here = footprint(anchor, actor.size)
        return [m for m in self.manifests if m.covers(here)]

    # Ten rounds to the minute, written once. Six sites multiplied their own way to get
    # here — `hours * 600`, `worked * MINUTES_PER_HOUR`, `days * 24 * 60`, `rounds // 10`
    # — and four of them then ticked nothing at all.
    ROUNDS_PER_MINUTE = 10

    def advance(self, minutes: int = 0, rounds: int | None = None,
                charge_body: bool = True) -> dict:
        """Move the world clock, and expire what that much time expires.

        The one door. Six places moved `clock_minutes` and two of them expired anything:
        a forty-eight-hour forage, a twelve-hour crafting session, an hour spent waking
        up and a resurrection costing up to twenty-seven days all left every timed effect
        in the scene exactly where it was. This is the survival module's own lesson —
        "the clock moved and the body did not know" — with effects in place of hunger.

        EXPIRY ONLY. `advance_turn` keeps the per-round *firing*: an eight-hour rest is
        4,800 rounds, and calling the ward hazards or the pool upkeep that many times
        would empty every pool and roll thousands of saves, while calling them once would
        under-resolve. Time passing ends things; it does not make them happen again.

        Returns what ended, so the caller can say so — four of the six threw that away.
        """
        minutes = max(0, int(minutes))
        # Rounds may be stated directly, because a round is finer than a minute and
        # the conversion floors. `advance_time` may be asked for five rounds, and
        # deriving rounds from `minutes` alone made that five-round advance tick
        # nothing at all (5 // 10 == 0) while fifteen rounds ticked ten. Found by an
        # adversarial review of this very change, in a probe it wrote to dump the
        # numbers — the suite was green through all of it.
        rounds = (max(0, int(rounds)) if rounds is not None
                  else minutes * self.ROUNDS_PER_MINUTE)
        if not minutes and not rounds:
            return {"minutes": 0, "rounds": 0, "ended": []}
        # Hours crossed on the world clock, not minutes // 60: the clock mostly moves
        # in ten-minute steps, and flooring each step would never heal anybody.
        hours = (int(self.clock_minutes) + minutes) // 60 - int(self.clock_minutes) // 60
        self.clock_minutes += minutes
        ended: list[str] = []
        # Everyone the campaign holds: an eight-hour rest expires the buff on the
        # merchant in the next room and advances his hunger, exactly as it does here.
        for a in self.people.values():
            # The body keeps its own clock, and the door has to open that one too.
            # `survival.pass_hours` is reached from exactly one place in the app, so
            # four of the six routed sites moved the world and left hunger, thirst and
            # wakefulness where they were: three days of `advance_time` and the needs
            # panel still reported full grace. That is the failure survival.py is named
            # after, arriving by a different route.
            #
            # The COUNTERS move here and the CHECKS do not. pass_hours rolls dice, can
            # knock a character unconscious and returns fewer hours than it was asked
            # for, none of which can live inside a function whose caller has already
            # decided how far the clock goes. Counters that are right beat counters
            # that are wrong, and the panel shows the danger either way.
            if charge_body and minutes:
                a.awake_minutes += minutes
                a.fed_minutes += minutes
                a.watered_minutes += minutes
            ended.extend(f"{a.name}: {name}" for name in a.tick_effects(rounds))
            ended.extend(f"{a.name}: {pid} is ready"
                         for pid in a.tick_pools(rounds))
            # A grudge the player earned by provoking them comes back with time, faster
            # the longer nothing new happens (rules/provocation.py, `recover`).
            if minutes and not a.is_pc:
                from . import provocation as _provocation

                _provocation.recover(a, self.clock_minutes)
            # "You heal nonlethal damage at the rate of 1 hit point per hour per
            # character level" (Core Rulebook p.191). Only a night's `rest` healed it
            # before, which was harmless while almost nothing dealt it; once punches
            # and saps did (2026-09-27), a player knocked out cold woke an hour later
            # still carrying more than their hit points, and the next blow's
            # hit-point check put them straight back down. Deterministic, so it sits
            # with the counters above rather than with the checks.
            if hours and a.nonlethal:
                out_cold = a.has_state("state.down.unconscious")
                a.heal_nonlethal(hours * max(1, int(getattr(a, "level", 1) or 1)))
                a.apply_nonlethal_state()
                if out_cold and not a.has_state("state.down.unconscious"):
                    ended.append(f"{a.name} comes round")
            # The breath they are holding, for anybody under the surface who does not
            # breathe water. A counter, like hunger above it and for the same reason:
            # the Constitution check that follows it rolls dice and belongs to the
            # engine (`Engine.breathe`). Surfacing resets it, because breathing is what
            # holding your breath stops being.
            if _drowning_ground(a):
                a.held_breath_rounds += rounds
            elif a.held_breath_rounds or a.drown_failures:
                a.held_breath_rounds = 0
                a.drown_failures = 0
        # The scene's own standing things expire on the same clock. `tick_standing` fires
        # `each_round` wards as well, which is exactly the work this must not repeat — so
        # it is called once, for expiry, and the firing stays where the rounds are real.
        for record in self.tick_standing(rounds, fire=False):
            what = record.get("what") or record.get("kind")
            if what:
                ended.append(str(what))
        return {"minutes": minutes, "rounds": rounds, "ended": ended}

    def tick_standing(self, rounds: int = 1, fire: bool = True) -> list[dict]:
        """One round of everything the scene is holding: hazards fire, then clocks run.

        On the Scene rather than on the Engine, and that is the same call `bleed_out`
        made: the round tick belongs to whatever owns the round, and `advance_turn` is
        reached from the NPC loop and from tests without an Engine anywhere in sight.
        The cost is that damage here goes through `Actor.take_damage` rather than
        `Engine._apply_damage`, so resistance, DR and temporary hit points all apply and
        interception does not — which is right anyway: a guard steps in front of a blow
        aimed at somebody, not in front of the ground they are both standing on.
        """
        out: list[dict] = []
        # `fire` is False when time is being SKIPPED rather than played: an eight-hour
        # rest is 4,800 rounds and firing every each_round ward that many times would
        # roll thousands of saves, while firing once would understate a cloud stood in
        # for a minute. Expiry still runs — a fog cloud does not outlive the night.
        for ward in list(self.wards) if fire else ():
            if ward.trigger == "each_round":
                out.extend(self._fire(ward))
        out.extend(self.tick_effects(rounds))
        return out

    def tick_effects(self, rounds: int = 1) -> list[dict]:
        """The scene's one ticker, and the one door out for anything standing in it.

        Wards and manifestations had an expiry loop each, three lines apart, and the two
        disagreed about everything: a ward was removed in silence while a manifestation
        emitted `manifest_ended`, and only the manifestation gave its squares back. That
        is the shape law 2 forbids — the Actor learned it in stage 2, when conditions,
        buffs and temporary hit points each had their own loop and a fourth mechanism
        added without a fourth loop simply never wore off.

        One loop, and one `_end_standing` that every removal goes through, so a thing
        cannot leave the scene without both its teardown and its tell.
        """
        out: list[dict] = []
        for holder in list(self.wards) + list(self.manifests):
            # A ward tied to a condition goes when the condition does, whatever its
            # clock says — "cure the bleeding and the bleed ward evaporates".
            stops = getattr(holder, "stops_with", "")
            if stops and getattr(holder, "owner", ""):
                # The store: a ward on somebody who has walked into the next room is
                # not a ward on somebody who has been cured.
                who = self.people.get(holder.owner)
                if who is None or not who.has_condition(stops):
                    out.append(self._end_standing(holder))
                    continue
            if holder.rounds_left is None:
                continue
            holder.rounds_left -= rounds
            if holder.rounds_left <= 0:
                out.append(self._end_standing(holder))
        return out

    def _end_standing(self, holder) -> dict:
        """Take one standing thing out of the scene, with its teardown and its tell.

        The teardown is why this is a door rather than two `remove` calls. A
        manifestation's squares are a MUTATION of the grid that only `lift` undoes, and
        `ActiveEffect` has no teardown hook — so an expiry routed through a generic
        ticker would drop the record and leave a fog cloud's squares in
        `grid.obscuring` for the rest of the session, with no fog in the room to
        explain why it was blind.
        """
        if isinstance(holder, Manifestation):
            self.lift(holder)
            return {"kind": "manifest_ended", "what": holder.what, "id": holder.id}
        if holder in self.wards:
            self.wards.remove(holder)
        return {"kind": "ward_ended", "ref": holder.owner or "",
                "source": holder.source, "what": holder.source}

    def _fire(self, ward: "Ward", struck_by: str = "") -> list[dict]:
        """Resolve one ward against whoever it aims at, and say what it did."""
        out: list[dict] = []
        for victim in self._aimed_at(ward, struck_by):
            out.extend(self._resolve_on(victim, ward, ward.spec or {},
                                        ward.save, ward.save_effect))
        return out

    def _resolve_on(self, victim: Actor, ward: "Ward", spec: dict,
                    save: str, save_effect: str) -> list[dict]:
        """One effect, on one creature, with its save rolled if it has one.

        Four types are resolved — damage, healing, a condition, ability damage — plus a
        save gate, which is unwrapped rather than treated as a fifth thing: incendiary
        cloud is "6d6 fire, Reflex half, **every round**", and without this the gate came
        back as "something is due, GM" once a round for as long as the cloud stood.

        Anything else is reported as due rather than silently skipped. A ward that
        quietly does nothing is precisely the failure a `trigger` field was added to end.
        """
        kind = str(spec.get("type", ""))
        if self._dice is None:
            return [{"kind": "ward_due", "ref": victim.ref, "source": ward.source,
                     "line": effectspec.render(spec)}]

        if kind == "save_gate":
            gate_save = str(spec.get("target") or save or "")
            branch = spec.get("on_failure") or []
            saved = False
            out: list[dict] = []
            if gate_save:
                roll = self._dice.d20(
                    victim.save_modifiers(gate_save),
                    label=f"{gate_save} save against {ward.source}", visibility="hidden")
                saved = d20_succeeds(roll, ward.dc)
                if saved:
                    branch = spec.get("on_success") or []
                    if not branch:
                        return [{"kind": "ward_saved", "ref": victim.ref,
                                 "source": ward.source, "roll": roll.total,
                                 "dc": ward.dc,
                                 "natural": natural_said(roll, ward.dc)}]
            for inner in branch:
                out.extend(self._resolve_on(victim, ward, inner, "", ""))
            return out

        saved = False
        if save:
            roll = self._dice.d20(victim.save_modifiers(save),
                                  label=f"{save} save against {ward.source}",
                                  visibility="hidden")
            saved = d20_succeeds(roll, ward.dc)
            if saved and save_effect in ("negates", ""):
                return [{"kind": "ward_saved", "ref": victim.ref, "source": ward.source,
                         "roll": roll.total, "dc": ward.dc,
                         "natural": natural_said(roll, ward.dc)}]

        out = []
        if kind in ("damage", "heal"):
            rolled = max(0, self._dice.roll(str(spec.get("dice") or "0"),
                                            label=ward.source,
                                            visibility="hidden").total)
            if saved and save_effect == "half":
                rolled //= 2
            if kind == "heal":
                return [{"kind": "heal", "ref": victim.ref,
                         "amount": victim.heal(rolled), "source": ward.source,
                         "origin": f"ward:{ward.source}"}]
            d = victim.take_damage(rolled, str(spec.get("damage_type") or "untyped"),
                                   (), str(spec.get("lethality") or "lethal"))
            out.append({"kind": "damage", "ref": victim.ref, "amount": d["taken"],
                        "type": d["type"], "rolled": rolled, "saved": saved,
                        "hp_after": victim.hp, "hp_max": victim.hp_max,
                        "source": ward.source, "origin": f"ward:{ward.source}"})
            for c in victim.apply_hp_state():
                out.append({"kind": "condition", "ref": victim.ref, "condition": c,
                            "from": ward.source})
        elif kind == "apply_condition":
            victim.add_condition(str(spec.get("target") or ""), source=ward.source)
            out.append({"kind": "condition", "ref": victim.ref,
                        "condition": str(spec.get("target") or ""),
                        "from": ward.source})
        elif kind == "ability_damage":
            amount = max(0, self._dice.roll(str(spec.get("dice") or "0"),
                                            label=ward.source,
                                            visibility="hidden").total)
            res = victim.damage_ability(str(spec.get("target") or "str")[:3], amount)
            # `**res` first, deliberately: `damage_ability` returns its own `kind`
            # ("damage" or "drain") and spreading it last overwrites the one that says
            # what sort of effect this is — a hit-point reader would then take an ability
            # loss for a wound.
            out.append({**res, "kind": "ability_damage", "ref": victim.ref,
                        "source": ward.source})
        else:
            out.append({"kind": "ward_due", "ref": victim.ref, "source": ward.source,
                        "line": effectspec.render(spec)})
        return out

    def _aimed_at(self, ward: "Ward", struck_by: str = "") -> list[Actor]:
        """Which creatures this ward lands on. The recipient field, resolved.

        This is the whole point of the field. Every spec used to land on "the target", so
        the ten-odd spells that punish an *attacker* could not be written without the
        engine burning the wrong creature — measured: thorn body, converted mechanically,
        set fire to the caster it was protecting.
        """
        who = ward.recipient or "target"
        if who == "attacker":
            found = self.actors.get(struck_by)
            return [found] if found and found.hp > 0 else []
        if who == "caster":
            found = self.actors.get(ward.caster)
            return [found] if found else []
        if who == "area":
            made = next((m for m in self.manifests if m.id == ward.manifest_id), None)
            if made is None:
                return []
            return [a for ref, a in self.actors.items()
                    if a.hp > 0 and made in self.standing_on(ref)]
        found = self.actors.get(ward.owner)
        return [found] if found else []

    def sides_standing(self) -> int:
        """How many of the recorded sides still have someone up."""
        return sum(
            1 for refs in self.sides.values()
            if any(self.conscious(r) for r in refs)
        )

    def end_encounter(self) -> None:
        # Whoever swung because they were provoked settles it now — cathartic or
        # embittered, and cooled either way (rules/provocation.py). Here because a fight
        # ends through eight different callers and this is the one door they all use.
        from . import provocation as _provocation

        for note in _provocation.settle_outbursts(
                [a for a in self.people.values() if not a.is_pc], self.clock_minutes):
            self.log.append({"op": "outburst-settled", "tell": "", "note": note})
        self.initiative = []
        self.turn = -1
        self.round = 0
        self.acted = set()
        self.attacked = set()
        # The next fight starts at round one again, and a walk from this one's round one
        # would read as already spent.
        self.move_spent = {}
        self.sides = {}
        # The battlefield does NOT go with the fight any more (item 28, 2026-09-19): the
        # ground belongs to the place, the party is standing on it before and after, and
        # "a map should be displayed at all times" was the request. What goes is the
        # tactical layer above it — initiative, sides, and the things a fight conjured.
        # The grid is cleared where it is replaced instead, when the party arrives
        # somewhere else (`Engine.place_party`).
        # The things a fight conjured go with it, and each is LIFTED off the ground it
        # was drawn on. This used to be `self.manifests = []`, written when the grid went
        # with the fight too; since item 28 the grid stays, and measured 2026-09-25 the
        # cleared list left its squares in `grid.obscuring` with nothing claiming them —
        # the room stayed blind and walled until the party walked out.
        #
        # Except a fire in the world (I3, 2026-09-29; docs/design-e-magic.md §6: "a fire
        # lit outside a fight must outlive that"). Brush a spell set alight is not a thing
        # the fight conjured; it burns its 2d4 × 10 minutes and expires on the clock like
        # anything timed. Known by its ward's `hazard` (`Engine._ignite`), not by its name.
        world = {w.manifest_id for w in self.wards
                 if (w.spec or {}).get("hazard") and w.rounds_left is not None
                 and (w.spec or {}).get("at", "") == (self.at or "")}
        for made in list(self.manifests):
            if made.id not in world:
                self.lift(made)
        self.manifests = [m for m in self.manifests if m.id in world]
        self.wards = [w for w in self.wards if w.manifest_id in world
                      and (w.spec or {}).get("hazard")]
        self.hazards = []

    # --- the props ledger: one applicator for where a thing is -----------------------

    def place_prop(self, name: str, *, owner: str = "", from_: str = "",
                   state: str = "intact", at: str | None = None, turn: int = 0,
                   square=None) -> dict:
        """A thing comes to lie somewhere: dropped, thrown, left in fragments. The
        record already held for it (by name, in the hands of somebody here or lying
        here) moves; otherwise one is made. Returns the record.

        `square` is the map square it lies in, when a map is laid and the caller knows
        it — a disarmed weapon lands "at the feet of the disarmed creature" (Greater
        Disarm's Normal line), so in its square. Without one the thing is at this spot
        and nowhere more exact, and a reach question about it is unmeasurable."""
        rec = self.prop_named(name)
        if rec is None:
            rec = {"name": " ".join(str(name).split()), "owner": owner, "from_": from_,
                   "state": state, "turn": int(turn)}
            self.props.append(rec)
        rec.pop("held_by", None)
        rec["at"] = str(at if at is not None else self.at)
        # Replaced, never kept: a square from where it lay LAST time would put a thrown
        # sap back at the feet it was knocked from.
        rec.pop("square", None)
        if square is not None and self.has_grid:
            rec["square"] = [int(v) for v in tuple(square)[:2]]
        if owner:
            rec["owner"] = owner
        if from_:
            rec["from_"] = from_
        if state:
            rec["state"] = state
        return rec

    def hold_prop(self, name: str, ref: str, *, owner: str = "", from_: str = "",
                  state: str = "", turn: int = 0) -> dict:
        """A thing goes into somebody's hands, keeping its owner and its provenance:
        picking up a fragment of the challenger's club does not make it yours, and does
        not make it a table."""
        rec = self.prop_named(name)
        if rec is None:
            rec = {"name": " ".join(str(name).split()), "owner": owner or ref,
                   "from_": from_, "state": state or "intact", "turn": int(turn)}
            self.props.append(rec)
        rec.pop("at", None)
        rec.pop("square", None)
        rec["held_by"] = ref
        if owner:
            rec["owner"] = owner
        if from_:
            rec["from_"] = from_
        if state:
            rec["state"] = state
        return rec

    def prop_named(self, name: str) -> dict | None:
        """The record for a thing by name, here or in the hands of somebody here."""
        key = " ".join(str(name or "").split()).lower()
        if not key:
            return None
        for rec in self.props:
            if str(rec.get("name", "")).lower() != key:
                continue
            if rec.get("at") == self.at or rec.get("held_by") in self.actors:
                return rec
        return None

    def out_of_hand(self, ref: str, item: str) -> dict | None:
        """The record of `ref`'s own `item` when it is somewhere other than their
        hands — knocked to the ground, or in a thief's — or None. Whole things only:
        fragments are not the weapon any more."""
        key = " ".join(str(item or "").split()).lower()
        for rec in self.props:
            if (rec.get("owner") == ref and str(rec.get("from_", "")).lower() == key
                    and rec.get("state") not in ("fragments", "destroyed")
                    and rec.get("held_by") != ref):
                return rec
        return None

    def within_reach(self, ref: str, rec: dict) -> int | None:
        """How far past `ref`'s reach a lying thing is, in feet: 0 when it can be
        taken from where they stand, None when it cannot be measured (no map, nobody
        placed on it, or a record with no square).

        Natural reach, not the weapon's: a glaive lets you strike ten feet off and does
        not let you pick a sap up there. Measured from the edge of the creature's space,
        as every reach in `grid` is, so a Large ogre's own squares count."""
        square = rec.get("square")
        anchor = self.positions.get(ref)
        actor = self.actors.get(ref)
        if not self.has_grid or square is None or anchor is None or actor is None:
            return None
        gap = gridmod.distance_between(tuple(anchor), actor.size,
                                       tuple(square), "medium")
        return max(0, gap - gridmod.natural_reach(actor.size))

    def props_here(self) -> list[dict]:
        """What lies at the party's spot, unheld."""
        return [r for r in self.props if r.get("at") == self.at and not r.get("held_by")]

    def prop_on_the_ground(self, asked: str) -> dict | None:
        """The thing lying here that a player's phrase means, or None.

        By name first; then by a shared word with what it is, what it was, or what it
        is made of — "a chunk of wood" is the fragments of a wooden club lying at the
        player's feet, and picking it up must find THAT record rather than conjure a
        second, provenance-less piece of wood from nowhere."""
        words = {w for w in re.findall(r"[a-z]+", str(asked or "").lower())
                 if len(w) >= 3 and w not in ("the", "and", "chunk", "piece", "bit",
                                              "some", "shard", "length", "lump")}
        if not words:
            return None
        here = self.props_here()
        for rec in here:
            if str(rec.get("name", "")).lower() == " ".join(str(asked).split()).lower():
                return rec
        for rec in here:
            about = " ".join(str(rec.get(k, "")) for k in ("name", "from_", "material")).lower()
            if words & set(re.findall(r"[a-z]+", about)):
                return rec
        return None

    def _unseat(self, ref: str) -> None:
        """Take one creature out of every TACTICAL structure that names it.

        The structures are the point. A first version that only deleted from the roster
        left the ref in the initiative order, the sides, the zones and the reaction
        ledger — places for a ghost to keep acting from. The 2026-08-22 playtest
        produced exactly that ghost by never removing anybody at all: a gatekeeper
        wounded in the city travelled inside the scene to the forest and took an NPC
        turn after every player turn for the rest of the session.

        Tactical only: a zone, a square, an initiative slot, a side, a spent reaction, a
        stated spawn distance, a turn spent lying on this floor, an attack made in this
        fight. Every one of those is meaningless in another room. Guards, wards, pools
        and manifests are NOT here — see `move` and `remove` for which of them each
        door touches, and why.
        """
        # The initiative order shrinks, and `turn` must go on pointing at the same
        # creature — an index into a list that just changed length is how a removal
        # hands somebody else's turn to the wrong side of the fight. `leave_order` is
        # the one door, and it also keeps the holder's successor next when the holder
        # is the one leaving.
        self.leave_order(ref)

        self.zones.pop(ref, None)
        self.positions.pop(ref, None)
        self.acted.discard(ref)
        self.move_spent.pop(ref, None)
        self.spawn_feet.pop(ref, None)
        # Leaked by three of the four old depart doors and persisted, so a stale age was
        # waiting for whoever wore the ref next; with refs never reused it is merely
        # untidy, and it is cleaned anyway.
        self.fallen.pop(ref, None)
        self.reacted = {k: v for k, v in self.reacted.items()
                        if not k.startswith(f"{ref}:")}
        self.attacked = {k for k in self.attacked
                         if ref not in k.split(">", 1)}
        self.sides = {side: [r for r in refs if r != ref]
                      for side, refs in self.sides.items()}

    def move(self, ref: str, place_id: str) -> Actor | None:
        """Put one creature in a place. The OTHER writer of `Actor.at`, and the only
        one that changes it.

        Inform's `PlayerTo` is the model: "the player object can only be moved by this
        routine: this allows us to maintain the invariant" (WorldModelKit §13). Moving
        the PC moves the party — `scene.at` follows, and the cast ledger of prose-people
        the narrator introduced *here* is emptied, because that is what walking out of
        a room does to the people in it.

        Tactical state is dropped (`_unseat`). Guards are not: a guard is a relationship
        between two creatures, and whether it survives depends on where BOTH of them
        end up, which only the caller knows once every move of a travel is done — see
        `settle_relations`. Wards with an owner are the teeth of something on that
        body and travel with it; area wards, pools and manifests are things on the
        floor of a room and stay on it.

        Mid-encounter the PC is refused: travel ends the fight first (`_op_travel`
        settles the XP, then `end_encounter`, then moves), and every other caller has
        no business moving the party out of an initiative order.

        Somebody moved into the party's place on a mapped scene is given a square, at
        their zone — the arrival door's rule, which `move` used to undo (item 14).
        """
        actor = self.people.get(ref)
        if actor is None:
            return None
        place_id = str(place_id or "").strip()
        if not place_id:
            raise ValueError("move: a place id, never nothing — the party is always somewhere")
        if actor.is_pc and self.in_encounter:
            raise ValueError("move: the player does not leave an initiative order; "
                             "end the encounter first")
        self._unseat(ref)
        was = actor.at
        actor.at = place_id
        self.zones[ref] = "near"
        if actor.is_pc and was != place_id:
            self.arrived = self.clock_minutes
            self.moves += 1
        elif not actor.is_pc and ref not in self.came_along:
            self.came_along.append(ref)
        if actor.is_pc:
            self.at = place_id
            self.cast = []
            # What was agreed here is a fact of this room; the next room starts clean.
            self.agreements = []
        elif place_id == self.at and self.grid is not None:
            # Moved INTO the party's room: they stand somewhere on its map from the
            # moment they come in, as an arrival through `arrive` does. Item 14 of the
            # 2026-09-28 playtest: a scheme brought Drenn in with `add` (which placed
            # him) and then `move`d him to the market the party was standing in, and
            # `_unseat` above had taken the square away with nothing to give one back —
            # he was on the WHO IS HERE list and not on the board. The ruling of the
            # same day: everyone in a scene has a square from arrival. The PC is not
            # placed here: moving the party is a new room, and `place_party` lays it.
            self.place_by_zone([ref])
        self._recognise(actor)
        return actor

    def settle_relations(self) -> list[str]:
        """Drop every guard whose two ends are no longer in one place.

        After ALL the moves of a travel, not inside each one: the PC moves first and the
        escort second, and a guard between them would be cut in the gap. Returns the
        guardians' refs, so a caller can say the arrangement lapsed.
        """
        lapsed: list[str] = []
        kept = []
        for g in self.guards:
            a, b = self.people.get(g.guardian), self.people.get(g.protects)
            if a is None or b is None or a.at != b.at:
                lapsed.append(g.guardian)
            else:
                kept.append(g)
        self.guards = kept
        return lapsed

    def remove(self, ref: str) -> Actor | None:
        """Take one creature out of the campaign for good. The ONE destroyer.

        Inform keeps `remove` (out of the tree, still in existence) apart from
        destruction; this app has no use for a creature that exists nowhere, so this is
        the destroyer and `move` is the only other spatial write. Everything relational
        goes with them: guards at either end, wards they own or cast, and — outside every
        scene table — the compulsions they were pulling on other people, which live on
        the *targets'* effect lists and would otherwise charge a −4 forever against
        somebody who no longer exists.

        The PC is refused: a scene without its player is not a scene, it is a bug.
        """
        actor = self.people.get(ref)
        if actor is None or actor.is_pc:
            return None
        self._unseat(ref)
        self.guards = [g for g in self.guards if ref not in (g.guardian, g.protects)]
        # A ward naming a creature who no longer exists is one more place for a ghost
        # to keep acting from, and this one would fire every round.
        self.wards = [w for w in self.wards if ref not in (w.owner, w.caster)]
        from . import compulsion as compulsion_mod

        for other in self.people.values():
            if other.ref != ref:
                compulsion_mod.remove(other, by=ref)
        for e in self.cast:
            if e.get("ref") == ref:
                e.pop("ref", None)
        del self.people[ref]
        return actor

    # The name every earlier stage knew the destroyer by. Kept so the four callers and
    # the tests that pin its contract (every trace gone, the turn stays on the same
    # creature, the PC refused) go on reading as written.
    depart = remove


# --- Results -----------------------------------------------------------------------

@dataclass
class Outcome:
    intent_id: str
    op: str
    status: str = "resolved"
    rolls: list[Roll] = field(default_factory=list)
    dc: dict | None = None
    verdict: str | None = None
    margin: int | None = None
    effects: list[dict] = field(default_factory=list)
    tell: str = ""
    because: str = ""
    # A refusal's code, the sentence a player reads, and what would fix it — the same
    # three an `IntentError` carries (rules/intents.py, `PLAYER_FIXABLE`), so a refusal
    # at resolution time and one at validation render into one shape
    # (docs/fix-interfaces.md §2.6). Empty on everything that is not a coded refusal.
    code: str = ""
    for_a_person: str = ""
    fix: dict | None = None

    def as_dict(self) -> dict:
        d = {
            "intent_id": self.intent_id,
            "op": self.op,
            "status": self.status,
            "rolls": [r.as_dict() for r in self.rolls],
            "dc": self.dc,
            "verdict": self.verdict,
            "margin": self.margin,
            "effects": self.effects,
            "tell": self.tell,
            "because": self.because,
        }
        # Emitted only when set: every turn log, pending outcome and replay written
        # before these existed reads back as the same ten keys, and an outcome that is
        # not a coded refusal still is those ten keys.
        if self.code:
            d["code"] = self.code
        if self.for_a_person:
            d["for_a_person"] = self.for_a_person
        if self.fix is not None:
            d["fix"] = self.fix
        return d

    def player_visible(self) -> dict:
        """The same outcome with hidden rolls stripped of their numbers.

        The GM never receives a number it might leak. A hidden roll reaches it only as a
        tell.
        """
        d = self.as_dict()
        d["rolls"] = [r for r in d["rolls"] if r["visibility"] == "player"]
        return d


@dataclass
class Resolution:
    outcomes: list[Outcome] = field(default_factory=list)
    awaiting: dict | None = None

    @property
    def status(self) -> str:
        return "awaiting_player_roll" if self.awaiting else "complete"

    def tells(self) -> list[str]:
        return [o.tell for o in self.outcomes if o.tell]

    def as_dict(self) -> dict:
        return {
            "status": self.status,
            "outcomes": [o.as_dict() for o in self.outcomes],
            "awaiting": self.awaiting,
        }


# Appended to every unknown-ref rejection. Measured in play: told that two bravos step
# out of the dark, the GM tried to name them, was refused, and never thought to create
# them — it spent five attempts guessing at refs that could not exist. A rejection that
# names the way out turns a lost turn into a repair.
# Four hand-written templates were the whole vocabulary offered here, while 7,133 stat
# blocks sat loaded and reachable (item 28, 2026-09-19). The hint no longer lists them:
# `rules/roster.py` tells the brief who THIS place would hold, with the template beside
# each, and the four are named here only as the floor for a scene with no place in it.
_SPAWN_HINT = (
    ' If a PERSON new to the scene should be in it, bring them in first with '
    '{"op": "introduce", "params": {"who": "old ferryman mending a net"}} and call them '
    'new1 after it. A creature or a foe arriving to fight is '
    '{"op": "spawn", "params": {"template": "thug", "count": 2}}, using the refs it '
    "returns; take the template from WHO THIS PLACE WOULD HOLD above where there is one — "
    "guildhand, watchman, thug and guard dog always exist. A thing (a weapon, a table, a "
    "door) is never introduced or spawned: a blow at a weapon is an attack on the person "
    "holding it."
)

# A spawn named after an object. Measured 2026-09-18: a thug named "weapon", 13 hp,
# on the initiative list of a saved campaign, killed for 135 XP. Refused at
# validation, with the fix named. The vocabulary is `judgement._A_THING`'s, imported
# lazily: rules must not import gm at module load.
def _spawn_names_a_thing(name) -> bool:
    if not name:
        return False
    try:
        from gm.judgement import names_a_thing
    except Exception:            # pragma: no cover — rules standing alone
        return False
    return names_a_thing(str(name))


class _NeedsPlayerRoll(Exception):
    """Raised inside an op handler to suspend the whole intent list."""

    def __init__(self, prompt: dict, partial: dict | None = None):
        super().__init__("awaiting player roll")
        self.prompt = prompt
        self.partial = partial or {}


@dataclass
class Manifestation:
    """Something a spell put into the scene and left standing there.

    The user called it "temp-spawning" and it is the largest gap the spell readers found
    that was not about numbers: fog clouds, walls, dancing lights, illusions, created
    objects and lingering hazards all *exist somewhere* for a while, and there was no
    shape in the app for a thing that is neither a creature nor a modifier.

    Almost none of this is new machinery. `rules/grid.py` already keeps `obscuring`,
    `blocked` and `difficult` square sets that the map draws and that `Grid.reachable`
    and `Grid.line_of_sight` already route around, so a fog cloud is twenty feet of
    obscuring squares and a wall of stone is blocked squares. `Scene.pools` is the
    precedent for the rest: a positioned thing with a lifetime, ticked with the round and
    cleared with the encounter.

    `added` is the half that is easy to get wrong. The squares this thing *changed* are
    not the squares it covers: a fog cloud rolled across a room with a stone pillar in it
    covers the pillar's square and did not make it opaque. Clearing on expiry removes
    `added` and nothing else, so a dungeon does not lose its own walls when the fog lifts.
    """
    what: str = ""
    terrain: str = "none"                       # obscuring | blocked | difficult | none
    squares: list[tuple[int, int]] = field(default_factory=list)
    added: list[tuple[int, int]] = field(default_factory=list)
    rounds_left: int | None = None              # None = until dispelled
    source: str = ""
    owner: str = ""                             # who put it there
    id: str = ""

    def covers(self, squares) -> bool:
        """Whether this manifestation is in any of these cells.

        A stored entry with only two numbers means the whole column — that is what every
        manifestation written before areas had a third axis meant, and reading it as
        "level 0 only" would quietly let an old fog cloud stop catching the people
        standing in it.
        """
        mine = {tuple(s) for s in self.squares}
        ground = {(s[0], s[1]) for s in mine}
        flat = {(s[0], s[1]) for s in mine if len(s) < 3}
        for s in squares:
            cell = tuple(s)
            here = (cell[0], cell[1])
            if cell in mine:
                return True
            # A missing level on EITHER side means "any level", and both directions
            # happen. A manifestation written before areas had a third axis stores
            # squares; a caller asking "is this creature in the cloud" may hand over a
            # footprint rather than a volume. Answering only one of those was how an
            # incendiary cloud came to stand over somebody and do nothing.
            if here in flat or (len(cell) < 3 and here in ground):
                return True
        return False

    def as_dict(self) -> dict:
        return {"what": self.what, "terrain": self.terrain,
                "squares": [list(s) for s in self.squares],
                "added": [list(s) for s in self.added],
                "rounds_left": self.rounds_left, "source": self.source,
                "owner": self.owner, "id": self.id}

    @classmethod
    def from_dict(cls, d: dict) -> "Manifestation":
        return cls(
            what=d.get("what", ""), terrain=d.get("terrain", "none"),
            squares=[tuple(s) for s in d.get("squares") or []],
            added=[tuple(s) for s in d.get("added") or []],
            rounds_left=d.get("rounds_left"), source=d.get("source", ""),
            owner=d.get("owner", ""), id=d.get("id", ""))


@dataclass
class Ward:
    """A standing arrangement that fires an effect when something happens.

    `Scene.guards` is the precedent and the shape is deliberately the same: a thing the
    *scene* holds rather than either creature, because it is a relationship and a copy on
    each end is two things to keep level. A guard answers "who steps in front of a blow";
    a ward answers "what happens, and to whom, when this occurs".

    It exists because two of the vocabulary's gaps turned out to be the same gap. Damage
    that repeats every round — incendiary cloud, acid fog, wall of fire's heat, black
    tentacles — and damage aimed at whoever strikes you — thorn body, eruptive pustules,
    holy aura, cape of wasps — differ only in which event wakes them up. One structure
    with a `trigger` on it covers both, and covered a third (a hazard paid on walking
    into it) without being asked to.
    """
    owner: str                                  # the creature it sits on, "" for an area
    trigger: str                                # each_round | when_struck | ...
    spec: dict = field(default_factory=dict)    # the effect, with its dice resolved
    recipient: str = "target"
    caster: str = ""
    rounds_left: int | None = None
    source: str = ""
    save: str = ""                              # "" | fort | ref | will
    dc: int = 0
    save_effect: str = ""                       # half | negates
    # A ward that is really a condition's teeth ends when the condition is removed.
    # Without this, curing a bleed would leave the thing that was doing the bleeding.
    stops_with: str = ""
    manifest_id: str = ""                       # the area this ward belongs to

    def as_dict(self) -> dict:
        return {"owner": self.owner, "trigger": self.trigger, "spec": self.spec,
                "recipient": self.recipient, "caster": self.caster,
                "rounds_left": self.rounds_left, "source": self.source,
                "save": self.save, "dc": self.dc, "save_effect": self.save_effect,
                "stops_with": self.stops_with, "manifest_id": self.manifest_id}

    @classmethod
    def from_dict(cls, d: dict) -> "Ward | None":
        """A saved ward, or None for a record too damaged to be one.

        Defensive on purpose, in the shape `rules/guards.py` already uses. `owner` and
        `trigger` have no defaults, so the obvious `cls(**{...})` raises TypeError on a
        truncated record — inside `Campaign.load`, which `_resume` turns into
        UnreadableSave, which means the whole campaign refuses to open because one fog
        cloud was written badly. A hazard that cannot be read is a hazard to drop.
        """
        if not isinstance(d, dict) or not str(d.get("trigger", "")).strip():
            return None
        try:
            return cls(
                owner=str(d.get("owner", "") or ""),
                trigger=str(d["trigger"]),
                spec=dict(d.get("spec") or {}),
                recipient=str(d.get("recipient", "target") or "target"),
                caster=str(d.get("caster", "") or ""),
                rounds_left=(None if d.get("rounds_left") is None
                             else int(d["rounds_left"])),
                source=str(d.get("source", "") or ""),
                save=str(d.get("save", "") or ""),
                dc=int(d.get("dc", 0) or 0),
                save_effect=str(d.get("save_effect", "") or ""),
                stops_with=str(d.get("stops_with", "") or ""),
                manifest_id=str(d.get("manifest_id", "") or ""),
            )
        except (TypeError, ValueError):
            return None


@dataclass
class BloodPool:
    """A pool of blood somewhere on the ground.

    `at` is a grid square when the scene has a grid and None when it does not — the
    same optionality the rest of the scene gives positions, so pools work in a
    theatre-of-the-mind fight and gain a location the moment a map is laid down.
    """
    owner: str
    at: tuple[int, int] | None = None
    amount: int = 1
    source: str = ""
    # WHICH floor it is on: the place id of the scene it was spilled in. Blood is a
    # fact about the room, not the bender — the review's ruling, against a first draft
    # that cleaned pools by owner on every move and so cost the one class whose
    # resource this is its bank for walking through a door. A pool is reachable when
    # its owner is back on this floor and not before; an old save's pools carry no
    # place and are read as here.
    place: str = ""

    def as_dict(self) -> dict:
        return {"owner": self.owner, "at": list(self.at) if self.at else None,
                "amount": self.amount, "source": self.source, "place": self.place}

    @classmethod
    def from_dict(cls, d: dict) -> "BloodPool":
        at = d.get("at")
        return cls(owner=d.get("owner", ""),
                   at=tuple(at) if at else None,
                   amount=int(d.get("amount", 1) or 1),
                   source=d.get("source", ""),
                   place=str(d.get("place") or ""))

    def here(self, scene) -> bool:
        return not self.place or self.place == scene.at


# --- The engine ---------------------------------------------------------------------

class Engine:
    def __init__(self, scene: Scene, dice: Dice | None = None, world=None):
        self.scene = scene
        self.dice = dice or Dice()
        self.scene._dice = self.dice
        # Optional, and only money reads it: what the coins are called belongs to the
        # world, and an engine built without one falls back to the Core Rulebook's own
        # names rather than refusing to do arithmetic.
        self.world = world
        # Where people are is reckoned against the world's own places and roads
        # (rules/residency.py), and half the finder's callers hold a scene and no world.
        if world is not None:
            from . import residency as _residency

            _residency.use_world(world)
        self._let_in: set = set()
        # Whether a fight began inside the current batch of intents. Read by the
        # attack op: a swing riding the same GM turn that opened the battle is
        # deferred to the player's own first combat turn, never resolved in prose.
        self._battle_joined = False
        # Where the party's one journey this batch has left them, or "". One journey a
        # turn (docs/playtest-2026-09-18.md item 35): a plan carrying five `travel` ops
        # walked the party across town in a single turn and left them standing on the
        # green while the prose described the market. Same shape as `_battle_joined`,
        # and for the same reason — a fresh batch is a fresh question.
        self._journeyed = ""
        # How many hours the way INTO a place costs, by place id, for the one hop that
        # reaches it. `_op_venture` sets it for the ground being entered and `_op_travel`
        # reads and clears it when its walk arrives on that hop, so a two-hour way into a
        # cave is checked for two hours on the road table — by the one meeting path, and
        # once. Before this the venture rolled its own check at the parent place, brought
        # the creature in THERE, opened the fight, and then moved the party in through
        # `travel`, which ended the fight and shed the creature: measured 2026-09-23, the
        # tell read "You are at the cave now. The fight is left behind. Left behind:
        # wolf. The road is not empty: a wolf is on it, and it has seen you."
        self._hours_underway: dict[str, int] = {}

    # --- Checks 2 and 3 -------------------------------------------------------------

    def validate(self, raw_intents: list, *, origin: str = "",
                 origin_name: str = "") -> list[Intent]:
        """Schema, then refs, then legality. Raises IntentError carrying which check
        failed so the caller can choose between regenerating and repairing.

        `origin` is the one trusted stamp of provenance. A door that turns a document
        into intents — the jar (`item:<id>`), a coating, the cheat clerk
        (`author:cheat`), a test (`author:test`) — passes it here, after parse, where
        the model cannot reach it; a model-written `origin` in params is refused at
        parse. Resolved by the door while it still holds the document, because the
        jar's last dose is popped from the satchel before its own heal is validated.
        """
        intents = parse_all(raw_intents)
        for intent in intents:
            intent.origin = str(origin or "")
            intent.origin_name = str(origin_name or "")
        # A place the plan founds, then goes to: the founding first. Measured live
        # 2026-09-26, a plan wrote `travel` to "the tavern" BEFORE the `found` that made
        # it — the list resolves in order, so the walk went looking for a place that did
        # not exist yet. Put right mechanically rather than refused: the plan said both.
        intents = _found_before_travel(intents)
        # And somebody the plan introduces as ALREADY HERE is here where the party ends
        # up. Measured live 2026-09-27: "I find somebody selling bread in the market" was
        # planned `introduce`, `travel` to the market, `say` to her — so she was made at
        # the crossing the party was leaving, and the question went to whoever stood in
        # the market instead.
        intents = _introduce_after_travel(intents)
        # Refs an earlier intent in this same list will have created by the time a later
        # one runs. Without this, "two bravos step out of the dark and I fight them" is
        # impossible to express: the whole list is validated before any of it runs, so a
        # spawn followed by an attack on what it spawned was always rejected, and the GM
        # burned every attempt guessing at refs that could not exist yet.
        pending = self._projected_refs(intents)
        # And the placeholders `introduce` hands out (new1, new2, new3), in the order the
        # people are introduced — legal only AFTER the intent that makes them, because the
        # list resolves in order and the swap to a real ref happens as each one lands.
        from .intents import INTRODUCED_REFS

        introduced: set[str] = set()
        # The places a `found` earlier in this list will have made by the time a later
        # `travel` runs — the `spawn` projection, for places. Without it "I look for a
        # tavern where the dockhands drink" could not become "found it, and walk in" in
        # one plan: validation refused the travel to a place that did not exist yet.
        self._planned_places: set[str] = set()
        # Who an earlier intent in this list moves. The same problem as `pending`, for
        # squares instead of refs: the combat panel posts "move to (6,10), strike the
        # thug" as one list, and a reach check asked of the board as it stands would
        # refuse the strike for the fifteen feet the move is about to close. Those
        # swings are left to the floor in `_op_attack`, which asks after the move.
        moved: set[str] = set()
        for i, intent in enumerate(intents):
            self._check_refs(intent, i, extra=pending | introduced)
            self._check_legality(intent, i, moved=moved)
            self._force_visibility(intent)
            if intent.op == "move":
                moved.add(str(intent.params.get("who") or intent.actor or ""))
            if intent.op == "introduce":
                # One introduce per plan, with `count` for a group. An op that is always
                # on offer gets over-used: Labyrinth's state-only planner "calls state
                # functions too frequently" (arXiv 2409.06949), and When2Call measured
                # Llama-3.1-8B calling a tool where none fitted 67% of the time (arXiv
                # 2504.18851). Measured live before any looser rule is allowed.
                if introduced:
                    raise IntentError(
                        "introduce: one introduce per turn — bring a group in together "
                        "with count, and anybody else next turn.", "schema", i)
                start = len(introduced)
                n = int(intent.params.get("count", 1) or 1)
                if start + n > len(INTRODUCED_REFS):
                    raise IntentError(
                        f"introduce: at most {len(INTRODUCED_REFS)} new people in one "
                        f"turn ({', '.join(INTRODUCED_REFS)}).", "schema", i)
                # Stamped here, after parse, so it survives a suspend (queued intents
                # are not re-parsed) and the model cannot write it: parse refuses any
                # param the op table does not list.
                intent.params["placeholders"] = list(INTRODUCED_REFS[start:start + n])
                introduced |= set(INTRODUCED_REFS[start:start + n])
            if intent.op == "found" and intent.params.get("name"):
                self._planned_places.add(_place_key(intent.params["name"]))
        self._planned_places = set()
        return intents

    def _projected_refs(self, intents: list[Intent]) -> set[str]:
        """The refs `spawn` intents in this list are going to mint.

        Through the one minter, with the refs projected so far passed as `taken`, so
        validation and minting cannot disagree — this used to be a hand-copied second
        version of the allocation loop, and CLAUDE.md's rule about copies of a rule
        exists because they drift. Validation consumes nothing: the mark advances only
        when a creature is actually added.
        """
        from .bestiary import next_ref

        projected: set[str] = set()
        for intent in intents:
            if intent.op != "spawn":
                continue
            for _ in range(int(intent.params.get("count", 1) or 1)):
                projected.add(next_ref(self.scene, taken=projected))
        return projected

    def _force_visibility(self, intent: Intent) -> None:
        """Only the PC can roll on the popup, so only the PC's rolls can be player-visible.

        Found on the first fully successful live turn: the GM marked the *guildhand's*
        Perception check `visibility: "player"`. Nothing suspended — the popup only ever
        asks the player for their own rolls — so the engine rolled it and then labelled
        it player-visible, which would have shown the player a number nobody rolled and
        handed the GM a hidden roll it was entitled to leak.

        "One PC. The dice popup only ever asks you for your own rolls" is an
        architecture decision, so it is enforced here rather than requested in a prompt.
        """
        actor = self.scene.get(intent.actor) if intent.actor else None
        if intent.visibility == "player" and (actor is None or not actor.is_pc):
            intent.visibility = "hidden"

    def _known(self, ref: str | None, extra: set[str] | None = None) -> bool:
        # A ref that is not a string is not a ref — and `ref in dict` on a list raises
        # `TypeError: unhashable type` rather than answering False. Found live on the
        # first `/cheat I defeat all the enemies`: gemma answered the plural honestly
        # with `"to": ["c2", "c3"]`, the validator died on the membership test, and
        # Django turned it into a 500 with a traceback. Every op here takes ONE ref;
        # a model that means several says so with several intents. Answering False
        # sends it to the `refs` branch, which is the one branch that repairs.
        return isinstance(ref, str) and bool(ref) and (
            ref in self.scene.actors or ref in (extra or set()))

    def _elsewhere(self, ref) -> str:
        """Where a ref the campaign holds but the party cannot reach is standing, or "".

        Under containment "unknown ref" splits in two, and the old refusal — "create
        them first with spawn" — would invite the model to spawn a duplicate of the
        merchant standing in the next room. This is the other branch. It does NOT say
        "travel there": a travel and an action on them in one list fails the action's
        own ref check, because validation runs against the view before anything moves.
        """
        if not isinstance(ref, str) or not ref:
            return ""
        actor = self.scene.people.get(ref)
        if actor is None or actor.at == self.scene.at:
            return ""
        from . import places as places_mod

        known = self.places()
        there = places_mod.find(known, actor.at)
        where = there.name if there is not None else "somewhere else"
        return (f"{ref} ({actor.name}) is at {where}, not here. Leave them out "
                f"of it this turn.")

    def _refuse_ref(self, intent: Intent, index: int, ref, role: str,
                    extra: set[str] | None) -> None:
        """One shape for every unknown-ref refusal, with the right branch chosen."""
        self._refuse_placeholder(intent, index, ref)
        away = self._elsewhere(ref)
        if away:
            raise IntentError(f"{intent.op}: {away}", "refs", index)
        raise IntentError(
            f"{intent.op}: unknown {role} {ref!r}; known refs are "
            f"{sorted(set(self.scene.actors) | (extra or set()))}."
            + (" Refer to people by ref, never by name." if role == "actor" else "")
            + _SPAWN_HINT,
            "refs", index,
        )

    def _refuse_placeholder(self, intent: Intent, index: int, ref) -> None:
        """`new1` with no `introduce` before it: refused with the two fixes named.

        Measured live 2026-09-27 (gemma-4-12B, the fight script): `attack new1` with no
        introduce, meaning the one man already in the room, fell through to the generic
        unknown-ref refusal and from there to the invented-ref repair, which spawned a
        thug called "new". A placeholder is the plan's own local id — JSON:API's `lid`
        names only a resource created in the same document — so the refusal says what
        the plan must do instead of what it may not.
        """
        from .intents import INTRODUCED_REFS

        if not (isinstance(ref, str)
                and re.fullmatch(r"new[ _-]?\d+", ref.strip(), re.I)):
            return
        here = ", ".join(f"{r} ({a.name})" for r, a in self.scene.actors.items()
                         if not a.is_pc) or "nobody"
        # The same split the prompt teaches: people arrive by `introduce`, a creature or
        # a foe arriving to fight by `spawn` — and in a fight only the second.
        arrive = ("a spawn written before it" if self.scene.in_encounter
                  else "an introduce written before it (a foe arriving to fight: a spawn)")
        raise IntentError(
            f"{intent.op}: {ref!r} is the placeholder introduce hands out "
            f"({', '.join(INTRODUCED_REFS)}), and nothing earlier in this plan introduces "
            f"anybody. Somebody already here is aimed at by their own ref — here: {here}. "
            f"Somebody new comes in by {arrive}.", "refs", index)

    def _check_cast_aim_ref(self, intent: Intent, index: int,
                            extra: set[str] | None) -> None:
        """A cast aimed at a ref nobody here holds is refused, never resolved at nobody.

        Measured live 2026-09-28 (G2, gemma-4-12B, Aurvantis, the cast-area script): with
        Kaelith Dagmar (c1) and the innkeeper (c2) in the room, "I cast burning hands at
        the man standing nearest me" was planned `cast burning-hands at=new2` — the
        placeholder for a person nobody introduced. Validation passed it and the engine
        RESOLVED it: "The flames reach nobody.", `caught: []`, `no_victim: true`. The page
        then invented a man called Dagan Havenstone and burned him, and the next turn's
        "I cast magic missile at him" reached nobody the same way and hit him again.

        Two holes, both closed here. The legacy `at` was never checked at all —
        `_check_aim` looked only at the `aim` param. And that check lived in
        `_check_legality`, which is not handed the refs an earlier `introduce` or `spawn`
        in the same list will make, so `introduce` then `aim ref:new1` was refused as
        though new1 could never exist. Here the aim is one more ref, checked with
        `extra` beside the actor and the target, and the refusal is plan-fixable
        (`no_such_target`, docs/fix-interfaces.md §2.6): the loop retries it with the
        people who ARE here named, in the attack op's words (`_refuse_placeholder`).
        """
        from . import areas

        caster = str(intent.actor or "")
        aim = areas.aim_of(intent.params, caster)
        if aim.kind != "ref" or self._known(aim.value, extra):
            return
        ref = aim.value
        here = ", ".join(f"{r} ({a.name})" for r, a in self.scene.actors.items()
                         if r != caster and not a.has_state("state.down.dead")) or "nobody"
        arrive = ("a spawn written before it" if self.scene.in_encounter
                  else "an introduce written before it (a foe arriving to fight: a spawn)")
        if re.fullmatch(r"new[ _-]?\d+", ref.strip(), re.I):
            from .intents import INTRODUCED_REFS

            lead = (f"{ref!r} is the placeholder introduce hands out "
                    f"({', '.join(INTRODUCED_REFS)}), and nothing earlier in this plan "
                    f"introduces anybody.")
        else:
            lead = self._elsewhere(ref) or f"nobody here is {ref!r}."
        raise IntentError(
            f"cast: {lead} A spell is aimed at somebody here by their own ref (aim "
            f"ref:<ref>) — here: {here}. If the player means somebody not yet in the "
            f"scene, bring them in by {arrive} in this same plan, and aim at the ref it "
            f"hands out.", "refs", index, code="no_such_target")

    def _check_refs(self, intent: Intent, index: int,
                    extra: set[str] | None = None) -> None:
        if intent.op == "introduce":
            if _spawn_names_a_thing(intent.params.get("who")):
                raise IntentError(
                    f"introduce: {str(intent.params.get('who'))!r} is a thing, not a "
                    f"person, and things are not introduced.", "legality", index)
            return
        if intent.op in ("narrate_only", "advance_time", "spawn", "begin_encounter"):
            if intent.op == "spawn" and _spawn_names_a_thing(intent.params.get("name")):
                raise IntentError(
                    f"spawn: {str(intent.params.get('name'))!r} is a thing, not a person "
                    f"or creature, and things are not spawned. A blow at a weapon or a "
                    f"table is an attack on the person holding or standing at it: aim "
                    f"the attack at their ref.", "legality", index)
            if intent.op == "begin_encounter":
                sides = intent.params["sides"]
                # Same family as the `_known` guard above: a container where a mapping
                # was expected is an AttributeError and a 500, not a rejection. The
                # model writes `sides` as a list of refs often enough to matter.
                if not isinstance(sides, dict):
                    raise IntentError(
                        "begin_encounter: sides is a map of side name to a list of "
                        f"refs, like {{\"you\": [\"pc\"], \"them\": [\"c1\"]}} — got "
                        f"{sides!r}", "schema", index)
                for side, refs in sides.items():
                    if isinstance(refs, str):
                        refs = [refs]
                    for r in refs:
                        if not self._known(r, extra):
                            raise IntentError(
                                f"begin_encounter: side {side!r} names unknown ref {r!r}; "
                                f"known refs are {sorted(set(self.scene.actors) | (extra or set()))}",
                                "refs", index,
                            )
            return

        needs_actor = intent.op in ("check", "save", "attack", "move")
        if needs_actor and not self._known(intent.actor, extra):
            self._refuse_ref(intent, index, intent.actor, "actor", extra)
        for t in intent.targets():
            if not self._known(t, extra):
                self._refuse_ref(intent, index, t, "target", extra)
        if intent.op == "cast":
            self._check_cast_aim_ref(intent, index, extra)
        # `with` was read at one production line and validated by none: the model could
        # name a ref the store holds in another room, and travel would have moved a
        # creature it could not see. Names are allowed (resolved by `_op_travel`) and
        # simply ignored when unknown, as before; a REF must be here.
        if intent.op == "travel":
            for w in (intent.params.get("with") or []):
                if isinstance(w, str) and re.fullmatch(r"c\d+|pc", w) \
                        and not self._known(w, extra):
                    self._refuse_ref(intent, index, w, "escort", extra)
        opposed = intent.params.get("opposed_by")
        if opposed and not isinstance(opposed, dict):
            raise IntentError(
                "check: opposed_by is an object naming a ref and a skill, like "
                f"{{\"ref\": \"c1\", \"skill\": \"perception\"}} — got {opposed!r}",
                "schema", index)
        if opposed and not self._known(opposed.get("ref"), extra):
            raise IntentError(
                f"check: opposed_by names unknown ref {opposed.get('ref')!r}",
                "refs", index,
            )
        to = intent.params.get("to")
        # `journey` is the one op whose `to` names a place rather than a body — a
        # settlement the world wrote a road to. `_op_journey` resolves it against that
        # road list and refuses an unknown one by naming the ones that exist, which is
        # the same courtesy `travel` extends to a place.
        if to and intent.op != "journey" and not self._known(to, extra):
            self._refuse_placeholder(intent, index, to)
            raise IntentError(
                f"{intent.op}: unknown ref {to!r} in params.to", "refs", index
            )
        frm = intent.params.get("from_")
        if intent.op == "loot" and frm and not self._known(frm, extra):
            raise IntentError(
                f"{intent.op}: unknown ref {frm!r} in params.from", "refs", index
            )

    def _check_legality(self, intent: Intent, index: int,
                        moved: set[str] | frozenset[str] = frozenset()) -> None:
        # The cheap facts, asked HERE so the model gets its retry with the list in
        # hand. Stage 7 measured that a refusal raised at resolution reaches nobody who
        # can act on it — `_advance` catches it once, answers 502, and pops the
        # player's line — while a refusal raised here goes back through the
        # five-attempt schedule with the fix named. "Is the item in the satchel" and
        # "is that an ability they have" are single lookups against the actor as it
        # stands, not a simulation of the list; the resolution-time floor below each
        # op still prints when the list has changed under itself.
        # The line, drawn by a live probe. A first cut of this also rejected "not
        # carrying that", "not on the counter today" and "the pool is empty" here, on
        # the theory that the model could then name something else. Probed against
        # gemma-4-12B: asked to drink a potion the satchel did not hold, the model
        # never proposed `use_item` at all — it emitted a bare `heal` and a `drink`,
        # and narrated a vial that did not exist. A rejection for a FACT ABOUT THE
        # WORLD hands the model a reason to route around the refusal; the player then
        # never learns the truth. So the line is the contract's own: what the MODEL
        # got wrong (a way of using a jar that does not exist, a weapon it is not
        # holding, a pool or an ability by a name nobody has) rejects here with the
        # fix named; what the PLAYER could not have known prints at resolution.
        #
        # The backstop of stage 8: a number with nothing behind it. The sampler no
        # longer offers these ops to the model at all (gm.prompts.turn_schema), so the
        # message here is for the engine's own doors and for a prompt that has
        # drifted — and it still names the fix rather than the fault.
        #
        # Every raise here carries a `code` (docs/fix-interfaces.md §2.6; the cast
        # branch's are `_check_cast`'s). Only a code in `intents.PLAYER_FIXABLE` stops
        # the plan loop — "no_such_weapon", "out_of_reach": the character's own gear and
        # the player's own words, which no second plan can change. The rest name the
        # plan's mistake ("no_document", "no_such_place", "no_such_target"…) and the
        # loop retries them as it always has. Measured 2026-09-28 (item 21.3): with no
        # code at all, a refusal only the player could fix went round seven attempts.
        if intent.op in AMOUNT_OPS and not intent.origin:
            raise IntentError(
                f"{intent.op}: no document behind this number. Name what does it: "
                f"use_item item=<id> for a jar, cast spell=<id> for a spell, "
                f"use_ability ability=<name> for a power. The engine supplies the "
                f"amount from the document.", "legality", index, code="no_document")
        # The outliers the maps found beside the seven (stage 8d): dice inside a
        # save's branches, a guard's absorb/share numbers, and a pool gained out of
        # nowhere. Each is the model authoring a number; each names the door.
        if intent.op == "save" and not intent.origin:
            for branch in ("on_failure", "on_success"):
                got = intent.params.get(branch) or {}
                if isinstance(got, dict) and got.get("damage"):
                    raise IntentError(
                        f"save: the {branch} damage is a number nobody wrote down. A "
                        f"spell's save carries its own dice (cast spell=<id>); a fall "
                        f"or a fire is hazard rule=<id>. A bare save carries a "
                        f"condition, not dice.", "legality", index, code="no_document")
        if intent.op == "guard" and not intent.origin:
            kind = str(intent.params.get("kind", "redirect"))
            numbered = [k for k in ("amount", "uses") if intent.params.get(k)]
            if kind != "redirect" or numbered:
                raise IntentError(
                    f"guard: {kind} with {', '.join(numbered) or 'a number'} is an "
                    f"ability's to declare — use_ability ability=<name> and its "
                    f"document sets the amount. A plain guard is kind=redirect with "
                    f"no numbers.", "legality", index, code="no_document")
        if intent.op == "resource" and not intent.params.get("spend") \
                and not intent.origin:
            raise IntentError(
                f"resource: a pool is not gained by saying so. Pools refill by "
                f"rest ({{\"op\": \"rest\"}}) or by an ability's document "
                f"(use_ability ability=<name>); spend=true spends one.",
                "legality", index, code="no_document")
        # Stage 8's rule, asked of a mind instead of a number.
        #
        # Reported from the table 2026-09-09: "I was able to break the game and use
        # psychic powers to manipulate the people and story in ways that should not be
        # possible." Reproduced in one intent — `condition` with `condition: helpful`
        # and `to: c1`, no ability, no spell, no origin — and the merchant went from
        # indifferent to helpful, tell and all. Nothing on any sheet was consulted,
        # because nothing asked. The seven amount-ops have been gated on provenance
        # since stage 8a; an attitude is a bigger lever than a number and had no gate
        # at all, and `condition` IS offered to the sampler (it is not an amount-op).
        #
        # The GAS rule this is: an ability that was never granted cannot be activated.
        # Here the grant is the document — a spell in the book, a power on the sheet, an
        # item in the satchel — and `origin` is the engine's record that one was read.
        # No document, no mind changed.
        #
        # Lifting one is NOT gated, and the inversion is the same one `_op_condition`
        # documents above: gate a removal and a charm can never be broken, exactly as
        # gating the applicator made 759 undead unkillable.
        if intent.op == "condition" and not intent.origin \
                and not intent.params.get("ends"):
            touched = states.touches_the_mind(
                str(intent.params.get("condition", "")),
                intent.params.get("descriptors") or ())
            if touched:
                raise IntentError(
                    f"condition: {touched} is not something anyone can simply decide "
                    f"on. Name what does it: cast spell=<id> for a spell, use_ability "
                    f"ability=<name> for a power on the sheet, use_item item=<id> for "
                    f"an item. To move somebody by ordinary means, talk to them and "
                    f"roll it: check skill=diplomacy, check skill=intimidate, "
                    f"check skill=bluff.", "legality", index, code="mind_ungated")
        if intent.op == "travel" and intent.params.get("place"):
            # A destination the scene does not hold is refused HERE, where the plan's
            # repair loop reads the message and names a real one — not in `run`,
            # where the same refusal was a 502 on the page ("there is no 'the
            # merchant's gate' here", 2026-09-06). The lenient finder answers the
            # GM's own dressing of a real place first ("the merchant's gate" is the
            # gate), so this fires only for a place that is nowhere.
            from . import places as places_mod

            known = self.places()
            # The open ground outside the walls answers by name too — the region
            # places a scheme's card names ("the approach", "the edge") — the same
            # lookup `_op_travel` makes, so validate and run agree.
            outside = ()
            if self.world is not None:
                terrain = self._terrain_hint(self.world.get(self.scene.location_id)) or ""
                if terrain:
                    outside = places_mod.region_set(self.scene.location_id, terrain)
            planned = _place_key(intent.params["place"]) in getattr(self, "_planned_places", ())
            if known and not planned \
                    and places_mod.find(known, str(intent.params["place"])) is None \
                    and places_mod.find(outside, str(intent.params["place"])) is None:
                raise IntentError(
                    f"travel: there is no {intent.params['place']!r} here. Name one of: "
                    f"{', '.join(p.name for p in known)} — or, if the scene goes somewhere "
                    f"new that a place like this would have, found it first in the same "
                    f"plan: {{\"op\": \"found\", \"params\": {{\"name\": "
                    f"{intent.params['place']!r}, \"kind\": \"tavern\"}}}} (kind: what it "
                    f"is), then travel to it.", "schema", code="no_such_place")
        if intent.op == "hazard":
            trouble = hazards.check(str(intent.params.get("rule", "")), intent.params)
            if trouble:
                raise IntentError(f"hazard: {trouble}", "legality", index, code="hazard_rule")
        if intent.op == "use_item" and intent.actor:
            actor = self.scene.get(intent.actor)
            said = str(intent.params.get("item", "")).strip().lower()
            item_id, _fits = (consumables.resolve_stock(actor.stock, said)
                              if actor is not None and said else (None, []))
            held = actor.stock.get(item_id) if item_id else None
            if held is not None and held.count >= 1:
                    how = str(intent.params.get("how", "drink")).strip().lower()
                    use = consumables.plan(held, how=how,
                                           target=intent.params.get("to") or intent.actor,
                                           because=intent.because)
                    if not use.ok:
                        raise IntentError(f"use_item: {'; '.join(use.problems)}",
                                          "legality", index, code="item_use")
                    if how == "coat":
                        weapon = str(intent.params.get("weapon") or actor.equipped
                                     or "").lower()
                        if not weapons_mod.has(weapon):
                            raise IntentError(
                                f"use_item: {actor.name} has no weapon {weapon!r} to coat",
                                "legality", index, code="no_weapon_to_coat")
        if intent.op == "resource" and intent.params.get("spend"):
            # The pool as it stands. A list that spends the same pool twice reaches the
            # printed floor in the resolver for the second one; this is the first.
            ref = intent.params.get("to") or intent.actor \
                or (self.scene.pc().ref if self.scene.pc() else None)
            target = self.scene.get(ref) if ref else None
            pool_id = str(intent.params.get("pool", "")).strip().lower()
            # A pool by a name nobody has is the model's error — the contract's own
            # worked example — and rejects here with the pools named. Empty, or still
            # recharging, is a fact about the sheet and prints at resolution.
            if target is not None and pool_id and target.pool(pool_id) is None:
                raise IntentError(
                    f"resource: no pool called {pool_id!r} on {target.name}. Their "
                    f"pools are: {', '.join(sorted(target.pools)) or 'none'}.",
                    "legality", index, code="no_such_pool")
        if intent.op == "ability_damage":
            ab = str(intent.params.get("ability", "")).strip().lower()
            if ab and ab not in ABILITY_FULL:
                raise IntentError(
                    f"ability_damage: no ability score called {ab!r}. The six are: "
                    f"{', '.join(ABILITY_FULL)}.", "schema", index,
                    code="no_such_ability_score")
        # `use_ability` with a name nobody has is NOT rejected here, on purpose. The
        # name is usually the PLAYER's ("I use Blood Nova on the merchant"), and
        # `judgement.refuse_unknown_ability` puts it into the list precisely so the
        # resolver prints the refusal with the real names — a rejection would send the
        # model back round for something it cannot fix, and the model's answer to that,
        # measured live, was an attack.
        if intent.op == "rest" and self.scene.in_encounter:
            # "Any significant interruption during your rest prevents you from healing
            # that night." Being in a fight is the significant interruption.
            raise IntentError(
                "rest: there is a fight going on. Nobody sleeps through a fight, and a "
                "night's rest cannot be taken mid-encounter.",
                "legality", index, code="in_a_fight",
            )
        if intent.op == "rest":
            pc = self.scene.pc()
            if pc is not None and pc.hp < 0:
                raise IntentError(
                    f"rest: {pc.name} is bleeding out, not sleeping. They have to be "
                    f"stabilised first.",
                    "legality", index, code="bleeding_out",
                )

        if intent.op == "craft":
            self._check_craft(intent, index)

        if intent.op == "cast":
            self._check_cast(intent, index)

        if intent.op == "move" and intent.params.get("square") is not None:
            self._check_move(intent, index)

        actor = self.scene.get(intent.actor) if intent.actor else None
        # The three ops this guard has always refused, and deliberately not `cast`,
        # which `states.BLOCKS` does say a stunned character cannot do. A refusal here
        # is an `IntentError` of check "legality", and a legality error regenerates
        # rather than repairs — while `turn_schema` builds a `contains` the sampler
        # cannot violate, so "I cast magic missile" forces the op that is about to be
        # refused and burns every attempt. Required-op meeting hard-refusal is the
        # buried-502 class, and turning these three into printable Outcomes is stage
        # 7's subject; adding a fourth op to the pile first would be shipping a new
        # blank page to fix a rules nicety.
        if actor and intent.op in ("attack", "move", "check"):
            # Asked per op, because the states are not all total. A nauseated character
            # gets their single move action, which the old `can_act()` boolean refused
            # along with everything else — it was the one action 1e explicitly allows.
            stopped = actor.blocking_condition(intent.op)
            if stopped:
                raise IntentError(
                    f"{intent.op}: {actor.name} is {stopped.lower()} and cannot "
                    f"{intent.op}",
                    "legality", index, code="condition_blocks",
                )
        if intent.op == "attack" and actor:
            key = intent.params.get("weapon") or actor.wielded_key()
            # A granted weapon is worn, not carried: it exists while its toggle holds
            # and nowhere else, so both the weapons-table check and the carried-list
            # check would refuse it for the wrong reason. Which grants exist — and
            # which aliases name them — is the class document's to say.
            from . import leveling

            granted = leveling.granted_weapon_named(actor, key)
            if granted is not None:
                if granted["key"] and not actor.has_condition(granted["key"]):
                    raise IntentError(
                        f"attack: the {granted['key']} is not formed. Use "
                        f"{granted['ability']} to form it first.", "legality", index, code="not_formed")
            elif actor.stat_block_weapon(key) is not None:
                # A printed attack: the ogre's greatclub, the owlbear's claws, a
                # dragon's tail slap. The stat block is the creature's inventory.
                pass
            elif (actor.stat_block_attacks()
                  and str(key).strip().lower() not in ("unarmed", "improvised")
                  and str(key).strip().lower() not in (actor.weapons or ())):
                # A monster reaching for a weapon its block does not print. It used to
                # be let through (a stat-block creature carries no `weapons` list, so
                # the carried check below never fired) and then swung at its printed
                # +7 with the named weapon's dice and its Strength on top — a number
                # that is neither the book's nor a derivation.
                printed = [a["key"] for cat in ("melee", "ranged")
                           for opt in actor.stat_block_attacks().get(cat) or ()
                           for a in opt]
                raise IntentError(
                    f"attack: {actor.name} has no {key}. Its attacks are "
                    f"{', '.join(dict.fromkeys(printed))}.", "legality", index, code="no_such_weapon")
            elif actor.natural_weapon(key) is not None:
                # The body's own weapon. Checked before the table, because the table
                # holds none of them: `weapons_mod.has("bite")` is False for every
                # natural attack in the evolution pool, so a race that grants a bite
                # was refused here even once `intents._known_weapon` let the name
                # through. Asking the actor is the only question worth asking — it is
                # their race document that says whether they have jaws.
                pass
            elif not weapons_mod.has(key):
                raise IntentError(
                    f"attack: {actor.name} has no weapon {key!r}", "legality", index, code="no_such_weapon"
                )
            elif (key.lower() not in [w.lower() for w in actor.weapons]
                  and self.scene.out_of_hand(actor.ref, key)):
                # Checked before the carried-list test, because that one is skipped
                # when the list is EMPTY (a bestiary creature with no list may swing
                # anything it is statted for) — and a thug disarmed of his last weapon
                # has an empty list, so his sap lying on the ground was swingable by
                # name. The ledger says where it is, and the refusal says so.
                rec = self.scene.out_of_hand(actor.ref, key)
                holder = self.scene.actors.get(str(rec.get("held_by") or ""))
                where = (f"is in {holder.name}'s hands" if holder is not None
                         else "lies on the ground")
                raise IntentError(
                    f"attack: {actor.name}'s {key} {where}. Picking it up is a give "
                    f"to {actor.ref} of '{rec['name']}'.", "legality", index, code="weapon_out_of_hand")
            elif (actor.weapons and key not in actor.weapons
                  and key not in ("unarmed", "improvised")):
                raise IntentError(
                    f"attack: {actor.name} is not carrying a {key} "
                    f"(has {', '.join(actor.weapons) or 'nothing'})",
                    "legality", index, code="no_such_weapon",
                )
            elif (actor.gear.get(key.lower()) is not None
                  and actor.gear[key.lower()].destroyed):
                # The sunder's "destroyed — in pieces" left the club on the weapons
                # list, so the pieces could be swung by name at full damage.
                raise IntentError(
                    f"attack: {actor.name}'s {key} is destroyed — in pieces.",
                    "legality", index, code="weapon_destroyed")
            if intent.params.get("power_attack"):
                why = actor.can_power_attack()
                if why:
                    raise IntentError(f"attack: {why}", "legality", index, code="cannot_power_attack")
            # "You can use a MELEE weapon that deals lethal damage to deal nonlethal
            # damage instead" (Core Rulebook p.191). An arrow cannot be pulled; a sling
            # of softstones already deals nonlethal and needs no param at all.
            if intent.params.get("lethality") == "nonlethal":
                held = actor.weapon(key)
                if (held.get("category") != "melee"
                        and weapons_mod.lethality_of(held) == "lethal"):
                    raise IntentError(
                        f"attack: a {held['name']} cannot pull its blow — only a melee "
                        f"weapon can deal non-lethal damage instead of lethal (at -4). "
                        f"Drop `lethality`, or strike with a melee weapon or the fists.",
                        "legality", index, code="cannot_pull_blow")
            man = intent.params.get("manoeuvre")
            if man:
                m = MANEUVERS[man]
                targets = intent.targets()
                defender = self.scene.get(targets[0]) if targets else None
                if defender is None:
                    raise IntentError(
                        f"attack: a {man} needs a target", "legality", index, code="no_such_target"
                    )
                # "You can only X an opponent who is no more than one size category
                # larger than you."
                limit = m.get("size_limit")
                if limit is not None:
                    try:
                        gap = SIZE_ORDER.index(defender.size) - SIZE_ORDER.index(actor.size)
                    except ValueError:
                        gap = 0
                    if gap > limit:
                        raise IntentError(
                            f"attack: {defender.name} is {defender.size} and "
                            f"{actor.name} is {actor.size} — a {man} only works on a "
                            f"target at most one size category larger.",
                            "legality", index, code="too_large",
                        )
                if m.get("condition") and defender.has_condition(m["condition"]):
                    raise IntentError(
                        f"attack: {defender.name} is already "
                        f"{m['condition']}", "legality", index, code="already",
                    )
            # Reach, asked here so the model gets its retry with the square to step
            # to in hand. Unless this list moves one of them first — then only the
            # board after the move can answer, and the floor in `_op_attack` does.
            # Only where a blow will actually land: inside a running fight, or a coup
            # de grace, which resolves on the spot with no fight (a sleeping guard). A
            # swing that opens a fight rolls nothing — it joins battle and defers — so
            # that blow is declared, and measured, on the attacker's first turn.
            # Nor while the target is still a question: with `undecided` parked, the
            # ref is a placeholder and `_op_attack` asks "which of them?" — the
            # distance to somebody nobody chose is not the refusal to print.
            targets = intent.targets()
            defender = self.scene.get(targets[0]) if targets else None
            if defender is not None \
                    and (self.scene.in_encounter or intent.params.get("coup_de_grace")) \
                    and not intent.params.get("undecided") \
                    and not ({intent.actor, defender.ref} & set(moved)):
                why = self._reach_refusal(intent, actor, defender, key)
                # One move reaches them: the blow stands, and `_drive` walks the closing
                # step in front of it (the owner's ruling, 2026-09-29). The attacker is
                # counted as moving in this list, so a second blow behind this one is
                # measured on the board after the step, by the floor, like any blow
                # behind a move.
                if why and self._closing_step(intent, actor, defender, key) is not None:
                    if isinstance(moved, set):
                        moved.add(intent.actor)
                    why = ""
                if why:
                    raise IntentError(
                        f"attack: {why}", "legality", index, code="out_of_reach",
                        for_a_person=self._reach_refusal(intent, actor, defender, key,
                                                         voice="person"))

    # --- Running --------------------------------------------------------------------

    def run(self, intents: list[Intent]) -> Resolution:
        # A fresh batch is a fresh question. Reset here and not in `resume`, because a
        # resume continues the same declared turn — a battle joined before the player
        # was handed a die is still the battle this batch joined, and a journey already
        # walked before a die was handed over is still this turn's one journey.
        self._battle_joined = False
        self._journeyed = ""
        self._provoked = set()
        # Homes whose door opened to the party this batch (`_op_call_on`, `_knock`).
        self._let_in = set()
        return self._tick_schemes(self._their_first_blow(
            self._drive([i.as_dict() for i in intents], [], {})))

    def _their_first_blow(self, resolution: "Resolution") -> "Resolution":
        """Somebody else opened the fight: their blow is rolled now, in this batch.

        The first-swing gate defers the swing that opens a fight, and for the PLAYER that
        is right — the dice are theirs, on their own first combat turn. For anybody else
        it is the wait the user refused: "I should be put into combat when I am attacked,
        it shouldn't wait for me" (2026-09-18). `struck_first` answered it by running the
        attack twice; this is that rule in the one place every door comes through, so a
        blow the PLAN declares (docs/declared-not-guessed.md, the blows door) is rolled
        before the prose is written, and the prose describes what actually landed.
        Only the initiator, holding the turn: anybody who came in on the same batch
        takes their swing in the order, as ever.
        """
        if resolution.awaiting or not self.scene.in_encounter:
            return resolution
        opened = next((e for o in resolution.outcomes if o.op == "attack"
                       for e in (o.effects or []) if e.get("kind") == "battle_joined"), None)
        if opened is None:
            return resolution
        ref, target = opened.get("ref"), opened.get("target")
        a = self.scene.actors.get(ref)
        if a is None or a.is_pc or target not in self.scene.actors:
            return resolution
        holding = (self.scene.initiative[self.scene.turn][0]
                   if self.scene.initiative and 0 <= self.scene.turn < len(self.scene.initiative)
                   else None)
        if holding != ref:
            return resolution
        # He lunged: if he stands out of reach, the lunge is the move that closes it,
        # then the blow — declared, told, provoking as it goes, never a silent shift of
        # where he stands. Too far for one move, the blow is the loop's to decide, and
        # he is not rolled a swing he could not have landed.
        from . import position as position_mod

        params = dict(opened.get("params") or {})
        closing = position_mod.closing_move(
            self.scene, a, self.scene.actors[target],
            params.get("weapon") or a.equipped or "unarmed")
        if closing is not None and not closing[1]:
            return resolution
        try:
            blow = self.validate(([closing[0]] if closing is not None else []) + [
                {"op": "attack", "actor": ref, "target": target,
                 "because": f"{a.name} struck first", "params": params}])
        except (IntentError, ValueError, KeyError):
            return resolution
        self._battle_joined = False
        return self._drive([i.as_dict() for i in blow],
                           [o.as_dict() for o in resolution.outcomes], {})

    def _tick_schemes(self, resolution: "Resolution") -> "Resolution":
        """After a batch resolves, the world's schemes get their tick (rules/schemes.py):
        the steps whose criteria now hold are candidates, the most specific fires, and
        a step the player could witness comes back as an outcome with a tell — a step
        they could not stays silent, on the log and the secret card only. Skipped
        while a roll is waiting: the batch is not over."""
        if resolution.awaiting:
            return resolution
        from . import schemes as schemes_mod

        # Whoever is no longer in a fit state to be talked to leaves the conversation,
        # said: a person who walked out, went down or drew is not somebody the player
        # has to take their leave of.
        resolution.outcomes.extend(self._settle_talk())
        # The party arrived somewhere this batch: people go where their day or their road
        # puts them (rules/residency.py). No outcome and no tell — WHO IS HERE is the view
        # of who is in the room, and it simply has them or does not.
        if not self.scene.in_encounter:
            self.settle_people()
        # A scheme that fails half-way leaves nothing of itself behind. Measured
        # 2026-09-25: the tick reads and CHANGES the scene (steps advance, people are
        # brought in, bodies fall), and a failure part-way kept whatever it had already
        # done — the turn went on, and the next save wrote the half-run step. Snapshot
        # only when there is a scheme to tick: a deep copy per turn for nothing is a cost.
        undo = self.scene.snapshot() if getattr(self.scene, "schemes", None) else None
        try:
            extra = schemes_mod.tick(self, resolution.outcomes)
        except Exception as exc:  # noqa: BLE001 — a scheme must never take the turn down
            if undo is not None:
                self.scene.restore(undo)
            import logging

            logging.getLogger("pathfindergm").exception(
                "a scheme's tick failed and was undone")
            extra = [Outcome(intent_id="", op="scheme", effects=[{"kind": "scheme_error",
                                                                   "error": str(exc)}],
                             tell="", because="")]
        resolution.outcomes.extend(extra)
        return resolution

    def resume(self, face: int) -> Resolution:
        """Continue a suspended list with the face the player rolled."""
        if not self.scene.awaiting:
            raise RuntimeError("nothing is awaiting a player roll")
        partial = dict(self.scene.pending_partial)
        partial["player_face"] = int(face)
        remaining = list(self.scene.pending_intents)
        done = list(self.scene.pending_outcomes)
        self.scene.awaiting = None
        self.scene.pending_intents = []
        self.scene.pending_outcomes = []
        self.scene.pending_partial = {}
        return self._tick_schemes(self._drive(remaining, done, partial))

    def _drive(self, remaining: list[dict], done: list[dict], partial: dict) -> Resolution:
        outcomes = [_rehydrate(o) for o in done]
        queue = list(remaining)
        while queue:
            raw = queue[0]
            # Reactions are owed by the rules, not proposed by anyone, and they happen
            # *before* the action that provoked them completes: an attack of opportunity
            # lands as the creature leaves the square, so if it drops them they never
            # arrive. The flag is what stops the spliced reaction from provoking itself
            # forever — it is stripped before anything else sees the intent.
            if not raw.pop("_reacted", False):
                fired = self._reactions_before(raw)
                if fired:
                    queue[0:0] = fired
                    raw["_reacted"] = True
                    continue
            # A blow one move short: the move goes in front of it as a real intent, so it
            # provokes through `_reactions_before` exactly as a declared move does, and
            # an attack of opportunity that drops the attacker stops the blow behind it
            # (`_op_attack`'s "never swings"). Asked once per blow — the flag — and never
            # on a resume, which is the same blow part-way through its dice.
            if not partial and not raw.pop("_closed", False):
                step = self._close_before(raw)
                if step is not None:
                    # The step is the move action and this blow the standard one; any
                    # further blow of the same attacker's in this list would be a full
                    # attack after a move, which the rule does not allow. Marked in its
                    # params, so the mark survives a suspension for the player's dice.
                    for later in queue[1:]:
                        if later.get("op") == "attack" \
                                and later.get("actor") == raw.get("actor") \
                                and not (later.get("params") or {}).get("reaction"):
                            later["params"] = dict(later.get("params") or {},
                                                   after_close=True)
                    queue[0:0] = [step]
                    raw["_closed"] = True
                    continue

            intent = _intent_from_dict(raw)
            try:
                outcome = self._resolve_one(intent, partial)
            except _NeedsPlayerRoll as suspend:
                # Freeze the rest of the list, including the intent we stopped inside.
                self.scene.pending_intents = list(queue)
                self.scene.pending_outcomes = [o.as_dict() for o in outcomes]
                self.scene.pending_partial = suspend.partial
                self.scene.awaiting = suspend.prompt
                return Resolution(outcomes=outcomes, awaiting=suspend.prompt)
            queue.pop(0)
            partial = {}
            outcomes.append(outcome)
            # The plan's placeholders (new1…) become the refs just made, in everything
            # still queued — rewritten in the queue itself, so a turn that suspends for
            # the player's roll later on carries real refs into the save.
            if intent.op == "introduce":
                bound = next((e.get("bound") for e in (outcome.effects or [])
                              if e.get("kind") == "introduce"), None) or {}
                if bound:
                    queue = [_rename_refs(r, bound) for r in queue]
            # Provoked past bearing: their own blow, with their fists — a provoked brawl
            # is fists, as a Skyrim brawl is (rules/provocation.py) — next in the queue.
            # It opens the fight from their side and `run` rolls it before the prose.
            # Called on, or broken in on: the party walks to the door, or in through it.
            if intent.op in ("call_on", "break_in"):
                went = next((e for e in (outcome.effects or [])
                             if e.get("kind") == "call_on" and e.get("go")), None)
                if went is not None and went["go"] != self.scene.at:
                    queue.insert(0, {"op": "travel", "params": {"place": went["go"]},
                                     "because": "calling on them"})
            if intent.op == "provoke":
                hit = next((e for e in (outcome.effects or [])
                            if e.get("kind") == "provoked" and e.get("strikes")), None)
                pc = self.scene.pc()
                if hit is not None and pc is not None:
                    queue.insert(0, {"op": "attack", "actor": hit["ref"], "target": pc.ref,
                                     "params": {"weapon": "unarmed"},
                                     "because": "provoked past bearing"})
            # Anyone who has done something is no longer flat-footed.
            if intent.actor and intent.op in ("attack", "check", "move", "save"):
                self.scene.acted.add(intent.actor)
            self.scene.log.append(outcome.as_dict())
            if len(self.scene.log) > self.scene.LOG_KEPT:
                del self.scene.log[:-self.scene.LOG_KEPT]
        return Resolution(outcomes=outcomes)

    # --- Reactions ---------------------------------------------------------------------

    def _reactions_before(self, raw: dict) -> list[dict]:
        """Intents owed to other creatures because of the one about to resolve.

        Returned as raw intent dicts so they go through `_drive` exactly like anything
        else — which is what makes a player-taken attack of opportunity suspend for a dice
        roll without a single line of special handling.

        Movement provokes, and so does picking a thing up off the ground (1e Table 7-2,
        "Pick up an item": a move action, attack of opportunity yes). The shape is a
        dispatch rather than an `if` because the next triggers (casting in a threatened
        square, standing up from prone) are the same machinery with a different question.
        """
        if not self.scene.in_encounter:
            return []
        if raw.get("op") == "give":
            return self._provoked_by_pick_up(raw)
        if raw.get("op") != "move":
            return []

        ref = (raw.get("params") or {}).get("who") or raw.get("actor")
        square = (raw.get("params") or {}).get("square")
        if not ref or square is None or not self.scene.has_grid:
            return []

        start = self.scene.positions.get(ref)
        out: list[dict] = []
        for watcher, reaction in reactions.provoked_by_move(
                self.scene, ref, start, tuple(square)):
            if not self._spend_reaction(watcher, reaction.budget):
                continue
            out.append({
                "op": reaction.op,
                "actor": watcher,
                "target": ref,
                "because": reaction.because,
                # Never a full attack: an attack of opportunity is a single swing, and
                # letting it inherit the attacker's iteratives would turn a fighter's
                # threatened square into four free attacks a round.
                "params": {"full_attack": False, "reaction": reaction.id},
                "visibility": "player" if self.scene.actors[watcher].is_pc else "hidden",
            })
        return out

    def _provoked_by_pick_up(self, raw: dict) -> list[dict]:
        """The attacks of opportunity a pick-up from the ground is owed.

        Only a thing that IS lying here with a record: a `give` from a giver's hands, a
        purchase, or a thing the world supplies with no record is not somebody stooping
        in a fight. And only when it is in reach — out of reach the give is refused, and
        a swing at a creature for a pick-up that never happened would be the engine
        inventing an opening. Found 2026-09-27: until this, the player's own pick-up of
        a disarmed thug's sap was a free action with a thug standing over it.
        """
        params = raw.get("params") or {}
        if params.get("from_") or params.get("price"):
            return []
        taker = params.get("to") or raw.get("target") or raw.get("actor")
        rec = self.scene.prop_on_the_ground(str(params.get("item", "")))
        if not taker or taker not in self.scene.actors or rec is None:
            return []
        if self.scene.within_reach(taker, rec):
            return []
        mover = self.scene.actors[taker]
        thing = str(rec.get("from_") or rec.get("name"))
        out: list[dict] = []
        for watcher, reaction in reactions.provoked_by_action(self.scene, taker):
            if not self._spend_reaction(watcher, reaction.budget):
                continue
            out.append({
                "op": reaction.op, "actor": watcher, "target": taker,
                "because": f"{mover.name} stooped for the {thing} within reach",
                "params": {"full_attack": False, "reaction": reaction.id},
                "visibility": "player" if self.scene.actors[watcher].is_pc else "hidden",
            })
        return out

    def _spend_reaction(self, ref: str, budget: str) -> bool:
        """Take one from this creature's allowance, or refuse.

        Refusing silently is right here and is not right anywhere else in the engine: an
        exhausted allowance is not an error the GM can repair, it is simply a swing that
        does not happen, and surfacing it as a rejection would abort the mover's whole
        intent list over somebody else's spent resource.
        """
        actor = self.scene.actors.get(ref)
        if actor is None:
            return False
        key = f"{ref}:{budget}"
        used = self.scene.reacted.get(key, 0)
        if used >= reactions.budget_for(actor, budget):
            return False
        self.scene.reacted[key] = used + 1
        return True

    # --- Op handlers -------------------------------------------------------------------

    def _resolve_one(self, intent: Intent, partial: dict) -> Outcome:
        handler = getattr(self, f"_op_{intent.op}", None)
        if handler is None:
            raise IntentError(f"no handler for op {intent.op!r}", "schema")
        return handler(intent, partial)

    # narrate_only ---------------------------------------------------------------------

    def _op_narrate_only(self, intent: Intent, partial: dict) -> Outcome:
        # Ordinarily a narrate_only turn carries no tell, which is the point of it. The one
        # exception is the world's answer to a person the player looked for and who is not
        # here: there is no ref to hang a refusal on — that is exactly what is being said —
        # so the sentence rides here, and the narrator is fed a fact rather than left to
        # conjure somebody to satisfy the sentence (2026-09-19, item 29).
        said = " ".join(str(intent.params.get("not_here") or "").split())
        if said:
            return self._refuse(intent, said)
        return Outcome(intent_id=intent.id, op=intent.op, status="resolved",
                       tell="", because=intent.because)

    # provoke -----------------------------------------------------------------------------

    # --- calling on somebody at home ----------------------------------------------------
    #
    # docs/the-population.md "Built: shop hours and calling on people" and "Built: the
    # still-not-built list" (2026-09-27). The research that set the shape:
    #   * WHERE SOMEBODY LIVES IS KNOWLEDGE, not a map object: PF1e's gather information
    #     (Diplomacy, at least 1d4 hours canvassing, DC 10 for what is commonly known), and
    #     The Alexandrian's targeted investigation. Held as a `knows.home.<key>` tag on the
    #     character through the one applicator, like `knows.way-past-gate`.
    #   * A VISIT IS A KNOCK with two gates, as Stardew Valley's homes have: the hour
    #     (its doors keep times) and the relationship (two hearts for a bedroom). Out, and
    #     nobody answers; at home by day, the door opens to anybody not ill-disposed; in the
    #     night, they are woken — which costs regard, as U7's innkeeper "must be awoken" —
    #     and only a friend lets you in.
    #   * ONCE A FRIEND, THE DOOR STAYS OPEN: Stardew's bedroom, once opened at two
    #     hearts, "is permanently unlocked even if the heart meter goes below 2 hearts".
    #     Held as `bond.welcome.<key>` on the character; the one exception is somebody
    #     who has come to hate them, which Stardew's hearts cannot express.
    #   * THREE KINDS OF PERSON KEEP A HOME: somebody from the population; a keeper, who
    #     lives on the premises of a counter under a roof (Pierre, Belethor) and has a
    #     house of their own when the counter is a stall; and a character the world
    #     wrote, found by name in their own town.
    # A house is a place founded once, owned by them (`found_place`, origin "home"), off a
    # street of their town; from then on the home their day sends them to IS that house
    # (`residency.resolve` reads what they hold).
    HOME_DC = 10
    _NIGHT_SLOTS = frozenset({0, 1})
    _STREET_WORDS = ("lane", "back streets", "warrens", "streets", "green", "row", "well")
    # Breaking in: PF1e Core Rulebook. A house door is a good wooden door, locked: break DC
    # 18 in both Table 13-2 (Doors) and the Breaking Items table, which disagree for most
    # doors and agree for this one. Its lock is average: Disable Device DC 25, +10 without
    # thieves' tools. Noise has no rule; Perception's own DCs judge it — the sound of
    # battle is -10 and a whisper 15, +10 for a sleeping listener — so a door smashed in
    # is heard like a fight (0) and a lock picked like a whisper (15).
    DOOR_BREAK_DC = 18
    LOCK_DC = 25
    NO_TOOLS = 10
    HEARS_FORCE = 0
    HEARS_PICK = 15
    ASLEEP = 10
    CAUGHT_AT_IT = 20        # regard lost by a householder who catches the party at it

    def _callee_of_body(self, body) -> dict:
        from . import keepers
        from . import population

        rec = population.of_ref(self.scene, body.ref)
        wid = str(getattr(body, "world_entity_id", "") or "")
        kind = ("person" if rec is not None else "keeper" if keepers.is_keeper(wid)
                else "world" if wid else "person")
        key = rec["id"] if rec is not None else (wid if kind == "world" else body.ref)
        return {"key": key, "kind": kind, "rec": rec, "body": body,
                "entity": wid if kind == "world" else "", "name": body.name}

    def _callee(self, who: str):
        """Whom `who` means in this town, as {"key", "kind", "rec", "body", "entity",
        "name"} — or a string saying why nobody."""
        from . import places as places_mod
        from . import population
        from . import scope as scope_mod

        scene = self.scene
        body = scene.people.get(who)
        if body is not None and not body.is_pc:
            return self._callee_of_body(body)
        words = who.lower().split()
        if words and words[0] in ("her", "him", "them", "his", "their", "she", "he", "they"):
            # The pronoun is the person whose home the character last learned — "I ask
            # where the bread seller lives", then "I go to her house" — and failing that
            # whoever they last spoke with in this town. Measured live 2026-09-27: two
            # people met in the same minute, and "her" went to the opening's companion
            # instead of the bread seller whose house had just been asked after.
            pc = scene.pc()
            learned = [e.key.split(":", 1)[1] for e in (getattr(pc, "effects", None) or [])
                       if str(getattr(e, "key", "")).startswith("knows-home:")]
            for key in reversed(learned):
                got = self._callee_by_key(key)
                if got is not None:
                    return got
            met = [r for r in (scene.population or {}).values()
                   if r.get("last_met") is not None and r.get("home") == scene.location_id]
            if met:
                rec = max(met, key=lambda r: (int(r["last_met"]),
                                              int(r.get("last_seen") or 0),
                                              int(str(r["id"])[1:] or 0)))
                return self._callee_of_record(rec)
            return "Nobody the party has spoken with lives in this town."
        found = population.find(scene, who, world=self.world, log_miss=False)
        if found.scope == population.AMBIGUOUS:
            return population.question(found.people)
        if found.people:
            return self._callee_of_record(found.people[0])
        # A keeper or a character the world wrote, by the name they go by here.
        wanted = population._tokens(who)
        for a in scene.people.values():
            if a.is_pc or not getattr(a, "world_entity_id", None):
                continue
            if places_mod.location_of(str(a.at or "")) not in ("", scene.location_id):
                continue
            if wanted and population._fits(wanted, set(population._tokens(a.name))):
                return self._callee_of_body(a)
        if self.world is not None:
            for e in getattr(self.world, "entities", {}).values():
                if (getattr(e, "kind", "") == "CHARACTER"
                        and getattr(e, "parent_id", "") == scene.location_id
                        and scope_mod.matches(e, who)):
                    body = next((a for a in scene.people.values()
                                 if getattr(a, "world_entity_id", "") == e.id), None)
                    return {"key": e.id, "kind": "world", "rec": None, "body": body,
                            "entity": e.id, "name": str(e.name)}
        return f"Nobody the party has met answers to {who!r}."

    def _callee_of_record(self, rec) -> dict:
        from . import population

        body = self.scene.people.get(rec.get("ref") or "")
        return {"key": rec["id"], "kind": "person", "rec": rec, "body": body, "entity": "",
                "name": body.name if body is not None else population._the(rec["phrase"])}

    def _callee_by_key(self, key: str):
        rec = (self.scene.population or {}).get(key)
        if rec is not None:
            return (self._callee_of_record(rec)
                    if rec.get("home") == self.scene.location_id else None)
        body = self.scene.people.get(key)
        if body is not None:
            return self._callee_of_body(body)
        body = next((a for a in self.scene.people.values()
                     if getattr(a, "world_entity_id", "") == key), None)
        if body is not None:
            return self._callee_of_body(body)
        e = self.world.get(key) if self.world is not None else None
        if e is not None and getattr(e, "parent_id", "") == self.scene.location_id:
            return {"key": key, "kind": "world", "rec": None, "body": None, "entity": key,
                    "name": str(e.name)}
        return None

    def _lives_here(self, callee) -> bool:
        from . import keepers
        from . import places as places_mod
        from . import residency

        if callee["kind"] == "person":
            rec = callee["rec"]
            return (residency.mobility_of(rec) == "resident"
                    and rec.get("home") == self.scene.location_id)
        if callee["kind"] == "keeper":
            place = keepers.place_of(callee["body"].world_entity_id)
            return places_mod.location_of(place) == self.scene.location_id
        return True   # a world character was found in this town, or by their body here

    def _knows_home(self, pc, callee) -> tuple[bool, str]:
        """Whether the character knows where this person lives, learning it if they can.

        Known already (the tag); told, when the person is friendly with them; else asked
        around for, taking 10 on Diplomacy against DC 10 — at least 1d4 hours, and the
        hours are the world's roll. A character who could not find out that way is told
        so, and who might tell them."""
        from . import attitude as attitude_mod
        from .activeeffect import ActiveEffect
        from .dice import stack

        key = callee["key"]
        tag = f"knows.home.{key}"
        if pc.has_state(tag):
            return True, ""

        def learn(how: str) -> None:
            pc.apply_effect(ActiveEffect(
                name=f"knows where {callee['name']} lives", kind="knowledge",
                key=f"knows-home:{key}", source=f"home:{key}", origin=how,
                duration="until-dismissed", tags=(tag,)))

        body = callee["body"]
        if body is not None and attitude_mod.step_of(attitude_mod.of(body)) >= \
                attitude_mod.step_of("friendly"):
            learn("told")
            return True, "They had told you where they live."
        try:
            bonus = sum(m.value for m in stack(pc.skill_modifiers("diplomacy")))
        except Exception:
            bonus = 0
        if 10 + bonus < self.HOME_DC:
            return False, ("Nobody you ask around will say where they live. Somebody "
                           "who knows them might, or they might tell you themselves.")
        hours = self.dice.roll("1d4", label="asking around", visibility="hidden").total
        self.scene.advance(hours * 60)
        learn("asked around")
        return True, f"{hours} hour{'s' if hours != 1 else ''} of asking around finds out where they live."

    def _street_for_a_house(self):
        from . import places as places_mod

        outdoor = [p for p in self.places()
                   if not places_mod.is_indoors(p.id)
                   and places_mod.terrain_of(p.id) == places_mod.URBAN]
        roomy = [p for p in outdoor if len(places_mod.children_of(
            self.scene.founded, p.id)) < places_mod.MOST_CHILDREN]
        for words in self._STREET_WORDS:
            for p in roomy:
                if words in p.name.lower():
                    return p
        return roomy[0] if roomy else None

    def _embody_callee(self, callee):
        """The person called on is given a body if they have none: the one door
        everybody is made by (population.embody), or a spawn from the world's own
        character, exactly as the plan's `spawn` does it."""
        from . import npcs
        from . import population
        from . import scope as scope_mod

        if callee["body"] is not None:
            return callee["body"]
        if callee["kind"] == "person":
            body = population.embody(self.scene, callee["rec"]["phrase"], "guildhand",
                                     world=self.world, rec=callee["rec"])
        else:
            e = self.world.get(callee["entity"]) if self.world is not None else None
            role = scope_mod._role_of(e) if e is not None else ""
            pc = self.scene.pc()
            template = npcs.block_for(callee["entity"], [w for w in role.split() if w] or
                                      ["commoner"], int(getattr(pc, "level", 1) or 1),
                                      callee["name"])
            made = self._bring_in(template, name=callee["name"],
                                  from_entity_id=callee["entity"])
            body = self.scene.people.get(made[0]["ref"]) if made else None
        callee["body"] = body
        return body

    def _house_of(self, callee):
        """Their house if it has been founded: the place dict, or None. A keeper under a
        roof lives on the premises, and their counter's place is their home."""
        from . import keepers

        body = callee["body"]
        if callee["kind"] == "keeper" and body is not None:
            shop = keepers.place_of(body.world_entity_id)
            if keepers.lives_in(shop):
                return {"id": shop, "origin": "shop", "owner": body.ref}
        for p in self.scene.founded:
            if body is not None and p.get("owner") == body.ref and p.get("origin") == "home":
                return p
        return None

    def _home_of(self, callee):
        """Their house, founded the first time anybody calls: the Place."""
        from . import places as places_mod

        body = self._embody_callee(callee)
        if body is None:
            return None
        held = self._house_of(callee)
        if held is None:
            street = self._street_for_a_house()
            if street is None:
                return None
            handle = callee["name"]
            name = (f"{body.name}'s house" if body.name == getattr(body, "true_name", None)
                    or callee["kind"] != "person" else f"the house of {handle}")[:60]
            place = self.found_place(name, street, owner=body, origin="home")
            # Where they are by day, for a character the world wrote: where the party
            # first found them. A population record carries its own (`spot`).
            for p in self.scene.founded:
                if p.get("id") == place.id and callee["kind"] == "world":
                    p["work"] = body.at if not str(body.at or "").startswith(
                        place.id) else ""
            held = {"id": place.id}
        target = self._callee_place_now(callee)
        if target and target != body.at and body.ref not in self.scene.actors:
            self.scene.move(body.ref, target)
        return places_mod.find(self.places(), held["id"])

    def _callee_place_now(self, callee) -> str:
        """Where their day puts them now, as a place id ("" for somewhere unknown)."""
        from . import keepers
        from . import residency

        body = callee["body"]
        clock = self.scene.clock_minutes
        if callee["kind"] == "person":
            where = residency.whereabouts(callee["rec"], clock, self.world, self.scene.founded)
            return residency.place_for(where, callee["rec"])
        house = self._house_of(callee)
        if callee["kind"] == "keeper" and body is not None:
            shop = keepers.place_of(body.world_entity_id)
            if keepers.open_now(shop, clock, self.scene.founded) or keepers.lives_in(shop):
                return shop
            return (house or {}).get("id") or residency.offstage(self.scene.location_id,
                                                                 f"home-{body.ref}")
        # A character the world wrote keeps the plainest day: home by night and in the
        # evening's last slot, and by day wherever the party first found them.
        if house is None:
            return ""
        slot = residency.slot_of(clock)
        if residency.TEMPLATES["default"][slot] == residency.HOME or slot in (6,):
            return house["id"]
        return str(house.get("work") or "") or house["id"]

    def _op_call_on(self, intent: Intent, partial: dict) -> Outcome:
        from . import population
        from . import residency

        pc = self.scene.pc()
        if pc is None:
            return self._refuse(intent, "There is nobody to go calling.")
        callee = self._callee(str(intent.params["who"]))
        if isinstance(callee, str):
            return self._refuse(intent, callee)
        body = callee["body"]
        if intent.params.get("visit", True) and body is not None and body.ref in self.scene.actors:
            return self._refuse(intent, residency.sentence(
                f"{body.name} is here, with you; there is no need to go to their door."))
        if not self._lives_here(callee):
            line = (population.seen_line(callee["rec"], self.scene, self.world)
                    if callee["rec"] else f"{callee['name']} does not live in this town.")
            return self._refuse(intent, line + " They keep no house in this town.")
        knows, how = self._knows_home(pc, callee)
        if not knows:
            return self._refuse(intent, how)
        house = self._home_of(callee)
        if house is None:
            return self._refuse(intent, "There is no street here with room for a house.")
        bits = [how] if how else []
        effects = [{"kind": "call_on", "who": callee["key"], "house": house.id,
                    "street": house.parent}]
        if not intent.params.get("visit", True):
            where = (f"off {self._place_name(house.parent)}" if house.parent
                     else "where they work")
            bits.append(f"They live at {house.name}, {where}.")
            return Outcome(intent_id=intent.id, op="call_on", effects=effects,
                           tell=" ".join(bits), because=intent.because)
        let_in, said = self._knock(callee, house)
        bits.append(residency.sentence(said))
        effects[0].update(let_in=let_in, go=house.id if let_in else (house.parent or ""))
        if let_in:
            self._let_in.add(house.id)
        return Outcome(intent_id=intent.id, op="call_on", effects=effects,
                       tell=" ".join(b for b in bits if b), because=intent.because)

    def _at_their_door(self, intent, place: str):
        """None when the party may walk in; a refusal carrying the knock when not.

        Somebody's house, unless its door has been broken; a keeper's shop under a roof
        in the small hours, when the counter is shut and they are abed (a tavern or an
        inn never shuts)."""
        from . import places as places_mod
        from . import residency

        target = places_mod.find(self.places(), place)
        if target is None or target.id in self._let_in:
            return None
        pc = self.scene.pc()
        home = next((p for p in self.scene.founded if p.get("id") == target.id
                     and p.get("origin") == "home"), None)
        if home is not None:
            if home.get("door") == "broken" or (pc is not None and home.get("owner") == pc.ref):
                return None
            body = self.scene.people.get(str(home.get("owner") or ""))
            if body is None or body.has_state(states.TRAVELS_WITH_YOU):
                return None
            callee = self._callee_of_body(body)
        else:
            # A shop shut for the night (`shut_for_the_night`, the one test the exits
            # row asks too).
            keeper = self.shut_for_the_night(target)
            if keeper is None:
                return None
            callee = self._callee_of_body(keeper)
        let_in, said = self._knock(callee, target)
        if let_in:
            self._let_in.add(target.id)
            return None
        return self._refuse(intent, residency.sentence(said))

    def _place_name(self, place_id: str) -> str:
        from . import places as places_mod

        p = places_mod.find(self.places(), place_id)
        return p.name if p is not None else "the street"

    def _knock(self, callee, house) -> tuple[bool, str]:
        """Who answers the door, and whether it opens. (let in, what happened)."""
        from . import attitude as attitude_mod
        from . import population
        from . import residency
        from .activeeffect import ActiveEffect

        body = callee["body"]
        who = callee["name"]
        if body is None or body.at != house.id:
            if callee["rec"] is not None:
                elsewhere = population.seen_line(callee["rec"], self.scene, self.world)
            else:
                elsewhere = f"{who} is out at this hour."
            return False, f"Nobody answers at {house.name}. A neighbour says: {elsewhere}"
        pc = self.scene.pc()
        step = attitude_mod.step_of(attitude_mod.of(body))
        welcome = pc is not None and pc.has_state(f"bond.welcome.{callee['key']}") \
            and step > attitude_mod.step_of(attitude_mod.HOSTILE)
        night = residency.slot_of(self.scene.clock_minutes) in self._NIGHT_SLOTS
        if night:
            attitude_mod.nudge_regard(body, -3, "woken")
            if welcome or step >= attitude_mod.step_of("friendly"):
                let_in, said = True, (f"{who} is woken by the knocking, comes to the door "
                                      f"half dressed, and lets you in.")
            else:
                return False, (f"{who} is woken by the knocking and shouts through the "
                               f"door to come back in daylight. It does not open.")
        elif welcome or step >= attitude_mod.step_of("indifferent"):
            let_in, said = True, f"{who} opens the door and lets you in."
        else:
            return False, (f"{who} opens the door a crack, sees who it is, and will not "
                           f"let you in.")
        # Let in as a friend: the door stays open to them from now on.
        if pc is not None and step >= attitude_mod.step_of("friendly") and \
                not pc.has_state(f"bond.welcome.{callee['key']}"):
            pc.apply_effect(ActiveEffect(
                name=f"welcome at {house.name}", kind="bond",
                key=f"welcome:{callee['key']}", source=f"home:{callee['key']}",
                origin="let in as a friend", duration="until-dismissed",
                tags=(f"bond.welcome.{callee['key']}",)))
        return let_in, said

    # --- breaking in --------------------------------------------------------------------

    def _op_break_in(self, intent: Intent, partial: dict) -> Outcome:
        """Force a house door or pick its lock (PF1e: Strength against the door's break
        DC; Disable Device against the lock, trained only). Whoever is home may hear it,
        and so may anybody in the street; a householder who catches the party at it
        loses a great deal of regard, and a witnessed break-in is a crime — suspected the
        first time, wanted the next, the warning before the warrant (Skyrim's trespass
        warns before it fines)."""
        from . import places as places_mod
        from . import residency
        from .dice import Modifier
        from .sheet import IllegalSheet

        pc = self.scene.pc()
        if pc is None:
            return self._refuse(intent, "There is nobody to break in.")
        how = "pick" if str(intent.params.get("how") or "").lower().startswith("pick") \
            else "force"
        house, callee = self._door_to_break(str(intent.params.get("who") or ""))
        if house is None:
            return self._refuse(intent, callee)
        home = next((p for p in self.scene.founded if p.get("id") == house.id), None)
        if (home or {}).get("door") == "broken" or house.id in self._let_in:
            self._let_in.add(house.id)
            return Outcome(intent_id=intent.id, op="break_in",
                           effects=[{"kind": "call_on", "go": house.id}],
                           tell=f"The door of {house.name} is already open to you.",
                           because=intent.because)
        if how == "force":
            mods = [Modifier(pc.ability_mod("str"), "Strength")]
            dc, label = self.DOOR_BREAK_DC, f"Strength check — breaking down the door of {house.name}"
        else:
            try:
                mods = list(pc.skill_modifiers("disable device"))
            except IllegalSheet:
                return self._refuse(intent, f"{pc.name} has no training in picking locks "
                                            f"(Disable Device is trained only). The door "
                                            f"can still be forced.")
            tools = any("thieves' tools" in str(getattr(s, "base", "")).lower()
                        for s in pc.stock.values())
            dc = self.LOCK_DC + (0 if tools else self.NO_TOOLS)
            label = (f"Disable Device — picking the lock of {house.name}"
                     + ("" if tools else " (no thieves' tools)"))
        roll = self._roll_or_suspend(intent, pc, mods, label, dc, partial)
        opened = roll.total >= dc
        self.scene.advance(0, rounds=1)

        bits = []
        effects: list[dict] = [{"kind": "break_in", "house": house.id, "how": how,
                                "opened": opened}]
        if opened:
            if home is not None and how == "force":
                home["door"] = "broken"
            bits.append(f"The door of {house.name} gives." if how == "force"
                        else f"The lock of {house.name} turns.")
        else:
            bits.append(f"The door of {house.name} holds." if how == "force"
                        else f"The lock of {house.name} defeats {pc.name}.")
        # Who heard it: the householder, if home (asleep in the small hours), and anybody
        # standing in the street with the party.
        body = callee["body"] if isinstance(callee, dict) else None
        caught = []
        if body is not None and body.at == house.id and not body.is_down:
            dc_hear = self.HEARS_FORCE if how == "force" else self.HEARS_PICK
            if residency.slot_of(self.scene.clock_minutes) in self._NIGHT_SLOTS:
                dc_hear += self.ASLEEP
            try:
                heard = self.dice.d20(body.skill_modifiers("perception"),
                                      label=f"{body.name} listens", visibility="hidden")
            except Exception:
                heard = self.dice.d20([], label=f"{body.name} listens", visibility="hidden")
            if heard.total >= dc_hear:
                from . import attitude as attitude_mod

                before, after = attitude_mod.nudge_regard(body, -self.CAUGHT_AT_IT,
                                                          "caught breaking in")
                effects.append({"kind": "regard", "ref": body.ref, "from": before,
                                "to": after})
                caught.append(body.name)
                bits.append(f"{body.name} is awake to it, and comes to see.")
        street = [a for r, a in self.scene.actors.items()
                  if not a.is_pc and self.scene.conscious(r)
                  and not a.has_state(states.TRAVELS_WITH_YOU)]
        if street:
            caught.extend(a.name for a in street)
            bits.append("It is seen: " + ", ".join(a.name for a in street) + ".")
        if caught:
            bits.append(self._witnessed_break_in(pc, house, effects))
        if opened:
            self._let_in.add(house.id)
            effects.append({"kind": "call_on", "go": house.id})
        return Outcome(intent_id=intent.id, op="break_in", effects=effects,
                       rolls=[roll], dc=dc,
                       tell=" ".join(b for b in bits if b), because=intent.because)

    def _witnessed_break_in(self, pc, house, effects: list) -> str:
        from . import places as places_mod
        from .activeeffect import ActiveEffect

        town = places_mod.location_of(self.scene.at) or self.scene.location_id
        law = states.standing_with_the_law(pc, town)
        if law == "wanted":
            return ""
        if law == "suspected":
            pc.apply_effect(ActiveEffect(
                name="a warrant", kind="situation", key=states.wanted_tag(town),
                source=f"rule:break-in/{house.id}", origin=f"rule:break-in/{house.id}",
                duration="until-dismissed", tags=(states.wanted_tag(town),)))
            effects.append({"kind": "wanted", "town": town})
            return "Twice now: the watch will have a warrant out by morning."
        pc.apply_effect(ActiveEffect(
            name="a name on the watch's lips", kind="situation",
            key=states.suspected_tag(town), source=f"rule:break-in/{house.id}",
            origin=f"rule:break-in/{house.id}", duration="until-dismissed",
            tags=(states.suspected_tag(town),)))
        effects.append({"kind": "reported", "town": town})
        return "Somebody will be telling the watch."

    def _door_to_break(self, who: str):
        """(the house Place, the callee) — or (None, why not). By whose house it is, or the
        one house off the street the party is standing in."""
        from . import places as places_mod

        if who.strip():
            callee = self._callee(who)
            if isinstance(callee, str):
                return None, callee
            house = self._house_of(callee)
            if house is None:
                return None, (f"The party does not know where {callee['name']} lives. "
                              f"Ask around first.")
            return places_mod.find(self.places(), house["id"]), callee
        homes = [p for p in self.scene.founded if p.get("origin") == "home"
                 and p.get("parent") == self.scene.at]
        if len(homes) != 1:
            return None, ("Whose door? " + (
                "The houses here are " + ", ".join(p["name"] for p in homes) + "."
                if homes else "There is no house here the party knows."))
        body = self.scene.people.get(str(homes[0].get("owner") or ""))
        callee = self._callee_of_body(body) if body is not None else {
            "key": homes[0]["id"], "kind": "world", "rec": None, "body": None,
            "entity": "", "name": homes[0]["name"]}
        return places_mod.find(self.places(), homes[0]["id"]), callee

    def _op_provoke(self, intent: Intent, partial: dict) -> Outcome:
        """The player insults or slights somebody: their regard falls, and a seeded roll on
        their temper decides whether it comes to blows (rules/provocation.py).

        Measured before this existed (2026-09-25, the provoke script): a man insulted nine
        times never struck and no attitude moved — worse, every exchange still earned the
        +2 of a friendly word, so the insults made him like the player more. A blow is
        queued as his own `attack` with his fists, and `run` rolls it before the prose
        (`_their_first_blow`). Somebody who will not come to blows and is hostile turns
        their back: out of the conversation, which is state the engine holds.
        """
        from . import attitude as attitude_mod
        from . import provocation as prov

        target = self.scene.actors.get(intent.target or "")
        pc = self.scene.pc()
        if target is None or target.is_pc or target.is_down or pc is None:
            return Outcome(intent_id=intent.id, op="provoke", status="resolved",
                           tell="", because=intent.because)
        how = intent.params.get("how") or "insult"
        day = int(self.scene.clock_minutes) // (24 * 60)
        eff = attitude_mod._regard_effect(target)
        payload = dict(getattr(eff, "payload", None) or {}) if eff is not None else {}
        times = int(payload.get("provoked", 0)) if payload.get("provoked_day") == day else 0
        now = int(self.scene.clock_minutes)
        before, after = attitude_mod.nudge_regard(target, -prov.cost(how, times),
                                                  f"provoked: {how}")
        attitude_mod.set_regard(target, after, f"provoked: {how}",
                                payload={"provoked": times + 1, "provoked_day": day})
        # What provocation took is a grudge, and it comes back with time (`recover`).
        prov.note_grudge(target, before - after, now)
        self._provoked = getattr(self, "_provoked", set()) | {target.ref}
        step = attitude_mod.of(target)
        effects = [{"kind": "regard", "ref": target.ref, "from": before, "to": after},
                   {"kind": "provoked", "ref": target.ref, "how": how}]
        if self.scene.in_encounter:
            return Outcome(intent_id=intent.id, op="provoke", status="resolved",
                           effects=effects, tell=f"{target.name} takes it badly.",
                           because=intent.because)
        # Cooled after an outburst: it still stings, but they will not rise to it again
        # so soon (RimWorld's post-break reset; `settle_outbursts`).
        if prov.cooled(target, now):
            effects[-1]["cooled"] = True
            return Outcome(intent_id=intent.id, op="provoke", status="resolved",
                           effects=effects,
                           tell=f"{target.name} glares at you, but will not be drawn "
                                f"again so soon.", because=intent.because)
        chance = prov.strike_chance(self.scene, target, step)
        roll = self.dice.roll("1d100", label=f"{target.name} keeps their temper",
                              visibility="hidden")
        strikes = chance > 0 and roll.total <= round(chance * 100)
        effects[-1].update({"strikes": strikes, "chance": round(chance, 2),
                            "roll": roll.total})
        if strikes:
            prov.mark_outburst(target)
            tell = f"{target.name} has had enough."
        elif step == attitude_mod.HOSTILE and chance < prov.WILL_NOT_FIGHT:
            ended = self.end_talk(who=target)
            tell = (f"{target.name} turns their back on you and will have nothing more "
                    f"to do with you." + (f" {ended}" if ended else ""))
            tell += self._what_they_do_instead(target, effects)
        else:
            tell = attitude_mod.regard_said(target.name, before, after) \
                or f"{target.name} takes it badly."
        return Outcome(intent_id=intent.id, op="provoke", status="resolved",
                       effects=effects, tell=tell, because=intent.because)

    def _what_they_do_instead(self, target, effects: list) -> str:
        """A hostile person who will not swing does something the engine holds, chosen
        by their rolled life (rules/provocation.py): the gregarious turn the room, the
        orderly report the player to the watch, anyone else only turns away. Returns the
        tell's extra sentence."""
        from . import attitude as attitude_mod
        from . import places as places_mod
        from . import provocation as prov

        pc = self.scene.pc()
        if prov.axis_of(self.scene, target, "sociability") >= prov.TURNS_THE_ROOM_FROM:
            others = [a for r, a in self.scene.actors.items()
                      if not a.is_pc and a is not target and self.scene.conscious(r)]
            for a in others:
                b, n = attitude_mod.nudge_regard(a, -prov.SLIGHT, f"turned by {target.ref}")
                effects.append({"kind": "regard", "ref": a.ref, "from": b, "to": n})
            if others:
                return f" {target.name} makes sure everybody here hears what you said."
        if (pc is not None and prov.axis_of(self.scene, target, "order") >= prov.REPORTS_FROM
                and places_mod.terrain_of(self.scene.at) == places_mod.URBAN):
            town = places_mod.location_of(self.scene.at) or self.scene.location_id
            if not states.standing_with_the_law(pc, town):
                pc.apply_effect(ActiveEffect(
                    name="a name on the watch's lips", kind="situation",
                    key=states.suspected_tag(town), source=f"rule:provocation/{target.ref}",
                    origin=f"rule:provocation/{target.ref}", duration="until-dismissed",
                    tags=(states.suspected_tag(town),)))
                effects.append({"kind": "reported", "ref": target.ref, "town": town})
                return f" {target.name} goes to find the watch."
        return ""

    # say ---------------------------------------------------------------------------------

    # A free action in 1e, so nothing is rolled and no time passes. What it produces is a
    # TELL, and that is the whole point: before this op existed, speech resolved to
    # `narrate_only`, a narrate_only turn carries no tells, and a prose call with no tells
    # to dress is the turn that came back as the holding line all through the 2026-09-08
    # session. The words are carried into the tell so the narrator dresses what the player
    # actually said instead of writing them a different line.
    _SAID_CAP = 400

    def _op_say(self, intent: Intent, partial: dict) -> Outcome:
        words = " ".join(str(intent.params.get("words") or "").split())[:self._SAID_CAP]
        speaker = self.scene.actors.get(intent.actor) or self.scene.pc()
        who = speaker.name if speaker is not None else "somebody"
        heard = self.scene.actors.get(str(intent.params.get("to") or ""))
        if not words:
            # Nothing was actually said. A tell claiming otherwise would be a mechanic
            # the engine did not decide.
            return Outcome(intent_id=intent.id, op=intent.op, status="resolved",
                           tell="", because=intent.because)
        # Speaking in a room with one other person in it is speaking to them. Decided
        # here, once, rather than asked of the model: the injector that makes this op
        # names a `to` only when the player's words name somebody.
        # Not when the plan named somebody who is not here: measured live 2026-09-27, a
        # question put to the bread seller went to the one other person in the room.
        if (heard is None and speaker is not None and speaker.is_pc
                and not str(intent.params.get("to") or "").strip()):
            others = [a for r, a in self.scene.actors.items()
                      if not a.is_pc and self.scene.conscious(r)]
            if len(others) == 1:
                heard = others[0]
        at = f" to {heard.name}" if heard is not None else ""
        # Quoted speech is quoted; reported speech is reported. "I ask her if she
        # wants to pay for my services" is not a sentence the character said, and a
        # tell that quotes it hands the narrator the player's own framing to put in
        # somebody's mouth.
        said = (f'{who} says{at}: "{words}"' if intent.params.get("quoted")
                else f"{who} speaks{at}, to the effect that {words}")
        effects = [{"kind": "said", "who": intent.actor or "",
                    "to": heard.ref if heard is not None else "",
                    "words": words}]
        # A conversation, and what it does to the standing between them. Addressing
        # somebody opens it; being addressed by them opens it from their side. The
        # exchange counts towards regard (`attitude.talked_today`), capped per day,
        # and the tell says so only when a step is crossed — the third law: the
        # narrator hears the change in words, never a number.
        from . import attitude as attitude_mod

        bits = [said]
        if heard is not None and speaker is not None and speaker.is_pc \
                and not heard.is_pc:
            opened = self.join_talk(heard, how="you spoke to them")
            if opened:
                bits.append(opened)
            day = int(self.scene.clock_minutes) // (24 * 60)
            # Not for an exchange that was an insult: the provocation already moved
            # their regard, and the friendly word's +2 made nine insults warm a man up
            # (measured 2026-09-25).
            if (not self.scene.in_encounter
                    and heard.ref not in getattr(self, "_provoked", set())
                    and attitude_mod.step_of(attitude_mod.of(heard))
                    > attitude_mod.step_of(attitude_mod.HOSTILE)
                    and attitude_mod.talked_today(heard, day)):
                before, after = attitude_mod.nudge_regard(
                    heard, attitude_mod.REGARD_PER_TALK, "talk")
                effects.append({"kind": "regard", "ref": heard.ref,
                                "from": before, "to": after})
                warmed = attitude_mod.regard_said(heard.name, before, after)
                if warmed:
                    bits.append(warmed)
        elif speaker is not None and not speaker.is_pc and heard is not None \
                and heard.is_pc:
            opened = self.join_talk(speaker, how="they spoke to you")
            if opened:
                bits.append(opened)
        return Outcome(
            intent_id=intent.id, op=intent.op, status="resolved",
            effects=effects, tell=" ".join(bits), because=intent.because)

    # check ------------------------------------------------------------------------------

    def _op_check(self, intent: Intent, partial: dict) -> Outcome:
        from .sheet import IllegalSheet

        actor = self.scene.actors[intent.actor]
        skill = intent.params["skill"]
        # A trained-only skill the character has no ranks in resolves as a refusal, not
        # an exception. Measured live: a player toggled their class's blood armament out
        # of combat, the spoken path invited the model to dress it as a Knowledge
        # (Arcana) check, and `skill_modifiers` raised straight through the turn —
        # "cannot attempt knowledge (arcana) untrained" cost the whole action. The rule
        # is right (1e knowledge checks are trained-only); the crash is not. Nothing is
        # rolled, the player is told why, and the turn survives.
        try:
            mods = actor.skill_modifiers(skill)
        except IllegalSheet as exc:
            return Outcome(
                intent_id=intent.id, op="check", effects=[],
                tell=f"{exc}. Nothing is rolled.", because=intent.because)
        opposed = intent.params.get("opposed_by")

        # The opposing side is rolled first and kept in `partial`, so the player's prompt
        # is fully formed before we suspend and so a resume never re-rolls it.
        opposing_roll: Roll | None = None
        if opposed:
            if "opposed_roll" in partial:
                opposing_roll = _roll_from_dict(partial["opposed_roll"])
            else:
                other = self.scene.actors[opposed["ref"]]
                opposing_roll = self.dice.d20(
                    other.skill_modifiers(opposed["skill"]),
                    label=f"{other.name} {opposed['skill'].title()}",
                    visibility="hidden",
                )

        level = actor.level if actor.is_pc else 1
        # Talking somebody round is a rule with a table behind it, so the DC is the
        # engine's and never the plan's (`rules/attitude.py`). A `check` naming a subject
        # with `target` and a skill that moves the track is the ordinary way to change a
        # mind — it is what the `condition` refusal has been telling the model to do
        # since stage 8, while nothing on this side did anything with it.
        swayed = self._sway_subject(intent, skill)
        if swayed is not None and (refusal := self._sway_refusal(intent, actor, swayed, skill)):
            return refusal
        # First aid (Lane C, `rules/firstaid.py`): a Heal check aimed at somebody dying
        # is the rulebook's DC 15 to make them stable, whatever DC the plan wrote.
        from . import firstaid

        patient = firstaid.patient_of(self, intent) if not opposed else None
        if patient is not None:
            resolved_dc = dc_mod.ResolvedDC(value=firstaid.DC, band=None)
        elif opposed:
            target = opposing_roll.total
            resolved_dc = dc_mod.ResolvedDC(value=target, band=None)
            if intent.params.get("circumstance"):
                c = intent.params["circumstance"]
                resolved_dc.circumstance = dc_mod.CIRCUMSTANCE[c["value"]]
                resolved_dc.circumstance_why = c.get("why", "") or c["value"]
        elif swayed is not None:
            from . import attitude as attitude_mod

            resolved_dc = dc_mod.ResolvedDC(
                value=(attitude_mod.influence_dc(swayed) if skill == "diplomacy"
                       else attitude_mod.intimidate_dc(swayed)), band=None)
        else:
            resolved_dc = dc_mod.resolve(
                intent.params.get("dc"), level, intent.params.get("circumstance")
            )

        roll = self._roll_or_suspend(
            intent, actor, mods,
            label=f"{skill.title()} check",
            dc=resolved_dc.final,
            partial=partial,
            extra_partial={"opposed_roll": opposing_roll.as_dict()} if opposing_roll else {},
            # On an opposed check the number to beat IS the opponent's roll, made in
            # secret a few lines above. Showing it hands the player the guard's
            # Perception result before they roll their Stealth — the one case with no
            # play argument at all, because it is not a difficulty they could know, it
            # is the outcome of somebody else's hidden die.
            dc_shown=not opposed,
        )

        margin = roll.total - resolved_dc.final
        verdict = "success" if margin >= 0 else "failure"
        rolls = [roll] + ([opposing_roll] if opposing_roll else [])

        if opposed:
            other = self.scene.actors[opposed["ref"]]
            tell = (
                f"{actor.name} beats {other.name}'s {opposed['skill']} by {margin}."
                if verdict == "success" else
                f"{other.name}'s {opposed['skill']} beats {actor.name} by {-margin}."
            )
        else:
            tell = (
                f"{actor.name} makes the {skill} check by {margin}."
                if verdict == "success" else
                f"{actor.name} misses the {skill} check by {-margin}."
            )
        if verdict == "success":
            # A check beaten is a challenge overcome, and it pays — the number to beat
            # being the DC, or on an opposed check the other side's own roll.
            beaten = (opposing_roll.total if opposing_roll else resolved_dc.final)
            tell += self.reward_check(actor, skill, beaten)

        effects: list[dict] = []
        if patient is not None:
            aided, effects = firstaid.settle(actor, patient, verdict == "success")
            tell += aided
        if swayed is not None:
            moved_tell, effects = self._sway(actor, swayed, skill, margin,
                                             intent.because)
            # The margin has already been said; what the player is told about the person
            # is how they now feel, which is the only part of this a character could
            # see. No step count, no DC — the third law.
            tell = f"{tell} {moved_tell}".strip()

        return Outcome(
            intent_id=intent.id, op="check", rolls=rolls, dc=resolved_dc.as_dict(),
            verdict=verdict, margin=margin, effects=effects, tell=tell,
            because=intent.because,
        )

    # --- talking somebody round ----------------------------------------------------------

    def _sway_subject(self, intent: Intent, skill: str):
        """The creature a social check is aimed at, or None if this is not one.

        A `check` with a `target` and a skill that moves the track. Everything else — a
        Diplomacy check at a band the GM named, a Climb, an opposed Bluff — resolves
        exactly as it did, which is what keeps this additive.
        """
        from . import attitude as attitude_mod

        if skill not in attitude_mod.LEVERS or intent.params.get("opposed_by"):
            return None
        refs = [r for r in intent.targets() if r and r != intent.actor]
        return self.scene.actors.get(refs[0]) if refs else None

    def _sway_refusal(self, intent: Intent, actor, target, skill: str):
        """Why this attempt does not happen at all, as an outcome. Or None.

        "You cannot use Diplomacy to influence a given creature's attitude more than once
        in a 24 hour period" — the Core Rulebook's own limit, and the thing that stops a
        player rolling until the dice agree with them. Intimidate has no such limit in
        the book and is not given one here; what it has instead is a target who ends up
        unfriendly, which is the book's own price.
        """
        from . import attitude as attitude_mod

        if skill != "diplomacy":
            return None
        last = self.scene.swayed.get(target.ref)
        if last is None or self.scene.clock_minutes - int(last) >= attitude_mod.COOLDOWN_MINUTES:
            return None
        return Outcome(
            intent_id=intent.id, op="check", rolls=[], effects=[],
            tell=(f"{target.name} has heard {actor.name} out once today and will not "
                  f"hear it again. Come back tomorrow, or find another way."),
            because=intent.because)

    def _sway(self, actor, target, skill: str, margin: int, because: str):
        """Move the target along the track, and say how they now feel.

        The book, and nothing but: Diplomacy shifts one step plus one per 5 over, two at
        most, and costs a step on a failure by 5 or more; the shift lasts 1d4 hours.
        Intimidate buys `1d6 x 10` minutes of friendliness on a success and nothing on a
        failure. Both land through `_set_attitude`, which is the one applicator.
        """
        from . import attitude as attitude_mod

        was = attitude_mod.of(target)
        # What the check does to the standing between them, over and above the shift
        # it buys for the hour (`rules/attitude.py`, regard): a success is remembered
        # by the step, a bad failure costs, and being cowed is resented.
        regard_effects: list[dict] = []

        def _remember(delta: int) -> None:
            before, after = attitude_mod.nudge_regard(target, delta, f"{skill} check")
            regard_effects.append({"kind": "regard", "ref": target.ref,
                                   "from": before, "to": after})

        if skill == "intimidate":
            if margin < 0:
                return f"{target.name} does not scare.", []
            minutes = self.dice.roll(attitude_mod.INTIMIDATE_DICE,
                                     label="cowed for", visibility="hidden").total * 10
            now, rounds = attitude_mod.COMES_ALONG, _to_rounds(minutes, "minute")
            _remember(-attitude_mod.REGARD_RESENTMENT)
        else:
            # The attempt is spent whether or not it worked: the limit is on trying.
            self.scene.swayed[target.ref] = int(self.scene.clock_minutes)
            steps = attitude_mod.steps_for(margin)
            now = attitude_mod.moved(was, steps)
            if steps < 0:
                _remember(-attitude_mod.REGARD_LOST_ON_FAILURE)
            elif steps > 0:
                _remember(attitude_mod.REGARD_PER_STEP * steps)
            if not steps or now == was:
                return attitude_mod.said(target.name, was, was), regard_effects
            hours = self.dice.roll(attitude_mod.SHIFT_DICE, label="for",
                                   visibility="hidden").total
            rounds = _to_rounds(hours, "hour")
        cond = self._set_attitude(target, now, rounds, because or f"{skill} check")
        return (attitude_mod.said(target.name, was, now),
                [{"ref": target.ref, "kind": "condition", "condition": now,
                  "rounds_left": cond.rounds_left}] + regard_effects)

    # save --------------------------------------------------------------------------------

    def _op_save(self, intent: Intent, partial: dict) -> Outcome:
        actor = self.scene.actors[intent.actor]
        save = intent.params["save"]
        mods = actor.save_modifiers(save)
        level = actor.level if actor.is_pc else 1
        resolved_dc = dc_mod.resolve(intent.params["dc"], level)

        roll = self._roll_or_suspend(
            intent, actor, mods, label=f"{SAVES[save]} save",
            dc=resolved_dc.final, partial=partial,
        )

        # The face decides before the total (CRB p.180; `dice.d20_succeeds`). Until
        # 2026-09-28 this read `margin >= 0` alone, so a natural 20 short of the DC failed
        # and a natural 1 over it passed. The margin is clamped to agree with the verdict,
        # as the manoeuvre path does, so nothing downstream reads "succeeded by -3".
        margin = roll.total - resolved_dc.final
        natural = natural_said(roll, resolved_dc.final)
        if d20_succeeds(roll, resolved_dc.final):
            verdict, margin = "success", max(margin, 0)
        else:
            verdict, margin = "failure", min(margin, -1)
        branch = intent.params.get("on_success" if verdict == "success" else "on_failure") or {}

        effects: list[dict] = []
        made = "makes" if verdict == "success" else "fails"
        tell_bits = [
            f"{actor.name} {made} the {SAVES[save]} save {natural}." if natural else
            f"{actor.name} makes the {SAVES[save]} save by {margin}."
            if verdict == "success" else
            f"{actor.name} fails the {SAVES[save]} save by {-margin}."
        ]

        # Evasion, and the shape of the rule is why it is read HERE rather than at the
        # top: it is about "an attack that normally deals half damage on a successful
        # save", and the only thing that knows whether this was such an attack is the
        # branch — a `save` whose success branch says `damage: "half"`. Nothing else in
        # the app can tell a fireball from a flat Reflex save against a closing door.
        #
        #   evasion           "If she makes a successful Reflex saving throw against an
        #                     attack that normally deals half damage on a successful
        #                     save, she instead takes no damage."
        #   improved evasion  "...she still takes no damage on a successful Reflex
        #                     saving throw ... henceforth she takes only half damage on
        #                     a failed save."
        #
        # Both clauses of the armour and helpless restrictions live in
        # `classfeatures.evades`, so this reads one answer.
        from . import classfeatures

        evasion = classfeatures.evades(actor) if save == "ref" else ""
        halves_on_success = str(
            (intent.params.get("on_success") or {}).get("damage") or "").strip().lower() == "half"
        dmg = branch.get("damage")
        if dmg and evasion and halves_on_success and verdict == "success":
            # Nothing at all, and the tell says which rule did it so the narrator can
            # write somebody diving clear rather than a number being skipped.
            tell_bits.append(f"{actor.name} takes nothing: they got clear of it entirely.")
            dmg = None
        elif dmg and evasion == "improved" and halves_on_success and verdict == "failure":
            base = str(dmg)
            dmg_roll = self.dice.roll(base, label="damage", visibility="hidden")
            hit = self._apply_damage(actor, max(0, dmg_roll.total // 2),
                                     branch.get("type", "untyped"))
            effects.append(hit)
            tell_bits.append(
                f"{actor.name} takes {hit['amount']} ({hit['type']}, halved — they got "
                f"part of the way clear)"
                + (f" — {hit['note']}." if hit["note"] else "."))
            dmg = None
        if dmg:
            half = str(dmg).strip().lower() == "half"
            if half:
                # "half" on a success means half of what the failure branch dealt.
                base = (intent.params.get("on_failure") or {}).get("damage")
                if base:
                    dmg_roll = self.dice.roll(str(base), label="damage", visibility="hidden")
                    amount = max(0, dmg_roll.total // 2)
                    hit = self._apply_damage(actor, amount, branch.get("type", "untyped"))
                    effects.append(hit)
                    tell_bits.append(
                        f"{actor.name} takes {hit['amount']} ({hit['type']}, halved)"
                        + (f" — {hit['note']}." if hit["note"] else ".")
                    )
            else:
                dmg_roll = self.dice.roll(str(dmg), label="damage", visibility="hidden")
                hit = self._apply_damage(actor, dmg_roll.total,
                                         branch.get("type", "untyped"))
                effects.append(hit)
                tell_bits.append(
                    f"{actor.name} takes {hit['amount']} {hit['type']} damage"
                    + (f" ({hit['note']})." if hit["note"] else ".")
                )

        cond = branch.get("condition")
        if cond:
            actor.add_condition(cond, branch.get("rounds"), source=intent.because)
            effects.append({"ref": actor.ref, "kind": "condition", "condition": cond})
            tell_bits.append(f"{actor.name} is {cond}.")

        crossed = self._hp_state_effects(actor)
        effects.extend(crossed)

        return Outcome(
            intent_id=intent.id, op="save", rolls=[roll], dc=resolved_dc.as_dict(),
            verdict=verdict, margin=margin, effects=effects,
            tell=" ".join(tell_bits) + self._hp_state_tell(crossed),
            because=intent.because,
        )

    # attack -------------------------------------------------------------------------------

    def _op_attack(self, intent: Intent, partial: dict) -> Outcome:
        """An attack, resolved one stage at a time.

        The PC rolls their own to-hit *and* their own damage, so a single attack can
        suspend up to three times (attack, crit confirmation, damage) and a full attack
        once more per iterative. All of the progress lives in `partial`, which survives
        the round trip through the dice popup.

        The engine still owns every number: the player supplies faces, never modifiers.
        """
        actor = self.scene.actors[intent.actor]
        targets = intent.targets()
        if not targets:
            return self._refuse(intent, "The attack names nobody to hit, so nothing is rolled.")
        if targets[0] not in self.scene.actors:
            # Defensive: resolution should never meet a ref that validation passed, but a
            # correction applied after validation once made that untrue and the engine
            # raised KeyError as a 500. An IntentError is recoverable; a KeyError is not.
            raise IntentError(
                f"attack: {targets[0]!r} is not on the board at resolution time",
                "refs",
            )
        defender = self.scene.actors[targets[0]]
        # The move's rule, for a swing. `validate` asked whether they could attack
        # before the list began; an attack of opportunity spliced in front of an
        # earlier intent in the same list can drop them since. Measured 2026-09-27:
        # the player's AoO put a thug stooping for his sap unconscious, the give said
        # "never picks up the sap", and the swing queued behind it still rolled.
        if (partial.get("attack_state") is None and self.scene.in_encounter
                and not intent.params.get("reaction")
                and (actor.is_down or actor.blocking_key("attack"))):
            why = (actor.blocking_condition() or "down").lower()
            return Outcome(
                intent_id=intent.id, op="attack", status="prevented",
                effects=[{"ref": actor.ref, "kind": "attack_stopped", "why": why}],
                tell=f"{actor.name} is {why} and never swings.",
                because=intent.because)
        # A second blow behind one that closed the distance (`_drive` marks it): a move
        # action and a standard action leave ONE attack — "the only movement you can take
        # during a full attack is a 5-foot step" (aonprd.com/Rules.aspx?ID=145).
        if partial.get("attack_state") is None and intent.params.get("after_close"):
            return self._refuse(
                intent, f"{actor.name} closed the distance this turn, and a move leaves "
                        f"time for one blow, already struck. Nothing more is rolled.")
        # Two live people and no word from the player about which: nobody chooses for
        # them. `judgement.check_the_target` parks the candidates here, and the refusal
        # is prose on the page (Inform's check rulebook), never a lost turn.
        undecided = [r for r in (intent.params.get("undecided") or [])
                     if r in self.scene.actors]
        if len(undecided) >= 2:
            names = [self.scene.actors[r].name for r in undecided]
            asked = ", ".join(names[:-1]) + f" or {names[-1]}"
            return self._refuse(
                intent, f"Which of them — {asked}? Say who, and the blow follows.")
        weapon_key = (intent.params.get("weapon") or actor.wielded_key()).lower()
        # The floor under validate's reach check, for the lists it could not answer: a
        # move earlier in the list that fell short, a push that put the target out of
        # reach, an attack of opportunity that dropped the mover before they arrived.
        # Printed, not raised — by now nobody is listening for a retry. Asked before
        # anybody is drawn in: a blow that cannot land does not make a bystander a
        # combatant. And only where a blow will land now: inside a running fight, or a
        # coup de grace (resolved on the spot, fight or none). A swing that opens a
        # fight is deferred below and rolls nothing, so there is no blow to measure.
        if (partial.get("attack_state") is None and not self._battle_joined
                and (self.scene.in_encounter or intent.params.get("coup_de_grace"))):
            out_of_reach = self._reach_refusal(intent, actor, defender, weapon_key,
                                               voice="tell")
            if out_of_reach:
                return self._refuse(intent, out_of_reach)
        # A blow given or taken ends being a bystander. The one place besides
        # `join_fight` that lifts the tag, and it lifts it BEFORE the encounter forms so
        # the sides are drawn with both of them in.
        actor.remove_condition(states.BYSTANDER_KEY)
        defender.remove_condition(states.BYSTANDER_KEY)
        # A blow at the dead. `redirect_attacks_off_corpses` lets it stand on purpose —
        # "kicking the fallen is a thing a player may genuinely mean" — so it happens,
        # and there is nothing in it to roll: the player is not handed a d20 against a
        # corpse, the insult the manoeuvre path was fixed for too. A manoeuvre is left to
        # that path, which already answers a corpse with an automatic success.
        if defender.has_state("state.down.dead") and not intent.params.get("manoeuvre"):
            return Outcome(
                intent_id=intent.id, op="attack",
                tell=f"{defender.name} is already dead; the blow falls on a corpse.",
                because=intent.because)
        # A coup de grâce is not a fight being started (tests/test_battle_gate.py), so it
        # never meets the gate below: finishing a bound prisoner opens no battle, and the
        # blow is resolved on the spot, never deferred. `rules/coup_de_grace.py`.
        coup = bool(intent.params.get("coup_de_grace"))
        # Whether the one struck can tell who struck them (owner, Q34, for swords and
        # spells alike): a hidden attacker sniping from ten feet or more who keeps hidden
        # opens no fight and costs no attitude — `attitude.perceived` carries the rule and
        # its sources. Asked once, on the first entry, and kept in the attack's state, so
        # a resume from the dice popup never rolls the Stealth contest again.
        from . import attitude as attitude_mod

        held = partial.get("attack_state")
        sniping: list = []
        seen = (bool(held.get("seen", True)) if held is not None
                else attitude_mod.perceived(self, actor, defender, rolls=sniping))
        # The moment of first violence opens the battle and stops there. Measured in
        # play (2026-08-27): a spoken turn spawned an opponent, began the encounter,
        # swung, confirmed a critical, killed, ended the fight and paid out XP — an
        # entire war inside one narrated paragraph, the map never shown and the player
        # never once at the combat panel. So an attack that finds no fight running, or
        # one riding the same batch that started the fight, is *deferred*: the
        # encounter forms (initiative, sides, the grid laid), the tell announces that
        # battle is joined, and the swing itself is the player's to declare on their
        # own first combat turn. A swing at somebody already down opens nothing — one
        # living combatant is no encounter — and resolves as the mercy stroke it is.
        if partial.get("attack_state") is None and not coup and seen:
            opened = False
            if not self.scene.in_encounter:
                opened = self._ensure_encounter(intent.actor, intent.target)
            elif intent.target in self.scene.actors and not any(
                    intent.target in refs for refs in self.scene.sides.values()):
                # Swinging at a bystander brings them into the fight, and their kind
                # with them.
                self.join_fight(intent.target)
                self.rally(intent.target)
            if opened or self._battle_joined:
                self._battle_joined = True
                # The initiator keeps the action they declared — the rule
                # _ensure_encounter has always applied, now honoured whichever door
                # opened the fight. Without this, a GM-proposed begin_encounter left
                # the turn on the initiative winner and the hand-over gave the other
                # side the first swing the announcement had just promised the player.
                for i, (ref, _) in enumerate(self.scene.initiative):
                    if ref == intent.actor:
                        self.scene.turn = i
                        self.scene.acted.add(intent.actor)
                        break
                # The other side, not everyone in the room: the tell named the
                # bystanders as people squared off against.
                mine = next((s for s, refs in self.scene.sides.items()
                             if intent.actor in refs), None)
                foes = [self.scene.actors[r].name
                        for s, refs in self.scene.sides.items() if s != mine
                        for r in refs if r in self.scene.actors
                        and not self.scene.actors[r].is_down]
                return Outcome(
                    intent_id=intent.id, op="attack",
                    # The declared params ride along, so the initiator's blow that
                    # `_their_first_blow` rolls is the one declared — the bow, not
                    # whatever is in hand (a shortbow shot was re-rolled as a melee
                    # swing and spiked by Thorn Body when this was missing).
                    effects=[{"ref": actor.ref, "kind": "battle_joined",
                              "target": defender.ref,
                              "params": dict(intent.params or {})}],
                    tell=(f"Battle is joined: {actor.name} squares off against "
                          f"{', '.join(foes) or defender.name}. Nothing has landed "
                          f"yet — the first blow is still to be struck."),
                    because=intent.because)
        if not coup and seen:
            self._ensure_encounter(intent.actor, intent.target)
        weapon = actor.weapon(weapon_key)
        # An improvised weapon IS the object: the tell names the chunk of wood, not
        # "improvised weapon", and the object leaves the hand for the ground below
        # (or the target's feet, thrown) when the swing is done.
        thrown_thing = str(intent.params.get("item") or "").strip() if weapon_key == "improvised" else ""
        if thrown_thing:
            weapon = dict(weapon, name=thrown_thing)
        # A granted strike exists only while its toggle is formed. Refused here with
        # the forming ability's own name, because a swing with a weapon you are not
        # wearing is not a miss — it is a turn that should never have been declared.
        # (A plain unarmed strike never reaches this: `Actor.weapon` only returns the
        # granted weapon when the ask named it or the toggle holds.)
        if weapon.get("granted_by") and not actor.has_condition(weapon["granted_by"]):
            return self._refuse(
                intent, f"The {weapon['granted_by']} is not formed, so there is nothing "
                        f"to swing. {weapon.get('formed_with', 'Its forming ability')} "
                        f"forms it, as a free action.")
        full = bool(intent.params.get("full_attack"))
        power = bool(intent.params.get("power_attack"))
        # Which kind of damage this swing deals: the weapon's own, unless the swing was
        # declared the other way (`lethality`), which costs the -4 `attack_modifiers`
        # charges. Measured 2026-09-27 before this was read: a punch took a thug from 13
        # to 4 hit points and a thug's sap took the player from 9 to 1, nonlethal 0 both
        # times — `tables.WEAPONS` had marked both non-lethal since the slice and
        # nothing had ever asked.
        usual = weapons_mod.lethality_of(weapon)
        lethality = str(intent.params.get("lethality") or usual)
        pulled = usual == "lethal" and lethality == "nonlethal"

        if coup:
            from . import coup_de_grace as coup_mod

            why = coup_mod.refusal(actor, defender, weapon,
                                   self._gap_ft(actor, defender))
            if why:
                return self._refuse(intent, why)
            # One blow is the whole full-round action: no iteratives, and no manoeuvre
            # riding it — a trip is not a way to finish somebody.
            full = False
        elif intent.params.get("manoeuvre"):
            return self._resolve_maneuver(intent, actor, defender, weapon_key, partial)

        flat_footed = self._flat_footed(defender)
        # A creature floundering in water is easier to hit and keeps no guard: the book
        # gives its opponents +2 and takes its Dexterity off its own AC. Both are facts
        # about the DEFENDER's footing, so they are read here where the defender is known
        # and applied to the number being rolled against — the same reasoning the cover
        # block below states, and for the same reason: everything that reads an AC should
        # see the real one.
        wet_defender = defender.water_row()
        flounders = wet_defender and water.loses_dex_to_ac(wet_defender)
        target_ac = defender.ac(against=weapon["category"],
                                flat_footed=flat_footed or bool(flounders))
        worn_ac = target_ac
        ac_note = f"AC {target_ac}" + (" (flat-footed)" if flat_footed else "")
        if wet_defender:
            against = water.bonus_against(wet_defender)
            if against:
                target_ac -= against
                ac_note += f", floundering in the water"

        # What the board is worth to the defender. Added to the number being rolled
        # against rather than taken off the attack roll: the two are the same arithmetic
        # for whether a blow lands and are not the same fact, and everything that reads
        # an AC — the panel, the tell, a spell that cares — should see the real one.
        from . import position as position_mod

        if position_mod.cover_of(self.scene, actor, defender) == "total":
            return self._refuse(
                intent,
                f"{defender.name} is behind total cover: there is no line to them from "
                f"where {actor.name} is standing.")
        cover_mods = position_mod.ac_mods(self.scene, actor, defender)
        if cover_mods:
            target_ac += sum(m.value for m in cover_mods)
            ac_note += " with " + ", ".join(m.source for m in cover_mods)
        # What the water and the board added, kept apart so a touch attack below can
        # stand them on the touch AC instead: floundering and cover are about where the
        # defender is, not about what they wear.
        footing = target_ac - worn_ac

        state = partial.get("attack_state") or {"i": 0, "stage": "attack", "rolls": [],
                                                "effects": [], "tells": []}
        if held is None:
            state["seen"] = seen
            state["rolls"].extend(sniping)
        # (weapon, iteration) per swing. One weapon for a character; for a monster, the
        # whole printed option — an owlbear's claw, claw, bite (`Actor.attack_plan`).
        sequence = actor.attack_plan(weapon_key, full)
        # One swing at a stated iterative. The combat panel lets a Blood Bender replace
        # any attack in a full attack with an ability, so the remaining weapon swings
        # arrive one op each, still carrying their own -5/-10 — a mixed full attack
        # whose swings all rolled at full BAB would be the panel quietly buffing the
        # class it was built for.
        it = intent.params.get("iteration")
        if it is not None and not full and not coup:
            whole = actor.attack_plan(weapon_key, True)
            sequence = [whole[min(int(it), len(whole) - 1)]]
        if coup:
            sequence = sequence[:1]
            # No roll to hit and a critical by right. Set once, on first entry: the
            # state rides every suspension, and a resume must not reset a damage stage
            # the player is halfway through rolling.
            if state["i"] == 0 and state["stage"] == "attack" and not state["rolls"]:
                state["stage"] = "damage"
                state["crit"] = True
                state["hit_total"] = None
                state["tells"].append(
                    f"{actor.name} stands over {defender.name} and delivers a coup de "
                    f"grâce: no roll to hit, and a critical hit by right.")

        # Swift Strikes: an always-active passive, never an ability to spend. On any
        # attack after the first against the same target this encounter, the swing
        # strikes again at the same bonus — +1 on a standard action, +2 on a declared
        # full attack, which is the printed rule and also makes a panel-split full
        # attack (each swing its own op) add up to the same total. Decided from the
        # scene's memory of *completed* attacks, so it is stable across the suspension
        # round-trips of the dice popup.
        from . import leveling as leveling_mod

        if (not coup and leveling_mod.has_passive(actor, "swift strikes")
                and f"{actor.ref}>{defender.ref}" in self.scene.attacked):
            extra = 2 if full else 1
            sequence = list(sequence) + [sequence[0]] * extra
            if state["i"] == 0 and not state["rolls"]:
                state["tells"].append(
                    f"Swift Strikes: {actor.name} strikes "
                    f"{'twice more' if extra == 2 else 'again'} at {defender.name}.")

        # Said once, before the first die: a narrator told only "the attack misses" has
        # no way to know the player was trying to take the man alive.
        if lethality != usual and not state.get("lethality_said"):
            state["lethality_said"] = True
            state["tells"].append(
                f"{actor.name} pulls the blow, meaning to leave {defender.name} alive."
                if lethality == "nonlethal" else
                f"{actor.name} strikes to kill.")

        named_key, named = weapon_key, weapon
        while state["i"] < len(sequence):
            # Stop swinging at somebody who has already gone down. Measured in the
            # tavern: the thug dropped to -5 on the first swing of a Swift Strikes pair,
            # and the second was still queued — so the player was asked to roll a d20 at
            # a body on the floor, and because `scene.awaiting` was set the NPC driver
            # returned early every time and never reached the "one side left standing"
            # check. The fight could not end, so the XP and the treasure never settled.
            # The reported "0 XP from the bear" has this shape underneath it too.
            # "Already down", not "cannot act": a stunned or fascinated defender is
            # still a target, and reading this off can-act made them unattackable.
            #
            # From the SECOND swing on. Until 2026-09-27 it broke on the first as well,
            # so a blow at somebody already lying there — unconscious, dying — came
            # back as 0 rolls, no effects, an empty tell and hit points unchanged, and
            # "I finish him" never resolved at all. The first swing is the one the
            # player declared at the body, and it lands (at helpless AC); what the
            # guard is for is the swing QUEUED behind one that dropped them.
            if defender.is_down and state["i"]:
                state["tells"].append(
                    f"{defender.name} is already down; {actor.name} holds the blow.")
                break
            swing_key, iteration = sequence[state["i"]]
            # Each swing its own weapon: the bite of a claw-claw-bite full attack rolls
            # the bite's printed bonus and dice, not the claw's. The named weapon keeps
            # the dict built for it above (an improvised weapon carries its object's name).
            if swing_key == named_key:
                weapon_key, weapon = named_key, named
            else:
                weapon_key, weapon = swing_key, actor.weapon(swing_key)
            printed = weapon.get("stat_block") or {}
            swing_ac, swing_note = target_ac, ac_note
            if printed.get("touch"):
                # "tongue +7 touch", "incorporeal touch +5": armour, shield and natural
                # armour do not count. 243 printed attacks say so.
                swing_ac = defender.touch_ac(flat_footed or bool(flounders)) + footing
                swing_note = (f"touch AC {swing_ac}"
                              + (" (flat-footed)" if flat_footed else ""))
            atk_mods = actor.attack_modifiers(weapon_key, iteration, power_attack=power,
                                              lethality=lethality)
            # Compulsions are charged here rather than in `attack_modifiers` because the
            # penalty depends on *who is being attacked*, which the sheet does not know.
            # It penalises and never prohibits: see the header of rules/compulsion.py.
            atk_mods = atk_mods + compulsion.penalty_against(actor, defender.ref)
            # And the board, for the same reason one step further out: flanking and
            # higher ground depend on where BOTH of them are standing, which the sheet
            # knows even less about than it knows the target. `rules/position.py`.
            atk_mods = atk_mods + position_mod.attack_mods(
                self.scene, actor, defender, weapon)

            # A crowd makes no attack roll. Pathfinder's troop subtype: instead of attacks,
            # "they deal automatic damage to any creature within reach or whose space they
            # occupy at the end of their move, with no attack roll needed." It also solves a
            # real engine problem the player would have met immediately — twelve raiders
            # would otherwise be twelve NPC turns and twelve rolls a round.
            #
            # A swarm is the same rule by another subtype ("creatures with the swarm
            # subtype don't make standard melee attacks"), and its block says so by
            # printing no bonus: "swarm (2d6 plus distraction)".
            if state["stage"] == "attack" and (getattr(actor, "troop", None) is not None
                                              or printed.get("automatic")):
                state["tells"].append(
                    f"{actor.name} are all around {defender.name} — no single blow to "
                    f"parry, and no roll to make.")
                state["hit_total"] = 0
                state["crit"] = False
                state["stage"] = "damage"

            if state["stage"] == "attack":
                atk = self._roll_or_suspend_stage(
                    intent, actor, atk_mods, f"Attack with {weapon['name']}",
                    swing_ac, partial, state, "1d20",
                )
                state["rolls"].append(atk.as_dict())
                natural = atk.natural
                if natural == 1:
                    state["tells"].append(
                        f"{actor.name}'s attack{_instrument(weapon, weapon_key)} goes "
                        f"badly wide (natural 1).")
                    state["i"] += 1
                    continue
                if not d20_succeeds(atk, swing_ac):
                    state["tells"].append(
                        f"{actor.name}'s attack{_instrument(weapon, weapon_key)} misses "
                        f"{defender.name} ({atk.total} against {swing_note}).")
                    state["i"] += 1
                    continue
                # Concealment: displacement, blur, entropic shield and invisibility all
                # come down to a percentile the attack has to beat, and there was nowhere
                # on the sheet to hold one — so four spells whose entire content is this
                # were inert, and `invisible` sat on the unimplemented-condition ledger.
                #
                # Rolled by the engine rather than handed to the player through the dice
                # popup, and that is a considered exception to "the player rolls their
                # own": 1e does not call this an attack roll, it is a chance the blow
                # finds a creature that is not quite where it looks. Adding a fourth
                # suspension stage to every swing to ask for it would cost more than it
                # is worth. The number is stated in the tell either way.
                chance, why = defender.concealment()
                if chance:
                    miss = self.dice.roll("1d100", label=f"miss chance ({why})",
                                          visibility="hidden")
                    state["rolls"].append(miss.as_dict())
                    if miss.total <= chance:
                        state["tells"].append(
                            f"{actor.name} finds nothing there — {why}, {chance}% miss "
                            f"chance ({miss.total}).")
                        state["i"] += 1
                        continue
                state["hit_total"] = atk.total
                # A threat is not a crit until it is confirmed — exactly the sort of step
                # a person forgets mid-fight and code does not.
                threat = natural is not None and natural >= weapon["crit_range"]
                state["stage"] = "confirm" if threat else "damage"
                state["crit"] = False

            if state["stage"] == "confirm":
                confirm = self._roll_or_suspend_stage(
                    intent, actor, atk_mods, f"Confirm critical ({weapon['name']})",
                    swing_ac, partial, state, "1d20",
                )
                state["rolls"].append(confirm.as_dict())
                state["crit"] = confirm.total >= swing_ac
                state["stage"] = "damage"

            if state["stage"] == "damage" and printed.get("ability"):
                # A shadow's touch: its dice are Strength, not hit points. Landed
                # through the `ability_damage` op with the stat block's provenance, the
                # way `_natural_riders` lands a race's rider — the one applicator, so
                # Constitution's hit points and a score at 0 follow by the op's rules.
                res = self.run(self.validate([{
                    "op": "ability_damage", "actor": actor.ref, "target": defender.ref,
                    "visibility": "hidden",
                    "because": f"{actor.name}'s {weapon['name']}",
                    "params": {"ability": printed["ability"], "amount": weapon["damage"],
                               "drain": bool(printed.get("drain"))},
                }], origin=printed.get("origin", ""), origin_name=actor.name))
                state["tells"].append(f"{actor.name}'s {weapon['name']} finds "
                                      f"{defender.name}.")
                for o in res.outcomes:
                    state["effects"].extend(o.effects or [])
                    state["rolls"].extend(r.as_dict() for r in (o.rolls or []))
                    if o.tell:
                        state["tells"].append(o.tell)
                state["i"] += 1
                state["stage"] = "attack"
                continue

            if state["stage"] == "damage":
                mult = weapon["crit_mult"] if state.get("crit") else 1
                dice_notation = _multiply_dice(weapon["damage"], mult)
                dmg_mods = actor.damage_modifiers(weapon_key, power_attack=power)
                rider_col = str(weapon.get("rider_column") or "")
                if rider_col:
                    # Blood DMG + Fist DMG + STR, and BOTH dice are the player's.
                    # The fist die used to be an engine-rolled hidden rider — "when
                    # striking with my fist and my armament on i deal fist dmg and
                    # blood dmg but i only roll blood dmg fist gets rolled for me" —
                    # so it is its own suspended stage now: one popup for the rider,
                    # one for the main die, each named. Riders do not multiply on a
                    # crit, same as 1e treats extra damage dice. Which column the
                    # rider reads is the weapon document's to say, not this file's.
                    from . import leveling as leveling_mod

                    rider = leveling_mod.table_die(actor, rider_col) or "1d6"
                    if "rider_total" not in state:
                        rider_roll = self._roll_or_suspend_stage(
                            intent, actor, [], f"{rider_col.title()} die ({rider})",
                            None, partial, state, rider)
                        state["rider_total"] = rider_roll.total
                        state["rolls"].append(rider_roll.as_dict())
                if mult > 1:
                    dmg_mods = [Modifier(m.value * mult, f"{m.source} x{mult}")
                                for m in dmg_mods]
                if rider_col:
                    # AFTER the crit scaling, deliberately: a live critical showed
                    # "+12 fist die (1d6) x2" — the rider doubled alongside Str,
                    # while the comment above it promised 1e's rule that extra
                    # damage DICE never multiply. Order is the whole fix.
                    dmg_mods = dmg_mods + [Modifier(state["rider_total"],
                                                    f"{rider_col} die ({rider})")]
                # Sneak attack, on the same shelf and for the same reason: the rogue's
                # extra damage "is not multiplied" on a critical hit, so it is added
                # here, past `mult`, and never folded into the weapon's notation.
                # `rules/precision.py` decides whether it applies at all.
                # "Any time her target would be denied a Dexterity bonus to AC": caught
                # flat-footed, or held somewhere Dex does not reach — helpless, stunned,
                # blinded. Only the first was asked until 2026-09-27, so once a fight's
                # first round was over a rogue's blow at a sleeping guard found nothing,
                # and the coup de grâce the book gives sneak attack explicitly got none.
                sneak_dice, sneak_why = self._sneak_for(
                    actor, defender, weapon,
                    flat_footed=flat_footed or defender.loses_dex_to_ac,
                    pulled=pulled)
                if sneak_dice:
                    if "sneak_total" not in state:
                        sneak_roll = self._roll_or_suspend_stage(
                            intent, actor, [], f"Sneak attack ({sneak_dice})",
                            None, partial, state, sneak_dice)
                        state["sneak_total"] = sneak_roll.total
                        state["rolls"].append(sneak_roll.as_dict())
                    dmg_mods = dmg_mods + [
                        Modifier(state["sneak_total"], f"sneak attack ({sneak_dice})")]
                # Said once per swing. The damage stage is re-entered on every resume, so
                # an unguarded append printed the line twice — measured live 2026-09-20
                # fighting a goblin troop, where every blow said "there is no single guard
                # to slip past" twice over.
                if (sneak_dice or sneak_why) and not state.get("sneak_said"):
                    state["sneak_said"] = True
                    state["tells"].append(
                        f"{actor.name} finds the opening — {sneak_why}." if sneak_dice
                        # The "why not" is worth saying: a rogue who never sees their
                        # dice is owed the reason, and the narrator is told it as a fact
                        # of the blow rather than as a rule that fired. Only the first
                        # letter is raised: `capitalize()` lowercases the rest, and it
                        # turned "Troop, Goblin" into "Troop, goblin".
                        else sneak_why[:1].upper() + sneak_why[1:] + ".")
                # "plus 1d6 fire", "plus 2d6 cold": a second packet of a second type,
                # rolled here BEFORE the main die for the reason the rider and sneak
                # dice are — a suspension after damage had landed would land it twice
                # on resume. Never multiplied on a critical (1e: extra dice are not),
                # and applied on its own so fire resistance meets only the fire.
                # Measured 2026-09-27: 551 printed attacks carry one.
                for n, extra in enumerate(printed.get("extra") or ()):
                    if f"extra_{n}" not in state:
                        extra_roll = self._roll_or_suspend_stage(
                            intent, actor, [],
                            f"{extra['type'].title()} ({extra['dice']})",
                            None, partial, state, extra["dice"])
                        state[f"extra_{n}"] = extra_roll.total
                        state["rolls"].append(extra_roll.as_dict())
                dmg = self._roll_or_suspend_stage(
                    intent, actor, dmg_mods,
                    # A granted weapon's damage is several named things — Blood DMG +
                    # Fist DMG + STR — and the label used to say only "armed punch",
                    # so a player watching 8 damage land could not tell whether the
                    # blood die was in it. The document's own label names this roll;
                    # the rider die was the popup before.
                    (f"{weapon['damage_label']} ({weapon['damage']})"
                     if weapon.get("damage_label") else f"Damage ({weapon['name']}")
                    + (" — CRITICAL" if mult > 1 else "")
                    + ("" if weapon.get("damage_label") else ")"),
                    None, partial, state, dice_notation,
                )
                state["rolls"].append(dmg.as_dict())
                amount = max(1, dmg.total)
                # Half, for a blade swung in water. The book halves the DAMAGE of a
                # slashing or bludgeoning weapon and leaves a spear whole, which no
                # modifier can express — a modifier is a number added to a roll and this
                # is a rule about the roll's result. Halved here, where the weapon's type
                # and the swinger's footing are both known, and never below one: a hit
                # that lands is a hit.
                wet_row = actor.water_row()
                if wet_row and water.damage_halved(wet_row, str(weapon["type"])):
                    amount = max(1, amount // 2)
                    state["tells"].append("The water takes half the force out of it.")
                hit = self._apply_damage(defender, amount, weapon["type"],
                                         lethality=lethality)
                if printed:
                    # Whose numbers these were: the stat block's, by the provenance
                    # vocabulary stage 8 gave every other amount.
                    hit["origin"] = printed.get("origin", "")
                # What struck, and how heavy it was: the death line's third axis.
                # Measured 2026-09-18: a thrown pebble took a man's head clean off
                # in the authored backstop, because the pool knew the damage type
                # and the margin and nothing about the weapon.
                hit["weapon"] = str(weapon.get("name") or weapon_key)
                hit["heft"] = ("light" if weapon.get("light")
                               or weapon_key in ("unarmed", "improvised")
                               or "unarmed" in str(weapon.get("name", ""))
                               else "heavy" if int(weapon.get("hands", 1) or 1) >= 2
                               else "one-handed")
                state["effects"].append(hit)
                # What the coup de grâce's save is set by: the damage DEALT, after DR.
                state["dealt"] = int(hit.get("amount") or 0)
                # What the *defender* lost, not what the die said. A hit for 12 against
                # DR 5 is a hit for 7, and the GM must be told the second number or it
                # will narrate a wound nobody took.
                state["tells"].append(
                    f"{actor.name} {'critically ' if state.get('crit') else ''}hits "
                    f"{defender.name}{_instrument(weapon, weapon_key)} for "
                    f"{hit['amount']} "
                    # The one word that keeps a knockout from being narrated as a
                    # wound: the narrator is fed tells and nothing else, and the
                    # effect's `lethality` never reaches it.
                    + ("non-lethal " if hit.get("lethality") == "nonlethal" else "")
                    + f"{weapon['type']}"
                    + (f" ({hit['note']})." if hit["note"] else "."))
                for n, extra in enumerate(printed.get("extra") or ()):
                    more = self._apply_damage(
                        defender, max(0, int(state.pop(f"extra_{n}"))), extra["type"])
                    more["weapon"] = hit["weapon"]
                    more["origin"] = printed.get("origin", "")
                    state["effects"].append(more)
                    state["tells"].append(
                        f"The {weapon['name']} adds {more['amount']} {more['type']}"
                        + (f" ({more['note']})." if more.get("note") else "."))
                # A coated blade delivers its dose on the first thing it cuts, and then it
                # is gone. Spent on the hit rather than on the swing: a poison wiped off
                # by a miss is a dose nobody got.
                for extra in self._deliver_coating(actor, defender, weapon_key):
                    state["effects"].append(extra["effect"])
                    state["tells"].append(extra["tell"])
                # What the body itself does past the wound: a jaw that holds on, a tail
                # that sweeps the legs. The race's own tags, read here because this is
                # where a hit is known to have landed.
                for extra in self._natural_riders(actor, defender, weapon_key):
                    state["effects"].append(extra["effect"])
                    state["tells"].append(extra["tell"])
                # Thorns, wasps, holy fire: whatever the defender is wearing that
                # punishes the creature who just hit them. Fired here rather than in
                # `_apply_damage`, because retribution is owed to a *melee attack* and
                # not to every point of damage — a fireball does not get spiked.
                if weapon["category"] == "melee":
                    for got in self._retaliate(defender, actor):
                        state["effects"].append(got)
                        state["tells"].append(_ward_tell(self.scene, got))
                # The swing is over, so its own dice go with it. They are parked in
                # `state` only to survive the popups between the extra dice and the
                # main damage roll; left in place, the `not in state` guards above read
                # the NEXT swing's as already rolled. Measured 2026-09-27: an 8th-level
                # rogue's full attack on a flat-footed foe hit twice, rolled "Sneak
                # attack (4d6)" once, and added the same +13 to both damage rolls; the
                # player was never asked for the second sneak die, and the opening was
                # found once. Each hit rolls its own in 1e.
                for key in ("rider_total", "sneak_total", "sneak_said"):
                    state.pop(key, None)
                state["i"] += 1
                state["stage"] = "attack"

        crossed = self._hp_state_effects(defender)
        coup_dc = None
        if coup and "dealt" in state and not defender.is_dead:
            # "If the defender survives the damage": the ladder has run first, so a blow
            # that killed outright asks nothing more of anybody.
            exempt = coup_mod.fortitude_exempt(defender)
            if exempt:
                state["tells"].append(
                    f"{defender.name} has {exempt}: there is no Fortitude save to fail, "
                    f"and only the wound counts.")
            else:
                coup_dc = coup_mod.save_dc(state["dealt"])
                # Rolled by the engine, never suspended: the defender is not the one who
                # declared this, and every NPC's save is the engine's. (A PC on the
                # receiving end only ever meets this from an NPC's intent, which
                # `_force_visibility` has already made hidden.)
                save = self.dice.d20(defender.save_modifiers("fort"),
                                     label="Fortitude save against the coup de grâce",
                                     visibility=intent.visibility)
                state["rolls"].append(save.as_dict())
                # CRB p.180: a natural 20 on a save always succeeds and a natural 1
                # always fails — `dice.d20_succeeds`, the reader every save asks.
                # Against DC 10 + damage the first is most of the reason anybody lives
                # through this. The natural is said when it decided, because "makes
                # the save (23 against DC 27)" read as bad arithmetic in the first run.
                nat = natural_said(save, coup_dc)
                why = f"{nat}, " if nat else ""
                if d20_succeeds(save, coup_dc):
                    state["tells"].append(
                        f"{defender.name} makes the Fortitude save ({why}{save.total} "
                        f"against DC {coup_dc}) and clings to life.")
                else:
                    state["tells"].append(
                        f"{defender.name} fails the Fortitude save ({why}{save.total} "
                        f"against DC {coup_dc}).")
                    # The one door death is written through (`Actor.die`), and the same
                    # effect shape the ladder writes, so the tell below says it.
                    if defender.die("a coup de grâce"):
                        # The rungs this same blow wrote (unconscious, dying) are gone
                        # again, and saying them first read "the thug is dying. the
                        # thug is dead." in the probe — only what still holds is said.
                        crossed = [e for e in crossed if e.get("ref") != defender.ref
                                   or defender.has_condition(str(e.get("condition")))]
                        crossed.append({"ref": defender.ref, "kind": "condition",
                                        "condition": "dead", "from": "coup de grâce"})
        rolls = [_roll_from_dict(r) for r in state["rolls"]]
        effects = list(state["effects"]) + crossed
        any_hit = any(e.get("kind") == "damage" for e in effects)
        # Harm moves how they feel (item 22.3; owner, Q37: the sword door obeys the rule
        # the spell door does). Damage, or a harmful condition landed by the blow.
        if any_hit or any(e.get("kind") == "condition" and e.get("ref") == defender.ref
                          and attitude_mod.harmful_condition(str(e.get("condition", "")))
                          for e in effects):
            felt = attitude_mod.harmed(self, defender, actor, f"attack:{weapon_key}",
                                       seen=bool(state.get("seen", True)))
            if felt:
                effects.append(felt)
                state["tells"].append(attitude_mod.harm_said(felt, defender.name))
        # A thrown thing is on the ground now, at this spot, with its record — the
        # player's, or whoever's it was before they picked it up. One applicator:
        # the same `place_prop` the sunder and the drop use.
        if thrown_thing and intent.params.get("thrown"):
            rec = self.scene.prop_named(thrown_thing)
            key = thrown_thing.lower()
            for name in list(actor.goods):
                if name.lower() == key:
                    actor.goods[name] -= 1
                    if actor.goods[name] <= 0:
                        del actor.goods[name]
                    break
            self.scene.place_prop(thrown_thing,
                                  owner=(rec or {}).get("owner") or actor.ref,
                                  from_=(rec or {}).get("from_", ""),
                                  state=(rec or {}).get("state", "intact"),
                                  turn=int(self.scene.clock_minutes))
            state["tells"].append(f"The {thrown_thing} lies where it fell.")
        # First blood is remembered only once the attack completes, so the decision
        # "is this a subsequent attack?" cannot flip between a suspension and its resume.
        self.scene.attacked.add(f"{actor.ref}>{defender.ref}")
        if coup:
            # No AC was rolled against; the only number set against anybody was the save.
            dc = ({"value": coup_dc, "explain": "Fortitude, 10 + damage dealt"}
                  if coup_dc is not None else None)
        else:
            dc = {"value": target_ac, "explain": ac_note, "flat_footed": flat_footed}
        return Outcome(
            intent_id=intent.id, op="attack", rolls=rolls, dc=dc,
            verdict="hit" if any_hit else "miss",
            effects=effects,
            tell=" ".join(state["tells"]) + self._hp_state_tell(crossed),
            because=intent.because,
        )

    def _reach_refusal(self, intent: Intent, actor: Actor, defender: Actor,
                       weapon_key: str, *, voice: str = "model") -> str:
        """Why this melee blow cannot land from where the two of them stand, or "".

        The measurement and its source are `position.out_of_reach`'s; this is the
        sentence. Measured 2026-09-27: a disarm, a trip, a grapple and a plain rapier
        thrust all resolved from fifteen feet.

        What the refusal names is a SQUARE. The model plans in zones, and a
        `move zone=engaged` on a mapped fight relabels the zone and leaves the body
        where it stood — so "move first" alone is an instruction nobody can carry out.
        The attacker is never moved HERE. Since the owner's ruling of 2026-09-29 a blow
        that one move action reaches is not refused at all — `_closing_step` answers
        first and `_drive` walks the step — so this sentence is what is left: the gap
        is more than one move, or the move action is already spent this round.

        Three readers, three sentences (`voice`). "model": the fix as a JSON move to
        copy, for the repair loop. "tell": the printed floor's, the fault alone — a
        tell is fed to the narrator, and a JSON move and a grid square in it are two
        things the prose has no business repeating. "person": the combat panel shows
        a refusal to the player directly, and the first live run put the JSON on the
        page (2026-09-28); the square is named the way the map names it.
        """
        from . import position as position_mod

        man = str(intent.params.get("manoeuvre") or "")
        miss = position_mod.out_of_reach(self.scene, actor, defender, weapon_key,
                                         manoeuvre=man,
                                         thrown=bool(intent.params.get("thrown")))
        if miss is None:
            return ""
        blow = (f"an {man}" if man[:1] in "aeiou" else f"a {man}") if man \
            else "a melee attack"
        # The table's own key ("glaive"), not its display name ("Glaive"), mid-sentence;
        # a granted or natural weapon has no key there and is called what it is called.
        if weapons_mod.has(weapon_key):
            held = weapon_key
        else:
            try:
                held = str(actor.weapon(weapon_key).get("name") or weapon_key)
            except KeyError:
                held = weapon_key
        if miss.too_close:
            fault = (f"{defender.name} is {miss.feet} ft from {actor.name}, inside the "
                     f"{held}'s reach — a reach weapon cannot strike a foe beside you, "
                     f"and {blow} with it needs them {miss.reach} ft off.")
        else:
            by = f" with the {held}" if miss.with_weapon and weapon_key != "unarmed" else ""
            fault = (f"{actor.name} reaches {miss.reach} ft{by} and {defender.name} is "
                     f"{miss.feet} ft away; {blow} needs them within reach.")
        if voice == "tell":
            return f"{_sentence(fault)} Nothing is rolled."
        found = position_mod.square_in_reach(self.scene, actor, defender, miss.reach,
                                             miss.gap)
        if found is None:
            return (f"{_sentence(fault) if voice == 'person' else fault} There is no "
                    f"open square in reach of {defender.name} that {actor.name} can get "
                    f"to. Take another action.")
        (x, y), cost = found
        step = (f'{{"op": "move", "actor": "{actor.ref}", "params": {{"square": '
                f'[{x}, {y}]}}}}')
        speed = int(getattr(actor, "speed_feet", 0) or 0)
        far = self.scene.in_encounter and speed and cost > speed
        if voice == "person":
            if far:
                return (f"{_sentence(fault)} The nearest square in reach, {x},{y}, is "
                        f"{cost} ft away and {actor.name} moves {speed} ft: close in "
                        f"this turn and strike on the next.")
            return (f"{_sentence(fault)} Click square {x},{y} on the map to move there "
                    f"({cost} ft), then strike.")
        if far:
            return (f"{fault} The nearest square in reach, [{x}, {y}], is {cost} ft away "
                    f"by the open route and {actor.name} has {speed} ft of movement: "
                    f"move toward them this turn and strike on the next.")
        return (f"{fault} Move first — to square [{x}, {y}], {cost} ft — with {step} "
                f"before the attack in the same list.")

    def _closing_step(self, intent: Intent, actor: Actor, defender: Actor,
                      weapon_key: str) -> tuple[tuple[int, int], int] | None:
        """The square one move action carries this attacker to, from which the blow it
        declared lands, and the feet the walk costs; None when the blow must be refused
        (`_reach_refusal`) or needs no step.

        Measured live 2026-09-28 (`tools/narrator_audit.py --script fight`): "I punch him
        in the face." came back 422 — "Kesst Vayr reaches 5 ft and Gorvoth Vexarion is
        15 ft away ... Click square 5,6 on the map to move there (10 ft), then strike."
        — three turns running, and the fight never moved. The owner's ruling
        (2026-09-29): "yes close the distance and strike if one move reaches."

        The rule it rests on (Core Rulebook, Combat; aonprd.com/Rules.aspx?ID=129, 130,
        137, 145): "In a normal round, you can perform a standard action and a move action";
        a move action moves you up to your speed; "Making an attack is a standard
        action" — ONE attack, because the iteratives need the full-round action, and
        "the only movement you can take during a full attack is a 5-foot step". So the
        step is a move action and never a charge (a full-round action this engine does
        not have), and the blow behind it is single whatever the attacker's BAB.

        The walk is `position.square_in_reach` — `Grid.reachable` over the occupancy the
        move op refuses by, difficult terrain at double ("each square of difficult
        terrain counts as 2 squares of movement", aonprd.com/Rules.aspx?ID=177) — so the square is one the
        move op would accept. Not for a reaction (an attack of opportunity is taken
        where you stand), a coup de grâce (a full-round action), a target still
        undecided, a body that cannot move, or an attacker who has walked this round
        already (`Scene.move_spent`).
        """
        from . import position as position_mod

        if not self.scene.in_encounter or not self.scene.has_grid:
            return None
        params = intent.params or {}
        if params.get("reaction") or params.get("coup_de_grace") \
                or params.get("undecided"):
            return None
        if actor.is_down or actor.blocking_key("move") or actor.blocking_key("attack"):
            return None
        if defender.has_state("state.down.dead"):
            return None
        if self.scene.move_spent.get(actor.ref) == self.scene.round:
            return None
        miss = position_mod.out_of_reach(self.scene, actor, defender, weapon_key,
                                         manoeuvre=str(params.get("manoeuvre") or ""),
                                         thrown=bool(params.get("thrown")))
        if miss is None:
            return None
        speed = int(getattr(actor, "speed_feet", 0) or 0)
        if speed <= 0:
            return None
        found = position_mod.square_in_reach(self.scene, actor, defender, miss.reach,
                                             miss.gap)
        if found is None or found[1] > speed:
            return None
        return found

    def _close_before(self, raw: dict) -> dict | None:
        """The move intent a blow one move short is owed, spliced in front of it by
        `_drive`; None for anything else.

        A real `move`, not a shift of `Scene.positions` inside the attack: the move op
        is the one door a body crosses the grid by, and going through it is what makes
        the step provoke (`_reactions_before`, "moving out of a threatened square
        usually provokes attacks of opportunity", aonprd.com/Rules.aspx?ID=102), be told, and be spent
        (`Scene.move_spent`). Asked under the same conditions as `_op_attack`'s reach
        floor — a blow that opens the fight this batch is deferred by the battle gate
        and rolls nothing, so it closes nothing either: its step is taken with the blow
        on the attacker's first combat turn.
        """
        if raw.get("op") != "attack" or self._battle_joined:
            return None
        intent = _intent_from_dict(raw)
        actor = self.scene.actors.get(intent.actor or "")
        targets = intent.targets()
        defender = self.scene.actors.get(targets[0]) if targets else None
        if actor is None or defender is None:
            return None
        weapon_key = (intent.params.get("weapon") or actor.wielded_key()).lower()
        found = self._closing_step(intent, actor, defender, weapon_key)
        if found is None:
            return None
        (x, y), _ = found
        # A move and a standard action: the blow after the step is one attack at the
        # highest bonus, never the full attack a model declared nor a stated iterative
        # (the panel's split full attack names one per swing).
        raw["params"] = dict(intent.params, full_attack=False)
        raw["params"].pop("iteration", None)
        return {"op": "move", "actor": actor.ref, "id": f"{intent.id}-close",
                "target": None, "visibility": intent.visibility,
                "because": f"closing on {defender.name}",
                "params": {"square": [x, y], "closing_on": defender.ref}}

    def _resolve_maneuver(self, intent: Intent, actor: Actor, defender: Actor,
                          weapon_key: str, partial: dict) -> Outcome:
        """A combat manoeuvre: the same attack roll, with CMB instead of the attack
        bonus, against the target's CMD instead of its AC.

        Core Rulebook p.198-201. Every manoeuvre shares this resolution; only the
        consequence differs, which is why they live in one table and one code path.
        """
        key = intent.params["manoeuvre"]
        m = MANEUVERS[key]
        self._ensure_encounter(intent.actor, intent.target)

        mods = list(actor.cmb_modifiers(key))

        # Attempting to disarm while unarmed is -4; so is grappling without two hands.
        if m.get("unarmed_penalty") and weapon_key == "unarmed":
            mods.append(Modifier(m["unarmed_penalty"], "unarmed"))
        # A stunned target is easier to manhandle; an incapacitated one cannot resist
        # at all.
        if defender.has_condition("stunned"):
            mods.append(Modifier(4, "target is stunned"))

        # A steal chooses its item before the roll, because the item sets the defence:
        # a sheathed weapon, a pouch or a cloak is fastened and worth +5 CMD. What is
        # held or worn close is not a steal at all, and is refused here with the
        # manoeuvre that would do it.
        loot = None
        if m.get("outcome") == "take":
            loot = self._steal_choice(defender, str(intent.params.get("item") or ""))
            if isinstance(loot, str):
                return self._refuse(intent, loot)

        flat_footed = self._flat_footed(defender)
        cmd_mods = defender.cmd_modifiers(
            flat_footed, maneuver=str(intent.params.get("manoeuvre") or "") or None)
        if loot and loot["fastened"]:
            cmd_mods = list(cmd_mods) + [Modifier(m["fastened_cmd"],
                                                  f"{loot['label']} is fastened")]
        cmd = sum(x.value for x in cmd_mods)
        cmd_note = f"CMD {cmd}" + (" (flat-footed)" if flat_footed else "")

        state = partial.get("attack_state") or {}
        automatic = defender.is_helpless or defender.is_down
        if automatic:
            # "If your target is immobilized, unconscious, or otherwise incapacitated,
            # your maneuver automatically succeeds." That is the `helpless` question,
            # not the can-act one: reading it off `can_act` handed a free grapple
            # against a merely dazed, stunned, cowering or fascinated target.
            #
            # `is_down` is here too, and the omission was caught by review rather than
            # by the suite. The `helpless` flag sits on five condition rows where the
            # old can-act test covered eleven, and `dead` and `stable` are in the gap —
            # so the player was handed a d20 to roll against a corpse, which is the
            # same insult the swing path had already been fixed for.
            roll = None
            margin = 0
            verdict = "success"
        else:
            # The CMB roll is kept in the parked state, because a sunder has a second
            # stage (the damage to the item) and the player rolls both. Before this,
            # the state handed to the suspension was a fresh dict every time: a second
            # popup would have spent its face on the CMB roll again.
            state = partial.get("attack_state") or {}
            if state.get("cmb"):
                roll = _roll_from_dict(state["cmb"])
            else:
                roll = self._roll_or_suspend_stage(
                    intent, actor, mods, f"{m['name'].title()} (CMB)", cmd, partial,
                    state, "1d20",
                )
                state["cmb"] = roll.as_dict()
            # A natural 20 always succeeds and a natural 1 always fails, whatever the
            # arithmetic says — `dice.d20_succeeds`, the one reader saves use too. The
            # margin is clamped to agree with the verdict, because the overrun's "by 5
            # or more" reads it.
            margin = roll.total - cmd
            if d20_succeeds(roll, cmd):
                verdict, margin = "success", max(margin, 0)
            else:
                verdict, margin = "failure", min(margin, -1)

        effects: list[dict] = []
        bits: list[str] = []
        extra_rolls: list[Roll] = []

        if verdict == "success":
            # Every sentence of the table is rendered by name, never spliced: the table
            # was written "you drag the target 5 feet", and on a creature's turn that
            # "you" was the creature while the narrator is told "you" is the player
            # (see `maneuver_text`). The player's own become "you" downstream, through
            # `narration.pc_to_second_person`, like every other tell. The lead was
            # `name + "s"` too, which wrote "bull rushs" and, once that rule ran, "you
            # trips"; each manoeuvre now says its own verb.
            def say(template: str, capital: bool = True, **values) -> str:
                return maneuver_text(template, actor.name, defender.name,
                                     capital=capital, **values)

            # The effect clause is written by whatever makes it true. A row with an
            # `outcome` hands the sentence to its applicator, which says what it did —
            # the item by name, the feet actually moved, the one condition put on — and
            # nothing else; the table's plain `effect` is only spliced for the rows whose
            # claim a `condition` below carries (trip, grapple).
            outcome = m.get("outcome")
            if outcome:
                clause, extra, done = self._MANEUVER_OUTCOMES[outcome](
                    self, m, intent, actor, defender, margin, weapon_key, loot, say)
                effects.extend(done)
            else:
                clause, extra = say(m["effect"], False), []
            bits.append(
                say(m["lead"])
                + (f" automatically, as {defender.name} cannot resist" if automatic
                   else f" by {margin}")
                + ("." if m.get("damages_item") else f": {clause}.")
            )
            bits.extend(extra)
            if m.get("damages_item"):
                # Sunder, Core Rulebook (aonprd.com, Rules: Sunder): "If your attack is
                # successful, you deal damage to the item normally. Damage that exceeds
                # the object's Hardness is subtracted from its hit points. If an object
                # has equal to or less than half its total hit points remaining, it
                # gains the broken condition. If the damage you deal would reduce the
                # object to less than 0 hit points, you can choose to destroy it."
                # Measured 2026-09-18: `damages_item` was a table flag nothing read —
                # the tell said "you damage an item", no damage was rolled, the club
                # took nothing, and the prose decided it was in fragments (and, a beat
                # later, a table). The damage is the attacker's weapon's, rolled by
                # the player when it is theirs, through hardness, and the state the
                # item is left in is in the tell for the prose to hold to.
                weapon = actor.weapon(weapon_key)
                item_name = str(intent.params.get("item") or defender.equipped
                                or (defender.weapons[0] if defender.weapons else "")
                                or "").strip()
                if not item_name or item_name == "unarmed":
                    bits.append(f"{defender.name} holds nothing that can be broken.")
                else:
                    dmg = self._roll_or_suspend_stage(
                        intent, actor, actor.damage_modifiers(weapon_key),
                        f"Sunder damage ({weapon['name']}) against {defender.name}'s "
                        f"{item_name}", None, partial, state, weapon["damage"])
                    extra_rolls.append(dmg)
                    item = defender.item(item_name)
                    was_broken = item.broken
                    res = defender.damage_item(item_name, max(0, dmg.total),
                                               str(weapon["type"]))
                    if res["destroyed"]:
                        what = "destroyed — in pieces"
                        # A weapon in pieces is not in the hand any more.
                        if (defender.equipped or "").lower() == item_name.lower():
                            others = [w for w in defender.weapons
                                      if w.lower() != item_name.lower()]
                            defender.equipped = others[0] if others else "unarmed"
                        # And the pieces lie at the spot, his, of his club, of its
                        # material — so "I pick up a chunk of wood" finds THIS record
                        # and keeps its provenance, and no later beat can make it a
                        # table (the props ledger's first entry, 2026-09-18).
                        self.scene.place_prop(
                            f"fragments of {defender.name}'s {item_name}",
                            owner=defender.ref, from_=item_name, state="fragments")
                        self.scene.prop_named(
                            f"fragments of {defender.name}'s {item_name}"
                        )["material"] = str(item.material or "")
                    elif res["broken"]:
                        what = "broken (half its hit points gone; -2 to hit and damage with it)"
                    elif was_broken:
                        what = "already broken, and worse for it"
                    elif res["taken"] == 0:
                        what = "unmarked — the blow did not get through its hardness"
                    else:
                        what = "dented, still whole"
                    bits.append(
                        f"{defender.name}'s {item_name} takes {res['taken']} through "
                        f"hardness {res['hardness']} ({res['hp']}/{res['hp_max']} left): "
                        f"{what}.")
                    effects.append({"kind": "item_damage", "ref": defender.ref,
                                    "owner": defender.ref, "weapon": weapon["name"],
                                    **res})
            cond = m.get("condition")
            if cond:
                defender.add_condition(cond, source=f"{m['name']} by {actor.name}")
                effects.append({"ref": defender.ref, "kind": "condition",
                                "condition": cond, "from": m["name"]})
            if m.get("also_grapples_attacker"):
                actor.add_condition("grappled", source=f"grappling {defender.name}")
                effects.append({"ref": actor.ref, "kind": "condition",
                                "condition": "grappled", "from": m["name"]})
            for over, extra in sorted((m.get("degrees") or {}).items()):
                if margin >= over:
                    bits.append(say(extra).rstrip(".") + ".")
                    dc_cond = (m.get("degree_condition") or {}).get(over)
                    if dc_cond:
                        defender.add_condition(dc_cond, source=m["name"])
                        effects.append({"ref": defender.ref, "kind": "condition",
                                        "condition": dc_cond, "from": m["name"]})
        else:
            bits.append(
                f"{actor.name}'s {m['name']} fails against {defender.name} by {-margin}."
            )
            # Failing by 10 or more can turn the manoeuvre back on you.
            if m.get("backfire") and margin <= -10 and m.get("outcome") == "drop":
                # "You drop the weapon that you were using." Said only when there was
                # one: a fist has nothing to let go of, and the tell used to drop "the
                # weapon used for the disarm" whether or not there was a weapon, and
                # then leave it in the hand.
                if self._drops_in_hand(actor, weapon_key):
                    rec = self._let_go(actor, weapon_key)
                    bits.append(maneuver_text(m["backfire"], actor.name, defender.name,
                                              item=self._the(weapon_key)) + ".")
                    effects.append({"ref": actor.ref, "kind": "dropped",
                                    "item": weapon_key, "prop": rec["name"],
                                    "from": f"failed {m['name']}"})
            elif m.get("backfire") and margin <= -10:
                bits.append(maneuver_text(m["backfire"], actor.name, defender.name) + ".")
                back = m.get("backfire_condition")
                if back:
                    actor.add_condition(back, source=f"failed {m['name']}")
                    effects.append({"ref": actor.ref, "kind": "condition",
                                    "condition": back, "from": f"failed {m['name']}"})

        crossed = self._hp_state_effects(defender)
        effects.extend(crossed)
        return Outcome(
            intent_id=intent.id, op="attack",
            rolls=([roll] if roll else []) + extra_rolls,
            dc={"value": cmd, "explain": cmd_note, "flat_footed": flat_footed,
                "breakdown": [x.as_dict() for x in cmd_mods]},
            verdict=verdict, margin=margin, effects=effects,
            tell=" ".join(bits) + self._hp_state_tell(crossed),
            because=intent.because,
        )

    # --- what a manoeuvre does, through the doors that already exist -------------------
    #
    # Measured 2026-09-27 on the tells-by-name branch: disarm, steal, bull rush, drag,
    # reposition, overrun and dirty trick each told the narrator an outcome nothing in
    # state carried — the club "dropped" and still `equipped`, the purse "taken" and
    # still in the purse, the thug "pushed back 10 feet" on the square he started on,
    # and "blinded, dazzled, deafened, entangled, shaken or sickened" over a dazzle.
    # Each applicator below changes the state through a door the engine already has —
    # the props ledger for where a thing is, the carry for who has it, `Scene.positions`
    # for where a body stands, `add_condition` for what it suffers — and returns the
    # sentence for what it did, so the tell is written from the change and not before it.
    #
    # Prior art. Foundry's pf1 system resolves a manoeuvre as a roll against CMD and
    # leaves every consequence to the GM (no issue proposes more); that is the shape this
    # engine had, and it only works with a human at the table to do the rest. Owlcat's
    # Pathfinder CRPGs made disarm a timed "cannot use weapons" condition instead of a
    # drop — refused here, because it changes the rule (the weapon comes back on its
    # own) and the props ledger already carries a thing lying on the ground. ROM puts a
    # disarmed weapon on the room's floor (`obj_to_room`) and a stolen thing in the
    # thief's inventory; so does this.

    def _drops_in_hand(self, actor: Actor, key: str) -> bool:
        """Is `key` a thing in this creature's hand that can leave it? A fist cannot,
        a bite cannot, and a weapon a class power forms exists only while it is formed."""
        from . import leveling

        key = (key or "").strip().lower()
        if not key or key in ("unarmed", "improvised"):
            return False
        if actor.natural_weapon(key) is not None:
            return False
        if leveling.granted_weapon_named(actor, key) is not None:
            return False
        return key == (actor.equipped or "").strip().lower()

    def _held_items(self, actor: Actor) -> list[str]:
        """What is in this creature's hands: the weapon it wields and a shield it holds.
        A buckler is strapped to the forearm and stays."""
        held = []
        if self._drops_in_hand(actor, actor.equipped or ""):
            held.append(str(actor.equipped))
        shield = str(actor.shield or "none")
        if shield != "none" and "buckler" not in shield.lower():
            held.append(shield)
        return held

    def _let_go(self, owner: Actor, item: str) -> dict:
        """A held thing leaves the hand and lies here, still its owner's. Returns the
        props record.

        The hand is empty afterwards — "unarmed", not the next weapon on the list. The
        sunder's destroyed branch draws the next one for free; a drop does not, because
        a draw is an action the tell would have to claim, and a creature that wants its
        dagger names it in its next attack the way it always could.
        """
        key = item.strip().lower()
        if str(owner.shield or "").lower() == key:
            owner.shield = "none"
        else:
            for i, w in enumerate(owner.weapons):
                if w.lower() == key:
                    del owner.weapons[i]
                    break
            for name in list(owner.goods):
                if name.lower() == key:
                    owner.goods[name] -= 1
                    if owner.goods[name] <= 0:
                        del owner.goods[name]
                    break
            if (owner.equipped or "").lower() == key:
                owner.equipped = "unarmed"
        worn = owner.gear.get(key)
        # Named for its owner, because the ledger finds a record by name: two thugs'
        # saps both called "sap" would be ONE record, and the second drop would pick the
        # first one up and move it.
        return self.scene.place_prop(
            f"{owner.name}'s {key}", owner=owner.ref, from_=key,
            state="broken" if worn is not None and worn.broken else "intact",
            turn=int(self.scene.clock_minutes),
            # At their feet: in their own square, so a bull rush that follows the
            # disarm leaves the weapon behind, where a pick-up has to reach it.
            square=self.scene.positions.get(owner.ref))

    def _into_hands(self, taker: Actor, item: str, equip: bool = False) -> None:
        """A thing goes into this creature's carry, routed the way `_op_give` routes a
        bought one: a weapon onto the weapons list, so it can be swung."""
        from . import weapons as weapons_mod

        key = item.strip().lower()
        taker.goods[key] = taker.goods.get(key, 0) + 1
        if goods.kind_of(key) == "weapon" or weapons_mod.has(key):
            if key not in [w.lower() for w in taker.weapons]:
                taker.weapons.append(key)
            if equip:
                taker.equipped = key

    @staticmethod
    def _the(item: str) -> str:
        return item if re.match(r"(?i)(the|a|an|some)\b", item) else f"the {item}"

    def _outcome_drop(self, m, intent, actor, defender, margin, weapon_key, loot, say):
        held = self._held_items(defender)
        if not held:
            return say(m["nothing"], False), [], []
        named = str(intent.params.get("item") or "").strip().lower()
        if margin >= m["both_hands_at"]:
            chosen = held
        else:
            chosen = [next((h for h in held if h.lower() == named), None)
                      or next((h for h in held if named and (named in h.lower()
                                                             or h.lower() in named)), None)
                      or held[0]]
        effects, recs = [], []
        for h in chosen:
            rec = self._let_go(defender, h)
            recs.append(rec)
            effects.append({"ref": defender.ref, "kind": "dropped", "item": h.lower(),
                            "prop": rec["name"], "from": m["name"]})
        extra = []
        # "If you successfully disarm your opponent without using a weapon, you may
        # automatically pick up the item dropped." A formed class weapon is a weapon.
        if weapon_key == "unarmed" and not actor.weapon(weapon_key).get("granted_by"):
            first = recs[0]
            self.scene.hold_prop(first["name"], actor.ref,
                                 turn=int(self.scene.clock_minutes))
            self._into_hands(actor, first["from_"], equip=True)
            extra.append(say(m["picked_up"], item=self._the(first["from_"])) + ".")
            effects.append({"ref": actor.ref, "kind": "picked_up",
                            "item": first["from_"], "prop": first["name"]})
        return (say(m["effect"], False,
                    item=" and ".join(self._the(h.lower()) for h in chosen)),
                extra, effects)

    # Slots a steal may reach: "tucked into a belt or loosely attached — brooches and
    # necklaces" are easy, a cloak is fastened (+5). Everything else a slot holds is
    # "closely worn" (armour, boots, clothing, rings) and is not a steal at all.
    _STEAL_SLOTS = {"neck": False, "shoulders": True}
    _PURSE_WORDS = re.compile(r"(?i)\b(purse|pouch|coins?|money|silver|gold|copper)\b")

    def _steal_choice(self, defender: Actor, named: str):
        """What a steal would take: a dict, a refusal (str), or None for nothing loose.

        The kit a creature was generated with collapses into contents here, because a
        hand in its pockets is the first observation of them (`bestiary.collapse_kit`)."""
        from .bestiary import collapse_kit

        collapse_kit(defender)
        held = {h.lower() for h in self._held_items(defender)}
        options: list[dict] = []
        seen: set[str] = set()

        def offer(label, where, key, fastened):
            if label.lower() in seen or label.lower() in held:
                return
            seen.add(label.lower())
            options.append({"label": label, "where": where, "key": key,
                            "fastened": fastened})

        for name, n in defender.goods.items():
            if n > 0:
                offer(name, "goods", name, False)
        for iid, n in defender.inventory.items():
            if n > 0:
                offer(iid.replace("-", " "), "inventory", iid, False)
        for slot, fastened in self._STEAL_SLOTS.items():
            for it in defender.slots.get(slot) or []:
                if it:
                    offer(str(it), f"slot:{slot}", str(it), fastened)
        for w in defender.weapons:
            if w.lower() not in ("unarmed", "improvised"):
                offer(w, "weapons", w, True)          # sheathed
        if any(int(v) > 0 for v in defender.purse.values()):
            offer("coin purse", "purse", "", True)

        named = " ".join(named.lower().split())
        if not named:
            loose = [o for o in options if not o["fastened"]]
            return (loose or options or [None])[0]
        if named in held or any(named in h or h in named for h in held):
            return (f"{defender.name} is holding the {named}. A steal takes what is not "
                    f"in the hand; knocking it out of the hand is a disarm.")
        close = [str(defender.armour or "")] + [
            str(it) for slot, items in defender.slots.items()
            if slot not in self._STEAL_SLOTS for it in (items or []) if it]
        if any(c and c.lower() == named for c in close):
            return (f"The {named} is worn close — armour, rings, boots and clothing "
                    f"cannot be stolen in a fight.")
        exact = next((o for o in options if o["label"].lower() == named), None)
        if exact:
            return exact
        if self._PURSE_WORDS.search(named):
            purse = next((o for o in options if o["where"] == "purse"), None)
            if purse:
                return purse
        words = {w for w in re.findall(r"[a-z]+", named) if len(w) >= 3}
        near = next((o for o in options
                     if words & set(re.findall(r"[a-z]+", o["label"].lower()))), None)
        return near or f"{defender.name} has no {named} that can be taken."

    def _outcome_take(self, m, intent, actor, defender, margin, weapon_key, loot, say):
        if not loot:
            return say(m["nothing"], False), [], []
        where, key, label = loot["where"], loot["key"], loot["label"]
        if where == "purse":
            coins = goods.coinage(getattr(self, "world", None), None)
            label = f"coin purse ({goods.purse_line(defender.purse, coins)})"
            for coin, n in defender.purse.items():
                actor.purse[coin] = actor.purse.get(coin, 0) + int(n)
            defender.purse = {}
        elif where == "inventory":
            defender.inventory[key] -= 1
            if defender.inventory[key] <= 0:
                del defender.inventory[key]
            actor.carry(key, 1, at_minute=self.scene.clock_minutes)
        elif where.startswith("slot:"):
            items = defender.slots.get(where[5:]) or []
            items.remove(key)
            self._into_hands(actor, key)
        else:
            # Goods or a sheathed weapon: out of both lists, since a bought sword sits
            # on both and a stolen one must leave both.
            self._let_go_quietly(defender, key)
            self._into_hands(actor, key)
        # Whose it was travels with it (Creation Kit's owner beside the stolen flag):
        # the thing is in the thief's hands and still the victim's, so the victim's own
        # dagger is refused to them by name, and the ledger can say whose purse it is.
        plain = loot["label"].lower()       # "dice of bone", not its id "dice-of-bone"
        rec = self.scene.hold_prop(f"{defender.name}'s {plain}", actor.ref,
                                   owner=defender.ref, from_=plain, state="intact",
                                   turn=int(self.scene.clock_minutes))
        return (say(m["effect"], False, item=self._the(label)), [],
                [{"ref": actor.ref, "kind": "stolen", "from": defender.ref,
                  "item": label, "prop": rec["name"]}])

    def _let_go_quietly(self, owner: Actor, key: str) -> None:
        """A sheathed weapon leaves the carry without touching the ground."""
        k = key.lower()
        for i, w in enumerate(owner.weapons):
            if w.lower() == k:
                del owner.weapons[i]
                break
        for name in list(owner.goods):
            if name.lower() == k:
                owner.goods[name] -= 1
                if owner.goods[name] <= 0:
                    del owner.goods[name]
                break

    def _outcome_trick(self, m, intent, actor, defender, margin, weapon_key, loot, say):
        # The attacker's choice, subject to the GM — here the intent's `trick`, checked
        # against the six at parse; the gentlest when none was named.
        trick = str(intent.params.get("trick") or m["default_trick"]).strip().lower()
        if trick not in m["tricks"]:
            trick = m["default_trick"]
        rounds = 1 + max(0, margin) // 5
        defender.add_condition(trick, rounds=rounds,
                               source=f"{m['name']} by {actor.name}")
        return (say(m["effect"], False, trick=trick,
                    rounds=f"{rounds} round{'' if rounds == 1 else 's'}"), [],
                [{"ref": defender.ref, "kind": "condition", "condition": trick,
                  "rounds": rounds, "from": m["name"]}])

    # --- the moving four --------------------------------------------------------------

    def _both_on_the_map(self, a: Actor, b: Actor) -> bool:
        return (self.scene.has_grid and a.ref in self.scene.positions
                and b.ref in self.scene.positions)

    def _heading(self, from_ref: str, to_ref: str) -> tuple[int, int]:
        """One square's step from one creature toward the other."""
        a, b = self.scene.positions[from_ref], self.scene.positions[to_ref]
        dx, dy = b[0] - a[0], b[1] - a[1]
        step = ((dx > 0) - (dx < 0), (dy > 0) - (dy < 0))
        return step if step != (0, 0) else (1, 0)

    def _open_for(self, ref: str, square) -> bool:
        from .grid import footprint

        grid = self.scene.grid
        taken = self.scene.occupied(ignore=ref)
        return all(grid.passable(q) and q not in taken
                   for q in footprint(square, self.scene.actors[ref].size))

    def _put(self, ref: str, square) -> None:
        """Stand a creature on a square, keeping a flier's height (`settle_levels`
        puts everything else back on the floor)."""
        was = self.scene.positions[ref]
        self.scene.positions[ref] = tuple(square[:2]) + tuple(was[2:])

    def _push_line(self, ref: str, step: tuple[int, int], squares: int) -> int:
        """Move a creature square by square in a straight line until it has gone
        `squares` or the next square is wall or somebody. Returns squares moved.

        Forced movement provokes nothing — it does not go through `_op_move` and so
        not through `_reactions_before`, which is the book's rule without Greater Bull
        Rush."""
        moved = 0
        for _ in range(max(0, squares)):
            here = self.scene.positions[ref]
            nxt = (here[0] + step[0], here[1] + step[1])
            if not self._open_for(ref, nxt):
                break
            self._put(ref, nxt)
            moved += 1
        return moved

    def _moved(self, ref: str, before, m: dict) -> dict:
        from .grid import distance

        self.scene.settle_levels()
        self.scene.resync_zones()
        after = self.scene.positions[ref]
        return {"ref": ref, "kind": "position", "from": before, "to": after,
                "feet": distance(before[:2], after[:2]), "forced": m["name"],
                "zone": self.scene.zones.get(ref, "")}

    def _moved_clause(self, m, say, moved: int, want: int, feet: int) -> str:
        if moved == 0:
            return say(m["blocked"], False)
        return say(m["effect" if moved >= want else "short"], False, feet=feet)

    def _unmapped(self, m, actor, defender, want, say, breaks_reach: bool):
        """No map: the zones are the only record, and they are measured from the
        player. A push breaks melee reach (13th Age's "popping free"; no tradition
        found turns five feet into a whole zone), so a bull rush with the player on
        either end puts the other one `near`. Everything else keeps its zone."""
        effects = []
        pc = self.scene.pc()
        other = (defender if pc is actor else actor if pc is defender else None)
        if breaks_reach and other is not None and \
                self.scene.zones.get(other.ref) == "engaged":
            self.scene.zones[other.ref] = "near"
            effects.append({"ref": other.ref, "kind": "zone", "from": "engaged",
                            "to": "near", "forced": m["name"]})
        return say(m["effect"], False, feet=want * FEET_PER_SQUARE), [], effects

    def _outcome_push(self, m, intent, actor, defender, margin, weapon_key, loot, say):
        want = 1 + max(0, margin) // 5
        if not self._both_on_the_map(actor, defender):
            return self._unmapped(m, actor, defender, want, say, breaks_reach=True)
        before = self.scene.positions[defender.ref]
        moved = self._push_line(defender.ref, self._heading(actor.ref, defender.ref),
                                want)
        done = [self._moved(defender.ref, before, m)] if moved else []
        return (self._moved_clause(m, say, moved, want,
                                   done[0]["feet"] if done else 0), [], done)

    def _outcome_drag(self, m, intent, actor, defender, margin, weapon_key, loot, say):
        want = 1 + max(0, margin) // 5
        if not self._both_on_the_map(actor, defender):
            return self._unmapped(m, actor, defender, want, say, breaks_reach=False)
        # "You and the target move 5 feet directly away": the dragger backs off first,
        # and the dragged follows into the ground it leaves, no further than it went.
        step = self._heading(defender.ref, actor.ref)
        a_before, d_before = (self.scene.positions[actor.ref],
                              self.scene.positions[defender.ref])
        went = self._push_line(actor.ref, step, want)
        followed = self._push_line(defender.ref, step, went)
        done = []
        if went:
            done.append(self._moved(actor.ref, a_before, m))
        if followed:
            done.append(self._moved(defender.ref, d_before, m))
        return (self._moved_clause(m, say, followed, want,
                                   done[-1]["feet"] if followed else 0), [], done)

    def _outcome_shift(self, m, intent, actor, defender, margin, weapon_key, loot, say):
        from . import reactions
        from .grid import distance, distance_between

        want = 1 + max(0, margin) // 5
        if not self._both_on_the_map(actor, defender):
            return self._unmapped(m, actor, defender, want, say, breaks_reach=False)
        grid = self.scene.grid
        here = self.scene.positions[defender.ref]
        mine = self.scene.positions[actor.ref]
        # Within reach, but for the last five feet, which may end just past it.
        reach = reactions._reach_of(actor) + FEET_PER_SQUARE
        budget = want * FEET_PER_SQUARE

        def allowed(q) -> bool:
            q = tuple(q[:2])
            return (q != tuple(here[:2]) and grid.inside(q)
                    and distance(here[:2], q) <= budget
                    and distance_between(mine, actor.size, q, defender.size) <= reach
                    and self._open_for(defender.ref, q))

        asked = intent.params.get("square")
        if asked is not None and allowed(tuple(asked)):
            dest = tuple(asked[:2])
        else:
            options = [(distance(here[:2], (x, y)), y, x)
                       for x in range(here[0] - want, here[0] + want + 1)
                       for y in range(here[1] - want, here[1] + want + 1)
                       if allowed((x, y))]
            if not options:
                return say(m["blocked"], False), [], []
            _, y, x = min(options)
            dest = (x, y)
        self._put(defender.ref, dest)
        done = self._moved(defender.ref, here, m)
        return say(m["effect"], False, feet=done["feet"]), [], [done]

    def _outcome_pass(self, m, intent, actor, defender, margin, weapon_key, loot, say):
        from .grid import footprint

        if not self._both_on_the_map(actor, defender):
            return say(m["effect"], False), [], []
        # "You move through the target's space": to the first open square on the far
        # side of it, along the line of the charge. Never INTO its space — two bodies do
        # not share a square at the end of a move.
        step = self._heading(actor.ref, defender.ref)
        start = self.scene.positions[actor.ref]
        theirs = set(footprint(self.scene.positions[defender.ref], defender.size))
        for k in range(1, 8):
            q = (start[0] + step[0] * k, start[1] + step[1] * k)
            if set(footprint(q, actor.size)) & theirs:
                continue
            if self._open_for(actor.ref, q):
                self._put(actor.ref, q)
                return say(m["effect"], False), [], [self._moved(actor.ref, start, m)]
            break
        return say(m["blocked"], False), [], []

    _MANEUVER_OUTCOMES = {
        "drop": _outcome_drop, "take": _outcome_take, "trick": _outcome_trick,
        "push": _outcome_push, "drag": _outcome_drag, "shift": _outcome_shift,
        "pass": _outcome_pass,
    }

    def _ensure_encounter(self, initiator: str, target: str | None = None) -> bool:
        """Start a fight the moment someone swings, if one is not already running.
        Returns whether it opened one — the attack op defers its swing when it did.

        Measured in play: asked to attack, the GM emitted a bare `attack` intent and no
        `begin_encounter`. Initiative was never rolled, so nothing tracked turns and the
        NPC loop never ran — the guildhand took a rapier through the arm and the fight
        simply stopped. Relying on the GM to *remember* a bookkeeping step is the pattern
        this whole architecture exists to avoid, so the engine does it.

        The initiator keeps the turn they just took: they are the one who started it, and
        re-rolling them to the back of the order would take away the action they have
        already declared.
        """
        if self.scene.in_encounter:
            return False
        standing = [r for r, a in self.scene.actors.items() if not a.is_down]
        # Who the fight is WITH. Every standing non-player used to go on "them":
        # reported at the table with the map open, 2026-09-06, a servant who had
        # been standing beside the player was laid out on the enemy side of a fight
        # the player picked with a hooded man. The fight is between the initiator's
        # side and the one they swung at; everybody else is a bystander — on the map,
        # off the initiative, and painted so — until they join it themselves (an
        # NPC that attacks is added to a side by `_op_attack`).
        pc_side = [r for r in standing if self.scene.actors[r].is_pc]
        if initiator in self.scene.actors and not self.scene.actors[initiator].is_pc:
            # Opened from THEIR side (`struck_first`): the fight is between the one
            # who swung and the player. Every other non-player in the room used to
            # land on "them" here — the whole market against the player because one
            # man drew.
            them = [initiator]
        elif target and target in self.scene.actors and target not in pc_side:
            them = [target]
        else:
            # Nobody named: everyone standing who is not merely in the room.
            them = [r for r in standing if not self.scene.actors[r].is_pc
                    and not self.scene.actors[r].has_state(states.BYSTANDER)]
        combatants = pc_side + [r for r in them if r in standing]
        for r in them:
            self.scene.actors[r].remove_condition(states.BYSTANDER_KEY)
        if len(combatants) < 2:
            return False

        rolls = []
        for ref in combatants:
            a = self.scene.actors[ref]
            r = self.dice.d20(a.initiative_modifiers(), label=f"{a.name} initiative",
                              visibility="hidden")
            rolls.append((ref, r.total))
        rolls.sort(key=lambda t: -t[1])

        self.scene.initiative = rolls
        self.scene.round = 1
        self.scene.move_spent = {}
        self.end_talk("a fight starts")
        sides = {"pc": pc_side, "them": [r for r in them if r in standing]}
        self.scene.sides = sides
        self.scene.acted = {initiator}
        self.scene.turn = next(
            (i for i, (ref, _) in enumerate(rolls) if ref == initiator), 0
        )
        # The battlefield goes with the fight, whichever door the fight came in by.
        # This path skipped the grid entirely: a swing that auto-started an encounter
        # played on a map that said no ground was mapped.
        self._lay_battlefield(sides)
        if target:
            self.rally(target)
        self._law_joins()
        return True

    # Templates whose people fight for each other. A guard comes to a guard's aid; a
    # merchant does not draw for a merchant.
    FIGHTING_KINDS = frozenset({"watchman", "thug", "guard dog", "soldier", "bandit",
                                "mercenary", "bruiser"})

    def join_fight(self, ref: str, side: str = "them") -> bool:
        """A bystander enters the fight: rolled into the initiative, put on a side,
        on the board if they were not. The one door for everybody who joins late —
        the spawn op's arrival used to be the only one, and a person already in the
        room had no way in at all ("make bystanders join the fight when they
        should", 2026-09-06)."""
        a = self.scene.actors.get(ref)
        if a is None or not self.scene.in_encounter or a.is_down:
            return False
        if any(ref in refs for refs in self.scene.sides.values()):
            return False
        # Whoever walks through this door has stopped watching.
        a.remove_condition(states.BYSTANDER_KEY)
        init = self.dice.d20(a.initiative_modifiers(), label=f"{a.name} initiative",
                             visibility="hidden")
        # `enrol`, not an append and a sort: a newcomer who rolls above the turn-holder
        # sorts in ahead of them, and `turn` is an index (see `Scene.enrol`).
        self.scene.enrol(ref, init.total)
        self.scene.sides.setdefault(side, []).append(ref)
        if ref not in self.scene.positions and self.scene.grid is not None:
            self.scene.place_by_zone([ref])
        return True

    def struck_first(self, ref: str) -> list[Outcome]:
        """Somebody in the room swung at the player: the fight opens from THEIR side and
        their blow is rolled, before the player's next line.

        The mirror of the swing that auto-starts an encounter. Measured 2026-09-18, the
        ring fight: the man in the leather apron "lunges … tries to overwhelm your guard
        with a heavy, horizontal sweep" and the engine rolled nothing, because the only
        door into a fight from the world's side was the model's `begin_encounter` op and
        the model narrated instead — this project's oldest lesson. The player: "I should
        be put into combat when I am attacked, it shouldn't wait for me."

        Two runs of the same attack, on purpose. The first finds no fight, forms one
        (`_ensure_encounter`: sides drawn between him and the player only, initiative
        rolled, the grid laid, the initiator holding the turn) and stops at "battle is
        joined" — the first-swing gate, honoured from this side too. The second is his
        swing, with dice, resolved the way any NPC attack is; the tells go to the page
        as consequences. Then the NPC loop carries the order on to the player, who is
        flat-footed until they act, as 1e says of a combatant who has not yet taken a
        turn. Returns the outcomes, [] when nothing could open.
        """
        pc = self.scene.pc()
        a = self.scene.actors.get(ref)
        if (pc is None or a is None or a.is_pc or a.is_down
                or self.scene.in_encounter or pc.is_down):
            return []
        # Somebody who likes the player, or travels with them, does not swing on the
        # prose's word. Measured 2026-09-25: the detector read "The barmaid rushes over to
        # you with a tankard" as a blow and this door opened the fight and rolled her
        # attack. The detector is tighter now; this is the engine's own half, asked of
        # the state it holds rather than of a sentence — a friend who means harm has to
        # stop being a friend first, and that is a change the engine would have made.
        from . import attitude as attitude_mod

        if (a.has_state(states.TRAVELS_WITH_YOU)
                or attitude_mod.step_of(attitude_mod.of(a))
                >= attitude_mod.step_of(attitude_mod.COMES_ALONG)):
            return []
        raw = {"op": "attack", "actor": ref, "target": pc.ref,
               "because": f"{a.name} struck first"}
        # One run: the fight opens and, because the initiator is not the player, `run`
        # rolls their blow in the same batch (`_their_first_blow`). This used to run the
        # attack twice by hand, which is the rule `run` now keeps for every door.
        try:
            return list(self.run(self.validate([raw])).outcomes)
        except (IntentError, ValueError, KeyError):
            return []

    def rally(self, ref: str) -> list[str]:
        """The bystanders who come in on a foe's side when they are struck: the ones
        of their own kind. Same head noun — "guard" beside "guards", the pair the
        prose promoted together — or the same fighting template. Civilians stay out;
        a merchant watching from across the yard is not a second guard."""
        foe = self.scene.actors.get(ref)
        if foe is None or not self.scene.in_encounter:
            return []
        side = next((s for s, refs in self.scene.sides.items() if ref in refs), None)
        if side is None:
            return []

        def head(name: str) -> str:
            word = (str(name or "").split() or [""])[-1].lower()
            return word[:-1] if word.endswith("s") and len(word) > 3 else word

        kind = foe.from_template if foe.from_template in self.FIGHTING_KINDS else ""
        joined = []
        for other, b in list(self.scene.actors.items()):
            if other == ref or b.is_pc or b.is_down:
                continue
            if any(other in refs for refs in self.scene.sides.values()):
                continue
            same_name = head(b.name) == head(foe.name) and head(foe.name)
            same_kind = kind and b.from_template == kind
            if (same_name or same_kind) and self.join_fight(other, side):
                joined.append(other)
        return joined

    def _law_joins(self) -> list[str]:
        """The guards who come in against a wanted player when a fight starts in the
        town that wants them (docs/wanted.md, reader three).

        Through `join_fight`, the one door — the same one `rally` uses — so a guard
        joining arrives with an initiative roll, a side and a square like anybody else.
        Who counts as the law is the vocabulary's answer, `role.guard`, or the watchman
        template by kind; a merchant watching from the stall does not draw. The town is
        read off the ground the fight is on, so a warrant in the last town brings no
        guard in here, and only a bystander joins: a guard already on the player's side
        (an escort the GM sided) is left where they were put.

        Called from `_ensure_encounter`, the door a first swing opens the fight by. A
        fight the GM declares through `begin_encounter` names its own sides and is not
        second-guessed here — noted as open in docs/wanted.md.
        """
        from . import places as places_mod

        if not self.scene.in_encounter:
            return []
        town = places_mod.location_of(self.scene.at) or self.scene.location_id
        hunted = [r for r, a in self.scene.actors.items()
                  if a.is_pc and states.standing_with_the_law(a, town) == "wanted"]
        if not hunted:
            return []
        pc_side = next((s for s, refs in self.scene.sides.items()
                        if any(r in refs for r in hunted)), None)
        against = next((s for s in self.scene.sides if s != pc_side), "them")
        joined = []
        for ref, b in list(self.scene.actors.items()):
            if b.is_pc or b.is_down:
                continue
            is_law = b.has_state(states.GUARD)
            if is_law and self.join_fight(ref, against):
                joined.append(ref)
        return joined

    def _has_acted(self, ref: str) -> bool:
        """Whether this combatant has taken a turn in the current encounter."""
        return ref in self.scene.acted

    # damage, condition, move, time, spawn, encounter ------------------------------------

    def _op_damage(self, intent: Intent, partial: dict) -> Outcome:
        ref = intent.params.get("to") or (intent.targets() or [None])[0]
        if not ref:
            return self._refuse(intent, "The damage names nobody to land on, so none lands.")
        target = self.scene.actors[ref]
        amount = intent.params["amount"]
        roll = None
        if isinstance(amount, str):
            roll = self.dice.roll(amount, label="damage", visibility="hidden")
            value = roll.total
        else:
            value = int(amount)
        hit = self._apply_damage(target, value, intent.params["type"],
                                 lethality=str(intent.params.get("lethality", "lethal")))
        hit["origin"] = intent.origin
        effects = [hit]
        # Every creature the blow actually reached, which after interception is not always
        # the one it was aimed at. Keyed off the effects rather than off `target`, because
        # a redirected blow that drops the guardian has to knock *them* out.
        crossed = []
        for ref in self._hurt_refs(hit):
            crossed.extend(self._hp_state_effects(self.scene.actors[ref]))
        effects.extend(crossed)
        return Outcome(
            intent_id=intent.id, op="damage", rolls=[roll] if roll else [],
            effects=effects,
            tell=self._damage_tell(hit) + self._by(intent, ".") + self._hp_state_tell(crossed),
            because=intent.because,
        )

    def _op_hazard(self, intent: Intent, partial: dict) -> Outcome:
        """A fall, a fire, acid, cold: the rule rolls, the model only named it.

        Stage 8d's one new op. The row in content/rules/hazards.json declares its
        slot and its dice per unit; validate has already checked the slot against the
        row's bounds, so nothing here is a number the model wrote. The record carries
        `origin: rule:<id>` and the tell names the rule, the way a jar's heal names
        the jar.
        """
        ref = intent.params.get("to") or intent.actor or (intent.targets() or [None])[0]
        if not ref or ref not in self.scene.actors:
            return self._refuse(intent, "The hazard names nobody, so nobody is hurt by it.")
        target = self.scene.actors[ref]
        plan = hazards.plan(str(intent.params["rule"]), intent.params)
        origin = f"rule:{plan['rule']}"
        rolls, effects, bits = [], [], []
        if plan.get("first_die_nonlethal"):
            roll = self.dice.roll(plan["first_die"], label=f"{plan['name']} (deliberate)",
                                  visibility="hidden")
            rolls.append(roll)
            hit = self._apply_damage(target, roll.total, plan["type"], lethality="nonlethal")
            hit["origin"] = origin
            effects.append(hit)
        if plan.get("dice"):
            roll = self.dice.roll(plan["dice"], label=plan["name"], visibility="hidden")
            rolls.append(roll)
            hit = self._apply_damage(target, roll.total, plan["type"],
                                     lethality=plan["lethality"])
            hit["origin"] = origin
            effects.append(hit)
        for hit in list(effects):
            bits.append(self._damage_tell(hit))
        crossed = []
        for ref2 in {e["ref"] for e in effects if e.get("kind") == "damage"}:
            crossed.extend(self._hp_state_effects(self.scene.actors[ref2]))
        effects.extend(crossed)
        tell = (f"{target.name} meets {plan['name']} ({plan['slot'].replace('_', ' ')} "
                f"{plan['value']}; the rule rolls {plan.get('first_die', '')}"
                f"{'+' if plan.get('first_die') and plan.get('dice') else ''}"
                f"{plan.get('dice', '')}). " + " ".join(bits)
                + self._hp_state_tell(crossed))
        return Outcome(intent_id=intent.id, op="hazard", rolls=rolls, effects=effects,
                       tell=" ".join(tell.split()), because=intent.because)

    @staticmethod
    def _by(intent: Intent, sep: str = "") -> str:
        """The clause that names the document behind a number, for the tell.

        Law 3 is only half kept by a sourced number whose source the narrator cannot
        see: the heal, damage, ability-damage and item-damage tells named nothing
        before stage 8, so the narrator could not have said what healed. `sep` is
        what to put in front when the tell already ended with a full stop.
        """
        if not intent.origin_name:
            return ""
        return f"{sep} from {intent.origin_name}" if sep else f" from {intent.origin_name}"

    def _hurt_refs(self, head: dict) -> list[str]:
        refs = [head["ref"]]
        for extra in head.get("also", []):
            if extra["ref"] not in refs:
                refs.append(extra["ref"])
        return refs

    def _damage_tell(self, head: dict) -> str:
        """Who took what — naming whoever actually took it.

        Built from the effects rather than from the intent's target. Saying "the companion
        takes 12" when a guardian threw themselves in front of it is a lie the player has
        no way to catch, and it was the first thing interception broke.
        """
        def one(e: dict) -> str:
            who = self.scene.actors[e["ref"]].name
            note = f" ({e['note']})" if e["note"] else ""
            # "hits for 0" is technically true and reads as a miss. A ward that ate the
            # blow whole is a thing that happened, and the player paid for it.
            if e["amount"] == 0 and e.get("intercepted"):
                return f"nothing reaches {who}{note}"
            kind = e["type"] + (" non-lethal" if e["lethality"] == "nonlethal" else "")
            return f"{who} takes {e['amount']} {kind} damage{note}"

        parts = [one(head)] + [one(e) for e in head.get("also", [])]
        return "; ".join(parts) + "."

    def _op_defence(self, intent: Intent, partial: dict) -> Outcome:
        """Grant damage reduction, immunity, energy resistance or vulnerability.

        The op the four types never had. `effectspec` has offered them since it was
        written and its own `blocked` text admitted the consequence — "nothing wears off
        yet, so nothing is granted temporarily" — so a potion of fire resistance was
        drunk, the dose was spent, and `_spec_to_intents` returned an empty list.
        """
        target = self.scene.actors.get(intent.params.get("to") or intent.actor or "")             or self.scene.pc()
        if target is None:
            raise IntentError("defence: nobody here to protect", "refs")
        kind = str(intent.params["kind"])
        against = str(intent.params.get("against", ""))
        amount = int(intent.params.get("amount", 0) or 0)
        bypass = str(intent.params.get("bypass", "") or "")
        source = str(intent.params.get("source") or "a preparation")
        rounds = _rounds_from(intent.params.get("duration"))
        target.grant_defence(kind, against, amount=amount, bypass=bypass,
                             source=source, rounds=rounds, origin=intent.origin)
        said = {
            "damage_reduction": f"damage reduction {amount}/{bypass or '—'}",
            "immunity": f"immunity to {against}",
            "resistance": f"resistance {amount} to {against}",
            "vulnerability": f"vulnerability to {against}",
        }[kind]
        return Outcome(
            intent_id=intent.id, op="defence",
            effects=[{"ref": target.ref, "kind": "defence", "defence": kind,
                      "against": against, "amount": amount, "rounds": rounds,
                      "origin": intent.origin}],
            tell=f"{target.name} has {said}" + (
                f" for {rounds} round(s)." if rounds else " while it lasts."),
            because=intent.because)

    def _op_buff(self, intent: Intent, partial: dict) -> Outcome:
        """A timed numeric bonus lands on an actor.

        The op `use_item` was missing: a drunk tea's `save_mod` fell through
        `_spec_to_intents` and the dose was spent for nothing. Duration arrives in the
        authored unit and is kept in rounds, the clock every other timed thing ticks on.
        """
        who = intent.params.get("to") or intent.actor
        actor = self.scene.actors.get(who)
        if actor is None:
            return self._refuse(intent, self._elsewhere(who) or f"There is no {who} here to affect.")
        kind = str(intent.params.get("type", "save_mod"))
        target = str(intent.params.get("target", ""))
        amount = int(intent.params.get("amount", 0) or 0)
        if not target or not amount:
            return self._refuse(intent, "The bonus names nobody, or nothing, so nothing changes.")
        source = str(intent.params.get("source") or "a preparation")
        duration = intent.params.get("duration") or {}
        rounds = None
        if isinstance(duration, dict) and duration.get("amount"):
            per = {"round": 1, "minute": 10, "hour": 600, "day": 14400}
            rounds = int(duration["amount"]) * per.get(str(duration.get("unit", "hour")), 600)
        actor.add_buff(kind, target, amount, source=source, rounds=rounds,
                       note=str(intent.params.get("note", "")),
                       bonus_type=str(intent.params.get("bonus_type", "")),
                       origin=intent.origin)
        span = ""
        if rounds:
            span = f" for {rounds // 600} hour(s)" if rounds >= 600 else \
                   f" for {rounds // 10} minute(s)" if rounds >= 10 else \
                   f" for {rounds} round(s)"
        return Outcome(
            intent_id=intent.id, op="buff",
            effects=[{"ref": actor.ref, "kind": "buff", "type": kind, "target": target,
                      "amount": amount, "rounds": rounds, "source": source,
                      "origin": intent.origin}],
            tell=f"{actor.name} gains {amount:+d} {target}{span} ({source}).",
            because=intent.because,
        )

    def _op_heal(self, intent: Intent, partial: dict) -> Outcome:
        """Restore hit points. Not damage with the sign flipped.

        Two 1e rules live here and both are easy to lose: healing never restores
        temporary hit points, and it stops at your maximum rather than banking the
        overflow. `Actor.heal` owns both so nothing else has to remember them.
        """
        ref = intent.params.get("to") or intent.actor or (intent.targets() or [None])[0]
        if not ref:
            return self._refuse(intent, "The healing names nobody, so nobody is healed.")
        target = self.scene.actors[ref]
        amount = intent.params["amount"]
        roll = None
        if isinstance(amount, str):
            roll = self.dice.roll(amount, label="healing", visibility="hidden")
            amount = roll.total

        nl_before = target.nonlethal
        temp_before = sum(p.amount for p in target.temp_pools)
        healed = target.heal(amount)
        nl_healed = nl_before - target.nonlethal
        temp_banked = sum(p.amount for p in target.temp_pools) - temp_before
        # The dying stop dying when they are back above zero; nothing else clears it.
        # `dead` is deliberately outside this family — resurrection is the only caller
        # entitled to remove it, and one shared list either breaks that or lets cure
        # light wounds raise a corpse.
        lifted = target.clear_states("recovery.hit-points") if target.hp > 0 else []

        # The tell owns everything the cure did. "Already unhurt" used to be the whole
        # sentence for a Blood Bender at full hit points, while the same drink was
        # quietly clearing their non-lethal — the resource their entire class spends —
        # and banking the spare as temporary hit points. A cure that lies about two of
        # its three effects reads as a cure that did nothing.
        parts = []
        if healed:
            parts.append(f"recovers {healed} hit points "
                         f"({target.hp}/{target.hp_max})")
        if nl_healed:
            parts.append(f"shakes off {nl_healed} non-lethal"
                         + (f" ({target.nonlethal} remains)" if target.nonlethal else ""))
        if temp_banked:
            parts.append(f"banks {temp_banked} as temporary vitality")
        tell = (f"{target.name} " + ", ".join(parts) + self._by(intent) + "."
                if parts else f"{target.name} is already unhurt.")
        # Coming back is the half a cure is FOR, and it was silent in both channels: the
        # effects list said `heal` and nothing else, and the tell counted hit points
        # while saying nothing about the dying stopping. Law 3 asks a removal to emit
        # its tell exactly as an application does.
        if lifted:
            # Ordered and joined the way the application tell says them, so "is
            # unconscious and dying" is undone by "is no longer unconscious and dying"
            # rather than by a semicolon-separated list of game words.
            order = ("unconscious", "dying", "stable", "disabled")
            back = sorted(lifted, key=lambda k: (order.index(k) if k in order else 9, k))
            tell += (f" {target.name} is no longer "
                     f"{' and '.join(back)}.")

        return Outcome(
            intent_id=intent.id, op="heal", rolls=[roll] if roll else [],
            effects=[{"ref": target.ref, "kind": "heal", "amount": healed,
                      "nonlethal_healed": nl_healed, "temp_banked": temp_banked,
                      "hp_after": target.hp, "hp_max": target.hp_max,
                      "origin": intent.origin}]
                    + [{"ref": target.ref, "kind": "condition", "condition": k,
                        "ends": True} for k in lifted],
            tell=tell,
            because=intent.because,
        )

    def _op_temp_hp(self, intent: Intent, partial: dict) -> Outcome:
        """Grant temporary hit points, which do not stack — the best source wins."""
        ref = intent.params.get("to") or intent.actor or (intent.targets() or [None])[0]
        if not ref:
            return self._refuse(intent, "The temporary hit points name nobody, so nobody gets them.")
        target = self.scene.actors[ref]
        amount = intent.params["amount"]
        roll = None
        if isinstance(amount, str):
            roll = self.dice.roll(amount, label="temporary hit points", visibility="hidden")
            amount = roll.total

        source = str(intent.params.get("source") or intent.because or "").strip()
        result = target.gain_temp_hp(amount, source, origin=intent.origin)
        if "ignored" in result:
            tell = (f"{target.name} already has {result['temp_hp']} temporary hit points "
                    f"from {result['source'] or 'another source'}; these do not stack.")
        else:
            tell = f"{target.name} gains {result['temp_hp']} temporary hit points."
        return Outcome(
            intent_id=intent.id, op="temp_hp", rolls=[roll] if roll else [],
            effects=[{"ref": target.ref, "kind": "temp_hp", "temp_hp": target.temp_hp,
                      "origin": intent.origin}],
            tell=tell, because=intent.because,
        )

    def _op_ability_damage(self, intent: Intent, partial: dict) -> Outcome:
        """Damage to a score rather than to hit points.

        Constitution carries hit points with it, and a score reduced to 0 has its own
        consequence — which for Constitution is death by a route `apply_hp_state` cannot
        see, since the character may be at full health when it happens.
        """
        ref = intent.params.get("to") or intent.target or intent.actor
        if not ref:
            return self._refuse(intent, "The ability damage names nobody, so none lands.")
        target = self.scene.actors[ref]
        ab = str(intent.params["ability"]).strip().lower()[:3]
        amount = intent.params["amount"]
        roll = None
        if isinstance(amount, str):
            roll = self.dice.roll(amount, label=f"{ab.upper()} damage", visibility="hidden")
            amount = roll.total

        drain = bool(intent.params.get("drain"))
        try:
            res = target.damage_ability(ab, amount, drain=drain)
        except KeyError:
            # The six are always the six; the message used to name the fault and not
            # them.
            return self._refuse(
                intent, f"No ability score called {ab}. The six are: "
                        f"{', '.join(ABILITY_FULL)}.")

        effects = [{"ref": target.ref, "kind": "ability_damage", **res,
                    "origin": intent.origin}]
        bits = [f"{target.name} takes {res['amount']} {ABILITY_FULL[ab]} "
                f"{'drain' if drain else 'damage'} (now {res['score']})"
                f"{self._by(intent)}."]
        if res["hp_change"]:
            bits.append(f"Hit points {res['hp_change']:+d} "
                        f"({target.hp}/{target.hp_max}).")
        for c in target.ability_zero_effects():
            effects.append({"ref": target.ref, "kind": "condition", "condition": c,
                            "from": f"{ABILITY_FULL[ab]} 0"})
            bits.append(f"{target.name} is {c}.")
        return Outcome(
            intent_id=intent.id, op="ability_damage", rolls=[roll] if roll else [],
            effects=effects, tell=" ".join(bits), because=intent.because,
        )

    def _op_item_damage(self, intent: Intent, partial: dict) -> Outcome:
        """Damage to gear. Named item, or everything carried when none is named."""
        ref = intent.params.get("to") or intent.target or intent.actor
        if not ref or ref not in self.scene.actors:
            # A refusal, never a raise: validation only requires `amount`, so this
            # op can arrive aimed at nobody — and did, live, mid-turn, where the
            # raise threw away the whole resolved turn as a 502. Whose gear wears
            # is a fact the GM failed to state; nothing is the honest resolution.
            return Outcome(
                intent_id=intent.id, op="item_damage", effects=[],
                tell="Nobody's gear is named, so nothing takes the wear.",
                because=intent.because)
        target = self.scene.actors[ref]
        amount = intent.params["amount"]
        roll = None
        if isinstance(amount, str):
            roll = self.dice.roll(amount, label="item damage", visibility="hidden")
            amount = roll.total
        dtype = intent.params.get("type", "untyped")

        named = intent.params.get("item")
        results = ([target.damage_item(str(named), amount, dtype)] if named
                   else target.damage_all_gear(amount, dtype))
        # Only say something about the gear that actually changed. A list of eleven items
        # that all shrugged it off buries the one that did not.
        notable = [r for r in results if r["taken"]]
        bits = []
        for r in notable:
            state = ("destroyed" if r["destroyed"] else
                     "broken" if r["broken"] else f"{r['hp']}/{r['hp_max']}")
            bits.append(f"{target.name}'s {r['item']}: {r['taken']} through hardness "
                        f"{r['hardness']} — {state}.")
        if not bits:
            bits.append(f"Nothing {target.name} carries is marked by it.")
        if intent.origin_name:
            bits.append(f"The cause: {intent.origin_name}.")
        return Outcome(
            intent_id=intent.id, op="item_damage", rolls=[roll] if roll else [],
            effects=[{"ref": target.ref, "kind": "item_damage", **r,
                      "origin": intent.origin} for r in results],
            tell=" ".join(bits), because=intent.because,
        )

    def _check_move(self, intent: Intent, index: int) -> None:
        """A square is a claim about geometry, and geometry is checkable.

        Every refusal here names the square and the number, because "you can't move there"
        with no distance in it is the kind of GM ruling this whole engine exists to
        replace. Outside an encounter nobody counts squares — walking across a village is
        not a tactical decision — so the speed limit applies only in a fight.
        """
        ref = intent.params.get("who") or intent.actor
        actor = self.scene.get(ref)
        target = tuple(intent.params["square"])

        if not self.scene.has_grid:
            raise IntentError(
                f"move: this scene has no map, so {target} means nothing. Move by zone "
                f"instead.", "legality", index,
            )
        if actor is None:
            raise IntentError(f"move: no such actor {ref!r}", "reference", index)

        grid = self.scene.grid
        occupied = self.scene.occupied(ignore=ref)
        if not grid.inside(target):
            raise IntentError(
                f"move: {target} is off the map, which is {grid.width} by {grid.height} "
                f"squares.", "legality", index,
            )
        for square in gridmod.footprint(target, actor.size):
            if not grid.passable(square):
                raise IntentError(
                    f"move: {actor.name} cannot stand at {target} — {square} is solid.",
                    "legality", index,
                )
            if square in occupied:
                raise IntentError(
                    f"move: {actor.name} cannot stand at {target} — {square} is taken.",
                    "legality", index,
                )

        start = self.scene.positions.get(ref)
        if start is None or not self.scene.in_encounter:
            return

        budget = actor.speed_feet
        routes = grid.reachable(start, budget, size=actor.size, occupied=occupied)
        if target in routes:
            return
        # Distinguish "too far" from "no way through". They lead to different next moves:
        # one wants a double move, the other wants a different route.
        anywhere = grid.reachable(start, 10_000, size=actor.size, occupied=occupied)
        if target in anywhere:
            raise IntentError(
                f"move: {target} is {anywhere[target]} ft away by the shortest open route "
                f"and {actor.name} has {budget} ft of movement.", "legality", index,
            )
        raise IntentError(
            f"move: there is no route from {start} to {target} that {actor.name} fits "
            f"through.", "legality", index,
        )

    def _check_craft(self, intent: Intent, index: int) -> None:
        """Refuse work the character cannot do, before any of it is scored.

        Both of these have to happen in validation rather than resolution. An unknown
        track resolved is a `KeyError` out of the engine's middle; a recipe above the
        character's level *scored* is a track levelling itself on work it has neither the
        tools nor the methods to attempt.
        """
        try:
            track = worldclass.get(str(intent.params.get("track", "")))
        except KeyError as exc:
            raise IntentError(f"craft: {exc}", "refs", index) from exc

        who = intent.actor or (self.scene.pc().ref if self.scene.pc() else None)
        actor = self.scene.actors.get(who) if who else None
        if actor is None:
            raise IntentError("craft: nobody here to do the work", "refs", index)

        tier = intent.params.get("tier")
        if not tier:
            return
        level = actor.track(track.id).level
        ceiling = track.at(level).max_tier

        # What the ceiling governs is the material the character *works*, not the band
        # the result comes out at. For every ordinary chain those are the same thing, so
        # the distinction never showed — until concentration, which is the one craft
        # designed to hand back something rarer than anything that went in. `crafting.
        # _concentration` checks the input and lets the output climb; this checked the
        # output. Two copies of one rule, disagreeing, and the disagreement was visible
        # in the app: /api/craft/preview returned 200 with a real percentage and
        # /api/craft/do answered 400 on the identical chain. That killed the ladder at
        # every rung above the crafter's own band, including the rung that reaches
        # legendary — which is the deed Herbalist 5 waits on.
        worked = worldclass.tier_rank(str(tier))
        if intent.params.get("concentrating"):
            worked -= crafting.CONCENTRATE_RARITY_STEP

        if worked > worldclass.tier_rank(ceiling):
            needed = next(l.level for l in sorted(track.levels, key=lambda x: x.level)
                          if worldclass.tier_rank(l.max_tier) >= worked)
            raise IntentError(
                f"craft: {track.name} {level} works {ceiling} at best, and "
                f"{intent.params.get('recipe', 'this')} is {tier}. "
                f"Reach {track.name} {needed} first.",
                "legality", index,
            )

    def _op_craft(self, intent: Intent, partial: dict) -> Outcome:
        """A session at a world class. Scores it, and advances the track if it is earned.

        The GM says what was attempted and how hard it was; the engine owns the mastery
        arithmetic and the level. Same line as everywhere else — the GM supplies what the
        fiction determines, the engine supplies what the sheet determines.
        """
        who = intent.actor or (self.scene.pc().ref if self.scene.pc() else None)
        actor = self.scene.actors.get(who) if who else None
        if actor is None:
            raise IntentError("craft: nobody here to do the work", "refs")

        track_id = str(intent.params["track"]).strip().lower()
        track = worldclass.get(track_id)
        progress = actor.track(track_id)
        was = progress.level
        recipe = str(intent.params["recipe"]).strip()
        tier = str(intent.params.get("tier") or track.at(progress.level).max_tier)

        result = worldclass.award(
            track, progress, recipe_id=recipe.lower(), tier=tier,
            success=not intent.params.get("failed"),
            risky=bool(intent.params.get("risky")),
            stages=int(intent.params.get("stages", 1) or 1),
            milestone=str(intent.params.get("milestone") or ""),
        )

        bits = []
        if intent.params.get("failed"):
            bits.append(f"The {recipe} is spoiled.")
        if result["mp"]:
            terms = ", ".join(f"{r['mp']} {r['why']}" for r in result["reasons"])
            bits.append(f"{actor.name} gains {result['mp']} mastery ({terms}).")
        elif not intent.params.get("failed"):
            bits.append(f"{recipe} is beneath a {track.name} of {was} now; "
                        f"there is nothing left in it to learn.")
        for lvl in result["levelled"]:
            gained = track.at(lvl)
            bits.append(f"{actor.name} is {track.name} {lvl}. "
                        f"Unlocked: {', '.join(gained.methods)}"
                        + (f"; tools: {', '.join(gained.tools)}" if gained.tools else "")
                        + f". Now works up to {gained.max_tier}.")
        if result["to_next"] and result["to_next"].get("milestone"):
            bits.append(f"{track.name} {progress.level + 1} also waits on "
                        f"{result['to_next']['milestone']}.")

        return Outcome(
            intent_id=intent.id, op="craft",
            effects=[{"ref": actor.ref, "kind": "craft", **result, "was": was}],
            tell=" ".join(bits), because=intent.because,
        )

    def _op_resource(self, intent: Intent, partial: dict) -> Outcome:
        """Spend or grant a pool.

        `to` rather than `actor` when it lands on somebody else, because a blood stack
        sits on the creature it was applied to and is spent by whoever put it there — the
        resource does not belong to its owner.
        """
        ref = intent.params.get("to") or intent.actor \
            or (self.scene.pc().ref if self.scene.pc() else None)
        target = self.scene.actors.get(ref) if ref else None
        if target is None:
            raise IntentError("resource: nobody to spend it from", "refs")

        pool_id = str(intent.params["pool"]).strip().lower()
        amount = intent.params.get("amount", 1)
        roll = None
        if isinstance(amount, str) and not amount.lstrip("-").isdigit():
            roll = self.dice.roll(amount, label=pool_id, visibility="hidden")
            amount = roll.total
        amount = int(amount)

        if intent.params.get("spend"):
            result = target.spend_pool(pool_id, amount)
            if not result["ok"]:
                # Refused out loud, not silently ignored: an ability that fires with an
                # empty pool is one the player thinks they still have. And printed, not
                # raised: this was `resource: no fury to spend.` as a 502 — the identical
                # sentence whether the pool was empty or had never existed, which is
                # the contract's own worked example of the message it forbids. Two
                # refusals now, because "not any more" and "no such thing" lead to
                # different next moves.
                if target.pool(pool_id) is None:
                    have = ", ".join(sorted(target.pools)) or "none"
                    return self._refuse(
                        intent, f"No pool called {pool_id!r} on {target.name}. Their "
                                f"pools are: {have}.")
                return self._refuse(
                    intent, f"{target.name} cannot spend {amount} {pool_id}: "
                            f"{result['why']}.")
            cooldown = intent.params.get("cooldown")
            if cooldown:
                rolled = self.dice.roll(str(cooldown), label=f"{pool_id} cooldown",
                                        visibility="hidden")
                target.start_cooldown(pool_id, rolled.total)
                roll = roll or rolled
            tell = (f"{target.name} spends {amount} {pool_id} "
                    f"({result['current']} left).")
        else:
            now = target.gain_pool(pool_id, amount, source=intent.because)
            tell = f"{target.name} gains {amount} {pool_id} ({now})."

        pool = target.pool(pool_id)
        return Outcome(
            intent_id=intent.id, op="resource", rolls=[roll] if roll else [],
            effects=[{"ref": target.ref, "kind": "resource",
                      **(pool.as_dict() if pool else {"id": pool_id})}],
            tell=tell, because=intent.because,
        )

    def tidy_the_fallen(self, grace: int = 2) -> list[str]:
        """Bodies age out of the scene on their own after a short grace.

        Two turns is time to loot and say a word over them; after that the dead
        depart quietly, whether or not the player ever walks away. The dying get
        the same treatment as `leave_behind`: their story resolves rather than
        printing "bleeding out" beats forever — and whoever comes out of it alive,
        stable or merely unconscious, stays. No-op mid-encounter.
        """
        if self.scene.in_encounter:
            return []
        tells: list[str] = []
        # The STORE: a body the party walked away from still leaves after its grace,
        # rather than lying in a room nobody will re-enter for the rest of the campaign.
        # The two-turn grace is why a fresh corpse is still in the VIEW meanwhile —
        # loot, heat, the finishing-blow check and the dead-men-walking cut all read it
        # there — and death does not move anybody, so it is.
        for ref in list(self.scene.people):
            a = self.scene.people[ref]
            # `state.down.fallen`, not the whole family: petrified and helpless are
            # down and alive, and asking the family aged a petrified enemy out of the
            # scene as a corpse two turns after the fight — statue, treasure and all.
            # A body on the floor, which exactly 0 hit points is not — that is
            # *disabled*: conscious, upright and taking turns, and it was being aged
            # out of the scene as a corpse.
            if a.is_pc or not (a.hp < 0 or a.has_state("state.down.fallen")):
                self.scene.fallen.pop(ref, None)
                continue
            age = self.scene.fallen.get(ref, 0) + 1
            self.scene.fallen[ref] = age
            if age > grace:
                if a.has_condition("dying"):
                    tells.extend(self._resolve_dying(a))
                # Only a corpse leaves. Measured 2026-09-25: unconscious and stable carry
                # `state.down.fallen` beside dead, so an NPC knocked out with non-lethal
                # damage — at full hit points — departed the campaign after three calls
                # with no tell at all, and so did a dying man who stabilised on the roll
                # just above. A prisoner, a spared thug and a fallen companion are all
                # still somebody; they stay where they lie until they wake or die.
                if a.has_state("state.down.dead"):
                    self.scene.depart(ref)
                self.scene.fallen.pop(ref, None)
        return tells

    def breathe(self) -> list[str]:
        """Everybody underwater holds their breath, and then stops being able to.

        The Core Rulebook's drowning rule, which is three sentences and a cliff: you hold
        your breath for twice your Constitution in rounds; after that it is a Constitution
        check each round at DC 10, rising by one every round; and on the first failure you
        are unconscious at 0, the next round dying at -1, and the round after that dead.

        There is no save against the last part and that is deliberate on the book's side —
        drowning is the one death in the game that arrives on a schedule. What the engine
        owes the player is that the schedule be visible, so every rung tells.

        Called where `tidy_the_fallen` is called, for the same reason: it is the engine
        resolving something that happens to a body while nobody is acting on it.
        """
        tells: list[str] = []
        for a in list(self.scene.people.values()):
            if not _drowning_ground(a) or a.has_state("state.down.dead"):
                continue
            limit = water.breath_rounds(a)
            if a.held_breath_rounds <= limit and not a.drown_failures:
                continue
            if not a.drown_failures:
                # Still trying to hold it. One check a round, one harder each time.
                dc = water.drown_dc(a.drown_failures)
                roll = self.dice.d20([Modifier(a.ability_mod("con"), "Con")],
                                     label=f"{a.name} holds their breath (DC {dc})",
                                     visibility="hidden")
                if roll.total >= dc:
                    tells.append(f"{a.name} holds on.")
                    continue
                # No condition is written here, and that is the point: the book does
                # not have a "drowning" condition, it has a schedule that writes
                # unconscious, then dying, then dead — all three of which
                # `apply_hp_state` derives from hit points already. The suite caught the
                # invention four separate ways (not in Appendix 2, no tag entry, helpless
                # but able to act, and one more literal condition key in this file than
                # the ceiling allows), which is the vocabulary law doing exactly its job.
                # The schedule lives in a counter; the states are the book's own.
                a.drown_failures = 1
                a.hp = 0
                # And `apply_hp_state` reads `drown_failures` to know that this
                # particular 0 is unconscious rather than disabled — the rule lives with
                # the other hit-point thresholds, which is both where it belongs and the
                # only way to write it without adding a literal condition name to this
                # file. The three laws hold the count here to a ceiling that may only
                # fall, and they are right to.
                tells.extend(f"{a.name} " + t for t in
                             ["breathes water, and goes limp."])
                a.apply_hp_state()
                continue
            # Past the first failure it is not a check any more, it is a countdown.
            a.drown_failures += 1
            if a.drown_failures == 2:
                a.hp = -1
                a.apply_hp_state()
                tells.append(f"{a.name} is dying, and nobody down here can help them.")
            else:
                a.hp = -max(1, a.ability_score("con"))
                a.apply_hp_state()
                tells.append(f"{a.name} has drowned.")
        return tells

    def _resolve_dying(self, a: Actor) -> list[str]:
        """One dying creature's story ends off-screen: stable, or gone."""
        floor = -a.ability_score("con")
        while a.hp > floor and a.has_condition("dying"):
            if self.dice.roll("1d100", label="stabilise",
                              visibility="hidden").total <= 10:
                a.remove_condition("dying")
                a.add_condition("stable", source="luck")
                break
            a.hp -= 1
        a.apply_hp_state()
        return [f"{a.name} "
                + ("stabilises where they lie."
                   if a.has_condition("stable")
                   else "has bled out where they fell.")]

    def _stays_in_the_world(self, actor) -> bool:
        """Whether somebody left behind by a journey goes on existing where they are.

        Until 2026-09-27 the road out destroyed everybody who did not come along, and
        coming back met strangers: measured, a woman met at the gate (Soren Kragnirath,
        regard 70) was Korvin Korvath at regard 35 two days later — the record kept her
        face and life, and the name and the standing lived on the body the road had
        destroyed. Kept now: anybody with a population record, a world character, anybody
        holding a standing with the player. RimWorld's world pawns are the precedent — kept
        for a reason, the rest let go — and so are its reasons: kin, memory, relationship.
        A spawned creature with none of those (the wolves, a hired thug) still goes, and the
        dead go as they always did.
        """
        from . import attitude as attitude_mod
        from . import population

        if actor.has_state("state.down.dead"):
            return False
        return bool(population.of_ref(self.scene, actor.ref)
                    or getattr(actor, "world_entity_id", None)
                    or attitude_mod._regard_effect(actor) is not None)

    def _keeper_goes(self, a, here_loc: str) -> bool:
        """Move a stall's keeper home when the counter shuts and back when it opens —
        to their own house once the party has called there (`_home_of`) — and a
        character the world wrote between their house and their day, once they have one.
        """
        from . import keepers
        from . import places as places_mod
        from . import residency

        wid = str(getattr(a, "world_entity_id", "") or "")
        if not wid or a.is_down or a.has_state(states.TALKING):
            return False
        callee = self._callee_of_body(a)
        house = self._house_of(callee)
        if keepers.is_keeper(wid):
            place = keepers.place_of(wid)
            if places_mod.location_of(place) != here_loc or keepers.lives_in(place):
                return False
            allowed = {place, residency.offstage(here_loc, f"home-{a.ref}")}
            if house is not None:
                allowed.add(house["id"])
            if a.at not in allowed:
                return False     # somewhere the plan took them; theirs to come back from
        elif house is None or places_mod.location_of(house["id"]) != here_loc:
            return False
        target = self._callee_place_now(callee)
        if not target or target == a.at:
            return False
        self.scene.move(a.ref, target)
        return True

    def settle_people(self) -> list[str]:
        """The party has arrived somewhere: everybody with a life goes where it puts them.

        Ultima VII's off-screen rule, confirmed in the Exult source
        (`teleport_offscreen_to_schedule`): nobody is walked to their slot, they are
        simply there. Asked once per arrival, never per turn and never on a clock — the
        same answer `population.where_now` gives the finder for people with no body, so a
        body and a record cannot disagree about where somebody is.

        Stays where they are: the party itself; whoever came along with it (`came_along`
        — the plan moved them, and they stay moved until the party leaves them); whoever
        the party has seen HERE since it arrived (the opening's own company, somebody
        introduced a minute ago); anybody down, helpless, held, travelling with the party,
        in conversation or in a fight; and anybody with no population record — a keeper
        at their counter, a world character, a thug the plan spawned. Returns the refs
        moved.
        """
        from . import places as places_mod
        from . import population
        from . import residency

        scene = self.scene
        if scene.settled == scene.moves:
            return []
        scene.settled = scene.moves
        came = set(scene.came_along)
        scene.came_along = []
        by_ref = {r.get("ref"): r for r in (scene.population or {}).values() if r.get("ref")}
        fighting = {ref for ref, _ in scene.initiative}
        moved: list[str] = []
        here_loc = scene.location_id
        for ref, a in list(scene.people.items()):
            rec = by_ref.get(ref)
            if a.is_pc or ref in came or ref in fighting:
                continue
            if rec is None:
                # A keeper keeps their counter's hours (rules/keepers.py): a stall in the
                # open is packed up and its keeper goes home; a keeper under a roof lives
                # on the premises and stays to be talked to, with the counter shut.
                if self._keeper_goes(a, here_loc):
                    moved.append(ref)
                continue
            if (a.at == scene.at
                    and int(rec.get("last_seen") or 0) >= int(scene.arrived or 0)):
                continue
            # A resident of another town lives their day where nobody is looking, and is
            # reckoned when the party is there; asking now would be the whole world's
            # bodies' cost on every arrival for an answer nobody reads — the finder asks
            # a body where it is only to the town.
            if (residency.mobility_of(rec) == "resident"
                    and places_mod.location_of(a.at) != here_loc):
                continue
            where = residency.whereabouts(rec, scene.clock_minutes, self.world,
                                          scene.founded)
            target = residency.place_for(where, rec)
            if not target or target == a.at:
                continue
            # The questions that cost (a state is asked of the whole sheet, race and
            # feats included: about a millisecond each, measured 2026-09-27) only of
            # somebody who would otherwise move.
            if (a.is_down or a.is_helpless or a.has_state("state.held")
                    or a.has_state(states.TRAVELS_WITH_YOU)
                    or a.has_state(states.TALKING)):
                continue
            # Living their day, they ate, drank and slept. The clock's one door charges
            # every body it holds (`Scene.advance`), and a baker the party left for a
            # month would otherwise come back into the room a month hungry. NetHack's
            # catch-up is the shape: settled once, when they are next reckoned.
            a.awake_minutes = a.fed_minutes = a.watered_minutes = 0
            scene.move(ref, target)
            moved.append(ref)
            if a.at == scene.at:
                population.seen(scene, rec)
        # The moves above are residency's own, not the plan's.
        scene.came_along = []
        return moved

    def leave_behind(self) -> list[str]:
        """The player says they are leaving: the dying here run their course.

        This used to shed the down family as well — and `clear_cast` after it shed the
        promoted civilians — because a room had no way to keep its people. It has one
        now: walking out is a `travel`, the room keeps everyone in it, and the party's
        view simply stops containing them. What is left of this door is the story
        beat: the dying resolve (1e's own odds — stabilise on the way down or bleed out
        at a point a round) before the party is out of earshot, so nobody bleeds out in
        silence two rooms away. Departs nobody. No-op mid-encounter — you do not walk
        out of an initiative order.
        """
        if self.scene.in_encounter:
            return []
        tells: list[str] = []
        for a in list(self.scene.actors.values()):
            if a.is_pc:
                continue
            if a.has_condition("dying"):
                tells.extend(self._resolve_dying(a))
        return tells

    def _terrain_hint(self, found) -> str:
        """The ground a location that is not a settlement stands on, when a bare id
        cannot say: the world's own facts if there is a world, else what the party is
        already standing on, else grassland."""
        from . import places as places_mod

        # Never the ground the party is currently on: that is what made a world-less
        # engine forget it had a town the moment the party walked into the forest —
        # "home" became the forest, and "back to urban" minted an urban region
        # outside the town. With no world the hint is empty and a bare id reads as
        # a settlement (`places._settled`); a caller that knows better says so.
        if self.world is not None and found is not None:
            # A settlement's open ground is the ground the world puts around it
            # (`geography.land_around`), the same reading the travel door grounds a
            # move against — so the wild place a scheme sends the party to is ground
            # that is there. This read `biomes.from_world` alone, whose matcher takes
            # "ash-fields" for grassland (docs/fix-interfaces.md §1.3 B4); two readers
            # of the land would send a scheme to ground the travel door then refuses.
            if places_mod._settled(found, ""):
                from . import geography

                land = geography.land_around(self.world, found)
                ground = next((b for b in (*land.near, *land.beyond)
                               if b not in ("coast", "water", places_mod.URBAN)), "")
                if ground:
                    return ground
            found_biomes = biomes.from_world(self.world, found)
            return next((b for b in found_biomes if b != places_mod.URBAN), "grassland")
        return ""

    def places(self) -> tuple:
        """Every place the party can name from where they stand — derived, never stored.

        The location's own set, plus the ground they are on when it is not the
        location's own ground: from the forest outside the town, "the market" still
        resolves. One derivation, `places.for_scene`, shared with the brief; there used
        to be two, and two copies of a rule is the trap CLAUDE.md names.
        """
        from . import places as places_mod

        found = (self.world.get(self.scene.location_id) if self.world else None)
        # The bare id when the world is not to hand: it is what seeds the layout, so a
        # scene still has its places without one.
        return places_mod.for_scene(found or self.scene.location_id, self.scene.at,
                                    terrain_hint=self._terrain_hint(found),
                                    founded=self.scene.founded,
                                    ring=self._ring(found, self.scene.at))

    def _ring(self, found, at: str = "") -> tuple:
        """The settlement's outside places (`rules/outskirts.py`), or () with no world.

        The middle scale Bobby needed on 2026-09-28: "I leave the village and stand
        outside it" had nowhere to go but the way in, inside the village. Derived from the
        world's roads and land every time, never stored — the same bargain as every
        generated place.
        """
        from . import outskirts

        if self.world is None or found is None:
            return ()
        return outskirts.ring(self.world, found, at)

    def here(self):
        """The place the party is standing in. Never None — they are always somewhere."""
        from . import places as places_mod

        known = self.places()
        return places_mod.find(known, self.scene.at) or known[0]

    def place_party(self, place_id: str = "") -> None:
        """Stand the party somewhere real: the named place, or the location's first.

        The Engine's door onto `Scene.move` for the PC, and the one that validates:
        `Scene` cannot know what places exist (it has no world), so a place id that did
        not come from `places()` is refused HERE — that is the free-text `spot` coming
        back through a side door. Everyone unplaced (a save from before actors had a
        place) is stood with the party.
        """
        from . import places as places_mod

        if place_id:
            # Validated against the set the TARGET's own ground implies, not the set
            # the party currently sees: a scene that has not been placed yet sees
            # nothing, and a save being healed onto the forest has to be allowed to
            # name the forest. The question is "is this a real place of this
            # location", and the id carries enough to ask it.
            found = (self.world.get(self.scene.location_id) if self.world else None)
            known = places_mod.for_scene(
                found or self.scene.location_id, place_id,
                terrain_hint=places_mod.terrain_of(place_id),
                founded=self.scene.founded,
                # The ground outside is a real place of this location too (Lane B).
                ring=self._ring(found, place_id))
            target = places_mod.find(known, place_id)
            if target is None:
                raise ValueError(f"place_party: no place {place_id!r} here; the places "
                                 f"are {[p.id for p in known]}")
        else:
            # Arriving means arriving AT the way in. Unnamed, this used to stand the
            # party at `places()[0]` — whatever the world happened to list first, which in
            # Vormoor is the well — so a character walking a week of road stepped straight
            # into the middle of the town. Reported 2026-09-21: "why would walking onto
            # town take me to the market it should be the streets or the entry square or
            # something like that."
            #
            # `places.ENTRANCES` is the same list the law watches and the generator
            # guarantees, so the door somebody arrives by is the door the warrant is
            # checked at. A place with no entrance at all falls back to the first, which
            # is what every location did before.
            here_now = self.places()
            target = next(
                (p for p in here_now
                 if " ".join(str(p.name or "").split()).lower() in places_mod.ENTRANCES),
                here_now[0])
        # Placement is not movement. `move` unseats — drops the zone, the initiative
        # slot, the side — and refuses the PC mid-encounter; a save loaded mid-fight
        # from before places existed has all of those and must keep them. Nothing is
        # walked out of, so the cast ledger stays too. The third and last writer of
        # `Actor.at`, and it only ever writes the party's own place.
        pc = self.scene.pc()
        was_at = self.scene.at
        if was_at != target.id:
            # An arrival, for residency: a load that stands the party where it already
            # was is not one, or a reload would send the baker home mid-conversation.
            self.scene.arrived = self.scene.clock_minutes
            self.scene.moves += 1
        self.scene.at = target.id
        if pc is not None:
            pc.at = target.id
        for a in self.scene.people.values():
            if not a.at:
                a.at = target.id
        self.staff_the_place()
        # New room, new ground — and only when the room is actually new. The map belongs to
        # the PLACE, so arriving somewhere else discards the old one and derives this one;
        # arriving where you already are keeps what is down, because this path also runs on
        # every load, and re-deriving there threw away everything laid ON the map. Measured
        # by the suite within the hour: a fog cloud survived a restart and its squares did
        # not (`test_a_fog_cloud_survives_closing_the_app`).
        if was_at != target.id:
            self.scene.grid = None
            self.scene.positions.clear()
        self.lay_the_ground()

    def lay_the_ground(self, even_nowhere: bool = False, place: bool = True) -> bool:
        """The map of wherever the party is standing. Laid on arrival, not on violence.

        Reported 2026-09-19: *"A map should be displayed at all times."* The grid existed
        only inside a fight by construction — laid by `_lay_battlefield` from the two doors
        a fight comes in by, cleared by `end_encounter`, and gated again in the view and in
        the browser, which printed "No ground is mapped. A grid is laid out when a fight
        starts."

        Nothing was missing to derive one. `floorplan.for_place` is a pure function of the
        place id, its terrain and the world's authored shape, and all three are available
        on every turn; its scatter is a SHA-seeded LCG rather than `random`, so the market
        has the same stalls every time anybody stands in it and none of it is saved. What
        was absent was POSITIONS — and the zone word (`engaged`/`near`/`far`) is on every
        actor at all times, which is exactly what `place_by_zone` reads.

        This is what every virtual tabletop does: the map is the room, and the fight adds
        the tactical layer on top of the same ground rather than conjuring ground of its
        own. Returns whether it laid anything.
        """
        # `even_nowhere` is the fight's door. A scene with no place is one that has not
        # been put anywhere yet — the map tray says so rather than drawing a blank field —
        # but a brawl still has to happen on ground, and `floorplan.for_place("")` falls
        # through to open ground the way every fight used to get.
        if self.scene.grid is not None:
            # The ground is down already; anybody still standing nowhere on it is put
            # at their zone now — a save from before arrivals were placed, a door that
            # added somebody before the player had a square. Nobody who HAS a square is
            # touched: it is theirs until they move (the ruling of 2026-09-28).
            pc = self.scene.pc()
            if place and pc is not None and pc.ref in self.scene.positions:
                stragglers = [r for r in self.scene.actors
                              if r != pc.ref and r not in self.scene.positions]
                if stragglers:
                    self.scene.place_by_zone(stragglers)
            return False
        if not (self.scene.at or even_nowhere):
            return False
        from . import floorplan, places as places_mod

        authored = getattr(self.here(), "shape", None)
        self.scene.grid = floorplan.for_place(
            self.scene.at, places_mod.terrain_of(self.scene.at), authored)
        # The player first and everyone else around them, because `place_by_zone` measures
        # from the PC. A quarter of the way in, the same spot a fight would have put them,
        # and never off the board — a ten-foot alley is two squares wide.
        # `place=False` is the fight's door again: `_lay_battlefield` is about to lay the
        # PC's side, the foes at their own distances and the bystanders around them, and
        # placing anybody here first would measure them from a PC who is about to move.
        # Measured by the suite: a servant standing `engaged` came out two squares away
        # rather than one, because the player was re-placed after they were.
        pc = self.scene.pc()
        if pc is None or not place:
            return True
        if pc.ref not in self.scene.positions:
            x = max(0, min(self.scene.grid.width - 1, self.scene.grid.width // 4))
            self.scene.positions[pc.ref] = self._clear_square(
                (x, self.scene.grid.height // 2), pc.size)
        unplaced = [r for r in self.scene.actors
                    if r != pc.ref and r not in self.scene.positions]
        if unplaced:
            self.scene.place_by_zone(unplaced)
        return True

    def staff_the_place(self):
        """Somebody behind the counter, where the party is standing (`rules/keepers.py`).

        Called from the two doors that change where the party is — here, and the end of
        a `travel` that moved — because those are the two, and a third caller would be
        a third place to forget. Idempotent: a place that has been staffed once is
        never staffed again, so a save reloaded fifty times still has one smith.
        """
        from . import keepers

        return keepers.staff(self)

    def _march(self, pc, hours: int, biome: str) -> tuple[bool, str]:
        """Walk a journey, eight hours a day with a camp between, and say what it cost.

        The first version of this spent the whole journey in one `pass_hours` call, and
        it was wrong in a way that only showed up when it was driven: a five-day road is
        forty hours, and forty hours *continuously* is a man marching without sleep. Both
        a four-hit-point traveller and a sixty-hit-point one collapsed at exactly the same
        hour, because what stopped them was the twenty-four-hour wakefulness grace and not
        anything about their bodies. A journey is not a forced march; it is days.

        So each day is `HOURS_PER_DAY` of walking, charged to the body, then a camp. The
        camp feeds, waters and sleeps the traveller — which is what this game models
        provisioning as everywhere else, since `_op_eat` resets the hunger clock and
        consumes nothing. Being stricter on the road than in a tavern would be a rule this
        one op invented for itself.

        Returns whether the far end was reached, and the tell for what the road took.
        """
        from . import journey as journey_mod

        if pc is None or not hours:
            if hours:
                self.scene.advance(hours * survival.MINUTES_PER_HOUR)
            return True, ""

        day = journey_mod.HOURS_PER_DAY
        told: list[str] = []
        left_to_walk = hours
        while left_to_walk > 0:
            today = min(day, left_to_walk)
            toll = survival.pass_hours(pc, today, self.dice, biome=biome)
            walked = max(1, toll.hours)
            self.scene.advance(walked * survival.MINUTES_PER_HOUR, charge_body=False)
            if toll.checks:
                told.append(survival_note(toll))
            if walked < today:
                # The body gave out with road still to go. They do not arrive — a journey
                # that ran out of traveller did not happen, and arriving anyway is what
                # makes the clock decorative on exactly the trip that should test it.
                return False, "; ".join(told)
            left_to_walk -= today
            if left_to_walk > 0:
                # Camp. The rest of the day passes and the traveller takes it.
                survival.eat(pc)
                survival.drink(pc)
                survival.sleep(pc)
                self.scene.advance((24 - day) * survival.MINUTES_PER_HOUR,
                                   charge_body=False)
        return True, "; ".join(told)

    def _op_journey(self, intent: Intent, partial: dict) -> Outcome:
        """Leave the town, for another one, and pay the road for it.

        The op `Scene.location_id` waited for. It was written once at campaign creation
        and never again, so a world shipping twelve settlements could be played in one —
        `travel` moves the ground underfoot *inside* a settlement and has no way out.

        Everything about the arithmetic lives in `rules/journey.py`; everything about the
        consequences is here, and it is the same shape as `_op_venture`: roll the body's
        checks for the hours, then move the world's clock by what they actually cost.
        Travel that costs nothing is why a three-day march used to be free on a clock
        that meters thirst in hours.
        """
        from . import journey as journey_mod, places as places_mod

        # One journey a turn, from this side too (item 35): a plan that walks across
        # town and then takes the road out is the same defect wearing a longer coat,
        # and this one costs days on the clock rather than minutes.
        if self._journeyed:
            return self._refuse(
                intent, f"The party has already travelled this turn and is at "
                        f"{self._journeyed}. One journey a turn — the road out is the "
                        f"next turn's.")

        pc = self.scene.pc()
        want = " ".join(str(intent.params.get("to") or "").split())
        legs = journey_mod.legs_from(self.world, self.scene.location_id)
        if not legs:
            return self._refuse(
                intent, "There is no road out of here that this world has written down.")
        leg = journey_mod.find(legs, want)
        if leg is None:
            return self._refuse(
                intent, f"There is no road from here to {want or 'there'}. From here you "
                        f"can reach {', '.join(x.to_name for x in legs)}.")

        # The warrant reads the road, exactly as it reads the gate. Leaving town by the
        # highway is the most public way out there is, and `_op_travel` already refuses
        # the open road to somebody who is wanted — this is that rule, one scale up.
        watched = self.watch_on_the_road(pc)
        if watched:
            return self._refuse(intent, watched)

        speed = pc.speed_feet if pc is not None else 30
        hours, measured, how = journey_mod.hours_for(leg, speed)
        on_foot = hours

        # On foot, riding, or at a gallop (the owner's ruling Q13; `journey.mounted_hours`
        # carries the sourced rules). Checked before anything moves: a refusal here must
        # leave the conversation and the company exactly as they were.
        pace = journey_mod.pace_of(intent.params.get("pace")) or "walk"
        if how == "sea":
            pace = "walk"             # a horse does not make a ship go faster
        mount_refs: list[str] = []
        if pace != "walk":
            party = [str(w) for w in (intent.params.get("with") or [])
                     if str(w) in self.scene.actors]
            party += [r for r, a in self.scene.actors.items()
                      if r not in party and not a.is_pc
                      and a.has_state(states.TRAVELS_WITH_YOU)]
            mount_refs = [r for r in party
                          if str(getattr(self.scene.actors[r], "from_template", "") or "")
                          in journey_mod.MOUNTS and not self.scene.actors[r].is_down]
            riders = 1 + len([r for r in party if r not in mount_refs])
            if len(mount_refs) < riders:
                walk_words = journey_mod.describe(leg, hours)
                return self._refuse(
                    intent,
                    (f"Nobody in the party has a horse to ride to {leg.to_name}"
                     if not mount_refs else
                     f"There are {riders} to carry and {len(mount_refs)} "
                     f"mount{'s' if len(mount_refs) != 1 else ''} to carry them")
                    # Bought, never hired (the owner, 2026-09-29): the stables sell them,
                    # or the market's horse lines where a settlement has no stables.
                    + f". On foot it is {walk_words}. A mount is bought at the stables, "
                      f"and comes along like anybody who travels with you.")
            mount_refs = mount_refs[:riders]
        # Setting out is walking away, whatever the road then does.
        parted = self.end_talk("walked away")

        # A road already half walked is half a road. `scene.road` is what an interrupted
        # journey left behind, and it is only good for the road it was left on: setting
        # out for somewhere else, or from somewhere else, is a new journey at full cost.
        resumed = 0
        if (self.scene.road.get("to") == leg.to_id
                and self.scene.road.get("from") == self.scene.location_id):
            resumed = max(0, int(self.scene.road.get("walked") or 0))
            hours = max(1, hours - resumed)
        elif self.scene.road:
            # A different road, or the same one from somewhere else: the old one's
            # progress is gone, and so is its record — a stale one otherwise waits
            # for the party to come back to the same origin and claim it.
            self.scene.road = {}
        # The road's length on foot, and the hours it takes at the pace chosen. The road
        # remembers progress in hours ON FOOT, so a road half galloped and then walked
        # is still half a road.
        walk_left = hours
        hours, hurt_days = journey_mod.mounted_hours(walk_left, pace)
        from_id = self.scene.location_id
        from . import outskirts as outskirts_mod

        # The way out to the road, through the ring: journeys along those roads pass
        # through the crossroads (owner's ruling Q11), and the tell says so.
        known_now = self.places()
        head = outskirts_mod.road_for(known_now, leg.to_id)
        through: list[str] = []
        if head is not None and self.scene.at != head.id:
            through = [p.name for p in (places_mod.find(known_now, x)
                                        for x in places_mod.route(known_now, self.scene.at,
                                                                  head.id))
                       if p is not None and places_mod.is_ring(p.id)]

        # The fight does not come with you, and neither does anybody who is not.
        fight_ended = bool(self.scene.initiative)
        if fight_ended:
            self.scene.end_encounter()
        escorts = [str(w) for w in (intent.params.get("with") or [])
                   if str(w) in self.scene.actors]
        # And whoever travels with you, for the reason `_op_travel` gives: days on a
        # road is the last place a companion should be silently dropped.
        escorts += [r for r, a in self.scene.actors.items()
                    if r not in escorts and not a.is_pc
                    and a.has_state(states.TRAVELS_WITH_YOU)]
        keeping = {pc.ref if pc is not None else "", *escorts}
        left = [a.name for ref, a in list(self.scene.actors.items())
                if ref not in keeping and not a.is_pc]
        for ref in list(self.scene.actors):
            if (ref not in keeping and not self.scene.actors[ref].is_pc
                    and not self._stays_in_the_world(self.scene.actors[ref])):
                self.scene.depart(ref)

        # The road, charged to the body first and the world's clock second — the order
        # `_op_venture` uses, because `pass_hours` can stop early and only it knows how
        # many hours were actually survived.
        # The road's own check, watch by watch, stopping at the first thing that happens
        # (`rules/ontheway.py`). The published procedure verbatim — four checks a day at
        # 20% — over the ground the world says this route crosses. Rolled BEFORE the
        # march so the march only charges the body for the hours actually walked: a
        # party stopped at noon on day one has not paid for day three.
        #
        # Not at sea. A passage is not a march and this table is a road's; a ship's own
        # trouble is `rules/ships.py`, which has its own.
        met = None
        # Two different hours. `remaining` is the road still ahead when they set out;
        # `progress` is how much of it gets walked today; `hours` is what the day
        # costs. Weather adds to the cost and never to the progress — and until
        # 2026-09-23 it did both, because the walked figure was taken off `hours`
        # after the storm's hours had gone into it: a ten-hour road held up by weather
        # on its second watch recorded twelve hours walked.
        progress = remaining = hours
        if how != "sea":
            met = ontheway.road(
                self.dice, hours,
                (leg.crosses[0] if leg.crosses else places_mod.terrain_of(self.scene.at)),
                int(getattr(pc, "level", 1) or 1) if pc is not None else 1)
        if met is not None:
            progress = ontheway.hours_walked(met, hours)
            hours = progress
            if met.kind == "weather":
                # Weather is the one band that costs rather than blocks: the road turns
                # against you and the hours go anyway, charged to the body like any
                # other hours out there. Added to the walk so `_march` pays for them,
                # and NOT added to what the road remembers — sitting out a storm does
                # not get you closer to anywhere.
                weathered = self.dice.roll(ontheway.WEATHER_HOURS,
                                           label="how long it holds you",
                                           visibility="hidden").total
                hours += weathered
        # Stopped short only when the road is not all walked. A check falls at the END
        # of a watch, and the last watch of a march is the part-watch that ends where
        # the road does — so a meeting there is a meeting within sight of the far town,
        # and the party arrives with it. Measured 2026-09-23 on an eight-hour road: a
        # hit on its second watch recorded eight hours walked of eight and stood the
        # party in the fields outside the town they had LEFT, with the next attempt
        # costing one hour.
        stopped_short = met is not None and progress < remaining

        toll_note = ""
        if how == "sea":
            # A passage is not a march. Nobody aboard is walking eight hours and camping
            # at dusk — they are fed, watered and slept by the ship, which is exactly what
            # `_march`'s camp does for a traveller and with none of the walking. So the
            # clock moves and the body is not charged, and a crossing always completes:
            # a ship does not turn back because a passenger is tired.
            arrived, walked = True, ""
            self.scene.advance(hours * survival.MINUTES_PER_HOUR, charge_body=False)
        else:
            arrived, walked = self._march(pc, hours,
                                          places_mod.terrain_of(self.scene.at))
        if walked:
            toll_note = f" The road cost them: {walked}"

        # A body that gave out did not meet anything: it turned back before the watch
        # the dice picked. The road's check is for a party that was still walking.
        if not arrived:
            met, stopped_short = None, False

        if arrived and not stopped_short:
            self.scene.location_id = leg.to_id
            # A march between settlements is this turn's journey too (item 35), and a
            # `travel` behind it would walk the party across the new town the moment it
            # arrived. A road turned back from cost hours but moved nobody, so it does
            # not spend the turn's journey.
            self._journeyed = leg.to_name
            # The road is behind them, whatever of it was walked on an earlier turn.
            self.scene.road = {}
            self.place_party()
        elif stopped_short:
            # Stopped on the road, which is a real place: the stretch of THIS road they
            # got to, `@along-the-road-to-{to_id}` (Lane B). It stood the party at
            # `region_set(origin)[0]` — "the approach", beside the town they had left,
            # hours out (docs/design-b-space.md §1). The ground is what the route crosses
            # at the fraction walked; progress stays in `Scene.road`, which already
            # existed, and the place is derived from it and the id.
            walked_units = round(progress * walk_left / max(1, remaining)) if remaining \
                else progress
            self.scene.road = {"to": leg.to_id, "to_name": leg.to_name,
                               "from": self.scene.location_id,
                               # Hours spent sitting out weather are hours, not
                               # progress: they cost the clock and the body and move
                               # nobody an inch nearer the far end. And they are hours
                               # ON FOOT, whatever the pace was.
                               "walked": resumed + walked_units}
            crosses = [c for c in (biomes.canonical(str(x)) for x in leg.crosses) if c]
            total = max(1, on_foot)
            if crosses:
                ground = crosses[min(len(crosses) - 1,
                                     int(len(crosses) * (resumed + walked_units) / total))]
            else:
                ground = places_mod.terrain_of(self.scene.at) or "grassland"
            if ground == places_mod.URBAN:
                ground = "grassland"
            along = outskirts_mod.ring_id(self.scene.location_id, ground,
                                          outskirts_mod.along_slug(leg.to_id))
            self.place_party(along)
            # The turn's journey is spent, and it names where the party IS — the
            # refusal a second travel gets says "is at {here}", and until 2026-09-23
            # this said the far town, which they had just been told they did not reach.
            self._journeyed = self.here().name
        else:
            self.place_party()

        # Whoever came along comes along. `place_party` writes the PARTY's place — the
        # PC and anybody who has no place at all — so an escort kept by `with` was left
        # standing at the far end of a road they had just walked, present in the store
        # and absent from the scene. Nobody noticed while `with` was the only way to be
        # kept, because naming somebody in `with` on a journey is a thing that had never
        # once happened in play.
        for ref in escorts:
            if ref in self.scene.people:
                self.scene.move(ref, self.scene.at)

        # The gallop's toll on the mounts, by the hustle rule (`journey.mounted_hours`):
        # a point of lethal damage for each day galloped past the first free hour, and
        # fatigued — through the one applicator, as a condition that lifts with eight
        # hours of the clock (the book's "8 hours of complete rest"), never a flag.
        mount_note = ""
        if hurt_days and mount_refs:
            days_out = max(1, -(-progress // journey_mod.HOURS_PER_DAY)) if stopped_short \
                else hurt_days
            hurt = min(hurt_days, days_out)
            tired = []
            for ref in mount_refs:
                horse = self.scene.actors.get(ref)
                if horse is None:
                    continue
                horse.take_damage(hurt)
                horse.add_condition(journey_mod.MOUNT_FATIGUE,
                                    rounds=journey_mod.FATIGUE_ROUNDS, source="hustle")
                tired.append(horse.name)
            if tired:
                mount_note = (f"The gallop has blown {', '.join(tired)}: pushed past the "
                              f"first hour, a mount is hurt by it and tires, and walks "
                              f"the rest of the day.")
        elif pace == "ride" and mount_refs:
            mount_note = "Mounted, the road goes at twice the pace of walking it."

        # The register's fields on every branch (docs/fix-interfaces.md §2.7).
        common = {"from_id": from_id, "setting": places_mod.setting_of(self.scene.at),
                  "direction": "out" if stopped_short else "in",
                  "place": self.scene.at}
        if pace != "walk":
            common.update(pace=pace, on_foot=on_foot, mounts=list(mount_refs))
        if through:
            common["went_by"] = through

        if not arrived:
            bits = [f"The road to {leg.to_name} was longer than {pc.name if pc else 'the party'} "
                    f"could walk: they turned back before it was done."]
            if toll_note:
                bits.append(toll_note.strip())
            if mount_note:
                bits.append(mount_note)
            return Outcome(
                intent_id=intent.id, op="journey", status="prevented",
                effects=[{"kind": "journey", "to": leg.to_id, "to_name": leg.to_name,
                          "hours": hours, "arrived": False, "how": how, "left": left,
                          **common}],
                tell=" ".join(bits),
                because=intent.because,
            )

        # Whoever the road held arrives by the one door creatures come in by, onto the
        # ground the party is now standing on — the open country it stopped in, or the
        # far town's way in when the meeting fell on the road's last watch.
        made = self._meet_on_the_way(met, zone="far") if met is not None else []
        if met is not None and met.aggressive and pc is not None and made:
            self._ensure_encounter(pc.ref, target=made[0]["ref"])

        if stopped_short:
            # The march is over for this turn, and the road remembers how much of it is
            # still to walk.
            bits = [f"{hours} hour{'s' if hours != 1 else ''} out of "
                    f"{getattr(self.world.get(self.scene.location_id), 'name', 'town') if self.world else 'town'} "
                    f"on the road to {leg.to_name}, and the road stops being yours.",
                    ontheway.describe(met, who=[self.scene.actors[m["ref"]].name
                                                for m in made
                                                if m["ref"] in self.scene.actors])]
            if through:
                bits.insert(0, f"Out by {_and_then(tuple(through))}.")
            if toll_note:
                bits.append(toll_note.strip())
            if mount_note:
                bits.append(mount_note)
            return Outcome(
                intent_id=intent.id, op="journey",
                effects=[{"kind": "journey", "to": leg.to_id, "to_name": leg.to_name,
                          "hours": hours, "arrived": False, "how": how, "left": left,
                          "stopped_short": True, "met": met.kind,
                          **common, "met_refs": [m["ref"] for m in made]}],
                tell=" ".join(b for b in bits if b),
                because=intent.because,
            )

        bits = [f"{journey_mod.describe(leg, hours).capitalize()}, and {leg.to_name} "
                f"is ahead of you."]
        if through:
            # Q11: the roads out part at the crossroads, and a journey along one of them
            # passes through it — said, so the page walks it rather than inventing one.
            bits.insert(0, f"Out by {_and_then(tuple(through))}.")
        if mount_note:
            bits.append(mount_note)
        if parted:
            bits.insert(0, parted)
        if met is not None:
            # Met on the last watch: the road ended at the same time.
            bits.append(ontheway.describe(met))
        if resumed:
            bits.append(f"The {resumed} hour{'s' if resumed != 1 else ''} of it already "
                        f"behind them counted: only the rest was walked today.")
        if how == "derived":
            # Never a mileage the world did not state. The tell says how long it took,
            # which is true, and not how far it was, which nobody wrote down.
            bits.append("How far it is, nobody has written down.")
        if fight_ended:
            bits.append("The fight is left behind.")
        if left:
            bits.append(f"Left behind: {', '.join(left)}.")
        if toll_note:
            bits.append(toll_note.strip())
        note = str(intent.params.get("note") or "").strip()
        if note:
            bits.append(note)
        return Outcome(
            intent_id=intent.id, op="journey",
            effects=[{"kind": "journey", "to": leg.to_id, "to_name": leg.to_name,
                      "hours": hours, "measured": measured, "how": how,
                      "left": left, "fight_ended": fight_ended,
                      "met": met.kind if met is not None else "", **common}],
            tell=" ".join(bits),
            because=intent.because,
        )

    def watch_at_the_way_out(self, pc, was_place: str, going_to, known) -> tuple[str, str]:
        """(refusal, line) for walking from `was_place` to `going_to` past the watch.

        The gate's reading of the warrant, as `_op_travel` has always applied it — moved
        here, unchanged, so the exits row (play/exits.py, I6) asks the SAME question
        before a button is offered rather than a second copy of the rule deciding which
        ways out look open. `refusal` is the sentence a wanted character is refused with;
        `line` is the suspected character's look-twice. Both "" when the watch has
        nothing to say. Reads nothing that a walk changes, so asking is free.
        """
        from . import places as places_mod

        if pc is None:
            return "", ""
        town = places_mod.location_of(was_place) or self.scene.location_id
        law = states.standing_with_the_law(pc, town)
        if not law:
            return "", ""
        # Any way in or out, not the literal word "gate". `places.ENTRANCES` is the
        # one list, so the generator and the law cannot disagree about what an
        # entrance is — and a village, which has a road rather than a gate, was
        # somewhere a warrant could never be enforced at all.
        at_gate = " ".join(going_to.name.split()).lower() in places_mod.ENTRANCES
        # Any way OUT, by place as well as by biome (Lane B, docs/fix-interfaces.md
        # §1.3 B3). This read `bool(want)`, so a travel by PLACE to ground outside —
        # which is how the outskirts and the road heads are entered — walked past the
        # watch unasked. Leaving is from inside to outside, whatever the plan named;
        # the founded and ventured ground stays the "another way" the refusal names.
        open_road = places_mod.setting_of(was_place) != "outside" \
            and places_mod.setting_of(going_to.id) == "outside" \
            and going_to.origin not in ("found", "venture") \
            and not (going_to.terrain == places_mod.URBAN)
        # A way past the watch that somebody showed you — a scheme's witness, a
        # smuggler's door — is a tag the player holds (`knows.way-past-gate`), and
        # the road is open to them by it; the gate itself stays shut.
        has_way = pc.has_state("knows.way-past-gate")
        if not (at_gate or (open_road and not has_way)):
            return "", ""
        found = self.world.get(self.scene.location_id) if self.world else None
        town_name = str(getattr(found, "name", "") or "the town")
        if law == "wanted":
            other_ways = [p.name for p in known
                          if p.origin in ("found", "venture")
                          and not p.described_only
                          and p.terrain != places_mod.URBAN]
            how = (f"Leave by another way — {', '.join(other_ways)} — or "
                   f"clear your name."
                   if other_ways else
                   "Leave by another way — ground you have founded or "
                   "ventured into outside the walls — or clear your name.")
            return (f"{pc.name} is wanted in {town_name}, and the gate is where the "
                    f"watch stands: they would take you at the arch. {how}"), ""
        return "", (f"Your name is on the watch's lips in {town_name}: the guards at "
                    f"the gate look twice, and let you through.")

    def watch_on_the_road(self, pc) -> str:
        """Why a journey out of here is refused to this character by the law, or "".

        `_op_journey`'s warrant check, given a name for the same reason as
        `watch_at_the_way_out`: the exits row greys the road with this sentence."""
        from . import places as places_mod

        if pc is None:
            return ""
        law = states.standing_with_the_law(
            pc, places_mod.location_of(self.scene.at) or self.scene.location_id)
        if law != "wanted" or pc.has_state("knows.way-past-gate"):
            return ""
        found = self.world.get(self.scene.location_id) if self.world else None
        return (f"{pc.name} is wanted in {getattr(found, 'name', 'this town')}, and "
                f"the road out is watched: they would be taken before the first "
                f"milestone. Clear your name, or find another way past the watch.")

    def shut_for_the_night(self, target):
        """The keeper asleep behind this shop's shut door at this hour, or None.

        `_at_their_door`'s test for a shop, without the knock: a keeper who lives above
        a trade counter, in the night slots, with the counter shut. Named so the exits
        row greys the same doors the travel knocks at, from one rule."""
        from . import keepers
        from . import places as places_mod
        from . import residency

        keeper = keepers.keeper_in(self.scene, target.id)
        # A SHOP whose keeper lives above it. A guardhouse is manned all night and a
        # guildhall is nobody's home: measured by the storeys suite, walking into the
        # guardhouse at midnight was refused as if it were a baker's.
        kind = keepers.kind_of(target.id, self.scene.founded)
        if (keeper is None or not keepers.lives_in(target.id)
                or places_mod.category_of(f"the {kind}") != "trade"
                or residency.slot_of(self.scene.clock_minutes) not in self._NIGHT_SLOTS
                or keepers.open_now(target.id, self.scene.clock_minutes,
                                    self.scene.founded)):
            return None
        return keeper

    def _op_travel(self, intent: Intent, partial: dict) -> Outcome:
        """Move the ground underfoot — and leave behind everyone who is not coming.

        Travel is the scene transition, and until it shed anybody it was only a biome
        field changing: in the 2026-08-22 playtest a gatekeeper wounded in the city
        travelled inside the scene to the forest, still in an initiative order that
        never ended, and took a "holds back" NPC turn after every player turn for the
        rest of the session. Every attack the fiction aimed at forest strangers then
        landed on him, because he was the only body the engine had.

        So travelling ends the encounter — walking to another biome *is* leaving the
        fight — and drops every non-PC actor except the refs named in `with`, which is
        how the GM says an escort comes along. The dead and the dying are not eligible
        even there: they stay where they fell.
        """
        from . import keepers

        # One journey a turn (item 35). A plan may name a whole route — measured
        # 2026-09-19 on "I find the mayor and grab him by the collar", which came back
        # as five travels: the guildhall, the market, the lane, the green, the upper
        # floor. The engine ran them in order, the fifth was refused because its stairs
        # are inside the guildhall, and the party ended standing on the GREEN while the
        # prose described the market.
        #
        # The first is kept and the rest refused, rather than collapsing to the last,
        # because that turn is exactly why: the destination the model meant was
        # reachable only from a place earlier in its own list, and the engine has no
        # route-finder to walk it there. Keeping the first preserves the invariant that
        # the party only ever arrives somewhere it could legally reach from where it
        # stood. The prior art wants the same thing from the other side — Inform's
        # Misadventure and Safari Guide take ONE named room and derive the route
        # themselves, and Angband and DCSS travel to one destination with the path
        # computed and the walk interruptible. In every tradition the traveller names a
        # destination and the system finds the way; here the model was handing over the
        # way itself. The refusal names where the party now stands so the next turn can
        # carry on from it, which is the roguelike's "repeat the command to resume".
        if self._journeyed:
            return self._refuse(
                intent, f"The party has already travelled this turn and is at "
                        f"{self._journeyed}. One journey a turn — the rest of the way "
                        f"is the next turn's.")

        want = str(intent.params.get("biome") or "").strip().lower()
        place = " ".join(str(intent.params.get("place") or "").split())
        if not want and not place:
            from . import places as places_mod

            return self._refuse(
                intent, "Nobody moves: where to? From here you can reach "
                        f"{', '.join(p.name for p in self.places())}, or the open ground "
                        f"outside — {', '.join(sorted(biomes.BIOMES))}.")
        # Somebody's house is knocked at, not walked into (`_knock`): the door opens
        # from their day and their regard, and a shut door leaves the party outside.
        if place:
            refused = self._at_their_door(intent, place)
            if refused is not None:
                return refused
        biome = biomes.canonical(want) if want else None
        if biome is not None and place:
            from . import places as places_mod

            named = places_mod.find(self.places(), place)
            if named is not None and named.terrain != biome:
                place = ""
        if want and biome is None:
            raise IntentError(
                f"travel: {want!r} is not a biome. The biomes are: "
                f"{', '.join(sorted(biomes.BIOMES))}.",
                "schema")

        # A destination that does not exist is refused with the ones that do, exactly as
        # an unknown biome already is. This is the courtesy the ref registry has always
        # extended to people and never to places — and it is what makes the difference
        # between the model CHOOSING a place and the model INVENTING one. A rewrite
        # naming a real place works, so this raises rather than printing: the model can
        # repair it, which is the test stage 7 sets for a correct raise.
        from . import outskirts as outskirts_mod
        from . import places as places_mod

        known = self.places()
        here = self.here()
        if place:
            going_to = places_mod.find(known, place)
            if going_to is None and self.world is not None:
                # The open ground outside the walls, by name: the region places the
                # scheme cards name. Reached as a travel by their ground.
                found = self.world.get(self.scene.location_id)
                terrain = self._terrain_hint(found) or ""
                if terrain:
                    region = places_mod.region_set(self.scene.location_id, terrain)
                    going_to = places_mod.find(region, place)
                    if going_to is not None:
                        biome = going_to.terrain
            if going_to is None:
                # Printed, not raised. The raise above was written for the plan's
                # repair loop and never reached it: `validate` does not look at the
                # place, so the first sight of it was here in `run`, where a raise is
                # a 502 on the page — "The engine refused the GM's intents: travel:
                # there is no 'the merchant's gate' here", measured 2026-09-06, on
                # "I say I will go there now, and ask him to point the way". The
                # legality check now names the fix at validate time, where the model
                # can act on it; this is the floor for anything that slips past.
                return self._refuse(
                    intent, f"There is no {place} here to go to. From here you can "
                            f"reach {', '.join(p.name for p in known)}.")
            if going_to.described_only:
                return self._refuse(
                    intent, f"{going_to.name} can be seen from here but not reached.")
            stair = self._not_by_the_stairs(here, going_to)
            if stair:
                return self._refuse(intent, stair)
        elif biome == here.terrain:
            # The ground already underfoot. This used to compare the stored biome and
            # do nothing; without the field the same answer has to be said, or a party
            # standing at the heart of the forest would be walked back to its approach
            # with the escort shed, on a wish to go deeper in.
            going_to = here
        elif biome == known[0].terrain:
            # Back to town. Three production paths send `urban` home — both injectors
            # and the bench picker — and every one of them would otherwise have minted
            # a region called urban outside the town it was trying to enter.
            going_to = known[0]
        else:
            # The fields and the shore ARE that ground: "into the fields" is the fields,
            # not a farmland wilderness minted beside them (Lane B). Anything else — the
            # trees, the hills — is open ground past the outskirts, reached through them.
            going_to = next((p for p in known if places_mod.is_ring(p.id)
                             and p.name in (outskirts_mod.FIELDS, outskirts_mod.SHORE)
                             and p.terrain == biome), None)
            if going_to is None:
                # Is it there at all? The world says what ground lies around a
                # settlement (`geography.land_around`), and a move onto ground it does not
                # have is refused and SHOWN, with the ground that is there named. Bobby
                # walked "west into the gnarled dense trees" around Vormoor on 2026-09-28
                # — a forest the previous beat had invented — and the engine accepted
                # `biome: forest` unchecked (docs/playtest-2026-09-28.md, 20.2).
                refused = self._absent_ground(intent, biome, known)
                if refused is not None:
                    return refused
                # Open ground of a kind the party is not on: the region's first place.
                going_to = places_mod.region_set(
                    places_mod.location_of(known[0].id) or self.scene.location_id,
                    biome)[0]

        # Escorts: refs are validated against the view already; names are resolved here,
        # against the view, and an ambiguous name refuses rather than guessing which of
        # two guards comes along. Unknown names are ignored, as they always were.
        escorts: list[str] = []
        for w in (intent.params.get("with") or []):
            w = str(w).strip()
            if not w:
                continue
            if w in self.scene.actors:
                escorts.append(w)
                continue
            matches = [r for r, a in self.scene.actors.items()
                       if not a.is_pc and str(a.name).lower() == w.lower()]
            if len(matches) > 1:
                raise IntentError(
                    f"travel: {w!r} names {len(matches)} people here; say which by "
                    f"ref: {', '.join(matches)}.", "refs")
            escorts.extend(matches)
        # And whoever travels with you, without being named. `with` asked the model to
        # remember who the party is on every single move, and it did not: measured live
        # 2026-09-22, the tell for crossing a village read "Left behind: Drenn
        # Ironvale". A companion is a state on the person (`_op_company`), and this is
        # the door that reads it.
        #
        # And it reads the attitude with it, which is the loyalty the bond shipped
        # without: somebody comes with you because they are friendly, so somebody who
        # has stopped being friendly has stopped coming. One question, asked of the
        # same track `_op_company` asks — not a second rule, and not a bond that
        # outlives the feeling it was granted for.
        from . import attitude as attitude_mod
        from . import journey as journey_mod

        fell_away: list[str] = []
        for r, a in self.scene.actors.items():
            if r in escorts or a.is_pc or not a.has_state(states.TRAVELS_WITH_YOU):
                continue
            # A mount is owned, not befriended (I3): a bought horse is indifferent on the
            # track, and asked the loyalty question it "did not come with you any more"
            # at the first step out of the gate — measured by this lane's pace tests. The
            # journey never asked it of a mount; neither does this.
            if str(getattr(a, "from_template", "") or "") in journey_mod.MOUNTS:
                escorts.append(r)
                continue
            if (attitude_mod.step_of(attitude_mod.of(a))
                    < attitude_mod.step_of(attitude_mod.COMES_ALONG)):
                a.remove_effects(source=f"company:{r}")
                fell_away.append(a.name)
                continue
            escorts.append(r)

        pc = self.scene.pc()
        was_place = self.scene.at
        was_ground = here.terrain
        moved = going_to.id != was_place

        # THE PACE, for a short trip out of town (I3, 2026-09-29). Lane B built riding and
        # galloping for journeys (owner, Q13) and could not give `travel` the param, so a
        # party with horses walked to the woods. The same closed word and the same rules:
        # riding halves the time outside the walls and a gallop thirds it
        # (`journey.PACES`), a gallop past the book's free hour hurts and tires the mount
        # (`journey.mounted_hours`, the hustle rule), one mount a rider, and a party short
        # of mounts is refused before anything moves. Only ground OUTSIDE is ridden faster:
        # a horse in the lanes of a town goes at the crowd's pace, and the in-town bands
        # (Q10) are a crowd's.
        from . import journey as journey_mod

        pace = journey_mod.pace_of(intent.params.get("pace")) or "walk"
        mount_refs: list[str] = []
        if pace != "walk" and moved:
            mount_refs = [r for r in escorts
                          if str(getattr(self.scene.actors[r], "from_template", "") or "")
                          in journey_mod.MOUNTS and not self.scene.actors[r].is_down]
            riders = 1 + len([r for r in escorts if r not in mount_refs])
            if len(mount_refs) < riders:
                return self._refuse(
                    intent,
                    ("Nobody in the party has a horse to ride"
                     if not mount_refs else
                     f"There are {riders} to carry and {len(mount_refs)} "
                     f"mount{'s' if len(mount_refs) != 1 else ''} to carry them")
                    + f", so the way to {going_to.name} is walked or not at all. A mount "
                      f"is bought at the stables, and comes along like anybody who "
                      f"travels with you.")
            mount_refs = mount_refs[:riders]
        ridden_minutes = 0          # minutes of the walk spent at the pace, for the tell
        tired_mounts: list[str] = []

        # THE WAY THERE, hop by hop, and whatever is on it.
        #
        # "i can say i go to the market and the narrator doesn't just put me in the
        # market but describes all the places i needed to move through to get there"
        # (2026-09-22). `Place.exits` has been the move vocabulary since this engine
        # was written and nothing ever walked it: a travel was a single assignment
        # however far across town it went, which is why "I head into the city" from the
        # roadside landed in the market with the gate and the square never mentioned.
        # `places.route` is the breadth-first walk; the destination is unchanged, so a
        # crossing still costs ONE turn — the player was explicit that it must ("not
        # that i have to spend four turns to get to the market").
        #
        # And every hop is checked (`rules/ontheway.py`), on the table for the ground
        # that hop crosses, stopping at the first thing that happens — which is the
        # request, and is also what the roguelikes do with a computed path: Angband and
        # DCSS walk it until something disturbs you and then hand the keyboard back.
        # The party stops where it was stopped, so the destination shrinks to that hop.
        # A route that comes back empty — 40 of Aurvantis's 10,792 pairs, and any
        # minted place the exits have not been wired for — falls back to the single
        # step this door has always taken, checked once.
        #
        # WHAT IT COSTS, hop by hop (Lane B, 2026-09-28). A crossing of town was free —
        # "still 08:00 after two crossings of town" (docs/playtest-2026-09-28.md, 16.5) —
        # and only a step between the walls and open ground cost anything, a flat hour.
        # Each hop now costs the minutes the rules' local movement gives it
        # (`outskirts.hop_minutes`: the owner's Q10 bands in town, half a mile a ring
        # hop, three miles into open ground), summed over the hops actually walked, so
        # a meeting cuts the sum short where it cuts the walk short. Ground beyond the
        # near land is as far as the world's own roads put it, at the journey's pace
        # (Q13): hours, and days if it comes to that.
        met = None
        went_by: tuple[str, ...] = ()
        went_by_about: list[dict] = []
        meant_for = going_to.name
        minutes = 0
        far_hours = far_walked = 0
        grounded_as = ""
        found_loc = self.world.get(self.scene.location_id) if self.world else None
        scale = places_mod.scale_of(found_loc) if found_loc is not None else "town"
        speed = int(getattr(pc, "speed_feet", 30) or 30) if pc is not None else 30
        if moved and want and places_mod.setting_of(going_to.id) == "outside" \
                and not places_mod.is_ring(going_to.id) and found_loc is not None \
                and places_mod._settled(found_loc, ""):
            from . import geography

            grounded_as, _words = geography.grounded(
                geography.land_around(self.world, found_loc), going_to.terrain)
            if grounded_as == "beyond":
                far_hours = outskirts_mod.beyond_hours(self.world, found_loc,
                                                       going_to.terrain, speed)
        # Ground beyond the near land, ridden: the journey's own arithmetic on the hours
        # it would take on foot — halved riding, thirded galloping while the hustle rule
        # lets the horse, and the days the gallop hurt it (paid after the walk, below).
        far_hurt = 0
        far_on_foot = far_hours
        if far_hours and mount_refs:
            far_hours, far_hurt = journey_mod.mounted_hours(far_hours, pace)
        if moved:
            level = int(getattr(pc, "level", 1) or 1) if pc is not None else 1
            passed: list = []
            hops = places_mod.route(known, was_place, going_to.id)
            if not hops and places_mod.find(known, going_to.id) is None:
                # Open ground is out past the outskirts: the walk goes through the way
                # out, the way the player would, and is checked and timed on each step.
                out = next((p for p in known if p.name == outskirts_mod.OUTSKIRTS
                            and places_mod.is_ring(p.id)), None)
                if out is not None and (places_mod.setting_of(was_place) != "outside"
                                        or places_mod.is_ring(was_place)):
                    lead = () if out.id == was_place else places_mod.route(
                        known, was_place, out.id)
                    if lead or out.id == was_place:
                        hops = tuple(lead) + (going_to.id,)
            prev = here
            for hop_id in (hops or (going_to.id,)):
                hop = places_mod.find(known, hop_id) or going_to
                underway = hop.id in self._hours_underway
                if underway:
                    # A venture's way in (two hours to a cave) is `_op_venture`'s to
                    # charge, and it has; the one meeting path checks those hours once.
                    step_hours = self._hours_underway.pop(hop.id, 1) or 1
                    step = 0
                elif hop.id == going_to.id and far_hours:
                    step_hours, step = far_hours, 0
                else:
                    step = outskirts_mod.hop_minutes(prev, hop, scale, speed)
                    step_hours = 0
                if mount_refs and step and "outside" in (
                        places_mod.setting_of(hop.id), places_mod.setting_of(prev.id)):
                    # Ridden: the step outside at the pace's multiple. A gallop this short
                    # sits inside the hustle rule's free hour, so it costs the horse
                    # nothing (`journey.HUSTLE_FREE_HOURS`).
                    step = max(1, -(-step // journey_mod.PACES[pace]))
                    ridden_minutes += step
                if places_mod.setting_of(hop.id) == "in":
                    met = ontheway.street(self.dice, level)
                else:
                    # Outside is the road's table, the chance pro rata by the time the
                    # step takes (the published 20% a six-hour watch).
                    met = ontheway.road(self.dice, step_hours or 1, hop.terrain, level,
                                        **({} if step_hours else {"minutes": step}))
                minutes += step
                if step_hours and not underway:
                    # Only the part walked before the meeting, for a march of hours.
                    far_walked = ontheway.hours_walked(met, step_hours) \
                        if met is not None else step_hours
                if met is not None:
                    going_to = hop
                    break
                passed.append(hop)
                prev = hop
            # The last hop of a quiet walk is the destination, and the tell names that
            # separately. An interrupted walk stops somewhere that is now the
            # destination, so everything in hand is a place passed through.
            kept = passed if met is not None else passed[:-1]
            went_by = tuple(p.name for p in kept)
            went_by_about = [{"name": p.name, "about": p.about} for p in kept if p.about]

        # Read AFTER the walk, against the place the party actually reached. Until
        # 2026-09-23 this block ran first, against the place the plan named, so a
        # suspected character stopped one hop short of the gate by a hawker was told
        # "the guards at the gate look twice, and let you through" about a gate they
        # never got to. A wanted one stopped short is now simply stopped short: the
        # refusal is for reaching the arch, and they did not.
        #
        # The gate reads the warrant (docs/wanted.md, reader one). The town is the one
        # whose ground the party is standing on — read off the place id, and off the
        # scene's location only when the id cannot say — so a warrant from the last
        # town does not shut this one's gate. Two ways out are watched: the gate
        # itself, by name, and the open road, which is a travel by BIOME off urban
        # ground. A travel by place to somewhere already made outside the walls — the
        # cave the party ventured into yesterday — is not watched; nor is `venture`,
        # which has its own op. That is the "another way" the refusal names, and the
        # only reason the refusal can be honest about a way out existing.
        #
        # A refusal, printed: the player may not know the warrant reached the gate,
        # and the fix is named — the founded and ventured ground, or clear the name.
        # Suspected is a line in the tell, never a refusal: the watch looks twice and
        # lets you through, which is the difference between the two states.
        law_line = ""
        if moved and pc is not None:
            refused, law_line = self.watch_at_the_way_out(pc, was_place, going_to, known)
            if refused:
                return self._refuse(intent, refused)

        left: list[str] = []
        walked_back = 0
        stayed_down: list[str] = []
        fight_ended = False
        xp_line = ""
        dying_tells: list[str] = []
        if moved:
            # In this order: pay, then end, then walk. `_settle_xp` needs the sides and
            # the bodies, `end_encounter` clears the sides, and a fight walked out of
            # used to pay nothing without a word — the tell below carries the line.
            if self.scene.in_encounter:
                xp_line = self._settle_xp()
                self.scene.end_encounter()
                fight_ended = True
            for a in list(self.scene.actors.values()):
                if a.is_pc:
                    continue
                if a.ref in escorts and a.is_down:
                    # The dead and the dying are not eligible even when named: they
                    # stay where they fell. Said, rather than silently dropped.
                    stayed_down.append(a.name)
                    escorts.remove(a.ref)
                if a.ref not in escorts:
                    # Three doors used to shed people and only two resolved the dying
                    # first; travel left them bleeding with no tell. Nobody bleeds out
                    # in silence because the party changed rooms.
                    if a.has_state("state.down.dying"):
                        dying_tells.extend(self._resolve_dying(a))
                    # Not the hidden, not the dead: "Left behind: the man hiding in
                    # the back room and the body" is a fact the character does not
                    # hold, and the tell lands on the visible card.
                    if a.has_state("state.hidden") or a.has_state("state.down.dead"):
                        continue
                    # Nor whoever keeps the room being walked out of. "Left behind:
                    # Gorvothys Vyrnys" of the stallholder standing at her own stall
                    # reads as an abandoned companion; she is where she lives, and the
                    # party is the one who left. A keeper who has come away from their
                    # place and is then dropped IS left behind, and is said.
                    if keepers.place_of(getattr(a, "world_entity_id", "") or "") == a.at:
                        continue
                    left.append(a.name)
            if pc is not None:
                self.scene.move(pc.ref, going_to.id)
                # The walk's minutes, charged once (the hop sum above). This was an hour
                # for a step between the walls and open ground and nothing for anything
                # else — the playtest measured a two-hour wild place reached in no time,
                # and then a village crossed twice with the clock still on 08:00. Minutes
                # are the clock's and not the body's, as the hour was.
                if minutes:
                    self.scene.advance(minutes, charge_body=False)
                # Ground beyond the near land is hours or days: a march, charged to the
                # body day by day with a camp between, the rule a journey pays.
                if far_walked:
                    self._march(pc, far_walked, going_to.terrain)
                # The gallop's toll on the mounts, as the journey pays it: a point of
                # lethal damage and fatigued for each day galloped past the free hour,
                # through the one applicator (a condition with the book's eight hours on
                # its clock). A ride cut short by a meeting hurt them only for the days
                # it actually lasted.
                if far_hurt and mount_refs:
                    days_out = max(1, -(-far_walked // journey_mod.HOURS_PER_DAY))
                    hurt = min(far_hurt, days_out)
                    for ref in mount_refs:
                        # The store, not the view: the PC has moved and the mounts
                        # follow below, so for this moment they stand in the old place.
                        horse = self.scene.people.get(ref)
                        if horse is None:
                            continue
                        horse.take_damage(hurt)
                        horse.add_condition(journey_mod.MOUNT_FATIGUE,
                                            rounds=journey_mod.FATIGUE_ROUNDS,
                                            source="hustle")
                        tired_mounts.append(horse.name)
                # Walking back along a road a journey stopped on costs the hours walked
                # out (owner's ruling Q15). The road used to forget itself for free the
                # moment the party was back inside the walls.
                if self.scene.road and (outskirts_mod.is_along(was_place)
                                        or places_mod.setting_of(going_to.id) == "in"):
                    back = int(self.scene.road.get("walked") or 0)
                    if back and places_mod.setting_of(was_place) == "outside":
                        self._march(pc, back, places_mod.terrain_of(was_place))
                        walked_back = back
                    self.scene.road = {}
            else:
                # A scene with no player (some tests) is placed rather than moved: the
                # party record has three writers and this door is not a fourth.
                self.place_party(going_to.id)
            for ref in escorts:
                self.scene.move(ref, going_to.id)
            # New room, new ground — the rule `place_party` states and this door never
            # kept. `Scene.move` changes where everybody is and touches no map, so
            # travelling from the well to the market left the WELL's floor on screen with
            # nobody standing on it: 5x5 and empty where the market is 12x12 with seven
            # clumps of stalls. Reported 2026-09-21 as "the same map and the scale of the
            # map is way too small", and it was the same map, literally.
            #
            # `place_party` is not called here on purpose — it is the party record's own
            # writer and this path has already moved everybody. What is shared is the
            # discard-and-derive, which is `lay_the_ground`'s whole job.
            self.scene.grid = None
            self.scene.positions.clear()
            # A fire burns where it was lit (I3). Its squares are the old place's map, and
            # left standing they would burn whoever stood on the same numbers here — so a
            # fire in a place walked out of is taken down through the one door. Nothing
            # keeps a place's fires while the party is away; it has burnt out by the time
            # anybody could come back to look (2d4 × 10 minutes).
            for w in list(self.scene.wards):
                spec = w.spec or {}
                if spec.get("hazard") and spec.get("at", "") != going_to.id:
                    made = next((m for m in self.scene.manifests
                                 if m.id == w.manifest_id), None)
                    if made is not None:
                        self.scene._end_standing(made)
                    self.scene._end_standing(w)
            self.lay_the_ground()
            # After every move, for the reason `settle_relations` gives.
            self.scene.settle_relations()
            # The one journey this batch is spent. Set only where the party actually
            # moved: a refused travel, or a travel to the ground already underfoot,
            # costs the turn nothing and must not bar the real one behind it.
            self._journeyed = going_to.name
            # Back inside the walls is off the road. `scene.road` remembers how far
            # along an interrupted road the party got, keyed on the settlement they set
            # out from — and walking back into that settlement does not change the
            # key, so until 2026-09-23 a party stopped three hours out, back in town
            # for the night, set out next morning with three hours already credited.
            # The road remembers only while you are on it.
            if self.scene.road and places_mod.setting_of(going_to.id) == "in":
                self.scene.road = {}
            # Walking out is walking away: the conversation ends, and the tell says
            # they were left mid-sentence if no leave was taken (2026-09-24).
            parted = self.end_talk("walked away")
            # And whoever keeps the room they have just walked into, if it is a room
            # somebody keeps and nobody has kept it yet.
            self.staff_the_place()

        # Whoever the walk ran into arrives by the one door creatures arrive by, onto
        # the ground that has just been laid. After the move, never before: they are in
        # the place the party stopped at, and `_bring_in` places them on its grid.
        met_tell = ""
        met_refs: list[str] = []
        if met is not None:
            # The watch reads the warrant here too, which is the half this band shipped
            # without: the gate is where a warrant is enforced, and the street is where
            # it stops being comfortable. One reader (`states.standing_with_the_law`),
            # the same one the gate uses.
            law_now = ""
            if pc is not None:
                law_now = states.standing_with_the_law(
                    pc, places_mod.location_of(self.scene.at) or self.scene.location_id)
            made = self._meet_on_the_way(met, zone="near")
            met_refs = [m["ref"] for m in made]
            # A stop names who and why (Lane B, item 16.3): "the watch comes down the
            # road … You get no further" became background prose — "the watchmen are
            # making their rounds" — because the tell never said who had stopped you.
            met_tell = ontheway.describe(
                met, going_to.name, law=law_now,
                who=[self.scene.actors[r].name for r in met_refs if r in self.scene.actors])
            if met.kind == "weather":
                # The one band that is nobody. It costs what it costs on the road
                # between towns — hours, off the clock — and here it costs the same,
                # because a storm on the hour outside the walls is the same storm.
                # Before 2026-09-23 this band was not guarded at all on this door: a
                # weather roll on a wild hop asked `_bring_in` for zero of an empty
                # template, which instantiates one creature named "" and raises — a
                # 502 with the player's sentence deleted, once in roughly every 220
                # trips outside the walls.
                weathered = self.dice.roll(ontheway.WEATHER_HOURS,
                                           label="how long it holds you",
                                           visibility="hidden").total
                self.scene.advance(weathered * survival.MINUTES_PER_HOUR,
                                   charge_body=False)
                met_tell += (f" {weathered} hour{'s' if weathered != 1 else ''} go "
                             f"by before it lets you.")
            if met.kind == "cutpurse" and pc is not None and made:
                met_tell += self._cutpurse(pc, self.scene.actors[made[0]["ref"]])
            elif met.kind == "patrol" and law_now == "wanted" and made:
                # Hostile, not arrested: there is no arrest in this app and inventing
                # one here would be a rule with one home. What the warrant buys the
                # watch is that they come for you — and `_law_joins` already knows that
                # every guard in a town where you are wanted is on the other side.
                from . import attitude as attitude_mod

                for m in made:
                    self.settle_attitude(self.scene.actors[m["ref"]],
                                         attitude_mod.HOSTILE, None,
                                         "the watch has your name")
            elif met.aggressive and pc is not None and made:
                self._ensure_encounter(pc.ref, target=made[0]["ref"])

        note = str(intent.params.get("note") or "").strip()
        bits = []
        if moved and parted:
            bits.append(parted)
        if not moved:
            bits.append(f"You are already at {going_to.name}.")
        setting = places_mod.setting_of(self.scene.at if moved else going_to.id)
        was_setting = places_mod.setting_of(was_place)
        direction = ""
        if moved:
            inside = ("in", "under")
            direction = ("out" if was_setting in inside and setting == "outside" else
                         "in" if was_setting == "outside" and setting in inside else
                         "along")
        if moved and direction == "out":
            # Leaving is said as leaving. Bobby's "I leave the village" came back as "the
            # gates of Vormoor open to receive you" (item 16.4): the tell named a place
            # and never a direction, and the prose picked one.
            town_name = str(getattr(found_loc, "name", "") or "the settlement")
            bits.append(f"You leave {town_name} behind.")
        elif moved and direction == "in":
            town_name = str(getattr(found_loc, "name", "") or "the settlement")
            bits.append(f"You come back into {town_name}.")
        if going_to.terrain != was_ground:
            bits.append(f"The ground changes: {biomes.describe(going_to.terrain).lower()}.")
        if went_by:
            # The places the walk actually crossed, said as fact. The narrator is asked
            # to describe them (see `gm/prompts.scene_brief`) and can only do that if
            # the engine says which ones they were — a model left to infer the route
            # invents streets, which is the failure this whole module exists to stop.
            #
            # And each with its own line (item 16.2): "The way there ran through the
            # well" gave the page half a sentence to walk. The place's own words — the
            # world's where it wrote them — are the material; a check (`route_walked`)
            # asks that the prose walks them.
            abouts = {row["name"]: str(row["about"]).strip().rstrip(".")
                      for row in went_by_about}
            said_route = [f"{n} ({abouts[n]})" if abouts.get(n) else n for n in went_by]
            bits.append(f"The way there ran through {_and_then(tuple(said_route))}.")
        if moved:
            bits.append(f"You are at {going_to.name} now.")
        if moved and direction == "out" and found_loc is not None:
            from . import geography

            land = geography.land_around(self.world, found_loc)
            if land.near or land.beyond:
                close = geography._listed(land.near) or "open ground"
                further = (f", and {geography._listed(land.beyond[:2])} beyond it"
                           if land.beyond else "")
                bits.append(f"Past the last house the land opens: {close}{further}.")
        spent = minutes + (far_walked + walked_back) * 60
        if moved and spent:
            from . import geography

            bits.append(f"It takes {geography.walk_words(spent)}.")
        if walked_back:
            bits.append("The road you had walked out along is walked back, every hour of it.")
        if moved and mount_refs and (ridden_minutes or far_hours):
            # The pace said, and what it cost the mounts, in words (the third law).
            bits.append("Mounted, the ground outside goes by at "
                        + ("a gallop." if pace == "gallop" else "twice a walker's pace."))
            if tired_mounts:
                bits.append(f"The gallop has blown {', '.join(tired_mounts)}: pushed past "
                            f"the first hour, a mount is hurt by it and tires.")
        if met_tell:
            bits.append(met_tell)
        if met is not None and meant_for != going_to.name:
            # Said plainly, because the player asked for somewhere else and needs to
            # know they did not get there — the roguelike's "you were interrupted", and
            # the thing that makes the next turn's repeat of the command make sense.
            bits.append(f"You were making for {meant_for} and got no further than "
                        f"{going_to.name}.")
        if fight_ended:
            bits.append("The fight is left behind." + xp_line)
        if stayed_down:
            bits.append(f"{', '.join(stayed_down)} cannot come: they stay where they fell.")
        bits.extend(dying_tells)
        if left:
            bits.append(f"Left behind: {', '.join(left)}.")
        if fell_away:
            bits.append(f"{', '.join(fell_away)} does not come with you any more.")
        if law_line:
            bits.append(law_line)
        if note:
            bits.append(note)
        effect = {"kind": "biome", "biome": going_to.terrain, "was": was_ground,
                  "left": left, "place": self.scene.at, "was_place": was_place,
                  "fight_ended": fight_ended, "went_by": list(went_by),
                  "met": met.kind if met is not None else ""}
        # The register's fields (docs/fix-interfaces.md §2.7), each only when set.
        extra = {"minutes": spent if moved else 0,
                 "went_by_about": went_by_about,
                 "setting": setting, "was_setting": was_setting,
                 "direction": direction,
                 "stopped_short": bool(met is not None and meant_for != going_to.name),
                 "meant_for": meant_for if met is not None and meant_for != going_to.name
                 else "",
                 "met_refs": met_refs, "grounded": grounded_as,
                 "road_to": self._road_to(going_to.id) if moved else ""}
        if moved and mount_refs and (ridden_minutes or far_hours):
            # The journey's own keys (§2.7's `journey` row), so one reader serves both.
            extra.update(pace=pace, mounts=list(mount_refs), tired=list(tired_mounts),
                         on_foot_hours=far_on_foot)
        effect.update({k: v for k, v in extra.items() if v})
        return Outcome(
            intent_id=intent.id, op="travel",
            effects=[effect],
            tell=" ".join(bits),
            because=intent.because,
        )

    def _road_to(self, place_id: str) -> str:
        """The World Bible id of the settlement a road head leads to, or ""."""
        from . import journey as journey_mod
        from . import outskirts as outskirts_mod

        slug = outskirts_mod.road_head_of(place_id)
        if not slug or self.world is None:
            return ""
        from . import places as places_mod

        for leg in journey_mod.legs_from(self.world, self.scene.location_id):
            if places_mod._slug(str(leg.to_id).replace("-", " ").replace("_", " ")) == slug:
                return leg.to_id
        return ""

    def _absent_ground(self, intent: Intent, biome: str, known) -> "Outcome | None":
        """A move onto ground the world says is not around this settlement, refused and
        shown (docs/playtest-2026-09-28.md, 20.2), or None when the ground is there, is
        further out, or the world said nothing (`unknown` is accepted and recorded — the
        three-way honesty `journey.pace` already keeps).

        Player-fixable (`absent_ground`, docs/fix-interfaces.md §2.6): the refusing fact
        is the world, not the plan's choice of a ref, and the player's fix is to name
        ground that is there — so the page shows the sentence and the plan loop does not
        spend seven retries on it.
        """
        from . import geography
        from . import outskirts as outskirts_mod
        from . import places as places_mod

        found = self.world.get(self.scene.location_id) if self.world else None
        if found is None or not places_mod._settled(found, ""):
            return None
        land = geography.land_around(self.world, found)
        how, _redirect = geography.grounded(land, biome)
        if how != "absent":
            return None
        name = str(getattr(found, "name", "") or "here")
        said = [f"There is no {biomes.describe(biome).split(',')[0].lower()} near {name}."]
        if land.near:
            said.append(f"Outside it is {', '.join(land.near)}.")
        if land.beyond:
            said.append(f"Further out, {', '.join(land.beyond)}.")
        wider = next((w for _who, w in land.words if geography.ground_in(w)), "")
        if wider:
            said.append(f"The wider land is {wider.rstrip('.')}.")
        sentence = " ".join(said)
        go = next((p.name for p in known if places_mod.is_ring(p.id)
                   and p.name in (outskirts_mod.FIELDS, outskirts_mod.SHORE)
                   and p.terrain in land.near), "") \
            or next((p.name for p in known if p.name == outskirts_mod.OUTSKIRTS), "")
        out = self._refuse(intent, sentence, code="absent_ground", for_a_person=sentence,
                           fix={"kind": "go", "place": go} if go else None)
        import dataclasses

        return dataclasses.replace(out, effects=[
            {"kind": "refused-ground", "biome": biome,
             "near": list(land.near), "beyond": list(land.beyond)}])

    def _meet_on_the_way(self, met, *, zone: str) -> list[dict]:
        """Whoever a meeting is, put on the board where the party now stands.

        The one bring-in for the three doors that move the party — `travel`, `journey`
        and, through travel, `venture`. It was three copies, and one of them (travel's)
        was missing the guard the other two had: a weather meeting is NOBODY — count
        zero, no template — and `_bring_in` reads a count of zero as one, so travel's
        copy asked for one creature named "" and got `UnknownTemplate`, which at
        resolution time is a 502 with the player's sentence deleted. Found 2026-09-23
        reading the code; reproduced by forcing the road's table to weather on a hop to
        the forest.

        Returns what `_bring_in` made. The caller decides what follows — a cutpurse's
        hand, a warrant, a fight — because those are the door's own business.
        """
        if met is None or int(getattr(met, "count", 0) or 0) < 1:
            return []
        made = self._bring_in(
            met.template or "guildhand", count=met.count,
            name=(met.creature or {}).get("name")
                 or (met.words[0].title() if met.words else None))
        for m in made:
            self.scene.zones[m["ref"]] = zone
            self.scene.positions.pop(m["ref"], None)
        if self.scene.grid is not None and self.scene.positions:
            self.scene.place_by_zone([m["ref"] for m in made])
        return made

    def _cutpurse(self, pc, thief) -> str:
        """A hand in the purse, resolved by the book and not by a flat chance.

        "Sleight of Hand DC 20 to lift a small object from another person" — and the
        mark's Perception is the opposed roll against it (Core Rulebook, Sleight of
        Hand). Both rolls are the engine's and both are hidden: the player is not
        offered a Perception popup, because being *asked* to roll Perception is itself
        the tell that something is being taken, which is the oldest way there is to
        ruin this encounter. What the player is told is what their character notices.

        The coin moves through `goods.spend`, the one door money leaves a purse by, so
        a thief cannot take copper that is not there.
        """
        take = self.dice.roll(ontheway.LIFT_DICE, label="a handful of small coin",
                              visibility="hidden").total
        lift = self.dice.d20(thief.skill_modifiers("sleight of hand"),
                             label=f"{thief.name} Sleight of Hand", visibility="hidden")
        spot = self.dice.d20(pc.skill_modifiers("perception"),
                             label=f"{pc.name} Perception", visibility="hidden")
        if lift.total < max(ontheway.LIFT_DC, spot.total):
            return (" A hand is on your purse, and you have hold of the wrist it "
                    "belongs to.")
        purse, enough = goods.spend(pc.purse, take)
        if not enough:
            return (" A hand comes away from your purse with nothing in it: there is "
                    "nothing in it to take.")
        pc.purse = purse
        return (f" They are gone into the crowd before you feel it, and your purse is "
                f"{take} copper lighter.")

    def _too_busy_to_forage(self, actor) -> str:
        """Why this character cannot wander off looking for herbs, or "".

        Foraging is an hour at minimum and forty-eight at most, spent alone with your eyes
        on the ground. Neither of the two things that make that impossible was being
        checked: a character could forage for a day and a half in the middle of a fight,
        or walk away mid-sentence and come back with a satchel and no lost time.

        Company is the test for conversation rather than any dialogue flag, because the
        engine has no such flag and inventing one would mean the GM had to remember to set
        it. Somebody standing in front of you is the fact that matters either way.

        Phrased as a whole sentence rather than a clause, because the bench prints it
        verbatim: a fragment came out as "You are not while you are with a road warden."
        """
        if self.scene.in_encounter:
            return ("You are in a fight. Foraging is an hour on your hands and knees "
                    "at the very least — end the encounter first.")
        talking = self.talking_to()
        if talking:
            return (f"You are talking with {', '.join(a.name for a in talking)}. "
                    f"Take your leave first.")

        # Unconscious company is not company, and neither is your own reflection.
        here = [a for ref, a in self.scene.actors.items()
                if ref != actor.ref and self.scene.conscious(ref)]
        if here:
            names = ", ".join(sorted(a.name for a in here[:3]))
            more = ", and others" if len(here) > 3 else ""
            return (f"You are with {names}{more}. Foraging takes hours alone — "
                    f"leave the scene first.")
        return ""

    def _op_loot(self, intent: Intent, partial: dict) -> Outcome:
        """Strip a body, and mean it: everything it carried moves to the looter.

        The measured gap, same class as the sale that was prose and nothing else: "I
        loot the watchman I take everything" got a paragraph of coins, trinkets and a
        sword, and the inventory page showed a traveler's outfit. The engine owns the
        corpse's pockets. Only the down and the dead can be looted — taking from
        somebody on their feet is a steal manoeuvre with an opposed roll, not this.
        """
        who = intent.actor or (self.scene.pc().ref if self.scene.pc() else None)
        looter = self.scene.actors.get(who) if who else None
        if looter is None:
            raise IntentError("loot: nobody here to do the taking", "refs")
        body = self.scene.actors.get(str(intent.params.get("from_", "")))
        if body is None:
            # Validated a moment ago and gone now: a travel earlier in the same list
            # left the room, or the ageing loop swept the body between turns. Nothing
            # the player did wrong, so nothing is raised — and under containment the
            # body may simply be in the room they left, which is said.
            away = self._elsewhere(str(intent.params.get("from_", "")))
            return self._refuse(
                intent, away or "There is no body here to loot.")
        # The same question the watcher asks, spelled the same way. Both said
        # `hp <= 0 or state.down`, which differs from `is_down` at exactly 0 hit
        # points — and there the creature is *disabled*: conscious, upright, and
        # being stripped of its belongings where it stood.
        if not body.lootable:
            return Outcome(
                intent_id=intent.id, op="loot", effects=[],
                tell=(f"{body.name} is on their feet and very much attached to their "
                      f"belongings. Taking from the living is a steal, and they get "
                      f"a say in it."), because=intent.because)

        # First observation: Schrödinger's pockets collapse here, rolled and stored
        # the moment somebody actually looks, immutable after.
        from .bestiary import collapse_kit
        collapse_kit(body)

        taken: list[str] = []
        effects: list[dict] = []
        for w in list(body.weapons):
            if w and w != "unarmed":
                looter.weapons.append(w)
                taken.append(w)
        body.weapons = []
        if body.armour and body.armour != "none":
            looter.carry(body.armour.replace(" ", "-"), 1)
            taken.append(body.armour)
            body.armour = "none"
        for coin, n in dict(body.purse).items():
            looter.purse[coin] = looter.purse.get(coin, 0) + n
            taken.append(f"{n} {coin}")
        body.purse = {}
        for iid, n in dict(body.inventory).items():
            looter.carry(iid, n)
            taken.append(f"{n}x {iid}")
        body.inventory = {}
        for sid, stock in dict(body.stock).items():
            looter.add_stock(stock, stock.count)
            taken.append(stock.name)
        body.stock = {}
        if taken:
            effects.append({"ref": looter.ref, "kind": "took",
                            "from": body.ref, "items": taken})
            tell = (f"{looter.name} strips {body.name}: "
                    + ", ".join(taken) + ". It is all real now — carried, counted, "
                    f"and on the sheet.")
        else:
            tell = f"{body.name} has nothing left worth taking."
        return Outcome(intent_id=intent.id, op="loot", effects=effects,
                       tell=tell, because=intent.because)

    def _op_forage(self, intent: Intent, partial: dict) -> Outcome:
        """Search the ground here for what grows on it.

        The table is assembled from the ingredient list rather than authored per biome:
        thirteen biomes across a hundred and sixty ingredients is two thousand rows nobody
        would keep current, and a herb added tomorrow should appear on every table it
        belongs to without anyone editing one.
        """
        who = intent.actor or (self.scene.pc().ref if self.scene.pc() else None)
        actor = self.scene.actors.get(who) if who else None
        if actor is None:
            raise IntentError("forage: nobody here to look", "refs")

        busy = self._too_busy_to_forage(actor)
        if busy:
            # A refusal outcome, not an IntentError — same shape as the untrained
            # check's "Nothing is rolled". Raising here put the spoken path into a
            # death spiral: `declared_ops` makes the schema REQUIRE the forage op the
            # player declared, so every one of the five attempts carried it, every one
            # was refused for company, and the player got a 502 where "foraging takes
            # hours alone" should have been. The reason was always printable; now it
            # is printed.
            return Outcome(intent_id=intent.id, op="forage", effects=[],
                           tell=f"No foraging happens. {busy}",
                           because=intent.because)

        # The ground underfoot, and nothing else. Foraging used to honour a `biome`
        # parameter, which meant a request could search a forest from the middle of a
        # city — the bench sent one and the GM could invent one. Where you are is a fact
        # the scene owns; `travel` is the only thing that changes it.
        biome = biomes.canonical(str(self.scene.biome or ""))
        if biome is None:
            return self._refuse(
                intent, "The ground here has not been named, so there is nothing to "
                        "search. Travel somewhere first.")

        track_id = str(intent.params.get("track") or "herbalist").strip().lower()
        try:
            track = worldclass.get(track_id)
        except KeyError:
            # A craft the world does not have is a fact about the world, not a
            # malformed intent; said, and the search does not happen.
            return self._refuse(
                intent, f"There is no craft called {track_id} to forage by. Foraging "
                        f"uses herbalist unless another craft is named.")
        level = actor.track(track.id).level
        ceiling = worldclass.tier_rank(track.at(level).max_tier)

        hours = max(1, int(intent.params.get("hours", 1) or 1))

        # The player rolls their own Survival — the popup, with the herbalism bonus in
        # the breakdown where they can see what the track is worth. Raised before
        # `pass_hours` because everything below this line mutates: a suspend after the
        # toll would charge the body twice for the same day when the roll came back.
        # The player's face is spent on the first hour; the engine rolls the rest.
        face = None
        if actor.is_pc:
            if "player_face" in partial:
                face = int(partial.pop("player_face"))
            else:
                mods = foraging.check_mods(actor, level)
                raise _NeedsPlayerRoll({
                    "label": f"Survival check — foraging ({biome})",
                    "die": "1d20",
                    "actor": actor.name,
                    "min": 1,
                    "max": 20,
                    "modifier": sum(m.value for m in mods),
                    "breakdown": [m.as_dict() for m in mods],
                    "dc": foraging.dc_for(biome),
                    "because": intent.because,
                    "intent_id": intent.id,
                }, {})

        # Foraging takes real time now, a minimum of an hour and as long as the player
        # asks for. The body is consulted for every hour of it — see rules/survival.py —
        # and a character who goes over is stopped at the hour they actually fell over
        # rather than at the end of the stretch they meant to work.
        toll = survival.pass_hours(actor, hours, self.dice, biome=biome)
        worked = max(1, toll.hours)

        result = foraging.forage(biome, level, ceiling, self.dice, hours=worked,
                                 actor=actor, first_face=face)
        result["asked_for"] = hours
        result["toll"] = toll.as_dict()
        for iid, n in result["found"].items():
            # Stamped with the world clock, so the 48 hours an animal part has can
            # be counted from something. Salt, if the character has any, is applied
            # here rather than as a separate action — "preservation can be automatic if
            # i have salt", and the turn you pick a gland up is the turn you are least
            # likely to be thinking about when it goes off.
            actor.carry(iid, n, pristine=result["pristine"].get(iid, 0),
                        at_minute=self.scene.clock_minutes)

        # After `carry` above, deliberately: herbs are stamped with the clock as it
        # reads when they are picked, so advancing first would hand the player up to
        # forty-eight hours of free freshness. And `worked` is what the body actually
        # managed — pass_hours can stop early — so the number is only known here.
        # `charge_body=False`: `survival.pass_hours` above has already charged the body
        # for exactly these hours, and rolled the checks that go with them.
        self.scene.advance(worked * survival.MINUTES_PER_HOUR, charge_body=False)

        span = f"{worked} hour{'s' if worked != 1 else ''}"
        if result["empty"]:
            tell = (f"{actor.name} spends {span} and knows nothing that grows in "
                    f"{biomes.describe(biome).lower()}.")
        elif result["found"]:
            got = ", ".join(f"{n}× {ing_mod.get(i).name}"
                            for i, n in result["found"].items())
            tell = f"{span} of looking: {actor.name} comes back with {got}."
            if result["pristine"]:
                best = ", ".join(ing_mod.get(i).name for i in result["pristine"])
                tell += f" The {best} came up perfect."
        else:
            tell = f"{actor.name} spends {span} and finds nothing worth carrying."

        spoiled = [h["wrecked"] for h in result["hourly"] if h.get("wrecked")]
        if spoiled:
            tell += (f" {len(spoiled)} hour{'s' if len(spoiled) != 1 else ''} came to "
                     f"nothing but a spoiled {spoiled[0]}.")
        if toll.checks:
            tell += f" It cost them: {survival_note(toll)}"
        if worked < hours:
            tell += (f" They meant to keep at it for {hours} and did not last.")

        # Once per expedition, the ground answers back (`rules/gathering.py`): a
        # rich patch, a bear, or a hollow full of the good stuff with something
        # sitting on it. After the haul is carried, because a rich find doubles what
        # was actually found, and a guarded one is booked rather than handed over.
        effects = [{"ref": actor.ref, "kind": "forage", **result}]
        tell += self._gathering_encounter(actor, biome, level, "herbs",
                                          found=result["found"], effects=effects)

        return Outcome(
            intent_id=intent.id, op="forage", effects=effects,
            tell=tell, because=intent.because,
        )

    def _gathering_encounter(self, actor, biome: str, level: int, what: str, *,
                             found: dict | None = None, stock: list | None = None,
                             effects: list) -> str:
        """The expedition's one encounter roll, applied. Returns the tell's clause.

        A rich find multiplies the haul in hand. A creature is brought on by the one
        door creatures come in by (`_bring_in`), far off; an aggressive one starts the
        fight the moment it is seen, with the player's own first swing still theirs.
        A guarded find is booked on the scene and paid when the guard is down or gone
        (`_settle_guarded_finds`), so the vein is real and the fight for it is real.
        """
        from . import gathering

        pc = self.scene.pc()
        enc = gathering.roll(biome, max(1, int(level)), self.dice)
        if enc.kind == "quiet":
            return ""
        clause = " " + gathering.describe(enc, what)
        effects.append({"kind": "gathering", "encounter": enc.kind, "roll": enc.roll,
                        "creature": (enc.creature or {}).get("name", ""),
                        "aggressive": enc.aggressive})
        if enc.kind == "rich":
            for iid, n in list((found or {}).items()):
                actor.carry(iid, int(n) * (enc.yield_times - 1),
                            at_minute=self.scene.clock_minutes)
            for s in stock or []:
                actor.add_stock(crafting.Stock(base=s["base"], tier=s.get("tier", "common"),
                                               kind=s.get("kind", "ore"),
                                               craft=s.get("craft", "smithing")),
                                int(s.get("count", 1)) * (enc.yield_times - 1))
            return clause
        made = self._bring_in(enc.creature["id"], count=1, name=enc.creature["name"])
        ref = made[0]["ref"]
        self.scene.zones[ref] = "far"
        self.scene.positions.pop(ref, None)
        if self.scene.grid is not None and self.scene.positions:
            self.scene.place_by_zone([ref])
        if enc.kind == "guarded":
            self.scene.guarded_finds.append({
                "guard": ref, "what": f"{what} find",
                "found": {iid: int(n) * enc.yield_times for iid, n in (found or {}).items()},
                "stock": [dict(s, count=int(s.get("count", 1)) * enc.yield_times)
                          for s in (stock or [])],
            })
        elif enc.aggressive and pc is not None and actor.ref == pc.ref:
            self._ensure_encounter(pc.ref, target=ref)
        return clause

    def _op_prospect(self, intent: Intent, partial: dict) -> Outcome:
        """Search the ground here for what can be dug out of it.

        The forage op's shape, against the blacksmith's stock list instead of the
        herbalist's: the ores that carry this biome in their tags are the table, the
        Survival check and the hours and the body's toll are the same, and the
        expedition rolls the same encounter — "a search for ore and find a massive
        vein guarded by a cave worm".
        """
        from . import blacksmith

        who = intent.actor or (self.scene.pc().ref if self.scene.pc() else None)
        actor = self.scene.actors.get(who) if who else None
        if actor is None:
            raise IntentError("prospect: nobody here to look", "refs")
        busy = self._too_busy_to_forage(actor)
        if busy:
            return Outcome(intent_id=intent.id, op="prospect", effects=[],
                           tell=f"No prospecting happens. {busy}", because=intent.because)
        biome = biomes.canonical(str(self.scene.biome or ""))
        if biome is None:
            return self._refuse(
                intent, "The ground here has not been named, so there is nothing to "
                        "search. Travel somewhere first.")
        ores = [m for m in blacksmith.materials().values()
                if m.kind == "ore" and biome in (m.biomes or [])]
        if not ores:
            return Outcome(intent_id=intent.id, op="prospect", effects=[],
                           tell=f"{actor.name} looks, and there is no ore in "
                                f"{biomes.describe(biome).lower()} to find.",
                           because=intent.because)
        hours = max(1, int(intent.params.get("hours", 1) or 1))
        level = actor.track("blacksmith").level if hasattr(actor, "track") else 1
        face = None
        if actor.is_pc:
            if "player_face" in partial:
                face = int(partial.pop("player_face"))
            else:
                mods = foraging.check_mods(actor, level)
                raise _NeedsPlayerRoll({
                    "label": f"Survival check — prospecting ({biome})",
                    "die": "1d20", "actor": actor.name, "min": 1, "max": 20,
                    "modifier": sum(m.value for m in mods),
                    "breakdown": [m.as_dict() for m in mods],
                    "dc": foraging.dc_for(biome), "because": intent.because,
                    "intent_id": intent.id,
                }, {})
        toll = survival.pass_hours(actor, hours, self.dice, biome=biome)
        worked = max(1, toll.hours)
        dc = foraging.dc_for(biome)
        mods = foraging.check_mods(actor, level)
        bonus = sum(m.value for m in mods)
        # Common ore is the bulk of any seam; rarer ore turns up when the check clears
        # the DC by more. The player's face on the first hour, the engine's after.
        stock: list[dict] = []
        for hour in range(worked):
            die = face if (hour == 0 and face is not None) else self.dice.roll(
                "1d20", label="prospecting", visibility="hidden").total
            margin = die + bonus - dc
            if margin < 0:
                continue
            tiers = ["common"] + (["uncommon"] if margin >= 5 else []) \
                + (["rare"] if margin >= 10 else [])
            pool = [m for m in ores if m.tier in tiers] or ores
            pick = pool[self.dice.roll(f"1d{len(pool)}", label="which ore",
                                       visibility="hidden").total - 1]
            count = 1 + margin // 5
            stock.append({"base": pick.name, "tier": pick.tier, "kind": "ore",
                          "craft": "smithing", "count": count})
        for s in stock:
            actor.add_stock(crafting.Stock(base=s["base"], tier=s["tier"], kind="ore",
                                           craft="smithing"), s["count"])
        self.scene.advance(worked * survival.MINUTES_PER_HOUR, charge_body=False)
        span = f"{worked} hour{'s' if worked != 1 else ''}"
        if stock:
            got = ", ".join(f"{s['count']}× {s['base']}" for s in stock)
            tell = f"{span} of digging: {actor.name} comes back with {got}."
        else:
            tell = f"{actor.name} spends {span} and turns up nothing worth carrying."
        if toll.checks:
            tell += f" It cost them: {survival_note(toll)}"
        effects = [{"ref": actor.ref, "kind": "prospect", "stock": stock,
                    "hours": worked, "toll": toll.as_dict()}]
        tell += self._gathering_encounter(actor, biome, level, "ore",
                                          stock=stock, effects=effects)
        return Outcome(intent_id=intent.id, op="prospect", effects=effects,
                       tell=tell, because=intent.because)

    # --- the doors places come in by (rules/places.py) --------------------------------

    def _parent_place(self, wanted: str):
        from . import places as places_mod

        known = self.places()
        if not str(wanted or "").strip():
            return self.here(), known
        return places_mod.find(known, str(wanted)), known

    # --- quests: a task taken up (rules/cards.py, kind "quest") ------------------------------

    def _op_quest(self, intent: Intent, partial: dict) -> Outcome:
        """Somebody has given the party a task and the party has taken it. The GM
        proposes it; the engine keeps it as a card with objectives, a giver who must be
        a person on the board (or a name the world knows), and a promise in words —
        never a number. Taking a quest pays nothing; finishing it pays the story award.
        """
        from . import cards as cards_mod

        title = " ".join(str(intent.params.get("title") or "").split()).rstrip(".")
        if not (4 <= len(title) <= 80):
            return self._refuse(intent, "A quest needs a title of a few words.")
        raw = intent.params.get("objectives")
        if isinstance(raw, str):
            raw = [x for x in re.split(r"[;\n]", raw)]
        objectives = [" ".join(str(o).split()) for o in (raw or []) if str(o).strip()]
        if not objectives:
            return self._refuse(intent, "A quest needs at least one objective — what "
                                        "is to be done, in a sentence each.")
        if len(objectives) > 6:
            return self._refuse(intent, "Six objectives at most; split the rest into a "
                                        "quest of their own.")
        if any(re.search(r"\d", o) for o in objectives) or re.search(r"\d", str(intent.params.get("reward") or "")):
            return self._refuse(intent, "No numbers on a quest: say what is promised in "
                                        "the world's words and the engine will price it.")
        existing = {c.title.lower() for c in cards_mod.quests(self.scene)}
        if title.lower() in existing:
            return self._refuse(intent, f"{title} is already a quest on the table.")
        giver = str(intent.params.get("giver") or "").strip()
        if giver and giver not in self.scene.actors:
            match = [r for r, a in self.scene.actors.items()
                     if not a.is_pc and str(a.name).lower() == giver.lower()]
            if len(match) == 1:
                giver = match[0]
            elif not self.world or self.world.get(giver) is None:
                return self._refuse(
                    intent, f"Nobody here is {giver} to give it. The people here are "
                            f"{', '.join(f'{a.name} ({r})' for r, a in self.scene.actors.items() if not a.is_pc) or 'nobody'}.")
        pc = self.scene.pc()
        card = cards_mod.open_quest(
            self.scene, title=title, objectives=objectives, giver=giver,
            reward=str(intent.params.get("reward") or "")[:120],
            facts=[str(intent.params.get("about") or "")][:1] if intent.params.get("about") else (),
            people=[giver] if giver in self.scene.actors else [],
            place=str(self.scene.at or ""), origin=intent.origin or "gm",
            turn=0)
        giver_name = (self.scene.actors[giver].name if giver in self.scene.actors
                      else giver)
        return Outcome(
            intent_id=intent.id, op="quest",
            effects=[{"kind": "quest", "id": card.id, "title": card.title,
                      "objectives": objectives, "giver": giver}],
            tell=f"{pc.name if pc else 'The party'} takes it on: {card.title}"
                 + (f", for {giver_name}" if giver_name else "") + ". "
                 + " ".join(f"({i + 1}) {o}" for i, o in enumerate(objectives)) + ".",
            because=intent.because)

    def _op_quest_step(self, intent: Intent, partial: dict) -> Outcome:
        """One objective of a quest done. The card ticks; when the last one is done
        the quest resolves and the story award is paid."""
        from . import cards as cards_mod

        wanted = str(intent.params.get("quest") or "").strip().lower()
        live = [c for c in cards_mod.quests(self.scene) if c.live]
        card = next((c for c in live if c.id.lower() == wanted or c.title.lower() == wanted), None)
        if card is None:
            return self._refuse(
                intent, "No such quest is underway. "
                        + ("The quests are: " + "; ".join(f"{c.title} [{c.id}]" for c in live) + "."
                           if live else "Nothing has been taken on yet."))
        try:
            index = int(intent.params.get("objective")) - 1
        except (TypeError, ValueError):
            index = -1
        if not (0 <= index < len(card.objectives)):
            return self._refuse(
                intent, f"{card.title} has objectives 1 to {len(card.objectives)}; say "
                        f"which one was done.")
        if card.objectives[index].get("done"):
            return self._refuse(intent, f"Objective {index + 1} of {card.title} is already done.")
        note = " ".join(str(intent.params.get("note") or "").split())
        if re.search(r"\d", note):
            note = ""
        after = cards_mod.objective_done(self.scene, card.id, index, note=note, turn=0)
        tell = f"Done: {card.objectives[index]['text']} ({card.title}, {after.clock}/{after.clock_max})."
        effects = [{"kind": "quest_step", "id": card.id, "objective": index + 1,
                    "finished": after.stage == "resolved"}]
        if after.stage == "resolved":
            line = self.award_story("new", card.title).strip()
            tell += f" {card.title} is finished." + (f" {line}" if line else "")
            if card.reward:
                tell += f" Promised: {card.reward}."
        return Outcome(intent_id=intent.id, op="quest_step", effects=effects, tell=tell,
                       because=intent.because)

    def _op_found(self, intent: Intent, partial: dict) -> Outcome:
        """The player makes a place from where they stand: a base at a friend's house,
        the alley behind the market. LambdaMOO's `@dig`: a room exists because a
        command created it, with an owner and a link — never because the narrator
        described it. The engine mints the id under the parent; the owner, if any, is a
        person the engine already holds and is granted `holds.place.<slug>` through the
        one applicator; and the base gets a situation card so what is done to it
        accumulates (Blades in the Dark's lair). Standing there is a separate `travel`.
        """
        from . import cards as cards_mod
        from . import places as places_mod
        from .activeeffect import ActiveEffect

        name = " ".join(str(intent.params.get("name") or "").split()).strip(".")
        if not (3 <= len(name) <= 60):
            return self._refuse(intent, "A place needs a name of a few words to be founded.")
        parent, known = self._parent_place(str(intent.params.get("parent") or ""))
        if parent is None:
            return self._refuse(
                intent, f"There is no {intent.params.get('parent')} here to found it off. "
                        f"From here you can reach {', '.join(p.name for p in known)}.")
        there = places_mod.find(known, name)
        if there is not None:
            # Bobby's turns 6 and 7: "I walk to the nearest crossroads" planned a `found`
            # of one. Vormoor has a crossroads now (the ring), and the refusal says to go
            # there — the fix is a place, not a new one.
            return self._refuse(intent, f"{name} is already a place here: {there.name}. "
                                        f"Go there rather than making it again.",
                                fix={"kind": "go", "place": there.name})
        if len(places_mod.children_of(self.scene.founded, parent.id)) >= places_mod.MOST_CHILDREN:
            return self._refuse(
                intent, f"{parent.name} already has as many places hanging off it as one "
                        f"place can hold; found it off somewhere else.")
        owner_ref = str(intent.params.get("owner") or "").strip()
        owner = None
        if owner_ref:
            owner = self.scene.actors.get(owner_ref)
            if owner is None:
                match = [a for a in self.scene.actors.values()
                         if not a.is_pc and str(a.name).lower() == owner_ref.lower()]
                owner = match[0] if len(match) == 1 else None
            if owner is None:
                return self._refuse(
                    intent, f"Nobody here is called {owner_ref} to hold it. The people "
                            f"here are {', '.join(f'{a.name} ({r})' for r, a in self.scene.actors.items() if not a.is_pc) or 'nobody'}.")
        # What it IS, when the plan says: a kind the settlement table knows, and one
        # that makes sense here (`places.fits_here`). A name that is itself a kind —
        # "the docks" — needs no `kind` to say so.
        kind = str(intent.params.get("kind") or "").strip().lower().removeprefix("the ")
        if not kind and name.lower().removeprefix("the ") in places_mod.KINDS:
            kind = name.lower().removeprefix("the ")
        # A building hangs off the street, not off the room the party is standing in.
        # Measured live 2026-09-26: "I head for the stables" from inside a shrine made
        # "the stables … off the shrine". A settlement kind (`places.KINDS` — the smithy,
        # the stables, the tavern) founded with no parent named goes off the nearest place
        # up the chain that is under the sky; a room (a cellar, a back room) still goes
        # off the room.
        if kind in places_mod.KINDS and not str(intent.params.get("parent") or "").strip():
            seen = set()
            while places_mod.is_indoors(parent.id) and parent.id not in seen:
                seen.add(parent.id)
                up = places_mod.find(known, parent.parent) if parent.parent else None
                if up is None:
                    # A building whose parent is the settlement itself (the guildhall):
                    # the street it opens onto — its first exit under the sky.
                    up = next((p for p in (places_mod.find(known, x) for x in parent.exits)
                               if p is not None and not places_mod.is_indoors(p.id)), None)
                if up is None:
                    break
                parent = up
        if kind:
            location = self.world.get(self.scene.location_id) if self.world else None
            why = places_mod.fits_here(kind, location, parent)
            if why:
                # A road's kind off a town room: the fix is a place to go (Lane B, the
                # register's `{"kind": "go"}` fix), so the plan can walk out first.
                outskirts = next((p for p in known if p.name == "the outskirts"
                                  and places_mod.is_ring(p.id)), None)
                go = (kind in places_mod.OUTSIDE_KINDS and outskirts is not None
                      and places_mod.setting_of(parent.id) != "outside")
                return self._refuse(intent, why, fix={"kind": "go", "place": outskirts.name}
                                    if go else None)
        # A road's kind stands on its parent's ground and is shaped as open ground; it is
        # not a settlement kind, so it carries no `kind` to shape it as a room.
        road_kind = kind in places_mod.OUTSIDE_KINDS and \
            places_mod.setting_of(parent.id) == "outside"
        place = self.found_place(name, parent,
                                 about=str(intent.params.get("about") or "")
                                 or (places_mod.OUTSIDE_KINDS[kind] if road_kind else ""),
                                 owner=owner, origin="found",
                                 kind="" if road_kind else kind)
        pc = self.scene.pc()
        held = f", held by {owner.name}" if owner is not None else ""
        what = f" It is a {kind}." if kind else ""
        return Outcome(
            intent_id=intent.id, op="found",
            effects=[{"kind": "place", "id": place.id, "name": name,
                      "parent": parent.id, "owner": place.owner, "is": kind,
                      "setting": places_mod.setting_of(place.id)}],
            tell=f"{name} is a place now, off {parent.name}{held}.{what} "
                 f"{pc.name if pc else 'The party'} can go there from {parent.name}.",
            because=intent.because)

    def found_place(self, name: str, parent, about: str = "", owner=None,
                    origin: str = "found", kind: str = ""):
        """Mint a place off `parent` and remember it: the one door a place is made by.

        Pulled out of `_op_found` when the page was given leave to make places too, so
        both doors minted the same thing — the record in `scene.founded`, the holder's
        effect, the place's card. The page's door is gone (ruled 2026-09-27); the plan's
        `found` and `venture` remain.
        """
        from . import cards as cards_mod
        from . import places as places_mod
        from .activeeffect import ActiveEffect

        place = places_mod.mint(parent, name, str(about or "")[:120],
                                owner=owner.ref if owner is not None else "",
                                origin=origin, kind=kind)
        self.scene.founded.append(place.as_dict())
        slug = place.id.rsplit("/", 1)[-1]
        if owner is not None:
            owner.apply_effect(ActiveEffect(
                name=f"holds {name}", kind="situation", key=f"holds:{place.id}",
                source=f"place:{place.id}", origin=origin,
                duration="until-dismissed", tags=(f"holds.place.{slug}",)))
        made = ("Made by the page" if origin == "narrated"
                else f"Founded from {parent.name}")
        cards_mod.open_card(self.scene, cards_mod.Card(
            id=f"place-{slug}", title=f"{name}, off {parent.name}",
            facts=[made + (f", held by {owner.name}" if owner is not None else "") + "."
                   + (f" {str(about).strip()}" if about and origin == "narrated" else "")],
            tags=("situation.place", cards_mod.TAG_PLAY),
            people=[owner.ref] if owner is not None else [], place=place.id,
            clock_max=6, origin=origin), turn=0)
        return place

    def vessel(self, vessel_id: str):
        """One ship the campaign holds, as a live record. None if it holds no such ship."""
        from . import ships as ships_mod

        for raw in self.scene.vessels:
            if str(raw.get("id")) == str(vessel_id):
                return ships_mod.Vessel.from_dict(raw)
        return None

    def _keep_vessel(self, vessel) -> None:
        """Write a vessel back. The one door: a hull's hit points are stored state, and
        two writers of stored state is how a save and a scene start disagreeing."""
        rows = [dict(v) for v in self.scene.vessels if str(v.get("id")) != vessel.id]
        rows.append(vessel.as_dict())
        self.scene.vessels = rows

    def _op_sea(self, intent: Intent, partial: dict) -> Outcome:
        """Two ships, and the distance between them.

        The ruling this implements (2026-09-16): **ships close and then people board, and
        the fight is on the deck.** So this op is five verbs and a band, and every one of
        them is a decision rather than a die roll dressed up:

            close       a sail on the horizon becomes bowshot becomes oars touching
            sheer off   the other way, and at the far end you are away
            ram         the book's own: Profession (sailor) against their AC, and it
                        costs you the minimum of your own ram dice
            grapple     the grapnels go in and nobody leaves until they are cut
            board       across to their deck, where the engine takes over

        The fight that matters is not here. It is on a deck, with a floor plan, a mast to
        put between you and them and a rail with the sea past it — which is ground this
        app has always been good at and Pathfinder's own fast-play rules stop short of.
        """
        from . import places as places_mod
        from . import ships as ships_mod

        from .sheet import IllegalSheet

        do = str(intent.params.get("do") or "").strip().lower()
        sea = dict(self.scene.sea or {})
        if not sea:
            return self._refuse(intent, "There is no other ship in sight.")
        ours, theirs = self.vessel(sea.get("ours", "")), self.vessel(sea.get("theirs", ""))
        if ours is None or theirs is None:
            return self._refuse(intent, "There is no other ship in sight.")
        band = str(sea.get("range") or "distant")
        who = intent.actor or (self.scene.pc().ref if self.scene.pc() else None)
        actor = self.scene.actors.get(who) if who else None

        if do in ("close", "sheer off", "sheer-off", "sheer"):
            if do != "close" and sea.get("grappled"):
                return self._refuse(
                    intent, f"The grapnels are in. {ours.name} is not going anywhere "
                            f"until they are cut.")
            now = ships_mod.closer(band) if do == "close" else ships_mod.further(band)
            sea["range"] = now
            if do != "close" and now == "distant":
                # Away. The engagement is over, which is a real outcome and the one a
                # merchantman wants: the book's ships are faster than they are tough.
                self.scene.sea = {}
                return Outcome(
                    intent_id=intent.id, op="sea",
                    effects=[{"kind": "sea", "range": "away"}],
                    tell=f"{_sentence(ours.name)} comes about and runs. {theirs.name} "
                         f"falls astern, and then there is only the sea.",
                    because=intent.because)
            self.scene.sea = sea
            said = {"closing": "is within bowshot now",
                    "alongside": "is alongside, close enough to throw to",
                    "distant": "is hull down again"}[now]
            return Outcome(
                intent_id=intent.id, op="sea",
                effects=[{"kind": "sea", "range": now}],
                tell=f"{_sentence(theirs.name)} {said}.", because=intent.because)

        if do == "ram":
            if band != "closing":
                return self._refuse(
                    intent, "A ram wants way on and a run at them: from bowshot, closing. "
                            "Alongside is too late and hull down is too far.")
            if actor is None:
                return self._refuse(intent, "Nobody is at the helm.")
            # The book: the captain makes a Profession (sailor) check against the target's
            # AC. Profession is trained only, which is a rule with teeth here — a party
            # with no sailor in it cannot ram anybody, and the refusal says so rather than
            # quietly rolling untrained.
            try:
                mods = actor.skill_modifiers("profession")
            except IllegalSheet:
                # Profession is trained-only, and `skill_modifiers` says so by raising.
                # That rule has teeth here: a party with nobody who has sailed cannot ram
                # anybody, and the refusal names what is missing rather than quietly
                # rolling an untrained check the book does not allow.
                return self._refuse(
                    intent, f"{actor.name} is no sailor. Ramming is a Profession (sailor) "
                            f"check at the helm, and it wants somebody who has done it "
                            f"before — find whoever has.")
            roll = self._roll_or_suspend(
                intent, actor, mods, label=f"Ramming {theirs.name} (AC {theirs.ac})",
                dc=theirs.ac, partial=partial)
            sea["range"] = "alongside"
            self.scene.sea = sea
            if roll.total < theirs.ac:
                self._keep_vessel(ours)
                return Outcome(
                    intent_id=intent.id, op="sea", rolls=[roll],
                    effects=[{"kind": "sea", "range": "alongside", "hit": False}],
                    tell=f"{_sentence(theirs.name)} turns inside it. {ours.name} slides "
                         f"past her beam, close enough to touch.",
                    because=intent.because)
            hit = self.dice.roll(ships_mod.ram_damage(ours.kind),
                                 label=f"{ours.name} rams", visibility="hidden")
            said = ships_mod.take_damage(theirs, hit.total)
            back = ships_mod.take_damage(ours, ships_mod.ram_self_damage(ours.kind))
            self._keep_vessel(theirs)
            self._keep_vessel(ours)
            return Outcome(
                intent_id=intent.id, op="sea", rolls=[roll, hit],
                effects=[{"kind": "sea", "range": "alongside", "hit": True,
                          "target": theirs.id, "sinking": theirs.sinking}],
                tell=f"{_sentence(ours.name)} goes into her. "
                     f"{_sentence(said)} {_sentence(back)}",
                because=intent.because)

        if do == "grapple":
            if band != "alongside":
                return self._refuse(
                    intent, "Grapnels do not carry that far. Close with her first.")
            sea["grappled"] = True
            self.scene.sea = sea
            return Outcome(
                intent_id=intent.id, op="sea",
                effects=[{"kind": "sea", "range": band, "grappled": True}],
                tell=f"The grapnels go across and bite. {ours.name} and {theirs.name} "
                     f"are one deck now, whether anybody likes it or not.",
                because=intent.because)

        if do == "board":
            if band != "alongside":
                return self._refuse(
                    intent, f"{theirs.name} is too far to step to. Close with her first.")
            if actor is None:
                return self._refuse(intent, "Nobody is here to go across.")
            deck = ships_mod.deck_of(theirs)
            if not deck:
                return self._refuse(intent, f"{theirs.name} has no deck to board.")
            # Everybody who goes across, goes across. `with` is the same word travel uses
            # for the people who come along, and for the same reason: a boarding party is
            # a party.
            going = [actor.ref] + [str(w) for w in (intent.params.get("with") or [])
                                   if str(w) in self.scene.actors]
            for ref in going:
                self.scene.move(ref, deck)
            self.scene.settle_relations()
            names = [self.scene.people[r].name for r in going if r in self.scene.people]
            said = ", ".join(names)
            verb = "goes" if len(names) == 1 else "go"
            # And somebody to meet them. Arriving on an empty deck is the anticlimax the
            # whole ruling exists to avoid — "the fight is on the deck" is not a design
            # if the deck is empty — so the watch at the rail is put on the board from
            # the NPC codex, by role words, at the party's own level. Not the whole crew:
            # two hundred rowers is not an encounter, it is a reason the fight has to be
            # won before the rest of them come up.
            met = self._defenders(theirs, deck)
            return Outcome(
                intent_id=intent.id, op="sea",
                effects=[{"kind": "sea", "boarded": theirs.id, "place": deck,
                          "who": going, "met": [a.ref for a in met]}],
                tell=f"{said} {verb} over the rail onto {theirs.name}'s deck."
                     + (f" {_and_list([a.name for a in met])} "
                        f"{'is' if len(met) == 1 else 'are'} waiting at the rail."
                        if met else " Nobody is on it."),
                because=intent.because)

        return self._refuse(
            intent, f"{do or 'that'} is not something to do to a ship. There is close, "
                    f"sheer off, ram, grapple and board.")

    def _defenders(self, vessel, deck: str) -> list:
        """Whoever meets a boarding party at the rail.

        From the NPC codex by role words, at the party's own level — the same door a
        scheme's cast and a shop's keeper come through, so a ship's crew is people rather
        than a number on a vessel record.

        A handful, and never the crew list: a galley carries two hundred rowers and two
        hundred creatures is not an encounter, it is a spreadsheet. What the count says
        instead is how many are *quick enough to be there* — a keelboat's one or two, a
        warship's four — and the rest of them are the reason a boarding action has to be
        won before they come up from below.
        """
        from . import npcs
        from .bestiary import instantiate

        if not vessel.crew:
            return []
        pc = self.scene.pc()
        level = int(getattr(pc, "level", 1) or 1)
        how_many = max(1, min(4, 1 + vessel.crew // 25))
        template = str((npcs.choose(["sailor", "pirate"], level) or {}).get("id")
                       or "thug")
        # Named apart, because the brief lists people by name beside their ref and three
        # actors all called "a hand" is a narrator writing about one person three times.
        called = ("a hand", "a second hand", "a third hand", "a fourth hand")
        out = []
        for i in range(how_many):
            try:
                who = instantiate(template, scene=self.scene,
                                  name=called[min(i, len(called) - 1)])
            except Exception:
                break
            self.scene.add(who)
            self.scene.move(who.ref, deck)
            out.append(who)
        return out

    # --- in conversation -----------------------------------------------------------------
    #
    # Ruled 2026-09-24: a conversation is a state you are in only while directly speaking
    # to somebody or being spoken to, and it ends only when you take your leave, walk
    # away on purpose, or the other party leaves it — never by silence. Everweave's
    # Dialogue Mode is the cautionary example: exits were implicit, scenes ended too
    # early or not at all, and NPCs called for skill checks on their own; the studio ended
    # up shipping a mode that bypasses the whole thing. So the state here is engine-held
    # (`states.TALKING` on the person, through the one applicator), the exit is one op
    # and one button, and nobody in it ever asks the player for a roll.

    def talking_to(self) -> list:
        """Who the player is in conversation with: here, conscious, holding the tag."""
        return [a for r, a in self.scene.actors.items()
                if not a.is_pc and self.scene.conscious(r) and a.has_state(states.TALKING)]

    def join_talk(self, who, how: str = "") -> str:
        """Bring somebody into the conversation; the tell, or "" if they were in it."""
        if who is None or who.is_pc or who.has_state(states.TALKING):
            return ""
        # Spoken with: the record's `last_met`, which the finder's `met` ring and the
        # coming "since last we met" catch-up read (rules/population.py, `met`).
        from . import population as _population

        _population.met(self.scene, _population.of_ref(self.scene, who.ref))
        who.apply_effect(ActiveEffect(
            name="in conversation", kind="bond", key="talk", source="talk",
            origin=str(how or "talk"), duration="until-dismissed",
            tags=(states.TALKING,)))
        return (f"{who.name} is talking to you." if "they" in str(how)
                else f"You are in conversation with {who.name}.")

    def end_talk(self, why: str = "", who=None) -> str:
        """End the conversation, for one person or everybody; the tell, or "" if there
        was none to end."""
        # Everybody holding the tag, wherever they now stand — not the room. Walking
        # away calls this after the party has moved, when the person left behind is
        # no longer in `scene.actors`; read the room and nobody would be found to
        # leave mid-sentence, and `_settle_talk` would say "no longer here" instead.
        gone = ([who] if who is not None else
                [a for a in self.scene.people.values() if not a.is_pc])
        gone = [a for a in gone if a is not None and a.has_state(states.TALKING)]
        for a in gone:
            a.remove_effects(source="talk")
        if not gone:
            return ""
        names = ", ".join(a.name for a in gone)
        if why == "walked away":
            return f"You leave {names} mid-sentence."
        if why == "a fight starts":
            return f"The talk with {names} is over: it has come to blows."
        return f"The conversation with {names} is over."

    def _settle_talk(self) -> list:
        """Whoever cannot be talked to any more leaves the conversation, said.

        Not here, down, dead, or hostile: none of those is somebody the player has to
        take their leave of. Runs at the end of every batch, so a person who walked
        out during an NPC turn is gone from the panel before the next beat."""
        out = []
        for ref, a in list(self.scene.people.items()):
            if a.is_pc or not a.has_state(states.TALKING):
                continue
            here = ref in self.scene.actors and self.scene.conscious(ref)
            from . import attitude as attitude_mod

            hostile = attitude_mod.of(a) == attitude_mod.HOSTILE
            if here and not hostile:
                continue
            a.remove_effects(source="talk")
            why = ("has turned hostile" if hostile else
                   "is no longer here" if ref not in self.scene.actors else "is down")
            out.append(Outcome(intent_id="", op="talk",
                               effects=[{"kind": "talk", "ref": ref, "left": True}],
                               tell=f"{a.name} {why}; the conversation with them is over.",
                               because=""))
        return out

    def _op_leave_talk(self, intent: Intent, partial: dict) -> Outcome:
        """The player ends a conversation, or refuses one.

        `do: "ignore"` is the refusal: somebody spoke to you and you do not answer.
        Either way the exit is the player's own act and costs nothing — no roll, no
        model call from the button — which is the whole of the lesson above."""
        do = str(intent.params.get("do") or "leave").strip().lower()
        want = str(intent.params.get("who") or "").strip()
        who = None
        if want:
            who = self.scene.actors.get(want)
            if who is None:
                match = [a for r, a in self.scene.actors.items()
                         if not a.is_pc and str(a.name).lower() == want.lower()]
                who = match[0] if len(match) == 1 else None
            if who is None or not who.has_state(states.TALKING):
                return self._refuse(intent, f"You are not in conversation with "
                                            f"{want}.")
        talking = [who] if who is not None else self.talking_to()
        if not talking:
            return self._refuse(intent, "You are not in conversation with anybody.")
        names = ", ".join(a.name for a in talking)
        for a in talking:
            a.remove_effects(source="talk")
        tell = (f"You do not answer {names}, and they can see it." if do == "ignore"
                else f"You take your leave of {names}.")
        return Outcome(
            intent_id=intent.id, op="leave_talk",
            effects=[{"kind": "talk", "ref": a.ref, "left": True} for a in talking],
            tell=tell, because=intent.because)

    def _op_company(self, intent: Intent, partial: dict) -> Outcome:
        """Somebody comes along, or stops coming.

        Asked for 2026-09-22: *"if you are taveling together they should follow and
        comment on the world around you."* They did not follow. `_op_travel` sheds every
        non-PC not named in `with`, for the good reason its docstring gives — a
        gatekeeper wounded in the city once followed the party to the forest and took an
        NPC turn for the rest of the session — and `with` is the only way back in. That
        shape asks the model to remember who the party is on every single move, which is
        the one thing a language model reliably does not do: measured live the same day,
        on a turn where the player crossed a village and the tell read "Left behind:
        Drenn Ironvale".

        So it is a state on the person instead, which is the first law: one vocabulary,
        asked by prefix. `bond.travels-with-you` is granted here through the one
        applicator, read by both movement doors, and dropped by `leave` or by the effect
        being removed like any other.

        **Who may come.** The attitude track decides, in its own words rather than a new
        rule: 1e's `friendly` is somebody who "will chat, advise, offer limited help" and
        `helpful` will "take risks to help". Walking somewhere with you is the first of
        those. Anyone below it is refused with the fix named — talk them round, which is
        a Diplomacy `check` the engine already resolves and already tracks the daily
        limit on. Inform's Van Helsing (Recipe Book 7.13) is the same rule from the other
        end: the follower is a property of the character, and the movement rule reads it.
        """
        do = str(intent.params.get("do") or "join").strip().lower()
        if do not in ("join", "leave"):
            # Printed, not raised: a resolution-time raise is a 502 with the player's
            # sentence deleted, and the stage 7 ratchet says so. The fix is named, so a
            # rewrite can land it.
            return self._refuse(
                intent, f"{do!r} is not a thing company does. It is 'join' or 'leave'.")
        want = str(intent.params.get("who") or "").strip()
        who = self.scene.actors.get(want)
        if who is None:
            matches = [r for r, a in self.scene.actors.items()
                       if not a.is_pc and str(a.name).lower() == want.lower()]
            if len(matches) > 1:
                raise IntentError(
                    f"company: {want!r} names {len(matches)} people here; say which by "
                    f"ref: {', '.join(matches)}.", "refs")
            who = self.scene.actors.get(matches[0]) if matches else None
        if who is None:
            here = [f"{r} ({a.name})" for r, a in self.scene.actors.items() if not a.is_pc]
            return self._refuse(
                intent, f"There is no {want or 'nobody'} here to come along."
                        + (f" Here: {', '.join(here)}." if here else ""))
        if who.is_pc:
            return self._refuse(intent, "The player does not follow themselves.")

        source = f"company:{who.ref}"
        if do == "leave":
            gone = who.remove_effects(source=source)
            return Outcome(
                intent_id=intent.id, op="company",
                effects=[{"ref": who.ref, "kind": "company", "travels": False}],
                tell=(f"{who.name} does not go on with you."
                      if gone else f"{who.name} was not travelling with you."),
                because=intent.because)

        if who.has_state(states.TRAVELS_WITH_YOU):
            return Outcome(
                intent_id=intent.id, op="company", effects=[],
                tell=f"{who.name} is already with you.", because=intent.because)
        if who.is_down:
            return self._refuse(
                intent, f"{who.name} is not going anywhere: they are down.")
        from . import attitude as attitude_mod

        mood = attitude_mod.of(who)
        if attitude_mod.step_of(mood) < attitude_mod.step_of(attitude_mod.COMES_ALONG):
            return self._refuse(
                intent, f"{who.name} is {mood} towards you and does not walk out of "
                        f"here at your word. Talk them round first — that is a "
                        f"Diplomacy check against them.")
        who.apply_effect(ActiveEffect(
            name="travels with you", kind="bond", key=f"{source}:travels",
            source=source, origin=source, duration="until-dismissed",
            tags=(states.TRAVELS_WITH_YOU,)))
        note = str(intent.params.get("note") or "").strip()
        return Outcome(
            intent_id=intent.id, op="company",
            effects=[{"ref": who.ref, "kind": "company", "travels": True}],
            tell=f"{who.name} comes with you from here." + (f" {note}" if note else ""),
            because=intent.because)

    def _op_venture(self, intent: Intent, partial: dict) -> Outcome:
        """Ground gone into: the sewers under the town, a cave in the hills outside it.
        Generated on entry from a seed off the parent's id (the roguelike answer), so the
        same stairs lead to the same cellar next time; the way there costs the hours the
        kind says, through the same body toll foraging pays; and something may live
        there — from the bestiary, by the ground, never invented. The party is moved in.
        """
        from . import gathering
        from . import places as places_mod

        kind = str(intent.params.get("kind") or "").strip().lower()
        if kind not in places_mod.VENTURES:
            return self._refuse(
                intent, f"There is no such ground as {kind or 'that'} to go into. The "
                        f"kinds are: {', '.join(sorted(places_mod.VENTURES))}.")
        who = intent.actor or (self.scene.pc().ref if self.scene.pc() else None)
        actor = self.scene.actors.get(who) if who else None
        if actor is None:
            return self._refuse(intent, "Nobody is here to go in.")
        if self.scene.in_encounter:
            return self._refuse(intent, "Not in the middle of a fight; end it or get clear first.")
        parent, known = self._parent_place(str(intent.params.get("parent") or ""))
        if parent is None:
            return self._refuse(
                intent, f"There is no {intent.params.get('parent')} here to go in from. "
                        f"From here you can reach {', '.join(p.name for p in known)}.")
        # You go in from where you are standing. `_parent_place` resolves a NAME against
        # every place in the settlement, and this op then moves the party to whatever it
        # found — so a venture was a way to cross the whole town and go underground in
        # one step, walking nothing. Caught live 2026-09-22: "I walk out to the way in,
        # at the edge of town" came back as a venture into sewers minted off the way in,
        # and the party went from the green to under the gate without passing through
        # either. Movement is walked (item 48); this was the one door left that was not.
        here_now = self.here()
        if parent.id != here_now.id:
            return self._refuse(
                intent, f"You are at {here_now.name}, not {parent.name}: the way down is "
                        f"there, not here. Travel to {parent.name} first — that is this "
                        f"turn's journey — and go in from it.")
        made = places_mod.venture_set(parent, kind)
        head = made[0]
        # The same place the second time: the id is seeded off the parent, so a return
        # finds the venture already minted and simply goes there.
        existing = places_mod.find(known, head.id)
        if existing is None:
            if len(places_mod.children_of(self.scene.founded, parent.id)) >= places_mod.MOST_CHILDREN:
                return self._refuse(
                    intent, f"{parent.name} already has as many places hanging off it "
                            f"as one place can hold.")
            for pl in made:
                self.scene.founded.append(pl.as_dict())
            fresh = True
        else:
            head = existing
            fresh = False
        spec = places_mod.VENTURES[kind]
        hours = int(spec["hours"])
        toll_note = ""
        if hours:
            toll = survival.pass_hours(actor, hours, self.dice, biome=head.terrain)
            self.scene.advance(max(1, toll.hours) * survival.MINUTES_PER_HOUR,
                               charge_body=False)
            if toll.checks:
                toll_note = f" The way cost them: {survival_note(toll)}"
        # In through the one mover: the party goes, the escorts named come, the rest
        # stay — exactly what `travel` does, by way of it.
        #
        # And the way in is checked like any other hours on the move
        # (`rules/ontheway.py`), by that walk and not here. The hours the kind charges
        # are handed to the one hop that reaches the new ground (`_hours_underway`), so
        # the check is made ONCE, against the ground being entered, and whatever it
        # meets arrives after the party has — in the cave, not at the top of the
        # stairs. A venture charged the hours and rolled nothing for them until
        # 2026-09-22; then it rolled its own check here, at the parent, brought the
        # creature in there and opened the fight, and the travel below ended that fight
        # and shed the creature in the same tell (2026-09-23).
        travel = Intent(op="travel", actor=actor.ref, because=intent.because,
                        params={"place": head.id, "with": list(intent.params.get("with") or [])},
                        visibility="hidden", id=intent.id, origin=intent.origin,
                        origin_name=intent.origin_name)
        self._hours_underway[head.id] = hours
        try:
            moved = self._op_travel(travel, {})
        finally:
            self._hours_underway.pop(head.id, None)
        effects = [{"kind": "place", "id": head.id, "name": head.name, "parent": parent.id,
                    "fresh": fresh, "spots": [m.name for m in made[1:]]}] + list(moved.effects)
        tell = (f"{head.name}, {'found for the first time' if fresh else 'as before'}, off "
                f"{parent.name}" + (f" — {hours} hour{'s' if hours != 1 else ''} away" if hours else "")
                + ". " + moved.tell + toll_note)
        # Something may live here. Half the time, by the ground, from the bestiary.
        pc = self.scene.pc()
        level = getattr(pc, "level", 1) if pc is not None else 1
        if self.dice.roll("1d2", label="is it inhabited", visibility="hidden").total == 2:
            row = gathering.creature_for(head.terrain, max(1, int(level)), self.dice)
            if row is not None:
                born = self._bring_in(row["id"], count=1, name=row["name"])
                ref = born[0]["ref"]
                self.scene.zones[ref] = "far"
                self.scene.positions.pop(ref, None)
                aggressive = row.get("creature_type") in gathering.AGGRESSIVE
                effects.append({"kind": "gathering", "encounter": "creature",
                                "creature": row["name"], "aggressive": aggressive})
                tell += (f" Something lives here: {gathering._an(row['name'])}"
                         + (", and it has seen you." if aggressive else ", further in."))
                if aggressive and pc is not None and actor.ref == pc.ref:
                    self._ensure_encounter(pc.ref, target=ref)
        return Outcome(intent_id=intent.id, op="venture", effects=effects, tell=tell,
                       because=intent.because)

    def _op_condition(self, intent: Intent, partial: dict) -> Outcome:
        ref = intent.params.get("to") or intent.actor or (intent.targets() or [None])[0]
        target = self.scene.actors[ref]
        key = str(intent.params["condition"]).strip().lower()

        # Lifting one, and it is checked BEFORE the immunity gate below. Immunity says
        # what may not be inflicted; gating a removal on it means a creature immune to
        # fear can never be cured of being shaken — the same inversion that made 759
        # undead unkillable when the gate was put on the applicator.
        #
        # The op could only ever add. Measured: `_op_condition` mints `rounds=None`
        # whenever the GM omits a duration, so an unbounded paralysis was a campaign the
        # character never played again — nothing ticked it, no turn could be taken, and
        # there was no route out of it in the whole app.
        if intent.params.get("ends"):
            gone = target.remove_effects(kind="condition",
                                         match=lambda e: e.key == key)
            named = CONDITIONS.get(key, {}).get("name", key).lower()
            return Outcome(
                intent_id=intent.id, op="condition",
                effects=[{"ref": target.ref, "kind": "condition", "condition": key,
                          "ends": True} for _ in gone],
                tell=(f"{target.name} is no longer {named}." if gone
                      else f"{target.name} was not {named}."),
                because=intent.because)

        duration = intent.params.get("duration")
        rounds = None
        if isinstance(duration, dict):
            rounds = _to_rounds(duration.get("amount", 0), duration.get("unit", "round"))
        elif isinstance(duration, int):
            rounds = duration
        # Immunity is consulted HERE, and never inside `add_condition`. That applicator
        # is also how `apply_hp_state` writes dead, dying and unconscious and how
        # `ability_zero_effects` writes helpless — gate it and the 759 shipped creatures
        # with undead traits become unkillable, immune to the very condition that
        # records their death. The op is where an outside effect asks to impose
        # something; the applicator is the engine's own hand.
        blocked = states.immunity_blocks(
            target.immunities, key,
            intent.params.get("descriptors") or ())
        if blocked:
            # A refusal, not a raise: the schema may require the op the GM declared.
            return Outcome(
                intent_id=intent.id, op="condition", effects=[],
                tell=f"{target.name} is immune to {blocked} and is not "
                     f"{CONDITIONS.get(key, {}).get('name', key).lower()}.",
                because=intent.because)
        # One step on the attitude track at a time. Nobody is hostile and helpful at
        # once, and without this a charm laid over an old grudge left both standing
        # and `attitude_of` answered with whichever the reversed walk hit first.
        # Here rather than in `add_condition`, for the reason argued directly above:
        # the applicator is the engine's own hand and this is a rule about the op.
        if key in states.ATTITUDES:
            cond = self._set_attitude(target, key, rounds, intent.because)
        else:
            cond = target.add_condition(key, rounds, source=intent.because)
        return Outcome(
            intent_id=intent.id, op="condition",
            effects=[{"ref": target.ref, "kind": "condition", "condition": key,
                      "rounds_left": cond.rounds_left}],
            tell=f"{target.name} is {cond.name.lower()}"
                 + (f" for {cond.rounds_left} rounds." if cond.rounds_left else "."),
            because=intent.because,
        )

    def settle_attitude(self, target, key: str, rounds: int | None = None,
                        source: str = ""):
        """The public name for the one attitude applicator, for callers outside this
        class — `rules/backgrounds.acquaint` is the first. A second copy of
        clear-then-add is the exact drift `_set_attitude`'s own docstring was written to
        prevent, and a module reaching for a private method is how that copy gets made.
        """
        return self._set_attitude(target, key, rounds, source or "the engine")

    def _set_attitude(self, target, key: str, rounds: int | None, source: str):
        """Move a creature to one step of the track. The one applicator for an attitude.

        One step at a time: nobody is hostile and helpful at once, and without the clear
        a charm laid over an old grudge left both standing and `attitude_of` answered
        with whichever the reversed walk hit first. Here rather than in `add_condition`,
        because that is the engine's own hand — it writes dead, dying and helpless — and
        this is a rule about changing somebody's mind, not about recording a fact.

        Two callers, which is exactly why it is a method: `condition` (a spell, a power)
        and `check` (talking to them). The second arrived 2026-09-16 and would otherwise
        have been a second copy of the clear-then-add rule — CLAUDE.md's "when you fix a
        rule, grep for every copy of it", applied before there was a copy to grep for.
        """
        target.clear_states("attitude")
        if rounds is None:
            # A shift with no end is a fact about the relationship, not a mood for
            # the hour: the standing regard follows it to the floor of that step, so
            # the step does not evaporate the moment something else clears the tag.
            # A background's "knows you" lands friendly this way; a guard who has
            # read the warrant lands hostile this way.
            from . import attitude as attitude_mod

            if attitude_mod.band_of(attitude_mod.regard_of(target)) != key:
                attitude_mod.set_regard(target, attitude_mod.floor_of(key), source)
        return target.add_condition(key, rounds, source=source)

    # What a natural weapon does past its damage. The rider tags a race grants —
    # `natural.trip`, `natural.grab.bite`, `natural.poison.sting` — and the intent each
    # one becomes. The weapon may be named in the tag's last segment or left off, in
    # which case the rider belongs to every natural attack the body has.
    #
    # Each is a save the defender may make, not a thing that simply happens. 1e resolves
    # grab, trip, pull and push as combat manoeuvres, and the honest reading is that this
    # is not that: a manoeuvre is CMB against CMD and suspends for the player's own d20,
    # mid-way through an attack that has already suspended twice. What is here instead is
    # the same *fork* — a roll the defender makes, at a DC off the attacker — and it is
    # marked as a simplification in docs/races.md rather than presented as the book's
    # rule. The alternative was leaving five evolutions inert, which is what they were.
    _NATURAL_RIDERS = {
        "trip":   ("ref", "prone", "is knocked off their feet"),
        "grab":   ("ref", "grappled", "is caught and held"),
        "pull":   ("ref", "", "is dragged in a step"),
        "push":   ("ref", "", "is driven back a step"),
    }

    def _rider_dc(self, actor: Actor) -> int:
        """10 + half the attacker's hit dice + Strength modifier — the shape 1e uses for
        a monster's special-attack DCs, so a rider scales with the body that has it."""
        level = max(1, int(getattr(actor, "level", 1) or 1))
        return 10 + level // 2 + actor.ability_mod("str")

    def _natural_riders(self, actor: Actor, defender: Actor,
                        weapon_key: str) -> list[dict]:
        """Fire the race's on-hit riders for the weapon that just landed.

        Built as intents and run through `validate`/`run` like everything else, for the
        reason `_deliver_coating` above does it: the one applicator, with provenance, so
        a grapple that arrived this way is removable exactly like any other and says
        where it came from. Nothing here touches a number directly.
        """
        if defender.hp <= 0:
            # A rider on a corpse. The damage already landed; dragging it a step is
            # noise, and `grappled` on the dead was the shape that once made 759
            # undead unkillable.
            return []
        out: list[dict] = []
        for rider, (_who, condition, words) in self._NATURAL_RIDERS.items():
            if not (actor.has_state(f"natural.{rider}.{weapon_key}")
                    or actor.has_state(f"natural.{rider}")):
                continue
            dc = self._rider_dc(actor)
            if condition:
                intents = [{
                    "op": "save", "actor": defender.ref, "visibility": "hidden",
                    "because": f"{actor.name}'s {weapon_key} {words}",
                    "params": {"save": "ref", "dc": dc,
                               "on_failure": {"condition": condition}},
                }]
                res = self.run(self.validate(intents, origin=f"race:natural.{rider}",
                                             origin_name=rider))
                for o in res.outcomes:
                    out.extend({"effect": e, "tell": o.tell} for e in (o.effects or [])
                               if e.get("kind") == "condition")
                    if not o.effects:
                        out.append({"effect": {"ref": defender.ref,
                                               "kind": "rider_resisted", "rider": rider},
                                    "tell": o.tell})
            else:
                # Pull and push move a body rather than condition it. The grid owns
                # where anybody is, so this asks it and says so when there is no grid
                # to ask — a scene without one is not a bug, it is the zone game.
                moved = self._shove(actor, defender, toward=(rider == "pull"))
                out.append({"effect": {"ref": defender.ref, "kind": "rider",
                                       "rider": rider, "moved": moved},
                            "tell": f"{defender.name} {words}."
                                    if moved else
                                    f"{actor.name} tries to {rider} {defender.name} "
                                    f"and cannot move them."})
        return out

    def _shove(self, actor: Actor, defender: Actor, toward: bool) -> bool:
        """One five-foot step of the defender, towards the attacker or away. False when
        there is no grid, no room, or the square is taken.

        One copy of forced movement, not two: this used to step the anchor itself and
        test only other anchors, so a Large body's second square and the level axis
        were both ignored, while the manoeuvres' `_push_line` checks footprints.
        """
        if not self._both_on_the_map(actor, defender):
            return False
        step = self._heading(actor.ref, defender.ref)
        if toward:
            step = (-step[0], -step[1])
        if not self._push_line(defender.ref, step, 1):
            return False
        self.scene.settle_levels()
        self.scene.resync_zones()
        return True

    def _deliver_coating(self, actor: Actor, defender: Actor, weapon_key: str) -> list[dict]:
        """Everything a coated weapon does to the thing it just cut.

        Returns effect/tell pairs rather than resolving into the attack's state directly,
        so the attack op stays readable and a coating that resolves to nothing costs it
        nothing.
        """
        raw = getattr(actor, "coating", None)
        if not raw:
            return []
        coat = consumables.coating_from_dict(raw)
        if coat.uses_left < 1 or (coat.weapon and coat.weapon != weapon_key):
            return []

        # Spent before it resolves, and unconditionally. A dose that killed its target
        # mid-resolution has still left the blade.
        actor.coating = {}

        intents = consumables.coating_intents(coat, defender.ref)
        if not intents:
            return [{"effect": {"ref": defender.ref, "kind": "coating_spent",
                                "item": coat.item},
                     "tell": f"The {coat.item} on the blade does nothing to "
                             f"{defender.name}."}]
        resolution = self.run(self.validate(intents, origin=f"item:{coat.item}",
                                            origin_name=coat.item))
        out = [{"effect": {"ref": defender.ref, "kind": "coating_spent",
                           "item": coat.item, "weapon": weapon_key},
                "tell": f"The {coat.item} goes into the wound."}]
        for o in resolution.outcomes:
            for e in o.effects:
                out.append({"effect": e, "tell": ""})
            if o.tell:
                out.append({"effect": {"ref": defender.ref, "kind": "coating"},
                            "tell": o.tell})
        return [x for x in out if x["effect"] or x["tell"]]

    def _op_use_item(self, intent: Intent, partial: dict) -> Outcome:
        """Drink it, throw it, or put it on a blade.

        A crafted potion used to be a paragraph in a satchel: the player threw a tincture
        at a beast and got narration, because narration was all there was. `Stock.specs`
        made the effects structured and `rules.consumables` turns them into intents, so
        this op does not resolve anything itself — it produces ordinary intents and lets
        them go through the same validation as everything the GM proposes.

        Throwing is a ranged touch attack in 1e. That attack is not emitted here: this op
        commits the dose and hands the effects back, and whether it hits is the `attack`
        op's business. Rolling it here would mean a second, hidden attack resolver.
        """
        actor = self.scene.actors[intent.actor]
        said = str(intent.params["item"]).strip().lower()
        how = str(intent.params.get("how", "drink")).strip().lower()
        target = intent.params.get("to") or intent.actor

        # By id, by name, or by the words the player used — "my healing potion" is
        # the Healing Draught. Two jars that both fit are a question, not a guess.
        item_id, fits = consumables.resolve_stock(actor.stock, said)
        held = actor.stock.get(item_id) if item_id else None
        if held is None or held.count < 1:
            # "I drink my healing potion" with none was the commonest 502 in play, and
            # it deleted the player's own line. The same check runs at validate time
            # now, where the model gets its retry with this list in hand; this is the
            # floor for a list that changed under itself.
            if len(fits) > 1:
                return self._refuse(
                    intent, f"Which does {actor.name} mean by {said}: "
                            f"{', '.join(fits)}? Nothing is opened until they say.")
            return self._refuse(
                intent, f"{actor.name} is not carrying {said}. They have: "
                        f"{', '.join(sorted(actor.stock)) or 'nothing crafted'}.")
        if target not in self.scene.actors:
            away = self._elsewhere(target)
            return self._refuse(intent, away or f"There is no {target} here to use it on.")

        use = consumables.plan(held, how=how, target=target, because=intent.because)
        if not use.ok:
            return self._refuse(intent, f"{use.item} cannot be used that way: "
                                        f"{'; '.join(use.problems)}.")

        # The dose is spent whichever way it was used, and spent before the effects
        # resolve. A poison that kills the drinker mid-resolution has still been drunk.
        held.count -= 1
        if held.count <= 0:
            actor.stock.pop(item_id, None)

        effects = [{"ref": actor.ref, "kind": "used_item", "item": use.item,
                    "how": how, "left": max(0, held.count)}]

        if how == "coat":
            weapon = str(intent.params.get("weapon") or actor.equipped or "").lower()
            if not weapons_mod.has(weapon):
                # The dose is already spent above, on purpose — a jar opened over
                # nothing is still opened — and the refusal says so.
                return self._refuse(
                    intent, f"{actor.name} has no weapon called {weapon or 'nothing'} "
                            f"to coat; the dose is spent on the air.")
            actor.coating = consumables.Coating(
                item=use.item, weapon=weapon,
                specs=[dict(s) for s in (held.specs or [])],
                potency=float(held.potency or 1.0)).as_dict()
            effects.append({"ref": actor.ref, "kind": "coated", "weapon": weapon,
                            "item": use.item})
            return Outcome(
                intent_id=intent.id, op="use_item", effects=effects,
                tell=f"{actor.name} works {use.item} along the {weapon}. It will keep "
                     f"until the next thing it cuts.",
                because=intent.because,
            )

        # Drink and throw both deliver now. The intents go through validation because
        # anything reaching the engine does, including what the engine itself proposed.
        # Stamped here, with the jar still in hand: `held` may already be popped from
        # the satchel (the last dose), so provenance is resolved by the door, not
        # looked up later.
        resolution = (self.run(self.validate(use.intents, origin=f"item:{item_id}",
                                             origin_name=use.item))
                      if use.intents else None)
        if resolution is not None:
            effects.extend(e for o in resolution.outcomes for e in o.effects)

        who = self.scene.actors[target].name
        verb = "drinks" if how == "drink" else "throws"
        at = "" if target == intent.actor else f" at {who}"
        tell = f"{actor.name} {verb} {use.item}{at}."
        if resolution is not None:
            tell += " " + " ".join(o.tell for o in resolution.outcomes if o.tell)
        if use.narrate:
            tell += f" ({'; '.join(use.narrate)})"

        return Outcome(
            intent_id=intent.id, op="use_item",
            rolls=[r for o in (resolution.outcomes if resolution else []) for r in o.rolls],
            effects=effects, tell=tell.strip(), because=intent.because,
        )

    def _op_sell(self, intent: Intent, partial: dict) -> Outcome:
        """Hand something over and be paid for it.

        Measured, and the reason this exists: a player asked a stallholder to price a
        satchel holding a potency-1,335 draught, haggled her from ten gold up to
        twenty-two and shook her hand on it. Every turn of that resolved to
        `narrate_only`. No item moved, no coin moved, and the purse was empty afterwards
        — "it's also obvious the vender in this interaction did not actually see what i
        was trying to give her it was completely narrative", which was exactly true.

        The stall's till is the interesting half. `market.can_pay` caps the payment at
        what this shop has on hand today, and the cap is an offer rather than a refusal:
        a stallholder short of the asking price puts down what they have, and whether
        that is worth taking is the player's decision, not the engine's.
        """
        from . import market as market_mod
        from . import pricing

        actor = self.scene.actors[intent.actor]
        item_id = str(intent.params["item"]).strip().lower()
        count = max(1, int(intent.params.get("count") or 1))

        held = actor.stock.get(item_id)
        if held is None or held.count < 1:
            # Printed, and also checked at validate time so the model can name the
            # thing they do carry — see `_refuse` for why a raise here reached the
            # player as a 502 with their sentence deleted.
            return self._refuse(
                intent, f"{actor.name} is not carrying {item_id}. They have: "
                        f"{', '.join(sorted(actor.stock)) or 'nothing crafted'}.")
        count = min(count, held.count)

        buyer = intent.params.get("to")
        if buyer and buyer not in self.scene.actors:
            return self._refuse(intent, self._elsewhere(buyer) or f"There is no {buyer} here to sell to.")
        from . import keepers as keepers_mod

        shut = keepers_mod.shut_here(self.scene, self.scene.actors[buyer] if buyer else None)
        if shut:
            return self._refuse(intent, shut)
        who = self.scene.actors[buyer].name if buyer else "the stallholder"

        # The same three coordinates the shelf is drawn on, read the same way
        # `craft_views` reads them, so a stall's money and its stock agree about which
        # shop on which day this is.
        place = str(self.scene.location_id or "nowhere")
        stall = str(intent.params.get("stall") or buyer or "market")
        day = market_mod.day_of(self.scene.clock_minutes)

        # The seller's standing with this town's law moves the price (docs/wanted.md):
        # a fence pays a fugitive less for the reason he charges them more.
        asking = round(pricing.what_a_shop_pays(held, seller=actor, town=place) * count, 2)
        # A price the player has already agreed to caps the ask — that is the haggle,
        # and the trade screen is where it gets named. It can only ever lower the price
        # asked: a player cannot talk a stall into paying more than the goods are worth
        # by writing a bigger number into the intent.
        agreed = intent.params.get("accept")
        if agreed is not None:
            try:
                asking = min(asking, max(0.0, float(agreed)))
            except (TypeError, ValueError):
                pass

        paid = market_mod.can_pay(self.scene.market_taken, asking, place, stall, day)
        if paid <= 0:
            return Outcome(
                intent_id=intent.id, op="sell", effects=[],
                tell=f"{who} turns out the till and finds nothing left in it today. "
                     f"Nothing changes hands.",
                because=intent.because,
            )

        # `take_stock` answers how many were *taken*, not how many are left — reading it
        # as "left" reported a sold-out jar as having one still on the shelf.
        sold = actor.take_stock(item_id, count)
        left = actor.stock[item_id].count if item_id in actor.stock else 0
        cp = int(round(paid * 100))
        actor.purse = goods.credit(actor.purse, cp)
        market_mod.mark_spent(self.scene.market_taken, paid, place, stall, day)

        coins = goods.coinage()
        short = paid < asking
        tell = (f"{actor.name} hands over {sold}x {held.name} and takes "
                f"{goods.purse_line(goods.coins_for(cp), coins)}")
        if short:
            # Said out loud, because a silent shortfall reads as a bad price rather than
            # an empty till, and the difference is the whole point of the cap.
            tell += (f" — all {who} can raise today, against "
                     f"{pricing.as_text(asking)} asked")
        tell += f". ({goods.purse_line(actor.purse, coins)} in hand.)"

        return Outcome(
            intent_id=intent.id, op="sell",
            effects=[{"ref": actor.ref, "kind": "sold", "item": held.name,
                      "count": sold, "paid_cp": cp, "left": left}],
            tell=tell, because=intent.because,
        )

    def _op_buy(self, intent: Intent, partial: dict) -> Outcome:
        """Buy something off the stall in front of you.

        Buying existed only on the crafting bench before this, as an excursion that
        spends hours and rolls a check to go and find a supplier. That is the right shape
        for stocking a workshop and the wrong one for standing at a counter, so there was
        no way at all to buy a thing while looking at it.

        The shelf is the same shelf `market` has always drawn — deterministic in
        (place, stall, day), so the amethyst is still there when you walk back in, and
        `mark_sold` means the one legendary is one legendary.
        """
        from . import market as market_mod
        from . import pricing

        actor = self.scene.actors[intent.actor]
        item_id = str(intent.params["item"]).strip().lower()
        count = max(1, int(intent.params.get("count") or 1))

        seller = intent.params.get("from_")
        if seller and seller not in self.scene.actors:
            return self._refuse(intent, self._elsewhere(seller) or f"There is no {seller} here to buy from.")
        # A counter keeps hours (rules/keepers.py): the keeper says when to come back.
        from . import keepers as keepers_mod

        shut = keepers_mod.shut_here(self.scene, self.scene.actors[seller] if seller else None)
        if shut:
            return self._refuse(intent, shut)
        # Whoever keeps this counter, by name, when the plan named no seller: the panel
        # never does, and "pays the stallholder" read wrong with Azhil Vex standing
        # behind it (live, 2026-09-27).
        here_keeper = keepers_mod.keeper_in(self.scene, str(self.scene.at or ""))
        # Never the master of a market, who keeps no counter (I2, `places.RUNNERS`).
        who = (self.scene.actors[seller].name if seller
               else here_keeper.name if here_keeper is not None
               and here_keeper.ref in self.scene.actors
               and keepers_mod.keeps_a_counter(here_keeper) else "the stallholder")

        place = str(self.scene.location_id or "nowhere")
        stall = str(intent.params.get("stall") or seller or "market")
        day = market_mod.day_of(self.scene.clock_minutes)

        # The stall names the counter when it is one of a market's (`market:armorer`, I2):
        # the armorer's shelf, not the whole market's.
        counter = market_mod.on_sale(place, stall, day, self.scene.market_taken,
                                     counter_kind=market_mod.counter_kind_here(self.scene,
                                                                               stall))
        found = next((m for m in counter if str(getattr(m, "id", "")).lower() == item_id),
                     None)
        if found is None:
            # Named the way a person names it ("rope", "a coil of rope") rather than by
            # id: the shelf's own matcher, which guesses nothing (`goods.match_want`).
            found, _ = goods.match_want(item_id, counter)
        if found is None:
            # Named, not blank, and printed: what is on a counter TODAY is a fact only
            # the engine holds — the shelf is drawn from a seeded table and the day is
            # in the key — so neither the player nor the model could have known, and a
            # 502 that deleted the player's sentence was the wrong answer to a question
            # only this line can answer.
            near = ", ".join(sorted(str(getattr(m, "id", "")) for m in counter)[:12])
            return self._refuse(
                intent, f"{who} has no {item_id} on the counter today. On the counter: "
                        f"{near or 'nothing'}.")

        price = round(pricing.worth(found, buyer=actor, town=place) * count, 2)
        cp = int(round(price * 100))
        purse, paid = goods.spend(actor.purse, cp)
        coins = goods.coinage()
        if not paid:
            return Outcome(
                intent_id=intent.id, op="buy", effects=[],
                tell=f"{found.name} is {pricing.as_text(price)} and {actor.name} has "
                     f"{goods.purse_line(actor.purse, coins)}. Nothing changes hands.",
                because=intent.because,
            )

        actor.purse = purse
        # Where the sheet reads it (`goods.deliver`): gear onto the shelf as a
        # crafted-shape entry, in its measure (one purchase of rope is fifty feet); a
        # weapon into the weapon list, armour carried to be worn, and a mount into the
        # scene as a creature that travels with the party (I2, the owner's 2026-09-29
        # ruling: mounts are bought, never hired).
        per = int(getattr(found, "per", 1) or 1)
        arrived, arrived_tell = goods.deliver(self.scene, actor, found, count)
        # A staple is never sold out; a thing drawn onto today's shelf is, once sold.
        if not getattr(found, "staple", False):
            for _ in range(count):
                market_mod.mark_sold(self.scene.market_taken, str(found.id), place, stall,
                                     day)

        return Outcome(
            intent_id=intent.id, op="buy",
            effects=[{"ref": actor.ref, "kind": "bought", "item": found.name,
                      "count": count, "paid_cp": cp}] + arrived,
            tell=f"{actor.name} pays {who} {pricing.as_text(price)} for "
                 + (f"{count * per} {found.unit} of {found.name}"
                    if getattr(found, "unit", "") else f"{count}x {found.name}")
                 + f". ({goods.purse_line(actor.purse, coins)} left.)" + arrived_tell,
            because=intent.because,
        )

    def _op_cast(self, intent: Intent, partial: dict) -> Outcome:
        """Cast a spell: spend the slot, state the numbers, and roll what the spell says.

        The engine owns the slot, the caster level and the save DC, and it owns them
        completely — the GM cannot cast a spell the caster does not have, at a level they
        cannot reach, out of a slot they already spent.

        **What changed, and where the boundary is now.** This used to state the facts and
        stop, because "a parser guessing mechanics out of three thousand English
        paragraphs would produce confident wrong numbers". That reasoning was right and it
        is now narrower rather than gone: 385 of the 3,040 spells carry effects that were
        read mechanically and validated against `effectspec`, and 2,655 still do not. So
        the boundary moved from per-corpus to **per-spell** — a spell carrying effects is
        executed, and a spell carrying none takes exactly the path it always took. An
        empty `spell.effects` is the honest signal that this one's mechanics are prose.

        Three stages, in 1e's own order:

        1. **The dice, once.** A fireball is rolled once and everyone in the area saves
           against that number; rolling per target would give two creatures in one blast
           different damage. The caster rolls it, which means a PC rolls their own — the
           same suspend/resume the player's attacks and their damage already use.
        2. **A saving throw per target**, rolled with that creature's own modifiers
           against the caster's real DC.
        3. **The damage**, full on a failure and halved on a success, through
           `_apply_damage` like every other point of damage in the game — so resistance,
           damage reduction, temporary hit points and interception all apply without a
           line of their own here.

        What it still does not do is spell resistance: `spell.sr` is a real tri-state now
        and no creature carries an SR *number* the engine can check against, so nothing is
        rolled and the printed line is reported as it always was. Half a check would be
        worse than none — see docs/spells.md §5.1.

        **Who is in it, since 2026-09-28** (docs/design-e-magic.md; items 22.1–22.3). An
        area spell used to take its victims from `intent.target` alone, and the Spells tab
        sent none for a cone: Bobby's Burning Hands rolled 1d4 = 1 with `targets: []` and
        the man it was pointed at stood at 4 of 4. Now the area is laid on the map from
        the caster and the aim (`rules/areas.py`, the one place membership is decided),
        every creature in it saves and takes its share, the things in it are listed, and a
        cast that caught nobody rolls nothing and says so (`no_victim`). With no map the
        aim alone decides, as before.

        **Harm opens the fight and moves attitude, when it is seen.** A spell that rolls
        damage or lays a harmful condition (`attitude.harmful_spell`) on somebody not on
        the caster's side is violence, and the first one defers through the battle gate
        exactly as a first swing does (owner, Q31): the encounter forms, nothing is spent
        or rolled, and the player casts it on their own first turn. Each creature it
        harms is told through `attitude.harmed`, the one rule the sword door shares (Q37).
        A caster nobody perceives — the sniping rule, `attitude.perceived` — opens no
        fight and costs no attitude (owner, Q34).
        """
        from . import areas, attitude as attitude_mod

        actor = self.scene.actors[intent.actor]
        spell = spells_mod.get(str(intent.params["spell"]))
        level = casting.spell_level_for(actor, spell)
        dc = casting.save_dc(actor, level)
        cl = casting.caster_level(actor)
        plan = spells_mod.casting_plan(spell, cl)
        dice = plan["dice"]

        # The slot is spent once, on the way in, and never again on a resume. `state`
        # living in `partial` is what distinguishes the two: a cast that suspends for the
        # player's damage roll comes back through here with its state, and re-spending
        # would cost a second slot for one fireball. Everything decided about WHERE the
        # spell went is decided once too, and kept in the state: a resume must not lay the
        # area again after somebody moved, nor roll the Stealth contest twice.
        state = partial.get("cast_state")
        if state is None:
            state = {"stage": "dice", "i": 0, "rolls": [], "effects": [], "tells": []}
            aim = self._cast_aim(intent, actor)
            if aim.kind == "object":
                # Held by the thing's own name ("canopy"), the player's words kept for
                # the tell ("the tree tops").
                found = areas.find_object(self.scene, aim.value)
                if found:
                    aim = areas.Aim("object", str(found["name"]).lower(),
                                    said=f"the {aim.value}")
            area = areas.lay(self.scene, actor.ref, spell, cl, aim)
            if area.shape != "none":
                caught = areas.caught(self.scene, area)
            else:
                # The aim, not the raw `at`: they are the same ref but for `at: "self"`,
                # which `aim_of` reads as the caster and the raw slot read as a person
                # called "self" who was never there.
                caught = intent.targets()
                if not caught and aim.kind == "ref":
                    caught = [aim.value]
                if not caught and aim.kind == "self":
                    caught = [actor.ref]
            objects = areas.objects_caught(self.scene, area, spell)
            harm = attitude_mod.harm_of(spell, cl)
            harms = bool(harm)
            foes = [r for r in caught if r in self.scene.actors
                    and self._against(actor, self.scene.actors[r])]
            # A charm or a magical sleep is harm only to an unfriendly eye (owner's
            # ruling, I3): of the player's victims, only those below friendly hold it
            # against them, so only they can open a fight over it. Another caster's is
            # an attack like any other — the ruling is about how people feel towards
            # the player, the only caster the app keeps feelings about.
            gated = harm == "gated" and actor.is_pc
            if gated:
                foes = [r for r in foes if attitude_mod.resents(self.scene.actors[r])]
            seen = {}
            if harms:
                for r in caught:
                    if r != actor.ref and r in self.scene.actors:
                        seen[r] = attitude_mod.perceived(
                            self, actor, self.scene.actors[r], rolls=state["rolls"])
            state.update({"aim": aim.as_dict(), "aim_param": aim.as_param(),
                          "area": area.as_dict() if area.shape != "none" else None,
                          "caught": list(caught), "objects": objects,
                          "harmful": bool(harms and foes), "harms": bool(harms),
                          "gated": gated,
                          "seen": seen, "fell_short": bool(area.fell_short)})
            noticed = [r for r in foes if seen.get(r, True)]
            if harms and noticed:
                deferred = self._cast_gate(intent, actor, spell, aim, noticed, state)
                if deferred is not None:
                    return deferred

            pool = casting.slot_pool(level)
            # A cantrip or orison is "not expended when cast and may be used again" (AoN,
            # Wizard/Cleric/Druid; "do not consume any slots", Sorcerer/Bard). Measured
            # 2026-09-29: this spent "spell slot 0" per cast, and a level 5 wizard's Light
            # went 4, 3, 2, 1, 0 and was then refused. Nothing is spent, nothing unprepared.
            spent = {"ok": True} if casting.at_will(level) else actor.spend_pool(pool, 1)
            if not spent["ok"]:
                # The mid-list case, measured: six casts in one list PASS validation
                # against two prepared slots, because `_check_cast` reads the count
                # before anything runs. The third used to raise here — after two slots
                # were gone and two fireballs had landed — and the 502 threw all of it
                # away. Printed instead: what was cast stands, and this one does not.
                # Validate is NOT taught to simulate the list; that is a second resolver.
                return self._refuse(
                    intent, f"{actor.name} has no {pool} left, so {spell.name} is not "
                            f"cast. What was cast before it stands.", code="no_slots",
                    for_a_person=f"{actor.name} has no level {level} spell slots left.")
            # The prepared copy is spent with the slot — for every prepared caster, not
            # only the ones who prepare from a book (item 25).
            converted = ""
            if casting.caster_data(actor).get("kind") == "prepared" and level > 0:
                if casting.prepared_count(actor, spell.id) > 0:
                    casting.unprepare(actor, spell.id, 1)
                else:
                    # Spontaneous conversion: the cure is cast and the prepared spell that
                    # paid for it is gone. Said out loud, because a player whose shield of
                    # faith silently vanished would be right to call it a bug.
                    given = casting.sacrifice_for(actor, level)
                    if given:
                        casting.unprepare(actor, given, 1)
                        try:
                            lost = spells_mod.get(given).name
                        except KeyError:
                            lost = given
                        converted = (f"{actor.name} gives up {lost} to cast "
                                     f"{spell.name} instead.")
            if converted:
                state["tells"].append(converted)
        pool = casting.slot_pool(level)

        targets = list(state.get("caught") or [])
        save = (spell.saving_throw or "").strip()
        sr = (spell.spell_resistance or "").strip()

        bits = [f"caster level {cl}"]
        if save and save.lower() not in ("none", "no", "—", "-"):
            bits.append(f"{save}, DC {dc}")
        if sr and sr.lower() not in ("no", "none", "—", "-"):
            bits.append(f"spell resistance {sr}")
        if spell.duration:
            bits.append(spell.duration)

        live = [ref for ref in targets if ref in self.scene.actors]
        # Nothing to roll against: nobody in it. The dice line "1d4 — 1." with no victim
        # was the bare roll the prose then invented a burned face for (item 22.4).
        no_victim = bool(dice) and not live

        # Everything a narrator, a player and a GM correcting a conversion all need. The
        # keys that were here before are untouched but `area`, which is the laid area now
        # when there is one; `effects_converted` is the one a GM most needs, because 385
        # of these numbers were read by a machine and nobody has checked them. The new
        # keys (fix-interfaces §2.7) are written only when they say something.
        cast_effect = {
            "ref": actor.ref, "kind": "cast", "spell": spell.id,
            "name": spell.name, "spell_level": level, "dc": dc,
            "caster_level": cl, "save": save, "spell_resistance": sr,
            "duration": spell.duration, "range": spell.range,
            "area": state.get("area") or (spell.area or spell.effect or spell.targets),
            "targets": targets, "slot": pool,
            "slots_left": casting.slots_left(actor, level),
            "at_will": casting.at_will(level),
            "element": spell.element, "dice": dice,
            "range_feet": spells_mod.range_feet(spell, cl),
            "effects": spell.effects, "effects_converted": spell.effects_converted,
        }
        aim_said = self._aim_words(state)
        if (state.get("aim") or {}).get("kind", "none") != "none":
            cast_effect["aim"] = dict(state["aim"], said=aim_said)
        if state.get("area"):
            cast_effect["caught"] = list(targets)
        if state.get("objects"):
            cast_effect["caught_objects"] = [
                {"kind": o["kind"], "name": o["name"], "burns": bool(o.get("burns"))}
                for o in state["objects"]]
        if no_victim:
            cast_effect["no_victim"] = True
        if state.get("harmful"):
            cast_effect["harmful"] = True
        if state.get("fell_short"):
            cast_effect["fell_short"] = True

        where = self._cast_where(actor, spell, state, targets, no_victim, aim_said)

        if not spell.effects:
            # One of the 2,655. Unchanged, deliberately: the outcome states the facts and
            # whatever the GM then declares arrives as its own validated intent.
            lit, lit_said = self._ignite_caught(actor, spell, state)
            return Outcome(
                intent_id=intent.id, op="cast", effects=[cast_effect] + lit,
                rolls=[_roll_from_dict(r) for r in state["rolls"]],
                tell=" ".join([f"{actor.name} casts {spell.name} ({'; '.join(bits)})."]
                              + where + lit_said),
                because=intent.because,
            )

        if dice and live and state["stage"] == "dice":
            roll = self._roll_or_suspend_stage(
                intent, actor, [],
                f"{spell.name} — {'healing' if plan['kind'] == 'heal' else 'damage'}",
                None, partial, state, dice, state_key="cast_state",
            )
            state["rolls"].append(roll.as_dict())
            state["rolled"] = max(0, roll.total)
            state["stage"] = "targets"

        rolled = int(state.get("rolled", 0))
        while dice and state["i"] < len(live):
            target = self.scene.actors[live[state["i"]]]
            amount, saved = rolled, False

            if plan["save"]:
                # Rolled by whoever is saving, not by the caster — which is what lets a
                # PC roll their own save against a spell and keeps every NPC's save with
                # the engine, through the one rule `_force_visibility` states.
                save_roll = self._roll_or_suspend_stage(
                    intent, target, target.save_modifiers(plan["save"]),
                    f"{SAVES[plan['save']]} save against {spell.name}", dc,
                    partial, state, "1d20", state_key="cast_state",
                )
                state["rolls"].append(save_roll.as_dict())
                saved = d20_succeeds(save_roll, dc)
                # Half from full without parsing a tell: the saved flag only. The DC and
                # total live on the save's Roll, under its own visibility (§1.6 E12).
                state["effects"].append({"kind": "save", "ref": target.ref,
                                         "save": plan["save"], "saved": bool(saved)})
                effect = plan["save_effect"]
                if saved and effect == "negates":
                    amount = 0
                elif saved and effect == "half":
                    # Half of the total that was actually rolled, not a second roll of
                    # half the dice. `effectspec` cannot say "roll and halve" — the stored
                    # success branch carries half the *dice* — so the engine does it here,
                    # where the rolled number exists. Same rule `_op_save` applies to a
                    # poison gate; not the same code, because that one rolls per save and
                    # an area spell must not.
                    amount = max(0, rolled // 2)
                elif saved:
                    # "partial" — a successful save reduces the spell rather than halving
                    # it, and by how much is in the spell's own text. Nothing is applied
                    # rather than a number being invented, and the tell says why.
                    amount = 0
                state["tells"].append(
                    f"{target.name} {'makes' if saved else 'fails'} the "
                    f"{SAVES[plan['save']]} save ("
                    + (f"{natural_said(save_roll, dc)}, " if natural_said(save_roll, dc)
                       else "")
                    + f"{save_roll.total} against DC {dc})"
                    + (f"; what a partial save leaves is in {spell.name}'s text."
                       if saved and plan["save_effect"] == "partial" else "."))

            if plan["kind"] == "heal":
                healed = target.heal(amount)
                state["effects"].append({
                    "ref": target.ref, "kind": "heal", "amount": healed,
                    "rolled": amount, "hp_after": target.hp, "hp_max": target.hp_max,
                    "origin": f"spell:{spell.id}"})
                state["tells"].append(
                    f"{target.name} recovers {healed} hit points.")
            elif amount > 0:
                # A crowd is immune to a spell that picks out a number of creatures and
                # takes half again from one that fills an area — both troop rules, both
                # answered by the spell's own text (item 33). The immunity is stated rather
                # than silent: a caster who wastes a slot on it must be told why.
                unit = getattr(target, "troop", None)
                if unit is not None and plan.get("targets_counted"):
                    state["tells"].append(
                        f"{spell.name} picks out single creatures, and {target.name} is a "
                        f"crowd: it finds no one target among them and is wasted.")
                    state["i"] += 1
                    continue
                hit = self._apply_damage(target, amount, plan["damage_type"],
                                         traits=("area",) if plan.get("area") else (),
                                         lethality=plan["lethality"])
                hit["origin"] = f"spell:{spell.id}"
                state["effects"].append(hit)
                # What the target actually lost, not what the die said: a 30-point
                # fireball against fire resistance 10 is 20, and a GM told the first
                # number narrates a wound nobody took.
                state["tells"].append(
                    f"{target.name} takes {hit['amount']} {hit['type']}"
                    + (f" ({hit['note']})." if hit["note"] else "."))
            state["i"] += 1

        effects = [cast_effect] + list(state["effects"])
        crossed = []
        for ref in {e["ref"] for e in state["effects"] if e.get("kind") == "damage"}:
            crossed.extend(self._hp_state_effects(self.scene.actors[ref]))
        effects.extend(crossed)

        tells = [f"{actor.name} casts {spell.name} ({'; '.join(bits)})."] + where
        if dice and "rolled" in state:
            tells.append(f"{dice} — {state.get('rolled', 0)}.")
        tells.extend(state["tells"])
        crossed_said = self._hp_state_tell(crossed).strip()
        if crossed_said:
            tells.append(crossed_said)

        # What the harm does to how they feel — once, after every roll, and only for a
        # spell that harms (being caught is the attack, so a made save counts).
        if state.get("harms"):
            for ref in live:
                victim = self.scene.actors.get(ref)
                if victim is None or ref == actor.ref:
                    continue
                felt = attitude_mod.harmed(self, victim, actor, f"spell:{spell.id}",
                                           seen=(state.get("seen") or {}).get(ref, True),
                                           gated=bool(state.get("gated")))
                if felt:
                    effects.append(felt)
                    line = attitude_mod.harm_said(felt, victim.name)
                    if line:
                        tells.append(line)

        lit, lit_said = self._ignite_caught(actor, spell, state)
        effects.extend(lit)
        tells.extend(lit_said)

        # The riders, in two piles. The ones the engine can run — a manifestation, a
        # summon, an operation on another spell, anything waiting on a trigger — are run;
        # everything else keeps the path it had, rendered for the GM. A bless's +1 is
        # still not applied, and that is a separate argument with its own test: applying
        # it needs a decision about stacking that this change is not making.
        ran, said = self._run_specs(plan["riders"], self._cast_context(
            actor, spell, cl, level, dc, live, plan, intent))
        effects.extend(ran)
        tells.extend(said)
        for spec in plan["riders"]:
            if not self._executes(spec):
                tells.append(effectspec.render(spec) + ".")

        return Outcome(
            intent_id=intent.id, op="cast",
            rolls=[_roll_from_dict(r) for r in state["rolls"]],
            effects=effects, tell=" ".join(tells), because=intent.because,
        )

    # --- where a cast went (rules/areas.py does the geometry) ---------------------------

    def _cast_aim(self, intent: Intent, actor: Actor):
        """The cast's aim: the `aim` param, else the legacy `at` or `square`, else the
        intent's own target."""
        from . import areas

        aim = areas.aim_of(intent.params, actor.ref)
        if aim.kind == "none" and intent.targets():
            first = intent.targets()[0]
            aim = areas.Aim("self") if first == actor.ref else areas.Aim("ref", first)
        return aim

    def _against(self, actor: Actor, other: Actor) -> bool:
        """Whether harming `other` is harming somebody not on `actor`'s side — the half of
        Invisibility's definition of an attack that is about WHO: "any spell ... whose area
        or effect includes a foe". In a fight, the sides say; out of one, the party is the
        PC and whoever travels with them."""
        if other is actor or other.has_state("state.down.dead"):
            return False
        for refs in (self.scene.sides or {}).values():
            if actor.ref in refs:
                return other.ref not in refs
        if actor.is_pc:
            return not (other.is_pc or other.has_state(states.TRAVELS_WITH_YOU))
        return other.is_pc or other.has_state(states.TRAVELS_WITH_YOU)

    def _cast_gate(self, intent: Intent, actor: Actor, spell, aim, foes: list[str],
                   state: dict) -> Outcome | None:
        """The battle gate, for a spell: first violence opens the fight and never resolves
        it (tests/test_battle_gate.py), whichever door the violence came through.

        Harmful magic was the one violence that never started a fight (item 22.2):
        `_op_cast` never called `_ensure_encounter`. Now a first harmful cast opens the
        encounter and stops, exactly as `_op_attack`'s first swing does — no slot spent,
        nothing rolled — and the caster keeps the turn to cast it as declared (owner,
        Q31: the gate, not a surprise round). `_ensure_encounter` takes one target, so the
        area's other victims are drawn in with `join_fight` and `rally`, or they would
        stay bystanders inside the flames. Inside a running fight nothing defers: a caught
        bystander is simply brought in, like a swing at one.

        Only the player's cast is deferred. Another caster's opens the fight and resolves:
        `_their_first_blow` rolls an NPC's deferred SWING in the same batch, and there is
        no such door for a spell, so deferring it would leave the cast undone."""
        def on_a_side(ref: str) -> bool:
            return any(ref in refs for refs in (self.scene.sides or {}).values())

        opened = False
        if not self.scene.in_encounter:
            opened = self._ensure_encounter(actor.ref, foes[0])
        for ref in foes:
            if self.scene.in_encounter and not on_a_side(ref):
                self.join_fight(ref)
                self.rally(ref)
        if not actor.is_pc or not (opened or self._battle_joined):
            return None
        self._battle_joined = True
        for i, (ref, _) in enumerate(self.scene.initiative):
            if ref == actor.ref:
                self.scene.turn = i
                self.scene.acted.add(actor.ref)
                break
        mine = next((s for s, refs in self.scene.sides.items() if actor.ref in refs), None)
        names = [self.scene.actors[r].name
                 for s, refs in self.scene.sides.items() if s != mine
                 for r in refs if r in self.scene.actors
                 and not self.scene.actors[r].is_down]
        params = {"spell": spell.id}
        if aim.as_param():
            params["aim"] = aim.as_param()
        return Outcome(
            intent_id=intent.id, op="cast",
            rolls=[_roll_from_dict(r) for r in state.get("rolls") or []],
            effects=[{"ref": actor.ref, "kind": "battle_joined", "op": "cast",
                      "target": foes[0], "params": params}],
            tell=(f"Battle is joined: {actor.name} squares off against "
                  f"{', '.join(names) or self.scene.actors[foes[0]].name}. Nothing has "
                  f"been cast yet — {spell.name} is still to be spoken."),
            because=intent.because)

    def _aim_words(self, state: dict) -> str:
        """What the cast was aimed at, in words: a person's name, a thing's, or "". A
        direction is never a word here — the world has no bearings (item 19.5)."""
        aim = state.get("aim") or {}
        kind, value = aim.get("kind", "none"), str(aim.get("value", ""))
        if aim.get("said"):
            return str(aim["said"])
        if kind == "ref" and value in self.scene.actors:
            return self.scene.actors[value].name
        if kind == "object":
            return f"the {value}"
        if kind == "direction" and value in ("up", "down"):
            return "overhead" if value == "up" else "below"
        return ""

    def _cast_where(self, actor: Actor, spell, state: dict, targets: list[str],
                    no_victim: bool, aim_said: str) -> list[str]:
        """The sentences that say where the cast went and whom it caught — facts for the
        narrator, never a compass word."""
        from . import areas

        out: list[str] = []
        aim = state.get("aim") or {}
        area = state.get("area") or {}
        kind = aim.get("kind", "none")
        if kind == "object" and aim_said:
            prep = "up into" if aim.get("value") == "canopy" else "at"
            out.append(f"It is aimed {prep} {aim_said}.")
        elif kind == "direction" and aim_said:
            out.append(f"It is aimed {aim_said}.")
        if state.get("fell_short") and aim_said:
            out.append(f"It falls short of {aim_said}.")
        if area.get("measured") and targets:
            word = {"cone": "cone", "line": "line", "cylinder": "column",
                    "cube": "area", "square": "area"}.get(area.get("shape"), "burst")
            names = [self.scene.actors[r].name for r in targets if r in self.scene.actors]
            if names:
                out.append(f"The {word} catches {', '.join(names)}.")
        if no_victim:
            out.append("The flames reach nobody." if areas.is_fire(spell)
                       else f"{spell.name} reaches nobody.")
        return out

    def _ignite_caught(self, actor: Actor, spell, state: dict) -> tuple[list, list]:
        """Light what a fire spell caught, once per cast — the flag in the state keeps a
        resume from lighting it twice."""
        if state.get("lit") or not any(o.get("burns") for o in state.get("objects") or []):
            return [], []
        state["lit"] = True
        return self._ignite([o for o in state["objects"] if o.get("burns")],
                            {"caster": actor.ref, "source": spell.name})

    def _ignite(self, objects: list[dict], ctx: dict) -> tuple[list[dict], list[str]]:
        """Set alight what a fire spell caught: "Flammable materials burn if the flames
        touch them" (Burning Hands). One executor, beside `_manifest`, and the same shape:
        a `Manifestation` for the burning, and one of smoke (`obscuring`) over burning
        ground — smoke gives concealment (CRB, Smoke Effects). Smoke from a canopy rises,
        so none is laid on the ground under it.

        How long it burns is the one duration the CRB gives a fire, the forest fire's
        "2d4 × 10 minutes", rolled on the engine's dice. It does not spread: no spread rate
        at this scale could be sourced, and the owner ruled a patch (Q33: "a patch, 2d4 ×
        10 min, no spread"), so the CR 6 forest fire is never reached from here.

        **What standing in it costs** (I3, 2026-09-29). Measured on the G2 cast-area run: the
        flames licked a stall's awnings and the undergrowth, the tell said they caught, and
        nothing followed — a manifestation with no ward is scenery. Each burning patch now
        carries a ward from `content/rules/hazards.json`'s `burning-brush` row (Catching on
        Fire: Reflex DC 15 or 1d6 fire, each round a creature stands in it) and each bank
        of smoke one from the `smoke` row (Fortitude DC 15 or 1d6 nonlethal; its
        concealment is the smoke's own obscuring squares). The numbers are the rows',
        never this method's, and each row names what of the book it does not yet do. The
        wards fire where the rounds are real — a fight's (`Scene.tick_standing`) — and
        expire on the clock with their fire, in minutes when time passes outside one
        (`Scene.advance` → rounds, the one ticker).

        The ward's spec also carries the hazard's id and the place the fire is in
        (`hazard`, `at`): the brief's BURNING HERE line (`gm/brief/burning.py`) reads the
        scene's standing fires by those, never by the words of a manifestation's name, and
        says nothing of a fire in a place the party has walked out of."""
        from . import hazards as hazards_mod

        effects: list[dict] = []
        tells: list[str] = []
        minutes = self.dice.roll("2d4", label="how long the fire burns",
                                 visibility="hidden").total * 10
        rounds = minutes * 10
        caster = str(ctx.get("caster", ""))
        source = str(ctx.get("source", ""))

        def ward_for(rule: str, made: Manifestation, what: str) -> None:
            row = hazards_mod.get(rule) or {}
            w = row.get("ward") or {}
            if not w:
                return
            hit = {"type": "damage", "dice": str(w["dice"]),
                   "damage_type": str(w.get("type", "untyped")),
                   "lethality": str(w.get("lethality", "lethal"))}
            self.scene.wards.append(Ward(
                owner="", trigger="each_round", recipient="area",
                spec={"type": "save_gate", "target": str(w["save"]),
                      "on_failure": [hit], "on_success": [],
                      "hazard": rule, "at": str(self.scene.at or ""), "what": what},
                caster=caster, rounds_left=rounds, source=str(row.get("name", rule)),
                dc=int(w["dc"]), manifest_id=made.id))

        for obj in objects:
            cells = [tuple(c) for c in (obj.get("at") or [])]
            if obj.get("kind") == "prop" and obj.get("square"):
                sq = obj["square"]
                cells = [(int(sq[0]), int(sq[1]))]
            name = str(obj.get("name") or "it")
            made = self.scene.place(Manifestation(
                what=f"burning {name}", terrain="none", squares=cells,
                rounds_left=rounds, source=source, owner=caster))
            ward_for("burning-brush", made, name)
            effects.append({"kind": "manifest", **made.as_dict(), "hazard": "burning-brush",
                            "minutes": minutes})
            said = f"The {name} catches fire"
            if obj.get("kind") == "feature" and name != "canopy":
                ground = sorted({(c[0], c[1]) for c in cells})
                smoke = self.scene.place(Manifestation(
                    what="smoke", terrain="obscuring", squares=ground,
                    rounds_left=rounds, source=source, owner=caster))
                ward_for("smoke", smoke, name)
                effects.append({"kind": "manifest", **smoke.as_dict(), "hazard": "smoke",
                                "minutes": minutes})
                said += ", and smoke rises from it"
            said += "; standing in it risks catching fire" if cells and name != "canopy" \
                else ""
            tells.append(said + ".")
        if objects:
            tells.append("It burns as a patch and does not spread, and it will burn "
                         "itself out before long.")
        return effects, tells

    def _retaliate(self, struck: Actor, by: Actor) -> list[dict]:
        """Whatever the creature that was just hit does back, on its own.

        Reads the wards the scene holds rather than anything on either sheet, for the
        reason `Scene.guards` gives: this is a relationship, and it belongs to the scene.
        """
        out: list[dict] = []
        for ward in list(self.scene.wards):
            if ward.trigger == "when_struck" and ward.owner == struck.ref:
                out.extend(self.scene._fire(ward, struck_by=by.ref))
        return out

    def _cast_context(self, actor: Actor, spell, cl: int, level: int, dc: int,
                      live: list[str], plan: dict, intent: Intent) -> dict:
        """Everything a spec needs about the cast it arrived in.

        The duration is the piece that was missing and is now real: `spells.parse_duration`
        reads the printed line and `spells.duration_rounds` turns it into rounds for this
        caster, so "rounds/level (1)" at caster level 5 is five rounds rather than a
        sentence nothing can time. Without it a ward would have to be given an invented
        lifetime, which is how a fog cloud ends up standing for the rest of the campaign.
        """
        square = intent.params.get("square")
        if square is None and self.scene.has_grid:
            square = (self.scene.positions.get(live[0]) if live else None) \
                or self.scene.positions.get(actor.ref)
        return {
            "caster": actor.ref, "targets": live, "caster_level": cl,
            # Rolled once, here, with the engine's own seeded dice — see
            # `spells.roll_duration` on why the deterministic reader stayed deterministic.
            "rounds": spells_mod.roll_duration(spell, cl, self.dice),
            "source": spell.name, "dc": dc,
            "save": plan.get("save", ""), "save_effect": plan.get("save_effect", ""),
            "square": tuple(square) if square else None,
            "chosen": intent.params.get("choose"),
            "vars": {
                "caster_level": cl, "level": actor.level, "spell_level": level,
                "hit_dice": actor.hit_dice, "casting_mod": dc - 10 - level,
                **{f"{ab}_mod": actor.ability_mod(ab)
                   for ab in ("str", "dex", "con", "int", "wis", "cha")},
            },
        }

    # --- executing the effect vocabulary --------------------------------------------
    #
    # Deliberately narrow, and the narrowness is the design. `casting_plan` already owns
    # the rolled dice and the save, and the 6,476 specs the corpus carried before these
    # types existed keep the exact path they had: a bless's +1 is still rendered for the
    # GM rather than applied, because applying it is a separate argument with its own
    # test pinning the current answer.
    #
    # What runs here is what could not be *said* at all before — a manifestation, a
    # summon, an operation on another spell, a miss chance, damage to gear — plus any
    # effect whose trigger is not "immediately", which is the repeating and retributive
    # family. Nothing that used to be narrated silently starts happening.

    _EXECUTES = ("manifest", "summon", "spell_operation", "concealment", "object_damage",
                 "choose_one", "bundle", "attitude")

    def _executes(self, spec: dict) -> bool:
        return (str(spec.get("type", "")) in self._EXECUTES
                or str(spec.get("trigger") or "on_cast") != "on_cast")

    def _run_specs(self, specs: list[dict], ctx: dict) -> tuple[list[dict], list[str]]:
        """Every spec in this list the engine can run, run. Returns effects and tells.

        `ctx` carries what a spec needs and cannot know: the caster, the targets, the
        caster level to resolve a formula against, the save DC, the duration in rounds,
        and the square a manifestation lands on.
        """
        effects: list[dict] = []
        tells: list[str] = []
        for spec in specs:
            if not self._executes(spec):
                continue
            got, said = self._run_one(spec, ctx)
            effects.extend(got)
            tells.extend(said)
        return effects, tells

    def _run_one(self, spec: dict, ctx: dict) -> tuple[list[dict], list[str]]:
        kind = str(spec.get("type", ""))
        if kind == "bundle":
            return self._run_specs(spec.get("effects") or [], ctx)
        if kind == "choose_one":
            return self._choose(spec, ctx)
        if kind == "manifest":
            return self._manifest(spec, ctx)
        if kind == "summon":
            return self._summon(spec, ctx)
        if kind == "spell_operation":
            return self._spell_operation(spec, ctx)
        if kind == "concealment":
            return self._conceal(spec, ctx)
        if kind == "object_damage":
            return self._object_damage(spec, ctx)
        if kind == "attitude":
            return self._attitude(spec, ctx)
        return self._stand_by(spec, ctx)

    def _attitude(self, spec: dict, ctx: dict) -> tuple[list[dict], list[str]]:
        """A spell that changes how somebody feels about you. Charm person, and 32 others.

        The type has existed since the spell import and shipped `engine=False` with the
        note "no check in the app consults an attitude yet". A check does now
        (`rules/attitude.py`), so the block came off — and the suite immediately caught
        that lifting the block is a CLAIM: `test_every_executable_type_has_something_that
        _executes_it` exists because a type marked executable with no executor is
        "narrative wearing a costume". This is the executor that makes the claim true.

        Through `_set_attitude`, the same one applicator the `condition` op and a
        Diplomacy check use, so a charmed guard and a talked-round guard are one kind of
        thing and one `remove_effects(source=...)` clears either.

        The spec's `towards` field is not honoured and cannot be: an `attitude.*` tag says
        how a creature feels, full stop, and the app has no per-observer attitudes. Twelve
        of the thirty-three spells say "towards the caster", which is what the tag already
        means in practice — the party is who the brief is written for.
        """
        from . import attitude as attitude_mod

        key = str(spec.get("target") or "").strip().lower()
        if key not in states.ATTITUDES:
            return self._stand_by(spec, ctx)
        rounds = ctx.get("rounds")
        effects: list[dict] = []
        tells: list[str] = []
        for ref in ctx.get("targets") or []:
            who = self.scene.actors.get(str(ref))
            if who is None:
                continue
            was = attitude_mod.of(who)
            cond = self._set_attitude(who, key, rounds,
                                      str(ctx.get("source") or "a spell"))
            effects.append({"ref": who.ref, "kind": "condition", "condition": key,
                            "rounds_left": cond.rounds_left})
            tells.append(attitude_mod.said(who.name, was, key))
        return effects, tells

    def _choose(self, spec: dict, ctx: dict) -> tuple[list[dict], list[str]]:
        """One option, or none and a sentence saying so.

        Never all of them. A polymorph spell written as five separate effects applies
        five shapes at once, which is the failure the type exists to end — so an unchosen
        choice is reported rather than resolved, and the report names the options so the
        GM can recast naming one.
        """
        options = spec.get("options") or []
        picked = spec.get("chosen") if spec.get("chosen") not in (None, "") \
            else ctx.get("chosen")
        try:
            index = int(picked)
        except (TypeError, ValueError):
            index = 0
        if not 1 <= index <= len(options):
            names = " / ".join(effectspec.render(o) for o in options)
            return ([{"kind": "choice_pending", "options": len(options)}],
                    [f"Nothing is applied until one is chosen — {names}. "
                     f'Recast with {{"choose": 1}} to take the first.'])
        # The chosen option is always named, and *then* whatever of it the engine can run
        # is run. Reporting only what executed meant a choice resolved to a form made of
        # modifiers said nothing at all — the GM could not tell which shape was taken.
        taken = options[index - 1]
        effects = [{"kind": "choice_made", "chosen": index,
                    "line": effectspec.render(taken)}]
        tells = [effectspec.render(taken) + "."]
        ran, said = self._run_one(taken, ctx) if self._executes(taken) else ([], [])
        return effects + ran, tells + said

    def _manifest(self, spec: dict, ctx: dict) -> tuple[list[dict], list[str]]:
        """Write a thing into the scene, and onto the map where there is one."""
        squares = self._squares_for(spec, ctx)
        made = self.scene.place(Manifestation(
            what=str(spec.get("what") or "something"),
            terrain=str(spec.get("terrain") or "none"),
            squares=squares, rounds_left=ctx.get("rounds"),
            source=ctx.get("source", ""), owner=ctx.get("caster", ""),
        ))
        # The hazard half. A cloud that burns whoever is in it is a ward aimed at the
        # area, and it is the same structure a per-round damage spell registers — which
        # is why `on_enter` did not need machinery of its own.
        for inner in spec.get("on_enter") or []:
            self.scene.wards.append(Ward(
                owner="", trigger="each_round", recipient="area",
                spec=self._resolved(inner, ctx), caster=ctx.get("caster", ""),
                rounds_left=ctx.get("rounds"), source=ctx.get("source", ""),
                save=ctx.get("save", ""), dc=int(ctx.get("dc", 0) or 0),
                save_effect=ctx.get("save_effect", ""), manifest_id=made.id,
            ))
        where = (f" over {len({(s[0], s[1]) for s in made.squares})} squares"
                 if made.squares else "")
        # Said when the thing wanted squares and there was nowhere to put them. The first
        # version tested `not made.squares`, which is true in exactly the case the note is
        # for — so the note never appeared on a mapless scene and always would have on a
        # dancing light.
        note = "" if self.scene.has_grid or made.terrain == "none" else \
            " — there is no map in this scene, so it is placed in the fiction only"
        return ([{"kind": "manifest", **made.as_dict()}],
                [f"{made.what[:1].upper()}{made.what[1:]}{where}{note}."])

    def _squares_for(self, spec: dict, ctx: dict) -> list[tuple[int, ...]]:
        """The cells a manifestation covers, from the grid's own area functions.

        `rules/grid.py` already draws a burst, a line and a cone for spell areas, so a
        fog cloud is `burst(centre, 20)` and nothing here has to know what a radius is.
        A scene with no map gets an empty list and the thing still exists — a
        manifestation without squares is fiction, not a bug.

        **Cells, not squares, since the areas gained a third axis.** A spread is defined
        by Aiming a Spell as extending "in all directions", and fireball's printed area is
        a 20-ft.-radius spread — so it has always been a sphere on paper and was a flat
        disc here. Measured: that disc was really an infinite column, because a stored
        square matches at any level, so a fireball on the floor caught a creature flying a
        hundred feet above it. A sphere has a top and a bottom.

        The centre is normalised to a cell first, using the ground under it when the
        caster named only a square, because an area that is a sphere only when somebody
        happens to be flying is two rules wearing one name.
        """
        if not self.scene.has_grid:
            return []
        centre = ctx.get("square")
        if centre is None:
            return []
        centre = tuple(centre) if len(tuple(centre)) > 2 else (
            centre[0], centre[1], self.scene.grid.ground(centre))
        size = int(spec.get("size") or 0)
        shape = str(spec.get("shape") or "radius")
        # Through `rules/areas.py`, the one place an area is laid, since 2026-09-28: the
        # grid's own shapes measured from a square's centre, so a 20-ft fog cloud covered
        # 61 squares where the book's intersection rule gives 44 (docs/design-e-magic.md
        # §3.3). Fog clouds and every other manifestation shrink to the book's size.
        from . import areas

        if not size or shape == "point":
            return [tuple(centre)]
        if shape == "line":
            towards = ctx.get("towards") or (centre[0] + 1, centre[1])
            cells, _ = areas.line_cells(self.scene, centre[:2], centre[2], tuple(towards),
                                        size)
            return sorted(cells | {tuple(centre)})
        if shape == "cone":
            facing = str(ctx.get("facing") or "e").lower()
            if facing not in gridmod.DIRECTIONS:
                facing = "e"
            cells, _ = areas.cone_cells(self.scene, centre[:2], centre[2], facing, size)
            return sorted(cells)
        if shape in ("wall", "square"):
            span = max(1, size // gridmod.SQUARE_FT)
            return [(centre[0] + dx, centre[1]) for dx in range(span)] if shape == "wall" \
                else [(centre[0] + dx, centre[1] + dy)
                      for dy in range(span) for dx in range(span)]
        # Nothing below the floor. A sphere centred on the ground reaches down as far as
        # it reaches up, and there is no level under level zero to fill — the first run
        # of this put a bank of fog in the cellar of a room that has no cellar.
        return sorted(areas.burst_cells(tuple(centre), size, self.scene))

    def _summon(self, spec: dict, ctx: dict) -> tuple[list[dict], list[str]]:
        """Bring a creature in through the same door everything else arrives by."""
        from .bestiary import UnknownTemplate

        name = str(spec.get("creature") or "").strip()
        side = "pc" if str(spec.get("side") or "caster") == "caster" else "them"
        caster = self.scene.actors.get(ctx.get("caster", ""))
        if caster is not None and not caster.is_pc:
            side = "them" if side == "pc" else "pc"
        try:
            made = self._bring_in(name, count=int(spec.get("count") or 1), side=side)
        except UnknownTemplate as exc:
            # Named rather than invented. A summon that quietly produces nothing is a
            # spell the player paid a slot for and cannot tell did not work.
            return ([{"kind": "summon_refused", "creature": name, "why": str(exc)}],
                    [f"Nothing arrives: {exc}"])
        return ([{"kind": "summon", "actors": made, "side": side}],
                ["Answering the call: "
                 + ", ".join(f"{m['name']} ({m['ref']})" for m in made) + "."])

    def _spell_operation(self, spec: dict, ctx: dict) -> tuple[list[dict], list[str]]:
        """Permanency, dispel magic, suppression — spells whose target is another spell.

        The caster level check is rolled where the book calls for one; the three
        operations that act on a lifetime act on the real lifetimes the engine keeps —
        a buff's `rounds_left`, a condition's, a manifestation's. Countering and
        absorbing are reported: both happen in the middle of somebody else's casting and
        there is no readied-action step to hang them on, which is said out loud rather
        than answered with a shrug.
        """
        op = str(spec.get("operation") or "dispel")
        who = self._recipient(spec, ctx)
        named = str(spec.get("target") or "").strip()
        effects: list[dict] = []

        if spec.get("check_dc"):
            dc = effectspec.evaluate(spec["check_dc"], ctx.get("vars") or {})
            roll = self.dice.d20([Modifier(int(ctx.get("caster_level", 1)),
                                           "caster level")],
                                 label=f"caster level check ({op})", visibility="hidden")
            effects.append({"kind": "caster_level_check", "op": op, "dc": dc,
                            "total": roll.total, "beat": roll.total >= dc})
            if roll.total < dc:
                return (effects,
                        [f"The caster level check fails ({roll.total} against DC {dc}); "
                         f"{named or 'the magic'} holds."])

        if op in ("counter", "absorb"):
            return (effects + [{"kind": "spell_operation_noted", "operation": op,
                                "target": named}],
                    [f"{effectspec.render(spec)} — the GM adjudicates this one: it "
                     f"resolves during another creature's casting, and the engine has no "
                     f"readied action to hang it on."])

        touched = self._lifetimes(who, named)
        if not touched:
            return (effects + [{"kind": "spell_operation_noted", "operation": op,
                                "target": named}],
                    [f"Nothing on {who.name if who else 'them'} matches "
                     f"{named or 'that'}."])

        changed = []
        for holder in touched if str(spec.get("everything")) == "yes" else touched[:1]:
            changed.append(self._retime(holder, op, ctx))
        effects.append({"kind": "spell_operation", "operation": op,
                        "ref": who.ref if who else "", "changed": changed})
        word = {"make_permanent": "will not expire now", "dispel": "ends",
                "suppress": "is held off", "extend": "lasts twice as long"}[op]
        return (effects,
                [", ".join(c["what"] for c in changed) + f" {word}."])

    def _lifetimes(self, who: Actor | None, named: str) -> list:
        """Everything on a creature — or in the scene — with a clock that can be changed.

        Matched by name where one is given, and everything otherwise. Buffs, conditions
        and manifestations all carry a `source`, which is the string a caster would use
        to say which spell they mean.
        """
        needle = named.strip().lower()

        def matches(source: str) -> bool:
            return not needle or needle in str(source or "").lower()

        found: list = []
        if who is not None:
            # The effect records themselves, not the read-only condition/buff views:
            # a dispel has to move a real clock, and the views are copies.
            found += [e for e in who.effects
                      if e.kind in ("buff", "condition") and matches(e.source)]
        found += [m for m in self.scene.manifests if matches(m.source)]
        return found

    def _retime(self, holder, op: str, ctx: dict) -> dict:
        """Change one thing's clock. The four operations that are really about a clock."""
        what = getattr(holder, "source", "") or getattr(holder, "what", "") or "it"
        left = getattr(holder, "rounds_left", None)
        if op == "make_permanent":
            holder.rounds_left = None
        elif op == "extend":
            holder.rounds_left = None if left is None else left * 2
        else:                                    # dispel, suppress
            holder.rounds_left = 0 if op == "suppress" else -1
            if isinstance(holder, Manifestation):
                self.scene.lift(holder)
            else:
                # Through the applicator, not `effects.remove`: this was the last edit
                # of the store outside the one door, and a dispel is exactly the case
                # law 2 is about — the effect's contribution has to evaporate with it.
                # Matched on identity, because two records can share a source and only
                # the one the dispel found is going.
                for owner in self.scene.actors.values():
                    if holder in owner.effects:
                        owner.remove_effects(match=lambda e, h=holder: e is h)
                        break
        return {"what": what, "was": left, "now": getattr(holder, "rounds_left", None)}

    def _conceal(self, spec: dict, ctx: dict) -> tuple[list[dict], list[str]]:
        """A miss chance, held as a buff so it expires on the clock everything else uses."""
        who = self._recipient(spec, ctx)
        if who is None:
            return [], []
        amount = int(spec.get("miss_chance", 20) or 20)
        who.add_buff("concealment", "miss_chance", amount,
                     source=ctx.get("source", "concealment"), rounds=ctx.get("rounds"))
        return ([{"kind": "concealment", "ref": who.ref, "miss_chance": amount,
                  "rounds": ctx.get("rounds")}],
                [f"{who.name} is hard to place: attacks against them miss {amount}% of "
                 f"the time."])

    def _object_damage(self, spec: dict, ctx: dict) -> tuple[list[dict], list[str]]:
        who = self._recipient(spec, ctx)
        if who is None:
            return [], []
        rolled = max(0, self.dice.roll(
            effectspec.resolve_dice(spec.get("dice"), ctx.get("caster_level", 1)),
            label="object damage", visibility="hidden").total)
        dtype = str(spec.get("damage_type") or "untyped")
        named = str(spec.get("item") or "").strip()
        results = ([who.damage_item(named, rolled, dtype)] if named
                   else who.damage_all_gear(rolled, dtype))
        notable = [r for r in results if r["taken"]]
        tell = "; ".join(
            f"{who.name}'s {r['item']} takes {r['taken']} through hardness "
            f"{r['hardness']}" + (" — destroyed" if r["destroyed"] else
                                  " — broken" if r["broken"] else "")
            for r in notable) or f"Nothing {who.name} carries is marked by it"
        return ([{"kind": "item_damage", "ref": who.ref, **r} for r in results],
                [tell + "."])

    def _stand_by(self, spec: dict, ctx: dict) -> tuple[list[dict], list[str]]:
        """An effect that is not due yet: register it and wait for its trigger.

        This is where repeating damage and retribution both land, and they land in the
        same place because they *are* the same thing with a different event on the front.
        """
        # Two different creatures, and keeping them apart is the whole fix. The ward
        # *sits on* whoever the spell was cast on — thorn body is on you — and its
        # `recipient` decides who takes the damage when it fires, which for thorn body is
        # whoever hit you. Collapsing the two is precisely the bug measured before this
        # existed: a converted thorn body burned the caster it was protecting.
        bearer = self._recipient({"recipient": "target"}, ctx)
        ward = Ward(
            owner=(bearer.ref if bearer else ctx.get("caster", "")),
            trigger=str(spec.get("trigger") or "on_cast"),
            spec=self._resolved(spec, ctx),
            recipient=str(spec.get("recipient") or "target"),
            caster=ctx.get("caster", ""), rounds_left=ctx.get("rounds"),
            source=ctx.get("source", ""), save=ctx.get("save", ""),
            dc=int(ctx.get("dc", 0) or 0), save_effect=ctx.get("save_effect", ""),
            stops_with=str(spec.get("stops_with") or ""),
        )
        self.scene.wards.append(ward)
        return ([{"kind": "ward", "ref": ward.owner, **ward.as_dict()}],
                [f"{effectspec.render(spec)} — standing, and it will fire when it is due."])

    def _resolved(self, spec: dict, ctx: dict) -> dict:
        """A spec with the things that depend on the caster already worked out.

        Done once, when the ward is registered, rather than every round it fires. A ward
        that re-read `caster_level` each round would keep changing as the caster levelled
        mid-fight, and — worse — would go on scaling after the caster had left the scene.
        """
        out = dict(spec)
        if out.get("dice"):
            out["dice"] = effectspec.resolve_dice(out["dice"], ctx.get("caster_level", 1))
        if "amount" in out and effectspec.is_formula(out["amount"]):
            out["amount"] = effectspec.evaluate(out["amount"], ctx.get("vars") or {})
        return out

    def _recipient(self, spec: dict, ctx: dict) -> Actor | None:
        """Which creature a spec lands on, at cast time."""
        who = str(spec.get("recipient") or "target")
        if who in ("caster", "self"):
            return self.scene.actors.get(ctx.get("caster", ""))
        live = [r for r in (ctx.get("targets") or []) if r in self.scene.actors]
        if live:
            return self.scene.actors[live[0]]
        return self.scene.actors.get(ctx.get("caster", ""))

    def _check_cast(self, intent: Intent, index: int) -> None:
        """Everything about a cast that is checkable before anything is spent.

        Each refusal names the thing that is wrong and, where there is one, the number,
        because a rejection the model cannot act on costs a whole regeneration.
        """
        actor = self.scene.get(intent.actor)
        if actor is None:
            raise IntentError(f"cast: no such actor {intent.actor!r}", "refs", index)
        if not casting.is_caster(actor):
            raise IntentError(
                f"cast: {actor.name} is a {actor.char_class or 'creature'} and does not "
                f"cast spells.", "legality", index, code="not_known",
                for_a_person=f"{actor.name} does not cast spells.",
            )
        try:
            spell = spells_mod.get(str(intent.params["spell"]))
        except KeyError:
            # By name, among the spells this caster knows — "magic missile" is what a
            # model writes and `magic-missile` is the id. Stage 8's verifiers found
            # the id-only lookup would have been the next refusal after the actor.
            said = " ".join(str(intent.params["spell"]).lower().replace("-", " ").split())
            spell = None
            for sid in list(getattr(actor, "spellbook", []) or []) \
                    + list((getattr(actor, "prepared", {}) or {}).keys()):
                try:
                    cand = spells_mod.get(str(sid))
                except KeyError:
                    continue
                if " ".join(str(cand.name).lower().split()) == said:
                    spell = cand
                    intent.params["spell"] = cand.id
                    break
            if spell is None:
                raise IntentError(
                    f"cast: no spell {intent.params['spell']!r}. Name one they know, by "
                    f"id: {', '.join(list(getattr(actor, 'spellbook', []) or [])[:8]) or 'none'}.",
                    "reference", index) from None

        data = casting.caster_data(actor)
        level = casting.spell_level_for(actor, spell)
        if level is None:
            raise IntentError(
                f"cast: {spell.name} is not on the {data.get('list', 'caster')} list.",
                "legality", index, code="not_on_list",
                for_a_person=f"{spell.name} is not a {data.get('list', 'caster')} spell.",
            )
        if level > casting.highest_spell_level(actor):
            raise IntentError(
                f"cast: {spell.name} is a level {level} spell and {actor.name} is a "
                f"level {actor.level} {actor.char_class} — they reach level "
                f"{casting.highest_spell_level(actor)}.", "legality", index,
                code="too_high",
                for_a_person=f"{spell.name} is a level {level} spell, beyond what "
                             f"{actor.name} can cast yet.",
            )
        if not casting.can_cast_level(actor, level):
            ability = casting.casting_ability(actor)
            raise IntentError(
                f"cast: a level {level} spell needs {ability.title()} {10 + level} and "
                f"{actor.name} has {actor.ability_score(ability)}.", "legality", index,
                code="ability_too_low",
                for_a_person=f"A level {level} spell needs {ability.title()} {10 + level}; "
                             f"{actor.name} has {actor.ability_score(ability)}.",
            )
        if not casting.knows(actor, spell):
            raise IntentError(
                f"cast: {spell.name} is not in {actor.name}'s spellbook.",
                "legality", index, code="not_known",
                for_a_person=f"{spell.name} is not in {actor.name}'s spellbook.",
            )
        # Every PREPARED caster, not only the ones who prepare from a book. This read
        # `prepare_from == "spellbook"` until 2026-09-19, so the check fired for wizards and
        # for nobody else — and a cleric, druid, paladin or ranger prepares nothing, ever,
        # which is the chain behind "spellcasting is broken in general" (item 25). With no
        # prepared spells a cleric's vocabulary was empty, `inject_cast` bowed out, no
        # `cast` op was ever emitted, and the nine checks below and above it — including the
        # caster-level one that refuses a level 5 spell to a level 1 cleric — were never
        # reached at all. The gate was working; nothing ever knocked on it.
        unprepared = casting.prepared_count(actor, spell.id) < 1
        # ...with the one exception the book names: a cure spell may be cast in place of a
        # prepared spell of the same level or higher, which is what keeps a cleric useful
        # when the day's preparation did not anticipate the wound (`casting.CONVERTS_TO`).
        # Conversion is a slot-for-slot trade, so it never reaches a 0-level spell: there
        # is no slot to spend on one.
        may_convert = (not casting.at_will(level)
                       and casting.converts_spontaneously(actor, spell)
                       and bool(casting.sacrifice_for(actor, level)))
        # Level 0 included since 2026-09-29. It was exempt (`and level > 0`), so every
        # cantrip in a wizard's book — twenty-odd of them — was castable without being
        # prepared. The rule is that a wizard "can prepare a number of cantrips... each
        # day" and casts THOSE at will (AoN, Wizard; the cleric's and druid's orisons read
        # the same): prepared first, then never expended.
        if data.get("kind") == "prepared" and unprepared and not may_convert:
            # Coded, with the fix a button can offer (item 21.3): measured 2026-09-28,
            # this refusal was raised seven times over one turn — the plan loop retried
            # a fact about the character that no plan could change — then handed to a
            # second model and narrated as nothing. A player-fixable code ends the loop
            # (Lane A) and reaches the player as this sentence and a Prepare button.
            raise IntentError(
                f"cast: {actor.name} did not prepare {spell.name} today."
                + (f" A cure spell may be cast in place of a prepared spell of that "
                   f"level or higher, and {actor.name} has none prepared to give up."
                   if casting.converts_spontaneously(actor, spell) else ""),
                "legality", index, code="unprepared",
                fix={"kind": "prepare", "spell": spell.id},
                for_a_person=f"{spell.name} is not prepared. Prepare it in the Spells tab "
                             f"first.",
            )
        if not casting.at_will(level) and casting.slots_left(actor, level) < 1:
            raise IntentError(
                f"cast: {actor.name} has no level {level} slots left.",
                "legality", index, code="no_slots",
                for_a_person=f"{actor.name} has no level {level} spell slots left today. "
                             f"A night's rest brings them back.",
            )
        self._check_aim(intent, index, actor, spell)

    def _check_aim(self, intent: Intent, index: int, actor: Actor, spell) -> None:
        """The aim, checked before anything is spent, each refusal coded (§2.6).

        Player-fixable where the refusing fact is the player's own words — a thing that is
        not here, a square out of range, an area spell aimed at nothing — and plan-fixable
        where it is the plan's choice of ref or of the aim's form."""
        from . import areas

        aim = self._cast_aim(intent, actor)
        cl = casting.caster_level(actor)
        shape = areas.shape_of(spell, cl)
        plan = spells_mod.casting_plan(spell, cl)
        # An aim at a ref nobody holds is `_check_cast_aim_ref`'s, asked in `_check_refs`
        # with the refs an earlier introduce or spawn in the list will make. It was asked
        # here, of the `aim` param only and of the scene as it stands, so a legacy `at`
        # passed unchecked and resolved at nobody (G2, 2026-09-28).
        if aim.kind == "object":
            if areas.find_object(self.scene, aim.value) is None:
                here = areas.objects_here(self.scene)
                raise IntentError(
                    f"cast: nothing here called {aim.value!r}. Here: "
                    f"{', '.join(here) or 'nothing to aim at but the people present'}.",
                    "legality", index, code="no_such_object",
                    for_a_person=(f"There is nothing here called {aim.value}."
                                  + (f" Here: {', '.join(here)}." if here else "")))
        if aim.kind in ("direction", "point") and plan.get("targets_counted"):
            raise IntentError(
                f"cast: {spell.name} picks out creatures; name one (aim ref:<ref>) rather "
                f"than a direction or a square.", "legality", index, code="wrong_aim")
        if aim.kind == "direction" and shape and shape["shape"] not in ("cone", "line"):
            raise IntentError(
                f"cast: {spell.name} bursts at a point; aim it at a creature, a thing or a "
                f"square, not a direction.", "legality", index, code="wrong_aim")
        if aim.kind == "self" and shape and shape["shape"] in ("cone", "line"):
            raise IntentError(
                f"cast: {spell.name} shoots away from the caster; aim it at somebody, "
                f"something or a direction.", "legality", index, code="wrong_aim")
        if aim.kind == "point" and self.scene.has_grid:
            cell = aim.cell()
            if not self.scene.grid.inside(cell[:2]):
                raise IntentError(
                    f"cast: square {aim.value} is off the map "
                    f"({self.scene.grid.width}x{self.scene.grid.height}).",
                    "legality", index, code="out_of_range",
                    for_a_person="That spot is off the map.")
            here = self.scene.positions.get(actor.ref)
            reach = spells_mod.range_feet(spell, cl)
            if here is not None and reach is not None:
                far = gridmod.distance(tuple(here[:2]), tuple(cell[:2]))
                if far > reach:
                    raise IntentError(
                        f"cast: that spot is {far} ft away and {spell.name} reaches "
                        f"{reach} ft.", "legality", index, code="out_of_range",
                        for_a_person=f"That spot is {far} ft away; {spell.name} reaches "
                                     f"{reach} ft.")
                if not areas._clear(self.scene, (here[0] + 0.5, here[1] + 0.5),
                                    (cell[0], cell[1]), ignore={tuple(here[:2])}):
                    raise IntentError(
                        f"cast: nothing reaches that spot from where {actor.name} stands "
                        f"— something solid is in the way.", "legality", index,
                        code="no_line_of_effect",
                        for_a_person="Something solid stands between you and that spot.")
        if shape and aim.kind == "none" and not shape.get("on_you"):
            raise IntentError(
                f"cast: {spell.name} fills an area and needs aiming: at somebody "
                f"(ref:<ref>), at something here (object:<name>), a direction for a cone "
                f"or line (dir:n..nw, up), or a square (point:x,y).", "legality", index,
                code="no_aim",
                for_a_person=f"Where do you aim {spell.name}? Say at whom or at what.")

    def _op_compel(self, intent: Intent, partial: dict) -> Outcome:
        """Pull somebody towards the actor.

        The tell says what defying it costs rather than that it happened, because "the
        thug is compelled" tells a player nothing they can act on and "−4 to attack anyone
        else" tells them everything.
        """
        ref = intent.params["to"]
        target = self.scene.actors[ref]
        towards = intent.actor or (intent.targets() or [None])[0]
        penalty = compulsion.PENALTY

        duration = intent.params.get("duration")
        rounds = None
        if isinstance(duration, dict):
            rounds = _to_rounds(duration.get("amount", 0), duration.get("unit", "round"))
        elif isinstance(duration, int):
            rounds = duration

        made = compulsion.add(target, by=towards, penalty=penalty, rounds=rounds,
                              source=intent.because or "compelled",
                              why=str(intent.params.get("why", "")))
        puller = self.scene.actors.get(towards)
        name = puller.name if puller else towards
        return Outcome(
            intent_id=intent.id, op="compel",
            effects=[{"ref": ref, "kind": "compulsion", "by": towards,
                      "penalty": made.penalty, "rounds_left": made.rounds_left}],
            tell=f"{target.name} is pulled towards {name}: −{made.penalty} to attack "
                 f"anyone else"
                 + (f" for {made.rounds_left} rounds." if made.rounds_left else "."),
            because=intent.because,
        )

    def _op_guard(self, intent: Intent, partial: dict) -> Outcome:
        """Stand between a blow and somebody else."""
        protects = intent.params["to"]
        guardian_ref = intent.actor or ""
        guardian = self.scene.actors[guardian_ref]
        kind = str(intent.params.get("kind", "redirect"))
        uses = intent.params.get("uses")

        made = Guard(
            guardian=guardian_ref, protects=protects, kind=kind,
            amount=int(intent.params.get("amount", 0) or 0),
            range_ft=int(intent.params.get("range_ft", 5) or 0),
            pool=str(intent.params.get("pool", "") or ""),
            uses_left=None if uses in (None, "") else int(uses),
            source=intent.because or "interposed",
        )
        # Replacing rather than appending: re-declaring the same arrangement is the
        # guardian renewing it, and stacking two copies would double every absorb.
        self.scene.guards = [g for g in self.scene.guards
                             if not (g.guardian == guardian_ref and g.protects == protects
                                     and g.kind == kind)]
        self.scene.guards.append(made)

        protected = self.scene.actors[protects]
        return Outcome(
            intent_id=intent.id, op="guard",
            effects=[{"ref": guardian_ref, "kind": "guard", **made.as_dict()}],
            tell=f"{guardian.name} steps in front of {protected.name} "
                 f"{guards_mod.PHRASE[kind]}.",
            because=intent.because,
        )

    def _op_move(self, intent: Intent, partial: dict) -> Outcome:
        ref = intent.params.get("who") or intent.actor
        actor = self.scene.actors[ref]
        was = self.scene.zones.get(ref, "near")
        square = intent.params.get("square")
        # A move with neither a square nor a zone word keeps the zone it had: the
        # square, when there is one, re-derives the zone below anyway, and a zone word
        # the fiction never contains is not worth a rejected turn.
        zone = str(intent.params.get("zone") or was).strip().lower()

        # An attack of opportunity has already resolved by the time we get here — it was
        # spliced in front of this intent precisely so it could land before the move did.
        # If it dropped them, they do not arrive: the whole reason for that ordering.
        if not actor.can_act():
            return Outcome(
                intent_id=intent.id, op="move", status="prevented",
                effects=[{"ref": ref, "kind": "move_stopped",
                          "why": actor.blocking_condition().lower()}],
                tell=f"{actor.name} is {actor.blocking_condition().lower()} and does not "
                     f"get there.",
                because=intent.because,
            )

        if square is not None and self.scene.has_grid:
            from_square = self.scene.positions.get(ref)
            refusal = self._cannot_leave_the_ground(actor, from_square, tuple(square))
            if refusal:
                return self._refuse(intent, refusal)
            self.scene.positions[ref] = tuple(square)
            self.scene.settle_levels()
            # The zone is now measured rather than taken on trust. The GM may still have
            # said "near"; if the square it also gave is forty feet away, the square wins.
            self.scene.resync_zones()
            zone = self.scene.zones.get(ref, zone)
            cost = self._move_cost(ref, from_square, tuple(square))
            crossed = f" ({cost} ft)" if cost is not None else ""
            # The move action, spent: a body that crossed the grid in a fight has walked
            # this round, and the closing step before a blow asks (`_closing_step`).
            if self.scene.in_encounter and from_square is not None \
                    and tuple(from_square) != tuple(square):
                self.scene.move_spent[ref] = self.scene.round
            effect = {"ref": ref, "kind": "position", "from": from_square,
                      "to": tuple(square), "feet": cost, "zone": zone}
            tell = f"{actor.name} moves to {zone}{crossed}."
            # The step `_close_before` put in front of a blow: told as what it is, so the
            # narrator hears that the distance was closed before the swing it dresses.
            # `closing_on` is written by code only — the parser refuses it from a model.
            foe = self.scene.actors.get(str(intent.params.get("closing_on") or ""))
            if foe is not None:
                effect["closing_on"] = foe.ref
                tell = (f"{actor.name} closes {cost} ft on {foe.name} to strike."
                        if cost is not None else
                        f"{actor.name} closes on {foe.name} to strike.")
            return Outcome(
                intent_id=intent.id, op="move",
                effects=[effect],
                tell=tell,
                because=intent.because,
            )

        self.scene.zones[ref] = zone
        return Outcome(
            intent_id=intent.id, op="move",
            effects=[{"ref": ref, "kind": "zone", "from": was, "to": zone}],
            tell=f"{actor.name} moves from {was} to {zone}.",
            because=intent.because,
        )

    def _not_by_the_stairs(self, here, going_to) -> str:
        """Why this floor cannot be reached from where the party is standing, or "".

        The place graph inside a settlement is deliberately a clique — "a settlement is
        not a maze, and a graph the player has to solve is a different game from the one
        this is" — and `_op_travel` has always resolved a destination by *name* among the
        places within reach rather than by walking exits. That was harmless while every
        exit list held everything.

        Storeys broke it. Measured the day they landed: standing in the market, the party
        could name "the top floor of the temple" and simply be there, having passed
        through neither the temple nor its stairs. So floors — and only floors — are
        checked against the exits that carry them, which is what the exit list was for.

        Ground level is left exactly as it was. The clique is a decision, not an
        oversight, and a stair is the one edge in this graph that means something.
        """
        from . import places as places_mod

        there = places_mod.storey_of(going_to.id)
        mine = places_mod.storey_of(here.id)
        if there == mine and places_mod.base_of(going_to.id) == places_mod.base_of(here.id):
            return ""
        if there == 0 and mine == 0:
            return ""                      # the town's own ground floor: as it always was
        if going_to.id in places_mod.stairs_from(here.id, here.terrain,
                                                 getattr(here, "shape", None),
                                                 getattr(here, "floors", ())):
            return ""
        # A floor that a walk can legitimately reach IS reached, since 2026-09-22: the
        # route-finder walks the stairs like any other exit, so market → guildhall →
        # upstairs is a legal way up and refusing it would be refusing the fix. Measured
        # on the live save the moment the router landed — "the upper floor of the
        # guildhall" from the market came back refused with its own remedy (go through
        # the guildhall) already available. This is the fifth travel of the item 35 turn,
        # answered properly rather than capped.
        if places_mod.route(self.places(), here.id, going_to.id):
            return ""
        # One floor of a building, named from somewhere that is not the floor below it.
        building = places_mod.base_of(going_to.id)
        door = next((p.name for p in self.places() if p.id == building), "the way in")
        return (f"{going_to.name} is not reached from here: the stairs to it are inside "
                f"{door}.")

    def _clear_square(self, wanted: tuple[int, int], size: str = "medium") -> tuple[int, int]:
        """`wanted`, or the nearest square that is not a wall and not somebody else.

        Needed the moment places gained a shape: the battlefield is laid out by zone and
        row, and those rows were computed against an empty field. Against a market with
        stalls in it, the arithmetic will cheerfully stand a guard inside one — and a
        creature in a blocked square cannot be routed to, cannot be left, and is a bug
        that looks like a rules problem.

        Spirals outward, so the answer stays as close to the intended spot as the ground
        allows and a line of people laid along a row stays a line.
        """
        from .grid import footprint

        grid = self.scene.grid
        if grid is None:
            return wanted
        taken = self.scene.occupied()

        def free(p) -> bool:
            return all(grid.passable(q) and q not in taken
                       for q in footprint(p, size))

        if free(wanted):
            return wanted
        for ring in range(1, max(grid.width, grid.height)):
            for dx in range(-ring, ring + 1):
                for dy in range(-ring, ring + 1):
                    if max(abs(dx), abs(dy)) != ring:
                        continue
                    p = (wanted[0] + dx, wanted[1] + dy)
                    if grid.inside(p) and free(p):
                        return p
        return wanted

    def _cannot_leave_the_ground(self, actor, start, end) -> str:
        """Why this creature may not move to that level, or "".

        The engine disposing of what the GM proposed, in the one place a creature's
        height can change. A model that narrates a spider scuttling up a wall is right
        and gets it; one that walks a man up the same wall is refused with the reason,
        which is a sentence it can act on rather than a silent correction.

        Only the *destination* level is asked about, not the route. A climber that has to
        cross a gap to reach its wall is a pathing question, and this is a permission
        question; `_move_cost` already answers "there is no route" with `None`.
        """
        level = end[2] if len(end) > 2 else 0
        was = start[2] if start is not None and len(start) > 2 else 0
        if level == was:
            return ""
        if level < 0:
            return f"{actor.name} cannot go below the floor."
        grid = self.scene.grid
        roof = grid.headroom(end) if grid is not None else None
        if roof is not None and level > roof:
            return (f"There is not that much air above {actor.name}: the ceiling is "
                    f"in the way.")
        how = actor.can_move_vertically()
        if how:
            return ""
        # Coming back down is always allowed — that is falling, and everybody can fall.
        if level < was:
            return ""
        return (f"{actor.name} has no way up: no fly speed and no climb speed, and "
                f"nothing here to climb.")

    def _move_cost(self, ref: str, start: tuple[int, ...] | None,
                   end: tuple[int, ...]) -> int | None:
        """What the move actually cost, routed around terrain and other creatures.

        `None` when there is no route — which is not the same as free, and is why this
        returns an optional rather than falling back to straight-line distance. A creature
        that has to go the long way round a wall pays for the long way.
        """
        if start is None or self.scene.grid is None:
            return None
        # The route is solved on the floor the creature is arriving at, and the climb or
        # the flight is added to it. Two reasons not to path in three dimensions here:
        # the grid's terrain — difficult, blocked, obscuring — is stated per square with
        # no notion of height, so there is nothing for a vertical A* to route around; and
        # the thing a player is owed is the total feet, which is the same either way for
        # every shape of route this engine can currently describe.
        from .grid import SQUARE_FT

        here, there = tuple(start[:2]), tuple(end[:2])
        was = start[2] if len(start) > 2 else 0
        now = end[2] if len(end) > 2 else 0
        if there == here:
            # Straight up or straight down, without crossing the floor at all — which is
            # the commonest move a climber makes and the one `reachable` cannot answer:
            # it returns every square you can get TO and deliberately omits the one you
            # are standing on, so asking it about your own column gives `None` and reads
            # as "there is no route" for a spider going up its own wall.
            flat = 0
        else:
            reach = self.scene.grid.reachable(
                here, 10_000, size=self.scene.actors[ref].size,
                occupied=self.scene.occupied(ignore=ref, level=now))
            flat = reach.get(there)
            if flat is None:
                return None
        return flat + abs(now - was) * SQUARE_FT

    def _op_advance_time(self, intent: Intent, partial: dict) -> Outcome:
        amount, unit = intent.params["amount"], intent.params["unit"]
        rounds = _to_rounds(amount, unit)
        minutes = rounds // 10 if unit == "round" else _to_minutes(amount, unit)
        # Through the one door. This op already collected its ended list and told it —
        # it was the only one of the six that did — but it ticked conditions and buffs
        # while pool cooldowns, compulsions, wards and fog clouds stood still.
        # Both, because they are not interchangeable here: the clock moves in whole
        # minutes and the tick is in rounds, and "five rounds pass" must expire a
        # five-round buff even though it moves the clock by nothing.
        passed = self.scene.advance(minutes, rounds=rounds)
        ended: list[str] = list(passed["ended"])
        tell = f"{amount} {unit}{'s' if amount != 1 else ''} pass."
        if ended:
            tell += " Ended: " + ", ".join(ended) + "."
        return Outcome(
            intent_id=intent.id, op="advance_time",
            effects=[{"kind": "time", "rounds": rounds, "minutes": minutes,
                      "ended": ended}],
            tell=tell, because=intent.because,
        )

    def _settle_xp(self) -> str:
        """Award the fight's XP to the PC while the sides are still declared.

        Returns the sentence for the tell, or "". Kept beside the encounter ops rather
        than in the view, because two different pieces of code end fights and both must
        pay out the same way.
        """
        from . import xp as xp_mod

        pc = self.scene.pc()
        if pc is None or pc.is_down:
            return ""
        # Settled first and appended to every path out of here. Written as
        # `return line + self._settle_treasure()` on the paying branch only, a creature
        # with a treasure column and no XP price — which is most of the bestiary, since
        # 6,355 of 7,136 entries never had either filled in — dropped its purse on the
        # floor and nobody picked it up.
        coin = self._settle_treasure()
        total, names = xp_mod.award_for_fallen(self.scene, pc)
        # Paid once. The routed units' debt is remembered on the scene because they are gone
        # from it (`_rout`), and a second fight in the same room must not pay for the first
        # one's dead a second time.
        self.scene.routed_xp = []
        if not total:
            # A fight that killed something and paid nothing has to say so. Silence
            # reads as "this fight was not worth anything", and the real reason is
            # usually that the creature carries no price — which is the GM's cue to
            # award it with the `xp` op rather than a thing to wonder about. Measured
            # in play: a bear died, the tally said nothing, and the ledger did not move.
            fallen = [a.name for side, refs in self.scene.sides.items()
                      if pc.ref not in refs
                      for a in (self.scene.actors.get(r) for r in refs)
                      if a is not None and (a.hp <= 0 or a.is_down)]
            if fallen:
                return (f" No experience: {', '.join(sorted(set(fallen)))} "
                        f"{'carries' if len(set(fallen)) == 1 else 'carry'} no price in "
                        f"the bestiary, so the award is the GM's to make.") + coin
            return coin
        return self.award_xp(pc, total, ", ".join(names)) + coin

    def award_xp(self, pc, total: int, reason: str) -> str:
        """The one writer of experience, and the one sentence that says so.

        Fights paid here first; now checks and storylines do too ("i should be
        receiving EXP for doing things and resolving situations and succeeding on
        checks", 2026-09-06). Second person at the source: this line reaches the
        page raw by design, and "MastaDaWanton gains 135 XP" was the one
        third-person survivor of the gemma4 fight audit's final run.
        """
        from . import xp as xp_mod

        total = int(total or 0)
        if total <= 0 or pc is None or not pc.is_pc:
            return ""
        pc.xp = int(getattr(pc, "xp", 0) or 0) + total
        nxt = xp_mod.total_for(min(20, pc.level + 1))
        line = (f" You gain {total:,} XP for {reason} "
                f"({pc.xp:,} of {nxt:,} for level {min(20, pc.level + 1)}).")
        if xp_mod.ready_to_level(pc):
            line += " Enough to advance — it will settle with a night's sleep."
        return line

    def reward_check(self, actor, skill: str, dc: int | None) -> str:
        """Pay for a check beaten, once per DC per place per day, or ""."""
        from . import xp as xp_mod

        if actor is None or not actor.is_pc or dc is None:
            return ""
        award = xp_mod.challenge_award(actor.level, dc)
        if not award:
            return ""
        day = self.scene.clock_minutes // (24 * 60)
        key = f"{skill}|{int(dc)}|{self.scene.at or ''}"
        if self.scene.rewarded.get(key) == day:
            return ""
        self.scene.rewarded[key] = day
        return self.award_xp(actor, award, f"the {skill} check (DC {int(dc)})")

    def award_story(self, action: str, thread: str = "") -> str:
        """The CRB's story award, when the undercurrent is concluded or advanced."""
        from . import xp as xp_mod

        pc = self.scene.pc()
        if pc is None:
            return ""
        total = xp_mod.story_award(pc.level, action)
        what = ("seeing a matter through" if action == "new" else "moving a matter along")
        return self.award_xp(pc, total, what + (f": {thread}" if thread else ""))

    def _settle_treasure(self) -> str:
        """What the fallen were carrying, into the PC's purse.

        Beside the XP for the same reason the XP is here: two pieces of code end fights
        and both have to pay out the same way. It became necessary the moment a market
        started charging — a character spent their starting wealth and there was no way
        in the game to earn a copper, because the `treasure` column every creature
        carries had never been read by anything.
        """
        from . import goods as goods_mod, treasure as treasure_mod

        pc = self.scene.pc()
        if pc is None or pc.is_down:
            return ""
        gold, names = treasure_mod.take_from_fallen(self.scene, pc, self.dice)
        if not gold:
            return ""
        pc.purse = goods_mod.credit(pc.purse, gold * 100)
        coins = goods_mod.coinage()
        return (f" Taken from {', '.join(sorted(set(names)))}: "
                f"{goods_mod.purse_line(goods_mod.coins_for(gold * 100), coins)} "
                f"({goods_mod.purse_line(pc.purse, coins)} in hand).")

    def _op_begin_encounter(self, intent: Intent, partial: dict) -> Outcome:
        rolls, order = [], []
        for side, refs in intent.params["sides"].items():
            for ref in refs:
                a = self.scene.actors[ref]
                r = self.dice.d20(a.initiative_modifiers(), label=f"{a.name} initiative",
                                  visibility="hidden")
                rolls.append(r)
                order.append((ref, r.total))
        order.sort(key=lambda t: -t[1])
        self.scene.initiative = order
        self.scene.round = 1
        self.scene.move_spent = {}
        self.end_talk("a fight starts")
        # Nobody has acted at the top of round one, so everyone is flat-footed until
        # their first turn comes round.
        self.scene.acted = set()
        self.scene.sides = {k: list(v) for k, v in intent.params["sides"].items()}
        self._lay_battlefield(intent.params["sides"])
        # The law joins a declared fight the way it joins one that starts with a swing:
        # a guard who sees it begin in the town where the player is wanted takes the
        # other side (docs/wanted.md).
        law_in = self._law_joins()
        # The turn pointer starts before the first combatant so the first advance lands
        # on whoever won initiative.
        self.scene.turn = -1
        self.scene.advance_turn()
        # An attack riding this same batch is deferred: the fight this op opened is
        # announced, and the first swing belongs to whoever wins the first turn.
        self._battle_joined = True
        # Rebuilt from the scene's own order, not the local one computed before the
        # law joined: the three-laws critic measured a guard in the initiative and
        # on the enemy side with no sentence saying so (2026-09-08).
        order = list(self.scene.initiative)
        names = ", ".join(self.scene.actors[r].name for r, _ in order if r in self.scene.actors)
        law_note = ""
        if law_in:
            law_note = (" The watch comes in against you: "
                        + ", ".join(self.scene.actors[r].name for r in law_in
                                    if r in self.scene.actors) + ".")
        return Outcome(
            intent_id=intent.id, op="begin_encounter", rolls=rolls,
            effects=[{"kind": "initiative", "order": order, "law": list(law_in or [])}],
            tell=f"Initiative: {names}.{law_note}", because=intent.because,
        )

    def _flat_footed(self, defender) -> bool:
        """Whether this defender has their guard down, for AC and for CMD alike.

        A defender who has not acted yet loses Dex to AC. Outside an encounter nobody has
        acted, so the first blow of a fight lands against a flat-footed target — the
        common ambush case, and usually several points of AC.

        ONE reader, because it was two: the attack path and the manoeuvre path each
        carried their own copy of this expression, so a rule corrected in one would have
        gone on shipping from the other. That is CLAUDE.md's "when you fix a rule, grep
        for every copy of it", and the copy was found by going looking for it rather than
        by anything failing.

        And it asks uncanny dodge (`rules/classfeatures.py`), which is the fix item 39
        called urgent: sneak attack keys off this answer, and the rule that stops a
        4th-level rogue ever being caught flat-footed was printed on their sheet and read
        by nothing.
        """
        from . import classfeatures

        if not classfeatures.caught_flat_footed(defender):
            # A condition somebody laid on them still counts: uncanny dodge stops you
            # being CAUGHT off guard, it does not make a `flat-footed` condition
            # somebody else applied evaporate.
            return defender.has_condition("flat-footed")
        return (
            defender.has_condition("flat-footed")
            or not self.scene.initiative
            or not self._has_acted(defender.ref)
        )

    def _gap_ft(self, actor, defender) -> float | None:
        """Feet between two creatures on the grid, or None when either is off it.

        Edge to edge, sizes included — the same measurement reach and range use, so a
        shot that is 30 feet for one rule is 30 feet for the other. One reader for
        sneak attack's 30 feet and the coup de grâce's point-blank bow.
        """
        here = self.scene.positions.get(getattr(actor, "ref", ""))
        there = self.scene.positions.get(getattr(defender, "ref", ""))
        if getattr(self.scene, "grid", None) is None or not here or not there:
            return None
        from .grid import distance_between

        return distance_between(
            tuple(here[:2]), str(getattr(actor, "size", "medium") or "medium"),
            tuple(there[:2]), str(getattr(defender, "size", "medium") or "medium"))

    def _sneak_for(self, actor, defender, weapon, *, flat_footed: bool,
                   pulled: bool = False) -> tuple[str, str]:
        """The sneak attack dice for this swing and why, or ("", why not).

        The engine's half is only the two facts `precision` cannot see for itself: how far
        apart they are standing, and whether the defender has concealment. Both are read
        from the same places the attack roll reads them, so the dice and the to-hit can
        never disagree about the board.
        """
        from . import position as position_mod, precision as precision_mod

        distance_ft = self._gap_ft(actor, defender)
        # Cover is not concealment in 1e — they are different rules with different
        # sources — but total cover means there is nothing to aim at. The rogue's bar is
        # concealment, so only what obscures counts.
        #
        # Asked as a PREFIX question, the first law: `state.hidden` covers invisibility
        # and everything else anyone hides behind later, without this line being edited
        # again. Matching "invisible" by name here is what the three-laws ratchet caught.
        concealed = bool(defender.has_state("state.hidden")
                         or position_mod.cover_of(self.scene, actor, defender) == "total")
        return precision_mod.applies(
            self.scene, actor, defender, weapon,
            flat_footed=flat_footed, distance_ft=distance_ft, concealed=concealed,
            pulled=pulled)

    def _lay_battlefield(self, sides: dict) -> None:
        """The ground. The map tray has promised "a grid is laid out when a fight
        starts" since the grid shipped, and nothing anywhere ever laid one —
        Scene.grid was assigned in tests and nowhere else, so every real fight played
        on a map that said no ground was mapped. Laid here, once, and only if the GM
        has not already put one down; combatants without positions are placed by
        their zones, the player's side on the left and everyone else a zone's worth
        of squares away. One helper for both doors a fight comes in by —
        `begin_encounter`, and the swing that auto-starts one.

        Since 2026-09-19 the ground is usually already down — `lay_the_ground` puts it
        there when the party arrives, because "a map should be displayed at all times"
        (item 28) — so this lays one only when there is none, and gets on with the part
        that is actually about a FIGHT: drawing the sides. Anybody already standing
        somewhere keeps where they were standing, which is the better fiction as well as
        the cheaper code: the man at the counter is at the counter when the brawl starts,
        not teleported into a line."""
        self.lay_the_ground(even_nowhere=True, place=False)
        if self.scene.grid is None:
            return
        from . import floorplan, places as places_mod

        # The ground the party is standing on, not a blank field. Derived from the place
        # id, so the market has the same stalls every time anybody fights in it and none
        # of it is saved. A place nobody has a shape for falls through to its terrain and
        # then to open ground, which is what every fight used to get.
        # And the world's own dimensions for the room when it wrote them: World Bible
        # ships width, depth, height, clutter, footing and a vertical kind on every place
        # it authors, and for two releases a fight in a 125-foot square was fought on
        # whatever this app's table said a room of that NAME looks like. `here()` carries
        # the authored shape; a generated or founded place carries None and derives, as
        # every place did before.
        authored = getattr(self.here(), "shape", None)
        mid = self.scene.grid.height // 2
        # A quarter of the way in, and never off the board. The literal 4 was safe while
        # every room was at least twelve squares wide; it stopped being safe the day a
        # ten-foot alley became authorable, and a PC placed at column 4 of a two-square
        # room is a PC standing in the sea. Reported from the World Bible side as "the
        # alley is gone" — their narrow-room rule had been made unreachable by this app's
        # own floor — and this is the half of that fix which is not the floor.
        pc_side, foe_row = max(1, min(4, self.scene.grid.width // 4)), 0
        # Everybody already standing somewhere keeps that square: a fight is a layer of
        # initiative over the room, not a new room. The user's ruling, 2026-09-28:
        # "people should already be in the scene which means they should already have a
        # place on the board that shouldn't change unless they move." Foundry's combat
        # tracker is the same shape — combatants are the tokens already on the canvas.
        #
        # This loop used to pop every combatant's square and lay them out afresh by
        # zone, on the theory that a zone word is a claim about the fight and an idle
        # position is not; the case behind it was a bowshot that opened at forty feet.
        # That is answered where the claim is made instead — a spawn with a stated
        # distance is placed AT that distance as it arrives (`_op_spawn`,
        # `place_by_zone(feet=...)`), so nothing here has to re-lay anybody. And the
        # re-lay did harm the other way: the man the player was standing beside was
        # moved fifteen feet off by the act of swinging at him.
        #
        # Only the unplaced are laid. With the player already on the map, from the
        # player's real square; on fresh ground, in the columns below.
        pc = self.scene.pc()
        if pc is not None and pc.ref in self.scene.positions:
            for ref in [r for refs in sides.values() for r in refs
                        if r in self.scene.actors and r not in self.scene.positions]:
                self.scene.place_by_zone([ref], feet=self.scene.spawn_feet.get(ref))
        for side, refs in sides.items():
            has_pc = any(self.scene.actors[r].is_pc for r in refs
                         if r in self.scene.actors)
            for i, ref in enumerate(refs):
                if ref in self.scene.positions or ref not in self.scene.actors:
                    continue
                zone = self.scene.zones.get(ref, "near")
                # `engaged` means within reach. Written `3 if near else 8`, the one
                # zone that means "close enough to hit" was laid out further away
                # than "near" — eight squares, forty feet, across the room.
                #
                # A distance the spawn actually asked for beats the zone word: a
                # bowshot at 120 feet is 24 squares, and the zone vocabulary has no
                # way to say anything past `far`.
                stated = self.scene.spawn_feet.get(ref)
                away = (max(1, stated // FEET_PER_SQUARE) if stated
                        else SQUARES_BY_ZONE.get(zone, 3))
                if pc_side + away >= self.scene.grid.width:
                    if authored is not None:
                        # A room the world measured is that size, and the distance gives
                        # way rather than the walls. Without this the reader would be
                        # undone by the first archer: a thirty-foot shop grew into a
                        # seventy-foot hall the moment somebody spawned at `far`, and the
                        # dimensions the export wrote would have survived exactly until a
                        # fight started in them.
                        away = max(1, self.scene.grid.width - pc_side - 2)
                    else:
                        # Ground nobody measured has no walls to argue with: a bowshot at
                        # a hundred and twenty feet is twenty-four squares, and the blank
                        # field is twenty. It grows.
                        self.scene.grid.width = pc_side + away + 2
                if has_pc:
                    self.scene.positions[ref] = self._clear_square(
                        (pc_side, mid + i), self.scene.actors[ref].size)
                else:
                    # Fanned out from the middle row rather than stacked downward:
                    # five people at one distance were laid as a column of five,
                    # "not how the people should be lined up according to the
                    # prose" (2026-09-06). Each stands at ITS OWN zone's distance —
                    # the servant beside you at one square, the hooded man at the
                    # far end at eight — and the rows alternate above and below
                    # the player's, so a crowd is a crowd and not a wall.
                    fan = (0, 1, -1, 2, -2, 3, -3, 4, -4)
                    row = mid + fan[foe_row % len(fan)] + (foe_row // len(fan))
                    self.scene.positions[ref] = self._clear_square(
                        (min(self.scene.grid.width - 1, pc_side + away),
                         max(0, min(self.scene.grid.height - 1, row))),
                        self.scene.actors[ref].size)
                    foe_row += 1
        # The bystanders — in the room, in no side — go on the board too, at their
        # own zones, so the map shows the room the prose described and not only the
        # two people hitting each other in it.
        bystanders = [r for r in self.scene.actors
                      if r not in self.scene.positions
                      and not any(r in refs for refs in sides.values())]
        if bystanders:
            self.scene.place_by_zone(bystanders)
        # The plan has raised ground in it, and until this everybody stood at level zero
        # on top of a dais they were not on.
        self.scene.settle_levels()
        self.scene.resync_zones()

    def _op_xp(self, intent: Intent, partial: dict) -> Outcome:
        """Experience awarded outright, through the one writer (`award_xp`).

        The GM's story award for a matter no fight paid, and the author's hand:
        "/cheat I gain 2000 experience" did nothing twice on 2026-09-18 because no op
        carried experience — the cheat is a plan like any other and had nothing to
        plan. The amount is a number the author or the GM states; `keep_the_authors_
        numbers` stamps a cheat's as theirs."""
        pc = self.scene.pc()
        if pc is None:
            return self._refuse(intent, "There is nobody here to award experience to.")
        try:
            amount = int(intent.params.get("amount") or 0)
        except (TypeError, ValueError):
            amount = 0
        if amount <= 0:
            return self._refuse(intent, "An experience award needs an amount above zero.")
        reason = " ".join(str(intent.params.get("reason") or "").split()) or "the GM's award"
        line = self.award_xp(pc, amount, reason).strip()
        return Outcome(intent_id=intent.id, op="xp",
                       effects=[{"ref": pc.ref, "kind": "xp", "amount": amount,
                                 "total": int(pc.xp)}],
                       tell=line, because=intent.because)

    def _op_end_encounter(self, intent: Intent, partial: dict) -> Outcome:
        """Stop the fight. The GM's call: they run, they yield, you get clear."""
        if not self.scene.in_encounter:
            return Outcome(intent_id=intent.id, op="end_encounter",
                           tell="", because=intent.because)
        standing = [self.scene.actors[r].name for r, _ in self.scene.initiative
                    if self.scene.conscious(r)]
        xp_line = self._settle_xp()
        self.scene.end_encounter()
        # The vein the guardian was sitting on, now that the guardian is not.
        xp_line += self._settle_guarded_finds()
        return Outcome(
            intent_id=intent.id, op="end_encounter",
            effects=[{"kind": "encounter", "ended": True}],
            tell="The fighting stops." + (f" Still standing: {', '.join(standing)}."
                                          if standing else "") + xp_line,
            because=intent.because,
        )

    def _settle_guarded_finds(self) -> str:
        """Pay out every booked find whose guard is dead or gone, or ""."""
        pc = self.scene.pc()
        if pc is None or not self.scene.guarded_finds:
            return ""
        kept, lines = [], []
        for g in self.scene.guarded_finds:
            guard = self.scene.actors.get(g.get("guard", ""))
            if guard is not None and not guard.is_down and guard.hp > 0:
                kept.append(g)
                continue
            got = []
            for iid, n in (g.get("found") or {}).items():
                pc.carry(iid, int(n), at_minute=self.scene.clock_minutes)
                got.append(f"{n}× {ing_mod.get(iid).name}")
            for s in g.get("stock") or []:
                pc.add_stock(crafting.Stock(base=s["base"], tier=s.get("tier", "common"),
                                            kind=s.get("kind", "ore"),
                                            craft=s.get("craft", "smithing")),
                             int(s.get("count", 1)))
                got.append(f"{s.get('count', 1)}× {s['base']}")
            lines.append(f" The {g.get('what', 'find')} is yours now: {', '.join(got)}.")
        self.scene.guarded_finds = kept
        return "".join(lines)

    def _op_give(self, intent: Intent, partial: dict) -> Outcome:
        """Something changes hands.

        One op for picking a thing up, being handed it, buying it and dropping it,
        because they are the same event with different ends attached. Either end may be
        the world: `to` alone is a gain, `from_` alone is a loss.

        Money is the same event again — a denomination is just an item whose name the
        world happens to have opinions about — so `price` is paid out of the receiver's
        purse in the same breath, and a purse that cannot cover it refuses the sale
        rather than going negative where nobody would notice.
        """
        item = str(intent.params.get("item", "")).strip()
        if not item:
            return self._refuse(intent, "Nothing was named to hand over, so nothing changes hands.")
        count = max(1, int(intent.params.get("count", 1) or 1))
        pc = self.scene.pc()

        to_ref = intent.params.get("to") or intent.target or intent.actor
        from_ref = intent.params.get("from_")
        if not to_ref and not from_ref:
            to_ref = pc.ref if pc else None
        taker = self.scene.actors.get(to_ref) if to_ref else None
        giver = self.scene.actors.get(from_ref) if from_ref else None
        # A gift is remembered. Something handed to a person by the player with no
        # price on it moves their regard (`rules/attitude.py`); recorded here, once,
        # and carried on the outcome so the log sees it. Nothing in the fiction is
        # claimed by it — the narrator gets no number.
        a_gift = (taker is not None and not taker.is_pc and giver is not None
                  and giver.is_pc and not intent.params.get("price"))

        # "merchants stuff" is not an item — measured live: the model proposed a
        # give of exactly that phrase with no giver, and the world-never-runs-out
        # branch minted it into the pack, labelled "the engine has no rules for
        # it". A bulk phrase means the whole carry: with a giver, everything they
        # hold moves; without one, there is nothing to move and the turn says so
        # instead of inventing an object called stuff.
        if re.search(r"\b(stuff|everything|belongings|wares|inventory|"
                     r"all (?:of )?(?:it|his|her|their|the) ?\w*)\b", item, re.I):
            if giver is None:
                return Outcome(
                    intent_id=intent.id, op="give", effects=[],
                    tell=(f"{item!r} is a word, not a thing. Name the item, or "
                          f"loot a body, or trade at the stall."),
                    because=intent.because)
            from .bestiary import collapse_kit
            collapse_kit(giver)
            taken: list[str] = []
            for store in (giver.goods, giver.inventory):
                for thing, n in list(store.items()):
                    if taker is not None:
                        tgt = (taker.goods if store is giver.goods
                               else taker.inventory)
                        tgt[thing] = tgt.get(thing, 0) + n
                    taken.append(f"{n} × {thing}" if n != 1 else str(thing))
                store.clear()
            for coin, n in list(giver.purse.items()):
                if taker is not None:
                    taker.purse[coin] = taker.purse.get(coin, 0) + n
                taken.append(f"{n} {coin}")
            giver.purse = {}
            return Outcome(
                intent_id=intent.id, op="give",
                effects=[{"ref": getattr(taker, "ref", ""), "kind": "took",
                          "from": giver.ref, "items": taken}],
                tell=(f"Everything {giver.name} carries changes hands: "
                      + (", ".join(taken) if taken else "nothing at all — "
                         "their hands are empty") + "."),
                because=intent.because)

        coins = goods.coinage(getattr(self, "world", None), None)
        denom = goods.coin_named(item, coins)

        paid = ""
        price = intent.params.get("price")
        if price and taker is not None:
            want = goods.coin_named(str(price).split()[-1], coins) or "gp"
            try:
                number = int(re.sub(r"\D", "", str(price)) or 0)
            except ValueError:
                number = 0
            cost_cp = number * dict(goods.DENOMINATIONS).get(want, 100)
            purse, enough = goods.spend(taker.purse, cost_cp)
            if not enough:
                return Outcome(
                    intent_id=intent.id, op="give", effects=[],
                    tell=(f"{taker.name} cannot afford {item}: "
                          f"{goods.purse_line(taker.purse, coins)} against {price}."),
                    because=intent.because,
                )
            taker.purse = purse
            paid = f" for {price}"

        moved = 0
        note = ""
        from_ground = False
        if giver is not None:
            held = (giver.purse if denom else giver.goods)
            moved = min(count, int(held.get(denom or item, 0)))
            if moved:
                held[denom or item] -= moved
                if held[denom or item] <= 0:
                    del held[denom or item]
        else:
            moved = count           # it came from the world, which never runs out
            # Unless it is lying right here with a record: then THAT thing is picked
            # up, and its owner and provenance come with it. "I pick up a chunk of
            # wood" after a sunder is the fragments of the challenger's club, his
            # still, and never a second piece of wood from nowhere.
            if taker is not None and not denom:
                rec = self.scene.prop_on_the_ground(item)
                if rec is not None:
                    # Picking a thing up is done with a hand, from where you stand
                    # (natural reach; 1e Table 7-2: a move action). A thing lying
                    # further off is walked to first — a `move`, which the refusal
                    # names — rather than taken across the room.
                    past = self.scene.within_reach(taker.ref, rec)
                    if past:
                        return self._refuse(
                            intent, f"{rec['name']} lies {past} ft beyond "
                                    f"{taker.name}'s reach. Move next to it first, then "
                                    f"pick it up.")
                    # Stooping for it provokes, and the attack of opportunity was
                    # spliced in front of this intent (`_reactions_before`): if it
                    # dropped them, the hand never closes on it — the move's rule.
                    if self.scene.in_encounter and not taker.can_act():
                        why = (taker.blocking_condition() or "down").lower()
                        return Outcome(
                            intent_id=intent.id, op="give", status="prevented",
                            effects=[{"ref": taker.ref, "kind": "pick_up_stopped",
                                      "prop": rec["name"], "why": why}],
                            tell=f"{taker.name} is {why} and never picks up "
                                 f"{self._the(str(rec.get('from_') or rec['name']))}.",
                            because=intent.because)
                    whose_rec = str(rec.get("owner") or "")
                    self.scene.hold_prop(rec["name"], taker.ref,
                                         turn=int(self.scene.clock_minutes))
                    item = rec["name"]
                    # A whole thing that was somebody's (a disarmed sap is recorded
                    # as "the thug's sap", so two thugs' saps are two records) is
                    # carried as what it IS, so it can be swung; fragments stay
                    # fragments. Picked up is in the hand: a weapon is wielded.
                    if rec.get("from_") and rec.get("state") in ("intact", "broken"):
                        item = str(rec["from_"])
                        from_ground = True
                        moved = 1           # that one thing, not `count` of them
                    whose = self.scene.actors.get(whose_rec)
                    if whose is not None and whose.ref != taker.ref:
                        note = f" — {whose.name}'s, not {taker.name}'s"
                    elif whose_rec == taker.ref and from_ground:
                        # Their own weapon, back from the ground. "The thug takes
                        # sap." was the whole tell, which says neither that it was
                        # lying there nor that it is in the hand again.
                        note = "back up off the ground; it is in hand again"

        if taker is not None and moved:
            if denom:
                taker.purse[denom] = taker.purse.get(denom, 0) + moved
            else:
                # Routed by what the thing is, so a bought sword is swingable, a bought
                # chain shirt wearable and a bought potion drinkable through the
                # machinery that already exists for each. Everything lands in `goods` as
                # well, because that is the list of what you are carrying.
                # A raw ingredient goes in the satchel, not the pack, and it goes in
                # with a timestamp. The 48 hours an animal part has were only ever
                # counted from foraging, so a gland the GM handed over across a table
                # kept forever — which made the whole spoilage rule avoidable by
                # never picking anything up yourself.
                from . import ingredients as ing_mod

                herb = ing_mod.by_name(item)
                if herb is not None:
                    # The satchel only. Everything else lands in `goods` as well
                    # because `goods` answers "what am I carrying", but the satchel
                    # answers that for ingredients — and one herb in two lists is two
                    # counts that drift the first time the pot spends from one.
                    taker.carry(herb.id, moved, at_minute=self.scene.clock_minutes)
                    return self._gave(intent, taker, giver, herb.name,
                                      moved, paid, denom)

                kind = goods.kind_of(item)
                taker.goods[item] = taker.goods.get(item, 0) + moved
                key = item.lower()
                if kind == "weapon" and key not in [w.lower() for w in taker.weapons]:
                    taker.weapons.append(key)
                if kind == "weapon" and from_ground:
                    taker.equipped = key
                elif kind == "consumable":
                    from .crafting import Stock

                    taker.add_stock(Stock(base=item, tier="common"), moved)

        what = f"{moved} × {item}" if moved != 1 else item
        if giver is not None and taker is not None:
            tell = f"{giver.name} hands {taker.name} {what}{paid}."
        elif taker is not None and note.startswith("back up"):
            tell = f"{taker.name} takes {self._the(what)} {note}."
        elif taker is not None:
            tell = f"{taker.name} takes {what}{paid}{note}."
        elif giver is not None:
            tell = f"{giver.name} parts with {what}."
            # Dropped, not vanished: the thing lies here with its record, the
            # giver's still (Inform: a dropped thing lands on the room's floor).
            if moved and not denom:
                rec = self.scene.prop_named(item)
                self.scene.place_prop(item, owner=giver.ref,
                                      from_=(rec or {}).get("from_", ""),
                                      state=(rec or {}).get("state", "intact"),
                                      turn=int(self.scene.clock_minutes))
                tell = f"{giver.name} sets down {what}; it lies here."
        else:
            tell = f"{what} changes hands."
        if giver is not None and not moved:
            tell = f"{giver.name} has no {item} to give."
        effects = [{"ref": (taker or giver).ref if (taker or giver) else "",
                    "kind": "give", "item": denom or item, "count": moved,
                    "purse": dict(taker.purse) if taker else {},
                    "goods": dict(taker.goods) if taker else {}}]
        if a_gift and moved:
            # Only once something actually changed hands. The narrator hears a step
            # crossed in words, or nothing; the log sees the numbers.
            from . import attitude as attitude_mod

            before, after = attitude_mod.nudge_regard(taker, attitude_mod.REGARD_GIFT,
                                                      "a gift")
            effects.append({"kind": "regard", "ref": taker.ref, "from": before,
                            "to": after})
            warmed = attitude_mod.regard_said(taker.name, before, after)
            if warmed:
                tell = f"{tell} {warmed}"

        return Outcome(
            intent_id=intent.id, op="give", effects=effects,
            tell=tell, because=intent.because,
        )

    def _op_use_ability(self, intent: Intent, partial: dict) -> Outcome:
        """Use a path ability, and be exact about how much of it the engine did.

        Every effect converted from the author's sentences is applied here; everything
        that stayed prose is reported as narrated. An ability that says it did nine
        things and silently did two would be worse than one that did nothing, so the
        tell counts both.
        """
        from . import leveling

        ref = intent.params.get("actor") or intent.actor
        actor = self.scene.actors.get(ref) if ref else self.scene.pc()
        if actor is None:
            raise IntentError("use_ability: nobody here to use it", "refs")

        wanted = str(intent.params.get("ability", "")).strip()
        path, found, effects = leveling.find_ability(actor, wanted)
        if not found:
            # Names the fix, not the fault: this used to print the PATHS ("Their paths
            # are blood spike") when the list the model needed was the abilities — the
            # same list the brief already computes, now from the one helper both use.
            names = leveling.usable_names(actor)
            return self._refuse(
                intent, f"{actor.name} has no ability called {wanted}. They can use: "
                        f"{', '.join(names) or 'nothing yet'}.")
        if leveling.is_passive(actor, found):
            # "Using" a passive was worse than a wasted action: Swift Strikes stood in
            # for the attack it exists to modify, and the fight went a round with no
            # to-hit rolled at all.
            #
            # A refusal, not a raise. This was an IntentError sitting twenty lines above
            # the comment that states the rule — "a hard refusal against a required op
            # is the 502 death-spiral this repo has buried four times" — and it is
            # reachable from nine ability names the shipped class file lists under its
            # own tiers. The schema may REQUIRE the op the player declared, so every
            # regeneration carried it, every one was refused, and the turn died as a
            # 502 where a sentence would have done.
            return Outcome(
                intent_id=intent.id, op="use_ability", effects=[],
                tell=(f"{found.title()} is always active — it is never used, it "
                      f"simply happens. {actor.name} attacks, and it does its work "
                      f"on the attack."),
                because=intent.because)

        # A toggle is a standing state, not a spent action. Using it again turns it
        # off, and the state lives as a clockless condition so every place that shows
        # conditions shows whether it holds — which is the whole point: the armament
        # used to be fire-and-forget with nothing on screen saying if it still held.
        #
        # An ability with a document (`paths.<path>.grants`) carries its requirements,
        # cost, modifiers, granted tags and tells as data; the engine applies them
        # here without knowing whose class they came from.
        key = leveling.toggle_key(actor, found)
        doc_path, doc = leveling.ability_doc(actor, found)
        if key:
            if actor.has_condition(key):
                self._drop_stance(actor, key, doc)
                return Outcome(
                    intent_id=intent.id, op="use_ability",
                    effects=[{"ref": actor.ref, "kind": "toggle", "state": "off",
                              "condition": key}],
                    tell=_doc_tell(doc.get("tell_off"), actor)
                         or f"{actor.name} lets the {key} fall away.",
                    because=intent.because)
            # Requirements and cost are checked before anything lands, and a failure
            # is a refusal Outcome with the reason printed — never an IntentError.
            # The schema may REQUIRE the op the player declared, and a hard refusal
            # against a required op is the 502 death-spiral this repo has buried four
            # times (see _op_forage's own post-mortem).
            refused = self._ability_refusal(actor, found, doc)
            if refused:
                return Outcome(intent_id=intent.id, op="use_ability", effects=[],
                               tell=f"Nothing takes hold. {refused}",
                               because=intent.because)
            spent = []
            cost = doc.get("cost") or {}
            if cost.get("pool"):
                paid = actor.spend_pool(str(cost["pool"]),
                                        int(cost.get("amount", 1) or 1))
                spent.append({"ref": actor.ref, "kind": "resource",
                              "pool": str(cost["pool"]),
                              "spent": paid.get("spent", 0),
                              "left": paid.get("current", 0)})
            applied = self._apply_ability_document(actor, found, key, doc_path, doc)
            return Outcome(
                intent_id=intent.id, op="use_ability",
                effects=[{"ref": actor.ref, "kind": "toggle", "state": "on",
                          "condition": key}] + spent + applied["effects"],
                tell=_doc_tell(doc.get("tell"), actor)
                     or f"{actor.name} forms the {key}."
                        + (" " + applied["said"] if applied["said"] else ""),
                because=intent.because)
        if not effects:
            tier = leveling.tier_needed(actor, wanted)
            return Outcome(
                intent_id=intent.id, op="use_ability", effects=[],
                tell=(f"{found.title()} is a Control Blood {tier} ability of the "
                      f"{path} path; {actor.name} has reached "
                      f"{leveling.control_blood_for(actor, path)}."),
                because=intent.because)

        target = self.scene.actors.get(intent.params.get("to") or "") or actor
        done, narrated, rolls = [], [], []
        # Everyone this ability actually hurt, so the hit-point ladder runs on them at
        # the end. It never did: measured, a level-12 blood bender's Blood Spike
        # Projectile took a thug to -22 of 13 against Constitution 13 — nine hit points
        # past the death line — and wrote no condition at all. Not dead, not dying, not
        # unconscious. An ability that deals damage could not kill anybody, and the
        # non-lethal cost could not knock its own user out either.
        hurt: list[str] = []
        for spec in effects:
            if spec.get("inactive"):
                continue
            kind = spec.get("type")
            if kind == "damage" and spec.get("lethality") == "nonlethal":
                roll = self.dice.roll(str(spec["dice"]), label=f"{found}: the cost",
                                      visibility="player")
                rolls.append(roll)
                actor.take_nonlethal(roll.total)
                hurt.append(actor.ref)
                done.append(f"{actor.name} pays {roll.total} non-lethal")
            elif kind == "damage":
                # Never at the user by default. Half these abilities are areas —
                # Hemorrhagic Eruption detonates pools "in a 10-ft radius" — and
                # falling back to the actor had the bender blowing themselves up for
                # 21 and ending the demonstration at -1 hit points.
                if not intent.params.get("to"):
                    narrated.append("damage with nobody named")
                    continue
                roll = self.dice.roll(str(spec.get("dice", "0")), label=found,
                                      visibility="player")
                rolls.append(roll)
                target.take_damage(roll.total, spec.get("damage_type", "untyped"))
                hurt.append(target.ref)
                done.append(f"{roll.total} damage to {target.name}")
            elif kind == "heal":
                roll = self.dice.roll(str(spec["dice"]), label=found,
                                      visibility="player")
                rolls.append(roll)
                if spec.get("lethality") == "nonlethal":
                    actor.heal_nonlethal(roll.total)
                    done.append(f"{roll.total} non-lethal healed")
                else:
                    done.append(f"{actor.heal(roll.total)} hit points healed")
            elif kind == "temp_hp":
                roll = self.dice.roll(str(spec["dice"]), label=found,
                                      visibility="player")
                rolls.append(roll)
                actor.gain_temp_hp(roll.total, spec.get("source") or found)
                done.append(f"{roll.total} temporary hit points")
            elif kind == "damage_reduction":
                done.append(f"DR {spec.get('amount')}/{spec.get('bypass') or '—'}")
            elif kind == "combat_mod":
                done.append(f"{int(spec.get('amount', 0)):+d} "
                            f"{spec.get('target', 'attack')}")
            elif kind == "apply_condition":
                done.append(f"{target.name} may become {spec.get('target')}")
            elif spec.get("op") == "blood_pool":
                where = self.scene.positions.get(actor.ref)
                self.scene.pools.append(BloodPool(owner=actor.ref, at=where, place=self.scene.at,
                                                  source=found))
                done.append("blood on the ground")
            elif spec.get("op") == "spend_pools":
                mine = [b for b in self.scene.pools if b.owner == actor.ref and b.here(self.scene)]
                take = len(mine) if str(spec.get("count")) == "all"                     else min(len(mine), int(spec.get("count", 1) or 1))
                for pool in mine[:take]:
                    self.scene.pools.remove(pool)
                done.append(f"{take} pool{'s' if take != 1 else ''} spent")
            else:
                narrated.append(kind)

        crossed = []
        for ref in dict.fromkeys(hurt):
            crossed.extend(self._hp_state_effects(self.scene.actors[ref]))

        bits = [f"{actor.name} uses {found.title()}."]
        if done:
            bits.append("The engine resolves: " + "; ".join(done) + ".")
        if narrated:
            bits.append(f"{len(narrated)} part(s) of it are yours to narrate.")
        return Outcome(
            intent_id=intent.id, op="use_ability", rolls=rolls,
            effects=[{"ref": actor.ref, "kind": "use_ability", "ability": found,
                      "path": path, "resolved": len(done), "narrated": len(narrated),
                      "origin": f"ability:{path}/{found}"}]
                    + crossed,
            tell=" ".join(bits) + self._hp_state_tell(crossed),
            because=intent.because,
        )

    def _refuse(self, intent: Intent, why: str, *, code: str = "", for_a_person: str = "",
                fix: dict | None = None) -> Outcome:
        """A refusal the player could not have foreseen, as a printable Outcome.

        The design contract's rule, made into one door: a refusal whose reason the
        player had no way to know is a sentence in the transcript, never a raised
        error. Inform's `check` rulebook is the model — an action that cannot happen
        prints why and stops, and the story never errors; "You aren't holding that"
        is prose, not a traceback.

        Stage 7 measured what a raise here actually cost. `_advance` catches a
        resolution-time raise ONCE, returns HTTP 502 with the raw engine string, and
        pops the player's own sentence from the transcript. There is no retry: these
        fire during `run()`, after `validate()` has passed, so the five-attempt schedule
        never sees them. The plan of record classified twenty-two of these raises as
        "correct — the model can name another item", and that is true at validate time
        and false here, where nobody is listening. Every resolution-time refusal now
        comes through this door; where the check is cheap it is ALSO made at validate
        time, so the model gets its retry with the list in hand.

        `effects=[]` and a tell, which is what fifteen refusals already looked like;
        this only gives the shape a name. The tell is a fact the narrator dresses, and
        the claims scrubber will not let prose claim the thing that did not happen.

        `code`, `for_a_person` and `fix` are the refusal's one payload
        (docs/fix-interfaces.md §2.6), the same three an `IntentError` carries. No
        caller passes them yet — the lanes place the codes — and an uncoded refusal is
        the same ten keys it always was.
        """
        # `status="refused"`, so a reader can tell a refusal from an outcome that
        # happened and simply changed nothing. `cards.touch_from_outcomes` needs to:
        # "X is already a quest on the table" landed on the quest's card as its first
        # FACT (2026-09-23), and a test double with no effects is not a refusal.
        return Outcome(intent_id=intent.id, op=intent.op, status="refused", effects=[],
                       tell=" ".join(str(why).split()), because=intent.because,
                       code=code, for_a_person=for_a_person, fix=fix)

    def _ability_refusal(self, actor: Actor, found: str, doc: dict) -> str:
        """Why this ability cannot be used right now, as a printable sentence — or "".

        Requirements are tag queries against the one vocabulary, and the answer is a
        graceful refusal in the untrained-check / busy-forage shape: the reason is
        something the player could not have known, so it is printed, not raised.
        """
        for q in doc.get("requires") or ():
            if not actor.has_state(str(q)):
                return (f"{found.title()} needs {q} to hold on {actor.name}, "
                        f"and it does not.")
        for q in doc.get("requires_not") or ():
            if actor.has_state(str(q)):
                return f"{found.title()} cannot be used while {q} holds on {actor.name}."
        cost = doc.get("cost") or {}
        if cost.get("pool"):
            pool = actor.pool(str(cost["pool"]))
            need = int(cost.get("amount", 1) or 1)
            if pool is None or pool.current < need:
                have = 0 if pool is None else pool.current
                return (f"{found.title()} costs {need} from the {cost['pool']} pool "
                        f"and {actor.name} has {have}.")
            if not pool.ready:
                return (f"The {cost['pool']} pool recharges in {pool.cooldown_left} "
                        f"round{'' if pool.cooldown_left == 1 else 's'}.")
        return ""

    def _apply_ability_document(self, actor: Actor, found: str, key: str,
                                path: str, doc: dict) -> dict:
        """Apply a document's standing half: one ActiveEffect through the one
        applicator, plus any temporary hit points it banks. Returns the effect
        records and a sentence for the tell."""
        from . import leveling, states

        effects: list[dict] = []
        said: list[str] = []

        mods: list[dict] = []
        for spec in doc.get("modifiers") or ():
            r = leveling.resolve_effect(dict(spec), actor, path)
            if r.get("inactive"):
                continue
            amount = int(r.get("amount", 0) or 0)
            if not amount:
                continue
            mods.append({"kind": str(r.get("type") or "combat_mod"),
                         "target": str(r.get("target") or ""),
                         "amount": amount,
                         "bonus_type": str(r.get("bonus_type") or "untyped")})
            said.append(f"{amount:+d} {r.get('target')}")

        tags = tuple(states.tags_for(key)) if key else ()
        tags += tuple(str(t) for t in (doc.get("tags") or ())
                      if str(t) not in tags)
        periodic = []
        drain = doc.get("drain") or {}
        if drain.get("pool"):
            periodic.append({"spend_pool": str(drain["pool"]),
                             "amount": int(drain.get("amount", 1) or 1),
                             "or_ends": True})
        payload = {}
        if isinstance(doc.get("weapon"), dict):
            payload["weapon"] = dict(doc["weapon"])
        if isinstance(doc.get("resist"), dict):
            # Percent resistance, tier-scaled like everything else — Blood Rage
            # Armor's 50% arrives at the rung the class file says, not before.
            r = leveling.resolve_effect(dict(doc["resist"]), actor, path)
            pct = int(r.get("percent", 0) or 0)
            if pct > 0 and not r.get("inactive"):
                against = str(r.get("against", "physical") or "physical")
                payload["resist"] = {"against": against, "percent": pct}
                said.append(f"{pct}% resistance to {against} damage")

        actor.apply_effect(ActiveEffect(
            name=found.title(), kind="condition", key=key, source=found.title(),
            origin=f"ability:{path}/{found}",
            tags=tags, modifiers=mods, payload=payload, periodic=periodic))
        if mods:
            effects.append({"ref": actor.ref, "kind": "stance", "ability": found,
                            "modifiers": list(mods)})

        temp = doc.get("temp_hp") or {}
        if temp:
            r = leveling.resolve_effect(dict(temp), actor, path)
            per_hd = int(r.get("per_hit_die", 0) or 0)
            amount = per_hd * actor.hit_dice
            if amount > 0 and not r.get("inactive"):
                got = actor.gain_temp_hp(amount, source=found.title(),
                                         origin=f"ability:{path}/{found}")
                effects.append({"ref": actor.ref, "kind": "temp_hp",
                                "temp_hp": actor.temp_hp, **got,
                                "origin": f"ability:{path}/{found}"})
                said.append(f"{amount} temporary hit points "
                            f"({per_hd} per Hit Die)")
        return {"effects": effects,
                "said": ("It carries " + ", ".join(said) + "." if said else "")}

    def _drop_stance(self, actor: Actor, key: str, doc: dict) -> None:
        """The other half of the applicator: removal evaporates everything the
        document granted — modifiers, tags, and the temporary hit points that were
        the stance's and not the character's."""
        eff = next((e for e in actor.effects
                    if e.kind == "condition" and e.key == key), None)
        source = eff.source if eff else ""
        actor.remove_condition(key)
        if (doc.get("temp_hp") or {}) and source:
            actor.clear_temp_hp(source=source)

    def _op_blood_pool(self, intent: Intent, partial: dict) -> Outcome:
        """Put blood on the ground.

        Where matters when there is a map and does not when there is not, so `at` is
        taken if given, otherwise the pool lands under whoever it came out of. That is
        also what the abilities say: Blood Pool Manifestation puts one "in the target's
        square (or your square if self)".
        """
        ref = intent.params.get("actor") or intent.actor
        actor = self.scene.actors.get(ref) if ref else self.scene.pc()
        if actor is None:
            raise IntentError("blood_pool: nobody here to bleed", "refs")

        where = intent.params.get("at")
        onto = intent.params.get("to")
        if where is None:
            landed_on = onto if onto in self.scene.positions else actor.ref
            where = self.scene.positions.get(landed_on)
        amount = max(1, int(intent.params.get("amount", 1) or 1))
        made = BloodPool(owner=actor.ref, place=self.scene.at, at=tuple(where) if where else None,
                         amount=amount, source=str(intent.params.get("source") or
                                                   intent.because or ""))
        self.scene.pools.append(made)

        return Outcome(
            intent_id=intent.id, op="blood_pool",
            effects=[{"ref": actor.ref, "kind": "blood_pool", **made.as_dict(),
                      "pools": len(self.scene.pools)}],
            tell=(f"A pool of {actor.name}'s blood spreads"
                  + (f" at {where[0]},{where[1]}." if where else " underfoot.")),
            because=intent.because,
        )

    def _op_spend_pools(self, intent: Intent, partial: dict) -> Outcome:
        """Take pools back off the ground: siphoned, detonated, stepped through.

        One op for all of them because the *spending* is the shared mechanic — what
        each ability does with the blood is its own effect, resolved by its own intent.
        `count` may be "all": Hemorrhagic Eruption detonates any number at once, and a
        cap this op invented would be a rule nobody wrote.
        """
        ref = intent.params.get("actor") or intent.actor
        actor = self.scene.actors.get(ref) if ref else self.scene.pc()
        mine = [b for b in self.scene.pools
                if (actor is None or b.owner == actor.ref) and b.here(self.scene)]
        want = intent.params.get("count", 1)
        take = len(mine) if str(want).lower() == "all" else max(1, int(want or 1))
        spent = mine[:take]

        if not spent:
            return Outcome(intent_id=intent.id, op="spend_pools", effects=[],
                           tell="There is no blood on the ground to use.",
                           because=intent.because)
        for pool in spent:
            self.scene.pools.remove(pool)
        why = str(intent.params.get("why") or intent.because or "").strip()
        return Outcome(
            intent_id=intent.id, op="spend_pools",
            effects=[{"ref": actor.ref if actor else "", "kind": "spend_pools",
                      "spent": len(spent), "left": len(self.scene.pools)}],
            tell=(f"{len(spent)} pool{'s' if len(spent) != 1 else ''} of blood "
                  f"{'are' if len(spent) != 1 else 'is'} used up"
                  + (f" — {why}." if why else ".")),
            because=intent.because,
        )

    def _op_wear(self, intent: Intent, partial: dict) -> Outcome:
        """Put on something you are carrying, and let it reach the numbers.

        Refused for anything not actually held: an inventory that can be worn without
        being owned is a sheet that claims protection nobody bought.
        """
        item = str(intent.params.get("item", "")).strip()
        ref = intent.params.get("actor") or intent.actor or (
            self.scene.pc().ref if self.scene.pc() else None)
        actor = self.scene.actors.get(ref) if ref else None
        if actor is None:
            raise IntentError("wear: nobody here to wear it", "refs")

        key = item.lower()
        carried = {k.lower() for k in actor.goods} | {w.lower() for w in actor.weapons}
        if key not in carried:
            return Outcome(intent_id=intent.id, op="wear", effects=[],
                           tell=f"{actor.name} is not carrying {item}.",
                           because=intent.because)

        kind = goods.kind_of(item)
        before = actor.ac()
        if kind == "armour":
            actor.armour = key
        elif kind == "shield":
            actor.shield = key
        elif kind == "weapon":
            actor.equipped = key
        else:
            return Outcome(intent_id=intent.id, op="wear", effects=[],
                           tell=f"{item} is not something that can be worn or wielded.",
                           because=intent.because)

        after = actor.ac()
        moved = f" Armour class {before} to {after}." if after != before else ""
        return Outcome(
            intent_id=intent.id, op="wear",
            effects=[{"ref": actor.ref, "kind": "wear", "item": key, "ac": after}],
            tell=(f"{actor.name} {'draws' if kind == 'weapon' else 'puts on'} "
                  f"the {item}.{moved}"),
            because=intent.because,
        )

    def _gave(self, intent, taker, giver, what, moved, paid, denom) -> Outcome:
        """The outcome for a handover that has already been applied.

        Shared because an ingredient returns early — it goes to the satchel and must
        not also land in `goods` — and the tell it deserves is the same one everything
        else gets.
        """
        thing = f"{moved} × {what}" if moved != 1 else what
        if giver is not None and taker is not None:
            tell = f"{giver.name} hands {taker.name} {thing}{paid}."
        elif taker is not None:
            tell = f"{taker.name} takes {thing}{paid}."
        else:
            tell = f"{thing} changes hands."
        return Outcome(
            intent_id=intent.id, op="give",
            effects=[{"ref": (taker or giver).ref if (taker or giver) else "",
                      "kind": "give", "item": denom or what, "count": moved,
                      "satchel": dict(taker.inventory) if taker else {}}],
            tell=tell, because=intent.because,
        )

    def _op_rest(self, intent: Intent, partial: dict) -> Outcome:
        """Sleep it off. Natural healing, CRB p.191.

        Everyone in the scene who is not hostile rests — in practice the PC, since the
        GM's people are not on the sheet. The clock moves, conditions expire, and the
        wounded wake up better than they went to bed, which is the only way a campaign
        survives its first real fight.
        """
        kind = intent.params.get("kind", "night")
        who = intent.actor or (self.scene.pc().ref if self.scene.pc() else None)
        actor = self.scene.actors.get(who) if who else None
        if actor is None:
            raise IntentError("rest: nobody here to rest", "refs")
        talking = self.talking_to()
        if talking and actor.is_pc:
            return self._refuse(
                intent, f"You are mid-sentence with "
                        f"{', '.join(a.name for a in talking)}. Take your leave first.")

        # Sleeping on enough experience is how a level arrives: "once i have enough
        # Exp sleeping should initiate the leveling process." Before the rest itself,
        # so the new hit die is part of the night's recovery rather than after it.
        levelled = None
        from . import leveling as leveling_mod
        from . import xp as xp_mod

        if kind == "night" and actor.is_pc and xp_mod.ready_to_level(actor):
            levelled = leveling_mod.level_up(actor, dice=self.dice)

        result = actor.rest(kind)
        refilled = actor.refresh_pools("rest.night", self.dice)
        # The morning's preparation (item 21.4): what was not cast is still prepared, and
        # the empty slots refill from the player's last loadout — or, for a wizard who has
        # never prepared, from the book in its own order. A cleric with nothing chosen is
        # left empty and told so (owner, Q39). No study hour is added (Q40): the night
        # already runs to dawn.
        prep_said = ""
        if casting.is_caster(actor):
            got = casting.ensure_prepared(actor, reason="rest")
            prep_said = casting.prepared_said(actor, got)
        hours = result["hours"]
        # Everyone, not only the sleeper. Rest ticked the resting actor alone, so an
        # NPC standing in the same scene kept every timed buff through an eight-hour
        # night. `advance` also leaves the body alone: `Actor.rest` has already called
        # survival.sleep, and a night deliberately costs no food or water.
        # `charge_body=False`: `Actor.rest` has already called survival.sleep, and a
        # night deliberately costs no food or water — pinned by tests/test_survival.py.
        # A night's sleep begun in the evening runs to the morning, not to a fixed eight
        # hours. Measured live 2026-09-27: "I find somewhere to sleep until morning" at
        # five in the afternoon woke the party at one in the morning, the prose wrote "the
        # morning sun has just begun to bleed through", and the market it walked into
        # next — shut until first light (rules/keepers.py) — was written trading. The
        # rules' eight hours are the least a night is; the next dawn ends it when it is
        # later than that and within sixteen.
        minutes = hours * 60
        if kind == "night":
            now = self.scene.clock_minutes
            dawn = (now // (24 * 60)) * 24 * 60 + 6 * 60
            if dawn <= now:
                dawn += 24 * 60
            if now + minutes < dawn <= now + 16 * 60:
                minutes = dawn - now
                hours = round(minutes / 60)
        ended = self.scene.advance(minutes, charge_body=False)["ended"]

        bits = [f"{actor.name} rests for {hours} hours."]
        if result["healed"]:
            bits.append(f"{actor.name} recovers {result['healed']} hit points "
                        f"({actor.hp}/{actor.hp_max}).")
        elif actor.hp >= actor.hp_max:
            bits.append(f"{actor.name} was already unhurt.")
        if result["woke"]:
            bits.append(f"{actor.name} is on their feet again.")
        if refilled:
            bits.append("Recovered: " + ", ".join(refilled) + ".")
        if ended:
            bits.append("Ended: " + ", ".join(ended) + ".")
        if prep_said:
            bits.append(prep_said)

        return Outcome(
            intent_id=intent.id, op="rest",
            effects=[{"ref": actor.ref, "kind": "rest", "healed": result["healed"],
                      "hours": hours, "hp_after": actor.hp, "origin": "rule:rest"}],
            tell=" ".join(bits)
                 + (f" In the night, level {levelled['level']} settles: "
                    f"+{levelled['hp']} hp"
                    f"{', ' + ', '.join(levelled['grants']) if levelled['grants'] else ''}."
                    if levelled and levelled.get("ok") else ""),
            because=intent.because,
        )

    def _op_eat(self, intent: Intent, partial: dict) -> Outcome:
        """A meal. Resets the hunger clock and nothing else — food is not medicine."""
        from . import survival

        actor = self._eater(intent)
        survival.eat(actor)
        return Outcome(
            intent_id=intent.id, op="eat",
            effects=[{"ref": actor.ref, "kind": "eat"}],
            tell=f"{actor.name} eats.", because=intent.because,
        )

    def _op_drink(self, intent: Intent, partial: dict) -> Outcome:
        from . import survival

        actor = self._eater(intent)
        survival.drink(actor)
        return Outcome(
            intent_id=intent.id, op="drink",
            effects=[{"ref": actor.ref, "kind": "drink"}],
            tell=f"{actor.name} drinks.", because=intent.because,
        )

    def _eater(self, intent: Intent):
        """Who the meal is for: the named actor, or the PC — the only creature whose
        hunger the survival rules track in practice."""
        who = intent.actor or intent.params.get("actor") \
            or (self.scene.pc().ref if self.scene.pc() else None)
        actor = self.scene.actors.get(who) if who else None
        if actor is None:
            raise IntentError(f"{intent.op}: nobody here to {intent.op}", "refs")
        return actor

    def _op_spawn(self, intent: Intent, partial: dict) -> Outcome:
        from .bestiary import split_collective_name

        # "pair of guards" is two guards, not one creature with a plural name —
        # measured live as a single 11-hp actor the scene panel called a pair.
        count = int(intent.params.get("count", 1))
        name = intent.params.get("name")
        if name:
            in_name, singular = split_collective_name(str(name))
            if in_name > 1:
                count, name = max(count, in_name), singular
        made = self._bring_in(
            intent.params["template"], count=count, name=name,
            from_entity_id=intent.params.get("from_entity_id"),
        )
        # The player's word is honoured (item 5.3 of the 2026-09-28 playtest): "girl"
        # spawned c2 as they/them, race human, with an Orc face and an old man's years.
        if name and not intent.params.get("from_entity_id"):
            from . import person_words

            person_words.honour_spawn(self.scene, self.world, made, str(name))
        # How close they arrive. Without this everything spawned defaulted to `near`,
        # which `begin_encounter` lays out three squares off — and a tavern brawl the
        # player started by swinging opened with the man they punched standing fifteen
        # feet away, out of reach of the attack that started it.
        # An exact distance beats a zone word. "I shoot him with my bow at 120 feet" is a
        # fact about the fight, and rounding it to `near` — three squares, fifteen feet —
        # makes a nonsense of the weapon. The default map is 20x20, a hundred feet
        # square, so a bowshot does not fit on it and the board grows to hold one.
        feet = intent.params.get("distance_ft")
        zone = str(intent.params.get("zone") or "").strip().lower()
        if feet or zone in ("engaged", "near", "far"):
            for m in made:
                if feet:
                    self.scene.zones[m["ref"]] = zone_for_feet(int(feet))
                    self.scene.spawn_feet[m["ref"]] = int(feet)
                else:
                    self.scene.zones[m["ref"]] = zone
                # A zone set after the layout has already run has to move them too.
                self.scene.positions.pop(m["ref"], None)
            if self.scene.grid is not None and self.scene.positions:
                self.scene.place_by_zone([m["ref"] for m in made],
                                         feet=int(feet) if feet else None)
        return Outcome(
            intent_id=intent.id, op="spawn",
            effects=[{"kind": "spawn", "actors": made}],
            tell="On the board: " + ", ".join(f"{m['name']} ({m['ref']})" for m in made) + ".",
            because=intent.because,
        )

    def _op_introduce(self, intent: Intent, partial: dict) -> Outcome:
        """People enter the scene because the plan says so, before the prose is written.

        docs/declared-not-guessed.md: until this, new people came into existence because
        a regex read them out of the finished prose (`note_cast` → `promote_cast`), and
        its misfires — the phantom elder out of "the elder-quarter" inside a quote, a
        second old man booked beside the opening's own — were people nobody declared.
        Labyrinth (arXiv 2409.06949) measured the same choice: letting the model rewrite
        state from its dialogue was the worst approach it tried.

        `already_here` asks the scene first: somebody standing here who answers to these
        words — an actor, or a glimpse the population already holds (`population.find`)
        — IS that person, and the placeholder binds to them. `arrives` is a newcomer by
        definition. Either way nobody enters the initiative: a person introduced mid-scene
        is a bystander until they act or are acted on (item 18's ruling).
        """
        from . import population

        who = intent.params["who"]
        # "I ask her name." came back as `introduce who="her name"` (live, 2026-09-27).
        if not population.names_a_person(who):
            return self._refuse(
                intent, f"introduce brings in a PERSON, and {who!r} is not somebody. "
                        f"Asking a name, a price or a question of somebody here is `say` "
                        f"to them, or narrate_only.")
        n = int(intent.params.get("count", 1) or 1)
        how = intent.params.get("how") or "already_here"
        template = intent.params.get("template") or "guildhand"
        zone = str(intent.params.get("zone") or "near").strip().lower()
        zone = zone if zone in ("engaged", "near", "far") else "near"
        placeholders = list(intent.params.get("placeholders") or [])
        made, bound = [], {}
        for k in range(n):
            actor = None
            if how == "already_here" and n == 1:
                actor = self._already_here(who)
            if actor is None:
                # A glimpse here with no body yet is who "already here" means; a record
                # that already has a body here is somebody else's, and a newcomer or the
                # second of several is always somebody new.
                rec = (population.here_as(self.scene, who)
                       if how == "already_here" and n == 1 else None)
                if rec is not None and rec.get("ref") in self.scene.actors:
                    rec = None
                if rec is None:
                    rec = population.note(self.scene, who, fresh=True)
                actor = population.embody(self.scene, who, template, zone=zone,
                                          world=self.world, rec=rec)
                made.append({"ref": actor.ref, "name": actor.name})
            if k < len(placeholders):
                bound[placeholders[k]] = actor.ref
        here = [f"{self.scene.actors[r].name} ({r})" for r in bound.values()] or \
               [f"{m['name']} ({m['ref']})" for m in made]
        return Outcome(
            intent_id=intent.id, op="introduce",
            effects=[{"kind": "introduce", "actors": made, "bound": bound,
                      "who": who, "how": how}],
            tell="In the scene: " + ", ".join(here) + ".",
            because=intent.because,
        )

    def _already_here(self, who: str):
        """The one person standing here these words fit, or None: an actor whose name
        or population record answers to every word (`population.find` does both)."""
        from . import population

        found = population.find(self.scene, who, rings=(population.HERE,), log_miss=False)
        if found.scope == population.HERE:
            ref = found.people[0].get("ref")
            if ref and ref in self.scene.actors:
                return self.scene.actors[ref]
        words = population._tokens(who)
        fits = [a for a in self.scene.actors.values()
                if not a.is_pc and words
                and population._fits(words, set(population._tokens(a.name)))]
        return fits[0] if len(fits) == 1 else None

    def _bring_in(self, template: str, count: int = 1, name: str | None = None,
                  from_entity_id: str | None = None, side: str = "") -> list[dict]:
        """Put creatures on the board. The one path a creature arrives by.

        Pulled out of `_op_spawn` so the `summon` effect type routes through it rather
        than growing a creature system of its own. A summoning spell and a GM saying "two
        bravos step out of the dark" are the same event with different fiction attached,
        and the initiative bookkeeping below is the part that is easy to forget and
        expensive to get wrong twice.
        """
        from .bestiary import instantiate  # local import: bestiary is data, not core

        made = []
        # A crowd arrives as ONE actor with the combined hit points of its members — the
        # troop (item 33, 2026-09-19). Five and up, because below that they arrive as
        # themselves and `split_collective_name`'s ruling about a pair of guards still
        # holds. A named individual is never a unit: "Drenn Ironvale" times eight is eight
        # of somebody, which is not a thing the fiction ever means.
        if int(count) >= troops_mod.UNIT_FROM and not from_entity_id:
            unit = troops_mod.form(template, int(count), scene=self.scene, name=name or "")
            self.scene.add(unit)
            made.append({"ref": unit.ref, "name": unit.name,
                         "members": int(unit.troop.members)})
            if self.scene.in_encounter:
                init = self.dice.d20(unit.initiative_modifiers(),
                                     label=f"{unit.name} initiative", visibility="hidden")
                # This branch adjusted `turn` not at all: a troop that rolled high took
                # the turn straight out of whoever's hand it was in.
                self.scene.enrol(unit.ref, init.total)
                self.scene.sides.setdefault(
                    side or ("pc" if unit.is_pc else "them"), []).append(unit.ref)
            return made
        for n in range(max(1, int(count))):
            actor = instantiate(template, scene=self.scene, name=name,
                                world_entity_id=from_entity_id, index=n)
            self.scene.add(actor)
            # A true name behind a descriptor, and a face, from the world's pools
            # (rules/names.py); a resident keeps their own name and their own
            # Appearance fact. Nothing here reaches the panel until given in play.
            if self.world is not None:
                from . import names as names_mod

                if from_entity_id:
                    actor.appearance = names_mod.resident_appearance(self.world,
                                                                     from_entity_id)
                    actor.true_name = actor.name
                elif not actor.true_name and _a_person(
                        getattr(actor, "from_template", "") or template):
                    taken = [a.true_name for a in self.scene.actors.values()
                             if getattr(a, "true_name", "")]
                    taken += [a.name for a in self.scene.actors.values()]
                    actor.true_name = names_mod.true_name(
                        self.world, self.scene.location_id, actor.ref, taken)
                    if not actor.appearance:
                        actor.appearance = names_mod.appearance_for(
                            self.world, self.scene.location_id, ref=actor.ref)
            made.append({"ref": actor.ref, "name": actor.name})
            # Someone who arrives mid-fight rolls in. Without this they were on the
            # board but not in the order, so they never took a turn and the fight could
            # not end — `sides_standing` never counted them either.
            if self.scene.in_encounter:
                init = self.dice.d20(actor.initiative_modifiers(),
                                     label=f"{actor.name} initiative", visibility="hidden")
                # `enrol`: the index this re-pointed was read after the sort, so it
                # "kept" whoever the sort had just moved into the slot.
                self.scene.enrol(actor.ref, init.total)
                # A summoned creature fights for whoever called it. Without the `side`
                # argument every arrival joined "them", so a caster's own celestial dog
                # counted against them and a fight could not end while it was standing.
                self.scene.sides.setdefault(
                    side or ("pc" if actor.is_pc else "them"), []
                ).append(actor.ref)
        return made

    # --- helpers ------------------------------------------------------------------------

    def _roll_or_suspend_stage(
        self, intent: Intent, actor: Actor, mods: list[Modifier], label: str,
        dc: int | None, partial: dict, state: dict, notation: str,
        state_key: str = "attack_state",
    ) -> Roll:
        """One stage of a multi-stage intent: roll it, or hand it to the player and stop.

        Unlike `_roll_or_suspend` this carries the accumulated `state` into the
        suspension, so an attack that has already rolled to-hit does not roll it again
        when the player comes back to roll damage.

        `state_key` names the slot the state is parked in across the round trip. It
        defaults to the attack's so every existing caller is unchanged; `cast` passes its
        own, because a cast has already spent a spell slot by the time it first suspends
        and reading a half-finished attack back into it would spend a second one.

        `actor` is whoever *makes* this roll, which is not always the intent's actor: a
        cast rolls the caster's damage and then each target's saving throw, and the popup
        must only ever open for a roll the player is entitled to make.
        """
        if intent.visibility == "player" and actor.is_pc:
            if "player_face" in partial:
                face = partial.pop("player_face")
                return self.dice.given_total(face, notation, mods, label=label)
            count, faces, _ = self.dice.parse(notation)
            raise _NeedsPlayerRoll(
                {
                    "label": label,
                    "die": notation,
                    "actor": actor.name,
                    "min": count,
                    "max": count * faces,
                    "modifier": sum(m.value for m in mods),
                    "breakdown": [m.as_dict() for m in mods],
                    "dc": dc,
                    "because": intent.because,
                    "intent_id": intent.id,
                },
                {state_key: state},
            )
        return self.dice.roll(notation, mods, label=label, visibility=intent.visibility)

    def _roll_or_suspend(
        self, intent: Intent, actor: Actor, mods: list[Modifier], label: str,
        dc: int, partial: dict, extra_partial: dict | None = None,
        dc_shown: bool = True,
    ) -> Roll:
        """Roll it, or hand it to the player and stop.

        The player rolls their own; everything else the engine rolls and hands to the GM
        as a fact. That is the architecture decision, enforced in one place.
        """
        if intent.visibility == "player" and actor.is_pc:
            if "player_face" in partial:
                return self.dice.given(partial["player_face"], mods, label=label)
            prompt = {
                "label": label,
                "die": "1d20",
                "actor": actor.name,
                "min": 1,
                "max": 20,
                "modifier": sum(m.value for m in mods),
                "breakdown": [m.as_dict() for m in mods],
                "dc": dc,
                # Whether the number may be shown. The popup carried it as a bare int
                # with no provenance, so the browser could not tell a difficulty the
                # player is entitled to know from the result of a die already rolled in
                # secret — and printed both as "beat: N".
                "dc_shown": bool(dc_shown),
                "because": intent.because,
                "intent_id": intent.id,
            }
            raise _NeedsPlayerRoll(prompt, dict(extra_partial or {}))
        return self.dice.d20(mods, label=label, visibility=intent.visibility)

    def _apply_damage(self, target: Actor, amount: int, dtype: str,
                      traits: tuple[str, ...] = (),
                      lethality: str = "lethal") -> dict:
        """One funnel for every point of damage in the game.

        Everything — weapon hits, the `damage` op, hazards — arrives here, which is what
        makes damage reduction, temporary hit points and now interception a single change
        rather than one per damage source.

        Returns the effect for whoever ended up taking the *largest* share, and hangs the
        rest off it. Every caller of this has always read one effect back, and a blow that
        split in two must not silently become invisible to the ones that did not change.
        """
        landed = self._intercept(target, amount, dtype, traits, lethality)
        if not landed:
            return {"ref": target.ref, "kind": "damage", "amount": 0, "rolled": amount,
                    "type": normalise_damage_type(dtype), "reduced": 0, "reduced_by": "",
                    "absorbed": 0, "hp_after": target.hp, "hp_max": target.hp_max,
                    "temp_hp": target.temp_hp, "lethality": lethality,
                    "nonlethal": target.nonlethal, "note": "stopped before it landed"}

        effects = [self._land(pk) for pk in landed]
        effects.sort(key=lambda e: e["amount"], reverse=True)
        head, rest = effects[0], effects[1:]
        if rest:
            head["also"] = rest
        return head

    def _intercept(self, target: Actor, amount: int, dtype: str,
                   traits: tuple[str, ...], lethality: str) -> list[Packet]:
        """Offer a blow to anybody standing in front of it, before anything else touches it.

        Before damage reduction and temporary hit points, deliberately: a blow redirected
        to somebody else has to meet *that* creature's armour, and resolving DR first would
        apply the wrong person's.
        """
        packet = Packet(amount=max(0, int(amount)), dtype=dtype, traits=tuple(traits),
                        lethality=lethality, target=target.ref)
        if not self.scene.guards:
            return [packet]
        return guards_mod.intercept(self.scene, packet)

    def _land(self, pk: Packet) -> dict:
        # The store, not the here-view: a body in another room is still somebody the one
        # damage door can reach. Measured 2026-09-25: a scheme's off-stage death wrote
        # `who.hp -= amount` around this door because `scene.actors[...]` raised
        # KeyError for a victim at the lodging while the player stood in the wild — so
        # resistances, damage reduction and guards never applied off-stage.
        target = self.scene.actors.get(pk.target) or self.scene.people[pk.target]
        amount = pk.amount
        # "A troop takes half again as much damage (+50%) from spells or effects that affect
        # an area" — the rule that makes a fireball feel right against a crowd, and the
        # reason a caster has something better to do than pick members off one at a time.
        # Applied before the packet lands, because it multiplies what was DEALT: the same
        # order `take_damage` gives vulnerability, and for the same reason.
        unit = getattr(target, "troop", None)
        if unit is not None:
            mult = troops_mod.damage_multiplier(unit, pk.traits)
            if mult != 1.0:
                amount = int(amount * mult)
        d = target.take_damage(amount, pk.dtype, pk.traits, pk.lethality)
        effect = self._describe_damage(target, d, pk.lethality)
        if unit is not None:
            effect.update(self._unit_took_it(target, d))
        if pk.notes:
            effect["intercepted"] = pk.notes
            through = guards_mod.describe(pk.notes)
            effect["note"] = f"{effect['note']}, {through}" if effect["note"] else through
        return effect

    def _unit_took_it(self, target: Actor, d: dict) -> dict:
        """What a blow did to a crowd: how many fell, and whether the rest ran.

        Both halves in one place, because they are one event to the player — "three raiders
        go down; the nine still standing scatter and run" is one sentence. The attrition
        itself is already done (`Actor.take_damage` is the one writer); this is the morale
        check on top of it, and the check is the one moment a unit needs dice of its own.

        Basic D&D's rule, unchanged: 2d6 against the morale score, higher and they run, and
        the two moments are the first death and half the group down. Pathfinder has no
        general morale rule, which is why its troops can only be destroyed — and "run away
        and scatter" is what was asked for.
        """
        unit = target.troop
        fell = int(d.get("fell", 0) or 0)
        out: dict = {"fell": fell, "members": int(unit.members),
                     "members_max": int(unit.members_max)}
        tell = troops_mod.tell_of(unit, target.name, fell)
        moment = troops_mod.owes_a_check(unit, fell)
        if moment and unit.members > 0:
            roll = self.dice.roll(troops_mod.MORALE_DICE,
                                  label=f"{target.name} morale ({moment})",
                                  visibility="hidden")
            if not troops_mod.morale_holds(unit, roll.total, moment):
                out["routed"] = True
                tell = f"{tell} {troops_mod.rout_tell(target.name, unit)}".strip()
                self._rout(target)
        if tell:
            out["unit_note"] = tell
        return out

    def _rout(self, target: Actor) -> None:
        """A unit whose morale broke leaves the board and the fight.

        The survivors scatter, which is the request's own word. They are not killed and they
        are not spared either: `troops.xp_owed` pays for the ones who fell, because eight
        dead and four fled is not mercy and paying nothing for it would be the answer the
        player would notice first.
        """
        if self.scene.in_encounter:
            for refs in (self.scene.sides or {}).values():
                if target.ref in refs:
                    refs.remove(target.ref)
            # Through the door, not a list comprehension: this ran BEFORE `scene.remove`,
            # so `_unseat` then read an order that had already shifted and re-pointed the
            # turn at somebody else (measured: the turn moved from the player to c3).
            self.scene.leave_order(target.ref)
        self.scene.positions.pop(target.ref, None)
        # The debt outlives them. They are about to leave the scene, and the experience for
        # the ones who died has not been paid yet — a fight's XP settles on the way OUT of
        # an encounter — so the amount is remembered where the scene remembers things.
        owed = troops_mod.xp_owed(target.troop)
        if owed:
            self.scene.routed_xp.append({"who": str(target.name),
                                         "fallen": int(target.troop.fallen),
                                         "xp": int(owed)})
        # Off the board through the one destroyer, which takes the relational state with
        # them (guards at either end, wards, compulsions). They ran; they are not a body
        # lying here, and leaving them in the scene at 1 hp would make them a target.
        self.scene.remove(target.ref)

    def _describe_damage(self, target: Actor, d: dict, lethality: str) -> dict:
        return {
            "ref": target.ref, "kind": "damage",
            # `amount` stays the number that actually came off hit points, because that is
            # what every existing reader of this effect means by it.
            "amount": d["taken"], "rolled": d["rolled"], "type": d["type"],
            "reduced": d["reduced"], "reduced_by": d["reduced_by"],
            "absorbed": d["absorbed"],
            "hp_after": target.hp, "hp_max": target.hp_max, "temp_hp": target.temp_hp,
            "lethality": lethality, "nonlethal": target.nonlethal,
            "note": _damage_note(d),
        }

    def _hp_state_effects(self, target: Actor) -> list[dict]:
        return [
            {"ref": target.ref, "kind": "condition", "condition": c, "from": "hit points"}
            for c in target.apply_hp_state()
        ]

    # What each hit-point state sounds like, said once. The narrator is fed tells and
    # nothing else about mechanics, and until this existed the tell for a killing blow
    # was "the thug takes 30 slashing damage." — the death was in `outcome.effects`,
    # which the narrator may not read, so it was never told anybody died. It wrote
    # wounded-man prose about a corpse and a repair pressed the death on afterwards.
    #
    def _hp_state_tell(self, effects: list[dict]) -> str:
        """The sentence that goes with what `_hp_state_effects` just wrote.

        Returned rather than appended in place, because the five sites that cross a
        hit-point threshold each build their tell differently — an attack's tell reads
        nothing like a falling rock's — and the state has to arrive in the same sentence
        the player is already reading.
        """
        keys = {str(e.get("condition") or "") for e in effects or []
                if e.get("kind") == "condition"}
        said = []
        for e in effects or []:
            if e.get("kind") != "condition":
                continue
            key = str(e.get("condition") or "")
            # 1e writes both on the one blow and they are a single event to anybody
            # reading, so the pair is said once rather than as two flat sentences.
            if key == "dying" and "unconscious" in keys:
                continue
            line = _STATE_SAID.get(key)
            if not line:
                continue
            line += "."
            if key == "unconscious" and "dying" in keys:
                line = "{name} is unconscious and dying."
            who = self.scene.actors.get(e.get("ref"))
            # Disabled says "still standing", and a body already out cold from non-lethal
            # damage is not: a blow that takes it to exactly 0 leaves it unconscious at
            # nothing. Unreachable until 2026-09-27, when a blow at an unconscious body
            # first landed at all; the first live coup de grâce the thug survived by a
            # natural 20 would have told the narrator he was on his feet.
            if key == "disabled" and who is not None \
                    and who.has_state("state.down.unconscious"):
                line = "{name} has no hit points left and lies unconscious."
            said.append(line.format(name=who.name if who else "they"))
        return (" " + " ".join(said)) if said else ""


# --- (de)serialisation for the suspend/resume round trip --------------------------------

def _and_then(names) -> str:
    """"the square, the market and the lane" — the way there, in the order walked."""
    got = [str(n) for n in names if str(n).strip()]
    if len(got) <= 1:
        return got[0] if got else ""
    return ", ".join(got[:-1]) + f" and {got[-1]}"


def _place_key(name) -> str:
    """A place's name as a plan's two ops compare it: "The Tarred Rope" is "tarred rope"."""
    text = " ".join(str(name or "").lower().split())
    return text[4:] if text.startswith("the ") else text


def _found_before_travel(intents: list) -> list:
    """Every `found` moved ahead of the first `travel` to the place it makes."""
    out = list(intents)
    for found in [i for i in out if i.op == "found" and i.params.get("name")]:
        key = _place_key(found.params["name"])
        walk = next((k for k, i in enumerate(out) if i.op == "travel"
                     and _place_key(i.params.get("place")) == key), None)
        if walk is not None and walk < out.index(found):
            out.remove(found)
            out.insert(walk, found)
    return out


def _introduce_after_travel(intents: list) -> list:
    """Every `introduce` of somebody already here moved after the plan's last walk,
    unless that walk takes them along (`with` names their placeholder). An `arrives`
    newcomer is left where it is: arriving is an event where the party stands."""
    out = list(intents)
    walks = [k for k, i in enumerate(out) if i.op in ("travel", "journey")]
    if not walks:
        return out
    for intro in [i for i in out if i.op == "introduce"
                  and (i.params.get("how") or "already_here") == "already_here"]:
        last = max(k for k, i in enumerate(out) if i.op in ("travel", "journey"))
        if out.index(intro) > last:
            continue
        walk = out[last]
        takes = {str(w) for w in (walk.params.get("with") or [])}
        if takes & {str(p) for p in intro.params.get("placeholders") or ["new1"]}:
            continue
        out.remove(intro)
        out.insert(last, intro)
    return out


def _rename_refs(raw: dict, names: dict) -> dict:
    """A queued intent with refs renamed, wherever an intent can hold one: actor, target
    (one or several), and the params that name people — `opposed_by.ref`, `to`, `from_`,
    `who`, and a begin_encounter's sides."""
    def swap(v):
        return names.get(v, v) if isinstance(v, str) else v

    raw = dict(raw)
    raw["actor"] = swap(raw.get("actor"))
    tgt = raw.get("target")
    raw["target"] = [swap(t) for t in tgt] if isinstance(tgt, list) else swap(tgt)
    params = dict(raw.get("params") or {})
    for key in ("to", "from_", "who"):
        if key in params:
            params[key] = swap(params[key])
    if isinstance(params.get("opposed_by"), dict):
        params["opposed_by"] = dict(params["opposed_by"],
                                    ref=swap(params["opposed_by"].get("ref")))
    if isinstance(params.get("sides"), dict):
        params["sides"] = {k: [swap(r) for r in v] if isinstance(v, list) else v
                           for k, v in params["sides"].items()}
    # A cast's aim holds a person too — the legacy `at`, and `aim: ref:<ref>`. Left out,
    # `introduce` then `cast at=new1` validated (new1 is legal after the introduce) and
    # then resolved at "new1", a ref nobody holds: the flames reached nobody (G2).
    if isinstance(params.get("at"), str):
        params["at"] = swap(params["at"])
    aim = params.get("aim")
    if isinstance(aim, str) and aim.startswith("ref:"):
        params["aim"] = "ref:" + swap(aim[4:])
    raw["params"] = params
    return raw


def _intent_from_dict(d: dict) -> Intent:
    return Intent(
        op=d["op"], actor=d.get("actor"), target=d.get("target"),
        because=d.get("because", ""), params=d.get("params") or {},
        visibility=d.get("visibility", "hidden"), id=d.get("id", "i1"),
        # The stamp survives the suspend/resume round trip the same way the rest
        # does; the first cut of stage 8 lost it here, and every op saw "".
        origin=str(d.get("origin", "") or ""),
        origin_name=str(d.get("origin_name", "") or ""),
    )


def _roll_from_dict(d: dict) -> Roll:
    return Roll(
        die=d["die"], faces=list(d["faces"]),
        # The type rides along: without it every bonus on a multi-stage attack — parked
        # as a dict between the roll and its resolution — reached the turn log untyped,
        # and the browser's popup could not say a morale +1 from an enhancement +1.
        # Found by the stage-8 verifiers' stacking probe.
        modifiers=[Modifier(m["value"], m["source"], str(m.get("type", "") or ""))
                   for m in d["modifiers"]],
        label=d.get("label", ""), visibility=d.get("visibility", "hidden"),
    )


def _rehydrate(d: dict) -> Outcome:
    return Outcome(
        intent_id=d["intent_id"], op=d["op"], status=d.get("status", "resolved"),
        rolls=[_roll_from_dict(r) for r in d.get("rolls", [])],
        dc=d.get("dc"), verdict=d.get("verdict"), margin=d.get("margin"),
        effects=d.get("effects", []), tell=d.get("tell", ""), because=d.get("because", ""),
        code=str(d.get("code", "") or ""), for_a_person=str(d.get("for_a_person", "") or ""),
        fix=d.get("fix"),
    )


def survival_note(toll) -> str:
    """What a long stretch of hours did to somebody, in a clause.

    Written for the GM to narrate rather than for the log, so it names the conditions and
    the collapse and leaves the individual DCs out — the checks are all in the effect for
    anyone auditing it.
    """
    bits = []
    if toll.nonlethal:
        bits.append(f"{toll.nonlethal} non-lethal")
    if toll.conditions:
        bits.append(", ".join(toll.conditions))
    if toll.collapsed:
        bits.append("they went down where they stood")
    failed = sum(1 for c in toll.checks if not c["passed"])
    if failed and not bits:
        bits.append(f"{failed} failed check{'s' if failed != 1 else ''}")
    return ("; ".join(bits) + ".") if bits else "nothing they could not walk off."


def _rounds_from(duration) -> int | None:
    """A duration block as a number of rounds, or None for one that never ends."""
    if not isinstance(duration, dict) or not duration.get("amount"):
        return None
    per = {"round": 1, "minute": 10, "hour": 600, "day": 14400}
    try:
        return int(duration["amount"]) * per.get(str(duration.get("unit", "hour")), 600)
    except (TypeError, ValueError):
        return None


def _doc_tell(template, actor) -> str:
    """An ability document's own tell, with the actor's name in it.

    The document writes `{name}` and nothing else — a template that names a number
    would be a mechanic authored into prose, which is exactly what the severed-tells
    rule exists to stop. A malformed template falls back to its literal text rather
    than crashing the turn.
    """
    if not template:
        return ""
    try:
        return str(template).format(name=actor.name)
    except (KeyError, IndexError, ValueError):
        return str(template)


# How a hit-point state reads, in the voice `_op_ability_damage` has used for these same
# conditions all along — one rule that had two copies, and only one of them was silent.
# Terse on purpose: a tell constrains the narrator, it does not decorate, and florid
# tells are the presentation layer leading the mechanic.
#
# `disabled` earns its clause because the bare game word is opaque — a narrator handed
# "the thug is disabled" writes nothing a player can picture, and the contract's own rule
# is that a fact the narrator needs becomes part of the tell. Shared with `_ward_tell` so
# a cloud that disables somebody is no more cryptic than a sword that does.
_STATE_SAID = {
    "dead": "{name} is dead",
    "dying": "{name} is dying",
    "unconscious": "{name} is unconscious",
    "disabled": "{name} is disabled: still standing, but any real effort now costs blood",
}


def _ward_tell(scene: Scene, e: dict) -> str:
    """One thing a standing effect did, in the voice the rest of the log is written in.

    A free function because both the attack path and the round tick produce these and
    `play/views.py` narrates the round tick's — three callers, one sentence, and three
    copies of it is how two of them end up disagreeing about what a saved hazard reads as.
    """
    who = scene.actors.get(e.get("ref", ""))
    name = who.name if who else e.get("ref", "something")
    source = e.get("source", "it")
    kind = e.get("kind")
    if kind == "damage":
        half = " (halved by the save)" if e.get("saved") else ""
        return (f"{name} takes {e['amount']} {e['type']} damage from {source}{half} "
                f"({e.get('hp_after')}/{e.get('hp_max')}).")
    if kind == "heal":
        return f"{source} restores {e['amount']} hit points to {name}."
    if kind == "ward_saved":
        nat = f"{e['natural']}, " if e.get("natural") else ""
        return f"{name} rides out {source} ({nat}{e.get('roll')} against DC {e.get('dc')})."
    if kind == "condition":
        key = str(e.get("condition") or "")
        said = _STATE_SAID.get(key, "{name} is " + key)
        return f"{said.format(name=name)} ({e.get('from', source)})."
    if kind == "ability_damage":
        return (f"{name} takes {e.get('amount')} "
                f"{ABILITY_FULL.get(str(e.get('ability', '')), 'ability')} damage "
                f"from {source}.")
    if kind == "manifest_ended":
        return f"{e.get('what', 'It')} thins out and is gone."
    if kind == "effect_ended":
        return f"{e.get('what', 'Something')} wears off {name}."
    if kind == "ward_ended":
        return f"{e.get('what') or source} fades."
    if kind == "pool_ready":
        return f"{name} can use {e.get('pool', 'it')} again."
    if kind == "compulsion_ended":
        return f"{name} is free of {e.get('what', 'it')}."
    if kind == "upkeep_failed":
        return (f"{e.get('what', 'It')} runs dry and lets go of {name} — "
                f"no {e.get('pool', 'fuel')} left to hold it.")
    if kind == "ward_due":
        return f"{source}: {e.get('line', '')} — for the GM to apply."
    return ""


def _instrument(weapon: dict, weapon_key: str) -> str:
    """" with the sap" — what the blow was struck with, for the tell — or "" for a
    bare hand or an improvised thing (whose own tell names it).

    The narrator is fed tells and nothing else about mechanics, and "the thug hits
    Kesst Vayr for 5 bludgeoning" named no weapon at all. Measured live 2026-09-27: a
    disarmed thug took his sap back up, swung it three rounds running, and the prose
    had him clamping her forearm, driving his fist into her ribs and raking with "its
    taloned limbs" — the body the brief describes, since nothing said what was in his
    hand. The weapon rides as the instrument, after the defender, never as the subject:
    a tell that opened with an object ("weapon's attack misses Masta", 2026-09-18) had
    the model hand the blow to the player (`narration.wrong_hands`).
    """
    key = str(weapon_key or "").lower()
    if key in ("unarmed", "improvised"):
        return ""
    name = " ".join(str(weapon.get("name") or key).split())
    return f" with the {name}" if name else ""


def _a_person(template: str) -> bool:
    """Whether a spawned creature is one of the local people, and so gets a true name
    and a face from their pools.

    `_bring_in` gave every arrival in a world a name and a face from the local people's
    pools, and could not tell a wolf from a woman. Measured 2026-09-29 while building the
    road starts: on Pangrella "the medium giant scorpion" spawned with the appearance
    "Korvu: Korvu have four limbs ending in sharp talons … a line of blue ink dots across
    the knuckles" and a person's true name, which the brief's WHO IS HERE then handed the
    narrator. The same happened to whatever the road and foraging drew from the land.

    Decided here: a humanoid is a person (a bandit, a thug, a goblin); every other type —
    animal, vermin, magical beast, outsider, and monstrous humanoid too, because a local
    people's body line is always wrong for a minotaur or a harpy — gets neither. The
    hand-made civilian blocks (guildhand, watchman) are not in the imported bestiary and
    are people by construction.
    """
    from . import bestiary

    row = bestiary.imported().get(str(template or "").strip().lower())
    if row is None:
        return True
    return str(row.get("creature_type") or "").strip().lower() == "humanoid"


def _damage_note(d: dict) -> str:
    """"12, less DR 5/—, 4 off temporary" — the sentence a player needs.

    Empty when nothing interesting happened, so the ordinary hit stays quiet and the two
    mechanics that can make damage vanish always say so. Damage disappearing without
    explanation is the failure this exists to prevent.
    """
    bits = []
    if d["reduced"]:
        bits.append(f"less {d['reduced_by']} ({d['reduced']})")
    if d.get("factored"):
        # Percent resistance is the third way damage vanishes, and it must say so
        # for the same reason DR does — the GM narrates the number that landed.
        bits.append(f"{d['factored']} shrugged off by {d.get('factored_by') or 'resistance'}")
    if d["absorbed"]:
        bits.append(f"{d['absorbed']} off temporary")
    if d.get("immune_nonlethal"):
        # The fourth way damage vanishes: a fist on a skeleton. Said, for the reason
        # this function exists.
        bits.append("not subject to non-lethal damage")
    if d.get("lethality") == "nonlethal" and d.get("taken"):
        bits.append(f"non-lethal now {d.get('nonlethal')}")
    if d.get("overflow"):
        bits.append(f"{d['overflow']} past the non-lethal limit, taken as lethal")
    return f"{d['rolled']}, " + ", ".join(bits) if bits else ""


def _multiply_dice(notation: str, mult: int) -> str:
    """1d6 x3 -> 3d6. A critical multiplies the dice, not the rolled result."""
    if mult <= 1:
        return notation
    count, faces, flat = Dice().parse(notation)
    if count == 0:
        # A constant: "1" is what a stat block's "(1)" or "(1d1)" becomes, and
        # "0d1+2" — what the line below would build — is refused by the roller. The
        # constant is the damage, and a critical multiplies it.
        return str(flat * mult)
    out = f"{count * mult}d{faces}"
    if flat:
        out += f"{flat:+d}"
    return out


def _to_rounds(amount: int, unit: str) -> int:
    return {"round": 1, "minute": 10, "hour": 600, "day": 14400}[unit] * int(amount)


def _to_minutes(amount: int, unit: str) -> int:
    return {"round": 0, "minute": 1, "hour": 60, "day": 1440}[unit] * int(amount)
