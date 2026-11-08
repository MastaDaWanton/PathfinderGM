"""The magic-item catalogue: Pathfinder's priced properties and wondrous items.

`rules/enchanter.py` is the house craft — essences, foci, a circle chalked on a floor —
and is where enchanting is done. This module is the catalogue reader the sheet, the
equipment panel, the fence, the shops and the loot ask (`catalogue`, `worn_specs`,
`market_price`, `recipe_named`, `finished`): every entry's effects are its CHECKED
documents, a wondrous row's `book` (lane D) or a weapon or armour row's property in lane
A's table, never the old `effects` (see `_book_effects`).

It was also the old /craft/ page's second enchanting tab, "By the book" (Craft Magic Arms
and Armor, Craft Wondrous Item and Forge Ring as a chain: the +1 ladder, the masterwork
requirement, half-price costs, DC 5 + caster level). The UI wave retired that tab on
2026-10-06 (docs/enchanting-ui-plan.md §2) and its chain, preview and routes were deleted
on 2026-11-08 (audit finding #20); nothing could reach them.
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from pathlib import Path

from . import effectspec
from . import worldclass as wc
from .registry import read_folder

# A finished catalogue item is filed under the Enchanter track (`finished`'s Stock), the
# same place the circle files what it binds.
TRACK_ID = "enchanter"

# Market price per point of total bonus equivalent, squared. Core Rulebook, magic arms
# and armour tables: a +1 weapon is 2,000 gp, a +5 is 50,000 (25 × 2,000).
WEAPON_GP_PER_PLUS_SQUARED = 2000
ARMOUR_GP_PER_PLUS_SQUARED = 1000


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
    # The book's creator level where it differs from the item's caster level (a ring of
    # protection is CL 5 and asks a maker of three times its bonus, lane D's fix).
    creator_level: int | None = None

    @property
    def rank(self) -> int:
        return wc.tier_rank(self.tier)

    def as_dict(self) -> dict:
        return {"id": self.id, "name": self.name, "kind": self.kind, "tier": self.tier,
                "rank": self.rank, "plus": self.plus, "slot": self.slot,
                "spell": self.spell, "caster_level": self.caster_level,
                "creator_level": self.creator_level,
                "price_gp": self.price_gp, "obtain": self.obtain, "text": self.text,
                "effects": self.effects, "drawbacks": self.drawbacks}


def _book_effects(d: dict) -> list:
    """What the entry does, from the checked fields (enchanting lane D, the lead's note of
    2026-10-05): a wondrous row's `book` (its numbers read by hand from AoN), a weapon or
    armour row's property in lane A's table (`effectspec.from_alias`, bound with the choice
    its old id implies). The old row's `effects` only when neither exists.

    Measured before this: the Goggles of Minute Seeing gave +5 Perception (the old row)
    where the book gives +5 Disable Device, and that number was live on every worn pair;
    the old flaming row's fire was a `note` "on a hit" with no trigger, which no reader
    could fire."""
    if isinstance(d.get("book"), list) and d["book"]:
        return [dict(e) for e in d["book"] if isinstance(e, dict)]
    alias = effectspec.from_alias(str(d.get("id") or ""))
    if alias:
        pid, choice = alias
        try:
            return effectspec.bind(pid, choice or None)
        except (ValueError, KeyError):
            # Bane's old row never named its foe (`mi-bane` maps to {}): its fire would
            # land on every foe, the note-only bug. Nothing rather than that.
            return []
    return list(d.get("effects") or [])


def from_dict(d: dict) -> Item:
    spells = d.get("spells")
    first = ""
    if isinstance(spells, list) and spells and isinstance(spells[0], list) and spells[0]:
        first = str(spells[0][0])
    return Item(
        id=d["id"], name=d.get("name", d["id"]),
        kind=d.get("kind", "weapon_property"), tier=d.get("tier", "common"),
        plus=int(d.get("plus", 0) or 0), slot=d.get("slot"),
        spell=str(d.get("spell") or first or ""),
        caster_level=int(d.get("caster_level", 1) or 1),
        price_gp=int(d.get("price_gp", 0) or 0), obtain=d.get("obtain", "bought"),
        text=d.get("text", ""),
        effects=_book_effects(d), drawbacks=list(d.get("drawbacks") or []),
        creator_level=int(d.get("creator_level") or 0) or None)


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


# --- a finished catalogue item, as a shop sells it and a body drops it ------------------------
#
# The enchanter's bench makes a wondrous item by binding its recipe onto a vessel: the record
# is the vessel with `magic.powers: [{"recipe": <id>}]` (`magic_layer.write`), and every
# reader — the worn walk, `use_item`'s powers, the card, the fence — reads that layer. A
# finished item bought at a counter or taken off a body is the same record, so it works the
# way the bench's own does and no second shape exists to drift from it. Before 2026-10-30 no
# counter sold one (docs/own-items.md: "No market sells catalogue wondrous items") and the
# loot dropped every printed one (bestiary `_assemble_kit` filtered `table == "magic item"`:
# 2,039 entries in 567 blocks, 231 of them a cloak of resistance +1).

# What a body's printed gear names an item that the catalogue spells another way: the
# Bestiary's "(type i)" against the catalogue's "(type I)" is case and is folded anyway;
# these are the words, not the case.
_PRINTED_ALIASES = {
    "pearl of power (1st)": "pearl of power (1st level)",
    "pearl of power (2nd)": "pearl of power (2nd level)",
    "pearl of power (3rd)": "pearl of power (3rd level)",
    "luckstone": "stone of good luck (luckstone)",
    "stone of good luck": "stone of good luck (luckstone)",
}


def recipe_named(printed: str) -> str | None:
    """The recipe id of the wondrous item a printed name means, or None.

    By the catalogue's own name, case and spacing folded, through the few printed spellings
    in `_PRINTED_ALIASES`; never a fuzzy match — a guessed item would be a fact nobody wrote.
    Retired rows are no recipe and answer None (`materials.recipes`)."""
    from . import materials

    want = " ".join(str(printed or "").split()).strip().lower()
    want = _PRINTED_ALIASES.get(want, want)
    if not want:
        return None
    # Indexed under the recipe door's own key (the files' paths, sizes and mtimes), so a
    # homebrew row added mid-session is seen and no stale index outlives its source;
    # `recipes()` deep-copies the whole catalogue per call, too dear per spawned body.
    key = materials._recipe_key()
    if _NAMES.get("key") != key:
        _NAMES.clear()
        _NAMES["key"] = key
        _NAMES["index"] = {" ".join(str(row.get("name") or "").split()).lower(): rid
                           for rid, row in materials.recipes().items()}
    return _NAMES["index"].get(want)


_NAMES: dict = {}


def finished(recipe_id: str, *, how: str = "bought"):
    """A finished wondrous item as a shelf entry (`crafting.Stock`), the record the bench
    writes: its vessel (worn in the row's slot, or slotless) with the recipe bound as its
    one power. `how` is "bought" — a counter's item is known for what it is and known to be
    clean — or "found": nothing about it is known (lane F's convention, `known = {}`), and
    it is identified the way any found item is. Raises KeyError for no recipe."""
    from . import magic_layer, materials
    from .crafting import Stock

    row = materials.recipe(recipe_id)
    if row is None:
        raise KeyError(f"no wondrous item {recipe_id!r}")
    vessel = str(row.get("vessel") or "slotless")
    slot = vessel if vessel not in ("slotless", "rod") else None
    # The binder's level the layer's capacity reads (`magic_layer.capacity`): enough to hold
    # the item, at the book's exchange rate — what the bench would have needed to make it.
    plus = max(1, math.ceil(math.sqrt(float(row.get("price_gp") or 0) / 2000.0)))
    rec = magic_layer.write({"id": str(row["id"]), "name": str(row["name"]), "slot": slot},
                            {"powers": [{"recipe": str(row["id"])}]},
                            binding={"quality_index": magic_layer.SUPERIOR,
                                     "level": 2 * plus, "perks": {}})
    known = ({"intent": True, "curse": True, "how": "bought"} if how == "bought" else {})
    rec["magic"]["known"] = known
    return Stock(base=str(row["name"]), count=1, craft=TRACK_ID, kind="crafted",
                 slot=slot, wearable=bool(slot), masterwork=False,
                 tier=str(row.get("tier") or "common"), magic=rec["magic"])


__all__ = ["Item", "TRACK_ID", "catalogue", "finished", "from_dict", "get", "market_price",
           "recipe_named", "worn_specs"]
