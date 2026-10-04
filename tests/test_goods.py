"""Carrying things, and what money is called where the game is being played.

The defect these answer to is one number: across fifty-four turns of a live game the GM
emitted fifty-four `narrate_only` and a single `check`. It narrated a pouch of lucite
crystals, a room paid for, a key handed over — and not one of them existed anywhere the
engine could see. There was nowhere for a thing to *be*, so nothing could be spent,
dropped, counted or stolen, and the side panel showing what was in the scene had
nothing to show because nothing was ever put there.
"""
from __future__ import annotations

import pytest

from gm import judgement
from rules import goods
from rules.dice import Dice
from rules.engine import Engine, Scene
from rules.intents import parse_all
from rules.sheet import from_dict, load_pc, to_dict
from pagesource import table_source


# --- money -----------------------------------------------------------------------------

def test_a_world_that_says_nothing_gets_the_books_own_coins():
    """Never wrong, and the fallback the whole design leans on."""
    assert [c.name for c in goods.coinage()] == [
        "copper piece", "silver piece", "gold piece", "platinum piece"]


def test_the_ratios_are_1e_whatever_the_coins_are_called():
    """Every price in the shipped tables is in copper, silver and gold. A world that
    renamed the arithmetic would have a longsword cost the wrong number."""
    assert [c.copper for c in goods.coinage()] == [1, 10, 100, 1000]
    assert goods.in_copper({"gp": 2, "sp": 3}) == 230


class FakePlace:
    def __init__(self, facts):
        self.facts = facts

    def fact(self, key, default=""):
        return self.facts.get(key, default)


class FakeWorld:
    factions: list = []
    entities: dict = {}


def test_a_currency_the_world_actually_names_is_used_as_written():
    place = FakePlace({"Currency": "Paid in Vermillion marks and nothing else."})
    assert [c.name for c in goods.coinage(FakeWorld(), place)][2] == \
        "Vermillion gold piece"


def test_a_coined_name_comes_from_the_worlds_own_vocabulary_and_says_it_is_coined():
    """"the game needs the ability to invent basic items like different kinds of
    currency depending on the world." Inventing is the feature — inventing from
    *nothing* is not, so the name is taken from a proper noun the world already uses
    and the coin is flagged as this app's invention rather than the export's."""
    place = FakePlace({"Social Classes": "Khy'vyr-centric clans, Nirkor artisans"})
    coins = goods.coinage(FakeWorld(), place)
    assert coins[2].name == "Khy'vyr gold piece"
    assert all(c.coined for c in coins)


def test_the_stem_is_taken_not_the_compound():
    """"Khy'vyr-centric clans" names the Khy'vyr. A "Khy'vyr-centric copper piece" is
    the app mistaking an adjective for a people."""
    place = FakePlace({"Social Classes": "Khy'vyr-centric clans"})
    assert "centric" not in goods.coinage(FakeWorld(), place)[0].name


def test_coins_pluralise_as_pieces():
    """Naming the coin after the metal alone gave "2 Khy'vyr golds"."""
    place = FakePlace({"Social Classes": "Khy'vyr-centric clans"})
    coins = goods.coinage(FakeWorld(), place)
    assert goods.purse_line({"gp": 2, "sp": 1}, coins) == \
        "2 Khy'vyr gold pieces, 1 Khy'vyr silver piece"


def test_an_empty_purse_says_so_rather_than_showing_nothing():
    assert goods.purse_line({}) == "nothing"


@pytest.mark.parametrize("said,expect", [
    ("gp", "gp"), ("gold", "gp"), ("silver pieces", "sp"), ("3 copper", "cp"),
    ("Khy'vyr gold piece", "gp"), ("a lantern", ""),
])
def test_a_denomination_is_recognised_by_id_metal_or_world_name(said, expect):
    place = FakePlace({"Social Classes": "Khy'vyr-centric clans"})
    assert goods.coin_named(said, goods.coinage(FakeWorld(), place)) == expect


def test_paying_breaks_a_big_coin_and_takes_the_change():
    """2 gold and 3 silver, paying 1 gold 5 silver, is 8 silver — not a negative
    balance and not a refusal."""
    after, ok = goods.spend({"gp": 2, "sp": 3}, 150)
    assert ok and after == {"sp": 8}
    assert goods.in_copper(after) == 80


def test_a_purse_that_cannot_cover_it_refuses_rather_than_going_negative():
    after, ok = goods.spend({"cp": 4}, 100)
    assert not ok and after == {"cp": 4}


# --- carrying anything at all ------------------------------------------------------------

def test_an_item_the_tables_know_is_described_from_the_tables():
    assert "1d4" in goods.describe("dagger")


def test_an_item_the_tables_never_heard_of_is_carried_and_says_so():
    """A game in which the GM can only hand over things the Core Rulebook printed is
    not a game. The honesty is the point: the player must not assume their lucite
    crystal does something."""
    line = goods.describe("lucite crystal", 3)
    assert line.startswith("3 × lucite crystal")
    assert "no rules for it" in line


# --- the op ------------------------------------------------------------------------------

@pytest.fixture
def engine():
    scene = Scene(location_id=None)
    scene.add(load_pc("fixtures/pc-kesst.json"))
    return Engine(scene, Dice(seed=3))


def run(engine, raw):
    return engine.run(engine.validate([raw], origin="author:test")).outcomes


def test_taking_something_puts_it_in_your_hands(engine):
    run(engine, {"op": "give", "params": {"item": "lucite crystal", "count": 3,
                                          "to": "pc"}})
    assert engine.scene.pc().goods == {"lucite crystal": 3}


def test_money_lands_in_the_purse_not_among_the_goods(engine):
    """A denomination is an item whose name the world has opinions about; it is still
    counted separately, because arithmetic can be done on it."""
    run(engine, {"op": "give", "params": {"item": "gold", "count": 5, "to": "pc"}})
    pc = engine.scene.pc()
    assert pc.purse == {"gp": 5} and pc.goods == {}


def test_parting_with_something_you_do_not_have_says_so_rather_than_going_negative(engine):
    out = run(engine, {"op": "give", "params": {"item": "lantern", "from_": "pc"}})
    assert "no lantern to give" in out[0].tell
    assert engine.scene.pc().goods == {}


def test_a_price_is_paid_out_of_the_purse_in_the_same_breath(engine):
    pc = engine.scene.pc()
    pc.purse = {"gp": 3}
    run(engine, {"op": "give", "params": {"item": "lantern", "to": "pc",
                                          "price": "2 gp"}})
    assert pc.goods == {"lantern": 1}
    assert pc.purse == {"gp": 1}


def test_a_sale_you_cannot_afford_does_not_happen(engine):
    pc = engine.scene.pc()
    pc.purse = {"sp": 2}
    out = run(engine, {"op": "give", "params": {"item": "warhorse", "to": "pc",
                                                "price": "200 gp"}})
    assert "cannot afford" in out[0].tell
    assert pc.goods == {} and pc.purse == {"sp": 2}


def test_what_is_carried_survives_a_save(engine):
    pc = engine.scene.pc()
    pc.goods = {"brass key": 1}
    pc.purse = {"sp": 7}
    again = from_dict(to_dict(pc))
    assert again.goods == {"brass key": 1} and again.purse == {"sp": 7}


# --- and the GM has to actually emit it --------------------------------------------------

def _scene():
    scene = Scene(location_id=None)
    scene.add(load_pc("fixtures/pc-kesst.json"))
    return scene


def _read(said, scene, *actions, plan=None, question=False):
    """The turn's goods door with this reading (gm/acts_to_ops.py). Since 2026-10-03 the
    reading drives these ops; `inject_goods`, the regex these tests first pinned, is
    retired (docs/structured-turn.md)."""
    from gm import acts_to_ops

    frame = {"question": question, "claims": [], "actions": [dict(a) for a in actions]}
    rows = acts_to_ops.table(frame, scene, sentence=said)
    return acts_to_ops.apply(list(plan or [{"op": "narrate_only"}]), rows, frame, scene)


@pytest.mark.parametrize("said,frame,item", [
    ("I pick up the brass key", {"act": "take", "object": "the brass key"}, "brass key"),
    ("I take a loaf of bread from the stall",
     {"act": "take", "object": "a loaf of bread", "target": "the stall"}, "loaf of bread"),
])
def test_a_declared_pick_up_reaches_the_engine_whatever_the_gm_proposed(said, frame, item):
    """The same shape and the same reason as `inject_survival`: the prompt already
    carries the op and the model does not use it. Fifty-four turns, fifty-four
    narrate_only. A purchase ("I buy a lantern") is the counter's since 2026-09-27
    (`strip_counter_buys`), and no give is built for it."""
    out = _read(said, _scene(), frame)
    give = next(i for i in out if i["op"] == "give")
    assert give["params"]["item"] == item
    assert give["params"]["to"] == "pc"
    assert not [i for i in _read("I buy a lantern", _scene(),
                                 {"act": "buy", "object": "a lantern"}) if i["op"] == "give"]


def test_handing_something_over_takes_it_from_the_player():
    """To the one person here, when the words name nobody (`acts_to_ops.addressed`)."""
    scene = _scene()
    scene.add(_guard(scene))
    scene.pc().goods["brass key"] = 1
    out = _read("I hand over the brass key", scene,
                {"act": "give", "object": "the brass key"})
    assert next(i for i in out if i["op"] == "give")["params"]["from_"] == "pc"


def _guard(scene):
    from rules.bestiary import instantiate

    return instantiate("guildhand", scene=scene, name="the guard")


def test_asking_about_a_thing_is_not_taking_it():
    """A question asked of the game is no act: the reading says `question`, and nothing
    is built."""
    said = "Can I buy a lantern here?"
    assert _read(said, _scene(), question=True) == [{"op": "narrate_only"}]


def test_the_gm_naming_its_own_give_is_left_alone():
    """A give to the player under an act that can get something (a purchase) stands."""
    raw = [{"op": "give", "params": {"item": "rope", "to": "pc"}}]
    assert _read("I buy a lantern", _scene(), {"act": "buy", "object": "a lantern"},
                 plan=raw) == raw


# --- and being unhurt must not stop you sleeping ------------------------------------

def test_an_untargeted_heal_is_aimed_at_the_player_rather_than_killing_the_turn():
    """Measured: "I go to my room, lock the door, and go to sleep" came back with an
    untargeted `heal` beside the rest, and the whole turn died on "heal: needs somebody
    to heal" — so being tired and unhurt made it impossible to go to bed."""
    from gm import judgement

    scene = _scene()
    out = judgement.fill_obvious_targets([{"op": "heal", "params": {"amount": "1d8"}}],
                                         scene)
    assert out[0]["actor"] == "pc"

    engine = Engine(scene, Dice(seed=1))
    engine.run(engine.validate(out, origin="author:test"))            # no IntentError


# --- what kind of thing it is decides where it goes ----------------------------------

@pytest.mark.parametrize("name,kind", [
    ("longsword", "weapon"), ("chain shirt", "armour"), ("light shield", "shield"),
    ("potion of cure light wounds", "consumable"), ("willow-bark tea", "consumable"),
    ("brass key", "gear"), ("rope", "gear"),
])
def test_an_item_is_routed_by_what_it_is(name, kind):
    """"inventory should hold my potions/tinctures/tea... items that can be reused or
    armor and jewelry that i can equip and should show up in my equipment tab and
    influence my stats." One bag of nouns is a list; routing is what makes it an
    inventory."""
    assert goods.kind_of(name) == kind


def test_rope_is_measured_rather_than_counted():
    """"rope(#ft)". Fifty feet of rope is one entry, not fifty ropes."""
    assert goods.unit_for("silk rope") == "ft"
    assert goods.unit_for("lantern") == ""


def test_a_bought_weapon_becomes_one_you_can_swing(engine):
    run(engine, {"op": "give", "params": {"item": "longsword", "to": "pc"}})
    pc = engine.scene.pc()
    assert "longsword" in [w.lower() for w in pc.weapons]
    assert pc.goods == {"longsword": 1}


def test_a_bought_potion_reaches_the_shelf_the_use_op_reads(engine):
    """Consumables already had a whole machinery — crafting, drinking, throwing,
    coating a blade. A bought potion that landed only in `goods` would have been a
    word on a list beside a system that could have used it."""
    run(engine, {"op": "give", "params": {"item": "potion of cure light wounds",
                                          "to": "pc"}})
    pc = engine.scene.pc()
    assert any("potion" in s.base.lower() for s in pc.stock.values())


def test_worn_armour_changes_the_armour_class(engine):
    pc = engine.scene.pc()
    before = pc.ac()
    run(engine, {"op": "give", "params": {"item": "chain shirt", "to": "pc"}})
    out = run(engine, {"op": "wear", "params": {"item": "chain shirt", "actor": "pc"}})
    assert pc.ac() > before
    assert f"{pc.ac()}" in out[0].tell


def test_you_cannot_wear_what_you_do_not_have(engine):
    """An inventory that can be worn without being owned is a sheet claiming
    protection nobody bought."""
    was = engine.scene.pc().armour
    out = run(engine, {"op": "wear", "params": {"item": "full plate", "actor": "pc"}})
    assert "not carrying" in out[0].tell
    assert engine.scene.pc().armour == was      # unchanged, not silently upgraded


def test_a_brass_key_cannot_be_worn(engine):
    run(engine, {"op": "give", "params": {"item": "brass key", "to": "pc"}})
    out = run(engine, {"op": "wear", "params": {"item": "brass key", "actor": "pc"}})
    assert "not something that can be worn" in out[0].tell


# --- the sheet shows what everything else is derived from -----------------------------

def test_the_sheet_carries_the_six_scores_and_what_the_class_grants():
    """Reported from the Defense tab: "character sheet is missing abilities and class".
    `full_sheet` had always *sent* the abilities and the page read exactly one of them,
    Constitution, to work out the number you die at."""
    from rules.sheet import full_sheet

    sheet = full_sheet(load_pc("fixtures/pc-kesst.json"))
    assert {a["key"] for a in sheet["abilities"]} == {
        "str", "dex", "con", "int", "wis", "cha"}
    assert "class_features" in sheet


def test_the_defense_tab_actually_renders_them():
    """The six scores were the old Defense page's `class="abilities"` block; since the
    table rebuild (stage 2) they are the right-hand panel's struck coins, beside the
    Sheet tab's cards, and the class features are in its Feats and traits card."""
    page = table_source()
    assert '$("#medals").innerHTML = Object.entries(pc.abilities' in page
    assert 'class="v2-coin' in page
    assert "s.class_features" in page


# --- what the race gives you, and the clothes you stand up in ------------------------

def test_racial_traits_reach_the_sheet():
    """"feats and trait only shows feats and is missing my racial traits darkvision
    and ferocity." The tab is called Feats & Traits and listed only feats, so half of
    what a half-orc can do was nowhere on the page a player checks."""
    from rules import races
    from rules.sheet import full_sheet

    pc = load_pc("fixtures/pc-kesst.json")
    pc.race = "half-orc"
    names = [t["name"] for t in full_sheet(pc)["traits"]]
    assert "darkvision 60 ft" in names
    assert "ferocity: keep fighting below 0" in names
    # One source with the forge, so a trait shown at creation is the trait shown after:
    # the race document's own lines (rules/races.py), which the forge card shows too.
    assert names == races.document("half-orc")["trait_lines"]


def test_every_race_the_forge_offers_has_traits_on_the_sheet():
    from rules import races
    from rules.sheet import full_sheet

    pc = load_pc("fixtures/pc-kesst.json")
    for race in races.shipped():
        pc.race = race
        assert full_sheet(pc)["traits"], race


def test_the_feats_tab_renders_traits_and_class_features():
    from pathlib import Path

    page = table_source()
    assert "Racial traits" in page and "s.traits.map" in page
    assert "Class features" in page


def test_a_new_character_is_wearing_something():
    """"the clothes my character spawns in should be in my inventory as well and
    should get equipped in the proper slots." The Core Rulebook gives an outfit free at
    first level; the app dressed characters in a sword and armour and nothing else."""
    from rules import creation
    from rules.sheet import body_slots, from_dict

    built, problems = creation.build({
        "name": "Clothed", "race": "half-orc", "bonus_ability": "str",
        "class": "fighter",
        "pronouns": "she/her",
        "abilities": {"str": 14, "dex": 12, "con": 12, "int": 10, "wis": 10, "cha": 10},
        "skills": [], "feats": [],
    })
    assert problems == []
    actor = from_dict(built["sheet"])
    assert actor.goods.get("traveler's outfit") == 1          # carried
    assert actor.slots["body"] == ["traveler's outfit"]       # and worn

    worn = body_slots(actor)
    body = next(s for s in worn["left"] + worn["right"] if s["key"] == "body")
    assert body["items"][0]["item"] == "traveler's outfit"


def test_every_class_walks_out_dressed():
    from rules import creation
    from rules.sheet import from_dict

    for cid in creation.options()["classes"]:
        built, problems = creation.build({
            "name": f"Dressed {cid['id']}", "race": "human", "bonus_ability": "con",
            "class": cid["id"],
            "pronouns": "she/her",
            "abilities": {"str": 12, "dex": 12, "con": 12, "int": 12,
                          "wis": 12, "cha": 12},
            "skills": [], "feats": [], "paths": cid.get("paths", [])[:1],
            "spellbook": creation.starter_spells(cid["id"]),
            # A cleric takes two domains at creation since 2026-09-19 and is refused
            # without them, the way a wizard with an empty book is refused (item 27).
            "domains": creation.starter_domains(cid["id"]),
        })
        assert problems == [], (cid["id"], problems)
        actor = from_dict(built["sheet"])
        assert actor.goods, cid["id"]
        assert actor.slots.get("body"), cid["id"]


# --- an abstract noun is not a thing you can carry -------------------------------------
#
# Found in a live save: the Inventory tab listed "offer" and "scene on" beside a
# traveller's outfit. `inject_goods` built a `give` intent from a regex over the player's
# own sentence — the GM never proposed either of them — and "I accept the offer" and
# "I take in the scene on the ridge" both parsed as somebody picking something up.
#
# Since 2026-10-03 the reading decides whether anything is taken, and the head noun of a
# take's object still has to be something a satchel could hold: the stop-list is now the
# validator on the reading's slot (`acts_to_ops._take`), for the reading that says `take`
# of a phrase like these.

@pytest.mark.parametrize("said,obj", [
    ("I accept the offer", "the offer"),                       # the exact sentence
    # The other one. A head noun read from the end is "ridge", which a satchel could hold;
    # this one is the READING's to get right — "take in" is looking — and the validator
    # alone would let it through, so the reading's act is what is pinned.
    ("I take in the scene on the ridge", "look:the scene on the ridge"),
    ("I take a moment to breathe", "a moment"),
    ("I take cover behind the wall", "cover"),
    ("I take note of the door", "note"),
    ("I take a seat by the fire", "a seat"),
    ("I take a look at the map", "a look"),
    ("I take stock of the situation", "stock"),
    ("I take charge of the group", "charge"),
    ("I take my leave of the innkeeper", "my leave"),
    ("I accept the risk", "the risk"),
    ("I take the lead", "the lead"),
])
def test_an_abstract_noun_never_becomes_an_item(said, obj):
    act, _, obj = obj.rpartition(":")
    out = _read(said, _scene(), {"act": act or "take", "object": obj})
    assert not [i for i in out if i.get("op") == "give"], said


@pytest.mark.parametrize("said,obj,item", [
    ("I take the brass key", "the brass key", "brass key"),
    ("I pick up the leather satchel", "the leather satchel", "leather satchel"),
    ("I pocket the silver ring", "the silver ring", "silver ring"),
])
def test_a_real_object_still_reaches_the_engine(said, obj, item):
    """The control. The stop-list must not turn the feature off — an inventory nothing
    ever writes to is a field on a sheet, not a game."""
    out = _read(said, _scene(), {"act": "take", "object": obj})
    give = [i for i in out if i.get("op") == "give"]
    assert give and give[0]["params"]["item"] == item


def test_the_head_noun_decides_not_the_whole_phrase():
    """"the offer of a room" is an offer; "a leather satchel" is a satchel. English puts
    the head last, so the check reads from the end rather than looking for any match."""
    assert judgement._is_a_thing("leather satchel")
    assert judgement._is_a_thing("brass key")
    assert not judgement._is_a_thing("generous offer")
    assert not judgement._is_a_thing("long look")


def test_a_plural_abstract_noun_is_refused_too():
    """"I take my chances" is not two chances in a satchel."""
    assert not judgement._is_a_thing("chances")
    assert not judgement._is_a_thing("offers")
