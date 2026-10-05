"""What a class table grants, as something code can ask about.

Item 39 of the 2026-09-19 play-test, found while finishing the sneak attack work and
written down rather than fixed inside it:

> "`rules/precision.py` is the only thing in the app that reads a class table's `grants`.
> Sneak attack applies; bravery, armour training, weapon training, trap sense, uncanny
> dodge, trapfinding, rogue talents, master strike, arcane bond and arcane school are
> printed on the Class tab and read by nothing."

**And one of them was urgent, because shipping sneak attack made it wrong.** Sneak attack
keys off the defender being flat-footed. Uncanny dodge is the rule that stops a 4th-level
rogue being flat-footed, and improved uncanny dodge is the rule that stops them being
flanked. Both were printed and inert, so a rogue took dice they are immune to — a
coherence problem group 15 introduced, not an old gap.

**A reader, not a special case.** The contract's own worked judgment is that a class
ability "does not need a special case in the engine; it needs a field in the `grants`
grammar, applied generically", and `tests/test_three_laws.py` pins that the engine names
no class ability. So this turns every row of every class table into a TAG, by the first
law's rules — hierarchical, asked by prefix, never matched as a string:

    grants: ["uncanny dodge"]            ->  class.uncanny-dodge
    grants: ["sneak attack 3d6"]         ->  class.sneak-attack
    grants: ["trap sense +2"]            ->  class.trap-sense
    grants: ["improved uncanny dodge"]   ->  class.improved-uncanny-dodge

The NUMBER stays in the table and is read by whoever needs it, exactly as
`precision.dice_for` already reads the sneak dice — because the ladder is the document,
and a homebrew class on the bench that grants uncanny dodge at 6th is then right for
free without anybody editing this file.

Joined to `Actor.standing_tags`, so they are live-read like a feat's tags and a race's:
nothing is stored on the sheet, and correcting a class table corrects every character of
it. `has_state("class.uncanny-dodge")` is the whole interface.

WHAT NOW HAS A READER, and what does not. Stated plainly, because the item this closes
was itself a note about inert documents and the honest half of closing it is saying which
rows are still inert and why:

  uncanny dodge             READ by `Engine._flat_footed`
  improved uncanny dodge    READ by `position.flanking_with`
  evasion / improved        READ by `_op_save`'s damage branch
  sneak attack              READ by `rules/precision.py` (group 15)
  unarmed strike            READ by `Actor.lethality_swap` (lethal fists, no -4), and its
                            die by `Actor.weapon` off the table's `fist` column

  Since 2026-10-05 (class audit, lane 3) the passive NUMBERS are documents too —
  content/class-features/<class>.json, read by the second half of this file: fast
  movement, damage reduction, divine grace, the paladin's and monk's immunities, the
  monk's AC bonus, fist, maneuver training and ki strike, armour training and mastery,
  weapon training, favoured enemy and terrain, trapfinding's Disable Device.

  bravery, trap sense,      written as documents with `when: {"against": "fear" | "trap" |
  still mind               "enchantment"}`, and DROPPED until a save says what it is
                            against: `save` carries no descriptor (its params are `save`
                            and `dc`), spell saves pass only "spell". Adding one to the
                            op would put the trigger in the model's hands, which the third
                            law forbids, so it waits for the descriptor to come from a
                            document (a spell's school, a hazard's row).
  rogue talent, arcane
  bond, arcane school       choices, not grants: they need a picker at level-up, and no
                            level-up feat/talent writer exists (`docs/hollow-classes.md`).
"""
from __future__ import annotations

import re

from . import classes as classes_mod

# The tag family. One level, like `role.` and `proficient.`, because a class feature is
# a flat thing a character either has or does not.
FAMILY = "class"

# What is stripped off a grant to leave its name: a dice ladder, a bonus, a parenthetical,
# a per-day count, a distance, a damage reduction's "N/bypass", "at will", "any distance".
#
# Measured 2026-10-05 (docs/class-audit.md, "the slug splits ladders into unrelated tags"):
# the old pattern stripped `+2`, `3d6` and `(…)` and nothing else, so "smite evil 1/day"
# … "7/day" became SEVEN tags, wild shape ten, the monk's slow fall nine, the barbarian's
# damage reduction five, and "fast movement +10 ft" the tag `class.fast-movement-10-ft`. A
# reader asking the prefix `class.smite-evil` found nothing. Stripped repeatedly, because a
# grant can carry two ("wild shape 2/day" beside "wild shape (Large … elemental)" is fine,
# but "fast movement +10 ft" is a sign, a number and a unit).
_NUMBER = re.compile(
    r"\s*(?:\(.*?\)"                                  # (1d6), (2nd), (Wis)
    r"|[+-]?\s*\d+\s*(?:ft\.?|feet)"                  # +10 ft, 60ft
    r"|\d+\s*/\s*(?:day|[-—–]|[a-z][a-z ]*)"          # 7/day, 1/-, 5/evil, 10/cold iron
    r"|\d*d\d+"                                       # 3d6
    r"|[+-]?\s*\d+"                                   # +2, 3
    r"|at will|any distance)\s*$")
# The number a rung carries, read off what `_NUMBER` strips: "+10 ft" -> 10, "5/evil" -> 5,
# "7/day" -> 7. Never a parenthetical's ("(2nd)" is an ordinal, "(1d6)" a die).
_RUNG_NUMBER = re.compile(r"^[+]?\s*(-?\d+)(?!d)")
_RUNG_BYPASS = re.compile(r"^\d+\s*/\s*(.+)$")

# The features this module's own readers ask for by name. Named here so no reader spells
# a tag inline, and so this file is the list of what is actually wired up.
UNCANNY_DODGE = f"{FAMILY}.uncanny-dodge"
IMPROVED_UNCANNY_DODGE = f"{FAMILY}.improved-uncanny-dodge"
EVASION = f"{FAMILY}.evasion"
# The monk's "unarmed strike (1d6)" row. Core Rulebook, Monk: "At 1st level, a monk gains
# Improved Unarmed Strike as a bonus feat", so this answers the feat's own question —
# may the fist strike lethal without the -4 — for a monk who never picked the feat.
UNARMED_STRIKE = f"{FAMILY}.unarmed-strike"
IMPROVED_EVASION = f"{FAMILY}.improved-evasion"

# Evasion is for people who can move: "can be used only if the rogue is wearing light
# armor or no armor", and "a helpless rogue does not gain the benefit of evasion"
# (Core Rulebook, Rogue). The weight word is the armour table's own.
EVASION_ARMOUR = frozenset({"light"})


def slug(grant: str) -> str:
    """"trap sense +2" -> "trap-sense". The name without its number."""
    return re.sub(r"[^a-z0-9]+", "-", _split(grant)[0]).strip("-")


def _split(grant: str) -> tuple[str, list[str]]:
    """("smite evil", ["1/day"]) — the name and each piece stripped off it, in order.

    The suffix is kept in the order it was written so `rung_number` can read the number
    without a second grammar: one pattern says what a ladder looks like, both halves use
    it.
    """
    text = " ".join(str(grant or "").split()).lower()
    tail: list[str] = []
    while True:
        m = _NUMBER.search(text)
        if not m or not m.group(0).strip() or m.start() == 0:
            break
        tail.insert(0, m.group(0).strip())
        text = text[:m.start()].rstrip()
    return text.strip(), tail


def rung_number(grant: str) -> int | None:
    """The number this rung of a ladder carries, or None: "damage reduction 2/-" -> 2,
    "fast movement +10 ft" -> 10, "smite evil 7/day" -> 7, "AC bonus (Wis)" -> None."""
    for part in _split(grant)[1]:
        if part.startswith("("):
            continue
        m = _RUNG_NUMBER.match(part)
        if m:
            return int(m.group(1))
    return None


def rung_bypass(grant: str) -> str:
    """What gets past a damage-reduction rung: "5/evil" -> "evil", "1/-" -> "" (the
    "—" nothing bypasses, written the way `Reduction.bypass` writes it)."""
    m = next((m for m in map(_RUNG_BYPASS.match, _split(grant)[1]) if m), None)
    if not m:
        return ""
    word = m.group(1).strip()
    # "/day" is a count's unit, not a bypass: only a reduction's rung has one.
    return "" if word in ("-", "—", "–", "day") else word


def rungs(class_id: str, level: int, feature: str) -> list[str]:
    """Every grant string of this feature the table has given by this level, in order:
    the ladder as written. `feature` is a slug or a `class.` tag."""
    want = str(feature or "").split(".")[-1]
    return list(_ladders(class_id, level).get(want, ()))


# Memo of (class, level) -> {slug: rungs}. `has_state` reads the class tags on every
# question and the class documents ask `rank` per feature per roll, so the table walk is
# done once per class and level. Each entry holds the class document it was built from
# and is used only while `classes.get` still returns that very object, so a class edited
# on the bench (which rebuilds `classes`' cache) is re-read, never served stale. Holding
# the object, not its id(), is what makes the identity check sound: a freed dict's id can
# be reused by its replacement.
_LADDERS: dict[tuple[str, int], tuple[dict, dict[str, tuple[str, ...]]]] = {}


def _ladders(class_id: str, level: int) -> dict[str, tuple[str, ...]]:
    cid = str(class_id or "").strip().lower()
    if not cid:
        return {}
    lvl = max(0, int(level or 0))
    cls = classes_mod.get(cid)
    got = _LADDERS.get((cid, lvl))
    if got is None or got[0] is not cls:
        built: dict[str, list[str]] = {}
        for n in range(1, lvl + 1):
            for grant in classes_mod.table_at(cid, n).get("grants") or []:
                leaf = slug(grant)
                if leaf:
                    built.setdefault(leaf, []).append(str(grant))
        if len(_LADDERS) > 512:
            _LADDERS.clear()
        got = _LADDERS[(cid, lvl)] = (cls, {k: tuple(v) for k, v in built.items()})
    return got[1]


def rank(class_id: str, level: int, feature: str) -> int:
    """How many rungs of this ladder have been climbed: weapon training at 9th is 2."""
    return len(rungs(class_id, level, feature))


def number(class_id: str, level: int, feature: str) -> int:
    """The number on the highest rung reached that carries one, else 0.

    The ladder is the document, the way `precision.dice_for` reads sneak dice: a smite
    evil at 7th is 3/day because the table's 7th row says "3/day", and a homebrew table
    that says otherwise is right for free.
    """
    for grant in reversed(rungs(class_id, level, feature)):
        n = rung_number(grant)
        if n is not None:
            return n
    return 0


def tags_for(class_id: str, level: int) -> tuple[str, ...]:
    """Every `class.*` tag this class has granted by this level, in table order.

    Deduplicated: a ladder that names "sneak attack" at nine different levels is one
    thing the character has, not nine.
    """
    return tuple(f"{FAMILY}.{leaf}" for leaf in _ladders(class_id, level))


def granted_at(class_id: str, feature: str) -> int:
    """The class level this feature arrives at, or 0.

    Improved uncanny dodge needs it: "unless the attacker has at least four more rogue
    levels than the target has levels in the class that granted this ability". The level
    is read off the table rather than assumed to be four, for the same reason the dice
    are.
    """
    want = str(feature or "").split(".")[-1]
    for lvl in range(1, 21):
        for grant in classes_mod.table_at(class_id, lvl).get("grants") or []:
            if slug(grant) == want:
                return lvl
    return 0


def caught_flat_footed(defender) -> bool:
    """Whether this creature can be caught flat-footed at all.

    The rule, verbatim (Core Rulebook, Rogue — Uncanny Dodge): "She cannot be caught
    flat-footed, nor does she lose her Dexterity bonus to AC if the attacker is invisible.
    She still loses her Dexterity bonus to AC if immobilized."

    Both halves are kept. The exception is asked as a state question and not as a list of
    condition names: `is_helpless` is this app's owner for 1e's "immobilized, unconscious,
    or otherwise incapacitated", which is the same clause, and the contract is explicit
    that conflating it with `is_down` or `can_act` has cost a bug each.

    The feint exception in the same paragraph — "can still lose her Dexterity bonus to AC
    if an opponent successfully uses the feint action against her" — is not implemented
    because there is no feint action in the app to succeed at. Said rather than silently
    dropped.
    """
    if defender is None or not defender.has_state(UNCANNY_DODGE):
        return True
    return bool(defender.is_helpless)


def cannot_be_flanked(defender, attacker) -> str:
    """Why flanking does not work on this defender, or "".

    "The character can no longer be flanked. This defense denies a rogue the ability to
    sneak attack this character by flanking her, unless the attacker has at least four
    more rogue levels than the target has levels in the class that granted this ability."

    The four-level clause is honoured with the levels both sides actually have, and the
    reason is returned in words because it becomes a tell: the rogue is told their flank
    found a guard, not that a rule fired.
    """
    if defender is None or not defender.has_state(IMPROVED_UNCANNY_DODGE):
        return ""
    theirs = int(getattr(defender, "level", 1) or 1)
    mine = int(getattr(attacker, "level", 1) or 1) if attacker is not None else 1
    # "at least four more rogue levels than the target has levels in the class that
    # granted this ability" — the target's levels in THAT class, which for a
    # single-classed character is their level.
    if mine >= theirs + 4:
        return ""
    return f"{defender.name} cannot be flanked"


def evades(actor) -> str:
    """Which evasion this character has working right now: "improved", "evasion", or "".

    The armour clause and the helpless clause are both the book's and both are checked
    here rather than at the call site, so the one rule has one reader.
    """
    if actor is None:
        return ""
    if actor.is_helpless:
        return ""                      # "a helpless rogue does not gain the benefit"
    from .tables import ARMOUR

    worn = str(getattr(actor, "armour", "") or "none").strip().lower()
    row = ARMOUR.get(worn)
    # The ranger's evasion is "light armor, medium armor, or no armor" (CRB, Ranger), the
    # rogue's and monk's light or none. The class document says which (`evasion.armour`);
    # before it, a ranger in a breastplate lost an evasion the book gives her.
    allowed = EVASION_ARMOUR | _evasion_armour(actor)
    if row is not None and str(row.get("weight", "")).lower() not in allowed:
        return ""
    if actor.has_state(IMPROVED_EVASION):
        return "improved"
    if actor.has_state(EVASION):
        return "evasion"
    return ""


# --- class-feature documents ----------------------------------------------------------
#
# The passive numbers a class table names and nothing read. Measured at 20th level on
# 2026-10-05 (docs/class-audit.md): the barbarian moved at 30 ft with no damage
# reduction, the paladin had no Charisma on any save, and the monk punched at -4 "not
# proficient with unarmed strike", for 1d3, at every level 1-20, with no Wisdom in his AC.
#
# Each class's passives are a DOCUMENT, `content/class-features/<class>.json`, keyed by the
# feature's slug — the feat documents' grammar (stage 8: `modifiers` with `type`, `target`,
# `amount | formula`, `bonus_type`, `when`), plus the few fields a class feature needs that
# a feat does not. Read live on every roll through the one funnel (`Actor._buff_mods` asks
# `modifiers`), so nothing is stored on a sheet: levelling up moves the number, and
# correcting a document corrects every character of the class. The level comes from the
# TABLE, never from code — a formula says `number` (the number on the highest rung
# reached: "damage reduction 2/-" is 2) or `rank` (rungs climbed: weapon training at 9th
# is 2), the way `precision.dice_for` reads sneak dice.
#
# Prior art: Foundry's PF1 system models a class feature as an item carrying "changes"
# whose formulas read the class level, with situational bonuses kept as notes rather than
# applied (not re-fetched for this; its v11 abandonment of copied effects is already the
# contract's reason feats are live-read). What none of the builders does is store the
# result on the sheet, and neither does this.
#
# Conditions are `when` clauses. The roll-context keys are `rules/sheet.py:_when_holds`'s
# own (`target`, `weapon`, `against`, ...), so a term that needs a context the roll does
# not carry is DROPPED, never applied (bravery's "against fear" waits for a save that says
# what it is against). Three keys are this module's, because they are about the BEARER or
# a pick, and no roll context carries them:
#
#   bearer        {"armour": ["none", "light"], "shield": false, "armoured": true,
#                  "load": ["light"], "helpless": false, "pool": "ki",
#                  "terrain": "$pick"} — asked of the character, every key must hold.
#                  `load` holds while encumbrance is not enforced (`gear.load`'s own
#                  `enforced`: the owner ruled load penalties a later batch), so the day it
#                  is, a monk's medium load takes his AC bonus with no edit here.
#   weapon_group  "$pick" — the weapon in hand is in this fighter weapon group
#                  (`weapons.groups_of`).
#   target        "$pick" — a favoured enemy written "humanoid (human)" becomes
#                  {"type": "humanoid", "subtype": "human"}, then the sheet's own clause.
#
# A feature the player CHOOSES for (`choice`: favoured enemy, favoured terrain, weapon
# training) is expanded once per pick, read through `chosen` — one function, so lane 1's
# storage can change shape without touching any reader. `$bonus` is the pick's bonus: the
# stored one if the choice records it, else the document's `pick_bonus` formula over
# `index` (0 = first pick), `picks` and `rank`.

DOC_KEYS = frozenset({"name", "source", "modifiers", "dr", "immunities", "weapon", "armour",
                      "evasion", "choice", "pick_bonus", "tags", "not_yet", "note"})
MOD_KEYS = frozenset({"type", "target", "amount", "formula", "bonus_type", "when", "note"})
# The feat grammar's four, plus `speed` (`target: "land"` after armour, the enhancement
# channel `speed_feet` already reads; `"land_base"` BEFORE armour, which is where the
# barbarian's goes: "apply this bonus before modifying the barbarian's speed because of
# any load carried or armor worn").
MOD_TYPES = ("ability_mod", "skill_mod", "save_mod", "combat_mod", "speed")
BEARER_KEYS = frozenset({"armour", "shield", "armoured", "load", "helpless", "pool",
                         "terrain"})
WEAPON_KEYS = frozenset({"applies_to", "damage_column", "strikes_as", "strikes_as_by_rank",
                         "when"})
ARMOUR_KEYS = frozenset({"max_dex", "check_penalty", "unhindered"})
WEIGHTS = ("none", "light", "medium", "heavy")

# The ranger's terrains (CRB Table 3-11, Ranger Favored Terrains) onto this app's ground
# words (`rules/biomes.py`). "Mountain (including hills)" and "Water (above and below the
# surface)" are the book's own parentheticals; `coast` is in neither and is left out
# rather than guessed into one.
TERRAINS: dict[str, tuple[str, ...]] = {
    "cold": ("tundra",), "desert": ("desert",), "forest": ("forest",),
    "jungle": ("jungle",), "mountain": ("mountain", "hills"),
    "plains": ("grassland", "farmland"), "planes": ("planar",), "swamp": ("swamp",),
    "underground": ("underground",), "urban": ("urban",),
    "water": ("water", "underwater"),
}

# Shipped with the install and never overlaid from a campaign, so there is no homebrew
# copy to go stale (the hazards and gear readers make the same choice). Deliberately not
# the `_NAME: ... | None = None` cache shape: that shape means "merged with homebrew under
# CAMPAIGN_DIR" to the isolation ratchet in tests/test_three_laws.py, and this is not.
_DOCS: dict[str, dict] = {}


def _folder():
    from pathlib import Path

    from django.conf import settings

    return Path(settings.BASE_DIR) / "content" / "class-features"


def forget() -> None:
    _DOCS.clear()


def documents(class_id: str) -> dict:
    """The class's feature documents, keyed by slug ({} for a class with none)."""
    import json

    key = str(class_id or "").strip().lower()
    if not key:
        return {}
    if key not in _DOCS:
        # "blood bending" is the class id and blood-bending.json the file, as in
        # content/classes: a file name has no spaces.
        path = _folder() / f"{re.sub(r'[^a-z0-9]+', '-', key).strip('-')}.json"
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            raw = {}
        _DOCS[key] = {k: v for k, v in raw.items()
                      if not str(k).startswith("_") and isinstance(v, dict)}
    return _DOCS[key]


def _class_of(actor) -> tuple[str, int]:
    return (str(getattr(actor, "char_class", "") or "").strip().lower(),
            int(getattr(actor, "level", 1) or 1))


def held(actor) -> list[tuple[str, dict]]:
    """(slug, document) for every documented feature this character's table has reached."""
    cid, level = _class_of(actor)
    if not cid:
        return []
    docs = documents(cid)
    if not docs:
        return []
    reached = _ladders(cid, level)
    return [(leaf, doc) for leaf, doc in docs.items() if leaf in reached]


def name_of(leaf: str, doc: dict) -> str:
    return str(doc.get("name") or leaf.replace("-", " ").capitalize())


# --- formulas ---------------------------------------------------------------------------

def _variables(actor, leaf: str, extra: dict | None = None):
    from collections import ChainMap

    from . import resources

    cid, level = _class_of(actor)
    own = {"rank": rank(cid, level, leaf), "number": number(cid, level, leaf),
           "class_level": level}
    if extra:
        own.update(extra)
    return ChainMap(own, resources.variables(actor))


def evaluate(formula, actor, leaf: str, extra: dict | None = None) -> int:
    """A document's formula over the sheet's variables plus `rank`, `number` and
    `class_level` (and `index`/`picks` for a pick). The resources grammar, unchanged —
    only the names it may use are widened, never what it may do."""
    import ast

    from . import resources

    if isinstance(formula, (int, float)):
        return int(formula)
    text = str(formula).strip()
    if not text:
        return 0
    try:
        tree = ast.parse(text, mode="eval")
    except SyntaxError as exc:
        raise resources.FormulaError(f"{text!r} is not a formula: {exc.msg}") from exc
    return int(resources._walk(tree.body, _variables(actor, leaf, extra), text) // 1)


def check_formula(formula) -> str:
    """"" when the formula is well formed over the names a document may use, else why."""
    import ast

    from . import resources
    from .tables import ABILITIES

    if isinstance(formula, (int, float)):
        return ""
    names = {n: 1 for n in ("rank", "number", "class_level", "index", "picks", "level",
                            "hit_dice", "hp", "hp_max", "temp_hp", "bab")}
    for ab in ABILITIES:
        names[ab] = 10
        names[f"{ab}_mod"] = 0
    text = str(formula).strip()
    try:
        resources._walk(ast.parse(text, mode="eval").body, names, text)
    except SyntaxError as exc:
        return f"{text!r} is not a formula: {exc.msg}"
    except resources.FormulaError as exc:
        return str(exc)
    return ""


# --- choices ----------------------------------------------------------------------------

def _choice_key(text) -> str:
    return " ".join(str(text or "").replace("favoured", "favored").split()).lower()


def chosen(actor, choice_id: str) -> list[dict]:
    """The picks this character has made for a class choice, in the order made:
    `[{"pick": "undead", "bonus": 4}, {"pick": "humanoid (orc)"}]`.

    THE one reader of the storage, so lane 1's writer can settle its shape here alone
    (docs/class-audit.md, §8: lane 1 owns the picker and storage, lane 3 the numbers).
    Read from `class_choices[<choice id>]` — the store the nature bond already uses — in
    any of the shapes a reasonable writer would produce: a list of words, a list of
    `{"pick": ..., "bonus": ...}`, or `{"picks": [...]}`. "favoured" and "favored" are one
    key, because the table spells it one way and English the other.
    """
    answers = getattr(actor, "class_choices", None) or {}
    want = _choice_key(choice_id)
    raw = next((v for k, v in answers.items() if _choice_key(k) == want), None)
    if isinstance(raw, dict):
        raw = raw.get("picks", raw.get("pick", raw.get("option")))
    if isinstance(raw, (str, dict)):
        raw = [raw]
    out: list[dict] = []
    for item in raw or ():
        if isinstance(item, dict):
            pick = str(item.get("pick") or item.get("name") or item.get("option") or "")
            entry = {"pick": " ".join(pick.split()).lower()}
            if item.get("bonus") is not None:
                try:
                    entry["bonus"] = int(item["bonus"])
                except (TypeError, ValueError):
                    pass
        else:
            entry = {"pick": " ".join(str(item or "").split()).lower()}
        if entry["pick"]:
            out.append(entry)
    return out


def _picks(actor, leaf: str, doc: dict) -> list[tuple[str, int]]:
    """(pick, bonus) for each pick the table's rungs have paid for, in order."""
    cid, level = _class_of(actor)
    got = chosen(actor, str(doc.get("choice") or ""))[:rank(cid, level, leaf)]
    out: list[tuple[str, int]] = []
    for i, entry in enumerate(got):
        bonus = entry.get("bonus")
        if bonus is None:
            try:
                bonus = evaluate(doc.get("pick_bonus", 0), actor, leaf,
                                 {"index": i, "picks": len(got)})
            except Exception:  # noqa: BLE001 — a malformed formula grants nothing
                bonus = 0
        out.append((entry["pick"], int(bonus)))
    return out


def _group_word(word: str) -> str:
    """A weapon group as `weapons.groups_of` spells it. The picker stores the catalogue's
    id ("blades-heavy", "pole-arms") and the book prints "Blades, Heavy"; the weapon
    table says "heavy blades" and "polearms". Read as written, a fighter who picked heavy
    blades on the sheet got no weapon training with a longsword (measured at the
    2026-10-05 merge). Same words in any order, or the same letters run together."""
    from . import weapons as weapons_mod

    words = re.findall(r"[a-z]+", str(word or "").lower())
    for group in weapons_mod.GROUPS:
        if sorted(words) == sorted(group.split()) or "".join(words) == group.replace(" ", ""):
            return group
    return " ".join(words)


def _enemy_clause(pick: str) -> dict:
    """"humanoid (human)" -> {"type": "humanoid", "subtype": "human"}; "undead" ->
    {"type": "undead"}. The book's table writes a subtype in brackets after its type.

    The picker stores the catalogue's id ("humanoid-orc", "magical-beast"), not the
    table's words; read as written, the id became the type "humanoid-orc", which no
    creature has, and every favoured enemy picked through the sheet granted nothing. The
    id is turned back into the catalogue's name before the brackets are read."""
    from . import classes as classes_mod

    named = classes_mod.entry("favored-enemies", str(pick or "")).get("name")
    if named:
        pick = str(named).lower()
    m = re.match(r"^\s*([^()]+?)\s*(?:\((.+)\))?\s*$", str(pick or ""))
    if not m:
        return {}
    out = {"type": m.group(1).strip()}
    if m.group(2):
        out["subtype"] = m.group(2).strip()
    return out


# --- conditions -------------------------------------------------------------------------

def bearer_facts(actor) -> dict:
    """What a `bearer` clause asks, read off the character as they stand."""
    from . import places as places_mod

    worn = str(getattr(actor, "armour", "") or "none").strip().lower()
    if worn in ("", "none"):
        weight = "none"
    else:
        weight = str(actor.armour_stats().get("weight") or "light").lower()
    shield = str(getattr(actor, "shield", "") or "none").strip().lower() not in ("", "none")
    return {"armour": weight, "shield": shield,
            "terrain": places_mod.terrain_of(str(getattr(actor, "at", "") or ""))}


def _load_band(actor) -> str | None:
    """The load band when encumbrance is enforced, else None (the clause then holds)."""
    from . import gear

    try:
        got = gear.load(actor)
    except Exception:  # noqa: BLE001 — a body the load table cannot weigh carries nothing
        return None
    return str(got.get("band")) if got.get("enforced") else None


def _bearer_holds(clause: dict, actor, pick: str = "") -> bool:
    facts = bearer_facts(actor)
    for key, want in (clause or {}).items():
        if key == "armour":
            if facts["armour"] not in [str(w).lower() for w in want or ()]:
                return False
        elif key == "shield":
            if facts["shield"] != bool(want):
                return False
        elif key == "armoured":
            if (facts["armour"] != "none" or facts["shield"]) != bool(want):
                return False
        elif key == "helpless":
            if bool(actor.is_helpless) != bool(want):
                return False
        elif key == "load":
            band = _load_band(actor)
            if band is not None and band not in [str(w).lower() for w in want or ()]:
                return False
        elif key == "pool":
            pool = actor.pool(str(want)) if hasattr(actor, "pool") else None
            if pool is None or int(getattr(pool, "current", 0) or 0) < 1:
                return False
        elif key == "terrain":
            word = pick if want == "$pick" else str(want or "")
            if facts["terrain"] not in TERRAINS.get(word.strip().lower(), ()):
                return False
        else:
            return False                     # a key nobody can answer means no
    return True


def holds(when, actor, ctx: dict | None, pick: str = "") -> bool:
    """A document's `when`: the bearer half here, the roll-context half by the sheet's
    own `_when_holds` — one grammar, never a second copy of it."""
    if not when:
        return True
    if not isinstance(when, dict):
        return False
    rest = dict(when)
    bearer = rest.pop("bearer", None)
    if bearer is not None and not _bearer_holds(bearer, actor, pick):
        return False
    group = rest.pop("weapon_group", None)
    if group is not None:
        from . import weapons as weapons_mod

        held_key = str(((ctx or {}).get("weapon") or {}).get("key") or "")
        word = _group_word(pick if group == "$pick" else str(group))
        if not held_key or word not in weapons_mod.groups_of(held_key):
            return False
    if rest.get("target") == "$pick":
        rest["target"] = _enemy_clause(pick)
    if not rest:
        return True
    from .sheet import _when_holds

    return _when_holds(rest, ctx)


# --- the readers -------------------------------------------------------------------------

def modifiers(actor, kind: str, target: str, ctx: dict | None = None) -> list:
    """Every class-feature term on this number, as the funnel's `Modifier`s.

    Named for the feature, and for the pick when there is one ("Favored enemy
    (undead)"), so the dice popup says where each number came from.
    """
    from .sheet import Modifier, _bonus_type

    want = str(target).lower()
    out = []
    for leaf, doc in held(actor):
        specs = [s for s in doc.get("modifiers") or ()
                 if isinstance(s, dict) and s.get("type") == kind
                 and str(s.get("target", "")).lower() == want]
        if not specs:
            continue
        picks = _picks(actor, leaf, doc) if doc.get("choice") else [("", 0)]
        for pick, bonus in picks:
            label = name_of(leaf, doc) + (f" ({pick})" if pick else "")
            for spec in specs:
                if not holds(spec.get("when"), actor, ctx, pick):
                    continue
                try:
                    if spec.get("amount") == "$bonus":
                        amount = bonus
                    elif spec.get("formula") is not None:
                        amount = evaluate(spec["formula"], actor, leaf)
                    else:
                        amount = int(spec.get("amount", 0) or 0)
                except Exception:  # noqa: BLE001 — a malformed formula grants nothing
                    continue
                if amount:
                    out.append(Modifier(amount, label, _bonus_type(spec.get("bonus_type"))))
    return out


def standing_dr(actor) -> list[dict]:
    """Damage reduction the class documents grant right now: `[{"amount", "bypass",
    "source"}]`, best-only applied by `Actor.damage_reduction` like every other source."""
    cid, level = _class_of(actor)
    out: list[dict] = []
    for leaf, doc in held(actor):
        dr = doc.get("dr")
        if not isinstance(dr, dict) or not holds(dr.get("when"), actor, None):
            continue
        try:
            amount = evaluate(dr.get("amount", 0), actor, leaf)
        except Exception:  # noqa: BLE001
            continue
        bypass = str(dr.get("bypass") or "")
        if bypass == "$rung":
            ladder = rungs(cid, level, leaf)
            bypass = rung_bypass(ladder[-1]) if ladder else ""
        if amount > 0:
            out.append({"amount": amount, "bypass": bypass, "source": name_of(leaf, doc)})
    return out


def immunities(actor) -> list[str]:
    """What the class documents make this character immune to: "disease", "fear"…"""
    out: list[str] = []
    for _leaf, doc in held(actor):
        for word in doc.get("immunities") or ():
            word = " ".join(str(word).split()).lower()
            if word and word not in out:
                out.append(word)
    return out


def tags(actor) -> list[str]:
    """`immune.<x>` for each immunity, plus a document's own `tags` — the has_state half
    of the same facts, so `immune_to` and the condition gate agree."""
    out = [f"immune.{re.sub(r'[^a-z0-9]+', '-', w).strip('-')}" for w in immunities(actor)]
    for _leaf, doc in held(actor):
        out.extend(str(t) for t in doc.get("tags") or () if str(t).strip())
    return out


def _unarmed_key(key: str) -> bool:
    from . import weapons as weapons_mod

    k = " ".join(str(key or "").split()).lower()
    return k in ("unarmed", "unarmed strike", "fist", "fists", "punch") \
        or weapons_mod.key_for(k) == "unarmed"


def weapon_grants(actor, weapon_key: str) -> dict:
    """What the class documents change about this weapon: `{"damage": "1d8",
    "strikes_as": [...], "sources": [...]}`, or {}.

    `applies_to: "unarmed"` is the monk's fist — its die off the table's `fist` column at
    this level, scaled by size (`weapons.size_die`), and ki strike's materials; `"all"` is
    the paladin's aura of faith ("weapons are treated as good-aligned").
    """
    from . import weapons as weapons_mod

    cid, level = _class_of(actor)
    unarmed = _unarmed_key(weapon_key)
    out: dict = {}
    for leaf, doc in held(actor):
        w = doc.get("weapon")
        if not isinstance(w, dict):
            continue
        applies = str(w.get("applies_to") or "unarmed")
        if applies == "unarmed" and not unarmed:
            continue
        if not holds(w.get("when"), actor, None):
            continue
        column = str(w.get("damage_column") or "")
        if column:
            die = str(classes_mod.table_at(cid, level).get(column) or "")
            if die:
                out["damage"] = weapons_mod.size_die(
                    die, str(getattr(actor, "size", "") or "medium"))
        got = list(w.get("strikes_as") or ())
        ladder = w.get("strikes_as_by_rank") or {}
        if ladder:
            have = rank(cid, level, leaf)
            for step, words in sorted(ladder.items(), key=lambda kv: int(kv[0])):
                if int(step) <= have:
                    got.extend(words or ())
        if got:
            out.setdefault("strikes_as", [])
            out["strikes_as"].extend(t for t in got if t not in out["strikes_as"])
        out.setdefault("sources", []).append(name_of(leaf, doc))
    return out


def armour_training(actor) -> dict:
    """{"max_dex": n, "check_penalty": n, "unhindered": {"medium", ...}} while armour is
    worn, else zeros. The fighter's: "reduces the armor check penalty by 1 (to a minimum
    of 0) and increases the maximum Dexterity bonus allowed by his armor by 1", every four
    levels after 3rd; "move at his normal speed while wearing medium armor. At 7th level,
    ... heavy armor" (CRB, Fighter)."""
    out = {"max_dex": 0, "check_penalty": 0, "unhindered": set(), "source": ""}
    if bearer_facts(actor)["armour"] == "none":
        return out
    cid, level = _class_of(actor)
    for leaf, doc in held(actor):
        a = doc.get("armour")
        if not isinstance(a, dict):
            continue
        try:
            out["max_dex"] += max(0, evaluate(a.get("max_dex", 0), actor, leaf))
            out["check_penalty"] += max(0, evaluate(a.get("check_penalty", 0), actor, leaf))
        except Exception:  # noqa: BLE001
            continue
        have = rank(cid, level, leaf)
        for weight, from_rank in (a.get("unhindered") or {}).items():
            if have >= int(from_rank):
                out["unhindered"].add(str(weight).lower())
        out["source"] = name_of(leaf, doc)
    return out


def _evasion_armour(actor) -> frozenset:
    """Armour weights a class document lets this character's evasion work in."""
    out: set[str] = set()
    for _leaf, doc in held(actor):
        e = doc.get("evasion")
        if isinstance(e, dict):
            out.update(str(w).lower() for w in e.get("armour") or ())
    return frozenset(out)


# --- validation ----------------------------------------------------------------------------

def validate(class_id: str, docs: dict | None = None) -> list[str]:
    """Everything wrong with a class's feature documents, each with the fix named.

    A document keyed by a slug the class table never grants is refused: it would be read
    by nothing, which is the defect this whole section exists to end.
    """
    docs = documents(class_id) if docs is None else docs
    problems: list[str] = []
    granted = {slug(g) for lvl in range(1, 21)
               for g in classes_mod.table_at(class_id, lvl).get("grants") or []}
    for leaf, doc in docs.items():
        at = f"class-features/{class_id}.{leaf}"
        if leaf not in granted:
            problems.append(f"{at}: the {class_id} table grants nothing called {leaf!r}, so "
                            f"nothing would ever read this. Key it by a granted slug: "
                            f"{', '.join(sorted(granted))}.")
        extra = sorted(set(doc) - DOC_KEYS)
        if extra:
            problems.append(f"{at}: unknown field(s) {', '.join(extra)}; a class-feature "
                            f"document carries {', '.join(sorted(DOC_KEYS))}.")
        if not str(doc.get("source") or "").strip():
            problems.append(f"{at}: say where the rule is printed (`source`) — every "
                            f"number here is checked against the book.")
        for i, spec in enumerate(doc.get("modifiers") or ()):
            mat = f"{at}.modifiers[{i}]"
            if not isinstance(spec, dict) or spec.get("type") not in MOD_TYPES:
                problems.append(f"{mat}: `type` is one of {', '.join(MOD_TYPES)}.")
                continue
            bad = sorted(set(spec) - MOD_KEYS)
            if bad:
                problems.append(f"{mat}: unknown key(s) {', '.join(bad)}; a modifier "
                                f"carries {', '.join(sorted(MOD_KEYS))}.")
            if spec.get("amount") is None and spec.get("formula") is None:
                problems.append(f"{mat}: an `amount` (a number, or \"$bonus\" with a "
                                f"`choice`) or a `formula`.")
            if spec.get("amount") == "$bonus" and not doc.get("choice"):
                problems.append(f"{mat}: \"$bonus\" is a pick's bonus and this document "
                                f"has no `choice`.")
            if spec.get("formula") is not None and check_formula(spec["formula"]):
                problems.append(f"{mat}.formula: {check_formula(spec['formula'])}")
            problems.extend(_check_when(spec.get("when"), mat, doc))
        for field_name in ("dr", "weapon", "armour", "evasion"):
            if field_name in doc and not isinstance(doc[field_name], dict):
                problems.append(f"{at}.{field_name}: an object.")
        if isinstance(doc.get("dr"), dict):
            if check_formula(doc["dr"].get("amount", 0)):
                problems.append(f"{at}.dr.amount: {check_formula(doc['dr']['amount'])}")
            problems.extend(_check_when(doc["dr"].get("when"), f"{at}.dr", doc))
        if isinstance(doc.get("weapon"), dict):
            bad = sorted(set(doc["weapon"]) - WEAPON_KEYS)
            if bad:
                problems.append(f"{at}.weapon: unknown key(s) {', '.join(bad)}.")
            if doc["weapon"].get("applies_to", "unarmed") not in ("unarmed", "all"):
                problems.append(f"{at}.weapon.applies_to: \"unarmed\" or \"all\".")
            problems.extend(_check_when(doc["weapon"].get("when"), f"{at}.weapon", doc))
        if isinstance(doc.get("armour"), dict):
            bad = sorted(set(doc["armour"]) - ARMOUR_KEYS)
            if bad:
                problems.append(f"{at}.armour: unknown key(s) {', '.join(bad)}.")
        if doc.get("choice") and not str(doc.get("pick_bonus", "")).strip():
            problems.append(f"{at}: a `choice` needs a `pick_bonus` formula for picks that "
                            f"do not record their own bonus.")
        for field_name in ("immunities", "tags", "not_yet"):
            got = doc.get(field_name)
            if got is not None and (not isinstance(got, list)
                                    or any(not str(x).strip() for x in got)):
                problems.append(f"{at}.{field_name}: a list of strings.")
    return problems


def _check_when(when, where: str, doc: dict) -> list[str]:
    if when is None:
        return []
    if not isinstance(when, dict):
        return [f"{where}.when: an object."]
    out: list[str] = []
    bearer = when.get("bearer")
    if bearer is not None:
        if not isinstance(bearer, dict):
            out.append(f"{where}.when.bearer: an object.")
        else:
            bad = sorted(set(bearer) - BEARER_KEYS)
            if bad:
                out.append(f"{where}.when.bearer: unknown key(s) {', '.join(bad)}; it asks "
                           f"{', '.join(sorted(BEARER_KEYS))}.")
            for w in bearer.get("armour") or ():
                if w not in WEIGHTS:
                    out.append(f"{where}.when.bearer.armour: {w!r} is not one of "
                               f"{', '.join(WEIGHTS)}.")
            terrain = bearer.get("terrain")
            if terrain is not None and terrain != "$pick" and terrain not in TERRAINS:
                out.append(f"{where}.when.bearer.terrain: one of {', '.join(TERRAINS)} "
                           f"or \"$pick\".")
    for key in ("weapon_group", "target"):
        if when.get(key) == "$pick" and not doc.get("choice"):
            out.append(f"{where}.when.{key}: \"$pick\" needs a `choice` on the document.")
    return out
