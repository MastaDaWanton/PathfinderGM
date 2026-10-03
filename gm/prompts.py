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

from gm import ledger as ledger_mod
from rules import spells as _spells_mod
from rules import states
from rules.intents import AMOUNT_OPS, OPS as _OPS
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
    # A descriptor the introduce op wrote with its article ("a young drover") is "the
    # young drover", never "the a young drover" — measured in a companion's own turn
    # prose, 2026-10-01, copied from the filled example.
    for article in ("a ", "an "):
        if name.lower().startswith(article):
            return f"the {name[len(article):]}"
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
                "the doorman shifts weight from one foot to the other and blows into "
                "cupped hands; the sap on his belt is loose on its cord, and he has "
                "not looked up in some while. The wall is eight feet of slick masonry with "
                "a hand's width of ledge along the top, and the light will be back across "
                "it in about as long as it takes to breathe twice. The lamp is at the far "
                "end of its arc now. What do you do?"
            ),
            "suggestions": [
                "I go now, while the lamp is away",
                "I wait for the doorman to turn away as well",
                "I follow the wall along, looking for a darker stretch",
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
                "has got up to fix it. <say who=c1 to=you>'The guild pays,'</say> he says at last, in the flat tone "
                "of a man giving you a sentence he was handed. <say who=c1 to=you>'The guild has always paid.'</say> "
                "Then his eyes come up and hold yours a moment too long, and flick past "
                "your shoulder to the door, and back. Whatever the true answer is, he has "
                "just decided you are the kind of trouble that might make him say it. Do "
                "you press him, or let it lie?"
            ),
            "suggestions": [
                "I press him on who really pays",
                "I let it go and ask about something else",
                "I look at whatever he glanced at by the door",
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
                "I go straight in before he can set his feet",
                "I drive him back over the crate",
                'I tell him "stand down and this ends here"',
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
                "I put him down and step clear",
                "I ride him to the ground and pin the arm",
                "I twist away from the swing as he falls",
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
                "I watch the quiet one going wide",
                "I put the barrels between me and the wide man",
                'I speak first: "who sent you?"',
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
                "I find somewhere out of the wind and rest",
                "I double back to see who came looking",
                "I head for the water while it is still dark",
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
                "I check my gear before I move",
                "I go straight to the counting house",
                "I find something to eat and listen to the street",
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
                "I move before they reach this door",
                "I stay still and listen",
                "I look for another way out of the room",
            ],
            "intents": [
                {"op": "use_item", "actor": "pc", "because": "the last of the draught",
                 "params": {"item": "healing-draught#1", "how": "drink"}},
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
                "I dig where the earth is freshest",
                "I get the door open again before it shuts",
                "I feel along the wall for what my hand touched",
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
                "I take the letters and shut the drawer",
                "I read the top one where I stand",
                "I put it all back and get away from the desk",
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
                "<say who=c1 to=you>'A name,'</say> she says. <say who=c1 to=you>'You understand that a name is the only thing in this "
                "room that cannot be given back.'</say> Her rings go round once on her finger. "
                "<say who=c1 to=you>'I will give you one. And if I hear it anywhere but from your mouth to "
                "mine, I will not need to send anyone after you — I will simply say where "
                "you were on the night of the fire, and let the guild do it.'</say> She waits, "
                "and the offer is on the table between you, and it has a price on it. Do "
                "you take it?"
            ),
            "suggestions": [
                "I take the name, and the risk with it",
                'I ask her "what do you want in return, exactly?"',
                "I walk away from this one",
            ],
            "intents": [{"op": "narrate_only", "because": "the pressure is hers, not the dice"}],
        },
    },
    # This slot held "I put my shoulder to the door and force it" — a swollen frame,
    # a rusted hinge, something heavy shifting on the other side. Retired 2026-09-05:
    # it was the strongest attractor in the file. The Continue fix found it finishing
    # every stopped scene; the movement-claim check found it walking players through
    # doors the engine never opened; and on the player's own first turn, with no
    # opening in the history, "I ask what is going on" came back as "You shoulder the
    # door, and it groans" and then a corridor with a candle niche. A question asked of
    # somebody busy, somewhere with water and no door, so nothing in it can be a room.
    {
        "player": "I ask the boatwright what the shouting on the water is about.",
        "reply": {
            "narration": (
                "He does not stop planing. The shaving curls off the strake and drops "
                "onto the pile at his feet, and he watches the river over the top of the "
                "work rather than you. <say who=c1 to=you>'Tide's wrong for it,'</say> he says. <say who=c1 to=you>'That's the Harrow "
                "boys trying to bring a barge in on the ebb, and the lock-keeper telling "
                "them what he thinks of that.'</say> Out past the slipway two lanterns are "
                "moving on the black water, one of them going in circles. Somebody on the "
                "far bank has started ringing a handbell, slowly, the way you would to be "
                "heard rather than to raise an alarm. He runs his thumb along the edge he "
                "has just made and looks at you properly for the first time. <say who=c1 to=you>'You're not "
                "from the lock,'</say> he says. <say who=c1 to=you>'So what do you want with it?'</say> What do you tell "
                "him?"
            ),
            "suggestions": [
                "I tell him the truth about why I am here",
                'I ask "who are the Harrow boys?"',
                "I watch the lanterns and say nothing yet",
            ],
            "intents": [],
        },
    },
    # Somebody new, declared before the prose (docs/declared-not-guessed.md): the plan
    # brings the ferryman in with `introduce`, and the same plan speaks to him as new1.
    # Before this op the only way anybody entered a scene was the prose describing them
    # and a regex booking them afterwards.
    {
        "player": "I look along the quay for someone who knows the river past the weir, "
                  "and ask them.",
        "reply": {
            "narration": (
                "Most of the quay has the look of people who have been asked something "
                "already today and did not care for it. The fish-sellers keep their eyes "
                "on their scales. Only at the far end, where the boards give way to "
                "shingle, does anybody look up: an old ferryman on an upturned hull with a "
                "net across his knees, working a torn mesh closed with a wooden needle. He "
                "watches you come the whole length of the quay without stopping the "
                "needle, and when you are close enough he lifts his chin a fraction, which "
                "on this quay is as good as an invitation. What do you ask him?"
            ),
            "suggestions": [
                "I ask him what lies past the weir",
                "I offer him a coin for the telling",
                "I sit down on the hull beside him and wait",
            ],
            "intents": [
                {"op": "introduce",
                 "because": "a quay has somebody who has worked the river for years",
                 "params": {"who": "old ferryman mending a net", "how": "already_here"}},
                {"op": "say", "actor": "pc", "because": "the player asks him",
                 "params": {"words": "Do you know the river past the weir?", "to": "new1"}},
            ],
        },
    },
    # Somebody else strikes first, declared in the plan (docs/declared-not-guessed.md,
    # the blows door). Before this the only way an NPC's blow reached the dice was a
    # regex reading it out of the finished prose (`attacked_by`), which read "the
    # barmaid rushes over to you with a tankard" as a blow. The actor is the NPC; the
    # engine opens the fight from his side and rolls his blow before the prose is written.
    {
        "player": "I knock the cup out of his hand and laugh in his face.",
        "reply": {
            "narration": (
                "The cup goes spinning off the end of the bar and the laugh is still in "
                "your mouth when he comes off the stool. He is bigger standing than he "
                "looked sitting, and he does not say anything at all: his right hand is "
                "already a fist and already coming round at the side of your head, and "
                "the men at the next table push their chairs back to give him the room. "
                "What do you do?"
            ),
            "suggestions": [
                "I duck under it and hit him back",
                "I step back out of his reach",
                "I grab the stool and put it between us",
            ],
            "intents": [
                {"op": "attack", "actor": "c1", "target": "pc",
                 "because": "he will not be laughed at in front of his friends"},
            ],
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

  LANDED   what the last blow did to the body — where it hit, what it opened or broke, the
           blood — in plain physical words, a clause, not a sentence
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
            "suggestions": ["I finish the one in front of me",
                            "I bring the bracket down on the other",
                            "I get the crates between me and both of them"],
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
            "suggestions": ["I wait for him to step on it",
                            "I go at him before he sets himself",
                            "I look for a way along the wall"],
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
            "suggestions": ["I go through the door while he is tangled",
                            "I put him down while he cannot move",
                            "I turn and meet the other one"],
            "intents": [{"op": "attack", "actor": "pc", "target": "c1",
                         "because": "she wants him off his feet, not dead",
                         "params": {"manoeuvre": "bull rush"}}],
        },
    },
    {
        "player": "I stay on him and keep hitting.",
        "reply": {
            # Written out in the body, 2026-09-25. The fight examples were bloodless — this
            # one's "the arm that is bleeding" was the only wound in five — and the prose
            # copied them: in the recorded fights, "the violence" and "the chaos" turned up
            # in about one beat in three. The player asked for the gore, plainly. These are
            # the wounds of the blows before this one, so the example still never says how
            # this turn's roll went.
            "narration": "He is not blocking any more, just covering: your last punch "
                         "opened his eyebrow to the bone, and blood has run into the eye so "
                         "he fights half blind, spitting red through a split lip. The "
                         "forearm he holds up is laid open from the wrist. Behind you the "
                         "door bangs — somebody has come in. Do you finish him or turn round?",
            "suggestions": ["I finish him now", "I turn to see who came in",
                            "I get where I can see both"],
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
            "suggestions": ["I go through and take the drop",
                            "I turn at the sill and meet him",
                            "I shutter it in his face and find another way"],
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

Write each suggestion as the PLAYER'S OWN LINE, in the first person, exactly as they
would type it: "I press him on who really pays", never "Press him on who really pays".
Clicking one puts it straight into their box, so a suggestion phrased as advice from
outside the fiction arrives in the box as advice. Put anything the character SAYS in
double quotes: I ask him "who sent you?".

When the player's character says something, emit a `say` op carrying their words. It
rolls nothing and costs nothing, because in these rules speaking is a free action. It is
not a substitute for a roll: if they are trying to PERSUADE, DECEIVE or THREATEN
somebody into something, that is a `check` with the skill named — Diplomacy, Bluff or
Intimidate — and the two go together, the words and the attempt.

Write to the player as "you". Name only the people and places listed below; if you need
someone new, describe them without a name. The examples show you the shape and the length
of a reply, not its words — never repeat a phrase from them.

The player says only what their character does. Who else is present, what they do, and
what the world does are yours to decide — decide them from the world below, and do not
take the player's word for what is there.

Reply with a JSON object:
{"narration": "...", "suggestions": ["...", "..."], "intents": [...]}.

People and creatures are named by ref, never by name. The refs that exist are listed
below; there are no others. To bring a person into the scene, introduce them first and
call them new1 for the rest of the turn; a creature or a foe arriving to fight is a spawn.

Difficulty is a word from this list, not a number: %s.
A circumstance is "favorable" or "unfavorable", nothing else.
To grab, shove, trip, disarm or break something rather than wound it, use an attack with
a manoeuvre: %s. A disarm, steal or sunder names the thing it is after in "item"; a dirty
trick names its one effect in "trick" (blinded, dazzled, deafened, entangled, shaken or
sickened).
When the fighting stops — they run, they yield, the player gets clear — end it with
{"op": "end_encounter"}. Nobody can rest while a fight is still running.
When the player sleeps or makes camp, use {"op": "rest", "params": {"kind": "night"}}
— that is how wounds heal. "bed rest" is a full day and night and heals twice as much.
You never write a number for what heals, wards, poisons or burns: the thing that does it
carries its own. A potion or a poultice is used by its id from the CARRYING list:
{"op": "use_item", "actor": "pc", "params": {"item": "<the jar's id>", "how": "drink"}}
("throw" at a ref in "to", "coat" for a blade; a salve, poultice or eyewash put on
somebody is "how": "apply" with "route": "wound", "skin", "eyes" or "inhale", and "to"
for whoever it is put on). A spell is cast by name:
{"op": "cast", "params": {"spell": "<the spell>", "at": "<ref>"}}. A class power is
{"op": "use_ability", "params": {"ability": "<name>"}}. The engine reads the jar, the
spell or the power and applies what it says. Never narrate a wound closing without one
of these; if you do, the character walks away as hurt as they arrived and the player will
see it on the sheet. A jar the character is not carrying cannot be used: say so.
A fall, a fire, acid, cold, thirst — the world hurting someone with no spell or blade
behind it — is a rule you cite, never dice you write: {"op": "hazard", "params":
{"rule": "falling", "distance_ft": 30, "to": "<ref>"}}. The rules are {HAZARD RULES};
you supply only that one number and the rule supplies the dice.
Add "deliberate": true for a chosen jump. A trap is narrated this stage, not rolled.
When the party moves onto different ground, say so: {"op": "travel", "params":
{"biome": "forest"}}. The biomes are urban, grassland, farmland, forest, jungle, swamp,
hills, mountain, desert, tundra, coast, underground, ruins, planar. What can be found by
searching depends entirely on it, so it has to be right before anyone looks.
A move WITHIN one place is the same op with a spot instead of a biome: leaving a stall for
the square, a taproom for the street, one wing of a ruin for another is {"op": "travel",
"params": {"place": "the market square"}}. Use it whenever the scene changes room, even
though the ground has not changed — it is what leaves the people of the old room behind,
and without it they follow the party around. Somebody who comes along is named in
"with", by ref: {"op": "travel", "params": {"place": "the gate", "with": ["c2"]}}.
Everyone not named stays where they are.
Going up to somebody who is HERE is never a travel — a travel leaves them behind. Out of a
fight as in one, close the distance with {"op": "move", "actor": "pc", "params":
{"square": [x, y]}} (a square beside them), or narrate the approach with no move at all.
ONE travel a turn. Name where the party ENDS UP, never the route they walk to get there:
the engine finds the way itself and walks every place between, in this one turn, and a
plan carrying a second travel has the second one refused. The tell says which places the
way ran through; describe them as passed through. Something may happen on the way and
stop the party short of where they were going — when it does, the tell says so, and
where they actually are is where they actually are.
When the player searches the ground for herbs or useful growing things:
{"op": "forage", "actor": "pc"}. The engine rolls against what actually grows there and
puts what turns up in their satchel — do not decide what they find.
A place the player makes theirs — a friend's house as a base, a rented room, the alley
behind the market as their own — is founded, from where they stand, and is a place
from then on: {"op": "found", "actor": "pc", "params": {"name": "Marra's house",
"owner": "c2"}}. `owner` is the ref of the person it belongs to, if it is somebody's;
`parent` names the place it hangs off when that is not where the party stands. Standing
in it is a separate travel.
The same door makes a place the scene needs and the list above does not have — a
tavern, the docks, a shrine, a smithy. Found it with its KIND, then travel to it:
{"op": "found", "actor": "pc", "params": {"name": "the Driftwood Reach", "kind":
"tavern", "about": "a squat, leaning structure of lashed-together beams"}}. The engine
keeps it for good, with that description, and refuses a kind that makes no sense here
(a cathedral in a village, docks where there is no water). The kinds are the settlement
words: market, smithy, mill, workshops, tannery, brewery, warehouses, guildhall, library,
keep, gaol, barracks, shrine, temple, graveyard, inn, tavern, bathhouse, theatre, arena,
gardens, well, granary, stables, docks, bridge, lane, back streets, warrens.
Ground the player goes INTO that is not a named place yet —
the sewers, a cellar, a crypt, the rooftops, an alley, a cave, a mine, ruins, a tower —
is {"op": "venture", "actor": "pc", "params": {"kind": "sewers", "parent": "the
market"}}. `parent` must be the place the party is STANDING in — you go down from where
you are, and a venture is not a way to cross town. The engine makes the ground (the same
ground next time), charges the hours the way there costs, moves the party in, and decides
whether anything lives there. Never travel to a place the list above does not name: a
place that is not on it is FOUNDED first, and travelled to after.
Leaving the town ALTOGETHER, for another settlement, is a different thing from travel and
takes days: {"op": "journey", "actor": "pc", "params": {"to": "Zhilgoroth"}}. Only
settlements the world has a road to can be named, the engine works out how long the road
takes and charges the days to the clock and the body, and anybody not named in "with" is
left behind. Say that they set out; do not say how far it is or how long it took — the
engine answers both.
A conversation is a state the engine keeps: it opens when the player speaks to somebody
or somebody speaks to them, and it ends ONLY when the player takes their leave, walks
out of the place, or the other party leaves it — never because a turn went by in
silence. The brief says who the player is IN CONVERSATION WITH; those people answer,
and nobody else steps in unless the player turns to them. When the player says they
take their leave, break off, or will not answer somebody: {"op": "leave_talk", "params":
{"who": "c2", "do": "leave"}} ("ignore" when they refuse to answer). Nobody in a
conversation ever asks the player to roll; a check comes only from what the player does.
When somebody here agrees to come along with the party — a friend, a guide, a hired
sword — say so once and the engine remembers it: {"op": "company", "params": {"who":
"c2"}}. From then on they move when the party moves, through every travel and every
journey, without being named again; {"do": "leave"} ends it. Only somebody friendly or
helpful will come, and the engine refuses anyone else — talk them round first. Somebody
travelling with the party is a person in the scene with their own eyes: let them speak
about what is around them.
When somebody gives the party a task and the player takes it on, it is a quest:
{"op": "quest", "params": {"title": "Find the missing salt", "objectives": ["Ask the
harbourmaster where the salt went", "Bring word back to Marra"], "giver": "c2",
"reward": "a season's salt at cost"}}. Objectives are what is to be done, one sentence
each, at most six; `giver` is the ref of the person who asked; `reward` is what was
promised in words — no numbers anywhere, the engine prices it. When play plainly finishes
one objective of a quest on the SITUATIONS list: {"op": "quest_step", "params":
{"quest": "<the quest's id>", "objective": 1, "note": "what was done"}}. The last
objective done finishes the quest and pays the award; never narrate a quest as finished
unless the engine says it is.
Foraging, harvesting or brewing at a world class — a craft the character works at rather
than a skill they roll: {"op": "craft", "params": {"track": "herbalist", "recipe":
"woundwort styptic", "tier": "common", "stages": 2, "risky": false}}. `stages` is how many
methods the work passed through, `risky` if the harvesting was dangerous, and
"failed": true when it spoils — a ruined batch still teaches something. The character does
not need to have chosen the class; doing the work is how they take it up.
Selling something out of the satchel:
{"op": "sell", "actor": "pc", "params": {"item": "<the jar's id>", "count": 1,
"to": "<the buyer's ref, if they are in the scene>"}} — the engine prices it, checks what
that stall can actually raise today and moves the coin. Never state a price or a sum of
money in the narration: what the buyer can pay is not something you know.
Taking armour or a shield off, or putting away what is in hand: {"op": "take_off",
"actor": "pc", "params": {"item": "armour"}} ("shield", or the thing's name). The engine
says how long it takes, and a suit does not come off in the middle of a fight.
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


def _states_of(actor) -> str:
    """What state a creature is in, as a clause for the brief, or "".

    Stage 7 measured the hole: the player-turn brief named hit points, gender,
    heritage, class, level and class abilities and never a single condition, on the PC
    or on anyone else — probed with a nauseated PC and a shaken NPC, the words
    "nauseated", "shaken" and "condition" were all absent. The NPC-turn prompt said
    "their conditions are: shaken" all along. So on the player-turn path the model was
    structurally unable to know that c1 was dead, and was then corrected for not
    knowing: both real legality firings in 261 turns were exactly that.

    Stated in the vocabulary's own words — a condition's name is a state the engine
    holds, not a number — so this is a fact the tells already back.
    """
    names = []
    for c in getattr(actor, "conditions", None) or []:
        n = str(getattr(c, "name", "") or getattr(c, "key", "")).strip().lower()
        if n and n not in names:
            names.append(n)
    if not names:
        return ""
    return f" Conditions: {', '.join(names)}."


PLACE_WORDS_BUDGET = 900


def place_in_its_own_words(location, budget: int = PLACE_WORDS_BUDGET) -> str:
    """The first paragraph of the sections that describe what a place LOOKS like —
    architecture and daily life before governance and history — cut to a budget at
    a sentence end. A world that ships no sections answers ""."""
    wanted = ("architecture", "urban life", "daily life", "geography", "terrain")
    picked = []
    for title in wanted:
        for s in getattr(location, "sections", None) or []:
            if str(s.get("title", "")).strip().lower() == title:
                for p in s.get("paragraphs") or []:
                    if str(p).strip():
                        picked.append(" ".join(str(p).split()))
                        break
    text = " ".join(picked)
    if len(text) > budget:
        cut = text[:budget]
        end = max(cut.rfind(". "), cut.rfind(".\n"))
        text = cut[:end + 1] if end > 0 else cut
    return text.strip()


def scene_brief(world, scene, location, recent_events=None, *, here=None,
                known=(), recent=None, secret=False, turn=0, names_for=None,
                absent: str = "", buying: str = "", reading=None, player_text: str = "",
                report: dict | None = None) -> str:
    """The world facts the GM may draw on this turn.

    A budget, not a dump. This is the thing that decides whether a local model answers in
    seconds or in a minute, and whether long campaigns stay coherent.

    `reading` (the interpreter's frame) and `player_text` are for the brief's sections
    (gm/brief/) and print nothing by themselves. `report`, when given, is filled with
    `report["facts"][section module] = the facts that section printed`.
    """
    lines = [f"WORLD: {world.name}."]
    if world.premise:
        lines.append("Premise: " + "; ".join(f"{k} — {v}" for k, v in world.premise.items()))

    # What time it is, as fact (rules/residency.py, `time_words`): who is where and which
    # counters are open follow the hour, and a narrator not told it writes a busy market
    # at a stall the engine has shut.
    from rules import residency as _residency

    lines.append(f"WHEN (fact): {_residency.time_words(getattr(scene, 'clock_minutes', 0))}.")

    # Which part of the settlement the party is in, handed down by the caller that has
    # an engine, never derived here: this used to be a second copy of `Engine.places()`,
    # keyed on the `location` argument where the engine keys on `scene.location_id`, and
    # two derivations of one fact is the trap CLAUDE.md names. The fallback is the same
    # one function the engine calls, for the callers (tests, mostly) that have no
    # engine. Resolved here, before the place slot, because the thread line below
    # needs `here` too.
    if location and not known:
        from rules import places as _places

        known = _places.for_scene(location, getattr(scene, "at", ""))
        here = _places.find(known, getattr(scene, "at", "")) or (known[0] if known else None)

    # The brief's sections (gm/brief/, docs/fix-interfaces.md §2.2). The "place" slot is
    # HERE / THE PLACES HERE / NEXT DOOR / UNDERFOOT, ROADS OUT and the settlement's fact
    # keys, which were written inline here until the 2026-09-28 fix pass moved them out
    # byte for byte, so the lanes that change them do not all edit this one function.
    # Each section's facts go into `report`, the `pack` pattern: the returned text is
    # unchanged, and a narrator check can read what the model was actually shown.
    from . import brief as _brief

    # A failed reading (`{"error": ...}`, gm/agent.py) is no reading, for every section.
    from collections.abc import Mapping

    if not isinstance(reading, Mapping) or "error" in reading:
        reading = None
    ctx = _brief.BriefContext(
        world=world, scene=scene, location=location, here=here, known=tuple(known or ()),
        recent_events=recent_events, recent=recent, secret=secret, turn=turn,
        names_for=names_for, absent=absent, buying=buying, reading=reading,
        player_text=player_text or "")
    shown: dict = {}
    placed, facts = _brief.run("place", ctx)
    shown.update(facts)
    if placed:
        lines.append(placed)

    if location:
        # The place in its author's own words, not only its fields. Asked for as "more
        # text and more description per generation", and the fields cannot supply it:
        # "wooden buildings, thatched roofs" is all the brief ever said of Vyrakon,
        # while its export carries a paragraph on timber framed for a cyclone coast
        # and low districts that flood. Measured the turn this landed without: with
        # nothing real to describe, the model furnished a common room with "the heavy
        # oak desk you just searched" — the study from worked example ten. Two
        # paragraphs, capped, because the brief is a budget.
        told = place_in_its_own_words(location)
        if told:
            lines.append(f"  THE PLACE, IN ITS OWN WORDS: {told}")
        parents = [e.name for e in world.ancestors(location.id) if e.kind != "WORLD"]
        if parents:
            lines.append(f"  Within: {', '.join(parents)}")

    # The standing thread, before the cast: what the player is engaged in is the
    # single fact the prose most needs, and the one it lost live (two followed
    # guards became a haunted house between beats).
    from . import judgement as _judgement
    # The place name the thread sentence asserts is the engine's, and only when the
    # place is real: the exitless no-location fallback would read "ALREADY at here".
    held = _judgement.thread_brief(
        scene, where=(here.name if here is not None and here.exits else ""))
    if held:
        lines.append("\n" + held)
    # The situation cards whose keys appear in the last few beats, and the one the
    # player is standing in (`rules/cards.py`). The plan may see the GM's secret
    # cards; the prose never does.
    from rules import cards as _cards

    deck = _cards.brief(scene, recent, turn=turn, secret=secret)
    if deck:
        lines.append("\n" + deck)
    ledger = _judgement.cast_brief(scene)
    if ledger:
        lines.append("\n" + ledger)
    seen = _judgement.heat_brief(scene)
    if seen:
        lines.append("\n" + seen)
    # The counter here keeps hours, and they are over (rules/keepers.py): said as fact, so
    # the beat does not write a bustling stall at midnight that the engine will not sell at.
    from rules import keepers as _keepers

    shut = _keepers.shut_here(scene)
    if shut:
        lines.append(f"\nCOUNTER SHUT (fact): {shut}")
    # The player set out to buy something and the counter's screen opens for it after
    # this beat (play/views.py, `_trade_offer`): the prose settles nothing.
    if buying:
        lines.append(f"\nAT THE COUNTER (fact): {buying}")

    # The player went looking for somebody who is not here, and the world has an answer.
    # Stated before the cast, as fact, because the failure was a model answering a question
    # the world had already answered: "I turn to find the mayor" produced "The mayor stands
    # before you, his heavy woolen cloak still smelling of woodsmoke" in a town whose
    # authority is a reeve and which has no mayor at all (2026-09-19, item 29).
    if absent:
        lines.append(f"\nWHO THE PLAYER LOOKED FOR AND IS NOT HERE (fact, and the beat "
                     f"says so — nobody arrives to satisfy the sentence): {absent}")

    # Who this place would hold, if anybody new appears. Not a claim that they are here —
    # `WHO IS HERE` below is the only such claim — but the roster the model picks from
    # instead of inventing, read off the place's own staffing, the open matters' people and
    # the world's residents (`rules/roster.py`, item 28). The four hand-written templates
    # this replaces were the whole vocabulary on offer while 7,133 stat blocks sat loaded.
    if scene is not None and getattr(scene, "at", ""):
        from rules import roster as roster_mod

        pc_here = scene.pc() if hasattr(scene, "pc") else None
        could = roster_mod.who_would_be_here(
            scene, world, level=int(getattr(pc_here, "level", 1) or 1))
        line = roster_mod.brief_line(could)
        if line:
            lines.append("\n" + line)

    lines.append("\nWHO IS HERE (these refs are the only ones that exist):")
    for ref, actor in scene.actors.items():
        # Somebody hiding in the house is not in the room the character can see. The
        # leak critic measured the giver of A Small Favour listed beside the corpse
        # while the engine held him hidden (2026-09-08): the narrator was handed a
        # presence the character could not know. Hidden people stay off this list.
        if not actor.is_pc and actor.has_state("state.hidden"):
            continue
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
            # What the race document says this body can do — flies, sees in the dark,
            # has claws — as a fact the narrator may use and may not contradict. A
            # tell about the body, not a rule: no number in it the engine did not set.
            race_doc = actor._race_doc()
            bodily = ""
            if race_doc:
                from rules import races as races_mod

                line = races_mod.body_line(race_doc)
                if line:
                    named = str(race_doc.get("name", actor.race) or "")
                    # "A Asura" was reaching the brief. The narrator copies the register
                    # of what it is given, so the article matters more here than it would
                    # in a log line.
                    article = "An" if named[:1].lower() in "aeiou" else "A"
                    bodily = f" {article} {named}: {line}."
            # What the character has noticed: the `knows.*` situation effects a
            # scheme or a card granted, by the name each carries. Measured missing by
            # the fairness critic: a tag alone put nothing in front of the player, so
            # the foreshadowing the twist was gated on was bookkeeping the narrator
            # never saw. A grant's `say` becomes the effect's name and lands here.
            noticed = actor.noticed()
            seen = (" What they have noticed: " + "; ".join(noticed) + ".") if noticed else ""
            # Where they were before the first turn, with the world's own people and
            # places in it. This is the half of a background that matters: the sheet's
            # two skill points are arithmetic the engine handles, and these sentences
            # are the part the narrator can use — somebody who already knows the
            # character, a door they can walk through without explaining themselves.
            # Stated as fact the narrator may rely on, like the body line above it.
            past = getattr(actor, "background_ties", None) or []
            history = (" Before this: " + " ".join(str(p) for p in past)) if past else ""
            lines.append(
                f"  {ref} — {actor.name}, the player's character{being}. Narrate to them "
                f"as 'you'; when someone speaks about them, {actor.pronouns}.{body} "
                # The heritage, or the race document's own name when the sheet's
                # heritage is blank — a homebrew race sits in `race` and the line
                # rendered "  Fighter 1" with nothing before it (2026-09-18).
                f"{actor.heritage or (race_doc or {}).get('name') or actor.race} "
                f"{actor.class_data.get('name', '')} {actor.level}, "
                f"{actor.hp}/{actor.hp_max} hp.{_states_of(actor)}{bodily}{history}{seen}"
            )
            # The jars, by id. `use_item` takes the id and nothing else in the brief
            # named one, so the model had no way to say it and wrote `heal 1d8+1`
            # instead — the recon's gm-side map: "the model is never shown anything
            # it could cite". A player character is the only one with a satchel.
            stock = getattr(actor, "stock", None) or {}
            if stock:
                jars = ", ".join(f"{iid} ({s.base}" + (f" ×{s.count}" if s.count > 1 else "")
                                 + ")" for iid, s in sorted(stock.items()))
                lines.append(f"    CARRYING (use_item by id): {jars}")
            # The raw herbs, with what the character KNOWS of each and nothing more
            # (docs/herbalism-revamp-plan.md §8.1, law 3): an unknown property never
            # reaches the narrator, so the line is built by the one owner of herb
            # knowledge and carries only known lines and a count of the rest.
            from rules import herbknowledge as _hk

            herbs = _hk.brief_line(actor)
            if herbs:
                lines.append(f"    HERBS (fact; only what {actor.name} knows of them — "
                             f"tasting one is the taste op, item=<its name>): {herbs}")
            # And the purse and the goods, as facts. Neither was ever in the brief —
            # the UI showed 231 gp and a chunk of wood, the narrator was shown nothing,
            # and invented the coin changing hands (2026-09-18, the brothel). A thing
            # picked up off the ground keeps whose it is and what it was
            # (`Scene.props`), and that is said beside it.
            from rules import goods as _goods

            purse = getattr(actor, "purse", None) or {}
            carried = getattr(actor, "goods", None) or {}
            if purse or carried:
                held_props = {str(r.get("name", "")).lower(): r
                              for r in (getattr(scene, "props", None) or [])
                              if r.get("held_by") == ref}
                bits = []
                for name, n in sorted(carried.items()):
                    rec = held_props.get(str(name).lower())
                    whose = ""
                    if rec and rec.get("owner") and rec["owner"] != ref:
                        owner = scene.actors.get(rec["owner"])
                        whose = f", {owner.name}'s" if owner is not None else ""
                    was = f", {rec['state']} {rec['from_']}" if rec and rec.get("from_") else ""
                    bits.append(f"{name}" + (f" ×{n}" if n != 1 else "") + whose + was)
                money = _goods.purse_line(purse, _goods.coinage()) if purse else "no coin"
                lines.append(f"    HAS (fact): purse {money}"
                             + (f"; carrying {', '.join(bits)}" if bits else "")
                             + ". Coin leaves the purse only through a give; nothing "
                               "is handed over that is not here.")
        else:
            note = actor.notes.split(".")[0] if actor.notes else ""
            # How they feel about the player, when anything has said. The attitude
            # effect type has existed since the spell import — thirty-three spells
            # set one — and shipped with nowhere to be read; a charmed guard was
            # charmed in the effect list and hostile in every sentence about him.
            # Stated as fact, in the vocabulary's own word, so the narrator writes
            # the creature the engine is holding.
            mood = states.attitude_of(actor)
            feels = f" {actor.name} is {mood} towards the player." if mood else ""
            # The name behind the descriptor and the face beside it, as facts: asked
            # his name, he gives THIS one (never "the stranger", never one made up),
            # and a first description uses THIS body. Both from the world's own
            # material (rules/names.py); a resident's Appearance fact is their own.
            # The true name is NOT shown. Measured twice (the group-3 and group-4
            # replays, 2026-09-18): shown the name, even with "until they give it,
            # call them by their description", the narrator used it anyway — "Soren's
            # eyes narrow", "the woman beside you, Kael Throk". So the model never sees
            # it: when the person introduces themselves the model's own guess is
            # replaced with the world's name in code (`narration.settle_introductions`)
            # and the panel is renamed (`judgement.apply_introductions`).
            # ...with one exception, and it is the turn the player asks. Then the name
            # goes in as the thing he says, for that turn and that person only
            # (`judgement.names_asked_for`), because a model with no name to give
            # refuses — which is how "the stranger" stayed "the stranger" for several
            # scenes (2026-09-19). An empty value means his attitude refuses: said as a
            # fact too, so the refusal is his and not the prompt's silence.
            names_it = ""
            if names_for and ref in names_for:
                given = str(names_for[ref] or "").strip()
                names_it = (f" ASKED HIS NAME THIS TURN (fact — he answers with THIS name "
                            f"and no other, in his own words): {given}." if given else
                            f" ASKED HIS NAME THIS TURN (fact): he will not give it — "
                            f"{actor.name} is {states.attitude_of(actor) or 'unfriendly'} "
                            f"towards the player. He deflects; he does not invent one.")
            # The people's line once per campaign: after the first orc has been
            # described, the next one is "an Orc" and what is different about them
            # (rules/faces.py). Otherwise the narrator repeats the world's one
            # sentence for every orc it meets — reported 2026-09-24.
            from rules import faces as _faces

            face = _faces.for_the_page(
                str(getattr(actor, "appearance", "") or "").strip(),
                _faces.people_seen_before(actor, scene.people.values()))
            # "Use it when they are first described" licensed a fresh invention on every
            # beat after the first: the watchman described as an Orc with hair like wet
            # rope came back as "an older man with a face like cracked leather" two beats
            # later (item 16.7, 2026-09-28). Every description keeps to it; the page's own
            # first description is ALREADY DESCRIBED (gm/brief/faces.py).
            looks = (f" Looks (fact — every description of them keeps to it): {face}"
                     if face else "")
            # Who this person is TO the player. Both are facts the engine holds and the
            # brief never carried, and without them the narrator writes every non-player
            # as a stranger met just now — which is what the player found after four
            # sessions with a local background on the sheet (2026-09-22). The travelling
            # one is why a companion may speak about where the party has just arrived:
            # they walked there too.
            bond = ""
            if actor.has_state(states.KNOWS_YOU):
                bond += (f" {actor.name} KNEW the player before this game began — not a "
                         f"stranger, and never introduced as one.")
            if actor.has_state(states.TRAVELS_WITH_YOU):
                bond += (f" {actor.name} TRAVELS WITH the player: they came here "
                         f"together and they go on together. They have their own eyes "
                         f"and their own opinions about what is around them.")
                # What they do with what the player tells them (owner's ruling,
                # 2026-10-01: companions "take spoken orders as their character dictates
                # they would or would not"). The character is the manner line below and
                # the attitude above; this says it is theirs to weigh. A claimed construct
                # is the house rule's: it follows, obeys, and can be named.
                if actor.has_state(states.OWNED_BY_YOU):
                    bond += (f" {actor.name} BELONGS TO the player, who claimed them, "
                             f"and is devoted: told plainly, {actor.name} does it, as "
                             f"literally as it was said.")
                else:
                    # Their nature in words, for a companion only: it is what decides an
                    # order (the manner line below shows it, which is subtler than the
                    # decision needs). Measured on the companions replay: a drover rolled
                    # timid, told to lift a thug's purse, "moves as if he were part of
                    # the shadows" — shown only how timidity looks, the page had him do
                    # the dangerous thing without a flicker of it.
                    from rules import population as _pop

                    nature = [t for t in (((_pop.of_ref(scene, ref) or {}).get("life")
                                           or {}).get("traits") or []) if t][:3]
                    bond += (f" Told to do something, {actor.name} answers as "
                             f"themselves — does it, does it their own way, or says no; "
                             f"a friend, not a servant."
                             + (f" By nature {actor.name} is {', '.join(nature)}, and "
                                f"that decides what they will and will not do when told."
                                if nature else ""))
                # In a fight their deeds are their own turn's. Measured on the companions
                # replay (2026-10-01): to "Bob, attack the thug! Drover, get that cudgel
                # off him!" the PLAYER's beat had the drover tackle the thug and Bob
                # strike — neither had acted, and both then did on their own turns.
                if scene.in_encounter and any(r == ref for r, _ in scene.initiative):
                    bond += (f" In this fight {actor.name} acts only on their own turn "
                             f"in the order: on anybody else's beat they have heard what "
                             f"was said and have not yet moved or struck.")
            # How they carry themselves, from the life the population rolled for them:
            # behaviour, two traits at most, the quirk only when it is due — and never
            # their wants, goal or hobby, which are learned in play and which a 12B model
            # told them leaks (rules/population.py, "what the narrator is told"), unless a
            # companion has CONFIDED one (below).
            from rules import population as _population

            rec = _population.of_ref(scene, ref)
            manner = _population.manner_for(rec, turn)
            manner = f" {manner}" if manner else ""
            # Said as a fact every turn: the table's content rule is adults only, and
            # the narrator cannot keep a rule about a child it was never told is one.
            if rec and "minor" in ((rec.get("life") or {}).get("tags") or []):
                manner += f" {actor.name} IS A CHILD (fact)."
            # What a companion has CONFIDED is the player's knowledge now, so it cannot
            # leak (gm/confide.py) — but only on a beat something touches it (the place,
            # the last beats, the player's words), decided in code: in the brief every
            # beat it would become their one subject, the tic the quirk's cadence exists
            # to prevent.
            if rec and actor.has_state(states.TRAVELS_WITH_YOU):
                from . import confide as _confide

                touch = " ".join([str(getattr(here, "name", "") or ""),
                                  str(getattr(here, "about", "") or ""),
                                  " ".join(str(x) for x in (recent or [])[-2:]),
                                  str(player_text or "")])
                topics = _confide.relevant_told(scene, actor, touch)
                told = _confide.told_line(scene, actor, only=topics) if topics else ""
                if told:
                    manner += f" {told}"
            lines.append(f"  {ref} — {actor.name}. {note}.{names_it}{looks}{feels}{bond}"
                         f"{manner}{_states_of(actor)}")
    # Who the player is talking to, as a fact with a rule attached. The step is the
    # vocabulary's word and the number stays on the panel: the narrator hears how
    # somebody feels, never what they score (the third law).
    #
    # Once, after the list. It sat inside the loop over WHO IS HERE until 2026-09-28
    # (register §3.4, found when S2 moved the brief's blocks), so a scene of five people
    # printed the same conversation block five times — demonstration volume for one fact.
    from rules import attitude as _attitude

    talking = [a for a in scene.actors.values()
               if not a.is_pc and a.has_state(states.TALKING)]
    if talking:
        lines.append(
            "  IN CONVERSATION WITH: "
            + "; ".join(f"{a.name} ({a.ref}), who is {_attitude.of(a)} towards the "
                        f"player" for a in talking)
            + ". They answer what the player says. Nobody else here joins in "
              "unless the player turns to them. The player is still in this "
              "conversation until they take their leave or walk away — do not end "
              "it for them, and do not have anyone in it ask the player to roll. "
              "If somebody new comes into the scene, write their ARRIVAL first — "
              "who looks up, what they see coming, what the newcomer looks like — "
              "and let the conversation react to it; nobody appears mid-sentence "
              "as if they had always been there.")

    # The "people" slot: sections about who is here, after the list that says who is
    # (gm/brief/, docs/fix-interfaces.md §2.2). Empty when the fix pass began.
    peopled, facts = _brief.run("people", ctx)
    shown.update(facts)
    if peopled:
        lines.append(peopled)
    if report is not None:
        report.setdefault("facts", {}).update(shown)

    # What the player's class can actually do, by name. Without this the GM narrates a
    # Blood Bender throwing spikes it has never heard of and emits `narrate_only`,
    # which is how fifty-four turns produced one mechanical intent between them.
    pc = scene.pc()
    if pc is not None and getattr(pc, "paths", None):
        from rules import leveling

        # The one list, shared with the engine's own refusal for an unknown ability.
        usable = leveling.usable_names(pc)
        if usable:
            lines.append(
                f"\nWHAT {pc.name.upper()} CAN DO (their own class abilities — when they "
                f'use one, emit {{"op": "use_ability", "params": {{"ability": "<name>", '
                f'"to": "<ref>"}}}} and let the engine resolve it):')
            for name in usable:
                lines.append(f"  {name}")

    # And what they can cast, which the brief said NOTHING about until 2026-09-19 — not
    # the spells, not the slots, not even that the character is a caster (item 25). With
    # no spell facts at all the model had nothing to be held to, so "I cast wall of flame"
    # came back as a wall of flame: a level 5 spell, from a level 1 cleric, out of slots
    # the panel still showed as full.
    if pc is not None:
        from rules import casting as _casting

        if _casting.is_caster(pc):
            left = [f"level {lvl}: {_casting.slots_left(pc, lvl)} of {total}"
                    for lvl, total in sorted(_casting.slots_for(pc).items())]
            prepared = []
            for sid, count in sorted((pc.prepared or {}).items()):
                try:
                    prepared.append(f"{_spells_mod.get(sid).name}"
                                    + (f" x{count}" if int(count) > 1 else ""))
                except KeyError:
                    continue
            lines.append(
                f"\nWHAT {pc.name.upper()} CAN CAST (fact — a spell not on this line is "
                f"NOT cast, whatever the beat says; if they cast one, emit "
                f'{{"op": "cast", "params": {{"spell": "<id>", "at": "<ref>"}}}} and let '
                f"the engine spend the slot):")
            lines.append("  Prepared today: " + (", ".join(prepared) or "nothing"))
            lines.append("  Slots left: " + (", ".join(left) or "none"))
            lines.append(f"  Caster level {_casting.caster_level(pc)}, highest spell level "
                         f"{_casting.highest_spell_level(pc)}.")

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


# --- the context budget ---------------------------------------------------------------
#
# Every turn is one prompt, and that prompt has to fit. Measured 2026-09-08 on the
# shipped Pangrella export: the history is an unbounded list that nothing trims, the
# assembled prompt passes the window at turn 46 out of combat, and from there Ollama
# drops messages off the front — the worked examples first, all twenty-four of them by
# turn 57, and one exchange of real play per turn after that. It says nothing to the
# caller when it does this; the only trace is a debug line in its own server log.
#
# Two consequences, in the order the player meets them. The examples go first, so the
# first symptom of a full window is prose quality falling apart rather than the game
# forgetting. Only later does it start losing what actually happened.
#
# So we do the cutting. `pack` decides what goes, in a stated order, and reports it.
NUM_CTX = 16384
# The window holds the prompt AND the answer. `gm/agent.py` asks for up to 1400 tokens
# of completion, and a prompt that fills the window leaves the model no room to answer:
# that failure is already recorded in gm/client.py's own comment, where a 4,086-token
# prompt against a 4,096 window died mid-sentence on every turn of a live scene.
MAX_COMPLETION_TOKENS = 1400
# The chat template's own wrapping, plus the error in the ratio below.
SAFETY_TOKENS = 600
# Measured by `tools/token_ratio.py` against the configured model, taking the worst
# case of three real prompts. Shipping a tokeniser is not an option — it would be a
# third dependency, one per model, in an app that has two — so the budget is counted in
# characters and converted here. Lower is safer: it under-fills rather than overflows.
#
# Measured 2026-09-08 on igorls/gemma-4-12B-it-heretic: 3.82 for the briefing and brief
# alone, 3.83 for a full turn out of combat, 3.79 in combat. The count comes back from
# the model's own `prompt_eval_count`, which counts the chat template's wrapping too
# while we only count message content — so the ratio already absorbs that overhead and
# errs low. 3.6 keeps a margin under the worst case on top of SAFETY_TOKENS.
CHARS_PER_TOKEN = 3.6
PROMPT_BUDGET_CHARS = int(
    (NUM_CTX - MAX_COMPLETION_TOKENS - SAFETY_TOKENS) * CHARS_PER_TOKEN)
# The most recent turns are kept ahead of the worked examples, because a model that has
# lost the thread writes a well-formed wrong scene. Everything older queues behind them.
KEEP_EXCHANGES = 3


def _chars(messages) -> int:
    return sum(len(m.get("content") or "") for m in messages)


def _from_a_user(messages: list[dict]) -> list[dict]:
    """Drop leading assistant turns so a kept stretch never opens on a reply.

    Ollama counts messages, not exchanges, and will happily cut between a question and
    its answer — leaving a reply standing with nothing it was replying to. We never do.
    """
    i = 0
    while i < len(messages) and messages[i].get("role") != "user":
        i += 1
    return messages[i:]


def pack(head: list[dict], examples: list[dict], history: list[dict],
         tail: list[dict], *, budget: int = PROMPT_BUDGET_CHARS,
         keep: int = KEEP_EXCHANGES, report: dict | None = None,
         ledger: list[dict] | None = None) -> list[dict]:
    """Fit the turn into the budget, deciding what goes rather than letting the server.

    The order is stated and tested: the system message and the player's own line are
    never cut, then the most recent few exchanges, then the worked examples, then older
    history newest-first. `report` is filled in with what happened so the caller can
    log it — a cut that nobody records is the failure this function exists to end.

    The GM's private note is pinned ahead of the history and never cut. It rides in
    `c.history` (planted first at campaign open, rewritten in place by the watcher), so
    cutting oldest-first made it the FIRST thing to go: measured 2026-10-01, turn 32 of
    a talk-only campaign, and the one message cut was the undercurrent
    (tests/test_undercurrent_survives_packing.py). NovelAI's Memory and SillyTavern's
    story string are the same answer: standing notes in their own slot, outside the
    history that gets trimmed.
    """
    from play.opening import NOTE_PREFIX

    original = history
    pinned = [m for m in history if str(m.get("content", "")).startswith(NOTE_PREFIX)]
    if pinned:
        history = [m for m in history if not str(m.get("content", "")).startswith(NOTE_PREFIX)]
    # The opening frame is pinned the same way: the campaign's first GM message, written
    # before the player has said anything. It was never in the prompt at all — the kept
    # stretch must open on a player's line (`_from_a_user`), so the one reply with nothing
    # before it was dropped on the FIRST turn and every turn after: measured 2026-10-03,
    # every turn of both owner saves logged "dropped the oldest 1 message(s)" from the
    # first, and that one was "Evening in Zhilvarnia. You are in a lit doorway… You came
    # in out of the weather to find a bed you can pay for." The ledger cannot carry it —
    # it is written from turns' outcomes, and the opening is no turn. KoboldAI's Memory
    # and MemGPT's read-only system block are the same answer: the frame the story began
    # in rides in its own slot, never a candidate for the cut.
    if history and history[0].get("role") == "assistant":
        pinned = pinned + [history[0]]
        history = history[1:]
    # The last `keep` EXCHANGES, counted from the player's lines. It was
    # `history[-(keep * 2):]`, but a turn writes three messages (the player's line, the
    # plan, the prose — play/views.py), so "three exchanges" kept two (2026-09-25).
    users = [i for i, m in enumerate(history) if m.get("role") == "user"]
    kept_recent = (_from_a_user(history[users[-keep]:]) if keep and len(users) >= keep
                   else _from_a_user(list(history)) if keep else [])
    older = history[:len(history) - len(kept_recent)] if kept_recent else list(history)

    # The ledger's room is reserved before anything competes for it, and rendered
    # after the history is decided, because what it may say depends on what was cut.
    # Reserving the cap rather than the rendered size under-fills by whatever the
    # ledger did not use, which is the safe direction.
    reserve = ledger_mod.BUDGET_CHARS if ledger else 0
    room = budget - _chars(head) - _chars(tail) - _chars(pinned) - reserve
    # The parts that are never cut already over the budget: the prompt goes anyway, since
    # there is nothing left to drop, but it is SAID — measured 2026-09-25, this sent an
    # over-budget prompt without a word in the report or the log, and Ollama then cuts
    # the front of it silently, the failure this function exists to end.
    over = room < 0
    if over:
        import logging

        logging.getLogger("pathfindergm").warning(
            "the prompt's fixed parts are %d characters over the %d budget; the model "
            "will see it cut", -room, budget)
    # A floor this small means the brief itself has outgrown the window; send the turn
    # anyway. A turn that refuses to be built is worse than a turn built thin.
    while kept_recent and _chars(kept_recent) > room:
        kept_recent = _from_a_user(kept_recent[1:])
    room -= _chars(kept_recent)

    with_examples = _chars(examples) <= room
    if with_examples:
        room -= _chars(examples)

    # Older history, newest first, one exchange at a time.
    front: list[dict] = []
    older = _from_a_user(older)
    while older:
        bite = older[-2:] if len(older) >= 2 else older[-1:]
        if _chars(bite) > room:
            break
        front = bite + front
        older = older[:-len(bite)]
        room -= _chars(bite)
    front = _from_a_user(front)

    kept_history = front + kept_recent
    dropped = len(history) - len(kept_history)

    # Where the window's edge falls, in the same units the ledger stamps: the index in
    # the campaign's own history of the first message still kept. That was `dropped`
    # until the note was pinned; it is the same number whenever nothing is pinned, and
    # counts a pinned note that sat before the edge as behind it. When nothing at all is
    # kept verbatim — which is every prose call, handed `[]` by design — the whole
    # ledger is outside the window and all of it is fair game.
    edge = (next((i for i, m in enumerate(original) if m is kept_history[0]), dropped)
            if kept_history else 10 ** 9)
    # Less the two characters of the "\n\n" it is joined on with below.
    remembered = (ledger_mod.block(ledger, before_hist=edge, budget=reserve - 2)
                  if ledger else "")
    if remembered and head:
        # Onto the system message, which is never cut: these are facts the engine
        # kept, and they rank with the brief rather than with the conversation.
        head = [{**head[0], "content": head[0]["content"] + "\n\n" + remembered}] + head[1:]

    if report is not None:
        report.update({
            "dropped": dropped,
            "kept": len(kept_history),
            "examples": with_examples,
            "budget": budget,
            "remembered": remembered.count("  * "),
            "over_budget": over,
        })
    # Where it sat before when nothing was cut: after the examples, ahead of the history.
    return head + (examples if with_examples else []) + pinned + kept_history + tail


HAZARD_TOKEN = "{HAZARD RULES}"


def hazard_rules_line() -> str:
    """The hazard rules the briefing lists, read from content/rules/hazards.json, each
    with the one number its slot takes: "falling (distance_ft), catching-fire (rounds), …".

    Read from the file, never a hand-kept copy. Measured 2026-09-29 (I3's hand-off): the
    briefing's own list stopped at the eight stage 8d shipped, and `burning-brush` and
    `smoke` — rows I3 added, which the engine rolls — were rules the model was never told
    it could cite. CLAUDE.md's rule about every copy of a rule, applied by removing the
    copy."""
    from rules import hazards

    return ", ".join(f"{rid} ({row['slot']['name']})"
                     for rid, row in hazards.rows().items())


def with_hazard_rules(text: str) -> str:
    return text.replace(HAZARD_TOKEN, hazard_rules_line()) if HAZARD_TOKEN in text else text


def call_one_messages(briefing_scene: str, history: list[dict], player_input: str,
                      in_combat: bool = False, enemy: str | None = None,
                      examples: list[dict] | None = None,
                      report: dict | None = None,
                      extra_briefing: str = "",
                      player_message: dict | None = None,
                      ledger: list[dict] | None = None,
                      briefing: str | None = None) -> list[dict]:
    """The turn prompt, in one of two modes.

    Out of a fight the model is shown long examples and asked to build a scene. In one it
    is shown short ones and asked to keep up. Same protocol, same ops, same refs — only
    the pace of the prose and the examples that teach it change.

    The combat examples *replace* rather than extend, deliberately. Showing both sets in a
    fight would put nine hundred characters of cellar-and-weather in front of a model
    being asked for three sentences, and demonstration volume is what wins.

    `briefing` replaces the turn briefing for a prose call that is not writing an
    ordinary turn — the intimate scene's (`INTIMATE_BRIEFING`, gm/intimate.py).
    """
    if briefing is None:
        briefing = with_hazard_rules(BRIEFING) + (COMBAT_BRIEFING_EXTRA if in_combat else "")
    # An explicit set replaces both — Continue is the caller that passes one, and its
    # examples have to be the only scene-shaped thing the model can see.
    if examples is None:
        examples = COMBAT_EXAMPLES if in_combat else EXAMPLES

    system = briefing + "\n\n" + briefing_scene + (("\n" + extra_briefing)
                                                   if extra_briefing else "")
    head = [{"role": "system", "content": system}]
    shown: list[dict] = []
    for ex in examples:
        shown.append({"role": "user", "content": fill_enemy(ex["player"], enemy)})
        shown.append({"role": "assistant",
                      "content": fill_enemy(json.dumps(ex["reply"]), enemy)})
    tail = [player_message or {"role": "user", "content": player_input}]
    return pack(head, shown, list(history), tail, report=report, ledger=ledger)


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
                          in_combat: bool = False, enemy: str | None = None,
                          report: dict | None = None,
                          ledger: list[dict] | None = None) -> list[dict]:
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
                                 in_combat=in_combat, enemy=enemy, report=report,
                                 ledger=ledger)
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


# The Continue button's line, written here rather than typed by the player, and kept
# beside the examples that teach it because the two only work together.
CARRY_ON = ("I take no action. Carry the scene on from where it stopped: if I asked "
            "somebody something, let them answer in their own words, and let the people "
            "and the place here go on doing what they were doing.")

# The answer a beat owed and did not give (`GMAgent._answer_the_question`, owner
# 2026-10-01). One person's spoken reply and nothing else, so the call is small: a few
# hundred tokens against a whole beat's rewrite, and it cannot lose the beat it is added to.
ANSWER_MAX_CHARS = 420
ANSWER_NUM_PREDICT = 220


def answer_schema() -> dict:
    return {"type": "object",
            "properties": {"answer": {"type": "string", "maxLength": ANSWER_MAX_CHARS}},
            "required": ["answer"]}


def answer_messages(name: str, player_line: str, beat: str, brief: str) -> list[dict]:
    """Ask for `name`'s spoken answer to the player's line, grounded in the brief."""
    system = (
        f"You write one line of dialogue in a tabletop game narrated to the player as "
        f"\"you\". The player asked {name} something, and the scene stopped before "
        f"{name} answered. Write ONLY {name}'s spoken answer: one to three sentences of "
        f"speech inside double quotation marks, with at most a short tag naming "
        f"{name}, in the present tense, shaped like this: \"The cook owes me a favour,\" "
        f"{name} says. \"Ask for her at the back.\" Answer what was asked. Use only what the scene brief says {name} "
        f"knows; if {name} does not know, they say so, or hedge, or name a price. Name "
        f"no person and no place the brief does not name. Do not narrate the player, do "
        f"not decide what the player does, and do not ask the player what they do.")
    user = (f"SCENE BRIEF:\n{str(brief or '')[:6000]}\n\n"
            f"THE SCENE SO FAR:\n{beat}\n\n"
            f"THE PLAYER:\n{player_line}\n\n"
            f"Write {name}'s answer.")
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


# The deeds a beat skipped (`GMAgent._show_declared`, owner 2026-10-01): the player's own
# words for what they did, played out, and nothing else. Small for the same reason the
# answer call is: it writes two or three sentences and cannot lose the beat it goes into.
DEEDS_MAX_CHARS = 480
DEEDS_NUM_PREDICT = 240


def deeds_schema() -> dict:
    return {"type": "object",
            "properties": {"passage": {"type": "string", "maxLength": DEEDS_MAX_CHARS}},
            "required": ["passage"]}


# One demonstration per placement, so it is the SHAPE that carries — the deed, the body,
# the person it is done to — and never the furniture (this file's own lesson: the
# examples' furniture gets copied). The move one stops at the turn away: the walk is
# already on the page after it. It holds hands and a shoulder and NO place on purpose:
# the first version thanked a smith at his anvil, and one replay of the owner's turn in
# seven walked out "through the heavy oak entrance of the local smithy" of a tavern.
_DEEDS_SHAPE_MOVE = ("You take his hand, thank him, and clap him once on the shoulder "
                     "before you turn away.")
_DEEDS_SHAPE_HERE = ("You tear the hem from your shirt in two long strips and bind his "
                     "forearm tight, knotting it off with your teeth.")


def deeds_shape(before_move: bool) -> str:
    return _DEEDS_SHAPE_MOVE if before_move else _DEEDS_SHAPE_HERE


def deeds_messages(deeds: list[str], player_line: str, beat: str, where: str,
                   people: list[str], *, before_move: bool,
                   harmless: bool = False, already: list[str] | None = None) -> list[dict]:
    """Ask for the declared deeds the beat skipped, as they play out, in order.

    `already` is what the beat DID write of the player's line. Measured on the owner's
    turn replayed: twice in four the beat had the smack and not the thanks, and the
    passage asked for the thanks wrote the smack again as well — the player's whole line
    is in front of it. Named here, and refused in `GMAgent._deeds_refusal` if it is
    written anyway."""
    shape = deeds_shape(before_move)
    system = (
        "You write one short passage of a tabletop game narrated to the player as \"you\", "
        "in the present tense. The player said what their character does, and the scene "
        "as written skipped part of it. Write ONLY the part it skipped, as it happens, in "
        "the player's order: one or two sentences, the hands and the body and the person "
        f"it is done to, shaped like this: {shape} "
        + ("It happens where they are now, before they set off: do not walk them anywhere "
           "and do not describe where they arrive. " if before_move else "")
        + ("It hurts nobody: no wound, no blood, no injury. " if harmless else "")
        + "Name nobody the scene does not name. Do not invent what anyone says back, and "
        "do not ask the player what they do.")
    named = ", ".join(people) if people else "nobody by name"
    user = (f"WHERE IT HAPPENS:\n{str(where or '')[-1400:]}\n\n"
            f"PEOPLE THERE: {named}\n\n"
            f"THE SCENE AS WRITTEN, WHICH SKIPPED IT:\n{str(beat or '')[:1600]}\n\n"
            f"THE PLAYER SAID: {player_line}\n\n"
            + ("ALREADY WRITTEN, DO NOT WRITE IT AGAIN:\n"
               + "\n".join(f"- {d}" for d in already) + "\n\n" if already else "")
            + "WRITE ONLY THIS, IN THIS ORDER:\n" + "\n".join(f"- {d}" for d in deeds))
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


# Continue's own demonstrations, and they REPLACE the turn examples rather than extend
# them — the same choice, for the same reason, that the combat set replaces them.
#
# Measured live on 2026-09-04, five presses of Continue out of five: the player was at a
# public ritual in a market, and every beat put them shoulder-first against a door into
# a room the scene does not contain — a cellar, a vestibule, a store of timber and
# grain. Not copied words: `build_echo_index` found zero shared six-word phrases, so the
# lexical detector could not see it and honestly cannot. It is the *situation* being
# copied. Worked example 11 is "I put my shoulder to the door and force it", it ends on
# "Do you take it?" with the shove still in the air, and it is the last thing the model
# is shown before the player's line. Told to "carry the scene on from where it stopped",
# a model with no demonstration of what that means completes the nearest stopped thing
# in front of it.
#
# So Continue is shown what it looks like: nobody acts, nothing new arrives, the place
# and the people already here go on. Every one ends by handing the turn back, and none
# of them opens a door.
# RULING 2026-09-18 (docs/playtest-2026-09-18.md, item 23): "Continue should work as I
# have nothing to add and continue the scene, not as nobody does anything. My character
# should keep doing whatever he is doing and the scene should move forward without any
# addition from me … if I keep hitting continue the fight should play out further and
# further, even coming to an end, having the authorities called." The three examples
# that stood here demonstrated the inverse — "nobody fills the gap", "he waits", "nothing
# has been decided either" — and, measured in the brothel, the model wrote exactly that
# seven beats running. These show a standing action HELD while the world moves a beat:
# the person in front of the player goes on with what they were doing and the next thing
# happens; none shows a stalled room.
CARRY_ON_EXAMPLES: list[dict] = [
    {
        "player": CARRY_ON,
        "reply": {"narration": (
            "You keep the bellows going, the same slow stroke, and the coals answer with "
            "the same dull orange. Behind you the argument by the gate has stopped being "
            "an argument: the taller man has the other by the front of his coat, and the "
            "first punch lands wet. The smith does not look up from the tongs. Somebody "
            "in the yard shouts for the watch, and somebody else shouts that there is no "
            "watch on a rest-day, and the two on the floor go on hitting each other in "
            "the dust between the anvil and the trough. What do you do?")},
    },
    {
        "player": CARRY_ON,
        "reply": {"narration": (
            "He takes his time about it, but he does answer. <say who=c1 to=you>'Two days,'</say> he says, still "
            "working the strap. <say who=c1 to=you>'The cart comes on the third, and it comes with men on "
            "it.'</say> He tests the buckle, finds it holds, and sets the harness on the rail "
            "beside the other two. His girl comes out with the pail and stops when she "
            "sees you, then goes on to the trough as if she had not. The rain has got "
            "into the ruts. <say who=c1 to=you>'If you are still here on the third,'</say> he says, <say who=c1 to=you>'stand where "
            "I can see you.'</say> What do you do?")},
    },
    {
        "player": CARRY_ON,
        "reply": {"narration": (
            "You stay where you are on the step and eat. The line at the gate moves; "
            "whatever was holding it has been settled or given up on, and the carts go "
            "through one after another with the guard waving each on without looking. "
            "The woman beside you finishes her bread, brushes her hands, and stands. "
            "<say who=c2 to=you>'They will want the square cleared by noon,'</say> she says, to you, and goes "
            "down the steps toward the market. Two of the guard come up the street the "
            "other way, and one of them is already looking at you. What do you do?")},
    },
]


# The speaker tags, one copy for both prose briefings — the turn's (`PROSE_AFTER_EXTRA`)
# and the intimate scene's (`INTIMATE_BRIEFING`). CLAUDE.md: a rule with two copies is a
# rule that drifts.
SAY_TAGS = """
When somebody from WHO IS HERE speaks, wrap their words in a tag with their ref, and
to=you when they say it to the player: <say who=c2 to=you>'Two days,'</say> he says.
The tags are taken out before anyone reads the page. The player's own words get no tag.
"""

PROSE_AFTER_EXTRA = """
THIS TURN: the engine has already resolved it, and what it decided is below. Write the
turn as prose — the scene, the people in it, what just happened — and put nothing in the
"intents" list; it must be empty.

What the engine decided is what happened. Do not contradict it, do not add a roll, do not
state a number, and do not invent an outcome it did not give you. If it decided nothing
mechanical, this is a quiet beat: describe the place and the people and hand the turn back.

Write bodies, not summaries. Say what moves, where it goes and what it does: the hand, the
blade, the step, the fall. When a blow lands, show the wound in plain physical words —
where it opened, what broke, the blood and where it runs — never "the violence", "the
chaos" or "the struggle".
""" + SAY_TAGS


# How much of the scene as it stands the prose call is shown, and how much of each beat.
# Two beats: the one being continued and the one before it, so a reply to a question
# still knows what the question was asked in. Trimmed from the front, because the end
# of a beat is where the scene was left.
EARLIER_BEATS = 2
EARLIER_CHARS = 1400


def scene_now(scene) -> str:
    """The scene as it stands this moment, derived from engine state, for the END of
    the prose prompt.

    Measured 2026-09-17 with a screenshot beside it: two dead in the square, the crowd
    scattering, and the beat opened "The market of Vyrakon is a cacophony of commerce".
    The facts were in the brief — in its middle, under the world, the place, the cast.
    Every tradition that beat this derives the description from state at the moment of
    writing rather than carrying it as prose (Inform's room descriptions; a MUD's corpse
    is an object in the room), and every shipped LLM narrator puts its load-bearing note
    LAST, immediately before generation, where *Lost in the Middle* found attention
    highest (docs/narrator-guards.md D6). So: the dead here, who is hostile or friendly,
    whether a fight is running, what the crowd just saw, the standing thread — one
    block, assembled from the same functions the brief uses so the two cannot
    disagree, placed after the tells. Empty when nothing is notable, so a quiet town
    is not told it is quiet every turn.
    """
    if scene is None:
        return ""
    from rules import states as _states

    from . import judgement as _judgement

    facts: list[str] = []
    actors = getattr(scene, "actors", {}) or {}
    if getattr(scene, "in_encounter", False):
        facts.append("a fight is running")
    dead = [a.name for a in actors.values()
            if not a.is_pc and a.name and (a.hp < 0 or a.has_state("state.down.dead"))]
    if dead:
        facts.append(f"dead on the ground here: {', '.join(dead)}")
    down = [a.name for a in actors.values()
            if not a.is_pc and a.name and a.is_down and a.name not in dead]
    if down:
        facts.append(f"down but alive: {', '.join(down)}")
    moods: dict[str, list[str]] = {}
    for a in actors.values():
        if a.is_pc or a.is_down or not a.name:
            continue
        mood = _states.attitude_of(a)
        if mood and mood != "indifferent":
            moods.setdefault(mood, []).append(a.name)
    for mood in ("hostile", "unfriendly", "friendly", "helpful"):
        if mood in moods:
            facts.append(f"{mood} towards the player: {', '.join(moods[mood])}")
    heat = getattr(scene, "heat", None) or {}
    if heat.get("note"):
        facts.append(f"what the crowd just saw: {heat['note']}")
    # What lies at this spot, whose it is and what it was — the props ledger, so a
    # sundered club's pieces stay the challenger's pieces of a club and never become
    # a table (2026-09-18). Inform derives the room's floor from the tree the same way.
    lying = scene.props_here() if hasattr(scene, "props_here") else []
    if lying:
        said = []
        for rec in lying[:6]:
            owner = actors.get(str(rec.get("owner") or ""))
            # A dropped or stolen thing's record is already named for its owner ("the
            # thug's sap", so two thugs' saps are two records); saying it twice is noise.
            whose = (f" ({owner.name}'s)" if owner is not None and not
                     str(rec.get("name", "")).lower().startswith(owner.name.lower())
                     else "")
            said.append(f"{rec.get('name')}{whose}")
        facts.append("lying on the ground here, and nothing else is: " + "; ".join(said))
    # What was agreed in this room, as the engine wrote it when the coin moved: the
    # negotiation and the payment had left the context window and nothing carried the
    # agreement forward (2026-09-18, item 22 — docs/memory-policy.md's gap in its most
    # concrete form). Cleared when the party moves rooms.
    agreed = [str(a) for a in (getattr(scene, "agreements", None) or [])]
    if agreed:
        facts.append("WHAT WAS AGREED here (fact, still standing): " + "; ".join(agreed[-3:]))
    thread = getattr(scene, "thread", None) or {}
    if thread.get("subject"):
        facts.append(f"the player is {thread.get('doing', 'engaged with')} "
                     f"{thread['subject']}")
    if not facts:
        return ""
    return ("THE SCENE AS IT STANDS NOW (engine facts, this moment — the passage "
            "describes this, not an ordinary day here): " + "; ".join(facts) + ".")


def false_claim_block(claim: str) -> str:
    """The engine's word on a claim the player made about what they are.

    Reported with a screenshot, 2026-09-18: "I reveal my true form as a divine being"
    and the prose made it so — mud to glass, a stranger on his knees, "the truth laid
    bare". The player's own design, the same morning: "It should read as my character
    being delusional and the people should see it similarly … people should roll their
    eyes or look at me with pity." The claim is a Bluff now (`judgement.
    inject_false_claim`), its verdict is in the tells above this block, and this is
    the fact the prose writes from. Last in the prompt, with the other things the
    beat must not get wrong.
    """
    claim = " ".join(str(claim or "").split())
    if not claim:
        return ""
    return (f"A CLAIM THE ENGINE HOLDS FALSE: the player has declared that they {claim}. "
            f"Nothing on their sheet makes it so, and NOTHING HAPPENED. Write what they "
            f"actually did — the words said aloud, the gesture, the coat thrown open — "
            f"and that the world stayed exactly as it was: no light, no change, no "
            f"power. The people here saw somebody claim to be what they plainly are "
            f"not, and they react as people do. If the Bluff in the tells above "
            f"SUCCEEDED, they take it for now, and they treat the player the way the "
            f"tells say they now feel about them — warmer or colder, and why. If it "
            f"FAILED, or there was no roll, nobody believes a "
            f"word: pity, a short laugh, an exchanged look, somebody finding something "
            f"else to look at, somebody saying so to their face. Never make the claim "
            f"true. Nobody kneels.")


def call_prose_messages(briefing_scene: str, history: list[dict], player_input: str,
                        tells: list[str], in_combat: bool = False,
                        enemy: str | None = None,
                        earlier: list[str] | None = None,
                        ledger: list[dict] | None = None,
                        scene_now_block: str = "", pull: str = "",
                        claim: str = "", scene_mode: str = "",
                        demonstrations: list[dict] | None = None,
                        before_leaving: list[str] | None = None) -> list[dict]:
    """Write the whole turn, after the dice.

    `before_leaving` is the player's own words for each deed they declared before a move
    this turn (`narration.owed_deeds`, `before_move`); on an arrival it opens the block.

    `scene_mode` is `intimate.decide`'s verdict for this beat: "intimate" swaps in the
    intimate scene's briefing, its note at the end, and `demonstrations` (the owner's
    passages as example turns, possibly none) for the worked examples; "fade" forces the
    fade line because a child is present or named; "" is the ordinary turn.

    The *call-one* briefing and examples, not the consequence ones, because this is being
    asked for a scene rather than for two sentences about a blow — the consequence prompt
    demonstrates brevity, and demonstration volume is what wins.

    The engine's tells go in as facts the prose has to honour. When there are none the
    turn was a quiet beat, which still needs writing: a `narrate_only` turn producing no
    prose at all is an empty page, and most town turns are `narrate_only`.
    """
    said = "\n".join(f"- {t}" for t in tells if t)
    # An arrival is a different kind of paragraph from a beat, and it was being written
    # as a beat. Asked for 2026-09-22: "describes all the places i needed to move
    # through to get there then describes positionally where i am ... what's around me
    # and where I can go ... then the buying and selling the sounds and smells and
    # finally hone in on some specific action or actions that the PC sees or hears".
    #
    # Fired off the engine's own tell and not a flag, so it can never disagree with
    # what happened: `_op_travel` says "You are at X now." and nothing else does.
    # Deliberately NOT a five-sentence skeleton — this file's own rule is that the
    # shape of a prompt becomes the shape of the output, and a numbered template would
    # produce five identical arrivals. It names what the passage owes the player and
    # leaves the sentences alone; the facts it draws on are all in the brief already
    # (the way there in the tells, UNDERFOOT, NEXT DOOR, and the roster).
    arriving = any(" now." in t and "You are at " in t for t in tells if t)
    arrival = (
        "THIS TURN THE PARTY ARRIVED SOMEWHERE. Walk them in: the places the engine "
        "says the way ran through are places they passed through, in order, and each "
        "is worth a clause; then where they are standing in this one and what is "
        "within reach of them; then what is going on around them — the work, the "
        "trade, the noise and the smell of it. End on ONE particular thing close "
        "enough to touch or speak to: somebody the brief names doing something, or, "
        "when the brief names nobody here, something of the place itself. Only places "
        "and people the brief names. They have ARRIVED — the walk is behind them, and "
        "the passage must not leave them still on their way there." if arriving else "")
    # And when the player did something BEFORE setting off, the block above was the whole
    # of the problem the owner reported (2026-10-01): "i thank her smack her butt and then
    # leave" opened "The door to the tavern swings shut behind you". A block whose first
    # words are "Walk them in" gets a passage whose first words are the walk — measured
    # on the owner's own turn replayed four times, three drafts opened at the departure
    # or the arrival and none wrote the thanks. So the block's FIRST element is now the
    # deeds, in the player's words and order, with one sentence of the shape (from far
    # away, so it is the shape that carries); the walk-in follows them. The deeds come
    # from the same reading `_show_declared` holds the finished beat to.
    #
    # No demonstration inside the block, measured: with one sentence of the shape here,
    # two replays in eleven copied it — once its smithy as the place they walked out of,
    # once the sentence word for word as the opening ("You take his hand, thank him, and
    # clap him once on the shoulder", to a woman). Last in the prompt is the most copied
    # place there is; the order of the block is the shape, and the player's own words are
    # the only content in it.
    if arriving and before_leaving:
        deeds = "; then ".join(f'"{d}"' for d in before_leaving)
        arrival = (
            "THIS TURN THE PLAYER DID THINGS WHERE THEY WERE, AND THEN LEFT. Open where "
            f"they were, with them doing it, in this order: {deeds} — played out there, "
            "with the person it was done to, before anybody takes a step. Only then the "
            "leaving. " + arrival)
    # "End on ONE particular thing one particular PERSON is doing" was this paragraph's
    # last demand, made whatever the brief said — and at the crossroads, where the scene
    # held only the PC, the model supplied the person: "a laborer… struggling with a
    # heavy crate… looks up as you approach" (live, 2026-09-29; docs/fix-interfaces.md,
    # deferred row). The shape of a prompt is the shape of its output; the demand now
    # names its own way out, and `gm/checks/absent_person.py` holds the page to it.
    # The scene as the player last read it, in front of the model that continues it.
    # This call had NO history at all — `[]` at the call site, and the opening was
    # never in the history either — and on the player's own first turn, 2026-09-05,
    # "I ask what is going on" in a sunlit market came back as "You shoulder the door,
    # and it groans": worked example eleven, the nearest scene the model had been shown.
    # The narrator continues what is in front of it.
    stood = [b[-EARLIER_CHARS:] for b in (earlier or []) if b][-EARLIER_BEATS:]
    # Not on an arrival. The block below calls the earlier beats "the scene as it stands,
    # which you are continuing", and after a move that scene is the one the party LEFT.
    # Measured in the 2026-09-29 caravan save (borin-achereth-3, beat 6): arriving at
    # the outskirts, the passage put "a man… struggling with a heavy crate of timber…
    # looks up as you approach" there — the crossroads' laborer, carried over word for
    # word from the beat before (the deferred "continuity slip" row of
    # docs/fix-interfaces.md). Inform's Standard Rules do the same on a move: the
    # "describe room gone into rule" writes the new room afresh rather than continuing
    # the old one. The places passed through are in the tells, which is all of the old
    # scene an arrival owes.
    if arriving:
        stood = []
    scene = ("What you narrated just before this — the scene as it stands, which you "
             "are continuing, not restarting:\n\n" + "\n\n".join(stood) + "\n\n"
             if stood else "")
    # Built BEFORE packing, both of them. This function used to call
    # `call_one_messages` and then rewrite its system message and its last user message
    # to bigger ones, which meant the prompt grew after the budget had already decided
    # it fitted — the tells and up to two earlier beats arriving behind the check. The
    # head and the tail are assembled here and handed to `pack` as what they really are.
    # The two blocks that go LAST, after the tells: the scene as it stands this moment
    # (`scene_now`) and the one open matter nearest to hand (`rules.cards.thread_to_pull`).
    # Last on purpose — the industry's author's-note slot, and the position *Lost in
    # the Middle* measured as best attended after the very start.
    final = {
        "role": "user",
        "content": (scene + f"The player said: {player_input}\n\n"
                    + (f"What the engine decided:\n{said}" if said
                       else "The engine decided nothing mechanical this turn.")
                    + (f"\n\n{arrival}" if arrival else "")
                    + (f"\n\n{scene_now_block}" if scene_now_block else "")
                    + (f"\n\n{pull}" if pull else "")
                    + (f"\n\n{claim}" if claim else "")),
    }
    if scene_mode == "intimate":
        # The Author's-Note slot: the very end of the last message, after the tells and
        # the scene as it stands (gm/intimate.py has the sources). The restrained worked
        # examples are replaced, not joined, by the owner's passages — the combat and
        # Continue sets replace them for the same reason — and with no passages on file
        # the model is shown no scene-shaped reply at all rather than the wrong one.
        final = {"role": "user",
                 "content": final["content"] + "\n\n" + intimate_note(bool(demonstrations))}
        return call_one_messages(
            briefing_scene, history, player_input, in_combat=False, enemy=enemy,
            examples=list(demonstrations or []),
            extra_briefing=SAY_TAGS, player_message=final, ledger=ledger,
            briefing=INTIMATE_BRIEFING)
    return call_one_messages(
        briefing_scene, history, player_input, in_combat=in_combat, enemy=enemy,
        examples=(CARRY_ON_EXAMPLES if player_input == CARRY_ON else None),
        extra_briefing=PROSE_AFTER_EXTRA + content_line(fade=scene_mode == "fade"),
        player_message=final, ledger=ledger)


def content_line(fade: bool = False) -> str:
    """The table's content setting as one line of the prose briefing (item 22).

    The app had taken no position, so whether a paid encounter happened was whatever
    the guards did by accident. Now it is the table's: "fade" is a designed transition —
    time passes, the scene resumes after — and "explicit" writes the scene. Read live,
    so a change on the shelf page holds from the next beat.

    `fade` forces the fade line at an explicit table: a child is present or named in the
    scene (`intimate.decide`), and adults-only is enforced in code, not left to the
    sentence below asking for it."""
    from rules import houserules

    if houserules.content() == "explicit" and not fade:
        # Asked for 2026-09-25: the narrator "shies away ... by being metaphorical"; the
        # table wants intimate scenes written as vividly as the fights, in the body.
        # Adults only, without exception — the population holds children now
        # (rules/lives.py), so the rule is stated here and checked in code after the
        # prose (`narration.intimate` with the scene's minors, in `views._finish`).
        return ("\nThis table permits adult content. When a scene between adults turns "
                "to intimacy, write it vividly and in the body — the physical actions, "
                "touch, breath and bodies described plainly, not in metaphor — and go on "
                "with the scene. Never anyone who is a child, in any way.\n")
    return ("\nWhen a scene turns to intimacy, fade to black: say in one sentence that "
            "time passes, then pick the scene up afterwards — never stall it, never "
            "replace what the people were doing with the room's weather.\n")


# How long the intimate passage is asked to run: 3,000 characters, the owner's figure
# (2026-10-01, "can we raise the limit for the text generation to 3000"). What held the
# owner's original beats to 665 and 709 characters was not a cap at all — it was the
# worked examples, none of them over 822 characters, which this beat no longer shows.
#
# 3,000 cannot go through the grammar: `maxLength` stops compiling between 2,000 and
# 2,100 on both models measured (GRAMMAR_MAXLENGTH_CEILING). So this beat's schema has
# no `maxLength` (`prose_schema(unbounded=True)`) and is bounded by the token budget
# instead, `INTIMATE_NUM_PREDICT`: 3,000 characters is about 800 tokens at the measured
# 3.8 characters a token, and the JSON object around it and the suggestions take the
# rest. A reply the budget does cut off is salvaged and trimmed to its last whole
# sentence (`intimate.narration_from_cut_reply`, `narration.trim_unfinished`).
#
# History, so the number is not re-learned: 1,700 was asked first under the 1,800
# grammar ceiling, and the first live briefed beat ran straight to the ceiling and was
# closed mid-sentence, losing its hand-back; 1,400 followed, before the owner raised it.
INTIMATE_LENGTH = 3000
INTIMATE_NUM_PREDICT = 1100

# The prose briefing for ONE kind of beat: an intimate scene between adults at a table
# whose content rule is "explicit", detected in code (gm/intimate.py). It replaces the
# turn briefing for that beat rather than adding to it, because the measured failure was
# a 350-character line losing to everything around it (13,103 characters of briefing,
# 13,634 of restrained worked examples). What it keeps is the game's laws: the engine's
# decisions stand and carry no number, names come from the brief, the hand-back. What it
# drops is what fights "plainly, in the body": the four moves (whose PUSH is "the weather
# turns, a door closes" — the room's fire written in place of the people), the shapes,
# the wound-and-blow language, and the op reference this call never uses.
#
# And one law it relaxes, by the owner's ruling of 2026-10-01 ("yes it can speak for the
# character"): in this scene, and only here, the narrator may write what the player's
# character does and says beyond the player's own line. Everywhere else the turn
# briefing's "The player says only what their character does" stands. Measured the same
# day: no check in the pipeline catches the narrator speaking for the player on ANY beat
# — that rule has only ever been the prompt's — so the relaxation is this paragraph, and
# the beat's turn-log row records it (`intimate.EXEMPTIONS`).
#
# Deliberately quotes none of the soft phrases it is written against: the shape of a
# prompt becomes the shape of the output, and a phrase put in front of the model, even
# as a thing to avoid, is a phrase it has been shown.
INTIMATE_BRIEFING = f"""You are the Game Master of a Pathfinder 1st Edition game, \
narrating to one adult player at a table that has asked for adult content written \
explicitly. You narrate and you voice everyone in the scene.

THIS BEAT IS AN INTIMATE SCENE BETWEEN ADULTS. Write it explicitly and in the body. \
Describe the bodies and what they do plainly and directly: name the parts of the body in \
plain words, say what touches what and how, what it feels like, the breath and the sounds, \
and the words the two of them say to each other. Write the act itself. Do not put a \
metaphor, a euphemism or a comparison where the act should be; do not cut away, summarise \
or skip ahead; do not turn from the people to the room, the light or the fire.

In this scene you may write what the player's character does and says, carrying on from \
the player's line in the direction it points: their hands, their body, their words. The \
other person has wants of their own and acts on them, in their own body and their own \
words.

What the engine decided is what happened. Do not contradict it, do not add a roll, and \
never write a number.

Write to the player as "you". Name only the people and places listed below; if you need \
someone new, describe them without a name. Everyone in this scene is an adult. Never \
anyone who is a child, in any way.

This passage may run long: up to about {INTIMATE_LENGTH:,} characters. Then hand it \
back: end by asking what they DO, and offer two or three things they might do next, each \
written as the PLAYER'S OWN LINE in the first person, the way they would type it.

Reply with a JSON object:
{{"narration": "...", "suggestions": ["...", "..."], "intents": []}}.
The intents list is always empty in this reply.
"""


# What a rewrite of an intimate beat is told to leave alone (`Agent.polish`). The rewrite
# exists to mend one named fault — a recurring phrase, a name — and a softened scene is a
# second change nobody asked for.
INTIMATE_KEEP = ("This passage is an intimate scene between adults, written explicitly "
                 "because this table asked for it. Keep it exactly as explicit and as "
                 "plain as it is: change only what the problem names.")


def intimate_note(shown: bool) -> str:
    """The note that goes LAST in the intimate beat's prompt — the Author's-Note slot
    (gm/intimate.py). `shown`: whether the owner's passages are in front of it."""
    like = (" the way the passages you wrote earlier in this conversation are written —"
            if shown else "")
    return (f"THIS BEAT: an intimate scene between adults, which this table writes "
            f"explicitly. Write it plainly and in the body,{like} the act itself and not "
            f"a figure of speech for it, carrying on from the player's line — you may "
            f"write what their character does and says. Carry on what happened before, "
            f"not the way it was worded. Up to about {INTIMATE_LENGTH:,} characters, "
            f"then ask what they do.")


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


# A creature's turn, demonstrated. The example above is the player's turn — the tell
# names the player and the answer calls them "you" — and it was the ONLY example this
# call had, so on a creature's turn it taught the wrong lesson exactly: the tell's
# subject is "you". Measured 2026-09-27 on the gemma-4-12B fight audit, with the call
# opening "The player said: Borin Lyraxys acts": "You weave through the panicked crowd …
# close the distance to the heavy door" for "Borin Lyraxys moves", and 8 of the 100
# enemy-turn beats in the recorded corpus turned round the same way. Demonstration, not
# instruction: this example has a creature acting and the player on the receiving end,
# the tells already in the player's person, and the creature named in the answer.
# The same ferry as the example above, and nowhere near the shipped world, for the same
# reason: a copied answer must be catchable.
CONSEQUENCE_NPC_EXAMPLE = {
    "user": (
        "It is the ferryman's turn, not the player's. The ferryman acted; the player's "
        "character is \"you\".\n\n"
        "You had already narrated: The ferryman lets go of the rail and comes at you "
        "along the deck with the boathook.\n\n"
        "What the engine decided:\n"
        "- The ferryman's attack misses you.\n"
    ),
    "assistant": (
        "The ferryman swings the boathook flat and hard, and you duck under it; the iron "
        "cracks against the mast behind your head. He drags it back for another try, "
        "breathing hard."
    ),
}


def call_two_messages(narration: str, tells: list[str], because: list[str],
                      player_input: str, *, acting: str = "",
                      pc_name: str = "", manner: str = "") -> list[dict]:
    """The consequence call. `acting` is set on a creature's own turn: then the call
    says whose turn it is instead of "The player said: <creature> acts", shows the
    tells with the player already as "you" (Inform's adaptive text does the same — one
    report, rendered "you" for the player and by name for anyone else, the story's
    viewpoint applied by the system rather than guessed by the writer), and
    demonstrates a creature's turn rather than the player's."""
    if acting and pc_name:
        from .narration import pc_to_second_person

        tells = [pc_to_second_person(t, pc_name)[0] if t else t for t in tells]
    facts = "\n".join(f"- {t}" for t in tells if t)
    why = "\n".join(f"- {b}" for b in because if b)
    if acting:
        opening = (f"It is {acting}'s turn, not the player's. {acting} acted; the "
                   f"player's character is \"you\".\n\n")
        example = CONSEQUENCE_NPC_EXAMPLE
    else:
        opening = f"The player said: {player_input}\n\n"
        example = CONSEQUENCE_EXAMPLE
    content = (
        opening
        + f"You had already narrated: {narration}\n\n"
        + f"What the engine decided:\n{facts}\n"
    )
    if why:
        content += f"\nWhy it was rolled:\n{why}\n"
    # A companion's turn: how they do it, as a fact beside the tells (gm/companions.py
    # `manner_line`; the owner's second ruling, 2026-10-01). Last, as the brief's
    # standing facts are, and in words — never a number.
    if manner:
        content += f"\n{manner}\n"
    return [
        {"role": "system", "content": CONSEQUENCE_BRIEFING},
        {"role": "user", "content": example["user"]},
        {"role": "assistant", "content": example["assistant"]},
        {"role": "user", "content": content},
    ]


# The targeted repair under `wrong-actor`: a creature's turn told the wrong way round.
# One call per beat, and only when the check fired — never a standing cost of a round.
ACTOR_REPAIR_BRIEFING = """You narrated a creature's turn in a fight, and wrote it the
wrong way round: the creature's act was given to the player, or the player's name to the
creature. Rewrite the passage so the creature named is the one who acts, called by its
name, and the player's character is "you" — the one it is done to — and never named.

Keep what happened exactly as the tells say, the voice, and about the same length. Do not
say how any roll turned out beyond what the tells say.

Reply with a JSON object: {"narration": "..."}."""

ACTOR_REPAIR_EXAMPLE = {
    "user": (
        "It was the ferryman's turn, not the player's.\n\n"
        "What the engine decided:\n- The ferryman's attack misses you.\n\n"
        "The passage:\nYou swing the boathook at the stranger on the deck, but it cracks "
        "against the mast.\n\n"
        "The problem: it was the ferryman's turn, and the passage never names the "
        "ferryman — the act is given to \"you\"."
    ),
    "assistant": json.dumps({"narration": (
        "The ferryman swings the boathook at you and it cracks against the mast, a "
        "hand's width from your head.")}),
}


def actor_repair_messages(passage: str, acting: str, tells: list[str],
                          problem: str) -> list[dict]:
    facts = "\n".join(f"- {t}" for t in tells if t) or "- (nothing landed)"
    return [
        {"role": "system", "content": ACTOR_REPAIR_BRIEFING},
        {"role": "user", "content": ACTOR_REPAIR_EXAMPLE["user"]},
        {"role": "assistant", "content": ACTOR_REPAIR_EXAMPLE["assistant"]},
        {"role": "user", "content":
            f"It was {acting}'s turn, not the player's.\n\n"
            f"What the engine decided:\n{facts}\n\n"
            f"The passage:\n{passage}\n\n"
            f"The problem: {problem}"},
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


COMPANION_TURN_BRIEFING = """This one travels with the player and fights on the player's
side. What the player told them is theirs to weigh, as themselves: an ordinary order they
simply do; a dangerous or hateful one they weigh against who they are — do it, do it their
own way, or refuse. A refusal is said in what they do, with a single narrate_only.
Told nothing, they still act, as somebody like them would with a friend in a fight.
However they act, the wind-up shows who they are in how they do it."""


# A companion's turn (gm/companions.py) is shown these INSTEAD of NPC_EXAMPLES, whose
# every attack aims at "pc": a model copying them would have the player's own companion
# strike the player. Demonstration, not instruction (CLAUDE.md) — the owner's ruling is
# that a companion takes spoken orders "as their character dictates they would or would
# not and interpret those orders according to their character as well", and three
# examples show the three answers: an ordinary order done (a devoted construct, done
# literally), a dangerous one weighed and bent (a timid friend keeps to the door they
# were sent to and goes no nearer), and one refused by temper (told to stay back, a
# hot-tempered friend comes anyway). Filled with the real companion, foe and refs, so a
# copied ref is a legal one and a copied name is the right person. The asks repeat the
# shape `companions.turn_facts` writes.
COMPANION_EXAMPLES = [
    {
        "ask": "Round 2. It is {Self} ({Companion}) turn.\nThey are unhurt and their "
               "conditions are: none.\n{Companion} TRAVELS WITH the player and came into "
               "this fight on the player's side. Who {Companion} is (fact): {Companion} "
               "belongs to the player, who claimed them, and is devoted to them: told "
               "plainly, {Companion} does it, as literally as it was said.\nThe fight is "
               "against: {Foe Ref} ({Foe}).\nWhat the player has said to {Companion}, "
               "newest first:\n  - \"{Companion}, take {Foe} down!\"\n{Companion} decides "
               "what to do with that as themselves: do it, do it their own way, or "
               "refuse. The engine decides what lands.\nWhat does {Self} do?",
        "reply": {
            "narration": "{Companion} turns from your side without a sound and goes "
                         "straight at {Foe}, the way a key turns in a lock.",
            "intents": [{"op": "attack", "actor": "{Self}", "target": "{Foe Ref}",
                         "because": "it was told to, and it does what it is told"}],
        },
    },
    # The owner's second ruling (2026-10-01): "they can comply but it should be narrated
    # that they did so in a way that was timid and matched their background." This
    # example used to show the timid friend bending the order to holding the door —
    # the only obeyed-timidly shape the model saw was a refusal. Now the order is done,
    # and the manner is in the verbs (swallows, edges, half-shut eyes) and in their trade
    # (a carter swings what a carter swings), never in the word "timid".
    {
        "ask": "Round 3. It is {Self} ({Companion}) turn.\nThey are unhurt and their "
               "conditions are: none.\n{Companion} TRAVELS WITH the player and came into "
               "this fight on the player's side. Who {Companion} is (fact): {Companion} "
               "is friendly towards the player — a friend who came along, not a servant, "
               "and free to say no. {Companion} is cautious, timid. in how they act: "
               "keeps a door at their back and a reason to leave ready. {Companion} is a "
               "drover by trade.\nThe fight is against: {Foe Ref} ({Foe}).\nWhat the "
               "player has said to {Companion}, newest first:\n  - \"{Companion}, hit "
               "him! Now!\"\n{Companion} decides what to do with that as themselves: do "
               "it, do it their own way, or refuse. The engine decides what lands.\nWhat "
               "does {Self} do?",
        "reply": {
            "narration": "{Companion} swallows hard and edges in at your shoulder, one "
                         "glance back at the way out, then swings at {Foe} the way you "
                         "would swing at a kicking mule — both hands, eyes half shut, "
                         "already flinching from the answer.",
            "intents": [{"op": "attack", "actor": "{Self}", "target": "{Foe Ref}",
                         "because": "told to, and does it, though every part of them "
                                    "wants to be at the door"}],
        },
    },
    {
        "ask": "Round 2. It is {Self} ({Companion}) turn.\nThey are lightly hurt and "
               "their conditions are: none.\n{Companion} TRAVELS WITH the player and came "
               "into this fight on the player's side. Who {Companion} is (fact): "
               "{Companion} is helpful towards the player — a friend who came along, not "
               "a servant, and free to say no. {Companion} is short-fused, bold. in how "
               "they act: flares fast, cools fast, and says the worst of it in between."
               "\nThe fight is against: {Foe Ref} ({Foe}).\nWhat the player has said to "
               "{Companion}, newest first:\n  - \"Stay back, I've got this one.\"\n"
               "{Companion} decides what to do with that as themselves: do it, do it "
               "their own way, or refuse. The engine decides what lands.\nWhat does "
               "{Self} do?",
        "reply": {
            "narration": "{Companion} hears you, swears, and comes anyway, grinning like "
                         "it is a fair-day brawl — nobody puts a blade near a friend "
                         "while they stand and watch.",
            "intents": [{"op": "attack", "actor": "{Self}", "target": "{Foe Ref}",
                         "because": "told to leave this one to you; too hot-tempered "
                                    "to do as told"}],
        },
    },
    # And told nothing at all, which is most rounds. Their nature decides unprompted
    # turns too — and the owner's second ruling (2026-10-01) is that they DO something:
    # "I do also want my companion to take action on their own if i dont direct them."
    # This example used to show a frightened friend hiding behind the player with a
    # narrate_only, and measured before the change (docs in tests/
    # test_companions_manner.py) that was what undirected timid turns copied. Now two
    # undirected friends act, each as themselves: the frightened one darts in from
    # behind the player and straight back; the soft-hearted one pulls the blow — the
    # `lethality` choice, a real rule (a club swung to knock down deals non-lethal at
    # -4), not a flourish of the prose.
    {
        "ask": "Round 1. It is {Self} ({Companion}) turn.\nThey are unhurt and their "
               "conditions are: none.\n{Companion} TRAVELS WITH the player and came into "
               "this fight on the player's side. Who {Companion} is (fact): {Companion} "
               "is friendly towards the player — a friend who came along, not a servant, "
               "and free to say no. {Companion} is easily frightened, quiet. in how they "
               "act: keeps a door at their back and a reason to leave ready.\nThe fight "
               "is against: {Foe Ref} ({Foe}).\nThe player has told {Companion} nothing "
               "this fight; {Companion} does what they would do.\nWhat does {Self} do?",
        "reply": {
            "narration": "Nobody asks it of {Companion}. They hover white-faced at your "
                         "back, then dart out past your elbow at {Foe} and skip straight "
                         "back behind you, breath hitching.",
            "intents": [{"op": "attack", "actor": "{Self}", "target": "{Foe Ref}",
                         "because": "nobody told them to, but {Foe} is on their friend "
                                    "and they will not only watch"}],
        },
    },
    {
        "ask": "Round 2. It is {Self} ({Companion}) turn.\nThey are unhurt and their "
               "conditions are: none.\n{Companion} TRAVELS WITH the player and came into "
               "this fight on the player's side. Who {Companion} is (fact): {Companion} "
               "is helpful towards the player — a friend who came along, not a servant, "
               "and free to say no. {Companion} is warm, kind. in how they act: cannot "
               "pass somebody in trouble without stopping.\nThe fight is against: "
               "{Foe Ref} ({Foe}).\nThe player has told {Companion} nothing this fight; "
               "{Companion} does what they would do.\nWhat does {Self} do?",
        "reply": {
            "narration": "{Companion} goes in on their own, wincing, and turns the swing "
                         "at {Foe} so it will knock him down rather than open him up.",
            "intents": [{"op": "attack", "actor": "{Self}", "target": "{Foe Ref}",
                         "params": {"lethality": "nonlethal"},
                         "because": "will not stand by while you are hurt, and will not "
                                    "kill to stop it"}],
        },
    },
    # And "would not" (the first ruling: "as their character dictates they would or
    # would not"): what a friend refuses is what goes against who they are, not merely
    # what frightens them — the timid one above obeys, shaking. A soft-hearted friend
    # told to finish a beaten man will not, and says so in what they do.
    {
        "ask": "Round 4. It is {Self} ({Companion}) turn.\nThey are unhurt and their "
               "conditions are: none.\n{Companion} TRAVELS WITH the player and came into "
               "this fight on the player's side. Who {Companion} is (fact): {Companion} "
               "is friendly towards the player — a friend who came along, not a servant, "
               "and free to say no. {Companion} is soft-hearted, quiet. in how they act: "
               "cannot pass somebody in trouble without stopping.\nThe fight is against: "
               "{Foe Ref} ({Foe}).\nWhat the player has said to {Companion}, newest "
               "first:\n  - \"He's done — finish him!\"\n{Companion} decides what to do "
               "with that as themselves: do it, do it their own way, or refuse. The "
               "engine decides what lands.\nWhat does {Self} do?",
        "reply": {
            "narration": "{Companion} lifts the club, looks at {Foe}, and lowers it again, "
                         "wincing — shaking their head at you without a word.",
            "intents": [{"op": "narrate_only",
                         "because": "will fight beside you, but will not kill a beaten "
                                    "man"}],
        },
    },
]


COMPANION_ANSWER_BRIEFING = """The player has just spoken to somebody who travels with
them. Answer for that companion: decide, as themselves, what they do about it, and say it
as intent. Nobody else acts.

Reply with a JSON object: {"narration": "...", "intents": [...]}. The narration is one or
two sentences of what they do in answer; the engine decides whether anything they try
works."""


# Out of a fight there is no turn of theirs to wait for, so the companion answers on the
# player's own beat: the targeted call `GMAgent.companion_answer` makes when the player's
# words are spoken TO a companion (`companions.addressed`). Measured before it existed
# (companions replay, 2026-10-01): "Drover, sneak up behind that thug and lift his purse"
# came back `narrate_only` + the player's `say` — nobody decided anything, and the prose
# had the timid drover slip into the shadows like a cutpurse. Three examples, the same
# three answers as the fight's: done (a construct, literally), refused in their own words
# (a timid friend, a `say`), and done their own way with what could fail rolled — a
# check against whoever could stop them, never a number.
COMPANION_ANSWER_EXAMPLES = [
    {
        "ask": "{Companion} ({Self}) TRAVELS WITH the player. Who {Companion} is (fact): "
               "{Companion} belongs to the player, who claimed them, and is devoted to "
               "them: told plainly, {Companion} does it, as literally as it was said.\n"
               "Here besides: {Other Ref} ({Other}).\nWhat the player just said: "
               "\"{Companion}, keep watch by the door.\"\nWhat does {Self} do about it, "
               "as themselves?",
        "reply": {
            "narration": "{Companion} crosses to the door and turns to face it, and goes "
                         "as still as the post beside it.",
            "intents": [{"op": "narrate_only",
                         "because": "told to keep watch; it keeps watch, exactly there"}],
        },
    },
    {
        "ask": "{Companion} ({Self}) TRAVELS WITH the player. Who {Companion} is (fact): "
               "{Companion} is friendly towards the player — a friend who came along, not "
               "a servant, and free to say no. {Companion} is cautious, timid. in how "
               "they act: keeps a door at their back and a reason to leave ready.\n"
               "Here besides: {Other Ref} ({Other}).\nWhat the player just said: "
               "\"{Companion}, slip round behind {Other} and take the keys off his "
               "belt.\"\nWhat does {Self} do about it, as themselves?",
        "reply": {
            "narration": "{Companion} looks at {Other}, then at you, and does not move "
                         "from the wall.",
            "intents": [{"op": "say", "actor": "{Self}", "target": "{Pc}",
                         "params": {"words": "Me? Not a chance. Ask me for something "
                                             "that won't get my hand broken.",
                                    "to": "{Pc}", "quoted": True},
                         "because": "too frightened to try it, and says so"}],
        },
    },
    {
        "ask": "{Companion} ({Self}) TRAVELS WITH the player. Who {Companion} is (fact): "
               "{Companion} is helpful towards the player — a friend who came along, not "
               "a servant, and free to say no. {Companion} is game for anything, blunt. "
               "in how they act: steps forward before anyone else has decided to.\n"
               "Here besides: {Other Ref} ({Other}).\nWhat the player just said: \"Keep "
               "{Other} talking while I look round the back.\"\nWhat does {Self} do "
               "about it, as themselves?",
        "reply": {
            "narration": "{Companion} plants an elbow on the counter in front of {Other} "
                         "and starts in on a long complaint about the roads, loud enough "
                         "to fill the room.",
            "intents": [{"op": "check", "actor": "{Self}",
                         "params": {"skill": "bluff",
                                    "opposed_by": {"ref": "{Other Ref}",
                                                   "skill": "sense motive"}},
                         "because": "holding the man's eye with talk, their own loud way"}],
        },
    },
    # Told, and done — timidly (the owner's second ruling, 2026-10-01: "they can comply
    # but it should be narrated that they did so in a way that was timid"). The examples
    # above showed a timid friend only refusing; obeying while afraid had no shape.
    {
        "ask": "{Companion} ({Self}) TRAVELS WITH the player. Who {Companion} is (fact): "
               "{Companion} is friendly towards the player — a friend who came along, not "
               "a servant, and free to say no. {Companion} is cautious, quiet. in how "
               "they act: keeps a door at their back and a reason to leave ready.\n"
               "Here besides: {Other Ref} ({Other}).\nWhat the player just said: "
               "\"{Companion}, hold the lamp up so I can see.\"\nWhat does {Self} do "
               "about it, as themselves?",
        "reply": {
            "narration": "{Companion} holds the lamp up at the full stretch of their arm, "
                         "as far from {Other} as the arm allows, and it trembles enough "
                         "to make the shadows jump.",
            "intents": [{"op": "narrate_only",
                         "because": "asked, and does it, nervous of who is watching"}],
        },
    },
]


def companion_answer_messages(briefing_scene: str, ref: str, actor, facts: str,
                              other: tuple[str, str] | None = None,
                              pc_ref: str = "pc") -> list[dict]:
    """The messages for a companion's answer to the player's words, out of a fight."""
    other_ref, other_name = other or ("c9", "stranger")
    fill = dict(self_ref=ref, name=actor.name, foe_ref=other_ref, foe=other_name)

    def filled(value):
        value = fill_companion(value, **fill)
        if isinstance(value, str):
            return (value.replace("{Other Ref}", other_ref)
                    .replace("{Other}", _definite(other_name)).replace("{Pc}", pc_ref))
        return json.loads(json.dumps(value).replace("{Other Ref}", other_ref)
                          .replace("{Pc}", pc_ref)
                          .replace("{Other}", _definite(other_name).replace('"', "'")))

    messages = [{"role": "system",
                 "content": COMPANION_ANSWER_BRIEFING + "\n\n" + briefing_scene}]
    for ex in COMPANION_ANSWER_EXAMPLES:
        messages.append({"role": "user", "content": filled(ex["ask"])})
        messages.append({"role": "assistant", "content": json.dumps(filled(ex["reply"]))})
    messages.append({"role": "user", "content": facts})
    return messages


def fill_companion(value, *, self_ref: str, name: str, foe_ref: str, foe: str):
    """Fill a companion example (a string, or a reply's dict/list) with the real people.
    Filled before the reply is dumped, so a name with a quote in it stays valid JSON; a
    narration that opens on a lower-case name ("the clockwork spy turns…") is
    capitalised."""
    if isinstance(value, dict):
        out = {k: fill_companion(v, self_ref=self_ref, name=name, foe_ref=foe_ref, foe=foe)
               for k, v in value.items()}
        if isinstance(out.get("narration"), str) and out["narration"]:
            out["narration"] = out["narration"][0].upper() + out["narration"][1:]
        return out
    if isinstance(value, list):
        return [fill_companion(v, self_ref=self_ref, name=name, foe_ref=foe_ref, foe=foe)
                for v in value]
    if not isinstance(value, str):
        return value
    return (value.replace("{Self}", self_ref).replace("{Companion}", _definite(name))
            .replace("{Foe Ref}", foe_ref).replace("{Foe}", _definite(foe)))


def npc_turn_messages(briefing_scene: str, history: list[dict], ref: str,
                      actor, round_no: int, first: str = "",
                      companion: str = "", foe: tuple[str, str] | None = None
                      ) -> list[dict]:
    """The messages for one creature's own turn.

    `companion`: the facts a companion's turn is told (`gm/companions.turn_facts`) — who
    they are and what the player said to them. With it, the companion examples replace
    the creature examples, filled with `foe` (ref, name) — the first standing foe."""
    hp_note = "unhurt"
    if actor.hp < actor.hp_max:
        share = actor.hp / max(1, actor.hp_max)
        hp_note = ("badly hurt" if share <= .34 else
                   "bloodied" if share <= .67 else "lightly hurt")
    conditions = ", ".join(c.name.lower() for c in actor.conditions) or "none"
    # What is in the hand, as a fact beside the hit points. Measured live 2026-09-27: a
    # thug swung his sap three rounds running and every wind-up had him grabbing,
    # pinning and seizing — nothing in this prompt said he held anything. A bare hand
    # says nothing: a wolf's "unarmed" is its jaws, not empty hands.
    # And what the thing IS (`weapons.described`): told only "the sap", the model wrote
    # a vial of tree sap splashing on the floor.
    from rules import weapons as _weapons

    held = str(getattr(actor, "equipped", "") or "").strip()
    gloss = _weapons.described(held) if held else ""
    holding = (f"In hand: the {held}" + (f" ({gloss})" if gloss else "") + ".\n"
               if held and held.lower() not in ("unarmed", "none") else "")
    briefing = NPC_TURN_BRIEFING + (("\n\n" + COMPANION_TURN_BRIEFING) if companion else "")
    messages = [{"role": "system", "content": briefing + "\n\n" + briefing_scene}]
    if companion:
        foe_ref, foe_name = foe or ("c2", "stranger")
        fill = dict(self_ref=ref, name=actor.name, foe_ref=foe_ref, foe=foe_name)
        for ex in COMPANION_EXAMPLES:
            messages.append({"role": "user", "content": fill_companion(ex["ask"], **fill)})
            messages.append({"role": "assistant",
                             "content": json.dumps(fill_companion(ex["reply"], **fill))})
    # The acting creature is its own {Current Enemy}: an example the model copies now
    # describes the animal whose turn it is, not a thug it was once shown.
    for ex in ([] if companion else NPC_EXAMPLES):
        messages.append({"role": "user", "content": fill_enemy(ex["ask"], actor.name)})
        messages.append({"role": "assistant",
                         "content": fill_enemy(json.dumps(ex["reply"]), actor.name)})
    # What the creature fights with, by the names its stat block prints and nothing
    # else: no bonus and no dice, because the model never authors a number. Without it
    # the model guessed — a "club" for an ogre whose line says greatclub — and the
    # engine now refuses a weapon the block does not print (2026-09-27), so an unnamed
    # attack list cost a retry. Ground every name.
    printed = [a["key"] for cat in ("melee", "ranged")
               for opt in (actor.stat_block_attacks().get(cat) or ())
               for a in opt] if hasattr(actor, "stat_block_attacks") else []
    # "Their", matching the "They are" above it. It first read "Its attacks", and the
    # audit that followed had NPC turns calling a barkeep "it" in 12 of 23 where the
    # run before had 1 of 12 — not proven to be this line, not worth the risk either.
    arms = (f"Their attacks, by weapon name: {', '.join(dict.fromkeys(printed))}.\n"
            if printed else "")
    messages.append({"role": "user", "content":
        f"Round {round_no}. It is {ref} ({actor.name}) turn.\n"
        f"They are {hp_note} and their conditions are: {conditions}.\n"
        f"{arms}"
        + (f"{first}\n" if first else holding)
        + (f"{companion}\n" if companion else "")
        + f"What does {ref} do?"})
    return messages


# --- a companion's manner, repaired -----------------------------------------------------
#
# The targeted call under `companions.shows_manner` (the owner's second ruling,
# 2026-10-01: "narrated that they did so in a way that was timid and matched their
# background"). Only the companion's own sentences go in, and only when the page carried
# no cue of their temper at all. The answer is kept only if the act is unchanged
# (`companions.act_kept`): a manner rewrite that lands a blow, loses a deed or adds a
# person is thrown away and the beat stands as written.
MANNER_REPAIR_BRIEFING = """You narrated what somebody did, and it reads as if anybody
could have done it. Rewrite each sentence you are given so that HOW they do it shows who
they are — in the verbs and the small details, never by naming the trait. Keep exactly
what they do, to whom, and how it turned out; add nobody; no numbers. About the same
length, a few words longer at most.

Reply with a JSON object: {"s1": "...", "s2": "..."} — one rewritten sentence per key."""

# Ways each temper comes out in a deed, offered to the repair as a menu rather than a
# rule — the model picks one that fits the sentence. Several per temper, because the shape
# of a prompt becomes the shape of the output: one suggestion would be every repair.
MANNER_HINTS = {
    "timid": "a hesitation first, a swallow, a glance at the way out, hands that shake, "
             "flinching, edging in, eyes half shut, darting back",
    "bold": "no hesitation, a grin, straight in, eagerness, a laugh, going in first",
    "hot_tempered": "a curse, a snarl, teeth gritted, fury, a yell",
    "placid": "calm, unhurried, steady, deliberate, as if it were a chore",
    # Not "pulling the blow": whether a blow is pulled is the `lethality` rule's, and a
    # repair offered it wrote "pull the blow" over a lethal swing (replay, 2026-10-01).
    "kind": "a wince, a muttered apology, looking away, a grimace, regret",
    "hard": "coldly, flatly, without a flicker, efficient, grim",
    "reserved": "silently, without a word, a single nod, quietly",
    "gregarious": "talking all the while, calling out, a joke, a cheer",
    "proud": "a flourish, chin up, making sure you saw",
    "suspicious": "warily, watching the hands, a sidelong look, narrowed eyes",
    "blunt": "flatly, plainly, without ceremony",
    "orderly": "precisely, methodically, squaring up first, careful",
    "devout": "a muttered prayer, a sign against harm, the gods' name",
    "devoted": "without a sound, mechanically, exactly as told, a click of joints, "
               "unhesitating, like a mechanism",
}

MANNER_REPAIR_EXAMPLE = {
    "user": (
        "Who does it: the ferry boy (fact): by nature cautious and quiet — keeps a door at "
        "their back and a reason to leave ready; a ferry hand by trade; does this ONLY "
        "because he was told to, against his own nerve.\n"
        "Ways it could show: a hesitation first, a swallow, a glance at the way out, "
        "hands that shake, flinching, edging in\n\n"
        "s1: The ferry boy swings the oar at the smuggler and it cracks against his "
        "shoulder."),
    "assistant": json.dumps({
        "s1": "The ferry boy swallows, edges closer, and swings the oar at the smuggler "
              "with shaking hands; it cracks against his shoulder."}),
}


def manner_repair_messages(sentences: list[str], name: str, manner: str,
                           pole: str) -> list[dict]:
    asks = "\n".join(f"s{i}: {s}" for i, s in enumerate(sentences, 1))
    return [
        {"role": "system", "content": MANNER_REPAIR_BRIEFING},
        {"role": "user", "content": MANNER_REPAIR_EXAMPLE["user"]},
        {"role": "assistant", "content": MANNER_REPAIR_EXAMPLE["assistant"]},
        {"role": "user", "content":
            f"Who does it: {name} (fact): {manner}\n"
            f"Ways it could show: {MANNER_HINTS.get(pole, '')}\n\n{asks}"},
    ]


# --- a companion speaks up, unasked ------------------------------------------------------
#
# The owner, 2026-10-01: "they should also interject their opinions on the things going on
# or the places we go". WHEN is decided in code (`companions.interjection_due`): arriving
# somewhere, something notable, else a cadence — the shape of Valve's response rules
# (Ruskin, GDC 2012: criteria plus write-back memory with expiry) and of the quirk's
# `quirk_due` here. WHAT is the model's, in their voice, fed only real names and the
# turn's own facts, and checked in code before it goes on the page.
#
# Opinions, never instructions: Valve's Episode One commentary records that Alyx's
# nagging and unsolicited hints made players "hate Alyx" within minutes and were cut,
# while lines that stated a reaction and stepped aside were liked. So the briefing asks
# for what they think or feel, and the line is refused if it hands the turn back.
INTERJECT_BRIEFING = """Somebody who travels with the player speaks up, unasked, about
what is happening or where they are. Write what they say: their own opinion or feeling,
in their own voice, coloured by who they are and what their life has been. Never advice
about what the player should do, never a question to the player about what to do next.

One or two sentences: a small gesture of theirs and their words in quotation marks.
Name only people and places you are given. No numbers.

Reply with a JSON object: {"line": "..."}."""

# Three, about three kinds of moment, nowhere near any shipped world so a copied line is
# caught by the invented-name check: arriving somewhere (a timid carter), something that
# just happened (a hot-tempered friend), and a quiet stretch (a claimed construct, whose
# opinion is an observation).
INTERJECT_EXAMPLES = [
    {
        "user": ("Who speaks: Pell (fact): by nature cautious and quiet — keeps a door at "
                 "their back; a carter by trade; friendly towards the player.\n"
                 "What it is about: the party has just arrived at the Saltmarsh Tollhouse, "
                 "an inn. Pell has never been here before.\n"
                 "People here: Pell, the tollkeeper."),
        "assistant": json.dumps({
            "line": "Pell lingers by the cart a moment longer than he needs to, eyeing the "
                    "shuttered windows. \"Smells like a place where carts go missing.\""}),
    },
    {
        "user": ("Who speaks: Mara (fact): by nature short-fused and plain-spoken — flares "
                 "fast, cools fast; a tanner by trade; helpful towards the player.\n"
                 "What it is about: what just happened — The smuggler is knocked out.\n"
                 "People here: Mara, the smuggler."),
        "assistant": json.dumps({
            "line": "Mara wipes her knuckles on her apron and snorts. \"He'll think twice "
                    "before he grabs a stranger's sleeve again.\""}),
    },
    {
        "user": ("Who speaks: the brass hound (fact): it belongs to the player and is "
                 "devoted; it does what it is told exactly, like a mechanism.\n"
                 "What it is about: a quiet moment — You wait by the gate while the "
                 "ferryman counts his rope.\n"
                 "People here: the brass hound, the ferryman."),
        "assistant": json.dumps({
            "line": "The brass hound's head turns toward the ferryman with a small click. "
                    "\"He has counted the same coil twice.\""}),
    },
]

INTERJECT_MAX_CHARS = 320


def interject_messages(facts: str) -> list[dict]:
    messages = [{"role": "system", "content": INTERJECT_BRIEFING}]
    for ex in INTERJECT_EXAMPLES:
        messages.append({"role": "user", "content": ex["user"]})
        messages.append({"role": "assistant", "content": ex["assistant"]})
    messages.append({"role": "user", "content": facts})
    return messages


def interject_schema() -> dict:
    return {"type": "object", "properties": {"line": {"type": "string"}},
            "required": ["line"]}


# --- a companion confides ----------------------------------------------------------------
#
# The owner, 2026-10-01: "Their wants should appear naturally locked behind their attitude
# toward you. but they shouldnt just blurt out personal feelings without some kind of warm
# up." WHEN, and how much, is gm/confide.py's: a lead-in or a hint (they are NOT told the
# content, so it cannot leak), the share itself, or a bridge from something in the world.
# WHAT is the model's, from facts holding their own life row's words, checked in code.
#
# Two demonstrations per kind, and only the asked-for kind is shown: the shape of a prompt
# becomes the shape of the output (CLAUDE.md), and a lead-in shown beside a share learns
# to share. The life texts here are invented for the examples and are NOT rows of
# content/people/life.json, so a companion who holds a shipped row cannot copy an
# example's confession word for word; no example names anybody the facts did not give.
CONFIDE_BRIEFING = """Somebody who travels with the player says something about their
own life. Write it: a small gesture of theirs and their words in quotation marks, in
their own voice, coloured by who they are.

Say only what the facts give you. When the facts say they do not say what it is, they do
not — only that there is something. When the facts give what they tell, they say that,
in their own words, and invent nothing else about their past: no names, no places, no
numbers.

Never advice, never a question about what the player will do next.

Reply with a JSON object: {"line": "..."}."""

_PELL = ("Who speaks: Pell (fact): by nature cautious and quiet — keeps a door at their back; "
         "Pell is a carter by trade; Pell is {feels} towards the player.")
_MARA = ("Who speaks: Mara (fact): by nature short-fused and plain-spoken — flares fast, cools "
         "fast; Mara is a tanner by trade; Mara is {feels} towards the player.")
_OSSIN = ("Who speaks: Ossin (fact): by nature reserved and steady — speaks when there is "
          "something to say and not otherwise; Ossin is a ferryman by trade; Ossin is {feels} "
          "towards the player.")
_TAMSA = ("Who speaks: Tamsa (fact): by nature warm and talkative — fills a silence before it "
          "settles; Tamsa is a baker by trade; Tamsa is {feels} towards the player.")

CONFIDE_EXAMPLES = {
    "lead-in": [
        {"user": _PELL.format(feels="helpful") + "\nWhat this is: Pell tells the player there "
                 "is something they have wanted to get off their chest — and does NOT say "
                 "what. They will say it later, when the player is listening.\n"
                 "People here: Pell, the tollkeeper.",
         "line": "Pell falls into step beside you and clears his throat twice before he gets "
                 "it out. \"There's a thing I've been meaning to tell you. Not here. When "
                 "it's quieter.\""},
        {"user": _MARA.format(feels="helpful") + "\nWhat this is: Mara tells the player there "
                 "is something they have wanted to get off their chest — and does NOT say "
                 "what. They will say it later, when the player is listening.\n"
                 "People here: Mara.",
         "line": "Mara kicks a stone off the path and doesn't look at you. \"Been carrying "
                 "something around I ought to get off my chest. Later.\""},
    ],
    "hint": [
        {"user": _OSSIN.format(feels="friendly") + "\nWhat this is: something is on Ossin's "
                 "mind, and Ossin is not ready to say it to the player yet. They let slip "
                 "that there is something, and do NOT say what.\nPeople here: Ossin.",
         "line": "Ossin's eyes stay on the water a long moment. \"Something on my mind. "
                 "Not yours to carry yet.\""},
        {"user": _TAMSA.format(feels="friendly") + "\nWhat this is: something is on Tamsa's "
                 "mind, and Tamsa is not ready to say it to the player yet. They let slip "
                 "that there is something, and do NOT say what.\n"
                 "People here: Tamsa, the miller.",
         "line": "Tamsa starts to say something, laughs it off and shakes her head. "
                 "\"Another time. It's nothing, really.\""},
    ],
    "bridge-hint": [
        {"user": _PELL.format(feels="friendly") + "\nWhat this is: the kennel put Pell in "
                 "mind of something of their own. They say the kennel reminds them of "
                 "something, and do NOT say what — not yet.\nPeople here: Pell, the "
                 "houndsman.",
         "line": "Pell slows by the kennel and watches the dogs a moment too long. \"Kennel "
                 "like that reminds me of something. Another time.\""},
        {"user": _MARA.format(feels="friendly") + "\nWhat this is: the shrine put Mara in "
                 "mind of something of their own. They say the shrine reminds them of "
                 "something, and do NOT say what — not yet.\nPeople here: Mara.",
         "line": "Mara stops short of the shrine and her jaw works. \"Places like this "
                 "remind me of something. Not now.\""},
    ],
    "share": [
        {"user": _PELL.format(feels="helpful") + "\nWhat Pell tells the player (fact, "
                 "something they want, now, for themselves, from their own life — say THIS, "
                 "in their own words, and nothing else about their past): to win back the "
                 "cart horse they sold the winter the money ran out\n"
                 "The player has just asked: Go on, Pell. What is it?\n"
                 "Earlier Pell said: \"There's a thing I've been meaning to tell you.\"\n"
                 "People here: Pell.",
         "line": "Pell rubs the back of his neck. \"Sold my old cart horse the winter the "
                 "money ran out. Been putting coin by to buy her back ever since. Daft, I "
                 "know.\""},
        {"user": _MARA.format(feels="helpful") + "\nWhat Mara tells the player (fact, "
                 "something they hope for, one day, from their own life — say THIS, in their "
                 "own words, and nothing else about their past): to see the tannery they "
                 "learned in kept honest when its old master is gone\n"
                 "Earlier Mara said: \"Been carrying something around I ought to get off my "
                 "chest.\" — now, in a quiet moment, they say it.\nPeople here: Mara.",
         "line": "Mara scrubs at a stain on her apron that isn't coming out. \"The tannery "
                 "I learned in. The old master won't last the year, and whoever gets it "
                 "will cut corners. I want it kept honest, that's all.\""},
    ],
    "bridge": [
        {"user": _OSSIN.format(feels="helpful") + "\nWhat Ossin tells the player (fact, "
                 "something they hope for, one day, from their own life — say THIS, in their "
                 "own words, and nothing else about their past): to make one blade fine "
                 "enough to hang over a door\nWhat brought it up: the forge, here. They start "
                 "from the forge and say what it reminds them of.\n"
                 "People here: Ossin, the smith.",
         "line": "Ossin stops at the forge's open side and watches the sparks. \"My father "
                 "kept one like this. I always meant to make one blade fine enough to hang "
                 "over the door.\""},
        {"user": _TAMSA.format(feels="helpful") + "\nWhat Tamsa tells the player (fact, "
                 "something they hope for, one day, from their own life — say THIS, in their "
                 "own words, and nothing else about their past): a family of their own, and a "
                 "table loud enough to need two benches\nWhat brought it up: the children, "
                 "here. They start from the children and say what it reminds them of.\n"
                 "People here: Tamsa, the children.",
         "line": "Tamsa watches the children chase each other round the well and smiles. "
                 "\"I want that, you know. A family of my own, a table so loud we need two "
                 "benches.\""},
    ],
}


def confide_messages(facts: str, kind: str) -> list[dict]:
    messages = [{"role": "system", "content": CONFIDE_BRIEFING}]
    for ex in CONFIDE_EXAMPLES.get(kind) or CONFIDE_EXAMPLES["share"]:
        messages.append({"role": "user", "content": ex["user"]})
        messages.append({"role": "assistant", "content": json.dumps({"line": ex["line"]})})
    messages.append({"role": "user", "content": facts})
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


def prose_schema(min_chars: int = 0, max_chars: int = 0, *,
                 unbounded: bool = False) -> dict:
    """The one-field schema for every call that only writes prose.

    `unbounded=True` puts NO `maxLength` in the grammar, whatever `max_chars` says — the
    one way past GRAMMAR_MAXLENGTH_CEILING, and an explicit flag so that nobody reaches it
    by passing a big number: `max_chars` is still clamped to the ceiling everywhere.
    Used by the intimate scene's beat alone (the owner asked for 3,000 characters,
    2026-10-01), which bounds its reply by `num_predict` instead and salvages a reply
    the budget cut off (`intimate.narration_from_cut_reply`).

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
    # `min_chars` is accepted and deliberately NOT put in the grammar. Measured
    # 2026-09-04 on gemma-4 12B with minLength=800: the grammar compiled and the
    # model, held inside a string it had finished, wrote the rest of the object
    # into it escaped — '", "suggestions": ["Wait for someone to' — on three turns
    # in four; `cut_schema_bleed` trimmed each back to 703-791 characters, under the
    # floor it was meant to guarantee. The floor is `narration.review`'s to report
    # and the repair call's to fix, which lengthened all three to 1,469-1,579.
    if max_chars and not unbounded:
        narration["maxLength"] = min(int(max_chars), GRAMMAR_MAXLENGTH_CEILING)
    # `suggestions` and `intents` are admitted and never read, because the prose call
    # is shown the TURN prompt — twelve worked examples, every one of them a three-key
    # object — and `PROSE_AFTER_EXTRA` then tells the model to leave the intents list
    # empty, which is a sentence that only makes sense if there is one. A one-key
    # grammar against that demonstration does not produce one key: it produces the
    # three-key object crammed into the narration string, escaped, and never closed.
    #
    # Measured live on the player's first turn, 2026-09-04, and reproduced four times
    # in eight runs against the same prompt. The reply ended:
    #
    #     ...the secret is in your pocket?\", \"suggestions\": [\"Leave the room...\"],
    #     \"intents\": []}<tool_call|>
    #
    # — 1,068 characters of perfectly good prose lost to `Unterminated string starting
    # at: line 1 column 15`. The model was obeying the prompt and refused by the
    # grammar. This repo's own rule is that instruction volume loses to demonstration
    # volume; the cheap half of that is to stop demonstrating one shape and requiring
    # another. `tests/test_prompts.py` pins the two together.
    return {"type": "object",
            "properties": {"narration": narration,
                           "suggestions": {"type": "array", "items": {"type": "string"}},
                           "intents": {"type": "array"}},
            "required": ["narration"]}


# Ollama's grammar compiler turns `maxLength` into a bounded repetition, and somewhere
# between 2,000 and 2,100 it stops compiling: HTTP 500 on every request carrying the
# schema. Measured by bisection on llama3.1:8b, 2026-08-25 — 1800 OK, 2000 OK, 2100
# fails, 2200 fails. The first value shipped was 2200, and every single call in the
# audit run came back 503. Both schema builders clamp here so nobody can reintroduce
# that by passing a bigger number.
#
# Re-measured 2026-09-04 on gemma-4 12B, the prose model now in use: 2000 fails the
# same way ("failed to parse grammar", HTTP 400) and 1800 compiles. The client had
# been stripping `maxLength` on that 400 and carrying on, so every prose call to
# gemma ran with NO ceiling — and with a floor in the grammar the string could only
# end when the token budget did: "Unterminated string" on two turns in three. 1800
# holds for both models measured.
GRAMMAR_MAXLENGTH_CEILING = 1800


def narration_repair_messages(text: str, complaint: str, player_input: str = "",
                              scene_brief: str = "",
                              facts: list[str] | None = None,
                              keep: str = "") -> list[dict]:
    """The rewrite call, given something to write *about*.

    It used to be handed the passage and the complaint and nothing else. Asked to rewrite
    a paragraph using none of the phrases it had copied, with no scene in front of it, the
    model had nothing to replace them with — and returned "..." and ". ..", three
    characters long, which then scored better than the plagiarism it replaced. Measured on
    all three turns of a live run.

    `keep` is one more thing the rewrite must not change, onto the system message — the
    intimate scene's register (`INTIMATE_KEEP`).
    """
    body = complaint + "\n\nThe passage:\n" + text
    if player_input:
        body += f"\n\nThe player said: {player_input}"
    if scene_brief:
        body += f"\n\nWrite about this scene, and nothing else:\n{scene_brief}"
    # The engine's decisions, which the rewrite was the one prose call never shown
    # (2026-09-25): asked to fix a phrase with no tells in front of it, it could turn a
    # miss into a hit, and the only guard was that 60% of the action sentences survived.
    if facts:
        body += ("\n\nWhat the engine decided. Every one of these stays true in your "
                 "rewrite:\n" + "\n".join(f"- {f}" for f in facts))
    return [
        {"role": "system", "content": NARRATION_REPAIR_BRIEFING
         + (f"\n\n{keep}" if keep else "")},
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

# Ops that resolve a turn in a fight. `narrate_only` is deliberately absent, and so
# are `damage` and `heal` since stage 8: a number the model wrote has no document
# behind it, and the sampler is where that is stopped — a validate-time rejection
# taught the model to route around (docs/stage-7-plan.md); an enum it cannot emit
# from has no route. Potions are `use_item`, spells are `cast`, powers are
# `use_ability`; the document supplies the number.
_FIGHT_OPS = ("attack", "cast", "use_ability", "use_item", "move", "spend_pools",
              "guard", "end_encounter", "check", "save")

# The one exception, named: a bestiary creature has no path, no spellbook and no
# satchel, and its bite's poison lives in a stat block no locator reads yet — 5,735
# of 7,188 shipped creatures carry `special_attacks`. On such a creature's turn the
# two ops come back, and the engine stamps `creature:<template>` as the origin: the
# engine names the source, the model still authors the number, and the ratchet lists
# this door by name until a creature-document stage retires it.
_CREATURE_OPS = _FIGHT_OPS + ("damage", "ability_damage")


_NUMERIC_PARAMS = {"amount": "number", "count": "integer", "hours": "integer"}


def _declared_op(op: str, refs: tuple[str, ...], places: tuple[str, ...],
                 aims: tuple[str, ...] = ()) -> dict:
    """One required op's shape in the reply's `declared` object: its target and params,
    the params the op requires marked required — and a travel's place held to the names
    of the places this town really has (generation under a list of valid names; GENRE,
    arXiv 2010.00904), so the model chooses among them and invents none.

    A cast's `aim` is held the same way (I3; docs/design-e-magic.md §4.6 step 5): "if they
    write nothing, the model infers the use" — from an enum of the aims that exist, so it
    chooses and cannot invent one. Ollama enforces an enum (6 of 6, memory
    `ollama-schema-enforcement`); a free-string aim came back as a placeholder for nobody
    (G2, 2026-09-28: `at=new2`, "the flames reach nobody", and the page burned an invented
    man). `aims` is `areas.legal_aims` for the scene when the caller has one; without it
    the enum is built from what this function already holds — the people present
    (`ref:`), the caster (`self`) and the map's directions — and a thing here reaches the
    cast through the player's own words (`judgement.aim_the_cast`) instead. Not required:
    the chip or the words may already have aimed it, and a required property is one the
    sampler must fill (the interpreter's slot measurement, 220 of 220).

    A journey's or travel's `pace` is the closed word Lane B's rules read (walk, ride,
    gallop; `journey.PACES`), never a free string."""
    from rules.intents import OPS as _OP_TABLE

    from rules.intents import FLAG_PARAMS

    required, optional, _vis = _OP_TABLE.get(op, ((), (), ""))
    props: dict = {}
    for name in (*required, *optional):
        # A flag is a boolean at the sampler: typed "string", `full_attack` could only
        # ever be sampled as a word, and `bool("false")` is True (rules.intents._flag).
        props[name] = {"type": "boolean" if name in FLAG_PARAMS
                       else _NUMERIC_PARAMS.get(name, "string")}
    need = list(required)
    if op == "travel" and places:
        props["place"] = {"type": "string", "enum": list(places)}
        need = ["place"]
    if "pace" in props:
        from rules.journey import PACES

        props["pace"] = {"type": "string", "enum": list(PACES)}
    if op == "cast" and "aim" in props:
        from rules import areas

        legal = [a for a in (aims or ()) if areas.valid(a)]
        if not legal:
            legal = [f"ref:{r}" for r in refs if areas.valid(f"ref:{r}")]
            legal += ["self"] + [f"dir:{d}" for d in areas.DIRECTIONS]
        props["aim"] = {"type": "string", "enum": list(dict.fromkeys(legal))}
    shape: dict = {"type": "object", "properties": {
        "params": {"type": "object", "properties": props, "required": need}},
        "required": ["params"]}
    if refs:
        shape["properties"]["target"] = {"type": "string", "enum": list(refs)}
    return shape


def turn_schema(*, fighting: bool = False, refs: tuple[str, ...] = (),
                min_chars: int = 0, must_contain: tuple[str, ...] = (),
                ops: tuple[str, ...] = (), places: tuple[str, ...] = (),
                aims: tuple[str, ...] = ()) -> dict:
    """The JSON schema this turn's reply must satisfy.

    `aims` is the scene's legal aims for a declared cast (`areas.legal_aims`), handed to
    `_declared_op` so the `aim` enum holds the features and props here as well as the
    people; without it the enum fell back to people, self and directions (I3's hand-off,
    closed 2026-09-29).

    `refs` pins the cast: the enum makes it impossible to aim at somebody who is not in
    the scene, which is the single most common rejection in the logs and the reason
    `repair_unknown_refs` had to be written.

    `must_contain` is the same idea aimed at the other failure — not proposing anything at
    all. When the player has plainly declared something (`judgement.declared_ops` decides,
    by asking the injectors themselves), the reply is required to contain that op, and the
    model then picks the item, the target and the reason with the scene in front of it. An
    injector bolting those on afterwards has to guess them.

    The placeholders `introduce` hands out (new1…) join the refs wherever that op can be
    written, so a plan can talk to the person it just brought in; the engine refuses one
    used before the intent that makes it.
    """
    from rules.intents import INTRODUCED_REFS

    if refs and not fighting and (not ops or "introduce" in ops):
        refs = tuple(refs) + tuple(r for r in INTRODUCED_REFS if r not in refs)
    intent = {
        "type": "object",
        "properties": {
            "op": {"type": "string",
                   "enum": (sorted(ops) if ops else
                            list(_FIGHT_OPS) if fighting else
                            sorted(op for op in _OPS if op not in AMOUNT_OPS))},
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
    # to write the intents after it. Clamped to what Ollama's grammar compiler can
    # actually build — see GRAMMAR_MAXLENGTH_CEILING.
    narration["maxLength"] = min(800 if fighting else 2000, GRAMMAR_MAXLENGTH_CEILING)
    schema = {
        "type": "object",
        "properties": {
            "narration": narration,
            "suggestions": {"type": "array", "items": {"type": "string"}},
            "intents": intents,
        },
        "required": ["narration", "intents"],
    }
    if wanted:
        # The requirement the sampler actually keeps. Measured 2026-09-27 against the
        # local model: Ollama's grammar does NOT enforce `contains` (0 of 6 replies held
        # the required op) nor `prefixItems` (0 of 6), so every declarer's "the reply is
        # unsamplable without one" was a hint the model could ignore — and did: "I go to
        # the market and buy a coil of rope" planned no walk, twice. A REQUIRED property
        # it keeps (6 of 6). So the ops the player's words commit the turn to are also
        # asked for as required keys of `declared`, one per op, which the agent merges
        # into the intents when the list left them out (`GMAgent._merge_declared`). The
        # `allOf` above stays for providers that do enforce it.
        schema["properties"]["declared"] = {
            "type": "object",
            "properties": {op: _declared_op(op, refs, places, aims) for op in wanted},
            "required": list(wanted)}
        schema["required"] = ["narration", "declared", "intents"]
    return schema


# --- The author's own hand -------------------------------------------------------------

# The ops a cheat may use: everything that does NOT put dice in somebody's hands.
# Derived from the op table's own visibility column rather than hand-listed, so an op
# added tomorrow lands on the right side of the line without this being edited.
#
# Measured live, and this is why it exists at all. Probing `/cheat I have 1000 gold`
# against gemma-4-12B in a scene that happened to be mid-fight came back with
# `{"op": "attack", "actor": "pc"}` — the merchant swung at the player and knocked her
# unconscious, on a wish about money. A model in a fight does what it does in a fight,
# and no amount of instruction outweighs the brief describing one. An enum at the
# sampler is not an instruction: `attack` is a token the model cannot emit here.
#
# The rule it encodes is also just true. A cheat never rolls — the whole point is that
# the author has decided the outcome — so every `player`-visibility op (attack, check,
# save, forage, use_item, sell, buy, use_ability) is exactly the wrong shape for one.
CHEAT_OPS: tuple[str, ...] = tuple(
    op for op, (_need, _may, vis) in _OPS.items() if vis != "player")


def _op_reference() -> str:
    """Every op and its params, generated from the op table.

    The ordinary turn prompt does not carry this: it teaches by example and the schema's
    enum pins the op name at the sampler. A cheat is bookkeeping rather than a scene, and
    the model is being asked for ops it has seen no example of — `advance_time`, `defence`,
    `temp_hp` — so it needs the params by name. Generated rather than written out, because
    a hand-copied list of forty ops is a copy that drifts, and CLAUDE.md's rule about
    grepping for every copy of a rule exists for exactly this.
    """
    lines = ["THE OPS you may use, and the params each takes "
             "(required first, then optional):"]
    for op, (need, may, _vis) in sorted(_OPS.items()):
        if op not in CHEAT_OPS:
            continue
        parts = ", ".join(need) or "—"
        if may:
            parts += "  [" + ", ".join(may) + "]"
        lines.append(f"  {op}: {parts}")
    return "\n".join(lines)


CHEAT_SYSTEM = """You are the rules engine's clerk, not its referee.

The person playing this game is also its author, and they have just written down
something that is now true. Your only job is to turn that sentence into the intents
that MAKE it true, using the ops below and the refs that exist. The rules do not get a
vote: nothing is too expensive, nobody rolls to resist, no check is made, and no reason
is needed.

What you may NOT do is invent. Every ref you name must be one of the refs listed in the
scene. Every place must be one of the places listed. If the wish names somebody who is
not here, spawn them; if it names a thing, give it. If nothing in the op list can do what
the wish asks, emit one narrate_only and let the prose carry it — a wish you cannot
mechanise honestly is better than an op that pretends.

Worked examples of the shape:

  "I have 1000 gold"
    [{"op": "give", "because": "the author says so",
      "params": {"item": "gold", "count": 1000, "to": "pc"}}]

  "I defeat all the enemies"
    [{"op": "condition", "because": "the author says so",
      "params": {"condition": "dead", "to": "<each enemy ref>"}},
     {"op": "end_encounter", "because": "the author says so", "params": {}}]

  "the merchant falls deeply in love with me"
    [{"op": "condition", "because": "the author says so",
      "params": {"condition": "helpful", "to": "<the merchant's ref>"}}]

  "I am wearing a suit of full plate"
    [{"op": "give", "because": "the author says so",
      "params": {"item": "full plate", "count": 1, "to": "pc"}},
     {"op": "wear", "because": "the author says so",
      "params": {"item": "full plate", "actor": "pc"}}]

  "it is suddenly midnight"
    [{"op": "advance_time", "because": "the author says so",
      "params": {"amount": 8, "unit": "hours"}}]

You cannot wear or use what you are not carrying: hand it over first, then put it
on. Two intents, in that order.

Numbers in the wish are the author's numbers. 1000 gold is 1000, not 500.

Attitudes are a real state and the track is hostile, unfriendly, indifferent, friendly,
helpful — "falls in love", "trusts me", "is my friend" are all `helpful` or `friendly`,
not a narrate_only.

Write no narration. The intents are the whole answer."""


OUT_OF_CHARACTER = """You are the Game Master, answering the player OUT OF CHARACTER.

This is not a turn and nothing in the world is happening. Do not narrate, do not write
a scene, do not describe what anybody does. Answer the question, in your own voice, as
the person running the game would across the table.

Answer in two to five sentences. Plain prose, no headings, no lists.

The rules are Pathfinder 1st edition. If the question is about the rules and you are
not certain, say which rule you think it falls under and say plainly that you are not
certain — a confident wrong answer about a rule is worse than "I would have to look
that up", because the player will act on it.

Below is what the engine actually holds, and it is the truth. Do not contradict it, and
do not invent a person, a place or an item that is not in it. If the question asks for
something the engine has not decided, say that it has not been decided yet rather than
deciding it here: nothing you say in this answer changes the game.
"""


def out_of_character_messages(briefing_scene: str, question: str,
                              found: str = "", notes: str = "",
                              record: str = "") -> list[dict]:
    """The `/gm` question the engine could not answer from its own books.

    Deliberately given the brief and nothing else — no history, no examples. The
    examples teach the model to write scenes, which is the one thing this call must not
    do, and the history is the fiction, which is what the player has stepped out of.

    `notes` (the GM's notes on where the party stands) and `record` (what the world's
    own record says about what was asked) go in the USER message after the question,
    last in the prompt — where a passage is read rather than lost in the middle — with
    the one instruction that matters: answer from them, and say when they do not cover
    it. docs/gm-questions.md.
    """
    facts = briefing_scene
    if found:
        facts += "\n\nWHAT THE BOOKS SAY ABOUT WHAT WAS ASKED:\n" + found
    ask = question
    if notes or record:
        ask += "\n\n" + "\n\n".join(x for x in (notes, record) if x)
        ask += ("\n\nAnswer the question from what is above, in your own voice, as the "
                "person running the game would across the table — a few sentences, "
                "specific, naming the people and places by their names here (never by a "
                "tag like c1). These are your own notes: say \"my notes\", not \"the "
                "information provided\". Where they do not cover the question, say so "
                "plainly rather than filling it in.")
    return [{"role": "system", "content": OUT_OF_CHARACTER + "\n\n" + facts},
            {"role": "user", "content": ask}]


def cheat_messages(briefing_scene: str, wish: str) -> list[dict]:
    """The author's wish, as a request for intents and nothing else.

    Deliberately NOT the ordinary turn prompt with a different instruction bolted on.
    That prompt is built to make a model refuse impossible things, keep the fiction
    honest and hand the turn back with a question — every one of which is exactly what a
    cheat is for overriding, and CLAUDE.md's own rule is that instruction volume loses to
    demonstration volume. A prompt whose examples all show a careful GM cannot be argued
    into being a clerk.

    The scene brief still goes in whole, because the one thing a cheat must not do is
    invent: the refs, the names and the places are the same grounding every other call
    gets, and the schema pins the refs at the sampler on top of it.
    """
    return [
        {"role": "system", "content": CHEAT_SYSTEM + "\n\n" + _op_reference()},
        {"role": "user", "content": briefing_scene},
        {"role": "user",
         "content": f"The author writes: {wish}\n\nMake it true."},
    ]
