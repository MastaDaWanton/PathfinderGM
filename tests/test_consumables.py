"""Drinking it, throwing it, and putting it on a blade.

A crafted potion was a paragraph in a satchel. It had a name, a rarity, a potency
multiplier and a list of effects written for a person to read, and nothing in the engine
could do anything with any of it — captured in play: the player threw a tincture at a beast
and got two sentences of narration and no mechanics at all, because narration was the only
thing available.

Two things were missing and both are here. `Stock` carried its effects as prose, so the
structure the extractor had already found was thrown away on the way to inventory; and
nothing turned a structured effect into an engine intent.
"""
from __future__ import annotations

import pytest

from rules import consumables as con
from rules import ingredients as ing_mod
from rules.bestiary import instantiate
from rules.crafting import Stock, _name_for, from_stock_dict
from rules.dice import Dice
from rules.engine import Engine, Scene
from rules.intents import IntentError
from rules.sheet import from_dict, load_pc, to_dict


class Named:
    """Anything with a `.name`, which is all `_name_for` reads."""

    def __init__(self, name):
        self.name = name


@pytest.fixture
def poison_specs():
    return ing_mod.get("dragon-flower").specs


@pytest.fixture
def board(poison_specs):
    s = Scene(location_id="5bbd0c40345f")
    pc = s.add(load_pc("fixtures/pc-kesst.json"))
    s.add(instantiate("thug", scene=s, name="the beast"))
    pc.stock["tincture#1"] = Stock(base="Dragon Flower Tincture", tier="rare",
                                   potency=1.25, count=3, specs=list(poison_specs))
    return s, Engine(s, Dice(seed=9))


def use(engine, **params):
    return engine.run(engine.validate([
        {"op": "use_item", "actor": "pc", "because": "she uses it",
         "params": {"item": "tincture#1", **params}}]))


def finish(engine, res, faces=(19, 14, 6, 5, 4)):
    for face in faces:
        if res.status == "complete":
            break
        res = engine.resume(face=face)
    return res


# --- the name that would not stop growing ---------------------------------------------

def test_a_shape_word_is_not_stacked_on_itself():
    """Crafted outputs go back into the craft tree as inputs — that is the whole point of
    keeping them in inventory — so distilling a tincture produced a "Dragon Flower Tincture
    Tincture". Seen in play ten deep, ending "Tincture Tincture Preparation"."""
    assert _name_for([Named("Dragon Flower")], ["distill"]) == "Dragon Flower Tincture"
    assert _name_for([Named("Dragon Flower Tincture")], ["distill"]) == \
        "Dragon Flower Tincture"


def test_a_name_that_already_compounded_is_healed():
    """Saves written before the fix carry the stacked name. Crafting with one brings it
    back rather than adding an eleventh."""
    assert _name_for([Named("Dragon Flower Tincture Tincture Tincture")], ["brew"]) == \
        "Dragon Flower Tea"


# --- the structure that used to be lost --------------------------------------------------

def test_an_ingredient_exposes_its_effects_structured(poison_specs):
    """Same source and same precedence as the card lines, so what the card says and what
    happens when you drink it cannot disagree."""
    assert poison_specs
    assert any(s["type"] == "ability_damage" for s in poison_specs)
    assert any(s["type"] == "save_gate" for s in poison_specs)


def test_specs_survive_into_inventory_and_a_save(poison_specs):
    item = Stock(base="Dragon Flower Tincture", specs=list(poison_specs))
    assert from_stock_dict(item.as_dict()).specs == item.specs


def test_a_character_keeps_them_through_a_save(board):
    scene, _ = board
    assert from_dict(to_dict(scene.pc())).stock["tincture#1"].specs


# --- what counts as harmful ----------------------------------------------------------------

def test_something_that_hurts_is_harmful(poison_specs):
    assert con.is_harmful(Stock(base="x", specs=list(poison_specs)))


def test_a_plain_restorative_is_not():
    assert not con.is_harmful(Stock(base="Woundwart Tea",
                                    specs=[{"type": "heal", "dice": "1d8"}]))


def test_harm_is_read_off_the_effects_not_the_name():
    """A "Purified Draught of Skull Orchid" is not made safe by being called one."""
    assert con.is_harmful(Stock(base="Purified Draught", specs=[
        {"type": "ability_damage", "target": "con", "dice": "1d4"}]))


# --- potency reaches the dice ----------------------------------------------------------------

def test_potency_scales_the_flat_part_not_the_dice():
    """1d6 at 125% as 1.25d6 is not a thing anyone can roll."""
    assert con.scale("1d6", 1.25) == "1d6+1"
    assert con.scale("2d4+1", 2.0) == "2d4+6"


def test_an_unmodified_chain_changes_nothing():
    assert con.scale("1d8", 1.0) == "1d8"


def test_something_that_is_not_dice_is_left_alone():
    assert con.scale("special", 1.5) == "special"


# --- drinking -------------------------------------------------------------------------------

def test_drinking_spends_the_dose(board):
    scene, engine = board
    use(engine, how="drink")
    assert scene.pc().stock["tincture#1"].count == 2


def test_the_last_dose_leaves_the_satchel(board):
    scene, engine = board
    scene.pc().stock["tincture#1"].count = 1
    use(engine, how="drink")
    assert "tincture#1" not in scene.pc().stock


def test_using_something_you_do_not_have_is_refused(board):
    scene, engine = board
    with pytest.raises(IntentError, match="not carrying"):
        engine.run(engine.validate([
            {"op": "use_item", "actor": "pc",
             "params": {"item": "nothing#1", "how": "drink"}}]))


def test_a_restorative_actually_heals(board):
    scene, engine = board
    pc = scene.pc()
    pc.hp = 3
    pc.stock["tea#1"] = Stock(base="Woundwart Tea", count=1,
                              specs=[{"type": "heal", "dice": "1d8"}])
    engine.run(engine.validate([
        {"op": "use_item", "actor": "pc", "because": "she drinks it",
         "params": {"item": "tea#1", "how": "drink"}}]))
    assert pc.hp > 3


# --- throwing --------------------------------------------------------------------------------

def test_throwing_a_poison_lands_its_effects(board):
    """The turn from the screenshot, which produced narration and nothing else."""
    scene, engine = board
    res = use(engine, how="throw", to="c1")
    beast = scene.actors["c1"]
    assert beast.ability_damage.get("con")
    assert beast.has_condition("nauseated")
    assert "throws Dragon Flower Tincture at the beast" in res.outcomes[0].tell


def test_the_save_is_rolled_rather_than_printed(board):
    """The extractor produces `save_gate` as its own effect — "Fortitude DC 25" sits
    beside "1d6 Constitution damage" rather than wrapping it — so without stitching the
    two back together the save is a line on a card that nothing ever rolls."""
    scene, engine = board
    assert "Fortitude save" in use(engine, how="throw", to="c1").outcomes[0].tell


def test_you_cannot_throw_something_harmless(board):
    scene, engine = board
    scene.pc().stock["tea#1"] = Stock(base="Woundwart Tea", count=1,
                                      specs=[{"type": "heal", "dice": "1d8"}])
    with pytest.raises(IntentError, match="nothing harmful"):
        engine.run(engine.validate([
            {"op": "use_item", "actor": "pc",
             "params": {"item": "tea#1", "how": "throw", "to": "c1"}}]))


def test_effects_the_engine_cannot_run_are_narrated_not_dropped(board):
    """An item that quietly does less than its card says is worse than one that says so
    and leaves the rest to the GM."""
    scene, engine = board
    assert "-2 actions" in use(engine, how="throw", to="c1").outcomes[0].tell


# --- coating a blade ---------------------------------------------------------------------------

def test_coating_puts_it_on_the_weapon(board):
    scene, engine = board
    res = use(engine, how="coat", weapon="rapier")
    assert scene.pc().coating["item"] == "Dragon Flower Tincture"
    assert scene.pc().coating["weapon"] == "rapier"
    assert "along the rapier" in res.outcomes[0].tell


def test_a_coated_blade_delivers_on_the_first_hit(board):
    scene, engine = board
    use(engine, how="coat", weapon="rapier")
    res = finish(engine, engine.run(engine.validate([
        {"op": "attack", "actor": "pc", "target": "c1", "because": "she cuts",
         "params": {"weapon": "rapier", "full_attack": False}}])))

    assert "goes into the wound" in " ".join(o.tell for o in res.outcomes)
    assert scene.actors["c1"].ability_damage.get("con")


def test_the_dose_is_gone_after_it_lands(board):
    """A 1e poison is a dose, not an enchantment."""
    scene, engine = board
    use(engine, how="coat", weapon="rapier")
    finish(engine, engine.run(engine.validate([
        {"op": "attack", "actor": "pc", "target": "c1",
         "params": {"weapon": "rapier", "full_attack": False}}])))
    assert not scene.pc().coating


def test_you_cannot_coat_a_weapon_you_do_not_have(board):
    scene, engine = board
    with pytest.raises(IntentError, match="no weapon"):
        engine.run(engine.validate([
            {"op": "use_item", "actor": "pc",
             "params": {"item": "tincture#1", "how": "coat", "weapon": "trebuchet"}}]))


def test_you_cannot_coat_a_blade_with_tea(board):
    scene, engine = board
    scene.pc().stock["tea#1"] = Stock(base="Woundwart Tea", count=1,
                                      specs=[{"type": "heal", "dice": "1d8"}])
    with pytest.raises(IntentError, match="nothing harmful"):
        engine.run(engine.validate([
            {"op": "use_item", "actor": "pc",
             "params": {"item": "tea#1", "how": "coat", "weapon": "rapier"}}]))


def test_the_coating_survives_a_save(board):
    scene, engine = board
    use(engine, how="coat", weapon="rapier")
    assert from_dict(to_dict(scene.pc())).coating["item"] == "Dragon Flower Tincture"


def test_an_unknown_way_of_using_it_is_refused(board):
    scene, engine = board
    with pytest.raises(IntentError, match="drink, throw or coat"):
        engine.run(engine.validate([
            {"op": "use_item", "actor": "pc",
             "params": {"item": "tincture#1", "how": "inhale"}}]))
