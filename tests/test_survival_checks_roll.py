"""The body's checks roll wherever the clock moves (the owner's report of 2026-10-05).

*"save DC for rest scales like crazy"* — the needs panel read Thirst "parched — a check
every hour, DC 12", Hunger "starving — a check every day, DC 11", and Rest "past a day
awake — Will save every active hour, DC 274". An earlier save, Sammy, read DC 107 at 121
hours awake.

The DC was the symptom. `Scene.advance` — the clock's one door, behind waiting, walking
the town, repairs, asking around, the crafting benches and a knockout's hours — moved the
body's counters and deliberately rolled none of its checks; only `survival.pass_hours`
rolled them, from four ops (forage, the crafting trip, venture, a journey's march). So in
ordinary play a character went 121 hours without sleep, food or water and nothing ever
asked, nothing made them collapse, and the awake DC (counted by hours until the prose lane
counted it by saves) climbed past anything a Will save can make.

Now `survival.charge` spends the body's hours for both doors and rolls what they owe, for
the player; the third failed save against sleep drops them asleep for eight hours, which
is a night's rest when it ends; and checks are rolled for hours as they pass, never for a
backlog that passed before.

The rules (CRB p.444 Starvation and Thirst, p.191 non-lethal, Appendix 2 fatigue): checks
at DC 10 +1 per previous check, 1d6 non-lethal on a failure, fatigued, past maximum hit
points the damage turns lethal; the book never says the count clears on sleep. Staying
awake is the owner's Will save, not a book rule — there is none in the Core Rulebook; the
2013 FAQ says only that a night without sleep leaves a character fatigued.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from rules import survival
from rules.dice import Dice
from rules.engine import Engine, Scene
from rules.sheet import from_dict, load_pc, to_dict

HOUR = 60
DAY = 24 * HOUR


def _pc(**kw):
    pc = from_dict(to_dict(load_pc("fixtures/pc-kesst.json")), ref="pc")
    pc.kind = "pc"
    for k, v in kw.items():
        setattr(pc, k, v)
    return pc


@pytest.fixture
def sammy():
    """The owner's Sammy at beat 63: 18 of 73, 121 hours unslept and unfed, no save made."""
    pc = _pc()
    pc.hp_max, pc.hp = 73, 18
    pc.fed_minutes = pc.awake_minutes = 121 * HOUR
    pc.watered_minutes = 0
    return pc


def _engine(pc, seed=3, clock=5 * DAY + 9 * HOUR + 49):
    s = Scene(location_id="bde94b038cba")
    s.add(pc)
    s.clock_minutes = clock
    return s, Engine(s, Dice(seed=seed))


def _wait(engine, hours):
    return engine.run(engine.validate([
        {"op": "advance_time", "actor": "pc", "because": "the player waits",
         "params": {"amount": hours, "unit": "hour"}}]))


class _Rigged:
    """`survival._check` with the verdict chosen, recording every DC asked."""

    def __init__(self, monkeypatch, passed=None):
        self.asked: list[tuple[str, int]] = []
        real = survival._check

        def spy(actor, kind, dc, dice, save=""):
            out = real(actor, kind, dc, dice, save)
            self.asked.append((kind, dc))
            if passed is not None:
                out["passed"] = passed(kind)
            return out

        monkeypatch.setattr(survival, "_check", spy)

    def of(self, kind):
        return [dc for k, dc in self.asked if k == kind]


# --- the checks roll on the clock's own door ------------------------------------------------

def test_waiting_rolls_the_checks_the_hours_owe(sammy, monkeypatch):
    """Sammy waited, walked and worked for five days on `Scene.advance` and not one Will
    save was asked: the counters said 121 hours and `awake_checks` said 0. Two hours of
    waiting are two waking hours past the grace, and each is a save."""
    rig = _Rigged(monkeypatch)
    _s, engine = _engine(sammy)
    res = _wait(engine, 2)
    assert rig.of("Exhaustion") == [10, 11]
    assert sammy.awake_checks == 2
    told = [o for o in res.outcomes if o.op == "body"]
    assert len(told) == 1, [o.op for o in res.outcomes]
    assert "Will save against sleep" in told[0].tell


def test_a_backlog_is_not_rolled_retroactively(sammy, monkeypatch):
    """Ninety-seven hours past the grace had passed unasked when the fix landed. Rolling
    them would be a wall of ninety-seven saves in one turn ending in a certain collapse;
    the hours that passed before are not rolled, and the next hour starts the count at
    DC 10 (tbaMUD freezes needs while a player is away, and caps its own catch-up)."""
    rig = _Rigged(monkeypatch)
    _s, engine = _engine(sammy)
    _wait(engine, 1)
    assert rig.of("Exhaustion") == [10]


def test_a_body_that_keeps_failing_is_fatigued_then_exhausted_then_asleep(sammy, monkeypatch):
    """The owner's ladder, which nothing ever climbed: every failure was `pass_hours`'s,
    and nothing but forage, a journey and venture reached it."""
    _Rigged(monkeypatch, passed=lambda kind: False)
    s, engine = _engine(sammy)
    _wait(engine, 1)
    assert sammy.has_condition("fatigued")
    _wait(engine, 1)
    assert sammy.has_condition("exhausted")
    assert not sammy.has_condition("fatigued"), "exhausted replaces fatigued"
    res = _wait(engine, 1)
    assert survival.asleep(sammy) is not None
    assert sammy.has_state("state.down.unconscious")
    assert "falls asleep where they stand" in " ".join(o.tell for o in res.outcomes)


def test_asleep_the_awake_clock_stands_still_and_no_save_is_asked(sammy, monkeypatch):
    rig = _Rigged(monkeypatch, passed=lambda kind: False)
    s, engine = _engine(sammy)
    _wait(engine, 3)
    assert survival.asleep(sammy) is not None
    awake, asked = sammy.awake_minutes, len(rig.of("Exhaustion"))
    s.advance(3 * HOUR)
    assert sammy.awake_minutes == awake
    assert len(rig.of("Exhaustion")) == asked
    assert survival.sleep_left(sammy) == survival.COLLAPSE_SLEEP_MINUTES - 3 * HOUR


def test_eight_hours_on_they_wake_and_it_was_a_night(sammy, monkeypatch):
    """Waking is `Actor.rest("night")`: the awake clock and its saves back to nothing,
    exhaustion down to fatigue. Without it the general knockout branch woke them after
    an hour with the awake clock untouched, and the next hour's save dropped them again."""
    _Rigged(monkeypatch, passed=lambda kind: False)
    s, engine = _engine(sammy)
    _wait(engine, 3)
    s.advance(survival.COLLAPSE_SLEEP_MINUTES)
    assert survival.asleep(sammy) is None
    assert not sammy.has_state("state.down")
    assert sammy.awake_minutes == 0 and sammy.awake_checks == 0
    assert sammy.has_condition("fatigued") and not sammy.has_condition("exhausted")
    said = " ".join(r for rec in s.take_body_said() for r in rec["said"])
    assert "wakes after eight hours' sleep" in said


def test_a_collapse_mid_stretch_spends_the_rest_of_it_asleep(sammy, monkeypatch):
    """The caller chose how far the clock goes — the reason `Scene.advance` once refused
    to roll at all. The stretch is not cut: the hour they drop is an hour in it, and the
    hours after it are sleep."""
    _Rigged(monkeypatch, passed=lambda kind: False)
    s, _engine_ = _engine(sammy)
    awake = sammy.awake_minutes
    s.advance(5 * HOUR)
    assert survival.asleep(sammy) is not None
    assert sammy.awake_minutes - awake == 3 * HOUR
    assert survival.sleep_left(sammy) == survival.COLLAPSE_SLEEP_MINUTES - 2 * HOUR


def test_the_dc_never_runs_away_once_the_checks_happen(monkeypatch):
    """Ten days without a night in a bed, waited out two hours a turn, fed and watered:
    the DC panel read 274 when the saves were never asked. Asked, the ladder ends every
    run of them in sleep within a few failures, which resets the count. Measured over
    five seeds: the highest awake DC any of them reached was 17."""
    worst = 0
    for seed in range(5):
        rig = _Rigged(monkeypatch)
        pc = _pc()
        pc.awake_minutes = 20 * HOUR
        s, engine = _engine(pc, seed=seed)
        for _ in range(120):
            pc.fed_minutes = pc.watered_minutes = 0
            s.advance(2 * HOUR)
            s.take_body_said()
        dcs = rig.of("Exhaustion")
        assert dcs, "ten days and no save asked"
        worst = max(worst, max(dcs))
        monkeypatch.undo()
    # Measured 2026-10-05: DC 17 at worst, across all five seeds (Kesst, a first-level rogue).
    assert worst <= 20, worst


def test_only_the_player_rolls(monkeypatch):
    """Nothing feeds, waters or beds a companion or a merchant — `rest`, `eat` and a
    march's camp are the player's — so rolling theirs would starve every companion by the
    fourth day. Their counters move; their checks wait for a rule that looks after them."""
    rig = _Rigged(monkeypatch)
    pc = _pc()
    other = from_dict(to_dict(load_pc("fixtures/pc-kesst.json")), ref="c1")
    other.kind = "npc"
    other.name = "Drenn"
    other.awake_minutes = other.fed_minutes = other.watered_minutes = 200 * HOUR
    s, _e = _engine(pc)
    s.add(other)
    s.advance(3 * HOUR)
    assert other.awake_minutes == 203 * HOUR
    assert rig.asked == []
    assert other.awake_checks == other.thirst_checks == 0


def test_the_dead_keep_no_clock(sammy):
    """Nine to twenty-seven days in the grave (the resurrection in play/views.py) are not
    days without water: a raised character came back three weeks parched."""
    sammy.add_condition("dead", source="test")
    s, _e = _engine(sammy)
    awake = sammy.awake_minutes
    s.advance(20 * DAY)
    assert sammy.awake_minutes == awake


# --- thirst and hunger, as the book has them ---------------------------------------------------

def test_a_night_no_longer_clears_the_thirst_and_hunger_counts():
    """CRB p.444: "DC 10, +1 for each previous check", and nothing in the text clears the
    count on sleep. `survival.sleep` cleared both every night, so a character three days
    without water slept back to DC 10 each morning. Food and water clear their own."""
    pc = _pc(thirst_checks=5, hunger_checks=3, awake_checks=4)
    pc.rest("night")
    assert (pc.thirst_checks, pc.hunger_checks, pc.awake_checks) == (5, 3, 0)
    survival.drink(pc)
    survival.eat(pc)
    assert (pc.thirst_checks, pc.hunger_checks) == (0, 0)


def test_thirst_past_maximum_hit_points_is_lethal(monkeypatch):
    """"Characters that take an amount of nonlethal damage equal to their total hit points
    begin to take lethal damage instead" (CRB p.444). Without it a parched body left
    unconscious took non-lethal for ever, and the knockout path waited out hours that
    only added to it."""
    _Rigged(monkeypatch, passed=lambda kind: False)
    pc = _pc()
    pc.watered_minutes = 200 * HOUR
    pc.nonlethal = pc.hp_max
    before = pc.hp
    toll = survival.charge(pc, HOUR, Dice(seed=1))
    assert toll.lethal > 0
    assert pc.hp == before - toll.lethal
    assert pc.nonlethal == pc.hp_max


def test_thirst_fatigues_and_never_exhausts(monkeypatch):
    """"Characters who have taken nonlethal damage from lack of food or water are
    fatigued" — a state the damage leaves, not a fresh cause each hour."""
    _Rigged(monkeypatch, passed=lambda kind: False)
    pc = _pc()
    pc.hp_max = pc.hp = 200
    pc.watered_minutes = 100 * HOUR
    survival.charge(pc, 4 * HOUR, Dice(seed=1))
    assert pc.has_condition("fatigued") and not pc.has_condition("exhausted")


# --- what the player is told -----------------------------------------------------------------

def test_every_toll_is_told_once(sammy, monkeypatch):
    """Law 3. The clock's door has no outcome of its own, so the toll waits on the scene
    and is told at the end of the batch — once: the next batch tells nothing again."""
    _Rigged(monkeypatch, passed=lambda kind: False)
    s, engine = _engine(sammy)
    first = [o for o in _wait(engine, 1).outcomes if o.op == "body"]
    assert len(first) == 1 and "fails a Will save" in first[0].tell
    again = engine.run(engine.validate([{"op": "narrate_only", "because": "x"}]))
    assert not [o for o in again.outcomes if o.op == "body"]


def test_two_stretches_before_one_telling_are_told_as_one(sammy, monkeypatch):
    """Measured live on the owner's save: a walk and a wait came back as "Sammy holds
    out against thirst once (DC 10)." and then "Sammy holds out against thirst 3 times
    (DC 11-13)." — two outcomes for one body. Every op is told behind itself now, but an
    op (or a bench view before a batch) can move the clock more than once before the
    telling, and those are folded into one."""
    _Rigged(monkeypatch, passed=lambda kind: True)
    sammy.watered_minutes = 200 * HOUR
    s, engine = _engine(sammy)
    s.advance(HOUR)
    s.advance(3 * HOUR)
    told = engine._body_settles()
    assert len(told) == 1
    assert "holds out against thirst 4 times (DC 10–13)" in told[0].tell
    assert len(told[0].effects) == 2


def test_the_toll_is_told_behind_the_op_that_spent_the_hours(sammy, monkeypatch):
    """Measured live: a wait that put Sammy to sleep, followed in the same plan by a
    `rest`, was told as "Sammy rests for 8 hours" and only then "falls asleep where they
    stand" — the batch's end is too late for a fact the next op stands on."""
    _Rigged(monkeypatch, passed=lambda kind: False)
    s, engine = _engine(sammy)
    res = engine.run(engine.validate([
        {"op": "advance_time", "actor": "pc", "because": "a", "params": {"amount": 3, "unit": "hour"}},
        {"op": "advance_time", "actor": "pc", "because": "b", "params": {"amount": 1, "unit": "hour"}}]))
    assert [o.op for o in res.outcomes][:2] == ["advance_time", "body"]
    assert "falls asleep" in res.outcomes[1].tell


def test_work_tells_its_own_toll_and_leaves_nothing_pending(sammy):
    """The activity ops spend their hours through `pass_hours` and say what it cost in
    their own sentence, then move the clock with `charge_body=False` — so nothing waits on
    the scene to be told a second time."""
    s, engine = _engine(sammy)
    survival.pass_hours(sammy, 3, engine.dice)
    s.advance(3 * HOUR, charge_body=False)
    assert s.take_body_said() == []


def test_the_forager_stops_at_the_first_failure_but_is_not_put_to_sleep(monkeypatch):
    """`pass_hours` ends the work at a failed save, as it always did; "they went down where
    they stood" was said of that, and it was false — they stop, fatigued, on their feet.
    Only the third failure is sleep."""
    _Rigged(monkeypatch, passed=lambda kind: False)
    pc = _pc(awake_minutes=30 * HOUR)
    toll = survival.pass_hours(pc, 10, Dice(seed=1))
    assert toll.hours == 1 and toll.collapsed and not toll.fell_asleep
    from rules.engine import survival_note

    assert "could not keep going" in survival_note(toll)
    assert "went down" not in survival_note(toll)


# --- the turn gate --------------------------------------------------------------------------

def _campaign(scene, engine):
    return SimpleNamespace(scene=scene, engine=lambda: engine, world=None, location=None)


def test_the_turn_gate_lets_the_sleep_run_out(sammy, monkeypatch):
    """play/downed.py had no branch for sleep: its general one woke the player after one
    hour with hit points floored and the awake clock untouched — "You come round about an
    hour later" — and the next hour's save dropped them again, for ever."""
    from play import downed

    _Rigged(monkeypatch, passed=lambda kind: False)
    s, engine = _engine(sammy)
    _wait(engine, 3)
    s.take_body_said()
    assert downed.state_of(sammy) == "stable"
    _Rigged(monkeypatch, passed=lambda kind: True)
    out = downed.resolve(_campaign(s, engine))
    assert out.playable
    assert out.lines[0].startswith("You sleep on where you dropped, 8 hours more")
    assert downed.state_of(sammy) == "fine"
    assert sammy.awake_minutes == 0


def test_a_knockout_that_does_not_lift_is_not_told_as_coming_round(monkeypatch):
    """Out cold on a parched body: the hours waited out add thirst damage as fast as they
    heal it, and the line said "You come round" over a character who had not."""
    from play import downed

    _Rigged(monkeypatch, passed=lambda kind: False)
    pc = _pc()
    assert pc.level == 1, "an hour heals one point at first level"
    pc.hp_max, pc.hp = 40, 10
    pc.watered_minutes = 200 * HOUR
    pc.nonlethal = 14
    pc.apply_nonlethal_state()
    assert pc.has_state("state.down.unconscious")
    s, engine = _engine(pc)
    # Every failed thirst check a six, against a point an hour healed.
    monkeypatch.setattr(engine.dice, "roll", lambda *a, **k: SimpleNamespace(total=6))
    out = downed.resolve(_campaign(s, engine))
    assert "do not come round" in out.lines[0]
    assert not out.playable
