"""A beat set in a different KIND of place from the one the party stands in (item 12).

Measured on the owner's market-talk save, 2026-10-03. The engine held the party at the
market — open ground, stalls, awnings — for every turn of it, and the page wrote a
taproom round them: "the tavern patrons have stopped their drinking", "the man on the
stool … the man at the bar", "the air in the room feels thick", "He leans back against
the bar", "the heavy atmosphere of the tavern seems to press in on the two of you".

`stands-elsewhere` (gm/narration.py) did not fire, and could not: Zhilvarnia HAS a
tavern, so naming one is not an invention, and no sentence said "you are in the tavern".
It reads place NAMES; this beat never named where it stood. It furnished it. So this
check reads the furniture — the things only one kind of place has — against what the
engine says the party's place is (`places.words_for_here`, the same words the
refused-move and stands-elsewhere checks read):

  * a tavern's own fittings and people (patrons, the bar as something stood at, a
    barkeep, a taproom, a common room, tankards, the tavern going quiet round you) where
    the party's place is not a tavern or an inn, nor in one;
  * a room's (the room, the rafters, the ceiling) where the party's place has no roof
    (`places.is_indoors`, the floorplan's own answer — one source).

Narration only; a character may talk about any bar they like. A sentence that sets the
tavern at a distance — across the square, from the tavern, out of its door — is a view,
not a setting, and is left alone. Precision over recall, as everywhere in this package:
the cue words are the app's own place kinds' furniture, never the world's names, so it
runs unchanged on any export.

Repair: one targeted rewrite per sentence, naming where the party is; the backstop cuts a
sentence that still furnishes the wrong place. The opening that started this drift ("a
lit doorway with a room's noise behind it", with the party placed at the market) is put
right at the source in play/campaign.py — this is the net for the turns after.
"""
from __future__ import annotations

import re

from gm.narration import Finding

from . import _space

ORDER = 57
KINDS = frozenset({"wrong-kind-of-place"})
DOORS = frozenset({"plan", "turn", "npc", "outcome"})

_TAVERN_WORDS = frozenset({"tavern", "inn", "alehouse", "taproom"})
_TAVERN = re.compile(
    r"\b(?:(?:the\s+)?tavern\s+patrons|patrons|barkeep|barkeeper|barman|barmaid|tapster|"
    r"taproom|tap-room|common\s+room|tankards?|"
    r"(?:at|against|behind|along|across|to|on|from)\s+the\s+bar(?!\w)|"
    r"(?:atmosphere|air|noise|hush|din|warmth|smoke|fug|regulars|floor|silence|"
    r"stillness)\s+of\s+the\s+(?:tavern|inn|alehouse)|"
    r"the\s+(?:tavern|inn|alehouse)\s+(?:falls|fell|goes|went|grows|grew|has\s+gone)\s+"
    r"(?:silent|quiet|still))\b", re.I)
_ROOM = re.compile(r"\b(?:the\s+(?:room|rafters|ceiling|beams\s+overhead)|in\s+the\s+"
                   r"rafters)\b(?!['’]s\s+door)", re.I)
# The tavern seen from where you stand is a view, not a setting.
_AT_A_DISTANCE = re.compile(
    r"\b(?:across|beyond|opposite|down\s+the\s+(?:street|lane|row)|up\s+the\s+"
    r"(?:street|lane|row)|in\s+the\s+distance|from\s+(?:the|a)\s+(?:tavern|inn|alehouse)|"
    r"out\s+of\s+the\s+(?:tavern|inn|alehouse)|outside\s+the\s+(?:tavern|inn|alehouse)|"
    r"through\s+the\s+(?:door|window|doorway)|far\s+side)\b", re.I)


def _where(ctx):
    """(the place's name, its words, whether it has a roof), or None with no answer."""
    from rules import places

    try:
        here = ctx.engine.here()
        known = tuple(ctx.engine.places())
    except Exception:  # noqa: BLE001 — a check with no engine answer reads no place
        return None
    if here is None:
        return None
    words = {str(w).lower() for w in places.words_for_here(here, known)}
    try:
        roofed = places.is_indoors(here.id, getattr(here, "terrain", ""),
                                   getattr(here, "shape", None))
    except Exception:  # noqa: BLE001 — unknown roof: judge no room words
        roofed = True
    return str(here.name or ""), words, roofed


def cues_in(narration: str, words, roofed: bool) -> list[str]:
    """The wrong kind of place's furniture in a stretch of narration, as written."""
    if _AT_A_DISTANCE.search(narration):
        return []
    found: list[str] = []
    if not (set(words) & _TAVERN_WORDS):
        found += [" ".join(m.group(0).split()) for m in _TAVERN.finditer(narration)]
    if not roofed:
        found += [" ".join(m.group(0).split()) for m in _ROOM.finditer(narration)]
    return found


def flagged_in(sentence: str, words, roofed: bool) -> list[str]:
    from gm import speech

    return [c for is_speech, chunk in speech.split(sentence) if not is_speech
            for c in cues_in(chunk, words, roofed)]


def find(ctx) -> list[Finding]:
    got = _where(ctx)
    if got is None:
        return []
    name, words, roofed = got
    flagged = [(s, cues) for s in _space.sentences(ctx.text)
               if (cues := flagged_in(s, words, roofed))]
    if not flagged:
        return []
    said = list(dict.fromkeys(c for _s, cs in flagged for c in cs))
    sky = "" if roofed else ", in the open air"
    absent = ([] if words & _TAVERN_WORDS else ["bar", "patrons", "taproom"]) \
        + ([] if roofed else ["room", "rafters", "ceiling"])
    return [Finding(
        kind="wrong-kind-of-place",
        detail=f"the page furnishes another kind of place ("
               + ", ".join(repr(c) for c in said[:4]) + f") — the party is at {name}",
        fix_hint=(f"The player is at {name}{sky}. There is no "
                  + ", no ".join(absent)
                  + f" here. Rewrite the sentence so it happens at {name}, among what "
                    f"is really there. Keep the people and what they do."),
        weight=3, sentences=tuple(s for s, _c in flagged))]


def backstop(ctx, text: str, findings: list) -> tuple[str, list[str]]:
    """Cut a sentence that still furnishes the wrong place after its rewrite."""
    got = _where(ctx)
    if got is None:
        return text, []
    _name, words, roofed = got
    notes: list[str] = []
    for f in findings:
        if f.kind != "wrong-kind-of-place":
            continue
        for s in f.sentences:
            if s in text and flagged_in(s, words, roofed):
                text = re.sub(r"\s*" + re.escape(s), "", text, count=1).strip()
                notes.append(f"wrong kind of place: cut {s[:80]!r}")
    return text, notes
