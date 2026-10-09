"""What the player means, read once, before the turn is planned: the interpreter.

Asked for 2026-09-27 ("the whole app hinges on consistently good narration and
accuracy"): about twenty regex readers in gm/judgement.py each read the player's English
for one kind of declaration, and nearly every live defect of that day was one of them
misreading it — "go to the market AND look for the bread seller" read as looking for
"market", "the woman WHO SOLD me bread" as "woman", "I ask HER NAME" as a person to
introduce, "until TEN AT NIGHT" as 140 minutes. This module is the experiment in reading
the sentence once, into a frame, and letting code check the frame.

The shape comes from a research pass (sources in docs/the-interpreter.md):
  * VERBATIM SPANS, never paraphrase or normalised values: every slot must be a piece of
    the player's own sentence, checked in code, and a slot that is not is dropped.
    Google's LangExtract aligns each extraction to the input and flags the ones it
    cannot (it keeps them; dropping is ours — checked by a critic pass). Small models
    invent normalised values (Uniphore, COLING 2025) and substitute objects: "examine
    phone" came back "examine note" from an LLM front end tested on intfiction.org.
    Times stay words ("until ten at night"); code turns them into minutes.
  * A CLOSED LIST OF ACTS, as an enum the sampler cannot leave, with `other` for the
    rest (Rasa's command generators; Ollama's structured outputs).
  * SPANS BEFORE THE ACT in each action, so the words are chosen before the label
    ("Let Me Speak Freely": the order of fields changes what a constrained model does).
  * ATTEMPTS APART FROM CLAIMS: "I kick in the door and the guards cower" attempts one
    thing and claims another; the claim is the engine's to refuse.
  * DEMONSTRATIONS OVER INSTRUCTIONS: this project's own lesson (CLAUDE.md — instruction
    volume loses to demonstration volume). The demonstrations below are not in the
    labelled set (tests/interpreter/gold.py), which would measure recall of the prompt.
"""
from __future__ import annotations

import json
import re
import time

# On in the app. Off in the test suite (tests/conftest.py), as the written opening and
# the schemes are: most turn tests script the model's replies in order, and a reading
# would spend one of them. The interpreter's own tests turn it back on.
ENABLED = True

ACTS = (
    "go", "journey", "leave", "look", "search", "seek", "talk", "insult", "buy", "sell",
    "give", "take", "drop", "steal", "attack", "cast", "use", "consume", "wait",
    "rest", "call_on", "break_in", "stealth", "athletics", "gather", "follow", "claim",
    "other",
)
# `drop` since 2026-10-03, because the act→op table (gm/acts_to_ops.py) needs it and the
# vocabulary did not have it: "I also drop the Brunt of the weight on the ground" was read
# `give, target: the Brunt of the weight, place: the ground` on the owner's items save, and
# a give is a hand-over to somebody — the smith gained a copy.
#
# Tried and withdrawn the same day: an `offer` act, for a sale not yet closed. It moved the
# problem rather than solving it — the live reader read "I try to sell the crate to Korvu"
# as `offer` and "I try to sell the crate to the smith" as `sell`, and on the held-out lines
# a `talk` came back `offer`. What separates them is not WHAT is done but how far it is
# done, which every act has: COMMITMENT, below.
SLOTS = ("target", "object", "place", "time", "says")

# How far each action is done (2026-10-03, lane F round 2). The coordinator, after the
# replay: "I take the crate to the man in the counting house who will buy it" was read as a
# sale and the crate was sold a turn early; "I try to sell the crate to the smith" was read
# `sell` and sold. The engine acted on something the player had not committed to.
#
# The research's answer is old. Event annotation marks every event mention with its REALIS:
# Rich ERE's "Actual (asserted), Generic (generic, habitual), and Other (future,
# hypothetical, negated, uncertain, etc.)" (Song et al. 2015, "From Light to Rich ERE",
# ACL W15-0812; the TAC KBP event-nugget task scored the same three). FactBank grades the
# same axis finer (certain / probable / possible, Saurí & Pustejovsky 2009). And dialogue
# acts keep an offer apart from its acceptance: ISO 24617-2's Offer is answered by an
# Accept Offer, "which has a functional dependence relation to the preceding Offer" (Bunt,
# annotation guidelines) — a sale tried is an offer, and only an agreement closes it.
# Ours is Rich ERE's split with the attempt kept apart, because 1e rolls for an attempt:
#   done      performed now, as stated ("I sell the crate to him", "it's a deal")
#   tried     attempted now, the outcome open ("I try to pick the lock", "I try to sell…")
#   intended  a plan, purpose or wish, not done this turn ("to sell it", "who will buy it",
#             "I'm going to…", "I want to…")
#   asked     asked about, not done ("can I sell it here?", "would you buy it?")
# Only `done` and `tried` move the engine (`acts_to_ops`, `ops_for`, `supported`).
COMMITS = ("done", "tried", "intended", "asked")
ACTING = frozenset({"done", "tried"})

# By what MEANS each action is done (2026-10-05, gm/means.py). The owner: "whatever you do
# must catch anything that is not within the players power to do not just psychic and
# memory stuff". The regex door before this (`judgement.refuse_unnamed_power`) listed the
# ways of reaching into a mind it knew, and the table found the ones it did not: "I make
# the smith forget he saw me" became a Diplomacy check, and "I erase the apprentice's
# memory of me" became the plan's guess at `cast charm-person`, which stood the door down.
#
# The answer every tradition gives is the same three-way split, and none of them is a
# list of forbidden verbs:
#   ordinary  what anybody can TRY — body, voice, skill, the things carried. "You write
#             the attempt, they write the result" (play-by-post etiquette on autohitting);
#             1e's skills and combat roll it.
#   power     by a named document — a spell, a class or path ability, a racial trait, a
#             feat, a magic item. Fate calls this a permission: an aspect or extra is what
#             lets a character do what others cannot (Fate System Toolkit, "Extras").
#   beyond    neither: nothing an ordinary person can do, and no power named for it.
#             Apocalypse World's "fictional positioning" — without it the move does not
#             trigger, whatever is said.
# The reader answers which (an enum, enforced by the sampler); code then asks the SHEET
# whether a power named is held (`means.held_power`) — a closed vocabulary, never English.
MEANS = ("ordinary", "power", "beyond")


def acting(a: dict) -> bool:
    """Whether this action of a reading is done or attempted now — the ones the engine
    acts on. A reading from before commitment existed has none, and is `done`."""
    return str(a.get("commit") or "done") in ACTING

# The slots each act can have: TADS 3's verb templates, where a verb names the slots it
# takes and nothing else (tads.org, "t3verb"). Measured 2026-09-27: with every slot
# required, the model filled all five on most lines and copied one phrase into several
# ("the ore he uses" as object AND place), slot precision 0.33. A slot the act cannot
# have is not the act's, and is dropped in code — never asked of the model twice.
ACT_SLOTS: dict[str, tuple[str, ...]] = {
    # A walk's `object` is what is carried along (round 2): "I take the crate to the man in
    # the counting house" was read `go`, and a crate the player was not yet holding never
    # came with them — the replay of the owner's items save then had nothing to sell.
    "go": ("place", "object", "time"), "journey": ("place",), "leave": ("place",),
    "look": ("object", "target", "place", "time"), "search": ("object", "place"),
    "seek": ("target", "place", "object"), "talk": ("target", "says"),
    "insult": ("target", "says"),
    "buy": ("object", "target", "place"), "sell": ("object", "target"),
    "drop": ("object", "place"),
    # A take's `target` is who or what it comes OUT of — a person, or a container: "the
    # coins from the pouch" is `object: the coins, target: the pouch` (TADS 3's TakeFrom,
    # whose indirect object is the holder, person or thing).
    "give": ("target", "object", "place"), "take": ("object", "target"),
    "steal": ("object", "target"), "attack": ("target", "object", "place", "time"),
    # `place` as well since I3 (2026-09-29): where a spell goes is as often a place-shaped
    # phrase ("into the tree tops", "into the empty air above my head") as a person, and a
    # slot the act cannot have is dropped in code — so the phrase was lost before the aim
    # reader could see it. Bobby's reading of "I cast burning hands into the tree tops"
    # came back `object: burning hands, target: the tree tops`; another reading of the
    # same line may put the treetops in `place`, and both now reach `cast_aim`.
    "cast": ("object", "target", "place"), "use": ("object", "target"), "consume": ("object",),
    "wait": ("place", "time", "target"), "rest": ("place", "time"),
    "call_on": ("target", "place"), "break_in": ("target", "object", "place"),
    "stealth": ("target", "place"), "athletics": ("place",), "gather": ("object", "time"),
    "follow": ("target", "object", "time"), "claim": (), "other": ("target", "object", "place"),
}

_WHAT_EACH_IS = """\
go        walk somewhere within reach (a place in town, the crossroads, the fields, into
          the trees, back to the gate); walking OUT INTO somewhere named is go, not leave
journey   take the road or a ship to another town
leave     walk out of where you are — a building, or the settlement itself — with
          nowhere else named
look      look, watch, listen, read, examine
search    look for a THING or a PLACE (water, a way in, somewhere to sleep, tracks)
seek      look for, ask around for, wave down, head for or turn to a PERSON
talk      speak to, ask, tell, greet, thank, persuade, order, haggle with somebody
insult    mock, taunt, call names, spit at, pick a fight with words — and telling
          anybody something meant to shame somebody ("I tell the room he is a coward")
buy       buy, order, pay for goods
sell      sell, offer for sale, agree a sale, accept a price, close a deal
give      hand over, pay, buy somebody a drink
take      pick up, loot, take, tip or count out of a container; the target is the
          person or the container it comes out of
drop      put down, set down, drop or leave a thing behind
steal     pick a pocket, steal, filch
attack    hit, punch, stab, shoot, assault, pick a fight with, run amok, finish somebody
cast      cast a named spell
use       draw a weapon, put on, show, use, bandage, light
consume   eat or drink
wait      wait, sit, stand, stay, keep watch, pass time
rest      sleep, lie down, make camp, rest, take a room
call_on   go to somebody's house, knock at their door, visit them at home
break_in  kick in, force or pick the lock of a door
stealth   sneak, hide, slip past
athletics climb, swim, jump
gather    forage, gather, fill waterskins
follow    follow somebody or a trail
claim     assert who or what you are
other     anything else

Each action also says by what MEANS it is done:
ordinary  anything a person could try with their body, voice, skill and what they carry
power     a spell, ability, trait, feat or magic item the sentence names; copy its name
          into `power`
beyond    something no ordinary person can do, with no power named for it"""

_DEMOS = [
    ("I head down to the docks and ask a fisherman what he caught today.",
     {"question": False, "claims": [], "actions": [
         {"span": "head down to the docks", "place": "the docks", "act": "go"},
         {"span": "ask a fisherman what he caught today", "target": "a fisherman",
          "says": "what he caught today", "act": "talk"}]}),
    ("I look for the tailor who mended my cloak last week.",
     {"question": False, "claims": [], "actions": [
         {"span": "look for the tailor who mended my cloak last week",
          "target": "the tailor who mended my cloak last week", "act": "seek"}]}),
    ("I buy three candles from her and ask where the temple is.",
     {"question": False, "claims": [], "actions": [
         {"span": "buy three candles from her", "object": "three candles", "target": "her",
          "act": "buy"},
         {"span": "ask where the temple is", "says": "where the temple is", "act": "talk"}]}),
    ("I sit on the steps until noon.",
     {"question": False, "claims": [], "actions": [
         {"span": "sit on the steps until noon", "place": "the steps", "time": "until noon",
          "act": "wait"}]}),
    ("I ask him his name.",
     {"question": False, "claims": [], "actions": [
         {"span": "ask him his name", "target": "him", "says": "his name", "act": "talk"}]}),
    ("I smash the tavern door and everyone inside flees.",
     {"question": False, "claims": ["everyone inside flees"], "actions": [
         {"span": "smash the tavern door", "object": "the tavern door", "act": "break_in"}]}),
    ("Is it still raining?",
     {"question": True, "claims": [], "actions": []}),
    ("I find somewhere dry to shelter and sleep until first light.",
     {"question": False, "claims": [], "actions": [
         {"span": "find somewhere dry to shelter", "object": "somewhere dry to shelter",
          "act": "search"},
         {"span": "sleep until first light", "time": "until first light", "act": "rest"}]}),
    ("I go round to the cooper's house.",
     {"question": False, "claims": [], "actions": [
         {"span": "go round to the cooper's house", "target": "the cooper",
          "place": "the cooper's house", "act": "call_on"}]}),
    ("I tell the sergeant, \"We march at dawn.\"",
     {"question": False, "claims": [], "actions": [
         {"span": "tell the sergeant, \"We march at dawn.\"", "target": "the sergeant",
          "says": "We march at dawn.", "act": "talk"}]}),
    # Words said to nobody named: the quotation is `says`, and the target is null — never
    # the quotation (2026-10-03, item 13, where `say "…"` came back as the target and was
    # minted as a person). Kept out of the labelled set, like every demonstration here.
    ("I shrug and say \"Only passing through, friend.\"",
     {"question": False, "claims": [], "actions": [
         {"span": "say \"Only passing through, friend.\"",
          "says": "Only passing through, friend.", "act": "talk"}]}),
    ("I spit on the ground in front of the fat merchant.",
     {"question": False, "claims": [], "actions": [
         {"span": "spit on the ground in front of the fat merchant",
          "target": "the fat merchant", "act": "insult"}]}),
    ("I tell the crowd the reeve is a thief and a liar.",
     {"question": False, "claims": [], "actions": [
         {"span": "tell the crowd the reeve is a thief and a liar", "target": "the crowd",
          "says": "the reeve is a thief and a liar", "act": "insult"}]}),
    ("I head for the cooper to ask about barrels.",
     {"question": False, "claims": [], "actions": [
         {"span": "head for the cooper", "target": "the cooper", "act": "seek"},
         {"span": "to ask about barrels", "commit": "intended", "says": "about barrels",
          "act": "talk"}]}),
    ("I climb the bell tower to look over the rooftops.",
     {"question": False, "claims": [], "actions": [
         {"span": "climb the bell tower", "place": "the bell tower", "act": "athletics"},
         {"span": "to look over the rooftops", "commit": "intended",
          "object": "the rooftops", "act": "look"}]}),
    ("I sit on the bench for an hour.",
     {"question": False, "claims": [], "actions": [
         {"span": "sit on the bench for an hour", "place": "the bench", "time": "for an hour",
          "act": "wait"}]}),
    ("I buy the old soldier a pint.",
     {"question": False, "claims": [], "actions": [
         {"span": "buy the old soldier a pint", "target": "the old soldier",
          "object": "a pint", "act": "give"}]}),
    # --- 2026-10-03: the reader now carries the turn (docs/structured-turn.md) ----------
    # Each from a measured systematic miss on the first 60 labelled lines — never a line
    # of the labelled set itself, and none from the 160 held out. Demonstrations, not
    # instructions: CLAUDE.md's ratio rule, and "head for the cooper" above taught `seek`
    # for every "head for", places included ("I head for the stables" came back `seek,
    # target: the stables`). A place headed for is `go`; a person headed for is `seek`.
    ("I head for the tannery to ask about hides.",
     {"question": False, "claims": [], "actions": [
         {"span": "head for the tannery", "place": "the tannery", "act": "go"},
         {"span": "to ask about hides", "commit": "intended", "says": "about hides",
          "act": "talk"}]}),
    # …and the person beside it, because the place demonstration alone turned "I head for
    # the smith" into `go, place: the smith` on the dev bench. "ask for X" is what is said.
    ("I head for the ferryman and ask for a crossing.",
     {"question": False, "claims": [], "actions": [
         {"span": "head for the ferryman", "target": "the ferryman", "act": "seek"},
         {"span": "ask for a crossing", "says": "for a crossing", "act": "talk"}]}),
    # "ask where/what X" is what is said, all of it, pronoun and all: "I wave down a
    # passing carter and ask where he is headed" came back `talk, target: he` and the
    # question was lost; "ask where the dockhands drink" came back `target: the
    # dockhands`. Nobody is named as spoken to, so the target is null.
    ("I flag down a porter and ask where she is taking the trunk.",
     {"question": False, "claims": [], "actions": [
         {"span": "flag down a porter", "target": "a porter", "act": "seek"},
         {"span": "ask where she is taking the trunk",
          "says": "where she is taking the trunk", "act": "talk"}]}),
    ("I ask where the ropemakers work, and walk there.",
     {"question": False, "claims": [], "actions": [
         {"span": "ask where the ropemakers work", "says": "where the ropemakers work",
          "act": "talk"},
         {"span": "walk there", "place": "there", "act": "go"}]}),
    # A house, and where somebody lives, is a place: "I go to her house" lost `place`.
    ("I ask around where the midwife lives.",
     {"question": False, "claims": [], "actions": [
         {"span": "ask around where the midwife lives", "target": "the midwife",
          "place": "where the midwife lives", "act": "seek"}]}),
    ("I call the bailiff a drunk to his face.",
     {"question": False, "claims": [], "actions": [
         {"span": "call the bailiff a drunk to his face", "target": "the bailiff",
          "says": "a drunk", "act": "insult"}]}),
    # A gesture is no hand-over: "I give a friendly wink" planned a `give` of "friendly
    # wink" on the owner's market save (2026-10-03, item 8).
    ("I give the guard a lazy salute and say \"Long night, friend?\"",
     {"question": False, "claims": [], "actions": [
         {"span": "give the guard a lazy salute", "target": "the guard", "act": "other"},
         {"span": "say \"Long night, friend?\"",
          "says": "Long night, friend?", "act": "talk"}]}),
    # Things moving, the shapes the owner's items save misread. Out of a container, the
    # container is the take's target; set down is `drop`, never a give to the nearest.
    ("I shake the silver out of the sack into my purse and set the empty sack down by "
     "the door.",
     {"question": False, "claims": [], "actions": [
         {"span": "shake the silver out of the sack into my purse", "object": "the silver",
          "target": "the sack", "act": "take"},
         {"span": "set the empty sack down by the door", "object": "the empty sack",
          "place": "by the door", "act": "drop"}]}),
    # Withdrawn, round 2: "I lift the lantern off the hook, then hand it to the boy." Two of
    # the 4.4 points of acts-in-order lost on the held-out lines were a search and an
    # `other` read as `take` (an act-level count, no sentence read), and this was one of
    # two take demonstrations added that day; "it" is the table's to resolve, in code.
    #
    # How far a deed is done (`COMMITS`). A sale tried is an offer the fiction answers; a
    # sale agreed, or closed in the player's own quoted words, is done.
    ("I offer the furrier my wolf pelts and ask what he would pay.",
     {"question": False, "claims": [], "actions": [
         {"span": "offer the furrier my wolf pelts", "commit": "tried",
          "object": "my wolf pelts", "target": "the furrier", "act": "sell"},
         {"span": "ask what he would pay", "says": "what he would pay", "act": "talk"}]}),
    ("I tell the miller, \"Done. The mule is yours.\"",
     {"question": False, "claims": [], "actions": [
         {"span": "tell the miller, \"Done. The mule is yours.\"", "target": "the miller",
          "says": "Done. The mule is yours.", "act": "talk"},
         {"span": "The mule is yours", "object": "The mule", "target": "the miller",
          "act": "sell"}]}),
    # One deed, not two (round 2): a time is when the deed ends, a weapon is what it is
    # done with, and where the player leans or stands is where they do it. Measured on the
    # dev lines written for it (`authored:segment`, after an act-level count of held-out
    # flips): 7 of 14 came back with an extra action — `go, wait`, `use, attack`,
    # `wait, look`, `other, talk`.
    ("I walk along the river until the bell rings.",
     {"question": False, "claims": [], "actions": [
         {"span": "walk along the river until the bell rings", "place": "the river",
          "time": "until the bell rings", "act": "go"}]}),
    ("I level my spear and drive it into the boar.",
     {"question": False, "claims": [], "actions": [
         {"span": "level my spear and drive it into the boar", "target": "the boar",
          "object": "my spear", "act": "attack"}]}),
    ("I lean against the doorframe and watch the street.",
     {"question": False, "claims": [], "actions": [
         {"span": "lean against the doorframe and watch the street",
          "object": "the street", "act": "look"}]}),
    ("I seize the pickpocket by the arm.",
     {"question": False, "claims": [], "actions": [
         {"span": "seize the pickpocket by the arm", "target": "the pickpocket",
          "act": "attack"}]}),
    # Violence nobody is named for (2026-10-09, the owner: "if i say I attack the closest
    # person or i go on a rampage or i assault a civilian etc. it should be able to start a
    # fight"). Measured live the same day on gemma-4-12B: "I go on a rampage." was read
    # `other`, and "I pick a fight with the biggest bruiser in the room." `insult` -- the
    # gloss said "pick a fight with words". Who the blow lands on is not the reader's to
    # say here: the words are kept whole and `confirm_victims` asks it of the people here.
    ("I pick a fight with the tallest of the sailors.",
     {"question": False, "claims": [], "actions": [
         {"span": "pick a fight with the tallest of the sailors",
          "target": "the tallest of the sailors", "act": "attack"}]}),
    ("I run amok through the fish stalls.",
     {"question": False, "claims": [], "actions": [
         {"span": "run amok through the fish stalls", "place": "the fish stalls",
          "act": "attack"}]}),
    # What somebody else will do is not the player's deed at all: no action. Tried first
    # as `sell, commit: intended` for "who will pay me for it", and on the dev lines the
    # reader then read "the net, which he will mend for me" as the player's own sale.
    ("I carry the barrel over to the cooper, who will pay me for it.",
     {"question": False, "claims": [], "actions": [
         {"span": "carry the barrel over to the cooper", "target": "the cooper",
          "object": "the barrel", "act": "seek"}]}),
    ("I take the lamp along to the old woman's hut.",
     {"question": False, "claims": [], "actions": [
         {"span": "take the lamp along to the old woman's hut",
          "place": "the old woman's hut", "object": "the lamp", "act": "go"}]}),
    # A purpose clause or a plan: intended, never done. "going to <a place>" is going;
    # "going to <do something>" is a plan.
    ("I'm going to the baker's to buy bread.",
     {"question": False, "claims": [], "actions": [
         {"span": "going to the baker's", "place": "the baker's", "act": "go"},
         {"span": "to buy bread", "commit": "intended", "object": "bread", "act": "buy"}]}),
    # …and "to <a place>" is where the walk goes, not a plan: "I head out of town to
    # wherever the charcoal burners work" came back `go, commit: intended` on the dev lines
    # — a walk the engine would never have made.
    ("I ride out past the walls to the old mill.",
     {"question": False, "claims": [], "actions": [
         {"span": "ride out past the walls to the old mill", "place": "the old mill",
          "act": "go"}]}),
    ("I go to the forge to sell the horseshoes.",
     {"question": False, "claims": [], "actions": [
         {"span": "go to the forge", "place": "the forge", "act": "go"},
         {"span": "to sell the horseshoes", "commit": "intended",
          "object": "the horseshoes", "act": "sell"}]}),
    # A price is not a second thing sold: "agree to sell the goat to the herder for six
    # silver" came back as two sales on the dev lines, the second of "six silver".
    ("I accept four silver from the tanner for the hides.",
     {"question": False, "claims": [], "actions": [
         {"span": "accept four silver from the tanner for the hides",
          "object": "the hides", "target": "the tanner", "act": "sell"}]}),
    ("I'm going to find the harbourmaster and ask about passage.",
     {"question": False, "claims": [], "actions": [
         {"span": "going to find the harbourmaster", "commit": "intended",
          "target": "the harbourmaster", "act": "seek"},
         {"span": "ask about passage", "commit": "intended", "says": "about passage",
          "act": "talk"}]}),
    # Tried: done now, the outcome the dice's.
    ("I try to pick the lock of the chapel door.",
     {"question": False, "claims": [], "actions": [
         {"span": "try to pick the lock of the chapel door", "commit": "tried",
          "target": "the chapel door", "act": "break_in"}]}),
    # Asked about: the asking is done; the deed asked about is not.
    ("I ask the trader whether she would buy my furs.",
     {"question": False, "claims": [], "actions": [
         {"span": "ask the trader whether she would buy my furs", "target": "the trader",
          "says": "whether she would buy my furs", "act": "talk"},
         {"span": "whether she would buy my furs", "commit": "asked", "object": "my furs",
          "target": "the trader", "act": "sell"}]}),
    # --- 2026-10-05: by what means (`MEANS`, gm/means.py) ------------------------------
    # Every demonstration above is `ordinary`, by default, which is the ratio the table
    # has. These are not in the means corpus (tests/means/gold.py). Paired on purpose: a
    # mind worked on by will against the same mind worked on by words and a coin, and a
    # result the player declared kept apart as a claim, never as a means.
    ("I stare hard at the ferryman until he forgets what I look like.",
     {"question": False, "claims": [], "actions": [
         {"span": "stare hard at the ferryman until he forgets what I look like",
          "target": "the ferryman", "means": "beyond", "act": "other"}]}),
    ("I tell the ferryman he never saw me and press a coin into his palm.",
     {"question": False, "claims": [], "actions": [
         {"span": "tell the ferryman he never saw me", "target": "the ferryman",
          "says": "he never saw me", "act": "talk"},
         {"span": "press a coin into his palm", "target": "his palm", "object": "a coin",
          "act": "give"}]}),
    ("I lie to the reeve and he swallows it whole.",
     {"question": False, "claims": ["he swallows it whole"], "actions": [
         {"span": "lie to the reeve", "target": "the reeve", "act": "talk"}]}),
    ("I peer at the fisherman's hands to see if he is hiding a knife.",
     {"question": False, "claims": [], "actions": [
         {"span": "peer at the fisherman's hands", "object": "the fisherman's hands",
          "act": "look"}]}),
    ("I cast hold portal on the cellar door.",
     {"question": False, "claims": [], "actions": [
         {"span": "cast hold portal on the cellar door", "object": "hold portal",
          "target": "the cellar door", "power": "hold portal", "means": "power",
          "act": "cast"}]}),
    ("I use Stunning Fist on the boatman.",
     {"question": False, "claims": [], "actions": [
         {"span": "use Stunning Fist on the boatman", "object": "Stunning Fist",
          "target": "the boatman", "power": "Stunning Fist", "means": "power",
          "act": "use"}]}),
    ("I call up a gale to blow the fishing boats back to shore.",
     {"question": False, "claims": [], "actions": [
         {"span": "call up a gale to blow the fishing boats back to shore",
          "means": "beyond", "act": "other"}]}),
    ("I vanish from the jetty and step out on the far bank.",
     {"question": False, "claims": [], "actions": [
         {"span": "vanish from the jetty and step out on the far bank",
          "place": "the far bank", "means": "beyond", "act": "other"}]}),
    # Three from the means corpus's first pass (dev lines, docs/means-gate.md): a skill
    # read as beyond twice — remembering, a disguise — and a result clause read as a deed
    # of its own; and a lock opened by a touch read as a lock picked. None is a corpus line.
    ("I try to remember the name of the ship's captain.",
     {"question": False, "claims": [], "actions": [
         {"span": "try to remember the name of the ship's captain", "commit": "tried",
          "object": "the name of the ship's captain", "act": "other"}]}),
    ("I dress up as a priest to get past the doorman.",
     {"question": False, "claims": [], "actions": [
         {"span": "dress up as a priest", "act": "other"},
         {"span": "to get past the doorman", "commit": "intended",
          "target": "the doorman", "act": "stealth"}]}),
    ("I shout at the dog until it slinks off.",
     {"question": False, "claims": [], "actions": [
         {"span": "shout at the dog until it slinks off", "target": "the dog",
          "act": "other"}]}),
    # Remembering is a deed, not a claim: on the regex gate's own corpus "I remember the
    # road to the coast" came back with no action, only a claim, which the means gate
    # refuses as saying-so (gm/means.py).
    ("I remember the way to the old quarry.",
     {"question": False, "claims": [], "actions": [
         {"span": "remember the way to the old quarry",
          "object": "the way to the old quarry", "act": "other"}]}),
    ("I make the shutters fly open by pointing at them.",
     {"question": False, "claims": [], "actions": [
         {"span": "make the shutters fly open by pointing at them",
          "object": "the shutters", "means": "beyond", "act": "other"}]}),
]


def schema() -> dict:
    """The reply's shape, enforced by the sampler: spans first, the act last."""
    slot = {"type": ["string", "null"]}
    return {
        "type": "object",
        "properties": {
            "question": {"type": "boolean"},
            "actions": {
                "type": "array", "maxItems": 4,
                "items": {
                    "type": "object",
                    "properties": {"span": {"type": "string"},
                                   "commit": {"type": "string", "enum": list(COMMITS)},
                                   **{s: slot for s in SLOTS},
                                   "power": slot,
                                   "means": {"type": "string", "enum": list(MEANS)},
                                   "act": {"type": "string", "enum": list(ACTS)}},
                    # Every slot required (null allowed). Measured 2026-09-27 on the
                    # labelled set: with the slots optional, the constrained sampler
                    # wrote `span` and `act` and nothing else on 220 of 220 lines —
                    # slot recall 0.0 — because an optional property is one the grammar
                    # lets it skip. The commitment is required for the same reason.
                    "required": ["span", "commit", *SLOTS, "power", "means", "act"],
                },
            },
            "claims": {"type": "array", "items": {"type": "string"}, "maxItems": 3},
        },
        "required": ["question", "actions", "claims"],
    }


# Which reply shape the reader is held to: "flat" (every slot on every action, the act
# last) or "per_act" (an `anyOf` of one object per act, the act a `const` straight after
# the span, and only that act's slots — TADS 3's verb templates, enforced by the sampler
# instead of dropped in code afterwards). Probed 2026-10-03 on six real lines before any
# reliance: Ollama enforced the per-act shape on 6 of 6, in both field orders. With the act
# LAST, the slot keys the model wrote first chose the act — "I look around and take stock"
# came back `claim, claim`, the one act with no slots — so the act goes straight after the
# span. Chosen on the dev bench (the first 60 labelled lines; docs/structured-turn.md),
# the same demonstrations both ways: engine-relevant frames 0.833 per-act against 0.767
# flat, strict 0.683 against 0.650, median 1.4 s against 2.4 s — fewer keys to write.
SCHEMA = "per_act"


def per_act_schema() -> dict:
    slot = {"type": ["string", "null"]}
    alts = []
    for act in ACTS:
        # The commitment between the span and the act: read off the words before the
        # label, as the slots are ("Let Me Speak Freely": field order changes what a
        # constrained model does), and the same in every alternative, so it chooses no act.
        props = {"span": {"type": "string"},
                 "commit": {"type": "string", "enum": list(COMMITS)},
                 "act": {"const": act},
                 **{s: slot for s in ACT_SLOTS.get(act, ())},
                 # The means last, with the deed and its slots already written, and the
                 # same in every alternative, so it chooses no act (gm/means.py). The
                 # power's name before the verdict, so the verdict is written with its
                 # evidence already chosen — the deed reader's order.
                 "power": slot,
                 "means": {"type": "string", "enum": list(MEANS)}}
        alts.append({"type": "object", "properties": props, "required": list(props),
                     "additionalProperties": False})
    out = schema()
    out["properties"]["actions"]["items"] = {"anyOf": alts}
    return out


def reply_schema() -> dict:
    return per_act_schema() if SCHEMA == "per_act" else schema()


def _demo_reply(frame: dict) -> str:
    """A demonstration in the shape the sampler holds the reply to. A demonstration that
    names no commitment is `done`."""
    acts = []
    for a in frame.get("actions") or []:
        commit = a.get("commit") or "done"
        means = {"power": a.get("power"), "means": a.get("means") or "ordinary"}
        if SCHEMA != "per_act":
            acts.append({"span": a.get("span", ""), "commit": commit,
                         **{s: a.get(s) for s in SLOTS}, **means, "act": a["act"]})
            continue
        acts.append({"span": a.get("span", ""), "commit": commit, "act": a["act"],
                     **{s: a.get(s) for s in ACT_SLOTS.get(a["act"], ())}, **means})
    return json.dumps({"question": frame.get("question", False), "actions": acts,
                       "claims": frame.get("claims", [])})


def messages(sentence: str) -> list[dict]:
    system = (
        "You read what a player typed in a text role-playing game and write down, in "
        "order, each thing their character sets out to do. Copy every slot as words "
        "from the sentence itself — never a paraphrase, never a word that is not "
        "there. Leave a slot null when the sentence does not say it. A question asked "
        "of the game, not done in it, is question=true with no actions. Anything the "
        "player states as having happened, rather than attempts, is a claim.\n\n"
        "The acts:\n" + _WHAT_EACH_IS)
    out = [{"role": "system", "content": system}]
    for said, frame in _DEMOS:
        out.append({"role": "user", "content": said})
        out.append({"role": "assistant", "content": _demo_reply(frame)})
    out.append({"role": "user", "content": sentence})
    return out


_TIME_WORD = re.compile(
    r"\b(?:until|till|for|while|dawn|dusk|noon|midday|midnight|morning|evening|night|"
    r"tonight|tomorrow|hours?|minutes?|days?|weeks?|months?|years?|dark|light|sunset|"
    r"sunrise|daybreak|nightfall|moment|bell|o'clock|am|pm)\b", re.I)


# A slot that is nothing but a time: "a while", "for an hour", "until he stops moving".
_A_TIME = re.compile(r"^(?:until|till|for|all|a|the)\s+(?:while\b|night\b|day\b|hour|moment|morning|evening)|^(?:until|till)\b|^for\s+(?:a|an|the|\d+|one|two|three|some|several)\b", re.I)


_NULL_WORDS = frozenset({"none", "null", "n/a", "-"})


def _within(span, sentence: str) -> bool:
    return bool(span) and str(span).strip().lower() in sentence.lower()


def ground(frame: dict, sentence: str) -> tuple[dict, list[str]]:
    """Every slot must be the player's own words: one that is not is dropped, and said.
    A claim that is not in the sentence is dropped the same way."""
    dropped: list[str] = []
    actions = []
    for a in frame.get("actions") or []:
        if not isinstance(a, dict) or a.get("act") not in ACTS:
            continue
        kept = {"act": a["act"]}
        # How far it is done; a reply from the flat schema of before 2026-10-03, or a
        # value outside the enum, is `done` — the reading the turn always acted on.
        commit = str(a.get("commit") or "done")
        if commit != "done":
            kept["commit"] = commit if commit in COMMITS else "done"
        used: set[str] = set()
        for s in ACT_SLOTS.get(a["act"], SLOTS):
            v = a.get(s)
            if v in (None, ""):
                continue
            v = str(v).strip()
            # The null written as a word: the per-act schema's probe came back
            # `target: "none"` on a gesture. Nothing is there.
            if v.lower() in _NULL_WORDS:
                continue
            if not _within(v, sentence):
                dropped.append(f"{a['act']}.{s}={v!r}")
                continue
            # One phrase, one slot: measured, "I punch him again" came back with "him"
            # as target, object AND place. The act's first slot keeps it — and a phrase
            # inside another slot's phrase is part of that description, not a second
            # thing: "a scribe" as the place of "a scribe who can read a letter".
            low = v.lower()
            if any(low in u or u in low for u in used):
                continue
            # A time is a time: "the face", "again" and "keep" all came back as one.
            if s == "time" and not _TIME_WORD.search(v):
                continue
            # And a time written into another slot is the time: "I follow the tracks a
            # while" came back with "a while" as the object.
            if s != "time" and _A_TIME.match(v):
                if "time" in ACT_SLOTS.get(a["act"], SLOTS) and "time" not in kept:
                    kept["time"] = v
                    used.add(low)
                continue
            kept[s] = v
            used.add(low)
        _speech_is_not_a_target(kept, dropped)
        # By what means (`MEANS`). Absent or outside the enum — a reading from before
        # 2026-10-05, a remembered test frame — is ordinary: the reading the turn always
        # acted on. A power's name is held to the sentence like every slot; one that is
        # not the player's words is dropped and said, and the means stands without it
        # (gm/means.py then asks the sheet about the deed's own words instead).
        means = str(a.get("means") or "ordinary")
        if means in MEANS and means != "ordinary":
            kept["means"] = means
        power = str(a.get("power") or "").strip()
        if power and power.lower() not in _NULL_WORDS:
            if _within(power, sentence):
                kept["power"] = power
            else:
                dropped.append(f"{a['act']}.power={power!r}")
        # The action's own words, when they are the player's: what a targeted second
        # question is asked about (`confirm_sale`).
        if _within(a.get("span"), sentence):
            kept["span"] = " ".join(str(a["span"]).split())
        actions.append(kept)
    actions = merge_repeats(actions)
    claims = [c for c in (frame.get("claims") or []) if _within(c, sentence)]
    dropped += [f"claim={c!r}" for c in (frame.get("claims") or []) if not _within(c, sentence)]
    return ({"question": bool(frame.get("question")), "actions": actions,
             "claims": claims}, dropped)


def merge_repeats(actions: list[dict], dropped: list[str] | None = None) -> list[dict]:
    """One deed read twice is one deed: two actions in a row with the same act whose
    slots do not disagree are merged, the first's slots kept and the second's added.

    Measured 2026-10-03 on the first 60 labelled lines, 3 of the 19 misses: "I make camp
    and sleep until dawn" came back `rest` then `rest, time: until dawn`; "I look around
    and take stock" `look` then `look …`; "I thank her, say goodnight" `talk, target: her`
    then `talk, says: goodnight`. Each would be two ops in the turn — two rests, two says.
    Structure only, never the words: a second action that names a DIFFERENT target, object,
    place, time or words is a second deed ("I buy bread and buy cheese"; "I turn my back
    on him and tell the barkeep he smells" insults two people), and stays.

    Narrowed in round 2: never when the SECOND is bare. The first rule — merge whenever
    nothing disagrees — joined `consume, object: …` and a bare `consume` into one, and the
    held-out set had that as two deeds ("eat … and drink"): one of the 4.4 acts-in-order
    points lost, found by an act-level count of the flips (no sentence read). A bare second
    is a deed whose object went unsaid; a second that only adds to the first (`rest` then
    `rest, time: until dawn`; `attack, target: him` then the same with `object: the face`)
    is the first spelled out. A first try that merged only after a bare FIRST lost the
    second kind (`attack` twice, the same count). And the commitments must agree."""
    out: list[dict] = []
    for a in actions:
        prev = out[-1] if out else None
        if prev is not None and prev.get("act") == a.get("act") \
                and prev.get("commit", "done") == a.get("commit", "done") \
                and prev.get("means", "ordinary") == a.get("means", "ordinary") \
                and any(a.get(s) for s in SLOTS) and not any(
                    prev.get(s) and a.get(s) and prev[s].lower() != a[s].lower()
                    for s in SLOTS):
            for s in (*SLOTS, "power"):
                if a.get(s) and not prev.get(s):
                    prev[s] = a[s]
            if dropped is not None:
                dropped.append(f"{a['act']} (the same deed twice, merged)")
            continue
        out.append(a)
    return out


_SAY_HEAD = re.compile(r"^\s*(?:say|says|said|tell|tells|ask|asks|shout|shouts|whisper|"
                       r"whispers|murmur|murmurs|reply|replies|answer|answers|mutter|"
                       r"mutters|add|adds)\b[\s,:]*", re.I)


def _speech_is_not_a_target(action: dict, dropped: list[str]) -> None:
    """A quotation is never who is spoken to; "say X" is speech, not a person called
    "say X".

    Measured on the owner's 2026-10-03 save (item 13): `I give a friendly wink and say
    "just trying to start a conversation and see what is happening here."` came back
    `talk, target: say "just trying…"` — the span was the sentence's own words, so
    grounding kept it — and `introduce` minted a person by that name. Inform's grammar
    keeps a topic or a quoted string out of the object slots entirely (WI §7.6, §17.5),
    and TADS 3 reads SAY's argument as a literal (`LiteralAction`). Same here, in code:
    a target whose shape is not a person's (`names.not_a_name`) is dropped, and its
    words become what is said when the act can say anything and nothing else was read."""
    from rules.names import not_a_name

    target = action.get("target")
    if not target or not not_a_name(target):
        return
    del action["target"]
    dropped.append(f"{action['act']}.target={target!r} (speech, not somebody)")
    if "says" in ACT_SLOTS.get(action["act"], ()) and not action.get("says"):
        from .speech import spans

        # The one quotation scanner (gm/speech.py), never a second rule here.
        quoted = [target[a + 1:b - 1] for a, b in spans(target) if b - a > 2]
        words = (quoted[0] if quoted else _SAY_HEAD.sub("", target)).strip()
        if words:
            action["says"] = words


def interpret(sentence: str, *, model: str | None = None, host: str | None = None,
              provider: str | None = None, api_key: str = "",
              temperature: float = 0.0) -> dict:
    """The frame for one sentence: {"question", "actions", "claims", "dropped",
    "seconds", "raw"}. The narrator's model unless another is named — the model already
    loaded, because a second model's load is what dominates local latency."""
    from . import client
    from play import modelcfg

    # A role nobody configured comes back as {"api_key": ""}, which is truthy.
    cfg = modelcfg.for_role("interpreter")
    if not cfg.get("model"):
        cfg = modelcfg.for_role("narrator")
    started = time.monotonic()
    reply = client.chat(messages(sentence), model or cfg["model"],
                        host or cfg["host"], as_json=True, think=False,
                        temperature=temperature, num_predict=400,
                        provider=provider or cfg.get("provider", "ollama"),
                        api_key=api_key or cfg.get("api_key", ""), schema=reply_schema())
    try:
        raw = reply.json()
    except Exception:
        raw = {}
    frame, dropped = ground(raw if isinstance(raw, dict) else {}, sentence)
    frame.update(dropped=dropped, seconds=round(time.monotonic() - started, 2),
                 raw=reply.text)
    return frame


# --- a sale, asked again ---------------------------------------------------------------------
#
# CLAUDE.md's rule: detect mechanically, repair with a targeted call. A sale is the one
# goods op the player cannot take back, and the frozen reader still misread its
# commitment on the owner's own lines (round 2's replay, readings from the frozen reader):
# "I take the crate to the man in the counting house who will buy it from me" came back
# `sell` DONE, and "I smile and flirt with the clerk and offer the crate for coin" `sell`
# DONE — the round-1 regression back, through a different door. So when the table is
# about to build a sale to somebody who keeps no counter, the reader is asked that one
# question alone, with the sale's own words in front of it: closed now, only offered,
# meant for later, or asked about? One enum, demonstrated; the frame's other twenty
# fields are not asked again. The demonstrations are not in the labelled set.
_SALE_DEMOS = [
    ("I tell the tanner the hides are his for four silver.", "the hides are his", "done"),
    ("I offer the tanner the hides.", "offer the tanner the hides", "tried"),
    ("I haggle with the tanner over the hides, smiling.", "haggle with the tanner over the hides",
     "tried"),
    ("I bring the hides to the tanner, who always buys them from me.",
     "who always buys them from me", "intended"),
    ("I shake the tanner's hand on the price.", "shake the tanner's hand on the price", "done"),
    ("Tomorrow I'll sell the hides to the tanner.", "sell the hides to the tanner", "intended"),
    ("I ask the tanner if she would take the hides.", "if she would take the hides", "asked"),
    ("I hand the hides over to the tanner and take her coin.",
     "hand the hides over to the tanner", "done"),
]


def sale_messages(sentence: str, span: str) -> list[dict]:
    system = ("A player in a role-playing game wrote the line below. Answer one question "
              "about the sale in it: is the sale CLOSED now (done: agreed, accepted, handed "
              "over for the price), only OFFERED or haggled over (tried), meant for LATER or "
              "something somebody else will do (intended), or ASKED ABOUT (asked)?")
    out = [{"role": "system", "content": system}]
    for said, part, commit in _SALE_DEMOS:
        out.append({"role": "user", "content": f"Line: {said}\nThe sale: {part}"})
        out.append({"role": "assistant", "content": json.dumps({"commit": commit})})
    out.append({"role": "user", "content": f"Line: {sentence}\nThe sale: {span}"})
    return out


def confirm_sale(sentence: str, span: str, *, model: str | None = None) -> str:
    """How far the sale in `span` is done, asked alone: one of `COMMITS`; "" when the
    call fails (the caller then holds the sale back — an offer, never a sale)."""
    from . import client
    from play import modelcfg

    cfg = modelcfg.for_role("interpreter")
    if not cfg.get("model"):
        cfg = modelcfg.for_role("narrator")
    schema = {"type": "object", "properties": {"commit": {"type": "string",
                                                          "enum": list(COMMITS)}},
              "required": ["commit"]}
    try:
        reply = client.chat(sale_messages(sentence, span), model or cfg["model"], cfg["host"],
                            as_json=True, think=False, temperature=0.0, num_predict=30,
                            provider=cfg.get("provider", "ollama"),
                            api_key=cfg.get("api_key", ""), schema=schema)
        got = str((reply.json() or {}).get("commit") or "")
    except Exception:  # noqa: BLE001 — a failed check holds the sale back
        return ""
    return got if got in COMMITS else ""


# --- a take from a person, asked again -------------------------------------------------
#
# Since 2026-10-08 a `give` the player makes from somebody else's hands is a TAKE
# (`Engine._op_give`): the owner is kept and the thing is marked stolen. That is right for
# "I take an apple from the fruit seller without paying" (measured: it used to be filed as
# the seller handing it over), and wrong for "I take the purse he holds out" — a reward
# would be a theft. Whether the holder agreed is not in the take's own words; it is in the
# beat before them, so the one question is asked with that beat in front of it: did the
# person give or offer it, or did the player take it without their agreement? Two enum
# values, demonstrated, none of them from the measured lines (tests/test_spoken_theft.py
# holds what was measured).
TAKE_ANSWERS = ("offered", "taken")

_TAKE_DEMOS = [
    ("The tanner is bent over a vat, her back to the street.",
     "I lift a strip of leather from the tanner's rack", "taken"),
    ("The old reeve holds out a small purse. \"For your trouble,\" he says.",
     "I take the purse from the reeve", "offered"),
    ("The baker slides a warm bun across the counter. \"On the house.\"",
     "I take the bun from her and thank her", "offered"),
    ("The gaoler snores on his stool, the ring of keys on his belt.",
     "I take the keys from the gaoler", "taken"),
    ("The pedlar haggles with a woman over a length of ribbon.",
     "I help myself to a ribbon from the pedlar's tray", "taken"),
    ("\"Go on, then — pick one,\" the fishwife says, tipping her basket towards you.",
     "I take a herring from the fishwife", "offered"),
    ("The clerk pushes the receipt across the desk for you to keep.",
     "I take the receipt from the clerk", "offered"),
    ("The cooper counts his barrels and does not look up.",
     "I grab a mallet from the cooper", "taken"),
]


def take_messages(beat: str, span: str) -> list[dict]:
    system = ("A player in a role-playing game takes something from another person. "
              "Using the scene just before, answer one question: did that person GIVE or "
              "OFFER it (held it out, handed it over, told them to take it, a gift, a "
              "reward, their change) — offered — or did the player take it WITHOUT the "
              "person agreeing (lifted, grabbed, helped themselves, did not pay, while "
              "the person was busy or asleep) — taken?")
    out = [{"role": "system", "content": system}]
    for before, said, answer in _TAKE_DEMOS:
        out.append({"role": "user", "content": f"Scene: {before}\nThe take: {said}"})
        out.append({"role": "assistant", "content": json.dumps({"took": answer})})
    out.append({"role": "user", "content": f"Scene: {beat or '(nothing yet)'}\n"
                                           f"The take: {span}"})
    return out


def confirm_take(beat: str, span: str, *, model: str | None = None) -> str:
    """"offered" or "taken" for a take from a person; "" when the call fails (the caller
    then leaves it a take — the engine's own rule, docs/items-have-owners.md)."""
    from . import client
    from play import modelcfg

    cfg = modelcfg.for_role("interpreter")
    if not cfg.get("model"):
        cfg = modelcfg.for_role("narrator")
    schema = {"type": "object", "properties": {"took": {"type": "string",
                                                        "enum": list(TAKE_ANSWERS)}},
              "required": ["took"]}
    try:
        reply = client.chat(take_messages(beat, span), model or cfg["model"], cfg["host"],
                            as_json=True, think=False, temperature=0.0, num_predict=20,
                            provider=cfg.get("provider", "ollama"),
                            api_key=cfg.get("api_key", ""), schema=schema)
        got = str((reply.json() or {}).get("took") or "")
    except Exception:  # noqa: BLE001 — a failed question leaves the take a take
        return ""
    return got if got in TAKE_ANSWERS else ""


# --- first aid, asked -----------------------------------------------------------------
#
# A deed aimed at somebody the engine says is dying (`acts_to_ops.first_aid`) may be first
# aid or anything else done to a body. The reader reads "I give first aid to the porter"
# as `other` and "I bandage him" as `use`, and no act of its vocabulary is first aid, so
# the one question is put on its own, with the deed's own words. Demonstrations written
# for this; none is a measured line.
AID_ANSWERS = ("first aid", "something else")

_AID_DEMOS = [
    ("press my cloak hard against the sailor's wound", "the sailor", "first aid"),
    ("drag the sailor into the shade of the wall", "the sailor", "something else"),
    ("stitch the gash in the hunter's thigh", "the hunter", "first aid"),
    ("say a prayer over the old drover", "the old drover", "something else"),
    ("try to stop the bleeding with my belt", "the guard", "first aid"),
    ("search the guard's boots for a hidden blade", "the guard", "something else"),
]


def aid_messages(span: str, patient: str) -> list[dict]:
    system = ("In a role-playing game, the player's character does something to a person "
              "who is lying on the ground dying, bleeding out. Answer one question: is the "
              "player trying to keep them alive — first aid, binding or stitching the "
              "wound, stopping the bleeding, tending them — or doing something else?")
    out = [{"role": "system", "content": system}]
    for said, who, answer in _AID_DEMOS:
        out.append({"role": "user", "content": f"Dying: {who}\nThe act: {said}"})
        out.append({"role": "assistant", "content": json.dumps({"act": answer})})
    out.append({"role": "user", "content": f"Dying: {patient}\nThe act: {span}"})
    return out


def confirm_first_aid(span: str, patient: str, *, model: str | None = None) -> str:
    """One of `AID_ANSWERS`; "" when the call fails (no first aid is built: the plan's own
    ops stand, as before)."""
    from . import client
    from play import modelcfg

    cfg = modelcfg.for_role("interpreter")
    if not cfg.get("model"):
        cfg = modelcfg.for_role("narrator")
    # The key is act: the deeds system keeps its own word out of everything the models are
    # shown (tests/test_deeds.py), and this question is about the act itself.
    schema = {"type": "object", "properties": {"act": {"type": "string",
                                                       "enum": list(AID_ANSWERS)}},
              "required": ["act"]}
    try:
        reply = client.chat(aid_messages(span, patient), model or cfg["model"], cfg["host"],
                            as_json=True, think=False, temperature=0.0, num_predict=20,
                            provider=cfg.get("provider", "ollama"),
                            api_key=cfg.get("api_key", ""), schema=schema)
        got = str((reply.json() or {}).get("act") or "")
    except Exception:  # noqa: BLE001
        return ""
    return got if got in AID_ANSWERS else ""


# --- who a blow lands on, asked ---------------------------------------------------------
#
# The owner, 2026-10-09: "if i say I attack the closest person or i go on a rampage or i
# assault a civilian etc. it should be able to start a fight." Measured live the same day
# (gemma-4-12B, a market of three bystanders on scratch data): "I attack the closest person."
# had the planner aim, rightly, at the fruit seller beside the player — and the fight
# declarer required a `spawn` behind it, so two bandits came out of nowhere and joined the
# fight on her side. `judgement.inject_fight` read the sentence with a regex and, finding
# nobody `_can_be_fought` (bystanders are not), conjured a template opponent.
#
# Who "the closest person", "a civilian" or "the biggest bruiser in the room" means is not
# in the words alone: it is the words held against the people standing here. So the one
# question is put with those people in front of it, as refs the sampler cannot leave: WHICH
# of them could the words mean — every one of them for "the closest person" or a rampage,
# the townsfolk for "a civilian", the one bruiser for "the biggest bruiser", nobody when
# nobody here fits. Which of those is NEAREST is the engine's to answer, from the squares
# people keep (`acts_to_ops.victims`), never the model's: a model asked "who is closest"
# would be guessing at a map it cannot see.
#
# Demonstrations written for this, with their own people; none is a measured line.
_VICTIM_DEMOS = [
    ("attack the closest person",
     [("c1", "a fishwife gutting herring"), ("c2", "the sailor with a bad leg"),
      ("c3", "the harbour guard")], ["c1", "c2", "c3"]),
    ("assault a civilian",
     [("c1", "the gate guard (a guard)"), ("c2", "a baker carrying loaves"),
      ("c3", "the old washerwoman")], ["c2", "c3"]),
    ("run amok through the stalls",
     [("c1", "the pedlar"), ("c2", "a girl selling ribbons")], ["c1", "c2"]),
    ("pick a fight with the biggest man in the tavern",
     [("c1", "a thin clerk"), ("c2", "the hulking stevedore with tattooed arms"),
      ("c3", "an old woman by the fire")], ["c2"]),
    ("punch the guard",
     [("c1", "a merchant"), ("c2", "the watchman at the door (a guard)")], ["c2"]),
    ("stab the priest",
     [("c1", "a farmer"), ("c2", "a small boy")], []),
    ("hit the nearest guard",
     [("c1", "the sergeant (a guard)"), ("c2", "a spearman of the watch (a guard)"),
      ("c3", "a cloth merchant")], ["c1", "c2"]),
    ("keep swinging my sword",
     [("c1", "a merchant watching from his stall")], []),
]


def victim_messages(span: str, words: str, people) -> list[dict]:
    system = ("In a role-playing game the player's character attacks somebody. Here are the "
              "people standing nearby, each with a ref. Answer one question: which of them "
              "could the player's words mean? Everyone the words could fit — all of them "
              "for 'the closest person', 'someone', 'anyone' or a rampage; only those who "
              "fit a description ('a civilian' is anybody who is not a guard or soldier); "
              "the one person a name or a description picks out; nobody ([]) when nobody "
              "here fits the words.")
    out = [{"role": "system", "content": system}]

    def ask(deed, here):
        listed = "\n".join(f"{ref}: {label}" for ref, label in here)
        return f"People here:\n{listed}\nThe attack: {deed}"

    for deed, here, meant in _VICTIM_DEMOS:
        out.append({"role": "user", "content": ask(deed, here)})
        out.append({"role": "assistant", "content": json.dumps({"meant": meant})})
    # The span holds the target words; when the reader's span lost them, they are added.
    deed = span if (not words or words.lower() in str(span).lower()) else f"{span} ({words})"
    out.append({"role": "user", "content": ask(deed or words, people)})
    return out


def confirm_victims(span: str, words: str, people, *,
                    model: str | None = None) -> list[str] | None:
    """The refs among `people` ((ref, label) pairs, everyone standing here) that the attack
    in `span` could mean; [] for nobody here; None when the call fails (the caller then
    builds nothing, and the plan stands)."""
    from . import client
    from play import modelcfg

    refs = [str(r) for r, _ in people]
    if not refs:
        return []
    cfg = modelcfg.for_role("interpreter")
    if not cfg.get("model"):
        cfg = modelcfg.for_role("narrator")
    schema = {"type": "object",
              "properties": {"meant": {"type": "array",
                                       "items": {"type": "string", "enum": refs}}},
              "required": ["meant"]}
    try:
        reply = client.chat(victim_messages(span, words, people), model or cfg["model"],
                            cfg["host"], as_json=True, think=False, temperature=0.0,
                            num_predict=20 + 8 * len(refs),
                            provider=cfg.get("provider", "ollama"),
                            api_key=cfg.get("api_key", ""), schema=schema)
        got = (reply.json() or {}).get("meant")
    except Exception:  # noqa: BLE001 — a failed question builds nothing
        return None
    if not isinstance(got, list):
        return None
    # Checked in code, whatever the sampler enforced: a ref that is not here is no answer.
    return list(dict.fromkeys(str(r) for r in got if str(r) in refs))


# --- in the turn ---------------------------------------------------------------------
#
# First integration (2026-09-27), additive by design: the research's advice was to keep
# the fast word-detectors as a second opinion (Rasa's pattern) and to retire each one
# only on a measured comparison. So the reading is (1) shown to the planner as fact, (2)
# joined to the ops the schema requires, (3) handed to the readers that need a slot
# (who is sought, what is bought, whose house), with the regex as the fallback, and (4)
# logged beside the detectors' opinion so each disagreement is on the record.
_READINGS: dict[str, dict] = {}


def _key(text: str) -> str:
    return " ".join(str(text or "").split()).lower()


def remember(text: str, frame: dict | None) -> None:
    """This turn's reading of this sentence, for the readers that ask later in the turn."""
    if len(_READINGS) > 64:
        _READINGS.clear()
    if frame is not None:
        _READINGS[_key(text)] = frame


def reading_of(text: str) -> dict | None:
    return _READINGS.get(_key(text))


def ops_for(frame: dict | None, scene=None, places=()) -> list[str]:
    """The ops the reading commits the turn to, where the reading grounds.

    Only the acts whose op cannot go wrong for want of a guess: a `go` to a place this
    town really has (the model still names it, from the brief's list); the house calls
    and break-ins; sleep; a wait with a time; an insult; words said. Buying opens the
    counter and is not an op; a fight's attacks are the fight schema's already."""
    from rules import places as places_mod

    ops: list[str] = []
    here = str(getattr(scene, "at", "") or "")

    def add(op):
        if op not in ops:
            ops.append(op)

    for a in (frame or {}).get("actions") or []:
        act = a.get("act")
        # A plan, a purpose or a question owes no op this turn (`COMMITS`): "I head for
        # the stables to ask about a horse" walks, and the asking is the next turn's.
        if not acting(a):
            continue
        if act == "cast" and scene is not None:
            # Where the spell goes, grounded here once: the cast's object, target or place
            # that is not the spell's own name, read by the same reader a typed and an
            # attached cast share (`areas.aim_from_words`). Kept on the action, so the
            # planner is shown it as fact (`brief_lines`) and the turn log records what
            # the words aimed at. No op is added: the cast is declared by its spell's
            # name (`judgement.inject_cast`), which the reading does not know.
            aim = cast_aim(frame, scene, a)
            if aim:
                a["aim"] = aim
        if act == "go" and a.get("place"):
            p = places_mod.find(places, a["place"]) if places else None
            if p is not None and p.id != here:
                add("travel")
            elif p is None and _outward(a["place"]) and _has_outside(places):
                # "the nearest crossroads", "the path away from town": a phrase no place
                # here is called, which names the ground outside (Bobby, turns 6 and 7).
                # The travel is owed; `travel_choices` holds it to the ring's names.
                add("travel")
        elif act == "leave" and _leaving(a, scene, places):
            # Bobby's turn 5: `leave: outside it` mapped to no op at all, and the plan
            # took the nearest listed place — the way in, INSIDE the village
            # (docs/playtest-2026-09-28.md, 16.1). Leaving is a move.
            add("travel")
        elif act == "journey":
            add("journey")
        elif act in ("call_on", "break_in", "rest"):
            add(act)
        elif act == "wait" and a.get("time"):
            add("advance_time")
        elif act == "insult":
            add("provoke")
        elif act == "talk" and a.get("says"):
            add("say")
        elif act == "seek" and a.get("target") and scene is not None:
            # Somebody sought who is HERE (item 8, 2026-09-30: "I aprouch the clockwork
            # Spy" planned a travel to the gate and left the Spy behind). Kept on the
            # action, so `supported` does not let this seek stand behind a travel.
            from rules import scope as scope_mod

            ref = scope_mod.in_the_room(scene, str(a["target"]))
            person = (getattr(scene, "actors", {}) or {}).get(ref)
            if person is not None and not getattr(person, "is_pc", False):
                a["here"] = ref
    return ops


def spell_named(scene, words) -> object | None:
    """The spell the player's caster can reach whose name the words hold, or None — read
    by `judgement.spell_in_words` against the whole catalogue, word-bounded and longest
    first, so "cure light wounds" is Cure Light Wounds (and None for a wizard who cannot
    reach it), never Light (item 4, 2026-09-30: the substring match here and in
    `inject_cast` were the same rule twice). Asked of the book, the prepared list and the
    class's own list, as `judgement.inject_cast` asks."""
    from rules import casting, spells as spells_mod

    from . import judgement

    pc = scene.pc() if scene is not None and hasattr(scene, "pc") else None
    said = " ".join(str(words or "").lower().split())
    if pc is None or not said or not casting.is_caster(pc):
        return None
    ids = [sp.id for lvl in casting.known_spells(
        pc, up_to=casting.highest_spell_level(pc)).values() for sp in lvl]
    ids += [s for s in (getattr(pc, "prepared", {}) or {}) if s not in ids]
    chosen = judgement._reachable_by_name(judgement.spell_in_words(said), ids)
    if not chosen:
        return None
    try:
        return spells_mod.get(chosen)
    except KeyError:
        return None


def cast_aim(frame: dict | None, scene, action: dict | None = None,
             spell=None) -> str | None:
    """Where the reading's cast is aimed, as an aim (`areas.AIM_PATTERN`), or None.

    Measured 2026-09-28 (docs/playtest-2026-09-28.md 21.2): "I cast burning hands into the
    tree tops" was read `cast, object: burning hands, target: the tree tops` — the
    treetops a *target*, as if a creature — and nothing turned that phrase into anything
    a cast could be pointed at. A cast act's target, place and object that is not the
    spell's own name are each grounded by `areas.aim_from_words` (a person here → `ref:`,
    a thing or a feature → `object:`, "above my head" → `dir:up`), target first: it is the
    words about WHO or WHAT. The spell is the one the action names when the caster can
    reach it, so a direction is not offered to a burst.

    `action` is one cast action of the frame; the first cast action when None."""
    from rules import areas

    if scene is None or not frame:
        return None
    pc = scene.pc() if hasattr(scene, "pc") else None
    if pc is None:
        return None
    acts = [action] if action is not None else [
        a for a in frame.get("actions") or [] if isinstance(a, dict) and a.get("act") == "cast"]
    for a in acts:
        if not isinstance(a, dict) or a.get("act") != "cast":
            continue
        chosen = spell
        if chosen is None:
            for slot in ("object", "target", "place"):
                chosen = spell_named(scene, a.get(slot))
                if chosen is not None:
                    break
        own = " ".join(str(getattr(chosen, "name", "") or "").lower().split())
        for slot in ("target", "place", "object"):
            phrase = " ".join(str(a.get(slot) or "").split())
            if not phrase or (own and own in phrase.lower()):
                continue
            aim = areas.aim_from_words(scene, pc.ref, phrase, chosen)
            if aim:
                return aim
    return None


def travel_choices(frame: dict | None, scene, places, location) -> tuple[str, ...]:
    """The place names a declared travel may choose among — the `places` enum of
    `prompts.turn_schema`, so the planner walks to a place that exists and invents none.

    Every place here but the one the party stands in — unless the reading says the
    party is LEAVING (Lane B, docs/design-b-space.md 16.1):

    - leaving the settlement ("I leave the village", "the path away from town"): the
      ring's names only — the outskirts, the fields, the roads out. The enum is enforced
      by the sampler (6 of 6, memory `ollama-schema-enforcement`), so the plan cannot
      walk to the way in and call it leaving, which is what Bobby's turn 5 did;
    - leaving a building ("I leave the tavern"): its exits under the sky only.

    With no ring (no world to build one from) the answer is today's.
    """
    here = getattr(scene, "at", None)
    everything = tuple(p.name for p in places if p.id != here)
    going = _going(frame, scene, places, location)
    if going == "settlement":
        from rules import places as places_mod

        ring = tuple(p.name for p in places if places_mod.is_ring(p.id) and p.id != here
                     and "along-the-road-to-" not in p.id)
        return ring or everything
    if going == "building":
        from rules import places as places_mod

        by_id = {p.id: p for p in places}
        cur = by_id.get(here)
        street = tuple(by_id[x].name for x in (cur.exits if cur else ())
                       if x in by_id and not places_mod.is_indoors(
                           x, by_id[x].terrain, by_id[x].shape))
        return street or everything
    return everything


# What a player says when the place they are leaving is the settlement itself, or the
# ground they want is outside it. Matched as whole words in the slot.
_SETTLEMENT_WORDS = frozenset({"town", "village", "city", "settlement", "outside", "out",
                               "it", "here", "walls", "hamlet", "place"})
_OUTWARD_WORDS = frozenset({"road", "roads", "path", "track", "trail", "crossroads",
                            "crossroad", "fields", "field", "outskirts", "signpost",
                            "milestone", "countryside", "wilds", "wilderness"})
_WORDS_RE = re.compile(r"[a-z']+")


def _outward(phrase) -> bool:
    words = set(_WORDS_RE.findall(str(phrase or "").lower()))
    return bool(words & _OUTWARD_WORDS) or "out of town" in str(phrase or "").lower()


def _has_outside(places) -> bool:
    from rules import places as places_mod

    return any(places_mod.is_ring(p.id) for p in places or ())


def _leaving(action: dict, scene, places, location=None) -> str:
    """"settlement", "building" or "" for one `leave` action of the reading."""
    from rules import places as places_mod

    here_id = str(getattr(scene, "at", "") or "")
    if places_mod.setting_of(here_id) == "outside":
        return ""                      # already out: "leave" names nowhere to go
    slot = str(action.get("place") or "").strip().lower()
    words = set(_WORDS_RE.findall(slot))
    name = str(getattr(location, "name", "") or "").lower()
    by_id = {p.id: p for p in places or ()}
    cur = by_id.get(here_id)
    named = places_mod.find(places, slot) if slot else None
    indoors = cur is not None and places_mod.is_indoors(cur.id, cur.terrain, cur.shape)
    # Asked of the place's own id when the list does not carry it (the floorplan answers
    # either way, `places.is_indoors`).
    roofed = indoors if cur is not None else bool(here_id) and places_mod.is_indoors(here_id)
    if not slot and here_id and not roofed:
        # A bare "walk off" under the open sky names nothing to leave: not a building
        # (there is none around them) and not the settlement (nobody said so). Measured
        # 2026-10-08 (the deeds lane, local model): "I take another apple from the fruit
        # seller and walk off" read `leave` with no place, this answered "settlement",
        # the travel was owed with only the roads out to choose from, and the player
        # walked out of Vormoor onto the road to Scrapden over an apple. Inform's EXIT
        # outside any container answers "But you aren't in anything at the moment" —
        # leaving needs a thing to leave. No walk is owed; the plan may still choose one.
        return ""
    if (not slot or words & _SETTLEMENT_WORDS or (name and name in slot)
            or (location is not None and places_mod.scale_of(location) in words)):
        if indoors and slot and (named is not None and named.id == here_id):
            return "building"
        if indoors and not slot:
            return "building"
        return "settlement" if _has_outside(places) or not indoors else "building"
    if named is not None and named.id == here_id and indoors:
        return "building"
    return ""


def _going(frame, scene, places, location) -> str:
    """Whether the reading leaves the settlement, a building, or neither."""
    for a in (frame or {}).get("actions") or []:
        if a.get("act") == "leave":
            got = _leaving(a, scene, places, location)
            if got:
                return got
        if a.get("act") == "go" and a.get("place") and _outward(a["place"]) \
                and _has_outside(places):
            from rules import places as places_mod

            if places_mod.find(places, a["place"]) is None:
                return "settlement"
    return ""


# Which acts of the reading can stand behind an op a word-detector requires. An op with
# no row here is not judged (the reading has no view on it).
_OP_NEEDS = {
    "travel": {"go", "leave", "journey", "search", "seek", "call_on"},
    "journey": {"journey"}, "introduce": {"seek", "talk", "call_on"},
    "say": {"talk", "insult"}, "provoke": {"insult"}, "give": {"give", "take", "drop"},
    "sell": {"sell"},
    "rest": {"rest"}, "advance_time": {"wait", "rest"}, "call_on": {"call_on"},
    "break_in": {"break_in"}, "forage": {"gather"}, "prospect": {"gather"},
    "gather": {"gather"},
    "loot": {"take", "steal"}, "cast": {"cast"},
    "use_item": {"consume", "use"}, "drink": {"consume"}, "eat": {"consume"},
    "taste": {"consume", "use"},
}


def supported(ops: list[str], frame: dict | None) -> tuple[list[str], list[str]]:
    """(the detectors' ops the reading supports, the ones it does not). Measured live
    2026-09-27: a detector required `give` for "I buy a dragon's egg", which the reading
    read — rightly — as a purchase. On the labelled set the reading's acts score F1 0.91
    against the detectors' 0.47, so where the two disagree the reading decides, and the
    overruled op is logged.

    A `seek` of somebody HERE (`ops_for` marks it `here`) licenses no travel: you do not
    walk to another place to find the person beside you. Measured on the 2026-09-30 save
    (turn_log row 82). Inform's GO TO takes only a room for the same reason (Emily
    Short's *Approaches*, "go to [any visited room]")."""
    # Only what is done or tried now stands behind an op (`COMMITS`).
    actions = [a for a in (frame or {}).get("actions") or [] if acting(a)]
    acts = {a.get("act") for a in actions}
    elsewhere = {a.get("act") for a in actions
                 if not (a.get("act") == "seek" and a.get("here"))}
    kept, dropped = [], []
    for op in ops:
        need = _OP_NEEDS.get(op)
        have = elsewhere if op == "travel" else acts
        (kept if need is None or have & need else dropped).append(op)
    return kept, dropped


# The acts under which the player can come away holding something. One set for both
# doors that judge a give to the player: `drop_unread_gifts` and the act→op table's
# overrule (`acts_to_ops.apply`; until 2026-10-03 the other door was the retired
# `judgement.inject_goods`).
GETTING_ACTS = frozenset({"give", "take", "buy", "steal", "gather", "sell"})


def gets_nothing(frame: dict | None) -> bool:
    """Whether a reading exists and none of its acts can leave the player holding
    anything. False when there is no reading to judge by."""
    if not frame or frame.get("error"):
        return False
    return not ({a.get("act") for a in frame.get("actions") or [] if acting(a)}
                & GETTING_ACTS)


# And the other direction: the acts under which the player can part with something —
# handing it over, dropping it, paying, selling. Measured 2026-10-03 on the market-talk
# save: "I give a friendly wink and say …" was read as `other` + `talk`, the reading
# overruled the detector's `give`, and `judgement.inject_goods` (retired since) planned
# one anyway — "Kesst Vayr has no friendly wink to give", and the ledger kept "handed
# something to Kesst Vayr". The rule that already held for gains holds for hand-overs;
# `drop` joined with the act itself.
PARTING_ACTS = frozenset({"give", "sell", "buy", "drop"})


def hands_nothing(frame: dict | None) -> bool:
    """Whether a reading exists and none of its acts can part the player from anything.
    False when there is no reading to judge by."""
    if not frame or frame.get("error"):
        return False
    return not ({a.get("act") for a in frame.get("actions") or [] if acting(a)}
                & PARTING_ACTS)


def drop_unread_gifts(raw, frame: dict | None) -> tuple[list, list]:
    """(the plan's intents, the gives dropped). A `give` to the player that no act of the
    reading asked for is the model conjuring: goods are open (rules/goods.py), so a give
    makes whatever it names. Measured live 2026-09-27 on the fight script, both with and
    without the interpreter: "Kesst Vayr takes fight", "takes table", "takes c3" — for
    "I pick a fight", "I throw him over a table". Only with a reading to judge by, and
    only gives to the player; a give the player makes to somebody else is left alone."""
    if not isinstance(raw, list) or not frame or frame.get("error"):
        return (raw if isinstance(raw, list) else []), []
    if not gets_nothing(frame):
        return raw, []
    kept, dropped = [], []
    for r in raw:
        p = (r.get("params") or {}) if isinstance(r, dict) else {}
        to = str(p.get("to") or "").lower()
        if (isinstance(r, dict) and str(r.get("op", "")).lower() == "give"
                and (to in ("pc", "you", "player") or not p.get("from_") and not to)):
            dropped.append(str(p.get("item") or ""))
            continue
        kept.append(r)
    return kept, dropped


def brief_lines(frame: dict | None) -> str:
    """What the planner is told the player's words say, in order, as fact."""
    if not frame:
        return ""
    if frame.get("question") and not frame.get("actions"):
        return ("THE PLAYER'S WORDS, READ (fact): a question asked of the game, not "
                "something the character does. Answer it; the character does nothing.")
    rows = []
    for n, a in enumerate(frame.get("actions") or [], 1):
        slots = ", ".join(f"{s}: {a[s]}" for s in (*SLOTS, "aim") if a.get(s))
        # How far it is done, said: a plan or a question is context for the plan, never
        # an op of its own (`COMMITS`).
        how = {"tried": " (TRIED now: the outcome is the dice's or the other person's)",
               "intended": " (INTENDED, not done this turn: no op for it)",
               "asked": " (ASKED ABOUT, not done: no op for it)"}.get(
                   str(a.get("commit") or "done"), "")
        rows.append(f"{n}. {a['act']}" + (f" — {slots}" if slots else "") + how)
    out = ""
    if rows:
        out = ("THE PLAYER'S WORDS, READ (fact, in the order they are done; the plan "
               "carries each one done or tried now): " + " ".join(rows))
    if frame.get("claims"):
        out += (" THE PLAYER CLAIMS, and it is not so unless the engine makes it so: "
                + "; ".join(frame["claims"]) + ".")
    return out


_BARE_PRONOUN = {"him", "her", "them", "he", "she", "they", "it", "his", "their", "its",
                 "me", "you", "us"}


def target_of(frame: dict | None, acts=("seek", "call_on", "talk", "give", "buy",
                                         "follow")) -> str:
    """The person the sentence goes looking for or addresses, without its article —
    the reading's answer to `judgement.person_sought`. "" when it names nobody."""
    for a in (frame or {}).get("actions") or []:
        t = str(a.get("target") or "").strip()
        if a.get("act") in acts and t and t.lower() not in _BARE_PRONOUN:
            return re.sub(r"^(?:the|a|an|my|some)\s+", "", t, flags=re.I)
    return ""


# --- who is asked, and who is only asked ABOUT ---------------------------------------------
#
# Inform's rule for ASK … ABOUT (Recipe Book §6.2; the I7 Handbook): the person token must
# be in scope, the topic token reaches out of it. `judgement.inject_company` learned it for
# the spawn door (item 5.1 of the 2026-09-28 playtest). Measured live 2026-09-29 on G3's
# market-seek turn 1, the same sentence came through the OTHER door: "I ask the nearest
# person about the girl who sells herbs in the market." read `talk, target: the nearest
# person, says: about the girl who sells herbs in the market` — right — and the plan still
# wrote `introduce who="herbalist vendor"` and a `say` TO her. The girl is the topic.
_TOPIC_OPENS = re.compile(r"^(?:about|regarding|concerning|after|of)\s+(.+)$", re.I)
_ASKED_ABOUT = re.compile(
    r"\b(?:ask|asks|asking|question|questions|enquire|enquires|inquire|inquires|"
    r"talk|talks|speak|speaks|chat|chats|tell|tells)\b[^.!?;\"“]*?"
    r"\b(?:about|regarding|concerning|after)\s+([^.!?;\"“]+)", re.I)
_NOT_A_DESCRIBING_WORD = frozenset({
    "the", "a", "an", "some", "any", "who", "that", "which", "in", "at", "on", "of", "by",
    "to", "for", "from", "with", "and", "or", "is", "are", "person", "people", "one",
    "someone", "somebody", "anyone", "anybody", "folk", "nearest", "closest", "nearby",
    "next", "here", "there", "me", "my", "him", "her", "them", "his", "their",
})


def topics(frame: dict | None, sentence: str = "") -> list[str]:
    """The phrases the sentence asks ABOUT: a `talk` act's "about …" `says` slot, the part
    of its span after "about", and — with no reading — the sentence's own "ask … about …"."""
    out: list[str] = []
    for a in (frame or {}).get("actions") or []:
        if a.get("act") not in ("talk", "insult", "seek"):
            continue
        for slot in ("says", "span"):
            said = " ".join(str(a.get(slot) or "").split())
            m = _TOPIC_OPENS.match(said) if slot == "says" else _ASKED_ABOUT.search(said)
            if m and m.group(1).strip() not in out:
                out.append(m.group(1).strip())
    if not out:
        from .speech import blanked

        for m in _ASKED_ABOUT.finditer(blanked(str(sentence or ""))):
            topic = " ".join(m.group(1).split()).strip()
            if topic and topic not in out:
                out.append(topic)
    return out


def addressee(frame: dict | None, sentence: str = "") -> str:
    """Who a `talk` act speaks to, in the player's words — "the nearest person"; "" when
    the reading names nobody (the regex's answer is `judgement.person_sought`'s)."""
    for a in (frame or {}).get("actions") or []:
        if a.get("act") in ("talk", "insult") and str(a.get("target") or "").strip():
            return " ".join(str(a["target"]).split())
    return ""


def _describing(phrase: str) -> set[str]:
    from rules import population

    words = [w for w in re.findall(r"[a-z][a-z'-]+", str(phrase or "").lower())
             if w not in _NOT_A_DESCRIBING_WORD]
    return {population._stem(w) for w in words} | set(population._tokens(" ".join(words)))


def _shares(a: set[str], b: set[str]) -> bool:
    """A word in common: the same stem or synonym token ("vendor" and "sells" are both
    `sell`), or one stem the start of the other ("herbalist", "herbs")."""
    if a & b:
        return True
    return any(len(x) >= 4 and len(y) >= 4 and (x.startswith(y) or y.startswith(x))
               for x in a for y in b if not x.startswith("work:") and not y.startswith("work:"))


def in_topic(phrase: str, topic_list, addressed: str = "") -> bool:
    """Whether a person phrase is somebody the sentence only asks ABOUT: it shares a
    describing word with a topic and none with the person addressed."""
    mine = _describing(phrase)
    if not mine or not topic_list:
        return False
    if addressed and _shares(mine, _describing(addressed)):
        return False
    return any(_shares(mine, _describing(t)) for t in topic_list)


def bought(frame: dict | None) -> str:
    for a in (frame or {}).get("actions") or []:
        if a.get("act") == "buy" and a.get("object"):
            return str(a["object"])
    return ""


def called(frame: dict | None) -> tuple[str, bool]:
    for a in (frame or {}).get("actions") or []:
        if a.get("act") == "call_on":
            return str(a.get("target") or "her"), True
    return "", False


def broken_into(frame: dict | None) -> tuple[str, str]:
    for a in (frame or {}).get("actions") or []:
        if a.get("act") == "break_in":
            who = str(a.get("target") or "")
            who = re.sub(r"(?:'s|s')?\s*(?:front\s+)?(?:door|house|home|lock)\b.*$", "", who,
                         flags=re.I).strip()
            if who.lower() in ("the", "a", "an", ""):
                who = ""
            how = "pick" if re.search(r"\block|pick", str(a.get("object") or ""), re.I) \
                else "force"
            return who, how
    return "", ""
