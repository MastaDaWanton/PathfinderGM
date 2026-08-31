"""Turn order, and a campaign that survives the app closing.

Both of these are "can you actually run a game" problems rather than rules problems, and
both were found by trying to play rather than by testing.
"""
from __future__ import annotations

import json

import pytest

from rules.bestiary import instantiate
from rules.dice import Dice
from rules.engine import Engine, Scene
from rules.sheet import load_pc


@pytest.fixture
def scene():
    s = Scene(location_id="5bbd0c40345f")
    s.add(load_pc("fixtures/pc-kesst.json"))
    s.add(instantiate("thug", scene=s, name="the thug"))
    s.add(instantiate("watchman", scene=s, name="the watchman"))
    return s


@pytest.fixture
def engine(scene):
    return Engine(scene, Dice(seed=99))


def begin(engine, scene):
    return engine.run(engine.validate([{
        "op": "begin_encounter",
        "params": {"sides": {"pc": ["pc"], "them": ["c1", "c2"]}},
    }]))


# --- Turn order ------------------------------------------------------------------

def test_initiative_sets_a_turn_pointer(engine, scene):
    """Initiative used to be rolled and then never consulted: the player could swing and
    nothing ever swung back, because nothing tracked whose turn it was."""
    assert not scene.in_encounter
    begin(engine, scene)
    assert scene.in_encounter
    assert scene.round == 1
    assert scene.current_ref() == scene.initiative[0][0]


def test_the_order_cycles_and_counts_rounds(engine, scene):
    begin(engine, scene)
    seen = [scene.current_ref()]
    for _ in range(len(scene.initiative) - 1):
        seen.append(scene.advance_turn())
    assert sorted(seen) == ["c1", "c2", "pc"]
    assert scene.round == 1

    scene.advance_turn()               # wraps to the top
    assert scene.round == 2
    assert scene.current_ref() == scene.initiative[0][0]


def test_the_unconscious_are_skipped_rather_than_stalled_on(engine, scene):
    """A fight that stops on a downed combatant never reaches the player again."""
    begin(engine, scene)
    scene.get("c1").hp = -3
    scene.get("c1").apply_hp_state()

    visited = {scene.advance_turn() for _ in range(6)}
    assert "c1" not in visited
    assert {"pc", "c2"} <= visited


def test_timed_conditions_expire_as_rounds_pass(engine, scene):
    """A round is the unit durations are measured in, so advancing one has to tick them
    or a two-round condition lasts the whole fight."""
    begin(engine, scene)
    scene.get("c2").add_condition("shaken", 2)
    for _ in range(len(scene.initiative) * 2):
        scene.advance_turn()
    assert not scene.get("c2").has_condition("shaken")


def test_a_side_with_nobody_standing_ends_the_fight(engine, scene):
    begin(engine, scene)
    assert scene.sides_standing() == 2
    for ref in ("c1", "c2"):
        scene.get(ref).hp = -5
        scene.get(ref).apply_hp_state()
    assert scene.sides_standing() == 1


def test_ending_an_encounter_clears_the_order(engine, scene):
    begin(engine, scene)
    scene.end_encounter()
    assert not scene.in_encounter
    assert scene.initiative == [] and scene.turn == -1 and scene.round == 0


def test_advance_returns_none_when_nobody_can_act(engine, scene):
    begin(engine, scene)
    for ref in ("pc", "c1", "c2"):
        scene.get(ref).add_condition("unconscious")
    assert scene.advance_turn() is None


# --- The campaign save ----------------------------------------------------------------

def test_a_campaign_resumes_instead_of_being_overwritten(tmp_path, settings=None):
    """Found by trying to play across a restart. `current()` never read the save, and
    because it then called `save()` on the fresh campaign, restarting the server did not
    merely forget the game — it destroyed the file.
    """
    from django.test import override_settings
    from play import campaign as cm

    with override_settings(CAMPAIGN_DIR=tmp_path):
        cm._LIVE.clear()
        first = cm.current("resume-test")
        first.transcript.append({"who": "player", "text": "a line that must survive"})
        first.scene.pc().hp = 3
        first.save()

        cm._LIVE.clear()               # as if the server had restarted
        again = cm.current("resume-test")

    assert any(b["text"] == "a line that must survive" for b in again.transcript)
    assert again.scene.pc().hp == 3


def test_starting_a_new_game_archives_the_old_one(tmp_path):
    """`?new=1` is one keystroke from a campaign nobody meant to end."""
    from django.test import override_settings
    from play import campaign as cm

    with override_settings(CAMPAIGN_DIR=tmp_path):
        cm._LIVE.clear()
        cm.current("archive-test").transcript.append({"who": "player", "text": "old game"})
        cm.current("archive-test").save()

        cm._LIVE.clear()
        cm.current("archive-test", reset=True)

        archived = [p for p in tmp_path.glob("archive-test-*.json")]
        assert len(archived) == 1
        kept = json.loads(archived[0].read_text(encoding="utf-8"))
        assert any(b["text"] == "old game" for b in kept["transcript"])


def test_an_unreadable_save_is_left_alone_and_never_replaced(tmp_path):
    """A save this build cannot parse is the player's only copy of their game.

    This test used to assert the opposite of its own docstring: `c is not None  # play
    continues` passed precisely BECAUSE the campaign had been renamed out of the way
    and a fresh character written in its place. `_resume` swallowed every exception,
    renamed the file, and returned None; `current()` answered None by calling `_begin`,
    which saves immediately. So any error on the load path — a new key, a validate()
    failure, a half-written file — cost the player their campaign, and the screen said
    nothing at all.

    The file now stays exactly where it is and the failure travels, because a campaign
    is the least replaceable thing in the user's data directory: the app may refuse to
    open one, and may never decide on the player's behalf that it is gone."""
    import pytest as _pytest
    from django.test import override_settings
    from play import campaign as cm

    with override_settings(CAMPAIGN_DIR=tmp_path):
        cm._LIVE.clear()
        save = tmp_path / "broken-test.json"
        save.write_text("{not json", encoding="utf-8")
        with _pytest.raises(cm.UnreadableSave, match="left where it is"):
            cm.current("broken-test")
        assert save.read_text(encoding="utf-8") == "{not json", "the save was touched"
        assert not list(tmp_path.glob("broken-test-unreadable-*.json"))
        assert [p.name for p in tmp_path.glob("*.json")] == ["broken-test.json"]


def test_a_save_from_an_older_build_still_opens(tmp_path):
    """`save_version != SAVE_VERSION` made every shape change unshippable: bumping the
    number would have declared all twelve of the user's campaigns unreadable at once,
    and the recovery path answered that by renaming them. Older opens; only a save from
    a NEWER build is refused, because that is the one this code genuinely cannot read —
    and it says so with the fix in the message."""
    import json as _json

    import pytest as _pytest
    from django.test import override_settings
    from play import campaign as cm

    with override_settings(CAMPAIGN_DIR=tmp_path):
        cm._LIVE.clear()
        c = cm.current("version-test")
        c.save()
        raw = _json.loads((tmp_path / "version-test.json").read_text(encoding="utf-8"))

        raw["save_version"] = cm.SAVE_VERSION - 1
        (tmp_path / "version-test.json").write_text(_json.dumps(raw), encoding="utf-8")
        cm._LIVE.clear()
        assert cm.current("version-test") is not None, "an older save must still open"

        raw["save_version"] = cm.SAVE_VERSION + 1
        (tmp_path / "version-test.json").write_text(_json.dumps(raw), encoding="utf-8")
        cm._LIVE.clear()
        with _pytest.raises(cm.UnreadableSave, match="newer version"):
            cm.current("version-test")


def test_a_fight_where_nobody_can_act_waits_rather_than_vanishing(scene):
    """Found by an adversarial review of the vocabulary split, under a green suite.

    Once `conscious` meant "still in the fight" rather than "can act now", a round in
    which EVERY combatant was stunned left `sides_standing()` at 2 — so the loop's own
    "the fight is over" branch was skipped — while `advance_turn` returned None, which
    `play/views.py` reads as the fight being over. The encounter ended with two live
    enemies upright, paid no XP and printed nothing at all.

    Holds are timed, so the answer is to keep looking across rounds. The first attempt
    at this fix returned None just as silently: the scan only ticks when it wraps past
    the top of the order, and a fight starting from `turn == -1` never wraps on its
    first pass, so the retry re-walked one round for ever and expired nothing.
    """
    s = scene
    s.initiative = [(r, 18 - i) for i, r in enumerate(s.actors)]
    s.turn = -1
    s.sides = {"party": ["pc"], "them": [r for r in s.actors if r != "pc"]}
    for a in s.actors.values():
        a.add_condition("stunned", source="a thunderclap", rounds=3)
    assert s.advance_turn.__self__ is s

    ref = s.advance_turn()

    assert ref is not None, "the fight ended with everyone still standing in it"
    assert s.round >= 3, "the holds were never ticked down"
    assert not s.actors[ref].has_condition("stunned")
    assert s.sides_standing() == 2, "and both sides are still in it"


def test_a_death_during_a_skipped_round_is_still_reported(engine, scene):
    """`scene.bleeding` was an assignment inside the per-round loop, six lines above a
    comment explaining why `hazards` beside it must be appended. Once one call could
    skip up to twenty rounds looking for somebody able to act, only the last round's
    dying survived — measured, a thug bled to death during a skipped round and
    `scene.bleeding` came back empty, so "he stops moving" was never said.

    Law 3 in reverse: the engine recorded it and the player could never be told.
    """
    s = scene
    dying = next(a for r, a in s.actors.items() if r != "pc")
    dying.hp = -9
    dying.apply_hp_state()
    others = [a for a in s.actors.values() if a is not dying]
    for a in others:
        a.add_condition("stunned", source="a thunderclap", rounds=6)
    s.initiative = [(r, 20 - i * 3) for i, r in enumerate(s.actors)]
    s.turn = 0

    s.advance_turn()

    assert s.round >= 5, "the rounds were not skipped, so this proves nothing"
    assert s.bleeding, "a creature bled out during a skipped round and nothing was said"


def test_a_departed_creature_takes_its_spawn_distance_with_it(scene):
    """Refs are recycled — the bestiary hands out the lowest free `cN` — so a stated
    spawn distance left behind is inherited by whoever takes the name next. Measured: an
    archer who arrived at 120 feet departed, and the next spawn to reuse `c1` was laid
    out 120 feet away despite asking for `engaged`.

    Harmless only while the field was dropped at every save; it is persisted now, so the
    poisoning would have lasted the campaign. This is the lesson CLAUDE.md records about
    derived state in the user's data directory, arriving through the scene save.
    """
    s = scene
    ref = next(r for r in s.actors if r != "pc")
    s.spawn_feet[ref] = 120

    s.depart(ref)

    assert ref not in s.spawn_feet, "the next creature to take this ref inherits 120 feet"


def test_how_far_away_a_spawn_arrived_survives_the_save(tmp_path):
    """`spawn` writes `spawn_feet` and `begin_encounter` reads it, and those are two
    different turns — so the one scene field whose entire life spans a turn boundary was
    the one the save dropped. A restart between setting an ambush up and the fight
    starting put every archer back at the `far` default of forty feet, however far the
    spawn had said they were.
    """
    from django.test import override_settings
    from play import campaign as cm

    with override_settings(CAMPAIGN_DIR=tmp_path):
        cm._LIVE.clear()
        c = cm.current("spawn-distance")
        c.scene.spawn_feet["c9"] = 120
        c.save()

        cm._LIVE.clear()
        back = cm.current("spawn-distance")

    assert back.scene.spawn_feet.get("c9") == 120, (
        "the archer's stated distance was lost across the restart")


def test_turn_order_survives_the_save(tmp_path):
    from django.test import override_settings
    from play import campaign as cm

    with override_settings(CAMPAIGN_DIR=tmp_path):
        cm._LIVE.clear()
        c = cm.current("turn-save")
        e = c.engine()
        thug = instantiate("thug", scene=c.scene, name="the thug")
        c.scene.add(thug)
        e.run(e.validate([{"op": "begin_encounter",
                           "params": {"sides": {"pc": ["pc"], "them": [thug.ref]}}}]))
        expected = (c.scene.turn, c.scene.round, c.scene.current_ref(), c.scene.sides)
        c.save()

        cm._LIVE.clear()
        back = cm.current("turn-save")

    assert (back.scene.turn, back.scene.round, back.scene.current_ref(),
            back.scene.sides) == expected
    assert back.scene.in_encounter
