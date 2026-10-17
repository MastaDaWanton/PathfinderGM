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
                   "beat-omits-outcome", "beat-condition", "beat-attempt", "beat-setting",
                   "beat-struck-with", "beat-swing-early", "beat-foe-struck-with",
                   "beat-struck-at-early"})
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
         "presence": ("beat-presence", 2), "hour": ("beat-hour", 2),
         # A body said to be held, down or blind that the engine holds no such state on:
         # the owner's report of 2026-10-16, a grip on the player's throat across three
         # beats with no grapple ever made. As wrong as a wound the dice never gave.
         "condition": ("beat-condition", 3),
         # A check or a save told the other way round: a failed lift with the cart rising,
         # a refused request with the person agreeing (2026-10-16). Wrong for as long as
         # the page is believed, and the roll was the player's own.
         "attempt": ("beat-attempt", 3),
         # A sentence set in another kind of place: a ship's deck in a market (the
         # report of 2026-10-16). As heavy as `wrong-kind-of-place`, the regex reader of
         # a tavern's furniture it stands beside.
         "setting": ("beat-setting", 3),
         # A blow written with a weapon the engine did not swing: the shard that "bites
         # deep" on an unarmed strike (live, 2026-10-16). As wrong as a wound the dice
         # never gave.
         "weapon": ("beat-struck-with", 3),
         # A blow of the player's landed on the turn the fight was only joined: "recoils
         # from your strike" before any die was rolled (live, 2026-10-17). The outcome has
         # not happened yet — `swing-not-yet-struck`'s weight, read by a model, not a list.
         "early": ("beat-swing-early", 3),
         # A creature's blow written with a weapon the engine did not swing: the barkeep's
         # heavy crossbow on a sap turn (live, 2026-10-17), carried into the next beat.
         "foe_weapon": ("beat-foe-struck-with", 3),
         # A creature swinging at the player on the player's own beat, before its turn:
         # the barkeep's sap on the dagger beat of round 4 (live, 2026-10-17), swung again
         # on his own turn after it. A blow no die threw, as heavy as the early one.
         "at_you": ("beat-struck-at-early", 3)}

# The kinds repaired by the backstop alone, never a one-sentence rewrite. A rewrite is
# checked by reading the rewritten sentence back ALONE (`beat_verify.read_beat` reads only
# the sentences a beat did not have), and alone it loses whose blow it is: measured live
# 2026-10-17, "He bellows … and recoils from your strike" re-read alone named "someone not
# listed" and passed. A creature's blow re-read alone ("the heavy bolt whistles past your
# ear") has the same hole, so the sentence goes and the engine's own line takes its place
# (`GMAgent._repair_sentences` reads this set). The early blow is the case that was measured,
# and joins it: the joined tell stands in for a cut wind-up that landed.
#
# A creature's swing on the player's beat joins it for the same reason: "He lunges forward,
# swinging the heavy sap" rewritten and re-read alone is nobody's swing, and there is no
# engine line to stand in its place — nothing happened — so the sentence simply goes.
CUT_ONLY = frozenset({"beat-foe-struck-with", "beat-swing-early", "beat-struck-at-early"})

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
        if d.category == "foe_weapon" and d.line:
            # The engine's own line in the cut sentence's place, its numbers off (the
            # creature's roll is hidden): "the one behind the bar's attack with the sap
            # misses Kesst Vayr." The name becomes "you" later in the groom.
            from play.views import plain_tell

            line = plain_tell(d.line)
            line = line[:1].upper() + line[1:]
            if line and line not in text:
                text = text.replace(d.sentence, line, 1)
                notes.append(f"beat read back: foe_weapon: {d.sentence[:60]!r} -> the "
                             f"engine's line")
                continue
        text = cut(text, [d.sentence])
        if d.category == "trade" and d.line and d.line not in text:
            text = f"{d.line} {text}".strip()
        if d.category == "early" and d.line and d.line not in text:
            # The engine's own declaration stands where the landed blow was, once, as
            # `cut_premature_blows` puts it (the name becomes "you" later in the groom).
            text = narration_mod.put_before_the_hand_back(text, d.line)
        notes.append(f"beat read back: {d.category}: cut {d.sentence[:60]!r}")
    return text, notes
