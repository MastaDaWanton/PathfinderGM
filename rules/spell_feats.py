"""Feat loop batch 5, lane b5-spells (2026-11-26): the questions this lane's feats ask that no
reader answered yet, each asked of the documents and the vocabulary, never of a feat's name.

- Who cast it: Schooled Resolve's "mind-affecting spells and effects from vampires" is a
  save `against` "vampire_mind" (`save_words`), added beside the spell's own words where
  the cast's and the creature's saves already add Witchbreaker's "hag_or_witch".

Text read on aonprd.com FeatDisplay pages 2026-11-26.
"""
from __future__ import annotations

VAMPIRE_MIND = "vampire_mind"


def is_vampire(actor) -> bool:
    """A vampire by its stat block (`vampire`, `vampire-lord`, `enlightened-vampire` ...):
    the bestiary's own family, as Witchbreaker's hags are found (`feat_events`)."""
    if actor is None:
        return False
    getter = getattr(actor, "_creature_doc", None)
    doc = getter() if callable(getter) else None
    return _doc_is_vampire(doc or {})


def _doc_is_vampire(doc: dict) -> bool:
    cid = str(doc.get("id") or "").strip().lower()
    return cid == "vampire" or cid.startswith("vampire-") or cid.endswith("-vampire")


def origin_is_vampire(origin) -> bool:
    text = str(origin or "")
    if not text.startswith("creature:"):
        return False
    from . import bestiary

    return _doc_is_vampire(bestiary.raw(text.split(":", 1)[1]) or {})


def save_words(words, *, caster=None, origin="") -> tuple[str, ...]:
    """`words` (what a save is against) with "vampire_mind" added when the effect is
    mind-affecting and a vampire's — its cast, or its own ability by the origin stamp."""
    words = (words,) if isinstance(words, str) else tuple(words or ())
    # "This does not stack with the normal bravery bonus on saves against fear effects":
    # a vampire's fear effect is bravery's alone, which is the same number once.
    if "mind-affecting" in words and "fear" not in words and (
            is_vampire(caster) or origin_is_vampire(origin)):
        return words + (VAMPIRE_MIND,)
    return words
