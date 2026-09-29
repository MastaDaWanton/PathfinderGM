"""A village the page calls a city.

Measured at the Phase-2 live gate (G2), 2026-09-29, gemma-4-12B on Aurvantis: the party in
Halhollow — a village; the export says `scale: village` — and the turn narrator wrote
"the city's heavy traffic is less frequent". Lane C's size check guards only the opening
(`play/opening_prose.problems`, item 1: Vormoor, a village, drafted as "a sprawling
settlement… the city's bustling thoroughfares"), and the plan said to measure the turn
narrator before adding the same check there. This is that measurement, and the check.

The world itself teaches the word: World Bible's settlement templates are scale-blind, so
48 of Aurvantis's 64 settlements say "the city's" of themselves (`geography.
in_its_own_words`). The brief puts those words back to the scale before the model sees
them; a model left to its own habits still reaches for "the city".

Detect in code, narration only (a character may speak of any city they like), and only
when the party is IN a settlement whose world stated a scale of village or town:

  * "the city('s)", "this city", "a busy city" — `city` in lower case; "the City Watch" is
    the world's name for something and "the city of Brackgate" is another place;
  * "the city of Halhollow", "Halhollow, a small city", "Halhollow is a city";
  * the city-scale words: metropolis, metropolitan, tens of thousands, districts,
    thoroughfares, and "sprawling" only before a word for a place ("a sprawling
    settlement") — "he lies sprawling in the mud" is a man, not a size;
  * for a village also "the town('s)", "this town", "the town of Halhollow".

A sentence that names another settlement of the world is left alone: "Brackgate, the city
to the north" is about Brackgate. Two lists of size words exist on purpose — this one and
`play/opening_prose.TOO_BIG`. The opening's is harder ("crowds", "teeming" fail a village
there) because a first paragraph is ALL description of the place; a turn in a village
market says "the crowd" about the people in front of the player, and that is not a size.

Repair: the scale named — "Halhollow is a village of a few hundred people — say village".
Backstop: the words put back to the scale, through `geography.in_its_own_words` for "the
city('s)" (the one rule the brief already uses, which never touches "the city of X") and
the same substitution for the rest; a sentence still too big after that is cut.
"""
from __future__ import annotations

import re

from gm.narration import Finding

from . import _space

ORDER = 65
KINDS = frozenset({"size-words"})
DOORS = frozenset({"plan", "turn", "outcome"})

SMALL = ("village", "town")

# `city` in lower case, after up to two lower-case describing words and a determiner, or
# on its own — never "city-state", never "city of <somewhere>" (that is handled by name),
# never capitalised mid-sentence ("the City Watch").
_CITY = re.compile(r"\b(?:(?P<det>[Tt]he|[Tt]his|[Aa]n?|[Oo]ur)(?P<mid>\s+(?:[a-z][a-z'’-]*\s+)"
                   r"{0,2}?)|(?<![A-Za-z]))(?P<word>city)(?P<pos>['’]s)?\b(?!-)(?!\s+of\b)")
_CITY_OF = re.compile(r"\b(?P<word>city|metropolis|town)\s+of\s+(?P<name>[A-Z][\w'’-]*"
                      r"(?:\s+[A-Z][\w'’-]*)*)")
_TOWN = re.compile(r"\b(?P<det>[Tt]he|[Tt]his|[Oo]ur)(?P<mid>\s+(?:[a-z][a-z'’-]*\s+){0,2}?)"
                   r"(?P<word>town)(?P<pos>['’]s)?\b(?!-)(?!\s+of\b)")
_PLACE_NOUN = (r"(?:settlement|city|town|village|streets?|markets?|quarters?|districts?|"
               r"maze|warren|expanse|neighbou?rhoods?|lanes?|sprawl)")
_SPRAWLING = re.compile(r"\bsprawling\s+(?=(?:[a-z][a-z'’-]*\s+){0,2}" + _PLACE_NOUN + r"\b)")
_BIG = re.compile(r"\b(?P<word>metropolis|metropolitan|tens of thousands|districts?|"
                  r"thoroughfares?)\b")


def _stated_scale(location) -> str:
    """village, town or city — only when the world SAID one (`places.scale_of` answers
    "town" for a place whose size it cannot read, which is no ground for a refusal)."""
    from rules import places

    said = " ".join(str(getattr(location, "scale", "") or "").split()).lower()
    if said in places.PLACES_BY_SCALE or said in places.SCALE_ALIASES:
        return places.scale_of(location)
    return ""


def _small_settlement(ctx):
    """(location, scale) when the party stands in a village or town the world sized."""
    from rules import places

    location = _space.settlement(ctx)
    if location is None or not places._settled(location, ""):
        return None, ""
    scale = _stated_scale(location)
    if scale not in SMALL:
        return None, ""
    if _space.here_setting(ctx) == "outside":
        return None, ""
    return location, scale


def _other_places(ctx, location) -> list[str]:
    """Every other settlement the world names, longest first."""
    from rules import places

    world = ctx.world
    names: set[str] = set()
    for e in (getattr(world, "entities", None) or {}).values():
        if e.id != location.id and e.name and _stated_scale(e) \
                and places._settled(e, ""):
            names.add(str(e.name))
    for r in _space.roads(ctx):
        if getattr(r, "to_name", ""):
            names.add(str(r.to_name))
    return sorted(names, key=len, reverse=True)


def _names_other(plain: str, others: list[str]) -> bool:
    return any(re.search(r"\b" + re.escape(n) + r"\b", plain) for n in others)


def words_in(plain: str, scale: str, name: str, others: list[str]) -> list[str]:
    """The size words a narration sentence uses about this settlement, as written."""
    found: list[str] = []
    for m in _CITY_OF.finditer(plain):
        if m.group("name").startswith(name) and (m.group("word") != "town" or
                                                 scale == "village"):
            found.append(f"{m.group('word')} of {name}")
    if name:
        # "Halhollow, a small city" / "Halhollow is a city" / "Halhollow's a town".
        big = "city|metropolis" + ("|town" if scale == "village" else "")
        said = re.search(r"\b" + re.escape(name) + r"(?:['’]s|,|\s+is)\s+(?:a|an|the)\s+"
                         r"(?:[a-z][a-z'’-]*\s+){0,2}(" + big + r")\b", plain)
        if said:
            found.append(said.group(1))
    if _names_other(plain, others):
        # About somewhere else, or at least not only about here.
        return list(dict.fromkeys(found))
    found += [(m.group("det").lower() + " " if m.group("det") else "")
              + "city" + (m.group("pos") or "") for m in _CITY.finditer(plain)]
    if scale == "village":
        found += [m.group("det").lower() + " town" + (m.group("pos") or "")
                  for m in _TOWN.finditer(plain)]
    if _SPRAWLING.search(plain):
        found.append("sprawling")
    found += [m.group("word") for m in _BIG.finditer(plain)]
    return list(dict.fromkeys(found))


def find(ctx) -> list[Finding]:
    from rules import places

    location, scale = _small_settlement(ctx)
    if location is None:
        return []
    name = str(getattr(location, "name", "") or "")
    others = _other_places(ctx, location)
    flagged: list[tuple[str, list[str]]] = []
    for s in _space.sentences(ctx.text):
        words = words_in(_space.unquoted(s), scale, name, others)
        if words:
            flagged.append((s, words))
    if not flagged:
        return []
    said = list(dict.fromkeys(w for _s, ws in flagged for w in ws))
    return [Finding(
        kind="size-words",
        detail=f"the page calls {name} " + ", ".join(repr(w) for w in said)
               + f" — the world says it is a {scale}",
        fix_hint=(f"{name} is {places.what_it_is(scale)} — say {scale}, not "
                  + ", ".join(repr(w) for w in said) + ". Describe it at that size."),
        weight=1, sentences=tuple(s for s, _w in flagged))]


# --- the backstop ---------------------------------------------------------------------

def _article(det: str, word: str) -> str:
    if det.lower() in ("a", "an"):
        a = "an" if word[:1].lower() in "aeiou" else "a"
        return a.capitalize() if det[:1].isupper() else a
    return det


def shrink(narration: str, scale: str, name: str) -> str:
    """Narration with its city words put back to the settlement's scale."""
    from rules import geography

    out = geography.in_its_own_words(narration, scale)

    def city(m: re.Match) -> str:
        det, mid = m.group("det") or "", m.group("mid") or ""
        if det:
            det = _article(det, (mid.strip() or scale))
            return f"{det}{mid or ' '}{scale}{m.group('pos') or ''}"
        return f"{scale}{m.group('pos') or ''}"

    out = _CITY.sub(city, out)
    out = re.sub(r"\b(city|metropolis|town)(\s+of\s+" + re.escape(name) + r")\b",
                 lambda m: scale + m.group(2)
                 if m.group(1) != "town" or scale == "village" else m.group(0), out)
    if scale == "village":
        out = _TOWN.sub(lambda m: f"{m.group('det')}{m.group('mid')}village"
                                  f"{m.group('pos') or ''}", out)
    out = re.sub(r"\b(an?)(\s+)metropolis\b",
                 lambda m: _article(m.group(1), scale) + m.group(2) + scale, out)
    out = re.sub(r"\bmetropolis\b", scale, out)
    out = re.sub(r"\bmetropolitan\s+", "", out)
    out = _SPRAWLING.sub("", out)
    few = "a few hundred" if scale == "village" else "some thousands"
    out = re.sub(r"\btens of thousands\b", few, out)
    lanes = "lanes" if scale == "village" else "streets"
    out = re.sub(r"\bdistricts\b", lanes, out)
    out = re.sub(r"\bdistrict\b", lanes[:-1], out)
    out = re.sub(r"\bthoroughfares\b", lanes, out)
    out = re.sub(r"\bthoroughfare\b", lanes[:-1], out)
    # "a village" after an "an" the substitution left: "an ancient city" keeps its "an".
    out = re.sub(r"\b([Aa])n(\s+)(village|town)\b", r"\1\2\3", out)
    return out


def backstop(ctx, text: str, findings: list) -> tuple[str, list[str]]:
    from gm import speech

    location, scale = _small_settlement(ctx)
    if location is None:
        return text, []
    name = str(getattr(location, "name", "") or "")
    others = _other_places(ctx, location)
    notes: list[str] = []
    for f in findings:
        if f.kind != "size-words":
            continue
        for s in f.sentences:
            if s not in text:
                continue
            # The narration only: a character's own words are theirs.
            fixed = "".join(chunk if is_speech else shrink(chunk, scale, name)
                            for is_speech, chunk in speech.split(s))
            if words_in(_space.unquoted(fixed), scale, name, others):
                text = re.sub(r"\s*" + re.escape(s), "", text, count=1).strip()
                notes.append(f"cut, still too big for a {scale}: {s[:80]}")
            elif fixed != s:
                text = text.replace(s, fixed, 1)
                notes.append(f"said {scale}: {fixed[:80]}")
    return text, notes
