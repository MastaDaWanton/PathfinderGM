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
    return ops


def spell_named(scene, words) -> object | None:
    """The spell the player's caster can reach whose name the words hold, or None — the
    longest name wins, so "cure light wounds" is not "cure". Asked of the book, the
    prepared list and the class's own list, as `judgement.inject_cast` asks."""
    from rules import casting, spells as spells_mod

    pc = scene.pc() if scene is not None and hasattr(scene, "pc") else None
    said = " ".join(str(words or "").lower().split())
    if pc is None or not said or not casting.is_caster(pc):
        return None
    ids = [sp.id for lvl in casting.known_spells(
        pc, up_to=casting.highest_spell_level(pc)).values() for sp in lvl]
    ids += [s for s in (getattr(pc, "prepared", {}) or {}) if s not in ids]
    best, found = "", None
    for sid in ids:
        try:
            sp = spells_mod.get(sid)
        except KeyError:
            continue
        name = " ".join(str(sp.name).lower().split())
        if name and name in said and len(name) > len(best):
            best, found = name, sp
    return found


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
    "say": {"talk", "insult"}, "provoke": {"insult"}, "give": {"give"}, "sell": {"sell"},
    "rest": {"rest"}, "advance_time": {"wait", "rest"}, "call_on": {"call_on"},
    "break_in": {"break_in"}, "forage": {"gather"}, "prospect": {"gather"},
    "loot": {"take", "steal"}, "cast": {"cast"},
    "use_item": {"consume", "use"}, "drink": {"consume"}, "eat": {"consume"},
}


def supported(ops: list[str], frame: dict | None) -> tuple[list[str], list[str]]:
    """(the detectors' ops the reading supports, the ones it does not). Measured live
    2026-09-27: a detector required `give` for "I buy a dragon's egg", which the reading
    read — rightly — as a purchase. On the labelled set the reading's acts score F1 0.91
    against the detectors' 0.47, so where the two disagree the reading decides, and the
    overruled op is logged."""
    acts = {a.get("act") for a in (frame or {}).get("actions") or []}
    kept, dropped = [], []
    for op in ops:
        need = _OP_NEEDS.get(op)
        (kept if need is None or acts & need else dropped).append(op)
    return kept, dropped


# The acts under which the player can come away holding something. One set for both
# doors that make a give to the player: the plan's (`drop_unread_gifts`) and the
# detector's (`judgement.inject_goods`).
GETTING_ACTS = frozenset({"give", "take", "buy", "steal", "gather", "sell"})


def gets_nothing(frame: dict | None) -> bool:
    """Whether a reading exists and none of its acts can leave the player holding
    anything. False when there is no reading to judge by — the regex decides then."""
    if not frame or frame.get("error"):
        return False
    return not ({a.get("act") for a in frame.get("actions") or []} & GETTING_ACTS)


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
        rows.append(f"{n}. {a['act']}" + (f" — {slots}" if slots else ""))
    out = ""
    if rows:
        out = ("THE PLAYER'S WORDS, READ (fact, in the order they are done; the plan "
               "carries each): " + " ".join(rows))
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
