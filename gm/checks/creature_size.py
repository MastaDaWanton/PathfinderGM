"""creature-size: the page makes a creature bigger or smaller than its own record.

The owner's report on 0.2.21 (2026-10-27): *"A Griol which is a medium sized creature was
described as large"*. The grioth is a Medium monstrous humanoid (Bestiary 5); the beats
called it "a massive creature", "a large, monstrous figure" and "the towering figure".
The first cause was that no narrator was told its size (`bestiary.body_words` is in every
brief and slot now); this check is the net under that, because a fact in a brief is an
instruction, and the last beat's own words carry on: replayed with the size given and the
old beat before it, "the massive creature" still came back 1 time in 6.

**What is detected, by structure.** A creature that is no person (`bestiary.body_size`
gives a size only then) which the beat reader says the page mentions — present, or gone
in this batch (`Reading.gone`). The sentences holding its mentions are read once, by the
narrator's own model, into a closed answer: one of the book's nine sizes, each glossed
beside a grown man (the d20 size table's "typical" heights, `bestiary.SIZE_BESIDE_A_MAN`),
or "not said". Code never reads the English; it compares the answer with the record.

**What counts as a contradiction** (`contradicts`), measured before it was set: the page's
size and the record's on opposite sides of the line a reader actually sees — no bigger
than a man (Medium and below) against bigger than a man (Large and up) — or two steps or
more apart on the same side. One step on the same side is prose, not an error: an ogre
(Large) called "towering" and read as Huge is not wrong, and neither is a Small goblin
read as Tiny. A person is never asked: a person's body is their people's and their face's
(rules/faces.py), and "a towering man" is fair prose about a tall human.

Measured 2026-10-27 on gemma-4-12B (the owner's model), two asks each, on 24 labelled
passages (written for the probe; none copied from a save): the owner's three
oversized beats, a "huge" grioth, a wolf "the size of a horse" and an ogre "no taller than
your waist" caught 12 of 12; seventeen true or unsized ones — a towering ogre, a massive
owlbear, a looming giant, a dragon blotting out the sky, a lean wolf, a goblin at your
belt, a rat no bigger than a cat, a man-sized grioth, a "tall and gaunt" grioth, a wolf
"level with your hip", four grioths given no size — flagged 0 of 34. One false positive
stands, 2 of 2: a Medium gnoll "a head taller than you" read as Large (a gnoll is a person
and never asked; a Medium monster written a head taller than the player would be).

The repair is the house's: one targeted rewrite of those sentences with the record named.
No backstop cut: the sentence that misnames a size usually carries the act ("You step
toward the massive creature"), and a cut would lose a true move to save an adjective.

With the reader off or unread (the suite, a failed call) this member finds nothing.
"""
from __future__ import annotations

import re

from gm.narration import Finding

ORDER = 13
KINDS = frozenset({"creature-size"})
DOORS = frozenset({"plan", "turn", "npc", "outcome"})

# How many creatures one beat asks about. A beat with more than this is a fight with a
# crowd, and the first few carry the defect.
MAX_ASKS = 2
NOT_SAID = "not said"

# Answered questions, (sentences key, name) -> the size said. `_repair_sentences` asks
# `find` again after the rewrite; an unchanged passage must not cost the question twice.
_ASKED: dict[tuple, str] = {}


def _sizes() -> tuple[str, ...]:
    from rules.tables import SIZE_ORDER

    return tuple(SIZE_ORDER)


# Each size as the reader is asked it: beside a man, and the words prose uses for it. The
# words are for the model to read by, never for code to match. Probed 2026-10-27 (gemma-4-
# 12B, two asks each): glossed only by height, "its towering form" was "not said" 2 of 2.
_GLOSS = {
    "fine": "no bigger than a hand",
    "diminutive": "about the size of a rat",
    "tiny": "about the size of a cat",
    "small": "about half a man's height; small, child-sized",
    "medium": "about a man's height, up to a head taller or shorter; man-sized",
    "large": "half again a man's height or more; large, towering, massive, hulking",
    "huge": "several times a man's height; huge, enormous, giant",
    "gargantuan": "as tall as a house",
    "colossal": "as tall as a tower or more",
}


def question(name: str, words=()) -> str:
    called = [w for w in dict.fromkeys(" ".join(str(w).split()) for w in words or ())
              if w and w.lower() != name.lower()]
    also = (f" (the sentences may call it {', '.join(repr(w) for w in called[:4])})"
            if called else "")
    glossed = "; ".join(f'"{s}" — {_GLOSS[s]}' for s in _sizes())
    return (f"How big do these sentences say {name}{also} is, beside a grown man? Answer "
            f"with the size their own words give it: {glossed}. Answer \"{NOT_SAID}\" when "
            f"the words give no size — when they only say it is frightening, strange, "
            f"still, solid or watchful.")


def contradicts(said: str, record: str) -> bool:
    """Whether the page's size is wrong for the record (the module note's rule): across
    the line between a man's size and bigger, either way; or two steps apart at a man's
    size or below. Above a man every size is "bigger than a man" to a reader: probed, "the
    dragon's enormous bulk blots out the sky" was read Colossal for a Huge dragon 2 of 2,
    and that is prose, not an error."""
    sizes = _sizes()
    if said not in sizes or record not in sizes:
        return False
    a, b = sizes.index(said), sizes.index(record)
    man = sizes.index("medium")
    if (a > man) != (b > man):
        return True
    return a <= man and b <= man and abs(a - b) >= 2


# What a creature is called in place of its own name when it is asked about (`unnamed`).
NEUTRAL = "the creature"


def unnamed(passage: str, name: str, words=(), names=()) -> tuple[str, str, tuple]:
    """The passage, the name asked about and the page's words for it, with the creature's
    OWN name taken out — its name on the record and its template's — so a size word that is
    part of what it is called is never read as a claim about its size.

    Measured on the owner's report of 2026-11-01 (Corvin T., the shrine): "the giant rot
    grub" is the Bestiary's name for a Small vermin, and the reader read "giant" as Huge
    on 15 beats of one fight; every repair then rewrote the name itself into "the small
    rot grub". The names are the engine's own strings, replaced literally (longest first,
    with any article in front), never words read for their meaning — and the question is
    asked of `NEUTRAL`, which the sentences now use for it."""
    forms = {" ".join(str(n).replace("-", " ").split()) for n in (name, *names)
             if str(n or "").strip()}
    bare = sorted({f[4:] if f.lower().startswith("the ") else f for f in forms}
                  - {"", "the", "a", "an"}, key=len, reverse=True)
    if not bare:
        return passage, name, tuple(words or ())
    pattern = re.compile(r"\b(?:(?:the|a|an)\s+)?(?:"
                         + "|".join(re.escape(b) for b in bare) + r")\b", re.I)
    if not pattern.search(passage) and not any(pattern.search(str(w)) for w in words or ()):
        return passage, name, tuple(words or ())
    # A page word that is only a piece of the name ("The giant", the mention finder's
    # chunk of "The giant rot grub") is the name too, and goes with it.
    def piece(w: str) -> bool:
        core = re.sub(r"^(?:the|a|an)\s+", "", " ".join(w.split()), flags=re.I).lower()
        return bool(core) and any(re.search(r"\b" + re.escape(core) + r"\b", b.lower())
                                  for b in bare)

    kept = tuple(w for w in (pattern.sub(NEUTRAL, str(w)) for w in words or ())
                 if w.strip().lower() != NEUTRAL and not piece(w))
    return pattern.sub(NEUTRAL, passage), NEUTRAL, kept


def ask(passage: str, name: str, words=(), *, chat=None, model: str = "", host: str = "",
        provider: str = "ollama", api_key: str = "", names=()) -> str | None:
    """The one closed question. None when the call fails: unanswered, nothing judged.
    `words`: the page's own words for it (the beat reader's mentions), so "the towering
    figure" is known to be it — probed without them, a passage in the owner's beat's shape,
    calling the grioth only "the towering figure" and "the massive creature", was "not
    said" 2 of 2 for "the grioth"."""
    from gm import beat_verify

    passage, name, words = unnamed(passage, name, words, names)
    msgs = [{"role": "system", "content": (
        "You answer one question about a few sentences of a story, from those sentences "
        "alone.")},
        {"role": "user", "content": f"The sentences: {passage}\n\nQuestion: "
                                    f"{question(name, words)}"}]
    return beat_verify._one_of(msgs, [NOT_SAID, *_sizes()], chat=chat, model=model,
                               host=host, provider=provider, api_key=api_key)


def creatures(ctx) -> list[tuple[str, str, str, list[str], list[str]]]:
    """(ref, name, record size, the page sentences mentioning it, the page's words for it)
    for every creature that is no person the beat reader found on the page — here, or gone
    in this batch."""
    from gm import beat_reader, mentions
    from rules import bestiary

    from ._page import page_sentences

    reading = ctx.attribution
    if not isinstance(reading, beat_reader.Reading) or not reading.read:
        return []
    scene = ctx.scene
    actors = getattr(scene, "actors", {}) or {}
    gone = {g["ref"]: g for g in (scene.gone_in(ctx.outcomes or ())
                                  if hasattr(scene, "gone_in") else ())}
    page = page_sentences(ctx.text)
    keys = {mentions._key(w): w for w, _n in page}
    out: dict[str, tuple[str, str, str, list[str]]] = {}
    for m in reading.mentions:
        ref = m.ref
        if not ref or ref == "pc":
            continue
        if ref in actors:
            if getattr(actors[ref], "is_pc", False):
                continue
            size, name = bestiary.body_size(actors[ref]), str(actors[ref].name)
        elif ref in gone:
            words = str(gone[ref].get("body") or "").split()
            size = words[0].lower() if words else ""
            name = str(gone[ref].get("name") or "")
        else:
            continue
        sentence = keys.get(mentions._key(m.sentence))
        if not size or not sentence:
            continue
        row = out.setdefault(ref, (ref, name, size, [], []))
        if sentence not in row[3]:
            row[3].append(sentence)
        if m.phrase not in row[4]:
            row[4].append(m.phrase)
    return list(out.values())[:MAX_ASKS]


def _own_names(ctx, ref: str, name: str) -> tuple[str, ...]:
    """The creature's record names — what it is called and the template it was made from
    (`from_template`, "giant-rot-grub") — for `unnamed`."""
    scene = ctx.scene
    who = (getattr(scene, "people", {}) or {}).get(ref) \
        or (getattr(scene, "actors", {}) or {}).get(ref)
    names = [name]
    if who is not None:
        names += [str(getattr(who, "name", "") or ""),
                  str(getattr(who, "from_template", "") or "")]
    return tuple(n for n in names if n)


def find(ctx) -> list:
    from gm import beat_verify, narration

    route = dict(getattr(ctx, "reader", None) or {})
    if not beat_verify.ENABLED or not route.get("model"):
        return []
    out = []
    for ref, name, size, sentences, words in creatures(ctx):
        called = narration.definite(name)
        key = (" ".join(sentences), called)
        if key not in _ASKED:
            got = ask(" ".join(sentences), called, words, model=route.get("model", ""),
                      host=route.get("host", ""), provider=route.get("provider") or "ollama",
                      api_key=route.get("api_key", ""), names=_own_names(ctx, ref, name))
            if got is None:
                continue
            _ASKED[key] = got
        while len(_ASKED) > 256:
            _ASKED.pop(next(iter(_ASKED)))
        said = _ASKED[key]
        if not contradicts(said, size):
            continue
        from rules import bestiary

        beside = bestiary.SIZE_BESIDE_A_MAN.get(size, "")
        way = "bigger" if _sizes().index(said) > _sizes().index(size) else "smaller"
        out.append(Finding(
            "creature-size",
            f"{called} is {size.title()} by its record and the page makes it {said}: "
            f"{sentences[0][:90]!r}",
            f"{called[:1].upper()}{called[1:]} is {size.title()} — {beside}. Rewrite the "
            f"words that make it {way} so it is that size; keep its name, {called}, "
            f"exactly as it is, and change nothing else.",
            weight=2, sentences=tuple(sentences)))
    return out
