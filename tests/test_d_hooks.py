"""Lane D, items 9.2 and 12 of docs/playtest-2026-09-28.md: the pull yields to the player's
search; a hook is ingredients and an approach the engine picks, never a cold pitch.

What was measured on the Bobby playtest (turn 4, tests/replays/bobby-2026-09-28):

  * "I head to the market and look for the girl that the watchman described to me" — the
    pull ("Find Drenn Ironvale's lost Power leaf") scored the card "present" and told the
    narrator "they approach the player and say the first word"; Drenn walked up and the
    search was dropped. The reading's `seek` was never consulted.
  * Drenn's first words to the player, his own former pupil by Bobby's background: "You!
    You have the look of someone who can navigate the nuances of a search … I am Drenn
    Ironvale … do you have any idea where such a thing might be hidden?" — a stranger's
    sizing-up, a self-introduction, and the quest's own answer asked of the player. The
    reward never reached the narrator.

Every scene test runs on the three worlds.
"""
from __future__ import annotations

import json
import re

import pytest

import replays
from gm import interpret
from gm.checks import BeatContext
from rules import cards, hooks, population, schemes
from rules.bestiary import instantiate
from rules.dice import Dice
from rules.engine import Engine, Scene
from rules.sheet import load_pc

WORK_HOUR = 10 * 60
DAY_TWO = 24 * 60 + 9 * 60


def _market(world, clock=WORK_HOUR):
    row = (world.play.get("settlements") or [])[0]
    s = Scene(location_id=row["id"])
    s.add(load_pc("fixtures/pc-kesst.json"))
    s.clock_minutes = clock
    e = Engine(s, Dice(seed=5), world=world)
    market = schemes._place_for(e, "market", {})
    e.place_party(market["id"])
    return s, e, market


def _giver(s, name="Tavi Holm", entity=None):
    g = instantiate("guildhand", scene=s, name=name, world_entity_id=entity)
    s.add(g)
    return g


def _quest(s, giver, turn=1):
    card = cards.open_quest(
        s, title=f"Find {giver.name}'s lost net", objectives=["Search the reeds for the net"],
        giver=giver.ref, reward="a free crossing until the thaw", people=[giver.ref],
        place=str(s.at), origin="author:test", turn=turn)
    return card


def _pull(s, text="", turn=4, reading=None):
    if reading is not None:
        interpret.remember(text, reading)
    return cards.thread_to_pull(s, recent=["The market is loud."], player_text=text,
                                turn=turn)


SEEK = "I head to the market and look for the girl that the watchman described to me"
SEEK_READING = {"question": False, "claims": [], "actions": [
    {"act": "go", "place": "the market"},
    {"act": "seek", "target": "the girl that the watchman described to me"}]}


# --- 9.2: the pull yields -----------------------------------------------------------------

def test_the_pull_yields_to_the_players_search(worlds):
    """Beat 8: the giver present, the reading seeking somebody else. The approach is
    `waits`, `yielded`, and the matter is not put in front of the model at all."""
    s, e, _m = _market(worlds)
    g = _giver(s)
    card = _quest(s, g)
    pull = _pull(s, SEEK, reading=SEEK_READING)
    assert pull["approach"] == "waits" and pull["yielded"] is True
    assert card.title not in pull["text"] and "approach the player" in pull["text"]
    assert "do not approach the player" in pull["text"]
    assert not pull["urgent"]


def test_without_a_search_the_same_stranger_is_overheard(worlds):
    s, e, _m = _market(worlds)
    g = _giver(s)
    _quest(s, g)
    pull = _pull(s, "I look around the stalls.", reading={
        "question": False, "claims": [], "actions": [{"act": "look", "object": "the stalls"}]})
    assert pull["approach"] == "overheard" and pull["yielded"] is False
    assert "does not approach the player" in pull["text"]


def test_the_player_turning_to_the_giver_is_asked_and_hears_the_offer(worlds):
    s, e, _m = _market(worlds)
    g = _giver(s)
    _quest(s, g)
    said = f"I ask {g.name} what is wrong."
    pull = _pull(s, said, reading={"question": False, "claims": [], "actions": [
        {"act": "talk", "target": g.name, "says": "what is wrong"}]})
    assert pull["approach"] == "asked"
    assert "a free crossing until the thaw" in pull["text"], "the offer reaches the narrator"
    assert pull["offer"] == "a free crossing until the thaw"


# --- 12: no cold approach, ingredients, the tie -------------------------------------------

@pytest.mark.parametrize("state", [hooks.PRESENT, hooks.ELSEWHERE, hooks.BUSY])
def test_no_cold_approach_by_a_stranger(state):
    """"You! You have the look of…": over every state, a stranger never greets the player
    and no approach tells anybody to walk up and speak first."""
    card = cards.Card(id="q", title="t", kind="quest", giver="c9")
    for turn in range(0, 60, 13):
        how = hooks.approach(hooks.STRANGER, state, card, turn=turn)
        assert how not in ("greets",), (state, how)
        card.approaches.append({"turn": turn, "approach": how})
    for how in hooks.APPROACHES:
        text = hooks.render({"giver": {"name": "Tavi", "ref": "c9"}, "hook": True,
                             "to_player": {"relationship": "stranger", "tie": ""},
                             "offer": "x", "motive": "", "doing": "", "withholds": ""},
                            how, head="HEAD")
        assert "say the first word" not in text


def test_the_hook_carries_its_ingredients_and_never_the_secret(worlds):
    """The lost-thing scheme on day two: the reward is in the text when the giver is
    asked; the secret card's distinctive words never are, under any approach; the
    withholding shows only when the giver is asked."""
    s, e, market = _market(worlds, clock=DAY_TWO)
    doc = schemes.shipped()["the-lost-thing"]
    inst = schemes.open_scheme(e, doc, turn=1)
    giver = s.people[inst["slots"]["giver"]["ref"]]
    rival = s.people[inst["slots"]["rival"]["ref"]]
    truth = next(c for c in cards.load(s) if c.secret)
    quest = next(c for c in cards.load(s) if c.kind == "quest")
    secret_words = {rival.name.lower()} | {w.lower() for w in rival.name.split()}
    texts = {}
    for how, said, reading in (
            ("asked", f"I ask {giver.name} what is wrong", {"actions": [
                {"act": "talk", "target": giver.name, "says": "what is wrong"}]}),
            ("overheard", "I look around", {"actions": [{"act": "look"}]}),
            ("waits", SEEK, SEEK_READING)):
        quest.approaches = []
        cards._store(s, quest)
        reading = {"question": False, "claims": [], **reading}
        pull = _pull(s, said, reading=reading, turn=40)
        assert pull["approach"] in (how, "overheard" if how == "overheard" else how), pull
        texts[pull["approach"]] = pull
        low = pull["text"].lower()
        assert not any(w in low for w in secret_words), (how, pull["text"])
        assert not any(f.lower()[:30] in low for f in truth.facts)
        assert not re.search(r"\d", pull["text"])
    asked = texts["asked"]
    assert quest.reward and quest.reward in asked["text"]
    assert asked["withholds"] and "looks away" in asked["text"]
    assert "looks away" not in texts["overheard"]["text"]
    assert texts["overheard"]["withholds"] == ""
    assert asked["giver"]["ref"] == giver.ref and asked["to_player"]["relationship"]


def test_a_tied_giver_greets_by_the_tie(worlds):
    """Drenn greeted his own former pupil as a stranger. A giver the PC's background
    names (scene.acquainted, Lane C's record) greets them, with the tie's own sentence."""
    s, e, _m = _market(worlds)
    g = _giver(s, name="Wenna Stoat", entity="ent-wenna")
    s.acquainted = ["ent-wenna"]
    s.pc().background_ties = ["You learned the knots from Wenna Stoat, who still asks after you."]
    _quest(s, g)
    assert hooks.relationship(s, g) == hooks.TIED
    pull = _pull(s, "I look around.", reading={"question": False, "claims": [],
                                                 "actions": [{"act": "look"}]})
    assert pull["approach"] == "greets"
    assert "You learned the knots from Wenna Stoat" in pull["text"]
    assert "never as a stranger" in pull["text"]
    assert pull["to_player"] == {"relationship": "tied",
                                 "tie": "You learned the knots from Wenna Stoat, who still "
                                        "asks after you."}


def test_a_tied_giver_through_lane_cs_door(tmp_path):
    """The same, through a real campaign's background binding: waits for Lane C, which
    writes `scene.acquainted` for every person a tie names (fix-interfaces §2.4)."""
    from django.test import override_settings

    from play import campaign as cm

    with override_settings(CAMPAIGN_DIR=str(tmp_path / "campaigns")):
        c = cm.new_campaign("d-tied", seed=3)
    if not getattr(c.scene, "acquainted", None):
        pytest.skip("Lane C has not merged: nothing writes scene.acquainted yet")
    entity = c.scene.acquainted[0]
    g = instantiate("guildhand", scene=c.scene, name="Tied One", world_entity_id=entity)
    c.scene.add(g)
    assert hooks.relationship(c.scene, g) == hooks.TIED


def test_an_approach_that_reaches_rests_and_then_changes(worlds):
    """The first sixty-turn run pulled one card eight times running; a reaching approach
    shows once per REST_TURNS, and the next is one not yet used."""
    s, e, _m = _market(worlds)
    g = _giver(s)
    card = _quest(s, g)
    look = {"question": False, "claims": [], "actions": [{"act": "look"}]}
    first = _pull(s, "I look around.", reading=look, turn=4)
    assert first["approach"] == "overheard"
    again = _pull(s, "I look around.", reading=look, turn=6)
    assert again["approach"] == "waits"
    later = _pull(s, "I look around.", reading=look, turn=4 + cards.REST_TURNS + 1)
    assert later["approach"] == "go_between"
    kept = cards.find(s, card.id).as_dict()["approaches"]
    assert [a["approach"] for a in kept] == ["overheard", "go_between"]


def test_a_card_with_no_approach_round_trips_byte_identically():
    card = cards.Card(id="q", title="t")
    assert "approaches" not in card.as_dict()
    assert cards.Card.from_dict(card.as_dict()).as_dict() == card.as_dict()


def test_the_demonstrations_share_no_word_with_any_world_and_carry_no_digit():
    """One demonstration per approach, set where no world is, so its shape is copied and
    its words cannot be (CLAUDE.md: the shape of a prompt becomes the shape of the output)."""
    from world.loader import load_cached

    demos = hooks.demonstrations()
    assert set(demos) == set(hooks.APPROACHES)
    words = set()
    for path in ("fixtures/aurvantis-campaign.json", "fixtures/pangrella-campaign.json",
                 "fixtures/synthetic-world.json"):
        world = load_cached(path)
        for ent in world.entities.values():
            words |= {w.lower() for w in re.findall(r"[A-Za-z]{4,}", str(ent.name))}
    stop = {"that", "with", "from", "have", "this", "they", "when", "what", "your", "will",
            "been", "down", "back", "more", "good", "month", "black", "mood", "night"}
    for how, text in demos.items():
        assert not re.search(r"\d", text), how
        shared = {w.lower() for w in re.findall(r"[A-Za-z]{4,}", text)} & words - stop
        assert not shared, (how, sorted(shared))


# --- the checks ----------------------------------------------------------------------------

def _ctx(s, e, world, *, text, said, reading=None, pull=None, player_text=""):
    return BeatContext(door="turn", text=text, player_text=player_text, engine=e, scene=s,
                       world=world, location=world.get(s.location_id), reading=reading,
                       outcomes=(), tells=(), said=tuple(said), attribution=None, brief="",
                       brief_facts={}, pull=pull, was_at=s.at, acting="", turn=8)


def _bobby_beat(world):
    """Turn 4 of the corpus, at Vormoor's market: Drenn with the pull, his two lines."""
    record = replays.turn(4)
    vormoor = world.by_name("Vormoor", kind="CITY").id
    s = Scene(location_id=vormoor)
    s.add(load_pc("fixtures/pc-kesst.json"))
    s.clock_minutes = WORK_HOUR
    e = Engine(s, Dice(seed=5), world=world)
    e.place_party(schemes._place_for(e, "market", {})["id"])
    drenn = world.by_name("Drenn Ironvale")
    d = _giver(s, name="Drenn Ironvale", entity=getattr(drenn, "id", None))
    card = cards.open_quest(s, title="Find Drenn Ironvale's lost Power leaf",
                            objectives=["Search the wild for the Power leaf",
                                        "Bring the Power leaf back to Drenn Ironvale"],
                            giver=d.ref, reward="Drenn Ironvale's gratitude",
                            people=[d.ref], place=s.at, origin="author:test", turn=1)
    beat = record["beats"][0]
    said = [dict(r, who=d.ref) for r in beat["said"]]
    reading = {k: v for k, v in record["plan"]["reading"].items()
               if k in ("question", "actions", "claims")}
    pull = {"id": card.id, "title": card.title, "people": [d.name],
            "keys": cards.identity_keys(card, [d.name]),
            "giver": {"ref": d.ref, "name": d.name, "role": ""}}
    return s, e, d, beat, said, reading, pull, record["player"]


def _corpus():
    if not replays.available():
        pytest.skip("the Bobby corpus is not on this disk (kept out of the repository)")
    from world.loader import load_cached

    return load_cached("fixtures/aurvantis-campaign.json")


def test_the_replayed_bobby_beat_raises_pull_took_the_beat():
    """The beat itself: the girl sought, never answered, and Drenn's two lines."""
    from gm.checks import pull_yields

    world = _corpus()
    s, e, d, beat, said, reading, pull, player = _bobby_beat(world)
    found = pull_yields.find(_ctx(s, e, world, text=beat["text"], said=said, reading=reading,
                                  pull=pull, player_text=player))
    assert [f.kind for f in found] == ["pull-took-the-beat"] and found[0].weight == 3


def test_a_beat_that_answers_the_search_is_not_flagged(worlds):
    from gm.checks import pull_yields

    s, e, _m = _market(worlds)
    g = _giver(s)
    card = _quest(s, g)
    said = [{"who": g.ref, "to": "you", "line": "Fine weather for it."}]
    text = ("The girl is not at any stall you can see; a woman at the fish stall says she "
            "went home an hour ago. 'Fine weather for it,' the net-mender says.")
    found = pull_yields.find(_ctx(s, e, worlds, text=text, said=said, reading=SEEK_READING,
                                  pull={"id": card.id, "people": [g.name]}, player_text=SEEK))
    assert found == []


def test_the_replayed_bobby_beat_asks_the_player_for_its_own_answer():
    """"do you have any idea where such a thing might be hidden?" — of his own leaf."""
    from gm.checks import hook_leaks

    world = _corpus()
    s, e, d, beat, said, reading, pull, player = _bobby_beat(world)
    kinds = [f.kind for f in hook_leaks.find(_ctx(s, e, world, text=beat["text"], said=said,
                                                  reading=reading, pull=pull))]
    assert "giver-asks-own-answer" in kinds


def test_the_secret_on_a_givers_line_is_flagged(worlds):
    from gm.checks import hook_leaks

    s, e, _m = _market(worlds, clock=DAY_TWO)
    inst = schemes.open_scheme(e, schemes.shipped()["the-lost-thing"], turn=1)
    giver = s.people[inst["slots"]["giver"]["ref"]]
    rival = s.people[inst["slots"]["rival"]["ref"]]
    quest = next(c for c in cards.load(s) if c.kind == "quest")
    truth = next(c for c in cards.load(s) if c.secret)
    distinctive = [k for k in cards.identity_keys(truth, cards._card_names(truth, s))
                   if k not in cards.identity_keys(quest, cards._card_names(quest, s))]
    assert len(distinctive) >= 2, distinctive
    line = f"It is {' and '.join(distinctive[:2])}, if you must know."
    ctx = _ctx(s, e, worlds, text=f"'{line}' {giver.name} says.",
               said=[{"who": giver.ref, "to": "you", "line": line}],
               pull={"id": quest.id, "people": [giver.name],
                     "keys": cards.identity_keys(quest, [giver.name]),
                     "giver": {"ref": giver.ref}})
    assert "hook-secret-on-page" in [f.kind for f in hook_leaks.find(ctx)]
    assert rival.name


def test_the_replayed_bobby_beat_greets_the_tied_teacher_as_a_stranger():
    """"You! You have the look of…" from the man Bobby's background says taught him."""
    from gm.checks import giver_knows_you

    world = _corpus()
    s, e, d, beat, said, reading, pull, player = _bobby_beat(world)
    s.acquainted = [d.world_entity_id] if d.world_entity_id else []
    s.pc().background_ties = ["You learned it from Drenn Ironvale, who was surprised how "
                              "well you took to it."]
    found = giver_knows_you.find(_ctx(s, e, world, text=beat["text"], said=said,
                                      reading=reading, pull=pull))
    assert [f.kind for f in found] == ["greets-known-as-stranger"]
    assert "You learned it from Drenn Ironvale" in found[0].fix_hint


def test_a_known_person_greeting_warmly_is_not_flagged(worlds):
    from gm.checks import giver_knows_you

    s, e, _m = _market(worlds)
    g = _giver(s, name="Wenna Stoat", entity="ent-wenna")
    s.acquainted = ["ent-wenna"]
    line = "There you are! You look fed, at least."
    found = giver_knows_you.find(_ctx(s, e, worlds, text=f"'{line}'",
                                      said=[{"who": g.ref, "to": "you", "line": line}]))
    assert found == []
