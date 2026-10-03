"""A people's name used in the prose as one person's name.

Item 14 of the 2026-10-03 playtest stopped the planner and the minting doors from NAMING a
person after their people ("a man named Korvu" made c11 "Korvu"). Measured live on the
merged branch the same day, the third turn played: the prose still wrote "Beside you, the
smith, Korvu, reaches out…" — the narrator had learned the habit from the older turns in
its own history ("a man named Korvu", "Korvu leans his head back…"), and nothing read the
page for it. The planner fix stops the record being wrong; this stops the page.

Shapes, never a free reading (OntoNotes keeps NORP apart from PERSON for this reason):

  * "named Korvu" / "called Korvu" — the naming itself;
  * ", Korvu," after a role — the smith, Korvu, reaches out — an appositive name;
  * "Korvu leans…" opening a sentence with no article — a bare proper subject.

"the Korvu", "a Korvu", "one of the Korvu", "Korvu people" and the face line's own "is of
the Korvu people" are a people, and are left alone. The appositive and bare-subject shapes
read only the world's own peoples (`names.peoples`); "named X" reads every people's name
(`names.people_names`, the rulebook's too). Speech is never read: a character may say what
they like. Repair: one rewrite; backstop: the naming is cut ("a man named Korvu" → "a
man", "the smith, Korvu, reaches" → "the smith reaches") and a bare subject takes its
article ("Korvu leans" → "The Korvu leans").
"""
from __future__ import annotations

import re

from gm.narration import Finding

from ._page import page_sentences

ORDER = 23
KINDS = frozenset({"peoples-name-as-name"})
DOORS = frozenset({"plan", "turn", "npc", "outcome"})


def _names(ctx) -> tuple[list[str], list[str]]:
    """(the world's own peoples, every people's name), as written, longest first."""
    from rules import names as names_mod

    own: set[str] = set()
    try:
        own = {str(n) for n in names_mod.peoples(ctx.world).values() if n} \
            if ctx.world is not None else set()
    except Exception:  # noqa: BLE001 — a world with no peoples has none to misuse
        own = set()
    every = set(own) | {n.title() for n in names_mod.people_names(ctx.world, ctx.scene)}
    key = lambda n: (-len(n), n)  # noqa: E731
    return sorted(own, key=key), sorted(every, key=key)


def _shapes(own: list[str], every: list[str]) -> list[tuple[re.Pattern, str]]:
    out: list[tuple[re.Pattern, str]] = []
    for name in every:
        n = re.escape(name)
        out.append((re.compile(rf"\s*,?\s+(?:named|called)\s+{n}s?(?![\w-])"), "named"))
    for name in own:
        n = re.escape(name)
        out.append((re.compile(rf",\s*{n}(?![\w-]),"), "apposition"))
        out.append((re.compile(
            rf"^(\s*){n}(?![\w'’-])(?=\s+(?!people\b|folk\b|man\b|woman\b|men\b|women\b|"
            rf"and\b|or\b)[a-z]+(?:s|ed)\b)"), "subject"))
    return out


def _fix(sentence: str, shapes) -> str:
    for rx, kind in shapes:
        if kind == "named":
            sentence = rx.sub("", sentence)
        elif kind == "apposition":
            sentence = rx.sub("", sentence)
        else:
            sentence = rx.sub(lambda m: f"{m.group(1)}The {m.group(0).strip()}", sentence)
    return sentence


def find(ctx) -> list:
    own, every = _names(ctx)
    if not every:
        return []
    shapes = _shapes(own, every)
    flagged = [w for w, n in page_sentences(ctx.text)
               if any(rx.search(n) for rx, _k in shapes)]
    if not flagged:
        return []
    return [Finding(
        "peoples-name-as-name",
        f"a people's name used as a person's name: {flagged[0][:90]!r}",
        "That is the name of a people of this world, not anyone's own name. Call the "
        "person by what they are — the smith, the laborer, the man in the heavy coat — or "
        "by a name they have given; never 'named <people>' or '<people>' alone as a name.",
        weight=2, sentences=tuple(flagged))]


def backstop(ctx, text: str, findings) -> tuple[str, list[str]]:
    own, every = _names(ctx)
    shapes = _shapes(own, every)
    fixed, n = text, 0
    for f in findings:
        for s in f.sentences:
            if s in fixed:
                new = _fix(s, shapes)
                if new != s:
                    fixed, n = fixed.replace(s, new, 1), n + 1
    return fixed, ([f"a people's name as a person's: respelled {n}"] if n else [])
