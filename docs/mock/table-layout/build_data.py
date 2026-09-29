"""Regenerate data.js for the table layout mock, from the engine and a recording.

Run from the repository root:

    python docs/mock/table-layout/build_data.py

Nothing in data.js is written by hand. The exits are `play/exits.py exits()` run against
the Pangrella fixture at every place in Zhilvarnia at 08:00, once plain and once with the
PC wanted in the city (which is what greys the ways past the watch). The story, the
suggestions and the people at the gate come from a recorded session against the same
fixture world, `tests/replay/2026-09-25-town-tags-retag-gemma4-12b.jsonl.gz`, which is in
the repository; the player's own corpora are not used (they stay off the public repo).
"""
from __future__ import annotations

import gzip
import json
import os
import sys
from pathlib import Path

ROOT = Path.cwd()
sys.path.insert(0, str(ROOT))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "pathfindergm.settings")

import django  # noqa: E402

django.setup()

from play import exits as exits_mod  # noqa: E402
from rules import geography, places, residency, states  # noqa: E402
from rules.activeeffect import ActiveEffect  # noqa: E402
from rules.dice import Dice  # noqa: E402
from rules.engine import Engine, Scene  # noqa: E402
from rules.sheet import load_pc  # noqa: E402
from world.loader import load_cached  # noqa: E402

WORLD = "fixtures/pangrella-campaign.json"
CITY = "6953424c8a82"                       # Zhilvarnia
START = CITY + "~urban:the-gate"
PC = "fixtures/pc-kesst.json"
REC = "tests/replay/2026-09-25-town-tags-retag-gemma4-12b.jsonl.gz"
OUT = Path(__file__).resolve().parent / "data.js"
HOUR = 8 * 60

world = load_cached(WORLD)
city = world.get(CITY)


def party(wanted: bool):
    scene = Scene(location_id=city.id)
    pc = load_pc(PC)
    scene.add(pc)
    scene.clock_minutes = HOUR
    engine = Engine(scene, Dice(seed=3), world=world)
    engine.place_party("")
    if wanted:
        tag = states.wanted_tag(city.id)
        pc.apply_effect(ActiveEffect(name="wanted", kind="situation", key=f"mock:{tag}",
                                     source="mock", origin="mock",
                                     duration="until-dismissed", tags=(tag,)))
    return scene, engine


# Blocked sentences once each, the PC's name made a slot so a second character reads them.
reasons: list[str] = []


def reason_index(text: str) -> int:
    if not text:
        return -1
    text = text.replace("Kesst Vayr", "{pc}")
    if text not in reasons:
        reasons.append(text)
    return reasons.index(text)


GROUP = {"next_door": "n", "outside": "o", "road": "r"}
place_rows: dict[str, dict] = {}
for wanted in (False, True):
    scene, engine = party(wanted)
    for p in engine.places():
        engine.place_party(p.id)
        row = place_rows.setdefault(p.id, {"name": p.name, "setting": places.setting_of(p.id)})
        row["wanted" if wanted else "exits"] = [
            [x["id"], x["name"], GROUP[x["group"]], x["time_words"],
             reason_index(x["blocked"]), 1 if x["journey"] else 0]
            for x in exits_mod.exits(engine, world)]
        if not wanted:
            where = geography.where(world, scene, engine.here())
            row["where"], row["ground"] = where.label, where.detail

rows = [json.loads(line) for line in gzip.open(ROOT / REC, "rt", encoding="utf-8")]
by_turn = {r["turn"]: r for r in rows[:10]}
transcript = [{"who": b["who"], "text": b["text"], "kind": b.get("kind", "")}
              for n in (4, 5) for b in by_turn[n]["added_transcript"]]
at_gate = by_turn[6]["save_before"]
people = []
for ref in ("c9", "c10"):
    a = at_gate["scene"]["people"][ref]
    face = a.get("appearance") or ""
    # Every face in this recording opens with the people's one shared body sentence; the
    # owner ruled that repetition a defect (NPC faces are individual), so the mock shows
    # the person's own part, everything after that first sentence.
    if ". " in face:
        face = face.split(". ", 1)[1]
    people.append({"ref": ref, "name": a["name"], "face": face})
said = [{"who": "the smith", "line": s["line"]}
        for b in by_turn[4]["added_transcript"] for s in b.get("said") or []]
# The guard's line went untagged in the recording; these are the guard's own quoted words.
said.append({"who": "the guard", "line": "Hold. State your business before the crossing."})

data = {
    "source": {
        "world": WORLD + " (Zhilvarnia, a real World Bible export)",
        "exits": "play/exits.py exits() at every place, 08:00, plain and wanted",
        "transcript": REC + ", the turns 'I ask the smith about the ore he uses.' and "
                      "'I leave the shop and walk out towards the gate.'",
        "suggestions_and_people": "the same recording, the save made at the gate after them",
    },
    "start": START,
    "day_part": residency.day_part(HOUR),
    "reasons": reasons,
    "places": place_rows,
    "transcript": transcript,
    "suggestions": at_gate["suggestions"],
    "people": {START: people},
    "said": said,
}
with open(OUT, "w", encoding="utf-8") as f:
    f.write("// Generated for the layout mock from real engine output and a real recording.\n")
    f.write("// Regenerate with docs/mock/table-layout/build_data.py; do not edit by hand.\n")
    f.write("window.MOCK_DATA = ")
    json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
    f.write(";\n")
print(f"wrote {OUT.name}: {len(place_rows)} places, {len(reasons)} reasons, "
      f"{len(transcript)} beats")
