"""Regenerate data.js for the table layout mock, from the engine and a recording.

Run from the repository root:

    python docs/mock/table-layout/build_data.py

Nothing in data.js is written by hand. Where each part comes from:

- The exits are `play/exits.py exits()` run against the Pangrella fixture at every place
  in Zhilvarnia at 08:00, once plain and once with the PC wanted in the city (which is what
  greys the ways past the watch).
- The story, the suggestions, the people at the gate, what they said, and the ground the
  map draws come from a recorded session against the same fixture world,
  `tests/replay/2026-09-25-town-tags-retag-gemma4-12b.jsonl.gz`, which is in the
  repository. The save made at the gate is loaded with the app's own `Campaign.load` and
  handed to `play/views.py _state`, the function behind `/api/state`, so the map's grid and
  tokens are exactly what the page is sent. The player's own corpora are not used (they
  stay off the public repo).
- The two characters are `fixtures/pc-kesst.json` and `fixtures/pc-caster.json`, loaded
  with `rules.sheet.load_pc`. Every number on the sheet is `rules.sheet.full_sheet` (the
  function behind `/api/sheet`) or `Actor.summary()` (the side panel's), and every swing of
  every attack is `Actor.attack_modifiers` at that iteration.
- The carried basket beyond the fixture's own weapons and armour is an example outfitter
  basket, marked `from: "example"` item by item. Each thing in it is still filed and
  described by the engine: `rules.goods.kind_of` and the server's shelf rules for its
  category, `goods.describe` for its line, the weapons table for a weapon's numbers and
  weight, and a scratch copy of the character wearing it for what it would do to AC and
  saves.
"""
from __future__ import annotations

import gzip
import itertools
import json
import os
import re
import sys
import tempfile
from pathlib import Path

ROOT = Path.cwd()
sys.path.insert(0, str(ROOT))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "pathfindergm.settings")

import django  # noqa: E402

django.setup()

from play import campaign as campaign_mod  # noqa: E402
from play import exits as exits_mod  # noqa: E402
from play import views  # noqa: E402
from rules import casting, geography, goods, magicitem, places, residency, states  # noqa: E402
from rules import weapons as weapons_mod  # noqa: E402
from rules.activeeffect import ActiveEffect  # noqa: E402
from rules.creation import DEFAULT_OUTFIT, OUTFITS  # noqa: E402
from rules.dice import Dice  # noqa: E402
from rules.engine import Engine, Scene  # noqa: E402
from rules.sheet import SAVES, body_slots, full_sheet, load_pc  # noqa: E402
from rules.tables import ARMOUR, MANEUVERS, SHIELDS  # noqa: E402
from world.loader import load_cached  # noqa: E402

WORLD = "fixtures/pangrella-campaign.json"
CITY = "6953424c8a82"                       # Zhilvarnia
START = CITY + "~urban:the-gate"
PCS = {"kesst": "fixtures/pc-kesst.json", "ysolde": "fixtures/pc-caster.json"}
REC = "tests/replay/2026-09-25-town-tags-retag-gemma4-12b.jsonl.gz"
OUT = Path(__file__).resolve().parent / "data.js"
HOUR = 8 * 60
# The recording's turns shown as the story: asking the smith about his ore, walking out to
# the gate, and asking the gate guard what lies north. The scene is the save made after
# them, still at the gate, which is where the suggestions and the map come from.
STORY_TURNS = (4, 5, 6)
SCENE_ROW = 7

world = load_cached(WORLD)
city = world.get(CITY)


# --- Exits -------------------------------------------------------------------------------

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


# --- The recording: story, suggestions, people, what was said, the ground ---------------

rows = [json.loads(line) for line in gzip.open(ROOT / REC, "rt", encoding="utf-8")]
by_turn = {r["turn"]: r for r in rows}
transcript = [{"who": b["who"], "text": b["text"], "kind": b.get("kind", "")}
              for n in STORY_TURNS for b in by_turn[n]["added_transcript"]]
at_gate = by_turn[SCENE_ROW]["save_before"]

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

# The conversation tray's log, in the shape `scene.conversation.recent` has
# (play/aftermath/conversation_log.py): numbered entries, who spoke, to whom, on which
# beat. The recording predates that log, so it is rebuilt here from the `said` lines each
# GM beat carried, which are the same quoted words the log keeps (owner Q43/Q44: speech
# only, never the player's reported actions). Every line is verbatim, including the
# recording's own damaged apostrophes.
names = {r: p["name"] for r, p in at_gate["scene"]["people"].items()}
convo, n = [], 0
for turn in range(0, max(STORY_TURNS) + 1):
    clock = by_turn[turn]["save_before"]["scene"].get("clock_minutes", 0)
    for b in by_turn[turn]["added_transcript"]:
        for s in b.get("said") or []:
            n += 1
            convo.append({"n": n, "t": clock, "beat": turn, "who": s["who"],
                          "name": names.get(s["who"], s["who"]), "to": s.get("to", "you"),
                          "kind": "line", "text": s["line"]})
here = {p["ref"] for p in people}
spoke = list(dict.fromkeys(e["who"] for e in convo))
convo_people = ([{"ref": r, "name": names[r], "present": True,
                  "talking": r == convo[-1]["who"]} for r in ("c9", "c10")]
                + [{"ref": r, "name": names[r], "present": False, "talking": False}
                   for r in spoke if r not in here])

with tempfile.TemporaryDirectory() as d:
    saved = Path(d) / "gate.json"
    saved.write_text(json.dumps(at_gate), encoding="utf-8")
    camp = campaign_mod.Campaign.load(saved)
    state = views._state(camp)
ground = {"grid": state["scene"]["grid"],
          "actors": [{k: a[k] for k in ("ref", "name", "hp", "hp_max", "is_pc", "side",
                                        "squares", "at")} for a in state["scene"]["actors"]],
          "in_encounter": state["scene"]["in_encounter"]}


# --- The characters ----------------------------------------------------------------------

def total(mods) -> int:
    return sum(m.value for m in mods)


def terms(mods) -> list:
    return [[m.source, m.value] for m in mods if m.value]


def attack_row(pc, key: str) -> dict:
    """One weapon's attack, every number from the engine.

    `swings` is each attack of a full attack at its own bonus, asked of
    `attack_modifiers` at that iteration rather than worked out here as BAB-5 steps, so a
    stat-block creature or a class that changes the sequence would come out right too.
    """
    w = weapons_mod.get(key)
    seq = pc.attack_sequence(key, full_attack=True)
    dmg = pc.damage_modifiers(key)
    dmg_total = total(dmg)
    return {
        "key": key, "name": w["name"],
        "category": w["category"], "hands": w.get("hands", 1), "light": bool(w.get("light")),
        "proficient": pc.is_proficient(key),
        "swings": [total(pc.attack_modifiers(key, iteration=i)) for i in seq],
        "attack_terms": terms(pc.attack_modifiers(key)),
        "damage": pc.damage_dice(key) + (f"{dmg_total:+d}" if dmg_total else ""),
        "damage_terms": terms(dmg),
        "crit": (f"{w['crit_range']}-20" if w["crit_range"] < 20 else "20")
                + f"/x{w['crit_mult']}",
        "type": w.get("type_text") or w.get("type", ""),
        "range_ft": w.get("range_ft"),
        "traits": list(w.get("traits") or []),
        "finessable": bool(w.get("finessable")),
        "weight_lb": w.get("weight_lb"),
    }


# What each character carries beyond the fixture. The fixture's own weapons and armour, and
# the outfit rules/creation.py grants at first level, are real; everything tagged here is an
# example outfitter basket, sized past forty things so the list's categories get tested.
# The names are the engine's own where it has one (goods.GEAR, the weapons table, the
# magic-item catalogue), so the engine files and describes them as it would in play.
BASKETS = {
    "kesst": [
        ("sap", 1), ("light crossbow", 1), ("crossbow bolts", 20), ("shortbow", 1),
        ("arrows", 20),
        ("studded leather", 1), ("buckler", 1),
        ("Cloak of Resistance +1", 1), ("Ring of Protection +1", 1),
        ("backpack", 1), ("bedroll", 1), ("blanket", 1), ("silk rope", 50), ("torch", 5),
        ("lantern", 1), ("waterskin", 1), ("flint and steel", 1), ("healer's kit", 1),
        ("grappling hook", 1), ("crowbar", 1), ("chalk", 10), ("sack", 2), ("whetstone", 1),
        ("hammer", 1), ("pitons", 10), ("mirror", 1), ("thieves' tools", 1), ("manacles", 1),
        ("candle", 6), ("ink and paper", 1), ("signal whistle", 1), ("caltrops", 2),
        ("climber's kit", 1), ("cold-weather outfit", 1), ("sunrod", 2),
        ("alchemist's fire", 2),
        ("rations", 5), ("bread", 2), ("cheese", 1), ("oil", 3), ("antitoxin", 1),
        ("potion of cure light wounds", 2),
        ("garnet", 2), ("freshwater pearl", 1), ("silver brooch", 1), ("ivory figurine", 1),
    ],
    "ysolde": [
        ("light crossbow", 1), ("crossbow bolts", 10),
        ("Cloak of Resistance +1", 1),
        ("spellbook", 1), ("spell component pouch", 1), ("ink and paper", 2),
        ("backpack", 1), ("bedroll", 1), ("blanket", 1), ("waterskin", 1),
        ("flint and steel", 1), ("candle", 10), ("lantern", 1), ("sack", 1), ("mirror", 1),
        ("chalk", 4), ("signal whistle", 1),
        ("rations", 4), ("bread", 1), ("oil", 2), ("antitoxin", 1),
        ("potion of cure light wounds", 1),
        ("garnet", 1), ("silver brooch", 1),
    ],
}

def _plain(e) -> dict:
    return e if isinstance(e, dict) else dict(vars(e))


MAGIC = {str(m["name"]).lower(): m for m in map(_plain, magicitem.catalogue().values())
         if m.get("slot")}
_VALUABLE = views._VALUABLE
FOOD = {n for k, e in goods.GEAR.items() if e.get("category") in ("food", "provisions")
        for n in (k, str(e["name"]).lower())}
GEAR_BY_NAME = {str(e["name"]).lower(): e for e in goods.GEAR.values()}
GEAR_BY_NAME.update({k: e for k, e in goods.GEAR.items()})


def shelf_of(name: str) -> str:
    """The server's `_shelf_of` for a bought thing, asked of the same engine facts: a
    wondrous item from the catalogue is magic, `goods.kind_of` files weapons, armour and
    consumables, food by the gear list's own category, a valuable by the server's own
    regex, and everything else is gear."""
    low = name.lower()
    if low in MAGIC:
        return "magic"
    kind = goods.kind_of(name)
    if kind == "weapon":
        return "weapons"
    if kind in ("armour", "shield"):
        return "armour"
    if kind == "consumable" or low in FOOD:
        return "consumables"
    return "valuables" if _VALUABLE.search(name) else "gear"


def numbers(pc) -> dict:
    return {"ac": pc.ac(), "touch": pc.touch_ac(), "ff": pc.ac(flat_footed=True),
            "ac_terms": terms(pc.ac_modifiers("melee")),
            "saves": {k: total(pc.save_modifiers(k)) for k in SAVES},
            "save_terms": {k: terms(pc.save_modifiers(k)) for k in SAVES}}


def worn_effect(path: str, change) -> dict:
    """AC and saves on a scratch copy of the character wearing the thing: the engine's
    own answer to "what would this do", never a number written here."""
    pc = load_pc(path)
    change(pc)
    return numbers(pc)


def item_row(cid: str, path: str, pc, name: str, count: int, state: str, source: str,
             key: str = "") -> dict:
    """One carried thing. `key` is the engine's own key where the shown name is not it:
    the fixture's armour is "leather" to the tables and "leather armour" on the sheet, and
    `goods.kind_of("leather armour")` answers "gear" (so a `wear` op naming it by its
    sheet name would be refused; recorded in the README)."""
    low = name.lower()
    shelf = shelf_of(key or name)
    row = {"id": re.sub(r"[^a-z0-9]+", "-", low).strip("-"), "name": name, "count": count,
           "unit": goods.unit_for(name), "shelf": shelf, "state": state, "from": source,
           "line": goods.describe(name, count), "weight_lb": None, "cost_gp": None,
           "can": [], "refused": {}}
    kind = goods.kind_of(key or name)
    gear = GEAR_BY_NAME.get(low)
    if gear:
        row["cost_gp"] = gear.get("cost_gp")
    if kind == "weapon":
        row["kind"] = "weapon"
        row["attack"] = attack_row(pc, low)
        row["weight_lb"] = row["attack"]["weight_lb"]
        row["cost_gp"] = weapons_mod.get(low).get("cost_gp")
        row["can"] = ["wield", "drop"]
    elif kind in ("armour", "shield"):
        row["kind"] = kind
        table = ARMOUR if kind == "armour" else SHIELDS
        key = key or next(k for k, v in table.items() if k == low or v["name"] == low)
        e = table[key]
        row["key"] = key
        row["armour"] = {"ac": e["ac"], "acp": e["acp"], "max_dex": e.get("max_dex"),
                         "class": e.get("weight", "")}
        row["cost_gp"] = e.get("cost_gp")
        row["if_worn"] = worn_effect(path, lambda p, k=key, a=kind: setattr(
            p, "armour" if a == "armour" else "shield", k))
        row["can"] = ["wear", "take off", "drop"]
        # There is a `wear` op for armour and a shield (_op_wear) and nothing that takes
        # either off again: the engine can change what you wear, never leave you without.
        row["refused"]["take off"] = "armour"
    elif low in MAGIC:
        m = MAGIC[low]
        row["kind"] = "slot"
        row["slot"] = m["slot"]
        row["cost_gp"] = m.get("price_gp")
        row["text"] = m.get("text", "")
        row["if_worn"] = worn_effect(path, lambda p, s=m["slot"], nm=m["name"]:
                                     p.set_slot(s, 0, nm))
        row["can"] = ["wear", "take off", "drop"]
    elif shelf == "consumables":
        row["kind"] = "consumable"
        row["can"] = ["use", "drop"]
    elif low.endswith("outfit") or low.endswith("vestments"):
        # The free outfit fills the body slot (rules/creation.py OUTFITS); a spare one is
        # clothing like any other and can be put on there.
        row["kind"] = "slot"
        row["slot"] = "body"
        row["can"] = ["wear", "take off", "drop"]
    else:
        row["kind"] = "gear"
        row["can"] = ["drop"]
    return row


def character(cid: str, path: str) -> dict:
    pc = load_pc(path)
    if casting.is_caster(pc):
        casting.ensure_prepared(pc)
    s = full_sheet(pc)
    summ = pc.summary()
    o, d = s["offense"], s["defense"]
    ident = s["identity"]

    carried_weapons = list(dict.fromkeys(w.lower() for w in pc.weapons))
    basket = []
    for w in carried_weapons:
        basket.append(item_row(cid, path, pc, w, 1,
                               "hand" if w == (pc.equipped or "").lower() else "", "fixture"))
    if pc.armour != "none":
        basket.append(item_row(cid, path, pc, ARMOUR[pc.armour]["name"], 1, "worn", "fixture",
                               key=pc.armour))
    if pc.shield != "none":
        basket.append(item_row(cid, path, pc, SHIELDS[pc.shield]["name"], 1, "worn", "fixture",
                               key=pc.shield))
    outfit = OUTFITS.get(str(pc.class_data.get("name", "")).lower(), DEFAULT_OUTFIT)
    basket.append(item_row(cid, path, pc, outfit, 1, "worn", "creation"))
    for name, count in BASKETS[cid]:
        basket.append(item_row(cid, path, pc, name, count, "", "example"))

    # Every combination the Equipment page can reach, each asked of the engine on a scratch
    # copy: which armour (the `wear` op swaps it and nothing takes it off, so there is no
    # "none" once worn), whether the shield is on, and which slot items are worn. Summing
    # each item's own change in the browser would be the mock doing arithmetic the engine
    # owns (a second shield bonus does not stack, a deflection bonus does), so it does not.
    armours = [b["key"] for b in basket if b.get("kind") == "armour"]
    shields = ["none"] + [b["key"] for b in basket if b.get("kind") == "shield"]
    magic = [b for b in basket if b.get("kind") == "slot" and b.get("slot") != "body"]
    loadouts = {}
    for arm in armours or ["none"]:
        for sh in shields:
            for k in range(len(magic) + 1):
                for worn in itertools.combinations(magic, k):
                    def dress(p, arm=arm, sh=sh, worn=worn):
                        p.armour, p.shield = arm, sh
                        for b in worn:
                            p.set_slot(b["slot"], 0, b["name"])
                    names = ",".join(sorted(b["name"] for b in worn))
                    loadouts[f"{arm}|{sh}|{names}"] = worn_effect(path, dress)

    spells = s["spells"]
    if spells:
        spells = {
            "kind": spells["kind"], "ability": spells["ability"],
            "caster_level": spells["caster_level"], "note": spells.get("note", ""),
            "slots": [{k: sl[k] for k in ("level", "max", "left", "dc")}
                      for sl in spells["slots"]],
            "known": [{k: sp.get(k) for k in ("id", "name", "level", "school", "range",
                                              "duration", "save", "components", "prepared")}
                      for sp in spells["known"] if not sp.get("missing")],
        }

    bluff = next(k for k in s["skills"] if k["name"] == "bluff")
    return {
        "name": ident["name"],
        "class": ident["class"], "race": ident["race"], "heritage": ident["heritage"],
        "pronouns": ident["pronouns"], "size": ident["size"],
        "hp": d["hp"]["current"], "hp_max": d["hp"]["max"],
        "speed": d["speed"]["current"],
        "xp": summ["xp"],
        "abilities": [{k: a[k] for k in ("key", "name", "score", "modifier")}
                      for a in s["abilities"]],
        "ac": {"total": d["ac"]["total"], "terms": [[t["source"], t["value"]]
                                                   for t in d["ac"]["terms"] if t["value"]]},
        "touch": d["ac_touch"]["total"], "ff": d["ac_flat_footed"]["total"],
        "cmd": {"total": d["cmd"]["total"], "terms": [[t["source"], t["value"]]
                                                     for t in d["cmd"]["terms"] if t["value"]]},
        "cmd_ff": d["cmd_flat_footed"]["total"],
        "saves": [{"key": sv["key"], "name": sv["name"], "total": sv["total"],
                   "terms": [[t["source"], t["value"]] for t in sv["terms"] if t["value"]]}
                  for sv in d["saves"]],
        "init": {"total": o["initiative"]["total"],
                 "terms": [[t["source"], t["value"]] for t in o["initiative"]["terms"]
                           if t["value"]]},
        "bab": o["bab"],
        "cmb": {"total": o["cmb"]["total"], "terms": [[t["source"], t["value"]]
                                                     for t in o["cmb"]["terms"] if t["value"]]},
        "attacks": [attack_row(pc, a["key"]) for a in o["attacks"]],
        "equipped": (pc.equipped or "").lower(),
        "maneuvers": [{"name": m["name"], "cmb": m["cmb"]["total"], "effect": m["effect"],
                       "size_limit": m["size_limit"],
                       "provokes": bool(MANEUVERS[m["name"]].get("provokes")),
                       "two_hands": bool(MANEUVERS[m["name"]].get("needs_two_hands"))}
                      for m in o["maneuvers"]],
        # Feint is not a manoeuvre in the engine: "feint" is filed as a Bluff check
        # (rules/intents.py), and nothing makes the target lose its Dexterity to AC
        # (rules/classfeatures.py says so). So the sheet can show the Bluff it rolls and
        # nothing else.
        "feint_bluff": bluff["total"] if bluff["usable"] else None,
        "conditions": [c["name"] for c in d["conditions"]],
        "skills": [{"name": k["name"], "total": k["total"], "rank": k["rank"],
                    "class_skill": k["class_skill"], "usable": k["usable"]}
                   for k in s["skills"]],
        "feats": [{"name": f["name"], "effect": f["effect"]} for f in s["feats"]],
        "background": ({"name": s["background"]["past"]["name"],
                        "line": s["background"]["past"]["line"]}
                       if s["background"]["past"] else None),
        "notes": s["background"]["notes"],
        "armour": s["equipment"]["armour"], "shield": s["equipment"]["shield"],
        "acp": s["equipment"]["armour_check_penalty"],
        "slots": body_slots(pc),
        "spells": spells,
        "numbers": numbers(pc),
        "loadouts": loadouts,
        "basket": basket,
    }


chars = {cid: character(cid, path) for cid, path in PCS.items()}

data = {
    "source": {
        "world": WORLD + " (Zhilvarnia, a real World Bible export)",
        "exits": "play/exits.py exits() at every place, 08:00, plain and wanted",
        "transcript": REC + ", turns " + ", ".join(
            repr(by_turn[t]["player"]) for t in STORY_TURNS),
        "scene": "the same recording, the save made at the gate after them, loaded with "
                 "Campaign.load and read through play/views.py _state",
        "characters": "rules.sheet.full_sheet and Actor.summary for " + ", ".join(PCS.values()),
    },
    "start": START,
    "day_part": residency.day_part(HOUR),
    "reasons": reasons,
    "places": place_rows,
    "transcript": transcript,
    "suggestions": at_gate["suggestions"],
    "people": {START: people},
    "conversation": {"people": convo_people, "recent": convo},
    "ground": ground,
    "chars": chars,
}
with open(OUT, "w", encoding="utf-8") as f:
    f.write("// Generated for the layout mock from real engine output and a real recording.\n")
    f.write("// Regenerate with docs/mock/table-layout/build_data.py; do not edit by hand.\n")
    f.write("window.MOCK_DATA = ")
    json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
    f.write(";\n")
print(f"wrote {OUT.name}: {len(place_rows)} places, {len(reasons)} reasons, "
      f"{len(transcript)} beats, {len(convo)} lines said, "
      + ", ".join(f"{c['name']} {len(c['basket'])} things" for c in chars.values()))
