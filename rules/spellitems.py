"""Scrolls and wands: spell items made at the enchanting circle and used through the item
cast door (docs/item-creation-feats-study.md §3.2, §3.3, options A; owner ruling
2026-11-22: "build the magic items like wands and scrolls and constructs into the
enchanting world class").

**What one is.** A `crafting.Stock` whose magic layer holds one *spell power*: a power
entry naming the spell itself (`{"spell", "caster_level", "level", "item_kind", ...}`)
rather than a catalogue recipe, which `magic_layer.layer` reads into the same
`item_power` document every recipe power becomes. So the Equipment row's Use button, the
engine's `use_item {item, power}` and the cast door (`Engine._use_power` ->
`_op_cast` with `partial["item_cast"]`: the item's caster level and DC, no slot) serve a
scroll and a wand exactly as they serve a ring's daily spell. No second store and no
second door: a scroll's one reading is a `once` use, taken off the stack; a wand's 50
charges are the layer's use count (`magic.uses`), kept across days (`charges` is not a
per-day limit, `Actor.reset_item_uses`).

**One vocabulary.** The layer carries `item.scroll` / `item.wand` and the book's
activation method, `activation.completion` (spell completion: a scroll) or
`activation.trigger` (spell trigger: a wand). Every reader asks those, never a name.

**Which spells.** Any spell the cast door can cast, at the same fidelity as casting it:
its run parts run and its told parts reach the narrator as tells, exactly as a slot cast
(`spells.casting_plan`). This is NOT alchemy's every-part rule (`formulae._executable_all`):
a scroll is a cast, not a bottled effect (study §3.2, Q4). The owner is being asked about
the parallel potion rule; scrolls are built this way and the report says so.

**The book's numbers** (CRB, Magic Items; legacy.aonprd.com/coreRulebook/magicItems/
scrolls.html and wands.html, read 2026-11-22):
- price: scroll 25 gp x spell level x caster level, wand 750 gp x spell level x caster
  level, a 0-level spell counting as half; materials are half the price;
- caster level: the minimum to cast the spell (`formulae.min_caster_level`);
- a wand holds a spell of 4th level or lower and has 50 charges;
- arcane and divine: "Arcane spellcasters ... can only use scrolls containing arcane
  spells, and divine spellcasters ... can only use scrolls containing divine spells".
"""
from __future__ import annotations

from . import words as english

TRACK_ID = "enchanter"

# The two kinds, every number the book's. `how` is the Stock's own verb list (the shelf's
# question "can this be used, and how"); `uses` is the layer power's limit word.
KINDS: dict[str, dict] = {
    "scroll": {"noun": "Scroll", "tag": "item.scroll", "activation": "completion",
               "gp_per_level": 25, "uses": "once", "charges": 1, "max_level": 9,
               "how": "read"},
    "wand": {"noun": "Wand", "tag": "item.wand", "activation": "trigger",
             "gp_per_level": 750, "uses": "charges", "charges": 50, "max_level": 4,
             "how": "zap"},
}
ACTIVATION_TAG = "activation."

# Which lists are divine, for a scroll's tradition and its spell level. The arcane lists
# are `armour.ARCANE_LISTS`, the one place the app says which casting is arcane. The
# occult and alchemical lists are neither: a spell only on them takes the lowest level any
# list gives it.
DIVINE_LISTS = frozenset({"cleric", "druid", "paladin", "ranger", "oracle", "inquisitor",
                          "shaman", "warpriest", "antipaladin", "hunter"})


def kind_row(kind: str) -> dict:
    return KINDS[str(kind or "").strip().lower()]


def _spell(spell):
    from . import spells as spells_mod

    return spells_mod.get(spell) if isinstance(spell, str) else spell


def tradition_of(spell, maker=None) -> str:
    """"arcane" or "divine". A caster writes in their own tradition when the spell is on
    their list; otherwise a spell on the wizard's or sorcerer's list is arcane, one only on
    divine lists divine, and anything else arcane (the enchanter's circle is arcane work).
    So a cure light wounds scroll a cleric or a shop sells is divine, mage armour arcane."""
    from . import armour, casting

    sp = _spell(spell)
    lists = {str(k).lower() for k in (sp.lists or {})}
    if maker is not None and casting.is_caster(maker) and casting.on_class_list(maker, sp):
        return "arcane" if armour.is_arcane(maker) else "divine"
    if lists & {"wizard", "sorcerer", "sorcerer/wizard"}:
        return "arcane"
    if lists & DIVINE_LISTS:
        return "divine"
    return "arcane"


def spell_level(spell, tradition: str) -> int:
    """The level the scroll's spell is written at: the lowest a list of its tradition
    gives it (the book prices by "the level of the spell" for its scribe's class)."""
    from . import armour

    sp = _spell(spell)
    lists = {str(k).lower(): int(v) for k, v in (sp.lists or {}).items()}
    pool = armour.ARCANE_LISTS if tradition == "arcane" else DIVINE_LISTS
    own = [v for k, v in lists.items() if k in pool]
    return min(own or list(lists.values()) or [0])


def min_caster_level(spell, level: int) -> int:
    from . import formulae

    return formulae.min_caster_level(_spell(spell), level)


def price_gp(kind: str, level: int, cl: int) -> float:
    """The book's market price: gp a level x spell level x caster level, 0-level half."""
    n = 0.5 if int(level or 0) <= 0 else int(level)
    return float(kind_row(kind)["gp_per_level"] * n * max(1, int(cl or 1)))


def item_dc(level: int) -> int:
    """The item DC the cast door uses for every item power (CRB, Magic Items, Saving
    Throws: 10 + spell level + the minimum ability modifier to cast that level), the same
    `10 + level + level // 2` `Engine._use_power` writes for a ring's spell."""
    n = int(level or 0)
    return 10 + n + n // 2


def name_for(kind: str, spell, cl: int) -> str:
    """"Scroll of Mage Armor (CL 1)": the caster level in the name, so two scrolls of one
    spell at different levels never stack into one row that casts at the better one."""
    return f"{kind_row(kind)['noun']} of {_spell(spell).name} (CL {int(cl)})"


def power_entry(kind: str, spell, cl: int, *, level: int, tradition: str) -> dict:
    row = kind_row(kind)
    sp = _spell(spell)
    out = {"spell": sp.id, "caster_level": int(cl), "level": int(level),
           "dc": item_dc(level), "item_kind": kind, "activation": row["activation"],
           "tradition": tradition, "uses": row["uses"],
           "price_gp": price_gp(kind, level, cl)}
    if row["uses"] == "charges":
        out["uses_count"] = int(row["charges"])
    return out


def make(kind: str, spell, cl: int | None = None, *, maker=None, quality: int | None = None,
         how: str = "made", tradition: str | None = None):
    """A finished scroll or wand as a shelf entry. `how` is "made" or "bought" (known for
    what it is) or "found" (nothing known: deciphered at the circle's Identify first)."""
    from .crafting import Stock
    from . import formulae

    row = kind_row(kind)
    sp = _spell(spell)
    trad = tradition or tradition_of(sp, maker)
    level = spell_level(sp, trad)
    cl = int(cl or min_caster_level(sp, level))
    known = ({"intent": True, "curse": True, "how": how} if how in ("made", "bought")
             else {})
    magic = {"powers": [power_entry(kind, sp, cl, level=level, tradition=trad)],
             "known": known}
    return Stock(base=name_for(kind, sp, cl), count=1, craft=TRACK_ID, kind="crafted",
                 tier=formulae.TIER_BY_SPELL_LEVEL[min(max(level, 0), 3)],
                 how=[row["how"]], holds_spell=sp.id, caster_level=cl, quality=quality,
                 magic=magic)


def entry_of(stock) -> dict | None:
    """The spell power a scroll or wand carries, or None for anything else."""
    mag = stock.get("magic") if isinstance(stock, dict) else getattr(stock, "magic", None)
    for p in (mag or {}).get("powers") or ():
        if isinstance(p, dict) and p.get("spell") and p.get("item_kind") in KINDS:
            return p
    return None


def kind_of(stock) -> str | None:
    e = entry_of(stock)
    return str(e["item_kind"]) if e else None


def tags_of(entry: dict) -> list[str]:
    return [kind_row(entry["item_kind"])["tag"], ACTIVATION_TAG + str(entry["activation"])]


def card_line(entry: dict, used: int = 0) -> str:
    """The item card's words for its power: what it casts, at what caster level, and what
    is left of it."""
    from . import spells as spells_mod

    try:
        name = spells_mod.get(str(entry["spell"])).name
    except KeyError:
        name = str(entry["spell"])
    line = f"{name}, caster level {entry.get('caster_level')}"
    if entry.get("uses") == "charges":
        left = int(entry.get("uses_count") or 0) - int(used or 0)
        line += f"; {left} charge{'s' if left != 1 else ''} left"
    return line


def wand_max_level() -> int:
    return int(KINDS["wand"]["max_level"])


def a_name(kind: str, spell) -> str:
    return english.a(f"{kind} of {_spell(spell).name}")


__all__ = ["KINDS", "DIVINE_LISTS", "a_name", "card_line", "entry_of", "item_dc",
           "kind_of", "kind_row", "make", "min_caster_level", "name_for", "power_entry",
           "price_gp", "spell_level", "tags_of", "tradition_of", "wand_max_level"]


_WRITTEN: list[tuple[str, str, int]] | None = None


def written_levels() -> list[tuple[str, str, int]]:
    """(spell id, name, level as written) for every spell, by name; built once a process.
    The level is the default tradition's (`tradition_of` with no maker), which is what a
    non-caster's circle writes it at."""
    global _WRITTEN
    if _WRITTEN is None:
        from . import spells as spells_mod

        rows = []
        for sp in spells_mod.all_spells().values():
            rows.append((sp.id, sp.name, spell_level(sp, tradition_of(sp))))
        _WRITTEN = sorted(rows, key=lambda r: r[1].lower())
    return _WRITTEN


def options(actor, cap: int, kind: str) -> list[dict]:
    """The spells the circle offers to write at this cap, the ones the writer knows or
    carries first (they need no +5), each `{id, name, level, known}`."""
    from . import casting, spells as spells_mod

    known: set[str] = set()
    if casting.is_caster(actor):
        for sid in list(getattr(actor, "spellbook", None) or ()):
            known.add(str(sid))
    for st in (getattr(actor, "stock", None) or {}).values():
        if getattr(st, "holds_spell", None) and kind_of(st) != "wand":
            known.add(str(st.holds_spell))
    top = min(cap, wand_max_level()) if kind == "wand" else cap
    out = [{"id": sid, "name": name, "level": lvl, "known": sid in known}
           for sid, name, lvl in written_levels() if lvl <= top]
    # A list caster (a cleric) knows every spell on the list: asked of the casting rules.
    if casting.is_caster(actor) and not getattr(actor, "spellbook", None):
        for row in out:
            if not row["known"]:
                try:
                    row["known"] = casting.knows(actor, spells_mod.get(row["id"]))
                except KeyError:
                    pass
    out.sort(key=lambda r: (not r["known"], r["name"].lower()))
    return out


# What a magic counter sells (`goods.magic_item_goods`), as the alchemist sells the 44
# classic potions and no derived row (owner, 2026-10-07): a fixed list of the book's common
# scrolls and wands, each at its minimum caster level and book price, drawn under the
# market's rarity quota and the settlement's base value like every other magic item. The
# picks are the CRB's own examples and the spells a table reaches for first; ours, not a
# Paizo table.
SOLD: dict[str, tuple[str, ...]] = {
    "scroll": ("mage-armor", "magic-missile", "shield", "sleep", "grease", "feather-fall",
               "comprehend-languages", "identify", "enlarge-person", "cure-light-wounds",
               "bless", "protection-from-evil", "shield-of-faith", "invisibility",
               "web", "knock", "see-invisibility", "cure-moderate-wounds",
               "restoration-lesser", "bull-s-strength", "cat-s-grace", "fireball", "fly",
               "haste", "dispel-magic", "lightning-bolt", "remove-curse",
               "cure-serious-wounds", "stoneskin", "dimension-door"),
    "wand": ("magic-missile", "cure-light-wounds", "mage-armor", "burning-hands",
             "shield-of-faith", "cure-moderate-wounds", "scorching-ray", "invisibility",
             "bull-s-strength", "fireball", "lightning-bolt", "cure-serious-wounds"),
}


def sold() -> list[tuple[str, str, object]]:
    """(good key "scroll:<spell>", name, the bought Stock) for every row of `SOLD` whose
    spell the corpus has."""
    from . import spells as spells_mod

    out = []
    for kind, ids in SOLD.items():
        for sid in ids:
            try:
                spells_mod.get(sid)
            except KeyError:
                continue
            out.append((f"{kind}:{sid}", make(kind, sid, how="bought")))
    return out


def from_good_key(key: str, how: str = "bought"):
    """The Stock a good key ("scroll:mage-armor", "wand:magic-missile") delivers, or None."""
    kind, _, sid = str(key or "").partition(":")
    if kind not in KINDS or not sid:
        return None
    return make(kind, sid, how=how)


# --- a wizard copies a scroll into the spellbook ------------------------------------------
#
# CRB, Magic, Arcane Magical Writings (legacy.aonprd.com/coreRulebook/magic.html, read
# 2026-11-22): "A wizard can also add a spell to his book whenever he encounters one on a
# magic scroll ... he must spend 1 hour studying the spell. At the end of the hour, he must
# make a Spellcraft check (DC 15 + spell's level). A wizard who has specialized in a school
# of spells gains a +2 bonus on the Spellcraft check if the new spell is from his specialty
# school. If the check succeeds, the wizard understands the spell and can copy it into his
# spellbook ... If the check fails, the wizard cannot understand or copy the spell. He
# cannot attempt to learn or copy that spell again until one week has passed"; "A wizard
# can only learn new spells that belong to the wizard spell lists"; "a spell successfully
# copied from a magic scroll disappears from the parchment" and "a failed Spellcraft check
# does not cause the spell to vanish". Writing takes 1 hour a spell level (a cantrip 30
# minutes) at the book's page costs: `formulae.copy_cost_gp` / `copy_minutes`, the same
# numbers the alchemist's formula book copies by. Deciphering the writing (Spellcraft DC
# 20 + level, or read magic) is the circle's Identify: a scroll whose writing is not known
# is refused until it is identified (an owner call). The coin is paid only for a spell
# written (owner report 2026-11-01, the alchemy copy route's rule).

COPY_STORE = "spellcopy:"


def _failed_at(actor, spell_id: str) -> int | None:
    from . import formulae

    entry = (getattr(actor, "herb_known", None) or {}).get(COPY_STORE + spell_id) or {}
    try:
        return int((entry.get("how") or {}).get(formulae.COPY_FAILED_KEY))
    except (TypeError, ValueError):
        return None


def copy_plan(actor, stock, *, clock: int | None = None) -> dict:
    """What copying this scroll into the book asks, before any roll: `{"spell", "level",
    "dc", "bonus_terms", "cost_gp", "minutes", "refused": [words]}`."""
    from . import casting, formulae, spells as spells_mod

    out = {"spell": "", "level": 0, "dc": None, "bonus_terms": [], "cost_gp": 0,
           "minutes": 60, "refused": []}
    entry = entry_of(stock)
    data = casting.caster_data(actor)
    if data.get("prepare_from") != "spellbook":
        out["refused"].append(f"{actor.name} keeps no spellbook to copy into.")
        return out
    if entry is None or entry.get("item_kind") != "scroll":
        out["refused"].append("Only a scroll's writing can be copied into a spellbook.")
        return out
    mag = getattr(stock, "magic", None) or {}
    if not (mag.get("known") or {}).get("intent"):
        out["refused"].append(f"The writing on the {stock.name} is not deciphered yet: "
                              f"identify it at the circle first.")
        return out
    try:
        sp = spells_mod.get(str(entry["spell"]))
    except KeyError:
        out["refused"].append("That scroll holds no spell the book knows.")
        return out
    level = casting.level_on_list(sp, str(data.get("list") or ""))
    out["spell"] = sp.id
    if level is None:
        out["refused"].append(f"{sp.name} is not on the wizard's list; only those spells "
                              f"go into the book.")
        return out
    out["level"] = int(level)
    if sp.id in (getattr(actor, "spellbook", None) or []):
        out["refused"].append(f"{sp.name} is in the spellbook already.")
    failed = _failed_at(actor, sp.id)
    if failed is not None and clock is not None and clock < failed + formulae.COPY_RETRY_MINUTES:
        from . import knowledge

        out["refused"].append(f"{actor.name} failed to understand {sp.name} within the week; "
                              f"another try waits until day "
                              f"{knowledge.day_of(failed + formulae.COPY_RETRY_MINUTES)}.")
    out["dc"] = formulae.COPY_DC_BASE + int(level)
    if casting.specialist_school(actor) and casting.specialist_school(actor) == \
            str(getattr(sp, "school", "") or "").lower():
        out["bonus_terms"].append({"label": "specialty school", "value": 2})
    out["cost_gp"] = formulae.copy_cost_gp(int(level))
    out["minutes"] = formulae.copy_minutes(int(level))
    return out


def resolve_copy(actor, stock_key: str, total: int, *, clock: int) -> dict:
    """Apply a copy whose Spellcraft total is already rolled (the plan's bonus terms in it).
    `{"success", "spell", "dc", "total", "spent_gp"}`: on a success the spell is written
    into the book and the scroll's writing is gone; on a failure the week starts and the
    scroll stays."""
    from . import formulae, goods

    st = actor.stock[stock_key]
    plan = copy_plan(actor, st, clock=clock)
    out = {"success": False, "spell": plan["spell"], "dc": plan["dc"], "total": int(total),
           "spent_gp": 0}
    if plan["refused"]:
        out["refused"] = plan["refused"]
        return out
    if int(total) >= int(plan["dc"]):
        out["success"] = True
        actor.spellbook.append(plan["spell"])
        actor.take_stock(stock_key, 1)
        cp = int(round(plan["cost_gp"] * 100))
        actor.purse, _ok = goods.spend(actor.purse, cp)
        out["spent_gp"] = plan["cost_gp"]
    else:
        entry = actor.herb_known.setdefault(COPY_STORE + plan["spell"], {"keys": [], "how": {}})
        entry.setdefault("how", {})[formulae.COPY_FAILED_KEY] = int(clock)
    return out
