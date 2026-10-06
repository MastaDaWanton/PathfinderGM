"""The magic layer: what an enchanter puts on top of an item, and what it does.

Enchanting plan §6 and contracts §3, as the owner's rulings of rounds 4 and 5 changed them
(docs/enchanting-answers.md). The forged sword stays the smith's work — its pieces, metals,
quench and quality — and the enchanter's work is one optional field on the same record:

    "magic": {"schema": 1, "enhancement": 1,
              "properties": [{"id": "bane", "essence": "bane-essence",
                              "choice": {"foe": "undead"}}],
              "flat": [{"id": "shadow", "essence": "shadowstuff"}],
              "powers": [{"recipe": "mi-ring-protection-1"}],
              "binding": {"quality_index": 3, "level": 2, "perks": {"potency": 0}},
              "curse": null, "known": {"intent": true, "curse": false, "how": "made"},
              "uses": {}, "made_day": 41}

**Ids and choices only; never a computed number** (the forge's read-live rule): every price,
mote, caster level, capacity and modifier is worked out here on read, from the property
table (`effectspec.properties()`, lane A) and the essence documents (lane D), so a corrected
document corrects every item that carries it. Before the revamp the enchanter wrote a NEW
record that dropped the forged build — no pieces, no `strikes_as`, no `weapon` field — so
`Actor.weapon` never found it (plan §1, measured on master e028885).

**One door for the readers.** `forge_items.build(record)` merges `layer(record)` into the
build it already returns (specs, riders, strikes_as), so the attack scope, the armour row,
`_item_riders` and the DR traits see the layer without a second reader. A record with no
layer builds exactly as before.

**Capacity** (owner, round 4 Q1, replacing the plan's Superior +8 / Flawless +9 / +10 cap):
an item holds floor(the binder's Enchanter level / 2) worth of enhancement-equivalent bonus,
**with no +10 ceiling** (Enchanter 20 holds +10, Enchanter 30 holds +15), and the smith's
quality adds a little on top: +1 per quality step above Superior, +1 per Capacity perk. The
book's other limit, "+1 to +5" enhancement (CRB magic weapons and armour), is KEPT: the
owner's ruling lifted the +10 total and said nothing of it, the plan (§3) keeps the book's
frame, and above +5 the room goes to properties — a +5 sword with +10 of abilities is what
an Enchanter 30's capacity means. So is "a weapon (armour) with a special ability must also
have at least a +1 enhancement bonus" (CRB).

**Prices are the book's**, computed: arms (total bonus)² × 2,000 gp, armour and shields
× 1,000, plus gold-priced abilities at their printed gold (outside the bonus and outside
capacity, plan §6.3); an upgrade costs the difference ("the same as if the item was not
magical, less the value of the original item", CRB p. 553); making costs half; motes are the
making cost ÷ 100, rounded up (owner Q9: 1 mote = 100 gp); 8 hours per 1,000 gp of the
increment, minimum 8, halved when hurried (CRB, magic item creation).

**Rings and wondrous items** carry no enhancement. Their capacity is spent by the same
budget, read through the book's own exchange rate: a power counts as the plus a weapon would
carry at its price, ceil(sqrt(price ÷ 2,000)) — a ring of protection +3 (18,000 gp) is +3,
a cloak of resistance +5 (25,000 gp) is +4, a belt of giant strength +6 (36,000 gp) is +5.
That is a reading (the book prices wondrous items in gold and has no bonus equivalent) and is
reported as one; the alternative, counting each scaled property's ladder step, would make a
+10 competence trinket (10,000 gp) cost more room than a +5 ring (50,000 gp).

**Curses** are lane F's record (`curses.roll`), opaque here. `layer` asks
`curses.documents(curse, layer)` when that module exists, and applies the change it returns
(`suppress`, `replace`, `add`, see `_apply_curse`); the card's view (`believed=True`) never
does. The curse's id never appears in anything this module returns.
"""
from __future__ import annotations

import copy
import math

from . import effectspec

SCHEMA = 1

# --- the book's numbers, each named once -----------------------------------------------------

# "+1 to +5" (CRB magic weapons / magic armor). Kept: see the docstring.
MAX_ENHANCEMENT = 5
# The creator's caster level for arms and armour is "three times the enhancement bonus"
# (CRB, magic weapons: "the higher of the two caster level requirements must be met").
CL_PER_ENHANCEMENT = 3
WEAPON_GP_PER_SQUARE = 2000
ARMOUR_GP_PER_SQUARE = 1000
MAKING_FRACTION = 0.5
# Several powers on one item (CRB, magic item creation, "Multiple Different Abilities" and
# "Adding New Abilities"): on a slotted item each added power costs 50% more; a slotless
# item pays the most costly in full, the next at 75%, every other at half (plan §6.4).
SLOTTED_EXTRA = 1.5
SLOTLESS_STEPS = (1.0, 0.75, 0.5)
HOURS_PER_1000_GP = 8
MIN_HOURS = 8
HOURS_PER_DAY = 8
# DC 5 + caster level; +5 per prerequisite not met; +5 to work in half the time (CRB).
DC_BASE = 5
DC_PER_MISSING = 5
DC_HURRY = 5
# Detect magic's aura strength by caster level (CRB detect magic): faint 5th or lower,
# moderate 6th-11th, strong 12th-20th, overwhelming 21st and up.
AURA_BANDS = ((5, "faint"), (11, "moderate"), (20, "strong"))
OVERWHELMING = "overwhelming"
# Cold iron: "adding any magical enhancements to a cold iron weapon increases its price by
# 2,000 gp. This increase is applied the first time the item is enhanced, not once per
# ability added" (CRB, special materials). A WEAPON's, and its main material's ("the most
# prevalent"). The catalogue's cold iron carries no `enchant_surcharge_gp`, so the book's
# number stands here until lane D (or World Bible) puts it on the material; a material's
# own field wins when it has one. Noqual's 5,000 IS on its document (`enchant_surcharge_gp`,
# "any magic item incorporating noqual") and is read from there, for any piece.
WEAPON_MAIN_SURCHARGE_GP = {"cold-iron": 2000}

# --- the owner's numbers (round 4; "use the proposed numbers, tune in play") ------------------

GP_PER_MOTE = 100
CAPACITY_LEVELS_PER_BONUS = 2         # floor(Enchanter level / 2)
CAPACITY_PER_QUALITY_STEP = 1         # each step above Superior (proposed)
CAPACITY_PER_PERK = 1                 # each Capacity perk
SUPERIOR = 3                          # the quality index that is masterwork (forge §4.4)
# Wondrous capacity read through the weapon table (docstring): the plus a weapon would carry
# at this price.
WONDROUS_EQUIVALENT_GP = WEAPON_GP_PER_SQUARE
# House top-ups on an essence (plan §6.7): bonuses × the forge's quality ladder × (1 + 5% per
# potency pick); drawbacks softened by the same steps, mirror image around Sound, never
# below half (proposed).
POTENCY_PER_PICK = 0.05
DRAWBACK_FLOOR = 0.5

ARMS = ("weapon", "armour", "shield")
_LISTS = ("specs", "riders", "wielded", "worn", "strikes_as", "raises", "powers", "tags")


# --- reading the record ----------------------------------------------------------------------

def _empty() -> dict:
    return {"schema": SCHEMA, "enhancement": 0, "properties": [], "flat": [], "powers": [],
            "binding": {}, "curse": None, "known": {}, "uses": {}, "made_day": None}


def magic_of(record) -> dict:
    """The record's layer, every field defaulted; never the record's own dict."""
    raw = record.get("magic") if isinstance(record, dict) else getattr(record, "magic", None)
    out = _empty()
    if isinstance(raw, dict):
        for k, v in raw.items():
            out[k] = copy.deepcopy(v)
    out["enhancement"] = int(out.get("enhancement") or 0)
    for k in ("properties", "flat", "powers"):
        out[k] = [dict(e) for e in out.get(k) or () if isinstance(e, dict)]
    for k in ("binding", "known", "uses"):
        out[k] = dict(out.get(k) or {})
    return out


def has_layer(record) -> bool:
    """Whether the record carries any magic: an enhancement, a property, a power or a
    curse. An empty `magic: {}` is no layer."""
    raw = record.get("magic") if isinstance(record, dict) else getattr(record, "magic", None)
    if not isinstance(raw, dict) or not raw:
        return False
    m = magic_of(record)
    return bool(m["enhancement"] or m["properties"] or m["flat"] or m["powers"] or m["curse"])


def vessel_kind(record) -> str:
    """"weapon", "armour", "shield", "ring" or "wondrous": what the book prices it as."""
    rec = record if isinstance(record, dict) else {}
    gear = str(rec.get("gear") or "").strip().lower()
    if gear in ARMS or gear in ("ring", "wondrous"):
        return gear
    if rec.get("weapon"):
        return "weapon"
    if rec.get("armour"):
        from . import armour as armour_mod

        kind, _ = armour_mod.key_for(str(rec["armour"]))
        return kind or "armour"
    if str(rec.get("slot") or "").strip().lower() == "ring":
        return "ring"
    return "wondrous"


def quality_index(record) -> int:
    """The vessel's quality on the forge's ladder (0 Crude ... 4 Flawless, 5 Flawless +1).
    A record with none says only whether it is masterwork: Superior (3) if so, Sound (1)
    if not — the room above Superior is 0 either way."""
    rec = record if isinstance(record, dict) else {}
    if rec.get("quality_index") is not None:
        try:
            return int(rec["quality_index"])
        except (TypeError, ValueError):
            pass
    return SUPERIOR if rec.get("masterwork") else 1


def _is_masterwork(record) -> bool:
    rec = record if isinstance(record, dict) else {}
    return bool(rec.get("masterwork")) or quality_index(rec) >= SUPERIOR


def _base_key(record) -> str:
    rec = record if isinstance(record, dict) else {}
    return str(rec.get("base") or rec.get("weapon") or rec.get("armour") or "")


# --- recipes (catalogue wondrous items), through whichever door exists -----------------------

def recipe(recipe_id: str) -> dict | None:
    """A catalogue item as a recipe: lane D's `materials.recipe` once it exists, the old
    catalogue (`magicitem.get`) until then. None when neither knows it."""
    rid = str(recipe_id or "").strip().lower()
    if not rid:
        return None
    try:
        from . import materials as _materials

        fn = getattr(_materials, "recipe", None)
        if callable(fn):
            got = fn(rid)
            if got:
                return dict(got)
    except Exception:  # noqa: BLE001 - a missing lane is not a crash
        pass
    try:
        from . import magicitem

        return magicitem.get(rid).as_dict()
    except (KeyError, Exception):  # noqa: BLE001
        return None


def _recipe_spell_groups(r: dict) -> list[list[str]]:
    groups = r.get("spells")
    if isinstance(groups, list) and groups:
        return [[str(s) for s in (g if isinstance(g, list) else [g])] for g in groups]
    return [[str(r["spell"])]] if r.get("spell") else []


# --- what each entry is worth -----------------------------------------------------------------

def _prop(entry: dict) -> dict | None:
    return effectspec.property(str(entry.get("id") or ""))


def _bonus_of(entry: dict) -> int | None:
    choice = entry.get("choice") or {}
    return int(choice["bonus"]) if isinstance(choice, dict) and choice.get("bonus") is not None \
        else None


def _equivalent_of_gp(gp: int) -> int:
    """The plus a weapon would carry at this price: ceil(sqrt(gp / 2,000))."""
    if gp <= 0:
        return 0
    return int(math.ceil(math.sqrt(gp / WONDROUS_EQUIVALENT_GP) - 1e-9))


def _entry_gp(entry: dict) -> int:
    """A gold-priced entry's printed gold (flat abilities, scaled properties)."""
    prop = _prop(entry)
    if prop is None:
        return 0
    if prop.get("gp") is not None:
        return int(prop["gp"])
    if prop.get("scaled"):
        try:
            return int(effectspec.price_of(prop, _bonus_of(entry))["gp"])
        except (ValueError, KeyError, TypeError):
            return 0
    return 0


def _plus_of(entry: dict) -> int:
    prop = _prop(entry)
    return int(prop.get("plus") or 0) if prop else 0


def total_bonus(magic: dict) -> int:
    """Arms and armour: the enhancement plus each ability's bonus equivalent (the number
    the squared price is taken of). Gold-priced abilities are outside it."""
    return int(magic.get("enhancement") or 0) + sum(_plus_of(e) for e in magic["properties"])


def _wondrous_powers_gp(magic: dict) -> list[int]:
    out = [_entry_gp(e) for e in magic["properties"] + magic["flat"]]
    for p in magic["powers"]:
        r = recipe(str(p.get("recipe") or "")) or {}
        out.append(int(r.get("price_gp") or 0))
    return out


def used(magic: dict, gear: str) -> int:
    """How much of an item's capacity its layer takes."""
    if gear in ARMS:
        return total_bonus(magic)
    return sum(_equivalent_of_gp(gp) for gp in _wondrous_powers_gp(magic))


def market_price(magic: dict, gear: str, slot: str = "") -> int:
    """The book's market price of the whole layer (never the vessel's own value: "the
    masterwork cost does not influence the base price", CRB)."""
    if gear in ARMS:
        per = WEAPON_GP_PER_SQUARE if gear == "weapon" else ARMOUR_GP_PER_SQUARE
        flat = sum(_entry_gp(e) for e in magic["flat"])
        return total_bonus(magic) ** 2 * per + flat
    prices = sorted((gp for gp in _wondrous_powers_gp(magic) if gp > 0), reverse=True)
    if not prices:
        return 0
    if str(slot or "").strip().lower() in ("", "slotless", "none"):
        return int(sum(gp * SLOTLESS_STEPS[min(i, len(SLOTLESS_STEPS) - 1)]
                       for i, gp in enumerate(prices)))
    return int(prices[0] + sum(gp * SLOTTED_EXTRA for gp in prices[1:]))


def caster_level(magic: dict, gear: str) -> int:
    """The ITEM's caster level: the highest of 3 × the enhancement and each ability's
    printed CL (CRB), a recipe's own. 0 for no magic."""
    cls = [CL_PER_ENHANCEMENT * int(magic.get("enhancement") or 0)] if gear in ARMS else []
    for e in magic["properties"] + magic["flat"]:
        prop = _prop(e)
        if prop and prop.get("cl") is not None:
            cls.append(int(prop["cl"]))
    for p in magic["powers"]:
        r = recipe(str(p.get("recipe") or "")) or {}
        if r.get("caster_level") is not None:
            cls.append(int(r["caster_level"]))
    return max(cls or [0])


def creator_level(magic: dict, gear: str) -> int:
    """The level the book asks of the CREATOR: for arms and armour the item's caster level
    (the higher of the two requirements); a scaled power's "at least N times the bonus"
    (ring of protection: three times); spell storing's "caster level 12th"."""
    need = caster_level(magic, gear) if gear in ARMS else 0
    for e in magic["properties"] + magic["flat"]:
        prop = _prop(e) or {}
        req = (prop.get("requires") or {}).get("creator_caster_level")
        if req:
            need = max(need, int(req))
        per = (prop.get("scaled") or {}).get("creator_cl_per_bonus")
        if per and _bonus_of(e) is not None:
            need = max(need, int(per) * int(_bonus_of(e)))
        if gear not in ARMS and prop.get("cl") is not None and not per:
            need = max(need, int(prop["cl"]))
    for p in magic["powers"]:
        r = recipe(str(p.get("recipe") or "")) or {}
        if r.get("caster_level") is not None:
            need = max(need, int(r["caster_level"]))
    return need


def aura(cl: int) -> str | None:
    if cl <= 0:
        return None
    for top, word in AURA_BANDS:
        if cl <= top:
            return word
    return OVERWHELMING


# --- capacity ---------------------------------------------------------------------------------

def _perk_count(perks, name: str = "capacity") -> int:
    if isinstance(perks, dict):
        return max(0, int(perks.get(name, 0) or 0))
    try:
        return max(0, int(perks or 0))
    except (TypeError, ValueError):
        return 0


def capacity(record, *, binder_level: int | None = None, binder_perks=None) -> dict:
    """What this vessel holds in this binder's hands (owner, round 4 Q1).

    `binder_level` and `binder_perks` (an int, or the perk dict with `capacity`) default to
    the record's last binding. Arms and armour must be masterwork first ("only a masterwork
    weapon can become a magic weapon", CRB); rings and wondrous items need not be
    (`magicitem.VESSEL_RULES`, kept).

    {"bonus": 5, "used": 2, "left": 3, "cap": None, "level": 6, "from_level": 3,
     "from_quality": 1, "from_perks": 1, "masterwork": True,
     "why": "Enchanter 6 holds +3; Flawless adds +1; 1 Capacity perk adds +1: +5"}
    """
    rec = record if isinstance(record, dict) else {}
    m = magic_of(rec)
    gear = vessel_kind(rec)
    binding = m.get("binding") or {}
    level = int(binder_level if binder_level is not None else binding.get("level", 0) or 0)
    perks = _perk_count(binder_perks if binder_perks is not None else binding.get("perks"))
    q = quality_index(rec)
    took = used(m, gear)
    if gear in ARMS and not _is_masterwork(rec):
        from .worldclass import quality_name

        return {"bonus": 0, "used": took, "left": -took, "cap": None, "level": level,
                "from_level": 0, "from_quality": 0, "from_perks": 0, "masterwork": False,
                "why": (f"{quality_name(q)} is not masterwork: only a Superior or better "
                        f"{gear} can carry magic.")}
    from_level = max(0, level) // CAPACITY_LEVELS_PER_BONUS
    from_quality = max(0, q - SUPERIOR) * CAPACITY_PER_QUALITY_STEP
    from_perks = perks * CAPACITY_PER_PERK
    bonus = from_level + from_quality + from_perks
    why = [f"Enchanter {level} holds +{from_level}"]
    if from_quality:
        from .worldclass import quality_name

        why.append(f"{quality_name(q)} adds +{from_quality}")
    if from_perks:
        why.append(f"{perks} Capacity perk{'s' if perks != 1 else ''} add"
                   f"{'s' if perks == 1 else ''} +{from_perks}")
    return {"bonus": bonus, "used": took, "left": bonus - took, "cap": None, "level": level,
            "from_level": from_level, "from_quality": from_quality, "from_perks": from_perks,
            "masterwork": _is_masterwork(rec),
            "why": "; ".join(why) + (f": +{bonus}" if len(why) > 1 else "")}


# --- merging a working onto a layer -----------------------------------------------------------

def _clean_entry(e: dict) -> dict:
    out = {"id": str(e.get("id") or "").strip().lower(),
           "essence": (str(e["essence"]) if e.get("essence") else None),
           "choice": (copy.deepcopy(e["choice"]) if isinstance(e.get("choice"), dict)
                      and e["choice"] else None)}
    return out


def _split_adds(adds: dict) -> tuple[int, list[dict], list[dict], list[dict]]:
    """(enhancement steps, plus- or scaled-priced entries, gold-priced entries, recipe
    powers). A property is filed by the table, not by which list the caller put it in:
    shadow is gold-priced wherever it was sent."""
    adds = dict(adds or {})
    enh = int(adds.get("enhancement") or 0)
    props, flat = [], []
    for e in list(adds.get("properties") or ()) + list(adds.get("flat") or ()):
        if not isinstance(e, dict):
            continue
        entry = _clean_entry(e)
        prop = _prop(entry)
        (flat if prop is not None and prop.get("gp") is not None else props).append(entry)
    powers = []
    for p in adds.get("powers") or ():
        if isinstance(p, dict) and p.get("recipe"):
            powers.append({"recipe": str(p["recipe"]).strip().lower(),
                           "essence": (str(p["essence"]) if p.get("essence") else None)})
        elif isinstance(p, str) and p:
            powers.append({"recipe": p.strip().lower(), "essence": None})
    return enh, props, flat, powers


def _merge(m: dict, adds: dict) -> dict:
    enh, props, flat, powers = _split_adds(adds)
    out = copy.deepcopy(m)
    out["enhancement"] = int(out.get("enhancement") or 0) + enh
    out["properties"] = list(out["properties"]) + props
    out["flat"] = list(out["flat"]) + flat
    out["powers"] = list(out["powers"]) + powers
    return out


def _same(a: dict, b: dict) -> bool:
    return a.get("id") == b.get("id") and (a.get("choice") or None) == (b.get("choice") or None)


# --- refusals ---------------------------------------------------------------------------------

def _weapon_row(record) -> dict | None:
    from . import weapons as weapons_mod

    key = weapons_mod.key_for(_base_key(record)) if _base_key(record) else ""
    if not key or not weapons_mod.has(key):
        return None
    return dict(weapons_mod.get(key), id=key)


def _requires_problems(prop: dict, record, gear: str) -> list[str]:
    """The vessel restrictions (a refusal: a keen club is not a thing). The creator
    clauses are DC terms, never refusals (owner Q4)."""
    req = prop.get("requires") or {}
    name = prop.get("name") or prop.get("id")
    if gear != "weapon":
        return []
    w = _weapon_row(record)
    if w is None:
        return []
    from . import weapons as weapons_mod

    out = []
    melee = str(w.get("category") or "") == "melee"
    launcher = weapons_mod.is_launcher(w["id"])
    thrown = bool(w.get("range_ft")) and not launcher
    types = set(w.get("types") or [w.get("type")])
    wname = str(w.get("name") or w["id"])
    if req.get("melee") and not melee:
        out.append(f"{name} goes only on a melee weapon; a {wname} is not one.")
    if req.get("ranged") and str(w.get("category") or "") != "ranged":
        out.append(f"{name} goes only on a ranged weapon; a {wname} is not one.")
    if req.get("thrown") and not thrown:
        out.append(f"{name} goes only on a thrown weapon; a {wname} cannot be thrown.")
    if req.get("launcher") is False and launcher:
        out.append(f"{name} cannot go on a bow or crossbow itself, only on its ammunition.")
    want = req.get("damage_types_any")
    if want and not (types & set(want)):
        out.append(f"{name} needs a {' or '.join(want)} weapon; a {wname} deals "
                   f"{', '.join(sorted(t for t in types if t)) or 'no such damage'}.")
    return out


def _entry_problems(entry: dict, record, gear: str, have: list[dict]) -> list[str]:
    prop = _prop(entry)
    if prop is None:
        return [f"There is no magic property {entry.get('id')!r}."]
    name = prop.get("name") or prop["id"]
    out = []
    if gear not in (prop.get("gear") or ()):
        out.append(f"{name} goes on {' or '.join(prop.get('gear') or ())}, not a {gear}.")
    slots = prop.get("slots")
    slot = str((record or {}).get("slot") or "").strip().lower()
    if slots and slot and slot not in slots:
        out.append(f"{name} is worn on the {' or '.join(slots)}, not the {slot}.")
    out.extend(_requires_problems(prop, record, gear))
    out.extend(effectspec.choice_problems(prop, entry.get("choice")))
    if any(_same(entry, h) for h in have):
        out.append(f"The item already carries {name}"
                   f"{' against that foe' if entry.get('choice') else ''}.")
    return out


# --- the plan of a working --------------------------------------------------------------------

def _spell_name(spell_id: str) -> str:
    from . import spells as spell_mod

    try:
        return spell_mod.get(spell_id).name
    except Exception:  # noqa: BLE001 - a corpus that lost a spell still names it
        return spell_id.replace("-", " ")


def _spell_groups(entry: dict) -> list[list[str]]:
    prop = _prop(entry) or {}
    return [[str(s) for s in g] for g in prop.get("spells") or () if g]


def plan(record, adds: dict, *, binder: dict, hurry: bool = False, helps=()) -> dict:
    """Everything about a working before any roll (contracts §3.2): refusals in words,
    the DC with each term, the price, the motes, the time, and what essences it needs.

    `adds` = {"enhancement": steps to ADD (an upgrade +1 -> +2 is 1),
              "properties": [{"id", "choice", "essence"}], "flat": [...],
              "powers": [{"recipe"}]}.
    `binder` = {"level": int, "perks": {"capacity": n, ...}, "knows": spell ids,
                "holds": spell ids carried in a potion or scroll, "classes": class ids}.
    `helps`: DC terms the bench works out (affinity, catalyst), each {"why", "dc"} with a
    negative dc; added as given (the bench owns their sizes and cap).
    """
    rec = record if isinstance(record, dict) else {}
    gear = vessel_kind(rec)
    before = magic_of(rec)
    enh, props, flat, powers = _split_adds(adds)
    after = _merge(before, adds)
    binder = dict(binder or {})
    level = int(binder.get("level", 0) or 0)
    problems: list[str] = []
    notes: list[str] = []

    if not (enh or props or flat or powers):
        problems.append("Nothing to bind: add an enhancement, a property or a power.")
    if enh < 0:
        problems.append("A binding adds; it never lowers an enhancement.")
    if gear in ARMS and not _is_masterwork(rec):
        from .worldclass import quality_name

        problems.append(f"Only a masterwork {gear} can carry magic (CRB): this one is "
                        f"{quality_name(quality_index(rec))}, and Superior is masterwork.")
    if enh and gear not in ARMS:
        problems.append(f"A {gear} takes no enhancement bonus; bind it a power instead.")
    if gear in ARMS and after["enhancement"] > MAX_ENHANCEMENT:
        problems.append(f"+{MAX_ENHANCEMENT} is the book's highest enhancement bonus; this "
                        f"would make it +{after['enhancement']}. Put the rest into "
                        f"properties.")
    have = list(before["properties"]) + list(before["flat"])
    for entry in props + flat:
        problems.extend(_entry_problems(entry, rec, gear, have))
        have.append(entry)
    for p in powers:
        if recipe(p["recipe"]) is None:
            problems.append(f"There is no recipe {p['recipe']!r}.")
    if gear in ARMS and (after["properties"] or after["flat"]) and after["enhancement"] < 1:
        problems.append(f"A {gear} with a special ability must also have at least a +1 "
                        f"enhancement bonus (CRB): bind the +1 first, or with it.")
    cap = capacity(rec, binder_level=level, binder_perks=binder.get("perks"))
    took = used(after, gear)
    if gear not in ARMS or cap["masterwork"]:
        if took > cap["bonus"]:
            problems.append(f"{cap['why']}. This working would make it +{took}.")
    cap = dict(cap, used=took, left=cap["bonus"] - took)

    # The DC (CRB: 5 + caster level; +5 per prerequisite unmet, never a refusal, owner Q4).
    cl = caster_level(after, gear)
    terms = [{"why": f"5 + the item's caster level {cl}", "dc": DC_BASE + cl}]
    knows = {str(s) for s in binder.get("knows") or ()}
    holds = {str(s) for s in binder.get("holds") or ()}
    missing_spells: list[list[str]] = []
    for entry in props + flat:
        for group in _spell_groups(entry):
            if not set(group) & (knows | holds):
                missing_spells.append(group)
    for p in powers:
        for group in _recipe_spell_groups(recipe(p["recipe"]) or {}):
            if not set(group) & (knows | holds):
                missing_spells.append(group)
    for group in missing_spells:
        terms.append({"why": f"no {' or '.join(_spell_name(s) for s in group)} known or "
                             f"carried", "dc": DC_PER_MISSING})
    need = creator_level(after, gear)
    if level < need:
        terms.append({"why": f"Enchanter {level} is below the caster level {need} it asks",
                      "dc": DC_PER_MISSING})
    classes = {str(c).strip().lower() for c in binder.get("classes") or ()}
    for entry in props + flat:
        prop = _prop(entry) or {}
        req = prop.get("requires") or {}
        if req.get("creator_class") and str(req["creator_class"]).lower() not in classes:
            terms.append({"why": f"{prop.get('name')} asks a {req['creator_class']}'s hand",
                          "dc": DC_PER_MISSING})
        if req.get("creator_alignment"):
            notes.append(f"{prop.get('name')} asks a {req['creator_alignment']} maker; no "
                         f"alignment is tracked yet, so it is waived (owner, round 4 Q7).")
    if hurry:
        terms.append({"why": "hurried: half the time", "dc": DC_HURRY})
    for h in helps or ():
        if isinstance(h, dict) and h.get("why"):
            terms.append({"why": str(h["why"]), "dc": int(h.get("dc", 0) or 0)})

    price = _price(rec, before, after, gear, hurry=hurry)
    new_grants = [e["id"] for e in props + flat]
    return {
        "ok": not problems, "problems": problems, "notes": notes,
        "gear": gear,
        "total_bonus": total_bonus(after) if gear in ARMS else took,
        "caster_level": cl, "creator_level": need,
        "dc_terms": terms, "dc": sum(t["dc"] for t in terms),
        "price": price, "capacity": cap,
        "needs": {"grants": new_grants, "powers": [p["recipe"] for p in powers],
                  "enhancement": ({"from": before["enhancement"], "to": after["enhancement"]}
                                  if enh else None),
                  "motes": price["motes"]},
        "aura": aura(cl),
    }


def _surcharges(record, before: dict, gear: str) -> list[dict]:
    """The material's price for taking magic at all, once: the first time it is enhanced
    (CRB cold iron; noqual's "any magic item incorporating noqual"). An item that already
    carries a layer has paid."""
    if has_layer({"magic": before}):
        return []
    from . import forge_items, item_tags

    out: list[dict] = []
    main = item_tags.main_material(record)
    for mid in item_tags.materials_in(record):
        doc = forge_items.material(mid) or {}
        gp = int(doc.get("enchant_surcharge_gp") or 0)
        why = "any magic item incorporating it"
        if not gp and gear == "weapon" and mid == main:
            gp = int(WEAPON_MAIN_SURCHARGE_GP.get(mid, 0))
            why = "a weapon's first enhancement"
        if gp:
            name = str(doc.get("name") or mid.replace("-", " "))
            out.append({"why": f"{name}: {why}, +{gp:,} gp", "gp": gp,
                        "motes": _motes(gp)})
    return out


def _motes(gp: int) -> int:
    return int(math.ceil(max(0, gp) / GP_PER_MOTE - 1e-9))


def _price(record, before: dict, after: dict, gear: str, *, hurry: bool) -> dict:
    slot = str((record or {}).get("slot") or "")
    was = market_price(before, gear, slot)
    now = market_price(after, gear, slot)
    increment = max(0, now - was)
    making = int(increment * MAKING_FRACTION)
    extra = _surcharges(record, before, gear)
    making_total = making + sum(s["gp"] for s in extra)
    thousands = int(math.ceil(increment / 1000 - 1e-9))
    hours = max(MIN_HOURS, thousands * HOURS_PER_1000_GP)
    if hurry:
        hours = int(math.ceil(hours / 2))
    return {"market_gp": increment, "item_market_gp": now, "was_gp": was,
            "making_gp": making_total, "motes": _motes(making_total),
            "surcharges": [{"why": s["why"], "motes": s["motes"]} for s in extra],
            "hours": hours, "days": int(math.ceil(hours / HOURS_PER_DAY))}


# --- writing ----------------------------------------------------------------------------------

def write(record, adds: dict, *, binding: dict, curse: dict | None = None,
          day: int | None = None) -> dict:
    """A new record with the working laid on (pure; the argument is never touched).

    Refuses (ValueError, named) an entry the table does not know or a choice it would not
    bind — a saved record must never carry a property no reader can build. Capacity and
    the rest are `plan`'s; the bench asks it first. `curse` is lane F's record, laid on
    when the binding was flawed; an earlier curse stays until something lifts it.
    """
    rec = copy.deepcopy(dict(record or {}))
    before = magic_of(rec)
    _, props, flat, powers = _split_adds(adds)
    bad: list[str] = []
    for entry in props + flat:
        prop = _prop(entry)
        if prop is None:
            bad.append(f"There is no magic property {entry.get('id')!r}.")
            continue
        bad.extend(effectspec.choice_problems(prop, entry.get("choice")))
    for p in powers:
        if recipe(p["recipe"]) is None:
            bad.append(f"There is no recipe {p['recipe']!r}.")
    if bad:
        raise ValueError("; ".join(bad))
    m = _merge(before, adds)
    m["schema"] = SCHEMA
    m["binding"] = copy.deepcopy(dict(binding or {}))
    if curse is not None:
        m["curse"] = copy.deepcopy(curse)
    prior = before.get("known") or {}
    m["known"] = {"intent": True,
                  "curse": bool(prior.get("curse")) and curse is None,
                  "how": str(prior.get("how") or "made")}
    if m.get("made_day") is None and day is not None:
        m["made_day"] = int(day)
    if day is not None:
        m["worked_day"] = int(day)
    rec["magic"] = m
    return rec


def strip(record) -> tuple[dict, dict]:
    """(the record without its layer, the layer) — Unbind (plan §13): the smith's item
    stays, the enchanter's work comes off whole, its curse with it."""
    rec = copy.deepcopy(dict(record or {}))
    layer_doc = rec.pop("magic", None)
    return rec, (layer_doc if isinstance(layer_doc, dict) else {})


# --- the layer as the readers see it ----------------------------------------------------------

def _essence_house(essence_id) -> list[dict]:
    """An essence's house top-ups (lane D's `house` list), or [] while lane D's door does
    not serve them."""
    if not essence_id:
        return []
    try:
        from . import materials as _materials
    except ImportError:
        return []
    fn = getattr(_materials, "essences", None)
    doc = None
    try:
        doc = (fn() or {}).get(str(essence_id)) if callable(fn) else None
    except Exception:  # noqa: BLE001
        doc = None
    return [dict(e) for e in (doc or {}).get("house") or () if isinstance(e, dict)]


def _house_scaled(eff: dict, binding: dict) -> dict | None:
    """A house top-up at the binding's quality, rounded toward zero once (the forge's
    rule); None when it rounds to nothing. Book numbers never come here."""
    from . import forge_items

    try:
        amount = float(eff.get("amount"))
    except (TypeError, ValueError):
        return dict(eff, house=True)
    q = forge_items.quality_multiplier(int(binding.get("quality_index", 1) or 0))
    potency = _perk_count(binding.get("perks"), "potency")
    if effectspec.is_drawback(eff):
        mult = max(DRAWBACK_FLOOR, 2.0 - q)
    else:
        mult = q * (1 + POTENCY_PER_PICK * potency)
    value = int(math.trunc(round(amount * mult, 6)))
    if not value:
        return None
    return dict(eff, amount=value, house=True)


def _bucket(out: dict, doc: dict, uses: dict, key: str) -> None:
    kind = str(doc.get("type") or "")
    trigger = str(doc.get("trigger") or "")
    if kind == "strikes_as":
        out["strikes_as"].append(str(doc.get("target") or ""))
    elif kind == "item_power":
        n = sum(1 for p in out["powers"] if p["source"] == doc.get("source"))
        pkey = key if not n else f"{key}#{n + 1}"
        out["powers"].append({"key": pkey, "source": doc.get("source"),
                              "spec": doc, "uses": doc.get("uses"),
                              "uses_count": doc.get("uses_count"),
                              "used": int(uses.get(pkey, 0) or 0)})
    elif trigger == "wielded":
        out["wielded"].append(doc)
    elif trigger == "worn":
        out["worn"].append(doc)
    elif trigger:
        out["riders"].append(doc)
    else:
        if kind == "enhancement_raise":
            out["raises"].append(doc)
        out["specs"].append(doc)


def layer(record, *, believed: bool = False) -> dict:
    """What the layer does, every number computed now (contracts §3.2).

    {"specs", "riders", "wielded", "worn", "strikes_as", "raises", "powers", "tags",
     "enhancement", "aura", "schools", "caster_level", "total_bonus", "price_gp",
     "capacity", "known", "problems"}

    `specs` are standing modifiers for the funnel (the +N as `combat_mod` attack and damage,
    typed enhancement, on a weapon; on armour or a shield an armour-typed AC bonus that
    `forge_items.armour_row` folds into the suit's bonus, as the book's "enhancement bonus to
    armour" is); `riders` fire on a hit or crit; `wielded`/`worn` are lane C's standing
    effects; `raises` are bane's `enhancement_raise` documents (also in `specs`), which
    `strikes_as_against` reads; `tags` the `property.<id>` tags a `reads_tag` reader asks.
    Each document is stamped `origin: item:<id>` and keeps `source: property:<id>`.

    `believed=True` is the item as its owner believes it (the card): no curse applied.
    """
    rec = record if isinstance(record, dict) else {}
    m = magic_of(rec)
    gear = vessel_kind(rec)
    item_id = str(rec.get("id") or rec.get("name") or "item").strip()
    origin = f"item:{item_id}"
    out: dict = {k: [] for k in _LISTS}
    problems: list[str] = []
    uses = m.get("uses") or {}

    enh = int(m["enhancement"] or 0)
    if enh and gear == "weapon":
        for target in ("attack", "damage"):
            out["specs"].append({"type": "combat_mod", "target": target, "amount": enh,
                                 "bonus_type": "enhancement", "origin": origin,
                                 "source": "enhancement", "book": True})
        out["strikes_as"].extend(effectspec.strikes_as_for_enhancement(enh))
    elif enh and gear in ("armour", "shield"):
        out["specs"].append({"type": "combat_mod", "target": "ac", "amount": enh,
                             "bonus_type": "armour", "origin": origin,
                             "source": "enhancement", "book": True})

    for entry in m["properties"] + m["flat"]:
        prop = _prop(entry)
        if prop is None:
            problems.append(f"no magic property {entry.get('id')!r}")
            continue
        try:
            docs = effectspec.bind(prop, entry.get("choice"))
        except (ValueError, KeyError) as exc:
            problems.append(str(exc))
            continue
        out["tags"].append(effectspec.property_tag(prop["id"]))
        for d in docs:
            _bucket(out, dict(d, origin=origin), uses, prop["id"])
        for eff in _essence_house(entry.get("essence")):
            scaled = _house_scaled(eff, m.get("binding") or {})
            if scaled is not None:
                _bucket(out, dict(scaled, origin=origin,
                                  source=f"essence:{entry.get('essence')}"), uses, prop["id"])
    for p in m["powers"]:
        rid = str(p.get("recipe") or "")
        r = recipe(rid)
        if r is None:
            problems.append(f"no recipe {rid!r}")
            continue
        for d in r.get("effects") or ():
            if isinstance(d, dict):
                _bucket(out, dict(copy.deepcopy(d), origin=origin, source=f"recipe:{rid}"),
                        uses, rid)
        for eff in _essence_house(p.get("essence")):
            scaled = _house_scaled(eff, m.get("binding") or {})
            if scaled is not None:
                _bucket(out, dict(scaled, origin=origin, source=f"essence:{p.get('essence')}"),
                        uses, rid)

    out["enhancement"] = enh if gear in ARMS else 0
    if not believed and m.get("curse"):
        out = _apply_curse(out, m["curse"])
    out["strikes_as"] = sorted({s for s in out["strikes_as"] if s})
    cl = caster_level(m, gear)
    schools: list[str] = []
    for entry in m["properties"] + m["flat"]:
        for s in ((_prop(entry) or {}).get("aura") or {}).get("school") or ():
            if s not in schools:
                schools.append(s)
    out.update({
        "schema": SCHEMA, "gear": gear,
        "aura": aura(cl), "schools": schools, "caster_level": cl,
        "total_bonus": total_bonus(m) if gear in ARMS else used(m, gear),
        "price_gp": market_price(m, gear, str(rec.get("slot") or "")),
        "capacity": capacity(rec),
        "known": dict(m.get("known") or {}),
        "problems": problems,
    })
    return out


def _apply_curse(out: dict, curse) -> dict:
    """Lane F's seam. `curses.documents(curse, layer)` returns how the layer changes:
    `{"suppress": True}` (a delusion: the layer applies nothing), `{"replace": {list: [...]}}`
    (an opposite or different effect), `{"add": {list: [...]}}` (a drawback's documents).
    Until rules/curses.py exists a curse changes nothing here, and says so nowhere the page
    can read."""
    try:
        from . import curses as _curses
    except ImportError:
        return out
    fn = getattr(_curses, "documents", None)
    if not callable(fn):
        return out
    change = fn(curse, copy.deepcopy(out)) or {}
    if change.get("suppress"):
        out = {k: [] for k in _LISTS}
        out["enhancement"] = 0
    for key, items in (change.get("replace") or {}).items():
        if key in _LISTS:
            out[key] = list(items or ())
    for key, items in (change.get("add") or {}).items():
        if key in _LISTS:
            out[key] = list(out.get(key) or ()) + list(items or ())
    if "enhancement" in change:
        out["enhancement"] = int(change["enhancement"] or 0)
    return out


# --- what lane C asks at the moment of a blow --------------------------------------------------

def raised_enhancement(lay: dict, holds) -> int:
    """The weapon's enhancement as raised against THIS target: its own plus every
    `enhancement_raise` (bane) whose `when` the caller's `holds(when) -> bool` answers.
    The caller is the engine, with `_when_holds` and the roll's context: bane's +2 is "+2
    better against the designated foe" (CRB), and against anybody else it is nothing."""
    total = int((lay or {}).get("enhancement") or 0)
    for doc in (lay or {}).get("raises") or ():
        if holds(doc.get("when")):
            total += int(doc.get("amount", 0) or 0)
    return total


def strikes_as_against(lay: dict, holds) -> tuple[str, ...]:
    """The DR traits a blow carries against this target: the layer's own (holy's `good`,
    the printed enhancement's) and the glossary's thresholds at the enhancement as raised
    (owner Q8: bane's +2 counts toward +3/+4/+5)."""
    own = set((lay or {}).get("strikes_as") or ())
    own.update(effectspec.strikes_as_for_enhancement(raised_enhancement(lay, holds)))
    return tuple(sorted(own))


def record_specs(record) -> list[dict]:
    """A NON-forged record's standing modifiers with its layer: an old record's flat
    `specs` plus the layer's. A forged record's come through `forge_items.build`; a ring or
    a cloak has no build, so lane C's `_record_specs` asks this."""
    rec = record if isinstance(record, dict) else {}
    out = [dict(s) for s in rec.get("specs") or () if isinstance(s, dict)]
    if has_layer(rec):
        out += [dict(s) for s in layer(rec)["specs"]]
    return out


__all__ = ["layer", "plan", "write", "strip", "capacity", "magic_of", "has_layer",
           "vessel_kind", "quality_index", "market_price", "total_bonus", "used",
           "caster_level", "creator_level", "aura", "recipe", "raised_enhancement",
           "strikes_as_against", "record_specs", "MAX_ENHANCEMENT", "SCHEMA"]
