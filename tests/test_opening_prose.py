"""The written opening: model prose, checked against the material it was given.

"there is absolutely no description of the place i am in. this is a failure." — the
player, 2026-09-04, on a template opening that read the export's fields aloud. The
model writes the screen now, from the place's own paragraphs, and everything the
model could get wrong is detected in code before the player sees it.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field

import pytest

from play import opening, opening_prose


@dataclass
class FakeEntity:
    id: str
    kind: str
    name: str
    facts: dict = field(default_factory=dict)
    prose: str = ""
    scale: str | None = None
    sections: list = field(default_factory=list)

    def fact(self, key, default=""):
        return self.facts.get(key, default)


@dataclass
class FakePC:
    name: str = "Borin Achereth"
    char_class: str = "fighter"
    equipped: str = "longsword"
    armour: str = "chain shirt"
    world_people_id: str | None = None
    heritage: str = "Nahyrin"
    race: str = "human"

    def carried(self):
        return [self.equipped, self.armour]


class FakeWorld:
    name = "Fantasia"
    premise: dict = {}

    def __init__(self, town):
        self.entities = {town.id: town}

    def get(self, eid):
        return self.entities.get(eid)


def _campaign():
    town = FakeEntity("t1", "CITY", "Vyrakon", facts={
        "Architecture": "wooden buildings, thatched roofs",
        "Formal Power": "matriarchal clan law",
        "Daily Norms": "morning markets, evening prayers",
    }, prose=("Vyrakon's architecture features wooden buildings with thatched roofs, "
              "designed for cyclone-prone coastlines. The Salt Market in the Old "
              "Quarter dominates bulk trade."))

    class Scene:
        def pc(self):
            return FakePC()

    class Campaign:
        id = "probe"
        seed = 7
        scene = Scene()

    c = Campaign()
    c.world, c.location = FakeWorld(town), town
    return c


SITUATION = opening.SITUATIONS[1]      # the common room


def _skeleton(c):
    return opening.compose(c, "Nahyrin, a long way from anyone who knows you")


def test_the_material_allows_the_worlds_own_words_and_nothing_else():
    """The place's paragraphs name a Salt Market and an Old Quarter the export never
    lists as entities. A check that called those inventions would refuse the world's
    own writing; a check that allowed anything would let the model add a tavern
    keeper called Grimble. Every capitalised word of the material is allowed; a
    capitalised word from nowhere is not."""
    c = _campaign()
    text, allowed = opening_prose.material(c, SITUATION, _skeleton(c))
    assert "Salt Market" in text and "Vyrakon" in text and "longsword" in text
    assert {"Salt", "Market", "Vyrakon", "Borin", "Achereth"} <= allowed
    assert not opening_prose.problems(
        "The Salt Market has gone quiet. " * 30 + "You are Borin Achereth in Vyrakon. "
        "What do you do?", allowed, "Vyrakon", "Borin Achereth")
    wrong = opening_prose.problems(
        "The Salt Market has gone quiet. " * 30 + "A keeper called Grimble watches you, "
        "Borin, in Vyrakon. What do you do?", allowed, "Vyrakon", "Borin Achereth")
    assert any("Grimble" in w for w in wrong), wrong


@pytest.mark.parametrize("draft, expect", [
    ("Short. What do you do?", "words"),
    ("word " * 400 + "What do you do?", "cut it"),
    ("A quiet room in Vyrakon. " * 20 + "You, Borin, sit still.", "end with the question"),
    ("The room in Vyrakon holds 12 men. " * 15 + "Borin, what do you do?", "digits"),
    ("You realize the room in Vyrakon has gone still. " * 12 + "Borin, what do you do?",
     "decides for the player"),
    ("Somewhere a room has gone still. " * 15 + "Borin, what do you do?",
     "never says where"),
    ("The room in Vyrakon has gone still. " * 15 + "What do you do?",
     "never says who"),
])
def test_each_way_a_draft_can_be_wrong_is_named_for_the_repair(draft, expect):
    """Validators name the fix, not the fault — the repair call is told exactly what
    to change and nothing else."""
    c = _campaign()
    _, allowed = opening_prose.material(c, SITUATION, _skeleton(c))
    found = opening_prose.problems(draft, allowed, "Vyrakon", "Borin Achereth")
    assert any(expect in f for f in found), (expect, found)


def test_a_copied_example_is_caught():
    """The Continue examples taught this repo that a model finishes the nearest
    stopped thing in front of it; the ferry example exists to be copyable and
    caught. Six shared words in a row is the echo detector's own threshold."""
    c = _campaign()
    _, allowed = opening_prose.material(c, SITUATION, _skeleton(c))
    ferry = json.loads(opening_prose.EXAMPLE["assistant"])["opening"]
    draft = ferry.replace("Hollin Stair", "Vyrakon").replace("Teodor Vance", "Borin Achereth")
    found = opening_prose.problems(draft, allowed, "Vyrakon", "Borin Achereth")
    assert any("copies the example" in f for f in found), found


def test_the_example_is_about_nowhere_the_table_can_roll():
    """Worked example 11 of the turn prompt was "I put my shoulder to the door" and
    the opening situation was a lit doorway; the two fused in play. The opening's one
    example may not share a setting word with any of the twelve situations."""
    example = opening_prose.EXAMPLE["user"].lower() + opening_prose.EXAMPLE["assistant"].lower()
    for word in ("common room", "market", "yard", "well", "gate", "square", "workshop",
                 "doorway", "cart", "step in the sun", "crossing", "ritual"):
        assert word not in example, word


def test_a_model_that_is_down_is_the_template_not_a_failed_start(monkeypatch):
    """Never raises: a game that cannot start because the prose model is not running
    is worse than a flat first screen."""
    from gm import client

    def down(*a, **k):
        raise client.ModelUnavailable("nothing on 11434")
    monkeypatch.setattr(client, "chat", down)
    monkeypatch.setattr(opening_prose, "ENABLED", True)
    c = _campaign()
    skeleton = _skeleton(c)
    text, wrong = opening_prose.write(c, SITUATION, skeleton)
    assert text == skeleton
    assert wrong and "failed" in wrong[0]


def test_a_bad_draft_is_repaired_once_with_the_complaint_and_then_dropped(monkeypatch):
    """One write, one repair naming what was wrong, then the floor. The repair call
    must carry the complaint — a retry that says nothing is a coin toss."""
    from gm import client

    calls = []

    def Reply(text):
        return client.Reply(text=text, seconds=0.0, model="fake")

    def fake_chat(messages, **k):
        calls.append(messages)
        n = len(calls)
        if n == 1:
            return Reply(json.dumps({"opening": "Old Grimble looks up. " * 60 + "Borin, in Vyrakon, what do you do?"}))
        return Reply(json.dumps({"opening": (
            "The clatter nearest the door has died, and the hush is spreading inward "
            "one table at a time. " * 12 + "Vyrakon's cyclone thatch drips over you, "
            "Borin Achereth, longsword at your side. What do you do?")}))
    monkeypatch.setattr(client, "chat", fake_chat)
    monkeypatch.setattr(opening_prose, "ENABLED", True)
    c = _campaign()
    text, wrong = opening_prose.write(c, SITUATION, _skeleton(c))
    assert wrong == []
    assert text.startswith("The clatter nearest the door")
    assert len(calls) == 2
    complaint = calls[1][-1]["content"]
    assert "Grimble" in complaint and "Rewrite it" in complaint


def test_a_draft_that_ignores_the_places_own_writing_is_sent_back():
    """Measured on the first three live drafts, 2026-09-04: all three passed every
    other check, and not one used a word of the place's paragraphs — the Salt
    Market, the cyclone coast, the flooded districts — because the template's facts
    were nearer to hand. The repair names the fix: one physical detail from that
    writing, in the paragraph about the place."""
    c = _campaign()
    skeleton = _skeleton(c)
    _, allowed = opening_prose.material(c, SITUATION, skeleton)
    prose = c.location.prose
    bland = ("The hush spreads through the room in Vyrakon. " * 24
             + "You are Borin Achereth. What do you do?")
    found = opening_prose.problems(bland, allowed, "Vyrakon", "Borin Achereth",
                                   prose=prose, skeleton=skeleton)
    assert any("place's own writing" in f for f in found), found
    placed = bland.replace("through the room", "through a room built for cyclone winds")
    assert opening_prose.drawn_from_the_place(placed, prose, skeleton) == ["cyclone"]
    assert not opening_prose.problems(placed, allowed, "Vyrakon", "Borin Achereth",
                                      prose=prose, skeleton=skeleton)


def test_the_game_nobody_asked_for_does_not_wait_on_the_model(monkeypatch):
    """`_begin` enrols the shipped pregen from the home page's own request when there
    is no save at all. A home page that waits on a cold 12B model is the hung home
    page of the same morning, so that path takes the template and never calls."""
    from gm import client
    from play import campaign as cm

    def never(*a, **k):
        raise AssertionError("the default game called the prose model")
    monkeypatch.setattr(client, "chat", never)
    c = _campaign()
    text = cm.opening_text(c, written=False)
    assert text.endswith("What do you do?")
