"""The second enchanting mode: Pathfinder's own magic item creation.

`rules/enchanter.py` is the house craft — essences, foci, a circle chalked on a floor.
This is the book: **Craft Magic Arms and Armor**, **Craft Wondrous Item** and **Forge
Ring**, with the +1 ladder, named properties priced as bonus equivalents, the masterwork
requirement, and the book's own costs and times. Both modes end in the same place — a
standing effect list on an item — and the play layer picks between them as two tabs of
one bench, which is why this module carries the same public surface as a track module
(`CraftError`, `Chain`, `chain_from_body`, `preview`, `Result`, `check_terms`).

**Two house rules, both deliberate, both stated rather than hidden.**

1. *The spell prerequisite is satisfiable with a potion.* The book requires the creator
   to know the prerequisite spell. In a solo game the party is one person, and a fighter
   who wants a flaming sword can never qualify — the requirement does not gate power, it
   deletes the whole feature for most characters. So: **a potion holding that spell,
   consumed in the making, stands in for knowing it.** The alchemist track brews those
   (`holds_spell` on the stock entry); knowing the spell still works, and is free.

2. *Permanency is not required.* Several book prerequisites read "…and permanency", a
   5th-level-caster service a solo campaign cannot farm. Dropped outright rather than
   fudged, and the drop is documented in `docs/enchanting.md` so it reads as a decision
   and not as an oversight.

Everything else is the book's: enhancement +1 to +5, at least +1 before any property,
enhancement + properties never past +10, market price N² × 2,000 gp for weapons and
N² × 1,000 gp for armour, crafting at half market price, 8 hours per 1,000 gp, and
**DC 5 + caster level**.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from . import effectspec
from . import worldclass as wc
from .registry import read_folder

MODE_ID = "magic-item"

# What the tab is called and what it promises. Read by `rules/benches.modes_for`, which
# falls back to a title-cased id — "Magic Item" would name the mode after its slug and
# say nothing about how it differs from the circle beside it.
MODE_NAME = "By the book"
MODE_BLURB = ("Pathfinder's own item creation: the +1 to +5 ladder, named properties "
              "priced as bonus equivalents, masterwork arms and armour, and gold and "
              "days instead of essences.")

# The mode is a face of the Enchanter track; a working here advances the same world
# class, and `output.craft` says "enchanter" so the sheet files both modes' results in
# one place.
TRACK_ID = "enchanter"

# The book's caps, named rather than inlined so the refusal sentences and the arithmetic
# cannot disagree about what the rule is.
MAX_ENHANCEMENT = 5
MAX_TOTAL_BONUS = 10

# Market price per point of total bonus equivalent, squared. Core Rulebook, magic arms
# and armour tables: a +1 weapon is 2,000 gp, a +5 is 50,000 (25 × 2,000).
WEAPON_GP_PER_PLUS_SQUARED = 2000
ARMOUR_GP_PER_PLUS_SQUARED = 1000

# "Creating a magic weapon takes 1 day for each 1,000 gp in the price" — expressed in
# hours here, because the bench works in hours and a day of crafting is 8 of them.
HOURS_PER_1000_GP = 8

# Crafting costs half the market price; the other half is the labour that is being
# supplied instead of paid for.
CRAFT_COST_FRACTION = 0.5

# Which vessel kinds each catalogue kind may be worked into, and whether the book asks
# for masterwork. Jewelry and wondrous items do **not** require it: a ring blank is a
# ring blank, and the book never asks a crafter to commission a masterwork one. That
# asymmetry is real and is called out in the docs so it reads as the rule rather than a
# gap in the checks.
VESSEL_RULES = {
    "weapon_property": {"vessels": ("weapon",), "masterwork": True},
    "armour_property": {"vessels": ("armour", "shield"), "masterwork": True},
    "wondrous": {"vessels": ("jewelry", "wondrous", "ring", "amulet", "cloak", "belt",
                             "headband", "bracers", "boots", "slotless"),
                 "masterwork": False},
}


class CraftError(ValueError):
    """The working cannot be described at all. A working that is merely illegal comes
    back as `problems` on the preview, so it can be shown and refused rather than
    raising — the contract `rules/crafting.py` sets and both enchanting modes keep."""


@dataclass
class Item:
    """One catalogue entry: a priced property, or a whole wondrous item."""
    id: str
    name: str
    kind: str = "weapon_property"   # weapon_property | armour_property | wondrous
    tier: str = "common"
    plus: int = 0                   # bonus equivalent, for properties
    slot: str | None = None         # wondrous: a rules/tables.py SLOTS key, or None
    spell: str = ""                 # the prerequisite spell, as a content/spells id
    caster_level: int = 1
    price_gp: int = 0               # wondrous: the book's market price
    obtain: str = "bought"
    text: str = ""
    effects: list = field(default_factory=list)
    drawbacks: list = field(default_factory=list)

    @property
    def rank(self) -> int:
        return wc.tier_rank(self.tier)

    def as_dict(self) -> dict:
        return {"id": self.id, "name": self.name, "kind": self.kind, "tier": self.tier,
                "rank": self.rank, "plus": self.plus, "slot": self.slot,
                "spell": self.spell, "caster_level": self.caster_level,
                "price_gp": self.price_gp, "obtain": self.obtain, "text": self.text,
                "effects": self.effects, "drawbacks": self.drawbacks}


def from_dict(d: dict) -> Item:
    return Item(
        id=d["id"], name=d.get("name", d["id"]),
        kind=d.get("kind", "weapon_property"), tier=d.get("tier", "common"),
        plus=int(d.get("plus", 0) or 0), slot=d.get("slot"),
        spell=str(d.get("spell") or ""), caster_level=int(d.get("caster_level", 1) or 1),
        price_gp=int(d.get("price_gp", 0) or 0), obtain=d.get("obtain", "bought"),
        text=d.get("text", ""),
        effects=list(d.get("effects") or []), drawbacks=list(d.get("drawbacks") or []))


_CATALOGUE: dict[str, Item] | None = None


def catalogue() -> dict[str, Item]:
    """Every property and wondrous item, shipped plus homebrew.

    **Only `magic-items.json`**, not the whole materials folder — and that is the one
    place this module deliberately parts company with `rules/enchanter.py`. The essence
    shelf is shared between five crafts on purpose; this catalogue is a priced rules
    table, and a blacksmith's quenching brine appearing in it as a weapon property
    would be nonsense rather than generosity. Homebrew layers over shipped entry by
    entry, the `worldclass.tracks()` rule, so a corrected shipped property is never
    shadowed by a stale user copy.
    """
    global _CATALOGUE
    if _CATALOGUE is None:
        from django.conf import settings

        raw: dict[str, dict] = {}
        shipped = Path(settings.BASE_DIR) / "content" / "materials" / "magic-items.json"
        if shipped.is_file():
            data = json.loads(shipped.read_text(encoding="utf-8"))
            for entry in data.get("materials", []):
                if entry.get("id"):
                    raw[str(entry["id"]).strip().lower()] = dict(entry)
        user = Path(settings.CAMPAIGN_DIR).parent / "homebrew" / "magic-items"
        for key, entry in read_folder(user, "materials").items():
            raw.setdefault(key, {}).update(entry)
        _CATALOGUE = {k: from_dict({**v, "id": k}) for k, v in raw.items()}
    return _CATALOGUE


def get(item_id: str) -> Item:
    found = catalogue().get((item_id or "").strip().lower())
    if found is None:
        raise KeyError(f"no magic item entry {item_id!r}")
    return found


def worn_specs(name: str) -> list[dict]:
    """The authored effects of a worn magic item, found by its printed name.

    Stage 4 of docs/states-effects-tells.md. A slot has always held a plain string —
    "Ring of Protection +1" — and the string did nothing: the sheet page itself
    admitted "a ring of protection here will not move your AC until magic items are
    modelled". The catalogue has carried the item's effects the whole time; this is
    the lookup that joins the two, so a worn slot becomes a standing effect with no
    clock — an infinite effect granted by wearing.

    Matched case-insensitively on the entry's own name. An unknown name answers []
    and stays the inert string it always was — a guessed effect would be worse.

    Searched fresh each call rather than through a name index built once: the
    catalogue itself is cached and layered with homebrew, and a second cache over it
    is exactly the stale-derived-cache trap CLAUDE.md records.
    """
    want = " ".join(str(name or "").split()).strip().lower()
    if not want:
        return []
    for entry in catalogue().values():
        if entry.name.strip().lower() == want:
            return [dict(spec) for spec in entry.effects if isinstance(spec, dict)]
    return []


# --- pricing ------------------------------------------------------------------------------

def market_price(kind: str, total_bonus: int, wondrous_gp: int = 0) -> int:
    """The book's market price for a finished item.

    Weapons and armour price on the *square* of the total bonus equivalent, which is why
    a +5 flaming sword (+6 total) costs 72,000 gp and not 12,000: the squaring is the
    whole reason a high-end item is a campaign goal rather than a shopping trip. A
    wondrous item carries its own printed price instead.
    """
    if kind == "wondrous":
        return int(wondrous_gp)
    per = ARMOUR_GP_PER_PLUS_SQUARED if kind == "armour_property" \
        else WEAPON_GP_PER_PLUS_SQUARED
    return int(total_bonus * total_bonus * per)


def craft_cost(price: int) -> int:
    """Half the market price, rounded **down** — costs round down, per the house rule
    inherited from `rules/crafting.py`. In the player's favour by at most a copper, and
    consistent with every other cost in the app."""
    return int(price * CRAFT_COST_FRACTION)


def craft_hours(price: int) -> int:
    """8 hours per 1,000 gp of market price, rounded **up** to a whole working day's
    worth — time is a cost, so it never rounds in the crafter's favour, and a 400 gp
    trinket still takes a day rather than three hours of a day nobody can subdivide."""
    if price <= 0:
        return 0
    thousands = (price + 999) // 1000
    return int(thousands * HOURS_PER_1000_GP)


# --- the chain ----------------------------------------------------------------------------

@dataclass
class Chain:
    """One book-faithful working.

    `methods` exists so the two modes share a shape and a dispatcher can treat them
    alike; this mode has no ritual verbs of its own, and an empty list is normal.
    `enhancement` is the +N being laid on, `material_ids` the catalogue properties or
    the single wondrous item, and `item` the vessel's name.
    """
    methods: list[str] = field(default_factory=list)
    material_ids: list[str] = field(default_factory=list)
    item: str = ""
    name: str = ""
    enhancement: int = 0
    # {stock id: how many}: potions consumed to stand in for spells known.
    stock_used: dict[str, int] = field(default_factory=dict)

    @property
    def stages(self) -> int:
        # A working is the enhancement plus each property; that is what the player is
        # holding in their head at once, and what the mastery award should count.
        return max(1, (1 if self.enhancement else 0) + len(self.material_ids))


def chain_from_body(body: dict) -> Chain:
    """A Chain from whatever the page posted, tolerantly.

    Deliberately forgiving about shape — `materials` may arrive as a list or as one
    string, `enhancement` as an int or the string "3" or "+3" — because the alternative
    is a 500 on a form that looks fine, and the validation that matters happens in
    `preview` where the answer can be shown to the player. Unknown keys are ignored
    rather than refused: the spine posts one body to whichever mode is active, and a
    field meant for the essence mode must not blow this one up.
    """
    body = dict(body or {})
    raw = body.get("materials", body.get("material_ids", body.get("properties", [])))
    if isinstance(raw, str):
        raw = [p.strip() for p in raw.split(",") if p.strip()]
    methods = body.get("methods", [])
    if isinstance(methods, str):
        methods = [p.strip() for p in methods.split(",") if p.strip()]

    plus = body.get("enhancement", body.get("plus", 0))
    try:
        plus = int(str(plus).strip().lstrip("+") or 0)
    except (TypeError, ValueError):
        plus = 0

    stock = body.get("stock", body.get("stock_used", {})) or {}
    if not isinstance(stock, dict):
        # A list of ids means one of each, which is what a checkbox group posts.
        stock = {str(s): 1 for s in stock}

    return Chain(
        methods=[str(m).strip().lower() for m in methods],
        material_ids=[str(m).strip().lower() for m in raw],
        item=str(body.get("item", body.get("vessel", "")) or "").strip(),
        name=str(body.get("name", "") or "").strip(),
        enhancement=plus,
        stock_used={str(k): int(v) for k, v in stock.items()},
    )


@dataclass
class Result:
    """What this working would produce — nothing rolled.

    `effects` is renderable prose and `specs` the executable list, the split the shared
    bench spine expects: a card shows strings, the engine runs specs, and neither has to
    re-derive the other.
    """
    name: str
    item: str = ""
    tier: str = "common"
    rank: int = 1
    stages: int = 1
    dc: int = 0
    risky: bool = False
    problems: list[str] = field(default_factory=list)
    effects: list[str] = field(default_factory=list)
    specs: list[dict] = field(default_factory=list)
    consumes: dict[str, int] = field(default_factory=dict)
    output: dict | None = None
    bonus: int = 0
    terms: list[dict] = field(default_factory=list)
    chance: int = 0
    # The book's own numbers, carried as data so the bench can show them and a later
    # economy can charge them.
    price_gp: int = 0
    cost_gp: int = 0
    hours: int = 0
    caster_level: int = 1
    enhancement: int = 0
    properties: list[str] = field(default_factory=list)
    total_bonus: int = 0
    notes: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "name": self.name, "item": self.item, "tier": self.tier, "rank": self.rank,
            "stages": self.stages, "dc": self.dc, "risky": self.risky,
            "problems": self.problems, "effects": self.effects, "specs": self.specs,
            "consumes": self.consumes, "output": self.output, "bonus": self.bonus,
            "terms": self.terms, "chance": self.chance, "price_gp": self.price_gp,
            "cost_gp": self.cost_gp, "hours": self.hours,
            "caster_level": self.caster_level, "enhancement": self.enhancement,
            "properties": self.properties, "total_bonus": self.total_bonus,
            "notes": self.notes,
        }


def check_terms(actor, level: int) -> list[dict]:
    """d20 + track level + half character level + Intelligence, itemised.

    The same shape and the same three terms as the essence mode, because it is the same
    enchanter doing the work with the same head. Itemised rather than summed for
    `rules/crafting.py`'s stated reason: "+9" says nothing, three named terms say which
    one to go and improve.
    """
    track_level = max(0, int(level or 0))
    char_level = max(1, int(getattr(actor, "level", 1) or 1)) if actor else 1
    intel = int(actor.ability_mod("int")) if actor is not None else 0
    return [
        {"label": f"Enchanter {track_level}", "value": track_level},
        {"label": f"half character level ({char_level})", "value": char_level // 2},
        {"label": "Intelligence", "value": intel},
    ]


def check_bonus(actor, level: int) -> int:
    return sum(t["value"] for t in check_terms(actor, level))


def _chance(dc: int, bonus: int, problems) -> int:
    if problems:
        return 0
    need = dc - bonus
    return max(5, min(95, int(round(100 * (21 - need) / 20))))


def _spell_name(spell_id: str) -> str:
    """The spell's printed name, for the refusal sentence.

    Falls back to the id with its hyphens opened out rather than raising: a refusal
    that names "flame blade" is still a useful sentence, and a preview that dies
    because one catalogue entry cites a spell the corpus lost is not.
    """
    from . import spells as spell_mod

    try:
        return spell_mod.get(spell_id).name
    except Exception:
        return spell_id.replace("-", " ")


def _holds(entry) -> str:
    """The spell a stock entry holds, or "".

    The alchemist track's contract: a brewed spell-potion carries `holds_spell` (and a
    `caster_level`) on its stock dict. Read off whatever shape the caller has — a dict
    from a saved satchel or an object from the crafting bench — because both reach here.
    """
    if isinstance(entry, dict):
        return str(entry.get("holds_spell") or "")
    return str(getattr(entry, "holds_spell", "") or "")


def _potion_for(spell_id: str, stock: dict) -> str | None:
    """The id of a carried potion holding this spell, or None."""
    for sid, entry in (stock or {}).items():
        if _holds(entry) == spell_id:
            count = entry.get("count", 1) if isinstance(entry, dict) \
                else getattr(entry, "count", 1)
            if int(count or 0) > 0:
                return sid
    return None


def _knows(actor, spell_id: str) -> bool:
    """Whether the crafter can reach the spell themselves.

    Read-only through `rules/casting.knows`, and defensive: a character with no caster
    data, a spell id the corpus does not have, or a bare Actor stub must all answer
    "no" rather than raising inside a preview.
    """
    if actor is None or not spell_id:
        return False
    try:
        from . import casting, spells as spell_mod

        return bool(casting.knows(actor, spell_mod.get(spell_id)))
    except Exception:
        return False


def preview(level: int, chain: Chain, stock: dict | None = None, actor=None,
            item: dict | None = None) -> Result:
    """What this working would make, what it costs, and everything wrong with it.

    Never raises for a working that is merely illegal — an enhancement past +5, a
    property with no enhancement under it, a non-masterwork vessel, an unsatisfied spell
    prerequisite all come back as `problems`. `item` describes the vessel:
    `{"masterwork": bool, "kind": "weapon" | "armour" | "shield" | "jewelry" | ...,
    "weapon": "<weapons.json id>", "armour": "<tables.ARMOUR key>", "slot": "<SLOTS key>"}`.
    """
    problems: list[str] = []
    notes: list[str] = []
    target = dict(item or {})
    kind = str(target.get("kind", "") or "").strip().lower()

    entries: list[Item] = []
    wanted: dict[str, int] = {}
    for mid in chain.material_ids:
        try:
            entries.append(get(mid))
            wanted[mid] = wanted.get(mid, 0) + 1
        except KeyError:
            problems.append(f"No such magic item property: {mid}.")

    wondrous = [e for e in entries if e.kind == "wondrous"]
    properties = [e for e in entries if e.kind != "wondrous"]
    enhancement = max(0, int(chain.enhancement or 0))

    # A wondrous item is a whole item, not a property laid on one: it never mixes with
    # an enhancement bonus or a weapon property, and one working makes one of them.
    if wondrous and (properties or enhancement):
        problems.append(
            "A wondrous item is made whole, not laid over an enhancement: "
            "make the ring or the sword, not both in one working.")
    if len(wondrous) > 1:
        problems.append("One wondrous item per working — "
                        f"this asks for {len(wondrous)}.")

    if not entries and not enhancement:
        problems.append("Nothing to make: choose an enhancement bonus, "
                        "a property, or a wondrous item.")

    # --- the +N ladder and the caps -------------------------------------------------
    property_bonus = sum(e.plus for e in properties)
    total_bonus = enhancement + property_bonus

    if enhancement > MAX_ENHANCEMENT:
        problems.append(
            f"An enhancement bonus stops at +{MAX_ENHANCEMENT}; this asks for "
            f"+{enhancement}. Spend the rest on properties.")
    if properties and enhancement < 1:
        # The book's own ordering rule, and the one people forget: properties are
        # priced as bonus equivalents *on top of* an enhancement bonus, so there has to
        # be one to be on top of.
        named = ", ".join(e.name.lower() for e in properties[:3])
        problems.append(
            f"A weapon or armour must be at least +1 before {named} can be added: "
            f"named properties are priced as bonus equivalents on top of an "
            f"enhancement bonus, and there is none here.")
    if total_bonus > MAX_TOTAL_BONUS:
        problems.append(
            f"Enhancement and properties together may not pass "
            f"+{MAX_TOTAL_BONUS}: +{enhancement} and "
            f"{property_bonus} of properties is +{total_bonus}.")

    # --- the vessel ------------------------------------------------------------------
    working_kind = ("wondrous" if wondrous else
                    "armour_property" if any(e.kind == "armour_property"
                                             for e in properties)
                    else "weapon_property")
    if not entries and enhancement:
        # A bare +N: which ladder it is depends on what is on the anvil.
        working_kind = "armour_property" if kind in ("armour", "shield") \
            else "weapon_property"

    mixed = {e.kind for e in properties}
    if len(mixed) > 1:
        problems.append("Weapon properties and armour properties cannot share "
                        "a working — they go on different items.")

    rules = VESSEL_RULES[working_kind]
    if kind and kind not in rules["vessels"]:
        problems.append(
            f"A {working_kind.replace('_', ' ')} goes on "
            f"{' or '.join(rules['vessels'][:2])}, not on a {kind}.")
    if rules["masterwork"] and not target.get("masterwork"):
        problems.append(
            f"{chain.item or 'The item'} is not masterwork. Only a masterwork weapon "
            f"or suit of armour takes an enchantment — commission one from the smith "
            f"or the leatherworker first.")
    if not rules["masterwork"] and target.get("masterwork") is False:
        # Said rather than silently allowed, so the asymmetry reads as the rule.
        notes.append("Rings, amulets and wondrous items need no masterwork vessel — "
                     "the book asks for one on arms and armour only.")

    # --- the spell prerequisite, and the potion that stands in for it ----------------
    stock = dict(stock or {})
    consumes: dict[str, int] = {}
    caster_level = max((e.caster_level for e in entries), default=1)

    for entry in entries:
        if not entry.spell:
            continue
        if _knows(actor, entry.spell):
            notes.append(f"{entry.name}: {_spell_name(entry.spell)} is known, "
                         f"so no potion is needed.")
            continue
        held = _potion_for(entry.spell, stock)
        if held:
            consumes[held] = consumes.get(held, 0) + 1
            notes.append(f"{entry.name}: a potion of "
                         f"{_spell_name(entry.spell)} is consumed in the making.")
            continue
        problems.append(
            f"{entry.name} needs {_spell_name(entry.spell)}, and you neither know it "
            f"nor carry a potion holding it. Brew or buy a potion of "
            f"{_spell_name(entry.spell)} and it will be consumed in the making.")

    # Permanency, dropped. Said out loud on every working that the book would have
    # asked it of, so the house rule is visible at the bench and not only in the docs.
    notes.append("House rule: the book's permanency prerequisites are not required "
                 "here — a solo game cannot farm a 5th-level caster.")

    # --- price, time, DC --------------------------------------------------------------
    wondrous_gp = wondrous[0].price_gp if wondrous else 0
    price = market_price(working_kind, total_bonus, wondrous_gp)
    cost = craft_cost(price)
    hours = craft_hours(price)
    # Craft Magic Arms and Armor / Craft Wondrous Item: "the DC is 5 + the caster level
    # of the item". The one number the whole book agrees on.
    dc = 5 + caster_level

    rank = max([e.rank for e in entries]
               + ([min(len(wc.TIERS), max(1, (total_bonus + 1) // 2))]
                  if total_bonus else []), default=1)
    tier = wc.TIERS[min(rank, len(wc.TIERS)) - 1]

    # --- what the finished item carries ----------------------------------------------
    specs: list[dict] = []
    for entry in entries:
        for spec in entry.effects:
            specs.append({**spec, "from": spec.get("from") or entry.name})
        for spec in entry.drawbacks:
            specs.append({**spec, "from": spec.get("from") or entry.name,
                          "drawback": True})
    if enhancement and working_kind == "weapon_property":
        specs.append({"type": "combat_mod", "amount": enhancement,
                      "bonus_type": "enhancement", "target": "attack",
                      "duration": {"unit": "permanent"}, "from": f"+{enhancement}"})
        specs.append({"type": "combat_mod", "amount": enhancement,
                      "bonus_type": "enhancement", "target": "damage",
                      "duration": {"unit": "permanent"}, "from": f"+{enhancement}"})
    elif enhancement:
        specs.append({"type": "combat_mod", "amount": enhancement,
                      "bonus_type": "enhancement", "target": "ac",
                      "duration": {"unit": "permanent"}, "from": f"+{enhancement}"})

    effects = [f"{s['from']}: {effectspec.render(s)}" if s.get("from")
               else effectspec.render(s) for s in specs]

    name = chain.name or _derived_name(chain, entries, enhancement)
    terms = check_terms(actor, level)
    bonus = sum(t["value"] for t in terms)

    slot = wondrous[0].slot if wondrous else (target.get("slot") or None)
    output = {
        "id": _slug(name), "name": name, "kind": "crafted", "craft": "enchanter",
        "tier": tier, "rank": rank, "count": 1,
        "effects": effects, "specs": specs,
        "from_materials": list(wanted),
        # True on the finished item either way: an enchanted ring is a masterwork ring
        # by the act of enchanting it, even though the book never demanded one going in.
        "masterwork": True,
        "wearable": working_kind != "weapon_property",
        "usable": working_kind == "weapon_property",
        "how": [],
        "slot": slot,
        "weapon": target.get("weapon") if working_kind == "weapon_property" else None,
        "armour": target.get("armour") if working_kind == "armour_property" else None,
        "enhancement": enhancement,
        "properties": [e.name for e in entries],
    }

    return Result(
        name=name, item=chain.item, tier=tier, rank=rank,
        stages=chain.stages, dc=dc,
        # The book's making is patient work in a workshop, not a hazard: nothing here
        # explodes. `risky` is carried because the spine reads it, and is honestly False.
        risky=False,
        problems=problems, effects=effects, specs=specs, consumes=consumes,
        output=output, bonus=bonus, terms=terms,
        chance=_chance(dc, bonus, problems),
        price_gp=price, cost_gp=cost, hours=hours, caster_level=caster_level,
        enhancement=enhancement, properties=[e.name for e in entries],
        total_bonus=total_bonus, notes=notes,
    )


def _slug(name: str) -> str:
    out = "".join(c if c.isalnum() else "-" for c in str(name).lower()).strip("-")
    while "--" in out:
        out = out.replace("--", "-")
    return out


def _derived_name(chain: Chain, entries: list[Item], enhancement: int) -> str:
    """"Flaming Longsword +1", the way the book prints it: properties in front, the
    enhancement bonus at the back. A wondrous item is already named, so it keeps its
    own name rather than being described as a property of a vessel."""
    wondrous = [e for e in entries if e.kind == "wondrous"]
    if wondrous:
        return wondrous[0].name
    item = (chain.item or "item").strip()
    item = item[:1].upper() + item[1:]
    words = " ".join(dict.fromkeys(e.name for e in entries if e.kind != "wondrous"))
    name = f"{words} {item}".strip() if words else item
    return f"{name} +{enhancement}" if enhancement else name


# --- what the bench shows -----------------------------------------------------------------

# One glyph per catalogue kind, from the Enchanter's reserved pool. Herbalism's
# 🌿 🍄 🦴 ☠️ are never reused.
#
# 🧿 and 📿 also stand for the essence mode's `treatment` and `catalyst` kinds, and that
# overlap is deliberate rather than an oversight: the reserved pool is ten glyphs and
# enchanting has eleven kinds across its two tabs. Reuse *within* one craft is legible —
# 🧿 is a warded thing in both places, 📿 a strung-together working — where reuse across
# two crafts would make one shelf look like another. The two dicts are separate
# namespaces, no single list ever shows both, and `benches.glyphs()` reads the tracks'
# maps rather than the modes', so the cross-craft assertion is unaffected either way.
KIND_GLYPH: dict[str, str] = {
    "weapon_property": "🪄",
    "armour_property": "🧿",
    "wondrous": "📿",
}

# This mode has no ritual stations — the book's making is one long patient session at a
# workbench, not a chain of verbs — so there is no `method_help` here. Said explicitly
# because an empty dict and a forgotten one look identical from the outside.
STATIONS: dict[str, dict] = {}


def by_kind(kind: str) -> list[Item]:
    return [i for _, i in sorted(catalogue().items()) if i.kind == kind]


def properties_for(vessel_kind: str) -> list[Item]:
    """Everything that can legally go on this kind of vessel — what the bench lists
    once the player has said what is on the anvil."""
    vessel_kind = (vessel_kind or "").strip().lower()
    return [i for _, i in sorted(catalogue().items())
            if vessel_kind in VESSEL_RULES.get(i.kind, {}).get("vessels", ())]


__all__ = ["CRAFT_COST_FRACTION", "Chain", "CraftError", "HOURS_PER_1000_GP", "Item",
           "KIND_GLYPH", "MAX_ENHANCEMENT", "MAX_TOTAL_BONUS", "MODE_ID", "Result",
           "STATIONS", "TRACK_ID", "VESSEL_RULES", "by_kind", "catalogue",
           "chain_from_body", "check_bonus", "check_terms", "craft_cost", "craft_hours",
           "from_dict", "get", "market_price", "preview", "properties_for"]
