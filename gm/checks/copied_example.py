"""A sentence lifted from a worked example the narrator was shown.

Measured 2026-10-16 on the fight audit (gemma-4-12B, free narrator, master c916a61f): two
beats in eleven opened "You break contact and the window is four running steps away,
shutters open on a drop you have not measured" — COMBAT_EXAMPLES[4], the last example a
fight is shown — while the player was punching a man forty feet off. `narration.review`
caught the first as `echoes-the-examples` (59 shared phrases); the whole-beat rewrite
removed every one and was refused anyway (it kept 0.0 of the draft's "events", which were
the example's), and in a fight there is no second rewrite and the echo had no backstop,
so the copied passage shipped whole. Across every scratchpad save, 5 of 5 caught copies
of three runs or more shipped the same way.

So the copy is now a sentence-sized finding, repaired the house way: one targeted
rewrite of each copied sentence with the copied words named (`GMAgent._repair_sentences`),
kept only if it no longer copies, and a deterministic backstop under it that cuts what
still does. Every door: the free narrator, a creature's turn, the consequence call and
the planned narrator's beats (which get no whole-beat rewrite at all) are all shown
demonstrations or repaired by a call that is.

What counts as a copy is a set comparison of the page with text the app itself wrote
(`narration.copied_sentences`: three or more six-word runs shared with
`prompts.demonstrations`, plus the owner's intimate passages shown this beat) — never a
reading of what the prose means. One or two shared runs are stock English, measured.
"""
from __future__ import annotations

from gm.narration import Finding

ORDER = 70
KINDS = frozenset({"copies-an-example"})
DOORS = frozenset({"plan", "turn", "npc", "outcome"})


def _index(ctx):
    from gm import narration

    return narration.demonstration_index(tuple(getattr(ctx, "shown", ()) or ()))


def _copied(ctx, text: str) -> list[str]:
    """The page's own sentences that copy a demonstration."""
    from gm import narration

    from ._page import page_sentences

    index = _index(ctx)
    # The page's sentences, as written (speech and all: a copied line of dialogue is as
    # much a copy), so the repair's `replace` finds them; judged by the same rule as
    # `narration.copied_sentences`.
    return [w for w, _n in page_sentences(text)
            if narration.copied_sentences(w, index)]


def _runs(sentence: str, index) -> list[str]:
    """The copied stretches of `sentence`, in its own order: overlapping six-word runs
    the index holds, merged — "you break contact and the window is four running steps
    away", not six fragments of it in alphabetical order."""
    from gm import narration, speech

    words = narration._words(speech.lift(sentence)[0])
    n = narration.ECHO_LENGTH
    hits = [i for i in range(max(0, len(words) - n + 1))
            if tuple(words[i:i + n]) in index]
    stretches: list[list[int]] = []
    for i in hits:
        if stretches and i <= stretches[-1][1]:
            stretches[-1][1] = i + n
        else:
            stretches.append([i, i + n])
    return [" ".join(words[a:b]) for a, b in stretches]


def find(ctx) -> list[Finding]:
    copied = _copied(ctx, ctx.text)
    if not copied:
        return []
    index = _index(ctx)
    runs = [r for s in copied for r in _runs(s, index)][:4]
    quoted = "; ".join(repr(r) for r in runs)
    facts = " ".join(t for t in (ctx.tells or ())[:3] if t)
    return [Finding(
        "copies-an-example",
        f"{len(copied)} sentence(s) copied from a worked example, including "
        f"{copied[0][:80]!r}",
        # The truth repair keeps "its voice, its detail and its length", and a copied
        # sentence's detail is the example's scene — a window, a cart, a chase that did
        # not happen. So the fact says the whole of it is borrowed and gives what is true.
        f"This sentence is copied word for word from a worked example ({quoted}); it "
        f"describes that example's scene, not this one, and none of it happened here. "
        f"Write it again in entirely new words, saying only what is true now"
        + (f": {facts}" if facts else ".")
        + " Use none of the copied words.",
        weight=2,
        sentences=tuple(copied),
    )]


def backstop(ctx, text: str, findings) -> tuple[str, list[str]]:
    """Cut every sentence that still copies a demonstration. A beat that was nothing but
    the example is cut to nothing: the view then writes the engine's own lines in its
    place (`play.views`, the empty-turn floor), which are true, where the example was
    not."""
    from dataclasses import is_dataclass, replace

    from ._page import cut

    probe = replace(ctx, text=text) if is_dataclass(ctx) else ctx
    still = _copied(probe, text)
    if not still:
        return text, []
    return cut(text, still), [f"copied from a worked example: cut {len(still)} "
                              f"sentence(s), from {still[0][:60]!r}"]
