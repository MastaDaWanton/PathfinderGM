"""People and creatures of our own, built from the rules rather than copied from a page.

The owner's direction, 2026-10-28: ship the rulebook line only (docs/bestiary-licensing.md,
option D) and make the people the adventures used to supply ourselves — a world-agnostic
role name, our own description, and numbers the rules compute. This module is the last of
those: a build document says what a person IS (race, class, level, how their scores fall,
which skills and feats, what they carry) and every number on the sheet comes out of the
engine that computes a player's — BAB, saves and hit dice off the class document, skills
off ranks and the class list, AC and attacks off what is worn and wielded. No model and no
author writes a total.

The method is the Core Rulebook's own, Chapter 14, "Creating NPCs" (pp. 450-454), read from
the book 2026-10-28:

  Step 2  ability scores: the basic array 13, 12, 11, 10, 9, 8 or the heroic 15, 14, 13,
          12, 10, 8 ("If the NPC possesses levels in a PC class, it is considered a heroic
          NPC"), or Table 14-6's preset for the role; then the race; then "for every four
          levels the NPC has attained, increase one of its scores by 1".
  Step 3  skills: Table 14-8's selections (the class's ranks + Int modifier), "the NPC
          receives a number of ranks in each skill equal to his level".
  Step 4  feats: "one feat for every two levels beyond 1st", and humans one more.
  Step 7  "Determine the character's total hit points by assuming the average result."

Then the favoured class bonus, the owner's ruling of 2026-10-30: a built person takes the
hit point for every level in their favoured class (CRB Chapter 3, "Favored Class": "+1 hit point
or +1 skill rank" each level), as Paizo's own NPC Codex people do. Every build has one class
and it is the favoured one (James Jacobs and Sean K Reynolds on the Paizo rules forum: "NPCs
do get favored class bonuses", and the first class taken is assumed favoured). Read off the
NPC Codex's NPC-class blocks (legacy.aonprd.com/npcCodex/npc/, 2026-10-30), hit points less
average dice, Constitution and Toughness: warriors take it in hit points 9 of 10 (the
brigand's 2d10+4 at Con 12, the guard's 3d10+6 at Con 10 with Toughness), adepts 5 of 10,
aristocrats 2, experts 2 and commoners 1 — the rest put it in a skill rank. The ruling takes
the hit point for every build; that split is recorded here for the day it is revisited.

And its CR from Chapter 12, "Adding NPCs" (p. 398): class levels with no racial Hit Dice are
"a CR equal to its class levels –1"; NPC class levels only, "–2"; below 1 it steps down
1/2, 1/3, 1/4, 1/6, 1/8.

A build is refused, with the fix named, rather than half-built: a person whose numbers do
not follow from the rules is the thing this module exists to stop shipping.
"""
from __future__ import annotations

ABILITIES = ("str", "dex", "con", "int", "wis", "cha")

# What a built person's `source` reads, and what `npcs.source_rank` ranks with the NPC
# Codex: the most generic source there is, a role and nothing else.
SOURCE = "Pathfinder GM builds (Core Rulebook, Chapter 14)"

# Step 2's two arrays, assigned in an order the build gives.
ARRAYS = {"basic": (13, 12, 11, 10, 9, 8), "heroic": (15, 14, 13, 12, 10, 8)}

# Table 14-6: NPC Ability Scores (CRB p. 451), by role, basic and heroic, in ABILITIES
# order. "* If the arcane caster's spellcasting relies on Charisma, exchange these scores
# with one another" (Int and Cha) — the build says `"swap": ["int", "cha"]`.
PRESETS = {
    ("melee", "basic"): (13, 11, 12, 9, 10, 8), ("melee", "heroic"): (15, 13, 14, 10, 12, 8),
    ("ranged", "basic"): (11, 13, 12, 10, 9, 8), ("ranged", "heroic"): (13, 15, 14, 12, 10, 8),
    ("divine", "basic"): (10, 8, 12, 9, 13, 11), ("divine", "heroic"): (12, 8, 14, 10, 15, 13),
    ("arcane", "basic"): (8, 12, 10, 13, 9, 11), ("arcane", "heroic"): (8, 14, 12, 15, 10, 13),
    ("skill", "basic"): (10, 12, 11, 13, 8, 9), ("skill", "heroic"): (12, 14, 13, 15, 8, 10),
}

# The CR step-down below 1 (CRB p. 398).
_BELOW_ONE = ("1/2", "1/3", "1/4", "1/6", "1/8")
_CR_VALUE = {"1/2": 0.5, "1/3": 1 / 3, "1/4": 0.25, "1/6": 1 / 6, "1/8": 0.125}


def challenge(level: int, npc_class: bool) -> str:
    """The CR of a creature whose Hit Dice are all class levels (CRB p. 398)."""
    raw = int(level) - (2 if npc_class else 1)
    if raw >= 1:
        return str(raw)
    return _BELOW_ONE[min(len(_BELOW_ONE) - 1, 1 - raw - 1)]


def cr_value(cr: str) -> float:
    return _CR_VALUE.get(cr, float(cr) if str(cr).isdigit() else 0.0)


def average_hp(hit_die: int, level: int) -> int:
    """Step 7's "average result", rounded down over the whole: a d10 is 5.5 a level."""
    return int(level) * (int(hit_die) + 1) // 2


def favoured_hp(level: int) -> int:
    """The favoured class bonus taken in hit points: one a level (CRB Chapter 3), the NPC
    Codex's way (module docstring). Measured 2026-10-30, before it: a warrior 3 guard built
    here had 3 hit points fewer than the Codex's own guard of the same scores and feats."""
    return int(level)


def _scores(doc: dict, heroic: bool, problems: list[str]) -> dict[str, int]:
    spec = doc.get("abilities") or {}
    if isinstance(spec, dict) and set(spec) >= set(ABILITIES):
        # Stated whole — for a build that needs scores no array gives (Step 2: "Some NPCs
        # might not fit into one of these categories and should have custom ability
        # scores"). Still before the race and the level increases, as the step reads.
        return {ab: int(spec[ab]) for ab in ABILITIES}
    if not isinstance(spec, dict):
        problems.append("abilities: {\"preset\": \"melee\"}, {\"array\": \"basic\", "
                        "\"order\": [\"str\", ...]} or all six scores.")
        return {ab: 10 for ab in ABILITIES}
    kind = str(spec.get("kind") or ("heroic" if heroic else "basic"))
    if spec.get("preset"):
        row = PRESETS.get((str(spec["preset"]), kind))
        if row is None:
            problems.append(f"abilities.preset: {spec['preset']!r} — one of melee, ranged, "
                            f"divine, arcane, skill (CRB Table 14-6).")
            return {ab: 10 for ab in ABILITIES}
        scores = dict(zip(ABILITIES, row))
    else:
        order = [str(a) for a in spec.get("order") or ()]
        array = ARRAYS.get(str(spec.get("array") or kind))
        if array is None or sorted(order) != sorted(ABILITIES):
            problems.append("abilities.order: all six abilities once each, highest score "
                            "first, for the basic or heroic array.")
            return {ab: 10 for ab in ABILITIES}
        scores = dict(zip(order, array))
    swap = spec.get("swap")
    if swap:
        a, b = swap
        scores[a], scores[b] = scores[b], scores[a]
    return scores


def build(doc: dict) -> tuple[dict | None, list[str]]:
    """A build document as a sheet `rules.sheet.from_dict` takes, or (None, problems).

    `doc` fields: `id`, `name`, `race`, `class`, `level`, `abilities` (above),
    `racial_choices` (the race's free picks, a human's "+2 any"), `increases` (one ability
    per four levels), `skills` (Table 14-8 selections), `feats`, `class_choices`,
    `weapons`, `equipped`, `armour`, `shield`, and anything the sheet carries as is
    (`tags`, `kit`, `notes`, `appearance`)."""
    from . import classes as classes_mod
    from . import creation
    from . import races as races_mod

    problems: list[str] = []
    bid = str(doc.get("id") or "").strip().lower()
    if not bid:
        problems.append("id: a lower-case id, permanent — saves store it.")
    cid = str(doc.get("class") or "").strip().lower()
    cls = classes_mod.get(cid)
    if not cls:
        problems.append(f"class: {cid!r} is no class — an NPC class (adept, aristocrat, "
                        f"commoner, expert, warrior) or a PC class.")
        return None, problems
    npc_class = cid in classes_mod.npc_classes()
    level = int(doc.get("level") or 1)
    if not 1 <= level <= 20:
        problems.append("level: 1 to 20.")
    race_id = str(doc.get("race") or "human").strip().lower()
    race = races_mod.get(race_id)
    if race is None:
        problems.append(f"race: {race_id!r} is no race.")
        return None, problems

    scores = _scores(doc, heroic=not npc_class, problems=problems)
    problems += creation.place_racial_adjustments(
        {"choices": list(doc.get("racial_choices") or [])}, race, scores)
    increases = [str(a) for a in doc.get("increases") or ()]
    if len(increases) != level // 4 or any(a not in ABILITIES for a in increases):
        problems.append(f"increases: one ability for every four levels — {level // 4} at "
                        f"level {level} (CRB Step 2).")
    for ab in increases:
        if ab in scores:
            scores[ab] += 1

    selections = _selections(cls, scores, race_id)
    skills = [str(s).strip().lower() for s in doc.get("skills") or ()]
    from .tables import SKILLS

    unknown = [s for s in skills if s not in SKILLS and not s.startswith(("craft",
                                                                         "profession",
                                                                         "perform"))]
    if unknown:
        problems.append(f"skills: no such skill {', '.join(unknown)}.")
    if len(skills) > selections:
        problems.append(f"skills: {len(skills)} selections, and a {cid} {level} with Int "
                        f"{scores['int']} has {selections} (CRB Table 14-8).")

    feats = [str(f) for f in doc.get("feats") or ()]
    owed = feats_owed(doc)
    if len(feats) != owed:
        problems.append(f"feats: {len(feats)} taken, {owed} owed — one at 1st and every odd "
                        f"level after{', one for being human' if race_id == 'human' else ''} "
                        f"(CRB Step 4).")

    if problems:
        return None, problems

    cr = challenge(level, npc_class)
    sheet = {
        "id": bid, "name": str(doc.get("name") or bid.replace("-", " ")),
        "kind": "npc", "race": race_id, "class": cid, "level": level,
        "abilities": scores, "feats": feats,
        "ranks": {s: level for s in skills},
        "class_choices": dict(doc.get("class_choices") or {}),
        "weapons": list(doc.get("weapons") or []),
        "equipped": doc.get("equipped") or None,
        "armour": str(doc.get("armour") or "none"),
        "shield": str(doc.get("shield") or "none"),
        "size": str(race.get("size") or "medium"),
        "speed": int(race.get("speed") or 30),
        "cr": cr, "cr_value": cr_value(cr),
        "creature_type": "humanoid", "subtype": race_id,
        "hit_die_avg": average_hp(int(cls.get("hit_die") or 8), level),
        "favoured_hp": favoured_hp(level),
    }
    for passthrough in ("tags", "kit", "notes", "appearance", "wealth", "pockets",
                        "description", "role"):
        if doc.get(passthrough):
            sheet[passthrough] = doc[passthrough]
    gear = doc.get("gear")
    if isinstance(gear, dict):
        # Step 6's purchases (`rules/npc_gear.outfit`): the suit and shield by their table
        # keys, the kit as a pocket claim, the leftover as coin. A masterwork or enchanted
        # weapon or suit is a forge record, worn by `actor`.
        sheet["armour"] = str((gear.get("armour") or {}).get("base") or "none")
        sheet["shield"] = str(gear.get("shield") or "none")
        sheet["pockets"] = list(gear.get("pockets") or [])
        sheet["coin_gp"] = int(gear.get("coin_gp") or 0)
    return sheet, []


def _selections(cls: dict, scores: dict, race_id: str) -> int:
    """Table 14-8: the class's ranks + Int modifier (at least 1), and humans one more
    ("skilled", one rank a level, CRB p. 27)."""
    n = max(1, int(cls.get("skill_ranks") or 0) + (int(scores["int"]) - 10) // 2)
    return n + (1 if race_id == "human" else 0)


def skill_selections(doc: dict) -> int:
    """How many skills this build may select, by the same arithmetic `build` checks."""
    from . import classes as classes_mod
    from . import creation
    from . import races as races_mod

    cid = str(doc.get("class") or "").strip().lower()
    race_id = str(doc.get("race") or "human").strip().lower()
    scores = _scores(doc, heroic=cid not in classes_mod.npc_classes(), problems=[])
    creation.place_racial_adjustments({"choices": list(doc.get("racial_choices") or [])},
                                      races_mod.get(race_id), scores)
    for ab in doc.get("increases") or ():
        if ab in scores:
            scores[ab] += 1
    return _selections(classes_mod.get(cid), scores, race_id)


def _real_target(target: str) -> bool:
    from . import weapons
    from .tables import SKILLS

    t = str(target).strip().lower()
    return (t in SKILLS or t.split(" (")[0] in ("craft", "profession", "perform")
            or weapons.key_for(t) is not None or weapons.has(t))


def feats_owed(doc: dict) -> int:
    """Step 4's count: 1 at 1st and one per two levels beyond, humans one more, and the
    class table's bonus feats."""
    level = int(doc.get("level") or 1)
    race_id = str(doc.get("race") or "human").strip().lower()
    cid = str(doc.get("class") or "").strip().lower()
    return (1 + (level - 1) // 2 + (1 if race_id == "human" else 0)
            + len(_class_bonus_feats(cid, level)))


def _class_bonus_feats(cid: str, level: int) -> list:
    """The bonus feats the class table grants by this level (a fighter's), which a build
    takes beside the level's own."""
    from . import leveling

    return [n for n in range(1, level + 1) for _ in range(leveling.class_bonus_feats_at(cid, n))]


def actor(doc: dict, ref: str | None = None):
    """The build as an Actor, hit points at Step 7's average, every other number derived.
    Raises ValueError naming the problems when the build does not follow the rules."""
    from .sheet import from_dict

    sheet, problems = build(doc)
    if sheet is None:
        raise ValueError("; ".join(problems))
    base = sheet.pop("hit_die_avg") + sheet.pop("favoured_hp", 0)
    coin = int(sheet.pop("coin_gp", 0) or 0)
    a = from_dict(sheet, ref=ref)
    # The rolled part and the favoured class's hit point a level: the sheet adds
    # Constitution per Hit Die and the feat channel (Toughness) itself (`Actor.hp_max`),
    # so the total follows the scores as a PC's does.
    a.hp_base = base
    # The bought weapon and suit worn as their records, read on their own swing and in
    # their own AC; the weapon held by its record, and its plain key off the carried list
    # so a looter takes one sword, not the record and a second plain one.
    from . import forge_items, npc_gear

    for rec in npc_gear.records(doc.get("gear") or {}):
        # On the shelf and worn, as a player's forged item is: the pack holds the thing
        # (what a looter takes, `Engine._op_loot`), the slot holds the copy `wear` keeps.
        a.add_stock(forge_items.stock_item(rec), 1)
        a.wear(rec)
        if rec.get("gear") == "weapon":
            a.weapons = [w for w in a.weapons if w != rec.get("base")]
            a.equipped = rec["id"]
    if coin:
        a.purse["gp"] = int(a.purse.get("gp", 0)) + coin
    a.hp = a.hp_max
    return a


def check(doc: dict) -> list[str]:
    """Everything wrong with a build, including what only a built sheet can answer: feat
    prerequisites, and a weapon carried in a hand that is not proficient with it."""
    sheet, problems = build(doc)
    if sheet is None:
        return problems
    from . import feats as feats_mod

    a = actor(doc)
    for f in a.feats:
        # Through the one normaliser, so "Skill Focus (Handle Animal)" is Skill Focus
        # with its target, as a player's sheet writes it.
        feat, target = feats_mod.resolve(f)
        if feat is None:
            problems.append(f"feats: no feat {f!r}.")
            continue
        # A target is a real skill or weapon: the roster's first run wrote "Skill Focus
        # (Stealth2)", and `meets` passed it — the prerequisite does not read the target.
        if target and not _real_target(target):
            problems.append(f"feats: {f} — {target!r} is no skill or weapon.")
            continue
        verdict = feats_mod.meets(a, feat)
        # `unknown` refuses too: "an unreadable prerequisite makes the answer honest
        # rather than optimistic" (`feats.meets`), and a build is checked once, here.
        if not verdict.get("ok"):
            why = "; ".join(list(verdict.get("unmet") or []) + [
                f"cannot check: {u}" for u in verdict.get("unknown") or []])
            problems.append(f"feats: {f} — {why}.")
    if a.equipped and not a.is_proficient(a.equipped):
        problems.append(f"equipped: a {a.char_class} {a.level} is not proficient with the "
                        f"{a.equipped} (-4 to hit) — pick a weapon its class grants.")
    return problems
