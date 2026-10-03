"""The beat reader: a finished beat read once, by a model, into closed answers code can check.

docs/structured-turn.md (Backward) and docs/beat-reader.md. The owner, 2026-10-03, after a
day of regexes that each fixed one phrasing and missed the next: *"we cant really depend i
think on just layering mechanical detection logic on top this will be an endless loop"*.
What the regexes cost that day, all live on gemma-4-12B:

  * "He is a large man" made a second smith (c15), who then joined the conversation;
  * "a grumpy man", in the man in the heavy coat's own speech, read as him naming himself;
  * "The Forge of the Broken Tide," and "…the back of the smithy" became two places with no
    landmark, though the speaker said "follow the main quay … the wharf";
  * a quoted player line became a person called `say "just trying…"`;
  * lines of "the man" booked to the servant carrying jugs.

So the reading of English moves here, and code only checks the answers:

  **A model reads; code validates against what the engine owns; the engine changes state.**

Two calls, because one call asked for everything answered worse (CLAUDE.md: a model asked
for N things answers in parallel — measured in docs/beat-reader.md):

  1. **people** — after the prose, on every groomed beat that has a person or a line in it.
     Each person mention code found (`mentions.find`: candidates only, over-found on
     purpose, since "nobody" is an answer) is answered with one of: a ref present, "new",
     "same as mN" (an earlier mention of the same newcomer), or "nobody". Each quoted line
     (`speech.spans`, the scanner — structure, not English) is answered with who says it
     (a ref, "you" for the player's character, a mention id, or "nobody") and to whom. Each
     newcomer is answered "here" (the beat shows them in the scene) or "elsewhere" (only
     spoken of), with the passage's own words for them. Every answer is an ENUM built here
     from the engine's refs at call time: Ollama enforces required properties and enums
     (6/6, memory `ollama-schema-enforcement`; re-probed for every construct used here,
     docs/beat-reader.md), so an answer outside the room cannot be generated.
  2. **places** — only when an NPC spoke. Which places a speaker named that this town does
     not have (the speaker's own words, a kind from `places.KINDS`/`DWELLINGS` or "other",
     and a landmark from this town's own place names), and which people a speaker put at
     one of this town's places.

Code then checks every answer against what the engine owns and drops — never repairs —
what fails, with the reason in `Reading.dropped` (a turn-log row):

  * a ref must be somebody present; a "same as" must point at an earlier newcomer;
  * a newcomer's words, a place's words and a person's words must be ON THE PAGE — the
    beat's narration for a newcomer, that speaker's own line for a place or a person
    (LangExtract's rule: an extraction that cannot be located in the source is not kept);
  * a place already on the map is not heard of (`places.find`); a kind outside the
    vocabulary is "" ; a landmark must be one of this town's places.

**When a call fails** the reading says so (`error`) and nothing is harvested from the beat
by any other means: no regex runs in its place (the owner's "endless loop"). The prose's
own speaker tags still stand — they are the writer's declarations, not a guess — and every
consumer writes one row saying the beat went unread. The rate is measured on the bench.

Off in the test suite (tests/conftest.py), as `mentions` and the interpreter are; tests that
need a reading stub the call's reply (`chat=`).
"""
from __future__ import annotations

import json
import re
import threading
import time
from dataclasses import dataclass, field

from . import mentions, speech
from .mentions import NOBODY, Attribution, Mention

ENABLED = True

NEW = "new"
YOU = "you"
HERE = "here"
ELSEWHERE = "elsewhere"
SAME = "same as "
HERE_SPEAKER = "where the speaker is"
NONE = "none"
OTHER = "other"

# The most of each a call answers. A beat that marks more people than this is rare; the
# rest stay unread (counted in the row), never guessed.
MAX_MENTIONS = 12
MAX_LINES = 12
# One beat telling of more places or placed people than this is a list, not talk. The
# places call lists the town's own places too (code sorts them out: `places.find`), so it
# has room for a few of those beside the new ones.
MAX_PLACES = 6
MAX_PLACED = 4


@dataclass
class Line:
    id: str
    a: int                    # the quotation's span in the beat, marks included
    b: int
    words: str                # what was said, marks stripped
    tag: str = ""             # the prose call's own speaker tag, if it wrote one
    by: str | None = None     # the reader's: a ref, YOU, a mention id, or NOBODY
    to: str | None = None

    def speaker(self, reading: "Reading") -> str:
        """Who said it, all told: a ref, YOU, or "" — a mention id resolved to its
        person (a ref, or the newcomer's root mention id while they have no body)."""
        by = str(self.by or "")
        if by in (YOU,):
            return YOU
        if by in reading.refs:
            return by
        m = reading.mention(by)
        if m is not None:
            return reading.person_of(m)
        return ""


@dataclass
class Newcomer:
    root: str                 # the first mention id of this person
    mentions: list[str]
    where: str                # HERE | ELSEWHERE
    words: str                # the page's words for them
    ref: str = ""             # once made a body (`play/aftermath/seen_people.py`)
    record: str = ""          # the population record


@dataclass
class HeardPlace:
    line: str
    words: str
    kind: str
    landmark: str             # a place id, or "" (the speaker's own place when HERE_SPEAKER)
    said_by: str = ""


@dataclass
class Placed:
    line: str
    words: str
    at: str                   # a place id of this settlement
    said_by: str = ""


@dataclass
class Reading(Attribution):
    """The beat's reading. An `Attribution` — every check that already reads mentions
    reads this — with the rest of the answers beside it."""
    lines: list[Line] = field(default_factory=list)
    newcomers: list[Newcomer] = field(default_factory=list)
    places: list[HeardPlace] = field(default_factory=list)
    placed: list[Placed] = field(default_factory=list)
    pronouns: dict = field(default_factory=dict)     # ref -> "he" | "she"
    names: list = field(default_factory=list)        # [{"who": ref | root id, "name"}]
    dropped: list[dict] = field(default_factory=list)
    refs: set = field(default_factory=set)          # the people here
    away: set = field(default_factory=set)          # known elsewhere in this town
    arrived: list = field(default_factory=list)     # away refs the passage shows here
    read: bool = False        # the people call answered
    places_read: bool = False
    asked: bool = False       # a call was made at all (False: nothing to read, or off)
    timings: dict = field(default_factory=dict)
    who_said: dict = field(default_factory=dict)   # mention id -> answer as given

    def mention(self, mid: str) -> Mention | None:
        return next((m for m in self.mentions if m.id == mid), None)

    def person_of(self, m: Mention) -> str:
        """A mention's person: a ref present, or the root mention id of a newcomer (or
        the newcomer's ref once they have a body), or ""."""
        if m.ref:
            return m.ref
        for n in self.newcomers:
            if m.id in n.mentions:
                return n.ref or n.root
        return ""

    def newcomer(self, root: str) -> Newcomer | None:
        return next((n for n in self.newcomers if n.root == root), None)

    def line_of(self, words: str) -> Line | None:
        rec = speech.speaker([{"line": ln.words, "id": ln.id} for ln in self.lines], words)
        return next((ln for ln in self.lines if ln.id == rec["id"]), None) if rec else None

    def unread_row(self, step: str) -> dict:
        """The row a consumer writes when there is no reading to apply: the beat went
        unread, and nothing was guessed in its place."""
        return {"kind": "beat-unread", "step": step,
                "why": self.error or ("the reader is off" if not ENABLED else "not read")}

    def as_log(self) -> dict:
        row = super().as_log()
        row.update({
            "kind": "beat-reading",
            "lines": len(self.lines),
            "lines_read": sum(1 for ln in self.lines if ln.by),
            "newcomers": [{"words": n.words, "where": n.where, "mentions": n.mentions}
                          for n in self.newcomers],
            "places": [{"words": p.words, "kind": p.kind, "landmark": p.landmark}
                       for p in self.places],
            "placed": [{"words": p.words, "at": p.at} for p in self.placed],
            **({"pronouns": dict(self.pronouns)} if self.pronouns else {}),
            **({"names": list(self.names)} if self.names else {}),
            **({"arrived": list(self.arrived)} if self.arrived else {}),
            **({"dropped": self.dropped} if self.dropped else {}),
            "read": self.read, "places_read": self.places_read,
            "seconds": self.timings,
        })
        return row


# --- what the reader is shown --------------------------------------------------------------

def lines_of(text: str, said=()) -> list[Line]:
    """Every quotation in the beat, numbered, with the prose call's tag where it wrote one."""
    out = []
    for a, b in speech.spans(text):
        words = text[a + 1:b - 1] if b - a >= 2 else ""
        if not words.strip():
            continue
        rec = speech.speaker(list(said or []), words)
        out.append(Line(id=f"q{len(out) + 1}", a=a, b=b, words=words.strip(),
                        tag=str((rec or {}).get("who") or "")))
    return out


def _cast_lines(cast: list[dict]) -> list[str]:
    out = []
    for p in cast:
        desc = "the player's character, \"you\" in the story" if p["pc"] else (p["what"] or "")
        if p["dead"]:
            desc = (desc + ", dead").strip(", ")
        out.append(f"{p['ref']}: {p['name']}" + (f" — {desc}" if desc else ""))
    return out


def marked(text: str, found: list[Mention], lines: list[Line]) -> str:
    """The beat with each person mention marked [mN: …] and each quoted line opened {qN}.

    Marks are placed by offset, mentions inside the narration only (`mentions.find` reads
    the narration), so a quotation that repeats a mention's words is not marked twice."""
    blank = speech.blanked(text)
    inserts: list[tuple[int, int, str]] = []        # (at, end, replacement)
    cursor = 0
    for m in found:
        # The mention's sentence was read from the unquoted text; find its words in the
        # narration in order, skipping speech.
        i = blank.find(m.phrase, cursor)
        if i < 0:
            i = blank.lower().find(m.phrase.lower(), cursor)
        if i < 0:
            continue
        inserts.append((i, i + len(m.phrase), f"[{m.id}: {text[i:i + len(m.phrase)]}]"))
        cursor = i + len(m.phrase)
    for ln in lines:
        inserts.append((ln.a, ln.a, f"{{{ln.id}}}"))
    inserts.sort(key=lambda x: (x[0], x[1]))
    out, at = [], 0
    for i, j, rep in inserts:
        if i < at:
            continue
        out.append(text[at:i])
        out.append(rep)
        at = j
    out.append(text[at:])
    return "".join(out)


# --- call 1: people and lines ------------------------------------------------------------

def people_schema(mention_ids: list[str], refs: list[str], line_ids: list[str],
                  vague: list[str], away: list[str] = ()) -> dict:
    """Every answer an enum the engine supplied. `vague`: the refs present with no gender
    and they/them pronouns, whose pronoun the page may settle (owner's ruling Q26)."""
    props: dict = {}
    earlier: list[str] = []
    for mid in mention_ids:
        props[mid] = {"type": "string",
                      "enum": list(refs) + list(away) + [NEW] + [SAME + e for e in earlier]
                      + [NOBODY]}
        earlier.append(mid)
    who = list(refs) + [YOU] + list(mention_ids) + [NOBODY]
    for lid in line_ids:
        props[lid] = {"type": "object",
                      "properties": {"by": {"type": "string", "enum": who},
                                     "to": {"type": "string", "enum": who}},
                      "required": ["by", "to"]}
    if mention_ids:
        props["new"] = {"type": "array", "maxItems": len(mention_ids),
                        "items": {"type": "object",
                                  "properties": {
                                      "mention": {"type": "string", "enum": mention_ids},
                                      "where": {"type": "string", "enum": [HERE, ELSEWHERE]},
                                      "words": {"type": "string"}},
                                  "required": ["mention", "where", "words"]}}
    # A name the page gives somebody: who (a person listed, not the player's character, or
    # a newcomer's mention) and the name as written. The name is the one free string here,
    # and it is checked: on the page, and nobody else's (`seen_people.name_them`).
    named = [r for r in refs if r != "pc"] + list(mention_ids)
    if named:
        props["names"] = {"type": "array", "maxItems": 3,
                          "items": {"type": "object",
                                    "properties": {"who": {"type": "string", "enum": named},
                                                   "name": {"type": "string"}},
                                    "required": ["who", "name"]}}
    # Somebody known elsewhere in town whom the passage shows here now: the cage owner met
    # in the back streets, written hunched over a ledger in the tavern. They walk in
    # (`Engine.walk_in`), never made twice — the owner's "saved if not already existing".
    if away:
        props["arrived"] = {"type": "array", "maxItems": 3,
                            "items": {"type": "string", "enum": list(away)}}
    for ref in vague:
        props[f"pronoun {ref}"] = {"type": "string", "enum": ["he", "she", "they", "not said"]}
    return {"type": "object", "properties": props, "required": list(props)}


_PEOPLE_SYSTEM = (
    "You read one passage of a story and answer questions about the people in it, from "
    "the passage alone. The people already in the scene are listed with a code.\n"
    "Marked phrases [m1: ...] are words that may refer to a person. For each, answer the "
    "code of the person it refers to; \"new\" for somebody not listed who is described "
    "for the first time; \"same as mN\" when it is the same newcomer as an earlier marked "
    "phrase; \"nobody\" when it refers to no single person: a crowd, a thing, somebody "
    "imagined or only compared to. A description of a listed person (\"he is a big man\") "
    "is that person, not somebody new.\n"
    "Numbered lines {q1} are words spoken aloud. For each, answer who says it (a code, "
    "\"you\" for the player's character, or the marked phrase of a newcomer) and who it is "
    "said to.\n"
    "Under \"new\", give each newcomer once, by their first marked phrase: \"here\" if the "
    "passage shows them in the scene now, \"elsewhere\" if they are only spoken of; and "
    "copy the passage's own words that best describe them.\n"
    "Under \"names\", a person's own name if the passage gives one (they say it, or the "
    "narration names them), exactly as written; leave it empty when nobody is named.\n"
    "Under \"arrived\", anybody from the people known but not here whom the passage shows "
    "here now; usually nobody.\n"
    "Under \"pronoun\", the pronoun the passage uses for that listed person, or \"not said\".")

# One demonstration carrying the hard cases measured 2026-10-03 (CLAUDE.md: instruction
# volume loses to demonstration volume): a predicate about a listed man ("He is a large
# man"), a listed man described rather than named, a newcomer shown and then spoken of
# again, a person only spoken of in the narration, the player's own quoted words, a crowd.
_PEOPLE_EXAMPLE_USER = (
    "People present:\n"
    "pc: Ashka Verel — the player's character, \"you\" in the story\n"
    "c4: the cooper — commoner\n"
    "c5: Dunmar Oake — ferryman\n\n"
    "Known, but not here — a mention may speak of one of them, but somebody the passage "
    "shows here and now is not one of them unless it says they came:\n"
    "c2: the harbour clerk\n"
    "c6: the net-mender with the limp\n\n"
    "Passage:\n"
    "[m1: The man at the barrel] does not look up. He is [m2: a broad man], his apron "
    "stiff with pitch. {q1}'Not today,' he says. You lean on the barrel. {q2}'I only want "
    "a word,' you say. Behind you [m3: a girl] with a basket of eels has stopped to "
    "watch, and [m4: the crowd] on the quay goes quiet. {q3}'Leave him be. Folk call me "
    "Tam,' [m5: the girl] calls to you. The cooper mutters that [m6: his brother] would "
    "have the hoops, if he were not away at sea, and that [m7: the clerk] still owes "
    "him. [m8: The net-mender] limps in out of the rain and sits by the stove.")
_PEOPLE_EXAMPLE_ASSISTANT = json.dumps({
    "m1": "c4", "m2": "c4", "m3": "new", "m4": "nobody", "m5": "same as m3", "m6": "new",
    "m7": "c2", "m8": "c6",
    "q1": {"by": "c4", "to": "you"}, "q2": {"by": "you", "to": "c4"},
    "q3": {"by": "m3", "to": "you"},
    "new": [{"mention": "m3", "where": "here", "words": "a girl with a basket of eels"},
            {"mention": "m6", "where": "elsewhere", "words": "his brother"}],
    "names": [{"who": "m3", "name": "Tam"}],
    "arrived": ["c6"],
    "pronoun c5": "not said"})


def people_messages(text: str, found: list[Mention], lines: list[Line], cast: list[dict],
                    vague: list[str], acting: str = "", facts: list[str] | None = None,
                    away: list[dict] = ()) -> list[dict]:
    body = ["People present:", *_cast_lines(cast)]
    if away:
        # Measured on the bench, 2026-10-03: with the list bare, "a lone laborer …
        # struggling with a stubborn, oversized crate" was answered as the man left
        # struggling with a crate at the docks.
        body += ["\nKnown, but not here — a mention may speak of one of them, but somebody "
                 "the passage shows here and now is not one of them unless it says they "
                 "came:",
                 *_cast_lines(list(away))]
    if acting:
        body.append(f"\nIt is {acting}'s turn.")
    if facts:
        body.append("What happened: " + " ".join(f for f in facts if f))
    body.append("\nPassage:\n" + marked(text, found, lines))
    return [{"role": "system", "content": _PEOPLE_SYSTEM},
            {"role": "user", "content": _PEOPLE_EXAMPLE_USER},
            {"role": "assistant", "content": _PEOPLE_EXAMPLE_ASSISTANT},
            {"role": "user", "content": "\n".join(body)}]


# --- call 2: places and people a speaker named ----------------------------------------------

def place_kinds() -> list[str]:
    from rules import places as places_mod

    return sorted({*places_mod.KINDS, *places_mod.DWELLINGS}) + [OTHER]


FIRST = "a new place"


def places_schema(line_ids: list[str], place_names: list[str]) -> dict:
    return {"type": "object", "properties": {
        "places": {"type": "array", "maxItems": MAX_PLACES, "items": {
            "type": "object", "properties": {
                "line": {"type": "string", "enum": line_ids},
                "words": {"type": "string"},
                # One place told of twice in other words ("The Forge of the Broken Tide"
                # … "the back of the smithy") is one place. Measured 2026-10-03: the
                # instruction alone did not stop two entries, and a "same as: entry N"
                # choice was not taken either (the forge and the smithy came back as two
                # unlinked entries, at temperature 0, twice); the place's other words, in
                # the same entry, are what the model writes when it knows they are one.
                "also called": {"type": "string"},
                # The kind as the model's own word, mapped onto the vocabulary in code
                # (`_kind_of`). Measured on the bench, 2026-10-03, with the kind an enum:
                # "the tunnels" came back "tannery", "the main thoroughfare" "theatre",
                # "the smithy" and "The Forge of the Broken Tide" "workshops" — 1 kind of
                # 3 right. Constrained decoding cuts the model's own word off at its first
                # letters and forces the nearest enum member that shares them; an enum
                # holds the vocabulary, not the reading.
                "kind": {"type": "string"},
                "near": {"type": "string",
                         "enum": list(place_names) + [HERE_SPEAKER, NONE]}},
            "required": ["line", "words", "also called", "kind", "near"]}},
        "people": {"type": "array", "maxItems": MAX_PLACED, "items": {
            "type": "object", "properties": {
                "line": {"type": "string", "enum": line_ids},
                "words": {"type": "string"},
                "at": {"type": "string", "enum": list(place_names)}},
            "required": ["line", "words", "at"]}}},
        "required": ["places", "people"]}


# Whether the places call lists the town's own places too (code sorts them out) or only
# the ones the town lacks (the model judges "not on the list"). Measured both ways on the
# bench, docs/beat-reader.md.
LIST_TOWN_PLACES = True

_PLACES_ALL = (
    "\"places\": every place a speaker names or points the player to, the town's own "
    "places among them — the speaker's own words for it, the kind of place it is (one of "
    "the kinds listed, or \"other\"), and which of the town's places it is near (\"where "
    "the speaker is\" for a place reached from the speaker's own spot, \"none\" if they do "
    "not say). When a speaker tells of the same place again in other words, it is ONE "
    "entry: put the other words under \"also called\" (\"\" when there are none). Leave "
    "out people, and anything that is not somewhere one could go.\n")
_PLACES_NEW = (
    "\"places\": each place a speaker tells of that is NOT one of the town's places "
    "listed — the speaker's own words for it, the kind of place it is (one of the kinds "
    "listed, or \"other\"), and which of the town's places it is near (\"where the speaker "
    "is\" for a place reached from the speaker's own spot, \"none\" if they do not say). "
    "When a speaker tells of the same place again in other words, it is ONE entry: put "
    "the other words under \"also called\" (\"\" when there are none). Leave out the town's "
    "own places, a part of one of them (the quay of the docks, the back room of the "
    "tavern), people, and anything that is not somewhere one could go.\n")


def _places_system() -> str:
    return ("You read what people say in a story and note two things.\n"
            + (_PLACES_ALL if LIST_TOWN_PLACES else _PLACES_NEW) + _PLACES_TAIL)


_PLACES_TAIL = (
    "\"people\": each single person (not a group) a speaker says is at one of the town's "
    "places — the speaker's own words for the person (never just \"he\" or \"she\"), and "
    "the place.\n"
    "Answer with empty lists when there are none.")

_PLACES_EXAMPLE_USER = (
    "The town's places: the gate; the market; the docks; the counting house; the "
    "tavern\nThe speakers are at: the market\n"
    "Kinds of place (words for the \"kind\" answer — NOT places this town has): docks, "
    "gate, house, market, smithy, tavern, warehouses, well, other\n\nLines:\n"
    "{q1} the ferryman: 'You'll want the salt-sheds. Follow the quay to the docks, and "
    "it's the long shed past the fish stalls. The Salt Sheds, they call it.'\n"
    "{q2} the ferryman: 'Ask the girl in the counting house, she keeps the tallies.'\n"
    "{q3} the ferryman: 'Or try the tavern. Or my sister's cottage, out back of here.'")
_SHEDS = {"line": "q1", "words": "The Salt Sheds", "also called": "the long shed",
          "kind": "warehouses", "near": "the docks"}
_COTTAGE = {"line": "q3", "words": "my sister's cottage", "also called": "",
            "kind": "house", "near": "where the speaker is"}
_GIRL = [{"line": "q2", "words": "the girl in the counting house", "at": "the counting house"}]


def _places_example() -> str:
    town = [{"line": "q1", "words": "the docks", "also called": "the quay", "kind": "docks",
             "near": "none"},
            {"line": "q3", "words": "the tavern", "also called": "", "kind": "tavern",
             "near": "none"}]
    places = ([_SHEDS, town[0], town[1], _COTTAGE] if LIST_TOWN_PLACES
              else [_SHEDS, _COTTAGE])
    return json.dumps({"places": places, "people": _GIRL})


def places_messages(lines: list[Line], names: dict, place_names: list[str],
                    here_name: str) -> list[dict]:
    body = ["The town's places: " + "; ".join(place_names),
            f"The speakers are at: {here_name}",
            "Kinds of place (words for the \"kind\" answer — NOT places this town has): "
            + ", ".join(place_kinds()), "", "Lines:"]
    for ln in lines:
        body.append(f"{{{ln.id}}} {names.get(ln.id, 'somebody')}: '{ln.words}'")
    return [{"role": "system", "content": _places_system()},
            {"role": "user", "content": _PLACES_EXAMPLE_USER},
            {"role": "assistant", "content": _places_example()},
            {"role": "user", "content": "\n".join(body)}]


# --- validation: the words must be on the page ---------------------------------------------

def _norm(text: str) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", str(text or "").lower().replace("’", "'")))


def on_page(words: str, source: str) -> bool:
    """Whether `words` are the source's own, give or take case, spacing and punctuation."""
    w = _norm(words)
    return bool(w) and f" {w} " in f" {_norm(source)} "


def _article_off(words: str) -> str:
    return re.sub(r"^(?:the|a|an|some|this|that|these|those)\s+", "", " ".join(str(words).split()),
                  flags=re.I)


# --- the read ------------------------------------------------------------------------------

def vague_refs(scene, cast: list[dict]) -> list[str]:
    """Refs present the world gave no gender, still they/them: the page may settle them."""
    out = []
    actors = getattr(scene, "actors", {}) or {}
    for p in cast:
        a = actors.get(p["ref"])
        if a is None or p["pc"]:
            continue
        if str(getattr(a, "gender", "") or "").strip():
            continue
        if str(getattr(a, "pronouns", "") or "they/them").lower() != "they/them":
            continue
        out.append(p["ref"])
    return out


def town_places(engine) -> tuple[list, object | None]:
    """(this town's places, the place here) as the engine has them, or ([], None)."""
    if engine is None:
        return [], None
    try:
        known = list(engine.places()) + list(engine.open_ground())
        here = engine.here()
    except Exception:  # noqa: BLE001 — no world to hand: no places to ask about
        return [], None
    return known, here


# The most people known elsewhere in this town the reader is shown beside the people here.
MAX_AWAY = 10


def away_people(scene) -> list[dict]:
    """People with a body elsewhere in this settlement, newest first — shown to the reader
    as "known, not here" so a mention of somebody the party just left is them, not a
    newcomer. Measured on the bench, 2026-10-03, first run: shown only the people here,
    the reader answered "new" for the merchant and the man left behind at the docks, the
    clerk whose door had just shut, and the watchman back at the gate — 6 of 14 bodies it
    would have made were people the engine already held."""
    from rules import places as places_mod

    here = getattr(scene, "at", None)
    loc = getattr(scene, "location_id", None)
    out = []
    for ref, a in (getattr(scene, "people", None) or {}).items():
        if getattr(a, "is_pc", False) or getattr(a, "at", None) == here:
            continue
        if places_mod.location_of(str(getattr(a, "at", "") or "")) != loc:
            continue
        if getattr(a, "hp", 1) < 0 or (hasattr(a, "has_state")
                                       and a.has_state("state.down.dead")):
            continue
        out.append({"ref": ref, "name": str(a.name),
                    "true": str(getattr(a, "true_name", "") or ""), "pc": False,
                    "what": "", "dead": False, "away": True})
    out.sort(key=lambda p: -int(re.sub(r"\D", "", p["ref"]) or 0))
    return out[:MAX_AWAY]


def read(text: str, scene, *, engine=None, said=(), acting: str = "",
         facts: list[str] | None = None, chat=None, model: str = "", host: str = "",
         provider: str = "ollama", api_key: str = "", places: bool = True) -> Reading:
    """The beat's reading. Never raises: a failed call leaves the code's certain answers
    (names `mentions.find` settled), says why in `error`, and guesses nothing else.

    The interface the other readers of a finished beat plug into (lane V's verify pass,
    docs/structured-turn.md): text in, a `Reading` out, `chat` the one door to a model
    (`client.chat`'s signature; a stub in the tests). Off when `ENABLED` is False unless a
    `chat` is passed — the suite's way of asking for a reading."""
    from .narration import _sentences

    cast = mentions.people(scene)
    away = away_people(scene)
    found = mentions.find(text, cast + away)
    reading = Reading(mentions=found)
    reading.sentences = {mentions._key(s) for s in _sentences(speech.unquoted(str(text or "")))}
    reading.refs = {p["ref"] for p in cast}
    reading.away = {p["ref"] for p in away}
    reading.lines = lines_of(text, said)
    ask_m = found[:MAX_MENTIONS]
    ask_l = reading.lines[:MAX_LINES]
    if len(found) > MAX_MENTIONS or len(reading.lines) > MAX_LINES:
        reading.dropped.append({"why": "too many to read in one call", "mentions":
                                len(found), "lines": len(reading.lines)})
    if (not ENABLED and chat is None) or not (ask_m or ask_l):
        return reading
    if chat is None:
        from . import client

        chat = client.chat
    reading.asked = True
    refs = [p["ref"] for p in cast]
    vague = vague_refs(scene, cast)
    # The places call does not wait for the people call: it is shown every line not
    # tagged to the player, and what came from a line the people call then gives to the
    # player or to nobody is dropped after. Two calls in flight cost one wait when Ollama
    # serves them together, and no more than two in a row when it does not.
    worker = None
    if places and ask_l:
        worker = threading.Thread(
            target=_read_places,
            args=(reading, scene, engine, chat, model, host, provider, api_key),
            daemon=True)
        worker.start()
    started = time.monotonic()
    try:
        reply = chat(people_messages(text, ask_m, ask_l, cast, vague, acting, facts, away),
                     model, host, as_json=True, think=False, temperature=0.0,
                     num_predict=180 + 14 * len(ask_m) + 22 * len(ask_l) + 12 * len(vague),
                     provider=provider, api_key=api_key,
                     schema=people_schema([m.id for m in ask_m], refs,
                                          [ln.id for ln in ask_l], vague,
                                          away=[p["ref"] for p in away]))
        reading.raw = reply.text
        _apply_people(reading, reply.json() or {}, ask_m, ask_l, refs, vague, text,
                      away=[p["ref"] for p in away])
        reading.read = True
        reading.labelled = True
    except Exception as exc:  # a failed read must never lose the turn
        reading.error = f"people: {type(exc).__name__}: {str(exc)[:160]}"
    reading.timings["people"] = round(time.monotonic() - started, 2)
    reading.seconds = reading.timings["people"]
    if worker is not None:
        worker.join()
        _places_from_npcs(reading, scene)
    return reading


def _places_from_npcs(reading: Reading, scene) -> None:
    """Keep only what the places call took from a line an NPC spoke, now the people call
    has said who spoke each; a line the reader gave to the player or to nobody tells of
    nothing. With no people answer, a line keeps its tag's speaker or tells of nothing."""
    actors = getattr(scene, "actors", {}) or {}
    lines = {ln.id: ln for ln in reading.lines}

    def speaker(line_id: str) -> str:
        ln = lines.get(line_id)
        if ln is None:
            return ""
        who = ln.speaker(reading) if reading.read and ln.by else ln.tag
        if not who or who == YOU or who == NOBODY:
            return ""
        a = actors.get(who)
        if a is not None and getattr(a, "is_pc", False):
            return ""
        return who

    for coll in (reading.places, reading.placed):
        kept = []
        for p in coll:
            who = speaker(p.line)
            if who:
                p.said_by = who
                kept.append(p)
            else:
                reading.dropped.append({"place" if coll is reading.places else "person":
                                        p.words[:80], "line": p.line,
                                        "why": "not a line an NPC spoke"})
        coll[:] = kept


def _apply_people(reading: Reading, ans: dict, ask_m, ask_l, refs, vague, text,
                  away=()) -> None:
    """Take the people call's answers that pass their checks; drop the rest with why."""
    narration = speech.unquoted(text)
    roots: dict[str, str] = {}               # mention id -> its newcomer's root id
    for m in ask_m:
        got = str(ans.get(m.id) or "")
        reading.who_said[m.id] = got
        if got in refs or got in away:
            m.model = got
        elif got == NOBODY:
            m.model = NOBODY
        elif got == NEW:
            m.model = NOBODY          # nobody listed: the checks read "not one of these"
            roots[m.id] = m.id
        elif got.startswith(SAME):
            earlier = got[len(SAME):]
            prior = reading.mention(earlier)
            if earlier in roots:
                m.model = NOBODY
                roots[m.id] = roots[earlier]
            elif prior is not None and prior.model and prior.model != NOBODY:
                # "the same as m4", m4 being somebody listed: that person. Measured on the
                # bench, 2026-10-03: "A man in a stained leather harness, a passing
                # carter" came back m5 = "same as m4", and m4 was the carter's ref.
                m.model = prior.model
            else:
                reading.dropped.append({"mention": m.id, "answer": got,
                                        "why": "same as a mention that is no newcomer"})
        elif got:
            reading.dropped.append({"mention": m.id, "answer": got, "why": "not a choice"})
    # Newcomers: each root once, with the reader's place for them and their words.
    given = {}
    for item in ans.get("new") or []:
        if not isinstance(item, dict):
            continue
        mid = str(item.get("mention") or "")
        if mid in roots and roots[mid] != mid:
            mid = roots[mid]               # named by a later mention: the same person
        if mid not in roots or mid in given:
            if mid and mid not in roots:
                reading.dropped.append({"mention": mid, "why": "listed as new but not "
                                        "answered new"})
            continue
        given[mid] = item
    for root in dict.fromkeys(roots.values()):
        m = reading.mention(root)
        item = given.get(root) or {}
        where = str(item.get("where") or "")
        words = " ".join(str(item.get("words") or "").split())
        if words and not on_page(words, narration):
            reading.dropped.append({"mention": root, "words": words[:80],
                                    "why": "the words are not the narration's"})
            words = ""
        if not words:
            words = m.phrase               # the marked words the reader called new
        if where not in (HERE, ELSEWHERE):
            reading.dropped.append({"mention": root, "why": "no answer for here or "
                                    "elsewhere: recorded, not made"})
            where = ""
        reading.newcomers.append(Newcomer(
            root=root, mentions=[k for k, v in roots.items() if v == root],
            where=where, words=_article_off(words)))
    # Lines.
    mids = {m.id for m in ask_m}
    who_ok = set(refs) | {YOU, NOBODY} | mids
    for ln in ask_l:
        got = ans.get(ln.id) or {}
        by = str(got.get("by") or "") if isinstance(got, dict) else ""
        to = str(got.get("to") or "") if isinstance(got, dict) else ""
        if by in who_ok:
            if by in mids and not reading.person_of(reading.mention(by)):
                reading.dropped.append({"line": ln.id, "answer": by,
                                        "why": "said by a mention that is nobody"})
                by = NOBODY
            ln.by = by
        if to in who_ok:
            ln.to = to
    for item in ans.get("names") or []:
        if not isinstance(item, dict):
            continue
        who = str(item.get("who") or "")
        name = " ".join(str(item.get("name") or "").split()).strip(" ,.;:!?'\"")
        person = who if who in refs else reading.person_of(reading.mention(who)) \
            if reading.mention(who) is not None else ""
        if not person or person == "pc" or not name:
            continue
        # The name exactly as the page writes it, a name's capital and all, and no longer
        # than a name runs: anything else is the model's paraphrase, not the page's word.
        if name not in text or not name[:1].isupper() or len(name.split()) > 4:
            reading.dropped.append({"name": name[:60], "who": person,
                                    "why": "not a name as the page writes it"})
            continue
        if not any(n["who"] == person for n in reading.names):
            reading.names.append({"who": person, "name": name})
    for ref in ans.get("arrived") or []:
        # Only somebody a mention of this passage was answered as: an arrival the passage
        # never mentions is the model's, not the page's.
        if ref in away and ref not in reading.arrived and any(
                m.model == ref for m in ask_m):
            reading.arrived.append(ref)
        elif ref in away:
            reading.dropped.append({"arrived": ref, "why": "no mention of them here"})
    for ref in vague:
        p = str(ans.get(f"pronoun {ref}") or "")
        if p in ("he", "she"):
            reading.pronouns[ref] = p


def _read_places(reading: Reading, scene, engine, chat, model, host, provider,
                 api_key) -> None:
    """Call 2, in a town with places to compare against: every line not tagged to the
    player, each shown with its tag's speaker or "somebody". It runs beside the people
    call, so it cannot wait for that call's speakers; `_places_from_npcs` keeps, after
    both, only what came from a line an NPC spoke."""
    from rules import places as places_mod

    known, here = town_places(engine)
    actors = getattr(scene, "actors", {}) or {}
    names: dict[str, str] = {}
    npc_lines = []
    for ln in reading.lines[:MAX_LINES]:
        a = actors.get(ln.tag)
        if a is not None and getattr(a, "is_pc", False):
            continue
        names[ln.id] = str(a.name) if a is not None else "somebody"
        npc_lines.append(ln)
    if not known or not npc_lines:
        return
    by_name: dict[str, object] = {}
    for p in known:
        nm = " ".join(str(p.name).split())
        if nm and nm.lower() not in {k.lower() for k in by_name}:
            by_name[nm] = p
    place_names = list(by_name)
    here_name = str(getattr(here, "name", "") or "here")
    started = time.monotonic()
    try:
        reply = chat(places_messages(npc_lines, names, place_names, here_name), model, host,
                     as_json=True, think=False, temperature=0.0,
                     num_predict=60 + 60 * (MAX_PLACES + MAX_PLACED),
                     provider=provider, api_key=api_key,
                     schema=places_schema([ln.id for ln in npc_lines], place_names))
        ans = reply.json() or {}
        reading.places_read = True
    except Exception as exc:  # noqa: BLE001
        reading.error = (reading.error + "; " if reading.error else "") + \
            f"places: {type(exc).__name__}: {str(exc)[:160]}"
        reading.timings["places"] = round(time.monotonic() - started, 2)
        return
    reading.timings["places"] = round(time.monotonic() - started, 2)
    lines = {ln.id: ln for ln in npc_lines}
    kinds = set(place_kinds()) - {OTHER}
    seen: set[str] = set()
    entries: list = []        # per answered item: its HeardPlace, or None when dropped
    # A place's other words ("also called") are read as a second entry that is the same
    # place as the first, so the one set of checks below holds for both names: each must
    # be in a speaker's own line, and a name the town already has makes the place that.
    expanded: list = []
    for item in ans.get("places") or []:
        if not isinstance(item, dict):
            continue
        expanded.append(item)
        alias = " ".join(str(item.get("also called") or "").split()).strip(" ,.;:!?")
        if alias:
            where = next((ln.id for ln in npc_lines if on_page(alias, ln.words)),
                         str(item.get("line") or ""))
            expanded.append({"line": where, "words": alias,
                             "same as": f"entry {len(expanded)}",
                             "kind": item.get("kind"), "near": item.get("near")})
    for item in expanded:
        ln = lines.get(str(item.get("line") or ""))
        words = " ".join(str(item.get("words") or "").split()).strip(" ,.;:!?")
        same = str(item.get("same as") or "")
        target = None
        if same.startswith("entry "):
            k = int(same.split()[-1]) - 1
            if 0 <= k < len(entries):
                target = entries[k]
                if target is None:
                    # The place it is the same as was dropped (on the map, not the
                    # speaker's words): so is this name for it.
                    entries.append(None)
                    continue
        if ln is None or not words:
            entries.append(None)
            continue
        if not on_page(words, ln.words):
            reading.dropped.append({"place": words[:80], "line": ln.id,
                                    "why": "the words are not the speaker's"})
            entries.append(None)
            continue
        name = _place_name(words)
        on_map = places_mod.find(known, name) or places_mod.find(known, _article_off(name))
        if on_map is not None:
            reading.dropped.append({"place": words[:80], "why": f"on the map already "
                                    f"({on_map.name})"})
            if target is not None and target in reading.places:
                # Another name for a place the town has: the first name was that place
                # too ("the Forge … in the back of the smithy", with a smithy on the map).
                reading.places.remove(target)
                reading.dropped.append({"place": target.words[:80],
                                        "why": f"the same place as {on_map.name}"})
            entries.append(None)
            continue
        kind = _kind_of(str(item.get("kind") or ""), kinds)
        if kind == "house" and re.search(r"(?:'s|’s)\b|\b(?:my|his|her|their|our|your)\b",
                                         words, re.I):
            # Somebody's house is `call_on`'s, which founds it the first time anybody
            # calls and knows whose it is (heard_places' own rule, kept).
            reading.dropped.append({"place": words[:80], "why": "somebody's house: "
                                    "call_on's"})
            entries.append(None)
            continue
        landmark = _landmark(str(item.get("near") or ""), here, by_name)
        if target is not None:
            # The same place again: one record. A proper name (a capitalised word past
            # the article) names it over a description; what the first entry lacked —
            # a kind, a landmark — the second may give.
            if _proper(name) and not _proper(target.words):
                target.words = name
            target.kind = target.kind or kind
            target.landmark = target.landmark or landmark
            entries.append(target)
            continue
        key = _norm(name)
        if key in seen:
            entries.append(next((p for p in reading.places if _norm(p.words) == key), None))
            continue
        seen.add(key)
        place = HeardPlace(line=ln.id, words=name, kind=kind, landmark=landmark,
                           said_by=ln.speaker(reading) or ln.tag)
        reading.places.append(place)
        entries.append(place)
    for item in ans.get("people") or []:
        ln = lines.get(str(item.get("line") or ""))
        words = " ".join(str(item.get("words") or "").split()).strip(" ,.;:!?")
        at = str(item.get("at") or "")
        if ln is None or not words or at not in by_name:
            continue
        if not on_page(words, ln.words):
            reading.dropped.append({"person": words[:80], "line": ln.id,
                                    "why": "the words are not the speaker's"})
            continue
        if not set(_norm(words).split()) - _PRONOUNS:
            # "He" at the shore: a pronoun is nobody the finder could ever match.
            reading.dropped.append({"person": words[:80], "why": "only a pronoun"})
            continue
        if here is not None and by_name[at].id == here.id:
            # Somebody at the speaker's own place is the page's to show, not hearsay
            # ("the men in the back", said in the counting house).
            reading.dropped.append({"person": words[:80], "why": "here, not elsewhere"})
            continue
        reading.placed.append(Placed(line=ln.id, words=words, at=by_name[at].id,
                                     said_by=ln.speaker(reading) or ln.tag))


def reconcile_tags(reading: "Reading", said) -> list[dict]:
    """Withdraw a prose-call speaker tag the reading contradicts. Edits `said` in place —
    `who` emptied, the claim kept in `was`, the reason in `doubt`, the shape `speech.lift`
    gives a tag naming nobody — so the "people" stage books the reader's speaker
    (`play/aftermath/speaker_real.py`). Returns one turn-log row per withdrawn tag.

    Replaces `judgement.doubt_tags`, which withdrew a tag when its own patterns — the
    player's "…,' you say", a head noun beside the line that was no word of the tagged
    person — made somebody else the speaker. Measured on the owner's 2026-10-03 save (item
    15): six beats of "the man" tagged to the servant carrying jugs. The writer's tag is
    a declaration made BEFORE the beat was groomed; the reader read the page as it stands.
    When the two disagree and the reader names somebody (a person here, the player, or a
    newcomer), the reader's answer is taken — measured on the bench, docs/beat-reader.md
    ("tags the reader overrules"). The reader's "nobody" withdraws nothing."""
    if not reading.read:
        return []
    rows = []
    for rec in said or []:
        who = str(rec.get("who") or "")
        if not who or rec.get("from"):
            continue
        ln = reading.line_of(str(rec.get("line") or ""))
        if ln is None or not ln.by or ln.by == NOBODY:
            continue
        read_as = ln.speaker(reading)
        if not read_as or read_as == who:
            continue
        rec["was"] = who
        rec["who"] = ""
        rec["doubt"] = f"the beat reader reads {read_as} as the speaker"
        rows.append({"kind": "speech-doubt", "was": who, "read_as": read_as,
                     "line": str(rec.get("line") or "")[:80]})
    return rows


def name_refusal(scene, world, ref: str, name: str) -> str:
    """Why `name` may not become `ref`'s name, or "" — the engine's checks on a name the
    reader read off the page, the same three `apply_introductions` made: the person has no
    proper name yet; nobody else here answers to it (`judgement._answers_to`, the Borin
    case of 2026-09-27); and it is not what one of the world's peoples is called (item 14,
    2026-10-03: "a man named Korvu", "the smith, Korvu" — Korvu is a people)."""
    from rules import names as names_mod

    from . import judgement

    actors = getattr(scene, "actors", {}) or {}
    who = actors.get(ref)
    if who is None or getattr(who, "is_pc", False):
        return "nobody here to name"
    held = str(who.name or "")
    if held[:1].isupper() and not held.lower().startswith(("the ", "a ", "an ")):
        return f"already named {held}"
    taken = judgement._answers_to(actors, who, name)
    if taken:
        return f"{taken} answers to it"
    if judgement._a_people(name, names_mod.people_names(world, scene)):
        return "a people of this world"
    return ""


_PRONOUNS = frozenset({"he", "she", "they", "him", "her", "them", "it", "his", "their",
                       "one", "someone", "somebody", "you", "i", "me", "we", "us"})


def _kind_of(word: str, kinds) -> str:
    """The model's word for the kind, as the settlement table's kind, or "": the kind
    itself, or the word people say for it (`places.KIND_WORDS`: "forge" is no kind,
    "stable" is the stables). A lookup in the engine's own table, never a guess: a word
    the table does not hold is "" — the place is still heard of, with no kind."""
    from rules import places as places_mod

    k = places_mod.kind_named(word)
    return k if k in kinds else ""


def _place_name(words: str) -> str:
    """The speaker's words as a place's name: "the smithy" for "a smithy" or "smithy";
    "my sister's cottage" kept as said."""
    if words.lower().startswith("the ") or re.match(r"(?i)^(?:my|his|her|their|our|your)\b",
                                                    words):
        return words
    return "the " + _article_off(words)


def _proper(name: str) -> bool:
    return any(w[:1].isupper() for w in _article_off(name).split())


def _landmark(near: str, here, by_name: dict) -> str:
    if near == HERE_SPEAKER and here is not None:
        return here.id
    if near in by_name:
        return by_name[near].id
    return ""
