"""repair-claimed / ownership-claimed: the page mends or tames a construct the engine did not.

Measured on the owner's save, 2026-10-01. Sam wrote "I attempt to use my knowledge of
engineering and my deft hands to fix the spy in a way that makes it recognize me as its
owner." Nothing resolved — the Clockwork Spy was wreckage at -1 hit points — and the page
described a full repair and a machine recognising its new master. The next turn printed
"Clockwork Spy has bled out where they fell." beside "You have tamed the heart of the
spy, and it now waits for your command." The owner: "did not heal the clockwork spy when
I fixed it." The engine half is `rules/repair.py` (a destroyed construct cannot be
repaired; a damaged one is mended only by the rule, and the `repair` op is declared from
the words by `judgement.declare_repair`); this is the page half.

What is detected, in code, on the beats written after resolution (`turn`, `outcome`): a
sentence about a construct in the scene (`_people.about`, carried on by "it", the way
`closing_claimed` reads a beast) that

  * says it is mended or working again — "repaired", "fixed", "whirs back to life", "its
    gears begin to turn again", "stabilizes" — when no `repair` outcome resolved a
    success on it this turn (kind `repair-claimed`); or
  * says it is the player's — "recognizes you", "its new master", "waits for your
    command", "tamed", "obeys you", "loyal to you" — which nothing in the engine grants at
    all (kind `ownership-claimed`; `rules/repair.py` says why: a construct obeys its
    maker, and taking one from its master is control construct, a 7th-level spell).

An attempt, a denial or a conditional is not a claim ("you try to repair it", "it will
never obey you", "past repair"), and a question never is. Bounded on purpose to
constructs: a person won over is the attitude track's business and is told by its own
tells.

Repair: the house shape. One targeted rewrite of the flagged sentences with the engine's
fact named; if a rewrite still claims it, the backstop cuts the flagged sentences and
ends the beat on that fact.
"""
from __future__ import annotations

import re

from gm.narration import Finding

ORDER = 32
KINDS = frozenset({"repair-claimed", "ownership-claimed"})
DOORS = frozenset({"turn", "outcome"})

# Mended, or working again.
_MENDED = re.compile(
    r"\b(?:repaired|fixed(?!\s+(?:on|upon|to|in\s+place|its|his|her|their)\b)|mended|restored|reassembled|rebuilt|rewired|patched\s+up"
    r"|(?:is|are|stands?|looks?)\s+(?:whole|good\s+as\s+new|functional|operational)"
    r"(?:\s+again|\s+once\s+more)?"
    r"|(?:working|running|functioning|ticking|moving)\s+(?:again|once\s+more)"
    r"|(?:whirs?|whirr?s?|hums?|ticks?|clicks?|sputters?|shudders?|springs?|stirs?|comes?"
    r"|flickers?|blinks?|jolts?|lurches?|creaks?|grinds?|rattles?)\s+(?:back\s+)?"
    r"(?:to\s+life|into\s+(?:life|motion)|awake|alive)"
    r"|(?:gears?|cogs?|mechanisms?|clockwork|springs?|works)\s+(?:begin|begins|start|starts"
    r"|resume|resumes|turn|turns|spin|spins|tick|ticks|whir|whirs|whirr|whirrs)"
    r"\s+(?:to\s+\w+\s+)?(?:again|once\s+more)"
    r"|stabili[sz](?:es|ed|ing))\b", re.I)

# The player's now.
_OWNED = re.compile(
    r"\b(?:recogni[sz](?:es|ed|ing)\s+you"
    r"|(?:your|its|a)\s+new\s+(?:master|mistress|owner|maker|lord|keeper|friend"
    r"|companion|servant|pet)"
    r"|(?:as|is|are)\s+(?:its|his|her)\s+(?:master|mistress|owner|maker)"
    r"|(?:awaits?|awaiting|waits?|waiting)\s+(?:for\s+)?your\s+(?:command|commands|orders?"
    r"|word|instructions?)"
    r"|at\s+your\s+(?:command|service|disposal)"
    r"|(?:obeys?|obeying|serves?|serving|heeds?)\s+you"
    r"|(?:loyal|devoted|bound|bonded|attuned)\s+to\s+you"
    r"|tamed?|yours\s+(?:now|to\s+command))\b", re.I)

# The words in front of a claim that make it an attempt, a denial or a condition.
_NOT_SO = re.compile(
    r"\b(?:tries|try|trying|tried|attempts?|attempting|attempted|struggles?|fails?|failed"
    r"|cannot|can't|can’t|couldn't|couldn’t|won't|won’t|will\s+not|would|could|might"
    r"|may|unable|not|never|no\s+longer|nothing|if|whether|hope|hoping|hopes|wish"
    r"|beyond|past)\s+(?:[\w'’]+\s+){0,4}$", re.I)

_IT = frozenset({"it", "its", "itself"})


def _claimed(pattern, narration: str) -> bool:
    if "?" in narration:
        return False
    for m in pattern.finditer(narration):
        before = narration[max(0, m.start() - 60):m.start()]
        if _NOT_SO.search(before):
            continue
        return True
    return False


def mends(narration: str) -> bool:
    """Whether one sentence says a machine is mended or working again."""
    return _claimed(_MENDED, narration)


def owns(narration: str) -> bool:
    """Whether one sentence says a machine is the player's."""
    return _claimed(_OWNED, narration)


def _machines(scene) -> list:
    from rules import repair as repair_mod

    return [a for a in (getattr(scene, "actors", {}) or {}).values()
            if not getattr(a, "is_pc", False) and repair_mod.is_construct(a)]


def _mended_this_turn(ctx, ref: str) -> bool:
    from ._page import effects, field

    for o in ctx.outcomes:
        if field(o, "op") == "repair" and field(o, "verdict") == "success" \
                and any(e.get("ref") == ref and e.get("kind") == "heal" for e in effects(o)):
            return True
    return False


def _sentences_about(ctx, actor) -> list[tuple[str, str]]:
    """The page's sentences about this machine, as (written, narration): `_people.about`
    and the "it" run after it, as `closing_claimed` reads a beast."""
    from ._page import page_sentences
    from ._people import about, linked, names_person, pronoun_words

    pairs = page_sentences(ctx.text)
    theirs = {w for w, _ in about(ctx, actor.ref)}
    others = [str(a.name or "") for r, a in ctx.scene.actors.items()
              if r != actor.ref and not getattr(a, "is_pc", False)]
    narr = [n for _, n in pairs]
    by_n = {n: w for w, n in pairs}
    picked = linked(narr, lambda n: by_n.get(n, n) in theirs,
                    lambda n: any(names_person(n, o) for o in others if o),
                    family=_IT | pronoun_words(getattr(actor, "pronouns", "")))
    return [pairs[i] for i in picked]


def _the(actor) -> str:
    from rules.engine import _the_creature

    name = str(actor.name or "")
    return _the_creature(name) if getattr(actor, "from_template", "") else name


def _fact(actor, kinds) -> str:
    """The engine's fact, as the backstop's closing sentence."""
    who = _the(actor)
    if actor.is_dead or actor.has_state("state.down.dead"):
        line = f"{who} is wreckage: destroyed, and past any repair."
    else:
        line = f"{who} is not mended."
    if "ownership-claimed" in kinds:
        line += " It answers to its maker, not to you."
    return line


def _flags(ctx, actor) -> tuple[list[str], list[str]]:
    mended = _mended_this_turn(ctx, actor.ref)
    claims_mend, claims_own = [], []
    for written, narration in _sentences_about(ctx, actor):
        if not mended and mends(narration):
            claims_mend.append(written)
        if owns(narration):
            claims_own.append(written)
    return claims_mend, claims_own


def find(ctx) -> list:
    out: list = []
    for actor in _machines(ctx.scene):
        claims_mend, claims_own = _flags(ctx, actor)
        who = _the(actor)
        dead = actor.is_dead or actor.has_state("state.down.dead")
        if claims_mend:
            out.append(Finding(
                "repair-claimed",
                f"the page mends {actor.name}, and no repair resolved: "
                f"{claims_mend[0][:90]!r}",
                (f"{who} is destroyed and cannot be repaired: it is wreckage. "
                 if dead else f"{who} was not repaired this turn. ")
                + "Rewrite the sentence so it stays broken — it does not stir, whir, or "
                  "work again.",
                weight=4, sentences=tuple(claims_mend)))
        if claims_own:
            out.append(Finding(
                "ownership-claimed",
                f"the page makes {actor.name} the player's, which nothing granted: "
                f"{claims_own[0][:90]!r}",
                f"{who} is not the player's: it does not recognise them, obey them or "
                f"wait for their command. A construct answers to its maker. Rewrite the "
                f"sentence without that.",
                weight=4, sentences=tuple(claims_own)))
    return out


def backstop(ctx, text: str, findings) -> tuple[str, list[str]]:
    """Cut every sentence that still mends or tames a machine, and end the beat on the
    engine's fact."""
    from dataclasses import is_dataclass, replace

    from ._page import cut, page_sentences

    probe = replace(ctx, text=text) if is_dataclass(ctx) else ctx
    flagged_before = {s for f in findings for s in (f.sentences or ())}
    notes: list[str] = []
    for actor in _machines(ctx.scene):
        claims_mend, claims_own = _flags(probe, actor)
        flagged = list(dict.fromkeys(claims_mend + claims_own))
        if not flagged:
            # The labeller read the original; a rewrite may have lost who it meant.
            flagged = [w for w, n in page_sentences(text)
                       if w in flagged_before and (mends(n) or owns(n))]
        if not flagged:
            continue
        kinds = (({"repair-claimed"} if claims_mend else set())
                 | ({"ownership-claimed"} if claims_own else set())
                 or {f.kind for f in findings})
        text = f"{cut(text, flagged)} {_fact(actor, kinds)}".strip()
        notes.append(f"repair or ownership claimed: cut {len(flagged)} sentence(s) about "
                     f"{actor.name}")
    return text, notes
