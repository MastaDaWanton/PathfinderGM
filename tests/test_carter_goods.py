"""The road-in carter and what a person holds (playtest 2026-11-20, items 5 and 6).

Research: docs/research/2026-11-20-carter-goods.md. Measured on the owner's save: the
carter (c2) had empty goods, inventory and stock; "inspect his cargo" opened nothing and
the narrator wrote "You find no items of the carter's to take"; the carter offered "dried
meat and some hard bread" from a pack that held nothing, and "I accept the food" was read
`consume` and fed Shadow her own trail rations (10 -> 9).
"""
from __future__ import annotations

import pytest
from django.test import override_settings

from gm import interpret
from play import campaign as cm
from rules import openings, states
from rules.bestiary import instantiate
from rules.dice import Dice
from rules.engine import Engine, Scene
from rules.sheet import load_pc


@pytest.fixture(autouse=True)
def _no_readings(monkeypatch):
    monkeypatch.setattr(interpret, "_READINGS", {})


def _carter_scene():
    """A carter loaded by the opening's own loader, and the player beside them."""
    import random

    s = Scene(location_id="5bbd0c40345f")
    s.add(load_pc("fixtures/pc-kesst.json"))
    carter = instantiate("guildhand", scene=s, name="the carter")
    s.add(carter)
    lead = openings.get("road-in")["lead"]
    openings._load_up(carter, lead["carries"], random.Random(7))
    return s, carter


def _run(scene, raw):
    engine = Engine(scene, Dice(seed=1))
    return engine.run(engine.validate(raw)).outcomes


def test_the_road_in_carter_hauls_real_goods(worlds, tmp_path):
    """#6: the carter's goods were empty, so the cart's cargo was prose ("Mostly just basic
    supplies") twice over. Staged now, before a word: their pack and five of the wares
    rows, every one a priced general good, and they sell what they carry."""
    from rules import goods

    with override_settings(CAMPAIGN_DIR=str(tmp_path / "campaigns")):
        c = cm.new_campaign("carter-1", seed=11, character=load_pc("fixtures/pc-borin.json"),
                            world_source=str(worlds.source), start_id="road-in")
    carter = c.scene.people[c.scene.start["slots"]["lead"]]
    assert carter.goods.get("rations") == 2 and carter.goods.get("waterskin") == 1
    assert len(carter.goods) == 2 + 5, carter.goods
    assert all(goods.good(k) is not None for k in carter.goods)
    assert carter.has_state(states.SELLS_WHAT_THEY_CARRY)
    assert not openings.validate(openings.get("road-in"))


def test_a_lead_carrying_an_unpriced_thing_is_refused():
    """Nothing the lead holds is a word without a price."""
    doc = dict(openings.get("road-in"))
    doc["lead"] = dict(doc["lead"], carries={"pack": [{"key": "dragon egg", "count": 1}]})
    assert any("dragon egg" in p for p in openings.validate(doc))


def test_accepting_the_offered_food_takes_it_from_the_carter():
    """#5: "I accept the food", read as the take it is (the reader's gloss and demo),
    naming nobody: it comes out of the hands of the one the player is dealing with, and
    `confirm_takes` asks whether it was offered. Offered, it is handed over: the carter's
    rations go down by one, the player's own are untouched, and nothing is stolen."""
    from gm import acts_to_ops

    scene, carter = _carter_scene()
    pc = scene.pc()
    before = {k: v for k, v in pc.goods.items()}
    frame = {"question": False, "claims": [], "actions": [
        {"act": "take", "object": "the food", "span": "accept the food"}]}
    rows = acts_to_ops.table(frame, scene, sentence="I accept the food.")
    built = [b for r in rows for b in r.intents]
    assert built and built[0]["params"].get("from_") == carter.ref, built
    notes = acts_to_ops.confirm_takes(rows, frame, scene, recent=[
        "'I have a few bits of dried meat and some hard bread left in my pack,' the carter "
        "says."], ask=lambda beat, span: "offered")
    assert notes
    raw = acts_to_ops.apply([{"op": "narrate_only", "params": {}}], rows, frame, scene)
    out = _run(scene, [r for r in raw if r.get("op") == "give"])
    assert out[0].status != "refused", out[0].tell
    assert carter.goods.get("rations") == 1
    assert pc.goods.get("rations", 0) == before.get("rations", 0) + 1
    assert not any(r.get("stolen") for r in scene.props)


def test_nobody_hands_over_what_they_do_not_hold():
    """#5, the owner: "an NPC may only offer what they hold". A hand-over of food by a
    person with nothing on them used to be minted (somebody else's pockets were open the
    way the world is); now it is refused and nothing moves."""
    s = Scene(location_id="5bbd0c40345f")
    s.add(load_pc("fixtures/pc-kesst.json"))
    stranger = instantiate("guildhand", scene=s, name="the stranger")
    s.add(stranger)
    out = _run(s, [{"op": "give", "actor": stranger.ref,
                    "params": {"item": "dried meat", "from_": stranger.ref, "to": "pc"}}])
    assert out[0].status == "refused", out[0].tell
    assert "dried meat" not in s.pc().goods


def test_taking_from_the_cart_unasked_is_a_theft():
    """#6: loot or steal, "with the consequences theft has anywhere else": a take from the
    carter's goods that was not offered keeps the carter as owner and is marked stolen,
    the record the deeds reader and the trial already read."""
    scene, carter = _carter_scene()
    key = next(k for k in carter.goods if k not in ("rations", "waterskin"))
    out = _run(scene, [{"op": "give", "actor": "pc",
                        "params": {"item": key, "from_": carter.ref, "to": "pc"}}])
    assert out[0].status != "refused", out[0].tell
    rec = scene.prop_named(key)
    assert rec["owner"] == carter.ref and rec["stolen"]


def test_buying_off_the_cart_moves_the_real_line_once():
    """#6: buy from the cart. tbaMUD's held object is sold once (`obj_from_char`): the
    carter's line goes down, the coin goes into the carter's purse at the book price, and
    asking for more than there is sells only what there is."""
    from rules import goods

    scene, carter = _carter_scene()
    pc = scene.pc()
    pc.purse = {"gp": 50}
    key = next(k for k in carter.goods if k not in ("rations", "waterskin"))
    have = carter.goods[key]
    out = _run(scene, [{"op": "buy", "actor": "pc",
                        "params": {"item": goods.good(key).id, "from_": carter.ref,
                                   "count": have + 5}}])
    assert out[0].status != "refused", out[0].tell
    assert key not in carter.goods
    assert goods.in_copper(carter.purse) == out[0].effects[0]["paid_cp"] > 0
    again = _run(scene, [{"op": "buy", "actor": "pc",
                          "params": {"item": goods.good(key).id, "from_": carter.ref}}])
    assert again[0].status == "refused" and "has no" in again[0].tell


def test_the_reply_is_shown_what_the_carter_has_on_them():
    """#5: the narrator offered food the carter did not have. What a person holds is in
    what they know, so the reply names only real things."""
    from gm import planned

    scene, carter = _carter_scene()
    engine = Engine(scene, Dice(seed=1))
    lines = planned.known_to(engine, carter.ref)
    assert any("trail rations" in x and "only these" in x for x in lines), lines


@pytest.fixture
def by_the_cart(tmp_path):
    """The player beside a loaded carter, with nobody else about, behind the real panel."""
    import random

    with override_settings(CAMPAIGN_DIR=str(tmp_path / "campaigns")):
        from play import concurrency

        cm._LIVE.clear()
        concurrency.reset_for_tests()
        c = cm.begin_with(load_pc("fixtures/pc-kesst.json"))
        if c.scene.in_encounter:
            c.scene.end_encounter()
        for ref in [r for r, a in c.scene.actors.items() if not a.is_pc]:
            c.scene.remove(ref)
        carter = instantiate("guildhand", scene=c.scene, name="the carter")
        c.scene.add(carter)
        openings._load_up(carter, openings.get("road-in")["lead"]["carries"],
                          random.Random(7))
        c.scene.pc().purse = {"gp": 30}
        c.save()
        yield c, carter.ref
        cm._LIVE.clear()


def test_the_panel_lists_the_cart_and_sells_off_it(by_the_cart):
    """#6, the path the player clicks: "inspect his cargo" is a browse, the browse opens the
    counter's screen (`_trade_offer`), and the screen is `/api/trade`. Before, nobody here
    kept a counter ("There is nobody here to trade with"). Now it lists the carter's own
    goods with prices, buys nothing from the player, and a buy moves the line."""
    import json

    from django.test import Client

    c, ref = by_the_cart
    got = Client().post("/api/trade", data=json.dumps({"want": ""}),
                        content_type="application/json").json()
    assert got.get("seller", {}).get("ref") == ref, got
    carter = cm.current().scene.actors[ref]
    assert {r["count"] for r in got["theirs"]} and len(got["theirs"]) == len(
        [k for k in carter.goods]), got["theirs"]
    assert got["mine"] == []
    row = got["theirs"][0]
    done = Client().post("/api/trade/do", data=json.dumps(
        {"op": "buy", "item": row["id"], "count": 1}),
        content_type="application/json").json()
    assert done.get("ok"), done
    after = cm.current().scene.actors[ref]
    left = Client().post("/api/trade", data=json.dumps({"want": ""}),
                         content_type="application/json").json()["theirs"]
    was = next((r["count"] for r in left if r["id"] == row["id"]), 0)
    assert was == row["count"] - 1, (row, left)
    assert after.purse
