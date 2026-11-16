"""Non-lethal damage, prone and natural healing: the playtest of 2026-11-15.

Each test names the item it holds and what was measured. The rules, Core Rulebook:
- Nonlethal Damage (p.191): staggered when it equals current hit points, unconscious when
  it exceeds them, never deducted from hit points; "If a creature's nonlethal damage is
  equal to his total maximum hit points (not his current hit points), all further nonlethal
  damage is treated as lethal damage"; it heals 1 hit point per hour per character level,
  and a cure removes an equal amount of it.
- Stable Characters and Recovery (p.190): an unconscious stable character checks every
  hour to regain consciousness, DC 10 Constitution with the negative hit points as a
  penalty; left without help, each failure costs 1 hit point.
- Natural Healing (p.191): a full night's rest heals 1 hit point per character level.
- Drop Prone (p.188): a free action. Prone (Appendix 2): -4 AC against melee, +4 against
  ranged.
"""
from __future__ import annotations

from types import SimpleNamespace

from gm import acts_to_ops, judgement
from rules import trial
from rules.dice import Dice
from rules.engine import Engine, Scene
from rules.sheet import from_dict, load_pc, to_dict
from tests.test_nonlethal_strikes import _fight
from tests.test_trial import _check, _taken_for_theft, _tells, _wait


def _merchant(hp=5, con=10):
    d = {"name": "the merchant", "kind": "npc", "hp": hp, "hp_max": 5, "level": 1,
         "abilities": {"str": 10, "dex": 10, "con": con, "int": 10, "wis": 10, "cha": 10}}
    return from_dict(d, ref="c9")


def _bender(**changes):
    d = to_dict(load_pc("fixtures/pc-kesst.json"))
    d.update(changes)
    return from_dict(d, ref="pc")


# --- #41, #45: past maximum hit points, non-lethal is lethal --------------------------

def test_4_then_8_nonlethal_on_a_5_hp_merchant_is_by_the_book_dying():
    """Playtest 2026-11-15 #41/#45 asked why 4 + 8 non-lethal on a 5 hp merchant left him
    "-2/5 · Unconscious, Dying". It is the CRB's ceiling, not a mix-up: 5 of the 12 fill
    the non-lethal track to his maximum and the other 7 are lethal. Pinned so nobody
    "fixes" it into a pool with no bottom. What was wrong was that no list showed the 5."""
    m = _merchant()
    m.take_damage(4, "bludgeoning", lethality="nonlethal")
    m.apply_hp_state()
    assert (m.hp, m.nonlethal) == (5, 4) and not m.is_down
    hit = m.take_damage(8, "bludgeoning", lethality="nonlethal")
    m.apply_hp_state()
    assert (m.hp, m.nonlethal, hit["overflow"]) == (-2, 5, 7)
    assert m.has_condition("dying")


def test_nonlethal_never_touches_hit_points_below_the_maximum_and_knocks_out():
    """Unconscious, never dying, while it is below hp_max (CRB p.191)."""
    m = _merchant()
    m.take_damage(3, "bludgeoning", lethality="nonlethal")
    m.apply_hp_state()
    assert m.hp == 5 and m.has_condition("staggered") is False
    m.take_damage(2, "bludgeoning", lethality="nonlethal")     # 5 of 5: still not past
    m.apply_hp_state()
    assert m.hp == 5 and m.has_condition("staggered")
    m.hp = 4                                                   # a scratch: 5 > 4
    m.apply_hp_state()
    assert m.has_condition("unconscious") and not m.has_condition("dying")


# --- #50: the merchant who never came round --------------------------------------------

def test_a_stable_npc_checks_each_hour_and_comes_round():
    """Playtest 2026-11-15 #50: stable at -2, the merchant was still out cold an hour
    later, and nothing in the engine would ever have woken him: the hourly check to
    regain consciousness (CRB p.190) was not built for anybody but the player. A Con of
    40 makes the DC 12 check certain."""
    scene = Scene(location_id="5bbd0c40345f")
    scene.add(load_pc("fixtures/pc-kesst.json"))
    m = scene.add(_merchant(hp=-2, con=40))
    m.add_condition("unconscious", source="hit points")
    m.add_condition("stable", source="stabilised")
    Engine(scene, Dice(seed=4))
    scene.advance(60)
    assert m.hp == 1 and not m.is_down and not m.has_condition("unconscious")


def test_a_stable_npc_still_carrying_nonlethal_is_not_told_awake():
    """Live, 2026-11-15: the merchant (stable at -2, 5 non-lethal) passed his check, was
    told "comes round" on 1 hit point under 4 non-lethal, and the prose had him push
    himself up, while the ladder had him unconscious, as the book does (CRB p.191)."""
    scene = Scene(location_id="5bbd0c40345f")
    scene.add(load_pc("fixtures/pc-kesst.json"))
    m = scene.add(_merchant(hp=-2, con=40))
    m.nonlethal = 5
    m.add_condition("unconscious", source="hit points")
    m.add_condition("stable", source="stabilised")
    Engine(scene, Dice(seed=4))
    ended = scene.advance(60)["ended"]
    assert m.hp == 1 and m.has_condition("unconscious")
    assert not any("comes round" in x for x in ended), ended
    assert any("still unconscious from non-lethal" in x for x in ended), ended


def test_left_untended_a_failed_check_costs_a_hit_point():
    """"Every failed Constitution check to regain consciousness results in the loss of 1
    hit point" (CRB p.190, Recovering without Help). Con 4 (-3) at -2 needs a 15."""
    for seed in range(40):
        m = _merchant(hp=-2, con=4)
        m.add_condition("unconscious", source="hit points")
        m.add_condition("stable", source="stabilised")
        came = m.come_round(Dice(seed=seed), 1)
        if not came:
            assert m.hp == -3 and m.has_condition("stable")
            return
    raise AssertionError("forty seeds and every one woke at -3 against DC 12")


# --- #65: woken over non-lethal ---------------------------------------------------------

def test_a_player_woken_from_wounds_stays_out_while_nonlethal_exceeds_hit_points():
    """Playtest 2026-11-15 (#65's snapshot): stable at -2 carrying 4 non-lethal, she came
    round on 1 hit point with 3 non-lethal and no condition at all — awake on 1 hp under 3
    non-lethal, which the book has unconscious. Now the wait runs until it heals back."""
    from play import downed

    scene, engine = _fight()
    scene.actors["c1"].hp = -50                    # nobody standing over her to act
    scene.actors["c1"].apply_hp_state()
    pc = scene.actors["pc"]
    pc.hp, pc.nonlethal = -2, 4
    pc.apply_hp_state()
    pc.stabilise("test")
    out = downed.resolve(SimpleNamespace(scene=scene, engine=lambda: engine))
    assert out.playable
    assert pc.nonlethal <= pc.nonlethal_threshold, (pc.hp, pc.nonlethal)
    assert not pc.has_state("state.down"), [c.key for c in pc.conditions]
    assert any("hours later" in line for line in out.lines), out.lines


# --- #72: a month in gaol --------------------------------------------------------------

def test_thirty_days_worked_off_in_the_gaol_heal_by_the_night():
    """Playtest 2026-11-15 #72: in on 1 of 26 hit points on day 1, out on 1 of 26 on day
    31. The term moved the clock with the body's checks off and slept no night, so natural
    healing (1 per level a night, CRB p.191) never ran."""
    s, e, pc, g, _ = _taken_for_theft()
    pc.purse = {}
    pc.hp = 1
    _check(e, "diplomacy", g.ref, face=1)
    clock = s.clock_minutes
    res = _wait(e)
    days = (s.clock_minutes - clock) // (24 * 60)
    assert days >= 1, _tells(res)
    assert pc.hp == min(pc.hp_max, 1 + days * max(1, pc.level)), (pc.hp, days)
    assert "nights' rest" in _tells(res), _tells(res)


def test_the_gaol_nights_are_told_once_as_a_total():
    pc = load_pc("fixtures/pc-kesst.json")
    pc.hp = 1
    said = trial._gaol_nights(SimpleNamespace(dice=Dice(seed=1)), pc, 30)
    assert pc.hp == pc.hp_max
    assert sum("recovers" in line for line in said) == 1, said


# --- #88: the cheat that banked a point ---------------------------------------------------

def test_cheat_heal_to_full_heals_what_is_missing_and_banks_nothing():
    """Playtest 2026-11-15 #88: "/cheat heal me to full hit points" from 1/26 "recovers 25
    hit points, banks 1 as temporary vitality": the model wrote 26, and Blood Bond banked
    the spare point. Full is what is missing, read in code."""
    scene = Scene(location_id="5bbd0c40345f")
    pc = scene.add(load_pc("fixtures/pc-kesst.json"))
    pc.hp, pc.nonlethal = 1, 3
    engine = Engine(scene, Dice(seed=1))
    wish = "heal me to full hit points"
    raw = judgement.cheat_intents(wish, scene)
    assert [r["params"]["amount"] for r in raw] == [pc.hp_max - 1]
    engine.run(judgement.keep_the_authors_numbers(
        engine.validate(raw, origin="author:cheat", origin_name="the author's word"), wish))
    assert (pc.hp, pc.nonlethal, pc.temp_hp) == (pc.hp_max, 0, 0)


def test_cheat_heal_to_full_with_more_nonlethal_than_wounds_clears_it_on_its_own_track():
    scene = Scene(location_id="5bbd0c40345f")
    pc = scene.add(load_pc("fixtures/pc-kesst.json"))
    pc.hp, pc.nonlethal = pc.hp_max - 1, 6
    raw = judgement.cheat_intents("restore me to full health", scene)
    assert [(r["params"]["amount"], r["params"].get("nonlethal")) for r in raw] \
        == [(1, None), (5, True)]


# --- #62, #64: dropping to her knees ---------------------------------------------------

def test_dropping_prone_lays_prone_and_the_spear_meets_ac_minus_four():
    """Playtest 2026-11-15 #62/#64: "drop to my knees" was read `go`, the tell was "Vesna
    Kroll moves from near to near", no prone state was laid, and the sergeant's spear swung
    at her standing AC (it missed 4 of 6). The reading's `prone` act now builds the
    condition; prone is -4 AC against melee (CRB Appendix 2)."""
    scene, engine = _fight()
    pc = scene.actors["pc"]
    melee_before, ranged_before = pc.ac("melee"), pc.ac("ranged")
    frame = {"actions": [{"span": "drop to my knees", "act": "prone", "commit": "done"}]}
    rows = acts_to_ops.table(frame, scene)
    built = [i for r in rows for i in r.intents]
    assert built and built[0]["op"] == "condition", built
    res = engine.run(engine.validate(built))
    assert pc.has_state("state.position.prone"), [o.tell for o in res.outcomes]
    assert "prone" in res.outcomes[-1].tell
    assert (pc.ac("melee"), pc.ac("ranged")) == (melee_before - 4, ranged_before + 4)
    # And up again: `rise` lifts it.
    rows = acts_to_ops.table({"actions": [{"span": "get up", "act": "rise",
                                           "commit": "done"}]}, scene)
    engine.run(engine.validate([i for r in rows for i in r.intents]))
    assert not pc.has_state("state.position.prone")


def test_the_plans_walk_to_nowhere_beside_a_drop_prone_is_struck():
    scene, engine = _fight()
    frame = {"actions": [{"span": "drop to my knees", "act": "prone", "commit": "done"}]}
    rows = acts_to_ops.table(frame, scene)
    raw = [{"op": "move", "actor": "pc", "params": {"zone": "near"}, "because": ""}]
    out = acts_to_ops.apply(raw, rows, frame, scene)
    assert not any(isinstance(r, dict) and r.get("op") == "move" for r in out), out


def test_a_move_to_the_band_already_stood_in_says_it_went_nowhere():
    """"Vesna Kroll moves from near to near" (playtest 2026-11-15 #62)."""
    scene = Scene(location_id="5bbd0c40345f")
    scene.add(load_pc("fixtures/pc-kesst.json"))
    engine = Engine(scene, Dice(seed=1))
    res = engine.run(engine.validate([{"op": "move", "actor": "pc",
                                       "params": {"zone": "near"}, "because": "t"}]))
    assert "near to near" not in res.outcomes[-1].tell, res.outcomes[-1].tell
