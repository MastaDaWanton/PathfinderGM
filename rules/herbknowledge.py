"""What a character knows about each herb (docs/herbalism-revamp-plan.md §8).

A property is one of an ingredient's effect lines (`Ingredient.pairs`), keyed by its
position: "p0", "p1" ... The key is positional on purpose: the corpus stores effects in a
fixed order, and a key that is a slug of the text would break the moment an author
corrected a typo in it.

**One store, one owner.** `Actor.herb_known` maps an ingredient id to
`{"keys": [...], "how": {key: "tasted, day 14"}, ...}` and nothing but this module reads or
writes it, so the bench card, the Journal and the narrator's brief cannot disagree about
what is known. Keys that begin with "_" are this module's bookkeeping (`_seeded` records
that the homeland and converted-herbalist seeds have run), never an ingredient.

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
import json
import re
from pathlib import Path

# The bookkeeping slot inside `Actor.herb_known`. Underscored so no ingredient id (the
# corpus slugs are lowercase letters, digits and hyphens) can ever collide with it.
SEEDED = "_seeded"

BENEFIT, DRAWBACK, NEUTRAL = "benefit", "drawback", "neutral"

# Effect types that hurt whoever takes them on top of `consumables.hurts`, which was
# written for a jar's Drawbacks panel and predates these three in the catalogue.
_HARM_TYPES = frozenset({"vulnerability", "ability_drain", "bleed"})


# --- the rule rows ------------------------------------------------------------------------
#
# Shipped content only, never a homebrew overlay, so an lru_cache is honest: nothing under
# CAMPAIGN_DIR can change what these files say mid-run (tests/test_three_laws.py's cache
# ratchet is about overlays, and these have none).

def _content(name: str) -> dict:
    from django.conf import settings

    path = Path(settings.BASE_DIR) / "content" / "rules" / name
    return json.loads(path.read_text(encoding="utf-8"))


@functools.lru_cache(maxsize=1)
def lore() -> dict:
    """content/rules/herb-lore.json: the prices, times and DCs of learning."""
    return _content("herb-lore.json")


@functools.lru_cache(maxsize=1)
def _manual_rows() -> tuple:
    return tuple(_content("herbal-manuals.json").get("manuals") or ())


def manuals() -> dict[str, dict]:
    """Every herbalism manual, by id (content/rules/herbal-manuals.json)."""
    return {str(m["id"]): dict(m) for m in _manual_rows() if m.get("id")}


# --- properties -----------------------------------------------------------------------------

def property_keys(ingredient) -> list[str]:
    """Every property this ingredient has, as keys."""
    return [f"p{i}" for i in range(len(getattr(ingredient, "pairs", []) or []))]


def _key_index(key: str) -> int:
    return int(key[1:]) if str(key)[1:].isdigit() else 0


def _ingredient(ingredient_or_id):
    if isinstance(ingredient_or_id, str):
        from . import ingredients as ing_mod

        try:
            return ing_mod.get(ingredient_or_id)
        except KeyError:
            return None
    return ingredient_or_id


def classify(spec: dict) -> str:
    """Whether one property is good for the taker, bad for them, or neither.

    Read off the structured spec, never the words: a penalty (a negative modifier), a
    condition caused, damage or ability damage to the taker is a drawback; healing, a
    bonus, a resistance or a condition ended is a benefit. A bare save gate is NEUTRAL:
    measured on the corpus, 38 of the 161 ingredients carry a "DC n" that gates nothing
    (the entry's crafting DC restated, swept up by the extractor), and the rest gate a
    poison's body, which is the drawback. `consumables.hurts` already says this for the
    jar's Drawbacks panel, so it is asked rather than copied.
    """
    from . import consumables

    kind = str((spec or {}).get("type", ""))
    if kind == "save_gate":
        return DRAWBACK if consumables.hurts(spec) else NEUTRAL
    if kind in _HARM_TYPES or consumables.hurts(spec):
        return DRAWBACK
    return BENEFIT


def is_drawback(spec: dict) -> bool:
    """The question the card's `drawback` field answers."""
    return classify(spec) == DRAWBACK


def _specs(ingredient) -> list[dict]:
    """The ingredient's specs, one per key, as the SAME dict objects each time asked
    within a call — `consumables.poisons` groups by identity."""
    return [spec for _, spec in (getattr(ingredient, "pairs", None) or [])]


def anatomy(ingredient) -> dict:
    """Each key's class, and which bare gate guards which poison body.

    `gate_of` maps a body key to the key of the save that gates it ("Fortitude DC 15"
    gates "Causes paralyzed"). A gate is revealed with its body, because 1e writes a
    poison as one thing — a save, and what happens when you fail it (`consumables.Poison`).
    """
    from . import consumables

    specs = _specs(ingredient)
    keys = property_keys(ingredient)
    index = {id(s): k for s, k in zip(specs, keys)}
    kinds = {k: classify(s) for s, k in zip(specs, keys)}
    gate_of: dict[str, str] = {}
    name = str(getattr(ingredient, "name", "") or "")
    for poison in consumables.poisons(specs, source=name):
        gate = index.get(id(poison.gate)) if poison.gate is not None else None
        for body in poison.effects:
            k = index.get(id(body))
            if k and gate and gate != k:
                gate_of[k] = gate
    return {"keys": keys, "kinds": kinds, "gate_of": gate_of, "specs": dict(zip(keys, specs))}


# --- what is known --------------------------------------------------------------------------

def _entry(actor, ingredient_id: str) -> dict | None:
    got = (getattr(actor, "herb_known", None) or {}).get(str(ingredient_id))
    return got if isinstance(got, dict) else None


def known_keys(actor, ingredient) -> list[str]:
    """The keys this actor knows, in key order. Only keys the ingredient still has: a
    corpus correction that shortens an effect list must not leave a phantom "known"."""
    entry = _entry(actor, getattr(ingredient, "id", ""))
    if entry is None:
        return []
    have = set(entry.get("keys") or ())
    return [k for k in property_keys(ingredient) if k in have]


def unknown_count(actor, ingredient) -> int:
    """How many of this ingredient's properties the actor does not yet know."""
    known = set(known_keys(actor, ingredient))
    return sum(1 for k in property_keys(ingredient) if k not in known)


def reveal(actor, ingredient_id: str, keys, how: str) -> list[str]:
    """Record that `keys` are now known, and how. Returns the keys that were NEW, so the
    caller can say "New: ..." only for real discoveries and pay mastery for firsts."""
    entry = actor.herb_known.setdefault(str(ingredient_id), {"keys": [], "how": {}})
    entry.setdefault("keys", [])
    entry.setdefault("how", {})
    have = set(entry.get("keys") or [])
    new = [k for k in dict.fromkeys(keys) if k not in have]
    if new:
        entry["keys"] = sorted(have | set(new), key=_key_index)
        for k in new:
            entry["how"][k] = str(how)
    return new


def meet(actor, ingredient_id: str) -> None:
    """Note that the character has come across this herb, knowing nothing yet, so the
    herbarium lists it. A herb met is a collection entry even before a property is."""
    actor.herb_known.setdefault(str(ingredient_id), {"keys": [], "how": {}})


def day_of(clock_minutes: int) -> int:
    """Day 1 is the first day, the way the Journal's history counts (play/history.py)."""
    return int(clock_minutes or 0) // (24 * 60) + 1


def properties(actor, ingredient) -> list[dict]:
    """The card's property rows (docs/herbalism-contracts.md §4.2): a known one says what
    it does and how it was learned; an unknown one says nothing at all."""
    entry = _entry(actor, ingredient.id) or {}
    how = entry.get("how") or {}
    known = set(known_keys(actor, ingredient))
    out = []
    for key, (line, spec) in zip(property_keys(ingredient), ingredient.pairs):
        if key in known:
            out.append({"key": key, "known": True, "text": line,
                        "drawback": is_drawback(spec), "how": str(how.get(key) or "")})
        else:
            out.append({"key": key, "known": False, "text": None, "drawback": None,
                        "how": None})
    return out


def danger_known(actor, ingredient) -> str:
    """What the character knows can hurt them, in one line, or "" — the card's warning
    ("You know this is dangerous: ..."). Read from known drawbacks every time, so every
    route that reveals one sets it, not only study."""
    known = set(known_keys(actor, ingredient))
    lines = [line for key, (line, spec) in zip(property_keys(ingredient), ingredient.pairs)
             if key in known and is_drawback(spec)]
    return "; ".join(lines)


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

def taste_picks(actor, ingredient, landed=()) -> list[str]:
    """Which keys a taste reveals: at most one benefit and at most one drawback, each the
    first UNKNOWN one, preferring what actually landed on the taster (if hemlock paralysed
    you, the paralysis is what you learned). A drawback brings its gate with it. A herb
    whose benefits are all known teaches nothing new on that side: a second taste is for
    the side you have not learned.

    "Benefit" here is anything not a drawback, so a herb whose only line is a bare DC
    still teaches that line on a first taste; a gate that guards a poison is never the
    benefit — it is half of the drawback.
    """
    a = anatomy(ingredient)
    known = set(known_keys(actor, ingredient))
    landed = set(landed)
    gates = set(a["gate_of"].values())

    def best(cands: list[str]) -> str:
        # Landed first, and among what landed a condition first: being paralysed is
        # the thing a taster cannot fail to notice, more than a point of Constitution.
        fresh = [k for k in cands if k not in known]
        fresh.sort(key=lambda k: (k not in landed,
                                  str(a["specs"][k].get("type")) != "apply_condition",
                                  _key_index(k)))
        return fresh[0] if fresh else ""

    good = best([k for k in a["keys"] if a["kinds"][k] == BENEFIT]) or best(
        [k for k in a["keys"] if a["kinds"][k] == NEUTRAL and k not in gates])
    bad = best([k for k in a["keys"] if a["kinds"][k] == DRAWBACK])
    picks = [k for k in (good, bad) if k]
    if bad and a["gate_of"].get(bad) and a["gate_of"][bad] not in known:
        picks.append(a["gate_of"][bad])
    return sorted(dict.fromkeys(picks), key=_key_index)


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

def study_dc(ingredient) -> int:
    """10 + 5 per rarity band (§8.3)."""
    from .worldclass import tier_rank

    rules = lore()["study"]
    # `tier_rank` counts from 1 (common is 1), and common is the band with nothing added.
    band = max(0, tier_rank(ingredient.tier) - 1)
    return int(rules["dc_base"]) + int(rules["dc_per_band"]) * band


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


def _rested_since(actor, mark: dict, clock: int) -> bool:
    """Whether the character has slept since `mark` was written. `awake_minutes` rises
    with every minute the clock moves and is reset by a night's sleep (rules/survival.py
    `sleep`), so a waking count lower than the miss's plus the time since is a sleep."""
    try:
        then_clock = int(mark.get("clock", 0))
        then_awake = int(mark.get("awake", 0))
    except (TypeError, ValueError):
        return True
    elapsed = max(0, int(clock) - then_clock)
    return int(getattr(actor, "awake_minutes", 0) or 0) < then_awake + elapsed


def study_waits(actor, ingredient_id: str, clock: int | None = None) -> bool:
    """A miss cannot be retried until after a rest (§8.3; PF1e's take-the-time
    convention). True while that rest is still owed. Clears itself once it is not."""
    entry = _entry(actor, ingredient_id)
    mark = (entry or {}).get("study_after_rest")
    if not isinstance(mark, dict):
        return False
    now = int(mark.get("clock", 0)) if clock is None else int(clock)
    if clock is None:
        # Asked without the clock (the card): the waking count alone says it — a sleep
        # puts it below what it was at the miss.
        return int(getattr(actor, "awake_minutes", 0) or 0) >= int(mark.get("awake", 0))
    if _rested_since(actor, mark, now):
        entry.pop("study_after_rest", None)
        return False
    return True


def study_order(actor, ingredient) -> list[str]:
    """The unknown keys a study reveals, in order, with each poison's gate folded into its
    body: a gate is free, it is the same fact as what it guards."""
    a = anatomy(ingredient)
    known = set(known_keys(actor, ingredient))
    gates = set(a["gate_of"].values())
    return [k for k in a["keys"] if k not in known and k not in gates]


def study(actor, ingredient, total: int, *, clock: int) -> dict:
    """Resolve a study on a total already rolled. No automatic natural 20: a skill check
    in 1e succeeds on the total alone (CRB p.180), which `dice.d20_succeeds` exists to
    keep apart from saves and attacks. Success reveals one property and one more per 5
    points over the DC; a miss stamps the herb until the next rest."""
    dc = study_dc(ingredient)
    margin = int(total) - dc
    success = margin >= 0
    revealed: list[str] = []
    if success:
        n = 1 + margin // int(lore()["study"]["reveal_per_margin"])
        order = study_order(actor, ingredient)[:n]
        gate_of = anatomy(ingredient)["gate_of"]
        keys = order + [gate_of[k] for k in order if k in gate_of]
        revealed = reveal(actor, ingredient.id, keys, f"studied, day {day_of(clock)}")
    else:
        meet(actor, ingredient.id)
        actor.herb_known[ingredient.id]["study_after_rest"] = {
            "clock": int(clock), "awake": int(getattr(actor, "awake_minutes", 0) or 0)}
    return {"dc": dc, "total": int(total), "success": success, "margin": margin,
            "revealed": revealed}


# --- teachers and libraries ---------------------------------------------------------------

def _words_say(text: str, words) -> bool:
    low = f" {str(text or '').lower()} "
    return any(re.search(rf"(?<![a-z]){re.escape(w.lower())}s?(?![a-z])", low)
               for w in words)


def teaches(person, rec: dict | None = None) -> bool:
    """Whether this person knows herbs: their trade by the population record (`work`,
    an occupation id), or their own words — name, template, description."""
    rules = lore()["teacher"]
    work = str((((rec or {}).get("life") or {}).get("work")) or "")
    if work and work in set(rules["works"]):
        return True
    said = " ".join(str(x or "") for x in (
        getattr(person, "name", ""), getattr(person, "template", ""),
        (rec or {}).get("phrase", ""), getattr(person, "notes", "")))
    return _words_say(said, rules["words"])


def lesson_size(person) -> int:
    """How many properties this person will teach for one fee, by how they feel about the
    player — the confiding gate's shape (rules/confiding.py). 0 is a refusal."""
    from . import attitude

    step = attitude.step_of(attitude.of(person))
    sizes = {attitude.step_of(k): int(v) for k, v in lore()["teacher"]["teaches"].items()}
    # The highest row at or below where they stand: "friendly" covers devoted too.
    fitting = [s for s in sizes if 0 <= s <= step]
    return sizes[max(fitting)] if fitting else 0


def lesson_order(actor, ingredient) -> list[str]:
    """What a teacher tells first: the dangers, then the uses. A healer warns before they
    recommend, and a gate is told with its body."""
    a = anatomy(ingredient)
    known = set(known_keys(actor, ingredient))
    gates = set(a["gate_of"].values())
    fresh = [k for k in a["keys"] if k not in known and k not in gates]
    return [k for k in fresh if a["kinds"][k] == DRAWBACK] + \
        [k for k in fresh if a["kinds"][k] != DRAWBACK]


def with_gates(ingredient, keys: list[str]) -> list[str]:
    gate_of = anatomy(ingredient)["gate_of"]
    return list(keys) + [gate_of[k] for k in keys if k in gate_of]


def is_library(place) -> bool:
    """A place that keeps records: the settlement table's library, a scriptorium, an
    archive, a temple's archive (rules/places.py names them; nothing here mints one)."""
    if place is None or getattr(place, "described_only", False):
        return False
    said = f"{getattr(place, 'name', '')} {getattr(place, 'kind', '')}"
    return _words_say(said, lore()["library"]["words"])


def common_knowledge(ingredient) -> list[str]:
    """What the world writes down about a herb: the benefits (and the bare DCs that guard
    nothing) of a common or uncommon herb. A rare herb's secrets and every drawback stay
    unwritten — the library is the safe route, never the complete one."""
    rules = lore()["library"]
    if str(ingredient.tier) not in set(rules["tiers"]):
        return []
    a = anatomy(ingredient)
    gates = set(a["gate_of"].values())
    want = set(rules["reveals"])
    return [k for k in a["keys"] if a["kinds"][k] in want and k not in gates]


# --- manuals ------------------------------------------------------------------------------

def manual_keys(manual: dict) -> dict[str, list[str]]:
    """A manual's teaching, resolved against the corpus as it stands: ingredient id ->
    keys. An id the corpus does not hold is skipped, never invented."""
    out: dict[str, list[str]] = {}
    for row in manual.get("teaches") or ():
        ing = _ingredient(str(row.get("ingredient") or ""))
        if ing is None:
            continue
        a = anatomy(ing)
        want = row.get("keys", "all")
        if want == "all":
            keys = list(a["keys"])
        elif want == "benefits":
            keys = [k for k in a["keys"] if a["kinds"][k] != DRAWBACK
                    and k not in set(a["gate_of"].values())]
        elif want == "drawbacks":
            keys = with_gates(ing, [k for k in a["keys"] if a["kinds"][k] == DRAWBACK])
        else:
            keys = [str(k) for k in (want or ()) if str(k) in a["keys"]]
        if keys:
            out.setdefault(ing.id, [])
            out[ing.id] += [k for k in keys if k not in out[ing.id]]
    return out


def manual_named(said: str) -> dict | None:
    """A manual by id or by name, as the browser or a shelf calls it."""
    said_l = " ".join(str(said or "").lower().split())
    for mid, m in manuals().items():
        if said_l in (mid, str(m.get("name", "")).lower()):
            return m
    return None


def holds_manual(actor, manual: dict) -> bool:
    """Whether the character has this book with them: bought off a counter it is a shelf
    entry under its name (`goods.deliver`); handed over or looted it may be a good."""
    names = {str(manual.get("id", "")).lower(), str(manual.get("name", "")).lower()}
    for s in (getattr(actor, "stock", None) or {}).values():
        if str(getattr(s, "base", "")).lower() in names and int(getattr(s, "count", 0)) > 0:
            return True
    for bag in ("goods", "loadout"):
        for k, n in (getattr(actor, bag, None) or {}).items():
            if str(k).lower() in names and int(n or 0) > 0:
                return True
    return False


# --- what a new herbalist already knows ----------------------------------------------------

def is_herbalist(actor) -> bool:
    return "herbalist" in (getattr(actor, "world_classes", None) or {})


def _people_entity(actor, world):
    """The world's own people this character's race is (`origin: world:<id>`), or None."""
    if world is None:
        return None
    from . import races as races_mod

    try:
        doc = races_mod.get(str(getattr(actor, "race", "") or ""))
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
