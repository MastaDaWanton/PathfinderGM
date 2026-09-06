"""Where the prose puts a person is where the map puts them.

Reported at the table, 2026-09-06, with the map open: a servant "beside you", a
hooded man "at the far end of the corridor", a merchant and two guards — all five
promoted to the same zone and laid out as one column three squares off. "This is
not how the people should be lined up according to the prose."
"""
from __future__ import annotations

from gm import judgement
from rules.bestiary import instantiate
from rules.dice import Dice
from rules.engine import SQUARES_BY_ZONE, Engine, Scene
from rules.sheet import load_pc


def _mentions(beat: str) -> dict[str, str]:
    return {m.group(1): judgement.zone_of_mention(beat, *m.span())
            for m in judgement._CAST_INTRO.finditer(beat)}


def test_the_words_around_a_person_say_which_zone_they_stand_in():
    """The engine's three words — engaged, near, far — read off the phrases the
    prose actually uses, on either side of the person, and never across a full
    stop: the far end belongs to the man, not to the servant in the next sentence."""
    beat = ("He stands at the far end of the corridor, a hooded man with a chain. "
            "Beside you, the servant carrying jugs has stopped. "
            "A merchant watches from across the square. "
            "A guard grabs your arm.")
    zones = _mentions(beat)
    assert zones["hooded man"] == "far"
    assert zones["servant"] == "engaged"
    assert zones["merchant"] == "far"
    assert zones["guard"] == "engaged"
    # Nothing said means the engine's own default.
    assert _mentions("A woman is there.")["woman"] == "near"


def test_a_noted_person_is_promoted_into_the_zone_the_prose_gave_them():
    s = Scene()
    s.add(load_pc("fixtures/pc-kesst.json"))
    beat = ("A hooded man waits at the far end of the hall. "
            "Beside you, a servant has stopped with two jugs.")
    added = judgement.note_cast(s, beat, turn=2)
    made = judgement.promote_cast(s, added)
    assert len(made) == 2
    by_name = {s.actors[e["ref"]].name: s.zones[e["ref"]]
               for e in s.cast if e.get("ref")}
    assert by_name["hooded man"] == "far"
    assert by_name["servant"] == "engaged"


def test_the_battlefield_lays_each_person_at_their_own_zone_and_not_in_one_column():
    """Before: everyone not on the player's side went in one column at one distance,
    rows counting downward — five in a line. Now the servant who was beside you is
    one square off, the man at the far end is eight, and the rows fan out from the
    player's own row."""
    s = Scene()
    pc = s.add(load_pc("fixtures/pc-kesst.json"))
    near = s.add(instantiate("guildhand", scene=s, name="the merchant"), zone="near")
    close = s.add(instantiate("guildhand", scene=s, name="the servant"), zone="engaged")
    away = s.add(instantiate("watchman", scene=s, name="the hooded man"), zone="far")
    engine = Engine(s, Dice(seed=1))
    engine._lay_battlefield({"a": [pc.ref], "b": [near.ref, close.ref, away.ref]})
    px, py = s.positions[pc.ref]
    dx = {r: s.positions[r][0] - px for r in (near.ref, close.ref, away.ref)}
    assert dx[close.ref] == SQUARES_BY_ZONE["engaged"] == 1
    assert dx[near.ref] == SQUARES_BY_ZONE["near"] == 3
    assert dx[away.ref] == SQUARES_BY_ZONE["far"] == 8
    rows = sorted(s.positions[r][1] - py for r in (near.ref, close.ref, away.ref))
    assert rows == [-1, 0, 1], rows
