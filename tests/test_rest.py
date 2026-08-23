"""Resting, and swapping between characters.

Natural healing is Core Rulebook p.191: "With a full night's rest (8 hours of sleep or
more), you recover 1 hit point per character level... If you undergo complete bed rest
for an entire day and night, you recover twice your character level in hit points."

Without it, winning a fight left you wounded for ever — the app could take hit points
away and had no way at all to give them back.
"""
from __future__ import annotations

import pytest
from django.test import override_settings

from rules.bestiary import instantiate
from rules.dice import Dice
from rules.engine import Engine, Scene
from rules.intents import IntentError, parse
from rules.sheet import load_pc


@pytest.fixture
def scene():
    s = Scene(location_id="5bbd0c40345f")
    s.add(load_pc("fixtures/pc-kesst.json"))
    s.add(instantiate("thug", scene=s, name="the thug"))
    return s


@pytest.fixture
def engine(scene):
    return Engine(scene, Dice(seed=42))


# --- Natural healing ------------------------------------------------------------------

def test_a_night_heals_your_level_in_hit_points():
    """Kesst is level 1, so a night is one hit point. Slow on purpose: 1e wants wounds
    to matter for more than a scene."""
    pc = load_pc("fixtures/pc-kesst.json")
    pc.hp = 4
    result = pc.rest("night")
    assert result["healed"] == 1
    assert pc.hp == 5
    assert result["hours"] == 8


def test_bed_rest_heals_twice_as_much():
    pc = load_pc("fixtures/pc-kesst.json")
    pc.hp = 4
    result = pc.rest("bed rest")
    assert result["healed"] == 2
    assert result["hours"] == 24


def test_a_higher_level_character_heals_faster():
    """Per *level*, so this is the thing that stops a long campaign grinding to a halt."""
    from rules.sheet import from_dict

    veteran = from_dict({
        "name": "veteran", "kind": "pc", "class": "fighter", "level": 6,
        "abilities": {"str": 14, "dex": 12, "con": 14, "int": 10, "wis": 10, "cha": 10},
        "hp": 50, "ranks": {},
    })
    veteran.hp = 10
    assert veteran.rest("night")["healed"] == 6


def test_you_cannot_heal_past_full():
    pc = load_pc("fixtures/pc-kesst.json")
    pc.hp = pc.hp_max
    assert pc.rest("night")["healed"] == 0
    assert pc.hp == pc.hp_max


def test_sleeping_does_not_carry_you_up_from_below_zero():
    """A night's sleep must not take someone from -6 to a comfortable 4. Healing starts
    from 0; getting there is stabilising's job, not resting's."""
    pc = load_pc("fixtures/pc-kesst.json")
    pc.hp = -6
    pc.apply_hp_state()
    pc.remove_condition("dying")
    pc.add_condition("stable")

    pc.rest("night")
    assert pc.hp == 1


def test_resting_gets_you_back_on_your_feet():
    pc = load_pc("fixtures/pc-kesst.json")
    pc.hp = -2
    pc.apply_hp_state()
    pc.remove_condition("dying")
    pc.add_condition("stable")

    result = pc.rest("night")
    assert result["woke"]
    assert not pc.has_condition("unconscious") and not pc.has_condition("stable")


def test_a_night_sleeps_off_fatigue():
    pc = load_pc("fixtures/pc-kesst.json")
    pc.add_condition("fatigued")
    pc.rest("night")
    assert not pc.has_condition("fatigued")


def test_exhaustion_becomes_fatigue_rather_than_vanishing():
    """1e: rest takes exhausted down to fatigued, not to fine."""
    pc = load_pc("fixtures/pc-kesst.json")
    pc.add_condition("exhausted")
    pc.rest("night")
    assert not pc.has_condition("exhausted")
    assert pc.has_condition("fatigued")


def test_you_are_on_your_feet_in_the_morning():
    """Found in play: Kesst slept a night in a doorway and woke still Prone. Waking
    prone, shaken and entangled from a fight the night before is the kind of stale state
    that quietly poisons every roll for the rest of the campaign."""
    pc = load_pc("fixtures/pc-kesst.json")
    for c in ("prone", "shaken", "entangled", "dazzled"):
        pc.add_condition(c)
    pc.rest("night")
    for c in ("prone", "shaken", "entangled", "dazzled"):
        assert not pc.has_condition(c), c


def test_the_dead_do_not_rest():
    pc = load_pc("fixtures/pc-kesst.json")
    pc.hp = -50
    pc.apply_hp_state()
    assert pc.rest("night")["healed"] == 0


# --- As an intent ------------------------------------------------------------------------

def test_the_engine_resolves_a_rest(engine, scene):
    pc = scene.pc()
    pc.hp = 3
    res = engine.run(engine.validate([
        {"op": "rest", "actor": "pc", "because": "the yard is quiet at last",
         "params": {"kind": "night"}},
    ]))
    assert pc.hp == 4
    assert "recovers 1 hit point" in res.outcomes[0].tell
    assert scene.clock_minutes >= 8 * 60


@pytest.mark.parametrize("said", ["sleep", "long rest", "overnight", "camp", "night"])
def test_the_words_a_model_reaches_for_all_mean_a_night(said):
    assert parse({"op": "rest", "params": {"kind": said}}).params["kind"] == "night"


@pytest.mark.parametrize("said", ["bed", "full day", "complete bed rest"])
def test_the_longer_rest_is_recognised_too(said):
    assert parse({"op": "rest", "params": {"kind": said}}).params["kind"] == "bed rest"


def test_an_invented_kind_of_rest_is_refused_with_the_two_that_exist():
    with pytest.raises(IntentError) as e:
        parse({"op": "rest", "params": {"kind": "a quick breather"}})
    assert "night is eight hours" in str(e.value)


def test_nobody_sleeps_through_a_fight(engine, scene):
    """"Any significant interruption during your rest prevents you from healing that
    night." Being in a fight is the significant interruption."""
    engine.run(engine.validate([
        {"op": "begin_encounter", "params": {"sides": {"pc": ["pc"], "them": ["c1"]}}}
    ]))
    with pytest.raises(IntentError, match="fight going on"):
        engine.validate([{"op": "rest", "params": {"kind": "night"}}])


def test_a_fight_can_be_ended_so_that_resting_becomes_possible(engine, scene):
    """Found in play: the player said "I find a doorway and sleep until morning", the GM
    correctly reached for `rest`, and it was refused because a fight was still running —
    then the GM tried `end_encounter`, which did not exist. A fight could only end by one
    side being wiped out, so a character could never disengage and never rest afterwards.
    """
    engine.run(engine.validate([
        {"op": "begin_encounter", "params": {"sides": {"pc": ["pc"], "them": ["c1"]}}}
    ]))
    assert scene.in_encounter

    res = engine.run(engine.validate([
        {"op": "end_encounter", "because": "they have had enough and back off"}
    ]))
    assert not scene.in_encounter
    assert "fighting stops" in res.outcomes[0].tell

    engine.run(engine.validate([{"op": "rest", "params": {"kind": "night"}}]))


def test_ending_a_fight_that_is_not_happening_is_harmless(engine):
    engine.run(engine.validate([{"op": "end_encounter"}]))


def test_the_dying_are_stabilised_before_they_are_rested(engine, scene):
    pc = scene.pc()
    pc.hp = -3
    pc.apply_hp_state()
    with pytest.raises(IntentError, match="bleeding out"):
        engine.validate([{"op": "rest", "params": {"kind": "night"}}])


def test_timed_conditions_are_long_gone_by_morning(engine, scene):
    pc = scene.pc()
    pc.add_condition("shaken", 10)
    engine.run(engine.validate([{"op": "rest", "params": {"kind": "night"}}]))
    assert not pc.has_condition("shaken")


# --- Swapping between characters -----------------------------------------------------------

def test_switching_resumes_the_other_campaign(tmp_path):
    """One campaign per character is what makes this possible: a character you come back
    to is where you left them, not at the start of a new game."""
    from play import campaign as cm
    from play import roster

    with override_settings(CAMPAIGN_DIR=tmp_path / "campaigns"):
        cm._LIVE.clear()
        first = cm.begin_with(load_pc("fixtures/pc-kesst.json"))
        first.transcript.append({"who": "player", "text": "kesst was here"})
        first.scene.pc().hp = 3
        first.save()
        kesst_id = first.character_id

        second = cm.begin_with(roster.from_pregen("pc-borin"))
        assert second.scene.pc().name == "Borin Achereth"
        assert second.character_id != kesst_id

        back = cm.switch_to(kesst_id)

    assert back.scene.pc().name == "Kesst Vayr"
    assert back.scene.pc().hp == 3
    assert any(b["text"] == "kesst was here" for b in back.transcript)


def test_a_character_resumes_the_campaign_their_entry_names(tmp_path):
    """Found in play: switching to Kesst opened a brand new campaign at 9/9 and left the
    one she had actually been played in — 3 hp, twenty-three lines of transcript — behind.

    `switch_to` derived the campaign from the character's id, which is very nearly always
    right and was wrong for every character created before campaigns were per-character:
    theirs is called `slice`. The entry already records `campaign_id`; it just was not
    being read.
    """
    from play import campaign as cm
    from play import roster

    with override_settings(CAMPAIGN_DIR=tmp_path / "campaigns"):
        cm._LIVE.clear()
        legacy = cm.new_campaign("slice", character=load_pc("fixtures/pc-kesst.json"))
        entry = roster.enrol(legacy.scene.pc(), campaign_id="slice")
        legacy.character_id = entry.id
        legacy.scene.pc().hp = 3
        legacy.transcript.append({"who": "player", "text": "kesst was here"})
        legacy.save()
        cm._LIVE.clear()

        back = cm.switch_to(entry.id)
        assert back.id == "slice"
        assert back.scene.pc().hp == 3
        assert any(b["text"] == "kesst was here" for b in back.transcript)

        # Switching brings the roster's copy of the sheet up to date, so the list you are
        # picking from is right at the moment you are reading it.
        assert roster.load(entry.id).summary()["hp"] == "3/9"


def test_the_roster_shows_the_hit_points_the_game_has(tmp_path):
    """The roster read every character at the hit points they were created with, because
    nothing ever called `roster.record`. Kesst showed 9/9 in the "who is playing" list
    while her save had her at 3 — and hit points are exactly what you choose on."""
    from play import campaign as cm
    from play import roster

    with override_settings(CAMPAIGN_DIR=tmp_path / "campaigns"):
        cm._LIVE.clear()
        c = cm.begin_with(load_pc("fixtures/pc-kesst.json"))
        c.scene.pc().hp = 3
        c.save()

        assert roster.load(c.character_id).summary()["hp"] == "3/9"


def test_a_new_character_does_not_replace_the_old_ones_campaign(tmp_path):
    from play import campaign as cm
    from play import roster

    with override_settings(CAMPAIGN_DIR=tmp_path / "campaigns"):
        cm._LIVE.clear()
        first = cm.begin_with(load_pc("fixtures/pc-kesst.json"))
        cm.begin_with(roster.from_pregen("pc-thessaly"))
        assert cm._save_path(first.character_id).exists()


def test_the_dead_cannot_be_switched_to(tmp_path):
    from play import campaign as cm
    from play import roster

    with override_settings(CAMPAIGN_DIR=tmp_path / "campaigns"):
        cm._LIVE.clear()
        c = cm.begin_with(load_pc("fixtures/pc-kesst.json"))
        pc = c.scene.pc()
        pc.hp = -50
        pc.apply_hp_state()
        roster.bury(c.character_id, pc)

        with pytest.raises(ValueError, match="is dead"):
            cm.switch_to(c.character_id)


def test_switching_to_nobody_is_refused(tmp_path):
    from play import campaign as cm

    with override_settings(CAMPAIGN_DIR=tmp_path / "campaigns"):
        cm._LIVE.clear()
        with pytest.raises(LookupError):
            cm.switch_to("nobody-at-all")


def test_the_active_campaign_survives_a_restart(tmp_path):
    """Which character you were playing is part of the save, not something the app
    forgets when it closes."""
    from play import campaign as cm
    from play import roster

    with override_settings(CAMPAIGN_DIR=tmp_path / "campaigns"):
        cm._LIVE.clear()
        cm.begin_with(load_pc("fixtures/pc-kesst.json"))
        borin = cm.begin_with(roster.from_pregen("pc-borin"))

        cm._LIVE.clear()                       # as if the server had restarted
        assert cm.active_id() == borin.character_id
        assert cm.current().scene.pc().name == "Borin Achereth"


def test_each_character_is_greeted_as_their_own_people(tmp_path):
    """The opening said "flightless, in a city whose nobility is not" for everybody —
    true of Kesst, and flatly wrong for a winged Korvu. The app shipped two more
    characters and kept telling them they could not fly."""
    from play import campaign as cm
    from play import roster

    with override_settings(CAMPAIGN_DIR=tmp_path / "campaigns"):
        cm._LIVE.clear()
        kesst = cm.begin_with(load_pc("fixtures/pc-kesst.json"))
        thessaly = cm.begin_with(roster.from_pregen("pc-thessaly"))

    # The *standing* clause, not the whole opening. The opening now also states what
    # the world is — "Winged people and the flightless beneath them" — which is true
    # for every character in it and says nothing about any one of them. Reading the
    # whole text made this pass on the world's own premise rather than on the line
    # that is actually about the character.
    def about_them(campaign):
        pc = campaign.scene.pc().name
        return next(p for p in campaign.transcript[0]["text"].split("\n\n") if pc in p)

    assert "flightless" in about_them(kesst)
    assert "winged" in about_them(thessaly)
    assert "flightless" not in about_them(thessaly)
