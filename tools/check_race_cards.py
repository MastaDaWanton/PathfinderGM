"""Check a World Bible export's `play.races[]` against what Pathfinder GM can read.

Standalone on purpose. It imports nothing from Pathfinder GM and nothing from World
Bible — only the standard library and `race-cues.json`, which is generated from
`rules/races.py`. Copy this file and that one into the World Bible repo and it runs
there:

    python check_race_cards.py <world>-campaign.json
    python check_race_cards.py <world>-campaign.json --cues race-cues.json

It reports, per race, exactly which traits Pathfinder GM would build from the card, and
every way the card wastes its own words. It cannot tell you whether a race is *good* —
it can tell you whether the prose reaches the table at all, which is the failure this was
written for.

Measured 2026-09-10 on a live card: 728 characters of prose across five lines produced
two traits, one of which the engine cannot use yet.

Exit code is 1 if any race would produce no engine-ready trait at all.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

# Pathfinder's own vocabulary. A card is the world's words; these are the consumer's, and
# a card containing them is describing a rule rather than a people. They usually still
# work — "low-light vision" trips the low-light cue — but they work by accident, and the
# next card says "they see well at dusk" and trips nothing.
_RULES_WORDS = re.compile(
    r"\b(darkvision|low-?light vision|blindsense|blindsight|scent\s+\d|natural armou?r|"
    r"racial bonus|ability score|saving throw|\bDC\b|\bCR\b|\bAC\b|\bHD\b|hit dice|"
    r"\d+\s*(ft|feet)\b|\+\d|\-\d\s+to\b|\d+d\d+)", re.I)

_DIGIT = re.compile(r"\d")

FIELDS = ("body", "senses", "movement")


def load_cues(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def fired(text: str, cues: list[dict]) -> list[dict]:
    low = text.lower()
    return [c for c in cues if re.search(c["pattern"], low)]


def check(race: dict, cues: dict) -> tuple[list[str], list[str], list[dict]]:
    """(problems, notes, cues that fired) for one card."""
    problems: list[str] = []
    notes: list[str] = []
    name = str(race.get("name") or "(unnamed)")

    for key in ("id", "name", "people_id"):
        if not str(race.get(key) or "").strip():
            problems.append(f"no {key}")

    size = str(race.get("size") or "").strip().lower()
    if size not in cues["sizes"]:
        problems.append(f"size {size!r} is not one of {', '.join(cues['sizes'])}")
    speed = str(race.get("speed") or "").strip().lower()
    if speed not in cues["speeds"]:
        problems.append(f"speed {speed!r} is not one of {', '.join(cues['speeds'])}")

    # Every line of prose, and which field it came from.
    lines: list[tuple[str, str]] = []
    for field in FIELDS:
        got = race.get(field) or []
        if isinstance(got, str):
            problems.append(f"{field} is a string; it must be a list of sentences")
            got = [got]
        for line in got:
            lines.append((field, str(line)))

    if not lines:
        problems.append("no body, senses or movement at all — nothing to read")

    # The consumer concatenates all three fields and runs the cues over the whole blob,
    # so a cue fires once no matter how many times it is said.
    blob = " ".join(t for _f, t in lines)
    hits = fired(blob, cues["cues"])

    ready = [c for c in hits if c["engine_ready"]]
    if not hits:
        problems.append("no cue fires: this card produces size and speed and nothing else")
    elif not ready:
        problems.append(
            "no ENGINE-READY cue fires — every trait it grants is one the engine cannot "
            "use yet (" + "; ".join(c["waits_on"] for c in hits) + ")")

    # Duplication between fields. Harmless mechanically, and a sign the card was filled
    # by copying rather than written.
    seen: dict[str, str] = {}
    for field, text in lines:
        key = " ".join(text.lower().split())
        if key in seen and seen[key] != field:
            notes.append(f"the same sentence appears in both {seen[key]} and {field}")
        elif key in seen:
            notes.append(f"the same sentence appears twice in {field}")
        seen[key] = field

    # A field whose words reach nothing.
    for field in FIELDS:
        got = [str(x) for x in (race.get(field) or [])]
        if got and not fired(" ".join(got), cues["cues"]):
            notes.append(f"{field} triggers no cue — its words reach nothing")

    for field, text in lines:
        if _RULES_WORDS.search(text):
            notes.append(f"{field} uses Pathfinder's vocabulary, not the world's: "
                         f"{_RULES_WORDS.search(text).group(0)!r}")
        if _DIGIT.search(text):
            notes.append(f"{field} contains a digit: {text[:60]!r}")
        words = len(text.split())
        if words > 30:
            notes.append(f"{field} has a {words}-word sentence; one clear sentence per "
                         f"line reads better and risks fewer accidental cues")
        if text.count(".") > 1 and not text.rstrip().endswith("."):
            notes.append(f"{field} line looks like more than one sentence")

    # What the people is good and bad at. All three or none: the Advanced Race Guide's
    # standard array is +2/+2/-2 as a unit, and a card giving two strengths and no
    # weakness would buy a net +4 by saying less.
    words = set(cues.get("ability_words") or {})
    good = [str(x).strip().lower() for x in (race.get("strengths") or []) if str(x).strip()]
    weak = str(race.get("weakness") or "").strip().lower()
    if not good and not weak:
        notes.append("no strengths or weakness — this race gets the same generic "
                     "+2 physical / +2 mental / -2 any as every other race in the world")
    else:
        unknown = [w for w in good + ([weak] if weak else []) if w not in words]
        if unknown:
            problems.append(f"not ability words: {', '.join(sorted(set(unknown)))} — "
                            f"use two of {', '.join(sorted(words))} as strengths and one "
                            f"as the weakness")
        elif len(good) != 2 or len(set(good)) != 2:
            problems.append(f"{len(set(good))} strength(s); it takes exactly two "
                            f"different ones or the whole array is ignored")
        elif not weak:
            problems.append("strengths with no weakness; the array is +2/+2/-2 as a "
                            "unit and half of one is ignored")
        elif weak in good:
            problems.append(f"{weak!r} is both a strength and the weakness")

    about = str(race.get("about") or "").strip()
    if not about:
        notes.append("no about paragraph — the character-creation screen will be blank")

    return problems, notes, hits


def _default_cues() -> Path:
    """Where the cue list is, in whichever repo this script is sitting in.

    Beside the script first, which is how it travels: this file is MEANT to be copied
    into the World Bible repo with `race-cues.json` next to it, and there the two sit
    together. Then the canonical generated copy, which is where it lives here.

    That order was the whole file's one bug, found 2026-09-16. A second copy of the
    generated list had been sitting in `tools/` since 10 September, six days and four
    vocabulary changes stale — twelve cues against fourteen, six engine-ready against
    twelve — and because it was beside the script it WON. Every count this checker
    printed in between, including the ones reported to the supplier as their content
    problem, was measured against a vocabulary this app had already moved past. The
    duplicate is deleted and this is why it cannot come back quietly.
    """
    beside = Path(__file__).with_name("race-cues.json")
    if beside.exists():
        return beside
    return Path(__file__).resolve().parent.parent / "docs" / "race-cues.json"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("export", type=Path, help="a <world>-campaign.json")
    ap.add_argument("--cues", type=Path, default=None)
    args = ap.parse_args()
    if args.cues is None:
        args.cues = _default_cues()

    if not args.cues.exists():
        print(f"cannot find {args.cues} — it is generated by Pathfinder GM's "
              f"tools/export_race_cues.py and must sit beside this script.")
        return 2
    cues = load_cues(args.cues)
    world = json.loads(args.export.read_text(encoding="utf-8"))
    written = (world.get("play") or {}).get("races") or []

    print(f"{args.export.name}: schema {world.get('schema_version')}, "
          f"{len(written)} race card(s)")
    print(f"vocabulary: {cues['cue_count']} cues, {cues['engine_ready_count']} of them "
          f"usable by the engine today\n")

    if not written:
        print("no play.races[] — the consumer will derive races from PEOPLE anatomy "
              "facts instead.")
        return 0

    bad = thin = noted = 0
    for race in written:
        problems, notes, hits = check(race, cues)
        name = str(race.get("name") or "(unnamed)")
        ready = [c for c in hits if c["engine_ready"]]
        head = f"  {name}"
        print(head)
        array = "+2/+2/-2 as written" if not [p for p in problems if "strength" in p
                or "ability words" in p or "weakness" in p] and (race.get("strengths")
                or race.get("weakness")) else "generic (player chooses)"
        print(f"    builds: size {race.get('size')}, speed {race.get('speed')}, "
              f"abilities {array}, {len(hits)} trait(s), {len(ready)} usable in play")
        for c in hits:
            mark = "ok  " if c["engine_ready"] else "wait"
            print(f"      [{mark}] {c['shows']}")
        for p in problems:
            print(f"    PROBLEM  {p}")
        for n in notes:
            print(f"    note     {n}")
        print()
        if problems:
            bad += 1
        if notes:
            noted += 1
        if len(ready) < 2:
            thin += 1

    # Three separate counts, because "clean" was the wrong headline: a card with no
    # problems and one usable trait passes every check and is still not worth playing.
    print(f"{len(written)} card(s): {bad} with problems, {noted} with notes, "
          f"{thin} thin (fewer than two traits the engine can use).")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
