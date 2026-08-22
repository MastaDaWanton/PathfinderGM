"""Pull core bestiary stat blocks out of the Bestiary PDFs.

The spreadsheet import gave 6,406 creatures and no plain Ogre: it is a variant and NPC
bestiary, and its Environment column is empty. The core creatures and their ecology are in
the PDFs, and `reference/` already knows where — it indexed 816 creature anchors, each a
name, a page and a CR. That is the hard half of the problem already solved, so this walks
the anchors, reads the page, and parses the stat block.

Pathfinder stat blocks are rigidly formatted, which is why this is parsing rather than
guessing: `AC 17, touch 11, flat-footed 16`, `hp 30 (4d10+8)`, `Fort +6, Ref +2, Will +1`,
`Str 21, Dex 8, Con 15`. Every field is anchored on a keyword the layout guarantees.

The typography repair from `reference/build_reference.py` is reused rather than rewritten —
these PDFs render "flat" as "f lat" and "situation" as "s itu ation", and that was solved
once already.

Run:  python tools/extract_bestiary_pdfs.py H:/Pathfinder content/bestiary/core.json
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "reference"))

from pypdf import PdfReader  # noqa: E402

import build_reference as ref  # noqa: E402

sys.path.insert(0, str(ROOT))

from rules.statblock import RESISTANCE, trim  # noqa: E402

SIZES = ("fine", "diminutive", "tiny", "small", "medium", "large", "huge",
         "gargantuan", "colossal")
ALIGNMENTS = ("LG", "NG", "CG", "LN", "N", "CN", "LE", "NE", "CE")


def slug(name: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", (name or "").lower()).strip("-")
    return s or "creature"


def cr_value(text: str) -> float | None:
    m = re.match(r"\s*(\d+)\s*/\s*(\d+)", text or "")
    if m:
        return int(m.group(1)) / int(m.group(2))
    m = re.match(r"\s*(\d+)", text or "")
    return float(m.group(1)) if m else None


def _num(m, group=1) -> int | None:
    return int(m.group(group)) if m else None


def _between(text: str, start: str, *stops: str) -> str:
    """The run of text after a keyword and before the next one.

    Stat block lines have no punctuation to close them — the next keyword is the
    terminator — so every field is bounded by the labels that can follow it.
    """
    stop = "|".join(stops) if stops else r"$"
    m = re.search(rf"\b{start}\b\s+(.+?)(?=\s*(?:{stop})|$)", text, re.I | re.S)
    return re.sub(r"\s+", " ", m.group(1)).strip(" ;,.") if m else ""


def parse_block(text: str, name: str, cr: str) -> dict | None:
    """One stat block, or None if the page did not actually hold one."""
    t = re.sub(r"\s+", " ", text)

    ac = re.search(r"\bAC\s+(\d+)\s*,\s*touch\s+(\d+)\s*,\s*flat-?\s?footed\s+(\d+)", t, re.I)
    hp = re.search(r"\bhp\s+(\d+)\s*\(([^)]{2,40})\)", t, re.I)
    saves = re.search(r"\bFort\s*([+-]\s?\d+)\s*,\s*Ref\s*([+-]\s?\d+)\s*,\s*Will\s*([+-]\s?\d+)",
                      t, re.I)
    # Without an AC and hit points there is no creature here — the anchor pointed at a
    # page of prose, or the extraction failed. Reported, never invented.
    if not (ac and hp):
        return None

    abil = {}
    m = re.search(r"\bStr\s+(\d+|—|-)\s*,\s*Dex\s+(\d+|—|-)\s*,\s*Con\s+(\d+|—|-)\s*,\s*"
                  r"Int\s+(\d+|—|-)\s*,\s*Wis\s+(\d+|—|-)\s*,\s*Cha\s+(\d+|—|-)", t, re.I)
    if m:
        for key, raw in zip(("str", "dex", "con", "int", "wis", "cha"), m.groups()):
            if raw.isdigit():
                abil[key] = int(raw)

    head = re.search(rf"({'|'.join(ALIGNMENTS)})\s+({'|'.join(SIZES)})\s+([a-z]+)"
                     r"(?:\s*\(([^)]+)\))?", t, re.I)
    init = re.search(r"\bInit\s*([+-]\s?\d+)", t, re.I)
    cmd = re.search(r"\bCMD\s+(\d+)", t, re.I)
    cmb = re.search(r"\bCMB\s*([+-]\s?\d+)", t, re.I)
    bab = re.search(r"\bBase Atk\s*([+-]\s?\d+)", t, re.I)
    speed = re.search(r"\bSpeed\s+(\d+)\s*ft", t, re.I)
    sr = re.search(r"\bSR\s+(\d+)", t, re.I)

    melee = _between(t, "Melee", "Ranged", "Special Attacks", "STATISTICS", "Space",
                     "Reach", "TACTICS")
    atk = re.search(r"([+-]\d+)", melee)
    dmg = re.search(r"\((\d+d\d+(?:[+-]\d+)?)", melee)

    dr = []
    for m2 in re.finditer(r"\bDR\s+(\d+)\s*/\s*([^;,]+)", t, re.I):
        bypass = m2.group(2).strip()
        dr.append({"amount": int(m2.group(1)),
                   "bypass": "" if bypass in ("—", "-", "–") else bypass,
                   "source": "natural"})

    def sign(m2):
        return int(m2.group(1).replace(" ", "")) if m2 else None

    return {
        "id": slug(name),
        "name": name,
        "kind": "npc",
        "cr": cr,
        "cr_value": cr_value(cr),
        "size": (head.group(2).lower() if head else "medium"),
        "creature_type": (head.group(3).lower() if head else ""),
        "subtype": (head.group(4).lower() if head and head.group(4) else ""),
        "alignment": (head.group(1).upper() if head else ""),
        "abilities": abil,
        "hp": int(hp.group(1)),
        "hit_dice": hp.group(2).strip(),
        "flat_ac": int(ac.group(1)),
        "ac_note": f"touch {ac.group(2)}, flat-footed {ac.group(3)}",
        "flat_saves": {"fort": sign(re.match(r"([+-]\s?\d+)", saves.group(1))) if saves else None,
                       "ref": sign(re.match(r"([+-]\s?\d+)", saves.group(2))) if saves else None,
                       "will": sign(re.match(r"([+-]\s?\d+)", saves.group(3))) if saves else None}
        if saves else {},
        "flat_initiative": sign(init),
        "flat_attack": int(atk.group(1)) if atk else None,
        "flat_damage": dmg.group(1) if dmg else "",
        "melee": melee[:200],
        "ranged": _between(t, "Ranged", "Special Attacks", "STATISTICS", "Space",
                           "Reach", "TACTICS")[:200],
        "flat_cmd": _num(cmd),
        "cmb": sign(cmb),
        "base_attack": sign(bab),
        "speed": _num(speed),
        "reductions": dr,
        # `trim` on all three, because these are the only fields that split on commas and
        # so the only ones a runaway `_between` turns into a list of plausible short terms
        # rather than one visibly wrong long one. Every other field below is capped by a
        # slice for the same reason. See rules/statblock.py.
        "immune": trim([x.strip() for x in _between(t, "Immune", "Resist", "SR",
                                                    "Weaknesses", "OFFENSE").split(",")
                        if x.strip()]),
        "resist": trim([x.strip() for x in _between(t, "Resist", "SR", "Weaknesses",
                                                    "OFFENSE").split(",") if x.strip()],
                       shape=RESISTANCE),
        "sr": _num(sr),
        "senses": _between(t, "Senses", "DEFENSE", "Aura")[:160],
        "special_attacks": _between(t, "Special Attacks", "STATISTICS", "TACTICS")[:300],
        "languages": trim([x.strip() for x in
                           _between(t, "Languages", "SQ", "ECOLOGY", "SPECIAL").split(",")
                           if x.strip()]),
        # The gap the spreadsheet could not fill: this is what ties a creature to a biome.
        "environment": _between(t, "Environment", "Organization", "Treasure")[:120],
        "organization": _between(t, "Organization", "Treasure", "SPECIAL")[:160],
        "treasure": _between(t, "Treasure", "SPECIAL ABILITIES", "DESCRIPTION")[:120],
        "playable": True,
    }


BOOKS = {
    "bestiary-1": "Pathfinder Bestiary 1.pdf",
    "bestiary-2": "Pathfinder Bestiary 2.pdf",
    "bestiary-3": "pathfinder - bestiary 3.pdf",
    "bestiary-4": "Pathfinder Bestiary 4.pdf",
    "bestiary-5": "pathfinder - bestiary 5.pdf",
    "bestiary-6": "pathfinder - bestiary 6.pdf",
}


def run(pdf_dir: Path, out: Path) -> dict:
    creatures: dict[str, dict] = {}
    report = []
    for slug_name, filename in BOOKS.items():
        book_file = ROOT / "reference" / "books" / f"{slug_name}.json"
        pdf = pdf_dir / filename
        if not book_file.exists() or not pdf.exists():
            report.append((slug_name, 0, 0, "missing"))
            continue

        book = json.loads(book_file.read_text(encoding="utf-8"))
        anchors = book.get("creatures") or []
        reader = PdfReader(str(pdf))
        title = book.get("title", slug_name)

        got = 0
        for a in anchors:
            page = a.get("page")
            if not isinstance(page, int):
                continue
            # A stat block can run onto the next page, so both are read and joined.
            text = ref.clean(ref.page_text(reader, page, min(page + 1,
                                                             len(reader.pages) - 1)))
            parsed = parse_block(text, a["name"], str(a.get("cr", "")))
            if parsed is None:
                continue
            parsed["source"] = title
            parsed["notes"] = f"CR {parsed['cr']} {parsed['creature_type']}".strip()
            # First book wins: Bestiary 1 is the canonical printing of anything reprinted.
            creatures.setdefault(parsed["id"], parsed)
            got += 1
        report.append((slug_name, len(anchors), got, ""))

    payload = {
        "source": "Bestiary PDFs, via the reference index's creature anchors",
        "note": ("Parsed from the printed stat blocks. A page whose block could not be "
                 "read is skipped and counted rather than filled in — a creature with an "
                 "invented AC is one the engine rolls against wrongly forever."),
        "creatures": sorted(creatures.values(), key=lambda c: c["name"].lower()),
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=1, ensure_ascii=False), encoding="utf-8")
    return {"payload": payload, "report": report}


if __name__ == "__main__":
    result = run(Path(sys.argv[1]), Path(sys.argv[2]))
    cs = result["payload"]["creatures"]
    print(f"{'book':14} {'anchors':>8} {'parsed':>8}")
    for name, anchors, got, note in result["report"]:
        print(f"{name:14} {anchors:8} {got:8}  {note}")
    print()
    print(f"unique creatures  {len(cs)}")
    print(f"with environment  {sum(1 for c in cs if c['environment'])}")
    print(f"with abilities    {sum(1 for c in cs if len(c['abilities']) >= 5)}")
    print(f"with a melee atk  {sum(1 for c in cs if c['flat_attack'] is not None)}")
    print(f"with DR           {sum(1 for c in cs if c['reductions'])}")
    print()
    for probe in ("ogre", "skeleton", "dire-wolf", "goblin", "young-red-dragon", "troll"):
        hit = next((c for c in cs if c["id"] == probe), None)
        print(f"  {probe:18}", f"CR {hit['cr']}, {hit['hp']} hp, AC {hit['flat_ac']}, "
                               f"env {hit['environment'][:34]!r}" if hit else "not found")
