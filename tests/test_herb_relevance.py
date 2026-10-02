"""Every herb is worth picking up, and every one does what its card says.

The owner's ruling, 2026-10-02: "for all of the hybrids that would only leave negatives
just make them have positives that apply through herbalism ... I would rather you change
the description to match what it does in app and bring all the herbs that do nothing
into relevance as herbs used to make bases or giving them positive effects."

So the app's mechanics are the truth. An ingredient is **irrelevant** when it is not a
bench reagent (a salve base, a solvent or a neutralizer) and no structured effect it
carries on a herbalist's route (`ingest`, `skin`, `eyes`, `wound`, `inhale`) both helps
the taker and is something the engine actually runs when the product is used.

"Actually runs" is asked of `consumables._spec_to_intents`, the one function that turns a
drunk or applied effect into engine intents, and of `intents.parse`, which the engine
refuses a malformed intent at, rather than of a list kept here. A `situational_mod`, a
`narrative`, a `permission` or a `sense` is shown to the GM and rolls nothing, and
`fast_healing` has no mapping there either: an herb whose only good was one of those was
a card line and nothing else. `remove_condition` is worse than inert (see `runs`).

Measured on ui/table-v2 before this pass (161 entries, 17 of them salve bases):

- **75 of 161 irrelevant.** 33 had no effect on a herbal route at all (Cave Star, whose
  one "effect" was its crafting DC, routed external; Mistveil Fern; every ward that
  worked only strewn or worn). 33 carried only drawbacks, crafting DCs or a condition
  removal that cannot run there (all three poisons; Harpy Vocal Cord's -2 Diplomacy;
  Cowslip). 9 had a benefit that only the GM could narrate (Chimera Horn's "+3 saves
  against chaotic magic", Dragon Flower's "+5 save vs poison").
- **5 effects broke the whole use**: every `remove_condition` (Allnight, Cowslip,
  Dawnpetal, Sherpa's Friend, Skull Orchid) became an intent the engine refuses.
- **39 of 63 hybrids** left the herbalist nothing that helps, among them the bark
  hybrids that count as relevant only because they are salve bases.
- **41 bare save gates gated nothing**: the entry's own crafting DC restated at the end
  of the description ("DC: 15."), or a check that is not a save, read as a save by the
  extractor's bare-DC fallback.
- **11 misparsed conditions**: Barbarian Chew "stunned" (it lengthens a rage), Chimera
  Horn "prone" ("prone to erratic behavior"), Menhirite and Nahre Lotus "dead", Skull
  Orchid *ending* "dead", Old Man's Friend "dying" (it stabilizes the dying), Borage,
  Firesnap and Juniper Berry "unconscious" (all three wake the unconscious), Sweetspire
  "paralyzed" (it grants a save against paralysis), and Frostbloom's fire resistance
  stored as 0 where the text says 10.
- **62 bonuses were untyped**, so two teas for the same save stacked where two
  alchemical preparations do not.
- **23 descriptions carried a dash**: a minus sign written as an en-dash ("a –3
  penalty"), and two em-dashes in Golden Maple Leaves.

After: 0 of each.
"""
from __future__ import annotations

import json
from pathlib import Path

from rules import consumables, effectspec, intents
from rules import ingredients as ing

CORPUS = Path("content/ingredients/herbs-and-parts.json")

# What a misparse looked like: a condition no herb in this corpus imposes as written.
# Dead and dying are never an herb's to give; stunned and prone came from "rage" and
# "prone to erratic behavior".
NEVER_APPLIED = {"dead", "dying", "stunned", "prone"}
NEVER_REMOVED = {"dead"}
# Conditions that take a creature out of the fight. A remedy never does that unasked,
# so each one must sit behind a save, as a poison does (`consumables.poisons` groups a
# bare gate with the harm its entry carries). Four entries applied one with no save at
# all, and every one of them was a remedy for that very condition.
DISABLING = {"unconscious", "paralyzed", "helpless", "petrified"}

# The ceiling on one modifier, by rarity tier (the balance rule this pass followed:
# common +1/+2, uncommon +2, rare +2/+3, exotic +3/+4, legendary +4/+6).
BONUS_CEILING = {"common": 2, "uncommon": 2, "rare": 3, "exotic": 4, "legendary": 6}
# And on healing and temporary hit points, as the average of the dice: common around
# 1d4, uncommon 1d6, rare 1d8 or 2d4, exotic a few dice more, legendary the most.
HEAL_CEILING = {"common": 4.5, "uncommon": 7.0, "rare": 9.0, "exotic": 14.0,
                "legendary": 21.0}


def _raw() -> list[dict]:
    return json.loads(CORPUS.read_text(encoding="utf-8"))["ingredients"]


def runs(spec: dict) -> bool:
    """Whether using a product that carries this effect makes the engine do anything.

    Two questions, because the first alone answered wrongly: `_spec_to_intents` must
    produce intents, and every one of them must pass `intents.parse`, the schema the
    engine refuses a bad intent at. `remove_condition` produces a `condition` intent
    carrying `remove`, and the op takes `ends`, so every drink holding one raised
    IntentError and the whole use failed: Cowslip, Sherpa's Friend, Allnight and
    Dawnpetal, measured on the bench's own drink path in tests/test_consumables.py."""
    made = consumables._spec_to_intents(dict(spec), "pc", 1.0, "audit")
    try:
        for raw in made:
            intents.parse(dict(raw))
    except intents.IntentError:
        return False
    return bool(made)


def _amount(spec: dict) -> int:
    try:
        return int(spec.get("amount") or 0)
    except (TypeError, ValueError):
        return 0


def helps(spec: dict) -> bool:
    """Whether one effect is good for whoever takes it, and the engine runs it."""
    kind = str(spec.get("type", ""))
    if kind in ("heal", "temp_hp"):
        good = True
    elif kind.endswith("_mod") or kind == "speed":
        good = _amount(spec) > 0
    elif kind in ("resistance", "damage_reduction"):
        good = _amount(spec) > 0
    elif kind == "immunity":
        good = bool(str(spec.get("target") or "").strip())
    elif kind == "remove_condition":
        good = str(spec.get("target") or "") not in NEVER_REMOVED
    else:
        good = False
    return good and runs(spec)


def herbal_benefits(entry: dict) -> list[dict]:
    return [s for s in entry.get("effects") or []
            if ing.route_of(s) in ing.HERBAL_ROUTES and helps(s)]


def is_reagent(entry: dict) -> bool:
    return bool(entry.get("base_for") or entry.get("solvent") or entry.get("neutralizer"))


def irrelevant(entries: list[dict]) -> dict[str, str]:
    """Every entry that earns no place on the herbalist's bench, with the reason.

    The detector the pass was built on (CLAUDE.md: find the defect in code, then fix
    what was found). Takes raw entries so it can be pointed at an older copy of the
    corpus to measure a before."""
    out: dict[str, str] = {}
    for e in entries:
        if is_reagent(e) or herbal_benefits(e):
            continue
        herbal = [s for s in e.get("effects") or []
                  if ing.route_of(s) in ing.HERBAL_ROUTES]
        if not herbal:
            why = "no effect on a herbal route"
        elif any(str(s.get("type")) in ("situational_mod", "narrative", "permission",
                                         "sense", "fast_healing")
                 for s in herbal):
            why = "its only good is narrated, and the engine runs none of it"
        else:
            why = "its herbal routes carry only drawbacks or crafting DCs"
        out[e["id"]] = why
    return out


def _poisonous(entry: dict) -> bool:
    return any(consumables._poisonous(s) for s in entry.get("effects") or [])


def gates_that_gate_nothing(entries: list[dict]) -> list[str]:
    """A bare save (no branches of its own) on an entry with no harm for it to gate.

    `consumables.poisons` ties a bare gate to the harm its own entry carries, so a gate
    on an entry with none is a number on a card that nothing ever rolls: almost always
    the crafting DC printed at the end of the description."""
    return [f"{e['id']} DC {s.get('dc')}" for e in entries
            for s in e.get("effects") or []
            if s.get("type") == "save_gate"
            and not (s.get("on_failure") or s.get("on_success"))
            and not _poisonous(e)]


def misparsed_conditions(entries: list[dict]) -> list[str]:
    bad = []
    for e in entries:
        gated = any(s.get("type") == "save_gate" for s in e.get("effects") or [])
        for s in e.get("effects") or []:
            kind, target = s.get("type"), str(s.get("target") or "")
            if kind == "apply_condition" and target in NEVER_APPLIED:
                bad.append(f"{e['id']} applies {target}")
            if kind == "apply_condition" and target in DISABLING and not gated:
                bad.append(f"{e['id']} applies {target} with no save")
            if kind == "remove_condition" and target in NEVER_REMOVED:
                bad.append(f"{e['id']} removes {target}")
            if kind == "resistance" and _amount(s) <= 0:
                bad.append(f"{e['id']} resists {target} by {s.get('amount')}")
    return bad


# --- the ratchets -------------------------------------------------------------------------

def test_every_ingredient_is_a_remedy_or_a_reagent():
    """75 of 161 were irrelevant before this pass (see the module docstring): nothing on
    a herbal route that both helps and runs, and no base, solvent or neutralizer role.
    Cave Star's only effect was its crafting DC; Harpy Vocal Cord's only body effect was
    the -2 Diplomacy it charged for a charm the herbalist cannot make."""
    bad = irrelevant(_raw())
    assert bad == {}, f"{len(bad)} irrelevant: {bad}"


def test_no_hybrid_is_drawback_only_on_the_herbalists_routes():
    """A hybrid sits on both shelves, and the herbalist keeps only its body routes. 39
    of 63 hybrids left the herbalist nothing but a cost (Salamander Ember Gland: 1d4 fire to
    the drinker, the flame itself external) or nothing at all (Mistveil Fern: both
    effects external)."""
    bad = [e["id"] for e in _raw() if e.get("hybrid") and not herbal_benefits(e)]
    assert bad == []


def test_no_misparsed_condition_survives():
    """Barbarian Chew stunned its chewer, Chimera Horn knocked its user prone, Menhirite
    and Nahre Lotus applied death, Skull Orchid cured it, Old Man's Friend put the dying
    to dying, Borage, Firesnap and Juniper Berry knocked out the people they were meant
    to wake, and Frostbloom resisted fire by 0. 11 before; 0 now."""
    assert misparsed_conditions(_raw()) == []


def test_every_save_gate_gates_something():
    """41 bare save gates gated nothing before this pass. Most were the entry's own
    crafting DC ("Cave Star ... DC: 10."), now in its `craft_dc` field; the rest were
    checks that are not saves (Darkroot's DC 20 Strength check to pull the glue apart,
    Orevine's Knowledge check) and are said in words."""
    assert gates_that_gate_nothing(_raw()) == []


def test_no_effect_breaks_the_use_it_rides_in():
    """One unparseable intent fails the whole drink, so an effect the engine refuses is
    worse than a missing one: it takes every good effect in the jar down with it. 5
    `remove_condition` effects did this before the pass (Dragon Flower, the fixture the
    consumables tests drink and throw, would have joined them had this pass added the
    "ends sickened" it first tried). If the drink path learns to send `ends`, this
    passes for a removal again by itself."""
    bad = []
    for e in _raw():
        for s in e.get("effects") or []:
            for raw in consumables._spec_to_intents(dict(s), "pc", 1.0, "audit"):
                try:
                    intents.parse(dict(raw))
                except intents.IntentError as exc:
                    bad.append(f"{e['id']} {s['type']}: {exc}")
    assert bad == []


def test_every_effect_renders_and_validates():
    """A card line is `effectspec.render`; an effect it cannot render, or one the
    editor's own validator refuses, is a card that breaks or a save that cannot be
    written back."""
    problems = []
    for e in _raw():
        for i, s in enumerate(e.get("effects") or []):
            assert effectspec.render(s), (e["id"], i)
            problems += effectspec.validate(s, f"{e['id']} effect {i + 1}")
    assert problems == []


def test_every_number_is_fixed_in_the_data():
    """No model and no formula authors a herb's number. An amount is an integer and a
    dice field is plain dice, so the card and the engine read the same figure."""
    bad = []
    for e in _raw():
        for s in e.get("effects") or []:
            if "amount" in s and not isinstance(s["amount"], int):
                bad.append((e["id"], s["type"], s["amount"]))
            if "dice" in s and effectspec.is_formula(s["dice"]):
                bad.append((e["id"], s["type"], s["dice"]))
    assert bad == []


def test_bonuses_and_healing_stay_inside_their_tier():
    """Balanced by rarity, Pathfinder 1e style. Before this pass a common Shadowvine gave
    +5 Stealth, a common Bloodroot 10 temporary hit points for 8 hours, and an exotic
    Cotsbalm +8 Fortitude. Penalties are drawbacks and are not capped here."""
    over = []
    for e in _raw():
        cap, heal_cap = BONUS_CEILING[e["tier"]], HEAL_CEILING[e["tier"]]
        for s in herbal_benefits(e):
            kind = s["type"]
            if kind.endswith("_mod") and _amount(s) > cap:
                over.append(f"{e['id']} {effectspec.render(s)} (cap +{cap})")
            if kind in ("heal", "temp_hp") and _average(s["dice"]) > heal_cap:
                over.append(f"{e['id']} {effectspec.render(s)} (cap {heal_cap})")
    assert over == []


def test_bonuses_carry_a_type_so_they_stack_as_the_book_says():
    """1e stacks untyped bonuses and does not stack two of a kind. 62 bonuses were
    untyped, so two herbal teas for the same save stacked where two alchemical
    preparations do not. A benefit names its type; penalties stay untyped, because
    penalties always stack."""
    bad = [f"{e['id']}: {effectspec.render(s)}" for e in _raw()
           for s in e.get("effects") or []
           if str(s.get("type", "")).endswith("_mod") and _amount(s) > 0
           and s.get("bonus_type") in (None, "", "untyped")]
    assert bad == []


def test_no_description_carries_a_dash():
    """No em-dashes or en-dashes in player-facing herb text. 23 descriptions carried
    one: a minus sign written as an en-dash ("a –3 penalty"), or Golden Maple Leaves'
    two em-dashes."""
    bad = [e["id"] for e in _raw()
           for field in ("text", "harvesting")
           if "—" in (e.get(field) or "") or "–" in (e.get(field) or "")]
    assert bad == []


def test_the_built_ingredient_agrees_with_the_file():
    """The audit reads the raw file; the bench reads `Ingredient.specs`. They must be the
    same effects, or the audit would pass a file the game reads differently."""
    built = ing.all_ingredients()
    for e in _raw():
        assert built[e["id"]].specs == [dict(s) for s in e.get("effects") or []], e["id"]


def _average(dice) -> float:
    import re

    text = str(dice).replace(" ", "")
    m = re.fullmatch(r"(\d*)d(\d+)([+-]\d+)?", text)
    if m:
        n, sides, flat = int(m.group(1) or 1), int(m.group(2)), int(m.group(3) or 0)
        return n * (sides + 1) / 2 + flat
    m = re.fullmatch(r"(\d+)-(\d+)", text)
    if m:
        return (int(m.group(1)) + int(m.group(2))) / 2
    return float(int(text))
