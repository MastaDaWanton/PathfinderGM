"""How a person carries themselves reaches the narrator as behaviour; their secrets never do.

Before this (2026-09-25) every rolled life — temperament, quirk, wants, goal — was stored
and nothing read it: a suspicious, tight-fisted scribe who counts favours aloud talked
like everybody else. docs/the-population.md §7 designed the line; a research pass decided
its shape (citations in rules/population.py):

  * two traits at most, the loudest, as behaviour — never a label (CoMPosT: generic
    framing is what breeds caricature);
  * the quirk on first meeting, then only after QUIRK_EVERY turns, held as state (Valve's
    `respeakdelay`) — a small model cannot count "now and then";
  * wants, goal and hobby never: a 12B model told a secret leaks it thematically about
    83% of the time (Holtzman & West 2026), and the user's ruling is that they are
    learned in play.
"""
from __future__ import annotations

import pytest

from gm import prompts
from rules import population
from rules.bestiary import instantiate
from rules.engine import Scene
from rules.sheet import load_pc
from world.loader import load_cached

WORLD = load_cached("fixtures/aurvantis-campaign.json")
VORMOOR = WORLD.by_name("Vormoor", kind="CITY").id


@pytest.fixture
def scene():
    s = Scene(location_id=VORMOOR)
    s.add(load_pc("fixtures/pc-kesst.json"))
    return s


def _person(scene, phrase="man in a shadowed corner"):
    rec = population.note(scene, phrase)
    actor = instantiate("guildhand", scene=scene, name=phrase)
    scene.add(actor)
    rec["ref"] = actor.ref
    return rec, actor


def _brief(scene, turn):
    return prompts.scene_brief(WORLD, scene, WORLD.get(VORMOOR), turn=turn)


def test_the_brief_carries_how_they_act_and_never_what_they_want(scene):
    rec, actor = _person(scene)
    life = rec["life"]
    line = next(ln for ln in _brief(scene, 3).splitlines() if ln.strip().startswith(actor.ref))
    for shows in life["shows"][:2]:
        assert shows in line
    assert life["quirk"] in line, "first meeting: the habit is offered"
    for secret in (life["wants"], life["goal"], life["hobby"], life["work_name"]):
        assert secret not in line, secret
    # Behaviour, not labels: the trait words themselves are not handed over.
    assert not any(f" {t} " in f" {line} " for t in life["traits"] if len(t.split()) == 1)


def test_the_quirk_rests_once_the_page_has_shown_it(scene):
    rec, actor = _person(scene)
    rec["life"]["quirk"] = "hums the same four notes whenever the talk turns to money"
    beat = ("He hums the same four notes, tunelessly, as you mention the money, and "
            "goes on stacking the coins.")
    assert population.note_quirks_shown(scene, beat, 3) == [actor.ref]
    assert rec["quirk_turn"] == 3
    for turn in (4, 7):
        assert rec["life"]["quirk"] not in _brief(scene, turn)
    assert rec["life"]["quirk"] in _brief(scene, 3 + population.QUIRK_EVERY)


def test_an_offered_quirk_rests_even_when_the_page_paraphrased_it(scene):
    """Measured live 2026-09-25: the model plays quirks in paraphrase — "can tell which
    quarter of town you grew up in from the way you say three words" came back as
    "focuses on the way you speak, as if trying to pin down where you grew up" — and the
    word detector missed all of them in twelve turns. Resting only on a detected showing
    would have offered every quirk every turn. It rests from the offer, as Valve's
    `respeakdelay` counts from the speaking."""
    rec, actor = _person(scene)
    rec["life"]["quirk"] = ("can tell which quarter of town you grew up in from the way "
                            "you say three words")
    beat = ("She focuses on the way you speak, as if trying to pin down where you grew up "
            "from the cadence of your voice.")
    assert rec["life"]["quirk"] in _brief(scene, 3)
    assert population.note_quirks_shown(scene, beat, 3) == [], "the detector misses it"
    assert rec["quirk_turn"] == 3
    assert rec["life"]["quirk"] not in _brief(scene, 4)


def test_a_trait_named_outright_is_caught(scene):
    rec, actor = _person(scene)
    rec["life"]["traits"] = ["suspicious", "tight-fisted"]
    beat = "The man in the corner is suspicious of you. He counts his coins twice."
    assert population.traits_named(rec, beat, actor.name) == ["suspicious"]
    assert population.traits_named(rec, "He watches your hands, not your face.",
                                   actor.name) == []


def test_somebody_with_no_record_is_briefed_as_before(scene):
    actor = instantiate("guildhand", scene=scene, name="watchman")
    scene.add(actor)
    line = next(ln for ln in _brief(scene, 1).splitlines() if ln.strip().startswith(actor.ref))
    assert "how they act" not in line and "habit" not in line
