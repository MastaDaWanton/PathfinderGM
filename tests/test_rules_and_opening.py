"""Playtest 2026-10-03, lane E: the Diplomacy DC, /gm about a word the story used, and
the opening card that never moved (docs/playtest-2026-10-03.md items 23-25;
docs/rules-and-opening-2026-10-03.md for the research).

Every case is built from a line of the owner's two saves (market-talk and items), which
are not in the repository.
"""
from __future__ import annotations

import copy
from types import SimpleNamespace

from gm import judgement
from play import gm_answers
from rules import cards, dc as dc_mod
from rules.bestiary import instantiate
from rules.dice import Dice
from rules.engine import Engine, Scene
from rules.sheet import load_pc

PANGRELLA = "fixtures/pangrella-campaign.json"
TOWN = "6953424c8a82"                       # Zhilvarnia, where the owner played
MARKET = f"{TOWN}~urban:the-market"


def _world():
    from world.loader import load_cached

    return load_cached(PANGRELLA)


# --- 23: the Diplomacy DC ------------------------------------------------------------------

# The planner's intent, verbatim from the items save's turn-log row 78.
FLIRT = {"op": "check", "actor": "pc", "target": None,
         "because": "trying to flirt and negotiate simultaneously",
         "params": {"skill": "diplomacy",
                    "circumstance": {"value": "favorable",
                                     "why": "the clerk is momentarily distracted by the "
                                            "flirtation"},
                    "dc": {"band": "average"}},
         "visibility": "player"}
FLIRT_SAID = "I smile and flirt with the clerk and offer the crate for coin."


def _counting_house(*others):
    s = Scene(location_id=TOWN)
    s.add(load_pc("fixtures/pc-kesst.json"))
    clerk = instantiate("guildhand", scene=s, name="the clerk of the counting house")
    clerk.abilities["cha"] = 14                       # the save's c12: Cha 14, +2
    s.add(clerk)
    for name in others:
        s.add(instantiate("guildhand", scene=s, name=name))
    e = Engine(s, Dice(seed=4))
    return s, e, clerk


def test_a_flirt_at_the_clerk_is_priced_by_her_attitude_not_an_average_band():
    """Measured on the items save (rows 78 and 84): an untargeted `check diplomacy` at
    `band: average` made DC 10, a favourable circumstance made it 8, and a natural 4
    (total 10) succeeded by 2. The clerk was in conversation with the player, Cha 14,
    indifferent at regard 39: the Core Rulebook's DC is 15 + 2 = 17, and the same face
    misses it by 7."""
    s, e, clerk = _counting_house("a porter")
    e.join_talk(clerk, "they spoke to you")

    plan = judgement.aim_the_sway([copy.deepcopy(FLIRT)], FLIRT_SAID, s)
    assert plan[0]["target"] == clerk.ref
    assert "dc" not in plan[0]["params"], "the band the plan named is the plan's price"
    assert "circumstance" not in plan[0]["params"]

    res = e.run(e.validate(plan))
    if res.awaiting:
        res = e.resume(4)
    o = res.outcomes[0]
    assert o.dc["value"] == 17, o.dc
    assert "indifferent 15, Cha +2" in o.dc["explain"]
    assert o.verdict == ("success" if o.rolls[0].total >= 17 else "failure")
    assert o.rolls[0].total < 17, "Kesst's +6 on a natural 4 is 10: the book says no"


def test_the_one_person_in_conversation_is_who_the_talk_is_aimed_at():
    """No name in the words ("I lean in and whisper…"), two people here, one of them in
    conversation with the player: the conversation is the subject."""
    s, e, clerk = _counting_house("a porter")
    e.join_talk(clerk, "they spoke to you")
    plan = judgement.aim_the_sway([copy.deepcopy(FLIRT)],
                                  'I lean in and whisper, "I just need it handled quietly."',
                                  s)
    assert plan[0]["target"] == clerk.ref


def test_two_people_and_neither_named_nor_talking_leaves_the_check_alone():
    """Choosing for the player is worse than asking: with nobody certain, the plan's own
    check stands as written."""
    s, e, _clerk = _counting_house("a porter")
    before = [copy.deepcopy(FLIRT)]
    after = judgement.aim_the_sway(before, "I smile at everyone in the room.", s)
    assert after[0]["target"] is None and after[0]["params"]["dc"] == {"band": "average"}


def test_a_targeted_diplomacy_with_a_dc_loses_the_dc_instead_of_a_retry():
    """`intents._check_params` refuses a targeted social check carrying a dc, and a
    refusal costs a model round trip (18-58 s a plan on the items save, item 26) to
    reach the intent this repair writes directly."""
    s, _e, clerk = _counting_house()
    raw = dict(copy.deepcopy(FLIRT), target=clerk.ref)
    plan = judgement.aim_the_sway([raw], FLIRT_SAID, s)
    assert plan[0]["target"] == clerk.ref and "dc" not in plan[0]["params"]


def test_intimidate_in_a_fight_is_demoralize_and_is_left_alone():
    s, _e, clerk = _counting_house()
    s.initiative = [("pc", 15), (clerk.ref, 10)]
    s.turn = 0
    assert s.in_encounter
    raw = {"op": "check", "actor": "pc", "params": {"skill": "intimidate",
                                                    "dc": {"band": "average"}}}
    assert judgement.aim_the_sway([raw], "I snarl at the clerk", s)[0] is raw


def test_a_circumstance_says_the_dc_moved_not_that_the_check_got_a_bonus():
    """The record read "average (DC 10); +2 circumstance: …" beside a DC of 8. "+2
    circumstance" is a bonus on the roll in the book's words; what ran was the DC lowered
    by 2 (the 3.5 SRD's option, same odds)."""
    r = dc_mod.resolve({"band": "average"}, 1,
                       {"value": "favorable", "why": "the clerk is distracted"})
    assert r.final == 8
    assert "DC lowered by 2 to 8 for a favourable circumstance" in r.explain()
    assert "+2 circumstance" not in r.explain()


# --- 24: /gm about a word the story used ---------------------------------------------------

# From the market-talk save: turn-log row 1's suggestions, and the line the player asked.
VEIL_SUGGESTIONS = ["I tell him of the men in the shadows",
                    "I explain why I am looking for the veil",
                    "I point to the empty glass and demand he speaks his mind"]


def _talk(transcript=(), suggested=(), current=()):
    s = Scene(location_id=TOWN)
    s.add(load_pc("fixtures/pc-kesst.json"))
    return SimpleNamespace(
        scene=s, transcript=list(transcript), suggestions=list(current),
        turn_log=[{"kind": "prose", "suggested": list(suggested)}] if suggested else [])


def test_the_veil_the_narrator_suggested_is_answered_from_the_story_first():
    """Measured on market-talk: the narrator's own suggestion read "I explain why I am
    looking for the veil", and "/gm what is the veil?" came back as the spell Veil's
    full entry — school, range, duration — and nothing else."""
    c = _talk(transcript=[{"who": "gm", "text": "Evening in Zhilvarnia."},
                          {"who": "player", "text": "What is going on?"}],
              suggested=VEIL_SUGGESTIONS)
    kind, text = gm_answers.answer(c, None, "what is the veil?")
    assert kind == "engine"
    lines = text.splitlines()
    assert lines[0].startswith("IN THE STORY")
    assert "I explain why I am looking for the veil" in text
    assert "Nothing in play has said what \"veil\" is yet" in text
    assert "IN THE RULES: Veil is also the name of a spell" in text
    assert "school:" not in text, "the spell's entry is offered, not answered"


def test_naming_the_catalogue_still_gets_the_rules_entry():
    c = _talk(suggested=VEIL_SUGGESTIONS)
    _kind, text = gm_answers.answer(c, None, "what is the spell veil?")
    assert text.startswith("SPELL: Veil.") and "school:" in text


def test_a_word_the_story_never_used_is_looked_up_as_before():
    c = _talk(transcript=[{"who": "gm", "text": "The market is closing."}])
    _kind, text = gm_answers.answer(c, None, "what is the veil?")
    assert text.startswith("SPELL: Veil.")


def test_the_story_quotes_what_the_narration_said_and_the_aside_is_not_the_story():
    """The /gm line itself is an aside (`views._gm_answer`) and must not count as the
    story having used the word."""
    c = _talk(transcript=[
        {"who": "gm", "text": "He lowers his voice. Nobody goes past the veil after dark."},
        {"who": "player", "text": "/gm what is the veil?", "kind": "aside"}])
    _kind, text = gm_answers.answer(c, None, "what is the veil?")
    assert "the story: “Nobody goes past the veil after dark.”" in text
    assert "That is all the story has said about it" in text
    only_aside = _talk(transcript=[{"who": "player", "text": "/gm what is the veil?",
                                    "kind": "aside"}])
    assert gm_answers.story_first(only_aside, None, "what is the veil?") is None


# --- 25: the opening card ------------------------------------------------------------------

def _bed_card():
    """The opening card exactly as the market-talk save holds it."""
    return cards.Card(
        id="opening", title="Find a bed you can pay for",
        facts=["You came in out of the weather to find a bed you can pay for.",
               "You have just come in out of the weather and not sat down yet.",
               "Somebody has just gone out the other door in a hurry, and the room is "
               "working hard at not having noticed."],
        keys=["find", "weather", "down", "gone", "door", "hurry", "room", "working",
              "hard", "having", "noticed"],
        tags=(cards.TAG_ERRAND, cards.TAG_PLAY), people=[], place=MARKET,
        origin="opening", always_on=True)


def _zhilvarnia(purse=None):
    world = _world()
    s = Scene(location_id=TOWN)
    pc = load_pc("fixtures/pc-kesst.json")
    pc.purse = dict(purse or {})                    # the save's purse: {} from turn one
    s.add(pc)
    e = Engine(s, Dice(seed=2), world=world)
    e.place_party(MARKET)
    cards.open_card(s, _bed_card())
    return s, e


def test_the_bed_card_is_keyed_on_bed():
    """The save's card had eleven keys and not *bed*: `keys_from` drops three-letter
    words, so the one word the errand is about could never key it."""
    card = _bed_card()
    assert cards.need_of(card) == cards.NEED_LODGING
    assert "bed" in cards._keys_of(card)
    assert cards._hits(card, "She says there is a bed going at the back.") >= 1


def test_the_watchers_offer_of_work_is_about_a_bed_the_player_cannot_pay_for():
    """Market-talk, turn-log row 23: "…as he considers the offer of work" was refused as
    "the fact is not about this card" while the purse was empty and the errand read "a
    bed you can pay for". With coin for a bed in hand it is not about the bed."""
    fact = ("The man's hostility has been replaced by a weary curiosity as he considers "
            "the offer of work.")
    s, _e = _zhilvarnia()
    assert cards.about(cards.find(s, "opening"), fact, s)
    rich, _e = _zhilvarnia({"gp": 5})
    assert not cards.about(cards.find(rich, "opening"), fact, rich)


def test_the_way_to_a_bed_is_put_on_the_card_from_the_towns_own_places():
    """Nothing put an inn within reach: three people stood in Zhilvarnia's tavern and
    the card never said so."""
    s, e = _zhilvarnia()
    assert cards.ground_the_errand(s, e.places()) == "Beds are let at the tavern."
    assert cards.ground_the_errand(s, e.places()) == "", "once"
    assert "Beds are let at the tavern." in cards.find(s, "opening").facts


def test_the_card_moves_once_per_step_and_talk_alone_never_settles_it():
    """Market-talk: five approaches (overheard, asked ×4) and clock 0/4 at the end. The
    player's own lines move it now — once each, however often they are said — and the
    clock stops one short until a bed is actually had."""
    s, e = _zhilvarnia()
    asked = cards.errand_progress(s, e.places(),
                                  player_text='"Is there anything I can do for some coin?"')
    assert "With nothing in your purse, you have asked after work to pay for a bed." in asked
    again = cards.errand_progress(s, e.places(),
                                  player_text='"Is there anything I can do to earn some coin?"')
    assert again == []
    assert cards.errand_progress(s, e.places(), player_text="I ask him about the docks.") == []
    cards.errand_progress(s, e.places(), player_text="Where can I find a bed for the night?")
    card = cards.find(s, "opening")
    assert (card.clock, card.stage) == (2, "moving")
    for i in range(6):
        cards.touch(s, "opening", f"talk {i}", tick=True)
    card = cards.find(s, "opening")
    assert card.live and card.clock == card.clock_max - 1


def test_a_night_slept_at_the_tavern_settles_the_bed_card():
    s, e = _zhilvarnia({"gp": 1})
    tavern = cards.where_met(cards.NEED_LODGING, e.places(), s.at)
    e.place_party(tavern.id)
    arrived = cards.errand_progress(s, e.places(), player_text="I go in.")
    assert "You have found the tavern, where beds are let." in arrived
    night = SimpleNamespace(op="rest", status="resolved",
                            tell="Kesst Vayr rests for 8 hours.")
    cards.errand_progress(s, e.places(), outcomes=[night])
    assert cards.find(s, "opening").stage == "resolved"


def test_an_errand_with_no_need_is_untouched():
    s = Scene(location_id=TOWN)
    s.add(load_pc("fixtures/pc-kesst.json"))
    cards.open_card(s, cards.Card(id="opening", title="A day's paid work",
                                  facts=["You came for a day's paid work."],
                                  tags=(cards.TAG_ERRAND,)))
    assert cards.errand_progress(s, (), player_text="any beds here?") == []
