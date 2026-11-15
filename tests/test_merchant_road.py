"""The merchant's road played end to end (fix/merchant-road, 2026-11-15): what 0.3.4's
hired swords and bulk trade goods did wrong in a live game, and the rules they lacked.

Every test names what was seen live or the book line it builds. The live run: Kesst at
Mirabalos hires the guardhouse's guard, buys iron, ships it to Zhilvarnia with the guard
set over it, sells it, and waits a week for the wage to renew.
"""
from __future__ import annotations

import math

import pytest

from gm import acts_to_ops, sequence
from rules import goods, hirelings, intents, states, trade
from rules.bestiary import instantiate
from rules.dice import Dice
from rules.engine import Engine, Scene
from rules.sheet import load_pc
from world import loader

PANGRELLA = loader.load_cached("fixtures/pangrella-campaign.json")
AURVANTIS = loader.load_cached("fixtures/aurvantis-campaign.json")
MIRABALOS, ZHILVARNIA = "7ef5e373c993", "6953424c8a82"
DAY = 24 * 60


def _at(place=MIRABALOS, gp=2000):
    scene = Scene(location_id=place, clock_minutes=10 * 60)
    pc = load_pc("fixtures/pc-kesst.json")
    scene.add(pc)
    engine = Engine(scene, Dice(seed=4), world=PANGRELLA)
    engine.place_party(f"{place}~urban:the-docks")
    pc.purse = {"gp": gp}
    return scene, engine, pc


def _run(engine, op, **params):
    engine._journeyed = ""
    return engine.run(engine.validate([{"op": op, "actor": "pc", "because": "t",
                                        "params": params}], origin="author:test")).outcomes


# --- buying and selling by the player's own words ----------------------------------------

@pytest.mark.parametrize("item,word,named", [
    ("iron ore", "Iron ore from nearby mines", True),
    ("iron", "Iron ore from nearby mines", True),
    ("ore", "Iron ore from nearby mines", False),     # not the word it is priced by
    ("tools", "iron tools", False),                   # "some tools" is a tool, not iron
    ("iron tools", "iron tools", True),
])
def test_a_good_is_named_by_the_worlds_words_that_keep_its_price_word(item, word, named):
    """Live 2026-11-15: "iron ore" at Mirabalos ("Iron ore from nearby mines") was refused
    "no iron ore on the counter today" — only "iron" or the whole commodity matched."""
    assert trade.names_the_good(item, "iron", word) is named


def test_iron_ore_is_bought_by_the_pound_where_it_is_mined():
    scene, engine, pc = _at()
    out = _run(engine, "buy", item="iron ore", count=50)[-1]
    assert out.status == "resolved" and "50 lb of iron" in out.tell, out.tell


def test_a_bulk_count_is_not_clamped_at_a_shelfs_500():
    """Live: 600 lb of iron asked for at the counter, 500 bought, nothing said — the
    intents layer bounded `buy.count` at give's 500."""
    scene, engine, pc = _at()
    _run(engine, "buy", item="cargo:iron", count=1500)
    assert sum(x["units"] for x in trade.lots(scene)) == 1500
    assert intents.CARGO_COUNT_MAX > trade.volume(PANGRELLA, MIRABALOS, "iron")


def test_what_waits_on_the_quay_is_said_as_one_lot():
    """Live: a second buy read "1500 lb of iron and 463 lb of iron waits here"."""
    scene, engine, pc = _at()
    _run(engine, "buy", item="cargo:iron", count=400)
    out = _run(engine, "buy", item="cargo:iron", count=400)[-1]
    waits = out.tell.split("lb (")[-1]
    assert " and " not in waits.split("waits here")[0].split(";")[-1], out.tell


def test_selling_the_iron_with_no_count_sells_the_lot():
    """Live: "I sell my iron" sold 1 lb of 2000."""
    scene, engine, pc = _at(ZHILVARNIA)
    trade.add_lot(scene, "iron", 300, pc.ref, 2400, MIRABALOS)
    _run(engine, "sell", item="iron")
    assert not trade.lots(scene)


def test_the_reading_sells_cargo_that_is_in_no_pack():
    """Live: "I sell my iron to the keeper of the general store" was refused "Kesst Vayr is
    not carrying my iron" with 2000 lb of it on the quay — the reading's sale looked only
    in the pack."""
    scene, engine, pc = _at(ZHILVARNIA)
    trade.add_lot(scene, "iron", 2000, pc.ref, 16000, MIRABALOS)
    keeper = instantiate("guildhand", scene=scene, name="the keeper")
    scene.add(keeper)
    scene.move(keeper.ref, scene.at)
    frame = {"actions": [{"act": "sell", "object": "my iron", "target": "the keeper",
                          "span": "sell my iron to the keeper"}]}
    rows = acts_to_ops.table(frame, scene)
    sells = [i for r in rows for i in r.intents if i["op"] == "sell"]
    assert sells and sells[0]["params"]["item"] == "cargo:iron"
    assert sells[0]["params"]["count"] == 2000


def test_a_clause_that_starts_with_we_keeps_its_subject():
    """Live: "…and we sail for Zhilvarnia" came back to the pen as "I we sail"."""
    assert sequence.as_sentence("we sail for Zhilvarnia") == "We sail for Zhilvarnia."
    assert sequence.as_sentence("weigh the iron") == "I weigh the iron."


# --- hauling: pack saddles and drovers ----------------------------------------------------

def test_a_pack_beast_carries_cargo_only_on_a_pack_saddle():
    """CRB: a pack saddle (5 gp, 15 lb) "holds as much gear as the mount can carry"; a
    beast without one carries none of the cargo."""
    scene, engine, pc = _at()
    on_foot = trade.haul_lb(scene)["lb"]
    mule = next(g for g in goods.stables_goods() if g.key == "mule")
    goods.deliver(scene, pc, mule)
    bare = trade.haul_lb(scene)
    assert bare["lb"] == on_foot and "1 beast with no pack saddle" in bare["how"]
    saddle = next(g for g in goods.stables_goods() if g.key == trade.PACK_SADDLE)
    goods.deliver(scene, pc, saddle)
    packed = trade.haul_lb(scene)
    from rules import journey

    beast = trade._beast_heavy(journey.owned_mounts(scene)[0])
    assert packed["lb"] == pytest.approx(on_foot + beast - trade.PACK_SADDLE_LB)


def test_a_herd_goes_as_far_as_it_has_drovers():
    """History, not the book: a drove needed "one man for every 50 or 60 cattle"
    (Droving). Kesst alone drives 50 head; the rest of 120 waits where it was bought."""
    scene, engine, pc = _at()
    trade.add_lot(scene, "sheep", 120, pc.ref, 0, MIRABALOS)
    assert trade.haul_lb(scene)["head"] == trade.DROVER_HEAD
    trade.load_up(scene)
    went = sum(x["units"] for x in trade.lots(scene) if x["stowed"] == "party")
    left = sum(x["units"] for x in trade.lots(scene) if x["stowed"] == "left")
    assert (went, left) == (50, 70)


def test_livestock_in_a_hold_pays_freight_and_is_fed():
    """Livestock weighed nothing in a hold, so ten cattle sailed free; at sea there is no
    grazing (CRB Feed), so they are fed for the days aboard."""
    lot = {"key": "cow", "units": 10}
    assert trade.freight_lb(lot) == 10_000
    assert trade.hold_cp([lot], 288, 2) == trade.freight_cp(10_000, 288) + math.ceil(
        10 * 1000 / trade.FEED_BEAST_LB * trade.FEED_CP_A_DAY * 2)


# --- customs ----------------------------------------------------------------------------

def test_customs_are_levied_where_a_town_keeps_a_customs_house():
    """The app's own places: Zhilvarnia has a customs house, Mirabalos none."""
    assert trade.levies_customs(PANGRELLA, ZHILVARNIA)
    assert not trade.levies_customs(PANGRELLA, MIRABALOS)


def test_goods_brought_in_pay_an_eightieth_once_and_goods_bought_here_none():
    """England's petty custom of 1303: 3d in the pound ad valorem on goods."""
    scene, engine, pc = _at(ZHILVARNIA, gp=100)
    brought = trade.add_lot(scene, "iron", 2000, pc.ref, 16000, MIRABALOS)
    brought["stowed"], brought["at"] = "left", ZHILVARNIA
    trade.add_lot(scene, "silk", 10, pc.ref, 8000, ZHILVARNIA)
    before = goods.in_copper(pc.purse)
    tell, fx = engine._customs(ZHILVARNIA)
    levy = math.ceil(2000 * 10 / 80)
    assert goods.in_copper(pc.purse) == before - levy and "customs house" in tell, tell
    assert engine._customs(ZHILVARNIA) == ("", [])        # cleared, never twice


def test_customs_the_purse_cannot_cover_come_out_of_the_sale():
    scene, engine, pc = _at(ZHILVARNIA, gp=0)
    pc.purse = {}
    lot = trade.add_lot(scene, "iron", 2000, pc.ref, 16000, MIRABALOS)
    lot["stowed"], lot["at"] = "left", ZHILVARNIA
    tell, _fx = engine._customs(ZHILVARNIA)
    assert "owed on the goods" in tell and lot["customs_due"] == math.ceil(2000 * 10 / 80)
    out = _run(engine, "sell", item="cargo:iron", count=2000)[-1]
    assert "goes to the customs owed" in out.tell, out.tell


# --- hirelings: Trust, Risk, unpaid days, a post ----------------------------------------

def _party(gp=100):
    s = Scene(location_id="bde94b038cba")
    pc = instantiate("guildhand", scene=s, name="PC")
    pc.kind = "pc"
    pc.purse = {"gp": gp}
    s.add(pc)
    e = Engine(s, Dice(seed=3), world=AURVANTIS)
    e.place_party("")
    sword = instantiate("guildhand", scene=s, name="Hesk")
    s.add(sword)
    s.move(sword.ref, s.at)
    s.population = {"p1": {"id": "p1", "ref": sword.ref, "home": "bde94b038cba",
                           "life": {"work": "caravan-guard", "axes": {"thrift": 50}}}}
    e.run(e.validate([{"op": "company", "actor": pc.ref, "because": "t",
                       "params": {"who": sword.ref, "do": "hire"}}], origin="author:test"))
    return s, e, pc, sword


def test_an_indifferent_hireling_signs_on_skeptical():
    """Ultimate Campaign's Trust 2, "skeptical": "can be called upon to perform tasks of
    minimal risk" — a stranger who takes your coin."""
    s, e, pc, sword = _party()
    assert hirelings.trust(sword) == 2


def test_a_road_riskier_than_their_trust_is_negotiated_and_a_loss_leaves_them(monkeypatch):
    """C&C: "Hirelings don't automatically refuse. Each category of difference adds 5 to
    the result of the opposed Diplomacy check." Lost: they stay, the unworked days back."""
    s, e, pc, sword = _party()
    monkeypatch.setattr(hirelings, "_negotiates", lambda *a: (False, "Diplomacy 4 against 19"))
    before = goods.in_copper(pc.purse)
    day = hirelings.wage(sword).payload["per_day_cp"]
    out = hirelings.balk(e, "hazardous", "Ledgerwarren")
    assert not sword.has_state(states.HIRED) and not sword.has_state(states.TRAVELS_WITH_YOU)
    assert goods.in_copper(pc.purse) == before + 7 * day
    assert "will not take a hazardous road" in out[0].tell


def test_a_road_within_their_trust_asks_nothing(monkeypatch):
    s, e, pc, sword = _party()
    monkeypatch.setattr(hirelings, "_negotiates", lambda *a: pytest.fail("asked"))
    assert hirelings.balk(e, "questionable", "Ledgerwarren") == []


def test_the_diplomacy_is_harder_by_five_a_step():
    s, e, pc, sword = _party()
    won, said = hirelings._negotiates(e, pc, sword, 4)
    assert " and 10 for the risk over their trust" in said


def test_unpaid_days_are_worked_on_credit_and_repaid_at_double(monkeypatch):
    """C&C: "When funds run out, hirelings may stay on duty. Each day you must attempt a new
    negotiation check ... Hirelings who keep working unpaid expect double pay for those
    days", and "failure to pay immediately reduces the hirelings' Trust to 1"."""
    s, e, pc, sword = _party()
    monkeypatch.setattr(hirelings, "_negotiates", lambda *a: (True, "Diplomacy 18 against 12"))
    day = hirelings.wage(sword).payload["per_day_cp"]
    pc.purse = {}
    s.clock_minutes += 7 * DAY
    out = hirelings.settle(e)
    assert sword.has_state(states.HIRED) and "stays on unpaid" in out[0].tell
    assert hirelings.trust(sword) == 1
    assert hirelings.wage(sword).payload["owed_days"] == 1
    pc.purse = {"gp": 100}
    s.clock_minutes += DAY
    out = hirelings.settle(e)
    assert "at double" in out[0].tell
    assert goods.in_copper(pc.purse) == 10_000 - 2 * day - 7 * day
    assert not hirelings.wage(sword).payload.get("owed_days")


def test_a_hireling_holds_a_post_while_the_party_goes_and_comes_at_a_word():
    """C&C's example: hirelings "watching over ... [a] business". Not built in 0.3.4:
    a guard order went with the party wherever it went."""
    s, e, pc, sword = _party()
    out = e.run(e.validate([{"op": "company", "actor": pc.ref, "because": "t",
                             "params": {"who": sword.ref, "do": "guard", "what": "here"}}],
                           origin="author:test")).outcomes[-1]
    assert "stays here when you go" in out.tell
    assert not sword.has_state(states.TRAVELS_WITH_YOU) and sword.has_state(states.HIRED)
    assert hirelings.guarding(sword) == "here"
    assert e._stays_in_the_world(sword)
    e.run(e.validate([{"op": "company", "actor": pc.ref, "because": "t",
                       "params": {"who": sword.ref}}], origin="author:test"))
    assert sword.has_state(states.TRAVELS_WITH_YOU) and hirelings.guarding(sword) == ""


# --- hires the plan missed (tools/hire_bench.py) -----------------------------------------

def _unhired():
    s = Scene(location_id="nowhere")
    pc = instantiate("guildhand", scene=s, name="PC")
    pc.kind = "pc"
    pc.purse = {"gp": 100}
    s.add(pc)
    sword = instantiate("guildhand", scene=s, name="Hesk")
    s.add(sword)
    s.population = {"p1": {"id": "p1", "ref": sword.ref, "home": "nowhere",
                           "life": {"work": "guard", "axes": {"thrift": 50}}}}
    return s, sword


def test_a_hire_with_no_say_is_found_by_the_readings_target():
    """Bench 2026-11-15: "I hire the guard." planned as a `check` alone — no `say` for the
    old door to read. The reading's own target, found here, is who the words go to."""
    s, sword = _unhired()
    frame = {"actions": [{"act": "other", "target": "Hesk", "span": "I hire the guard"}]}
    got = acts_to_ops.orders_spoken([{"op": "check", "params": {}}], frame, s,
                                    ask=lambda *a: "has them come along")
    assert got[-1]["params"] == {"who": sword.ref, "do": "hire"}
    walk = {"actions": [{"act": "go", "target": "Hesk", "span": "I go to the guard"}]}
    assert acts_to_ops.orders_spoken([{"op": "check"}], walk, s,
                                     ask=lambda *a: "has them come along") == [{"op": "check"}]


def test_a_hire_said_to_nobody_by_name_goes_to_the_one_person_here():
    """Bench: '"You're hired. Come with me."' planned as a `say` with no `to`."""
    s, sword = _unhired()
    frame = {"actions": [{"act": "talk", "span": "You're hired. Come with me."}]}
    got = acts_to_ops.orders_spoken([{"op": "say", "params": {"words": "You're hired."}}],
                                    frame, s, ask=lambda *a: "has them come along")
    assert got[-1]["params"] == {"who": sword.ref, "do": "hire"}


def test_a_guard_order_to_a_sword_not_yet_hired_hires_them_first():
    """Bench: "I hire the guard to guard my cargo." planned as `company do: guard` alone,
    which the engine refuses (they are not with you)."""
    s, sword = _unhired()
    frame = {"actions": [{"act": "other", "target": "Hesk",
                          "span": "I hire the guard to guard my cargo"}]}
    plan = [{"op": "company", "params": {"who": sword.ref, "do": "guard", "what": "cargo"}}]
    got = acts_to_ops.orders_spoken(plan, frame, s, ask=lambda *a: "sets them to guard",
                                    ask_what=lambda *a: "cargo")
    assert [r["params"]["do"] for r in got] == ["hire", "guard"]


def test_a_journey_with_nowhere_to_go_takes_the_place_the_words_name():
    """Live 2026-11-15: "...book passage to Mirabalos for us and my silk." — five plans
    wrote `journey` with no `to`, all refused, and the turn degraded to narration."""
    frame = {"actions": [{"act": "go", "place": "the docks", "span": "head to the docks"},
                         {"act": "journey", "place": "Mirabalos", "span": "book passage"}]}
    got = acts_to_ops.journey_named([{"op": "journey", "params": {}}], frame)
    assert got == [{"op": "journey", "params": {"to": "Mirabalos"}}]
    kept = [{"op": "journey", "params": {"to": "Elyrielle"}}]
    assert acts_to_ops.journey_named(kept, frame) == kept


def test_a_berth_is_booked_after_a_walk_to_the_docks_in_the_same_turn():
    """Live 2026-11-15: "I head to the docks with my guard and book passage to Mirabalos"
    walked to the docks, then the booking was refused "One journey a turn" — but a berth
    booked leaves the party at the quay; the voyage is the next turn's."""
    scene, engine, pc = _at(ZHILVARNIA)
    engine.place_party(f"{ZHILVARNIA}~urban:the-market")
    out = engine.run(engine.validate([
        {"op": "travel", "actor": "pc", "because": "t", "params": {"place": "the docks"}},
        {"op": "journey", "actor": "pc", "because": "t", "params": {"to": "Mirabalos"}}],
        origin="author:test")).outcomes
    assert out[-1].status == "resolved" and "passage to Mirabalos" in out[-1].tell, out[-1].tell


def test_an_order_about_the_other_ship_reaches_the_sea_op():
    """Live 2026-11-15, pirates a sail away: "We close with the pirate ship." was refused
    "You don't know of anywhere called the pirate ship"; "bring us alongside" was a say.
    No words reached `sea`, and no fight on deck could be had."""
    scene, engine, pc = _at()
    scene.sea = {"ours": "ship-a", "theirs": "ship-b", "range": "distant", "hostile": True}
    frame = {"actions": [{"act": "go", "place": "the pirate ship",
                          "span": "We close with the pirate ship"}]}
    plan = [{"op": "narrate_only", "params": {}}]
    assert acts_to_ops.sea_spoken(plan, frame, scene, ask=None) == plan
    got = acts_to_ops.sea_spoken(plan, frame, scene, ask=lambda span: "close")
    assert got == [{"op": "sea", "actor": pc.ref, "because": "the player's orders at sea",
                    "params": {"do": "close"}}]
    scene.sea = {}
    assert acts_to_ops.sea_spoken(plan, frame, scene, ask=lambda span: "close") == plan


def test_closing_again_on_the_other_ship_is_not_a_repeat_of_the_last_turn():
    """Live 2026-11-15: "We close with the pirate ship." took her to bowshot; "Bring us
    alongside her." planned the same `sea do: close` (the last band) and the repeat guard
    refused it twice — the pirates stayed a bowshot off."""
    from gm import interpret, judgement
    from rules.engine import Intent

    line = "Bring us alongside her."
    interpret.remember(line, {"question": False, "claims": [], "actions": [
        {"act": "other", "target": "her", "span": "Bring us alongside her"}]})
    assert judgement._does_what_was_declared([Intent(op="sea", params={"do": "close"})], line)


def test_a_fight_with_the_hireling_standing_is_not_lost_when_the_player_falls():
    """Live 2026-11-15: Kesst fell to a pirate on her own deck with her hired guard at
    10 of 10 hit points; the next line went to the downed door, which ended the fight on
    the spot, and the pirate robbed her past a guard who never swung. While somebody on
    the player's side stands, the say door runs the fight a round a line instead
    (`views._side_stands`)."""
    from play import views

    s = Scene(location_id="nowhere")
    pc = instantiate("guildhand", scene=s, name="PC")
    pc.kind = "pc"
    s.add(pc)
    guard = instantiate("guildhand", scene=s, name="Hesk")
    s.add(guard)
    foe = instantiate("thug", scene=s, name="the pirate")
    s.add(foe)
    e = Engine(s, Dice(seed=2))
    e.run(e.validate([{"op": "begin_encounter", "params": {"sides": {
        "party": [pc.ref, guard.ref], "pirates": [foe.ref]}}}], origin="author:test"))
    pc.hp = -2
    pc.apply_hp_state()
    assert views._side_stands(s)
    guard.hp = -2
    guard.apply_hp_state()
    assert not views._side_stands(s)
