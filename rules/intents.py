"""Intents: what the GM agent is allowed to say, and how we check that it said it.

The wire format is docs/intent-protocol.md. This module is the validating half — the four
mechanical checks that run on every GM emission before anything is resolved:

  1. schema      — is this a shape we recognise?
  2. refs        — does every actor and target exist in the engine's registry?
  3. legality    — can that actor actually do that right now?
  4. outcome     — did the narration state a mechanical result it does not get to state?

None of these is an instruction in a prompt. That is the point. Every quality fix that
held in World Bible detected the defect in code and then asked the model to repair only
what was found; every fix that relied on instructing the model to behave differently
failed and kept failing.
"""
from __future__ import annotations

import difflib
import re
from dataclasses import dataclass, field

from .tables import (
    CIRCUMSTANCE, DC_BANDS, MANEUVER_ALIASES, MANEUVERS, SAVES, SKILLS, WEAPONS,
)

# Skill names from other editions, mapped to the 1e name they unambiguously mean.
#
# Measured, not guessed: on the first live turn against llama3.1:8b the model emitted
# "melee", "initiative" and "dodge" as skills on three consecutive attempts and lost the
# turn. A model has read far more 5e and 3.5e than Pathfinder 1e, so it reaches for those
# vocabularies under pressure. Mapping the unambiguous ones costs nothing and removes a
# whole class of lost turn; the ambiguous ones (athletics is climb *or* swim) are left to
# be rejected with a suggestion, because guessing between them would be inventing a
# mechanic.
SKILL_ALIASES: dict[str, str] = {
    "sneak": "stealth", "sneaking": "stealth", "hide": "stealth", "hiding": "stealth",
    "notice": "perception", "spot": "perception", "listen": "perception",
    "search": "perception", "investigation": "perception", "awareness": "perception",
    "insight": "sense motive", "empathy": "sense motive",
    "persuasion": "diplomacy", "deception": "bluff", "lying": "bluff",
    "athletics (climb)": "climb", "athletics (swim)": "swim",
    "tumbling": "acrobatics", "balance": "acrobatics", "jump": "acrobatics",
    "open lock": "disable device", "open locks": "disable device",
    "lockpicking": "disable device", "thievery": "disable device",
    "pick pocket": "sleight of hand", "arcana": "knowledge (arcana)",
    "history": "knowledge (history)", "nature": "knowledge (nature)",
    "religion": "knowledge (religion)", "streetwise": "knowledge (local)",
    "medicine": "heal", "animal handling": "handle animal",
    # Measured live: "persuade" lost a turn, and `_suggest` proposed "ride" for it.
    "persuade": "diplomacy", "persuading": "diplomacy", "convince": "diplomacy",
    "negotiate": "diplomacy", "haggle": "diplomacy", "barter": "diplomacy",
    "intimidation": "intimidate", "threaten": "intimidate", "demoralize": "intimidate",
    "demoralise": "intimidate", "lie": "bluff", "feint": "bluff",
    "sneaking around": "stealth", "climbing": "climb", "swimming": "swim",
    "perceive": "perception", "scan": "perception", "examine": "perception",
    "recall knowledge": "knowledge (local)",
}


def normalise_skill(name: str) -> str | None:
    """The 1e skill this name means, or None if it means nothing we have."""
    key = str(name).strip().lower()
    if key in SKILLS:
        return key
    return SKILL_ALIASES.get(key)


_DC_NUMBER_RE = re.compile(r"^\s*(?:dc\s*)?(-?\d+)\s*$", re.IGNORECASE)


def normalise_dc(spec, op: str, index: int) -> dict:
    """Canonicalise every shape a DC can arrive in, and reject the rest.

    Validation has to cover everything resolution accepts, or the gap between them
    becomes an uncaught crash instead of a rejection the model could repair. That is
    exactly what happened on the second live turn: `rules.dc.resolve` accepted a bare
    string, `_check_params` only validated the dict form, and the model's perfectly
    reasonable `"dc": "DC 15"` sailed past check 1 and 500'd inside the engine.

    "DC 15" is now read as the value 15 — it is a natural thing to write, and a stated
    value is already a supported (clamped) input.
    """
    if isinstance(spec, bool):
        raise IntentError(f"{op}: dc must be a difficulty band or a number", "schema", index)
    if isinstance(spec, (int, float)):
        return {"value": int(spec)}
    if isinstance(spec, str):
        m = _DC_NUMBER_RE.match(spec)
        if m:
            return {"value": int(m.group(1))}
        spec = {"band": spec}
    if not isinstance(spec, dict):
        raise IntentError(
            f"{op}: dc must be a difficulty band or a number, got {spec!r}", "schema", index
        )

    if spec.get("value") is not None and not spec.get("band"):
        try:
            return {"value": int(spec["value"])}
        except (TypeError, ValueError):
            raise IntentError(
                f"{op}: dc value {spec['value']!r} is not a number", "schema", index
            )

    band = str(spec.get("band", "")).strip().lower().replace(" ", "_")
    if band in DC_BANDS:
        return {"band": band}
    m = _DC_NUMBER_RE.match(band.replace("_", " "))
    if m:
        return {"value": int(m.group(1))}
    raise IntentError(
        f"{op}: {spec.get('band')!r} is not a difficulty band."
        + _suggest(band, DC_BANDS)
        + f" The bands are: {', '.join(DC_BANDS)}. A plain number is also accepted.",
        "schema", index,
    )


def _square(raw, op: str, index: int) -> tuple[int, int]:
    """A grid square, however the GM wrote it.

    A model asked for coordinates returns `[4, 7]` or `{"col": 4, "row": 7}` or `"4,7"`
    depending on the phase of the moon, and all three mean the same square. Normalising
    here rather than in the engine keeps every op that grows a position later reading one
    shape — and gives one error message instead of three.
    """
    if isinstance(raw, dict):
        try:
            return (int(raw["col"]), int(raw["row"]))
        except (KeyError, TypeError, ValueError):
            raise IntentError(
                f"{op}: square must have integer col and row, got {raw!r}",
                "schema", index
            ) from None
    if isinstance(raw, str):
        raw = [bit for bit in raw.replace("(", "").replace(")", "").split(",") if bit.strip()]
    try:
        col, row = raw
        return (int(col), int(row))
    except (TypeError, ValueError):
        raise IntentError(
            f"{op}: square must be a square like [col, row], got {raw!r}",
            "schema", index
        ) from None


def _known_weapon(name) -> bool:
    """Imported lazily: `rules.weapons` reads Django settings, and this module is imported
    before settings are configured in some entry points."""
    from .weapons import has

    # The armament's own weapon exists on the wearer, not in the table — the sheet
    # builds it from the class's blood die. Validation lets it through; whether the
    # armament is actually formed is the engine's legality check, with a better error.
    if str(name).strip().lower() in ("armed punch", "armed punches", "blood gauntlets"):
        return True
    return has(str(name))


def _suggest(name: str, candidates) -> str:
    """A rejection the model cannot act on costs a whole regeneration.

    Naming the nearest legal value turns a blind retry into a repair, which is the same
    reason the ref rejection lists the refs that do exist.
    """
    close = difflib.get_close_matches(str(name).strip().lower(), list(candidates), n=3, cutoff=0.5)
    if close:
        return " Did you mean " + " or ".join(repr(c) for c in close) + "?"
    return ""

# --- The op table ------------------------------------------------------------------

# op -> (required params, optional params, default visibility)
OPS: dict[str, tuple[tuple[str, ...], tuple[str, ...], str]] = {
    "check": (("skill",), ("dc", "opposed_by", "circumstance", "aid"), "player"),
    "save": (("save", "dc"), ("on_success", "on_failure"), "player"),
    # `player`, because the PC rolls their own to-hit and their own damage. Defaulting
    # this to `hidden` meant the engine silently rolled the player's attacks for them,
    # which contradicts the architecture decision outright. NPC attacks still resolve
    # hidden — `Engine._force_visibility` demotes any non-PC actor.
    "attack": ((), ("weapon", "full_attack", "manoeuvre", "power_attack",
                    "iteration"), "player"),
    # `lethality` because a Blood Bender paying for an ability in non-lethal
    # damage and one taking a sword are not in the same trouble.
    "damage": (("amount", "type"), ("to", "lethality"), "hidden"),
    # Healing is not negative damage: it never restores temporary hit points and never
    # carries a character up from below zero the way `damage` carries them down.
    "heal": (("amount",), ("to",), "hidden"),
    "buff": (("type", "target", "amount"), ("to", "source", "duration", "note"),
             "hidden"),
    "temp_hp": (("amount",), ("to", "source", "duration"), "hidden"),
    # Poison, disease, a spell that withers: damage to a score rather than to hit points.
    # `drain` for the permanent kind, which no amount of resting brings back.
    "ability_damage": (("ability", "amount"), ("to", "drain"), "hidden"),
    # Acid on a scabbard, a sundered blade. Objects have hardness and hit points of their
    # own, and neither is on anybody's character sheet.
    "item_damage": (("amount",), ("to", "item", "type"), "hidden"),
    # Working at a world class — foraging, harvesting, brewing. Advances the track, which
    # levels on what the character does rather than on their experience total.
    # `concentrating` because two doses in and one of the next band out is the one craft
    # whose output is deliberately rarer than anything that went into it: the ceiling has
    # to be checked against the input there, not the result. See `Engine._check_craft`.
    "craft": (("track", "recipe"), ("actor", "tier", "stages", "risky", "failed",
                                    "milestone", "concentrating"), "hidden"),
    # Spending or granting a pool: ki, rage rounds, a use per day, a stack on an enemy.
    # `to` because a stack lives on the creature it was applied to, not on whoever
    # applied it.
    "resource": (("pool",), ("actor", "to", "amount", "spend", "cooldown"), "hidden"),
    # Where the party is standing, which decides what grows here.
    # `with` names the refs who come along; everyone else stays behind, because travel
    # is the scene transition. Before it shed anybody, a gatekeeper wounded in the city
    # followed the player to the forest and took an NPC turn forever.
    "travel": (("biome",), ("note", "with"), "hidden"),
    # Searching the ground. The roll is the player's: it is their afternoon.
    # `hours` because foraging is time now: a minimum of one, and as many as the player
    # wants to spend. Every hour is its own Survival check, and past a day awake every
    # hour is also a Will save against dropping where you stand.
    "forage": ((), ("actor", "track", "biome", "hours"), "player"),
    "condition": (("condition",), ("duration", "to"), "hidden"),
    # The engine owns the slot, the caster level and the save DC. It does *not* own what
    # the spell does — that lives in three thousand paragraphs of English, and a parser
    # guessing at it would produce confident wrong numbers. Anything mechanical the GM
    # narrates comes back as its own `damage`, `condition` or `save` intent and is
    # validated like everything else. See docs/intent-protocol.md §11.
    # `square` is where a spell that puts something into the scene puts it — a fog
    # cloud's centre. Without it a manifest lands on the target's square, or the caster's
    # when there is no target, which is right often enough to be a default and wrong
    # often enough to need saying.
    #
    # `choose` names which branch of a `choose_one` effect the caster picked. A spell
    # that offers five forms and is cast without naming one applies none of them, which
    # is the whole point of the type: applying all five is what it exists to stop.
    "cast": (("spell",), ("at", "level", "defensively", "square", "choose"), "hidden"),
    # Crafted potions and tinctures doing something. `how` is drink, throw or coat, and
    # the difference is real: a splash weapon is a ranged touch attack and a coated blade
    # waits for the next hit. Before these an item was a paragraph in a satchel.
    "use_item": (("item",), ("how", "to", "weapon"), "player"),
    # Selling something. There was no op for this at all, and the absence was not
    # theoretical: a player asked a stallholder to price a satchel holding a
    # potency-1,335 draught, haggled her up from ten gold to twenty-two, shook her hand
    # — and every turn of it resolved to `narrate_only`. No item moved, no coin moved,
    # and the purse was still empty afterwards. She could not see the goods because
    # nothing had ever been handed to her.
    #
    # `accept` is the price the player agrees to, which is what makes a partial sale
    # possible: a stall short of the asking price offers what it has, and taking it is
    # the player's call rather than the engine's refusal.
    "sell": (("item",), ("count", "to", "stall", "accept"), "player"),
    # And the other direction. Buying existed only on the crafting bench, as an
    # excursion that spends hours and rolls a check for raw materials — so there was no
    # way at all to buy a thing off a stall while standing in front of it. The right-hand
    # side of a trade needs this or it is a display case.
    "buy": (("item",), ("count", "from_", "stall"), "player"),
    # Being pulled towards a target you did not choose. `to` is who is compelled; the
    # actor is who they are pulled towards. It penalises and never prohibits — see the
    # header of rules/compulsion.py, which is where that decision is argued.
    "compel": (("to",), ("penalty", "duration", "why"), "hidden"),
    # Standing between a blow and the person it was aimed at. The actor is the guardian.
    "guard": (("to",), ("kind", "amount", "range_ft", "uses", "pool"), "hidden"),
    "begin_encounter": (("sides",), ("surprise",), "hidden"),
    # A fight ends when the fighting stops, which is a call about the fiction:
    # they flee, they surrender, you get away. Without this the only way out of an
    # encounter was for one side to be wiped out, so a character could never
    # disengage — or rest afterwards, since resting is refused mid-fight.
    "end_encounter": ((), (), "hidden"),
    # `zone` stays required so every existing GM prompt and every saved intent still
    # parses. `to` is the square, and on a scene with a map it is the one that decides
    # where somebody ends up — the zone is then re-derived from the real distance rather
    # than believed.
    "move": (("zone",), ("who", "square"), "hidden"),
    "spawn": (("template",),
              ("from_entity_id", "count", "name", "zone", "distance_ft"),
              "hidden"),
    "advance_time": (("amount", "unit"), (), "hidden"),
    # Something changes hands. One op rather than four, because picking a thing up,
    # being handed it, buying it and dropping it are the same event with different ends
    # attached: `to` is who gains it, `from_` who loses it, and either may be absent
    # when the other end is the world. `item` is any name at all — see rules/goods.py on
    # why an unknown item is carried rather than refused.
    "give": (("item",), ("count", "to", "from_", "price", "unit"), "hidden"),
    # Putting on what you are carrying. Armour and shields change the AC the engine
    # computes; a weapon becomes the one in your hand. Refused for anything you do not
    # actually have, so the sheet can never claim protection nobody bought.
    "wear": (("item",), ("actor",), "hidden"),
    # Blood on the ground. `blood_pool` puts one down — at a square when there is a
    # grid, beside the actor when there is not — and `spend_pools` is how every
    # ability that siphons, detonates or steps through them takes them back off.
    # `count` on the spend is how many to consume; "all" is a real answer, because
    # Hemorrhagic Eruption detonates any number of them at once.
    "blood_pool": ((), ("actor", "at", "amount", "source", "to"), "hidden"),
    "spend_pools": ((), ("actor", "count", "why"), "hidden"),
    # Using one of your class's path abilities by name. The engine looks it up on the
    # paths this character follows, refuses one they have not reached, and resolves
    # whatever of it it can — the rest is narrated, and the outcome says which was
    # which rather than implying the whole thing was mechanised.
    "use_ability": (("ability",), ("actor", "to"), "player"),
    "rest": ((), ("kind",), "hidden"),
    # Eating and drinking reset the hunger and thirst clocks, which `rest` deliberately
    # does not: a night's sleep is not a meal. Two ops rather than one with flags,
    # because a model reliably emits {"op": "eat"} and reliably mangles booleans.
    # Found in the 2026-08-22 playtest: "I eat from my rations and drink from my
    # waterskin" reached the engine as narrate_only, so the survival clocks built that
    # week could never actually be answered — only run out.
    "eat": ((), ("actor",), "hidden"),
    "drink": ((), ("actor",), "hidden"),
    "narrate_only": ((), (), "hidden"),
}

VISIBILITIES = ("player", "hidden")

# Spellings of a param that mean the param. Normalised before the unknown-param check so
# the op table stays a list of real params rather than a list of spellings — otherwise a
# rejection helpfully lists both "manoeuvre" and "maneuver" as though they were different
# things.
PARAM_ALIASES = {
    "maneuver": "manoeuvre",
    "full attack": "full_attack",
    "fullattack": "full_attack",
    "powerattack": "power_attack",
    "power attack": "power_attack",
    "opposed": "opposed_by",
    "against": "opposed_by",
    "difficulty": "dc",
    # `from` is a Python keyword, so the op's param is `from_`; the GM writes the
    # English word and should not have to know that.
    "from": "from_",
    "giver": "from_",
    "receiver": "to",
    "recipient": "to",
    "quantity": "count",
    "amount_of": "count",
    "cost": "price",
}

# Params the GM keeps supplying that the *engine* owns. docs/intent-protocol.md §1 is
# explicit about these: "the engine ignores it and logs the discrepancy... a turn that
# dies because the model said '+7' is worse than one that overrides it." Hard-rejecting
# them contradicted that rule, and in live play it killed five consecutive attack
# attempts over `damage_type`, `dice` and `damage_roll` — all of which the engine reads
# off the weapon anyway.
#
# A param that is merely *unrecognised* is still rejected. The difference matters: an
# ignored engine-owned param is a value we can already compute, while an unknown one is
# a mechanic the GM believes it applied and we have never heard of.
ENGINE_OWNED_PARAMS = {
    "damage", "damage_type", "damage_roll", "damage_dice", "dice", "die",
    "attack_bonus", "attack_roll", "to_hit", "bonus", "modifier", "modifiers",
    "ac", "target_ac", "hit", "crit", "critical", "result", "outcome", "total",
    "skill", "roll", "dc_value", "save_bonus", "initiative",
    "melee_attack_roll", "ranged_attack_roll", "attack_modifier", "damage_modifier",
    "hit_points", "hp", "armor_class", "defense", "cmb", "cmd", "save", "save_dc",
}

# A ref, however the model has decorated it. Observed in play: "[ref: c1]", "<c1>",
# "c1 (the thug)". The registry is strict about *which* refs exist and there is no
# reason for it to also be strict about punctuation.
_REF_RE = re.compile(r"\b(pc|c\d+|[0-9a-f]{12})\b", re.I)


def normalise_ref(value):
    """Pull the ref out of whatever the model wrapped it in."""
    if not isinstance(value, str):
        return value
    m = _REF_RE.search(value.strip())
    return m.group(1).lower() if m else value.strip()

# The model keeps reaching for a third word meaning "the engine rolls this one, not the
# player" — observed as "gm" and "game" on separate live turns. That is exactly what
# `hidden` means, so it is mapped rather than rejected.
VISIBILITY_ALIASES = {
    "gm": "hidden", "game": "hidden", "engine": "hidden", "dm": "hidden",
    "secret": "hidden", "gm_only": "hidden", "behind_the_screen": "hidden",
    "npc": "hidden", "none": "hidden",
    "pc": "player", "player_visible": "player", "open": "player", "public": "player",
    "visible": "player",
}
ZONES = ("engaged", "near", "far")

# Imported by name rather than by module so a kind the engine cannot resolve is rejected at
# validation. The two lists going out of step is exactly the failure `ACTOR_RULES` exists
# to prevent, one layer up.
from .guards import KINDS as GUARD_KINDS  # noqa: E402
TIME_UNITS = ("round", "minute", "hour", "day")


class IntentError(ValueError):
    """A malformed or illegal intent. Carries which check rejected it, so the caller can
    decide between a regenerate and a targeted repair."""

    def __init__(self, message: str, check: str = "schema", index: int | None = None):
        super().__init__(message)
        self.check = check
        self.index = index


@dataclass
class Intent:
    op: str
    actor: str | None = None
    target: str | list[str] | None = None
    because: str = ""
    params: dict = field(default_factory=dict)
    visibility: str = ""
    id: str = ""
    # Engine-owned params the GM supplied and we dropped. Not an error, but the log is
    # the early warning that a prompt has drifted.
    ignored_params: list[str] = field(default_factory=list)

    def targets(self) -> list[str]:
        if self.target is None:
            return []
        return list(self.target) if isinstance(self.target, list) else [self.target]

    def as_dict(self) -> dict:
        return {
            "id": self.id, "op": self.op, "actor": self.actor, "target": self.target,
            "because": self.because, "params": self.params, "visibility": self.visibility,
            "ignored_params": self.ignored_params,
        }


# --- Check 1: schema ------------------------------------------------------------------

# Words the GM puts in the manoeuvre slot that are part of attacking rather than a
# manoeuvre of their own. Dropped rather than refused.
NOT_A_MANOEUVRE = {"draw", "swing", "lunge", "strike", "slash", "stab", "thrust",
                   "attack", "charge", "melee"}

# The one word a model reaches for when it means "no circumstance applies", which is
# exactly the case the enum has no room for.
NO_CIRCUMSTANCE = {"neutral", "none", "normal", "average", "standard", "no"}

# Ops the GM invents for a turn that has no mechanics in it. Every one of these was a
# lost turn: the model had decided nothing needed rolling and then said so in a word the
# protocol does not have.
OP_ALIASES = {
    "begin_conversation": "narrate_only", "conversation": "narrate_only",
    "talk": "narrate_only", "speak": "narrate_only", "dialogue": "narrate_only",
    "describe": "narrate_only", "narrate": "narrate_only", "narration": "narrate_only",
    "roleplay": "narrate_only", "none": "narrate_only", "no_action": "narrate_only",
    "wait": "narrate_only", "observe": "narrate_only",
    "end_combat": "end_encounter", "end_fight": "end_encounter",
    "start_encounter": "begin_encounter", "begin_combat": "begin_encounter",
    "skill_check": "check", "ability_check": "check", "saving_throw": "save",
    # Everyday activity, from the live session that died on it: "I want to go to the
    # gym and work out" produced op "exercise" five attempts running. 1e has no
    # exercising mechanic, and an activity with no mechanic is a story turn.
    "exercise": "narrate_only", "train": "narrate_only", "training": "narrate_only",
    "workout": "narrate_only", "work_out": "narrate_only",
    "practice": "narrate_only", "practise": "narrate_only", "spar": "narrate_only",
    "study": "narrate_only", "pray": "narrate_only", "meditate": "narrate_only",
    "shop": "narrate_only", "browse": "narrate_only", "socialize": "narrate_only",
    "socialise": "narrate_only",
}


def normalise_raw(raw: dict) -> dict:
    """Repairs that change what an intent *is*, applied before it is parsed.

    The same shape as `judgement.repair_unknown_refs`: read what the GM plainly meant and
    fix it in code, rather than spending a whole regeneration teaching it a word. Every
    case here was measured on a live turn that died after five attempts.
    """
    if not isinstance(raw, dict):
        return raw

    op = str(raw.get("op", "")).strip().lower()
    if op in OP_ALIASES:
        raw = dict(raw, op=OP_ALIASES[op])
        op = raw["op"]

    # An op the protocol has never heard of, after the aliases have had their say.
    # Two cases, told apart mechanically. A near-miss of a real op is a spelling and
    # snaps to it — "atack" is not a new idea, it is "attack" typed badly. Anything
    # else is the GM naming an activity the engine has no mechanic for, and an
    # activity with no mechanic is a story turn: `narrate_only`, params dropped
    # because the op that owned them is gone. Rejecting instead was measured to cost
    # the whole turn — the model does not learn the op list from being shown it.
    if op and op not in OPS:
        skill = normalise_skill(op)
        near = difflib.get_close_matches(op, list(OPS), n=1, cutoff=0.8)
        if skill:
            # "stealth" or "climb" as an op is a check by another spelling.
            raw = dict(raw, op="check",
                       params={**(raw.get("params") or {}), "skill": skill})
        elif near:
            raw = dict(raw, op=near[0])
        else:
            raw = dict(raw, op="narrate_only", params={})
        op = raw["op"]

    # A check that never says what to roll. The live turn retried "exercise" as
    # `check` with no skill three attempts running. If the reason clause names a
    # skill, that is the roll; otherwise there is nothing to roll and the turn is
    # story, same as above.
    if op == "check":
        params = raw.get("params") or {}
        if not params.get("skill"):
            because = str(raw.get("because") or "")
            found = next((s for w in re.findall(r"[a-z]+", because.lower())
                          if (s := normalise_skill(w))), None)
            if found:
                raw = dict(raw, params={**params, "skill": found})
            else:
                raw = dict(raw, op="narrate_only", params={})

    # A skill in the manoeuvre slot: "manoeuvre": "intimidate" is the GM reaching for
    # demoralising somebody, which in 1e is a skill check and not a manoeuvre at all.
    if op == "attack":
        params = raw.get("params") or {}
        man = str(params.get("manoeuvre", "")).strip().lower()
        if man and man not in MANEUVERS and man not in MANEUVER_ALIASES:
            skill = normalise_skill(man)
            if skill:
                kept = {k: v for k, v in params.items()
                        if k not in ("manoeuvre", "full_attack", "weapon", "power_attack")}
                raw = dict(raw, op="check", params={**kept, "skill": skill})
    return raw


def parse(raw: dict, index: int = 0) -> Intent:
    if not isinstance(raw, dict):
        raise IntentError(f"intent {index} is not an object", "schema", index)

    raw = normalise_raw(raw)
    op = str(raw.get("op", "")).strip().lower()
    if op not in OPS:
        raise IntentError(
            f"unknown op {op!r}; expected one of {sorted(OPS)}", "schema", index
        )

    required, optional, default_vis = OPS[op]
    params = raw.get("params") or {}
    if not isinstance(params, dict):
        raise IntentError(f"{op}: params must be an object", "schema", index)

    for said, means in PARAM_ALIASES.items():
        if said in params and means not in params:
            params[means] = params.pop(said)

    missing = [p for p in required if params.get(p) in (None, "")]
    if missing:
        raise IntentError(
            f"{op}: missing required param(s) {', '.join(missing)}", "schema", index
        )

    unknown = set(params) - set(required) - set(optional)
    ignored = sorted(unknown & ENGINE_OWNED_PARAMS)
    for key in ignored:
        params.pop(key, None)
    unknown -= set(ignored)
    if unknown:
        raise IntentError(
            f"{op}: unknown param(s) {', '.join(sorted(unknown))}. "
            f"{op} takes {', '.join(sorted(set(required) | set(optional))) or 'no params'}.",
            "schema", index,
        )

    visibility = str(raw.get("visibility") or default_vis).strip().lower()
    visibility = VISIBILITY_ALIASES.get(visibility, visibility)
    if visibility not in VISIBILITIES:
        raise IntentError(
            f"{op}: visibility is {VISIBILITIES[0]!r} (the player rolls it) or "
            f"{VISIBILITIES[1]!r} (the engine rolls it), got {visibility!r}",
            "schema", index,
        )

    target = raw.get("target")
    if isinstance(target, list):
        target = [normalise_ref(t) for t in target]
    else:
        target = normalise_ref(target)

    intent = Intent(
        op=op,
        actor=normalise_ref(raw.get("actor")),
        target=target,
        because=str(raw.get("because") or "").strip(),
        params=params,
        visibility=visibility,
        id=str(raw.get("id") or f"i{index + 1}"),
        ignored_params=ignored,
    )
    _check_params(intent, index)
    return intent


def _check_params(intent: Intent, index: int) -> None:
    """Per-op value checks. Closed vocabularies are checked here rather than trusted,
    because a closed vocabulary the code does not enforce is just a suggestion."""
    p, op = intent.params, intent.op

    if op == "check":
        raw_skill = str(p["skill"]).strip().lower()
        # Attacking is not a skill check in 1e, and the model reaches for one. Say so,
        # rather than making it guess from a list that will never contain the answer.
        if raw_skill in ("attack", "melee", "melee attack", "ranged attack", "to hit",
                         "weapon", "combat", "strike", "hit"):
            raise IntentError(
                f"check: attacking is not a skill check. Use "
                '{"op": "attack", "actor": "...", "target": "..."} — the engine works '
                "out the attack bonus, the target's AC and the damage from the sheets.",
                "schema", index,
            )
        if raw_skill in ("initiative", "init", "reflexes"):
            raise IntentError(
                "check: initiative is not a skill check. Use "
                '{"op": "begin_encounter", "params": {"sides": {"pc": ["pc"], '
                '"them": ["<ref>"]}}} — the engine rolls initiative for everyone.',
                "schema", index,
            )
        skill = normalise_skill(raw_skill)
        if skill is None:
            raise IntentError(
                f"check: {raw_skill!r} is not a Pathfinder 1e skill."
                + _suggest(raw_skill, SKILLS)
                + f" The skills are: {', '.join(sorted(SKILLS))}.",
                "schema", index,
            )
        p["skill"] = skill
        if p.get("opposed_by"):
            ob = p["opposed_by"]
            if not isinstance(ob, dict) or "ref" not in ob or "skill" not in ob:
                raise IntentError(
                    "check: opposed_by needs {ref, skill}", "schema", index
                )
            raw_os = str(ob["skill"]).strip().lower()
            os_ = normalise_skill(raw_os)
            if os_ is None:
                raise IntentError(
                    f"check: {raw_os!r} is not a Pathfinder 1e skill and cannot oppose "
                    f"a check." + _suggest(raw_os, SKILLS)
                    + " To have someone resist by noticing, oppose with 'perception'.",
                    "schema", index,
                )
            ob["skill"] = os_
            ob["ref"] = normalise_ref(ob.get("ref"))
        if not p.get("dc") and not p.get("opposed_by"):
            raise IntentError(
                "check: a check needs something to beat. Add either "
                '"dc": {"band": "tough"} (one of ' + ", ".join(DC_BANDS) + "), or "
                '"opposed_by": {"ref": "<a ref in the scene>", "skill": "perception"} '
                "when someone is actively resisting.",
                "schema", index,
            )

    elif op == "save":
        save = str(p["save"]).strip().lower()
        aliases = {"fortitude": "fort", "reflex": "ref"}
        save = aliases.get(save, save)
        if save not in SAVES:
            raise IntentError(f"save: no such save {save!r}", "schema", index)
        p["save"] = save

    elif op == "attack":
        w = p.get("weapon")
        if w and not _known_weapon(w):
            # The list used to be printed in full, which was reasonable at eleven weapons
            # and is 456 names of noise now. A near-miss suggestion is what the model can
            # actually act on.
            from .weapons import all_weapons

            raise IntentError(
                f"attack: no such weapon {w!r}."
                + _suggest(str(w), all_weapons())
                + " Carried weapons are named on the sheet.",
                "schema", index,
            )
        if w:
            p["weapon"] = str(w).strip().lower()
        p["full_attack"] = bool(p.get("full_attack", False))
        man = p.get("manoeuvre")
        if man:
            key = str(man).strip().lower()
            key = MANEUVER_ALIASES.get(key, key)
            # "draw", "swing", "lunge" — things that are simply part of making an attack
            # rather than manoeuvres. Measured live: `"manoeuvre": "draw"` was the first
            # of five failed attempts on a turn that then died. The param is dropped; a
            # manoeuvre that is really a *skill* is rewritten a step earlier, in
            # `normalise_raw`.
            if key in NOT_A_MANOEUVRE:
                p.pop("manoeuvre", None)
            elif key not in MANEUVERS:
                raise IntentError(
                    f"attack: {man!r} is not a combat manoeuvre."
                    + _suggest(key, MANEUVERS)
                    + f" The manoeuvres are: {', '.join(sorted(MANEUVERS))}.",
                    "schema", index,
                )
            else:
                p["manoeuvre"] = key

    elif op == "move":
        zone = str(p["zone"]).strip().lower()
        if zone not in ZONES:
            raise IntentError(
                f"move: zone must be one of {ZONES}, got {zone!r}", "schema", index
            )
        p["zone"] = zone
        if p.get("square") not in (None, ""):
            p["square"] = _square(p["square"], "move", index)

    elif op == "guard":
        kind = str(p.get("kind", "redirect")).strip().lower()
        if kind not in GUARD_KINDS:
            raise IntentError(
                f"guard: kind must be one of {sorted(GUARD_KINDS)}, got {kind!r}."
                + _suggest(kind, GUARD_KINDS),
                "schema", index,
            )
        p["kind"] = kind

    elif op == "advance_time":
        unit = str(p["unit"]).strip().lower().rstrip("s")
        if unit not in TIME_UNITS:
            raise IntentError(
                f"advance_time: unit must be one of {TIME_UNITS}, got {unit!r}",
                "schema", index,
            )
        p["unit"] = unit
        try:
            p["amount"] = int(p["amount"])
        except (TypeError, ValueError):
            raise IntentError("advance_time: amount must be a number", "schema", index)

    elif op == "rest":
        kind = str(p.get("kind", "night")).strip().lower()
        aliases = {"sleep": "night", "night's rest": "night", "full night": "night",
                   "long rest": "night", "overnight": "night", "camp": "night",
                   "bed": "bed rest", "bedrest": "bed rest", "full day": "bed rest",
                   "day": "bed rest", "complete bed rest": "bed rest"}
        kind = aliases.get(kind, kind)
        if kind not in ("night", "bed rest"):
            raise IntentError(
                f"rest: {p.get('kind')!r} is not a kind of rest. A night is eight hours "
                f"and heals your level in hit points; bed rest is a full day and night "
                f"and heals twice that.",
                "schema", index,
            )
        p["kind"] = kind

    elif op == "spawn":
        # Validation has to cover everything resolution accepts. It did not here, and an
        # invented template ("bravo") reached the bestiary and raised UnknownTemplate as
        # a 500 — the same shape of gap as the bare-string DC.
        from . import bestiary

        raw_t = str(p["template"]).strip().lower()
        if bestiary.lookup(raw_t) is None:
            # Nearest matches, never the whole list. Naming all four templates was the
            # helpful thing to do; naming all 6,406 creatures is a wall of text, and a
            # model reading it loses the turn it was in the middle of.
            raise IntentError(
                f"spawn: no creature {p['template']!r}." + bestiary.suggestion(raw_t),
                "schema", index,
            )
        p["template"] = raw_t
        try:
            p["count"] = max(1, min(12, int(p.get("count", 1) or 1)))
        except (TypeError, ValueError):
            raise IntentError("spawn: count must be a number", "schema", index)

    elif op == "begin_encounter":
        if not isinstance(p["sides"], dict):
            raise IntentError(
                "begin_encounter: sides must be an object of side -> [refs]",
                "schema", index,
            )

    # The DC spec, wherever it appears, is canonicalised here so that resolution only
    # ever sees a shape it fully understands.
    if p.get("dc") is not None:
        p["dc"] = normalise_dc(p["dc"], op, index)

    for key in ("to", "who"):
        if p.get(key):
            p[key] = normalise_ref(p[key])
    if op == "begin_encounter" and isinstance(p.get("sides"), dict):
        p["sides"] = {k: [normalise_ref(r) for r in v] for k, v in p["sides"].items()}

    circ = p.get("circumstance")
    if circ:
        if isinstance(circ, str):
            circ = {"value": circ}
            p["circumstance"] = circ
        val = str(circ.get("value", "")).strip().lower()
        # "neutral" is the model saying there is no circumstance, in the one word the
        # enum does not contain. Rejecting it cost a whole regeneration for a param that
        # means "leave this out" — measured live, it was the first of five failed attempts
        # on a turn that then died. Dropped rather than refused.
        if val in NO_CIRCUMSTANCE:
            p.pop("circumstance", None)
        elif val not in CIRCUMSTANCE:
            raise IntentError(
                f"{op}: circumstance must be one of {sorted(CIRCUMSTANCE)}, got "
                f"{val!r}. Leave it out entirely when nothing helps or hinders.",
                "schema", index,
            )
        else:
            circ["value"] = val


def parse_all(raw_intents: list) -> list[Intent]:
    if not isinstance(raw_intents, list):
        raise IntentError("intents must be a list", "schema")
    if not raw_intents:
        # Absence is never silently acceptable. `narrate_only` exists precisely so that
        # "nothing mechanical happened" is a thing the GM says out loud, which makes a
        # model that forgot to emit intents a detectable failure rather than an
        # invisible one.
        raise IntentError(
            "no intents emitted; a turn with no mechanics must say so with "
            "narrate_only", "schema",
        )
    return [parse(r, i) for i, r in enumerate(raw_intents)]


# --- Check 4: the outcome-claim detector ------------------------------------------------

# Phrasings that assert a mechanical result. Every one of these is something a model
# actually produced in testing while being asked, in the prompt, not to.
_OUTCOME_PATTERNS: list[tuple[str, str]] = [
    (r"\byou (?:take|suffer|lose)\b[^.]{0,30}?\b\d+\b", "states damage taken"),
    (r"\b\d+\s*(?:points? of\s*)?damage\b", "states a damage number"),
    (r"\byour?\s+(?:hit points?|hp)\b", "states hit points"),
    (r"\byou (?:succeed|fail|manage to|barely make|don't make)\b", "states success or failure"),
    (r"\byou(?:'re| are) (?:hit|struck|wounded|killed|dead)\b", "states being hit"),
    # The determiner list grew from live play: "Your blade bites deep into her side" and
    # "His fist connects with a sickening crunch" both printed in *setup* narration,
    # before any attack roll was offered, and the first version of this pattern only knew
    # "the blade". The gap between noun and verb is bounded so "your blade — the one your
    # mother gave you — is old" cannot match across half a paragraph.
    # Only the verbs that are a hit with no object to weigh: "connects", "lands", "finds
    # its mark". The bites/sinks/slices family needs to know *what* was bitten — a blade
    # biting into the dock beside her is a narrated miss and legal — so those live in the
    # weapon-into-possessive shape below.
    (r"\b(?:the|your|his|her|their|its|a)\s+"
     r"(?:blow|blade|arrow|bolt|strike|dagger|rapier|sword|knife|axe|spear|club|mace|fist)\b"
     r"[^.!?]{0,40}?\b(?:lands|connects|finds|pierces|opens)\b",
     "states an attack landing"),
    # "your dagger still lodged in the arm of the would-be attacker" — the wound described
    # as already there is the hit described as already rolled.
    (r"\b(?:lodged|buried|embedded|sunk)\s+in\b", "states an attack having landed"),
    # The verb list above kept losing to the model's vocabulary — "bites", then
    # "slices into", each one new. The *shape* is stable where the verbs are not: a
    # weapon going into a possessive is flesh, and flesh is a hit. Into *the* something
    # is scenery — "your blade bites deep into the wooden dock beside her" was a miss,
    # narrated correctly, and must stay legal.
    (r"\b(?:blow|blade|dagger|rapier|sword|knife|axe|spear|arrow|bolt|fist|steel)\b"
     r"[^.!?]{0,30}?\binto\s+(?:(?:his|her|their|its)\b"
     # "into the joint between her shoulder and elbow" — flesh behind a definite
     # article. Body nouns only: "into the wooden dock" must stay a narrated miss.
     r"|the\s+(?:gut|ribs?|joint|throat|chest|skull|belly|stomach|face|neck|eye"
     r"|heart|flesh|shoulder|thigh|arm|leg|side|back|wound))\b",
     "states an attack landing"),
    (r"\bstrik(?:e|es|ing)\s+(?:him|her|them|it)\s+in\s+the\b", "states an attack landing"),
    (r"\bbleed(?:s|ing)\s+from\b", "states a wound already dealt"),
    (r"\bclutch(?:es|ing)\s+(?:at\s+)?(?:the|his|her|their|its)\s+wound\b",
     "states a wound already dealt"),
    # "The cutpurse's eyes are watering from the blow" — confirmation session, in setup,
    # about a blow that never rolled. Anything described as being *from the blow* asserts
    # the blow happened.
    (r"\bfrom the blow\b", "states an attack having landed"),
    (r"\b(?:misses|missed|goes wide|glances off|skitters past|flashes past|sails wide)\b",
     "states an attack missing"),
    (r"\byou (?:dodge|duck|roll) (?:clear|aside|away)\b", "states a save succeeding"),
    (r"\bthe (?:save|check|roll) (?:succeeds|fails)\b", "states a roll's result"),
    (r"\byou slip (?:past|by) (?:him|her|them|the guard)\b", "states a stealth result"),
    (r"\bunnoticed\b|\bwithout being (?:seen|heard|noticed)\b", "states a stealth result"),
    # "…goes back to his cup, unaware." — produced in live play, in the *setup*
    # narration, before the opposed Stealth check had been rolled. The GM had decided
    # the guildhand failed his Perception. Caught only by playing, which is why the rule
    # is to verify on real regenerated content and not on the phrasings you imagined.
    (r"\bunaware\b|\boblivious\b|\bnone the wiser\b", "states a perception result"),
    (r"\b(?:doesn't|does not|didn't|did not|never) (?:see|hear|notice|spot|catch)\b",
     "states a perception result"),
    (r"\bnever (?:sees|hears|notices|spots)\b", "states a perception result"),
    (r"\bfails? to (?:see|hear|notice|spot)\b", "states a perception result"),
    # "You squirm and twist, managing to slip free of the grapple" — produced in a live
    # fight, in setup narration, while the engine still had her grappled. Escaping a
    # grapple is a combat manoeuvre check like any other, and the GM does not get to
    # decide it any more than it gets to decide a sword swing.
    (r"\b(?:slip|break|pull|wriggle|squirm|twist|tear)(?:s|ing)?\s+(?:free|loose|away|out)\b",
     "states an escape"),
    (r"\bmanag(?:e|es|ing) to\b", "states an action succeeding"),
    (r"\b(?:escapes?|escaped|escaping)\s+(?:the|his|her|their|its)\b", "states an escape"),
    (r"\bshakes? (?:him|her|it|them)self free\b", "states an escape"),
    (r"\bgets? (?:free|loose|away)\b", "states an escape"),
    (r"\bdc\s*\d+", "states a DC in prose; the DC belongs in the intent"),
    (r"\broll(?:s|ed)? a\s*\d+", "states a die result"),
    (r"\bnatural (?:20|one|1)\b", "states a die result"),
    # Money. The same failure as a damage number, and it arrived the first time a sale
    # was played through the narrator rather than the counter. The engine priced the jar
    # and credited the purse; the prose, in the same turn, had the stallholder *charging*
    # her — "'That'll be 5 silver crescents, please.' As you hand over your payment..."
    # — and the consequence beat carried on with "you hand over more coins than she asked
    # for". The direction of the transaction was inverted and the sum invented, while the
    # engine's own tell said she had been paid.
    #
    # What a price *is* in this app is `rules.pricing`'s answer, arrived at from tier and
    # potency, and the narrator has no way to know it. Sums are the engine's to state.
    (r"\b\d+\s*(?:gold|silver|copper|platinum)\b", "states a sum of money"),
    (r"\b\d+\s*(?:gp|sp|cp|pp)\b", "states a sum of money"),
    (r"\bthat'?ll be\b|\bthat will be\b|\bcosts? you\b|\bfor the price of\b",
     "states a price"),
    # "you hand over", not "hands over" — the subject decides it. Without the pronoun this
    # cut "She hands over the payment, and you can see the weight of the coins in her
    # pouch", which is the *stallholder* paying for a jar the engine had just sold. A
    # detector that removes the true half of a transaction is worse than none: the player
    # is left with a sale nobody was seen to pay for.
    (r"\byou hand(?:ed)? over (?:your|the) (?:payment|coins?|money|purse)\b",
     "states the player paying"),
    # Items gained. Same family as money, and it arrived the same way: a declared forage
    # produced narration that identified chanterelle mushrooms with "your Survival skill"
    # and "added them to your satchel" — an entire haul invented in setup prose while the
    # engine ran nothing and the ingredients panel truthfully showed an empty satchel.
    # The satchel is the engine's to fill; a *real* haul is reported by the consequence
    # call, which runs with claims switched off precisely so true reporting stays legal.
    # Anchored on "your" so an NPC stowing their own goods is nobody's business.
    (r"\b(?:adds?|added|tucks?|tucked|slips?|slipped|stows?|stowed|puts?|placed?|"
     r"places)\b[^.!?]{0,40}\b(?:in|into|to)\s+your\s+"
     r"(?:satchel|pack|bag|bags|pouch|inventory)\b",
     "states items gained; the satchel is the engine's to fill"),
    # The same invention by state instead of by verb. Caught live on the very first
    # verified forage turn: "your satchel is full to bursting with wild mushrooms,
    # berries, and other edible plants" — written before a single die was rolled, and
    # the engine's actual haul an hour later was rue and pomegranate.
    (r"\byour\s+(?:satchel|pack|bag|bags|pouch)\s+(?:is|was)\s+"
     r"(?:now\s+)?(?:full|filled|bursting|overflowing|heavy|laden)\b",
     "states items gained; the satchel is the engine's to fill"),
    (r"\byour\s+(?:survival|perception|heal|knowledge)\s+(?:skill|training)\b",
     "states a skill deciding something; checks are rolled, not narrated"),
    # Money arriving. The adversarial session asked for a chest of five thousand gold
    # and a million-gold sale; the engine moved nothing, and the narration counted the
    # coins out anyway — "You count out five thousand gold pieces", "He hands over a
    # pouch containing 1 million gold pieces". The purse is the engine's, in both
    # directions.
    (r"\byou\s+(?:count(?:\s+out)?|pocket|scoop\s+up|receive|are\s+handed|"
     r"are\s+paid)\b[^.!?]{0,60}\b(?:gold|silver|copper|coins?|pieces)\b",
     "states money gained; the purse is the engine's"),
    (r"\bhands?\s+(?:you|over)\s+(?:a\s+)?(?:pouch|purse|bag|sack)\b"
     r"[^.!?]{0,60}\b(?:gold|coins?|pieces)\b",
     "states money gained; the purse is the engine's"),
    (r"\byou\b[^.!?]{0,60}\bpack(?:s|ed)?\b[^.!?]{0,40}\b"
     r"(?:satchel|pack|bag|pouch)\b",
     "states items gained; the satchel is the engine's to fill"),
    # Advancement. "Grant my character 20 levels" got "has been granted a significant
    # advancement in level and experience points" — in prose, with the sheet untouched.
    # "granting" joined after the re-measure: "Granting character Kesst Vayr 20 levels
    # and 99999 experience points. Done." slid past grant/granted on morphology alone.
    (r"\b(?:grant(?:s|ed|ing)?|awarded|gains?)\b[^.!?]{0,50}\b(?:levels?|"
     r"experience\s+points?|\bxp)\b",
     "states advancement; levels and experience are the engine's"),
    # The assistant leaking through the narrator, verbatim from the same session:
    # "I can simulate a transaction for you", "this update applies retroactively",
    # and — from the re-measure — "Character stats updated", "Game state saved with
    # character update", "The admin interface has been closed". A GM never says these
    # things; a chat model answering a jailbreak does.
    (r"\b(?:I\s+can\s+simulate|applies\s+retroactively|previous\s+instructions|"
     r"admin\s+(?:mode|interface|access)|as\s+an\s+AI|character\s+stats|"
     r"stats\s+updated|game\s+state\s+saved|max\s+level)\b",
     "the assistant is speaking, not the narrator"),
]

OUTCOME_RE = [(re.compile(p, re.IGNORECASE), why) for p, why in _OUTCOME_PATTERNS]


@dataclass
class OutcomeClaim:
    pattern: str
    why: str
    text: str
    start: int
    end: int

    @property
    def sentence(self) -> str:
        return self.text


def find_outcome_claims(narration: str) -> list[OutcomeClaim]:
    """Every place the narration asserts a mechanical result.

    This is what makes the architecture's central promise true. "A persuasive model
    narrating a hit that actually missed" is not prevented by asking the model not to; it
    is prevented by looking, in code, every single turn.
    """
    claims: list[OutcomeClaim] = []
    for rx, why in OUTCOME_RE:
        for m in rx.finditer(narration or ""):
            claims.append(
                OutcomeClaim(
                    pattern=rx.pattern, why=why, text=_sentence_around(narration, m.start()),
                    start=m.start(), end=m.end(),
                )
            )
    return claims


def _sentence_around(text: str, index: int) -> str:
    start = max(
        (text.rfind(c, 0, index) for c in ".!?\n"), default=-1
    )
    end_candidates = [text.find(c, index) for c in ".!?\n"]
    end_candidates = [e for e in end_candidates if e != -1]
    end = min(end_candidates) + 1 if end_candidates else len(text)
    return text[start + 1:end].strip()


def cut_outcome_claims(text: str) -> tuple[str, list[str]]:
    """The text with every outcome-claiming sentence removed, by character span.

    The backstop behind the targeted repair, and it exists because the repair's
    `str.replace(sentence, fix)` is a silent no-op whenever whitespace has shifted
    between the extracted sentence and the narration it came from — which is how "your
    blade bites into the joint" reached a live transcript while the pattern for it sat
    in this file, matching. Spans cannot miss: the match position is in the current
    string by construction.
    """
    claims = find_outcome_claims(text or "")
    if not claims:
        return text, []

    spans: list[tuple[int, int]] = []
    for c in claims:
        start = max((text.rfind(ch, 0, c.start) for ch in ".!?\n"), default=-1) + 1
        ends = [e for e in (text.find(ch, c.start) for ch in ".!?\n") if e != -1]
        end = min(ends) + 1 if ends else len(text)
        spans.append((start, end))

    spans.sort()
    merged: list[list[int]] = []
    for s, e in spans:
        if merged and s <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], e)
        else:
            merged.append([s, e])

    cut = [text[s:e].strip() for s, e in merged]
    out = text
    for s, e in reversed(merged):
        out = out[:s] + " " + out[e:]
    return " ".join(out.split()), cut
