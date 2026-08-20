"""Which books the reference covers, and what each one is for.

Keyed by a distinctive fragment of the filename rather than the whole name, because the
files came from different places and are named inconsistently ("Pathfinder Bestiary 1",
"pathfinder - bestiary 3", "Pathfinder_Core_Rulebook").

`kind` decides what the builder extracts beyond the index:

  core       the rules themselves — conditions, combat, encounter design
  player     character options: classes, feats, races, archetypes
  gm         running the game
  bestiary   creatures; each leaf outline entry is a monster, and we try for its CR
  equipment  items; each leaf entry is a thing you can buy
  sheet      a character sheet form, not a rules book — indexed for its reference tables
"""
from __future__ import annotations

# fragment (lowercased) -> metadata
CATALOGUE: dict[str, dict] = {
    "core_rulebook": {
        "slug": "core-rulebook", "abbr": "CRB", "kind": "core",
        "title": "Pathfinder Roleplaying Game Core Rulebook",
    },
    "gamemastery guide": {
        "slug": "gamemastery-guide", "abbr": "GMG", "kind": "gm",
        "title": "Pathfinder Roleplaying Game GameMastery Guide",
    },
    "advanced player": {
        "slug": "advanced-players-guide", "abbr": "APG", "kind": "player",
        "title": "Advanced Player's Guide",
    },
    "advanced_class_guide": {
        "slug": "advanced-class-guide", "abbr": "ACG", "kind": "player",
        "title": "Advanced Class Guide",
    },
    # These two must stay in this order. Both filenames contain "advanced race guide",
    # so the more specific errata fragment has to be tested first or the four-page errata
    # sheet claims the identity of the 759-page book.
    #
    # `pathfinder advanced race guide pdf.pdf` is the errata for the first printing, not
    # the book — a genuinely confusing filename that cost a wrong entry once already.
    "advanced race guide pdf": {
        "slug": "advanced-race-guide-errata", "abbr": "ARG-errata", "kind": "errata",
        "title": "Advanced Race Guide — first printing errata",
    },
    "advanced race guide": {
        "slug": "advanced-race-guide", "abbr": "ARG", "kind": "player",
        "title": "Advanced Race Guide",
    },
    "ultimate campaign": {
        "slug": "ultimate-campaign", "abbr": "UCam", "kind": "gm",
        "title": "Ultimate Campaign",
    },
    "ultimate combat": {
        "slug": "ultimate-combat", "abbr": "UC", "kind": "player",
        "title": "Ultimate Combat",
    },
    "ultimate equipment": {
        "slug": "ultimate-equipment", "abbr": "UE", "kind": "equipment",
        "title": "Ultimate Equipment",
    },
    "unchained": {
        "slug": "pathfinder-unchained", "abbr": "PU", "kind": "player",
        "title": "Pathfinder Unchained",
    },
    "mythic adventures": {
        "slug": "mythic-adventures", "abbr": "MA", "kind": "player",
        "title": "Mythic Adventures",
    },
    "bestiary 1": {
        "slug": "bestiary-1", "abbr": "B1", "kind": "bestiary", "title": "Bestiary",
    },
    "bestiary 2": {
        "slug": "bestiary-2", "abbr": "B2", "kind": "bestiary", "title": "Bestiary 2",
    },
    "bestiary 3": {
        "slug": "bestiary-3", "abbr": "B3", "kind": "bestiary", "title": "Bestiary 3",
    },
    "bestiary 4": {
        "slug": "bestiary-4", "abbr": "B4", "kind": "bestiary", "title": "Bestiary 4",
    },
    "bestiary 5": {
        "slug": "bestiary-5", "abbr": "B5", "kind": "bestiary", "title": "Bestiary 5",
    },
    "bestiary 6": {
        "slug": "bestiary-6", "abbr": "B6", "kind": "bestiary", "title": "Bestiary 6",
    },
    # Indexed but not creature-scanned. Its outline is 26 entries for 258 pages, so the
    # index is nearly empty, and at 131 MB its text layer takes so long to extract that a
    # full scan never finished — it was still on this one book after twenty minutes while
    # every other bestiary took twenty seconds. Kept in the catalogue so its absence is
    # visible rather than silent.
    "codex monstrueux": {
        "slug": "codex-monstrueux", "abbr": "CM", "kind": "reference-only",
        "title": "Codex Monstrueux",
        "note": "outline too thin to index and too slow to text-scan; not searchable",
    },
    "player character folio": {
        "slug": "player-character-folio", "abbr": "PCF", "kind": "sheet",
        "title": "Player Character Folio",
    },
}


def identify(filename: str) -> dict | None:
    """Match a PDF filename to its catalogue entry, or None if we do not know it."""
    name = filename.lower()
    for fragment, meta in CATALOGUE.items():
        if fragment in name:
            return dict(meta)
    return None
