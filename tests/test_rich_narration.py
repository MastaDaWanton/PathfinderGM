"""WHAT IS HERE TO SEE beside the first act out of fights (gm/planned.py, `see_slot`).

The owner's ask (2026-11-20): slightly longer prose outside combat, nothing added to the
scene. Measured on the richer-prose bench (pgm-work richer-prose-results.md, 105 paired
non-fight beats, three blind scorers): 406 -> 478 characters a beat at the same
errors/beat (0.067 both) and the same invented-scene rate. Planned beats had used the
place's own facts in none of the owner's 2026-11-20 transcript: #11 said "a friendly
atmosphere" beside a carter whose ink-dotted knuckles were in the brief."""
from gm import planned

BRIEF = """THE SCENE
WHEN (fact): day 4, evening (about 6 in the evening).
HERE: the market
  UNDERFOOT at the market (what is physically here, and what the map is drawn from): stalls and awnings, and a cart to climb on.
  THE PLACE, IN ITS OWN WORDS: A river town of tanners and rope-walks.
  THE LAND AROUND REEDSINK (fact; describe from these, in your own words):
    close by: swamp, coast, forest.
"""


class _Scene:
    in_encounter = False
    said = None


class _Engine:
    def __init__(self, fighting=False):
        self.scene = _Scene()
        self.scene.in_encounter = fighting


def test_the_see_lines_are_the_briefs_own_and_the_hour_has_no_day():
    """Two of the arm's seven tells-check remakes on the bench were a wait's slot, shown
    "day 4, evening", writing "the early morning light of day five" beside a tell that
    said "the next day": the day number is the tell's to say, not the see block's."""
    lines = planned.see_lines(BRIEF, _Engine())
    assert lines[-1] == "the hour: evening (about 6 in the evening)."
    assert len([x for x in lines if not x.startswith(("the hour", "the light"))]) == 2
    for x in lines[:-1]:
        assert x.split(": ", 1)[1].rstrip(".") in BRIEF


def test_the_first_act_out_of_a_fight_is_shown_what_is_here_to_see():
    slots = [{"key": "fact1", "want": 220, "say": "The engine decided this: you wait."},
             {"key": "reply", "want": 240, "say": "x"}]
    planned.see_slot(slots, BRIEF, _Engine())
    assert slots[0]["see"].startswith("WHAT IS HERE TO SEE")
    assert slots[0]["want"] == 220 + planned.SEE_EACH * 3
    assert "see" not in slots[1]
    plan = planned.plan_messages("brief", slots, [], "the market")
    for s in slots:
        s["max"] = s["want"]
    ask = planned.slot_messages(plan, slots, 0, [])[1]["content"]
    assert "WHAT IS HERE TO SEE" in ask and "one to three sentences" in ask
    # Shown to its own slot only, never in the PLAN every slot shares (Ollama's cache).
    assert "WHAT IS HERE TO SEE" not in plan[1]["content"]
    assert "WHAT IS HERE TO SEE" not in planned.slot_messages(plan, slots, 1, [])[1]["content"]


def test_a_fight_keeps_its_own_shape():
    slots = [{"key": "fact1", "want": 300, "say": "blow"}]
    planned.see_slot(slots, BRIEF, _Engine(fighting=True))
    assert "see" not in slots[0] and slots[0]["want"] == 300


def test_a_demonstration_word_is_a_leak_only_when_the_scene_does_not_hold_it():
    words = planned._DEMO_WORDS_ACT
    assert planned.demo_leak("You ask the ferry-keeper on the tarred deck.", words, "") == [
        "ferry-keeper", "tarred"]
    assert planned.demo_leak("You cross to the ferry.", words, "the ferry waits") == []
    # An ordinary word is no leak: "landing" was in the bench's list and matched three
    # base beats that held no demonstration ("You climb the stairs and reach the landing").
    assert planned.demo_leak("You climb the stairs and reach the landing.", words, "") == []
