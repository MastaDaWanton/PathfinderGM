"""A purchase opens the counter, and the counter carries what people buy.

Measured live 2026-09-27 (tools/narrator_audit.py --script calling, three runs): "I try
to buy a coil of rope." was `narrate_only` every time. The narrator invented a rope
seller and handed rope over at one in the morning, and no coin moved — nothing turned a
purchase into anything the engine resolves. Had it reached the engine there was nothing
to buy either: every shelf was drawn from the crafting benches' materials, so the market
sold alum, bismuth and quicklime, and no rope, no torch and no bread.

The user's ruling: a purchase "should open the trade tab [potentially with Rope in the
basket]". Every tradition researched hands words to a trade screen and never settles a
sale in them (Fallout's ShowBarterMenu, Neverwinter Nights' OpenStore, Baldur's Gate 3's
Trade button), and matches the thing named against real stock, refusing rather than
guessing (tbaMUD: "Sorry, I haven't got exactly that item.").
"""
from __future__ import annotations

import json

import pytest
from django.test import Client, override_settings

from gm import judgement
from rules import goods, keepers, market
from rules.dice import Dice
from rules.engine import Engine, Scene
from rules.sheet import load_pc

TOWN = "5bbd0c40345f"
MARKET = f"{TOWN}~urban:the-market"
HOUR = 60


# --- the words ------------------------------------------------------------------------------

@pytest.mark.parametrize("said,want", [
    ("I try to buy a coil of rope.", "a coil of rope"),
    ("I go to the market and buy a coil of rope.", "a coil of rope"),
    ("I want to buy some bread from her.", "some bread"),
    ('"I\'d like to buy a loaf," I say.', "a loaf"),
    ("I buy the man a drink.", ""),
    ("I buy a round for the bar.", ""),
    ("I buy time.", ""),
    ("I pay for a room.", ""),
    ("I sell the rope.", ""),
])
def test_what_the_player_set_out_to_buy(said, want):
    assert judgement.purchase_sought(said) == want


def test_a_buy_the_model_wrote_for_it_waits_for_the_screen():
    """The screen is where the price is seen and the coin moves; a `buy` in the plan
    would settle the sale before the player saw either."""
    raw = [{"op": "buy", "params": {"item": "rope"}}, {"op": "narrate_only"}]
    assert judgement.strip_counter_buys(raw, "I buy a coil of rope.") == [{"op": "narrate_only"}]
    assert judgement.strip_counter_buys(raw, "I look around.") == raw


# --- the shelves --------------------------------------------------------------------------

def test_the_market_carries_rope_and_bread():
    shelf = market.on_sale(TOWN, "market", 0, {}, counter_kind="market")
    names = {getattr(x, "name", "") for x in shelf}
    assert {"hemp rope", "torch", "loaf of bread"} <= names
    # And the material draw is still there beside the staples.
    assert any(not isinstance(x, goods.Good) for x in shelf)


def test_a_tavern_sells_food_and_drink_and_not_alum():
    shelf = market.on_sale(TOWN, "tavern", 0, {}, counter_kind="tavern")
    assert shelf and all(isinstance(x, goods.Good) for x in shelf)
    assert "mug of ale" in {x.name for x in shelf} and "hemp rope" not in {x.name for x in shelf}


def test_a_coil_of_rope_is_the_hemp_rope_and_a_loaf_is_bread():
    shelf = goods.goods_at("market")
    assert goods.match_want("a coil of rope", shelf)[0].name == "hemp rope"
    assert goods.match_want("a loaf", shelf)[0].name == "loaf of bread"
    assert goods.match_want("a dragon's egg", shelf)[0] is None


# --- the engine's buy ----------------------------------------------------------------------

def _at_market(clock=10 * HOUR):
    s = Scene(location_id=TOWN)
    s.add(load_pc("fixtures/pc-kesst.json"))
    s.clock_minutes = clock
    e = Engine(s, Dice(seed=1))
    e.place_party(MARKET)
    return s, e


def test_buying_rope_by_name_gives_fifty_feet_and_takes_a_gold_piece():
    s, e = _at_market()
    pc = s.pc()
    pc.purse = {"gp": 10}
    before = goods.in_copper(pc.purse)
    out = e.run(e.validate([{"op": "buy", "actor": "pc", "params": {"item": "rope"}}],
                           origin="author:test"))
    assert out.outcomes[0].status == "resolved", out.outcomes[0].tell
    # Live: "pays the stallholder 1 gp for 1x hemp rope" — fifty feet, said as such.
    assert "50 ft of hemp rope" in out.outcomes[0].tell
    assert goods.in_copper(pc.purse) == before - 100
    rope = [st for st in pc.stock.values() if st.base == "hemp rope"]
    assert rope and rope[0].count == 50
    # A staple is not sold out: the second coil is there too.
    again = e.run(e.validate([{"op": "buy", "actor": "pc", "params": {"item": "rope"}}],
                             origin="author:test"))
    assert again.outcomes[0].status == "resolved"


# --- the panel and the turn ------------------------------------------------------------------

@pytest.fixture
def at_the_market(tmp_path):
    with override_settings(CAMPAIGN_DIR=str(tmp_path / "campaigns")):
        from play import campaign as cm
        from play import concurrency

        cm._LIVE.clear()
        concurrency.reset_for_tests()
        c = cm.begin_with(load_pc("fixtures/pc-kesst.json"))
        c.scene.location_id = TOWN
        c.scene.clock_minutes = 10 * HOUR
        c.engine().place_party(MARKET)
        c.save()
        yield cm
        cm._LIVE.clear()


def _trade(want):
    return Client().post("/api/trade", data=json.dumps({"want": want}),
                         content_type="application/json").json()


def test_the_panel_picks_what_was_asked_for(at_the_market):
    got = _trade("a coil of rope")
    assert got["pick"] == "gear:rope" and got["want_line"] == ""
    assert any(r["id"] == "gear:rope" and r["name"] == "hemp rope (50 ft)"
               for r in got["theirs"])


def test_a_thing_the_counter_does_not_carry_is_said_and_not_guessed(at_the_market):
    got = _trade("a dragon's egg")
    assert got["pick"] == "" and "has no dragon's egg on the counter" in got["want_line"]


def test_trying_to_buy_rope_opens_the_counter_with_the_rope_picked(at_the_market,
                                                                    monkeypatch):
    """The turn the player clicks: /api/say returns `trade`, and the page opens the
    panel with it (play/static/js/table/04 and 06)."""
    from gm import client as gm_client
    from gm.agent import TurnPlan
    from gm.client import Reply
    from play import views

    seen = {}

    def plan(agent, *a, **kw):
        agent.last_said = []
        return TurnPlan(narration="", intents=agent.engine.validate(
            [{"op": "narrate_only", "because": "t"}]))

    def chat(*a, **k):
        seen.setdefault("prompts", []).append(json.dumps(a[0] if a else k, default=str))
        return Reply(json.dumps({"narration": "The keeper looks up from the counter. "
                                               * 8 + "What do you do?",
                                 "suggestions": ["I look"]}), 0.1, "stub")

    monkeypatch.setattr(views.GMAgent, "plan_turn", plan)
    monkeypatch.setattr(gm_client, "chat", chat)
    r = Client().post("/api/say", data=json.dumps({"text": "I try to buy a coil of rope."}),
                      content_type="application/json")
    assert r.status_code == 200, r.content[:300]
    assert r.json()["trade"] == {"open": True, "want": "a coil of rope"}
    assert any("AT THE COUNTER (fact)" in p for p in seen["prompts"])


def test_a_shut_counter_opens_nothing(at_the_market, monkeypatch):
    from play import campaign as cm
    from play import views

    c = cm.current()
    c.scene.clock_minutes = 23 * HOUR
    assert keepers.shut_here(c.scene) or views._merchant_here(c.scene) is None
    assert views._trade_offer(c, "I try to buy a coil of rope.") is None


# --- found live, 2026-09-27 ---------------------------------------------------------------------

def test_the_prose_does_not_settle_the_sale_the_screen_is_for():
    """Live, on the turn that opened the counter: "The metal of the coil feels heavy and
    cool in your hands" — the rope was the player's before a coin had moved."""
    from gm import narration

    beat = ("The metal of the coil feels heavy and cool in your hands, a simple weight of "
            "hemp. Azhil Vex stands behind the counter. 'Fifty feet, a gold piece,' he "
            "says. It is yours once you have paid. What do you do?")
    assert "contradicts-the-engine" in [
        f.kind for f in narration.review(beat, buying="a coil of rope").findings]
    kept, cut = narration.keep_the_goods(beat, "a coil of rope")
    assert cut and "in your hands" not in kept
    assert "a gold piece" in kept and "once you have paid" in kept
    # Not a buying turn: nothing is read.
    assert narration.keep_the_goods(beat, "") == (beat, [])


def test_going_to_a_named_place_requires_the_walk():
    """Live, twice: "I go to the market and buy a coil of rope." was one `narrate_only`,
    and the party stayed in the tavern. The schema now requires a `travel`; the model
    still names the place from the brief's list."""
    s = Scene(location_id=TOWN)
    s.add(load_pc("fixtures/pc-kesst.json"))
    e = Engine(s, Dice(seed=1))
    e.place_party(f"{TOWN}~urban:the-gate")
    assert "travel" in judgement.declared_ops("I go to the market and buy a coil of rope.", s)
    assert "travel" not in judgement.declared_ops("I look at the market prices.", s)
    assert "travel" not in judgement.declared_ops("Should I go to the market?", s)


def test_a_shut_market_sells_nothing_in_the_prose_either(at_the_market):
    """Live: the market shut for the night, "I buy a dragon's egg." — the prose invented a
    vendor and wrote "The transaction for the egg is complete, and the heavy weight of it
    now rests in your pack", and the plan's `give` conjured the egg for nothing."""
    from gm import narration
    from play import campaign as cm
    from play import views

    c = cm.current()
    c.scene.clock_minutes = 23 * HOUR
    note = views._buying_note(c, "I buy a dragon's egg.")
    assert "nothing is sold" in note
    beat = ("The transaction for the egg is complete, and the heavy weight of it now rests "
            "in your pack. What do you do?")
    assert len(narration.hands_over_goods(beat)) == 1
    raw = judgement.strip_counter_buys(
        [{"op": "give", "params": {"item": "dragon's egg", "to": "pc"}},
         {"op": "narrate_only"}], "I buy a dragon's egg.")
    assert raw == [{"op": "narrate_only"}]
