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
aliased in content/bestiary/aliases.json (`bestiary.raw_block` reads it first):

- a humanoid to what the chooser answers for its name's words at its own CR
  (`npcs.choose`) — the app's own people, or a kept rulebook row;
- anything else to the shipped block of the same name words, else the nearest shipped
  block of its type by CR.

    python tools/ship_rulebook_line.py C:/path/monster_stat_blocks_full.xlsx
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


# The hand-written floor `npcs.choose` falls to, as the build of the same shape.
_FLOOR_ROLE = {"watchman": "guardsman", "thug": "thug", "guildhand": "townsfolk"}


_TYPES = ("aberration", "animal", "construct", "dragon", "fey", "humanoid", "magical beast",
          "monstrous humanoid", "ooze", "outsider", "plant", "undead", "vermin")


def _kind(block: dict) -> str:
    """The creature type alone. The spreadsheet writes it loosely — "Ooze", "ooze (cold)",
    "augmented plant", "animal companion 5", "outsider familiar" — and an "elemental" is
    the outsider subtype written as a type (Bestiary 1, Appendix 2)."""
    text = str(block.get("creature_type") or "").lower()
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


def alias_for(block: dict, shipped: dict[str, dict]) -> str | None:
    from rules import npcs

    name = str(block.get("name") or "")
    cr = block.get("cr_value")
    if _kind(block) == "humanoid":
        # The chooser's own level for a CR (`npcs.target_cr` inverted): CR 1/2 is level 1.
        level = max(1, int(float(cr or 0.5) + 1))
        # Head noun first: English puts it last ("Tian Merchant Sailor" is a sailor,
        # "Hobgoblin Archer" an archer), and the chooser weights its first word most.
        got = npcs.choose(list(reversed(_words(name))), level) or {}
        if got.get("floor"):
            # A name of nobody's trade ("Aelzeldra", "Agent of the Enlightenment"): the
            # floor's own shape, as one of the app's people — the watch, a thug, a
            # townsperson — so a saved one still has a body with a weapon to swing.
            # Past the chooser's reach (a CR 12 nobody is no townsperson within three of
            # it), the stand-in's own rung nearest the CR.
            stand_in = _FLOOR_ROLE.get(got["id"], "townsfolk")
            got = npcs.choose([stand_in], level) or {}
            if got.get("floor"):
                rungs = [(abs(float(b.get("cr_value") or 0) - float(cr or 0)), bid)
                         for bid, b in shipped.items() if bid.startswith(stand_in + "-level-")]
                return min(rungs)[1] if rungs else None
        return got["id"] if got.get("id") in shipped else None
    words = set(_words(name))
    # The nearest printed Bestiary creature of its type — never a templated one or a
    # person, which are made from these — sharing the most name words ("Advanced Giant
    # Scorpion" is the giant scorpion, "Noble Salamander" the salamander; by type and CR
    # alone the first map made them an ant knight and an akhana, and a black bear a
    # celestial deinonychus); then by CR, or for the rows that print none (an animal
    # companion, a familiar, an eidolon: its CR is its master's business) by Hit Dice.
    kind = _kind(block)
    printed = [(bid, b) for bid, b in shipped.items() if _kind(b) == kind
               and str(b.get("source") or "").startswith("Bestiary")
               and b.get("biomes_from") not in ("template", "build")]
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
    mine = _subtypes(block)

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

    same = [(-shared(b), -kin(b), -bent(b), far(b), bid) for bid, b in printed]
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
    core_aliases = json.loads((SPREAD.parent / "core.json").read_text(encoding="utf-8")) \
        .get("aliases") or {}
    aliases: dict[str, str] = {}
    lost = []
    for c in gone:
        # Shipped under its own id, or already the Bestiary's alias ("zombie" is the human
        # zombie, core.json): the first map sent the spreadsheet's "Zombie" to a
        # townsperson, which raw_block would have overruled and nobody should read.
        if c["id"] in shipped or c["id"] in core_aliases:
            continue
        target = alias_for(c, shipped)
        if target:
            aliases[c["id"]] = target
        else:
            lost.append(c["id"])
    # And the creatures renamed out of Golarion (2026-10-30), so this rewrite of the file
    # does not drop the aliases tools/strip_golarion.py put there.
    moved = golarion_rewrites.bestiary_aliases()
    aliases = {k: moved.get(v, v) for k, v in aliases.items()}
    for old_id, new_id in moved.items():
        aliases.setdefault(old_id, new_id)
    ALIASES.write_text(json.dumps({
        "note": ("Ids creatures.json carried before option D (2026-10-29), each to the shipped "
                 "body it now is: written by tools/ship_rulebook_line.py, read by "
                 "bestiary.raw_block, so a save's from_template keeps a body."),
        # Keyed by hash, not by the id: the ids are the removed rows' names, Paizo's
        # adventure characters among them, which option D stopped shipping.
        "hashed": True,
        "aliases": dict(sorted((bestiary.alias_key(k), v) for k, v in aliases.items()))},
        indent=1, ensure_ascii=False),
        encoding="utf-8")
    doc_after["note"] = (str(doc.get("note") or "") + " Since 2026-10-28 the rulebook line only "
                         "(option D, tools/ship_rulebook_line.py); aliases.json lands every "
                         "removed id on a shipped body.")
    SPREAD.write_text(json.dumps(doc_after, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"kept {len(keep)}, removed {len(gone)}, aliased {len(aliases)}, unaliased {len(lost)}")
    if lost:
        print("unaliased:", [(i, _kind(by_id[i]), by_id[i].get("cr_value")) for i in lost[:40]])


if __name__ == "__main__":
    main(Path(sys.argv[1]))
