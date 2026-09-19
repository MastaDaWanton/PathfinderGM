"""Situation cards: the facts of a situation, on an index card the engine keeps.

The drift the player named, 2026-09-06: a woman, her supplies, a jar to seal — and by
the time the jar is sealed the model has lost her, because nothing wrote her down. A
language model rebuilds the world from the text in front of it every turn, and
whatever is not in that text stops existing (Lost in Stories, Microsoft 2026; the D&D
state-tracking model of Callison-Burch et al. 2022 got the state right 58% of the
time when asked to infer it). Every tradition that beat this did the same thing:
stop asking the model to remember, and hand it a small written record that
something else keeps.

The record here is Fate's situation aspect on an index card, with Inform's scene
lifecycle (begins when, ends when) and Blades in the Dark's clock (how close it is
to changing), delivered the way every lorebook delivers a note — AI Dungeon's Story
Cards, NovelAI's Lorebook, KoboldAI's and SillyTavern's World Info all scan the last
few turns for an entry's keys and slip the matching entries in front of the model,
most relevant first, within a budget, and take them out when the keys stop
appearing. Keyword scanning, not the model; a scan window; always-on for the
situation you are standing in; a budget; no chaining (Kobold's documented limit is a
fine first design).

Three laws, applied:
  one vocabulary — a card's tags are hierarchical (`situation.errand`,
    `situation.strain`, `situation.hook`) and queried by prefix through
    `states.matches`, never by string equality;
  one applicator — a card that puts a state on a person does it as an ActiveEffect
    with source `card:<id>` through `Actor.apply_effect`, and taking the card off the
    table removes it; nothing is added outside the funnel;
  severed tells — facts arrive on a card from the engine's own tells, the opening,
    the world's export or a validated proposal; the model never writes one directly.

Provenance, stage 8's rule: every card says where it came from — `opening`,
`world:<entity id>`, `engine:<op>`, `watcher`, `author:test`.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from . import states
from .activeeffect import ActiveEffect

STAGES = ("open", "moving", "resolved", "dropped")
FACT_CAP = 8
CLOCK_DEFAULT = 4
# How many of the most recent beats the keys are scanned over, and how much card text
# the brief may carry. Small on purpose: the Stanford agents result is that a handful
# of relevant lines beats the whole history.
SCAN_BEATS = 3
BUDGET_CHARS = 1400
# Resolved cards stay on the table this many turns, so a beat can refer back to what
# just ended, then leave the brief.
LINGER_TURNS = 3

# The tag families cards use. Prefix-queried like every other tag in `rules/states.py`.
TAG_ERRAND = "situation.errand"      # why the character came here today
TAG_STRAIN = "situation.strain"      # what is wrong with this place, from the export
TAG_HOOK = "situation.hook"          # the world's own unwritten hooks — the GM's
TAG_WORLD = "situation.world"        # authored by World Bible, shipped with the world
TAG_PLAY = "situation.play"          # arose in play
# A quest: a situation the player has taken up as a task, with a giver, objectives to
# tick and something promised at the end. Baldur's Gate 3's journal keeps the same
# two things apart — *objectives* say what to do next, *steps* (our facts) say what just
# happened — and Skyrim's stages taught that objectives finish in any order and not
# every one is reached. Kept as a card so the watcher, the brief and the XP award all
# work on it unchanged; the quest log on the table page reads it by this tag.
TAG_QUEST = "situation.quest"

_STOP = {"the", "and", "that", "with", "from", "this", "here", "there", "their", "which",
         "have", "been", "were", "your", "into", "over", "under", "than", "them", "they",
         "what", "when", "where", "about", "after", "before", "through", "while", "would",
         "could", "should", "these", "those", "other", "every", "still", "being", "came",
         "come", "will", "just", "only", "some", "more", "much", "very", "then", "than",
         "also", "does", "done", "make", "made", "take", "took", "gets", "goes", "went",
         "know", "knows", "something", "anything", "nothing", "somebody", "anybody"}


@dataclass
class Card:
    id: str
    title: str
    facts: list[str] = field(default_factory=list)
    keys: list[str] = field(default_factory=list)
    tags: tuple[str, ...] = ()
    people: list[str] = field(default_factory=list)   # actor refs, or names for the world's
    place: str = ""                                    # a place id (`Actor.at`), or ""
    stage: str = "open"
    clock: int = 0
    clock_max: int = CLOCK_DEFAULT
    origin: str = ""
    secret: bool = False        # the GM's to know, never on the prose's brief
    always_on: bool = False     # in front of the model whether or not a key appears
    opened_at: int = 0          # scene clock, minutes
    touched: int = 0            # transcript turn last touched
    resolved_turn: int = 0
    grants: list[dict] = field(default_factory=list)   # [{"to": ref, "tags": [...]}]
    # A quest's own fields; empty on an ordinary situation.
    kind: str = "situation"                             # "situation" | "quest"
    objectives: list[dict] = field(default_factory=list)   # [{"text": str, "done": bool}]
    giver: str = ""                                     # an actor ref, or a name
    reward: str = ""                                    # in the world's words, no number
    # The transcript turn the prose last carried this card (named one of its people or
    # hit two of its keys) — Ruskin's write-back, so a matter's urgency starts again
    # from the beat that mentioned it. Zero until it ever has been.
    mentioned: int = 0

    def as_dict(self) -> dict:
        return {
            "id": self.id, "title": self.title, "facts": list(self.facts),
            "keys": list(self.keys), "tags": list(self.tags), "people": list(self.people),
            "place": self.place, "stage": self.stage, "clock": self.clock,
            "clock_max": self.clock_max, "origin": self.origin, "secret": self.secret,
            "always_on": self.always_on, "opened_at": self.opened_at,
            "touched": self.touched, "resolved_turn": self.resolved_turn,
            "grants": [dict(g) for g in self.grants],
            "kind": self.kind, "objectives": [dict(o) for o in self.objectives],
            "giver": self.giver, "reward": self.reward,
            "mentioned": self.mentioned,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Card":
        return cls(
            id=str(d.get("id", "")), title=str(d.get("title", "")),
            facts=[str(f) for f in d.get("facts") or []],
            keys=[str(k).lower() for k in d.get("keys") or []],
            tags=tuple(str(t) for t in d.get("tags") or ()),
            people=[str(p) for p in d.get("people") or []],
            place=str(d.get("place") or ""),
            stage=str(d.get("stage") or "open"),
            clock=int(d.get("clock", 0) or 0),
            clock_max=int(d.get("clock_max", CLOCK_DEFAULT) or CLOCK_DEFAULT),
            origin=str(d.get("origin") or ""), secret=bool(d.get("secret", False)),
            always_on=bool(d.get("always_on", False)),
            opened_at=int(d.get("opened_at", 0) or 0), touched=int(d.get("touched", 0) or 0),
            resolved_turn=int(d.get("resolved_turn", 0) or 0),
            grants=[dict(g) for g in d.get("grants") or []],
            kind=str(d.get("kind") or "situation"),
            objectives=[{"text": str(o.get("text", "")), "done": bool(o.get("done"))}
                        for o in d.get("objectives") or [] if isinstance(o, dict)],
            giver=str(d.get("giver") or ""), reward=str(d.get("reward") or ""),
            mentioned=int(d.get("mentioned", 0) or 0),
        )

    def is_(self, query: str) -> bool:
        """Prefix query over the card's tags — `card.is_("situation.errand")`."""
        return any(states.matches(t, query) for t in self.tags)

    @property
    def live(self) -> bool:
        return self.stage in ("open", "moving")


# --- keys ----------------------------------------------------------------------------------

def keys_from(*texts: str) -> list[str]:
    """The trigger words of a card, from its own text: the content words, four letters
    or more, minus the stop list. A lorebook asks its author to type triggers; here the
    engine writes them from what the card says, so "seal the jar" hits the card about
    the jar without anyone having typed 'jar'."""
    out: list[str] = []
    for text in texts:
        for w in re.findall(r"[A-Za-z][A-Za-z'-]{3,}", text or ""):
            low = re.sub(r"'s$", "", w.lower().strip("'-"))   # "woman's" is about the woman
            if len(low) >= 4 and low not in _STOP and low not in out:
                out.append(low)
    return out


def _keys_of(card: Card) -> list[str]:
    """The card's keys, plus the words of its open objectives.

    What a quest is about is what is left to do on it: "Ask the harbourmaster where the
    salt went" makes *harbourmaster* a key whether or not the title or a fact ever said
    it. Measured by the first write-back test — a beat in which the harbourmaster
    talked about the salt did not count as carrying the salt quest, because the
    objective's words were not keys."""
    if not card.objectives:
        return list(card.keys)
    extra = keys_from(*[str(o.get("text", "")) for o in card.objectives
                        if not o.get("done")])
    return list(card.keys) + [k for k in extra if k not in card.keys]


def _hits(card: Card, haystack: str) -> int:
    low = haystack.lower()
    return sum(1 for k in _keys_of(card)
               if re.search(r"\b" + re.escape(k) + r"\w{0,2}\b", low))


# --- the table --------------------------------------------------------------------------------

def load(scene) -> list[Card]:
    return [Card.from_dict(d) for d in (getattr(scene, "cards", None) or [])]


def save(scene, cards: list[Card]) -> None:
    scene.cards = [c.as_dict() for c in cards]


def find(scene, card_id: str) -> Card | None:
    return next((c for c in load(scene) if c.id == card_id), None)


def open_card(scene, card: Card, turn: int = 0) -> Card:
    """Put a card on the table, once, and grant what it grants through the applicator."""
    cards = load(scene)
    if any(c.id == card.id for c in cards):
        return next(c for c in cards if c.id == card.id)
    card.opened_at = int(getattr(scene, "clock_minutes", 0) or 0)
    card.touched = int(turn)
    if not card.keys:
        card.keys = keys_from(card.title, *card.facts)
    cards.append(card)
    save(scene, cards)
    _grant(scene, card)
    return card


def _grant(scene, card: Card) -> None:
    actors = getattr(scene, "actors", {}) or {}
    for g in card.grants:
        who = actors.get(str(g.get("to", "")))
        tags = tuple(str(t) for t in g.get("tags") or ())
        if who is None or not tags:
            continue
        who.apply_effect(ActiveEffect(
            name=card.title, kind="situation", key=card.id, source=f"card:{card.id}",
            origin=card.origin, duration="until-dismissed", tags=tags))


def _ungrant(scene, card: Card) -> None:
    for who in (getattr(scene, "actors", {}) or {}).values():
        who.remove_effects(source=f"card:{card.id}")


def touch(scene, card_id: str, fact: str, turn: int = 0, tick: bool = True) -> Card | None:
    """A fact lands on a card: dedupe, cap, move the stage and the clock. A full
    clock resolves the card. Returns the card, or None if there is no such card."""
    cards = load(scene)
    card = next((c for c in cards if c.id == card_id), None)
    if card is None or not card.live:
        return card
    fact = " ".join(str(fact or "").split())
    if fact and fact not in card.facts:
        card.facts.append(fact)
        card.facts = card.facts[-FACT_CAP:]
    card.touched = int(turn)
    if card.stage == "open":
        card.stage = "moving"
    if tick:
        card.clock = min(card.clock_max, card.clock + 1)
        if card.clock >= card.clock_max:
            card.stage = "resolved"
            card.resolved_turn = int(turn)
            _ungrant(scene, card)
    save(scene, cards)
    return card


def resolve(scene, card_id: str, how: str = "resolved", turn: int = 0) -> Card | None:
    cards = load(scene)
    card = next((c for c in cards if c.id == card_id), None)
    if card is None:
        return None
    card.stage = "resolved" if how != "dropped" else "dropped"
    card.resolved_turn = int(turn)
    _ungrant(scene, card)
    save(scene, cards)
    return card


def touch_from_outcomes(scene, outcomes, turn: int = 0) -> list[str]:
    """The engine's own tells land on the cards they concern, mechanically.

    A tell that names one of a card's people, or hits one of its keys, is a fact
    about that situation — "Borin gives the woman the sealed jar" belongs on the
    woman's card. Ticks the clock only for a tell with a person on it: a check
    beaten near the jar is movement, weather is not. Returns the card ids touched.
    """
    cards = load(scene)
    if not cards:
        return []
    actors = getattr(scene, "actors", {}) or {}
    touched: list[str] = []
    for o in outcomes or []:
        tell = " ".join(str(getattr(o, "tell", "") or "").split())
        if not tell or len(tell) < 12:
            continue
        low = tell.lower()
        for card in cards:
            if not card.live:
                continue
            named = False
            for ref in card.people:
                a = actors.get(ref)
                name = (a.name if a is not None else ref).lower()
                if name and name in low:
                    named = True
                    break
            if named or _hits(card, tell) >= 2:
                touch(scene, card.id, tell[:200], turn=turn, tick=named)
                touched.append(card.id)
    return touched


# --- what the model is shown -------------------------------------------------------------------

def active(scene, recent: list[str] | None, *, turn: int = 0, secret: bool = False,
           budget: int = BUDGET_CHARS) -> list[Card]:
    """The cards in front of the model this turn, most relevant first, within budget.

    Order: the live card always-on at this place, then live cards whose keys appear in
    the scan window (most hits first, then most recently touched), then cards resolved
    within the last few turns so a beat can refer to what just ended. Secret cards
    only when asked for — the plan may know them; the prose may not.
    """
    cards = [c for c in load(scene) if secret or not c.secret]
    here = str(getattr(scene, "at", "") or "")
    window = " ".join((recent or [])[-SCAN_BEATS:])
    scored: list[tuple[tuple, Card]] = []
    for c in cards:
        if c.stage in ("resolved", "dropped"):
            if c.stage == "resolved" and turn - c.resolved_turn <= LINGER_TURNS:
                scored.append(((3, 0, c.touched), c))
            continue
        pinned = c.always_on or (c.place and c.place == here)
        hits = _hits(c, window)
        if pinned:
            scored.append(((0, -hits, -c.touched), c))
        elif hits:
            scored.append(((1, -hits, -c.touched), c))
    scored.sort(key=lambda t: t[0])
    out, spent = [], 0
    for _, c in scored:
        cost = len(c.title) + sum(len(f) for f in c.facts)
        if out and spent + cost > budget:
            continue
        out.append(c)
        spent += cost
    return out


def brief(scene, recent: list[str] | None, *, turn: int = 0, secret: bool = False) -> str:
    """The cards as the brief states them: facts the engine keeps, not suggestions."""
    shown = active(scene, recent, turn=turn, secret=secret)
    if not shown:
        return ""
    actors = getattr(scene, "actors", {}) or {}
    people = getattr(scene, "people", None) or actors
    lines = ["SITUATIONS (kept by the engine; facts, not suggestions — keep them true, "
             "and let the player move them):"]
    for c in shown:
        # Named from the store: a person elsewhere is still a name, not a bare ref
        # the prose then copies ("with c3").
        who = ", ".join(
            (actors[r].name if r in actors else people[r].name if r in people else r)
            + (f" ({r})" if r in actors else "")
            for r in c.people)
        stage = {"open": "just begun", "moving": "in motion", "resolved": "settled",
                 "dropped": "let go"}.get(c.stage, c.stage)
        head = f"  * {c.title} — {stage}"
        if c.live and c.clock_max:
            head += f", {c.clock}/{c.clock_max} of the way to changing"
        if who:
            head += f"; with {who}"
        if c.secret:
            head += " [the GM's alone; the player does not know this]"
        if c.kind == "quest":
            head = head.replace("  * ", "  * QUEST: ", 1)
        lines.append(head + ".")
        if c.kind == "quest":
            # Objectives first — what to do next — then the facts, what has happened.
            for i, o in enumerate(c.objectives):
                lines.append(f"      [{'x' if o.get('done') else ' '}] objective {i + 1}: "
                             f"{o.get('text', '')}")
            if c.reward:
                lines.append(f"      promised: {c.reward}")
        for f in c.facts:
            lines.append(f"      - {f}")
    return "\n".join(lines)


# --- quests -----------------------------------------------------------------------------------

def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", str(text or "").lower()).strip("-")


def _store(scene, card: Card) -> None:
    """Write one card back among the others."""
    items = load(scene)
    save(scene, [card if x.id == card.id else x for x in items])


def quests(scene) -> list[Card]:
    return [c for c in load(scene) if c.kind == "quest"]


def open_quest(scene, *, title: str, objectives, giver: str = "", reward: str = "",
               facts=(), people=(), place: str = "", origin: str = "gm",
               turn: int = 0) -> Card:
    """A task taken up: a card of kind quest. The id is minted from the title."""
    n = sum(1 for c in load(scene) if c.kind == "quest") + 1
    cid = f"quest-{n}-{_slug(title)[:24]}"
    obj = [{"text": " ".join(str(o).split()), "done": False} for o in objectives
           if str(o).strip()][:6]
    card = Card(
        id=cid, title=str(title).strip()[:80], facts=[str(f) for f in facts if str(f).strip()],
        keys=keys_from(title, *[o["text"] for o in obj]),
        tags=(TAG_QUEST, TAG_PLAY), people=[p for p in people if p], place=place,
        clock_max=max(1, len(obj)), origin=origin, always_on=True,
        kind="quest", objectives=obj, giver=giver, reward=str(reward or ""),
    )
    return open_card(scene, card, turn=turn)


def objective_done(scene, card_id: str, index: int, note: str = "", turn: int = 0) -> Card | None:
    """Tick one objective. The clock is the count done; the quest resolves when every
    objective is, and the note — what was done — lands as a fact."""
    card = find(scene, card_id)
    if card is None or card.kind != "quest" or not card.live:
        return None
    if not (0 <= index < len(card.objectives)):
        return None
    card.objectives[index]["done"] = True
    card.clock = sum(1 for o in card.objectives if o.get("done"))
    card.clock_max = max(1, len(card.objectives))
    card.touched = turn
    if card.stage == "open":
        card.stage = "moving"
    if note and note not in card.facts:
        card.facts = (card.facts + [note])[-FACT_CAP:]
    if card.clock >= card.clock_max:
        card.stage = "resolved"
        card.resolved_turn = turn
    _store(scene, card)
    return card


def quest_log(scene) -> dict:
    """What the table page shows: the quests underway, then the ones finished."""
    actors = getattr(scene, "actors", {}) or {}

    def row(c: Card) -> dict:
        giver = actors[c.giver].name if c.giver in actors else c.giver
        return {"id": c.id, "title": c.title, "stage": c.stage, "giver": giver,
                "reward": c.reward, "objectives": [dict(o) for o in c.objectives],
                "facts": list(c.facts), "done": sum(1 for o in c.objectives if o.get("done")),
                "of": len(c.objectives)}

    qs = quests(scene)
    return {"active": [row(c) for c in qs if c.live],
            "finished": [row(c) for c in qs if not c.live]}


# --- where cards come from ---------------------------------------------------------------------

def from_opening(situation, place_id: str, watcher_ref: str, pc_name: str) -> Card:
    """The card the game starts with: the errand, the thing already happening, the
    person beside you. Always on: it is the situation the player is standing in."""
    title = _title_from_errand(situation.errand) or "What you came here for"
    facts = [f for f in (situation.errand, situation.doing, situation.edge) if f]
    return Card(
        id="opening", title=title, facts=facts,
        keys=keys_from(title, *facts), tags=(TAG_ERRAND, TAG_PLAY),
        people=[watcher_ref] if watcher_ref else [], place=place_id or "",
        stage="open", origin="opening", always_on=True,
    )


def _title_from_errand(errand: str) -> str:
    """"You came for a day's paid work before your money runs out." → "A day's paid
    work before your money runs out"."""
    text = " ".join((errand or "").split()).rstrip(".")
    text = re.sub(r"^You came (?:to|for|because|out to|in out of the weather to|looking for)\s+",
                  "", text, flags=re.I)
    return (text[:1].upper() + text[1:])[:70] if text else ""


# --- the one open matter nearest to hand -------------------------------------------------------
#
# How long an open matter may go unmentioned before it starts to press, and before the
# prose is asked for it. Booth's Director shape — a quiet stretch raises the pressure —
# with constants that are ours rather than a shooter's. The unit is TRANSCRIPT ENTRIES,
# which is what `turn` counts everywhere in this file: a player's turn is the player's
# line plus the GM's beat, two entries, sometimes three. So twelve is about six turns
# of play and twenty about ten — a quest taken up and not heard of for ten turns is the
# failure the player described. The first cut of these read 6 and 10 and meant them in
# turns; the audit's "has not come up for 14 turns" was seven.
QUIET_TURNS = 12
URGENT_TURNS = 20
# A matter the beat has carried rests until it has gone quiet — Valve's "don't say this
# if it's been said in the last N", SillyTavern's Cooldown, Booth's relax phase. The
# first sixty-turn run pulled the same card on consecutive turns eight times: the beat
# mentioned it, so its words were in the recent window, so it scored again. A four-entry
# rest fixed that and was still too eager: on the second run the player's quest was
# pulled on thirty of sixty turns, the beat carried it on five, and two of the five were
# forced (a whisker that chimes, a texture a sound "oddly mirrors"). A card that has
# surfaced once is not pulled again until QUIET_TURNS have passed since the beat last
# carried it; a card that has never surfaced is pulled until it does.
REST_TURNS = QUIET_TURNS

_PROPER = re.compile(r"[A-Z][A-Za-z'’-]{3,}")


def _proper_nouns(*texts) -> list[str]:
    """Capitalised words that do not open a sentence — the names a card's facts carry.

    "Tensions between Khy'vyr and Nirkor populations" is about the Khy'vyr and the
    Nirkor; "tensions", "between" and "populations" are every strain card in the world.
    The first word of a sentence is skipped because English capitalises it whatever it
    is, which costs a name that happens to open a sentence and saves every "Tensions".
    """
    out: list[str] = []
    for text in texts:
        for sentence in re.split(r"(?<=[.!?])\s+", str(text or "")):
            for w in sentence.split()[1:]:
                m = _PROPER.match(w.strip("\"'“”‘’(),;:"))
                if not m:
                    continue
                low = re.sub(r"['’]s$", "", m.group(0).lower()).strip("'’-")
                if len(low) >= 4 and low not in _STOP and low not in out:
                    out.append(low)
    return out


def identity_keys(card: Card, names=()) -> list[str]:
    """The words that mean THIS card and not its neighbours.

    `keys_from` takes every content word of the title and the facts — forty to
    seventy-eight per world card in the shipped export, and "between", "power",
    "resources", "competition" are on most of them. Measured on the first sixty-turn
    run: one such key in a three-beat window was enough to make a card "recent", so
    nearly every card was recent on nearly every turn, the same card was pulled eight
    times running, and `note_mentions` stamped fifteen cards as carried by one beat.
    Identity is narrower: the title's content words, the open objectives' words (what a
    quest is about is what is left to do on it), the names of its people, and the
    proper nouns in its facts. The fact words themselves stay out.
    """
    out = keys_from(card.title)
    for o in card.objectives:
        if not o.get("done"):
            for k in keys_from(str(o.get("text", ""))):
                if k not in out:
                    out.append(k)
    for k in _proper_nouns(*card.facts):
        if k not in out:
            out.append(k)
    for nm in names:
        low = " ".join(str(nm or "").lower().split())
        if len(low) >= 3 and low not in out:
            out.append(low)
    return out


def _identity_hits(keys, haystack: str) -> int:
    low = haystack.lower()
    return sum(1 for k in keys
               if re.search(r"\b" + re.escape(k) + r"\w{0,2}\b", low))


def _card_names(card: Card, scene) -> list[str]:
    actors = getattr(scene, "actors", {}) or {}
    people = getattr(scene, "people", None) or actors
    out = []
    for r in card.people:
        a = actors.get(r)
        if a is None and hasattr(people, "get"):
            a = people.get(r)
        name = (a.name if a is not None else str(r)).strip()
        if len(name) >= 3:
            out.append(name)
    return out


def _names_in(names, haystack: str) -> bool:
    low = haystack.lower()
    return any(n.lower() in low for n in names)


def salience(scene, *, recent, player_text: str = "", tells=(),
             turn: int = 0) -> list[tuple[int, list[str], Card]]:
    """Every live, visible card scored by how many of the scene's facts point at it.

    Ruskin's rule selection (Valve, GDC 2012), adopted whole: the score is the NUMBER
    of criteria that hold — "the simplest one imaginable" — so the card the scene points
    at from several directions beats the card it merely mentions. The criteria: pinned
    to this place; one of its people present; named in what the player just said or
    the engine just decided ("spoken": two of its keys, or one of its people); its
    identity in the last few beats ("recent": two identity words, or a person); an
    objective still open; and how long since the prose last carried it, a point past
    QUIET_TURNS and another past URGENT_TURNS.

    Which cards may be candidates at all is the correction the first run taught. The
    player's OWN matters — a quest, the errand they came with, a situation that arose in
    play, or any card whose person is standing here — qualify on any criterion but
    time. The world's ambient cards — a town's strain, a guild's description — qualify
    only when spoken of or recently in the prose: they are the brief's business already,
    and pulling them for being pinned to the town turned fifty of fifty beats toward
    faction politics nobody had raised. A card the prose has carried rests for
    REST_TURNS after the last time it did.
    Ties go to the card most recently touched, deterministic where Valve chose random,
    so a test can pin the pick. Never the model's judgement: Drama Llama let a model
    decide which storylet was live and its authors reported the triggers misfiring
    (docs/narrator-guards.md).
    """
    here = str(getattr(scene, "at", "") or "")
    actors = getattr(scene, "actors", {}) or {}
    window = " ".join(str(b) for b in list(recent or [])[-SCAN_BEATS:])
    now = " ".join([str(player_text or "")] + [str(t) for t in (tells or ())])
    out: list[tuple[int, list[str], Card]] = []
    for c in load(scene):
        if not c.live or c.secret:
            continue
        if c.mentioned and int(turn) - int(c.mentioned) < REST_TURNS:
            continue
        names = _card_names(c, scene)
        ident = identity_keys(c, names)
        why: list[str] = []
        present = any(r in actors for r in c.people)
        if c.place and c.place == here:
            why.append("here")
        if present:
            why.append("present")
        if _hits(c, now) >= 2 or _names_in(names, now):
            why.append("spoken")
        if _identity_hits(ident, window) >= 2 or _names_in(names, window):
            why.append("recent")
        if c.kind == "quest" and any(not o.get("done") for o in c.objectives):
            why.append("open")
        since = int(turn) - int(c.mentioned or c.touched or 0)
        # A card whose person is standing here goes quiet in two turns, not twelve:
        # the giver in the room is the matter nearest to hand, and two quiet turns is
        # the push the play-test asked for (item 7).
        if since >= QUIET_TURNS or (present and since >= 2):
            why.append("quiet")
        if since >= URGENT_TURNS:
            why.append("urgent")
        own = (c.kind == "quest" or c.is_(TAG_ERRAND) or c.is_(TAG_PLAY) or present)
        if own:
            qualifies = bool(set(why) - {"quiet", "urgent"})
        else:
            qualifies = "spoken" in why or "recent" in why
        if qualifies:
            out.append((len(why), why, c))
    out.sort(key=lambda t: (-t[0], -t[2].touched, t[2].id))
    return out


def thread_to_pull(scene, *, recent, player_text: str = "", tells=(),
                   turn: int = 0) -> dict | None:
    """The one open matter nearest to hand: the prose prompt's last block, and the
    facts `gm.narration.review` polices it with.

    One, never the list. A model asked for N things answers in parallel (CLAUDE.md's
    five-factions lesson), and SillyTavern's inclusion groups exist because one entry
    firing beats five. The text is a fact with one detail attached — the open objective
    if there is one, else the latest thing that happened — and carries no number.
    Returns None when nothing scores, which is most quiet turns.
    """
    ranked = salience(scene, recent=recent, player_text=player_text, tells=tells,
                      turn=turn)
    if not ranked:
        return None
    _score, why, c = ranked[0]
    names = _card_names(c, scene)
    open_objective = next((str(o.get("text", "")) for o in c.objectives
                           if not o.get("done")), "")
    fact = open_objective or (c.facts[-1] if c.facts else "")
    since = int(turn) - int(c.mentioned or c.touched or 0)
    text = ("STILL OPEN, NEAREST TO HAND (one matter the engine keeps — a fact to let "
            f"show where it fits, never to resolve for the player): {c.title}"
            + (f" — {fact}" if fact else "") + "."
            + (" It has not come up for a while." if "quiet" in why else ""))
    # The person it belongs to is standing here: they reach for the player. A named
    # giver sat in the "In the scene" list for many turns and was never named in prose
    # (2026-09-18, item 7) — presence was a listing, and a listing makes nothing happen.
    if "present" in why:
        actors = getattr(scene, "actors", {}) or {}
        who = next((actors[r].name for r in c.people if r in actors), "")
        if who:
            text += (f" {who} is standing here and has a reason to speak of it: they "
                     f"approach the player and say the first word about it — in their "
                     f"own words, in this beat.")
    return {"id": c.id, "title": c.title, "kind": c.kind, "fact": fact,
            "keys": identity_keys(c, names), "people": names, "since": since,
            "urgent": "urgent" in why, "why": why, "text": text}


def note_mentions(scene, text: str, turn: int = 0) -> list[str]:
    """Which live cards this beat carried, marked `mentioned` — the write-back.

    A card is carried when the prose names one of its people or two of its IDENTITY
    words (`identity_keys`); one word is a coincidence ("salt" in a market), and two
    of the loose fact-keys was no bar at all — measured, fifteen cards "carried" by one
    beat about winged and flightless folk. Speech counts: a character talking about the
    matter is the matter coming up.
    """
    cards = load(scene)
    if not cards or not text:
        return []
    low = " ".join(str(text).split()).lower()
    carried: list[str] = []
    for c in cards:
        if not c.live:
            continue
        names = _card_names(c, scene)
        if _names_in(names, low) or _identity_hits(identity_keys(c, names), low) >= 2:
            c.mentioned = int(turn)
            carried.append(c.title)
    if carried:
        save(scene, cards)
    return carried


def from_world(world, place_id: str = "") -> list[Card]:
    """The cards a world ships with: the ones its author wrote (`play.cards`, the
    contract in docs/campaign-format.md — World Bible does not write them yet), and
    the ones every export already implies — a settlement's own strain, and each
    unwritten hook as the GM's secret card. Nothing invented: every fact is the
    export's own sentence."""
    out: list[Card] = []
    play = getattr(world, "play", None) or {}
    for i, raw in enumerate(play.get("cards") or []):
        if not isinstance(raw, dict) or not str(raw.get("title", "")).strip():
            continue
        facts = [str(f) for f in raw.get("facts") or [] if str(f).strip()]
        cid = str(raw.get("id") or f"world-{i + 1}")
        tags = tuple(str(t) for t in raw.get("tags") or ()) or ()
        if not any(states.matches(t, "situation") for t in tags):
            tags = (TAG_WORLD,) + tags
        out.append(Card(
            id=cid, title=str(raw["title"]).strip()[:80], facts=facts[:FACT_CAP],
            keys=[str(k).lower() for k in raw.get("keys") or []] or keys_from(raw["title"], *facts),
            tags=tags, people=[str(p) for p in raw.get("people") or []],
            place=str(raw.get("place") or ""), stage="open",
            clock_max=int(raw.get("clock", CLOCK_DEFAULT) or CLOCK_DEFAULT),
            origin=f"world:{cid}", secret=bool(raw.get("secret", False)),
            always_on=bool(raw.get("always_on", False)),
        ))
    entities = getattr(world, "entities", None) or {}
    # The starting settlement's strain, from its own facts: "tensions between Vyrakon
    # and Oorvieth's city government" — border control and taxation. Public knowledge
    # in the place, so a visible card.
    town = _entity_for(world, place_id)
    if town is not None:
        strain = _fact(town, ("Tension", "Conflict", "Volatility"))
        cause = _fact(town, ("Cause", "Status"))
        if strain:
            facts = [_sentence(strain)] + ([_sentence(cause)] if cause else [])
            out.append(Card(
                id=f"strain-{town.id}", title=f"What is wrong in {town.name}",
                facts=facts, keys=keys_from(town.name, *facts),
                tags=(TAG_STRAIN, TAG_WORLD), place=place_id, stage="open",
                clock_max=6, origin=f"world:{town.id}",
            ))
    for u in getattr(world, "unwritten", None) or []:
        if not isinstance(u, dict):
            continue
        name = str(u.get("name") or "").strip()
        why = str(u.get("why") or u.get("text") or u.get("hook") or "").strip()
        if not (name and why):
            continue
        out.append(Card(
            id=f"hook-{re.sub(r'[^a-z0-9]+', '-', name.lower()).strip('-')}",
            title=name, facts=[_sentence(why)], keys=keys_from(name, why),
            tags=(TAG_HOOK, TAG_WORLD), stage="open", clock_max=6,
            origin=f"world:{u.get('id') or name}", secret=True,
        ))
    return out


def _entity_for(world, place_id: str):
    entities = getattr(world, "entities", None) or {}
    eid = str(place_id or "").split("~", 1)[0]
    if eid in entities:
        return entities[eid]
    return None


def _fact(entity, keys) -> str:
    for k in keys:
        v = (entity.fact(k, "") or "").strip() if hasattr(entity, "fact") else ""
        if v:
            return v
    return ""


def _sentence(text: str) -> str:
    text = " ".join(str(text or "").split()).rstrip(" .;,")
    return text[:1].upper() + text[1:] + "." if text else ""
