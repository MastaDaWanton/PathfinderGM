"""An introduce whose `who` is a ref binds to that person; a ref naming nobody is refused.

Measured on the 2026-09-30 playtest (docs/playtest-2026-09-30-findings.md item 7): the
plan wrote `introduce {who: "c8"}` — the barkeep's own ref — and the engine minted **c9
named "c8"**. The tells then read "In the scene: the c8 (c9)" and, a turn later, "Left
behind: the c8": a person called by a ref, which the page must never show.
"""
from __future__ import annotations

import pytest

from rules.dice import Dice
from rules.engine import Engine, Scene
from rules.sheet import load_pc
from world.loader import load_cached

WORLD = load_cached("fixtures/aurvantis-campaign.json")
VORMOOR = WORLD.by_name("Vormoor", kind="CITY").id


@pytest.fixture
def engine():
    s = Scene(location_id=VORMOOR)
    s.add(load_pc("fixtures/pc-kesst.json"))
    e = Engine(s, Dice(seed=3), world=WORLD)
    e.place_party()
    return e


def _run(e, plan):
    return e.run(e.validate(plan, origin="author:test"))


def _intro(who, **params):
    return {"op": "introduce", "because": "t", "params": {"who": who, **params}}


def _barkeep(engine):
    res = _run(engine, [_intro("the barkeep polishing a tankard")])
    return next(r for r, a in engine.scene.actors.items() if not a.is_pc), res


def test_introduce_by_ref_binds_to_that_person_and_mints_nobody(engine):
    """c9 named "c8" (the measured case): the ref is the person, not a description."""
    ref, _ = _barkeep(engine)
    before = set(engine.scene.people)
    res = _run(engine, [_intro(ref),
                        {"op": "say", "actor": "pc", "because": "t",
                         "params": {"words": "Another, please.", "to": "new1"}}])
    assert set(engine.scene.people) == before, "a ref minted somebody new"
    assert not any(a.name == ref for a in engine.scene.people.values())
    out = res.outcomes[0]
    assert out.status == "resolved"
    assert out.effects[0]["bound"] == {"new1": ref}
    assert f"the {ref}" not in out.tell and out.tell.startswith("In the scene: ")
    assert res.outcomes[1].status == "resolved"


@pytest.mark.parametrize("decorated", ["[{ref}]", " {ref} ", "the barkeep ({ref})"])
def test_a_decorated_ref_is_still_that_ref(engine, decorated):
    ref, _ = _barkeep(engine)
    before = set(engine.scene.people)
    res = _run(engine, [_intro(decorated.format(ref=ref))])
    assert set(engine.scene.people) == before
    assert res.outcomes[0].effects[0]["who"] == engine.scene.actors[ref].name


def test_a_ref_that_names_nobody_is_refused_with_the_fix_named(engine):
    before = set(engine.scene.people)
    res = _run(engine, [_intro("c41")])
    out = res.outcomes[0]
    assert set(engine.scene.people) == before, "c41 was minted as a person called 'c41'"
    assert out.effects == [] or not out.effects
    assert "nobody here is c41" in out.tell
    assert "by their own ref" in out.tell and "few words" in out.tell


def test_an_old_save_gives_a_ref_named_person_their_words_back(engine):
    """The damage already saved: Sam's c9 is NAMED "c8" and the Here list printed it
    (Lane A, live, 2026-09-30). On load it gets a descriptor: its record's words unless
    they are the ref too, else the work its record rolled (c9's: "ratcatcher"), else its
    block's name unless that is the civilian floor, else "a stranger"."""
    from rules import person_words, population
    from rules.sheet import Actor

    s = engine.scene
    c9 = Actor(ref="c9", name="c8", from_template="guildhand")
    s.add(c9)
    rec = population.note(s, "c8")
    rec["ref"] = "c9"
    rec["life"]["work_name"] = "ratcatcher"
    s.cast.append({"who": "c8", "turn": 0, "ref": "c9"})
    bare = Actor(ref="c12", name="new1", from_template="guildhand")
    s.add(bare)
    thug = Actor(ref="c13", name="c2", from_template="thug")
    s.add(thug)
    done = {r: (old, new) for r, old, new in person_words.heal_ref_names(s)}
    assert done == {"c9": ("c8", "a ratcatcher"), "c12": ("new1", "a stranger"),
                    "c13": ("c2", "a thug")}
    assert rec["phrase"] == "a ratcatcher"
    assert s.cast[-1]["who"] == "a ratcatcher"
    assert person_words.heal_ref_names(s) == [], "a second load changes nothing"


def test_the_players_own_ref_is_refused(engine):
    res = _run(engine, [_intro("pc")])
    assert "player's own" in res.outcomes[0].tell
    assert not any(a.name == "pc" for a in engine.scene.people.values() if not a.is_pc)
