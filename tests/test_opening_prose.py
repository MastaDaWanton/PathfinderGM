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
    # Nothing WRONG with it; the soft asks (somebody speaking, the past) are separate.
    assert not opening_prose.hard_problems(opening_prose.problems(
        "The Salt Market of Vyrakon has gone quiet. " * 30 + "You are Borin Achereth. "
        "What do you do?", allowed, "Vyrakon", "Borin Achereth"))
    wrong = opening_prose.problems(
        "The Salt Market of Vyrakon has gone quiet. " * 30 + "A keeper called Grimble watches you, "
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
    text, could, wrong = opening_prose.write(c, SITUATION, skeleton, ["Ask", "Look"])
    assert text == skeleton and could == ["Ask", "Look"]
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
            return Reply(json.dumps({"opening": "Old Grimble looks up. " * 60 + "Borin, in Vyrakon, what do you do?",
                                     "suggestions": ["Ask him what he wants", "Leave"]}))
        return Reply(json.dumps({"opening": (
            "Vyrakon's cyclone thatch drips over you. The clatter nearest the door has "
            "died, and the hush is spreading inward one table at a time. " * 12
            + "You are Borin Achereth, longsword at your side. What do you do?"),
            "suggestions": ["Ask the man clearing the table what happened",
                            "Look at the door", "Finish my bowl"]}))
    monkeypatch.setattr(client, "chat", fake_chat)
    monkeypatch.setattr(opening_prose, "ENABLED", True)
    c = _campaign()
    text, could, wrong = opening_prose.write(c, SITUATION, _skeleton(c))
    # Nothing wrong with the repaired draft; the soft asks (a spoken line) may remain
    # and are returned for the record, not held against it.
    assert opening_prose.hard_problems(wrong) == []
    assert text.startswith("Vyrakon's cyclone thatch")
    assert could == ["Ask the man clearing the table what happened",
                     "Look at the door", "Finish my bowl"]
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
    bland = ("The hush spreads through the room in Vyrakon. " * 30
             + "You are Borin Achereth. What do you do?")
    found = opening_prose.problems(bland, allowed, "Vyrakon", "Borin Achereth",
                                   prose=prose, skeleton=skeleton)
    assert any("place's own writing" in f for f in found), found
    placed = bland.replace("through the room", "through a room built for cyclone winds")
    assert opening_prose.drawn_from_the_place(placed, prose, skeleton) == ["cyclone"]
    assert not [f for f in opening_prose.problems(placed, allowed, "Vyrakon",
                                                  "Borin Achereth", prose=prose,
                                                  skeleton=skeleton)
                if "place's own writing" in f]


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
    text, could = cm.opening_text(c, written=False)
    assert text.endswith("What do you do?")
    assert len(could) == 3


# --- 2026-09-18: a player's opening fell to the template, and why ----------------------
#
# The app log for 09:05 that morning reads "opening fell back to the template: it copies
# the example about the ferry; this is not a ferry landing". Both drafts had shared one
# six-word run of stock English with the worked example and were thrown away for a
# template a third shorter than either. Reproduced the same morning on a different
# character: one write in three. The player's verdict: "short and bland".


def test_one_stock_phrase_shared_with_the_example_is_not_a_copy():
    """"with the last of your money" is in the example and in half the openings any
    model will write about a character who is short of coin. A copy carries the ferry's
    nouns; three shared runs is a sentence lifted whole."""
    stock = ("Vyrakon wakes slowly. You came to the yard with the last of your money, "
             "meaning to find work. " + "The yard is loud with somebody else's trade. " * 25
             + "You are john, asura. What do you do?")
    assert opening_prose.copied_from_the_example(stock) == []
    # The boundary: the example's own sentence with two words changed is a nine-word
    # run — three overlapping six-word runs — and that is a copy whatever it is about.
    lifted_clause = ("Vyrakon wakes. You came down this morning with the last of your "
                     "money and no plan. " + "The yard is loud. " * 30 + "What do you do?")
    assert opening_prose.copied_from_the_example(lifted_clause)
    ferry = json.loads(opening_prose.EXAMPLE["assistant"])["opening"]
    lifted = ferry.split("\n\n")[0] + " You are john, in Vyrakon. What do you do?"
    copied = opening_prose.copied_from_the_example(lifted)
    assert copied and any(set(p.split()) & opening_prose.EXAMPLE_MARKS for p in copied)


def test_the_copy_complaint_names_the_phrases():
    """A repair the model cannot locate is a blind retry — the same lesson
    `gm.narration.review` learned on its echo finding."""
    c = _campaign()
    _, allowed = opening_prose.material(c, SITUATION, _skeleton(c))
    ferry = json.loads(opening_prose.EXAMPLE["assistant"])["opening"]
    found = opening_prose.problems(ferry.split("\n\n")[0] + " You are Borin Achereth in "
                                   "Vyrakon. What do you do?", allowed, "Vyrakon",
                                   "Borin Achereth")
    copy = [f for f in found if "copies the example" in f]
    assert copy and "word for word: '" in copy[0] and "ferry landing" in copy[0]


def test_a_capitalised_player_name_still_names_the_player():
    """Every character on the player's shelf is saved lowercase; a model that writes
    "John" has not failed to say who the player is."""
    c = _campaign()
    _, allowed = opening_prose.material(c, SITUATION, _skeleton(c))
    allowed = allowed | {"john"}
    text = ("The Salt Market of Vyrakon has gone quiet. " * 25
            + "You are John, a long way from home. What do you do?")
    assert not [p for p in opening_prose.problems(text, allowed, "Vyrakon", "john")
                if "who the player is" in p]


def test_a_draft_short_of_the_floor_but_longer_than_the_template_ships(monkeypatch):
    """The template is the floor for prose that is wrong, not for prose that is a dozen
    words under what was asked. Measured: a repaired draft was being dropped for a
    template a third shorter than it."""
    from gm import client

    def Reply(text):
        return client.Reply(text=text, seconds=0.0, model="fake")

    c = _campaign()
    skeleton = _skeleton(c)
    n_skel = len(skeleton.split())
    # Long enough to beat the template, short of MIN_WORDS, otherwise clean.
    body = ("The Salt Market of Vyrakon has gone quiet under the thatch. " * 2
            + "A cart stands where the crowd has parted. ")
    while len(body.split()) < n_skel + 5:
        body += "Somebody has put their tools down and not picked them up. "
    draft = body + "You are Borin Achereth, longsword at your side. What do you do?"
    assert n_skel <= len(draft.split()) < opening_prose.MIN_WORDS, (n_skel, len(draft.split()))

    monkeypatch.setattr(client, "chat", lambda *a, **k: Reply(json.dumps(
        {"opening": draft, "suggestions": ["Ask who put the cart there",
                                            "Look at the cart more closely"]})))
    monkeypatch.setattr(opening_prose, "ENABLED", True)
    text, could, wrong = opening_prose.write(c, SITUATION, skeleton, ["Ask", "Look"])
    assert text.startswith("The Salt Market"), "the draft shipped, not the template"
    assert could == ["Ask who put the cart there", "Look at the cart more closely"]
    assert wrong and wrong[0].startswith("only "), wrong


def test_a_draft_shorter_than_the_template_does_not_ship_over_it(monkeypatch):
    from gm import client

    def Reply(text):
        return client.Reply(text=text, seconds=0.0, model="fake")

    c = _campaign()
    skeleton = _skeleton(c)
    stub = "Vyrakon. You are Borin Achereth. What do you do?"
    monkeypatch.setattr(client, "chat", lambda *a, **k: Reply(json.dumps(
        {"opening": stub, "suggestions": ["Ask", "Look"]})))
    monkeypatch.setattr(opening_prose, "ENABLED", True)
    text, could, wrong = opening_prose.write(c, SITUATION, skeleton, ["Ask", "Look"])
    assert text == skeleton and wrong


def test_a_wrong_draft_still_falls_to_the_template(monkeypatch):
    """Hard problems keep the floor: a person who does not exist is not "less than was
    asked", it is wrong."""
    from gm import client

    def Reply(text):
        return client.Reply(text=text, seconds=0.0, model="fake")

    c = _campaign()
    skeleton = _skeleton(c)
    draft = ("Old Grimble looks up from the Salt Market of Vyrakon. " * 30
             + "You are Borin Achereth. What do you do?")
    monkeypatch.setattr(client, "chat", lambda *a, **k: Reply(json.dumps(
        {"opening": draft, "suggestions": ["Ask him", "Leave now"]})))
    monkeypatch.setattr(opening_prose, "ENABLED", True)
    text, could, wrong = opening_prose.write(c, SITUATION, skeleton, ["Ask", "Look"])
    assert text == skeleton and any("Grimble" in w for w in wrong)


def test_the_worlds_own_name_with_a_curly_apostrophe_or_a_suffix_is_not_invented():
    """Two of five live drafts were sent back for "inventing" Khy'vyr — the world's own
    people, written with the curly quote the model prefers, or as "Khy'vyr-style"."""
    from gm.narration import invented_names

    known = {"Khy'vyr", "Nirkor", "Vyrakon"}
    assert invented_names("The Nirkor quarter is quiet; a Khy’vyr boy runs past.", known) == []
    assert invented_names("The stall sells Khy'vyr-style knives to Nirkor women.", known) == []
    assert invented_names("The stall is kept by Grimble, a Nirkor.", known) == ["Grimble"]


# --- 2026-09-18: "nobody knows me", and a stranger who waits to be asked ---------------
#
# On the same morning, the same player: "I chose pit-fighter as my background but there
# is no mention of that and still nobody knows me?" and "its major issue is that again it
# didn't interact with me first, have the stranger ask a question to me or something".
# The save carried `background_ties: ["You fought where Drenn Ironvale took the bets,
# near the market, and drew a crowd."]` — bound on 09-15, read by the turn brief, and
# never handed to the opening's template or material. And the worked example's porter
# stood silent, so every opening's stranger did too.

TIE = "You fought where Drenn Ironvale took the bets, near the market, and drew a crowd."


def _known(c, ties=(TIE,)):
    """A campaign whose character the world has bound a past to. `_campaign()`'s scene
    hands out a fresh FakePC on every call, so the tie has to live on one instance."""
    pc = FakePC()
    pc.background_ties = list(ties)
    c.scene.pc = lambda: pc
    return pc


def test_the_material_carries_the_past_and_allows_its_names():
    c = _campaign()
    _known(c)
    text, allowed = opening_prose.material(c, SITUATION, _skeleton(c))
    assert "Drenn Ironvale took the bets" in text
    assert {"Drenn", "Ironvale"} <= allowed


def test_the_template_names_who_knows_them_instead_of_calling_them_a_stranger():
    from play import campaign as cm

    c = _campaign()
    pc = _known(c)
    pc.world_people_id = None
    standing = cm._standing(c.world, pc)
    assert "long way from anyone who knows you" not in standing
    line = opening.who_you_are(pc, standing)
    assert TIE in line and "long way" not in line
    # Without a past the stranger's line stands, as it always has.
    pc.background_ties = []
    assert "long way from anyone who knows you" in cm._standing(c.world, pc)


def test_ignoring_the_past_and_a_silent_stranger_are_reasons_to_rewrite_not_to_fall_back():
    c = _campaign()
    _, allowed = opening_prose.material(c, SITUATION, _skeleton(c))
    silent = ("The Salt Market of Vyrakon has gone quiet under the thatch. " * 24
              + "You are Borin Achereth, longsword at your side. What do you do?")
    found = opening_prose.problems(silent, allowed, "Vyrakon", "Borin Achereth", past=[TIE])
    assert any(f.startswith("it never uses the character's own past") for f in found), found
    assert any(f.startswith("nobody here has spoken") for f in found), found
    assert opening_prose.hard_problems(found) == [], "soft: the draft still beats the template"
    spoken = silent.replace("What do you do?",
                            "'Ironvale's man, aren't you?' the woman beside you says. "
                            "'Thought you'd left.' What do you do?")
    again = opening_prose.problems(spoken, allowed | {"Ironvale"}, "Vyrakon",
                                   "Borin Achereth", past=[TIE])
    assert not any(f.startswith(("it never uses", "nobody here")) for f in again), again


def test_the_example_shows_the_person_beside_them_speaking_first():
    """Instruction volume loses to demonstration volume: the brief said the person
    beside them "belongs here" and the example showed him silent, and every stranger
    the model wrote was silent too."""
    ferry = json.loads(opening_prose.EXAMPLE["assistant"])["opening"]
    third = ferry.split("\n\n")[2]
    assert opening_prose._SPEECH.search(third), third
    assert "porter beside you" in third
