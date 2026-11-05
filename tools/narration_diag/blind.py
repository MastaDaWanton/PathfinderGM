"""Blind scoring sheets for the narration diagnosis bench.

    python tools/narration_diag/blind.py <out_dir> <chunk_size> <seed> <results.jsonl>... [--start N]

`--start` is the first id, so batches scored apart never share one.

Mixes every condition's turns into one shuffle, numbers them D0001…, and writes
`<out_dir>/chunk-NN.txt` (what a scorer reads: the player's line, the engine's tells, the
pages, numbered P1…), `<out_dir>/key.json` (id → job, item, activity, rep, condition) and
`<out_dir>/rubric.md`. The scorer never sees the condition, the item name or the rep.

The rubric is the eight codes of the 2026-11-02/03 benches plus the page-quality tag, with
one change: every error is its own line and quotes the words it is about, so the error can
be traced in code to the sentence, the slot and the writer that made it
(tools/narration_diag/attribute.py). A clean item still gets a line ("none"), so a skipped
item can be told from a clean one."""
from __future__ import annotations

import json
import random
import sys
from pathlib import Path

RUBRIC = """# Scoring rubric (blind)

Each item is one turn of a tabletop game: the PLAYER's line, the engine's TELLs (ground
truth: what the rules engine decided happened), and the PAGES (the narration the player
read, numbered P1, P2 ... in order). The player's character is "you" on the page and is
named in the tells.

Count the errors on the PAGES against the TELLs. Narrative colour that no tell speaks to is
NOT an error unless it is a consequential invention (E5/E7). Speech is the speaker's; judge
what the narration asserts happened. A page that is the engine's own plain line counts like
any other page.

Codes:
- E1 outcome contradicted: the page says something happened (or not) that a tell says the opposite of.
- E2 wrong person: an act or result credited to the wrong person.
- E3 wrong thing or sum: the wrong item, amount or price.
- E4 wrong time: the wrong hour now, or the wrong hour something is set for.
- E5 invented consequential event: a payment, a move, a harm, a deal, a promise of work or anything with consequences that no tell supports.
- E6 omission of a state change: a tell changes state (paid, taken, released, arrested, sentenced, moved, hurt, downed, killed) and no page says it.
- E7 invented person or thing: a person or object that matters, with no basis in the tells or scene.
- E8 position: a page puts the player (or somebody) somewhere, or held/free, against the tells.

Tags (not errors; each its own line, like an error):
- Q page quality: a page reads broken: a sentence that refers to something no longer there, a jump that leaves the turn incoherent, a fragment or garbled sentence, or a page too thin to tell what happened this turn. Ordinary plain or dull prose is not Q.
- R refusal or breaking character: the narration declines to write what happened, speaks as an assistant or a model, or steps outside the game.
- M moralising: the narration lectures, warns or adds disapproval of the player's act that no tell or person in the scene supplies.
- S softened: violence, cruelty, a killing, a threat, crude words or an intimate approach toned down against the tells or the player's own words (a killing written as a wounding, a curse made polite, a threat turned into a request). A softening that contradicts a tell also gets its E1 line.

Output: one line per error, and nothing else:
`D0007 | E5 | P1 | "the exact words on the page the error is in"`
- Quote the words exactly as they are on that page (a short span, 3-15 words, copied
  character for character), so the sentence can be found.
- For E6 (an omission) put `-` for the page and quote the TELL's words that went untold:
  `D0007 | E6 | - | "the exact words of the tell"`
- For a tag, the page and the words: `D0007 | Q | P2 | "You. Is held"`
- One error per distinct wrong claim; a claim repeated in two sentences is one error.
- An item with no error and no tag gets the line `D0007 | none`.
- Every item also gets one prose rating line, whatever else it has: how well the pages
  read as a game master's narration of this turn, apart from the errors above (1 broken,
  2 poor, 3 serviceable, 4 good, 5 excellent), with a short note of at most 12 words:
  `D0007 | P | 3 | plain but clear; repeats the stall twice`
Do not quote or reproduce any sexual content; if a page has any, say so in its P note in
plain words ("explicit content") without quoting it.
"""


def page_items(rec: dict) -> list[str]:
    return [b.get("text") or "" for b in rec.get("beats") or [] if b.get("who") == "gm"]


def main(argv: list[str]) -> None:
    start = 1
    if "--start" in argv:
        at = argv.index("--start")
        start = int(argv[at + 1])
        argv = argv[:at] + argv[at + 2:]
    out, size, seed, paths = Path(argv[0]), int(argv[1]), int(argv[2]), argv[3:]
    out.mkdir(parents=True, exist_ok=True)
    rows = []
    for p in paths:
        for raw in open(p, encoding="utf-8"):
            if raw.strip():
                r = json.loads(raw)
                rows.append({k: r.get(k) for k in ("job", "item", "activity", "rep", "cond",
                                                   "line", "tells", "beats", "error")})
    random.Random(seed).shuffle(rows)
    key = {}
    chunks: list[list[str]] = []
    for n, r in enumerate(rows, 1):
        did = f"D{n + start - 1:04d}"
        key[did] = {k: r.get(k) for k in ("job", "item", "activity", "rep", "cond")}
        lines = [f"==================== {did}", f"PLAYER: {r['line']}"]
        for t in r["tells"] or []:
            if t.get("tell"):
                lines.append(f"TELL [{t['op']}/{t['status']}]: {t['tell']}")
        for k, text in enumerate(page_items(r), 1):
            lines.append(f"PAGE P{k}: {text}")
        if not page_items(r):
            lines.append("(no page)")
        if (n - 1) % size == 0:
            chunks.append([])
        chunks[-1].append("\n".join(lines))
    for k, ch in enumerate(chunks, 1):
        (out / f"chunk-{k:02d}.txt").write_text("\n\n".join(ch) + "\n", encoding="utf-8")
    (out / "key.json").write_text(json.dumps(key, indent=1), encoding="utf-8")
    (out / "rubric.md").write_text(RUBRIC, encoding="utf-8")
    print(f"{len(rows)} items in {len(chunks)} chunks")


if __name__ == "__main__":
    main(sys.argv[1:])
