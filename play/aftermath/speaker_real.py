"""A speaker the prose introduced, who spoke to the player, is made real (item 20.4).

Measured on the Bobby playtest, 2026-09-28, turn 9: in the woods "a man in a stained
leather jerkin" sharpened a skinning knife and spoke three lines to the player — "The road
to Grotburrow isn't for the faint of heart", "You looking for a shortcut, or just lost?".
The prose call tagged them to `new1`, a ref nobody held: `speech-tags` logged
`unknown_refs: ["new1"]`, 3 lines, 0 attributed. The man existed as a population record
only; nobody was hailed, no conversation opened, and he became an actor (c8) one turn
later, only because the player turned to him.

The owner's ruling (Q5, 2026-09-28): a speaker addressing the player gets a body through
the arrival door — but only when matched to the record this beat wrote. So, before the
hails are read (the "people" stage runs just before `hailed_by`):

  * the lines whose tag named nobody here (`who` empty, the claim kept in `was`), and to
    the player (`to` "you", or no `to` with "you" in the words);
  * the people this beat recorded at the party's spot with no body yet, whose words the
    page uses (`checks._people.names_person`) — PDNC's lesson (Vishnubhotla et al. 2023):
    attribution restricted to people already resolved went from 0.40 to 0.62;
  * exactly one such person, one claimed speaker: they walk on through the one door
    (`judgement.embody` → `Scene.arrive`, a square with it — the item-14 ruling), wearing
    the face their record rolled, and the lines are re-tagged to them (`"made": ref`).

**And the lines nobody tagged at all** (the Phase-2 live gate, G2, 2026-09-29, gemma-4-12B
in Halhollow): a beat brought on "a man in a stained leather apron" who said "'That's a
long way to sit and watch a man work,' he says… 'You looking for something specific, or
just waiting for the world to start?'" — `speech-tags {tagged: 0, lines: 2}`, `mentions
{unknown: 2}`, the scene's people stayed pc, c1, c2, and the conversation log stayed empty.
The path above never saw him: it starts from a tag, and tagging is all or nothing per
beat (4 of 8 beats tagged, 2026-09-25). So the page is read the way the tagless tradition
reads it — the quote-attribution cues of He et al. 2013 and Muzny et al. 2017, in their
cheapest code form, over `checks._people.spans_in_context`:

  1. an explicit clause beside the line — "…,' he says", "…,' the woman adds", "says the
     carter", "The carter turns and asks, '…";
  2. else the speaker of the line before it in the same paragraph, when this one has no
     clause (a speech run on after "he says, nodding at the lock-keeper.");
  3. else the one person the sentence before names.

A pronoun is carried to the nearest person described before it in the narration. The
answer must be one of THIS beat's population records at the party's spot with no body —
the Q5 limit — and each of these refuses rather than guesses:

  * a pronoun with nobody described before it ("…,' he says" and no man anywhere) makes
    nobody: a body out of a bare "he" is the phantom this project keeps paying for;
  * a person already on the board — by the words of their name, or by the attribution's
    own answer — is attribution, not embodiment: `hailed_by`'s guess has them;
  * a pronoun whose gender the nearest person contradicts ("she says" after "a man")
    makes nobody;
  * a person none of whose lines addresses the player makes nobody (the ruling is about
    being spoken TO); one who did is given every line of theirs in the beat;
  * one body per record per beat, however many lines and descriptions.

A line so resolved gains a record in `said` (`"made": ref, "from": "page"`), the one
addition the "people" stage may make (`play.aftermath._said_kept`), so `hailed_by` reads a
hail from it and the "beat" stage's conversation log keeps the lines.

Anything less certain changes nothing and says why in a row. In a fight the prose makes
no bodies at all (`GMAgent._undeclared_arrivals` rewrites the newcomer out), so this step
stands aside.
"""
from __future__ import annotations

import re

STAGE = "people"
ORDER = 10
DOORS = frozenset({"turn", "carry_on", "opening"})

_YOU = re.compile(r"\b(?:you|your|you're|you've|you'll|yours|yourself)\b", re.I)


def _to_the_player(rec: dict) -> bool:
    to = str(rec.get("to") or "")
    return to == "you" or (not to and bool(_YOU.search(str(rec.get("line") or ""))))


def step(ctx) -> list[dict]:
    rows = _from_tags(ctx)
    return rows + _from_the_page(ctx)


def _from_tags(ctx) -> list[dict]:
    """The lines the prose call tagged to a ref nobody held (the Bobby turn 9 path)."""
    scene = ctx.scene
    lines = [r for r in (ctx.said or []) if not r.get("who") and _to_the_player(r)]
    if not lines:
        return []
    if getattr(scene, "in_encounter", False):
        return [{"kind": "speaker-real", "made": "", "lines": len(lines),
                 "why": "in a fight the prose brings nobody in"}]
    claimed = {str(r.get("was") or "") for r in lines}
    if len(claimed) != 1:
        return [{"kind": "speaker-real", "made": "", "lines": len(lines),
                 "why": f"lines claimed for {len(claimed)} different speakers"}]
    from gm.checks._people import names_person
    from gm.narration import unquoted

    narration = unquoted(ctx.text)
    here = getattr(scene, "at", None)
    held = set(getattr(scene, "actors", {}) or {})
    candidates = [rec for rec in (getattr(scene, "population", None) or {}).values()
                  if rec.get("spot") == here
                  and not (rec.get("ref") and rec["ref"] in held)
                  and names_person(narration, str(rec.get("phrase") or ""))]
    # One person, however many phrases the page recorded them under: two records whose
    # head words agree ("man in a stained leather jerkin", "man with the whetstone") are
    # the same man described twice; two different heads are two people.
    from gm.checks._people import head_of

    heads = {head_of(str(r.get("phrase") or "")) for r in candidates}
    if len(heads) != 1:
        return [{"kind": "speaker-real", "made": "", "lines": len(lines),
                 "why": f"{len(candidates)} people this beat could mean"}]
    rec = min(candidates, key=lambda r: int(re.sub(r"\D", "", str(r.get("id"))) or 0))
    actor = _embody(ctx, rec)
    for r in lines:
        r["who"] = actor.ref
        r["made"] = actor.ref
    return [{"kind": "speaker-real", "made": actor.ref, "phrase": rec["phrase"],
             "record": rec.get("id", ""), "lines": len(lines),
             "square": list(scene.positions.get(actor.ref) or [])
             if getattr(scene, "positions", None) else []}]


def _embody(ctx, rec: dict):
    """Through the one door (`judgement.embody` → `population.embody` → `Scene.add`, a
    square with it), wearing the face the record rolled; onto the ledger with its ref."""
    from gm import judgement

    scene = ctx.scene
    actor = judgement.embody(scene, str(rec["phrase"]), world=ctx.world, rec=rec)
    if not any(e.get("ref") == actor.ref for e in getattr(scene, "cast", []) or []):
        scene.cast.append({"who": rec["phrase"], "turn": int(rec.get("turn", 0) or 0),
                           "ref": actor.ref})
    return actor


# --- the lines nobody tagged ------------------------------------------------------------------

# The clause patterns live in `gm.checks._quotes`, shared with the sentence repair and the
# cut-only backstops of keeper-forward and master-approaches (item 12, 2026-09-30): the
# repair has to find the same "…,' he says" this attribution reads, or it cuts the quote
# and leaves the clause claiming somebody said it.
from gm.checks._quotes import clause as _shared_clause  # noqa: E402


def _clause(blank: str, qa: int, qb: int) -> str:
    """The subject of the speech clause beside the quotation at [qa, qb), or ""."""
    return _shared_clause(blank, qa, qb)


def _words_re(words) -> re.Pattern | None:
    words = sorted({w for w in words if w}, key=len, reverse=True)
    if not words:
        return None
    return re.compile(r"\b(?:" + "|".join(re.escape(w) for w in words) + r")(?:s|es)?\b",
                      re.I)


class _Room:
    """Who the narration can mean: this beat's bodiless records here, and the board."""

    def __init__(self, ctx, narration: str):
        from gm.checks._people import head_of, name_words
        from rules import population

        scene = ctx.scene
        here = getattr(scene, "at", None)
        held = set(getattr(scene, "actors", {}) or {})
        low = " ".join(narration.lower().split())
        # This beat's records (Q5): at the party's spot, no body, and described by the
        # words they were recorded under somewhere in this beat's narration.
        self.records = [
            rec for rec in (getattr(scene, "population", None) or {}).values()
            if rec.get("spot") == here and not (rec.get("ref") and rec["ref"] in held)
            and population._norm(rec.get("phrase", ""))
            and population._norm(rec.get("phrase", "")) in population._norm(low)]
        self.head = {rec["id"]: head_of(str(rec.get("phrase") or "")).lower()
                     for rec in self.records}
        self.board: dict[str, set[str]] = {}
        for ref, a in (getattr(scene, "actors", {}) or {}).items():
            if getattr(a, "is_pc", False):
                continue
            words = set(name_words(str(a.name or "")))
            words |= set(name_words(str(getattr(a, "true_name", "") or "")))
            self.board[ref] = {w.lower() for w in words}
        self.att = getattr(ctx, "attribution", None)
        pc = scene.pc() if hasattr(scene, "pc") else None
        self.pc_name = str(getattr(pc, "name", "") or "")

    def by_head(self, head: str) -> tuple[list[dict], list[str]]:
        head = head.lower()
        recs = [r for r in self.records if self.head[r["id"]] == head]
        board = [ref for ref, words in self.board.items() if head in words]
        return recs, board

    def mentions(self, narration: str) -> list[tuple[int, int, str, str]]:
        """(start, end, "record"|"board"|"other", id) for every person the narration
        names, the longest words winning where two overlap."""
        from gm.checks._people import _PERSON
        from gm import speech

        found: list[tuple[int, int, str, str]] = []
        for rec in self.records:
            words = [re.escape(w) for w in re.findall(r"[a-z']+", str(rec["phrase"]).lower())]
            if words:
                pat = re.compile(r"\b" + r"[\s,-]+".join(words) + r"\b", re.I)
                found += [(m.start(), m.end(), "record", rec["id"])
                          for m in pat.finditer(narration)]
        for ref, words in self.board.items():
            pat = _words_re(words)
            if pat:
                found += [(m.start(), m.end(), "board", ref) for m in pat.finditer(narration)]
            # A description the page pinned to a ref — "the man in the heavy coat (c4)" —
            # is that person, whatever their name's words: measured on the 2026-10-03 save
            # (item 15), c4's name was the player's quoted words, the page called him "the
            # man in the heavy coat (c4)", and "man" made a new man, c6, out of his lines.
            # The whole description is claimed, so a shorter match inside it loses.
            for m in re.finditer(r"\b(?:the|a|an|this|that)\s+(?:[a-z'’-]+\s+){0,6}?"
                                 r"[a-z'’-]+\s*\(" + re.escape(ref) + r"\)", narration, re.I):
                found.append((m.start(), m.end(), "board", ref))
        # Anybody else the narration describes — with a determiner, the way the
        # attribution's own finder reads a description (`mentions.find`): "wiping his
        # hands on a rag" is a body part, and `_PERSON` holds "hand" for the farmhand.
        heads = set(_PERSON) - set(speech._COLLECTIVE)
        alt = "|".join(sorted((re.escape(h) for h in heads), key=len, reverse=True))
        pat = re.compile(r"\b(?:the|a|an|this|that|another|one)\s+(?:[a-z'’]+[\s-]+){0,3}?"
                         r"(?P<head>" + alt + r")\b(?!-)", re.I)
        for m in pat.finditer(narration):
            found.append((m.start("head"), m.end("head"), "other", m.group("head").lower()))
        # Longest first at each place; drop what a longer match already covers.
        found.sort(key=lambda f: (f[0], -(f[1] - f[0])))
        kept: list[tuple[int, int, str, str]] = []
        for f in found:
            if kept and f[0] < kept[-1][1]:
                continue
            kept.append(f)
        return kept

    def settle(self, kind: str, ident: str) -> tuple[str, str]:
        """A mention as ("record", id) | ("board", ref) | ("", why)."""
        if kind in ("record", "board"):
            return kind, ident
        recs, board = self.by_head(ident)
        if board:
            return "board", board[0]
        if len(recs) == 1:
            return "record", recs[0]["id"]
        if recs:
            return "", f"{len(recs)} people here are a {ident}"
        return "", f"the {ident} is nobody this beat recorded"


def _gender_of(word: str) -> str:
    from gm import speech

    word = word.lower()
    return "f" if word in speech._FEMALE else "m" if word in speech._MALE else ""


def _speaker(room: _Room, blank: str, subj: str, qa: int) -> tuple[str, str]:
    """Who a clause's subject is: ("record", id) | ("board", ref) | ("", why)."""
    from gm.checks._people import head_of

    words = subj.split()
    if words and words[0].lower() in ("he", "she", "they") and len(words) == 1:
        before = room.mentions(blank[:qa])
        if not before:
            return "", f"'{subj}' with nobody described before it"
        kind, ident = before[-1][2], before[-1][3]
        settled = room.settle(kind, ident)
        if settled[0] == "record":
            rec = next(r for r in room.records if r["id"] == settled[1])
            said = {"he": "m", "she": "f"}.get(words[0].lower(), "")
            has = _gender_of(room.head[rec["id"]])
            if said and has and said != has:
                return "", f"'{subj}' after a {room.head[rec['id']]}"
        return settled
    # A description. The record whose words it holds; else its head word.
    low = " ".join(subj.lower().split())
    for rec in room.records:
        from rules import population

        if population._norm(rec["phrase"]) in population._norm(low):
            return "record", rec["id"]
    head = head_of(subj).lower()
    if not head or " " in head:
        return "", f"'{subj}' is not a description of a person"
    return room.settle("other", head)


def _from_the_page(ctx) -> list[dict]:
    """The untagged lines, attributed by the three rules of the module docstring.

    **A line attributed to somebody on the board is booked as theirs** (2026-09-30
    playtest, item 1): 37 of 43 real NPC lines reached the conversation log, and of the 6
    that did not, the page had already said who spoke — "'…,' the cage owner says" at the
    opening, "They lean in slightly… 'He's still with us…'" at beat 3, the guard running
    on after his tagged "A brothel, eh?" at beat 49. The rules found them, then wrote
    only a miss row ("on the board: attribution, not a body") and no `said` record, and
    returned early before reading any beat whose lines held no "you". So a ("board",
    ref) answer appends `{"who": ref, "to": …, "line": …, "from": "page"}` — with no
    "you" gate and in a fight too, because what somebody said is what they said. The Q5
    limits stay on MAKING a body (owner's ruling A1): only a line to the player, out of
    a fight, embodies a record.

    Rule 2 now carries the speaker of a TAGGED line before as well (beat 49's run-on),
    and rule 3 carries a sentence-initial He/She/They through `_speaker`'s nearest
    mention (beat 3's "They lean in slightly"): Muzny et al. 2017's sieve order, where
    the conversation-run and the pronoun-subject sieves come after the explicit clause."""
    from gm import speech

    scene = ctx.scene
    text = str(ctx.text or "")
    said = ctx.said if isinstance(ctx.said, list) else []
    fighting = bool(getattr(scene, "in_encounter", False))
    # Every quotation in order, the tagged ones included, so rule 2 can carry a tag on:
    # (qa, qb, line, tagged ref or None).
    every = []
    for qa, qb in speech.spans(text):
        line = text[qa + 1:qb - 1] if qb - qa >= 2 else ""
        if not line.strip():
            continue
        rec = speech.speaker(said, line)
        every.append((qa, qb, line,
                      str(rec.get("who") or "") if rec is not None else None))
    quotes = [(qa, qb, line) for qa, qb, line, tag in every if tag is None]
    if not quotes:
        return []
    blank = speech.blanked(text)
    room = _Room(ctx, speech.unquoted(text))
    # 1-3 of the docstring: each untagged line's speaker, as ("record", id) |
    # ("board", ref) | ("", why).
    whose: list[tuple[str, str]] = []
    prev: tuple[int, tuple[str, str]] | None = None     # (end of the line before, whose)
    for qa, qb, line, tag in every:
        if tag is not None:
            prev = (qb, ("board", tag) if tag in room.board else ("", "tagged"))
            continue
        w = _whose(room, blank, text, qa, qb, prev)
        whose.append(w)
        prev = (qb, w)
    rows: list[dict] = []
    misses: dict[str, int] = {}
    made: dict[str, object] = {}
    for rid in dict.fromkeys(ident for kind, ident in whose if kind == "record"):
        mine = [q for q, w in zip(quotes, whose) if w == ("record", rid)]
        if fighting or not any(_YOU.search(line) for _qa, _qb, line in mine):
            continue            # the fight's rule; or spoke, but not to the player
        rec = next(r for r in room.records if r["id"] == rid)
        actor = _embody(ctx, rec)
        made[rid] = actor
        for _qa, _qb, line in mine:
            said.append({"who": actor.ref, "to": "you", "line": line.strip(),
                         "made": actor.ref, "from": "page"})
        rows.append({"kind": "speaker-real", "made": actor.ref, "phrase": rec["phrase"],
                     "record": rid, "lines": len(mine), "untagged": len(mine),
                     "square": list(scene.positions.get(actor.ref) or [])
                     if getattr(scene, "positions", None) else []})
    booked: dict[str, int] = {}
    for (qa, qb, line), (kind, ident) in zip(quotes, whose):
        if kind == "board":
            said.append({"who": ident, "to": "you" if _YOU.search(line) else "",
                         "line": line.strip(), "from": "page"})
            booked[ident] = booked.get(ident, 0) + 1
            continue
        if not _YOU.search(line) or (kind == "record" and ident in made):
            continue
        why = ("in a fight the prose brings nobody in" if fighting and kind == "record"
               else ident if not kind else "")
        if why:
            misses[why] = misses.get(why, 0) + 1
    rows += [{"kind": "speaker-real", "made": "", "booked": ref, "lines": n,
              "why": "on the board: the line is theirs, attribution, not a body"}
             for ref, n in booked.items()]
    rows += [{"kind": "speaker-real", "made": "", "untagged": n, "why": why}
             for why, n in misses.items()]
    return rows


def _whose(room: _Room, blank: str, text: str, qa: int, qb: int,
           prev: tuple[int, tuple[str, str]] | None) -> tuple[str, str]:
    """One untagged line's speaker, by rules 1-3 of the module docstring."""
    # 0: the player's character's own line — "'…,' you say", or the second half of one
    # ("…,' you say, …, '…'"). Measured on the 2026-10-03 save (item 15): with no "you"
    # among the clause subjects, rule 3 gave Kesst's invented line to the clerk the
    # sentence before named, and "You speak clearly, 'Just trying…'" to the servant.
    from gm.checks._quotes import pc_spoken

    if pc_spoken(blank, qa, qb, room.pc_name, after=prev[0] if prev is not None else -1):
        return "", "the player's own line"
    subj = _clause(blank, qa, qb)
    if subj:
        return _speaker(room, blank, subj, qa)
    # 2: the line before in the same paragraph, tagged or not, when it had a speaker.
    if prev is not None and prev[1][0] and "\n\n" not in text[prev[0]:qa]:
        return prev[1]
    # 3: the sentence before, alone — exactly one person named in it; or, naming nobody,
    # opened by a He/She/They that carries the nearest person described before it.
    head = blank[:qa].rstrip()
    cut = max(head[:-1].rfind("."), head[:-1].rfind("!"), head[:-1].rfind("?"),
              head[:-1].rfind("\n"))
    sentence = blank[cut + 1:qa]
    named = room.mentions(sentence)
    settled = {room.settle(k, ident) for _a, _b, k, ident in named}
    if len(settled) == 1 and next(iter(settled))[0]:
        return next(iter(settled))
    lead = re.match(r"\s*(He|She|They)\b", sentence)
    if not named and lead:
        return _speaker(room, blank, lead.group(1), cut + 1 + lead.start(1))
    return "", "no speaker named beside the line"
