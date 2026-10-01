"""person-not-there: the page puts a person at a place where nobody is.

Measured live on 2026-09-29 (the caravan start, docs/fix-interfaces.md, the deferred row
"an arrival narrates a person who is not there"): Borin withdrew to the crossroads, and
the scene held only the PC — no actor there, no population record — while the arrival
prose put "a team of pack-mules … being unloaded by a laborer who is currently
struggling with a heavy crate of timber. The man wipes sweat from his brow … and looks up
as you approach". A silent, unnamed person placed and looking at the player passed every
check: Q5 gives a body only to a SPEAKER matched to this beat's record, and the
population books a phrase without asking whether the place had anybody in it.

What is detected, in code: a described person — a determiner and a person noun, "a
laborer", "the man" — doing something in the present tense toward the player ("looks up
as you approach", "watches you", "nods to you"), at a place that holds nobody: no actor
here but the party, and no population record at this spot. A town's square with people
already in it is not this: a nameless figure in a crowd is fair prose
(docs/nobody-is-invented.md), and the check stands aside wherever the engine already
holds somebody.

The repair is the house shape: one targeted rewrite of the flagged sentence with the
fact named (nobody is here), kept only if this check no longer finds it; else the
backstop cuts the sentence and the ones that carry the person on by pronoun ("He wipes
his brow…").
"""
from __future__ import annotations

import re

from gm.narration import Finding

ORDER = 64
KINDS = frozenset({"person-not-there"})
DOORS = frozenset({"turn"})

# Present-tense acts that are toward somebody: a gaze, a gesture, a greeting, an
# approach. "looks", "watches" and "turns" need the player after them in the sentence.
_ACTS = (r"looks?|glances?|watches|eyes|stares|studies|regards|notices|spots|nods|"
         r"waves|beckons|calls|greets|smiles|grins|frowns|scowls|turns|approaches|"
         r"steps|straightens|pauses|stops|squints|raises|lifts|tips|doffs|hails|"
         r"addresses|gestures|points|shouts|whistles")
_THE = r"(?:a|an|the|one|another|some|this|that)"


def _person_re():
    from gm import speech
    from gm.checks._people import _PERSON

    heads = sorted(set(_PERSON) - set(speech._COLLECTIVE)
                   - {"beast", "creature", "monster", "animal", "horror", "fiend"},
                   key=len, reverse=True)
    return re.compile(r"\b" + _THE + r"\s+(?:[a-z'’-]+\s+){0,3}?(?P<head>"
                      + "|".join(re.escape(h) for h in heads) + r")\b(?!-)", re.I)


_YOU = re.compile(r"\b(?:you|your|yourself)\b", re.I)
_ACT_RE = re.compile(r"\b(?:" + _ACTS + r")\b", re.I)
_PRONOUN_SUBJECT = re.compile(r"^\s*(?:He|She|They)\b")


def _nobody_here(scene) -> bool:
    here = getattr(scene, "at", None)
    if any(not a.is_pc and not a.has_state("state.hidden") and a.hp > 0
           for a in (getattr(scene, "actors", {}) or {}).values()):
        return False
    return not any(str(rec.get("spot") or "") == str(here or "")
                   for rec in (getattr(scene, "population", None) or {}).values())


def _acts_toward_you(narration: str) -> bool:
    act = _ACT_RE.search(narration)
    return bool(act) and bool(_YOU.search(narration[act.start():]))


def placed_toward_you(narration: str) -> str:
    """The person noun of a described person acting toward the player in this sentence
    (narration only, speech blanked), or ""."""
    m = _person_re().search(narration)
    if not m:
        return ""
    after = narration[m.end():]
    act = _ACT_RE.search(after)
    if not act or not _YOU.search(after[act.start():]):
        return ""
    return m.group("head").lower()


def find(ctx) -> list:
    from gm.checks._page import page_sentences

    scene = ctx.scene
    if getattr(scene, "in_encounter", False) or not _nobody_here(scene):
        return []
    pairs = page_sentences(ctx.text)
    out = []
    taken: set[int] = set()
    for i, (written, narration) in enumerate(pairs):
        if i in taken:
            continue
        head = placed_toward_you(narration)
        flagged = [written]
        anaphoric = bool(head) and bool(re.match(
            r"(?:the|this|that)\b", _person_re().search(narration).group(0), re.I))
        if not head and _PRONOUN_SUBJECT.match(narration) and _acts_toward_you(narration):
            # "He wipes sweat from his brow … and looks up as you approach": the person
            # is the one the nearest sentence before described.
            back = next((k for k in range(i - 1, -1, -1)
                         if _person_re().search(pairs[k][1])), None)
            if back is None:
                continue
            head = _person_re().search(pairs[back][1]).group("head").lower()
            flagged = [pairs[k][0] for k in range(back, i + 1)
                       if k == back or k == i or _PRONOUN_SUBJECT.match(pairs[k][1])]
        elif anaphoric:
            # "The man … looks up as you approach" is anaphoric: the person was brought
            # on earlier, "by a laborer who is currently struggling with a heavy crate".
            # The nearest sentence before that brings somebody on with an indefinite
            # article goes with it, or the cut leaves the laborer standing there.
            for back, nar in reversed(pairs[:i]):
                intro = _person_re().search(nar)
                if intro and re.match(r"(?:a|an|one|another|some)\b", intro.group(0), re.I):
                    flagged.insert(0, back)
                    break
        if not head:
            continue
        # The sentences after it that carry the same person on by pronoun, up to the
        # first that describes somebody else.
        for k in range(i + 1, len(pairs)):
            later, nar = pairs[k]
            if _person_re().search(nar) or not _PRONOUN_SUBJECT.match(nar):
                break
            flagged.append(later)
            taken.add(k)
        from gm.checks._page import here_name

        where = here_name(ctx) or "this place"
        out.append(Finding(
            "person-not-there",
            f"the page puts a {head} at {where}, acting toward the player, and nobody is "
            f"there: {written[:120]!r}",
            f"Nobody is at {where} but the party: there is no {head} here. Write this "
            f"without any person in it — the place itself, what lies on the ground, what "
            f"can be heard.",
            weight=2, sentences=tuple(flagged)))
    return out


def backstop(ctx, text: str, findings) -> tuple[str, list[str]]:
    """Cut the flagged sentences that still stand."""
    from gm.checks._page import cut

    gone = [s for f in findings if f.kind in KINDS for s in f.sentences if s in text]
    if not gone:
        return text, []
    return cut(text, gone), [f"person-not-there: cut {s[:80]!r}" for s in gone]
