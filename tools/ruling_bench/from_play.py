"""Candidate ruling-set lines from the owner's engine marks in play.

    python -m tools.ruling_bench.from_play <data>/training/engine-corrections.jsonl
        [--out tools/ruling_bench/play-candidates.jsonl]

A mark of kind needs_roll, should_work or shouldnt (play/engine_corrections.py) is the
owner saying what the ruling on their line should have been: roll, say yes, refuse (a
shouldnt only on a reading line; see `candidates`). Each
becomes one line in the bench's own shape (`build_set.compact`: id, split, scene, kind,
text, verdict, roll, refuse, author, note), with the scene inline because a line from play
has no scene in `ruling-set.json`.

Kept apart on purpose: split "play", author "owner-play", written to its own file and
never into `ruling-set.json`, whose set1/set2 are frozen with their sha256 (build_set.py).
What these are not yet: reviewed. A refusal's reason and a roll's skill are not in the
mark (the owner said only "needed a roll"), so `refuse` and `roll` are left empty for the
review to fill, and a line is a candidate until somebody does.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

VERDICTS = {"needs_roll": "roll", "should_work": "say_yes", "shouldnt": "refuse"}


def _span(rec: dict, mark: dict) -> str:
    """The player's words the mark is about: a reading line's own span, else the line."""
    lid = str(mark.get("line") or "")
    if ".a" in lid:
        try:
            k = int(lid.rsplit(".a", 1)[1])
            span = ((rec.get("reading") or {}).get("actions") or [])[k].get("span")
            if span:
                return str(span)
        except (ValueError, IndexError, AttributeError):
            pass
    return str(rec.get("player_line") or "")


def candidates(records) -> list[dict]:
    out = []
    for rec in records:
        for n, m in enumerate(rec.get("marks") or []):
            verdict = VERDICTS.get(m.get("kind"))
            if not verdict:
                continue
            # "Shouldn't have happened" on an outcome is usually the engine inventing a
            # deed nobody asked for ("Kesst Vayr drinks at the well", live 2026-11-15 on a
            # line that bought a waterskin), not a ruling that the player's words be
            # refused. Only on the reading of the player's own words is it a refusal.
            if verdict == "refuse" and ".a" not in str(m.get("line") or ""):
                continue
            out.append({
                "id": f"p-{rec.get('id')}-{n}", "split": "play",
                "scene": f"play-{rec.get('id')}", "kind": "play",
                "text": _span(rec, m), "verdict": verdict, "roll": {},
                "refuse": None, "author": "owner-play", "provenance": "owner-play",
                "note": str(m.get("note") or ""),
                "engine_line": str(m.get("text") or ""),
                "scene_facts": str(rec.get("scene_brief") or ""),
                "record": rec.get("id"), "app_version": rec.get("app_version"),
                "reviewed": False,
            })
    return out


def _read(path: Path) -> list[dict]:
    latest: dict = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            rec = json.loads(line)
        except ValueError:
            continue
        if isinstance(rec, dict):
            latest[rec.get("id") or id(rec)] = rec
    return list(latest.values())


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("log")
    ap.add_argument("--out", default="")
    a = ap.parse_args(argv)
    lines = candidates(_read(Path(a.log)))
    text = "".join(json.dumps(x, ensure_ascii=False) + "\n" for x in lines)
    if a.out:
        if Path(a.out).name == "ruling-set.json":
            print("refused: the frozen set is build_set.py's alone", file=sys.stderr)
            return 2
        Path(a.out).write_text(text, encoding="utf-8")
        print(a.out, len(lines), "candidate line(s)")
    else:
        sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
