"""What a character knows about each herb and each craft material
(docs/herbalism-revamp-plan.md §8; docs/blacksmithing-revamp-plan.md §9; the API is
docs/blacksmithing-contracts.md §6).

This is `rules/herbknowledge.py`'s machinery lifted off the ingredient corpus, so the
smith's discovery is the herbalist's and not a second copy of it. `herbknowledge` keeps
every name it had, by re-exporting from here or wrapping, and keeps what only herbs have
(tasting's condition rule, the homeland seed, the herbarium rows, the narrator's brief).
The plan's first idea (§9.1) was to copy the module for metals; a copy is exactly what
CLAUDE.md's "when you fix a rule, grep for every copy of it" warns about, and the two
would have drifted the first time anyone corrected how a drawback is told.

**A document** is either an `Ingredient` (its effect lines are `pairs`) or a normalised
material document (contract §3: a dict with `weapon`, `armour`, `working` and
`quench_mark`). A string is resolved as a material first, through lane C's
`rules/materials.py` (the one door to every craft material), then as an ingredient. The
two id spaces are disjoint (`tests/test_alchemist.py` pins it), so the order only decides
which loader is asked first.

**A property is one positional key.** An ingredient's are "p0", "p1"... as they always
were. A material's are one per effect, by list: "w0".. for `weapon`, "a0".. for `armour`,
"t0".. for `working` traits, and "q0" for the quench mark. Positional on purpose, for the
reason herbs gave: a key that is a slug of the text breaks the moment an author fixes a
typo in it.

**One store.** `Actor.herb_known`, keyed by herb id or material id (contract §6: no new
Actor field this wave; a rename is a later migration). A material is stored under its
parent material (`materials.material_of`), so mithral learned at the forge is mithral at
the leatherworker's bench too, the owner's "one material, many shelves" ruling.

**Severed tells.** Nothing here hands an unknown property to anyone: `properties` prints
a known row's words and an unknown row's nothing.

**No model authors a number.** Every DC, price and time is a row in
content/rules/herb-lore.json or content/rules/smithing-lore.json; every effect is the
document's own spec.
"""
from __future__ import annotations

import functools
import importlib
import json
import re
import sys
from pathlib import Path

# The bookkeeping slot inside `Actor.herb_known`. Underscored so no ingredient or material
# id (lowercase letters, digits and hyphens) can ever collide with it.
SEEDED = "_seeded"

BENEFIT, DRAWBACK, NEUTRAL = "benefit", "drawback", "neutral"

# Effect types that hurt whoever takes them on top of `consumables.hurts`, which was
# written for a jar's Drawbacks panel and predates these three in the catalogue.
_HARM_TYPES = frozenset({"vulnerability", "ability_drain", "bleed"})

HERBALIST, BLACKSMITH = "herbalist", "blacksmith"

# A material's lists, in the order their properties are keyed and shown, with the prefix
# each key carries. Herbs' "p" sorts first, so an ingredient's key order is untouched.
MATERIAL_LISTS = (("weapon", "w"), ("armour", "a"), ("working", "t"), ("quench_mark", "q"))
_PREFIX_ORDER = {"p": 0, **{p: i + 1 for i, (_, p) in enumerate(MATERIAL_LISTS)}}
GROUP_OF_PREFIX = {p: g for g, p in MATERIAL_LISTS}

# `gear_mod` targets where a LOWER number is the better item (contract §2): less spell
# failure, less weight, a lighter category, a smaller speed penalty. Every other target
# (hardness, hit points per inch, maximum Dex, and the armour check penalty, which is
# written as the negative number the armour tables print, so +1 lessens it) is better
# higher. Read off the spec, never the words, as herbs' classifier is.
_LOWER_IS_BETTER = frozenset({"asf", "weight_pct", "category", "speed_penalty"})

# Working traits that make the metal harder to work or worse when it is done (plan
# §5.5). The rest help. `reactive` is the drawback that makes assaying dangerous.
_BAD_TRAITS = frozenset({"slaggy", "sulfurous", "quench_sensitive", "narrow_window",
                         "reactive", "brittle", "hot_short"})

# A rider whose trigger is a blow lands on the struck foe (contract §2), so the harm it
# does is the wielder's benefit: wyvern blood's first-wound poison is why you quench in
# it. A `carried` rider lands on whoever holds the thing, and is judged as harm to them.
_FOE_TRIGGERS = frozenset({"hit", "crit", "first_wound_daily"})


# --- the rule rows ------------------------------------------------------------------------
#
# Shipped content only, never a homebrew overlay, so an lru_cache is honest: nothing under
# CAMPAIGN_DIR can change what these files say mid-run.

_LORE_FILES = {HERBALIST: "herb-lore.json", BLACKSMITH: "smithing-lore.json"}
_MANUAL_FILES = {HERBALIST: "herbal-manuals.json", BLACKSMITH: "smithing-manuals.json"}


def _content(name: str) -> dict:
    from django.conf import settings

    path = Path(settings.BASE_DIR) / "content" / "rules" / name
    return json.loads(path.read_text(encoding="utf-8"))


@functools.lru_cache(maxsize=4)
def _rule_file(name: str) -> dict:
    return _content(name)


def craft_of(doc_or_craft) -> str:
    """Which craft's rule rows answer for a document: a material's are the smith's, a
    herb's the herbalist's. A craft id passes through."""
    if isinstance(doc_or_craft, str):
        return BLACKSMITH if doc_or_craft == BLACKSMITH else HERBALIST
    return BLACKSMITH if is_material(doc_or_craft) else HERBALIST


def lore(doc_or_craft=HERBALIST) -> dict:
    """The prices, times and DCs of learning, for this document's craft."""
    return _rule_file(_LORE_FILES[craft_of(doc_or_craft)])


@functools.lru_cache(maxsize=4)
def _manual_rows(craft: str) -> tuple:
    return tuple(_rule_file(_MANUAL_FILES[craft]).get("manuals") or ())


def manuals(craft: str | None = None) -> dict[str, dict]:
    """Every manual of one craft (or of every craft, with None), by id. The herbal ones
    are content/rules/herbal-manuals.json, the smithing ones smithing-manuals.json."""
    crafts = [craft] if craft else list(_MANUAL_FILES)
    out: dict[str, dict] = {}
    for c in crafts:
        for m in _manual_rows(c):
            if m.get("id"):
                out[str(m["id"])] = dict(m, craft=c)
    return out


# --- documents ------------------------------------------------------------------------------

def _door():
    """`rules/materials.py`, lane C's one door to every craft material, or None where it
    is not built yet. Looked up by name in `sys.modules` first, so a test can stand a
    fake door there (or None, to block it) and this module never pins an import order.

    A failed import is not cached by Python: every herb reveal asks the door whether
    its id is a material, and without lane C that was a fresh search of the import path
    each time. The miss is remembered once (`_import_door`); a module that does import
    lands in `sys.modules` and is found there."""
    name = f"{__package__}.materials"
    if name in sys.modules:
        return sys.modules[name]
    return _import_door(name)


@functools.lru_cache(maxsize=1)
def _import_door(name: str):
    try:
        return importlib.import_module(name)
    except ImportError:
        return None


def material_of(material_id: str) -> str:
    """The parent material a form belongs to ("mithral-fittings" -> "mithral"), so one
    material is learned once whichever shelf it was met on."""
    door = _door()
    mid = str(material_id or "")
    if door is None or not hasattr(door, "material_of"):
        return mid
    try:
        return str(door.material_of(mid) or mid)
    except (KeyError, ValueError):
        return mid


def material(material_id: str) -> dict | None:
    """The normalised material document, or None. A form resolves to its parent."""
    door = _door()
    if door is None:
        return None
    for mid in dict.fromkeys((material_of(material_id), str(material_id or ""))):
        try:
            got = door.get(mid)
        except KeyError:
            got = None
        if got:
            return got
    return None


def all_materials() -> dict[str, dict]:
    door = _door()
    if door is None:
        return {}
    try:
        return dict(door.all())
    except Exception:  # noqa: BLE001 — a door that cannot list is a door with nothing on it
        return {}


def is_material(doc) -> bool:
    """A material document is a dict (contract §3); an ingredient is an object with
    `pairs`. Asked by shape, so a document from any craft's file counts."""
    return isinstance(doc, dict)


def _ingredient(ingredient_or_id):
    if isinstance(ingredient_or_id, str):
        from . import ingredients as ing_mod

        try:
            return ing_mod.get(ingredient_or_id)
        except KeyError:
            return None
    return ingredient_or_id


def resolve(doc_or_id):
    """A document from an id (material first, then ingredient), or the document itself."""
    if isinstance(doc_or_id, str):
        return material(doc_or_id) or _ingredient(doc_or_id)
    return doc_or_id


def _field(doc, name: str, default=""):
    if isinstance(doc, dict):
        return doc.get(name, default)
    return getattr(doc, name, default)


def doc_id(doc) -> str:
    """The id knowledge is stored under: a material's parent, an ingredient's own id."""
    raw = str(_field(doc, "id", "") or "")
    return material_of(raw) if is_material(doc) else raw


def _material_specs(doc: dict) -> list[tuple[str, dict, str]]:
    """(key, spec, group) per property, in key order."""
    out: list[tuple[str, dict, str]] = []
    for group, prefix in MATERIAL_LISTS:
        raw = doc.get(group)
        if group == "quench_mark":
            raw = [raw] if isinstance(raw, dict) else []
        for i, spec in enumerate(raw or ()):
            if isinstance(spec, dict):
                out.append((f"{prefix}{i}", spec, group))
    return out


# --- properties -----------------------------------------------------------------------------

def property_keys(doc) -> list[str]:
    """Every property this document has, as keys."""
    if is_material(doc):
        return [k for k, _, _ in _material_specs(doc)]
    return [f"p{i}" for i in range(len(getattr(doc, "pairs", []) or []))]


def _key_index(key: str) -> int:
    return int(key[1:]) if str(key)[1:].isdigit() else 0


def key_order(key: str) -> tuple:
    """Sort order for keys of any document: by list, then by position. Every herb key is
    "p", so an ingredient's order is exactly `_key_index`'s, as it always was."""
    k = str(key)
    return (_PREFIX_ORDER.get(k[:1], 9), _key_index(k))


def _specs(doc) -> list[dict]:
    """The document's specs, one per key, as the SAME dict objects each time asked
    within a call — `consumables.poisons` groups by identity."""
    if is_material(doc):
        return [spec for _, spec, _ in _material_specs(doc)]
    return [spec for _, spec in (getattr(doc, "pairs", None) or [])]


def classify(spec: dict) -> str:
    """Whether one property is good for the one it belongs to, bad for them, or neither.

    Read off the structured spec, never the words: a penalty (a negative modifier), a
    condition caused, damage or ability damage to the taker is a drawback; healing, a
    bonus, a resistance or a condition ended is a benefit. A bare save gate is NEUTRAL:
    measured on the corpus, 38 of the 161 ingredients carry a "DC n" that gates nothing
    (the entry's crafting DC restated, swept up by the extractor), and the rest gate a
    poison's body, which is the drawback. `consumables.hurts` already says this for the
    jar's Drawbacks panel, so it is asked rather than copied.

    The smith's three types (contract §2) are asked first, and no herb carries one:
    a `working` trait is good or bad by name (`_BAD_TRAITS`); `strikes_as` is always a
    benefit; a `gear_mod` is good or bad by its sign AND its target, because "-10" is a
    benefit on spell failure and a drawback on hardness, which a sign rule alone (what
    `consumables.hurts` does to every `_mod`) would have read backwards for half of
    mithral's book line. A rider triggered by a blow lands on the foe, so it is a benefit.
    """
    from . import consumables

    spec = spec or {}
    kind = str(spec.get("type", ""))
    if kind == "working":
        trait = str(spec.get("trait") or spec.get("target") or "")
        return DRAWBACK if trait in _BAD_TRAITS else BENEFIT
    if kind == "strikes_as":
        return BENEFIT
    if kind == "gear_mod":
        try:
            amount = int(spec.get("amount", 0) or 0)
        except (TypeError, ValueError):
            return NEUTRAL
        if amount == 0:
            return NEUTRAL
        better = amount < 0 if str(spec.get("target")) in _LOWER_IS_BETTER else amount > 0
        return BENEFIT if better else DRAWBACK
    if str(spec.get("trigger") or "") in _FOE_TRIGGERS:
        return BENEFIT
    if kind == "save_gate":
        return DRAWBACK if consumables.hurts(spec) else NEUTRAL
    if kind in _HARM_TYPES or consumables.hurts(spec):
        return DRAWBACK
    return BENEFIT


def is_drawback(spec: dict) -> bool:
    """The question the card's `drawback` field answers."""
    return classify(spec) == DRAWBACK


def anatomy(doc) -> dict:
    """Each key's class, and which bare gate guards which poison body.

    `gate_of` maps a body key to the key of the save that gates it ("Fortitude DC 15"
    gates "Causes paralyzed"). A gate is revealed with its body, because 1e writes a
    poison as one thing — a save, and what happens when you fail it (`consumables.Poison`).
    A material writes its save with the harm nested inside it (`on_failure`), so it has
    no loose gates and its `gate_of` is empty.
    """
    from . import consumables

    specs = _specs(doc)
    keys = property_keys(doc)
    kinds = {k: classify(s) for s, k in zip(specs, keys)}
    gate_of: dict[str, str] = {}
    if not is_material(doc):
        index = {id(s): k for s, k in zip(specs, keys)}
        name = str(getattr(doc, "name", "") or "")
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


def known_keys(actor, doc) -> list[str]:
    """The keys this actor knows, in key order. Only keys the document still has: a
    corpus correction that shortens an effect list must not leave a phantom "known"."""
    entry = _entry(actor, doc_id(doc))
    if entry is None:
        return []
    have = set(entry.get("keys") or ())
    return [k for k in property_keys(doc) if k in have]


def unknown_count(actor, doc) -> int:
    """How many of this document's properties the actor does not yet know."""
    known = set(known_keys(actor, doc))
    return sum(1 for k in property_keys(doc) if k not in known)


def reveal(actor, ingredient_id: str, keys, how: str) -> list[str]:
    """Record that `keys` are now known, and how. Returns the keys that were NEW, so the
    caller can say "New: ..." only for real discoveries and pay mastery for firsts.
    `ingredient_id` may be any document's id; a material form is stored on its parent."""
    entry = actor.herb_known.setdefault(_store_id(ingredient_id), {"keys": [], "how": {}})
    entry.setdefault("keys", [])
    entry.setdefault("how", {})
    have = set(entry.get("keys") or [])
    new = [k for k in dict.fromkeys(keys) if k not in have]
    if new:
        entry["keys"] = sorted(have | set(new), key=key_order)
        for k in new:
            entry["how"][k] = str(how)
    return new


def _store_id(any_id) -> str:
    """The id knowledge lives under. A material form goes to its parent; anything else,
    an ingredient above all, is its own id — the door is only asked about materials."""
    raw = str(any_id or "")
    door = _door()
    if door is None or not hasattr(door, "material_of"):
        return raw
    try:
        known = door.get(raw)
    except KeyError:
        known = None
    return material_of(raw) if known else raw


def meet(actor, ingredient_id: str) -> None:
    """Note that the character has come across this herb or material, knowing nothing
    yet, so the herbarium or the ledger lists it."""
    actor.herb_known.setdefault(_store_id(ingredient_id), {"keys": [], "how": {}})


def day_of(clock_minutes: int) -> int:
    """Day 1 is the first day, the way the Journal's history counts (play/history.py)."""
    return int(clock_minutes or 0) // (24 * 60) + 1


_GEAR_WORDS = {
    "acp": "armour check penalty", "max_dex": "maximum Dex bonus",
    "asf": "% arcane spell failure", "weight_pct": "% weight", "hardness": "hardness",
    "hp_per_inch": "hit points per inch", "category": "armour category for movement",
    "speed_penalty": "ft speed penalty",
}


def line(spec: dict) -> str:
    """One property as a card's words. The effect vocabulary's renderer first; for the
    smith's three types, until lane A's renderer speaks them (it answers with the bare
    type id meanwhile), a plain line built from the spec and the trait words in
    content/rules/smithing-lore.json."""
    from . import effectspec

    kind = str((spec or {}).get("type", ""))
    try:
        said = effectspec.render(spec)
    except Exception:  # noqa: BLE001 — a spec the renderer cannot read still has a line
        said = ""
    if said and said not in (kind, str(spec.get("note") or "")):
        return said
    amount = spec.get("amount")
    if kind == "gear_mod":
        word = _GEAR_WORDS.get(str(spec.get("target")), str(spec.get("target")))
        try:
            return f"{int(amount):+d}{'' if word.startswith('%') else ' '}{word}"
        except (TypeError, ValueError):
            return word
    if kind == "strikes_as":
        return f"Strikes as {str(spec.get('target', '')).replace('_', ' ')}"
    if kind == "working":
        trait = str(spec.get("trait") or spec.get("target") or "")
        words = (lore(BLACKSMITH).get("working_words") or {}).get(trait)
        name = trait.replace("_", " ").capitalize()
        return f"{name}: {words}" if words else name
    return said or str(spec.get("note") or kind or "?")


def _lines(doc) -> list[tuple[str, str, dict]]:
    """(key, words, spec) per property."""
    if is_material(doc):
        return [(k, line(s), s) for k, s, _ in _material_specs(doc)]
    return [(k, ln, s) for k, (ln, s) in zip(property_keys(doc), getattr(doc, "pairs", []) or [])]


def properties(actor, doc) -> list[dict]:
    """The card's property rows (docs/herbalism-contracts.md §4.2): a known one says what
    it does and how it was learned; an unknown one says nothing at all. A material's rows
    also say which list they are in (`group`: weapon, armour, working, quench_mark), and
    the group is shown even when the row is not — that the iron does *something* to a
    blade is visible on the anvil; what it does is the discovery."""
    entry = _entry(actor, doc_id(doc)) or {}
    how = entry.get("how") or {}
    known = set(known_keys(actor, doc))
    out = []
    for key, words, spec in _lines(doc):
        if key in known:
            row = {"key": key, "known": True, "text": words,
                   "drawback": is_drawback(spec), "how": str(how.get(key) or "")}
        else:
            row = {"key": key, "known": False, "text": None, "drawback": None, "how": None}
        if is_material(doc):
            row["group"] = GROUP_OF_PREFIX.get(key[:1], "")
        out.append(row)
    return out


def danger_known(actor, doc) -> str:
    """What the character knows can hurt them, in one line, or "" — the card's warning
    ("You know this is dangerous: ..."). Read from known drawbacks every time, so every
    route that reveals one sets it, not only study."""
    known = set(known_keys(actor, doc))
    return "; ".join(words for key, words, spec in _lines(doc)
                     if key in known and is_drawback(spec))


# --- one benefit and one drawback (tasting, assaying) --------------------------------------

def reveal_picks(actor, doc, landed=()) -> list[str]:
    """Which keys a taste or an assay reveals: at most one benefit and at most one
    drawback, each the first UNKNOWN one, preferring what actually landed (if hemlock
    paralysed you, the paralysis is what you learned). A drawback brings its gate with
    it. A document whose benefits are all known teaches nothing new on that side: a
    second try is for the side you have not learned.

    "Benefit" here is anything not a drawback, so a herb whose only line is a bare DC
    still teaches that line on a first taste; a gate that guards a poison is never the
    benefit — it is half of the drawback.
    """
    a = anatomy(doc)
    known = set(known_keys(actor, doc))
    landed = set(landed)
    gates = set(a["gate_of"].values())

    def best(cands: list[str]) -> str:
        # Landed first, and among what landed a condition first: being paralysed is
        # the thing a taster cannot fail to notice, more than a point of Constitution.
        fresh = [k for k in cands if k not in known]
        fresh.sort(key=lambda k: (k not in landed,
                                  str(a["specs"][k].get("type")) != "apply_condition",
                                  key_order(k)))
        return fresh[0] if fresh else ""

    good = best([k for k in a["keys"] if a["kinds"][k] == BENEFIT]) or best(
        [k for k in a["keys"] if a["kinds"][k] == NEUTRAL and k not in gates])
    bad = best([k for k in a["keys"] if a["kinds"][k] == DRAWBACK])
    picks = [k for k in (good, bad) if k]
    if bad and a["gate_of"].get(bad) and a["gate_of"][bad] not in known:
        picks.append(a["gate_of"][bad])
    return sorted(dict.fromkeys(picks), key=key_order)


# --- study -------------------------------------------------------------------------------

def study_dc(doc) -> int:
    """10 + 5 per rarity band (herbs §8.3; materials the same, plan §9.2)."""
    from .worldclass import tier_rank

    rules = lore(doc)["study"]
    # `tier_rank` counts from 1 (common is 1), and common is the band with nothing added.
    band = max(0, tier_rank(str(_field(doc, "tier", "") or "")) - 1)
    return int(rules["dc_base"]) + int(rules["dc_per_band"]) * band


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
    entry = _entry(actor, _store_id(ingredient_id))
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


def study_order(actor, doc) -> list[str]:
    """The unknown keys a study reveals, in order, with each poison's gate folded into its
    body: a gate is free, it is the same fact as what it guards."""
    a = anatomy(doc)
    known = set(known_keys(actor, doc))
    gates = set(a["gate_of"].values())
    return [k for k in a["keys"] if k not in known and k not in gates]


def study(actor, doc, total: int, *, clock: int) -> dict:
    """Resolve a study on a total already rolled. No automatic natural 20: a skill check
    in 1e succeeds on the total alone (CRB p.180), which `dice.d20_succeeds` exists to
    keep apart from saves and attacks. Success reveals one property and one more per 5
    points over the DC; a miss stamps the document until the next rest."""
    dc = study_dc(doc)
    margin = int(total) - dc
    success = margin >= 0
    revealed: list[str] = []
    did = doc_id(doc)
    if success:
        n = 1 + margin // int(lore(doc)["study"]["reveal_per_margin"])
        order = study_order(actor, doc)[:n]
        gate_of = anatomy(doc)["gate_of"]
        keys = order + [gate_of[k] for k in order if k in gate_of]
        revealed = reveal(actor, did, keys, f"studied, day {day_of(clock)}")
    else:
        meet(actor, did)
        actor.herb_known[did]["study_after_rest"] = {
            "clock": int(clock), "awake": int(getattr(actor, "awake_minutes", 0) or 0)}
    return {"dc": dc, "total": int(total), "success": success, "margin": margin,
            "revealed": revealed}


# --- teachers and libraries ---------------------------------------------------------------

def _words_say(text: str, words) -> bool:
    low = f" {str(text or '').lower()} "
    return any(re.search(rf"(?<![a-z]){re.escape(w.lower())}s?(?![a-z])", low)
               for w in words)


def teaches(person, rec: dict | None = None, craft: str = HERBALIST) -> bool:
    """Whether this person knows the craft's lore: their trade by the population record
    (`work`, an occupation id: a healer for herbs, a smith for metals), or their own
    words — name, template, description."""
    rules = lore(craft)["teacher"]
    work = str((((rec or {}).get("life") or {}).get("work")) or "")
    if work and work in set(rules["works"]):
        return True
    said = " ".join(str(x or "") for x in (
        getattr(person, "name", ""), getattr(person, "template", ""),
        (rec or {}).get("phrase", ""), getattr(person, "notes", "")))
    return _words_say(said, rules["words"])


def lesson_size(person, craft: str = HERBALIST) -> int:
    """How many properties this person will teach for one fee, by how they feel about the
    player — the confiding gate's shape (rules/confiding.py). 0 is a refusal."""
    from . import attitude

    step = attitude.step_of(attitude.of(person))
    sizes = {attitude.step_of(k): int(v) for k, v in lore(craft)["teacher"]["teaches"].items()}
    # The highest row at or below where they stand: "friendly" covers devoted too.
    fitting = [s for s in sizes if 0 <= s <= step]
    return sizes[max(fitting)] if fitting else 0


def lesson_order(actor, doc) -> list[str]:
    """What a teacher tells first: the dangers, then the uses. A healer warns before they
    recommend, and so does a smith; a gate is told with its body."""
    a = anatomy(doc)
    known = set(known_keys(actor, doc))
    gates = set(a["gate_of"].values())
    fresh = [k for k in a["keys"] if k not in known and k not in gates]
    return [k for k in fresh if a["kinds"][k] == DRAWBACK] + \
        [k for k in fresh if a["kinds"][k] != DRAWBACK]


def with_gates(doc, keys: list[str]) -> list[str]:
    gate_of = anatomy(doc)["gate_of"]
    return list(keys) + [gate_of[k] for k in keys if k in gate_of]


def is_library(place, craft: str = HERBALIST) -> bool:
    """A place that keeps records: the settlement table's library, a scriptorium, an
    archive, a temple's archive (rules/places.py names them; nothing here mints one)."""
    if place is None or getattr(place, "described_only", False):
        return False
    said = f"{getattr(place, 'name', '')} {getattr(place, 'kind', '')}"
    return _words_say(said, lore(craft)["library"]["words"])


def common_knowledge(doc) -> list[str]:
    """What the world writes down about a herb or a metal: the benefits (and the bare DCs
    that guard nothing) of a common or uncommon one. A rare one's secrets and every
    drawback stay unwritten — the library is the safe route, never the complete one."""
    rules = lore(doc)["library"]
    if str(_field(doc, "tier", "")) not in set(rules["tiers"]):
        return []
    a = anatomy(doc)
    gates = set(a["gate_of"].values())
    want = set(rules["reveals"])
    return [k for k in a["keys"] if a["kinds"][k] in want and k not in gates]


# --- manuals ------------------------------------------------------------------------------

def manual_keys(manual: dict) -> dict[str, list[str]]:
    """A manual's teaching, resolved against the documents as they stand: id -> keys. A
    row names an `ingredient` (herbal manuals) or a `material` (smithing manuals); an id
    nothing holds is skipped, never invented."""
    out: dict[str, list[str]] = {}
    for row in manual.get("teaches") or ():
        if row.get("material"):
            doc = material(str(row.get("material") or ""))
        else:
            doc = _ingredient(str(row.get("ingredient") or ""))
        if doc is None:
            continue
        a = anatomy(doc)
        want = row.get("keys", "all")
        if want == "all":
            keys = list(a["keys"])
        elif want == "benefits":
            keys = [k for k in a["keys"] if a["kinds"][k] != DRAWBACK
                    and k not in set(a["gate_of"].values())]
        elif want == "drawbacks":
            keys = with_gates(doc, [k for k in a["keys"] if a["kinds"][k] == DRAWBACK])
        elif want == "working":
            keys = [k for k in a["keys"] if k.startswith("t")]
        else:
            keys = [str(k) for k in (want or ()) if str(k) in a["keys"]]
        if keys:
            did = doc_id(doc)
            out.setdefault(did, [])
            out[did] += [k for k in keys if k not in out[did]]
    return out


def manual_named(said: str, craft: str | None = None) -> dict | None:
    """A manual by id or by name, as the browser or a shelf calls it."""
    said_l = " ".join(str(said or "").lower().split())
    for mid, m in manuals(craft).items():
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


# --- assay (plan §9.2; contract §6) --------------------------------------------------------

def known_material(actor, material_id: str) -> bool:
    """A material counts as known for comparison once one property of it is: a needle
    you have never read anything off is not a reference."""
    entry = _entry(actor, material_of(material_id))
    return bool(entry and entry.get("keys"))


def assay_dc(doc, actor) -> int:
    """The rarity DC (study's: 10 + 5 a band), less 1 for each OTHER material of the same
    kind the character knows, at most 4 off.

    Assaying is comparison (docs/blacksmithing-prior-art.md §3.8): a touchstone streak is
    read against needles of known fineness, and a spark against sparks you have seen, so
    every metal you know makes the next one easier to place. The cut is by kind (metal
    against metal, ore against ore) because a known fuel says nothing about a new alloy.
    """
    doc = resolve(doc)
    rules = lore(BLACKSMITH)["assay"]
    base = study_dc(doc)
    kind = str(_field(doc, "kind", "") or "")
    me = doc_id(doc)
    everything = all_materials()
    same = 0
    for mid, entry in (getattr(actor, "herb_known", None) or {}).items():
        if mid.startswith("_") or mid == me or not (isinstance(entry, dict) and entry.get("keys")):
            continue
        other = everything.get(mid) or material(mid)
        if other is not None and str(_field(other, "kind", "")) == kind:
            same += 1
    cut = min(int(rules["comparison_max"]), int(rules["comparison_per_known"]) * same)
    return max(0, base - cut)


def assay_cost(doc) -> dict:
    """A sliver: one ore, or a tenth of a bar (bars track tenths), the owner's ruling."""
    rules = lore(BLACKSMITH)["assay"]
    kind = str(_field(doc, "kind", "") or "")
    form = str(_field(doc, "form", "") or "")
    if kind == "ore" or form == "ore":
        return {"ore": int(rules["ore_sliver"])}
    return {"bars": float(rules["bar_sliver"])}


def is_reactive(doc) -> bool:
    """Whether a material has the `reactive` working trait (noqual, abysium): the one
    thing that makes an assay dangerous."""
    return any(str(s.get("trait") or s.get("target") or "") == "reactive"
               for s in (_field(doc, "working", None) or ()) if isinstance(s, dict))


def danger_of(doc) -> tuple[str, dict] | None:
    """(key, effect) of the carrier effect an assay of a reactive metal applies, or None.

    The material's OWN carrier effect (`trigger: carried`, contract §2), so the assay is
    the metal doing to the assayer what it does to anyone who holds it: abysium's
    sickness, never a hazard invented for the bench. A reactive metal with no carrier
    effect has nothing to do to a handler, and an assay of it is safe; a carrier effect
    on a metal that is not reactive is felt by carrying it, not by a ten-minute assay.
    The trigger and the book flag are the item's bookkeeping and do not travel; a
    carrier effect states no length (it lasts while carried), so the assay's comes from
    the rule row (the book's abysium: 1d4 hours after it is put down).
    """
    if not is_reactive(doc):
        return None
    # A danger the material states for the assay itself, when its harm is not a carrier
    # effect: noqual's "magic recoils" (the owner's house rule, 2026-10-04). Its key is
    # the `reactive` working trait's, so what the assayer learns from it is that the
    # metal is reactive — learned by having their wards go quiet.
    stated = _field(doc, "assay_danger", None)
    if isinstance(stated, dict) and stated.get("type"):
        key = next((k for k, spec, _g in _material_specs(doc)
                    if str(spec.get("trait") or "") == "reactive"), "reactive")
        return key, {k: v for k, v in stated.items() if k != "note"}
    for key, spec, _group in _material_specs(doc):
        if str(spec.get("trigger") or "") == "carried":
            effect = {k: v for k, v in spec.items() if k not in ("trigger", "book")}
            duration = effect.get("duration")
            if str(effect.get("type")) == "apply_condition" and not (
                    isinstance(duration, dict) and duration.get("amount")):
                effect["duration"] = dict(lore(BLACKSMITH)["assay"]["danger_duration"])
            return key, effect
    return None


def assay(actor, material_id: str, total: int, *, clock: int) -> dict:
    """Resolve an assay on a Craft total already rolled (the player's die, the smith's
    bonus: `blacksmith.check_terms`).

    The sliver is cut and spent either way, and the ten minutes pass either way: the bench
    takes the cost (`cost`, `minutes`) and this records the knowledge. A success reveals
    one benefit and one drawback, the owner's ruling mirroring tasting, with the danger's
    own key preferred as the drawback (you learned abysium sickens by being sickened). A
    miss reveals nothing and does not wait for a rest as study does: each try costs a
    sliver, which is its own limit.

    `danger` is the reactive metal's carrier effect, applied for real whatever the roll
    said, because the handling hurts and not the reading: the caller runs it through the
    engine with `apply_danger`, so it lands as an ActiveEffect through the one applicator
    (law 2) and is told like every other effect (law 3). Nothing here writes a condition.
    """
    doc = material(material_id)
    if doc is None:
        raise KeyError(f"no material called {material_id!r}")
    mid = doc_id(doc)
    rules = lore(BLACKSMITH)["assay"]
    dc = assay_dc(doc, actor)
    margin = int(total) - dc
    success = margin >= 0
    found = danger_of(doc)
    meet(actor, mid)
    revealed: list[str] = []
    if success:
        landed = {found[0]} if found else set()
        revealed = reveal(actor, mid, reveal_picks(actor, doc, landed=landed),
                          f"assayed, day {day_of(clock)}")
    return {"material": mid, "dc": dc, "total": int(total), "success": success,
            "margin": margin, "revealed": revealed, "cost": assay_cost(doc),
            "minutes": int(rules["minutes"]),
            "danger": found[1] if found else None}


def apply_danger(engine, actor, material_id: str, effect: dict | None,
                 because: str = "") -> list:
    """Run an assay's danger through the engine, as the taste op runs a herb's raw effect:
    the spec becomes ordinary intents (`consumables.plan`), validated with `origin
    item:<material id>` so immunity and every other gate apply, and run. (The condition
    op stamps the intent's `because` as the condition's source and not yet its `origin`;
    that is the engine's, contract §5, and the herb taste shares it.) Dice in a
    duration ("1d4" hours) are left as dice: `Engine._duration_rounds` is the one place
    every op's duration is rolled. Returns the outcomes (empty when there is no danger,
    or when the engine cannot stand the spec up: a property that did nothing this time,
    never an assay that crashes the turn)."""
    if not effect:
        return []
    from . import consumables
    from .engine import IntentError

    doc = material(material_id) or {}
    mid = doc_id(doc) if doc else str(material_id)
    name = str(doc.get("name") or mid)
    spec = dict(effect)
    if str(spec.get("type") or "") == "suppress_magic":
        return [_suppress_magic(engine, actor, mid, name, spec, because)]
    use = consumables.plan({"name": name, "specs": [spec], "count": 1}, how="drink",
                           target=actor.ref, because=because or f"assaying {name}")
    made = [dict(i, visibility="hidden") for i in use.intents]
    for m in made:
        # `consumables` writes a lifted condition as `remove`; the op's word is `ends`
        # (the taste op's own note says the same).
        params = m.get("params") or {}
        if m.get("op") == "condition" and "remove" in params:
            m["params"] = {**{k: v for k, v in params.items() if k != "remove"},
                           "ends": bool(params["remove"])}
    if not made:
        return []
    try:
        res = engine.run(engine.validate(made, origin=f"item:{mid}", origin_name=name))
    except IntentError:
        return []
    return list(res.outcomes)


def _suppress_magic(engine, actor, mid: str, name: str, spec: dict, because: str):
    """Noqual's recoil (the owner's HOUSE RULE, 2026-10-04, contracts §13.2): the
    assayer's active magical effects — buffs and wards — are suppressed for 1d4 rounds.

    One `ActiveEffect` through the one applicator, `origin: item:<material>`, granting
    `suppressed.magic` (`sheet.MAGIC_SUPPRESSED`); `Actor._buff_mods` skips a spell's
    modifiers and the engine skips the bearer's wards while it holds. Nothing is removed
    or re-timed: the book's antimagic field "suppresses" a spell, which resumes when the
    field is gone, and so do these when the recoil wears off (law 2 — remove the effect
    and its contribution evaporates; here the contribution is the silence). The duration
    is rolled by `Engine._duration_rounds`, the one place every duration is rolled. The
    tell says it (law 3)."""
    from .activeeffect import ActiveEffect
    from .engine import Outcome
    from .sheet import MAGIC_SUPPRESSED, is_magical

    rounds = engine._duration_rounds(spec.get("duration"), default_unit="round") \
        if engine is not None else None
    rounds = max(1, int(rounds or 1))
    held = [e for e in actor.effects if is_magical(e)]
    actor.apply_effect(ActiveEffect(
        name="magic recoils", kind="situation", key="magic-recoils",
        source=because or f"assaying {name}", origin=f"item:{mid}",
        duration="rounds", rounds_left=rounds, tags=(MAGIC_SUPPRESSED,),
        payload={"house_rule": True}))
    wards = [w for w in (getattr(getattr(engine, "scene", None), "wards", None) or ())
             if getattr(w, "owner", "") == actor.ref]
    span = f"{rounds} round{'s' if rounds != 1 else ''}"
    tell = (f"The {name.lower()} recoils from magic: "
            + (f"the spells and wards on {actor.name} go quiet for {span}."
               if held or wards else
               f"{actor.name} carries no magic for it to touch, but for {span} it would."))
    return Outcome(intent_id="assay", op="condition",
                   effects=[{"ref": actor.ref, "kind": "condition",
                             "condition": "magic-recoils", "rounds_left": rounds,
                             "origin": f"item:{mid}", "house_rule": True,
                             "suppressed": [str(e.source or e.name) for e in held]}],
                   tell=tell, because=because or f"assaying {name}")


def worked(actor, material_id: str, *, clock: int) -> list[str]:
    """A successful step at the bench reveals the material's working traits: you watched
    it behave under the hammer (plan §9.2). Returns the keys that were new."""
    doc = material(material_id)
    if doc is None:
        return []
    keys = [k for k in property_keys(doc) if k.startswith("t")]
    return reveal(actor, doc_id(doc), keys, f"worked it, day {day_of(clock)}")


# --- the smith's ledger (plan §9.4) ---------------------------------------------------------

def carried_material(actor, doc) -> float:
    """How much of this material the character carries: satchel counts under its id, and
    shelf entries whose base is its name or id (prospected ore is shelved by name)."""
    mid = doc_id(doc)
    names = {mid.lower(), str(_field(doc, "id", "")).lower(), str(_field(doc, "name", "")).lower()}
    n = float((getattr(actor, "inventory", None) or {}).get(mid, 0) or 0)
    for s in (getattr(actor, "stock", None) or {}).values():
        base = str(getattr(s, "base", "") or "").lower()
        if base in names:
            n += float(getattr(s, "count", 0) or 0)
    return int(n) if n == int(n) else n


def met_materials(actor) -> list[str]:
    """Every material the character has come across: what they know of (the store) and
    what they carry. Forms collapse onto their parent."""
    everything = all_materials()
    by_name = {str(d.get("name", "")).lower(): mid for mid, d in everything.items()}
    ids = [k for k in (getattr(actor, "herb_known", None) or {}) if not k.startswith("_")]
    ids += [k for k, n in (getattr(actor, "inventory", None) or {}).items() if n]
    for s in (getattr(actor, "stock", None) or {}).values():
        base = str(getattr(s, "base", "") or "").lower()
        if int(getattr(s, "count", 0) or 0) > 0 and (base in everything or base in by_name):
            ids.append(base if base in everything else by_name[base])
    out = []
    for raw in dict.fromkeys(ids):
        doc = everything.get(raw) or material(raw)
        if doc is not None:
            out.append(doc_id(doc))
    return list(dict.fromkeys(out))


def ledger_row(actor, doc) -> dict:
    """One ledger row: the herbarium's row for a material. `danger_known` is the card's
    warning line, read from known drawbacks only, so the ledger never warns of a danger
    the character has not learned (law 3's rule, kept at the bench too)."""
    return {"id": doc_id(doc), "name": str(_field(doc, "name", "")),
            "kind": str(_field(doc, "kind", "")), "tier": str(_field(doc, "tier", "")),
            "known": len(known_keys(actor, doc)), "total": len(property_keys(doc)),
            "danger_known": danger_known(actor, doc),
            "carried": carried_material(actor, doc)}


def ledger(actor) -> list[dict]:
    """Every material met, by kind then name — the herbarium for materials (contract §6)."""
    rows = []
    for mid in met_materials(actor):
        doc = material(mid)
        if doc is not None:
            rows.append(ledger_row(actor, doc))
    return sorted(rows, key=lambda r: (r["kind"], r["name"].lower()))
