"""True names and faces for the people the scene makes, from the world's own material.

World Bible ships `play.names`: 80 pools, each `{people_id, given[16+], family[16+]}`.
Sixteen resolve to PEOPLE entities (Human, Elf, Half-Orc … under their continents) and
sixty-four to finer culture ids the export does not otherwise name. Measured 2026-09-18:
no module in `play/`, `rules/` or `gm/` read them, and an NPC asked his name called
himself "the stranger" — our placeholder — while the model, guessing at the pool it was
never shown, wrote "Kaelen", a hair from the world's own Kael / Kaelin / Kaelos.

`play.races` carries the same peoples' bodies as sentences ("Small, wiry, sharp-toothed,
disproportionately strong for their size."), and every world CHARACTER carries an
Appearance fact. That is enough for a face: a people's body line for a promoted
civilian, the resident's own Appearance for a resident.

Deterministic on purpose: the same scene, the same ref, the same name, so a save
replayed does not hand the stranger a second name. Seeded off the ref and the location.
"""
from __future__ import annotations

import hashlib
import re

_WORD = re.compile(r"[A-Za-z][A-Za-z'’-]+")


def pools(world) -> list[dict]:
    play = getattr(world, "play", None) or {}
    out = play.get("names") if isinstance(play, dict) else None
    return [p for p in (out or []) if isinstance(p, dict) and p.get("given")]


def peoples(world) -> dict[str, str]:
    """PEOPLE entity id → name, for the pools that resolve to one."""
    try:
        return {e.id: e.name for e in world.entities.values()
                if str(getattr(e, "kind", "")).upper() == "PEOPLE"}
    except Exception:
        return {}


def people_of(world, location_id: str | None) -> str | None:
    """The PEOPLE id most of a settlement's residents belong to, read off their own
    Identity prose ("… is a Half-Orc guildmaster working out of Ashwatch"), or None.

    Settlements in the export do not say who lives in them; the residents do, one
    sentence each. The majority is the town's people; a tie takes the first named."""
    if world is None or not location_id:
        return None
    named = peoples(world)
    if not named:
        return None
    by_name = {v.lower(): k for k, v in named.items()}
    counts: dict[str, int] = {}
    try:
        residents = [e for e in world.entities.values()
                     if str(getattr(e, "kind", "")).upper() == "CHARACTER"
                     and getattr(e, "parent_id", None) == location_id]
    except Exception:
        residents = []
    for r in residents:
        text = " ".join(str(p) for s in (getattr(r, "sections", None) or [])
                        for p in (s.get("paragraphs") or [])
                        if str(s.get("title", "")).lower() == "identity").lower()
        for people_name, pid in by_name.items():
            if re.search(rf"\b{re.escape(people_name)}\b", text):
                counts[pid] = counts.get(pid, 0) + 1
                break
    if not counts:
        return None
    return max(counts, key=lambda k: (counts[k], -list(counts).index(k)))


def pool_for(world, location_id: str | None, people_id: str | None = None) -> dict | None:
    """The name pool for a person made here: theirs by people id, else the settlement's
    people, else the first pool that resolves to a PEOPLE entity, else any."""
    all_pools = pools(world)
    if not all_pools:
        return None
    wanted = people_id or people_of(world, location_id)
    if wanted:
        for p in all_pools:
            if p.get("people_id") == wanted:
                return p
    known = peoples(world)
    for p in all_pools:
        if p.get("people_id") in known:
            return p
    return all_pools[0]


def town_pool(world, location_id: str | None) -> dict | None:
    """The settlement's OWN name pool — the `play.names` row whose `home_id` is the town —
    or None.

    Aurvantis ships sixty-four of them, one per settlement: Vormoor's holds sixteen
    families (Grimstone, Fellhaven, …) that nothing read until 2026-09-28, while every
    keeper there took a family off the town's four cast members and the market was kept
    by an Ironvale in every game (playtest item 8.4). A world with none (Pangrella) gets
    None, and the caller falls back.
    """
    if world is None or not location_id:
        return None
    for p in pools(world):
        if str(p.get("home_id") or "") == str(location_id):
            return p
    return None


def _pick(seq: list, seed: str, salt: str) -> str:
    if not seq:
        return ""
    h = hashlib.sha256(f"{seed}|{salt}".encode("utf-8")).hexdigest()
    return str(seq[int(h[:8], 16) % len(seq)])


def true_name(world, location_id: str | None, ref: str, taken=(),
              people_id: str | None = None) -> str:
    """A given and a family name from the right pool, seeded off the ref and the place
    so it is the same every time it is asked; a name already worn here is skipped."""
    pool = pool_for(world, location_id, people_id)
    if not pool:
        return ""
    given = [str(g) for g in pool.get("given") or []]
    family = [str(f) for f in pool.get("family") or []]
    used = {str(t).lower() for t in taken}
    seed = f"{location_id or ''}|{ref}"
    for n in range(8):
        g = _pick(given, seed, f"given{n}")
        f = _pick(family, seed, f"family{n}") if family else ""
        name = f"{g} {f}".strip()
        if name and name.lower() not in used and g.lower() not in used:
            return name
    return f"{_pick(given, seed, 'given')} {_pick(family, seed, 'family')}".strip()


def people_name(world, people_id: str | None) -> str:
    return peoples(world).get(people_id or "", "") if world is not None else ""


def appearance_for(world, location_id: str | None, people_id: str | None = None,
                   ref: str = "", own: str | None = None) -> str:
    """What a stranger would see of a person of this people: the export's own body
    sentences for the people, one or two of them, in the people's name."""
    if world is None:
        return ""
    pid = people_id or people_of(world, location_id)
    play = getattr(world, "play", None) or {}
    races = play.get("races") if isinstance(play, dict) else None
    race = next((r for r in (races or []) if isinstance(r, dict)
                 and r.get("people_id") == pid), None)
    if race is None and races:
        race = next((r for r in races if isinstance(r, dict)
                     and r.get("people_id") in peoples(world)), None)
    if race is None:
        return ""
    body = [str(b).strip() for b in (race.get("body") or []) if str(b).strip()]
    if not body:
        return ""
    # One line always, the second sometimes, so two people of one people do not read
    # as twins — which was the whole of the variety until 2026-09-23, and most peoples
    # ship one body line, so six orcs in one scene were the same sentence six times.
    # What is theirs and not their people's is `rules/faces.py`, seeded like the name.
    lines = [body[0]]
    if len(body) > 1 and int(hashlib.sha256(f"{ref}|face".encode()).hexdigest()[:2], 16) % 2:
        lines.append(body[1])
    from . import faces as faces_mod

    # `own` is given when the person was rolled by `rules.lives`, whose face was chosen to
    # agree with their work (2026-09-25); otherwise the seeded pick from `faces`.
    if own is None:
        own = faces_mod.details_for(" ".join(lines), ref, location_id)
    if own:
        lines.append(own)
    named = str(race.get("name") or people_name(world, pid) or "").strip()
    return (f"{named}: " if named else "") + " ".join(lines)


def resident_appearance(world, entity_id: str | None) -> str:
    """A world resident's own Appearance fact, or ""."""
    if world is None or not entity_id:
        return ""
    try:
        ent = world.get(entity_id)
    except Exception:
        ent = None
    if ent is None:
        return ""
    return str(getattr(ent, "facts", {}).get("Appearance", "") or "").strip()


# --- a person's label as the engine prints it ------------------------------------------
#
# Measured live 2026-09-29 (G3): the engine's own tell read "You leave man mid-sentence",
# and the Bobby corpus's turn log is full of the same shape — "On the board: girl (c2).",
# "You are with Guard, girl, the watchman waving traffic through", "Bobby speaks to man in
# a stained leather jerkin". A person the prose described is booked under the prose's
# words, and those words are a KIND of person ("man", "girl", "herbalist vendor"), which in
# English takes its article. There were already three private copies of this rule
# (`narration.definite`, `prompts._definite`, `xp._definite`), each written after one of
# these reached the page; the engine's ~300 tells never had one. So the rule lives here,
# once, and the engine applies it to every tell it finishes (`Engine._resolve_one`,
# `Engine._tick_schemes`) rather than at three hundred print sites.
_DETERMINERS = frozenset({
    "the", "a", "an", "your", "his", "her", "their", "its", "my", "our", "some", "this",
    "that", "these", "those", "every", "each", "no", "another", "any", "one", "whose",
})


def is_descriptor(name: str) -> bool:
    """Whether a person's name is a kind of person that needs its article — "man",
    "girl", "man with the ledger" — rather than a proper name ("Grix", "Guard") or a
    phrase that already carries one ("the watchman waving traffic through")."""
    words = str(name or "").split()
    return bool(words) and words[0][:1].islower() and words[0].lower() not in _DETERMINERS


def definite(name: str) -> str:
    """"man" → "the man"; "Grix" and "the watchman" stay as they are."""
    name = " ".join(str(name or "").split())
    return f"the {name}" if is_descriptor(name) else name


_QUOTED = re.compile(r"\"[^\"]*\"|“[^”]*”")
_WORD_BEFORE = re.compile(r"([A-Za-z'’]+)\s+$")
_SENTENCE_START = re.compile(r"(?:^|[.!?]\s+|\n\s*)$")


def with_articles(text: str, names) -> str:
    """Every bare descriptor-name of a person in `text` given its article.

    Idempotent, and careful in three ways that each have a failure behind them: the
    player's own quoted words are never touched; a name that sits inside another
    person's longer name ("man" inside "the man with the ledger") is that other person
    and is left alone, longest names claimed first; and a name already following a
    determiner ("the man", "your man") is already definite. At the start of a sentence
    the article is capitalised: "The man takes it badly."
    """
    text = str(text or "")
    low = text.lower()
    wanted = sorted({" ".join(str(n or "").split()) for n in names or ()
                     if str(n or "").strip()
                     and " ".join(str(n).split()).lower() in low}, key=len, reverse=True)
    if not text or not wanted:
        return text
    claimed = [m.span() for m in _QUOTED.finditer(text)]
    edits: list[tuple[int, int, str]] = []

    def free(lo: int, hi: int) -> bool:
        return not any(lo < b and a < hi for a, b in claimed)

    for name in wanted:
        # The name as it is kept, and — for a descriptor — as a sentence opening
        # capitalises it ("Man comes round" from a `.capitalize()`d tell).
        forms = [re.escape(name)]
        if is_descriptor(name):
            forms.append(re.escape(name[:1].upper() + name[1:]))
        rx = re.compile(rf"(?<![\w'’-])(?:{'|'.join(forms)})(?![\w-])")
        for m in rx.finditer(text):
            lo, hi = m.span()
            if not free(lo, hi):
                continue
            before = text[:lo]
            opening = bool(_SENTENCE_START.search(before))
            if m.group(0) != name and not opening:
                continue                 # a capitalised word mid-sentence is not them
            claimed.append((lo, hi))
            if not is_descriptor(name):
                continue
            prev = _WORD_BEFORE.search(before)
            if prev and prev.group(1).lower() in _DETERMINERS:
                continue
            edits.append((lo, hi, f"{'The' if opening else 'the'} {name}"))
    for lo, hi, new in sorted(edits, reverse=True):
        text = text[:lo] + new + text[hi:]
    return text
