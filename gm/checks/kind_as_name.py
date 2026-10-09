"""kind-as-name: somebody gives, as their own name, what they ARE.

The owner, 2026-10-09, playing 0.2.12: a creature met on an ore seam, asked "What is your
name", answered "I am Aelzeldra" — "it introduced itself as its species like it was a
name". The engine had met it as a kind of thing ("you find an Aelzeldra there before
you"), and a kind is not anybody's name; nor is a people's ("I am Korvu", item 14 of
2026-10-03, where Korvu is one of Pangrella's peoples).

**Nothing here reads English.** Who gave which name is the beat reader's answer
(`Reading.names`, a closed choice of the codes here, the name copied off the page), and
which line each person speaks is its answer too (`Reading.lines`). Code compares the
name with the engine's own vocabularies — the world's peoples and the rulebook's races
(`names.people_names`), and the person's own kind (`bestiary.kind_names`): exactly
`beat_reader.what_not_who`, the rule `name_refusal` refuses the record with, so the page
and the record cannot disagree about what is a name. The name is then found in that
person's own spoken lines by a plain search for the reader's own string.

The repair is the house shape: one targeted rewrite of the line, told the engine's fact —
their real name if the world holds one for them, else that they give none — and kept
only if the rewritten line no longer gives the kind. The backstop cuts the line with its
speech clause (`_quotes.cut_units`), as `narration_in_quotes` does: a line whose whole
point was a wrong name says nothing true without it.

Narration that names a person after their people ("a man named Korvu") stays
`peoples_name`'s; this reads speech, where that check never looks.
"""
from __future__ import annotations

import re

from gm.narration import Finding

ORDER = 24
KINDS = frozenset({"kind-as-name"})
DOORS = frozenset({"plan", "turn", "npc", "outcome"})


def _giving(ctx) -> list[tuple[str, str, str, list[str]]]:
    """(ref, name, why, lines) for each name the reader read off the page that is what
    its bearer is, with the bearer's own spoken lines that give it, as they stand now."""
    from gm import beat_reader, speech

    reading = ctx.attribution
    if not isinstance(reading, beat_reader.Reading) or not reading.read:
        return []
    actors = getattr(ctx.scene, "actors", {}) or {}
    text = str(ctx.text or "")
    read_lines = {ln.words for ln in reading.lines}
    # Quotations on the page now that the reader never read: a repair's own rewrite.
    # Judged by the name alone, which this beat has already shown to be a kind given
    # as a name — otherwise a rewrite that says "I am Aelzeldra" again in other words
    # would pass its own re-check.
    fresh = [text[a + 1:b - 1].strip() for a, b in speech.spans(text)
             if text[a + 1:b - 1].strip() and text[a + 1:b - 1].strip() not in read_lines]
    out = []
    for n in reading.names:
        ref, name = str(n.get("who") or ""), str(n.get("name") or "")
        if ref not in actors or getattr(actors[ref], "is_pc", False) or not name.strip():
            continue
        why = beat_reader.what_not_who(ctx.scene, ctx.world, ref, name)
        if not why:
            continue
        said = re.compile(rf"(?<![\w'’-]){re.escape(name.strip())}(?![\w'’-])", re.I)
        own = [ln.words for ln in reading.lines
               if ln.speaker(reading) == ref and ln.words in text and said.search(ln.words)]
        own += [w for w in fresh if said.search(w)]
        if own:
            out.append((ref, name.strip(), why, list(dict.fromkeys(own))))
    return out


def find(ctx) -> list:
    from gm import beat_reader

    out = []
    actors = getattr(ctx.scene, "actors", {}) or {}
    for ref, name, why, lines in _giving(ctx):
        who = actors[ref]
        shown = str(getattr(who, "name", "") or ref)
        true = str(getattr(who, "true_name", "") or "")
        # Their own name, when the world holds one that is a name; otherwise none at all.
        if true and true.lower() != name.lower() and not beat_reader.what_not_who(
                ctx.scene, ctx.world, ref, true):
            fact = f"Their own name is {true}: if they give a name, it is that one."
        else:
            fact = "They have no name to give here: they give none."
        what = ("a people of this world" if why.startswith("a people")
                else "what they are")
        out.append(Finding(
            "kind-as-name",
            f"{shown} ({ref}) gives {name!r} as their own name — {why}",
            f"{name} is {what}, not anybody's name. {fact} Keep the line as speech, in "
            f"their voice.",
            weight=2, sentences=tuple(lines)))
    return out


def backstop(ctx, text: str, findings) -> tuple[str, list[str]]:
    """Cut each line still giving the kind as a name, with its speech clause."""
    from dataclasses import replace

    from gm.checks._quotes import cut_units

    still = {s for f in find(replace(ctx, text=text)) for s in f.sentences}
    lines = [s for f in findings if f.kind in KINDS for s in f.sentences if s in still]
    if not lines:
        return text, []
    out, gone = cut_units(text, lines)
    return out, [f"kind-as-name: cut {g[:80]!r}" for g in gone]
