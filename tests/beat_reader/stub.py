"""A stub for the beat reader's two calls, for tests that need a reading without a model.

The reader is off in the suite (tests/conftest.py), as the interpreter and the mention
labeller are: most turn tests script the model's replies in order, and a reading call
would spend one. A test that pins what follows FROM a reading — a newcomer made, a line
booked, a place heard of — builds the reading with this stub instead, which answers the
"people" call and the "places" call with the replies the test wrote, exactly as the
model's JSON would arrive. The schema is still built and the answers still checked by
`beat_reader.read`, so a stubbed answer the engine would refuse is refused.

Answers are written by the page's words, not by mention ids, so a test reads as the beat:

    reading = stub.read(text, scene,
                        who={"a figure": "new", "the barkeep": "c3"},
                        new=[("a figure", "here", "woman")],
                        lines={"Not today": ("c3", "you")},
                        names={"c3": "Gorm"}, pronouns={"c3": "he"},
                        places=[("q1", "the smithy", "smithy", "the counting house")],
                        placed=[("q2", "the girl in the market", "the market")])

and the helpers `people_stage`/`beat_stage` run the aftermath members over it.
"""
from __future__ import annotations

import json
from types import SimpleNamespace

from gm import beat_reader, mentions, speech
from gm.client import Reply


def chat(people: dict | None = None, places: dict | None = None, *, fail: str = "",
         calls: list | None = None):
    """A `client.chat` stand-in: `people` for the people call, `places` for the places
    call (told apart by the schema's top-level keys). `fail` raises for that call
    ("people" | "places"), as a dead Ollama would. `calls` collects (kind, schema,
    messages) for a test that looks at the question asked."""
    def _chat(messages, model, host, *, schema=None, **_kw):
        props = set((schema or {}).get("properties") or {})
        kind = "places" if props == {"places", "people"} else "people"
        if calls is not None:
            calls.append((kind, schema, messages))
        if fail == kind:
            raise ConnectionError(f"stubbed: the {kind} call failed")
        answer = (places if kind == "places" else people) or {}
        if kind == "places":
            answer = {"places": [], "people": [], **answer}
        return Reply(text=json.dumps(answer), seconds=0.0, model="stub")
    return _chat


def _mention_ids(text: str, scene) -> dict[str, list[str]]:
    """phrase (lower-case) -> the mention ids `mentions.find` gives it, in order."""
    cast = mentions.people(scene) + beat_reader.away_people(scene)
    out: dict[str, list[str]] = {}
    for m in mentions.find(text, cast):
        out.setdefault(m.phrase.lower(), []).append(m.id)
    return out


def _line_ids(text: str) -> dict[str, str]:
    return {ln.words: ln.id for ln in beat_reader.lines_of(text)}


def people_answer(text: str, scene, *, who: dict | None = None, new=(), lines=None,
                  names: dict | None = None, pronouns: dict | None = None,
                  arrived=()) -> dict:
    """The people call's JSON from the page's words. `who`: phrase ("the man#2" for the
    second) -> a ref, "new", "nobody", or "same as <phrase>". `new`: (phrase, "here" |
    "elsewhere", the page's words). `lines`: the first words of a line -> (by, to), each a
    ref, "you", "nobody" or a phrase. Every mention and line not given is "nobody"."""
    ids = _mention_ids(text, scene)

    def mid(phrase: str) -> str:
        p, _, n = phrase.partition("#")
        got = ids.get(p.lower())
        if not got:
            raise KeyError(f"the finder marks no {p!r}: it marks {sorted(ids)}")
        return got[int(n or 1) - 1]

    def person(x: str) -> str:
        if x in ("you", "nobody") or x.startswith("c") and x[1:].isdigit() or x == "pc":
            return x
        return mid(x)

    ans: dict = {m: "nobody" for ms in ids.values() for m in ms}
    for phrase, a in (who or {}).items():
        ans[mid(phrase)] = ("same as " + mid(a[len("same as "):])
                            if a.startswith("same as ") else a)
    for words, lid in _line_ids(text).items():
        ans[lid] = {"by": "nobody", "to": "nobody"}
        flat = " ".join(words.split()).lower()
        for prefix, (by, to) in (lines or {}).items():
            if flat.startswith(prefix.lower()):
                ans[lid] = {"by": person(by), "to": person(to)}
        if ans[lid]["by"] == "nobody":
            # A line the beat's quote marks ran into another (Bobby's turn 2): by the
            # words it holds.
            for prefix, (by, to) in (lines or {}).items():
                if prefix.lower() in flat:
                    ans[lid] = {"by": person(by), "to": person(to)}
                    break
    if ids:
        ans["new"] = [{"mention": mid(p), "where": w, "words": words} for p, w, words in new]
    ans["names"] = [{"who": person(w), "name": n} for w, n in (names or {}).items()]
    if arrived:
        ans["arrived"] = list(arrived)
    for ref, p in (pronouns or {}).items():
        ans[f"pronoun {ref}"] = p
    return ans


def places_answer(text: str, *, places=(), placed=()) -> dict:
    """The places call's JSON. `places`: (line prefix, words, kind, near[, same as]);
    `placed`: (line prefix, words, at)."""
    lines = _line_ids(text)

    def lid(prefix: str) -> str:
        """The line opening with these words; else the one holding them (a beat whose
        quote marks run two lines into one, as Bobby's turn 2 does)."""
        norm = {w: " ".join(w.split()).lower() for w in lines}
        return next((i for w, i in lines.items() if norm[w].startswith(prefix.lower())),
                    None) or next(i for w, i in lines.items() if prefix.lower() in norm[w])

    return {"places": [{"line": lid(p[0]), "words": p[1], "kind": p[2], "near": p[3],
                        "same as": p[4] if len(p) > 4 else beat_reader.FIRST}
                       for p in places],
            "people": [{"line": lid(p[0]), "words": p[1], "at": p[2]} for p in placed]}


def read(text: str, scene, *, engine=None, said=(), who=None, new=(), lines=None,
         names=None, pronouns=None, arrived=(), places=(), placed=(), fail: str = "",
         calls: list | None = None) -> beat_reader.Reading:
    people = people_answer(text, scene, who=who, new=new, lines=lines, names=names,
                           pronouns=pronouns, arrived=arrived)
    where = places_answer(text, places=places, placed=placed) if (places or placed) else {}
    return beat_reader.read(text, scene, engine=engine, said=said,
                            chat=chat(people, where, fail=fail, calls=calls))


def ctx(scene, reading, *, text: str, engine=None, world=None, said=None, turn: int = 0,
        stage: str = "people", door: str = "turn", player_text: str = "",
        campaign=None):
    """The `AfterBeat` fields the beat reader's members read, without a campaign."""
    from play import aftermath

    camp = campaign or SimpleNamespace(engine=lambda: engine, transcript=[])
    return SimpleNamespace(
        stage=stage, door=door, campaign=camp, scene=scene, world=world, text=text,
        said=said if said is not None else [], player_text=player_text, attachments=(),
        reading=None, attribution=reading, outcomes=(), people=aftermath.people_of(scene),
        talking_after=(), beat_index=None, turn=turn)


def people_stage(scene, reading, *, text: str, engine=None, world=None, said=None,
                 turn: int = 0) -> list[dict]:
    """`seen_people` then `speaker_real`, as the "people" stage runs them."""
    from play.aftermath import seen_people, speaker_real

    c = ctx(scene, reading, text=text, engine=engine, world=world, said=said, turn=turn)
    return seen_people.step(c) + speaker_real.step(c)


def lines_said(text: str) -> list[str]:
    return [ln for ln in speech.lines(text) if ln.strip()]
