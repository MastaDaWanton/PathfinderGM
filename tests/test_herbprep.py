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
