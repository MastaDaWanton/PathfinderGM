"""Guided character creation: the settled decision, finally built.

Everything here is validated the way the table validates a GM: the rules decide, and a
refusal names the number. The output is exactly the dict a pregen file holds, so a made
character and a shipped one are indistinguishable to everything downstream — `from_dict`,
the roster, the campaign. No new save shape, no second loader.

What is deliberately simple, stated so it reads as a decision:

- **Point buy, 20 points** — the Core Rulebook's "High Fantasy" budget rather than the
  15-point standard, because a solo character has nobody to be carried by.
- **Racial modifiers are baked into the scores at creation.** The sheet has no live race
  system; a dwarf is +2 Con because the number 16 is written down, the same way every
  pregen already works. The race's speed and size are written the same way.
- **Spells known are capped, not curated.** A wizard starts with 3 + Int mod first-level
  spells in the book, a sorcerer knows 2, a bard 4 cantrips' worth — the caps are the
  book's, the choice of which spells is entirely the player's.
"""
from __future__ import annotations

import re

from . import backgrounds as backgrounds_mod
from . import casting, classes as classes_mod, dice, feats as feats_mod, houserules
from . import races as races_mod
from . import leveling
from .sheet import from_dict, gender_from_pronouns, pronouns_for_gender
from .tables import ARMOUR, SKILLS, WEAPONS

# The races used to be a seven-row table here. They are documents in content/races
# now (rules/races.py), in the feat grammar, so a world's own peoples and a table's
# homebrew join by the same door and the sheet reads all of them live.
# Core Rulebook Table 1-2, typed out because it is not linear and every generated
# approximation of it is wrong at one end or the other.
POINT_COSTS = {7: -4, 8: -2, 9: -1, 10: 0, 11: 1, 12: 2, 13: 3, 14: 5, 15: 7,
               16: 10, 17: 13, 18: 17}
# The budget itself lives in rules/houserules.py — it is a tier the player picks on
# the homebrew tab, 20 ("High fantasy") by default, and reading it from a constant
# here is how a forge and a validator come to disagree. The 18 ceiling lives there too.

# The book's table stops at 18. Its marginal cost rises by one every second point —
# 14 and 15 cost 2 each, 16 and 17 cost 3, 18 costs 4 — so a score above 18 continues
# that curve: 19 costs 4 more, 20 and 21 five each, 22 and 23 six. This is
# extrapolation and not the Core Rulebook, which is exactly why it is only reachable
# by lifting a ceiling on the homebrew tab.
ABILITY_FLOOR = 7


def point_cost(score: int) -> int:
    """What one score costs, on the book's table or on its continuation."""
    score = int(score)
    if score in POINT_COSTS:
        return POINT_COSTS[score]
    if score < ABILITY_FLOOR:
        raise ValueError(f"{score} is below the floor of {ABILITY_FLOOR}")
    total, step = POINT_COSTS[18], 4
    for n in range(19, score + 1):
        total += step
        # The step grows on every odd score, which is the rhythm the printed table has
        # from 14 upward: pairs of equal increments.
        if n % 2:
            step += 1
    return total


def _reachable_cap() -> int:
    """The highest score this table's rules and budget could actually reach.

    With a ceiling that is the ceiling. Without one it is arithmetic: five other
    scores must still be bought at 7 (which refunds points), so the budget plus those
    refunds is what one score has to spend.
    """
    cap = houserules.ability_cap()
    if cap:
        return cap
    budget = houserules.point_budget()
    if not budget:
        return 60                      # unlimited: the table's own top score
    purse = budget - 5 * POINT_COSTS[ABILITY_FLOOR]
    top = 18
    while point_cost(top + 1) <= purse and top < 60:
        top += 1
    return top


def point_costs_to(cap: int) -> dict[int, int]:
    """The whole table the wizard draws its counter from, up to a ceiling."""
    return {n: point_cost(n) for n in range(ABILITY_FLOOR, max(18, cap) + 1)}

# What every character is wearing before anything else is bought. The Core Rulebook
# gives one outfit free at first level and it never reached the sheet, so a character
# stood in the opening scene with a sword, armour and, by the app's own reckoning, no
# clothes. Free, no mechanics, and it fills the `body` slot the equipment page draws.
OUTFITS: dict[str, str] = {
    "barbarian": "cold-weather outfit", "bard": "entertainer's outfit",
    "cleric": "cleric's vestments", "druid": "traveler's outfit",
    "fighter": "traveler's outfit", "monk": "monk's outfit",
    "paladin": "traveler's outfit", "ranger": "traveler's outfit",
    "rogue": "traveler's outfit", "sorcerer": "traveler's outfit",
    "wizard": "scholar's outfit", "blood bending": "traveler's outfit",
}
DEFAULT_OUTFIT = "traveler's outfit"

# What a first-level character walks out the door holding: an outfit, and their own hands.
#
# Eleven hand-written class kits stood here until 2026-09-19, when the player asked for
# them to go — "remove the starting items from classes and give them extra starting gold,
# we have the outfitter now". Removing them is a return to the Core Rulebook rather than a
# nerf, and the arithmetic says so: starting wealth was ALREADY rolled per class
# (`starting_purse` below), so a character was getting the book's full wealth *and* a free
# kit on top. A fighter's kit priced at 172 gp against an average roll of 175 — the "extra
# gold" the player asked for is the gold that was always there and had been quietly
# pre-spent on somebody else's choices.
#
# What the book actually grants is one line: "each character begins play with an outfit
# worth 10 gp or less" — which is `OUTFITS` above, and is kept. Everything else is now
# bought at the outfitter, which is the step between the sheet and the road.
#
# Nothing else in the app granted gear, and a homebrew class never had a kit at all, so
# this also ends an inconsistency: the eleven shipped classes were the only ones the rule
# did not apply to.

# How many level-≤1 spells a new caster writes down. The wizard's is a formula, so it is
# resolved against the built Intelligence; `None` means the class picks nothing at
# creation (a cleric or druid prepares off the whole list every morning).
SPELLS_KNOWN: dict[str, object] = {
    "wizard": "3 + int_mod", "sorcerer": 2, "bard": 4,
}


def max_hit_die(spec) -> int:
    """The best a class's first-level hit die can roll.

    A hit die is not always a number. The Core classes declare `8` or `12`, and a
    homebrew class is free to declare notation — Blood Bending ships `"2d8"`, and
    `int("2d8")` raised a ValueError that reached the browser as a 500, which the
    forge showed as a button that did nothing at all. Anything unreadable falls back
    to a d8: refusing to build the character over its hit die would be a worse answer
    than the commonest die in the game.
    """
    if isinstance(spec, (int, float)):
        return max(1, int(spec))
    text = str(spec).strip().lower()
    if text.isdigit():
        return max(1, int(text))
    m = re.fullmatch(r"(\d*)d(\d+)\s*(?:([+-])\s*(\d+))?", text)
    if not m:
        return 8
    count = int(m.group(1) or 1)
    total = count * int(m.group(2))
    if m.group(3):
        total += int(m.group(4)) * (-1 if m.group(3) == "-" else 1)
    return max(1, total)


def die_label(spec) -> str:
    """How a hit die is written on a class card. `8` is a d8; `"2d8"` is already said."""
    return f"d{spec}" if isinstance(spec, (int, float)) or str(spec).isdigit() else str(spec)


def _domains_mod():
    from . import domains as domains_mod

    return domains_mod


def _domain_menu() -> list[dict]:
    """Every domain with a sample of what it grants, for the forge's picker."""
    mod = _domains_mod()
    out = []
    for name in mod.names():
        first = mod.spells_of(name, 1)
        out.append({"name": name, "spells": len(mod.spells_of(name)),
                    "first": first[0].replace("-", " ") if first else ""})
    return out


def starter_domains(cid: str) -> list[str]:
    """A legal opening pair of domains for a class that takes them, or [].

    The same shape and the same reason as `starter_spells` below: a cleric with no domains
    is refused, the way a wizard with an empty book is refused, so every "build every class"
    caller needs a legal pick to hand. The player's own choice is the point — this is the
    default a test or a script uses, not a recommendation.
    """
    from . import domains as domains_mod

    if str(cid or "").strip().lower() != "cleric":
        return []
    names = domains_mod.names()
    # Two that the corpus definitely carries, by name rather than by position, so a corpus
    # that grows or reorders does not change what a default cleric gets.
    wanted = [n for n in ("Healing", "Protection", "War", "Good") if n in names]
    return (wanted + names)[:domains_mod.HOW_MANY]


def starter_spells(cid: str, int_mod: int = 0, count: int | None = None) -> list[str]:
    """A legal opening spellbook for a class that needs one.

    Only wizard, sorcerer and bard declare a `spells_known` cap; everybody else prepares
    from the whole class list and is never asked. Chosen by name so the answer is stable
    across builds rather than depending on however the corpus happens to be ordered.

    Exists because a caster with an empty book is a character who cannot take their own
    turn, and refusing to build one meant every generic "build every class" test needed
    a legal book to hand.
    """
    from . import spells as spells_lib

    cap_spec = SPELLS_KNOWN.get(cid)
    if cap_spec is None:
        return []
    cap = (3 + int_mod) if cap_spec == "3 + int_mod" else int(cap_spec)
    if count is not None:
        cap = min(cap, count)
    out = []
    # A wizard's book opens with EVERY 0-level spell, and the Intelligence-scaled number
    # applies to the first-level ones only: "A wizard begins play with a spellbook
    # containing all 0-level wizard spells (except those from her prohibited school or
    # schools, if any) plus three 1st-level spells of her choice… for each point of
    # Intelligence bonus." Measured 2026-09-19: a new wizard's book held one orison and
    # five first-level spells, so most of a wizard's actual repertoire — the cantrips they
    # cast all day — was missing (item 25).
    #
    # Only the wizard. A sorcerer and a bard KNOW a small number at every level, cantrips
    # included, and the cap is the whole of it for them.
    if cid == "wizard":
        out += [sid for sid, sp in sorted(spells_lib.all_spells().items())
                if sp.lists.get(cid) == 0]
    for sid, sp in sorted(spells_lib.all_spells().items()):
        level = sp.lists.get(cid)
        if level is None or level > 1 or sid in out:
            continue
        if cid == "wizard" and level == 0:
            continue
        out.append(sid)
        if len([s for s in out if spells_lib.all_spells()[s].lists.get(cid) != 0
                or cid != "wizard"]) >= cap:
            break
    return out


def starting_purse(cls: dict) -> dict[str, int]:
    """What a new character has to spend, rolled from the class's own declaration.

    Every class states this — "1d6 x 10 gp" for Blood Bending, "5d6 x 10 gp" for a
    fighter — and nothing read it, so every character ever made began with an empty
    purse. That was invisible until the craft hub grew a market: "Buy from the market"
    handed over Steel, a Steel Crossguard and Tin to a character with nothing in their
    pockets, because the buy path never asked what anything cost.

    Rolled rather than averaged. Starting wealth is a roll in the Core Rulebook, and a
    fixed 35 gp for every fighter is a different game from one where the dice decide
    whether you can afford the breastplate.
    """
    spec = str(cls.get("starting_wealth") or "").strip().lower()
    if not spec:
        return {}
    m = re.fullmatch(r"(\d+)d(\d+)\s*(?:[x×*]\s*(\d+))?\s*([a-z]{2})?", spec)
    if not m:
        return {}
    count, faces = int(m.group(1)), int(m.group(2))
    times = int(m.group(3) or 1)
    coin = m.group(4) or "gp"
    try:
        total = dice.Dice().roll(f"{count}d{faces}").total * times
    except dice.BadDice:
        # A homebrew class wrote "300d100 x 100 gp" and the uncaught BadDice came out
        # of character creation as a 500 with the forge's picks all filled in. The
        # author's extravagance is theirs to have — it is their class and their game —
        # so implausible dice pay their expected value instead of rolling: at three
        # hundred dice the spread is noise on the mean anyway.
        total = round(count * (faces + 1) / 2) * times
    return {coin: total} if total else {}


def _feat_index() -> list[dict]:
    from collections import Counter

    everything = feats_mod.all_feats()
    seen = Counter(f.name for f in everything.values())
    return sorted(
        ({"id": fid,
          "name": f.name if seen[f.name] == 1 else f"{f.name} ({f.source})",
          "prereq": f.prerequisites_text.rstrip(".")}
         for fid, f in everything.items()),
        key=lambda row: row["name"].lower())


def _world(world_id: str):
    """The world a forge was opened from, or None: a bad id is the caller's problem
    to report, not this module's to raise over."""
    if not world_id:
        return None
    try:
        from play import library

        return library.world(world_id)
    except Exception:
        return None


def _races_for(world_id: str = "") -> dict[str, dict]:
    """What the forge offers, derived: the world's own races (the bench's edited copy
    winning), then the Core Rulebook's seven unless the table has turned them off.
    Each carries `rp`, `power` and `of` (the world it belongs to) for the cards."""
    out: dict[str, dict] = {}
    world = _world(world_id)
    if world is not None:
        for d in races_mod.for_world(world):
            out[d["id"]] = {**d, "of": getattr(world, "name", "") or world_id}
    if houserules.core_races() or world is None:
        for rid, d in races_mod.all_races().items():
            if rid not in out and str(d.get("origin", "")) in ("core", "yours"):
                out[rid] = {**races_mod.derive(d), "of": ""}
    return out


def _heritages_for(world_id: str = "") -> list[dict]:
    world = _world(world_id)
    return races_mod.heritages_from_world(world) if world is not None else []


def options(world_id: str = "") -> dict:
    """Everything the creation wizard's forms are drawn from — one payload, no guessing."""
    return {
        # The world's own races first, then the Core seven when the table allows them
        # — a forge opened from a world's page offers what that world ships.
        "races": list(_races_for(world_id).values()),
        "race_rp": houserules.race_rp(),
        # Where the character was before the first turn. Optional: a character with no
        # background is exactly what every character was before this existed.
        "backgrounds": backgrounds_mod.catalogue(),
        "background_groups": backgrounds_mod.groups(),
        "heritages": _heritages_for(world_id),
        "classes": [{"id": cid, "name": c.get("name", cid.title()),
                     # A homebrew class may declare notation rather than a number, so
                     # the label is made here rather than by pasting a "d" on the front
                     # in the template — Blood Bending's card read "d2d8".
                     "hit_die": c["hit_die"], "die_label": die_label(c["hit_die"]),
                     "bab": c["bab"],
                     "good_saves": c["good_saves"], "skill_ranks": c["skill_ranks"],
                     "class_skills": c.get("class_skills", []),
                     "summary": c.get("summary", ""),
                     "caster": bool(casting.CASTERS.get(cid) or c.get("casting")),
                     "features": classes_mod.features_at(cid, 1),
                     "paths": leveling.paths_for(cid),
                     "max_paths": leveling.max_paths(cid),
                     "unlocks_b": leveling.unlocks_at(cid, 1)}
                    for cid, c in sorted(classes_mod.all_classes().items())
                    if cid != "blood bending" or True],
        # The budget is the house rule's, not the constant's: a forge that showed 20
        # while the validator enforced 40 would refuse characters its own form said
        # were legal.
        # The table runs to whatever the ceiling allows. With no ceiling the budget is
        # the only wall left, so the payload stops at the highest score this budget
        # could actually buy — a counter offering a 40 nobody can afford is noise.
        # The domains a cleric picks from, all 153 of them, derived from the corpus
        # (`rules/domains.py`). The forge offers them on the same screen as the spells and
        # one step ahead, because a domain decides part of what can be prepared (item 27).
        "domains": _domain_menu(),
        "domains_wanted": _domains_mod().HOW_MANY,
        "point_costs": point_costs_to(_reachable_cap()),
        "point_budget": houserules.point_budget(),
        "ability_cap": houserules.ability_cap(),
        "ability_floor": ABILITY_FLOOR,
        "skills": sorted(SKILLS),
        "spells_known": SPELLS_KNOWN,
        # What the forge asks. Woman and man, and then whatever sets this table has
        # turned on — a set is offered here rather than in a second question because it
        # answers both at once, which is the whole reason the two were coupled.
        "genders": ["woman", "man"] + [p for p in houserules.pronoun_sets()
                                       if p not in houserules.DEFAULT_PRONOUNS],
        # The full feat index, so the forge can offer a picker rather than a spelling
        # test. Names alone: the bench remains the place to read a feat in full.
        # 148 names collide with a Mythic Adventures twin — two rows both reading
        # "Dodge" is a coin flip presented as a choice, so a collided name carries
        # its source and only a collided one does.
        "feats": _feat_index(),
    }


def place_racial_adjustments(payload: dict, race, abilities: dict) -> list[str]:
    """Apply a race's adjustments to `abilities` in place; return what was wrong.

    One pick per `choose` entry of the race document — a human's one "+2 any", the Race
    Builder's standard "+2 physical, +2 mental, -2 any" a world's people is drafted with.
    `bonus_ability` is the old single-pick spelling and still answers the first slot.

    Pulled out of `build` on 2026-09-20 when the forge's own choices page needed the same
    finished scores to ask "which feats does this character qualify for". A second copy of
    this loop would be a rule with two homes, and the one that drifted would be the one
    the player sees: the forge showing a cap of three where the server grants four is the
    exact disagreement `spellCap` already carries a comment about.
    """
    picks = payload.get("choices")
    if not isinstance(picks, list):
        picks = [payload.get("bonus_ability")] if payload.get("bonus_ability") else []
    picks = [str(p or "").strip().lower() for p in picks]
    problems: list[str] = []
    if not race:
        return problems
    pools = {"physical": races_mod.PHYSICAL, "mental": races_mod.MENTAL}
    for i, c in enumerate(race.get("choose") or []):
        pool = pools.get(c["from"], races_mod.ABILITIES)
        pick = picks[i] if i < len(picks) else ""
        where = "any ability" if c["from"] == "any" else f"a {c['from']} ability"
        if pick not in pool:
            problems.append(f"A {race['name'].lower()} puts {c['amount']:+d} on "
                            f"{where} — say which ability ({', '.join(pool)}).")
        elif pick in picks[:i]:
            problems.append(f"Each of a {race['name'].lower()}'s adjustments lands "
                            f"on a different ability; {pick} is named twice.")
        else:
            abilities[pick] += int(c["amount"])
    for ab, mod in (race.get("mods") or {}).items():
        abilities[ab] += mod
    return problems


def build(payload: dict) -> tuple[dict | None, list[str]]:
    """One character from one form, or every problem at once.

    All the problems rather than the first, the same choice the effect builder made and
    for the same reason: a wizard nobody finishes is a wizard built one error per submit.
    """
    problems: list[str] = []

    name = str(payload.get("name", "")).strip()
    if not name:
        problems.append("A character needs a name.")

    # Optional on purpose. Every character made before backgrounds existed has none, and
    # a forge that refused to load them would be a migration nobody asked for.
    from . import backgrounds as backgrounds_mod

    background_id = str(payload.get("background", "")).strip().lower()
    if background_id and backgrounds_mod.get(background_id) is None:
        problems.append(
            f"{background_id!r} is not a background: "
            f"{', '.join(sorted(backgrounds_mod.all_backgrounds()))}.")
        background_id = ""

    offered = _races_for(str(payload.get("world", "")).strip())
    race = offered.get(races_mod.slug(str(payload.get("race", ""))))
    if race is None:
        problems.append(f"Pick a race: {', '.join(sorted(offered))}.")

    cid = str(payload.get("class", "")).strip().lower()
    # `classes_mod.get` answers an unknown class with an empty dict rather than raising,
    # which is right for a sheet loading a retired homebrew class and wrong here: a
    # creation form naming a class that does not exist is a mistake to report.
    cls = classes_mod.get(cid) or None
    if cls is None:
        problems.append(f"Pick a class: {', '.join(sorted(classes_mod.all_classes()))}.")

    # --- abilities: point buy, then the race ---------------------------------------
    # An object, or nothing. A string here — "abilities": "x" — reached `raw.get(ab)`
    # and raised AttributeError, so a malformed create came back as HTTP 500 with a
    # traceback instead of the list of problems this function exists to return.
    raw = payload.get("abilities") or {}
    if not isinstance(raw, dict):
        problems.append("Abilities must be an object of six scores.")
        raw = {}
    abilities: dict[str, int] = {}
    spent = 0
    for ab in ("str", "dex", "con", "int", "wis", "cha"):
        try:
            score = int(raw.get(ab, 10))
        except (TypeError, ValueError):
            score = -1
        cap = houserules.ability_cap()
        top = f"{cap}" if cap else "no ceiling"
        if score < ABILITY_FLOOR or (cap and score > cap):
            problems.append(
                f"{ab}: scores run {ABILITY_FLOOR} to {top} before race, "
                f"not {raw.get(ab)!r}.")
            score = 10
        spent += point_cost(score)
        abilities[ab] = score
    budget = houserules.point_budget()
    # 0 is the Unlimited tier: no budget at all, only the ceiling stands.
    if budget and spent > budget:
        problems.append(f"That spends {spent} of {budget} points.")

    # One question, asked once, and the pronouns follow from it.
    #
    # It used to be the other way round: the forge asked for pronouns and nothing at all
    # asked what the character *was*. That defaulted to they/them with no field anywhere,
    # so every character made through that screen was saved identically regardless of who
    # they were — a roster of seven had two sets of real pronouns and both came off
    # fixture files.
    #
    # Asking for pronouns instead of gender did not fix it either, and the reason is
    # measured: a character stood in front of a mirror and was given a man's chest in a
    # paragraph written end to end in the second person — "your pectoralis major muscles"
    # — where no pronoun appears at all, so the only fact the sheet held could not apply.
    # Two uncoupled fields also let a save disagree with itself, which is exactly what
    # happened: gender said one thing and the pronouns beside it said another, and the
    # narrator had two answers to choose between.
    #
    # A woman is she/her and a man is he/him. A world of winged people or constructs
    # turns its own set on in the house rules, and that set answers both questions at
    # once — which is why picking one here is picking a gender, not a grammar.
    said_gender = " ".join(str(payload.get("gender", "")).split()).lower()
    said_pronouns = " ".join(str(payload.get("pronouns", "")).split()).lower()
    # Whether the answer came from the player or was read off an older payload. It
    # decides which of the two wins below, and getting it wrong made a stated gender of
    # "elf" quietly keep whatever pronouns happened to be sitting beside it.
    stated = bool(said_gender)
    if not said_gender:
        # A payload from before this field existed still says it, which is how the
        # fixtures and the API keep working and how the roster reads back without a
        # migration. Reading what the player already said is not guessing.
        said_gender = gender_from_pronouns(said_pronouns) or said_pronouns
    if not said_gender:
        problems.append(
            f"Say whether {name or 'this character'} is a woman or a man. The narration "
            f"describes their body and chooses their pronouns from this, and left blank "
            f"it will pick for them.")
    elif len(said_gender) > 40:
        problems.append(f"{payload.get('gender')!r} is too long to be a description.")

    # The gender wins when the player stated one — that is the coupling. When it was only
    # read off the pronouns, the pronouns are the thing that was actually said.
    said_pronouns = (pronouns_for_gender(said_gender) or
                     ("" if stated else said_pronouns))
    if said_gender and not said_pronouns:
        problems.append(
            f"Nothing follows from {said_gender!r} about which words to use for them. "
            f"Choose woman or man, or turn a pronoun set on in the house rules and pick "
            f"that — a set says both things at once.")

    # The adjustments the player places: one pick per `choose` entry of the race
    # document — a human's one "+2 any", the Race Builder's standard "+2 physical,
    # +2 mental, -2 any" a world's people is drafted with. `bonus_ability` is the old
    # single-pick spelling and still answers the first slot.
    problems.extend(place_racial_adjustments(payload, race, abilities))
    if race:
        if houserules.race_rp() and races_mod.rp(race) > houserules.race_rp():
            problems.append(
                f"{race['name']} is a {races_mod.rp(race)} RP race and this table "
                f"allows {houserules.race_rp()} (the Race Builder's "
                f"{races_mod.power(houserules.race_rp())} tier). Raise the tier on the "
                f"Rulesets bench, or trim the race on the Races bench.")

    con_mod = (abilities.get("con", 10) - 10) // 2
    int_mod = (abilities.get("int", 10) - 10) // 2

    # --- skills --------------------------------------------------------------------
    ranks_budget = 0
    if cls:
        ranks_budget = max(1, int(cls["skill_ranks"]) + int_mod) \
            + (int((race.get("budget") or {}).get("ranks", 0)) if race else 0)
    picked = [str(s).strip().lower() for s in (payload.get("skills") or [])]
    for s in picked:
        if s not in SKILLS:
            problems.append(f"{s!r} is not a skill.")
    if len(set(picked)) != len(picked):
        problems.append("One rank per skill at first level — a skill is listed twice.")
    if cls and len(picked) > ranks_budget:
        problems.append(f"That is {len(picked)} skills against "
                        f"{ranks_budget} ranks ({cls['skill_ranks']} class"
                        f"{' + Int' if int_mod else ''}"
                        f"{' + race' if race and (race.get('budget') or {}).get('ranks') else ''}).")

    # --- paths ---------------------------------------------------------------------
    # A class that declares branches must have one chosen at creation: the user's own
    # framing, "you have to choose a path or both paths". A class with none must carry
    # none, because a rogue with a Coagulator branch is a save that confuses everything
    # downstream that reads it.
    paths, path_problems = leveling.check_paths(cid, payload.get("paths"))
    problems.extend(path_problems)

    # --- feats ---------------------------------------------------------------------
    feat_budget = 1 + (int((race.get("budget") or {}).get("feats", 0)) if race else 0) \
        + (1 if cid == "fighter" else 0)
    # A feat is a string id, or {"id": ..., "target": ...} for one that binds to a
    # chosen weapon — Weapon Focus, Weapon Specialization, a Weapon Proficiency. The
    # forge used to write every one bare, and a bare Weapon Focus was +1 with every
    # weapon; under the documents it would be +1 with none, so the target is asked
    # for here, with the fix named.
    raw_feats = payload.get("feats") or []
    feat_ids = [str(f.get("id", "") if isinstance(f, dict) else f).strip().lower()
                for f in raw_feats]
    feats_named: list[str] = []
    for f, fid in zip(raw_feats, feat_ids):
        try:
            feat = feats_mod.get(fid)
        except LookupError:
            problems.append(f"No feat called {fid!r}.")
            continue
        target = str(f.get("target", "") if isinstance(f, dict) else "").strip().lower()
        doc = feats_mod.documents().get(feat.id)
        if feats_mod.needs_target(doc) and not target:
            problems.append(
                f"{feat.name} needs a weapon: send {{\"id\": \"{feat.id}\", "
                f"\"target\": \"<weapon>\"}}.")
            continue
        feats_named.append(feat.name.lower() + (f" ({target})" if target else ""))
    if len(feat_ids) > feat_budget:
        problems.append(f"That is {len(feat_ids)} feats against {feat_budget} "
                        f"(one, plus one for a human, plus one for a fighter).")

    # --- domains ----------------------------------------------------------------------
    # A cleric picks two, on the same screen that prepares her spells and one step ahead of
    # it, because a domain decides part of what she can prepare. No deity step and no
    # alignment gate: the ruling, 2026-09-19, was "grab whatever the belief system of the
    # world is and let that be enough. dont worry about the gods or the alignment" — and
    # the world's own Metaphysics fact says why that is enough.
    from . import domains as domains_mod

    picked_domains = [" ".join(str(d).split()).title()
                      for d in (payload.get("domains") or []) if str(d).strip()]
    problems += domains_mod.problems(picked_domains, cid)

    # --- spells known ----------------------------------------------------------------
    spellbook = [str(s).strip().lower() for s in (payload.get("spellbook") or [])]
    cap_spec = SPELLS_KNOWN.get(cid)
    # A wizard's cantrips are a GRANT, not a choice — "a wizard begins play with a
    # spellbook containing all 0-level wizard spells" — so they are added here rather
    # than asked for. The forge used to demand the whole book as typed ids, which meant
    # a player who typed their three first-level spells and pressed the button got a
    # wizard with no cantrips at all: a caster who cannot take a turn without spending a
    # slot. Granted after the player's list and deduplicated, so a book that already
    # names them is unchanged and the first-level count below is unaffected.
    if cid == "wizard":
        from . import spells as _spells_lib

        cantrips = [s.id for s in _spells_lib.all_spells().values()
                    if isinstance(s.lists, dict) and s.lists.get(cid) == 0]
        spellbook = list(dict.fromkeys(spellbook + sorted(cantrips)))
    if spellbook and cap_spec is None:
        problems.append(f"A {cid or 'non-caster'} picks no spells at creation.")
    elif cap_spec is not None:
        cap = (3 + int_mod) if cap_spec == "3 + int_mod" else int(cap_spec)
        # A wizard's cap counts the FIRST-level spells only. The book grants "all 0-level
        # wizard spells plus three 1st-level spells of her choice… for each point of
        # Intelligence bonus", so counting the cantrips against it refused a legal opening
        # book of 35 orisons and six spells as "38 spells against 4 known" (item 25).
        # Everybody else's cap is the whole of what they know, cantrips included.
        counted = spellbook
        if cid == "wizard":
            from . import spells as spells_lib

            every = spells_lib.all_spells()
            counted = [sid for sid in spellbook
                       if (every[sid].lists.get(cid) if sid in every else 1) != 0]
        if len(counted) > cap:
            problems.append(f"That is {len(counted)} spells against {cap} known.")
        # And at least one. A wizard with an empty book is a character who cannot take
        # their own turn: found on the roster as Thessaly Corr, a Wizard 1 with 66 turns
        # played, three level-0 and two level-1 slots, save DCs of 13 and 14 — and no
        # spells at all to put in them. Classes that prepare from the whole class list
        # rather than a book declare no cap and are not asked.
        # `counted`, not the whole book: since a wizard's cantrips are granted above, the
        # book is never empty for one, and asking "did you choose anything" has to mean
        # the spells they actually chose. Without this the refusal stopped firing and a
        # wizard could walk out having picked no first-level spell at all.
        if cap and not counted:
            problems.append(
                f"A {cid} begins knowing spells: choose up to {cap}.")
        from . import spells as spells_lib

        for sid in spellbook:
            try:
                sp = spells_lib.get(sid)
            except KeyError:
                problems.append(f"No spell called {sid!r}.")
                continue
            lvl = sp.lists.get(cid)
            if lvl is None or lvl > 1:
                problems.append(f"{sp.name} is not a level 0-1 {cid} spell.")

    if problems:
        return None, problems

    # --- assemble, exactly the pregen shape ------------------------------------------
    # A class with no authored kit starts with its hands. The old fallback was a
    # dagger, and a Blood Bending player met it mid-fight: the panel opened their
    # first attack with a knife they never chose, never saw in their inventory, and
    # rightly said they were not carrying. Every creature has an unarmed strike; no
    # homebrew class has a dagger until somebody writes one down.
    # Their hands, and whatever their body came with. Every creature has an unarmed
    # strike; a race built with claws or a bite carries them by name. The old fallback for
    # a class with no kit was a dagger, and a Blood Bending player met it mid-fight: the
    # panel opened their first attack with a knife they never chose, never saw in their
    # inventory, and rightly said they were not carrying. That fallback is now the rule.
    own = [str(w.get("key")) for w in (race.get("weapons") or []) if w.get("key")]
    weapons = own + ["unarmed"] if own else ["unarmed"]
    outfit = OUTFITS.get(cid, DEFAULT_OUTFIT)
    hp = max(1, max_hit_die(cls["hit_die"]) + con_mod)  # max die at 1st, the kind rule
    sheet = {
        "name": name, "kind": "pc", "class": cid, "level": 1,
        "race": race["id"],
        # The people of the world this body belongs to, when it is a world's race.
        "world_people_id": race.get("people_id") or None,
        "heritage": str(payload.get("heritage", "")).strip(),
        # Where they were before the first turn. Stored as the id alone: the modifiers,
        # tags and traits are read live off the document the way a race's are, so a
        # background edited on the bench changes every character who has it and removing
        # one removes its arithmetic.
        "background": background_id,
        "pronouns": said_pronouns, "gender": said_gender,
        "size": race["size"], "speed": race["speed"],
        "abilities": abilities,
        "ranks": {s: 1 for s in picked},
        "feats": feats_named,
        "weapons": weapons,
        "equipped": weapons[0],
        # Unarmoured and unshielded out of the forge. Both are bought at the outfitter now,
        # out of a purse that was always large enough for them.
        "armour": "none",
        "shield": "none",
        # Worn *and* carried, because those are two different questions and the sheet
        # asks both: the `body` slot is what the equipment page draws on the figure,
        # and `goods` is the answer to "what am I carrying".
        "paths": paths,
        "goods": {outfit: 1},
        "slots": {"body": [outfit]},
        "purse": starting_purse(cls),
        "hp": hp, "hp_max": hp,
        "notes": str(payload.get("notes", "")).strip(),
    }
    if spellbook:
        sheet["spellbook"] = spellbook
    if picked_domains:
        sheet["domains"] = picked_domains

    # The proof of the whole exercise: the dict must load as an Actor before anything is
    # saved, so a creation bug is a refusal here rather than a corrupt file on disk.
    from_dict(sheet)

    # Feat legality is judged *after* the sheet exists, because prerequisites read the
    # finished scores. Two verdicts, treated differently. A prerequisite that was READ
    # and is NOT MET — Great Cleave's Cleave, Power Attack and base attack +4 on a
    # first-level sheet — is a refusal with the fix named, the same law every other
    # document here answers to. A prerequisite that could not be read (prose the parser
    # does not know) is a warning: refusing those would refuse half the book.
    #
    # Reported 2026-09-18 with a screenshot — "Toughness, great cleave" on a level-one
    # sheet: "I am allowed to choose feats I don't meet the prerequisites for." The
    # first version of this block warned for both, and read a `why` key `meets` never
    # returned, so the warning it did raise always said "short of a prerequisite" and
    # named nothing.
    warnings = []
    actor = from_dict(sheet)
    for fid in feat_ids:
        feat = feats_mod.get(fid)
        verdict = feats_mod.meets(actor, feat)
        if verdict.get("unmet"):
            problems.append(
                f"{feat.name} requires {', '.join(verdict['unmet'])}; this character "
                f"does not meet that. Pick another feat, or build toward it.")
        elif verdict.get("unknown"):
            warnings.append(
                f"{feat.name}: could not check {', '.join(verdict['unknown'])} — "
                f"make sure the character qualifies.")
    if problems:
        return {}, problems
    return {"sheet": sheet, "warnings": warnings}, []


# --- what this character can actually take -------------------------------------------------

def _provisional(payload: dict):
    """An Actor built from a half-finished forge draft, for asking what it qualifies for.

    Prerequisites read FINISHED scores — Power Attack wants Strength 13 after the race is
    applied — so the only honest way to answer "can they take this" is to build the body
    and ask it. `build` already does exactly that for feat legality once the sheet exists;
    this is the same move one step earlier, while the player is still choosing.

    Returns None when the draft has not said enough yet: the page then says so, rather
    than offering a list that will change under the player's hands.
    """
    race = _races_for(str(payload.get("world", "") or "")).get(
        str(payload.get("race", "")).strip().lower())
    cid = str(payload.get("class", "")).strip().lower()
    cls = classes_mod.get(cid)
    if not race or not cls:
        return None
    raw = payload.get("abilities") or {}
    abilities = {}
    for ab in ("str", "dex", "con", "int", "wis", "cha"):
        try:
            abilities[ab] = int(raw.get(ab, 10))
        except (TypeError, ValueError):
            abilities[ab] = 10
    # The same adjustment `build` applies, through the same function, so the page and the
    # server can never disagree about the scores a prerequisite is read against.
    place_racial_adjustments(payload, race, abilities)
    picked = [str(s).strip().lower() for s in (payload.get("skills") or [])]
    try:
        return from_dict({
            "name": str(payload.get("name") or "Someone"), "kind": "pc",
            "class": cid, "level": 1, "race": race["id"],
            "size": race["size"], "speed": race["speed"],
            "abilities": abilities,
            "ranks": {s: 1 for s in picked if s in SKILLS},
            "feats": [str(f) for f in (payload.get("feats") or [])],
            "background": str(payload.get("background", "")).strip().lower(),
            "hp": 1, "hp_max": 1,
        })
    except Exception:      # noqa: BLE001 — a draft too broken to embody offers no choices
        return None


def feat_choices(payload: dict) -> dict:
    """Every feat this draft could take, and why the rest are shut.

    The forge offered a search box over all 1,474 by name, which is the wrong question
    asked of the wrong person — reported 2026-09-20: "People do not usually know the feats
    without looking through them so the process needs guiding." A first-level fighter
    qualifies for 145 of them, measured, which is a list somebody can actually read.

    Both halves come back. `open` is what they qualify for; `shut` is the rest with the
    missing prerequisite named, because a list showing only what you can have today hides
    the ladder you are climbing — and Pathbuilder's answer, "show what you qualify for",
    works precisely because the rest stays visible behind it.
    """
    actor = _provisional(payload)
    if actor is None:
        return {"ready": False, "open": [], "shut": []}
    open_: list[dict] = []
    shut: list[dict] = []
    for feat in feats_mod.all_feats().values():
        verdict = feats_mod.meets(actor, feat)
        types = [str(t) for t in (feat.types or [])]
        # 148 feats share a display name with their mythic namesake — `feats.by_name`
        # already has to prefer the ordinary one for exactly this reason. Listed side by
        # side with the shut ones showing, that put two rows called "Acrobatic" on the
        # screen, which reads as a glitch even though the second says what it needs.
        name = (f"{feat.name} (mythic)" if "mythic" in {t.lower() for t in types}
                else feat.name)
        row = {"id": feat.id, "name": name, "types": types,
               "text": str(feat.benefit or feat.description or "")[:400]}
        # Mythic feats are never open, whatever their prerequisites say. `feats.NOT_YET`
        # already treats a `mythic_tier` condition as uncheckable, so 155 of the 158 are
        # shut for the right reason — but three (Extra Mythic Power, Mythic Paragon,
        # Potent Surge) state no prerequisite at all and were being offered to a
        # first-level character in a game that has no mythic tiers to spend. Measured
        # 2026-09-20 while building this page.
        if "mythic" in {t.lower() for t in (feat.types or [])}:
            verdict = {"ok": False, "unmet": ["a mythic tier, which this game has none of"],
                       "unknown": []}
        if verdict["ok"]:
            open_.append(row)
        else:
            # `unmet` was read and failed; `unknown` this app could not parse. They are
            # different answers and the page says which — an unreadable prerequisite is
            # the app's shortcoming, not the character's, and `feats.meets` is careful
            # to keep them apart for exactly that reason.
            row["unmet"] = [str(x) for x in verdict["unmet"]]
            row["unknown"] = [str(x) for x in verdict["unknown"]]
            shut.append(row)
    open_.sort(key=lambda r: r["name"])
    shut.sort(key=lambda r: r["name"])
    return {"ready": True, "open": open_, "shut": shut}


def spell_choices(payload: dict) -> dict:
    """What this draft's caster is GRANTED, what they CHOOSE, and out of which list.

    Three things the forge never said, and each is a standing complaint on D&D Beyond's
    own builder forums: which spells arrive granted rather than chosen, that only the
    levels you can actually cast should be offered, and what your slots are while you
    choose. A wizard here was shown "level 0-1 wizard spells 0 / 28" and a box asking for
    comma-separated ids.
    """
    from . import spells as spells_lib

    actor = _provisional(payload)
    cid = str(payload.get("class", "")).strip().lower()
    cap_spec = SPELLS_KNOWN.get(cid)
    out: dict = {"ready": actor is not None, "casts": cap_spec is not None,
                 "prepares": False,
                 "granted": [], "choose": [], "cap": 0, "chosen": 0, "slots": {},
                 "choose_level": 1}
    if actor is None:
        return out
    # The slots this character will have on day one, from the same function the play
    # table reads, so the number here is the number there. Answered for EVERY caster,
    # not only the ones with a book to fill: a cleric chooses no spells at the forge and
    # still wants to know what she will be able to cast, which is half of what was asked
    # for — "filling spell slots for the first session should be easy and intuitive".
    try:
        out["slots"] = {str(k): int(v) for k, v in casting.slots_for(actor).items()}
    except Exception:      # noqa: BLE001 — a draft that cannot answer says nothing
        out["slots"] = {}
    if cap_spec is None:
        # Casts, but prepares from the whole class list rather than from a book of known
        # spells — cleric, druid, paladin. Nothing to choose here; the choosing happens
        # each morning at the table, and the page says so rather than staying silent.
        out["prepares"] = bool(out["slots"])
        return out
    int_mod = (int(actor.abilities.get("int", 10)) - 10) // 2
    out["cap"] = (3 + int_mod) if cap_spec == "3 + int_mod" else int(cap_spec)

    def _row(sp) -> dict:
        return {"id": sp.id, "name": sp.name, "level": sp.lists.get(cid),
                "school": str(sp.school or ""),
                "text": str(sp.description or "")[:300]}

    mine = [s for s in spells_lib.all_spells().values()
            if isinstance(s.lists, dict) and s.lists.get(cid) is not None]
    if cid == "wizard":
        # "A wizard begins play with a spellbook containing all 0-level wizard spells …
        # plus three 1st-level spells of her choice … for each point of Intelligence
        # bonus." The cantrips are granted and the cap is the first-level allowance
        # alone — which is what `build` already counts and the old panel did not say.
        out["granted"] = sorted((_row(s) for s in mine if s.lists.get(cid) == 0),
                                key=lambda r: r["name"])
        out["choose"] = sorted((_row(s) for s in mine if s.lists.get(cid) == 1),
                               key=lambda r: r["name"])
    else:
        # Sorcerer and bard know cantrips and first-level spells alike, and both count
        # against the one cap.
        out["choose"] = sorted((_row(s) for s in mine if s.lists.get(cid) in (0, 1)),
                               key=lambda r: (r["level"], r["name"]))
    picked = [str(s).strip().lower() for s in (payload.get("spellbook") or [])]
    granted = {r["id"] for r in out["granted"]}
    out["chosen"] = len([p for p in picked if p not in granted])
    return out
