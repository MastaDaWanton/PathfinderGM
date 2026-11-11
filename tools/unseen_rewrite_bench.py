"""Should `beat-sees-the-unseen` be rewritten, or only cut? (`beat_verified.CUT_ONLY`)

    python tools/unseen_rewrite_bench.py --tries 3 --record unseen-rewrites.json

`CUT_ONLY` holds the kinds whose one-sentence rewrite cannot be trusted, because the
rewrite is checked by reading the rewritten sentence back ALONE (`beat_verify.read_beat`
reads only sentences the beat did not have). `beat-aimed-wrong` joined it on a measurement
(docs/ally-swings.md: 9 of 15 rewrites wrong, 6 of those 9 passed the alone re-read). This
takes the same measurement for the unseen kind, which never reached the repair before
3aeb7805 declared it.

For each flagged beat of tests/beat_verify/unseen_gold.py, `beat_verified.find` runs on it
exactly as in the game (the read, the second read, the finding's fix hint). Each finding's
sentence is then rewritten `--tries` times through `_truth_repair_messages` with the
repair call's own settings, and `find` runs again on the beat with the rewrite in place —
the real cached re-read — giving `_repair_sentences`' verdict: "still did it" (rejected)
or kept. Whether a KEPT rewrite is really right is labelled by hand from the record.

Not reproduced: `GMAgent._lift` (speaker tags; the gold beats have none) and the tells
gate (the gold beats have no tells).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="igorls/gemma-4-12B-it-heretic-GGUF:latest")
    ap.add_argument("--host", default="http://localhost:11434")
    ap.add_argument("--tries", type=int, default=3)
    ap.add_argument("--record", default="")
    args = ap.parse_args()
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "pathfindergm.settings")
    import django

    django.setup()
    from gm import beat_verify as bv
    from gm import client
    from gm import narration
    from gm.agent import _truth_repair_messages
    from gm.checks import beat_verified
    from gm.checks._page import page_sentences
    from tests.beat_verify import unseen_gold as G

    bv.ENABLED = True
    route = {"model": args.model, "host": args.host, "provider": "ollama", "api_key": ""}
    schema = {"type": "object", "properties": {"sentence": {"type": "string",
                                                            "maxLength": 500}},
              "required": ["sentence"]}
    record, kept_n, rejected_n, unflagged = [], 0, 0, []
    for beat in G.BEATS:
        if not beat["flag"]:
            continue
        facts = G.facts(beat)
        bv.facts_from = lambda ctx, facts=facts: facts      # the gold beat's engine side
        bv.clear_cache()
        beat_verified._CONFIRMED.clear()
        ctx = SimpleNamespace(text=beat["text"], reader=route)
        found = [f for f in beat_verified.find(ctx) if f.kind == "beat-sees-the-unseen"]
        if not found:
            unflagged.append(beat["id"])
            print(f"{beat['id']}: not flagged by the first read; nothing to repair")
            continue
        for f in found:
            sentence = f.sentences[0]
            for n in range(args.tries):
                reply = client.chat(_truth_repair_messages(sentence, f.fix_hint),
                                    args.model, args.host, as_json=True, think=False,
                                    temperature=0.3, num_predict=240, provider="ollama",
                                    api_key="", schema=schema)
                fixed = str(reply.json().get("sentence", "")).strip()
                fixed, _ = narration.pc_to_second_person(fixed, "Kesst Vayr")
                candidate = beat["text"].replace(sentence, fixed, 1)
                new = {w for w, _ in page_sentences(fixed)} | {fixed}
                still = [g for g in beat_verified.find(SimpleNamespace(text=candidate,
                                                                       reader=route))
                         if g.kind == f.kind]
                rejected = any(set(g.sentences) & new or not g.sentences for g in still)
                rejected_n += rejected
                kept_n += not rejected
                verdict = "REJECTED (still did it)" if rejected else "kept"
                print(f"{beat['id']} try {n + 1} {verdict}\n   was: {sentence}\n   now: {fixed}")
                record.append({"id": beat["id"], "try": n + 1, "sentence": sentence,
                               "rewrite": fixed, "rejected": rejected})
    print(f"\n{kept_n} kept, {rejected_n} rejected; not flagged first: {unflagged or 'none'}")
    if args.record:
        Path(args.record).write_text(json.dumps(record, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
