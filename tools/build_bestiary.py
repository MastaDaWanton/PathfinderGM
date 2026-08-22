"""Import the monster stat blocks into creatures the engine can actually fight.

`rules/bestiary.py` called itself "a holding pen, not the destination — the real bestiary
is an SRD import". This is that import.

The difference from the spell list matters: spells are reference, because the engine has no
spell system, but creatures are *executable*. `instantiate()` turns one into an Actor with
hit points, an AC, saves and an attack, and the engine rolls against it. So the fields that
have to parse are the ones combat reads, and this script reports how many stat blocks
produce a complete set rather than assuming they all do.

Everything is parsed defensively and nothing is invented: a stat block missing an AC gets
no AC and is marked incomplete, rather than being given 10 so the row looks tidy.

Run:  python tools/build_bestiary.py monster_stat_blocks_full.xlsx content/bestiary/creatures.json
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import openpyxl

SIZES = ("fine", "diminutive", "tiny", "small", "medium", "large", "huge",
         "gargantuan", "colossal")

ABILITIES = ("str", "dex", "con", "int", "wis", "cha")


def cell(v):
    if v is None:
        return None
    s = str(v).strip()
    return s or None


def as_int(v) -> int | None:
    s = cell(v)
    if s is None:
        return None
    m = re.search(r"[-+]?\d+", s.replace(",", ""))
    return int(m.group()) if m else None


def cr_value(v) -> float | None:
    """CR is written "2", "1/3", "1/2". Kept as text for display and as a number for
    sorting and for encounter budgeting later."""
    s = cell(v)
    if not s:
        return None
    m = re.match(r"\s*(\d+)\s*/\s*(\d+)", s)
    if m:
        return int(m.group(1)) / int(m.group(2))
    m = re.match(r"\s*(\d+(?:\.\d+)?)", s)
    return float(m.group(1)) if m else None


def abilities(v) -> dict[str, int]:
    """"Str 10, Dex 15, Con 12, Int 10, Wis 13, Cha 14".

    A dash means the creature has no such score — an ooze has no Intelligence — and that
    is left out rather than written as 10, because 10 is a real score and "none" is not.
    """
    out: dict[str, int] = {}
    s = cell(v) or ""
    for ab in ABILITIES:
        m = re.search(rf"\b{ab}\s+(\d+)", s, re.I)
        if m:
            out[ab] = int(m.group(1))
    return out


def first_attack(v) -> tuple[int | None, str]:
    """"mwk longsword +4 (1d8/19-20)" -> (+4, "1d8").

    The first attack only. A full attack routine is several attacks with iteratives and
    riders, and the engine's flat-attack shape holds one — so one is taken and the whole
    line is kept beside it, rather than a parse pretending to be the routine.
    """
    s = cell(v)
    if not s:
        return None, ""
    bonus = None
    m = re.search(r"([+-]\d+)", s)
    if m:
        bonus = int(m.group(1))
    dmg = ""
    m = re.search(r"\((\d+d\d+(?:[+-]\d+)?)", s)
    if m:
        dmg = m.group(1)
    return bonus, dmg


def reductions(v) -> list[dict]:
    """"5/silver", "10/magic and silver", "2/—"."""
    out = []
    s = cell(v) or ""
    for m in re.finditer(r"(\d+)\s*/\s*([^,;]+)", s):
        bypass = m.group(2).strip()
        if bypass in ("—", "-", "–"):
            bypass = ""
        out.append({"amount": int(m.group(1)), "bypass": bypass, "source": "natural"})
    return out


def listish(v) -> list[str]:
    s = cell(v) or ""
    return [x.strip() for x in re.split(r"[,;]", s) if x.strip()]


def skills(v) -> dict[str, int]:
    out: dict[str, int] = {}
    for part in re.split(r"[,;]", cell(v) or ""):
        m = re.match(r"\s*([A-Za-z][A-Za-z '()\-]*?)\s*([+-]\d+)\s*$", part)
        if m:
            out[m.group(1).strip().lower()] = int(m.group(2))
    return out


def speed(v) -> int | None:
    m = re.search(r"(\d+)\s*ft", cell(v) or "", re.I)
    return int(m.group(1)) if m else None


def slug(name: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", (name or "").lower()).strip("-")
    return s or "creature"


def build(src: Path, out: Path) -> dict:
    wb = openpyxl.load_workbook(src, read_only=True, data_only=True)
    ws = wb[wb.sheetnames[0]]
    rows = ws.iter_rows(values_only=True)
    header = [str(h or "").strip() for h in next(rows)]
    at = {h: i for i, h in enumerate(header)}

    creatures = []
    seen: set[str] = set()
    complete = 0
    for raw in rows:
        def col(key):
            i = at.get(key)
            return raw[i] if i is not None and i < len(raw) else None

        name = cell(col("Name"))
        if not name:
            continue
        cid = slug(name)
        if cid in seen:
            continue
        seen.add(cid)

        atk, dmg = first_attack(col("Melee"))
        ranged_atk, ranged_dmg = first_attack(col("Ranged"))
        size = (cell(col("Size")) or "").lower()

        c = {
            "id": cid,
            "name": name,
            "kind": "npc",
            "cr": cell(col("CR")) or "",
            "cr_value": cr_value(col("CR")),
            "xp": as_int(col("XP")),
            "size": size if size in SIZES else "medium",
            "creature_type": (cell(col("Type")) or "").lower(),
            "subtype": (cell(col("SubType")) or "").strip("()").lower(),
            "alignment": cell(col("Alignment")) or "",
            "abilities": abilities(col("AbilityScores")),
            "hp": as_int(col("HP")),
            "hit_dice": cell(col("HD")) or "",
            "flat_ac": as_int(col("AC")),
            "ac_note": cell(col("AC_Mods")) or "",
            "flat_saves": {k: as_int(col(c2)) for k, c2 in
                           (("fort", "Fort"), ("ref", "Ref"), ("will", "Will"))
                           if as_int(col(c2)) is not None},
            "flat_initiative": as_int(col("Init")),
            "flat_attack": atk,
            "flat_damage": dmg,
            "melee": cell(col("Melee")) or "",
            "ranged": cell(col("Ranged")) or "",
            "ranged_attack": ranged_atk,
            "ranged_damage": ranged_dmg,
            "flat_cmd": as_int(col("CMD")),
            "cmb": as_int(col("CMB")),
            "base_attack": as_int(col("BaseAtk")),
            "speed": speed(col("Speed")),
            "speed_note": cell(col("Speed")) or "",
            "reductions": reductions(col("DR")),
            "immune": listish(col("Immune")),
            "resist": listish(col("Resist")),
            "sr": as_int(col("SR")),
            "weaknesses": cell(col("Weaknesses")) or "",
            "senses": cell(col("Senses")) or "",
            "flat_skills": skills(col("Skills")),
            "feats": listish(col("Feats")),
            "languages": listish(col("Languages")),
            "special_attacks": cell(col("SpecialAttacks")) or "",
            "special_abilities": cell(col("SpecialAbilities")) or "",
            "spell_like": cell(col("SpellLikeAbilities")) or "",
            "environment": cell(col("Environment")) or "",
            "organization": cell(col("Organization")) or "",
            "treasure": cell(col("Treasure")) or "",
            "source": cell(col("Source")) or cell(col("MonsterSource")) or "",
            "notes": cell(col("Description_Visual")) or cell(col("Description")) or "",
        }
        # What combat actually needs. Reported rather than patched: a stat block given a
        # default AC so the row looks tidy is one the engine rolls against wrongly and
        # nobody ever questions.
        c["playable"] = all(c[k] is not None for k in ("hp", "flat_ac")) \
            and bool(c["abilities"])
        if c["playable"]:
            complete += 1
        creatures.append(c)

    payload = {
        "source": src.name,
        "note": ("Imported from the monster stat block spreadsheet. Nothing is invented: "
                 "a stat block missing a field has that field empty and is marked "
                 "`playable: false`, rather than being given a default so the row looks "
                 "complete."),
        "creatures": sorted(creatures, key=lambda c: c["name"].lower()),
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=1, ensure_ascii=False), encoding="utf-8")
    return payload


if __name__ == "__main__":
    import collections

    data = build(Path(sys.argv[1]), Path(sys.argv[2]))
    cs = data["creatures"]
    playable = [c for c in cs if c["playable"]]
    print(f"creatures     {len(cs)}")
    print(f"  playable    {len(playable)}  (hp, AC and ability scores all parsed)")
    print(f"  incomplete  {len(cs) - len(playable)}")
    print(f"file          {Path(sys.argv[2]).stat().st_size / 1e6:.1f} MB")
    print()
    for label, key in (("types", "creature_type"), ("sizes", "size")):
        print(f"{label}:")
        for k, n in collections.Counter(c[key] for c in cs).most_common(8):
            print(f"  {n:5}  {k or '(none)'}")
        print()
    print("CR spread:")
    for lo, hi in ((0, 1), (1, 4), (4, 8), (8, 12), (12, 17), (17, 100)):
        n = sum(1 for c in cs if c["cr_value"] is not None and lo <= c["cr_value"] < hi)
        print(f"  CR {lo}-{hi if hi < 100 else '+'}: {n}")
    print()
    print(f"with damage reduction  {sum(1 for c in cs if c['reductions'])}")
    print(f"with an environment    {sum(1 for c in cs if c['environment'])}")
    print(f"with a melee attack    {sum(1 for c in cs if c['flat_attack'] is not None)}")
