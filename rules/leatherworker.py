"""Leatherworking: the bench's rules (docs/leatherworking-revamp-plan.md §6-§13, §17;
docs/leatherworking-contracts.md §7, lane E), and the shelf library the market and the
acquisition hub read.

**The step bench** (most of this file), the forge's shape for the fifth craft: one method at
a time, each its own d20 Craft check, then an always-played minigame whose 0..1 score the
server turns into a quality tier under the leatherworker's ceiling. Twelve methods (owner
Q2.1): Flense, Salt, Tan, Curry, Cut, Stitch, Harden, Tool, Dye, Laminate, Assemble and
Grade. Skin became the cross-craft harvest of a carcass (lane C's `rules/harvest.py`), Cure
became Salt, which really takes salt, Oil folded into Curry, and Line became the lining
piece at Assemble (measured to do nothing, inventory §1).

  check   `plan_step`: what the step would make, the DC itemised, the odds, every rack
          entry's fit in words, the step ceiling and its reasons (your hands, the hide's
          grade, the tannin), the wait of a tannage, the rent;
  roll    the d20 (no naturals: a skill check, CRB p.180). A miss by 4 or less loses the
          time; by 5 or more half the materials are ruined (the book's Craft rule, which
          fixes "every input spent on any failure", inventory §1). On a success the step
          waits behind a token for the game;
  finish  the score becomes the tier, `make` writes the stock and the records, `land`
          shelves them, and a tannage that waits (alum, bark, mineral, planar, rawhide
          drying, a thick hide's lime pit) goes In progress (rules/inprogress.py).

**Every stage lands on the shelf** (owner Q2.3): green hide, salted hide, pelt, leather or
fur or rawhide, panels, plates, lacing, grips, then the finished item. Each is a
`crafting.Stock` with `craft="leatherworker"` whose state travels in `properties` as
`leather.*` tags (law 1's vocabulary, asked by prefix), the forge's way: `Stock` has no
field for a grade or a hide's clock, belongs to no lane in this wave, and its tags survive a
save and load untouched. `Hide` is the record of contracts §4.1 rebuilt from them: ids,
units, a grade and a clock, never a computed number. A finished thing is the forge's
crafted record (plan §13.1) in a `forge_items.ForgedStock`, read by `forge_items.build`
and `Actor.armour_stats` (lane B), so leather armour is the forge's armour model.

**Where you work** (plan §10; owner Q6.4 and answer 3 of 2026-10-08): the field kit works
common and uncommon hides anywhere, Harden included ("add a small kettle to the field kit");
a tannery adds the vats (bark, mineral, planar), the lime pit (a thick hide's Flense) and
rare-and-up hides. Asked of lane G's `places.leather_bench_here`, never of the player's
words. **No vat cap** (the lead's ruling of 2026-10-08, from the owner's "no limit to how
many things are crafting"): vats are rented per tannage as the work needs
(`places.vats_for`), the count shown, never a refusal.

**Mastery** (owner 2026-10-05 and 2026-10-06): every successful step pays through
`worldclass.award_step` (a batch of N is N steps; `MISHAP_LIMIT` still caps what failing
teaches); firsts pay 3 (a product kind made, a hide worked, a property learned by working);
grading pays `STUDY_MP` (1) for each property it reveals, 0 if none.

**Marks are on hold** (`materials.MARKS_HELD`, the owner asked for an explanation first,
2026-10-08): the consumables a step uses are recorded on the stock (`uses`) and the item
(`marks` stays empty), and nothing here applies a mark.

**The shelf library** (the bottom of the file): `Material`, `materials()`, `get`,
`KIND_GLYPH`, `ACQUISITION`, `obtainable` and `hides_from` still serve the market's
counter (`market.kind_staples`), the `/craft/` page's shelf and the acquisition hub
(`rules/benches.py`). The old chain (`Chain`, `preview`) retired with the step bench:
`preview` refuses in words, naming the patterns it knows. The `skin` excursion in
`ACQUISITION` is lane C's to remove when the harvest lands (contracts §1: "the four
ACQUISITION carcass rows ... removal only").
"""
from __future__ import annotations

import copy as _copy
import hashlib
import importlib
import json
import math
from dataclasses import dataclass, field
from math import ceil, floor
from pathlib import Path

from . import worldclass as wc
from pathfindergm import files

TRACK_ID = "leatherworker"


def _lane(name: str):
    """A sibling lane's module, or None while it is not merged (contracts §1). Imported on
    each call, so a test can stand a fake in `sys.modules` (the forge's `_lane`)."""
    try:
        return importlib.import_module(f"rules.{name}")
    except ImportError:
        return None


# One glyph per material kind, for the shelf. A hide must never render as a herb — that
# was the reported bug, and it happened because the shelf had one icon for "content".
# Herbalism owns 🌿 herb, 🍄 fungus, 🦴 monster part, ☠️ poison; none is reused here, and
# the bench asserts across all five crafts that no two maps collide.
KIND_GLYPH: dict[str, str] = {
    "hide": "🦬",        # the beast it came off
    "tannin": "🛢️",      # the bark vat
    "thread": "🧵",
    "oil": "🧴",
    "dye": "🎨",
    "wax": "🕯️",
    "fitting": "🔘",     # a stud, a buckle — the smith's contribution
    # The reserved pool held no vessel, salt or chemical glyph, so the least-wrong
    # symbol wins: a bundle tied for the liming pit. Flagged for reassignment if a
    # better one frees up — it is the only entry here chosen by elimination.
    "treatment": "🪢",
}

METHODS = ("flense", "salt", "tan", "curry", "cut", "stitch", "harden", "tool", "dye",
           "laminate", "assemble", "grade")

# Station icons for the old /craft/ tab's method strip (`benches.method_glyphs` prefers a
# module's own map). Distinct within the track (tests/test_benches.py pins it).
METHOD_GLYPH: dict[str, str] = {
    "flense": "🪒", "salt": "🧂", "tan": "🛢️", "curry": "🧴", "cut": "✂️", "stitch": "🧵",
    "harden": "♨️", "tool": "🖋️", "dye": "🎨", "laminate": "📚", "assemble": "🪡",
    "grade": "🔍",
}

# Hours before an uncured hide is refuse when neither the material nor the rule row says
# otherwise. The herbalist's animal-part clock (`herbprep.ANIMAL_HOURS`), because a hide
# *is* an animal part; pinned equal by the tests so the two cannot drift.
FRESH_HOURS = 48

# Hide sizes, smallest first. Position is what the rules compare.
SIZES = ("fine", "diminutive", "tiny", "small", "medium", "large", "huge", "gargantuan",
         "colossal")


def size_rank(name: str) -> int:
    name = str(name or "medium").strip().lower()
    return SIZES.index(name) + 1 if name in SIZES else SIZES.index("medium") + 1


# --- what the bench makes (plan §4.2, §13.2, §13.6; owner Q1.4) -------------------------------
#
# Picked from this list, never typed (plan §7, Cut: "the pattern is picked from the engine's
# list of products"). `base` is ALWAYS a table key (`tables.ARMOUR` / `SHIELDS`): the
# measured wear defect was a NAME in that field (inventory §0.1). `body` is what the body
# piece must be at Assemble: `plate` (hardened, cuir bouilli: leather armour is boiled in the
# book, plan §3) or `panel` (stitched soft work). `fastenings`: a suit or a shield needs them
# (the forge's two required pieces); worn and carried goods are a body and a lining. Studded
# leather, the armoured coat and steel lamellar are NOT here: the forge finishes them from a
# leather base (owner Q1.3), so a leather armour record says `base_for`. Horn lamellar waits
# on a harvested horn material (plan §4.2, "proposed"), which no catalogue carries yet.
# Hide units per pattern are the rule rows' (`bench.products`).
PRODUCTS: dict[str, dict] = {
    "padded":           {"gear": "armour", "base": "padded", "slot": "armor", "body": "panel",
                         "fastenings": True, "word": "Padded Armour"},
    "quilted cloth":    {"gear": "armour", "base": "quilted cloth", "slot": "armor",
                         "body": "panel", "fastenings": True, "word": "Quilted Coat"},
    "leather armour":   {"gear": "armour", "base": "leather", "slot": "armor", "body": "plate",
                         "fastenings": True, "word": "Leather Armour",
                         "base_for": ["studded leather", "armored coat"]},
    "hide armour":      {"gear": "armour", "base": "hide armour", "slot": "armor",
                         "body": "panel", "fastenings": True, "thick": True,
                         "word": "Hide Armour"},
    "leather lamellar": {"gear": "armour", "base": "leather lamellar", "slot": "armor",
                         "body": "plate", "fastenings": True, "word": "Leather Lamellar"},
    "bone-studded leather": {"gear": "armour", "base": "studded leather", "slot": "armor",
                             "body": "plate", "fastenings": True,
                             "word": "Bone-Studded Leather"},
    "madu":             {"gear": "shield", "base": "madu", "slot": "shield", "body": "plate",
                         "fastenings": True, "word": "Madu"},
    "cloak":            {"gear": "worn", "base": "cloak", "slot": "shoulders", "body": "panel",
                         "word": "Cloak"},
    "boots":            {"gear": "worn", "base": "boots", "slot": "feet", "body": "panel",
                         "word": "Boots"},
    "gloves":           {"gear": "worn", "base": "gloves", "slot": "hands", "body": "panel",
                         "word": "Gloves"},
    "bracers":          {"gear": "worn", "base": "bracers", "slot": "wrists", "body": "panel",
                         "word": "Bracers"},
    "belt":             {"gear": "worn", "base": "belt", "slot": "belt", "body": "panel",
                         "word": "Belt"},
    "cap":              {"gear": "worn", "base": "cap", "slot": "head", "body": "panel",
                         "word": "Cap"},
    # Carried goods (owner Q3.3): a book rule where one exists, flavour otherwise. The kit
    # roll at Superior is masterwork artisan's tools, +2 circumstance (`kit_terms`).
    "satchel":          {"gear": "worn", "base": "satchel", "slot": "", "body": "panel",
                         "carried": True, "word": "Satchel"},
    "sheath":           {"gear": "worn", "base": "sheath", "slot": "", "body": "panel",
                         "carried": True, "word": "Sheath"},
    "quiver":           {"gear": "worn", "base": "quiver", "slot": "", "body": "panel",
                         "carried": True, "word": "Quiver"},
    "kit roll":         {"gear": "worn", "base": "kit roll", "slot": "", "body": "panel",
                         "carried": True, "word": "Kit Roll"},
}
# What Cut makes besides a pattern's panels: pieces the forge takes (plan §4.4) and the
# fastenings a suit is laced with.
CUT_PIECES = {"lacing": "Lacing Set", "grip": "Grip"}

FORMS = ("green", "salted", "pelt", "leather", "fur", "rawhide", "panel", "plate", "lacing",
         "grip", "scales", "scrap")
TANNED_FORMS = ("leather", "fur", "rawhide", "panel", "plate", "lacing", "grip")
HIDE_FORMS = ("green", "salted", "pelt", "leather", "fur", "rawhide")
RECORD_SCHEMA = 3

GROUPS = {"green": "Green hides", "salted": "Salted hides", "pelt": "Pelts (fleshed)",
          "leather": "Leather and rawhide", "fur": "Leather and rawhide",
          "rawhide": "Leather and rawhide", "panel": "Panels and plates",
          "plate": "Panels and plates", "lacing": "Bases and grips", "grip": "Bases and grips",
          "scales": "Panels and plates", "scrap": "Scraps",
          "tannin": "Tannins", "oil": "Oils and waxes", "wax": "Oils and waxes",
          "thread": "Threads and lacing", "dye": "Dyes", "salt": "Salt and treatments",
          "treatment": "Salt and treatments", "fitting": "Fittings",
          "item": "Finished work", "old": "Old work"}

OLD_WORK = "made at the old bench: it can be worn or sold, not worked further"


# --- the rule rows -----------------------------------------------------------------------------

def track() -> wc.Track:
    return wc.get(TRACK_ID)


def bench_rules() -> dict:
    """The track JSON's `bench` block: every number the plan marks proposed."""
    return dict(track().data.get("bench") or {})


def method_row(method: str) -> dict | None:
    return (bench_rules().get("methods") or {}).get(str(method or "").strip().lower())


def method_level(method: str) -> int:
    t = track()
    for row in sorted(t.levels, key=lambda r: r.level):
        if method in row.methods:
            return row.level
    return t.max_level + 1


def tannage_row(kind: str) -> dict:
    return dict((bench_rules().get("tannages") or {}).get(str(kind or ""), {}) or {})


def old_method(name: str) -> str:
    """What a removed method became (cure -> salt, oil -> curry, line -> assemble; skin
    left the bench for the harvest and becomes nothing here)."""
    key = str(name or "").strip().lower()
    return str((track().data.get("old_methods") or {}).get(key, key))


def _mw_index() -> int:
    return int(bench_rules().get("masterwork_index", 3))


def level_tier_rank(level: int) -> int:
    """The rarest hide this level works (plan §17.1): uncommon at 1, exotic at 2,
    legendary at 3 and every endless level after."""
    return wc.tier_rank(track().at(int(level or 1)).max_tier)


def level_for_rank(rank: int) -> int | None:
    for row in sorted(track().levels, key=lambda r: r.level):
        if wc.tier_rank(row.max_tier) >= int(rank):
            return row.level
    return None


def units_of_size(size: str) -> float:
    """Hide units a hide of this size is (plan §5.5): Medium 1, doubling per size."""
    table = bench_rules().get("hide_units") or {}
    return float(table.get(str(size or "medium").strip().lower(), table.get("medium", 1)))


def quarters(units: float) -> int:
    """Units in quarters, the store's whole number (contracts §4.1)."""
    return int(round(float(units or 0) * 4))


def units_word(q: int) -> str:
    """"1 unit", "2.5 units", "a quarter unit"."""
    u = int(q) / 4
    if int(q) == 1:
        return "a quarter unit"
    if int(q) == 2:
        return "half a unit"
    text = f"{u:g}"
    return f"{text} unit{'' if u == 1 else 's'}"


def product_units(product: str, part: str, actor=None) -> int:
    """Quarters of hide a pattern's body or lining takes (plan §5.5). A suit's body scales
    with its wearer's size (`suit_by_size`); everything else is the Medium figure."""
    rules = bench_rules()
    row = (rules.get("products") or {}).get(product) or {}
    if part == "lining":
        return quarters(float(row.get("lining", 0) or 0))
    units = float(row.get("body", 0) or 0)
    info = PRODUCTS.get(product) or {}
    if info.get("gear") == "armour" and actor is not None:
        size = str(getattr(actor, "size", "medium") or "medium").lower()
        units = float((rules.get("suit_by_size") or {}).get(size, units))
    return quarters(units)


def grade_cap(grade) -> int | None:
    """The highest quality index work from a hide of this grade can reach (plan §5.7), or
    None for no cap. Grade 0 is reject: scraps only."""
    try:
        g = int(grade)
    except (TypeError, ValueError):
        return None
    if g <= 0:
        return 0
    got = (bench_rules().get("grade_caps") or {}).get(str(g))
    return None if got is None else int(got)


# --- the crafter's own bonus ------------------------------------------------------------------

def check_terms(actor, level: int) -> list[dict]:
    """What a leatherworker adds to the die, itemised.

    **d20 + track level + half character level + Intelligence**, plus half the Craft
    ranks (option A, 2026-10-07; `tradecraft.bench_terms`), always last. Itemised rather
    than summed because "+9" says nothing and "Leatherworker 2, half level +3, Int +2"
    says which to improve.
    """
    track_level = max(0, int(level or 0))
    char_level = max(1, int(getattr(actor, "level", 1) or 1)) if actor else 1
    intelligence = int(actor.ability_mod("int")) if actor is not None else 0
    from . import tradecraft

    return [
        {"label": f"Leatherworker {track_level}", "value": track_level},
        # Half level, rounded down, as every half-level term in 1e rounds.
        {"label": f"half character level ({char_level})", "value": char_level // 2},
        {"label": "Intelligence", "value": intelligence},
        # Half the Craft ranks: tanning and leatherwork are Craft (leather), and this
        # game keeps one Craft (option A, 2026-10-07; `tradecraft.bench_terms`).
        *tradecraft.bench_terms(actor, "leatherworker"),
    ]


def check_bonus(actor, level: int) -> int:
    return sum(t["value"] for t in check_terms(actor, level))


def kit_terms(actor) -> list[dict]:
    """A masterwork kit roll: the book's masterwork artisan's tools, +2 circumstance on the
    craft's checks (Core p.158, UE p.77; plan §13.6). A kit roll this bench made at
    Superior or better, carried. Kept out of `check_terms`, whose Craft-ranks term is
    pinned last (tests/test_craft_at_the_benches.py), and asked of the record, never of a
    name."""
    for item in (getattr(actor, "stock", None) or {}).values():
        rec = getattr(item, "record", None)
        if not isinstance(rec, dict) or rec.get("craft") != TRACK_ID:
            continue
        if rec.get("product") == "kit roll" and int(getattr(item, "count", 0) or 0) > 0 \
                and int(rec.get("quality_index") or 0) >= _mw_index():
            return [{"label": "masterwork kit roll (circumstance)", "value": 2}]
    return []


# --- material documents (lane D's door) --------------------------------------------------------

def material(mid: str) -> dict | None:
    """The normalised material document (contracts §3) through `rules/materials.py`."""
    mid = str(mid or "").strip().lower()
    if not mid:
        return None
    mats = _lane("materials")
    if mats is None:
        return None
    try:
        return mats.get(mid)
    except Exception:          # noqa: BLE001 - a bad document is "no such material"
        return None


def _working(doc: dict | None) -> list[str]:
    out = []
    for w in (doc or {}).get("working") or []:
        trait = w.get("trait") if isinstance(w, dict) else w
        if trait:
            out.append(str(trait))
    return out


def _has(doc: dict | None, trait: str) -> bool:
    return trait in _working(doc)


def doc_name(mid: str) -> str:
    doc = material(mid)
    return str((doc or {}).get("name") or str(mid or "").replace("-", " ").title())


def _shelf_row(mid: str):
    """The catalogue row as written (`materials()` below), for the two fields the one door's
    normalised document does not carry: a hide's `size` and `fresh_hours`. Measured
    2026-10-08: `materials.get("horse-hide")` has neither, so a Large horse hide read as one
    Medium unit and every hide's own clock fell back to the rule row's."""
    try:
        return materials().get(str(mid or "").strip().lower())
    except Exception:          # noqa: BLE001 - no row is a Medium hide on the default clock
        return None


def hide_size(mid: str) -> str:
    row = _shelf_row(mid)
    return str(getattr(row, "size", "") or "medium")


def tannage_kind(tannin_id: str) -> str:
    """The tannage a tannin makes ("bark", "brain", ...), from its document's `tannage`
    field (plan §8.1). "" for no tannin; "rawhide" is said by the form, not here."""
    doc = material(tannin_id)
    return str((doc or {}).get("tannage") or "")


def _is_salt(doc: dict | None) -> bool:
    mats = _lane("materials")
    if mats is not None and hasattr(mats, "is_salt") and doc is not None:
        try:
            return bool(mats.is_salt(doc))
        except Exception:      # noqa: BLE001
            return False
    return bool(doc and (doc.get("id") == "curing-salt" or doc.get("salt") is True))


def _grip_capable(doc: dict | None) -> bool:
    return "haft" in (((doc or {}).get("pieces") or {}).get("weapon") or [])


def _rank(tier: str) -> int:
    return wc.tier_rank(str(tier or "common"))


def dc_of(doc: dict | None, tier: str = "") -> int:
    """An intermediate step's DC: the material's authored `craft_dc`, else 5 + 5 x rank
    (plan §7, the forge's rule). No +2 a stage: the measured creep was DC 38 for a red
    dragonhide suit (inventory §1)."""
    stated = (doc or {}).get("craft_dc")
    if stated is not None:
        try:
            return int(stated)
        except (TypeError, ValueError):
            pass
    return 5 + 5 * _rank(tier or (doc or {}).get("tier") or "common")


# --- what the leatherworker puts on the shelf --------------------------------------------------

def _enc(text: str) -> str:
    return str(text).replace(" ", "_")


def _dec(text: str) -> str:
    return str(text).replace("_", " ")


def _slug(text: str) -> str:
    slug = "".join(c if c.isalnum() else "-" for c in str(text).lower()).strip("-")
    while "--" in slug:
        slug = slug.replace("--", "-")
    return slug


@dataclass
class Hide:
    """One leather stock entry, any form (contracts §4.1): ids, units in quarters, a grade,
    the tannin it was tanned with, laminations, and the clock's two minutes. Every number a
    reader shows is computed from these."""
    form: str
    material: str
    quarters: int = 4
    grade: int = 2
    tannage: str = ""            # the tannin's id ("oak-bark"); "" when untanned
    passes: int = 0
    quality: int | None = None
    harvested_at: int | None = None
    salted_at: int | None = None
    creature: str = ""           # a generic hide's beast (bestiary id), plan §5.4
    tier: str = ""               # set when the beast and not the document decides
    worked: list = field(default_factory=list)   # flense, curry, stitch, harden, tool...
    pattern: str = ""            # the product its panels or plates were cut for
    part: str = ""               # "body" or "lining"
    uses: dict = field(default_factory=dict)     # consumable kind -> material id
    name: str = ""

    def copy(self) -> "Hide":
        return _copy.deepcopy(self)

    @property
    def units(self) -> float:
        return int(self.quarters) / 4

    @property
    def salted(self) -> bool:
        return self.salted_at is not None

    @property
    def doc(self) -> dict | None:
        return material(self.material)

    @property
    def tier_name(self) -> str:
        return self.tier or str((self.doc or {}).get("tier") or "common")

    @property
    def rank(self) -> int:
        return _rank(self.tier_name)

    @property
    def tannage_kind(self) -> str:
        if self.form == "rawhide" or (self.form in ("panel", "plate", "lacing", "grip")
                                      and not self.tannage and "rawhide" in self.worked):
            return "rawhide"
        return tannage_kind(self.tannage) if self.tannage else ""

    @property
    def tanned(self) -> bool:
        return self.form in TANNED_FORMS

    @property
    def hair_on(self) -> bool:
        return self.form == "fur" or "fur" in self.worked

    def tags(self) -> list[str]:
        t = [f"leather.form.{self.form}", f"leather.material.{self.material}",
             f"leather.q.{int(self.quarters)}", f"leather.grade.{int(self.grade)}"]
        if self.tannage:
            t.append(f"leather.tannage.{self.tannage}")
        if self.passes:
            t.append(f"leather.passes.{int(self.passes)}")
        if self.quality is not None:
            t.append(f"leather.quality.{int(self.quality)}")
        if self.harvested_at is not None:
            t.append(f"leather.harvested.{int(self.harvested_at)}")
        if self.salted_at is not None:
            t.append(f"leather.salted.{int(self.salted_at)}")
        if self.creature:
            t.append(f"leather.creature.{self.creature}")
        if self.tier:
            t.append(f"leather.tier.{self.tier}")
        t += [f"leather.worked.{w}" for w in self.worked]
        if self.pattern:
            t.append(f"leather.pattern.{_enc(self.pattern)}")
        if self.part:
            t.append(f"leather.part.{self.part}")
        for kind, mid in sorted(self.uses.items()):
            t.append(f"leather.use.{kind}.{mid}")
        t.append("leather.schema.1")
        return t

    @classmethod
    def from_tags(cls, tags, *, name: str = "") -> "Hide | None":
        tags = [str(x) for x in (tags or []) if str(x).startswith("leather.")]
        if not any(x.startswith("leather.form.") for x in tags):
            return None
        h = cls(form="", material="", name=name)
        for x in tags:
            parts = x.split(".")
            head, rest = parts[1], parts[2:]
            val = ".".join(rest)
            try:
                if head == "form":
                    h.form = val
                elif head == "material":
                    h.material = val
                elif head == "q":
                    h.quarters = int(val)
                elif head == "grade":
                    h.grade = int(val)
                elif head == "tannage":
                    h.tannage = val
                elif head == "passes":
                    h.passes = int(val)
                elif head == "quality":
                    h.quality = int(val)
                elif head == "harvested":
                    h.harvested_at = int(val)
                elif head == "salted":
                    h.salted_at = int(val)
                elif head == "creature":
                    h.creature = val
                elif head == "tier":
                    h.tier = val
                elif head == "worked":
                    h.worked.append(val)
                elif head == "pattern":
                    h.pattern = _dec(val)
                elif head == "part":
                    h.part = val
                elif head == "use" and len(rest) >= 2:
                    h.uses[rest[0]] = ".".join(rest[1:])
            except ValueError:
                continue
        return h if h.form and h.material else None

    @classmethod
    def from_stock(cls, item) -> "Hide | None":
        if str(getattr(item, "craft", "") or "") != TRACK_ID:
            return None
        return cls.from_tags(getattr(item, "properties", None),
                             name=str(getattr(item, "base", "") or ""))

    def digest(self) -> str:
        sig = json.dumps([t for t in self.tags()])
        return hashlib.md5(sig.encode()).hexdigest()[:10]


def _lead_word(mid: str) -> str:
    """"Winter Wolf" out of "Winter Wolf Pelt": the hide's name with its material word off,
    so a pelt makes a "Winter Wolf Cloak" and not a "Winter Wolf Pelt Cloak"."""
    lead = doc_name(mid)
    for word in ("Hide", "Pelt", "Skin", "Leather", "Plate", "Shell", "Cloth", "Hide Leather"):
        if lead.endswith(" " + word):
            return lead[: -(len(word) + 1)]
    return lead


def _pattern_word(pattern: str) -> str:
    info = PRODUCTS.get(pattern) or {}
    return str(info.get("word") or CUT_PIECES.get(pattern) or pattern.title())


def hide_name(h: Hide) -> str:
    """"Green Deer Hide", "Elk Leather (oak bark)", "Stitched Elk Panels for Hide Armour"."""
    lead = _lead_word(h.material)
    full = doc_name(h.material)
    if h.form == "green":
        return f"Green {full}"
    if h.form == "salted":
        return f"Salted {full}"
    if h.form == "pelt":
        return f"{lead} Pelt, fleshed" + (", salted" if h.salted else "")
    if h.form == "scrap":
        return f"{lead} Scraps"
    tan = doc_name(h.tannage).lower() if h.tannage else ""
    if h.form in ("leather", "fur", "rawhide"):
        noun = {"leather": "Leather", "fur": "Fur", "rawhide": "Rawhide"}[h.form]
        words = []
        if "curry" in h.worked:
            words.append("Curried")
        if "tool" in h.worked:
            words.append("Tooled")
        name = " ".join(words + [lead, noun])
        if tan:
            name += f" ({tan})"
        if h.passes:
            name += f", laminated ×{h.passes}"
        return name
    if h.form in ("lacing", "grip"):
        return f"{lead} {CUT_PIECES[h.form]}"
    if h.form in ("panel", "plate"):
        words = []
        if h.form == "plate":
            words.append("Hardened")
        elif "stitch" in h.worked:
            words.append("Stitched")
        if "tool" in h.worked:
            words.append("Tooled")
        noun = "Plates" if h.form == "plate" else "Panels"
        what = _pattern_word(h.pattern) + (" lining" if h.part == "lining" else "")
        return " ".join(words + [lead, noun, "for", what])
    return f"{lead} {h.form.title()}"


def to_stock(h: Hide):
    """The leather product as a shelf entry: `craft` leatherworker, the state in tags."""
    from .crafting import Stock

    return Stock(base=h.name or hide_name(h), tier=h.tier_name, count=1, craft=TRACK_ID,
                 kind="leather-stock", how=["ingredient"],
                 from_materials=[m for m in [h.material, *h.uses.values()] if m],
                 properties=h.tags())


def stock_key(h: Hide) -> str:
    """The shelf key: the name's slug and the digest of what it is. Two Elk Leathers with
    different grades are different things and must not stack."""
    return f"{_slug(h.name or hide_name(h))}~{h.digest()}"


def put_hide(actor, h: Hide, count: int = 1) -> str:
    """Put a leather stock entry on the shelf, stacking with an identical one. Returns its
    key. **The one writer of hide stock**: lane C's harvest calls it with the green hide it
    took (`make_hide(..., form="green", harvested_at=now)`), so the bench reads a hide from
    a carcass and one from a counter the same way."""
    if not h.name:
        h.name = hide_name(h)
    key = stock_key(h)
    have = (actor.stock or {}).get(key)
    if have is not None and not getattr(have, "work", None):
        have.count = int(have.count or 0) + int(count)
    else:
        while key in (actor.stock or {}):
            key += "+"
        st = to_stock(h)
        st.count = int(count)
        actor.stock[key] = st
    return key


def make_hide(material_id: str, *, form: str = "green", units: float | None = None,
              grade: int = 2, harvested_at: int | None = None,
              salted_at: int | None = None, creature: str = "", tier: str = "",
              tannage: str = "") -> Hide:
    """A hide in contracts §4.1's shape, for the harvest (lane C) or a test. `units` from
    the hide document's size when not given (plan §5.5)."""
    if units is None:
        units = units_of_size(hide_size(material_id))
    return Hide(form=form, material=str(material_id), quarters=quarters(units),
                grade=int(grade), harvested_at=harvested_at, salted_at=salted_at,
                creature=str(creature or ""), tier=str(tier or ""), tannage=tannage)


def record_of_hide(item) -> dict | None:
    """Contracts §4.1's record of a leather stock entry, rebuilt from its tags (the one
    reader for every lane that wants the dict)."""
    h = item if isinstance(item, Hide) else Hide.from_stock(item)
    if h is None:
        return None
    return {"id": h.material, "kind": "leather-stock", "craft": TRACK_ID,
            "count": int(getattr(item, "count", 1) or 1), "material": h.material,
            "form": h.form, "units": h.units, "grade": h.grade,
            "tannage": h.tannage or None, "passes": h.passes, "marks": [],
            "quality_index": h.quality, "hardened": h.form == "plate",
            "harvested_at": h.harvested_at, "salted": h.salted, "salted_at": h.salted_at,
            "creature": h.creature or None, "schema": 1}


# --- the clock (plan §6) ---------------------------------------------------------------------

def freshness(h: Hide, now: int) -> dict:
    """{"spoiled", "hours_left", "why", "clock"}: computed on read from `harvested_at` and
    `salted_at`, never stored (contracts §4.1). A green hide or an unsalted pelt keeps 48
    hours from the harvest (a document's `fresh_hours` wins); salt stops the clock for six
    weeks, after which it runs again. Tanned work never spoils. Lane C serves the same
    question for its harvest sheet as `harvest.freshness`; asked there first when it
    exists, so the two can never disagree."""
    harvest = _lane("harvest")
    fn = getattr(harvest, "freshness", None) if harvest is not None else None
    if callable(fn):
        try:
            got = fn(record_of_hide(h), now)
            if isinstance(got, dict) and "spoiled" in got:
                return {"spoiled": bool(got["spoiled"]),
                        "hours_left": got.get("hours_left"),
                        "why": str(got.get("why") or ""), "clock": got.get("clock", True)}
        except Exception:      # noqa: BLE001 - our own answer below
            pass
    if h.form not in ("green", "salted", "pelt") or h.harvested_at is None:
        return {"spoiled": False, "hours_left": None, "why": "", "clock": False}
    rules = bench_rules()
    row = _shelf_row(h.material)
    window = int(getattr(row, "fresh_hours", None) or rules.get("fresh_hours")
                 or FRESH_HOURS) * 60
    now = int(now)
    if h.salted_at is not None:
        keep = int(rules.get("salted_keep_minutes", 60480))
        until = int(h.salted_at) + keep
        if now < until:
            return {"spoiled": False, "hours_left": (until - now) // 60, "clock": False,
                    "why": "salted: it keeps"}
        # The salt has done what it can; the hide's own clock runs again from there.
        left = until + window - now
    else:
        left = int(h.harvested_at) + window - now
    if left <= 0:
        return {"spoiled": True, "hours_left": 0, "clock": True,
                "why": "it has spoiled: scraps and glue stock now, nothing more"}
    return {"spoiled": False, "hours_left": left // 60, "clock": True,
            "why": f"spoils in {_span(left)} unless salted or tanned"}


def _span(minutes: int) -> str:
    from . import sky

    return sky.span_words(int(minutes))


# --- the rack --------------------------------------------------------------------------------

@dataclass
class Piece:
    """One rack entry (UI plan §6.2): raw material from the satchel's counts, leather stock
    from the shelf, or a finished leather record. `count` is pieces (a stack of hides) or
    measures (a consumable)."""
    key: str
    name: str
    material: str
    form: str
    count: int
    tier: str = "common"
    hide: Hide | None = None
    kind: str = ""
    record: dict | None = None
    old: str = ""
    spoiled: bool = False

    @property
    def rank(self) -> int:
        return _rank(self.tier)

    @property
    def quarters(self) -> int:
        return int(self.hide.quarters) if self.hide is not None else 0

    @property
    def doc(self) -> dict | None:
        return material(self.material)


def _bought_hide(mid: str, doc: dict, n: int, actor, now: int) -> Hide:
    """A hide in the satchel as a bare count: a counter's purchase (`goods.deliver` puts a
    craft material there). Sold tanned, never green (plan §9; lane D's proposal): the
    document's `sold_as` form, oak bark, grade 2, its units by its size. An old excursion's
    raw hide with a clock (`picked_at`) is green, or salted if the satchel's salt kept it."""
    rules = bench_rules()
    bought = rules.get("bought") or {}
    picked = (getattr(actor, "picked_at", None) or {}).get(mid)
    q = quarters(units_of_size(hide_size(mid)))
    if picked is not None:
        salted = bool((getattr(actor, "preserved", None) or {}).get(mid))
        return Hide(form="salted" if salted else "green", material=mid, quarters=q,
                    grade=int(bought.get("grade", 2)), harvested_at=int(picked),
                    salted_at=int(picked) if salted else None)
    form = str(doc.get("sold_as") or "leather")
    if form not in ("leather", "fur"):
        form = "leather"
    return Hide(form=form, material=mid, quarters=q, grade=int(bought.get("grade", 2)),
                tannage=str(bought.get("tannage") or "oak-bark"))


def _consumable_form(doc: dict) -> str:
    kind = str(doc.get("kind") or "")
    if _is_salt(doc):
        return "salt"
    return kind


def _leather_relevant(doc: dict | None) -> bool:
    if not doc:
        return False
    mats = _lane("materials")
    if mats is not None and hasattr(mats, "is_leather"):
        try:
            if mats.is_leather(doc):
                return True
        except Exception:      # noqa: BLE001
            pass
    return str(doc.get("kind") or "") in ("hide",) or _is_salt(doc)


def rack(actor, now: int = 0, reserved: dict | None = None) -> list[Piece]:
    """Everything the bench can reach for: only what is carried (UI plan §6.2). Raw
    material from `Actor.inventory` (bought, gathered), leather stock and finished leather
    work from the shelf. Work In progress is not on the rack: it is in the section, where
    it is collected (`inprogress.entries`). `reserved` is `{key: count}` held by a step
    between its roll and its finish."""
    from . import inprogress

    reserved = reserved or {}
    out: list[Piece] = []
    if actor is None:
        return out
    for iid, n in sorted((getattr(actor, "inventory", {}) or {}).items()):
        if int(n or 0) <= 0:
            continue
        doc = material(iid)
        if not _leather_relevant(doc):
            continue
        key = f"inv:{iid}"
        count = int(n) - int(reserved.get(key, 0))
        if count <= 0:
            continue
        if doc.get("kind") == "hide":
            h = _bought_hide(iid, doc, count, actor, now)
            h.name = hide_name(h)
            spoiled = freshness(h, now)["spoiled"]
            out.append(Piece(key=key, name=h.name, material=iid, form=h.form, count=count,
                             tier=h.tier_name, hide=h, kind="hide", spoiled=spoiled))
        else:
            out.append(Piece(key=key, name=str(doc.get("name") or iid), material=iid,
                             form=_consumable_form(doc), count=count,
                             tier=str(doc.get("tier") or "common"),
                             kind=str(doc.get("kind") or "")))
    for sid, st in sorted((getattr(actor, "stock", {}) or {}).items(),
                          key=lambda kv: str(kv[1].name).lower()):
        if inprogress.work_of(st, now) is not None:
            continue
        key = f"stock:{sid}"
        count = int(st.count or 0) - int(reserved.get(key, 0))
        rec = getattr(st, "record", None)
        if isinstance(rec, dict) and rec.get("craft") == TRACK_ID:
            if count > 0:
                out.append(Piece(key=key, name=st.name, material=str(
                    ((rec.get("pieces") or {}).get("body") or {}).get("material") or ""),
                    form="item", count=count, tier=str(rec.get("tier") or "common"),
                    record=rec, kind="item"))
            continue
        h = Hide.from_stock(st)
        if h is None or count <= 0:
            continue
        spoiled = freshness(h, now)["spoiled"]
        out.append(Piece(key=key, name=st.name, material=h.material, form=h.form,
                         count=count, tier=h.tier_name, hide=h, kind="hide",
                         spoiled=spoiled))
    return out


def piece_view(p: Piece, actor=None, now: int = 0) -> dict:
    """One rack row as the page draws it: the swatch and surface from the document (UI
    §4), the units in words, the grade, the clock and the badges. The page computes no
    number."""
    doc = p.doc or {}
    mats = _lane("materials")
    colour = str(doc.get("color") or "")
    if not colour and mats is not None:
        colour = str((getattr(mats, "KIND_COLOUR", {}) or {}).get(doc.get("kind"), ""))
    d = {"key": p.key, "name": p.name, "material": p.material, "form": p.form,
         "group": GROUPS.get(p.form, "Other"), "count": p.count, "tier": p.tier,
         "rank": p.rank, "kind": p.kind,
         "glyph": KIND_GLYPH.get(str(doc.get("kind") or ""), KIND_GLYPH["hide"]),
         "color": colour or "#a0764a", "surface": str(doc.get("surface") or ""),
         "unknown": _unknown(actor, doc), "old": p.old, "spoiled": p.spoiled}
    h = p.hide
    if h is not None:
        fresh = freshness(h, now)
        d.update({"units": h.units, "units_words": units_word(h.quarters),
                  "total_units": h.units * p.count, "grade": h.grade,
                  "grade_words": f"grade {h.grade}" if h.grade else "reject",
                  "grade_cap": grade_cap(h.grade),
                  "tannage": h.tannage or None, "tannage_kind": h.tannage_kind or None,
                  "passes": h.passes, "quality": h.quality,
                  "quality_name": wc.quality_name(h.quality) if h.quality is not None
                  else None,
                  "pattern": h.pattern or None, "part": h.part or None,
                  "clock": fresh, "badges": _badges(h, fresh),
                  "creature": h.creature or None})
    if p.record is not None:
        d["record"] = p.record
    return d


def _badges(h: Hide, fresh: dict) -> list[str]:
    out = []
    if h.form == "green":
        out.append("green")
    if h.salted:
        out.append("salted")
    if fresh.get("spoiled"):
        out.append("spoiled")
    for w, word in (("curry", "curried"), ("stitch", "stitched"), ("tool", "tooled"),
                    ("dye", "dyed")):
        if w in h.worked:
            out.append(word)
    if h.form == "plate":
        out.append("hardened")
    if h.passes:
        out.append(f"laminated ×{h.passes}")
    return out


def _unknown(actor, doc: dict | None) -> int:
    kn = _lane("knowledge")
    if kn is None or actor is None or not doc:
        return 0
    try:
        keys = list(kn.property_keys(doc))
    except Exception:          # noqa: BLE001
        return 0
    entry = (getattr(actor, "herb_known", None) or {}).get(str(doc.get("id") or "")) or {}
    known = set(entry.get("keys") or [])
    return sum(1 for k in keys if k not in known)


# --- where you work (lane G, contracts §8) ----------------------------------------------------

_NOWHERE = {"at": None, "tannery": None, "field_kit": False, "tiers": (), "vats": False}


def where_here(scene, actor, known=()) -> dict:
    """Lane G's `places.leather_bench_here`: {"at": "tannery" | "field" | None, "tannery",
    "field_kit", "tiers", "vats"}. Read from the scene's coordinate and the pack, never the
    player's words (plan §10)."""
    places = _lane("places")
    fn = getattr(places, "leather_bench_here", None) if places is not None else None
    if fn is None:
        return dict(_NOWHERE)
    try:
        got = dict(fn(scene, actor, known) or {})
    except Exception:          # noqa: BLE001 - a place we cannot read is no bench
        return dict(_NOWHERE)
    got["tiers"] = tuple(got.get("tiers") or ())
    return got


def rent_cp(scene, where: dict, minutes: int, known=()) -> int:
    """The tannery yard's hours (lane G's `market.tannery_rent`): nothing in the field or
    at your own tannery. Charged at the roll, beside the one clock door, as the forge's."""
    if not (where or {}).get("tannery") or minutes <= 0:
        return 0
    market = _lane("market")
    fn = getattr(market, "tannery_rent", None) if market is not None else None
    if fn is None:
        return 0
    return max(0, int(fn(scene, minutes / 60, known)))


def vat_rent_cp(scene, where: dict, wait_minutes: int, vats: int, known=()) -> int:
    """A vat tannage's rent for its whole wait, paid when the hides go in (lane G's
    `market.vat_rent`: "a rent charged at collection would let a player walk away from
    the bill")."""
    if not (where or {}).get("tannery") or wait_minutes <= 0 or vats <= 0:
        return 0
    market = _lane("market")
    fn = getattr(market, "vat_rent", None) if market is not None else None
    if fn is None:
        return 0
    return max(0, int(fn(scene, wait_minutes / 1440, vats, known)))


def vats_for(quarters_total: int) -> int:
    """How many vats a batch fills (lane G's `places.vats_for`). The count is shown and
    priced, never a gate (no vat cap, the lead's ruling of 2026-10-08)."""
    places = _lane("places")
    fn = getattr(places, "vats_for", None) if places is not None else None
    units = int(quarters_total) / 4
    if fn is not None:
        return int(fn(units))
    return int(math.ceil(units / 4)) if units > 0 else 0


def methods_view(level: int, where: dict | None = None) -> list[dict]:
    """The method strip (UI plan §6.1): every method in a tanner's order, with its lock in
    words: "Leatherworker 2", "Needs a tannery", "Needs a field kit or a tannery". A
    tannage's own place is Tan's to say at check, because one Tan is a kit's (brain) and
    another a vat's (bark)."""
    where = where or dict(_NOWHERE)
    rules = bench_rules()
    out = []
    for mid in rules.get("order") or METHODS:
        row = (rules.get("methods") or {}).get(mid) or {}
        need = method_level(mid)
        reason = ""
        if need > int(level):
            reason = f"Leatherworker {need}"
        elif row.get("where") == "tannery" and not where.get("tannery"):
            reason = "Needs a tannery"
        elif not where.get("at"):
            reason = "Needs a field kit or a tannery"
        out.append({"id": mid, "name": row.get("name", mid.title()), "level": need,
                    "where": row.get("where", "kit"), "bulk": bool(row.get("bulk")),
                    "locked": bool(reason), "lock_reason": reason,
                    "takes": row.get("takes", ""), "makes": row.get("makes", ""),
                    "glyph": METHOD_GLYPH.get(mid, "")})
    return out


def products_view(actor=None) -> list[dict]:
    """The patterns Cut and Assemble pick from (never typed): what each is, its book DC,
    and the hide units its body and lining take, in words."""
    out = []
    for pid, info in PRODUCTS.items():
        body = product_units(pid, "body", actor)
        lining = product_units(pid, "lining", actor)
        out.append({"id": pid, "name": info["word"], "gear": info["gear"],
                    "base": info["base"], "slot": info.get("slot") or "",
                    "carried": bool(info.get("carried")), "body_form": info["body"],
                    "fastenings": bool(info.get("fastenings")),
                    "thick": bool(info.get("thick")),
                    "body_units": body / 4, "body_words": units_word(body),
                    "lining_units": lining / 4,
                    "lining_words": units_word(lining) if lining else "",
                    "dc": product_dc(pid), "base_for": list(info.get("base_for") or [])})
    for pid, word in CUT_PIECES.items():
        q = product_units(pid, "body", actor)
        out.append({"id": pid, "name": word, "gear": "piece", "base": "", "slot": "",
                    "carried": False, "body_form": pid, "fastenings": False,
                    "thick": False, "body_units": q / 4, "body_words": units_word(q),
                    "lining_units": 0, "lining_words": "", "dc": None, "base_for": []})
    return out


def product_dc(product: str) -> int:
    """The book's Craft DC (plan §7): a suit or shield 10 + its armour bonus, worn and
    carried goods a typical item, 10."""
    from .tables import ARMOUR, SHIELDS

    info = PRODUCTS.get(product) or {}
    dcs = bench_rules().get("book_dc") or {}
    if info.get("gear") == "armour":
        return int(dcs.get("armour_base", 10)) + int((ARMOUR.get(info["base"]) or {}).get(
            "ac", 0))
    if info.get("gear") == "shield":
        return int(dcs.get("armour_base", 10)) + int((SHIELDS.get(info["base"]) or {}).get(
            "ac", 0))
    return int(dcs.get("goods", 10))


# --- whether one thing fits a slot --------------------------------------------------------------

METHOD_SLOTS = {
    "flense": ("hide",),
    "salt": ("hide", "salt"),
    "tan": ("hide", "tannin"),
    "curry": ("piece", "oil"),
    "cut": ("hide",),
    "stitch": ("piece", "thread"),
    "harden": ("piece",),
    "tool": ("piece", "wax"),
    "dye": ("piece", "dye", "mordant"),
    "laminate": ("piece",),
    "assemble": ("body", "fastenings", "lining"),
}
OPTIONAL = {"tan": ("tannin",), "tool": ("wax",), "dye": ("mordant",),
            "assemble": ("fastenings", "lining")}

_MISSING = {
    "hide": "Put a hide on the beam.",
    "salt": "Add curing salt.",
    "piece": "Put a piece on the bench.",
    "oil": "Choose an oil.",
    "thread": "Choose a thread.",
    "dye": "Choose a dye.",
    "body": "Put a body in the body slot: panels or plates cut for what you are making.",
    "fastenings": "Put fastenings in the fastenings slot: a lacing set or a fitting.",
}


def _plated(pattern: str) -> bool:
    return (PRODUCTS.get(pattern) or {}).get("body") == "plate"


def fit_reason(method: str, slot: str, p: Piece, *, product: str = "",
               batch: int = 1) -> str:
    """Why this rack entry cannot go in this slot for this method, in words, or "" when it
    fits. Every dimmed row carries one (UI plan §6.2: never colour alone)."""
    if p.old:
        return p.old
    if p.count <= 0:
        return "there is none of it left"
    f, h, doc = p.form, p.hide, p.doc or {}
    hide_slot = slot in ("hide", "piece", "body", "lining")
    if hide_slot and h is None:
        return "that is not a hide or a piece of one"
    if hide_slot and p.spoiled and method != "grade":
        return "it has spoiled: scraps and glue stock now"
    if method == "salt":
        if slot == "salt":
            return "" if _is_salt(doc) else "that is not curing salt"
        if f == "green" or (f == "pelt" and not h.salted):
            return ""
        if f == "salted" or h.salted:
            return "it is already salted"
        return "only a green hide or a fleshed pelt is salted"
    if method == "flense":
        return "" if f in ("green", "salted") else "only a green or salted hide is fleshed"
    if method == "tan":
        if slot == "tannin":
            return "" if doc.get("kind") == "tannin" else "that is not a tannin"
        return "" if f == "pelt" else (
            "flense it first: flesh left on the hide putrefies in the vat"
            if f in ("green", "salted") else "only a fleshed pelt is tanned")
    if method == "curry":
        if slot == "oil":
            return "" if doc.get("kind") == "oil" else "that is not an oil"
        if f not in ("leather", "fur", "panel"):
            return "only tanned leather, fur or soft panels are curried"
        if h.tannage_kind == "rawhide" or (f == "panel" and not h.tannage):
            return "rawhide is not curried: it is not tanned"
        if "curry" in h.worked:
            return "it is already curried"
        return ""
    if method == "cut":
        if f not in ("leather", "fur", "rawhide"):
            return "only tanned leather, fur or rawhide is cut"
        if product == "grip" and (f == "fur" or not _grip_capable(doc)):
            return f"{doc.get('name') or p.material} does not make a grip"
        if product == "lacing" and f == "fur":
            return "fur makes no lacing: cut it from leather or rawhide"
        if product and _plated(product) and (f != "leather" or h.tannage_kind not in
                                             _hardening_kinds()):
            return (f"a {_pattern_word(product).lower()} is hardened plates, and only "
                    f"bark- or planar-tanned leather hardens")
        if product == "hide armour" and not _has(doc, "thick"):
            return "hide armour wants a thick hide: this one is too thin"
        return ""
    if method == "stitch":
        if slot == "thread":
            return "" if doc.get("kind") == "thread" else "that is not a thread"
        if f != "panel":
            return "only cut panels are stitched"
        if "stitch" in h.worked:
            return "it is already stitched"
        return ""
    if method == "harden":
        if f == "plate":
            return "it is already hardened"
        if f != "panel":
            return "only cut panels are hardened"
        if not _plated(h.pattern):
            return (f"{_pattern_word(h.pattern).lower()} is stitched soft work: a hardened "
                    f"panel will not make it")
        return _harden_refusal(h)
    if method == "tool":
        if slot == "wax":
            return "" if doc.get("kind") == "wax" else "that is not a wax"
        if f not in ("leather", "panel", "plate") or not h.tannage:
            return "only tanned leather is tooled"
        if "tool" in h.worked:
            return "it is already tooled"
        return ""
    if method == "dye":
        if slot == "dye":
            return "" if doc.get("kind") == "dye" else "that is not a dye"
        if slot == "mordant":
            return "" if (doc.get("kind") == "treatment" and _has(doc, "fast_colour")) \
                else "that is not a mordant"
        if f not in ("leather", "fur", "panel", "plate") or not h.tannage:
            return "only tanned work takes a dye"
        if "dye" in h.worked:
            return "it is already dyed"
        return ""
    if method == "laminate":
        if f != "leather" or not h.tannage:
            return "only tanned leather is laminated (not fur, not hardened plates)"
        if p.count < 2:
            return "laminating takes two of one leather, and there is one"
        return ""
    if method == "assemble":
        return _assemble_fit(slot, p, product)
    return "no such slot"


def _hardening_kinds() -> tuple[str, ...]:
    return tuple(k for k, row in (bench_rules().get("tannages") or {}).items()
                 if row.get("hardens"))


def _harden_refusal(h: Hide) -> str:
    """Cuir bouilli is done to vegetable-tanned leather (prior art §3.5): the plan's fix of
    the measured "Harden's one enforced input was the wrong one" (a wax). Each refusal says
    why, in the craft's words."""
    kind = h.tannage_kind
    if kind in _hardening_kinds():
        return ""
    return {"alum": "alum leather softens in water: it will not harden",
            "brain": "brain-tanned leather is soft by nature: it will not harden",
            "mineral": "mineral-tanned leather shrugs off the heat: it will not harden",
            "rawhide": "rawhide was never tanned: in the kettle it turns to glue",
            }.get(kind, "only bark- or planar-tanned leather hardens")


def _assemble_fit(slot: str, p: Piece, product: str) -> str:
    f, h, doc = p.form, p.hide, p.doc or {}
    if slot in ("body", "lining"):
        if f not in ("panel", "plate"):
            return "a body or a lining is cut panels or hardened plates"
        want = product or h.pattern
        if h.part != slot:
            return f"these were cut for a {h.part or 'body'}, not a {slot}"
        if want and h.pattern != want:
            return (f"these were cut for {_pattern_word(h.pattern).lower()}, not "
                    f"{_pattern_word(want).lower()}")
        info = PRODUCTS.get(h.pattern) or {}
        if slot == "body" and info.get("body") == "plate" and f != "plate":
            return f"{info.get('word', '').lower()} wants hardened plates: harden them first"
        if f == "panel" and "stitch" not in h.worked:
            return "stitch the panels first"
        return ""
    if slot == "fastenings":
        info = PRODUCTS.get(product) or {}
        if product and not info.get("fastenings"):
            return f"{info.get('word', product).lower()} has no fastenings"
        only = (bench_rules().get("fastenings_for") or {}).get(product)
        if f == "lacing":
            return "" if not only else f"{info.get('word', product).lower()} is fastened " \
                                       f"with {', '.join(doc_name(x).lower() for x in only)}"
        if p.kind == "fitting" or doc.get("kind") == "fitting":
            if p.material in (bench_rules().get("forge_fittings") or ()):
                return ("studs make a forge suit: put the leather base on a smith's anvil "
                        "to stud it")
            if only and p.material not in only:
                return f"{info.get('word', product).lower()} is fastened with " \
                       f"{', '.join(doc_name(x).lower() for x in only)}"
            if "fastenings" not in ((doc.get("pieces") or {}).get("armour") or []):
                return f"{doc.get('name') or p.material} does not fasten armour"
            return ""
        return "fastenings are a lacing set or a fitting"
    return "no such slot"


def fits_for(method: str, items: list[Piece], *, product: str = "") -> dict:
    """`{slot: {key: reason or ""}}` for every rack entry and every slot of the method,
    which is what dims rows (contracts §7 `check`)."""
    return {slot: {p.key: fit_reason(method, slot, p, product=product) for p in items}
            for slot in METHOD_SLOTS.get(method, ())}


# --- one step -------------------------------------------------------------------------------

@dataclass
class LeatherPlan:
    """What one step would do: everything `check` shows, `roll` gates on and `finish`
    makes. Built fresh for every request; nothing in it is trusted from the page."""
    method: str
    batch: int = 1
    slots: dict = field(default_factory=dict)       # slot -> (Piece, count)
    problems: list = field(default_factory=list)
    dc: int = 0
    bonus: int = 0
    terms: list = field(default_factory=list)
    need: int | None = None
    impossible: str = ""
    minutes: int = 0
    units: int = 0                                  # steps, for mastery and the batch
    consumes: list = field(default_factory=list)    # (Piece, count)
    outputs: list = field(default_factory=list)     # (Hide | record dict, count)
    lead: dict | None = None                        # the hide's (or the lead's) document
    lead_id: str = ""
    rank_in: int = 1
    rank_out: int = 1
    tier: str = "common"
    level: int = 1
    ceiling: int = 2
    step_ceiling: int = 2
    ceiling_why: list = field(default_factory=list)
    grade_cap: int | None = None
    product: str = ""
    part: str = "body"
    gear: str = ""
    masterwork_work: bool = False
    masterwork_why: str = ""
    always_masterwork: bool = False
    aim: bool = True
    perks: dict = field(default_factory=dict)
    working: list = field(default_factory=list)
    wait_minutes: int = 0
    wait_where: str = ""                            # "carried" | "tannery"
    vats: int = 0
    tannage: str = ""                               # the tannage kind of a Tan
    noun: str = "piece"
    name: str = ""
    where: dict = field(default_factory=dict)
    hair: bool | None = None

    @property
    def can_roll(self) -> bool:
        return not self.problems and self.need is not None and self.units > 0

    @property
    def info(self) -> str:
        """The line under the stage (UI plan §6.3): "1 pelt. 40m. DC 10, you need 4 or
        better. Then 4 weeks in the vat." Every number is this plan's."""
        if not self.units:
            return ""
        # The product, never Cut's offcut going back on the rack beside it.
        n = (self.outputs[0][1] if self.outputs else 0) or self.units
        hours, mins = divmod(int(self.minutes), 60)
        span = (f"{hours}h {mins}m" if hours and mins else f"{hours}h" if hours
                else f"{mins}m")
        word = self.noun + ("" if n == 1 else "s")
        line = f"{n} {word}. {span}. DC {self.dc}"
        line = (f"{line}: {self.impossible}." if self.need is None
                else f"{line}, you need {self.need} or better.")
        if self.wait_minutes:
            place = "in the vat" if self.wait_where == "tannery" else "in your pack"
            if self.method == "flense":
                place = "in the lime pit"
            line += f" Then {_span(self.wait_minutes)} {place}."
        return line


def _perk_counts(progress) -> dict:
    held = getattr(progress, "perks", {}) or {}
    return {p: int(held.get(p, 0)) for p in ("potency", "hardening", "quality", "yield")}


def plan_step(actor, progress, method: str, slots: dict, batch: int = 1, *,
              product: str = "", part: str = "body", hair: bool | None = None,
              where: dict | None = None, masterwork: bool = True,
              now: int = 0) -> LeatherPlan:
    """One step, worked out without changing anything.

    `slots` maps a slot name to (rack Piece, count). `where` is `where_here`'s answer; None
    means the field kit and no tannery, which is what the rules tests want. `product` is
    Cut's pattern (or "lacing", "grip") and Assemble's product (inferred from the body
    when not said); `part` is Cut's body or lining; `hair` is Tan's hair on (fur) or off.
    `masterwork` is the ambition at Assemble (choose before the roll, the forge's Burning
    Wheel lesson): aiming for Superior raises the DC to the book's 20, and not aiming caps
    the work at Fine.
    """
    method = str(method or "").strip().lower()
    level = int(getattr(progress, "level", 1) or 1)
    batch = max(1, int(batch or 1))
    where = dict(where) if where is not None else {"at": "field", "tannery": None,
                                                   "field_kit": True,
                                                   "tiers": ("common", "uncommon"),
                                                   "vats": False}
    plan = LeatherPlan(method=method, batch=batch, slots=dict(slots or {}), level=level,
                       perks=_perk_counts(progress), product=str(product or "").strip().lower(),
                       part=str(part or "body").strip().lower() or "body",
                       aim=bool(masterwork), where=where, hair=hair,
                       ceiling=wc.ceiling_index(progress) if progress is not None else 2)
    plan.step_ceiling = plan.ceiling
    row = method_row(method)
    if row is None:
        plan.problems.append(f"There is no leatherworking step called {method!r}.")
        return plan
    if method == "grade":
        plan.problems.append("Grading is not worked at the beam: grade the material from "
                             "its card.")
        return plan
    plan.terms = check_terms(actor, level) + (kit_terms(actor) if actor is not None else [])
    plan.bonus = sum(t["value"] for t in plan.terms)
    need = method_level(method)
    if need > level:
        plan.problems.append(f"{row['name']} is learned at Leatherworker {need}.")
    if not where.get("at"):
        plan.problems.append("You have no leatherworker's field kit with you, and there is "
                             "no tannery here.")
    elif row.get("where") == "tannery" and not where.get("tannery"):
        plan.problems.append(f"{row['name']} needs a tannery.")
    if batch > 1 and not row.get("bulk"):
        plan.problems.append(f"{row['name']} works one piece at a time; there is no batch.")
        return plan
    if plan.problems:
        return plan

    for slot, (p, n) in plan.slots.items():
        if slot not in METHOD_SLOTS.get(method, ()):
            plan.problems.append(f"{row['name']} has no {slot} slot.")
            continue
        why = fit_reason(method, slot, p, product=plan.product)
        if why:
            plan.problems.append(f"{p.name}: {why}.")
        if int(n) <= 0:
            plan.problems.append(f"{p.name}: a count of {n} is nothing.")
    if plan.problems:
        return plan

    _BUILD[method](plan, row, actor)
    if plan.problems:
        return plan

    # Enough of everything, across the whole batch, counting one piece used twice.
    used: dict[str, list] = {}
    for p, n in plan.consumes:
        used.setdefault(p.key, [p, 0])[1] += int(n)
    for p, n in used.values():
        if n > p.count:
            plan.problems.append(f"{p.name}: the step wants {n} and you carry {p.count}.")

    # Rarity: the level's band, and a tannery for what the kit does not reach (plan §10,
    # §17.1). Hides only: a tannin's tier is the Tan rule's ("within one tier").
    top = level_tier_rank(level)
    tiers = tuple(where.get("tiers") or ())
    seen: set[str] = set()
    for p, _ in plan.consumes:
        if p.hide is None or p.key in seen:
            continue
        seen.add(p.key)
        if p.rank > top:
            lvl = level_for_rank(p.rank)
            plan.problems.append(f"{p.name} is {p.tier}; Leatherworker {level} works "
                                 f"{wc.TIERS[top - 1]} hides at best"
                                 + (f": it needs Leatherworker {lvl}." if lvl else "."))
        elif tiers and p.tier not in tiers:
            plan.problems.append(f"{p.name} is {p.tier}: rare and rarer hides need a "
                                 f"tannery, not the field kit.")
    plan.tier = wc.TIERS[max(1, min(len(wc.TIERS), plan.rank_out)) - 1]

    from .crafting import check_odds

    plan.need, plan.impossible = check_odds(plan.dc, plan.bonus)
    plan.step_ceiling = max(0, plan.step_ceiling)
    return plan


def _piece(plan: LeatherPlan, slot: str, *, optional: bool = False) -> Piece | None:
    got = plan.slots.get(slot)
    if not got:
        if not optional:
            plan.problems.append(_MISSING.get(slot, f"Fill the {slot} slot."))
        return None
    return got[0]


def _cap(plan: LeatherPlan, cap: int | None, why: str) -> None:
    if cap is None:
        return
    if int(cap) < plan.step_ceiling:
        plan.step_ceiling = max(0, int(cap))
        plan.ceiling_why.append(why)


def _ceiling_for(plan: LeatherPlan, hides: list[Hide], tannin_id: str = "") -> None:
    """The step ceiling (plan §11): your hands' ceiling, moved by the tannin's
    `ceiling_up` / `ceiling_down` trait (the tannin in hand at Tan, else the one the leather
    was tanned with), then capped by the worst grade on the bench (plan §5.7)."""
    plan.ceiling_why.append(f"your hands: {wc.quality_name(plan.ceiling)}")
    tid = tannin_id or next((h.tannage for h in hides if h.tannage), "")
    if tid:
        traits = bench_rules().get("traits") or {}
        doc = material(tid)
        delta = sum(int((traits.get(t) or {}).get("ceiling", 0)) for t in _working(doc))
        if delta:
            plan.step_ceiling = max(0, plan.step_ceiling + delta)
            plan.ceiling_why.append(
                f"{doc_name(tid).lower()}: "
                + (f"{abs(delta)} higher" if delta > 0 else f"{abs(delta)} lower"))
    grades = [int(h.grade) for h in hides]
    if grades:
        worst = max(grades)
        cap = grade_cap(worst)
        plan.grade_cap = cap
        if cap is not None:
            _cap(plan, cap, f"grade {worst} hide: {wc.quality_name(cap)} is the most it "
                            f"allows")


def _minutes(row: dict, quarters_total: int, *, key: str = "minutes") -> int:
    per = int(row.get(key, row.get("minutes", 0)) or 0)
    if row.get("per_unit"):
        return max(1, int(math.ceil(per * max(1, quarters_total) / 4)))
    return per


def _common(plan: LeatherPlan, p: Piece, noun: str) -> None:
    plan.lead = p.doc
    plan.lead_id = p.material
    plan.rank_in = max(plan.rank_in, p.rank)
    plan.rank_out = max(plan.rank_out, p.rank)
    plan.working = list(dict.fromkeys(plan.working + _working(p.doc)))
    plan.noun = noun
    if not plan.dc:
        plan.dc = dc_of(p.doc, p.tier)


def _build_salt(plan: LeatherPlan, row: dict, actor) -> None:
    p = _piece(plan, "hide")
    s = _piece(plan, "salt")
    if plan.problems:
        return
    n = plan.batch
    total_q = p.quarters * n
    measures = max(1, int(math.ceil(total_q / 4 * float(row.get("salt_per_unit", 1)))))
    out = p.hide.copy()
    out.form = "salted" if out.form == "green" else out.form
    out.salted_at = 0                      # stamped with the minute at `make`
    out.name = ""
    plan.consumes = [(p, n), (s, measures)]
    plan.outputs = [(out, n)]
    plan.units = n
    _common(plan, p, "salted hide" if out.form == "salted" else "pelt")
    plan.minutes = _minutes(row, total_q)
    _ceiling_for(plan, [p.hide])


def _build_flense(plan: LeatherPlan, row: dict, actor) -> None:
    p = _piece(plan, "hide")
    if plan.problems:
        return
    n = plan.batch
    out = p.hide.copy()
    out.form = "pelt"
    out.worked = list(dict.fromkeys(out.worked + ["flense"]))
    out.name = ""
    plan.consumes = [(p, n)]
    plan.outputs = [(out, n)]
    plan.units = n
    _common(plan, p, "pelt")
    plan.minutes = _minutes(row, p.quarters * n)
    if _has(p.doc, "thick"):
        # Liming a thick hide (plan §7): a lime pit for days, which is a tannery's.
        if not plan.where.get("tannery"):
            plan.problems.append(f"{p.name} is thick: liming it takes a tannery's lime "
                                 f"pit, not the field kit.")
            return
        plan.wait_minutes = int(row.get("lime_minutes", 4320))
        plan.wait_where = "tannery"
    _ceiling_for(plan, [p.hide])


def _build_tan(plan: LeatherPlan, row: dict, actor) -> None:
    p = _piece(plan, "hide")
    t = _piece(plan, "tannin", optional=True)
    if plan.problems:
        return
    rules = bench_rules()
    n = plan.batch
    total_q = p.quarters * n
    tdoc = t.doc if t is not None else None
    kind = str((tdoc or {}).get("tannage") or "") if t is not None else "rawhide"
    if t is not None and kind not in (rules.get("tannages") or {}):
        plan.problems.append(f"{t.name} names no tannage the bench knows.")
        return
    trow = tannage_row(kind)
    plan.tannage = kind
    lvl = int(trow.get("level", 1))
    if lvl > plan.level:
        plan.problems.append(f"{trow.get('name', kind).capitalize()} tanning is learned at "
                             f"Leatherworker {lvl}.")
    if trow.get("where") == "tannery" and not plan.where.get("tannery"):
        plan.problems.append(f"{trow.get('name', kind).capitalize()} tanning sits in a "
                             f"tannery's vat for weeks: it needs a tannery.")
    if t is not None and p.rank - t.rank > 1:
        plan.problems.append(f"{t.name} cannot bite {p.name}: the tannin must be within one "
                             f"tier of the hide it is asked to bind.")
    if plan.problems:
        return
    doc = p.doc or {}
    out = p.hide.copy()
    hair = plan.hair
    if hair is None:
        hair = str(doc.get("surface") or "") in ("fur", "feather")
    if kind == "rawhide":
        out.form = "rawhide"
        out.tannage = ""
        out.worked = list(dict.fromkeys(out.worked + ["rawhide"]))
    else:
        out.form = "fur" if hair else "leather"
        out.tannage = t.material
    # Tanned leather never spoils (plan §6): its clock is done with.
    out.harvested_at = None
    out.salted_at = None
    out.name = ""
    measures = 0
    if t is not None:
        measures = max(1, int(math.ceil(total_q / 4 * float(row.get("tannin_per_unit", 1)))))
    plan.consumes = [(p, n)] + ([(t, measures)] if t is not None else [])
    plan.outputs = [(out, n)]
    plan.units = n
    _common(plan, p, {"rawhide": "rawhide", "leather": "leather", "fur": "fur"}[out.form])
    if t is not None:
        plan.rank_in = max(plan.rank_in, t.rank)
        plan.working = list(dict.fromkeys(plan.working + _working(tdoc)))
    # Bench time: brain tanning is a day's work per unit; the rest a setup hour, then the
    # wait. A salted hide soaks the salt out first unless the tannin is salt-proof.
    plan.minutes = _minutes({**row, **{k: trow[k] for k in ("minutes", "per_unit")
                                       if k in trow}}, total_q)
    if p.hide.salted and not _has(tdoc, "salt_proof"):
        plan.minutes += int(row.get("desalt_minutes", 480))
    wait = int(trow.get("thick_wait_minutes") if _has(doc, "thick")
               and trow.get("thick_wait_minutes") else trow.get("wait_minutes", 0) or 0)
    if wait:
        traits = rules.get("traits") or {}
        scale = 1.0
        # A tannin's and the hide's fast_tan and slow_tan move a TANNAGE; rawhide is
        # not tanned at all, only dried, and dries in its day whatever the hide.
        for trait in (_working(tdoc) + _working(doc)) if kind != "rawhide" else ():
            scale *= float((traits.get(trait) or {}).get("time", 1.0))
        plan.wait_minutes = max(1, int(round(wait * scale)))
        plan.wait_where = "tannery" if trow.get("where") == "tannery" else "carried"
        if plan.wait_where == "tannery" and trow.get("vat", True) is not False:
            plan.vats = vats_for(total_q)
    _ceiling_for(plan, [p.hide], t.material if t is not None else "")


def _build_curry(plan: LeatherPlan, row: dict, actor) -> None:
    p = _piece(plan, "piece")
    o = _piece(plan, "oil")
    if plan.problems:
        return
    out = p.hide.copy()
    out.worked = list(dict.fromkeys(out.worked + ["curry"]))
    out.uses["oil"] = o.material
    out.name = ""
    plan.consumes = [(p, 1), (o, int(row.get("oil_per_piece", 1)))]
    plan.outputs = [(out, 1)]
    plan.units = 1
    _common(plan, p, out.form)
    plan.rank_in = max(plan.rank_in, o.rank)
    plan.working = list(dict.fromkeys(plan.working + _working(o.doc)))
    plan.minutes = _minutes(row, p.quarters)
    _ceiling_for(plan, [p.hide])


def _build_cut(plan: LeatherPlan, row: dict, actor) -> None:
    p = _piece(plan, "hide")
    if plan.problems:
        return
    pattern = plan.product
    if not pattern:
        plan.problems.append("Pick what to cut from the list of patterns.")
        return
    if pattern not in PRODUCTS and pattern not in CUT_PIECES:
        plan.problems.append(f"There is no {pattern!r} on the list of patterns.")
        return
    part = "body" if pattern in CUT_PIECES else plan.part
    if part not in ("body", "lining"):
        plan.problems.append("Cut panels for a body or for a lining.")
        return
    need = product_units(pattern, part, actor)
    if need <= 0:
        plan.problems.append(f"{_pattern_word(pattern)} has no {part}.")
        return
    n = plan.batch
    want = need * n
    each = max(1, p.quarters)
    have = each * p.count
    if have < want:
        plan.problems.append(
            f"{_pattern_word(pattern)} {part}{' x' + str(n) if n > 1 else ''} takes "
            f"{units_word(want)} of hide, and {p.name} is {units_word(have)}: hides of "
            f"one kind and grade combine, so carry more of it.")
        return
    pieces_used = int(math.ceil(want / each))
    left = pieces_used * each - want
    src = p.hide
    out = src.copy()
    out.form = {"lacing": "lacing", "grip": "grip"}.get(pattern, "panel")
    out.quarters = need
    out.pattern = "" if pattern in CUT_PIECES else pattern
    out.part = "" if pattern in CUT_PIECES else part
    if src.form == "fur":
        out.worked = list(dict.fromkeys(out.worked + ["fur"]))
    out.name = ""
    plan.consumes = [(p, pieces_used)]
    plan.outputs = [(out, n)]
    if left > 0:
        rest = src.copy()
        rest.quarters = left
        rest.name = ""
        plan.outputs.append((rest, 1))
    plan.units = n
    _common(plan, p, {"lacing": "lacing set", "grip": "grip"}.get(pattern, "set of panels"))
    plan.minutes = _minutes(row, want) * n if not row.get("per_unit") else _minutes(row, want)
    _ceiling_for(plan, [src])


def _build_stitch(plan: LeatherPlan, row: dict, actor) -> None:
    p = _piece(plan, "piece")
    th = _piece(plan, "thread")
    if plan.problems:
        return
    out = p.hide.copy()
    out.worked = list(dict.fromkeys(out.worked + ["stitch"]))
    out.uses["thread"] = th.material
    out.name = ""
    plan.consumes = [(p, 1), (th, int(row.get("thread_per_piece", 1)))]
    plan.outputs = [(out, 1)]
    plan.units = 1
    _common(plan, p, "stitched piece")
    plan.rank_in = max(plan.rank_in, th.rank)
    plan.working = list(dict.fromkeys(plan.working + _working(th.doc)))
    plan.minutes = _minutes(row, p.quarters)
    _ceiling_for(plan, [p.hide])


def _build_harden(plan: LeatherPlan, row: dict, actor) -> None:
    p = _piece(plan, "piece")
    if plan.problems:
        return
    out = p.hide.copy()
    out.form = "plate"
    out.worked = list(dict.fromkeys(out.worked + ["harden"]))
    out.name = ""
    plan.consumes = [(p, 1)]
    plan.outputs = [(out, 1)]
    plan.units = 1
    _common(plan, p, "set of plates")
    plan.minutes = _minutes(row, p.quarters)
    _ceiling_for(plan, [p.hide])


def _build_tool(plan: LeatherPlan, row: dict, actor) -> None:
    p = _piece(plan, "piece")
    w = _piece(plan, "wax", optional=True)
    if plan.problems:
        return
    out = p.hide.copy()
    out.worked = list(dict.fromkeys(out.worked + ["tool"]))
    if w is not None:
        out.uses["wax"] = w.material
    out.name = ""
    plan.consumes = [(p, 1)] + ([(w, 1)] if w is not None else [])
    plan.outputs = [(out, 1)]
    plan.units = 1
    _common(plan, p, "tooled piece")
    if w is not None:
        plan.working = list(dict.fromkeys(plan.working + _working(w.doc)))
    plan.minutes = _minutes(row, p.quarters)
    _ceiling_for(plan, [p.hide])


def _build_dye(plan: LeatherPlan, row: dict, actor) -> None:
    p = _piece(plan, "piece")
    d = _piece(plan, "dye")
    m = _piece(plan, "mordant", optional=True)
    if plan.problems:
        return
    out = p.hide.copy()
    out.worked = list(dict.fromkeys(out.worked + ["dye"]))
    out.uses["dye"] = d.material
    if m is not None:
        out.uses["mordant"] = m.material
    out.name = ""
    plan.consumes = [(p, 1), (d, 1)] + ([(m, 1)] if m is not None else [])
    plan.outputs = [(out, 1)]
    plan.units = 1
    _common(plan, p, "dyed piece")
    plan.rank_in = max(plan.rank_in, d.rank)
    plan.minutes = _minutes(row, p.quarters)
    _ceiling_for(plan, [p.hide])


def _build_laminate(plan: LeatherPlan, row: dict, actor) -> None:
    p = _piece(plan, "piece")
    if plan.problems:
        return
    out = p.hide.copy()
    out.passes = int(out.passes) + 1
    out.worked = list(dict.fromkeys(out.worked + ["laminate"]))
    out.name = ""
    # Two pieces of N units make one of N units (plan §12); the 2^n hide cost is the
    # brake, as the forge's bar cost is.
    plan.consumes = [(p, 2)]
    plan.outputs = [(out, 1)]
    plan.units = 1
    _common(plan, p, "laminated leather")
    plan.minutes = _minutes(row, p.quarters)
    _ceiling_for(plan, [p.hide])


def masterwork_ready(body: Hide | None) -> tuple[bool, str]:
    """Whether a body can carry Superior work (plan §13.4): hardened plates (leather armour,
    lamellar, the madu) or a curried soft body — the leather counterpart of the forge's
    tempered and honed head."""
    if body is None:
        return False, "there is no body"
    if body.form == "plate":
        return True, ""
    if "curry" in body.worked:
        return True, ""
    if body.hair_on or "rawhide" in body.worked or not body.tannage:
        return False, "the body is not curried"
    return False, "the body is not curried"


def _build_assemble(plan: LeatherPlan, row: dict, actor) -> None:
    body = _piece(plan, "body")
    if body is None:
        return
    b = body.hide
    product = plan.product or b.pattern
    info = PRODUCTS.get(product)
    if info is None:
        plan.problems.append(f"{body.name} were not cut for anything the bench assembles.")
        return
    plan.product = product
    plan.gear = info["gear"]
    fast = _piece(plan, "fastenings", optional=True)
    lining = _piece(plan, "lining", optional=True)
    if info.get("fastenings") and fast is None:
        plan.problems.append(_MISSING["fastenings"])
    for slot, (p, _n) in plan.slots.items():
        why = fit_reason("assemble", slot, p, product=product)
        if why and f"{p.name}: {why}." not in plan.problems:
            plan.problems.append(f"{p.name}: {why}.")
    if info.get("thick") and not _has(body.doc, "thick"):
        plan.problems.append(f"{info['word']} wants a thick hide, and "
                             f"{doc_name(b.material).lower()} is not one.")
    if plan.problems:
        return
    doc = body.doc or {}
    rules = bench_rules()
    mw = _mw_index()
    plan.always_masterwork = doc.get("always_masterwork") is True
    ready, why = masterwork_ready(b)
    plan.masterwork_work = bool(ready and plan.aim) and not plan.always_masterwork
    if plan.always_masterwork:
        plan.masterwork_why = "masterwork by its nature"
    else:
        plan.masterwork_why = why if not ready else (
            "" if plan.aim else "you are not aiming for masterwork")
    plan.dc = product_dc(product)
    hides = [b] + ([lining.hide] if lining is not None else [])
    _ceiling_for(plan, hides)
    if b.quality is not None:
        _cap(plan, int(b.quality) + 1,
             f"the body is {wc.quality_name(int(b.quality))}: one above it")
    if not plan.always_masterwork:
        if not plan.masterwork_work:
            _cap(plan, mw - 1, why if not ready else "not aiming for masterwork")
        elif plan.step_ceiling >= mw and not _has(doc, "flawless"):
            # The book's masterwork component is DC 20 (CRB Craft); Unchained's `flawless`
            # raw material waives the increase.
            plan.dc = max(plan.dc, int(rules.get("masterwork_dc", 20)))
    if rules.get("flawless_needs_tool", True) and "tool" not in b.worked:
        _cap(plan, mw, "the body is not tooled: Flawless needs tooling")
    pieces: dict[str, dict] = {"body": _piece_spec(b)}
    if fast is not None:
        if fast.hide is not None:
            pieces["fastenings"] = dict(_piece_spec(fast.hide), form="lacing")
        else:
            pieces["fastenings"] = {"material": fast.material, "passes": 0}
    if lining is not None:
        pieces["lining"] = _piece_spec(lining.hide)
    plan.consumes = [(p, 1) for p, _ in plan.slots.values()]
    plan.outputs = [({"product": product, "pieces": pieces}, 1)]
    plan.units = 1
    plan.lead = doc
    plan.lead_id = b.material
    plan.rank_in = max(p.rank for p, _ in plan.slots.values())
    plan.rank_out = body.rank
    plan.working = _working(doc)
    plan.minutes = int(row.get("minutes_suit" if plan.gear in ("armour", "shield")
                               else "minutes", 30))
    plan.noun = "item"


def _piece_spec(h: Hide) -> dict:
    """A record's piece (contracts §4.2): ids, passes, grade and tannage, and a generic
    hide's beast, which `forge_items.build` reads through `harvest.inherited` (lane B)."""
    spec = {"material": h.material, "passes": int(h.passes), "grade": int(h.grade)}
    if h.tannage:
        spec["tannage"] = h.tannage
    if h.creature:
        spec["creature"] = h.creature
    return spec


_BUILD = {"salt": _build_salt, "flense": _build_flense, "tan": _build_tan,
          "curry": _build_curry, "cut": _build_cut, "stitch": _build_stitch,
          "harden": _build_harden, "tool": _build_tool, "dye": _build_dye,
          "laminate": _build_laminate, "assemble": _build_assemble}


# --- what a step makes -------------------------------------------------------------------------

def _record(plan: LeatherPlan, spec: dict, tier: int) -> dict:
    """The forge's crafted record (plan §13.1) for an assembled thing: ids and passes, the
    quality the hands reached, the maker's level and perks; never a computed number."""
    product = spec["product"]
    info = PRODUCTS[product]
    pieces = _copy.deepcopy(spec["pieces"])
    body = pieces.get("body") or {}
    q = int(tier)
    prefix = "" if q == 1 else f"{wc.quality_name(q)} "
    name = f"{prefix}{_lead_word(body.get('material', ''))} {info['word']}".strip()
    mw = q >= _mw_index() or plan.always_masterwork
    rec = {
        "id": _slug(name), "name": name, "kind": "crafted", "craft": TRACK_ID, "count": 1,
        "gear": info["gear"], "base": info["base"],
        "slot": info.get("slot") or "",
        "quality": wc.quality_name(q).lower(), "quality_index": q, "masterwork": mw,
        "pieces": pieces, "quench": None, "finish": [], "flaws": [], "marks": [],
        "base_for": list(info.get("base_for") or []), "product": product,
        "tier": plan.tier,
        "smith": {"level": plan.level,
                  "perks": {"potency": plan.perks.get("potency", 0),
                            "hardening": plan.perks.get("hardening", 0)}},
        "schema": RECORD_SCHEMA,
    }
    if info.get("carried"):
        rec["carried"] = True
    return rec


def make(plan: LeatherPlan, tier: int, *, now: int = 0) -> list[tuple]:
    """What a finished step puts on the shelf, at the tier the player's hands earned under
    the step's ceiling. A leftover offcut from Cut keeps the quality it had."""
    tier = max(0, min(int(tier), plan.step_ceiling))
    out = []
    for i, (template, n) in enumerate(plan.outputs):
        if isinstance(template, dict):
            out.append((_record(plan, template, tier), n))
            continue
        h = template.copy()
        leftover = plan.method == "cut" and i > 0
        if not leftover:
            h.quality = tier
        if plan.method == "salt":
            h.salted_at = int(now)
        h.name = ""
        h.name = hide_name(h)
        out.append((h, int(n)))
    return out


def _land_record(actor, rec: dict) -> str:
    """A finished record onto the shelf, numbered when another, different build already
    holds its name ("Fine Elk Hide Armour (2)"), as the forge's `land` does."""
    from . import forge_items

    base, k = rec["name"], 1
    while any(getattr(st, "name", "") == rec["name"] for st in (actor.stock or {}).values()):
        k += 1
        rec["name"] = f"{base} ({k})"
        rec["id"] = _slug(rec["name"])
    item = forge_items.stock_item(rec)
    actor.add_stock(item, 1)
    return item.id


def land(actor, plan: LeatherPlan, made: list[tuple], *, now: int,
         where: dict | None = None, setup_score: float | None = None) -> list[dict]:
    """Put what a step made on the shelf; work that waits (a vat tannage, alum ageing,
    rawhide drying, a thick hide's lime pit) goes In progress (rules/inprogress.py, the one
    store), at the tannery when the tannery holds it, in the pack otherwise. Returns
    [{key, hide | record, count, waits, ready_at, where}]."""
    from . import inprogress

    where = where or {}
    out = []
    for i, (thing, n) in enumerate(made):
        if isinstance(thing, dict):
            key = _land_record(actor, thing)
            out.append({"key": key, "record": thing, "count": 1, "waits": 0,
                        "ready_at": None})
            continue
        waits = plan.wait_minutes if i == 0 else 0
        if not waits:
            out.append({"key": put_hide(actor, thing, n), "hide": thing, "count": n,
                        "waits": 0, "ready_at": None})
            continue
        # Its own entry, never stacked into a ready one: the whole entry goes into the
        # section (inprogress.begin).
        st = to_stock(thing)
        st.count = int(n)
        key = stock_key(thing)
        while key in (actor.stock or {}):
            key += "+"
        actor.stock[key] = st
        tannery = where.get("tannery") or {}
        at_tannery = plan.wait_where == "tannery" and tannery.get("place")
        place = f"place:{tannery['place']}" if at_tannery else "carried"
        result = {"method": plan.method, "setup_score": setup_score,
                  "ceiling": plan.step_ceiling, "quarters": thing.quarters * int(n)}
        if at_tannery:
            if plan.vats:
                result["vats"] = int(plan.vats)
            else:
                result["vat"] = False        # the lime pit fills no vat
        if plan.method == "tan":
            label = (f"{doc_name(thing.material)} in {doc_name(thing.tannage).lower()}"
                     if thing.tannage else f"{doc_name(thing.material)} drying as rawhide")
            doing = "tanning" if thing.tannage else "drying"
        else:
            label = f"{doc_name(thing.material)} in the lime pit"
            doing = "liming"
        got = inprogress.begin(actor, key, craft=TRACK_ID, minutes=max(1, int(waits)),
                               now=int(now), label=label, where=place,
                               where_name=str(where.get("name") or ""), doing=doing,
                               result=result)
        out.append({"key": key, "hide": thing, "count": n, "waits": int(waits),
                    "ready_at": got.get("ready_at"), "where": place})
    return out


def failure_losses(plan: LeatherPlan, miss: int) -> list[tuple[Piece, int]]:
    """What a failed roll ruins, by the book's Craft rule (plan §11): miss by 4 or less and
    only the time is lost; miss by 5 or more and half of what was on the bench is ruined,
    rounded down, at least one whenever there were two. Shared out by each material's
    share, largest remainders first; a tie goes to the cheaper thing (consumables before
    hides, then the lower rarity): every crafting game the sweep found was softened after
    launch (prior art §6), so the bench starts on the generous side."""
    if miss < 5:
        return []
    total = sum(int(n) for _, n in plan.consumes)
    ruin = total // 2
    if ruin <= 0:
        return []
    shares = []
    for i, (p, n) in enumerate(plan.consumes):
        exact = n * ruin / total
        worked = 1 if p.hide is not None else 0
        shares.append([p, int(exact), exact - int(exact), n, (worked, p.rank, i)])
    left = ruin - sum(s[1] for s in shares)
    for s in sorted(shares, key=lambda s: (-round(s[2], 9), s[4])):
        if left <= 0:
            break
        if s[1] < s[3]:
            s[1] += 1
            left -= 1
    return [(p, k) for p, k, _, _, _ in shares if k > 0]


def spend(actor, consumes: list[tuple[Piece, int]]) -> list[dict]:
    """Take what a step used: raw material from the satchel's counts, products off the
    shelf, by the key the rack was read under."""
    out = []
    for p, n in consumes:
        if n <= 0:
            continue
        if p.key.startswith("stock:"):
            took = actor.take_stock(p.key.split(":", 1)[1], n)
        else:
            took = actor.spend(p.material, n)
        if took:
            out.append({"key": p.key, "name": p.name, "count": int(took)})
    return out


def band_for(plan: LeatherPlan) -> dict | None:
    """The game's band (contracts §11.1, `opts.band`): the real variable's unit, where it
    starts, the target and failing bands, its drift, and whether the window is narrow (rare
    and rarer hides: the forge's "better metal, tighter window"). From the rule rows, so the
    page computes no number."""
    row = method_row(plan.method) or {}
    band = ((row.get("tuning") or {}).get("band"))
    if not isinstance(band, dict):
        return None
    out = dict(band)
    out["narrow"] = bool(plan.rank_in >= 3)
    return out


def tuning_for(plan: LeatherPlan) -> dict:
    """The minigame's numbers (UI plan §9): the method's base difficulty, harder by
    `rarity_step` per band above common, and the working traits' band scales (forgiving
    wider; supple at Curry, fills_tooling at Tool, fine_pitch and strong_seam at Stitch).
    The same at every level: skill raises the ceiling, not the window, as for herbs."""
    rules = bench_rules()
    row = method_row(plan.method) or {}
    tun = row.get("tuning") or {}
    traits = rules.get("traits") or {}
    scale = 1.0
    for t in dict.fromkeys(plan.working):
        spec = traits.get(t) or {}
        scale *= float(spec.get("band", 1.0))
        scale *= float(spec.get(f"{plan.method}_band", 1.0))
    rank = plan.rank_in or 1
    diff = float(tun.get("difficulty", 0.45)) + float(rules.get("rarity_step", 0.05)) \
        * max(0, rank - 1)
    ceiling = max(0, int(plan.step_ceiling))
    return {"method": plan.method, "game": plan.method,
            "difficulty": round(min(0.95, diff), 4), "band_scale": round(scale, 4),
            "band": band_for(plan), "seconds": tun.get("seconds", 6),
            "traits": list(dict.fromkeys(plan.working)),
            "names": [wc.quality_name(t) for t in range(ceiling + 1)],
            "bands": [t / (ceiling + 1) for t in range(ceiling + 1)],
            "masterwork_at": _mw_index(),
            "two_halves": bool(plan.method == "tan" and plan.wait_minutes
                               and plan.tannage not in ("rawhide",))}


# --- In progress: what Collect means for a tannage (rules/inprogress.py) ------------------------

def _collect(item, actor) -> dict:
    """Collecting a tannage or a lime pit: the leather is already what it will be; its tier
    comes from both halves of the Tan game (plan §8.3) when the cut test was played (the
    bench's collect puts its score in `result["cut_score"]` first), else from the setup
    half alone. Collecting late costs nothing: leather does not over-tan here (plan §8.3,
    proposed)."""
    from . import crafting
    from . import inprogress

    block = inprogress.work_of(item) or {}
    result = block.get("result") or {}
    h = Hide.from_stock(item)
    if h is None:
        return {"said": f"You take the {item.name} out."}
    setup = result.get("setup_score")
    cut = result.get("cut_score")
    if setup is not None and cut is not None and result.get("method") == "tan":
        ceiling = int(result.get("ceiling", h.quality or 0) or 0)
        tier, _ = crafting.tier_from_score((float(setup) + float(cut)) / 2, ceiling)
        h.quality = tier
        h.name = ""
        h.name = hide_name(h)
        item.properties = h.tags()
        item.base = h.name
    where = {"tan": "the vat" if result.get("vats") else "the bag",
             "flense": "the lime pit"}.get(str(result.get("method") or ""), "the work")
    q = f", {wc.quality_name(h.quality)}" if h.quality is not None else ""
    return {"said": f"You take the {item.name} out of {where}{q}.",
            "product": {"name": item.name, "quality": h.quality,
                        "quality_name": wc.quality_name(h.quality)
                        if h.quality is not None else None}}


def _register() -> None:
    from . import inprogress

    inprogress.register(TRACK_ID, collect=_collect, icon="leather", stop_words="")


_register()


# --- grade: the leather assay (plan §16) -------------------------------------------------------

def grade_source(actor, material_id: str, now: int = 0) -> Piece | None:
    """What a scrap for grading this material would come from: scraps of it first, then
    the smallest stack of its hide or leather (a quarter unit is cut off), else one measure
    of a consumable."""
    mid = str(material_id or "").strip().lower()
    items = [p for p in rack(actor, now) if p.material == mid and not p.old
             and p.form != "item" and p.count > 0]
    scraps = [p for p in items if p.form == "scrap"]
    hides = sorted((p for p in items if p.hide is not None and p.form != "scrap"),
                   key=lambda p: (p.quarters, p.key))
    rest = [p for p in items if p.hide is None]
    return (scraps or hides or rest or [None])[0]


def pay_grade(actor, p: Piece, now: int = 0) -> list[dict]:
    """Take the scrap a grade costs (plan §16: "a scrap, a quarter unit or an offcut"):
    one quarter unit off a hide, the rest of the hide going back on the shelf; one measure
    of anything else."""
    if p is None:
        return []
    if p.hide is None or p.form == "scrap" or p.quarters <= 1:
        return spend(actor, [(p, 1)])
    took = spend(actor, [(p, 1)])
    rest = p.hide.copy()
    rest.quarters = p.quarters - 1
    rest.name = ""
    put_hide(actor, rest, 1)
    if took:
        took[0]["count"] = 1
        took[0]["quarters"] = 1
    return took


def working_keys(doc: dict) -> list[str]:
    """The knowledge keys of a material's working traits, revealed by working it (plan
    §16: "working a hide reveals its working traits")."""
    kn = _lane("knowledge")
    if kn is None or not doc:
        return []
    fn = getattr(kn, "working_keys", None)
    if fn is not None:
        try:
            return list(fn(doc))
        except Exception:      # noqa: BLE001
            return []
    keys = list(kn.property_keys(doc))
    return [k for k in keys if str(k).startswith("t")]


def reveal(actor, material_id: str, keys, how: str) -> list[str]:
    """Record keys as known; returns the new ones (one store, `Actor.herb_known`)."""
    kn = _lane("knowledge")
    fn = getattr(kn, "reveal", None) if kn is not None else None
    if fn is None:
        from . import herbknowledge

        fn = herbknowledge.reveal
    return list(fn(actor, material_id, list(keys), how) or [])


# =============================================================================================
# The shelf library: the market's counter, the /craft/ page's shelf and the acquisition hub
# =============================================================================================

@dataclass
class Material:
    """One thing on the tannery shelf, as the market and the old page read it."""
    id: str
    name: str
    kind: str = "hide"          # hide | tannin | thread | oil | dye | wax | fitting | treatment
    tier: str = "common"
    craft_dc: int | None = None
    text: str = ""
    risky: bool = False
    # Which creatures this hide comes off, as lowercase name fragments: the old skin
    # excursion's reader (`hides_from`). Lane C's harvest reads bestiary tags instead and
    # removes the excursion (contracts §1).
    from_creatures: list[str] = field(default_factory=list)
    source: str = "bought"      # skinned | foraged | bought | rendered | smithed
    size: str = ""
    fresh_hours: int | None = None
    effects: list = field(default_factory=list)
    obtain: str = "bought"      # harvested | gathered | mined | bought
    price_gp: float | None = None
    biomes: list[str] = field(default_factory=list)

    @property
    def rank(self) -> int:
        return wc.tier_rank(self.tier)

    @property
    def is_raw_hide(self) -> bool:
        return self.kind == "hide" and self.fresh_hours is not None

    @property
    def specs(self) -> list[dict]:
        return [dict(e) for e in self.effects]

    def as_dict(self) -> dict:
        return {
            "id": self.id, "name": self.name, "kind": self.kind, "tier": self.tier,
            "rank": self.rank, "craft_dc": self.craft_dc, "text": self.text,
            "risky": self.risky, "from_creatures": self.from_creatures,
            "source": self.source, "size": self.size,
            "fresh_hours": self.fresh_hours, "effects": self.effects,
            "obtain": self.obtain, "price_gp": self.price_gp,
            "biomes": self.biomes, "glyph": self.glyph,
        }

    @property
    def glyph(self) -> str:
        """The shelf icon. Unknown kinds fall back to the hide glyph rather than to a
        herb: a homebrew material with a novel kind is still tannery goods."""
        return KIND_GLYPH.get(self.kind, KIND_GLYPH["hide"])


def from_dict(d: dict) -> Material:
    return Material(
        id=d["id"], name=d.get("name", d["id"]), kind=d.get("kind", "hide"),
        tier=d.get("tier", "common"), craft_dc=d.get("craft_dc"),
        text=d.get("text", ""), risky=bool(d.get("risky")),
        from_creatures=[str(x).lower() for x in d.get("from_creatures") or []],
        source=d.get("source", "bought"), size=d.get("size", ""),
        fresh_hours=d.get("fresh_hours"),
        effects=list(d.get("effects") or []),
        # A homebrew entry that says nothing is bought: the safest default, because a
        # material wrongly marked harvested would appear on every carcass in the game.
        obtain=str(d.get("obtain") or "bought").strip().lower(),
        price_gp=d.get("price_gp"),
        biomes=[str(b).strip().lower() for b in d.get("biomes") or []],
    )


def load_dir(path: str | Path, claimed_by: str = "") -> dict[str, Material]:
    """Every material in a directory, accepting both file shapes (one list, or one file per
    thing, which the homebrew editor writes). `claimed_by` filters to one craft's goods:
    `content/materials/` is one shelf for all five benches, and without the filter this
    loader answered with the blacksmith's ash hafts (measured, six of eleven)."""
    out: dict[str, Material] = {}
    p = Path(path)
    if not p.is_dir():
        return out
    for file in sorted(p.glob("*.json")):
        try:
            data = json.loads(file.read_text(encoding="utf-8"))
        except Exception as exc:
            files.unreadable(file, exc)
            continue
        file_craft = str(data.get("craft") or "").strip().lower() \
            if isinstance(data, dict) else ""
        if not file_craft and claimed_by and file.stem.startswith(claimed_by):
            file_craft = claimed_by
        entries = data.get("materials") if isinstance(data, dict) else None
        if not isinstance(entries, list):
            entries = [data] if isinstance(data, dict) and data.get("id") else []
        for raw in entries:
            if not raw.get("id"):
                continue
            craft = str(raw.get("craft") or file_craft or "").strip().lower()
            if claimed_by and craft != claimed_by:
                continue
            m = from_dict(raw)
            out[m.id] = m
    return out


_MATERIALS: dict[str, Material] | None = None


def materials() -> dict[str, Material]:
    """Every leatherworker material the app knows, shipped and homebrew (homebrew layered
    over, so a corrected hide in a later build is not shadowed by a stale copy)."""
    global _MATERIALS
    if _MATERIALS is None:
        from django.conf import settings

        shelf = Path(settings.BASE_DIR) / "content" / "materials"
        _MATERIALS = load_dir(shelf, claimed_by=TRACK_ID)
        user = Path(settings.CAMPAIGN_DIR).parent / "homebrew" / "materials"
        if user.is_dir():
            _MATERIALS.update(load_dir(user))
    return _MATERIALS


def get(material_id: str) -> Material:
    m = materials().get((material_id or "").strip().lower())
    if m is None:
        raise KeyError(f"no material {material_id!r}")
    return m


def hides_from(creature_name: str) -> list[Material]:
    """The hide entries a fallen creature could yield, by name fragment: the old skin
    excursion's reader, kept until lane C's harvest replaces it with bestiary tags."""
    return _by_creature(creature_name, lambda m: m.kind == "hide")


def _by_creature(creature_name: str, keep) -> list[Material]:
    said = str(creature_name or "").strip().lower()
    if not said:
        return []
    found = [(max((len(f) for f in m.from_creatures if f in said), default=0), m)
             for m in materials().values() if keep(m)]
    matched = [(n, m) for n, m in found if n > 0]
    matched.sort(key=lambda pair: -pair[0])
    return [m for _, m in matched]


# --- acquisition ----------------------------------------------------------------------------
#
# The play page's craft-action hub, the track's half of it. `skin` is lane C's to remove
# (the harvest replaces it, plan §5.1); left as it was until then, so the hub does not lose
# its only carcass door before the new one exists.

ACQUISITION: dict[str, dict] = {
    "skin": {
        "id": "skin", "label": "Skin the carcass", "obtain": "harvested",
        "requires": "creature",
        "requires_note": "A fallen creature in the scene. What it yields is read off "
                         "its name, so the beast decides the hide.",
        "method": "skin",
        "blurb": "Take the hide, and the sinew and tallow with it. The spoilage "
                 "clock starts now — 48 hours to cure or tan.",
    },
    "gather": {
        "id": "gather", "label": "Strip bark and gather", "obtain": "gathered",
        "requires": "biome",
        "requires_note": "Somewhere that grows it. Oak bark wants forest, mangrove "
                         "wants the salt coast, glowcap wants the deep places.",
        "blurb": "Tannins, plant dyes, pitch and wax — the vat's supplies come out "
                 "of the landscape, not a shop.",
    },
    "mine": {
        "id": "mine", "label": "Dig for salt and mineral", "obtain": "mined",
        "requires": "biome",
        "requires_note": "Underground, mountain or hardpan, depending on the mineral.",
        "blurb": "Curing salt, alum, quicklime and the mineral colours.",
    },
    "buy": {
        "id": "buy", "label": "Buy from the market", "obtain": "bought",
        "requires": "market",
        "requires_note": "A settlement that trades. Everything bought carries a "
                         "price in gp; nothing here is free.",
        "blurb": "Thread, buckles and studs off the smith's bench, and the "
                 "imported colours.",
    },
}


def obtainable(obtain_kind: str, *, biome=None, creature=None) -> list[Material]:
    """What this excursion could actually turn up, here, now. Harvesting delegates to the
    creature (never another beast's hide); gathering and mining ask the ground; buying
    asks nothing but a market."""
    kind = str(obtain_kind or "").strip().lower()
    pool = [m for m in materials().values() if m.obtain == kind]

    if kind == "harvested":
        if not creature:
            return []
        specific = _by_creature(creature, lambda m: m.obtain == "harvested")
        generic = [m for m in pool if not m.from_creatures]
        seen, out = set(), []
        for m in specific + generic:
            if m.id not in seen:
                seen.add(m.id)
                out.append(m)
        return out

    if kind in ("gathered", "mined"):
        if not biome:
            return sorted(pool, key=lambda m: m.name)
        here = str(biome).strip().lower()
        return sorted((m for m in pool if here in m.biomes), key=lambda m: m.name)

    return sorted(pool, key=lambda m: (m.price_gp or 0, m.name))


# --- the old chain, retired ------------------------------------------------------------------

MOVED_WORDS = ("Leatherworking is worked at the bench at the table now, one step at a time: "
               "salt, flense, tan, cut, stitch, harden, assemble. The chain bench no longer "
               "takes it.")


class CraftError(ValueError):
    """A step that cannot be described at all (kept for the routing table's shape)."""


@dataclass
class Chain:
    methods: list = field(default_factory=list)
    material_ids: list = field(default_factory=list)
    product: str = "satchel"
    name: str = ""


def chain_from_body(body: dict) -> Chain:
    """The old chain's reader, kept so `benches.supports` stays honest."""
    body = body or {}
    raw = body.get("materials")
    if raw is None:
        raw = body.get("material_ids") or []
    return Chain(methods=[str(m).strip().lower() for m in body.get("methods") or []],
                 material_ids=[str(m).strip().lower() for m in raw if str(m).strip()],
                 product=str(body.get("product") or body.get("pattern") or "satchel")
                 .strip().lower(),
                 name=str(body.get("name") or "").strip())


def preview(level: int, chain: Chain, stock: dict | None = None, actor=None):
    """Refuses: the chain bench retired for leatherworking. A pattern it never knew is
    refused by name with the ones it does (the old contract the /craft/ page still reads);
    any real one says where the bench went."""
    product = str(getattr(chain, "product", "") or "").strip().lower()
    if product and product not in PRODUCTS:
        raise CraftError(f"no product pattern {product!r}. Known: "
                         f"{', '.join(sorted(PRODUCTS))}.")
    raise CraftError(MOVED_WORDS)


__all__ = ["ACQUISITION", "CUT_PIECES", "Chain", "CraftError", "FORMS", "FRESH_HOURS", "Hide",
           "KIND_GLYPH", "LeatherPlan", "METHODS", "METHOD_GLYPH", "METHOD_SLOTS", "Material",
           "OPTIONAL", "PRODUCTS", "Piece", "TRACK_ID", "band_for", "bench_rules",
           "chain_from_body", "check_bonus", "check_terms", "failure_losses", "fit_reason",
           "fits_for", "freshness", "from_dict", "get", "grade_cap", "grade_source",
           "hide_name", "hides_from", "kit_terms", "land", "make", "make_hide", "materials",
           "method_level", "method_row", "methods_view", "obtainable", "pay_grade",
           "piece_view", "plan_step", "preview", "product_dc", "product_units",
           "products_view", "put_hide", "rack", "record_of_hide", "rent_cp", "reveal",
           "spend", "tuning_for", "units_of_size", "vat_rent_cp", "where_here",
           "working_keys"]
