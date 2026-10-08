"""What a character knows about each herb, each craft material, each essence and each
magic item (docs/herbalism-revamp-plan.md §8; docs/blacksmithing-revamp-plan.md §9;
docs/enchanting-revamp-plan.md §12-13; the APIs are docs/blacksmithing-contracts.md §6 and
docs/enchanting-contracts.md §7 — the enchanter's half is the last section of this file).

This is `rules/herbknowledge.py`'s machinery lifted off the ingredient corpus, so the
smith's discovery is the herbalist's and not a second copy of it. `herbknowledge` keeps
every name it had, by re-exporting from here or wrapping, and keeps what only herbs have
(tasting's condition rule, the homeland seed, the herbarium rows, the narrator's brief).
The plan's first idea (§9.1) was to copy the module for metals; a copy is exactly what
CLAUDE.md's "when you fix a rule, grep for every copy of it" warns about, and the two
would have drifted the first time anyone corrected how a drawback is told.

**A document** is either an `Ingredient` (its effect lines are `pairs`) or a normalised
material document (contract §3: a dict with `product`, `weapon`, `armour`, `working`,
`quench_mark`, `mishap` and `toxic`). A string is resolved as a material first, through
`rules/materials.py` (the one door to every craft material), then as an ingredient.
Every material id in every catalogue and every ingredient id in the herb corpus are
disjoint — tests/test_alchemy_shelf.py pins it — so the order only decides which loader
is asked first. (Until 2026-10-06 this said tests/test_alchemist.py pinned it; that test
compared the material catalogues only with each other, and `basilisk-eye` was a herb
and an alchemist's gland at once, the herb's own id resolving to the gland. Merged into
the herb: alchemy plan §5.7.)

**A property is one positional key.** An ingredient's are "p0", "p1"... as they always
were. A material's are one per effect, by list: "p0".. for `product` (what it puts in a
bottle — the same letter as a herb's, because a hybrid herb's effects ARE its product,
and tasting it and assaying it must teach one set of keys), "w0".. for `weapon`, "a0"..
for `armour`, "t0".. for `working` traits, "q0" for the quench mark, "m0" for the
alchemist's mishap and "x0" for the toxic-to-handle document. Positional on purpose, for
the reason herbs gave: a key that is a slug of the text breaks the moment an author
fixes a typo in it.

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

import copy
import functools
import importlib
import math
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

HERBALIST, BLACKSMITH, ENCHANTER = "herbalist", "blacksmith", "enchanter"
ALCHEMIST = "alchemist"
LEATHERWORKER = "leatherworker"

# A material's lists, in the order their properties are keyed and shown, with the prefix
# each key carries. "p" sorts first, so an ingredient's key order is untouched.
#
# The alchemist's four (alchemy contracts §4): `product`, `mishap` and `toxic` joined the
# forge's lists. Measured before they did: `property_keys` was 0 for all 139 alchemist
# materials, because this tuple knew only the forge's fields, so nothing about a reagent
# could ever be learned, taught or shown.
#
# The leatherworker's two (leatherworking contracts §3): a hide's own `shield` list ("s"),
# and a consumable's one `mark` ("k"). Measured before they joined (lane D's finding,
# 2026-10-08): `materials.properties` counted both and this tuple neither, so a hide written
# with a shield list would have had properties the card could never show nor a Grade
# reveal. Marks are ON HOLD (`materials.MARKS_HELD`, the owner's open point 13): the "k"
# list is skipped while the door says so, so no mark is ever learned, shown or taught, and
# enabling marks is that one flag. New letters only: no existing key moves.
MATERIAL_LISTS = (("product", "p"), ("weapon", "w"), ("armour", "a"), ("shield", "s"),
                  ("working", "t"), ("quench_mark", "q"), ("mark", "k"), ("mishap", "m"),
                  ("toxic", "x"))
# The lists that hold one document rather than a list of them.
_SINGLE_LISTS = frozenset({"quench_mark", "mark", "mishap", "toxic"})
# Lists a rule holds back (`_held_lists`): read by nobody while the hold stands.
_HOLDABLE = {"mark": "MARKS_HELD"}
_PREFIX_ORDER = {p: i for i, (_, p) in enumerate(MATERIAL_LISTS)}
GROUP_OF_PREFIX = {p: g for g, p in MATERIAL_LISTS}
# Routes on which a product trait lands on whoever the product is used AGAINST (alchemy
# contracts §2.1): a flask's fire on the struck foe, a cloud's on those inside it. Harm
# delivered there is the product's point, a benefit to its maker; the same harm by
# `carried` or `ingest` is a cost to whoever holds or drinks it. `external` is left out on
# purpose: it is the herb corpus's word, and reclassifying its 49 effects would move what
# a taste of every hybrid herb teaches.
_FOE_ROUTES = frozenset({"struck", "area"})

# `gear_mod` targets where a LOWER number is the better item (contract §2): less spell
# failure, less weight, a lighter category, a smaller speed penalty. Every other target
# (hardness, hit points per inch, maximum Dex, and the armour check penalty, which is
# written as the negative number the armour tables print, so +1 lessens it) is better
# higher. Read off the spec, never the words, as herbs' classifier is.
_LOWER_IS_BETTER = frozenset({"asf", "weight_pct", "category", "speed_penalty"})

# Working traits that make the metal harder to work or worse when it is done (plan
# §5.5). The rest help. `reactive` is the drawback that makes assaying dangerous.
_BAD_TRAITS = frozenset({"slaggy", "sulfurous", "quench_sensitive", "narrow_window",
                         "reactive", "brittle", "hot_short",
                         # The circle's (enchanting plan §7.3): a phial that binds only
                         # by night, drifts in its seat, fades as it is refined, or is
                         # dangerous to read. `eager` and `pure` help.
                         "night_only", "skittish", "heavy", "volatile",
                         # The alchemist's (alchemy plan §5.5): refused at Calcine, a
                         # narrower Dissolve band, a grade lost a day unsealed, refused
                         # in a metal vessel, and harm to whoever works it. `volatile` is
                         # the circle's word too, and means a mishap here.
                         "combustible", "slow_to_dissolve", "light_sensitive",
                         "corrosive", "toxic_to_handle",
                         # The leatherworker's (rules/effectspec.py LEATHER_WORKING_TRAITS):
                         # a tannage half again as long, a step off the best result, a dye
                         # that runs when soaked, an oil that spoils. Measured before: all
                         # four read as benefits, so a Grade of willow bark could "reveal one
                         # positive and one negative" with the negative missing and its
                         # coarse tannage shown as a virtue. `thick` is not here: it is what
                         # makes hide armour possible, at the price of a lime pit.
                         "slow_tan", "ceiling_down", "fugitive", "rancid"})

# An essence's discoverable traits (enchanting plan §7.2; lane D's
# `materials.essence_traits`): what it binds, each house top-up, its phase, its polarity,
# its affinity and each working trait. Keyed by NAME, not position ("grants", "house:0",
# "working:eager"), because that is the key lane D's door hands out; the head of the key
# orders them as a Read reveals them.
ESSENCE_ORDER = ("grants", "house", "phase", "polarity", "affinity", "working")
# The facts that are neither a benefit nor a drawback but what the essence is: where it
# sits and what suits it. What it binds is its benefit.
_ESSENCE_FACTS = ("grants", "phase", "polarity", "affinity")

# A rider whose trigger is a blow lands on the struck foe (contract §2), so the harm it
# does is the wielder's benefit: wyvern blood's first-wound poison is why you quench in
# it. A `carried` rider lands on whoever holds the thing, and is judged as harm to them.
_FOE_TRIGGERS = frozenset({"hit", "crit", "first_wound_daily"})


# --- the rule rows ------------------------------------------------------------------------
#
# Shipped content only, never a homebrew overlay, so an lru_cache is honest: nothing under
# CAMPAIGN_DIR can change what these files say mid-run.

_LORE_FILES = {HERBALIST: "herb-lore.json", BLACKSMITH: "smithing-lore.json",
               ENCHANTER: "enchanting-lore.json", ALCHEMIST: "alchemy-lore.json",
               LEATHERWORKER: "leatherworking-lore.json"}
_MANUAL_FILES = {HERBALIST: "herbal-manuals.json", BLACKSMITH: "smithing-manuals.json",
                 ENCHANTER: "enchanting-manuals.json", ALCHEMIST: "alchemy-manuals.json",
                 LEATHERWORKER: "leatherworking-manuals.json"}
# The alchemist's rule rows are not all written yet (alchemy contracts §1: the manuals
# are lane H's file; no lane owns an alchemy-lore.json in wave 1). Until a file is
# shipped, its craft reads the herbalist's rows — the plan's own fallback for reagents
# (alchemy plan §13.3: "the herbalism `teaches` route", "Libraries: the herbalism route,
# reused") — and has no manuals, rather than crashing every card that asks.
_LORE_FALLBACK = {ALCHEMIST: HERBALIST}


def _content(name: str) -> dict:
    from django.conf import settings

    path = Path(settings.BASE_DIR) / "content" / "rules" / name
    return json.loads(path.read_text(encoding="utf-8"))


def _has_content(name: str) -> bool:
    from django.conf import settings

    return (Path(settings.BASE_DIR) / "content" / "rules" / name).is_file()


@functools.lru_cache(maxsize=8)
def _rule_file(name: str) -> dict:
    return _content(name)


def craft_of(doc_or_craft) -> str:
    """Which craft's rule rows answer for a document: an essence's are the enchanter's,
    any other material's the smith's, a herb's — on either shelf — the herbalist's. A
    craft id passes through (`ALCHEMIST` included: `lore(ALCHEMIST)`, `manuals(ALCHEMIST)`).

    An alchemist's reagent answers to the ALCHEMIST's rows (content/rules/alchemy-lore.json,
    alchemy lane F, 2026-10-06): an alchemist is its teacher and a library its record.
    Until then it answered to the smith's (lane A left the switch for the bench lane with
    this file), so a blacksmith taught camphor once lane D's pass gave it properties. A
    hybrid herb on the alchemy shelf is still a herb, and a healer still teaches it.

    A hide, tannin, oil, wax, thread or dye answers to the LEATHERWORKER's rows
    (content/rules/leatherworking-lore.json, leather lane F, 2026-10-08). Measured before:
    every one of the 140 leather materials answered to the smith's, so a blacksmith taught
    deer hide, a guildhall shelved it, and its Grade was the forge's assay (a tenth of a
    bar, compared against every known material of kind `hide`)."""
    if isinstance(doc_or_craft, str):
        return doc_or_craft if doc_or_craft in (BLACKSMITH, ENCHANTER, ALCHEMIST,
                                                LEATHERWORKER) else HERBALIST
    if is_essence(doc_or_craft):
        return ENCHANTER
    if not is_material(doc_or_craft) or _is_herb_view(doc_or_craft):
        return HERBALIST
    door = _door()
    fn = getattr(door, "is_alchemy", None) if door is not None else None
    if callable(fn) and isinstance(doc_or_craft, dict) and fn(doc_or_craft):
        return ALCHEMIST
    if is_leather(doc_or_craft):
        return LEATHERWORKER
    return BLACKSMITH


def is_leather(doc) -> bool:
    """A leatherworker's material, as the door judges it (`materials.is_leather`): the
    leather catalogue, or homebrew in one of the leather-only kinds."""
    door = _door()
    fn = getattr(door, "is_leather", None) if door is not None else None
    return bool(isinstance(doc, dict) and callable(fn) and fn(doc))


def lore(doc_or_craft=HERBALIST) -> dict:
    """The prices, times and DCs of learning, for this document's craft."""
    craft = craft_of(doc_or_craft)
    while craft in _LORE_FALLBACK and not _has_content(_LORE_FILES[craft]):
        craft = _LORE_FALLBACK[craft]
    return _rule_file(_LORE_FILES[craft])


@functools.lru_cache(maxsize=8)
def _manual_rows(craft: str) -> tuple:
    if not _has_content(_MANUAL_FILES[craft]):
        return ()
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
    """The normalised material document, or None. A form resolves to its parent, except
    an alchemist's form, which is its own document (`_own_store`): cinnabar is not
    quicksilver at the alchemist's bench, whatever it smelts to."""
    door = _door()
    if door is None:
        return None
    try:
        own = door.get(str(material_id or ""))
    except KeyError:
        own = None
    if own and _own_store(own):
        return own
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


def _is_herb_view(doc) -> bool:
    """A hybrid herb as the alchemy shelf serves it (`materials.herb_view`): a dict, so
    it is keyed as a material is, but the herb's own document underneath — its knowledge
    lives under the herb's id, its rows are the herbalist's, and a bare save gate in it
    guards its poison exactly as on the herb's card."""
    return isinstance(doc, dict) and doc.get("catalogue") == "ingredients"


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
    """The id knowledge is stored under: a material's parent, an ingredient's own id, and
    an alchemist's material its own id (`_own_store`)."""
    raw = str(_field(doc, "id", "") or "")
    if not is_material(doc) or _own_store(doc):
        return raw
    return material_of(raw)


def _own_store(doc) -> bool:
    """Whether a material keeps what is known of it under its OWN id, not its parent's.

    Every alchemist material and hybrid herb does. A forge form shares its parent's
    store because a form of mithral is mithral, read by mithral's lists; an alchemist's
    form is NOT read by its parent's lists — iron filings carry their own product traits,
    and iron its weapon and armour effects — and positional keys under one store would
    mean two documents' "p0" were one fact. Measured 2026-10-06 when the alchemist's
    lists joined `MATERIAL_LISTS`: of the 9 alchemist forms, iron filings and the iron
    flask would have shared "p0" (and, after lane D's working traits, "t0" with iron's own
    forge trait), and cinnabar would have shared "p0" with quicksilver, itself an
    alchemist reagent with an effect: the basilisk-eye collision again, one level down."""
    if not isinstance(doc, dict):
        return False
    if _is_herb_view(doc):
        return True
    door = _door()
    fn = getattr(door, "is_alchemy", None) if door is not None else None
    return bool(callable(fn) and fn(doc))


def is_essence(doc) -> bool:
    """An enchanter's essence: a material document of kind `essence` on the enchanter's
    shelf (lane D). The alchemist's catalogue also files camphor and oil of cloves under
    `essence`, and those are an alchemist's reagents, not the circle's: they keep the
    material keys they always had."""
    return (isinstance(doc, dict) and str(doc.get("kind") or "") == "essence"
            and str(doc.get("catalogue") or "enchanter-materials") == "enchanter-materials")


def essence_keys(doc: dict) -> list[str]:
    """An essence's trait keys, as lane D's door names them (`materials.essence_traits`),
    asked of the door when it serves them so the two can never disagree; the same rule
    here until it does (tests/test_enchant_knowledge.py holds the two to one answer)."""
    door = _door()
    fn = getattr(door, "essence_traits", None) if door is not None else None
    if callable(fn):
        try:
            return [str(k) for k in fn(doc)]
        except Exception:  # noqa: BLE001 - a door that cannot read it falls back
            pass
    out: list[str] = []
    if doc.get("grants"):
        out.append("grants")
    out.extend(f"house:{i}" for i, _ in enumerate(doc.get("house") or []))
    for fact in ("phase", "polarity", "affinity"):
        if doc.get(fact):
            out.append(fact)
    out.extend(f"working:{w.get('trait')}" for w in doc.get("working") or []
               if isinstance(w, dict))
    return out


def _essence_specs(doc: dict) -> list[tuple[str, dict, str]]:
    """(key, spec, group) per essence trait. A plain fact (what it binds, its phase, its
    polarity, its affinity) has no effect document, so it is carried as a small
    `essence_fact` spec the card and the classifier read; a house top-up is its own
    document and a working trait the circle's, as a metal's are the forge's."""
    out: list[tuple[str, dict, str]] = []
    house = [h for h in doc.get("house") or [] if isinstance(h, dict)]
    for key in essence_keys(doc):
        head, _, rest = key.partition(":")
        if head == "house":
            i = int(rest) if rest.isdigit() else -1
            if 0 <= i < len(house):
                out.append((key, house[i], "house"))
        elif head == "working":
            out.append((key, {"type": "working", "trait": rest}, "working"))
        elif head in _ESSENCE_FACTS:
            out.append((key, {"type": "essence_fact", "fact": head,
                              "value": copy.deepcopy(doc.get(head))}, head))
    return out


def _held_lists() -> frozenset:
    """The lists a standing rule holds back, read off the door each time (so a test, or
    the owner's decision, flips it in one place): `mark` while `materials.MARKS_HELD`.
    A door that does not say holds it: a mark is never shown by default."""
    door = _door()
    return frozenset(group for group, flag in _HOLDABLE.items()
                     if door is None or bool(getattr(door, flag, True)))


def _material_specs(doc: dict) -> list[tuple[str, dict, str]]:
    """(key, spec, group) per property, in key order."""
    if is_essence(doc):
        return _essence_specs(doc)
    out: list[tuple[str, dict, str]] = []
    held = _held_lists()
    for group, prefix in MATERIAL_LISTS:
        if group in held:
            continue
        raw = doc.get(group)
        if group in _SINGLE_LISTS:
            raw = [raw] if isinstance(raw, dict) else []
        for i, spec in enumerate(raw or ()):
            if isinstance(spec, dict):
                if group in ("mishap", "toxic") and spec.get("drawback") is not True:
                    # What a reagent does to the one working it is a cost whatever its
                    # type: a mishap that hastes nobody is still a mishap. Said on the
                    # spec, so every reader of the class (card, picks, teacher) agrees.
                    spec = dict(spec, drawback=True)
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
    head, sep, rest = k.partition(":")
    if head in ESSENCE_ORDER and (sep or head in _ESSENCE_FACTS):
        # An essence's keys, in the order a Read reveals them. Every key of one document
        # is of one kind, so these tuples are never compared with a herb's.
        return (10 + ESSENCE_ORDER.index(head), int(rest) if rest.isdigit() else 0)
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
    if kind == "essence_fact":
        # What an essence binds is why you would bind it; where it sits and what suits
        # it are what it is.
        return BENEFIT if spec.get("fact") == "grants" else NEUTRAL
    # An alchemist's product trait says outright when it is a cost to the user (alchemy
    # contracts §2.1, `drawback: true`), and says where it lands by its route: harm on the
    # struck foe or in the cloud is what the flask is FOR.
    if spec.get("drawback") is True:
        return DRAWBACK
    if str(spec.get("route") or "") in _FOE_ROUTES:
        return BENEFIT
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
    if not is_material(doc) or _is_herb_view(doc):
        # A herb on the alchemy shelf is the same herb: its loose gates guard the same
        # bodies, so a taste and an assay of it pick the same keys.
        index = {id(s): k for s, k in zip(specs, keys)}
        name = str(_field(doc, "name", "") or "")
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
    """The id knowledge lives under. A material form goes to its parent (an alchemist's
    material excepted: `_own_store`); anything else, an ingredient above all, is its own
    id — the door is only asked about materials."""
    raw = str(any_id or "")
    door = _door()
    if door is None or not hasattr(door, "material_of"):
        return raw
    try:
        known = door.get(raw)
    except KeyError:
        known = None
    return material_of(raw) if known and not _own_store(known) else raw


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
    if kind == "essence_fact":
        return _fact_line(spec)
    if kind == "working":
        trait = str(spec.get("trait") or spec.get("target") or "")
        # The smith's words, then the alchemist's (content/rules/alchemy-lore.json): a
        # trait's line does not know which shelf it came from, and the two lists share
        # only `pure`, which says the same thing in both.
        words = (lore(BLACKSMITH).get("working_words") or {}).get(trait) or \
            (lore(ALCHEMIST).get("working_words") or {}).get(trait)
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
        if is_essence(doc):
            row["group"] = key.partition(":")[0]
        elif is_material(doc):
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
        # An enchanting manual also teaches recipes (a catalogue item's making) and
        # property types (what Unbind would teach), each one fact under its own id.
        if row.get("recipe"):
            from . import magic_layer

            rid = str(row["recipe"])
            if magic_layer.recipe(rid) is not None:
                out.setdefault(rid, [])
                if RECIPE_KEY not in out[rid]:
                    out[rid].append(RECIPE_KEY)
            continue
        if row.get("property"):
            from . import effectspec

            pid = str(row["property"])
            if pid == "enhancement" or effectspec.property(pid) is not None:
                sid = property_store_id(pid)
                out.setdefault(sid, [])
                if TYPE_KEY not in out[sid]:
                    out[sid].append(TYPE_KEY)
            continue
        if row.get("material") or row.get("essence"):
            doc = material(str(row.get("material") or row.get("essence") or ""))
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
            keys = [k for k in a["keys"] if k.startswith("working:")
                    or (k.startswith("t") and not is_essence(doc))]
        else:
            keys = [str(k) for k in (want or ()) if str(k) in a["keys"]]
        if keys:
            did = doc_id(doc)
            out.setdefault(did, [])
            out[did] += [k for k in keys if k not in out[did]]
    return out


def read_manual(actor, manual: dict, *, clock: int) -> dict:
    """Read a manual the character holds (any craft's): what it teaches is learned, and a
    first reading is worth the craft's `manual.mastery` once (`Actor.manuals_read` keeps
    the record, as the herb bench's reader does). Returns {"revealed": {id: [new keys]},
    "minutes": the reading's hours, "first": bool, "mp": the mastery owed, "craft"}.
    The caller passes the minutes and pays the mastery on the craft's own track; this
    refuses nothing — whether the book is in hand is `holds_manual`, asked first.

    Written for the leatherworker's manuals (plan §16) so the leather bench's reader is
    one call: before it, only `play/herb_views.herb_manual` read a manual at all, and it
    reads herbal ones only (`herbknowledge.manual_named` is the herbalist's shelf)."""
    craft = str(manual.get("craft") or "") or next(
        (c for c in _MANUAL_FILES if str(manual.get("id")) in manuals(c)), HERBALIST)
    how = f"read in {manual.get('name') or manual.get('id')}"
    revealed: dict[str, list[str]] = {}
    for did, keys in manual_keys(manual).items():
        new = reveal(actor, did, keys, how)
        if new:
            revealed[did] = new
    read = getattr(actor, "manuals_read", None)
    first = isinstance(read, list) and str(manual.get("id")) not in read
    if first:
        read.append(str(manual.get("id")))
    mp = int(lore(craft).get("manual", {}).get("mastery", 0)) if first else 0
    return {"revealed": revealed, "minutes": int(manual.get("hours", 1) or 1) * 60,
            "first": first, "mp": mp, "craft": craft}


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
    entry = _entry(actor, _store_id(material_id))
    return bool(entry and entry.get("keys"))


def _assay_rules(doc) -> dict:
    """The assay's rule rows for this document's craft: the leatherworker's Grade
    (leatherworking-lore.json `grade`) for a leather material, the forge's `assay` for
    everything else, as it always was (the alchemist's assay is the forge's rows)."""
    if is_leather(doc):
        return lore(LEATHERWORKER)["grade"]
    return lore(BLACKSMITH)["assay"]


def _type_word(raw) -> str | None:
    """A stat block's creature type as the vocabulary spells it (`effectspec.
    CREATURE_TYPES`: "magical-beast"), or None. The two bestiary files spell it three
    ways: "magical beast", "advanced magical beast", and core.json's truncated "magical"
    (107 blocks) and "monstrous" (55) — measured 2026-10-08. A type contained in the words
    wins (longest first), then a type the words begin; anything else is no type."""
    from .effectspec import CREATURE_TYPES

    words = " ".join(re.findall(r"[a-z]+", str(raw or "").lower()))
    if not words:
        return None
    for t in sorted(CREATURE_TYPES, key=len, reverse=True):
        if f" {t.replace('-', ' ')} " in f" {words} ":
            return t
    for t in CREATURE_TYPES:
        if t.replace("-", " ").startswith(words):
            return t
    return None


def creature_type_of(creature) -> str | None:
    """A creature's type from its stat block, by bestiary id or name (`bestiary.
    raw_block`, the one resolver), or from a block or actor handed in. None when nothing
    names one."""
    if creature is None or creature == "":
        return None
    if isinstance(creature, dict):
        return _type_word(creature.get("creature_type"))
    if not isinstance(creature, str):
        tid = getattr(creature, "from_template", "") or getattr(creature, "template", "")
        return creature_type_of(str(tid or "")) if tid else None
    from . import bestiary

    said = creature.strip().lower()
    block = bestiary.raw_block(said) or bestiary.raw_block(
        "-".join(re.findall(r"[a-z0-9]+", said)))
    return _type_word((block or {}).get("creature_type"))


def hide_type(doc, creature=None) -> str | None:
    """The creature type a hide is compared under (plan §16: "−1 DC for each known hide
    of the same creature type"), or None.

    The hide's own `creature_type` first (the document's fact, as a World Bible hide
    states it); then the creature it was taken from, when the caller has one (a generic
    hide's stock record names its `creature`, contracts §4.1); then the first of its
    `from_creatures` the bestiary resolves. A generic hide with no creature named has no
    type: the catalogue's fur hide is every furred beast at once, so it is no reference
    for any one of them."""
    doc = resolve(doc)
    stated = _type_word(_field(doc, "creature_type", None))
    if stated:
        return stated
    got = creature_type_of(creature)
    if got:
        return got
    for name in _field(doc, "from_creatures", None) or ():
        got = creature_type_of(str(name))
        if got:
            return got
    return None


def _comparison_key(doc, creature=None) -> tuple[str, str | None]:
    """What an assay compares a document against: a hide by its creature type (plan §16,
    "keyed on type rather than kind"), anything else by its kind (the forge's touchstone
    rule, which a leather tannin or dye keeps: a known oak bark helps place a hemlock)."""
    if is_leather(doc) and str(_field(doc, "kind", "")) == "hide":
        return ("type", hide_type(doc, creature))
    return ("kind", str(_field(doc, "kind", "") or ""))


def assay_dc(doc, actor, creature=None) -> int:
    """The rarity DC (study's: 10 + 5 a band), less 1 for each OTHER material of the same
    kind the character knows, at most 4 off — a hide's of the same creature TYPE.

    Assaying is comparison (docs/blacksmithing-prior-art.md §3.8): a touchstone streak is
    read against needles of known fineness, and a spark against sparks you have seen, so
    every metal you know makes the next one easier to place. The cut is by kind (metal
    against metal, ore against ore) because a known fuel says nothing about a new alloy.
    A hide is graded against hides of its creature type (plan §16): a known wolf pelt
    says something about a dog's hide and nothing about a basilisk's. A hide with no type
    (`hide_type` None) is compared with nothing, never with every other untyped hide.
    `creature` is the creature a harvested hide came from, when the caller has it.
    """
    doc = resolve(doc)
    rules = _assay_rules(doc)
    base = study_dc(doc)
    sort, key = _comparison_key(doc, creature)
    if key is None:
        return base
    me = doc_id(doc)
    everything = all_materials()
    same = 0
    for mid, entry in (getattr(actor, "herb_known", None) or {}).items():
        if mid.startswith("_") or mid == me or not (isinstance(entry, dict) and entry.get("keys")):
            continue
        other = everything.get(mid) or material(mid)
        if other is None:
            continue
        if sort == "type":
            if str(_field(other, "kind", "")) == "hide" and is_leather(other) \
                    and hide_type(other) == key:
                same += 1
        elif str(_field(other, "kind", "")) == key:
            same += 1
    cut = min(int(rules["comparison_max"]), int(rules["comparison_per_known"]) * same)
    return max(0, base - cut)


def assay_cost(doc) -> dict:
    """A sliver: one ore, or a tenth of a bar (bars track tenths), the owner's ruling. A
    leather material's is a scrap: a quarter unit of hide (hides track quarters,
    contracts §4.1), or a quarter measure of a tannin, oil, wax, thread or dye (plan §16:
    "a quarter unit, or an offcut from any earlier step")."""
    if is_leather(doc):
        return {"units": float(lore(LEATHERWORKER)["grade"]["scrap_units"])}
    rules = lore(BLACKSMITH)["assay"]
    kind = str(_field(doc, "kind", "") or "")
    form = str(_field(doc, "form", "") or "")
    if kind == "ore" or form == "ore":
        return {"ore": int(rules["ore_sliver"])}
    if _is_alchemy(doc):
        # Alchemy plan §13.2: "a pinch (a tenth of a unit, tracked as tenths, as the
        # forge's slivers are)" — the sliver's own row, under the alchemist's word.
        return {"pinch": float(rules["bar_sliver"])}
    return {"bars": float(rules["bar_sliver"])}


def _is_alchemy(doc) -> bool:
    door = _door()
    fn = getattr(door, "is_alchemy", None) if door is not None else None
    return bool(callable(fn) and fn(doc))


def _assay_doc(material_id: str):
    """What an assay reads: a material through the door, else a hybrid herb off the
    alchemy shelf — an alchemist assays a basilisk eye as readily as brimstone, and what
    it teaches is the herb's own keys (one document, two shelves)."""
    doc = material(material_id)
    if doc is None:
        door = _door()
        fn = getattr(door, "alchemy_doc", None) if door is not None else None
        doc = fn(material_id) if callable(fn) else None
    return doc


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
    if not is_reactive(doc) or is_leather(doc):
        # No hide bites back when it is graded (the owner, 2026-10-08, open point 10:
        # "dangerous hides should not bite they should force another round of checks ...
        # while skinning"): a dangerous body is the harvest's second check, never Grade's.
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


def assay(actor, material_id: str, total: int, *, clock: int, creature=None) -> dict:
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
    doc = _assay_doc(material_id)
    if doc is None:
        raise KeyError(f"no material called {material_id!r}")
    mid = doc_id(doc)
    rules = _assay_rules(doc)
    dc = assay_dc(doc, actor, creature)
    margin = int(total) - dc
    success = margin >= 0
    found = danger_of(doc)
    meet(actor, mid)
    revealed: list[str] = []
    if success:
        landed = {found[0]} if found else set()
        verb = "graded" if is_leather(doc) else "assayed"
        revealed = reveal(actor, mid, reveal_picks(actor, doc, landed=landed),
                          f"{verb}, day {day_of(clock)}")
    return {"material": mid, "dc": dc, "total": int(total), "success": success,
            "margin": margin, "revealed": revealed, "cost": assay_cost(doc),
            "minutes": int(rules["minutes"]),
            "danger": found[1] if found else None,
            # What the bench pays for it (`worldclass.STUDY_MP` a property found, 0 for
            # none: the owner, 2026-10-06), said here so every bench pays one number.
            "mp": _study_mp() * len(revealed)}


def _study_mp() -> int:
    from . import worldclass

    return int(getattr(worldclass, "STUDY_MP", 1))


def grade(actor, material_id: str, total: int, *, clock: int, creature=None) -> dict:
    """The leatherworker's Grade (plan §16): the assay in leather words. A scrap (a
    quarter unit) and ten minutes, a Craft roll at the material's rarity DC less 1 for
    each known hide of the same creature type (at most 4), and a success reveals one
    benefit and one drawback. No danger: no hide bites back when graded (the owner's
    answer 10). `creature` is the creature the graded hide came from, when the bench
    knows it (a generic hide's stock record carries it).

    Resolves on a total already rolled, as `assay` does; the bench takes the scrap
    (`cost`), passes the minutes and pays `mp` — `worldclass.STUDY_MP` for each property
    found, 0 when nothing was. Raises KeyError for an id no shelf holds, and ValueError
    for a material that is not the leatherworker's (an iron bar is assayed at the forge,
    never graded)."""
    doc = _assay_doc(material_id)
    if doc is None:
        raise KeyError(f"no material called {material_id!r}")
    if not is_leather(doc):
        raise ValueError(f"{_field(doc, 'name', material_id)} is not a leatherworker's "
                         f"material: assay it at the forge instead.")
    return assay(actor, material_id, total, clock=clock, creature=creature)


def apply_danger(engine, actor, material_id: str, effect: dict | None,
                 because: str = "", *, origin: str = "", name: str = "") -> list:
    """Run an assay's danger through the engine, as the taste op runs a herb's raw effect:
    the spec becomes ordinary intents (`consumables.document_intents`), validated with
    `origin item:<material id>` (or the caller's `origin`: the alchemy bench stamps
    `rule:mishap:<material>` and `rule:toxic:<material>`, contracts §7) so immunity and
    every other gate apply, and run. The ONE door a handling hazard takes: the alchemy
    bench's `alchemist.apply_rule` calls it rather than keeping a private copy (law 2).

    Not the drink door. Until 2026-10-07 this went through `consumables.plan(how="drink")`,
    which keeps only what works when swallowed, and a toxic document is a save gate whose
    route is nobody's mouth: all 18 alchemy toxic documents came back "nothing in
    Quicksilver works when swallowed" and applied nothing here, which is why lane F wrote
    its own applicator beside this one. (The condition
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
    name = name or str(doc.get("name") or mid)
    spec = {k: v for k, v in dict(effect).items() if k not in ("recipient", "note")}
    if str(spec.get("type") or "") == "suppress_magic":
        return [_suppress_magic(engine, actor, mid, name, spec, because)]
    made = [dict(i, visibility="hidden") for i in consumables.document_intents(
        [spec], actor.ref, because or f"assaying {name}", name)]
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
        res = engine.run(engine.validate(made, origin=origin or f"item:{mid}",
                                         origin_name=name))
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


def alchemy_codex(actor) -> list[dict]:
    """The alchemist's reagent ledger (alchemy plan §13.3, "3 of 7 known"): every
    document on the alchemy shelf the character has met — known of, or carried — as the
    smith's ledger rows, by kind then name. A hybrid herb tasted at the herb bench is
    here with what the taste taught, because it is one document (plan §13.2)."""
    door = _door()
    fn = getattr(door, "alchemy_shelf", None) if door is not None else None
    if not callable(fn):
        return []
    shelf = fn()
    by_name = {str(d.get("name", "")).lower(): mid for mid, d in shelf.items()}
    # A form's knowledge is stored under its parent (mithral dust's under mithral), so a
    # store id leads back to the shelf entries that are forms of it.
    by_store: dict[str, list[str]] = {}
    for mid, d in shelf.items():
        by_store.setdefault(doc_id(d), []).append(mid)
    met: list[str] = [k for k in (getattr(actor, "herb_known", None) or {})
                      if not str(k).startswith("_")]
    met += [k for k, n in (getattr(actor, "inventory", None) or {}).items() if n]
    for s in (getattr(actor, "stock", None) or {}).values():
        base = str(getattr(s, "base", "") or "").lower()
        if int(getattr(s, "count", 0) or 0) > 0:
            met.append(base if base in shelf else by_name.get(base, ""))
    rows, seen = [], set()
    for raw in met:
        for mid in ([raw] if raw in shelf else by_store.get(str(raw), [])):
            if mid in seen:
                continue
            seen.add(mid)
            # The row is the shelf's entry (mithral dust, not mithral); `store` is where
            # what is known of it lives.
            row = ledger_row(actor, shelf[mid])
            rows.append(dict(row, id=mid, store=row["id"],
                             hybrid=bool(shelf[mid].get("hybrid"))))
    return sorted(rows, key=lambda r: (r["kind"], r["name"].lower()))


# --- the enchanter: essences, items and unbinding (enchanting plan §12-13; contracts §7) -----
#
# Still one store. An essence's traits live under its own id, as a metal's do; a recipe (a
# catalogue item's making) under its recipe id; a property TYPE (what Unbind teaches) under
# "property:<id>" — a colon no material, herb or recipe id can carry (lowercase letters,
# digits, hyphens), so the third id space cannot collide with the other two.
#
# What is known about one ITEM lives on the item (`magic.known`, lane B's field), not on
# the character: two longswords off one rack are two items, and identifying one says
# nothing about the other.

RECIPE_KEY = "recipe"
TYPE_KEY = "type"
PROPERTY_PREFIX = "property:"


def property_store_id(property_id: str) -> str:
    """Where knowledge of a property type is kept in `Actor.herb_known`."""
    return PROPERTY_PREFIX + str(property_id or "").strip().lower()


def _knows(actor, store_id: str, key: str) -> bool:
    entry = _entry(actor, store_id) or {}
    return key in set(entry.get("keys") or ())


def _learn(actor, store_id: str, key: str, how: str) -> bool:
    """Record one fact; True when it was new. The herb store's own `reveal`, so the
    Journal, the bench and the narrator read one answer."""
    return bool(reveal(actor, store_id, [key], how))


def knows_property(actor, property_id: str) -> bool:
    """Whether the character knows this property type (Unbind, a manual, a teacher).
    "enhancement" is a type too: unbinding a +2 sword teaches that a blade can take one,
    never how much (Skyrim: "the magnitude is irrelevant", prior art §5.3)."""
    return _knows(actor, property_store_id(property_id), TYPE_KEY)


def learn_property(actor, property_id: str, how: str) -> bool:
    return _learn(actor, property_store_id(property_id), TYPE_KEY, how)


def known_properties(actor) -> list[str]:
    """Every property type the character knows, sorted."""
    out = []
    for sid, entry in (getattr(actor, "herb_known", None) or {}).items():
        if str(sid).startswith(PROPERTY_PREFIX) and TYPE_KEY in set(
                (entry or {}).get("keys") or ()):
            out.append(str(sid)[len(PROPERTY_PREFIX):])
    return sorted(out)


def knows_recipe(actor, recipe_id: str) -> bool:
    return _knows(actor, str(recipe_id or ""), RECIPE_KEY)


def learn_recipe(actor, recipe_id: str, how: str) -> bool:
    return _learn(actor, str(recipe_id or ""), RECIPE_KEY, how)


# --- the alchemist: formulae, potions and the codex (alchemy contracts §4-§5) ---------------
#
# Still one store. A formula is kept under "formula:<id>" — the property type's colon
# trick, so a formula id can never be read as a material, a herb or a recipe — with one
# key, "formula". Lane E's `formulae.known` and `formulae.learn` read and write through
# these and never keep a second list (contract §4).

FORMULA_PREFIX = "formula:"
FORMULA_KEY = "formula"
POTION_PREFIX = "potion:"
IDENTIFIED_KEY = "identified"
# The book's number, used until an alchemy lore file states it as a rule row
# (`identify_potion.dc_base`). The CRB disagrees with itself on what is added to it,
# checked 2026-10-06: the Potions page says "15 + the spell level of the potion"
# (legacy.aonprd.com/coreRulebook/magicItems/potions.html), the Perception table says
# "15 + the potion's caster level" (.../skills/perception.html). The contract (alchemy
# contracts §4, plan §11.3) takes the Potions page, the rule written for potions; the
# owner has not been asked to choose, and the report says so.
POTION_IDENTIFY_DC = 15


def formula_store_id(formula_id: str) -> str:
    """Where knowledge of a formula is kept in `Actor.herb_known`."""
    return FORMULA_PREFIX + str(formula_id or "").strip().lower()


def knows_formula(actor, formula_id: str) -> bool:
    return _knows(actor, formula_store_id(formula_id), FORMULA_KEY)


def learn_formula(actor, formula_id: str, how: str) -> bool:
    """Record a formula as known, and how ("experiment, day 4", "copied from a
    spellbook"). True when it was new — the caller's cue to pay mastery for a first."""
    return _learn(actor, formula_store_id(formula_id), FORMULA_KEY, how)


def known_formulae(actor) -> list[str]:
    """Every formula id the character knows, sorted."""
    out = []
    for sid, entry in (getattr(actor, "herb_known", None) or {}).items():
        if str(sid).startswith(FORMULA_PREFIX) and FORMULA_KEY in set(
                (entry or {}).get("keys") or ()):
            out.append(str(sid)[len(FORMULA_PREFIX):])
    return sorted(out)


def formula_how(actor, formula_id: str) -> str:
    """How the character came to know a formula, or "" when they do not."""
    entry = _entry(actor, formula_store_id(formula_id)) or {}
    return str((entry.get("how") or {}).get(FORMULA_KEY) or "")


def _potion_spell_level(stock) -> int | None:
    """A potion's spell level: what its own row says, else the authored spell potion's
    row for its spell, else the spell's lowest level on any list (the level a brewer
    could have made it at). None when it holds no spell."""
    sid = str(getattr(stock, "holds_spell", None) or "")
    if not sid:
        return None
    own = getattr(stock, "spell_level", None)
    if isinstance(own, int):
        return own
    try:
        from django.conf import settings

        path = Path(settings.BASE_DIR) / "content" / "materials" / \
            "alchemist-spell-potions.json"
        for row in json.loads(path.read_text(encoding="utf-8")).get("potions") or ():
            if str(row.get("spell") or "") == sid and row.get("spell_level") is not None:
                return int(row["spell_level"])
    except (OSError, ValueError, TypeError):
        pass
    try:
        from . import spells

        return spells.get(sid).min_level
    except (KeyError, ImportError):
        return None


def potion_identify_dc(stock) -> int:
    """DC 15 + the potion's spell level (alchemy plan §11.3: the book's Perception DC to
    identify a potion, which the APG alchemist reads with his own skill). A product that
    holds no spell is the DC with nothing added."""
    rules = lore(ALCHEMIST).get("identify_potion") or {}
    base = int(rules.get("dc_base", POTION_IDENTIFY_DC))
    return base + int(_potion_spell_level(stock) or 0)


def potion_known(actor, stock) -> bool:
    """Whether the character has identified potions of this kind. Kept per stock id (a
    stack's id is a digest of what the thing IS: `crafting.Stock.id`), so a second vial
    from the same brewing needs no second check, and a different brewing does."""
    sid = str(getattr(stock, "id", "") or "")
    return bool(sid) and _knows(actor, POTION_PREFIX + sid, IDENTIFIED_KEY)


def identify_potion(actor, stock, total: int, *, clock: int | None = None) -> dict:
    """Identify a potion on a total already rolled (alchemy contracts §4; plan §11.3).

    The check is the alchemist's own, holding the vial for a round; no natural 20 (a skill
    check, CRB p.180). Success reveals what the potion IS — its spell and caster level, or
    a house product's name — and is remembered (`potion_known`); it does NOT teach the
    formula, which is the potion-in-hand route of lane E (plan §10.4). A miss teaches
    nothing; the book sets no wait on this check, and each try costs the round.

    {"dc", "total", "margin", "success", "spell": id | None, "spell_level": int | None,
     "caster_level": int | None, "name": str | None, "rounds": 1, "repeat": bool}
    Nothing about the potion is in the answer on a miss: it goes to the page."""
    dc = potion_identify_dc(stock)
    margin = int(total) - dc
    success = margin >= 0
    repeat = potion_known(actor, stock)
    out = {"dc": dc, "total": int(total), "margin": margin, "success": success,
           "spell": None, "spell_level": None, "caster_level": None, "name": None,
           "rounds": 1, "repeat": repeat}
    if not success:
        return out
    sid = str(getattr(stock, "id", "") or "")
    if sid:
        how = f"identified, day {day_of(clock)}" if clock is not None else "identified"
        _learn(actor, POTION_PREFIX + sid, IDENTIFIED_KEY, how)
    spell = str(getattr(stock, "holds_spell", None) or "") or None
    return dict(out, spell=spell,
                spell_level=_potion_spell_level(stock) if spell else None,
                caster_level=getattr(stock, "caster_level", None) if spell else None,
                name=str(getattr(stock, "base", "") or "") or None)


# --- essences --------------------------------------------------------------------------------

_POLARITY_WORDS = {"weapon": "Seats in a weapon", "armour": "Seats in armour or a shield",
                   "ward": "Seats in a ward: a ring, a cloak, a belt",
                   "any": "Seats in any vessel"}


def _fact_line(spec: dict) -> str:
    """An essence fact as a card line, built from the documents (never authored prose)."""
    fact = str(spec.get("fact") or "")
    value = spec.get("value")
    if fact == "grants":
        g = value if isinstance(value, dict) else {}
        if g.get("property"):
            from . import effectspec

            prop = effectspec.property(str(g["property"])) or {}
            name = str(prop.get("name") or str(g["property"]).replace("-", " "))
            if g.get("bonus") is not None:
                name += f" +{g['bonus']}"
            choice = g.get("choice") or {}
            if choice:
                name += " (" + ", ".join(str(v).replace("-", " ")
                                         for v in choice.values()) + ")"
            return f"Binds {name}"
        if g.get("enhancement"):
            return f"Binds a +{int(g['enhancement'])} enhancement"
        if g.get("power"):
            from . import magic_layer

            r = magic_layer.recipe(str(g["power"])) or {}
            return f"Binds the power of {r.get('name') or g['power']}"
        return "Binds nothing of its own"
    if fact == "phase":
        return f"Favours {value}"
    if fact == "polarity":
        return _POLARITY_WORDS.get(str(value), f"Seats in {value}")
    if fact == "affinity":
        names = []
        for mid in value or ():
            doc = material(str(mid)) or {}
            names.append(str(doc.get("name") or str(mid).replace("-", " ")))
        return "Takes to " + ", ".join(names) if names else "Takes to nothing in particular"
    return fact


def essence(essence_id: str) -> dict | None:
    """An essence's document through the one door, or None (and None for a material that
    is not an essence)."""
    doc = material(essence_id)
    return doc if is_essence(doc) else None


def essence_danger(doc) -> tuple[str, dict] | None:
    """(key, effect) a Read of a volatile essence applies, or None (plan §7.3: "reading it
    applies its house drawback for an hour, the forge's reactive-assay shape").

    The essence's OWN first house drawback, never a hazard invented for the bench: a
    volatile phial with no drawback is safe to read. Its trigger and bookkeeping do not
    travel; the hour comes from content/rules/enchanting-lore.json."""
    if not is_essence(doc):
        return None
    if not any(isinstance(w, dict) and w.get("trait") == "volatile"
               for w in doc.get("working") or ()):
        return None
    for key, spec, group in _essence_specs(doc):
        if group == "house" and is_drawback(spec):
            effect = {k: v for k, v in spec.items()
                      if k not in ("trigger", "house", "book", "when", "recipient")}
            effect["duration"] = dict(lore(ENCHANTER)["read"]["danger_duration"])
            return key, effect
    return None


def read(actor, essence_id: str, total: int, *, clock: int) -> dict:
    """Read a pinch of an essence (plan §10, §12.3): the herb rule, one benefit and one
    drawback where there is one, on a total already rolled (no natural 20: a skill check,
    CRB p.180). The pinch and the ten minutes are spent either way (the bench takes them:
    `cost`, `minutes`), and a volatile phial's danger lands whatever the roll — the
    handling bites, not the reading — through `apply_danger`, which runs it through the
    one applicator with its tell (laws 2 and 3). A miss teaches nothing and waits for no
    rest: each try costs a pinch, which is its own limit (the assay's rule)."""
    doc = essence(essence_id)
    if doc is None:
        raise KeyError(f"no essence called {essence_id!r}")
    rules = lore(ENCHANTER)["read"]
    eid = doc_id(doc)
    dc = study_dc(doc)
    margin = int(total) - dc
    success = margin >= 0
    found = essence_danger(doc)
    meet(actor, eid)
    revealed: list[str] = []
    if success:
        landed = {found[0]} if found else set()
        revealed = reveal(actor, eid, reveal_picks(actor, doc, landed=landed),
                          f"read, day {day_of(clock)}")
    return {"essence": eid, "dc": dc, "total": int(total), "success": success,
            "margin": margin, "revealed": revealed,
            "cost": {"phial": float(rules["pinch"])}, "minutes": int(rules["minutes"]),
            "danger": found[1] if found else None}


def attuned(actor, essence_id: str, *, clock: int) -> list[str]:
    """Seating an essence at Attune shows where it sits and when it favours (plan §12.3:
    "an unknown essence's polarity and planet show when it is seated" — the planet is a
    phase of the day now, owner round 4 point 10). Returns the keys that were new."""
    doc = essence(essence_id)
    if doc is None:
        return []
    keys = [k for k in property_keys(doc) if k in ("polarity", "phase")]
    return reveal(actor, doc_id(doc), keys, f"attuned it, day {day_of(clock)}")


def bound(actor, essence_id: str, *, clock: int) -> list[str]:
    """Binding an essence shows what it binds (plan §12.3; ESO's translate-by-use, prior
    art §5.3). Returns the keys that were new."""
    doc = essence(essence_id)
    if doc is None:
        return []
    keys = [k for k in property_keys(doc) if k == "grants"]
    return reveal(actor, doc_id(doc), keys, f"bound it, day {day_of(clock)}")


# --- items -----------------------------------------------------------------------------------

def _item_record(item) -> dict | None:
    """The record dict that holds `magic`: a record, or a forged shelf entry's record."""
    if isinstance(item, dict):
        return item
    rec = getattr(item, "record", None)
    return rec if isinstance(rec, dict) and rec else None


def _live_magic(item) -> dict | None:
    """The item's OWN `magic` dict (never a copy), so what is learned stays on the item:
    a record's field, a forged entry's record's field, or a plain Stock's `magic`."""
    rec = _item_record(item)
    magic = rec.get("magic") if rec is not None else getattr(item, "magic", None)
    return magic if isinstance(magic, dict) else None


def _as_record(item) -> dict:
    rec = _item_record(item)
    if rec is not None:
        return rec
    return {"id": str(getattr(item, "id", "") or ""), "name": str(getattr(item, "name", "")
                                                                    or ""),
            "slot": getattr(item, "slot", None), "magic": getattr(item, "magic", None)}


def find_item(actor, item_id: str):
    """The shelf entry an id names: the shelf key, the entry's id, or its record's id."""
    want = str(item_id or "")
    for key, s in (getattr(actor, "stock", None) or {}).items():
        rec = _item_record(s) or {}
        if want in (str(key), str(getattr(s, "id", "") or ""), str(rec.get("id") or "")):
            return s
    return None


def _resolve_item(actor, item):
    if isinstance(item, str):
        found = find_item(actor, item)
        if found is None:
            raise KeyError(f"no item called {item!r}")
        return found
    return item


def identify_dc(item) -> int:
    """DC 15 + the item's caster level (CRB Spellcraft), for the roll mat's terms."""
    from . import magic_layer

    rec = _as_record(item)
    cl = magic_layer.caster_level(magic_layer.magic_of(rec), magic_layer.vessel_kind(rec))
    return int(lore(ENCHANTER)["identify"]["dc_base"]) + int(cl)


def identify(actor, item, total: int, *, day: int) -> dict:
    """Identify an item on a total already rolled (contracts §7; plan §12.1).

    The book, graded: fail, nothing ("try again tomorrow"); succeed, the INTENT — every
    property, its plus, its powers — and a catalogue item's recipe joins what the
    character knows; beat the DC by 10, the curse too ("unless the check made to identify
    the item exceeds the DC by 10 or more, the curse is not detected", CRB). Once per item
    per day: a second try that day returns the first answer ("additional attempts reveal
    the same results", CRB Spellcraft) and learns nothing new.

    Writes what was learned onto the item's own `magic.known` (in place: pass the stored
    record or shelf entry) and the recipe into `Actor.herb_known`.

    {"result": "fail" | "intent" | "curse", "learned": [...], "recipe": id | None,
     "dc", "total", "margin", "again_on_day", "cursed": bool | None, "curse": words | None,
     "repeat": bool}

    `result: "curse"` means the curse check was passed: `cursed` then says whether there
    is one and `curse` its words. Below that both are None, whatever the item carries —
    this answer goes to the page. A plain item answers `result: "none"`.
    """
    from . import curses, magic_layer

    item = _resolve_item(actor, item)
    rec = _as_record(item)
    magic = _live_magic(item)
    day = int(day)
    if magic is None or not magic_layer.has_layer(dict(rec, magic=magic)):
        return {"result": "none", "learned": [], "recipe": None, "dc": 0,
                "total": int(total), "margin": 0, "again_on_day": day, "cursed": None,
                "curse": None, "repeat": False}
    known = magic.setdefault("known", {})
    tried = known.get("tried")
    if isinstance(tried, dict) and tried.get("day") == day and isinstance(
            tried.get("answer"), dict):
        return dict(tried["answer"], learned=[], repeat=True)
    rules = lore(ENCHANTER)["identify"]
    dc = identify_dc(dict(rec, magic=magic))
    margin = int(total) - dc
    learned: list[str] = []
    recipe = None
    cursed = None
    words = None
    curse = curses.curse_of({"magic": magic})
    how = f"identified, day {day}"
    if margin < 0:
        result = "fail"
    else:
        result = "intent"
        if not known.get("intent"):
            known["intent"] = True
            learned.append("intent")
        if not known.get("how"):
            known["how"] = how
        for p in magic.get("powers") or ():
            rid = str((p or {}).get("recipe") or "")
            if rid and learn_recipe(actor, rid, how) and recipe is None:
                recipe = rid
        if margin >= int(rules["curse_margin"]):
            result = "curse"
            if not known.get("curse"):
                known["curse"] = True
                if curse:
                    learned.append("curse")
            cursed = bool(curse)
            words = curses.describe(curse) if curse else None
    answer = {"result": result, "recipe": recipe, "dc": dc, "total": int(total),
              "margin": margin, "again_on_day": day + 1, "cursed": cursed, "curse": words}
    known["tried"] = {"day": day, "answer": dict(answer)}
    return dict(answer, learned=learned, repeat=False)


def learn_by_use(actor, item, key: str) -> bool:
    """The hard way (plan §12.2): the first time a property fires in play it is known, and
    the first time a curse's clause bites (a daily save, a gutter, a refusal to be put
    down) the curse is known. `item` is the shelf entry, the record or its id; `key` is
    "curse", "intent" or a property id. True when it was new — the caller's cue to tell
    the moment with `curses.tell(..., known=True)`. The engine (lane C) calls this."""
    item = find_item(actor, item) if isinstance(item, str) else item
    magic = _live_magic(item) if item is not None else None
    if magic is None:
        return False
    known = magic.setdefault("known", {})
    if key == "curse":
        if known.get("curse") or not (isinstance(magic.get("curse"), dict)
                                       and magic["curse"].get("row")):
            return False
        known["curse"] = True
        known["curse_how"] = "found the hard way"
        return True
    if key == "intent":
        if known.get("intent"):
            return False
        known["intent"] = True
        known.setdefault("how", "found by use")
        return True
    if known.get("intent"):
        return False
    props = known.setdefault("properties", [])
    if key in props:
        return False
    props.append(str(key))
    return True


def unbind(actor, record, *, clock: int | None = None) -> dict:
    """Unbind a magic item (plan §13; owner round 4 Q6): the layer comes off whole, the
    smith's item stays, and the character learns the TYPES of property it carried — never
    their size ("the magnitude is irrelevant", Skyrim) — and its recipe if it was one. A
    quarter of the layer's motes come back as residue, rounded down. A curse goes with the
    layer: the cheap cure, whose price is the layer.

    Returns {"record": the stripped record, "learned": [new property types],
             "types": [every type], "recipe": first new recipe | None, "recipes": [...],
             "motes": the layer's motes, "residue": {"arcane-residue": n}}.
    Pure on the record (the bench stores the one returned); the knowledge is written to
    `Actor.herb_known`. Whether the unbinding succeeded is the bench's roll (lane E):
    call this on a success."""
    from . import magic_layer

    rec = _as_record(record)
    gear = magic_layer.vessel_kind(rec)
    m = magic_layer.magic_of(rec)
    stripped, _ = magic_layer.strip(rec)
    rules = lore(ENCHANTER)["unbind"]
    types: list[str] = []
    if m["enhancement"] and gear in magic_layer.ARMS:
        types.append("enhancement")
    for e in m["properties"] + m["flat"]:
        pid = str(e.get("id") or "")
        if pid and pid not in types:
            types.append(pid)
    recipes = [str(p.get("recipe")) for p in m["powers"] if p.get("recipe")]
    how = f"unbound, day {day_of(clock)}" if clock is not None else "unbound"
    learned = [t for t in types if learn_property(actor, t, how)]
    recipe = None
    for rid in recipes:
        if learn_recipe(actor, rid, how) and recipe is None:
            recipe = rid
    gp = magic_layer.market_price(m, gear, str(rec.get("slot") or ""))
    motes = int(math.ceil(gp * magic_layer.MAKING_FRACTION / magic_layer.GP_PER_MOTE - 1e-9))
    residue = int(math.floor(motes * float(rules["residue_fraction"]) + 1e-9))
    return {"record": stripped, "learned": learned, "types": types, "recipe": recipe,
            "recipes": recipes, "motes": motes, "residue": {str(rules["residue"]): residue}}


def item_card(item) -> dict:
    """What the item card may show of the layer (plan §12.4), and nothing it may not.

    Unidentified: the aura's strength and schools (detect magic shows those before
    anything is identified). Identified: what the maker intended — every property and
    power, believed (`magic_layer.layer(..., believed=True)`), marked "as the maker
    intended" until the curse check is passed. The curse's words only once it is known.
    """
    from . import curses, effectspec, magic_layer

    rec = _as_record(item)
    magic = _live_magic(item) or {}
    whole = dict(rec, magic=magic)
    if not magic_layer.has_layer(whole):
        return {"magic": False}
    m = magic_layer.magic_of(whole)
    gear = magic_layer.vessel_kind(whole)
    known = m.get("known") or {}
    lay = magic_layer.layer(whole, believed=True)
    out = {"magic": True, "aura": lay["aura"], "schools": list(lay["schools"]),
           "identified": bool(known.get("intent")),
           "flawed": bool(known.get("flawed")),
           "curse": None, "clings": False}
    if known.get("intent"):
        lines = []
        if m["enhancement"] and gear in magic_layer.ARMS:
            lines.append(f"+{m['enhancement']} enhancement")
        for e in m["properties"] + m["flat"]:
            try:
                lines.extend(effectspec.property_lines(str(e.get("id")), e.get("choice")))
            except Exception:  # noqa: BLE001 - a property the table lost still shows its id
                lines.append(str(e.get("id")))
        for p in m["powers"]:
            r = magic_layer.recipe(str(p.get("recipe") or "")) or {}
            lines.append(str(r.get("name") or p.get("recipe")))
        out["lines"] = lines
        out["caster_level"] = lay["caster_level"]
        out["as_intended"] = not known.get("curse")
    else:
        out["learned_by_use"] = [str(p) for p in known.get("properties") or ()]
    if known.get("curse"):
        c = curses.curse_of(whole)
        out["curse"] = curses.describe(c) if c else "none"
        out["clings"] = bool(c and curses.clings(whole))
    return out
