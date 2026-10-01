"""A people the page granted in reply binds the next person made there (owner ruling F2).

Measured on the 2026-09-30 playtest (docs/playtest-2026-09-30-findings.md item 10, turns
22-23 of Sam's save). The player asked the barkeep "any human women here?"; Gorm answered
"There is one," and the narrator described a woman humming behind the curtain. When the
party went through, the chamber's keeper was minted — Quin Nutmeg — with the town's
people's face: "Ratfolk: Small, rodent-featured…". The prose described human hair and skin
and then, a few beats later, "rodent-featured eyes". The answer had been given and nothing
held it.

**What the traditions do with an answer once given.** The solo-play tradition is the one
built around this exact move — the player asks the world a question and the answer becomes
part of it. Mythic GME's Fate Question is the model: the answer is interpreted into the
adventure and becomes context the next question builds on ("every new Question adds
Context", Mythic GME 2e, Word Mill Games). Ironsworn's oracle guidance says the same from
the other side: "If an answer to a question or the result of a situation is obvious,
interesting and dramatic, make it happen" (Ironsworn rulebook, p.104). And Vincent Baker's
account of the Apocalypse World conversation, "Fictional causes have real effects"
(lumpley.games, "Powered by the Apocalypse, part 1", 2019): what was said in the fiction
constrains what the rules may do next. Ironsworn's *vows* were looked at and are not the
precedent: a vow is the player character's sworn quest with a progress track, a promise
the PC makes, not a fact the world states — the brief named them, and they do not fit.
Nothing found describes a system that let an answer lapse on purpose; the failure here is
the absence of the record, not a rule that chose to drop it.

**The shape.** Detected in code, never asked of a model: the player's own words name a
people (a world PEOPLE, or "human") — `person_words.people_named` — and an NPC's line in
the same beat opens by affirming somebody is there ("There is one", "Aye", "We've two").
The grant is then an engine record: a population record (the store every person heard of
already lives in — the finder can find her and `introduce` binds to her) carrying a
`granted` block. The next person minted at that place or inside it — the keeper door, the
embody door (introduce, the speaker made real, the player turning to her) — claims it and
draws that people's body, name pool and the granted gender (`person_words.settle_people`).
Claimed once; a claimed grant binds nobody else. A minted person whose own words contradict
it (a "man", where a woman was granted) does not claim it.

The tell is the brief's: `gm/brief/granted_people.py` states each open grant as a fact the
narrator writes to, and the turn log carries a `people-granted` row.
"""
from __future__ import annotations

import re

# The player asked about presence. A people named in "I kill the elf" is not a question
# the world answers; "any elves here?", "is there an elf in the back" are.
_ASKS = re.compile(r"\?|^\s*(?:any|is there|are there|do you have|have you got|got any|"
                   r"you got any|where (?:is|are|can i find))\b", re.I)
# The NPC's line opens by saying yes. Tight on purpose: the grant binds a body, and a
# false positive puts a people on somebody nobody promised.
_AFFIRMS = re.compile(
    r"^\W*(?:yes|yeah|yep|aye|sure|of course|indeed|certainly|"
    r"there(?:'s|’s| is| are| be)\s+(?:one|a\s+few|some|two|three|a\s+couple|a\s+girl|"
    r"a\s+woman|a\s+man|a\s+lad|a\s+lass)|"
    r"we(?:'ve|’ve| have| got)\s+(?:one|some|a\s+few|two|three|a\s+couple)|"
    r"one(?:'s|’s| is)\s+(?:here|in|behind|upstairs|downstairs|out|back|through)|"
    # The asked-for words given back, then the yes: "A woman, aye," — Gorm's answer in
    # the 2026-10-01 replay, which the opening-yes pattern missed, so nothing recorded her.
    r"(?:a|an|one)\s+(?:[a-z'’-]+\s+){0,2}?[a-z'’-]+\s*,\s*(?:aye|yes|yeah|indeed|sure))\b",
    re.I)
_NEGATES = re.compile(r"\b(?:no|none|not|never|nobody|no one|isn't|aren't|ain't|"
                      r"isn’t|aren’t|ain’t|neither|nay)\b", re.I)
_HUMAN = re.compile(r"(?<![\w-])humans?(?![\w-])", re.I)


# Somebody is THERE, said anywhere in the line: "there's a group of sisters … staying in the
# chamber" (live, 2026-09-30, after "They're mostly in the inner wards"). A clause, not the
# line: it must itself begin with the existential and carry no negation.
_THERE_IS = re.compile(
    r"^\W*(?:but\s+|and\s+|still\s+|though\s+)?(?:(?:if|when)\s+[^,]*,\s*)?"
    r"there(?:'s|’s| is| are| be)\s+(?:one|a|an|some|two|three|a\s+few|a\s+couple|"
    r"a\s+group|a\s+pair|several)\b", re.I)


def _opening_clause(line: str) -> str:
    return re.split(r"[,.;:!?—–]", str(line or ""), maxsplit=1)[0]


def affirms(line: str) -> bool:
    """Whether an NPC's line says somebody is there.

    Its opening clause first: "There is one, but she isn't looking for company" is a yes
    (the playtest's line), and an opening "No" or "None" is a no whatever follows — "No,
    but there's a dwarf upstairs" answers a different question. Otherwise any sentence of
    the line that is itself "there is/are <somebody>", un-negated: Gorm's live answer put
    the yes in its third clause."""
    line = str(line or "")
    first = _opening_clause(line)
    if _NEGATES.search(first):
        return False
    if _AFFIRMS.match(line):
        return True
    for sentence in re.split(r"(?<=[.!?;])\s+", line):
        if _THERE_IS.match(sentence) and not _NEGATES.search(sentence):
            return True
        # "But if you're looking for company, there's a group of sisters …": the
        # existential after a leading condition.
        m = re.search(r",\s*(there(?:'s|’s| is| are)\s.*)$", sentence, re.I)
        if m and _THERE_IS.match(m.group(1)) and not _NEGATES.search(m.group(1)):
            return True
    return False


def asked_for(player_text: str, world) -> dict | None:
    """The people and gender the player asked after, or None.

    ``{"people_id", "kind", "gender", "phrase"}``: `people_id` the world's PEOPLE id the
    words name, else "" with `kind` "human" for a world that ships no Human — the player
    may ask for one anywhere, and the answer still binds the body's kind."""
    from . import person_words

    text = str(player_text or "")
    if not text or not _ASKS.search(text):
        return None
    pid = person_words.people_named(text, world)
    kind = ""
    if pid:
        kind = person_words.people_name(world, pid)
    elif _HUMAN.search(text):
        kind = "human"
    else:
        return None
    gender = person_words.gender_of(person_words._words(text))
    noun = gender or "person"
    return {"people_id": pid, "kind": kind, "gender": gender,
            "phrase": f"{kind.lower()} {noun}".strip(),
            "elsewhere": bool(_ELSEWHERE.search(text))}


# The question places them somewhere else: "it is a human woman who LIVES THERE right?"
# (the owner's save, 2026-10-01, of the house "three streets over"). A yes to that is not a
# promise of somebody HERE, and binding the next person minted in the tavern to it would
# hand the tavern's next stranger the people of a woman who lives across town.
_ELSEWHERE = re.compile(
    r"\b(?:lives?|living|stays?|staying|works?|sleeps?)\s+(?:there|over|in|at|on|by|near|"
    r"across|down|up|out)\b|\bover\s+there\b|\bacross\s+town\b|\bstreets?\s+(?:over|away|"
    r"down|from)\b|\bdown\s+the\s+(?:road|street|lane)\b", re.I)


def detect(player_text: str, said, world, scene, text: str = "") -> list[dict]:
    """The grants this beat made: the player asked after a people, and an NPC here said
    yes. Each is ``asked_for``'s dict plus ``by`` (the NPC's ref) and ``line``.

    The tagged lines first. Then, when the prose call tagged nothing (live, 2026-09-30:
    Gorm's answer came back with `said` empty), the page's own quotations, as spoken by
    the one person the player asked — named in the player's words, else the one person
    in conversation, else the only person here. Never a guess between two."""
    asked = asked_for(player_text, world)
    if asked is None:
        return []
    people = getattr(scene, "people", {}) or {}
    for rec in said or []:
        who = str(rec.get("who") or "")
        actor = people.get(who)
        if actor is None or getattr(actor, "is_pc", False):
            continue
        if affirms(str(rec.get("line") or "")):
            return [dict(asked, by=who, line=str(rec.get("line") or "").strip())]
    if not text:
        if asked.get("elsewhere"):
            for rec in said or []:
                who = str(rec.get("who") or "")
                if who in people and not getattr(people[who], "is_pc", False) and \
                        _speaks_of(str(rec.get("line") or ""), asked):
                    return [dict(asked, by=who, line=str(rec.get("line") or "").strip())]
        return []
    from gm import speech

    who = _the_one_asked(scene, player_text)
    if who is None:
        return []
    lines = [ln for ln in speech.lines(text) if speech.speaker(said or [], ln) is None]
    for line in lines:
        if affirms(line):
            return [dict(asked, by=who, line=line.strip())]
    if asked.get("elsewhere"):
        # Asked about somebody who lives elsewhere, the answer need not open with a yes to
        # be about her. Replayed 2026-10-01 on the owner's save: "it is a human woman who
        # lives in the house 3 streets over, right?" — Gorm: "'Three streets over … The
        # house with the blue shutters … A woman alone in a house like that doesn't take
        # kindly to strangers'". Nothing recorded her, and the call on "the human woman
        # Grom spoke of" found nobody. A heard-of record binds no body in the room, so the
        # looser reading costs nothing a strict one protects.
        for rec in said or []:
            if str(rec.get("who") or "") == who and _speaks_of(str(rec.get("line") or ""),
                                                                asked):
                return [dict(asked, by=who, line=str(rec.get("line") or "").strip())]
        for line in lines:
            if _speaks_of(line, asked):
                return [dict(asked, by=who, line=line.strip())]
    return []


def _speaks_of(line: str, asked: dict) -> bool:
    """Whether a reply is about the person asked after: it names them by the asked-for
    noun or a pronoun of theirs, and does not open by saying no."""
    if _NEGATES.search(_opening_clause(line)):
        return False
    gender = asked.get("gender") or ""
    words = {"woman": r"woman|she|her|lady|lass", "man": r"man|he|him|fellow|lad"}.get(
        gender, r"one|someone|somebody|they")
    kind = str(asked.get("kind") or "").lower()
    if kind:
        words += "|" + re.escape(kind)
    return bool(re.search(rf"(?<![\w-])(?:{words})(?![\w-])", str(line or ""), re.I))


def _the_one_asked(scene, player_text: str) -> str | None:
    """Who the player put the question to, when it can be told without guessing."""
    from . import states

    actors = [(r, a) for r, a in (getattr(scene, "actors", {}) or {}).items()
              if not getattr(a, "is_pc", False)]
    words = {w.lower() for w in re.findall(r"[A-Za-z]{3,}", str(player_text or ""))}
    named = [r for r, a in actors
             if words & {w.lower() for w in re.findall(r"[A-Z][a-z]{2,}", str(a.name))}]
    if len(named) == 1:
        return named[0]
    talking = [r for r, a in actors if a.has_state(states.TALKING)]
    if len(talking) == 1:
        return talking[0]
    return actors[0][0] if len(actors) == 1 else None


def grant(scene, found: dict, *, turn: int = 0) -> dict | None:
    """Record one grant at the party's place: a population record, heard of and not yet
    seen, carrying the `granted` block. The same grant twice (the player asks again and is
    told again) is the one record. Returns the record."""
    from . import population

    at = str(getattr(scene, "at", "") or "")
    if not at:
        return None
    # Asked about somebody who lives elsewhere: heard of, with no place — the place the
    # talk happened is not where she is (`asked_for`'s `elsewhere`).
    place = "" if found.get("elsewhere") else at
    for rec in open_grants(scene):
        g = rec["granted"]
        if (g.get("place") == place and g.get("people_id") == found.get("people_id")
                and g.get("kind") == found.get("kind")
                and g.get("gender") == found.get("gender")):
            return rec
    # The beat's own narration may already have recorded her a moment ago ("he had told
    # you a human woman lives there" booked p16, then this grant made p17 — the owner's
    # save, 2026-10-01): one person, so that record becomes the grant.
    rec = _recorded_this_beat(scene, found["phrase"], turn)
    if rec is None:
        rec = population.note(scene, found["phrase"], turn=turn, fresh=True,
                              **({"spot": ""} if not place else {}))
    elif not place:
        rec["spot"] = ""
        rec["seen_at"] = ""
        rec["last_seen"] = None
    if not place and isinstance(rec.get("life"), dict):
        # Asked about as somebody who lives there: a resident, whatever the roll said of
        # travelling — a merchant rolled for her would have the call on her house refused
        # with "They keep no house in this town".
        rec["life"]["mobility"] = "resident"
        rec.pop("anchor", None)
    # Heard of: Gorm said she is there, nobody has seen her.
    rec["seen"] = False
    rec["heard_from"] = str(found.get("by") or "")
    rec["heard_at"] = int(getattr(scene, "clock_minutes", 0) or 0)
    rec["granted"] = {
        "people_id": str(found.get("people_id") or ""), "kind": str(found.get("kind") or ""),
        "gender": str(found.get("gender") or ""), "place": place,
        "by": str(found.get("by") or ""), "line": str(found.get("line") or "")[:200],
        "turn": int(turn), "claimed_by": "",
    }
    return rec


def _recorded_this_beat(scene, phrase: str, turn: int) -> dict | None:
    """The one record this beat's prose made (no body, no grant) that the granted phrase
    describes, or None. Unseen-or-not does not matter: the beat wrote her a moment ago."""
    from . import population

    words = population._tokens(phrase)
    bodies = getattr(scene, "people", {}) or {}
    fits = [r for r in (getattr(scene, "population", None) or {}).values()
            if r.get("turn") is not None and int(r["turn"]) == int(turn) and not isinstance(r.get("granted"), dict)
            and not (r.get("ref") and r["ref"] in bodies)
            and words and population._fits(words, population._bag(r, scene))]
    return fits[0] if len(fits) == 1 else None


def open_grants(scene) -> list[dict]:
    """Every grant no person has claimed yet, oldest first."""
    out = [rec for rec in (getattr(scene, "population", None) or {}).values()
           if isinstance(rec.get("granted"), dict) and not rec["granted"].get("claimed_by")
           and not rec.get("ref")]
    return sorted(out, key=lambda r: int(r["granted"].get("turn") or 0))


def _within(place: str, grant_place: str) -> bool:
    """The grant's place, or a place inside it: "behind the curtain" is the chamber
    founded inside the tavern (`…/the-velvet-veil/the-chamber`)."""
    place, grant_place = str(place or ""), str(grant_place or "")
    return bool(place and grant_place) and (
        place == grant_place or place.startswith(grant_place + "/"))


def claim(scene, place: str, *, gender: str = "", ref: str = "",
          rec: dict | None = None) -> dict | None:
    """The grant the next person minted at `place` is bound by, marked claimed by `ref`;
    None when nothing was granted there.

    `rec` is the person's own population record: when it IS a grant it is the one claimed.
    `gender` is what the person's own words say; a grant of a woman is not claimed by
    somebody the words call a man (nor the reverse)."""
    if rec is not None and isinstance(rec.get("granted"), dict):
        g = rec["granted"]
        if not g.get("claimed_by"):
            g["claimed_by"] = ref or "?"
        return g
    for cand in open_grants(scene):
        g = cand["granted"]
        if not _within(place, g.get("place", "")):
            continue
        if gender and g.get("gender") and gender != g["gender"]:
            continue
        g["claimed_by"] = ref or "?"
        if ref:
            cand["ref"] = ref
        return g
    return None


def phrase_of(g: dict) -> str:
    """"a human woman" — how the brief says what was granted."""
    words = f"{str(g.get('kind') or '').lower()} {g.get('gender') or 'person'}".strip()
    return ("an " if words[:1] in "aeiou" else "a ") + words
