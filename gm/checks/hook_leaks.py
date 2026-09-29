"""A quest-giver's lines that give away the hook: the secret on the page, or the giver asking
the player for the answer to their own quest.

Measured on the 2026-09-28 playtest (item 12, turn 4): Drenn Ironvale, the giver of "Find
Drenn Ironvale's lost Power leaf", said "Tell me, do you have any idea where such a thing
might be hidden?" — asking the player where his own leaf is, which is the quest's own
information turned into a question (the pull had given him the open objective and nothing
else to say). The same line's "lost not through carelessness" was traced to the scheme's
open grant, not the secret card (fix-interfaces §1.5 D2) — that path is closed in the
scheme itself; this check keeps the secret card's own path closed too.

  * `hook-secret-on-page` (weight 3): two or more DISTINCTIVE identity words of the
    scheme's secret card — its identity keys, minus the visible card's — in a giver's line.
    What the narrator is not told it cannot tell (the hidden-facts ruling, 2026-09-25);
    this is the net under that.
  * `giver-asks-own-answer` (weight 2): a giver's line asks a question (where, hidden,
    find) about the lost thing or the objective's place.
"""
from __future__ import annotations

import re

from gm.narration import Finding

ORDER = 62
KINDS = frozenset({"hook-secret-on-page", "giver-asks-own-answer"})
DOORS = frozenset({"turn", "npc"})

_ASKS = re.compile(r"\b(?:where|hidden|hide|hid|find|found|seen|know)\b", re.I)


def _hits(keys, line: str) -> list[str]:
    low = str(line or "").lower()
    return [k for k in keys if re.search(r"\b" + re.escape(k) + r"\w{0,2}\b", low)]


def _secret_keys(scene, card_id: str) -> list[str]:
    """The distinctive identity words of the secret cards that share a scheme with this
    card: theirs, minus the visible card's."""
    from rules import cards

    visible = cards.find(scene, card_id)
    if visible is None:
        return []
    mine = set(cards.identity_keys(visible, cards._card_names(visible, scene)))
    out: list[str] = []
    for inst in getattr(scene, "schemes", None) or []:
        ids = list((inst.get("cards") or {}).values())
        if card_id not in ids:
            continue
        for cid in ids:
            c = cards.find(scene, cid)
            if c is None or not c.secret:
                continue
            for k in cards.identity_keys(c, cards._card_names(c, scene)):
                if k not in mine and k not in out:
                    out.append(k)
    return out


def _question_sentences(line: str) -> list[str]:
    return [s for s in re.split(r"(?<=[.!?])\s+", str(line or "")) if s.strip().endswith("?")]


def find(ctx) -> list:
    from gm.checks import _sought

    pull = ctx.pull or {}
    if not pull or not pull.get("id"):
        return []
    refs = _sought.people_refs(ctx, pull.get("people") or ())
    giver = (pull.get("giver") or {}).get("ref")
    if giver:
        refs.add(str(giver))
    lines = _sought.lines_by(ctx, refs)
    if not lines:
        return []
    out = []
    secret = _secret_keys(ctx.scene, str(pull["id"]))
    for line in lines:
        hit = _hits(secret, line)
        if len(hit) >= 2:
            out.append(Finding(
                "hook-secret-on-page",
                f"the giver's line carries the GM's secret ({', '.join(hit)}): {line[:120]!r}",
                "Cut what the giver says about the secret; they say only what they want, "
                "why, and what they offer.", weight=3, sentences=(line,)))
    # The quest's own information: the open objective's words, less the verbs of doing it.
    want = [k for k in (pull.get("keys") or [])
            if k not in ("search", "find", "bring", "back", "return", "take", "ask")]
    want = [k for k in want if not any(k in str(n).lower() for n in pull.get("people") or ())]
    for line in lines:
        for q in _question_sentences(line):
            if not _ASKS.search(q):
                continue
            # The question itself, or the line it closes, names the thing or its place.
            if _hits(want, q) or (_hits(want, line) and re.search(
                    r"\b(?:such a thing|it|that)\b", q, re.I)):
                out.append(Finding(
                    "giver-asks-own-answer",
                    f"the giver asks the player for their own quest's answer: {q[:120]!r}",
                    "The giver does not know where it is — that is why they need the "
                    "player. They say what they want found and what they offer; they do not "
                    "ask the player where it is.", weight=2, sentences=(line,)))
                break
    return out
