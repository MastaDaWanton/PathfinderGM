"""A sale or a purchase the engine did not make, settled in the prose.

Measured live on the 2026-10-03 batch. "I agree to sell the crate to the smith for
whatever it is worth": the engine refused the sale — "The smith's counter is not open
yet; it opens at first light", it being half past one in the morning — and the crate and
the purse stood as they were. The page opened "The transaction is finalized. The heavy
clink of the coin is the only thing that breaks the silence of the forge." The refusal,
the one thing the player needed to read, was nowhere on it.

`contradicts-the-engine`'s counter-screen rule (`narration.hands_over_goods`) only runs
while the trade screen is open; this is the turn where a trade was declared at the table.
It applies when a `sell` or `buy` was refused this turn, or when the reading declared one
and none resolved. Closed vocabulary: a sentence that settles a deal — the transaction
or the deal finished, coin paid over to the player, the payment theirs. Repair: one
rewrite; backstop: the sentences go and the engine's own refusal takes their place.
"""
from __future__ import annotations

import re

from gm.narration import Finding

from ._page import cut, field, page_sentences

ORDER = 21
KINDS = frozenset({"trade-claimed"})
DOORS = frozenset({"plan", "turn"})

_TRADE_OPS = ("sell", "buy")
_SETTLED = re.compile(
    r"\b(?:transaction|deal|sale|bargain|trade|exchange)\s+(?:is|was|has\s+been)\s+"
    r"(?:\w+\s+)?(?:finali[sz]ed|finished|complete[d]?|done|concluded|settled|struck|"
    r"sealed|made|closed)\b"
    r"|\b(?:clink|chink|jingle|weight)\s+of\s+(?:the\s+)?coins?\b"
    r"|\bcoins?\s+(?:clink|chink|jingle|spill|change\s+hands|pass(?:es)?\s+to\s+you)\b"
    r"|\b(?:pays|paid)\s+you\b|\bpresses\s+(?:the\s+)?coins?\b"
    r"|\b(?:hands|slides|passes|counts\s+out|drops)\s+(?:you\s+)?(?:a|the|some|several)?\s*"
    r"(?:\w+\s+)?(?:coins?|silver|gold|copper|pouch|purse)\s+(?:to|into|across\s+to)?\s*you"
    r"|\bthe\s+(?:payment|money|coin)\s+is\s+yours\b", re.I)


def _trade_state(ctx) -> tuple[list, bool]:
    """(the refused trade outcomes, whether any trade resolved this turn)."""
    refused, resolved = [], False
    for o in ctx.outcomes:
        if field(o, "op") not in _TRADE_OPS:
            continue
        if field(o, "status") == "refused":
            refused.append(o)
        else:
            resolved = True
    return refused, resolved


def _declared(ctx) -> bool:
    reading = ctx.reading if isinstance(ctx.reading, dict) else {}
    return any(isinstance(a, dict) and a.get("act") in _TRADE_OPS
               for a in reading.get("actions") or [])


def find(ctx) -> list:
    refused, resolved = _trade_state(ctx)
    if resolved or not (refused or _declared(ctx)):
        return []
    flagged = [w for w, n in page_sentences(ctx.text) if _SETTLED.search(n)]
    if not flagged:
        return []
    why = str(field(refused[0], "tell") or "").strip() if refused else ""
    return [Finding(
        "trade-claimed",
        f"no trade was made ({why or 'none resolved'}), and the prose settled one: "
        f"{flagged[0][:90]!r}",
        (f"Nothing was sold or bought: {why} " if why else
         "Nothing was sold or bought this turn. ")
        + "Rewrite those sentences so no deal is struck and no coin changes hands — the "
          "other party may refuse, hesitate, or say why not. Keep the rest.",
        weight=3, sentences=tuple(flagged))]


def backstop(ctx, text: str, findings) -> tuple[str, list[str]]:
    gone = [s for f in findings for s in f.sentences if s in text]
    if not gone:
        return text, []
    kept = cut(text, gone)
    refused, _ = _trade_state(ctx)
    why = str(field(refused[0], "tell") or "").strip() if refused else ""
    if why and why not in kept:
        kept = f"{why} {kept}".strip()
    return kept, [f"a trade the engine did not make, settled in the prose: cut {len(gone)}"]
