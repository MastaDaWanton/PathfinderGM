"""Lift the four Blood Bending paths out of the author's own document.

Run once, against `Blood Bending.docx`. The class file carried the four path *names*
and a note explaining that the abilities behind them were not written down anywhere the
engine could read — which was true of the repository and false of the author's desk.

The shape the document uses is the one the class table already refers to: abilities are
tiered by **Control Blood level**, one to five, not by character level. That is what
`control blood 1a` through `5b` on the progression means — reaching it raises the tier
in the path you follow. So the import keys them that way rather than flattening them
onto levels, because flattening would lose the whole reason the table has two tracks.

Nothing is paraphrased. Every description is the document's own sentence, so the class
in the app says what the class in the document says.

    python tools/import_blood_paths.py "C:/Users/natha/Downloads/Blood Bending.docx"
"""
from __future__ import annotations

import json
import re
import sys
import zipfile
from pathlib import Path

TARGET = Path(__file__).resolve().parents[1] / "content" / "classes" / "blood-bending.json"


def read_docx(path: str) -> list[str]:
    xml = zipfile.ZipFile(path).read("word/document.xml").decode("utf-8", "ignore")
    xml = re.sub(r"</w:p>", "\n", xml)
    xml = re.sub(r"<w:tab[^>]*/>", "\t", xml)
    text = re.sub(r"<[^>]+>", "", xml)
    for a, b in (("&amp;", "&"), ("&lt;", "<"), ("&gt;", ">"), ("&#8217;", "'"),
                 ("&quot;", '"'), ("&#8211;", "-"), ("&#8212;", "—")):
        text = text.replace(a, b)
    return [l.strip() for l in text.split("\n")]


def parse_paths(lines: list[str]) -> dict:
    start = next(i for i, l in enumerate(lines) if l == "Blood Bending Paths")
    heads = [(i, l) for i, l in enumerate(lines[start:], start)
             if re.match(r"^\d+\.\s+.+\(", l)]

    out: dict[str, dict] = {}
    for n, (at, title) in enumerate(heads):
        end = heads[n + 1][0] if n + 1 < len(heads) else len(lines)
        seg = [l for l in lines[at:end] if l]
        m = re.match(r"^\d+\.\s+(.+?)\s*\((.+)\)\s*$", title)
        name, role = m.group(1).strip(), m.group(2).strip()

        # The blurb is whatever sits between the heading and the first structural line.
        blurb, rule = "", ""
        for l in seg[1:]:
            if l.startswith("Global Rule:"):
                rule = l.split(":", 1)[1].strip()
            elif l == "Control Blood Lvl":
                break
            elif not blurb:
                blurb = l

        # Tier rows: a bare 1-5 followed by a comma-separated list of ability names.
        tiers: dict[str, list[str]] = {}
        for i, l in enumerate(seg):
            if re.fullmatch(r"[1-5]", l) and i + 1 < len(seg):
                nxt = seg[i + 1]
                if not re.fullmatch(r"[1-5]", nxt) and ":" not in nxt[:40]:
                    tiers[l] = [x.strip() for x in nxt.split(",") if x.strip()]

        # Definitions: "Name: the author's own sentence."
        abilities: dict[str, str] = {}
        for l in seg:
            m2 = re.match(r"^([A-Z0-9][^:]{2,60}):\s+(.+)$", l)
            if m2 and not l.startswith("Global Rule"):
                abilities[m2.group(1).strip()] = m2.group(2).strip()

        # A tier row names the scaled form — "Blood Burst 40ft", "Extracorporeal Blood
        # Manipulation 3" — and the description is written once under the bare name.
        # Resolving them here means the sheet can show the text beside every rank
        # instead of blanking four rows in five.
        resolved, upgrades, core, undescribed = {}, {}, [], []
        for listed in {a for row in tiers.values() for a in row}:
            key = _match(listed, abilities)
            if key:
                resolved[listed] = key
                continue
            parent, detail = _upgrade_of(listed, abilities)
            if parent:
                resolved[listed] = parent
                upgrades[listed] = detail
            elif _strip(listed) in CORE_ABILITIES:
                core.append(listed)
            else:
                undescribed.append(listed)

        out[name.lower()] = {
            "name": name, "role": role, "summary": blurb,
            "global_rule": rule,
            "tiers": {k: tiers[k] for k in sorted(tiers)},
            "abilities": abilities,
            "resolves": resolved,
            # A rank whose text lives inside its parent's sentence, and the parenthetical
            # that distinguishes it: "Mighty Blood Rage" -> "+4 attack/damage, +4 Temp HP/HD".
            "upgrades": upgrades,
            # Named here, defined by the Core Rulebook. A reference, not an omission.
            "core": sorted(core),
            # Named on the table and never written up. Recorded rather than dropped:
            # the page can say "the source names this and does not describe it", which
            # is the truth, where a silent blank would read as a bug in the app.
            "undescribed": sorted(undescribed),
        }
    return out


def _strip(name: str) -> str:
    """A listed name reduced to the heading its description is written under."""
    n = re.sub(r"\s*\(.*?\)\s*$", "", str(name)).strip()
    # Trailing rank or measurement: "3", "40ft", "2NLDR", "DR 5/-".
    n = re.sub(r"\s+(?:\d+\s*(?:ft|NLDR)?|DR\s*\d+/.*)$", "", n, flags=re.I)
    return n.strip().lower()


def _match(listed: str, abilities: dict) -> str:
    want = _strip(listed)
    for key in abilities:
        if _strip(key) == want:
            return key
    return ""


# Abilities the Core Rulebook already defines. Naming one on a homebrew table is a
# reference, not an omission, and reporting it as undescribed says the document is
# missing something it had no reason to write.
CORE_ABILITIES = {"uncanny dodge", "improved uncanny dodge", "evasion",
                  "improved evasion", "combat expertise", "combat reflexes"}


def _upgrade_of(listed: str, abilities: dict) -> tuple[str, str]:
    """A rank described inside another ability's sentence, as parent and detail.

    "Upgrades to Greater Blood Rage (+3 attack/damage, +3 Temp HP/HD) and Mighty Blood
    Rage (+4 ...)" defines two abilities without giving either its own heading. Reading
    only headings reported both as undescribed, which is what the author corrected.
    """
    for key, text in abilities.items():
        m = re.search(rf"{re.escape(listed)}\s*\(([^)]+)\)", text, re.I)
        if m:
            return key, m.group(1).strip()
    return "", ""


def main() -> int:
    src = sys.argv[1] if len(sys.argv) > 1 else r"C:\Users\natha\Downloads\Blood Bending.docx"
    paths = parse_paths(read_docx(src))

    data = json.loads(TARGET.read_text(encoding="utf-8"))
    data["paths"] = paths
    data["_paths_note"] = (
        "Imported from the author's own document by tools/import_blood_paths.py. "
        "Abilities are tiered by Control Blood level (1-5), which is what "
        "'control blood 1a' through '5b' on the progression table refers to — not by "
        "character level. Descriptions are the document's own sentences, unedited: the "
        "engine executes none of them yet, so what the app shows is what the author "
        "wrote rather than a paraphrase of it."
    )
    TARGET.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n",
                      encoding="utf-8")

    for key, p in paths.items():
        named = sum(len(v) for v in p["tiers"].values())
        print(f"{p['name']:16} ({p['role']:20}) {len(p['tiers'])} tiers, "
              f"{named:2} listed, {len(p['abilities']):2} described")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
