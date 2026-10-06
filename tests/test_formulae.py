"""Alchemy formulae (alchemy plan §10, §11; contracts §5; lane E).

What was measured before this lane, and what each test below keeps from coming back:
- formulae keyed on exact material names and method chains: a near-miss made an ordinary
  preparation, and the 30 effectless "key" materials existed only to be named (plan §5.1);
- a potion of haste sold for 60 gp against the book's 750 (inv §0.4), and anyone at
  Alchemist 3 brewed any of the 44 with no caster level and no level-by-spell gate;
- the plan's "791 spells fully executable" counted top-level documents only: 347 of the
  783 that pass that count carry a save gate whose failure branch is prose (baleful
  polymorph turns its victim into "As beast shape III, ..."), so a derived potion of them
  would have done nothing on a failed save;
- the contract's derived-row level max(1, 2n) asked Alchemist 2 for a 1st-level potion
  the owner's cap (max(1, floor(level/2))) opens at Alchemist 1.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from rules import effectspec, formulae, knowledge, materials, spells
from rules.sheet import Actor

ROOT = Path(__file__).resolve().parent.parent
POTIONS = json.loads((ROOT / "content/materials/alchemist-spell-potions.json")
                     .read_text(encoding="utf-8"))["potions"]
RAW = json.loads((ROOT / "content/rules/alchemy-formulae.json").read_text(encoding="utf-8"))


def _pc(level: int = 1) -> Actor:
    pc = Actor(name="Alchemist", ref="pc")
    pc.track("alchemist").level = level
    return pc


def _mix(*pairs) -> dict:
    """A mix as the bench pools it (contracts §5): benefits with their essence and grade."""
    return {"traits": [{"key": f"t.{e}", "essence": e, "grade": g, "from": ["x"]}
                       for e, g in pairs],
            "drawbacks": [], "materials": ["x"]}


# --- the derivation table --------------------------------------------------------------------

def test_the_derivation_table_names_only_lane_bs_essences():
    """Lane B moved the 18 essences into effectspec.ESSENCES; this file holds only the
    derivation, keyed on them. A row naming any other id would derive an essence no
    material can carry, and a formula keyed on it could never be made — refused, named."""
    table = formulae.essence_table()
    assert formulae.essence_table_problems(table) == []
    bad = copy.deepcopy(table)
    bad["descriptors"]["fire"] = "holy-fire"
    bad["condition_tags"].append(["state.held", "glue"])
    problems = formulae.essence_table_problems(bad)
    assert any("descriptors.fire" in p and "holy-fire" in p for p in problems)
    assert any("condition_tags" in p and "glue" in p for p in problems)


def test_a_spells_essences_are_read_from_its_descriptors_effects_and_school():
    """The Alchemy Manual keys reagents to spells by school, subschool and descriptor
    (salt: necromancy; quicksilver: mind-affecting); the derivation does the same, plus
    what the typed effects do. Measured without the secondary floor: the school's lone
    vote became every cure's second essence (vigour + change)."""
    assert formulae.spell_essences(spells.get("shocking-grasp")) == ["storm"]
    assert formulae.spell_essences(spells.get("inflict-light-wounds")) == ["decay"]
    assert formulae.spell_essences(spells.get("cure-light-wounds")) == ["vigour"]
    assert formulae.spell_essences(spells.get("bull-s-strength")) == ["might"]
    for sp in list(spells.all_spells().values())[:400]:
        got = formulae.spell_essences(sp)
        assert len(got) <= 2 and set(got) <= set(effectspec.ESSENCES)


# --- the authored table ----------------------------------------------------------------------

def test_every_authored_formula_has_its_own_signature():
    """The classics and the 44 are found by experiment (owner, open point 4), and
    experiment tells formulae apart by family + essences only. Under the derivation table
    cure light, moderate and serious wounds all read as vigour: three potions experiment
    could never tell apart. The validator refuses a shared signature, named."""
    rows = {fid: r for fid, r in formulae.all().items() if r["authored"]}
    seen = {}
    for fid, row in rows.items():
        for sig in formulae.row_signatures(row):
            assert sig not in seen, f"{fid} shares {sig} with {seen[sig]}"
            seen[sig] = fid
    clash = {k: copy.deepcopy(v) for k, v in rows.items()}
    clash["potion-of-cure-moderate-wounds"]["requires"] = {"essences": {"vigour": 1}}
    problems = formulae.table_problems(clash, awaiting=RAW["awaiting"])
    assert any("also potion-of-cure-light-wounds's" in p or
               "also potion-of-cure-moderate-wounds's" in p for p in problems)


def test_the_classics_and_the_44_are_formulae_and_keep_their_ids():
    """Owner Q10.2: every potion id and holds_spell kept exactly — the enchanter consumes
    an old potion as its spell (tests/test_magicitem.py:207). Every shipped potion is a
    formula under its own id, with its own spell, spell level and caster level."""
    rows = formulae.all()
    for pot in POTIONS:
        row = rows[pot["id"]]
        assert row["authored"] and row["kind"] == "spell"
        assert row["spell"] == pot["spell"]
        assert row["spell_level"] == pot["spell_level"]
        assert row["caster_level"] == pot["caster_level"]
        assert formulae.for_spell(pot["spell"])["id"] == pot["id"]
    classics = {fid for fid, r in rows.items() if r["kind"] == "classic"}
    assert {"acid-flask", "alchemists-fire", "antitoxin", "tanglefoot-bag", "sunrod",
            "smokestick", "thunderstone", "tindertwig"} <= classics
    assert set(formulae.starting()) == {"alchemists-fire", "acid-flask", "antitoxin",
                                        "tanglefoot-bag"}
    assert len([r for r in RAW["potions"]]) == len(POTIONS) == 44


def test_the_book_classics_carry_the_books_numbers():
    """Q1.4, the book wins. Measured on the catalogue: alchemist's fire dealt 2d6 at once
    with no attack and no next round; antitoxin was two non-stacking +1s, so +1; the
    sunrod was a blade coating dealing 1d4 fire; the smokestick was drinkable."""
    def core(fid):
        return formulae.get(fid)["core"]

    fire = core("alchemists-fire")
    assert {(c["type"], c.get("dice"), c.get("damage_type")) for c in fire} == {
        ("damage", "1d6", "fire"), ("burning", "1d6", "fire")}
    burn = next(c for c in fire if c["type"] == "burning")
    assert (burn["rounds"], burn["save"], burn["dc"], burn["smother_bonus"]) == (1, "ref", 15, 2)
    assert formulae.get("alchemists-fire")["splash"] == {"amount": 1, "damage_type": "fire"}
    assert [(c["type"], c["dice"], c["damage_type"]) for c in core("acid-flask")] == [
        ("damage", "1d6", "acid")]
    tox = core("antitoxin")[0]
    assert (tox["type"], tox["amount"], tox["bonus_type"], tox["target"], tox["when"],
            tox["duration"]) == ("save_mod", 5, "alchemical", "fort", {"against": "poison"},
                                 {"amount": 1, "unit": "hour"})
    tangle = core("tanglefoot-bag")
    assert tangle[0]["target"] == "entangled"
    assert (tangle[1]["target"], tangle[1]["dc"]) == ("ref", 15)
    assert tangle[1]["on_failure"][0]["target"] == "glued"
    sun = core("sunrod")[0]
    assert (sun["type"], sun["radius_ft"], sun["raised_ft"], sun["duration"]) == (
        "light", 30, 60, {"amount": 6, "unit": "hour"})
    smoke = core("smokestick")[0]
    assert (smoke["type"], smoke["terrain"], smoke["size"]) == ("manifest", "obscuring", 10)
    thunder = core("thunderstone")[0]
    assert (thunder["target"], thunder["dc"], thunder["on_failure"][0]["target"]) == (
        "fort", 15, "deafened")
    # The CRB's Craft DCs and prices (prior art §1.1, cross-checked with Unchained).
    book = {"acid-flask": (15, 10), "alchemists-fire": (20, 20), "smokestick": (20, 20),
            "tindertwig": (20, 1), "antitoxin": (25, 50), "sunrod": (25, 2),
            "tanglefoot-bag": (25, 50), "thunderstone": (25, 30)}
    for fid, (dc, price) in book.items():
        row = formulae.get(fid)
        assert (row["craft_dc"], row["price_gp"]) == (dc, price), fid


def test_a_core_is_never_narrative():
    """The cross-craft rule: no narrative effects. A core written as words is refused
    with the fix named; a condition the engine lane adds this wave (glued) is allowed and
    named in `waiting`, so nothing pretends. Once that reader landed (lane C, 2026-10-06)
    the `awaiting` note came off and glued is an ordinary condition: the tanglefoot bag
    waits on nothing."""
    problems = formulae.core_problems([{"type": "narrative", "target": "it glows"}], "core")
    assert problems and "narrative" in problems[0]
    assert formulae.core_problems([], "core")
    assert formulae.core_problems(
        [{"type": "apply_condition", "target": "glued"}], "core") == []
    assert not any("glued" in w for w in formulae.get("tanglefoot-bag")["waiting"])


def test_a_potion_still_written_in_words_is_not_brewed():
    """Plan §11.2: until a shipped potion is fully typed, old stock stays usable but no
    new one is brewed. A potion carrying a narrative line is not brewable; the bench
    refuses it in words, never silently."""
    pc = _pc(6)
    for row in formulae.all().values():
        if not row["authored"] or row["kind"] != "spell":
            continue
        prose = any(s.get("type") == "narrative" for s in formulae._walk(row["core"]))
        assert row["brewable"] is (not prose), row["id"]
    unbrewable = next((r for r in formulae.all().values() if not r["brewable"]), None)
    if unbrewable is not None:
        formulae.learn(pc, unbrewable["id"], "teacher")
        got = formulae.match(pc, _mix(*((e, 3) for e in unbrewable["requires"]["essences"])),
                             unbrewable["family"], unbrewable["id"])
        assert got["formula"] is None
        assert any("written as words" in r for r in got["refused"])


# --- the owner's spell rule ------------------------------------------------------------------

@pytest.mark.parametrize("level,cap", [(1, 1), (2, 1), (3, 1), (4, 2), (5, 2), (17, 8),
                                       (18, 9)])
def test_the_spell_level_cap_is_half_the_alchemist_level_minimum_one(level, cap):
    """Owner Q4.3: "the max spell level should be 1/2 alchemy level with a minimum of 1"."""
    assert formulae.spell_level_cap(level) == cap


def test_a_first_level_potion_is_in_reach_at_alchemist_one():
    """Contracts §5 wrote a derived row's level as max(1, 2n): 2 for a 1st-level spell,
    which the owner's cap opens at Alchemist 1 (Q6.1: 1st-level potions at level 1)."""
    assert [formulae.level_for_spell_level(n) for n in (0, 1, 2, 3, 9)] == [1, 1, 4, 6, 18]
    row = formulae.get("potion-of-burning-hands")
    assert row["level"] == 1 and formulae.within_reach(row, 1)
    haste = formulae.get("potion-of-haste")
    assert not formulae.within_reach(haste, 5)
    assert any("Alchemist 6" in w for w in formulae.reach_problems(haste, 5))
    assert formulae.within_reach(haste, 6)


def test_caster_level_is_the_book_minimum_plus_one_per_tier_above_sound():
    """Owner Q6.4: each tier above Sound adds +1 caster level; Crude stays at the minimum
    ("never lower than the minimum level needed to cast the needed spell", CRB)."""
    assert [formulae.caster_level("cure-light-wounds", q) for q in (0, 1, 2, 3, 4, 5)] == [
        1, 1, 2, 3, 4, 5]
    assert formulae.caster_level("haste", 1) == 5          # authored: CL 5, the book's
    assert formulae.min_caster_level("fireball") == 5      # wizard 3rd at 5th
    bard_only = SimpleNamespace(id="x", lists={"bard": 2}, min_level=2)
    assert formulae.min_caster_level(bard_only) == 4       # a bard casts 2nd at 4th
    paladin_only = SimpleNamespace(id="x", lists={"paladin": 1}, min_level=1)
    assert formulae.min_caster_level(paladin_only) == 1    # paladin 4th, CL = level - 3
    summoner_only = SimpleNamespace(id="x", lists={"summoner": 2}, min_level=2)
    assert formulae.min_caster_level(summoner_only) == 3   # no class document: 2n - 1
    cantrip = SimpleNamespace(id="x", lists={"wizard": 0}, min_level=0)
    assert formulae.min_caster_level(cantrip) == 1


def test_a_potions_price_is_fifty_times_spell_level_times_caster_level():
    """A potion of haste sold for 60 gp against the book's 750 (inv §0.4). The CRB:
    "the level of the spell x the creator's caster level x 50 gp", a cantrip half a
    level. Quality reaches the price only through caster level (open point 6)."""
    assert formulae.potion_price(3, 5) == 750
    assert formulae.get("potion-of-haste")["price_gp"] == 750
    assert formulae.potion_price(1, 1) == 50
    assert formulae.potion_price(0, 1) == 25
    assert formulae.potion_price(2, 3) == 300
    crude = formulae.potion_price(1, formulae.caster_level("cure-light-wounds", 0))
    fine = formulae.potion_price(1, formulae.caster_level("cure-light-wounds", 2))
    assert (crude, fine) == (50, 100)


def test_brew_time_follows_the_brew_potion_feat():
    """CRB, Brew Potion: 2 hours at 250 gp or less, else 1 day per 1,000 gp (started
    thousands: the creation section's "or fraction thereof")."""
    assert formulae.brew_minutes(50) == 120
    assert formulae.brew_minutes(250) == 120
    assert formulae.brew_minutes(750) == 1440
    assert formulae.brew_minutes(1500) == 2880
    assert formulae.get("potion-of-haste")["brew_minutes"] == 1440


# --- derived rows ----------------------------------------------------------------------------

def test_a_derived_formula_exists_only_for_a_spell_whose_effects_all_execute():
    """Measured: 783 corpus spells pass `executable` at the top level, but 347 of them
    carry prose inside a save gate's branch (baleful polymorph's failure is a paragraph).
    A derived potion of one would do nothing on a failed save, so the whole tree must run;
    and an authored potion's spell gets no second, derived row."""
    rows = formulae.all()
    derived = [r for r in rows.values() if r["derived"]]
    assert derived
    for row in derived:
        sp = spells.get(row["spell"])
        assert all(effectspec.executable(s) for s in formulae._walk(sp.effects)), row["id"]
    assert "potion-of-baleful-polymorph" not in rows
    assert not any(r["derived"] and r["spell"] == "restoration-lesser" for r in derived)


def test_a_harmful_spell_yields_a_thrown_flask_and_says_who_it_takes():
    """Owner, open point 5: drunk, the drinker is the target; it may also go into a
    thrown flask, the struck creature the target. The row names its forms."""
    row = formulae.get("potion-of-burning-hands")
    assert row["harmful"] and row["families"] == ["potion", "splash"]
    assert row["delivers"] == {"potion": "the drinker", "splash": "the creature it strikes"}
    mage = formulae.get("potion-of-mage-armor")
    assert mage["families"] == ["potion"] and not mage["harmful"]


# --- matching and the count ------------------------------------------------------------------

def _row(fid, essences, *, family="potion", families=None, authored=False, spell_level=1,
         level=None, tier="common"):
    fams = families or [family]
    return {"id": fid, "name": fid.title(), "kind": "spell", "authored": authored,
            "derived": not authored, "brewable": True, "family": family, "families": fams,
            "requires": {"essences": dict(essences)}, "spell_level": spell_level,
            "level": level or formulae.level_for_spell_level(spell_level), "tier": tier,
            "core": [], "delivers": {}, "shadowed": [], "waiting": []}


@pytest.fixture
def table(monkeypatch):
    """A small fixed table, so the hand counts below cannot drift as the corpus is typed.
    Classic-like authored rows A (fire) and B (fire + ward); derived C and D share
    potion {mind}; E is a 3rd-level derived {sight}; F a derived row shadowed by A."""
    rows = {
        "a": _row("a", {"fire": 1}, family="splash", authored=True),
        "b": _row("b", {"fire": 1, "ward": 2}, authored=True),
        "c": _row("c", {"mind": 1}),
        "d": _row("d", {"mind": 1}, spell_level=2),
        "e": _row("e", {"sight": 1}, spell_level=3),
        "f": _row("f", {"fire": 1}, family="potion", families=["potion", "splash"]),
    }
    rows["f"]["shadowed"] = ["splash"]
    monkeypatch.setattr(formulae, "_rows", lambda: rows)
    return rows


def test_the_possible_formulae_count_equals_a_hand_count(table):
    """Owner Q5.3: a count, never names. Hand counts on three fixed mixes:
    - fire, no vessel, Alchemist 1: a, b, f (every row requiring fire; d and e out of
      reach by spell level) = 3;
    - fire in a potion vessel, Alchemist 1: b, f = 2;
    - mind, Alchemist 4: c, d = 2 (d's 2nd level opens at 4); at Alchemist 1, c alone."""
    pc = _pc(1)
    assert formulae.could_become(pc, _mix(("fire", 1)))["count"] == 3
    assert formulae.could_become(pc, _mix(("fire", 1)), "potion")["count"] == 2
    assert formulae.could_become(pc, _mix(("mind", 1)))["count"] == 1
    assert formulae.could_become(_pc(4), _mix(("mind", 1)))["count"] == 2


def test_the_count_names_only_formulae_the_player_knows(table):
    pc = _pc(1)
    formulae.learn(pc, "a", "experiment")
    got = formulae.could_become(pc, _mix(("fire", 1)))
    assert got["known"] == ["a"]
    assert "You know 1 of them: A" in got["line"]
    assert "B" not in got["line"] and "F" not in got["line"]


def test_an_authored_formula_wins_its_signature(table):
    """Plan §10.2: a mix that matches an authored row exactly is that row, whatever
    derived rows share it — f's splash form is never found by experiment."""
    got = formulae.match(_pc(1), _mix(("fire", 1)), "splash")
    assert (got["formula"], got["found"], got["experiment"], got["new"]) == ("a", True, True,
                                                                              True)
    assert formulae.findable_by_experiment("f", 18) == ["potion"]


def test_experiment_finds_a_derived_formula_only_while_it_is_unique_within_reach(table):
    """Plan §10.3, contracts §5: a derived row is found by experiment only when its
    signature is unique within the actor's reach; otherwise it is counted, not named."""
    first = formulae.match(_pc(1), _mix(("mind", 1)), "potion")
    assert (first["formula"], first["found"]) == ("c", True)
    later = formulae.match(_pc(4), _mix(("mind", 1)), "potion")
    assert (later["formula"], later["ambiguous"]) == (None, 2)
    assert formulae.findable_by_experiment("c", 1) == ["potion"]
    assert formulae.findable_by_experiment("c", 4) == []


def test_experiment_needs_the_grades_but_never_says_what_is_short(table):
    weak = formulae.match(_pc(1), _mix(("fire", 1), ("ward", 1)), "potion")
    assert weak["formula"] is None and weak["weak"] == 1 and weak["missing"] == []
    strong = formulae.match(_pc(1), _mix(("fire", 1), ("ward", 2)), "potion")
    assert strong["formula"] == "b"


def test_a_chosen_formula_says_what_the_mix_lacks_in_words(table):
    """Plan §10.2: "needs lightness at grade 2; you have grade 1"."""
    pc = _pc(1)
    formulae.learn(pc, "b", "teacher")
    got = formulae.match(pc, _mix(("fire", 1), ("ward", 1), ("mind", 1)), "potion", "b")
    assert got["formula"] is None
    assert got["missing"] == ["needs ward at grade 2; you have 1"]
    got = formulae.match(pc, _mix(("ward", 2)), "potion", "b")
    assert got["missing"] == ["needs fire; nothing in the mix carries it"]
    ok = formulae.match(pc, _mix(("fire", 1), ("ward", 2), ("mind", 1)), "potion", "b")
    assert ok["formula"] == "b" and ok["missing"] == [] and ok["refused"] == []


def test_a_chosen_formula_must_be_known_in_reach_and_in_its_vessel(table):
    pc = _pc(1)
    got = formulae.match(pc, _mix(("fire", 1), ("ward", 2)), "potion", "b")
    assert any("do not know" in r for r in got["refused"])
    formulae.learn(pc, "b", "teacher")
    got = formulae.match(pc, _mix(("fire", 1), ("ward", 2)), "splash", "b")
    assert any("is a potion" in r for r in got["refused"])
    formulae.learn(pc, "e", "teacher")
    got = formulae.match(pc, _mix(("sight", 1)), "potion", "e")
    assert any("Alchemist 6" in r for r in got["refused"])


def test_the_real_table_finds_the_classics_by_experiment():
    """The classics and the 44 are always found by experiment (open point 4). Real
    table: fire in a flask is alchemist's fire, fire on a stick a tindertwig, vigour in a
    vial the shipped cure light wounds — even though derived vigour potions exist."""
    pc = _pc(1)
    assert formulae.match(pc, _mix(("fire", 1)), "splash")["formula"] == "alchemists-fire"
    assert formulae.match(pc, _mix(("fire", 1)), "tool")["formula"] == "tindertwig"
    assert formulae.match(_pc(18), _mix(("vigour", 1)), "potion")["formula"] == \
        "potion-of-cure-light-wounds"
    for row in formulae.all().values():
        if row["authored"] and row["brewable"]:
            level = max(row["level"], formulae.level_for_spell_level(row.get("spell_level") or 0))
            assert formulae.findable_by_experiment(row["id"], level), row["id"]


def test_a_vessel_decides_the_family():
    """Owner Q7.3: the vessel decides. A family name stands for any vessel of it; a
    vessel document is read for its vessel traits, and one with none is refused in words
    rather than guessed (the old bench inferred drink, throw or coat, which is how the
    sunrod became a blade coating)."""
    assert formulae.vessel_families("splash") == ("splash",)
    doc = materials.alchemy_doc("glass-vial") or {}
    traits = {str(w.get("trait")) for w in doc.get("working") or () if isinstance(w, dict)}
    if "drinkable" in traits:
        assert formulae.vessel_families("glass-vial") == ("potion", "oil")
    got = formulae.match(_pc(1), _mix(("fire", 1)), "brimstone")
    assert got["formula"] is None and got["refused"]


# --- learning --------------------------------------------------------------------------------

def test_learning_writes_the_one_store_with_how_and_the_day():
    """Contracts §4: one store, "formula:<id>" in herb_known, never a second list."""
    pc = _pc(1)
    assert formulae.learn(pc, "alchemists-fire", "experiment", clock=13 * 1440 + 5)
    assert not formulae.learn(pc, "alchemists-fire", "experiment", clock=20 * 1440)
    assert knowledge.formula_how(pc, "alchemists-fire") == "found by experiment, day 14"
    assert formulae.known(pc) == ["alchemists-fire"]
    assert not formulae.learn(pc, "no-such-formula", "teacher")
    assert "formula:no-such-formula" not in pc.herb_known


def test_a_new_alchemist_knows_the_four_classics():
    pc = _pc(1)
    assert sorted(formulae.grant_starting(pc)) == sorted(
        ["alchemists-fire", "acid-flask", "antitoxin", "tanglefoot-bag"])
    assert knowledge.formula_how(pc, "antitoxin") == "known from the start"


def test_copying_from_a_scroll_is_the_wizards_rule():
    """CRB, Arcane Magical Writings: DC 15 + spell level, the writing cost, 1 hour of
    study plus 1 hour a level; the scroll is used up on success; a failure keeps it and
    bars that formula for a week."""
    pc = _pc(6)
    plan = formulae.learn_route(pc, "potion-of-haste", "scroll", clock=0)
    assert (plan["dc"], plan["cost_gp"], plan["minutes"], plan["spends"]) == (18, 90, 240,
                                                                           "on_success")
    fail = formulae.resolve_learn(pc, "potion-of-haste", "scroll", 17, clock=100)
    assert (fail["success"], fail["learned"], fail["spent"]) == (False, False, False)
    barred = formulae.learn_route(pc, "potion-of-haste", "scroll", clock=200)
    assert any("again on day 8" in r for r in barred["refused"])
    week = formulae.learn_route(pc, "potion-of-haste", "scroll", clock=100 + 7 * 1440)
    assert week["refused"] == []
    ok = formulae.resolve_learn(pc, "potion-of-haste", "spellbook", 18, clock=100 + 7 * 1440)
    assert (ok["success"], ok["learned"], ok["spent"]) == (True, True, False)


def test_a_potion_in_hand_teaches_its_formula_and_is_spent():
    """Owner, open point 9: spend the potion to learn its formula, DC 15 + spell level.
    It is broken down to be read, so it is spent whatever the roll."""
    pc = _pc(1)
    stock = SimpleNamespace(holds_spell="cure-light-wounds", formula=None)
    fid = formulae.potion_formula(stock)
    assert fid == "potion-of-cure-light-wounds"
    miss = formulae.resolve_learn(pc, fid, "potion", 10)
    assert (miss["dc"], miss["success"], miss["spent"], miss["learned"]) == (16, False, True,
                                                                              False)
    hit = formulae.resolve_learn(pc, fid, "potion", 16)
    assert (hit["success"], hit["spent"], hit["learned"]) == (True, True, True)
    assert knowledge.formula_how(pc, fid) == "learned from a potion"
    classic = formulae.learn_route(pc, "acid-flask", "potion")
    assert any("holds no spell" in r for r in classic["refused"])


# --- the old recipes still make their potions ------------------------------------------------

def _benefit_essences(mid: str) -> set[str]:
    doc = materials.alchemy_doc(mid)
    return {str(t["essence"]) for t in materials.product_traits(doc)
            if t.get("essence") and not t.get("drawback")}


def test_every_old_potion_recipe_still_satisfies_its_formula():
    """Plan §10.1: the 44's exact material sets become essence requirements their old
    materials still satisfy, so every old recipe still makes its potion. The essences on
    the materials are lane D's data pass; until it lands no material carries one, and
    this test waits rather than passing on nothing."""
    shelf = materials.alchemy_shelf()
    if not any(t.get("essence") for d in shelf.values() for t in materials.product_traits(d)):
        pytest.skip("no alchemy material carries an essence yet (lane D's data pass)")
    short = []
    for pot in POTIONS:
        have = set().union(*(_benefit_essences(m) for m in pot["materials"]))
        need = set(formulae.get(pot["id"])["requires"]["essences"])
        if not need <= have:
            short.append(f"{pot['id']}: needs {sorted(need - have)} from {pot['materials']}")
    assert short == []
