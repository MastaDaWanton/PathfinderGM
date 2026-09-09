"""What happened in the turns that fell out of the window.

The near window holds recent play verbatim. Older turns are cut by `prompts.pack`,
and before this module they were simply gone: the campaign could run forty turns, the
oldest exchanges would leave the prompt, and nothing anywhere remembered that they had
happened.

Three decisions, each with a reason that is not a preference.

**Built from the engine, not from prose.** Every resolved turn already carries
outcomes, and an outcome names its op and the people it touched. An entry assembled
from those cannot hallucinate, which is the failure SillyTavern documents for its own
summariser ("the outputs may lose some important details or contain hallucinations").
No model call, so no latency on a turn that already costs twenty-five seconds.

**Written once, never re-summarised.** The one direct comparison available puts
recursive summarisation last of every approach measured — 35.3% against 78.6% for
periodic summaries and 94.4% for full context — and names the cause as detail lost
through repeated re-compression. So an entry is made when its turn resolves and is
never rewritten.

**No numbers.** An entry saying the player took nine damage is a second store of a
fact the engine already holds, and the second law forbids parallel stores. The moment
the two disagree, the prompt carries a stale near-miss beside the truth, which is the
single most damaging thing measured in the retrieval literature: one related-but-wrong
passage beside a correct one dropped accuracy from 56.4% to 45.9%, while wholly
irrelevant text did no harm at all. So the prose of an entry may not contain a digit;
the turn index is a field, not a sentence.

See docs/memory-policy.md and docs/retrieval-and-memory.md.
"""
from __future__ import annotations

import re

# What the ledger may say about a turn. Deliberately short of the full op vocabulary:
# a Perception check is not a thing worth remembering forty turns later, and a ledger
# that records everything is a second transcript rather than a memory.
_WORTH_KEEPING = {
    "travel": "went to {where}",
    "quest": "took up {title}",
    "quest_step": "moved {title} along",
    "found": "founded {title}",
    "venture": "went into {title}",
    "buy": "bought from {who}",
    "sell": "sold to {who}",
    "give": "handed something to {who}",
    "loot": "stripped {who}",
    "begin_encounter": "fought {who}",
    "rest": "rested",
    "craft": "worked at a craft",
}

# What was actually said, kept in full up to here. docs/memory-policy.md planned one
# small model call at eviction for exactly this — the part the engine does not own —
# and once speech had an op of its own the call turned out to be unnecessary: the words
# are in an effect the engine wrote, so they can be kept mechanically, with no latency
# and nothing to invent. A promise made forty turns ago is the single most useful thing
# a ledger can hold, and it is the thing a summariser would have been most likely to
# get wrong.
SAID_CAP = 160

# How much of the prompt the ledger may take. Small on purpose: the Stanford agents
# result, which `rules/cards.py` already cites for the same reason, is that a handful
# of relevant lines beats the whole history.
BUDGET_CHARS = 1200
# How many entries are kept on the campaign at all. Past this the oldest go, because a
# ledger that grows without limit is the problem it was built to solve.
ENTRY_CAP = 400

_DIGIT = re.compile(r"\d")


def note(outcomes, *, turn: int, hist: int = 0, spoke_with: str = "", where: str = "",
         names: dict | None = None) -> dict | None:
    """One entry for one resolved turn, or None if nothing worth keeping happened.

    `outcomes` are the engine's own, so the op names here are the engine's decisions
    rather than anything a model proposed. `names` maps refs to the names the player
    read, because "you stripped c6" is not a memory of anything.
    """
    did: list[str] = []
    for o in outcomes or []:
        if str(getattr(o, "op", "") or "") == "say":
            words = _said(o)
            if words:
                heard = _named(o, ("to",), names)
                did.append((f"told {heard}" if heard else "said") + f", “{words}”")
            continue
        shape = _WORTH_KEEPING.get(str(getattr(o, "op", "") or ""))
        if not shape:
            continue
        said = shape.format(where=_named(o, ("place", "to", "biome"), names) or where
                            or "somewhere new",
                            title=_named(o, ("title", "name"), names) or "something",
                            who=_named(o, ("ref", "to", "from_", "target", "who"),
                                       names) or "someone")
        if said not in did:
            did.append(said)
    # Only when the turn produced no `say` of its own. With both, the entry read
    # "you spoke with the clerk, told the clerk, ..." — the same fact twice, which is
    # the thing this file exists to keep out of the prompt.
    if spoke_with and not any(s.startswith(("spoke", "told", "said")) for s in did):
        did.insert(0, f"spoke with {spoke_with}")
    if not did:
        return None
    text = "you " + ", ".join(did)
    # The rule, enforced rather than asked for: no mechanical number reaches the
    # ledger. A name with a digit in it is not worth the door it would open.
    text = _DIGIT.sub("", text)
    return {"turn": int(turn), "hist": int(hist), "at": str(where or ""), "text": text}


def _said(o) -> str:
    """The words on a `say` outcome, as the engine wrote them into its effect."""
    for e in getattr(o, "effects", None) or []:
        if isinstance(e, dict) and e.get("kind") == "said" and e.get("words"):
            return " ".join(str(e["words"]).split())[:SAID_CAP]
    return ""


def _named(o, keys, names: dict | None) -> str:
    """The first of `keys` any of this outcome's effects carries, as a name.

    An `Outcome` holds `effects`, a list of dicts the engine wrote — there is no
    params bag to read, and the ref in an effect is `c6` rather than anybody the
    player would recognise, so refs are resolved through the scene's own names.
    """
    for e in getattr(o, "effects", None) or []:
        if not isinstance(e, dict):
            continue
        for key in keys:
            got = e.get(key)
            if got in (None, "", []):
                continue
            got = str(got)
            return str((names or {}).get(got, got))
    return ""


def keep(entries: list[dict], entry: dict | None) -> list[dict]:
    """Add an entry and hold the cap. Entries are never rewritten, only dropped.

    A run of identical entries is collapsed to the first. Six turns of asking the same
    clerk the same kind of question is one memory, and "ten of ten paragraphs ended the
    same way" is this project's oldest measured smell — a ledger is the cheapest place
    in the app to spend the whole budget saying one thing over and over.
    """
    if entry is None:
        return entries
    if entries and entries[-1].get("text") == entry.get("text"):
        entries[-1]["hist"] = entry.get("hist", entries[-1].get("hist"))
        entries[-1]["turn"] = entry.get("turn", entries[-1].get("turn"))
        return entries
    entries.append(entry)
    # In place. Returning `entries[-ENTRY_CAP:]` instead built a new list and left the
    # campaign's own still growing — the cap read correctly and enforced nothing, on
    # every caller, because none of them reassign. Caught by the cap's own test.
    if len(entries) > ENTRY_CAP:
        del entries[:-ENTRY_CAP]
    return entries


def block(entries, *, before_hist: int, budget: int = BUDGET_CHARS) -> str:
    """The ledger as the prompt states it: only turns the window no longer carries.

    `before_hist` is how many history messages the budget cut from the front, and an
    entry records `hist` — the length of the history when it was written — so the two
    are counted in the same units. Anything at or below the cut is outside the window
    and is the ledger's business; anything above it is still there verbatim and is
    not, because a fact in the prompt twice is the parallel store the second law
    forbids.

    Newest first while the budget lasts, then reversed back into reading order: the
    most recent of the forgotten turns is the one most worth the room.
    """
    older = [e for e in entries or [] if int(e.get("hist", 0)) <= int(before_hist)]
    if not older:
        return ""
    lines, spent = [], 0
    for e in reversed(older):
        line = f"  * {e.get('text', '')}" + (f" (at {e['at']})" if e.get("at") else "")
        if lines and spent + len(line) > budget:
            break
        lines.append(line)
        spent += len(line)
    return ("EARLIER, WHICH YOU NO LONGER HAVE THE WORDS FOR (facts, kept by the "
            "engine; do not contradict them):\n" + "\n".join(reversed(lines)))
