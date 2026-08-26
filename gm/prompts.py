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

from rules.intents import OPS as _OPS
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
# The worked examples used to cast real templates — a guildhand under the lamp, thugs in
# the alley, "c1 (a thug)" taking its NPC turn — and mid-bear-fight the model played the
# examples instead of the scene: the bear's turn narrated a grinning thug and his sap.
# So no example names an enemy type any more. They say {Current Enemy}, and the token is
# filled at build time with the creature actually there — a copied sentence now lands on
# the right actor instead of inventing a wrong one. Two tokens because grammar and data
# want different shapes: {Current Enemy} is a definite noun phrase mid-sentence ("the
# bear", "Ragnar"), {Current Enemy Kind} is the bare name for asks and spawn params.
ENEMY_TOKEN = "{Current Enemy}"
ENEMY_KIND_TOKEN = "{Current Enemy Kind}"


def _definite(name: str) -> str:
    """"bear" reads as "the bear" in prose; a proper name is already itself."""
    name = (name or "").strip()
    if not name:
        return "the stranger"
    if name[0].isupper() or name.lower().startswith("the "):
        return name
    return f"the {name}"


def fill_enemy(text: str, enemy: str | None) -> str:
    """Put the scene's actual opposition into an example's placeholder slots.

    With nobody declared — no fight on, an empty scene — the fill is "stranger", which
    is deliberately not a template and not a person: if the model copies it anyway, the
    prose says a stranger did something, which invents nobody in particular, and a
    copied spawn of it fails validation instead of conjuring a phantom thug.
    """
    kind = (enemy or "").strip() or "stranger"
    return text.replace(ENEMY_TOKEN, _definite(kind)).replace(ENEMY_KIND_TOKEN, kind)


EXAMPLES = [
    {
        "player": "I wait for the lamp to swing away, then go over the wall.",
        "reply": {
            "narration": (
                "You have been behind the water butt long enough that the rain has found "
                "the seam of your collar and started working its way down. Above the yard "
                "the watch-lamp swings out on its chain, drags a wedge of wet light across "
                "the flagstones, and begins the slow pull back. In the doorway beneath it "
                "{Current Enemy} shifts weight from one foot to the other and blows into "
                "cupped hands; the sap on his belt is loose on its cord, and he has "
                "not looked up in some while. The wall is eight feet of slick masonry with "
                "a hand's width of ledge along the top, and the light will be back across "
                "it in about as long as it takes to breathe twice. The lamp is at the far "
                "end of its arc now. What do you do?"
            ),
            "suggestions": [
                "Go now, while the lamp is away",
                "Wait for {Current Enemy} to turn away as well",
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
                {"op": "spawn", "because": "trouble like this does not come alone",
                 "params": {"template": "{Current Enemy Kind}", "count": 2}},
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
    # --- Variety, which is the point ---------------------------------------------------
    #
    # Eight examples covering eight situations gives every situation exactly one template,
    # and a model inclined to copy has nothing else to do with it. Measured on
    # qwen3-8b-heretic: three turns in five came back as whole example paragraphs, and not
    # even the paragraph belonging to the turn it was asked about — it reached for the
    # nearest one it had. Reframing them as foreign illustrations rather than as its own
    # prior replies changed nothing at all.
    #
    # So the fix is more of them, further apart. Several shapes per situation means no
    # single paragraph is "the answer" to anything, and the only thing left to generalise
    # from is the shape.
    {
        "player": "I follow the steps down and see where they come out.",
        "reply": {
            "narration": (
                "Eleven steps, and the eleventh is not there — your boot goes down through "
                "wet air and you catch yourself on the wall with your palm flat against "
                "something that gives slightly, like sacking. The stair opens into a cellar "
                "that smells of standing water and, under it, sweetly of rot. Light comes "
                "from a grating somewhere off to the right, enough to show you the floor is "
                "not floor: it is packed earth, and it has been dug over recently, and not "
                "carefully. Something has been buried here in a hurry. Behind you, up the "
                "steps, the door you came through swings a hand's width on its hinge and "
                "stops. Where do you look first?"
            ),
            "suggestions": [
                "Dig where the earth is freshest",
                "Get the door open again before it shuts",
                "Feel along the wall for what your hand touched",
            ],
            "intents": [{"op": "narrate_only", "because": "nothing has forced a roll yet"}],
        },
    },
    {
        "player": "I go through his desk while he's out of the room.",
        "reply": {
            "narration": "You have about as long as it takes a man to cross a yard and "
                         "come back. The top drawer is unlocked and holds nothing worth "
                         "locking; the second one sticks, and when it comes it comes with "
                         "a crack that you feel in your teeth. Inside: three sticks of "
                         "sealing wax, a purse with almost nothing in it, and a bundle of "
                         "letters tied with a bootlace, the top one addressed in a hand "
                         "you have seen before and cannot place. Out in the yard, the "
                         "talking has stopped. How much do you take?",
            "suggestions": [
                "Take the letters and shut the drawer",
                "Read the top one where you stand",
                "Put it all back and get away from the desk",
            ],
            "intents": [{
                "op": "check", "actor": "pc",
                "because": "going through a man's desk with him a yard away",
                "params": {"skill": "sleight of hand",
                           "circumstance": {"value": "unfavorable",
                                            "why": "he is coming back"}},
                "visibility": "player",
            }],
        },
    },
    {
        "player": "I tell her I can get it for her, but I want the name first.",
        "reply": {
            "narration": (
                "She lets that sit. The fire has burned down to the point where it is more "
                "sound than light, and she does not look at you while she thinks — she "
                "looks at the shutter, which is closed, and at the door, which is not. "
                "'A name,' she says. 'You understand that a name is the only thing in this "
                "room that cannot be given back.' Her rings go round once on her finger. "
                "'I will give you one. And if I hear it anywhere but from your mouth to "
                "mine, I will not need to send anyone after you — I will simply say where "
                "you were on the night of the fire, and let the guild do it.' She waits, "
                "and the offer is on the table between you, and it has a price on it. Do "
                "you take it?"
            ),
            "suggestions": [
                "Take the name and the risk with it",
                "Ask what she wants in return, exactly",
                "Walk away from this one",
            ],
            "intents": [{"op": "narrate_only", "because": "the pressure is hers, not the dice"}],
        },
    },
    {
        "player": "I put my shoulder to the door and force it.",
        "reply": {
            "narration": "The frame is swollen with damp and the door is older than the "
                         "frame. First shove, nothing but a shower of grit out of the "
                         "lintel and a jarring all the way up into your shoulder. Second "
                         "shove and you can feel where it will go — the top hinge is "
                         "rusted almost through, and the whole thing is holding on the "
                         "bottom two and a bolt you cannot see. Somewhere on the other "
                         "side, something heavy shifts and settles, the way a thing does "
                         "when it has been leaning against a door for a long time. You "
                         "have got one good go at this before whatever is behind it knows "
                         "you are coming. Do you take it?",
            "suggestions": [
                "Put everything into one more shove",
                "Work the top hinge loose instead",
                "Back off and find another way in",
            ],
            "intents": [{
                "op": "check", "actor": "pc", "because": "forcing a swollen door",
                "params": {"skill": "climb", "dc": {"band": "tough"}},
                "visibility": "player",
            }],
        },
    },
]

# --- Combat ---------------------------------------------------------------------------
#
# A fight is a different job and gets a different prompt. Nine hundred characters of
# scene-setting is right when somebody opens a door onto a cellar and badly wrong when
# there is a sap coming at their head: the pace of the prose is the pace of the fight,
# and a turn that takes four sentences to arrive at the threat has already lost it.
#
# So combat gets its own briefing, its own examples, and its own much lower floor. One
# formula, and it is short on purpose.
COMBAT_FORMULA = """A fight is fast and the writing is fast with it. One formula, every
round:

  LANDED   what the last beat did — a clause, not a sentence
  THREAT   what is coming at them right now, and from where
  OPENING  one concrete thing they could use: ground, a rail, a lamp, somebody's blind
           side, the fact that he has to step over a body to reach you
  ASK      short

Three or four sentences. No scene-setting, no weather, no recap of how the fight began.
The player is looking for the next thing to do and everything else is in the way.

You still never say how a roll turned out. "His sap comes round at your head" is the
wind-up; whether it lands is the engine's."""

COMBAT_BRIEFING_EXTRA = """

IT IS A FIGHT. Everything above still holds — refs, ops, the wind-up only — but the shape
of the writing changes.

""" + COMBAT_FORMULA


COMBAT_EXAMPLES = [
    {
        "player": "I go for the one with the sap.",
        "reply": {
            "narration": "You come inside his reach before he can get the swing going. "
                         "The other one is already moving round the crates on your blind "
                         "side, quick for his size. There is a lamp bracket at head height "
                         "between you and him, and it is not fixed to anything much. Which "
                         "of them do you deal with?",
            "suggestions": ["Finish the one in front of you",
                            "Bring the bracket down on the other",
                            "Get the crates between you and both of them"],
            "intents": [{"op": "attack", "actor": "pc", "target": "c1",
                         "because": "the sap is the thing that will put her down"}],
        },
    },
    {
        "player": "I get my back to the wall and wait for him.",
        "reply": {
            "narration": "You give ground and the wall comes up behind your shoulders, "
                         "cold through the coat. He does not rush it — he comes on flat "
                         "feet with the blade low, taking the angle away from you a step "
                         "at a time. There is broken crockery underfoot on his side of the "
                         "floor and he has not looked down once. What do you do?",
            "suggestions": ["Wait for him to step on it",
                            "Go at him before he sets himself",
                            "Look for a way along the wall"],
            "intents": [{"op": "narrate_only", "because": "she is waiting, not acting"}],
        },
    },
    {
        "player": "I kick the table into him.",
        "reply": {
            "narration": "The table is heavier than it looks and it goes over rather than "
                         "across, but it goes at him. He gets a hand down and the whole "
                         "thing catches him at the hip, and for a moment he is tangled and "
                         "the doorway behind him is clear. His friend is still coming, and "
                         "closer than he was. Do you take the door?",
            "suggestions": ["Go through the door while he is tangled",
                            "Put him down while he cannot move",
                            "Turn and meet the other one"],
            "intents": [{"op": "attack", "actor": "pc", "target": "c1",
                         "because": "she wants him off his feet, not dead",
                         "params": {"manoeuvre": "bull rush"}}],
        },
    },
    {
        "player": "I stay on him and keep hitting.",
        "reply": {
            "narration": "He is not blocking any more, just covering, and the arm he is "
                         "covering with is the one that is bleeding. Behind you the door "
                         "you came in by bangs once against its frame — somebody has come "
                         "through it. He sees them before you do, and it puts something "
                         "back into his face. Do you finish him or turn round?",
            "suggestions": ["Finish him now", "Turn and see who came in",
                            "Get where you can see both"],
            "intents": [{"op": "attack", "actor": "pc", "target": "c1",
                         "because": "she is not giving him the room to recover"}],
        },
    },
    {
        "player": "I've had enough. I'm going out the window.",
        "reply": {
            "narration": "You break contact and the window is four running steps away, "
                         "shutters open on a drop you have not measured. Behind you he "
                         "comes after you rather than letting you go, and he is faster over "
                         "open floor than he was in the press. Below the sill there is a "
                         "cart, or something the shape of a cart, in the dark. Do you go?",
            "suggestions": ["Go through and take the drop",
                            "Turn at the sill and meet him",
                            "Shutter it in his face and find another way"],
            "intents": [
                {"op": "end_encounter", "because": "she is breaking off and going out"},
                {"op": "check", "actor": "pc", "because": "a drop she has not measured",
                 "params": {"skill": "acrobatics", "dc": {"band": "tough"}},
                 "visibility": "player"},
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

Build the turn out of four moves. They are not paragraphs and not an order to follow
slavishly — they are what a turn is made of:

  ANCHOR   pick up from what just happened, in a clause, not a recap
  SENSE    two or three concrete things: what is heard, smelt, felt underfoot, not seen
  PUSH     somebody or something acts — an NPC moves, the weather turns, a door closes
  TURN     hand it back by asking what they DO. Never what they see, notice, feel or
           find — the player cannot perceive anything you have not already written,
           so a question about their senses is you asking them to write the room.

Which of them carries the weight depends on the situation. Some shapes that work:

  ARRIVING SOMEWHERE     heavy SENSE, one detail that is wrong or unexpected, then TURN
  SEARCHING              what they find first, what it implies, what they have not
                         reached yet
  TALKING                what the body does before the mouth does; the answer; the thing
                         the answer avoided
  A DEAL OR A THREAT     what it costs them, what the other side wants, the clock on it
  DISCOVERY              the thing itself, then the detail that makes it worse
  A HAZARD GOING WRONG   the mechanism failing, the change spreading, how long they have
  AFTERMATH              the quiet, the damage, what it cost, what is still out there

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
Selling something out of the satchel:
{"op": "sell", "actor": "pc", "params": {"item": "<the jar's id>", "count": 1,
"to": "<the buyer's ref, if they are in the scene>"}} — the engine prices it, checks what
that stall can actually raise today and moves the coin. Never state a price or a sum of
money in the narration: what the buyer can pay is not something you know.
If the turn needs no mechanics at all, emit a single {"op": "narrate_only"} intent.
""" % (", ".join(DC_BANDS), ", ".join(sorted(MANEUVERS)))


# What the brief says about a body when the sheet names one of the two the app ships
# with. Matter-of-fact and specific: this exists because "it is a woman's body" on its
# own produced a narrator who described no body at all rather than the wrong one.
_BODY_BRIEF = {
    "woman": (" She is a woman and her body is a woman's — she has breasts, whatever "
              "size, and no beard. Describe her as she is when the narration reaches "
              "her; do not go vague to avoid it."),
    "man": (" He is a man and his body is a man's. Describe him as he is when the "
            "narration reaches him; do not go vague to avoid it."),
}


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
            # Both facts, in plain words. Pronouns alone were not enough and could not
            # have been: measured in play on a character who stood in front of a mirror,
            # the whole paragraph was in the second person — "your jaw", "your pectoralis
            # major muscles" — so no pronoun appeared in it anywhere, and the only thing
            # the brief had ever said about her was which pronouns to use *when somebody
            # speaks about her*. Nothing said what she was, so the model wrote the body it
            # defaults to. It knows what a woman looks like; it was never told this was one.
            being = f", a {actor.gender}" if actor.gender else ""
            # Said plainly, because vague is the failure mode. Told only "it is a woman's
            # body", a model that has been stopped from writing the wrong chest writes no
            # chest at all — "a woman should have breasts, whatever size they may be,
            # otherwise its a man". So the brief names the thing rather than gesturing at
            # it, and `narration.right_body` is the net under that, not the instruction.
            body = _BODY_BRIEF.get(str(actor.gender).strip().lower(), "")
            if not body and actor.gender:
                body = (f" When the narration touches their body, it is a "
                        f"{actor.gender}'s body.")
            elif not actor.gender:
                # Said out loud rather than left blank. Four characters on the live
                # roster predate this field and cannot be derived — they/them says
                # nothing about a body — and silence is what produced the wrong one in
                # the first place: told nothing, the model writes its default and then
                # treats it as settled. An instruction not to assert is weaker than a
                # fact, but it is the only honest thing to say when nobody has said.
                body = (" Nobody has said what they look like. Do not describe their "
                        "body or assert anything about it; write what they do.")
            lines.append(
                f"  {ref} — {actor.name}, the player's character{being}. Narrate to them "
                f"as 'you'; when someone speaks about them, {actor.pronouns}.{body} "
                f"{actor.heritage} {actor.class_data.get('name', '')} {actor.level}, "
                f"{actor.hp}/{actor.hp_max} hp."
            )
        else:
            note = actor.notes.split(".")[0] if actor.notes else ""
            lines.append(f"  {ref} — {actor.name}. {note}.")

    # What the player's class can actually do, by name. Without this the GM narrates a
    # Blood Bender throwing spikes it has never heard of and emits `narrate_only`,
    # which is how fifty-four turns produced one mechanical intent between them.
    pc = scene.pc()
    if pc is not None and getattr(pc, "paths", None):
        from rules import leveling

        usable = []
        for path in pc.paths:
            det = leveling.path_detail(pc.char_class or "", path)
            reached = leveling.control_blood_for(pc, path)
            for tier, names in sorted((det.get("tiers") or {}).items()):
                if int(tier) <= reached:
                    usable += names
        if usable:
            lines.append(
                f"\nWHAT {pc.name.upper()} CAN DO (their own class abilities — when they "
                f'use one, emit {{"op": "use_ability", "params": {{"ability": "<name>", '
                f'"to": "<ref>"}}}} and let the engine resolve it):')
            for name in usable:
                lines.append(f"  {name}")

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


def call_one_messages(briefing_scene: str, history: list[dict], player_input: str,
                      in_combat: bool = False, enemy: str | None = None) -> list[dict]:
    """The turn prompt, in one of two modes.

    Out of a fight the model is shown long examples and asked to build a scene. In one it
    is shown short ones and asked to keep up. Same protocol, same ops, same refs — only
    the pace of the prose and the examples that teach it change.

    The combat examples *replace* rather than extend, deliberately. Showing both sets in a
    fight would put nine hundred characters of cellar-and-weather in front of a model
    being asked for three sentences, and demonstration volume is what wins.
    """
    briefing = BRIEFING + (COMBAT_BRIEFING_EXTRA if in_combat else "")
    examples = COMBAT_EXAMPLES if in_combat else EXAMPLES

    messages = [{"role": "system", "content": briefing + "\n\n" + briefing_scene}]
    for ex in examples:
        messages.append({"role": "user", "content": fill_enemy(ex["player"], enemy)})
        messages.append({"role": "assistant",
                         "content": fill_enemy(json.dumps(ex["reply"]), enemy)})
    messages.extend(history)
    messages.append({"role": "user", "content": player_input})
    return messages


# --- intents first, prose afterwards -----------------------------------------------------
#
# The experiment behind `GM_INTENTS_FIRST`. Today one call returns narration and intents
# together, which means the prose is written *before* the dice are rolled and before the
# scene state changes — and every awkward thing in the turn descends from that:
#
#   * `_repair_outcome_claims` exists only because the model asserts results it cannot
#     know yet. Remove the cause and the repair has nothing to do.
#   * Every retry regenerates a 600-character paragraph. Five attempts means writing the
#     scene five times to fix a malformed `target` field.
#   * `polish` is a second full model call, spent fixing prose written blind. Measured on
#     one live turn that resolved to `narrate_only` — nothing happened at all — plan 9.3s
#     plus polish 10.6s, 19.9s and two model calls.
#
# The counter-argument is real and is why this is measured rather than assumed: the
# narration may be doing work as a reasoning scratchpad. Writing "you swing at the thug"
# before emitting `attack` is chain-of-thought, and on an 8B model that may well make the
# *intents* better. Splitting them could make them worse. `tools/narrator_audit.py` is the
# instrument; the 196/200 baseline is what it has to beat.
INTENTS_ONLY_EXTRA = """
THIS TURN: intents only. Do not write any narration at all — the "narration" field must be
an empty string. Somebody else writes the prose after the engine has rolled, and they will
know what actually happened, which you do not. Emit only the intents.
"""


def call_one_intents_only(briefing_scene: str, history: list[dict], player_input: str,
                          in_combat: bool = False, enemy: str | None = None) -> list[dict]:
    """The same turn prompt, with the prose taken out of the examples as well.

    The first cut left the examples' narration in place and measured 26.8s a turn against
    a 16.9s baseline — same correctness, 60% slower — because both calls were carrying the
    same several thousand characters of scene-writing. On a local 8B that is most of the
    cost of a turn, paid twice.

    So the examples keep their intents and lose their prose. What they are here to teach
    is the shape of an intent list; the narration in them is teaching the other call's job.
    A one-character narration rather than an empty string, deliberately: an example whose
    narration field is "" reads as a demonstration that a turn may be empty, which is the
    failure grammar-constrained decoding exists to prevent.
    """
    messages = call_one_messages(briefing_scene, history, player_input,
                                 in_combat=in_combat, enemy=enemy)
    messages[0] = {"role": "system",
                   "content": messages[0]["content"] + "\n" + INTENTS_ONLY_EXTRA}
    out = [messages[0]]
    for m in messages[1:]:
        if m["role"] == "assistant":
            try:
                reply = json.loads(m["content"])
            except (ValueError, TypeError):
                out.append(m)
                continue
            reply["narration"] = "-"
            reply.pop("suggestions", None)
            out.append({"role": "assistant", "content": json.dumps(reply)})
        else:
            out.append(m)
    return out


PROSE_AFTER_EXTRA = """
THIS TURN: the engine has already resolved it, and what it decided is below. Write the
turn as prose — the scene, the people in it, what just happened — and put nothing in the
"intents" list; it must be empty.

What the engine decided is what happened. Do not contradict it, do not add a roll, do not
state a number, and do not invent an outcome it did not give you. If it decided nothing
mechanical, this is a quiet beat: describe the place and the people and hand the turn back.
"""


def call_prose_messages(briefing_scene: str, history: list[dict], player_input: str,
                        tells: list[str], in_combat: bool = False,
                        enemy: str | None = None) -> list[dict]:
    """Write the whole turn, after the dice.

    The *call-one* briefing and examples, not the consequence ones, because this is being
    asked for a scene rather than for two sentences about a blow — the consequence prompt
    demonstrates brevity, and demonstration volume is what wins.

    The engine's tells go in as facts the prose has to honour. When there are none the
    turn was a quiet beat, which still needs writing: a `narrate_only` turn producing no
    prose at all is an empty page, and most town turns are `narrate_only`.
    """
    messages = call_one_messages(briefing_scene, history, player_input,
                                 in_combat=in_combat, enemy=enemy)
    messages[0] = {"role": "system",
                   "content": messages[0]["content"] + "\n" + PROSE_AFTER_EXTRA}
    said = "\n".join(f"- {t}" for t in tells if t)
    messages[-1] = {
        "role": "user",
        "content": (f"The player said: {player_input}\n\n"
                    + (f"What the engine decided:\n{said}" if said
                       else "The engine decided nothing mechanical this turn.")),
    }
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
# Deliberately nowhere near the shipped world: no Kesst, no guildhand, no gate. The first
# version of this example was written about the very yard the fixture opens on, and when
# the 4B qwen copied its answer word for word — which it did, on the first live playtest
# turn — the plagiarism read exactly like play and narrated the player over a wall they
# had never gone near. An example about a ferry can be copied and still be *caught*,
# because nothing in the campaign will ever look like it.
CONSEQUENCE_EXAMPLE = {
    "user": (
        "The player said: I grab for the mooring rope before the ferry drifts out.\n\n"
        "You had already narrated: The current has the ferry now, and the ferryman is "
        "shouting at you from the deck.\n\n"
        "What the engine decided:\n"
        "- Ashka Verel makes the Reflex save by 3.\n"
    ),
    "assistant": (
        "The rope burns through your palms and then holds, and the ferry swings back "
        "against the pilings hard enough to stagger the ferryman. He looks at the water, "
        "then at you, and does not say thank you."
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
# These examples used to cast "a thug" and "a guildhand", and the bleed was watched
# live: a bear's turn came back as "The thug, grinning in a way that doesn't reach his
# eyes, swinging the sap". Now they cast {Current Enemy}, filled with the creature whose
# turn it actually is — a model that copies its example now narrates the right animal.
NPC_EXAMPLES = [
    {
        "ask": "Round 2. It is c1 ({Current Enemy Kind}) turn.\nThey are unhurt and "
               "their conditions are: none.\nWhat does c1 do?",
        "reply": {
            "narration": "{Current Enemy} closes the distance fast, low and quiet, "
                         "picking the moment.",
            "intents": [{"op": "attack", "actor": "c1", "target": "pc",
                         "because": "it means to put the intruder down"}],
        },
    },
    {
        "ask": "Round 4. It is c2 ({Current Enemy Kind}) turn.\nThey are badly hurt and "
               "their conditions are: shaken.\nWhat does c2 do?",
        "reply": {
            "narration": "{Current Enemy} takes in the blood it is losing, and the open "
                         "ground behind it, and chooses the ground.",
            "intents": [{"op": "narrate_only",
                         "because": "living matters more to it now than winning"}],
        },
    },
    {
        "ask": "Round 3. It is c1 ({Current Enemy Kind}) turn.\nThey are bloodied and "
               "their conditions are: none.\nWhat does c1 do?",
        "reply": {
            "narration": "{Current Enemy} is past caution now — it comes straight on, "
                         "hard, everything it has left in the one rush.",
            "intents": [{"op": "attack", "actor": "c1", "target": "pc",
                         "because": "wounded and cornered, it fights"}],
        },
    },
    {
        "ask": "Round 2. It is c3 ({Current Enemy Kind}) turn.\nThey are lightly hurt "
               "and their conditions are: none.\nWhat does c3 do?",
        "reply": {
            "narration": "{Current Enemy} gives a step of ground and raises a cry that "
                         "carries — a summons, not a retreat.",
            "intents": [{"op": "narrate_only",
                         "because": "it is buying time for whatever answers the call"}],
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
    # The acting creature is its own {Current Enemy}: an example the model copies now
    # describes the animal whose turn it is, not a thug it was once shown.
    for ex in NPC_EXAMPLES:
        messages.append({"role": "user", "content": fill_enemy(ex["ask"], actor.name)})
        messages.append({"role": "assistant",
                         "content": fill_enemy(json.dumps(ex["reply"]), actor.name)})
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


# The repair call was the last prompt in the file with no demonstration in it, and it
# showed. Measured on qwen3-4b-instruct-abliterated: asked to rewrite a narration, it
# returned `{"player": "Kesst Vayr", "pc": "Kesst V. Vayr", "c1": "the guildhand", ...}` —
# a ref table, because nothing had ever shown it what a repair reply looks like.
#
# Kept deliberately plain and short. This example teaches a *shape*, and the less of it
# there is to lift the better; the scene it describes is nowhere else in the app.
NARRATION_REPAIR_EXAMPLE = {
    "user": (
        "You have copied wording from the examples: 'the lamp is at the far end'. "
        "Rewrite it completely.\n\n"
        "The passage:\nThe lamp is at the far end of its arc. What do you do?\n\n"
        "The player said: I wait for my moment."
    ),
    "assistant": json.dumps({
        "narration": "The light has swung as far from you as it is going to get, and it "
                     "will not stay there. What do you do?"
    }),
}


def prose_schema(min_chars: int = 0, max_chars: int = 0) -> dict:
    """The one-field schema for every call that only writes prose.

    Honest about what it buys, because the first version of this docstring overclaimed
    and the call-site audit corrected it. `as_json=True` already puts a JSON grammar at
    the sampler on Ollama, so the live failure —

        polish failed: Unterminated string starting at: line 1 column 15 (char 14)

    — was not an unconstrained sampler. It was the token budget dying mid-string
    (`num_predict` stops generation regardless of grammar state), which no schema
    prevents and the callers' try/except still catches. Three things this *does* buy:

      * the required `narration` key, so a structurally empty reply is unsamplable;
      * `maxLength`, which is the real truncation fix — a ceiling the token budget can
        comfortably afford means the string closes before the budget dies (six call-1
        rejections in the census were "Expecting ',' delimiter" at ~char 420, all
        budget deaths);
      * nothing at all on hosted providers, which silently ignore `schema=` — the
        guarantee is Ollama-only, and the except paths are why that is survivable.
    """
    narration: dict = {"type": "string"}
    if min_chars:
        narration["minLength"] = int(min_chars)
    if max_chars:
        narration["maxLength"] = int(max_chars)
    return {"type": "object", "properties": {"narration": narration},
            "required": ["narration"]}


def narration_repair_messages(text: str, complaint: str, player_input: str = "",
                              scene_brief: str = "") -> list[dict]:
    """The rewrite call, given something to write *about*.

    It used to be handed the passage and the complaint and nothing else. Asked to rewrite
    a paragraph using none of the phrases it had copied, with no scene in front of it, the
    model had nothing to replace them with — and returned "..." and ". ..", three
    characters long, which then scored better than the plagiarism it replaced. Measured on
    all three turns of a live run.
    """
    body = complaint + "\n\nThe passage:\n" + text
    if player_input:
        body += f"\n\nThe player said: {player_input}"
    if scene_brief:
        body += f"\n\nWrite about this scene, and nothing else:\n{scene_brief}"
    return [
        {"role": "system", "content": NARRATION_REPAIR_BRIEFING},
        {"role": "user", "content": NARRATION_REPAIR_EXAMPLE["user"]},
        {"role": "assistant", "content": NARRATION_REPAIR_EXAMPLE["assistant"]},
        {"role": "user", "content": body},
    ]


# --- the shape a turn is allowed to have -----------------------------------------------
#
# Everything else in this file asks the model to behave. This describes a reply the model
# *cannot* break, because Ollama passes `format` to the sampler as a grammar: a token that
# would leave the schema is never sampled, so there is no validate-and-retry loop and no
# turn lost to a reply that came back the wrong shape.
#
# Researched rather than guessed. Grammar-constrained decoding is the standard answer to
# exactly this failure — XGrammar is the default structured-generation backend for vLLM,
# SGLang and TensorRT-LLM, and llama.cpp/Ollama expose the same thing through `format`.
#
# The important part is that the schema is built **per turn, from the situation**. A
# static schema can only say "intents is a list of ops"; one built here can say "it is
# this character's turn in a fight, so the list may not be empty and `narrate_only` is
# not one of the choices". The failure that cost this session its whole combat loop —
# the GM narrating a punch and proposing nothing — stops being something to detect and
# repair, and becomes something the sampler cannot emit.

# Ops that resolve a turn in a fight. `narrate_only` is deliberately absent.
_FIGHT_OPS = ("attack", "cast", "use_ability", "use_item", "move", "spend_pools",
              "guard", "end_encounter", "check", "save", "damage", "heal")


def turn_schema(*, fighting: bool = False, refs: tuple[str, ...] = (),
                min_chars: int = 0, must_contain: tuple[str, ...] = ()) -> dict:
    """The JSON schema this turn's reply must satisfy.

    `refs` pins the cast: the enum makes it impossible to aim at somebody who is not in
    the scene, which is the single most common rejection in the logs and the reason
    `repair_unknown_refs` had to be written.

    `must_contain` is the same idea aimed at the other failure — not proposing anything at
    all. When the player has plainly declared something (`judgement.declared_ops` decides,
    by asking the injectors themselves), the reply is required to contain that op, and the
    model then picks the item, the target and the reason with the scene in front of it. An
    injector bolting those on afterwards has to guess them.
    """
    intent = {
        "type": "object",
        "properties": {
            "op": {"type": "string",
                   "enum": list(_FIGHT_OPS) if fighting else sorted(_OPS)},
            "actor": ({"type": "string", "enum": list(refs)} if refs
                      else {"type": "string"}),
            "target": ({"type": "string", "enum": list(refs)} if refs
                       else {"type": "string"}),
            "because": {"type": "string"},
            "params": {"type": "object"},
        },
        "required": ["op"],
    }
    intents = {"type": "array", "items": intent}
    if fighting:
        # The whole point. In a fight the list may not be empty, so "narrated the punch
        # and proposed nothing" is not a reply this model can produce.
        intents["minItems"] = 1
    wanted = [op for op in dict.fromkeys(must_contain) if op in _OPS]
    if wanted:
        # `allOf` of `contains`, one per op, because a single `contains` with an enum is
        # satisfied by any one of them — a turn that both travels and buys needs both, and
        # the enum form would accept either alone.
        intents["allOf"] = [
            {"contains": {"type": "object",
                          "properties": {"op": {"const": op}},
                          "required": ["op"]}}
            for op in wanted]
        intents["minItems"] = max(int(intents.get("minItems", 0)), len(wanted))
    narration = {"type": "string"}
    if min_chars:
        narration["minLength"] = int(min_chars)
    # A ceiling as well as a floor. Six planner rejections in the all-saves census were
    # "Expecting ',' delimiter" at around character 420 — the token budget dying inside
    # the narration string, which no grammar prevents but a length ceiling makes room
    # for: a string that must close by N characters closes while there is still budget
    # to write the intents after it.
    narration["maxLength"] = 800 if fighting else 2200
    return {
        "type": "object",
        "properties": {
            "narration": narration,
            "suggestions": {"type": "array", "items": {"type": "string"}},
            "intents": intents,
        },
        "required": ["narration", "intents"],
    }
