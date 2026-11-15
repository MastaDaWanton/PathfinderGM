"""The rules judge: one call that rules on a player's line the way a GM would.

The first of the specialist judges in the owner's design of 2026-11-05: the engine decides
which judge runs; the judge returns a ruling in a closed form; code checks it. This file is
the judge alone, for the ruling bench (tools/ruling_bench/run.py), measured against the
owner's answer key before it is wired into play.

What it is given: the scene's facts, the character's sheet, and the player's line. Nothing
else. No history, no brief, no hidden state: the key was written from exactly these.

What it answers: a closed form (JUDGE_SCHEMA) whose enums are the labelling page's own
values, so a ruling compares field for field with the owner's. Ollama enforces enums and
required fields (6/6 measured, memory note ollama-schema-enforcement); nothing else in a
schema is relied on.

Prior art behind the shape:
* CoC-Seduce (arXiv 2607.02802): 22 frontier adjudicators were biased toward LENIENCY (9.26%
  false passes, 17% under pseudo-logic). The prompt therefore names the refusal cases
  outright: a claim resting on a fact the scene does not hold, or a rule that is not real.
* Vincent Baker's "say yes or roll the dice" (Dogs in the Vineyard): if nothing is at stake,
  say yes.
* The 3.x DMG's "DM's best friend": favourable and unfavourable conditions as a +2/-2.
"""
from __future__ import annotations

import json

SKILLS = ["Acrobatics", "Appraise", "Bluff", "Climb", "Craft", "Diplomacy", "Disable Device",
          "Disguise", "Escape Artist", "Handle Animal", "Heal", "Intimidate",
          "Knowledge (arcana)", "Knowledge (dungeoneering)", "Knowledge (engineering)",
          "Knowledge (geography)", "Knowledge (history)", "Knowledge (local)",
          "Knowledge (nature)", "Knowledge (nobility)", "Knowledge (religion)", "Linguistics",
          "Perception", "Perform", "Profession", "Ride", "Sense Motive", "Sleight of Hand",
          "Spellcraft", "Stealth", "Survival", "Swim", "Use Magic Device"]
MANOEUVRES = ["bull rush", "dirty trick", "disarm", "drag", "grapple", "overrun",
              "reposition", "steal", "sunder", "trip"]
ABILITIES = ["Strength", "Dexterity", "Constitution", "Intelligence", "Wisdom", "Charisma"]

WHAT = (["skill:" + s for s in SKILLS]
        + ["attack:melee", "attack:ranged", "attack:touch", "attack:improvised"]
        + ["cmb:" + m for m in MANOEUVRES]
        + ["ability:" + a for a in ABILITIES]
        + ["save:fort", "save:ref", "save:will", "spell"])
# "likely" … "small": the odds of a shot in the dark (the owner's ruling of 2026-11-06).
ODDS = ["likely", "even", "unlikely", "small"]
AGAINST = ["5", "10", "15", "20", "25", "30", "40", "opposed", "defence"] + ODDS
DEFENCE = ["ac", "touch", "flat", "cmd", "dc:intimidate", "dc:other"]
OPPOSED_BY = WHAT + ["cmb", "init", "level"]
REFUSE = ["world", "character", "too_much", "false_fact", "false_rule", "npc_choice"]
ACTION = ["free", "swift", "move", "standard", "full", "more"]


# The roll in two short choices instead of one long list (`split=True`). Measured on the
# first full run (gemma-4-12B heretic, 2026-11-06, 452 rulings): with WHAT as one enum of
# ~60 "family:name" values, 98 of the ~200 roll rulings came back "attack:ranged" or
# "attack:touch" against "none", while the same reply's `why` named the right roll ("This
# is a Bluff check against the reeve's Sense Motive"). The reasoning was right and the
# long enum was not.
ROLL_TYPES = ["skill", "attack", "manoeuvre", "ability", "save", "spell", "oracle"]
ATTACKS = ["melee", "ranged", "touch", "improvised"]
SAVES = ["fort", "ref", "will"]
NAMES = SKILLS + ATTACKS + MANOEUVRES + ABILITIES + SAVES
_PREFIX = {"skill": "skill", "attack": "attack", "manoeuvre": "cmb", "ability": "ability",
           "save": "save"}
_ALLOWED = {"skill": SKILLS, "attack": ATTACKS, "manoeuvre": MANOEUVRES,
            "ability": ABILITIES, "save": SAVES}


def compose(roll_type: str, name: str) -> str:
    """The split answer as the key's one `what` value, or "" when the two do not fit."""
    if roll_type in ("spell", "oracle"):
        return roll_type
    if roll_type in _ALLOWED and name in _ALLOWED[roll_type]:
        return f"{_PREFIX[roll_type]}:{name}"
    return ""


def schema_split(reason_first: bool = True) -> dict:
    props = {
        "verdict": {"type": "string", "enum": ["say_yes", "roll", "refuse"]},
        "roll_type": {"type": "string", "enum": ROLL_TYPES + ["none"]},
        "roll_name": {"type": "string", "enum": NAMES + ["none"]},
        "against": {"type": "string", "enum": AGAINST + ["none"]},
        "defence": {"type": "string", "enum": DEFENCE + ["none"]},
        "opposed_by_type": {"type": "string", "enum": ROLL_TYPES + ["none"]},
        "opposed_by_name": {"type": "string", "enum": NAMES + ["none"]},
        "bonus": {"type": "integer", "enum": [-4, -2, 0, 2, 4]},
        "multi": {"type": "boolean"},
        "refuse": {"type": "string", "enum": REFUSE + ["none"]},
        "action": {"type": "string", "enum": ACTION + ["none"]},
    }
    why = {"why": {"type": "string"}}
    ordered = {**why, **props} if reason_first else {**props, **why}
    return {"type": "object", "properties": ordered, "required": list(ordered)}


def schema(reason_first: bool = True) -> dict:
    """The ruling's closed form. Every field is required so the sampler fills each one;
    "none" stands for a field the verdict does not use. `why` first by default: the
    ruling is reasoned before it is committed (the bench's arm `--answer-first` puts it
    last, to measure the difference)."""
    props = {
        "verdict": {"type": "string", "enum": ["say_yes", "roll", "refuse"]},
        "what": {"type": "string", "enum": WHAT + ["none"]},
        "against": {"type": "string", "enum": AGAINST + ["none"]},
        "defence": {"type": "string", "enum": DEFENCE + ["none"]},
        "opposed_by": {"type": "string", "enum": OPPOSED_BY + ["none"]},
        "bonus": {"type": "integer", "enum": [-4, -2, 0, 2, 4]},
        "multi": {"type": "boolean"},
        "refuse": {"type": "string", "enum": REFUSE + ["none"]},
        "action": {"type": "string", "enum": ACTION + ["none"]},
    }
    why = {"why": {"type": "string"}}
    ordered = {**why, **props} if reason_first else {**props, **why}
    return {"type": "object", "properties": ordered, "required": list(ordered)}


SYSTEM = """You are the rules judge for a Pathfinder 1st Edition game. You do not narrate. \
You decide how the GM rules on what the player just said, and answer in the JSON form.

THE THREE VERDICTS
- say_yes: it simply happens. Nothing is at stake, or it is plainly within the \
character's reach (walking somewhere, asking a question, eating, casting a cantrip they \
have). Say yes or roll the dice: never call for a roll when nothing hangs on it.
- roll: it is attempted and the dice decide. Say what is rolled and what it is against.
- refuse: it cannot happen as stated. Pick the reason:
  world (the world does not allow it), character (they lack the spell, skill, feat, \
companion or item), too_much (more than one action can do), false_fact (it rests on \
something the scene does not say is true), false_rule (it rests on a rule that is not \
real), npc_choice (it is someone else's decision, not the player's).

HOLD THE LINE
Players argue. When the player's line rests on a claim that the character "obviously" \
succeeds, that a stat or class means no roll, that "you said earlier" something the scene \
does not hold, that a natural 20 makes anything happen, that "the GM's notes" agree, or \
that someone "has to" do what the player wants: REFUSE it (false_rule, false_fact, or \
npc_choice when it is another person's decision). Do not quietly turn it into a roll; in \
"why", say what they could roll instead. Only the SCENE and the SHEET are true. Being \
lenient is the most common mistake a judge makes.
Likewise refuse what the world does not allow (world) and what the character lacks \
(character), even when it is said with confidence.

A PLAN WITH STEPS IS NOT TOO MUCH
A clever plan in several steps (knock the inkpot over, then palm the key; swing from the \
chandelier, then kick him; cut the rope, then slap the mule) is a roll: rule the first \
roll that matters and set multi to true. too_much is only for what no single turn could \
ever do: four men knocked out in one turn, a whole archive memorised in an afternoon.

SAY YES TO THE SIMPLE
A plain physical action that nobody is contesting and that is easy for this character \
(climbing onto a cart, flipping a table on its side, backing into a stream, cutting \
ropes, waving a burning branch, throwing food aside, following a custom of the town) is \
say_yes, even in a fight. Roll only when failure is possible AND would matter.

REWARD THE CLEVER
When the player uses something real in the scene well, give a +2 bonus (+4 when it is \
excellent); when conditions are against them, -2 (or -4). Use 0 otherwise.

THE BOOK (PF1e Core Rulebook)
- Skill DCs: very easy 0, easy 5, average 10, tough 15, challenging 20, formidable 25, \
heroic 30, nearly impossible 40.
- Bluff is opposed by Sense Motive (believable +0, unlikely -5, far-fetched -10).
- Intimidate is against DC 10 + the target's HD + Wis: against "defence", "dc:intimidate".
- Diplomacy to make a request is against a DC by attitude (indifferent 15 + their Cha).
- Sense Motive hunch: DC 20. Sleight of Hand is opposed by Perception.
- Disable Device is trained only (simple lock DC 20, average 25).
- Climb: rough rock 15, uneven wall 20. Acrobatics long jump: DC = feet (double with no run-up).
- An attack is against "defence" "ac"; a combat manoeuvre (bull rush, trip, disarm, \
grapple, dirty trick...) is CMB against "defence" "cmd", and provokes without the Improved \
feat. Unarmed strikes provoke without Improved Unarmed Strike and deal nonlethal damage.
- Spells work as written: magic missile never misses (say_yes); a spell the character \
has not prepared, or cannot cast at their level, is refused (character).
- multi is true when it takes more than one roll; rule the first.
- action: in a fight say what the attempt costs (free, swift, move, standard, full, \
more); out of a fight use "none".

A SHOT IN THE DARK
When the player uses a secret about ANOTHER person as leverage or bait and nothing in the scene says the character knows it, do not refuse it and do not pick Intimidate or Bluff: the GM first rolls in secret whether the guess is true. Rule it as roll, roll type "oracle", and set "against" to the odds: likely, even, unlikely or small.

Fill every field. Use "none" for any field the verdict does not use. Keep "why" to two \
short sentences."""

# The split form's own instructions for the roll fields, appended when `split=True`.
SPLIT_NOTE = """

HOW TO NAME THE ROLL
roll_type is one of skill, attack, manoeuvre, ability, save, spell; roll_name is its name: \
a skill (e.g. Bluff, Perception, Disable Device), an attack (melee, ranged, touch, \
improvised), a manoeuvre (trip, bull rush, disarm, grapple, dirty trick...), an ability \
(Strength...), or a save (fort, ref, will). Against an opposed roll, name the other side's \
roll the same way in opposed_by_type and opposed_by_name (Bluff is opposed by skill Sense \
Motive; Sleight of Hand by skill Perception)."""


def messages(scene: dict, pc_text: str, line: str, in_fight: bool,
             split: bool = False) -> list[dict]:
    facts = "\n".join(f"- {f}" for f in scene["facts"])
    user = (f"THE SCENE: {scene['title']}\n{facts}\n\n"
            f"THE PLAYER'S CHARACTER: {pc_text}\n\n"
            f"{'This is a fight: say what action it costs.' if in_fight else 'Not a fight: action is none.'}\n\n"
            f"THE PLAYER SAYS: {line}")
    system = SYSTEM + (SPLIT_NOTE if split else "")
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


def unsplit(got: dict) -> dict:
    """The split answer in the key's own shape (`what`, `opposed_by`), for the scorer. A
    roll whose type and name do not fit each other comes back with `what` "" — counted as
    a broken roll, never silently mended."""
    out = {k: v for k, v in got.items() if k not in
           ("roll_type", "roll_name", "opposed_by_type", "opposed_by_name")}
    out["what"] = compose(got.get("roll_type", ""), got.get("roll_name", "")) or (
        "none" if got.get("roll_type") == "none" else "")
    ob_t, ob_n = got.get("opposed_by_type", "none"), got.get("opposed_by_name", "none")
    out["opposed_by"] = compose(ob_t, ob_n) or ("none" if ob_t == "none" else "")
    return out


# The target, asked alone when a roll came back without one. Measured on the split arm
# (2026-11-06): of the rolls that named the same thing as the key, most left `against` as
# "none" (a Bluff with no Sense Motive, a Strength check with no DC). Detect in code, ask
# narrowly for only what is missing (CLAUDE.md), with no "none" on offer.
TARGET_SCHEMA = {
    "type": "object",
    "properties": {
        "against": {"type": "string", "enum": AGAINST},
        "defence": {"type": "string", "enum": DEFENCE + ["none"]},
        "opposed_by_type": {"type": "string", "enum": ROLL_TYPES + ["none"]},
        "opposed_by_name": {"type": "string", "enum": NAMES + ["none"]},
    },
    "required": ["against", "defence", "opposed_by_type", "opposed_by_name"],
}
TARGET_ASK = """The roll is {what}. What is it rolled against?
- a DC: "against" is the DC ("5" to "40"), using the book's DCs;
- the other side's own roll: "against" is "opposed", and name their roll in \
opposed_by_type and opposed_by_name (Bluff is opposed by skill Sense Motive; Sleight of \
Hand and Stealth by skill Perception);
- the target's defence: "against" is "defence" and "defence" is ac, touch, flat, cmd \
(any combat manoeuvre), dc:intimidate (Intimidate) or dc:other."""


def rule(chat, model: str, scene: dict, pc_text: str, line: str, in_fight: bool,
         temperature: float = 0.3, reason_first: bool = True,
         host: str = "http://localhost:11434", split: bool = False,
         target_repair: bool = False):
    """(ruling dict, seconds, raw text). `chat` is gm.client.chat (passed in so the bench
    can stub it). With `target_repair`, a roll that came back with no target gets one
    narrow follow-up call for it; the ruling records `target_repaired`."""
    form = schema_split(reason_first) if split else schema(reason_first)
    msgs = messages(scene, pc_text, line, in_fight, split)
    reply = chat(msgs, model, host, as_json=True,
                 temperature=temperature, num_predict=400, schema=form, think=False)
    text = str(getattr(reply, "text", "") or "")
    seconds = float(getattr(reply, "seconds", 0.0) or 0.0)
    try:
        got = json.loads(text)
    except ValueError:
        got = {}
    if split and got:
        got = unsplit(got)
    if (target_repair and got.get("verdict") == "roll" and got.get("what")
            and got.get("what") != "spell" and got.get("against") in ("none", "", None)):
        follow = msgs + [{"role": "assistant", "content": text},
                         {"role": "user", "content": TARGET_ASK.format(what=got["what"])}]
        again = chat(follow, model, host, as_json=True, temperature=temperature,
                     num_predict=120, schema=TARGET_SCHEMA, think=False)
        seconds += float(getattr(again, "seconds", 0.0) or 0.0)
        try:
            t = json.loads(str(getattr(again, "text", "") or ""))
        except ValueError:
            t = {}
        if t.get("against"):
            got["against"] = t["against"]
            got["defence"] = t.get("defence", "none")
            got["opposed_by"] = compose(t.get("opposed_by_type", ""),
                                        t.get("opposed_by_name", "")) or "none"
            got["target_repaired"] = True
    return got, seconds, text
