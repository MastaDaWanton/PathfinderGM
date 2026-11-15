"""The rules judge as specialists: four small questions instead of one big ruling.

The owner, 2026-11-06, after the one-call judge and the 26B MoE tied at ~71%: "the whole
point was to break the task up into smaller less prone to error segments that have their
own specialist". The one-call judge (`judge.py`) is CLAUDE.md's measured failure: a model
asked for N things answers them all half-well. Its leniency moved with every prompt edit
(47% -> 32% -> 42%), because each instruction pulled on the same single answer.

An MoE's "experts" are not this: they are routed per token inside one model, not per task
(Mistral reported no clear topic specialisation in Mixtral's routing; recalled, not re-read).
This file splits the TASK. Each specialist gets one narrow question, its own instructions
and a closed answer; code combines the answers; numbers stay the book's.

  1. CLAIMS  — does the line rest on a claim (a rule, a fact, someone else's choice, a
               power the character lacks, more than a turn holds), and does it hold?
               A claim that does not hold refuses the line. Asked FIRST, alone, so no other
               job can pull it toward leniency.
  2. STAKES  — is anything at stake, and is the outcome in doubt? If not: say yes.
  3. ROLL    — which roll (type, then name); then, with that roll's RULE CARD loaded, what
               it is against. The owner's "rules as referenceable skills": only the card for
               the roll in hand is shown.
  4. BONUS   — what real thing in the scene helps or hinders: +4/+2/0/-2/-4.

Same model, same scene facts, same sheet, same answer key as the one-call judge; only the
design differs.
"""
from __future__ import annotations

import json

from . import judge as J

# --- 1. claims -----------------------------------------------------------------------------

CLAIM_KINDS = ["none", "rule", "fact", "someone_elses_choice", "own_ability",
               "beyond_the_world", "more_than_a_turn", "a_guess_about_someone"]
# The owner's ruling of 2026-11-06 ("it just need to know that you dont know that"): a
# secret about another person that the character does not know, used as leverage, is a
# SHOT IN THE DARK, settled by the GM's hidden odds roll, never refused as a false fact.
ODDS = ["likely", "even", "unlikely", "small"]
REFUSE_FOR = {"rule": "false_rule", "fact": "false_fact",
              "someone_elses_choice": "npc_choice", "own_ability": "character",
              "beyond_the_world": "world", "more_than_a_turn": "too_much"}

CLAIMS_SYSTEM = """You check ONE thing about a player's line in a Pathfinder 1st Edition \
game: does what they want rest on a CLAIM, and does that claim hold?

An attempt is not a claim. "I try to pick the lock", "I ask her for help", "I swing at \
him" are attempts: answer claim "none".

A claim is the player declaring something true so that they get what they want:
- rule: a rule that is not real ("a natural 20 means they all agree", "rogues are fastest", \
"high Strength means no roll", "an hour's rest heals me fully");
- fact: something about the scene, the past or a person that the scene facts do not say \
("you said it was unlocked", "she owes me", "they are scared of fire so they run");
- someone_elses_choice: deciding what another person does, feels or agrees to as if it \
were already so ("she signs the business over", "they make me chief", "she has to help, \
it's her job", "the other two run away") rather than trying to persuade them;
- own_ability: using a spell, power, skill, companion or item the character sheet does not \
give them;
- beyond_the_world: something the world cannot allow, however it is tried;
- more_than_a_turn: several separate feats that each need their own action, crammed into \
one moment ("knock out all four", "grab him, use him as a shield, then throw him at the \
others"). One action with a follow-through is not this.
- a_guess_about_someone: the player uses a secret about ANOTHER person as leverage or \
bait ("I know you've been skimming the tithe", "remind him about his debts") when nothing \
in the scene says the character knows it. The answer is not known yet: the GM rolls the \
odds in secret. For this kind, holds is "unsure".

NOT claims, whatever they sound like:
- a PURPOSE or HOPE: "I tip the bucket so the guard slips", "I shout so the crowd turns", \
"I drop back so he has to come to me". Saying what they hope will happen is part of an \
attempt; the dice and the other people decide whether it does. Only declaring that it \
HAS happened, or MUST happen, is a claim;
- a LIE told to someone ("I tell the guard I'm the mayor's nephew"): that is a Bluff \
attempt, not a claim;
- a small, plausible detail of the place that nothing contradicts (a loose board on an old \
jetty, a bucket in a stable yard, a candle on a tavern table): that is not a claim of fact;
- a combat manoeuvre anyone may try (trip, bull rush, grapple, disarm, dirty trick): \
without the Improved feat it only provokes, it is not a missing ability;
- one action with its natural follow-through (vault the fence and land on him; duck \
behind the cart and loose an arrow): that is not more_than_a_turn.

holds: "yes" only if the scene facts, the character sheet or the real rules make the claim \
true; "no" if they do not; "unsure" if you cannot tell. Only the SCENE and the SHEET are true."""

CLAIMS_SCHEMA = {
    "type": "object",
    "properties": {"why": {"type": "string"},
                   "claim": {"type": "string", "enum": CLAIM_KINDS},
                   "holds": {"type": "string", "enum": ["yes", "no", "unsure"]}},
    "required": ["why", "claim", "holds"],
}

ODDS_SYSTEM = """The player is guessing at a secret about another person, a secret the \
character does not actually know. Before anything else the GM rolls, in secret, whether \
the guess happens to be true. You set the odds of that roll from what the scene says about \
the person: their trade, their standing, their situation.

odds: "likely" (75%) when the scene makes it very plausible (a known gambler owing \
money), "even" (50%), "unlikely" (25%) for a specific secret about someone the scene gives \
no reason to suspect, "small" (10%) when it is far-fetched."""

ODDS_SCHEMA = {
    "type": "object",
    "properties": {"why": {"type": "string"},
                   "odds": {"type": "string", "enum": ODDS}},
    "required": ["why", "odds"],
}

# --- 2. stakes -----------------------------------------------------------------------------

STAKES_SYSTEM = """You check ONE thing about a player's line in a Pathfinder 1st Edition \
game: does it need a roll?

Say yes or roll the dice. A roll is only for when something is at stake (someone opposes \
it, something could go wrong that would matter) AND the outcome is in doubt for THIS \
character. Plain things that nobody contests and that are easy for them (walking \
somewhere, asking a question, eating, sitting, climbing onto a cart, flipping a table, \
cutting a rope, casting a cantrip or a spell they have prepared) need no roll.

at_stake: "something" or "nothing". outcome: "certain" or "in_doubt"."""

STAKES_SCHEMA = {
    "type": "object",
    "properties": {"why": {"type": "string"},
                   "at_stake": {"type": "string", "enum": ["something", "nothing"]},
                   "outcome": {"type": "string", "enum": ["certain", "in_doubt"]}},
    "required": ["why", "at_stake", "outcome"],
}

# --- 3. the roll ---------------------------------------------------------------------------

PICK_SYSTEM = """You name ONE roll for a player's line in a Pathfinder 1st Edition game: \
the roll that decides whether the attempt works.

roll_type: skill, attack, manoeuvre, ability, save or spell. roll_name: the skill \
(Bluff, Perception, Diplomacy, Sleight of Hand, Acrobatics, Climb, Disable Device, \
Intimidate, Sense Motive, Stealth, Heal, Knowledge (engineering)...), the attack \
(melee, ranged, touch, improvised), the manoeuvre (trip, bull rush, disarm, grapple, \
dirty trick, reposition, steal, drag, overrun, sunder), the ability (Strength...) or the \
save (fort, ref, will). Lying is Bluff. Persuading or asking a favour is Diplomacy. \
Threatening is Intimidate. Noticing or listening is Perception. Reading someone is Sense \
Motive. Palming or planting something is Sleight of Hand. Pushing, tripping or grabbing \
someone in a fight is a manoeuvre. Raw lifting or bursting is Strength.

multi: true if the plan needs more than one roll; name the FIRST that matters."""

PICK_SCHEMA = {
    "type": "object",
    "properties": {"why": {"type": "string"},
                   "roll_type": {"type": "string", "enum": J.ROLL_TYPES},
                   "roll_name": {"type": "string", "enum": J.NAMES + ["none"]},
                   "multi": {"type": "boolean"}},
    "required": ["why", "roll_type", "roll_name", "multi"],
}

# The rule cards: what the Core Rulebook says each roll is made against. Loaded one at a
# time, for the roll the PICK specialist named, so the TARGET specialist reads only the
# rules it needs (the owner's design: rules as situational, referenceable cards).
CARDS = {
    "skill:Bluff": "Bluff is opposed by the target's Sense Motive (against: opposed, skill "
                   "Sense Motive). The book's modifiers to the Bluff: the target wants to "
                   "believe it +5; believable +0; unlikely -5; far-fetched -10; the target "
                   "is drunk or impaired +5.",
    "skill:Diplomacy": "Diplomacy to change an attitude or make a request is against a DC "
                       "by the person's attitude: helpful 0, friendly 10, indifferent 15, "
                       "unfriendly 20, hostile 25 (plus their Cha modifier). A request is "
                       "harder for a lengthy or complicated favour (+5), dangerous help "
                       "(+10), or help that could get them punished (+15).",
    "skill:Intimidate": "Intimidate is against DC 10 + the target's Hit Dice + Wisdom "
                        "modifier (against: defence, dc:intimidate). Demoralizing one foe "
                        "in a fight is a standard action.",
    "skill:Perception": "Perception: hear a conversation DC 0, a creature walking 10, a "
                        "whispered conversation 15; +1 to the DC per 10 feet away; harder "
                        "when distracted or in noise. Spotting someone hiding is opposed by "
                        "their Stealth; spotting a pickpocket is opposed by their Sleight "
                        "of Hand.",
    "skill:Sense Motive": "Sense Motive: a hunch about someone is DC 20; seeing through a "
                          "lie is opposed by their Bluff.",
    "skill:Sleight of Hand": "Sleight of Hand is opposed by the Perception of whoever is "
                             "watching (against: opposed, skill Perception). Palming a "
                             "small object is DC 10 if nobody is watching.",
    "skill:Stealth": "Stealth is opposed by the Perception of whoever might notice.",
    "skill:Disable Device": "Disable Device is trained only. A simple lock DC 20, average "
                            "25, good 30.",
    "skill:Climb": "Climb: a knotted rope or a surface with ledges DC 5-10; very rough rock "
                   "or a tree 15; an uneven wall with narrow holds 20; brick or rough "
                   "natural rock 21-24.",
    "skill:Acrobatics": "Acrobatics: a long jump's DC is the distance in feet (double "
                        "without a 10-foot run-up); balancing on a narrow surface DC 5-20 "
                        "by its width; a soft landing from a fall DC 15.",
    "skill:Heal": "Heal: first aid to a dying creature DC 15; treat deadly wounds DC 20 "
                  "(needs a healer's kit); long-term care DC 15.",
    "skill:Swim": "Swim: calm water DC 10, rough water 15, stormy water 20.",
    "skill:Linguistics": "Linguistics to decipher writing: a simple message DC 20, a "
                         "standard text 25, intricate, exotic or very old writing 30.",
    "skill:Handle Animal": "Handle Animal: handle a trained animal DC 10, push it to do "
                           "something it does not know DC 25.",
    "attack": "An attack is against the target's AC (against: defence, ac); a touch attack "
              "against touch AC. An improvised weapon takes -4. A ranged attack takes -2 "
              "for each full range increment past the first.",
    "manoeuvre": "Every combat manoeuvre (bull rush, trip, disarm, grapple, dirty trick, "
                 "reposition, drag, steal, overrun, sunder) is the attacker's CMB against "
                 "the target's CMD (against: defence, cmd). Without the matching Improved "
                 "feat it provokes an attack of opportunity.",
    "ability": "An ability check is against a DC: average 10, tough 15, challenging 20. "
               "Breaking open a simple wooden door is Strength DC 13, a good door 18.",
    "save": "A saving throw is the target's, against the effect's own DC.",
    "skill": "A skill check is against a DC: easy 5, average 10, tough 15, challenging 20, "
             "formidable 25, heroic 30. Untrained Knowledge cannot beat DC 10.",
}


def card_for(what: str) -> str:
    return CARDS.get(what) or CARDS.get(what.split(":")[0].replace("cmb", "manoeuvre"), "") \
        or CARDS["skill"]


TARGET_SYSTEM = """You set what ONE roll is made against, in a Pathfinder 1st Edition game, \
from the rule card below.

THE ROLL: {what}
THE RULE CARD: {card}

against: a DC ("5" to "40"), or "opposed" (then name the other side's roll in \
opposed_by_type and opposed_by_name), or "defence" (then defence is ac, touch, flat, cmd, \
dc:intimidate or dc:other). action: in a fight what the attempt costs (free, swift, move, \
standard, full, more); out of a fight "none"."""

TARGET_SCHEMA = {
    "type": "object",
    "properties": {"against": {"type": "string", "enum": J.AGAINST},
                   "defence": {"type": "string", "enum": J.DEFENCE + ["none"]},
                   "opposed_by_type": {"type": "string", "enum": J.ROLL_TYPES + ["none"]},
                   "opposed_by_name": {"type": "string", "enum": J.NAMES + ["none"]},
                   "action": {"type": "string", "enum": J.ACTION + ["none"]}},
    "required": ["against", "defence", "opposed_by_type", "opposed_by_name", "action"],
}

# --- 4. the bonus --------------------------------------------------------------------------

BONUS_SYSTEM = """You set ONE number for a roll in a Pathfinder 1st Edition game: the \
circumstance bonus or penalty for HOW it is done.

+2 when the player makes clever use of something that is really in the scene (a thing, a \
place, a custom, a person's weakness the scene names); +4 only when it is excellent. -2 \
when the conditions named in the scene are against them (noise, status, distance, haste); \
-4 when badly against them. 0 otherwise. Nothing the scene does not mention counts."""

BONUS_SCHEMA = {
    "type": "object",
    "properties": {"why": {"type": "string"},
                   "bonus": {"type": "integer", "enum": [-4, -2, 0, 2, 4]}},
    "required": ["why", "bonus"],
}


def _ask(chat, model, system, user, schema, temperature, host):
    reply = chat([{"role": "system", "content": system}, {"role": "user", "content": user}],
                 model, host, as_json=True, temperature=temperature, num_predict=300,
                 schema=schema, think=False)
    text = str(getattr(reply, "text", "") or "")
    try:
        got = json.loads(text)
    except ValueError:
        got = {}
    return got, float(getattr(reply, "seconds", 0.0) or 0.0)


def rule(chat, model: str, scene: dict, pc_text: str, line: str, in_fight: bool,
         temperature: float = 0.3, host: str = "http://localhost:11434"):
    """(ruling in the key's shape, seconds, a record of each specialist's answer)."""
    facts = "\n".join(f"- {f}" for f in scene["facts"])
    user = (f"THE SCENE: {scene['title']}\n{facts}\n\nTHE PLAYER'S CHARACTER: {pc_text}\n\n"
            f"{'This is a fight.' if in_fight else 'This is not a fight.'}\n\n"
            f"THE PLAYER SAYS: {line}")
    seconds, steps = 0.0, {}
    out = {"verdict": "", "what": "none", "against": "none", "defence": "none",
           "opposed_by": "none", "bonus": 0, "multi": False, "refuse": "none",
           "action": "none"}

    claims, s = _ask(chat, model, CLAIMS_SYSTEM, user, CLAIMS_SCHEMA, temperature, host)
    seconds += s
    steps["claims"] = claims
    if claims.get("claim") == "a_guess_about_someone":
        # A shot in the dark: only the odds are the judge's; the roll that follows is the
        # engine's to choose from the hidden result (Intimidate if true, Bluff if not).
        odds, s = _ask(chat, model, ODDS_SYSTEM, user, ODDS_SCHEMA, temperature, host)
        seconds += s
        steps["odds"] = odds
        out.update(verdict="roll", what="oracle", against=odds.get("odds") or "unlikely")
        return out, seconds, steps
    if claims.get("claim") in REFUSE_FOR and claims.get("holds") == "no":
        out.update(verdict="refuse", refuse=REFUSE_FOR[claims["claim"]])
        return out, seconds, steps

    stakes, s = _ask(chat, model, STAKES_SYSTEM, user, STAKES_SCHEMA, temperature, host)
    seconds += s
    steps["stakes"] = stakes
    if stakes.get("at_stake") == "nothing" or stakes.get("outcome") == "certain":
        out.update(verdict="say_yes")
        return out, seconds, steps

    pick, s = _ask(chat, model, PICK_SYSTEM, user, PICK_SCHEMA, temperature, host)
    seconds += s
    steps["pick"] = pick
    what = J.compose(pick.get("roll_type", ""), pick.get("roll_name", ""))
    out.update(verdict="roll", what=what or "", multi=bool(pick.get("multi")))
    if what == "spell" or not what:
        return out, seconds, steps

    target, s = _ask(chat, model, TARGET_SYSTEM.format(what=what, card=card_for(what)),
                     user, TARGET_SCHEMA, temperature, host)
    seconds += s
    steps["target"] = target
    out.update(against=target.get("against", "none"),
               defence=target.get("defence", "none"),
               opposed_by=J.compose(target.get("opposed_by_type", ""),
                                    target.get("opposed_by_name", "")) or "none",
               action=target.get("action", "none") if in_fight else "none")

    bonus, s = _ask(chat, model, BONUS_SYSTEM, user, BONUS_SCHEMA, temperature, host)
    seconds += s
    steps["bonus"] = bonus
    out["bonus"] = int(bonus.get("bonus") or 0)
    return out, seconds, steps
