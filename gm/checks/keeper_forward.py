"""keeper-forward: a keeper the player has not dealt with speaks to them first.

Measured on the 2026-09-28 playtest (item 9.1): the market's keeper was the first person
the player met at the market — minted on arrival for the trade panel, listed in WHO IS
HERE, and so walked up to the player. The owner's ruling: keepers are present but in the
background until dealt with. The brief says so (`gm/brief/keepers_in_background.py`);
this holds the page to it. "Dealt with" is `rules.hooks.dealt_with`, the same answer the
brief gave, never a second copy of the rule.

**Cut, never rewritten** (2026-09-30 playtest, item 12). The first version let the
sentence repair rewrite the flagged lines, and the rewrite was spliced in INSIDE the
quotation marks: the model paraphrased this module's own fix hint, so Gorm Vesper "said"
`'Gorm Vesper remains at their post, silent, until you turn to them.'` — five narration
sentences in quotes across beats 51 and 53. There is nothing for a rewrite to say that
is true: a keeper in the background does not speak first, so the line goes. `REWRITE =
False` sends the finding straight to `backstop`, which cuts each line with its speech
clause (`_quotes.cut_units` — the quote and its "he says", PARC's whole relation), so no
"he says" is left claiming a line that is gone. And `find` counts only lines still on
the page, so the cut is seen to have held.
"""
from __future__ import annotations

from gm.narration import Finding

ORDER = 66
KINDS = frozenset({"keeper-forward"})
DOORS = frozenset({"turn"})
# Repaired by the backstop alone: see the docstring.
REWRITE = False


def _on_the_page(ctx, lines: list[str]) -> list[str]:
    """The lines whose quotation still stands in the beat."""
    from gm.checks._quotes import quote_of

    text = str(ctx.text or "")
    return [ln for ln in lines if quote_of(text, ln) is not None]


def find(ctx) -> list:
    from gm.brief.keepers_in_background import background
    from gm.checks._people import pronoun_forms

    buying = ""
    facts = (ctx.brief_facts or {}).get("keepers_in_background")
    quiet = background(ctx.scene, ctx.reading, ctx.player_text, buying)
    if facts is not None:
        # What the brief was shown wins: a keeper it did not put in the background (the
        # counter opened this turn) was the player's to deal with.
        shown = set(facts.get("refs") or [])
        quiet = [a for a in quiet if a.ref in shown]
    out = []
    for actor in quiet:
        lines = [str(r.get("line") or "") for r in ctx.said or ()
                 if str(r.get("who") or "") == actor.ref and str(r.get("to") or "") == "you"
                 and str(r.get("line") or "").strip()]
        lines = _on_the_page(ctx, lines)
        if not lines:
            continue
        he, him, his = pronoun_forms(getattr(actor, "pronouns", ""))
        out.append(Finding(
            "keeper-forward",
            f"{actor.name} ({actor.ref}) speaks to the player unprompted, while in the "
            f"background: {lines[0][:120]!r}",
            f"{actor.name} is at {his} work and does not approach the player or speak "
            f"first; {he} answers only if the player turns to {him}.",
            weight=2, sentences=tuple(lines)))
    return out


def backstop(ctx, text: str, findings) -> tuple[str, list[str]]:
    """Cut each flagged line with its speech clause."""
    from gm.checks._quotes import cut_units

    lines = [s for f in findings if f.kind in KINDS for s in f.sentences]
    out, gone = cut_units(text, lines)
    return out, [f"keeper-forward: cut {g[:80]!r}" for g in gone]
