"""fighter-not-in-fight: in a fight, somebody the engine does not hold fights on the page.

Measured live 2026-10-17 (integration branch, free narrator, gemma-4-12B): the player and
the one behind the bar were the only people in the inn, and the beat after the player's
dagger hit read "The other man, his eyes wide with shock, hesitates for a heartbeat before
lunging toward you, his hands out like claws." Nothing caught it:

  * the read back (`beat_verified`) ran on that beat and claimed nothing of him — its
    vocabulary judges a person it has a code for, and "someone not listed" is never
    judged (an `attacks` slot was tried there and taken out: it cost harm claims 12/14 ->
    8/14, docs/beat-verify.md);
  * the beat reader DID read him: a newcomer, "other man", here — and the aftermath
    rightly made nobody of him ("in a fight the prose brings nobody in",
    play/aftermath/seen_people.py). So he was never an actor, and stayed on the page as a
    phantom fighter lunging at the player, with the suggestions offering "I strike the man
    lunging at me".

What is detected, by structure: the scene is in a fight (`scene.in_encounter`), and the
beat reader's closed answer for a person mention is "new" and "here" — a person the
engine does not hold, standing in the scene — or the code of somebody the engine holds
elsewhere in town. Code never reads the English. Whether that
person FIGHTS in the sentence — attacks, lunges, strikes, grabs, blocks — or only watches,
shouts, flinches or flees is one closed question to the narrator's own model about that
one sentence (`beat_verify.ask`, the read back's second-read shape), because a crowd
reacting to a fight is fair prose and a fighter the engine never rolled is not.

Repair is the cut, never a rewrite (`REWRITE = False`): the re-check after a rewrite would
read the reader's mentions of the OLD sentence, find none, and pass a rewrite that still
has him lunging. The sentence goes; the engine's own blows are on the page through the
blow pass (`GMAgent._show_blows`).

With the reader off or unread (the suite, a failed call) this member finds nothing: no
reading, no claim, and nothing guessed in its place.
"""
from __future__ import annotations

from gm.narration import Finding

ORDER = 11
KINDS = frozenset({"fighter-not-in-fight", "hand-back-names-nobody"})
DOORS = frozenset({"plan", "turn", "npc", "outcome"})
REWRITE = False

# How many mention sentences one beat may ask about: a fight beat with more newcomers than
# this is a narrator inventing a crowd, and the first few carry the defect.
MAX_ASKS = 3

# The asked questions, (sentence key, words) -> fights. `_repair_sentences` asks `find`
# again before the backstops; an answered sentence must not cost the question twice.
_ASKED: dict[tuple, bool] = {}


def question(words: str) -> str:
    """Asked of the fighting, with the bystander's reactions named as what it is not.

    Measured 2026-10-17, gemma-4-12B at temperature 0, on the 21 newcomer sentences the
    beat reader found in 144 recorded fight-file beats (tests/replay *fight*, every beat
    treated as a fight) plus the live lunge and four made sentences, two asks each with
    the sentence before as context. Without "{words} themselves" and "not only being
    attacked or grabbed", "It doesn't wait for the guards; it lunges forward to grab the
    intruder" was the INTRUDER fighting, 2 of 2 — the one being grabbed. With them, 0 of
    2; the live lunge, "A local laborer lunges forward … as he prepares to strike you",
    "A desperate stranger lunges toward him", a dockhand's boathook and a barmaid
    grabbing your arm 2 of 2 each; a lout nursing a mug, a watchman rounding the corner,
    a man pinned under a table, a woman screaming and backing away, a patron shouting for
    the watch 0 of 2 each."""
    return (f"Does this sentence show {words} fighting — {words} themselves attacking, "
            f"lunging or charging at, striking, grabbing, or blocking somebody, or swinging "
            f"or drawing a weapon on them — not only being attacked or grabbed, watching, "
            f"shouting, flinching, backing away, fleeing or standing by?")


def _words(m) -> str:
    phrase = " ".join(str(m.phrase or "").split())
    # "The man's face buckles" names "The man", not "The man's" (live, 2026-10-17).
    for tail in ("'s", "’s"):
        phrase = phrase.removesuffix(tail)
    low = phrase.lower()
    if low.startswith(("the ", "a ", "an ")):
        return phrase
    return f"the {phrase}" if phrase[:1].islower() else phrase


def candidates(ctx) -> list[tuple[str, str, str]]:
    """(the page sentence as written, the reader's words for the newcomer, the sentence
    before it) for every mention the beat reader answered "new" and "here", whose
    sentence is still on the page, in a fight. Structure only."""
    from gm import beat_reader, mentions

    from ._page import page_sentences

    if not bool(getattr(ctx.scene, "in_encounter", False)):
        return []
    reading = ctx.attribution
    if not isinstance(reading, beat_reader.Reading) or not reading.read:
        return []
    page = page_sentences(ctx.text)
    keys = [mentions._key(w) for w, _n in page]
    out: list[tuple[str, str, str]] = []
    # The newcomers here, and the mentions the reader gave to somebody the engine holds
    # ELSEWHERE in town (`Reading.away`): on the replay of the live beat the same "The
    # other man" came back "new" twice and as the away guard (c6) once. Neither is in
    # this fight; the second read decides whether the sentence has them fight.
    asked = [mid for n in reading.newcomers if n.where == beat_reader.HERE
             for mid in n.mentions]
    asked += [m.id for m in reading.mentions
              if m.ref and m.ref in (reading.away or ()) and m.id not in asked]
    for mid in asked:
        m = reading.mention(mid)
        if m is None:
            continue
        k = mentions._key(m.sentence)
        if k not in keys:
            continue
        at = keys.index(k)
        row = (page[at][0], _words(m), page[at - 1][0] if at > 0 else "")
        if row not in out:
            out.append(row)
    return out[:MAX_ASKS]


def hand_back_naming_nobody(ctx) -> str:
    """The beat's closing question, when it names somebody the engine does not hold here
    in a fight — a mention the beat reader answered "new" and here, or gave to somebody
    held elsewhere — or "". Structure only: the reader's closed answer, and the question
    being the page's last sentence.

    Measured live 2026-10-17 (integration branch, gemma-4-12B): the fighting sentence of
    "the other man" was cut, and the beat still closed "Do you turn to face the second man
    or move for the exit?" — the reader's newcomer "second man", here. A choice offered on
    nobody: he has no body in a fight, so whatever the player answers acts on air, and the
    phantom comes back next beat from the player's own words. Not asked of the model:
    whether the question has him fight does not matter, only that it offers him."""
    from gm import beat_reader, mentions

    from ._page import page_sentences

    if not bool(getattr(ctx.scene, "in_encounter", False)):
        return ""
    reading = ctx.attribution
    if not isinstance(reading, beat_reader.Reading) or not reading.read:
        return ""
    page = page_sentences(ctx.text)
    if not page or not page[-1][0].rstrip().endswith("?"):
        return ""
    last = page[-1][0]
    nobody = {mid for n in reading.newcomers if n.where == beat_reader.HERE
              for mid in n.mentions}
    nobody |= {m.id for m in reading.mentions if m.ref and m.ref in (reading.away or ())}
    for m in reading.mentions:
        if m.id in nobody and mentions._key(m.sentence) == mentions._key(last):
            return last
    return ""


def find(ctx) -> list:
    from gm import beat_verify, mentions

    route = dict(getattr(ctx, "reader", None) or {})
    if not beat_verify.ENABLED or not route.get("model"):
        return []
    out = []
    asked = hand_back_naming_nobody(ctx)
    if asked:
        out.append(Finding(
            "hand-back-names-nobody",
            f"the closing question offers somebody the engine does not hold in this fight: "
            f"{asked[:90]!r}",
            "The closing question names somebody who is not in this fight. Ask only about "
            "the people the engine holds.", weight=3, sentences=(asked,)))
    for sentence, words, before in candidates(ctx):
        key = (mentions._key(sentence), words)
        if key not in _ASKED:
            _ASKED[key] = beat_verify.ask(sentence, question(words), before=before,
                                          model=route.get("model", ""),
                                          host=route.get("host", ""),
                                          provider=route.get("provider") or "ollama",
                                          api_key=route.get("api_key", ""))
        while len(_ASKED) > 256:
            _ASKED.pop(next(iter(_ASKED)))
        if not _ASKED[key]:
            continue
        out.append(Finding(
            "fighter-not-in-fight",
            f"{words} fights on the page, and the engine holds nobody of that description "
            f"in this fight: {sentence[:90]!r}",
            f"Nobody but the people the engine holds is in this fight. {words} is not one "
            f"of them and does nothing in it. Remove what {words} does.",
            weight=3, sentences=(sentence,)))
    return out


def backstop(ctx, text: str, findings) -> tuple[str, list[str]]:
    """The sentences still on the page go. A cut closing question is put back as the
    plain hand-back by the groom (`narration.ensure_hand_back`), on the doors that hand
    back at all."""
    from ._page import cut

    notes = []
    for f in findings:
        what = ("a question about nobody here" if f.kind == "hand-back-names-nobody"
                else "fighter not in the fight")
        for s in f.sentences:
            if s and s in text:
                text = cut(text, [s])
                notes.append(f"{what}: cut {s[:70]!r}")
    return text, notes
