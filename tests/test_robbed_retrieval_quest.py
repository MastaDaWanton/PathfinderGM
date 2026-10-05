"""Robbed while down: a share of the coin, one thing worth taking, and a quest to get it back.

The owner's ruling, 2026-10-05: when robbers beat you down they take "a percentage of your
coin and 1 item they would want. a quest to retrieve the gold and the item should be
created."

Measured before it, on the rebuilt warrens scene (`tests/test_robbers_after_the_fight.py`,
the owner's 2026-10-04 robbery): the robbers took ALL 30 gp and nothing else, and no quest
was made — the player woke with an empty purse, the rapier still on their belt, and
nothing in the Journal to say who had their money or where they went. The coin sat in the
robber's purse off stage, at a place no door led to.

The design and its sources are in `rules/defeat.py`. Every scene here is built from the
same measured shape: Kesst (rapier and dagger), 30 gp, two street thugs.
"""
from __future__ import annotations

import copy

from play import downed
from rules import cards, defeat, goods, heard_places, residency
from rules.bestiary import instantiate
from rules.crafting import Stock
from rules.dice import Dice
from rules.engine import Engine, Scene
from rules.sheet import load_pc

WARRENS = "5bbd0c40345f~urban:the-warrens"


def _lane(seed=3, robbers=2):
    s = Scene(location_id="5bbd0c40345f")
    s.stand(WARRENS)
    pc = s.add(load_pc("fixtures/pc-kesst.json"))
    pc.purse = {"gp": 30}
    gang = [s.add(instantiate("street-thug", scene=s, name=n))
            for n in ("the robber", "the second robber", "the third robber")[:robbers]]
    e = Engine(s, Dice(seed=seed))
    e.run(e.validate([{"op": "begin_encounter", "because": "test",
                       "params": {"sides": {"party": [pc.ref],
                                            "robbers": [a.ref for a in gang]}}}]))
    return s, e, pc, gang


def _beaten(s, pc):
    pc.hp = -2
    pc.apply_hp_state()
    pc.remove_condition("dying")
    pc.add_condition("stable")
    s.end_encounter()


class _Campaign:
    def __init__(self, scene, engine):
        self.scene, self._engine = scene, engine

    def engine(self):
        return self._engine


def _robbed(robbers=2, before=None):
    s, e, pc, gang = _lane(robbers=robbers)
    if before is not None:
        before(s, e, pc, gang)
    _beaten(s, pc)
    out = downed.resolve(_Campaign(s, e))
    quest = next(c for c in cards.quests(s) if c.recover)
    return s, e, pc, gang, out, quest


def _tick(e):
    """One batch that does nothing but let the world settle — the tick every turn ends on."""
    return e.run(e.validate([{"op": "narrate_only", "because": "time passes"}]))


# --- the robbery ----------------------------------------------------------------------------

def test_a_share_of_the_coin_one_thing_and_a_quest_not_all_the_coin_and_nothing():
    """Measured before the ruling: the robbers took all 30 gp and nothing else, and no
    quest was made. Now two robbers take three quarters of the coin (22 of 30 gp; the odd
    coin is the one the search missed) and the rapier — the most valuable thing Kesst
    carries that a fence would pay for — and a quest is in the Journal."""
    s, e, pc, gang, out, quest = _robbed()
    robber, second = gang
    assert pc.purse == {"gp": 8}, "a share, never the whole purse"
    assert robber.purse.get("gp") == 22, "the share is in the robber's own purse"
    assert "rapier" not in pc.weapons and "rapier" in robber.weapons
    assert "dagger" in pc.weapons, "one thing, not the belt"
    assert "The robber took 22 of your 30 gold pieces, and your rapier." in out.lines
    assert "The robber and the second robber have gone." in out.lines
    said = " ".join(out.lines)
    assert "You mean to get it back" in said and quest.title in said
    # The quest, through the one quest store the Journal reads.
    log = cards.quest_log(s)
    row = next(r for r in log["active"] if r["id"] == quest.id)
    assert row["title"] == "Get back what the robber and the second robber took"
    assert [o["text"] for o in row["objectives"]] == [
        "Get your rapier back from the robber", "Get back the 22 gold pieces the robber took"]
    assert quest.origin == defeat.QUEST_ORIGIN
    assert set(quest.people) == {robber.ref, second.ref}, "the robbers by ref"
    rec = quest.recover
    assert rec["robber"] == robber.ref and rec["coin_cp"] == 2200
    assert residency.is_offstage(rec["where"]) and robber.at == rec["where"]
    assert {x["kind"] for x in out.effects} == {"took", "left", "quest"}


def test_the_share_grows_with_the_hands_and_never_takes_it_all():
    """A hasty search of a body in a street finds the purse and misses the coin in a boot:
    one robber half, each further robber a quarter more, never more than three quarters.
    Counted coin by coin, rounded down, no change made."""
    from fractions import Fraction

    assert defeat.coin_share(0) == 0
    assert defeat.coin_share(1) == Fraction(1, 2)
    assert defeat.coin_share(2) == Fraction(3, 4)
    assert defeat.coin_share(5) == Fraction(3, 4)
    assert defeat.take_coin({"gp": 30, "sp": 3, "cp": 1}, Fraction(1, 2)) == {"gp": 15, "sp": 1}
    s, e, pc, gang, out, quest = _robbed(robbers=1)
    assert pc.purse == {"gp": 15} and gang[0].purse.get("gp") == 15


def test_worn_armour_and_what_cannot_be_run_with_are_never_the_thing_taken():
    """The owner's limit: never a worn suit of armour mid-body. Kesst's leather (10 gp) is
    worth less than the rapier anyway, so the measured case is a chain shirt WORN beside a
    spare one in the pack: the worn one stays on, the spare is fair game. A thing heavier
    than the robber's spare light load (CRB Table 7-4) is left: they are leaving."""
    s, e, pc, gang = _lane()
    robber = gang[0]
    pc.armour = "chain shirt"
    pc.goods = {"chain shirt": 1}
    assert defeat.the_take(pc, robber)["name"] == "rapier", "100 gp, but on the body"
    things = {c["name"] for c in defeat.carried_things(pc)}
    assert "chain shirt" not in things, "the one on the body is worn, not carried"
    pc.goods = {"chain shirt": 2}
    assert defeat.the_take(pc, robber)["name"] == "chain shirt", "the spare, 100 gp"
    robber.abilities["str"] = 3                     # light load 10 lb; the shirt is 25
    took = defeat.the_take(pc, robber)
    assert took is not None and took["name"] == "rapier"


def test_a_forged_enchanted_blade_is_valued_by_its_working_and_taken_whole():
    """A forged or enchanted thing counts by its value: the base row, the book's
    masterwork price and its enhancement's market price (15 + 300 + 2,000 gp for a +1
    longsword), where `pricing.worth` alone priced it as an untiered jar at 1.5 gp. And it
    goes into the robber's hands as the record it is, every field kept."""
    def give_blade(s, e, pc, gang):
        pc.add_stock(Stock(base="Vayr's Blade", tier="rare", weapon="longsword",
                           masterwork=True, enhancement=1, properties=["keen-edged"],
                           kind="crafted", craft="enchanter"), 1)

    s, e, pc, gang, out, quest = _robbed(before=give_blade)
    robber = gang[0]
    assert "Vayr's Blade" in " ".join(out.lines)
    assert "rapier" in pc.weapons, "the blade was worth more, so the rapier stays"
    sid = quest.recover["item"]["key"]
    held = robber.stock[sid]
    assert (held.weapon, held.masterwork, held.enhancement, held.properties) == \
        ("longsword", True, 1, ["keen-edged"])
    assert sid not in pc.stock
    assert defeat.stock_worth(held) == 15 + 300 + 2000


def test_the_hideout_is_a_heard_of_place_and_the_robbers_are_in_it_once_it_is_real():
    """Where they went: a place heard of, off where it happened, made real through the
    place doors (`found`, which `judgement.go_to_heard_place` writes when the player goes
    there). Until it exists the robbers are off stage; the batch it is founded in, they
    are in it — so going there finds them."""
    s, e, pc, gang, out, quest = _robbed()
    hideout = quest.recover["hideout"]
    assert hideout == "the robber's hideout"
    rec = next(h for h in s.heard_places if h["name"] == hideout)
    assert rec["landmark"] == WARRENS
    assert heard_places.named_in("I go to the robber's hideout", s, e.places()) is not None
    # Off the lane: with no world loaded the warrens is not one of this test town's
    # places, and the hideout's landmark only steers `go_to_heard_place` when it is.
    e.run(e.validate([{"op": "found", "actor": pc.ref,
                       "params": {"name": hideout, "parent": "the lane"},
                       "because": "the player went there"}]))
    place = next(p for p in s.founded if p["name"] == hideout)
    assert all(a.at == place["id"] for a in gang)
    e.run(e.validate([{"op": "travel", "actor": pc.ref, "params": {"place": hideout},
                       "because": "test"}]))
    assert all(a.ref in s.actors for a in gang), "found there"


# --- the way back ---------------------------------------------------------------------------

def test_beating_them_and_stripping_the_body_gets_it_all_back_and_finishes_the_quest():
    """The commonest road back: find them, beat the one who has it, strip the body. The
    loot moved the weapons list, the armour, the purse, the satchel and the shelf — and
    left the GOODS on the body until this was built — and nothing measured the quest."""
    s, e, pc, gang, out, quest = _robbed()
    robber = gang[0]
    s.move(robber.ref, s.at)                       # met again, wherever it is
    robber.hp = -20
    robber.apply_hp_state()
    res = e.run(e.validate([{"op": "loot", "actor": pc.ref,
                             "params": {"from_": robber.ref}, "because": "test"}]))
    assert "rapier" in pc.weapons and pc.purse.get("gp", 0) >= 30
    card = cards.find(s, quest.id)
    assert card.stage == "resolved", [o["done"] for o in card.objectives]
    told = " ".join(o.tell for o in res.outcomes)
    assert "You have your rapier back." in told
    # The coin by the words it was taken in: a tick that named the world's coin afresh,
    # with no place to name it by, called 22 Kragmoor gold "22 Ashgate gold" live.
    assert f"The robber no longer has your {quest.recover['coin_said']}." in told
    assert "is finished" in told
    prop = next(p for p in s.props if p["name"] == "Kesst Vayr's rapier")
    assert prop["held_by"] == pc.ref and not prop.get("stolen")


def test_a_rapier_bought_at_a_shop_is_not_the_rapier_they_took():
    """Measured on the holdings, never the means — and the holdings say the robber still
    has the original. A replacement does not tick the objective."""
    s, e, pc, gang, out, quest = _robbed()
    goods.stow(pc, "rapier", 1)
    _tick(e)
    card = cards.find(s, quest.id)
    assert not card.objectives[0]["done"]
    assert card.live


def test_handed_back_by_the_robber_counts_and_he_no_longer_holds_it():
    """Paid or persuaded: the robber hands the rapier and the coin back. A handover read
    only the goods, so "the robber hands back the rapier" took one out of the air while
    he kept his on the weapons list — and the objective could never tick."""
    s, e, pc, gang, out, quest = _robbed()
    robber = gang[0]
    s.move(robber.ref, s.at)
    e.run(e.validate([
        {"op": "give", "actor": robber.ref, "params": {"item": "rapier", "to": pc.ref},
         "because": "persuaded"},
        {"op": "give", "actor": robber.ref,
         "params": {"item": "gp", "count": 22, "to": pc.ref}, "because": "persuaded"}]))
    assert "rapier" not in robber.weapons and "rapier" in pc.weapons
    card = cards.find(s, quest.id)
    assert [o["done"] for o in card.objectives] == [True, True]
    assert card.stage == "resolved"


def test_a_shelf_record_handed_over_keeps_its_record():
    """A forged blade on somebody's shelf, handed over, arrived as a goods line with its
    name and nothing else — no pieces, no working, no enchantment."""
    s, e, pc, gang = _lane()
    robber = gang[0]
    blade = Stock(base="Vayr's Blade", tier="rare", weapon="longsword", masterwork=True,
                  enhancement=1, kind="crafted", craft="enchanter")
    robber.add_stock(copy.deepcopy(blade), 1)
    sid = next(iter(robber.stock))
    e.run(e.validate([{"op": "give", "actor": robber.ref,
                       "params": {"item": "Vayr's Blade", "to": pc.ref}, "because": "test"}]))
    assert sid in pc.stock and pc.stock[sid].enhancement == 1
    assert "Vayr's Blade" not in pc.goods


def test_the_quest_survives_a_save_and_a_load():
    """The quest's record of its target rides on the card (`Card.recover`), so the way
    back is measured the same after the app restarts."""
    s, e, pc, gang, out, quest = _robbed()
    again = cards.Card.from_dict(quest.as_dict())
    assert again.recover == quest.recover
    plain = cards.Card(id="x", title="y")
    assert "recover" not in plain.as_dict(), "a card without one round-trips unchanged"
