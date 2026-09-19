"""Turn the weapons workbook into an index the engine can use.

Run once against the author's `Pathfinder_Weapons_DB_filled_1.xlsx`; the output is
committed and the workbook is not needed to build or run the app.

    python tools/build_weapons.py "C:/Users/natha/Downloads/Pathfinder_Weapons_DB_filled_1.xlsx"

The sheet is a formatted document rather than a flat table: proficiency headings (SIMPLE,
MARTIAL, EXOTIC) alternate with section headings (Light Weapons, Ranged Weapons, Siege
Engines), and **each section carries its own column layout** — nine distinct ones. Firearms
add Misfire and Capacity; siege engines add Crew, Aim, Load and Speed and drop the small
damage column entirely.

Reading columns by position is therefore wrong, and wrong in the quiet way: a first survey
by position reported damage types of "50 lbs." and "1 lb." because a siege engine's weight
column had landed where the type column was. Columns 0-8 are read against whichever header
most recently preceded the row.

Believing the headers about the *last* four columns is wrong too, and that took a second
pass to find. Columns 9-12 are the component columns in all 456 rows, but only the very
first header labels them; the firearm and siege headers run past their own data and label
9 and 10 as Type and Special, while the cells beneath hold "Barrel", "Frame", "Grip". So
9-12 are mapped by position and the header is ignored there. Checked against every row
rather than assumed — see the test that no weapon has a weight where its damage type
should be.

The cost of that is real and worth saying: firearms and siege engines carry no Type or
Special in this sheet at all, and siege sections have no Speed. That is missing from the
source, not dropped here.

The component columns — Primary Head/Blade, Haft, Grip, Guard/Pommel — are the author's own
additions for the crafting system, not Open Game Content, and are carried through as
`components` so the craft tree can reach them.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "content" / "weapons" / "weapons.json"

PROFICIENCIES = {"simple", "martial", "exotic"}

# Header cell -> the key it becomes. Several spellings of the same column appear across
# sections ("Dmg" alone on siege rows, "Dmg (M)" everywhere else).
COLUMNS = {
    "name": "name", "cost": "cost", "dmg (s)": "damage_small", "dmg (m)": "damage",
    "dmg": "damage", "critical": "critical", "range": "range", "weight": "weight",
    "type": "type", "special": "special", "misfire": "misfire", "capacity": "capacity",
    "crew": "crew", "aim": "aim", "load": "load", "speed": "speed",
    "primary head/blade": "head", "haft/ hilt / stock": "haft",
    "grip / handle": "grip", "guard / pommel / hardware": "guard",
}

DASHES = {"", "—", "-", "–", "n/a"}

# The component columns sit at the end of every row and are labelled only once.
COMPONENTS_AT = 9
COMPONENT_COLUMNS = {9: "head", 10: "haft", 11: "grip", 12: "guard"}

# Single letters as the sheet writes them.
TYPE_LETTERS = {"b": "bludgeoning", "p": "piercing", "s": "slashing"}

RE_CRIT = re.compile(r"^(?:(\d+)\s*[-–]\s*20\s*/\s*)?x(\d+)$", re.I)
RE_RANGE = re.compile(r"(\d+)\s*ft", re.I)
RE_WEIGHT = re.compile(r"([\d.]+)\s*lb", re.I)
RE_COST = re.compile(r"([\d,.]+)\s*(gp|sp|cp)", re.I)
COIN = {"gp": 1.0, "sp": 0.1, "cp": 0.01}

# 1e: Weapon Finesse works with light melee weapons, plus the rapier, whip and spiked
# chain by name. Derived from the section for the light ones and listed for the three
# exceptions, because nothing in the sheet marks them.
FINESSE_BY_NAME = {"rapier", "whip", "spiked chain"}

# Four weapons print a dash in the Cost column — they cost nothing, because they are a
# stick, a strap and a sharpened stake (Core Rulebook Table 6-4, confirmed against
# d20pfsrd's weapon tables 2026-09-19: club, quarterstaff, sling and wooden stake all
# read "—"). The workbook's cost cell for them is empty, and an empty cell also means
# "the source does not say" for firearms and siege engines, so the two cases cannot be
# told apart by parsing. Named here instead: free is a fact about these four, not a
# property of a blank cell. It matters downstream — the outfitter would not stock an item
# it could not price, so five class kits were built from weapons the shop could not sell
# (docs/playtest-2026-09-18.md item 24).
FREE_BY_NAME = {"club", "quarterstaff", "sling", "wooden stake"}


def slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", str(name).strip().lower()).strip("-")


def clean(value) -> str:
    s = "" if value is None else str(value).strip()
    return "" if s.lower() in DASHES else s


def parse_crit(raw: str) -> tuple[int, int]:
    """"19-20/x2" -> (19, 2). A bare "x3" threatens only on a natural 20."""
    m = RE_CRIT.match(clean(raw).replace(" ", ""))
    if not m:
        return (20, 2)
    return (int(m.group(1)) if m.group(1) else 20, int(m.group(2)))


def parse_types(raw: str) -> list[str]:
    """"B or P" -> both, "B and P" -> both. The distinction between "or" and "and" is real
    in 1e — one is the wielder's choice, the other applies both at once — but damage
    reduction is the only thing that reads this today and it treats them alike, so both
    become a list and the wording is kept in `type_text` rather than guessed at."""
    text = clean(raw).lower()
    if not text:
        return []
    out = []
    for bit in re.split(r"\s*(?:,|\bor\b|\band\b|&|/)\s*", text):
        bit = bit.strip(" ()")
        if not bit:
            continue
        name = TYPE_LETTERS.get(bit, bit)
        if name and name not in out:
            out.append(name)
    return out


def parse_specials(raw: str) -> list[str]:
    text = clean(raw).lower()
    if not text:
        return []
    out = []
    for bit in re.split(r"\s*,\s*", text):
        bit = bit.strip()
        if bit and bit not in out:
            out.append(bit)
    return out


def parse_cost(raw: str, free: bool = False) -> float | None:
    """The price in gp, `0.0` for a weapon the rulebook prints free, `None` for unknown.

    The three answers are distinct on purpose: `None` means the source did not say and
    nothing may sell it, `0.0` means it costs nothing and a shop may hand it over.
    """
    m = RE_COST.search(clean(raw))
    if not m:
        return 0.0 if free else None
    return round(float(m.group(1).replace(",", "")) * COIN[m.group(2).lower()], 2)


def parse_number(raw: str, pattern: re.Pattern) -> float | None:
    m = pattern.search(clean(raw))
    return float(m.group(1)) if m else None


def hands_for(section: str) -> int:
    s = section.lower()
    if "two-handed" in s or "siege" in s:
        return 2
    return 1


def category_for(section: str) -> str:
    """melee or ranged, which is what `Actor.attack_modifiers` branches on."""
    s = section.lower()
    if any(w in s for w in ("ranged", "firearm", "ammunition", "siege", "explosive",
                            "thrown")):
        return "ranged"
    return "melee"


def build(src: Path) -> dict:
    import openpyxl

    wb = openpyxl.load_workbook(src, read_only=True, data_only=True)
    ws = wb[wb.sheetnames[0]]
    rows = [[("" if c is None else str(c).strip()) for c in r]
            for r in ws.iter_rows(values_only=True)]

    proficiency = ""
    section = ""
    layout: dict[int, str] = {}
    weapons: list[dict] = []
    skipped: list[str] = []

    for raw in rows:
        first = clean(raw[0]) if raw else ""
        rest = [c for c in raw[1:] if clean(c)]

        if first and not rest:
            if first.lower() in PROFICIENCIES:
                proficiency = first.lower()
                section = ""
            else:
                section = first
            continue

        if first.lower() == "name":
            # A new column layout starts here and applies until the next header.
            #
            # Only columns 0-8 are taken from the header. Columns 9-12 are *always* the
            # component columns, in all 456 rows, whatever the header claims — checked
            # against the whole sheet rather than assumed. Only the very first header
            # labels them; the firearm and siege headers run past their own data and
            # label 9 and 10 as Type and Special, but the cells underneath hold "Barrel",
            # "Frame", "Grip". Believing those headers put "Barrel" in the musket's damage
            # type.
            #
            # The cost is real and worth stating: firearms and siege engines have no Type
            # or Special in this sheet at all, and the siege sections lose Speed. That is
            # missing from the source, not dropped here.
            layout = {}
            for i, cell in enumerate(raw[:COMPONENTS_AT]):
                key = COLUMNS.get(clean(cell).lower())
                if key:
                    layout[i] = key
            layout.update(COMPONENT_COLUMNS)
            continue

        if not first or not layout:
            continue

        row = {key: clean(raw[i]) if i < len(raw) else ""
               for i, key in layout.items()}
        name = row.get("name", "")
        if not name:
            continue
        if not proficiency:
            skipped.append(name)
            continue

        crit_range, crit_mult = parse_crit(row.get("critical", ""))
        types = parse_types(row.get("type", ""))
        specials = parse_specials(row.get("special", ""))
        light = "light" in section.lower()

        weapons.append({
            "id": slug(name),
            "name": name,
            "prof": proficiency,
            "section": section,
            "category": category_for(section),
            "hands": hands_for(section),
            "light": light,
            # Keys below match rules/tables.WEAPONS so the overlay is a merge rather than
            # a translation layer.
            "damage": row.get("damage", "") or "",
            "damage_small": row.get("damage_small", "") or "",
            "crit_range": crit_range,
            "crit_mult": crit_mult,
            "type": types[0] if types else "untyped",
            "types": types,
            "type_text": row.get("type", ""),
            "finessable": light and category_for(section) == "melee"
                          or name.strip().lower() in FINESSE_BY_NAME,
            "traits": specials,
            "range_ft": parse_number(row.get("range", ""), RE_RANGE),
            "weight_lb": parse_number(row.get("weight", ""), RE_WEIGHT),
            "cost_gp": parse_cost(row.get("cost", ""),
                                  free=name.strip().lower() in FREE_BY_NAME),
            "cost_text": row.get("cost", "") or ("—" if name.strip().lower() in FREE_BY_NAME
                                                 else ""),
            "misfire": row.get("misfire", ""),
            "capacity": row.get("capacity", ""),
            "crew": row.get("crew", ""),
            "aim": row.get("aim", ""),
            "load": row.get("load", ""),
            "speed": row.get("speed", ""),
            # The author's own, for the craft tree. Not Open Game Content.
            "components": {k: row.get(k, "") for k in ("head", "haft", "grip", "guard")
                           if row.get(k)},
        })

    # Names repeat across sections rarely but they do (a weapon listed as both simple and
    # exotic in different forms). Keep the first and qualify the rest, so nothing is lost
    # to a silent overwrite — the same failure the feats import had.
    seen: dict[str, dict] = {}
    requalified = 0
    for w in weapons:
        if w["id"] not in seen:
            seen[w["id"]] = w
            continue
        w["id"] = f"{w['id']}-{slug(w['section'])}"
        if w["id"] in seen:
            continue
        requalified += 1
        seen[w["id"]] = w

    out = sorted(seen.values(), key=lambda w: w["name"].lower())
    return {
        "schema": 1,
        "source": src.name,
        "source_note": "Pathfinder 1st Edition weapon statistics.",
        "licence": "Open Game Content, Open Game License v1.0a — see OGL.txt. The "
                   "component columns (head, haft, grip, guard) are the author's own "
                   "additions for crafting and are not Open Game Content.",
        "counts": {
            "weapons": len(out),
            "requalified_names": requalified,
            "skipped_before_any_heading": len(skipped),
            "reach": sum(1 for w in out if "reach" in w["traits"]),
            "finessable": sum(1 for w in out if w["finessable"]),
        },
        "weapons": out,
    }


def main() -> int:
    src = Path(sys.argv[1] if len(sys.argv) > 1
               else Path.home() / "Downloads" / "Pathfinder_Weapons_DB_filled_1.xlsx")
    if not src.is_file():
        print(f"no such workbook: {src}")
        return 1

    data = build(src)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(data, indent=1, ensure_ascii=False), encoding="utf-8")

    c = data["counts"]
    print(f"{OUT.relative_to(ROOT)}: {c['weapons']} weapons")
    print(f"  {c['reach']} with reach, {c['finessable']} finessable")
    if c["requalified_names"]:
        print(f"  {c['requalified_names']} names appeared in two sections and were "
              f"qualified by section")
    if c["skipped_before_any_heading"]:
        print(f"  {c['skipped_before_any_heading']} rows before any proficiency heading, "
              f"skipped")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
