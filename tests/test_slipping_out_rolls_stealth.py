"""The manner of a move is rolled where 1e rolls it (the register's deferred row).

"I slip out quietly" beside a place chip: since 2026-09-29 the words are read as a Stealth
check (`declared_ops` gave ['check'] in all three exports), counted as the MANNER of the
move so it takes the engine's own door with no planner asked — and the Stealth check was
then never rolled. The narrator was handed "quietly" and nothing decided whether anybody
saw.

When 1e calls for it (CRB p.106, Archives of Nethys, Skills > Stealth): the check "is
opposed by the Perception check of anyone who might notice you", made "as part of
movement, so it doesn't take a separate action"; up to half speed at no penalty, which is
what slipping out is. So: rolled against the sharpest eye here, and with nobody here to
notice, not rolled at all. Not modelled: "if people are observing you … you can't use
Stealth" — nothing records who is watching the player — and the Bluff that can buy the
diversion.
"""
from __future__ import annotations

import json

import pytest
from django.test import Client

from gm import judgement
from rules.bestiary import instantiate

from test_a_take_is_not_a_boast import _sam
from test_exits_attach import _players, _say, _way, desk  # noqa: F401 — the fixture


def test_slipping_out_past_somebody_is_stealth_against_their_perception():
    s = _sam("the watchman", "the clerk")
    out = judgement.manner_checks("I slip out quietly", s)
    assert len(out) == 1
    check = out[0]
    assert check["params"]["skill"] == "stealth"
    assert check["params"]["opposed_by"]["skill"] == "perception"
    assert check["params"]["opposed_by"]["ref"] in ("c1", "c2")
    assert "dc" not in check["params"]


def test_with_nobody_to_notice_nothing_is_rolled():
    """"Anyone who might notice you" — there is no one, so there is no roll."""
    s = _sam()
    assert judgement.manner_checks("I slip out quietly", s) == []
    assert judgement.inject_checks([], "I sneak past the stalls", s) == []


def test_the_sharpest_eye_is_the_one_rolled_against():
    s = _sam("the watchman", "the clerk")
    # A bestiary body carries its printed skills flat (`flat_skills`).
    s.actors["c2"].flat_skills = dict(s.actors["c2"].flat_skills or {}, perception=25)
    assert judgement.stealth_opposed(s) == {"ref": "c2", "skill": "perception"}


@pytest.mark.parametrize("line", ["I nod to the watchman", "I walk out", ""])
def test_only_stealth_is_manner(line):
    assert judgement.manner_checks(line, _sam("the watchman")) == []


def test_the_spoken_turn_rolls_it_opposed_too():
    """The planner's path: the check `inject_checks` declares is opposed, not a band."""
    s = _sam("the watchman")
    out = judgement.inject_checks([{"op": "narrate_only"}], "I sneak past the watchman", s)
    check = next(r for r in out if r.get("op") == "check")
    assert check["params"]["opposed_by"] == {"ref": "c1", "skill": "perception"}


def test_slipping_out_past_a_watchman_on_the_exits_row_asks_for_the_die(worlds, desk):
    """Through the real `/api/say`, beside a place chip, no planner asked: with somebody
    here the die is the player's to roll before the walk, and the walk follows it."""
    c = desk["c"]
    way = _way(c)
    c.scene.add(instantiate("guildhand", scene=c.scene, name="the watchman"))
    c.save()
    r = _say("I slip out quietly", way)
    assert r.status_code == 200, r.content[:300]
    assert desk["calls"]["plans"] == []
    state = r.json()
    assert state.get("awaiting"), "the Stealth die is the player's"
    assert "Stealth" in json.dumps(state["awaiting"])
    r2 = Client().post("/api/roll", content_type="application/json",
                       data=json.dumps({"face": 15}))
    assert r2.status_code == 200, r2.content[:300]
    assert c.scene.at == way["id"]
    assert _players(c)[-1]["text"] == "I slip out quietly"
