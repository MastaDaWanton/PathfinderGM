"""The phases of the day magic keeps (rules/sky.py).

The owner's ruling of 2026-10-05 (docs/enchanting-answers.md, Round 4 point 10) replaced
the plan's planetary hours: "this is not earth", and named planets would not be world
agnostic. These tests pin the phases to the engine's own clock and to the narrator's own
words for the hour, so the bench, the brief and the prose cannot disagree about what time
it is. Each names the defect it prevents.
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

from rules import sky

DAY = 1440


def test_every_minute_of_the_day_has_exactly_one_phase():
    """A gap in the window table would answer some minute with the wrong phase (or none);
    an overlap would make "Noon, 42 minutes left" and "Afternoon" both true at once."""
    seen = {}
    for m in range(DAY):
        p = sky.phase_at(5 * DAY + m)
        assert p["starts"] <= 5 * DAY + m < p["ends"], (m, p)
        assert p["left"] == p["ends"] - (5 * DAY + m)
        seen[p["phase"]] = seen.get(p["phase"], 0) + 1
    assert set(seen) == set(sky.PHASES)
    assert sum(seen.values()) == DAY


def test_the_turning_points_sit_on_the_engines_own_dawn_and_dusk():
    """The engine's dawn is 06:00 (a night's rest runs to it) and night is 18:00-06:00
    (`craft_views._is_night`). A phase table typed in by hand could put dawn somewhere the
    rest of the app does not: here each turning point is two hours centred on its moment,
    built from the one constant pair."""
    assert (sky.DAWN_MINUTE, sky.DUSK_MINUTE) == (6 * 60, 18 * 60)
    at = lambda h, m=0: sky.phase_at(h * 60 + m)["phase"]  # noqa: E731
    assert at(6) == "dawn" and at(5) == "dawn" and at(4, 59) == "night"
    assert at(12) == "noon" and at(11) == "noon" and at(13) == "afternoon"
    assert at(18) == "dusk" and at(17) == "dusk" and at(19) == "night"
    assert at(0) == "midnight" and at(23) == "midnight" and at(1) == "night"
    assert at(7) == "morning" and at(10, 59) == "morning"


def test_the_night_phases_agree_with_the_benches_night():
    """`craft_views._is_night` is the binding circle's night (dusk to dawn). Every minute it
    calls night must be dusk, night, midnight or dawn here, never morning or noon."""
    from play.craft_views import _is_night

    class _C:
        class scene:
            clock_minutes = 0

    for m in range(0, DAY, 5):
        _C.scene.clock_minutes = m
        if _is_night(_C):
            assert sky.phase_at(m)["phase"] in ("dusk", "night", "midnight", "dawn"), m


def test_no_phase_names_an_hour_the_narrator_check_would_call_false():
    """`gm/beat_verify.PARTS` holds the hours at which prose may truthfully name a part of
    the day. A phase label outside its word's window (calling 15:00 "noon") is exactly the
    false hour that check exists to catch, and is why `afternoon` exists: six names cannot
    cover a day truthfully."""
    from gm.beat_verify import PARTS

    same = {"dawn": "dawn", "morning": "morning", "noon": "midday", "afternoon": "afternoon",
            "dusk": "dusk", "night": "night", "midnight": "night"}
    for w in sky.windows():
        hours = {(m // 60) % 24 for m in range(w["starts"], w["ends"])}
        assert hours <= PARTS[same[w["phase"]]], (w, sorted(hours - PARTS[same[w["phase"]]]))


def test_the_bench_line_says_the_window_left_or_the_wait():
    """Round 4, point 10: the bench says "Noon, 42 minutes left" or "Midnight in 3 hours 10
    minutes", with Wait for it. The wait is what `next_phase` answers, and it must cross
    midnight — the window that wraps the day — correctly."""
    assert sky.words(12 * 60 + 18, "noon") == "Noon, 42 minutes left"
    assert sky.words(20 * 60 + 50, "midnight") == "Midnight in 2 hours 10 minutes"
    assert sky.next_phase("midnight", 23 * 60 + 30) == 0
    assert sky.words(23 * 60 + 30, "midnight") == "Midnight, 1 hour 30 minutes left"
    assert sky.words(DAY + 30, "midnight") == "Midnight, 30 minutes left"
    assert sky.next_phase("dawn", 7 * 60) == 22 * 60
    assert sky.next_phase("night", 2 * DAY + 0) == 60       # midnight, then the small hours
    assert sky.next_phase("night", 2 * DAY + 13 * 60) == 6 * 60


def test_an_unknown_phase_is_refused_by_name():
    """A family naming a planet ("mars", the plan before the owner's ruling) must fail
    loudly, not quietly match nothing and leave the bench with no favourable window."""
    with pytest.raises(ValueError, match="no phase of the day called 'mars'"):
        sky.next_phase("mars", 0)
    assert set(sky.OWNER_PHASES) < set(sky.PHASES)


def test_the_sky_asks_the_world_for_nothing():
    """World-agnostic (the owner: "named planets would not be world agnostic"): the phases
    read the clock and nothing else. Walked as an AST, the way test_three_laws reads code:
    the module imports nothing at all, and names no planet table."""
    tree = ast.parse(Path(sky.__file__).read_text(encoding="utf-8"))
    imports = [n for n in ast.walk(tree) if isinstance(n, (ast.Import, ast.ImportFrom))
               and not (isinstance(n, ast.ImportFrom) and n.module == "__future__")]
    assert imports == [], [ast.dump(n) for n in imports]
    names = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)} \
        | {n.targets[0].id for n in tree.body if isinstance(n, ast.Assign)
           and isinstance(n.targets[0], ast.Name)}
    assert not {"PLANETS", "planet_of_day"} & names


def test_countdown_words_never_say_ready_sooner_than_it_is():
    """A countdown that rounds down tells the player to come back before the work is done:
    47 hours and a minute read "1 day 24 hours" in the first draft of this helper."""
    assert sky.span_words(42) == "42 minutes"
    assert sky.span_words(190) == "3 hours 10 minutes"
    assert sky.span_words(DAY) == "1 day"
    assert sky.span_words(DAY + 61) == "1 day 2 hours"
    assert sky.span_words(2 * DAY - 1) == "2 days"
    assert sky.span_words(5 * DAY + 1) == "6 days"
