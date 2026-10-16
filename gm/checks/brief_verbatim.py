"""The brief's own wording printed as prose (item 17.6).

Measured on the Bobby playtest, 2026-09-28, turn 7: "There is a settlement to the north,
reachable by journey: Dustgate. There is a settlement to the west, reachable by journey:
Grotburrow." That is the ROADS OUT line's shape, not its words — it shares no 3-gram with
the brief, so an echo index would never see it. What gives it away is the shape: a
lowercase label, a colon, a capitalised name and a full stop. Over the 32 prose beats of
the five saves on this machine that shape occurred twice, both times this defect. CALYPSO
(Zhu et al. 2023) measured the same leak in another system: a prompt's stat blocks echoed
into the output despite an instruction not to, which is why this is detected in code and
not forbidden in the brief.

Two detectors: (1) the label-colon shape in the narration; (2) a 4-gram of a brief
section's registered scaffold (`gm.brief.scaffold()`: the fixed words of its lines, the
world's own values left out), so the brief's labels are caught verbatim too. A gram made
only of short function words is not evidence. Repair: one rewrite of the sentence in the
story's own words. Backstop: the sentence is cut.
"""
from __future__ import annotations

import re

from gm.narration import Finding

from ._page import cut, page_sentences

ORDER = 60
KINDS = frozenset({"brief-wording-on-the-page"})
DOORS = frozenset({"plan", "turn", "npc", "outcome"})

# "reachable by journey: Dustgate." / "the roads out: Dustgate, Grotburrow." — a label
# in lower case (it is the model's paraphrase of ours), a colon, then only capitalised
# names to the full stop.
_NAME = r"[A-Z][\w'’-]*(?:\s+(?:of|the|de|du|von|van)?\s*[A-Z][\w'’-]*)*"
_LABEL_COLON = re.compile(
    rf"\b[a-z][a-z'’ -]{{2,60}}:\s+{_NAME}(?:\s*(?:,|and|or)\s*{_NAME})*\s*[.!]?\s*$")

_SHORT = frozenset("the a an of to in on at by is are was be it and or for with as its "
                   "this that they there then".split())


def _grams(narration: str) -> set[tuple[str, ...]]:
    from gm import brief

    return {g for g in brief.grams(narration)
            if sum(1 for w in g if w not in _SHORT and len(w) >= 4) >= 1}


def _scaffold() -> frozenset:
    try:
        from gm import brief

        return brief.scaffold()
    except Exception:  # noqa: BLE001 — no scaffold, the shape detector still runs
        return frozenset()


def _names(scene) -> list[str]:
    """The names the people here go by, longest first."""
    names = {" ".join(str(getattr(a, "name", "") or "").split())
             for a in (getattr(scene, "actors", {}) or {}).values()}
    return sorted((n for n in names if n), key=len, reverse=True)


def _without(narration: str, names) -> str:
    """The narration with every person's own name taken out, by position, not by reading."""
    low = narration.lower()
    for name in names:
        n = name.lower()
        at = low.find(n)
        while at >= 0:
            narration = narration[:at] + " " * len(n) + narration[at + len(n):]
            low = narration.lower()
            at = low.find(n)
    return narration


def flagged(text: str, names=()) -> list[tuple[str, str]]:
    """(sentence as written, what gives it away) for each sentence that prints the
    brief's wording. `names` are the people here: a person's own name is not the brief's
    wording even when the brief's scaffold holds it. Measured 2026-10-16 on the planned
    benches: the market's master goes by "the master of the market", the scaffold holds "is
    the master of the market", and every sentence naming him was "repaired" — renamed "the
    merchant" (he sells nothing) or made "You walk the rows, checking the weight of the
    starweave", the player doing the master's rounds: 11 of 40 town and talk beats, in
    both narrators' slots alike."""
    scaffold = _scaffold()
    out = []
    for written, narration in page_sentences(text):
        if _LABEL_COLON.search(narration):
            out.append((written, narration.rsplit(":", 1)[0].split(",")[-1].strip()
                        + ":"))
            continue
        hit = sorted(_grams(_without(narration, names)) & scaffold)
        if hit:
            out.append((written, " ".join(hit[0])))
    return out


def find(ctx) -> list:
    found = flagged(ctx.text, _names(ctx.scene))
    if not found:
        return []
    return [Finding(
        "brief-wording-on-the-page",
        f"the brief's own wording is printed as prose ({found[0][1]!r}): "
        f"{found[0][0][:90]!r}",
        f"This sentence copies the notes you were given ({found[0][1]!r}) instead of "
        f"telling the story. Say the same thing as the world would show it — no label, "
        f"no colon, no list of names.",
        weight=2, sentences=tuple(w for w, _ in found))]


def backstop(ctx, text: str, findings) -> tuple[str, list[str]]:
    gone = [w for w, _ in flagged(text, _names(getattr(ctx, "scene", None)))]
    if not gone:
        return text, []
    return cut(text, gone), [f"the brief's wording on the page: cut {len(gone)} "
                             f"sentence(s)"]
