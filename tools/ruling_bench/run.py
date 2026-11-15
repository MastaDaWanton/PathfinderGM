"""Run one judge arm over the frozen ruling set and record every ruling.

    python -m tools.ruling_bench.run --model <ollama model> --arm checklist|direct|onecall|spec
        [--prec] [--split set1|set2|rulings|all] [--runs 1] [--temperature 0]
        [--tag v1] [--out ruling-bench-out/r3]

Reads tools/ruling_bench/ruling-set.json (build_set.py). One JSONL row per (line, run):
the ruling, the model's own seconds, the WALL seconds (Ollama is shared with other lanes,
so wall time includes queueing behind them), and the model's raw answers. Resumable: rows
already written are skipped. Temperature 0 by default so a rerun reproduces the arm.

--prec shows the GM's rulings on the most similar lines from OTHER scenes (closed.py):
set1 lines draw from set1's other scenes (leave-one-scene-out), set2 and the derived lines
draw from set1 alone, so the held-out split never sees itself.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

SET = Path(__file__).resolve().parent / "ruling-set.json"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--arm", required=True, choices=["checklist", "direct", "onecall", "spec"])
    ap.add_argument("--prec", action="store_true")
    ap.add_argument("--per-verdict", type=int, default=2)
    ap.add_argument("--split", default="set1")
    ap.add_argument("--runs", type=int, default=1)
    ap.add_argument("--temperature", type=float, default=0.0)
    ap.add_argument("--qv", default="v1", help="the checklist's question version (closed.py)")
    ap.add_argument("--tag", default="")
    ap.add_argument("--out", default="ruling-bench-out/r3")
    a = ap.parse_args(argv)

    from gm import client
    from . import closed, judge, specialists

    data = json.loads(SET.read_text(encoding="utf-8"))
    scenes = data["scenes"]
    lines = [l for l in data["lines"] if a.split in ("all", l["split"])]
    set1 = [l for l in data["lines"] if l["split"] == "set1"]
    prec = closed.Precedents(set1) if a.prec else None

    arm = "-".join(x for x in (a.model.replace("/", "_").replace(":", "_"), a.arm,
                               "prec" if a.prec else "", f"t{a.temperature}", a.split,
                               a.tag) if x)
    out_dir = Path(a.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"{arm}.jsonl"
    done = set()
    if out.exists():
        for row in out.read_text(encoding="utf-8").splitlines():
            r = json.loads(row)
            done.add((r["id"], r["run"]))
    total, n = len(lines) * a.runs, len(done)
    with out.open("a", encoding="utf-8") as f:
        for run in range(a.runs):
            for l in lines:
                if (l["id"], run) in done:
                    continue
                scene = scenes[l["scene"]]
                pc_text = data["pcs"][scene["pc"]]
                block = ""
                if prec:
                    # set1 lines exclude their own scene; other splits already sit outside set1
                    near = prec.nearest(l["text"], l["scene"], a.per_verdict)
                    block = closed.precedent_block(near, scenes)
                t0 = time.monotonic()
                try:
                    if a.arm in ("checklist", "direct"):
                        got, secs, raw = closed.rule(client.chat, a.model, scene, pc_text,
                                                     l["text"], a.arm, block, a.temperature,
                                                     version=a.qv)
                    elif a.arm == "spec":
                        got, secs, raw = specialists.rule(client.chat, a.model, scene, pc_text,
                                                          l["text"], scene["fight"],
                                                          temperature=a.temperature)
                    else:
                        got, secs, raw = judge.rule(client.chat, a.model, scene, pc_text,
                                                    l["text"], scene["fight"],
                                                    temperature=a.temperature, split=True,
                                                    target_repair=True)
                    err = ""
                except Exception as exc:  # noqa: BLE001 — a bench records, never stops
                    got, secs, raw, err = {}, 0.0, "", f"{type(exc).__name__}: {exc}"
                wall = time.monotonic() - t0
                f.write(json.dumps({"id": l["id"], "run": run, "model": a.model, "arm": a.arm,
                                    "prec": a.prec, "temperature": a.temperature,
                                    "tag": a.tag, "qv": a.qv, "ruling": got, "seconds": round(secs, 2),
                                    "wall": round(wall, 2), "raw": raw, "error": err},
                                   ensure_ascii=False) + "\n")
                f.flush()
                n += 1
                print(f"{n}/{total} {l['id']} {got.get('verdict', '?')} "
                      f"{got.get('refuse') or ''} {wall:.1f}s {err}", flush=True)
    print(f"DONE {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
