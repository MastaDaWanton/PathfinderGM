"""The watcher's undercurrent and the GM's table talk: the 2026-11-16 overnight playtest
(log pgm-work/playtest-2026-11-16.md, the item numbers below).

* #97: the undercurrent read twelve beats of narration and wrote "Aethonira, watching the
  player's interaction with the Korvu deckhand, notes ... confirming his status as a
  skilled survivor of the Nahyrin's previous purges" — an unseen watcher and an invented
  history, kept as the GM's memory.
* #82: the watcher laid "The passage into the sewers from the gardens is now clear" on the
  dungeon's quest, which only the engine settles; nothing was cleared.
* #71: the table talk said "Mirabalos doesn't have any healers in this order" over a
  refusal that said only that no Father is here.
* #93: on a natural one on a search, "You tripped over your own feet while looking". No
  tell said so, and 1e has no fumble on a skill check.

Synthetic scenes; the save itself is private.
"""
from __future__ import annotations

import json
from types import SimpleNamespace

import pytest
from django.test import override_settings

from rules import bestiary, cards
from rules.sheet import load_pc


@pytest.fixture
def campaign(tmp_path):
    from gm import watcher
    from play import campaign as cm

    with override_settings(CAMPAIGN_DIR=tmp_path / "campaigns"):
        cm._LIVE.clear()
        watcher._reset()
        yield cm.begin_with(load_pc("fixtures/pc-kesst.json"))
        cm._LIVE.clear()
        watcher._reset()


# --- #97: the undercurrent is shown tells, never prose -----------------------------------------

def test_the_undercurrent_is_shown_the_engines_tells_not_the_narration(campaign):
    """#97: the prose said a watcher was on deck and the deckhand had survived purges; the
    engine said only that she spoke to him. The undercurrent's job sees the tell."""
    from gm import watcher

    c = campaign
    assert watcher._jobs_for(c) == []                 # first sight starts the clock
    for _ in range(watcher.TURNS_BETWEEN_LOOKS):
        c.transcript.append({"who": "gm", "kind": "setup",
                             "text": "Aethonira watches from the rail; the deckhand is a "
                                     "survivor of the Nahyrin's previous purges."})
        c.turn_log.append({"kind": "turn", "outcomes": [
            {"op": "say", "status": "resolved", "actor": "pc",
             "tell": "Kesst asks the deckhand what the ship was carrying."}]})
    job = next(j for j in watcher._jobs_for(c) if j["job"] == "undercurrent")
    assert job["recent"] == ["Kesst asks the deckhand what the ship was carrying."]
    assert not [r for r in job["recent"] if "Aethonira" in r or "purges" in r]


# --- #82: an engine-kept quest takes no watcher fact -------------------------------------------

def _dungeon_quest(c):
    who = c.scene.add(bestiary.instantiate("commoner-level-1", scene=c.scene,
                                           name="the gardener"))
    return cards.open_card(c.scene, cards.Card(
        id="quest-3-find-what-was-kept-below", title="Find what was kept below",
        kind="quest", origin="rule:dungeon/sewers", people=[who.ref]), turn=1)


def test_the_watcher_is_not_shown_a_dungeon_quest(campaign):
    """#82: the dungeon's quest is ticked only by `dungeons.settle`; the cards job never
    sees it, so no fact can be written on it."""
    from gm import watcher
    from rules import objectives

    c = campaign
    card = _dungeon_quest(c)
    assert objectives.engine_keeps(card)
    watcher._jobs_for(c)
    c.turn_log += [{"kind": "turn", "outcomes": []}] * 10
    jobs = [j for j in watcher._jobs_for(c) if j["job"] == "cards"]
    assert not [k for j in jobs for k in j["cards"] if k["id"] == card.id]


def test_a_watcher_fact_named_on_a_dungeon_quest_is_refused(campaign):
    """#82, at the door that writes: "The passage into the sewers from the gardens is now
    clear" named against the quest anyway leaves the card exactly as it was."""
    from gm import watcher

    c = campaign
    card = _dungeon_quest(c)
    before = (list(card.facts), card.stage, card.clock)
    fact = "The passage into the sewers from the gardens is now clear."
    changed = watcher._apply_cards(c, {"changes": [
        {"id": card.id, "action": "advance", "fact": fact,
         "was": [card.stage, card.clock]}]})
    now = cards.find(c.scene, card.id)
    assert not changed
    assert (list(now.facts), now.stage, now.clock) == before
    assert c.turn_log[-1]["action"] == "refused"


# --- #71, #93: the table talk states nothing past the facts ------------------------------------

AGENT = SimpleNamespace(prose_model="m", prose_host="", prose_provider="ollama", prose_key="")
TRIP = "Ouch, that one is a sting. You tripped over your own feet while looking."
FACTS = ["The die showed a natural one on the Perception check.",
         "What happened: Kesst searches the hold and finds nothing."]


@pytest.fixture
def reads(monkeypatch):
    """The two reads scripted: nothing contradicts; a sentence about tripping or healers
    adds a fact."""
    from gm import beat_verify

    monkeypatch.setattr(beat_verify, "ENABLED", True)
    monkeypatch.setattr(beat_verify, "against_tells",
                        lambda text, premises, **kw: SimpleNamespace(clashes=[]))

    def beyond(text, premises, **kw):
        return [(s, s.rstrip(".")) for s in
                (x.strip() + "." for x in text.split(".") if x.strip())
                if "tripped" in s or "healers" in s]

    monkeypatch.setattr(beat_verify, "beyond_tells", beyond)


def test_a_table_line_that_invents_a_deed_is_asked_again(reads):
    """#93: the invented trip is named in one narrow ask; the clean remake goes out."""
    from play import table_talk

    asked = []

    def ask(msgs):
        asked.append(msgs[-1]["content"])
        return "Ouch, that one is a sting. Nothing down there worth the climb."

    line, why, remade = table_talk._held_to_the_tells(
        AGENT, ask, [], TRIP, TRIP, FACTS, None, "", [])
    assert (line, why, remade) == (
        "Ouch, that one is a sting. Nothing down there worth the climb.", "", True)
    assert "You tripped over your own feet while looking" in asked[0]


def test_a_table_line_that_invents_again_keeps_only_its_reaction(reads):
    """#93: remade and still tripping, the sentence is cut and the reaction kept."""
    from play import table_talk

    line, why, _ = table_talk._held_to_the_tells(
        AGENT, lambda m: TRIP, [], TRIP, TRIP, FACTS, None, "", [])
    assert (line, why) == ("Ouch, that one is a sting.", "")


def test_a_table_line_that_is_all_invention_is_dropped(reads):
    """#71: "Mirabalos doesn't have any healers in this order" with nothing else said, and
    the remake no better: no line at all."""
    from play import table_talk

    said = "Mirabalos doesn't have any healers in this order."
    line, why, _ = table_talk._held_to_the_tells(
        AGENT, lambda m: said, [], said, said,
        ["Refused: No Father is here, and Mirabalos has none the world names."],
        None, "Mirabalos Father", [])
    assert line == "" and why.startswith("states what no fact carries")


def test_the_read_acts_only_on_words_the_sentence_holds():
    """The reader's "adds" costs a sentence only when it quotes that sentence (the same
    grounding as the tells check); a verdict it cannot point at is no finding."""
    from gm import beat_verify

    answer = {"1": {"verdict": "reacts", "words": ""},
              "2": {"verdict": "adds", "words": "You tripped over your own feet"},
              "3": {"verdict": "adds", "words": "the guild hoards every boat"}}
    seen = {}

    def chat(msgs, *a, **kw):
        seen["schema"] = kw["schema"]
        return SimpleNamespace(json=lambda: answer)

    found = beat_verify.beyond_tells(
        "Ouch, that one is a sting. You tripped over your own feet. Try the deck instead.",
        FACTS, who="Kesst", chat=chat, model="m")
    assert found == [("You tripped over your own feet.", "You tripped over your own feet")]
    assert seen["schema"]["required"] == ["1", "2", "3"]
    assert json.dumps(seen["schema"]).count('"adds"') == 3


def test_a_failed_read_leaves_the_line_alone():
    from gm import beat_verify

    def chat(*a, **kw):
        raise RuntimeError("down")

    assert beat_verify.beyond_tells("You tripped.", FACTS, chat=chat, model="m") is None
