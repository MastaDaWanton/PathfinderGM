"""The people here saw it, and somebody does something about it.

Reported with two screenshots, 2026-09-18, on 0.1.9. The player put a longsword through a
merchant's crates in the open — "i swing the longsword cutting reality apart in front of
me" — and got: "The stranger on the step watches the arc of your sword, his face unmoving,
and the crowd at the end of the street remains silent." Their verdict: "the world hardly
reacts to my very odd behaviour … like the model is afraid to interact with the PC first.
I'd argue it should be trying to interact with the PC as much as possible, verbally and
situationally."

Heat — the engine's note of what the bystanders just saw — was written for a killing and
nothing else, so nothing carried the sword through the crates into the next beat, and the
model, which continues what is in front of it, wrote the crowd as it had been: watching.
Now the acts a crowd sees just as well write heat with a kind, the brief asks for the
reaction that kind deserves, and a fresh beat in which nobody present acts or speaks is
sent back with the people named.
"""
from __future__ import annotations

from gm import interpret, judgement, narration
from rules.engine import Outcome, Scene


def _read(text, *actions):
    """The reader's reading of the player's line, as the turn would have cached it."""
    interpret.remember(text, {"question": False, "claims": [],
                              "actions": [dict(a) for a in actions]})
    return text


class _Body:
    def __init__(self, ref, name, *, pc=False, down=False):
        self.ref, self.name, self.is_pc, self.is_down = ref, name, pc, down
        self.hp = 10
        self.at = ""          # `Scene.actors` is everybody standing where the scene is


def _scene(*names):
    s = Scene()
    s.people = {"pc": _Body("pc", "Kesst", pc=True)}
    for i, n in enumerate(names, 1):
        s.people[f"c{i}"] = _Body(f"c{i}", n)
    return s


SILENT = ("The steel of your blade bites into the air. The sword meets the wood with a "
          "sharp crack of steel against timber, a few splinters flying into the mud. The "
          "stranger on the step watches the arc of your sword, his face unmoving, and the "
          "crowd at the end of the street remains silent. What do you do?")


def test_a_sword_through_the_crates_is_heat_of_its_own_kind():
    s = _scene("stranger", "merchant")
    said = _read("i swing the longsword at the crates in front of me",
                 {"act": "attack", "target": "the crates"})
    judgement.note_heat(s, [], said)
    assert s.heat["kind"] == "property" and s.heat["age"] == 0
    assert "goods" in s.heat["note"] and "onlookers" in s.heat["note"]
    brief = judgement.heat_brief(s)
    assert "WHAT THE CROWD JUST SAW" in brief and "objects out loud" in brief


def test_a_threat_is_heat_and_the_words_alone_are_none():
    """The reader's `threaten` is a threat the crowd sees. A drawn blade and a shout made
    heat by regex over the player's words until 2026-11-20 (against the owner's ruling
    that models read and code validates); the reader has no closed reading for either
    yet, so the words alone make none, whatever they say."""
    s = _scene("guard")
    judgement.note_heat(s, [], _read("Back off or I gut you.",
                                     {"act": "threaten", "target": "the guard"}))
    assert s.heat["kind"] == "threat"
    for words in ("I draw my sword and hold it low.",
                  "I shout at the top of my voice for everyone to get back."):
        s = _scene("guard")
        judgement.note_heat(s, [], _read(words, {"act": "talk"}))
        assert not s.heat


def test_an_attack_that_landed_is_violence_and_a_kill_is_still_a_killing():
    s = _scene("guard", "merchant")
    hit = Outcome(intent_id="i1", op="attack",
                  effects=[{"ref": "c1", "kind": "damage", "amount": 4}])
    judgement.note_heat(s, [hit], "I hit the guard.")
    assert s.heat["kind"] == "violence" and "attacked guard" in s.heat["note"]
    dead = Outcome(intent_id="i2", op="attack",
                   effects=[{"ref": "c1", "kind": "damage", "amount": 9},
                            {"ref": "c1", "kind": "condition", "condition": "dead"}])
    judgement.note_heat(s, [dead], "I finish him.")
    assert s.heat["kind"] == "killing" and "killed guard" in s.heat["note"]
    assert "running for the watch" in judgement.heat_brief(s)


def test_with_nobody_watching_there_is_no_heat():
    s = Scene()
    s.people = {"pc": _Body("pc", "Kesst", pc=True)}
    judgement.note_heat(s, [], _read("I smash the crates to splinters.",
                                     {"act": "attack", "target": "the crates"}))
    assert not s.heat


class _Foe(_Body):
    def has_state(self, tag):
        return tag == "attitude.hostile"


def test_the_foe_being_fought_is_no_crowd():
    """Playtest 2026-11-20 #23, shadow-0073: in the empty ruins the brief said "WHAT THE
    CROWD JUST SAW ... The people here react to it NOW" with only the ghoran being fought
    in PEOPLE HERE NOW — the foe counted as an onlooker of its own fight."""
    s = _scene()
    s.people["c3"] = _Foe("c3", "ghoran")
    hit = Outcome(intent_id="i1", op="attack",
                  effects=[{"ref": "c3", "kind": "damage", "amount": 12}])
    judgement.note_heat(s, [hit], "I strike the ghoran.")
    assert not s.heat and judgement.heat_brief(s) == ""


def test_the_line_goes_to_who_saw_it_and_goes_with_them():
    """The reaction is the witnesses' own, named; when they are gone, so is the line —
    the owner's ruins kept "killed second lizard in front of onlookers" six beats on with
    nobody but a broken construct there."""
    s = _scene("merchant")
    s.people["c3"] = _Foe("c3", "thug")
    hit = Outcome(intent_id="i1", op="attack",
                  effects=[{"ref": "c3", "kind": "damage", "amount": 4}])
    judgement.note_heat(s, [hit], "I hit the thug.")
    assert s.heat["seen_by"] == ["c1"]
    brief = judgement.heat_brief(s)
    assert "Seen by: merchant, and nobody else" in brief
    del s.people["c1"]          # the merchant runs off
    assert judgement.heat_brief(s) == "" and judgement.heat_seen(s) == {}
    s.people["c1"] = _Body("c1", "merchant", down=True)
    assert judgement.heat_brief(s) == ""


def test_a_heat_from_before_witnesses_were_kept_carries_to_nobody():
    s = _scene("merchant")
    s.heat = {"note": "the player just killed second lizard in front of onlookers",
              "age": 6, "kind": "killing"}
    assert judgement.heat_brief(s) == ""


def test_heat_cools_and_the_note_ages():
    s = _scene("guard")
    judgement.note_heat(s, [], _read("I kick the barrel over.",
                                     {"act": "attack", "target": "the barrel"}))
    for _ in range(judgement.HEAT_TURNS):
        judgement.note_heat(s, [], "I wait.")
    assert s.heat.get("age") == judgement.HEAT_TURNS
    judgement.note_heat(s, [], "I wait.")
    assert not s.heat


# --- the beat where nobody does anything --------------------------------------------------


def test_the_measured_beat_has_nobody_reacting():
    assert narration.nobody_reacts(SILENT, ("stranger", "merchant"))


def test_speech_or_an_acting_person_is_a_reaction():
    spoke = SILENT.replace("remains silent.", "remains silent. 'Oi!' the stranger shouts, "
                           "on his feet now. 'Those are Marrow's crates.'")
    assert not narration.nobody_reacts(spoke, ("stranger",))
    acted = SILENT.replace("watches the arc of your sword, his face unmoving",
                           "steps back off the step and reaches for the club at his belt")
    assert not narration.nobody_reacts(acted, ("stranger",))


def test_review_sends_a_silent_crowd_back_while_the_heat_is_fresh():
    heat = {"note": "the player just went at somebody's goods in the open — swing the "
                    "longsword at the crates — in front of onlookers", "age": 0,
            "kind": "property"}
    r = narration.review(SILENT, others=("stranger", "merchant"), heat=heat)
    f = next(f for f in r.findings if f.kind == "nobody-reacts")
    assert f.weight == 2
    assert "stranger, merchant" in f.fix_hint and "acts or speaks" in f.fix_hint
    # Cooled heat asks nothing; a beat with a reaction is left alone; no heat, no finding.
    assert "nobody-reacts" not in {
        f.kind for f in narration.review(SILENT, others=("stranger",),
                                         heat=dict(heat, age=3)).findings}
    spoke = SILENT.replace("remains silent.", "remains silent. 'Oi!' the stranger shouts.")
    assert "nobody-reacts" not in {
        f.kind for f in narration.review(spoke, others=("stranger",), heat=heat).findings}
    assert "nobody-reacts" not in {
        f.kind for f in narration.review(SILENT, others=("stranger",)).findings}


def test_the_finding_is_rewrite_only_and_out_of_fights():
    import inspect

    from gm import agent

    assert "nobody-reacts" in agent.GMAgent._NO_BACKSTOP
    src = inspect.getsource(agent.GMAgent.polish)
    assert "in_encounter" in src and "heat=" in src
