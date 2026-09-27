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

ACTS = (
    "go", "journey", "leave", "look", "search", "seek", "talk", "insult", "buy", "sell",
    "give", "take", "steal", "attack", "cast", "use", "consume", "wait", "rest",
    "call_on", "break_in", "stealth", "athletics", "gather", "follow", "claim", "other",
)
SLOTS = ("target", "object", "place", "time", "says")

# The slots each act can have: TADS 3's verb templates, where a verb names the slots it
# takes and nothing else (tads.org, "t3verb"). Measured 2026-09-27: with every slot
# required, the model filled all five on most lines and copied one phrase into several
# ("the ore he uses" as object AND place), slot precision 0.33. A slot the act cannot
# have is not the act's, and is dropped in code — never asked of the model twice.
ACT_SLOTS: dict[str, tuple[str, ...]] = {
    "go": ("place", "time"), "journey": ("place",), "leave": ("place",),
    "look": ("object", "target", "place", "time"), "search": ("object", "place"),
    "seek": ("target", "place"), "talk": ("target", "says"), "insult": ("target", "says"),
    "buy": ("object", "target", "place"), "sell": ("object", "target"),
    "give": ("target", "object", "place"), "take": ("object", "target"),
    "steal": ("object", "target"), "attack": ("target", "object", "place", "time"),
    "cast": ("object", "target"), "use": ("object", "target"), "consume": ("object",),
    "wait": ("place", "time", "target"), "rest": ("place", "time"),
    "call_on": ("target", "place"), "break_in": ("target", "object", "place"),
    "stealth": ("target", "place"), "athletics": ("place",), "gather": ("object", "time"),
    "follow": ("target", "object", "time"), "claim": (), "other": ("target", "object", "place"),
}

_WHAT_EACH_IS = """\
go        walk somewhere within reach (a place in town, into the trees, back to the gate);
          walking OUT INTO somewhere named is go, not leave
journey   take the road or a ship to another town
leave     walk out of where you are, with nowhere named
look      look, watch, listen, read, examine
search    look for a THING or a PLACE (water, a way in, somewhere to sleep, tracks)
seek      look for, ask around for, wave down, head for or turn to a PERSON
talk      speak to, ask, tell, greet, thank, persuade, order, haggle with somebody
insult    mock, taunt, call names, spit at, pick a fight with words — and telling
          anybody something meant to shame somebody ("I tell the room he is a coward")
buy       buy, order, pay for goods
sell      sell
give      hand over, pay, buy somebody a drink, drop something somewhere
take      pick up, loot, take
steal     pick a pocket, steal, filch
attack    hit, punch, stab, shoot, finish somebody
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
other     anything else"""

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
         {"span": "ask about barrels", "says": "about barrels", "act": "talk"}]}),
    ("I climb the bell tower to look over the rooftops.",
     {"question": False, "claims": [], "actions": [
         {"span": "climb the bell tower", "place": "the bell tower", "act": "athletics"},
         {"span": "look over the rooftops", "object": "the rooftops", "act": "look"}]}),
    ("I sit on the bench for an hour.",
     {"question": False, "claims": [], "actions": [
         {"span": "sit on the bench for an hour", "place": "the bench", "time": "for an hour",
          "act": "wait"}]}),
    ("I buy the old soldier a pint.",
     {"question": False, "claims": [], "actions": [
         {"span": "buy the old soldier a pint", "target": "the old soldier",
          "object": "a pint", "act": "give"}]}),
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
                                   **{s: slot for s in SLOTS},
                                   "act": {"type": "string", "enum": list(ACTS)}},
                    # Every slot required (null allowed). Measured 2026-09-27 on the
                    # labelled set: with the slots optional, the constrained sampler
                    # wrote `span` and `act` and nothing else on 220 of 220 lines —
                    # slot recall 0.0 — because an optional property is one the grammar
                    # lets it skip.
                    "required": ["span", *SLOTS, "act"],
                },
            },
            "claims": {"type": "array", "items": {"type": "string"}, "maxItems": 3},
        },
        "required": ["question", "actions", "claims"],
    }


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
        out.append({"role": "assistant", "content": json.dumps(frame)})
    out.append({"role": "user", "content": sentence})
    return out


_TIME_WORD = re.compile(
    r"\b(?:until|till|for|while|dawn|dusk|noon|midday|midnight|morning|evening|night|"
    r"tonight|tomorrow|hours?|minutes?|days?|weeks?|months?|years?|dark|light|sunset|"
    r"sunrise|daybreak|nightfall|moment|bell|o'clock|am|pm)\b", re.I)


# A slot that is nothing but a time: "a while", "for an hour", "until he stops moving".
_A_TIME = re.compile(r"^(?:until|till|for|all|a|the)\s+(?:while\b|night\b|day\b|hour|moment|morning|evening)|^(?:until|till)\b|^for\s+(?:a|an|the|\d+|one|two|three|some|several)\b", re.I)


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
        used: set[str] = set()
        for s in ACT_SLOTS.get(a["act"], SLOTS):
            v = a.get(s)
            if v in (None, ""):
                continue
            v = str(v).strip()
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
        actions.append(kept)
    claims = [c for c in (frame.get("claims") or []) if _within(c, sentence)]
    dropped += [f"claim={c!r}" for c in (frame.get("claims") or []) if not _within(c, sentence)]
    return ({"question": bool(frame.get("question")), "actions": actions,
             "claims": claims}, dropped)


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
                        api_key=api_key or cfg.get("api_key", ""), schema=schema())
    try:
        raw = reply.json()
    except Exception:
        raw = {}
    frame, dropped = ground(raw if isinstance(raw, dict) else {}, sentence)
    frame.update(dropped=dropped, seconds=round(time.monotonic() - started, 2),
                 raw=reply.text)
    return frame
