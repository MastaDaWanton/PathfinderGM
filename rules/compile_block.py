"""A stat block compiled once into what play reads: its attacks and what it carries.

docs/compiled-bestiary-plan.md, step 6 of the bestiary rebuild (owner, 2026-10-28: "get all
creatures set up so there is no interpretation"). Until this, every creature's printed lines
were read at play time — the attack lines by `statblock_attacks` on every swing, possession
guessed from the attack lines (`Actor.take_up_printed_arms`), coin and kit derived from XP
(`bestiary._assemble_kit`) while the book's own Gear line sat unread in the spreadsheet.

The prior art is Foundry PF1's statblock converter: a block is converted ONCE, at import,
into stored actor data, and its changelog moved toward attacks found from the carried
weapons (v4.6.0, "find attacks from inventory weapons") with the integrated ones — the
armour spikes, the shield bash — processed without an item (v5.9.0). That is this shape:

    {"attacks": {"melee": [[attack, ...], ...], "ranged": [...]},   # the book's "or" / ","
     "carries": [item, ...],
     "unread":  ["what could not be accounted for", ...],
     "source_hash": "...", "compiler": COMPILER}

Each attack is exactly what `statblock_attacks.parse` reads, plus:

- `class`: `item` (a carried made weapon, `item` the index into `carries`), `natural`
  (bite, claw), `fist` (the unarmed strike, a flurry), `body` (touch, tendrils, swarm,
  troop), `thrown_object` (a giant's rock), `worn` (armour spikes, a shield bash) or
  `ability` (a bomb);
- `mode`: "flurry" for a flurry of blows, which is a way of attacking, not a weapon.

Each carried item: `printed` (as the book wrote it), `key` and `table` (`goods.known_item`:
weapon, ammunition, armour, shield, gear — or `potion`, `coin`, `magic item`, or "" when
nothing resolves it), `count`, `enhancement`, `masterwork`, `material`, `properties`,
`charges`, and `slot` (hand, armour, shield, pack, coin).

Nothing is guessed: a piece no table knows keeps its printed words, has an empty `key`, and
is listed in `unread`, which the shipped-content test counts and may only shrink. The
compile is deterministic code over printed text — no model reads a stat block.

`source_hash` is the hash of the lines it was compiled from and `compiler` this module's
version (CLAUDE.md: version-stamp anything derived and compare content, not timestamps):
a block edited after its compile has a stale record, and `record_for` refuses to answer
with one.
"""
from __future__ import annotations

import hashlib
import json
import re

# Bump when the compile's output changes for the same input: every shipped record is then
# stale and the content test names the command that rewrites them.
COMPILER = 1

# The lines a record is compiled from. Change one and the record is stale.
SOURCE_FIELDS = ("melee", "ranged", "printed_gear", "printed_other_gear")

# CRB Chapter 6, "Special Materials", the ones a stat block's gear prints.
MATERIALS = ("alchemical silver", "cold iron", "adamantine", "mithral", "darkwood",
             "dragonhide", "silver")

# The sourcebook marks the index glues onto an item's name ("manacles of cooperationAPG",
# "throwing shieldUE"): Paizo's abbreviations for the book an item comes from.
_BOOK_MARKS = re.compile(
    r"(?:(?<=[a-z\)])|\s)(?:APG|ACG|ARG|UC|UE|UM|ISWG|ISG|OA|UI|HA|MA|B[1-6])\b")
_NUMBER_WORDS = {"two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7,
                 "eight": 8, "nine": 9, "ten": 10, "twelve": 12, "twenty": 20}
_COIN = re.compile(r"^(\d[\d,]*)\s*(pp|gp|sp|cp)$", re.I)
_TRAILING_COUNT = re.compile(r"\s*\((\d+)\)$")
_CHARGES = re.compile(r"\s*\((?:[^()]*?)(\d+)\s+charges?\)$", re.I)
_PAREN = re.compile(r"\s*\([^()]*\)")
_WITH = re.compile(r"^(?P<item>.+?)\s+with\s+(?P<n>\d+)\s+(?P<ammo>[a-z' -]+)$", re.I)
_PLUS = re.compile(r"^\+(\d)(?:/\+\d)?\s+")
_MWK = re.compile(r"^(?:mwk|masterwork)\s+", re.I)
_OF = re.compile(r"^(potion|oil|scroll|wand|elixir)s?\s+of\s+", re.I)
_MAGIC_WORDS = re.compile(r"\b(?:ring|cloak|amulet|belt|headband|bracers|boots|gloves|"
                          r"gauntlets|goggles|eyes|circlet|robe|vest|stone|pearl|rod|"
                          r"staff of|bag of|figurine|token|horn|lens|phylactery|periapt|"
                          r"scarab|brooch|necklace|hat|helm|mask|cape|mantle|wand|scroll)\b",
                          re.I)


def source_hash(block: dict) -> str:
    lines = [str((block or {}).get(f) or "") for f in SOURCE_FIELDS]
    return hashlib.sha1(json.dumps(lines, ensure_ascii=False).encode("utf-8")).hexdigest()[:16]


def _properties() -> list[str]:
    from django.conf import settings
    from pathlib import Path

    doc = json.loads((Path(settings.BASE_DIR) / "content" / "rules" / "magic-properties.json")
                     .read_text(encoding="utf-8"))
    names = {str(p.get("name") or "").lower() for p in doc.get("properties") or []}
    # Longest first, so "flaming burst" is one property and not "flaming" and a stray word.
    return sorted((n for n in names if n), key=len, reverse=True)


_PROPS: list[str] | None = None


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", str(text or "").lower()).strip("-")


def _singular(text: str) -> str:
    """The last word made one: "tanglefoot bags" -> "tanglefoot bag"."""
    words = str(text or "").split()
    if not words:
        return ""
    last = words[-1]
    if last.endswith("ies"):
        last = last[:-3] + "y"
    elif last.endswith(("ches", "shes", "xes", "sses")):
        last = last[:-2]
    elif last.endswith("s") and not last.endswith("ss"):
        last = last[:-1]
    return " ".join(words[:-1] + [last])


def _split(text: str) -> list[str]:
    from .statblock_attacks import _split_top

    # "1,150 gp" is one amount, not "1" and "150 gp".
    text = re.sub(r"(?<=\d),(?=\d{3}\b)", "", " ".join(str(text or "").split()))
    return [p for p in _split_top(text, ",") if p]


def item(printed: str) -> dict:
    """One printed piece of gear as a carried item. Never a guess: what no table resolves
    keeps its printed words and an empty `key`."""
    global _PROPS
    from . import goods

    if _PROPS is None:
        _PROPS = _properties()
    raw = _BOOK_MARKS.sub("", " ".join(str(printed or "").split())).strip(" .;")
    out = {"printed": raw, "key": "", "table": "", "count": 1, "enhancement": 0,
           "masterwork": False, "material": "", "properties": [], "charges": 0,
           "slot": "pack"}
    coin = _COIN.match(raw)
    if coin:
        out.update(key=coin.group(2).lower(), table="coin", slot="coin",
                   count=int(coin.group(1).replace(",", "")))
        return out
    # "3d6 gp" (the drow's purse): rolled when the body is first looked at, like any kit.
    rolled = re.match(r"^(\d+d\d+(?:\s*[+-]\s*\d+)?)\s*(pp|gp|sp|cp)$", raw, re.I)
    if rolled:
        out.update(key=rolled.group(2).lower(), table="coin", slot="coin", count=0,
                   dice=rolled.group(1).replace(" ", ""))
        return out
    text = raw
    ch = _CHARGES.search(text)
    if ch:
        out["charges"] = int(ch.group(1))
        text = text[:ch.start()]
    cnt = _TRAILING_COUNT.search(text)
    if cnt:
        out["count"] = int(cnt.group(1))
        text = text[:cnt.start()]
    low = text.lower()
    # A composite bow's strength rating and any other qualifier in parentheses
    # ("(+4 Str)", "(anchor)", "(2nd)") are not the thing's name.
    low = _PAREN.sub("", low).strip()
    # "4 javelins", "12 +2 flaming darts", "2 doses of Medium spider venom".
    lead = re.match(r"^(\d+|" + "|".join(_NUMBER_WORDS) + r")\s+(?:doses?\s+of\s+)?(?=[a-z+])",
                    low)
    if lead:
        word = lead.group(1)
        out["count"] = int(word) if word.isdigit() else _NUMBER_WORDS[word]
        low = low[lead.end():]
    plus = _PLUS.match(low)
    if plus:
        out["enhancement"] = int(plus.group(1))
        out["masterwork"] = True          # every magic weapon and suit is masterwork
        low = low[plus.end():]
    mwk = _MWK.match(low)
    if mwk:
        out["masterwork"] = True
        low = low[mwk.end():]
    # The brewed and the bought are looked up on their whole name first; a property or a
    # material is only ever a weapon's or a suit's. The first cut stripped them first and
    # read "potion of bull's strength" as a potion of bull's with the strength property.
    found = _made_thing(low, out)
    if found:
        return out
    of = _OF.match(low)
    # Brewed things by the alchemy catalogue's own ids (`formulae.all()`, 485 rows: every
    # spell potion and oil, and the classics — tanglefoot bag, thunderstone): the first
    # cut looked only at the 44 potions a shop sells and left "potion of bull's strength"
    # (40 blocks) unread. "potions of" and "tanglefoot bags" are the one and the many.
    from . import formulae

    book = formulae.all()
    if of and of.group(1).lower() in ("potion", "oil", "elixir"):
        rest = _slug(low[of.end():])
        lead = of.group(1).lower()
        for cand in (f"{lead}-of-{rest}", f"potion-of-{rest}", f"oil-of-{rest}"):
            if cand in book:
                out.update(key=cand, table="potion")
                return out
        out["table"] = "potion"
        return out
    for cand in (_slug(low), _slug(_singular(low))):
        if cand in book:
            out.update(key=cand, table="alchemy")
            return out
    for cand in (low, _singular(low)):
        if goods.GEAR.get(cand) is not None:
            out.update(key=cand, table="gear")
            return out
    # Now a weapon or a suit under its properties and material: "+1 flaming longsword",
    # "mwk cold iron dagger", "+1 light fortification breastplate".
    bare = low
    props, material = [], ""
    for prop in _PROPS:
        if re.search(rf"\b{re.escape(prop)}\b", bare):
            props.append(prop)
            bare = re.sub(rf"\b{re.escape(prop)}\b", " ", bare)
    for mat in MATERIALS:
        if re.search(rf"\b{mat}\b", bare):
            material = mat
            bare = re.sub(rf"\b{mat}\b", " ", bare)
            break
    bare = " ".join(bare.split())
    if bare != low and _made_thing(bare, out):
        out["properties"], out["material"] = props, material
        return out
    if _MAGIC_WORDS.search(low) or of:
        out["table"] = "magic item"
    return out


# What the tables name another way: "bullets" are the sling's.
_ITEM_ALIASES = {"bullets": "sling bullets", "bullet": "sling bullets"}


def _weapon_key(key: str) -> str:
    from . import weapons as weapons_mod

    return weapons_mod.key_for(str(key or "").replace("-", " ")) or str(key or "")


def _made_thing(low: str, out: dict) -> bool:
    """A weapon, round, suit or shield the Core tables know (`goods.known_item`), by the
    name, its alias or its singular; fills `out` and says whether it did."""
    from . import goods

    for cand in dict.fromkeys((low, _ITEM_ALIASES.get(low, ""), _singular(low))):
        found = goods.known_item(cand) if cand else None
        if found:
            table = str(found["table"])
            out.update(key=str(found["key"]), table=table,
                       slot={"armour": "armour", "shield": "shield"}.get(table, "pack"))
            return True
    return False


def carries(block: dict) -> list[dict]:
    out: list[dict] = []
    for field in ("printed_gear", "printed_other_gear"):
        for piece in _split(block.get(field) or ""):
            w = _WITH.match(piece)
            if w:
                out.append(item(w.group("item")))
                ammo = item(f"{w.group('ammo')} ({w.group('n')})")
                out.append(ammo)
            else:
                out.append(item(piece))
    return out


def _class(a: dict) -> tuple[str, str]:
    from . import weapons as weapons_mod

    name = str(a.get("name") or "").lower()
    mode = "flurry" if "flurry" in name else ""
    if a.get("automatic"):
        return "body", mode
    base = str(a.get("base") or "")
    if base == "unarmed":
        return "fist", mode
    if a.get("natural"):
        return "natural", mode
    if re.search(r"\bspike[sd]?\b|\bshield bash\b", name):
        return "worn", mode
    if re.search(r"\bbombs?\b", name):
        return "ability", mode
    if re.search(r"\brocks?\b|\bboulders?\b", name) and not base:
        return "thrown_object", mode
    if base and weapons_mod.wieldable(base)[0]:
        return "item", mode
    return "body", mode


def attacks(block: dict) -> tuple[dict, list[str]]:
    from .statblock_attacks import _attack, _clean, _split_top, of_block

    parsed = of_block(block)
    unread: list[str] = []
    for cat in ("melee", "ranged"):
        for opt in _split_top(_clean(block.get(cat) or ""), " or "):
            for piece in _split_top(opt, ","):
                if _attack(piece, cat) is None:
                    unread.append(f"{cat}: {piece}")
        for option in parsed[cat]:
            for a in option:
                a["class"], a["mode"] = _class(a)
    return parsed, unread


def compile_block(block: dict) -> dict:
    """The whole record for one block. An `item` attack points at the carried thing it
    stands on (`item`, an index into `carries`), matched by weapon and enhancement; one
    the gear line does not list is still `item` with no index — the print says it has it,
    and the Gear line, where the book prints one, is the possession the record keeps."""
    atk, unread = attacks(block)
    carried = carries(block)
    for it in carried:
        if not it["key"] and it["table"] != "magic item":
            unread.append(f"gear: {it['printed']}")
    for cat in ("melee", "ranged"):
        for option in atk[cat]:
            for a in option:
                if a["class"] != "item":
                    continue
                plus = re.match(r"\+(\d)", str(a.get("name") or ""))
                want = int(plus.group(1)) if plus else 0
                # Both sides through the weapons table's one resolver: the attack line
                # prints "shortsword", "daggers", "scimitars" where the gear prints
                # "short sword", "dagger", "two +1 scimitars".
                base = _weapon_key(a["base"])
                idx = next((i for i, it in enumerate(carried)
                            if _weapon_key(it["key"]) == base
                            and it["enhancement"] == want), None)
                if idx is None:
                    idx = next((i for i, it in enumerate(carried)
                                if _weapon_key(it["key"]) == base), None)
                a["item"] = idx
    return {"attacks": atk, "carries": carried, "unread": unread,
            "source_hash": source_hash(block), "compiler": COMPILER}


# --- the shipped records ------------------------------------------------------------------

_RECORDS: dict | None = None


def records() -> dict[str, dict]:
    """content/bestiary/compiled.json, keyed by creature id (tools/compile_bestiary.py)."""
    global _RECORDS
    if _RECORDS is None:
        from django.conf import settings
        from pathlib import Path

        from pathfindergm import files

        path = Path(settings.BASE_DIR) / "content" / "bestiary" / "compiled.json"
        try:
            doc = json.loads(path.read_text(encoding="utf-8"))
            _RECORDS = dict(doc.get("creatures") or {}) \
                if int(doc.get("compiler") or 0) == COMPILER else {}
        except FileNotFoundError:
            _RECORDS = {}
        except Exception as exc:  # noqa: BLE001 — a bad file is no records, reported
            files.unreadable(path, exc)
            _RECORDS = {}
    return _RECORDS


def record_for(block: dict | None) -> dict | None:
    """The compiled record for this block, or None — none shipped, or the block has been
    changed since it was compiled (its lines no longer hash to the record's). A homebrew
    creature and a templated or rules-built one have none and are read live."""
    if not block or not block.get("id"):
        return None
    rec = records().get(str(block["id"]))
    if rec is None or rec.get("source_hash") != source_hash(block):
        return None
    return rec
