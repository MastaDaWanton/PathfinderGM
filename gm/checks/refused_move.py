"""A move the engine refused, narrated as a move that happened (item 17.5).

Measured on the Bobby playtest, 2026-09-28. "I walk to the nearest crossroads" and "I
take the path away from town": `found` and `travel` were refused both times, the party
stood at the way in both times, and the page said "You are standing where the paths
diverge" and "You are now on the outskirts". The only check that fired caught the word
"gate". Every later turn resolves from where the engine holds the party, so a page that
moves them anyway is wrong for the rest of the session — the highest-priority truth check.

Inform's order is the model (WI §12.2, §12.9): a check that fails says why and stops the
action, and the report rule that describes a move is never reached. Here the report is a
model's prose, so it is reached, and this check is the stop: detect the move claim in
code, ask for one rewrite of those sentences with the refusal named, and, if the rewrite
still moves the player, cut the beat from the first move claim and let the refusal's own
sentence stand (`hold_the_door`'s shape).

What counts as a claim is the second person being put somewhere: "you are (now) on / at /
in / standing where…", "you reach / arrive / emerge", "you walk / head / set off / turn
your back on…". Only the verb immediately after "you", so "you could walk", "you will
reach" and "you do not reach" are never claims; a question is never one. A phrase naming
the place the party is actually in is no displacement. World-agnostic: the only place
name read is the engine's own `here()`.
"""
from __future__ import annotations

import re

from gm.narration import Finding

from ._page import field, here_name, moved, page_sentences, refused_moves

ORDER = 10
KINDS = frozenset({"refused-move-shown-as-moved"})
DOORS = frozenset({"plan", "turn"})

# Somewhere is being stood in. The complement must open like a place — a determiner or
# "where" — so "you are in no hurry" and "you are at ease" are not places.
_POSITION = re.compile(
    r"\byou(?:'re|\s+are|\s+stand|\s+find\s+yourself|\s+now\s+stand)\s+"
    r"(?:now\s+|finally\s+|already\s+)?(?:standing\s+|waiting\s+|left\s+)?"
    r"(?P<prep>on|at|in|inside|outside|beyond|among|upon|near|before|where)\b"
    r"(?P<rest>[^.!?;]*)", re.I)
_PLACE_OPENS = re.compile(r"^\s*(?:the|a|an|this|that|these|those)\b", re.I)
# Not places, though they open like one: states and stances.
_NOT_A_PLACE = re.compile(
    r"^\s*(?:the|a|an|this|that)\s+(?:\w+\s+)?(?:way|mood|hurry|position|state|debt|"
    r"trouble|danger|luck|charge|doubt|moment|middle\s+of\s+(?:a|the)\s+(?:conversation|"
    r"sentence|thought)|presence|company|care|habit|dark\s+about)\b", re.I)
_ARRIVE = re.compile(
    r"\byou\s+(?:finally\s+|soon\s+|at\s+last\s+)?(?:reach|arrive|emerge|step\s+out|"
    r"come\s+out|come\s+to\s+(?:a|the)\s+(?:stop|halt)\s+(?:at|beside|before))\b", re.I)
_LEAVE = re.compile(
    r"\byou\s+(?:walk|head|set\s+off|set\s+out|make\s+your\s+way|leave|stride|"
    r"strike\s+out|start\s+down|follow\s+the\s+(?:road|path|track|lane)|"
    r"turn\s+your\s+back\s+(?:on|to))\b(?P<rest>[^.!?;]*)", re.I)
_DIRECTIONAL = re.compile(
    r"\b(?:toward|towards|to|into|out|away|along|down|up|past|beyond|through|north|"
    r"south|east|west|behind|off|across|onto)\b", re.I)


def _names_here(rest: str, here: str) -> bool:
    words = [w for w in re.findall(r"[a-z']+", here.lower())
             if w not in ("the", "a", "an", "of")]
    return bool(words) and all(re.search(rf"\b{re.escape(w)}\b", rest.lower())
                               for w in words)


def claims(narration: str, here: str) -> bool:
    """Whether one sentence of narration moves the player somewhere."""
    if "?" in narration:
        return False
    for m in _POSITION.finditer(narration):
        rest = m.group("rest")
        if m.group("prep").lower() != "where" and (not _PLACE_OPENS.search(rest)
                                                   or _NOT_A_PLACE.search(rest)):
            continue
        if here and _names_here(rest, here):
            continue
        return True
    if _ARRIVE.search(narration):
        return True
    for m in _LEAVE.finditer(narration):
        rest = m.group("rest")
        if here and _names_here(rest, here):
            continue
        verb = m.group(0).lower()
        if (_DIRECTIONAL.search(rest) or "turn your back" in verb
                or re.search(r"\byou\s+leave\b", verb)):
            return True
    return False


def _applies(ctx) -> bool:
    if moved(ctx):
        return False
    if refused_moves(ctx):
        return True
    acts = (ctx.reading or {}).get("actions") or [] if isinstance(ctx.reading, dict) else []
    return any(isinstance(a, dict) and a.get("act") in ("go", "leave") for a in acts)


def refusal_words(ctx) -> str:
    """The refusal in words a player reads: the outcome's own `for_a_person` when the
    refusing rule wrote one. Today's refused-move tells are written for the planner
    ("The kinds are: arena, back streets…") and cannot stand on the page, so without one
    the sentence is the engine's plain fact: where the party still is."""
    for o in refused_moves(ctx):
        said = str(field(o, "for_a_person") or "").strip()
        if said:
            return said
    return ""


def find(ctx) -> list:
    if not _applies(ctx):
        return []
    here = here_name(ctx)
    flagged = [w for w, n in page_sentences(ctx.text) if claims(n, here)]
    if not flagged:
        return []
    why = refusal_words(ctx) or "nothing the engine resolved moved them"
    where = f"They are still at {here}." if here else "They are still where they were."
    return [Finding(
        "refused-move-shown-as-moved",
        f"the player did not move ({why}), and the prose moves them: {flagged[0][:90]!r}",
        f"The player did not move: {why}. {where} Rewrite the sentence so they are "
        f"still there — they may look, reach or want to go, but they have not gone.",
        weight=4, sentences=tuple(flagged))]


def backstop(ctx, text: str, findings) -> tuple[str, list[str]]:
    """Cut the beat from the first sentence that still moves the player — everything
    after it is a walk the engine never made — and end on the fact."""
    from ._page import cut_from

    here = here_name(ctx)
    first = next((w for w, n in page_sentences(text) if claims(n, here)), "")
    if not first:
        return text, []
    kept = cut_from(text, first)
    line = refusal_words(ctx) or (f"You are still at {here}." if here else "")
    if line:
        kept = f"{kept} {line}".strip()
    return kept, [f"refused move: cut the beat from {first[:60]!r}"]
