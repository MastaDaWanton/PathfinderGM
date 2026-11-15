"""Freeze the ruling bench's answer key into one file in the repo, with its provenance.

    python -m tools.ruling_bench.build_set --set1 <answer-key-set1-v2.json>
        --set2 <answer-key-set2.json> [--out tools/ruling_bench/ruling-set.json]

The keys were labelled outside the repo (C:\\Users\\natha\\pgm-work\\ruling-set, 2026-11-05/06:
the owner's labelling pages, 38 rulings written by the owner, 156 Claude drafts the owner
saved). The bench used to read them from there, so a score could not be reproduced from
the branch alone. This writes the compact key (no prose, only what is scored, plus the
bracketed table note the ruling's own words carry, which the precedent judge shows as
the reason) and records each source's sha256, so a changed source is visible.

Splits:
* set1 — 152 lines, 11 scenes (2 flagged unclear by the owner are left out). Every prompt
  before 2026-11-14 was tuned on it: it is the DEV split.
* set2 — 40 lines, 4 scenes, written after the tuning; the HELD-OUT split. Precedents for
  it come from set1 only.
* rulings — a handful of lines derived by Claude from the owner's recorded rulings in
  memory (named per line). Not owner-labelled; reported apart, never in the gate.

The correction log (training/corrections.jsonl) holds narration rewrites, not rulings on
claims, so nothing in it could become a line; it is not read, and never edited.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent  # a dev tool, never frozen into the app

# Lines derived from the owner's rulings in memory. Claude's labels, so they are scored
# apart from the owner's key. Each names the ruling it follows.
DERIVED = [
    {"id": "r-01", "scene": "s1", "text": "I draw my longsword and stab the priest.",
     "verdict": "refuse", "refuse": "false_fact",
     "source": "declared-violence-victim-ruling.md (2026-10-10): 'stab the priest' with no "
               "priest present is refused, never turned on a bystander"},
    {"id": "r-02", "scene": "s1",
     "text": "I tell the serving boy I know he's been watering the ale, so he'd better "
             "bring me a free bowl of stew.",
     "verdict": "roll", "roll": {"what": "oracle", "against": "unlikely"},
     "source": "shot-in-the-dark-ruling.md (2026-11-06): an unknown secret used as "
               "leverage is a hidden odds roll, not a refusal"},
    {"id": "r-03", "scene": "s9",
     "text": "While Brenna has her back to me I cast charm person on her, then ask her to "
             "open the glass case.",
     "verdict": "refuse", "refuse": "character",
     "source": "rulings-2026-11-09.md (charm unseen then talk) — but Thessaly has not "
               "prepared charm person, so the sheet refuses it first"},
    {"id": "r-04", "scene": "s1",
     "text": "I nod to Delyth, thank her for her time, and leave the hall.",
     "verdict": "say_yes",
     "source": "conversation-state-ruling.md (2026-09-24, 2026-10-17): leaving a "
               "conversation is a free exit"},
    {"id": "r-05", "scene": "s11",
     "text": "The drunk sailor backs down and buys me a drink to say sorry.",
     "verdict": "refuse", "refuse": "npc_choice",
     "source": "companions-obey-in-character.md / seen-people-are-real.md: another "
               "person's choice is theirs, never the player's to declare"},
    {"id": "r-06", "scene": "s7",
     "text": "I wade back into the stream so the wolves have to come at me through the "
             "water.",
     "verdict": "say_yes",
     "source": "set1 s7 precedent and continue-means-the-scene-moves.md: a plain move "
               "nobody contests needs no roll"},
]


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def note(words: str) -> str:
    """The bracketed table note in a ruling's words: the GM's own reason, out of fiction."""
    return " ".join(m.strip() for m in re.findall(r"\[([^\]]+)\]", words or ""))[:600]


def compact(line: dict, split: str, scenes: dict) -> dict:
    r = line["ruling"]
    roll = {k: v for k, v in (r.get("roll") or {}).items()
            if k in ("what", "against", "defence", "opposed_by", "bonus", "multi")}
    return {"id": line["id"], "split": split, "scene": line["scene"], "kind": line["kind"],
            "text": line["text"], "verdict": r["verdict"],
            "roll": roll if r["verdict"] == "roll" else {},
            "refuse": r.get("refuse") if r["verdict"] == "refuse" else None,
            "author": r.get("author", "?"), "note": note(r.get("words", ""))}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--set1", required=True)
    ap.add_argument("--set2", required=True)
    ap.add_argument("--out", default=str(HERE / "ruling-set.json"))
    a = ap.parse_args(argv)
    out = {"version": 1, "built": "2026-11-14", "sources": {}, "pcs": {}, "scenes": {},
           "lines": [], "left_out": []}
    for split, p in (("set1", Path(a.set1)), ("set2", Path(a.set2))):
        key = json.loads(p.read_text(encoding="utf-8"))
        out["sources"][split] = {"file": p.name, "sha256": sha(p),
                                 "frozen": key.get("frozen"), "version": key.get("version")}
        out["pcs"].update(key["pcs"])
        for s in key["scenes"]:
            # A fight is what the scene says it is; the old bench hard-coded {s4, s7} and so
            # judged set2's fight (t3) as "not a fight".
            out["scenes"][s["id"]] = {**s, "fight": s["facts"][0].startswith("In combat")}
        for l in key["lines"]:
            if l["ruling"].get("flag"):
                out["left_out"].append({"id": l["id"], "why": "flagged unclear by the owner"})
                continue
            out["lines"].append(compact(l, split, out["scenes"]))
    for d in DERIVED:
        out["lines"].append({"id": d["id"], "split": "rulings", "scene": d["scene"],
                             "kind": "derived", "text": d["text"], "verdict": d["verdict"],
                             "roll": d.get("roll", {}), "refuse": d.get("refuse"),
                             "author": "claude-derived", "note": "", "source": d["source"]})
    Path(a.out).write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    n = {}
    for l in out["lines"]:
        n[l["split"]] = n.get(l["split"], 0) + 1
    print(a.out, n, "left out", len(out["left_out"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
