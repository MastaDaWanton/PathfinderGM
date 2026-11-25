"""What a creature looks like, the first time it is seen.

The owner's list for playtest 2026-11-23, O1: "enemies appear but are often not described;
people don't know what things look like unless they are described." The ramidreju, the
clockwork spy, the two chickens and the poltergeist all came on to the page as names and
nothing else ("you can barely make out two chickens"). A person met gets a face
(`names.appearance_for`, rules/faces.py, and the face backstop in `play/views._finish`);
a creature with no people got nothing, because that backstop skips an empty appearance.

**Code supplies the facts, the model writes the prose, code validates it.** The facts are
the creature's own record (`facts`): its size beside a grown man and its kind
(`bestiary.body_said`), its subtype, the natural weapons it attacks with, the ways it moves
besides walking. The model writes one or two sentences of what a person would see (one
schema call, `write`). Code then holds it (`fault`): no number, no deed (a look is how it
is, not what it does to anyone), no size that goes against the record — the size read by
the house's own closed question (`checks.creature_size.ask` / `contradicts`). One rewrite
with the fault named; still wrong, a plain line made from the facts (`plain`) stands in.

Prior art: CircleMUD gives every mobile a long description shown in the room listing when
it is first there, and a detailed description for "look at" (building.txt, §mobiles);
Inform 7 gives a thing an "initial appearance" for first sight (WI 3.11). The Alexandrian's
monster formula — a visible sign of what it can do, one physical trait — is the shape of
the facts list. docs/research/2026-11-25-people-and-arrivals.md.

The look is written once per kind of creature in a campaign (`KEY`): the second chicken is
the first chicken's kind, and its look is already on the page.
"""
from __future__ import annotations

import re

KEY = "look:"
MAX_CHARS = 300

# A natural weapon's name in a stat block's melee line: "bite +2 (1d3-4)", "2 claws +5
# (1d4+2)", "slam +4 (1d6)". The words before the bonus, without a count.
_WEAPON = re.compile(r"(?:^|,|\band\b|\bor\b)\s*(?:\d+\s+)?([a-z][a-z ]{1,24}?)\s*[+−–-]\d",
                     re.I)
_MOVES = {"fly": "it flies", "swim": "it swims", "climb": "it climbs",
          "burrow": "it burrows"}
# A deed in the look: the second person (it does something to "you") or a number.
_YOU = re.compile(r"\b(?:you|your|yours|yourself)\b", re.I)
_DIGIT = re.compile(r"\d")


def facts(actor) -> list[str]:
    """The creature's look as its record gives it, each a short line; [] for a person or a
    creature with no record."""
    from rules import bestiary

    doc = actor._creature_doc() if hasattr(actor, "_creature_doc") else None
    if not doc or bestiary.has_a_people(actor):
        return []
    out = []
    body = bestiary.body_said(bestiary.body_words(actor))
    if body:
        out.append(f"what it is: {body}")
    sub = " ".join(str(doc.get("subtype") or "").replace(",", " ").split())
    if sub:
        out.append(f"of its kind: {sub}")
    weapons = list(dict.fromkeys(m.group(1).strip().lower()
                                 for m in _WEAPON.finditer(str(doc.get("melee") or ""))))
    weapons = [w for w in weapons if w not in ("melee", "touch")]
    if weapons:
        out.append("it fights with: " + ", ".join(weapons[:4]))
    moves = [_MOVES[m] for m in bestiary.speeds(doc) if m in _MOVES]
    if moves:
        out.append("how it moves: " + ", ".join(moves))
    return out


def messages(name: str, lines: list[str], redo: str = "") -> list[dict]:
    told = "\n".join(f"- {x}" for x in lines)
    ask = (f"Describe how {name} looks to someone who sees it for the first time, in one "
           "or two short sentences: its shape, its skin, hide, feathers or what stands for "
           "them, its colour, how it holds itself. The engine's record of it (nothing you "
           f"write may go against it):\n{told}\nWrite only what is seen. No numbers, and "
           "nothing it is doing to anybody: no attack, no step toward anyone.")
    msgs = [{"role": "system", "content": "You write short, concrete descriptions of "
                                          "creatures for a fantasy story."},
            {"role": "user", "content": ask}]
    if redo:
        msgs.append({"role": "user", "content": redo})
    return msgs


def _sentences(text: str) -> list[str]:
    return [s for s in re.split(r"(?<=[.!?])\s+", " ".join(str(text or "").split())) if s]


def fault(text: str, actor, *, size_said=None) -> str:
    """What is wrong with a look as written, or "". `size_said(text, name)` is the closed
    size question (`checks.creature_size.ask`), None to leave the size unjudged."""
    from rules import bestiary

    from .checks import creature_size

    if not str(text or "").strip():
        return "It is empty."
    if _DIGIT.search(text):
        return "It has a number in it."
    if _YOU.search(text):
        return "It has the creature doing something to the onlooker; say only how it looks."
    record = bestiary.body_size(actor)
    if size_said is not None and record:
        said = size_said(text, str(actor.name or ""))
        if said and creature_size.contradicts(said, record):
            return (f"It makes {actor.name} {said}, and it is {record}: "
                    f"{bestiary.SIZE_BESIDE_A_MAN.get(record, '')}.")
    return ""


def plain(actor, lines: list[str]) -> str:
    """The look made from the facts alone, when the model's will not stand."""
    from . import narration

    name = narration.definite(str(actor.name or "it"))
    name = name[:1].upper() + name[1:]
    what = next((x.split(": ", 1)[1] for x in lines if x.startswith("what it is: ")), "")
    if not what:
        return ""
    rest = [x.split(": ", 1)[1] for x in lines if x.startswith(("it fights with: ",))]
    arms = rest[0].split(", ") if rest else []
    tail = (", armed with " + (", ".join(arms[:-1]) + " and " + arms[-1] if len(arms) > 1
                               else arms[0])) if arms else ""
    return f"{name} is {what}{tail}."


def write(actor, *, chat, model: str, host: str, provider: str = "ollama",
          api_key: str = "", size_said=None) -> tuple[str, list[str]]:
    """(the look, notes). "" when the creature has no record to describe it from."""
    lines = facts(actor)
    if not lines:
        return "", []
    name = str(actor.name or "the creature")
    notes: list[str] = []
    redo = ""
    for attempt in range(2):
        try:
            reply = chat(messages(name, lines, redo), model, host, as_json=True, think=False,
                         temperature=0.7, num_predict=220, provider=provider,
                         api_key=api_key,
                         schema={"type": "object", "properties": {"look": {
                             "type": "string", "maxLength": MAX_CHARS}},
                             "required": ["look"]})
            text = " ".join(str((reply.json() or {}).get("look") or "").split())
        except Exception:  # noqa: BLE001 — a model down costs the prose, never the look
            text = ""
        text = " ".join(_sentences(text)[:2])
        wrong = fault(text, actor, size_said=size_said)
        if not wrong:
            if attempt:
                notes.append(f"{name}'s look: asked again, fixed")
            return text, notes
        notes.append(f"{name}'s look: {wrong}")
        redo = f"You wrote: {text!r}. {wrong} Write it again."
    line = plain(actor, lines)
    notes.append(f"{name}'s look: written from the record")
    return line, notes


def held(scene, actor) -> str:
    """This creature's kind's look, already written in this campaign, or ""."""
    said = getattr(scene, "said", None)
    key = KEY + str(getattr(actor, "from_template", "") or "").lower()
    return str(said.get(key) or "") if isinstance(said, dict) else ""


def keep(scene, actor, text: str) -> None:
    said = getattr(scene, "said", None)
    if isinstance(said, dict) and text:
        said[KEY + str(getattr(actor, "from_template", "") or "").lower()] = text


def sentence(actor, look: str) -> str:
    """The look as it stands on the page: as written when it opens on the creature itself
    ("The chicken is…", "It…"), else after its name ("You see the chicken: a plump…"), the
    form a face takes (`narration.a_face_for`)."""
    from . import narration

    look = " ".join(str(look or "").split())
    if not look:
        return ""
    name = narration.definite(str(actor.name or ""))
    if look.lower().startswith((name.lower(), "it ", "its ")):
        return look[:1].upper() + look[1:]
    return narration.a_face_for(str(actor.name or ""), look)
