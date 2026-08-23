"""What has to happen to an ingredient before it is any use.

The bench could brew but treated everything as equally ready: a shelled nut, a volatile
resin and a handful of leaves all went into the pot the same way. These are the author's
rules, each test naming the sentence it protects.
"""
from __future__ import annotations

import pytest

from rules import herbprep as H


def prep(**over):
    return H.Prep(**over)


# --- the order the steps come in ---------------------------------------------------------

def test_nothing_can_be_done_to_a_thing_still_in_its_shell():
    """"What herbs need extracting (pulling it out of a shell etc..) before they can be
    ground or mixed or brewed"."""
    nut = prep(needs_extraction=True)
    for step in ("grind", "mix", "brew", "neutralise"):
        ok, why = H.can(step, nut, "raw")
        assert not ok and "extracted" in why, step
    assert H.can("extract", nut, "raw")[0]


def test_extracting_something_that_has_no_shell_is_refused():
    ok, why = H.can("extract", prep(), "raw")
    assert not ok and "nothing to extract" in why


def test_a_volatile_herb_must_be_neutralised_before_grinding():
    """"what herb are volatile and need neutralized before they can be ground"."""
    resin = prep(volatile=True)
    ok, why = H.can("grind", resin, "raw")
    assert not ok and "neutralise it before grinding" in why
    assert H.can("neutralise", resin, "raw")[0]
    assert H.can("grind", resin, "neutralised")[0]


def test_neutralising_something_stable_is_refused():
    ok, why = H.can("neutralise", prep(), "raw")
    assert not ok and "not volatile" in why


def test_the_whole_chain_for_the_worst_case():
    """A shelled, volatile herb that cannot be brewed raw: extract, neutralise, grind,
    and only then does the pot accept it."""
    worst = prep(needs_extraction=True, volatile=True, brew_raw=False)
    state = "raw"
    for step in ("extract", "neutralise", "grind"):
        assert H.can(step, worst, state)[0], (step, state)
        state = H.after(step, state)
    assert state == "ground"
    assert H.can("brew", worst, "ground")[0]


# --- what can be mixed and brewed raw ----------------------------------------------------

def test_an_ordinary_herb_mixes_and_brews_raw():
    assert H.can("mix", prep(), "raw")[0]
    assert H.can("brew", prep(), "raw")[0]


def test_one_that_cannot_says_to_grind_it_first():
    """"what herbs can be mixed raw vs only when ground", and the same for brewing.
    The refusal is the rule: a player who reads it once knows it thereafter."""
    ok, why = H.can("mix", prep(mix_raw=False), "raw")
    assert not ok and "once it has been ground" in why
    assert H.can("mix", prep(mix_raw=False), "ground")[0]

    ok, why = H.can("brew", prep(brew_raw=False), "raw")
    assert not ok and "once it has been ground" in why
    assert H.can("brew", prep(brew_raw=False), "ground")[0]


def test_a_herb_that_cannot_be_ground_at_all():
    ok, why = H.can("grind", prep(can_grind=False), "raw")
    assert not ok and "cannot be ground" in why


# --- potency -----------------------------------------------------------------------------

def test_grinding_and_brewing_both_raise_potency():
    """"grinding and brewing should both increase potency"."""
    assert H.potency_change("grind") > 0
    assert H.potency_change("brew") > 0


def test_the_increase_goes_up_with_the_herbalist():
    """"the increases in potency should go up with herbalist lvl" — a master gets more
    out of the same leaf, which is what levelling a craft is for."""
    novice = H.potency_change("grind", 0)
    master = H.potency_change("grind", 10)
    assert master > novice
    assert H.potency_change("brew", 5) > H.potency_change("brew", 1)


def test_preserving_costs_potency():
    """"preservation should lower potency" — the price of not losing the material."""
    assert H.potency_change("preserve") < 0


def test_a_step_that_does_nothing_to_potency_says_zero():
    assert H.potency_change("extract") == 0
    assert H.potency_change("neutralise") == 0


# --- the clock ---------------------------------------------------------------------------

def test_animal_parts_have_two_days_and_plants_a_week():
    """"all animal parts need preserved within 48 hours for they become garbage and
    fresh herbs last a week"."""
    assert H.spoils_after(prep(animal=True)) == 48
    assert H.spoils_after(prep()) == 24 * 7


def test_a_gland_left_two_days_is_refuse():
    gland = prep(animal=True)
    assert not H.is_spoiled(gland, 47)
    assert H.is_spoiled(gland, 48)


def test_a_leaf_keeps_a_week_and_not_a_day_longer():
    leaf = prep()
    assert not H.is_spoiled(leaf, 167)
    assert H.is_spoiled(leaf, 168)


def test_preserved_material_does_not_spoil_at_all():
    assert not H.is_spoiled(prep(animal=True), 10_000, preserved=True)


def test_a_monster_part_is_an_animal_part_without_being_told():
    """The 161 already authored say nothing about any of this. A monster part is on
    the shorter clock because of what it is, not because somebody remembered to tick a
    box that did not exist when it was written."""
    assert H.Prep.of({"kind": "monster part"}).animal
    assert not H.Prep.of({"kind": "herb"}).animal


def test_everything_already_authored_behaves_exactly_as_it_did():
    """Every default is the old behaviour: grind it, mix it, brew it, keep it a week."""
    plain = H.Prep.of({"kind": "herb", "name": "Leechwort"})
    assert plain == H.Prep()
    for step in ("grind", "mix", "brew"):
        assert H.can(step, plain, "raw")[0], step


def test_flags_read_from_yes_and_no_as_well_as_booleans():
    """The editor stores choices as strings, and the loader must not care."""
    got = H.Prep.of({"kind": "herb", "volatile": "yes", "brew_raw": "no"})
    assert got.volatile and not got.brew_raw


# --- infusions ---------------------------------------------------------------------------

def test_an_infusion_needs_a_crafted_tincture_to_go_into():
    """"Infusions are only possible on already crafted tinctures"."""
    ok, why = H.can_infuse({"kind": "herb"}, {"kind": "herb"})
    assert not ok and "already been crafted" in why
    assert H.can_infuse({"kind": "tincture", "crafted": True}, {"kind": "herb"})[0]


def test_a_raw_herb_may_be_infused_only_if_it_could_be_brewed_raw():
    """"raw herbs as long as the raw herbs could be brewed raw"."""
    base = {"kind": "tincture", "crafted": True}
    assert H.can_infuse(base, {"brew_raw": True}, "raw")[0]
    ok, why = H.can_infuse(base, {"brew_raw": False}, "raw")
    assert not ok and "brewed raw" in why


def test_grinding_it_first_makes_it_infusable_anyway():
    base = {"kind": "tincture", "crafted": True}
    assert H.can_infuse(base, {"brew_raw": False}, "ground")[0]


def test_a_volatile_herb_still_has_to_come_out_of_its_shell():
    """"some herbs that are volitile need extraction"."""
    base = {"kind": "tincture", "crafted": True}
    ok, why = H.can_infuse(base, {"needs_extraction": True, "volatile": True}, "raw")
    assert not ok and "extracted" in why


# --- and it reaches the ingredient editor ------------------------------------------------

def test_the_ingredient_form_offers_every_preparation_rule():
    """Modular was the ask: the bench draws every editor from the registry, so a new
    rule is one Field and appears in the UI without a line of template changing."""
    from rules import registry

    fields = {f.name for f in registry.KINDS["ingredients"].fields}
    assert {"needs_extraction", "volatile", "can_grind", "mix_raw", "brew_raw",
            "animal"} <= fields


def test_every_new_field_explains_itself_or_is_obvious():
    from rules import registry

    for f in registry.KINDS["ingredients"].fields:
        if f.name in ("volatile", "mix_raw", "brew_raw", "needs_extraction", "animal"):
            assert f.help, f.name


# --- salt (asked for 2026-08-23) ---------------------------------------------------------

class Carrier:
    def __init__(self, **goods):
        self.goods = goods
        self.inventory = {}


def test_carrying_salt_preserves_it_without_being_asked():
    """"preservation can be automatic if i have salt" — so it does not depend on the
    player remembering on the turn they pick a gland up, which is the turn they are
    least likely to be thinking about the 48 hours that start now."""
    gland = H.Prep(animal=True)
    ok, cost, why = H.preserve_automatically(Carrier(**{"rock salt": 2}), gland)
    assert ok and cost < 0 and "salt" in why


def test_without_salt_it_says_how_long_there_is():
    ok, cost, why = H.preserve_automatically(Carrier(rope=50), H.Prep(animal=True))
    assert not ok and cost == 0
    assert "48 hours" in why


def test_salt_is_recognised_by_the_name_a_player_would_buy():
    for name in ("salt", "Sea Salt", "a pouch of curing salt"):
        assert H.has_salt(Carrier(**{name: 1})), name
    assert not H.has_salt(Carrier(lantern=1))


# --- the tags actually survive the trip in (found by applying them, 2026-08-23) ------

def test_the_ingredient_dataclass_has_somewhere_to_put_them():
    """55 ingredients were tagged, the file merged correctly, and every one still read
    as an ordinary leaf: `from_dict` builds a dataclass and quietly drops anything it
    has no field for. The flags were nowhere on `Ingredient`, so they vanished on the
    way in with nothing raised and nothing logged."""
    from rules.ingredients import Ingredient

    fields = set(Ingredient.__dataclass_fields__)
    assert {"needs_extraction", "volatile", "can_grind", "mix_raw", "brew_raw",
            "animal"} <= fields


def test_a_flag_stored_as_the_word_no_is_not_true():
    """The editor stores choices as "yes"/"no" and the importer writes the same. A
    plain `bool("no")` is True, which would turn "cannot be ground" into its
    opposite — the worst direction for a rule about volatile things to fail in."""
    from rules.ingredients import from_dict

    got = from_dict({"id": "x", "name": "X", "can_grind": "no", "volatile": "yes"})
    assert got.can_grind is False and got.volatile is True


def test_a_monster_part_is_animal_unless_the_entry_says_otherwise():
    from rules.ingredients import from_dict

    assert from_dict({"id": "a", "name": "A", "kind": "monster part"}).animal
    assert not from_dict({"id": "b", "name": "B", "kind": "herb"}).animal
    # And an explicit answer wins, which is how a plant growing on a creature is told
    # apart from the creature.
    assert from_dict({"id": "c", "name": "C", "kind": "monster part",
                      "animal": "no"}).animal is False


def test_the_shipped_corpus_is_untouched_by_tagging():
    """The tags land in the homebrew overlay. Deleting one file undoes all of it, and
    a corrected corpus in a later build is not shadowed by a stale copy."""
    import json
    from pathlib import Path

    corpus = json.loads(
        Path("content/ingredients/herbs-and-parts.json").read_text(encoding="utf-8"))
    entries = corpus.get("ingredients", corpus)
    assert not any("volatile" in e for e in entries), \
        "preparation flags belong in the overlay, not in the shipped file"


# --- and the bench enforces it (2026-08-23) ------------------------------------------

class FakeHerb:
    """An ingredient with flags chosen by the test rather than by the corpus.

    The tagged flags live in the *homebrew overlay*, in the player's own data
    directory — so a test that reached for "Hydra Gall is volatile" would be asserting
    something about whoever ran it. It passed on this machine and would fail on a fresh
    clone, which is the worst kind of green.
    """
    def __init__(self, name, **flags):
        self.id = name.lower().replace(" ", "-")
        self.name = name
        self.kind = flags.pop("kind", "herb")
        self.tier = "common"
        self.rank = 1
        self.risky = False
        self.effects = []
        self.text = ""
        for k, v in flags.items():
            setattr(self, k, v)


def _problems(methods, *herbs):
    from rules.crafting import _preparation_problems

    return _preparation_problems(list(herbs), methods)


def test_a_shelled_herb_cannot_simply_be_ground():
    """The pot has to be told to open it first, and the refusal names the ingredient
    and the rule rather than only saying no."""
    got = _problems(["grind"], FakeHerb("Hydra Gall", needs_extraction=True))
    assert any("Hydra Gall" in p and "extracted" in p for p in got)


def test_extracting_first_makes_the_same_chain_legal():
    """The state is carried through the chain, which is the whole point: checking each
    step against the raw ingredient would refuse a chain that extracts and then works."""
    assert _problems(["extract", "brew"],
                     FakeHerb("Hydra Gall", needs_extraction=True)) == []


def test_a_volatile_herb_will_not_be_ground_until_it_is_neutralised():
    volatile = FakeHerb("Henbane", volatile=True)
    got = _problems(["grind"], volatile)
    assert any("Henbane" in p and "neutralise" in p for p in got)
    assert _problems(["neutralize", "grind"], volatile) == []


def test_a_step_an_ingredient_has_no_use_for_is_not_an_error():
    """Neutralising a pot of eight herbs because one is volatile is the point; the
    other seven are not spoiled by sitting through it."""
    got = _problems(["neutralize", "brew"],
                    FakeHerb("Henbane", volatile=True), FakeHerb("Acacia"))
    assert got == []


def test_only_the_ingredient_at_fault_is_named():
    got = _problems(["grind"], FakeHerb("Acacia"),
                    FakeHerb("Hydra Gall", needs_extraction=True))
    assert any("Hydra Gall" in p for p in got)
    assert not any("Acacia" in p for p in got)


def test_one_that_cannot_be_brewed_raw_is_refused_until_it_is_ground():
    dry = FakeHerb("Coldwood", brew_raw=False)
    assert any("ground" in p for p in _problems(["brew"], dry))
    assert _problems(["grind", "brew"], dry) == []


def test_grinding_and_brewing_pay_more_in_better_hands():
    """The per-level term reaches the bench: the same chain is worth more to a master.
    `herbprep` holds the numbers so the two cannot disagree about what a grind is."""
    from rules import crafting

    def potency(level):
        return crafting.preview(
            "herbalist", level,
            crafting.Chain(track="herbalist", methods=["brew"],
                           ingredient_ids=["acacia"]),
            satchel={"acacia": 9}).potency

    assert potency(5) > potency(1) > 1.0


def test_spoiled_material_is_refused_rather_than_quietly_weakened():
    """"all animal parts need preserved within 48 hours for they become garbage" —
    and garbage in a pot is not a worse potion, it is not a potion."""
    from rules import crafting
    from rules.sheet import load_pc

    pc = load_pc("fixtures/pc-kesst.json")
    pc.carry("wyrmfang-venom", 3, at_minute=0)
    got = crafting.preview(
        "herbalist", 3,
        crafting.Chain(track="herbalist", methods=["brew"],
                       ingredient_ids=["wyrmfang-venom"]),
        satchel=dict(pc.inventory), carrier=pc, now_minute=49 * 60)
    assert any("spoiled" in p for p in got.problems), got.problems


def test_salt_carried_at_the_time_keeps_it():
    from rules import crafting
    from rules.sheet import load_pc

    pc = load_pc("fixtures/pc-kesst.json")
    pc.goods["rock salt"] = 1
    pc.carry("wyrmfang-venom", 3, at_minute=0)      # salted on the way in
    got = crafting.preview(
        "herbalist", 3,
        crafting.Chain(track="herbalist", methods=["brew"],
                       ingredient_ids=["wyrmfang-venom"]),
        satchel=dict(pc.inventory), carrier=pc, now_minute=1000 * 60)
    assert not any("spoiled" in p for p in got.problems), got.problems


def test_a_plant_keeps_a_week_where_a_gland_keeps_two_days():
    from rules.sheet import load_pc

    pc = load_pc("fixtures/pc-kesst.json")
    pc.carry("acacia", 1, at_minute=0)
    pc.carry("wyrmfang-venom", 1, at_minute=0)
    from rules import ingredients as ing

    e = ing.all_ingredients()
    at_three_days = 72 * 60
    assert pc.freshness("acacia", at_three_days, H.Prep.of(e["acacia"]))[0] is False
    assert pc.freshness("wyrmfang-venom", at_three_days,
                        H.Prep.of(e["wyrmfang-venom"]))[0] is True


def test_material_carried_before_the_clock_existed_is_treated_as_fresh():
    """A save that retroactively spoiled somebody's satchel would be a worse answer
    than a lenient one."""
    from rules.sheet import load_pc

    pc = load_pc("fixtures/pc-kesst.json")
    pc.inventory["wyrmfang-venom"] = 2          # no timestamp, as an old save has none
    spoiled, _ = pc.freshness("wyrmfang-venom", 9999 * 60, H.Prep(animal=True))
    assert spoiled is False


# --- infusion is the only way to combine a tincture (2026-08-23) ----------------------

def _pot(methods, stock_names=(), raw=(), level=5):
    """A chain over named jars and raw ingredients, without touching the corpus."""
    from rules import crafting

    stock = {}
    for name in stock_names:
        s = crafting.Stock(base=name, tier="common", count=9)
        stock[s.id] = s
    chain = crafting.Chain(track="herbalist", methods=list(methods),
                           ingredient_ids=list(raw),
                           stock_used={sid: 1 for sid in stock})
    return crafting.preview("herbalist", level, chain, stock=stock,
                            satchel={i: 9 for i in raw})


def test_a_tincture_alone_can_still_be_distilled():
    """"you can solo distill and concentrate" — the rule is about combining, and a
    tincture worked on its own is not combined with anything."""
    got = _pot(["distill"], stock_names=["Mad Cap Tincture"])
    assert not any("infusion" in p for p in got.problems), got.problems


def test_a_tincture_will_not_take_a_herb_without_an_infusion():
    """"Infusions should be the only way to combine tinctures with other things.\""""
    got = _pot(["mix"], stock_names=["Mad Cap Tincture"], raw=["acacia"])
    assert any("only take" in p and "infusion" in p for p in got.problems), got.problems


def test_two_tinctures_will_not_combine_without_one_either():
    got = _pot(["mix"], stock_names=["Mad Cap Tincture", "Ice Lotus Tincture"])
    assert any("infusion" in p for p in got.problems), got.problems


def test_infusing_is_what_makes_it_legal():
    got = _pot(["infuse"], stock_names=["Mad Cap Tincture"], raw=["acacia"])
    assert not any("infusion" in p for p in got.problems), got.problems


def test_the_restriction_lifts_itself_when_the_method_is_learned():
    """`infuse` is Herbalist 4, so below it the chain is refused for not knowing the
    method — which is the same wall arriving by a different route, and correct."""
    from rules import worldclass as wc

    track = wc.tracks()["herbalist"]
    assert "infuse" in track.unlocked_methods(4)
    assert "infuse" not in track.unlocked_methods(3)
    assert "distill" in track.unlocked_methods(3)

    low = _pot(["infuse"], stock_names=["Mad Cap Tincture"], raw=["acacia"], level=3)
    assert any("learned at" in p for p in low.problems), low.problems


def test_a_jar_that_is_not_a_tincture_is_not_restricted():
    """A tea and a herb in the same pot is an ordinary compound, which is most of what
    the bench does; the rule is about tinctures alone."""
    got = _pot(["mix"], stock_names=["Woundwort Tea"], raw=["acacia"])
    assert not any("infusion" in p for p in got.problems), got.problems


def test_a_raw_herb_that_cannot_be_brewed_raw_cannot_be_infused_raw():
    """"raw herbs as long as the raw herbs could be brewed raw" — the same question
    asked twice, so the same flag answers it."""
    from rules.crafting import _infusion_additions

    dry = FakeHerb("Coldwood", brew_raw=False)
    assert any("brewed raw" in p for p in _infusion_additions([dry], [], ["infuse"]))
    # Grinding it in the same chain answers the objection.
    assert _infusion_additions([dry], [], ["grind", "infuse"]) == []


def test_a_volatile_shelled_herb_needs_opening_before_it_is_infused():
    """"some herbs that are volitile need extraction.\""""
    from rules.crafting import _infusion_additions

    sealed = FakeHerb("Salamander Gland", needs_extraction=True, volatile=True)
    assert any("extracted" in p for p in _infusion_additions([sealed], [], ["infuse"]))
    assert _infusion_additions([sealed], [], ["extract", "infuse"]) == []
