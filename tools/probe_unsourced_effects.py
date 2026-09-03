"""Stage 8's acceptance probe: a number with nothing behind it must not reach the sheet.

Measured twice on 2026-09-02 (docs/stage-7-plan.md): asked to drink a potion the satchel
did not hold, the model emitted `heal` with `amount: "1d8+1"` and the engine applied it.
This drives the same sentence against the real model, three times, in a throwaway
campaign directory, and reports every intent and outcome off the turn log. It passes
when no heal/damage/buff/temp_hp outcome carries effects and hit points do not move.

Never the user's %LOCALAPPDATA%\\PathfinderGM: `PATHFINDER_GM_DATA` is pointed at a
temp dir BEFORE the app is imported, the pattern tools/adversary.py uses.

    python tools/probe_unsourced_effects.py [--times 3]
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ["PATHFINDER_GM_DATA"] = tempfile.mkdtemp(prefix="pfgm-unsourced-")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "pathfindergm.settings")

import django  # noqa: E402

django.setup()

from django.test import Client, override_settings  # noqa: E402

from play import campaign as cm  # noqa: E402
from rules.sheet import load_pc  # noqa: E402

EFFECT_OPS = {"heal", "damage", "buff", "temp_hp", "defence", "ability_damage",
              "item_damage"}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--times", type=int, default=3)
    ap.add_argument("--say", default="I drink my healing potion")
    # The inverse: the same sentence with a real jar in the satchel. Passes when the
    # heal that lands carries `origin: item:<id>` on its record, the jar is spent, and
    # no bare-number op reached the engine.
    ap.add_argument("--with-jar", action="store_true")
    args = ap.parse_args()

    faults: list[str] = []
    tmp = Path(tempfile.mkdtemp(prefix="unsourced-"))
    with override_settings(CAMPAIGN_DIR=tmp / "campaigns"):
        for n in range(1, args.times + 1):
            cm._LIVE.clear()
            c = cm.begin_with(load_pc("fixtures/pc-kesst.json"))
            pc = c.scene.pc()
            pc.hp = max(1, pc.hp_max - 4)             # room to heal, so a heal would show
            assert not pc.stock, "the probe needs an empty satchel"
            jar = ""
            if args.with_jar:
                from rules.crafting import Stock
                jar = "healing-draught#1"
                pc.stock[jar] = Stock(base="Healing Draught", count=1,
                                      specs=[{"type": "heal", "dice": "1d8+1"}])
            c.save()
            hp_before = pc.hp
            r = Client().post("/api/say", data=json.dumps({"text": args.say}),
                              content_type="application/json")
            c = cm.current()
            pc = c.scene.pc()
            hp_after = pc.hp
            turns = [x for x in c.turn_log if x.get("kind") == "turn"]
            last = turns[-1] if turns else {}
            landed = [o for o in last.get("outcomes", [])
                      if o.get("op") in EFFECT_OPS and o.get("effects")]
            print("=" * 72)
            print(f"RUN {n}: {args.say!r} -> {r.status_code} | hp {hp_before} -> {hp_after}")
            for i in last.get("intents", []):
                print("   INTENT", i.get("op"), i.get("params"))
            for o in last.get("outcomes", []):
                if o.get("tell"):
                    print("   TELL  ", o["tell"][:160])
                for e in o.get("effects", []):
                    if e.get("kind") in ("heal", "damage") or e.get("origin"):
                        print("   EFFECT", e.get("kind"), "origin=", e.get("origin"))
            if r.status_code != 200:
                faults.append(f"run {n}: HTTP {r.status_code}")
            if any(i.get("op") in EFFECT_OPS for i in last.get("intents", [])):
                faults.append(f"run {n}: a bare-number op reached the engine: "
                              f"{[i.get('op') for i in last.get('intents', [])]}")
            if not args.with_jar:
                if landed:
                    faults.append(f"run {n}: an unsourced effect landed: "
                                  f"{[(o['op'], o.get('effects')) for o in landed]}")
                if hp_after != hp_before:
                    faults.append(f"run {n}: hit points moved {hp_before} -> {hp_after}")
            else:
                heals = [e for o in last.get("outcomes", []) for e in o.get("effects", [])
                         if e.get("kind") == "heal"]
                if not heals:
                    faults.append(f"run {n}: the jar was named and no heal landed")
                elif any(e.get("origin") != f"item:{jar}" for e in heals):
                    faults.append(f"run {n}: a heal landed without the jar as origin: "
                                  f"{[e.get('origin') for e in heals]}")
                if jar in pc.stock:
                    faults.append(f"run {n}: the jar was not spent")
        cm._LIVE.clear()
    print()
    if faults:
        print(f"{len(faults)} FAULT(S)")
        for f in faults:
            print(" -", f)
        return 1
    print("ALL CLEAN: no unsourced number reached the sheet")
    return 0


if __name__ == "__main__":
    sys.exit(main())
