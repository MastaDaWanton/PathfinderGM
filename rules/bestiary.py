"""Creatures the engine can put in a scene and roll against.

Three sources, one lookup:

- the hand-written town NPCs below — the people the opening scene actually needs;
- 782 core creatures parsed out of the six Bestiary PDFs, which is where the plain Ogre,
  Skeleton and Troll live, and the only source that carries **Environment**;
- 6,406 stat blocks from a variant and NPC spreadsheet, which is where the named
  adventure-path villains live.

Unlike the spell list, this is **executable**. `instantiate()` builds an Actor with hit
points, an AC, saves, damage reduction and an attack, and the engine rolls against it. An
imported creature is not reference material; it is a thing that can hit the player.

Precedence runs hand-written, then core, then spreadsheet. The town NPCs are tuned for the
opening scene and must not be replaced; the printed Bestiary block is the canonical one
where a variant shares its name.

Environment is prose and only the core blocks have it, so every creature also carries
`biomes` and `climates` — the same line read into the canonical vocabulary, or, for the
6,406 that never had a line, guessed from the species in the name or from the creature
type. `tools/tag_creature_biomes.py` writes them and `biomes_inferred` marks every guess.
"""
from __future__ import annotations

import json
import re
from difflib import get_close_matches
from pathlib import Path

from . import creature_effects
from .sheet import Actor, from_dict

TEMPLATES: dict[str, dict] = {
    "guildhand": {
        "xp": 65,
        "name": "guildhand",
        "kind": "npc",
        "abilities": {"str": 11, "dex": 10, "con": 11, "int": 10, "wis": 10, "cha": 9},
        "hp": 4,
        "flat_ac": 10,
        "flat_attack": 0,
        "flat_saves": {"fort": 0, "ref": 0, "will": 0},
        "flat_skills": {"perception": 3, "sense motive": 1, "craft": 4},
        "flat_initiative": 0,
        "flat_cmd": 11,
        "equipped": "club",
        "weapons": ["club"],
        "kit": "kit.laborer",
        "notes": "Commoner 1. Tired, half-attentive, not paid enough to fight.",
    },
    "watchman": {
        "xp": 135,
        "name": "watchman",
        "kind": "npc",
        "abilities": {"str": 13, "dex": 12, "con": 12, "int": 9, "wis": 11, "cha": 10},
        "hp": 11,
        "flat_ac": 15,
        "flat_attack": 2,
        "flat_saves": {"fort": 3, "ref": 1, "will": 0},
        "flat_skills": {"perception": 5, "intimidate": 4, "sense motive": 2},
        "flat_initiative": 1,
        "flat_cmd": 14,
        "equipped": "shortsword",
        "weapons": ["shortsword", "club"],
        "armour": "chain shirt",
        "kit": "kit.militia",
        "notes": "Warrior 1 in a chain shirt. Will shout before drawing.",
    },
    "thug": {
        "xp": 135,
        "name": "thug",
        "kind": "npc",
        "abilities": {"str": 14, "dex": 13, "con": 13, "int": 9, "wis": 10, "cha": 8},
        "hp": 13,
        "flat_ac": 14,
        "flat_attack": 3,
        "flat_saves": {"fort": 3, "ref": 2, "will": 0},
        "flat_skills": {"perception": 4, "intimidate": 6, "stealth": 3},
        "flat_initiative": 1,
        "flat_cmd": 15,
        "equipped": "sap",
        "weapons": ["sap", "dagger"],
        "armour": "leather",
        "kit": "kit.cutpurse",
        "notes": "Warrior 1. Prefers a sap: a body that wakes up cannot testify to a killing.",
    },
    "guard dog": {
        "xp": 100,
        "name": "dog",
        "kind": "npc",
        "size": "small",
        "abilities": {"str": 13, "dex": 17, "con": 15, "int": 2, "wis": 12, "cha": 6},
        "hp": 6,
        "flat_ac": 14,
        "flat_attack": 2,
        "flat_saves": {"fort": 4, "ref": 5, "will": 1},
        "flat_skills": {"perception": 8, "survival": 1, "stealth": 5},
        "flat_initiative": 3,
        "flat_cmd": 13,
        "flat_damage": "1d4",
        "equipped": "unarmed",
        "weapons": ["unarmed"],
        "notes": "Scent. Barks first.",
    },
}


# Loadouts by tag, so the same statblock can spawn dressed for different work: a
# watchman on the wall carries kit.militia; the same warrior working a counting
# house carries kit.merchant-guard. Kits are TABLES, not model output, same law as
# the templates' own pockets — and a template's inline wealth/pockets still win
# over the kit's, so nothing shipped changes shape.
KITS: dict[str, dict] = {
    "kit.laborer": {"wealth": "1d4 sp",
                    "pockets": ["work gloves", "chalk stub"]},
    "kit.militia": {"wealth": "1d6 sp",
                    "pockets": ["watch whistle", "rations"]},
    "kit.cutpurse": {"wealth": "2d4 sp",
                     "pockets": ["dice of bone", "strip of dried meat"]},
    "kit.merchant-guard": {"wealth": "2d6 sp",
                           "pockets": ["ledger scrap", "brass token", "rations"]},
}


_COLLECTIVE_NAME = re.compile(
    r"^(?:a\s+|the\s+)?(pair|couple|duo|two|trio|three|four|five|six|group|band|"
    r"gang|mob|pack|squad|patrol|crowd|bunch)\s+of\s+(.+)$", re.I)
_COLLECTIVE_COUNTS = {"pair": 2, "couple": 2, "duo": 2, "two": 2, "trio": 3,
                      "three": 3, "four": 4, "five": 5, "six": 6}


def split_collective_name(name: str) -> tuple[int, str]:
    """"pair of guards" is two guards, not one creature with a plural name.

    Measured live: the GM spawned a single 11-hp actor called "pair of guards" and
    the player fought half as many people as the fiction described — the collective
    walked through the count=1 path with nobody reading the name. Returns
    (count, singular) for a collective name, (1, name) untouched otherwise. An
    unlisted collective (group, gang, mob...) means four, matching the fight
    injector's own reading of a crowd.
    """
    m = _COLLECTIVE_NAME.match(str(name or "").strip())
    if not m:
        return 1, str(name or "")
    count = _COLLECTIVE_COUNTS.get(m.group(1).lower(), 4)
    plural = m.group(2).strip()
    singular = {"wolves": "wolf", "thieves": "thief", "knives": "knife"}.get(
        plural.lower())
    if singular is None:
        if plural.lower().endswith("men"):
            singular = plural[:-3] + "man"
        elif plural.lower().endswith("s") and not plural.lower().endswith("ss"):
            singular = plural[:-1]
        else:
            singular = plural
    return count, singular


class UnknownTemplate(KeyError):
    pass


def instantiate(
    template: str,
    scene=None,
    name: str | None = None,
    world_entity_id: str | None = None,
    index: int = 0,
) -> Actor:
    key = template.strip().lower()
    found = lookup(key)
    if found is None:
        raise UnknownTemplate(f"no creature {template!r}." + suggestion(key))
    data = dict(found)
    # What defeating this creature is worth — `lookup` computed it into `xp`; here it
    # becomes the actor's `xp_value`, and its own ledger starts at zero.
    data["xp_value"] = int(data.pop("xp", 0) or 0)
    data["xp"] = 0
    # The template this creature came from, kept because `name` is about to be
    # overwritten with whatever the GM called it. "a bear" spawned from `black-bear`
    # lost every link back to its stat block, so a creature that died was worth nothing
    # the moment anybody named it — measured in real play: a bear awarded 0 XP.
    data["from_template"] = key
    if name:
        data["name"] = name
    data["world_entity_id"] = world_entity_id
    actor = from_dict(data, ref=_next_ref(scene))
    _assemble_kit(actor, data)
    return actor


def _assemble_kit(actor, data: dict) -> None:
    """Pockets for the spawned — as a CLAIM, not yet as contents.

    The loot op made empty pockets visible — "I take everything" off a thug who owns a
    sap and nothing else is a hollow sentence. Kits are TABLES, not model output: every
    quality lesson in this repo says a model-authored inventory is unpriceable
    narrative garbage in the ledger. A template declares `kit` (a tag into KITS)
    and/or inline `wealth`/`pockets`, inline winning; anything undeclared derives
    from what the stat block already says.

    Nothing is rolled here. Stats resolve at spawn because combat needs them the
    same round; the pockets stay `kit_pending` until `collapse_kit` at the first
    observation — loot, steal, trade — so the transcript can never contradict
    pockets nobody opened, and the watcher has the whole player turn to garnish.
    """
    if int((data.get("abilities") or {}).get("int", 10) or 10) <= 2:
        return                                  # animals carry teeth, not coin
    kit_key = str(data.get("kit") or "").strip().lower()
    kit = KITS.get(kit_key, {})
    wealth = str(data.get("wealth") or kit.get("wealth") or "").strip()
    if not wealth and data.get("kind") == "npc":
        # Derived, roughly: what defeating them is worth maps to what they carry.
        xp = int(data.get("xp_value", 0) or 0)
        wealth = "2d6 sp" if xp >= 100 else "1d4 sp"
    pockets = [str(p) for p in (data.get("pockets") or kit.get("pockets") or [])]
    if wealth or pockets:
        actor.kit_pending = {"kit": kit_key, "wealth": wealth, "pockets": pockets}


def collapse_kit(actor) -> list[str]:
    """First observation: the claim becomes contents, and the claim is gone.

    Idempotent by construction —
    the pending dict is consumed — so loot-then-loot cannot double the purse.
    Returns what materialised, for the tell.
    """
    from . import creation as creation_mod

    pending = dict(getattr(actor, "kit_pending", None) or {})
    if not pending:
        return []
    actor.kit_pending = {}
    made = []
    wealth = str(pending.get("wealth") or "").strip()
    if wealth:
        # Merged, never assigned: play may already have put coin on this body (a
        # bribe taken, a payout pocketed), and the claim collapsing must add the
        # kit's coin to the facts, not overwrite them.
        rolled = creation_mod.starting_purse({"starting_wealth": wealth}) or {}
        for coin, n in rolled.items():
            actor.purse[coin] = int(actor.purse.get(coin, 0)) + int(n)
        made.append(f"a purse ({wealth})")
    for thing in pending.get("pockets") or []:
        key = str(thing).strip().lower().replace(" ", "-")
        if key:
            actor.carry(key, 1)
            made.append(key)
    return made


def next_ref(scene, taken=()) -> str:
    """The next ref, minted once and never reused. The ONE minter.

    Refs are `c1, c2, ...` — short because the GM has to type them, and distinct from
    World Bible's twelve-character ids so the two can never be confused.

    They used to be recycled: the lowest `cN` not in `scene.actors`, and that rule was
    copied by hand into four other places (the validator's projection and three
    judgement repairs). Recycling poisoned every per-ref table that outlived a creature
    — `spawn_feet` (an archer's 120 feet inherited by the next `c1`, engine.py's own
    comment), `fallen`, `pools`, `attacked`, the market's stall key, the watcher's
    garnish ledger — and under containment it would have been worse than poison: an
    actor in the next room is not in the view, so his ref would have been minted a
    second time for a living creature.

    So the mark, not the dict. `scene.minted` is a high-water mark that only `Scene.add`
    advances; a save from before it existed heals to the highest `cN` it holds. `taken`
    is for callers projecting several refs before anybody is added — the validator
    checking a list that spawns three — and it advances nothing: validation must not
    consume a ref.
    """
    if scene is None:
        return "c1"
    held = set(getattr(scene, "people", None) or getattr(scene, "actors", {}) or ())
    n = int(getattr(scene, "minted", 0) or 0)
    while True:
        n += 1
        ref = f"c{n}"
        if ref not in held and ref not in taken:
            return ref


# The name stage 8a and every older test knew it by.
_next_ref = next_ref


# --- the imported bestiary ------------------------------------------------------------------

_IMPORTED: dict[str, dict] | None = None
_INDEX: list[str] = []

# Fields on an imported stat block that the Actor does not take. Kept in the record for the
# bestiary page and stripped before the Actor is built, because `from_dict` rejects what it
# does not recognise and a stat block is a great deal more than a combatant.
_NOT_ON_THE_SHEET = (
    "cr", "cr_value", "xp", "creature_type", "subtype", "alignment", "hit_dice",
    "ac_note", "melee", "ranged", "ranged_attack", "ranged_damage", "cmb",
    "base_attack", "speed", "speed_note", "immune", "resist", "sr", "weaknesses",
    "senses", "languages", "special_attacks", "special_abilities", "spell_like",
    "environment", "organization", "treasure", "source", "playable", "id", "feats",
    "biomes", "climates", "biomes_any", "biomes_inferred", "biomes_from",
)


def imported() -> dict[str, dict]:
    """Every imported stat block, keyed by slug. Loaded once, on first use."""
    global _IMPORTED, _INDEX
    if _IMPORTED is None:
        from django.conf import settings

        out: dict[str, dict] = {}
        for folder in (Path(settings.BASE_DIR) / "content" / "bestiary",
                       Path(settings.CAMPAIGN_DIR).parent / "homebrew" / "creatures"):
            if not folder.is_dir():
                continue
            # `core.json` is loaded last so it wins the 55 name collisions with the
            # variant spreadsheet: a printed Bestiary stat block is the canonical one, and
            # an adventure-path variant that happens to share a name must not replace it.
            for path in sorted(folder.glob("*.json"),
                               key=lambda q: (q.stem == "core", q.stem)):
                try:
                    data = json.loads(path.read_text(encoding="utf-8"))
                except Exception:
                    continue
                entries = data.get("creatures") if isinstance(data, dict) else None
                if not isinstance(entries, list):
                    entries = [data] if isinstance(data, dict) and data.get("id") else []
                for e in entries:
                    if e.get("id"):
                        base = dict(out.get(e["id"], {}))
                        base.update({k: v for k, v in e.items() if v not in (None, "")})
                        out[e["id"]] = base
        _IMPORTED = out
        _INDEX = sorted(set(list(TEMPLATES) + list(out)))
    return _IMPORTED


def everything() -> dict[str, dict]:
    """Every creature the app knows, hand-written ones included.

    `imported()` is the two content files and nothing else, which is right for play — the
    town NPCs are reached through `lookup` — and wrong for the editor. The creatures bench
    lists the four hand-written townsfolk and the registry's loader pointed at `imported`,
    so clicking `guildhand` asked for a creature that loader had never heard of and got a
    404 from a row the same page had just drawn.
    """
    out = {k: {"id": k, **v} for k, v in TEMPLATES.items()}
    out.update(imported())
    return out


def lookup(key: str) -> dict | None:
    """A creature by name, hand-written first.

    The town NPCs are tuned for the opening scene, so an import that happens to share a
    name must not replace them.
    """
    key = (key or "").strip().lower()
    if key in TEMPLATES:
        return TEMPLATES[key]
    raw = imported().get(key) or imported().get(key.replace(" ", "-"))
    if raw is None:
        return None
    data = {k: v for k, v in raw.items() if k not in _NOT_ON_THE_SHEET}
    data["name"] = raw.get("name", key)
    data["kind"] = "npc"
    # `immune`, `resist`, `weaknesses` and `senses` are stripped by `_NOT_ON_THE_SHEET`
    # above, and `Actor` had no field for any of them — so a frost giant took full damage
    # from cold and 4,673 immunity terms in the content directory were read by nothing.
    # They travel as effect specs instead, which is the same shape a potion's effects
    # arrive in and the same shape the builder edits.
    #
    # Derived here rather than baked into the JSON: `immune` is the field the editor shows
    # and the one a person corrects, so a copy of it inside `effects` would be a second
    # answer that disagrees the moment the first is edited. An authored `effects` list is
    # left alone, which is how a homebrew creature says something the parse cannot.
    if not data.get("effects"):
        data["effects"] = creature_effects.from_creature(raw)
    if not data.get("notes"):
        data["notes"] = f"CR {raw.get('cr', '?')} {raw.get('creature_type', '')}".strip()
    # What defeating it is worth. Stated `xp` first, then CR against the Core award
    # table. Carried as `xp` here and turned into `xp_value` by `instantiate` —
    # `_NOT_ON_THE_SHEET` strips both source fields, so without this hop every
    # imported creature was worth nothing and no fight ever paid out.
    stated = raw.get("xp")
    if stated:
        data["xp"] = int(stated)
    else:
        from .xp import CR_AWARD

        cr = raw.get("cr_value")
        if cr is not None:
            data["xp"] = CR_AWARD.get(round(float(cr), 3), 0)
    return data


def details(key: str) -> dict | None:
    """The whole stat block, for showing rather than fighting."""
    key = (key or "").strip().lower()
    if key in TEMPLATES:
        return {"id": key, "hand_written": True, **TEMPLATES[key]}
    return imported().get(key)


def suggestion(key: str) -> str:
    """Name the nearest few, never all of them.

    With four templates, listing every one was the helpful thing to do. With 6,406 it is a
    wall of text in an error message, and a model reading it loses the turn it was in the
    middle of.
    """
    imported()
    key = (key or "").strip().lower().replace(" ", "-")

    # Containment first, edit distance second. This import is a variant and NPC bestiary —
    # it holds `ambro-the-ogre` and `ogre-brute` and no plain Ogre — so a name *containing*
    # the query is nearly always what was meant.
    #
    # Measured: `get_close_matches("ogre", ...)` came back with 'grue', 'grev' and 'zorek'
    # — short names a few edits away — while every actual ogre scored worse for being
    # longer. Ordering fuzzy first meant the most obvious ask in the book got nonsense.
    close: list[str] = []
    if len(key) >= 3:
        close = sorted((k for k in _INDEX if key in k), key=len)[:5]
    if not close:
        close = get_close_matches(key, _INDEX, n=5, cutoff=0.6)
    if close:
        # Offered, never substituted: "ogre" must not quietly become an ogre boss.
        return " Did you mean " + ", ".join(repr(c) for c in close) + "?"
    return f" There are {len(_INDEX)} creatures and none is close to that name."


def search(text: str = "", creature_type: str = "", size: str = "",
           cr_min: float | None = None, cr_max: float | None = None,
           biome: str = "", climate: str = "", specialists: bool = False,
           limit: int = 120) -> list[dict]:
    """Filter the bestiary. Every argument narrows; none widens.

    `biome` and `climate` are the two axes a Bestiary Environment line carries, and they
    are separate arguments because the line separates them: "warm deserts" is one of each,
    and folding them together would make a frost giant and a fire giant the same query.

    A creature whose climate list is empty is unrestricted and matches every climate —
    absent is not the same as none, and reading it as none would empty the results for
    two thirds of the book.

    `specialists` drops the creatures whose biome list is an expansion of "any". 4,636 of
    the 7,133 are found anywhere, so a swamp asked without it answers mostly with ghosts
    and NPCs who merely could be there: 4,761 hits without it and 125 with.

    (7,133, not the 7,188 the two source files hold between them — 55 names appear in both
    and the printed block wins. Counting the sum is the mistake that made the first three
    figures in this module disagree with each other.)
    """
    out = []
    needle = (text or "").strip().lower()
    for c in imported().values():
        if creature_type and c.get("creature_type") != creature_type:
            continue
        if size and c.get("size") != size:
            continue
        cr = c.get("cr_value")
        if cr_min is not None and (cr is None or cr < cr_min):
            continue
        if cr_max is not None and (cr is None or cr > cr_max):
            continue
        if biome and biome not in (c.get("biomes") or ()):
            continue
        if climate and c.get("climates") and climate not in c["climates"]:
            continue
        if specialists and c.get("biomes_any"):
            continue
        if needle and needle not in c["name"].lower():
            continue
        out.append(c)
    out.sort(key=lambda c: (c.get("cr_value") if c.get("cr_value") is not None else 99,
                            c["name"].lower()))
    return out[:limit]


def vocabularies() -> dict:
    """What a filter can be built from, counted so an empty option is visible first.

    Biomes and climates count only the creatures that belong there specifically. Counting
    the "any" expansions too would have shown every biome with roughly the same 4,700 and
    told a reader nothing about which ground is thin.
    """
    counts: dict[str, dict[str, int]] = {"types": {}, "sizes": {}, "biomes": {},
                                         "climates": {}}
    for c in imported().values():
        for field, key in (("types", "creature_type"), ("sizes", "size")):
            v = c.get(key)
            if v:
                counts[field][v] = counts[field].get(v, 0) + 1
        if c.get("biomes_any"):
            continue
        for field, key in (("biomes", "biomes"), ("climates", "climates")):
            for v in c.get(key) or ():
                counts[field][v] = counts[field].get(v, 0) + 1
    return {k: dict(sorted(v.items(), key=lambda kv: -kv[1])) for k, v in counts.items()}
