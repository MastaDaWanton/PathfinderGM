"""Spellcasting for pay: a temple's healing, sold by whoever keeps it.

Playtest 2026-11-16 #70: a city cathedral's priest could not heal for pay ("I am not a
doctor, nor do I possess the arts of healing"), because no spellcasting service existed
anywhere in the code, and a wounded 1st-level character's only healing was 1 hp a night.

## The book (researched 2026-11-16)

* **Price** — CRB, Goods and Services, Spellcasting: "caster level x spell level x 10 gp",
  a 0-level spell counted as 1/2, and the cost of a costly material component added
  (d20pfsrd.com, Hirelings, Servants & Services). The caster level is the lowest a cleric
  casts the spell at (2 x level - 1), so cure light wounds is 1 x 1 x 10 = 10 gp.
* **What a settlement can cast** — GameMastery Guide, Settlements (aonprd Rules ID 843):
  each settlement type has a base "Spellcasting", the highest spell level for sale there —
  thorp 1st, hamlet 2nd, village 3rd, small town 4th, large town 5th, small city 6th,
  large city 7th, metropolis 8th. This app's three scales (`places.POPULATION_BY_SCALE`:
  village 200-1,200, town 2,000-12,000, city 50,000 up) read as small town, large town and
  metropolis.
* **What is sold** — only spells whose mechanics this engine executes (a `heal`, or a
  `remove_condition` it lays): cure light, moderate, serious and critical wounds, lesser
  restoration and restoration. Remove disease, neutralize poison and remove curse carry
  prose alone (`spell.effects` all `narrative`), and selling a casting that changes
  nothing would take the player's coin for words; they join when their effects do.

## How traditions do it

Baldur's Gate and Neverwinter Nights sell a temple's healing off a priest's own list
(cure wounds, restoration, raise dead), priced by the spell, from the temple's
"store"; Skyrim dropped paid healing for free shrine blessings, and the 1e book keeps the
fee. The fee is kept: it is the CRB's.

The cast itself is the engine's one cast door with no slot (`Engine._op_cast`,
`partial["item_cast"]`, the same door a wand uses), the priest the caster and the payer
the target, so the hit points come back through the one heal path and its tell.
"""
from __future__ import annotations

PREFIX = "service:spell:"

# GameMastery Guide's base Spellcasting by settlement type, read onto this app's scales.
MAX_LEVEL_BY_SCALE = {"village": 4, "town": 5, "city": 8}

# (spell id, costly material in gp). The CRB's restoration is 100 gp of diamond dust (1,000
# for a permanent negative level, which this engine does not track).
SOLD = (("cure-light-wounds", 0), ("cure-moderate-wounds", 0),
        ("cure-serious-wounds", 0), ("cure-critical-wounds", 0),
        ("restoration-lesser", 0), ("restoration", 100))


def cleric_level(spell) -> int | None:
    return next((int(r["level"]) for r in getattr(spell, "level_available", ()) or ()
                 if r.get("via") == "class" and r.get("name") == "cleric"), None)


def caster_level(spell_level: int) -> int:
    """The lowest caster level a cleric casts a spell of this level at (CRB Table 3-6)."""
    return 1 if spell_level <= 1 else 2 * spell_level - 1


def price_cp(spell_level: int, material_gp: int = 0) -> int:
    """CRB: caster level x spell level x 10 gp (a cantrip counts 1/2), plus the material."""
    level = 0.5 if spell_level == 0 else spell_level
    return int(round((caster_level(spell_level) * level * 10 + material_gp) * 100))


def keeps_a_temple(actor) -> bool:
    """Whether this person keeps a place of faith (the temple, the cathedral, a founded
    chapel) and stands in it: the one who sells its castings."""
    from . import keepers, places as places_mod

    place = keepers.place_of(str(getattr(actor, "world_entity_id", "") or ""))
    return bool(place) and str(getattr(actor, "at", "") or "") == place \
        and places_mod.category_of(keepers.label_of(place)) == "faith"


def menu(scale: str) -> list[dict]:
    """What a temple in a settlement of this scale sells: one row per spell, priced."""
    from . import spells as spells_mod

    top = MAX_LEVEL_BY_SCALE.get(scale, MAX_LEVEL_BY_SCALE["town"])
    rows = []
    for sid, material in SOLD:
        try:
            spell = spells_mod.get(sid)
        except KeyError:
            continue
        level = cleric_level(spell)
        if level is None or level > top:
            continue
        rows.append({"id": PREFIX + sid, "spell": sid, "level": level,
                     "cl": caster_level(level), "material_gp": material,
                     "spell_name": spell.name.lower(),
                     "cp": price_cp(level, material), "gp": price_cp(level, material) / 100,
                     # Its name and how healing is asked for, for the counter's matcher
                     # (`goods.match_want`: every word of the want in the row's name);
                     # `find` takes the cheapest row a general ask fits.
                     "name": f"{spell.name.lower()}: healing, to heal me and my wounds "
                             f"for pay (a spell cast)"})
    return rows


def find(want: str, scale: str) -> dict | None:
    """The casting the words ask for, or None. "healing" alone is the cheapest cure."""
    from . import goods

    want = str(want or "").strip().lower()
    rows = menu(scale)
    if want.startswith(PREFIX):
        return next((r for r in rows if r["id"] == want), None)
    bare = want.removeprefix("a ").removeprefix("the ")
    exact = next((r for r in rows if r["spell_name"] == bare), None)
    if exact is not None:
        return exact
    found, fits = goods.match_want(want, rows)
    return min(fits, key=lambda r: r["cp"]) if found is not None else None
