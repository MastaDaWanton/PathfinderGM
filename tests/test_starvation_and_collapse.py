"""What thirst and hunger deal does not mend until the need is met; a collapse slept
through is a night (the owner's rulings of 2026-10-05).

**Withheld non-lethal.** "Nonlethal damage from thirst or starvation cannot be recovered
until the character gets food or water, as needed—not even magic that restores hit points
heals this damage" (Core Rulebook p.444, Starvation and Thirst; Pathfinder 2e keeps the
same rule: thirst damage "can't be healed until it quenches its thirst"). The owner: "yes
it should not heal until you eat or drink". Measured by the survival lane before this: from
about level 4 the hourly non-lethal healing (1 a level, CRB p.191) outpaced 1d6 an hour,
so thirst only ever fatigued and a parched body never went down — the rule's whole bite
was gone. Every heal path is covered because every one passes through
`Actor.heal_nonlethal`, whose floor is the withheld amount; each refusal is told.

**The collapse is a night.** The third failed save against sleep drops the character
asleep for eight hours, and waking from it called `Actor.rest` alone: the hit points and
the awake clock came back, the spell slots, the daily pools, the preparation and an
earned level did not — `Engine._op_rest` did those inline. The owner: "yes if you
collapse for 8 hours". Both now go through `Actor.sleep_through`.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from rules import casting, survival
from rules.activeeffect import ActiveEffect
from rules.dice import Dice
from rules.engine import Engine, Scene, _ward_tell
from rules.sheet import from_dict, load_pc, to_dict

HOUR = 60
DAY = 24 * HOUR


def _pc(path="fixtures/pc-kesst.json", **kw):
    pc = from_dict(to_dict(load_pc(path)), ref="pc")
    pc.kind = "pc"
    for k, v in kw.items():
        setattr(pc, k, v)
    return pc


def _engine(pc, seed=3, clock=5 * DAY + 9 * HOUR):
    s = Scene(location_id="bde94b038cba")
    s.add(pc)
    s.clock_minutes = clock
    return s, Engine(s, Dice(seed=seed))


def _run(engine, *ops, origin=""):
    return engine.run(engine.validate(list(ops), origin=origin))


def _tells(res) -> str:
    return " ".join(o.tell for o in res.outcomes)


class _Rigged:
    """Every survival check fails or passes as told, and every 1d6 of it rolls `harm`."""

    def __init__(self, monkeypatch, passed=lambda kind: False, harm=None):
        real = survival._check

        def spy(actor, kind, dc, dice, save=""):
            out = real(actor, kind, dc, dice, save)
            out["passed"] = passed(kind)
            return out

        monkeypatch.setattr(survival, "_check", spy)
        self.harm = harm


def _parched(pc, points, need="thirst"):
    """`points` of a need's non-lethal, landed as `survival` lands it."""
    pc.take_nonlethal(points)
    pc.withhold_nonlethal(need, points)
    return pc


# --- the hold, and the hours that cannot reach it ---------------------------------------------

def test_the_hours_no_longer_outheal_thirst(monkeypatch):
    """The survival lane's measurement: a fifth-level character heals 5 non-lethal an hour,
    thirst deals 1d6 on a failure, and without the rule every hour's thirst damage was
    healed by the same hour — ten failed checks in a row left 0 non-lethal. With it, the
    ten failures are all still there: 30 of 30."""
    _Rigged(monkeypatch)
    pc = _pc(level=5)
    pc.hp_max = pc.hp = 200
    pc.watered_minutes = 200 * HOUR
    s, engine = _engine(pc)
    monkeypatch.setattr(engine.dice, "roll",
                        lambda *a, **k: SimpleNamespace(total=3))
    s.advance(10 * HOUR)
    assert pc.nonlethal == 30, pc.nonlethal
    assert pc.withheld_nonlethal() == {"thirst": 30}
    assert pc.has_state("heal.withheld.thirst")
    said = " ".join(r for rec in s.take_body_said() for r in rec["said"])
    assert "thirst damage (30) will not mend until they drink." in said
    assert "not even magic" not in said, "an hour's rest is not a spell failing"


def test_the_sleep_ladders_damage_is_not_withheld(monkeypatch):
    """The book withholds what thirst and starvation deal, and nothing else: the 1d6 a
    failed save against sleep costs mends with the hours as any non-lethal does."""
    _Rigged(monkeypatch)
    pc = _pc(awake_minutes=30 * HOUR)
    toll = survival.charge(pc, HOUR, Dice(seed=1))
    assert toll.nonlethal and not toll.withheld
    assert pc.withheld_nonlethal() == {}


def test_a_night_does_not_mend_it_and_says_so(monkeypatch):
    """`Actor.rest` set non-lethal to 0 — the one heal path that did not pass through the
    floor. A night mends the rest of it, and the hold is told behind the rest."""
    pc = _parched(_pc(), 4)
    pc.take_nonlethal(2)                       # a sap's bruise, which a night does mend
    s, engine = _engine(pc, clock=5 * DAY + 22 * HOUR)
    res = _run(engine, {"op": "rest", "actor": "pc", "because": "night",
                        "params": {"kind": "night"}})
    assert pc.nonlethal == 4
    tells = _tells(res)
    assert "thirst damage (4) will not mend until they drink" in tells
    assert tells.index("rests for") < tells.index("will not mend")


# --- every cure ---------------------------------------------------------------------------------

def test_a_potion_heals_the_wounds_and_not_the_thirst():
    """A cure's rider ("removes an equal amount of nonlethal damage") stops at the hold;
    the hit points it restores are restored. "Not even magic" is said."""
    pc = _parched(_pc(), 5)
    pc.take_nonlethal(3)
    pc.hp = pc.hp_max - 4
    s, engine = _engine(pc)
    res = _run(engine, {"op": "heal", "actor": "pc", "because": "potion",
                        "params": {"to": "pc", "amount": 20}}, origin="author:test")
    assert pc.hp == pc.hp_max
    assert pc.nonlethal == 5, "the sap's 3 came off; thirst's 5 did not"
    tell = _tells(res)
    assert "shakes off 3 non-lethal" in tell
    assert "thirst damage (5) will not mend until they drink; not even magic heals it." \
        in tell


def test_a_cure_that_reaches_only_the_hold_is_not_told_as_unhurt():
    pc = _parched(_pc(), 5)
    s, engine = _engine(pc)
    res = _run(engine, {"op": "heal", "actor": "pc", "because": "potion",
                        "params": {"to": "pc", "amount": 8}}, origin="author:test")
    tell = _tells(res)
    assert "already unhurt" not in tell
    assert "will not mend until they drink" in tell
    assert pc.nonlethal == 5


def test_a_liniment_for_non_lethal_alone_is_refused_the_same():
    pc = _parched(_pc(), 5, need="hunger")
    s, engine = _engine(pc)
    res = _run(engine, {"op": "heal", "actor": "pc", "because": "willow bark",
                        "origin": "author:test",
                        "params": {"to": "pc", "amount": 4, "nonlethal": True}}, origin="author:test")
    assert pc.nonlethal == 5
    assert "hunger damage (5) will not mend until they eat" in _tells(res)


def test_a_cure_does_not_wake_a_body_the_hold_still_has_down():
    """`_op_heal` swept `recovery.hit-points` whenever hit points were above 0, which woke a
    character knocked out by non-lethal the cure had not taken off — here, all of it
    thirst's. The ladder is asked again after the sweep."""
    pc = _pc()
    pc.hp_max, pc.hp = 20, 4
    _parched(pc, 12)
    pc.apply_nonlethal_state()
    assert pc.has_state("state.down.unconscious")
    s, engine = _engine(pc)
    res = _run(engine, {"op": "heal", "actor": "pc", "because": "potion",
                        "params": {"to": "pc", "amount": 5}}, origin="author:test")
    assert pc.hp == 9 and pc.nonlethal == 12
    assert pc.has_state("state.down.unconscious")
    assert "no longer unconscious" not in _tells(res)


def test_fast_healing_and_a_ward_say_the_hold_too():
    """The two cures that are not ops: a periodic heal (troll blood's fast healing,
    `Actor.run_periodic`) and a ward's. Both are records `_ward_tell` says."""
    pc = _parched(_pc(), 6)
    pc.apply_effect(ActiveEffect(name="troll blood", kind="buff", source="troll blood",
                                 origin="item:troll-blood",
                                 periodic=[{"per": "round", "heal": 2}]))
    s, _e = _engine(pc)
    recs = pc.run_periodic("round", 1, Dice(seed=1))
    heal = next(r for r in recs if r["kind"] == "heal")
    assert heal["amount"] == 0 and "will not mend until they drink" in heal["unmended"]
    assert _ward_tell(s, heal).startswith("Kesst Vayr's thirst damage (6) will not mend")
    assert pc.nonlethal == 6


def test_every_heal_path_goes_through_the_floor():
    """The rule holds by construction, not by each cure remembering it: every site that
    takes non-lethal off calls `heal_nonlethal` or `heal` (whose rider is that call), and
    `rest` reads the same floor. A new direct write to `.nonlethal` that lowers it would
    be a heal path this rule never sees."""
    import re
    from pathlib import Path

    lowers = re.compile(r"\.nonlethal\s*(-=|=\s*0\b)")
    found = []
    for path in sorted(Path(".").glob("*/*.py")):
        if path.parts[0] not in ("rules", "play", "gm", "world"):
            continue
        for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if lowers.search(re.sub(r"#.*$", "", line)):
                found.append(f"{path.as_posix()}:{line.strip()}")
    allowed = {"rules/sheet.py:self.nonlethal -= back",
               "rules/sheet.py:self.nonlethal -= nonlethal_gone",
               # Resurrection, which releases the hold in the next line.
               "play/views.py:pc.nonlethal = 0"}
    assert set(found) <= allowed, sorted(set(found) - allowed)


# --- meeting the need ----------------------------------------------------------------------------

def test_drinking_frees_the_thirst_and_it_heals_by_the_hour():
    pc = _parched(_pc(), 4)
    s, engine = _engine(pc)
    res = _run(engine, {"op": "drink", "actor": "pc", "because": "a stream"})
    assert "The thirst damage on Kesst Vayr (4) can mend now." in _tells(res)
    assert any(e.get("kind") == "withheld_released" for o in res.outcomes for e in o.effects)
    assert pc.withheld_nonlethal() == {} and not pc.has_state("heal.withheld")
    assert pc.nonlethal == 4, "water is not medicine"
    s.advance(4 * HOUR)
    assert pc.nonlethal == 0


def test_eating_frees_hunger_and_leaves_thirst_held():
    pc = _parched(_pc(), 3, need="hunger")
    _parched(pc, 2, need="thirst")
    s, engine = _engine(pc)
    _run(engine, {"op": "eat", "actor": "pc", "because": "bread"})
    assert pc.withheld_nonlethal() == {"thirst": 2}
    s.advance(5 * HOUR)
    assert pc.nonlethal == 2


def test_parched_out_cold_and_alone_dies_of_it(monkeypatch):
    """The consequence the owner accepted: nobody brings water to a body that cannot
    drink, the hours cannot mend thirst's damage, and past the maximum it turns lethal."""
    _Rigged(monkeypatch)
    pc = _pc(level=5)
    pc.hp_max, pc.hp = 30, 30
    pc.watered_minutes = 200 * HOUR
    s, engine = _engine(pc)
    monkeypatch.setattr(engine.dice, "roll", lambda *a, **k: SimpleNamespace(total=6))
    for _ in range(30):
        s.advance(4 * HOUR)
        if pc.has_state("state.down.dead") or pc.has_state("state.down.dying"):
            break
    assert pc.hp <= 0
    assert pc.withheld_nonlethal() == {"thirst": 30}


# --- the panel and the save -------------------------------------------------------------------

def test_the_needs_panel_shows_what_is_held_and_why():
    pc = _parched(_pc(), 7)
    rows = {r["id"]: r for r in pc.summary()["needs"]}
    held = rows["thirst-held"]
    assert held["withheld"] == 7 and held["danger"]
    assert held["state"] == "7 non-lethal — drink to mend it"
    assert "not even magic" in held["detail"]
    assert "hunger-held" not in rows


def test_saves_round_trip_and_an_empty_hold_writes_nothing_new():
    """Existing saves are checked byte for byte elsewhere; the hold is an effect in the one
    store, so with nothing held the written sheet is exactly what it was."""
    fresh = to_dict(load_pc("fixtures/pc-kesst.json"))
    assert to_dict(from_dict(fresh, ref="pc")) == fresh
    assert not [e for e in fresh.get("effects", []) if e.get("kind") == "withheld"]
    pc = _parched(_pc(), 5)
    back = from_dict(to_dict(pc), ref="pc")
    assert back.withheld_nonlethal() == {"thirst": 5}
    assert back.has_state("heal.withheld.thirst")
    assert back.heal_nonlethal(10) == 0


def test_a_hold_over_a_hand_edited_sheet_never_sits_above_the_damage():
    pc = _parched(_pc(), 5)
    pc.nonlethal = 2
    assert pc.withheld_nonlethal() == {"thirst": 2}
    assert pc.heal_nonlethal(5) == 0


# --- the collapse is a night ------------------------------------------------------------------

@pytest.fixture
def spent_wizard():
    """Bobby, the caster fixture: both first-level slots cast, their copies gone."""
    pc = _pc("fixtures/pc-caster.json")
    casting.define_slots(pc)
    casting.ensure_prepared(pc, reason="start")
    pc.pool(casting.slot_pool(1)).current = 0
    for sid in ("burning-hands", "magic-missile"):
        pc.prepared.pop(sid, None)
    pc.awake_minutes = pc.fed_minutes = 40 * HOUR
    pc.watered_minutes = 0
    return pc


def _collapse(monkeypatch, pc, engine):
    """Three failed saves: fatigued, exhausted, asleep where they stand."""
    _Rigged(monkeypatch, passed=lambda kind: kind != "Exhaustion")
    pc.hp_max = pc.hp = 60
    for _ in range(3):
        _run(engine, {"op": "advance_time", "actor": "pc", "because": "waits",
                      "params": {"amount": 1, "unit": "hour"}})
    assert survival.asleep(pc) is not None


def test_eight_hours_asleep_where_they_fell_bring_the_slots_back(spent_wizard, monkeypatch):
    """The wake called `Actor.rest` alone: Bobby woke with 0 of 2 first-level slots and
    nothing prepared at first level. The night's door refills both."""
    pc = spent_wizard
    s, engine = _engine(pc)
    _collapse(monkeypatch, pc, engine)
    s.take_body_said()
    s.advance(survival.COLLAPSE_SLEEP_MINUTES)
    assert survival.asleep(pc) is None and not pc.has_state("state.down")
    assert casting.slots_left(pc, 1) == 2
    assert not casting.empty_slots(pc).get(1), casting.empty_slots(pc)
    said = " ".join(r for rec in s.take_body_said() for r in rec["said"])
    assert "wakes after eight hours' sleep" in said
    assert "Recovered: spell slot 1." in said


def test_a_collapse_cut_short_gives_nothing_back(spent_wizard, monkeypatch):
    """Woken before the eight hours — here by a cure, whose sweep lifts the sleep — is not
    a night: 1e gives all of it to "a full night's rest (8 hours of sleep or more)"."""
    pc = spent_wizard
    s, engine = _engine(pc)
    _collapse(monkeypatch, pc, engine)
    s.advance(3 * HOUR)
    pc.hp -= 5
    _run(engine, {"op": "heal", "actor": "pc", "because": "a slap and a draught",
                  "params": {"to": "pc", "amount": 2}}, origin="author:test")
    assert survival.asleep(pc) is None
    s.advance(6 * HOUR)
    assert casting.slots_left(pc, 1) == 0


def test_the_rest_op_and_the_collapse_share_one_door():
    """`_op_rest` did the level, the pools and the preparation inline, which is how the
    collapse came to do none of them. Both now call `Actor.sleep_through`, and neither
    repeats what it does. Read off the syntax tree, not the source text
    (tests/test_suite_isolation.py caps source-text pins)."""
    import ast
    from pathlib import Path

    def calls(path, name):
        tree = ast.parse(Path(path).read_text(encoding="utf-8"))
        fn = next(n for n in ast.walk(tree)
                  if isinstance(n, ast.FunctionDef) and n.name == name)
        return {c.func.attr if isinstance(c.func, ast.Attribute) else
                getattr(c.func, "id", "") for c in ast.walk(fn) if isinstance(c, ast.Call)}

    for path, name in (("rules/engine.py", "_op_rest"), ("rules/survival.py", "_wake")):
        made = calls(path, name)
        assert "sleep_through" in made, (path, name)
        assert not made & {"refresh_pools", "ensure_prepared", "level_up", "rest"}, \
            (path, name, made & {"refresh_pools", "ensure_prepared", "level_up", "rest"})
