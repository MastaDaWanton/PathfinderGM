"""Import The Spell Codex spreadsheet into the app's spell data.

Two sources were offered. A JSON dump of 2,827 spells had the canonical descriptors
stripped out — `[fire]`, `[mind-affecting]` and the rest survived in four stray brackets
out of nearly three thousand entries — so tagging from it would have meant *deriving*
things Paizo had already stated, and deriving what is already authoritative is how a
corpus fills up with confident mistakes.

The Codex has all twenty-six descriptors as their own columns, subschool separate from
school, and a spell level column per class. So the descriptors and the spell lists are
read, not guessed, and only the functional tags — the "DoT", "buff", "control" kind, which
Pathfinder does not define — are derived. Those are marked as derived so the two can never
be confused.

Run:  python tools/build_spells.py "The Spell Codex.xlsx" content/spells/spells.json
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import openpyxl

# The 26 canonical descriptors, exactly as the Codex names them. Read from columns, never
# inferred: a descriptor is a rules fact with mechanical consequences (a [fire] spell is
# stopped by fire immunity), and guessing one is worse than having none.
DESCRIPTOR_COLUMNS = [
    "[Acid]", "[Air]", "[Chaotic]", "[Cold]", "[Curse]", "[Darkness]", "[Death]",
    "[Disease]", "[Draconic]", "[Earth]", "[Electricity]", "[Emotion]", "[Evil]",
    "[Fear]", "[Fire]", "[Force]", "[Good]", "[Language-Dependent]", "[Lawful]",
    "[Light]", "[Meditative]", "[Mind-Affecting]", "[Pain]", "[Poison]", "[Ruse]",
    "[Shadow]", "[Sonic]", "[Water]",
]

# Every class with a spell list in the Codex. The "X vs. Y" columns beside them are the
# spreadsheet's own comparison helpers, not spell lists, and are deliberately absent.
CLASS_COLUMNS = [
    "Arcanist", "Wizard", "Sorcerer", "Witch", "Magus", "Bard", "Skald", "Summoner",
    "UnSummoner", "Bloodrager", "Shaman", "Druid", "Hunter", "Ranger", "Cleric",
    "Oracle", "Warpriest", "Inquisitor", "Antipaladin", "Paladin", "Alchemist",
    "Investigator", "Psychic", "Mesmerist", "Occultist", "Spiritualist", "Medium",
]

COMPONENT_COLUMNS = {
    "Verbal": "V", "Somatic": "S", "Material": "M", "Focus": "F", "Divine Focus": "DF",
}


def cell(value):
    """The Codex writes an em dash for "no". Everything else is a value."""
    if value is None:
        return None
    s = str(value).strip()
    if s in ("", "—", "-", "–"):
        return None
    return s


def flag(value) -> bool:
    return cell(value) is not None


def level(value) -> int | None:
    s = cell(value)
    if s is None:
        return None
    try:
        return int(float(s))
    except ValueError:
        return None


def slug(name: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", (name or "").lower()).strip("-")
    return s or "spell"


# --- derived tags -------------------------------------------------------------------------
#
# What a spell is *for*. Pathfinder does not define these, so every one is derived and says
# so. They exist to make three thousand spells searchable; they are never rules.

def derive_tags(row: dict) -> list[str]:
    tags: list[str] = []
    desc = (row.get("description") or "").lower()
    school = (row.get("school") or "").lower()
    sub = (row.get("subschool") or "").lower()
    dur = (row.get("duration") or "").lower()
    save = (row.get("saving_throw") or "").lower()
    area = " ".join(str(row.get(k) or "") for k in ("area", "effect", "targets")).lower()
    rng = (row.get("range") or "").lower()

    def add(t):
        if t not in tags:
            tags.append(t)

    # What it does.
    damages = bool(re.search(r"\d+d\d+\s+(?:points? of\s+)?\w*\s*damage|deals?\s+\d",
                             desc))
    if damages:
        add("damage")
    # Damage that repeats is the "DoT" the request names: harm plus a duration that is not
    # instantaneous, plus the spell saying it happens again.
    if damages and re.search(r"each round|per round|every round|each turn", desc) \
            and "instantaneous" not in dur:
        add("dot")
    if re.search(r"\bcures?\b|\bheals?\b|restores? \d|hit points? (?:are )?restored", desc) \
            or sub == "healing":
        add("healing")
    if re.search(r"\+\d+\s+\w*\s*bonus", desc) or "(harmless)" in save:
        add("buff")
    if re.search(r"[-–]\d+\s+\w*\s*penalty", desc):
        add("debuff")
    if sub in ("summoning", "calling") or re.search(r"\bsummons?\b", desc):
        add("summoning")
    if sub == "teleportation" or re.search(r"\bteleport|\bfly\b|speed increases", desc):
        add("movement")
    if school == "divination" or re.search(r"\bdetects?\b|\bscry", desc):
        add("detection")
    if school == "abjuration" or re.search(r"resistance to|immunity to|deflection bonus",
                                           desc):
        add("defence")
    if sub in ("compulsion", "charm") or re.search(
            r"\bentangled?\b|\bparalyz|\bstunned?\b|\bdazed?\b|cannot move|"
            r"\bheld?\b|\bsleep\b", desc):
        add("control")
    if school == "illusion":
        add("illusion")
    if not tags:
        add("utility")

    # How it is delivered.
    if re.search(r"\bburst\b|\bcone\b|\bline\b|\bspread\b|\bemanation\b|\bradius\b", area):
        add("aoe")
    if rng.startswith("touch"):
        add("touch")
    elif rng.startswith("personal"):
        add("personal")
    elif rng:
        add("ranged")

    # When it ends.
    if "concentration" in dur:
        add("sustained")
    if "instantaneous" in dur:
        add("instant")
    if "permanent" in dur:
        add("permanent")

    # What the save does, which is the first thing anyone filters on in play.
    if "harmless" in save:
        add("harmless")
    elif "negates" in save:
        add("save-negates")
    elif "half" in save:
        add("save-half")
    elif "partial" in save:
        add("save-partial")
    elif not save or save == "none":
        add("no-save")
    return tags


def build(src: Path, out: Path) -> dict:
    wb = openpyxl.load_workbook(src, read_only=True, data_only=True)
    ws = wb["The Spell Codex"]
    rows = ws.iter_rows(values_only=True)
    header = [str(h or "").strip() for h in next(rows)]
    at = {h: i for i, h in enumerate(header)}
    # The name column's header carries a line break and the AoN hyperlink note.
    name_col = next(i for i, h in enumerate(header) if h.lower().startswith("spell name"))

    spells = []
    seen: set[str] = set()
    for raw in rows:
        def col(key):
            i = at.get(key)
            return raw[i] if i is not None and i < len(raw) else None

        name = cell(raw[name_col] if name_col < len(raw) else None)
        if not name:
            continue

        sid = slug(name)
        if sid in seen:
            continue
        seen.add(sid)

        lists = {}
        for klass in CLASS_COLUMNS:
            lvl = level(col(klass))
            if lvl is not None:
                lists[klass.lower()] = lvl

        components = [short for column, short in COMPONENT_COLUMNS.items()
                      if flag(col(column))]

        spell = {
            "id": sid,
            "name": name,
            "school": (cell(col("School")) or "").lower(),
            "subschool": (cell(col("Subschool")) or "").lower(),
            # Read, never inferred.
            "descriptors": [c.strip("[]").lower() for c in DESCRIPTOR_COLUMNS
                            if flag(col(c))],
            "lists": lists,
            "casting_time": cell(col("Casting Time")) or "",
            "range": cell(col("Range")) or "",
            "area": cell(col("Area")) or "",
            "effect": cell(col("Effect")) or "",
            "targets": cell(col("Targets")) or "",
            "duration": cell(col("Duration")) or "",
            "saving_throw": cell(col("Saving Throw")) or "",
            "spell_resistance": cell(col("Spell Resistance")) or "",
            "components": components,
            "component_cost": cell(col("Component Costs")) or "",
            "dismissible": flag(col("Dismissible")),
            "shapeable": flag(col("Shapeable")),
            "source": cell(col("Sourcebook")) or "",
            "description": cell(col("Description")) or "",
            "deity": cell(col("Deity")) or "",
            "domain": cell(col("Domain")) or "",
            "bloodline": cell(col("Bloodline")) or "",
            "patron": cell(col("Patron")) or "",
            "sla_level": level(col("SLA Level")),
        }
        spell["tags"] = derive_tags(spell)
        spells.append(spell)

    payload = {
        "source": src.name,
        "note": ("Descriptors and spell lists are read from The Spell Codex, not derived: "
                 "a descriptor is a rules fact with mechanical consequences and guessing "
                 "one is worse than having none. `tags` are ours, derived from the text "
                 "to make three thousand spells searchable, and are never rules."),
        "descriptors": [c.strip("[]").lower() for c in DESCRIPTOR_COLUMNS],
        "classes": [c.lower() for c in CLASS_COLUMNS],
        "spells": sorted(spells, key=lambda s: s["name"].lower()),
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=1, ensure_ascii=False), encoding="utf-8")
    return payload


if __name__ == "__main__":
    import collections

    data = build(Path(sys.argv[1]), Path(sys.argv[2]))
    spells = data["spells"]
    print(f"spells        {len(spells)}")
    print(f"file          {Path(sys.argv[2]).stat().st_size / 1e6:.1f} MB")
    print()
    print("schools:")
    for k, n in collections.Counter(s["school"] for s in spells).most_common():
        print(f"  {n:5}  {k or '(none)'}")
    print()
    print("descriptors (read from the Codex):")
    d = collections.Counter(x for s in spells for x in s["descriptors"])
    for k, n in d.most_common(12):
        print(f"  {n:5}  {k}")
    print(f"  ...{len(d)} distinct, {sum(1 for s in spells if s['descriptors'])} spells carry one")
    print()
    print("derived tags:")
    t = collections.Counter(x for s in spells for x in s["tags"])
    for k, n in t.most_common(16):
        print(f"  {n:5}  {k}")
    print()
    print("spell lists:")
    c = collections.Counter(k for s in spells for k in s["lists"])
    for k, n in c.most_common(8):
        print(f"  {n:5}  {k}")
    print(f"  ...{len(c)} classes; "
          f"{sum(1 for s in spells if len(s['lists']) > 1)} spells on more than one list")
