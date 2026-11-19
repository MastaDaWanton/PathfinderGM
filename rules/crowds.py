"""A crowd: when and where a place is full of people, held by the engine.

Owner, 2026-11-18, on the crowd cut (owner bug 2026-11-17 #7): "even during the day in
markets there has never once been a crowd spawned" — so cutting crowd prose where the map
was empty described every market at noon as deserted. A crowd is engine state now, and the
prose may say one exactly where the engine laid one.

The rule is the book's (CRB, Urban Adventures, City Streets, "Crowds", p.433): "just
indicate which squares on the map contain crowds"; "It takes 2 squares of movement to enter
a square with crowds"; the crowds "provide cover for anyone who does so, enabling a Stealth
check"; "If crowds see something obviously dangerous, they'll move away". So a crowd is a
`Manifestation` of difficult squares on the place's own map (the one shape the engine has
for a thing on the ground that is not a creature), and `Engine._watched_in_the_open` lets a
person standing in it hide.

How the traditions keep a market busy without a body per passer-by: Lusternia's builders
made a market's villagers one crowd mob rather than one mob each, and MUD rooms vary their
ambient population by the clock (Sindome's ambience lines; the MUD-Dev "dynamically
changing room descriptions" threads, 1999). One crowd per place, by the hour, is that.
Anybody the narration picks out of it is still a real person (`seen_people`, the ruling of
2026-10-01): the crowd is the ground they step out of, never a cast list.

When, by house rule (the CRB says only that streets "are often full of people going about
their daily lives"): the trading places in the day trade hours `keepers.DAY_TRADE` keeps;
the docks from first light; the taverns in the evening; a village has no crowd to be lost
in (`places.what_it_is`: "a few hundred people, and everyone knows everyone").
"""
from __future__ import annotations

import hashlib

from . import keepers, places as places_mod, residency

WHAT = "crowd"
SCALE_RANK = {"village": 0, "town": 1, "city": 2}
# (what the place is called, the smallest settlement that crowds it, the busy slots).
# Slots are residency's three hours from midnight: 2 first light ... 6 evening, 7 curfew.
BUSY: tuple[tuple[tuple[str, ...], str, frozenset], ...] = (
    (("market", "merchants row", "bazaar", "square", "plaza", "crossing", "fair"),
     "town", frozenset({3, 4, 5})),
    (("docks", "quay", "wharf", "harbour", "harbor"), "town", frozenset({2, 3, 4, 5})),
    (("tavern", "inn", "alehouse", "taproom"), "town", frozenset({6, 7})),
    (("arena", "theatre"), "city", frozenset({5, 6})),
)
# How much of the open ground the crowd fills: patchy, so a way through is slow but never
# shut. A house figure.
SHARE = 0.6


def busy(place_id: str, scale: str, clock: int, founded=()) -> bool:
    """Whether this place is crowded at this hour. Only the streets and the ground floor:
    a room upstairs at the inn, the ground outside the walls and a cellar have none."""
    if not place_id or places_mod.setting_of(place_id) != "in" \
            or places_mod.storey_of(place_id) != 0:
        return False
    kind = keepers.kind_of(place_id, founded)
    slot = residency.slot_of(int(clock or 0))
    rank = SCALE_RANK.get(scale, 1)
    return any(slot in slots and rank >= SCALE_RANK[smallest]
               and any(kind == w or kind.endswith(" " + w) for w in words)
               for words, smallest, slots in BUSY)


def squares(grid, place_id: str) -> list[tuple[int, int]]:
    """The squares the crowd stands in: open ground only, the same squares every time for
    the same place (seeded off the id, as `floorplan` seeds its stalls)."""
    out = []
    for y in range(grid.height):
        for x in range(grid.width):
            p = (x, y)
            if p in grid.blocked or p in grid.difficult or not grid.passable(p) \
                    or grid.ground(p):
                continue
            if hashlib.sha1(f"{place_id}:{x},{y}".encode()).digest()[0] < 256 * SHARE:
                out.append(p)
    return out


def standing(scene, place_id: str = ""):
    """The crowd laid at this place, or None (a scattered one counts as none)."""
    at = place_id or scene.at or ""
    return next((m for m in scene.manifests if m.what == WHAT and m.source == at
                 and m.terrain == "difficult"), None)


# The brief's line while one stands (gm/brief/here.py). No numbers: the third law.
BRIEF = ("busy with people going about their business at this hour. They are the "
         "crowd and nobody in particular; anyone singled out from it is a real person.")


def gathered_line(name: str) -> str:
    return f"{name[:1].upper()}{name[1:]} is crowded at this hour."


def thinned_line(name: str) -> str:
    return f"The crowd at {name} thins out and goes about its business elsewhere."


def scattered_line(name: str) -> str:
    return f"The crowd at {name} scatters away from the fight."
