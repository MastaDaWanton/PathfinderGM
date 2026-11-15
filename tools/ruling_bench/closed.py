"""The ruling judge as closed questions plus the GM's own precedents (bench round 2026-11-14).

Why this shape, from what was measured before (docs/ruling-judge.md has the record):
* the one-call judge (judge.py) let 77% of the key's refusals through on the held-out set;
* the specialists (specialists.py) held refusals but said yes to 9 of 18 rolls, because their
  "stakes" question was answered "nothing at stake" for watching, listening and searching;
* both were tuned by instruction on set1, and set1's 76% fell to 57-60% on set2.

So the model is asked only closed questions it can answer from the line (enums, required,
reason first: arXiv 2610.12056 measured answer-first schemas dropping hardest in small
models), and CODE turns the answers into the verdict (CheckEval arXiv 2403.18771, TICK
arXiv 2410.03608: fixed human-written checklists steady a judge). The GM's own rulings on
the most similar lines from OTHER scenes are shown as precedents (kNN demonstrations beat
random ones, Liu et al. arXiv 2101.06804), balanced by verdict so the prompt carries no
majority label (Zhao et al. arXiv 2102.09690 measured majority and recency label bias).
CLAUDE.md: demonstration volume beats instruction volume.
"""
from __future__ import annotations

import json
import math
import re
from collections import Counter

YN = {"type": "string", "enum": ["yes", "no"]}

QUESTIONS = {
    "missing_ability": "Does the player use a spell, power, feat, companion or item that "
                       "the CHARACTER sheet does not give them?",
    "beyond_world": "Is it something no one could do in this world, however it is tried "
                    "(an absurd feat of strength, magic nobody here has)?",
    "rule_claim": "Does the player say a rule, a stat, a class, a custom or a law makes it "
                  "succeed automatically, skip the roll, or oblige someone?",
    "decides_for_other": "Does the line DECLARE what another person or creature does, "
                         "feels, notices or agrees to, as if it had already happened, "
                         "instead of trying something and letting them react?",
    "unknown_fact": "Does success rest on something stated as true that the SCENE does "
                    "not say? 'false': a fact about the scene, the past or a person that "
                    "the scene does not support. 'secret': a secret about another person "
                    "used as leverage or bait that the character has no way to know. "
                    "'no': nothing like that.",
    "too_much": "Does the line cram several separate deeds, each needing its own roll, "
                "into one moment (knock out all four, cross, swing down and escape before "
                "anyone moves)?",
    "seeks_hidden": "Is the player trying to notice, find, read, recall or work out "
                    "something the scene does not already tell them?",
    "contested": "Could someone resist or refuse it, or could it fail in a way that "
                 "matters (a fall, a fight, a lie, a request, a theft)?",
    "trivial": "Is it plainly easy for this character and nobody stands against it "
               "(walking, asking, eating, a cantrip they have, a plain move)?",
}


# v2 (2026-11-14), from v1's per-question firing on set1 (12B heretic, 152 lines):
# * missing_ability fired on 5 of the key's 9 "character" refusals (cast knock, whistle the
#   gulls in, make them forget): the model was asked to compare the line with the sheet.
#   The sheet is the engine's, so the comparison moves to CODE: the model only names which
#   of the character's own powers the line uses, or "another" (power_used, below).
# * decides_for_other fired on 11 lines the key lets happen, nearly all a hoped-for result
#   of the character's own act ("so it flips up and trips him", "so she rushes to save
#   it", "drive him back"). The question now says that outright, with examples.
# * contested/trivial: say_yes lines answered contested "yes" 14 of 44 times and roll lines
#   "no" 13 of 57; one three-way question about how sure the outcome is replaces both.
QUESTIONS_V2 = {
    "power_used": "Which spell, power or special ability of the character's does the line "
                  "use? One from the list, 'none' if it uses no magic or special power, or "
                  "'another' if it uses magic, a supernatural power, mind-reading, talking "
                  "to animals or the like that is NOT on the list.",
    "beyond_world": QUESTIONS["beyond_world"],
    "rule_claim": QUESTIONS["rule_claim"],
    "decides_for_other": "Does the player DECLARE another person's or creature's decision "
                         "or feelings as settled (\"she signs it over\", \"they make me "
                         "chief\", \"the wolves accept me\", \"he backs down\") with nothing "
                         "the character does that the other could resist? NOT this: the "
                         "hoped-for result of the character's own act (\"I tip the bucket so "
                         "he slips\", \"I knock the ink over so she rushes to save it\", \"I "
                         "shove him into the rack\", \"I stare them down until they back "
                         "off\") — the dice and the people decide that.",
    "unknown_fact": QUESTIONS["unknown_fact"],
    "too_much": QUESTIONS["too_much"],
    "seeks_hidden": QUESTIONS["seeks_hidden"],
    "outcome": "If the character simply does it, how sure is the result? 'certain': plainly "
               "easy for them and nobody resists (walking, asking, offering, buying, a "
               "plain move, a cantrip they have). 'could_fail': someone could resist or "
               "refuse, or it is hard enough that they could fail in a way that matters.",
}


# v3 (2026-11-15), from v2's first 50 set1 lines: 6 of its 12 misses were needless rolls on
# an ask or an offer ("tell him I'm looking for sellsword work", "buy a round and ask what
# jobs are going", "shout that I'll pay ten silver") answered could_fail because "someone
# could refuse". The key says yes to asking and offering: the person simply answers. Only
# changing a mind, deceiving or threatening is a roll.
QUESTIONS_V3 = {**QUESTIONS_V2, "outcome": (
    "If the character simply does it, how sure is the result? 'certain': plainly easy for "
    "them and nobody resists: walking, a plain move, eating, a cantrip they have, and also "
    "ASKING, OFFERING, TELLING, BUYING or CHALLENGING, because the other person simply "
    "answers in their own way. 'could_fail': it tries to change someone's mind against "
    "their will, deceive or threaten them, take or hide something from someone, or it is "
    "physically hard enough that they could fail in a way that matters.")}
# v4 (2026-11-15). v3's instruction did not move the asks: on set1 the same lines (s1-04,
# s1-15, s8-12, s10-02, s11-02) still came back could_fail, needless rolls 38.6% before and
# after. CLAUDE.md's lesson again: instructing the model to judge differently fails. So the
# model is asked a different, easier closed question — WHAT KIND of act it is — and the
# code decides which kinds roll. The kinds are the book's: Diplomacy/Bluff/Intimidate are
# rolls, a plain request is not (CRB "Using skills": no check when there is no chance of
# failure or nothing at stake).
ACTS = ["ask_or_offer", "persuade_deceive_or_threaten", "notice_or_learn",
        "attack_or_manoeuvre", "steal_or_hide", "physical_feat", "simple_act"]
QUESTIONS_V4 = {**QUESTIONS_V3, "act": (
    "What kind of act is it? ask_or_offer: a question, an offer, a request, a challenge, "
    "paying or buying, an order to a friend. persuade_deceive_or_threaten: changing a "
    "mind against its will, a lie, a bribe, a threat, a stare-down. notice_or_learn: "
    "looking, listening, searching, studying, recalling. attack_or_manoeuvre: a blow, a "
    "shot, a trip, a shove, a grab. steal_or_hide: palming, swapping, sneaking, hiding. "
    "physical_feat: climbing, jumping, lifting, breaking, balancing, swimming. "
    "simple_act: walking, sitting, eating, picking up, cutting a rope, knocking something "
    "over, a plain move.")}
VERSIONS = {"v1": QUESTIONS, "v2": QUESTIONS_V2, "v3": QUESTIONS_V3, "v4": QUESTIONS_V4}


def powers_of(pc_text: str) -> list[str]:
    """The spells and cantrips the sheet names, read from the bench's fixed sheet text.
    In play the engine has the real list; this is only the bench's copy of it."""
    m = re.findall(r"(?:Prepared|Cantrips):([^.]+)\.", pc_text)
    names = [n.split("(")[0].strip() for part in m for n in part.split(",")]
    return [n for n in names if n]


def checklist_schema(version: str = "v1", powers: list[str] | None = None) -> dict:
    qs = VERSIONS[version]
    props = {"why": {"type": "string"}}
    for q in qs:
        if q == "unknown_fact":
            props[q] = {"type": "string", "enum": ["no", "false", "secret"]}
        elif q == "power_used":
            props[q] = {"type": "string", "enum": ["none"] + (powers or []) + ["another"]}
        elif q == "act":
            props[q] = {"type": "string", "enum": ACTS}
        elif q == "outcome":
            props[q] = {"type": "string", "enum": ["certain", "could_fail"]}
        else:
            props[q] = YN
    return {"type": "object", "properties": props, "required": list(props)}


def checklist_system(version: str = "v1", powers: list[str] | None = None) -> str:
    qs = VERSIONS[version]
    head = CHECKLIST_SYSTEM
    if version != "v1":
        head += f"\nTHE CHARACTER'S POWERS: {', '.join(powers) if powers else 'none'}.\n"
    return head + "\n".join(f"- {k}: {v}" for k, v in qs.items())


CHECKLIST_SYSTEM = """You help a Pathfinder 1st Edition GM rule on a player's line. You do \
not decide the ruling: you answer a few yes/no questions about the line, and the GM's \
rules turn your answers into the ruling. Only the SCENE and the CHARACTER sheet are true; \
anything else the player says is just what they say.

First write "why": one or two short sentences on what the player is trying to do and what \
it rests on. Then answer each question:
"""

DIRECT_SCHEMA = {"type": "object",
                 "properties": {"why": {"type": "string"},
                                "verdict": {"type": "string",
                                            "enum": ["say_yes", "roll", "refuse"]},
                                "refuse": {"type": "string",
                                           "enum": ["none", "world", "character", "too_much",
                                                    "false_fact", "false_rule", "npc_choice"]}},
                 "required": ["why", "verdict", "refuse"]}

DIRECT_SYSTEM = """You are a Pathfinder 1st Edition GM ruling on a player's line. Rule the \
way THIS GM rules: the past rulings shown are theirs, and they are the standard.
- say_yes: it simply happens; no roll.
- roll: it is attempted and the dice decide.
- refuse, with the reason: world (no one could), character (the sheet lacks the spell, \
skill, feat or item), too_much (several deeds crammed into one moment), false_fact (it rests \
on something the scene does not say), false_rule (it rests on a rule that is not real), \
npc_choice (it declares someone else's decision).
A secret about another person used as leverage, which the character cannot know, is a roll \
(the GM rolls the odds in secret), not a refusal.
Only the SCENE and the CHARACTER sheet are true. Write "why" first, in one or two sentences."""


def combine(a: dict) -> dict:
    """The checklist's answers as a verdict. The refusals are checked first and in a fixed
    order, so no later answer can talk one away (the leniency CoC-Seduce measured)."""
    yes = lambda q: a.get(q) == "yes"  # noqa: E731
    if a.get("power_used") == "another":
        return {"verdict": "refuse", "refuse": "character"}
    for q, reason in (("missing_ability", "character"), ("beyond_world", "world"),
                      ("rule_claim", "false_rule"), ("decides_for_other", "npc_choice")):
        if yes(q):
            return {"verdict": "refuse", "refuse": reason}
    if a.get("unknown_fact") == "false":
        return {"verdict": "refuse", "refuse": "false_fact"}
    if a.get("unknown_fact") == "secret":
        return {"verdict": "roll", "what": "oracle"}
    if yes("too_much"):
        return {"verdict": "refuse", "refuse": "too_much"}
    if a.get("power_used") not in (None, "none"):
        # A spell on the sheet is cast, and its own rules (attack, save) do the rolling; the
        # key says yes to casting (magic missile, grease, detect magic, light). On v2's
        # stored answers this rule alone moved set1 from 108 to 110 of 152.
        return {"verdict": "say_yes"}
    act = a.get("act")
    if act in ("persuade_deceive_or_threaten", "notice_or_learn", "attack_or_manoeuvre",
               "steal_or_hide"):
        return {"verdict": "roll"}
    if act in ("ask_or_offer", "simple_act"):
        return {"verdict": "say_yes"}
    if act == "physical_feat":
        return {"verdict": "roll" if a.get("outcome") == "could_fail" else "say_yes"}
    if yes("seeks_hidden"):
        return {"verdict": "roll"}
    if a.get("outcome") == "could_fail" or (yes("contested") and not yes("trivial")):
        return {"verdict": "roll"}
    return {"verdict": "say_yes"}


# --- precedents ---------------------------------------------------------------------------

_WORD = re.compile(r"[a-z']+")
_STOP = set("i a an the to and of my me her his him she he they them their it is in on at "
            "so for with that this as be by from into up out if or but it's i'm".split())


def _bag(text: str) -> Counter:
    return Counter(w for w in _WORD.findall(text.lower()) if w not in _STOP)


class Precedents:
    """Tf-idf cosine over the lines' words: the nearest rulings, balanced by verdict.

    shortcut: lexical similarity only (no embedding model is installed locally); upgrade to
    the reader's act enum or an embedding if lexical neighbours prove off-topic."""

    def __init__(self, pool: list[dict]):
        self.pool = pool
        self.bags = [_bag(l["text"]) for l in pool]
        df = Counter(w for b in self.bags for w in b)
        self.idf = {w: math.log((1 + len(pool)) / (1 + n)) + 1 for w, n in df.items()}

    def _vec(self, bag: Counter) -> dict:
        v = {w: c * self.idf.get(w, 1.0) for w, c in bag.items()}
        norm = math.sqrt(sum(x * x for x in v.values())) or 1.0
        return {w: x / norm for w, x in v.items()}

    def nearest(self, text: str, exclude_scene: str, per_verdict: int = 2) -> list[dict]:
        q = self._vec(_bag(text))
        scored = []
        for l, b in zip(self.pool, self.bags):
            if l["scene"] == exclude_scene:
                continue
            v = self._vec(b)
            scored.append((sum(q.get(w, 0) * x for w, x in v.items()), l))
        scored.sort(key=lambda t: -t[0])
        picked = []
        for verdict in ("say_yes", "roll", "refuse"):
            picked += [t for t in scored if t[1]["verdict"] == verdict][:per_verdict]
        picked.sort(key=lambda t: t[0])  # most similar last
        return [l for _, l in picked]


def ruling_label(l: dict) -> str:
    if l["verdict"] == "refuse":
        return f"refuse ({l['refuse']})"
    if l["verdict"] == "roll":
        what = (l.get("roll") or {}).get("what") or ""
        return "roll (the GM's secret odds roll)" if what == "oracle" else f"roll ({what})"
    return "say_yes"


def precedent_block(prec: list[dict], scenes: dict) -> str:
    rows = []
    for l in prec:
        note = (l.get("note") or "").strip()
        rows.append(f"- In \"{scenes[l['scene']]['title']}\" the player said: \"{l['text']}\"\n"
                    f"  The GM ruled: {ruling_label(l)}."
                    + (f" The GM's note: {note[:260]}" if note else ""))
    return "PAST RULINGS BY THIS GM, in other scenes:\n" + "\n".join(rows)


def user_text(scene: dict, pc_text: str, line: str, prec_block: str = "") -> str:
    facts = "\n".join(f"- {f}" for f in scene["facts"])
    return ((prec_block + "\n\n" if prec_block else "")
            + f"THE SCENE: {scene['title']}\n{facts}\n\nTHE CHARACTER: {pc_text}\n\n"
            + ("This is a fight.\n\n" if scene.get("fight") else "")
            + f"THE PLAYER SAYS: {line}")


def ask(chat, model, system, user, schema, temperature, host="http://localhost:11434"):
    reply = chat([{"role": "system", "content": system}, {"role": "user", "content": user}],
                 model, host, as_json=True, temperature=temperature, num_predict=400,
                 schema=schema, think=False)
    try:
        got = json.loads(str(getattr(reply, "text", "") or ""))
    except ValueError:
        got = {}
    return got, float(getattr(reply, "seconds", 0.0) or 0.0)


def rule(chat, model, scene, pc_text, line, mode, prec_block="", temperature=0.0,
         version="v1"):
    """(ruling, model seconds, the model's answers). mode: 'checklist' or 'direct'."""
    user = user_text(scene, pc_text, line, prec_block)
    if mode == "direct":
        got, secs = ask(chat, model, DIRECT_SYSTEM, user, DIRECT_SCHEMA, temperature)
        out = {"verdict": got.get("verdict", ""), "refuse": got.get("refuse")}
        return out, secs, got
    powers = powers_of(pc_text)
    got, secs = ask(chat, model, checklist_system(version, powers), user,
                    checklist_schema(version, powers), temperature)
    return (combine(got) if got else {"verdict": ""}), secs, got


if __name__ == "__main__":
    # Self-check of the combiner: refusals win over everything after them.
    assert combine({"rule_claim": "yes", "seeks_hidden": "yes"})["refuse"] == "false_rule"
    assert combine({"unknown_fact": "secret"})["what"] == "oracle"
    assert combine({"contested": "yes", "trivial": "yes"})["verdict"] == "say_yes"
    assert combine({"seeks_hidden": "yes", "trivial": "yes"})["verdict"] == "roll"
    assert combine({"power_used": "another", "outcome": "certain"})["refuse"] == "character"
    assert combine({"power_used": "light", "outcome": "certain"})["verdict"] == "say_yes"
    assert combine({"act": "ask_or_offer", "outcome": "could_fail"})["verdict"] == "say_yes"
    assert combine({"act": "ask_or_offer", "rule_claim": "yes"})["verdict"] == "refuse"
    assert combine({"act": "physical_feat", "outcome": "could_fail"})["verdict"] == "roll"
    sheet = "Prepared: magic missile, grease (one each). Cantrips: detect magic, light."
    assert powers_of(sheet) == ["magic missile", "grease", "detect magic", "light"]
    print("ok")
