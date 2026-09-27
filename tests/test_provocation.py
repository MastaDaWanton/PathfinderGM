"""An insult costs regard, and temper decides whether it comes to blows.

Measured before this (2026-09-25, `narrator_audit.py --script provoke`): one man was
insulted nine times, the planner wrote `say` and `narrate_only` every time, no attitude
moved — and every exchange still earned the +2 of a friendly word, so the insults made
him like the player MORE. The user's ruling ("by temper"): the insult lowers his
attitude; a hot-tempered man swings after one or two, a placid one may never swing and
does something else. The research put temper on the CHANCE of striking, not on the
regard lost (RimWorld, Dwarf Fortress, Oblivion); rules/provocation.py carries it.
"""
from __future__ import annotations

import pytest

from gm import judgement
from rules import attitude, population, provocation, states
from rules.bestiary import instantiate
from rules.dice import Dice
from rules.engine import Engine, Scene
from rules.sheet import load_pc
from world.loader import load_cached

WORLD = load_cached("fixtures/aurvantis-campaign.json")
VORMOOR = WORLD.by_name("Vormoor", kind="CITY").id


def _bar(seed=1, temper=50, watch=False):
    s = Scene(location_id=VORMOOR)
    s.add(load_pc("fixtures/pc-kesst.json"))
    e = Engine(s, Dice(seed=seed), world=WORLD)
    e.place_party()
    e.run(e.validate([{"op": "introduce", "params": {"who": "big man at the bar"}}],
                     origin="author:test"))
    ref = next(r for r, a in s.actors.items() if not a.is_pc)
    population.of_ref(s, ref)["life"]["axes"]["temper"] = temper
    if watch:
        s.add(instantiate("watchman", scene=s, name="watchman"))
    return s, e, ref


def _insult_until_blows(temper, seed, most=8, watch=False):
    s, e, ref = _bar(seed, temper, watch)
    for n in range(1, most + 1):
        res = e.run(e.validate([{"op": "provoke", "target": ref}]))
        if s.in_encounter:
            return n, res
        if "turns their back" in res.outcomes[0].tell:
            return 0, res
    return 0, res


@pytest.mark.parametrize("said, how", [
    ("I call him a coward in front of his friends.", "insult"),
    ("I tell him he fights like his mother.", "insult"),
    ("I laugh in his face.", "insult"),
    ("I say 'you fight like a farmer'.", "insult"),
    ("I shove past the men at the door.", "slight"),
    ("I ask the thief where the gate is.", ""),
    ("I buy the smith a drink.", ""),
    ("I stay where I am and smile at him.", ""),
])
def test_an_insult_is_read_from_the_words_and_a_noun_is_not(said, how):
    assert judgement.provocation_in(said) == how


def test_the_insult_costs_regard_and_earns_no_friendly_word():
    """The measured inversion: nine insults warmed him, +2 a word."""
    s, e, ref = _bar(temper=5)
    before = attitude.regard_of(s.actors[ref])
    e.run(e.validate([{"op": "provoke", "target": ref},
                      {"op": "say", "actor": "pc", "params": {"words": "coward", "to": ref}}]))
    assert attitude.regard_of(s.actors[ref]) == before - provocation.INSULT


def test_a_placid_man_never_swings_and_a_volcanic_one_swings_within_two():
    placid = [_insult_until_blows(5, seed)[0] for seed in range(20)]
    volcanic = [_insult_until_blows(95, seed)[0] for seed in range(20)]
    average = [_insult_until_blows(50, seed)[0] for seed in range(20)]
    assert placid == [0] * 20
    assert all(volcanic) and sorted(volcanic)[10] <= 2
    assert sorted(x for x in average if x)[len([x for x in average if x]) // 2] >= 3


def test_a_placid_man_turns_his_back_and_the_talk_is_over():
    s, e, ref = _bar(temper=5)
    e.run(e.validate([{"op": "say", "actor": "pc", "params": {"words": "hello", "to": ref}}]))
    assert s.actors[ref].has_state(states.TALKING)
    res = None
    for _ in range(5):
        res = e.run(e.validate([{"op": "provoke", "target": ref}]))
        if "turns their back" in res.outcomes[0].tell:
            break
    assert "turns their back" in res.outcomes[0].tell
    assert not s.actors[ref].has_state(states.TALKING)
    assert not s.in_encounter


def test_a_swing_is_his_fists_and_is_rolled_before_the_prose():
    n, res = _insult_until_blows(95, 3)
    assert n
    blows = [o for o in res.outcomes if o.op == "attack"]
    assert "Battle is joined" in blows[0].tell and len(blows) == 2
    assert blows[0].effects[0]["params"].get("weapon") == "unarmed"


def test_the_watch_looking_on_holds_most_tempers_back():
    s, e, ref = _bar(temper=60, watch=True)
    step = attitude.HOSTILE
    held = provocation.strike_chance(s, s.actors[ref], step)
    s2, e2, ref2 = _bar(temper=60)
    free = provocation.strike_chance(s2, s2.actors[ref2], step)
    assert held == pytest.approx(free * provocation.WATCH_HOLDS)


def test_no_number_reaches_the_narrator():
    for seed in range(6):
        n, res = _insult_until_blows(50, seed)
        for o in res.outcomes:
            if o.op == "provoke":
                assert not any(ch.isdigit() for ch in o.tell), o.tell


def test_the_players_insult_declares_the_op_aimed_at_him():
    s, e, ref = _bar()
    said = "I call him a coward in front of his friends."
    assert "provoke" in judgement.declared_ops(said, s, WORLD)
    raw = judgement.inject_provoke([{"op": "say", "actor": "pc",
                                     "params": {"words": "coward", "to": ref}}], said, s)
    assert raw[0] == {"op": "provoke", "target": ref, "params": {"how": "insult"},
                      "because": raw[0]["because"]}


def test_the_insult_finds_the_man_it_is_spoken_at():
    """Measured live 2026-09-25: "I tell the biggest man at the bar that I have seen
    better fighters in a nursery" provoked nobody — three men were here and nobody was
    in conversation yet. The words it is spoken at are looked for, through the finder,
    without where he stands: "the biggest man" is the "large man"."""
    s = Scene(location_id=VORMOOR)
    s.add(load_pc("fixtures/pc-kesst.json"))
    e = Engine(s, Dice(seed=1), world=WORLD)
    e.place_party()
    for who in ("man with a thick beard", "large man", "man with the ledger"):
        e.run(e.validate([{"op": "introduce", "params": {"who": who, "how": "arrives"}}],
                         origin="author:test"))
    refs = {a.name: r for r, a in s.actors.items() if not a.is_pc}
    for said, who in [
        ("I tell the biggest man at the bar that I have seen better fighters in a nursery.",
         "large man"),
        ("I call the man with the ledger a cheat.", "man with the ledger"),
        ("I laugh at the bearded man.", "man with a thick beard"),
    ]:
        assert judgement.provoked_one([], said, s) == refs[who], said


# --- what they do instead, the grudge coming back, and the cooling after -------------

def _hostile_now(temper=5, **axes):
    s, e, ref = _bar(temper=temper)
    life = population.of_ref(s, ref)["life"]
    life["axes"].update(axes)
    for _ in range(6):
        res = e.run(e.validate([{"op": "provoke", "target": ref}]))
        if "turns their back" in res.outcomes[0].tell:
            return s, e, ref, res
    raise AssertionError("never turned away")


def test_a_gregarious_man_turns_the_room():
    s, e, ref = _bar(temper=5)
    s.add(instantiate("guildhand", scene=s, name="woman with a basket"))
    other = next(r for r, a in s.actors.items() if a.name == "woman with a basket")
    before = attitude.regard_of(s.actors[other])
    population.of_ref(s, ref)["life"]["axes"].update(sociability=90, order=10)
    for _ in range(6):
        res = e.run(e.validate([{"op": "provoke", "target": ref}]))
        if "turns their back" in res.outcomes[0].tell:
            break
    assert "everybody here hears" in res.outcomes[0].tell
    assert attitude.regard_of(s.actors[other]) == before - provocation.SLIGHT


def test_an_orderly_man_goes_to_the_watch():
    """PF1e's lapsed Intimidate: they "may report you to local authorities". The town's
    existing `state.suspected` (docs/wanted.md): prices up, a warning at the gate."""
    from rules import places

    s, e, ref, res = _hostile_now(sociability=10, order=90)
    assert "goes to find the watch" in res.outcomes[0].tell
    town = places.location_of(s.at) or s.location_id
    assert states.standing_with_the_law(s.pc(), town) == "suspected"


def test_the_grudge_comes_back_with_time_and_faster_the_longer_nothing_happens():
    """Dwarf Fortress 0.40.17: "Made stress levels drop faster the longer no stressors
    are applied". Only what provocation took comes back."""
    s, e, ref = _bar(temper=5)
    start = attitude.regard_of(s.actors[ref])
    e.run(e.validate([{"op": "provoke", "target": ref}]))
    low = attitude.regard_of(s.actors[ref])
    s.advance(12 * 60)
    first_half_day = attitude.regard_of(s.actors[ref]) - low
    s.advance(provocation.GRUDGE_DAYS * 24 * 60)
    assert attitude.regard_of(s.actors[ref]) == start
    assert 0 <= first_half_day < (start - low) / 4, "slow at first"


def test_a_cooled_man_is_not_drawn_again_so_soon():
    s, e, ref = _bar(temper=95)
    for _ in range(8):
        e.run(e.validate([{"op": "provoke", "target": ref}]))
        if s.in_encounter:
            break
    assert s.in_encounter
    before = attitude.regard_of(s.actors[ref])
    s.end_encounter()
    after = attitude.regard_of(s.actors[ref])
    assert abs(after - before) == provocation.AFTERMATH, "cathartic or embittered, a step"
    res = e.run(e.validate([{"op": "provoke", "target": ref}]))
    assert "will not be drawn again so soon" in res.outcomes[0].tell
    assert not s.in_encounter
    s.advance(provocation.COOL_MINUTES)
    assert not provocation.cooled(s.actors[ref], s.clock_minutes)
