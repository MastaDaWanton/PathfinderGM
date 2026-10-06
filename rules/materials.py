"""The one door to every craft material: what it is, what it does, and whether it is sound.

`content/materials` is one shelf shared by four crafts (blacksmith, alchemist, enchanter,
leatherworker), and before this module each craft read it through its own loader in its
own dialect. Nothing here replaces those loaders yet (contract §3): this reads the same
files, normalises every entry into one document shape with every field defaulted, so a
file written before the forge revamp still loads, and serves the forge's questions.

Two ideas hold it together, both the owner's rulings (docs/blacksmithing-revamp-plan.md §2):

**One material, many shelves.** Mithral is one document. The leatherworker's mithral
fittings, the enchanter's mithral filings and the alchemist's mithral dust are *forms* of
it: each carries `"material": "mithral"` and keeps its own id (tests/test_alchemy_shelf.py
pins that no id is claimed twice — by two catalogues, or by a catalogue and the herb
corpus — and a merge would have broken four benches). `material_of` walks
the link; the parent's `forms` lists every shelf it appears on, computed here rather than
written into the parent, so a new form can never leave a stale list behind.

**Two layers.** A forge material carries *item effects* (`weapon`, `armour`: what the
finished piece does, typed and executable) and *working traits* (`working`: how it
behaves at the anvil). Book numbers carry `"book": true` and are applied from the main
piece only, never scaled (plan §6.3). Measured before the pass: 40 of the 63 material
effects were `narrative` prose nothing could execute, and no material had 3 discoverable
traits. `validate` refuses both, with the fix named, the way `effectspec.validate` does.

The legacy flat `effects` list stays in the files because `rules/blacksmith.py` still
reads it until its bench moves to this door; it is passed through untouched and is not
part of what `validate` judges.
"""
from __future__ import annotations

import builtins
import copy
import json
import re
from pathlib import Path

from . import effectspec
from .worldclass import TIERS
from pathfindergm import files

# The four shipped catalogues this door reads, by file stem. Not the whole folder: the
# folder also holds the alchemist's spell potions and the magic-item table, which are
# products, not materials, and a door that read them would answer "is a potion of cure
# light wounds a material?" with yes.
CATALOGUES = ("blacksmith-materials", "alchemist-materials", "enchanter-materials",
              "leatherworker-materials")
FORGE_CATALOGUE = "blacksmith-materials"
# The alchemist's shelf (docs/alchemy-contracts.md §3, plan §5.7): its own catalogue plus
# every hybrid herb, which is served through this door under the catalogue name
# `HERB_CATALOGUE` — one document on two shelves, never a copy in this folder.
ALCHEMY_CATALOGUE = "alchemist-materials"
HERB_CATALOGUE = "ingredients"
# The alchemist's eight kinds (plan §5.1: reagent 46, gland 23, solvent 16, vessel 13,
# salt 11, treatment 11, essence 10, catalyst 9). Two are shared with other crafts'
# kinds — the forge's `treatment`, the enchanter's `essence` — so a homebrew entry with no
# catalogue is the alchemist's by kind only for the six that are nobody else's.
ALCHEMY_KINDS = ("reagent", "gland", "solvent", "vessel", "salt", "treatment", "essence",
                 "catalyst")
_ALCHEMY_ONLY_KINDS = ("reagent", "gland", "solvent", "vessel", "salt", "catalyst")

# The eight forge kinds. Fixed: tests/test_blacksmith.py pins them, and a typo'd kind
# would load and then never count as fuel or metal anywhere.
KINDS = ("ore", "metal", "alloy", "fuel", "flux", "quenchant", "fitting", "treatment")
STRUCTURAL = ("metal", "alloy", "fitting")
CONSUMABLE = ("fuel", "flux")          # working traits only (the owner's ruling)
GEARS = ("weapon", "armour")
PIECES = {"weapon": ("head", "haft", "fittings"),
          "armour": ("body", "fastenings", "lining")}

# The ceiling on any one house modifier, by tier (plan §5.7). Book numbers are exempt,
# being the book. The ceilings above 2 are proposed and still open to playtest (§17).
TIER_CEILING = {"common": 2, "uncommon": 2, "rare": 3, "exotic": 3, "legendary": 4}

# House modifiers *start* at ±2 (the owner's ruling after the first draft): at ±1 a
# half-weight haft gave ±0.5 and rounded to nothing, which made two of the three pieces
# pointless. So a summed house number on a structural material is at least 2 in size.
# Quench marks and finish treatments are applied once and unscaled (§6.3), so a 1 there
# still moves the number and they are held to the ceiling only.
HOUSE_FLOOR = 2

# How big one "point" is for targets that are not counted in ones. A ceiling of 2 on a
# weight change of 2% would make weight unusable as a drawback; spell failure moves in 5%
# steps in the book, weight in tenths, and speed in 5-foot squares.
POINT = {"weight_pct": 10, "asf": 5, "speed_penalty": 5}

# What an assay danger may be, beyond a reactive metal's own carrier effect. One kind:
# `suppress_magic`, the owner's house rule for noqual (2026-10-04, contracts §13.2) —
# "magic recoils": the assayer's active magical effects (buffs, wards) are suppressed for
# the duration. Applied by `knowledge.apply_danger` through the one applicator.
ASSAY_DANGERS = ("suppress_magic",)

# Effect types whose `amount` is a house number the ceiling governs.
_AMOUNTED = ("combat_mod", "save_mod", "skill_mod", "ability_mod", "gear_mod",
             "resistance", "damage_reduction", "fast_healing")
# Types that hurt whoever they land on. On a hit they are the weapon's sting; carried or
# landing on the bearer they are the material's drawback.
_HARMFUL = ("apply_condition", "save_gate", "ability_damage", "ability_drain", "damage",
            "negative_level", "bleed", "vulnerability")

# Form defaults by kind, from plan §5.2's list. A fitting's form is read off its id
# because the catalogue names them that way (ash-haft, leather-grip, brass-guard).
_FORM_OF_KIND = {"ore": "ore", "metal": "bar", "alloy": "alloy bar", "fuel": "fuel",
                 "flux": "flux", "quenchant": "quenchant", "treatment": "treatment"}
_DEFAULT_FORMS = {"metal": ["ingot", "bar", "blank", "plate"],
                  "alloy": ["alloy bar", "blank", "plate"]}


def _fitting_form(mid: str) -> str:
    for word in ("haft", "grip", "guard", "binding", "core"):
        if word in mid:
            return {"crossguard": "guard", "binding": "grip", "core": "haft"}.get(word, word)
    return "fitting"


# --- loading --------------------------------------------------------------------------------

def _read(path: Path) -> list[dict]:
    """Entries from one file, in either shape `blacksmith.load_dir` accepts: a list under
    "materials", or a homebrew file holding one entry."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        files.unreadable(path, exc)
        return []
    entries = data.get("materials") if isinstance(data, dict) else None
    if not isinstance(entries, list):
        entries = [data] if isinstance(data, dict) and data.get("id") else []
    return [e for e in entries if isinstance(e, dict) and e.get("id")]


def _list(value) -> list:
    return list(value) if isinstance(value, (list, tuple)) else []


def normalise(raw: dict, catalogue: str = "") -> dict:
    """One entry as the normalised document (contract §3), every field defaulted.

    Old files load: an entry with none of the forge fields comes back with empty lists,
    no mark, `material` pointing at itself and a form read from its kind. Nothing is
    inferred from prose; an absent list is an empty list, never a guess.
    """
    mid = str(raw.get("id", "")).strip().lower()
    kind = str(raw.get("kind") or "metal")
    pieces_raw = raw.get("pieces") if isinstance(raw.get("pieces"), dict) else {}
    pieces = {g: [str(p) for p in _list(pieces_raw.get(g))] for g in GEARS}
    if kind == "fitting":
        form = _fitting_form(mid)
    else:
        form = _FORM_OF_KIND.get(kind, kind)
    obtain = raw.get("obtain")
    if isinstance(obtain, dict):            # the alchemist's nested dialect
        obtain = obtain.get("how") or ""
    mark = raw.get("quench_mark")
    return {
        "id": mid,
        "name": str(raw.get("name") or mid),
        "kind": kind,
        "tier": str(raw.get("tier") or "common"),
        "form": str(raw.get("form") or form),
        "material": str(raw.get("material") or mid).strip().lower(),
        "pieces": pieces,
        "weapon": [dict(e) for e in _list(raw.get("weapon")) if isinstance(e, dict)],
        "armour": [dict(e) for e in _list(raw.get("armour")) if isinstance(e, dict)],
        "working": [dict(e) for e in _list(raw.get("working")) if isinstance(e, dict)],
        "quench_mark": dict(mark) if isinstance(mark, dict) else None,
        "book": bool(raw.get("book", False)),
        "forms": [str(f) for f in _list(raw.get("forms"))],
        # Which forge methods a material with no piece to fill feeds: djezet, zinc and
        # bismuth are alloying stock, never a blade (contract §3's relevance rule).
        "feeds": [str(f) for f in _list(raw.get("feeds"))],
        # Which gear a treatment finishes. A treatment fills no piece; it is laid over
        # the finished item, so it says which kinds of item it can go on.
        "finishes": [str(f) for f in _list(raw.get("finishes"))],
        # The book's restrictions on a finish: alchemical silver cannot go on
        # adamantine, cold iron or mithral (CRB 155).
        "not_on": [str(f) for f in _list(raw.get("not_on"))],
        # Noqual's "any magic item incorporating noqual costs +5,000 gp to create" is a
        # price, not an effect, so it is a field the enchanter can read.
        "enchant_surcharge_gp": int(raw.get("enchant_surcharge_gp") or 0),
        # What handling a sliver does to the assayer, for a reactive metal whose harm is
        # not a carrier effect (abysium's is: its sickness is what carrying it does).
        # Noqual's is the owner's HOUSE RULE of 2026-10-04, "magic recoils"
        # (`ASSAY_DANGERS`); read by `knowledge.danger_of`. None when it has none.
        "assay_danger": (dict(raw["assay_danger"])
                         if isinstance(raw.get("assay_danger"), dict) else None),
        "price_gp": raw.get("price_gp"),
        "text": str(raw.get("text") or ""),
        "biomes": [str(b) for b in _list(raw.get("biomes"))],
        "obtain": str(obtain or raw.get("source") or ""),
        "catalogue": catalogue,
        # Passed through for the readers that still use them.
        "craft_dc": raw.get("craft_dc"),
        "risky": bool(raw.get("risky", False)),
        "source": str(raw.get("source") or ""),
        "from_creatures": [str(c).lower() for c in _list(raw.get("from_creatures"))],
        "weight_factor": float(raw.get("weight_factor", 1.0) or 1.0),
        "effects": [dict(e) for e in _list(raw.get("effects")) if isinstance(e, dict)],
        # The enchanter's fields (enchanting contracts §5), defaulted on every entry so a
        # reader never has to ask which shelf a document came from. Read by the essence
        # door below; meaningless (and empty) on a metal.
        "grants": dict(raw["grants"]) if isinstance(raw.get("grants"), dict) else None,
        "motes": _int(raw.get("motes")),
        "family": str(raw.get("family") or ""),
        "phase": str(raw.get("phase") or "").strip().lower(),
        "polarity": str(raw.get("polarity") or ""),
        "affinity": [str(a).strip().lower() for a in _list(raw.get("affinity"))],
        "house": [dict(e) for e in _list(raw.get("house")) if isinstance(e, dict)],
        # The enchanter writes a colour as a CSS string ("#c8a2ff"); the alchemist as the
        # [r, g, b] the stage draws its liquid in (alchemy contracts §3). Each shelf keeps
        # its own shape: flattening the list to a string would hand the stage "[0.86, ...]".
        "color": _colour(raw.get("color")),
        # The alchemist's fields (docs/alchemy-contracts.md §3), defaulted on every entry
        # for the reason the enchanter's are. `product` is what the material puts in a
        # bottle; an alchemist entry written before the revamp has only `effects`, which is
        # read as its product (`_legacy_product`), the forge normaliser's trick for its own
        # legacy list. A forge or enchanter entry's `effects` is NOT a product: the
        # blacksmith still reads that list as item effects, and folding it in would hand
        # every metal a row of potion traits.
        "product": _legacy_product(raw, catalogue, kind),
        # What a fail by 5 or more does to the alchemist (a volatile material), and what
        # working it unprotected does (a toxic-to-handle one): one effect document each,
        # applied through the engine by the bench (plan §8). None when it has none.
        "mishap": dict(raw["mishap"]) if isinstance(raw.get("mishap"), dict) else None,
        "toxic": dict(raw["toxic"]) if isinstance(raw.get("toxic"), dict) else None,
        "market": raw.get("market") or None,
        # A shelf entry kept loadable (old saves name it) but never offered: the vessel
        # entries, now that a vessel is a real record (enchanting plan §7.3).
        "retired": bool(raw.get("retired", False)),
        # The pre-revamp enchanter's fields, passed through for `rules/enchanter.py` until
        # lane E's bench moves to the fields above.
        "prefers": str(raw.get("prefers") or ""),
        "plus": _int(raw.get("plus")),
        "adjective": str(raw.get("adjective") or ""),
        "binds_at": str(raw.get("binds_at") or ""),
        "drawbacks": [dict(e) for e in _list(raw.get("drawbacks")) if isinstance(e, dict)],
    }


def _int(value) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _colour(value):
    """A colour as its shelf wrote it: three numbers stay a list (the alchemist's), any
    other value is the enchanter's string, and nothing is ""."""
    if isinstance(value, (list, tuple)) and len(value) == 3:
        try:
            return [float(v) for v in value]
        except (TypeError, ValueError):
            return ""
    return str(value or "")


def _legacy_product(raw: dict, catalogue: str, kind: str) -> list[dict]:
    """An entry's product traits: `product` when written, else an alchemist entry's
    pre-revamp `effects` (see `normalise`)."""
    if isinstance(raw.get("product"), list):
        return [dict(e) for e in raw["product"] if isinstance(e, dict)]
    if catalogue == ALCHEMY_CATALOGUE or (catalogue == "" and kind in _ALCHEMY_ONLY_KINDS):
        return [dict(e) for e in _list(raw.get("effects")) if isinstance(e, dict)]
    return []


# The cache is keyed on *which* homebrew it read and what that homebrew looked like, so it
# cannot leak between tests or go stale under a bench that just saved a file. The rest of
# rules/ holds `_NAME: ... | None = None` caches that tests/conftest.py drops whenever
# `settings.CAMPAIGN_DIR` moves (sixteen tests assign it outright and never restore it);
# this one needs no such list because a moved directory or a changed file is a different
# key. Shipped content is fixed for the life of the process and is not in the key.
_CACHE: dict[tuple, dict[str, dict]] = {}


def _content_dir() -> Path:
    from django.conf import settings
    return Path(settings.BASE_DIR) / "content" / "materials"


def _homebrew_dir() -> Path:
    from django.conf import settings
    return Path(settings.CAMPAIGN_DIR).parent / "homebrew" / "materials"


def _load() -> dict[str, dict]:
    raw: dict[str, dict] = {}
    stems: dict[str, str] = {}
    for stem in CATALOGUES:
        path = _content_dir() / f"{stem}.json"
        if path.is_file():
            for entry in _read(path):
                key = str(entry["id"]).strip().lower()
                raw[key] = dict(entry)
                stems[key] = stem
    home = _homebrew_dir()
    if home.is_dir():
        # Merged field by field, like `blacksmith.materials`: a homebrew file that
        # corrects one field must not erase five, and a correction keeps the catalogue
        # of the entry it corrects (an uncorrected homebrew entry belongs to none).
        for path in sorted(home.glob("*.json")):
            for entry in _read(path):
                key = str(entry["id"]).strip().lower()
                merged = dict(raw.get(key, {}))
                merged.update(entry)
                raw[key] = merged
                stems.setdefault(key, "")
    docs = {k: normalise({**v, "id": k}, stems.get(k, "")) for k, v in raw.items()}
    # An essence's phase is its family's (the owner's ruling: "each essence family names
    # its phase"), so it is filled from the family table here and never needs writing
    # twice. An essence of a family the table does not know keeps its own, which is how a
    # world's own essence (World Bible) names a phase for a family nobody shipped.
    fams = _families_raw()
    for doc in docs.values():
        if doc["kind"] == "essence" and not doc["phase"]:
            doc["phase"] = str((fams.get(doc["family"]) or {}).get("phase") or "")
    # Each parent lists the shelves it appears on: "ore:mithral-ore",
    # "catalyst:mithral-dust", "fitting:mithral-fittings". Computed, never stored.
    for mid, doc in docs.items():
        if not doc["forms"]:
            doc["forms"] = list(_DEFAULT_FORMS.get(doc["kind"], [doc["form"]]))
    for mid, doc in docs.items():
        root = _root(mid, docs)
        if root != mid and root in docs:
            docs[root]["forms"].append(f"{doc['form']}:{mid}")
    return docs


def _key() -> tuple:
    home = _homebrew_dir()
    if not home.is_dir():
        return (str(home),)
    sig = []
    for path in sorted(home.glob("*.json")):
        try:
            st = path.stat()
        except OSError:
            continue
        sig.append((path.name, st.st_mtime_ns, st.st_size))
    return (str(home), tuple(sig))


def _cache(refresh: bool = False) -> dict[str, dict]:
    key = _key()
    if refresh or key not in _CACHE:
        _CACHE.clear()
        _CACHE[key] = _load()
    return _CACHE[key]


def refresh() -> None:
    """Drop the cache. Rarely needed, since a changed homebrew file is a new key; kept
    for a writer that changes a file within the filesystem's timestamp resolution."""
    _cache(refresh=True)


def get(material_id: str) -> dict | None:
    """The normalised document, or None. A copy: the cache is not the caller's to edit."""
    doc = _cache().get(str(material_id or "").strip().lower())
    return copy.deepcopy(doc) if doc is not None else None


def all() -> dict[str, dict]:   # noqa: A001 - the contract's name
    return {k: copy.deepcopy(v) for k, v in _cache().items()}


def of_kind(kind: str) -> list[dict]:
    """Every material of one kind, by tier then name, so a shelf lists them in the order
    a smith climbs to them."""
    out = [copy.deepcopy(d) for d in _cache().values() if d["kind"] == kind]
    return sorted(out, key=lambda d: (_rank(d["tier"]), d["name"]))


def _root(mid: str, docs: dict[str, dict]) -> str:
    seen: set[str] = set()
    cur = mid
    while cur in docs and docs[cur]["material"] != cur and cur not in seen:
        seen.add(cur)
        cur = docs[cur]["material"]
    return cur


def material_of(material_id: str) -> str:
    """A form's parent material: "mithral-fittings" -> "mithral". Followed to the root
    and cycle-safe; an unknown id is its own material, because a homebrew entry nobody
    linked is still the one thing it is."""
    mid = str(material_id or "").strip().lower()
    try:
        docs = _cache()
    except Exception:
        return mid
    return _root(mid, docs)


def is_forge(doc: dict) -> bool:
    """Whether the forge's rules judge this document: the blacksmith's own catalogue, and
    homebrew written in one of the eight forge kinds. The other crafts' entries are read
    through this door and judged by their own benches."""
    cat = doc.get("catalogue", "")
    return cat == FORGE_CATALOGUE or (cat == "" and doc.get("kind") in KINDS)


def _rank(tier: str) -> int:
    return TIERS.index(tier) + 1 if tier in TIERS else 1


# --- judging an effect ------------------------------------------------------------------------

def is_negative(spec: dict) -> bool:
    """Whether this effect leaves the bearer worse off.

    `effectspec.is_drawback` answers for numbers (gear targets by direction, modifiers by
    sign). The rest is who it lands on: a sickness *carried* is the material's drawback,
    the same sickness delivered on a *hit* is its sting. Abysium's only drawback is its
    carrier effect, which is why this cannot be sign-only.
    """
    if effectspec.is_drawback(spec):
        return True
    t = str(spec.get("type") or "")
    if t == "vulnerability":
        return True
    if t in _HARMFUL:
        return spec.get("trigger") == "carried" or spec.get("recipient") == "self"
    if t == "bundle":
        return any(is_negative(e) for e in spec.get("effects") or [])
    return False


def points(spec: dict) -> float | None:
    """The size of a house number in points (see `POINT`), or None if it has none."""
    if str(spec.get("type") or "") not in _AMOUNTED:
        return None
    try:
        amount = int(spec.get("amount"))
    except (TypeError, ValueError):
        return None
    return abs(amount) / POINT.get(str(spec.get("target") or ""), 1)


def _walk(spec: dict):
    """The effect and every effect nested inside it (gate branches, bundles)."""
    yield spec
    for key in ("on_failure", "on_success", "effects", "options", "on_enter"):
        for nested in spec.get(key) or []:
            if isinstance(nested, dict):
                yield from _walk(nested)


def properties(doc: dict) -> int:
    """How many things there are to discover about this material: its item effects, its
    working traits and its quench mark (plan §5.7, "three traits to discover")."""
    return (len(doc.get("weapon") or []) + len(doc.get("armour") or [])
            + len(doc.get("working") or []) + (1 if doc.get("quench_mark") else 0))


# --- validation -------------------------------------------------------------------------------

def validate(doc: dict, *, shelf: dict[str, dict] | None = None) -> list[str]:
    """Everything wrong with one material document, each with the fix named.

    Takes a raw or normalised entry. Documents outside the forge (`is_forge`) are held to
    the shared shape only; the forge's own entries to plan §5.7 in full.

    `shelf` is what a link is resolved against: the loaded shelf by default, or the shelf
    as it is about to be when a tool checks a batch before writing it (an ore's metal must
    be judged as rewritten, not as it was).
    """
    if "pieces" not in doc or not isinstance(doc.get("pieces"), dict) \
            or "catalogue" not in doc:
        default = ENCHANT_CATALOGUE if doc.get("kind") == "essence" else FORGE_CATALOGUE
        doc = normalise(doc, doc.get("catalogue", default))
        if doc["kind"] == "essence" and not doc["phase"]:
            doc["phase"] = str((_families_raw().get(doc["family"]) or {}).get("phase")
                               or "")
    mid = doc.get("id") or "?"
    out: list[str] = []
    known = shelf
    if known is None:
        try:
            known = _cache()
        except Exception:
            known = None

    def say(msg: str) -> None:
        out.append(f"{mid}: {msg}")

    if not doc.get("id"):
        say("has no id. Give it a lowercase hyphenated id.")
    if not doc.get("name") or doc.get("name") == doc.get("id"):
        say("has no name. Give it the name a player reads on the shelf.")
    if doc.get("tier") not in TIERS:
        say(f"tier {doc.get('tier')!r} is not one of {', '.join(TIERS)}.")
    if doc.get("material") != mid:
        if known is not None and doc["material"] not in known:
            say(f"names {doc['material']!r} as its material, and no material has that id. "
                f"Point it at a real parent or remove the field.")
    if doc.get("catalogue") == ALCHEMY_CATALOGUE:
        # The alchemist's own fences (alchemy lane D, contracts §3), asked before the
        # enchanter's: ten alchemist materials are of the kind `essence` too, and the
        # circle's rules (motes, phases, grants) mean nothing on the alchemist's shelf.
        out.extend(alchemy_problems(doc, shelf=known))
        return out
    if doc.get("kind") == "essence" and not is_forge(doc):
        out.extend(essence_problems(doc, shelf=known))
        return out
    if not is_forge(doc):
        return out

    kind = doc.get("kind")
    tier = doc.get("tier")
    ceiling = TIER_CEILING.get(tier, 2)
    if kind not in KINDS:
        say(f"kind {kind!r} is not a forge kind. One of: {', '.join(KINDS)}.")

    # Pieces name real slots.
    for gear, slots in doc["pieces"].items():
        for slot in slots:
            if slot not in PIECES.get(gear, ()):
                say(f"{gear} piece {slot!r} is not a slot. A {gear} has "
                    f"{', '.join(PIECES.get(gear, ()))}.")

    lists = {g: doc.get(g) or [] for g in GEARS}

    # Every effect is a real, executable document. `effectspec.validate` is the
    # vocabulary's own judge; narrative is legal there and refused here (contract §2).
    for gear in GEARS:
        for i, spec in enumerate(lists[gear]):
            out.extend(_effect_problems(spec, f"{mid} {gear} effect {i + 1}"))
    if doc.get("quench_mark"):
        out.extend(_effect_problems(doc["quench_mark"], f"{mid} quench mark"))

    # Book flags agree with each other.
    book_effects = [e for g in GEARS for e in lists[g] if e.get("book")]
    if book_effects and not doc.get("book"):
        say("carries book effects but is not marked \"book\": true. Mark the document.")
    if doc.get("book") and not book_effects:
        say("is marked \"book\": true with no book effect. Remove the mark or add the "
            "printed rule as an effect with \"book\": true.")

    # House numbers: within the tier ceiling, and at least the base on summed lists.
    summed = kind in STRUCTURAL
    for gear in GEARS:
        for i, spec in enumerate(lists[gear]):
            if spec.get("book"):
                continue
            pts = points(spec)
            if pts is None:
                continue
            here = f"{gear} effect {i + 1} ({spec.get('type')} {spec.get('target', '')})"
            if pts > ceiling:
                say(f"{here} is {pts:g} points; a {tier} house modifier is at most "
                    f"±{ceiling}. Bring it inside the ceiling or mark a printed rule "
                    f"\"book\": true.")
            if summed and pts < HOUSE_FLOOR:
                say(f"{here} is {pts:g} points; house modifiers start at ±{HOUSE_FLOOR} "
                    f"(a half-weight piece rounds ±1 to nothing). Raise it to ±2.")
            if summed and spec.get("type") in ("combat_mod", "save_mod", "skill_mod",
                                               "ability_mod") \
                    and spec.get("bonus_type") != "material":
                say(f"{here} has bonus type {spec.get('bonus_type')!r}; a house modifier "
                    f"on a piece is a \"material\" bonus so two pieces fold into one "
                    f"number. Set \"bonus_type\": \"material\".")
    mark = doc.get("quench_mark")
    if mark:
        for spec in _walk(mark):
            pts = points(spec)
            if pts is not None and not spec.get("book") and pts > ceiling:
                say(f"quench mark ({spec.get('type')} {spec.get('target', '')}) is "
                    f"{pts:g} points; a {tier} mark is at most ±{ceiling}.")

    # The structural rule: 3 + 3 where the piece is named, one drawback in each.
    if kind in STRUCTURAL:
        for gear in GEARS:
            named = bool(doc["pieces"].get(gear))
            n = len(lists[gear])
            if named and n < 3:
                say(f"fills a {gear} piece and has {n} {gear} effect(s); a structural "
                    f"material needs at least 3. Add house modifiers at ±2 "
                    f"(combat_mod, gear_mod, save_mod...).")
            if named and n and not any(is_negative(e) for e in lists[gear]):
                say(f"has no drawback in its {gear} effects; every material needs at "
                    f"least one (the owner's ruling: iron hits harder and swings slower). "
                    f"Add a negative house modifier.")
            if not named and n:
                say(f"has {n} {gear} effect(s) but fills no {gear} piece, so none of them "
                    f"can ever apply. Name the piece in \"pieces\" or remove them.")
    elif kind == "treatment":
        if not doc["finishes"]:
            say("is a treatment that finishes nothing. Say which gear it goes on in "
                "\"finishes\" (weapon, armour).")
        for gear in GEARS:
            if lists[gear] and gear not in doc["finishes"]:
                say(f"has {gear} effects but does not finish a {gear}. Add it to "
                    f"\"finishes\" or remove them.")
        if any(doc["pieces"].get(g) for g in GEARS):
            say("is a treatment and fills a piece. A finish is laid over the item; remove "
                "\"pieces\".")
    elif kind in CONSUMABLE or kind == "quenchant" or kind == "ore":
        for gear in GEARS:
            if lists[gear]:
                what = ("a fuel or flux carries working traits only (the owner's ruling)"
                        if kind in CONSUMABLE else
                        "a quenchant leaves one quench mark, not item effects"
                        if kind == "quenchant" else
                        "an ore's effects are its metal's; link it with \"material\"")
                say(f"has {gear} effects, but {what}. Remove them.")
        if any(doc["pieces"].get(g) for g in GEARS):
            say(f"is a {kind} and fills a piece. Remove \"pieces\".")

    danger = doc.get("assay_danger")
    if danger:
        if danger.get("type") not in ASSAY_DANGERS:
            say(f"assay danger {danger.get('type')!r} is not one the assay can apply. One "
                f"of: {', '.join(ASSAY_DANGERS)}.")
        dur = danger.get("duration")
        if not (isinstance(dur, dict) and dur.get("amount") and dur.get("unit")):
            say("assay danger has no duration. Give it {\"amount\": \"1d4\", \"unit\": "
                "\"round\"}.")
        if not any(str(w.get("trait") or "") == "reactive" for w in doc.get("working") or []):
            say("has an assay danger but is not reactive; only a reactive metal is "
                "dangerous to assay (the owner's ruling). Add the `reactive` trait or "
                "remove the danger.")
        if not danger.get("house") and not danger.get("book"):
            say("assay danger says neither \"house\": true nor \"book\": true. Say whose "
                "rule it is.")

    if kind == "quenchant" and not doc.get("quench_mark"):
        say("is a quenchant with no quench mark. Give it one small executable effect it "
            "leaves on what it hardens (plan §5.6).")
    if kind != "quenchant" and doc.get("quench_mark"):
        say("has a quench mark but is not a quenchant. Remove it.")

    # Working traits: at least one, each a real trait.
    working = doc.get("working") or []
    if not working:
        say("has no working trait. Every material behaves some way at the forge: give it "
            "at least one (forgiving, slaggy, narrow_window...).")
    for i, spec in enumerate(working):
        if spec.get("type") != "working":
            say(f"working entry {i + 1} is a {spec.get('type')!r}, not a working trait. "
                f"Write {{\"type\": \"working\", \"trait\": ...}}.")
            continue
        out.extend(effectspec.validate(spec, f"{mid} working {i + 1}"))

    # Three things to discover. An ore is assayed for its metal, so its metal's
    # properties count as its own (plan §2: assay costs "a tenth of a bar, or one ore").
    count = properties(doc)
    parent = None
    if doc.get("material") != mid and known is not None:
        parent = known.get(_root(doc["material"], known))
    if parent is not None:
        count += properties(parent)
        if not is_forge(parent):
            # Another craft's parent (quicksilver is the alchemist's) is known by its
            # own effects, which are what that craft's bench teaches.
            count += len(parent.get("effects") or [])
    if count < 3:
        say(f"has {count} discoverable propert{'y' if count == 1 else 'ies'}; every "
            f"material needs at least 3 (item effects, working traits, mark). Add working "
            f"traits or effects.")

    # Relevance: it fills a piece, feeds a method, or finishes an item (plan §5.7).
    relevant = (any(doc["pieces"].get(g) for g in GEARS)
                or kind in CONSUMABLE or kind == "quenchant"
                or (kind == "treatment" and doc["finishes"]
                    and any(lists[g] for g in GEARS))
                or bool(doc["feeds"])
                or (kind == "ore" and parent is not None))
    if not relevant:
        if kind == "ore":
            say("is an ore that smelts to nothing. Link it to its metal with "
                "\"material\", or say what it feeds in \"feeds\".")
        else:
            say("is irrelevant: it fills no piece, feeds no method and finishes nothing. "
                "Give it \"pieces\", \"feeds\" or \"finishes\".")
    return out


def _effect_problems(spec: dict, path: str) -> list[str]:
    """One item effect: no narrative anywhere in it, executable, and valid vocabulary."""
    out: list[str] = []
    for nested in _walk(spec):
        t = str(nested.get("type") or "")
        if t == "narrative":
            out.append(f"{path}: is narrative prose; a material's effects must be "
                       f"executable. Write it as a typed effect, or move the words to "
                       f"\"text\".")
        elif t == "working":
            out.append(f"{path}: a working trait is not an item effect. Move it to "
                       f"\"working\".")
        elif effectspec.find(t) is not None and not effectspec.executable(nested):
            out.append(f"{path}: {t} is not executable by the engine. Use a type it can "
                       f"run (combat_mod, gear_mod, strikes_as, resistance...).")
    out.extend(effectspec.validate(spec, path))
    return out


# =============================================================================================
# The enchanter's shelf: essences, their families, and the catalogue's recipes
# (docs/enchanting-contracts.md §5, enchanting plan §7; enchanting lane D, 2026-10-05).
# =============================================================================================
#
# **Essences are the cost** (the owner, round 1), so an essence document says two things the
# old shelf never did: *what* it binds (`grants`, a property in lane A's table or a step of
# enhancement) and *how much* (`motes`, potency). ESO's split of a glyph into an essence
# rune and a potency rune is the prior art (enchanting plan §6.5); one mote is 100 gp of the
# book's making cost (the owner, round 4 point 9).
#
# Measured before this pass, over the 81 essences: 14 carried `narrative` prose nothing could
# execute, none said which book property it bound, every bought price was authored by eye
# (flaming 1,800 gp against the 3,000 gp the book charges to make the +1 it adds over a +1
# sword), and no family named the time of day it favours.

ENCHANT_CATALOGUE = "enchanter-materials"
RECIPE_CATALOGUE = "magic-items"

# Where an essence wants to sit (plan §7.2): the old `prefers`, now a matching-seat rule at
# Attune instead of a +5 DC. `ward` is rings, cloaks, belts and the other worn wards.
POLARITIES = ("weapon", "armour", "ward", "any")

# The working traits the circle reads. effectspec.WORKING_TRAITS holds the forge's too; an
# essence that said `slaggy` would load and mean nothing at the bench.
ENCHANT_TRAITS = ("night_only", "eager", "skittish", "heavy", "volatile", "pure")

# The ceiling on one house top-up, by tier (plan §7.2, proposed; the owner's "use the
# proposed numbers", round 4 point 9). Smaller than the forge's ±2 base because a layer's
# top-ups stack on the smith's own piece modifiers.
HOUSE_CEILING = {"common": 1, "uncommon": 1, "rare": 2, "exotic": 2, "legendary": 3}

# One mote is 100 gp of the book's making cost (owner, round 4 point 9). The making cost is
# half the market price (CRB, magic item creation), so a mote carries 200 gp of market value.
MOTE_GP = 100
MARKET_PER_MOTE = 2 * MOTE_GP

# **Rarity is a price band** (the owner, 2026-10-05, for the magic-item catalogue): under
# 1,000 gp common, under 5,000 uncommon, under 20,000 rare, under 50,000 exotic, legendary
# above. Before it the catalogue's tiers were authored by eye and 35 of the 112 wondrous
# items sat outside the band of their own price (Ring of Climbing at 2,500 gp "common"
# beside a 1,000 gp Cloak of Resistance +1; Cloak of Resistance +5 at 25,000 gp
# "legendary" above a 32,000 gp Ring of Protection +4 "exotic").
#
# The same bands tier an **essence**, read on the market value its motes carry (motes × 200
# gp). The price rule forces this rather than taste: `pricing.material_price_problems`
# refuses a rarer essence cheaper than a commoner one, and a bought essence costs its motes
# × 100 by the owner's ruling, so any tiering that is not a rising function of motes fails
# somewhere. Measured on the first draft, which kept lane A's property tiers: the exotic
# ghost touch essence (30 motes, 3,000 gp) came in under the rare Arcane Essence III (90
# motes, 9,000 gp). With one band table a +1 flaming sword's essence sits in the band of
# the 6,000 gp of market value it adds — rare, where lane A put flaming too.
PRICE_BANDS: tuple[tuple[int, str], ...] = (
    (1000, "common"), (5000, "uncommon"), (20000, "rare"), (50000, "exotic"))


def tier_for_price(gp) -> str:
    """The rarity band of a market price in gold (the owner's re-tier of 2026-10-05)."""
    try:
        value = float(gp or 0)
    except (TypeError, ValueError):
        value = 0.0
    for under, tier in PRICE_BANDS:
        if value < under:
            return tier
    return "legendary"


def essence_tier(motes) -> str:
    """An essence's band: the market value its motes carry, on the magic items' bands."""
    return tier_for_price(_int(motes) * MARKET_PER_MOTE)


class BadEssences(ValueError):
    """The shipped essence shelf does not validate. Raised on load with every problem and
    its fix named, as `effectspec.BadProperties` is for lane A's table."""


class BadRecipes(ValueError):
    """The shipped recipe catalogue does not validate (the same shape as `BadEssences`)."""


def _families_from(path: Path) -> dict[str, dict]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    fams = data.get("families") if isinstance(data, dict) else None
    if not isinstance(fams, dict):
        return {}
    return {str(k).strip().lower(): dict(v) for k, v in fams.items() if isinstance(v, dict)}


def _families_raw() -> dict[str, dict]:
    """Every essence family: the shipped table, then homebrew merged field by field."""
    out = _families_from(_content_dir() / f"{ENCHANT_CATALOGUE}.json")
    home = _homebrew_dir()
    if home.is_dir():
        for path in sorted(home.glob("*.json")):
            for key, fam in _families_from(path).items():
                merged = dict(out.get(key, {}))
                merged.update(fam)
                out[key] = merged
    return out


def families() -> dict[str, dict]:
    """The family table, `{family: {"phase", "why", "affinity", "color", "working"}}`.

    Each family names the phase of the day it favours: the owner's ruling (round 4 point
    10) is phases of the day, never a planet, so it asks nothing of the world."""
    return copy.deepcopy(_families_raw())


def family_problems(fams: dict[str, dict], *, shelf: dict[str, dict] | None = None
                    ) -> list[str]:
    """Everything wrong with the family table, each with the fix named."""
    from . import sky

    out: list[str] = []
    for name, fam in fams.items():
        phase = str(fam.get("phase") or "").strip().lower()
        if phase not in sky.PHASES:
            out.append(f"family {name}: phase {fam.get('phase')!r} is not a phase of the "
                       f"day. One of: {', '.join(sky.PHASES)} (rules/sky.py).")
        if not str(fam.get("why") or "").strip():
            out.append(f"family {name}: gives no reason for its phase. Say the folklore in "
                       f"\"why\" so the owner can review it.")
        if not _is_colour(str(fam.get("color") or "")):
            out.append(f"family {name}: color {fam.get('color')!r} is not #rrggbb.")
        for t in fam.get("working") or []:
            if t not in ENCHANT_TRAITS:
                out.append(f"family {name}: working trait {t!r} is not the circle's. One "
                           f"of: {', '.join(ENCHANT_TRAITS)}.")
        if shelf is not None:
            for mid in fam.get("affinity") or []:
                if mid not in shelf:
                    out.append(f"family {name}: affinity {mid!r} is no material. Name a "
                               f"real material id (a metal, a hide, a focus).")
    return out


def _is_colour(value: str) -> bool:
    # Not `all(...)`: this module's own `all()` (the contract's name) shadows the builtin.
    return (len(value) == 7 and value.startswith("#")
            and set(value[1:]) <= set("0123456789abcdefABCDEF"))


_ESSENCES: dict[tuple, dict[str, dict]] = {}


def essences() -> dict[str, dict]:
    """Every essence on the shelf by id, as normalised documents validated on load.

    A problem in a **shipped** essence raises `BadEssences` (shipped content is fixed, and
    a test pins it clean); a broken homebrew essence is left off the shelf rather than
    taking the bench down with it."""
    key = _key()
    if key not in _ESSENCES:
        _ESSENCES.clear()
        shelf = _cache()
        fams = _families_raw()
        problems = [f"{ENCHANT_CATALOGUE}.json: {p}"
                    for p in family_problems(fams, shelf=shelf)]
        out: dict[str, dict] = {}
        for mid, doc in shelf.items():
            if doc["kind"] != "essence":
                continue
            found = essence_problems(doc, shelf=shelf, fams=fams)
            if found and doc["catalogue"] == ENCHANT_CATALOGUE:
                problems.extend(found)
            elif not found:
                out[mid] = doc
        if problems:
            raise BadEssences("the essence shelf is not valid:\n  " + "\n  ".join(problems))
        _ESSENCES[key] = out
    return {k: copy.deepcopy(v) for k, v in _ESSENCES[key].items()}


# --- what a grant costs ---------------------------------------------------------------------

def _ceil_div(a: float, b: float) -> int:
    q = int(a // b)
    return q + (1 if a - q * b > 1e-9 else 0)


def grant_motes(grants: dict | None, polarity: str = "") -> int:
    """The book's making cost of what an essence grants, in motes, on the cheapest item
    that can carry it. One rule, so the gold route is the book's price exactly:

    - `{"enhancement": n}`: a +n weapon is n² × 2,000 gp and armour n² × 1,000 (CRB); the
      making cost is half, so 10n² motes for a weapon essence and 5n² for an armour one.
    - a property priced in `plus`: the market value it adds on top of the +1 enhancement
      every special ability needs under it (CRB: "must have at least a +1 enhancement
      bonus"), halved. Flaming on a +1 sword is (2² − 1²) × 2,000 = 6,000 gp market and
      3,000 to make: 30 motes, and with Arcane Essence I's 10 that is the 40 a +1 flaming
      sword costs.
    - a property priced in `gp` (shadow, energy resistance): half its gold, rounded up.
    - a scaled one (deflection, resistance...): bonus² × its price per square, halved, at
      the grant's `bonus`, or the smallest value the book prints.
    - `{"power": recipe}`: the recipe's own making cost.
    """
    if not grants:
        return 0
    if "enhancement" in grants:
        n = _int(grants.get("enhancement"))
        per = 1000 if polarity == "armour" else 2000
        return _ceil_div(n * n * per / 2, MOTE_GP)
    if grants.get("property"):
        prop = effectspec.properties().get(str(grants["property"]))
        if not prop:
            return 0
        if prop.get("plus") is not None:
            p = int(prop["plus"])
            per = 2000 if "weapon" in (prop.get("gear") or ()) else 1000
            return _ceil_div(((1 + p) ** 2 - 1) * per / 2, MOTE_GP)
        if prop.get("gp") is not None:
            return _ceil_div(int(prop["gp"]) / 2, MOTE_GP)
        scaled = prop.get("scaled") or {}
        values = list(scaled.get("values") or [1])
        bonus = _int(grants.get("bonus")) or int(values[0])
        return _ceil_div(bonus * bonus * int(scaled.get("gp_per_square") or 0) / 2, MOTE_GP)
    if grants.get("power"):
        row = _recipe_rows().get(str(grants["power"]))
        if not row:
            return 0
        return _ceil_div(float(row.get("price_gp") or 0) / 2, MOTE_GP)
    return 0


def grant_problems(grants: dict | None, polarity: str = "") -> list[str]:
    """What is wrong with one `grants` field; [] when it resolves."""
    if grants is None:
        return []
    keys = [k for k in ("property", "enhancement", "power") if k in grants]
    if len(keys) != 1:
        return [f"grants names {', '.join(keys) or 'nothing'}; it names exactly one of "
                f"property, enhancement or power (contracts §5)."]
    out: list[str] = []
    extra = set(grants) - {"property", "enhancement", "power", "choice", "bonus"}
    if extra:
        out.append(f"grants carries {', '.join(sorted(extra))}, which no reader knows. Use "
                   f"property (with an optional choice or bonus), enhancement or power.")
    if keys == ["enhancement"]:
        if not 1 <= _int(grants.get("enhancement")) <= 5:
            out.append(f"grants enhancement {grants.get('enhancement')!r}; a step is +1 to "
                       f"+5 (the book's enhancement ladder).")
        if polarity not in ("weapon", "armour"):
            out.append(f"grants enhancement with polarity {polarity!r}; an enhancement step "
                       f"is a weapon's or an armour's (its price differs), so say which.")
    elif keys == ["property"]:
        pid = str(grants["property"])
        prop = effectspec.properties().get(pid)
        if prop is None:
            alias = effectspec.from_alias(pid)
            hint = f" It is the old id of {alias[0]!r}: name that." if alias else ""
            return out + [f"grants property {pid!r}, which is not in "
                          f"content/rules/magic-properties.json.{hint}"]
        if grants.get("choice") is not None:
            if not prop.get("choice"):
                out.append(f"grants {pid} with a choice, and {pid} takes none. Remove it.")
            else:
                out.extend(f"grants {pid}: {p}" for p in effectspec.choice_problems(
                    prop, dict(grants.get("choice") or {})))
        if grants.get("bonus") is not None:
            values = (prop.get("scaled") or {}).get("values") or []
            if _int(grants["bonus"]) not in values:
                out.append(f"grants {pid} at bonus {grants['bonus']!r}; the book prints "
                           f"{values or 'no bonus for it'}.")
    elif str(grants["power"]) not in _recipe_rows():
        out.append(f"grants power {grants['power']!r}, and no recipe has that id.")
    return out


# --- the essence document ---------------------------------------------------------------------

def essence_traits(doc: dict) -> list[str]:
    """The things there are to discover about an essence (plan §7.2): what it grants, each
    house top-up, its phase, its polarity, its affinity and each working trait. Keys in the
    order a Read reveals them."""
    out: list[str] = []
    if doc.get("grants"):
        out.append("grants")
    out.extend(f"house:{i}" for i, _ in enumerate(doc.get("house") or []))
    if doc.get("phase"):
        out.append("phase")
    if doc.get("polarity"):
        out.append("polarity")
    if doc.get("affinity"):
        out.append("affinity")
    out.extend(f"working:{w.get('trait')}" for w in doc.get("working") or [])
    return out


def _house_points(spec: dict) -> float | None:
    """`points` for a house top-up, and a flat damage rider's size: a fire mote's "+1 fire
    on a hit" is one point. Dice are refused before this is asked."""
    if spec.get("type") == "damage":
        try:
            return float(int(str(spec.get("dice")).strip()))
        except (TypeError, ValueError):
            return None
    return points(spec)


# The kinds of document a house top-up may be: the small typed numbers plan §7.2 names
# (a resistance, a skill or save modifier, a combat modifier, a flat rider) and fast
# healing, which one shipped essence carries. Everything else is a book property's own
# shape and comes through "grants".
HOUSE_TYPES = frozenset({"resistance", "save_mod", "skill_mod", "combat_mod", "damage",
                         "fast_healing"})


def essence_problems(doc: dict, *, shelf: dict[str, dict] | None = None,
                     fams: dict[str, dict] | None = None) -> list[str]:
    """Everything wrong with one essence document, each with the fix named: at least three
    traits, no narrative, a grant that resolves, price = motes × 100, top-ups inside the
    ceilings (contracts §5), and a phase of the day (the owner's ruling)."""
    from . import sky

    mid = doc.get("id") or "?"
    out: list[str] = []

    def say(msg: str) -> None:
        out.append(f"{mid}: {msg}")

    fams = _families_raw() if fams is None else fams
    tier = doc.get("tier")
    polarity = doc.get("polarity") or ""
    grants = doc.get("grants")

    # What it grants, and what that costs.
    for p in grant_problems(grants, polarity):
        say(p)
    motes = _int(doc.get("motes"))
    need = grant_motes(grants, polarity) if not out else 0
    bought = str(doc.get("obtain") or "") == "bought"
    if motes < 1:
        say("has no motes. Every essence carries potency: give it \"motes\" (1 mote = "
            "100 gp of the book's making cost).")
    elif motes < need:
        say(f"carries {motes} motes, under the {need} its grant costs to make. Raise "
            f"\"motes\" to at least {need}.")
    elif bought and grants and need and motes != need:
        say(f"is bought and carries {motes} motes against the {need} its grant costs; a "
            f"bought essence carries exactly its grant's making cost, so buying it is the "
            f"book's price. Set \"motes\" to {need}.")
    if motes >= 1 and tier != essence_tier(motes):
        say(f"is {tier} with {motes} motes ({motes * MARKET_PER_MOTE:,} gp of market "
            f"value), and that is the {essence_tier(motes)} band (materials.PRICE_BANDS). "
            f"Set \"tier\" to {essence_tier(motes)!r}.")
    price = doc.get("price_gp")
    if bought:
        try:
            priced = float(price) if price not in (None, "") else None
        except (TypeError, ValueError):
            priced = None
        if priced != motes * MOTE_GP:
            say(f"is bought at {price!r} gp; a bought essence costs its motes × {MOTE_GP} "
                f"(the owner's ruling). Set \"price_gp\" to {motes * MOTE_GP}.")
    elif price not in (None, "", 0):
        say(f"is {doc.get('obtain') or 'not bought'} and carries a price; no shop sells "
            f"it, which an absent price says. Remove \"price_gp\" or make it bought.")

    # Family and phase: the owner's ruling, checked on load.
    family = doc.get("family") or ""
    if not family:
        say("has no family. Name the family it belongs to (fire, holy, shadow...).")
    fam = fams.get(family)
    phase = str(doc.get("phase") or "").strip().lower()
    if phase not in sky.PHASES:
        where = (f"its family {family!r} is not in the families table" if fam is None
                 else f"its family {family!r} names {fam.get('phase')!r}")
        say(f"has phase {doc.get('phase')!r} ({where}). A phase is one of "
            f"{', '.join(sky.PHASES)}: give the family a \"phase\" in the families table, "
            f"or the essence its own.")
    elif fam is not None and str(fam.get("phase") or "").lower() not in ("", phase):
        say(f"says phase {phase!r} but its family {family!r} favours {fam.get('phase')!r}. "
            f"A family has one phase: drop the essence's own.")

    if polarity not in POLARITIES:
        say(f"polarity {polarity!r} is not one of {', '.join(POLARITIES)}.")
    if shelf is not None:
        for a in doc.get("affinity") or []:
            if a not in shelf:
                say(f"affinity {a!r} is no material on the shelf. Name a real id.")

    # House top-ups: small, typed, executable, scaled by binding quality.
    house = doc.get("house") or []
    if not house:
        say("has no house top-up. Every essence carries at least one small typed effect "
            "(plan §7.2): a resistance, a skill or save modifier, a flat rider.")
    ceiling = HOUSE_CEILING.get(tier, 1)
    for i, spec in enumerate(house):
        here = f"house {i + 1} ({spec.get('type')} {spec.get('target', '')})".replace(" )", ")")
        for nested in _walk(spec):
            t = str(nested.get("type") or "")
            if t == "narrative":
                say(f"{here} is narrative prose; a top-up is a typed effect. Move the words "
                    f"to \"text\".")
            elif t in effectspec.AWAITING_READER:
                say(f"{here} is a {t}, which waits on lane C's reader "
                    f"({effectspec.AWAITING_READER[t]}); an essence names book properties "
                    f"through \"grants\", never these documents.")
            elif nested is spec and t not in HOUSE_TYPES:
                # A top-up is a small house number; a book property's own document (keen's
                # crit_range, speed's extra_attack) is reached through "grants". This was
                # refused only while those types waited on lane C's readers; once the
                # readers landed (2026-10-05) a keen top-up on a flaming essence passed.
                say(f"{here} is a {t}; a top-up is one of {', '.join(sorted(HOUSE_TYPES))}. "
                    f"A book property is named through \"grants\".")
            elif effectspec.find(t) is not None and not effectspec.executable(nested):
                say(f"{here}: {t} is not executable by the engine. Use one it runs "
                    f"(resistance, save_mod, skill_mod, combat_mod, a flat damage rider).")
        if not spec.get("house"):
            say(f"{here} is not marked \"house\": true. Every top-up is a house number "
                f"that binding quality scales: mark it.")
        if spec.get("book"):
            say(f"{here} is marked \"book\"; a book number is the property's, reached "
                f"through \"grants\". Remove the mark.")
        if spec.get("type") == "damage" and not str(spec.get("dice", "")).strip().isdigit():
            say(f"{here} rolls dice {spec.get('dice')!r}; a house rider is a flat number "
                f"(dice are the book's, through \"grants\").")
        pts = _house_points(spec)
        if pts is not None and pts > ceiling:
            say(f"{here} is {pts:g} points; a {tier} top-up is at most ±{ceiling} "
                f"(materials.HOUSE_CEILING). Bring it inside the ceiling.")
        out.extend(effectspec.validate(spec, f"{mid} {here}"))

    # Working traits: the circle's own.
    for i, spec in enumerate(doc.get("working") or []):
        if spec.get("type") != "working":
            say(f"working entry {i + 1} is a {spec.get('type')!r}, not a working trait.")
            continue
        if spec.get("trait") not in ENCHANT_TRAITS:
            say(f"working trait {spec.get('trait')!r} is not the circle's. One of: "
                f"{', '.join(ENCHANT_TRAITS)}.")
        out.extend(effectspec.validate(spec, f"{mid} working {i + 1}"))
    traits = {w.get("trait") for w in doc.get("working") or []}
    if "volatile" in traits and not any(is_negative(e) for e in house):
        say("is volatile and has no drawback among its top-ups; volatile means reading it "
            "applies its drawback (plan §7.3). Add a negative top-up or drop the trait.")
    if not _is_colour(str(doc.get("color") or "")):
        say(f"color {doc.get('color')!r} is not #rrggbb; the stage's glow reads it.")

    n = len(essence_traits(doc))
    if n < 3:
        say(f"has {n} discoverable trait(s); an essence needs at least 3 (grant, top-ups, "
            f"phase, polarity, affinity, working traits).")
    return out


# --- recipes: the catalogue's wondrous items --------------------------------------------------
#
# The owner: "a catalogue item is a known recipe of essences and a vessel" (round 3). The 112
# wondrous rows of magic-items.json are the recipes; the 58 weapon and armour rows are lane
# A's property table now (its `aliases`). The old fields (`spell`, `effects`, `slot`) stay
# for `rules/magicitem.py` until lane E's bench reads these.

RECIPE_VESSELS = ("slotless", "rod")


def _recipe_paths() -> list[Path]:
    from django.conf import settings

    paths = [_content_dir() / f"{RECIPE_CATALOGUE}.json"]
    home = Path(settings.CAMPAIGN_DIR).parent / "homebrew" / "magic-items"
    if home.is_dir():
        paths.extend(sorted(home.glob("*.json")))
    return paths


def _recipe_rows() -> dict[str, dict]:
    """The raw wondrous rows, shipped then homebrew merged field by field."""
    out: dict[str, dict] = {}
    for i, path in enumerate(_recipe_paths()):
        for row in _read(path):
            key = str(row["id"]).strip().lower()
            merged = dict(out.get(key, {}))
            merged.update(row)
            if i:
                merged.setdefault("_homebrew", True)
            out[key] = merged
    return {k: v for k, v in out.items() if v.get("kind") == "wondrous"}


def normalise_recipe(raw: dict) -> dict:
    """One wondrous row as a recipe document (plan §7.4), every field defaulted."""
    spells = raw.get("spells")
    if not isinstance(spells, list):
        spells = [[raw["spell"]]] if raw.get("spell") else []
    price = raw.get("price_gp") or 0
    cost = raw.get("cost_gp")
    if cost in (None, ""):
        cost = float(price) / 2
    return {
        "id": str(raw.get("id") or "").strip().lower(),
        "name": str(raw.get("name") or raw.get("id") or ""),
        "vessel": str(raw.get("vessel") or raw.get("slot") or "slotless"),
        "book": [dict(e) for e in _list(raw.get("book")) if isinstance(e, dict)],
        "spells": [[str(s) for s in g] for g in spells if isinstance(g, list)],
        "caster_level": _int(raw.get("caster_level")),
        "creator_level": _int(raw.get("creator_level")) or None,
        "creator": [str(c) for c in _list(raw.get("creator"))],
        "price_gp": price,
        "cost_gp": cost,
        "motes": _ceil_div(float(cost or 0), MOTE_GP),
        "essences": [dict(e) for e in _list(raw.get("essences")) if isinstance(e, dict)],
        "tier": str(raw.get("tier") or "common"),
        "source": str(raw.get("source") or ""),
        "not_yet": [str(n) for n in _list(raw.get("not_yet"))],
        "retired": bool(raw.get("retired", False)),
        "why_retired": str(raw.get("why_retired") or ""),
        "text": str(raw.get("text") or ""),
        "homebrew": bool(raw.get("_homebrew", False)),
    }


_RECIPES: dict[tuple, dict[str, dict]] = {}


def _recipe_key() -> tuple:
    sig = []
    for path in _recipe_paths():
        try:
            st = path.stat()
        except OSError:
            continue
        sig.append((str(path), st.st_mtime_ns, st.st_size))
    return (_key(), tuple(sig))


def recipes() -> dict[str, dict]:
    """Every recipe a binder can know, by id: the wondrous items, retired rows left out.
    Validated on load like `essences()`: a shipped problem raises `BadRecipes`, a broken
    homebrew row is left out."""
    key = _recipe_key()
    if key not in _RECIPES:
        _RECIPES.clear()
        shelf = essences()
        rows = _recipe_rows()
        problems = [f"{RECIPE_CATALOGUE}.json: {p}" for p in magic_item_tier_problems(
            [r for r in rows.values() if not r.get("_homebrew")])]
        out: dict[str, dict] = {}
        for rid, raw in rows.items():
            doc = normalise_recipe(raw)
            if doc["retired"]:
                continue
            found = recipe_problems(doc, essences=shelf)
            if found and not doc["homebrew"]:
                problems.extend(found)
            elif not found:
                out[rid] = doc
        if problems:
            raise BadRecipes("the recipe catalogue is not valid:\n  " + "\n  ".join(problems))
        _RECIPES[key] = out
    return {k: copy.deepcopy(v) for k, v in _RECIPES[key].items()}


def recipe(recipe_id: str) -> dict | None:
    return recipes().get(str(recipe_id or "").strip().lower())


def magic_item_tier_problems(rows) -> list[str]:
    """Every priced wondrous row whose tier is not its price band (the owner's re-tier of
    2026-10-05), each with the fix named; [] when sound. A check, not a derivation, so the
    tier stays a written fact `rules/magicitem.py` reads as it is."""
    out: list[str] = []
    for row in rows or ():
        if not isinstance(row, dict) or row.get("kind") != "wondrous":
            continue
        try:
            price = float(row.get("price_gp") or 0)
        except (TypeError, ValueError):
            continue
        if price <= 0:
            continue
        band = tier_for_price(price)
        if row.get("tier") != band:
            out.append(f"{row.get('id')}: {row.get('name')} is {row.get('tier')} at "
                       f"{price:,.0f} gp, and that price is {band} (under 1,000 gp common, "
                       f"5,000 uncommon, 20,000 rare, 50,000 exotic, then legendary). Set "
                       f"\"tier\" to {band!r}.")
    return out


def recipe_problems(doc: dict, *, essences: dict[str, dict] | None = None,
                    spell_ids=None) -> list[str]:
    """Everything wrong with one recipe, each with the fix named."""
    from .tables import SLOTS

    if "book" not in doc or "vessel" not in doc:
        doc = normalise_recipe(doc)
    rid = doc.get("id") or "?"
    out: list[str] = []

    def say(msg: str) -> None:
        out.append(f"{rid}: {msg}")

    shelf = essences if essences is not None else {}
    price = float(doc.get("price_gp") or 0)
    if price <= 0:
        say("has no price. Give it the book's price_gp.")
    elif doc.get("tier") != tier_for_price(price):
        say(f"is {doc.get('tier')} at {price:,.0f} gp; set \"tier\" to "
            f"{tier_for_price(price)!r} (the price bands).")
    if not 1 <= _int(doc.get("caster_level")) <= 20:
        say(f"caster level {doc.get('caster_level')!r} is not the book's 1st to 20th.")
    if doc.get("vessel") not in SLOTS and doc.get("vessel") not in RECIPE_VESSELS:
        say(f"vessel {doc.get('vessel')!r} is no slot. One of the sheet's slots "
            f"(rules/tables.SLOTS) or {', '.join(RECIPE_VESSELS)}.")
    if not str(doc.get("source") or "").startswith("https://legacy.aonprd.com/"):
        say("cites no source. Name the AoN page its numbers were read from.")

    book = doc.get("book") or []
    if not book:
        say("has no book effects. Write what the item does as effect documents.")
    for i, spec in enumerate(book):
        for nested in _walk(spec):
            if str(nested.get("type") or "") == "narrative":
                say(f"book effect {i + 1} is narrative prose; write it as a typed effect "
                    f"(an item_power with a tell, if it changes no number) and put the "
                    f"clause nothing runs in \"not_yet\".")
        out.extend(effectspec.validate(spec, f"{rid} book {i + 1}"))

    if spell_ids is None:
        try:
            from . import spells as _spells

            spell_ids = set(_spells.all_spells())
        except Exception:
            spell_ids = None
    for g in doc.get("spells") or []:
        if not g:
            say("has an empty spell group. Remove it.")
        for sid in g:
            if spell_ids is not None and sid not in spell_ids:
                say(f"spell {sid!r} is not in the spell corpus. Use the Spells bench's id.")

    needs = doc.get("essences") or []
    if not needs:
        say("names no essences. A recipe is essences and a vessel: say which.")
    granted = {str((e.get("grants") or {}).get("property") or "") for e in shelf.values()}
    steps = any("enhancement" in (e.get("grants") or {}) for e in shelf.values())
    fams_here = {e.get("family") for e in shelf.values()}
    for need in needs:
        if _int(need.get("count") or 1) < 1:
            say(f"needs {need.get('count')!r} of an essence; a count is 1 or more.")
        if need.get("grants"):
            g = str(need["grants"])
            if g == "enhancement":
                if shelf and not steps:
                    say("needs an enhancement essence and none is on the shelf.")
            elif g not in effectspec.properties():
                say(f"needs grants {g!r}, which is not a property id.")
            elif shelf and g not in granted:
                say(f"needs an essence granting {g!r} and none on the shelf grants it. Add "
                    f"one, or name a family instead.")
        elif need.get("family"):
            if shelf and need["family"] not in fams_here:
                say(f"needs a {need['family']!r} essence and no essence is of that family.")
        else:
            say(f"essence need {need!r} names neither grants nor family.")
    return out


# =============================================================================================
# The alchemist's shelf: its catalogue and the hybrid herbs, through this one door
# (docs/alchemy-contracts.md §3; alchemy plan §5.7; alchemy lane A, 2026-10-06).
# =============================================================================================
#
# **The two-way door.** The owner's "one material, many shelves" (alchemy Q2.1): the alchemy
# shelf is the alchemist's catalogue plus every ingredient marked `hybrid` (63 shipped). No
# herb is copied into content/materials. A hybrid herb is served here as a document in
# this module's shape, built from the herb corpus each time it is asked, with its effects
# read as product traits, ALL routes included — the 49 `external` effects the herb bench
# drops as "alchemy only" are exactly what this shelf is for.
#
# **The collision this door would have opened.** Before it, `basilisk-eye` was the id of a
# herb (hybrid, rare) AND of an alchemist gland. Knowledge asked materials first, so the
# herb's own card resolved to the gland; one `herb_known` entry stood for two documents;
# and the moment hybrids joined this shelf the two would have sat on it under one id. The
# gland was the same object (an intact basilisk eye), so it was merged into the herb as an
# `external` product trait and its row deleted. tests/test_alchemy_shelf.py pins every
# material id against every ingredient id, which the old test (catalogues against each
# other only) could not see.
#
# Herb views are rebuilt on each call rather than cached: the herb corpus has its own
# cache (`ingredients.all_ingredients`, dropped by tests/conftest.py when the campaign
# directory moves), and a second cache here would be the stale copy CLAUDE.md warns of.

def _ingredient_of(doc_or_id):
    """The herb an id or a herb view names, or None."""
    from . import ingredients

    hid = doc_or_id if isinstance(doc_or_id, str) else (doc_or_id or {}).get("id")
    try:
        return ingredients.all_ingredients().get(str(hid or "").strip().lower())
    except Exception:  # noqa: BLE001 - a corpus that cannot load has no herbs to serve
        return None


def _hybrids() -> dict:
    from . import ingredients

    try:
        corpus = ingredients.all_ingredients()
    except Exception:  # noqa: BLE001 - as above
        return {}
    return {k: ing for k, ing in corpus.items() if getattr(ing, "hybrid", False)}


def herb_view(ing) -> dict:
    """A hybrid herb as an alchemy document (contract §3's shape, every field defaulted).

    Its product traits are its effects in the herb's own order, one for one with the
    herb's property keys ("p0", "p1"...), so what was learned by tasting it is what the
    alchemist knows of it and the other way round: one document, one store
    (`knowledge` reads the same keys either way; the shelf test holds the two to it)."""
    part = str(getattr(ing, "part", "") or "")
    source = str(getattr(ing, "source", "") or "").strip().lower()
    if getattr(ing, "kind", "") == "monster part":
        obtain = "harvested"
    elif getattr(ing, "forageable", False):
        obtain = "gathered"
    else:
        obtain = ""
    doc = normalise({
        "id": ing.id, "name": ing.name, "kind": ing.kind, "tier": ing.tier,
        "form": part or ing.kind, "text": ing.text, "biomes": list(ing.biomes),
        "craft_dc": ing.craft_dc, "risky": ing.risky, "source": source,
        "from_creatures": [source] if source and obtain == "harvested" else [],
        "obtain": obtain,
        # `pairs`, not `effects`: the same walk the herb's keys come from, so a homebrew
        # herb whose effects are still parsed from its text keeps its keys aligned too.
        "product": [copy.deepcopy(spec) for _, spec in ing.pairs],
    }, HERB_CATALOGUE)
    doc["forms"] = [doc["form"]]
    doc["hybrid"] = True
    doc["part"] = part
    return doc


def is_herb_view(doc) -> bool:
    """A hybrid herb served on the alchemy shelf (`herb_view`)."""
    return isinstance(doc, dict) and doc.get("catalogue") == HERB_CATALOGUE


def is_alchemy(doc) -> bool:
    """Whether a document belongs on the alchemist's shelf: the alchemist's catalogue, a
    hybrid herb (as a view or as the herb itself), or homebrew with no catalogue that
    writes `product` or is of one of the alchemist's own kinds."""
    if doc is None:
        return False
    if not isinstance(doc, dict):
        return bool(getattr(doc, "hybrid", False))
    cat = doc.get("catalogue")
    if cat in (ALCHEMY_CATALOGUE, HERB_CATALOGUE):
        return True
    if cat is None and doc.get("hybrid") and "effects" in doc:
        return True                       # a raw herb row
    if not cat:
        return bool(doc.get("product")) or str(doc.get("kind") or "") in _ALCHEMY_ONLY_KINDS
    return False


def alchemy_shelf() -> dict[str, dict]:
    """Every document on the alchemist's shelf, by id: the alchemist's catalogue (and
    homebrew in its kinds), then every hybrid herb. Copies, as `all` gives.

    Retired entries are left off, as every shelf leaves them. Shipped ids are pinned
    disjoint; should a homebrew herb ever take a material's id, the material keeps it,
    because `knowledge.resolve` asks materials first and the shelf must answer as it does.
    """
    out = {mid: copy.deepcopy(d) for mid, d in _cache().items()
           if is_alchemy(d) and not d.get("retired")}
    for hid, ing in _hybrids().items():
        if hid not in out:
            out[hid] = herb_view(ing)
    return out


def alchemy_doc(doc_id: str) -> dict | None:
    """One document off the alchemy shelf, or None: a material of the alchemist's, or a
    hybrid herb's view. Never another craft's material."""
    mid = str(doc_id or "").strip().lower()
    doc = get(mid)
    if doc is not None:
        return doc if is_alchemy(doc) and not doc.get("retired") else None
    ing = _ingredient_of(mid)
    return herb_view(ing) if ing is not None and getattr(ing, "hybrid", False) else None


def product_traits(doc) -> list[dict]:
    """What a document puts into a bottle, as effect documents (copies): its `product`,
    or a pre-revamp alchemist entry's `effects`, or a hybrid herb's effects. A forge or
    enchanter document has none. Takes a normalised or raw document, or the herb."""
    if doc is None:
        return []
    if not isinstance(doc, dict):
        if not getattr(doc, "hybrid", False):
            return []
        return [copy.deepcopy(spec) for _, spec in doc.pairs]
    if isinstance(doc.get("product"), list):
        return [copy.deepcopy(e) for e in doc["product"] if isinstance(e, dict)]
    if doc.get("hybrid"):
        return [copy.deepcopy(e) for e in _list(doc.get("effects")) if isinstance(e, dict)]
    return [copy.deepcopy(e) for e in _legacy_product(doc, str(doc.get("catalogue") or ""),
                                                      str(doc.get("kind") or ""))]


def product_essences(doc) -> set[str]:
    """The essences a document's product traits carry (`essence.<id>` without the
    prefix). Contract §3 names this `essences(doc)`; that name was already the
    enchanter's (`essences()`, every essence document on its shelf), and the enchanter's
    name stands, so the alchemist's question is asked by this one."""
    return {str(t["essence"]) for t in product_traits(doc) if t.get("essence")}


# =============================================================================================
# The alchemist's validator (docs/alchemy-contracts.md §3, plan §5.6; alchemy lane D,
# 2026-10-06): what an alchemy material must add up to, each refusal with its fix named.
# =============================================================================================
#
# Measured before the pass (plan §5.1): of 139 materials, 70 carried no effect at all, 5
# carried only narrative, none carried three properties, and no material could say how it
# behaves at the bench. The forge's branch above returns early for every non-forge entry,
# so nothing judged an alchemist's document at all.
#
# **The house ceilings.** Flat numbers are held to the forge's `TIER_CEILING` (plan §5.6:
# "the forge's TIER_CEILING ... bounds every flat house number"), counted by `points`.
# House dice are held to `ALCHEMY_DICE_CEILING` (PROPOSED in plan §5.6, open to playtest),
# compared by the largest roll, so 2d8 (16) fits under an exotic 3d6 (18) and 3d8 (24) does
# not. Book effects are exempt, being the book.
#
# **Who needs a drawback.** Q7.1's ruling is "at least three discoverable traits per
# reagent, one a drawback". A material that puts nothing into the bottle — a vessel, a
# catalyst that is never spent, a neutral medium, prima materia's wild trait — is apparatus
# rather than a reagent, and has no cost of its own to carry into a product; it is held
# to three properties and not to the drawback. The drawback is judged by
# `knowledge.classify`, the one judge the card uses, so a "drawback" here is exactly what
# the player sees marked as one.

ALCHEMY_DICE_CEILING = {"common": "1d4", "uncommon": "1d6", "rare": "2d6",
                        "exotic": "3d6", "legendary": "4d6"}
# Working traits that give a material a job at the bench without a product trait: a
# vessel's family, a solvent, a stabilizer, a catalyst or apparatus, the wild trait.
_ALCHEMY_ROLES = ("catalyst", "apparatus", "stabilizer", "wild")
# The routes on which a trait lands on a foe or on everyone near where the product lands,
# never on the user: a cost on one of them is not a cost to anybody who chose it.
_FOE_ROUTES = ("struck", "splash", "area")


def dice_max(dice) -> int | None:
    """The largest total a dice string can roll ("2d6+1" -> 13, "20" -> 20); None when it
    is not one (a formula, a word)."""
    s = str(dice or "").replace(" ", "").lower()
    if not s:
        return None
    total = 0
    for part in re.split(r"(?=[+-])", s):
        if not part:
            continue
        sign = -1 if part[0] == "-" else 1
        body = part.lstrip("+-")
        m = re.fullmatch(r"(\d*)d(\d+)", body)
        if m:
            total += sign * int(m.group(1) or 1) * int(m.group(2))
        elif body.isdigit():
            total += sign * int(body)
        else:
            return None
    return total


def alchemy_problems(doc: dict, *, shelf: dict[str, dict] | None = None) -> list[str]:
    """Everything wrong with one alchemist's material (plan §5.6), each with the fix named.

    Takes a normalised alchemy document (`normalise(raw, ALCHEMY_CATALOGUE)`). Checks:
    the kind; every product trait through `effectspec.product_trait_problems` (essence,
    route, never narrative) and executable, or waiting on a reader the vocabulary names;
    a drawback is never on a foe's route; working traits are the alchemist's; at least
    three properties; a drawback on anything with product traits; the house ceilings;
    `volatile` with a mishap and `toxic_to_handle` with a toxic document, both ways; a
    job at the bench for anything with no product trait; the book flags; the colour.
    """
    from . import knowledge

    mid = doc.get("id") or "?"
    out: list[str] = []

    def say(msg: str) -> None:
        out.append(f"{mid}: {msg}")

    kind, tier = doc.get("kind"), doc.get("tier")
    if kind not in ALCHEMY_KINDS:
        say(f"kind {kind!r} is not an alchemist's kind. One of: {', '.join(ALCHEMY_KINDS)}.")
    product = list(doc.get("product") or [])
    working = list(doc.get("working") or [])
    traits = [str(w.get("trait") or "") for w in working]

    for i, spec in enumerate(product):
        here = f"{mid} product {i + 1}"
        out.extend(effectspec.product_trait_problems(spec, here))
        for nested in _walk(spec):
            if nested is not spec and str(nested.get("type") or "") == "narrative":
                out.append(f"{here}: carries narrative prose inside it. Type it or leave "
                           f"it out.")
        t = str(spec.get("type") or "")
        waiting = (t in effectspec.AWAITING_READER
                   or str(spec.get("target") or "") in
                   effectspec.TARGETS_AWAITING_READER.get(t, {}))
        if effectspec.find(t) is not None and not effectspec.executable(spec) \
                and not waiting and t != "narrative":
            out.append(f"{here}: {t} is not executable by the engine, and no reader is "
                       f"promised for it. Use a type the engine runs.")
        if spec.get("drawback") and str(spec.get("route") or "") in _FOE_ROUTES:
            out.append(f"{here}: is marked a drawback but lands on a foe "
                       f"({spec.get('route')}). A drawback is a cost to whoever uses the "
                       f"product: give it a route that reaches them (ingest, skin, eyes, "
                       f"inhale, carried), or drop the mark.")

    for i, spec in enumerate(working):
        if spec.get("type") != "working":
            say(f"working entry {i + 1} is a {spec.get('type')!r}, not a working trait. "
                f"Write {{\"type\": \"working\", \"trait\": ...}}.")
        elif traits[i] not in effectspec.ALCHEMY_WORKING_TRAITS:
            say(f"working trait {traits[i]!r} means nothing at the alchemist's bench. One "
                f"of: {', '.join(effectspec.ALCHEMY_WORKING_TRAITS)}.")

    for key in ("mishap", "toxic"):
        if doc.get(key):
            out.extend(_effect_problems(doc[key], f"{mid} {key}"))
    volatile = "volatile" in traits
    if volatile and not doc.get("mishap"):
        say("is volatile and has no mishap. Say what a roll failed by 5 or more does to the "
            "alchemist (plan §8.2), in \"mishap\".")
    if doc.get("mishap") and not volatile:
        say("has a mishap and is not volatile; only a volatile input flares. Add the "
            "`volatile` working trait or remove the mishap.")
    if "toxic_to_handle" in traits and not doc.get("toxic"):
        say("is toxic to handle and has no toxic document. Say what working it unprotected "
            "does (plan §8.4), in \"toxic\".")
    if doc.get("toxic") and "toxic_to_handle" not in traits:
        say("has a toxic document and is not toxic_to_handle. Add the trait or remove it.")

    count = len(product) + len(working) + bool(doc.get("mishap")) + bool(doc.get("toxic"))
    if count < 3:
        say(f"has {count} discoverable propert{'y' if count == 1 else 'ies'}; every "
            f"alchemist's material needs at least 3 (product traits, working traits, the "
            f"mishap, the toxic document).")
    if product and knowledge.DRAWBACK not in knowledge.anatomy(doc)["kinds"].values():
        say("puts traits in a bottle and has no drawback; every reagent has at least one "
            "(owner, Q7.1). Add a product trait with \"drawback\": true, a working trait "
            "that costs (volatile, corrosive, combustible...), or a mishap.")
    if not product and not any(t in _ALCHEMY_ROLES or t.startswith("solvent:")
                               or t in effectspec.VESSEL_TRAITS for t in traits):
        say("puts nothing in a bottle and has no job at the bench. Give it product traits, "
            "or a role: a vessel trait, a solvent, stabilizer, catalyst or apparatus.")

    ceiling = TIER_CEILING.get(tier, 2)
    dice_cap = dice_max(ALCHEMY_DICE_CEILING.get(tier, "1d4"))
    for label, spec in ([(f"product {i + 1}", s) for i, s in enumerate(product)]
                        + [(k, doc[k]) for k in ("mishap", "toxic") if doc.get(k)]):
        if spec.get("book"):
            continue
        for nested in _walk(spec):
            pts = points(nested)
            if pts is not None and pts > ceiling:
                say(f"{label} ({nested.get('type')} {nested.get('target', '')}) is {pts:g} "
                    f"points; a {tier} house number is at most ±{ceiling}. Bring it inside "
                    f"or mark a printed rule \"book\": true.")
            top = dice_max(nested.get("dice")) if "dice" in nested else None
            if top is not None and dice_cap is not None and top > dice_cap:
                say(f"{label} ({nested.get('type')} {nested.get('dice')}) can roll {top}; a "
                    f"{tier} house die is at most {ALCHEMY_DICE_CEILING.get(tier)} "
                    f"({dice_cap}). Shrink it or mark a printed rule \"book\": true.")

    has_book = any(s.get("book") for s in product)
    if has_book and not doc.get("book"):
        say("carries book traits but is not marked \"book\": true. Mark the document.")
    if doc.get("book") and not has_book:
        say("is marked \"book\": true with no book trait. Remove the mark.")
    colour = doc.get("color")
    if colour not in ("", None) and not (
            isinstance(colour, list) and len(colour) == 3
            # `builtins.all`: this module's own `all()` is the shelf.
            and builtins.all(isinstance(c, (int, float)) and 0 <= c <= 1
                             for c in colour)):
        say("color is three numbers from 0 to 1, [r, g, b], the stage's liquid colour.")
    return out
