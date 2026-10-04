"""A companion's club stays a club: the face check reads a weapon as its carrier's.

Measured 2026-10-01 on the companions replay (scratch save: a young drover made from the
`guildhand` template — weapons ['club'], equipped 'club' — beside a thug carrying a sap and
a dagger; gemma-4-12B): in **4 of 15** companion wind-ups the groom's `face-changed` repair
rewrote "grips their club" into "grips their dagger" ("face-changed: 'They grip their club
tight...' -> 'They grip their dagger tight...'"), and the consequence prose on the
companion's turn swung "their sap" or "their dagger" while every tell said "with the club".

Not the stat block and not the prompt: the guildhand prints no attacks, and the drover's
turn prompt named the club and nothing else. The cause was `face_kept`. The wind-up said
"The young drover grips their club tightly, eyes darting between the thug and the nearest
exit", which names the thug, so `about(ctx, thug)` claimed it; the thug carries a sap and
a dagger, so "their club" was filed as the thug's face changing. The repair was told the
thug's face and wrote a dagger, and the re-check passed it because the thug does carry
one. On the outcome door every "swings their club at the thug" was filed the same way.
"""
from __future__ import annotations

from gm import companions, prompts
from gm.checks import face_kept

from _a_truth import WAY_IN, context, scene_at

# The third undirected timid wind-up of the replay, verbatim — the one that names the thug.
WIND_UP = ("The young drover grips their club tightly, eyes darting between the thug and "
           "the nearest exit. They stay low, hunkering down behind you to keep their back "
           "to the escape route.")


def _drover_and_thug():
    agent, _ = scene_at(WAY_IN, [("a young drover", "guildhand"), ("thug", "thug")])
    scene = agent.engine.scene
    drover = next(a for a in scene.actors.values() if a.name == "a young drover")
    thug = next(a for a in scene.actors.values() if a.name == "thug")
    for a in (drover, thug):
        a.described = True
        a.appearance = "Human: lean and sunburnt."
    return agent, drover, thug


def _flags(agent, text, door="turn"):
    return [f.detail for f in face_kept.find(context(agent, text, door=door))]


def test_the_scene_is_the_one_measured():
    _, drover, thug = _drover_and_thug()
    assert (drover.weapons, drover.equipped) == (["club"], "club")
    assert set(thug.weapons) == {"sap", "dagger"}


def test_the_drover_gripping_their_club_is_no_face_changed():
    """4 of 15 wind-ups had the club repaired into a dagger. Neither the plain sentence
    nor the replay's own — which names the thug — is a finding against anybody."""
    agent, _, _ = _drover_and_thug()
    assert _flags(agent, "The drover grips their club tightly.") == []
    assert _flags(agent, WIND_UP) == []


def test_the_drovers_blow_on_the_thug_is_no_face_changed():
    """The consequence prose came back swinging a sap; on the outcome door every
    "their club ... the thug" sentence was filed as the thug's face."""
    agent, _, _ = _drover_and_thug()
    for text in ("The young drover swings their club at the thug, and it cracks against "
                 "his shoulder.",
                 "The young drover lunges in, bringing their club down on the thug's arm."):
        assert _flags(agent, text, door="outcome") == [], text


def test_the_thug_alone_with_a_club_is_still_caught():
    """The fix reads a weapon as the carrier's only among the people the sentence is
    about: the thug named alone with a club he does not carry is still a changed face."""
    agent, _, _ = _drover_and_thug()
    found = _flags(agent, "The thug grips his club and comes at you.", door="outcome")
    assert found and "thug is described as carrying a club" in found[0]


def _weapons_named(messages, brief):
    named = set()
    for m in messages:
        text = m["content"].replace(brief, "")
        named |= {w.lower() for w in face_kept._SWORDISH.findall(text)}
    return named


def test_the_companions_turn_prompt_names_only_what_they_hold():
    """The guildhand prints no attacks, so "Their attacks, by weapon name" is absent and
    "In hand: the club" is the drover's only weapon. A companion example once read
    "lifts the club" for every companion — a club in the prompt of one holding a sap."""
    agent, drover, thug = _drover_and_thug()
    scene = agent.engine.scene
    brief = "THE SCENE BRIEF"
    for who, foe in ((drover, thug), (thug, drover)):
        msgs = prompts.npc_turn_messages(brief, [], who.ref, who, 1,
                                         companion=companions.turn_facts(scene, who, []),
                                         foe=(foe.ref, foe.name))
        named = _weapons_named(msgs, brief)
        held = face_kept._carried(who)
        assert named and all(face_kept._among(w, held) for w in named), (who.name, named)
    msgs = prompts.npc_turn_messages(brief, [], drover.ref, drover, 1)
    assert _weapons_named(msgs, brief) == {"club"}
