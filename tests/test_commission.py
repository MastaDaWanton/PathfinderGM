"""Paying a keeper to finish the player's own work (owner report 2026-11-01, Corvin).

Turns 21-29 at the smithy: a forged blank for a trident in the pack, "ask the smith if he
can sell me a grip for my trident", "can you put them together and i will give you 10 gold
peices", "okay I wait for the smith to get done", "okay i give him the money as I take the
grip". The reading had no act for paying somebody to do work, nothing was made, the blank
stayed a blank, and the coin was refused "How much?" — the table's give of "the money"
(no amount) had replaced the plan's coin op for ten gold.
"""
from __future__ import annotations

import pytest

from gm import acts_to_ops
from rules import commission, inprogress
from rules.bestiary import instantiate
from tests.test_typed_crafting import _make, _named


@pytest.fixture(scope="module")
def world():
    from world.loader import load_cached

    return load_cached("fixtures/pangrella-campaign.json")


def _engine(world, *, carry=()):
    """Zhilgoroth, whose smithy is a real place with a keeper's trade (Vormoor has none)."""
    from rules.dice import Dice
    from rules.engine import Engine, Scene
    from rules.sheet import load_pc

    s = Scene(location_id="58b90a214ada")
    pc = load_pc("fixtures/pc-kesst.json")
    s.add(pc)
    s.clock_minutes = 10 * 60
    e = Engine(s, Dice(seed=3), world=world)
    e.place_party(next(p.id for p in e.places() if p.name == "the smithy"))
    pc.inventory.clear()
    pc.stock.clear()
    pc.purse = {"gp": 20}
    for key, n in carry:
        pc.carry(key, n)
    return e, pc


def _smith(e):
    """The smithy's own keeper, staffed when the party walked in (`staff_the_place`)."""
    smithy = next(p for p in e.places() if p.name == "the smithy")
    e.place_party(smithy.id)
    smith = next(a for a in e.scene.actors.values()
                 if not a.is_pc and commission.craft_of(a) == "blacksmith")
    return smith, smithy


def _blank(e, pc):
    _make(e, "blacksmith", "a dagger", faces=(15, 1))     # forged, then a spoiled fit
    assert [st.name for st in pc.stock.values()] == ["Iron Blank (Dagger)"]


def _dagger(pc):
    from rules import typed_craft

    return typed_craft.get("blacksmith").target("a dagger", pc, "a dagger")


class _Face:
    """The keeper's die, fixed: every Craft roll the keeper makes comes up `total`."""

    def __init__(self, total):
        self.total = total

    def __call__(self, engine, keeper, step):
        from rules.dice import Modifier, Roll

        return Roll(die="1d20", faces=[10], modifiers=[Modifier(self.total - 10, "test")],
                    label=f"{keeper.name} Craft", visibility="hidden")


def _commission(e, smith, **params):
    return e.run(e.validate([{"op": "commission", "actor": "pc", "because": "t",
                              "params": {"who": smith.ref, "item": "the dagger",
                                         **params}}])).outcomes[0]


def test_a_keepers_craft_is_read_off_their_trade(world):
    e, pc = _engine(world)
    smith, _ = _smith(e)
    assert commission.craft_of(smith) == "blacksmith"
    nobody = e.scene.add(instantiate("guildhand", scene=e.scene, name="a porter"))
    assert commission.craft_of(nobody) == ""


def test_the_smith_finishes_the_blank_for_the_book_wage_and_holds_it_for_the_work(world):
    """The blank and a haft from the pack, the smith's sure hands, the forge's hours plus a
    trained hireling's day (CRB Table 6-9, 3 sp), and the dagger held at the smithy until
    the work's time has passed. No mastery for the player: the work was the smith's."""
    e, pc = _engine(world, carry=(("iron", 1), ("charcoal", 1), ("ash-haft", 2)))
    _blank(e, pc)
    smith, smithy = _smith(e)
    mp_before = pc.track("blacksmith").mp
    level_before = pc.track("blacksmith").level
    from rules import goods

    purse_before = goods.in_copper(pc.purse)
    rows = acts_to_ops.table({"question": False, "claims": [], "actions": [
        {"act": "commission", "target": "the smith", "object": "them",
         "span": "put them together"}]}, e.scene, places=tuple(e.places()))
    built = rows[0].intents
    assert built and built[0]["op"] == "commission" and built[0]["params"]["who"] == smith.ref
    clock = e.scene.clock_minutes
    out = e.run(e.validate(built)).outcomes[0]
    assert out.status == "resolved", out.tell
    eff = out.effects[0]
    assert eff["kind"] == "commission" and eff["items"] == ["Iron Dagger"]
    paid = purse_before - goods.in_copper(pc.purse)
    assert paid == eff["cp"] and paid >= commission.DAY_WAGE_CP
    assert e.scene.clock_minutes == clock, "the player's time is their own"
    dagger = _named(pc, "Iron Dagger")
    assert len(dagger) == 1 and inprogress.work_of(dagger[0], clock) is not None
    assert inprogress.state_of(dagger[0], clock) == "working"
    assert inprogress.state_of(dagger[0], clock + eff["minutes"]) == "ready"
    assert pc.track("blacksmith").mp == mp_before
    assert pc.track("blacksmith").level == level_before
    assert "takes the job" in out.tell and "ready to collect" in out.tell


def test_ruling_no_haft_in_the_pack_the_smith_supplies_one_and_bills_it(world):
    """Owner ruling 2026-11-01: "the smith (keeper) supplies plain fittings (haft, grip)
    from stock, added to the price, when the player has none". Before it, the job was
    refused "needs a haft or grip, and none is in the pack" with the smithy full of them.
    The cheapest bought common grip in the catalogue, at its own price, on the bill."""
    e, pc = _engine(world, carry=(("iron", 1), ("charcoal", 1), ("ash-haft", 1)))
    _blank(e, pc)                                         # the one haft spoiled
    smith, _ = _smith(e)
    fit = commission.stock_fitting(_dagger(pc))
    assert fit and fit["price_gp"] == 1, fit
    out = e.run(e.validate([{"op": "commission", "actor": "pc", "because": "t",
                             "params": {"who": smith.ref, "item": "the dagger"}}])).outcomes[0]
    eff = out.effects[0]
    assert out.status == "resolved" and eff["fitting"] == fit["id"], out.tell
    assert eff["listed_cp"] >= commission.DAY_WAGE_CP + 100
    assert fit["name"].lower() in out.tell and "own stock" in out.tell
    assert not pc.inventory.get(fit["id"]), "the grip went into the dagger"


def test_a_purse_that_cannot_pay_puts_the_pack_back(world):
    e, pc = _engine(world, carry=(("iron", 1), ("charcoal", 1), ("ash-haft", 2)))
    _blank(e, pc)
    smith, _ = _smith(e)
    pc.purse = {}
    out = e.run(e.validate([{"op": "commission", "actor": "pc", "because": "t",
                             "params": {"who": smith.ref, "item": ""}}])).outcomes[0]
    assert out.effects == [] and "wants" in out.tell
    assert [st.name for st in pc.stock.values()] == ["Iron Blank (Dagger)"]
    assert pc.inventory.get("ash-haft") == 1


def test_a_commission_is_code_only_and_the_reader_has_the_act():
    from gm import interpret
    from rules.intents import CODE_ONLY_OPS

    assert "commission" in CODE_ONLY_OPS and "commission" in interpret.ACTS
    assert interpret.ACT_SLOTS["commission"] == ("target", "object")


def test_the_money_with_no_amount_keeps_the_plans_ten_gold():
    """Turn 29: the table's give of "money" took the place of the plan's coin op for ten
    gold and was refused "How much?". The amount the plan carried is kept; the reading
    still says it goes from the player to the smith."""
    from types import SimpleNamespace

    from rules.engine import Scene
    from rules.sheet import load_pc

    s = Scene(location_id="5bbd0c40345f")
    pc = load_pc("fixtures/pc-kesst.json")
    s.add(pc)
    pc.purse = {"gp": 50}
    smith = s.add(instantiate("guildhand", scene=s, name="the smith"))
    row = acts_to_ops.Row(index=0, act="give")
    row.intents = [{"op": "give", "actor": "pc",
                    "params": {"item": "money", "from_": "pc", "to": smith.ref},
                    "because": "the player handed it over"}]
    frame = {"question": False, "claims": [], "actions": [
        {"act": "give", "target": "him", "object": "the money", "span": "give him the money"}]}
    plan = [{"op": "sell", "actor": "pc", "params": {"item": "gold-piece-10",
                                                    "to": smith.ref}}]
    out = acts_to_ops.apply(plan, [row], frame, s)
    give = next(r for r in out if r["op"] == "give")
    assert give["params"]["item"] == "gold-piece-10" and give["params"]["to"] == smith.ref


def test_a_job_that_cannot_be_finished_holds_no_half_made_thing(world):
    """Measured live on Corvin's save the day the commission was built: the plain chain
    passed over the player's tempered blank, forged a NEW pewter blank from the pack, could
    not fit it for want of a haft, and held that half-thing 45 minutes as "the job". Only a
    finished thing is a job done: with nothing to forge from at all, refused, the pack
    whole. (Bars, fuel and no haft is a job now: the smith supplies the grip.)"""
    e, pc = _engine(world, carry=(("charcoal", 2),))
    smith, _ = _smith(e)
    from rules import goods

    before = (goods.in_copper(pc.purse), dict(pc.inventory), sorted(pc.stock))
    out = e.run(e.validate([{"op": "commission", "actor": "pc", "because": "t",
                             "params": {"who": smith.ref, "item": "a dagger"}}])).outcomes[0]
    assert out.effects == [] and "cannot take the job" in out.tell, out.tell
    assert (goods.in_copper(pc.purse), dict(pc.inventory), sorted(pc.stock)) == before


# --- the keeper's own hands (owner ruling 2026-11-01) -------------------------------------

def test_ruling_the_keepers_roll_ladder_is_the_books_failure_bands():
    """CRB Craft: fail by 5 or more and half the raw materials are ruined; fail by 4 or
    less and no progress is made — finished here as lesser work. Ten over is finer work."""
    q = commission.keeper_quality
    assert q(-5) is None and q(-9) is None
    assert q(-4) == 0 and q(-1) == 0
    assert q(0) == 1 and q(9) == 1
    assert q(10) == 2


@pytest.mark.parametrize("over, quality", [(-3, "Crude"), (2, "Sound")])
def test_ruling_the_keepers_own_roll_sets_the_quality(world, monkeypatch, over, quality):
    """Before the ruling the keeper "never fails": every commission came back the plain
    item whatever the smith's Craft. Now his own roll against the step's DC decides."""
    e, pc = _engine(world, carry=(("iron", 1), ("charcoal", 1), ("ash-haft", 2)))
    _blank(e, pc)
    smith, _ = _smith(e)
    from rules import typed_craft

    step_dc = {}
    real = commission.keeper_roll

    def fixed(engine, keeper, step):
        step_dc["dc"] = step.dc
        return _Face(int(step.dc) + over)(engine, keeper, step)
    monkeypatch.setattr(commission, "keeper_roll", fixed)
    out = _commission(e, smith)
    assert out.status == "resolved", out.tell
    assert out.effects[0]["quality"] == quality, out.effects[0]
    if quality == "Crude":
        assert "crude work" in out.tell
    assert real is not fixed


def test_ruling_a_keeper_who_misses_by_five_spoils_it_and_asks_no_fee(world, monkeypatch):
    e, pc = _engine(world, carry=(("iron", 1), ("charcoal", 1), ("ash-haft", 2)))
    _blank(e, pc)
    smith, _ = _smith(e)
    from rules import goods

    purse = goods.in_copper(pc.purse)
    monkeypatch.setattr(commission, "keeper_roll",
                        lambda engine, keeper, step: _Face(int(step.dc) - 6)(engine, keeper,
                                                                             step))
    out = _commission(e, smith)
    assert out.effects[0].get("spoiled") and "spoils it" in out.tell, out.tell
    assert "No fee" in out.tell and goods.in_copper(pc.purse) == purse
    assert "mastery" not in out.tell, "the player is paid nothing for the keeper's work"
    # And that no job is held (round 3, 2026-11-05: the smith's reply told spoiled work
    # "finished"; tests/test_narration_r3.py has the counts).
    assert out.tell.endswith(f"no job is taken: nothing is being made for {pc.name}."),         out.tell


def test_ruling_the_smiths_craft_is_off_his_own_sheet(world):
    """NPC builds carry ranks: the smithy's keeper is a blacksmith-level-1 build with Craft
    +6 (1 rank, class skill, Int +2), and that is the roll."""
    e, pc = _engine(world)
    smith, _ = _smith(e)
    assert sum(m.value for m in smith.skill_modifiers("craft")) == 6


# --- the haggle (owner ruling 2026-11-01) ------------------------------------------------

def test_ruling_an_offered_commission_is_haggled_with_diplomacy(world):
    """A commission OFFERED (a `tried` reading) is a Make Request on the player's own die
    (CRB p.93) for Ultimate Campaign's undercut: 2% and 1% a point, never past 25%."""
    e, pc = _engine(world, carry=(("iron", 1), ("charcoal", 1), ("ash-haft", 2)))
    _blank(e, pc)
    smith, _ = _smith(e)
    from rules import attitude, requests

    attitude.set_regard(smith, 95, "test")
    dc, _basis = requests.dc(smith, requests.FAVOUR, e.scene.clock_minutes)
    res = e.run(e.validate([{"op": "commission", "actor": "pc", "because": "t",
                             "params": {"who": smith.ref, "item": "the dagger",
                                        "haggle": True}}]))
    assert res.awaiting and "Diplomacy" in str(res.awaiting), res.awaiting
    res = e.resume(20)
    out = next(o for o in res.outcomes if o.op == "commission")
    eff = out.effects[0]
    assert "haggles" in out.tell and "comes down" in out.tell, out.tell
    assert eff["cp"] < eff["listed_cp"] and "to the haggle" in out.tell and "listed" in out.tell
    assert any(r.label.startswith("Diplomacy") for r in out.rolls)
    # Once a day with a keeper: the second ask holds to the same price, no roll.
    again = e.run(e.validate([{"op": "commission", "actor": "pc", "because": "t",
                               "params": {"who": smith.ref, "item": "the dagger",
                                          "haggle": True}}]))
    assert not again.awaiting


def test_ruling_a_counter_haggle_won_today_holds_for_the_commission(world):
    """The trade panel's Haggle (Profession, the owner's option B) writes the day's
    percent with this keeper; the commission bill reads the same record — under the one
    key every door keeps a shop by (`market.stall_of`, audit #13), where this test once
    wrote an arbitrary "stall-1" that a search by keeper ref had to find."""
    e, pc = _engine(world, carry=(("iron", 1), ("charcoal", 1), ("ash-haft", 2)))
    _blank(e, pc)
    smith, _ = _smith(e)
    from rules import market, tradecraft

    day = market.day_of(e.scene.clock_minutes)
    e.scene.dealings[tradecraft.dealing_key("haggle", pc.ref, e.scene.location_id,
                                            market.stall_of(e.scene, smith), day)] = {
        "percent": 20, "keeper": smith.ref}
    out = _commission(e, smith)
    eff = out.effects[0]
    assert eff["cp"] == commission._undercut(eff["listed_cp"], 20), eff


def test_ruling_an_offer_read_as_tried_asks_for_the_haggle(world):
    e, pc = _engine(world, carry=(("iron", 1), ("charcoal", 1), ("ash-haft", 2)))
    smith, _ = _smith(e)
    rows = acts_to_ops.table({"question": False, "claims": [], "actions": [
        {"act": "commission", "target": "the smith", "object": "the dagger",
         "commit": "tried", "span": "offer the smith five silver to fit it"}]},
        e.scene, places=tuple(e.places()))
    assert rows[0].intents[0]["params"].get("haggle") is True


def test_ruling_the_plans_haggle_at_the_keeper_becomes_the_commissions_haggle(world):
    """Measured live 2026-11-01 on the owner's save: "I offer the smith five silver to fit a
    haft to my trident blank" was read as a commission done (not tried) and planned with a
    `haggle` at the smith — refused as untrained Profession, the job taken at list price.
    The plan's haggle at the keeper the table commissioned is folded into the commission."""
    e, pc = _engine(world)
    smith, _ = _smith(e)
    row = acts_to_ops.Row(index=0, act="commission")
    row.intents = [{"op": "commission", "actor": "pc",
                    "params": {"who": smith.ref, "item": "my trident blank"},
                    "because": "the player pays the smith"}]
    frame = {"question": False, "claims": [], "actions": [
        {"act": "commission", "target": "the smith", "object": "my trident blank",
         "span": "offer the smith five silver to fit a haft"}]}
    plan = [{"op": "haggle", "actor": "pc", "target": smith.ref, "params": {},
             "because": "bargaining"}]
    out = acts_to_ops.apply(plan, [row], frame, e.scene)
    assert not [r for r in out if r["op"] == "haggle"], out
    com = next(r for r in out if r["op"] == "commission")
    assert com["params"].get("haggle") is True


def test_ruling_the_plans_diplomacy_at_the_keeper_is_the_commissions_haggle(world):
    """Measured live 2026-11-01 on the integration build: "I ask the smith to finish my
    trident for me, and I try to talk him down on the price" was read as a commission beside
    a tried talk; the plan wrote a plain Diplomacy check at the smith, it made DC 14 by 2,
    the smith warmed, and the job was taken at the full list price. The plan's Diplomacy at
    the keeper the table commissioned is the haggle; a Diplomacy at somebody else is not."""
    e, pc = _engine(world)
    smith, _ = _smith(e)
    row = acts_to_ops.Row(index=0, act="commission")
    row.intents = [{"op": "commission", "actor": "pc",
                    "params": {"who": smith.ref, "item": "my trident"},
                    "because": "the player pays the smith"}]
    frame = {"question": False, "claims": [], "actions": [
        {"act": "commission", "target": "the smith", "object": "my trident",
         "span": "ask the smith to finish my trident for me"},
        {"act": "talk", "commit": "tried", "target": "him", "says": "down on the price",
         "span": "try to talk him down on the price"}]}
    plan = [{"op": "check", "actor": "pc", "target": smith.ref,
             "params": {"skill": "diplomacy"}, "because": "talking him down"},
            {"op": "check", "actor": "pc", "target": "c-somebody-else",
             "params": {"skill": "diplomacy"}, "because": "a word with a stranger"}]
    out = acts_to_ops.apply(plan, [row], frame, e.scene)
    checks = [r for r in out if r["op"] == "check"]
    assert [c["target"] for c in checks] == ["c-somebody-else"], out
    com = next(r for r in out if r["op"] == "commission")
    assert com["params"].get("haggle") is True


@pytest.mark.parametrize("collected", [True, False])
def test_a_second_commission_holds_only_the_new_piece(world, monkeypatch, collected):
    """Audit #12, measured on 0.2.26: the keeper's dagger stacked onto the identical dagger
    the player already owned (`blacksmith.put`), and `inprogress.begin` locked the whole
    stack — yesterday's collected dagger became "still finishing". With the first job not
    yet collected, `begin` refused the new one after the fee had been taken: paid for
    nothing. The new piece is split onto its own key first (`inprogress.set_apart`)."""
    from rules import goods

    e, pc = _engine(world, carry=(("iron", 2), ("charcoal", 2), ("ash-haft", 4)))
    monkeypatch.setattr(commission, "keeper_roll",
                        lambda engine, keeper, step: _Face(int(step.dc) + 2)(engine, keeper,
                                                                             step))
    _blank(e, pc)
    smith, smithy = _smith(e)
    level = pc.track("blacksmith").level
    first = _commission(e, smith)
    assert first.status == "resolved", first.tell
    if collected:
        e.scene.clock_minutes += first.effects[0]["minutes"]
        (key,) = [k for k, st in pc.stock.items() if st.name == "Iron Dagger"]
        assert inprogress.collect(pc, key, now=e.scene.clock_minutes,
                                  here=smithy.id)["ok"]
    _make(e, "blacksmith", "a dagger", faces=(15, 1))
    # The record carries the forging track's level, and making the second blank raised it:
    # put back, the keeper's second dagger is the first one's exact twin, which stacks.
    pc.track("blacksmith").level = level
    purse = goods.in_copper(pc.purse)
    second = _commission(e, smith)
    assert second.status == "resolved", second.tell
    assert second.effects[0]["items"] == ["Iron Dagger"], second.tell
    assert goods.in_copper(pc.purse) == purse - second.effects[0]["cp"]
    now = e.scene.clock_minutes
    daggers = _named(pc, "Iron Dagger")
    assert sum(int(d.count) for d in daggers) == 2
    held = [d for d in daggers if inprogress.work_of(d, now) is not None]
    free = [d for d in daggers if inprogress.work_of(d, now) is None]
    if collected:
        assert len(held) == 1 and held[0].count == 1, "the owned dagger was locked too"
        assert len(free) == 1 and free[0].count == 1
    else:
        assert len(held) == 2 and all(d.count == 1 for d in held)


def test_a_haggle_lost_at_the_counter_holds_for_the_commission(world):
    """Audit #13: the trade panel's Haggle keyed the day's record by the keeper's name
    (the stall the panel sends), the commission by the keeper's ref, and the commission
    only looked for a WON haggle across keys — so a haggle lost at the counter was asked
    again through the commission, and rolled. Once a day with a keeper, win or lose."""
    import re

    e, pc = _engine(world, carry=(("iron", 1), ("charcoal", 1), ("ash-haft", 2)))
    _blank(e, pc)
    smith, _ = _smith(e)
    from rules import market, tradecraft

    # What the panel's Haggle (`/api/tradeskill`, the engine's `haggle` with the panel's
    # stall) writes when the keeper is not moved: the day's record, at no percent.
    stall = re.sub(r"[^a-z0-9]+", "-", smith.name.lower()).strip("-")
    e.scene.dealings[tradecraft.dealing_key(
        "haggle", pc.ref, e.scene.location_id, stall,
        market.day_of(e.scene.clock_minutes))] = {"percent": 0, "keeper": smith.ref}
    again = e.run(e.validate([{"op": "commission", "actor": "pc", "because": "t",
                               "params": {"who": smith.ref, "item": "the dagger",
                                          "haggle": True}}]))
    assert not again.awaiting, "the lost haggle was rolled again at the commission"
    assert "already been haggled" in again.outcomes[0].tell
