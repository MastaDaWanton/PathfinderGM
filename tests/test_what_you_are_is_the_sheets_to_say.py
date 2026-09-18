"""A player declaring what their character IS plays as the boast it is.

Reported with a screenshot, 2026-09-18, on 0.1.9. Two turns earlier the same session
had been handled well: "I attempt to implode the boxes" got "the world remains
stubbornly intact", "I swing the longsword cutting reality apart" got "the world does not
tear". Then:

    I reveal my true from as a divine being

and the prose made it so — "The mud at your feet flash-freezes into glass … the silhouette
isn't that of a man, but something towering and ancient. The stranger on the step falls to
his knees … What do you say to them now that the truth is laid bare?"

Why the 0.1.9 gates missed it: `refuse_unnamed_power` turns a claimed faculty into
`use_ability` so the engine's door can refuse it, but this line produced no intent at all,
and a gate on intents has nothing to hold.

The first fix was a door — the line handed back before any model, like fiat. The player's
own correction the same morning: "It should read as my character being delusional and the
people should see it similarly … if I were to say aloud that I will reveal my true nature
and then nothing happens or I open my coat to no changes people should roll their eyes or
look at me with pity." So the claim PLAYS: it becomes a Bluff the room rolls to see
through, the prose is told the claim is false and how the roll went, a finding catches
prose that makes it true with a backstop under it, and the crowd's reaction rides heat.
"""
from __future__ import annotations

import inspect

import pytest

from gm import judgement, narration, prompts
from rules.engine import Outcome, Scene


class _PC:
    is_pc = True
    name = "Dorito"
    ref = "pc"
    at = ""
    is_down = False
    race = "asura"
    heritage = ""
    char_class = "blood bending"
    class_data = {"name": "Blood Bending"}
    paths = ["battle blood"]
    feats = ["toughness"]
    background = "pit-fighter"
    background_ties = ["You fought where Drenn Ironvale took the bets, near the market."]
    gender = "man"

    def carried(self):
        return ["longsword", "traveler's outfit"]


class _Body:
    def __init__(self, ref, name):
        self.ref, self.name, self.is_pc, self.is_down, self.at, self.hp = ref, name, False, False, "", 10


def _scene(*others):
    s = Scene()
    s.people = {"pc": _PC()}
    for i, n in enumerate(others, 1):
        s.people[f"c{i}"] = _Body(f"c{i}", n)
    return s


@pytest.fixture
def plain(monkeypatch):
    """A character whose sheet grants no form, shape or divinity."""
    from rules import leveling

    monkeypatch.setattr(leveling, "usable_names", lambda actor: ["Blood Armament", "Iron Skin"])
    return _scene("stranger", "merchant")


@pytest.fixture
def shapeshifter(monkeypatch):
    from rules import leveling

    monkeypatch.setattr(leveling, "usable_names", lambda actor: ["Wild Shape", "Woodland Stride"])
    return _scene("stranger")


REPORTED = "I reveal my true from as a divine being"        # the reported line, typo and all

GRANTED = ("The words do not leave your throat as a sound; they leave your lips as a command "
           "that vibrates in the marrow of the onlookers' bones. For a heartbeat, the air "
           "around you doesn't just move — it folds. The mud at your feet flash-freezes into "
           "glass, and the moisture in the air crystallizes into a shimmering haze. Your "
           "shadow stretches out across the dirt, and for a moment the silhouette isn't that "
           "of a man, but something towering and ancient. The stranger on the step falls to "
           "his knees, his face pressed into the dirt. You stand in the center of it, the air "
           "still humming with the residue of your presence. What do you say to them now that "
           "the truth is laid bare?")


# --- the claim is seen for what it is --------------------------------------------------------


@pytest.mark.parametrize("line", [
    REPORTED,
    "I reveal my true form as a divine being.",
    "I shed my mortal guise and rise.",
    "I transform into a dragon and roar at them.",
    "Knowing what I am, I let go of the mask of being human and show my true nature to the crowd.",
    "I am no mere mortal, and I let them see it.",
    "As a god such as myself, I make the crates kneel.",
    # Not a word list. "don't just do divine being or I will just find a way around it."
    "I reveal to them that I am the king's lost heir.",
    "I am actually the greatest swordsman alive, and I tell them so.",
    "I unleash the ancient power within me.",
    "I am the chosen one of the old prophecy.",
    "I have always been a wizard; I only hid it.",
    "I'm a Vyrakon noble, and they will treat me as one.",
    'I tell the guard, "I am a divine being and you will kneel."',    # a boast aloud is the boast
    "I let them see what I truly am: a master assassin of the eastern guilds.",
])
def test_declaring_what_you_are_is_a_claim_the_sheet_holds_false(plain, line):
    claim = judgement.false_claim(line, plain)
    assert claim, line
    # Their own words, said about them, so the prose can be told what was claimed.
    assert not claim.lower().startswith(("i am", "i'm", "my ")), claim


@pytest.mark.parametrize("line", [
    "I ask him whether he believes I am a god?",                     # a question is asking
    "I reveal the letter to the crier.",                             # revealing a thing
    "I take the true road north.",                                   # "true" is not a form
    "I punch him in the face.",
    "I turn into the alley.",
    "I am tired and I sit down.",                                    # a state
    "I am the last in the queue and I wait.",                        # a place, not a being
    "I am not a god, I tell him, just a traveller.",                 # a denial
    # What the sheet vouches for is not a claim: the class, the background bound to the
    # world, the race, the name, a power of the class.
    "I am a pit-fighter, and I have the scars to prove it.",
    "I am an asura.",
    "I am Dorito.",
    "I unleash the blood within me.",
])
def test_questions_states_denials_and_the_sheets_own_words_make_no_claim(plain, line):
    assert judgement.false_claim(line, plain) == "", line


def test_a_class_the_sheet_does_not_hold_is_a_claim_and_the_one_it_does_is_not(plain):
    """A Blood Bender saying "I am a fighter" lies; a fighter saying it does not."""
    assert judgement.false_claim("I am a fighter, and a good one.", plain)
    plain.pc().class_data = {"name": "Fighter"}
    plain.pc().char_class = "fighter"
    assert judgement.false_claim("I am a fighter, and a good one.", plain) == ""


def test_the_claim_reads_as_said_about_them():
    assert judgement._as_they("I am the king's lost heir") == "are the king's lost heir"
    assert judgement._as_they("reveal my true form as a divine being") ==         "reveal their true form as a divine being"
    assert judgement._as_they("I have always been a wizard") == "have always been a wizard"


def test_throwing_a_coat_open_is_not_violence():
    """Measured in the live check of this very feature: "I throw my coat open to show
    them and wait for the light" started a fight with the apprentice — the bare verb
    "throw" was on the violence list, and the model's actor-less attack was handed to
    the player as the one swinging."""
    assert not judgement._player_is_the_one_swinging("I throw my coat open to show them.")
    assert judgement._player_is_the_one_swinging("I throw my dagger at him.")
    assert judgement._player_is_the_one_swinging("I hurl the stone at the guard.")


def test_a_sheet_that_grants_a_form_makes_it_no_claim(shapeshifter):
    """A druid's Wild Shape is an ability being used, and `inject_ability` routes it."""
    assert judgement.false_claim("I transform into a bear.", shapeshifter) == ""
    assert judgement.false_claim("I reveal my true form.", shapeshifter) == ""


# --- it plays as a Bluff --------------------------------------------------------------------


def test_the_claim_becomes_a_bluff_the_room_rolls_to_see_through(plain):
    raw = [{"op": "narrate_only", "actor": "pc"}]
    out = judgement.inject_false_claim(raw, REPORTED, plain)
    assert [r["op"] for r in out] == ["check"], out
    check = out[0]
    assert check["params"]["skill"] == "bluff" and check["visibility"] == "player"
    assert check["params"]["dc"]["band"] == "heroic", "I am a god is the far end of a lie"
    # A Bluff the model already wrote is not doubled, and an ordinary line adds nothing.
    already = [{"op": "check", "actor": "pc", "params": {"skill": "bluff", "dc": {"band": "tough"}}}]
    assert judgement.inject_false_claim(already, REPORTED, plain) is already
    plain_line = [{"op": "narrate_only", "actor": "pc"}]
    assert judgement.inject_false_claim(plain_line, "I look around.", plain) is plain_line


def test_the_injector_runs_in_the_plan_before_the_check_injector():
    from gm import agent

    src = inspect.getsource(agent.GMAgent.plan_turn)
    assert src.index("refuse_declared_creation") < src.index("inject_false_claim") \
        < src.index("inject_checks(")


# --- the prose is told it is false, and caught when it makes it true ---------------------------


def test_the_prose_prompt_carries_the_engines_word_last():
    block = prompts.false_claim_block("reveal my true form as a divine being")
    assert "HOLDS FALSE" in block and "NOTHING HAPPENED" in block and "Nobody kneels" in block
    assert "SUCCEEDED" in block and "FAILED" in block, "the Bluff's verdict decides the faces"
    msgs = prompts.call_prose_messages("WORLD: Test.", [], REPORTED, ["Dorito fails the Bluff check by 9."],
                                       scene_now_block="THE SCENE AS IT STANDS NOW: nothing.",
                                       claim=block)
    last = msgs[-1]["content"]
    assert last.rstrip().endswith("Nobody kneels.")
    assert last.index("What the engine decided") < last.index("HOLDS FALSE")


def test_the_measured_prose_is_caught_as_granting_a_nature():
    granted = narration.grants_a_nature(GRANTED)
    assert granted, "flash-freezing mud, a silhouette not a man's, a stranger on his knees"
    assert any("flash-freezes" in s for s in granted)
    assert any("knees" in s for s in granted)
    assert any("towering and ancient" in s for s in granted)
    r = narration.review(GRANTED, claim="reveal my true form as a divine being")
    f = next(f for f in r.findings if f.kind == "grants-a-nature")
    assert f.weight == 3 and "Nobody kneels" in f.fix_hint
    # The same prose with no claim this turn raises nothing: a real dragon may kneel a crowd.
    assert "grants-a-nature" not in {f.kind for f in narration.review(GRANTED).findings}


def test_honest_prose_about_a_false_claim_passes():
    honest = ("You say it, loud enough for the step to hear, and throw your coat open. Nothing "
              "happens. The stranger on the step looks at you for a long moment and then "
              "back at his bread. 'Right,' he says. What do you do?")
    assert narration.grants_a_nature(honest) == []
    assert "grants-a-nature" not in {
        f.kind for f in narration.review(honest, claim="reveal my true form").findings}


def test_the_backstop_cuts_the_granting_and_writes_the_worlds_answer_never_twice_running():
    said: dict = {}
    outs = []
    for _ in range(4):
        out, cut = narration.cut_granted_nature(GRANTED, "reveal my true form as a divine being",
                                                ("stranger", "merchant"), said=said)
        assert cut and not narration.grants_a_nature(out), out
        assert "The stranger" in out, "the nearest person present is the one who reacts"
        # The hand-back itself asserted the truth was "laid bare" and went with the rest;
        # `_groom` puts the question back afterwards, as it does for every beat.
        assert "laid bare" not in out and "flash-freezes" not in out
        outs.append(out)
    assert len(set(outs)) == 4, "four answers, none repeated"
    same, none = narration.cut_granted_nature("You say it. Nothing happens. What do you do?",
                                              "reveal my true form", ("stranger",), said={})
    assert none == [] and same.startswith("You say it.")


# --- the crowd saw it -------------------------------------------------------------------------


def test_the_crowd_saw_somebody_claim_to_be_a_god(plain):
    judgement.note_heat(plain, [], REPORTED)
    assert plain.heat["kind"] == "delusion"
    assert "nothing happened" in plain.heat["note"] and "nobody believed" in plain.heat["note"]
    assert "pity" in judgement.heat_brief(plain) and "Nobody kneels" in judgement.heat_brief(plain)
    # A Bluff that took changes the faces, not the fact.
    took = Outcome(intent_id="i1", op="check", verdict="success",
                   tell="Dorito makes the Bluff check by 2.")
    judgement.note_heat(plain, [took], REPORTED)
    assert "half-took" in plain.heat["note"] and plain.heat["kind"] == "delusion"


def test_the_say_handler_stashes_the_claim_for_the_prose_instead_of_refusing():
    from play import views

    src = inspect.getsource(views.say)
    assert "agent.false_claim" in src and "claims_a_nature" not in src
    assert 'status=422' in src.split("agent.false_claim")[0], "fiat is still handed back"
    src2 = inspect.getsource(views._finish)
    assert "claim=str(getattr(agent, \"false_claim\"" in src2
