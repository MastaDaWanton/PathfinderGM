"""The page as the truth checks read it — a helper, not a check.

Two things every check in this package needs and none should copy:

  * **the sentences, as they stand on the page.** A finding names the sentences it flags
    (`Finding.sentences`), and the repair replaces exactly those strings in the beat, so
    they must be the page's own — quotation marks, speech and all. The checks read the
    narration only (a character may say anything), so each sentence comes with its
    narration beside it: the same slice of `speech.blanked`, which turns speech to spaces
    and keeps every offset. Cutting the sentences out of `speech.unquoted` instead would
    give strings that are not on the page, and a `replace` that silently does nothing —
    the failure `_repair_outcome_claims` records learning once already.
  * **the engine's records, read the same way whether an outcome arrived as an
    `Outcome` or as its saved dict** (the replay corpus holds dicts).
"""
from __future__ import annotations

import re


def page_sentences(text: str) -> list[tuple[str, str]]:
    """(the sentence as written, its narration with speech blanked), in order."""
    from gm import speech
    from gm.narration import _SENTENCE

    text = str(text or "")
    blank = speech.blanked(text)
    out: list[tuple[str, str]] = []
    for m in _SENTENCE.finditer(blank):
        s, e = m.span()
        written = text[s:e].strip()
        if written:
            out.append((written, " ".join(blank[s:e].split())))
    return out


def field(o, key: str, default=None):
    """One field of an outcome, an `Outcome` or its dict."""
    if isinstance(o, dict):
        return o.get(key, default)
    return getattr(o, key, default)


def effects(o) -> list[dict]:
    return [e for e in (field(o, "effects") or []) if isinstance(e, dict)]


MOVE_OPS = frozenset({"travel", "journey", "venture", "found"})


def moved(ctx) -> bool:
    """Whether anything this turn changed where the party stands: a resolved move whose
    effect lands somewhere other than where it left, or the scene simply standing
    somewhere else than the turn began."""
    if str(getattr(ctx.scene, "at", "") or "") != str(ctx.was_at or ""):
        return True
    for o in ctx.outcomes:
        if field(o, "op") not in MOVE_OPS or field(o, "status") == "refused":
            continue
        for e in effects(o):
            if e.get("place") and e.get("place") != e.get("was_place"):
                return True
            if field(o, "op") == "journey" and e.get("kind") in ("journey", "arrived"):
                return True
    return False


def refused_moves(ctx) -> list:
    return [o for o in ctx.outcomes
            if field(o, "op") in MOVE_OPS and field(o, "status") == "refused"]


def here_name(ctx) -> str:
    """The name of the place the party stands in now, as the engine holds it."""
    try:
        here = ctx.engine.here()
    except Exception:  # noqa: BLE001 — a check with no engine answer reads no place
        here = None
    return str(getattr(here, "name", "") or "")


def cut(text: str, sentences) -> str:
    """`text` without the given sentences (as written), spacing tidied."""
    for s in sentences:
        if s and s in text:
            text = text.replace(s, "", 1)
    return re.sub(r"[ \t]{2,}", " ", text).strip()


def cut_from(text: str, sentence: str) -> str:
    """`text` up to the given sentence — everything after it is the walk the engine
    never made (`narration.hold_the_door`'s shape)."""
    at = text.find(sentence) if sentence else -1
    return text if at < 0 else text[:at].rstrip()
