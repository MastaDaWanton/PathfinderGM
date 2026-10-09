"""The beat read back and compared: what the page says happened, against what the engine did.

Lane V of the structured turn (docs/structured-turn.md, Backward §4; docs/beat-verify.md).
The owner, 2026-10-03: *"could we have the interpretor/one of these smaller models read the
final text convert it back to json and make sure that it matches the expected actions?"*

Every other member of this package reads the page's English with its own patterns. This
one does not read English at all: `gm.beat_verify` has a model state the beat's claims in
the engine's own closed vocabularies — the place the party ends at, what changed hands,
what was sold, who was hurt, who came or went, what hour it is — each with the page's own
words as a quote, which code checks is really the narration. Then code compares those
claims with `ctx.outcomes` and the scene, and every contradiction is asked once more as a
closed question about its one sentence (`beat_verify.confirm`) before it costs a word.

Measured on tests/beat_verify/gold.py (docs/beat-verify.md has the table), 50 beats,
gemma-4-12B twice, every alarm at precision 1.00 and no clean beat alarmed (0 of 72):

  * `thing_kept` RETIRED  — things changing hands, recall 0.40 -> 0.80;
  * `trade_claimed` RETIRED — a sale settled the engine did not make, 0.50 -> 1.00;
  * `time_of_day` RETIRED — the hour against the clock, 1.00 -> 1.00, no false alarm;
  * `refused_move` STAYS — 1.00 against this member's 0.67 ("You are standing where the
    paths diverge" read as staying put); both run, and on one sentence the heavier wins;
  * `empty_roll` STAYS — equal on harm (1/3 and 2/6), and the only reader of a victim
    who is not on the actor list at all, which this member never judges.

The rest of the package still runs beside it.

Repair is the house shape, through `GMAgent._repair_sentences`: one targeted rewrite of
the sentence with the engine's fact named (the finding's `fix_hint`), checked by reading
the rewritten sentence back; then the backstop below — the sentence cut, and for a move or
a sale the engine's own sentence put on the page. An omission (a refused sale the page
never mentions) names no sentence and goes straight to its backstop: the engine's refusal,
put before the hand-back.

When the read fails — Ollama down, a reply that will not parse — `find` raises, the
registry logs a `check-error` row for this member and the turn goes on; the categories
whose regex checks were retired go unchecked for that beat. The failure rate is measured
in the doc.
"""
from __future__ import annotations

from gm.narration import Finding

from ._page import cut, cut_from

ORDER = 9
KINDS = frozenset({"beat-moves-player", "beat-hands-over", "beat-settles-trade",
                   "beat-harms", "beat-absent", "beat-presence", "beat-hour",
                   "beat-omits-outcome"})
DOORS = frozenset({"plan", "turn", "npc", "outcome"})

# Which finding kind each discrepancy category raises, and how heavy it is: a move the
# engine never made is wrong for the rest of the session (the weight `refused_move` had),
# a thing or a sale for as long as the pack is read, the hour until the next beat.
_KIND = {"move": ("beat-moves-player", 4), "hands": ("beat-hands-over", 3),
         "trade": ("beat-settles-trade", 3), "harm": ("beat-harms", 3),
         # Somebody acting here whom the engine holds elsewhere: as wrong as a wound the
         # dice never gave (2026-10-09, the raiders narrated lunging an hour after they
         # robbed the player and went; docs/narrator-after-defeat.md).
         "absent": ("beat-absent", 3),
         "presence": ("beat-presence", 2), "hour": ("beat-hour", 2)}

# The confirmations already asked this beat: (facts, sentence, question) -> kept. The repair
# asks `find` again after each rewrite and once more before the backstops; a sentence it
# did not touch must not cost the question twice.
_CONFIRMED: dict[tuple, bool] = {}


def _route(ctx) -> dict:
    return dict(getattr(ctx, "reader", None) or {})


def discrepancies(ctx) -> list:
    """The beat's confirmed contradictions and its omissions, read through the caches."""
    from gm import beat_verify as bv

    if not bv.ENABLED:
        return []
    route = _route(ctx)
    if not route.get("model"):
        return []
    facts = bv.facts_from(ctx)
    reading = bv.read_beat(ctx.text, facts, **route)
    if reading.error:
        raise RuntimeError(f"the beat could not be read back: {reading.error}")
    found = bv.diff(reading.claims, facts, ctx.text)
    asked, kept = [], []
    for d in found:
        key = (facts.key(), d.sentence, bv.question(d, facts))
        if d.kind != "contradiction" or not key[2]:
            kept.append(d)
        elif key in _CONFIRMED:
            if _CONFIRMED[key]:
                kept.append(d)
        else:
            asked.append((key, d))
    if asked:
        held, _refuted, _s = bv.confirm([d for _k, d in asked], ctx.text, facts, **route)
        for key, d in asked:
            _CONFIRMED[key] = d in held
            if d in held:
                kept.append(d)
    while len(_CONFIRMED) > 256:
        _CONFIRMED.pop(next(iter(_CONFIRMED)))
    return kept


def find(ctx) -> list:
    out = []
    for d in discrepancies(ctx):
        if d.kind == "omission":
            out.append(Finding(
                "beat-omits-outcome",
                f"the engine's answer is not on the page: {d.fact[:120]}",
                f"The page must say: {d.fact}", weight=1))
            continue
        kind, weight = _KIND[d.category]
        quote = d.claim.quote if d.claim is not None else ""
        out.append(Finding(
            kind, f"the page says {quote[:90]!r}; the engine: {d.fact}",
            f"{d.fact} Rewrite the sentence so it agrees — keep everything else it says.",
            weight=weight, sentences=(d.sentence,) if d.sentence else ()))
    return out


def backstop(ctx, text: str, findings) -> tuple[str, list[str]]:
    """What still disagrees after the rewrite: the sentence goes, and where the engine has
    a sentence of its own for the fact — the refusal, where the party still is — it stands
    in its place. A move is cut from its first claim on, as `hold_the_door` cuts: every
    sentence after a walk the engine never made is set somewhere the party is not."""
    from dataclasses import replace

    from gm import narration as narration_mod

    notes: list[str] = []
    found = discrepancies(replace(ctx, text=text))
    moves = [d for d in found if d.kind == "contradiction" and d.category == "move"
             and d.sentence in text]
    if moves:
        first = min(moves, key=lambda d: text.find(d.sentence))
        text = cut_from(text, first.sentence)
        if first.line and first.line not in text:
            text = f"{text} {first.line}".strip()
        notes.append(f"beat read back: a move the engine did not make, cut from "
                     f"{first.sentence[:60]!r}")
    for d in found:
        if d.kind == "omission":
            if d.line and d.line not in text:
                text = narration_mod.put_before_the_hand_back(text, d.line)
                notes.append(f"beat read back: the engine's answer was missing: {d.line[:60]!r}")
            continue
        if d.category == "move" or d.sentence not in text:
            continue
        text = cut(text, [d.sentence])
        if d.category == "trade" and d.line and d.line not in text:
            text = f"{d.line} {text}".strip()
        notes.append(f"beat read back: {d.category}: cut {d.sentence[:60]!r}")
    return text, notes
