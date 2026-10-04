"""Lane D, items 9.1 and 15 of docs/playtest-2026-09-28.md: keepers stay in the background
until dealt with; pronouns are stated, adopted from the page, and the suggestions follow
who the player is dealing with.

What was measured on the Bobby playtest (turn 4, tests/replays/bobby-2026-09-28):

  * the market's keeper (Ashla) was the first person met at the market — minted on
    arrival for the trade panel, listed in WHO IS HERE like anyone, so walked up;
  * Drenn was they/them on the sheet (no world character carries a gender), "a man" and
    "he says" on the page, and the suggestions read "I ask her what she's looking for…".
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

import replays
from gm import prompts
from gm.checks import BeatContext
from play import aftermath
from rules import keepers, schemes
from rules.bestiary import instantiate
from rules.dice import Dice
from rules.engine import Engine, Scene
from rules.sheet import load_pc

WORK_HOUR = 10 * 60


def _market(world):
    row = (world.play.get("settlements") or [])[0]
    s = Scene(location_id=row["id"])
    s.add(load_pc("fixtures/pc-kesst.json"))
    s.clock_minutes = WORK_HOUR
    e = Engine(s, Dice(seed=5), world=world)
    e.place_party(schemes._place_for(e, "market", {})["id"])
    return s, e


def _keeper(s):
    k = next((a for a in s.actors.values()
              if keepers.is_keeper(getattr(a, "world_entity_id", "") or "")), None)
    if k is None:
        k = instantiate("guildhand", scene=s, name="Ashla Ironvale",
                        world_entity_id=keepers.entity_id(s.at))
        s.add(k)
    return k


def _brief(world, s, e, player_text="", reading=None):
    return prompts.scene_brief(world, s, world.get(s.location_id), here=e.here(),
                               known=e.places(), reading=reading, player_text=player_text)


def _ctx(s, e, world, *, text, said, reading=None, player_text="", facts=None):
    return BeatContext(door="turn", text=text, player_text=player_text, engine=e, scene=s,
                       world=world, location=world.get(s.location_id), reading=reading,
                       outcomes=(), tells=(), said=tuple(said), attribution=None, brief="",
                       brief_facts=facts or {}, pull=None, was_at=s.at, acting="", turn=8)


# --- 9.1: keepers in the background --------------------------------------------------------

def test_a_keeper_not_dealt_with_is_in_the_background(worlds):
    """Ashla was the first person met at the market. Until the player deals with her, the
    brief says she is at her work and does not approach or speak first."""
    s, e = _market(worlds)
    k = _keeper(s)
    brief = _brief(worlds, s, e, "I look around.")
    assert f"IN THE BACKGROUND (fact): {k.name} ({k.ref})" in brief
    e.join_talk(k, how="the player spoke to her")
    # Her line, not every line: a town's market has two keepers since I2 (its master
    # and its general store), and the other one is still at their work.
    assert f"IN THE BACKGROUND (fact): {k.name} ({k.ref})" not in _brief(
        worlds, s, e, "I look around.")


def test_the_player_turning_to_the_keeper_brings_her_forward(worlds):
    s, e = _market(worlds)
    k = _keeper(s)
    reading = {"question": False, "claims": [], "actions": [
        {"act": "talk", "target": k.name, "says": "what she sells"}]}
    assert f"IN THE BACKGROUND (fact): {k.name} ({k.ref})" not in _brief(
        worlds, s, e, f"I ask {k.name} what she sells", reading)
    # And a counter opening this turn is dealing with her, read off the brief's `buying`.
    brief = prompts.scene_brief(worlds, s, worlds.get(s.location_id), here=e.here(),
                                known=e.places(), buying="a coil of rope")
    assert "IN THE BACKGROUND" not in brief


def test_a_keeper_speaking_first_is_flagged(worlds):
    from gm.checks import keeper_forward

    s, e = _market(worlds)
    k = _keeper(s)
    line = "Looking for something, friend? Best rope in town."
    said = [{"who": k.ref, "to": "you", "line": line}]
    found = keeper_forward.find(_ctx(s, e, worlds, text=f"'{line}'", said=said,
                                     player_text="I look around."))
    assert [f.kind for f in found] == ["keeper-forward"] and found[0].weight == 2
    reading = {"question": False, "claims": [], "actions": [
        {"act": "talk", "target": k.name, "says": "about rope"}]}
    assert keeper_forward.find(_ctx(s, e, worlds, text=line, said=said, reading=reading,
                                    player_text=f"I ask {k.name} about rope")) == []


# --- 15: pronouns ----------------------------------------------------------------------------

def _drenn(s, gender=""):
    d = instantiate("guildhand", scene=s, name="Drenn Ironvale")
    s.add(d)
    if gender:
        d.gender, d.pronouns = gender, {"man": "he/him", "woman": "she/her"}[gender]
    return d


def _after(s, e, world, *, text, said, suggestions, reading=None, talking=(),
           pronouns=None):
    """The "beat" stage. `pronouns`: the beat reader's answer for the they/them people
    here, stubbed as a careful reader gives it (tests/beat_reader/stub.py); until
    2026-10-03 `pronouns_adopted` read "'…,' he says" beside their line with a pattern."""
    c = SimpleNamespace(scene=s, world=world, transcript=[], suggestions=list(suggestions),
                        engine=lambda: e)
    beat_reading = None
    if pronouns is not None:
        from tests.beat_reader import stub

        beat_reading = stub.read(text, s, engine=e, said=said, pronouns=pronouns)
    ctx = aftermath.context("beat", "turn", c, engine=e, text=text, said=said,
                            reading=reading, attribution=beat_reading)
    rows = aftermath.run("beat", ctx)
    return rows, c


def test_the_brief_states_pronouns_that_are_set(worlds):
    s, e = _market(worlds)
    d = _drenn(s, "man")
    brief = _brief(worlds, s, e)
    assert f"SPEAK OF THEM AS" in brief and f"{d.name} ({d.ref}) he/him" in brief
    other = _drenn(s)
    assert f"{other.name} ({other.ref})" not in brief.split("SPEAK OF THEM AS")[1] \
        .split("\n")[0]


def test_suggestions_about_her_when_a_man_spoke_become_him(worlds):
    """Item 15: "I ask her what she's looking for…" with only Drenn — he/him — on the
    page, speaking to the player."""
    s, e = _market(worlds)
    d = _drenn(s, "man")
    line = "Tell me, have you seen such a thing?"
    rows, c = _after(s, e, worlds, text=f"'{line}' Drenn Ironvale asks.",
                     said=[{"who": d.ref, "to": "you", "line": line}],
                     suggestions=["I ask her what she's looking for", "I head back to the gate",
                                  "I tell her \"I haven't seen her\""])
    assert c.suggestions[0] == "I ask him what he's looking for"
    assert c.suggestions[1] == "I head back to the gate"
    # Inside the player's own quoted words a pronoun is theirs to choose.
    assert c.suggestions[2] == "I tell him \"I haven't seen her\""
    kinds = [r for r in rows if r.get("kind") == "suggestion-pronoun"]
    assert kinds[0] == {"kind": "suggestion-pronoun", "before": "I ask her what she's looking for",
                        "after": "I ask him what he's looking for"}


def test_a_pronoun_that_fits_somebody_else_on_the_page_is_kept(worlds):
    s, e = _market(worlds)
    d = _drenn(s, "man")
    w = _drenn(s, "woman")
    w.name = "the woman at the fish stall"
    line = "Ask her, not me."
    rows, c = _after(s, e, worlds,
                     text=f"'{line}' Drenn Ironvale nods at the woman at the fish stall.",
                     said=[{"who": d.ref, "to": "you", "line": line}],
                     suggestions=["I ask her about the net"])
    assert c.suggestions == ["I ask her about the net"] and not [
        r for r in rows if r.get("kind") == "suggestion-pronoun"]


def test_a_pronoun_that_cannot_be_squared_is_dropped(worlds):
    """Nobody on the page it fits, and nobody the player is dealing with to give it: the
    suggestion goes rather than point at nobody. (A person on the page whose pronouns are
    not set fits either family, so this is rarer than it sounds.)"""
    s, e = _market(worlds)
    d = _drenn(s, "man")
    line = "Fine day for it."
    rows, c = _after(s, e, worlds, text=f"Drenn Ironvale calls to a carter: '{line}'",
                     said=[{"who": d.ref, "to": "", "line": line}],
                     suggestions=["I ask her about the net", "I walk on"])
    assert c.suggestions == ["I walk on"]
    assert {"kind": "suggestion-pronoun", "before": "I ask her about the net",
            "after": ""} in rows


def test_pronouns_are_adopted_from_the_page_and_held(worlds):
    """Q26: the first gendered reference the page makes to somebody the world gave no
    gender. "'…,' he says" beside Drenn's own line makes him he/him, and a later "she"
    does not undo it."""
    s, e = _market(worlds)
    d = _drenn(s)
    line = "You look like you could use work"
    rows, _c = _after(s, e, worlds, text=f"'{line},' he says, not unkindly.",
                      said=[{"who": d.ref, "to": "you", "line": line}], suggestions=[],
                      pronouns={d.ref: "he"})
    assert d.pronouns == "he/him" and d.gender == "man"
    assert {"kind": "pronouns-adopted", "ref": d.ref, "pronouns": "he/him"}.items() <= \
        next(r for r in rows if r.get("kind") == "pronouns-adopted").items()
    _after(s, e, worlds, text=f"'{line},' she says.",
           said=[{"who": d.ref, "to": "you", "line": line}], suggestions=[],
           pronouns={d.ref: "she"})
    assert d.pronouns == "he/him"


def test_the_replayed_drenn_beat_adopts_he_and_repairs_the_suggestion():
    """The Bobby beat: Drenn's "'You! You have the look of …,' he says", and a
    suggestion about "her" after it."""
    if not replays.available():
        pytest.skip("the Bobby corpus is not on this disk (kept out of the repository)")
    from world.loader import load_cached

    world = load_cached("fixtures/aurvantis-campaign.json")
    s = Scene(location_id=world.by_name("Vormoor", kind="CITY").id)
    s.add(load_pc("fixtures/pc-kesst.json"))
    s.clock_minutes = WORK_HOUR
    e = Engine(s, Dice(seed=5), world=world)
    e.place_party(schemes._place_for(e, "market", {})["id"])
    d = _drenn(s)
    beat = replays.turn(4)["beats"][0]
    said = [dict(r, who=d.ref) for r in beat["said"]]
    rows, c = _after(s, e, world, text=beat["text"], said=said,
                     suggestions=["I ask her what she's looking for"],
                     pronouns={d.ref: "he"})
    assert d.pronouns == "he/him"
    assert c.suggestions == ["I ask him what he's looking for"]
