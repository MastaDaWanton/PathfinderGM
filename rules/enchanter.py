"""Enchanting: the circle's rules (docs/enchanting-revamp-plan.md §4, §5, §10, §14;
docs/enchanting-contracts.md §6, lane E), and the old shelf library kept beside them.

**The step bench** (most of this file). The herb bench's and the forge's shape, for the
third craft: one method at a time, each its own d20 check, then an always-played minigame
whose 0..1 score the server turns into a quality tier under the enchanter's ceiling. The
enchanter does not make a new item: the work is **a layer on top of a vessel** the smith or
the leatherworker made (`rules/magic_layer.py`, lane B), and the ritual is three real steps
on that vessel, each leaving it in a state the shelf shows:

  Prepare  lay a circle round the vessel (chalk or salt, ink, a focus for a ring or an
           amulet, a treatment): the vessel is PREPARED, at the circle's quality.
  Attune   seat essences on it, one per seat, choices made (bane's foe): ATTUNED for a
           day. Nothing is spent: the seated phials are held back from the shelf, and when
           the day runs out the attunement lapses and they are simply on the shelf again
           ("the essences drift back unharmed", plan §10) with nothing to write.
  Bind     the book's creation check, DC through `magic_layer.plan`. Success or a miss by
           5+ (FLAWED, a hidden curse, owner round 1) spends the essences and puts the
           vessel In progress for the book's working days (`rules/inprogress.py`); the
           layer is written at Collect. A miss by 1-4 does not take and keeps everything.

Refine, Unbind and Cleanse are steps of the same shape; Read and Identify are single rolls
with no game (tasting and assay have none).

**The owner's rulings that bind it** (docs/enchanting-answers.md):
- Enchanter level is the caster level; each prerequisite spell neither known nor carried in
  a potion or scroll is +5 DC, and so is an Enchanter level below the item's caster level:
  never a refusal (round 1, round 4 point 4). Alignment clauses are waived (point 7).
- Capacity floor(level / 2), at least +1, + quality steps above Superior + Capacity perks,
  no ceiling (rounds 4 and 7; `magic_layer.capacity`). Enhancement still stops at +5.
- Countdowns on the calendar and no limit to how many bindings are in progress (point 5).
- The favourable time is the essence family's phase of the day: Bind's windows ×1.5 inside
  it, and Wait for it moves the clock there through `Scene.advance` (point 10).
- 1 mote = 100 gp; affinity -1 DC a matching seat, at most -2; residue a quarter on
  Unbind; attuned vessels hold a day (point 9). Every one of these is a row in the track's
  `bench` block, so they tune without a code change.
- Mastery: every successful step pays, through `worldclass.award_step` (owner 2026-10-05,
  "batch of 10 should pay 10"); `MISHAP_LIMIT` still caps what failing teaches.

**Which tier gates the binder's level: the essence's, never the property's** (lane D left
this to lane E, docs/enchanting-review.md open row 2). The level bands are the cross-craft
ruling on MATERIAL rarity ("L1 common/uncommon, L2 rare/exotic, L3 legendary"), and the
essence is the material the enchanter handles. Its tier is a price band the price rule can
hold (lane D measured the alternative failing it: ghost touch exotic at 3,000 gp under a
rare 9,000 gp arcane essence). Lane A's property tiers are the table's authored words and
are not price-banded, so gating on them would let a cheap essence demand Enchanter 3
(speed, "legendary", from a 15,000 gp exotic phial) and two essences granting one property
disagree about who may bind it. A recipe's tier (also a price band, `materials.PRICE_BANDS`)
gates as well, and an item's own price band gates Unbind (plan §13).

**No feedback loop** (plan §4.5, Skyrim's Fortify loop in docs/enchanting-prior-art.md §5.6):
the check reads Enchanter level, half the character level and the Intelligence the
character has without any `ability_mod` effect, so a headband of vast intelligence an
enchanter made never makes the next one easier. **No naturals**: a skill check (CRB p.180),
as at the herb and forge benches.

**Lane F (curses, identify, unbind's knowledge)** merged into build/enchanting after this
lane branched. Its API (contracts §7, as F built it: `curses.roll/describe/lift/lift_dc/
clings`, `knowledge.read/apply_danger/attuned/bound/identify/unbind/item_card/
knows_recipe/learn_recipe`) is called through `_lane_fn` with F's own signatures wherever
it exists; the "lane F seam" section's stubs answer only on a tree without it, marked
`"stub": True`. A stub's flawed binding records `{"d100", "cl", "pending"}`; F's records
the book's row. Neither reaches the page while the curse is unknown.

**The old shelf library** (the bottom of the file): `Material`, `materials()`, `get`,
`KIND_GLYPH`, `ACQUISITION` and `obtainable` still serve the `/craft/` page's shelf and the
acquisition hub (rules/benches.py). The old chain (`Chain`, `preview`) cannot run on the new
track (its scribe, seal, imbue and empower are gone), so `rules/benches.MOVED` refuses it in
words, as it does herbalism's, and the stubs here only keep `benches.supports` honest.
"""
from __future__ import annotations

import copy
import importlib
import json
import math
from dataclasses import dataclass, field
from pathlib import Path

from . import effectspec
from . import worldclass as wc

TRACK_ID = "enchanter"


def _lane(name: str):
    """A sibling lane's module, or None while it is not merged. Imported on each call, so a
    test can stand a fake in `sys.modules` (the forge's `_lane`)."""
    try:
        return importlib.import_module(f"rules.{name}")
    except ImportError:
        return None


def _lane_fn(module: str, fn: str):
    mod = _lane(module)
    got = getattr(mod, fn, None) if mod is not None else None
    return got if callable(got) else None


# =============================================================================================
# The track's rule rows
# =============================================================================================

def track() -> wc.Track:
    return wc.get(TRACK_ID)


def bench_rules() -> dict:
    """The `bench` block of content/world-classes/enchanter.json, through the track cache
    (a homebrew track overrides its rules too)."""
    return dict(track().data.get("bench") or {})


def method_row(method: str) -> dict | None:
    return (bench_rules().get("methods") or {}).get(str(method or "").strip().lower())


def methods_order() -> tuple[str, ...]:
    return tuple(bench_rules().get("order") or ())


def method_level(method: str) -> int:
    t = track()
    for row in sorted(t.levels, key=lambda r: r.level):
        if method in row.methods:
            return row.level
    return 99


def _n(key: str, default):
    v = bench_rules().get(key, default)
    return type(default)(v) if v is not None else default


def level_band(level: int) -> int:
    """The rarest essence rank this level may handle (L1 uncommon, L2 exotic, L3 legendary)."""
    return wc.tier_rank(track().at(max(1, int(level))).max_tier)


def level_for_rank(rank: int) -> int | None:
    for row in sorted(track().levels, key=lambda r: r.level):
        if wc.tier_rank(row.max_tier) >= int(rank):
            return row.level
    return None


def _band_refusal(name: str, tier: str, level: int) -> str:
    need = level_for_rank(wc.tier_rank(tier))
    return (f"{name} is {tier}: that is Enchanter {need} work, and you are Enchanter {level}."
            if need else f"{name} is {tier}, beyond every Enchanter level.")


# =============================================================================================
# The check
# =============================================================================================

def _base_int(actor) -> int:
    """Intelligence as the character has it with no `ability_mod` effect counted: damage,
    drain and a condition's penalty, never an item's or a buff's bonus (plan §4.5)."""
    if actor is None:
        return 10
    score = int((getattr(actor, "abilities", None) or {}).get("int", 10) or 10)
    for c in getattr(actor, "conditions", None) or ():
        data = getattr(c, "data", None) or {}
        score += int((data.get("ability_penalty") or {}).get("int", 0) or 0)
    score -= int((getattr(actor, "ability_damage", None) or {}).get("int", 0) or 0)
    score -= int((getattr(actor, "ability_drain", None) or {}).get("int", 0) or 0)
    return max(0, score)


def check_terms(actor, level: int) -> list[dict]:
    """d20 + Enchanter level + half character level + Intelligence, itemised (plan §4.3).
    The Intelligence term is the character's own (`_base_int`): nothing worn reaches it."""
    track_level = max(0, int(level or 0))
    char_level = max(1, int(getattr(actor, "level", 1) or 1)) if actor is not None else 1
    intel = (_base_int(actor) - 10) // 2
    from . import tradecraft

    return [
        {"label": f"Enchanter {track_level}", "value": track_level},
        {"label": f"half character level ({char_level})", "value": char_level // 2},
        {"label": "Intelligence", "value": intel},
        # Half the Craft ranks (option A, 2026-10-07; `tradecraft.bench_terms`). Ranks
        # are the character's own count, so the no-feedback rule above still holds.
        *tradecraft.bench_terms(actor, "enchanter"),
    ]


def check_bonus(actor, level: int) -> int:
    return sum(t["value"] for t in check_terms(actor, level))


def check_odds(dc: int, bonus: int) -> tuple[int | None, str]:
    """The face needed, or None and why none will do. No naturals (CRB p.180)."""
    from . import crafting

    return crafting.check_odds(dc, bonus)


# =============================================================================================
# Where you enchant (plan §14)
# =============================================================================================

def sanctum_here(scene, actor, known=()) -> dict | None:
    """A sanctum you stand in, or None: a place whose kind is `sanctum` (rules/places.py
    derives `place.sanctum` from the kind, never from its name) that the character holds
    (`holds.place.<slug>`, the found door's effect). Read from the scene, never the words."""
    if scene is None:
        return None
    places = _lane("places")
    if places is None or not hasattr(places, "_place_at"):
        return None
    try:
        place = places._place_at(scene, known)
    except Exception:  # noqa: BLE001 - a place we cannot read is no sanctum
        return None
    if place is None or not places.has_place_tag(place, bench_rules().get("sanctum_tag",
                                                                            "place.sanctum")):
        return None
    slug = str(place.id).rsplit("/", 1)[-1]
    if actor is None or not actor.has_state(f"holds.place.{slug}"):
        # Somebody else's sanctum is not yours to work in; a hired circle (rent, as the
        # forge's town smithy) waits on a keeper whose trade is enchanting (plan §14).
        return None
    return {"kind": "owned", "place": place.id, "name": str(getattr(place, "name", "") or "")}


def where_here(scene, actor, known=()) -> dict:
    """{"fight": bool, "sanctum": dict | None, "quiet": bool, "label": str}. Anywhere out of a
    fight is quiet enough for the ritual (the book: "any place suitable for preparing
    spells"); a sanctum adds Refine, Cleanse and legendary essence (plan §14, proposed)."""
    fight = bool(getattr(scene, "in_encounter", False)) if scene is not None else False
    sanctum = sanctum_here(scene, actor, known)
    if fight:
        label = "In a fight: the circle waits until it is over"
    elif sanctum:
        label = "In your sanctum"
    else:
        label = "Anywhere quiet: a circle on the ground"
    return {"fight": fight, "sanctum": sanctum, "quiet": not fight, "label": label}


def methods_view(level: int, where: dict | None = None) -> list[dict]:
    """The method strip (UI plan §6.1): every method in craft order, its lock in words."""
    where = where or {"fight": False, "sanctum": None, "quiet": True}
    out = []
    for mid in methods_order():
        row = method_row(mid) or {}
        need = method_level(mid)
        reason = ""
        if need > int(level):
            reason = f"Enchanter {need}"
        elif where.get("fight"):
            reason = "Not in a fight"
        elif row.get("where") == "sanctum" and not where.get("sanctum"):
            reason = "Needs a sanctum"
        out.append({"id": mid, "name": row.get("name", mid.title()), "level": need,
                    "where": row.get("where", "quiet"), "locked": bool(reason),
                    "lock_reason": reason, "takes": row.get("takes", ""),
                    "makes": row.get("makes", ""),
                    "minigame": bool(row.get("tuning"))})
    return out


# =============================================================================================
# The shelf: phials, circle materials, vessels
# =============================================================================================

PHIAL_TAG = "enchant."            # tags on a stock-kept phial (refined, opened, residue)


def _tags(st) -> dict[str, str]:
    out = {}
    for t in getattr(st, "properties", None) or ():
        t = str(t)
        if t.startswith(PHIAL_TAG):
            head, _, val = t[len(PHIAL_TAG):].partition(".")
            out[head] = val
    return out


def is_phial_stock(st) -> bool:
    return str(getattr(st, "craft", "") or "") == TRACK_ID and _tags(st).get("form") == "phial"


def _essence_docs() -> dict[str, dict]:
    from . import materials

    try:
        return materials.essences()
    except Exception:  # noqa: BLE001 - a broken homebrew shelf is no reason to lose the bench
        return {}


@dataclass
class Phial:
    """One essence on the shelf: an inventory phial (`inv:<id>`, the document's motes) or a
    stock-kept one (`stock:<key>`: refined, opened by a Read, or Unbind's residue), whose
    motes and tenths ride in its `enchant.*` tags."""
    key: str
    id: str
    name: str
    tier: str
    family: str
    phase: str
    polarity: str
    motes: int
    grants: dict | None
    affinity: list
    traits: list
    color: str
    count: int
    tenths: int = 10
    stocked: bool = False

    @property
    def rank(self) -> int:
        return wc.tier_rank(self.tier)

    @property
    def amount(self) -> float:
        return round(self.count - 1 + self.tenths / 10, 1) if self.tenths < 10 else self.count

    def has(self, trait: str) -> bool:
        return trait in self.traits

    def as_item(self, actor=None) -> dict:
        return {"key": self.key, "id": self.id, "name": self.name, "tier": self.tier,
                "rank": self.rank, "family": self.family, "phase": self.phase,
                "polarity": self.polarity, "motes": self.motes, "count": self.count,
                "amount": self.amount, "color": self.color, "group": "Essences",
                "grants": _grant_words(self.grants), "traits": list(self.traits),
                "unknown": _unknown_traits(actor, self.id) if actor is not None else 0,
                "refined": self.stocked}


def _grant_words(grants: dict | None) -> str:
    if not grants:
        return "motes only"
    if "enhancement" in grants:
        return f"+{int(grants['enhancement'])} enhancement"
    if grants.get("property"):
        prop = effectspec.property(str(grants["property"])) or {}
        name = str(prop.get("name") or grants["property"])
        if grants.get("bonus"):
            name += f" +{grants['bonus']}"
        choice = grants.get("choice") or {}
        if choice:
            name += " (" + ", ".join(str(v) for v in choice.values()) + ")"
        return name
    if grants.get("power"):
        from . import materials

        r = materials.recipe(str(grants["power"])) or {}
        return str(r.get("name") or grants["power"])
    return "motes only"


def _phial_from_doc(key: str, doc: dict, count: int, *, motes: int | None = None,
                    tenths: int = 10, stocked: bool = False, name: str | None = None) -> Phial:
    return Phial(key=key, id=doc["id"], name=name or doc["name"], tier=doc["tier"],
                 family=doc.get("family") or "", phase=doc.get("phase") or "",
                 polarity=doc.get("polarity") or "any",
                 motes=int(doc.get("motes") or 0) if motes is None else int(motes),
                 grants=copy.deepcopy(doc.get("grants")),
                 affinity=list(doc.get("affinity") or ()),
                 traits=[str(w.get("trait")) for w in doc.get("working") or () if w.get("trait")],
                 color=str(doc.get("color") or "#c9b98a"), count=int(count), tenths=tenths,
                 stocked=stocked)


def _family_affinity(family: str) -> list[str]:
    from . import materials

    try:
        return list((materials.families().get(family) or {}).get("affinity") or ())
    except Exception:  # noqa: BLE001
        return []


def phials(actor, reserved: dict | None = None) -> list[Phial]:
    """Every essence the character carries, less what an attuned vessel holds back."""
    reserved = reserved or {}
    docs = _essence_docs()
    out: list[Phial] = []
    if actor is None:
        return out
    for iid, n in sorted((getattr(actor, "inventory", {}) or {}).items()):
        doc = docs.get(str(iid))
        if doc is None or int(n or 0) <= 0:
            continue
        key = f"inv:{iid}"
        left = int(n) - int(reserved.get(key, 0))
        if left > 0:
            out.append(_phial_from_doc(key, doc, left))
    for sid, st in sorted((getattr(actor, "stock", {}) or {}).items()):
        if not is_phial_stock(st):
            continue
        key = f"stock:{sid}"
        left = int(getattr(st, "count", 1) or 0) - int(reserved.get(key, 0))
        if left <= 0:
            continue
        t = _tags(st)
        eid = t.get("essence", "")
        doc = docs.get(eid)
        tenths = int(t.get("tenths", 10) or 10)
        full = int(t.get("motes", 0) or 0)
        motes = full * tenths // 10
        if doc is None:
            # Residue, or an essence the shelf no longer knows: motes only.
            fam = t.get("family", "arcane")
            doc = {"id": eid or "arcane-residue", "name": str(st.base), "tier":
                   _tier_of_motes(full), "family": fam, "phase": _family_phase(fam),
                   "polarity": "any", "grants": None, "affinity": _family_affinity(fam),
                   "working": [], "color": "#9c8fd0"}
        out.append(_phial_from_doc(key, doc, left, motes=motes, tenths=tenths, stocked=True,
                                   name=str(st.base)))
    return out


def _tier_of_motes(motes: int) -> str:
    from . import materials

    return materials.essence_tier(motes)


def _family_phase(family: str) -> str:
    from . import materials

    try:
        return str((materials.families().get(family) or {}).get("phase") or "night")
    except Exception:  # noqa: BLE001
        return "night"


# The kinds of circle material (plan §7.3), as the old shelf names them.
CIRCLE_KINDS = ("chalk", "salt", "ink", "treatment", "catalyst", "focus")
_GROUPS = {"chalk": "Circle", "salt": "Circle", "ink": "Circle", "treatment": "Circle",
           "catalyst": "Catalysts", "focus": "Gems"}


@dataclass
class CircleItem:
    key: str
    id: str
    name: str
    kind: str
    tier: str
    count: int
    dc_mod: int = 0
    lifts: str = ""
    fragile: bool = False

    @property
    def rank(self) -> int:
        return wc.tier_rank(self.tier)

    def as_item(self) -> dict:
        return {"key": self.key, "id": self.id, "name": self.name, "kind": self.kind,
                "group": _GROUPS.get(self.kind, "Circle"), "tier": self.tier,
                "rank": self.rank, "count": self.count, "dc_mod": self.dc_mod,
                "lifts": self.lifts, "fragile": self.fragile}


def circle_items(actor) -> list[CircleItem]:
    out = []
    mats = materials()
    for iid, n in sorted((getattr(actor, "inventory", {}) or {}).items()):
        m = mats.get(str(iid))
        if m is None or m.kind not in CIRCLE_KINDS or int(n or 0) <= 0:
            continue
        out.append(CircleItem(key=f"inv:{m.id}", id=m.id, name=m.name, kind=m.kind,
                              tier=m.tier, count=int(n), dc_mod=int(m.dc_mod or 0),
                              lifts=m.lifts, fragile=bool(m.fragile)))
    return out


# Old vessel blanks (retired as materials by lane D, plan §7.3) that are still how a ring,
# an amulet or a cloak reaches the circle until the forge makes jewellery (plan §20's
# cross-craft ask): a carried blank becomes a wondrous vessel record at Prepare.
BLANKS = {
    "ring-vessel": {"name": "Ring", "slot": "ring", "gear": "ring"},
    "amulet-vessel": {"name": "Amulet", "slot": "neck", "gear": "wondrous"},
    "masterwork-cloak-vessel": {"name": "Cloak", "slot": "shoulders", "gear": "wondrous"},
}


def _item_record(key: str, st) -> dict | None:
    """The vessel record behind a shelf entry: a forged record (with its layer), or one made
    for a crafted wearable (a leatherworker's cloak, an enchanter's ring blank)."""
    from . import forge_items

    if is_phial_stock(st):
        return None
    rec = forge_items.record_of(st)
    if rec is not None:
        rec = copy.deepcopy(rec)
        rec.setdefault("id", key)
        return rec
    slot = str(getattr(st, "slot", "") or "")
    if not (getattr(st, "wearable", False) or getattr(st, "weapon", None)
            or getattr(st, "armour", None)) or not (slot or getattr(st, "weapon", None)):
        return None
    mw = bool(getattr(st, "masterwork", False))
    rec = {"id": str(getattr(st, "id", key)), "name": str(st.name), "kind": "crafted",
           "craft": str(getattr(st, "craft", "") or ""), "slot": slot or None,
           "masterwork": mw, "quality_index": 3 if mw else 1,
           "weapon": getattr(st, "weapon", None), "armour": getattr(st, "armour", None)}
    if slot == "ring":
        rec["gear"] = "ring"
    magic = getattr(st, "magic", None)
    if isinstance(magic, dict) and magic:
        rec["magic"] = copy.deepcopy(magic)
    return rec


def _magic_of_stock(st) -> dict:
    rec = getattr(st, "record", None)
    if isinstance(rec, dict) and "pieces" in rec:
        got = rec.get("magic")
    else:
        got = getattr(st, "magic", None)
    return copy.deepcopy(got) if isinstance(got, dict) else {}


def _store_magic(st, magic: dict | None) -> None:
    """Put a magic block back where this kind of entry keeps it: a forged record's own
    `magic`, else the Stock's `magic` field (lane G's, contracts §8.1)."""
    clean = copy.deepcopy(magic) if magic else None
    rec = getattr(st, "record", None)
    if isinstance(rec, dict) and "pieces" in rec:
        if clean:
            rec["magic"] = clean
        else:
            rec.pop("magic", None)
        return
    st.magic = clean


def _rename(st, name: str) -> None:
    st.base = name
    rec = getattr(st, "record", None)
    if isinstance(rec, dict) and "pieces" in rec:
        rec["name"] = name


@dataclass
class Vessel:
    key: str
    name: str
    record: dict
    gear: str
    quality_index: int
    state: str               # plain | prepared | attuned | magic
    why_not: str = ""
    blank: str = ""          # an inventory blank id, made a record at Prepare
    count: int = 1

    def as_item(self, actor=None, now: int = 0) -> dict:
        from . import magic_layer

        cap = magic_layer.capacity(self.record, binder_level=_level_of(actor),
                                   binder_perks=_perks_of(actor))
        m = magic_layer.magic_of(self.record)
        circle = m.get("circle") or {}
        known = m.get("known") or {}
        badges = []
        if self.state in ("prepared", "attuned"):
            badges.append(self.state)
        if magic_layer.has_layer(self.record):
            if not known.get("intent", True):
                badges.append("unidentified")
            if known.get("flawed") or (m.get("curse") and known.get("curse")):
                badges.append("flawed")
        out = {"key": self.key, "name": self.name, "gear": self.gear, "group": "Vessels",
               "quality_index": self.quality_index,
               "quality_name": wc.quality_name(self.quality_index),
               "state": self.state, "badges": badges, "count": self.count,
               "holds": _holds_view(cap), "why_not": self.why_not,
               "seats": [dict(s) for s in seats_for(self.gear)],
               "base": self.record.get("base") or self.record.get("weapon")
               or self.record.get("armour") or "",
               "pieces": copy.deepcopy(self.record.get("pieces") or {}),
               "slot": self.record.get("slot")}
        if circle.get("prepared"):
            p = circle["prepared"]
            out["prepared"] = {"quality": int(p.get("quality", 0)),
                               "quality_name": wc.quality_name(int(p.get("quality", 0))),
                               "holds_up_to": wc.TIERS[min(len(wc.TIERS), int(
                                   p.get("holds_rank", 2))) - 1]}
        att = circle.get("attuned")
        if att and attuned_live(att, now):
            out["attuned"] = {"quality": int(att.get("quality", 0)),
                              "quality_name": wc.quality_name(int(att.get("quality", 0))),
                              "seats": {s: {"key": v.get("key"), "name": v.get("name")}
                                        for s, v in (att.get("seats") or {}).items()},
                              "until": int(att.get("until", 0)),
                              "left_words": _span(int(att.get("until", 0)) - int(now))}
        if magic_layer.has_layer(self.record):
            out["card"] = item_card(self.record)
        return out


def _span(minutes: int) -> str:
    from . import sky

    return sky.span_words(max(0, int(minutes)))


def _holds_view(cap: dict) -> dict:
    """The holds pips (UI plan §6.5), every number the server's: ten pips for the book's
    old +10 frame and a notch at the capacity, which may be past ten now (owner, round 4)."""
    bonus, used = int(cap.get("bonus", 0)), int(cap.get("used", 0))
    pips = max(10, bonus, used)
    return {"bonus": bonus, "used": used, "left": bonus - used, "why": cap.get("why", ""),
            "masterwork": bool(cap.get("masterwork", True)),
            "pips": [{"filled": i < used, "inside": i < bonus} for i in range(pips)],
            "words": f"+{used} of +{bonus}"}


def _level_of(actor) -> int:
    if actor is None:
        return 1
    try:
        return int(actor.track(TRACK_ID).level)
    except Exception:  # noqa: BLE001
        return 1


def _perks_of(actor) -> dict:
    if actor is None:
        return {}
    try:
        return dict(actor.track(TRACK_ID).perks or {})
    except Exception:  # noqa: BLE001
        return {}


def attuned_live(att: dict | None, now: int) -> bool:
    return bool(att) and int(att.get("until", 0) or 0) > int(now)


def _worn_names(actor) -> set[str]:
    names = {str(w).strip().lower() for line in (getattr(actor, "slots", None) or {}).values()
             for w in (line or ()) if w}
    eq = str(getattr(actor, "equipped", "") or "").strip().lower()
    if eq:
        names.add(eq)
    return names


def vessels(actor, now: int = 0) -> list[Vessel]:
    """Everything that can take (or carries) a layer, from the pack only (UI plan §6.2):
    forged arms and armour, crafted wearables, enchanted items, and the old ring, amulet and
    cloak blanks. Work In progress is not here: it sits in its own section."""
    from . import inprogress, magic_layer

    out: list[Vessel] = []
    if actor is None:
        return out
    worn = _worn_names(actor)
    for sid, st in (getattr(actor, "stock", {}) or {}).items():
        if inprogress.work_of(st, now) is not None:
            continue
        rec = _item_record(f"stock:{sid}", st)
        if rec is None:
            continue
        gear = magic_layer.vessel_kind(rec)
        q = magic_layer.quality_index(rec)
        m = magic_layer.magic_of(rec)
        circle = m.get("circle") or {}
        if attuned_live(circle.get("attuned"), now):
            state = "attuned"
        elif circle.get("prepared"):
            state = "prepared"
        elif magic_layer.has_layer(rec):
            state = "magic"
        else:
            state = "plain"
        why = ""
        if gear in magic_layer.ARMS and not (rec.get("masterwork") or q >= magic_layer.SUPERIOR):
            why = (f"{wc.quality_name(q)} work is not masterwork: arms magic needs a Superior "
                   f"vessel")
        names = {str(rec.get("id") or "").lower(), str(rec.get("name") or "").lower(),
                 str(sid).lower(), str(getattr(st, "name", "")).lower()}
        if names & worn:
            why = why or "You are wearing or holding it: take it off first"
        out.append(Vessel(key=f"stock:{sid}", name=str(rec.get("name") or st.name),
                          record=rec, gear=gear, quality_index=q, state=state, why_not=why,
                          count=int(getattr(st, "count", 1) or 1)))
    for iid, n in sorted((getattr(actor, "inventory", {}) or {}).items()):
        spec = BLANKS.get(str(iid))
        if spec is None or int(n or 0) <= 0:
            continue
        rec = _blank_record(str(iid))
        out.append(Vessel(key=f"inv:{iid}", name=spec["name"], record=rec,
                          gear=magic_layer.vessel_kind(rec), quality_index=3, state="plain",
                          blank=str(iid), count=int(n)))
    out.sort(key=lambda v: (v.state not in ("attuned", "prepared"), v.name.lower()))
    return out


def _blank_record(blank_id: str) -> dict:
    spec = BLANKS[blank_id]
    rec = {"id": f"{spec['name'].lower()}-blank", "name": spec["name"], "kind": "crafted",
           "craft": TRACK_ID, "slot": spec["slot"], "masterwork": True, "quality_index": 3}
    if spec["gear"] == "ring":
        rec["gear"] = "ring"
    return rec


def _make_blank(actor, blank_id: str) -> str:
    """Turn one carried blank into a shelf vessel; returns its stock key."""
    from .crafting import Stock

    spec = BLANKS[blank_id]
    actor.spend(blank_id, 1)
    n = 1
    while f"enchant-{blank_id}-{n}" in actor.stock:
        n += 1
    key = f"enchant-{blank_id}-{n}"
    actor.stock[key] = Stock(base=spec["name"], count=1, craft=TRACK_ID, kind="crafted",
                             slot=spec["slot"], wearable=True, masterwork=True,
                             tier="common")
    return key


def shelf(actor, now: int = 0) -> dict:
    """The shelf as the page draws it (UI plan §6.2): only what is carried, grouped."""
    res = reserved(actor, now)
    vs = vessels(actor, now)
    ok = [v.as_item(actor, now) for v in vs if not v.why_not]
    bad = [v.as_item(actor, now) for v in vs if v.why_not]
    circle = [c.as_item() for c in circle_items(actor)]
    return {
        "vessels": [v for v in ok if v["state"] in ("plain", "magic")],
        "intermediates": [v for v in ok if v["state"] in ("prepared", "attuned")],
        "essences": [p.as_item(actor) for p in phials(actor, res)],
        "circle": [c for c in circle if c["group"] == "Circle"],
        "gems": [c for c in circle if c["group"] == "Gems"],
        "catalysts": [c for c in circle if c["group"] == "Catalysts"],
        "cant_use": bad,
    }


def reserved(actor, now: int, *, except_key: str | None = None) -> dict[str, int]:
    """Phials held back by every live attunement (except one vessel's own, at its Bind)."""
    out: dict[str, int] = {}
    for sid, st in (getattr(actor, "stock", {}) or {}).items():
        if f"stock:{sid}" == except_key:
            continue
        att = (_magic_of_stock(st).get("circle") or {}).get("attuned")
        if not attuned_live(att, now):
            continue
        for seat in (att.get("seats") or {}).values():
            k = str(seat.get("key") or "")
            if k:
                out[k] = out.get(k, 0) + 1
    return out


def find_vessel(actor, key: str, now: int) -> Vessel | None:
    return next((v for v in vessels(actor, now) if v.key == str(key or "")), None)


def seats_for(gear: str) -> list[dict]:
    seats = bench_rules().get("seats") or {}
    return [dict(s) for s in seats.get(gear) or seats.get("wondrous") or ()]


def polarities_for(gear: str) -> list[str]:
    pol = bench_rules().get("polarity") or {}
    return list(pol.get(gear) or ("any",))


# =============================================================================================
# Item knowledge and the card (UI plan §6.6)
# =============================================================================================

def item_card(record: dict) -> dict:
    """The item card's magic section (UI plan §6.6): lane F's `knowledge.item_card` (what
    may be shown and what may not: aura and schools before identify, the intent after, the
    curse's words only once known), with the bench's two additions when the intent is
    known: the binding's house top-ups at their quality, and each power's uses left today.
    Without F, the bench's own card (`_own_card`), held to the same rule."""
    mine = _own_card(record)
    fn = _lane_fn("knowledge", "item_card")
    if fn is None:
        card = mine
    else:
        card = dict(fn(record) or {})
        if card.get("identified"):
            card["house"] = mine.get("house", [])
            card["uses"] = mine.get("powers", [])
        else:
            card.setdefault("summary", mine.get("summary"))
    # An item converted from an old save that never named a choice (bane's foe) asks it
    # here, on its own card, for as long as it is unanswered (plan §19, lane H): the
    # one-time notice can be dismissed, the question cannot be lost.
    asks = pending_of(record)
    if asks:
        card["questions"] = asks
    return card


def _own_card(record: dict) -> dict:
    """The bench's card: every number the layer builder's, as the owner believes it
    (`believed=True`, so a curse never reaches it), "not identified" where the intent is
    not known, the curse named only once it is known."""
    from . import magic_layer

    m = magic_layer.magic_of(record)
    known = m.get("known") or {}
    lay = magic_layer.layer(record, believed=True)
    intent = bool(known.get("intent", True))
    out = {"aura": lay.get("aura"), "caster_level": lay.get("caster_level"),
           "identified": intent, "lines": [], "powers": [], "house": [],
           "enhancement": lay.get("enhancement", 0), "total_bonus": lay.get("total_bonus"),
           "flawed": bool(m.get("curse") and known.get("curse")), "curse": ""}
    if not intent:
        out["summary"] = f"Magic, {lay.get('aura') or 'faint'} aura"
        return out
    if lay.get("enhancement"):
        out["lines"].append(f"+{lay['enhancement']} enhancement")
    for e in m.get("properties", []) + m.get("flat", []):
        prop = effectspec.property(str(e.get("id") or ""))
        if prop is None:
            continue
        for line in effectspec.property_lines(prop, e.get("choice")):
            out["lines"].append(f"{prop['name']}: {line}")
    for p in m.get("powers", []):
        r = magic_layer.recipe(str(p.get("recipe") or "")) or {}
        out["powers"].append(str(r.get("name") or p.get("recipe")))
    q = int((m.get("binding") or {}).get("quality_index", 0) or 0)
    for d in lay.get("specs", []) + lay.get("riders", []):
        if d.get("house"):
            out["house"].append(f"{effectspec.render(d)} (from the binding, "
                                f"{wc.quality_name(q)})")
    for p in lay.get("powers", []):
        uses = p.get("uses")
        n = p.get("uses_count")
        left = (f", {max(0, int(n) - int(p.get('used', 0)))} of {n} left today"
                if uses == "per_day" and n else "")
        out["powers"].append(effectspec.render(p.get("spec") or {}) + left)
    if m.get("curse") and known.get("curse"):
        out["curse"] = curse_words(m["curse"])
    elif not known.get("curse"):
        # Said of every item whose curse question is open, cursed or not: a card that
        # spoke only of the clean ones would tell the cursed ones apart.
        out["curse_question"] = "not identified for a curse"
    out["flawed"] = bool(known.get("flawed") or out["flawed"])
    return out


# =============================================================================================
# The plan of one step
# =============================================================================================

@dataclass
class StepPlan:
    method: str
    level: int
    ceiling: int = 0
    vessel: Vessel | None = None
    problems: list[str] = field(default_factory=list)
    info: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    dc: int = 0
    dc_terms: list[dict] = field(default_factory=list)
    bonus: int = 0
    terms: list[dict] = field(default_factory=list)
    need: int | None = None
    impossible: str = ""
    minutes: int = 0
    consumes: list[tuple[str, int, str]] = field(default_factory=list)   # (key, n, name)
    rank: int = 1
    lead: dict | None = None
    traits: list[str] = field(default_factory=list)
    phase: str = ""
    seats: dict = field(default_factory=dict)       # seat -> Phial
    choices: dict = field(default_factory=dict)
    recipe: str = ""
    adds: dict = field(default_factory=dict)
    layer_plan: dict | None = None
    hurry: bool = False
    catalyst: CircleItem | None = None
    circle: list[CircleItem] = field(default_factory=list)
    focus: CircleItem | None = None
    potions: list[str] = field(default_factory=list)  # stock keys of potions used up
    refine: list[tuple[Phial, int]] = field(default_factory=list)
    flawed_ok: bool = False                          # a miss by 5+ still takes (Bind)
    work_minutes: int = 0
    days: int = 0
    name_after: str = ""
    lifts: list[str] = field(default_factory=list)

    @property
    def can_roll(self) -> bool:
        return not self.problems and self.need is not None


def _say_list(words: list[str]) -> str:
    words = [w for w in words if w]
    if len(words) <= 1:
        return "".join(words)
    return ", ".join(words[:-1]) + " and " + words[-1]


def _step_dc(rank: int) -> int:
    return int(_n("step_dc_base", 5)) + int(_n("step_dc_per_rank", 5)) * max(1, int(rank))


def _step_dc_terms(rank: int, what: str) -> list[dict]:
    """The step DC's one term, in words that add up to its number.

    The words used to read "5 + 5 for rare essence" beside a DC of 20, which is 5 + 5 × 3:
    the 5 is per step of rarity and rare is the third (the final pass, 2026-10-06, read off
    the working's DC line). The words are built from the same two numbers `_step_dc`
    adds, so a retuned enchanter.json cannot leave them saying something else."""
    rank = max(1, int(rank))
    base, per = int(_n("step_dc_base", 5)), int(_n("step_dc_per_rank", 5))
    tier = wc.TIERS[min(rank, len(wc.TIERS)) - 1]
    steps = f"{per} for {tier} {what}" if rank == 1 else \
        f"{per} × {rank} for {tier} {what} (the {_ORDINAL.get(rank, str(rank))} step of rarity)"
    return [{"why": f"{base} + {steps}", "dc": _step_dc(rank)}]


_ORDINAL = {2: "second", 3: "third", 4: "fourth", 5: "fifth"}


def _choices_for(prop: dict) -> dict | None:
    ch = prop.get("choice")
    if not ch:
        return None
    opts = list(ch.get("options") or ())
    if not opts and ch.get("of") == "skill":
        from .tables import SKILLS

        opts = sorted(SKILLS)
    return {"key": ch.get("key"), "of": ch.get("of"), "options": opts}


def _seat_choice(phial: Phial, said: dict | None) -> tuple[dict | None, list[str]]:
    """The choice a seated essence binds with: its grant's own (Resist Fire Essence binds
    fire), else what the player picked from the engine's list. Bonus for a scaled one."""
    grants = phial.grants or {}
    prop = effectspec.property(str(grants.get("property") or "")) or {}
    choice: dict = {}
    if isinstance(grants.get("choice"), dict):
        choice.update(grants["choice"])
    said = dict(said or {})
    ch = prop.get("choice") or {}
    key = ch.get("key")
    if key and key not in choice and said.get(key) not in (None, ""):
        choice[key] = str(said[key]).strip().lower()
    if prop.get("scaled"):
        values = list((prop.get("scaled") or {}).get("values") or [1])
        bonus = grants.get("bonus")
        if bonus is None:
            raw = said.get("bonus")
            try:
                bonus = int(raw) if raw not in (None, "") else int(values[0])
            except (TypeError, ValueError):
                bonus = int(values[0])
        choice["bonus"] = int(bonus)
    problems = effectspec.choice_problems(prop, choice) if prop else []
    return (choice or None), problems


def adds_from_seats(record: dict, seats: dict, choices: dict, recipe: str = "") -> tuple[dict, list[str]]:
    """What the seated essences bind (plan §6.5): the highest enhancement a seated arcane or
    warding essence grants, each property a seated essence grants that the item does not
    already carry, or a known recipe's power. Duplicates and motes-only phials are motes."""
    from . import magic_layer

    m = magic_layer.magic_of(record)
    gear = magic_layer.vessel_kind(record)
    problems: list[str] = []
    adds: dict = {"enhancement": 0, "properties": [], "powers": []}
    if recipe:
        adds["powers"].append({"recipe": recipe, "essence": _lead_id(seats)})
        return adds, problems
    have = [(e.get("id"), e.get("choice") or None) for e in m["properties"] + m["flat"]]
    top = 0
    for seat, ph in seats.items():
        g = ph.grants or {}
        if "enhancement" in g and gear in magic_layer.ARMS:
            top = max(top, int(g["enhancement"]))
        elif g.get("property"):
            choice, bad = _seat_choice(ph, (choices or {}).get(seat))
            # Said for the essence the player seated, not the property's id: "Bane
            # Essence: choose its foe ...", never "Bane Essence: bane: choose its foe".
            pid = f"{g['property']}: "
            problems.extend(f"{ph.name}: {p[len(pid):] if p.startswith(pid) else p}"
                            for p in bad)
            pair = (str(g["property"]), choice)
            if pair in have:
                continue
            have.append(pair)
            adds["properties"].append({"id": str(g["property"]), "essence": ph.id,
                                       "choice": choice})
    if top > int(m["enhancement"]):
        adds["enhancement"] = top - int(m["enhancement"])
    return adds, problems


def _lead_id(seats: dict) -> str | None:
    if not seats:
        return None
    ph = max(seats.values(), key=lambda p: (bool(p.grants), p.rank, p.motes))
    return ph.id


def _lead(phs: list[Phial]) -> Phial | None:
    if not phs:
        return None
    return max(phs, key=lambda p: (bool(p.grants), p.rank, p.motes))


def _recipe_needs_met(rec_doc: dict, seated: list[Phial]) -> list[str]:
    """A recipe names its essences by what they grant or by family (lane D's `essences`)."""
    pool = list(seated)
    out = []
    for need in rec_doc.get("essences") or ():
        count = max(1, int(need.get("count") or 1))
        for _ in range(count):
            if need.get("grants"):
                g = str(need["grants"])
                hit = next((p for p in pool if (g == "enhancement" and "enhancement" in
                                                (p.grants or {}))
                            or (p.grants or {}).get("property") == g), None)
                what = (effectspec.property(g) or {}).get("name") or g
            else:
                hit = next((p for p in pool if p.family == need.get("family")), None)
                what = f"a {need.get('family')} essence"
            if hit is None:
                out.append(f"{rec_doc.get('name')} needs {what} seated.")
                break
            pool.remove(hit)
    return out


def _spells_held(actor) -> dict[str, str]:
    """{spell id: stock key} for every carried potion or scroll holding a spell."""
    out = {}
    for sid, st in (getattr(actor, "stock", {}) or {}).items():
        sp = str(getattr(st, "holds_spell", "") or "")
        if sp and int(getattr(st, "count", 0) or 0) > 0:
            out.setdefault(sp, sid)
    return out


def _spells_known(actor, ids) -> set[str]:
    out = set()
    try:
        from . import casting, spells as spell_mod
    except ImportError:
        return out
    for sid in ids:
        try:
            if casting.knows(actor, spell_mod.get(sid)):
                out.add(sid)
        except Exception:  # noqa: BLE001 - an unknown id or a non-caster knows nothing
            continue
    return out


def _spell_groups_of(adds: dict) -> list[list[str]]:
    from . import magic_layer

    groups = []
    for e in adds.get("properties") or ():
        prop = effectspec.property(str(e.get("id") or "")) or {}
        groups += [[str(s) for s in g] for g in prop.get("spells") or () if g]
    for p in adds.get("powers") or ():
        r = magic_layer.recipe(str(p.get("recipe") or "")) or {}
        groups += magic_layer._recipe_spell_groups(r)
    return groups


def binder_of(actor, level: int, adds: dict) -> tuple[dict, list[str]]:
    """`magic_layer.plan`'s binder, and the potions it would use up: a spell neither known
    nor carried is +5 DC; one carried in a potion or scroll is satisfied by it, and the
    potion is consumed in the making (the book's "through another magic item")."""
    groups = _spell_groups_of(adds)
    ids = {s for g in groups for s in g}
    knows = _spells_known(actor, ids)
    held = _spells_held(actor)
    holds, potions = set(), []
    for g in groups:
        if set(g) & knows:
            continue
        hit = next((s for s in g if s in held), None)
        if hit:
            holds.add(hit)
            if held[hit] not in potions:
                potions.append(held[hit])
    cls = [str(getattr(actor, "char_class", "") or "")] if actor is not None else []
    binder = {"level": int(level), "perks": _perks_of(actor), "knows": sorted(knows),
              "holds": sorted(holds), "classes": [c for c in cls if c]}
    return binder, potions


def _affinity_helps(record: dict, seats: dict) -> list[dict]:
    """-1 DC for each seat whose essence's family suits the material it sits on, at most -2
    (owner round 4 point 9; Ars Magica's idea of affinity, never its table, plan §6.6)."""
    from . import item_tags

    pieces = record.get("pieces") or {}
    focus = ((record.get("magic") or {}).get("circle") or {}).get("prepared", {}).get("focus")
    per, cap = int(_n("affinity_dc", -1)), int(_n("affinity_max", -2))
    total, why = 0, []
    for seat in seats_for((_vessel_gear(record))):
        ph = seats.get(seat["id"])
        if ph is None:
            continue
        piece = seat.get("piece") or ""
        mat = focus if piece == "focus" else (pieces.get(piece) or {}).get("material")
        if not mat:
            continue
        root = item_tags.root_material(mat) if hasattr(item_tags, "root_material") else mat
        suits = set(ph.affinity) | set(_family_affinity(ph.family))
        if mat in suits or root in suits:
            total += per
            why.append(f"{ph.name} suits the {str(root).replace('-', ' ')}")
    total = max(cap, total)
    return [{"why": f"affinity: {_say_list(why)}", "dc": total}] if total else []


def _vessel_gear(record: dict) -> str:
    from . import magic_layer

    return magic_layer.vessel_kind(record)


def _hour(phase: str, now: int) -> dict | None:
    from . import sky

    if phase not in sky.PHASES:
        return None
    at = sky.phase_at(now)
    inside = at["phase"] == phase
    return {"phase": phase, "now": at["phase"], "inside": inside,
            "minutes_left": at["left"] if inside else 0,
            "minutes_until": 0 if inside else sky.next_phase(phase, now),
            "words": sky.words(now, phase),
            "widen": float(_n("phase_widen", 1.5)) if inside else 1.0}


def _parse_seats(body: dict, shelf_phials: list[Phial], gear: str) -> tuple[dict, list[str]]:
    raw = body.get("seats") or {}
    if not isinstance(raw, dict):
        return {}, ["`seats` must be an object of {seat: essence key}."]
    ids = {s["id"] for s in seats_for(gear)}
    by_key = {p.key: p for p in shelf_phials}
    taken: dict[str, int] = {}
    out, problems = {}, []
    for seat, key in raw.items():
        seat = str(seat).strip().lower()
        if key in (None, ""):
            continue
        if seat not in ids:
            problems.append(f"This vessel has no seat called {seat!r}; its seats are "
                            f"{_say_list(sorted(ids))}.")
            continue
        ph = by_key.get(str(key))
        if ph is None:
            problems.append("An essence on the circle is no longer on your shelf. Lift it "
                            "and look again.")
            continue
        taken[ph.key] = taken.get(ph.key, 0) + 1
        if taken[ph.key] > ph.count:
            problems.append(f"You carry {ph.count} {ph.name} and seated it "
                            f"{taken[ph.key]} times.")
            continue
        out[seat] = ph
    return out, problems


def _circle_pick(body: dict, items: list[CircleItem]) -> tuple[list[CircleItem], list[str]]:
    by_key = {c.key: c for c in items}
    keys = body.get("circle") or []
    if isinstance(keys, str):
        keys = [keys]
    out, problems = [], []
    for k in keys or ():
        c = by_key.get(str(k))
        if c is None:
            problems.append("Something in the circle is no longer in your pack.")
            continue
        out.append(c)
    return out, problems


def plan_step(actor, progress, method: str, body: dict, *, scene=None, known=(),
              now: int = 0) -> StepPlan:
    """Everything about one step before any roll: refusals in words, the DC with its terms,
    the bonus, the face needed, the time, what is spent. Never raises for a bad step."""
    method = str(method or "").strip().lower()
    level = int(getattr(progress, "level", 1) or 1)
    plan = StepPlan(method=method, level=level)
    row = method_row(method)
    if row is None:
        plan.problems.append(f"There is no enchanting method called {method!r}.")
        return plan
    plan.minutes = int(row.get("minutes", 0) or 0)
    plan.ceiling = wc.ceiling_index(progress) if progress is not None else 2
    plan.terms = check_terms(actor, level)
    plan.bonus = sum(t["value"] for t in plan.terms)
    need_level = method_level(method)
    if need_level > level:
        plan.problems.append(f"{row.get('name', method.title())} is learned at Enchanter "
                             f"{need_level}.")
    where = where_here(scene, actor, known)
    if where["fight"]:
        plan.problems.append("You are in a fight. The circle waits until it is over.")
    if row.get("where") == "sanctum" and not where["sanctum"]:
        plan.problems.append(f"{row.get('name')} needs a sanctum: a place of your own, "
                             f"founded as one.")
    body = dict(body or {})
    build = _BUILD.get(method)
    if build is not None:
        build(plan, actor, body, where, now)
    if plan.dc:
        plan.need, plan.impossible = check_odds(plan.dc, plan.bonus)
    return plan


def _need_vessel(plan: StepPlan, actor, body, now, *, states: tuple) -> Vessel | None:
    key = str(body.get("vessel") or "")
    if not key:
        plan.problems.append("Put a vessel in the circle first.")
        return None
    v = find_vessel(actor, key, now)
    if v is None:
        from . import inprogress

        k = key.split(":", 1)[-1]
        st = (getattr(actor, "stock", {}) or {}).get(k)
        if st is not None and inprogress.work_of(st, now) is not None:
            plan.problems.append(f"{st.name} is {inprogress.held_back(st, now)}.")
        else:
            plan.problems.append("That vessel is no longer in your pack.")
        return None
    plan.vessel = v
    if v.why_not:
        plan.problems.append(v.why_not + ".")
    if v.state not in states:
        plan.problems.append(_STATE_REFUSAL.get((plan.method, v.state),
                                                f"{v.name} is {v.state}."))
    return v


_STATE_REFUSAL = {
    ("prepare", "prepared"): "This vessel is already prepared: attune it next.",
    ("prepare", "attuned"): "This vessel is attuned: bind it, or let the day run out.",
    ("attune", "plain"): "Prepare the vessel first: an essence has no circle to sit in.",
    ("attune", "magic"): "Prepare the vessel first: an essence has no circle to sit in.",
    ("attune", "attuned"): "This vessel is attuned already: bind it, or let the day run out.",
    ("bind", "plain"): "Prepare and attune the vessel first.",
    ("bind", "magic"): "Prepare and attune the vessel first.",
    ("bind", "prepared"): "Attune the vessel first: no essence is seated.",
    ("unbind", "plain"): "There is no magic on it to unbind.",
    ("unbind", "attuned"): "It is attuned: bind it or let the day run out before you unbind.",
    ("cleanse", "plain"): "There is no magic on it, and no curse.",
}


def _build_prepare(plan: StepPlan, actor, body, where, now) -> None:
    v = _need_vessel(plan, actor, body, now, states=("plain", "magic"))
    items = circle_items(actor)
    picked, bad = _circle_pick(body, items)
    plan.problems += bad
    fk = str(body.get("focus") or "")
    focus = next((c for c in items if c.key == fk and c.kind == "focus"), None) if fk else None
    if fk and focus is None:
        plan.problems.append("That focus is no longer in your pack.")
    lines = [c for c in picked if c.kind in ("chalk", "salt")]
    inks = [c for c in picked if c.kind == "ink"]
    treat = [c for c in picked if c.kind == "treatment"]
    other = [c for c in picked if c.kind not in ("chalk", "salt", "ink", "treatment")]
    if not lines:
        plan.problems.append("Lay the circle: put chalk or salt in it.")
    if not inks:
        plan.problems.append("Cut the sigils: put an ink in the circle.")
    if len(lines) > 1 or len(inks) > 1 or len(treat) > 1:
        plan.problems.append("One chalk or salt, one ink and at most one treatment make a "
                             "circle.")
    if other:
        plan.problems.append(f"{_say_list([c.name for c in other])} is no circle material "
                             f"(a catalyst goes in at Bind, a gem as the focus).")
    if v is not None:
        slot = str(v.record.get("slot") or "")
        jewel = v.gear == "ring" or slot == "neck"
        if jewel and focus is None:
            plan.problems.append(f"A {('ring' if v.gear == 'ring' else 'amulet')} takes a "
                                 f"focus: set a gem in it.")
        if focus is not None and not jewel:
            plan.problems.append("Only a ring or an amulet takes a focus.")
    used = lines[:1] + inks[:1] + treat[:1] + ([focus] if focus else [])
    for c in used:
        if c.rank > level_band(plan.level):
            plan.problems.append(_band_refusal(c.name, c.tier, plan.level))
    plan.circle = used
    plan.focus = focus
    plan.rank = max((c.rank for c in used), default=1)
    plan.dc = _step_dc(plan.rank)
    plan.dc_terms = _step_dc_terms(plan.rank, "circle material")
    plan.consumes = [(c.key, 1, c.name) for c in used]
    plan.lifts = [c.lifts for c in treat if c.lifts]
    plan.lead = {"id": (lines[0].id if lines else ""), "name": (lines[0].name if lines else ""),
                 "rank": plan.rank}
    if v is not None:
        holds = min(len(wc.TIERS), (lines[0].rank if lines else 1) + 1)
        plan.info.append(f"A {lines[0].name.lower() if lines else 'chalk'} circle holds "
                         f"essence up to {wc.TIERS[holds - 1]}.")
        plan.name_after = v.name


def _build_attune(plan: StepPlan, actor, body, where, now) -> None:
    from . import magic_layer

    v = _need_vessel(plan, actor, body, now, states=("prepared",))
    if v is None:
        return
    res = reserved(actor, now, except_key=v.key)
    shelf_ph = phials(actor, res)
    seats, bad = _parse_seats(body, shelf_ph, v.gear)
    plan.problems += bad
    plan.seats = seats
    choices = body.get("choices") or {}
    plan.choices = {str(k): dict(val) for k, val in choices.items()
                    if isinstance(val, dict)} if isinstance(choices, dict) else {}
    plan.recipe = str(body.get("recipe") or "").strip().lower()
    if not seats:
        plan.problems.append("Seat at least one essence.")
    prep = (magic_layer.magic_of(v.record).get("circle") or {}).get("prepared") or {}
    holds = int(prep.get("holds_rank", 2) or 2)
    pols = polarities_for(v.gear)
    for seat, ph in seats.items():
        if ph.rank > level_band(plan.level):
            plan.problems.append(_band_refusal(ph.name, ph.tier, plan.level))
        if ph.rank > holds:
            plan.problems.append(f"The circle holds nothing rarer than "
                                 f"{wc.TIERS[holds - 1]}; {ph.name} is {ph.tier}.")
        if ph.rank >= int(_n("sanctum_rank", 5)) and not where.get("sanctum"):
            plan.problems.append(f"{ph.name} is legendary: it will only sit in a sanctum's "
                                 f"circle.")
        if ph.polarity not in pols:
            plan.problems.append(f"{ph.name} wants a {ph.polarity}; it will not sit on a "
                                 f"{v.gear}.")
    _plan_working(plan, actor, v, now)
    plan.rank = max((p.rank for p in seats.values()), default=1)
    plan.dc = _step_dc(plan.rank)
    plan.dc_terms = _step_dc_terms(plan.rank, "essence")
    lead = _lead(list(seats.values()))
    if lead is not None:
        plan.lead = {"id": lead.id, "name": lead.name, "rank": lead.rank}
        plan.phase = lead.phase
        plan.traits = sorted({t for p in seats.values() for t in p.traits})


def _plan_working(plan: StepPlan, actor, v: Vessel, now: int, *, hurry: bool = False,
                  helps=()) -> None:
    """The working the seats make (shared by Attune, which refuses one that cannot be
    bound, and Bind, which rolls it): the adds, `magic_layer.plan`, the motes."""
    from . import magic_layer, materials

    seats = plan.seats
    if plan.recipe:
        r = materials.recipe(plan.recipe)
        if r is None:
            plan.problems.append(f"There is no recipe {plan.recipe!r}.")
            return
        if not recipe_known(actor, plan.recipe):
            plan.problems.append(f"You do not know how {r['name']} is made: identify or "
                                 f"unbind one, or learn it from a teacher or a manual.")
        if wc.tier_rank(r.get("tier")) > level_band(plan.level):
            plan.problems.append(_band_refusal(r["name"], r["tier"], plan.level))
        vessel = str(r.get("vessel") or "slotless")
        slot = str(v.record.get("slot") or "")
        if vessel not in ("slotless", slot):
            plan.problems.append(f"{r['name']} is worn on the {vessel}; this vessel is worn "
                                 f"on the {slot or 'body'}.")
        plan.problems += _recipe_needs_met(r, list(seats.values()))
    adds, bad = adds_from_seats(v.record, seats, plan.choices, plan.recipe)
    plan.problems += bad
    plan.adds = adds
    new_props = len(adds.get("properties") or ())
    if new_props > 1 and plan.level < int(_n("multi_property_level", 2)):
        plan.problems.append(f"More than one new property in one working is Enchanter "
                             f"{int(_n('multi_property_level', 2))}: bind them one at a "
                             f"time.")
    if not (adds.get("enhancement") or adds.get("properties") or adds.get("powers")):
        if seats:
            plan.problems.append("Nothing seated grants anything the item does not already "
                                 "carry: seat an essence that grants a property or a "
                                 "higher enhancement.")
        return
    binder, potions = binder_of(actor, plan.level, adds)
    lp = magic_layer.plan(v.record, adds, binder=binder, hurry=hurry, helps=helps)
    plan.layer_plan = lp
    plan.potions = potions
    # The layer's plan asks every new property's choice again (`_entry_problems`), so an
    # unchosen bane foe came up twice in the bench's problems list, once for the essence
    # and once for the property (the final pass, 2026-10-06). A choice problem already said
    # for a seat is not said again.
    said = set()
    for p in plan.problems:
        said.add(p.split(": ", 1)[-1])
    for p in lp.get("problems") or ():
        bare = str(p).split(": ", 1)[-1]
        if "choose its" in bare and bare in said:
            continue
        plan.problems.append(p)
    plan.notes += list(lp.get("notes") or ())
    have = sum(p.motes for p in seats.values())
    need = int(lp["price"]["motes"])
    if have < need:
        parts = [f"{int(lp['price']['motes']) - sum(s['motes'] for s in lp['price']['surcharges'])}"
                 f" for the working"] + [f"{s['motes']} for {s['why'].split(':')[0].lower()}"
                                        for s in lp["price"]["surcharges"]]
        plan.problems.append(f"The working costs {need} motes ({_say_list(parts)}); the "
                             f"seated essences carry {have}.")
    plan.days = int(lp["price"]["days"])
    plan.work_minutes = plan.days * 1440
    plan.name_after = bound_name(v.record, adds)


def _build_bind(plan: StepPlan, actor, body, where, now) -> None:
    from . import magic_layer, sky

    v = _need_vessel(plan, actor, body, now, states=("attuned",))
    if v is None:
        return
    circle = magic_layer.magic_of(v.record).get("circle") or {}
    att = circle.get("attuned") or {}
    prep = circle.get("prepared") or {}
    # The seats as attuned, read back off the shelf (excluding this vessel's own hold).
    shelf_ph = {p.key: p for p in phials(actor, reserved(actor, now, except_key=v.key))}
    seats = {}
    for seat, s in (att.get("seats") or {}).items():
        ph = shelf_ph.get(str(s.get("key") or ""))
        if ph is None:
            plan.problems.append(f"The {s.get('name') or 'essence'} seated at the {seat} is "
                                 f"gone from your pack. Attune the vessel again.")
            continue
        seats[seat] = ph
    plan.seats = seats
    plan.choices = copy.deepcopy(att.get("choices") or {})
    plan.recipe = str(att.get("recipe") or "")
    plan.hurry = bool(body.get("hurry"))
    items = circle_items(actor)
    ck = str(body.get("catalyst") or "")
    cat = next((c for c in items if c.key == ck and c.kind == "catalyst"), None) if ck else None
    if ck and cat is None:
        plan.problems.append("That catalyst is no longer in your pack.")
    if cat is not None and cat.rank > level_band(plan.level):
        plan.problems.append(_band_refusal(cat.name, cat.tier, plan.level))
    plan.catalyst = cat
    helps = list(_affinity_helps(v.record, seats))
    if cat is not None and cat.dc_mod:
        helps.append({"why": f"{cat.name}", "dc": int(cat.dc_mod)})
    for ph in seats.values():
        if ph.rank >= int(_n("sanctum_rank", 5)) and not where.get("sanctum"):
            plan.problems.append(f"{ph.name} is legendary: bind it in a sanctum.")
    # Ghost residue's night (plan §7.3): only between dusk and dawn, unless the vessel was
    # prepared with a treatment that lifts it (moonlit varnish).
    lifted = set(prep.get("lifts") or ())
    night = set(bench_rules().get("night_phases") or ())
    at = sky.phase_at(now)["phase"]
    for ph in seats.values():
        if ph.has("night_only") and "night" not in lifted and at not in night:
            plan.problems.append(f"{ph.name} binds only between dusk and dawn, and it is "
                                 f"{at}. Wait for dusk, or prepare the vessel with a "
                                 f"treatment that lifts it (moonlit varnish).")
    _plan_working(plan, actor, v, now, hurry=plan.hurry, helps=helps)
    lp = plan.layer_plan
    if lp is not None:
        plan.dc = int(lp["dc"])
        plan.dc_terms = list(lp["dc_terms"])
        plan.rank = max((p.rank for p in seats.values()), default=1)
    else:
        plan.dc = 0
    lead = _lead(list(seats.values()))
    if lead is not None:
        plan.lead = {"id": lead.id, "name": lead.name, "rank": lead.rank}
        plan.phase = lead.phase
        plan.traits = sorted({t for p in seats.values() for t in p.traits})
    if cat is not None:
        plan.consumes.append((cat.key, 1, cat.name))
    plan.flawed_ok = True
    lift = int(_n("circle_lift", 1))
    caps = [int(plan.ceiling)]
    if prep:
        caps.append(int(prep.get("quality", 0)) + lift)
    if att:
        caps.append(int(att.get("quality", 0)) + lift)
    plan.ceiling = max(0, min(caps))
    if prep or att:
        plan.info.append(f"Prepared at {wc.quality_name(int(prep.get('quality', 0)))}, "
                         f"attuned at {wc.quality_name(int(att.get('quality', 0)))}: Bind can "
                         f"reach {wc.quality_name(plan.ceiling)}.")
    if plan.days:
        plan.info.append(f"{int(lp['price']['hours'])} hours of work: ready in "
                         f"{plan.days} day{'s' if plan.days != 1 else ''}.")


def _build_refine(plan: StepPlan, actor, body, where, now) -> None:
    raw = body.get("phials") or {}
    if isinstance(raw, list):
        counts: dict[str, int] = {}
        for k in raw:
            counts[str(k)] = counts.get(str(k), 0) + 1
        raw = counts
    if not isinstance(raw, dict):
        plan.problems.append("`phials` must be {key: count}.")
        return
    shelf_ph = {p.key: p for p in phials(actor, reserved(actor, now))}
    picked: list[tuple[Phial, int]] = []
    for k, n in raw.items():
        ph = shelf_ph.get(str(k))
        try:
            n = int(n)
        except (TypeError, ValueError):
            n = 0
        if ph is None or n <= 0:
            plan.problems.append("A phial in the dropper is no longer on your shelf.")
            continue
        if n > ph.count:
            plan.problems.append(f"You carry {ph.count} {ph.name} and asked for {n}.")
            n = ph.count
        picked.append((ph, n))
    total = sum(n for _, n in picked)
    if total < 2:
        plan.problems.append("Refine condenses two or more phials into one.")
    fams = {ph.family for ph, _ in picked}
    if len(fams) > 1:
        plan.problems.append(f"One family at a time: {_say_list(sorted(fams))} will not "
                             f"share a phial.")
    grants = {json.dumps(ph.grants, sort_keys=True) for ph, _ in picked if ph.grants}
    if len(grants) > 1:
        plan.problems.append("Two essences that grant different things cannot share a phial.")
    for ph, _ in picked:
        if ph.rank > level_band(plan.level):
            plan.problems.append(_band_refusal(ph.name, ph.tier, plan.level))
    plan.refine = picked
    lead = _lead([ph for ph, _ in picked])
    plan.rank = max((ph.rank for ph, _ in picked), default=1)
    plan.dc = _step_dc(plan.rank)
    plan.dc_terms = _step_dc_terms(plan.rank, "essence")
    plan.consumes = [(ph.key, n, ph.name) for ph, n in picked]
    if lead is not None:
        plan.lead = {"id": lead.id, "name": lead.name, "rank": lead.rank}
        plan.phase = lead.phase
        plan.traits = sorted({t for ph, _ in picked for t in ph.traits})
        motes = sum(ph.motes * n for ph, n in picked)
        plan.info.append(f"{total} phials, {motes} motes between them: a clean draw keeps "
                         f"them all, a careless one loses up to a fifth.")
        plan.name_after = f"Refined {lead.name}"


def _layer_rank(record: dict) -> int:
    """How rare an item's magic is, for the rarity lock on Unbind (plan §13: "an item whose
    recipe is legendary needs Enchanter 3 to unbind"): the rarest of its recipes' tiers and
    the price band of the whole layer (`materials.PRICE_BANDS`, the band recipes and
    essences are tiered on), so a +5 vorpal sword with no recipe is legendary too."""
    from . import magic_layer, materials

    m = magic_layer.magic_of(record)
    price = magic_layer.market_price(m, magic_layer.vessel_kind(record),
                                     str(record.get("slot") or ""))
    ranks = [wc.tier_rank(materials.tier_for_price(price))]
    for p in m["powers"]:
        r = materials.recipe(str(p.get("recipe") or "")) or {}
        if r.get("tier"):
            ranks.append(wc.tier_rank(r["tier"]))
    return max(ranks)


def _build_unbind(plan: StepPlan, actor, body, where, now) -> None:
    from . import magic_layer

    v = _need_vessel(plan, actor, body, now, states=("magic", "prepared"))
    if v is None:
        return
    if not magic_layer.has_layer(v.record):
        plan.problems.append("There is no magic on it to unbind.")
        return
    m = magic_layer.magic_of(v.record)
    cl = magic_layer.caster_level(m, v.gear)
    plan.rank = _layer_rank(v.record)
    if plan.rank > level_band(plan.level):
        plan.problems.append(_band_refusal(v.name, wc.TIERS[plan.rank - 1], plan.level))
    plan.dc = int(_n("unbind_dc_base", 10)) + cl
    plan.dc_terms = [{"why": f"10 + the item's caster level {cl}", "dc": plan.dc}]
    plan.lead = {"id": str(v.record.get("id") or v.key), "name": v.name, "rank": plan.rank}
    plan.info.append("The layer comes off whole; the item stays the smith's.")
    plan.name_after = str((m.get("binding") or {}).get("vessel_name") or v.name)


def _build_cleanse(plan: StepPlan, actor, body, where, now) -> None:
    from . import magic_layer

    v = _need_vessel(plan, actor, body, now, states=("magic", "prepared"))
    if v is None:
        return
    m = magic_layer.magic_of(v.record)
    if not m.get("curse") or not (m.get("known") or {}).get("curse"):
        plan.problems.append("You know of no curse on it to lift: identify it well first.")
    plan.rank = _layer_rank(v.record)
    plan.dc = cleanse_dc(v.record)
    plan.dc_terms = [{"why": f"remove curse: 10 + the caster level {plan.dc - 10}",
                      "dc": plan.dc}]
    plan.lead = {"id": str(v.record.get("id") or v.key), "name": v.name, "rank": plan.rank}
    plan.name_after = v.name


_BUILD = {"prepare": _build_prepare, "attune": _build_attune, "bind": _build_bind,
          "refine": _build_refine, "unbind": _build_unbind, "cleanse": _build_cleanse}


def fits_for(plan: StepPlan, actor, now: int) -> dict:
    """Why each shelf entry would or would not go into this step, for the shelf's greying
    (the herb bench learned a rule that only speaks after the button is pressed reads as no
    rule). {key: {"ok": bool, "as": slot word, "why": str}}."""
    out: dict[str, dict] = {}
    m = plan.method
    level = plan.level
    for v in vessels(actor, now):
        want = {"prepare": ("plain", "magic"), "attune": ("prepared",), "bind": ("attuned",),
                "unbind": ("magic", "prepared"), "cleanse": ("magic", "prepared")}.get(m)
        if want is None:
            continue
        why = v.why_not or ("" if v.state in want else _STATE_REFUSAL.get(
            (m, v.state), f"It is {v.state}."))
        out[v.key] = {"ok": not why, "as": "vessel", "why": why}
    if m in ("prepare", "bind"):
        for c in circle_items(actor):
            kinds = ("chalk", "salt", "ink", "treatment", "focus") if m == "prepare" \
                else ("catalyst",)
            if c.kind not in kinds:
                why = ("A catalyst goes in at Bind." if c.kind == "catalyst"
                       else "Circle materials go in at Prepare.")
            elif c.rank > level_band(level):
                why = _band_refusal(c.name, c.tier, level)
            else:
                why = ""
            out[c.key] = {"ok": not why, "as": c.kind, "why": why}
    if m in ("attune", "refine"):
        v = plan.vessel
        prep = ((v.record.get("magic") or {}).get("circle") or {}).get("prepared") \
            if v is not None else None
        holds = int((prep or {}).get("holds_rank", 5) or 5)
        pols = polarities_for(v.gear) if v is not None else None
        for p in phials(actor, reserved(actor, now, except_key=v.key if v else None)):
            why = ""
            if p.rank > level_band(level):
                why = _band_refusal(p.name, p.tier, level)
            elif m == "attune" and p.rank > holds:
                why = (f"The circle holds nothing rarer than {wc.TIERS[holds - 1]}; "
                       f"{p.name} is {p.tier}.")
            elif m == "attune" and pols is not None and p.polarity not in pols:
                why = f"{p.name} wants a {p.polarity}; it will not sit on a {v.gear}."
            out[p.key] = {"ok": not why, "as": "seat" if m == "attune" else "phial",
                          "why": why}
    return out


def take_pinch(actor, key: str) -> dict | None:
    """A Read's tenth of a phial (plan §10). An inventory phial is opened: one comes off
    the count as a stock-kept phial at nine tenths, its full motes kept in its tags so the
    tenths say what is left. A stock phial loses a tenth; at none it is gone."""
    from .crafting import Stock

    k = str(key or "")
    docs = _essence_docs()
    if k.startswith("inv:"):
        iid = k[4:]
        doc = docs.get(iid)
        if doc is None or not actor.spend(iid, 1):
            return None
        n = 1
        while f"enchant-opened-{iid}-{n}" in actor.stock:
            n += 1
        sk = f"enchant-opened-{iid}-{n}"
        actor.stock[sk] = Stock(
            base=doc["name"], count=1, craft=TRACK_ID, kind="essence", tier=doc["tier"],
            properties=[f"{PHIAL_TAG}form.phial", f"{PHIAL_TAG}essence.{iid}",
                        f"{PHIAL_TAG}motes.{int(doc.get('motes') or 0)}",
                        f"{PHIAL_TAG}family.{doc.get('family') or ''}",
                        f"{PHIAL_TAG}tenths.9"], how=["ingredient"])
        return {"key": f"stock:{sk}", "left": 0.9}
    st = _stock_of(actor, k)
    if st is None or not is_phial_stock(st):
        return None
    t = _tags(st)
    tenths = int(t.get("tenths", 10) or 10) - 1
    if tenths <= 0:
        actor.take_stock(k[6:] if k.startswith("stock:") else k, 1)
        return {"key": k, "left": 0}
    st.properties = [x for x in st.properties if not str(x).startswith(f"{PHIAL_TAG}tenths.")]
    st.properties.append(f"{PHIAL_TAG}tenths.{tenths}")
    return {"key": k, "left": tenths / 10}


# =============================================================================================
# Names
# =============================================================================================

def bound_name(record: dict, adds: dict) -> str:
    """The item as the book prints it once the working is on: "+1 Flaming Superior Iron
    Longsword", a recipe's own name ("Ring of Protection +1"), or the vessel with its powers
    ("Cloak (Resistance +1)"). Built from the vessel's name before any layer."""
    from . import magic_layer

    m = magic_layer.magic_of(record)
    base = str((m.get("binding") or {}).get("vessel_name") or record.get("name") or "Item")
    after = magic_layer._merge(m, adds)
    for p in after.get("powers") or ():
        r = magic_layer.recipe(str(p.get("recipe") or "")) or {}
        if r.get("name"):
            return str(r["name"])
    words = []
    scaled = []
    for e in after.get("properties", []) + after.get("flat", []):
        prop = effectspec.property(str(e.get("id") or "")) or {}
        name = str(prop.get("name") or e.get("id"))
        bonus = (e.get("choice") or {}).get("bonus")
        if prop.get("scaled"):
            scaled.append(f"{name} +{bonus}" if bonus else name)
        else:
            words.append(name)
    enh = int(after.get("enhancement") or 0)
    gear = magic_layer.vessel_kind(record)
    if gear in magic_layer.ARMS:
        front = (f"+{enh} " if enh else "") + " ".join(dict.fromkeys(words))
        return f"{front.strip()} {base}".strip() if front.strip() else base
    if scaled or words:
        return f"{base} ({', '.join(scaled + list(dict.fromkeys(words)))})"
    return base


# =============================================================================================
# Doing it: spending, the minigame's numbers, the outcomes
# =============================================================================================

def _take(actor, key: str, n: int) -> int:
    k = str(key)
    if k.startswith("inv:"):
        return actor.spend(k[4:], n)
    if k.startswith("stock:"):
        return actor.take_stock(k[6:], n)
    return 0


def spend(actor, consumes) -> list[dict]:
    out = []
    for key, n, name in consumes:
        took = _take(actor, key, n)
        if took:
            out.append({"key": key, "name": name, "count": took})
    return out


def tuning_for(plan: StepPlan, now: int) -> dict:
    """The minigame's numbers (UI plan §9, contracts §13): the base difficulty, harder by
    `rarity_step` a band above common; Bind's windows ×1.5 inside the lead essence's phase
    (owner round 4) and ×1.1 for an eager one; the strip's tier names and bands."""
    rules = bench_rules()
    row = method_row(plan.method) or {}
    tun = row.get("tuning") or {}
    diff = float(tun.get("difficulty", 0.45)) + float(rules.get("rarity_step", 0.05)) \
        * max(0, plan.rank - 1)
    widen = 1.0
    hour = _hour(plan.phase, now) if plan.phase else None
    if plan.method == "bind":
        if hour and hour["inside"]:
            widen *= float(rules.get("phase_widen", 1.5))
        if "eager" in plan.traits:
            widen *= float(rules.get("eager_widen", 1.1))
    ceiling = max(0, int(plan.ceiling))
    out = {"method": plan.method, "game": plan.method, "track": "enchant",
           "difficulty": round(min(0.95, diff), 4), "widen": round(widen, 4),
           "band": tun.get("band", ""), "seconds": tun.get("seconds", 6),
           "traits": list(plan.traits), "hour": hour,
           "names": [wc.quality_name(t) for t in range(ceiling + 1)],
           "bands": [t / (ceiling + 1) for t in range(ceiling + 1)]}
    if plan.method == "prepare":
        out["seq"] = [c.kind for c in plan.circle if c.kind != "focus"] + \
            (["focus"] if plan.focus else []) + ["bell"]
    if plan.method == "attune" and plan.vessel is not None:
        out["seats"] = seat_signs(plan.vessel, plan.seats)
    if plan.method == "unbind" and plan.vessel is not None:
        from . import magic_layer

        m = magic_layer.magic_of(plan.vessel.record)
        out["seq"] = list(reversed(["enhancement"] * int(m["enhancement"] > 0)
                                   + ["sigil"] * len(m["properties"] + m["flat"]
                                                     + m["powers"])))
    if plan.method == "cleanse":
        out["seq"] = ["sigil", "sigil", "sigil"]
    return out


def seat_signs(v: Vessel, seats: dict | None = None) -> list[dict]:
    """Each seat with its sign in words (UI plan §6.5): the polarity the vessel takes and
    the material the seat sits on, which an essence of that material's family suits."""
    pieces = v.record.get("pieces") or {}
    focus = ((v.record.get("magic") or {}).get("circle") or {}).get("prepared", {}).get("focus")
    out = []
    for s in seats_for(v.gear):
        piece = s.get("piece") or ""
        mat = focus if piece == "focus" else (pieces.get(piece) or {}).get("material")
        ph = (seats or {}).get(s["id"])
        out.append({"seat": s["id"], "name": s.get("name", s["id"].title()),
                    "polarity": polarities_for(v.gear),
                    "material": str(mat or "").replace("-", " "),
                    "sign": (f"takes {_say_list(polarities_for(v.gear))} essences"
                             + (f"; suits what loves {str(mat).replace('-', ' ')}"
                                if mat else "")),
                    "seated": ph.key if ph else None,
                    "essence": ph.name if ph else None,
                    "color": ph.color if ph else None,
                    # A seated essence shows its phase (knowledge.py: "an unknown essence's
                    # polarity and phase show when it is seated"; the check's `hour` names
                    # it already). At Bind the essences are held by the vessel and off the
                    # shelf, so the page had no row to read it from and said "Noon favours
                    # this essence" (the final pass, 2026-10-06).
                    "phase": (ph.phase or None) if ph else None})
    return out


def lines_for(plan: StepPlan) -> dict:
    """The two failure lines printed before the roll (plan §4.4, §10.1), in words."""
    m = plan.method
    if m == "bind":
        return {"miss_small": "Miss by 1 to 4: the binding does not take. You keep the "
                              "essences and the vessel stays attuned.",
                "miss_big": "Miss by 5 or more: it takes, flawed, with a hidden curse."}
    if m == "prepare":
        return {"miss_small": "Miss: the circle is spoiled. The chalk and ink are spent; "
                              "the vessel is untouched.",
                "miss_big": "Miss by 5 or more: the same. A spoiled circle is chalk."}
    if m == "attune":
        return {"miss_small": "Miss: the essences will not settle. Nothing is spent.",
                "miss_big": "Miss by 5 or more: the same. Essences are never lost before "
                            "Bind."}
    if m == "refine":
        return {"miss_small": "Miss by 1 to 4: the time is lost, nothing spent.",
                "miss_big": "Miss by 5 or more: half the phials are ruined."}
    if m == "unbind":
        return {"miss_small": "Miss by 1 to 4: the time is lost, the item untouched.",
                "miss_big": "Miss by 5 or more: the layer is lost and nothing is learned."}
    if m == "cleanse":
        return {"miss_small": "Miss: the curse holds. The time is lost.",
                "miss_big": "Miss by 5 or more: the same."}
    return {"miss_small": "", "miss_big": ""}


def verdict_of(plan: StepPlan, margin: int) -> str:
    if margin >= 0:
        return "success"
    if plan.flawed_ok and margin <= -5:
        return "flawed"
    return "failure"


def miss(actor, progress, plan: StepPlan, margin: int, *, now: int) -> dict:
    """A failed step (plan §10.1): what it costs, said, and the lesson's mastery."""
    out_by = -int(margin)
    lost: list[dict] = []
    if plan.method == "prepare":
        lost = spend(actor, plan.consumes)
        said = (f"Missed by {out_by}. The circle is spoiled: "
                f"{_say_list([x['name'] for x in lost]) or 'nothing'} spent; the vessel is "
                f"untouched.")
    elif plan.method == "refine" and out_by >= 5:
        half = []
        for ph, n in plan.refine:
            k = n // 2
            if k:
                half.append((ph.key, k, ph.name))
        lost = spend(actor, half)
        said = (f"Missed by {out_by}. Half the phials are ruined: "
                f"{_say_list([str(x['count']) + ' ' + x['name'] for x in lost]) or 'none'}.")
    elif plan.method == "unbind" and out_by >= 5 and plan.vessel is not None:
        st = _stock_of(actor, plan.vessel.key)
        if st is not None:
            _store_magic(st, None)
            name = str((_magic_of_stock(st).get("binding") or {}).get("vessel_name")
                       or plan.name_after or st.name)
            _rename(st, name)
        said = (f"Missed by {out_by}. The layer tears away and is lost; nothing is learned. "
                f"The item is as the smith made it.")
    elif plan.method == "bind":
        said = (f"Missed by {out_by}. The binding does not take: the essences are kept and "
                f"the vessel stays attuned.")
    else:
        said = f"Missed by {out_by}. The time is lost; nothing is spent."
    track = wc.get(TRACK_ID)
    lead = plan.lead or {}
    got = wc.award_step(track, progress, method=plan.method,
                        ingredient_id=str(lead.get("id") or ""),
                        rarity_rank=int(plan.rank), quality_index=0, success=False,
                        name=str(lead.get("name") or ""))
    return {"said": said, "lost": lost, "mastery": got}


def _stock_of(actor, key: str):
    k = str(key or "")
    if k.startswith("stock:"):
        k = k[6:]
    return (getattr(actor, "stock", {}) or {}).get(k)


def _split_one(actor, key: str) -> str:
    """One of a stack, split off under its own key so a layer or a circle goes on one item
    and not on every identical sword in the pile."""
    k = key[6:] if key.startswith("stock:") else key
    st = actor.stock[k]
    if int(getattr(st, "count", 1) or 1) <= 1:
        return k
    one = copy.deepcopy(st)
    one.count = 1
    st.count = int(st.count) - 1
    rec = getattr(one, "record", None)
    if isinstance(rec, dict):
        rec["count"] = 1
        if isinstance(getattr(st, "record", None), dict):
            st.record["count"] = st.count
    n = 2
    while f"{k}~{n}" in actor.stock:
        n += 1
    actor.stock[f"{k}~{n}"] = one
    return f"{k}~{n}"


def finish(actor, progress, plan: StepPlan, tier: int, *, engine=None, now: int = 0,
           flawed: bool = False) -> dict:
    """Land a step whose roll succeeded (or a Bind that took, flawed): spend, make, pay.

    Returns {"products", "lines", "levelled", "discoveries", "said", "work"}."""
    from . import magic_layer

    track = wc.get(TRACK_ID)
    lines: list[dict] = []
    levelled: list[int] = []
    discoveries: list[dict] = []
    products: list[dict] = []
    day = int(now) // 1440 + 1

    def pay_first(key: str, why: str) -> None:
        seen = int(progress.crafted.get(key, 0))
        progress.crafted[key] = seen + 1
        if seen == 0:
            res = wc.award_bonus(track, progress, why=why, mp=wc.FIRST_MP)
            lines.extend(res.get("reasons") or [])
            levelled.extend(res.get("levelled") or [])

    def learn(essence_id: str, way, name: str) -> None:
        new = way(actor, essence_id, clock=now)
        doc = _essence_docs().get(str(essence_id)) or {}
        for k in new:
            words = trait_words(doc, k)
            discoveries.append({"essence": essence_id, "name": name, "key": k,
                                "text": words})
            res = wc.award_bonus(track, progress, why=f"learned: {name}, {words}",
                                 mp=wc.FIRST_MP)
            lines.extend(res.get("reasons") or [])
            levelled.extend(res.get("levelled") or [])

    said = ""
    work = None
    v = plan.vessel
    if plan.method == "prepare" and v is not None:
        spend(actor, plan.consumes)          # chalk or salt, ink, treatment, the focus set
        key = _make_blank(actor, v.blank) if v.blank else _split_one(actor, v.key)
        st = actor.stock[key]
        m = _magic_of_stock(st)
        line = next((c for c in plan.circle if c.kind in ("chalk", "salt")), None)
        circle = dict(m.get("circle") or {})
        circle.pop("attuned", None)
        circle["prepared"] = {"quality": int(tier), "day": day,
                              "materials": [c.id for c in plan.circle],
                              "holds_rank": min(len(wc.TIERS), (line.rank if line else 1) + 1),
                              "lifts": list(plan.lifts),
                              "focus": plan.focus.id if plan.focus else None,
                              "fragile": bool(plan.focus and plan.focus.fragile)}
        m["circle"] = circle
        _store_magic(st, m)
        said = f"The circle is laid round the {st.name}: prepared, {wc.quality_name(tier)}."
        products.append({"key": f"stock:{key}", "name": st.name, "state": "prepared"})
    elif plan.method == "attune" and v is not None:
        st = _stock_of(actor, v.key)
        m = _magic_of_stock(st)
        circle = dict(m.get("circle") or {})
        circle["attuned"] = {"quality": int(tier),
                             "seats": {s: {"key": p.key, "id": p.id, "name": p.name,
                                           "motes": p.motes}
                                       for s, p in plan.seats.items()},
                             "choices": copy.deepcopy(plan.choices), "recipe": plan.recipe,
                             "until": int(now) + int(_n("attuned_hold_minutes", 1440))}
        m["circle"] = circle
        _store_magic(st, m)
        for p in plan.seats.values():
            learn(p.id, learn_attuned, p.name)
        said = (f"{_say_list([p.name for p in plan.seats.values()])} settle into the "
                f"{st.name}: attuned for a day.")
        products.append({"key": v.key, "name": st.name, "state": "attuned"})
    elif plan.method == "bind" and v is not None:
        work, extra = _land_binding(actor, progress, plan, tier, engine=engine, now=now,
                                    flawed=flawed)
        lines += extra["lines"]
        levelled += extra["levelled"]
        said = extra["said"]
        for p in plan.seats.values():
            if (p.grants or {}).get("property") or "enhancement" in (p.grants or {}):
                learn(p.id, learn_bound, p.name)
        for e in plan.adds.get("properties") or ():
            prop = effectspec.property(str(e["id"])) or {}
            pay_first(f"bound:{e['id']}", f"first {prop.get('name', e['id'])} bound")
        products.append({"key": v.key, "name": plan.name_after, "state": "in_progress",
                         "work": work})
    elif plan.method == "refine":
        spend(actor, plan.consumes)
        key, name, motes = _land_refined(actor, plan, tier)
        said = f"{name}: one phial of {motes} motes."
        products.append({"key": f"stock:{key}", "name": name, "motes": motes})
    elif plan.method == "unbind" and v is not None:
        got = _land_unbind(actor, progress, plan, now=now)
        said = got["said"]
        products += got["products"]
        discoveries += got["discoveries"]
        pay_first(f"unbound:{v.record.get('id') or v.key}", f"first unbinding of {v.name}")
    elif plan.method == "cleanse" and v is not None:
        st = _stock_of(actor, v.key)
        lifted = lift_curse(_item_record(v.key, st) or {})
        _store_magic(st, lifted.get("magic"))
        said = f"The curse is lifted from the {st.name}; the rest of its magic stays."
        products.append({"key": v.key, "name": st.name, "state": "magic"})

    lead = plan.lead or {}
    got = wc.award_step(track, progress, method=plan.method,
                        ingredient_id=str(lead.get("id") or ""), rarity_rank=int(plan.rank),
                        quality_index=int(tier), success=not flawed,
                        name=str(lead.get("name") or ""))
    lines = list(got.get("reasons") or []) + lines
    levelled = list(got.get("levelled") or []) + levelled
    return {"products": products, "lines": lines, "levelled": levelled,
            "discoveries": discoveries, "said": said, "work": work}


def _land_binding(actor, progress, plan: StepPlan, tier: int, *, engine, now: int,
                  flawed: bool) -> tuple[dict, dict]:
    """Spend the essences (one may be spared by the Yield perk, the roll shown), set the
    vessel In progress for the book's days, and keep everything Collect needs in the
    block's craft-owned `result` (never sent to the page)."""
    from . import inprogress, magic_layer

    lines: list[dict] = []
    v = plan.vessel
    seats = dict(plan.seats)
    chance = float(wc.perk_multipliers(progress).get("yield_chance", 0) or 0)
    spared = None
    if chance > 0 and engine is not None and seats:
        roll = engine.dice.roll("1d100", label="Yield perk", visibility="player")
        at = int(round(chance * 100))
        if roll.total <= at:
            spared = max(seats.values(), key=lambda p: p.motes)
        lines.append({"why": f"Yield perk: d100 {roll.total} against {at} or less, "
                             f"{(spared.name + ' kept') if spared else 'nothing kept'}",
                      "mp": 0})
    use: dict[str, int] = {}
    names: dict[str, str] = {}
    for p in seats.values():
        use[p.key] = use.get(p.key, 0) + 1
        names[p.key] = p.name
    if spared is not None:
        use[spared.key] -= 1
    spend(actor, [(k, n, names[k]) for k, n in use.items() if n > 0])
    spend(actor, plan.consumes)                                 # the catalyst
    for sk in plan.potions:
        actor.take_stock(sk, 1)
    st = _stock_of(actor, v.key)
    m = _magic_of_stock(st)
    circle = m.pop("circle", {}) or {}
    prep = circle.get("prepared") or {}
    binding = {"quality_index": int(tier), "level": int(plan.level),
               "perks": {k: int(n) for k, n in _perks_of(actor).items() if n},
               "vessel_name": str((m.get("binding") or {}).get("vessel_name") or v.name)}
    focus = prep.get("focus") or (m.get("binding") or {}).get("focus")
    cracked = False
    curse = None
    if flawed:
        curse = roll_curse(engine, v.record, plan.layer_plan or {}, plan.adds)
        if focus and prep.get("fragile"):
            cracked = True
            focus = None
    if focus:
        binding["focus"] = focus
    _store_magic(st, m or None)
    day = int(now) // 1440 + 1
    name = plan.name_after or v.name
    result = {"adds": copy.deepcopy(plan.adds), "binding": binding, "curse": curse,
              "name": name, "day": day, "flawed": bool(flawed)}
    got = inprogress.begin(actor, v.key, craft=TRACK_ID, minutes=max(1, plan.work_minutes),
                           now=int(now), label=f"Binding {_a(name)}", doing="binding",
                           result=result)
    if flawed:
        said = (f"It took, but something went wrong in the binding. The {name} waits In "
                f"progress, ready in {plan.days} day{'s' if plan.days != 1 else ''}.")
        if cracked:
            said += " The focus cracked through."
    else:
        said = (f"The binding takes. The {name} waits In progress, ready in {plan.days} "
                f"day{'s' if plan.days != 1 else ''}.")
    return got, {"lines": lines, "levelled": [], "said": said}


def _a(name: str) -> str:
    n = str(name)
    if n[:1] in "+0123456789":
        return n
    return ("an " if n[:1].lower() in "aeiou" else "a ") + n


def _land_refined(actor, plan: StepPlan, tier: int) -> tuple[str, str, int]:
    from .crafting import Stock

    yields = list(bench_rules().get("refine_yield") or [0.8, 0.85, 0.9, 0.95, 1.0])
    frac = float(yields[min(int(tier), len(yields) - 1)])
    total = sum(ph.motes * n for ph, n in plan.refine)
    motes = int(math.floor(total * frac + 1e-9))
    lead = _lead([ph for ph, _ in plan.refine])
    name = f"Refined {lead.name}" if lead else "Refined Essence"
    n = 1
    base = "enchant-refined-" + "".join(c if c.isalnum() else "-" for c in
                                        (lead.id if lead else "essence"))
    while f"{base}-{n}" in actor.stock:
        n += 1
    key = f"{base}-{n}"
    actor.stock[key] = Stock(
        base=name, count=1, craft=TRACK_ID, kind="essence", tier=_tier_of_motes(motes),
        properties=[f"{PHIAL_TAG}form.phial", f"{PHIAL_TAG}essence.{lead.id if lead else ''}",
                    f"{PHIAL_TAG}motes.{motes}", f"{PHIAL_TAG}family.{lead.family if lead else 'arcane'}"],
        how=["ingredient"])
    return key, name, motes


def _land_unbind(actor, progress, plan: StepPlan, *, now: int) -> dict:
    from . import magic_layer
    from .crafting import Stock

    v = plan.vessel
    st = _stock_of(actor, v.key)
    rec = _item_record(v.key, st)
    m = magic_layer.magic_of(rec)
    got = unbind_learn(actor, rec, now=now)
    # The layer comes off whole, its curse with it (plan §13): the smith's item stays.
    _store_magic(st, None)
    vname = str((m.get("binding") or {}).get("vessel_name") or plan.name_after or st.name)
    _rename(st, vname)
    products = [{"key": v.key, "name": vname, "state": "plain"}]
    back = 0
    for rid, n in (got.get("residue") or {}).items():
        if int(n or 0) > 0:
            actor.carry(str(rid), int(n))
            back += int(n)
            products.append({"key": f"inv:{rid}", "name": "Arcane Residue", "count": int(n),
                             "motes": int(n)})
    types = list(got.get("types") or got.get("learned") or [])
    words = [("an enhancement" if p == "enhancement" else
              str((effectspec.property(p) or {}).get("name") or p)) for p in types]
    said = (f"The {vname} gives up its magic"
            + (f"; you learn it carried {_say_list(words)}" if words else "")
            + (f", and {back} motes of residue come back." if back else "."))
    return {"said": said, "products": products,
            "discoveries": [{"property": p} for p in got.get("learned") or []]}


# =============================================================================================
# In progress: what Collect and Stop mean for a binding (rules/inprogress.py, lane G)
# =============================================================================================

def _collect_binding(item, actor) -> dict:
    """Write the layer onto the vessel at Collect (contracts §6): the binding's result, kept
    in the block since Bind, laid on through `magic_layer.write`."""
    from . import inprogress, magic_layer

    block = inprogress.work_of(item) or {}
    res = block.get("result") or {}
    if not res.get("adds"):
        return {"said": f"You collect the {item.name}."}
    key = next((k for k, st in (getattr(actor, "stock", {}) or {}).items() if st is item), "")
    rec = _item_record(f"stock:{key}", item)
    if rec is None:
        return {"ok": False, "why": f"The {item.name} is not a vessel any more."}
    try:
        new = magic_layer.write(rec, res["adds"], binding=res.get("binding") or {},
                                curse=res.get("curse"), day=res.get("day"))
    except ValueError as exc:
        return {"ok": False, "why": f"The binding cannot be laid on: {exc}"}
    m = new.get("magic") or {}
    m.pop("circle", None)
    if res.get("flawed"):
        # The maker saw the margin and the word FLAWED (owner round 4 point 2): the item
        # knows it is flawed, never which curse (lane F's card reads `known.flawed`).
        m["known"] = dict(m.get("known") or {}, flawed=True)
    _store_magic(item, m)
    name = str(res.get("name") or item.name)
    _rename(item, name)
    return {"said": f"You collect the {name}.",
            "product": {"key": f"stock:{key}", "name": name, "card": item_card(
                _item_record(f"stock:{key}", item) or {})}}


def _cancel_binding(item, actor) -> dict:
    return {"said": f"The binding is stopped. The {item.name} comes back as it was; the "
                    f"essences are spent."}


def _register() -> None:
    from . import inprogress

    inprogress.register(TRACK_ID, collect=_collect_binding, cancel=_cancel_binding,
                        icon="enchant",
                        stop_words="The vessel comes back unenchanted. The essences are "
                                   "spent.")


# =============================================================================================
# The lane F seam (contracts §7). Lane F (rules/curses.py, the enchanter half of
# rules/knowledge.py) merged into build/enchanting on 2026-10-05, after this lane branched.
# Each function below calls F's API with F's own signature when it is there, and otherwise
# does the least that keeps the bench honest, marked `"stub": True` in what it returns.
# =============================================================================================

def roll_curse(engine, record: dict, layer_plan: dict, adds: dict | None = None) -> dict:
    """A flawed binding's curse: `curses.roll(dice, record, dict(plan, adds=adds))` (lane
    F; `adds` lets a completely-different curse substitute like for like). STUB without
    F: the engine's hidden d100 and the item's caster level, `{"d100", "cl", "pending"}`,
    no row, so nothing is applied (`magic_layer._apply_curse` asks F) and F can read the
    row off the roll already made. Either way it never reaches the page."""
    fn = _lane_fn("curses", "roll")
    dice = getattr(engine, "dice", None)
    if fn is not None and dice is not None:
        return dict(fn(dice, record, dict(layer_plan or {}, adds=copy.deepcopy(adds or {})))
                    or {})
    face = 0
    if dice is not None:
        face = int(dice.roll("1d100", label="Enchanting: the flaw", visibility="hidden").total)
    return {"d100": face, "cl": int((layer_plan or {}).get("caster_level", 0) or 0),
            "pending": "rules/curses.py"}


def curse_words(curse: dict) -> str:
    """`curses.describe` (lane F). STUB: a curse lane F has not read says only that it is
    there. Asked only once the curse is known."""
    fn = _lane_fn("curses", "describe")
    if fn is not None:
        return str(fn(curse) or "")
    return "A curse, not yet read."


def cleanse_dc(record: dict) -> int:
    """Remove curse's DC (CRB): `curses.lift_dc` (lane F, 10 + the caster level the curse
    was laid at), else 10 + the item's caster level now."""
    from . import magic_layer

    m = magic_layer.magic_of(record)
    fn = _lane_fn("curses", "lift_dc")
    if fn is not None and isinstance(m.get("curse"), dict):
        return int(fn(m["curse"]))
    return int(_n("cleanse_dc_base", 10)) + magic_layer.caster_level(
        m, magic_layer.vessel_kind(record))


def lift_curse(record: dict) -> dict:
    """`curses.lift` (lane F): the record with the curse gone, the rest kept, and the owner
    knowing the item is clean. The book's remove curse is also the only way to put down an
    item that clings ("can only be discarded after ... remove curse", CRB Cursed Items):
    `curses.clings` answers False once it is lifted."""
    fn = _lane_fn("curses", "lift")
    if fn is not None:
        return dict(fn(record))
    rec = copy.deepcopy(dict(record or {}))
    m = dict(rec.get("magic") or {})
    m["curse"] = None
    m["known"] = dict(m.get("known") or {}, curse=True)
    rec["magic"] = m
    return rec


def clings(record: dict) -> bool:
    fn = _lane_fn("curses", "clings")
    return bool(fn(record)) if fn is not None else False


def recipe_known(actor, recipe_id: str) -> bool:
    fn = _lane_fn("knowledge", "knows_recipe")
    if fn is not None:
        return bool(fn(actor, str(recipe_id)))
    entry = (getattr(actor, "herb_known", None) or {}).get(str(recipe_id))
    return isinstance(entry, dict) and "recipe" in (entry.get("keys") or ())


def learn_recipe(actor, recipe_id: str, how: str) -> bool:
    fn = _lane_fn("knowledge", "learn_recipe")
    if fn is not None:
        return bool(fn(actor, str(recipe_id), how))
    from . import knowledge

    return bool(knowledge.reveal(actor, str(recipe_id), ["recipe"], how))


def learn_attuned(actor, essence_id: str, *, clock: int) -> list[str]:
    """Seating an essence shows its polarity and phase (plan §12.3): `knowledge.attuned`
    (lane F), else the bench writes the two keys itself."""
    fn = _lane_fn("knowledge", "attuned")
    if fn is not None:
        return list(fn(actor, essence_id, clock=clock) or [])
    return reveal_traits(actor, essence_id, ["polarity", "phase"],
                         f"attuned it, day {int(clock) // 1440 + 1}")


def learn_bound(actor, essence_id: str, *, clock: int) -> list[str]:
    """Binding an essence shows what it grants: `knowledge.bound` (lane F), else the key."""
    fn = _lane_fn("knowledge", "bound")
    if fn is not None:
        return list(fn(actor, essence_id, clock=clock) or [])
    return reveal_traits(actor, essence_id, ["grants"], f"bound it, day {int(clock) // 1440 + 1}")


def _unknown_traits(actor, essence_id: str) -> int:
    from . import materials

    doc = _essence_docs().get(str(essence_id))
    if doc is None:
        return 0
    have = set(((getattr(actor, "herb_known", None) or {}).get(essence_id) or {})
               .get("keys") or ())
    return sum(1 for k in materials.essence_traits(doc) if k not in have)


def known_traits(actor, essence_id: str) -> list[str]:
    return list(((getattr(actor, "herb_known", None) or {}).get(str(essence_id)) or {})
                .get("keys") or ())


def reveal_traits(actor, essence_id: str, keys, how: str) -> list[str]:
    """Record essence traits as known (plan §12.3) in the one store, `Actor.herb_known`
    (contracts §7), keyed by `materials.essence_traits`'s keys. Lane F owns the store's
    rules; this only writes the keys the bench reveals (seated: polarity and phase; bound:
    what it grants)."""
    from . import knowledge, materials

    doc = _essence_docs().get(str(essence_id))
    if doc is None:
        return []
    have = set(materials.essence_traits(doc))
    want = [k for k in keys if k in have]
    if not want:
        return []
    return knowledge.reveal(actor, str(essence_id), want, how)


def read_essence(actor, essence_id: str, total: int, *, clock: int) -> dict:
    """A Read on a total already rolled: `knowledge.read(actor, id, total, clock=)` (lane F:
    DC 10 + 5 a rarity band, the herb rule's one benefit and one drawback, and a volatile
    phial's danger named for `apply_danger`). Either way the keys in `revealed` are NEW
    and already written to the store. STUB without F: the next unknown trait, no DC; a
    volatile essence's danger named and not applied."""
    fn = _lane_fn("knowledge", "read")
    if fn is not None:
        got = fn(actor, essence_id, total, clock=clock)
        if isinstance(got, dict) and "revealed" in got:
            return got
    from . import materials

    doc = _essence_docs().get(str(essence_id)) or {}
    have = set(known_traits(actor, essence_id))
    nxt = next((k for k in materials.essence_traits(doc) if k not in have), None)
    new = reveal_traits(actor, essence_id, [nxt] if nxt else [],
                        f"read, day {int(clock) // 1440 + 1}")
    danger = None
    if any(w.get("trait") == "volatile" for w in doc.get("working") or ()):
        danger = next((dict(e) for e in doc.get("house") or () if materials.is_negative(e)),
                      None)
    return {"revealed": new, "success": True, "dc": None,
            "cost": {"phial": float(_n("read_pinch", 0.1))},
            "minutes": int((method_row("read") or {}).get("minutes", 10)), "danger": danger,
            "stub": True}


def apply_read_danger(engine, actor, essence_id: str, danger: dict | None) -> list:
    """A volatile phial bites whoever handles it, whatever the roll: `knowledge.apply_danger`
    (lane F) runs it through the one applicator with its tell (laws 2 and 3). Without F
    nothing is applied, and the response says so (`danger_applied: false`)."""
    fn = _lane_fn("knowledge", "apply_danger")
    if fn is None or not danger or engine is None:
        return []
    doc = _essence_docs().get(str(essence_id)) or {}
    return list(fn(engine, actor, essence_id, danger,
                   because=f"reading {doc.get('name') or essence_id}") or [])


def trait_words(doc: dict, key: str) -> str:
    """A revealed essence trait, in words for the ledger card."""
    from . import sky  # noqa: F401 - phases are words already

    if key == "grants":
        return f"grants {_grant_words(doc.get('grants'))}"
    if key == "phase":
        return f"binds best at {doc.get('phase')}"
    if key == "polarity":
        pol = doc.get("polarity") or "any"
        return "goes on anything" if pol == "any" else f"wants a {pol}"
    if key == "affinity":
        return "suits " + _say_list([str(a).replace("-", " ") for a in doc.get("affinity")
                                     or ()])
    if key.startswith("house:"):
        try:
            spec = (doc.get("house") or [])[int(key.split(":", 1)[1])]
        except (IndexError, ValueError):
            return key
        return effectspec.render(spec)
    if key.startswith("working:"):
        return key.split(":", 1)[1].replace("_", " ")
    return key


def identify_item(actor, record: dict, total: int, *, day: int) -> dict:
    """Lane F's `knowledge.identify`. STUB (plan §12.1, the book's Spellcraft rule): DC 15 +
    the item's caster level; beat it to learn the intent (and the recipe, if it was one),
    by 10 to see the curse too; once per item per day, a second try that day returns the
    first answer. Writes `magic.known` on the record handed in; the caller stores it.

    With lane F: `knowledge.identify(actor, record, total, day=)`, handed the bench's own
    record dict (its `magic` written in place, then stored by the caller), so the caster
    level is read off a record that says what gear it is: a forge item kept as a plain
    shelf entry has no record of its own for F to read."""
    fn = _lane_fn("knowledge", "identify")
    if fn is not None:
        got = fn(actor, record, total, day=day)
        if isinstance(got, dict) and "result" in got:
            return got
    from . import magic_layer

    m = magic_layer.magic_of(record)
    known = dict(m.get("known") or {})
    dc = int(_n("identify_dc_base", 15)) + magic_layer.caster_level(
        m, magic_layer.vessel_kind(record))
    tried = known.get("identified") or {}
    if int(tried.get("day", -1)) == int(day):
        return {"result": tried.get("result", "fail"), "learned": [], "recipe": None,
                "dc": dc, "again_on_day": int(day) + 1, "repeat": True, "stub": True}
    if total >= dc + 10:
        result = "curse"
    elif total >= dc:
        result = "intent"
    else:
        result = "fail"
    learned, recipe = [], None
    if result != "fail":
        known["intent"] = True
        learned = [e.get("id") for e in m["properties"] + m["flat"]]
        for p in m["powers"]:
            recipe = str(p.get("recipe") or "") or recipe
    if result == "curse":
        known["curse"] = True
    known["identified"] = {"day": int(day), "result": result}
    m["known"] = known
    record["magic"] = m
    return {"result": result, "learned": learned, "recipe": recipe, "dc": dc,
            "again_on_day": int(day) + 1, "stub": True}


def unbind_learn(actor, record: dict, *, now: int) -> dict:
    """What an Unbind that succeeded teaches and gives back: `knowledge.unbind(actor,
    record, clock=)` (lane F; no roll of its own, the bench's roll is the Unbind) →
    {"record": stripped, "learned", "types", "recipe", "recipes", "motes",
    "residue": {"arcane-residue": n}}. STUB without F, the same shape: the property TYPES
    (never their size: "the magnitude is irrelevant", Skyrim, plan §12.3), the recipes
    learned, a quarter of the layer's motes as residue, rounded down (owner, round 4)."""
    fn = _lane_fn("knowledge", "unbind")
    if fn is not None:
        got = fn(actor, record, clock=now)
        if isinstance(got, dict) and "learned" in got:
            return got
    from . import magic_layer

    m = magic_layer.magic_of(record)
    gear = magic_layer.vessel_kind(record)
    types = (["enhancement"] if m["enhancement"] and gear in magic_layer.ARMS else []) + \
        list(dict.fromkeys(str(e.get("id")) for e in m["properties"] + m["flat"]
                           if e.get("id")))
    recipes = [str(p.get("recipe")) for p in m["powers"] if p.get("recipe")]
    day = int(now) // 1440 + 1
    recipe = None
    for rid in recipes:
        if learn_recipe(actor, rid, f"unbound, day {day}") and recipe is None:
            recipe = rid
    price = magic_layer.market_price(m, gear, str(record.get("slot") or ""))
    motes = int(math.ceil(price * magic_layer.MAKING_FRACTION / magic_layer.GP_PER_MOTE
                          - 1e-9))
    residue = int(math.floor(motes * float(_n("residue_fraction", 0.25)) + 1e-9))
    stripped, _ = magic_layer.strip(record)
    return {"record": stripped, "learned": types, "types": types, "recipe": recipe,
            "recipes": recipes, "motes": motes,
            "residue": {str(_n("residue_id", "arcane-residue")): residue}, "stub": True}


# =============================================================================================
# Old saves: enchanted items from before the revamp (plan §19; contracts §12, lane H)
# =============================================================================================
#
# The owner's ruling (round 3): "Convert. ... old enchanted items keep their +N and specs,
# re-derived onto the new layer where possible, the old record kept beside them for one
# version." An item from the old circle or the old "By the book" tab is a shelf entry with
# `craft: "enchanter"`, a flat `specs` list, an `enhancement` number, `properties` as display
# NAMES and `from_materials` naming what it was made from (catalogue `mi-*` ids, or essence
# ids beside the focus and vessel). Nothing on it says what a property's choice was, and its
# numbers were written once and never re-read, so a corrected document corrected nothing.
#
# Prior art read before this was designed (CLAUDE.md, "search first"):
# - Factorio's migrations (https://lua-api.factorio.com/latest/Migrations.html): a rename
#   table first (lane A's `aliases`, `effectspec.from_alias`), then code that adjusts state
#   (`migrate_old_record`), each remembered by name so it never runs twice (`MIGRATION_STAMP`
#   on the layer; idempotent because a record with a layer is not an old record).
# - Path of Exile's "legacy" items (forum thread 3229344, "Items updated to new mod values
#   which retain old mod values"): items that WORK by the new numbers while still SHOWING the
#   old ones were the complaint. So the converted record's own `effects` prose is rewritten
#   to what still rides flat on it, and every other line on the card is the layer's, read
#   live; the old numbers survive only in `magic.migrated.from`, for undo.
# - The quarantine pattern (a farm-game engine's issue #52, "drop or quarantine missing
#   IDs"): what nothing maps is neither dropped nor guessed. It stays on the record as the
#   flat spec it was, read exactly as before (`magic_layer.record_specs`), and is named in
#   the conversion's notes. The plan's `legacy_specs` field would have needed a new reader in
#   lane B's and lane C's files; keeping them in `specs` is "read as today" with none.
#
# **Never guess a choice.** A choice the old record cannot prove is asked of the player. Bane
# is the case lane A named: `mi-bane` maps to bane with no foe, because the old bane never
# named one. Where the old numbers DO settle a choice (an old Knack Essence's +N on one skill
# is skill competence on that skill at +N) it is read, not guessed: every way the property
# can be bound is tried and the old specs must pick out exactly one. A tie is a question.
# An unanswered property waits on the layer under `pending` — the layer builder skips it, so
# it does nothing until answered (an old bane's +2d6 on EVERY foe was the note-only defect
# bane's `when` exists to close; carrying it on would keep the bug) — and the item card asks
# (`item_card`'s `question`), as does the one-time notice (`conversions`).

MIGRATION_STAMP = "enchanting-19"
# The vessel's quality index: an old enchanted item was masterwork by the old rule (both
# old modes demanded or granted it), and the forge's Superior is masterwork (forge §4.4).
_MIGRATED_QUALITY = 3


def is_old_enchanted(d) -> bool:
    """An enchanted item from before the revamp: a shelf or worn record of the old circle
    or the old "By the book" tab, with a +N, named properties or flat specs and no layer.

    Not one: anything with a `magic` layer or a forge record (`pieces`), anything in
    progress, the new bench's phials (`enchant.*` tags) and blanks (no numbers at all)."""
    if not isinstance(d, dict) or str(d.get("craft") or "") != TRACK_ID:
        return False
    if isinstance(d.get("pieces"), dict) or d.get("work"):
        return False
    if isinstance(d.get("magic"), dict) and d["magic"]:
        return False
    if any(str(p).startswith(PHIAL_TAG) for p in d.get("properties") or ()):
        return False
    try:
        enh = int(d.get("enhancement") or 0)
    except (TypeError, ValueError):
        enh = 0
    return bool(enh or d.get("properties") or d.get("specs"))


def _old_source_names() -> dict[str, str]:
    """{id: display name} for everything an old item's specs could say they came `from`:
    the old catalogue (retired rows included: `magicitem.catalogue` keeps them) and every
    shelf material, old library and lane D's essences both. These are TODAY's names, and
    three catalogue rows were renamed by lane D's book check (Gauntlets of Rust is now
    Gauntlet of Rust, Belt of Mighty Hurling is the Lesser one, Ring of Mindshielding is
    Ring of Mind Shielding): measured on the old corpus, their specs stayed flat beside the
    power they had become, so the item did its thing twice. `_labels` adds the name the old
    record itself wrote."""
    names: dict[str, str] = {}
    try:
        from . import magicitem

        names.update({k: v.name for k, v in magicitem.catalogue().items()})
    except Exception:  # noqa: BLE001 - a broken homebrew catalogue still migrates the rest
        pass
    try:
        names.update({k: m.name for k, m in materials().items()})
    except Exception:  # noqa: BLE001
        pass
    names.update({k: str(d.get("name") or k) for k, d in _essence_docs().items()})
    return names


def _norm(text) -> str:
    return " ".join(str(text or "").split()).strip().lower()


def _sig(doc: dict) -> tuple:
    """What a document does, as a comparable fact: type, target, number, energy. An old
    flat spec and a bound document agree on this when they are the same effect."""
    amount = doc.get("amount", doc.get("dice", doc.get("percent")))
    return (str(doc.get("type") or ""), _norm(doc.get("target")), _norm(amount),
            _norm(doc.get("damage_type")))


def _infer_choice(prop: dict, partial: dict, old_specs: list[dict]) -> dict:
    """The choice the old numbers prove, or `partial` unchanged.

    Every complete way the property can be bound (`effectspec.sample_choices`, with what
    is already known kept) is bound and compared with what the old item actually did. Only
    a single best match is taken; a tie, or nothing in common, leaves the choice open for
    the player. Bane ties across every creature type (its old numbers never named a foe), so
    bane is always asked."""
    if not effectspec.choice_problems(prop, partial):
        return partial
    old = {_sig(s) for s in old_specs}
    if not old:
        return partial
    scored: list[tuple[int, dict]] = []
    for pick in effectspec.sample_choices(prop):
        merged = {**pick, **{k: v for k, v in partial.items() if v not in (None, "", {})}}
        if effectspec.choice_problems(prop, merged) or any(merged == c for _, c in scored):
            continue
        try:
            docs = effectspec.bind(prop, merged)
        except (ValueError, KeyError):
            continue
        scored.append((len({_sig(d) for d in docs} & old), merged))
    if not scored:
        return partial
    best = max(n for n, _ in scored)
    winners = [c for n, c in scored if n == best]
    return winners[0] if best and len(winners) == 1 else partial


def _missing(prop: dict, choice: dict) -> list[str]:
    """Which parts of a choice the player still has to give: the property's own key
    (`foe`, `skill`, `energy`) and, for a scaled one, `bonus`."""
    out = []
    spec = prop.get("choice") or {}
    if spec and choice.get(spec.get("key")) in (None, "", {}):
        out.append(str(spec["key"]))
    scaled = prop.get("scaled") or {}
    if scaled and choice.get("bonus") not in scaled.get("values", ()):
        out.append("bonus")
    return out


def _sources_of(d: dict, names: dict[str, str]) -> list[str]:
    """What the old item was made from, as ids: its `from_materials`, or for a record that
    predates that field, its property names read back to ids."""
    got = [str(x).strip().lower() for x in d.get("from_materials") or () if x]
    if got:
        return list(dict.fromkeys(got))
    by_name = {_norm(n): k for k, n in sorted(names.items())}
    return list(dict.fromkeys(by_name[_norm(n)] for n in d.get("properties") or ()
                              if _norm(n) in by_name))


def _labels(d: dict, sources: list[str], names: dict[str, str]) -> dict[str, set[str]]:
    """Every name an old item's specs may give each source in `from`: today's name, and the
    name the old record wrote itself. Both old benches wrote `properties` as the names of
    exactly the things specs came from, in `from_materials` order — every catalogue entry
    (the book tab), every essence (the circle; its focus, vessel and inks made no specs) —
    so the two lists pair up by position when their lengths agree."""
    out = {mid: {_norm(names.get(mid, mid))} for mid in sources}
    try:
        shelf = materials()
    except Exception:  # noqa: BLE001
        shelf = {}
    makers = [mid for mid in sources if mid.startswith("mi-")
              or getattr(shelf.get(mid), "kind", "") == "essence"
              or mid in _essence_docs()]
    said = [_norm(n) for n in d.get("properties") or ()]
    if len(makers) == len(said):
        for mid, label in zip(makers, said):
            out[mid].add(label)
    return out


def migrate_old_record(d) -> dict | None:
    """An old enchanted item re-derived onto the magic layer, or None when `d` is not one
    (plan §19, the owner's "convert").

    - The +N becomes `magic.enhancement` (arms and armour; the book's +5 kept).
    - Each catalogue property (`mi-*`) becomes its property by lane A's alias, with the
      choice the alias implies; each essence its grant (lane D's `grants`); each catalogue
      wondrous item a recipe power, retired rows included (they still resolve through the
      old catalogue in `magic_layer.recipe`, so an item built on one keeps working and is
      never offered again). Essences that now grant an enhancement are the +N already.
    - A choice the old record cannot prove waits in `magic.pending`, asked, never guessed.
    - Specs from anything nothing maps (a mote that grants nothing now) stay flat, read as
      before.
    - Arms and armour become a forged record of their base (`forge_items.record_for_base`,
      default pieces marked plain, Superior), so the armour row folds the +N into the suit
      and the material tag answers. Rings and wondrous items keep their shelf shape with the
      layer on `magic`. An item whose base the tables do not know keeps its shelf shape too.
    - The binding is stamped at the Enchanter level that holds what the item carries
      (capacity floor(level / 2), owner round 4): it was made, so it held it.

    **The old record is kept beside the new, for one version**, in `magic.migrated.from`
    (`undo_migration`); remove it in the release after the one that ships this. The keys
    the readers find it by — id, name, the shelf key — do not change.
    """
    if not is_old_enchanted(d):
        return None
    from . import armour as armour_mod
    from . import forge_items, magic_layer

    old = copy.deepcopy(d)
    names = _old_source_names()
    essences = _essence_docs()
    specs = [dict(s) for s in d.get("specs") or () if isinstance(s, dict)]
    try:
        enh = max(0, min(magic_layer.MAX_ENHANCEMENT, int(d.get("enhancement") or 0)))
    except (TypeError, ValueError):
        enh = 0
    name = str(d.get("name") or d.get("base") or "Enchanted item")

    gear, base = "", ""
    if d.get("weapon"):
        gear, base = "weapon", str(d["weapon"])
    elif d.get("armour"):
        kind, _ = armour_mod.key_for(str(d["armour"]))
        gear, base = (kind or "armour"), str(d["armour"])
    arms = gear in magic_layer.ARMS

    covered: set[str] = set()
    # Where the +N's own specs say they came from: "+1" (the book tab) or an arcane or
    # warding essence's name (the circle). Covered only when the +N moves onto the layer.
    plus_labels: set[str] = {_norm(f"+{n}") for n in range(1, magic_layer.MAX_ENHANCEMENT + 1)}
    props: list[dict] = []
    flat: list[dict] = []
    powers: list[dict] = []
    pending: list[dict] = []
    changes: list[str] = []

    def from_of(s: dict) -> str:
        return _norm(s.get("from"))

    sources = _sources_of(d, names)
    labels = _labels(d, sources, names)
    for mid in sources:
        label = names.get(mid, mid)
        mine = [s for s in specs if from_of(s) in labels[mid]]
        essence = None
        alias = effectspec.from_alias(mid)
        if alias:
            pid, choice = alias[0], dict(alias[1] or {})
        elif mid in essences:
            grants = essences[mid].get("grants") or {}
            if "enhancement" in grants:
                plus_labels |= labels[mid]       # the +N, read off `enhancement` above
                continue
            if grants.get("power"):
                powers.append({"recipe": str(grants["power"]), "essence": mid})
                covered |= labels[mid]
                changes.append(f"{label}: now {_recipe_name(grants['power'])}.")
                continue
            if not grants.get("property"):
                continue                         # grants nothing now: its specs stay flat
            pid, essence = str(grants["property"]), mid
            choice = dict(grants.get("choice") or {})
            if grants.get("bonus") is not None:
                choice["bonus"] = int(grants["bonus"])
        elif magic_layer.recipe(mid) is not None:
            powers.append({"recipe": mid, "essence": None})
            covered |= labels[mid]
            continue
        else:
            continue                             # a vessel, focus, ink: no specs of its own
        prop = effectspec.property(pid)
        if prop is None:
            continue
        choice = _infer_choice(prop, choice, mine)
        covered |= labels[mid]
        entry = {"id": prop["id"], "essence": essence, "choice": choice or None}
        if any(e["id"] == entry["id"] and (e.get("choice") or None) == entry["choice"]
               for e in props + flat + pending):
            continue
        ask = _missing(prop, choice)
        if ask:
            pending.append({**entry, "asks": ask})
            changes.append(f"{prop['name']}: waits for you to choose its {_say_list(ask)}; "
                           f"until then it does nothing.")
            continue
        (flat if prop.get("gp") is not None else props).append(entry)
        before = [effectspec.render(s) for s in mine]
        # A property that is a rule rather than a number (returning, bashing) has no line
        # of its own; its card text says what it does.
        after = effectspec.property_lines(prop, choice) or [str(prop.get("text") or "")]
        # Compared as facts, with the trigger, not as rendered words: "Resist fire 10
        # (permanent)" and "Resist fire 10" are the same effect, while the old flaming's
        # "1d6 fire damage" (a note no reader fired) and the new "1d6 fire damage, on a
        # hit" are not, and the player should be told the fire lands now.
        was = {_sig(s) + (str(s.get("trigger") or ""),) for s in mine}
        now = {_sig(x) + (str(x.get("trigger") or ""),) for x in effectspec.bind(prop, choice)}
        if before and was != now:
            changes.append(f"{prop['name']}: was {'; '.join(b.rstrip('.') for b in before)}"
                           f"; now {'; '.join(a.rstrip('.') for a in after)}.")

    # Arms and armour become a forged record of their base, which the armour row and the
    # material tag read. A forged build reads its pieces and its layer, never a flat
    # `specs` list, so an item with something left flat keeps its shelf shape, where
    # `magic_layer.record_specs` reads both. Measured on the old corpus (268 items the old
    # code makes, tests/test_enchant_migration.py): only 19 bound with an essence that
    # grants nothing now (a mote, or an alchemist's essence the old shelf also read) leave
    # anything flat.
    rid = str(d.get("id") or "").split("#", 1)[0] or _slug(name)
    rec = None
    if arms:
        try:
            rec = forge_items.record_for_base(base, gear=gear,
                                              quality_index=_MIGRATED_QUALITY,
                                              item_id=rid, name=name)
        except ValueError:
            rec = None
    flat_left = [s for s in specs if from_of(s) not in covered | plus_labels]
    forge = rec is not None and not flat_left
    # The +N moves onto the layer on a forged item and on a weapon (whose shelf record the
    # attack path reads with its layer, `Actor._crafted_weapon`). Not on a shelf-kept suit:
    # the layer's +N is an ARMOUR bonus that only the forged armour row folds into the
    # suit's, and read loose it would be one more armour bonus the suit's own beats — so a
    # suit that stays on the shelf keeps its +N flat, as it was. Nor on a ring: the book
    # gives rings no enhancement.
    if enh and (forge or gear == "weapon"):
        covered |= plus_labels
    else:
        enh = 0
    legacy = [s for s in specs if from_of(s) not in covered]
    if legacy:
        changes.append("Kept as it was (nothing in the new enchanting reads it): "
                       + "; ".join(effectspec.render(s) for s in legacy) + ".")

    magic: dict = {
        "schema": magic_layer.SCHEMA, "enhancement": enh, "properties": props,
        "flat": flat, "powers": powers,
        "binding": {"quality_index": _MIGRATED_QUALITY, "level": 1, "perks": {},
                    "migrated": True},
        # Made or bought before curses existed, and known to whoever has it: nothing to
        # identify, and no curse question to leave open on the card.
        "curse": None, "known": {"intent": True, "curse": True, "how": "migrated"},
        "uses": {}, "made_day": None,
        "migrated": {"stamp": MIGRATION_STAMP, "from": old, "changes": changes,
                     "seen": False},
    }
    if pending:
        magic["pending"] = pending
    used = magic_layer.used(magic_layer.magic_of({"magic": magic}), gear or "wondrous")
    magic["binding"]["level"] = max(1, magic_layer.CAPACITY_LEVELS_PER_BONUS * used)

    if forge:
        rec["craft"] = TRACK_ID
        rec["count"] = int(d.get("count", 1) or 1)
        rec["magic"] = magic
        return rec
    out = copy.deepcopy(d)
    out["magic"] = magic
    out["specs"] = legacy
    out["effects"] = [effectspec.render(s) for s in legacy]
    # The shelf entry's own `enhancement` and `properties` were display fields nothing
    # computes from; the layer says them now. A ring's +N is not the layer's (above), so
    # its number stays where its flat spec still reads it.
    out["enhancement"] = int(out.get("enhancement") or 0) if not enh else 0
    out["properties"] = []
    return out


def _recipe_name(recipe_id) -> str:
    from . import magic_layer

    r = magic_layer.recipe(str(recipe_id or "")) or {}
    return str(r.get("name") or recipe_id)


def _slug(name: str) -> str:
    out = "".join(c if c.isalnum() else "-" for c in str(name).lower()).strip("-")
    while "--" in out:
        out = out.replace("--", "-")
    return out


def undo_migration(record) -> dict | None:
    """The old record a converted one was made from, while it is still kept."""
    from . import magic_layer

    got = (magic_layer.magic_of(record).get("migrated") or {}).get("from")
    return copy.deepcopy(got) if isinstance(got, dict) else None


def pending_of(record) -> list[dict]:
    """The questions a converted item is waiting on, as the page asks them: {"property",
    "name", "asks", "options", "words"}. `options` are the engine's (lane A's choice lists),
    so the page offers and never invents; a humanoid or outsider foe also needs a subtype,
    which is the world's own and typed by the player."""
    from . import magic_layer

    out = []
    for p in magic_layer.magic_of(record).get("pending") or ():
        prop = effectspec.property(str(p.get("id") or ""))
        if prop is None:
            continue
        spec = _choices_for(prop) or {}
        asks = list(p.get("asks") or ())
        q = {"property": prop["id"], "name": prop["name"], "asks": asks,
             "options": spec.get("options") or [], "of": spec.get("of"),
             "key": spec.get("key")}
        if "bonus" in asks:
            q["bonus_values"] = list((prop.get("scaled") or {}).get("values") or ())
        what = "foe" if spec.get("of") == "creature_type" else (spec.get("key") or "bonus")
        q["words"] = (f"{prop['name']} on {record.get('name') or 'this item'} never named "
                      f"its {what}. Choose it and it starts working.")
        out.append(q)
    return out


def answer_pending(record, property_id: str, answer: dict) -> dict:
    """A new record with one pending property answered and bound (pure). `answer` is the
    choice's own keys (`{"foe": "undead"}`, `{"foe": {"subtype": "goblinoid"}}`,
    `{"skill": "stealth", "bonus": 2}`). Raises ValueError with the engine's sentence for a
    choice the property would not bind, so a bad answer leaves the question open."""
    from . import magic_layer

    rec = copy.deepcopy(dict(record or {}))
    m = rec.get("magic") if isinstance(rec.get("magic"), dict) else {}
    waiting = list(m.get("pending") or ())
    pid = str(property_id or "").strip().lower()
    hit = next((p for p in waiting if str(p.get("id")) == pid), None)
    if hit is None:
        raise ValueError(f"{rec.get('name') or 'This item'} is not waiting on {pid!r}.")
    prop = effectspec.property(pid)
    if prop is None:
        raise ValueError(f"There is no magic property {pid!r}.")
    choice = {k: v for k, v in dict(hit.get("choice") or {}).items() if v not in (None, "", {})}
    for k, v in dict(answer or {}).items():
        if isinstance(v, str):
            v = v.strip().lower()
        if k == "bonus":
            try:
                v = int(v)
            except (TypeError, ValueError):
                pass
        choice[str(k)] = v
    problems = effectspec.choice_problems(prop, choice)
    if problems:
        raise ValueError("; ".join(problems))
    entry = {"id": prop["id"], "essence": hit.get("essence"), "choice": choice}
    key = "flat" if prop.get("gp") is not None else "properties"
    m[key] = list(m.get(key) or ()) + [entry]
    m["pending"] = [p for p in waiting if p is not hit]
    if not m["pending"]:
        m.pop("pending")
    note = m.get("migrated")
    if isinstance(note, dict):
        # Plain words, no dash (the final pass, 2026-10-06: "Bane: you named it — ...").
        line = f"{prop['name']}, now named: {'; '.join(effectspec.property_lines(prop, choice))}."
        note["changes"] = [c for c in note.get("changes") or ()
                           if not str(c).startswith(f"{prop['name']}: waits")] + [line]
    # The binding still holds what the item now carries (it was made with this property).
    used = magic_layer.used(magic_layer.magic_of({"magic": m}),
                            magic_layer.vessel_kind(rec))
    binding = m.setdefault("binding", {})
    binding["level"] = max(int(binding.get("level", 1) or 1),
                           magic_layer.CAPACITY_LEVELS_PER_BONUS * used)
    rec["magic"] = m
    return rec


def _converted_things(actor):
    """(where, key, record getter, record setter) for everything the actor carries or wears
    that was converted: the pack's entries and the worn copies `wear` keeps."""
    from . import forge_items

    for sid, st in (getattr(actor, "stock", {}) or {}).items():
        rec = forge_items.record_of(st)
        if rec is not None:
            yield f"stock:{sid}", rec, (lambda new, st=st: _put_record(st, new))
            continue
        magic = getattr(st, "magic", None)
        if isinstance(magic, dict) and magic.get("migrated"):
            yield f"stock:{sid}", st.as_dict(), (lambda new, st=st: setattr(
                st, "magic", copy.deepcopy(new.get("magic"))))
    for wk, rec in (getattr(actor, "worn", {}) or {}).items():
        if isinstance(rec, dict):
            yield f"worn:{wk}", rec, (lambda new, wk=wk: actor.worn.__setitem__(wk, new))


def _put_record(st, new: dict) -> None:
    rec = getattr(st, "record", None)
    if isinstance(rec, dict) and "pieces" in rec:
        rec.clear()
        rec.update(copy.deepcopy(new))
    else:
        st.magic = copy.deepcopy(new.get("magic"))


def _same_item(a: dict, b: dict) -> bool:
    return bool({_norm(a.get("id")), _norm(a.get("name"))} - {""}
                & {_norm(b.get("id")), _norm(b.get("name"))})


def conversions(actor) -> list[dict]:
    """The one-time notice on the first load after the revamp (owner round 3): every carried
    or worn item the migration converted and the player has not yet been shown, with what
    changed, and every question still open. Read by the bench state; a worn copy and its
    pack entry are one item and listed once. [] for a save with nothing converted."""
    from . import magic_layer

    out: list[dict] = []
    seen: list[dict] = []
    for key, rec, _ in _converted_things(actor):
        m = magic_layer.magic_of(rec)
        note = m.get("migrated")
        if not isinstance(note, dict) or any(_same_item(rec, s) for s in seen):
            continue
        questions = pending_of(rec)
        if note.get("seen") and not questions:
            continue
        seen.append(rec)
        out.append({"key": key, "name": str(rec.get("name") or ""),
                    "changes": list(note.get("changes") or ()), "questions": questions,
                    "seen": bool(note.get("seen"))})
    return out


def _each_copy(actor, key: str, change) -> int:
    """Apply `change(record) -> record` to the item `key` names and to every other copy of
    the same item (the pack entry and its worn copy). Returns how many were changed."""
    things = list(_converted_things(actor))
    target = next((rec for k, rec, _ in things if k == key), None)
    if target is None:
        raise ValueError("You are not carrying that.")
    n = 0
    for _, rec, put in things:
        if rec is target or _same_item(rec, target):
            put(change(copy.deepcopy(rec)))
            n += 1
    return n


def answer_question(actor, key: str, property_id: str, answer: dict) -> dict:
    """Answer one converted item's open question, on the pack entry and its worn copy alike.
    Returns `{"ok": True, "lines": [...]}` (the property's card lines as now bound) or
    raises ValueError with the sentence to show."""
    _each_copy(actor, key, lambda rec: answer_pending(rec, property_id, answer))
    prop = effectspec.property(property_id) or {}
    rec = next(rec for k, rec, _ in _converted_things(actor) if k == key)
    from . import magic_layer

    entry = next((e for e in magic_layer.magic_of(rec)["properties"]
                  + magic_layer.magic_of(rec)["flat"] if e.get("id") == prop.get("id")), {})
    return {"ok": True, "lines": effectspec.property_lines(prop, entry.get("choice"))
            if prop else []}


def conversion_seen(actor, key: str) -> None:
    """The notice is shown once: mark it seen (the open questions stay on the item card)."""
    def mark(rec):
        m = rec.get("magic") if isinstance(rec.get("magic"), dict) else None
        if m and isinstance(m.get("migrated"), dict):
            m["migrated"]["seen"] = True
        return rec

    _each_copy(actor, key, mark)


# =============================================================================================
# The old shelf library: the /craft/ page's catalogue and the acquisition hub
# =============================================================================================

class CraftError(ValueError):
    """Kept for the routing table's shape (rules/benches.py)."""


@dataclass
class Material:
    """One thing on the old enchanter's shelf, as the `/craft/` page and the acquisition
    hub still read it. `capacity` on a focus, `fragile` on the diamond, `dc_mod` on a
    catalyst and `lifts` on a treatment are read by the new bench too (the circle)."""
    id: str
    name: str
    kind: str = "essence"
    tier: str = "common"
    family: str = ""
    adjective: str = ""
    plus: int = 0
    prefers: str = ""
    binds_at: str = ""
    capacity: int = 0
    fragile: bool = False
    requires: str = ""
    consumed: bool = False
    dc_mod: int = 0
    lifts: str = ""
    text: str = ""
    obtain: str = "bought"
    biomes: list[str] = field(default_factory=list)
    from_creature: list[str] = field(default_factory=list)
    price_gp: float = 0
    effects: list = field(default_factory=list)
    drawbacks: list = field(default_factory=list)

    @property
    def rank(self) -> int:
        return wc.tier_rank(self.tier)

    @property
    def glyph(self) -> str:
        return KIND_GLYPH.get(self.kind, "✨")

    def as_dict(self) -> dict:
        return {
            "id": self.id, "name": self.name, "kind": self.kind, "tier": self.tier,
            "rank": self.rank, "family": self.family, "adjective": self.adjective,
            "plus": self.plus, "prefers": self.prefers, "binds_at": self.binds_at,
            "capacity": self.capacity, "fragile": self.fragile,
            "requires": self.requires, "consumed": self.consumed,
            "dc_mod": self.dc_mod, "lifts": self.lifts, "text": self.text,
            "obtain": self.obtain, "biomes": self.biomes,
            "from_creature": self.from_creature, "price_gp": self.price_gp,
            "glyph": self.glyph,
            "effects": self.effects, "drawbacks": self.drawbacks,
        }


def from_dict(d: dict) -> Material:
    """An old-shape entry. An essence's `effects` are its `grants` read through lane A's
    table where it has one (lane D's fields; the old prose list is read only when there is
    no grant), so the shelf card says what binding it really does."""
    effects = list(d.get("effects") or [])
    grants = d.get("grants") if isinstance(d.get("grants"), dict) else None
    if grants and grants.get("property"):
        try:
            effects = effectspec.bind(str(grants["property"]), grants.get("choice")
                                      or ({"bonus": grants["bonus"]} if grants.get("bonus")
                                          else None))
        except (ValueError, KeyError):
            pass
    return Material(
        id=d["id"], name=d.get("name", d["id"]), kind=d.get("kind", "essence"),
        tier=d.get("tier", "common"), family=d.get("family", ""),
        adjective=d.get("adjective", ""),
        plus=int((grants or {}).get("enhancement", d.get("plus", 0)) or 0),
        prefers=str(d.get("polarity") or d.get("prefers", "") or ""),
        binds_at=("night" if any(w.get("trait") == "night_only" for w in d.get("working")
                                 or () if isinstance(w, dict)) else d.get("binds_at", "")),
        capacity=int(d.get("capacity", 0) or 0), fragile=bool(d.get("fragile")),
        requires=d.get("requires", ""), consumed=bool(d.get("consumed")),
        dc_mod=int(d.get("dc_mod", 0) or 0), lifts=d.get("lifts", ""),
        text=d.get("text", ""),
        obtain=str(d.get("obtain") or "bought").strip().lower(),
        biomes=[str(b).strip().lower() for b in (d.get("biomes") or [])],
        from_creature=[str(c).strip().lower() for c in (d.get("from_creature") or [])],
        # Fractional prices kept (1 cp is 0.01): `int()` made them free.
        price_gp=(lambda g: int(g) if g.is_integer() else g)(float(d.get("price_gp", 0) or 0)),
        effects=effects,
        drawbacks=list(d.get("drawbacks") or []),
    )


_MATERIALS: dict[str, Material] | None = None

# Files in the shared shelf folder that are not shelf materials: the recipe catalogue.
NOT_SHELF = {"magic-items"}


def materials() -> dict[str, Material]:
    """Every enchanter material the app knows, shipped and homebrew, merged entry by entry
    (the `worldclass.tracks()` overlay rule)."""
    global _MATERIALS
    if _MATERIALS is None:
        from django.conf import settings

        raw: dict[str, dict] = {}
        shipped = Path(settings.BASE_DIR) / "content" / "materials"
        user = Path(settings.CAMPAIGN_DIR).parent / "homebrew" / "materials"
        for folder in (shipped, user):
            if not folder.is_dir():
                continue
            for path in sorted(folder.glob("*.json")):
                if path.stem in NOT_SHELF:
                    continue
                for key, entry in _entries(path):
                    raw.setdefault(key, {}).update(entry)
        _MATERIALS = {k: from_dict({**v, "id": k}) for k, v in raw.items()}
    return _MATERIALS


def _entries(path: Path):
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return
    entries = data.get("materials") if isinstance(data, dict) else None
    if not isinstance(entries, list):
        entries = [data] if isinstance(data, dict) and data.get("id") else []
    for entry in entries:
        if isinstance(entry, dict) and entry.get("id"):
            yield str(entry["id"]).strip().lower(), entry


def get(material_id: str) -> Material:
    m = materials().get((material_id or "").strip().lower())
    if m is None:
        raise KeyError(f"no enchanting material {material_id!r}")
    return m


# The old chain, refused by `rules/benches.MOVED`: these exist so `benches.supports` keeps
# answering for every track, and say the same thing if anything calls them directly.
MOVED_WORDS = ("Enchanting is worked at the circle at the table now, one step at a time: "
               "prepare, attune, bind.")


@dataclass
class Chain:
    methods: list[str] = field(default_factory=list)
    material_ids: list[str] = field(default_factory=list)
    item: str = ""
    name: str = ""

    @property
    def stages(self) -> int:
        return len(self.methods)


def chain_from_body(body: dict) -> Chain:
    body = dict(body or {})

    def as_list(value):
        if isinstance(value, str):
            return [p.strip().lower() for p in value.split(",") if p.strip()]
        return [str(v).strip().lower() for v in (value or [])]

    return Chain(methods=as_list(body.get("methods")),
                 material_ids=as_list(body.get("materials", body.get("material_ids"))),
                 item=str(body.get("item", "") or "").strip(),
                 name=str(body.get("name", "") or "").strip())


@dataclass
class Result:
    name: str = ""
    tier: str = "common"
    rank: int = 1
    stages: int = 0
    dc: int = 0
    problems: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {"name": self.name, "tier": self.tier, "rank": self.rank,
                "stages": self.stages, "dc": self.dc, "problems": list(self.problems)}


def preview(level: int, chain: Chain, **_kw) -> Result:
    return Result(name=chain.name or chain.item, stages=chain.stages,
                  problems=[MOVED_WORDS])


# One glyph per material kind, the Enchanter's reserved pool (rules/benches.glyphs asserts
# no two crafts share one).
KIND_GLYPH: dict[str, str] = {
    "essence": "✨",
    "focus": "💎",
    "ink": "🖋️",
    "chalk": "🜏",
    "salt": "⭐",
    "vessel": "🔮",
    "catalyst": "📿",
    "treatment": "🧿",
}


ACQUISITION: list[dict] = [
    {"id": "essence-hunt", "label": "Skim essence", "obtain": "gathered",
     "needs": {"biome": True},
     "blurb": "Motes and residues are skimmed where the world runs thin: a forge's "
              "heart, a storm's tail, the flagstones of a bad death. What is out "
              "depends on where you are standing and, for some of it, on the hour.",
     "yields_kind": "essence"},
    {"id": "gem-cutting", "label": "Mine and cut foci", "obtain": "mined",
     "needs": {"biome": True},
     "blurb": "Quartz from any hillside, amethyst from a geode seam, diamond from "
              "somewhere that will cost you. A focus is set into a ring or an amulet "
              "when its circle is laid.",
     "yields_kind": "focus"},
    # `reliquary-harvest` left the hub with the other three carcass excursions
    # (leatherworking lane C, plan §5.1): the slain are harvested once, across every
    # craft, by rules/harvest.py, an essence being a `harvest.essence.*` tag on the body.
    {"id": "scriptorium-order", "label": "Buy inks, chalks and catalysts",
     "obtain": "bought", "needs": {"market": True},
     "blurb": "Silver ink, consecrated chalk, powdered pearl. Circle materials are "
              "spent by every Prepare, so this is the errand an enchanter runs most.",
     "yields_kind": "ink"},
    {"id": "vessel-commission", "label": "Commission a vessel", "obtain": "bought",
     "needs": {"market": True, "craft": ("blacksmith", "leatherworker")},
     "blurb": "A Superior weapon or suit from the smith, a cloak or boots from the "
              "leatherworker, or their own bench if the character has the track. Arms "
              "and armour take magic only from masterwork up.",
     "yields_kind": "vessel"},
]


def obtainable(obtain_kind: str, *, biome: str | None = None,
               creature: str | None = None) -> list[Material]:
    want = (obtain_kind or "").strip().lower()
    out: list[Material] = []
    for _, m in sorted(materials().items()):
        if m.obtain != want:
            continue
        if biome and m.biomes and biome.strip().lower() not in m.biomes:
            continue
        if creature and m.from_creature:
            said = creature.strip().lower()
            if not any(part in said or said in part for part in m.from_creature):
                continue
        out.append(m)
    return out


_register()

__all__ = ["ACQUISITION", "BLANKS", "Chain", "CraftError", "KIND_GLYPH", "MIGRATION_STAMP",
           "Material", "answer_pending", "answer_question", "conversion_seen", "conversions",
           "is_old_enchanted", "migrate_old_record", "pending_of", "undo_migration",
           "Phial", "StepPlan", "TRACK_ID", "Vessel", "bench_rules", "bound_name",
           "chain_from_body", "check_bonus", "check_terms", "circle_items", "finish",
           "from_dict", "get", "identify_item", "item_card", "materials", "methods_view",
           "miss", "obtainable", "phials", "plan_step", "preview", "read_essence",
           "reveal_traits", "roll_curse", "shelf", "spend", "tuning_for", "unbind_learn",
           "verdict_of", "vessels", "where_here"]
