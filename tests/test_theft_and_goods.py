"""Theft from a shop, a helpless person's purse, typed sales and three loot-data defects.

Every case is an item of the 2026-11-15 playtest (C:/Users/natha/pgm-work/
playtest-2026-11-15.md, a 0.3.6 human Blood Bender outlaw), each reproduced on the turn's
own snapshot before the fix (play-036-data/training/engine-corrections.jsonl):

- #7: "pocket a handful of coins from his open till" — "Nobody here is holding any coin
  out to Vesna Kroll, and none lies here", with the till holding coin.
- #10: "Snatch a silver bracelet" rolled Stealth 20 vs 12, hid her and paid 100 XP, then
  was refused "the shopkeeper has no silver bracelet to take".
- #13: "look over what the stalls have on display" named no goods at all.
- #14: "grab the hooded lantern off the general store's counter" — "has no hooded lantern
  to take" beside a Trade panel listing it at 7 gp with 212 gp in the till.
- #15: the open grab was written as Sleight of Hand: "cannot attempt sleight of hand
  untrained. Nothing is rolled."
- #43: "take the merchant's purse", the merchant unconscious at her feet: "Nothing loose
  lies here", while "search his body" found 5 sp.
- #74: "sell the merchant's dagger, rope, bedroll and backpack to the general store" —
  "not carrying the merchant's dagger, rope, bedroll and backpack"; nothing sold.
- #77: a garnished "a notched whetstone" sold at 7 sp 5 cp beside the store's 2 cp one.
- #78: a looted torch was "for show, no effect in play" though the engine models light.

The rules: CRB p.104 Sleight of Hand (trained only; "If you try to take something from a
creature, you must make a DC 20 Sleight of Hand check. The opponent makes a Perception
check to detect the attempt"); CRB Table 8-2 (picking up an item is a move action, no
check); CRB Vision and Light (a torch: normal 20 ft, increased 40 ft, 1 hour).
"""
from __future__ import annotations

import pytest

from gm import acts_to_ops, interpret, watcher
from rules import goods, keepers, market
from rules.crafting import Stock
from rules.dice import Dice
from rules.engine import Engine, Scene
from rules.sheet import from_dict, load_pc

TOWN = "5bbd0c40345f"
MARKET = f"{TOWN}~urban:the-market"


@pytest.fixture(autouse=True)
def _no_readings(monkeypatch):
    monkeypatch.setattr(interpret, "_READINGS", {})


def _at_the_store():
    s = Scene(location_id=TOWN)
    s.add(load_pc("fixtures/pc-kesst.json"))
    s.clock_minutes = 10 * 60
    e = Engine(s, Dice(seed=3))
    e.place_party(MARKET)
    keeper = next(a for a in s.actors.values()
                  if not a.is_pc and keepers.keeps_a_counter(a))
    return s, e, s.pc(), keeper


def _take(item, frm, **extra):
    return {"op": "give", "actor": "pc", "because": "the player took it",
            "params": {"item": item, "to": "pc", "from_": frm, **extra}}


def _check(skill):
    return {"op": "check", "actor": "pc", "because": "doing it unseen",
            "params": {"skill": skill, "dc": {"band": "average"}}, "visibility": "hidden"}


def _run(e, raw):
    res = e.run(e.validate(raw))
    for _ in range(10):
        if not res.awaiting:
            break
        res = e.resume(face=10)
    return res.outcomes


def _till_left(s, e, keeper):
    return e._till(e.validate([_take("coin", keeper.ref)])[0], keeper)[3]


def test_a_lantern_off_the_counter_is_stolen_from_the_shelf():
    """#14: the hooded lantern on the general store's Trade panel could not be taken at
    all. It comes off the same shelf `buy` reads, into the pack, marked stolen and still
    the keeper's — the record the law's theft charge finds (`trial._goods_held`)."""
    s, e, pc, keeper = _at_the_store()
    out = _run(e, [_take("hooded lantern", keeper.ref)])
    took = next(o for o in out if o.op == "give")
    assert took.status == "resolved", took.tell
    assert any(st.base == "hooded lantern" for st in pc.stock.values())
    rec = s.prop_named("hooded lantern")
    assert rec["held_by"] == pc.ref and rec["owner"] == keeper.ref and rec["stolen"]
    fx = took.effects[0]
    assert fx["how"] == "took_from" and fx["from"] == keeper.ref
    # The deeds reader books it as a theft with its witnesses, and the keeper saw it.
    deed = next(x for x in took.effects if x.get("tag") == "deed.theft")
    assert keeper.ref in deed["witnesses"]


def test_coin_comes_out_of_the_till_and_the_till_is_lighter():
    """#7: a keeper's coin is the till's (`market.purse`), which a take never looked in.
    A handful comes out of it, and what the panel's till shows drops by the same."""
    s, e, pc, keeper = _at_the_store()
    before_purse, before_till = goods.in_copper(pc.purse), _till_left(s, e, keeper)
    out = _run(e, [_take("handful of coins", keeper.ref)])
    took = next(o for o in out if o.op == "give")
    assert took.status == "resolved", took.tell
    got = goods.in_copper(pc.purse) - before_purse
    assert 200 <= got <= 300                  # 2d10+10 silver
    assert _till_left(s, e, keeper) == before_till - got


def test_the_till_is_found_when_the_holder_named_is_no_person():
    """#7, the reading's side: `steal: a handful of coins, target: his open till` built a
    give from nobody. The one counter keeper here is whose till it is."""
    s, e, pc, keeper = _at_the_store()
    frame = {"actions": [{"act": "steal", "object": "a handful of coins",
                          "target": "his open till", "commit": "done",
                          "span": "pocket a handful of coins from his open till"}]}
    rows = acts_to_ops.table(frame, s)
    assert rows[0].intents[0]["params"]["from_"] == keeper.ref


def test_an_impossible_take_is_refused_before_anything_is_rolled():
    """#10: Stealth was rolled, hid the player and paid XP, then the take was refused.
    With every take of the batch refused, the covert check is never made."""
    s, e, pc, keeper = _at_the_store()
    xp = pc.xp
    out = _run(e, [_check("stealth"), _take("silver bracelet", keeper.ref)])
    assert [o.op for o in out if o.op in ("check", "give")] == ["give"]
    assert out[-1].status == "refused" or any(o.status == "refused" for o in out)
    assert "On the counter:" in next(o.tell for o in out if o.op == "give")
    assert pc.xp == xp and not pc.has_state("state.hidden")


def test_an_untrained_grab_is_made_in_plain_sight():
    """#15: an open grab was forced through Sleight of Hand, which is trained only. With
    no ranks the check is dropped and the take stands, seen by everybody here."""
    s, e, pc, keeper = _at_the_store()
    with pytest.raises(Exception):
        pc.skill_modifiers("sleight of hand")         # Kesst has no ranks in it
    out = _run(e, [_check("sleight of hand"), _take("hooded lantern", keeper.ref)])
    assert not any(o.op == "check" for o in out)
    took = next(o for o in out if o.op == "give")
    assert took.status == "resolved" and "seen" in took.tell.lower()


def test_a_trained_lift_still_rolls_its_sleight_of_hand():
    """The covert lift by the book keeps its roll: a trained thief's Sleight of Hand is
    made, and the witnesses roll Perception against it (`trial._noticed`)."""
    s, e, pc, keeper = _at_the_store()
    pc.ranks["sleight of hand"] = 4
    out = _run(e, [_check("sleight of hand"), _take("hooded lantern", keeper.ref)])
    assert [o.op for o in out if o.op in ("check", "give")] == ["check", "give"]


def test_take_his_purse_searches_the_helpless_body():
    """#43: the merchant lay unconscious and "take the merchant's purse" looked only on
    the ground. A purse no record holds is the coin on the one helpless body here."""
    s = Scene(location_id=TOWN)
    pc = s.add(load_pc("fixtures/pc-kesst.json"))
    merchant = s.add(from_dict({"name": "merchant", "kind": "npc", "hp": -2, "hp_max": 6,
                                "abilities": {k: 10 for k in ("str", "dex", "con", "int",
                                                              "wis", "cha")},
                                "purse": {"sp": 5}}, ref="c9"))
    merchant.at = pc.at = s.at
    merchant.apply_hp_state()
    assert merchant.is_helpless
    e = Engine(s, Dice(seed=1))
    before = goods.in_copper(pc.purse)
    out = _run(e, [{"op": "give", "actor": "pc", "because": "the player took it",
                    "params": {"item": "merchant's purse", "to": "pc"}}])
    took = next(o for o in out if o.op == "give")
    assert took.status == "resolved", took.tell
    assert goods.in_copper(pc.purse) - before == 50 and not merchant.purse


def test_selling_several_things_after_a_walk_builds_each_sale():
    """#74: one `sell` slot naming four things was "not carrying" all four, and the buyer
    at the end of the walk was nobody here. Each carried thing named whole becomes its own
    sale, and the engine finds the counter's keeper where the walk ends. "Rope" is the
    hemp rope by its head noun, and the whole fifty feet of it: the replay sold one foot
    for 1 cp (#76's measure, on the typed path)."""
    s = Scene(location_id=TOWN)
    pc = s.add(load_pc("fixtures/pc-kesst.json"))
    pc.stock = {}
    pc.add_stock(Stock(base="hemp rope", tier="common", potency=1.0), 50)
    for name in ("bedroll", "backpack"):
        pc.add_stock(Stock(base=name, tier="common", potency=1.0), 1)
    frame = {"actions": [
        {"act": "go", "place": "the market", "commit": "done", "span": "go to the market"},
        {"act": "sell", "object": "the merchant's dagger, rope, bedroll and backpack",
         "target": "the general store", "commit": "done", "span": "sell …"}]}
    rows = acts_to_ops.table(frame, s)
    sells = [i for r in rows for i in r.intents if i["op"] == "sell"]
    items = [i["params"]["item"] for i in sells]
    assert [pc.stock[k].base for k in items] == ["hemp rope", "bedroll", "backpack"], items
    assert sells[0]["params"]["count"] == 50
    assert all("to" not in i["params"] for i in sells)


def test_a_torch_lights_through_the_light_model():
    """#78: a torch read "for show, no effect in play". It carries the light model's
    document now — a purchase, a pocket, and an old save's torch alike."""
    s = Scene(location_id=TOWN)
    pc = s.add(load_pc("fixtures/pc-kesst.json"))
    goods.deliver(s, pc, goods.good("torch"), 1)
    sid = next(k for k, st in pc.stock.items() if st.base == "torch")
    assert pc.stock[sid].how == ["light"] and pc.stock[sid].specs
    old = Stock(base="torch", tier="common", potency=1.0).as_dict()
    assert goods.lit_record(old)["how"] == ["light"]
    out = _run(Engine(s, Dice(seed=1)), [{"op": "use_item", "actor": "pc", "because": "lit",
                                          "params": {"item": sid, "how": "light"}}])
    assert any(fx.get("light") == {"radius_ft": 20, "raised_ft": 40}
               for o in out for fx in o.effects)


def test_a_garnished_store_good_is_that_good_at_its_price():
    """#77: "a notched whetstone" became an uncommon trinket at 37 times the store's own
    whetstone. A garnish whose head noun is a store good is that good."""
    got = watcher._valid_garnish({"item": "a notched whetstone", "band": "modest"}, set())
    assert got == {"kind": "good", "key": "whetstone"}
    assert watcher._valid_garnish({"item": "a silver locket", "band": "modest"},
                                  set())["kind"] == "trinket"


def test_looking_over_the_stalls_shows_the_real_shelf():
    """#13: the look had no rule and the page named no goods. On a beat the player looks,
    the brief carries what the counters here really hold."""
    from gm.brief import BriefContext
    from gm.brief import on_display

    s, e, pc, keeper = _at_the_store()
    reading = {"actions": [{"act": "look", "object": "what the stalls have on display",
                            "commit": "done"}]}
    ctx = BriefContext(world=None, scene=s, location=None, here=None, known=(),
                       recent_events=None, recent=None, secret=False, turn=1,
                       names_for=None, absent="", buying="", reading=reading,
                       player_text="")
    text, facts = on_display.section(ctx)
    assert "ON DISPLAY (fact)" in text and "hooded lantern" in facts[keeper.ref]
    quiet = BriefContext(**{**ctx.__dict__, "reading": {"actions": []}})
    assert on_display.section(quiet) == ("", {})
