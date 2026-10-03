"""Every minting door records the people a person's face was drawn from (item 10).

Measured on the 2026-09-30 playtest (docs/playtest-2026-09-30-findings.md item 10): **8 of 8
NPCs in Sam's save were stored `race: "human"`** — the `Actor` default — **with a Ratfolk
face and no `world_people_id`**, the Clockwork Spy (a construct) included in the eight with
race human. `names.appearance_for` chose the people and only its text was kept; the keeper
door, `population.embody` and the speaker made real wrote the face and never the people.
Only the named spawn recorded one.

Now one helper (`person_words.settle_people`) records it at every door, the face and the
record come from one pick (`names.face_people`), and the brief states it as fact
(`gm/brief/peoples.py`). The rules `race` is left alone on purpose — it is the stat block's
rules term; the world's people is `heritage`/`world_people_id` (memory: "the world owns its
own races").
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from gm import judgement
from gm.brief import BriefContext, peoples as brief_peoples
from rules import faces, keepers, names, person_words, population
from rules.dice import Dice
from rules.engine import Engine, Scene
from rules.sheet import Actor, load_pc
from world import loader

WORLD = loader.load_cached("fixtures/aurvantis-campaign.json")
LEDGERWARREN = WORLD.by_name("Ledgerwarren", kind="CITY").id
MARKET = f"{LEDGERWARREN}~urban:the-market"
RATFOLK = names.people_of(WORLD, LEDGERWARREN)
HUMAN = next(k for k, v in names.peoples(WORLD).items() if v == "Human")


def _table(at: str = MARKET):
    scene = Scene(location_id=LEDGERWARREN)
    scene.add(load_pc("fixtures/pc-kesst.json"))
    engine = Engine(scene, Dice(seed=3), world=WORLD)
    engine.place_party(at)
    return scene, engine


def _run(e, plan):
    return e.run(e.validate(plan, origin="author:test"))


def _agrees(actor, pid):
    """The person's people is recorded, and the face shows that people."""
    assert actor.world_people_id == pid, (actor.name, actor.world_people_id)
    assert actor.heritage == person_words.people_name(WORLD, pid)
    assert faces.people_of(actor.appearance) == actor.heritage, actor.appearance


def test_the_ledgerwarren_people_is_the_measured_one():
    assert names.peoples(WORLD)[RATFOLK] == "Ratfolk"


def test_a_keeper_records_their_people():
    """Oren Bramble and Soren Moorcock: Ratfolk faces, no people. Now recorded."""
    scene, _ = _table(MARKET)
    held = [a for a in scene.people.values() if keepers.is_keeper(str(a.world_entity_id))]
    assert held
    for k in held:
        _agrees(k, RATFOLK)


def test_introduce_records_their_people():
    scene, engine = _table(MARKET)
    _run(engine, [{"op": "introduce", "because": "t",
                   "params": {"who": "old woman mending a sack"}}])
    who = next(a for a in scene.actors.values() if a.name == "old woman mending a sack")
    _agrees(who, RATFOLK)


def test_the_words_people_wins_over_the_towns():
    """"the human sailor" in a Ratfolk town is human: face, people and name pool."""
    scene, engine = _table(MARKET)
    _run(engine, [{"op": "introduce", "because": "t",
                   "params": {"who": "the human sailor"}}])
    who = next(a for a in scene.actors.values() if a.name == "the human sailor")
    _agrees(who, HUMAN)
    pool = names.pool_for(WORLD, LEDGERWARREN, HUMAN)
    assert who.true_name.split()[0] in pool["given"]


def test_the_speaker_made_real_records_their_people():
    """A speaker the beat reader reads as somebody new and here gets a body through
    `seen_people` → `judgement.embody` → `population.embody` (`speaker_real._embody`
    until 2026-10-03), and the body records their people."""
    from play.aftermath import seen_people
    from tests.beat_reader import stub

    scene, engine = _table(MARKET)
    text = "A man in a stained apron looks up. 'You lost?' he asks."
    reading = stub.read(text, scene, engine=engine, who={"A man": "new"},
                        new=[("A man", "here", "man in a stained apron")],
                        lines={"You lost": ("A man", "you")})
    seen_people.step(stub.ctx(scene, reading, text=text, engine=engine, world=WORLD,
                              turn=3))
    (n,) = reading.newcomers
    _agrees(scene.actors[n.ref], RATFOLK)


def test_a_named_spawn_still_records_its_people():
    scene, engine = _table(MARKET)
    _run(engine, [{"op": "spawn", "because": "t",
                   "params": {"template": "guildhand", "name": "dockhand"}}])
    who = next(a for a in scene.actors.values() if a.name == "dockhand")
    assert who.world_people_id == RATFOLK


def test_a_construct_gets_no_people():
    """The Clockwork Spy was one of the eight `race: "human"` NPCs. A construct is not a
    person: no people, no people's face, nothing written."""
    spy = Actor(ref="c7", name="Clockwork Spy")
    scene, _ = _table(MARKET)
    assert person_words.settle_people(scene, WORLD, spy, words="Clockwork Spy",
                                      template="clockwork-spy") == ""
    assert spy.world_people_id is None and spy.heritage == "" and spy.appearance == ""


def test_the_rules_race_is_left_alone():
    """The stat block's rules term is not the world's people, and is not overwritten
    to agree with it: a world's Orc is the world's (memory, 2026-09-16)."""
    scene, engine = _table(MARKET)
    _run(engine, [{"op": "introduce", "because": "t", "params": {"who": "a porter"}}])
    who = next(a for a in scene.actors.values() if a.name == "a porter")
    assert who.race == Actor(ref="c99", name="x").race
    assert who.heritage == "Ratfolk"


def test_an_old_save_gets_the_people_its_face_shows():
    """8 of 8 on Sam's save: the face is the evidence. Nothing is redrawn."""
    scene = Scene(location_id=LEDGERWARREN)
    scene.add(load_pc("fixtures/pc-kesst.json"))
    face = names.appearance_for(WORLD, LEDGERWARREN, ref="c1")
    old = [Actor(ref=f"c{n + 1}", name=f"person {n}", appearance=face) for n in range(8)]
    spy = Actor(ref="c9", name="Clockwork Spy", from_template="clockwork-spy")
    for a in old + [spy]:
        scene.add(a)
    done = person_words.record_peoples(scene, WORLD)
    assert len(done) == 8
    assert all(a.world_people_id == RATFOLK and a.appearance == face for a in old)
    assert spy.world_people_id is None


def test_the_brief_states_the_people_as_fact():
    scene, engine = _table(MARKET)
    _run(engine, [{"op": "introduce", "because": "t", "params": {"who": "a porter"}}])
    ctx = BriefContext(world=WORLD, scene=scene, location=None, here=None, known=(),
                       recent_events=None, recent=None, secret=False, turn=1,
                       names_for=None, absent="", buying="", reading=None, player_text="")
    text, facts = brief_peoples.section(ctx)
    assert "OF WHICH PEOPLE (fact" in text and "a porter" in text and "Ratfolk" in text
    assert set(facts.values()) == {"Ratfolk"}


def test_a_named_people_with_no_body_is_not_given_another_peoples_face():
    """Pangrella ships one body (Korvu) and six peoples. Asked for a Nirkor, the old
    fallback drew the first body on the list: a Korvu face on a Nirkor."""
    pang = loader.load_cached("fixtures/pangrella-campaign.json")
    nirkor = next(k for k, v in names.peoples(pang).items() if v == "Nirkor")
    face = names.appearance_for(pang, "5bbd0c40345f", people_id=nirkor, ref="c4")
    assert face.startswith("Nirkor: ") and "Korvu" not in face
    assert person_words.people_drawn(pang, "5bbd0c40345f") == \
        names.face_people(pang, "5bbd0c40345f")[0]


@pytest.mark.parametrize("phrase,people", [("any elves here?", "Elf"),
                                           ("two dwarves at the bar", "Dwarf"),
                                           ("the humans", "Human"),
                                           ("a half-orc smith", "Half-Orc")])
def test_a_people_is_heard_in_the_plural_too(phrase, people):
    pid = person_words.people_named(phrase, WORLD)
    assert names.peoples(WORLD).get(pid) == people
