"""Measure who-the-prose-means over the replay corpus (docs/who-the-prose-means.md).

Every recorded prose beat (tests/replay/*.jsonl.gz), against the scene from before its
turn: the mentions code found, the ones code settled by name, what the labeller said,
and the disagreements. Writes one JSON line per mention so a person can grade them.

Not a pytest: the label call needs a live Ollama. With --code-only it needs none.

    python tools/mention_bench.py --out mentions.jsonl
    python tools/mention_bench.py --code-only
"""
from __future__ import annotations

import argparse
import gzip
import json
import os
import statistics
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "pathfindergm.settings")

import django  # noqa: E402

django.setup()

from django.test import override_settings  # noqa: E402

REPLAY = Path(__file__).resolve().parents[1] / "tests" / "replay"
PROSE_ROLES = ("narrate_turn", "narrate_outcome")


def _prose_of(raw: str) -> str:
    try:
        d = json.loads(raw)
        return str(d.get("narration", "")) if isinstance(d, dict) else str(raw)
    except ValueError:
        return str(raw)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="")
    ap.add_argument("--code-only", action="store_true")
    ap.add_argument("--limit", type=int, default=0, help="stop after this many beats")
    args = ap.parse_args()

    from gm import mentions
    from gm.agent import GMAgent
    from play import campaign as cm
    from play import modelcfg

    mentions.ENABLED = not args.code_only
    cfg = modelcfg.for_role("narrator")
    out = open(args.out, "w", encoding="utf-8") if args.out else None
    beats = found = by_name = labelled = misnamed = failed = 0
    seconds: list[float] = []
    tmp = Path(tempfile.mkdtemp(prefix="mention-bench-"))
    with override_settings(CAMPAIGN_DIR=str(tmp)):
        for f in sorted(REPLAY.glob("*.jsonl.gz")):
            with gzip.open(f, "rt", encoding="utf-8") as fh:
                for n, line in enumerate(fh):
                    rec = json.loads(line)
                    save = rec["save_before"]
                    p = tmp / f"{save['id']}.json"
                    p.write_text(json.dumps(save), encoding="utf-8")
                    c = cm.Campaign.load(p)
                    agent = GMAgent(c.world, c.engine())
                    acting = ""
                    for call in rec["calls"]:
                        if call["role"] == "npc_turn":
                            try:
                                first = (json.loads(call["raw"]).get("intents") or [{}])[0]
                                who = c.scene.actors.get(first.get("actor") or "")
                                acting = who.name if who is not None else ""
                            except (ValueError, AttributeError, IndexError):
                                acting = ""
                            continue
                        if call["role"] in ("plan_turn", "narrate_turn"):
                            acting = "" if call["role"] == "plan_turn" else acting
                        if call["role"] not in PROSE_ROLES:
                            continue
                        text = agent._lift(_prose_of(call["raw"]))
                        if not text.strip():
                            continue
                        beats += 1
                        a = mentions.attribute(
                            text, c.scene, acting=acting if call["role"] == "narrate_outcome" else "",
                            model=cfg["model"], host=cfg["host"],
                            provider=cfg.get("provider", "ollama"),
                            api_key=cfg.get("api_key", ""))
                        found += len(a.mentions)
                        by_name += sum(1 for m in a.mentions if m.code)
                        labelled += sum(1 for m in a.mentions if m.model)
                        misnamed += len(a.misnamed())
                        failed += int(bool(a.error))
                        if a.labelled:
                            seconds.append(a.seconds)
                        if out:
                            cast = {p["ref"]: p["name"] for p in mentions.people(c.scene)}
                            for m in a.mentions:
                                out.write(json.dumps({
                                    "file": f.name, "turn": n, "role": call["role"],
                                    "acting": acting if call["role"] == "narrate_outcome" else "",
                                    "id": m.id, "kind": m.kind, "phrase": m.phrase,
                                    "code": m.code, "model": m.model, "ref": m.ref,
                                    "misnamed": m.misnamed, "sentence": m.sentence,
                                    "cast": cast}, ensure_ascii=False) + "\n")
                        if args.limit and beats >= args.limit:
                            break
            if args.limit and beats >= args.limit:
                break
    if out:
        out.close()
    print(json.dumps({
        "beats": beats, "mentions": found, "settled_by_name": by_name,
        "labelled": labelled, "misnamed": misnamed, "label_calls_failed": failed,
        "seconds_median": round(statistics.median(seconds), 2) if seconds else None,
        "seconds_max": max(seconds) if seconds else None,
    }, indent=1))


if __name__ == "__main__":
    main()
