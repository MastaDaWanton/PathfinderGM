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
            c.save()
            hp_before = pc.hp
            r = Client().post("/api/say", data=json.dumps({"text": args.say}),
                              content_type="application/json")
            c = cm.current()
            hp_after = c.scene.pc().hp
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
            if r.status_code != 200:
                faults.append(f"run {n}: HTTP {r.status_code}")
            if landed:
                faults.append(f"run {n}: an unsourced effect landed: "
                              f"{[(o['op'], o.get('effects')) for o in landed]}")
            if hp_after != hp_before:
                faults.append(f"run {n}: hit points moved {hp_before} -> {hp_after}")
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
