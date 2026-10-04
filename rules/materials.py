"""The one door to every craft material: what it is, what it does, and whether it is sound.

`content/materials` is one shelf shared by four crafts (blacksmith, alchemist, enchanter,
leatherworker), and before this module each craft read it through its own loader in its
own dialect. Nothing here replaces those loaders yet (contract §3): this reads the same
files, normalises every entry into one document shape with every field defaulted, so a
file written before the forge revamp still loads, and serves the forge's questions.

Two ideas hold it together, both the owner's rulings (docs/blacksmithing-revamp-plan.md §2):

**One material, many shelves.** Mithral is one document. The leatherworker's mithral
fittings, the enchanter's mithral filings and the alchemist's mithral dust are *forms* of
it: each carries `"material": "mithral"` and keeps its own id (test_alchemist.py pins that
no id is claimed twice, and a merge would have broken four benches). `material_of` walks
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

import copy
import json
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
    }


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
        doc = normalise(doc, doc.get("catalogue", FORGE_CATALOGUE))
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
