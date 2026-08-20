"""The rules engine: it owns all state and all rolls.

The GM agent proposes intents; this resolves them. Nothing here asks a model anything, and
nothing here can be talked out of a result — resolution is arithmetic over the sheet.

Resolution is a state machine rather than a function, because a player roll is an
asynchronous human input in the middle of an intent list. `run()` returns either a
finished `Resolution` or one that is `awaiting_player_roll`, and `resume()` continues the
same list from exactly where it stopped.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from . import dc as dc_mod
from .dice import Dice, Modifier, Roll
from .intents import Intent, IntentError, parse_all
from .sheet import Actor
from .tables import SAVES, WEAPONS


# --- Scene state -------------------------------------------------------------------

@dataclass
class Scene:
    """Everything the engine owns. The world agent may read this and writes none of it —
    see docs/intent-protocol.md §8."""
    location_id: str | None = None
    actors: dict[str, Actor] = field(default_factory=dict)
    zones: dict[str, str] = field(default_factory=dict)
    initiative: list[tuple[str, int]] = field(default_factory=list)
    round: int = 0
    clock_minutes: int = 0
    log: list[dict] = field(default_factory=list)

    # Suspended-resolution state. Non-empty only between a dice prompt and the player's
    # answer.
    pending_intents: list[dict] = field(default_factory=list)
    pending_outcomes: list[dict] = field(default_factory=list)
    pending_partial: dict = field(default_factory=dict)
    awaiting: dict | None = None

    def add(self, actor: Actor, zone: str = "near") -> Actor:
        self.actors[actor.ref] = actor
        self.zones[actor.ref] = zone
        return actor

    def refs(self) -> list[str]:
        return list(self.actors)

    def get(self, ref: str) -> Actor | None:
        return self.actors.get(ref)

    def pc(self) -> Actor | None:
        return next((a for a in self.actors.values() if a.is_pc), None)


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


class _NeedsPlayerRoll(Exception):
    """Raised inside an op handler to suspend the whole intent list."""

    def __init__(self, prompt: dict, partial: dict | None = None):
        super().__init__("awaiting player roll")
        self.prompt = prompt
        self.partial = partial or {}


# --- The engine ---------------------------------------------------------------------

class Engine:
    def __init__(self, scene: Scene, dice: Dice | None = None):
        self.scene = scene
        self.dice = dice or Dice()

    # --- Checks 2 and 3 -------------------------------------------------------------

    def validate(self, raw_intents: list) -> list[Intent]:
        """Schema, then refs, then legality. Raises IntentError carrying which check
        failed so the caller can choose between regenerating and repairing."""
        intents = parse_all(raw_intents)
        for i, intent in enumerate(intents):
            self._check_refs(intent, i)
            self._check_legality(intent, i)
            self._force_visibility(intent)
        return intents

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

    def _known(self, ref: str | None) -> bool:
        return bool(ref) and ref in self.scene.actors

    def _check_refs(self, intent: Intent, index: int) -> None:
        if intent.op in ("narrate_only", "advance_time", "spawn", "begin_encounter"):
            if intent.op == "begin_encounter":
                for side, refs in intent.params["sides"].items():
                    for r in refs:
                        if not self._known(r):
                            raise IntentError(
                                f"begin_encounter: side {side!r} names unknown ref {r!r}; "
                                f"known refs are {sorted(self.scene.actors)}",
                                "refs", index,
                            )
            return

        needs_actor = intent.op in ("check", "save", "attack", "move")
        if needs_actor and not self._known(intent.actor):
            raise IntentError(
                f"{intent.op}: unknown actor {intent.actor!r}; known refs are "
                f"{sorted(self.scene.actors)}. Refer to people by ref, never by name.",
                "refs", index,
            )
        for t in intent.targets():
            if not self._known(t):
                raise IntentError(
                    f"{intent.op}: unknown target {t!r}; known refs are "
                    f"{sorted(self.scene.actors)}",
                    "refs", index,
                )
        opposed = intent.params.get("opposed_by")
        if opposed and not self._known(opposed.get("ref")):
            raise IntentError(
                f"check: opposed_by names unknown ref {opposed.get('ref')!r}",
                "refs", index,
            )
        to = intent.params.get("to")
        if to and not self._known(to):
            raise IntentError(
                f"{intent.op}: unknown ref {to!r} in params.to", "refs", index
            )

    def _check_legality(self, intent: Intent, index: int) -> None:
        actor = self.scene.get(intent.actor) if intent.actor else None
        if actor and intent.op in ("attack", "move", "check") and not actor.can_act():
            raise IntentError(
                f"{intent.op}: {actor.name} is {actor.blocking_condition().lower()} and "
                f"cannot act",
                "legality", index,
            )
        if intent.op == "attack" and actor:
            key = intent.params.get("weapon") or actor.equipped or "unarmed"
            if key not in WEAPONS:
                raise IntentError(
                    f"attack: {actor.name} has no weapon {key!r}", "legality", index
                )
            if actor.weapons and key not in actor.weapons and key != "unarmed":
                raise IntentError(
                    f"attack: {actor.name} is not carrying a {key} "
                    f"(has {', '.join(actor.weapons) or 'nothing'})",
                    "legality", index,
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
            self.scene.log.append(outcome.as_dict())
        return Resolution(outcomes=outcomes)

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
                    effects.append(self._apply_damage(actor, amount,
                                                      branch.get("type", "untyped")))
                    tell_bits.append(
                        f"{actor.name} takes {amount} ({branch.get('type', 'untyped')}, halved)."
                    )
            else:
                dmg_roll = self.dice.roll(str(dmg), label="damage", visibility="hidden")
                effects.append(self._apply_damage(actor, dmg_roll.total,
                                                  branch.get("type", "untyped")))
                tell_bits.append(
                    f"{actor.name} takes {dmg_roll.total} {branch.get('type', 'untyped')} damage."
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
        actor = self.scene.actors[intent.actor]
        targets = intent.targets()
        if not targets:
            raise IntentError("attack: needs a target", "schema")
        defender = self.scene.actors[targets[0]]
        weapon_key = intent.params.get("weapon") or actor.equipped or "unarmed"
        weapon = actor.weapon(weapon_key)
        full = bool(intent.params.get("full_attack"))

        rolls: list[Roll] = []
        effects: list[dict] = []
        tell_bits: list[str] = []
        target_ac = defender.ac(against=weapon["category"])

        for iteration in actor.attack_sequence(weapon_key, full):
            mods = actor.attack_modifiers(weapon_key, iteration)
            atk = self.dice.d20(mods, label=f"{actor.name} attack", visibility=intent.visibility)
            rolls.append(atk)
            natural = atk.natural

            if natural == 1:
                tell_bits.append(f"{actor.name}'s attack goes badly wide (natural 1).")
                continue
            hit = natural == 20 or atk.total >= target_ac
            if not hit:
                tell_bits.append(
                    f"{actor.name}'s attack misses {defender.name} "
                    f"({atk.total} against AC {target_ac})."
                )
                continue

            # Crit confirmation — a threat is not a crit until it is confirmed, which is
            # exactly the sort of step a person forgets and code does not.
            crit = False
            if natural is not None and natural >= weapon["crit_range"]:
                confirm = self.dice.d20(
                    actor.attack_modifiers(weapon_key, iteration),
                    label="crit confirm", visibility=intent.visibility,
                )
                rolls.append(confirm)
                crit = confirm.total >= target_ac

            mult = weapon["crit_mult"] if crit else 1
            total_damage = 0
            for _ in range(mult):
                dmg = self.dice.roll(weapon["damage"], actor.damage_modifiers(weapon_key),
                                     label="damage", visibility="hidden")
                total_damage += max(1, dmg.total)
            effects.append(self._apply_damage(defender, total_damage, weapon["type"]))
            tell_bits.append(
                f"{actor.name} {'critically ' if crit else ''}hits {defender.name} "
                f"for {total_damage} {weapon['type']}."
            )

        effects.extend(self._hp_state_effects(defender))
        any_hit = any(e.get("kind") == "damage" for e in effects)
        return Outcome(
            intent_id=intent.id, op="attack", rolls=rolls,
            dc={"value": target_ac, "explain": f"AC {target_ac}"},
            verdict="hit" if any_hit else "miss",
            effects=effects, tell=" ".join(tell_bits), because=intent.because,
        )

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
        effects = [self._apply_damage(target, value, intent.params["type"])]
        effects.extend(self._hp_state_effects(target))
        return Outcome(
            intent_id=intent.id, op="damage", rolls=[roll] if roll else [],
            effects=effects,
            tell=f"{target.name} takes {value} {intent.params['type']} damage.",
            because=intent.because,
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

    def _op_move(self, intent: Intent, partial: dict) -> Outcome:
        ref = intent.params.get("who") or intent.actor
        actor = self.scene.actors[ref]
        zone = intent.params["zone"]
        was = self.scene.zones.get(ref, "near")
        self.scene.zones[ref] = zone
        return Outcome(
            intent_id=intent.id, op="move",
            effects=[{"ref": ref, "kind": "zone", "from": was, "to": zone}],
            tell=f"{actor.name} moves from {was} to {zone}.",
            because=intent.because,
        )

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
        names = ", ".join(self.scene.actors[r].name for r, _ in order)
        return Outcome(
            intent_id=intent.id, op="begin_encounter", rolls=rolls,
            effects=[{"kind": "initiative", "order": order}],
            tell=f"Initiative: {names}.", because=intent.because,
        )

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
        return Outcome(
            intent_id=intent.id, op="spawn",
            effects=[{"kind": "spawn", "actors": made}],
            tell="On the board: " + ", ".join(f"{m['name']} ({m['ref']})" for m in made) + ".",
            because=intent.because,
        )

    # --- helpers ------------------------------------------------------------------------

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
                "modifier": sum(m.value for m in mods),
                "breakdown": [m.as_dict() for m in mods],
                "dc": dc,
                "because": intent.because,
                "intent_id": intent.id,
            }
            raise _NeedsPlayerRoll(prompt, dict(extra_partial or {}))
        return self.dice.d20(mods, label=label, visibility=intent.visibility)

    def _apply_damage(self, target: Actor, amount: int, dtype: str) -> dict:
        target.take_damage(amount)
        return {
            "ref": target.ref, "kind": "damage", "amount": amount, "type": dtype,
            "hp_after": target.hp, "hp_max": target.hp_max,
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


def _to_rounds(amount: int, unit: str) -> int:
    return {"round": 1, "minute": 10, "hour": 600, "day": 14400}[unit] * int(amount)


def _to_minutes(amount: int, unit: str) -> int:
    return {"round": 0, "minute": 1, "hour": 60, "day": 1440}[unit] * int(amount)
