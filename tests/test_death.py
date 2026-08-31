"""Dying, death, and the roster that outlives it.

The bug this came from, in the player's own words: Kesst was dying at -3, "The fight is
over" printed, the player typed "now what" — and the GM narrated her dodging and
stumbling while a thug attacked her, a *second* encounter began, and "The fight is over"
printed again. Nothing anywhere asked whether the character was in a state to take a turn.
"""
from __future__ import annotations

import pytest
from django.test import override_settings

from play import downed, roster
from rules.bestiary import instantiate
from rules.dice import Dice
from rules.engine import Engine, Scene
from rules.sheet import load_pc


@pytest.fixture
def scene():
    s = Scene(location_id="5bbd0c40345f")
    s.add(load_pc("fixtures/pc-kesst.json"))
    s.add(instantiate("thug", scene=s, name="the thug"))
    return s


class FakeCampaign:
    """Just enough campaign for `downed.resolve`."""

    def __init__(self, scene, seed=3):
        self.scene = scene
        self._seed = seed

    def engine(self):
        return Engine(self.scene, Dice(self._seed))


# --- What state is the character in -------------------------------------------------

def test_the_states_are_told_apart(scene):
    pc = scene.pc()
    assert downed.state_of(pc) == "fine"

    pc.hp = 0
    pc.apply_hp_state()
    assert downed.state_of(pc) == "disabled"

    pc.hp = -2
    pc.apply_hp_state()
    assert downed.state_of(pc) == "dying"

    pc.remove_condition("dying")
    pc.add_condition("stable")
    assert downed.state_of(pc) == "stable"

    pc.hp = -99
    pc.apply_hp_state()
    assert downed.state_of(pc) == "dead"


def test_a_character_who_cannot_act_is_not_reported_fine(scene):
    """The fifth answer, and the 502 underneath it.

    `state_of` knew four conditions. Measured across the 31 shipped ones, SEVEN that
    cannot act fell through to "fine" — cowering, dazed, fascinated, helpless,
    paralyzed, petrified and stunned. `play/views.py` gates the turn on
    `state_of(pc) not in ("fine", "disabled")`, so a petrified character was handed a
    turn, the GM planned it, and `Engine.validate` then refused every op in it as a
    `legality` IntentError — which regenerates rather than repairs. The turn burned the
    retry loop and reached the player as a blank 502 page.
    """
    pc = scene.pc()
    held = ("petrified", "paralyzed", "stunned", "helpless", "dazed",
            "cowering", "fascinated")
    for key in held:
        pc.add_condition(key, source="probe")
        assert downed.state_of(pc) == "held", f"{key} was reported fit for a turn"
        assert not pc.can_act()
        pc.remove_condition(key)
    assert downed.state_of(pc) == "fine"

    # And at exactly 0 hit points, where `disabled` — a rung that HANDS OUT a turn —
    # was tested first and shadowed every one of them. Found by review: the 502 this
    # rung exists to close was still open for the whole hp == 0 case.
    for key in held:
        pc.hp = 0
        pc.apply_hp_state()
        pc.add_condition(key, source="probe")
        assert pc.has_condition("disabled")
        assert downed.state_of(pc) == "held", (
            f"disabled shadowed {key}: the turn was handed out and every op in it "
            f"would be refused as a legality error")
        pc.remove_condition(key)
        pc.remove_condition("disabled")


def test_a_hold_inside_a_fight_skips_no_time_at_all(scene):
    """Found by an adversarial review, under a green suite, and the worst thing this
    stage shipped before it was caught.

    `Scene.advance` is EXPIRY ONLY by contract — it runs no turns, fires no wards,
    drains no upkeep and never rolls the dying. Waiting a hold out with it put the
    player inside a safety bubble: measured, a paralyzed character stood among three
    thugs for four rounds and was not touched once, while the burning cloud they were
    lying in lost four rounds of its clock for free. Every stun, daze and cower the
    player suffered cost them nothing, and ghoul paralysis — whose whole danger in 1e is
    that the ghouls eat you while you are down — became a free rest.

    The turn is simply not theirs. The world takes its own, through `advance_turn`,
    which is the door that fires things.
    """
    from rules.engine import Ward

    s = scene
    pc = s.pc()
    s.initiative = [(r, 20 - i * 3) for i, r in enumerate(s.actors)]
    s.turn = 0
    s.sides = {"party": ["pc"], "them": [r for r in s.actors if r != "pc"]}
    s.wards.append(Ward(owner="pc", trigger="each_round", rounds_left=10,
                        source="a burning cloud", spec={}))
    pc.add_condition("paralyzed", source="a ghoul", rounds=4)
    before = (s.round, s.clock_minutes, s.wards[0].rounds_left)

    got = downed.resolve(FakeCampaign(s))

    assert got.state == "held" and not got.playable
    assert (s.round, s.clock_minutes, s.wards[0].rounds_left) == before, (
        "the hold skipped time inside a fight, so nobody swung and the ward's clock "
        "was spent for free")
    assert pc.has_condition("paralyzed"), (
        "the hold expired without a single round of the fight being played")


def test_an_endless_hold_is_said_plainly_and_costs_no_world_clock(scene):
    """The tempting fix was to widen the "stable" rung to `state.down`, which routes a
    petrified character into the wake-up path: `scene.advance(60)` burns an hour, the
    removal loop leaves the petrification in place, hit points are floored at 1, and the
    player is told "You come round about an hour later" — to a statue that is still a
    statue, on hit points it never lost.
    """
    pc = scene.pc()
    pc.hp = 9
    pc.add_condition("petrified", source="a basilisk")
    before = scene.clock_minutes

    got = downed.resolve(FakeCampaign(scene))

    assert got.state == "held" and not got.playable and not got.died
    assert scene.clock_minutes == before, "an hour was burned on a statue"
    assert pc.hp == 9, "hit points were floored by a recovery that never happened"
    assert pc.has_condition("petrified"), "the petrification was quietly cured"
    assert not any("come round" in line for line in got.lines)
    assert got.lines and "petrified" in got.lines[0]


def test_a_hold_with_a_clock_is_waited_out(scene):
    """The other half: paralysis from a ghoul does end, and a character who cannot act
    still has to get to the far side of it. The one ticker moves the rounds."""
    pc = scene.pc()
    pc.add_condition("paralyzed", source="a ghoul", rounds=3)

    got = downed.resolve(FakeCampaign(scene))

    assert got.playable, "the hold ran out and the character never got their turn back"
    assert pc.can_act() and not pc.has_condition("paralyzed")
    assert any("3 rounds pass" in line for line in got.lines)


def test_a_character_at_exactly_zero_may_still_act(scene):
    """Disabled is conscious. Refusing their turn would be as wrong as letting a dying
    character take one."""
    pc = scene.pc()
    pc.hp = 0
    pc.apply_hp_state()
    assert downed.resolve(FakeCampaign(scene)).playable


def test_a_disabled_character_stays_in_the_fight(scene):
    """Found in play: Kesst hit exactly 0, and the fight ended around her while she was
    still on her feet — `conscious` demanded hit points above zero, so a disabled
    character was dropped from the initiative order and counted as down.
    """
    pc = scene.pc()
    engine = Engine(scene, Dice(seed=6))
    engine.run(engine.validate([
        {"op": "begin_encounter", "params": {"sides": {"pc": ["pc"], "them": ["c1"]}}}
    ]))
    pc.hp = 0
    pc.apply_hp_state()

    assert pc.has_condition("disabled")
    assert scene.conscious("pc")
    assert scene.sides_standing() == 2
    assert "pc" in {scene.advance_turn() for _ in range(4)}


def test_the_unconscious_are_not_in_the_fight(scene):
    pc = scene.pc()
    pc.hp = -1
    pc.apply_hp_state()
    assert not scene.conscious("pc")


# --- Bleeding out -------------------------------------------------------------------

def test_the_dying_are_carried_to_a_conclusion(scene):
    """The player has no turn to take, so the rules take it. Either they stabilise or
    they die; they do not lie there for ever while the GM improvises."""
    pc = scene.pc()
    pc.hp = -2
    pc.apply_hp_state()

    out = downed.resolve(FakeCampaign(scene))
    assert out.state in ("stable", "dead")
    assert out.lines
    assert not pc.has_condition("dying")


def test_bleeding_out_is_narrated_round_by_round(scene):
    """The most frightening thing that can happen to a character should not be one line
    reporting the result."""
    pc = scene.pc()
    pc.hp = -9                       # Con 12, so there is a way to fall
    pc.apply_hp_state()
    out = downed.resolve(FakeCampaign(scene, seed=1))
    assert len(out.lines) >= 1
    if out.state == "dead":
        assert "is dead" in out.lines[-1]


def test_a_character_who_bleeds_out_is_dead_and_unplayable(scene):
    pc = scene.pc()
    pc.hp = -11                      # one point from -Con
    pc.apply_hp_state()
    out = downed.resolve(FakeCampaign(scene, seed=2))
    assert out.state == "dead" and out.died and not out.playable
    assert pc.has_condition("dead")


def test_the_stable_wake_up_and_the_fight_is_over(scene):
    """Waking with the encounter still running would put the character straight back
    into a fight that finished an hour ago."""
    pc = scene.pc()
    engine = Engine(scene, Dice(seed=6))
    engine.run(engine.validate([
        {"op": "begin_encounter", "params": {"sides": {"pc": ["pc"], "them": ["c1"]}}}
    ]))
    pc.hp = -2
    pc.apply_hp_state()
    pc.remove_condition("dying")
    pc.add_condition("stable")

    out = downed.resolve(FakeCampaign(scene))
    assert out.state == "stable" and out.playable
    assert pc.hp >= 1
    assert not scene.in_encounter
    assert downed.state_of(pc) == "fine"
    assert scene.clock_minutes >= 60


def test_the_dead_stay_dead(scene):
    pc = scene.pc()
    pc.hp = -50
    pc.apply_hp_state()
    out = downed.resolve(FakeCampaign(scene))
    assert out.died and not out.playable
    assert "is dead" in out.lines[0]


def test_the_death_notice_says_it_plainly(scene):
    """No roll left to make, and no pretending otherwise."""
    notice = downed.death_notice(scene.pc())
    assert "Kesst Vayr is dead" in notice
    assert "no roll left" in notice


# --- The roster -----------------------------------------------------------------------

def test_a_character_is_enrolled_and_comes_back(tmp_path):
    with override_settings(CAMPAIGN_DIR=tmp_path / "campaigns"):
        entry = roster.enrol(load_pc("fixtures/pc-kesst.json"), "slice")
        assert entry.status == roster.ALIVE

        back = roster.load(entry.id)
        assert back.name == "Kesst Vayr"
        assert back.actor.hp_max == 9


def test_the_dead_are_kept(tmp_path):
    """A character who died in the second session is the reason the third went the way
    it did. Deleting them throws away the only record of it."""
    with override_settings(CAMPAIGN_DIR=tmp_path / "campaigns"):
        pc = load_pc("fixtures/pc-kesst.json")
        entry = roster.enrol(pc, "slice")
        pc.hp = -20
        pc.apply_hp_state()

        roster.bury(entry.id, pc, epitaph="a club, in a guild yard, after dark")
        back = roster.load(entry.id)
        assert back.status == roster.DEAD
        assert back.died
        assert "guild yard" in back.epitaph
        assert roster.path_for(entry.id).exists()


def test_two_characters_of_the_same_name_do_not_collide(tmp_path):
    with override_settings(CAMPAIGN_DIR=tmp_path / "campaigns"):
        a = roster.enrol(load_pc("fixtures/pc-kesst.json"))
        b = roster.enrol(load_pc("fixtures/pc-kesst.json"))
        assert a.id != b.id
        assert roster.load(a.id) and roster.load(b.id)


def test_starting_again_retires_the_character_it_replaces(tmp_path):
    """Every `?new=1` used to leave another living copy on the roster — three identical
    Kessts, all alive, none being played. The dead are kept because they are a record;
    an abandoned character is not the same thing."""
    from play import campaign as cm

    with override_settings(CAMPAIGN_DIR=tmp_path / "campaigns"):
        cm._LIVE.clear()
        first = cm.current("retire-test")
        first_id = first.character_id
        assert roster.load(first_id).status == roster.ALIVE

        cm.current("retire-test", reset=True)
        assert roster.load(first_id).status == roster.RETIRED

        living = [e for e in roster.everyone() if e.status == roster.ALIVE]
        assert len(living) == 1


def test_the_roster_keeps_the_sheet_current(tmp_path):
    with override_settings(CAMPAIGN_DIR=tmp_path / "campaigns"):
        pc = load_pc("fixtures/pc-kesst.json")
        entry = roster.enrol(pc)
        pc.hp = 4
        roster.record(entry.id, pc, turns_played=7)
        back = roster.load(entry.id)
        assert back.actor.hp == 4
        assert back.turns_played == 7


# --- Somebody to play next ---------------------------------------------------------------

def test_there_is_more_than_one_character_to_choose_from(tmp_path):
    """A death needs somebody to hand the player. Guided 1e creation is not built yet,
    so these ship with the app."""
    with override_settings(CAMPAIGN_DIR=tmp_path / "campaigns"):
        choices = roster.pregens()
        assert len(choices) >= 3
        names = {c["name"] for c in choices}
        assert {"Kesst Vayr", "Borin Achereth", "Thessaly Corr"} <= names
        assert all(c["line"] and c["hp"] for c in choices)


@pytest.mark.parametrize("source,cls,hp", [
    ("pc-kesst", "Rogue", 9),
    ("pc-borin", "Fighter", 12),
    ("pc-thessaly", "Wizard", 7),
])
def test_every_shipped_character_is_a_legal_build(source, cls, hp):
    """A wrong sheet poisons every roll that follows, so these are checked the same way
    a hand-made one would be."""
    actor = roster.from_pregen(source)
    assert actor.class_data["name"] == cls
    assert actor.hp_max == hp
    assert actor.pronouns


def test_an_unknown_character_is_refused():
    with pytest.raises(FileNotFoundError):
        roster.from_pregen("pc-nobody")


def test_only_character_fixtures_can_be_loaded():
    """The source name comes off the wire; it must not be able to reach another file."""
    with pytest.raises(FileNotFoundError):
        roster.from_pregen("pangrella-campaign")
