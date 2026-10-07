"""Alchemy: the bench's rules (docs/alchemy-revamp-plan.md §4, §7-§9, §12, §14, §15;
docs/alchemy-contracts.md §8, lane F), and the shelf library the acquisition hub reads.

**The step bench** (most of this file), the herb bench's and the forge's shape for the
fourth craft: one method at a time, each its own d20 check, then an always-played
minigame whose 0..1 score the server turns into a quality tier under the alchemist's
ceiling. Nine methods (owner Q3.1): Dissolve, Calcine, Bottle and Assay at level 1;
Distill, Filter and React at 2; Sublime and Transmute at 3. Seal became Bottle,
Precipitate is Filter's solid end, Stabilize is an ingredient (the `stabilizer` working
trait) and Catalyze a working trait that is never spent (`catalyst`).

  check   `plan_step`: what the step would make, the DC itemised, the odds, every shelf
          entry's fit in words, the mishap and toxic lines BEFORE the roll (plan §8.1), the
          possible-formulae count, the slots with reasons, the mix colour;
  roll    the d20 (no naturals: a skill check, CRB p.180). A miss by 4 or less loses the
          time; by 5 or more half the materials are ruined and every unstabilised
          volatile input's mishap lands on the alchemist, once per batch (plan §8.2,
          §15.2). A toxic input lands at the start of the step unless protected (§8.4);
          on a success the step waits behind a token for the game;
  finish  the score becomes the tier, `make` writes the records (rules/alchemy_items.py),
          `land` shelves them, and a spell potion setting, a Transmute or any step longer
          than eight hours goes In progress (rules/inprogress.py, plan §12.3).

**Containment is alchemy's flavour** (owner Q1.1): the stakes are stated before the roll,
the mishap is the one place chance can cost the alchemist (a minigame miss after a
successful roll only lowers quality and never costs materials, plan §3), and it lands
through the engine as ordinary intents stamped `rule:mishap:<material>` (contracts §7),
never through a private applicator.

**Where you work** (plan §14): a field kit anywhere for common and uncommon work; a
laboratory for rare and above and for Distill, Sublime and Transmute, +2 circumstance (the
book's alchemist's lab) and a fume hood. Lane G's `places.laboratory_here`,
`places.has_alchemy_kit` and `market.lab_rent` (contracts §9) are asked when they exist;
until they land there is no laboratory anywhere and the kit folds out wherever the
character stands, as the forge's did before its lane G (`where_here`).

**Mastery** (plan §4.4; owner 2026-10-05 and 2026-10-06): every successful step pays,
through `worldclass.award_step` (a batch of N is N steps; `MISHAP_LIMIT` still caps what
failing teaches); firsts pay 3 (a property learned, a product family made, a reagent
worked, a formula written); and studying a material by assay pays 1 for each property it
reveals, 0 if none (`STUDY_MP`).

**The shelf library** (the bottom of the file): `Material`, `materials()`, `get`,
`KIND_GLYPH`, `ACQUISITION` and `obtainable` still serve the `/craft/` page's shelf and the
acquisition hub (rules/benches.py), now read through the one door
(`materials.alchemy_shelf`, lane A) instead of a private loader: the private loader never
saw the hybrid herbs, and the harvest excursion lost the basilisk eye when the gland row
merged into the herb. The gathering functions are being rebuilt by the gathering-parity
lane and are otherwise left as they were. The old chain (`Chain`, `preview`) retired with
the `/craft/` Alchemy tab: `rules/benches.MOVED` refuses it in words.

Namespace note: "alchemist" here is the WORLD CLASS (`rules.worldclass.get("alchemist")`),
not the PF1e Alchemist character class in `content/classes/`.
"""
from __future__ import annotations

import copy
import importlib
import math
import re
from dataclasses import dataclass, field

from . import alchemy_items as items
from . import worldclass as wc

TRACK_ID = "alchemist"


class CraftError(ValueError):
    """A step that cannot be described at all (kept for the routing table's shape)."""


def _lane(name: str):
    """A sibling lane's module, or None while it is not merged. Imported on each call, so a
    test can stand a fake in `sys.modules` (the forge's `_lane`)."""
    try:
        return importlib.import_module(f"rules.{name}")
    except ImportError:
        return None


# =============================================================================================
# The track's rule rows
# =============================================================================================

def track() -> wc.Track:
    return wc.get(TRACK_ID)


def bench_rules() -> dict:
    """The `bench` block of content/world-classes/alchemist.json (every proposed number)."""
    return dict(track().data.get("bench") or {})


def method_row(method: str) -> dict | None:
    return (bench_rules().get("methods") or {}).get(str(method or "").strip().lower())


def methods_order() -> tuple[str, ...]:
    return tuple(bench_rules().get("order") or ())


METHODS = ("dissolve", "calcine", "filter", "distill", "react", "sublime", "bottle",
           "transmute", "assay")


def method_level(method: str) -> int:
    t = track()
    for row in sorted(t.levels, key=lambda r: r.level):
        if method in row.methods:
            return row.level
    return t.max_level + 1


def rarity_ceiling(level: int) -> int:
    """The rarest material rank a level may work (L1 uncommon, L2 exotic, L3 legendary)."""
    return wc.tier_rank(track().at(max(1, int(level))).max_tier)


def level_for_rank(rank: int) -> int | None:
    for row in sorted(track().levels, key=lambda r: r.level):
        if wc.tier_rank(row.max_tier) >= int(rank):
            return row.level
    return None


def perk_count(progress, perk: str) -> int:
    return int((getattr(progress, "perks", None) or {}).get(perk, 0) or 0)


def containment(progress) -> int:
    """Containment picks, times the perk's size (alchemist.json `endless.perks`)."""
    size = float((track().endless.get("perks") or {}).get("containment", 1) or 0)
    return int(size * perk_count(progress, "containment"))


# Station icons for the old /craft/ tab's method strip (`benches.method_glyphs` prefers a
# module's own map). The new bench draws icon masks (UI plan §4).
METHOD_GLYPH: dict[str, str] = {
    "dissolve": "💧", "calcine": "🔥", "filter": "🧫", "distill": "⚗️", "react": "💥",
    "sublime": "☁️", "bottle": "🧴", "transmute": "🜍", "assay": "🔍",
}

# One glyph per kind, from this track's reserved pool (the shared shelf's rule: a repeated
# glyph would make two different things look like the same thing on one page).
KIND_GLYPH = {
    "reagent": "🜂", "solvent": "🧪", "salt": "🧂", "catalyst": "💠", "essence": "🔆",
    "gland": "🩸", "vessel": "🫙", "treatment": "🧫", "intermediate": "🧊", "potion": "⚱️",
}


# =============================================================================================
# The check
# =============================================================================================

def check_terms(actor, level: int, *, lab: bool = False) -> list[dict]:
    """d20 + Alchemist level + half character level + Intelligence, itemised (plan §7.1),
    with the laboratory's +2 circumstance when the work is done in one (the book's
    alchemist's lab: "+2 circumstance bonus on Craft (alchemy) checks", UE p.77)."""
    track_level = max(0, int(level or 0))
    char_level = max(1, int(getattr(actor, "level", 1) or 1)) if actor is not None else 1
    intelligence = int(actor.ability_mod("int")) if actor is not None else 0
    out = [
        {"label": f"Alchemist {track_level}", "value": track_level},
        {"label": f"half character level ({char_level})", "value": char_level // 2},
        {"label": "Intelligence", "value": intelligence},
    ]
    if lab:
        out.append({"label": "laboratory", "value": int(bench_rules().get("lab_bonus", 2))})
    return out


def check_bonus(actor, level: int, *, lab: bool = False) -> int:
    return sum(t["value"] for t in check_terms(actor, level, lab=lab))


def check_odds(dc: int, bonus: int) -> tuple[int | None, str]:
    """The face needed, or None and why none will do. No naturals (CRB p.180)."""
    from . import crafting

    return crafting.check_odds(dc, bonus)


# =============================================================================================
# Where you work (plan §14; lane G, contracts §9)
# =============================================================================================

def _named(actor, names) -> bool:
    """Whether the actor carries something by one of these names, in either store a
    carried thing can be in (the forge's `has_field_kit` reading, `places.py`)."""
    want = {" ".join(str(n).lower().replace("’", "'").split()) for n in names}

    def said(x) -> bool:
        return " ".join(str(x or "").lower().replace("’", "'").split()) in want

    for s in (getattr(actor, "stock", None) or {}).values():
        if int(getattr(s, "count", 0) or 0) > 0 and (said(getattr(s, "base", ""))
                                                     or said(getattr(s, "name", ""))):
            return True
    for name, n in (getattr(actor, "goods", None) or {}).items():
        if int(n or 0) > 0 and said(name):
            return True
    return False


def laboratory_here(scene, known=()) -> dict | None:
    """Lane G's `places.laboratory_here(scene, known)` (contracts §9), or None while it is
    not merged: no laboratory anywhere, so rare work and Distill, Sublime and Transmute are
    refused with the reason in words."""
    places = _lane("places")
    fn = getattr(places, "laboratory_here", None) if places is not None else None
    if fn is None or scene is None:
        return None
    try:
        return fn(scene, known) or None
    except Exception:  # noqa: BLE001 - a place we cannot read is no laboratory
        return None


def has_kit(actor) -> bool:
    """Lane G's `places.has_alchemy_kit(actor)`; until it lands the field kit folds out
    wherever the character stands (the forge's own fallback before its lane G)."""
    places = _lane("places")
    fn = getattr(places, "has_alchemy_kit", None) if places is not None else None
    if fn is None:
        return True
    try:
        return bool(fn(actor)) or _named(actor, bench_rules().get("kit_names") or ())
    except Exception:  # noqa: BLE001
        return False


def protected(actor, lab: dict | None) -> str:
    """What spares the alchemist a toxic reagent (plan §8.4), in words, or "": a
    laboratory's fume hood, or a mask and gloves carried."""
    if lab and lab.get("fume_hood", True):
        return "the laboratory's fume hood"
    if actor is not None and _named(actor, bench_rules().get("protection_names") or ()):
        return "your mask and gloves"
    return ""


def where_here(scene, actor, known=()) -> dict:
    """{"lab", "kit", "fight", "protected", "label"}, read from the scene and the pack,
    never from the player's words."""
    fight = bool(getattr(scene, "in_encounter", False)) if scene is not None else False
    lab = laboratory_here(scene, known)
    kit = has_kit(actor)
    if fight:
        label = "In a fight: the bench waits until it is over"
    elif lab:
        label = ("In your laboratory" if lab.get("kind") == "owned"
                 else "In a laboratory, rented by the hour")
    elif kit:
        label = "A field kit on the ground"
    else:
        label = "No field kit and no laboratory here"
    return {"lab": lab, "kit": kit, "fight": fight, "protected": protected(actor, lab),
            "label": label}


def rent_cp(scene, lab: dict | None, minutes: int, known=()) -> int:
    """What the laboratory here charges for the minutes (plan §14), asked of lane G's
    `market.lab_rent` when it exists; the laboratory's own rate (or the rule row's 2 sp an
    hour, proposed) only while it does not. Your own laboratory is free."""
    if not lab or minutes <= 0 or lab.get("kind") == "owned":
        return 0
    hours = minutes / 60
    market = _lane("market")
    fn = getattr(market, "lab_rent", None) if market is not None else None
    if fn is not None:
        try:
            return max(0, int(fn(scene, hours, known)))
        except Exception:  # noqa: BLE001
            pass
    rate = int(lab.get("rate_cp_per_hour") or bench_rules().get("lab_rate_cp_per_hour", 20))
    return max(0, int(math.ceil(round(rate * hours, 6))))


def methods_view(level: int, where: dict | None = None) -> list[dict]:
    """The method strip (UI plan §6.1): every method in craft order, its lock in words."""
    where = where or {"lab": None, "kit": True, "fight": False}
    out = []
    for mid in methods_order() or METHODS:
        row = method_row(mid) or {}
        need = method_level(mid)
        reason = ""
        if need > int(level):
            reason = f"Alchemist {need}"
        elif where.get("fight"):
            reason = "Not in a fight"
        elif row.get("where") == "lab" and not where.get("lab"):
            reason = "Needs a laboratory"
        elif not where.get("lab") and not where.get("kit"):
            reason = "Needs a field kit or a laboratory"
        out.append({"id": mid, "name": row.get("name", mid.title()), "level": need,
                    "where": row.get("where", "kit"), "bulk": bool(row.get("bulk")),
                    "locked": bool(reason), "lock_reason": reason,
                    "takes": row.get("takes", ""), "makes": row.get("makes", ""),
                    "minigame": bool(row.get("tuning")),
                    "glyph": METHOD_GLYPH.get(mid, "")})
    return out


# =============================================================================================
# The shelf: what the alchemist carries
# =============================================================================================

GROUPS = {
    "reagent": "Reagents", "gland": "Glands and essences", "essence": "Glands and essences",
    "solvent": "Solvents", "salt": "Salts and spirits", "treatment": "Reagents",
    "herb": "Hybrid herbs", "fungus": "Hybrid herbs", "monster part": "Hybrid herbs",
    "catalyst": "Catalysts and apparatus", "apparatus": "Catalysts and apparatus",
    "vessel": "Vessels", "solution": "Solutions and admixtures",
    "admixture": "Solutions and admixtures", "filtrate": "Solutions and admixtures",
    "spirit": "Salts and spirits", "calx": "Salts and spirits",
    "precipitate": "Salts and spirits", "sublimate": "Salts and spirits",
    "product": "Finished work", "work": "In progress", "old": "Old work",
}

OLD_WORK = "made at the old bench: it can be used or sold, not worked further"


def _working(doc: dict | None) -> list[str]:
    return [str((w or {}).get("trait") if isinstance(w, dict) else w)
            for w in (doc or {}).get("working") or ()]


@dataclass
class Item:
    """One shelf entry (UI plan §6.2): raw material from the satchel's counts, or alchemy
    stock (an intermediate, a product, work in progress, old work). `count` is whole units
    usable; a unit opened by an assay is `cut` tenths down and is not one of them."""
    key: str
    name: str
    material: str = ""
    kind: str = ""
    tier: str = "common"
    count: int = 0
    doc: dict | None = None
    stock: object | None = None
    cut: int = 0
    old: str = ""
    work: str = ""

    @property
    def record(self) -> dict | None:
        rec = getattr(self.stock, "record", None)
        return rec if isinstance(rec, dict) else None

    @property
    def rank(self) -> int:
        return wc.tier_rank(self.tier)

    @property
    def traits(self) -> list[str]:
        """Working traits: a raw material's own; an intermediate's from its form."""
        if self.doc is not None:
            return _working(self.doc)
        rec = self.record
        if rec and rec.get("family") == items.INTERMEDIATE:
            row = items.form_row(str(rec.get("form") or ""))
            return ["liquid"] if row.get("liquid") else ["solid"]
        return []

    @property
    def family(self) -> str:
        rec = self.record
        return str(rec.get("family") or "") if rec else ""

    @property
    def form(self) -> str:
        rec = self.record
        return str(rec.get("form") or "") if rec else ""

    @property
    def intermediate(self) -> bool:
        return self.family == items.INTERMEDIATE

    @property
    def finished(self) -> bool:
        return bool(self.record) and not self.intermediate

    def has(self, trait: str) -> bool:
        return trait in self.traits

    @property
    def liquid(self) -> bool:
        if self.has("liquid"):
            return True
        return bool(self.intermediate and items.form_row(self.form).get("liquid"))

    @property
    def solid(self) -> bool:
        if self.intermediate:
            return not self.liquid
        return not self.has("liquid")

    @property
    def amount(self) -> float:
        return round(self.count + ((10 - self.cut) / 10 if self.cut else 0), 1)

    @property
    def group(self) -> str:
        if self.work:
            return GROUPS["work"]
        if self.old:
            return GROUPS["old"]
        if self.finished:
            return GROUPS["product"]
        if self.intermediate:
            return GROUPS.get(self.form, "Salts and spirits")
        t = self.traits
        if "catalyst" in t or "apparatus" in t:
            return GROUPS["catalyst"]
        if any(x.startswith("solvent:") for x in t):
            return GROUPS["solvent"]
        return GROUPS.get(self.kind, "Reagents")

    def badges(self) -> list[str]:
        out = []
        t = self.traits
        for word in ("volatile", "toxic_to_handle", "catalyst", "apparatus", "stabilizer",
                     "corrosive", "combustible", "wild"):
            if word in t:
                out.append(word.replace("_", " "))
        rec = self.record
        if rec:
            conc = int(rec.get("concentration") or 0)
            if conc:
                out.append(f"concentrated x{conc + 1}")
            if rec.get("filtered"):
                out.append("filtered")
        return out

    def color(self) -> list[float] | None:
        if self.doc is not None:
            c = self.doc.get("color")
            return list(c) if isinstance(c, list) and len(c) == 3 else None
        rec = self.record
        if rec:
            return mix_color([(m, 1) for m in items.record_materials(rec)])
        return None


def _shelf_doc(mid: str) -> dict | None:
    return items.doc_of(mid)


def _by_name() -> dict[str, str]:
    from . import materials

    return {str(d.get("name") or "").lower(): mid
            for mid, d in materials.alchemy_shelf().items()}


def shelf(actor, now: int = 0, reserved: dict | None = None) -> list[Item]:
    """Everything the bench can reach for: only what is carried (UI plan §6.2). Raw
    materials from `Actor.inventory` (bought, gathered, harvested), and from the stock the
    alchemist's own records, old alchemist work, and bought goods that are shelf
    materials by name. `reserved` is `{key: count}` held by a step between its roll and
    its finish."""
    from . import inprogress

    reserved = reserved or {}
    out: list[Item] = []
    if actor is None:
        return out
    for mid, n in sorted((getattr(actor, "inventory", None) or {}).items()):
        if int(n or 0) <= 0:
            continue
        doc = _shelf_doc(mid)
        if doc is None:
            continue
        key = f"inv:{mid}"
        count = int(n) - int(reserved.get(key, 0))
        if count > 0:
            out.append(Item(key=key, name=str(doc.get("name") or mid), material=mid,
                            kind=str(doc.get("kind") or "reagent"),
                            tier=str(doc.get("tier") or "common"), count=count, doc=doc))
    names = None
    for sid, st in sorted((getattr(actor, "stock", None) or {}).items(),
                          key=lambda kv: kv[1].name.lower()):
        key = f"stock:{sid}"
        whole = int(getattr(st, "count", 0) or 0)
        count = whole - int(reserved.get(key, 0))
        if isinstance(st, items.AlchemyStock):
            rec = st.record
            work = inprogress.held_back(st, now)
            if rec.get("family") == "raw":
                # A unit an assay opened (plan §13.2: a pinch is a tenth, tracked as tenths).
                mid = str(rec.get("material") or "")
                doc = _shelf_doc(mid)
                if doc is not None and whole > 0:
                    out.append(Item(key=key, name=str(doc.get("name") or mid), material=mid,
                                    kind=str(doc.get("kind") or "reagent"),
                                    tier=str(doc.get("tier") or "common"),
                                    count=max(0, count - 1), doc=doc,
                                    stock=st, cut=int(rec.get("cut") or 0)))
                continue
            if count <= 0 and not work:
                continue
            out.append(Item(key=key, name=st.name, kind="intermediate" if
                            rec.get("family") == items.INTERMEDIATE else "product",
                            tier=str(st.tier or "common"), count=max(0, count), stock=st,
                            work=work))
            continue
        if count <= 0:
            continue
        if str(getattr(st, "craft", "") or "") == TRACK_ID:
            out.append(Item(key=key, name=st.name, kind="old", tier=str(st.tier or "common"),
                            count=count, stock=st, old=OLD_WORK,
                            work=inprogress.held_back(st, now)))
            continue
        if names is None:
            names = _by_name()
        mid = names.get(str(getattr(st, "base", "") or "").lower())
        doc = _shelf_doc(mid) if mid else None
        if doc is not None:
            out.append(Item(key=key, name=st.name, material=mid,
                            kind=str(doc.get("kind") or "reagent"),
                            tier=str(doc.get("tier") or "common"), count=count, doc=doc,
                            stock=st))
    return out


def find(actor, key: str, now: int = 0, reserved: dict | None = None) -> Item | None:
    key = str(key or "")
    for it in shelf(actor, now, reserved):
        if it.key == key or (it.material and key in (it.material, f"inv:{it.material}")):
            return it
    return None


def mix_color(parts) -> list[float] | None:
    """The mix colour (UI plan §7.4): the inputs' `color`s weighted by amount, computed
    here so the page never invents one. `parts`: [(material id, amount)]."""
    total, acc = 0.0, [0.0, 0.0, 0.0]
    for mid, n in parts:
        doc = _shelf_doc(mid) or {}
        c = doc.get("color")
        if not (isinstance(c, list) and len(c) == 3):
            continue
        w = max(0.0, float(n or 0))
        total += w
        acc = [a + w * float(x) for a, x in zip(acc, c)]
    if total <= 0:
        return None
    return [round(a / total, 3) for a in acc]


# =============================================================================================
# Whether one thing fits a role
# =============================================================================================

ROLES = ("inputs", "solvent", "vessel", "catalysts")


def _corrosive_metal(vessel: Item) -> bool:
    """A metal vessel (contracts §10.2: the metal tag, `rules/item_tags.py`): iron flask
    and brass casing, read from the vessel's `material` link."""
    from . import item_tags

    try:
        return item_tags.substance_of(vessel.material) == "metal"
    except Exception:  # noqa: BLE001 - a vessel the tags cannot read is not metal
        return False


def fit_reason(method: str, role: str, it: Item) -> str:
    """Why this shelf entry cannot take this role in this method, in words, or "" when it
    fits. Every dimmed row carries one (UI plan §6.2: never colour alone)."""
    if it.work:
        return f"it is {it.work}"
    if it.old:
        return it.old
    if it.finished:
        return "a finished product cannot go back into the glass"
    if it.count <= 0:
        return "only part of one is left of it"
    t = it.traits
    if role == "catalysts":
        if "catalyst" in t or "apparatus" in t:
            return ""
        return "it is not a catalyst or apparatus: those are never spent"
    if "apparatus" in t:
        return "it is apparatus: set it beside the work, it is never spent"
    if role == "vessel":
        from . import effectspec

        if not any(x in effectspec.VESSEL_TRAITS for x in t) or "apparatus" in t:
            return "it is not a vessel: a vial, a flask, a bladder, a casing or a rod"
        return ""
    if role == "solvent":
        if any(x.startswith("solvent:") for x in t):
            return ""
        return "it is not a solvent: water, spirits, vinegar, oil or acid"
    from . import effectspec

    if any(x in effectspec.VESSEL_TRAITS for x in t) and it.doc is not None \
            and str(it.doc.get("kind")) == "vessel":
        return "it is a vessel: bottle into it"
    if method == "dissolve":
        if it.liquid:
            return "it is already a liquid: react it, filter it or bottle it"
        return ""
    if method == "calcine":
        if it.liquid:
            return "a liquid does not calcine"
        if "combustible" in t:
            return "it burns away; it will not calcine"
        return ""
    if method in ("distill", "filter"):
        if not it.liquid:
            return f"{'distilling' if method == 'distill' else 'filtering'} takes a liquid"
        return ""
    if method == "sublime":
        return "" if it.solid else "subliming takes a solid"
    if method == "react":
        return ""
    if method == "bottle":
        if it.liquid or it.intermediate:
            return ""
        if str((it.doc or {}).get("kind")) in ("salt", "essence"):
            return ""
        return "bottle a liquid or a powder: dissolve or calcine it first"
    if method == "transmute":
        if it.intermediate:
            return "transmute works a raw material, not a worked one"
        return ""
    return ""


def fits_for(method: str, shelf_items: list[Item]) -> dict:
    """`{role: {key: reason or ""}}` for every shelf entry and every role of the method,
    which is what dims rows (contracts §8 `check`)."""
    roles = ["inputs"]
    if method == "dissolve":
        roles.append("solvent")
    if method == "bottle":
        roles.append("vessel")
    roles.append("catalysts")
    return {role: {it.key: fit_reason(method, role, it) for it in shelf_items}
            for role in roles}


# =============================================================================================
# One step
# =============================================================================================

@dataclass
class AlchemyPlan:
    """What one step would do: everything `check` shows, `roll` gates on and `finish`
    makes. Built fresh for every request; nothing in it is trusted from the page."""
    method: str
    batch: int = 1
    units: int = 0
    level: int = 1
    ceiling: int = 2
    inputs: list = field(default_factory=list)      # [(Item, per unit)]
    solvent: Item | None = None
    vessel: Item | None = None
    catalysts: list = field(default_factory=list)   # [Item]
    problems: list = field(default_factory=list)
    notes: list = field(default_factory=list)
    dc: int = 0
    dc_terms: list = field(default_factory=list)
    bonus: int = 0
    terms: list = field(default_factory=list)
    need: int | None = None
    impossible: str = ""
    minutes: int = 0
    hands_on: int = 0
    waits: int = 0                                  # minutes In progress after the step
    consumes: list = field(default_factory=list)    # [(Item, total)]
    pool: dict = field(default_factory=dict)
    mix: dict = field(default_factory=dict)
    choice: dict = field(default_factory=dict)
    match: dict = field(default_factory=dict)
    could: dict = field(default_factory=dict)
    family: str = ""
    form: str = ""
    formula: dict | None = None
    concentration: int = 0
    filtered: int = 0
    worked: list = field(default_factory=list)
    rank_in: int = 1
    rank_out: int = 1
    tier: str = "common"
    lead: str = ""
    working: list = field(default_factory=list)
    volatiles: list = field(default_factory=list)   # [(mid, name)]
    stabilized: list = field(default_factory=list)  # [(mid, name, by)]
    mishaps: list = field(default_factory=list)     # [(mid, name, spec)]
    toxics: list = field(default_factory=list)      # [(mid, name, spec)]
    protected: str = ""
    lab: dict | None = None
    roll_twice: bool = False
    yields: bool = False
    target: str = ""                                # Transmute's output
    candidates: list = field(default_factory=list)
    strip: list = field(default_factory=list)
    perks: dict = field(default_factory=dict)
    experiment: bool = False

    @property
    def can_roll(self) -> bool:
        return not self.problems and self.need is not None and self.units > 0

    @property
    def noun(self) -> str:
        if self.method == "bottle":
            return items.FAMILY_WORDS.get(self.family, "product") if self.family else "product"
        if self.method == "transmute":
            return "transmutation"
        return (items.form_row(self.form).get("word") or "measure").lower()

    @property
    def info(self) -> str:
        """The line under the stage (UI plan §6.3): "3 flasks. 30m. DC 20, you need 12 or
        better." Every number in it is this plan's."""
        if not self.units:
            return ""
        from . import sky

        word = self.noun + ("" if self.units == 1 else "s")
        line = f"{self.units} {word}. {sky.span_words(self.minutes)}"
        if self.waits:
            line += f", then {sky.span_words(self.waits)} In progress"
        line += f". DC {self.dc}"
        if self.need is None:
            return f"{line}: {self.impossible}."
        return f"{line}, you need {self.need} or better."


def _items_of(actor, body, now: int, key: str) -> list:
    raw = body.get(key)
    if raw in (None, "", []):
        return []
    if not isinstance(raw, list):
        raw = [raw]
    out = []
    for entry in raw:
        if isinstance(entry, dict):
            k, n = str(entry.get("key") or entry.get("item") or ""), entry.get("count", 1)
        else:
            k, n = str(entry), 1
        try:
            n = max(1, int(n or 1))
        except (TypeError, ValueError):
            n = 1
        out.append((k, n))
    return out


def _dc_of(it: Item) -> int:
    if it.doc is not None and it.doc.get("craft_dc") not in (None, ""):
        try:
            return int(it.doc["craft_dc"])
        except (TypeError, ValueError):
            pass
    return 5 + 5 * it.rank


def _smaller(dice: str, steps: int) -> str:
    """A mishap's dice one step smaller per Containment pick (plan §4.2): 1d6 -> 1d4 -> 1d3
    -> 1, never below 1 point. A die larger than d6 walks down the same ladder."""
    ladder = [12, 10, 8, 6, 4, 3, 2]
    text = str(dice or "").replace(" ", "")
    m = re.fullmatch(r"(\d*)d(\d+)([+-]\d+)?", text)
    if not m or steps <= 0:
        return text or "1"
    count, sides = int(m.group(1) or 1), int(m.group(2))
    flat = m.group(3) or ""
    for _ in range(steps):
        smaller = [s for s in ladder if s < sides]
        if not smaller or sides <= 2:
            return str(max(1, count))
        sides = smaller[0]
    return f"{count}d{sides}{flat}"


def _contained(spec: dict, steps: int) -> dict:
    s = copy.deepcopy(spec)
    if s.get("dice") not in (None, ""):
        s["dice"] = _smaller(s["dice"], steps)
    for branch in ("on_failure", "on_success"):
        if isinstance(s.get(branch), list):
            s[branch] = [_contained(c, steps) for c in s[branch] if isinstance(c, dict)]
    return s


def _catalyst_jobs(mid: str) -> list[str]:
    return list((bench_rules().get("catalyst_jobs") or {}).get(mid) or ())


def plan_step(actor, progress, method: str, body: dict, *, where: dict | None = None,
              now: int = 0, reserved: dict | None = None) -> AlchemyPlan:
    """One step, worked out without changing anything (contracts §8 `check`).

    `body`: {"inputs": [{"key", "count"}], "solvent": key, "vessel": key, "catalysts":
    [key], "formula": id | null, "as": "potion" | "oil", "picks": [trait keys], "wild":
    key, "strip": key, "target": material id, "batch": n}. Keys are the shelf's ("inv:<id>"
    or "stock:<id>"). `where` is `where_here`'s answer; None means a field kit and no
    laboratory, which is what the rules tests want."""
    method = str(method or "").strip().lower()
    level = int(getattr(progress, "level", 1) or 1)
    where = where or {"lab": None, "kit": True, "fight": False, "protected": ""}
    try:
        batch = max(1, int((body or {}).get("batch") or 1))
    except (TypeError, ValueError):
        batch = 1
    plan = AlchemyPlan(method=method, batch=batch, level=level,
                       ceiling=wc.ceiling_index(progress) if progress is not None else 2,
                       lab=where.get("lab"), protected=str(where.get("protected") or ""),
                       perks={p: perk_count(progress, p) for p in
                              ("potency", "duration", "quality", "yield", "containment")})
    row = method_row(method)
    if row is None:
        plan.problems.append(f"There is no alchemy step called {method!r}.")
        return plan
    if method == "assay":
        plan.problems.append("An assay is not worked at the bench: assay a reagent from its "
                             "card.")
        return plan
    plan.terms = check_terms(actor, level, lab=bool(plan.lab))
    plan.bonus = sum(t["value"] for t in plan.terms)
    need = method_level(method)
    if need > level:
        plan.problems.append(f"{row['name']} is learned at Alchemist {need}.")
    if where.get("fight"):
        plan.problems.append("You are in a fight. The bench waits until it is over.")
    if row.get("where") == "lab" and not plan.lab:
        plan.problems.append(f"It needs a laboratory: {row['name'].lower()} is not field "
                             f"work.")
    elif not plan.lab and not where.get("kit"):
        plan.problems.append("You have no field kit with you, and there is no laboratory "
                             "here.")
    if batch > 1 and not row.get("bulk"):
        plan.problems.append(f"{row['name']} works one at a time; there is no batch.")
        return plan

    shelf_items = {it.key: it for it in shelf(actor, now, reserved)}

    def pick(key_):
        it = shelf_items.get(key_)
        if it is None:
            alt = f"inv:{key_}" if not key_.startswith(("inv:", "stock:")) else ""
            it = shelf_items.get(alt) if alt else None
        return it

    for k, n in _items_of(actor, body, now, "inputs"):
        it = pick(k)
        if it is None:
            plan.problems.append(f"You carry no {k.split(':', 1)[-1].replace('-', ' ')}.")
            continue
        if any(x.key == it.key for x, _ in plan.inputs):
            continue
        plan.inputs.append((it, n))
    for role in ("solvent", "vessel"):
        got = _items_of(actor, body, now, role)
        if got:
            it = pick(got[0][0])
            if it is None:
                plan.problems.append(f"You carry no {got[0][0].split(':', 1)[-1]}.")
            else:
                setattr(plan, role, it)
    for k, _n in _items_of(actor, body, now, "catalysts"):
        it = pick(k)
        if it is None:
            plan.problems.append(f"You carry no {k.split(':', 1)[-1].replace('-', ' ')}.")
        elif all(c.key != it.key for c in plan.catalysts):
            plan.catalysts.append(it)
    for it, _n in plan.inputs:
        why = fit_reason(method, "inputs", it)
        if why:
            plan.problems.append(f"{it.name}: {why}.")
    for role in ("solvent", "vessel"):
        it = getattr(plan, role)
        if it is not None:
            why = fit_reason(method, role, it)
            if why:
                plan.problems.append(f"{it.name}: {why}.")
    for it in plan.catalysts:
        why = fit_reason(method, "catalysts", it)
        if why:
            plan.problems.append(f"{it.name}: {why}.")
    if plan.problems:
        return plan

    _BUILD[method](plan, actor, body, row)
    if plan.problems:
        return plan
    _common(plan, actor, body, row)
    return plan


def _sources(plan: AlchemyPlan) -> list[dict]:
    """The pool's sources, one per distinct input (count is batch, not strength)."""
    out = []
    for it in [i for i, _ in plan.inputs] + ([plan.solvent] if plan.solvent else []):
        if it.record is not None:
            out.append({"record": it.record})
        elif it.material:
            out.append({"material": it.material, "wild": it.has("wild")})
    return out


def _conc(plan: AlchemyPlan) -> int:
    return max([int((it.record or {}).get("concentration") or 0) for it, _ in plan.inputs]
               + [0])


def _filtered(plan: AlchemyPlan) -> int:
    return max([int((it.record or {}).get("filtered") or 0) for it, _ in plan.inputs] + [0])


def _need_inputs(plan: AlchemyPlan, n: int, words: str) -> bool:
    if len(plan.inputs) < n:
        plan.problems.append(words)
        return False
    return True


def _build_dissolve(plan, actor, body, row):
    if not _need_inputs(plan, 1, "Put a solid in the flask to dissolve."):
        return
    if plan.solvent is None:
        plan.problems.append("Choose a solvent: water, spirits, vinegar, oil or acid.")
        return
    plan.form = "solution"
    plan.concentration = _conc(plan)
    plan.filtered = _filtered(plan)


def _build_calcine(plan, actor, body, row):
    if _need_inputs(plan, 1, "Put a solid in the crucible."):
        plan.form = "calx"
        plan.concentration = _conc(plan)
        plan.filtered = _filtered(plan)


def _build_filter(plan, actor, body, row):
    if not _need_inputs(plan, 1, "Pour a solution onto the cloth."):
        return
    if len(plan.inputs) > 1:
        plan.problems.append("Filter one liquid at a time.")
        return
    plan.form = "filtrate"
    plan.concentration = _conc(plan)
    plan.filtered = _filtered(plan) + 1


def _build_distill(plan, actor, body, row):
    if not _need_inputs(plan, 1, "Put a liquid in the cucurbit."):
        return
    if len(plan.inputs) > 1:
        plan.problems.append("Distill one liquid at a time.")
        return
    plan.form = "spirit"
    plan.concentration = _conc(plan) + 1
    plan.filtered = _filtered(plan)


def _build_sublime(plan, actor, body, row):
    if not _need_inputs(plan, 1, "Put a solid in the aludel."):
        return
    if len(plan.inputs) > 1:
        plan.problems.append("Sublime one solid at a time.")
        return
    plan.form = "sublimate"
    plan.concentration = _conc(plan) + 1
    plan.filtered = _filtered(plan)


def _build_react(plan, actor, body, row):
    if not _need_inputs(plan, 2, "A reaction takes two or more inputs."):
        return
    if not any(it.liquid or any(t.startswith("solvent:") for t in it.traits)
               for it, _ in plan.inputs):
        plan.problems.append("A reaction needs a medium: put in a solvent, a solution or a "
                             "spirit.")
        return
    plan.form = "admixture"
    plan.concentration = _conc(plan)
    plan.filtered = _filtered(plan)


def _build_bottle(plan, actor, body, row):
    from . import formulae

    if not _need_inputs(plan, 1, "Put a liquid or a powder on the bench to bottle."):
        return
    if plan.vessel is None:
        plan.problems.append("Choose a vessel to bottle into.")
        return
    if any(it.has("corrosive") for it, _ in plan.inputs) and _corrosive_metal(plan.vessel):
        plan.problems.append(f"Something corrosive would eat through the {plan.vessel.name}: "
                             f"bottle it in glass or clay.")
        return
    plan.concentration = _conc(plan)
    plan.filtered = _filtered(plan)
    plan.yields = True


def _build_transmute(plan, actor, body, row):
    if len(plan.inputs) != 1:
        plan.problems.append("Transmute works one material at a time.")
        return
    it = plan.inputs[0][0]
    plan.candidates = transmute_candidates(it.material, plan.level)
    target = str(body.get("target") or "").strip().lower()
    if not plan.candidates:
        plan.problems.append(f"Nothing {it.name.lower()} can become: no material of its "
                             f"kind one band rarer shares an essence with it.")
        return
    if not target:
        plan.problems.append("Choose what it becomes.")
        return
    if target not in {c["id"] for c in plan.candidates}:
        doc = _shelf_doc(target) or {}
        plan.problems.append(f"{it.name} does not become {doc.get('name') or target}: it "
                             f"becomes one of its own kind, one band rarer, that shares an "
                             f"essence with it.")
        return
    plan.target = target


_BUILD = {"dissolve": _build_dissolve, "calcine": _build_calcine, "filter": _build_filter,
          "distill": _build_distill, "sublime": _build_sublime, "react": _build_react,
          "bottle": _build_bottle, "transmute": _build_transmute}


def _common(plan: AlchemyPlan, actor, body: dict, row: dict) -> None:
    """Everything the steps share: units and what they consume, the pool, the formula,
    the slots, rarity and the laboratory, the volatile and toxic stakes, the DC, the time.
    """
    from . import formulae

    rules = bench_rules()
    per = int(row.get("per_unit", 1) or 1)
    one_for_one = plan.method == "transmute" and any(
        "one_for_one" in _catalyst_jobs(c.material) for c in plan.catalysts)
    if one_for_one:
        per = 1
    plan.units = plan.batch
    for it, n in plan.inputs:
        plan.consumes.append((it, (per if per > 1 else int(n)) * plan.units))
    if plan.solvent is not None:
        plan.consumes.append((plan.solvent, plan.units))
    if plan.vessel is not None:
        plan.consumes.append((plan.vessel, plan.units))
    used: dict[str, list] = {}
    for it, n in plan.consumes:
        used.setdefault(it.key, [it, 0])[1] += int(n)
    for it, n in used.values():
        if n > it.count:
            plan.problems.append(f"{it.name}: the step wants {n} and you carry {it.count}.")

    # Rarity, and the laboratory for rare and up (plan §4.1, §14).
    top = rarity_ceiling(plan.level)
    lab_rank = int(rules.get("lab_rank", 3))
    every = [it for it, _ in plan.inputs] + [x for x in (plan.solvent, plan.vessel) if x] \
        + plan.catalysts
    for it in every:
        if it.rank > top:
            lvl = level_for_rank(it.rank)
            plan.problems.append(f"{it.name} is {it.tier}; Alchemist {plan.level} works "
                                 f"{wc.TIERS[top - 1]} at best"
                                 + (f": it needs Alchemist {lvl}." if lvl else "."))
        elif it.rank >= lab_rank and not plan.lab:
            plan.problems.append(f"{it.name} is {it.tier}: rare and rarer work needs a "
                                 f"laboratory, not a field kit.")
    plan.rank_in = max([it.rank for it in every] + [1])

    # The pool, and what the step makes of it (plan §6).
    wild = str(body.get("wild") or "") or None
    plan.pool = items.pool(_sources(plan), level=plan.level, wild=wild)
    plan.mix = items.mix_of(plan.pool)
    plan.lead = next((it.material or (items.record_materials(it.record or {})[:1] or [""])[0]
                      for it, _ in plan.inputs), "")
    plan.worked = []
    for it, _ in plan.inputs:
        for m in (it.record or {}).get("worked") or ():
            if m not in plan.worked:
                plan.worked.append(m)
    plan.worked.append(plan.method)
    strip_keys = []
    if any("strip_one" in _catalyst_jobs(c.material) for c in plan.catalysts):
        want = str(body.get("strip") or "")
        bad = [r["key"] for r in plan.pool.get("drawbacks") or ()]
        if bad:
            strip_keys = [want if want in bad else bad[0]]
    plan.strip = strip_keys
    picks = body.get("picks")
    if picks is not None and not isinstance(picks, list):
        picks = [picks]

    if plan.method == "bottle":
        vid = plan.vessel.material
        fams = formulae.vessel_families(vid)
        fid = body.get("formula")
        fid = None if fid in (None, "", "experiment") else str(fid)
        plan.experiment = fid is None
        plan.match = formulae.match(actor, plan.mix, vid, fid)
        plan.could = formulae.could_become(actor, plan.mix, vid)
        for r in plan.match.get("refused") or ():
            plan.problems.append(r)
        if fid and plan.match.get("missing"):
            plan.problems.append(f"The mix falls short: {'; '.join(plan.match['missing'])}.")
        if plan.match.get("formula"):
            plan.formula = formulae.get(plan.match["formula"])
            plan.family = str(plan.match.get("family") or plan.formula.get("family"))
        else:
            want = str(body.get("as") or "")
            plan.family = want if want in fams else (fams[0] if fams else "")
            if plan.experiment and plan.match.get("ambiguous"):
                plan.notes.append(f"This fits {plan.match['ambiguous']} formulae. A writing "
                                  f"would tell you which; bottled now it is your own "
                                  f"compound.")
        if not plan.family:
            plan.problems.append(f"The {plan.vessel.name} decides no product.")
            return
        plan.choice = items.choose(plan.pool, family=plan.family, formula=plan.formula,
                                   picks=picks, level=plan.level, strip=strip_keys)
        if not plan.formula and not plan.choice["traits"]:
            plan.problems.append(f"Nothing in the mix can be carried by "
                                 f"{items._a(items.FAMILY_WORDS.get(plan.family, plan.family))}"
                                 f": see why beside each trait.")
        if plan.formula and plan.formula.get("harmful") and plan.family == "potion":
            plan.notes.append(f"The drinker is the target: this would {plan.formula['name']} "
                              f"you, or whoever you hand it to.")
    elif plan.method == "transmute":
        plan.choice = {"traits": [], "drawbacks": [], "rows": [], "drawback_rows": [],
                       "slots": 0, "free": 0}
    else:
        plan.family = items.INTERMEDIATE
        plan.choice = items.choose(plan.pool, family=items.INTERMEDIATE, picks=picks,
                                   level=plan.level, strip=strip_keys)
        plan.could = formulae.could_become(actor, plan.mix, None)

    # What the output is, and whether the level reaches it (concentration moves it rarer).
    # As rare as what goes INTO it (a vessel or a catalyst that is never spent does not
    # make the work rarer; `alchemy_items._tier_of` reads the same materials).
    rank_spent = max([wc.tier_rank(str((_shelf_doc(m) or {}).get("tier") or "common"))
                      for m in plan.pool.get("materials") or ()] + [1])
    if plan.method == "transmute":
        plan.rank_out = wc.tier_rank(str((_shelf_doc(plan.target) or {}).get("tier") or "common"))
    else:
        plan.rank_out = min(len(wc.TIERS), max(rank_spent, wc.tier_rank(str(
            (plan.formula or {}).get("tier") or "common"))) + plan.concentration)
    plan.tier = wc.TIERS[max(1, plan.rank_out) - 1]
    if plan.rank_out > top and not any("needs Alchemist" in x for x in plan.problems):
        lvl = level_for_rank(plan.rank_out)
        plan.problems.append(f"This would make {plan.tier} work, beyond Alchemist "
                             f"{plan.level}" + (f": it needs Alchemist {lvl}." if lvl else "."))

    # Working traits read by the game, and pure material (roll twice).
    for it in every:
        for t in it.traits:
            if t not in plan.working:
                plan.working.append(t)
    plan.roll_twice = any(it.has("pure") for it in plan.catalysts) or any(
        "roll_twice" in _catalyst_jobs(c.material) for c in plan.catalysts)

    # Volatility (plan §8): stated before the roll, stabilizers cancel one each.
    spent = [it for it, _ in plan.inputs] + ([plan.solvent] if plan.solvent else [])
    vol = []
    for it in spent:
        if it.doc is not None and it.has("volatile") and it.doc.get("mishap"):
            vol.append((it.material, it.name, dict(it.doc["mishap"])))
    stabs = [it.name for it in spent if it.has("stabilizer")] + \
        [c.name for c in plan.catalysts if c.has("stabilizer")
         or "stabilizes" in _catalyst_jobs(c.material)]
    vol.sort(key=lambda v: -items._strength(v[2]))
    plan.volatiles = [(m, n) for m, n, _ in vol]
    for by in stabs:
        if not vol:
            break
        m, n, _spec = vol.pop(0)
        plan.stabilized.append((m, n, by))
    from types import SimpleNamespace

    containment_steps = containment(SimpleNamespace(perks=plan.perks))
    plan.mishaps = [(m, n, _contained(s, containment_steps)) for m, n, s in vol]

    # Toxic to handle (plan §8.4): at the start of the step, unless protected.
    if not plan.protected:
        for it in spent + plan.catalysts:
            if it.doc is not None and it.has("toxic_to_handle") and it.doc.get("toxic"):
                plan.toxics.append((it.material, it.name, dict(it.doc["toxic"])))

    # The DC (plan §7.1), itemised.
    terms: list[dict] = []
    if plan.method == "transmute":
        tr = rules.get("transmute") or {}
        base = int(tr.get("dc_base", 10)) + int(tr.get("dc_per_band", 5)) * (plan.rank_out - 1)
        terms.append({"label": f"{plan.tier} output", "value": base})
    elif plan.method == "bottle" and plan.formula is not None:
        f = plan.formula
        if f.get("kind") == "spell":
            terms.append({"label": f"5 + caster level {f.get('caster_level')}",
                          "value": 5 + int(f.get("caster_level") or 1)})
        else:
            terms.append({"label": f"{f['name']}, the book's DC",
                          "value": int(f.get("craft_dc") or 10)})
    else:
        hardest = max([(_dc_of(it), it) for it in spent if it is not None] or [(10, None)],
                      key=lambda x: x[0])
        terms.append({"label": f"{hardest[1].name} (the hardest input)" if hardest[1]
                      else "the work", "value": hardest[0]})
    if row.get("concentrates"):
        terms.append({"label": f"concentration step {plan.concentration}",
                      "value": int((rules.get("concentration") or {}).get("dc_per_step", 2))
                      * plan.concentration})
    live = len(plan.mishaps)
    if live > 1:
        terms.append({"label": f"{live} volatile inputs",
                      "value": int(rules.get("volatile_dc_step", 3)) * (live - 1)})
    if live and containment_steps:
        terms.append({"label": "Containment", "value": -containment_steps})
    plan.dc_terms = terms
    plan.dc = sum(t["value"] for t in terms)

    # Time (plan §7, §12.3): a step past the threshold waits In progress.
    minutes = int(row.get("minutes", 10) or 10) * plan.units
    after = int(rules.get("in_progress_after", 480))
    if plan.method == "transmute" or minutes > after:
        plan.hands_on = int(row.get("hands_on", min(minutes, 60)) or 60)
        plan.waits = max(0, minutes - plan.hands_on) if plan.method != "transmute" \
            else minutes
        plan.minutes = plan.hands_on
    else:
        plan.minutes = minutes
        plan.hands_on = minutes
    if plan.method == "bottle" and plan.formula is not None \
            and plan.formula.get("kind") == "spell":
        # A spell potion sets for the Brew Potion feat's time (plan §11.4), at its price
        # at the minimum caster level; the price is the book's at the CL the tier gives.
        price = formulae.potion_price(int(plan.formula.get("spell_level") or 0),
                                      int(plan.formula.get("caster_level") or 1))
        plan.waits = formulae.brew_minutes(price * plan.units)
    plan.need, plan.impossible = check_odds(plan.dc, plan.bonus)


# Brewing costs only the ingredients put in (the owner, 2026-10-07: "Ingredients only").
# Lane H's `pricing.coin_to_make` (the book's making fraction less the inputs' worth) is
# deliberately not called: no coin step at Bottle. A cheap-ingredient potion selling for
# far more than it cost is accepted knowingly.


# =============================================================================================
# What the page is shown for one plan
# =============================================================================================

def stakes(plan: AlchemyPlan) -> dict:
    """The mishap and toxic lines, before the roll (plan §8.1, UI §6.3), in words."""
    from . import effectspec

    mishap = []
    for mid, name, spec in plan.mishaps:
        words = effectspec.render(dict(spec, recipient="self"))
        mishap.append({"material": mid, "name": name, "text": f"{words} ({name.lower()})"})
    line = ""
    if mishap:
        line = ("If this fails by 5 or more: "
                + "; ".join(m["text"] for m in mishap)
                + ". Half the materials are ruined.")
    toxic = [{"material": mid, "name": name,
              "text": f"{name}: {effectspec.render(spec)}, unless you are protected"}
             for mid, name, spec in plan.toxics]
    stabilized = [f"{by} calms the {name.lower()}" for _m, name, by in plan.stabilized]
    return {"mishap": mishap, "mishap_line": line, "toxic": toxic,
            "toxic_line": "; ".join(t["text"] for t in toxic),
            "protected": plan.protected, "stabilized": stabilized,
            "volatile_count": len(plan.mishaps)}


def tuning_for(plan: AlchemyPlan) -> dict:
    """The minigame's numbers (contracts §12, UI plan §9): the method's base difficulty,
    harder by `rarity_step` per band above common (rarer reagents narrow the window), and
    the working traits' band scales (a catalyst or apparatus widens it, slow to dissolve
    narrows Dissolve's). The same at every level: skill raises the ceiling, not the
    window."""
    rules = bench_rules()
    row = method_row(plan.method) or {}
    tun = copy.deepcopy(row.get("tuning") or {})
    traits = rules.get("traits") or {}
    band = 1.0
    present = set(plan.working)
    for name, spec in traits.items():
        if name not in present or "band" not in spec:
            continue
        if spec.get("only") and spec["only"] != plan.method:
            continue
        band *= float(spec["band"])
    diff = float(tun.get("difficulty", 0.45)) + float(rules.get("rarity_step", 0.05)) * \
        max(0, plan.rank_in - 1)
    ceiling = max(0, int(plan.ceiling))
    out = {"method": plan.method, "game": tun.get("game", plan.method),
           "gauge": tun.get("gauge", ""), "difficulty": round(min(0.95, diff), 4),
           "band_scale": round(band, 4), "seconds": tun.get("seconds", 6),
           "traits": list(plan.working),
           "names": [wc.quality_name(t) for t in range(ceiling + 1)],
           "bands": [t / (ceiling + 1) for t in range(ceiling + 1)]}
    for k in ("heat", "reaction", "stages", "pour"):
        if k in tun:
            out[k] = tun[k]
    if "reaction" in out and band != 1.0:
        lo, hi = out["reaction"]["band"]
        mid, half = (lo + hi) / 2, (hi - lo) / 2 * band
        out["reaction"] = dict(out["reaction"], band=[round(max(0, mid - half), 1),
                                                      round(min(100, mid + half), 1)])
    return out


def liquid_for(plan: AlchemyPlan) -> dict:
    """The stage's liquid (UI plan §7.4): colour from the inputs, the level from the
    volume, the turbidity from the method's start and end. Presentation values the server
    authors, so the page interpolates between two it was sent and invents none."""
    row = method_row(plan.method) or {}
    tun = (row.get("tuning") or {}).get("liquid") or {}
    parts = []
    for it, n in plan.inputs + ([(plan.solvent, 1)] if plan.solvent else []):
        mats = [it.material] if it.material else items.record_materials(it.record or {})
        for m in mats:
            parts.append((m, n))
    color = mix_color(parts)
    level = round(min(1.0, 0.2 + 0.12 * sum(int(n) for _, n in parts)), 3)
    start = {"color": color, "level": level,
             "turbidity": float((tun.get("start") or {}).get("turbidity", 0.3))}
    end = {"color": color, "level": level if not (method_row(plan.method) or {}).get(
        "concentrates") else round(level / 2, 3),
        "turbidity": float((tun.get("end") or {}).get("turbidity", 0.1))}
    return {"start": start, "end": end}


# =============================================================================================
# The roll's consequences
# =============================================================================================

def rule_intents(effects, *, kind: str, actor_ref: str) -> list[tuple[str, str, list[dict]]]:
    """Mishap or toxic documents as intents on the alchemist (contracts §7: "the bench's
    mishap and toxic effects arrive as ordinary intents with origin rule:<kind>:<material>,
    through validate and run. There is no private applicator."). `effects` are
    (material, name, spec). Each becomes intents for one creature — the alchemist — with
    a save before what it gates; every die is the engine's (`visibility: hidden`), as an
    assay's danger is."""
    from . import consumables

    out = []
    for mid, name, spec in effects:
        why = (f"{name.lower()} flares at the bench" if kind == "mishap"
               else f"{name.lower()}, handled bare")
        doc = {k: v for k, v in spec.items() if k not in ("recipient", "note")}
        made = [dict(i, visibility="hidden")
                for i in consumables.splash_intents([doc], actor_ref, 1.0, why)]
        out.append((mid, name, made))
    return out


def apply_rule(engine, actor, effects, *, kind: str) -> list:
    """Run the mishap or toxic intents through the engine (`validate`, then `run`), stamped
    `rule:<kind>:<material>`. Returns the outcomes; a document the engine cannot stand up
    does nothing this time and never crashes the step."""
    from .engine import IntentError

    out = []
    for mid, name, made in rule_intents(effects, kind=kind, actor_ref=actor.ref):
        if not made:
            continue
        try:
            res = engine.run(engine.validate(made, origin=f"rule:{kind}:{mid}",
                                             origin_name=name))
        except IntentError:
            continue
        out.extend(res.outcomes)
    return out


def failure_losses(plan: AlchemyPlan, miss: int) -> list[tuple[Item, int]]:
    """What a failed roll ruins (plan §7.1, the forge's rule kept): miss by 4 or less and
    only the time is lost; by 5 or more half of what was on the bench is ruined, rounded
    down, at least one whenever there were two. Shared out by each input's share, largest
    remainders first, the cheaper thing first on a tie. Catalysts and apparatus are never
    spent, so never ruined."""
    if miss < 5:
        return []
    total = sum(int(n) for _, n in plan.consumes)
    ruin = total // 2
    if ruin <= 0:
        return []
    shares = []
    for i, (it, n) in enumerate(plan.consumes):
        exact = n * ruin / total
        shares.append([it, int(exact), exact - int(exact), n,
                       (1 if it.record else 0, it.rank, i)])
    left = ruin - sum(s[1] for s in shares)
    for s in sorted(shares, key=lambda s: (-round(s[2], 9), s[4])):
        if left <= 0:
            break
        if s[1] < s[3]:
            s[1] += 1
            left -= 1
    return [(it, k) for it, k, _, _, _ in shares if k > 0]


def spend(actor, consumes: list[tuple[Item, int]]) -> list[dict]:
    """Take what a step used: raw material from the satchel's counts, stock off the
    shelf, by the key the shelf was read under."""
    out = []
    for it, n in consumes:
        if n <= 0:
            continue
        if it.key.startswith("stock:"):
            took = actor.take_stock(it.key.split(":", 1)[1], n)
        else:
            took = actor.spend(it.material, n)
        if took:
            out.append({"key": it.key, "name": it.name, "count": int(took)})
    return out


# =============================================================================================
# Finishing: the records, the shelf, In progress
# =============================================================================================

def make(plan: AlchemyPlan, tier: int, *, extra: int = 0, now: int = 0) -> list[dict]:
    """The records a finished step writes, at the tier the player's hands earned, each with
    its `count` (contracts §6: ids and grades; the build is computed on read). `extra` is
    the Yield perk's one more, rolled and shown by the caller."""
    tier = max(0, min(int(tier), int(plan.ceiling)))
    level, perks = plan.level, {k: v for k, v in plan.perks.items() if v}
    mats = list(plan.pool.get("materials") or ())
    if plan.method == "transmute":
        rec = items.new_record(family="transmute", quality_index=tier, level=level,
                               perks=perks, materials=[plan.inputs[0][0].material],
                               made_minute=now, count=plan.units)
        rec["makes"] = plan.target
        rec["name"] = items.product_name(rec)
        rec["id"] = items._slug(rec["name"])
        return [rec]
    if plan.method == "bottle":
        rec = items.new_record(family=plan.family, traits=plan.choice["traits"],
                               drawbacks=plan.choice["drawbacks"],
                               formula=(plan.formula or {}).get("id"),
                               vessel=plan.vessel.material, quality_index=tier, level=level,
                               perks=perks, concentration=plan.concentration,
                               filtered=plan.filtered, worked=plan.worked, materials=mats,
                               made_minute=now, count=plan.units + int(extra))
        return [rec]
    if plan.method == "filter":
        out = [items.new_record(family=items.INTERMEDIATE, form="filtrate",
                                traits=plan.choice["traits"], drawbacks=[],
                                quality_index=tier, level=level, perks=perks,
                                concentration=plan.concentration, filtered=plan.filtered,
                                worked=plan.worked, materials=mats, made_minute=now,
                                count=plan.units)]
        stripped = list(plan.pool.get("drawbacks") or ())
        if stripped:
            # What the cloth held back (plan §7: "the precipitate, a salt, lands on the
            # shelf too"): the drawbacks, as a salt that carries them and nothing else.
            out.append(items.new_record(family=items.INTERMEDIATE, form="precipitate",
                                        traits=[], drawbacks=stripped, quality_index=tier,
                                        level=level, perks=perks, worked=plan.worked,
                                        materials=mats, made_minute=now, count=plan.units))
        return out
    drawbacks = [] if plan.method == "filter" else plan.choice["drawbacks"]
    return [items.new_record(family=items.INTERMEDIATE, form=plan.form,
                             traits=plan.choice["traits"], drawbacks=drawbacks,
                             quality_index=tier, level=level, perks=perks,
                             concentration=plan.concentration, filtered=plan.filtered,
                             worked=plan.worked, materials=mats, made_minute=now,
                             count=plan.units)]


def waits_for(plan: AlchemyPlan, rec: dict) -> int:
    """How long this record waits In progress (plan §12.3): a spell potion its Brew Potion
    time at the caster level it was made at; a Transmute a day a unit; any step longer
    than the threshold its own minutes. 0 when it is ready at once."""
    from . import formulae

    if plan.method == "bottle" and plan.formula is not None \
            and plan.formula.get("kind") == "spell":
        b = items.build(rec)
        return formulae.brew_minutes(float(b["price_gp"] or 0) * int(rec.get("count") or 1))
    return int(plan.waits or 0)


def land(actor, plan: AlchemyPlan, made: list[dict], *, now: int,
         where: dict | None = None) -> list[dict]:
    """Put what a step made on the shelf; work that waits goes In progress
    (rules/inprogress.py, the one store). Returns [{key, record, waits, ready_at}]."""
    from . import inprogress

    where = where or {}
    lab = where.get("lab")
    out = []
    for rec in made:
        n = int(rec.get("count") or 1)
        waits = waits_for(plan, rec) if plan.method in ("bottle", "transmute") or plan.waits \
            else 0
        if waits:
            # Its own entry, never stacked into a ready one: the whole entry goes into the
            # section (inprogress.begin), and a stack that was half ready is not a thing.
            st = items.to_stock(rec, n)
            key = st.id
            while key in (actor.stock or {}):
                key += "+"
            actor.stock[key] = st
            doing = {"bottle": "setting", "transmute": "transmuting"}.get(plan.method,
                                                                          "working")
            label = (f"{rec['name']} setting" if plan.method == "bottle"
                     else rec["name"] if plan.method == "transmute"
                     else f"{rec['name']}: {plan.method}")
            place = f"place:{lab['place']}" if lab and lab.get("place") else "carried"
            got = inprogress.begin(actor, key, craft=TRACK_ID, minutes=int(waits), now=now,
                                   label=label, where=place,
                                   where_name=str((lab or {}).get("name") or ""),
                                   doing=doing)
            out.append({"key": key, "record": rec, "waits": int(waits),
                        "ready_at": got.get("ready_at")})
        else:
            key = items.put(actor, rec, n)
            out.append({"key": key, "record": rec, "waits": 0, "ready_at": None})
    return out


# --- In progress (rules/inprogress.py) ---------------------------------------------------------

def _collect(item, actor) -> dict:
    """Collecting alchemy work: a set potion or a long step is already the thing it will
    be, so nothing is done but the section's lift; a Transmute's output goes into the
    satchel and the work's entry leaves the shelf."""
    rec = getattr(item, "record", None) or {}
    if rec.get("family") != "transmute":
        return {"said": f"You take the {item.name} off the bench."}
    mid = str(rec.get("makes") or "")
    n = int(rec.get("count") or item.count or 1)
    doc = _shelf_doc(mid) or {}
    actor.inventory[mid] = int((actor.inventory or {}).get(mid, 0) or 0) + n
    for k, v in list((actor.stock or {}).items()):
        if v is item:
            del actor.stock[k]
    name = str(doc.get("name") or mid)
    return {"said": f"The Great Work is done: {n} {name}.",
            "product": {"key": f"inv:{mid}", "name": name, "count": n}}


def _register() -> None:
    from . import inprogress

    inprogress.register(TRACK_ID, collect=_collect, icon="alchemy",
                        stop_words="")


_register()


# =============================================================================================
# Transmute (plan §9)
# =============================================================================================

def transmute_candidates(material_id: str, level: int) -> list[dict]:
    """What a material can become (plan §9): the same kind, exactly one band rarer, at
    least one essence shared, within the level's reach. Derived from the shelf, so a
    world's own reagents get transmutes for free. The player picks; it is never a roll."""
    from . import materials

    doc = _shelf_doc(material_id)
    if doc is None:
        return []
    kind = str(doc.get("kind") or "")
    rank = wc.tier_rank(str(doc.get("tier") or "common"))
    mine = materials.product_essences(doc)
    top = rarity_ceiling(level)
    out = []
    for mid, other in sorted(materials.alchemy_shelf().items()):
        if mid == material_id or str(other.get("kind") or "") != kind:
            continue
        r = wc.tier_rank(str(other.get("tier") or "common"))
        if r != rank + 1 or r > top:
            continue
        shared = sorted(mine & materials.product_essences(other))
        if shared:
            out.append({"id": mid, "name": str(other.get("name") or mid),
                        "tier": str(other.get("tier") or "common"), "shares": shared})
    return out


def transmute_refusal(a: str, b: str) -> str:
    """Why A cannot become B, in words, or "" when it can (at the top level, so only the
    shape of the pair is judged)."""
    from . import materials

    da, db = _shelf_doc(a), _shelf_doc(b)
    if da is None or db is None:
        return "There is no such material."
    if str(da.get("kind")) != str(db.get("kind")):
        return (f"{da.get('name')} is {items._a(str(da.get('kind')))}, "
                f"{db.get('name')} {items._a(str(db.get('kind')))}: a material becomes one "
                f"of its own kind.")
    ra, rb = wc.tier_rank(str(da.get("tier"))), wc.tier_rank(str(db.get("tier")))
    if rb != ra + 1:
        return (f"{db.get('name')} is {db.get('tier')} and {da.get('name')} "
                f"{da.get('tier')}: a transmutation goes exactly one band rarer.")
    if not materials.product_essences(da) & materials.product_essences(db):
        return f"{da.get('name')} and {db.get('name')} share no essence."
    return ""


# =============================================================================================
# Assay (plan §13.2)
# =============================================================================================

def assay_source(actor, material_id: str, now: int = 0) -> Item | None:
    """What a pinch for assaying would come from: a unit already opened first (two assays
    never leave two part-units), else a whole one."""
    mid = str(material_id or "").strip().lower()
    cands = [it for it in shelf(actor, now) if it.material == mid and not it.old]
    opened = [it for it in cands if it.cut]
    whole = [it for it in cands if it.count > 0 and not it.cut]
    return (opened or whole or [None])[0]


def take_pinch(actor, it: Item, tenths: int = 1) -> dict:
    """Take tenths of a unit for an assay. A whole unit from the satchel becomes an opened
    one on the shelf the first time; ten tenths taken and it is gone."""
    tenths = max(1, int(tenths))
    if it.cut and it.stock is not None:
        st = it.stock
        st.record["cut"] = int(st.record.get("cut") or 0) + tenths
        while int(st.record.get("cut") or 0) >= 10:
            st.record["cut"] = int(st.record["cut"]) - 10
            sid = it.key.split(":", 1)[1]
            actor.take_stock(sid, 1)
            if (actor.stock or {}).get(sid) is None:
                break
        return {"key": it.key, "name": it.name, "tenths": tenths}
    if it.key.startswith("inv:"):
        actor.spend(it.material, 1)
    else:
        actor.take_stock(it.key.split(":", 1)[1], 1)
    if tenths >= 10:
        return {"key": it.key, "name": it.name, "tenths": tenths}
    rec = {"family": "raw", "material": it.material, "cut": tenths, "name": it.name,
           "schema": 0}
    st = items.AlchemyStock(base=it.name, count=1, craft=TRACK_ID, kind="raw",
                            tier=it.tier, record=rec)
    key = f"opened-{it.material}"
    while key in (actor.stock or {}):
        key += "+"
    actor.stock[key] = st
    return {"key": f"stock:{key}", "name": it.name, "tenths": tenths}


def assay_dangers(it: Item, total: int, dc: int, *, protected_by: str) -> list:
    """What an assay does to the alchemist (contracts §4): a failed assay by 5 or more on
    a volatile reagent applies its mishap; an unprotected assay of a toxic reagent applies
    its toxic document, whatever the roll. (material, name, spec, kind) each."""
    out = []
    doc = it.doc or {}
    if it.has("volatile") and doc.get("mishap") and int(total) <= int(dc) - 5:
        out.append((it.material, it.name, dict(doc["mishap"]), "mishap"))
    if it.has("toxic_to_handle") and doc.get("toxic") and not protected_by:
        out.append((it.material, it.name, dict(doc["toxic"]), "toxic"))
    return out


# =============================================================================================
# Knowledge at the bench (plan §13)
# =============================================================================================

def keys_for(material_id: str, trait_key_: str) -> list[str]:
    """The knowledge keys a trait of this material is stored under (the property keys of
    `knowledge`, "p0".., a herb's gate with its body), so making a product teaches exactly
    the traits the product carries (Skyrim's rule, plan §13.1)."""
    from . import knowledge, materials

    doc = items.doc_of(material_id)
    if doc is None:
        return []
    keys = knowledge.property_keys(doc)
    product = [s for s in (doc.get("product") or []) if isinstance(s, dict)]
    out = []
    folded = materials.is_herb_view(doc)
    gate_of = {}
    if folded:
        try:
            gate_of = knowledge.anatomy(doc)["gate_of"]
        except Exception:  # noqa: BLE001
            gate_of = {}
    for k, spec in zip(keys, product):
        key = items.trait_key(spec)
        if folded and k in gate_of:
            gate = dict(zip(keys, product)).get(gate_of[k]) or {}
            body = {x: v for x, v in spec.items() if x not in ("route", "essence", "grade")}
            key = items.trait_key({"type": "save_gate", "target": gate.get("target"),
                                   "on_failure": [body],
                                   "route": spec.get("route") or gate.get("route")})
            if key == trait_key_:
                out += [k, gate_of[k]]
                continue
        if key == trait_key_:
            out.append(k)
    return out


def working_keys(material_id: str) -> list[str]:
    from . import knowledge

    doc = items.doc_of(material_id)
    if doc is None:
        return []
    return [k for k in knowledge.property_keys(doc) if str(k).startswith("t")]


def reveal(actor, material_id: str, keys, how: str) -> list[str]:
    from . import knowledge

    return list(knowledge.reveal(actor, material_id, list(keys), how) or [])


def known_starting(actor, *, clock: int = 0) -> list[str]:
    """The four classics every alchemist knows from the start (owner Q5.4), taught the
    first time the bench is opened. The homeland reagents are the herb rule's, taught where
    the herbalist's are (plan §13.4)."""
    from . import formulae

    try:
        return formulae.grant_starting(actor, clock=clock)
    except Exception:  # noqa: BLE001 - a formula table that cannot load teaches nothing
        return []


# =============================================================================================
# The shelf library (the acquisition hub and the old /craft/ page's shelf)
# =============================================================================================

@dataclass
class Material:
    """One thing on the alchemist's shelf, as the acquisition hub and the old /craft/ page
    read it: the document through the one door, its acquisition fields flat."""
    id: str
    name: str
    kind: str = "reagent"
    tier: str = "common"
    craft_dc: int | None = None
    text: str = ""
    risky: bool = False
    volatile: bool = False
    obtain: str = ""
    market: str = ""
    price_gp: float | None = None
    biomes: list[str] = field(default_factory=list)
    from_creatures: list[str] = field(default_factory=list)
    obtain_dc: int | None = None
    product: list = field(default_factory=list)
    working: list = field(default_factory=list)

    @property
    def rank(self) -> int:
        return wc.tier_rank(self.tier)

    @property
    def glyph(self) -> str:
        return KIND_GLYPH.get(self.kind, "🜂")

    @property
    def obtain_how(self) -> str:
        return self.obtain

    @property
    def lines(self) -> list[str]:
        from . import effectspec

        return [effectspec.render(s) for s in self.product]

    def as_dict(self) -> dict:
        return {
            "id": self.id, "name": self.name, "kind": self.kind, "tier": self.tier,
            "rank": self.rank, "craft_dc": self.craft_dc, "text": self.text,
            "risky": self.risky, "volatile": self.volatile, "glyph": self.glyph,
            "obtain": self.obtain, "market": self.market, "price_gp": self.price_gp,
            "biomes": self.biomes, "from_creatures": self.from_creatures,
            "obtain_dc": self.obtain_dc, "product": self.product, "lines": self.lines,
        }


def _price_or_none(value) -> float | None:
    """A price in gp, kept fractional: water is 0.01 (1 cp), and `int()` made it 0 (found
    by the pricing lane, 2026-10-05). Whole prices stay ints."""
    try:
        got = float(value)
    except (TypeError, ValueError):
        return None
    return int(got) if got.is_integer() else got


def _int_or_none(value) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def from_dict(d: dict) -> Material:
    """A shelf document (normalised, `materials.alchemy_shelf`) as a `Material`."""
    raw = d.get("obtain")
    nested = raw if isinstance(raw, dict) else {}
    how = str(nested.get("how") if nested else (raw or ""))
    creatures = (d.get("from_creatures") or nested.get("from_creatures")
                 or ([d["from_creature"]] if d.get("from_creature") else []))
    return Material(
        id=d["id"], name=d.get("name", d["id"]), kind=d.get("kind", "reagent"),
        tier=d.get("tier", "common"), craft_dc=_int_or_none(d.get("craft_dc")),
        text=d.get("text", ""), risky=bool(d.get("risky")),
        volatile="volatile" in _working(d),
        obtain=how, market=str(d.get("market") or nested.get("market") or ""),
        price_gp=_price_or_none(d.get("price_gp", nested.get("price_gp"))),
        biomes=[str(b) for b in (d.get("biomes") or nested.get("biomes") or [])],
        from_creatures=[str(c) for c in creatures],
        obtain_dc=_int_or_none(d.get("obtain_dc", nested.get("dc"))),
        product=list(d.get("product") or []), working=list(d.get("working") or []))


def materials() -> dict[str, Material]:
    """Every material the acquisition hub can turn up for the alchemist, read through the
    one door (lane A): every catalogue in content/materials, shelf-wide as the private
    loader was (a market sells what it sells whichever bench wanted it), plus every hybrid
    herb from `materials.alchemy_shelf` — which the private loader never saw, so the
    harvest excursion lost the basilisk eye when the gland row merged into the herb.
    Retired entries are left off. Not cached here: the door caches, and a second cache
    would be the stale copy CLAUDE.md warns of."""
    from . import materials as door

    docs = {mid: d for mid, d in door.all().items() if not d.get("retired")}
    docs.update(door.alchemy_shelf())
    return {mid: from_dict(d) for mid, d in docs.items()}


def get(material_id: str) -> Material:
    m = materials().get((material_id or "").strip().lower())
    if m is None:
        raise KeyError(f"no material {material_id!r}")
    return m


# --- acquisition (the gathering-parity lane rebuilds these; left as they were) ---------------

ACQUISITION: dict[str, dict] = {
    "market-run": {
        "id": "market-run",
        "label": "Buy reagents",
        "obtain": "bought",
        "needs": "market",
        "markets": ["market", "apothecary", "glassblower", "smith", "temple",
                    "planar broker"],
        "blurb": "An apothecary sells brimstone and lamp oil; a planar broker sells "
                 "azoth and asks no questions. Price is in gp on each material.",
    },
    "quarry": {
        "id": "quarry",
        "label": "Mine salts and ores",
        "obtain": "mined",
        "needs": "biome",
        "blurb": "Vitriol out of a cave wall, brimstone from a fumarole, star-iron from "
                 "a crater. Needs the right ground under you and a check against the "
                 "material's DC.",
    },
    "field-gathering": {
        "id": "field-gathering",
        "label": "Gather field reagents",
        "obtain": "gathered",
        "needs": "biome",
        "blurb": "Pitch from a pine, natron from a dry lakebed, ghost salt from a crypt "
                 "cistern. The alchemist's answer to foraging, and the reason this "
                 "track has no forage panel of its own.",
    },
    "harvest-reagents": {
        "id": "harvest-reagents",
        "label": "Harvest reagents from a kill",
        "obtain": "harvested",
        "needs": "creature",
        "blurb": "The gland, sac or humour comes off something that was alive, and the "
                 "creature has to have been in the scene. An ankheg acid sac should come "
                 "from an ankheg the table actually killed.",
    },
}


def obtainable(obtain_kind: str, *, biome: str = None,
               creature: str = None) -> list[Material]:
    """Every material one excursion could turn up, filtered by where the party is.
    Shelf-wide, and only materials that DECLARE an `obtain` (silence is "not stated",
    never "buy it anywhere"). Creature matching is substring-and-case-insensitive both
    ways ("the ankheg" against "ankheg")."""
    want = str(obtain_kind or "").strip().lower()
    said = str(creature or "").strip().lower()
    out: list[Material] = []
    for m in materials().values():
        if m.obtain_how != want:
            continue
        if biome and m.biomes and biome not in m.biomes:
            continue
        if said and m.from_creatures:
            if not any(c.lower() in said or said in c.lower() for c in m.from_creatures):
                continue
        elif said and not m.from_creatures:
            continue
        out.append(m)
    return sorted(out, key=lambda m: (m.rank, m.name))


# --- the old chain, retired --------------------------------------------------------------------

MOVED_WORDS = ("Alchemy is worked at the bench at the table now, one step at a time: "
               "dissolve, react, bottle. The chain bench no longer takes it.")


@dataclass
class Chain:
    methods: list = field(default_factory=list)
    material_ids: list = field(default_factory=list)
    name: str = ""
    stock_used: dict = field(default_factory=dict)


def chain_from_body(body: dict) -> Chain:
    """The old chain's reader, kept so `benches.supports` stays honest; `benches.MOVED`
    refuses the alchemist's chains before this is reached."""
    body = body or {}
    return Chain(methods=list(body.get("methods") or []),
                 material_ids=list(body.get("materials") or []),
                 name=str(body.get("name") or ""))


def preview(level: int, chain: Chain, **_kw):
    raise CraftError(MOVED_WORDS)


__all__ = ["ACQUISITION", "AlchemyPlan", "CraftError", "Item", "KIND_GLYPH", "METHODS",
           "METHOD_GLYPH", "Material", "TRACK_ID", "apply_rule", "assay_dangers",
           "assay_source", "bench_rules", "check_bonus", "check_odds", "check_terms",
           "failure_losses", "find", "fit_reason", "fits_for", "from_dict", "get",
           "keys_for", "land", "liquid_for", "make", "materials", "method_level",
           "method_row", "methods_view", "obtainable", "plan_step", "rent_cp", "shelf",
           "spend", "stakes", "take_pinch", "transmute_candidates", "transmute_refusal",
           "tuning_for", "where_here", "working_keys"]
