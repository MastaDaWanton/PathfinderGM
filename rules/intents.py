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
import functools
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


def _square(raw, op: str, index: int) -> tuple[int, ...]:
    """A grid square, however the GM wrote it.

    A model asked for coordinates returns `[4, 7]` or `{"col": 4, "row": 7}` or `"4,7"`
    depending on the phase of the moon, and all three mean the same square. Normalising
    here rather than in the engine keeps every op that grows a position later reading one
    shape — and gives one error message instead of three.

    An optional third number is the **level**, five feet apiece, added 2026-09-14 — so
    `[5, 5, 4]` is the square twenty feet above `[5, 5]`, where a spider on a ceiling
    lives. Two numbers still mean the ground and are still what almost everything sends;
    the engine is what decides whether the creature may go up, not this.
    """
    if isinstance(raw, dict):
        try:
            got = (int(raw["col"]), int(raw["row"]))
            if raw.get("level") is not None:
                got += (int(raw["level"]),)
            return got
        except (KeyError, TypeError, ValueError):
            raise IntentError(
                f"{op}: square must have integer col and row, got {raw!r}",
                "schema", index
            ) from None
    if isinstance(raw, str):
        raw = [bit for bit in raw.replace("(", "").replace(")", "").split(",") if bit.strip()]
    try:
        bits = tuple(int(n) for n in raw)
    except (TypeError, ValueError):
        bits = ()
    if len(bits) in (2, 3):
        return bits
    raise IntentError(
        f"{op}: square must be a square like [col, row], or [col, row, level] for one "
        f"off the ground, got {raw!r}",
        "schema", index
    )


def _known_weapon(name) -> bool:
    """Imported lazily: `rules.weapons` reads Django settings, and this module is imported
    before settings are configured in some entry points."""
    from .weapons import has

    # The armament's own weapon exists on the wearer, not in the table — the sheet
    # builds it from the class's blood die. Validation lets it through; whether the
    # armament is actually formed is the engine's legality check, with a better error.
    if str(name).strip().lower() in ("armed punch", "armed punches", "blood gauntlets"):
        return True
    # A natural weapon is the same shape of thing and was not getting the same courtesy.
    # `Actor.weapon` has always resolved bite, claws, gore and the rest through
    # `natural_weapon` off the race document — but the 456-weapon table holds none of
    # them, so this gate refused the name before the engine was ever asked, and **no
    # racial natural attack could be declared at all**. A race could take Bite and the
    # player could never bite anything; the whole attack group of the evolution pool was
    # unreachable, not merely the fifteen entries that admit to a `not_yet`.
    #
    # Measured 2026-09-14: bite, claws, claw, gore, slam, pincers, sting, tail slap,
    # tentacle and wing buffet — every one `has()` == False.
    #
    # Let through here and refused by the engine, exactly as the armament is: validation
    # cannot see the actor, and "you have no bite" is a better sentence than "no such
    # weapon, did you mean bardiche".
    if str(name).strip().lower() in natural_weapon_names():
        return True
    return has(str(name))


@functools.lru_cache(maxsize=1)
def natural_weapon_names() -> frozenset[str]:
    """Every name a natural attack answers to, read from the evolution pool.

    Read rather than listed, because a list here would go stale in the direction that
    hides the bug: an evolution added with a new weapon would be refused by this gate
    and nobody would think to look in `intents.py` for the reason.
    """
    from .races import natural_weapon_aliases

    return natural_weapon_aliases()


def _suggest(name: str, candidates) -> str:
    """A rejection the model cannot act on costs a whole regeneration.

    Naming the nearest legal value turns a blind retry into a repair, which is the same
    reason the ref rejection lists the refs that do exist.
    """
    close = difflib.get_close_matches(str(name).strip().lower(), list(candidates), n=3, cutoff=0.5)
    if close:
        return " Did you mean " + " or ".join(repr(c) for c in close) + "?"
    return ""


def _bounded(value, low: int, high: int, index: int, what: str) -> int:
    """A model-authored count, coerced and clamped, refusing what is not a number.

    "No model authors a number" is half of law 3, and the half the op table kept
    forgetting: `spawn.count` was bounded and `give.count`, `forage.hours` and
    `attack.iteration` were not — so one authored value could mint a million gold
    pieces, drive a foraging loop for a year, or index past the end of an attack
    sequence and raise inside resolution as a 500.

    Clamping rather than refusing an out-of-range number is deliberate and matches
    `rules/dc.py`: the model meant "a lot", the engine decides how much, and the turn
    survives. Only a value that is not a number at all is refused, because there is no
    honest reading of it — and the refusal names what the field is for, so the retry
    is a repair rather than a guess.
    """
    try:
        return max(low, min(high, int(value)))
    except (TypeError, ValueError):
        raise IntentError(f"{what}. {value!r} is not a number.", "schema", index)

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
                    # `undecided` is written by code, never by the model: the target
                    # check hands an ambiguous attack back as a printed question.
                    # `item`: the object an improvised weapon IS — "chunk of wood",
                    # "pebble" — so the tell can name it and the props ledger can
                    # move it.
                    "iteration", "undecided", "item", "thrown"), "player"),
    # `lethality` because a Blood Bender paying for an ability in non-lethal
    # damage and one taking a sword are not in the same trouble.
    "damage": (("amount", "type"), ("to", "lethality"), "hidden"),
    # Healing is not negative damage: it never restores temporary hit points and never
    # carries a character up from below zero the way `damage` carries them down.
    "heal": (("amount",), ("to",), "hidden"),
    # Damage reduction, immunity, energy resistance and vulnerability, granted with a
    # clock. Before this there was no op for any of them: `effectspec` offered all four
    # types, 123 spells and 13 magic items authored one, and `consumables` had no branch
    # — so the dose was spent and nothing happened, with no error anywhere.
    "defence": (("kind",),
                ("against", "amount", "bypass", "to", "duration", "source"), "hidden"),
    "buff": (("type", "target", "amount"),
             ("to", "source", "duration", "note", "bonus_type"),
             "hidden"),
    "temp_hp": (("amount",), ("to", "source", "duration"), "hidden"),
    # Poison, disease, a spell that withers: damage to a score rather than to hit points.
    # `drain` for the permanent kind, which no amount of resting brings back.
    "ability_damage": (("ability", "amount"), ("to", "drain"), "hidden"),
    # A fall, a fire, acid, cold: the rule document GM fiat cites (content/rules/
    # hazards.json). The model names the rule and fills its one slot — how far, how
    # many rounds — and the engine rolls the row. Stage 8d: before this a fall was a
    # bare `damage` with dice the model wrote.
    "hazard": (("rule",), ("to", "distance_ft", "rounds", "hours", "days",
                           "deliberate", "immersed"), "hidden"),
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
    "travel": ((), ("biome", "place", "note", "with"), "hidden"),
    # Leaving the town altogether, which `travel` has never been able to do: it moves the
    # ground underfoot inside one settlement, and `Scene.location_id` was written once at
    # campaign creation and never again. A separate op rather than another `travel` param
    # because they are different scales doing different work — one costs a move, the
    # other costs days — and because a model that says "we set out for Zhilgoroth" should
    # not be able to reach it by naming a biome.
    "journey": (("to",), ("note", "with", "pace"), "hidden"),
    # Doors two and three of rules/places.py. `found`: the player makes a place from
    # where they stand — a base at a friend's house, the alley behind the market —
    # with an owner the engine knows; the engine mints the id, the narrator never
    # does. `venture`: ground gone into — the sewers, a cave outside the town —
    # generated from a seed on entry, the same next time; `parent` names the place
    # it hangs off, default here.
    # A task taken up: a quest card with objectives to tick, a giver and a promise.
    # `quest_step` ticks one objective by its number, with what was done as a note.
    # Talking. There was no op for this at all among the other forty-one, so every line
    # the player wrote as speech could only land in `narrate_only` — and a turn that
    # resolves to narrate_only has no tells, which is why the 2026-09-08 playtest kept
    # answering speech with the holding line while actions in the same session worked.
    #
    # It rolls nothing and costs nothing, because Pathfinder 1e already says so: "In
    # general, speaking is a free action that you can perform even when it isn't your
    # turn. Speaking more than a few sentences is generally beyond the limit of a free
    # action." A *directed* social attempt — persuade, deceive, threaten — is a
    # different thing with a DC and a time cost, and it is a `check`, not this.
    #
    # `words` is what the player's character actually said, carried through so the
    # narrator dresses the line rather than inventing a different one; `to` is who they
    # said it to, and is absent when they addressed the room.
    "say": (("words",), ("actor", "to", "quoted"), "hidden"),
    "quest": (("title", "objectives"), ("actor", "giver", "reward", "about"), "player"),
    "quest_step": (("quest", "objective"), ("actor", "note"), "player"),
    "found": (("name",), ("actor", "owner", "parent", "about"), "player"),
    "venture": (("kind",), ("actor", "parent", "name"), "player"),
    # Two ships and the distance between them. `do` is close / sheer off / ram / grapple
    # / board, and `with` names whoever goes across — the same word travel uses for the
    # people who come along, because a boarding party is a party.
    "sea": (("do",), ("with", "actor"), "player"),
    # Searching the ground. The roll is the player's: it is their afternoon.
    # `hours` because foraging is time now: a minimum of one, and as many as the player
    # wants to spend. Every hour is its own Survival check, and past a day awake every
    # hour is also a Will save against dropping where you stand.
    "forage": ((), ("actor", "track", "biome", "hours"), "player"),
    # Ore, not herbs: the same expedition against the blacksmith's stock list, in
    # ground that carries it — mountain, hills, underground, a bog for bog iron.
    "prospect": ((), ("actor", "hours"), "player"),
    # Stripping a body. "I loot the watchman I take everything" was narration and
    # nothing else — the coins, the sword, the chain shirt all described and none of
    # them in the inventory — the same gap the trade op closed for shops. `from` is
    # the body; the engine owns what is actually on it.
    "loot": (("from_",), (), "hidden"),
    # `descriptors` is what the effect declares itself to BE — a fear effect, a
    # poison, a mind-affecting compulsion — which is what 1e attaches immunity to.
    # Without it the only question that can be asked is "are you immune to being
    # shaken", and the answer to that is not the rule.
    "condition": (("condition",), ("duration", "to", "descriptors", "ends"), "hidden"),
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
    # The penalty is the rule's (−4, rules/compulsion.py), not a param: it was an
    # unbounded model integer until stage 8d.
    "compel": (("to",), ("duration", "why"), "hidden"),
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
    # `zone` is no longer required. Stage 7 measured why it was the single worst
    # schema rejection in play — 17 rejections against 2 attempts, 89% — and the reason
    # was what the param is MADE OF: `engaged`/`near`/`far` is engine vocabulary, and
    # the player writes "I back toward the door", which contains none of it. A square
    # says where; a bare move keeps the zone it had. Only `attack`, which has no
    # required params at all, never failed.
    "move": ((), ("zone", "who", "square"), "hidden"),
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
    # Experience awarded outright: the GM's story award for a matter the fights do not
    # pay, and the author's own hand through `/cheat I gain 2000 experience` — which
    # did nothing twice on 2026-09-18 because no op carried experience at all
    # (item 1/20). Hidden, so the cheat may use it; the engine's `award_xp` is the one
    # writer.
    "xp": (("amount",), ("reason",), "hidden"),
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
# Params only code writes, never the model: accepted by validation, left out of the
# "takes" list a rejection shows the model, so it is never taught to reach for them.
# `undecided` is `judgement.check_the_target` handing an ambiguous attack back as a
# printed question.
CODE_ONLY_PARAMS = frozenset({"undecided"})

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
    # Where the number came from — `item:<stock id>`, `spell:<id>`, `ability:<path>/
    # <key>`, `rule:<id>`, `creature:<template>`, `author:cheat`, `author:test` — and
    # the display name the tell uses. Never in `params`, because `parse` treats params
    # as the model's and pops engine-owned keys silently; this is stamped after parse
    # by `Engine.validate(raw, origin=...)`, the one trusted path, so a door's own heal
    # and the model's are distinguishable for the first time. Stage 8, 2026-09-03:
    # measured twice, "I drink my healing potion" with an empty satchel became a bare
    # `heal 1d8+1` — the prompt's own worked example handed back — and the engine
    # applied it, because nothing could tell it from the potion's.
    origin: str = ""
    origin_name: str = ""

    def targets(self) -> list[str]:
        if self.target is None:
            return []
        return list(self.target) if isinstance(self.target, list) else [self.target]

    def as_dict(self) -> dict:
        return {
            "id": self.id, "op": self.op, "actor": self.actor, "target": self.target,
            "because": self.because, "params": self.params, "visibility": self.visibility,
            "ignored_params": self.ignored_params,
            "origin": self.origin, "origin_name": self.origin_name,
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

    # Scoped to the op, not global. The table is a courtesy — the GM writes "against"
    # and means `opposed_by` on a check — but applied to every op it silently renames a
    # param another op legitimately declares: `defence` declares `against`, and the
    # alias took it away and then refused the intent for missing it. An alias fires
    # only when the op actually wants the target and does not itself declare the word.
    declared = set(required) | set(optional)
    for said, means in PARAM_ALIASES.items():
        if said in params and means not in params                 and means in declared and said not in declared:
            params[means] = params.pop(said)

    missing = [p for p in required if params.get(p) in (None, "")]
    if missing:
        raise IntentError(
            f"{op}: missing required param(s) {', '.join(missing)}", "schema", index
        )

    # Ahead of the engine-owned pop on purpose: that set IGNORES, it does not refuse,
    # and provenance is the one thing a model asserting it must be told about.
    if "origin" in params or "origin_name" in params:
        raise IntentError(
            f"{op}: origin is the engine's to stamp, never yours. Name the document "
            f"instead: use_item item=<id> for a jar, cast spell=<id> for a spell, "
            f"use_ability ability=<name> for a power.", "schema", index)

    unknown = set(params) - set(required) - set(optional)
    ignored = sorted(unknown & ENGINE_OWNED_PARAMS)
    for key in ignored:
        params.pop(key, None)
    unknown -= set(ignored)
    if unknown:
        raise IntentError(
            f"{op}: unknown param(s) {', '.join(sorted(unknown))}. "
            f"{op} takes "
            f"{', '.join(sorted((set(required) | set(optional)) - CODE_ONLY_PARAMS)) or 'no params'}.",
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
        # Talking somebody round is the exception, and it is the engine's DC rather than
        # a missing one: Diplomacy or Intimidate aimed at a named person is resolved
        # against the Core Rulebook's own table — 25/20/15/10/0 by their attitude plus
        # their Charisma, or 10 + Hit Dice + Wisdom for a threat (`rules/attitude.py`).
        # A band named here would be the plan setting the price of changing a mind.
        social = (p.get("skill") in ("diplomacy", "intimidate")
                  and intent.targets() and not p.get("opposed_by"))
        if social and p.get("dc"):
            raise IntentError(
                f"check: the DC for {p['skill']} on a named person is the engine's — "
                f"the book sets it from their attitude and their own scores. Drop the "
                f"dc and keep the target.", "legality", index)
        if not p.get("dc") and not p.get("opposed_by") and not social:
            raise IntentError(
                "check: a check needs something to beat. Add either "
                '"dc": {"band": "tough"} (one of ' + ", ".join(DC_BANDS) + "), or "
                '"opposed_by": {"ref": "<a ref in the scene>", "skill": "perception"} '
                "when someone is actively resisting. To talk somebody round, name them "
                'with "target" and the engine reads the DC off them.',
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
        # Which swing of a full attack this is. Unvalidated, it reached
        # `whole[min(int(it), len(whole) - 1)]` in the engine, where a non-numeric value
        # raised inside resolution — a 500 rather than a refusal the model could act on.
        if p.get("iteration") not in (None, ""):
            p["iteration"] = _bounded(
                p["iteration"], 0, 15, index,
                "attack: iteration is which swing of a full attack this is, counting "
                "from 0")

    elif op == "defence":
        kinds = ("damage_reduction", "immunity", "resistance", "vulnerability")
        raw = str(p.get("kind", "")).strip().lower().replace(" ", "_")
        if raw not in kinds:
            raise IntentError(
                f"defence: {p.get('kind')!r} is not a kind of defence."
                + _suggest(raw, kinds)
                + f" The kinds are: {', '.join(kinds)}.",
                "schema", index)
        p["kind"] = raw
        # Three of the four are AGAINST something and one is not: damage reduction is
        # an amount and what bypasses it, with no damage type attached, so requiring
        # `against` for every kind refused the only one that cannot have it.
        if raw != "damage_reduction" and not str(p.get("against", "") or "").strip():
            raise IntentError(
                f"defence: {raw} needs `against` — what it protects from, like "
                f"\"fire\" or \"poison\". Only damage_reduction has none.",
                "schema", index)
        if raw == "damage_reduction" and not p.get("amount"):
            raise IntentError(
                "defence: damage_reduction needs an amount — how many points it stops.",
                "schema", index)
        if p.get("amount") not in (None, ""):
            p["amount"] = _bounded(
                p["amount"], 0, 1000, index,
                "defence: amount is how many points it stops")

    elif op == "buff":
        # A closed vocabulary the code does not enforce is just a suggestion, and this
        # one decides whether two bonuses stack: an unrecognised type would fall to
        # untyped, which stacks with everything, so a typo would silently double a
        # number rather than being refused.
        raw = str(p.get("bonus_type", "") or "").strip().lower()
        if raw:
            from .effectspec import VOCAB

            allowed = {o["id"] for o in VOCAB["bonus_type"]}
            fixed = {"armor": "armour", "natural armor": "natural armour"}.get(raw, raw)
            if fixed not in allowed:
                raise IntentError(
                    f"buff: {p['bonus_type']!r} is not a bonus type."
                    + _suggest(raw, allowed)
                    + f" The types are: {', '.join(sorted(allowed))}.",
                    "schema", index)
            p["bonus_type"] = fixed

    elif op == "give":
        # The purse is the engine's in both directions, and that has to hold at the
        # intent layer too: `count` was `max(1, int(...))` in the engine with no ceiling,
        # so one model-authored number could mint a million gold pieces into a campaign
        # whose whole economy is hand-priced. Bounded like `spawn.count`, and generously
        # — a sack of forty arrows is a real thing to hand over.
        if p.get("count") not in (None, ""):
            p["count"] = _bounded(
                p["count"], 1, 500, index,
                "give: count is how many of the item change hands")

    elif op == "forage":
        # Bounded on the browser path and bounded in the injector; unbounded on the one
        # path the model actually uses, where it drives the loop the op runs. A day is
        # already an enormous forage — `_op_forage` refuses company for a reason.
        # 48 is the injector's own ceiling (gm/judgement.py), not a new number: two
        # paths already bounded this and the one the model uses did not, so matching
        # them is the fix rather than inventing a third answer. It must stay above a
        # day, because the survival rules are built to be exercised past one — a
        # thirty-hour forage is how the awake clock's checks get tested at all.
        if p.get("hours") not in (None, ""):
            p["hours"] = _bounded(
                p["hours"], 1, 48, index,
                "forage: hours is how long is spent on the ground, 1 to 48")

    elif op == "move":
        # Optional now (see the op table): a zone word the fiction never contains is
        # not worth a rejected turn. Given, it must still be one of the three.
        zone = str(p.get("zone") or "").strip().lower()
        if zone and zone not in ZONES:
            raise IntentError(
                f"move: zone must be one of {ZONES}, got {zone!r}", "schema", index
            )
        if zone:
            p["zone"] = zone
        else:
            p.pop("zone", None)
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
        # Bounded, and never negative. `amount` was a bare `int()` with no floor and no
        # ceiling, and the engine hands it to `tick_effects`, whose body is
        # `e.rounds_left -= rounds` — so a negative advance rewound the world clock past
        # market days already sold AND *extended* every timed effect on every actor in
        # the scene. The ceiling is a year in the unit asked for, which is far past any
        # honest turn and short of the numbers that make the tick loop meaningless.
        ceiling = {"round": 100_000, "minute": 10_000, "hour": 8_760, "day": 365}[unit]
        p["amount"] = _bounded(
            p["amount"], 0, ceiling, index,
            f"advance_time: amount is how much time passes, 0 to {ceiling} {unit}s")

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


# The ops whose `amount` lands on a sheet. Every one of them needs an origin the engine
# stamped: a jar, a spell, an ability, a rule, a creature's stat block, or the author.
# The model is not offered these ops at the sampler (gm.prompts.turn_schema); the check
# in Engine._check_legality is the backstop for the engine's own doors.
AMOUNT_OPS: frozenset[str] = frozenset(
    {"damage", "heal", "buff", "temp_hp", "defence", "ability_damage", "item_damage"})


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

# An enclosed place the player could be said to have entered, with its article and up
# to three adjectives — commas included, because "a small, stifling room" is the live
# example and `\w+` alone cannot cross the comma. One definition, used by both of the
# movement patterns below.
_A_PLACE = (r"(?:the|a|an|another)\s+(?:[\w-]+,?\s+){0,3}?"
            r"(?:door|doorway|room|chamber|hall|hallway|corridor|passage|passageway|"
            r"vestibule|cellar|stairwell|threshold|gate|archway|antechamber|office|"
            r"study|library|kitchen|storeroom|shop|house|building|cell|vault|"
            r"space)\b")

# Phrasings that assert a mechanical result. Every one of these is something a model
# actually produced in testing while being asked, in the prompt, not to.
_OUTCOME_PATTERNS: list[tuple[str, str]] = [
    (r"\byou (?:take|suffer|lose)\b[^.]{0,30}?\b\d+\b", "states damage taken"),
    (r"\b\d+\s*(?:points? of\s*)?damage\b", "states a damage number"),
    (r"\byour?\s+(?:hit points?|hp)\b", "states hit points"),
    (r"\byou (?:succeed|fail|manage to|barely make|don't make)\b", "states success or failure"),
    # Where the player is standing is the engine's — `Actor.at`, one writer, the whole
    # point of the places stage. Measured live 2026-09-04: the turn resolved to
    # `narrate_only`, the scene stayed at the market, and the prose read "the door
    # gives way with a groan of complaining wood, and you are shoved forward into a
    # small, stifling room", then furnished the room with a desk, a man and a coin.
    # The fiction moved the character and the state did not, which is the same class of
    # lie as a narrated hit that never rolled.
    #
    # Deliberately narrow. It fires on the player crossing into an enclosed place —
    # into/through a door, a room, a passage — and not on ordinary movement inside a
    # scene ("you step closer", "you move to the rail"), because within a place is the
    # model's to describe. `travel` and `move` back it.
    (rf"\byou (?:are |get )?"
     rf"(?:step|steps|stepped|stumble|stumbles|walk|walks|move|moves|push|pushes|"
     rf"shove|shoved|pushed|carried|pulled|swept|spill|spills|duck|ducks|slip|slips|"
     rf"enter|enters|entered|cross|crosses|crossed)\w*\s+"
     rf"(?:forward\s+|back\s+|out\s+|in\s+)?(?:through|into|inside|past)\s+"
     rf"{_A_PLACE}",
     "states the player went somewhere; where they are is the engine's"),
    # The same claim with no verb in it at all.
    (rf"\byou find yourself\s+(?:in|inside|within|standing in)\s+{_A_PLACE}",
     "states the player went somewhere; where they are is the engine's"),
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
    # A loot narrated before the engine opened the pockets. Live: the setup beat had
    # "removing his wallet, a small pouch of coins, and a leather belt with a silver
    # buckle... Your pockets now hold a few copper pieces, some silver coins, and the
    # leather belt" — and the corpse actually carried a club, two silver, chalk stubs
    # and work gloves. The player got the real haul AND a belt that never existed,
    # which reads as being jipped the moment the sheet disagrees with the sentence.
    (r"\byour\s+pockets?\s+(?:now\s+)?(?:holds?|contains?)\b",
     "states items gained; the pockets are the engine's to fill"),
    (r"\byou\s+take\s+(?:these|those)\s+items\b",
     "states items gained; the pockets are the engine's to fill"),
    (r"\b(?:removing|you\s+remove|pulling\s+out|you\s+pull)\b[^.!?]{0,60}"
     r"\b(?:wallet|coin\s+purse|pouch\s+of\s+coins|belt|rings?)\b",
     "states items gained; the pockets are the engine's to fill"),
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


# What the engine must already have decided before prose is allowed to say it. The
# contract's rule is that an outcome-claim is prose stating a mechanic **no tell backs**,
# and until this existed the detector had never been shown the engine's answer — it could
# ask "does this sentence assert a mechanic" and never "was that mechanic true".
#
# Which is why the two doors the player actually reads run with `claims=False`: written
# AFTER the dice, "your blade finds the gap" is reporting rather than invention. Measured
# on the twelve real campaigns, scrubbing them blind cuts 25 of 43 consequence beats below
# forty characters — the beat is destroyed.
#
# Keyed on what the OUTCOMES structurally establish, never on the text of the tells.
# Searching a tell's prose for a word to answer a mechanical question is exactly the
# string-matching stage 5 spent itself removing.
_BACKED_BY = {
    "hit": ("states an attack landing", "states an attack having landed",
            "states being hit", "states a wound already dealt"),
    "miss": ("states an attack missing",),
    "damage": ("states a damage number", "states damage taken", "states hit points",
               "states a wound already dealt"),
    "verdict": ("states success or failure", "states an action succeeding"),
    "save": ("states a save succeeding",),
    "perception": ("states a perception result",),
    "stealth": ("states a stealth result", "states an escape"),
    "roll": ("states a die result", "states a roll's result"),
    "purse": ("states a sum of money", "states money gained; the purse is the engine's",
              "states a price", "states the player paying"),
    "items": ("states items gained; the pockets are the engine's to fill",
              "states items gained; the satchel is the engine's to fill"),
    "xp": ("states advancement; levels and experience are the engine's",),
    "moved": ("states the player went somewhere; where they are is the engine's",),
}


def claims_the_engine_backs(outcomes) -> frozenset[str]:
    """Which mechanical assertions prose may make, because the dice already made them.

    Deliberately NOT derived from the tells' text. A tell is a sentence, and asking
    whether it "mentions a hit" is a regex over English — a second vocabulary living in
    the presentation layer. The outcome record says what happened in fields.

    Nothing here is licence to invent a NUMBER. The patterns that catch a stated DC, a
    skill deciding an outcome, or the assistant speaking in its own voice are backed by
    nothing and never can be.
    """
    backed: set[str] = set()

    def allow(key: str) -> None:
        backed.update(_BACKED_BY.get(key, ()))

    for o in outcomes or []:
        # Outcomes arrive as objects live and as dicts out of the turn log, and the
        # measurement that justifies this function replays the log.
        get = o.get if isinstance(o, dict) else (lambda k, d=None, _o=o: getattr(_o, k, d))
        op = str(get("op", "") or "")
        verdict = str(get("verdict", "") or "")
        effects = list(get("effects", None) or [])
        rolls = list(get("rolls", None) or [])

        if verdict:
            allow("verdict")
        if verdict == "hit":
            allow("hit")
        if verdict == "miss":
            allow("miss")
        if op == "save" and verdict == "success":
            allow("save")
        if any(isinstance(e, dict) and e.get("kind") == "damage"
               and int(e.get("amount") or 0) > 0 for e in effects):
            allow("damage")
        if any(str((r.get("visibility") if isinstance(r, dict)
                    else getattr(r, "visibility", ""))) == "player" for r in rolls):
            allow("roll")
        if op == "check":
            skill = str((get("params", None) or {}).get("skill", "")).lower()
            if "perception" in skill:
                allow("perception")
            if "stealth" in skill:
                allow("stealth")
        if op in ("loot", "trade", "buy", "sell", "give", "pay"):
            allow("purse")
            allow("items")
        if op in ("forage", "craft", "take"):
            allow("items")
        if op == "xp":
            allow("xp")
        # Where the party is standing is `Actor.at`, and the engine is its one writer
        # (docs/places-8b-plan.md). Prose may say the player went through a door only
        # when an op actually took them through one.
        if op in ("travel", "move"):
            allow("moved")
    return frozenset(backed)


# A denial in the words before an escape verb: "doesn't pull away", "without breaking
# free", "never slips loose". Read over the forty characters before the match.
_NEGATED = re.compile(
    r"\b(?:doesn't|does not|didn't|did not|not|never|without|nor|no longer|fails? to|"
    r"cannot|can't|couldn't|could not|unable to|instead of)\s+(?:\w+\s+){0,3}$", re.I)


def find_outcome_claims(narration: str, backed=(), restrained: bool = True) -> list[OutcomeClaim]:
    """Every place the narration asserts a mechanical result the engine never reached.

    This is what makes the architecture's central promise true. "A persuasive model
    narrating a hit that actually missed" is not prevented by asking the model not to; it
    is prevented by looking, in code, every single turn.

    `backed` is what the dice already decided — see `claims_the_engine_backs`. Prose
    written after resolution is reporting, and reporting is the narrator's whole job;
    without this the detector cut the true sentence beside the invented one, which is why
    the doors the player reads had it switched off altogether.
    """
    allowed = frozenset(backed or ())
    claims: list[OutcomeClaim] = []
    for rx, why in OUTCOME_RE:
        if why in allowed:
            continue
        # An escape is a claim only when somebody is HELD — a grapple, a pin, an
        # entanglement on the books — and only when it is asserted, not denied.
        # Measured in the brothel (2026-09-18): "She doesn't pull away; instead … she
        # works to discard the layers between you" matched `pull … away`, negated, in a
        # room where nobody held anybody, and the sentence was cut.
        if why == "states an escape" and not restrained:
            continue
        for m in rx.finditer(narration or ""):
            if why == "states an escape" and _NEGATED.search(narration[max(0, m.start() - 40):m.start()]):
                continue
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


def cut_outcome_claims(text: str, restrained: bool = True) -> tuple[str, list[str]]:
    """The text with every outcome-claiming sentence removed, by character span.

    The backstop behind the targeted repair, and it exists because the repair's
    `str.replace(sentence, fix)` is a silent no-op whenever whitespace has shifted
    between the extracted sentence and the narration it came from — which is how "your
    blade bites into the joint" reached a live transcript while the pattern for it sat
    in this file, matching. Spans cannot miss: the match position is in the current
    string by construction.
    """
    claims = find_outcome_claims(text or "", restrained=restrained)
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
