"""A companion confides — when, about what, and whether what they said may stand.

The owner's ruling, 2026-10-01: "Their wants should appear naturally locked behind their
attitude toward you. but they shouldnt just blurt out personal feelings without some kind
of warm up. like telling there is something they wanted to get off their chest or if you
come across a thing that makes sense to remind them of a thing they can share."

Before this, a companion's wants rode one ordinary remark in three (the manner lane's
shortcut in `views._companions_on_the_page`): no gate, no warm-up, the want told cold in
the middle of an opinion about the weather. Gone. A companion's own life now reaches the
page only through the two doors below, every decision of which is made HERE, in code, from
what the engine holds (CLAUDE.md: detect mechanically; never ask a model whether now is a
good moment). The words are the model's (`GMAgent.companion_confide`), checked here.

**The gate** is `rules.confiding.gate`: below friendly nothing personal ever; friendly, a
hint at most — that there is something, never what; helpful or better (or claimed and
devoted), the thing itself. The track it writes is `rules.confiding`.

**Door one, the lead-in** (BG3's "they want to talk", Mass Effect's "I need your help"):
in a quiet moment — no fight, no roll waiting, nobody but companions being talked to, no
death or deal this beat, not the beat they arrived somewhere — and only after
`CONFIDE_EVERY` player turns since anybody last confided and since this one started
travelling with the player, they say there is something they have wanted to get off their
chest. Never what. The share comes on a LATER beat: the player turns to them and asks
(`invited`), or, if the player does not brush it off ("not now", "later" — `BRUSH_OFF`),
the next quiet moment `CONFIDE_GAP` turns on. A brush-off holds it `POSTPONE` turns.

**Door two, the reminder** (Disco Elysium's Kim, who opens up "in specific situations"
rather than by the player "cleaning out his tree"): something in the world that plausibly
touches their want, goal or hobby appears this beat — the place just walked into, somebody
here by their trade or their years (a child, an elder), the turn's own tells, the beat's
own words — matched against the row's `reminded_by` words in content/people/life.json. New
this beat only (`_fresh`): the tavern they have stood in for ten beats is not a reminder
on the eleventh. Then they share it, bridged from the thing ("…that forge. My father kept
one like it."), when the gate allows; at friendly the bridge is a hint only.

**What may stand** (`refusal`): the lead-in and the hint say nothing of the content (they
are not told it — what a model is not told it cannot leak, rules/population.py); the share
names the want's own key words (`key_stems`, a paraphrase allowed, a different want not),
no number, no name the world does not know, no advice; a bridge names what reminded them.
One targeted repair, else nothing is said this beat and the share stays owed.

Prior art, searched 2026-10-01 (sources in tests/test_companions_confide.py): approval
thresholds as hard gates (BG3: "below the required number, the dialogue option does not
appear"); one camp event per long rest, the rest queued (BG3); a fixed sequence of
conversations per companion with the loyalty talk blocking the rest until done (Mass
Effect 2); supports earned C then B then A, never skipped (Fire Emblem); and what was
abandoned — DA:O's unlimited gifts that bought approval outright, the "romance vending
machine" critique, and Avowed dropping approval altogether so players would not feel they
"had to choose the 'right' options". So: no new meter here, nothing the player can buy
or farm — the existing attitude track gates it, and the companion is the one who brings
it up.
"""
from __future__ import annotations

import re

from rules import confiding

from . import companions

# Player turns between one confiding moment (anybody's) and the next lead-in, and the
# least a companion must have travelled with the player before their first. Rarer than an
# ordinary remark (`companions.INTERJECT_EVERY`, 5): The Last of Us put Ellie's gifts on
# "a really long timer" once a gift every minute devalued them (Dyckhoff, Game AI Pro 2).
CONFIDE_EVERY = 8
# Turns after a lead-in before the share may come unasked — a later beat, never the next
# sentence (the ruling's "warm up").
CONFIDE_GAP = 2
# Turns a brush-off holds the share off.
POSTPONE = 6
# How long their words may run: a lead-in is a sentence; a share is a small confession.
LEAD_IN_MAX_CHARS = 300
SHARE_MAX_CHARS = 460

LEAD_IN, HINT, SHARE, BRIDGE, BRIDGE_HINT = "lead-in", "hint", "share", "bridge", "bridge-hint"

# "Not now", "later", "another time", "save it", "drop it", "never mind".
BRUSH_OFF = re.compile(
    r"\b(?:not now|not right now|not the time|not here|later|another time|some other time|"
    r"save it|drop it|never ?mind|no time|can it wait|it can wait|keep it to yourself|"
    r"not interested|don'?t care|shut up|quiet|hush|enough)\b", re.I)
# The player turning to them to hear it: a question, or the words of an invitation.
_INVITE = re.compile(
    r"\?|\b(?:tell me|go on|go ahead|what is it|what'?s (?:wrong|the matter|on your mind|"
    r"bothering you|eating you)|spit it out|out with it|i'?m listening|listening|talk to me|"
    r"say it|speak|what did you want|you wanted to (?:say|tell)|something to say|"
    r"get it off your chest|what were you going to say)\b", re.I)

# Words of a lead-in: there is something, and it is not yet said.
_ON_THEIR_MIND = re.compile(
    r"\b(?:something|a thing|meaning to|been thinking|been wanting|wanted to|want to tell|"
    r"tell you|off my chest|on my mind|another time|some other time|one day|someday|"
    r"later|not now|when there'?s time|reminds me|remind(?:s|ed)? me|i'?ll tell you|"
    r"never mind|forget it|it'?s nothing)\b", re.I)

_STOP = frozenset({
    "their", "they", "them", "theirs", "before", "after", "which", "would", "could", "once",
    "what", "have", "that", "this", "with", "from", "been", "never", "every", "make", "made",
    "enough", "someone", "something", "anybody", "everyone", "people", "thing", "things",
    "finally", "actually", "instead", "other", "properly", "least", "most", "whole", "next",
    "last", "back", "into", "onto", "over", "about", "than", "then", "there", "here", "when",
    "where", "will", "were", "only", "some", "much", "many", "more", "just", "even", "ever",
    "again", "still", "same", "own", "see", "get", "got", "find", "take", "keep", "kept",
    "let", "the", "and", "for", "not", "one", "who", "two", "all", "any", "can", "out",
    "way", "day", "year", "years", "time", "come", "came", "goes", "went", "gone", "anyone",
    "worth", "real", "actually", "nothing", "anything", "else", "able", "lot", "bit",
})


def _stem(w: str) -> str:
    from rules import population

    return population._stem(w)


def key_stems(text: str) -> set[str]:
    """The words of a life row that say what it IS: "to see the sea once before they
    die" → {sea, die}. A share must carry at least one (two, when the row has four or
    more): a paraphrase passes, a different want does not."""
    return {_stem(w) for w in re.findall(r"[a-z][a-z'-]+", str(text or "").lower())
            if w not in _STOP and len(w) >= 3} - {_stem(w) for w in _STOP}


def says_it(line: str, text: str) -> bool:
    keys = key_stems(text)
    if not keys:
        return True
    said = {_stem(w) for w in re.findall(r"[a-z][a-z'-]+", str(line or "").lower())}
    need = 2 if len(keys) >= 4 else 1
    return len(keys & said) >= need


# --- the reminder: something in the world that touches their life --------------------

def reminded_by(topic: str, text: str) -> list[str]:
    row = confiding.row_of(topic, text)
    return [str(w).lower() for w in (row or {}).get("reminded_by") or () if w]


def _hits(words: list[str], text: str) -> list[str]:
    """The reminder words found in `text`, as written there, in order."""
    found: dict[str, int] = {}
    for w in words:
        m = re.search(rf"\b{re.escape(w)}(?:s|es)?\b", text or "", re.I)
        if m:
            found.setdefault(m.group(0).lower(), m.start())
    return sorted(found, key=found.get)


def _fresh(word: str, before: str) -> bool:
    return not re.search(rf"\b{re.escape(word)}", before or "", re.I)


def world_now(scene, *, place=None, moved: bool = False, outcomes=(), beat: str = "",
              ref: str = "") -> list[tuple[str, str]]:
    """What the world put in front of the party this beat, as (source, text): the place
    just walked into, the people here by their trade and years, the turn's own tells, the
    beat's words. Engine facts first, so a match is credited to the most solid source."""
    from rules import population

    out: list[tuple[str, str]] = []
    if moved and place is not None:
        out.append(("place", f"{getattr(place, 'name', '')}. {getattr(place, 'about', '')}"))
    for r, a in (getattr(scene, "actors", {}) or {}).items():
        if r == ref or a.is_pc or companions.is_companion(a) or not scene.conscious(r):
            continue
        rec = population.of_ref(scene, r) or {}
        life = rec.get("life") or {}
        bits = [str(a.name or ""), str(life.get("work_name") or "")]
        tags = set(life.get("tags") or ())
        if "minor" in tags:
            bits.append("child")
        elif "old" in tags:
            bits.append("elder")
        out.append(("person", " ".join(b for b in bits if b)))
    for o in outcomes or ():
        tell = str(getattr(o, "tell", "") or "")
        if tell:
            out.append(("tell", tell))
    if beat:
        from . import speech

        # Their own words are not the world: a companion who mentions the sea has not
        # come across it.
        out.append(("beat", speech.unquoted(beat)))
    return out


def reminder(rec: dict, now: list[tuple[str, str]], before: str,
             topics=None) -> dict | None:
    """The first topic of theirs something fresh in the world touches: {"topic", "thing",
    "source", "text"}, or None."""
    for topic in topics if topics is not None else confiding.untold(rec):
        words = reminded_by(topic, confiding.life_text(rec, topic))
        if not words:
            continue
        for source, text in now:
            for hit in _hits(words, text):
                if _fresh(hit, before):
                    return {"topic": topic, "thing": hit, "source": source, "text": text}
    return None


# --- when -----------------------------------------------------------------------------

def _confidings(scene) -> list[dict]:
    return [e for e in (getattr(scene, "conversation_log", None) or [])
            if isinstance(e, dict) and e.get("src") == "confide"]


def _record(scene, ref: str) -> dict | None:
    from rules import population

    return population.of_ref(scene, ref)


def party(scene) -> list[str]:
    return [r for r, a in (getattr(scene, "actors", {}) or {}).items()
            if companions.is_companion(a) and not a.is_down and scene.conscious(r)]


def heard(scene, transcript, player_text: str, beat: int) -> dict:
    """Before anything answers the player: what their words do to a share that is owed.
    {"invited": [refs], "brushed": [refs], "not_ready": [refs]}.

      * a companion first seen travelling has their clock started (`confiding.since`);
      * a companion owed a share whom the player addresses (`companions.addressed`), or
        whose lead-in was the very last thing before this line and the line names no other
        companion: a brush-off postpones it; a question or an invitation, at a gate that
        allows the share, is `invited` — their answer this beat IS the share, and the
        ordinary answer call is skipped for them; at a gate that allows only the hint,
        `not_ready` — the ordinary answer is told they are not ready to say."""
    out = {"invited": [], "brushed": [], "not_ready": []}
    text = str(player_text or "")
    called = set(companions.addressed(scene, text)) if text.strip() else set()
    for ref in party(scene):
        rec = _record(scene, ref)
        if rec is None:
            continue
        confiding.since(rec, beat)
        pend = confiding.pending(rec)
        if pend is None or not text.strip():
            continue
        just_after = companions._turns_since(transcript, pend.get("beat")) <= 1 \
            and not (called - {ref})
        if ref not in called and not just_after:
            continue
        if BRUSH_OFF.search(text) and not _INVITE.search(re.sub(BRUSH_OFF, "", text)):
            confiding.postpone(rec, beat)
            out["brushed"].append(ref)
            continue
        # Asked, not merely addressed: "Wil, keep watch by the door" is an order, and
        # their ordinary answer's (`views._companions_answer`); the share stays owed. A
        # bare question counts only when it is put to them by name — "shall we eat?"
        # straight after their lead-in is not "what is it?".
        asked = _INVITE.search(text) if ref in called \
            else _INVITE.search(text.replace("?", ""))
        if asked:
            gate = confiding.gate(scene.actors[ref])
            if gate == confiding.SHARE:
                out["invited"].append(ref)
            elif gate == confiding.HINT:
                out["not_ready"].append(ref)
    return out


def due(scene, transcript, outcomes, *, invited=(), answered=(), talking=(),
        moved: bool = False, place=None, beat_text: str = "", before: str = "") -> dict | None:
    """Whether somebody confides this beat, and what: {"ref", "kind", "topic", "door",
    "thing", "source"} or None. At most one, and it takes the ordinary remark's slot.

    In this order: a share the player just asked for; a share owed after a lead-in, at a
    quiet moment `CONFIDE_GAP` turns on and not within a brush-off's `POSTPONE`; a
    reminder (door two); a lead-in (door one). The quiet-moment rules are the remark's
    (`companions.interjection_due`) plus no notable event and no arrival for a lead-in."""
    if getattr(scene, "in_encounter", False) or getattr(scene, "awaiting", None):
        return None
    refs = party(scene)
    if not refs:
        return None
    for ref in invited or ():
        rec = _record(scene, ref)
        pend = confiding.pending(rec)
        if ref in refs and pend and confiding.gate(scene.actors[ref]) == confiding.SHARE:
            return {"ref": ref, "kind": SHARE, "topic": pend["topic"], "door": "asked",
                    "thing": pend.get("thing", ""), "source": ""}
    if answered:
        return None
    if not moved and any(not companions.is_companion(a) for a in talking or ()):
        return None
    remarks = [e for e in (getattr(scene, "conversation_log", None) or [])
               if isinstance(e, dict) and e.get("src") in ("interject", "confide")]
    since_remark = companions._turns_since(transcript, remarks[-1].get("beat")
                                           if remarks else None)
    if since_remark < companions.INTERJECT_GAP:
        return None
    first = companions.least_recently_heard(scene, refs)
    order = [first] + [r for r in refs if r != first]
    # A share owed.
    for ref in order:
        rec = _record(scene, ref)
        pend = confiding.pending(rec)
        if not pend or confiding.gate(scene.actors[ref]) != confiding.SHARE:
            continue
        if companions._turns_since(transcript, pend.get("beat")) < CONFIDE_GAP:
            continue
        if pend.get("postponed") is not None and \
                companions._turns_since(transcript, pend["postponed"]) < POSTPONE:
            continue
        if companions.notable(outcomes):
            continue
        return {"ref": ref, "kind": SHARE, "topic": pend["topic"], "door": "quiet",
                "thing": pend.get("thing", ""), "source": ""}
    # A reminder.
    for ref in order:
        rec = _record(scene, ref)
        gate = confiding.gate(scene.actors[ref])
        if rec is None or gate == confiding.NONE or confiding.pending(rec):
            continue
        topics = [t for t in confiding.untold(rec)
                  if gate == confiding.SHARE or confiding.stage(rec, t) == confiding.NOTHING]
        if not topics:
            continue
        now = world_now(scene, place=place, moved=moved, outcomes=outcomes, beat=beat_text,
                        ref=ref)
        hit = reminder(rec, now, before, topics)
        if hit is None:
            continue
        return {"ref": ref, "kind": BRIDGE if gate == confiding.SHARE else BRIDGE_HINT,
                "topic": hit["topic"], "door": "reminder", "thing": hit["thing"],
                "source": hit["source"]}
    # A lead-in.
    if moved or companions.notable(outcomes):
        return None
    marks = _confidings(scene)
    if companions._turns_since(transcript, marks[-1].get("beat") if marks else None) \
            < CONFIDE_EVERY:
        return None
    for ref in order:
        rec = _record(scene, ref)
        gate = confiding.gate(scene.actors[ref])
        if rec is None or gate == confiding.NONE or confiding.pending(rec):
            continue
        if companions._turns_since(transcript, rec.get("travelling_since")) < CONFIDE_EVERY:
            continue
        fresh = [t for t in confiding.untold(rec) if confiding.stage(rec, t) == confiding.NOTHING]
        if not fresh:
            continue
        return {"ref": ref, "kind": LEAD_IN if gate == confiding.SHARE else HINT,
                "topic": fresh[0], "door": "lead-in", "thing": "", "source": ""}
    return None


# --- what the call is told ------------------------------------------------------------

_WHAT = {"wants": "something they want, now, for themselves",
         "goal": "something they hope for, one day",
         "hobby": "something they do for their own pleasure"}


def facts(scene, actor, plan: dict, *, place=None, player_text: str = "",
          lead_in: str = "") -> str:
    """The confiding call's facts. The lead-in and the hint are NOT told what it is —
    what a model is not told it cannot leak (rules/population.py, ~83% at 12B)."""
    rec = _record(scene, actor.ref) or {}
    name = actor.name
    who = companions.manner_line(scene, actor, ordered=False).split(": ", 1)[-1].rstrip(".")
    who = re.sub(r";\s*nobody told .*$", "", who)
    kind = plan["kind"]
    thing = plan.get("thing") or ""
    lines = [f"Who speaks: {name} (fact): {who}."]
    if kind == LEAD_IN:
        lines.append(f"What this is: {name} tells the player there is something they have "
                     f"wanted to get off their chest — and does NOT say what. They will say "
                     f"it later, when the player is listening.")
    elif kind == HINT:
        lines.append(f"What this is: something is on {name}'s mind, and {name} is not ready "
                     f"to say it to the player yet. They let slip that there is something, "
                     f"and do NOT say what.")
    elif kind == BRIDGE_HINT:
        lines.append(f"What this is: the {thing} put {name} in mind of something of their "
                     f"own. They say the {thing} reminds them of something, and do NOT say "
                     f"what — not yet.")
    else:
        text = confiding.life_text(rec, plan["topic"])
        lines.append(f"What {name} tells the player (fact, {_WHAT[plan['topic']]}, from "
                     f"their own life — say THIS, in their own words, and nothing else "
                     f"about their past): {text}")
        if kind == BRIDGE:
            lines.append(f"What brought it up: the {thing}, here. They start from the "
                         f"{thing} and say what it reminds them of.")
        elif plan.get("door") == "asked":
            lines.append(f"The player has just asked: {' '.join(player_text.split())}")
            if lead_in:
                lines.append(f"Earlier {name} said: {lead_in}")
        elif lead_in:
            lines.append(f"Earlier {name} said: {lead_in} — now, in a quiet moment, they "
                         f"say it.")
    if place is not None and kind in (BRIDGE, BRIDGE_HINT) and plan.get("source") == "place":
        lines.append(f"Where they are: {place.name}.")
    here = [a.name for a in scene.actors.values() if not a.is_pc and scene.conscious(a.ref)]
    lines.append(f"People here: {', '.join(here) or name}.")
    return "\n".join(lines)


def told_line(scene, actor, *, only=None) -> str:
    """What this companion has told the player about themselves, for a call that may
    now use it (known to the player, so nothing leaks), or "". `only` limits it to those
    topics."""
    rec = _record(scene, actor.ref)
    got = [(t, x) for t, x in confiding.told(rec) if only is None or t in only]
    if not got:
        return ""
    return (f"What {actor.name} has already told the player about themselves (known to "
            f"both; never announced again as news): "
            + "; ".join(f"{_WHAT[t].split(',')[0]} — {x}" for t, x in got) + ".")


def relevant_told(scene, actor, text: str) -> list[str]:
    """The told topics something in `text` (the place, the recent beats, the player's
    words) touches: the brief carries a told want only when it is relevant."""
    rec = _record(scene, actor.ref)
    out = []
    for topic, life in confiding.told(rec):
        if _hits(reminded_by(topic, life), text) or (key_stems(life) and says_it(text, life)):
            out.append(topic)
    return out


# --- what may stand -------------------------------------------------------------------

def refusal(line: str, actor, known: set[str], plan: dict, rec: dict | None) -> str:
    """Why a confiding line cannot go on the page, or ""."""
    from . import speech

    kind = plan["kind"]
    limit = LEAD_IN_MAX_CHARS if kind in (LEAD_IN, HINT, BRIDGE_HINT) else SHARE_MAX_CHARS
    why = companions.interjection_refusal(line, actor, known, limit=limit)
    if why:
        return why
    said = " ".join(speech.lines(line))
    thing = str(plan.get("thing") or "")
    if kind in (BRIDGE, BRIDGE_HINT) and thing and not re.search(
            rf"\b{re.escape(thing[:max(4, len(thing) - 2)])}", line, re.I):
        return f"does not say it was the {thing} that brought it up"
    if kind in (LEAD_IN, HINT, BRIDGE_HINT):
        # They were not told it, so a match here is chance or invention; either way the
        # content comes later, after the warm-up.
        for topic in confiding.TOPICS:
            text = confiding.life_text(rec, topic)
            if text and len(key_stems(text)) >= 2 and says_it(said, text):
                return "says what it is too soon — only that there is something"
        if not _ON_THEIR_MIND.search(said):
            return ("does not say there is something on their mind — say there is "
                    "something, and not what")
        if len(said.split()) > 40:
            return "is too long for a hint"
        return ""
    text = confiding.life_text(rec, plan["topic"])
    if not says_it(said, text):
        return (f"does not say what it is ({text}) — say that, in their own words, and "
                f"nothing else about their past")
    return ""
