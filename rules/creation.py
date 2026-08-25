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

from . import casting, classes as classes_mod, dice, feats as feats_mod, houserules
from . import leveling
from .sheet import from_dict
from .tables import ARMOUR, SKILLS, WEAPONS

# The Core Rulebook's seven. `mods` is what the race does to the scores; `any` means the
# +2 lands where the player says (human, half-elf, half-orc), which is a required choice
# rather than a default — silently picking for them is choosing their character.
RACES: dict[str, dict] = {
    "human":    {"name": "Human", "size": "medium", "speed": 30, "mods": {},
                 "any": 2, "bonus_feat": True, "bonus_ranks": 1,
                 "traits": ["+2 to one ability score", "bonus feat",
                            "+1 skill rank per level"]},
    "dwarf":    {"name": "Dwarf", "size": "medium", "speed": 20,
                 "mods": {"con": 2, "wis": 2, "cha": -2},
                 "traits": ["darkvision 60 ft", "+4 CMD vs bull rush and trip",
                            "+2 saves vs poison, spells and spell-like abilities"]},
    "elf":      {"name": "Elf", "size": "medium", "speed": 30,
                 "mods": {"dex": 2, "int": 2, "con": -2},
                 "traits": ["low-light vision", "immune to magic sleep",
                            "+2 saves vs enchantment", "+2 Perception"]},
    "gnome":    {"name": "Gnome", "size": "small", "speed": 20,
                 "mods": {"con": 2, "cha": 2, "str": -2},
                 "traits": ["low-light vision", "small: +1 AC, +1 attack, +4 Stealth",
                            "+2 saves vs illusions"]},
    "half-elf": {"name": "Half-Elf", "size": "medium", "speed": 30, "mods": {},
                 "any": 2,
                 "traits": ["low-light vision", "immune to magic sleep",
                            "Skill Focus at 1st level", "+2 Perception"]},
    "half-orc": {"name": "Half-Orc", "size": "medium", "speed": 30, "mods": {},
                 "any": 2,
                 "traits": ["darkvision 60 ft", "ferocity: keep fighting below 0",
                            "+2 Intimidate"]},
    "halfling": {"name": "Halfling", "size": "small", "speed": 20,
                 "mods": {"dex": 2, "cha": 2, "str": -2},
                 "traits": ["small: +1 AC, +1 attack, +4 Stealth", "+2 all saves",
                            "+2 Perception"]},
}

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
    purse = houserules.point_budget() - 5 * POINT_COSTS[ABILITY_FLOOR]
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

# What a first-level character of each class walks out the door holding.
#
# Everything here is drawn from the *small* core tables the sheet validates against —
# eleven weapons, eight armours, four shields — because `equipped` is refused outside
# them. That costs some book flavour: the barbarian's greataxe becomes a greatsword, the
# cleric's mace a quarterstaff, the ranger's longbow a shortbow, "scale mail" its nearest
# listed armour. The nearest-legal substitution lives here, in one place, and the test
# walks every kit through `from_dict` so a kit naming unknown gear is a failing test
# rather than a corrupt character on disk.
KITS: dict[str, dict] = {
    "barbarian": {"weapons": ["greatsword", "dagger"], "armour": "studded leather"},
    "bard":      {"weapons": ["rapier", "dagger"], "armour": "leather"},
    "cleric":    {"weapons": ["quarterstaff", "light crossbow"], "armour": "chain shirt",
                  "shield": "heavy shield"},
    "druid":     {"weapons": ["quarterstaff", "club"], "armour": "leather",
                  "shield": "heavy shield"},
    "fighter":   {"weapons": ["longsword", "dagger", "light crossbow"],
                  "armour": "chain shirt", "shield": "heavy shield"},
    "monk":      {"weapons": ["quarterstaff", "unarmed"], "armour": "none"},
    "paladin":   {"weapons": ["longsword", "dagger"], "armour": "chain shirt",
                  "shield": "heavy shield"},
    "ranger":    {"weapons": ["longsword", "shortbow", "dagger"], "armour": "leather"},
    "rogue":     {"weapons": ["rapier", "dagger", "shortbow"], "armour": "leather"},
    "sorcerer":  {"weapons": ["quarterstaff", "light crossbow", "dagger"],
                  "armour": "none"},
    "wizard":    {"weapons": ["quarterstaff", "light crossbow", "dagger"],
                  "armour": "none"},
}

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
    total = dice.Dice().roll(f"{count}d{faces}").total * times
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


def options() -> dict:
    """Everything the creation wizard's forms are drawn from — one payload, no guessing."""
    return {
        "races": [{"id": rid, **{k: v for k, v in r.items() if k != "bonus_feat"}}
                  for rid, r in RACES.items()],
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
        "point_costs": point_costs_to(_reachable_cap()),
        "point_budget": houserules.point_budget(),
        "ability_cap": houserules.ability_cap(),
        "ability_floor": ABILITY_FLOOR,
        "skills": sorted(SKILLS),
        "spells_known": SPELLS_KNOWN,
        # The full feat index, so the forge can offer a picker rather than a spelling
        # test. Names alone: the bench remains the place to read a feat in full.
        # 148 names collide with a Mythic Adventures twin — two rows both reading
        # "Dodge" is a coin flip presented as a choice, so a collided name carries
        # its source and only a collided one does.
        "feats": _feat_index(),
    }


def build(payload: dict) -> tuple[dict | None, list[str]]:
    """One character from one form, or every problem at once.

    All the problems rather than the first, the same choice the effect builder made and
    for the same reason: a wizard nobody finishes is a wizard built one error per submit.
    """
    problems: list[str] = []

    name = str(payload.get("name", "")).strip()
    if not name:
        problems.append("A character needs a name.")

    race = RACES.get(str(payload.get("race", "")).strip().lower())
    if race is None:
        problems.append(f"Pick a race: {', '.join(RACES)}.")

    cid = str(payload.get("class", "")).strip().lower()
    # `classes_mod.get` answers an unknown class with an empty dict rather than raising,
    # which is right for a sheet loading a retired homebrew class and wrong here: a
    # creation form naming a class that does not exist is a mistake to report.
    cls = classes_mod.get(cid) or None
    if cls is None:
        problems.append(f"Pick a class: {', '.join(sorted(classes_mod.all_classes()))}.")

    # --- abilities: point buy, then the race ---------------------------------------
    raw = payload.get("abilities") or {}
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
    if spent > budget:
        problems.append(f"That spends {spent} of {budget} points.")

    bonus_ab = str(payload.get("bonus_ability", "")).strip().lower()
    if race:
        if race.get("any"):
            if bonus_ab not in abilities:
                problems.append(f"A {race['name'].lower()} puts +2 where they choose — "
                                f"say which ability.")
            else:
                abilities[bonus_ab] += race["any"]
        for ab, mod in race.get("mods", {}).items():
            abilities[ab] += mod

    con_mod = (abilities.get("con", 10) - 10) // 2
    int_mod = (abilities.get("int", 10) - 10) // 2

    # --- skills --------------------------------------------------------------------
    ranks_budget = 0
    if cls:
        ranks_budget = max(1, int(cls["skill_ranks"]) + int_mod) \
            + (race.get("bonus_ranks", 0) if race else 0)
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
                        f"{' + human' if race and race.get('bonus_ranks') else ''}).")

    # --- paths ---------------------------------------------------------------------
    # A class that declares branches must have one chosen at creation: the user's own
    # framing, "you have to choose a path or both paths". A class with none must carry
    # none, because a rogue with a Coagulator branch is a save that confuses everything
    # downstream that reads it.
    paths, path_problems = leveling.check_paths(cid, payload.get("paths"))
    problems.extend(path_problems)

    # --- feats ---------------------------------------------------------------------
    feat_budget = 1 + (1 if race and race.get("bonus_feat") else 0) \
        + (1 if cid == "fighter" else 0)
    feat_ids = [str(f).strip().lower() for f in (payload.get("feats") or [])]
    feats_named: list[str] = []
    for fid in feat_ids:
        try:
            feats_named.append(feats_mod.get(fid).name.lower())
        except LookupError:
            problems.append(f"No feat called {fid!r}.")
    if len(feat_ids) > feat_budget:
        problems.append(f"That is {len(feat_ids)} feats against {feat_budget} "
                        f"(one, plus one for a human, plus one for a fighter).")

    # --- spells known ----------------------------------------------------------------
    spellbook = [str(s).strip().lower() for s in (payload.get("spellbook") or [])]
    cap_spec = SPELLS_KNOWN.get(cid)
    if spellbook and cap_spec is None:
        problems.append(f"A {cid or 'non-caster'} picks no spells at creation.")
    elif cap_spec is not None:
        cap = (3 + int_mod) if cap_spec == "3 + int_mod" else int(cap_spec)
        if len(spellbook) > cap:
            problems.append(f"That is {len(spellbook)} spells against {cap} known.")
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
    kit = KITS.get(cid, {"weapons": ["dagger"], "armour": "none"})
    outfit = OUTFITS.get(cid, DEFAULT_OUTFIT)
    hp = max(1, max_hit_die(cls["hit_die"]) + con_mod)  # max die at 1st, the kind rule
    sheet = {
        "name": name, "kind": "pc", "class": cid, "level": 1,
        "race": next(k for k, v in RACES.items() if v is race),
        "heritage": str(payload.get("heritage", "")).strip(),
        "pronouns": str(payload.get("pronouns", "")).strip() or "they/them",
        "size": race["size"], "speed": race["speed"],
        "abilities": abilities,
        "ranks": {s: 1 for s in picked},
        "feats": feats_named,
        "weapons": list(kit["weapons"]),
        "equipped": kit["weapons"][0],
        "armour": kit.get("armour", "none"),
        "shield": kit.get("shield", "none"),
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

    # The proof of the whole exercise: the dict must load as an Actor before anything is
    # saved, so a creation bug is a refusal here rather than a corrupt file on disk.
    from_dict(sheet)

    # Feat legality is reported *after* the sheet exists, because prerequisites read the
    # finished scores. Advisory rather than fatal: `meets` returns "cannot check" for
    # prose prerequisites, and refusing those would refuse half the book.
    warnings = []
    actor = from_dict(sheet)
    for fid in feat_ids:
        verdict = feats_mod.meets(actor, feats_mod.get(fid))
        if verdict.get("ok") is False:
            warnings.append(f"{feats_mod.get(fid).name}: {verdict.get('why', 'short of a prerequisite')}")
    return {"sheet": sheet, "warnings": warnings}, []
