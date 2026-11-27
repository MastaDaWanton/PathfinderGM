"""Feat loop batch 4, lane b4-crafting (2026-11-26): the feats that needed an item creation
feat the owner retired, stripped of it and reworked for the benches.

The owner, 2026-11-26: "any feat that requires a crafting feat that we removed, strip that
requirement and allow it to be taken and reworked to fit our systems." Measured on
integrate/feats-b3 71e7ce50 before this lane: Cypher Magic (Scribe Scroll), Create Sanguine
Elixir (Brew Potion), Create Reliquary Arms and Shields (Craft Magic Arms and Armor) and
Cooperative Crafting ("any item creation feat") answered `meets` ok False for every
character, since no sheet can hold a retired feat; Cooperative Crafting's "1 rank in any
Craft skill" was also read as a skill called "any craft skill", so a smith with 10 Craft
ranks was refused it, and Master Craftsman's "any Craft or Profession skill" the same.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from rules import (class_abilities, classbuilder, cooperative, enchanter as en, feats,
                   grantedpowers, inprogress, reliquary, sanguine, spellitems, tradecraft)
from rules.activeeffect import ActiveEffect
from rules.dice import Dice
from rules.engine import Engine, Scene
from rules.intents import IntentError
from rules.states import TRAVELS_WITH_YOU
from tests.test_class_active_abilities import _fight, _pc, _use


def test_the_lane_file_validates():
    doc = json.loads(Path("content/feats/mechanics/b4-crafting.json").read_text("utf-8"))
    assert classbuilder.validate_feat_documents(
        {k: v for k, v in doc.items() if not k.startswith("_")}) == []


# --- the prerequisites ---------------------------------------------------------------------

def test_no_feat_asks_for_a_retired_item_creation_feat():
    """Four feats named a retired feat (or "any item creation feat") and could never be
    taken. None does now, structured or as unparsed text."""
    for feat in feats.all_feats().values():
        named = {c.get("feat") for c in feat.prerequisites if c.get("kind") == "feat"}
        assert not named & feats.RETIRED, feat.id
        assert "any item creation feat" not in [
            str(t).strip().lower() for t in feat.unparsed_prerequisites], feat.id


def _sorcerer(level=5, bloodline="aberrant", **extra):
    pc = _pc("sorcerer", level, class_choices={"bloodline": {
        "option": "class option", "picks": [{"pick": bloodline, "level": 1}]}}, **extra)
    pc.abilities["cha"] = 16
    pc.ranks = {"craft": 12}
    pc.purse = {"gp": 500}
    return pc


def _cleric(level=5, **extra):
    pc = _pc("cleric", level, **extra)
    pc.abilities["wis"] = 16
    return pc


def test_each_reworked_feat_is_taken_by_whoever_meets_the_rest():
    wizard = _pc("wizard", 1)
    wizard.abilities["int"] = 15
    assert feats.meets(wizard, "cypher-magic")["ok"]
    wizard.abilities["int"] = 14
    assert feats.meets(wizard, "cypher-magic")["unmet"] == ["Int 15"]

    assert feats.meets(_sorcerer(), "create-sanguine-elixir")["ok"]
    low = _sorcerer()
    low.ranks = {"craft": 11}
    assert feats.meets(low, "create-sanguine-elixir")["unmet"] == ["12 ranks in Craft (Alchemy)"]

    # "ability to cast consecrate or desecrate": a 3rd-level cleric casts 2nd-level spells,
    # a 2nd-level cleric does not yet.
    assert feats.meets(_cleric(3), "create-reliquary-arms-and-shields")["ok"]
    assert feats.meets(_cleric(2), "create-reliquary-arms-and-shields")["unmet"] == [
        "able to cast Consecrate or Desecrate"]
    assert not feats.meets(_pc("fighter", 9), "create-reliquary-arms-and-shields")["ok"]

    smith = _pc("fighter", 1)
    smith.ranks = {"craft": 1}
    assert feats.meets(smith, "cooperative-crafting")["ok"]
    smith.ranks = {}
    assert not feats.meets(smith, "cooperative-crafting")["ok"]


def test_any_craft_or_profession_reads_the_best_of_them():
    """Master Craftsman's "5 ranks in any Craft or Profession skill" was never met."""
    pc = _pc("fighter", 5)
    pc.ranks = {"profession": 5}
    assert feats.meets(pc, "master-craftsman")["ok"]


def test_mythic_crafter_still_waits_on_mythic_tiers():
    """Its "any item creation feat" went with the others, but the picker still refuses
    every mythic feat: this game has no mythic tiers."""
    from rules import creation

    rows = creation.feat_rows(_pc("fighter", 1))
    shut = next(r for r in rows["shut"] if r["id"] == "mythic-crafter")
    assert shut["unmet"] == ["a mythic tier, which this game has none of"]


def test_the_picker_offers_the_reworked_feats():
    """The feat picker's own rows (`creation.feat_rows`, the forge's and the level-up's):
    each reworked feat is open to a character who meets the rest."""
    from rules import creation

    def opened(pc):
        return {r["id"] for r in creation.feat_rows(pc)["open"]}

    sorc = _sorcerer()
    sorc.abilities["int"] = 15
    assert {"cypher-magic", "create-sanguine-elixir", "cooperative-crafting"} <= opened(sorc)
    assert "create-reliquary-arms-and-shields" in opened(_cleric(3))


# --- Cypher Magic --------------------------------------------------------------------------

def test_cypher_magic_lifts_a_scroll_scribed_at_the_circle():
    """"This benefit extends to scrolls that you have created": a scroll of mage armor
    scribed at the enchanting circle (CL 1) reads at CL 2 for a Cypher Magic wizard — two
    hours of armour, 1,200 rounds, not one."""
    from tests.test_spell_items import _circle_wizard

    pc, prog = _circle_wizard()
    pc.feats.append("cypher magic")
    plan = en.plan_step(pc, prog, "scroll", {"spell": "mage-armor",
                                              "blank": "inv:scroll-vellum",
                                              "ink": "inv:silver-ink"})
    assert plan.problems == []
    got = en.finish(pc, prog, plan, 1, now=0)
    key = got["products"][0]["key"].split(":", 1)[1]
    st = pc.stock[key]
    assert spellitems.kind_of(st) == "scroll"
    inprogress.collect(pc, key, now=200, here=None)
    s = Scene(location_id="5bbd0c40345f")
    s.add(pc)
    e = Engine(s, Dice(seed=3))
    e.run(e.validate([{"op": "use_item", "actor": "pc",
                       "params": {"item": st.name, "power": "mage-armor"}}]))
    armour = next(x for x in pc.effects if x.source == "Mage Armor" or x.name == "Mage Armor")
    assert armour.rounds_left == 1200


# --- Create Sanguine Elixir ----------------------------------------------------------------

def _bottle(pc, power="acidic ray", now=1000):
    assert sanguine.refusal(pc, power, where={"kit": True}) == ""
    return sanguine.make(pc, power, now=now)


def test_bottling_costs_100_gp_and_lends_the_power_until_rest():
    """The sorcerer "lose[s] access to the bloodline power until the next time you clear
    your mind to regain spell slots", and makes one a day."""
    pc = _sorcerer(feats=["Create Sanguine Elixir"])
    assert [r["power"]["key"] for r in grantedpowers.had(pc)] == ["acidic ray", "long limbs"]
    _bottle(pc)
    assert pc.purse == {"gp": 400}
    assert [r["power"]["key"] for r in grantedpowers.had(pc)] == ["long limbs"]
    assert "Acidic Ray" not in [d.get("name") for d in class_abilities._docs_for(pc)]
    assert "since your last rest" in sanguine.refusal(pc, "long limbs", where={"kit": True})
    elixir = next(s for s in pc.stock.values() if s.craft == sanguine.CRAFT)
    assert elixir.spoils_minute == 1000 + 24 * 60
    pc.rest("night")
    assert [r["power"]["key"] for r in grantedpowers.had(pc)] == ["acidic ray", "long limbs"]
    assert sanguine.refusal(pc, "acidic ray", where={"kit": True}) == ""


def test_the_bench_refuses_without_the_feat_the_kit_or_the_coin():
    pc = _sorcerer()
    assert "does not have" in sanguine.refusal(pc, "acidic ray", where={"kit": True})
    pc = _sorcerer(feats=["Create Sanguine Elixir"])
    assert "field kit" in sanguine.refusal(pc, "acidic ray", where={})
    assert "not one of your bloodline powers" in sanguine.refusal(
        pc, "breath weapon", where={"kit": True})
    pc.purse = {"gp": 99}
    assert "100 gp" in sanguine.refusal(pc, "acidic ray", where={"kit": True})


def _drink(maker, clock=1100, level=3):
    friend = _pc("fighter", level)
    key = next(k for k, s in maker.stock.items() if s.craft == sanguine.CRAFT)
    friend.stock[key] = maker.stock[key]
    scene, e = _fight(friend, "thug")
    scene.clock_minutes = clock
    out = e.run(e.validate([{"op": "use_item", "actor": "pc", "because": "test",
                             "params": {"item": key}}])).outcomes
    return friend, scene, e, out


def test_the_drinker_uses_the_power_once_at_the_lower_level():
    """A 3rd-level fighter drinking a 5th-level sorcerer's acidic ray spits it at level 3
    — 1d6 + floor(3/2) — once, before the end of the next turn."""
    maker = _sorcerer(feats=["Create Sanguine Elixir"])
    _bottle(maker)
    friend, scene, e, out = _drink(maker)
    assert "gains Acidic Ray" in out[-1].tell
    assert [(r["power"]["key"], r["level"]) for r in grantedpowers.had(friend)] == [
        ("acidic ray", 3)]
    ray = next(d for d in class_abilities._docs_for(friend) if d.get("key") == "acidic ray")
    # Read at the drinker's own level 3: 1d6 + 1, never the sorcerer's 1d6 + 2.
    assert ray["roll"]["bonus"] == "floor(level / 2)"
    scene.round += 1
    hit = _use(e, "Acidic Ray", to="c1")
    assert hit.status == "resolved" and "1d6+1" in hit.tell
    again = _use(e, "Acidic Ray", to="c1")
    assert again.status == "refused"
    # The borrow is a two-round effect: gone after the drinker's next turn.
    eff = next(x for x in friend.effects if any(t.startswith(sanguine.BORROWED)
                                                for t in x.tags))
    assert eff.rounds_left <= sanguine.ROUNDS


def test_too_low_a_drinker_gains_nothing_and_a_day_old_elixir_is_spent():
    maker = _sorcerer(level=9, feats=["Create Sanguine Elixir"])
    _bottle(maker, "unusual anatomy")
    friend, *_ = _drink(maker, level=5)
    assert grantedpowers.had(friend) == []
    maker = _sorcerer(feats=["Create Sanguine Elixir"])
    _bottle(maker)
    friend, scene, e, out = _drink(maker, clock=1000 + 24 * 60)
    assert out[-1].status == "refused" and "lost its potency" in out[-1].tell
    assert grantedpowers.had(friend) == []


def test_a_model_cannot_lend_itself_a_bloodline_power():
    """The borrowed tag is honoured only from a stamped item: a planned `grant` naming it
    is refused, and nothing is borrowed."""
    pc = _pc("fighter", 5)
    scene, e = _fight(pc, "thug")
    with pytest.raises(IntentError):
        e.validate([{"op": "grant", "actor": "pc", "because": "x", "params": {
            "tag": "borrowed.bloodline.acidic-ray",
            "borrowed": {"bloodline": "aberrant", "power": "acidic ray", "level": 5}}}])
    assert grantedpowers.had(pc) == []


# --- Create Reliquary Arms and Shields ------------------------------------------------------

def test_a_reliquary_spends_the_casting_and_the_coin_and_adds_250_gp():
    """At the circle's Bind: a cleric who prepared consecrate casts it into arms, pays
    125 gp (half the 250 gp the price rises by), and the binding records the spell."""
    from rules import magic_layer

    pc = _cleric(5, feats=["Create Reliquary Arms and Shields"])
    pc.prepared = {"consecrate": 1}
    pc.rebuild_pools()
    pc.purse = {"gp": 200}
    assert reliquary.refusal(pc, "consecrate", "weapon") == ""
    assert "Only a weapon" in reliquary.refusal(pc, "consecrate", "wondrous")
    assert "cannot cast Desecrate" in reliquary.refusal(pc, "desecrate", "weapon") \
        or "not prepared" in reliquary.refusal(pc, "desecrate", "weapon")
    reliquary.spend(pc, "consecrate")
    assert pc.purse == {"gp": 75}
    assert pc.prepared.get("consecrate", 0) == 0
    assert "not prepared" in reliquary.refusal(pc, "consecrate", "weapon")
    rec = {"weapon": "longsword", "masterwork": True,
           "magic": {"enhancement": 1, "binding": {"reliquary": "consecrate"}}}
    plain = {"weapon": "longsword", "masterwork": True, "magic": {"enhancement": 1}}
    gear = magic_layer.vessel_kind(rec)
    assert magic_layer.market_price(magic_layer.magic_of(rec), gear) == \
        magic_layer.market_price(magic_layer.magic_of(plain), gear) + 250
    assert reliquary.of(rec) == "consecrate" and reliquary.of(plain) == ""


def test_without_the_feat_bind_refuses_a_reliquary():
    pc = _cleric(5)
    assert "does not have" in reliquary.refusal(pc, "consecrate", "weapon")


# --- Cooperative Crafting ------------------------------------------------------------------

def _companion(name="Bob", craft=1, feats_=()):
    pal = _pc("fighter", 3, ref="ally")
    pal.name, pal.kind = name, "npc"
    pal.ranks = {"craft": craft}
    pal.feats = list(feats_)
    pal.apply_effect(ActiveEffect(name="Travels with you", kind="effect", key="bond",
                                  tags=(TRAVELS_WITH_YOU,)))
    return pal


def _crafter(feats_=("Cooperative Crafting",), craft=2):
    pc = _pc("fighter", 4)
    pc.ranks = {"craft": craft}
    pc.feats = list(feats_)
    return pc


def _labels(pc):
    return [t["label"] for t in tradecraft.bench_check_terms(
        pc, 1, track="blacksmith", name="Blacksmith", ability="int")]


def test_a_companion_who_crafts_gives_plus_two_and_halves_the_time():
    """+2 circumstance on the bench check, named for the helper, and work In progress
    takes half the time ("doubles the gp value of items that can be crafted each day")."""
    pc, pal = _crafter(), _companion()
    s = Scene()
    s.add(pc)
    s.add(pal)
    cooperative.settle(s, pc)
    terms = tradecraft.bench_check_terms(pc, 1, track="blacksmith", name="Blacksmith",
                                         ability="int")
    assert {"label": "Cooperative Crafting (Bob)", "value": 2} in terms
    assert cooperative.minutes(pc, 121, craft="blacksmith") == 61
    assert cooperative.minutes(pc, 121, craft="commission") == 121
    # The companion leaves: the next bench opened lifts the help.
    s.remove(pal.ref)
    cooperative.settle(s, pc)
    assert not any("Cooperative" in label for label in _labels(pc))


def test_either_crafter_may_hold_it_and_both_need_the_craft():
    s = Scene()
    pc = _crafter(feats_=())
    s.add(pc)
    s.add(_companion(feats_=["Cooperative Crafting"]))
    cooperative.settle(s, pc)
    assert "Cooperative Crafting (Bob)" in _labels(pc)
    s2 = Scene()
    pc2 = _crafter()
    s2.add(pc2)
    s2.add(_companion(craft=0))
    cooperative.settle(s2, pc2)
    assert not any("Cooperative" in label for label in _labels(pc2))
    s3 = Scene()
    pc3 = _crafter(feats_=())
    s3.add(pc3)
    s3.add(_companion())
    cooperative.settle(s3, pc3)
    assert not any("Cooperative" in label for label in _labels(pc3))


def test_the_helpers_spell_stands_in_at_the_circle():
    """"Either one of you can fulfill any other prerequisites": a spell the helper can cast
    is one the enchanter need not know, so its +5 DC goes."""
    pc = _crafter()
    helper = _companion()
    helper.char_class, helper.level = "cleric", 5
    helper.abilities["wis"] = 16
    s = Scene()
    s.add(pc)
    s.add(helper)
    assert en._spells_known(pc, {"bless"}) == set()
    cooperative.settle(s, pc)
    assert en._spells_known(pc, {"bless"}) == {"bless"}
