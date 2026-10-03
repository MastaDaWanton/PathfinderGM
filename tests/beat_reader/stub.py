"""A stub for the beat reader's two calls, for tests that need a reading without a model.

The reader is off in the suite (tests/conftest.py), as the interpreter and the mention
labeller are: most turn tests script the model's replies in order, and a reading call
would spend one. A test that pins what follows FROM a reading — a newcomer made, a line
booked, a place heard of — builds the reading with this stub instead, which answers the
"people" call and the "places" call with the replies the test wrote, exactly as the
model's JSON would arrive. The schema is still built and still checked by
`beat_reader.read`, so a stubbed answer outside the engine's vocabulary is refused the way
a model's would be.

    reading = stub.read(text, scene, people={"m1": "new", ...}, places={...})
"""
from __future__ import annotations

import json

from gm import beat_reader
from gm.client import Reply


def chat(people: dict | None = None, places: dict | None = None, *, fail: str = "",
         calls: list | None = None):
    """A `client.chat` stand-in: the people answer for the people call, the places answer
    for the places call (told apart by the schema's own top-level keys). `fail` raises
    for that call ("people" | "places"), as a dead Ollama would. `calls` collects the
    (kind, schema, messages) of each call made, for a test that looks at the question."""
    def _chat(messages, model, host, *, schema=None, **_kw):
        kind = "places" if set((schema or {}).get("properties") or {}) == {"places",
                                                                            "people"} \
            else "people"
        if calls is not None:
            calls.append((kind, schema, messages))
        if fail == kind:
            raise ConnectionError(f"stubbed: the {kind} call failed")
        answer = (places if kind == "places" else people) or {}
        if kind == "places":
            answer = {"places": [], "people": [], **answer}
        return Reply(text=json.dumps(answer), seconds=0.0, model="stub")
    return _chat


def read(text: str, scene, *, people: dict | None = None, places: dict | None = None,
         engine=None, said=(), fail: str = "", calls: list | None = None
         ) -> beat_reader.Reading:
    return beat_reader.read(text, scene, engine=engine, said=said,
                            chat=chat(people, places, fail=fail, calls=calls))
