"""A people the page granted in reply binds the next person made there (owner ruling F2).

The measured case, Sam's save turns 22-23 (docs/playtest-2026-09-30-findings.md item 10):
the player asked the barkeep "any human women here?"; Gorm answered "There is one," and the
narrator described a woman humming behind the curtain. Two turns later the chamber behind
it was founded and its keeper minted — **Quin Nutmeg, with a Ratfolk face** — and the prose
went from human hair and skin to "rodent-featured eyes".

Detected in code (`rules/granted.py`, from `play/aftermath/people_granted.py`): the player's
words name a people and an NPC's line opens with a yes. The grant is an engine record (a
population record with a `granted` block); the next person minted at that place or inside
it — keeper, introduce, embody — draws that people's body, pool and gender. Precedent: the
solo tradition's oracle question, whose answer becomes the adventure's context (Mythic GME),
and "if an answer ... is obvious, interesting and dramatic, make it happen" (Ironsworn p.104).
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from gm.brief import BriefContext, peoples as brief_peoples
from play.aftermath import people_granted
from rules import faces, granted, keepers, names, places
from rules.dice import Dice
from rules.engine import Engine, Scene
from rules.sheet import load_pc
from world import loader

WORLD = loader.load_cached("fixtures/aurvantis-campaign.json")
LEDGERWARREN = WORLD.by_name("Ledgerwarren", kind="CITY").id
GATE = f"{LEDGERWARREN}~urban:the-gate"
HUMAN = next(k for k, v in names.peoples(WORLD).items() if v == "Human")
RATFOLK = names.people_of(WORLD, LEDGERWARREN)


def _run(e, plan):
    return e.run(e.validate(plan, origin="author:test"))


def _go(engine, name, parent, kind="tavern"):
    _run(engine, [{"op": "found", "because": "t",
                   "params": {"name": name, "parent": parent, "kind": kind}}])
    there = places.find(engine.places(), name)
    _run(engine, [{"op": "travel", "because": "t", "params": {"place": there.id}}])
    return there.id


@pytest.fixture
def veil():
    """The Velvet Veil, off the gate, with its barkeep behind the bar (Gorm, c8)."""
    scene = Scene(location_id=LEDGERWARREN)
    scene.add(load_pc("fixtures/pc-kesst.json"))
    engine = Engine(scene, Dice(seed=3), world=WORLD)
    engine.place_party(GATE)
    at = _go(engine, "the Velvet Veil", "the gate")
    gorm = keepers.keeper_in(scene, at)
    assert gorm is not None and gorm.world_people_id == RATFOLK
    return scene, engine, gorm


def _beat(scene, player_text, said, turn=22):
    ctx = SimpleNamespace(player_text=player_text, said=said, world=WORLD, scene=scene,
                          turn=turn)
    return people_granted.step(ctx)


def _gorm_says(gorm, *lines):
    return [{"who": gorm.ref, "to": "you", "line": line} for line in lines]


def test_quin_the_keeper_behind_the_curtain_is_the_human_woman_promised(veil):
    """Turns 22-23: "any human women here?" — "There is one," — then the chamber's keeper
    was Quin Nutmeg with a Ratfolk face. Now she is Human, a woman, named from the Human
    pool, and the grant is spent."""
    scene, engine, gorm = veil
    rows = _beat(scene, "any human women here?", _gorm_says(
        gorm, "There is one,", "But she isn't looking for company, and the one who owns "
                               "that room doesn't take kindly to interruptions."))
    assert len(rows) == 1 and rows[0]["kind"] == "people-granted"
    assert rows[0]["people"] == HUMAN and rows[0]["gender"] == "woman"
    assert rows[0]["by"] == gorm.ref
    chamber = _go(engine, "the chamber", "the Velvet Veil")
    quin = keepers.keeper_in(scene, chamber)
    assert quin is not None
    assert quin.world_people_id == HUMAN and quin.heritage == "Human"
    assert faces.people_of(quin.appearance) == "Human", quin.appearance
    assert quin.gender == "woman" and quin.pronouns == "she/her"
    assert quin.true_name.split()[0] in names.pool_for(WORLD, LEDGERWARREN, HUMAN)["given"]
    assert quin.name != quin.true_name, "and her name is still hers to give (F1)"
    assert granted.open_grants(scene) == []


def test_without_the_grant_the_chamber_keeper_is_the_towns_people(veil):
    """The control: no question, no promise — Ratfolk, as the town is."""
    scene, engine, _ = veil
    chamber = _go(engine, "the chamber", "the Velvet Veil")
    assert keepers.keeper_in(scene, chamber).world_people_id == RATFOLK


def test_introducing_the_woman_behind_the_curtain_keeps_the_promise(veil):
    scene, engine, gorm = veil
    _beat(scene, "any human women here?", _gorm_says(gorm, "There is one,"))
    _run(engine, [{"op": "introduce", "because": "t",
                   "params": {"who": "the woman humming behind the curtain"}}])
    her = next(a for a in scene.actors.values()
               if a.name == "the woman humming behind the curtain")
    assert her.world_people_id == HUMAN and faces.people_of(her.appearance) == "Human"


def test_a_man_does_not_keep_a_promise_of_a_woman(veil):
    scene, engine, gorm = veil
    _beat(scene, "any human women here?", _gorm_says(gorm, "There is one,"))
    _run(engine, [{"op": "introduce", "because": "t",
                   "params": {"who": "a man dozing by the fire"}}])
    man = next(a for a in scene.actors.values() if a.name == "a man dozing by the fire")
    assert man.world_people_id == RATFOLK
    assert len(granted.open_grants(scene)) == 1


def test_the_promise_binds_once(veil):
    scene, engine, gorm = veil
    _beat(scene, "any human women here?", _gorm_says(gorm, "There is one,"))
    _run(engine, [{"op": "introduce", "because": "t",
                   "params": {"who": "the woman in the back"}}])
    _run(engine, [{"op": "introduce", "because": "t", "params": {"how": "arrives",
                   "who": "a woman with a basket"}}])
    second = next(a for a in scene.actors.values() if a.name == "a woman with a basket")
    assert second.world_people_id == RATFOLK


@pytest.mark.parametrize("player,line", [
    ("any human women here?", "No. None of that sort here."),
    ("any human women here?", "There's no one like that,"),
    ("any human women here?", "Ask somebody else."),
    ("I order an ale.", "There is one,"),
    ("any women here?", "There is one,"),
])
def test_no_yes_or_no_people_asked_after_grants_nothing(veil, player, line):
    scene, _, gorm = veil
    assert _beat(scene, player, _gorm_says(gorm, line)) == []
    assert granted.open_grants(scene) == []


@pytest.mark.parametrize("line", ["There is one,", "Aye, in the back.", "Yes.",
                                  "We've two upstairs.", "There's a few, aye."])
def test_the_yes_forms(line):
    assert granted.affirms(line)


def test_the_player_cannot_grant_it_to_themselves(veil):
    scene, _, _ = veil
    pc = scene.pc()
    assert _beat(scene, "any human women here?",
                 [{"who": pc.ref, "to": "", "line": "There is one,"}]) == []


def test_the_brief_states_the_promise_until_it_is_kept(veil):
    scene, engine, gorm = veil
    _beat(scene, "any human women here?", _gorm_says(gorm, "There is one,"))
    ctx = BriefContext(world=WORLD, scene=scene, location=None, here=None, known=(),
                       recent_events=None, recent=None, secret=False, turn=23,
                       names_for=None, absent="", buying="", reading=None, player_text="")
    text, _ = brief_peoples.section(ctx)
    assert "PROMISED HERE" in text and "a human woman" in text and gorm.name in text
    _go(engine, "the chamber", "the Velvet Veil")
    text, _ = brief_peoples.section(ctx)
    assert "PROMISED HERE" not in text
    assert "is Human" in text


def test_human_in_a_world_with_no_human_still_binds_the_kind():
    """Pangrella has no Human people. "any humans here?" — "Aye," binds a person of
    kind Human with no world people id and no Korvu body borrowed for them."""
    pang = loader.load_cached("fixtures/pangrella-campaign.json")
    scene = Scene(location_id="5bbd0c40345f")
    scene.add(load_pc("fixtures/pc-kesst.json"))
    engine = Engine(scene, Dice(seed=3), world=pang)
    engine.place_party("5bbd0c40345f~urban:the-market")
    _run(engine, [{"op": "introduce", "because": "t", "params": {"who": "a carter"}}])
    carter = next(a for a in scene.actors.values() if a.name == "a carter")
    found = granted.detect("any humans here?", [{"who": carter.ref, "line": "Aye,"}],
                           pang, scene)
    assert found and found[0]["kind"] == "human" and not found[0]["people_id"]
    granted.grant(scene, found[0], turn=3)
    _run(engine, [{"op": "introduce", "because": "t", "params": {"how": "arrives",
                   "who": "a traveller in a dusty coat"}}])
    t = next(a for a in scene.actors.values() if a.name == "a traveller in a dusty coat")
    assert t.heritage == "Human" and t.world_people_id is None
    assert t.appearance.startswith("Human: ") and "Korvu" not in t.appearance
