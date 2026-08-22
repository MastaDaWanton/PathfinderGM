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

# One example per shape the GM actually needs. Demonstration, not description — and the
# *length* is as much of the demonstration as the content.
#
# Measured, on the prompt these replaced. The eight narrations here used to average 102
# characters and the longest was 158; against 3,863 characters of briefing that is an
# instruction-to-demonstration ratio of 4.7 : 1. Live output came back at a mean of 81
# characters — "The air inside is stale, thick with the smell of parchment and ink." — and
# two of three turns were visibly paraphrasing these examples rather than the scene. The
# model was not failing. It was copying what it had been shown, faithfully.
#
# That is the World Bible lesson in its natural habitat: instruction volume loses to
# demonstration volume, and the fix is the ratio rather than the wording. Each narration
# below now does four things — picks up what just happened, puts the player somewhere with
# their senses, lets the world push back, and hands the turn over with a real question —
# and the four are *shown* rather than listed, because a prompt that lists them produces
# four dutiful paragraphs in that order every single time.
EXAMPLES = [
    {
        "player": "I wait for the lamp to swing away, then go over the wall.",
        "reply": {
            "narration": (
                "You have been behind the water butt long enough that the rain has found "
                "the seam of your collar and started working its way down. Above the yard "
                "the watch-lamp swings out on its chain, drags a wedge of wet light across "
                "the flagstones, and begins the slow pull back. In the doorway beneath it "
                "a guildhand shifts his weight from one foot to the other and blows into "
                "his cupped hands; the sap on his belt is loose on its cord, and he has "
                "not looked up in some while. The wall is eight feet of slick masonry with "
                "a hand's width of ledge along the top, and the light will be back across "
                "it in about as long as it takes to breathe twice. The lamp is at the far "
                "end of its arc now. What do you do?"
            ),
            "suggestions": [
                "Go now, while the lamp is away",
                "Wait for the guildhand to turn his back as well",
                "Follow the wall along and look for a darker stretch",
            ],
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
    # A turn with no mechanics is still a scene. This one used to be 119 characters and
    # taught the model that conversation is where the prose stops.
    {
        "player": "I ask him who pays for the windcatchers.",
        "reply": {
            "narration": (
                "He does not answer straight away. He turns the cup in his hands instead, "
                "twice around, and looks at the ring it has left on the counter. Somewhere "
                "behind him a shutter is banging in the wind off the terraces and nobody "
                "has got up to fix it. 'The guild pays,' he says at last, in the flat tone "
                "of a man giving you a sentence he was handed. 'The guild has always paid.' "
                "Then his eyes come up and hold yours a moment too long, and flick past "
                "your shoulder to the door, and back. Whatever the true answer is, he has "
                "just decided you are the kind of trouble that might make him say it. Do "
                "you press him, or let it lie?"
            ),
            "suggestions": [
                "Press him on who really pays",
                "Let it go and ask about something else",
                "Look at whatever he glanced at by the door",
            ],
            "intents": [{"op": "narrate_only", "because": "he is only talking"}],
        },
    },
    {
        "player": "I've had enough of this. I draw and go for him.",
        "reply": {
            "narration": (
                "The talking is over and the whole yard seems to know it a half-second "
                "before he does. Your rapier comes out of the scabbard with a note that "
                "carries off the wet walls, and the sound turns two heads at the far gate. "
                "He gets a hand to his own hilt, but he is still half-turned towards the "
                "man he was speaking to, weight on the wrong foot, and there is a crate at "
                "his heel he has forgotten about. Rain runs off the lamp above and makes a "
                "curtain of light between the two of you. He has not got the blade clear "
                "yet. How do you come at him?"
            ),
            "suggestions": [
                "Go straight in before he can set his feet",
                "Drive him back over the crate",
                "Give him one last chance to stand down",
            ],
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
            "narration": (
                "You drop your weight and go low, under the arc of his swing, close enough "
                "to smell the wine on him. The flagstones are running with rain and his "
                "boots have no more grip than yours do. Your leading foot hooks in behind "
                "his ankle and takes his heel off the ground; he grabs for the doorframe, "
                "misses it by the width of a hand, and his free arm comes round hard "
                "towards the side of your head to take you down with him. Both of you are "
                "committed now. What do you do with the moment?"
            ),
            "suggestions": [
                "Put him down and step clear",
                "Ride him to the ground and pin the arm",
                "Twist away from the swing as he falls",
            ],
            "intents": [{
                "op": "attack", "actor": "pc", "target": "c1",
                "because": "she wants him on the ground, not dead",
                "params": {"manoeuvre": "trip"},
            }],
        },
    },
    # The player says what their character does; who is in the yard is the GM's to
    # decide. An earlier version of this example had the player declaring that two
    # bravos arrive, which taught exactly the wrong division of authority — and the app
    # then honoured it, reading the enemy count out of the player's sentence.
    #
    # The example that replaced it shows the right shape: the player commits to an
    # action, and the GM decides who is there to meet it.
    {
        "player": "I've been followed. I put my back to the wall and draw.",
        "reply": {
            "narration": (
                "You get the wall behind you — cold, and slick, and running with water from "
                "the gutter above — and the footsteps that have been keeping your pace "
                "since the bridge stop keeping it. Two shapes come away from the dark at "
                "the mouth of the alley, unhurried, taking their time about it because "
                "there is nowhere behind you for them to hurry towards. One of them lets a "
                "sap swing loose on its cord and it knocks twice against his thigh as he "
                "comes. The other says nothing at all, and fans wide to your off side "
                "where the light does not reach. The alley is nine feet across and there is "
                "a stack of empty barrels at your left shoulder. Which of them do you watch?"
            ),
            "suggestions": [
                "Watch the quiet one going wide",
                "Put the barrels between you and the wide man",
                "Speak first — ask who sent them",
            ],
            "intents": [
                {"op": "spawn", "because": "the guild does not send one man",
                 "params": {"template": "thug", "count": 2}},
            ],
        },
    },
    # Measured: the player broke off and ran, the GM narrated them getting clear — and
    # left the encounter running, so the thug went on hitting a character who was
    # supposed to be three streets away. Then the rest that followed was refused because
    # a fight was still going on. Getting away has to actually end the fight.
    {
        "player": "I break off and run for the lower quarter until nobody is following me.",
        "reply": {
            "narration": (
                "You break off mid-step, go over the low wall at the end of the yard, and "
                "drop into the run of alleys behind the tannery where the ground goes down "
                "towards the water. For a while there is shouting behind you, and then only "
                "one voice, and then the slap of your own boots and the blood in your ears. "
                "By the third turning the lower quarter has taken you in — washing strung "
                "between the upper storeys, a dog barking itself hoarse behind a gate, the "
                "river smell coming up strong. You stop under an archway with your hands on "
                "your knees. Behind you there is nothing but rain on stone. You have lost "
                "them, and the better part of an hour with them. Where do you go now?"
            ),
            "suggestions": [
                "Find somewhere out of the wind and rest",
                "Double back and see who came looking",
                "Head for the water while it is still dark",
            ],
            "intents": [
                {"op": "end_encounter", "because": "she is away and they have lost her"},
                {"op": "advance_time", "because": "the run across the quarter",
                 "params": {"amount": 20, "unit": "minute"}},
            ],
        },
    },
    # And the other half: rest is what puts hit points back, and the GM has to reach for
    # it when the player sleeps rather than narrating a night and healing nobody.
    {
        "player": "I find a doorway out of the wind and sleep until morning.",
        "reply": {
            "narration": (
                "The doorway is dry, more or less, and deep enough that the wind goes past "
                "the mouth of it instead of into it. You get your back into the corner "
                "where the two stones meet and your coat over you, and for a long time you "
                "listen to the city doing what it does at night — a cart somewhere on the "
                "cobbles, a woman laughing two streets over, the gutters emptying "
                "themselves. The ache under your ribs settles into something you can sleep "
                "through. When you open your eyes the sky over the roofline has gone the "
                "colour of dirty milk and the bells are starting. It is morning, and "
                "nobody found you in the night. What is the first thing you do?"
            ),
            "suggestions": [
                "Check your gear before you move",
                "Go straight to the counting house",
                "Find something to eat and listen to the street",
            ],
            "intents": [
                {"op": "rest", "actor": "pc", "because": "a night out of the weather",
                 "params": {"kind": "night"}},
            ],
        },
    },
    # Healing that is not sleeping. Without an example the GM narrates a potion working
    # and emits nothing, so the character walks away from the scene as hurt as they
    # entered it — the same failure `rest` was added to fix, in a different costume.
    {
        "player": "I dig the flask out of my coat and drink whatever is left in it.",
        "reply": {
            "narration": (
                "The flask has been digging into your ribs since the yard, and there is "
                "less in it than you hoped — a swallow and a half, gone warm from being "
                "carried. It goes down like a mouthful of hot coins. For a moment nothing, "
                "and then the grip under your ribs eases by degrees and the shivering in "
                "your hands starts to settle. Out in the street somebody is going door to "
                "door, three knocks each time, working their way along. The flask is empty "
                "now and you are steadier than you were. Do you move, or wait and see who "
                "is knocking?"
            ),
            "suggestions": [
                "Move before they reach this door",
                "Stay still and listen",
                "Look for another way out of the room",
            ],
            "intents": [
                {"op": "heal", "actor": "pc", "because": "the last of the draught",
                 "params": {"amount": "1d8+1"}},
            ],
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

Put the player in the place. Pick up from what just happened, give them something to see
and hear and feel, let the world act back at them, and hand the turn over. A single line
of scene-setting is not a turn — look at how long the examples are, and match them.

End by giving the player a real choice to make, and offer two or three things they might
do. They are suggestions, not a menu: the player may do anything they like.

Write to the player as "you". Name only the people and places listed below; if you need
someone new, describe them without a name. The examples show you the shape and the length
of a reply, not its words — never repeat a phrase from them.

The player says only what their character does. Who else is present, what they do, and
what the world does are yours to decide — decide them from the world below, and do not
take the player's word for what is there.

Reply with a JSON object:
{"narration": "...", "suggestions": ["...", "..."], "intents": [...]}.

People and creatures are named by ref, never by name. The refs that exist are listed
below; there are no others. If you want someone new in the scene, use the spawn op.

Difficulty is a word from this list, not a number: %s.
A circumstance is "favorable" or "unfavorable", nothing else.
To grab, shove, trip, disarm or break something rather than wound it, use an attack with
a manoeuvre: %s.
When the fighting stops — they run, they yield, the player gets clear — end it with
{"op": "end_encounter"}. Nobody can rest while a fight is still running.
When the player sleeps or makes camp, use {"op": "rest", "params": {"kind": "night"}}
— that is how wounds heal. "bed rest" is a full day and night and heals twice as much.
A potion, a poultice, a spell that mends: {"op": "heal", "params": {"amount": "1d8+1"}}.
Something that wards a person rather than mending them — a blessing, a shield of force —
grants temporary hit points: {"op": "temp_hp", "params": {"amount": "2d6",
"source": "the ward"}}. Never narrate a wound closing without one of these; if you do,
the character walks away as hurt as they arrived and the player will see it on the sheet.
Poison, disease, or anything that saps a body rather than wounding it damages a score:
{"op": "ability_damage", "params": {"ability": "con", "amount": "1d4"}}. Add
"drain": true only when the loss is permanent.
When the party moves onto different ground, say so: {"op": "travel", "params":
{"biome": "forest"}}. The biomes are urban, grassland, farmland, forest, jungle, swamp,
hills, mountain, desert, tundra, coast, underground, ruins, planar. What can be found by
searching depends entirely on it, so it has to be right before anyone looks.
When the player searches the ground for herbs or useful growing things:
{"op": "forage", "actor": "pc"}. The engine rolls against what actually grows there and
puts what turns up in their satchel — do not decide what they find.
Foraging, harvesting or brewing at a world class — a craft the character works at rather
than a skill they roll: {"op": "craft", "params": {"track": "herbalist", "recipe":
"woundwort styptic", "tier": "common", "stages": 2, "risky": false}}. `stages` is how many
methods the work passed through, `risky` if the harvesting was dangerous, and
"failed": true when it spoils — a ruined batch still teaches something. The character does
not need to have chosen the class; doing the work is how they take it up.
Acid, and anything that eats what a person is carrying:
{"op": "item_damage", "params": {"amount": "2d6", "type": "acid"}} — name an "item" for
one thing, or leave it out and everything they carry takes it.
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
                f"  {ref} — {actor.name}, the player's character. Narrate to them as "
                f"'you'; when someone speaks about them, {actor.pronouns}. "
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

Carry on from what you already narrated; do not restate it. Write to the player as "you".

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


NPC_TURN_BRIEFING = """It is this creature's turn in the fight. Act for it.

Decide what it does from what it is and what has just happened to it — a frightened
commoner runs, a paid guard fights, a wounded animal bolts. Then say it as intent.

Reply with a JSON object: {"narration": "...", "intents": [...]}, exactly as before.
Your narration is the wind-up only; the engine decides whether anything lands.

If the creature does something with no mechanics — surrenders, flees, shouts for help —
say so with a single {"op": "narrate_only"} intent."""


# The player-turn prompt carries five worked examples; this one carried none, and the
# model answered with intents that were strings rather than objects on nearly every NPC
# turn — "intent 0 is not an object", three attempts in a row, so the creature stood
# there hesitating while the player was attacked by nobody. Same lesson, second place it
# had to be learned: demonstration, not instruction.
NPC_EXAMPLES = [
    {
        "ask": "Round 2. It is c1 (a thug) turn.\nThey are unhurt and their conditions "
               "are: none.\nWhat does c1 do?",
        "reply": {
            "narration": "The nearer one shifts his grip on the sap and comes in low.",
            "intents": [{"op": "attack", "actor": "c1", "target": "pc",
                         "because": "he is paid to put her down, not to kill her"}],
        },
    },
    {
        "ask": "Round 4. It is c2 (a guildhand) turn.\nThey are badly hurt and their "
               "conditions are: shaken.\nWhat does c2 do?",
        "reply": {
            "narration": "He looks at the blood on his sleeve, and at the gate, and "
                         "decides the gate is closer.",
            "intents": [{"op": "narrate_only",
                         "because": "he is not paid enough to die on a gate"}],
        },
    },
]


def npc_turn_messages(briefing_scene: str, history: list[dict], ref: str,
                      actor, round_no: int) -> list[dict]:
    hp_note = "unhurt"
    if actor.hp < actor.hp_max:
        share = actor.hp / max(1, actor.hp_max)
        hp_note = ("badly hurt" if share <= .34 else
                   "bloodied" if share <= .67 else "lightly hurt")
    conditions = ", ".join(c.name.lower() for c in actor.conditions) or "none"
    messages = [{"role": "system", "content": NPC_TURN_BRIEFING + "\n\n" + briefing_scene}]
    for ex in NPC_EXAMPLES:
        messages.append({"role": "user", "content": ex["ask"]})
        messages.append({"role": "assistant", "content": json.dumps(ex["reply"])})
    messages.append({"role": "user", "content":
        f"Round {round_no}. It is {ref} ({actor.name}) turn.\n"
        f"They are {hp_note} and their conditions are: {conditions}.\n"
        f"What does {ref} do?"})
    return messages


REPAIR_BRIEFING = """Rewrite the sentence you are given so that it no longer states how a
roll turned out. Keep everything else about it — the voice, the detail, the length.

Reply with a JSON object: {"sentence": "..."}."""


def repair_messages(sentence: str, why: str) -> list[dict]:
    return [
        {"role": "system", "content": REPAIR_BRIEFING},
        {"role": "user", "content": f"This sentence {why}:\n\n{sentence}"},
    ]


# "Keep everything else — the events, the voice, the length" was right for every finding
# that existed when it was written, and became wrong the moment one of the findings *was*
# the length: it told the model to hold a one-line narration at one line while being asked
# to turn it into a scene.
NARRATION_REPAIR_BRIEFING = """Rewrite the passage you are given so that it no longer has
the problem described. Keep the events and the voice. Change the length only if the
problem is about length.

You are the Game Master, writing to the player as "you". Do not say how any roll turned
out.

Reply with a JSON object: {"narration": "..."}."""


def narration_repair_messages(text: str, complaint: str) -> list[dict]:
    return [
        {"role": "system", "content": NARRATION_REPAIR_BRIEFING},
        {"role": "user", "content": complaint + "\n\nThe passage:\n" + text},
    ]
