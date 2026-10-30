"""Option D: ship the rulebook line, and give every removed id a body to land on.

The owner's choice (docs/bestiary-licensing.md option D, 2026-10-28): `creatures.json` keeps
only the rows from Paizo's rulebooks (NPC, Villain and Monster Codex, the Game Mastery Guide,
Bestiaries 3, 5 and 6, Mythic Adventures — the `Rulebook` family of
tools/bestiary_provenance.py), less the iconics (Seelah, Sajan… are Paizo characters). The
adventure, society, module, setting and third-party rows go: 5,545 of 6,406.

Applied as a filter over the shipped file, not a re-import, so each kept row keeps every
pass already run on it (the list repair, the biome and harvest tags) byte for byte; the
spreadsheet's `Gear` and `OtherGear` text is added to the kept rows (the import dropped it;
loot is what a creature carries, the owner's ruling).

No save may lose its creature: the owner's saves hold five removed ids
(`tian-merchant-sailor`, `commoner-outlaw`, `agent-of-the-enlightenment`, `hedge-witch`,
`aelzeldra`), and any player on 0.2.22 could hold any of the 5,545. Every removed id is
aliased in content/bestiary/aliases.json (`bestiary.raw_block` reads it after the store):

- a person — a humanoid no bigger than Medium, not of the giant subtype, of no people the
  printed Bestiaries print — to what the chooser answers for its name's words at its own
  CR (`npcs.choose`), else to one of the app's people of its Hit Dice's class nearest its
  CR (`_person_for`);
- anything else, the giants, the ogres, the hobgoblins and every non-humanoid, to the
  nearest printed Bestiary block of its type: within one CR first, then by name words,
  subtypes and alignment (`_printed_for`).

And each removed id's own CR beside its body (`was_cr`), so a saved creature standing on a
stand-in more than one CR from what it was fights on its own saved numbers, not the
stand-in's print (`bestiary.stand_in_far`).

Measured 2026-10-30 (review of 0.2.23): the first map put 2,164 of the 5,537 on
`townsfolk-level-1`, 141 of them Large or bigger (an ogre barbarian, a CR 16 biclops) and
777 of no human subtype; and on printed bodies, by name words before CR, 983 more than two
CR from what they were — a CR 1 nupperibo on the CR 14 peri, swinging +27/+22/+17/+12.

    python tools/ship_rulebook_line.py C:/path/monster_stat_blocks_full.xlsx
    python tools/ship_rulebook_line.py --aliases-from DIR   # DIR: 0.2.22's creatures.json,
                                                            # core.json and mounts.json
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for p in (ROOT, ROOT / "tools"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "pathfindergm.settings")

import django  # noqa: E402

django.setup()

import bestiary_provenance as bp  # noqa: E402

SPREAD = ROOT / "content" / "bestiary" / "creatures.json"
ALIASES = ROOT / "content" / "bestiary" / "aliases.json"
ICONICS = ("amiri", "ezren", "harsk", "kyra", "lem-", "lini", "merisiel", "sajan", "seelah",
           "seoni", "valeros", "sorzan")


_TYPES = ("aberration", "animal", "construct", "dragon", "fey", "humanoid", "magical beast",
          "monstrous humanoid", "ooze", "outsider", "plant", "undead", "vermin")


def _kind(block: dict) -> str:
    """The creature type alone. The spreadsheet writes it loosely — "Ooze", "ooze (cold)",
    "augmented plant", "animal companion 5", "outsider familiar" — and an "elemental" is
    the outsider subtype written as a type (Bestiary 1, Appendix 2)."""
    text = str(block.get("creature_type") or "").lower()
    # Three types 0.2.22's Bestiary 4 rows carried cut short by the OCR (the almiraj and the
    # death dog "magical", the scorpions "ve", the samsaran "iso"): unrepaired, six of the
    # thirteen ids the re-read lost landed nowhere.
    text = {"magical": "magical beast", "ve": "vermin", "iso": "humanoid"}.get(text.strip(), text)
    if "elemental" in text:
        return "outsider"
    # Longest first, so a monstrous humanoid is not a humanoid.
    return next((t for t in sorted(_TYPES, key=len, reverse=True) if t in text), text.strip())


def _slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", (name or "").lower()).strip("-") or "creature"


def gear_columns(xlsx: Path) -> dict[str, dict]:
    """{id: {"gear", "other_gear"}} off the spreadsheet, ids slugged as the import slugs."""
    import openpyxl

    wb = openpyxl.load_workbook(xlsx, read_only=True, data_only=True)
    ws = wb[wb.sheetnames[0]]
    rows = ws.iter_rows(values_only=True)
    header = [str(h or "").strip() for h in next(rows)]
    at = {h: i for i, h in enumerate(header)}
    out: dict[str, dict] = {}
    for raw in rows:
        def col(key):
            i = at.get(key)
            v = raw[i] if i is not None and i < len(raw) else None
            return str(v).strip() if v not in (None, "") else ""
        name = col("Name")
        if name and _slug(name) not in out:
            out[_slug(name)] = {"gear": col("Gear"), "other_gear": col("OtherGear")}
    return out


# How near a stand-in's CR must be for its printed attacks to stand in for the removed
# row's. Measured 2026-10-30 over the 2,918 aliases on printed bodies whose removed row and
# stand-in both print an attack: the stand-in's first attack bonus against the row's own,
# |difference| median / 90th percentile / share 5 or more —
#
#   |CR gap| 0      2.0 / 6 / 18%       |CR gap| <= 2   3.0 / 8 / 35%
#            <= 1   2.0 / 7 / 24%                <= 3   5.0 / 8 / 52%
#                                                > 5   11.0 / 21 / 86%
#
# and two printed Bestiary creatures of the same type and the same CR, the spread the
# Bestiary itself has: 2.0 / 6 / 19%. Within one CR a stand-in is as near as a sibling;
# past it, worse at every step. So the map looks within one CR first, and a saved creature
# whose stand-in is further than that fights on its own saved numbers
# (`bestiary.stand_in_far`, the same number read from aliases.json's `window`).
WINDOW = 1.0

# A people the app's builds are not: they are all human (content/npc-builds/people.json),
# so a removed hobgoblin archer, elf ranger or orc chieftain lands on the printed Bestiary's
# own hobgoblin, elf or orc when there is one — a Medium human townsperson is the wrong
# body and the wrong face for any of them. Human is the one people a build is.
_BUILD_PEOPLES = {"human"}

_SIZES = ("fine", "diminutive", "tiny", "small", "medium", "large", "huge", "gargantuan",
          "colossal")


def _printed(shipped: dict[str, dict]) -> list[tuple[str, dict]]:
    """The printed Bestiary blocks, never a templated creature or one of the app's people
    (those are made from these)."""
    return [(bid, b) for bid, b in shipped.items()
            if str(b.get("source") or "").startswith("Bestiary")
            and b.get("biomes_from") not in ("template", "build")]


def is_person(block: dict, shipped: dict[str, dict]) -> bool:
    """Whether a removed row lands on one of the app's people rather than a printed body.

    A humanoid, no bigger than Medium (a build is a Medium human: 141 Large and bigger
    humanoids landed on `townsfolk-level-1` in the first map, the CR 16 biclops among them),
    not of the giant subtype (an ogre is a humanoid with the giant subtype, Bestiary 1, and
    no townsperson), not a troop (a build is one person), and of no people a printed
    Bestiary humanoid is."""
    if _kind(block) != "humanoid":
        return False
    size = str(block.get("size") or "medium").strip().lower()
    if size in _SIZES and _SIZES.index(size) > _SIZES.index("medium"):
        return False
    mine = _subtypes(block)
    if "giant" in mine or "troop" in mine:
        return False
    peoples = mine - _BUILD_PEOPLES
    if not peoples:
        return True
    # Its people's printed subtype, or the printed block's own name: the re-read Bestiary 1
    # orc prints no subtype at all, and by subtype alone 32 orcs stayed on human builds.
    kin = set()
    for _, b in _printed(shipped):
        if _kind(b) == "humanoid":
            kin |= _subtypes(b) | set(_words(str(b.get("name") or "")))
    return not (peoples & kin)


def alias_for(block: dict, shipped: dict[str, dict]) -> str | None:
    if is_person(block, shipped):
        return _person_for(block, shipped)
    return _printed_for(block, shipped)


# What a person of no trade the chooser knows stands on, by the class their Hit Dice say
# they had: the d10s and d12s of the martial classes are a warrior's, a d8 a skilled
# worker's, a d6 a caster's — read off the printed "(2d8+3d10+5)", never off the name.
_BY_DIE = {12: ("fighter", "soldier", "mercenary"), 10: ("fighter", "soldier", "mercenary"),
           8: ("craftsman", "merchant", "sage", "clerk"), 6: ("priest", "healer")}


def _person_for(block: dict, shipped: dict[str, dict]) -> str | None:
    from rules import npcs

    name = str(block.get("name") or "")
    cr = float(block.get("cr_value") or 0.5)
    # The chooser's own level for a CR (`npcs.target_cr` inverted): CR 1/2 is level 1.
    level = max(1, int(cr + 1))
    # Head noun first: English puts it last ("Tian Merchant Sailor" is a sailor,
    # "Hobgoblin Archer" an archer), and the chooser weights its first word most.
    got = npcs.choose(list(reversed(_words(name))), level) or {}
    body = shipped.get(str(got.get("id") or "")) or {}
    # A printed person (an NPC Codex row) only within `WINDOW`: its print is what a saved
    # creature on it swings, and the chooser's own band is three CR wide. A build prints
    # nothing, so its CR decides nothing a saved creature does.
    if not got.get("floor") and body and (
            body.get("build") or abs(float(body.get("cr_value") or 0) - cr) <= WINDOW):
        return got["id"]
    # A name of nobody's trade ("Aelzeldra", "Agent of the Enlightenment", "Druid"): the
    # app's people of the class its Hit Dice were, the rung nearest its CR. The first map
    # sent these to the floor's townsperson, who has one rung — level 1 — and so every
    # nameless person of any CR was `townsfolk-level-1`: 2,164 of 5,537.
    roles = _BY_DIE.get(_main_die(block), _BY_DIE[8])
    rungs = [(abs(float(b.get("cr_value") or 0) - cr), roles.index(bid.split("-level-")[0]),
              float(b.get("cr_value") or 0), bid)
             for bid, b in shipped.items() if b.get("build")
             and bid.split("-level-")[0] in roles]
    return min(rungs)[-1] if rungs else None


def _main_die(block: dict) -> int:
    """The die most of its Hit Dice are: "(2d8+3d10+5 plus 2)" is a d10."""
    counts: dict[int, int] = {}
    for n, die in re.findall(r"(\d+)d(\d+)", str(block.get("hit_dice") or "")):
        counts[int(die)] = counts.get(int(die), 0) + int(n)
    return max(counts, key=lambda d: (counts[d], d)) if counts else 8


def _printed_for(block: dict, shipped: dict[str, dict]) -> str | None:
    name = str(block.get("name") or "")
    cr = block.get("cr_value")
    words = set(_words(name))
    # The nearest printed Bestiary creature of its type — never a templated one or a
    # person, which are made from these — within one CR first (`WINDOW`), then sharing the
    # most name words ("Advanced Giant Scorpion" is the giant scorpion, "Noble Salamander"
    # the salamander), its subtypes and its alignment; by CR, or for the rows that print
    # none (an animal companion, a familiar, an eidolon: its CR is its master's business)
    # by Hit Dice. Name words came first in the first map, and 983 removed rows landed more
    # than two CR from what they were: a CR 2 stone bat on the CR 11 stone golem, a CR 3
    # grue on the CR 12 shining child, the CR 1 nupperibo on the CR 14 peri.
    kind = _kind(block)
    mine = _subtypes(block)
    printed = [(bid, b) for bid, b in _printed(shipped) if _kind(b) == kind]
    # A crowd stands on a crowd and one creature on one creature: a troop's hit points are
    # the unit's (`bestiary._form_if_a_troop`), a swarm's are the swarm's. The first map put
    # the CR 10 hobgoblin phalanx troop on a single hobgoblin paragon.
    for crowd in ("troop", "swarm"):
        same = [(bid, b) for bid, b in printed
                if (crowd in _subtypes(b)) == (crowd in mine)]
        printed = same or printed
    hd = _hd(block)

    def far(b: dict) -> float:
        if cr is not None and b.get("cr_value") is not None:
            return abs(float(b["cr_value"]) - float(cr))
        return abs(_hd(b) - hd) if hd and _hd(b) else 99.0

    def shared(b: dict) -> int:
        # A word inside a longer one counts: a "warhorse" is a horse.
        theirs = _words(str(b.get("name") or ""))
        return sum(1 for w in words if any(w == t or (len(t) >= 4 and t in w) for t in theirs))

    # Then its subtypes: "Choral the Conqueror" shares no word with any dragon, and by CR
    # alone landed on the colourless elder wyrm — its fire subtype makes it a red dragon,
    # and the abominable snowman's cold makes it the yeti, not a swamp's fen mauler.
    def kin(b: dict) -> int:
        # Shared, less what either has that the other lacks: the jabberwock's fire is
        # one of several, the red dragon's its only one.
        theirs = _subtypes(b)
        return 2 * len(mine & theirs) - len(mine ^ theirs)

    # Then its alignment: a red and a gold dragon are both of fire, and Choral is evil.
    align = str(block.get("alignment") or "").upper().strip()

    def bent(b: dict) -> int:
        theirs = str(b.get("alignment") or "").upper().strip()
        return sum(1 for x, y in zip(align.ljust(2), theirs.ljust(2)) if x == y and x != " ")

    same = [(max(0.0, far(b) - WINDOW), -shared(b), -kin(b), -bent(b), far(b), bid)
            for bid, b in printed]
    return min(same)[-1] if same else None


# Words that say nothing about what a creature is: joiners, the adventure's rung labels,
# and the simple templates' names (the creature under "advanced" is the creature).
_EMPTY = {"of", "the", "a", "an", "and", "tier", "subtier", "level", "advanced", "s"}


def _words(name: str) -> list[str]:
    return [w for w in re.findall(r"[a-z]+", name.lower()) if w not in _EMPTY]


def _subtypes(block: dict) -> set[str]:
    return {s.strip() for s in re.split(r"[,()]", str(block.get("subtype") or "").lower())
            if s.strip()}


def _hd(block: dict) -> int:
    """Hit Dice off the printed line: "(4d8+4)" is 4, "(10 HD; 9d10+1d8+20)" is 10."""
    text = str(block.get("hit_dice") or "")
    m = re.search(r"(\d+)\s*HD", text)
    return int(m.group(1)) if m else sum(int(n) for n in re.findall(r"(\d+)d\d+", text))


def main(xlsx: Path) -> None:
    from rules import bestiary

    doc = json.loads(SPREAD.read_text(encoding="utf-8"))
    rows = doc["creatures"]
    keep = [c for c in rows if bp.family(str(c.get("source") or "")) == "Rulebook"
            and not c["id"].startswith(ICONICS)]
    kept_ids = {c["id"] for c in keep}
    gone = [c for c in rows if c["id"] not in kept_ids]
    by_id = {c["id"]: c for c in gone}
    cols = gear_columns(xlsx)
    for c in keep:
        g = cols.get(c["id"]) or {}
        if g.get("gear"):
            c["printed_gear"] = g["gear"]
        if g.get("other_gear"):
            c["printed_other_gear"] = g["other_gear"]
    # The gear comes back from the workbook with its gods ("silver holy symbol of Gorum");
    # the same table as the spells takes them out (tools/golarion_rewrites.py).
    import golarion_rewrites

    keep = golarion_rewrites.apply_bestiary(keep)

    # The store as it will stand: what the aliases may land on. Built from the kept rows,
    # the printed Bestiaries and the app's own people and templated creatures.
    doc_after = dict(doc, creatures=keep)
    SPREAD.write_text(json.dumps(doc_after, indent=1, ensure_ascii=False), encoding="utf-8")
    from rules import npcs, pristine

    bestiary._IMPORTED = None
    pristine._MEMO.pop("bestiary", None)
    npcs._BUILT = ()
    shipped = bestiary.imported()
    aliases, lost = write_aliases(gone, shipped)
    doc_after["note"] = (str(doc.get("note") or "") + " Since 2026-10-28 the rulebook line only "
                         "(option D, tools/ship_rulebook_line.py); aliases.json lands every "
                         "removed id on a shipped body.")
    SPREAD.write_text(json.dumps(doc_after, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"kept {len(keep)}, removed {len(gone)}, aliased {len(aliases)}, unaliased {len(lost)}")
    if lost:
        print("unaliased:", [(i, _kind(by_id[i]), by_id[i].get("cr_value")) for i in lost[:40]])


def write_aliases(gone: list[dict], shipped: dict[str, dict]) -> tuple[dict, list]:
    """Land every removed row on a shipped body and write aliases.json: the body by hashed
    id (`aliases`), the row's own CR by the same hash (`was_cr`, for `bestiary.stand_in_far`)
    and the CR gap past which a stand-in's print is not the row's (`window`)."""
    from rules import bestiary

    core_aliases = json.loads((SPREAD.parent / "core.json").read_text(encoding="utf-8")) \
        .get("aliases") or {}
    aliases: dict[str, str] = {}
    was_cr: dict[str, float] = {}
    lost = []
    for c in gone:
        # Shipped under its own id, or already the Bestiary's alias ("zombie" is the human
        # zombie, core.json): the first map sent the spreadsheet's "Zombie" to a
        # townsperson, which raw_block would have overruled and nobody should read.
        if c["id"] in shipped or c["id"] in core_aliases or c["id"] in aliases:
            continue
        target = alias_for(c, shipped)
        if target:
            aliases[c["id"]] = target
            if c.get("cr_value") not in (None, ""):
                was_cr[c["id"]] = round(float(c["cr_value"]), 3)
        else:
            lost.append(c["id"])
    # And the creatures renamed out of Golarion (2026-10-30, fix/bestiary-names), so this
    # rewrite of the file does not drop the aliases tools/strip_golarion.py put there: an
    # old id's target follows its rename, and each renamed id points at its new one.
    import golarion_rewrites

    moved = golarion_rewrites.bestiary_aliases()
    aliases = {k: moved.get(v, v) for k, v in aliases.items()}
    for old_id, new_id in moved.items():
        aliases.setdefault(old_id, new_id)
    ALIASES.write_text(json.dumps({
        "note": ("Ids the bestiary carried before option D (2026-10-29), each to the shipped "
                 "body it now is: written by tools/ship_rulebook_line.py, read by "
                 "bestiary.raw_block after the store, so a save's from_template keeps a body. "
                 "`was_cr` is each removed row's own CR; a stand-in more than `window` CR "
                 "from it fights on the saved creature's own numbers (bestiary.stand_in_far)."),
        # Keyed by hash, not by the id: the ids are the removed rows' names, Paizo's
        # adventure characters among them, which option D stopped shipping.
        "hashed": True,
        "window": WINDOW,
        "aliases": dict(sorted((bestiary.alias_key(k), v) for k, v in aliases.items())),
        "was_cr": dict(sorted((bestiary.alias_key(k), v) for k, v in was_cr.items()))},
        indent=1, ensure_ascii=False),
        encoding="utf-8")
    return aliases, lost


def aliases_from(old: Path) -> None:
    """Rewrite aliases.json alone from 0.2.22's bestiary files in `old` (creatures.json,
    core.json and mounts.json as tagged v0.2.22). Every id they carried that names no
    shipped block, no core.json alias and no hand-written template is landed again — the
    spreadsheet's removed rows and the Bestiary 4 blocks the re-read of 2026-10-28 could
    not parse (almiraj, bhole, the colossi... 13 ids that resolved to nothing, though
    docs/bestiary-licensing.md promised no save loses a creature)."""
    from rules import bestiary

    rows: dict[str, dict] = {}
    for name in ("creatures.json", "mounts.json", "core.json"):
        doc = json.loads((old / name).read_text(encoding="utf-8"))
        for c in doc.get("creatures") or []:
            if c.get("id"):
                rows.setdefault(c["id"], {}).update(c)
    bestiary._ALIAS_MAP = None
    shipped = bestiary.imported()
    gone = [c for i, c in sorted(rows.items())
            if i not in shipped and i not in bestiary.TEMPLATES]
    aliases, lost = write_aliases(gone, shipped)
    bestiary._ALIAS_MAP = None
    print(f"0.2.22 ids {len(rows)}, not shipped {len(gone)}, aliased {len(aliases)}, "
          f"unaliased {len(lost)}")
    if lost:
        print("unaliased:", [(i, _kind(rows[i]), rows[i].get("cr_value")) for i in lost[:40]])


if __name__ == "__main__":
    if sys.argv[1] == "--aliases-from":
        aliases_from(Path(sys.argv[2]))
    else:
        main(Path(sys.argv[1]))
