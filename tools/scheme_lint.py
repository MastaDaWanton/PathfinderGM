"""Lint every quest scheme: the validator, and then the authoring rules it does not hold.

`rules.schemes.validate` refuses what a document must never say — a criterion in
prose, a digit in a reward, an action outside the vocabulary. It does not know what
a *line* of schemes promises across its steps, and those promises are where "A Small
Favour" went wrong in draft: a twist whose foreshadowing no earlier step or open
granted (the engine would skip it forever and log why, and the murder would never be
answered for); a slot declared and filled from the world's cast that no tell ever
names (a person pulled onto the board for nothing); an outcome no step fires; a card
opened that nothing touches; a `since(step)` on a step id that does not exist (the
criterion is false forever, silently); a scheme that opens on a tag nothing in the
set grants (a line that can never start).

Every problem is printed with the fix named, the classbuilder's style, and the exit
code is one when there are any — so it can gate a commit.

    python tools/scheme_lint.py                 # content/schemes and homebrew/schemes
    python tools/scheme_lint.py path/to/a.json  # one file
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "pathfindergm.settings")

import django  # noqa: E402

django.setup()

from rules import schemes  # noqa: E402

_SINCE_STEP = re.compile(r"^since\(([\w-]+)\)")
_HAS_PC = re.compile(r"^(?:not\s+)?has\(pc,\s*([a-z0-9.\-_]+)\)$")


def _actions(step: dict) -> list[dict]:
    return [a for a in [step.get("action")] + list(step.get("also") or []) if isinstance(a, dict)]


def _granted_by(doc: dict, upto: int | None = None) -> set[str]:
    """Tags the pc could hold from this scheme: the open, the steps before `upto`
    (all of them when None), the outcomes, and the `knows.news.<step>` a news item
    grants on arrival."""
    tags: set[str] = set()
    for g in doc.get("grants_on_open") or []:
        if str(g.get("to", "pc")) == "pc":
            tags.update(str(t) for t in g.get("tags") or [])
    for i, st in enumerate(doc.get("steps") or []):
        if upto is not None and i >= upto:
            break
        for a in _actions(st):
            if a.get("do") == "grant" and str(a.get("to", "pc")) == "pc":
                tags.update(str(t) for t in a.get("tags") or [])
            if a.get("do") == "news":
                slug = re.sub(r"[^a-z0-9]+", "-", str(st.get("id")).lower()).strip("-")[:32]
                tags.add(f"knows.news.{slug}")
    if upto is None:
        for out in (doc.get("outcomes") or {}).values():
            for g in (out or {}).get("grants") or []:
                if str(g.get("to", "pc")) == "pc":
                    tags.update(str(t) for t in g.get("tags") or [])
    return tags


def _supplies(tags: set[str], want: str) -> bool:
    from rules import states
    return any(states.matches(t, want) for t in tags)


def lint_set(docs: dict[str, dict]) -> list[str]:
    """Problems across a set of schemes, each with the fix named."""
    problems: list[str] = []
    everything = {sid: _granted_by(d) for sid, d in docs.items()}
    for sid, doc in docs.items():
        at = f"{sid}"
        for p in schemes.validate(doc):
            problems.append(f"{at}: {p}")
        steps = doc.get("steps") or []
        ids = {st.get("id") for st in steps if isinstance(st, dict)}
        # Fairness: every tag a twist names must be granted before it could fire — by
        # this scheme's open, by an earlier step of this scheme, or by another scheme in
        # the set (the line before this one). Otherwise the engine skips the twist every
        # tick and logs "foreshadowing not on the brief", and nothing ever fires.
        for i, st in enumerate(steps):
            if not isinstance(st, dict):
                continue
            here = _granted_by(doc, upto=i)
            elsewhere = set().union(*(v for k, v in everything.items() if k != sid)) if len(docs) > 1 else set()
            for tag in st.get("fairness") or []:
                if _supplies(here, str(tag)):
                    continue
                if _supplies(elsewhere, str(tag)):
                    continue
                problems.append(
                    f"{at}: steps[{i + 1}] ({st.get('id')}) needs {tag!r} for fairness but nothing "
                    f"grants it earlier — add it to grants_on_open or to a grant on a step "
                    f"authored before this one.")
            # since(<step>) names a step of this scheme, or the criterion is false forever.
            for c in st.get("criteria") or []:
                m = _SINCE_STEP.match(" ".join(str(c).split()))
                if m and m.group(1) not in ("open", "campaign") and m.group(1) not in ids:
                    problems.append(
                        f"{at}: steps[{i + 1}] ({st.get('id')}) waits on since({m.group(1)}), "
                        f"which is not a step of this scheme; name one of {', '.join(sorted(str(x) for x in ids))}.")
        # Every slot is named in at least one tell: a slot is a person, place or thing
        # pulled from the world and frozen on the instance, and one no tell ever names
        # is a body on the board for nothing.
        tells = " ".join(str(v) for st in steps if isinstance(st, dict)
                         for v in (st.get("tell") or {}).values())
        named = set(re.findall(r"\$(\w+)", tells))
        for slot in doc.get("slots") or {}:
            if slot not in named:
                problems.append(f"{at}: slot ${slot} is filled from the world but no tell names it — "
                                f"name it in a tell, or drop the slot.")
        # Every outcome is fired by some step; every card is touched by some step or
        # resolved by some outcome.
        fired = {a.get("name") for st in steps if isinstance(st, dict)
                 for a in _actions(st) if a.get("do") == "outcome"}
        for name in doc.get("outcomes") or {}:
            if name not in fired:
                problems.append(f"{at}: outcome {name!r} is declared but no step fires it — add "
                                f"{{\"do\": \"outcome\", \"name\": \"{name}\"}} to a step, or drop it.")
        # A secret card is touched by the engine itself: every fired tell lands on it.
        used = {a.get("card") for st in steps if isinstance(st, dict) for a in _actions(st) if a.get("card")}
        used |= {out.get("resolve") for out in (doc.get("outcomes") or {}).values() if isinstance(out, dict)}
        for card in doc.get("cards") or []:
            if isinstance(card, dict) and card.get("key") not in used and not card.get("secret"):
                problems.append(f"{at}: card {card.get('key')!r} is opened but no step or outcome touches "
                                f"it — add a fact, objective or resolve on it, or drop the card.")
        # A scheme that opens on a pc tag nothing in the set grants can never start.
        for c in doc.get("opens") or []:
            m = _HAS_PC.match(" ".join(str(c).split()))
            if m and not str(c).startswith("not") and not any(
                    _supplies(v, m.group(1)) for k, v in everything.items() if k != sid):
                problems.append(f"{at}: opens on has(pc, {m.group(1)}) but no other scheme grants "
                                f"{m.group(1)!r} — grant it from an outcome or a step of the scheme before this one.")
    return problems


def lint_file(path: Path) -> list[str]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as ex:
        return [f"{path}: not JSON — {ex}"]
    entries = data.get("schemes") if isinstance(data, dict) and "schemes" in data else [data]
    docs = {str(e.get("id")): e for e in entries or [] if isinstance(e, dict) and e.get("id")}
    if not docs:
        return [f"{path}: no scheme with an id in it."]
    return [f"{path.name}: {p}" for p in lint_set(docs)]


def main(argv: list[str]) -> int:
    paths = [Path(a) for a in argv[1:]]
    if not paths:
        folders = [schemes._content_dir(), schemes.homebrew_dir()]
        paths = [p for f in folders if f.exists() for p in sorted(f.glob("*.json"))]
    problems: list[str] = []
    for p in paths:
        problems.extend(lint_file(p))
    if problems:
        for p in problems:
            print(p)
        print(f"\n{len(problems)} problem(s).")
        return 1
    print(f"{len(paths)} file(s), no problems.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
