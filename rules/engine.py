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
from dataclasses import dataclass, field
from typing import Any

from . import biomes
from . import goods
from . import casting
from . import compulsion
from . import consumables
from . import crafting
from . import dc as dc_mod
from . import foraging
from . import ingredients as ing_mod
from . import resources
from . import survival
from . import worldclass
from . import grid as gridmod
from . import guards as guards_mod
from . import reactions
from . import spells as spells_mod
from . import weapons as weapons_mod
from .guards import Guard, Packet
from .dice import Dice, Modifier, Roll
from .grid import Grid
from .intents import Intent, IntentError, parse_all
from .sheet import Actor
from .tables import (
    ABILITY_FULL, MANEUVERS, SAVES, SIZE_ORDER, WEAPONS, normalise_damage_type,
)


# --- Scene state -------------------------------------------------------------------

@dataclass
class Scene:
    """Everything the engine owns. The world agent may read this and writes none of it —
    see docs/intent-protocol.md §8."""
    location_id: str | None = None
    actors: dict[str, Actor] = field(default_factory=dict)
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
    initiative: list[tuple[str, int]] = field(default_factory=list)
    # Who has taken a turn this encounter. A combatant who has not acted is flat-footed,
    # which is usually several points of AC and is the thing an ambush is *for*.
    acted: set[str] = field(default_factory=set)
    round: int = 0
    clock_minutes: int = 0
    log: list[dict] = field(default_factory=list)
    # The ground underfoot, which decides what can be foraged here. Defaults from the
    # world's own Biomes/Terrain facts when a campaign starts, and the GM moves it as the
    # party travels.
    biome: str = ""

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
    # The scene owns no randomness of its own; the engine lends it one for the
    # round tick, so stabilisation rolls come from the same seeded stream as
    # everything else and a scene stays reproducible.
    _dice: Any = None

    def add(self, actor: Actor, zone: str = "near", at: tuple[int, int] | None = None) -> Actor:
        self.actors[actor.ref] = actor
        self.zones[actor.ref] = zone
        if at is not None:
            self.positions[actor.ref] = (int(at[0]), int(at[1]))
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
        return next((a for a in self.actors.values() if a.is_pc), None)

    # --- turn order -------------------------------------------------------------------

    @property
    def in_encounter(self) -> bool:
        return bool(self.initiative) and self.turn >= 0

    def current_ref(self) -> str | None:
        if not self.in_encounter:
            return None
        return self.initiative[self.turn % len(self.initiative)][0]

    def conscious(self, ref: str) -> bool:
        """Still up, and still in the fight.

        Exactly 0 hit points is *disabled*, not unconscious: you are on your feet and
        may take a single action, at the cost of a hit point. Requiring `hp > 0` here
        dropped a disabled character out of the initiative order and ended the fight
        around them while they were still standing.
        """
        a = self.actors.get(ref)
        if not a or not a.can_act():
            return False
        return a.hp > 0 or (a.hp == 0 and not a.has_condition("unconscious"))

    def advance_turn(self) -> str | None:
        """Move to the next combatant who can still act, and return their ref.

        Skips the dead and unconscious rather than stalling on them, and ends the
        encounter when only one side is left standing. Without this a fight had no way
        to proceed past the player's first swing: initiative was rolled and then nothing
        ever consulted it.
        """
        if not self.initiative:
            return None
        for step in range(1, len(self.initiative) + 1):
            nxt = (self.turn + step) % len(self.initiative)
            if nxt <= self.turn:
                self.round += 1
                # Attacks of opportunity refill at the top of the round, not on your own
                # turn: the allowance is what you may do while other people act.
                self.reacted = {}
                for a in self.actors.values():
                    a.tick_conditions(1)
                    a.tick_pools(1)
                    compulsion.tick(a, 1)
                self.bleeding = [r for r in (
                    a.bleed_out(self._dice) for a in self.actors.values()
                ) if r]
            if self.conscious(self.initiative[nxt][0]):
                self.turn = nxt
                self.acted.add(self.initiative[nxt][0])
                return self.initiative[nxt][0]
        return None                      # nobody left standing

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
        self.sides = {}
        # The battlefield goes with the fight. `begin_encounter` lays a grid when none
        # exists, and the side panel's own words are "there is no grid outside a fight";
        # here rather than only in the end_encounter *op*, because most fights end by
        # a side emptying inside the NPC-turn loop, which calls this directly.
        self.grid = None
        self.positions.clear()

    def depart(self, ref: str) -> Actor | None:
        """Take one creature out of the scene, and out of every structure that names it.

        The structures are the point. A first version that only deleted from `actors`
        would leave the ref in the initiative order, the sides, the zones, the guard
        arrangements and the reaction ledger — five places for a ghost to keep acting
        from. The 2026-08-22 playtest produced exactly that ghost by never removing
        anybody at all: a gatekeeper wounded in the city travelled inside the scene to
        the forest and took an NPC turn after every player turn for the rest of the
        session.

        The PC is refused: a scene without its player is not a scene, it is a bug.
        """
        actor = self.actors.get(ref)
        if actor is None or actor.is_pc:
            return None

        # The initiative order shrinks, and `turn` must go on pointing at the same
        # creature — an index into a list that just changed length is how a removal
        # hands somebody else's turn to the wrong side of the fight.
        current = self.initiative[self.turn][0] if 0 <= self.turn < len(self.initiative) else None
        self.initiative = [(r, roll) for r, roll in self.initiative if r != ref]
        if current == ref or current is None:
            self.turn = -1 if not self.initiative else min(self.turn, len(self.initiative) - 1)
        else:
            self.turn = next(i for i, (r, _) in enumerate(self.initiative) if r == current)

        del self.actors[ref]
        self.zones.pop(ref, None)
        self.positions.pop(ref, None)
        self.acted.discard(ref)
        self.reacted = {k: v for k, v in self.reacted.items()
                        if not k.startswith(f"{ref}:")}
        self.guards = [g for g in self.guards if ref not in (g.guardian, g.protects)]
        self.sides = {side: [r for r in refs if r != ref]
                      for side, refs in self.sides.items()}
        return actor


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

    def as_dict(self) -> dict:
        return {"owner": self.owner, "at": list(self.at) if self.at else None,
                "amount": self.amount, "source": self.source}

    @classmethod
    def from_dict(cls, d: dict) -> "BloodPool":
        at = d.get("at")
        return cls(owner=d.get("owner", ""),
                   at=tuple(at) if at else None,
                   amount=int(d.get("amount", 1) or 1),
                   source=d.get("source", ""))


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

    # --- Checks 2 and 3 -------------------------------------------------------------

    def validate(self, raw_intents: list) -> list[Intent]:
        """Schema, then refs, then legality. Raises IntentError carrying which check
        failed so the caller can choose between regenerating and repairing."""
        intents = parse_all(raw_intents)
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
        """The refs `spawn` intents in this list are going to mint."""
        from .bestiary import _next_ref

        taken = set(self.scene.actors)
        projected: set[str] = set()
        for intent in intents:
            if intent.op != "spawn":
                continue
            for _ in range(int(intent.params.get("count", 1) or 1)):
                n = 1
                while f"c{n}" in taken or f"c{n}" in projected:
                    n += 1
                projected.add(f"c{n}")
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
        return bool(ref) and (ref in self.scene.actors or ref in (extra or set()))

    def _check_refs(self, intent: Intent, index: int,
                    extra: set[str] | None = None) -> None:
        if intent.op in ("narrate_only", "advance_time", "spawn", "begin_encounter"):
            if intent.op == "begin_encounter":
                for side, refs in intent.params["sides"].items():
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
            raise IntentError(
                f"{intent.op}: unknown actor {intent.actor!r}; known refs are "
                f"{sorted(set(self.scene.actors) | (extra or set()))}. Refer to people by ref, never by name."
                + _SPAWN_HINT,
                "refs", index,
            )
        for t in intent.targets():
            if not self._known(t, extra):
                raise IntentError(
                    f"{intent.op}: unknown target {t!r}; known refs are "
                    f"{sorted(set(self.scene.actors) | (extra or set()))}." + _SPAWN_HINT,
                    "refs", index,
                )
        opposed = intent.params.get("opposed_by")
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

    def _check_legality(self, intent: Intent, index: int) -> None:
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
        if actor and intent.op in ("attack", "move", "check") and not actor.can_act():
            raise IntentError(
                f"{intent.op}: {actor.name} is {actor.blocking_condition().lower()} and "
                f"cannot act",
                "legality", index,
            )
        if intent.op == "attack" and actor:
            key = intent.params.get("weapon") or actor.equipped or "unarmed"
            if not weapons_mod.has(key):
                raise IntentError(
                    f"attack: {actor.name} has no weapon {key!r}", "legality", index
                )
            if actor.weapons and key not in actor.weapons and key != "unarmed":
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
        return self._drive([i.as_dict() for i in intents], [], {})

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
        return self._drive(remaining, done, partial)

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

    # check ------------------------------------------------------------------------------

    def _op_check(self, intent: Intent, partial: dict) -> Outcome:
        actor = self.scene.actors[intent.actor]
        skill = intent.params["skill"]
        mods = actor.skill_modifiers(skill)
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

        effects.extend(self._hp_state_effects(actor))

        return Outcome(
            intent_id=intent.id, op="save", rolls=[roll], dc=resolved_dc.as_dict(),
            verdict=verdict, margin=margin, effects=effects,
            tell=" ".join(tell_bits), because=intent.because,
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
            raise IntentError("attack: needs a target", "schema")
        if targets[0] not in self.scene.actors:
            # Defensive: resolution should never meet a ref that validation passed, but a
            # correction applied after validation once made that untrue and the engine
            # raised KeyError as a 500. An IntentError is recoverable; a KeyError is not.
            raise IntentError(
                f"attack: {targets[0]!r} is not on the board at resolution time",
                "refs",
            )
        defender = self.scene.actors[targets[0]]
        self._ensure_encounter(intent.actor)
        weapon_key = (intent.params.get("weapon") or actor.equipped or "unarmed").lower()
        weapon = actor.weapon(weapon_key)
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

        while state["i"] < len(sequence):
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
                if mult > 1:
                    dmg_mods = [Modifier(m.value * mult, f"{m.source} x{mult}")
                                for m in dmg_mods]
                dmg = self._roll_or_suspend_stage(
                    intent, actor, dmg_mods,
                    f"Damage ({weapon['name']}{' — CRITICAL' if mult > 1 else ''})",
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
                state["i"] += 1
                state["stage"] = "attack"

        rolls = [_roll_from_dict(r) for r in state["rolls"]]
        effects = list(state["effects"]) + self._hp_state_effects(defender)
        any_hit = any(e.get("kind") == "damage" for e in effects)
        return Outcome(
            intent_id=intent.id, op="attack", rolls=rolls,
            dc={"value": target_ac, "explain": ac_note, "flat_footed": flat_footed},
            verdict="hit" if any_hit else "miss",
            effects=effects, tell=" ".join(state["tells"]), because=intent.because,
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
        self._ensure_encounter(intent.actor)

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
        cmd_mods = defender.cmd_modifiers(flat_footed)
        cmd = sum(x.value for x in cmd_mods)
        cmd_note = f"CMD {cmd}" + (" (flat-footed)" if flat_footed else "")

        automatic = not defender.can_act()
        if automatic:
            # "If your target is immobilized, unconscious, or otherwise incapacitated,
            # your maneuver automatically succeeds."
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

        effects.extend(self._hp_state_effects(defender))
        return Outcome(
            intent_id=intent.id, op="attack", rolls=[roll] if roll else [],
            dc={"value": cmd, "explain": cmd_note, "flat_footed": flat_footed,
                "breakdown": [x.as_dict() for x in cmd_mods]},
            verdict=verdict, margin=margin, effects=effects,
            tell=" ".join(bits), because=intent.because,
        )

    def _ensure_encounter(self, initiator: str) -> None:
        """Start a fight the moment someone swings, if one is not already running.

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
            return
        combatants = [r for r, a in self.scene.actors.items() if a.hp > 0]
        if len(combatants) < 2:
            return

        rolls = []
        for ref in combatants:
            a = self.scene.actors[ref]
            r = self.dice.d20(a.initiative_modifiers(), label=f"{a.name} initiative",
                              visibility="hidden")
            rolls.append((ref, r.total))
        rolls.sort(key=lambda t: -t[1])

        self.scene.initiative = rolls
        self.scene.round = 1
        self.scene.sides = {
            "pc": [r for r in combatants if self.scene.actors[r].is_pc],
            "them": [r for r in combatants if not self.scene.actors[r].is_pc],
        }
        self.scene.acted = {initiator}
        self.scene.turn = next(
            (i for i, (ref, _) in enumerate(rolls) if ref == initiator), 0
        )

    def _has_acted(self, ref: str) -> bool:
        """Whether this combatant has taken a turn in the current encounter."""
        return ref in self.scene.acted

    # damage, condition, move, time, spawn, encounter ------------------------------------

    def _op_damage(self, intent: Intent, partial: dict) -> Outcome:
        ref = intent.params.get("to") or (intent.targets() or [None])[0]
        if not ref:
            raise IntentError("damage: needs a target", "schema")
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
        effects = [hit]
        # Every creature the blow actually reached, which after interception is not always
        # the one it was aimed at. Keyed off the effects rather than off `target`, because
        # a redirected blow that drops the guardian has to knock *them* out.
        for ref in self._hurt_refs(hit):
            effects.extend(self._hp_state_effects(self.scene.actors[ref]))
        return Outcome(
            intent_id=intent.id, op="damage", rolls=[roll] if roll else [],
            effects=effects,
            tell=self._damage_tell(hit),
            because=intent.because,
        )

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

    def _op_buff(self, intent: Intent, partial: dict) -> Outcome:
        """A timed numeric bonus lands on an actor.

        The op `use_item` was missing: a drunk tea's `save_mod` fell through
        `_spec_to_intents` and the dose was spent for nothing. Duration arrives in the
        authored unit and is kept in rounds, the clock every other timed thing ticks on.
        """
        who = intent.params.get("to") or intent.actor
        actor = self.scene.actors.get(who)
        if actor is None:
            raise IntentError(f"buff: unknown target {who!r}", "refs")
        kind = str(intent.params.get("type", "save_mod"))
        target = str(intent.params.get("target", ""))
        amount = int(intent.params.get("amount", 0) or 0)
        if not target or not amount:
            raise IntentError("buff: needs a target and a non-zero amount", "schema")
        source = str(intent.params.get("source") or "a preparation")
        duration = intent.params.get("duration") or {}
        rounds = None
        if isinstance(duration, dict) and duration.get("amount"):
            per = {"round": 1, "minute": 10, "hour": 600, "day": 14400}
            rounds = int(duration["amount"]) * per.get(str(duration.get("unit", "hour")), 600)
        actor.add_buff(kind, target, amount, source=source, rounds=rounds,
                       note=str(intent.params.get("note", "")))
        span = ""
        if rounds:
            span = f" for {rounds // 600} hour(s)" if rounds >= 600 else \
                   f" for {rounds // 10} minute(s)" if rounds >= 10 else \
                   f" for {rounds} round(s)"
        return Outcome(
            intent_id=intent.id, op="buff",
            effects=[{"ref": actor.ref, "kind": "buff", "type": kind, "target": target,
                      "amount": amount, "rounds": rounds, "source": source}],
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
            raise IntentError("heal: needs somebody to heal", "schema")
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
        for gone in ("dying", "stable", "unconscious", "disabled"):
            if target.hp > 0 and target.has_condition(gone):
                target.remove_condition(gone)

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
        tell = (f"{target.name} " + ", ".join(parts) + "."
                if parts else f"{target.name} is already unhurt.")

        return Outcome(
            intent_id=intent.id, op="heal", rolls=[roll] if roll else [],
            effects=[{"ref": target.ref, "kind": "heal", "amount": healed,
                      "nonlethal_healed": nl_healed, "temp_banked": temp_banked,
                      "hp_after": target.hp, "hp_max": target.hp_max}],
            tell=tell,
            because=intent.because,
        )

    def _op_temp_hp(self, intent: Intent, partial: dict) -> Outcome:
        """Grant temporary hit points, which do not stack — the best source wins."""
        ref = intent.params.get("to") or intent.actor or (intent.targets() or [None])[0]
        if not ref:
            raise IntentError("temp_hp: needs somebody to grant them to", "schema")
        target = self.scene.actors[ref]
        amount = intent.params["amount"]
        roll = None
        if isinstance(amount, str):
            roll = self.dice.roll(amount, label="temporary hit points", visibility="hidden")
            amount = roll.total

        source = str(intent.params.get("source") or intent.because or "").strip()
        result = target.gain_temp_hp(amount, source)
        if "ignored" in result:
            tell = (f"{target.name} already has {result['temp_hp']} temporary hit points "
                    f"from {result['source'] or 'another source'}; these do not stack.")
        else:
            tell = f"{target.name} gains {result['temp_hp']} temporary hit points."
        return Outcome(
            intent_id=intent.id, op="temp_hp", rolls=[roll] if roll else [],
            effects=[{"ref": target.ref, "kind": "temp_hp", "temp_hp": target.temp_hp}],
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
            raise IntentError("ability_damage: needs a target", "schema")
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
        except KeyError as exc:
            raise IntentError(f"ability_damage: {exc}", "schema") from exc

        effects = [{"ref": target.ref, "kind": "ability_damage", **res}]
        bits = [f"{target.name} takes {res['amount']} {ABILITY_FULL[ab]} "
                f"{'drain' if drain else 'damage'} (now {res['score']})."]
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
        if not ref:
            raise IntentError("item_damage: needs whose gear", "schema")
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
        return Outcome(
            intent_id=intent.id, op="item_damage", rolls=[roll] if roll else [],
            effects=[{"ref": target.ref, "kind": "item_damage", **r} for r in results],
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
                # Refused, not silently ignored: an ability that fires with an empty pool
                # is one the player thinks they still have.
                raise IntentError(f"resource: {result['why']}.", "legality")
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
        want = str(intent.params["biome"]).strip().lower()
        biome = biomes.canonical(want)
        if biome is None:
            raise IntentError(
                f"travel: {want!r} is not a biome. The biomes are: "
                f"{', '.join(sorted(biomes.BIOMES))}.",
                "schema")

        kept = {str(r) for r in (intent.params.get("with") or [])}
        left: list[str] = []
        if biome != self.scene.biome:
            fight_ended = self.scene.in_encounter
            if fight_ended:
                self.scene.end_encounter()
            for ref in list(self.scene.actors):
                actor = self.scene.actors[ref]
                if actor.is_pc:
                    continue
                stays = ref not in kept and str(actor.name) not in kept
                cannot_come = (actor.hp <= 0
                               or actor.has_condition("dead")
                               or actor.has_condition("dying")
                               or actor.has_condition("unconscious"))
                if stays or cannot_come:
                    self.scene.depart(ref)
                    left.append(actor.name)
        else:
            fight_ended = False

        was, self.scene.biome = self.scene.biome, biome
        note = str(intent.params.get("note") or "").strip()
        bits = []
        if biome != was:
            bits.append(f"The ground changes: {biomes.describe(biome).lower()}.")
        if fight_ended:
            bits.append("The fight is left behind.")
        if left:
            bits.append(f"Left behind: {', '.join(left)}.")
        if note:
            bits.append(note)
        return Outcome(
            intent_id=intent.id, op="travel",
            effects=[{"kind": "biome", "biome": biome, "was": was, "left": left,
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
            raise IntentError(f"forage refused. {busy}", "legality")

        # The ground underfoot, and nothing else. Foraging used to honour a `biome`
        # parameter, which meant a request could search a forest from the middle of a
        # city — the bench sent one and the GM could invent one. Where you are is a fact
        # the scene owns; `travel` is the only thing that changes it.
        biome = biomes.canonical(str(self.scene.biome or ""))
        if biome is None:
            raise IntentError(
                "forage: nowhere in particular. Set the ground first with "
                "{\"op\": \"travel\", \"params\": {\"biome\": \"forest\"}}.",
                "legality")

        track_id = str(intent.params.get("track") or "herbalist").strip().lower()
        try:
            track = worldclass.get(track_id)
        except KeyError as exc:
            raise IntentError(f"forage: {exc}", "refs") from exc
        level = actor.track(track.id).level
        ceiling = worldclass.tier_rank(track.at(level).max_tier)

        # Foraging takes real time now, a minimum of an hour and as long as the player
        # asks for. The body is consulted for every hour of it — see rules/survival.py —
        # and a character who goes over is stopped at the hour they actually fell over
        # rather than at the end of the stretch they meant to work.
        hours = max(1, int(intent.params.get("hours", 1) or 1))
        toll = survival.pass_hours(actor, hours, self.dice, biome=biome)
        worked = max(1, toll.hours)

        result = foraging.forage(biome, level, ceiling, self.dice, hours=worked,
                                 actor=actor)
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

        self.scene.clock_minutes += worked * survival.MINUTES_PER_HOUR

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

        return Outcome(
            intent_id=intent.id, op="forage",
            effects=[{"ref": actor.ref, "kind": "forage", **result}],
            tell=tell, because=intent.because,
        )

    def _op_condition(self, intent: Intent, partial: dict) -> Outcome:
        ref = intent.params.get("to") or intent.actor or (intent.targets() or [None])[0]
        target = self.scene.actors[ref]
        key = str(intent.params["condition"]).strip().lower()
        duration = intent.params.get("duration")
        rounds = None
        if isinstance(duration, dict):
            rounds = _to_rounds(duration.get("amount", 0), duration.get("unit", "round"))
        elif isinstance(duration, int):
            rounds = duration
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
        resolution = self.run(self.validate(intents))
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
        item_id = str(intent.params["item"]).strip().lower()
        how = str(intent.params.get("how", "drink")).strip().lower()
        target = intent.params.get("to") or intent.actor

        held = actor.stock.get(item_id)
        if held is None or held.count < 1:
            raise IntentError(
                f"use_item: {actor.name} is not carrying {item_id!r}. They have: "
                f"{', '.join(sorted(actor.stock)) or 'nothing crafted'}", "legality")
        if target not in self.scene.actors:
            raise IntentError(f"use_item: unknown target {target!r}", "refs")

        use = consumables.plan(held, how=how, target=target, because=intent.because)
        if not use.ok:
            raise IntentError(f"use_item: {'; '.join(use.problems)}", "legality")

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
                raise IntentError(
                    f"use_item: {actor.name} has no weapon {weapon!r} to coat", "legality")
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
        resolution = self.run(self.validate(use.intents)) if use.intents else None
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

    def _op_cast(self, intent: Intent, partial: dict) -> Outcome:
        """Cast a spell: spend the slot, state the numbers, and stop there.

        The engine owns the slot, the caster level and the save DC, and it owns them
        completely — the GM cannot cast a spell the caster does not have, at a level they
        cannot reach, out of a slot they already spent.

        It does **not** own what the spell does. That lives in the spell's prose, and a
        parser guessing mechanics out of three thousand English paragraphs would produce
        confident wrong numbers, which is the failure mode this project has been bitten by
        most. So the outcome carries the facts a narrator and a player both need — DC, save
        type, caster level, duration, whether spell resistance applies — and any damage or
        condition that follows arrives as its own validated intent.
        """
        actor = self.scene.actors[intent.actor]
        spell = spells_mod.get(str(intent.params["spell"]))
        level = casting.spell_level_for(actor, spell)
        dc = casting.save_dc(actor, level)
        cl = casting.caster_level(actor)

        pool = casting.slot_pool(level)
        spent = actor.spend_pool(pool, 1)
        if not spent["ok"]:
            raise IntentError(f"cast: {actor.name} has no {pool} left", "legality")
        if casting.caster_data(actor).get("prepare_from") == "spellbook":
            casting.unprepare(actor, spell.id, 1)

        targets = intent.targets() or ([intent.params["at"]] if intent.params.get("at")
                                       else [])
        save = (spell.saving_throw or "").strip()
        sr = (spell.spell_resistance or "").strip()

        bits = [f"caster level {cl}"]
        if save and save.lower() not in ("none", "no", "—", "-"):
            bits.append(f"{save}, DC {dc}")
        if sr and sr.lower() not in ("no", "none", "—", "-"):
            bits.append(f"spell resistance {sr}")
        if spell.duration:
            bits.append(spell.duration)

        return Outcome(
            intent_id=intent.id, op="cast",
            effects=[{"ref": actor.ref, "kind": "cast", "spell": spell.id,
                      "name": spell.name, "spell_level": level, "dc": dc,
                      "caster_level": cl, "save": save, "spell_resistance": sr,
                      "duration": spell.duration, "range": spell.range,
                      "area": spell.area or spell.effect or spell.targets,
                      "targets": targets, "slot": pool,
                      "slots_left": casting.slots_left(actor, level)}],
            tell=f"{actor.name} casts {spell.name} ({'; '.join(bits)}).",
            because=intent.because,
        )

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
            raise IntentError(
                f"cast: no spell {intent.params['spell']!r}", "reference", index
            ) from None

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
        penalty = abs(int(intent.params.get("penalty", 4) or 0))

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
        zone = intent.params["zone"]
        was = self.scene.zones.get(ref, "near")
        square = intent.params.get("square")

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
        self.scene.clock_minutes += minutes
        ended: list[str] = []
        for a in self.scene.actors.values():
            ended.extend(f"{a.name}: {name}" for name in a.tick_conditions(rounds))
        tell = f"{amount} {unit}{'s' if amount != 1 else ''} pass."
        if ended:
            tell += " Ended: " + ", ".join(ended) + "."
        return Outcome(
            intent_id=intent.id, op="advance_time",
            effects=[{"kind": "time", "rounds": rounds, "minutes": minutes,
                      "ended": ended}],
            tell=tell, because=intent.because,
        )

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
        # The ground. The map tray has promised "a grid is laid out when a fight starts"
        # since the grid shipped, and nothing anywhere ever laid one — Scene.grid was
        # assigned in tests and nowhere else, so every real fight played on a map that
        # said no ground was mapped. Laid here, once, and only if the GM has not already
        # put one down; combatants without positions are placed by their zones, the
        # player's side on the left and everyone else a zone's worth of squares away.
        if self.scene.grid is None:
            from .grid import Grid

            self.scene.grid = Grid()
            mid = self.scene.grid.height // 2
            pc_side, foe_row = 4, 0
            for side, refs in intent.params["sides"].items():
                has_pc = any(self.scene.actors[r].is_pc for r in refs
                             if r in self.scene.actors)
                for i, ref in enumerate(refs):
                    if ref in self.scene.positions or ref not in self.scene.actors:
                        continue
                    zone = self.scene.zones.get(ref, "near")
                    away = 3 if zone == "near" else 8
                    if has_pc:
                        self.scene.positions[ref] = (pc_side, mid + i)
                    else:
                        self.scene.positions[ref] = (
                            min(self.scene.grid.width - 1, pc_side + away),
                            mid + foe_row)
                        foe_row += 1
            self.scene.resync_zones()
        # The turn pointer starts before the first combatant so the first advance lands
        # on whoever won initiative.
        self.scene.turn = -1
        self.scene.advance_turn()
        names = ", ".join(self.scene.actors[r].name for r, _ in order)
        return Outcome(
            intent_id=intent.id, op="begin_encounter", rolls=rolls,
            effects=[{"kind": "initiative", "order": order}],
            tell=f"Initiative: {names}.", because=intent.because,
        )

    def _op_end_encounter(self, intent: Intent, partial: dict) -> Outcome:
        """Stop the fight. The GM's call: they run, they yield, you get clear."""
        if not self.scene.in_encounter:
            return Outcome(intent_id=intent.id, op="end_encounter",
                           tell="", because=intent.because)
        standing = [self.scene.actors[r].name for r, _ in self.scene.initiative
                    if self.scene.conscious(r)]
        self.scene.end_encounter()
        return Outcome(
            intent_id=intent.id, op="end_encounter",
            effects=[{"kind": "encounter", "ended": True}],
            tell="The fighting stops." + (f" Still standing: {', '.join(standing)}."
                                          if standing else ""),
            because=intent.because,
        )

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
            raise IntentError("give: needs something to give", "schema")
        count = max(1, int(intent.params.get("count", 1) or 1))
        pc = self.scene.pc()

        to_ref = intent.params.get("to") or intent.target or intent.actor
        from_ref = intent.params.get("from_")
        if not to_ref and not from_ref:
            to_ref = pc.ref if pc else None
        taker = self.scene.actors.get(to_ref) if to_ref else None
        giver = self.scene.actors.get(from_ref) if from_ref else None

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
            raise IntentError(
                f"use_ability: {actor.name} has no ability called {wanted!r}. "
                f"Their paths are {', '.join(actor.paths) or 'none'}.", "legality")
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
        for spec in effects:
            if spec.get("inactive"):
                continue
            kind = spec.get("type")
            if kind == "damage" and spec.get("lethality") == "nonlethal":
                roll = self.dice.roll(str(spec["dice"]), label=f"{found}: the cost",
                                      visibility="player")
                rolls.append(roll)
                actor.take_nonlethal(roll.total)
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
                self.scene.pools.append(BloodPool(owner=actor.ref, at=where,
                                                  source=found))
                done.append("blood on the ground")
            elif spec.get("op") == "spend_pools":
                mine = [b for b in self.scene.pools if b.owner == actor.ref]
                take = len(mine) if str(spec.get("count")) == "all"                     else min(len(mine), int(spec.get("count", 1) or 1))
                for pool in mine[:take]:
                    self.scene.pools.remove(pool)
                done.append(f"{take} pool{'s' if take != 1 else ''} spent")
            else:
                narrated.append(kind)

        bits = [f"{actor.name} uses {found.title()}."]
        if done:
            bits.append("The engine resolves: " + "; ".join(done) + ".")
        if narrated:
            bits.append(f"{len(narrated)} part(s) of it are yours to narrate.")
        return Outcome(
            intent_id=intent.id, op="use_ability", rolls=rolls,
            effects=[{"ref": actor.ref, "kind": "use_ability", "ability": found,
                      "path": path, "resolved": len(done), "narrated": len(narrated)}],
            tell=" ".join(bits), because=intent.because,
        )

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
        made = BloodPool(owner=actor.ref, at=tuple(where) if where else None,
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
                if actor is None or b.owner == actor.ref]
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

        result = actor.rest(kind)
        refilled = actor.refresh_pools("rest.night", self.dice)
        hours = result["hours"]
        self.scene.clock_minutes += hours * 60
        ended = actor.tick_conditions(hours * 600)      # ten rounds to the minute

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
                      "hours": hours, "hp_after": actor.hp}],
            tell=" ".join(bits), because=intent.because,
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
        from .bestiary import instantiate  # local import: bestiary is data, not core

        count = int(intent.params.get("count", 1))
        made = []
        for n in range(count):
            actor = instantiate(
                intent.params["template"],
                scene=self.scene,
                name=intent.params.get("name"),
                world_entity_id=intent.params.get("from_entity_id"),
                index=n,
            )
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
                self.scene.sides.setdefault(
                    "pc" if actor.is_pc else "them", []
                ).append(actor.ref)
        return Outcome(
            intent_id=intent.id, op="spawn",
            effects=[{"kind": "spawn", "actors": made}],
            tell="On the board: " + ", ".join(f"{m['name']} ({m['ref']})" for m in made) + ".",
            because=intent.because,
        )

    # --- helpers ------------------------------------------------------------------------

    def _roll_or_suspend_stage(
        self, intent: Intent, actor: Actor, mods: list[Modifier], label: str,
        dc: int | None, partial: dict, state: dict, notation: str,
    ) -> Roll:
        """One stage of a multi-stage intent: roll it, or hand it to the player and stop.

        Unlike `_roll_or_suspend` this carries the accumulated `state` into the
        suspension, so an attack that has already rolled to-hit does not roll it again
        when the player comes back to roll damage.
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
                {"attack_state": state},
            )
        return self.dice.roll(notation, mods, label=label, visibility=intent.visibility)

    def _roll_or_suspend(
        self, intent: Intent, actor: Actor, mods: list[Modifier], label: str,
        dc: int, partial: dict, extra_partial: dict | None = None,
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


# --- (de)serialisation for the suspend/resume round trip --------------------------------

def _intent_from_dict(d: dict) -> Intent:
    return Intent(
        op=d["op"], actor=d.get("actor"), target=d.get("target"),
        because=d.get("because", ""), params=d.get("params") or {},
        visibility=d.get("visibility", "hidden"), id=d.get("id", "i1"),
    )


def _roll_from_dict(d: dict) -> Roll:
    return Roll(
        die=d["die"], faces=list(d["faces"]),
        modifiers=[Modifier(m["value"], m["source"]) for m in d["modifiers"]],
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


def _damage_note(d: dict) -> str:
    """"12, less DR 5/—, 4 off temporary" — the sentence a player needs.

    Empty when nothing interesting happened, so the ordinary hit stays quiet and the two
    mechanics that can make damage vanish always say so. Damage disappearing without
    explanation is the failure this exists to prevent.
    """
    bits = []
    if d["reduced"]:
        bits.append(f"less {d['reduced_by']} ({d['reduced']})")
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
