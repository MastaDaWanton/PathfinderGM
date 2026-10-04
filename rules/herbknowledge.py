"""What a character knows about each herb (docs/herbalism-revamp-plan.md §8).

A property is one of an ingredient's effect lines (`Ingredient.pairs`), keyed by its
position: "p0", "p1" ... The key is positional on purpose: the corpus stores effects in a
fixed order, and a key that is a slug of the text would break the moment an author
corrected a typo in it.

**One store, one owner.** `Actor.herb_known` maps an ingredient id to
`{"keys": [...], "how": {key: "tasted, day 14"}, ...}`. Since the blacksmithing revamp
(docs/blacksmithing-contracts.md §6) the same store holds what the smith knows of each
material, keyed by material id, and the machinery that reads and writes it lives in
`rules/knowledge.py`, which this module re-exports: every name below still works exactly
as it did, so the herb bench, the Journal and the narrator's brief are untouched and
cannot disagree with the forge about what is known. Keys that begin with "_" are
bookkeeping (`_seeded` records that the homeland and converted-herbalist seeds have run),
never an ingredient.

What stays here is what only herbs have: the herb lore and manuals files, tasting's
condition rule, the satchel and the herbarium rows, the homeland seed, and the brief.

**Four doors in, and each says how.** Tasting (the engine's `taste` op: real effects, one
benefit and one drawback revealed), study (a Knowledge or Profession check on the player's
die), a teacher or a library (coin and time, gated by attitude or by what the world writes
down), and a manual (hours of reading, mastery once). The prior art (docs/herbalism-
prior-art.md) is Skyrim's: eat it and learn the first effect, or read about it; the plan
adds the safer, slower routes because a nibble of hemlock here really paralyses.

**Severed tells.** The narrator is never told an unknown property (law 3). `brief_line`
is the only shape herb knowledge reaches a prompt in, and it prints known lines only.

**No model authors a number.** Every DC, price and time is a row in
content/rules/herb-lore.json; every effect is the ingredient's own spec.
"""
from __future__ import annotations

import functools
import re

from . import knowledge as _k
# The generic machinery, re-exported under the names this module always had (lane E of
# the blacksmithing revamp). Bound, not wrapped, wherever the signature is unchanged, so
# `herbknowledge.reveal is knowledge.reveal` and there is one copy of each rule.
from .knowledge import (  # noqa: F401 — re-exports are this module's public face
    BENEFIT,
    DRAWBACK,
    NEUTRAL,
    SEEDED,
    _HARM_TYPES,
    _entry,
    _ingredient,
    _key_index,
    _rested_since,
    _specs,
    _words_say,
    anatomy,
    classify,
    common_knowledge,
    danger_known,
    day_of,
    holds_manual,
    is_drawback,
    known_keys,
    lesson_order,
    manual_keys,
    meet,
    properties,
    property_keys,
    reveal,
    study,
    study_dc,
    study_order,
    study_waits,
    unknown_count,
    with_gates,
)
from .knowledge import reveal_picks as taste_picks  # noqa: F401 — the taste op's name


# --- the rule rows ------------------------------------------------------------------------
#
# Shipped content only, never a homebrew overlay, so an lru_cache is honest: nothing under
# CAMPAIGN_DIR can change what these files say mid-run (tests/test_three_laws.py's cache
# ratchet is about overlays, and these have none).

def _content(name: str) -> dict:
    return _k._content(name)


@functools.lru_cache(maxsize=1)
def lore() -> dict:
    """content/rules/herb-lore.json: the prices, times and DCs of learning."""
    return _k.lore(_k.HERBALIST)


def manuals() -> dict[str, dict]:
    """Every herbalism manual, by id (content/rules/herbal-manuals.json)."""
    return _k.manuals(_k.HERBALIST)


def manual_named(said: str) -> dict | None:
    """A herbalism manual by id or by name, as the browser or a shelf calls it."""
    return _k.manual_named(said, _k.HERBALIST)


# --- teachers and libraries: the herbalist's rows -----------------------------------------

def teaches(person, rec: dict | None = None) -> bool:
    """Whether this person knows herbs: their trade by the population record (`work`,
    an occupation id), or their own words — name, template, description."""
    return _k.teaches(person, rec, _k.HERBALIST)


def lesson_size(person) -> int:
    """How many properties this person will teach for one fee, by how they feel about the
    player — the confiding gate's shape (rules/confiding.py). 0 is a refusal."""
    return _k.lesson_size(person, _k.HERBALIST)


def is_library(place) -> bool:
    """A place that keeps records: the settlement table's library, a scriptorium, an
    archive, a temple's archive (rules/places.py names them; nothing here mints one)."""
    return _k.is_library(place, _k.HERBALIST)


# --- the satchel and the herbarium ----------------------------------------------------------

def carried(actor, ingredient_id: str) -> int:
    """Raw doses of this herb in the satchel."""
    return int((getattr(actor, "inventory", None) or {}).get(str(ingredient_id), 0) or 0)


def stock_of(actor, ingredient_id: str) -> str:
    """A shelf entry that is this herb and nothing else (a prepared dose: dried, ground),
    or "". A product made of several things is not a dose of any one of them."""
    from .crafting import base_ingredient_id

    for sid, s in (getattr(actor, "stock", None) or {}).items():
        refs = [base_ingredient_id(r) for r in (getattr(s, "from_ingredients", None) or [])]
        if refs and set(refs) == {str(ingredient_id)} and int(getattr(s, "count", 0)) > 0:
            return sid
    return ""


def met(actor) -> list[str]:
    """Every herb the character has come across: what they know of, what they carry, and
    what their shelf holds as a single herb."""
    from . import ingredients as ing_mod

    everything = ing_mod.all_ingredients()
    ids = [k for k in (getattr(actor, "herb_known", None) or {}) if not k.startswith("_")]
    ids += [k for k, n in (getattr(actor, "inventory", None) or {}).items() if n]
    out = []
    for iid in dict.fromkeys(ids):
        if iid in everything:
            out.append(iid)
    return out


def _part(ingredient) -> str:
    """The plant or body part (lane A's field), with the contract's default by kind."""
    part = str(getattr(ingredient, "part", "") or "")
    if part:
        return part
    kind = str(getattr(ingredient, "kind", "") or "")
    return {"monster part": "organ", "fungus": "fungus"}.get(kind, "leaf")


def entry(actor, ingredient) -> dict:
    """One herbarium row (docs/herbalism-contracts.md §4.1)."""
    keys = property_keys(ingredient)
    return {"id": ingredient.id, "name": ingredient.name, "kind": ingredient.kind,
            "part": _part(ingredient), "tier": ingredient.tier,
            "known": len(known_keys(actor, ingredient)), "total": len(keys),
            "biomes": list(ingredient.biomes or []), "carried": carried(actor, ingredient.id)}


def herbarium(actor) -> list[dict]:
    """Every herb met, by kind then name — the order the plan's Journal groups them in."""
    from . import ingredients as ing_mod

    everything = ing_mod.all_ingredients()
    rows = [entry(actor, everything[i]) for i in met(actor)]
    return sorted(rows, key=lambda r: (str(r["kind"]), str(r["name"]).lower()))


def card(actor, ingredient, *, clock: int = 0) -> dict:
    """The herb's card, the parts this module can answer alone (§4.2). The teachers and
    the library are the scene's, and the view adds them."""
    unknown = unknown_count(actor, ingredient)
    doses = carried(actor, ingredient.id) + (1 if stock_of(actor, ingredient.id) else 0)
    able = bool(getattr(actor, "can_act", lambda: True)())
    return {"id": ingredient.id, "name": ingredient.name, "kind": ingredient.kind,
            "part": _part(ingredient), "tier": ingredient.tier,
            "biomes": list(ingredient.biomes or []),
            "danger_known": danger_known(actor, ingredient),
            "properties": properties(actor, ingredient),
            "can_study": bool(doses and unknown and able
                              and not study_waits(actor, ingredient.id)),
            "study_minutes": int(lore()["study"]["minutes"]),
            "study_dc": study_dc(ingredient),
            "study_waits": bool(study_waits(actor, ingredient.id)),
            "can_taste": bool(doses and able)}


# --- tasting -----------------------------------------------------------------------------

def taste_condition(spec: dict) -> dict:
    """A raw herb's condition with the rule row's default length when it states none.

    The corpus writes "Causes paralyzed" with no duration on most of its condition rows,
    and an unbounded paralysis is a campaign the character never plays again; death and
    dying keep their own rules (content/rules/herb-lore.json, `taste`)."""
    spec = dict(spec)
    if str(spec.get("type")) != "apply_condition":
        return spec
    rules = lore()["taste"]
    cond = str(spec.get("target") or spec.get("condition") or "").lower()
    if cond in set(rules.get("condition_no_default") or ()):
        return spec
    duration = spec.get("duration")
    if not (isinstance(duration, dict) and duration.get("amount")):
        spec["duration"] = {"amount": int(rules["condition_minutes"]), "unit": "minute"}
    return spec


# --- study -------------------------------------------------------------------------------

def study_skill(actor, dc: int) -> tuple[str, list]:
    """The better of Knowledge (nature) and Profession, as (skill, modifiers), or ("", [])
    when neither can be attempted. Untrained, Knowledge answers nothing above DC 10 (CRB
    p.99), and then only on the Intelligence modifier."""
    from .dice import Modifier
    from .sheet import IllegalSheet

    rules = lore()["study"]
    best: tuple[str, list] | None = None
    for skill in rules["skills"]:
        try:
            mods = actor.skill_modifiers(skill)
        except (IllegalSheet, KeyError):
            continue
        if best is None or sum(m.value for m in mods) > sum(m.value for m in best[1]):
            best = (skill, list(mods))
    if best is not None:
        return best
    if dc <= int(rules["untrained_dc_cap"]):
        am = actor.ability_mod("int")
        return "knowledge (nature)", ([Modifier(am, "Int (untrained)")] if am else [])
    return "", []


# --- what a new herbalist already knows ----------------------------------------------------

def is_herbalist(actor) -> bool:
    return "herbalist" in (getattr(actor, "world_classes", None) or {})


def _people_entity(actor, world):
    """The world's own people this character's race is (`origin: world:<id>`), or None."""
    if world is None:
        return None
    from . import races as races_mod

    try:
        # The actor's own read when it has one: a world's drafted race is in no registry.
        reader = getattr(actor, "_race_doc", None)
        doc = reader() if callable(reader) else races_mod.get(str(getattr(actor, "race", "") or ""))
    except Exception:  # noqa: BLE001 — a race with no document has no homeland to read
        return None
    origin = str((doc or {}).get("origin") or "")
    if not origin.startswith("world:"):
        return None
    try:
        return world.get(origin.split(":", 1)[1])
    except Exception:  # noqa: BLE001
        return None


def homeland_biomes(actor, *, world=None, scene=None) -> list[str]:
    """The biomes of the land this character grew up in.

    Read, in order, from: the world's own people the character's race is — its
    `Homeland` fact ("The Pangrellan grasslands of southern Kaelinora" reads grassland),
    then the land around that people's entity; then the settlement the campaign began in
    (the first place stood in), by the land around it; then the ground underfoot. A
    settlement's own "urban" is never a homeland biome: what grows is in the land around.
    """
    from . import biomes as biomes_mod
    from . import places as places_mod

    never = set(lore()["homeland"]["never"])

    def keep(found) -> list[str]:
        return [b for b in dict.fromkeys(found or ()) if b and b not in never]

    people = _people_entity(actor, world)
    if people is not None:
        said = keep(biomes_mod.detect(str((getattr(people, "facts", None) or {})
                                          .get("Homeland") or "")))
        if said:
            return said
        around = keep(biomes_mod.from_world(world, people))
        if around:
            return around
    if scene is not None:
        been = []
        try:
            been = list(scene.places_been())
        except Exception:  # noqa: BLE001 — an older scene with no record of where it stood
            been = []
        first = been[0] if been else str(getattr(scene, "at", "") or "")
        loc_id = places_mod.location_of(first) if first else ""
        loc_id = loc_id or str(getattr(scene, "location_id", "") or "")
        if world is not None and loc_id:
            try:
                found = world.get(loc_id)
            except Exception:  # noqa: BLE001
                found = None
            if found is not None:
                around = keep(biomes_mod.from_world(world, found))
                if around:
                    return around
        ground = keep([str(getattr(scene, "biome", "") or "")])
        if ground:
            return ground
    return []


def seed_homeland(actor, biomes) -> list[str]:
    """Teach a new herbalist the common herbs of home, every property, how = "homeland"
    (the owner's ruling Q4: "starting with nothing would make level 1 a lottery of
    poison"). Idempotent: run once per character, recorded in `_seeded`. Returns the
    ingredient ids seeded this call."""
    from . import ingredients as ing_mod

    mark = actor.herb_known.setdefault(SEEDED, {})
    if mark.get("homeland") is not None:
        return []
    rules = lore()["homeland"]
    tiers, kinds = set(rules["tiers"]), set(rules["kinds"])
    home = [b for b in biomes or () if b]
    mark["homeland"] = home
    seeded = []
    for ing in ing_mod.all_ingredients().values():
        if ing.tier not in tiers or ing.kind not in kinds or not ing.forageable:
            continue
        if not set(ing.biomes or ()) & set(home):
            continue
        if reveal(actor, ing.id, property_keys(ing), "homeland"):
            seeded.append(ing.id)
    return seeded


def herbs_in(recipe_id: str) -> list[str]:
    """The ingredient ids a crafted recipe's name mentions ("woundwort styptic",
    "distilled comfrey tea"). Best effort, whole words, longest names first so "juniper
    berry" is not read as "juniper"."""
    from . import ingredients as ing_mod

    said = f" {' '.join(str(recipe_id or '').lower().replace('-', ' ').split())} "
    found: list[str] = []
    for ing in sorted(ing_mod.all_ingredients().values(), key=lambda i: -len(i.name)):
        name = " ".join(ing.name.lower().replace("-", " ").split())
        if name and re.search(rf"(?<![a-z]){re.escape(name)}(?![a-z])", said):
            found.append(ing.id)
            said = said.replace(name, " ")
    return found


def seed_converted(actor) -> list[str]:
    """A herbalist from before the revamp knows every property of every herb in what
    they have crafted (plan §14 item 4): they used them. Once, recorded in `_seeded`."""
    from . import ingredients as ing_mod

    mark = actor.herb_known.setdefault(SEEDED, {})
    if mark.get("converted"):
        return []
    mark["converted"] = True
    progress = (getattr(actor, "world_classes", None) or {}).get("herbalist")
    seeded = []
    for recipe in (getattr(progress, "crafted", None) or {}):
        for iid in herbs_in(recipe):
            ing = ing_mod.all_ingredients().get(iid)
            if ing is not None and reveal(actor, iid, property_keys(ing), "crafted with it"):
                seeded.append(iid)
    return seeded


def ensure_seeded(actor, *, world=None, scene=None) -> dict:
    """The one hook: seed a herbalist's homeland and converted knowledge, once each.

    Called when the herbarium, a herb card or the bench state is first read, and before
    a taste picks what it teaches. Does nothing for a character without the herbalist
    track, and nothing the second time: the marks in `_seeded` say it ran."""
    if actor is None or not is_herbalist(actor):
        return {}
    out = {}
    mark = (actor.herb_known or {}).get(SEEDED) or {}
    if mark.get("homeland") is None:
        out["homeland"] = seed_homeland(
            actor, homeland_biomes(actor, world=world, scene=scene))
    if not mark.get("converted"):
        out["converted"] = seed_converted(actor)
    return out


# --- the narrator's view ------------------------------------------------------------------

def brief_line(actor) -> str:
    """The herbs the character carries, with what they KNOW of each and nothing else.

    The only shape herb knowledge reaches a prompt in (law 3: an unknown property never
    reaches the narrator). Before the revamp the brief named no raw herb at all; it names
    them now so "I hand her the woundwort" has a thing to stand on, and the gate is that
    each herb carries only its known lines and a count of what is not known.
    """
    from . import ingredients as ing_mod

    everything = ing_mod.all_ingredients()
    bits = []
    for iid, n in sorted((getattr(actor, "inventory", None) or {}).items()):
        ing = everything.get(iid)
        if ing is None or not n:
            continue
        known = set(known_keys(actor, ing))
        lines = [line for key, (line, _spec) in zip(property_keys(ing), ing.pairs)
                 if key in known]
        hidden = len(property_keys(ing)) - len(known)
        said = "; ".join(lines) if lines else "nothing known of what it does"
        if lines and hidden:
            said += f"; {hidden} more not known"
        bits.append(f"{ing.name}" + (f" ×{n}" if n != 1 else "") + f" ({said})")
    return ", ".join(bits)
