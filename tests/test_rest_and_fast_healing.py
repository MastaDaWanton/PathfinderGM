"""Every night heals by the book, and fast healing heals by the round of time.

The owner, 2026-10-09, playing 0.2.12 as Sammy, an asura (a homebrew race card) at level 1
with 73 maximum hit points: "i have slept multiple times now and my health is not going
up. i also have fast healing so i should be healing all the time". The turn log settled
the first half — every `rest` resolved "Sammy recovers 1 hit points (34/73)", which IS
the rule at level 1 (CRB p.191: "1 hit point per character level"), said without the rate.
The second half was real: the save held no fast healing anywhere. The race's evolution
tag `fast-healing.1` reached `has_state` and nothing with a clock, its `not_yet` still
reading "waits on a periodic effect executor" long after `Actor.run_periodic` existed.

Measured before this change, on a scratch level-5 fighter at 20/50:
- the `rest` op: 20 -> 25 (correct, and kept);
- a two-day lived-through wait (`Scene.wait`), one night slept inside it: 20 -> 20;
- fast healing 5 held as an effect, a one-minute wait: 20 -> 20 (it fired on played
  rounds only, so out of a fight it never healed anybody).
"""
from __future__ import annotations

import json

import pytest

from pathfindergm import files
from rules import races, survival
from rules.activeeffect import ActiveEffect
from rules.dice import Dice
from rules.engine import Engine, Scene
from rules.intents import parse
from rules.sheet import from_dict, load_pc


def _vet(hp=20):
    pc = from_dict({"name": "Vet", "kind": "pc", "class": "fighter", "level": 5,
                    "abilities": {"str": 14, "dex": 12, "con": 14, "int": 10, "wis": 10,
                                  "cha": 10}, "hp": 50, "ranks": {}})
    pc.hp = hp
    return pc


def _scene(pc=None, seed=3):
    s = Scene(location_id="5bbd0c40345f")
    pc = s.add(pc or _vet())
    s._dice = Dice(seed=seed)
    return s, pc


def _fast_healing(pc, n=5, rounds=None):
    pc.apply_effect(ActiveEffect(
        name=f"fast healing {n}", kind="effect", key="buff.fast-healing",
        tags=("buff.fast-healing",), source="item:troll-marrow", origin="item:troll-marrow",
        duration="rounds" if rounds is not None else "until-dismissed", rounds_left=rounds,
        periodic=[{"per": "round", "heal": n}]))


# --- natural healing: every night, any route ---------------------------------------------

def test_a_night_inside_a_long_wait_heals_by_the_book():
    """Measured: a two-day wait with one night slept in it left a level-5 fighter at
    20/50. The night is a full night — 5 hit points at level 5 — and is told with its rate."""
    s, pc = _scene()
    passed = s.wait(2 * 1440)
    assert pc.hp == 25, passed
    said = " ".join(survival.wait_lines(passed, pc.ref))
    assert "recovers 5 hit points (25/50)" in said
    assert "1 per character level" in said


def test_a_working_weeks_camp_nights_heal():
    """`_work_hours` camped with `survival.sleep`, which resets the awake clock and heals
    nothing: sixteen hours of work across one camp night healed 0. Now the camp's night is
    the night's one door (`survival.night`)."""
    s, pc = _scene()
    e = Engine(s, Dice(seed=4))
    worked, told = e._work_hours(pc, 16)
    assert worked == 16
    assert pc.hp == 25 and "recovers 5 hit points" in told


def test_the_rest_op_says_the_rate_beside_the_number():
    """The owner read "Sammy recovers 1 hit points (34/73)" as no healing at all. The rule
    was right; the sentence did not say it. Bed rest is the book's 2 per level."""
    s, pc = _scene()
    e = Engine(s, Dice(seed=3))
    res = e.run([parse({"op": "rest", "actor": pc.ref, "params": {"kind": "night"}})])
    assert pc.hp == 25
    assert "recovers 5 hit points (25/50) — a night's rest heals 1 per character level" \
        in res.outcomes[0].tell
    pc.hp = 20
    res = e.run([parse({"op": "rest", "actor": pc.ref, "params": {"kind": "bed rest"}})])
    assert pc.hp == 30
    assert "2 per character level" in res.outcomes[0].tell


def test_a_level_one_night_is_one_hit_point_and_says_so():
    """The owner's own numbers: level 1, 34 of 73. One night is 35 — the book's rate, not a
    defect — and the sentence carries the rate so it reads as one."""
    pc = load_pc("fixtures/pc-kesst.json")
    pc.hp = 4
    said = survival.night(pc, Dice(seed=1))
    assert pc.hp == 5
    assert said[0].startswith("Kesst Vayr recovers 1 hit point (5/")


# --- fast healing over time --------------------------------------------------------------

def test_fast_healing_heals_across_a_wait_out_of_a_fight():
    """Measured: fast healing 5 and a one-minute wait, 20 -> 20. A minute is ten rounds, so
    fifty points, capped at full; told as a body record with where they stand."""
    s, pc = _scene()
    _fast_healing(pc, 5)
    passed = s.advance(1)
    assert pc.hp == 50
    said = " ".join(survival.wait_lines(passed, pc.ref))
    assert "restores 30 hit points to Vet" in said and "(50/50)" in said


def test_a_draught_heals_only_the_rounds_it_had_left():
    """Three rounds of fast healing 2 inside a ten-minute wait are six points, not two
    hundred: each effect runs for what it had left, and the tick then ends it."""
    s, pc = _scene()
    _fast_healing(pc, 2, rounds=3)
    s.advance(10)
    assert pc.hp == 26
    assert not pc.has_state("buff.fast-healing")


def test_fast_healing_in_a_fight_is_the_played_round_not_the_clock():
    """Two played rounds of fast healing 5 are ten points. The clock door does not heal a
    second time when an op moves a round mid-fight (`advance(0, rounds=1)`)."""
    from rules.bestiary import instantiate

    s, pc = _scene()
    _fast_healing(pc, 5)
    thug = s.add(instantiate("thug", scene=s, name="the thug"))
    s.enrol(pc.ref, 20)
    s.enrol(thug.ref, 1)
    s.advance_turn()                    # round one begins; no rollover yet
    assert s.in_encounter and pc.hp == 20
    s.advance(0, rounds=1)
    assert pc.hp == 20, "the clock door healed inside a fight"
    first = s.round
    while s.round < first + 2:
        s.advance_turn()
    assert pc.hp == 30


def test_fast_healing_lifts_the_dying_back_to_their_feet():
    """"Fast healing continues to function (even at negative hit points) until a creature
    dies" (Bestiary, universal monster rules). A dying character it raises past zero stops
    dying, as a cure's do."""
    s, pc = _scene(_vet(hp=-2))
    pc.apply_hp_state()
    assert pc.has_state("state.down.dying")
    _fast_healing(pc, 5)
    pc.run_periodic("round", 1, s._dice)
    assert pc.hp == 3
    assert not pc.has_state("state.down")


def test_the_dead_do_not_fast_heal():
    s, pc = _scene()
    _fast_healing(pc, 5)
    pc.die("test")
    before = pc.hp
    s.advance(10)
    assert pc.hp == before


# --- a race's fast healing ----------------------------------------------------------------

def _race(rid: str, **doc):
    body = races.normalise({"id": rid, "name": doc.pop("name", rid.title()),
                            "choose": list(races.STANDARD_CHOOSE), **doc})
    path = races.homebrew_dir(make=True) / f"{rid}.json"
    files.write_text(path, json.dumps(body))
    return path


def test_a_homebrew_races_fast_healing_heals_through_the_one_executor():
    """The owner's asura: a homebrew race with fast healing, and not a point of it ever
    healed. The evolution taken five times is fast healing 5 (APG: "+1 per round for every
    2 additional evolution points spent (maximum 5)"), granted as a standing effect
    through the applicator with a tell, run by `run_periodic` over a wait and in a fight,
    and gone when the race no longer grants it."""
    path = _race("fh-asura", name="FH Asura", evolutions=[{"id": "fast-healing"}] * 5)
    try:
        assert races.validate(races.get("fh-asura")) == []
        assert "fast-healing.5" in races.document("fh-asura")["tags"]
        pc = _vet()
        pc.race = "fh-asura"
        s, pc = _scene(pc)
        granted = pc.sync_carried(s._dice)
        assert granted == [{"kind": "trait", "ref": pc.ref, "what": "FH Asura",
                            "grants": "fast healing 5"}]
        from rules.engine import _ward_tell
        assert _ward_tell(s, granted[0]) == "Vet has fast healing 5, as the FH Asura do."
        assert pc.sync_carried(s._dice) == []          # granted once, not every batch
        s.advance(1)
        assert pc.hp == 50
        pc.race = "human"
        gone = pc.sync_carried(s._dice)
        assert [g["kind"] for g in gone] == ["effect_ended"]
        assert not any(e.periodic for e in pc.effects)
    finally:
        files.remove(path)


def test_the_first_wait_after_the_grant_already_heals():
    """Measured live 2026-10-09 on scratch data: a homebrew race with fast healing 5 waited
    a minute at 2/9 and stood at 2/9 — `sync_carried` ran at the END of the stretch, so the
    effect was granted as the minute closed, and told as "Ended: … has fast healing 5". The
    standing heal is settled first now, and both facts ride the stretch's body record."""
    path = _race("fh-first", name="FH First", evolutions=[{"id": "fast-healing"}] * 5)
    try:
        pc = _vet()
        pc.race = "fh-first"
        s, pc = _scene(pc)
        passed = s.advance(1)
        assert pc.hp == 50
        said = " ".join(survival.wait_lines(passed, pc.ref))
        assert said.startswith("Vet has fast healing 5, as the FH First do.")
        assert "(50/50)" in said
        assert not any("fast healing" in x for x in passed["ended"])
    finally:
        files.remove(path)


@pytest.mark.parametrize("card, want", [
    # The unconverted card's shapes: a bare trait line, an effects document, an
    # evolution written by hand with the catalogue's name rather than its id.
    ({"traits": ["Fast healing 3"]}, 3),
    ({"effects": [{"type": "fast_healing", "amount": 4}]}, 4),
    ({"evolutions": [{"id": "Fast Healing", "times": 2}]}, 2),
    ({"tags": ["fast-healing.7"]}, 7),
    ({"evolutions": [{"id": "fast-healing", "times": 9}]}, 5),     # the APG's maximum
    # A sentence about healing is not the trait, and the expander's counted line is not
    # read as a second, smaller one.
    ({"traits": ["Their wounds close fast; healing herbs are sacred"]}, 0),
])
def test_every_shape_a_card_says_fast_healing_in_reaches_the_tag(card, want):
    """A homebrew card says fast healing in whatever shape its author wrote; each is
    converted once, on load, into the one tag play reads (`races.fast_healing`). Before,
    only the evolution's tag existed and nothing read even that."""
    assert races.fast_healing(races.derive({"name": "Card", **card})) == want


def test_a_world_card_can_state_fast_healing_in_its_grants():
    """Fixes are world-agnostic: a World Bible people that heals at a rate states it in
    `grants[]` (schema 1.5). Before, `fast-healing.2` was not in the shared vocabulary and
    `draft` dropped it into `not_yet` as "this engine has no such tag"."""
    doc = races.draft("Mendfolk", ["They are tall."], granted=["fast-healing.2"])
    assert races.fast_healing(races.derive(doc)) == 2
    assert "fast healing 2" in doc["traits"]
    assert not doc["not_yet"]
