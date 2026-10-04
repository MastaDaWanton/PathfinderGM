"""The suggestions follow who the player is dealing with: a pronoun that fits nobody here is
the dealing person's, or the suggestion goes.

Measured on the 2026-09-28 playtest (item 15): with Drenn Ironvale — a man, on the page —
the only person speaking, the suggestions read "I ask her what she's looking for…". They
are the model's own words (`GMAgent.last_suggestions`), written after the beat, and nothing
checked a pronoun in them against anybody present. Detect in code, repair in code: the
pronoun family is compared with the people here; one that fits nobody is rewritten to the
person the player is dealing with, when their pronouns are set, and dropped otherwise.

Who the player is dealing with, in order: the person in conversation with them
(`talk.with-you`), else this beat's speaker to the player (`said` with to="you"), else the
reading's `talk` target, found in the room.
"""
from __future__ import annotations

import re

STAGE = "beat"
ORDER = 40

_FAMILY = {"he": "man", "him": "man", "his": "man", "himself": "man",
           "she": "woman", "her": "woman", "hers": "woman", "herself": "woman"}
_TO_MAN = {"she": "he", "hers": "his", "herself": "himself"}
_TO_WOMAN = {"he": "she", "him": "her", "his": "her", "himself": "herself"}
_PRONOUN = re.compile(r"\b(he|him|his|himself|she|her|hers|herself)\b"
                      r"(?P<tail>'s|'d|'ll|’s|’d|’ll)?", re.I)
# After "her", these words mean it is the object ("ask her what …"), not a possessive.
_OBJECT_NEXT = frozenset({
    "what", "where", "why", "how", "who", "whether", "if", "to", "for", "about", "and",
    "or", "a", "an", "the", "that", "this", "again", "directly", "once", "more", "some",
    "any", "in", "on", "at", "with", "by", "from", "out", "up", "down", "back", "away",
    "off", "over", "into", "if", "when", "while", "as", "so", "but", "too", "now", "then",
    "here", "there", "anything", "something", "everything", "nothing", "one", "my",
})


def _unquoted_spans(text: str) -> list[tuple[int, int]]:
    """Where the suggestion is the player's narration, not words they quote."""
    spans, start, inside = [], 0, False
    for i, ch in enumerate(text):
        if ch in "\"“”":
            if not inside:
                spans.append((start, i))
            else:
                start = i + 1
            inside = not inside
    if not inside:
        spans.append((start, len(text)))
    return spans


def _dealing(ctx):
    scene = ctx.scene
    actors = getattr(scene, "actors", {}) or {}
    talking = [actors[r] for r in (ctx.talking_after or ()) if r in actors]
    if len(talking) == 1:
        return talking[0]
    speakers = [str(r.get("who") or "") for r in ctx.said or ()
                if str(r.get("to") or "") == "you" and str(r.get("who") or "") in actors]
    if speakers:
        return actors[speakers[-1]]
    from rules import scope as scope_mod

    for a in (ctx.reading or {}).get("actions") or []:
        if a.get("act") == "talk" and a.get("target"):
            ref = scope_mod.in_the_room(scene, str(a["target"]))
            if ref:
                return actors[ref]
    return None


def _on_page(ctx) -> list[str]:
    """The genders of the people a suggestion can mean: everybody present whom this beat
    put on the page — a speaker, the person in conversation, somebody the attribution
    bound, somebody named or described by their head noun — and anybody unembodied the
    population holds at this place whose words the page used. "" for a person whose
    gender nobody has set: they could be either, so they fit either.

    A keeper at the back of the market, never mentioned, is not whom "I ask her…" means:
    measured on the playtest, the market's keeper stood in the room while the only person
    on the page was Drenn."""
    from gm.checks._people import head_of
    from rules import person_words

    scene = ctx.scene
    actors = getattr(scene, "actors", {}) or {}
    text = str(ctx.text or "").lower()
    refs = {str(r.get("who") or "") for r in ctx.said or ()}
    refs |= set(ctx.talking_after or ())
    for m in getattr(ctx.attribution, "mentions", None) or ():
        if getattr(m, "ref", None):
            refs.add(m.ref)
    for ref, a in actors.items():
        for name in (str(a.name or ""), str(getattr(a, "true_name", "") or "")):
            head = head_of(name).lower() if name else ""
            if head and re.search(rf"\b{re.escape(head)}\b", text):
                refs.add(ref)
    genders = [str(getattr(actors[r], "gender", "") or "").lower() for r in refs
               if r in actors and not getattr(actors[r], "is_pc", False)]
    at = getattr(scene, "at", None)
    for rec in (getattr(scene, "population", {}) or {}).values():
        if rec.get("ref") or at not in (rec.get("spot"), rec.get("seen_at")):
            continue
        head = head_of(rec.get("phrase", "")).lower()
        if head and re.search(rf"\b{re.escape(head)}\b", text):
            genders.append(person_words.from_words(rec.get("phrase", ""))["gender"])
    # And anybody the beat itself spoke of by that pronoun, here or not. Measured live on
    # the merged structured-turn branch (2026-10-03): the smith said "There is a woman who
    # operates near the old tannery. She is discreet…", the suggestion read "I ask her
    # name or where exactly she is located", and with the smith the only one present it
    # was rewritten to "I ask his name or where exactly he is located" — the fence turned
    # into the smith. A pronoun the beat just used means whoever the beat used it for;
    # this step cannot tell who that is, so it leaves the suggestion alone.
    for m in _PRONOUN.finditer(text):
        genders.append(_FAMILY[m.group(1).lower()])
    return genders


def _fits(family: str, genders: list[str]) -> bool:
    return any(g in (family, "") for g in genders)


def _swap(word: str, tail: str, to: str, following: str) -> str:
    low = word.lower()
    if to == "man":
        if low == "her":
            new = "him" if (following in _OBJECT_NEXT or not following) else "his"
        else:
            new = _TO_MAN.get(low, low)
    else:
        new = _TO_WOMAN.get(low, low)
    if word[:1].isupper():
        new = new[:1].upper() + new[1:]
    return new + (tail or "")


def repair(text: str, genders: list[str], dealing) -> tuple[str | None, bool]:
    """(the suggestion, changed). None when it cannot be squared and must go: the pronoun
    fits nobody on the page and the person the player is dealing with has no pronouns
    set to give it."""
    changed = False
    target = str(getattr(dealing, "gender", "") or "").lower() if dealing is not None else ""
    out, last = [], 0
    for start, end in _unquoted_spans(text):
        for m in _PRONOUN.finditer(text, start, end):
            family = _FAMILY[m.group(1).lower()]
            if _fits(family, genders):
                continue
            if target not in ("man", "woman") or target == family:
                return None, False
            nxt = re.match(r"\s*([A-Za-z']+)", text[m.end():])
            following = nxt.group(1).lower() if nxt else ""
            out.append(text[last:m.start()])
            out.append(_swap(m.group(1), m.group("tail") or "", target, following))
            last = m.end()
            changed = True
    out.append(text[last:])
    return "".join(out), changed


def step(ctx) -> list[dict]:
    campaign = ctx.campaign
    suggestions = list(getattr(campaign, "suggestions", None) or [])
    if not suggestions:
        return []
    dealing = _dealing(ctx)
    genders = _on_page(ctx)
    kept, rows = [], []
    for s in suggestions:
        text = s if isinstance(s, str) else str((s or {}).get("text") or "")
        fixed, changed = repair(text, genders, dealing)
        if fixed is None:
            rows.append({"kind": "suggestion-pronoun", "before": text, "after": ""})
            continue
        if changed:
            rows.append({"kind": "suggestion-pronoun", "before": text, "after": fixed})
            kept.append(fixed if isinstance(s, str) else dict(s, text=fixed))
        else:
            kept.append(s)
    if rows:
        campaign.suggestions = kept
    return rows
