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

import copy
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
    # How the matter has reached the player so far, `[{"turn", "approach"}]`
    # (rules/hooks.py): the next approach is one not yet used, and one that reaches for
    # the player rests between showings. Written only when there is one (§2.0), so a card
    # from before it existed round-trips byte-identically.
    approaches: list[dict] = field(default_factory=list)
    # What a quest is to get back, when the engine opened it because something was taken
    # (`rules/defeat.py`): who holds it, how much coin, which thing, and how much of each
    # they held before, so `defeat.settle` can tell recovered from merely replaced. The
    # quest's own record of its target, never a model's. Written only when there is one,
    # like `approaches`, so every card from before it round-trips unchanged.
    recover: dict = field(default_factory=dict)

    def as_dict(self) -> dict:
        out = {
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
        if self.approaches:
            out["approaches"] = [dict(a) for a in self.approaches]
        if self.recover:
            out["recover"] = copy.deepcopy(self.recover)
        return out

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
            approaches=[{"turn": int(a.get("turn", 0) or 0),
                         "approach": str(a.get("approach") or "")}
                        for a in d.get("approaches") or [] if isinstance(a, dict)],
            recover=(copy.deepcopy(d["recover"])
                     if isinstance(d.get("recover"), dict) else {}),
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
    """The card's keys, plus the words of its open objectives, plus its need's.

    What a quest is about is what is left to do on it: "Ask the harbourmaster where the
    salt went" makes *harbourmaster* a key whether or not the title or a fact ever said
    it. Measured by the first write-back test — a beat in which the harbourmaster
    talked about the salt did not count as carrying the salt quest, because the
    objective's words were not keys.

    And an errand's need (`need_of`): "Find a bed you can pay for" had eleven keys on
    the owner's save of 2026-10-03 — find, weather, down, gone, door, hurry, room,
    working, hard, having, noticed — and not *bed*, because `keys_from` drops words of
    three letters. The one word the errand is about could never key it."""
    out = list(card.keys)
    if card.objectives:
        extra = keys_from(*[str(o.get("text", "")) for o in card.objectives
                            if not o.get("done")])
        out += [k for k in extra if k not in out]
    need = need_of(card)
    if need:
        out += [k for k in NEED_KEYS[need] if k not in out]
    return out


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
    # A quest's clock is its objectives and `objective_done` is its only ticker.
    # Reported 2026-09-23 with the quest log on screen: "Find Drenn Ironvale's lost
    # Power leaf" showed FINISHED with both objectives unticked and no award paid,
    # the moment the player had accepted it. Its giver is one of the card's people,
    # so every tell that named Drenn — two of them the engine's own "is already a
    # quest on the table" refusals — ticked a clock whose maximum was two.
    if tick and card.kind != "quest":
        # An errand with a need is met by meeting it (`errand_progress`: a night in a
        # bed), never by being talked about four times. Blades' clocks track the
        # obstacle, not the method; Bethesda's objectives complete on their own stage.
        # Its clock fills to one short and waits there.
        top = card.clock_max - 1 if need_of(card) else card.clock_max
        card.clock = min(top, card.clock + 1)
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
        # A refusal is nothing happening (`Engine._refuse`), and nothing happening is
        # not a fact about a situation. The same quest above carried "Find Drenn
        # Ironvale's lost Power leaf is already a quest on the table." as its first
        # fact, and so did the scheme's secret card beside it. Read off the status,
        # not off "no effects": an outcome that happened and changed nothing still
        # said something true.
        if str(getattr(o, "status", "") or "") == "refused":
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
    # The whole store, not `actors` (who is here): a giver left behind in the back streets
    # printed as "for c1" in the Journal, a ref on the page (ruling 2026-09-28), measured
    # on the scratch Sam campaign 2026-10-01. A giver with no name anywhere is left out.
    people = {**(getattr(scene, "people", {}) or {}), **(getattr(scene, "actors", {}) or {})}

    def row(c: Card) -> dict:
        who = people.get(c.giver)
        giver = (who.name if who is not None else
                 "" if re.fullmatch(r"c\d+|pc|[0-9a-f]{12}", str(c.giver or "")) else c.giver)
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


# How many approaches a card remembers: enough to vary them, never a growing list.
APPROACHES_KEPT = 8


def thread_to_pull(scene, *, recent, player_text: str = "", tells=(),
                   turn: int = 0, world=None) -> dict | None:
    """The one open matter nearest to hand: the prose prompt's last block, and the
    facts `gm.narration.review` polices it with.

    One, never the list. A model asked for N things answers in parallel (CLAUDE.md's
    five-factions lesson), and SillyTavern's inclusion groups exist because one entry
    firing beats five. The text is a fact with one detail attached — the open objective
    if there is one, else the latest thing that happened — and carries no number.
    Returns None when nothing scores, which is most quiet turns.

    When the matter has a person, HOW it reaches the player is the engine's choice from a
    closed table (`rules.hooks`, design D §4.6), by who they are to the player and what
    the player is doing. Until 2026-09-28 it was always "they approach the player and say
    the first word" — which gave the playtest Drenn's cold pitch to his own former pupil
    (item 12) and let the pull take the beat from the player's own search (item 9.2).
    Now: a stranger is overheard or mentioned, never a cold open; somebody who knows the
    player greets them first; a player about their own business is left to it — the
    pull YIELDS, and the matter is not put in front of the model at all that beat.
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
    head = ("STILL OPEN, NEAREST TO HAND (one matter the engine keeps — a fact to let "
            f"show where it fits, never to resolve for the player): {c.title}"
            + (f" — {fact}" if fact else "") + "."
            + (" It has not come up for a while." if "quiet" in why else ""))
    out = {"id": c.id, "title": c.title, "kind": c.kind, "fact": fact,
           "keys": identity_keys(c, names), "people": names, "since": since,
           "urgent": "urgent" in why, "why": why, "text": head}
    from . import hooks
    from . import residency

    if hooks.giver_of(scene, c) is None:
        return out
    # The player's words, as the interpreter read them this turn — a cache lookup, the
    # reading already made for the plan (gm/interpret.py). Imported here: rules reads gm
    # only inside a function (the precedent is `Engine`'s own reading of it).
    from gm import interpret as _interpret

    reading = _interpret.reading_of(player_text) if player_text else None
    if reading is not None and reading.get("error"):
        reading = None
    world = residency._world(world)
    ing = hooks.ingredients(c, scene, world, reading)
    state = hooks.scene_state(scene, c, reading)
    if state == hooks.ELSEWHERE and not ing["hook"]:
        # A situation whose person is not here, and who wants nothing of the player:
        # nobody to send word or to mention them. The matter alone, as it always was.
        return out
    how = hooks.approach(ing["to_player"]["relationship"], state, c, turn=turn,
                         rest=REST_TURNS)
    if not how:
        return out
    first = not c.approaches and how != "waits"
    out.update({
        "approach": how, "yielded": state == hooks.BUSY,
        "giver": dict(ing["giver"]), "to_player": dict(ing["to_player"]),
        "offer": ing["offer"], "motive": ing["motive"], "doing": ing["doing"],
        "withholds": ing["withholds"] if how == "asked" else "",
        "text": hooks.render(ing, how, head=head, first=first),
    })
    if out["yielded"]:
        # A pull that has yielded asks nothing of the beat: the urgency check
        # (`narration.review`) must not then demand the matter be carried.
        out["urgent"] = False
    if how != "waits":
        # The card remembers how it reached the player, for the next choice and the rest.
        c.approaches = (list(c.approaches) + [{"turn": int(turn), "approach": how}]
                        )[-APPROACHES_KEPT:]
        _store(scene, c)
    return out


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


# --- what an errand needs, and where in the world it is had ------------------------------
#
# Playtest item 25 (the owner's saves, 2026-10-03): the opening card "Find a bed you can
# pay for" was pulled six times — overheard, then asked ×5 — and never moved. Nothing put
# a bed within reach: the town HAD a tavern (three people stood in it) and the card never
# said so. The watcher's one proposal for it, "The man's hostility has been replaced by a
# weary curiosity as he considers the offer of work", was refused as "not about this
# card", and the player — with an empty purse — drifted into a dock job with the bed
# forgotten.
#
# What the traditions do (docs/rules-and-opening-2026-10-03.md): Bethesda's objectives
# name their target and complete on their own stage; Dungeon World's GM "offers an
# opportunity" and points at the thing; Blades' clocks are "about the obstacle, not the
# method". So an errand that names a need gets three things, all read by code:
#   - its need's words as keys (`_keys_of`), so talk about a bed is about the card;
#   - the place in this settlement that meets it, from the world's own place set, put
#     on the card as a fact — the way to satisfy it, within reach;
#   - progress from what the engine can see: the player asking after it, the player
#     asking for paid work while they cannot pay for it, arriving where it is had, and
#     a night slept there, which settles it.
# Only lodging is wired: it is the measured case. The table is the shape for more.

NEED_LODGING = "lodging"
# Read off the errand's own words. "find a bed you can pay for", "hear where a stranger
# can sleep tonight", "a bed for the night".
_NEED_CUES = {NEED_LODGING: re.compile(r"\b(?:bed|beds|sleep|lodging|lodgings)\b", re.I)}
# The words that are about the need, as keys. Not "room": "the room is working hard at
# not having noticed" is the same opening card's own fact, and every tavern beat has one.
NEED_KEYS = {NEED_LODGING: ("bed", "beds", "lodging", "lodgings", "inn", "innkeeper")}
# The player asking after it. "room" only in the phrases that mean a room to sleep in.
_ASKS_AFTER = {NEED_LODGING: re.compile(
    r"\b(?:beds?|lodgings?|an inn|the inn|innkeeper|somewhere to sleep|a place to sleep|"
    r"place to stay|somewhere to stay|rooms? for the night|rent (?:a|the) room|"
    r"a room to (?:rent|let)|rooms? to (?:rent|let))\b", re.I)}
# An errand that says it has to be paid for: earning the money is then part of it.
_PAYS_ITS_WAY = re.compile(r"\b(?:pay|paid|afford|purse|money|coin)\b", re.I)
# Asking for paid work, or for coin. "Is there anything I can do for some coin?" and
# "…to earn some coin?" are the two lines on the save that the card never heard.
_ASKS_FOR_WORK = re.compile(
    r"\b(?:for (?:some )?coin|earn(?:ing)? (?:some )?(?:coin|money)|paid work|"
    r"work for (?:coin|pay|money)|any work|a job|need(?:s)? (?:a )?hand|"
    r"(?:who|anyone|anybody) (?:is )?hiring|hire me)\b", re.I)
# The words a fact uses about earning, for the watcher's about-test on such an errand.
MEANS_KEYS = ("coin", "coins", "work", "wage", "wages", "earn", "paid", "hire", "job")
# What a bed costs, in copper, when the world says nothing: the Core Rulebook's "Inn stay
# (common)", 5 sp — "a place on a raised, heated floor and the use of a blanket and a
# pillow". (Poor, 2 sp, is "a place on the floor near the hearth", which is not a bed.)
# A world that exports its own room prices replaces this (docs/from-world-bible.md).
BED_PRICE_CP = 50


def need_of(card: Card) -> str:
    """What this errand needs — "lodging" — or "" for anything else. An errand card
    only; read off its title and its first fact, which is the errand sentence."""
    if not card.is_(TAG_ERRAND):
        return ""
    said = " ".join([card.title] + list(card.facts[:1]))
    return next((n for n, cue in _NEED_CUES.items() if cue.search(said)), "")


def pays_its_way(card: Card) -> bool:
    """Whether the errand says the need must be paid for."""
    return bool(_PAYS_ITS_WAY.search(" ".join([card.title] + list(card.facts[:1]))))


def cannot_pay(scene, price_cp: int = BED_PRICE_CP) -> bool:
    """The player's purse holds less than the price."""
    from . import goods

    pc = scene.pc() if hasattr(scene, "pc") else None
    return pc is not None and goods.in_copper(getattr(pc, "purse", None) or {}) < price_cp


def where_met(need: str, places, at: str = ""):
    """The place among `places` that meets this need, or None. Lodging is the
    settlement table's own `lodging` slot (`schemes.PLACE_KINDS`: the tavern, the
    inn), or a place founded with one of those kinds. The one the party stands in
    first, so a card never sends the player to the tavern from inside the inn."""
    if need != NEED_LODGING:
        return None
    from . import places as places_mod
    from . import schemes

    labels = tuple(schemes.PLACE_KINDS.get("lodging") or ())
    kinds = {lbl.removeprefix("the ") for lbl in labels}
    fits = [p for p in places or ()
            if " ".join(str(getattr(p, "name", "")).lower().split()) in labels
            or places_mod.kind_named(getattr(p, "kind", "") or "") in kinds]
    here = [p for p in fits if getattr(p, "id", "") == at]
    return (here or fits or [None])[0]


def _met_fact(place, at: str) -> str:
    """"Beds are let at the tavern." — or, standing in it, who lets them."""
    from . import places as places_mod

    if getattr(place, "id", "") == at:
        keeper, _words = places_mod.keeper_of(getattr(place, "name", ""))
        return f"Beds are let here{', by ' + keeper if keeper else ''}."
    return f"Beds are let at {getattr(place, 'name', 'the inn')}."


def about(card: Card, fact: str, scene=None) -> bool:
    """Whether a proposed fact is about this card: one of its keys, one of its people,
    or one of its identity words — and, for an errand that has to be paid for while the
    player cannot pay, the earning of the money. The watcher's test (`gm/watcher.py`);
    one place, so the rule is not copied there."""
    names = _card_names(card, scene) if scene is not None else []
    if (_hits(card, fact) >= 1 or _names_in(names, fact)
            or _identity_hits(identity_keys(card, names), fact) >= 1):
        return True
    return bool(scene is not None and need_of(card) and pays_its_way(card)
                and cannot_pay(scene) and _identity_hits(MEANS_KEYS, fact) >= 1)


def ground_the_errand(scene, places, turn: int = 0) -> str:
    """Put the place that meets the errand's need on its card, once, without a tick.
    Returns the fact added, or ""."""
    card = next((c for c in load(scene) if c.live and need_of(c)), None)
    if card is None:
        return ""
    at = str(getattr(scene, "at", "") or "")
    place = where_met(need_of(card), places, at)
    if place is None:
        return ""
    fact = _met_fact(place, at)
    if fact in card.facts or any(f.startswith("Beds are let") for f in card.facts):
        return ""
    card.facts = (card.facts + [fact])[-FACT_CAP:]
    _store(scene, card)
    return fact


def errand_progress(scene, places, *, player_text: str = "", outcomes=(),
                    turn: int = 0) -> list[str]:
    """Move an errand with a need on what the engine can see this turn. Returns the
    facts added (the turn log records them).

    Each step lands once (a fact already on the card is not ticked again — asking five
    times is not five steps): asked after it; asked for paid work while unable to pay
    for it (the errand says "you can pay for", and the purse is empty — on the save it
    was `{}` from the first turn); arrived where it is had. A night's `rest` resolved
    where it is had settles the card. Never the model's say-so: these are the player's
    words, the purse, `scene.at` and an outcome's op."""
    card = next((c for c in load(scene) if c.live and need_of(c)), None)
    if card is None:
        return []
    need = need_of(card)
    at = str(getattr(scene, "at", "") or "")
    place = where_met(need, places, at)
    added: list[str] = []
    grounded = ground_the_errand(scene, places, turn=turn)
    if grounded:
        added.append(grounded)

    def step(fact: str) -> None:
        live = find(scene, card.id)
        if live is None or not live.live or fact in live.facts:
            return
        touch(scene, card.id, fact, turn=turn, tick=True)
        added.append(fact)

    text = " ".join(str(player_text or "").split())
    if text and _ASKS_AFTER[need].search(text):
        step("You have asked after a bed for the night.")
    if (text and pays_its_way(card) and cannot_pay(scene)
            and _ASKS_FOR_WORK.search(text)):
        step("With nothing in your purse, you have asked after work to pay for a bed.")
    if place is not None and getattr(place, "id", "") == at:
        step(f"You have found {getattr(place, 'name', 'somewhere')}, where beds are let.")
        # The engine's own night: a `rest` that ran ("… rests for 8 hours."), not one
        # refused mid-conversation (`Engine._op_rest`).
        slept = any(str(getattr(o, "op", "")) == "rest"
                    and str(getattr(o, "status", "") or "") != "refused"
                    and " rests for " in str(getattr(o, "tell", ""))
                    for o in outcomes or ())
        if slept:
            fact = f"You have slept in a bed at {getattr(place, 'name', 'the inn')}."
            live = find(scene, card.id)
            if live is not None and live.live:
                live.facts = (live.facts + [fact])[-FACT_CAP:]
                _store(scene, live)
                resolve(scene, card.id, turn=turn)
                added.append(fact)
    return added
