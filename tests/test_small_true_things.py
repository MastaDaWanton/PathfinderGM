"""Group 7 of the 2026-09-19 fix pass: the small true things.

Three reported items, all visible in the first ten minutes of play
(docs/playtest-2026-09-18.md items 31, 32 and the price half of 24).

  * **"Stranger on the stairs refuses to give his name."** A regression from group 3,
    built the day before. Every promoted person draws a true name from the world's own
    pools; then the narrator began using those names before anybody asked ("Soren's eyes
    narrow"), so the name was removed from the brief entirely — and nothing put it back
    on the turn the player asked for it. `settle_introductions` only *replaces* a name
    the model has already offered, so a model with no name to give did the only thing
    left to it and refused. Measured on the 2026-09-19 screen: "the stranger beside you
    stands", "the stranger says", several scenes in.

  * **"Drenn Ironvale and the merchant are in scene without having been described."**
    Four writers put people into a scene — the opening companion, the keeper behind a
    counter, a scheme's cast, the `spawn` op — and `narration.faceless` ran over exactly
    one thing: the phrases `note_cast` booked from *this turn's* prose. There was no
    `described` flag on `Actor` at all, so everyone else could be referred to for the
    rest of the campaign with nothing describing them. Keepers were worse off: their
    `world_entity_id` is the synthetic `keeper:<place>`, so `names.resident_appearance`
    found no resident and returned "" — no appearance, no `Looks` clause in the brief,
    and nothing for a check to enforce even if one ran.

  * **Five class kits were built from weapons the shop could not sell.** `club`,
    `quarterstaff` and `sling` carried `cost_gp: null` because the workbook's cost cell
    was empty where the rulebook prints a dash, and the outfitter skipped anything
    costing nothing (`outfit_views.catalogue`). Three of the eleven kits hand over a
    quarterstaff and a club; none of them could be bought back.
"""
from __future__ import annotations

import inspect
import json
from pathlib import Path

import pytest

from gm import judgement, narration, prompts
from play import outfit_views
from rules import attitude, keepers, weapons as weapons_mod
from rules.bestiary import instantiate
from rules.dice import Dice
from rules.engine import Engine, Scene
from rules.sheet import from_dict, load_pc, to_dict
from world import loader

WORLD = loader.load_cached("fixtures/pangrella-campaign.json")
TOWN = "5bbd0c40345f"
MARKET = f"{TOWN}~urban:the-market"


@pytest.fixture
def step():
    """A scene with one nameless stranger in it, as the play-test had."""
    scene = Scene(location_id=TOWN)
    scene.add(load_pc("fixtures/pc-kesst.json"))
    who = instantiate("guildhand", scene=scene, name="the stranger")
    who.true_name = "Soren Valdis"
    scene.add(who)
    return scene, who


# --- 24, the price half: free is a price -----------------------------------------------------

def test_the_four_free_weapons_carry_a_price_and_the_unknown_ones_still_do_not():
    """Measured 2026-09-19: ten weapons had `cost_gp: null`. Four of them are free in the
    book — club, quarterstaff, sling and wooden stake all print "—" in the Cost column
    (confirmed against d20pfsrd's weapon tables) — and six simply were not imported with
    a price. One value for two different facts is why the shop refused a club."""
    all_of_them = weapons_mod.all_weapons()
    for key in ("club", "quarterstaff", "sling", "wooden-stake"):
        assert all_of_them[key].get("cost_gp") == 0.0, key
    # Not a blanket zeroing: unknown stays unknown, and unknown stays unsellable.
    assert all_of_them["stingchuck"].get("cost_gp") is None
    assert all_of_them["throwing-shield"].get("cost_gp") is None


def test_the_builder_tells_free_from_unpriced_so_a_reimport_keeps_the_fact():
    """The committed index is the build output, so the rule lives in the builder too —
    otherwise the next run of `tools/build_weapons.py` silently undoes this."""
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from tools.build_weapons import FREE_BY_NAME, parse_cost

    assert parse_cost("") is None, "no price given is not the same as free"
    assert parse_cost("", free=True) == 0.0
    assert parse_cost("35 gp") == 35.0
    assert {"club", "quarterstaff", "sling", "wooden stake"} == FREE_BY_NAME


def test_the_outfitter_stocks_a_free_weapon_and_will_hand_one_over():
    """Three of the eleven class kits hand out a quarterstaff and one a club; the shop
    stocked neither, so a character who lost one could not replace it."""
    stock = outfit_views.catalogue()["weapons"]
    by_key = {w["key"]: w for w in stock}
    assert "club" in by_key and by_key["club"]["cost_gp"] == 0.0
    assert "quarterstaff" in by_key
    assert outfit_views._price("weapon", "club")[0] == 0.0
    assert outfit_views._price("weapon", "stingchuck") is None, "unpriced is still not for sale"
    html = Path("play/templates/play/outfit.html").read_text(encoding="utf-8")
    assert '"free"' in html, "a 0 gp row reads 'free', not '0 gp'"


# --- 31: the name, on the turn it is asked for ------------------------------------------------

def test_the_name_is_handed_over_only_on_the_turn_it_is_asked_for(step):
    scene, who = step
    assert judgement.names_asked_for(scene, "I ask the stranger his name") == {
        who.ref: "Soren Valdis"}
    assert judgement.names_asked_for(scene, "who are you?") == {who.ref: "Soren Valdis"}
    assert judgement.names_asked_for(scene, "I sit down beside him") == {}
    assert judgement.names_asked_for(scene, "") == {}


def test_only_the_person_actually_asked_answers(step):
    """Measured live 2026-09-19 against a copy of the `masta` save: "I turn to the woman in
    the corner and ask her what her name is" matched BOTH the woman in the corner and the
    woman, so two names were offered and the beat ended with a second stranger
    volunteering hers to nobody — '"Kael Throk," the woman says.' appended by the backstop.
    The best match answers; a tie answers not at all."""
    scene, corner = step
    corner.name = "woman in the corner"
    other = instantiate("guildhand", scene=scene, name="woman")
    other.true_name = "Kael Throk"
    scene.add(other)
    asked = judgement.names_asked_for(
        scene, "I turn to the woman in the corner and ask her what her name is")
    assert asked == {corner.ref: "Soren Valdis"}, "two words shared beats one"
    # Two people who match equally well: nobody answers, because choosing would be
    # choosing for the player.
    other.name = "woman in the corner"
    assert judgement.names_asked_for(scene, "I ask the woman in the corner her name") == {}


def test_whether_he_tells_you_is_his_attitude_and_not_the_models_whim(step):
    """The player's own ruling was that refusing is fine. What was wrong was that it
    happened for no reason and nothing could change it. The Core Rulebook's attitude
    track answers instead: indifferent is the default and tells you; unfriendly and
    hostile refuse, and Diplomacy is the documented way through."""
    scene, who = step
    assert attitude.of(who) == "indifferent"
    assert attitude.tells_their_name(who) is True
    for mood in ("friendly", "helpful"):
        assert attitude.tells_their_name(_feeling(who, mood)) is True
    for mood in ("unfriendly", "hostile"):
        assert attitude.tells_their_name(_feeling(who, mood)) is False
        assert judgement.names_asked_for(scene, "what is your name?") == {who.ref: ""}
    _feeling(who, "indifferent")
    assert judgement.names_asked_for(scene, "what is your name?") == {who.ref: "Soren Valdis"}


def _feeling(actor, mood: str):
    """Put a creature on the track through the engine's one applicator, never by hand —
    `Engine._set_attitude` clears the family first, and a charm laid over an old grudge
    left both standing when anything else wrote the tag."""
    scene = Scene(location_id=TOWN)
    Engine(scene, Dice(seed=1))._set_attitude(actor, mood, None, "the test")
    return actor


def test_the_true_name_is_in_the_brief_only_when_it_was_asked_for(step):
    """Both halves at once, because they pull in opposite directions and the fix for one
    is what broke the other. Measured twice on 2026-09-18: shown the name, the narrator
    used it before anybody asked. Measured 2026-09-19: not shown it, the narrator
    refused to give it at all."""
    scene, who = step
    quiet = prompts.scene_brief(WORLD, scene, WORLD.get(TOWN), [])
    assert "Soren Valdis" not in quiet, "the name is still not shown on an ordinary turn"
    asked = prompts.scene_brief(WORLD, scene, WORLD.get(TOWN), [],
                                names_for={who.ref: "Soren Valdis"})
    assert "Soren Valdis" in asked
    assert "ASKED HIS NAME THIS TURN" in asked
    refused = prompts.scene_brief(WORLD, scene, WORLD.get(TOWN), [],
                                  names_for={who.ref: ""})
    assert "Soren Valdis" not in refused
    assert "he will not give it" in refused


def test_the_panel_takes_the_name_from_the_person_who_was_asked(step):
    """Measured live 2026-09-19, run 2: asked for her name, the woman in the corner said
    "you may call me Gorvothor" — and the panel kept "woman in the corner". Every branch
    of the old order declined: `introductions` read the speaker's head word as "low" (out
    of "a low, resonant grind"), her true name is two words so the equality missed the
    partial, and both women present answered to "woman". The ref was known all along."""
    scene, corner = step
    corner.name = "woman in the corner"
    corner.true_name = "Gorvothor Kragnir"
    other = instantiate("guildhand", scene=scene, name="woman")
    other.true_name = "Kael Throk"
    scene.add(other)
    beat = ("'Names are heavy things to carry in a place like this,' she says, her voice a "
            "low, resonant grind. 'But if you must have one, you may call me Gorvothor.'")
    renamed = judgement.apply_introductions(
        scene, beat, "I turn to the woman in the corner and ask her what her name is")
    assert renamed == [(corner.ref, "Gorvothor")]
    assert corner.name == "Gorvothor"
    assert other.name == "woman", "the other woman is untouched"


def test_a_beat_that_still_gives_no_name_gets_the_engines_own_line():
    """The deterministic backstop: 46% of everything the reviewer caught used to ship
    anyway, because the rewrite losing was the end of the road."""
    beat = "The stranger shifts on the step and says nothing you can use."
    out, told = narration.give_the_name(beat, [("the stranger", "Soren Valdis")])
    assert told == ["Soren Valdis"]
    assert out.endswith('"Soren Valdis," the stranger says.')
    # A name the model gave itself is left alone: its own sentence is better than ours.
    already = 'He meets your eye. "Soren Valdis," he says, and looks away.'
    assert narration.give_the_name(already, [("the stranger", "Soren Valdis")]) == (already, [])
    # And it lands before the hand-back, not after the question.
    asked = "The stranger shifts on the step. What do you do?"
    out, _ = narration.give_the_name(asked, [("the stranger", "Soren Valdis")])
    assert out.endswith("What do you do?")
    assert '"Soren Valdis," the stranger says.' in out
    assert narration.give_the_name(beat, [("the stranger", "")]) == (beat, [])


def test_the_engines_own_line_is_read_back_as_an_answer(step):
    """Measured live 2026-09-19, run 3: the model refused, the backstop appended
    '"Gorvothor Kragnir," the woman in the corner says.' — and the panel still kept the
    descriptor, because `_BARE_NAME_ANSWER` read a one-word descriptor only ("the woman
    says") and gave up on "the woman in the corner says". The engine's own sentence has to
    be legible to the engine."""
    scene, who = step
    who.name = "woman in the corner"
    who.true_name = "Gorvothor Kragnir"
    beat, told = narration.give_the_name(
        "She weighs your voice and says nothing you can use. What do you do?",
        [("woman in the corner", "Gorvothor Kragnir")])
    assert told == ["Gorvothor Kragnir"]
    assert narration.introductions(beat, asked_for_name=True) == [
        ("woman", "Gorvothor Kragnir")]
    assert judgement.apply_introductions(scene, beat, "I ask the woman in the corner her name") \
        == [(who.ref, "Gorvothor Kragnir")]


def test_the_turn_path_asks_for_the_name_and_grooms_the_answer():
    from gm import agent
    from play import views

    assert "names_for=judgement.names_asked_for" in inspect.getsource(views._finish)
    src = inspect.getsource(agent.GMAgent._groom)
    assert "narration_mod.give_the_name(text, offers)" in src


# --- 32: nobody stands in a scene undescribed -------------------------------------------------

def test_the_actor_remembers_whether_anybody_ever_described_them():
    pc = load_pc("fixtures/pc-kesst.json")
    assert pc.described is False
    pc.described = True
    assert from_dict(to_dict(pc), ref="pc").described is True, "and it survives a save"


def test_a_person_the_beat_used_without_describing_is_owed_a_face(step):
    """The condition that was meant all along. `faceless` only ever ran over the phrases
    booked from this turn's prose, so somebody put in the scene on an earlier turn — a
    keeper, a companion, a scheme's cast — was never checked again."""
    scene, who = step
    owed = judgement.settle_descriptions(scene, "The stranger shifts on the step and says "
                                                "nothing.")
    assert owed == [who.ref]
    assert who.described is False
    # A beat that does describe them settles it, once and for good.
    assert judgement.settle_descriptions(
        scene, "The stranger is a gaunt man in a grey cloak, his face lined.") == []
    assert who.described is True
    assert judgement.settle_descriptions(scene, "The stranger shifts again.") == [], \
        "asked once, never again"


def test_somebody_the_player_addressed_is_owed_one_even_if_the_beat_ignored_them(step):
    scene, who = step
    owed = judgement.settle_descriptions(scene, "The market is loud and the rain holds off.",
                                         "I ask the stranger what he wants")
    assert owed == [who.ref]


def test_nobody_in_the_scene_is_owed_a_face_for_a_beat_they_are_not_in(step):
    scene, _ = step
    assert judgement.settle_descriptions(scene, "Rain beads on the shutters.") == []


def test_the_keeper_behind_the_counter_has_a_face_and_owns_their_name():
    """Drenn Ironvale's path. `keepers.name_for` composes a world-shaped name and stamps
    the synthetic `keeper:<place>` id, so `names.resident_appearance` looked up a
    resident who does not exist and returned "" — the keeper had no appearance at all,
    which is why nothing described them and why nothing could."""
    scene = Scene(location_id=TOWN)
    scene.add(load_pc("fixtures/pc-kesst.json"))
    engine = Engine(scene, Dice(seed=3), world=WORLD)
    engine.place_party(MARKET)
    who = keepers.keeper_in(scene, MARKET)
    assert who is not None
    assert who.appearance, "the keeper has a body line from their own people"
    assert who.true_name == who.name, "their name is theirs; they are not keeping it back"
    brief = prompts.scene_brief(WORLD, scene, WORLD.get(TOWN), [])
    assert "Looks (fact" in brief


def test_the_turn_path_settles_descriptions_over_everybody_present():
    from play import views

    src = inspect.getsource(views._finish)
    assert "judgement.settle_descriptions(c.scene, text, player_input)" in src
    assert "nobody stands here undescribed" in src


def test_one_appended_face_a_beat_and_never_the_same_sentence_twice():
    """Measured live 2026-09-19, run 4: the beat ended with "The woman: Orc: Powerfully
    built, prominent lower tusks…" and then "The girl with the cup: Orc: Powerfully built,
    prominent lower tusks…" — word for word the same, because the export gives the Orc
    people exactly ONE body sentence and `appearance_for` has nothing to vary. The backstop
    is a floor, not an appendix."""
    from play import views

    src = inspect.getsource(views._finish)
    # The guard, not the whole line: 2026-09-22 added `not line or` in front of it when
    # the face became a sentence rather than a label, and a test that pins an exact line
    # fails on a change that keeps its rule.
    assert "who.appearance in text" in src, "never the same sentence twice in one beat"
    assert src.count("face from the world's own body line") == 1
    body = src[src.index("nobody stands here undescribed") - 900:]
    assert "break" in body[:1400], "one appended line a beat"
