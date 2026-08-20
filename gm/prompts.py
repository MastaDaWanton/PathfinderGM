"""What the GM agent is told.

Two lessons from World Bible shape everything here:

  * **Instruction volume loses to demonstration volume.** 368 characters of "write about
    anatomy" against 6,469 characters of social prose produced more social prose. So the
    briefing is short and the *examples* carry the weight.

  * **Ground every name.** Given freedom a model invents places and people, then treats
    them as settled fact. Every name the GM is allowed to use is passed in, and the ref
    registry rejects anything else.

Nothing in here tries to make the model obey the outcome rule by asking nicely. That is
checked in code afterwards (rules/intents.find_outcome_claims), because asking is the
class of fix that failed repeatedly.
"""
from __future__ import annotations

import json

from rules.tables import DC_BANDS, MANEUVERS

# One example per shape the GM actually needs. Demonstration, not description.
EXAMPLES = [
    {
        "player": "I wait for the lamp to swing away, then go over the wall.",
        "reply": {
            "narration": (
                "The lamp on its chain sweeps the yard wall, pauses at the top of its "
                "arc, and starts back. Behind it a guildhand leans in the doorway, "
                "half-asleep over a cup."
            ),
            "intents": [{
                "op": "check",
                "actor": "pc",
                "because": "going over the wall while the lamp is away",
                "params": {
                    "skill": "stealth",
                    "opposed_by": {"ref": "c1", "skill": "perception"},
                    "circumstance": {"value": "favorable",
                                     "why": "the lamp is at the far end of its swing"},
                },
                "visibility": "player",
            }],
        },
    },
    {
        "player": "I ask him who pays for the windcatchers.",
        "reply": {
            "narration": (
                "He turns the cup in his hands. 'The guild pays,' he says, in the tone "
                "of a man repeating something he was told to say.'"
            ),
            "intents": [{"op": "narrate_only", "because": "he is only talking"}],
        },
    },
    {
        "player": "I've had enough of this. I draw and go for him.",
        "reply": {
            "narration": "The rapier comes free of its scabbard with a sound the whole yard hears.",
            "intents": [
                {"op": "begin_encounter", "because": "she has drawn on him",
                 "params": {"sides": {"pc": ["pc"], "them": ["c1"]}}},
                {"op": "attack", "actor": "pc", "target": "c1",
                 "because": "she has run out of talking"},
            ],
        },
    },
    # Without this one the model resolved "I sweep his legs out from under him" as an
    # ordinary rapier attack: it had no way to know a manoeuvre was available, because
    # nothing had shown it one. Demonstration, not another paragraph of instruction.
    {
        "player": "I sweep his legs out from under him.",
        "reply": {
            "narration": "She drops her weight and hooks a boot behind his ankle.",
            "intents": [{
                "op": "attack", "actor": "pc", "target": "c1",
                "because": "she wants him on the ground, not dead",
                "params": {"manoeuvre": "trip"},
            }],
        },
    },
]


BRIEFING = """You are the Game Master of a Pathfinder 1st Edition game set in a world that
already exists. You narrate and you voice everyone in the scene.

You do not decide what happens mechanically. When the fiction calls for a roll, you say
what it calls for as an intent, and the rules engine rolls it and tells you the result.
You then narrate the result you are handed.

Your narration covers the wind-up only: what is true no matter how the dice land. Never
the landing.

Reply with a JSON object: {"narration": "...", "intents": [...]}.

People and creatures are named by ref, never by name. The refs that exist are listed
below; there are no others. If you want someone new in the scene, use the spawn op.

Difficulty is a word from this list, not a number: %s.
A circumstance is "favorable" or "unfavorable", nothing else.
To grab, shove, trip, disarm or break something rather than wound it, use an attack with
a manoeuvre: %s.
If the turn needs no mechanics at all, emit a single {"op": "narrate_only"} intent.
""" % (", ".join(DC_BANDS), ", ".join(sorted(MANEUVERS)))


def scene_brief(world, scene, location, recent_events=None) -> str:
    """The world facts the GM may draw on this turn.

    A budget, not a dump. This is the thing that decides whether a local model answers in
    seconds or in a minute, and whether long campaigns stay coherent.
    """
    lines = [f"WORLD: {world.name}."]
    if world.premise:
        lines.append("Premise: " + "; ".join(f"{k} — {v}" for k, v in world.premise.items()))

    if location:
        lines.append(f"\nHERE: {location.name}, a {location.scale or 'place'}.")
        for key in ("Urban Life", "Social Classes", "Architecture", "Governance",
                    "Formal Power", "Shadow Power", "Tension", "Daily Norms"):
            if location.fact(key):
                lines.append(f"  {key}: {location.fact(key)}")
        parents = [e.name for e in world.ancestors(location.id) if e.kind != "WORLD"]
        if parents:
            lines.append(f"  Within: {', '.join(parents)}")

    lines.append("\nWHO IS HERE (these refs are the only ones that exist):")
    for ref, actor in scene.actors.items():
        if actor.is_pc:
            lines.append(
                f"  {ref} — {actor.name}, the player's character. "
                f"{actor.heritage} {actor.class_data.get('name', '')} {actor.level}, "
                f"{actor.hp}/{actor.hp_max} hp."
            )
        else:
            note = actor.notes.split(".")[0] if actor.notes else ""
            lines.append(f"  {ref} — {actor.name}. {note}.")

    if recent_events:
        lines.append("\nWHAT THIS PLACE REMEMBERS:")
        for e in recent_events:
            year = f"{e.year}" if e.year is not None else "undated"
            lines.append(f"  {year}: {e.name} — {e.summary}")

    if world.secret:
        lines.append(
            f"\nSECRET (almost nobody in the world knows this; never state it outright): "
            f"{world.secret}"
        )
    return "\n".join(lines)


def call_one_messages(briefing_scene: str, history: list[dict], player_input: str) -> list[dict]:
    messages = [{"role": "system", "content": BRIEFING + "\n\n" + briefing_scene}]
    for ex in EXAMPLES:
        messages.append({"role": "user", "content": ex["player"]})
        messages.append({"role": "assistant", "content": json.dumps(ex["reply"])})
    messages.extend(history)
    messages.append({"role": "user", "content": player_input})
    return messages


CONSEQUENCE_BRIEFING = """You are the Game Master, narrating what just happened.

The rules engine has resolved it. Below is what it decided. Narrate exactly that in two or
three sentences of prose — no more. Do not add a further roll, do not contradict it, and
do not give any numbers.

Write it as fiction, not as a report."""

# The briefing above already said "you are the Game Master", and the model still wrote
# "As I waited for the perfect moment... my chance arrived" — it took the player's own
# first-person input as the voice to continue. Instruction volume loses to demonstration
# volume, so the person is fixed by showing it once rather than by saying it twice.
CONSEQUENCE_EXAMPLE = {
    "user": (
        "The player said: I go over the wall while he is not looking.\n\n"
        "You had already narrated: The lamp sweeps the yard and starts back.\n\n"
        "What the engine decided:\n"
        "- Kesst Vayr beats the guildhand on the gate's perception by 10.\n"
    ),
    "assistant": (
        "You are over before the lamp comes back, and the drop on the far side is "
        "shorter than it looked. Behind you the guildhand shifts his weight and says "
        "something to nobody, and goes on watching the light."
    ),
}


def call_two_messages(narration: str, tells: list[str], because: list[str],
                      player_input: str) -> list[dict]:
    facts = "\n".join(f"- {t}" for t in tells if t)
    why = "\n".join(f"- {b}" for b in because if b)
    content = (
        f"The player said: {player_input}\n\n"
        f"You had already narrated: {narration}\n\n"
        f"What the engine decided:\n{facts}\n"
    )
    if why:
        content += f"\nWhy it was rolled:\n{why}\n"
    return [
        {"role": "system", "content": CONSEQUENCE_BRIEFING},
        {"role": "user", "content": CONSEQUENCE_EXAMPLE["user"]},
        {"role": "assistant", "content": CONSEQUENCE_EXAMPLE["assistant"]},
        {"role": "user", "content": content},
    ]


REPAIR_BRIEFING = """Rewrite the sentence you are given so that it no longer states how a
roll turned out. Keep everything else about it — the voice, the detail, the length.

Reply with a JSON object: {"sentence": "..."}."""


def repair_messages(sentence: str, why: str) -> list[dict]:
    return [
        {"role": "system", "content": REPAIR_BRIEFING},
        {"role": "user", "content": f"This sentence {why}:\n\n{sentence}"},
    ]
