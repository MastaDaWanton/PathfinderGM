"""The map item: a nation's map, bought at a general store and read (place map v2, phase 5).

The owner's rulings of 2026-11-18 (docs/place-map-v2-build-plan.md, decision 6 and "Rulings
this carries"):

  * general stores only, about 5 gp, the store's OWN nation: one map to a nation;
  * 0.5 lb, sold back at the usual resale rate;
  * about 10 minutes of game time to read; reading puts the nation in `Scene.maps_read`,
    and the World and Continent maps then know its towns (`PlacesWorld.worldKnown`, "map");
  * a second copy of a map already read teaches nothing (a spare to sell or give away);
  * what a map teaches is never forgotten.

The shelf holds one row, `GEAR["map"]`, "map of the land": a shelf does not know its town
(`market.on_sale` is asked by five callers, none with the world), so the map is named for
the store's nation when it is bought (`Engine._op_buy`, `named`), and what is carried is
"map of <nation>". Reading reads the name back against the world's nations (`nation_named`),
so a map cannot teach a nation that is not there.
"""
from __future__ import annotations

KEY = "map"
SHELF_NAME = "map of the land"
PREFIX = "map of "
READ_MINUTES = 10


def nation_of(world, settlement_id: str) -> str:
    """The nation a settlement lies in: its nearest ancestor below the world, as
    `play/atlas._ancestry` reads it (the containment chain, never the kind names)."""
    if world is None or not settlement_id:
        return ""
    try:
        chain = [a for a in world.ancestors(settlement_id)
                 if str(getattr(a, "kind", "")).upper() != "WORLD"]
    except Exception:  # noqa: BLE001 — an id the world does not hold has no nation
        return ""
    return chain[0].id if chain else ""


def named(world, settlement_id: str) -> str:
    """What a map bought in this settlement is called: "map of <its nation>", or "" when the
    settlement has no nation to map."""
    nation = world.get(nation_of(world, settlement_id)) if world is not None else None
    return f"{PREFIX}{nation.name}" if nation is not None and nation.name else ""


def nation_named(world, item_name: str) -> str:
    """The nation a carried map is of, read off its name, or ""."""
    low = " ".join(str(item_name or "").split()).lower()
    if world is None or not low.startswith(PREFIX):
        return ""
    want = low[len(PREFIX):]
    for row in (getattr(world, "play", None) or {}).get("settlements") or []:
        nid = nation_of(world, row.get("id"))
        n = world.get(nid) if nid else None
        if n is not None and str(n.name).lower() == want:
            return nid
    return ""


def shelf_name(item_name: str) -> str:
    """The name the general store's row goes by, for a carried map; any other name as given.
    A carried map is "map of <nation>", and its weight and its worth are the row's."""
    return SHELF_NAME if is_map(item_name) else item_name


def is_map(item_name: str) -> bool:
    return " ".join(str(item_name or "").split()).lower().startswith(PREFIX)


def read(scene, nation: str) -> bool:
    """Put `nation` among the maps read; False when it was read already (nothing new)."""
    held = getattr(scene, "maps_read", None)
    if held is None or not nation or nation in held:
        return False
    held.append(nation)
    return True
