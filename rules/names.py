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


def face_people(world, location_id: str | None,
                people_id: str | None = None) -> tuple[str, dict | None]:
    """(people id, `play.races` row) whose body a person made here is drawn with — the
    ONE answer, read by `appearance_for` for the face and by `person_words.people_drawn`
    for the record, so a body and its people cannot disagree.

    Measured on the 2026-09-30 playtest (item 10): 8 of 8 NPCs in Sam's save carried a
    Ratfolk face and `race: "human"` with no people at all, because this function's pick
    was kept as text and thrown away. The people asked for when it has a body; else the
    town's people; else the first body that belongs to a PEOPLE; ("", None) for none.
    A people asked for by name that the world ships no body for is returned with no row:
    its name is still who they are, and another people's body would be a lie about them.
    """
    if world is None:
        return "", None
    play = getattr(world, "play", None) or {}
    races = [r for r in ((play.get("races") if isinstance(play, dict) else None) or [])
             if isinstance(r, dict)]
    if people_id:
        row = next((r for r in races if r.get("people_id") == people_id), None)
        return str(people_id), row
    pid = people_of(world, location_id)
    row = next((r for r in races if r.get("people_id") == pid), None) if pid else None
    if row is None:
        known = peoples(world)
        row = next((r for r in races if r.get("people_id") in known), None)
    if row is not None:
        return str(row.get("people_id") or ""), row
    return str(pid or ""), None


def appearance_for(world, location_id: str | None, people_id: str | None = None,
                   ref: str = "", own: str | None = None) -> str:
    """What a stranger would see of a person of this people: the export's own body
    sentences for the people, one or two of them, in the people's name.

    Which people is `face_people`'s answer. A people named outright that ships no body
    (Pangrella's Nirkor) gets its name and the person's own details, never the first body
    on the list — that fallback is what put a Korvu face on whoever it was asked about."""
    if world is None:
        return ""
    pid, race = face_people(world, location_id, people_id)
    if race is None:
        named = people_name(world, pid) if pid else ""
        if not named or not ref:
            return ""
        from . import faces as faces_mod

        own = own if own is not None else faces_mod.details_for("", ref, location_id)
        return f"{named}: {own}" if own else ""
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


def appearance_of_kind(word: str, ref: str, location_id: str | None = None,
                       own: str | None = None) -> str:
    """A face for a person of a kind the world ships no people for — "human" granted in a
    world with no Human (F2): the kind's own word and the person's own details, and no
    people's body borrowed for it."""
    word = " ".join(str(word or "").split())
    if not word or not ref:
        return ""
    from . import faces as faces_mod

    own = own if own is not None else faces_mod.details_for("", ref, location_id)
    return f"{word[:1].upper()}{word[1:]}: {own}" if own else ""


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


# --- what can be a person's name at all ------------------------------------------------
#
# Measured on the owner's 2026-10-03 save (docs/playtest-2026-10-03.md, item 13): the
# player typed `I give a friendly wink and say "just trying to start a conversation and
# see what is happening here."`, the reading came back `talk, target: say "just trying…"`,
# and an actor (c4) was minted with that whole phrase as his NAME. It printed in prose
# ("The say \"just trying…\" is a Korvu"), in every tell and in the ledger, and he was
# still being spoken to ten turns later. Inform and TADS settle the same question by
# kind, not by guess: a quoted string or the words after SAY are a topic or a literal,
# never resolved against the world's objects (Writing with Inform §7.6, §17.5; TADS 3
# `LiteralAction`). So a person's name is refused by its SHAPE, in code, at every door
# that mints or renames one — the reason is returned, so the refusal can name the fix.
_QUOTE_MARKS = re.compile(r"[\"“”«»]|(?:^|\s)['‘]")
# A verb of speech or of the player's own doing at the head of a phrase: "say …",
# "ask him …", "tell the guard …" are things done, never somebody.
_SPEECH_HEAD = re.compile(
    r"^\s*(?:i\s+|you\s+)?(?:say|says|said|saying|ask|asks|asked|asking|tell|tells|told|"
    r"telling|shout|shouts|shouted|whisper|whispers|whispered|murmur|murmurs|reply|"
    r"replies|replied|answer|answers|answered|mutter|mutters|muttered|yell|yells|yelled|"
    r"call\s+out|greet|greets|greeted|explain|explains|explained|add|adds|added)\b", re.I)
_FIRST_PERSON_HEAD = re.compile(r"^\s*(?:i|i'm|i've|we|let's|let\s+me)\b", re.I)
# Longer than any description the corpus holds ("the tailor who mended my cloak last
# week" is 8 words) by a margin: past this it is a sentence, not somebody.
_MOST_NAME_WORDS = 14


def not_a_name(phrase: str) -> str:
    """Why `phrase` cannot be what a person is called, or "" when it can.

    Shape only — a quotation, a verb of speech at its head, a first-person opening, a
    sentence's closing mark (see below), or more words than any description
    — so it is world-agnostic and needs no list of names. "the woman who sold me bread"
    and "a Korvu porter" pass; `say "just trying…"` does not."""
    p = " ".join(str(phrase or "").split())
    if not p:
        return "it is empty"
    if _QUOTE_MARKS.search(p):
        return "it holds quoted words, which are something said, not somebody"
    if _SPEECH_HEAD.match(p):
        return "it opens with a verb of speech, which is something done, not somebody"
    if _FIRST_PERSON_HEAD.match(p):
        return "it is the player's own sentence, not somebody"
    words = p.split()
    end = p.rstrip(")]")[-1:]
    # A question or an exclamation is a sentence; a full stop alone is not proof — a
    # sloppy reply writes "the man at the bar." — so it counts only after six words that
    # do not open as a description does.
    if (end in "!?" and len(words) >= 3) or (
            end == "." and len(words) >= 6 and words[0].lower() not in _DETERMINERS):
        return "it is a sentence, not somebody"
    if len(words) > _MOST_NAME_WORDS:
        return f"it is {len(words)} words long, a sentence rather than somebody"
    return ""


def people_names(world=None, scene=None) -> set[str]:
    """Every name a PEOPLE goes by, lowercased: the world's own (its PEOPLE entities and
    its `play.races` rows), the heritages the scene's people carry, and the rulebook's
    races (`rules.races`). World-agnostic: nothing here is a list of one world's names.

    Item 14 of the 2026-10-03 playtest: the narrator wrote "a man named Korvu", Korvu
    being one of Pangrella's peoples, and the laborer c11 became "Korvu" — the people's
    name taken for his. OntoNotes keeps the two apart for the same reason (NORP,
    "nationalities or religious or political groups", is not PERSON, even inside one
    noun phrase: "Nicaraguan President Daniel Ortega")."""
    out: set[str] = set()
    if world is not None:
        out |= {str(n).lower() for n in peoples(world).values() if n}
        play = getattr(world, "play", None) or {}
        for r in (play.get("races") if isinstance(play, dict) else None) or []:
            if isinstance(r, dict) and r.get("name"):
                out.add(str(r["name"]).lower())
    for a in (getattr(scene, "people", None) or getattr(scene, "actors", None) or {}
              ).values() if scene is not None else ():
        for held in (getattr(a, "heritage", ""), getattr(a, "race", "")):
            if str(held or "").strip():
                out.add(str(held).strip().lower())
    try:
        from . import races as races_mod

        for doc in races_mod.shipped().values():
            if isinstance(doc, dict) and doc.get("name"):
                out.add(str(doc["name"]).lower())
    except Exception:  # noqa: BLE001 — the rulebook's names only ever add certainty
        pass
    return {n for n in (" ".join(x.split()) for x in out) if n}


def is_a_peoples_name(name: str, world=None, scene=None, *, known=None) -> bool:
    """Whether a name given in play is a people's name rather than a person's: the whole
    of it, or of it less a plural "s" ("Korvus"), is what a people is called."""
    n = " ".join(str(name or "").split()).lower()
    if not n:
        return False
    names = known if known is not None else people_names(world, scene)
    return n in names or (n.endswith("s") and n[:-1] in names)


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
