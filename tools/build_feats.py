"""Turn the OGL feat spreadsheet into a machine-checkable index.

Run once against the author's `Feats_OGL.xlsx`; the output is committed and the workbook is
not needed to build or run the app.

    python tools/build_feats.py "C:/Users/natha/Downloads/Feats_OGL.xlsx"

The interesting half is the prerequisite parser. The spreadsheet states prerequisites as
prose — "Dex 15, Power Attack, base attack bonus +1." — and the whole reason to have feats
in a database rather than as a list of names is to be able to *ask* whether a character
qualifies. So each clause is classified into a typed condition, and anything that does not
classify is kept verbatim in `unparsed_prerequisites` rather than dropped or guessed at.

That bucket is the point. A parser that silently discards what it does not understand
produces a feat which looks freely available and is not, and the only symptom is a
character who was allowed to take something illegal. Measured on the shipped data: of
3,129 clauses, the typed patterns claim about four fifths, and the rest are recorded as
text a human can read.

The race vocabulary is read off the sheet's own `race_name` column rather than typed here.
Every attempt to write that list by hand missed tieflings, oreads and vishkanya, which are
exactly the ones that turn up in racial feat prerequisites.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "content" / "feats" / "feats.json"

# Split on commas *and semicolons* that are not inside parentheses: "Spell Focus
# (conjuration), Int 13" must not become "Spell Focus (conjuration" and "conjuration)".
#
# The semicolon was missed at first and it is not decorative — "Con 13; dwarf" is two
# conditions, and treating it as one left a dozen perfectly ordinary racial feats with an
# unparseable prerequisite.
SPLIT = re.compile(r"[,;]\s*(?![^()]*\))")

ABILITIES = {"str": "str", "dex": "dex", "con": "con", "int": "int", "wis": "wis",
             "cha": "cha", "strength": "str", "dexterity": "dex", "constitution": "con",
             "intelligence": "int", "wisdom": "wis", "charisma": "cha"}

SIZES = ("fine", "diminutive", "tiny", "small", "medium", "large", "huge", "gargantuan",
         "colossal")

# The classes a prerequisite may name. Kept as a set so "fighter level 4" is a class level
# and "Elemental Fist level 4" — which does not exist — falls through to the honest bucket
# instead of inventing a class called Elemental Fist.
CLASSES = {
    "alchemist", "antipaladin", "arcanist", "barbarian", "bard", "bloodrager", "brawler",
    "cavalier", "cleric", "druid", "fighter", "gunslinger", "hunter", "inquisitor",
    "investigator", "kineticist", "magus", "medium", "mesmerist", "monk", "ninja",
    "occultist", "oracle", "paladin", "psychic", "ranger", "rogue", "samurai", "shaman",
    "skald", "slayer", "sorcerer", "spiritualist", "summoner", "swashbuckler", "vigilante",
    "warpriest", "witch", "wizard",
}

RE_ABILITY = re.compile(
    r"^(str|dex|con|int|wis|cha|strength|dexterity|constitution|intelligence|wisdom|"
    r"charisma)\s+(\d+)\s*$", re.I)
RE_BAB = re.compile(r"base attack bonus\s*\+?\s*(\d+)", re.I)
RE_CASTER_LEVEL = re.compile(r"caster level\s+(\d+)", re.I)
RE_CHAR_LEVEL = re.compile(r"character level\s+(\d+)", re.I)
RE_CLASS_LEVEL_A = re.compile(r"(\d+)(?:st|nd|rd|th)[-\s]level\s+([a-z]+)", re.I)
RE_CLASS_LEVEL_B = re.compile(r"^([a-z]+)\s+level\s+(\d+)", re.I)
RE_SKILL_RANKS_A = re.compile(r"^([A-Za-z][\w \(\)'-]*?)\s+(\d+)\s+ranks?\b", re.I)
RE_SKILL_RANKS_B = re.compile(r"^(\d+)\s+ranks?\s+(?:in|of)\s+(.+)$", re.I)
RE_SIZE = re.compile(r"^(" + "|".join(SIZES) + r")\s+size(\s+or\s+(smaller|larger))?\s*$",
                     re.I)
RE_FIRST_LEVEL = re.compile(r"must be taken (?:as a .*? )?at (?:1st|first) level", re.I)
RE_MYTHIC = re.compile(r"(\d+)(?:st|nd|rd|th)\s+mythic tier", re.I)
# A run of 2-4 capitals straight after a lowercase letter is the source book's superscript,
# flattened by the export: "Powerful ShapeUM" is Powerful Shape, from Ultimate Magic.
RE_SOURCE_TAG = re.compile(r"(?<=[a-z])([A-Z]{2,4})$")
# "good alignment", "non-lawful", "nonlawful", "any chaotic alignment".
RE_ALIGNMENT = re.compile(
    r"^(?:any\s+)?(non-?)?(lawful|chaotic|good|evil|neutral)(\s+alignment)?\s*$", re.I)


def slug(name: str) -> str:
    """`Weapon Focus (rapier)` -> `weapon-focus-rapier`."""
    s = re.sub(r"[^a-z0-9]+", "-", str(name).strip().lower())
    return s.strip("-")


def clean(value) -> str:
    """Spreadsheet cells arrive as None, "None", or text with stray asterisks."""
    s = "" if value is None else str(value).strip()
    if s.lower() in ("none", "null", "n/a", "-", "—"):
        return ""
    # Trailing asterisks mark a footnote in the source and are not part of the name.
    return s.replace("\u2019", "'").strip().rstrip("*").strip()


def parse_clause(raw: str, feat_ids: dict[str, str], races: set[str]) -> dict | None:
    """One prerequisite clause as a typed condition, or None if it does not classify."""
    c = clean(raw).rstrip(".").strip()
    if not c:
        return None
    low = c.lower()
    bare = re.sub(r"\s*\([^)]*\)", "", c).strip().lower()

    # Feats first: a feat name may contain words every other pattern would claim, and the
    # name list is exact rather than a guess.
    if low in feat_ids:
        return {"kind": "feat", "feat": feat_ids[low], "name": c}
    if bare in feat_ids:
        return {"kind": "feat", "feat": feat_ids[bare], "name": c}

    # The source book's superscript survives the export glued to the name: "Powerful
    # ShapeUM", "Arcane BlastAPG". Stripped only when what is left is an actual feat, so
    # this cannot invent one — measured on the shipped data it recovers 48 clauses with a
    # single near-miss, and that one is a compound clause that fails anyway.
    tag = RE_SOURCE_TAG.search(c)
    if tag:
        trimmed = c[: -len(tag.group(1))].strip()
        for candidate in (trimmed.lower(),
                          re.sub(r"\s*\([^)]*\)", "", trimmed).strip().lower()):
            if candidate in feat_ids:
                return {"kind": "feat", "feat": feat_ids[candidate], "name": trimmed}

    m = RE_ABILITY.match(c)
    if m:
        return {"kind": "ability", "ability": ABILITIES[m.group(1).lower()],
                "value": int(m.group(2))}

    m = RE_BAB.search(c)
    if m:
        return {"kind": "bab", "value": int(m.group(1))}

    m = RE_CHAR_LEVEL.search(c)
    if m:
        return {"kind": "character_level", "value": int(m.group(1))}

    m = RE_CASTER_LEVEL.search(c)
    if m:
        return {"kind": "caster_level", "value": int(m.group(1))}

    m = RE_CLASS_LEVEL_A.search(c)
    if m and m.group(2).lower() in CLASSES:
        return {"kind": "class_level", "class": m.group(2).lower(),
                "value": int(m.group(1))}
    m = RE_CLASS_LEVEL_B.match(c)
    if m and m.group(1).lower() in CLASSES:
        return {"kind": "class_level", "class": m.group(1).lower(),
                "value": int(m.group(2))}

    m = RE_SKILL_RANKS_A.match(c)
    if m:
        return {"kind": "skill_ranks", "skill": m.group(1).strip().lower(),
                "ranks": int(m.group(2))}
    m = RE_SKILL_RANKS_B.match(c)
    if m:
        return {"kind": "skill_ranks", "skill": m.group(2).strip().lower().rstrip("."),
                "ranks": int(m.group(1))}

    m = RE_SIZE.match(c)
    if m:
        return {"kind": "size", "size": m.group(1).lower(),
                "or": (m.group(3) or "").lower()}

    if low in races:
        return {"kind": "race", "race": low}

    # "Half-orc or orc", "dwarf or gnome". Only when *every* alternative is a race — a
    # partial match here would quietly drop half a condition, which is worse than keeping
    # the whole clause as text.
    alternatives = [a.strip().lower() for a in re.split(r"\s+or\s+", low) if a.strip()]
    if len(alternatives) > 1 and all(a in races for a in alternatives):
        return {"kind": "race_any", "races": alternatives}

    m = RE_MYTHIC.search(c)
    if m:
        return {"kind": "mythic_tier", "value": int(m.group(1))}

    m = RE_ALIGNMENT.match(c)
    if m:
        return {"kind": "alignment", "component": m.group(2).lower(),
                "negated": bool(m.group(1))}

    if RE_FIRST_LEVEL.search(c):
        return {"kind": "first_level_only"}

    if "proficien" in low:
        return {"kind": "proficiency", "text": c}

    if "class feature" in low:
        return {"kind": "class_feature", "text": c}

    return None


def _same_feat(a: dict, b: dict) -> bool:
    """Is this the same feat reprinted, or a different one wearing the same name?

    Compared on the benefit text with whitespace and case flattened, because reprints
    differ in punctuation and hyphenation — "nonlawful" against "non-lawful" — and not in
    what the feat does.
    """
    def flat(s: str) -> str:
        return re.sub(r"[^a-z0-9]+", "", (s or "").lower())

    return flat(a.get("benefit", "")) == flat(b.get("benefit", ""))


def build(src: Path) -> dict:
    import openpyxl

    wb = openpyxl.load_workbook(src, read_only=True, data_only=True)
    ws = wb[wb.sheetnames[0]]
    rows = list(ws.iter_rows(values_only=True))
    header = [str(h or "").strip() for h in rows[0]]
    raw = [dict(zip(header, r)) for r in rows[1:] if r and r[1]]

    # Mythic Adventures gives 155 feats the same name as the ordinary feat they require —
    # the mythic Dodge's only prerequisite is Dodge. Slugging on name alone collapsed each
    # pair into one entry, losing 156 feats and leaving Power Attack listing itself as an
    # unmet prerequisite. Mythic feats therefore get their own id, and a prerequisite that
    # names a feat resolves to the *ordinary* one, which is what it means.
    base_names = {clean(d.get("name")).lower() for d in raw
                  if "mythic" not in clean(d.get("type")).lower()}

    def feat_id(d: dict) -> str:
        name = clean(d.get("name"))
        mythic = "mythic" in clean(d.get("type")).lower()
        if mythic and name.lower() in base_names:
            return slug(name) + "-mythic"
        return slug(name)

    # Two passes: the name index has to exist before any prerequisite can be resolved to a
    # feat, and a third of the clauses are feat names.
    feat_ids: dict[str, str] = {}
    races: set[str] = set()
    for d in raw:
        name = clean(d.get("name"))
        if not name:
            continue
        this = feat_id(d)
        # `setdefault`, so the ordinary feat claims the plain name and the mythic one
        # does not overwrite it.
        feat_ids.setdefault(name.lower(), this)
        feat_ids.setdefault(re.sub(r"\s*\([^)]*\)", "", name).strip().lower(), this)
        for bit in re.split(r"\s*(?:,|/|\bor\b)\s*", clean(d.get("race_name")).lower()):
            if bit.strip():
                races.add(bit.strip())

    flags = ("teamwork", "critical", "grit", "style", "performance", "racial",
             "companion_familiar")

    feats = []
    stats = {"clauses": 0, "typed": 0, "unparsed": 0, "fully_typed": 0, "with_prereqs": 0}
    for d in raw:
        name = clean(d.get("name"))
        if not name:
            continue
        text = clean(d.get("prerequisites"))
        conditions, leftovers = [], []
        if text:
            stats["with_prereqs"] += 1
            for clause in SPLIT.split(text.rstrip(".")):
                if not clean(clause):
                    continue
                stats["clauses"] += 1
                parsed = parse_clause(clause, feat_ids, races)
                if parsed is None:
                    stats["unparsed"] += 1
                    leftovers.append(clean(clause).rstrip("."))
                else:
                    stats["typed"] += 1
                    conditions.append(parsed)
            if not leftovers:
                stats["fully_typed"] += 1

        types = [t.strip().lower() for t in clean(d.get("type")).split(",") if t.strip()]
        feats.append({
            "id": feat_id(d),
            "name": name,
            "types": types,
            "description": clean(d.get("description")),
            "benefit": clean(d.get("benefit")),
            "normal": clean(d.get("normal")),
            "special": clean(d.get("special")),
            "source": clean(d.get("source")),
            "race": clean(d.get("race_name")).lower(),
            "prerequisites_text": text,
            "prerequisites": conditions,
            # Kept verbatim rather than dropped. A parser that discards what it does not
            # understand produces a feat that looks freely available and is not.
            "unparsed_prerequisites": leftovers,
            "tags": [f for f in flags if str(d.get(f) or "").strip() not in ("", "0", "0.0",
                                                                            "None")],
            "multiples": str(d.get("multiples") or "").strip() not in ("", "0", "0.0",
                                                                      "None"),
            "goal": clean(d.get("goal")),
            "completion_benefit": clean(d.get("completion_benefit")),
        })

    # Beyond the mythic pairs, thirteen ids still collide. Almost all are honest reprints
    # — Blood Vengeance appears in both the Advanced Race Guide and Orcs of Golarion — and
    # collapsing those to one entry is right. But `spider-step` is two genuinely different
    # feats sharing a name, and silently keeping one of them would lose a feat with no
    # symptom at all. So reprints merge and record the extra book; anything whose benefit
    # text actually differs is kept under its own source-qualified id.
    seen: dict[str, dict] = {}
    reprints = 0
    for f in feats:
        first = seen.get(f["id"])
        if first is None:
            seen[f["id"]] = f
            continue
        if _same_feat(first, f):
            reprints += 1
            first.setdefault("also_in", [])
            if f["source"] and f["source"] not in first["also_in"]:
                first["also_in"].append(f["source"])
        else:
            f["id"] = f"{f['id']}-{slug(f['source'])}"
            seen[f["id"]] = f
    feats = list(seen.values())
    stats["reprints_merged"] = reprints

    feats.sort(key=lambda f: f["name"].lower())
    return {
        "schema": 1,
        "source": src.name,
        "source_note": "Pathfinder OGL feat data, sheet dated 2014-03-23.",
        "licence": "Open Game Content, Open Game License v1.0a. The licence text must "
                   "travel with any build that ships this file.",
        "counts": {"feats": len(feats), **stats},
        "races_seen": sorted(races),
        "feats": feats,
    }


def main() -> int:
    src = Path(sys.argv[1] if len(sys.argv) > 1
               else Path.home() / "Downloads" / "Feats_OGL.xlsx")
    if not src.is_file():
        print(f"no such workbook: {src}")
        return 1

    data = build(src)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(data, indent=1, ensure_ascii=False), encoding="utf-8")

    c = data["counts"]
    typed_pct = 100 * c["typed"] / c["clauses"] if c["clauses"] else 0
    whole_pct = 100 * c["fully_typed"] / c["with_prereqs"] if c["with_prereqs"] else 0
    print(f"{OUT.relative_to(ROOT)}: {c['feats']} feats")
    print(f"  {c['with_prereqs']} have prerequisites, {c['clauses']} clauses")
    print(f"  {c['typed']} typed ({typed_pct:.1f}%), {c['unparsed']} kept as text")
    print(f"  {c['fully_typed']} feats fully machine-checkable ({whole_pct:.1f}%)")
    print(f"  {len(data['races_seen'])} races read off the sheet's own column")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
