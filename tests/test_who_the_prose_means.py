"""Who the prose means: mentions attributed to refs, and the checks that read them.

docs/who-the-prose-means.md. The engine never confused two people in the 2026-09-27
manoeuvre run; the checks that read the PROSE did, because they guessed from names and
nouns:

  * `wrong_actor` flagged three sound creature-turn beats because the actor was "the
    warrior" or "the Korvu", words its lists did not hold (3 of 3 flags false);
  * `cut_dead_men_walking` cut a LIVING thug's groan because a dead man was also "thug";
  * `creature_nouns_for_pc` wrote the player's name onto the enemy it guessed was them;
  * `apply_introductions` named whoever owned the head word, or the one unnamed person.

gm/mentions.py finds the mentions in code, settles unique names in code, and labels the
rest with one enum-constrained call. On the replay corpus (142 beats, 335 mentions) the
call took 0.54 s median and two hand-graded samples of 45 labels were 37 and 40 right.
"""
from __future__ import annotations

import json

import pytest

from gm import mentions, narration
from gm.mentions import Attribution, Mention

PC, BORIN = "Kesst Vayr", "Borin Lyraxys"


def _cast(*extra):
    base = [{"ref": "pc", "name": PC, "true": "", "pc": True, "what": "", "dead": False},
            {"ref": "c2", "name": BORIN, "true": "", "pc": False, "what": "thug, Korvu",
             "dead": False}]
    return base + list(extra)


# --- step 1: code finds --------------------------------------------------------------------

def test_descriptions_and_names_are_found_and_speech_is_not():
    found = mentions.find(
        "The warrior lunges, and the Korvu's claws rake past you. Borin grunts. "
        "'Kesst, you fool,' he says.", _cast())
    assert [(m.phrase, m.kind, m.code) for m in found] == [
        ("The warrior", "description", None), ("the Korvu's", "description", None),
        ("Borin", "name", "c2")]


@pytest.mark.parametrize("sentence", [
    "Your fist sweeps through the air, missing his guard by a hair.",
    "He is shouting something that makes the nearby crowd flinch.",
    "A collective intake of breath is followed by a panicked scuffle as people recoil.",
])
def test_what_read_as_a_person_on_the_corpus_and_is_not(sentence):
    """Three false mentions from the first corpus pass (2026-09-28): a stance, a relative
    "that", and a description bridged over "as"."""
    phrases = [m.phrase.lower() for m in mentions.find(sentence, _cast())]
    assert "his guard" not in phrases
    assert "that makes the nearby crowd" not in phrases
    assert not any("scuffle" in p for p in phrases)


def test_a_shared_surname_beside_an_unknown_first_name_is_not_certain():
    """"the ostler, Lyraea Lyraxys" was settled as Aethorin Lyraxys, whose surname it
    shares (the corpus, 2026-09-28)."""
    cast = _cast({"ref": "c15", "name": "Aethorin Lyraxys", "true": "", "pc": False,
                  "what": "", "dead": False})
    found = mentions.find("In front of you, the ostler, Lyraea Lyraxys, is busy.", cast)
    assert [(m.phrase, m.code) for m in found if m.kind == "name"] == [("Lyraxys", None)]
    assert [m.code for m in mentions.find("Aethorin Lyraxys nods.", cast)] == ["c15"]


# --- step 3: one call labels ---------------------------------------------------------------

class _Scene:
    def __init__(self, cast):
        self.cast = cast


def _attribute(text, answers, monkeypatch, cast=None):
    from gm import client

    monkeypatch.setattr(mentions, "ENABLED", True)
    monkeypatch.setattr(mentions, "people", lambda scene: cast or _cast())
    seen = {}

    def chat(messages, model, host, **kw):
        seen["schema"], seen["messages"] = kw["schema"], messages
        return client.Reply(json.dumps(answers), 0.1, model)

    return mentions.attribute(text, _Scene(cast), acting=BORIN, chat=chat), seen


def test_the_label_is_an_enum_of_the_people_here_and_nobody(monkeypatch):
    a, seen = _attribute("The warrior lunges. The crowd gasps.",
                         {"m1": "c2", "m2": "nobody"}, monkeypatch)
    schema = seen["schema"]
    assert schema["required"] == ["m1", "m2"]
    assert schema["properties"]["m1"]["enum"] == ["pc", "c2", "nobody"]
    assert [m.ref for m in a.mentions] == ["c2", None]
    assert "[m1: The warrior]" in seen["messages"][-1]["content"]


def test_with_the_labeller_off_names_still_settle_and_nothing_is_called(monkeypatch):
    """The suite runs with it off (tests/conftest.py); the code's answers still hold,
    and every check falls back to its guess for the rest."""
    monkeypatch.setattr(mentions, "ENABLED", False)
    monkeypatch.setattr(mentions, "people", lambda scene: _cast())
    a = mentions.attribute("Borin grunts. The warrior lunges.", _Scene(None),
                           chat=lambda *a, **k: pytest.fail("the labeller was called"))
    assert [(m.phrase, m.ref) for m in a.mentions] == [("Borin", "c2"),
                                                      ("The warrior", None)]
    assert not a.labelled


def test_a_name_the_sentence_means_for_somebody_else_is_misnamed(monkeypatch):
    """"Kesst Vayr's momentum carries it past you" — the words name the player, the
    sentence is about the enemy. Written by our own backstop in 2026-09-27's audit."""
    a, _ = _attribute("Kesst Vayr's momentum carries it past you.", {"m1": "c2"},
                      monkeypatch)
    assert [(m.phrase, m.code, m.model) for m in a.misnamed()] == [
        ("Kesst Vayr's", "pc", "c2")]


# --- stage 2: the checks read it -----------------------------------------------------------

KORVU = ("The Korvu lunges forward, its massive frame colliding with yours as it pushes "
         "past your shoulder. It ignores your presence entirely, trampling through your "
         "space to close the distance.")


def test_wrong_actor_no_longer_flags_the_korvu_when_the_korvu_is_borin(monkeypatch):
    """Live 2026-09-27, Borin's overrun: the beat was the right way round and was
    flagged — and rewritten — because "the Korvu" is not a word of "Borin Lyraxys"."""
    assert narration.wrong_actor(KORVU, BORIN, PC)          # the old guess, still there
    a, _ = _attribute(KORVU, {"m1": "c2"}, monkeypatch)
    assert a.mentioned_in(KORVU, "c2") is True
    assert narration.wrong_actor(KORVU, BORIN, PC, named=True) == []


def test_the_attribution_can_only_clear_wrong_actor_never_arm_it():
    turned = "You weave through the panicked crowd and close the distance to the door."
    assert narration.wrong_actor(turned, BORIN, PC, named=None)
    assert narration.wrong_actor(turned, BORIN, PC, named=False)


def test_a_living_thug_is_not_cut_for_a_dead_one_of_the_same_word():
    """docs/wrong-actor.md: two actors named "thug", one dead; the living one's groan
    on his own turn was cut as a dead man walking."""
    text = "The thug groans and drags himself toward the door."
    kept, cut = narration.cut_dead_men_walking(text, ["thug"])
    assert cut, "the old cut still fires on the word alone"
    kept, cut = narration.cut_dead_men_walking(text, ["thug"],
                                               spare=lambda s, w: True)
    assert kept == text and cut == []


def test_the_beast_is_swapped_for_the_player_only_when_it_means_the_player():
    text = "The thug's swing goes wide, and the beast steps inside his guard."
    swapped, beasts = narration.creature_nouns_for_pc(
        text, PC, True, whose=lambda s, w: "pc")
    assert "Kesst Vayr steps inside" in swapped and beasts == ["beast"]
    kept, beasts = narration.creature_nouns_for_pc(
        text, PC, True, whose=lambda s, w: "c2")
    assert kept == text and beasts == []


def test_an_apposition_names_the_man_the_attribution_says_it_is():
    """The head word "man" belongs to two unnamed men; the head-word guess took the
    first. The attribution names the right one."""
    from gm import judgement
    from rules.bestiary import instantiate
    from rules.engine import Scene

    s = Scene(location_id="t")
    pc = instantiate("guildhand", scene=s, name=PC)
    pc.kind = "pc"
    s.add(pc)
    first = instantiate("guildhand", scene=s, name="man by the door")
    second = instantiate("guildhand", scene=s, name="man at the bar")
    s.add(first)
    s.add(second)
    beat = "The man—Korgath Varn—takes a slow pull of his ale."
    got = judgement.apply_introductions(s, beat, "I look at him",
                                        whose=lambda sentence, words: second.ref)
    assert got == [(second.ref, "Korgath Varn")]
    assert first.name == "man by the door"


# --- stage 3: a name on the wrong person, rewritten ----------------------------------------

def _agent():
    from gm import agent as agent_mod
    from rules.bestiary import instantiate
    from rules.dice import Dice
    from rules.engine import Engine, Scene
    from rules.sheet import load_pc

    class _World:
        name, secret, premise, entities = "Testholme", "", {}, {}
        unwritten, chronology, factions = [], [], []

        def ancestors(self, _):
            return []

    s = Scene()
    s.add(load_pc("fixtures/pc-kesst.json"))
    s.add(instantiate("thug", scene=s, name=BORIN))
    return agent_mod, agent_mod.GMAgent(_World(), Engine(s, Dice(seed=1)))


def test_the_misnamed_sentence_is_rewritten_when_the_rewrite_holds(monkeypatch):
    from gm import client

    agent_mod, gm = _agent()
    borin_ref = next(r for r, a in gm.engine.scene.actors.items() if a.name == BORIN)
    sentence = "The strike misses, and Kesst Vayr's momentum carries it past you."
    att = Attribution(mentions=[Mention("m1", sentence, "Kesst Vayr's", "name",
                                        code="pc", model=borin_ref)])
    monkeypatch.setattr(agent_mod.client, "chat", lambda m, model, *a, **k: client.Reply(
        json.dumps({"s1": "The strike misses, and Borin's momentum carries him past you."}),
        0.1, model))
    text, notes, attempts = gm._repair_misnamed(sentence + " You stand firm.", att)
    assert text == "The strike misses, and Borin's momentum carries him past you. You stand firm."
    assert "rewritten" in notes[0] and len(attempts) == 1


def test_a_rewrite_that_keeps_the_wrong_name_leaves_the_sentence_and_says_so(monkeypatch):
    """No mechanical swap under it: the flag is the labeller's word against the name's,
    and a swap on a wrong flag writes the wrong name — `creature_nouns_for_pc`'s fault."""
    from gm import client

    agent_mod, gm = _agent()
    borin_ref = next(r for r, a in gm.engine.scene.actors.items() if a.name == BORIN)
    sentence = "Kesst Vayr's momentum carries it past you."
    att = Attribution(mentions=[Mention("m1", sentence, "Kesst Vayr's", "name",
                                        code="pc", model=borin_ref)])
    monkeypatch.setattr(agent_mod.client, "chat", lambda m, model, *a, **k: client.Reply(
        json.dumps({"s1": "Kesst Vayr's weight carries it past you."}), 0.1, model))
    text, notes, _ = gm._repair_misnamed(sentence, att)
    assert text == sentence
    assert "left as written" in notes[0]


# --- the record ---------------------------------------------------------------------------

def test_each_groomed_beat_is_logged_and_nothing_reaches_the_page():
    from play.views import _log_mentions

    class C:
        turn_log: list = []

    class Agent:
        mention_rows = [Attribution(mentions=[Mention("m1", "The warrior lunges.",
                                                      "The warrior", "description",
                                                      model="c2")]).as_log()]

    c, agent = C(), Agent()
    _log_mentions(c, agent)
    assert c.turn_log[0]["kind"] == "mentions" and c.turn_log[0]["labelled"] == 1
    assert agent.mention_rows == []
