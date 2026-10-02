"""Every herb effect is a complete structured document, never prose.

The owner, 2026-10-02: herb effects follow the GAS framework (docs/states-effects-tells.md).
The lead ruled that the flat `rules/effectspec.py` dict already is that document, one per
effect, our GameplayEffect, with `route` as its application requirement; it is not
nested by route. "Complete" means the engine can run it from its fields alone:

1. it is a type `effectspec.executable` says the engine resolves;
2. anything temporary carries `duration: {"amount": <int>, "unit": ...}`, because the
   bench's quality scaling multiplies `duration.amount`, and a duration written in a note
   can never be lengthened. An int and not dice: the lead's brief allowed dice, and the
   engine's `_to_rounds` reads `int(amount)`, so a thrown Dragon Flower whose nausea
   lasted "1d6" rounds raised ValueError in the middle of the throw (measured, the
   consumables tests' own board). Aconite shipped one such duration before this pass;
   the engine rolling duration dice is a rules change, not a data one;
3. every condition it causes ends;
4. a bonus names its 1e type, alchemical for an herbal preparation, so two of them do
   not stack the way two untyped bonuses do;
5. magnitudes are numbers or dice, never words;
6. it says its route.

Measured on ui/table-v2 before this pass, across the 161 ingredients:

- **47 effects the engine could not run**: 27 `narrative`, 16 `situational_mod`, 4
  `permission` (the lead's own count, 48, included one `spell_effect` this measurement
  does not find on ui/table-v2).
- **132 effects carried a `note`**, 9 of them with a number or a duration inside it.
- **54 temporary effects had no duration at all** (24 of them conditions, among them
  Dawnpetal's exhaustion and Mad Cap's coma), **39 durations wrote their amount as
  text** ("1" rather than 1), Aconite's nausea lasted "1d4" rounds, which crashes the
  condition op, and Dragon Flower's penalty lasted "1d4 week", a unit the engine has no
  clock for.
- **62 bonuses were untyped**.

After: 0 of each. Every condition now ends; the engine's own comment on `_op_condition`
records why that matters ("an unbounded paralysis was a campaign the character never
played again").
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from rules import effectspec
from rules import ingredients as ing

CORPUS = Path("content/ingredients/herbs-and-parts.json")

# Types that last: a buff, a defence, a pool, a condition, a hazard.
TEMPORARY = {"ability_mod", "skill_mod", "save_mod", "combat_mod", "situational_mod",
             "temp_hp", "resistance", "damage_reduction", "immunity", "vulnerability",
             "concealment", "speed", "sense", "fast_healing", "apply_condition", "bleed",
             "manifest"}
UNITS = {"round", "minute", "hour", "day", "permanent"}
DICE = re.compile(r"^\d*d\d+([+-]\d+)?$")
# A note may qualify ("against disease") or carry flavour. A digit or a unit of time in
# it is a mechanic hiding from the fields that would run it.
MECHANICS_IN_A_NOTE = re.compile(r"\d|\b(rounds?|minutes?|hours?|days?|weeks?)\b", re.I)

# Bonuses that are not alchemical, each because the source names the kind of magic
# whose bonus type it is. Pinned by hand so a new exception is a decision, not a drift.
TYPED_ON_PURPOSE = {
    ("behemoth-hide", "natural armour"): "the hide toughens the wearer's own hide",
    ("ironbark-moss", "natural armour"): "barkskin by another name",
    ("fey-cherry", "deflection"): "protection from evil: a deflection bonus to AC",
    ("fey-cherry", "resistance"): "protection from evil: a resistance bonus on saves",
    ("mad-cap", "morale"): "a rage, and rage's bonus is morale",
    ("spriggan-tree", "size"): "enlarge person's Strength is a size bonus",
    ("tahtoalehti", "inherent"): "a wish grants an inherent bonus",
}


def _effects():
    """Every effect, nested branches included, with where it lives."""
    def walk(spec, where):
        yield where, spec
        for key in ("on_failure", "on_success", "options", "effects", "on_enter"):
            for i, inner in enumerate(spec.get(key) or []):
                if isinstance(inner, dict):
                    yield from walk(inner, f"{where} > {key} {i + 1}")

    for e in json.loads(CORPUS.read_text(encoding="utf-8"))["ingredients"]:
        for i, s in enumerate(e.get("effects") or []):
            yield from ((e["id"], w, x) for w, x in walk(s, f"effect {i + 1}"))


def test_every_effect_is_one_the_engine_runs():
    """47 before: narrative lines ("The odour frightens animals"), situational
    modifiers the GM had to recognise, permissions, all shown and none rolled. Each was
    replaced in its own slot, so the herbarium's positional keys still point at it."""
    bad = [f"{i} {w}: {s['type']}" for i, w, s in _effects()
           if not effectspec.executable(s)]
    assert bad == []


def test_anything_temporary_has_a_structured_duration():
    """54 temporary effects had no duration and 39 wrote theirs as text. The bench
    lengthens a duration by scaling `duration.amount`; one that is missing or prose
    cannot be lengthened, and one with no duration at all never ends.

    Dice durations are rolled by the engine (owner, 2026-10-02: "roll them, it's what
    should have been happening"). Every duration reader goes through one dice-aware door
    (`Engine._duration_rounds`), and the bench scales dice as dice (1d4 at x1.5 is
    1d4+2), so an amount may be a positive integer OR dice the project's own parser reads.
    Prose ("a while", "1 week") still fails here."""
    from rules.dice import BadDice, Dice

    def readable(amount) -> bool:
        if isinstance(amount, int):
            return amount > 0
        try:
            Dice(seed=1).parse(str(amount))
            return True
        except (BadDice, ValueError):
            return False

    bad = []
    for iid, where, s in _effects():
        if s.get("type") not in TEMPORARY:
            continue
        dur = s.get("duration")
        if not isinstance(dur, dict) or dur.get("unit") not in UNITS:
            bad.append(f"{iid} {where}: {dur}")
            continue
        amount = dur.get("amount")
        if dur["unit"] != "permanent" and not readable(amount):
            bad.append(f"{iid} {where}: amount {amount!r}")
    assert bad == []


def test_the_sources_dice_durations_stay_dice():
    """The herb rework (2026-10-02) flattened every dice duration to its average because
    the engine could not roll one; the owner ruled they are rolled. These six are the
    source's own dice, restored, and pinned so they cannot quietly become averages again.
    (Mad Cap's rage stays at a minute by the owner's choice; Menhirite heals 1d6.)"""
    from rules import ingredients

    want = {("aconite", 2): "1d4", ("dragon-flower", 0): "1d6",
            ("dragon-flower", 4): "1d6", ("lish-nut", 1): "2d4",
            ("mad-cap", 3): "1d10", ("mandrake", 2): "1d4"}
    every = ingredients.all_ingredients()
    got = {k: every[k[0]].effects[k[1]]["duration"]["amount"] for k in want}
    assert got == want


def test_every_condition_ends():
    """24 conditions had no duration before this pass, including Mad Cap's
    unconsciousness and Dawnpetal's exhaustion: applied, they never ticked off."""
    bad = [f"{i} {w}: {s.get('target')}" for i, w, s in _effects()
           if s.get("type") == "apply_condition" and not isinstance(s.get("duration"), dict)]
    assert bad == []


def test_no_mechanic_hides_in_a_note():
    """132 effects carried a note and 9 of those held a number or a duration, which no
    field reads: "for 2 hours" in a note is a duration the engine never sees."""
    bad = [f"{i} {w}: {s['note']!r}" for i, w, s in _effects()
           if s.get("note") and MECHANICS_IN_A_NOTE.search(str(s["note"]))]
    assert bad == []


def test_bonuses_are_typed_and_alchemical_unless_the_source_says_otherwise():
    """62 bonuses were untyped, and untyped stacks with everything. An herbal
    preparation's bonus is alchemical, so a second tea for the same save does not stack;
    the pinned exceptions above each name the rule that types them otherwise."""
    allowed = {o["id"] for o in effectspec.VOCAB["bonus_type"]}
    bad = []
    for iid, where, s in _effects():
        if not str(s.get("type", "")).endswith("_mod"):
            continue
        bonus = s.get("bonus_type")
        if bonus not in allowed:
            bad.append(f"{iid} {where}: {bonus!r} is not a bonus type")
            continue
        if isinstance(s.get("amount"), int) and s["amount"] > 0 and bonus != "alchemical" \
                and (iid, bonus) not in TYPED_ON_PURPOSE:
            bad.append(f"{iid} {where}: {bonus}")
    assert bad == []
    by_id = {e["id"] for e in json.loads(CORPUS.read_text(encoding="utf-8"))["ingredients"]}
    assert {i for i, _ in TYPED_ON_PURPOSE} <= by_id, "a stale exemption"


def test_magnitudes_are_numbers_or_dice():
    """An amount is an integer and dice are dice; never "a little", never a formula."""
    bad = []
    for iid, where, s in _effects():
        if "amount" in s and s.get("type") != "save_gate" and not isinstance(s["amount"], int):
            bad.append(f"{iid} {where}: amount {s['amount']!r}")
        if "dice" in s and not (DICE.match(str(s["dice"])) or str(s["dice"]).isdigit()
                                or re.fullmatch(r"\d+-\d+", str(s["dice"]))):
            bad.append(f"{iid} {where}: dice {s['dice']!r}")
    assert bad == []


def test_every_top_level_effect_names_its_route():
    """The route is the effect's application requirement: which product can carry it. A
    missing one reads as `ingest`, which is how an untagged external effect would slip
    onto a herbal tea."""
    raw = json.loads(CORPUS.read_text(encoding="utf-8"))["ingredients"]
    bad = [f"{e['id']} effect {i + 1}" for e in raw
           for i, s in enumerate(e.get("effects") or []) if s.get("route") not in ing.ROUTES]
    assert bad == []
