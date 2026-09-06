"""Situation cards: the facts of a situation, kept by the engine and shown to the
model while the situation is in play.

"as i seal the jar it seem to lose the initial situation" — the player, 2026-09-06.
docs/situation-cards.md carries the research; these pin the mechanism.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from gm import prompts
from rules import cards, states
from rules.bestiary import instantiate
from rules.engine import Scene
from rules.sheet import load_pc


def _scene():
    s = Scene(location_id="5bbd0c40345f")
    s.add(load_pc("fixtures/pc-kesst.json"))
    woman = s.add(instantiate("guildhand", scene=s, name="the woman at the bread stall"))
    return s, woman


def test_keys_are_written_by_the_engine_from_the_cards_own_words():
    """A lorebook asks its author to type triggers; here they come from the card, so
    "seal the jar" hits the card about the jar without anybody typing 'jar'."""
    keys = cards.keys_from("The woman's supplies", "You promised to seal the jar for her.")
    assert "supplies" in keys and "seal" in keys and "jar" not in keys   # three letters
    assert "woman" in keys and "promised" in keys
    assert "the" not in keys and "her" not in keys


def test_the_card_the_player_is_standing_in_is_always_in_front_of_the_model():
    from play import opening

    s, woman = _scene()
    here = opening.SITUATIONS[0]
    card = cards.open_card(s, cards.from_opening(here, s.at, woman.ref, "Kesst"), turn=1)
    assert card.is_("situation.errand") and card.always_on and card.origin == "opening"
    shown = cards.active(s, ["Nothing about anything."], turn=1)
    assert [c.id for c in shown] == ["opening"]
    text = cards.brief(s, [], turn=1)
    assert "SITUATIONS" in text and "the woman at the bread stall" in text
    assert here.errand in text


def test_a_card_is_shown_when_its_keys_appear_in_the_last_beats_and_not_otherwise():
    s, woman = _scene()
    jar = cards.open_card(s, cards.Card(
        id="jar", title="The sealed jar for the woman", facts=["She asked you to seal a jar."],
        tags=(cards.TAG_PLAY,), people=[woman.ref], origin="author:test"), turn=1)
    assert "seal" in jar.keys and "sealed" in jar.keys
    assert cards.active(s, ["You walk down the lane. The rain starts."], turn=2) == []
    assert [c.id for c in cards.active(s, ["I seal it with wax."], turn=2)] == ["jar"]
    # The scan window is the last three beats: a key four beats back is forgotten.
    old = ["I seal it.", "a", "b", "c"]
    assert cards.active(s, old, turn=2) == []


def test_a_tell_naming_the_cards_person_lands_on_the_card_and_ticks_the_clock():
    """Severed tells: the engine's own sentence is the fact, and the model writes
    none. A full clock resolves the card."""
    s, woman = _scene()
    cards.open_card(s, cards.Card(id="jar", title="The woman's jar", people=[woman.ref],
                                  clock_max=2, origin="author:test"), turn=1)

    @dataclass
    class Out:
        tell: str = ""
        effects: list = field(default_factory=list)

    touched = cards.touch_from_outcomes(
        s, [Out("Kesst hands the woman at the bread stall a sealed jar.")], turn=2)
    assert touched == ["jar"]
    jar = cards.find(s, "jar")
    assert jar.stage == "moving" and jar.clock == 1
    assert "sealed jar" in jar.facts[-1]
    # A tell about the weather is not about her.
    assert cards.touch_from_outcomes(s, [Out("The rain gets heavier over the roofs.")],
                                     turn=3) == []
    cards.touch_from_outcomes(s, [Out("The woman at the bread stall pays Kesst.")], turn=4)
    assert cards.find(s, "jar").stage == "resolved"
    # Settled cards linger for a few turns, then leave the brief.
    assert [c.id for c in cards.active(s, [], turn=5)] == ["jar"]
    assert cards.active(s, [], turn=9) == []


def test_a_card_grants_through_the_one_applicator_and_takes_it_back():
    """Second law: a state a card puts on a person is an ActiveEffect with source
    card:<id>; resolving the card removes it and the tag evaporates."""
    s, woman = _scene()
    cards.open_card(s, cards.Card(
        id="owed", title="Hospitality owed", people=[woman.ref], origin="author:test",
        grants=[{"to": woman.ref, "tags": ["situation.owed.hospitality"]}]), turn=1)
    assert woman.has_state("situation.owed")
    assert any(e.source == "card:owed" for e in woman.effects)
    cards.resolve(s, "owed", turn=2)
    assert not woman.has_state("situation")


def test_secret_cards_reach_the_plan_and_never_the_prose():
    s, _ = _scene()
    cards.open_card(s, cards.Card(id="hook-x", title="Somebody is selling the salt",
                                  facts=["The elder skims the levy."], tags=(cards.TAG_HOOK,),
                                  secret=True, always_on=True, origin="world:x"), turn=1)
    assert cards.brief(s, [], turn=1) == ""
    private = cards.brief(s, [], turn=1, secret=True)
    assert "selling the salt" in private and "the GM's alone" in private


def test_the_world_ships_cards_its_author_wrote_and_the_ones_every_export_implies():
    """The contract in docs/campaign-format.md, and the derived cards: the starting
    settlement's strain from its own facts, each unwritten hook as a secret card."""
    @dataclass
    class Town:
        id: str
        name: str
        facts: dict

        def fact(self, k, d=""):
            return self.facts.get(k, d)

    class World:
        entities = {"t1": Town("t1", "Averthorn", {"Tension": "the reeve's tithe is two years unpaid",
                                                 "Cause": "a bad harvest"})}
        unwritten = [{"name": "Kaelvyr", "why": "engineer who found the hidden salt vein"}]
        play = {"cards": [{"id": "levy", "title": "The salt levy is due",
                           "facts": ["Nobody can pay it."], "people": ["c9"], "place": "t1~urban:the-market",
                           "clock": 3, "tags": ["debt"]}]}

    got = cards.from_world(World(), "t1~urban:the-market")
    by = {c.id: c for c in got}
    assert by["levy"].origin == "world:levy" and by["levy"].clock_max == 3
    assert by["levy"].is_("situation.world") and "debt" in by["levy"].tags
    assert by["strain-t1"].is_("situation.strain")
    assert by["strain-t1"].facts == ["The reeve's tithe is two years unpaid.", "A bad harvest."]
    assert by["hook-kaelvyr"].secret and by["hook-kaelvyr"].is_("situation.hook")


def test_cards_ride_the_brief_and_survive_a_save(tmp_path):
    from django.test import override_settings
    from play import campaign as cm

    with override_settings(CAMPAIGN_DIR=tmp_path / "campaigns"):
        cm._LIVE.clear()
        c = cm.current("cards-test", reset=True)
        opened = cards.load(c.scene)
        assert any(k.id == "opening" for k in opened)
        assert any(k.is_("situation.strain") for k in opened), [k.id for k in opened]
        brief = prompts.scene_brief(c.world, c.scene, c.location, recent=[], turn=1)
        assert "SITUATIONS" in brief and "just begun" in brief
        c.save()
        cm._LIVE.clear()
        again = cm.current("cards-test")
        assert [k.id for k in cards.load(again.scene)] == [k.id for k in opened]


def test_card_tags_are_the_one_vocabulary():
    c = cards.Card(id="x", title="x", tags=(cards.TAG_ERRAND,))
    assert c.is_("situation") and c.is_("situation.errand") and not c.is_("situation.err")
    assert states.matches(cards.TAG_STRAIN, "situation")
