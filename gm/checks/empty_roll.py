"""Harm with no victim: a damage roll that reached nobody, narrated as a hit (item 22.4).

Measured on the Bobby playtest, 2026-09-28, turn 13. Burning Hands from the Spells tab
resolved with `targets: []` and a bare "1d4 — 1" — no damage effect on anybody, the man
in the jerkin still at 4 of 4. The page burned him anyway: "the heat licks across his
face", "the man is thrown backward", "his face blackened by soot, his hands clutching his
scorched arms", "a raspy growl of pain". `contradicts_state` run on that beat found
nothing: `_name_stems` dropped "man", the wound sentences said "he" and "his", and the
wound words held no burn and no impact. FIREBALL (Zhu et al. 2023) records the same
failure in real D&D play — damage read as a kill "regardless of the target's true
remaining health"; this is it with no target at all.

Condition: an outcome that rolled damage and landed it on nobody — a cast whose targets
are empty, or E's `no_victim`, with no `damage` or `condition` effect on anybody but the
caster. Detect, for each person here the turn did not harm: the sentences about them
(`_people.about`, pronoun continuation included) that hold a harm word of the damage's
family — fire, impact, or a wound. Repair: one rewrite per sentence, the fact named
("the spell reached nobody; he is untouched"). Backstop: the sentences are cut and the
engine's plain fact stands in their place.

**And the victim the page invents** (G2, measured live 2026-09-28, gemma-4-12B,
Aurvantis, the cast-area script). The scene held Ysolde, Kaelith Dagmar and the
innkeeper; "I cast burning hands at the man standing nearest me" resolved at a
placeholder ref and reached nobody ("The flames reach nobody.", `no_victim`). The page
then invented a man — "Dagan Havenstone", with Kaelith's own face line from the brief
put under the new name — and burned him: "He screams, his skin blistering as he is
thrown backward into the structure". The truth pass found nothing and repaired nothing,
because the reader above only asks about the people on the actor list, and Dagan was
not on it. So when the roll reached nobody, a harm sentence is also flagged when it is
about a person who is not here at all: a capitalised name nobody here, no place and
nothing in the world's own words owns (`narration.invented_names`), or a description
of a person the attribution could not book on anyone present — carried on by its
pronouns exactly as a person present is (`_people.linked`). The caster is never one:
"you" is not a phantom, and an NPC caster is on the actor list. The fact the repair
names is the engine's: the spell reached nobody, and there is nobody there it hit.
"""
from __future__ import annotations

import re

from gm.narration import Finding

from ._page import cut, effects, field
from ._people import about

ORDER = 40
KINDS = frozenset({"harm-without-a-victim"})
DOORS = frozenset({"turn", "outcome", "plan"})

# Fire ON somebody, not fire as such: "a searing cone surging toward him" is the spell
# being cast, which happened; "his scorched arms" is a wound, which did not.
_GROUND = (r"(?!,?\s+(?:\w+\s+)?(?:earth|ground|soil|grass|brush|ferns?|air|path|floor|"
           r"scar|stones?|wood|trees?|leaves|mulch|moss|bark|canopy))")
_FIRE = (r"burn(?:s|ed|t)?\b(?!\s+(?:bright|low|steady))|scorch\w*\b" + _GROUND + r"|"
         r"sear(?:s|ed)\b|singe\w*|blacken\w*\b" + _GROUND + r"|soot\b|blister\w*|"
         r"char(?:s|red)\b" + _GROUND + r"|"
         r"(?:heat|flames?|fire)\s+(?:licks?|washes?|rolls?|engulfs?|sweeps?)\s+(?:over|"
         r"across|into)\s+(?:his|her|their|its|the)|engulf\w*|catch(?:es)?\s+fire|"
         r"on\s+fire|in\s+flames")
# The magic missile beat of G2 (2026-09-28) hit its invented man with "slamming into his
# chest", "knocking the air from his lungs" and "throwing him back" — none of which the
# first cut's "slams into" and "thrown back" read.
_IMPACT = (r"thrown\s+(?:back|backward|backwards|clear|off)|knocked\s+(?:back|down|flat)|"
           r"thr(?:ow|ows|owing|ew)\s+(?:him|her|them)\s+(?:back|backward|backwards|clear)|"
           r"knock(?:s|ed|ing)?\s+the\s+(?:air|wind|breath)\s+(?:from|out)|"
           r"hits?\s+the\s+(?:ground|floor|dirt)|slams?\s+into|"
           # Into a body, not "slamming into the wall beside him", which is a miss.
           r"slam(?:med|ming)\s+into\s+(?:his|her|their|him|them)\b|"
           r"sent\s+(?:flying|sprawling)|sprawl\w*|staggers?\s+back")
_WOUND = (r"wound\w*|bleed\w*|bloodied|blood\s+(?:runs|pours|wells)|injur\w*|"
          r"(?:cry|cries|gasps?|growls?|groans?|howls?|screams?)\s+(?:of|in|with)\s+pain|"
          r"clutch\w*\s+(?:his|her|their)\s+\w*\s*(?:arm|arms|face|side|chest|hand|hands|"
          r"leg|burns?|wound)|writh\w*|in\s+agony")
HARM = re.compile(rf"\b(?:{_FIRE}|{_IMPACT}|{_WOUND})", re.I)


def _no_victim(o) -> bool:
    """A damage roll that landed on nobody."""
    if field(o, "status") == "refused":
        return False
    effs = effects(o)
    caster = {str(field(o, "actor") or "")}
    for e in effs:
        if e.get("kind") == "cast":
            caster.add(str(e.get("ref") or ""))
    if any(e.get("kind") in ("damage", "condition", "ability_damage")
           and str(e.get("ref") or "") not in caster for e in effs):
        return False
    if any(e.get("no_victim") or e.get("reached_nobody") for e in effs):
        return True
    rolled = any("damage" in str(r.get("label", "") if isinstance(r, dict)
                                 else getattr(r, "label", "")).lower()
                 for r in (field(o, "rolls") or []))
    cast = [e for e in effs if e.get("kind") == "cast"]
    return rolled and bool(cast) and all(not (e.get("targets") or e.get("caught"))
                                         for e in cast)


def _unharmed(ctx) -> list[str]:
    harmed = {str(e.get("ref") or "") for o in ctx.outcomes for e in effects(o)
              if e.get("kind") in ("damage", "condition", "ability_damage")}
    return [r for r, a in ctx.scene.actors.items()
            if not getattr(a, "is_pc", False) and r not in harmed]


def _spell(ctx) -> str:
    for o in ctx.outcomes:
        if _no_victim(o):
            for e in effects(o):
                if e.get("kind") == "cast" and e.get("name"):
                    return str(e["name"])
    return "the spell"


def _flagged(ctx) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for ref in _unharmed(ctx):
        hits = [w for w, n in about(ctx, ref) if HARM.search(n)]
        if hits:
            out[ref] = hits
    return out


# --- the victim who is not here ---------------------------------------------------------

_POSSESSIVE = re.compile(r"['’]s$")
_NAME_RUN = re.compile(r"[A-Z][A-Za-z'’-]+(?:\s+[A-Z][A-Za-z'’-]+)*")


def _known_words(ctx) -> set[str]:
    """Every name the beat may use without naming a person who is not here: the people
    present (shown and true names, their race and heritage), the places, the spells cast,
    the world's entities and the words the world's own prose uses (the same vocabulary
    the invented-name review trusts, `GMAgent._world_vocabulary`, whose measured false
    positives — Council, Valtorian, Elders — were all of them the world's own words)."""
    known: set[str] = set()
    for a in (getattr(ctx.scene, "actors", {}) or {}).values():
        for held in (a.name, getattr(a, "true_name", ""), getattr(a, "race", ""),
                     getattr(a, "heritage", "")):
            if held:
                known.add(str(held))
    try:
        known |= {str(p.name) for p in ctx.engine.places() if getattr(p, "name", "")}
    except Exception:  # noqa: BLE001 — no places answer: the people and world still count
        pass
    if ctx.location is not None and getattr(ctx.location, "name", ""):
        known.add(str(ctx.location.name))
    for o in ctx.outcomes:
        for e in effects(o):
            if e.get("kind") == "cast" and e.get("name"):
                known.add(str(e["name"]))
    world = ctx.world
    if world is not None:
        try:
            known |= {str(e.name) for e in world.entities.values() if e.name}
            known |= {str(f["name"]) for f in world.factions}
            known.add(str(world.name or ""))
            from types import SimpleNamespace

            from gm.agent import GMAgent

            # The cached walk over the world's prose; it reads nothing but `world`.
            known |= GMAgent._world_vocabulary(SimpleNamespace(world=world))
        except Exception:  # noqa: BLE001 — a world that will not read: names stay strict
            pass
    return {k for k in known if k}


def _phantom_tokens(ctx, narration: list[str]) -> set[str]:
    """The name words the beat writes that nobody here, no place and nothing in the
    world owns, lower-case, possessive off: "catches Dagan's sleeve" gives "dagan".
    `invented_names` skips a sentence's first word (a sentence start proves nothing), so
    "Dagan Havenstone is a Human" gives "havenstone" — and "dagan" from wherever the
    beat writes him mid-sentence."""
    from gm.narration import invented_names

    known = _known_words(ctx)
    pc = ctx.scene.pc() if hasattr(ctx.scene, "pc") else None
    if pc is not None:
        known.add(str(pc.name))
    return {_POSSESSIVE.sub("", t).lower() for t in invented_names(" ".join(narration), known)}


def _unbooked(ctx, written: str, narration: str) -> list[str]:
    """Descriptions of a person in this sentence that nobody present answers to: the
    attribution's mentions it could not book ("nobody", or no answer), else the code's
    own find where the attribution did not read the sentence. A description whose words
    are a present person's ("the innkeeper") is theirs, labelled or not."""
    from gm import mentions as mentions_mod

    from ._people import names_person

    att = getattr(ctx, "attribution", None)
    if att is not None and att.refs_in(written) is not None:
        found = [m for m in att._in(written) if m.kind == "description" and m.ref is None]
    else:
        found = [m for m in mentions_mod.find(narration, mentions_mod.people(ctx.scene))
                 if m.kind == "description"]
    names = [str(a.name or "") for a in ctx.scene.actors.values()
             if not getattr(a, "is_pc", False)]
    return [m.phrase for m in found
            if not any(names_person(m.phrase, n) for n in names if n)]


def _phantoms(ctx, taken=()) -> tuple[list[str], str]:
    """(the sentences that harm somebody who is not here, the words the page calls them)
    — harm sentences only, each anchored on a phantom name or an unbooked description or
    carried on from one by a pronoun, and never one already flagged for a person present
    (`taken`) or one naming somebody the turn really did harm."""
    from ._page import page_sentences
    from ._people import _ANY_THIRD, _named_by, linked, names_person

    pairs = page_sentences(ctx.text)
    if not pairs:
        return [], ""
    narr = [n for _, n in pairs]
    tokens = _phantom_tokens(ctx, narr)
    token_re = (re.compile(r"\b(?:" + "|".join(re.escape(t) for t in sorted(tokens))
                           + r")(?:['’]s)?\b", re.I) if tokens else None)
    att = getattr(ctx, "attribution", None)
    others = [(r, str(a.name or "")) for r, a in ctx.scene.actors.items()
              if not getattr(a, "is_pc", False)]
    harmed = {str(e.get("ref") or "") for o in ctx.outcomes for e in effects(o)
              if e.get("kind") in ("damage", "condition", "ability_damage")}
    who: list[str] = []

    def anchor(i: int) -> bool:
        written, n = pairs[i]
        hit = False
        if token_re is not None:
            m = token_re.search(n)
            if m:
                hit = True
                run = next((r.group(0) for r in _NAME_RUN.finditer(n)
                            if r.start() <= m.start() < r.end()), m.group(0))
                who.append(_POSSESSIVE.sub("", run))
        described = _unbooked(ctx, written, n)
        if described:
            hit = True
            who.append(described[0])
        return hit

    def names(i: int, refs) -> bool:
        written, n = pairs[i]
        for r, name in others:
            if r not in refs:
                continue
            said = _named_by(att, written, r, name)
            if said if said is not None else names_person(n, name):
                return True
        return False

    # `linked` reads the pronouns off the sentence text, so it is handed the narration;
    # a sentence written twice answers the same both times, so the first index serves.
    at = {}
    for i, n in enumerate(narr):
        at.setdefault(n, i)
    anchored = {i for i in range(len(pairs)) if anchor(i)}
    every = {r for r, _ in others}
    idx = linked(narr, lambda n: at[n] in anchored, lambda n: names(at[n], every),
                 _ANY_THIRD)
    taken = set(taken)
    out = [pairs[i][0] for i in idx
           if HARM.search(pairs[i][1]) and pairs[i][0] not in taken
           and not names(i, harmed)]
    return out, (who[0] if who else "somebody")


def _plain_line(ctx, spell: str) -> str:
    """The engine's own sentence for a cast that reached nobody, from its tell."""
    from gm.narration import _sentences

    for o in ctx.outcomes:
        if _no_victim(o):
            for s in _sentences(str(field(o, "tell") or "")):
                if "nobody" in s.lower():
                    return s.strip()
    return f"{spell[:1].upper()}{spell[1:]} reaches nobody."


def find(ctx) -> list:
    if not any(_no_victim(o) for o in ctx.outcomes):
        return []
    found = []
    spell = _spell(ctx)
    flagged = _flagged(ctx)
    for ref, hits in flagged.items():
        name = called(str(ctx.scene.actors[ref].name))
        found.append(Finding(
            "harm-without-a-victim",
            f"{spell} reached nobody, and the prose harms {name}: {hits[0][:90]!r}",
            f"{spell} reached nobody: nothing was caught in it, and {name} is untouched "
            f"— not burned, not thrown, not hurt. Rewrite the sentence so the {spell} "
            f"misses them or lands on nothing, and {name} is exactly as they were.",
            weight=3, sentences=tuple(hits)))
    ghosts, who = _phantoms(ctx, taken=[s for hits in flagged.values() for s in hits])
    if ghosts:
        found.append(Finding(
            "harm-without-a-victim",
            f"{spell} reached nobody, and the prose harms {who}, who is nobody in this "
            f"scene: {ghosts[0][:90]!r}",
            f"{spell} reached nobody: there is nobody there it hit. {who} is not one of "
            f"the people here, and nobody was burned, thrown or hurt by it. Rewrite the "
            f"sentence so the {spell} lands on nothing and harms no one, and bring "
            f"nobody new into the scene.",
            weight=3, sentences=tuple(ghosts)))
    return found


def backstop(ctx, text: str, findings) -> tuple[str, list[str]]:
    """Cut what still harms somebody the roll never reached, and say who it reached."""
    from dataclasses import replace

    now = replace(ctx, text=text)
    flagged = _flagged(now)
    gone = [s for hits in flagged.values() for s in hits]
    ghosts, _ = _phantoms(now, taken=gone)
    if not gone and not ghosts:
        return text, []
    kept = cut(text, gone + ghosts)
    spell = _spell(ctx)
    if flagged:
        names = [called(str(ctx.scene.actors[r].name)) for r in flagged]
        line = (f"{spell[:1].upper()}{spell[1:]} catches nobody; {' and '.join(names)} "
                f"{'is' if len(names) == 1 else 'are'} untouched.")
    else:
        # Nobody present was harmed on the page, so nobody present is named: the engine's
        # plain line, "The flames reach nobody.", is the whole of the fact.
        line = _plain_line(ctx, spell)
    from gm.narration import _append_before_hand_back

    notes = []
    if gone:
        notes.append(f"harm without a victim: cut {len(gone)} sentence(s) and said nobody "
                     f"was caught")
    if ghosts:
        notes.append(f"harm without a victim: cut {len(ghosts)} sentence(s) harming "
                     f"somebody who is not here")
    return _append_before_hand_back(kept, line), notes


def called(name: str) -> str:
    """A descriptor as a sentence uses it: "man in a stained leather jerkin" → "the man
    in a stained leather jerkin"; a proper name as it is."""
    name = " ".join(str(name or "").split())
    if name[:1].islower() and not name.lower().startswith(("the ", "a ", "an ")):
        return f"the {name}"
    return name
