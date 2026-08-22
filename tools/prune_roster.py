"""Collapse duplicate roster entries left by the same character being started twice.

`roster.enrol` minted a fresh id on every call until it was taught to reuse an untouched
start, so a roster could accumulate rows that are identical in every visible way — seven
"Kesst Vayr · Rogue 1 · 9/9 hp" lines with nothing to tell them apart.

Nothing is deleted. Duplicates move to `characters/archive/`, and their campaigns move to
`campaigns/archive/` beside them, which is the same choice `campaign._read` makes for a
save it cannot parse: the player keeps the file, the app stops tripping over it.

Which one survives, in order:
  1. the character currently being played — losing the game under the cursor is not a
     tidy-up, it is a bug;
  2. failing that, the one with the most turns played;
  3. failing that, the oldest, because it is the one whose id has no suffix.

A name with one entry is never touched, so this is safe to run twice.

Run:  python tools/prune_roster.py            (report only)
      python tools/prune_roster.py --apply
"""
from __future__ import annotations

import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import os  # noqa: E402

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "pathfindergm.settings")

import django  # noqa: E402

django.setup()

from django.conf import settings  # noqa: E402

from play import campaign as campaign_mod, roster  # noqa: E402


def keeper(entries: list) -> object:
    """The one of a duplicate set that stays.

    `active_id()` is the *campaign* id and a campaign is free to be named something
    else entirely — the live one here is "slice" while its character is "kesst-vayr" —
    so the character actually in the chair is read off the campaign. The dry run caught
    this proposing to archive the game under the cursor, which is the exact outcome the
    first rule exists to prevent.
    """
    playing = campaign_mod.current().character_id
    for e in entries:
        if e.id == playing:
            return e
    return sorted(entries, key=lambda e: (-int(e.turns_played or 0), e.created or ""))[0]


def main() -> int:
    apply = "--apply" in sys.argv

    by_name: dict[str, list] = defaultdict(list)
    for entry in roster.everyone():
        by_name[entry.name].append(entry)

    char_archive = Path(settings.CAMPAIGN_DIR).parent / "characters" / "archive"
    camp_archive = Path(settings.CAMPAIGN_DIR) / "archive"

    moved = 0
    for name, entries in sorted(by_name.items()):
        if len(entries) < 2:
            continue
        stays = keeper(entries)
        print(f"{name}: {len(entries)} entries, keeping {stays.id} "
              f"({stays.turns_played} turns)")
        for e in entries:
            if e.id == stays.id:
                continue
            print(f"    archive {e.id} ({e.turns_played} turns)")
            moved += 1
            if not apply:
                continue
            char_archive.mkdir(parents=True, exist_ok=True)
            src = roster.path_for(e.id)
            if src.exists():
                src.rename(char_archive / src.name)
            camp = Path(settings.CAMPAIGN_DIR) / f"{e.campaign_id or e.id}.json"
            if camp.exists():
                camp_archive.mkdir(parents=True, exist_ok=True)
                camp.rename(camp_archive / camp.name)

    if not moved:
        print("nothing to prune: every name is unique.")
    elif apply:
        print(f"\n{moved} archived. Characters in {char_archive}, "
              f"their games in {camp_archive}.")
    else:
        print(f"\n{moved} would be archived. Re-run with --apply to do it.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
