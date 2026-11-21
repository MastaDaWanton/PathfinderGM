"""Playtest 2026-11-20 #22: the narrator invents the moon.

One move ended in "a moonless night", the next beat said "the dim, moonlit gloom". The
engine keeps no moon (`Scene.ambient_light`: "The app keeps no moon and no cloud"), yet
its own light reason for a dim night told the narrator "starlight and moonlight only"; and
nothing held a page's moon to anything. A moon, present or absent, is a light level in
PF1e (dim "with a moon in the sky", darkness "on a cloudy, moonless night"), so a page
that names one is a model authoring a mechanical state. docs/research/2026-11-21-moonlight.md.
"""
from __future__ import annotations

from gm import beat_verify as bv
from gm import prompts
from gm.checks import light_shown as L
from tests.test_light_on_the_page import _night

NIGHT = 2 * 24 * 60 + 21 * 60 + 30          # day 3, half past nine at night


def _facts(clock=NIGHT, settings=("open country",)):
    return bv.Facts(start="the fields", end="the fields", places=("the fields",),
                    people=(bv.Person("pc", "Shadow", pc=True),), clock=clock,
                    settings=settings)


def _hour(quote, sentence, part="night"):
    return bv.Claim("hour", {"part": part}, quote=quote, sentence=sentence, valid=True)


def test_the_engines_night_brief_names_no_moon():
    """#22: `sight` gave "night under the open sky, starlight and moonlight only" — the
    engine feeding the narrator a moon it does not hold, into `light_now` (and the
    richer-prose see block, which reads the same derivation)."""
    s, e, pc = _night()
    seen = L.sight(s)
    assert seen["level"] == "dim" and "moon" not in seen["why"]
    assert "moon" not in prompts.light_now(s).lower()


def test_a_moon_on_the_page_is_a_contradiction_either_way():
    """#22's two sentences, as the read-back quotes them: the moon present and the moon
    absent are both claims the engine never made, so both are judged."""
    f = _facts()
    for quote, sentence in (
            ("the dim moonlit gloom", "You press on through the dim, moonlit gloom."),
            ("under a moonless night", "You walk on under a moonless night.")):
        found = [d for d in bv.diff([_hour(quote, sentence)], f) if d.category == "hour"]
        assert len(found) == 1, quote
        assert "moon" in found[0].fact


def test_the_night_told_without_a_moon_is_not_judged():
    """Stars and the dark say the hour truly and name no moon: nothing to repair."""
    f = _facts()
    calm = _hour("the night is dark and full of stars",
                 "The night is dark and full of stars.")
    assert not [d for d in bv.diff([calm], f) if d.category == "hour"]


def test_the_reader_is_asked_for_the_moon():
    """The read-back's hour list is where the moon is caught, so its instruction names it:
    a moonlit sentence not read as saying the hour would never reach the check."""
    assert "moon" in bv._SYSTEM.split("time_of_day:")[1]
