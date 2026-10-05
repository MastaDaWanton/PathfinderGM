"""Measure whether the page shows the player's declared deeds: the reader against the
cue-word check it replaces, on the hand-labelled deeds of tests/deeds/gold.py.

    python tools/deed_bench.py --model igorls/gemma-4-12B-it-heretic-GGUF:latest
    python tools/deed_bench.py --regex-only
    python tools/deed_bench.py --model ... --extra scratch/owner_gold.json --runs 2

The positive class is a deed NOT shown — the alarm. Precision is how many alarms were
right, recall how many unshown deeds were caught, and the false-alarm rate is on the deeds
the page did show (each one costs a sentence the beat did not need).

Two regex rows, because the shipped check had two parts: `shows_deed` (cue words) judged
only what `owed_deeds` owed, and `owed_deeds` owed no speech ("ask", "tell", "say", a
quotation) and no `other` on a still turn. The act of a gold deed is not labelled, so the
shipped scope is approximated here from the span's first word (`_old_owed`); the cue-word
row without the scope judges every deed.

`--extra` adds rows from a JSON file — the owner's labelled beats, which are never
committed: [{"id", "player", "text", "deeds": [[span, true|false|null], ...]}].
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from gm import deed_reader, narration  # noqa: E402
from tests.deeds import gold as G  # noqa: E402

# The acts `owed_deeds` owed (DECLARED_DEEDS) by the verbs that open their spans here;
# anything else on these still turns was speech or `other`, which it did not owe.
_PHYSICAL = ("pick", "tip", "take", "pocket", "hand", "give", "set", "drop", "wave",
             "stand", "pull", "kiss", "buy", "offer", "count", "smile")


def _old_owed(span: str) -> bool:
    s = span.strip().lower()
    if s.startswith(('"', "'")) or narration._SPEECH_VERB.search(s):
        return False
    return s.split()[0] in _PHYSICAL if s.split() else False


def rows(extra: str | None) -> list[dict]:
    out = []
    for source, deeds in G.GOLD:
        player, text = G.load(source, ROOT)
        out.append({"id": source, "player": player, "text": text, "deeds": deeds})
    if extra:
        for r in json.loads(Path(extra).read_text(encoding="utf-8")):
            out.append({**r, "deeds": [tuple(d) for d in r["deeds"]]})
    return out


def score(pairs: list[tuple[bool, bool]]) -> dict:
    """pairs of (labelled unshown, alarmed)."""
    tp = sum(1 for u, a in pairs if u and a)
    fp = sum(1 for u, a in pairs if not u and a)
    fn = sum(1 for u, a in pairs if u and not a)
    shown = sum(1 for u, _ in pairs if not u)
    return {"P": round(tp / (tp + fp), 3) if tp + fp else None,
            "R": round(tp / (tp + fn), 3) if tp + fn else None,
            "false alarms": f"{fp}/{shown}", "tp": tp, "fp": fp, "fn": fn}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="igorls/gemma-4-12B-it-heretic-GGUF:latest")
    ap.add_argument("--host", default="http://localhost:11434")
    ap.add_argument("--runs", type=int, default=1)
    ap.add_argument("--extra")
    ap.add_argument("--regex-only", action="store_true")
    ap.add_argument("--show", action="store_true", help="print every miss")
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")

    data = rows(args.extra)
    labelled = [(r, s, lab) for r in data for s, lab in r["deeds"] if lab is not None]
    n_u = sum(1 for *_x, lab in labelled if lab is False)
    print(f"{len(data)} beats, {len(labelled)} labelled deeds: {n_u} not shown, "
          f"{len(labelled) - n_u} shown")

    cue = [(lab is False, not narration.shows_deed(
        r["text"], {"cues": narration.deed_cues({"span": s})})) for r, s, lab in labelled]
    old = [(u, a and _old_owed(s)) for (u, a), (_r, s, _l) in zip(cue, labelled)]
    print("cue words, every deed       ", score(cue))
    print("cue words, shipped scope    ", score(old))
    if args.regex_only:
        return 0

    for run in range(args.runs):
        pairs, secs, errors, unsure = [], [], 0, 0
        for r in data:
            spans = [s for s, _lab in r["deeds"]]
            got = deed_reader.read(r["text"], spans, r["player"], model=args.model,
                                   host=args.host)
            secs.append(got.seconds)
            if got.error:
                errors += 1
            verdicts = {v.span: v for v in got.verdicts}
            for s, lab in r["deeds"]:
                v = verdicts.get(" ".join(s.split()))
                if v is not None and v.verdict == deed_reader.UNSURE:
                    unsure += 1
                if lab is None:
                    continue
                alarmed = bool(v and v.missing)
                pairs.append((lab is False, alarmed))
                if args.show and alarmed != (lab is False):
                    print(f"  MISS {r['id']}: {s!r} labelled "
                          f"{'U' if lab is False else 'S'}, read "
                          f"{v.verdict if v else 'nothing'} {v.sentence[:80] if v else ''!r}"
                          f"{(' (' + v.why + ')') if v and v.why else ''}")
        print(f"reader run {run + 1}            ", score(pairs),
              f"median {statistics.median(secs):.2f}s max {max(secs):.2f}s, "
              f"{errors} errors, {unsure} unsure")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
