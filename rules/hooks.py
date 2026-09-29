"""A quest hook as ingredients, and the approach the engine picks for it.

Measured on the 2026-09-28 playtest (docs/playtest-2026-09-28.md item 12): Drenn Ironvale
walked up to Bobby — his own former teacher, by Bobby's background — and opened "You! You
have the look of someone who can navigate the nuances of a search". The pull had told him
to: "they approach the player and say the first word about it" (rules/cards.py), with the
open objective as its one detail. No offer reached the narrator (the reward never did),
no motive, nothing of who Drenn was to the player. And the same pull fired while the
player was looking for somebody else, so the search was dropped (item 9.2).

Design record: docs/design-d-people.md §4.5–4.6. What the traditions settled:

  * **A situation, not a pitch.** The Alexandrian's *Don't Prep Plots* and *A Plague of
    Patrons*: one job offer is a fragile node; news arrives proactively, reactively or
    opportunistically, "in the general conversation" (*Rumor tables, part 2*). So there
    are several approaches — overheard, a go-between, word sent — and the engine picks
    one from a closed table, never the model.
  * **What was abandoned.** Oblivion's Radiant AI let NPC goals decide for themselves and
    was dialled back before release (secondary sources; no primary interview found).
    Fallout 4's Preston Garvey is the quest-giver who pushes whatever the player is doing,
    and players banish him. So wants never walk up to the player on their own, and the
    pull yields when the player is about their own business.
  * **No cold open by a stranger** (the Angry GM on in-medias-res; the owner's Q27
    ruling, 2026-09-28): a stranger reaches for the player only through an engine event,
    which is another system's business. That row of the table does not exist.

Pure: reads the scene, the card and the reading; writes nothing (the card records its
approach in `cards.thread_to_pull`, the one writer of cards).
"""
from __future__ import annotations

import json
import re

TIED = "tied"
KNOWN = "known"
STRANGER = "stranger"

# The scene states the table is read by.
FIGHT = "fight"
ASKED = "asked"
BUSY = "busy"
PRESENT = "present"
ELSEWHERE = "elsewhere"

APPROACHES = ("overheard", "go_between", "sends_word", "greets", "waits", "asked")
# The approaches that reach for the player, and so rest between showings.
REACHING = frozenset({"overheard", "go_between", "sends_word", "greets"})

# The table (design D §4.6). Each cell is the approaches in the order they are tried; the
# first not yet used on this card is the one given, so a card that comes back does not
# come back the same way (the "shape of the prompt" lesson in CLAUDE.md). A stranger has
# no row that reaches the player unasked except by being seen at it, or mentioned.
TABLE = {
    (PRESENT, STRANGER): ("overheard", "go_between"),
    (PRESENT, KNOWN): ("greets",),
    (PRESENT, TIED): ("greets",),
    (ELSEWHERE, STRANGER): ("go_between",),
    (ELSEWHERE, KNOWN): ("go_between",),
    (ELSEWHERE, TIED): ("sends_word", "go_between"),
}
ONCE = frozenset({"sends_word"})


# --- who the giver is to the player ----------------------------------------------------------

def relationship(scene, actor) -> str:
    """"tied", "known" or "stranger" — engine facts only (fix-interfaces §2.9).

    tied: the giver's world entity is one the PC's background names (`scene.acquainted`,
    written by Lane C), or they hold `bond.knows-you` from a `background:` source.
    known: any other `bond.knows-you`, a recorded regard (the player has dealt with
    them), talking with the player now, or a population record the player has met.
    stranger: none of those — including "no record at all"."""
    from . import states

    if actor is None:
        return STRANGER
    entity = str(getattr(actor, "world_entity_id", "") or "")
    if entity and entity in (getattr(scene, "acquainted", None) or ()):
        return TIED
    knows = [e for e in getattr(actor, "effects", None) or ()
             if states.KNOWS_YOU in (getattr(e, "tags", ()) or ())]
    if any(str(getattr(e, "source", "") or "").startswith("background:") for e in knows):
        return TIED
    if knows:
        return KNOWN
    if actor.has_state(states.REGARD) or actor.has_state(states.TALKING):
        return KNOWN
    from . import population

    rec = population.of_ref(scene, getattr(actor, "ref", ""))
    if rec is not None and rec.get("last_met") is not None:
        return KNOWN
    return STRANGER


def tie_sentence(scene, actor) -> str:
    """The PC's own background sentence that names this person, or "".

    "You learned it from Drenn Ironvale, who was surprised how well you took to it" is
    the whole of what Bobby's past says about Drenn, and it is what a greeting between
    them rests on. Matched by the person's full name, or their given and family name
    both, never one common word."""
    pc = scene.pc() if hasattr(scene, "pc") else None
    if pc is None or actor is None:
        return ""
    ties = [str(t) for t in (getattr(pc, "background_ties", None) or []) if str(t).strip()]
    names = {str(getattr(actor, "name", "") or ""), str(getattr(actor, "true_name", "") or "")}
    for name in (n for n in names if n.strip()):
        words = [w for w in re.findall(r"[A-Za-z][A-Za-z'’-]+", name) if w[:1].isupper()]
        if not words:
            continue
        for t in ties:
            if name in t or (len(words) > 1 and all(re.search(rf"\b{re.escape(w)}\b", t)
                                                    for w in words)):
                return " ".join(t.split())
    return ""


# --- who the player is dealing with, and whether this person was turned to ---------------------

def _pronoun(word: str) -> bool:
    from gm import interpret as _interpret  # noqa: F401  (the pronoun list lives there)

    return word.lower() in _interpret._BARE_PRONOUN


def targets(reading) -> list[tuple[str, str]]:
    """(act, target) for every act of the reading that turns to a person."""
    out = []
    for a in (reading or {}).get("actions") or []:
        if a.get("act") in ("seek", "call_on", "talk", "buy", "give", "insult") \
                and str(a.get("target") or "").strip():
            out.append((str(a["act"]), str(a["target"]).strip()))
    return out


def resolve_target(scene, world, target: str) -> str:
    """The ref a target phrase means here, "" for nobody here, "?" for somebody who is
    not here (a record elsewhere, nobody at all). A bare pronoun is whoever the player is
    in conversation with, else unknown ("")."""
    from . import scope as scope_mod
    from . import states

    t = " ".join(str(target or "").split())
    if not t:
        return ""
    if _pronoun(t):
        talking = [a for a in scene.actors.values()
                   if not a.is_pc and a.has_state(states.TALKING)]
        return talking[0].ref if len(talking) == 1 else ""
    # A name said whole is that person. `scope.in_the_room` counts a word shared with the
    # shown name and the true name twice, so a keeper whose family name the giver shares
    # ("Gribbet Sootspar" beside "Bregan Sootspar") tied with the giver and won the tie.
    bare = re.sub(r"^(?:the|a|an)\s+", "", t.lower())
    for ref, a in (getattr(scene, "actors", {}) or {}).items():
        if a.is_pc:
            continue
        if bare in {str(a.name).lower(), str(getattr(a, "true_name", "") or "").lower()}:
            return ref
    want = {w for w in re.findall(r"[a-z']{3,}", bare)}
    best, score = "", 0
    for ref, a in (getattr(scene, "actors", {}) or {}).items():
        if a.is_pc:
            continue
        owns = {w for w in re.findall(r"[a-z']{3,}", f"{a.name} {getattr(a, 'true_name', '')}"
                                      .lower())}
        shared = len(want & owns)
        if shared > score:
            best, score = ref, shared
    if best and score >= 1:
        ref = scope_mod.in_the_room(scene, t)
        return best if score > 1 or not ref else ref
    return "?"


def dealt_with(scene, actor, reading=None, player_text: str = "", buying: str = "") -> bool:
    """Whether the player is dealing, or has dealt, with this person (design D §4.4).

    Asked of existing state, never of a new flag (the second law): they hold
    `talk.with-you`, a recorded regard or any `bond.*`; or this turn's talk, seek or buy
    turns to them; or a counter opens this turn (`buying`) at the place they keep."""
    from . import states

    if actor is None:
        return False
    if actor.has_state(states.TALKING) or actor.has_state("bond"):
        return True
    for _act, target in targets(reading):
        if resolve_target(scene, None, target) == actor.ref:
            return True
    if not reading and player_text:
        from . import scope as scope_mod

        name_words = {w.lower() for w in re.findall(r"[A-Za-z]{3,}", str(actor.name))}
        said = {w.lower() for w in re.findall(r"[A-Za-z]{3,}", str(player_text))}
        if name_words and name_words & said and scope_mod.in_the_room(scene, player_text) \
                == actor.ref:
            return True
    if buying:
        from . import keepers as keepers_mod

        place = keepers_mod.place_of(getattr(actor, "world_entity_id", "") or "")
        if place and place == getattr(scene, "at", None):
            return True
    return False


# --- the scene, the table, the choice ---------------------------------------------------------

def giver_of(scene, card):
    """The person the matter belongs to: the card's giver, else its first person here,
    else its first person anywhere the scene holds."""
    people = getattr(scene, "people", None) or getattr(scene, "actors", {}) or {}
    actors = getattr(scene, "actors", {}) or {}
    refs = ([card.giver] if getattr(card, "giver", "") else []) + list(card.people or [])
    for r in refs:
        if r in actors:
            return actors[r]
    for r in refs:
        if r in people:
            return people[r]
    return None


def scene_state(scene, card, reading) -> str:
    """"fight", "asked", "busy", "present" or "elsewhere" (design D §4.6).

    busy: the player is seeking or addressing somebody who is not the card's people, or is
    in conversation with somebody else. asked: the player turned to the giver (or is in
    conversation with them). Elsewhere includes a giver behind a shut door."""
    from . import states

    if getattr(scene, "in_encounter", False):
        return FIGHT
    giver = giver_of(scene, card)
    mine = {r for r in ([getattr(card, "giver", "")] + list(card.people or [])) if r}
    actors = getattr(scene, "actors", {}) or {}
    giver_words = {w.lower() for w in re.findall(r"[A-Za-z]{3,}", str(getattr(giver, "name", "")))
                   if w[:1].isupper()} if giver is not None else set()
    for act, target in targets(reading):
        if act not in ("seek", "call_on", "talk", "buy"):
            continue
        ref = resolve_target(scene, None, target)
        if ref and ref in mine:
            return ASKED
        if ref == "?" and giver_words and giver_words & {
                w.lower() for w in re.findall(r"[A-Za-z]{3,}", target)}:
            return ASKED     # the player went looking for the giver by name
        if ref:              # somebody else here, or somebody sought who is not here
            return BUSY
    talking = [a for a in actors.values() if not a.is_pc and a.has_state(states.TALKING)]
    if giver is not None and any(a.ref == giver.ref for a in talking):
        return ASKED
    if talking:
        return BUSY
    present = giver is not None and giver.ref in actors \
        and not giver.has_state("state.hidden")
    return PRESENT if present else ELSEWHERE


def _used(card) -> list[str]:
    return [str(a.get("approach") or "") for a in (getattr(card, "approaches", None) or [])]


def approach(rel: str, state: str, card, *, turn: int = 0, rest: int = 12) -> str:
    """The approach, from the closed table. "" in a fight (no pull, as before).

    Busy always yields ("waits"); asked always answers ("asked"). Otherwise the first of
    the cell's approaches not yet used on this card, once-only ones never twice; and an
    approach that reaches for the player shows once per `rest` turns — inside that, the
    giver waits."""
    if state == FIGHT:
        return ""
    if state == ASKED:
        return "asked"
    if state == BUSY:
        return "waits"
    cell = TABLE.get((state, rel)) or TABLE.get((state, STRANGER)) or ("waits",)
    history = list(getattr(card, "approaches", None) or [])
    reached = [a for a in history if a.get("approach") in REACHING]
    if reached and int(turn) - int(reached[-1].get("turn") or 0) < int(rest):
        return "waits"
    used = _used(card)
    fresh = [a for a in cell if a not in used]
    choice = fresh[0] if fresh else None
    if choice is None:
        again = [a for a in cell if a not in ONCE]
        if not again:
            return "waits"
        # All used: the one used longest ago.
        order = {a: max((i for i, u in enumerate(used) if u == a), default=-1) for a in again}
        choice = min(again, key=lambda a: order[a])
    return choice


# --- the ingredients ----------------------------------------------------------------------------

_ROLE_KEYS = ("Role", "Occupation", "Profession", "Position", "Title")


def _role(world, actor) -> str:
    entity = str(getattr(actor, "world_entity_id", "") or "")
    if world is not None and entity:
        try:
            ent = world.get(entity)
        except Exception:
            ent = None
        facts = dict(getattr(ent, "facts", {}) or {}) if ent is not None else {}
        for k in _ROLE_KEYS:
            v = " ".join(str(facts.get(k) or "").split())
            if v and v.lower() not in ("person", "character", "npc"):
                return v
    return ""


def _scheme_hook(scene, card) -> dict:
    """The scheme card's optional `hook` block, its slots filled, for this card — or {}.
    Read from the shipped document through the instance that opened the card."""
    try:
        from . import schemes as schemes_mod
    except Exception:  # pragma: no cover - schemes is always importable
        return {}
    for inst in getattr(scene, "schemes", None) or []:
        key = next((k for k, cid in (inst.get("cards") or {}).items() if cid == card.id), "")
        if not key:
            continue
        doc = (schemes_mod.all_schemes() or {}).get(inst.get("scheme"))
        spec = next((c for c in (doc or {}).get("cards") or []
                     if isinstance(c, dict) and c.get("key") == key), None)
        hook = (spec or {}).get("hook") or {}
        if not isinstance(hook, dict):
            return {}
        return {k: " ".join(schemes_mod.fill_text(str(v), inst.get("slots") or {}).split())
                for k, v in hook.items() if isinstance(v, str) and v.strip()}
    return {}


def _doing(scene, actor, hook: dict) -> str:
    if hook.get("doing"):
        return hook["doing"]
    from . import population

    rec = population.of_ref(scene, getattr(actor, "ref", "")) if actor is not None else None
    work = str(((rec or {}).get("life") or {}).get("work_name") or "").strip()
    if work:
        return f"at their work as {'an' if work[:1] in 'aeiou' else 'a'} {work}"
    return ""


def ingredients(card, scene, world=None, reading=None) -> dict:
    """What the pull may tell the narrator about this matter: all words, no numbers.

    `giver` {"ref", "name", "role"}; `to_player` {"relationship", "tie"}; `want` (the
    open objective, else the latest fact); `offer` (the card's reward, which never reached
    the narrator before — "no offer" was half of item 12); `motive`, `doing`, `withholds`
    from the scheme card's `hook` block. The secret card's facts are never here: what the
    narrator is not told it cannot tell (the 2026-09-25 hidden-facts ruling)."""
    giver = giver_of(scene, card)
    hook = _scheme_hook(scene, card)
    want = next((str(o.get("text", "")) for o in card.objectives if not o.get("done")), "") \
        or (card.facts[-1] if card.facts else "")
    rel = relationship(scene, giver)
    return {
        # Whether this is a hook at all — somebody who wants something of the player (a
        # quest, or a card with a giver) — or a situation that merely has a person in it,
        # like the opening's errand with the companion beside it.
        "hook": bool(card.kind == "quest" or getattr(card, "giver", "")),
        "giver": {"ref": getattr(giver, "ref", "") or "",
                  "name": str(getattr(giver, "name", "") or ""),
                  "role": _role(world, giver) if giver is not None else ""},
        "to_player": {"relationship": rel, "tie": tie_sentence(scene, giver)},
        "want": " ".join(want.split()),
        "offer": " ".join(str(card.reward or "").split()),
        "motive": hook.get("motive", ""),
        "doing": _doing(scene, giver, hook),
        "withholds": hook.get("withholds", ""),
    }


# --- what the prose is told ---------------------------------------------------------------------

_DEMOS = None


def demonstrations() -> dict:
    """One short scene per approach, in a situation no world shares (a ferry landing, a
    lost net): the shape, never the words. Found through `settings.BASE_DIR`, never
    `__file__` (CLAUDE.md: it lies once frozen)."""
    global _DEMOS
    if _DEMOS is None:
        from pathlib import Path

        from django.conf import settings

        path = Path(settings.BASE_DIR) / "content" / "hooks" / "approaches.json"
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            data = {}
        _DEMOS = {k: str(v) for k, v in (data.get("approaches") or {}).items()}
    return _DEMOS


def _a(word: str) -> str:
    return f"{'an' if word[:1].lower() in 'aeiou' else 'a'} {word}"


def render(ing: dict, how: str, *, head: str = "", first: bool = False) -> str:
    """The pull's text for one approach. `head` is the matter's own line (title, the open
    objective, how long it has been quiet), which every approach but `waits` carries;
    `first` adds the approach's demonstration, once per card."""
    g = ing.get("giver") or {}
    name = g.get("name") or "the one it belongs to"
    # Named, never by ref: the pull carries no number of any kind (a ref is "c4"), which
    # tests/test_narrator_guards.py has held since the pull was written.
    ref = ""
    role = f", {g['role']}" if g.get("role") and g["role"].lower() not in name.lower() else ""
    tie = (ing.get("to_player") or {}).get("tie", "")
    offer, motive = ing.get("offer", ""), ing.get("motive", "")
    doing, withholds = ing.get("doing", ""), ing.get("withholds", "")
    if how == "waits":
        # The pull yields: the matter is not put in front of the model at all, only the
        # instruction that its person stays at their own business (item 9.2).
        return (f"{name}{ref} is busy with their own business this beat: they do not "
                f"approach the player or raise anything with them. The player's own "
                f"purpose comes first.") if g.get("name") else ""
    parts = [head] if head else []
    if not ing.get("hook", True) and how in ("greets", "asked", "go_between", "sends_word"):
        # A situation with a person in it, not somebody's errand for the player: nobody
        # is to ask anything of the player, only let it come up where it fits.
        knows = " They know the player; it comes up between people who know each other." \
            if how == "greets" else ""
        parts.append(f"{name}{ref} is here with the player; if it fits, it may come up in "
                     f"what they say or do, in their own words.{knows}")
        return " ".join(p for p in parts if p)
    if how == "overheard":
        parts.append(
            f"{name}{ref}{role} is here{', ' + doing if doing else ''}, and does not "
            f"approach the player or speak to them. Let it show in the background: "
            f"{name} seen at it, or heard speaking of it to somebody else or to nobody, "
            f"so the player may step in if they choose.")
    elif how == "go_between":
        parts.append(
            f"{name}{role} does not raise it this beat. If somebody the player is already "
            f"dealing with fits it, they mention {name}'s trouble in passing, in one "
            f"sentence of their own; nobody brings {name} on stage.")
    elif how == "sends_word":
        parts.append(
            f"Word comes from {name}{role}: a runner or a note asks the player to come by. "
            f"{name} does not appear.")
    elif how == "greets":
        known = f" {tie}" if tie else ""
        parts.append(
            f"{name}{ref}{role} knows the player.{known} They greet the player as someone "
            f"they know — never as a stranger, never giving their own name as if meeting "
            f"for the first time — and only after the greeting may they raise it, as a "
            f"favour between people who know each other"
            + (f": why it matters to them ({motive}), then what they offer ({offer})."
               if motive and offer else
               f", saying what they offer ({offer})." if offer else "."))
    elif how == "asked":
        why = f" Why it matters to them: {motive}." if motive else ""
        gives = f" What they offer: {offer}." if offer else ""
        parts.append(
            f"The player has turned to {name}{ref}{role}. {name} says what they want, why, "
            f"and what they offer, in their own words.{why}{gives}")
        if withholds:
            parts.append(f"If the player asks how it came about, {name} {withholds} — "
                         f"shown in what they do, never explained.")
    if first:
        demo = demonstrations().get(how, "")
        if demo:
            parts.append(f"(Like this, never these words: {demo})")
    return " ".join(p for p in parts if p)
