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
from . import worldclass
from . import grid as gridmod
from . import guards as guards_mod
from . import reactions
from . import spells as spells_mod
from . import weapons as weapons_mod
from .activeeffect import ActiveEffect
from .guards import Guard, Packet
from .dice import Dice, Modifier, Roll
from .grid import Grid
from . import hazards
from .intents import AMOUNT_OPS, Intent, IntentError, parse_all
from .sheet import Actor
from .tables import (
    CONDITIONS,
    ABILITY_FULL, MANEUVERS, SAVES, SIZE_ORDER, WEAPONS, normalise_damage_type,
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
    # Places minted in play (`rules/places.py`, doors two and three): the stored
    # exception to "derived, never stored", since the player made them. Place dicts
    # with a parent and an owner; `places.with_founded` grafts them onto the derived
    # set by parent at read time. `Engine.found`/`Engine.venture` are the doors.
    founded: list[dict] = field(default_factory=list)
    # The schemes running in this campaign (rules/schemes.py): one instance per opened
    # scheme — its filled slots, the steps that fired and when, its outcome. Stored,
    # like `founded`, because play made it; read back through the one ticker.
    schemes: list[dict] = field(default_factory=list)
    log: list[dict] = field(default_factory=list)

    # Whose turn it is: an index into `initiative`. -1 outside an encounter.
    turn: int = -1
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
        """Put a creature into the scene, HERE. One of the writers of `Actor.at`.

        Stamped unconditionally: a roster sheet carries the place the character last
        stood in, in a campaign that may be in another world, and `if not actor.at`
        would let that id walk in.

        The keyword `at` is a GRID SQUARE and predates the place field of the same
        name on the actor; forty test sites pass it. The two are never confused in
        code because one is a tuple and the other a string, and the name stays.
        """
        actor.at = self.at
        self.people[actor.ref] = actor
        self.zones[actor.ref] = zone
        if at is not None:
            self.positions[actor.ref] = (int(at[0]), int(at[1]))
        # The mark only ever rises. Loading a save, spawning, promoting a cast entry all
        # come through here, so a save from before the mark existed heals itself to the
        # highest ref it holds on the first load.
        m = re.fullmatch(r"c(\d+)", str(actor.ref))
        if m:
            self.minted = max(self.minted, int(m.group(1)))
        return actor

    # --- the map, when there is one ------------------------------------------------------

    @property
    def has_grid(self) -> bool:
        """A scene without a map is not a broken scene. Most of them do not need one — a
        conversation in a tavern has no squares — and combat still resolves off zones."""
        return self.grid is not None

    def position(self, ref: str) -> tuple[int, int] | None:
        return self.positions.get(ref)

    def occupied(self, ignore: str = "") -> set[tuple[int, int]]:
        """Every square something is standing on, for movement to route around."""
        from .grid import footprint

        out: set[tuple[int, int]] = set()
        for ref, anchor in self.positions.items():
            if ref == ignore or ref not in self.actors:
                continue
            if self.actors[ref].has_condition("dead"):
                continue
            out.update(footprint(anchor, self.actors[ref].size))
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
            for dy in range(0, self.grid.height):
                for sign in (1, -1):
                    spot = (min(self.grid.width - 1, max(0, px + away)),
                            min(self.grid.height - 1, max(0, py + sign * dy)))
                    if spot not in taken:
                        self.positions[ref] = spot
                        taken.add(spot)
                        break
                else:
                    continue
                break

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
        for step in range(1, len(self.initiative) + 1):
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
        made.id = made.id or f"m{len(self.manifests) + 1}"
        if self.grid is not None and made.terrain in ("obscuring", "blocked", "difficult"):
            already = getattr(self.grid, made.terrain)
            made.added = [s for s in made.squares
                          if self.grid.inside(s) and s not in already]
            already.update(made.added)
        self.manifests.append(made)
        return made

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
                saved = roll.total >= ward.dc
                if saved:
                    branch = spec.get("on_success") or []
                    if not branch:
                        return [{"kind": "ward_saved", "ref": victim.ref,
                                 "source": ward.source, "roll": roll.total,
                                 "dc": ward.dc}]
            for inner in branch:
                out.extend(self._resolve_on(victim, ward, inner, "", ""))
            return out

        saved = False
        if save:
            roll = self._dice.d20(victim.save_modifiers(save),
                                  label=f"{save} save against {ward.source}",
                                  visibility="hidden")
            saved = roll.total >= ward.dc
            if saved and save_effect in ("negates", ""):
                return [{"kind": "ward_saved", "ref": victim.ref, "source": ward.source,
                         "roll": roll.total, "dc": ward.dc}]

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
        self.initiative = []
        self.turn = -1
        self.round = 0
        self.acted = set()
        self.attacked = set()
        self.sides = {}
        # The battlefield goes with the fight. `begin_encounter` lays a grid when none
        # exists, and the side panel's own words are "there is no grid outside a fight";
        # here rather than only in the end_encounter *op*, because most fights end by
        # a side emptying inside the NPC-turn loop, which calls this directly.
        self.grid = None
        self.positions.clear()
        # The fog goes with the map it was drawn on. A manifestation kept past the grid
        # that held its squares is a bank of fog with no location, and the next fight
        # would lay a fresh grid without it — the squares would be gone and the thing
        # claiming them would not.
        self.manifests = []
        self.wards = []
        self.hazards = []

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
        # hands somebody else's turn to the wrong side of the fight.
        current = self.initiative[self.turn][0] if 0 <= self.turn < len(self.initiative) else None
        self.initiative = [(r, roll) for r, roll in self.initiative if r != ref]
        if current == ref or current is None:
            self.turn = -1 if not self.initiative else min(self.turn, len(self.initiative) - 1)
        else:
            self.turn = next(i for i, (r, _) in enumerate(self.initiative) if r == current)

        self.zones.pop(ref, None)
        self.positions.pop(ref, None)
        self.acted.discard(ref)
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
        actor.at = place_id
        self.zones[ref] = "near"
        if actor.is_pc:
            self.at = place_id
            self.cast = []
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

    def as_dict(self) -> dict:
        return {
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
_SPAWN_HINT = (
    ' If someone new should be in the scene, create them first with '
    '{"op": "spawn", "params": {"template": "thug", "count": 2}} — the templates are '
    "guildhand, watchman, thug and guard dog — and use the refs it returns."
)


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
        mine = {tuple(s) for s in self.squares}
        return any(tuple(s) in mine for s in squares)

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
        # Whether a fight began inside the current batch of intents. Read by the
        # attack op: a swing riding the same GM turn that opened the battle is
        # deferred to the player's own first combat turn, never resolved in prose.
        self._battle_joined = False

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
        # Refs an earlier intent in this same list will have created by the time a later
        # one runs. Without this, "two bravos step out of the dark and I fight them" is
        # impossible to express: the whole list is validated before any of it runs, so a
        # spawn followed by an attack on what it spawned was always rejected, and the GM
        # burned every attempt guessing at refs that could not exist yet.
        pending = self._projected_refs(intents)
        for i, intent in enumerate(intents):
            self._check_refs(intent, i, extra=pending)
            self._check_legality(intent, i)
            self._force_visibility(intent)
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

    def _check_refs(self, intent: Intent, index: int,
                    extra: set[str] | None = None) -> None:
        if intent.op in ("narrate_only", "advance_time", "spawn", "begin_encounter"):
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
        if to and not self._known(to, extra):
            raise IntentError(
                f"{intent.op}: unknown ref {to!r} in params.to", "refs", index
            )
        frm = intent.params.get("from_")
        if intent.op == "loot" and frm and not self._known(frm, extra):
            raise IntentError(
                f"{intent.op}: unknown ref {frm!r} in params.from", "refs", index
            )

    def _check_legality(self, intent: Intent, index: int) -> None:
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
        if intent.op in AMOUNT_OPS and not intent.origin:
            raise IntentError(
                f"{intent.op}: no document behind this number. Name what does it: "
                f"use_item item=<id> for a jar, cast spell=<id> for a spell, "
                f"use_ability ability=<name> for a power. The engine supplies the "
                f"amount from the document.", "legality", index)
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
                        f"condition, not dice.", "legality", index)
        if intent.op == "guard" and not intent.origin:
            kind = str(intent.params.get("kind", "redirect"))
            numbered = [k for k in ("amount", "uses") if intent.params.get(k)]
            if kind != "redirect" or numbered:
                raise IntentError(
                    f"guard: {kind} with {', '.join(numbered) or 'a number'} is an "
                    f"ability's to declare — use_ability ability=<name> and its "
                    f"document sets the amount. A plain guard is kind=redirect with "
                    f"no numbers.", "legality", index)
        if intent.op == "resource" and not intent.params.get("spend") \
                and not intent.origin:
            raise IntentError(
                f"resource: a pool is not gained by saying so. Pools refill by "
                f"rest ({{\"op\": \"rest\"}}) or by an ability's document "
                f"(use_ability ability=<name>); spend=true spends one.",
                "legality", index)
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
            if known and places_mod.find(known, str(intent.params["place"])) is None                     and places_mod.find(outside, str(intent.params["place"])) is None:
                raise IntentError(
                    f"travel: there is no {intent.params['place']!r} here. Name one of: "
                    f"{', '.join(p.name for p in known)}.", "schema")
        if intent.op == "hazard":
            trouble = hazards.check(str(intent.params.get("rule", "")), intent.params)
            if trouble:
                raise IntentError(f"hazard: {trouble}", "legality", index)
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
                                          "legality", index)
                    if how == "coat":
                        weapon = str(intent.params.get("weapon") or actor.equipped
                                     or "").lower()
                        if not weapons_mod.has(weapon):
                            raise IntentError(
                                f"use_item: {actor.name} has no weapon {weapon!r} to coat",
                                "legality", index)
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
                    "legality", index)
        if intent.op == "ability_damage":
            ab = str(intent.params.get("ability", "")).strip().lower()
            if ab and ab not in ABILITY_FULL:
                raise IntentError(
                    f"ability_damage: no ability score called {ab!r}. The six are: "
                    f"{', '.join(ABILITY_FULL)}.", "schema", index)
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
                "legality", index,
            )
        if intent.op == "rest":
            pc = self.scene.pc()
            if pc is not None and pc.hp < 0:
                raise IntentError(
                    f"rest: {pc.name} is bleeding out, not sleeping. They have to be "
                    f"stabilised first.",
                    "legality", index,
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
                    "legality", index,
                )
        if intent.op == "attack" and actor:
            key = intent.params.get("weapon") or actor.equipped or "unarmed"
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
                        f"{granted['ability']} to form it first.", "legality", index)
            elif not weapons_mod.has(key):
                raise IntentError(
                    f"attack: {actor.name} has no weapon {key!r}", "legality", index
                )
            elif actor.weapons and key not in actor.weapons and key != "unarmed":
                raise IntentError(
                    f"attack: {actor.name} is not carrying a {key} "
                    f"(has {', '.join(actor.weapons) or 'nothing'})",
                    "legality", index,
                )
            if intent.params.get("power_attack"):
                why = actor.can_power_attack()
                if why:
                    raise IntentError(f"attack: {why}", "legality", index)
            man = intent.params.get("manoeuvre")
            if man:
                m = MANEUVERS[man]
                targets = intent.targets()
                defender = self.scene.get(targets[0]) if targets else None
                if defender is None:
                    raise IntentError(
                        f"attack: a {man} needs a target", "legality", index
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
                            "legality", index,
                        )
                if m.get("condition") and defender.has_condition(m["condition"]):
                    raise IntentError(
                        f"attack: {defender.name} is already "
                        f"{m['condition']}", "legality", index,
                    )

    # --- Running --------------------------------------------------------------------

    def run(self, intents: list[Intent]) -> Resolution:
        # A fresh batch is a fresh question. Reset here and not in `resume`, because a
        # resume continues the same declared turn — a battle joined before the player
        # was handed a die is still the battle this batch joined.
        self._battle_joined = False
        return self._tick_schemes(self._drive([i.as_dict() for i in intents], [], {}))

    def _tick_schemes(self, resolution: "Resolution") -> "Resolution":
        """After a batch resolves, the world's schemes get their tick (rules/schemes.py):
        the steps whose criteria now hold are candidates, the most specific fires, and
        a step the player could witness comes back as an outcome with a tell — a step
        they could not stays silent, on the log and the secret card only. Skipped
        while a roll is waiting: the batch is not over."""
        if resolution.awaiting:
            return resolution
        from . import schemes as schemes_mod

        try:
            extra = schemes_mod.tick(self, resolution.outcomes)
        except Exception as exc:  # noqa: BLE001 — a scheme must never take the turn down
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
            # Anyone who has done something is no longer flat-footed.
            if intent.actor and intent.op in ("attack", "check", "move", "save"):
                self.scene.acted.add(intent.actor)
            self.scene.log.append(outcome.as_dict())
        return Resolution(outcomes=outcomes)

    # --- Reactions ---------------------------------------------------------------------

    def _reactions_before(self, raw: dict) -> list[dict]:
        """Intents owed to other creatures because of the one about to resolve.

        Returned as raw intent dicts so they go through `_drive` exactly like anything
        else — which is what makes a player-taken attack of opportunity suspend for a dice
        roll without a single line of special handling.

        Only movement provokes today. The shape is a dispatch rather than an `if` because
        the next triggers (casting in a threatened square, standing up from prone) are the
        same machinery with a different question.
        """
        if raw.get("op") != "move" or not self.scene.in_encounter:
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
        return Outcome(intent_id=intent.id, op=intent.op, status="resolved",
                       tell="", because=intent.because)

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
        at = f" to {heard.name}" if heard is not None else ""
        # Quoted speech is quoted; reported speech is reported. "I ask her if she
        # wants to pay for my services" is not a sentence the character said, and a
        # tell that quotes it hands the narrator the player's own framing to put in
        # somebody's mouth.
        said = (f'{who} says{at}: "{words}"' if intent.params.get("quoted")
                else f"{who} speaks{at}, to the effect that {words}")
        return Outcome(
            intent_id=intent.id, op=intent.op, status="resolved",
            effects=[{"kind": "said", "who": intent.actor or "",
                      "to": (str(intent.params.get("to") or "") if heard is not None
                             else ""),
                      "words": words}],
            tell=said, because=intent.because)

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
        if opposed:
            target = opposing_roll.total
            resolved_dc = dc_mod.ResolvedDC(value=target, band=None)
            if intent.params.get("circumstance"):
                c = intent.params["circumstance"]
                resolved_dc.circumstance = dc_mod.CIRCUMSTANCE[c["value"]]
                resolved_dc.circumstance_why = c.get("why", "") or c["value"]
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

        return Outcome(
            intent_id=intent.id, op="check", rolls=rolls, dc=resolved_dc.as_dict(),
            verdict=verdict, margin=margin, tell=tell, because=intent.because,
        )

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

        margin = roll.total - resolved_dc.final
        verdict = "success" if margin >= 0 else "failure"
        branch = intent.params.get("on_success" if verdict == "success" else "on_failure") or {}

        effects: list[dict] = []
        tell_bits = [
            f"{actor.name} makes the {SAVES[save]} save by {margin}."
            if verdict == "success" else
            f"{actor.name} fails the {SAVES[save]} save by {-margin}."
        ]

        dmg = branch.get("damage")
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
        if partial.get("attack_state") is None:
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
                    effects=[{"ref": actor.ref, "kind": "battle_joined",
                              "target": defender.ref}],
                    tell=(f"Battle is joined: {actor.name} squares off against "
                          f"{', '.join(foes) or defender.name}. Nothing has landed "
                          f"yet — the first blow is still to be struck."),
                    because=intent.because)
        self._ensure_encounter(intent.actor, intent.target)
        weapon_key = (intent.params.get("weapon") or actor.equipped or "unarmed").lower()
        weapon = actor.weapon(weapon_key)
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

        if intent.params.get("manoeuvre"):
            return self._resolve_maneuver(intent, actor, defender, weapon_key, partial)

        # Flat-footed: a defender who has not acted yet loses Dex to AC. Outside an
        # encounter nobody has acted, so the first blow of a fight lands against a
        # flat-footed target — which is the common ambush case and is worth getting
        # right, since it is usually several points of AC.
        flat_footed = (
            defender.has_condition("flat-footed")
            or not self.scene.initiative
            or not self._has_acted(defender.ref)
        )
        target_ac = defender.ac(against=weapon["category"], flat_footed=flat_footed)
        ac_note = f"AC {target_ac}" + (" (flat-footed)" if flat_footed else "")

        state = partial.get("attack_state") or {"i": 0, "stage": "attack", "rolls": [],
                                                "effects": [], "tells": []}
        sequence = actor.attack_sequence(weapon_key, full)
        # One swing at a stated iterative. The combat panel lets a Blood Bender replace
        # any attack in a full attack with an ability, so the remaining weapon swings
        # arrive one op each, still carrying their own -5/-10 — a mixed full attack
        # whose swings all rolled at full BAB would be the panel quietly buffing the
        # class it was built for.
        it = intent.params.get("iteration")
        if it is not None and not full:
            whole = actor.attack_sequence(weapon_key, True)
            sequence = [whole[min(int(it), len(whole) - 1)]]

        # Swift Strikes: an always-active passive, never an ability to spend. On any
        # attack after the first against the same target this encounter, the swing
        # strikes again at the same bonus — +1 on a standard action, +2 on a declared
        # full attack, which is the printed rule and also makes a panel-split full
        # attack (each swing its own op) add up to the same total. Decided from the
        # scene's memory of *completed* attacks, so it is stable across the suspension
        # round-trips of the dice popup.
        from . import leveling as leveling_mod

        if (leveling_mod.has_passive(actor, "swift strikes")
                and f"{actor.ref}>{defender.ref}" in self.scene.attacked):
            extra = 2 if full else 1
            sequence = list(sequence) + [sequence[0]] * extra
            if state["i"] == 0 and not state["rolls"]:
                state["tells"].append(
                    f"Swift Strikes: {actor.name} strikes "
                    f"{'twice more' if extra == 2 else 'again'} at {defender.name}.")

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
            if defender.is_down:
                if state["i"]:
                    state["tells"].append(
                        f"{defender.name} is already down; {actor.name} holds the blow.")
                break
            iteration = sequence[state["i"]]
            atk_mods = actor.attack_modifiers(weapon_key, iteration, power_attack=power)
            # Compulsions are charged here rather than in `attack_modifiers` because the
            # penalty depends on *who is being attacked*, which the sheet does not know.
            # It penalises and never prohibits: see the header of rules/compulsion.py.
            atk_mods = atk_mods + compulsion.penalty_against(actor, defender.ref)

            if state["stage"] == "attack":
                atk = self._roll_or_suspend_stage(
                    intent, actor, atk_mods, f"Attack with {weapon['name']}",
                    target_ac, partial, state, "1d20",
                )
                state["rolls"].append(atk.as_dict())
                natural = atk.natural
                if natural == 1:
                    state["tells"].append(
                        f"{actor.name}'s attack goes badly wide (natural 1).")
                    state["i"] += 1
                    continue
                if not (natural == 20 or atk.total >= target_ac):
                    state["tells"].append(
                        f"{actor.name}'s attack misses {defender.name} "
                        f"({atk.total} against {ac_note}).")
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
                    target_ac, partial, state, "1d20",
                )
                state["rolls"].append(confirm.as_dict())
                state["crit"] = confirm.total >= target_ac
                state["stage"] = "damage"

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
                hit = self._apply_damage(defender, amount, weapon["type"])
                state["effects"].append(hit)
                # What the *defender* lost, not what the die said. A hit for 12 against
                # DR 5 is a hit for 7, and the GM must be told the second number or it
                # will narrate a wound nobody took.
                state["tells"].append(
                    f"{actor.name} {'critically ' if state.get('crit') else ''}hits "
                    f"{defender.name} for {hit['amount']} {weapon['type']}"
                    + (f" ({hit['note']})." if hit["note"] else "."))
                # A coated blade delivers its dose on the first thing it cuts, and then it
                # is gone. Spent on the hit rather than on the swing: a poison wiped off
                # by a miss is a dose nobody got.
                for extra in self._deliver_coating(actor, defender, weapon_key):
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
                state["i"] += 1
                state["stage"] = "attack"

        rolls = [_roll_from_dict(r) for r in state["rolls"]]
        crossed = self._hp_state_effects(defender)
        effects = list(state["effects"]) + crossed
        any_hit = any(e.get("kind") == "damage" for e in effects)
        # First blood is remembered only once the attack completes, so the decision
        # "is this a subsequent attack?" cannot flip between a suspension and its resume.
        self.scene.attacked.add(f"{actor.ref}>{defender.ref}")
        return Outcome(
            intent_id=intent.id, op="attack", rolls=rolls,
            dc={"value": target_ac, "explain": ac_note, "flat_footed": flat_footed},
            verdict="hit" if any_hit else "miss",
            effects=effects,
            tell=" ".join(state["tells"]) + self._hp_state_tell(crossed),
            because=intent.because,
        )

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

        flat_footed = (
            defender.has_condition("flat-footed")
            or not self.scene.initiative
            or not self._has_acted(defender.ref)
        )
        cmd_mods = defender.cmd_modifiers(
            flat_footed, maneuver=str(intent.params.get("manoeuvre") or "") or None)
        cmd = sum(x.value for x in cmd_mods)
        cmd_note = f"CMD {cmd}" + (" (flat-footed)" if flat_footed else "")

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
            roll = self._roll_or_suspend_stage(
                intent, actor, mods, f"{m['name'].title()} (CMB)", cmd, partial,
                partial.get("attack_state") or {}, "1d20",
            )
            natural = roll.natural
            margin = roll.total - cmd
            # A natural 20 always succeeds and a natural 1 always fails, whatever the
            # arithmetic says.
            if natural == 20:
                verdict, margin = "success", max(margin, 0)
            elif natural == 1:
                verdict, margin = "failure", min(margin, -1)
            else:
                verdict = "success" if margin >= 0 else "failure"

        effects: list[dict] = []
        bits: list[str] = []

        if verdict == "success":
            bits.append(
                f"{actor.name} {m['name']}s {defender.name}"
                + (" automatically — it cannot resist" if automatic else f" by {margin}")
                + f": {m['effect']}."
            )
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
                    bits.append(extra.capitalize().rstrip(".") + ".")
                    dc_cond = (m.get("degree_condition") or {}).get(over)
                    if dc_cond:
                        defender.add_condition(dc_cond, source=m["name"])
                        effects.append({"ref": defender.ref, "kind": "condition",
                                        "condition": dc_cond, "from": m["name"]})
            if m.get("per_5_over") and margin >= 5:
                bits.append(f"{margin // 5} x {m['per_5_over']}.")
        else:
            bits.append(
                f"{actor.name}'s {m['name']} fails against {defender.name} by {-margin}."
            )
            # Failing by 10 or more can turn the manoeuvre back on you.
            if m.get("backfire") and margin <= -10:
                bits.append(m["backfire"].capitalize() + ".")
                back = m.get("backfire_condition")
                if back:
                    actor.add_condition(back, source=f"failed {m['name']}")
                    effects.append({"ref": actor.ref, "kind": "condition",
                                    "condition": back, "from": f"failed {m['name']}"})

        crossed = self._hp_state_effects(defender)
        effects.extend(crossed)
        return Outcome(
            intent_id=intent.id, op="attack", rolls=[roll] if roll else [],
            dc={"value": cmd, "explain": cmd_note, "flat_footed": flat_footed,
                "breakdown": [x.as_dict() for x in cmd_mods]},
            verdict=verdict, margin=margin, effects=effects,
            tell=" ".join(bits) + self._hp_state_tell(crossed),
            because=intent.because,
        )

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
        if target and target in self.scene.actors and target not in pc_side:
            them = [target]
        else:
            them = [r for r in standing if not self.scene.actors[r].is_pc]
        combatants = pc_side + [r for r in them if r in standing]
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
        init = self.dice.d20(a.initiative_modifiers(), label=f"{a.name} initiative",
                             visibility="hidden")
        self.scene.initiative.append((ref, init.total))
        self.scene.initiative.sort(key=lambda t: -t[1])
        current = self.scene.current_ref()
        self.scene.turn = next(
            (i for i, (r, _) in enumerate(self.scene.initiative) if r == current),
            self.scene.turn)
        self.scene.sides.setdefault(side, []).append(ref)
        if ref not in self.scene.positions and self.scene.grid is not None:
            self.scene.place_by_zone([ref])
        return True

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

        Two turns is time to loot and say a word over them; after that they
        depart quietly, whether or not the player ever walks away. The dying get
        the same treatment as `leave_behind`: their story resolves rather than
        printing "bleeding out" beats forever. No-op mid-encounter.
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
                self.scene.depart(ref)
                self.scene.fallen.pop(ref, None)
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
                                    founded=self.scene.founded)

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
                founded=self.scene.founded)
            target = places_mod.find(known, place_id)
            if target is None:
                raise ValueError(f"place_party: no place {place_id!r} here; the places "
                                 f"are {[p.id for p in known]}")
        else:
            target = self.places()[0]
        # Placement is not movement. `move` unseats — drops the zone, the initiative
        # slot, the side — and refuses the PC mid-encounter; a save loaded mid-fight
        # from before places existed has all of those and must keep them. Nothing is
        # walked out of, so the cast ledger stays too. The third and last writer of
        # `Actor.at`, and it only ever writes the party's own place.
        pc = self.scene.pc()
        self.scene.at = target.id
        if pc is not None:
            pc.at = target.id
        for a in self.scene.people.values():
            if not a.at:
                a.at = target.id

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
        want = str(intent.params.get("biome") or "").strip().lower()
        place = " ".join(str(intent.params.get("place") or "").split())
        if not want and not place:
            from . import places as places_mod

            return self._refuse(
                intent, "Nobody moves: where to? From here you can reach "
                        f"{', '.join(p.name for p in self.places())}, or the open ground "
                        f"outside — {', '.join(sorted(biomes.BIOMES))}.")
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
            # Open ground of a kind the party is not on: the region's first place.
            going_to = places_mod.region_set(
                places_mod.location_of(known[0].id) or self.scene.location_id, biome)[0]

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

        pc = self.scene.pc()
        was_place = self.scene.at
        was_ground = here.terrain
        moved = going_to.id != was_place

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
            town = places_mod.location_of(was_place) or self.scene.location_id
            law = states.standing_with_the_law(pc, town)
            at_gate = " ".join(going_to.name.split()).lower().removeprefix("the ") == "gate"
            open_road = bool(want) and was_ground == places_mod.URBAN \
                and going_to.terrain != places_mod.URBAN
            # A way past the watch that somebody showed you — a scheme's witness, a
            # smuggler's door — is a tag the player holds (`knows.way-past-gate`), and
            # the road is open to them by it; the gate itself stays shut.
            has_way = pc.has_state("knows.way-past-gate")
            if law and (at_gate or (open_road and not has_way)):
                found = self.world.get(self.scene.location_id) if self.world else None
                town_name = str(getattr(found, "name", "") or "the town")
                if law == "wanted":
                    other_ways = [p.name for p in known
                                  if p.origin and not p.described_only
                                  and p.terrain != places_mod.URBAN]
                    how = (f"Leave by another way — {', '.join(other_ways)} — or "
                           f"clear your name."
                           if other_ways else
                           "Leave by another way — ground you have founded or "
                           "ventured into outside the walls — or clear your name.")
                    return self._refuse(
                        intent, f"{pc.name} is wanted in {town_name}, and the gate is "
                                f"where the watch stands: they would take you at the "
                                f"arch. {how}")
                law_line = (f"Your name is on the watch's lips in {town_name}: the "
                            f"guards at the gate look twice, and let you through.")
        left: list[str] = []
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
                    left.append(a.name)
            if pc is not None:
                self.scene.move(pc.ref, going_to.id)
                # Between the walls and the open ground is an hour on foot either way
                # — the playtest measured a two-hour wild place reached in no time, so
                # a scheme keyed on the hours never came. Inside the walls, or across
                # the same open ground, stays free: the map is small there.
                if (was_ground == places_mod.URBAN) != (going_to.terrain == places_mod.URBAN):
                    self.scene.advance(60, charge_body=False)
            else:
                # A scene with no player (some tests) is placed rather than moved: the
                # party record has three writers and this door is not a fourth.
                self.place_party(going_to.id)
            for ref in escorts:
                self.scene.move(ref, going_to.id)
            # After every move, for the reason `settle_relations` gives.
            self.scene.settle_relations()

        note = str(intent.params.get("note") or "").strip()
        bits = []
        if not moved:
            bits.append(f"You are already at {going_to.name}.")
        if going_to.terrain != was_ground:
            bits.append(f"The ground changes: {biomes.describe(going_to.terrain).lower()}.")
        if moved:
            bits.append(f"You are at {going_to.name} now.")
        if fight_ended:
            bits.append("The fight is left behind." + xp_line)
        if stayed_down:
            bits.append(f"{', '.join(stayed_down)} cannot come: they stay where they fell.")
        bits.extend(dying_tells)
        if left:
            bits.append(f"Left behind: {', '.join(left)}.")
        if law_line:
            bits.append(law_line)
        if note:
            bits.append(note)
        return Outcome(
            intent_id=intent.id, op="travel",
            effects=[{"kind": "biome", "biome": going_to.terrain, "was": was_ground,
                      "left": left, "place": self.scene.at, "was_place": was_place,
                      "fight_ended": fight_ended}],
            tell=" ".join(bits),
            because=intent.because,
        )

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
        if not body.is_down:
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
        if places_mod.find(known, name) is not None:
            return self._refuse(intent, f"{name} is already a place here.")
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
        place = places_mod.mint(parent, name, str(intent.params.get("about") or "")[:120],
                                owner=owner.ref if owner is not None else "",
                                origin="found")
        self.scene.founded.append(place.as_dict())
        slug = place.id.rsplit("/", 1)[-1]
        if owner is not None:
            owner.apply_effect(ActiveEffect(
                name=f"holds {name}", kind="situation", key=f"holds:{place.id}",
                source=f"place:{place.id}", origin="found",
                duration="until-dismissed", tags=(f"holds.place.{slug}",)))
        pc = self.scene.pc()
        cards_mod.open_card(self.scene, cards_mod.Card(
            id=f"place-{slug}", title=f"{name}, off {parent.name}",
            facts=[f"Founded from {parent.name}"
                   + (f", held by {owner.name}" if owner is not None else "") + "."],
            tags=("situation.place", cards_mod.TAG_PLAY),
            people=[owner.ref] if owner is not None else [], place=place.id,
            clock_max=6, origin="found"), turn=0)
        held = f", held by {owner.name}" if owner is not None else ""
        return Outcome(
            intent_id=intent.id, op="found",
            effects=[{"kind": "place", "id": place.id, "name": name,
                      "parent": parent.id, "owner": place.owner}],
            tell=f"{name} is a place now, off {parent.name}{held}. "
                 f"{pc.name if pc else 'The party'} can go there from {parent.name}.",
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
        travel = Intent(op="travel", actor=actor.ref, because=intent.because,
                        params={"place": head.id, "with": list(intent.params.get("with") or [])},
                        visibility="hidden", id=intent.id, origin=intent.origin,
                        origin_name=intent.origin_name)
        moved = self._op_travel(travel, {})
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
            target.clear_states("attitude")
        cond = target.add_condition(key, rounds, source=intent.because)
        return Outcome(
            intent_id=intent.id, op="condition",
            effects=[{"ref": target.ref, "kind": "condition", "condition": key,
                      "rounds_left": cond.rounds_left}],
            tell=f"{target.name} is {cond.name.lower()}"
                 + (f" for {cond.rounds_left} rounds." if cond.rounds_left else "."),
            because=intent.because,
        )

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
        from .crafting import Stock

        actor = self.scene.actors[intent.actor]
        item_id = str(intent.params["item"]).strip().lower()
        count = max(1, int(intent.params.get("count") or 1))

        seller = intent.params.get("from_")
        if seller and seller not in self.scene.actors:
            return self._refuse(intent, self._elsewhere(seller) or f"There is no {seller} here to buy from.")
        who = self.scene.actors[seller].name if seller else "the stallholder"

        place = str(self.scene.location_id or "nowhere")
        stall = str(intent.params.get("stall") or seller or "market")
        day = market_mod.day_of(self.scene.clock_minutes)

        counter = market_mod.on_sale(place, stall, day, self.scene.market_taken)
        found = next((m for m in counter if str(getattr(m, "id", "")).lower() == item_id),
                     None)
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
        # Onto the shelf as a crafted-shape entry, which is the one container the
        # inventory panels and the benches both already read.
        actor.add_stock(Stock(base=found.name, tier=str(getattr(found, "tier", "common")),
                              potency=1.0, craft=str(getattr(found, "track", "") or "")),
                        count)
        for _ in range(count):
            market_mod.mark_sold(self.scene.market_taken, item_id, place, stall, day)

        return Outcome(
            intent_id=intent.id, op="buy",
            effects=[{"ref": actor.ref, "kind": "bought", "item": found.name,
                      "count": count, "paid_cp": cp}],
            tell=f"{actor.name} pays {who} {pricing.as_text(price)} for {count}x "
                 f"{found.name}. ({goods.purse_line(actor.purse, coins)} left.)",
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
        """
        actor = self.scene.actors[intent.actor]
        spell = spells_mod.get(str(intent.params["spell"]))
        level = casting.spell_level_for(actor, spell)
        dc = casting.save_dc(actor, level)
        cl = casting.caster_level(actor)

        # The slot is spent once, on the way in, and never again on a resume. `state`
        # living in `partial` is what distinguishes the two: a cast that suspends for the
        # player's damage roll comes back through here with its state, and re-spending
        # would cost a second slot for one fireball.
        state = partial.get("cast_state")
        if state is None:
            pool = casting.slot_pool(level)
            spent = actor.spend_pool(pool, 1)
            if not spent["ok"]:
                # The mid-list case, measured: six casts in one list PASS validation
                # against two prepared slots, because `_check_cast` reads the count
                # before anything runs. The third used to raise here — after two slots
                # were gone and two fireballs had landed — and the 502 threw all of it
                # away. Printed instead: what was cast stands, and this one does not.
                # Validate is NOT taught to simulate the list; that is a second resolver.
                return self._refuse(
                    intent, f"{actor.name} has no {pool} left, so {spell.name} is not "
                            f"cast. What was cast before it stands.")
            if casting.caster_data(actor).get("prepare_from") == "spellbook":
                casting.unprepare(actor, spell.id, 1)
            state = {"stage": "dice", "i": 0, "rolls": [], "effects": [], "tells": []}
        pool = casting.slot_pool(level)

        targets = intent.targets() or ([intent.params["at"]] if intent.params.get("at")
                                       else [])
        save = (spell.saving_throw or "").strip()
        sr = (spell.spell_resistance or "").strip()
        plan = spells_mod.casting_plan(spell, cl)
        dice = plan["dice"]

        bits = [f"caster level {cl}"]
        if save and save.lower() not in ("none", "no", "—", "-"):
            bits.append(f"{save}, DC {dc}")
        if sr and sr.lower() not in ("no", "none", "—", "-"):
            bits.append(f"spell resistance {sr}")
        if spell.duration:
            bits.append(spell.duration)

        # Everything a narrator, a player and a GM correcting a conversion all need. The
        # keys that were here before are untouched; `effects_converted` is new and is the
        # one a GM most needs, because 385 of these numbers were read by a machine and
        # nobody has checked them.
        cast_effect = {
            "ref": actor.ref, "kind": "cast", "spell": spell.id,
            "name": spell.name, "spell_level": level, "dc": dc,
            "caster_level": cl, "save": save, "spell_resistance": sr,
            "duration": spell.duration, "range": spell.range,
            "area": spell.area or spell.effect or spell.targets,
            "targets": targets, "slot": pool,
            "slots_left": casting.slots_left(actor, level),
            "element": spell.element, "dice": dice,
            "range_feet": spells_mod.range_feet(spell, cl),
            "effects": spell.effects, "effects_converted": spell.effects_converted,
        }

        if not spell.effects:
            # One of the 2,655. Unchanged, deliberately: the outcome states the facts and
            # whatever the GM then declares arrives as its own validated intent.
            return Outcome(
                intent_id=intent.id, op="cast", effects=[cast_effect],
                tell=f"{actor.name} casts {spell.name} ({'; '.join(bits)}).",
                because=intent.because,
            )

        live = [ref for ref in targets if ref in self.scene.actors]

        if dice and state["stage"] == "dice":
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
                saved = save_roll.total >= dc
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
                    f"{SAVES[plan['save']]} save ({save_roll.total} against DC {dc})"
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
                hit = self._apply_damage(target, amount, plan["damage_type"],
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

        tells = [f"{actor.name} casts {spell.name} ({'; '.join(bits)})."]
        if dice:
            tells.append(f"{dice} — {state.get('rolled', 0)}.")
        tells.extend(state["tells"])
        crossed_said = self._hp_state_tell(crossed).strip()
        if crossed_said:
            tells.append(crossed_said)

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
                 "choose_one", "bundle")

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
        return self._stand_by(spec, ctx)

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
        where = (f" over {len(made.squares)} squares" if made.squares else "")
        # Said when the thing wanted squares and there was nowhere to put them. The first
        # version tested `not made.squares`, which is true in exactly the case the note is
        # for — so the note never appeared on a mapless scene and always would have on a
        # dancing light.
        note = "" if self.scene.has_grid or made.terrain == "none" else \
            " — there is no map in this scene, so it is placed in the fiction only"
        return ([{"kind": "manifest", **made.as_dict()}],
                [f"{made.what[:1].upper()}{made.what[1:]}{where}{note}."])

    def _squares_for(self, spec: dict, ctx: dict) -> list[tuple[int, int]]:
        """The squares a manifestation covers, from the grid's own area functions.

        `rules/grid.py` already draws a burst, a line and a cone for spell areas, so a
        fog cloud is `burst(centre, 20)` and nothing here has to know what a radius is.
        A scene with no map gets an empty list and the thing still exists — a
        manifestation without squares is fiction, not a bug.
        """
        if not self.scene.has_grid:
            return []
        centre = ctx.get("square")
        if centre is None:
            return []
        size = int(spec.get("size") or 0)
        shape = str(spec.get("shape") or "radius")
        if not size or shape == "point":
            return [tuple(centre)]
        if shape == "line":
            towards = ctx.get("towards") or (centre[0] + 1, centre[1])
            return sorted(gridmod.line(tuple(centre), tuple(towards), size))
        if shape == "cone":
            return sorted(gridmod.cone(tuple(centre), str(ctx.get("facing") or "e"), size))
        if shape in ("wall", "square"):
            span = max(1, size // gridmod.SQUARE_FT)
            return [(centre[0] + dx, centre[1]) for dx in range(span)] if shape == "wall" \
                else [(centre[0] + dx, centre[1] + dy)
                      for dy in range(span) for dx in range(span)]
        return sorted(gridmod.burst(tuple(centre), size))

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
                f"cast spells.", "legality", index,
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
                "legality", index,
            )
        if level > casting.highest_spell_level(actor):
            raise IntentError(
                f"cast: {spell.name} is a level {level} spell and {actor.name} is a "
                f"level {actor.level} {actor.char_class} — they reach level "
                f"{casting.highest_spell_level(actor)}.", "legality", index,
            )
        if not casting.can_cast_level(actor, level):
            ability = casting.casting_ability(actor)
            raise IntentError(
                f"cast: a level {level} spell needs {ability.title()} {10 + level} and "
                f"{actor.name} has {actor.ability_score(ability)}.", "legality", index,
            )
        if not casting.knows(actor, spell):
            raise IntentError(
                f"cast: {spell.name} is not in {actor.name}'s spellbook.",
                "legality", index,
            )
        if data.get("prepare_from") == "spellbook" and \
                casting.prepared_count(actor, spell.id) < 1 and level > 0:
            raise IntentError(
                f"cast: {actor.name} did not prepare {spell.name} today.",
                "legality", index,
            )
        if casting.slots_left(actor, level) < 1:
            raise IntentError(
                f"cast: {actor.name} has no level {level} slots left.",
                "legality", index,
            )

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
            self.scene.positions[ref] = tuple(square)
            # The zone is now measured rather than taken on trust. The GM may still have
            # said "near"; if the square it also gave is forty feet away, the square wins.
            self.scene.resync_zones()
            zone = self.scene.zones.get(ref, zone)
            cost = self._move_cost(ref, from_square, tuple(square))
            crossed = f" ({cost} ft)" if cost is not None else ""
            return Outcome(
                intent_id=intent.id, op="move",
                effects=[{"ref": ref, "kind": "position", "from": from_square,
                          "to": tuple(square), "feet": cost, "zone": zone}],
                tell=f"{actor.name} moves to {zone}{crossed}.",
                because=intent.because,
            )

        self.scene.zones[ref] = zone
        return Outcome(
            intent_id=intent.id, op="move",
            effects=[{"ref": ref, "kind": "zone", "from": was, "to": zone}],
            tell=f"{actor.name} moves from {was} to {zone}.",
            because=intent.because,
        )

    def _move_cost(self, ref: str, start: tuple[int, int] | None,
                   end: tuple[int, int]) -> int | None:
        """What the move actually cost, routed around terrain and other creatures.

        `None` when there is no route — which is not the same as free, and is why this
        returns an optional rather than falling back to straight-line distance. A creature
        that has to go the long way round a wall pays for the long way.
        """
        if start is None or self.scene.grid is None:
            return None
        reach = self.scene.grid.reachable(
            start, 10_000, size=self.scene.actors[ref].size,
            occupied=self.scene.occupied(ignore=ref))
        return reach.get(end)

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

    def _lay_battlefield(self, sides: dict) -> None:
        """The ground. The map tray has promised "a grid is laid out when a fight
        starts" since the grid shipped, and nothing anywhere ever laid one —
        Scene.grid was assigned in tests and nowhere else, so every real fight played
        on a map that said no ground was mapped. Laid here, once, and only if the GM
        has not already put one down; combatants without positions are placed by
        their zones, the player's side on the left and everyone else a zone's worth
        of squares away. One helper for both doors a fight comes in by —
        `begin_encounter`, and the swing that auto-starts one."""
        if self.scene.grid is not None:
            return
        from .grid import Grid

        self.scene.grid = Grid()
        mid = self.scene.grid.height // 2
        pc_side, foe_row = 4, 0
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
                    self.scene.grid.width = pc_side + away + 2
                if has_pc:
                    self.scene.positions[ref] = (pc_side, mid + i)
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
                    self.scene.positions[ref] = (
                        min(self.scene.grid.width - 1, pc_side + away),
                        max(0, min(self.scene.grid.height - 1, row)))
                    foe_row += 1
        # The bystanders — in the room, in no side — go on the board too, at their
        # own zones, so the map shows the room the prose described and not only the
        # two people hitting each other in it.
        bystanders = [r for r in self.scene.actors
                      if r not in self.scene.positions
                      and not any(r in refs for refs in sides.values())]
        if bystanders:
            self.scene.place_by_zone(bystanders)
        self.scene.resync_zones()

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
        if giver is not None:
            held = (giver.purse if denom else giver.goods)
            moved = min(count, int(held.get(denom or item, 0)))
            if moved:
                held[denom or item] -= moved
                if held[denom or item] <= 0:
                    del held[denom or item]
        else:
            moved = count           # it came from the world, which never runs out

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
                elif kind == "consumable":
                    from .crafting import Stock

                    taker.add_stock(Stock(base=item, tier="common"), moved)

        what = f"{moved} × {item}" if moved != 1 else item
        if giver is not None and taker is not None:
            tell = f"{giver.name} hands {taker.name} {what}{paid}."
        elif taker is not None:
            tell = f"{taker.name} takes {what}{paid}."
        elif giver is not None:
            tell = f"{giver.name} parts with {what}."
        else:
            tell = f"{what} changes hands."
        if giver is not None and not moved:
            tell = f"{giver.name} has no {item} to give."

        return Outcome(
            intent_id=intent.id, op="give",
            effects=[{"ref": (taker or giver).ref if (taker or giver) else "",
                      "kind": "give", "item": denom or item, "count": moved,
                      "purse": dict(taker.purse) if taker else {},
                      "goods": dict(taker.goods) if taker else {}}],
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

    def _refuse(self, intent: Intent, why: str) -> Outcome:
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
        """
        return Outcome(intent_id=intent.id, op=intent.op, effects=[],
                       tell=" ".join(str(why).split()), because=intent.because)

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
        hours = result["hours"]
        # Everyone, not only the sleeper. Rest ticked the resting actor alone, so an
        # NPC standing in the same scene kept every timed buff through an eight-hour
        # night. `advance` also leaves the body alone: `Actor.rest` has already called
        # survival.sleep, and a night deliberately costs no food or water.
        # `charge_body=False`: `Actor.rest` has already called survival.sleep, and a
        # night deliberately costs no food or water — pinned by tests/test_survival.py.
        ended = self.scene.advance(hours * 60, charge_body=False)["ended"]

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
        for n in range(max(1, int(count))):
            actor = instantiate(template, scene=self.scene, name=name,
                                world_entity_id=from_entity_id, index=n)
            self.scene.add(actor)
            made.append({"ref": actor.ref, "name": actor.name})
            # Someone who arrives mid-fight rolls in. Without this they were on the
            # board but not in the order, so they never took a turn and the fight could
            # not end — `sides_standing` never counted them either.
            if self.scene.in_encounter:
                init = self.dice.d20(actor.initiative_modifiers(),
                                     label=f"{actor.name} initiative", visibility="hidden")
                self.scene.initiative.append((actor.ref, init.total))
                self.scene.initiative.sort(key=lambda t: -t[1])
                self.scene.turn = next(
                    (i for i, (r, _) in enumerate(self.scene.initiative)
                     if r == self.scene.current_ref()), self.scene.turn
                )
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
        target = self.scene.actors[pk.target]
        d = target.take_damage(pk.amount, pk.dtype, pk.traits, pk.lethality)
        effect = self._describe_damage(target, d, pk.lethality)
        if pk.notes:
            effect["intercepted"] = pk.notes
            through = guards_mod.describe(pk.notes)
            effect["note"] = f"{effect['note']}, {through}" if effect["note"] else through
        return effect

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
            said.append(line.format(name=who.name if who else "they"))
        return (" " + " ".join(said)) if said else ""


# --- (de)serialisation for the suspend/resume round trip --------------------------------

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
        return f"{name} rides out {source} ({e.get('roll')} against DC {e.get('dc')})."
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
    if d.get("lethality") == "nonlethal" and d.get("taken"):
        bits.append(f"non-lethal now {d.get('nonlethal')}")
    return f"{d['rolled']}, " + ", ".join(bits) if bits else ""


def _multiply_dice(notation: str, mult: int) -> str:
    """1d6 x3 -> 3d6. A critical multiplies the dice, not the rolled result."""
    if mult <= 1:
        return notation
    count, faces, flat = Dice().parse(notation)
    out = f"{count * mult}d{faces}"
    if flat:
        out += f"{flat:+d}"
    return out


def _to_rounds(amount: int, unit: str) -> int:
    return {"round": 1, "minute": 10, "hour": 600, "day": 14400}[unit] * int(amount)


def _to_minutes(amount: int, unit: str) -> int:
    return {"round": 0, "minute": 1, "hour": 60, "day": 1440}[unit] * int(amount)
