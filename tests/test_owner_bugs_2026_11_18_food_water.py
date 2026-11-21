"""Owner bug list 2026-11-18, items 17 (food and water) and 18 (the rock).

Each test names the defect it prevents, measured on the owner's own saves (jack, frag).
"""
from __future__ import annotations

import pytest

from rules import gear, survival
from rules.crafting import Stock
from rules.dice import Dice
from rules.engine import Engine, Scene
from rules.sheet import load_pc


@pytest.fixture
def scene():
    s = Scene(location_id="5bbd0c40345f")
    s.add(load_pc("fixtures/pc-kesst.json"))
    pc = s.pc()
    pc.goods.clear()
    pc.stock.clear()
    return s


def _engine(scene, well: str = "") -> Engine:
    e = Engine(scene, Dice(seed=1))
    e.water_at_hand = lambda: well
    return e


# --- 17: the waterskin --------------------------------------------------------------------

def test_jacks_waterskin_used_as_a_jar_is_drunk_once_and_counts():
    """jack, turn_log[200]: `use_item waterskin#1 how=drink` beside a bare `drink` spent his
    last full skin for nothing (the jar door spends any shelf item) and then refused the
    drink: "has no water to drink". Now the use is the drink, once, and the skin is left."""
    s = Scene(location_id="5bbd0c40345f")
    s.add(load_pc("fixtures/pc-kesst.json"))
    pc = s.pc()
    pc.goods.clear()
    pc.stock.clear()
    pc.stock["waterskin#1"] = Stock(base="waterskin", count=2, craft="")
    pc.watered_minutes = 30 * 60
    e = _engine(s)
    res = e.run(e.validate([
        {"op": "use_item", "actor": "pc", "params": {"item": "waterskin#1", "how": "drink"}},
        {"op": "drink", "actor": "pc", "params": {}}]))
    assert [o.op for o in res.outcomes] == ["drink"]
    assert res.outcomes[0].status == "resolved", res.outcomes[0].tell
    assert pc.stock["waterskin#1"].count == 1
    assert pc.goods.get("empty waterskin") == 1
    # Half a gallon is half a day (CRB p.444: a gallon a day): the clock, held at the
    # grace, comes back 12 hours, not to nothing.
    grace = survival.hours_until_thirsty(pc) * 60
    assert pc.watered_minutes == min(30 * 60, grace) - 12 * 60


def test_a_skin_is_half_a_day_and_a_loaf_half_a_day_of_food(scene):
    """`survival.drink`/`eat` reset the need in full for any sip or crumb."""
    pc = scene.pc()
    pc.goods.update({"waterskin": 1, "loaf of bread": 1})
    pc.watered_minutes = pc.fed_minutes = 20 * 60
    e = _engine(scene)
    e.run(e.validate([{"op": "drink", "actor": "pc", "params": {}},
                      {"op": "eat", "actor": "pc", "params": {"item": "bread"}}]))
    assert pc.watered_minutes == 8 * 60
    assert pc.fed_minutes == 8 * 60


def test_ale_and_wine_are_drink(scene):
    """"Ale does nothing for thirst": a bought mug had no gear row, so no door took it."""
    pc = scene.pc()
    pc.goods["mug of ale"] = 1
    pc.watered_minutes = 10 * 60
    e = _engine(scene)
    out = e.run(e.validate([{"op": "drink", "actor": "pc",
                             "params": {"item": "mug of ale"}}])).outcomes[0]
    assert out.status == "resolved", out.tell
    assert pc.watered_minutes == 7 * 60            # a pint, an eighth of a day
    assert "mug of ale" not in pc.goods
    assert gear.provision_row("pitcher of common wine") == "drink"


def test_an_empty_skin_fills_at_water_and_not_without_it(scene):
    """There was no way to refill a skin ("nothing refills an empty skin yet")."""
    pc = scene.pc()
    pc.goods["empty waterskin"] = 2
    dry = _engine(scene)
    out = dry.run(dry.validate([{"op": "drink", "actor": "pc",
                                 "params": {"fill": True}}])).outcomes[0]
    assert out.status == "refused" and pc.goods["empty waterskin"] == 2
    wet = _engine(scene, well="the well")
    out = wet.run(wet.validate([{"op": "drink", "actor": "pc",
                                 "params": {"fill": True}}])).outcomes[0]
    assert out.status == "resolved", out.tell
    assert pc.goods.get("waterskin") == 2 and "empty waterskin" not in pc.goods
    # A model's "false" is not a yes: it drinks instead.
    out = wet.run(wet.validate([{"op": "drink", "actor": "pc",
                                 "params": {"fill": "false"}}])).outcomes[0]
    assert pc.goods.get("waterskin") == 1


def test_a_drunk_tea_counts_a_cup(scene):
    """Teas and potions gave no water at all. House rule: a tea is a cup (1/16 gallon,
    90 minutes of a day), a tincture or potion a dose."""
    pc = scene.pc()
    tea = Stock(base="Yarrow Infusion", count=1, form="infusion", how=["drink"])
    pc.stock["yarrow-infusion#1"] = tea
    pc.watered_minutes = 10 * 60
    e = _engine(scene)
    out = e.run(e.validate([{"op": "use_item", "actor": "pc",
                             "params": {"item": "yarrow-infusion#1",
                                        "how": "drink"}}])).outcomes[0]
    assert out.op == "use_item" and out.status == "resolved", out.tell
    assert pc.watered_minutes == 10 * 60 - 90
    assert survival.jar_fluid(Stock(base="x", form="tincture")) == survival.DOSE_GALLONS


def test_the_pack_feeds_an_awake_body_in_short_stretches(scene):
    """frag went 143 hours without eating carrying 5 trail rations: the pack fed only
    stretches of a day or more, and play and the benches spend hours, not days."""
    pc = scene.pc()
    pc.goods["trail rations"] = 5
    pc.fed_minutes = survival.DAY_MINUTES - 30
    toll = survival.charge(pc, 60, Dice(seed=2))
    assert pc.goods["trail rations"] == 4
    assert pc.fed_minutes < 60
    assert "from the pack" in " ".join(survival.said(pc, toll))
    # An hour that is not due draws nothing.
    survival.charge(pc, 60, Dice(seed=2))
    assert pc.goods["trail rations"] == 4


def test_drink_and_fill_are_buttons_and_provisions_are_consumables():
    """The UI stripped Drink from gear rows and `_gear_acts` added only Eat; the
    waterskin sat on the gear shelf among the rope."""
    from play import views

    labels = [a["label"] for a in views._gear_acts(gear.row_for("waterskin")[1], "w")]
    assert labels == ["Drink"]
    labels = [a["label"] for a in views._gear_acts(gear.row_for("empty waterskin")[1], "e")]
    assert labels == ["Fill"]
    names = views._food_names()
    assert {"waterskin", "trail rations", "empty waterskin", "mug of ale"} <= names


# --- 18: the rock -------------------------------------------------------------------------

def test_throw_the_rock_i_picked_up_before_finds_the_rock(scene):
    """jack, turn_log[162]: "throw the rock i picked up before at the wolf" was refused
    "has no rock i picked up before to swing or throw", with a rock in his goods."""
    from rules.bestiary import instantiate

    pc = scene.pc()
    pc.goods["rock"] = 1
    wolf = scene.add(instantiate("wolf", scene=scene, name="the wolf")) or next(
        a for a in scene.actors.values() if a.name == "the wolf")
    e = _engine(scene)
    assert e._improvised_unheld(pc, "rock i picked up before") == ""
    assert e._improvised_held(pc, "rock i picked up before") == "rock"
    e.run(e.validate([{"op": "begin_encounter",
                       "params": {"sides": {"pc": ["pc"], "them": [wolf.ref]}}}]))
    res = e.run(e.validate([{"op": "attack", "actor": "pc", "target": wolf.ref,
                             "params": {"weapon": "improvised", "thrown": True,
                                        "item": "rock i picked up before"}}]))
    assert not any(o.status == "refused" for o in res.outcomes), \
        [o.tell for o in res.outcomes]


def test_pick_up_and_throw_at_a_named_bystander_is_an_attack(scene):
    """"I pick up a rock and throw it at the goat" planned the pick-up only: the throw had
    no target the fill would give it (an untouched goat is a bystander), so no attack
    was rolled and the table said "Nice shot"."""
    from gm import judgement
    from rules import states
    from rules.bestiary import instantiate

    scene.add(instantiate("goat", scene=scene, name="the goat"))
    scene.add(instantiate("goat", scene=scene, name="the nanny"))
    goat = next(a for a in scene.actors.values() if a.name == "the goat")
    goat.add_condition(states.BYSTANDER_KEY)
    raw = judgement.inject_improvised(
        [{"op": "give", "actor": "pc", "params": {"item": "rock", "to": "pc"}}],
        "I pick up a rock and throw it at the goat", scene)
    attack = next(r for r in raw if r["op"] == "attack")
    assert attack["target"] == goat.ref
    assert attack["params"]["thrown"] and attack["params"]["item"] == "rock"


def test_table_talk_cannot_praise_a_throw_nobody_rolled():
    """"Nice shot" over a turn with no attack outcome passed the beyond-tells read as a
    reaction. A sentence the read marks `attack: yes` on a turn with no attack is cut."""
    from gm import beat_verify

    def chat(msgs, *a, **kw):
        class R:
            def json(self):
                return {"1": {"verdict": "reacts", "words": "", "attack": "yes"},
                        "2": {"verdict": "reacts", "words": "", "attack": "no"}}
        return R()

    text = "Nice shot. What do you do now?"
    facts = ["Jack takes the rock."]
    found = beat_verify.beyond_tells(text, facts, chat=chat, model="m", attacked=False)
    assert [s for s, _ in found] == ["Nice shot."]
    assert beat_verify.beyond_tells(text, facts, chat=chat, model="m", attacked=True) == []
