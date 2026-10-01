"""Everybody the campaign has seen, kept where they were seen.

The user's ruling of 2026-09-25: "I dont care if a database grows of random people as long
as we can search the data base quickly and precisely"; the woman watching from a doorway
"should stay there until i leave or something moves them in prose. and once I leave that
woman remains a resident of the city/town/village unless she is a merchant or traveller".
Design record: docs/the-population.md.

A person here is a RECORD, not a character sheet: a sheet is 1.4 KB bare and several KB
with gear (measured), too heavy for a town's worth of passers-by. The record carries the
phrase the prose first used (what the player will paraphrase), where and when, and a life
rolled by `rules.lives` — work, face, temperament, wants, goal, hobby, quirk. A person
becomes an `Actor` in `Scene.people` only when they enter play (the existing promotion,
and later the player engaging them), and the record keeps the ref.

Tiers, after RimWorld's "who is kept" and Dwarf Fortress's "anybody named you meet":
  glimpse       the prose described them; nothing more has happened
  acquaintance  the player spoke to them, or they were named, or acted in a scene
  figure        tied to a quest, a debt, a fight or a relative of a figure
Only the first exists before the engagement work of phase 2's later steps.

Nothing here writes a number the narrator hears, and nothing here is a second store of a
fact the engine holds elsewhere: a person with an `Actor` is that actor for everything
mechanical; the record holds only what no sheet has — the phrase, the place first seen,
the life, and when the player last met them.
"""
from __future__ import annotations

import re

from . import lives


def _norm(phrase: str) -> str:
    return " ".join(re.findall(r"[a-z']+", str(phrase or "").lower()))


def _next_id(scene) -> str:
    taken = [int(k[1:]) for k in (getattr(scene, "population", {}) or {})
             if re.fullmatch(r"p\d+", k)]
    return f"p{max(taken, default=0) + 1}"


def at_spot(scene, phrase: str, spot: str | None = None) -> dict | None:
    """The person already recorded under this phrase at this place, if any."""
    want = _norm(phrase)
    where = spot if spot is not None else getattr(scene, "at", None)
    for rec in (getattr(scene, "population", {}) or {}).values():
        if rec.get("spot") == where and _norm(rec.get("phrase", "")) == want:
            return rec
    return None


def here_as(scene, phrase: str) -> dict | None:
    """The person at this spot this phrase means, if the population already holds them.

    The exact phrase first; then the finder, in the here ring, for somebody the prose now
    calls by other words — but only one who fits alone and whom no actor in the room
    already embodies (somebody standing here in a body was the ledger's to match, and is
    not who a fresh booking means). Measured live 2026-09-25: an old woman "mending fishing
    nets by the doorway" was a glimpse at the party's spot; the player spoke to her, the
    prose wrote "the old woman", and the booking door made a second person with a second
    face while her record stayed without a body.
    """
    exact = at_spot(scene, phrase)
    if exact is not None:
        return exact
    found = find(scene, phrase, rings=(HERE,), log_miss=False)
    if found.scope != HERE:
        return None
    rec = found.people[0]
    if rec.get("ref") and rec["ref"] in (getattr(scene, "actors", {}) or {}):
        return None
    # Somebody booked on this visit's ledger was already ruled a different person by the
    # ledger's own definiteness test (`judgement._refers_back`): "a young guard" booked,
    # then "a guard" arriving, are two. The finder only reaches people the ledger does
    # not hold — an earlier visit's, or a glimpse it never booked.
    ledger = {_norm(e.get("who", "")) for e in (getattr(scene, "cast", None) or [])}
    if _norm(rec.get("phrase", "")) in ledger:
        return None
    return rec


# --- a booking keeps its description --------------------------------------------------
#
# Measured live 2026-09-29 (G3): a scene entry named just "man", and the engine's tell
# "You leave man mid-sentence". The plan's `introduce` says who in as few words as it
# likes ("man"), and `_op_introduce` named the body with those words even when the person
# it bound to was a record the prose had described ("man in a stained leather jerkin" is
# how the Bobby corpus's c8 was booked, and p8 "man with the whetstone" beside him). A
# bare head noun distinguishes nobody once a second man walks in; the description is what
# the player will paraphrase and what the finder matches.

# Where a description starts after its head word: "man WITH the ledger", "woman IN the
# doorway", "watchman WAVING traffic through".
_TAIL_START = frozenset({
    "with", "in", "at", "by", "from", "of", "who", "that", "wearing", "carrying", "holding",
    "near", "beside", "behind", "on", "under", "outside", "inside", "selling", "mending",
})
_ARTICLE = re.compile(r"^(?:the|a|an|some)\s+", re.I)


def head_of(phrase: str) -> str:
    """The word a description is built on: "older man with a face" → "man"."""
    words = _ARTICLE.sub("", " ".join(str(phrase or "").split())).lower().split()
    for i, w in enumerate(words):
        if i and (w in _TAIL_START or w.endswith("ing")):
            return words[i - 1].strip(",.")
    return words[-1].strip(",.") if words else ""


def is_bare(phrase: str) -> bool:
    """A head noun and nothing else — "man", "the girl"."""
    return len(_ARTICLE.sub("", " ".join(str(phrase or "").split())).split()) == 1


def fuller(phrase: str, rec: dict | None) -> str:
    """The record's own words when `phrase` is only their head noun, else `phrase`."""
    said = " ".join(str((rec or {}).get("phrase") or "").split())
    if (said and is_bare(phrase) and not is_bare(said)
            and head_of(said) == head_of(phrase)):
        return said
    return phrase


def described_here(scene, phrase: str) -> dict | None:
    """The one record at this spot, with no body in the room, whom a bare head noun
    means because the prose described them: "man" when the population holds "man with
    the whetstone" here and no other man. None when the phrase is not bare, or when two
    unembodied people here share the head — that is a "which do you mean", not a pick."""
    if not is_bare(phrase):
        return None
    head = head_of(phrase)
    where = getattr(scene, "at", None)
    bodies = getattr(scene, "people", {}) or {}
    fits = [r for r in (getattr(scene, "population", {}) or {}).values()
            if r.get("spot") == where and not (r.get("ref") and r["ref"] in bodies)
            and not is_bare(r.get("phrase", "")) and head_of(r.get("phrase", "")) == head]
    return fits[0] if len(fits) == 1 else None


def embody(scene, phrase: str, template: str, *, zone: str = "near", world=None,
           rec: dict | None = None, seen_here: bool = True):
    """One person becomes an actor in the room: the one door the prose's people
    (`judgement.promote_cast`), the finder's repair and the planner's `introduce` all go
    through. `rec` is their population record, when they have one: the actor wears the
    face it rolled and the record keeps the ref.

    `seen_here=False` for a body made only to be moved on at once — the call on somebody
    heard of (`Engine._embody_callee`), who is not in the room the party stands in. Marking
    her seen there put her day's work at the party's place: measured 2026-10-01, the woman
    a barkeep spoke of was "at the gate at this hour" when the party knocked at her house."""
    from . import states
    from .bestiary import instantiate

    from . import person_words

    # The words the record was first known by, when the booking came with fewer: never a
    # bare "man" for somebody the prose described as "the man with the ledger".
    phrase = fuller(phrase, rec)
    actor = instantiate(template, scene=scene, name=phrase)
    # Through the door. The fallback that wrote `scene.actors` directly would now
    # write into a derived view and vanish; `add` stamps the place and the zone —
    # the zone the prose put them in, so the map lays them out where the words did.
    scene.add(actor, zone=zone)
    # What the words already say: "the girl in the market" is she/her (item 5.3, the
    # 2026-09-28 playtest's c2 walked on as they/them). The record's own phrase first —
    # it is the words the person was first known by.
    said = person_words.from_words((rec or {}).get("phrase") or phrase, world,
                                   getattr(scene, "location_id", "") or "")
    person_words.apply(actor, said)
    if rec is not None and rec.get("seen") is False and seen_here:
        # Heard of until now (`note(spot=...)`); a body in the room is seen.
        seen(scene, rec)
    # In the room, not in the fight. Law two: the fact travels as an effect whose
    # tag is `role.bystander`, lifted by the one door into a fight and by a blow
    # given or taken — never by a flag beside it.
    actor.add_condition(states.BYSTANDER_KEY, source="introduced by the scene")
    if rec is not None:
        rec["ref"] = actor.ref
    # A name behind the descriptor and a face beside it, from the world's own
    # pools and bodies (rules/names.py) — the panel keeps showing the descriptor
    # until the name is given in play.
    if world is not None:
        from . import names as names_mod

        taken = [a.true_name for a in scene.actors.values() if getattr(a, "true_name", "")]
        taken += [a.name for a in scene.actors.values()]
        actor.true_name = names_mod.true_name(world, scene.location_id, actor.ref, taken)
        # The face their population record rolled, when they have one — chosen to
        # agree with their work (rules/lives.py) — and the people it is drawn from,
        # recorded (`person_words.settle_people`). Until 2026-09-30 only the face text
        # was kept: 8 of 8 NPCs in Sam's save were race "human" with a Ratfolk face and
        # no people. The words first ("the elf at the bar"), then a grant here (F2:
        # "any human women here?" — "There is one"), then the town's people.
        own = ((rec.get("life") or {}).get("face") if rec else None)
        person_words.settle_people(scene, world, actor,
                                   words=(rec or {}).get("phrase") or phrase,
                                   template=template, own=own, redraw_face=True, rec=rec)
        if not actor.appearance and person_words.is_a_person(template):
            actor.appearance = names_mod.appearance_for(world, scene.location_id,
                                                        ref=actor.ref, own=own)
    if getattr(scene, "grid", None) is not None:
        scene.place_by_zone([actor.ref])
    return actor


# --- what the narrator is told about a person ------------------------------------------
#
# docs/the-population.md §7, built 2026-09-25 after a research pass (citations in
# docs/the-population.md "Built: manner in the brief"):
#   * two traits at most, the loudest — salient attributes crowd out the rest (The
#     Chameleon's Limit, 2026), and Dwarf Fortress reports only facets past its neutral band;
#   * as behaviour, never a label: the `shows` line is something they do, and CoMPosT
#     (EMNLP 2023) found generic framing is what breeds caricature;
#   * the quirk on first meeting and then only after QUIRK_EVERY turns, held here as
#     state like Valve's `respeakdelay` — a small model cannot count "now and then";
#   * wants, goal and hobby never: at 12B a secret the model is told leaks thematically
#     about 83% of the time, and "don't reveal" helped only frontier models (Holtzman &
#     West 2026). What it is not told it cannot tell.

QUIRK_EVERY = 5


def manner_for(rec: dict | None, turn: int) -> str:
    """The line the brief carries for a person with a record, or ""."""
    life = (rec or {}).get("life") or {}
    shows = [s for s in (life.get("shows") or []) if s][:2]
    parts = []
    if shows:
        parts.append("In how they act (show it; never name it): " + "; ".join(shows) + ".")
    quirk = str(life.get("quirk") or "").strip()
    if quirk and quirk_due(rec, turn):
        parts.append(f"A habit of theirs, shown once in what they do this beat: {quirk}.")
    return " ".join(parts)


def quirk_due(rec: dict | None, turn: int) -> bool:
    last = (rec or {}).get("quirk_turn")
    return last is None or int(turn) - int(last) >= QUIRK_EVERY


_QUIRK_FILLER = frozenset({
    "their", "they", "them", "whenever", "every", "anybody", "somebody", "something",
    "about", "before", "after", "while", "would", "could", "never", "always", "again",
    "other", "people", "thing", "things", "where", "which", "there", "those", "these",
})


def quirk_shown(rec: dict | None, beat: str) -> bool:
    """Whether the beat showed this person's quirk: two of its distinctive words (five
    letters or more, not grammar) appear in it. Mechanical and deliberately loose — it
    decides only when the brief next offers the habit, never what the page says."""
    quirk = str(((rec or {}).get("life") or {}).get("quirk") or "").lower()
    words = {_stem(w) for w in re.findall(r"[a-z]{5,}", quirk)} - {_stem(w) for w in _QUIRK_FILLER}
    if len(words) < 2:
        return False
    said = {_stem(w) for w in re.findall(r"[a-z]{5,}", str(beat or "").lower())}
    return len(words & said) >= 2


def note_quirks_shown(scene, beat: str, turn: int) -> list[str]:
    """After the prose: the quirk rests for QUIRK_EVERY turns from the beat it was OFFERED
    in, whether or not the page used it — Valve's `respeakdelay` counts from the speaking,
    not from somebody confirming it was heard. Measured live 2026-09-25: the model plays
    quirks in paraphrase ("can tell which quarter of town you grew up in from the way you
    say three words" came back as "focuses on the way you speak, as if trying to pin down
    where you grew up"), the word detector missed every one of them in twelve turns, and a
    cadence waiting on the detector would have offered each quirk every turn — the
    caricature the cadence exists to prevent. Returns the refs whose quirk the detector
    DID see, for the turn log."""
    seen = []
    for ref, actor in (getattr(scene, "actors", {}) or {}).items():
        if getattr(actor, "is_pc", False):
            continue
        rec = of_ref(scene, ref)
        if rec is None or not ((rec.get("life") or {}).get("quirk")):
            continue
        if quirk_shown(rec, beat):
            seen.append(ref)
        if quirk_due(rec, turn):
            rec["quirk_turn"] = int(turn)
    return seen


_TOO_COMMON_TO_BE_A_LABEL = frozenset({
    "open", "warm", "hard", "cold", "soft", "quiet", "loud", "plain", "close", "free",
    "sharp", "still", "light", "dark", "tight", "loose", "straight", "fair", "short",
})


def traits_named(rec: dict | None, beat: str, name: str = "") -> list[str]:
    """The trait words the beat says outright about this person — "suspicious",
    "tight-fisted" — within the sentences that name them. Behaviour was asked for; a
    label is the caricature CoMPosT describes. Logged, to be measured before any repair
    is written for it."""
    life = (rec or {}).get("life") or {}
    # Words too common to be a label: "the gate stood open" named nobody "open" (live,
    # 2026-09-25, the only hit in twelve turns).
    words = [w.lower() for w in (life.get("traits") or [])
             if w and w.lower() not in _TOO_COMMON_TO_BE_A_LABEL]
    if not words or not beat:
        return []
    head = (str(name or rec.get("phrase") or "").lower().split() or [""])[-1]
    out = []
    for sentence in re.split(r"(?<=[.!?])\s+", str(beat)):
        low = sentence.lower()
        if head and head not in low and not re.search(r"\b(?:he|she|they)\b", low):
            continue
        out += [w for w in words if re.search(rf"\b{re.escape(w)}\b", low)]
    return sorted(set(out))


def used_frames(scene, home) -> set[str]:
    """The quirk frames people of this settlement already carry, so the next is new."""
    return {rec["life"]["quirk_frame"]
            for rec in (getattr(scene, "population", {}) or {}).values()
            if rec.get("home") == home and rec.get("life")}


_HINT_WORK = re.compile(r"\b(?:her|his|their)\s+([a-z][a-z'-]{2,})", re.I)


def note(scene, phrase: str, *, turn: int = 0, body: str = "", fresh: bool = False,
         spot: str | None = None, heard_from: str = "", hint: str = "") -> dict:
    """Record the person this phrase describes, where the party stands; return the record.

    The same phrase at the same place is the same person seen again — their `last_seen`
    moves and nothing is rolled twice. A new one is rolled once, seeded by their id, and
    never re-rolled: the roll is stored, not the seed. `fresh`: somebody new whatever the
    words — the planner's newcomer, or the second of two introduced together.

    `spot` names another place in this settlement: somebody an NPC placed there, HEARD
    OF and not seen (Eric Eve's Epistemology: *familiar*, not *seen* — Inform Recipe Book
    §5.5). The owner's ruling (Q5, 2026-09-28): a person an NPC places at a real place in
    this settlement becomes a population record. Measured on the playtest: the watchman
    said "the girl in the market", nothing wrote her down, and at the market the finder
    missed her. `heard_from` is the speaker's ref; `hint` is the speaker's words about
    them, read only for what they work at ("her stall"). `spot=""` is heard of with the
    place unknown — never where the talk happened (owner's save, 2026-10-01: the woman who
    lives "three streets over" was recorded in the tavern where Gorm spoke of her).
    """
    from . import person_words

    if not hasattr(scene, "population") or scene.population is None:
        scene.population = {}
    clock = int(getattr(scene, "clock_minutes", 0) or 0)
    heard = spot is not None and spot != getattr(scene, "at", None)
    if heard:
        have = None if fresh else at_spot(scene, phrase, spot)
        if have is not None:
            return have
    else:
        have = None if fresh else here_as(scene, phrase)
        if have is not None:
            seen(scene, have)
            return have
    pid = _next_id(scene)
    home = getattr(scene, "location_id", None)
    # The roll reads the words with the Q25 ruling applied ("girl" is a young woman
    # unless the words make her a child) and the work the speaker gave them, if any.
    said = person_words.from_words(phrase)
    rolled = person_words.roll_phrase(phrase, said)
    work = [w for w in _HINT_WORK.findall(str(hint or "")) if lives.occupation_for(w)]
    if work and not lives.occupation_for(rolled):
        rolled = f"{rolled} {work[0]}"
    used = used_frames(scene, home)
    life = None
    if heard and spot:
        # The speaker said they are THERE, now: their life must agree. A roll whose
        # routine has them elsewhere at this hour (a priest at the shrine at ten) is
        # rolled again, deterministically, until one keeps them at work — and where a
        # resident works is where they were first placed (`residency.resolve`). Measured
        # while building this: the first girl of the market rolled a priest, and at the
        # market at ten in the morning the finder put her at the shrine.
        from . import residency

        slot = residency.slot_of(clock)
        for salt in range(12):
            cand = lives.roll(f"{home}|{pid}" + (f"|{salt}" if salt else ""),
                              phrase=rolled, body=body, used_frames=used)
            probe = {"id": pid, "life": cand.as_dict(), "first_seen": clock}
            if cand.mobility != "resident" or \
                    residency.schedule_for(probe)[slot] == residency.WORK:
                life = cand
                break
    if life is None:
        life = lives.roll(f"{home}|{pid}", phrase=rolled, body=body, used_frames=used)
    where = spot if heard else getattr(scene, "at", None)
    rec = {
        "id": pid, "phrase": " ".join(str(phrase).split()), "home": home,
        "spot": where, "seen_at": "" if heard else where,
        "first_seen": clock, "last_seen": None if heard else clock,
        "last_met": None, "turn": int(turn), "ref": "", "tier": "glimpse",
        "life": life.as_dict(),
    }
    if heard:
        # Written only when they differ from a seen record's defaults (§2.0, §2.4): an
        # old save's records read `seen` as True and have no `heard_from`.
        rec["seen"] = False
        rec["heard_from"] = str(heard_from or "")
        rec["heard_at"] = clock
    if rec["life"].get("mobility", "resident") != "resident":
        # A traveller's roads are walked from where and when they were last seen.
        rec["anchor"] = {"loc": home, "place": rec["spot"], "t": clock}
    scene.population[pid] = rec
    return rec


def heard_of_match(scene, phrase: str, *, turn: int, within: int = 2) -> dict | None:
    """The one person HEARD OF in the last few beats (`seen` False, no body) whom this
    phrase describes, or None — for two descriptions of one person to stay one record.

    Measured on the owner's save (2026-10-01): Gorm said a human woman lives in "the house
    three streets over", and the population recorded her twice in the same beat — p16 'human
    woman' from the narration's own report of it, and p17 'human woman' heard from Gorm —
    so "which human woman do you mean?" refused the call on her. `within` counts transcript
    entries (a beat and its player line are two), so "the same or the next beat"."""
    words = _tokens(phrase)
    if not words:
        return None
    bodies = getattr(scene, "people", {}) or {}
    fits = [r for r in (getattr(scene, "population", None) or {}).values()
            if r.get("seen") is False and not (r.get("ref") and r["ref"] in bodies)
            and int(turn) - int(r.get("turn") or 0) <= within
            and _fits(words, _bag(r, scene))]
    return fits[0] if len(fits) == 1 else None


def keep_as_resident(scene, actor, place_id: str) -> dict:
    """A person who already has a body, recorded as somebody who lives in the settlement
    `place_id` is in and is found at that place: their existing record if they have one,
    else a new one with a life rolled like anybody's — and a resident's, whatever the roll
    said about travelling, because that is what they are. Used for a keeper an older save
    stood up where there is no longer a counter for them (`keepers.retire_stale_masters`).
    """
    from . import places as places_mod

    have = of_ref(scene, actor.ref)
    if have is not None:
        return have
    if not hasattr(scene, "population") or scene.population is None:
        scene.population = {}
    pid = _next_id(scene)
    home = places_mod.location_of(place_id) or getattr(scene, "location_id", None)
    life = lives.roll(f"{home}|{pid}", phrase=str(actor.name),
                      body=str(getattr(actor, "appearance", "") or ""),
                      used_frames=used_frames(scene, home)).as_dict()
    life["mobility"] = "resident"
    clock = int(getattr(scene, "clock_minutes", 0) or 0)
    met_before = bool(getattr(actor, "true_name", ""))
    rec = {
        "id": pid, "phrase": str(actor.name), "home": home, "spot": place_id,
        "seen_at": place_id, "first_seen": clock, "last_seen": clock,
        "last_met": None, "turn": 0, "ref": actor.ref,
        "tier": "acquaintance" if met_before else "glimpse", "life": life,
    }
    scene.population[pid] = rec
    return rec


def seen(scene, rec: dict) -> None:
    """The party has seen this person, here, now: the fact everything about where they
    are next is reckoned from (`rules/residency.py`)."""
    from . import residency

    at = getattr(scene, "at", None)
    rec["seen_at"] = at
    # Heard of no longer: seen is the default, and a default is not written (§2.0).
    rec.pop("seen", None)
    residency.observe(rec, getattr(scene, "location_id", None) or "", at or "",
                      int(getattr(scene, "clock_minutes", 0) or 0))


def met(scene, rec: dict | None) -> None:
    """The player has engaged this person: spoken with them. `last_met` is what the
    "since last we met" catch-up will compare the clock with, and the finder's `met` ring
    reads it; before 2026-09-27 nothing wrote it, and that ring was always empty."""
    if rec is None:
        return
    rec["last_met"] = int(getattr(scene, "clock_minutes", 0) or 0)
    if rec.get("tier", "glimpse") == "glimpse":
        rec["tier"] = "acquaintance"
    seen(scene, rec)


def of_ref(scene, ref: str) -> dict | None:
    """The record behind an actor, if the actor came from one."""
    for rec in (getattr(scene, "population", {}) or {}).values():
        if rec.get("ref") == ref:
            return rec
    return None


# --- finding somebody the player describes ------------------------------------------------
#
# Scope, not semantic search (docs/the-population.md §6). On a 2,000-person set, word match
# with a synonym table picked the right person 70% of the time inside the scene and 4.6%
# across everybody, because 97% of references fit more than one person globally — which no
# retriever fixes. Inform and TADS resolve by scope first and then ask "which do you
# mean"; so does this. Rings, first clean answer wins:
#
#     here → seen in the last hour → met → this settlement → everyone
#
# Within a ring a person FITS only if every word the player used matches something the
# record says (its phrase, its work, its face, the name its actor carries) after the
# synonym table. One fit is them; several is a question; none moves out a ring. Nothing is
# ranked by word statistics: BM25 committed to wrong answers more often than plain matching
# in the same measurement.
#
# Measured before an index was reached for (2026-09-25): a search that misses, and so
# scans every ring, took 66 ms over 5,000 records — against a turn of seconds. SQLite FTS5
# waits for a population that needs it (tests/test_finding_someone.py holds the line).

HERE = "here"
ELSEWHERE = "elsewhere"
AMBIGUOUS = "ambiguous"
NONE = "none"

# Words that say whether somebody is a man, a woman, a boy or a girl. A record that says
# none of them is not ruled out by the player's — the prose's "someone mending nets" is
# who "the woman mending nets" means — but a record that says another one is.
_GENDERED = frozenset({"woman", "man", "boy", "girl"})
_SELLS = frozenset({"baker", "butcher", "brewer", "stallholder", "merchant", "peddler"})

# Words that are somebody, for `names_a_person`: kin and the generic nouns a description
# is built on. Only asked of a phrase that opens with a possessive, where "her husband" is
# a person and "her name" is not.
_PERSON_WORDS = frozenset({
    "woman", "man", "boy", "girl", "child", "person", "figure", "stranger", "friend",
    "brother", "sister", "mother", "father", "son", "daughter", "wife", "husband", "kin",
    "cousin", "uncle", "aunt", "nephew", "niece", "grandmother", "grandfather", "master",
    "mistress", "servant", "companion", "partner", "lover", "rival", "guard", "man-at-arms",
    "apprentice", "boss", "employer", "captain", "lord", "lady", "sir", "folk", "people",
    "family", "neighbour", "neighbor", "helper", "assistant", "mate", "crew", "retainer",
})
_POSSESSIVE = re.compile(r"^\s*(?:her|his|their|its|my|your|our)\s+", re.I)


def names_a_person(phrase: str) -> bool:
    """Whether a phrase the plan declared as somebody is a person at all.

    Measured live 2026-09-27: "I ask her name." came back as `introduce who="her name"`,
    a person the population then rolled a life for and the prose check made the narrator
    write in ("lost the scene, re-introduced her name"). Narrow on purpose: only a phrase
    that opens with a possessive is asked, and it passes when any word is a person —
    kin, a trade, or a generic noun ("her husband", "his apprentice"). Everything else
    ("a hooded figure", "a Korvu porter") is the plan's to declare.
    """
    # "somewhere" is a place: live 2026-09-27, "I find somewhere to sleep until morning"
    # came back as `introduce who="somewhere"`, a person the scene then held.
    if " ".join(str(phrase or "").lower().split()) in ("somewhere", "anywhere", "nowhere",
                                                        "everywhere", "someplace"):
        return False
    if not _POSSESSIVE.match(str(phrase or "")):
        return True
    rest = _POSSESSIVE.sub("", str(phrase))
    words = {_stem(w) for w in re.findall(r"[a-z][a-z'-]*", rest.lower())}
    if words & {_stem(w) for w in _PERSON_WORDS}:
        return True
    return any(t.startswith("work:") for t in _tokens(rest))

# Searches that found nobody, for the turn log (`drain_misses`): the synonym table grows
# from what real play missed, not from guesses.
_MISSES: list[dict] = []


# The past of the verbs people are described by. Measured live 2026-09-27: "the woman who
# sold me bread" missed the record "somebody selling bread in the market", because the
# suffix rules make "selling" into "sell" and leave "sold" as "sold".
_IRREGULAR = {
    "sold": "sell", "bought": "buy", "told": "tell", "sang": "sing", "sung": "sing",
    "caught": "catch", "fought": "fight", "wore": "wear", "worn": "wear", "held": "hold",
    "brought": "bring", "taught": "teach", "made": "make", "gave": "give", "given": "give",
    "spoke": "speak", "spoken": "speak", "drove": "drive", "driven": "drive", "rode": "ride",
    "ridden": "ride", "led": "lead", "kept": "keep", "swept": "sweep", "wept": "weep",
    "slept": "sleep", "dug": "dig", "hung": "hang", "sewn": "sew", "fed": "feed",
    "met": "meet", "ran": "run", "threw": "throw", "thrown": "throw", "carried": "carry",
    "sweeping": "sweep",
}


def _stem(w: str) -> str:
    w = w.lower().strip("'-")
    if w in _IRREGULAR:
        return _IRREGULAR[w]
    if w.endswith("'s"):
        w = w[:-2]
    if len(w) > 5 and w.endswith("ing"):
        w = w[:-3]
    elif len(w) > 4 and w.endswith("ed"):
        w = w[:-2]
    elif len(w) > 4 and w.endswith("es") and not w.endswith(("ees", "oes")):
        w = w[:-2]
    elif len(w) > 3 and w.endswith("s") and not w.endswith("ss"):
        w = w[:-1]
    # "sitting" and "sits", "scarred" and "scar": a doubled consonant left by the cut.
    if len(w) > 3 and w[-1] == w[-2] and w[-1] not in "lsaeiou":
        w = w[:-1]
    return w


_CANON: dict | None = None


def _canon() -> dict:
    """{stem: canonical token} from the synonym groups and the occupations' own words."""
    global _CANON
    if _CANON is None:
        t = lives.tables()
        syn = t["synonyms"]
        canon: dict = {}
        for group in syn["groups"]:
            for w in group:
                canon[_stem(w)] = _stem(group[0])
        # A trade is found by any word the occupation table already reads it from — the
        # player's "blacksmith" is the prose's "smith". One-word matches only: "leather
        # apron" is how the prose MAKES a tanner, not how a player names one.
        for occ in t["occupations"]:
            for w in [occ["id"], *str(occ["name"]).split(), *(occ.get("match") or [])]:
                if " " not in w:
                    canon.setdefault(_stem(w), f"work:{occ['id']}")
        implies = {_stem(k): {_stem(x) for x in v} for k, v in syn["implies"].items()}
        still = {_stem(w) for w in syn["still"]}
        _CANON = {"canon": canon, "implies": implies, "still": still}
    return _CANON


def _tokens(text: str) -> list[str]:
    c = _canon()
    out = []
    for w in re.findall(r"[a-z][a-z'-]*", str(text or "").lower()):
        s = _stem(w)
        if s in c["still"] or len(s) < 2:
            continue
        out.append(c["canon"].get(s, s))
    return out


def _bag(rec: dict, scene) -> set[str]:
    """Everything a record answers to."""
    c = _canon()
    life = rec.get("life") or {}
    said = [rec.get("phrase", ""), life.get("face", ""), life.get("work_name", "")]
    actor = (getattr(scene, "people", {}) or {}).get(rec.get("ref") or "")
    if actor is not None:
        said += [str(getattr(actor, "name", "") or "")]
    bag = set()
    for text in said:
        bag.update(_tokens(text))
    # Anybody whose trade is selling answers to "seller": measured live 2026-09-27, "the
    # bread seller" read "seller" as a stallholder's word and missed the baker the prose
    # had written as "somebody selling bread".
    if life.get("work") in _SELLS:
        bag.add("sell")
    if life.get("work"):
        bag.add(f"work:{life['work']}")
    for tok in list(bag):
        bag |= c["implies"].get(tok, set())
    return bag


def _fits(words: list[str], bag: set[str]) -> bool:
    gendered = bool(bag & _GENDERED)
    for w in words:
        if w in bag:
            continue
        if w in _GENDERED and not gendered:
            continue
        return False
    return True


def where_now(rec: dict, scene, world=None):
    """Where this person is, as a `residency.Where`. Three answers, the first that holds:

    1. their body, if they have one: the engine moves bodies (`Engine.settle_people`);
    2. where the party saw them, if the party has not left that place since. The
       ruling: she "should stay there until i leave or something moves them";
    3. the schedule key or the road (`residency.whereabouts`).
    """
    from . import places as places_mod
    from . import residency

    clock = int(getattr(scene, "clock_minutes", 0) or 0)
    actor = (getattr(scene, "people", {}) or {}).get(rec.get("ref") or "")
    if actor is not None and getattr(actor, "at", None):
        return residency.where_of_place(str(actor.at), int(rec.get("last_seen") or 0))
    here = getattr(scene, "at", None)
    seen_at = rec.get("seen_at", rec.get("spot"))
    # Unplaced (a scene nobody has stood anywhere yet) is still one room. Somebody only
    # heard of was never seen anywhere, so the rule "she stays where you saw her" has
    # nothing to hold: the schedule places them (the speaker's spot is their WORK).
    if (rec.get("seen", True) is not False and (seen_at or "") == (here or "")
            and int(rec.get("last_seen") or 0) >= int(getattr(scene, "arrived", 0) or 0)):
        return residency.Where("place", places_mod.location_of(here or "") or
                               str(getattr(scene, "location_id", "") or ""), here or "")
    return residency.whereabouts(rec, clock, world, getattr(scene, "founded", None))


def _where(rec: dict, scene, world=None) -> str:
    """The place id a person is at now (see `where_now`)."""
    return where_now(rec, scene, world).place


def _rings(scene, world=None):
    from . import residency

    pop = list((getattr(scene, "population", {}) or {}).values())
    home = getattr(scene, "location_id", None)
    at = getattr(scene, "at", None)
    clock = int(getattr(scene, "clock_minutes", 0) or 0)
    taken: set[str] = set()
    where: dict[str, object] = {}

    def now(r):
        # A resident of another settlement with no body is in neither of the first
        # rings; asking their schedule would cost the whole population for nothing.
        if (r.get("home") != home and residency.mobility_of(r) == "resident"
                and not r.get("ref")):
            return None
        if r["id"] not in where:
            where[r["id"]] = where_now(r, scene, world)
        return where[r["id"]]

    def ring(name, keep):
        members = [r for r in pop if r["id"] not in taken and keep(r)]
        taken.update(r["id"] for r in members)
        return name, members

    def is_here(r):
        w = now(r)
        return w is not None and w.kind == "place" and w.place == at

    def in_town(r):
        w = now(r)
        return w is not None and w.kind in ("place", "home") and w.location == home

    yield ring(HERE, is_here)
    yield ring("recent", lambda r: int(r.get("last_seen") or 0) >= clock - 60)
    yield ring("met", lambda r: r.get("last_met") is not None)
    yield ring("settlement", in_town)
    yield ring("everyone", lambda r: True)


class Found(dict):
    """{"scope", "ring", "people"}: one of HERE / ELSEWHERE / AMBIGUOUS / NONE."""

    @property
    def scope(self) -> str:
        return self["scope"]

    @property
    def people(self) -> list[dict]:
        return self["people"]

    @property
    def ring(self) -> str:
        return self["ring"]


# --- "the woman Gorm spoke of": who told the player about them ----------------------------
#
# Measured on the owner's save, 2026-10-01: "I enter the house of the human woman Grom spoke
# of" logged `population-miss` seven times with the words human, woman, grom, speak. Two
# faults in one phrase. "Grom" is the player's slip for Gorm, the barkeep who had told them
# about her; and "spoke of" is no part of who she is — it says WHERE the player learned of
# her, which the record already holds as `heard_from`. Inform reaches out of scope for
# exactly the asking-about case (Recipe Book §6.2) and Eric Eve's Epistemology keeps the
# *familiar* flag for somebody known of and not seen (§5.5); a familiar person is the one a
# player names by who told them. So the clause is read off the phrase, the speaker is
# resolved to a ref, and among the people who fit the rest, the one heard of from that
# speaker is chosen.
#
# The slip: Damerau's 1964 count was that about 80% of misspellings are one insertion,
# deletion, substitution or transposition, and "Grom" for "Gorm" is one transposition.
# Tolerated only against the names of people the campaign holds (never every word of the
# phrase, where "man" is one letter from "men" and "map"), and only when one name is that
# close — two names in reach is a guess, and is not made.

_HEARD_VERBS = (r"(?:spoke\s+(?:of|about)|spoken\s+(?:of|about)|speaks\s+(?:of|about)|"
                r"talked\s+(?:of|about)|was\s+talking\s+about|"
                r"told\s+(?:me|us|you)\s+(?:of|about)|tells\s+(?:me|us|you)\s+(?:of|about)|"
                r"mentioned|mentions|described|pointed\s+out|sent\s+me\s+to)")
# Case matters for the name: "woman Grom" must not be read as a two-word name, so only the
# verbs and connectives are case-blind.
_HEARD = re.compile(
    r"(?:\s+(?i:that|who|whom))?\s+(?P<who>(?i:he|she|they|someone|somebody)|"
    r"(?i:the\s+)[a-z][\w'’-]+|[A-Z][\w'’-]+(?:\s+[A-Z][\w'’-]+)?)\s+"
    r"(?i:(?:had\s+|has\s+|just\s+|once\s+)?" + _HEARD_VERBS + r")\b"
    r"(?i:\s+(?:earlier|before|a\s+minute\s+ago|just\s+now|yesterday))?")
_PRONOUN_SPEAKER = frozenset({"he", "she", "they", "someone", "somebody"})
# Who the clause names, unresolved: anybody who told the player about somebody.
ANYONE = "?"


def _osa(a: str, b: str) -> int:
    """Optimal-string-alignment distance: Levenshtein plus the swap of two neighbours."""
    a, b = a.lower(), b.lower()
    d = [[0] * (len(b) + 1) for _ in range(len(a) + 1)]
    for i in range(len(a) + 1):
        d[i][0] = i
    for j in range(len(b) + 1):
        d[0][j] = j
    for i in range(1, len(a) + 1):
        for j in range(1, len(b) + 1):
            cost = 0 if a[i - 1] == b[j - 1] else 1
            d[i][j] = min(d[i - 1][j] + 1, d[i][j - 1] + 1, d[i - 1][j - 1] + cost)
            if i > 1 and j > 1 and a[i - 1] == b[j - 2] and a[i - 2] == b[j - 1]:
                d[i][j] = min(d[i][j], d[i - 2][j - 2] + 1)
    return d[len(a)][len(b)]


def _reach(word: str) -> int:
    """How many edits a name of this length tolerates: one up to five letters, two past."""
    return 1 if len(word) <= 5 else 2


def _known_names(scene) -> dict[str, str]:
    """{name word: ref} for the proper names of everybody the campaign holds a body for —
    the names the player can know, and so the only words a slip is corrected towards."""
    out: dict[str, str] = {}
    for ref, a in (getattr(scene, "people", {}) or {}).items():
        if getattr(a, "is_pc", False):
            continue
        for n in (getattr(a, "name", ""), getattr(a, "true_name", "")):
            for w in re.findall(r"[A-Z][a-z]{2,}(?![a-z])", str(n or "")):
                out.setdefault(w.lower(), ref)
    return out


def near_name(scene, word: str) -> tuple[str, str]:
    """(the name word, its ref) a word means, exactly or by one slip; ("", "") for none or
    for two names in reach."""
    names = _known_names(scene)
    w = str(word or "").lower()
    if len(w) < 3:
        return "", ""
    if w in names:
        return w, names[w]
    close = {n: r for n, r in names.items()
             if abs(len(n) - len(w)) <= _reach(n) and _osa(n, w) <= _reach(n)}
    if len(close) == 1:
        n, r = next(iter(close.items()))
        return n, r
    return "", ""


def speaker_of(scene, who: str) -> str:
    """The ref a hearsay clause's speaker names: by a proper name (a slip tolerated), or
    by every word of a descriptor the body goes by ("the barkeep" of "the barkeep"). A
    pronoun or nobody resolved is ANYONE: somebody told the player, it is not known who."""
    who = " ".join(str(who or "").split())
    if not who or who.lower() in _PRONOUN_SPEAKER:
        return ANYONE
    caps = re.findall(r"[A-Z][a-z]{2,}(?![a-z])", who)
    if caps:
        refs = {near_name(scene, w)[1] for w in caps} - {""}
        return refs.pop() if len(refs) == 1 else ANYONE
    want = set(_tokens(_ARTICLE.sub("", who)))
    if want:
        hits = [ref for ref, a in (getattr(scene, "people", {}) or {}).items()
                if not getattr(a, "is_pc", False)
                and want <= set(_tokens(str(getattr(a, "name", "") or "")))]
        if len(hits) == 1:
            return hits[0]
    return ANYONE


def heard_clause(phrase: str) -> tuple[str, str]:
    """(the phrase without its hearsay clause, the clause's speaker words) — ("the human
    woman", "Grom") from "the human woman Grom spoke of"; (phrase, "") with no clause."""
    padded = " " + str(phrase or "")
    m = _HEARD.search(padded)
    if not m:
        return str(phrase or ""), ""
    rest = (padded[:m.start()] + padded[m.end():]).strip(" ,")
    return " ".join(rest.split()), m.group("who").strip()


def heard_words(text: str) -> str:
    """The hearsay clause in a player's sentence as written ("Grom spoke of"), or ""."""
    m = _HEARD.search(" " + str(text or ""))
    if not m:
        return ""
    return " ".join(m.group(0).split())


def correct_names(scene, phrase: str) -> str:
    """The phrase with a near-miss proper name put right ("Grom's house" → "Gorm's
    house"), against the names of people the campaign holds."""
    def fix(m):
        word = m.group(0)
        n, _ref = near_name(scene, word)
        return n[:1].upper() + n[1:] if n and n != word.lower() else word
    # Letters only: "Grom's" is the name "Grom" and its possessive.
    return re.sub(r"(?<![\w'’-])[A-Z][a-z]{2,}(?![a-z])", fix, str(phrase or ""))


def find(scene, phrase: str, *, rings: tuple[str, ...] | None = None,
         log_miss: bool = True, world=None) -> Found:
    """The person that phrase means, by scope. `rings` limits the search to those rings.
    `world` lets a traveller's roads be walked (`rules/residency.py`); without it they are
    reckoned to stay where they were seen, and nothing reckoned so is stored.

    A hearsay clause ("Gorm spoke of", "the barkeep told me about") is read off first: it
    names who told the player about this person, and among those who fit the rest, the one
    heard of from that speaker is the one meant — searched across every ring allowed,
    because the woman Gorm spoke of is who was asked for even with another woman here."""
    said = str(phrase or "")
    rest, who = heard_clause(said)
    speaker = speaker_of(scene, who) if who else ""
    words = _tokens(correct_names(scene, rest))
    if not words or scene is None:
        return Found(scope=NONE, ring="", people=[])
    ringed = [(name, members) for name, members in _rings(scene, world)
              if rings is None or name in rings]
    if speaker:
        told = [(name, r) for name, members in ringed for r in members
                if (r.get("heard_from") == speaker if speaker != ANYONE
                    else bool(r.get("heard_from")))
                and _fits(words, _bag(r, scene))]
        if len(told) == 1:
            name, rec = told[0]
            return Found(scope=HERE if name == HERE else ELSEWHERE, ring=name, people=[rec])
        if told:
            return Found(scope=AMBIGUOUS, ring=told[0][0], people=[r for _n, r in told])
    for name, members in ringed:
        fits = [r for r in members if _fits(words, _bag(r, scene))]
        if len(fits) == 1:
            return Found(scope=HERE if name == HERE else ELSEWHERE, ring=name, people=fits)
        if fits:
            return Found(scope=AMBIGUOUS, ring=name, people=fits)
    # A clause naming somebody nobody heard of from them leaves the rest, which was still
    # searched above: "the woman Gorm spoke of" of a woman the prose wrote is that woman.
    phrase = rest
    # A description with a relative clause the record cannot answer to ("the woman who
    # waved at me" of a woman nobody saw wave) is still asking for the woman. "that" and
    # "whom" clauses too: measured on the 2026-09-28 playtest, "the girl that the
    # watchman described to me" searched for ["girl", "work:guard", "describ"] — the
    # watchman read as her trade — and missed.
    head = re.split(r"\s+(?:who|whom|that)\s+", str(phrase), maxsplit=1, flags=re.I)
    if len(head) == 2 and head[0].strip():
        return find(scene, head[0], rings=rings, log_miss=log_miss, world=world)
    if log_miss and getattr(scene, "population", None):
        _MISSES.append({"kind": "population-miss", "phrase": " ".join(said.split()),
                        "words": words})
    return Found(scope=NONE, ring="", people=[])


def drain_misses() -> list[dict]:
    """The searches that found nobody since last asked, for the turn log — each phrase
    once. Measured on the owner's save (2026-10-01): one turn wrote seven identical
    `population-miss` rows for "human woman Grom spoke of", because seven readers of the
    player's words each asked the finder; the synonym table needs the miss, not its echo."""
    out: list[dict] = []
    seen_rows: set[str] = set()
    for row in _MISSES:
        key = row.get("phrase", "")
        if key in seen_rows:
            continue
        seen_rows.add(key)
        out.append(row)
    _MISSES.clear()
    return out


def _the(phrase: str) -> str:
    p = " ".join(str(phrase or "").split())
    # "somebody selling bread" is "the one selling bread": measured live 2026-09-27, the
    # finder said "The somebody selling bread in the market is at the north crossing".
    if re.match(r"^(?:somebody|someone|a person)\b", p, re.I):
        rest = re.sub(r"^(?:somebody|someone|a person)\s*", "", p, flags=re.I)
        return f"the one {rest}".strip() if rest else "that person"
    p = re.sub(r"^(?:a|an|the|some)\s+", "", p, flags=re.I)
    return f"the {p}" if p else "that person"


def question(people: list[dict]) -> str:
    """ "Which do you mean — the woman at the well, or the woman mending nets?" """
    named = []
    for rec in people:
        n = _the(rec.get("phrase", ""))
        if n not in named:
            named.append(n)
    if len(named) > 4:
        named = named[:3] + ["somebody else"]
    if len(named) == 1:
        # Two people the prose described in the same words: said so, not "the X or the X".
        return f"There is more than one — which {named[0][4:]} do you mean?"
    return f"Which do you mean — {', '.join(named[:-1])}, or {named[-1]}?"


def _place_name(place_id: str, scene, world=None) -> str:
    from . import places as places_mod

    try:
        loc_id = places_mod.location_of(place_id)
        loc = world.get(loc_id) if world is not None else None
        known = places_mod.for_scene(loc or loc_id, place_id,
                                     founded=getattr(scene, "founded", None))
        place = places_mod.find(known, place_id)
        return str(getattr(place, "name", "") or "")
    except Exception:
        return ""


def seen_line(rec: dict, scene, world=None) -> str:
    """What asking around turns up about somebody who is not here: where they ARE.

    Until residency (2026-09-27) this could only say where they were SEEN, "was at the
    market square when you saw them", because that was all the campaign knew. Now it is
    reckoned (`where_now`): at another place in town at this hour, at home, in another
    town, on the road, or gone. Where a person is found is what any neighbour would say,
    so it is said; what they ARE (work, wants, temper) is never in this line.
    """
    from . import residency

    who = _the(rec.get("phrase", ""))
    here_loc = getattr(scene, "location_id", None) or ""
    clock = int(getattr(scene, "clock_minutes", 0) or 0)
    w = where_now(rec, scene, world)
    if w.kind == "place" and w.location == here_loc:
        name = _place_name(w.place, scene, world)
        return residency.sentence(f"{who} is at {name} at this hour, and is not here."
                                  if name else f"{who} is not here.")
    day = ""
    if w.kind == "home" and residency.mobility_of(rec) == "resident":
        day = _place_name(residency.resolve(residency.WORK, rec, w.location, world,
                                            getattr(scene, "founded", None)), scene, world)
    said = residency.line(who, w, here_loc=here_loc, clock=clock, world=world,
                          day_place=day)
    return said or residency.sentence(f"{who} is not here.")
