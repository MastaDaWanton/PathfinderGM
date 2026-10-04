"""Every quoted line of the beat is booked to who said it — as the beat reader read it.

Measured before this, each on the owner's or a playtest's save:

  * Bobby, 2026-09-28, turn 9: "a man in a stained leather jerkin" spoke three lines to the
    player, tagged to `new1`, a ref nobody held — 3 lines, 0 attributed, nobody hailed;
  * the Phase-2 live gate, 2026-09-29: "a man in a stained leather apron" spoke twice with
    no tags at all, and the conversation log stayed empty;
  * the 2026-09-30 playtest (item 1): 6 of 43 real NPC lines missing from the log, the
    page having said who spoke ("'…,' the cage owner says");
  * the owner's save, 2026-10-03 (item 15): six beats of "the man" tagged to the servant
    carrying jugs, and the player's own line ("'…,' you say") booked to the clerk.

Each was answered with a rule over the page — a clause pattern, a carry-on from the line
before, the nearest person described before a pronoun, a gender check — in `_Room`,
`_whose`, `_speaker` and `_from_the_page` here, `doubt_tags` and `hailed_by`'s untagged
half in `gm/judgement.py`. Every one of them was a reading of English in code, and every
new phrasing needed one more (docs/beat-reader.md). They are gone. The reader answers,
for each line, who says it — a ref present, "you", or a newcomer the same reading made —
from a closed list (Michel et al. 2024 measured an LLM given the character list at 89-91%
on PDNC novels; the pipeline tools with candidates restricted, 62%).

This step books what the reader said, through the two changes the "people" stage may make
to `said` (`play.aftermath._said_kept`):

  * a record whose `who` is empty (a tag naming nobody here, or a tag the reader
    contradicted — `beat_reader.reconcile_tags`, run where `doubt_tags` ran) is given the
    reader's speaker, with `"made"`;
  * a line with no record at all gains one, `"from": "page"` (and `"made"` when the speaker
    is a newcomer this beat made a body for: `seen_people`, ORDER 10, ran first).

A line the reader gave to the player's character, or to nobody, books nobody. A newcomer
who spoke but was given no body (in a fight, or over the cap) books nobody either, and the
row says so. No reading books nothing beyond the prose call's own tags.
"""
from __future__ import annotations

STAGE = "people"
ORDER = 20
# The opening too: its lines are read by the reader in `aftermath.after_opening`.
DOORS = frozenset({"turn", "carry_on", "opening"})


def step(ctx) -> list[dict]:
    from gm import beat_reader, speech

    reading = ctx.attribution
    if not isinstance(reading, beat_reader.Reading) or not reading.read:
        if isinstance(reading, beat_reader.Reading) and reading.asked and reading.lines:
            return [reading.unread_row("speaker_real")]
        return []
    said = ctx.said if isinstance(ctx.said, list) else []
    actors = getattr(ctx.scene, "actors", {}) or {}
    booked: dict[str, int] = {}
    filled: dict[str, int] = {}
    misses: dict[str, int] = {}
    for ln in reading.lines:
        who = _person(reading, ln.speaker(reading))
        if not who or who == beat_reader.YOU or who not in actors \
                or getattr(actors[who], "is_pc", False):
            if ln.by and ln.by not in (beat_reader.YOU, beat_reader.NOBODY) and not who:
                misses["a newcomer with no body"] = misses.get("a newcomer with no body", 0) + 1
            continue
        to = _person(reading, str(ln.to or ""))
        to = "you" if to in (beat_reader.YOU, "pc") else (to if to in actors else "")
        rec = speech.speaker(said, ln.words)
        if rec is not None:
            if not rec.get("who"):
                rec["who"] = who
                rec["made"] = who
                filled[who] = filled.get(who, 0) + 1
            continue
        new = {"who": who, "to": to, "line": ln.words, "from": "page"}
        if any(n.ref == who for n in reading.newcomers):
            new["made"] = who
        said.append(new)
        booked[who] = booked.get(who, 0) + 1
    rows = [{"kind": "speaker-read", "booked": ref, "lines": n} for ref, n in booked.items()]
    rows += [{"kind": "speaker-read", "filled": ref, "lines": n} for ref, n in filled.items()]
    rows += [{"kind": "speaker-read", "booked": "", "lines": n, "why": why}
             for why, n in misses.items()]
    return rows


def _person(reading, who: str) -> str:
    """A ref, "you", or "" — a newcomer's root mention id is their body's ref, if made."""
    if not who:
        return ""
    if who in reading.refs or who == "you" or any(n.ref == who for n in reading.newcomers):
        return who
    n = reading.newcomer(who)
    if n is not None:
        return n.ref
    m = reading.mention(who)
    if m is not None:
        return _person(reading, reading.person_of(m))
    return ""
