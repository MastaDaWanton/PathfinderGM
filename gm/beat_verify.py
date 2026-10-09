"""The round trip: read the finished beat back into the engine's vocabulary, and compare.

docs/beat-verify.md is the design record and the bench. The owner, 2026-10-03: *"we cant
really depend i think on just layering mechanical detection logic on top this will be an
endless loop"* — then *"could we have the interpretor/one of these smaller models read the
final text convert it back to json and make sure that it matches the expected actions?"*

Thirty-three `gm/checks` modules each re-read the page's English with their own regex,
and each new phrasing needed new code: "You move toward the anvil" was a walk out of the
smithy to one of them, "The clerk's eyes drop to the floor" a man down to another. This
module asks ONE question of the page instead — what does it say happened? — answered by a
schema-constrained model call whose every slot is an enum the ENGINE supplies at call time
(the places it knows, the refs here, the things in the pack, the parts of its day), and
then compares the answer with the engine's own outcomes in code. Code never decides what
an English sentence means; it decides whether a claim, once stated in the engine's words,
is true.

Prior art (docs/beat-verify.md has the numbers and what could not be sourced):
  * Wiseman, Shieber & Rush 2017 — an information-extraction model reads the generated
    text into (entity, value, type) records and they are compared with the source
    records (RG precision, CS precision/recall). Their extractor recalled ~60% of the
    relations and "erred" on ~8% of human-written text: the checker inherits its
    reader's errors, which is why the bench below measures the READER first.
  * QAGS (Wang, Cho & Lewis 2020) — ask questions of the output, answer them from both
    sides, compare. 32.5% of its source-side answers were wrong in their own error
    analysis. Here one side is not read at all: the engine's records are the answers.
  * RefChecker (Hu et al. 2024) — claim triplets beat other granularities; FRANK (Pagnoni
    et al. 2021) — time and discourse are the weak categories, which is why the hour is
    measured on its own row.
  * Claimify (Metropolitansky & Larson 2025) and NuExtract — abstaining beats guessing:
    every slot here has a "not stated" / "not listed" answer, and an unlisted thing is
    never judged.

**Every claim carries a quote**, validated in code as the page's own narration (speech is
blanked first: a character may say anything). A claim whose quote is not on the page is
dropped. That is the one guard against a reader that invents (Wiseman's 8%); the bench
measures what it costs in recall.

The interface is deliberately small, so lane N's beat reader (gm/beat_reader.py, being
built in parallel) can carry this read as one more question later:

    facts = facts_from(ctx)                  # the engine's side, closed vocabularies
    reading = read(text, facts, chat=...)    # the model's side, validated claims
    found = diff(reading.claims, facts)      # code: contradictions and omissions
"""
from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field

from . import speech

# On in the app; off in the test suite (tests/conftest.py), as the mentions labeller and
# the interpreter are: a turn test that scripts the model's replies in order would have
# one spent on this read. tests/test_beat_verify.py scripts its own replies.
ENABLED = True

# The values that mean "the engine has no name for it". A claim that lands on one of
# these is never judged — there is nothing of the engine's to compare it with — but it
# is kept on the reading, so the bench can see what the reader said.
UNLISTED_PLACE = "somewhere not listed"
NEW_PERSON = "someone not listed"
OTHER_THING = "something else"
FLOOR = "the floor"
NOBODY = "nobody"
UNSTATED = "unstated"
HOW = ("hurt", "down", "dead")

# The parts of the day the reader may name, each with the hours (0-23) at which a narrator
# may truthfully say it. Generous on purpose — the hour a narrator calls "night" at 19:00
# is not wrong, and a guard that argues with dusk is noise (the same judgement the regex
# check `gm/checks/time_of_day.py` made on the owner's saves; it retired into this module
# on 2026-10-03, docs/beat-verify.md, and its windows live on here). The engine's own eight slots
# (`residency._PARTS`) are three-hour bins named for a brief, not for prose: "the small
# hours" and "late evening" are not words a narrator's sky is read into, so the reader is
# offered the words prose uses and the windows map them back to the engine's clock.


def _hours(a: int, b: int) -> frozenset[int]:
    out, h = set(), a
    while True:
        out.add(h % 24)
        if h % 24 == b % 24:
            return frozenset(out)
        h += 1


PARTS: dict[str, frozenset[int]] = {
    "night": _hours(18, 6),
    "before dawn": _hours(2, 6),
    "dawn": _hours(4, 8),
    "morning": _hours(5, 11),
    "midday": _hours(10, 14),
    "afternoon": _hours(12, 18),
    "dusk": _hours(16, 21),
    "evening": _hours(16, 23),
}


@dataclass(frozen=True)
class Person:
    ref: str
    name: str
    what: str = ""
    pc: bool = False
    down: bool = False
    dead: bool = False
    # False for somebody the engine holds elsewhere in this town (`beat_reader.away_people`,
    # the list the beat reader is shown): offered to the reader so a beat that brings them
    # on stage is read as THEM, and judged — "someone not listed" is never judged.
    # Measured 2026-10-09 (docs/narrator-after-defeat.md): the two raiders who robbed the
    # player and went were narrated lunging at the wagon an hour later, and the read back
    # had no code for them, so nothing on the page was wrong to it.
    here: bool = True


@dataclass(frozen=True)
class Facts:
    """The engine's side of the comparison, in closed vocabularies. Built by
    `facts_from(ctx)` in the game and from the gold file on the bench — the same shape, so
    the bench measures exactly the comparison the game makes."""
    start: str                        # where the beat began (the place's name)
    end: str                          # where the engine holds the party now
    places: tuple[str, ...]           # every place the party can name
    went_by: tuple[str, ...] = ()     # the places a resolved walk passed through
    pack: tuple[str, ...] = ()        # what the player holds after the turn
    props: tuple[str, ...] = ()       # what lies here, unheld
    people: tuple[Person, ...] = ()
    clock: int | None = None
    outcomes: tuple[dict, ...] = ()   # this turn's outcomes, as dicts
    in_fight: bool = False
    pc_ref: str = "pc"

    def person(self, ref: str) -> Person | None:
        return next((p for p in self.people if p.ref == ref), None)

    @property
    def refs(self) -> tuple[str, ...]:
        return tuple(p.ref for p in self.people)

    def absent(self, ref: str) -> Person | None:
        """The person with this code when the engine holds them somewhere else, or None."""
        p = self.person(ref)
        return p if p is not None and not p.here else None

    @property
    def things(self) -> tuple[str, ...]:
        """The pack, what lies here, and what this turn's outcomes moved — the crate sold
        to the smith is in nobody's pack the moment the page describes the sale, and a
        reader with no word for it can only answer "something else" (the bench's own
        label check caught it)."""
        moved = [str(e.get("item")) for o in self.outcomes for e in o.get("effects") or ()
                 if isinstance(e, dict) and e.get("item")]
        return tuple(dict.fromkeys([*self.pack, *self.props, *moved]))

    def key(self) -> str:
        """An identity for the beat's facts: the cache below reads a sentence once per
        beat, however many times the repair asks."""
        return json.dumps([self.start, self.end, self.places, self.pack, self.props,
                           [p.ref for p in self.people], self.clock,
                           [o.get("intent_id") for o in self.outcomes]],
                          default=str, sort_keys=True)


@dataclass
class Claim:
    category: str          # move | hands | trade | harm | shown | arrived | left | hour
    slots: dict
    quote: str
    sentence: str = ""     # the page sentence the quote stands in, as written
    valid: bool = False
    why: str = ""          # why it was dropped, when it was

    def as_dict(self) -> dict:
        return {"category": self.category, **self.slots, "quote": self.quote,
                **({"dropped": self.why} if not self.valid else {})}


@dataclass
class Reading:
    claims: list[Claim] = field(default_factory=list)
    dropped: list[Claim] = field(default_factory=list)
    seconds: float = 0.0
    error: str = ""
    raw: str = ""
    model: str = ""

    def as_log(self) -> dict:
        return {"kind": "beat-verify", "claims": [c.as_dict() for c in self.claims],
                "dropped": [c.as_dict() for c in self.dropped], "seconds": self.seconds,
                "model": self.model, **({"error": self.error} if self.error else {})}


# --- the engine's side -----------------------------------------------------------------

def _name_of(place) -> str:
    return " ".join(str(getattr(place, "name", "") or "").split())


def facts_from(ctx) -> Facts:
    """The beat's facts, read off the engine at the check's run site (`BeatContext`)."""
    from rules import places as places_mod

    engine, scene = ctx.engine, ctx.scene
    try:
        known = tuple(engine.places()) + tuple(engine.open_ground())
    except Exception:  # noqa: BLE001 — a scene with no places still has people and things
        known = ()
    try:
        end = _name_of(engine.here())
    except Exception:  # noqa: BLE001
        end = ""
    was = places_mod.find(known, str(ctx.was_at or "")) if ctx.was_at else None
    start = _name_of(was) if was is not None else end
    outcomes = tuple(o if isinstance(o, dict) else o.as_dict() for o in ctx.outcomes)
    went_by: list[str] = []
    for o in outcomes:
        if o.get("status") == "refused":
            continue
        for e in o.get("effects") or ():
            if isinstance(e, dict):
                went_by += [str(w) for w in e.get("went_by") or ()]
    pc = scene.pc() if hasattr(scene, "pc") else None
    pack = tuple(str(k) for k in (getattr(pc, "goods", None) or {}))
    try:
        props = tuple(str(r.get("name") or "") for r in scene.props_here() if r.get("name"))
    except Exception:  # noqa: BLE001
        props = ()
    from .mentions import what_they_are

    people = []
    for ref, a in (getattr(scene, "actors", {}) or {}).items():
        dead = bool(getattr(a, "hp", 1) < 0 or a.has_state("state.down.dead"))
        people.append(Person(ref=str(ref), name=str(a.name), what=what_they_are(a),
                             pc=bool(getattr(a, "is_pc", False)),
                             down=bool(getattr(a, "is_down", False)), dead=dead))
    # And the people held elsewhere in this town: the beat reader's own list of them, one
    # definition, so the two readers of a beat cannot disagree about who is away.
    from . import beat_reader

    for p in beat_reader.away_people(scene):
        people.append(Person(ref=str(p["ref"]), name=str(p["name"]), here=False))
    clock = getattr(scene, "clock_minutes", None)
    return Facts(start=start, end=end,
                 places=tuple(dict.fromkeys(n for n in (_name_of(p) for p in known) if n)),
                 went_by=tuple(dict.fromkeys(went_by)), pack=pack, props=props,
                 people=tuple(people), clock=None if clock is None else int(clock),
                 outcomes=outcomes, in_fight=bool(getattr(scene, "in_encounter", False)),
                 pc_ref=str(getattr(pc, "ref", "pc") or "pc"))


# --- the question ---------------------------------------------------------------------

def _places(facts: Facts) -> list[str]:
    return list(dict.fromkeys([facts.start, *facts.places, UNLISTED_PLACE]))


def _who(facts: Facts) -> list[str]:
    return [*facts.refs, NEW_PERSON]


def _holders(facts: Facts) -> list[str]:
    return [*facts.refs, NEW_PERSON, FLOOR, NOBODY]


def schema(facts: Facts) -> dict:
    """The answer's shape: every slot an enum built from the engine, every property
    required. Measured on this stack (memory `ollama-schema-enforcement`, re-probed for
    the nested shapes in docs/beat-verify.md): required properties and enums hold, so
    nothing here is optional — an optional property gets skipped, so each list is
    required and may be empty, and code filters."""
    things = [*facts.things, OTHER_THING]
    away = [p.ref for p in facts.people if not p.here]
    s = {"type": "string"}

    def lst(props: dict) -> dict:
        return {"type": "array", "maxItems": 6,
                "items": {"type": "object", "properties": {**props, "quote": s},
                          "required": [*props, "quote"]}}

    return {"type": "object", "properties": {
        "player_ends_at": {"type": "object", "properties": {
            "place": {"type": "string", "enum": _places(facts)}, "quote": s},
            "required": ["place", "quote"]},
        "changed_hands": lst({"item": {"type": "string", "enum": things},
                              "from": {"type": "string", "enum": _holders(facts)},
                              "to": {"type": "string", "enum": _holders(facts)}}),
        "trades": lst({"item": {"type": "string", "enum": things},
                       "seller": {"type": "string", "enum": _who(facts)},
                       "buyer": {"type": "string", "enum": _who(facts)},
                       "settled": {"type": "boolean"}}),
        "harmed": lst({"who": {"type": "string", "enum": _who(facts)},
                       "how": {"type": "string", "enum": list(HOW)}}),
        "arrived": lst({"who": {"type": "string", "enum": _who(facts)}}),
        "left": lst({"who": {"type": "string", "enum": _who(facts)}}),
        # A LIST, one entry per sentence that says the hour. It was one object until
        # 2026-10-05, and one object is one claim: the owner's beat at 17:49 said "The
        # morning air is cold" and, a sentence later, "the gray morning"; the reader
        # reported the second, its repair held, and the first shipped untouched because
        # the slot had no room for it (sammy.json's beat-verify rows: 2 of 2 beats with a
        # wrong "morning" kept it in a sentence the reader never named).
        "time_of_day": lst({"part": {"type": "string", "enum": list(PARTS)}}),
        # Somebody held elsewhere whom the page shows here anyway, doing anything at all —
        # only on a beat where the engine holds somebody away, so every other beat is
        # asked exactly what it was. The departed raider "lunges again … at the axle of
        # the wagon" hurt nobody and arrived nowhere, and stood on the page all the same
        # (2026-10-09, docs/narrator-after-defeat.md).
        #
        # Offered every code, and only the away are judged: with the away codes alone the
        # first live run read "Vyraxys is busy at the front" as the raider — the reader
        # wanted to list the wagon master and the enum had no room for him (an enum
        # guarantees the vocabulary, not the reading: docs/beat-reader.md).
        #
        # Tried and taken out: an `attacks` slot (who goes at whom, landing or not). On
        # the bench it took the blows the reader had been reporting as harm — harm claims
        # recall 12/14 -> 8/14 on the same beats, the harm alarm 2/6 -> 1/6 — the slot
        # competing with its neighbour (CLAUDE.md: a model asked for N things answers in
        # parallel), and `shown_here` alone caught the departed raiders (6/6, then 5/6 on
        # the final bench run; docs/narrator-after-defeat.md).
        **({"shown_here": lst({"who": {"type": "string", "enum": _who(facts)}})}
           if away else {}),
    }, "required": ["player_ends_at", "changed_hands", "trades", "harmed", "arrived",
                    "left", "time_of_day", *(["shown_here"] if away else [])]}


_SYSTEM = (
    "You read a passage of a story told to a player (\"you\") and report what the "
    "NARRATOR says happens in it, in the codes given. Never report what a character only "
    "says aloud inside quotation marks, plans, offers or imagines. Every answer copies the "
    "passage's own words exactly into \"quote\", from the narration outside quotation "
    "marks. Leave a list empty when the passage claims nothing of that kind; most passages "
    "claim very little.\n"
    "player_ends_at: where the passage leaves the player. The place they began in when "
    "they stay there — moving about inside it (to a counter, a table, toward someone, "
    "across the room) is staying. \"somewhere not listed\" when they go out to somewhere "
    "the list does not have, such as the street. quote is \"\" when they stay.\n"
    "changed_hands: a thing that passes from one holder to another — taken, handed over, "
    "picked up, set down. from/to are codes, \"the floor\" or \"nobody\".\n"
    "trades: a sale or purchase. settled is true only when the narrator says it is done "
    "(paid, the goods taken in exchange); false when it is offered, refused, put off or "
    "still being haggled.\n"
    "harmed: somebody physically hurt in the passage — hurt (struck, wounded, burned), "
    "down (unconscious, collapsed and unable to fight), dead. Looking down, kneeling, "
    "being tired or afraid is not harm.\n"
    "arrived / left: somebody who comes into, or goes out of, the place during the "
    "passage, or whom it says is no longer there. Not the player.\n"
    "time_of_day: EVERY sentence in which the narrator says what time of day it is NOW "
    "— the light, the sky, the hour — one entry per sentence, even when two sentences "
    "say different hours. Empty when it never says; never a time somebody mentions or "
    "plans for.")

_DEMO_USER = (
    "The player began this passage at: the toll house\n"
    "Places: the toll house, the ferry landing, the fish market, the river road, "
    "somewhere not listed\n"
    "People: pc: Ashka Verel — the player (\"you\"); c4: Dunmar Oake — ferryman; "
    "c5: the drover — commoner\n"
    "Things: lantern, coil of rope, eel basket, something else\n\n"
    "Passage:\n"
    "The lamps of the toll house gutter in the dawn wind. You cross to the counter and "
    "set your lantern down on it. Dunmar Oake picks it up, turns it over, and slides three "
    "coppers across to you; the sale is done. 'Mind the drover,' he says. 'He'll want it "
    "back by evening, and he'll break your arm for it.' The drover's eyes drop to his "
    "boots. Behind him a boy in a wet cap slips out into the rain, and you follow him out "
    "onto the river road.")
_DEMO_ANSWER = {
    "player_ends_at": {"place": "the river road",
                       "quote": "you follow him out onto the river road"},
    "changed_hands": [{"item": "lantern", "from": "pc", "to": "c4",
                       "quote": "Dunmar Oake picks it up"}],
    "trades": [{"item": "lantern", "seller": "pc", "buyer": "c4", "settled": True,
                "quote": "the sale is done"}],
    "harmed": [], "arrived": [],
    "left": [{"who": "someone not listed",
              "quote": "a boy in a wet cap slips out into the rain"}],
    "time_of_day": [{"part": "dawn", "quote": "gutter in the dawn wind"}]}

_DEMO2_USER = (
    "The player began this passage at: the fish market\n"
    "Places: the toll house, the ferry landing, the fish market, the river road, "
    "somewhere not listed\n"
    "People: pc: Ashka Verel — the player (\"you\"); c4: Dunmar Oake — ferryman; "
    "c5: the drover — commoner\n"
    "Things: coil of rope, eel basket, something else\n\n"
    "Passage:\n"
    "You stoop and lift the eel basket from the cobbles onto your hip. "
    "You move toward the eel stalls and stop beside the drover. He looks at your coil "
    "of rope and shakes his head: he will not buy it, not tonight. 'Tomorrow morning, "
    "maybe,' he says. Dunmar Oake staggers back as the drover's fist cracks into his jaw, "
    "and drops senseless to the cobbles. A watchman comes in from the street. Overhead the "
    "stars are out. The evening chill comes up off the river.")
_DEMO2_ANSWER = {
    "player_ends_at": {"place": "the fish market", "quote": ""},
    "changed_hands": [{"item": "eel basket", "from": "the floor", "to": "pc",
                       "quote": "You stoop and lift the eel basket from the cobbles"}],
    "trades": [{"item": "coil of rope", "seller": "pc", "buyer": "c5", "settled": False,
                "quote": "he will not buy it, not tonight"}],
    "harmed": [{"who": "c4", "how": "hurt",
                "quote": "the drover's fist cracks into his jaw"},
               {"who": "c4", "how": "down", "quote": "drops senseless to the cobbles"}],
    "arrived": [{"who": "someone not listed",
                 "quote": "A watchman comes in from the street"}],
    "left": [],
    "time_of_day": [{"part": "night", "quote": "Overhead the stars are out"},
                    {"part": "evening", "quote": "The evening chill comes up off the river"}]}


def _ask(text: str, facts: Facts) -> str:
    people = []
    for p in facts.people:
        desc = "the player (\"you\")" if p.pc else (p.what or "")
        if not p.here:
            desc = (desc + ", not here").strip(", ")
        elif p.dead:
            desc = (desc + ", dead").strip(", ")
        elif p.down:
            desc = (desc + ", down").strip(", ")
        people.append(f"{p.ref}: {p.name}" + (f" — {desc}" if desc else ""))
    return (f"The player began this passage at: {facts.start}\n"
            f"Places: {', '.join(_places(facts))}\n"
            f"People: {'; '.join(people)}\n"
            f"Things: {', '.join([*facts.things, OTHER_THING])}\n\n"
            f"Passage:\n{text}")


# When the engine holds somebody away (`Person.here` False), and only then, the question
# grows the `shown_here` slot: one paragraph of instruction and the second demonstration
# with an away man in it. Every other beat is asked word for word what it was asked
# before. Measured on the bench (2026-10-09): with the paragraph and the demonstration
# shown on every beat, the beats with nobody away lost harm claims they had read before
# (12 -> 9 of 14; "the commoner lunges forward, slamming their weight into you" no
# longer hurt the player) — the slot competed even where it could not apply. Split like
# this, the 50 earlier bench beats get identical messages and scored as on master.
_SYSTEM_AWAY = (
    "\nPeople marked \"not here\" are somewhere else. shown_here: only those of them the "
    "passage nonetheless shows here and now, doing or saying anything — not one only "
    "remembered, spoken of or imagined; usually nobody. Report what it has them do under "
    "the other lists with their code too.")
_DEMO2_AWAY_USER = (_DEMO2_USER.replace(
    "c5: the drover — commoner\n", "c5: the drover — commoner; c6: the bargeman — not here\n")
    .replace("A watchman comes in", "The bargeman leans on the rail of the gangway, watching "
             "you. A watchman comes in"))
# Something the away man does that is no harm and no arrival: a first cut had him swing a
# boathook at the player and miss, and a demonstrated miss teaches "a blow at you is no
# harm". Leaning on a rail teaches only the new slot.
_DEMO2_AWAY_ANSWER = dict(_DEMO2_ANSWER, shown_here=[
    {"who": "c6", "quote": "The bargeman leans on the rail of the gangway"}])


def messages(text: str, facts: Facts) -> list[dict]:
    away = any(not p.here for p in facts.people)
    return [{"role": "system", "content": _SYSTEM + (_SYSTEM_AWAY if away else "")},
            {"role": "user", "content": _DEMO_USER},
            {"role": "assistant", "content": json.dumps(_DEMO_ANSWER)},
            {"role": "user", "content": _DEMO2_AWAY_USER if away else _DEMO2_USER},
            {"role": "assistant", "content": json.dumps(
                _DEMO2_AWAY_ANSWER if away else _DEMO2_ANSWER)},
            {"role": "user", "content": _ask(text, facts)}]


def _raw_prompt(msgs: list[dict]) -> list[dict]:
    """The same conversation for a model whose Ollama template is the bare prompt
    (`TEMPLATE {{ .Prompt }}` — the Osmosis-Structure build pulled 2026-10-03): the chat
    is rendered in its base model's own turn markers (Qwen3's ChatML), as ONE user
    message, or the system turn and the demonstrations never reach it."""
    parts = [f"<|im_start|>{m['role']}\n{m['content']}<|im_end|>" for m in msgs]
    return [{"role": "user", "content": "\n".join(parts) + "\n<|im_start|>assistant\n"}]


def bare_template(model: str) -> bool:
    return "osmosis" in str(model or "").lower()


# --- the quote, validated ---------------------------------------------------------------

_FOLD = str.maketrans({"’": "'", "‘": "'", "“": '"', "”": '"', "—": " ", "–": " ",
                       "-": " "})


def _norm(text: str) -> str:
    text = str(text or "").translate(_FOLD).lower()
    text = re.sub(r"[^\w' ]+", " ", text)
    return " ".join(text.split())


def _sentences(text: str) -> list[tuple[str, str]]:
    from .checks._page import page_sentences

    return page_sentences(text)


MIN_QUOTE_WORDS = 3

# The words an hour's quote must carry one of (`validate`): the day's parts and the sky's
# lights. Not "light", "dark" or "gloom", which a cellar has at noon.
_HOUR_WORD = re.compile(
    r"\b(?:(?:pre )?dawn\w*|daybreak|sunrise|sun|suns|sunlit|sunlight|sunset|sundown|"
    r"morning\w*|noon\w*|midday|afternoon\w*|evening\w*|dusk\w*|twilight|gloaming|"
    r"night\w*|midnight|moon\w*|stars?|starlight|starlit|first light|daylight|day)\b")


def place_quote(quote: str, sentences: list[tuple[str, str]]) -> str:
    """The page sentence a quote stands in — narration only — or "" when it is nowhere on
    the page's narration. A quote across two sentences belongs to the first."""
    q = _norm(quote)
    if len(q) < 3:
        return ""
    for written, narration in sentences:
        if q in _norm(narration):
            return written
    joined = [(_norm(n), w) for w, n in sentences]
    whole = " ".join(n for n, _ in joined)
    at = whole.find(q)
    if at < 0:
        return ""
    pos = 0
    for n, written in joined:
        if pos <= at < pos + len(n) + 1:
            return written
        pos += len(n) + 1
    return ""


# --- reading the model's answer ------------------------------------------------------------

def claims_of(answer: dict, facts: Facts) -> list[Claim]:
    """The model's answer as claims, before validation; anything off the schema is
    simply not a claim (a hosted provider does not enforce the schema)."""
    out: list[Claim] = []
    if not isinstance(answer, dict):
        return out
    where = answer.get("player_ends_at") or {}
    if isinstance(where, dict):
        place = str(where.get("place") or "")
        if place and place != facts.start and place in _places(facts):
            out.append(Claim("move", {"place": place}, str(where.get("quote") or "")))
    for key, cat, slots in (("changed_hands", "hands", ("item", "from", "to")),
                            ("trades", "trade", ("item", "seller", "buyer", "settled")),
                            ("harmed", "harm", ("who", "how")),
                            ("shown_here", "shown", ("who",)),
                            ("arrived", "arrived", ("who",)),
                            ("left", "left", ("who",))):
        for row in answer.get(key) or ():
            if isinstance(row, dict) and all(s in row for s in slots):
                out.append(Claim(cat, {s: row[s] for s in slots},
                                 str(row.get("quote") or "")))
    # A list now; a single object is still read, so an answer recorded before the list
    # (the bench's gold file, a test's scripted reply) means what it meant.
    hours = answer.get("time_of_day") or []
    for hour in ([hours] if isinstance(hours, dict) else hours):
        if isinstance(hour, dict) and str(hour.get("part") or "") in PARTS:
            out.append(Claim("hour", {"part": str(hour["part"])},
                             str(hour.get("quote") or "")))
    return out


def validate(claims: list[Claim], text: str, facts: Facts) -> tuple[list[Claim], list[Claim]]:
    """(kept, dropped). A claim is kept only when its quote is the page's own narration
    and its slots are the engine's own values."""
    sentences = _sentences(text)
    kept, dropped = [], []
    allowed = {"item": set(facts.things) | {OTHER_THING},
               "from": set(_holders(facts)), "to": set(_holders(facts)),
               "seller": set(_who(facts)), "buyer": set(_who(facts)),
               "who": set(_who(facts)), "how": set(HOW), "place": set(_places(facts)),
               "part": set(PARTS)}
    seen: set[str] = set()
    for c in claims:
        bad = [k for k, v in c.slots.items()
               if k in allowed and str(v) not in allowed[k]]
        if c.category == "trade" and not isinstance(c.slots.get("settled"), bool):
            bad.append("settled")
        if bad:
            c.why = f"not the engine's value: {', '.join(bad)}"
            dropped.append(c)
            continue
        # Three words at least: "the exchange" quoted from "you turn your back on the man
        # and the exchange" was read as a sale (the first bench run, 2026-10-03). A quote too
        # short to say anything is a reader leaning on one word, which is the regex's
        # failure in a model's clothes.
        if len(_norm(c.quote).split()) < MIN_QUOTE_WORDS:
            c.why = "the quote is too short to say anything"
            dropped.append(c)
            continue
        # An hour's quote names the hour or the sky. Offered a LIST for the hour
        # (2026-10-05), the reader filled it with weak cues: "the dim light around him"
        # came back as evening and cost a clean beat a false alarm on the bench (1 of 36
        # clean beats; 0 before the list). A closed vocabulary, checked the way the quote's
        # presence is checked: it decides whether the quote could say the hour at all, and
        # leaves what it says to the reader.
        if c.category == "hour" and not _HOUR_WORD.search(_norm(c.quote)):
            c.why = "the quote names no hour and no sky"
            dropped.append(c)
            continue
        c.sentence = place_quote(c.quote, sentences)
        if not c.sentence:
            c.why = "the quote is not the page's narration"
            dropped.append(c)
            continue
        # The same claim about the same sentence is one claim. The same claim about two
        # sentences is two: "the heat licks across his face" and "his hands clutching his
        # scorched arms" both burn the man, and the first bench run kept only the first —
        # whose second read was "no", so the burn the engine never rolled shipped.
        same = json.dumps([c.category, c.slots, c.sentence], sort_keys=True, default=str)
        if same in seen:
            continue
        seen.add(same)
        c.valid = True
        kept.append(c)
    return kept, dropped


def read(text: str, facts: Facts, *, chat=None, model: str = "", host: str = "",
         provider: str = "ollama", api_key: str = "", num_predict: int = 700) -> Reading:
    """One call: the page read back as claims, validated. Never raises — a failed call
    is a reading with `error` set and no claims, and the turn goes on."""
    result = Reading(model=model)
    if not str(text or "").strip():
        return result
    if chat is None:
        from . import client

        chat = client.chat
    msgs = messages(text, facts)
    if bare_template(model):
        msgs = _raw_prompt(msgs)
    started = time.monotonic()
    try:
        reply = chat(msgs, model, host, as_json=True, think=False, temperature=0.0,
                     num_predict=num_predict, provider=provider, api_key=api_key,
                     schema=schema(facts))
        result.raw = reply.text
        answer = reply.json()
        result.claims, result.dropped = validate(claims_of(answer, facts), text, facts)
    except Exception as exc:  # noqa: BLE001 — a failed read must never lose the turn
        result.error = f"{type(exc).__name__}: {str(exc)[:160]}"
    result.seconds = round(time.monotonic() - started, 2)
    return result


# --- the diff: code only ------------------------------------------------------------------

@dataclass
class Discrepancy:
    kind: str              # "contradiction" | "omission"
    category: str          # the claim category, or the outcome's for an omission
    fact: str              # the engine's fact, in words the repair can name
    sentence: str = ""     # the page sentence (contradictions)
    line: str = ""         # the engine's own sentence, for the backstop
    claim: Claim | None = None
    ref: str = ""          # who an `absent` contradiction is about


def _resolved(facts: Facts) -> list[dict]:
    return [o for o in facts.outcomes if o.get("status") != "refused"]


def _effects(o: dict) -> list[dict]:
    return [e for e in o.get("effects") or () if isinstance(e, dict)]


def _head(name: str) -> str:
    from rules import holding

    return holding.head_of(str(name or "")) or str(name or "").lower()


def _same(a: str, b: str) -> bool:
    return bool(a) and bool(b) and _head(a) == _head(b)


def _moves_of_things(facts: Facts) -> list[tuple[str, str, str]]:
    """(item, from, to) for every thing a resolved outcome moved this turn. An effect
    written before `from`/`to` existed names its receiver as `ref`."""
    out = []
    for o in _resolved(facts):
        for e in _effects(o):
            if not e.get("item"):
                continue
            kind = str(e.get("kind") or "")
            if kind == "sold":
                out.append((str(e["item"]), str(e.get("ref") or facts.pc_ref),
                            str(e.get("to") or "")))
            elif kind in ("bought",):
                out.append((str(e["item"]), str(e.get("from") or ""),
                            str(e.get("ref") or facts.pc_ref)))
            elif "from" in e or "to" in e:
                out.append((str(e["item"]), str(e.get("from") or ""), str(e.get("to") or "")))
            elif kind == "give":
                out.append((str(e["item"]), "", str(e.get("ref") or "")))
    return out


_TRADE_OPS = ("sell", "buy")
_HARM_OPS = ("attack", "cast", "damage", "full_attack", "maneuver", "coup_de_grace",
             "hazard", "use_ability")


def _refusal_line(o: dict) -> str:
    return str(o.get("for_a_person") or "").strip() or str(o.get("tell") or "").strip()


def _hour(facts: Facts) -> int | None:
    return None if facts.clock is None else (int(facts.clock) % (24 * 60)) // 60


def _not_here(p: Person, c: Claim) -> Discrepancy:
    """The page has somebody the engine holds elsewhere here: hurt, arriving or in a fight.
    The fact the repair names is where they are not, and that nothing brought them back —
    the engine's own doors (an arrival, an encounter, `defeat.settle`) bring people."""
    return Discrepancy(
        "contradiction", "absent",
        f"{p.name} is not here: they are somewhere else, and nothing has brought them back. "
        f"Nothing {p.name} does happens in this place.", c.sentence, "", c, ref=p.ref)


def diff(claims: list[Claim], facts: Facts, text: str = "") -> list[Discrepancy]:
    """The page's claims against the engine's outcomes and state. Code only.

    Precision is what matters most here: a false alarm costs a good sentence. So a claim
    is judged only where the engine holds the fact outright — a person's state, the pack,
    the place it put the party, a resolved or refused sale, the clock — and anything the
    engine has no record of (a thing "not listed", a newcomer, a wound in a scene where
    nothing rolled harm) is left alone."""
    out: list[Discrepancy] = []
    moved = facts.end != facts.start
    refused_moves = [o for o in facts.outcomes if o.get("status") == "refused"
                     and o.get("op") in ("travel", "journey", "venture", "found")]
    things_moved = _moves_of_things(facts)
    pc = facts.pc_ref

    for c in claims:
        if not c.valid:
            continue
        s = c.slots
        if c.category == "move":
            place = s["place"]
            if not moved:
                why = next((_refusal_line(o) for o in refused_moves if _refusal_line(o)), "")
                out.append(Discrepancy(
                    "contradiction", "move",
                    f"The player did not move{': ' + why if why else ''}. They are still at "
                    f"{facts.start}.", c.sentence,
                    next((str(o.get("for_a_person") or "") for o in refused_moves
                          if o.get("for_a_person")), "") or f"You are still at {facts.start}.",
                    c))
            elif place not in (facts.end, UNLISTED_PLACE) and place not in facts.went_by:
                out.append(Discrepancy(
                    "contradiction", "move",
                    f"The player is at {facts.end}, not {place}.", c.sentence,
                    f"You are at {facts.end}.", c))
        elif c.category == "hands":
            item, frm, to = str(s["item"]), str(s["from"]), str(s["to"])
            # "nobody" on the receiving end is a thing used up, tipped out or lost — the
            # pouch whose contents were tipped into a hand read as the pouch given away
            # (first bench run). Nothing the engine records answers it, so it is not judged.
            if item == OTHER_THING or frm == to or (frm == pc and to == NOBODY):
                continue
            held = any(_same(item, p) for p in facts.pack)
            out_of_pc = any(_same(item, i) and f == pc for i, f, _t in things_moved)
            into_pc = any(_same(item, i) and t == pc for i, _f, t in things_moved)
            if frm == pc and held and not out_of_pc:
                out.append(Discrepancy(
                    "contradiction", "hands",
                    f"Nothing changed hands: the player still carries the {item}.",
                    c.sentence, "", c))
            elif to == pc and not held and not into_pc:
                out.append(Discrepancy(
                    "contradiction", "hands",
                    f"The player does not have the {item}: nothing gave it to them.",
                    c.sentence, "", c))
        elif c.category == "trade":
            item, seller, buyer = str(s["item"]), str(s["seller"]), str(s["buyer"])
            if pc not in (seller, buyer):
                continue
            trades = [o for o in facts.outcomes if o.get("op") in _TRADE_OPS]
            done = [o for o in trades if o.get("status") != "refused"]
            refused = [o for o in trades if o.get("status") == "refused"]
            if s["settled"] and not done:
                why = _refusal_line(refused[0]) if refused else ""
                out.append(Discrepancy(
                    "contradiction", "trade",
                    "Nothing was sold or bought: " + (why or "no sale was made this turn."),
                    c.sentence, why, c))
            elif not s["settled"] and done and (item == OTHER_THING or any(
                    _same(item, e.get("item")) for o in done for e in _effects(o))):
                out.append(Discrepancy(
                    "contradiction", "trade",
                    f"The sale went through: {_refusal_line(done[0])}", c.sentence,
                    _refusal_line(done[0]), c))
        elif c.category == "harm":
            who = str(s["who"])
            p = facts.person(who)
            if p is None:
                continue
            if not p.here:
                out.append(_not_here(p, c))
                continue
            how = s["how"]
            if how == "dead" and not p.dead:
                out.append(Discrepancy(
                    "contradiction", "harm", f"{p.name} is not dead.", c.sentence, "", c))
            elif how == "down" and not (p.down or p.dead):
                out.append(Discrepancy(
                    "contradiction", "harm",
                    f"{p.name} is not down: still on their feet and able to act.",
                    c.sentence, "", c))
            elif how == "hurt":
                harmed = {str(e.get("ref") or "") for o in _resolved(facts)
                          for e in _effects(o)
                          if e.get("kind") in ("damage", "condition", "ability_damage")}
                rolled = any(o.get("op") in _HARM_OPS for o in facts.outcomes)
                if who not in harmed and rolled and not (p.down or p.dead):
                    out.append(Discrepancy(
                        "contradiction", "harm",
                        f"Nothing the engine resolved hurt {p.name}: they are untouched.",
                        c.sentence, "", c))
        elif c.category == "shown":
            # Somebody the engine holds elsewhere cannot act here, whatever they do: the
            # departed raiders' lunges (2026-10-09). Somebody here, listed by the reader
            # all the same, is not judged — the slot offers every code (`schema`).
            gone = facts.absent(str(s["who"]))
            if gone is not None:
                out.append(_not_here(gone, c))
        elif c.category in ("arrived", "left"):
            who = str(s["who"])
            p = facts.person(who)
            if p is None or p.pc:
                continue
            if not p.here:
                # Gone and not brought back by anything the engine did: they are not here.
                # A `left` of somebody already away is simply true.
                if c.category == "arrived":
                    out.append(_not_here(p, c))
                continue
            came = any(str(e.get("ref") or "") == who
                       and e.get("kind") in ("introduce", "spawn", "arrive", "enter",
                                             "position", "moved", "left", "leave")
                       for o in _resolved(facts) for e in _effects(o))
            if not came:
                verb = "has been here all along" if c.category == "arrived" else "is still here"
                out.append(Discrepancy(
                    "contradiction", "presence", f"{p.name} {verb}.", c.sentence, "", c))
        elif c.category == "hour":
            h = _hour(facts)
            if h is not None and h not in PARTS[s["part"]]:
                from rules import residency

                out.append(Discrepancy(
                    "contradiction", "hour",
                    f"It is {residency.time_words(int(facts.clock))}, not "
                    f"{s['part']}: the engine keeps the clock.", c.sentence, "", c))

    out += _omissions(claims, facts, text)
    return out


def _omissions(claims: list[Claim], facts: Facts, text: str) -> list[Discrepancy]:
    """What the engine did (or refused) that the page never says. Only the trade, the
    one place the owner measured it (2026-10-03, playtest item 8: the refusal "the one
    thing the player needed to read, was nowhere on it"), and only when the page does not
    even name the thing — an omission's repair appends the engine's sentence, and the
    reader's recall is the ceiling on knowing it is missing (Wiseman's extractor recalled
    ~60%), so a page that names the crate is given the benefit of the doubt."""
    out: list[Discrepancy] = []
    page = _norm(speech.unquoted(text)) if text else ""
    for o in facts.outcomes:
        if o.get("op") not in _TRADE_OPS:
            continue
        line = _refusal_line(o)
        if not line:
            continue
        items = [str(e.get("item")) for e in _effects(o) if e.get("item")] or \
                [str((o.get("params") or {}).get("item") or "")]
        items = [i for i in items if i]
        said = [c for c in claims if c.valid and c.category == "trade"
                and (not items or str(c.slots.get("item")) == OTHER_THING
                     or any(_same(c.slots.get("item"), i) for i in items))]
        named = any(i and _head(i) in page.split() for i in items)
        if said or named or _norm(line) in page:
            continue
        out.append(Discrepancy("omission", "trade", line, "", line))
    return out


# --- the second read: a contradiction is asked about once more before it costs a sentence --

def _name(facts: Facts, ref: str) -> str:
    if ref == facts.pc_ref:
        return "you (the player)"
    p = facts.person(ref)
    if p is not None:
        # A descriptor name reads as a person only with its article: "is man in a stained
        # leather jerkin physically hurt" is not a question a reader answers yes to.
        name = str(p.name)
        if name[:1].islower() and not name.lower().startswith(("the ", "a ", "an ")):
            name = f"the {name}"
        return name
    return {NEW_PERSON: "somebody", FLOOR: "the floor", NOBODY: "nobody"}.get(ref, ref)


def question(d: Discrepancy, facts: Facts) -> str:
    """The contradiction's claim as one closed question about one sentence, written from
    the claim's slots in code. "" for a discrepancy that is not asked (an omission)."""
    c = d.claim
    if c is None:
        return ""
    s = c.slots
    if c.category == "move":
        return (f"Does this sentence say that you (the player) have left {facts.start} and "
                f"are now somewhere else — not just moving about inside {facts.start}?")
    if c.category == "hands":
        # Not "passes from you to the smith": asked that way, gemma answered "no" to
        # "Korvu takes the crate with a grunt" — the sentence never says "from you", and a
        # people's name is not plainly the smith (probe of 2026-10-03, 0 of 2 such
        # sentences confirmed). The direction is the first read's; this asks only whether
        # the thing moved at all.
        if s["to"] == facts.pc_ref:
            return (f"Does this sentence say that the {s['item']} is picked up, taken or "
                    f"given to you?")
        # "left behind" is the narrator's commonest drop: asked without it, "the Brunt of
        # the Weight is left behind on the dirt floor" was refused twice of twice.
        return (f"Does this sentence say that the {s['item']} is taken, handed over, set "
                f"down, dropped or left behind?")
    if c.category == "trade":
        if s["settled"]:
            return ("Does this sentence say that a sale or purchase is completed — goods "
                    "and payment actually exchanged?")
        return "Does this sentence say that the sale did not happen — refused or put off?"
    if c.category == "harm":
        what = {"hurt": "physically hurt — struck, wounded or burned",
                "down": "unconscious or collapsed and unable to fight",
                "dead": "dead"}[s["how"]]
        return f"Does this sentence say that {_name(facts, s['who'])} is {what}?"
    if c.category == "shown":
        return (f"Does this sentence show {_name(facts, s['who'])} here, doing or saying "
                f"something now — not only remembered or spoken of?")
    if c.category == "arrived":
        return f"Does this sentence say that {_name(facts, s['who'])} comes into the place?"
    if c.category == "left":
        # A departure is told as a state as often as an act. Asked "does this sentence say
        # that Aelzeldra goes out of the place?" of "The Aelzeldra is gone.", gemma said
        # no three times of three (the bench's `gone-while-you-slept`, 2026-10-09) — the
        # owner's report, a creature the engine kept on its seam written gone while the
        # player slept, and the first read had it right every time. Probed the same day,
        # two asks each at temperature 0: "…has left the place, or is gone from it?" 0/2
        # on that sentence; "…is no longer here?" 2/2 on it but 0/2 on "a boy … slips out
        # into the rain"; this wording 2/2 on both, and 0/2 on each of two sentences that
        # keep the creature there ("is still there", "remains a silent, looming shadow").
        # The hands question learned the same about "left behind".
        return (f"Does this sentence say that {_name(facts, s['who'])} has gone — left, or "
                f"no longer here?")
    # The hour is not asked again. Asked "does this sentence say that it is dawn now?" of
    # "the pre-dawn light is just beginning to bleed into the gray", gemma said no — and
    # was right, it says before dawn, at 01:28, which is just as wrong. The part word is
    # the reader's approximation and the windows in `PARTS` are generous for that reason;
    # a second read that grades the word would only refuse true alarms.
    return ""


# No "answer no unless it plainly says it": with that line gemma refused 3 of 5 true
# contradictions on the probe of 2026-10-03, "The transaction is finalized." among them;
# without it, 1 of 5 (and the 4 false ones stayed refused either way).
_CONFIRM_SYSTEM = (
    "You answer one yes-or-no question about one sentence of a story told to a player "
    "(\"you\"). Answer from what the narrator says, not from what a character says aloud "
    "inside quotation marks.")


def confirm(found: list[Discrepancy], text: str, facts: Facts, *, chat=None,
            model: str = "", host: str = "", provider: str = "ollama",
            api_key: str = "") -> tuple[list[Discrepancy], list[Discrepancy], float]:
    """(kept, refuted, seconds). Each contradiction is put to the model again as a closed
    question about its sentence alone (`question`), and kept only on a "yes".

    Why a second read: a false alarm costs a good sentence, and on the first bench run
    three of the four were one reading's leap ("the man and the exchange" as a sale, a
    pouch's contents tipped out as the pouch given away). A narrow question about one
    sentence is the QAGS shape — ask, answer from the text, compare — and FActScore's and
    SAFE's verify-each-claim step, where the extraction above is their decomposition.
    Omissions are not asked: their repair appends the engine's own sentence and cuts
    nothing. A call that fails keeps the contradiction — the check's answer stands."""
    if chat is None:
        from . import client

        chat = client.chat
    kept, refuted = [], []
    started = time.monotonic()
    sentences = [w for w, _n in _sentences(text)]
    for d in found:
        q = question(d, facts)
        if d.kind != "contradiction" or not q or not d.sentence:
            kept.append(d)
            continue
        at = sentences.index(d.sentence) if d.sentence in sentences else -1
        before = sentences[at - 1] if at > 0 else ""
        if d.category == "absent" and d.ref:
            (kept if _shows(d, before, facts, chat, model, host, provider, api_key)
             else refuted).append(d)
            continue
        ask = ((f"The sentence before it, for context: {before}\n" if before else "")
               + f"The sentence: {d.sentence}\n\nQuestion: {q}")
        msgs = [{"role": "system", "content": _CONFIRM_SYSTEM},
                {"role": "user", "content": ask}]
        if bare_template(model):
            msgs = _raw_prompt(msgs)
        try:
            reply = chat(msgs, model, host, as_json=True, think=False, temperature=0.0,
                         num_predict=20, provider=provider, api_key=api_key,
                         schema={"type": "object",
                                 "properties": {"answer": {"type": "string",
                                                           "enum": ["yes", "no"]}},
                                 "required": ["answer"]})
            yes = str((reply.json() or {}).get("answer") or "") == "yes"
        except Exception:  # noqa: BLE001 — unconfirmable: the first read's answer stands
            yes = True
        (kept if yes else refuted).append(d)
    return kept, refuted, round(time.monotonic() - started, 2)


def _shows(d: Discrepancy, before: str, facts: Facts, chat, model, host, provider,
           api_key) -> bool:
    """The second read of an `absent` contradiction: not "does this sentence show the
    raider?" — asked that way of "Vyraxys is busy at the front, his voice now low and
    raspy", gemma answered yes twice of twice (the first live run after the fix,
    2026-10-09) — but WHO it shows, from the codes, compared in code with the person the
    first read named. QAGS's shape: answer the question from the text, then compare.
    A call that fails keeps the contradiction, as every second read does."""
    codes = [*facts.refs, NEW_PERSON, NOBODY]
    # Who each code is, as the first read was told it (`_ask`): what they are, and "not
    # here". Listed by name alone, "c29: Sorvika Sorvix" beside "c21: goblin with a scarred
    # cheek", the owner's goblin standing on the ridge was the away goblin 16 times of 16
    # (the eight goblin sentences of the name-turn replays, two asks each, 2026-10-09).
    people = "; ".join(
        f"{p.ref}: {p.name}" + (" (the player, \"you\")" if p.pc else
                                f" — {', '.join(x for x in (p.what, '' if p.here else 'not here') if x)}"
                                if (p.what or not p.here) else "")
        for p in facts.people)
    ask = ((f"The sentence before it, for context: {before}\n" if before else "")
           + f"The sentence: {d.sentence}\n\nPeople: {people}\n\nQuestion: which of these "
           f"people does this sentence show doing or saying something, here and now? "
           f"Every one it shows; \"{NEW_PERSON}\" for somebody else, \"{NOBODY}\" if none. "
           f"Not somebody only remembered, spoken of or imagined.")
    msgs = [{"role": "system", "content": _CONFIRM_SYSTEM.replace(
                "one yes-or-no question", "one question")},
            {"role": "user", "content": ask}]
    if bare_template(model):
        msgs = _raw_prompt(msgs)
    try:
        reply = chat(msgs, model, host, as_json=True, think=False, temperature=0.0,
                     num_predict=60, provider=provider, api_key=api_key,
                     schema={"type": "object", "properties": {"shown": {
                         "type": "array", "maxItems": 6,
                         "items": {"type": "string", "enum": codes}}},
                         "required": ["shown"]})
        return d.ref in [str(x) for x in (reply.json() or {}).get("shown") or []]
    except Exception:  # noqa: BLE001 — unconfirmable: the first read's answer stands
        return True


# --- the cache: a beat is read once, however many times the repair asks ----------------

_CACHE: dict[str, dict[str, list[Claim]]] = {}
_CACHE_LIMIT = 8


def _skey(sentence: str) -> str:
    return " ".join(str(sentence).split())


def read_beat(text: str, facts: Facts, **kw) -> Reading:
    """`read`, sentence-cached per beat. The repair path asks the member again after each
    rewrite (`GMAgent._repair_sentences` re-runs `find` on the candidate) and once more
    before the backstops; reading the whole beat each time would cost a model call per
    ask. So the claims are kept by the sentence their quote stands in, and a later text
    is read only for the sentences it has that the beat did not — a cut costs nothing,
    and a rewrite costs one short call over the rewritten sentence."""
    key = facts.key()
    held = _CACHE.setdefault(key, {})
    while len(_CACHE) > _CACHE_LIMIT:
        _CACHE.pop(next(iter(_CACHE)))
    sentences = [w for w, _n in _sentences(text)]
    new = [s for s in sentences if _skey(s) not in held]
    result = Reading(model=kw.get("model", ""))
    if new:
        fresh = read(" ".join(new), facts, **kw)
        result.seconds, result.raw, result.error = fresh.seconds, fresh.raw, fresh.error
        result.dropped = fresh.dropped
        if not fresh.error:
            for s in new:
                held[_skey(s)] = []
            for c in fresh.claims:
                held.setdefault(_skey(c.sentence), []).append(c)
    for s in sentences:
        result.claims += held.get(_skey(s), [])
    if new:
        global _LAST
        _LAST = result
    return result


# The last read that cost a call, for the turn log (`GMAgent._truth_pass` drains it):
# what the page was read as, and how long it took, beside the findings it led to.
_LAST: Reading | None = None


def take_last() -> dict | None:
    global _LAST
    out, _LAST = (_LAST.as_log() if _LAST is not None else None), None
    return out


def clear_cache() -> None:
    global _LAST
    _CACHE.clear()
    _LAST = None
