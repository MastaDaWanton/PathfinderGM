"""The labelled deeds the deed reader (gm/deed_reader.py) is measured against.

Built 2026-10-05 for the owner's "narrator does not describe my actions" (docs/
narrator-guards.md, "The deed on the page"). Every passage is prose the narrator really
wrote, and none is copied here: a row names where its passage already lives in the repo —

  * `bv:<id>`   a beat of tests/beat_verify/gold.py (excerpts of the owner's 2026-10-03
                save and the Bobby corpus, cut there for their own labels);
  * `rp:<file>:<turn>`  a recorded turn of tests/replay/<file>-gemma4-12b.jsonl.gz, the
                scripted sessions of 2026-09-25/26, the gm text of the turn whole.

The owner's own saves are never committed; their rows live in a scratch file the bench
takes with `--extra` (the counts of both are in the doc).

Each row: the player's line (from the source) and, for each deed the page owes, the
player's own words for it (as the reader's `span` gives them) and a hand label:

  * S — the page shows the player's character doing it, as it happens, in any words: the
        act, the gesture, the words said or reported ("you ask what work is available",
        "as you mention the girl", "you lean against the counter … let a slow, practiced
        smile play").
  * U — it does not: the beat opens on somebody's answer or reaction ("He does not look up
        as you speak", "the query seems to land with a heavy thud", "The words of your
        challenge hang in the damp air"), shows only a result ("The transaction is
        finalized"), or never comes to it.

A deed labelled `None` is defensible either way ("The heavy crate meets the dirt" for "set
the crate down": the act's result as it happens, with nobody doing it) and is not scored.
"As you speak" with nothing of what was said is U: it names that the player spoke and
shows none of it — the owner's complaint, word for word.
"""
from __future__ import annotations

S, U = True, False

GOLD: list[tuple[str, list[tuple[str, bool | None]]]] = [
    # --- tests/beat_verify/gold.py ----------------------------------------------------
    ("bv:anvil", [("set the crate down on the ground", None)]),
    ("bv:takes-the-crate", [("pick the crate back up", S),
                            ("tip the coins from the pouch into my coin purse", U)]),
    ("bv:settled", [("agree to sell the crate to the smith for whatever it is worth", S)]),
    ("bv:finalized", [("agree to sell the crate to the smith for whatever it is worth", U)]),
    ("bv:first-hint-of-dawn", [("take the pouch", S), ("count the coins", None)]),
    ("bv:eyes-drop", [('lean in and whisper, "I just need it handled quietly."', U)]),
    ("bv:payment-is-yours", [("tell the clerk to give me the money", U)]),
    ("bv:counter-and-go", [("take the crate to the man in the counting house", S)]),
    ("bv:picked-up-unresolved", [("pick the crate back up", S),
                                 ("tip the coins from the pouch into my coin purse", S)]),
    ("bv:stranger-pack", [("take the brunt of the weight", S)]),
    ("bv:into-the-smithy", [("pocket the coins", S)]),
    ("bv:midnight-air", [("ask him who the master of the docks is", U)]),
    ("bv:sold", [('tell the smith, "It\'s a deal. You can have the crate."', U)]),
    ("bv:looking-for-work", [('"Is there anything I can do to earn some coin?"', U)]),
    ("bv:man-on-the-stool", [("What is going on?", U)]),
    ("bv:rapier", [("ask the man in the heavy coat where I could get my rapier "
                    "sharpened", S)]),
    ("bv:broken-tide", [('"Who is he, and where exactly can I find him?"', U)]),
    ("bv:evening-shift", [("ask him about the 'evening shift' he mentioned", U)]),
    ("bv:sell-it-to-me", [("try to sell the crate to Korvu for coin", U)]),
    ("bv:flirt", [("smile", S), ("flirt with the clerk", S),
                  ("offer the crate for coin", S)]),
    ("bv:lid", [("tell the smith I'd like to sell him the crate", U),
                ("agree to whatever it's worth", U)]),
    ("bv:pry-bar", [('"It\'s a deal. You can have the crate."', U)]),
    ("bv:whetstone", [('say to the man "lost implies I had a particular destination in '
                       'mind."', U)]),
    ("bv:morning-mist", [("ask him about the girl in the market", U)]),
    ("bv:ho-satchel", [("take what he was carrying", S)]),
    ("bv:ho-lies-still", [("stand over him", S), ("tell him to stay down", U)]),
    ("bv:ho-life-extinguished", [("find somewhere quiet and sit down", U)]),
    # --- tests/replay ------------------------------------------------------------------
    ("rp:2026-09-25-strangers:0", [("ask them", U)]),
    ("rp:2026-09-25-strangers:1", [("ask what a loaf costs", U)]),
    ("rp:2026-09-25-strangers:2", [("ask around for a healer", U)]),
    ("rp:2026-09-25-strangers:3", [("ask for a room", U)]),
    ("rp:2026-09-25-strangers:4", [("wave down a passing carter", U),
                                   ("ask where he is headed", U)]),
    ("rp:2026-09-25-strangers:6", [("buy them a drink", U)]),
    ("rp:2026-09-25-strangers:7", [("ask around for a guide who knows the grassland", U)]),
    ("rp:2026-09-25-strangers:9", [("ask what this quarter was like once", U)]),
    ("rp:2026-09-25-town:1", [("ask the nearest stallholder what work there is", S)]),
    ("rp:2026-09-25-town:2", [("ask them who runs this quarter", U)]),
    ("rp:2026-09-25-town:4", [("ask the smith about the ore he uses", S)]),
    ("rp:2026-09-25-town:6", [("ask the gate guard what lies north", U)]),
    ("rp:2026-09-25-town:11", [("ask the nearest stallholder what work there is", U)]),
    ("rp:2026-09-25-town:12", [("ask them who runs this quarter", U)]),
    ("rp:2026-09-25-town:14", [("ask the smith about the ore he uses", U)]),
    ("rp:2026-09-25-town:16", [("ask the gate guard what lies north", U)]),
    ("rp:2026-09-25-town:21", [("ask the nearest stallholder what work there is", U)]),
    ("rp:2026-09-25-town:22", [("ask them who runs this quarter", U)]),
    ("rp:2026-09-25-town-tags:1", [("ask the nearest stallholder what work there is", U)]),
    ("rp:2026-09-25-town-tags:2", [("ask them who runs this quarter", U)]),
    ("rp:2026-09-25-town-tags:4", [("ask the smith about the ore he uses", U)]),
    ("rp:2026-09-25-town-tags:6", [("ask the gate guard what lies north", U)]),
    ("rp:2026-09-25-town-tags:11", [("ask the nearest stallholder what work there is", U)]),
    ("rp:2026-09-25-town-tags-retag:1", [("ask the nearest stallholder what work there is",
                                          U)]),
    ("rp:2026-09-25-town-tags-retag:2", [("ask them who runs this quarter", U)]),
    ("rp:2026-09-25-town-tags-retag:4", [("ask the smith about the ore he uses", U)]),
    ("rp:2026-09-25-town-tags-retag:6", [("ask the gate guard what lies north", U)]),
    ("rp:2026-09-25-town-tags-retag:11", [("ask the nearest stallholder what work there "
                                           "is", U)]),
    ("rp:2026-09-26-discover:0", [("ask where the dockhands drink", U)]),
    ("rp:2026-09-26-discover:2", [("sit a while", S)]),
    ("rp:2026-09-25-fight-bodies:7", [("take what he was carrying", S)]),
]


def load(source: str, repo) -> tuple[str, str]:
    """(the player's line, the passage) for a row's source."""
    import gzip
    import json
    from pathlib import Path

    kind, _, rest = source.partition(":")
    if kind == "bv":
        from tests.beat_verify import gold as bv

        beat = bv.by_id(rest)
        return beat["player"], beat["text"]
    if kind == "rp":
        name, _, turn = rest.rpartition(":")
        path = Path(repo) / "tests" / "replay" / f"{name}-gemma4-12b.jsonl.gz"
        with gzip.open(path, "rt", encoding="utf-8") as fh:
            for line in fh:
                row = json.loads(line)
                if str(row.get("turn")) == turn:
                    text = " ".join(e["text"] for e in row.get("added_transcript") or ()
                                    if e.get("who") == "gm")
                    return str(row.get("player") or "").strip(), " ".join(text.split())
        raise KeyError(source)
    raise KeyError(source)
