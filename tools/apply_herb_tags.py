"""Take the tagging answer back in, having checked it first.

A model's JSON is a proposal, not a fact. Everything here is refused unless it names a
real ingredient and sets known flags to real booleans — the same posture the intent
protocol takes with the GM, and for the same reason: a confident wrong answer written
into the content is worse than no answer, because nobody will look at it again.

Writes to the *homebrew* overlay rather than to `content/`, so the shipped corpus is
untouched and the tags can be thrown away by deleting one file. Dry run by default.

    python tools/apply_herb_tags.py answer.json
    python tools/apply_herb_tags.py answer.json --apply
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "pathfindergm.settings")

import django  # noqa: E402

django.setup()

FLAGS = ("needs_extraction", "volatile", "can_grind", "mix_raw", "brew_raw", "animal")


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    apply = "--apply" in sys.argv
    raw = Path(sys.argv[1]).read_text(encoding="utf-8").strip()
    # A chat answer often arrives fenced. Take the JSON out of the middle rather than
    # making the user edit the file by hand.
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        raw = raw[raw.index("{"):] if "{" in raw else raw
    proposed = json.loads(raw)

    # Two shapes arrive in practice. The prompt asks for {id: {flags}} and a model
    # often answers with the whole corpus back, each entry carrying its flags inline —
    # which is a perfectly clear answer and not worth rejecting over its envelope.
    if isinstance(proposed, list):
        proposed = {str(r.get("id")): {k: v for k, v in r.items() if k != "id"}
                    for r in proposed if isinstance(r, dict) and r.get("id")}

    from django.conf import settings

    from rules import herbprep, ingredients as ing

    known = ing.all_ingredients()
    kept, problems = {}, []

    for iid, flags in proposed.items():
        if iid not in known:
            problems.append(f"{iid!r} is not an ingredient in this build")
            continue
        if not isinstance(flags, dict):
            problems.append(f"{iid}: expected an object of flags")
            continue
        entry, why = {}, flags.get("why") or {}
        for flag in FLAGS:
            if flag not in flags:
                continue
            value = flags[flag]
            if not isinstance(value, bool):
                problems.append(f"{iid}.{flag}: {value!r} is not true or false")
                continue
            # Only what differs from the default is worth writing: a file restating
            # every default for 162 ingredients hides the twelve that matter.
            if value != getattr(herbprep.Prep(), flag):
                entry[flag] = "yes" if value else "no"
                if flag in why:
                    entry.setdefault("_why", {})[flag] = str(why[flag])
        if entry:
            kept[iid] = {"id": iid, "name": known[iid].name, **entry}

    for line in problems:
        print("refused:", line)
    print(f"\n{len(kept)} of {len(proposed)} ingredients carry a tag away from the "
          f"defaults.")
    for iid, entry in sorted(kept.items()):
        marks = ", ".join(f"{k}={v}" for k, v in entry.items()
                          if k in FLAGS)
        print(f"  {entry['name']:28} {marks}")

    if not apply:
        print("\nDry run. Re-run with --apply to write them.")
        return 0

    out = Path(settings.CAMPAIGN_DIR).parent / "homebrew" / "ingredients"
    out.mkdir(parents=True, exist_ok=True)
    target = out / "preparation-tags.json"
    target.write_text(
        json.dumps({"ingredients": list(kept.values())}, indent=2, ensure_ascii=False)
        + "\n", encoding="utf-8")
    print(f"\nWritten to {target}. The shipped corpus is untouched; delete that file "
          f"to undo the whole thing.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
