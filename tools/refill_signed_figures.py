"""Refill core.json's signed figures from the Bestiary PDFs, touching nothing else.

The PDF scan (`tools/extract_bestiary_pdfs.py`) read every signed figure — saves,
initiative, CMB, base attack, the first attack bonus — with an ASCII "-" only, and the
books print a minus as an en dash. Measured 2026-10-30 over the 1,417 core blocks: 39 had
no saves at all (each lost all three to one negative save, or to a qualifier between two
saves, or to the kerned "w ill"), 69 no initiative, 48 no CMB, 10 no first attack bonus,
and the horse's read the "+1" of its damage for want of its "–2". Five blocks that print no
Special Attacks line had taken a template's rules prose for one ("Special Attacks: A
lycanthrope retains ..." on the lizardfolk).

The scan is fixed. Re-running it whole would rewrite fields later tools add to the same
file (biomes, climates, tags) and lose them, so this runs the fixed scan into memory and
copies across only these fields, only where the scan reads them differently:

    python tools/refill_signed_figures.py H:/Pathfinder            # write and report
    python tools/refill_signed_figures.py H:/Pathfinder --dry-run  # report only

Then `python tools/compile_bestiary.py` is not needed: none of these fields is a compiled
source line (`compile_block.SOURCE_FIELDS`).
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import extract_bestiary_pdfs as ex  # noqa: E402

CORE = ROOT / "content" / "bestiary" / "core.json"
FIELDS = ("flat_saves", "flat_initiative", "cmb", "base_attack", "flat_attack",
          "special_attacks")


def refill(pdf_dir: Path, dry_run: bool = False) -> dict:
    raw = CORE.read_bytes()
    newline = "\r\n" if b"\r\n" in raw[:4096] else "\n"
    doc = json.loads(raw.decode("utf-8"))
    previous = doc.get("creatures") or []
    with tempfile.TemporaryDirectory() as tmp:
        scan = ex.run_scan(pdf_dir, Path(tmp) / "scan.json",
                           {ex._words_key(c["name"]): c["id"] for c in previous},
                           old=previous)["payload"]["creatures"]
    fresh = {c["id"]: c for c in scan}
    changed: dict[str, list[str]] = {}
    for c in previous:
        n = fresh.get(c["id"])
        if n is None:
            continue
        for f in FIELDS:
            if f in n and n[f] != c.get(f):
                c[f] = n[f]
                changed.setdefault(f, []).append(c["id"])
    if not dry_run and changed:
        text = json.dumps(doc, indent=1, ensure_ascii=False)
        CORE.write_bytes(text.replace("\n", newline).encode("utf-8"))
    return changed


if __name__ == "__main__":
    out = refill(Path(sys.argv[1]), dry_run="--dry-run" in sys.argv)
    for field, ids in out.items():
        print(f"{field:16} {len(ids):4}  {', '.join(ids[:12])}{' ...' if len(ids) > 12 else ''}")
