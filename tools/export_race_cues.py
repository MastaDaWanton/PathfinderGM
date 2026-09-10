"""Write the race-cue vocabulary out for World Bible, from the table itself.

World Bible has to know which words in a race card actually do something on this side.
That list lives in `rules/races.py:CUES` as regular expressions, which is the right shape
for matching and the wrong shape for a person writing prose to read.

So this generates both: `docs/race-cues.json` for a program, and the options table inside
`docs/race-options.md` for a person. Generated rather than transcribed for the reason
CLAUDE.md gives — a hand-copied rule goes stale in the copy nobody looks at — and the
`_SAYS` map below is asserted complete against `CUES`, so adding a cue without describing
it fails here rather than shipping a list with a hole in it.

    python tools/export_race_cues.py

Run it after any change to `CUES`, `SIZES`, `SPEEDS`, `_SMALL`, `_LARGE`, `_FAST` or
`_SLOW`, and commit what it writes.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "pathfindergm.settings")
try:
    import django

    django.setup()
except Exception:                                    # the table needs no settings
    pass

from rules import races                              # noqa: E402

# The words a person should actually write, per cue, keyed by the first tag it grants.
# Not parsed out of the regex on purpose: several cues are two-part proximity matches
# ("sight" within forty characters of "dark") and a flat word list would misrepresent
# them. Completeness is asserted below instead.
_SAYS: dict[str, dict[str, str]] = {
    "move.fly.30": {
        "write": "wings, winged, fly, flight, glide, soar, airborne",
        "example": "They have broad wings and fly between the canopy platforms.",
    },
    "sense.blindsense.30": {
        "write": "echolocation (any ending), blindsense, sonar",
        "example": "They hunt by echolocation, and the dark costs them nothing.",
    },
    "sense.darkvision.60": {
        "write": "one of see / sight / vision / eyes WITHIN FORTY CHARACTERS of one of "
                 "dark / darkness / night / lightless / pitch — or the single words "
                 "darkvision / nightvision",
        "example": "They see in pitch darkness as well as in daylight.",
    },
    "sense.low-light": {
        "write": "dim light, low light, low-light, twilight, dusk",
        "example": "They see clearly by dusk light and hunt in the last of it.",
    },
    "sense.scent": {
        "write": "one of scent / smell / olfactory / nose WITHIN FORTY CHARACTERS of one "
                 "of keen / sharp / track / hunt / acute / strong — or the phrases "
                 "\"track by scent\" / \"hunt by smell\"",
        "example": "They track by scent over open ground.",
    },
    "amphibious": {
        "write": "gills, amphibious, aquatic, \"breathe water\", \"breathes underwater\"",
        "example": "Gills at the throat let them breathe underwater.",
        "note": "grants TWO tags: amphibious and a swim speed",
    },
    "move.climb.20": {
        "write": "climb (any ending), arboreal, tree-dwelling",
        "example": "They climb sheer trunks without rope.",
    },
    "move.burrow.20": {
        "write": "burrow, tunnel, dig (any ending)",
        "example": "They dig through packed earth to move between chambers.",
    },
    "natural.claws": {
        "write": "talon, talons, claw, claws, clawed",
        "example": "Each hand ends in heavy claws.",
    },
    "natural.bite": {
        "write": "fang, fangs, bite, tusk, tusks, mandibles, beak",
        "example": "A hooked beak, strong enough to break bone.",
    },
    "natural.armor.1": {
        "write": "carapace, chitin (any ending), scale, scales, scaled, hide, armour, "
                 "armored, plated, shell",
        "example": "Overlapping scales cover the back and shoulders.",
    },
    "weakness.light-sensitivity": {
        "write": "one of light / sun / sunlight / daylight WITHIN FORTY CHARACTERS of one "
                 "of pain / blind / burn / dazzle / hurt / weak (any ending)",
        "example": "Direct sunlight dazzles them within moments.",
    },
}


def rows() -> list[dict]:
    out = []
    for pattern, granted, line, waits in races.CUES:
        key = granted[0]
        said = _SAYS.get(key)
        if said is None:
            raise SystemExit(
                f"tools/export_race_cues.py: no plain-words entry for the cue granting "
                f"{key!r}. Add one to _SAYS — World Bible reads this list to know what "
                f"to write, and a cue missing from it is a trait nobody can trigger.")
        out.append({
            "grants": list(granted),
            "shows": line,
            "write": said["write"],
            "example": said["example"],
            "note": said.get("note", ""),
            "engine_ready": not waits,
            "waits_on": waits,
            "pattern": pattern,
        })
    return out


def main() -> None:
    data = {
        "_about": "The complete vocabulary a World Bible race card can trigger in "
                  "Pathfinder GM. Generated by tools/export_race_cues.py from "
                  "rules/races.py — do not edit by hand.",
        "sizes": list(races.SIZES),
        "size_words": {
            "small": "small, short, slight, diminutive, half the height, child-sized, "
                     "waist-high, knee-high, halfling-sized",
            "large": "towering, giant, huge, massive, twice the height, ten feet, "
                     "nine feet, eight feet — RECOGNISED BUT NOT GRANTED: the Race "
                     "Builder allows Large for giants only, so the sheet stays medium "
                     "and a not_yet line is written",
        },
        "speeds": {"slow": 20, "normal": 30, "fast": 40},
        "speed_words": {
            "fast": "swift, fast, quick, fleet, sprint, outrun, rapid",
            "slow": "slow, lumbering, plodding, ponderous, waddling",
        },
        "cues": rows(),
        "cue_count": len(races.CUES),
        "engine_ready_count": sum(1 for r in rows() if r["engine_ready"]),
    }
    out = ROOT / "docs" / "race-cues.json"
    out.write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n",
                   encoding="utf-8")
    md = ROOT / "docs" / "race-options.md"
    md.write_text(markdown(data), encoding="utf-8")
    print(f"wrote {out.relative_to(ROOT)} and {md.relative_to(ROOT)}: "
          f"{data['cue_count']} cues, {data['engine_ready_count']} engine-ready")


def markdown(data: dict) -> str:
    """The same table for a person to read while writing a race card."""
    L = ["# Every option a race card has",
         "",
         "**Generated from `rules/races.py` by `tools/export_race_cues.py`. Do not edit "
         "by hand — regenerate it.**",
         "",
         "This is the complete list. A race card in a World Bible export can produce "
         f"**a size, a speed, and up to {data['cue_count']} traits** — the ones below — "
         "and nothing else. There is no other channel: any sentence whose words match "
         "none of these rows is read by the consumer, matched against every pattern, "
         "and discarded.",
         "",
         f"**{data['engine_ready_count']} of the {data['cue_count']} do something in "
         "play today.** The rest are recorded on the sheet and shown to the player, and "
         "the engine cannot act on them yet — it has no walls to climb, no water to "
         "swim, no air to fly through, and it rolls the weapon in hand rather than a "
         "claw. Write them anyway; they are true about the people and they will start "
         "working without the card changing.",
         "",
         "## Size",
         "",
         f"One of: {', '.join('`' + s + '`' for s in data['sizes'])}. Send the word in "
         "the `size` field.",
         "",
         "The prose is also read, and overrides nothing — it only fills the gap when "
         "`size` is missing:",
         "",
         f"- **small** — {data['size_words']['small']}",
         f"- **large** — {data['size_words']['large']}",
         "",
         "## Speed",
         "",
         "One of `slow`, `normal`, `fast` in the `speed` field — which become 20, 30 and "
         "40 feet. Never write the number.",
         "",
         f"- **fast** — {data['speed_words']['fast']}",
         f"- **slow** — {data['speed_words']['slow']}",
         "",
         "## The traits, and the words that trigger them",
         "",
         "Every one of these is matched over `body[]`, `senses[]` and `movement[]` "
         "**joined together**. Which field a word sits in makes no difference to what "
         "fires — put it in the field a reader would expect, because the fields are for "
         "the human, not the matcher.",
         ""]
    for c in data["cues"]:
        mark = "works in play" if c["engine_ready"] else "**not yet: " + c["waits_on"] + "**"
        L += [f"### {c['shows']}",
              "",
              f"- *Write one of:* {c['write']}",
              f"- *Grants:* {', '.join('`' + t + '`' for t in c['grants'])}",
              f"- *Status:* {mark}"]
        if c["note"]:
            L.append(f"- *Note:* {c['note']}")
        L += ["", f"> {c['example']}", ""]
    L += ["## What a card cannot say",
          "",
          "Worth knowing before you try. None of these can be expressed in the card "
          "format as it stands, and no wording will reach them:",
          "",
          "- **Ability score modifiers.** Every world race is given the standard "
          "+2 physical / +2 mental / -2 any, chosen by the player. This is the single "
          "most defining mechanical feature of a Pathfinder race and the card has no "
          "channel for it.",
          "- **Skill bonuses**, save bonuses, and any conditional modifier "
          "(\"+4 against poison\", \"+2 on checks made underground\").",
          "- **Creature type.** Every world race is `humanoid`.",
          "- **Bonus feats or extra skill ranks.**",
          "- **Languages** beyond the people's own.",
          "- **Anything Large.** The Race Builder allows Large for giants only, so a "
          "towering people is recorded as medium with a note.",
          ""]
    return "\n".join(L) + "\n"


if __name__ == "__main__":
    main()
