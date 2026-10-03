"""speaks-for-the-player: the narrator puts words in the player's character's mouth.

Measured on the owner's 2026-10-03 save (docs/playtest-2026-10-03.md, item 16). The
player wrote "I smile and flirt with the clerk and offer the crate for coin." The plan's
invented `say` was caught and dropped ("a say in words the player never wrote",
`judgement.own_words_only`) — and the prose then gave Kesst the line anyway:

    "A piece of work like this," you say, your voice dropping into a sultry lilt that
    seems to hang in the dry air of the counting house, "deserves a bit more respect
    than just being weighed. It's a rare find, and I suspect you have a very keen eye
    for what is truly valuable."

Why nothing caught it: the rule had only ever been the prompt's ("The player says only
what their character does"). `prompts.INTIMATE_BRIEFING`'s own note records it, measured
2026-10-01: "no check in the pipeline catches the narrator speaking for the player on ANY
beat". `own_words_only` guards the plan's `say`, never the page.

The tradition agrees on the rule and not on the means. Play-by-post etiquette forbids
writing another player's dialogue ("godmodding"); SillyTavern's defence is a stop string
on the user's name, which its own issue tracker records missing whenever the model
writes "{{user}}" without the colon — and no stop string can fire inside second-person
prose, where the player's speech is "…,' you say". So, the house way: detect in code,
repair with one targeted rewrite, cut as the backstop.

**Detection.** A quotation whose speech clause has "you" (or the PC's name) as its
subject, or that the prose call tagged to the player (`_quotes.pc_lines`), whose content
words are not the player's own — under `judgement.OWN_WORDS` of them found in the
player's line, the bar the plan's `say` is held to. The player's own words said back
("You speak clearly, 'Just trying to start a conversation…'") pass. Never at an intimate
scene between adults at an explicit table: the owner's ruling of 2026-10-01 lets the
narrator speak for the player there and nowhere else (`gm/intimate.py`).

**Backstop.** The sentences holding the line are cut; when the player DID say something
this turn and it is not on the page, it takes the first cut sentence's place in the
player's own words.
"""
from __future__ import annotations

import re

from gm.narration import Finding

ORDER = 33
KINDS = frozenset({"speaks-for-the-player"})
DOORS = frozenset({"plan", "turn", "npc", "outcome"})


def invented_lines(text: str, player_text: str, said=(), pc_name: str = "",
                   pc_ref: str = "pc") -> list[tuple[int, int, str]]:
    """(qa, qb, line) for every line on the page the player's character speaks in words
    that are not the player's own."""
    from gm.checks._quotes import pc_lines
    from gm.judgement import OWN_WORDS, _content_words

    mine = _content_words(player_text)
    out = []
    for qa, qb, line in pc_lines(text, said, pc_name, pc_ref):
        theirs = _content_words(line)
        if not theirs:
            continue            # "Yes." — nothing to have invented
        if len(theirs & mine) / len(theirs) >= OWN_WORDS:
            continue            # the player's own words, said back
        out.append((qa, qb, line))
    return out


def _sentences_holding(text: str, spans) -> list[str]:
    """The page's sentences that hold the given quotations, whole and in order — exact
    substrings of `text`, so the repair can find them."""
    from gm import speech
    from gm.checks._quotes import _bounds

    blank = speech.blanked(text)
    bounds = _bounds(blank)
    picked: list[tuple[int, int]] = []
    for qa, qb in spans:
        for lo, hi in bounds:
            # By the line's own characters: its closing mark, not the space after it,
            # which the next sentence's span may start on.
            if lo <= qa < hi or lo <= qb - 2 < hi or (qa <= lo and hi <= qb):
                if (lo, hi) not in picked:
                    picked.append((lo, hi))
    picked.sort()
    # Neighbouring sentences one line runs across are one stretch.
    merged: list[list[int]] = []
    for lo, hi in picked:
        if merged and lo <= merged[-1][1] + 1:
            merged[-1][1] = max(merged[-1][1], hi)
        else:
            merged.append([lo, hi])
    out = []
    for lo, hi in merged:
        # The sentence's end mark sits inside the line ("…valuable.\""): its closing quote
        # mark belongs with it, or a cut leaves the mark behind.
        while hi < len(text) and text[hi] in "\"'”’":
            hi += 1
        if text[lo:hi].strip():
            out.append(text[lo:hi].strip())
    return out


def find(ctx) -> list:
    if getattr(ctx, "intimate", False):
        return []
    scene = ctx.scene
    pc = scene.pc() if scene is not None and hasattr(scene, "pc") else None
    pc_name = str(getattr(pc, "name", "") or "")
    pc_ref = str(getattr(pc, "ref", "") or "pc")
    found = invented_lines(ctx.text, ctx.player_text, ctx.said, pc_name, pc_ref)
    if not found:
        return []
    sentences = _sentences_holding(ctx.text, [(qa, qb) for qa, qb, _ in found])
    own = _players_own_words(ctx.player_text)
    wrote = (f"The player wrote only: {ctx.player_text.strip()!r}." if ctx.player_text
             else "The player wrote nothing for their character to say.")
    return [Finding(
        "speaks-for-the-player",
        f"the narrator gives the player's character words the player never wrote: "
        f"{found[0][2][:100]!r}",
        f"{wrote} Only the player speaks for their character. Keep what happens, but put "
        f"no words in the character's mouth: say what you do in plain narration, with no "
        f"quotation marks around anything you say"
        + (f" — or use the player's own words, exactly: {own!r}." if own else "."),
        weight=3, sentences=tuple(sentences))]


def _players_own_words(player_text: str) -> str:
    """What the player put in quotation marks this turn, joined — and nothing else.
    `judgement.spoken` would also hand back a reported complement ("I ask him about the
    docks" → "the docks"), which written as "You say, 'the docks.'" is the narrator
    inventing again."""
    from gm import speech

    text = str(player_text or "")
    parts = [text[a + 1:b - 1].strip() for a, b in speech.spans(text) if b - a > 2]
    return " ".join(" ".join(p for p in parts if p).split())


def backstop(ctx, text: str, findings) -> tuple[str, list[str]]:
    """Cut the sentences holding the invented lines; the player's own words, if they said
    any this turn and the page lacks them, stand in the first one's place."""
    scene = ctx.scene
    pc = scene.pc() if scene is not None and hasattr(scene, "pc") else None
    found = invented_lines(text, ctx.player_text, ctx.said,
                           str(getattr(pc, "name", "") or ""),
                           str(getattr(pc, "ref", "") or "pc"))
    if not found:
        return text, []
    sentences = _sentences_holding(text, [(qa, qb) for qa, qb, _ in found])
    own = _players_own_words(ctx.player_text)
    if own and own.lower() in text.lower():
        own = ""
    notes: list[str] = []
    out = text
    for k, sentence in enumerate(sentences):
        if sentence not in out:
            continue
        instead = ""
        if k == 0 and own:
            said = own if own[-1:] in ".!?" else own + "."
            instead = f"You say, “{said}”"
        out = out.replace(sentence, instead, 1)
        notes.append(f"speaks-for-the-player: cut {sentence[:80]!r}"
                     + (f" -> the player's own words {own[:60]!r}" if instead else ""))
    out = re.sub(r"[ \t]{2,}", " ", out)
    out = re.sub(r"[ \t]+([,.;:!?])", r"\1", out)
    return out.strip(), notes
