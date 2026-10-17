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

# The conditions a body can be said to be IN, as the tag vocabulary names them
# (`rules/states.py` TAGS keys; `states.tags_for(key)[0]` is the leaf `has_state` asks).
# Added 2026-10-16 for the owner's report: across three beats a woman "lunges forward, her
# hands reaching out to grab you by the throat", then has "her fingers digging into your
# throat", then "Her fingers tighten around your throat… her grip intended to crush your
# wind" — and the engine had grappled nobody: no grapple op, no `state.held.grappled`. The
# English reader before this (gm/state_claims.py) had no grappled row at all, and its one
# hit that fight was a false "prone" on "aiming to knock you off your feet" — an aim, cut,
# which left the wind-up's filler standing alone as a beat.
#
# Closed on purpose: the conditions a fight's prose puts on a body that the engine would
# hold as a state. Not "unconscious" or "dead" — those are `harmed`'s `down`/`dead`, and
# a second slot for them competes with it (the `attacks` slot measured exactly that:
# harm recall 12/14 -> 8/14). Not "staggered", "shaken" or "frightened": the commonest
# words in fight prose for a step back and a face, rarely the condition.
CONDITIONS = ("grappled", "pinned", "prone", "entangled", "stunned", "dazed", "blinded",
              "deafened", "paralyzed")
# What each condition is, in words a reader answers to (the second read's question) and
# what the engine's NOT holding it means (the fact a repair is given).
_COND_WHAT = {
    "grappled": "grappled — held fast in somebody's grip",
    "pinned": "pinned — held down so that they cannot move",
    "prone": "prone — down on the ground, lying or knocked flat",
    "entangled": "entangled — tangled up or bound by something",
    "stunned": "stunned — senseless for a moment, unable to act",
    "dazed": "dazed — too dazed to act",
    "blinded": "blinded — unable to see",
    "deafened": "deafened — unable to hear",
    "paralyzed": "paralyzed — unable to move at all",
}
_COND_NOT = {
    "grappled": "nobody has hold of {o} — no grapple was made",
    "pinned": "nobody holds {o} down",
    "prone": "{s} {v} still on {p} feet",
    "entangled": "nothing binds or tangles {o}",
    "stunned": "{s} can act as ever",
    "dazed": "{s} can act as ever",
    "blinded": "{s} can see",
    "deafened": "{s} can hear",
    "paralyzed": "{s} can move",
}

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
    # The `CONDITIONS` the engine holds on them after the turn (`has_state` on each key's
    # leaf tag) — what a `conditions` claim is judged against.
    holds: tuple[str, ...] = ()


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
    # Not an intimate beat: an intimate scene between adults is not read for the body's
    # conditions (its own words are the scene's, `GMAgent._repair_state_claims` likewise).
    intimate: bool = False
    # The kinds of place (`places.SETTINGS`) the beat may truthfully put the party in: the
    # union of where it began, where it ends and what its walk passed through
    # (`places.settings_for`). Empty when the engine cannot say, and then no `setting`
    # claim is judged and no setting call is made.
    settings: tuple[str, ...] = ()
    # The player's blows this beat, by the weapon the ENGINE struck with (each attack
    # outcome's `blows[...]["weapon"]`, on a roll the player made), and the weapons the
    # reader may answer with: what the player carries, unarmed, and whatever the engine
    # struck with. Empty `blows` asks nothing (`struck_with`).
    blows: tuple[str, ...] = ()
    arms: tuple[str, ...] = ()
    # The player's attack this beat only OPENED the fight (`battle_joined`, no roll): the
    # first blow is still to be struck, so any blow of theirs the page shows landing is a
    # contradiction (`_struck_early`). The swing question is asked on such a beat too.
    # The engine's own line for it (the joined tell), for the backstop.
    joined: str = ""
    # On a creature's turn (`ctx.acting`), the weapons ITS blows were struck with
    # (`Outcome.blows[...]["weapon"]` on its own attack outcomes), the weapons it may be
    # named with (what it carries and what its stat block prints, unarmed, what it swung),
    # and who it is. Empty `foe_blows` asks nothing (`foe_struck_with`).
    foe: str = ""
    foe_name: str = ""
    foe_blows: tuple[str, ...] = ()
    foe_arms: tuple[str, ...] = ()
    # Every one of its blows this turn was a natural attack (a bite, a claw, a tentacle):
    # then "something else" is the narrator's own word for the limb and is not judged.
    foe_natural: bool = False

    @property
    def bodies(self) -> bool:
        """Whether the reader is asked for `conditions`: in a fight, or on a beat where a
        blow, a spell or a manoeuvre was resolved — the beats where a body's state is
        what the prose is about. Every other beat is asked exactly what it was before, as
        `shown_here` is asked only with somebody away (a slot shown where it cannot apply
        competes with its neighbours: docs/beat-verify.md)."""
        if self.intimate:
            return False
        return self.in_fight or any(o.get("op") in _HARM_OPS for o in self.outcomes)

    @property
    def swings(self) -> bool:
        """Whether the swing question is asked: the player struck (`blows`), or their
        attack only opened the fight (`joined`)."""
        return bool(self.blows) or bool(self.joined)

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
                           [o.get("intent_id") for o in self.outcomes],
                           # The question asked depends on it (`schema`), so the read does.
                           self.bodies, [p.holds for p in self.people],
                           # The attempts question too (`attempts_of`).
                           [(a.code, a.who, a.verdict) for a in attempts_of(self)],
                           self.settings, self.blows, self.arms, self.joined,
                           self.foe, self.foe_blows, self.foe_arms, self.foe_natural],
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
    # Where the party stood before is looked up among the places known HERE, so a walk in
    # from open ground outside this town found nothing and fell back to `end`: start ==
    # end, "the player did not move". Measured on the owner's save, 2026-10-09: "I go to
    # the tavern" from the ridgelines resolved (went by the fields, the outskirts and the
    # gate), and the read-back cut the true walk as "a move the engine did not make" and
    # ended the beat "You are still at the tavern." A place we cannot name here is still
    # not where the party is now: it is named from its own id.
    if was is None and ctx.was_at:
        try:
            here_id = str(getattr(engine.here(), "id", "") or "")
        except Exception:  # noqa: BLE001
            here_id = ""
        if str(ctx.was_at) != here_id:
            from rules import keepers

            # The outskirts ring's "@" is part of the id, never the name.
            start = keepers.label_of(str(ctx.was_at)).lstrip("@") or "somewhere else"
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

    from rules import states

    people = []
    for ref, a in (getattr(scene, "actors", {}) or {}).items():
        dead = bool(getattr(a, "hp", 1) < 0 or a.has_state("state.down.dead"))
        # Asked by tag (law one), never by a condition string: a homebrew hold that tags
        # itself `state.held.grappled` is grappled to this as much as the book's is.
        holds = tuple(k for k in CONDITIONS if a.has_state(states.tags_for(k)[0]))
        people.append(Person(ref=str(ref), name=str(a.name), what=what_they_are(a),
                             pc=bool(getattr(a, "is_pc", False)),
                             down=bool(getattr(a, "is_down", False)), dead=dead,
                             holds=holds))
    # And the people held elsewhere in this town: the beat reader's own list of them, one
    # definition, so the two readers of a beat cannot disagree about who is away.
    from . import beat_reader

    for p in beat_reader.away_people(scene):
        people.append(Person(ref=str(p["ref"]), name=str(p["name"]), here=False))
    clock = getattr(scene, "clock_minutes", None)
    # What kind of place the beat is set in, from the engine's own answers about where it
    # began, where it ends and where it went by. A walk in from somewhere this town cannot
    # name leaves the first half unknown, and then nothing is judged (precision: a sentence set back on
    # the road the party just left is not a deck in a market).
    settings: frozenset[str] = frozenset()
    try:
        here_place = engine.here()
    except Exception:  # noqa: BLE001
        here_place = None
    if here_place is not None and (not ctx.was_at or was is not None):
        settings = places_mod.settings_for(here_place, known)
        # And every place the beat's own walk passed through: "you pass through the docks
        # … into the great square … and into the counting house" is set in streets on the
        # way to a room (the bench's counter-and-go, a false alarm before this).
        on_the_way = [p for p in (places_mod.find(known, w) for w in went_by) if p]
        for p in ([was] if was is not None else []) + on_the_way:
            if settings and p is not here_place:
                more = places_mod.settings_for(p, known)
                settings = (settings | more) if more else frozenset()
    return Facts(start=start, end=end,
                 places=tuple(dict.fromkeys(n for n in (_name_of(p) for p in known) if n)),
                 went_by=tuple(dict.fromkeys(went_by)), pack=pack, props=props,
                 people=tuple(people), clock=None if clock is None else int(clock),
                 outcomes=outcomes, in_fight=bool(getattr(scene, "in_encounter", False)),
                 pc_ref=str(getattr(pc, "ref", "pc") or "pc"),
                 intimate=bool(getattr(ctx, "intimate", False)),
                 settings=tuple(sorted(settings)),
                 **_blows_of(ctx, outcomes, pc),
                 **_foe_blows_of(ctx, outcomes, scene))


UNARMED = "unarmed strike"


def _weapon_name(name) -> str:
    return " ".join(str(name or "").split()).lower()


def _blows_of(ctx, outcomes, pc) -> dict:
    """{"blows", "arms"} for `Facts`: the weapons the player's own blows were struck with
    this beat, and the weapons the reader may name. A blow is the player's when its roll
    was the player's to make (`visibility == "player"`; every non-PC roll is forced hidden,
    `Engine._force_visibility`) — `Outcome` carries no actor, and an NPC's turn is its own
    door (`ctx.acting`)."""
    if pc is None or getattr(ctx, "acting", ""):
        return {}
    blows: list[str] = []
    pc_ref = str(getattr(pc, "ref", "pc") or "pc")
    joined = ""
    for o in outcomes:
        if o.get("op") != "attack" or o.get("status") == "refused":
            continue
        # The first swing that opens a fight is declared and stops (the battle gate):
        # "Battle is joined … Nothing has landed yet — the first blow is still to be
        # struck." No roll, no `blows`. Measured live 2026-10-17 (integration branch,
        # gemma-4-12B): on that turn the page shipped "He bellows … and recoils from your
        # strike" — the claims scrubber had cut the stab sentence before it, the harm
        # repair turned "pain" into "defiance", and nothing else asked whether a blow of
        # the player's had landed at all. The swing question is asked on this beat too,
        # and any blow of theirs it finds is judged against the joined tell.
        if not o.get("rolls") and any(
                isinstance(e, dict) and e.get("kind") == "battle_joined"
                and str(e.get("ref") or "") == pc_ref for e in o.get("effects") or ()):
            joined = joined or str(o.get("tell") or "Nothing has landed yet.")
            continue
        if not o.get("blows"):
            continue
        if not any(isinstance(r, dict) and r.get("visibility") == "player"
                   for r in o.get("rolls") or ()):
            continue
        blows += [_weapon_name(b.get("weapon")) for b in o["blows"]
                  if isinstance(b, dict) and b.get("weapon")]
    if not blows and not joined:
        return {}
    if blows:
        joined = ""
    arms: list[str] = []
    for key in list(getattr(pc, "weapons", None) or ()):
        try:
            name = (pc.weapon(key) or {}).get("name") or key
        except Exception:  # noqa: BLE001 — a weapon the sheet cannot read is named by key
            name = key
        arms.append(_weapon_name(name))
    arms += [UNARMED, *blows]
    return {"blows": tuple(dict.fromkeys(blows)),
            "arms": tuple(dict.fromkeys(a for a in arms if a and a != "improvised weapon")),
            "joined": joined}


def arms_of(a) -> list[str]:
    """The weapons a creature may be named striking with: what it carries (`weapons`,
    `equipped`) and what its stat block prints (`stat_block_attacks` — the barkeep's sap,
    dagger and heavy crossbow), by name. Read off the actor, never off prose."""
    out: list[str] = []
    raw = getattr(a, "weapons", None) or ()
    for key in (list(raw) if not isinstance(raw, dict) else list(raw.keys())):
        try:
            name = (a.weapon(key) or {}).get("name") or key
        except Exception:  # noqa: BLE001 — a weapon the sheet cannot read is named by key
            name = key
        out.append(_weapon_name(name))
    if getattr(a, "equipped", None):
        out.append(_weapon_name(a.equipped))
    try:
        blocks = a.stat_block_attacks() if hasattr(a, "stat_block_attacks") else {}
    except Exception:  # noqa: BLE001 — a block that will not parse names nothing
        blocks = {}
    for options in (blocks or {}).values():
        for option in options or ():
            for att in option or ():
                out.append(_weapon_name(att.get("name") or att.get("key")))
    return [w for w in dict.fromkeys(out) if w and w != "improvised weapon"]


def _foe_blows_of(ctx, outcomes, scene) -> dict:
    """{"foe", "foe_name", "foe_blows", "foe_arms"} for `Facts`: on a creature's turn
    (`ctx.acting`), the weapons its resolved attacks were struck with. Measured live
    2026-10-17 (integration branch, gemma-4-12B): the barkeep's tell was "the one behind
    the bar's attack with the sap misses Kesst Vayr (7 against AC 15)", and the beat wrote
    "The tavern keeper swings the heavy crossbow … the heavy bolt whistles past your ear"
    — a crossbow his stat block prints and the engine never fired, carried into the next
    round's beat. The struck-with question read the player's blows only."""
    acting = str(getattr(ctx, "acting", "") or "")
    actors = getattr(scene, "actors", {}) or {}
    a = actors.get(acting)
    if not acting or a is None or getattr(a, "is_pc", False):
        return {}
    blows: list[str] = []
    for o in outcomes:
        if o.get("op") != "attack" or o.get("status") == "refused" or not o.get("blows"):
            continue
        # The creature's own attack: the stamped actor where the outcome carries one, else
        # a roll nobody showed the player (every non-PC roll is forced hidden).
        who = str(o.get("actor") or "")
        if who and who != acting:
            continue
        if not who and any(isinstance(r, dict) and r.get("visibility") == "player"
                           for r in o.get("rolls") or ()):
            continue
        blows += [_weapon_name(b.get("weapon")) for b in o["blows"]
                  if isinstance(b, dict) and b.get("weapon")]
    if not blows:
        return {}

    def natural(w: str) -> bool:
        try:
            return bool((a.weapon(w) or {}).get("natural"))
        except Exception:  # noqa: BLE001 — a weapon the sheet cannot read is not natural
            return False

    arms = [*arms_of(a), UNARMED, *blows]
    return {"foe": acting, "foe_name": str(a.name), "foe_blows": tuple(dict.fromkeys(blows)),
            "foe_arms": tuple(dict.fromkeys(w for w in arms if w)),
            "foe_natural": all(natural(w) for w in blows)}


def asks_bodies(ctx) -> bool:
    """Whether this beat's read back asks the body's `conditions` (`Facts.bodies`), read
    off the context without building the whole of `facts_from`: the read is on, routed to
    a model, and the beat is a fight's. `GMAgent._repair_state_claims` stands its English
    body question down when this is true — one reader per question."""
    if not ENABLED or not dict(getattr(ctx, "reader", None) or {}).get("model"):
        return False
    if getattr(ctx, "intimate", False):
        return False
    if bool(getattr(getattr(ctx, "scene", None), "in_encounter", False)):
        return True
    return any((o if isinstance(o, dict) else o.as_dict()).get("op") in _HARM_OPS
               for o in getattr(ctx, "outcomes", ()) or ())


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
        # The kind of place, as a slot of this read — only when it is not asked on its
        # own (`SETTING_ALONE`, measured both ways in docs/beat-verify.md).
        **({} if SETTING_ALONE else {"setting": lst({"kind": {
            "type": "string", "enum": list(_settings())}})}),
        # And what the player's blows were struck with, as a slot — measured against the
        # call of its own (`SWING_ALONE`), on a beat where the player struck only.
        **({"struck_with": lst({"weapon": {"type": "string",
                                           "enum": swing_codes(facts)}})}
           if facts.swings and not SWING_ALONE else {}),
    }, "required": ["player_ends_at", "changed_hands", "trades", "harmed", "arrived",
                    "left", "time_of_day", *(["shown_here"] if away else []),
                    *([] if SETTING_ALONE else ["setting"]),
                    *(["struck_with"] if facts.swings and not SWING_ALONE else [])]}


def _settings() -> tuple[str, ...]:
    from rules.places import SETTINGS

    return SETTINGS


def bodies_schema(facts: Facts) -> dict:
    """The body's conditions, asked in a call of their own (`read_bodies`), on a fight's
    beats only (`Facts.bodies`): who, and which of `CONDITIONS`, each with its quote."""
    s = {"type": "string"}
    return {"type": "object", "properties": {"conditions": {
        "type": "array", "maxItems": 6,
        "items": {"type": "object", "properties": {
            "who": {"type": "string", "enum": _who(facts)},
            "condition": {"type": "string", "enum": list(CONDITIONS)}, "quote": s},
            "required": ["who", "condition", "quote"]}}},
        "required": ["conditions"]}


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


# The body's conditions are asked in a call of their own (`read_bodies`), on a fight's
# beats only (`Facts.bodies`); the read above is asked exactly what it was before on every
# beat, fight or not. Measured 2026-10-16 on the bench's 22 fight beats, gemma-4-12B x2:
# folded into that read as one more slot, the conditions read well (claims P 0.91 R 0.83)
# but the slot competed with `harmed` — the CLAUDE.md rule, a model asked for N things
# answers in parallel, and the `attacks` slot's lesson above. Three wordings were tried:
#   * a demonstrated grab at the player that missed, and a sentence of what is NOT a
#     condition: harm claims 15/19 on master -> 7/19, "knocks the wind from your lungs" no
#     longer hurt the player (ho-shove-lands, ho-blow-lands, 0 of 4 reads);
#   * without the demonstrated miss: still 7/19;
#   * a short clause ending "a blow that lands is reported under harmed as well": claims
#     back to 16/20, but the harm ALARMS the second read keeps went 3/6 -> 0/6 (the reader
#     moved "He hits the ground hard" from harm to prone).
# Apart, the harm read is byte-identical to master's on every beat, and this one can show
# what the folded slot could not afford to: an attempt that is no condition.
_BODIES_SYSTEM = (
    "You read a passage of a story told to a player (\"you\") and report every body the "
    "NARRATOR says IS held or impaired at the end of it, in the codes given: grappled "
    "(held fast in somebody's grip), pinned (held down), prone (down on the ground), "
    "entangled, stunned, dazed, blinded, deafened, paralyzed. Copy the passage's own words "
    "exactly into \"quote\". Never report an attempt, a near miss, an aim or a threat — "
    "somebody reaching to grab someone is not grappled, aiming to knock someone down is "
    "not prone — nor what a character only says aloud inside quotation marks. Unconscious "
    "and dead are not conditions here. Leave the list empty when the passage says none; "
    "most passages say none.")
_BODIES_DEMO_USER = (
    "People: pc: Ashka Verel — the player (\"you\"); c4: Dunmar Oake — ferryman; "
    "c5: the drover — commoner\n\n"
    "Passage:\n"
    "Dunmar Oake reaches to catch you by the collar, meaning to pull you off your feet, "
    "and you twist out of his reach. The drover's fist cracks into his jaw and he staggers. "
    "A watchman comes in from the street, seizes the drover by the arm and holds him fast. "
    "Dunmar Oake's foot catches on a rope and he goes down flat on the planks.")
_BODIES_DEMO_ANSWER = {"conditions": [
    {"who": "c5", "condition": "grappled",
     "quote": "seizes the drover by the arm and holds him fast"},
    {"who": "c4", "condition": "prone", "quote": "he goes down flat on the planks"}]}
_BODIES_DEMO2_USER = (
    "People: pc: Ashka Verel — the player (\"you\"); c4: Dunmar Oake — ferryman\n\n"
    "Passage:\n"
    "Dunmar Oake lunges with the boathook, aiming to knock you into the river. The hook "
    "catches your shoulder and knocks the wind out of you, and you stagger a step but keep "
    "your feet. 'Next time you go in,' he says.")
_BODIES_DEMO2_ANSWER = {"conditions": []}


# --- the kind of place, asked on its own ---------------------------------------------------
#
# What KIND of place each sentence shows the player in, from the app's own kinds
# (`places.SETTINGS`), judged in code against `places.settings_for` of where the engine
# holds the party. Measured 2026-10-16 on the report's market fight: "thudding uselessly
# into the wooden planks of the deck" — no deck in a market — passed every check, because
# the only reader of a setting (gm/checks/setting_kind.py) is a word list of a tavern's and
# a room's furniture. That list is not to grow; this replaces growing it.
#
# A LIST, one entry per sentence, for the hour's reason (`schema`'s `time_of_day`): the
# deck was one sentence among a market's, and one answer per passage is the market's.
# The reader is NOT told where the engine holds the party: told "the market", a reader
# reads the market into every sentence (QAGS answers from the text alone, then compares).
SETTING_ALONE = True

_SETTING_SYSTEM = (
    "You read a passage of a story told to a player (\"you\") and report what KIND of "
    "place the narrator shows the player in, sentence by sentence, in the codes given: "
    "\"a town street, square or market\" (the open air among a town's buildings, stalls, "
    "carts and crowds); \"inside a building\" (a room, hall, shop or house, with walls and a "
    "roof round them); \"a tavern or inn\" (its bar, taproom, tankards and patrons); "
    "\"open country\" (fields, forest, hills or wild land, or a road out among them); "
    "\"underground\" (a cave, tunnel, cellar, sewer or mine); \"aboard a ship or boat\" (its "
    "deck, hold, rail or mast). One entry for each sentence whose narration plainly shows "
    "which of these the place round the player is, copying its own words into \"quote\". "
    "Dirt, mud, ground, stone, wood, a table or a crate can be in any of them and show none. "
    "Not a place only seen in the distance, through a door or from outside, spoken of "
    "inside quotation marks, remembered or planned. Leave the list empty when no sentence "
    "shows it.")
# The second sentence of this demonstration is the weak cue, NOT reported: on the first full
# bench (2026-10-16, gemma-4-12B x2) "she lands flat on her back in the dirt" and "the dirt
# of the west crossing" came back as open country, "he stumbles into the nearest table" as
# a tavern, and "You wake on the hard ground … mineral and old stone" as underground — 8 of
# the 18 false setting alarms, every one a thing any place has.
_SETTING_DEMO_USER = (
    "Passage:\n"
    "The crowd presses close between the fish stalls, and the awnings snap overhead. The "
    "carter sprawls in the dirt against an overturned table, groaning. Across the square "
    "the tavern door bangs open on a burst of laughter. The drover swings at you and his "
    "cudgel cracks against the cobbles at your feet. 'I'll see you on the next boat out,' "
    "he spits.")
_SETTING_DEMO_ANSWER = {"setting": [
    {"kind": "a town street, square or market",
     "quote": "The crowd presses close between the fish stalls"},
    {"kind": "a town street, square or market",
     "quote": "his cudgel cracks against the cobbles at your feet"}]}
_SETTING_DEMO2_USER = (
    "Passage:\n"
    "The lantern swings from the rafters above the table. You rise, and the ferryman's "
    "knife flashes. Spray bursts over the rail as the deck "
    "heaves under your boots. He nods at the door. 'Out in the woods they'll never find "
    "you.'")
_SETTING_DEMO2_ANSWER = {"setting": [
    {"kind": "inside a building",
     "quote": "The lantern swings from the rafters above the table"},
    {"kind": "aboard a ship or boat",
     "quote": "Spray bursts over the rail as the deck heaves under your boots"}]}


# --- what the player's blows were struck with ----------------------------------------------
#
# Measured live 2026-10-16: "I grab a shard of the broken pot and stab him" — the engine
# refused the shard (nothing had put one there) and rolled an unarmed strike, 5 non-lethal;
# the page wrote "The shard bites deep into the soft tissue of his shoulder." No reader
# asked what a blow was struck with. Asked only on a beat where the player struck
# (`Facts.blows`), from the weapons the player carries, unarmed, and what the engine swung,
# with "something else" and "not shown" — and compared in code with `Outcome.blows`.
SWING_ALONE = True
OTHER_WEAPON = "something else"
NOT_SHOWN = "not shown"

_SWING_SYSTEM = (
    "You read a passage of a story told to a player (\"you\") in a fight, and report what "
    "the narrator shows each of the player's own blows struck with — landing or missing — "
    "in the codes given. \"unarmed strike\" is a fist, foot, knee, elbow or head. "
    "\"something else\" is a weapon or object not in the list. \"not shown\" when the "
    "sentence shows the blow and never says what it was struck with. One entry per "
    "sentence that shows one of YOUR blows, copying its own words into \"quote\"; never "
    "somebody else's blow, never what a character only says. Leave the list empty when "
    "the passage shows none of your blows.")
_SWING_DEMO_USER = (
    "Your weapons: shortsword, sling, unarmed strike, something else, not shown\n\n"
    "Passage:\n"
    "You drive your knee up into the drover's gut and he folds. He swings his cudgel back "
    "at you and it whistles past your ear. You lunge again. The jagged spar of wood tears "
    "across his cheek. 'Is that all?' he spits.")
# The third entry is the shape of the live defect — a weapon named in a sentence of its
# own after "You lunge", never saying "your": on the first bench run (2026-10-17, x2) the
# reader quoted "You close the distance and lunge" as not shown and passed over "The shard
# bites deep into the soft tissue of his shoulder", both runs.
_SWING_DEMO_ANSWER = {"struck_with": [
    {"weapon": "unarmed strike", "quote": "You drive your knee up into the drover's gut"},
    {"weapon": "something else", "quote": "The jagged spar of wood tears across his cheek"}]}
# The pommel is the weapon's: "You reverse your rapier and crack the pommel against her
# temple" came back "something else", both runs of the same bench.
_SWING_DEMO2_USER = (
    "Your weapons: shortsword, sling, unarmed strike, something else, not shown\n\n"
    "Passage:\n"
    "You snatch a bottle off the table and smash it across her shoulder. You turn your "
    "shortsword and drive its hilt into her ribs. Your next blow takes her across the "
    "cheek.")
_SWING_DEMO2_ANSWER = {"struck_with": [
    {"weapon": "something else", "quote": "smash it across her shoulder"},
    {"weapon": "shortsword", "quote": "drive its hilt into her ribs"},
    {"weapon": "not shown", "quote": "Your next blow takes her across the cheek"}]}


def swing_codes(facts: Facts) -> list[str]:
    return list(dict.fromkeys([*facts.arms, OTHER_WEAPON, NOT_SHOWN]))


def swing_schema(facts: Facts) -> dict:
    s = {"type": "string"}
    return {"type": "object", "properties": {"struck_with": {
        "type": "array", "maxItems": 6,
        "items": {"type": "object", "properties": {
            "weapon": {"type": "string", "enum": swing_codes(facts)}, "quote": s},
            "required": ["weapon", "quote"]}}},
        "required": ["struck_with"]}


def swing_messages(text: str, facts: Facts) -> list[dict]:
    return [{"role": "system", "content": _SWING_SYSTEM},
            {"role": "user", "content": _SWING_DEMO_USER},
            {"role": "assistant", "content": json.dumps(_SWING_DEMO_ANSWER)},
            {"role": "user", "content": _SWING_DEMO2_USER},
            {"role": "assistant", "content": json.dumps(_SWING_DEMO2_ANSWER)},
            {"role": "user", "content": f"Your weapons: {', '.join(swing_codes(facts))}\n\n"
                                        f"Passage:\n{text}"}]


# --- what a creature's blows were struck with, on its own turn --------------------------
#
# The sibling of the question above, asked on a creature's turn (`Facts.foe_blows`, the
# `outcome` door with `ctx.acting`): its weapons are what it carries and what its stat block
# prints, so a weapon it HAS but did not swing — the barkeep's heavy crossbow on a sap turn —
# is a code the reader can answer with, and code compares it with the engine's. A call of its
# own, not the player's question widened: "YOUR blows" is the player's question's whole
# point, and its demonstrations teach skipping the drover's cudgel.
_FOE_SWING_SYSTEM = (
    "You read a passage of a story told to a player (\"you\") in a fight, and report what "
    "the narrator shows each blow of ONE named attacker struck with — landing or missing — "
    "in the codes given. \"unarmed strike\" is a fist, foot, knee, elbow or head. "
    "\"something else\" is a weapon or object not in the list. \"not shown\" when the "
    "sentence shows that attacker's blow and never says what it was struck with. One entry "
    "per sentence that shows one of THAT ATTACKER's blows, copying its own words into "
    "\"quote\"; never the player's blow or anybody else's, never what a character only says. "
    "Leave the list empty when the passage shows none of that attacker's blows.")
_FOE_SWING_DEMO_USER = (
    "The attacker: the drover\n"
    "The drover's weapons: cudgel, knife, unarmed strike, something else, not shown\n\n"
    "Passage:\n"
    "The drover swings his cudgel at your head and it whistles past your ear. You duck "
    "under it and drive your knee into his gut. He snatches a bottle off the table and "
    "smashes it against your shoulder. 'Is that all you've got?' he spits.")
_FOE_SWING_DEMO_ANSWER = {"struck_with": [
    {"weapon": "cudgel", "quote": "The drover swings his cudgel at your head"},
    {"weapon": "something else", "quote": "smashes it against your shoulder"}]}
_FOE_SWING_DEMO2_USER = (
    "The attacker: the drover\n"
    "The drover's weapons: cudgel, knife, unarmed strike, something else, not shown\n\n"
    "Passage:\n"
    "He reverses the knife and cracks its pommel against your temple. His next blow takes "
    "you across the cheek. Behind him the watchman's spear clatters to the floor, and your "
    "rapier slides off his shoulder.")
_FOE_SWING_DEMO2_ANSWER = {"struck_with": [
    {"weapon": "knife", "quote": "cracks its pommel against your temple"},
    {"weapon": "not shown", "quote": "His next blow takes you across the cheek"}]}


def foe_swing_codes(facts: Facts) -> list[str]:
    return list(dict.fromkeys([*facts.foe_arms, OTHER_WEAPON, NOT_SHOWN]))


def foe_swing_schema(facts: Facts) -> dict:
    s = {"type": "string"}
    return {"type": "object", "properties": {"foe_struck_with": {
        "type": "array", "maxItems": 6,
        "items": {"type": "object", "properties": {
            "weapon": {"type": "string", "enum": foe_swing_codes(facts)}, "quote": s},
            "required": ["weapon", "quote"]}}},
        "required": ["foe_struck_with"]}


def _foe_line(facts: Facts) -> str:
    who = facts.foe_name or "the attacker"
    return (f"The attacker: {who}\n"
            f"{who[:1].upper() + who[1:]}'s weapons: {', '.join(foe_swing_codes(facts))}")


def foe_swing_messages(text: str, facts: Facts) -> list[dict]:
    # The demonstrations answer under the player's key; the live call's schema asks for
    # `foe_struck_with`, so they are shown under that key too.
    one = {"foe_struck_with": _FOE_SWING_DEMO_ANSWER["struck_with"]}
    two = {"foe_struck_with": _FOE_SWING_DEMO2_ANSWER["struck_with"]}
    return [{"role": "system", "content": _FOE_SWING_SYSTEM},
            {"role": "user", "content": _FOE_SWING_DEMO_USER},
            {"role": "assistant", "content": json.dumps(one)},
            {"role": "user", "content": _FOE_SWING_DEMO2_USER},
            {"role": "assistant", "content": json.dumps(two)},
            {"role": "user", "content": f"{_foe_line(facts)}\n\nPassage:\n{text}"}]


def setting_schema() -> dict:
    from rules.places import SETTINGS

    s = {"type": "string"}
    return {"type": "object", "properties": {"setting": {
        "type": "array", "maxItems": 6,
        "items": {"type": "object", "properties": {
            "kind": {"type": "string", "enum": list(SETTINGS)}, "quote": s},
            "required": ["kind", "quote"]}}},
        "required": ["setting"]}


def setting_messages(text: str) -> list[dict]:
    return [{"role": "system", "content": _SETTING_SYSTEM},
            {"role": "user", "content": _SETTING_DEMO_USER},
            {"role": "assistant", "content": json.dumps(_SETTING_DEMO_ANSWER)},
            {"role": "user", "content": _SETTING_DEMO2_USER},
            {"role": "assistant", "content": json.dumps(_SETTING_DEMO2_ANSWER)},
            {"role": "user", "content": f"Passage:\n{text}"}]


# What each kind of place is, said for the second read's question, and what is NOT there
# when the party is not in one (the fact a repair is given).
_SET_WHAT = {
    "a town street, square or market": "out in a town street, square or market, in the "
                                       "open air",
    "inside a building": "inside a building — in a room, with walls and a roof round them",
    "a tavern or inn": "in a tavern or inn — at its bar, in its taproom",
    "open country": "out in open country — in fields, forest or wild land, or on a road "
                    "out among them",
    "underground": "underground — in a cave, tunnel, cellar, sewer or mine",
    "aboard a ship or boat": "aboard a ship or boat — on its deck, in its hold, at its rail",
}
_SET_ABSENT = {
    "a town street, square or market": "no street, square or open sky",
    "inside a building": "no room, roof, rafters or walls round them",
    "a tavern or inn": "no bar, taproom, tankards or patrons",
    "open country": "no fields, forest or wild road",
    "underground": "no cave, tunnel, cellar or rock overhead",
    "aboard a ship or boat": "no ship, boat, deck, hold, rail or mast",
}
_SET_IN = {
    "a town street, square or market": "out in a street or square",
    "inside a building": "inside a building",
    "a tavern or inn": "in a tavern",
    "open country": "out in open country",
    "underground": "underground",
    "aboard a ship or boat": "aboard a ship or boat",
}
# Where the party IS, said from the kinds the place truly is, first match wins.
_SET_HERE = (
    ("a tavern or inn", "inside a tavern"),
    ("inside a building", "indoors, under a roof"),
    ("a town street, square or market", "in the open air of the town"),
    ("underground", "underground"),
    ("open country", "out in open country"),
    ("aboard a ship or boat", "by the water"),
)


def bodies_messages(text: str, facts: Facts) -> list[dict]:
    people = []
    for p in facts.people:
        if not p.here:
            continue
        desc = "the player (\"you\")" if p.pc else (p.what or "")
        people.append(f"{p.ref}: {p.name}" + (f" — {desc}" if desc else ""))
    return [{"role": "system", "content": _BODIES_SYSTEM},
            {"role": "user", "content": _BODIES_DEMO_USER},
            {"role": "assistant", "content": json.dumps(_BODIES_DEMO_ANSWER)},
            {"role": "user", "content": _BODIES_DEMO2_USER},
            {"role": "assistant", "content": json.dumps(_BODIES_DEMO2_ANSWER)},
            {"role": "user", "content": f"People: {'; '.join(people)}\n\nPassage:\n{text}"}]


# --- the attempts: a check or a save told the other way round ----------------------------
#
# The third question, in a call of its own like the body's (`read_attempts`), asked only
# on a beat where the engine settled a check or a save (`attempts_of`). Measured 2026-10-16
# on 0.2.20's code: nothing compared the page with a check's verdict. The claims scrubber
# (`rules/intents.py`, English regex) backs ANY success claim once the turn has any
# verdict, so a failed lift told as the cart rising, or a refused request told as the
# person agreeing, shipped. docs/beat-verify.md, "The attempts", has the bench.
#
# Prior art: tools built on the same split — the engine rolls, a model narrates — report
# this exact defect (agentic-dm-engine issue #34, a death save narrated "passed" under a
# "fail" badge), and the one repair found in the open (infinite-realms-app PR #345) reads
# "you succeed"/"you manage to" by regex and spent four rounds narrowing it against false
# alarms: the endless loop the owner named. Here the reader states, per attempt, a closed
# answer, and code compares it with the verdict (QAGS's shape: the engine's side is never
# read). Attacks are not listed: a blow's landing is `blows_shown`'s, read from the
# engine's own blow records; listing them here would judge one sentence twice.
SHOWN = ("succeeds", "fails", "unsure")
# The ops whose verdict is a check's or a save's, the attempt's own success or failure.
# Not an attack, a manoeuvre or a spell: their verdicts are hits and misses, and the blow
# lane owns them. A whitelist, so an op that grows a verdict later is asked about only once
# somebody has looked at what its verdict means.
_ATTEMPT_OPS = ("check", "save", "judge", "mend", "trade_lore", "haggle", "work", "track",
                "extinguish", "break_free", "repair")


@dataclass(frozen=True)
class Attempt:
    code: str              # "a1", the reader's key
    who: str               # the ref of whoever made it
    label: str             # the roll, as the engine labels it ("Strength check")
    verdict: str           # "success" | "failure", the engine's
    why: str = ""          # what it was for, in plain words, never the verdict
    save: bool = False
    request: str = ""      # "payment" | "favour" — a Diplomacy request (`rules/requests.py`)
    of: str = ""           # who a request or an aid was made of


def _roll_label(o: dict, at: int = 0) -> str:
    rolls = [r for r in o.get("rolls") or () if isinstance(r, dict)]
    return str(rolls[at].get("label") or "") if len(rolls) > at else ""


def attempts_of(facts: Facts) -> list[Attempt]:
    """Every check and save this turn settled, with its verdict: the engine's side of the
    attempts question. Built from the outcome records only — the op, the stamped `actor`,
    the roll's own label, and the structured effects of a request or an aid — never from
    a tell's words. An outcome with no actor on record (a turn log written before the
    stamp) is left out: there is nobody to name, so nothing is asked."""
    out: list[Attempt] = []
    for o in _resolved(facts):
        verdict = str(o.get("verdict") or "")
        if o.get("op") not in _ATTEMPT_OPS or verdict not in ("success", "failure"):
            continue
        who = str(o.get("actor") or "")
        if not who or facts.person(who) is None:
            continue
        label = _roll_label(o) or f"{str(o.get('op')).replace('_', ' ')} attempt"
        aid = next((e for e in _effects(o) if e.get("kind") == "aid"), None)
        asked = next((e for e in _effects(o) if e.get("kind") == "request"), None)
        if aid is not None:
            # Aid Another is two attempts: the helper's against the book's 10, and the
            # helped person's own effort (CRB p.86). The outcome's verdict is the second.
            # Live 2026-10-16: the player's help failed and the smith lifted the cart
            # alone, and the page said exactly that — one verdict would have called it
            # wrong.
            helped = str(aid.get("ref") or "")
            out.append(Attempt(f"a{len(out) + 1}", who, label,
                               "success" if aid.get("made") else "failure", of=helped))
            if facts.person(helped) is not None and "done" in aid:
                helper = "you" if who == facts.pc_ref else _name(facts, who)
                out.append(Attempt(
                    f"a{len(out) + 1}", helped, "their own effort at the task",
                    "success" if aid.get("done") else "failure",
                    why=f"the task {helper} tried to help with"))
            continue
        why = str(o.get("because") or "").strip()
        if asked is not None:
            of = str(asked.get("ref") or "")
            kind = "payment" if asked.get("request") == "payment" else "favour"
            what = "payment for the work" if kind == "payment" else "a favour"
            out.append(Attempt(f"a{len(out) + 1}", who, label, verdict,
                               why=f"asking {_name(facts, of)} for {what}",
                               request=kind, of=of))
            continue
        out.append(Attempt(f"a{len(out) + 1}", who, label, verdict, why=why,
                           save=o.get("op") == "save" or label.lower().endswith(" save")))
    return out


def attempts_schema(attempts: list[Attempt]) -> dict:
    """One required property per listed attempt, each a closed `shown` and its quote.
    Required properties and enums are what this stack enforces (memory
    `ollama-schema-enforcement`), so every attempt is answered, if only with "unsure"."""
    s = {"type": "string"}
    return {"type": "object", "properties": {
        a.code: {"type": "object", "properties": {
            "shown": {"type": "string", "enum": list(SHOWN)}, "quote": s},
            "required": ["shown", "quote"]} for a in attempts},
        "required": [a.code for a in attempts]}


_ATTEMPTS_SYSTEM = (
    "You read a passage of a story told to a player (\"you\"), and a list of attempts "
    "the rules settled this turn — who tried what. For each attempt, say how the passage "
    "tells it turning out:\n"
    "succeeds: the passage shows it working — the thing done, the person won over or "
    "agreeing, the lie believed, the trail found; for a save, the person shrugs off or "
    "escapes what it was against.\n"
    "fails: the passage shows it not working — the thing not done, the person refusing "
    "or unmoved, the lie doubted, nothing found; for a save, it takes hold of them.\n"
    "unsure: the passage does not show how it turned out — only the try, or nothing about "
    "it at all, or something the passage leaves open.\n"
    "A person's spoken answer to what they were asked IS how it turned out. A threat, a "
    "plan or a hope is not. Copy the passage's own words that show it into \"quote\"; "
    "\"\" when unsure.\n"
    # Measured 2026-10-17: every bench beat with no check of its own was given one failed
    # check the page never tells (four kinds, 71 beats each). Without this line and the
    # third demonstration, a failed "Perception check: the player looks about" was read
    # as succeeding on 20-22 of 71 beats — any description of what is in view — and the
    # second read kept 3-4 of those. With them: 3-5 of 71 claimed, 1-2 kept, and the
    # 32 labelled attempt claims and 11 alarms on the gold beats unchanged.
    "Most passages show the outcome of few of the attempts listed, often none: a passage "
    "about something else says nothing of an attempt, and a description of what is there "
    "to be seen is not a search or a look succeeding unless it finds what was looked for.")
_ATTEMPTS_DEMO_USER = (
    "People: pc: Ashka Verel — the player (\"you\"); c4: Dunmar Oake — ferryman; "
    "c5: the drover — commoner\n"
    "Attempts:\n"
    "a1: you (the player) — Climb check: the player climbs the toll-house wall\n"
    "a2: you (the player) — Diplomacy check: asking Dunmar Oake for a favour\n"
    "a3: the drover — Sense Motive check\n\n"
    "Passage:\n"
    "You get a boot into a gap in the stones and haul yourself up until your fingers "
    "close on the top of the wall, and you swing over onto the roof. Below, Dunmar Oake "
    "folds his arms. 'Not a chance,' he says. 'Find your own boat.' The drover spits into "
    "the river.")
_ATTEMPTS_DEMO_ANSWER = {
    "a1": {"shown": "succeeds", "quote": "you swing over onto the roof"},
    "a2": {"shown": "fails", "quote": "'Not a chance,' he says"},
    "a3": {"shown": "unsure", "quote": ""}}
_ATTEMPTS_DEMO2_USER = (
    "People: pc: Ashka Verel — the player (\"you\"); c4: Dunmar Oake — ferryman\n"
    "Attempts:\n"
    "a1: you (the player) — Fortitude save: the eel's venom\n"
    "a2: Dunmar Oake — Perception check: he watches the far bank\n\n"
    "Passage:\n"
    "The bite throbs, and for a moment your vision swims — then it clears, and the "
    "numbness ebbs out of your hand. Dunmar Oake squints across the water toward the far "
    "bank, chewing his lip.")
_ATTEMPTS_DEMO2_ANSWER = {
    "a1": {"shown": "succeeds", "quote": "it clears, and the numbness ebbs out of your hand"},
    "a2": {"shown": "unsure", "quote": ""}}
# A passage that tells neither attempt: a view described is not a search succeeding.
_ATTEMPTS_DEMO3_USER = (
    "People: pc: Ashka Verel — the player (\"you\"); c4: Dunmar Oake — ferryman\n"
    "Attempts:\n"
    "a1: you (the player) — Perception check: the player scans the river for boats\n"
    "a2: you (the player) — Sleight of Hand check: the player palms a die\n\n"
    "Passage:\n"
    "The ferry landing is quiet at this hour. Nets hang drying from the posts, and through "
    "the thinning mist you can make out the far bank. You tip the last coins from your "
    "pouch into your palm and count them. Dunmar Oake is coiling a rope by the bollard.")
_ATTEMPTS_DEMO3_ANSWER = {"a1": {"shown": "unsure", "quote": ""},
                          "a2": {"shown": "unsure", "quote": ""}}


def _attempt_line(a: Attempt, facts: Facts) -> str:
    who = "you (the player)" if a.who == facts.pc_ref else _name(facts, a.who)
    return f"{a.code}: {who} — {a.label}" + (f": {a.why}" if a.why else "")


def attempts_messages(text: str, facts: Facts, attempts: list[Attempt]) -> list[dict]:
    people = []
    for p in facts.people:
        if not p.here:
            continue
        desc = "the player (\"you\")" if p.pc else (p.what or "")
        people.append(f"{p.ref}: {p.name}" + (f" — {desc}" if desc else ""))
    listed = "\n".join(_attempt_line(a, facts) for a in attempts)
    return [{"role": "system", "content": _ATTEMPTS_SYSTEM},
            {"role": "user", "content": _ATTEMPTS_DEMO_USER},
            {"role": "assistant", "content": json.dumps(_ATTEMPTS_DEMO_ANSWER)},
            {"role": "user", "content": _ATTEMPTS_DEMO2_USER},
            {"role": "assistant", "content": json.dumps(_ATTEMPTS_DEMO2_ANSWER)},
            {"role": "user", "content": _ATTEMPTS_DEMO3_USER},
            {"role": "assistant", "content": json.dumps(_ATTEMPTS_DEMO3_ANSWER)},
            {"role": "user", "content": f"People: {'; '.join(people)}\nAttempts:\n{listed}"
                                        f"\n\nPassage:\n{text}"}]


def attempt_claims(answer: dict, attempts: list[Attempt]) -> list[Claim]:
    """The attempts answer as claims: one per attempt the passage shows either way.
    "unsure" is no claim — it abstains, as "not listed" does."""
    out = []
    if not isinstance(answer, dict):
        return out
    for a in attempts:
        row = answer.get(a.code)
        if isinstance(row, dict) and row.get("shown") in ("succeeds", "fails"):
            out.append(Claim("attempt", {"attempt": a.code, "shown": row["shown"]},
                             str(row.get("quote") or "")))
    return out
# The slot version of the setting question (`SETTING_ALONE` False), kept so the bench can
# measure it against the call of its own.
_SYSTEM_SETTING = (
    "\nsetting: EVERY sentence whose narration shows what kind of place the player is in "
    "— a town street, square or market; inside a building; a tavern or inn; open country; "
    "underground; aboard a ship or boat — one entry per sentence. Not a place seen in the "
    "distance or spoken of.")
_DEMO_SETTING = [{"kind": "inside a building",
                  "quote": "You cross to the counter and set your lantern down on it"}]
_DEMO2_SETTING = [{"kind": "a town street, square or market",
                   "quote": "You move toward the eel stalls and stop beside the drover"}]


def messages(text: str, facts: Facts) -> list[dict]:
    away = any(not p.here for p in facts.people)
    one = dict(_DEMO_ANSWER)
    two = dict(_DEMO2_AWAY_ANSWER if away else _DEMO2_ANSWER)
    if not SETTING_ALONE:
        one["setting"], two["setting"] = _DEMO_SETTING, _DEMO2_SETTING
    swing_slot = facts.swings and not SWING_ALONE
    if swing_slot:
        # The demonstrations hold no blow of the player's (the drover's fist is his own).
        one["struck_with"], two["struck_with"] = [], []
    ask = _ask(text, facts)
    if swing_slot:
        ask = ask.replace("\n\nPassage:\n",
                          f"\nYour weapons: {', '.join(swing_codes(facts))}\n\nPassage:\n", 1)
    return [{"role": "system", "content": _SYSTEM + (_SYSTEM_AWAY if away else "")
             + ("" if SETTING_ALONE else _SYSTEM_SETTING)
             + (_SYSTEM_SWING if swing_slot else "")},
            {"role": "user", "content": _DEMO_USER},
            {"role": "assistant", "content": json.dumps(one)},
            {"role": "user", "content": _DEMO2_AWAY_USER if away else _DEMO2_USER},
            {"role": "assistant", "content": json.dumps(two)},
            {"role": "user", "content": ask}]


_SYSTEM_SWING = (
    "\nstruck_with: EVERY sentence that shows one of the player's own blows, landing or "
    "missing, with what it was struck with from \"Your weapons\" — \"unarmed strike\" for a "
    "fist, foot, knee, elbow or head, \"something else\" for a weapon or object not listed, "
    "\"not shown\" when the sentence never says.")


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
                            ("left", "left", ("who",)),
                            ("conditions", "condition", ("who", "condition")),
                            ("setting", "setting", ("kind",)),
                            ("struck_with", "weapon", ("weapon",)),
                            ("foe_struck_with", "foe_weapon", ("weapon",))):
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
    # An attempt's quote may be speech: a person's spoken "Not a chance" to what they were
    # asked IS the request's outcome on the page, and a refused request told as agreement
    # is usually told in the agreeing voice. Every other claim stays narration only.
    written = [(w, w) for w, _n in sentences]
    kept, dropped = [], []
    allowed = {"item": set(facts.things) | {OTHER_THING},
               "from": set(_holders(facts)), "to": set(_holders(facts)),
               "seller": set(_who(facts)), "buyer": set(_who(facts)),
               "who": set(_who(facts)), "how": set(HOW), "place": set(_places(facts)),
               "part": set(PARTS), "condition": set(CONDITIONS),
               "attempt": {a.code for a in attempts_of(facts)}, "shown": set(SHOWN),
               "kind": set(_settings()), "weapon": set(swing_codes(facts))}
    # A creature's weapons are its own codes, not the player's (`foe_swing_codes`).
    foe_codes = set(foe_swing_codes(facts)) if facts.foe_blows else set()
    seen: set[str] = set()
    for c in claims:
        bad = [k for k, v in c.slots.items()
               if k in allowed and str(v) not in allowed[k]
               and not (c.category == "foe_weapon" and k == "weapon")]
        if c.category == "foe_weapon" and str(c.slots.get("weapon")) not in foe_codes:
            bad.append("weapon")
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
        if c.category == "attempt":
            # Joined across a gap with an ellipsis — "the ground shows a clear, recent
            # path... The tracks lead straight toward the knoll" — the quote is two of the
            # page's own pieces, not one (2 of 32 attempt quotes on the first bench run,
            # both true claims, both dropped). The first piece long enough to say anything
            # stands for it; it must still be on the page.
            pieces = [p for p in re.split(r"\.\.\.|…", c.quote)
                      if len(_norm(p).split()) >= MIN_QUOTE_WORDS]
            c.sentence = next((s for s in (place_quote(p, written) for p in pieces) if s),
                              "")
        else:
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
        if facts.bodies:
            # The second question of a fight's beat, in a call of its own (see
            # `_BODIES_SYSTEM` for why it is not a slot of the first).
            msgs = bodies_messages(text, facts)
            if bare_template(model):
                msgs = _raw_prompt(msgs)
            more = chat(msgs, model, host, as_json=True, think=False, temperature=0.0,
                        num_predict=300, provider=provider, api_key=api_key,
                        schema=bodies_schema(facts))
            result.raw += "\n" + more.text
            answer = dict(answer or {}, conditions=(more.json() or {}).get("conditions")
                          or [])
        if SETTING_ALONE and facts.settings:
            # The kind of place, in a call of its own (`_SETTING_SYSTEM`), on every beat
            # whose place the engine can name the kinds of — and on no other, since an
            # unjudgeable answer is a call for nothing.
            msgs = setting_messages(text)
            if bare_template(model):
                msgs = _raw_prompt(msgs)
            where = chat(msgs, model, host, as_json=True, think=False, temperature=0.0,
                         num_predict=300, provider=provider, api_key=api_key,
                         schema=setting_schema())
            result.raw += "\n" + where.text
            answer = dict(answer or {}, setting=(where.json() or {}).get("setting") or [])
        if SWING_ALONE and facts.swings:
            # What the player's blows were struck with, in a call of its own, on a beat
            # where the player struck and on no other (`_SWING_SYSTEM`).
            msgs = swing_messages(text, facts)
            if bare_template(model):
                msgs = _raw_prompt(msgs)
            swung = chat(msgs, model, host, as_json=True, think=False, temperature=0.0,
                         num_predict=300, provider=provider, api_key=api_key,
                         schema=swing_schema(facts))
            result.raw += "\n" + swung.text
            answer = dict(answer or {},
                          struck_with=(swung.json() or {}).get("struck_with") or [])
        if facts.foe_blows:
            # What the creature's blows were struck with, on its own turn, in a call of
            # its own (`_FOE_SWING_SYSTEM`).
            msgs = foe_swing_messages(text, facts)
            if bare_template(model):
                msgs = _raw_prompt(msgs)
            theirs = chat(msgs, model, host, as_json=True, think=False, temperature=0.0,
                          num_predict=300, provider=provider, api_key=api_key,
                          schema=foe_swing_schema(facts))
            result.raw += "\n" + theirs.text
            answer = dict(answer or {}, foe_struck_with=(theirs.json() or {}).get(
                "foe_struck_with") or [])
        claims = claims_of(answer, facts)
        attempts = attempts_of(facts)
        if attempts:
            # The third question, on a beat where a check or a save was settled, in a call
            # of its own (see `_ATTEMPTS_SYSTEM`'s block and docs/beat-verify.md for the
            # measurement of folding it into the first).
            msgs = attempts_messages(text, facts, attempts)
            if bare_template(model):
                msgs = _raw_prompt(msgs)
            more = chat(msgs, model, host, as_json=True, think=False, temperature=0.0,
                        num_predict=80 + 60 * len(attempts), provider=provider,
                        api_key=api_key, schema=attempts_schema(attempts))
            result.raw += "\n" + more.text
            claims += attempt_claims(more.json() or {}, attempts)
        result.claims, result.dropped = validate(claims, text, facts)
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
# The ops after which the player may truthfully be shown holding something the read-back
# has no name for: whatever they resolved, the page may describe it loosely.
_GETTING_OPS = ("loot", "buy", "sell", "forage", "gather", "prospect", "harvest", "craft",
                "quest", "trade")


def _anything_into(facts: Facts, ref: str) -> bool:
    """Whether anything at all came into `ref`'s hands this turn: a resolved getting op,
    or any resolved effect that names them as the receiver of a thing or of coin (`to`,
    or `ref` on an effect written before `to` existed, as `_moves_of_things` reads)."""
    for o in _resolved(facts):
        if o.get("op") in _GETTING_OPS:
            return True
        for e in _effects(o):
            got = e.get("to") if "to" in e else e.get("ref")
            if got == ref and any(k in e for k in ("item", "items", "goods", "purse")):
                return True
    return False
def _parts_with_unlisted(facts: Facts, frm: str, things_moved) -> bool:
    """Whether a thing the engine has no name for, put down by `frm`, is judged at all:
    `frm` a listed person here who is not the player, nothing at all coming into the
    player's hands this turn (`_anything_into`), and no resolved effect moving anything
    out of `frm`'s hands — an engine drop, give or sale of theirs the page may name
    loosely."""
    p = facts.person(frm)
    if p is None or p.pc or not p.here:
        return False
    if _anything_into(facts, facts.pc_ref):
        return False
    return not any(f == frm for _i, f, _t in things_moved)


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


def _condition_unheld(c: Claim, facts: Facts) -> Discrepancy | None:
    """A body said to be in a condition the engine does not hold on it, or None.

    Judged only where the engine has the answer outright: somebody here, on their feet
    (a body on the floor is prone and holdable in every sense, and `harmed` judges the
    fall), not holding the condition after the turn (`Person.holds`, read by tag), and not
    named in one of this turn's effects for that condition — a grapple broken this turn,
    a stand from prone, the hold the engine gave and took inside one batch."""
    who, cond = str(c.slots["who"]), str(c.slots["condition"])
    p = facts.person(who)
    if p is None:
        return None
    if not p.here:
        return _not_here(p, c)
    if p.down or p.dead or cond in p.holds:
        return None
    # "Pinned" said of a body the engine holds grappled is the narrator's word for a hold
    # that is real, not a hold invented: 2 of the 5 alarms on the committed fight
    # recordings (99 fight beats replayed, 2026-10-16) were "Pinned and struggling against
    # your grip" / "still pinned against the table" inside a grapple the engine had made.
    # The defect this slot exists for is the hold from nowhere; a pin inside a grapple is
    # degree, and the tells say which it is.
    if cond == "pinned" and "grappled" in p.holds:
        return None
    for o in _resolved(facts):
        for e in _effects(o):
            if str(e.get("ref") or "") == who and cond in {
                    str(v).lower() for v in e.values() if isinstance(v, str)}:
                return None
    if p.pc:
        subject, verb, obj, poss, name = "you", "are", "you", "your", "You (the player)"
    else:
        subject, verb, obj, poss = "they", "are", "them", "their"
        name = _name(facts, who)
        name = name[:1].upper() + name[1:]
    why = _COND_NOT[cond].format(s=subject, v=verb, o=obj, p=poss)
    return Discrepancy(
        "contradiction", "condition",
        f"{name} {'are' if p.pc else 'is'} not {cond}: {why}. The rules put no such state "
        f"on {obj}.", c.sentence, "", c, ref=who)


def _attempt_fact(a: Attempt, facts: Facts) -> str:
    """The engine's verdict on one attempt, as the fact a one-sentence repair is given:
    who, what, and what it means on the page — with no number (the third law: the margin
    stays the engine's)."""
    pc = a.who == facts.pc_ref
    subj = "You (the player)" if pc else _name(facts, a.who)
    subj = subj[:1].upper() + subj[1:]
    obj = "you" if pc else "them"
    of = _name(facts, a.of) if a.of else ""
    the = "" if a.label.lower().startswith(("the ", "their ")) else "the "
    what = f"{the}{a.label}" + (f" ({a.why})" if a.why else "")
    ok = a.verdict == "success"
    if a.request:
        asked = "payment for the work" if a.request == "payment" else "the favour"
        if ok:
            return (f"{of[:1].upper() + of[1:]} agrees to the request for {asked}: the "
                    f"answer is yes.")
        return (f"{of[:1].upper() + of[1:]} says no to the request for {asked}"
                + (" and pays nothing: nothing changes hands." if a.request == "payment"
                   else ": the favour is refused.")
                + " The answer is no, however it is put.")
    if a.of:
        return (f"{subj} {'help' if pc else 'helps'} {of}: the help makes a difference."
                if ok else
                f"{subj} {'do' if pc else 'does'} not manage to help {of}: the help makes "
                f"no difference to {of}'s effort.")
    if a.save:
        they = "you" if pc else "they"
        return (f"{subj} {'make' if pc else 'makes'} {what}: {they} resist it, and it does "
                f"not take hold of {obj}." if ok else
                f"{subj} {'fail' if pc else 'fails'} {what}: it takes hold of {obj}, and "
                f"{they} do not shrug it off.")
    return (f"{subj} {'succeed' if pc else 'succeeds'} at {what}: the attempt works." if ok
            else f"{subj} {'fail' if pc else 'fails'} at {what}: the attempt does not work, "
                 f"and what was tried is not done.")


def _said_weapon(name: str) -> str:
    return ("bare hands — a fist, foot, knee, elbow or head" if name == UNARMED
            else f"the {name}")


def _weapon_wrong(c: Claim, facts: Facts) -> Discrepancy | None:
    """A player's blow shown struck with something the engine did not swing, or None.

    Judged only on a beat where the engine records the player's blows (`Facts.blows`), and
    never for "not shown". "something else" is judged: the live shard was exactly that — a
    thing no list held, against an unarmed strike the engine rolled."""
    said = str(c.slots.get("weapon") or "")
    if not facts.blows or said in ("", NOT_SHOWN) or said in facts.blows:
        return None
    struck = " and ".join(_said_weapon(w) for w in facts.blows)
    instead = "anything else" if said == OTHER_WEAPON else f"the {said}"
    return Discrepancy(
        "contradiction", "weapon",
        f"Your (the player's) blow was struck with {struck}, not with {instead}: nothing "
        f"else was in your hand.", c.sentence, "", c)


def _struck_early(c: Claim, facts: Facts) -> Discrepancy | None:
    """A blow of the player's shown on a beat whose attack only opened the fight
    (`Facts.joined`), or None. Any weapon, "not shown" included: no blow was rolled, so
    whatever it was struck with, it was not struck. Whether the sentence shows the blow
    already struck — reaching him, knocking him back — or only drawn, aimed or coming is
    the second read's question (`question`), never code's."""
    if not facts.joined or facts.blows:
        return None
    return Discrepancy(
        "contradiction", "early",
        "No blow has been struck yet: the fight has only just been joined, and your (the "
        "player's) first blow is still to come — nothing of yours has reached anybody, so "
        "nobody is hit, cut, staggered or sent recoiling by it. You square off; the blow is "
        "coming, not landed.", c.sentence, facts.joined, c)


def _foe_weapon_wrong(c: Claim, facts: Facts) -> Discrepancy | None:
    """A creature's blow, on its own turn, shown struck with something the engine did not
    swing, or None. "not shown" is never judged; "something else" is, as for the player."""
    said = str(c.slots.get("weapon") or "")
    if not facts.foe_blows or said in ("", NOT_SHOWN) or said in facts.foe_blows:
        return None
    # A natural attack has no name a reader can hold it to: on the recorded fight beats
    # (2026-10-17, gemma-4-12B x2) the one false alarm of 10 was Zygomind's tentacle
    # written as "the heavy vine strikes your ribs" — "something else", both runs, kept
    # by the second read. A listed weapon it did not swing is still judged.
    if said == OTHER_WEAPON and facts.foe_natural:
        return None
    who = facts.foe_name or "the attacker"
    struck = " and ".join(_said_weapon(w) for w in facts.foe_blows)
    instead = "anything else" if said == OTHER_WEAPON else f"the {said}"
    # The engine's own line for the blow, for the backstop to stand in the cut sentence's
    # place: the attack outcome's tell (its numbers are taken off where it is put).
    line = next((str(o.get("tell") or "") for o in _resolved(facts)
                 if o.get("op") == "attack" and o.get("blows") and o.get("tell")
                 and str(o.get("actor") or facts.foe) == facts.foe), "")
    return Discrepancy(
        "contradiction", "foe_weapon",
        f"{who[:1].upper() + who[1:]} struck with {struck}, not with {instead}: that is "
        f"the only weapon {who} used this turn.", c.sentence, line, c, ref=facts.foe)


def _taken_though_refused(c: Claim, facts: Facts) -> Discrepancy | None:
    """The player shown picking up a thing on a turn the engine refused a pick-up of
    something that is not there (`Engine._picked_from_nowhere`, code `not_here`), or None.

    The read judges nothing taken off the floor ("a stone picked up is the world's"), and
    that was right while the world never ran out. It runs out now (2026-10-16): on the live
    check "I pick up one of the crates of dried fruit and throw it" was refused — "There is
    no one of the crates of dried fruit here … to pick up" — and the page wrote "you have to
    wrench it from the pile. You heave the wood and the heavy, sticky fruit, and it flies."
    The refusal's own sentence is the fact, and the line the backstop puts in."""
    if c.category != "hands" or str(c.slots.get("to")) != facts.pc_ref:
        return None
    if str(c.slots.get("from")) not in (FLOOR, NOBODY, NEW_PERSON):
        return None
    why = next((_refusal_line(o) for o in facts.outcomes
                if o.get("op") == "give" and o.get("status") == "refused"
                and o.get("code") == "not_here" and _refusal_line(o)), "")
    if not why:
        return None
    return Discrepancy("contradiction", "hands",
                       f"Nothing was picked up: {why} The player's hands stay empty of it.",
                       c.sentence, why, c)


def _setting_wrong(c: Claim, facts: Facts) -> Discrepancy | None:
    """A sentence set in a kind of place the party is not in, or None.

    Judged only where the engine names the kinds of both ends of the beat
    (`Facts.settings`), and generously (`places.settings_for`): a cellar is a room and a
    vault, the outskirts are road and town, a boat is the docks' own. The fact the repair
    is given says where the party is and names what is not there."""
    kind = str(c.slots.get("kind") or "")
    if not facts.settings or not kind or kind in facts.settings:
        return None
    # A sentence that names the place the engine holds the party at is set there by the
    # narrator's own word, whatever kind the reader inferred from the rest: "the dirt of
    # the west crossing mingling with the blood on his tunic" was open country to the
    # reader, both runs, both reads (bench, 2026-10-16). Names compared, never English read.
    said = f" {_norm(c.sentence)} "
    for name in dict.fromkeys((facts.start, facts.end, *facts.went_by)):
        own = _norm(name).removeprefix("the ").strip()
        if own and f" {own} " in said:
            return None
    here = next((said for k, said in _SET_HERE if k in facts.settings), "here")
    where = facts.end or "this place"
    return Discrepancy(
        "contradiction", "setting",
        f"The player is at {where}, {here} — not {_SET_IN.get(kind, kind)}. There is "
        f"{_SET_ABSENT.get(kind, 'none of that')} here.", c.sentence, "", c)


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
        refused = _taken_though_refused(c, facts)
        if refused is not None:
            out.append(refused)
            continue
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
            if frm == to or (frm == pc and to == NOBODY):
                continue
            if item == OTHER_THING:
                # A thing the engine has no name for, handed to the player by somebody,
                # on a turn when nothing the engine resolved put anything into their
                # hands: the prose gave it. Measured 2026-10-16 (a real player's game,
                # 0.2.19): "I ask for fair compensation" rolled nothing, and the carter
                # "pull[s] out a small, weathered coin … handing it over with a grunt" —
                # read back as exactly this claim, `something else` from c1 to pc, and
                # skipped here because the thing was unlisted; the next turn "I take the
                # coin" minted it. Not judged from the floor (a stone picked up is the
                # world's) or when anything at all came into the player's hands this
                # turn, so a purchase or a payment the page names loosely still stands.
                if to == pc and frm != FLOOR and frm != NOBODY \
                        and not _anything_into(facts, pc):
                    # The fact names who keeps it and what it must not do. Worded "they
                    # hold nothing new" alone, the first live rewrite (2026-10-16) turned
                    # "He tosses it to you; it lands in your palm" into "He gestures
                    # toward it; it sits in your palm" — still in the hand, and the read
                    # of the rewrite missed it.
                    giver = facts.person(frm)
                    who = giver.name if giver is not None else "whoever holds it"
                    out.append(Discrepancy(
                        "contradiction", "hands",
                        f"Nothing was given to the player: {who} keeps it. It is not "
                        f"handed, tossed, pressed or placed into the player's hands, and "
                        f"it does not land or sit in them.", c.sentence, "", c))
                elif to in (FLOOR, NOBODY) and _parts_with_unlisted(facts, frm, things_moved):
                    # The same gift by the floor. Live on 0.2.20 (2026-10-16): the smith
                    # refused to pay ("says no and pays nothing: nothing changes hands"),
                    # and the page had him pull "a piece of coarse, stained leather" from
                    # his pouch and toss it "into the dirt between you. 'There's your
                    # pay.'" — read back as exactly this claim (`something else`, c4 ->
                    # the floor) and skipped, because the floor is where a stone the
                    # player picks up comes from. Judged only when the one parting with
                    # it is a listed person here (a bird dropping a feather is no
                    # listed person) on a turn the engine moved nothing of theirs and put
                    # nothing in the player's hands; whether it is put down FOR the
                    # player, or is only the smith laying down his own hammer, is the
                    # second read's question (`question`), not code's.
                    who = facts.person(frm).name
                    out.append(Discrepancy(
                        "contradiction", "hands",
                        f"Nothing was given to the player: {who} pays nothing and gives "
                        f"nothing, and keeps whatever {who} holds. Nothing is tossed, "
                        f"dropped, set down or left for the player, and nothing lands at "
                        f"the player's feet.", c.sentence, "", c, ref=frm))
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
            # A deal the engine never had in front of it is not judged. Live on 0.2.20
            # (2026-10-16): a turn with no sale, no purchase and no haggle — a refused
            # request for pay, in conversation — ended "You are still here, and the trade
            # is finished.", read back as a settled sale of `something else`, and the
            # repair wrote "…the trade is not finished.": a trade still open, on a turn
            # that never had one. The engine answers a sale claim only when it holds one
            # of its two sides: a sale, purchase or haggle this turn (refused or not), or
            # a thing it names (the crate in the pack is not sold, whatever the page says
            # — kesst:18, "the transaction is finalized in the eyes of the guild").
            # A rest is a side of one too since 2026-10-17: a room at an inn is bought by
            # resting there (rules/lodging.py), and the live turn that pinned this ("The
            # transaction of coin is a formality…", dn-live) had a refused rest and nothing
            # else — a payment the engine never took, which the page must not keep.
            if item == OTHER_THING and not any(
                    o.get("op") in (*_TRADE_OPS, "haggle", "rest") for o in facts.outcomes):
                continue
            done = [o for o in trades if o.get("status") != "refused"]
            refused = [o for o in trades if o.get("status") == "refused"]
            # A granted request that paid (`Engine._pay_for_work`, a `check` whose record
            # moves coin to the player) is coin exchanged for work: a page calling it a
            # deal done is true, and is not cut as a sale nobody made.
            paid = any(e.get("kind") == "give" and e.get("how") == "paid"
                       and e.get("to") == pc for o in _resolved(facts) for e in _effects(o))
            if s["settled"] and not done and not paid:
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
        elif c.category == "condition":
            found = _condition_unheld(c, facts)
            if found is not None:
                out.append(found)
        elif c.category == "attempt":
            a = next((x for x in attempts_of(facts) if x.code == s["attempt"]), None)
            if a is not None and (s["shown"] == "succeeds") != (a.verdict == "success"):
                out.append(Discrepancy("contradiction", "attempt", _attempt_fact(a, facts),
                                       c.sentence, "", c, ref=a.who))
        elif c.category == "weapon":
            found = _struck_early(c, facts) or _weapon_wrong(c, facts)
            if found is not None:
                out.append(found)
        elif c.category == "foe_weapon":
            found = _foe_weapon_wrong(c, facts)
            if found is not None:
                out.append(found)
        elif c.category == "setting":
            found = _setting_wrong(c, facts)
            if found is not None:
                out.append(found)
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
    if c.category == "hands" and d.line and s.get("from") in (FLOOR, NOBODY, NEW_PERSON):
        # `_taken_though_refused`: a pick-up, not a hand-over — "is something handed to
        # you?" is no question to ask of "you wrench it from the pile … and it flies".
        return ("Does this sentence say that you (the player) pick something up, take hold "
                "of it, or throw it?")
    if c.category == "move":
        return (f"Does this sentence say that you (the player) have left {facts.start} and "
                f"are now somewhere else — not just moving about inside {facts.start}?")
    if c.category == "hands":
        # Not "passes from you to the smith": asked that way, gemma answered "no" to
        # "Korvu takes the crate with a grunt" — the sentence never says "from you", and a
        # people's name is not plainly the smith (probe of 2026-10-03, 0 of 2 such
        # sentences confirmed). The direction is the first read's; this asks only whether
        # the thing moved at all.
        if s["to"] == facts.pc_ref and s["item"] == OTHER_THING:
            # A thing with no name of the engine's: "the something else" is no question
            # a reader answers. Asked whether anything is put in the player's hands.
            return ("Does this sentence say that something is handed over or given to "
                    "you — put into your hands now, not only shown or offered?")
        if s["item"] == OTHER_THING and s["to"] in (FLOOR, NOBODY):
            # Put down FOR the player, or only laid down: "He tosses it into the dirt
            # between you" (the smith's unpaid pay, live 2026-10-16) is the first, the
            # smith setting his own hammer on the anvil the second. The giver by name:
            # the first read already said whose hand it left.
            return (f"Does this sentence say that {_name(facts, s['from'])} gives "
                    f"something to you (the player) — tosses, drops, sets down or leaves "
                    f"it for you, as payment or a gift — not only puts down or throws "
                    f"away their own things?")
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
    if c.category == "condition":
        # Asked as a state at the end of the sentence, with the attempt named as what it
        # is not: the owner's report's first grab was "her hands reaching out to grab you
        # by the throat" — an attempt, the prose's to write — and its later beats had the
        # grip landed, which only the engine may do.
        who = _name(facts, s["who"])
        be = "are" if s["who"] == facts.pc_ref else "is"
        return (f"Does this sentence say that {who} {be} {_COND_WHAT[s['condition']]} — "
                f"actually so, not only grabbed at, aimed at, threatened or nearly?")
    if c.category == "attempt":
        a = next((x for x in attempts_of(facts) if x.code == s["attempt"]), None)
        if a is None:
            return ""
        whose = ("your (the player's)" if a.who == facts.pc_ref
                 else f"{_name(facts, a.who)}'s")
        what = a.label + (f" ({a.why})" if a.why else "")
        if a.save:
            how = ("working — they shrug off or escape what it was against"
                   if s["shown"] == "succeeds" else
                   "failing — what it was against takes hold of them")
        else:
            how = ("working — done, agreed to, believed or found"
                   if s["shown"] == "succeeds" else
                   "failing — not done, refused, doubted or not found")
        return (f"Does this sentence show {whose} attempt — {what} — {how}? Not only the "
                f"try, a threat or a hope.")
    if c.category == "shown":
        return (f"Does this sentence show {_name(facts, s['who'])} here, doing or saying "
                f"something now — not only remembered or spoken of?")
    if d.category == "early":
        # Asked of the blow's ARRIVAL, with the wind-up named as what it is not: a joined
        # turn's page is the player drawing and going for him, and that is true.
        return ("Does this sentence show a blow of yours (the player's) already struck — "
                "reaching, hitting or cutting somebody, or somebody reeling or recoiling from "
                "it — not only drawn, raised, aimed, or still coming?")
    if c.category == "foe_weapon":
        # Asked in `_struck_with`'s shape too; this line is the cache key.
        return f"Which weapon does this sentence show {facts.foe_name}'s blow struck with?"
    if c.category == "weapon":
        # Asked in `_struck_with`'s shape (which weapon, from the codes), not yes-or-no;
        # this line is the cache key and the record of what was asked.
        return "Which of your weapons does this sentence show your blow struck with?"
    if c.category == "setting":
        # Asked of the scene, not of the player's feet: "the club thuds into the planks of
        # the deck" never says where the player stands, and it sets the whole fight on a
        # ship all the same. Probed 2026-10-16 on ten sentences (five true settings, five
        # views, speech, a memory, a wrong guess), gemma-4-12B at temperature 0: "Does
        # this sentence show the place round you as…" and "…describe the place where you
        # are now as…" each refused "Branches whip at your face as you push on through the
        # undergrowth" (9/10); this wording 10/10.
        return (f"Is the scene in this sentence set {_SET_WHAT.get(s['kind'], s['kind'])} — "
                f"where you (the player) are now, not somewhere only seen in the distance or "
                f"from outside, remembered or spoken of?")
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
_CONFIRM_ATTEMPT_SYSTEM = (
    "You answer one yes-or-no question about one sentence of a story told to a player "
    "(\"you\"). A person's spoken answer to what they were asked counts as what happened.")


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
        if d.category == "foe_weapon":
            lead = " ".join(sentences[max(0, at - 2):at]) if at > 0 else ""
            (kept if _foe_struck_with(d, lead, facts, chat, model, host, provider,
                                      api_key) else refuted).append(d)
            continue
        if d.category == "weapon":
            lead = " ".join(sentences[max(0, at - 2):at]) if at > 0 else ""
            (kept if _struck_with(d, lead, facts, chat, model, host, provider, api_key)
             else refuted).append(d)
            continue
        if d.category == "condition" and d.ref:
            # The passage up to the sentence, not one sentence: "He is dazed" names nobody,
            # and with only "He hits the wood of the bar…" before it, the read named the
            # player three times of three (live audit, 2026-10-16) — the "he" was the man
            # struck two sentences earlier.
            lead = " ".join(sentences[max(0, at - 4):at]) if at > 0 else ""
            (kept if _in_condition(d, lead, facts, chat, model, host, provider, api_key)
             else refuted).append(d)
            continue
        # An attempt's outcome may be spoken: the person asked says yes or no aloud
        # (`validate` lets its quote be speech for that reason).
        yes = ask(d.sentence, q, before=before, chat=chat, model=model, host=host,
                  provider=provider, api_key=api_key, spoken=d.category == "attempt")
        (kept if yes else refuted).append(d)
    return kept, refuted, round(time.monotonic() - started, 2)


def ask(sentence: str, q: str, *, before: str = "", chat=None, model: str = "",
        host: str = "", provider: str = "ollama", api_key: str = "",
        spoken: bool = False) -> bool:
    """One closed yes-or-no question about one sentence (`confirm`'s second read), for any
    finder whose finding names a sentence and a question: `GMAgent.polish` asks it of the
    review's truth findings before it cuts a sentence the rewrite could not mend. A call
    that fails answers yes — the finder's answer stands, as in every second read."""
    if chat is None:
        from . import client

        chat = client.chat
    text = ((f"The sentence before it, for context: {before}\n" if before else "")
            + f"The sentence: {sentence}\n\nQuestion: {q}")
    msgs = [{"role": "system", "content": _CONFIRM_ATTEMPT_SYSTEM if spoken
             else _CONFIRM_SYSTEM},
            {"role": "user", "content": text}]
    if bare_template(model):
        msgs = _raw_prompt(msgs)
    try:
        reply = chat(msgs, model, host, as_json=True, think=False, temperature=0.0,
                     num_predict=20, provider=provider, api_key=api_key,
                     schema={"type": "object",
                             "properties": {"answer": {"type": "string",
                                                       "enum": ["yes", "no"]}},
                             "required": ["answer"]})
        return str((reply.json() or {}).get("answer") or "") == "yes"
    except Exception:  # noqa: BLE001 — unconfirmable: the first read's answer stands
        return True


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


def _struck_with(d: Discrepancy, before: str, facts: Facts, chat, model, host, provider,
                 api_key) -> bool:
    """The second read of a `weapon` contradiction, in `_shows`' shape: WHICH weapon the one
    sentence shows the player's blow struck with, from the same codes, compared in code —
    kept only when the answer is neither the engine's weapon nor "not shown". A call that
    fails keeps the contradiction, as every second read does."""
    codes = swing_codes(facts)
    ask = ((f"The sentences before it, for context: {before}\n" if before else "")
           + f"The sentence: {d.sentence}\n\nYour weapons: {', '.join(codes)}\n\n"
           f"Question: what does this sentence show YOUR (the player's) blow struck with? "
           f"\"unarmed strike\" for a fist, foot, knee, elbow or head; \"{OTHER_WEAPON}\" "
           f"for a weapon or object not listed; \"{NOT_SHOWN}\" if it never says or shows "
           f"no blow of yours.")
    msgs = [{"role": "system", "content": _CONFIRM_SYSTEM.replace(
                "one yes-or-no question", "one question")},
            {"role": "user", "content": ask}]
    if bare_template(model):
        msgs = _raw_prompt(msgs)
    try:
        reply = chat(msgs, model, host, as_json=True, think=False, temperature=0.0,
                     num_predict=40, provider=provider, api_key=api_key,
                     schema={"type": "object", "properties": {"weapon": {
                         "type": "string", "enum": codes}}, "required": ["weapon"]})
        said = str((reply.json() or {}).get("weapon") or "")
    except Exception:  # noqa: BLE001 — unconfirmable: the first read's answer stands
        return True
    return bool(said) and said != NOT_SHOWN and said not in facts.blows


def _foe_struck_with(d: Discrepancy, before: str, facts: Facts, chat, model, host,
                     provider, api_key) -> bool:
    """The second read of a `foe_weapon` contradiction: WHICH weapon the one sentence shows
    the creature's blow struck with, from its codes, compared in code — kept only when the
    answer is neither what the engine swung nor "not shown"."""
    codes = foe_swing_codes(facts)
    who = facts.foe_name or "the attacker"
    ask = ((f"The sentences before it, for context: {before}\n" if before else "")
           + f"The sentence: {d.sentence}\n\n{who[:1].upper() + who[1:]}'s weapons: "
           f"{', '.join(codes)}\n\nQuestion: what does this sentence show {who}'s "
           f"blow struck with? \"unarmed strike\" for a fist, foot, knee, elbow or head; "
           f"\"{OTHER_WEAPON}\" for a weapon or object not listed; \"{NOT_SHOWN}\" if it never "
           f"says, or shows no blow of {who}'s.")
    msgs = [{"role": "system", "content": _CONFIRM_SYSTEM.replace(
                "one yes-or-no question", "one question")},
            {"role": "user", "content": ask}]
    if bare_template(model):
        msgs = _raw_prompt(msgs)
    try:
        reply = chat(msgs, model, host, as_json=True, think=False, temperature=0.0,
                     num_predict=40, provider=provider, api_key=api_key,
                     schema={"type": "object", "properties": {"weapon": {
                         "type": "string", "enum": codes}}, "required": ["weapon"]})
        said = str((reply.json() or {}).get("weapon") or "")
    except Exception:  # noqa: BLE001 — unconfirmable: the first read's answer stands
        return True
    return bool(said) and said != NOT_SHOWN and said not in facts.foe_blows


def _in_condition(d: Discrepancy, before: str, facts: Facts, chat, model, host, provider,
                  api_key) -> bool:
    """The second read of a `condition` contradiction, in `_shows`' shape: not "is the man
    pinned?" but WHO the sentence says is in that condition, from the codes, compared in
    code with the person the first read named. Measured on the committed fight recordings
    (2026-10-16, 99 fight beats replayed): asked yes-or-no, "his weight pins yours against
    the shattered furniture" kept a pin on a bystander the first read had named — the
    sentence pins the player, under the man who has hold of him."""
    cond = str(d.claim.slots.get("condition") if d.claim else "")
    codes = [*facts.refs, NEW_PERSON, NOBODY]
    people = "; ".join(
        f"{p.ref}: {p.name}" + (" (the player, \"you\")" if p.pc else
                                f" — {p.what}" if p.what else "")
        for p in facts.people if p.here)
    ask = ((f"The passage before it, for who \"he\", \"she\" and \"they\" are: {before}\n"
            if before else "")
           + f"The sentence: {d.sentence}\n\nPeople: {people}\n\nQuestion: which of these "
           f"people does this sentence say is {_COND_WHAT.get(cond, cond)} — actually so, "
           f"not only grabbed at, aimed at, threatened or nearly? Every one it says so of; "
           f"\"{NEW_PERSON}\" for somebody else, \"{NOBODY}\" if none.")
    msgs = [{"role": "system", "content": _CONFIRM_SYSTEM.replace(
                "one yes-or-no question", "one question")},
            {"role": "user", "content": ask}]
    if bare_template(model):
        msgs = _raw_prompt(msgs)
    try:
        reply = chat(msgs, model, host, as_json=True, think=False, temperature=0.0,
                     num_predict=60, provider=provider, api_key=api_key,
                     schema={"type": "object", "properties": {"who": {
                         "type": "array", "maxItems": 6,
                         "items": {"type": "string", "enum": codes}}},
                         "required": ["who"]})
        named = [str(x) for x in (reply.json() or {}).get("who") or []]
    except Exception:  # noqa: BLE001 — unconfirmable: the first read's answer stands
        return True
    if d.ref in named:
        return True
    # A grapple is two bodies' (CRB p.199: "both you and the target gain the grappled
    # condition"), so a hold is confirmed whichever of the two the read names, so long as
    # the engine holds that one ungrappled too. Probed on the report's beat (2026-10-16, 3 of
    # 3): "her fingers digging into your throat" — the first read named the player, the
    # second the woman doing the gripping, and both are grappled by the book.
    if cond == "grappled":
        return any((p := facts.person(code)) is not None and p.here
                   and "grappled" not in p.holds for code in named)
    return False


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
