"""Where a campaign begins, as documents — the start, not the paragraph about it.

Playtest 2026-09-28, items 2 and 3, measured on the code before this module:

- **Every campaign started in Vormoor.** `opening.starting_place` ranked settlements by how
  much the export wrote about them, and a templated export writes the same amount about
  every one, so the tie fell to summary length and then reverse alphabetical order:
  Vormoor, the last of Aurvantis's sixteen villages, one hundred per cent of the time.
- **The twelve starts were one start.** `SITUATIONS` rolled 1d12 seeded off the campaign
  id — the character's slugified NAME — so a name always got the same start; every one of
  the twelve edges was "something went quiet and nobody says why" (Kate Compton's ten
  thousand bowls of oatmeal: different words, one idea); none put anything in engine state;
  and the character's background was bound after the roll and never shaped it.

What replaced it is a vocabulary rather than a story (docs/design-c-starts.md §2–4):

- **A start is a document** in `content/openings/*.json`, the envelope the backgrounds and
  the schemes use, homebrew in `homebrew/openings/` winning on a shared id. RimWorld's
  scenario is the nearest precedent — a list of parts (arrival, people, conditions,
  incidents) with different values — and Skyrim's *Alternate Start* the proof of demand.
- **It leaves state behind.** Cyberpunk's lifepaths converge and are forgotten; Kenshi's
  starts put a bounty or a missing arm in place at minute one. Here the incident runs as
  ordinary intents through `Engine.validate(..., origin="start:<id>")` — the trusted
  provenance door — so the patient really is dying and the challenger really has
  initiative. No new op, no number authored by a model.
- **It stops at the hand-off.** Blades in the Dark cuts "to the first serious obstacle"
  with the crew "already in action"; the player's own example was the cage owner who walks
  the bonesetter to the patient, talking, and stops where the Heal check begins. The prose
  may not narrate past `hand_off.moment` (`CROSSED`).
- **The town and the start are drawn together, from the campaign's own story seed**, and
  weighted by who the character is: their people's towns, the towns where their
  background's people live, the starts written for their background (Dragon Age's origins,
  with DA:O's lesson that a few engine-real starts beat twelve paragraphs).
- **What was kept on purpose:** three of the old quiet situations, at half weight — Caves
  of Qud keeps Joppa beside its generated villages.

Nothing here names a place, a person or a people. Every name comes from the world at the
moment the start is staged; a document that carries a capitalised word mid-sentence or a
digit is refused with the fix named (`validate`).
"""
from __future__ import annotations

import json
import random
import re
from pathlib import Path

from django.conf import settings

from pathfindergm import files

# --- the vocabulary ---------------------------------------------------------------------------

# What sort of trouble a start opens on. Varied KINDS is the point of the whole module: the
# old table had one kind twelve times.
KINDS = ("attack", "injury", "rescue", "chase", "brawl", "fire", "offer", "arrival",
         "summons", "accused", "quiet")
# Where the player takes over, and what the engine is holding at that moment.
HANDOFFS = ("check", "fight", "offer", "speech", "arrival")
# Where the start stands the party. `road` and `outskirts` VALIDATE now and are refused at
# placement (`placeable`) until Phase 3's I1 lands Lane B's outskirts: a road start with no
# road to stand on would be the gate wearing a road's name.
WHERE_AT = ("place", "lodging", "road", "outskirts")
NOT_YET = {"road": "a road start needs the outskirts (I1)",
           "outskirts": "an outskirts start needs the outskirts (I1)"}
# Who the character is to the town: its own people, a stranger to it, or either.
PEOPLE = ("own", "stranger", "any")
# The incident's verbs. Each becomes an arrival through the scene's one door or an
# ordinary intent through the trusted provenance door — never a new op.
VERBS = ("bring", "wound", "fight")
# How badly a `wound` leaves somebody, by the rulebook's own thresholds: `dying` is one
# below zero (unconscious and losing a hit point a round), `staggered` is exactly zero,
# `hurt` is half.
WOUNDS = ("hurt", "staggered", "dying")
ZONES = ("engaged", "near", "far")
# How many a `bring` or a `fight` means, in words: a document never carries a digit.
COUNTS = {"one": 1, "two": 2, "three": 3, "a few": 3}

# The weights (docs/design-c-starts.md §4.4; owner's answers Q19 and Q21, 2026-09-28).
FOR_THE_BACKGROUND = 6.0    # a start written for this character's background
GENERIC = 1.0               # anybody's start
QUIET = 0.5                 # the three kept quiet situations, a floor and not a habit
OWN_PEOPLE = 3.0            # a town of the character's own people
AWAY_FROM_OWN = 1.0 / 3.0   # ... for a start that wants a stranger (the exile)
TIE_LIVES_HERE = 2.0        # a town where somebody filling the background's tie lives

# The hours a start may open at. The table's own keys (`opening._HOUR_OF`), read rather
# than copied so there is one list; night is not among them on purpose — a locked door at
# midnight with nobody to talk to was the opening this whole line of work replaced.
_LABEL_BANNED = frozenset({"who", "that", "with", "through", "which", "whose", "while"})
_GENDERED = re.compile(r"\b(he|him|his|himself|she|her|hers|herself)\b", re.I)
_DIGIT = re.compile(r"\d")
_SLOT = re.compile(r"\$(\w+)")
_ID = re.compile(r"[a-z][a-z0-9]*(?:-[a-z0-9]+)*")

# What the prose may not narrate once the start has handed over (§4.3): the check's
# result, the fight's first blow, the player's answer. Per hand-off, and per skill for a
# check, because "the bleeding stops" crosses a Heal check and nothing else does.
CROSSED: dict[str, tuple[str, ...]] = {
    # Outcomes only, never the offer of one: "you could kneel and stop the bleeding" is
    # the NOW paragraph's choice and the start's own suggestion (measured on the first
    # offline run, 2026-09-28: it flagged every bonesetter template). So the verbs are
    # the ones that say it happened.
    "heal": (r"\bstabili[sz]ed\b", r"\bbleeding (?:stops|stopped|slows|slowed|eases|eased)",
             r"\b(?:stops|stopped|staunches|staunched) the bleeding",
             r"\b(?:is|was|lies) (?:now )?stable\b", r"\bbreathing again\b",
             r"\bcomes round\b|\bcame round\b", r"\bsets the bone\b",
             r"\byou saved\b"),
    "fight": (r"\byou (?:strike|hit|punch|kick|swing|stab|slash|land)\b",
              r"\byour (?:blow|fist|punch|strike|blade) (?:lands|connects|finds)",
              r"\b(?:falls|fell|drops|dropped|collapses|collapsed|flees|fled) "
              r"(?:to the|in a|like|senseless|unconscious|and)",
              r"\bknocked (?:out|down|senseless)\b"),
    "offer": (r"\byou (?:accept|agree|take the job|take the work|shake on it|say yes)\b",),
    "speech": (r"\byou (?:answer|reply|agree|refuse|accept|promise)\b",),
    "arrival": (),
}

_ALL_CACHE: dict = {}


def _dir() -> Path:
    return Path(settings.BASE_DIR) / "content" / "openings"


def _homebrew() -> Path:
    return Path(settings.CAMPAIGN_DIR).parent / "homebrew" / "openings"


def _stamp(folder: Path) -> tuple:
    if not folder.is_dir():
        return ()
    return tuple((p.name, p.stat().st_mtime_ns, p.stat().st_size)
                 for p in sorted(folder.glob("*.json")))


def all_starts() -> dict[str, dict]:
    """Every start document, shipped then homebrew, the latter winning on a shared id.

    Cached by the folders' own contents (name, mtime, size) rather than in a module-level
    `None` slot: the homebrew folder hangs off CAMPAIGN_DIR, which tests move, and a key
    that includes the folder and what is in it cannot serve one directory's documents to
    another — the leak `tests/conftest._CACHED` exists to stop, closed here by construction.
    """
    key = (str(_dir()), _stamp(_dir()), str(_homebrew()), _stamp(_homebrew()))
    if key in _ALL_CACHE:
        return _ALL_CACHE[key]
    out: dict[str, dict] = {}
    for folder in (_dir(), _homebrew()):
        if not folder.is_dir():
            continue
        for path in sorted(folder.glob("*.json")):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except Exception as exc:
                files.unreadable(path, exc)
                continue
            entries = data.get("starts") if isinstance(data, dict) else None
            if not isinstance(entries, list):
                entries = [data] if isinstance(data, dict) and data.get("id") else []
            for e in entries:
                if isinstance(e, dict) and e.get("id"):
                    out[str(e["id"])] = e
    _ALL_CACHE.clear()
    _ALL_CACHE[key] = out
    return out


def get(start_id: str) -> dict | None:
    return all_starts().get(str(start_id or "").strip().lower())


# The validated set, held beside the very dict it was computed from (an identity check,
# not an id(), which a freed dict's successor can reuse).
_USABLE: list = [None, {}]


def usable() -> dict[str, dict]:
    """The documents that validate. A broken homebrew start is skipped, never drawn."""
    docs = all_starts()
    if _USABLE[0] is not docs:
        _USABLE[:] = [docs, {k: d for k, d in docs.items() if not validate(d)}]
    return _USABLE[1]


# --- the validator ----------------------------------------------------------------------------

def _plain_words(text: str, where: str, problems: list[str]) -> None:
    """No digits and no capitalised word except at a sentence start (or "I").

    Ground every name: the WORLD supplies the names at staging time, the document
    supplies none. A capital mid-sentence is either a name the world may not contain or a
    habit that will read as one."""
    text = str(text or "")
    if _DIGIT.search(text):
        problems.append(f"{where}: no digits — say it in words; the engine owns every number.")
    for sentence in re.split(r"(?<=[.!?])\s+|\n+|[\"'“”]\s*", text):
        words = re.findall(r"[A-Za-z][A-Za-z'’-]*", sentence)
        for w in words[1:]:
            if w[0].isupper() and w != "I" and not w.startswith("I'"):
                problems.append(
                    f"{where}: {w!r} is capitalised mid-sentence — a document names nobody "
                    f"and nowhere; the world's names are filled in when the start is staged.")
                return


def _known_kind(word: str) -> bool:
    from . import places as places_mod
    from . import schemes as schemes_mod

    word = " ".join(str(word or "").split()).lower().removeprefix("the ")
    return (word in places_mod.KINDS or word in ("water", "lodging")
            or bool(schemes_mod.PLACE_KINDS.get(word)))


def validate(doc: dict) -> list[str]:
    """Everything wrong with a start document, all at once, each with the fix named.

    The same contract as `classbuilder.validate_class` and `backgrounds.validate`: refuse
    on save, name the repair, and never let through a document that would silently do
    nothing — or say something the world did not.
    """
    from . import backgrounds as backgrounds_mod
    from . import places as places_mod
    from .tables import SKILLS

    p: list[str] = []
    if not isinstance(doc, dict):
        return ["a start is an object."]
    sid = str(doc.get("id") or "")
    if not _ID.fullmatch(sid):
        p.append("id: lower case words joined by hyphens, and permanent — it is saved "
                 "with every campaign that opens on it.")
    if not str(doc.get("name") or "").strip():
        p.append("name: a start needs a name for the picker.")
    kind = str(doc.get("kind") or "")
    if kind not in KINDS:
        p.append(f"kind: one of {', '.join(KINDS)}; got {kind or 'nothing'}.")

    fits = doc.get("fits") or {}
    if not isinstance(fits, dict):
        p.append("fits: an object (backgrounds, favours, open, scales, needs, people).")
        fits = {}
    known_bgs = backgrounds_mod.all_backgrounds()
    for bg in list(fits.get("backgrounds") or []) + list((fits.get("favours") or {}).keys()):
        if str(bg) not in known_bgs:
            p.append(f"fits: {bg!r} is not a background; the backgrounds are "
                     f"{', '.join(sorted(known_bgs))}.")
    for bg, times in (fits.get("favours") or {}).items():
        try:
            ok = float(times) > 0
        except (TypeError, ValueError):
            ok = False
        if not ok:
            p.append(f"fits.favours: {bg!r} needs a weight above zero.")
    if not fits.get("open", True) and not fits.get("backgrounds"):
        p.append("fits: a start that is not open must name the backgrounds it is for, "
                 "or nobody can ever draw it.")
    for sc in fits.get("scales") or []:
        if sc not in places_mod.SCALES:
            p.append(f"fits.scales: {sc!r} is not a scale; use {', '.join(places_mod.SCALES)}.")
    for need in fits.get("needs") or []:
        for alt in str(need).split("|"):
            if not _known_kind(alt):
                p.append(f"fits.needs: {alt!r} is not a kind of place this app builds "
                         f"(market, gate, lodging, temple, water, …).")
    if str(fits.get("people") or "any") not in PEOPLE:
        p.append(f"fits.people: one of {', '.join(PEOPLE)}.")

    where = doc.get("where") or {}
    at = str(where.get("at") or "") if isinstance(where, dict) else ""
    if at not in WHERE_AT:
        p.append(f"where.at: one of {', '.join(WHERE_AT)}.")
    if at == "place":
        kinds = list(where.get("kinds") or [])
        if not kinds:
            p.append("where.kinds: a start in a place names the places it can stand in.")
        for k in kinds:
            if not _known_kind(k):
                p.append(f"where.kinds: {k!r} is not a kind of place this app builds.")

    from play.opening import _HOUR_OF

    when = " ".join(str(doc.get("when") or "").lower().split())
    if when not in _HOUR_OF:
        p.append(f"when: one of the table's hours ({', '.join(sorted(_HOUR_OF))}); a start "
                 f"never opens at night.")

    lead = doc.get("lead") or {}
    if not isinstance(lead, dict) or not lead:
        p.append("lead: every start has somebody who speaks to the player first.")
        lead = {}
    label = " ".join(str(lead.get("label") or "").split())
    words = label.split()
    if not label.lower().startswith("the ") or not 2 <= len(words) <= 3:
        p.append("lead.label: two or three words beginning 'the' — it becomes the "
                 "person's name on the board (\"the cage owner\").")
    bad = [w for w in words[1:] if w.lower().endswith("ing") or w.lower() in _LABEL_BANNED]
    if bad:
        # Item 4b: "the watchman waving traffic through" was the watchman's NAME on the
        # panel, and "through" became the word the face check keyed him on.
        p.append(f"lead.label: {label!r} is a role phrase, not a name — keep it to the "
                 f"noun and put {' '.join(bad)!r} and what follows in `look`.")
    if lead.get("role") and lead["role"] not in backgrounds_mod.TIE_ROLES:
        p.append(f"lead.role: one of {', '.join(backgrounds_mod.TIE_ROLES)}, or leave it "
                 f"out.")
    if not lead.get("words"):
        p.append("lead.words: the role words the codex and the cast are searched by.")
    for field in ("look", "says"):
        if not str(lead.get(field) or "").strip():
            p.append(f"lead.{field}: required.")
    for field, text in (("lead.look", lead.get("look")), ("lead.says", lead.get("says")),
                        ("doing", doc.get("doing")), ("edge", doc.get("edge")),
                        ("errand", doc.get("errand")),
                        ("hand_off.moment", (doc.get("hand_off") or {}).get("moment"))):
        _plain_words(text, field, p)
        if _GENDERED.search(str(text or "")):
            p.append(f"{field}: no he or she — whoever the world casts in the part brings "
                     f"their own pronouns; say it without one.")
    for field in ("doing", "edge"):
        if not str(doc.get(field) or "").strip():
            p.append(f"{field}: required — what the player is doing, and what is already "
                     f"happening, one sentence each.")

    declared = {"lead"}
    for i, step in enumerate(doc.get("incident") or []):
        w = f"incident[{i + 1}]"
        if not isinstance(step, dict):
            p.append(f"{w}: a step is an object.")
            continue
        verb = str(step.get("do") or "")
        if verb not in VERBS:
            p.append(f"{w}: do is one of {', '.join(VERBS)}; got {verb or 'nothing'}.")
            continue
        slot = str(step.get("slot") or "")
        if verb in ("bring", "fight"):
            if not re.fullmatch(r"[a-z]+", slot) or slot == "lead":
                p.append(f"{w}: slot is a lower-case word naming who this brings in.")
            s_label = " ".join(str(step.get("label") or "").split())
            if not s_label.lower().startswith("the ") or len(s_label.split()) > 3:
                p.append(f"{w}: label is two or three words beginning 'the'.")
            _plain_words(s_label, f"{w}.label", p)
            if not step.get("words"):
                p.append(f"{w}: words — what the codex is asked for.")
            if str(step.get("zone") or "near") not in ZONES:
                p.append(f"{w}: zone is one of {', '.join(ZONES)}.")
            if str(step.get("count") or "one") not in COUNTS:
                p.append(f"{w}: count in words: {', '.join(COUNTS)}.")
            declared.add(slot)
        elif verb == "wound":
            if slot not in declared:
                p.append(f"{w}: ${slot} is not brought in by an earlier step.")
            if step.get("to") not in WOUNDS:
                p.append(f"{w}: to is one of {', '.join(WOUNDS)} — the engine works out "
                         f"the damage from the target's own hit points.")

    hand = doc.get("hand_off") or {}
    h_at = str(hand.get("at") or "")
    if h_at not in HANDOFFS:
        p.append(f"hand_off.at: one of {', '.join(HANDOFFS)}.")
    if not str(hand.get("moment") or "").strip():
        p.append("hand_off.moment: the sentence the opening stops on, before the question.")
    if h_at == "check":
        if str(hand.get("skill") or "") not in SKILLS:
            p.append("hand_off.skill: a real skill for a check hand-off.")
        on = str(hand.get("on") or "").lstrip("$")
        if on not in declared:
            p.append(f"hand_off.on: ${on or '?'} is not a slot the incident brings in.")
    if h_at == "fight" and not any((s or {}).get("do") == "fight"
                                   for s in doc.get("incident") or []):
        p.append("hand_off: a fight hand-off needs a `fight` step in the incident.")

    errand = str(doc.get("errand") or "")
    if not errand.startswith("You came"):
        p.append("errand: begins 'You came' — why the character is here today.")
    sugg = doc.get("suggestions") or []
    if not 2 <= len(sugg) <= 4:
        p.append("suggestions: two to four, in the player's voice.")
    for i, s in enumerate(sugg):
        _plain_words(s, f"suggestions[{i + 1}]", p)
    for i, tag in enumerate(doc.get("tags") or []):
        if not str(tag).startswith("start."):
            p.append(f"tags[{i + 1}]: a start's own tags begin 'start.'.")
    from . import schemes as schemes_mod

    for i, g in enumerate(doc.get("grants") or []):
        w = f"grants[{i + 1}]"
        if not isinstance(g, dict):
            p.append(f"{w}: a grant is an object.")
            continue
        for tag in g.get("tags") or []:
            if not str(tag).startswith(schemes_mod.GRANTABLE):
                p.append(f"{w}: {tag!r} is not grantable; a start grants "
                         f"{', '.join(schemes_mod.GRANTABLE)}.")
            if str(tag).startswith("knows.") and not str(g.get("say") or "").strip():
                p.append(f"{w}: a knows.* grant carries a `say` — the sentence the "
                         f"narrator may state as true.")
        _plain_words(g.get("say"), f"{w}.say", p)
    scheme = str(doc.get("opens_scheme") or "")
    if scheme and not _ID.fullmatch(scheme):
        p.append("opens_scheme: a scheme id, or empty.")
    return p


def placeable(doc: dict) -> str:
    """Why this start cannot be placed today, or "" when it can."""
    at = str((doc.get("where") or {}).get("at") or "")
    return NOT_YET.get(at, "")


# --- which towns, which starts ----------------------------------------------------------------

def towns(world) -> list:
    """The settlements a game may start in: adequately described, and with places.

    Adequate is one section of the world's own prose or four facts — what the opening
    and the brief have to draw on — and a non-empty place set. If nothing qualifies the
    old best-described ranking is the floor, so a sparse world still starts somewhere.
    """
    from play import opening
    from . import places as places_mod

    entities = getattr(world, "entities", None) or {}
    out = []
    for e in sorted(entities.values(), key=lambda e: str(e.id)):
        if not (e.kind in opening.SETTLEMENT_KINDS
                or (e.scale or "").lower() in opening.SETTLEMENT_SCALES):
            continue
        if not (e.sections or len(e.facts or {}) >= 4):
            continue
        try:
            if not places_mod.spots_for(e):
                continue
        except Exception:
            continue
        out.append(e)
    if not out:
        floor = opening.starting_place(world)
        out = [floor] if floor is not None else []
    return out


_TOWN_FACTS: dict = {}


def _town(world, town) -> dict:
    """What the draw asks of a settlement, worked out once per world and town: its place
    labels, its scale, its people, and the roles its residents fill. Measured the first
    time a thousand draws were run: recomputing these per (town, start) pair took over
    ten minutes on Aurvantis (64 towns, 256 residents), almost all of it `role_of`."""
    from . import geography
    from . import names as names_mod
    from . import places as places_mod

    held = _TOWN_FACTS.get(id(world))
    if held is None or held[0] is not world:
        held = _TOWN_FACTS[id(world)] = (world, {})
    got = held[1].get(town.id)
    if got is None:
        spots = places_mod.spots_for(town)
        labels = {" ".join(p.name.lower().split()) for p in spots}
        roles = [geography.role_of(world, r).lower()
                 for r in ((getattr(world, "play", None) or {}).get("cast") or [])
                 if isinstance(r, dict) and str(r.get("home_id") or "") == str(town.id)]
        got = held[1][town.id] = {
            "spots": spots, "labels": labels, "scale": places_mod.scale_of(town),
            "people": names_mod.people_of(world, town.id),
            "roles": [r for r in roles if r],
            "water": _has_water(world, town, labels)}
    return got


def _kind_labels(word: str) -> tuple[str, ...]:
    from . import places as places_mod
    from . import schemes as schemes_mod

    word = " ".join(str(word or "").split()).lower().removeprefix("the ")
    got = schemes_mod.PLACE_KINDS.get(word)
    if got:
        return tuple(got)
    if word in places_mod.KINDS:
        return (f"the {word}",)
    return ()


def _has_water(world, town, labels: set[str]) -> bool:
    """Docks or a bridge among its places, else the land around it (coast, a river)."""
    if labels & {"the docks", "the bridge"}:
        return True
    try:
        from . import geography

        land = geography.land_around(world, town)
        return bool(land.coast or land.water)
    except Exception:
        return False


def spot_for(world, town, doc: dict, rng: random.Random | None = None):
    """The place in this town the start stands the party at, or None if it has none."""
    where = doc.get("where") or {}
    at = str(where.get("at") or "")
    spots = _town(world, town)["spots"]
    by_label = {" ".join(p.name.lower().split()): p for p in spots}
    wanted: list[str] = []
    if at == "lodging":
        wanted = list(_kind_labels("lodging"))
    elif at == "place":
        for k in where.get("kinds") or []:
            wanted.extend(_kind_labels(k))
    found = [by_label[w] for w in dict.fromkeys(wanted) if w in by_label]
    if not found:
        return None
    return found[0] if rng is None else found[rng.randrange(len(found))]


def fits(world, town, doc: dict, pc=None) -> bool:
    """Whether this start can open in this town, for this character."""
    if placeable(doc):
        return False
    f = doc.get("fits") or {}
    bg = str(getattr(pc, "background", "") or "")
    if not f.get("open", True) and bg not in (f.get("backgrounds") or []):
        return False
    facts = _town(world, town)
    scales = f.get("scales") or []
    if scales and facts["scale"] not in scales:
        return False
    labels = facts["labels"]
    for need in f.get("needs") or []:
        ok = False
        for alt in str(need).split("|"):
            alt = alt.strip().lower()
            if alt == "water":
                ok = facts["water"]
            else:
                ok = bool(set(_kind_labels(alt)) & labels)
            if ok:
                break
        if not ok:
            return False
    return spot_for(world, town, doc) is not None


def _town_weight(world, town, doc: dict, pc, tie_roles: tuple[str, ...]) -> float:
    weight = 1.0
    facts = _town(world, town)
    people = str(getattr(pc, "world_people_id", "") or "")
    if people and facts["people"] == people:
        weight *= (AWAY_FROM_OWN if (doc.get("fits") or {}).get("people") == "stranger"
                   else OWN_PEOPLE)
    if tie_roles and _role_lives_in(facts["roles"], tie_roles):
        weight *= TIE_LIVES_HERE
    return weight


def _role_lives_in(said_roles: list[str], roles: tuple[str, ...]) -> bool:
    """Whether a resident's own role fits one of a background's tie roles (the healer a
    bonesetter learned from could live here)."""
    from . import schemes as schemes_mod

    for said in said_roles:
        for role in roles:
            if any(re.search(r"\b" + re.escape(w) + r"\b", said)
                   for w in schemes_mod.role_words(role)):
                return True
    return False


def _doc_weight(doc: dict, pc) -> float:
    f = doc.get("fits") or {}
    bg = str(getattr(pc, "background", "") or "")
    if bg and bg in (f.get("backgrounds") or []):
        return FOR_THE_BACKGROUND
    if not f.get("open", True):
        return 0.0
    base = QUIET if doc.get("kind") == "quiet" else GENERIC
    try:
        return base * float((f.get("favours") or {}).get(bg, 1.0)) if bg else base
    except (TypeError, ValueError):
        return base


def _tie_roles(pc) -> tuple[str, ...]:
    from . import backgrounds as backgrounds_mod

    doc = backgrounds_mod.get(getattr(pc, "background", "")) if pc is not None else None
    return tuple(str(t["role"]) for t in (doc or {}).get("ties") or [] if t.get("role"))


def offer(world, pc=None) -> list[tuple]:
    """Every (town, start, weight) this character could open on, heaviest first — the
    list a picker would show. The weights are the same ones `choose` draws with.

    Held per world and per what the weights read of the character (background, people),
    beside the very objects it was computed from: a thousand draws recomputing it took
    forty-four seconds on Aurvantis."""
    docs = usable()
    key = (id(world), str(getattr(pc, "background", "") or ""),
           str(getattr(pc, "world_people_id", "") or ""))
    held = _OFFERS.get(key)
    if held is not None and held[0] is world and held[1] is docs:
        return list(held[2])
    out = _offer(world, pc, docs)
    _OFFERS[key] = (world, docs, tuple(out))
    return out


_OFFERS: dict = {}


def _offer(world, pc, docs) -> list[tuple]:
    roles = _tie_roles(pc)
    out = []
    for town in towns(world):
        for sid in sorted(docs):
            doc = docs[sid]
            w = _doc_weight(doc, pc)
            if w <= 0 or not fits(world, town, doc, pc):
                continue
            out.append((town, doc, w * _town_weight(world, town, doc, pc, roles)))
    out.sort(key=lambda t: (-t[2], str(t[0].id), t[1]["id"]))
    return out


def choose(world, pc, rng: random.Random, *, start_town: str | None = None,
           start_id: str | None = None) -> tuple:
    """(town, start) in one weighted draw over the pairs, or (town, None).

    One draw over pairs rather than a town and then a start, because they are not
    independent: a ferry rescue needs water and a bout needs somewhere to fight, and a
    town drawn first can leave the character's own start with nowhere to happen.

    A choice made on the new-campaign screen (`start_town`, `start_id`, by id or name) is
    honoured when it fits, and quietly narrows the draw when only one half was chosen.
    None comes back only for a world with no settlement the documents can use, and the
    caller then opens the legacy way.
    """
    pairs = offer(world, pc)
    if start_town:
        want = str(start_town).strip().lower()
        narrowed = [t for t in pairs if want in (str(t[0].id).lower(), t[0].name.lower())]
        pairs = narrowed or pairs
    if start_id:
        narrowed = [t for t in pairs if t[1]["id"] == str(start_id).strip().lower()]
        pairs = narrowed or pairs
    if not pairs:
        # The legacy opening, where it always opened: nothing here fits this world.
        from play import opening

        return opening.starting_place(world), None
    # Sorted by id before drawing, so the draw depends on the seed and the documents,
    # never on dict order.
    pairs = sorted(pairs, key=lambda t: (str(t[0].id), t[1]["id"]))
    total = sum(t[2] for t in pairs)
    point = rng.random() * total
    for town, doc, w in pairs:
        point -= w
        if point < 0:
            return town, doc
    return pairs[-1][0], pairs[-1][1]


def rng_for(story_seed: int, salt: str) -> random.Random:
    """The story's own stream for one question. A STRING seed, which Python hashes the
    same way in every process (unlike `hash()`, which is why `_seed_from` exists); the
    character's name is not part of it, so the name decides nothing."""
    return random.Random(f"{int(story_seed)}:{salt}")


# --- staging ----------------------------------------------------------------------------------

def count_of(step: dict) -> int:
    return COUNTS.get(str(step.get("count") or "one"), 1)


def wound_amount(actor, to: str) -> int:
    """How much damage leaves this creature in the named state, by the rulebook's own
    thresholds and its own hit points — the number is the rule's, never the document's.
    Dying is one below zero; staggered (disabled) is exactly zero; hurt is half."""
    hp = int(getattr(actor, "hp", 0) or 0)
    if to == "dying":
        return max(1, hp + 1)
    if to == "staggered":
        return max(0, hp)
    return max(1, hp // 2)


def crossed(text: str, start: dict) -> list[str]:
    """Phrases in `text` that narrate past the start's hand-off, for the repair to name."""
    hand = (start or {}).get("hand_off") or {}
    at = str(hand.get("at") or "")
    patterns = CROSSED.get(str(hand.get("skill") or ""), ()) if at == "check" \
        else CROSSED.get(at, ())
    out = []
    for pat in patterns:
        m = re.search(pat, text or "", re.I)
        if m:
            out.append(m.group(0))
    return out


def spoken_for(scene) -> set[str]:
    """Every world entity already given a part: the scene's one shared list, and — for a
    save written before that list existed — the people its schemes' slots hold."""
    got = {str(x) for x in (getattr(scene, "spoken_for", None) or []) if x}
    for inst in getattr(scene, "schemes", None) or []:
        for slot in (inst.get("slots") or {}).values():
            if isinstance(slot, dict) and slot.get("entity"):
                got.add(str(slot["entity"]))
    return got


def speak_for(scene, entity_id: str) -> None:
    """Record a world entity as given a part, once."""
    entity_id = str(entity_id or "")
    if entity_id and entity_id not in scene.spoken_for:
        scene.spoken_for.append(entity_id)


def _cast_rows(world, town_id: str | None = None) -> list[dict]:
    rows = [r for r in ((getattr(world, "play", None) or {}).get("cast") or [])
            if isinstance(r, dict) and r.get("id") and r.get("name")]
    if town_id is not None:
        rows = [r for r in rows if str(r.get("home_id") or "") == str(town_id)]
    return sorted(rows, key=lambda r: str(r["id"]))


def _matches(world, row: dict, words) -> bool:
    from . import geography

    said = geography.role_of(world, row).lower()
    return bool(said) and any(re.search(r"\b" + re.escape(str(w).lower()) + r"\b", said)
                              for w in words or ())


def _lead_person(engine, doc: dict, bound: list[dict], rng: random.Random) -> dict | None:
    """Who plays the lead: somebody the character's past names, then a townsperson whose
    own role fits, else nobody in particular (the label and a codex block).

    The first is the one that makes a background matter at the door: the bonesetter's
    teacher, if the teacher is the healer the start wants, is who walks up — and knows
    them. Returns the cast row, or None.
    """
    lead = doc.get("lead") or {}
    role = str(lead.get("role") or "")
    world = engine.world
    by_id = {str(r["id"]): r for r in _cast_rows(world)} if world is not None else {}
    if role:
        for b in bound or []:
            if b.get("role") == role and b.get("entity") in by_id:
                return by_id[b["entity"]]
    if world is None:
        return None
    taken = spoken_for(engine.scene)
    on_board = {str(a.world_entity_id) for a in engine.scene.people.values()
                if a.world_entity_id}
    here = [r for r in _cast_rows(world, engine.scene.location_id)
            if str(r["id"]) not in taken and str(r["id"]) not in on_board
            and _matches(world, r, lead.get("words"))]
    return here[rng.randrange(len(here))] if here else None


def _stand_up(engine, doc: dict, label: str, words, *, zone: str, row: dict | None = None,
              look: str = ""):
    """One person into the scene through the arrival door, with a face and a record.

    The same three steps `new_campaign` has always taken for the opening's companion —
    a population record so the finder keeps them, a face the brief and the check can
    read, a line on the scene's cast ledger so a later "the cage owner" is somebody
    already here — because a person the start brings in is the same kind of person.
    """
    from . import names as names_mod
    from . import npcs
    from . import population
    from .bestiary import instantiate

    scene, world = engine.scene, engine.world
    pc = scene.pc()
    level = int(getattr(pc, "level", 1) or 1)
    words = [str(w) for w in (words or ())]
    if row is not None:
        name, eid = str(row["name"]), str(row["id"])
        template = npcs.block_for(eid, words, level, name)
        actor = instantiate(template, scene=scene, name=name, world_entity_id=eid)
        actor.true_name = name
        own = names_mod.resident_appearance(world, eid)
        actor.appearance = own or names_mod.appearance_for(world, scene.location_id,
                                                          ref=actor.ref or eid)
        scene.arrive(actor, zone=zone, source=f"start:{doc['id']}")
        speak_for(scene, eid)
        rec = population.note(scene, label, body=actor.appearance)
        rec["ref"] = actor.ref
    else:
        got = npcs.choose(words, level) or {}
        actor = instantiate(str(got.get("id") or "guildhand"), scene=scene, name=label)
        rec = population.note(scene, label,
                              body=names_mod.appearance_for(world, scene.location_id, own=""))
        actor.appearance = names_mod.appearance_for(world, scene.location_id,
                                                    ref=actor.ref, own=rec["life"]["face"])
        scene.arrive(actor, zone=zone, source=f"start:{doc['id']}")
        rec["ref"] = actor.ref
    if look:
        actor.notes = (f"{label[:1].upper()}{label[1:]}, {look}." if row is None
                       else f"{label[:1].upper()}{label[1:]} ({look}).")
    scene.cast.append({"who": re.sub(r"^(?:the|a|an)\s+", "", label, flags=re.I),
                       "turn": 0, "ref": actor.ref})
    return actor


def _run(engine, doc: dict, raw: list[dict]):
    """Intents through the trusted provenance door: the start is the document behind
    every number, and says so on the record (`origin: start:<id>`)."""
    intents = engine.validate(raw, origin=f"start:{doc['id']}",
                              origin_name=str(doc.get("name") or doc["id"]).lower())
    return engine.run(intents)


def stage(engine, doc: dict, *, story_seed: int, bound: list[dict] | None = None) -> dict:
    """Put the start into the engine: the party at its place, the lead beside them, the
    incident in motion, the grants on the character. Returns the `Scene.start` record.

    Runs before the first word is written, with no model: what the opening then says is
    checked against what this left behind.
    """
    from . import places as places_mod
    from . import schemes as schemes_mod
    from .activeeffect import ActiveEffect

    scene, world = engine.scene, engine.world
    town = world.get(scene.location_id) if world is not None else None
    spot = spot_for(world, town, doc, rng_for(story_seed, "spot")) if town is not None else None
    if spot is not None:
        target = places_mod.find(engine.places(), spot.name)
        if target is not None and target.id != scene.at:
            engine.place_party(target.id)
    pc = scene.pc()
    slots: dict[str, str] = {}
    tells: list[str] = []

    lead = doc.get("lead") or {}
    row = _lead_person(engine, doc, bound or [], rng_for(story_seed, "lead"))
    label = " ".join(str(lead.get("label") or "the stranger").split())
    who = _stand_up(engine, doc, label, lead.get("words"), zone="near", row=row,
                    look=str(lead.get("look") or ""))
    slots["lead"] = who.ref

    for step in doc.get("incident") or []:
        verb, slot = step.get("do"), str(step.get("slot") or "")
        if verb == "bring":
            made = None
            for _ in range(count_of(step)):
                made = _stand_up(engine, doc, str(step.get("label")), step.get("words"),
                                 zone=str(step.get("zone") or "near"))
            if made is not None:
                slots[slot] = made.ref
        elif verb == "wound" and slots.get(slot) in scene.people:
            target = scene.people[slots[slot]]
            amount = wound_amount(target, str(step.get("to")))
            if amount > 0:
                res = _run(engine, doc, [{
                    "op": "damage", "because": f"the start: {doc['id']}",
                    "params": {"to": target.ref, "amount": amount,
                               "type": str(step.get("type") or "bludgeoning"),
                               "lethality": "lethal"}}])
                tells.extend(res.tells())
        elif verb == "fight":
            from . import npcs

            level = int(getattr(pc, "level", 1) or 1)
            got = npcs.choose([str(w) for w in step.get("words") or ()], level) or {}
            res = _run(engine, doc, [{
                "op": "spawn", "because": f"the start: {doc['id']}",
                "params": {"template": str(got.get("id") or "thug"),
                           "count": count_of(step), "name": str(step.get("label")),
                           "zone": str(step.get("zone") or "near")}}])
            refs = [a["ref"] for o in res.outcomes for e in (o.effects or [])
                    if e.get("kind") == "spawn" for a in e.get("actors") or []]
            if refs:
                slots[slot] = refs[0]
                fight = _run(engine, doc, [{
                    "op": "begin_encounter", "because": f"the start: {doc['id']}",
                    "params": {"sides": {"party": [pc.ref], slot: refs}}}])
                tells.extend(fight.tells())

    filled = {name: {"kind": "actor", "ref": ref,
                     "name": scene.people[ref].name if ref in scene.people else ""}
              for name, ref in slots.items()}
    source = f"start:{doc['id']}"
    if pc is not None and doc.get("tags"):
        pc.apply_effect(ActiveEffect(
            name=str(doc.get("name") or doc["id"]), kind="start", key=source, source=source,
            origin=source, duration="until-dismissed", tags=tuple(doc["tags"])))
    for g in doc.get("grants") or []:
        schemes_mod._grant(scene, filled, g, source)
    hand = dict(doc.get("hand_off") or {})
    if hand.get("on"):
        hand["ref"] = slots.get(str(hand["on"]).lstrip("$"), "")
    # The engine's damage tell ends in a full stop and its source clause starts with one
    # ("…damage.. from called to the cage"); tidied here, on the record only.
    tells = [re.sub(r"\.\.\s", ". ", " ".join(str(t).split())) for t in tells if t]
    record = {"id": doc["id"], "kind": str(doc.get("kind") or ""),
              "where": spot.name if spot is not None else "",
              "slots": slots, "hand_off": hand, "tells": tells}
    scene.start = record
    return record
