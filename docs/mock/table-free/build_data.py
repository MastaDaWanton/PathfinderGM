"""Regenerate data.js for the free table mock, from the engine, the fixtures and two recordings.

Run from the repository root:

    python docs/mock/table-free/build_data.py

Nothing in data.js is written by hand. It extends docs/mock/table-layout/build_data.py:

- exits: `play/exits.py exits()` on the Pangrella fixture at every place in Zhilvarnia at
  08:00, once plain and once with the PC wanted in the city;
- the story at the gate, its suggestions and people: the recorded session
  `tests/replay/2026-09-25-town-tags-retag-gemma4-12b.jsonl.gz`;
- the fight: `tests/replay/2026-09-25-fight-bodies-gemma4-12b.jsonl.gz`, its real grid,
  positions, initiative, rolls with their terms, tells and prose;
- both sheets: `rules.sheet.full_sheet()` and `summary()` for fixtures/pc-kesst.json and
  fixtures/pc-caster.json, with each manoeuvre's `provokes` from `rules.tables.MANEUVERS`
  and each weapon's range from `rules.tables.WEAPONS`;
- the counters: `rules.goods.goods_at()` for the smithy and the market, and the coin
  names `rules.goods.coinage()` coins for Zhilvarnia;
- the wizard's spells: `content/spells/spells.json`.

The player's own saves and corpora are never read.
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
from rules import geography, goods, places, residency, states  # noqa: E402
from rules.activeeffect import ActiveEffect  # noqa: E402
from rules.dice import Dice  # noqa: E402
from rules.engine import Engine, Scene  # noqa: E402
from rules.sheet import from_dict as sheet_from_dict  # noqa: E402
from rules.sheet import full_sheet, load_pc  # noqa: E402
from rules.tables import MANEUVERS, WEAPONS  # noqa: E402
from world.loader import load_cached  # noqa: E402

WORLD = "fixtures/pangrella-campaign.json"
CITY = "6953424c8a82"                       # Zhilvarnia
START = CITY + "~urban:the-gate"
PCS = {"kesst": "fixtures/pc-kesst.json", "ysolde": "fixtures/pc-caster.json"}
TOWN = "tests/replay/2026-09-25-town-tags-retag-gemma4-12b.jsonl.gz"
FIGHT = "tests/replay/2026-09-25-fight-bodies-gemma4-12b.jsonl.gz"
OUT = Path(__file__).resolve().parent / "data.js"
HOUR = 8 * 60

world = load_cached(WORLD)
city = world.get(CITY)


def party(wanted: bool):
    scene = Scene(location_id=city.id)
    pc = load_pc(PCS["kesst"])
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


# --- exits, as the first mock had them -----------------------------------------------------
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

# --- the gate: story, suggestions, people ----------------------------------------------------
rows = [json.loads(line) for line in gzip.open(ROOT / TOWN, "rt", encoding="utf-8")]
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
said.append({"who": "the guard", "line": "Hold. State your business before the crossing."})

# --- the fight ---------------------------------------------------------------------------------
frows = [json.loads(line) for line in gzip.open(ROOT / FIGHT, "rt", encoding="utf-8")]
fby = {r["turn"]: r for r in frows}
# The save before turn 4 is the moment the second fight is joined: Borin Lyraxys has won
# initiative, the first man is down and dying at the bar, and it is round one.
fsave = fby[4]["save_before"]
fscene = fsave["scene"]
fight_people = {}
for ref, p in fscene["people"].items():
    face = p.get("appearance") or ""
    if ". " in face:
        face = face.split(". ", 1)[1]
    row = {"name": p.get("name"), "hp": p.get("hp"), "hp_max": p.get("hp_max"), "face": face}
    if ref != "pc":
        # Their real numbers, read back through the sheet the engine itself uses, so the
        # mock's enemy turn rolls against what the engine would have rolled against.
        npc = sheet_from_dict(p, ref)
        nf = full_sheet(npc)
        att = nf["offense"]["attacks"][:1]
        row.update({"ac": nf["defense"]["ac"]["total"],
                    "attack": ({"name": att[0]["name"], "bonus": att[0]["attack"]["total"],
                                "dice": att[0]["damage_dice"],
                                "dmg": att[0]["damage"]["total"]} if att else None)})
    fight_people[ref] = row
fight_rolls, fight_tells = [], []
for e in fby[3]["added_turn_log"]:
    if e.get("kind") != "resolution":
        continue
    for o in e["outcomes"]:
        if o.get("tell"):
            fight_tells.append(o["tell"])
        for rl in o.get("rolls", []):
            fight_rolls.append({"label": rl["label"], "die": rl["die"], "faces": rl["faces"],
                                "natural": rl.get("natural"), "terms": rl["modifiers"],
                                "total": rl["total"]})
        fight_dc = o.get("dc")
fight = {
    "grid": fscene["grid"],
    "positions": fscene["positions"],
    "initiative": fscene["initiative"],
    "round": fscene["round"],
    "people": fight_people,
    "opening": fby[1]["player"],
    "struck": fby[2]["player"],
    "prose": [b["text"] for b in fby[3]["added_transcript"] if b["who"] == "gm"],
    "rolls": fight_rolls,
    "dc": fight_dc,
    "tells": fight_tells,
    "suggestions": fsave.get("suggestions") or [],
}

# --- the two characters --------------------------------------------------------------------
def trim_terms(block):
    return {"total": block["total"], "terms": block["terms"]} if block else None


sheets = {}
for key, path in PCS.items():
    pc = load_pc(path)
    s, full = pc.summary(), full_sheet(pc)
    feats = {f.lower() for f in s.get("feats", [])}
    attacks = []
    for a in full["offense"]["attacks"]:
        w = WEAPONS.get(a["key"], {})
        attacks.append({**{k: a[k] for k in ("key", "name", "equipped", "category", "hands",
                                             "damage_dice", "crit", "type", "sequence")},
                        "attack": trim_terms(a["attack"]), "damage": trim_terms(a["damage"]),
                        "range_ft": w.get("range_ft") or 0})
    maneuvers = []
    for m in full["offense"]["maneuvers"]:
        improved = "improved " + m["name"] in feats
        maneuvers.append({"name": m["name"], "cmb": trim_terms(m["cmb"]), "effect": m["effect"],
                          "provokes": bool(MANEUVERS.get(m["name"], {}).get("provokes"))
                          and not improved})
    d = full["defense"]
    sheets[key] = {
        "identity": full["identity"],
        "class_features": full.get("class_features", []),
        "traits": full.get("traits", []),
        "abilities": full["abilities"],
        "hp": {k: d["hp"][k] for k in ("current", "max", "temp", "nonlethal")},
        "hp_terms": d["hp"]["max_terms"]["terms"],
        "speed": d["speed"]["current"],
        "ac": trim_terms(d["ac"]), "touch": trim_terms(d["ac_touch"]),
        "flat": trim_terms(d["ac_flat_footed"]),
        "saves": d["saves"], "cmd": trim_terms(d["cmd"]),
        "cmd_flat": trim_terms(d["cmd_flat_footed"]),
        "bab": full["offense"]["bab"], "init": trim_terms(full["offense"]["initiative"]),
        "cmb": trim_terms(full["offense"]["cmb"]),
        "attacks": attacks, "maneuvers": maneuvers,
        "skills": [{k: sk[k] for k in ("name", "ability", "rank", "class_skill", "total",
                                       "trained_only", "terms")} for sk in full["skills"]],
        "feats": s.get("feats", []), "xp": s["xp"], "needs": s["needs"],
        "pools": s.get("pools", []), "conditions": s.get("conditions", []),
    }

# --- counters and coin -------------------------------------------------------------------------
def shelf(g) -> list:
    return [[x.id, x.name, x.price_gp, x.tier, x.per, x.unit, x.kind] for x in g]


counters = {
    "smithy": shelf(goods.goods_at("smithy")),
    "market": shelf(goods.goods_at("market")),
    "tavern": shelf(goods.goods_at("tavern")),
    "weapons": shelf([g for g in goods.table_goods("weapons")
                      if g.key in ("dagger", "short sword", "rapier", "light crossbow", "sling",
                                   "club", "handaxe", "shortbow", "sap", "whip")]),
}
coins = [[c.id, c.name, c.copper, c.coined] for c in goods.coinage(world, city)]

# --- the wizard's book ---------------------------------------------------------------------------
BOOK_IDS = ["acid-splash", "arcane-mark", "bleed", "dancing-lights", "daze", "detect-magic",
            "detect-poison", "disrupt-undead", "flare", "ghost-sound", "light", "mage-hand",
            "mending", "message", "open-close", "prestidigitation", "ray-of-frost",
            "read-magic", "resistance", "touch-of-fatigue", "burning-hands", "magic-missile",
            "color-spray", "sleep", "mage-armor", "shield"]
codex = {sp["id"]: sp for sp in json.load(open(ROOT / "content/spells/spells.json",
                                               encoding="utf-8"))["spells"]}
spells = {}
for sid in BOOK_IDS:
    sp = codex.get(sid)
    if not sp:
        continue
    spells[sid] = {k: sp.get(k, "") for k in ("name", "school", "casting_time", "range",
                                              "area", "effect", "targets", "duration",
                                              "saving_throw", "spell_resistance",
                                              "components", "description")}
    spells[sid]["level"] = sp["lists"].get("wizard", sp["lists"].get("sorcerer/wizard", 0))

data = {
    "source": {
        "world": WORLD + " (Zhilvarnia, a real World Bible export)",
        "exits": "play/exits.py exits() at every place, 08:00, plain and wanted",
        "transcript": TOWN,
        "fight": FIGHT + ", the save before turn 4 and the rolls of turn 3",
        "sheets": "rules.sheet.full_sheet() and summary() on both fixtures",
        "counters": "rules.goods.goods_at() for smithy, market, tavern; table_goods('weapons')",
        "spells": "content/spells/spells.json",
    },
    "start": START,
    "day_part": residency.day_part(HOUR),
    # The engine's own words for every hour, so the mock's clock says what the app says.
    "day_parts": [residency.day_part(h * 60) for h in range(24)],
    "reasons": reasons,
    "places": place_rows,
    "transcript": transcript,
    "suggestions": at_gate["suggestions"],
    "people": {START: people},
    "said": said,
    "fight": fight,
    "sheets": sheets,
    "counters": counters,
    "coins": coins,
    "spells": spells,
}
with open(OUT, "w", encoding="utf-8") as f:
    f.write("// Generated for the free table mock from real engine output and real recordings.\n")
    f.write("// Regenerate with docs/mock/table-free/build_data.py; do not edit by hand.\n")
    f.write("window.MOCK_DATA = ")
    json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
    f.write(";\n")
print(f"wrote {OUT.name}: {len(place_rows)} places, {len(reasons)} reasons, "
      f"{len(transcript)} beats, {len(fight_rolls)} fight rolls, {len(spells)} spells, "
      f"{sum(len(v) for v in counters.values())} goods")
