"""Fly, climb, swim and burrow speeds, and the fact that nothing moves on them.

Measured 2026-09-14, chasing whether verticality was missing or merely unfinished. It is
missing, and the sheet did not say so.

A race that takes Flight gets everything except the flying:

    expand()    move.fly.base -> move.fly.30      resolved against the race's own speed
    speeds()    {'land': 30, 'fly': 30}           on the sheet, correctly
    price_tag() (4, 'fly 30 ft (clumsy)', 'exact')  priced from the ARG anchor

and then `rules.engine` never asks. `races.speeds()` has three call sites — two in
`races.py`, one in `sheet.py` — and every one of them only *describes*. Grep the engine
for "flying", "elevation", "higher ground" or "airborne" and there are no hits at all,
because `grid.Point` is `tuple[int, int]` and there is nowhere for a fly speed to go.

**The defect this file pins is the disagreement, not the gap.** The same tag arrives by
two doors. A world that describes a winged people reaches `races.CUES`, which has always
said "a fly speed: the engine moves on the ground only". A player who picks Flight on the
races bench reached the evolution, which said nothing — so the one path admitted the
engine could not fly and the other quietly implied it could.

`test_every_movement_evolution_says_the_engine_cannot_use_it` is written to **fail when
the feature lands**. When the engine reads a movement mode, the `not_yet` becomes a lie
and this test says so rather than leaving a stale apology on the sheet for ever. That is
the point: the guard removes itself.
"""
from __future__ import annotations

import re
from pathlib import Path

from django.conf import settings

from rules import races

MODES = ("fly", "climb", "swim", "burrow")


def _movement_evolutions() -> dict[str, dict]:
    """Every evolution that grants a `move.<mode>.*` tag, found by the tag rather than
    by a hand-kept list of four ids — a fifth added tomorrow is caught the same day."""
    out = {}
    for eid, ev in races.evolutions().items():
        if any(re.match(r"^move\.(fly|climb|swim|burrow)\.", str(t))
               for t in (ev.get("tags") or [])):
            out[eid] = ev
    return out


def test_the_catalogue_still_offers_all_four_modes():
    """If this shrinks, the test below is guarding nothing."""
    found = _movement_evolutions()
    assert len(found) >= 4, found
    granted = {re.match(r"^move\.([a-z]+)\.", t).group(1)
               for ev in found.values() for t in ev["tags"]
               if re.match(r"^move\.([a-z]+)\.", t)}
    assert set(MODES) <= granted, granted


def test_every_movement_evolution_says_the_engine_cannot_use_it():
    """Until the engine reads a movement mode, every door to one must admit it.

    Deliberately paired with the assertion below: the moment `rules/engine.py` learns
    the word, that assertion fails, this apology becomes false, and both come off
    together. A `not_yet` that outlives its defect is worse than none, because it tells
    a player a working feature is broken.
    """
    missing = [eid for eid, ev in _movement_evolutions().items()
               if not str(ev.get("not_yet") or "").strip()]
    assert not missing, (
        f"{missing} grant a movement mode and do not say the engine cannot use it. "
        f"`races.CUES` says so on the world-derived path; both doors to the same tag "
        f"have to agree.")


def test_the_engine_still_cannot_read_a_movement_mode():
    """The other half of the pair, and the thing that makes the apology true today.

    Mechanical rather than a promise: it greps the engine for the vocabulary a vertical
    would have to introduce. When stage 3 lands this fails, and the `not_yet` sentences
    above come off in the same commit.
    """
    engine = Path(settings.BASE_DIR, "rules", "engine.py").read_text(encoding="utf-8")
    # `speeds(` would match `speed_feet(`-adjacent noise, so ask for the word the
    # feature cannot be built without: a mode name next to a speed.
    hits = re.findall(r"\bfly_speed\b|\bclimb_speed\b|\belevation\b|\bairborne\b", engine)
    assert not hits, (
        f"rules/engine.py now speaks of {sorted(set(hits))} — if the engine reads a "
        f"movement mode, remove the `not_yet` from the movement evolutions in "
        f"content/races/evolutions.json and delete this test with it.")


def test_the_two_doors_to_a_fly_speed_agree():
    """A winged people from World Bible and a Flight evolution are the same tag, and a
    player should not learn different things about it depending which door they came in
    by. Both must carry a caveat; the wording is each path's own."""
    world_side = [waits for _pat, granted, _line, waits in races.CUES
                  if any(t.startswith("move.fly.") for t in granted)]
    assert world_side and world_side[0], "CUES no longer admits the fly speed is inert"

    bench_side = [ev.get("not_yet") for eid, ev in _movement_evolutions().items()
                  if any(t.startswith("move.fly.") for t in ev["tags"])]
    assert bench_side and all(bench_side), bench_side


def test_a_race_that_takes_flight_carries_the_caveat_onto_its_sheet():
    """End to end through the real path. `expand()` is what turns `move.fly.base` into
    a real speed, and it is also what collects `not_yet` — so a document built the way
    the bench builds one has both the speed and the warning."""
    built = races.derive({"id": "x", "name": "X", "speed": 30, "size": "medium",
                          "evolutions": [{"id": "flight"}]})

    assert races.speeds(built)["fly"] == 30, "the fly speed stopped reaching the sheet"
    assert any("fly speed" in n for n in built["not_yet"]), built["not_yet"]
    # And it is still honestly priced — the caveat is about the engine, not the cost.
    assert races.price_tag("move.fly.30") == (4, "fly 30 ft (clumsy)", "exact")
