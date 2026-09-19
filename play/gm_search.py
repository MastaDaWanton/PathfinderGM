"""What the world's own record says about what the player asked the GM.

`/gm` is the player stepping out of the fiction to ask the person running the game, and
until 2026-09-18 it could answer only what it could match by NAME: the engine's own state
by topic, a rules entry whose name the question contained, a world entity spelled exactly.
"What is this town's council?" matched nothing, because "this town" is not a name, and
"what do the Saltmakers want?" matched nothing unless the export spelled it that way.

Two things fix that, both measured before they were built (docs/gm-questions.md):

**Deixis is the place the engine already knows.** "Here", "this town", "the city" — the
question is about the current location, and the GM's notes on it are the entity's whole
record: every typed fact, its prose, the places inside it, who lives there and what they
are. `dossier()` writes those notes, the fact the question is about first.

**Names are found, not matched.** A BM25 index over the world's entities, factions and
events — SQLite FTS5, in the standard library, compiled into this Python and the frozen
bundle — ranks "Vormoor" and every resident of it first for a question about Vormoor,
every Sootspar for "who are the Sootspars", and scores a question the world has no words
for near zero, which is a threshold the code can refuse on. Measured on the shipped
Aurvantis export: 422 documents indexed in a tenth of a second, a query in a millisecond.

**What was refused, and why.** Dense embeddings. The literature this was read against
(BEIR; EntityQuestions, where DPR trails BM25 49.7% to 72.0% on questions about named
entities; two Pathfinder/D&D rules corpora that measured hybrid retrieval as no better)
says a few thousand documents full of proper nouns is BM25's home ground, and the one
thing dense retrieval buys — paraphrase — is closed here by `INTENTS`, a map from how a
player asks to how the export types its facts. An embedding model would also be a second
download for every player. And the refusal lives in code: FaithEval measured an 8B model
saying "unknown" correctly 37.6% of the time when the passage was absent, so a question
that finds nothing never reaches the model to be answered confidently and wrong.
"""
from __future__ import annotations

import re
import sqlite3
import threading
from dataclasses import dataclass, field

# Words that carry no scent. Kept small: a stop list that eats "council" or "temple" would
# eat the question.
STOP = frozenset(
    "what is the a an and of who in to do does how where can i my this here about are "
    "there it its it's s that they them their his her he she was were be been being for "
    "with from by on at as or if so than then too very just tell me know did you your "
    "any some all which whom whose why when will would could should".split())

# "here", "this town": the question is about where the party stands.
DEIXIS = re.compile(
    r"\b(?:here|this (?:town|city|place|village|settlement|region|land|country|"
    r"district|quarter|street|market)|around here|nearby|locally|hereabouts|"
    r"where (?:i am|we are|i'm|we're)|the (?:town|city|place|village)|in town)\b", re.I)

# The paraphrase gap, closed in code: how a player asks, mapped to how the export types
# its facts and titles its sections. The first tuple whose pattern matches names the
# facts to put first; a question matching none gets the whole record in its own order.
INTENTS: tuple[tuple[re.Pattern, tuple[str, ...]], ...] = (
    (re.compile(r"\b(?:who (?:runs|rules|leads|governs|is in charge|holds (?:the )?power)|"
                r"councils?|rulers?|government|governance|laws?|authority|authorities|"
                r"mayor|lord|lady|king|queen|elders?|in charge|administration)\b", re.I),
     ("Formal Power", "Governance", "Administration", "Shadow Power")),
    (re.compile(r"\b(?:tensions?|trouble|wrong|conflicts?|disputes?|unrest|feuds?|"
                r"rivalr(?:y|ies)|afraid|fear|danger|threats?|simmering|underneath)\b",
                re.I),
     ("Tension", "Shadow Power", "Conflict", "Volatility")),
    (re.compile(r"\b(?:look like|looks like|architecture|buildings?|built|houses?|"
                r"streets?|walls?|roofs?|made of)\b", re.I),
     ("Architecture", "Urban Life")),
    (re.compile(r"\b(?:eat|food|drink|customs?|daily|everyday|norms?|festivals?|"
                r"market days?|prayers?|worship|religion|gods?|temples?|shrines?|"
                r"holy|priests?)\b", re.I),
     ("Daily Norms", "Religion", "Urban Life")),
    (re.compile(r"\b(?:who lives|people|classes|rich|poor|nobles?|commoners?|"
                r"population|folk|races?|peoples)\b", re.I),
     ("Social Classes", "Urban Life", "Origin")),
    (re.compile(r"\b(?:history|happened|founded|wars?|battles?|past|ago|"
                r"old days|legends?|remember)\b", re.I),
     ("History",)),
    (re.compile(r"\b(?:trade|sells?|buy|bought|markets?|goods|wares|merchants?|"
                r"prices?|costs?|shops?|stalls?)\b", re.I),
     ("Trade", "Urban Life", "Daily Norms")),
)

# Below this a BM25 hit is noise. Measured on the Aurvantis export with the name column
# weighted ten to one: a named entity scores -6 to -23, a question the world has no words
# for scores -1 to -3.3 against whatever shares a preposition with it.
THRESHOLD = -4.5
NAME_WEIGHT = 10.0
BODY_CAP = 6000          # characters of an entity's record indexed; the prose is long
PASSAGE_BUDGET = 1800    # what the model is shown of the hits, in characters
DOSSIER_BUDGET = 2400    # and of the place the party stands in


@dataclass
class Hit:
    kind: str
    name: str
    score: float
    entity_id: str | None = None
    facts: dict = field(default_factory=dict)
    prose: str = ""
    parent: str = ""
    text: str = ""           # factions and events, which have no entity
    matched: int = 0         # how many rows passed the threshold for this question
    exhaustive: bool = True  # False when the fetch was full and there may be more


_LOCK = threading.Lock()
_INDEX: dict[int, tuple[sqlite3.Connection, dict[int, dict]]] = {}


def _rows(world) -> list[tuple[str, str, str, dict]]:
    """Every document the record holds: entities, factions, events. `meta` is what the
    hit hands back beyond the score."""
    out: list[tuple[str, str, str, dict]] = []
    entities = getattr(world, "entities", None) or {}
    for e in entities.values():
        parent = entities.get(e.parent_id) if getattr(e, "parent_id", None) else None
        facts = " ".join(f"{k}: {v}" for k, v in (e.facts or {}).items())
        places = " ".join(str(p.get("name", "")) for p in (getattr(e, "places", None) or []))
        body = (f"{e.name}. {e.summary or ''}. In {parent.name if parent else ''}. {places}. "
                f"{facts} {e.prose}")[:BODY_CAP]
        out.append((e.name, str(e.kind or "").lower(), body,
                    {"entity_id": e.id, "parent": parent.name if parent else ""}))
    for f in getattr(world, "factions", None) or []:
        if isinstance(f, dict) and f.get("name"):
            out.append((str(f["name"]), "faction",
                        " ".join(str(v) for v in f.values())[:BODY_CAP],
                        {"text": " ".join(f"{k}: {v}" for k, v in f.items() if v)}))
    for ev in getattr(world, "chronology", None) or []:
        name = getattr(ev, "name", "")
        if name:
            text = " ".join(str(x) for x in (getattr(ev, "summary", ""),
                                             getattr(ev, "background", ""),
                                             getattr(ev, "aftermath", "")) if x)
            out.append((str(name), "event", f"{name}. {text}"[:BODY_CAP], {"text": text}))
    return out


def index_for(world) -> tuple[sqlite3.Connection, dict[int, dict]]:
    """The FTS5 index of one world, built once per process and kept. A world is loaded
    once and cached (`play.campaign.load_cached`), so its identity is stable."""
    key = id(world)
    with _LOCK:
        got = _INDEX.get(key)
        if got is not None:
            return got
        con = sqlite3.connect(":memory:", check_same_thread=False)
        con.execute("CREATE VIRTUAL TABLE docs USING fts5(name, kind, body, "
                    "tokenize='porter unicode61')")
        meta: dict[int, dict] = {}
        for i, (name, kind, body, extra) in enumerate(_rows(world), start=1):
            con.execute("INSERT INTO docs(rowid, name, kind, body) VALUES (?,?,?,?)",
                        (i, name, kind, body))
            meta[i] = extra
        con.commit()
        _INDEX[key] = (con, meta)
        return con, meta


def forget(world=None) -> None:
    """Drop a world's index (or every index) — for a reloaded export, and for tests."""
    with _LOCK:
        if world is None:
            _INDEX.clear()
        else:
            _INDEX.pop(id(world), None)


def terms(question: str) -> list[str]:
    """The words a question could be about, in order, stop words out."""
    out = []
    for w in re.findall(r"[a-z][a-z'’-]*", str(question or "").lower()):
        w = w.replace("’", "'").strip("'-")
        if len(w) > 2 and w not in STOP and w not in out:
            out.append(w)
    return out


def phrases(question: str) -> list[str]:
    """Adjacent pairs of content words, as the question had them: "long peace",
    "salt fever", "drenn ironvale". A name is usually two words standing together, and
    FTS5 scores a phrase as a term of its own with its own rarity."""
    words = [w.replace("’", "'").strip("'-")
             for w in re.findall(r"[a-z][a-z'’-]*", str(question or "").lower())]
    out = []
    for a, b in zip(words, words[1:]):
        if (len(a) > 2 and len(b) > 2 and a not in STOP and b not in STOP
                and f"{a} {b}" not in out):
            out.append(f"{a} {b}")
    return out


def match_expression(question: str) -> str:
    """A MATCH expression FTS5 will accept: quoted phrases, then quoted tokens, OR-joined.

    Raw text is not one — `Saltmakers' guild` and `want?` are syntax errors — and the
    default between bare tokens is AND, which is what made another project's full-text
    baseline return nothing for most questions.

    The phrases are what lifts a name made of ordinary words out of the noise. Measured on
    the Aurvantis export: "what is the Long Peace" scored -3.9 on tokens alone — below the
    threshold, indistinguishable from a question the world has no words for — and -7.8
    with the phrase; every proper name roughly doubled its score; noise did not move.
    """
    return " OR ".join([f'"{p}"' for p in phrases(question)]
                       + [f'"{t}"' for t in terms(question)])


def intent_keys(question: str) -> tuple[str, ...]:
    for pattern, keys in INTENTS:
        if pattern.search(str(question or "")):
            return keys
    return ()


def asks_about_here(question: str) -> bool:
    return bool(DEIXIS.search(str(question or "")))


def search(world, question: str, limit: int = 3, threshold: float = THRESHOLD) -> list[Hit]:
    """The record's best matches for a question, best first, none below the threshold."""
    expr = match_expression(question)
    if not expr or world is None:
        return []
    con, meta = index_for(world)
    fetch = max(1, limit) * 4
    rows = con.execute(
        "SELECT rowid, name, kind, bm25(docs, ?, 1.0, 1.0) AS score FROM docs "
        "WHERE docs MATCH ? ORDER BY score LIMIT ?",
        (NAME_WEIGHT, expr, fetch)).fetchall()
    entities = getattr(world, "entities", None) or {}
    hits: list[Hit] = []
    seen: set[tuple[str, str]] = set()
    matched = 0
    for rowid, name, kind, score in rows:
        if score > threshold:
            continue
        matched += 1
        # An export can hold the same name twice at the same kind (a person filed under
        # two parents); one passage is enough.
        if (name, kind) in seen:
            continue
        seen.add((name, kind))
        extra = meta.get(rowid, {})
        hit = Hit(kind=kind, name=name, score=float(score),
                  entity_id=extra.get("entity_id"), parent=extra.get("parent", ""),
                  text=extra.get("text", ""))
        e = entities.get(hit.entity_id) if hit.entity_id else None
        if e is not None:
            hit.facts = dict(e.facts or {})
            hit.prose = e.prose
        hits.append(hit)
    # A row whose whole name the question contains goes first, whatever BM25 said. For
    # "tell me about the Kragmoor Horde" three shorter rows — the founding, the accord,
    # a faction within it — outscored the nation itself by half a point, because BM25
    # favours a short document, and the one passage the player wanted was cut off at
    # the limit. Stable, so the rest keep their order.
    asked = " " + " ".join(re.findall(r"[a-z0-9'’-]+", str(question).lower())) + " "
    hits.sort(key=lambda h: 0 if f" {h.name.lower()} " in asked else 1)
    hits = hits[:limit]
    for h in hits:
        h.matched = matched
        h.exhaustive = len(rows) < fetch
    return hits


# --- what the character would know ------------------------------------------------------
#
# The export marks hiddenness in three places (2026-09-18, item 9): every character
# carries a `Secret`, the world a foundational secret, cards may be `secret`. Settlement
# facts carry no flag, so the tier is by key: what the town says of itself is public;
# what is whispered is rumour; what somebody keeps is hidden. PF1e already encodes the
# split — Knowledge (local): rulers and laws DC 10, common rumour DC 15, hidden
# organisations DC 20, "Try Again: No"; finding out is Diplomacy (gather information),
# 1d4 hours, retryable — and the Alexandrian names the error this prevents ("Preempting
# Investigation"). An unknown key is public: the world's own record is mostly the kind
# of thing anybody in the town could tell you.
HIDDEN_KEYS = frozenset({
    "secret", "secrets", "shadow power", "hidden power", "true power", "conspiracy",
    "underworld", "black market", "what is hidden", "hidden", "the truth",
})
RUMOUR_KEYS = frozenset({
    "tension", "volatility", "rivals", "turning point", "limitations", "weakness",
    "weaknesses", "rumour", "rumours", "rumor", "rumors", "gossip", "scandal",
    "fault lines", "unrest",
})
PUBLIC, RUMOUR, HIDDEN = "public", "rumour", "hidden"


def tier_of(key: str) -> str:
    k = " ".join(str(key or "").split()).lower()
    if k in HIDDEN_KEYS:
        return HIDDEN
    if k in RUMOUR_KEYS:
        return RUMOUR
    return PUBLIC


def _ordered_facts(facts: dict, keys: tuple[str, ...],
                   allow: frozenset = frozenset({PUBLIC})) -> list[tuple[str, str]]:
    facts = {k: v for k, v in facts.items() if tier_of(k) in allow}
    first = [(k, facts[k]) for k in keys if k in facts]
    rest = [(k, v) for k, v in facts.items() if k not in dict(first)]
    return first + rest


def withheld_from(facts: dict, allow: frozenset) -> list[tuple[str, str]]:
    """The (key, tier) pairs `allow` kept out — what the GM knows and did not say."""
    return [(k, tier_of(k)) for k in facts if tier_of(k) not in allow]


def _fit(lines: list[str], budget: int) -> list[str]:
    out, spent = [], 0
    for line in lines:
        if spent + len(line) > budget:
            room = budget - spent
            if room > 80:
                out.append(line[:room - 1].rstrip() + "…")
            break
        out.append(line)
        spent += len(line)
    return out


def passages(world, hits: list[Hit], question: str = "",
             budget: int = PASSAGE_BUDGET, allow: frozenset = frozenset({PUBLIC})) -> str:
    """What the model is shown of the hits: name, kind, where, the facts the question is
    about first, and a little prose. Labelled from the row — the source is the code's
    to state, not the model's to guess."""
    if not hits:
        return ""
    keys = intent_keys(question)
    head = "WHAT THE WORLD'S OWN RECORD SAYS ABOUT WHAT WAS ASKED"
    # "The records list three individuals with that surname" was said of the Sootspars,
    # of whom the record holds a dozen; the model was shown three and counted them. The
    # count is the code's to state.
    if hits[0].matched > len(hits):
        head += (f" (the best {len(hits)} of "
                 f"{'' if hits[0].exhaustive else 'at least '}{hits[0].matched} matches; "
                 f"there are more than these)")
    lines = [head + " (fact; answer from this, and say when it does not cover the question):"]
    per = max(400, budget // max(1, len(hits)))
    for h in hits:
        head = f"  * {h.name} — {h.kind}" + (f", in {h.parent}" if h.parent else "") + "."
        body: list[str] = []
        for k, v in _ordered_facts(h.facts, keys, allow):
            body.append(f"      {k}: {' '.join(str(v).split())}")
        if h.prose:
            body.append("      " + " ".join(h.prose.split())[:600])
        if h.text and not h.facts:
            body.append("      " + " ".join(h.text.split())[:600])
        lines.append("\n".join([head] + _fit(body, per)))
    return "\n".join(lines)


def dossier(world, location, question: str = "", budget: int = DOSSIER_BUDGET,
            allow: frozenset = frozenset({PUBLIC})) -> str:
    """The GM's notes on where the party stands: the whole record of the place, the fact
    the question is about first, then who lives there and what is inside it."""
    if world is None or location is None:
        return ""
    keys = intent_keys(question)
    entities = getattr(world, "entities", None) or {}
    parents = []
    pid = getattr(location, "parent_id", None)
    while pid and pid in entities and len(parents) < 3:
        parents.append(entities[pid])
        pid = entities[pid].parent_id
    within = ", ".join(f"{p.name} ({str(p.kind).lower()})" for p in parents if p.kind != "WORLD")
    lines = [f"THE GM'S NOTES ON {location.name.upper()} ({str(location.kind or 'place').lower()}"
             + (f", within {within}" if within else "") + "):"]
    body: list[str] = []
    for k, v in _ordered_facts(dict(getattr(location, "facts", {}) or {}), keys, allow):
        body.append(f"  {k}: {' '.join(str(v).split())}")
    # The short, load-bearing lines before the long prose, so the budget never eats
    # them: what is inside the place, who lives here, and the land it sits in.
    places = [str(p.get("name", "")) for p in (getattr(location, "places", None) or []) if p.get("name")]
    if places:
        body.append("  Places inside it: " + ", ".join(places) + ".")
    try:
        residents = world.residents(location.id)
    except Exception:  # noqa: BLE001 — a world without the helper has no residents to list
        residents = []
    if residents:
        body.append("  People who live here: " + "; ".join(
            f"{r.name} ({' '.join(str(r.role).split())[:60]})" if getattr(r, "role", "")
            else r.name for r in residents[:12]) + ".")
    for p in parents:
        if p.kind == "WORLD":
            continue
        pf = dict(getattr(p, "facts", {}) or {})
        chosen = [(k, pf[k]) for k in ("Formal Power", "Governance", "Tension")
                  if k in pf and tier_of(k) in allow]
        if chosen:
            body.append(f"  {p.name}: " + " ".join(f"{k}: {' '.join(str(v).split())}"
                                                    for k, v in chosen)[:400])
    # The prose, the section the question is about first, filling what budget is left.
    sections = list(getattr(location, "sections", None) or [])
    wanted = {k.lower() for k in keys}
    sections.sort(key=lambda s: 0 if str(s.get("title") or s.get("heading") or "").lower()
                  in wanted else 1)
    for s in sections:
        title = str(s.get("title") or s.get("heading") or "").strip()
        if title and tier_of(title) not in allow:
            continue
        text = " ".join(" ".join(s.get("paragraphs", [])).split())
        if text:
            body.append(f"  {title + ': ' if title else ''}{text[:600]}")
    return "\n".join(lines + _fit(body, budget))


# --- when the record holds nothing ---------------------------------------------------
#
# The refusal is the code's (docs/gm-questions.md G3), so it has to be sure: a question
# refused wrongly is the GM declining to answer about the town the player is standing
# in. Two shapes are sure enough, and both are checked against the index itself —
# "unknown" here means a word that appears in NO document of the world, not one that
# merely scored low.
#
#   * a proper name — a capitalised word that is not the sentence's first — with a word
#     the world has never used: "who is Grimble", "where is Hollin Stair";
#   * a lowercase head phrase after "who/what/where is the", "about the", "called" whose
#     words the world has NONE of, and none of which is a word about the game itself:
#     "what are the winged clans" is refused, "any advice about the fight" is not, even
#     though this world's prose happens never to say "fight".
#
# Everything else goes to the model with the notes on where the party stands, told to
# say when they do not cover it — a weaker guarantee, taken knowingly, because the
# alternative is refusing questions the record could have answered.

# Words a player uses about the game rather than about the world. A head phrase made of
# these is a request for a reading, never a name the record might hold.
_GAME_WORDS = frozenset(
    "fight fights battle plan plans idea ideas situation scene thing things next advice "
    "option options choice choices move moves turn turns chance chances odds risk risks "
    "strategy tactic tactics approach way ways best point story game character party "
    "sheet roll rolls check checks rule rules mechanic mechanics dice die action actions "
    "attack attacks defence defense spell spells feat feats level levels class classes "
    "encounter combat round rounds damage hit hits miss reason".split())

_PROPER = re.compile(r"(?<!^)(?<![.!?]\s)\b[A-Z][a-z'’-]{2,}\b")
_HEAD = re.compile(
    r"\b(?:(?:who|what|where|which)\s+(?:is|are|was|were|does|do|did)|about|called|named|"
    r"tell me of|heard of|know of)\s+(?:the\s+|a\s+|an\s+)?"
    r"([a-z][a-z'’-]{2,}(?:\s+[a-z][a-z'’-]{2,})?)", re.I)


def proper_noun(question: str) -> bool:
    """Does the question carry a name — a capitalised word that is not the first?"""
    q = " ".join(str(question or "").split())
    return any(m.group(0) not in ("GM",) for m in _PROPER.finditer(q))


def unknown_terms(world, words) -> list[str]:
    """Those of `words` that appear in no document of the world's record."""
    if world is None:
        return []
    con, _ = index_for(world)
    out = []
    for w in words:
        w = str(w).lower().replace("’", "'").strip("'-")
        if len(w) < 3 or w in STOP:
            continue
        n = con.execute('SELECT count(*) FROM docs WHERE docs MATCH ?', (f'"{w}"',)).fetchone()[0]
        if n == 0 and w not in out:
            out.append(w)
    return out


def unfiled(world, question: str) -> list[str]:
    """The words that justify refusing in code — empty when the model should be asked."""
    q = " ".join(str(question or "").split())
    if not q or world is None:
        return []
    names = [m.group(0) for m in _PROPER.finditer(q) if m.group(0) != "GM"]
    if names:
        return unknown_terms(world, names)
    m = _HEAD.search(q)
    if not m:
        return []
    words = re.findall(r"[a-z][a-z'’-]*", m.group(1).lower())
    # "what do YOU think of this" has no head: a phrase that opens on a pronoun is a
    # question about a reading, whatever follows it.
    if not words or words[0] in STOP:
        return []
    head = [w for w in words if w not in STOP and len(w) > 2]
    if not head or any(w in _GAME_WORDS for w in head):
        return []
    unknown = unknown_terms(world, head)
    return unknown if len(unknown) == len(head) else []


def nothing_filed(question: str, unknown: list[str] | None = None, notes: str = "") -> str:
    """The answer the code gives when the record holds nothing on what was asked — never
    the model, which would answer anyway. With the first lines of the notes on where the
    party stands, so the player still gets something true to go on."""
    named = ", ".join(unknown or terms(question)[:5])
    text = (f"The GM has nothing filed under that. The world's own record never mentions "
            f"{named or 'what you asked about'}, and the engine has not decided it. Ask "
            f"about where you are, the people here, a name you have heard, or a rule by "
            f"name.")
    lead = [ln for ln in str(notes or "").split("\n") if ln.strip()][:4]
    if lead:
        text += "\n" + "\n".join(lead)
    return text
