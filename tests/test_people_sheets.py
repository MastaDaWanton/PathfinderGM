"""The shipped builds' sheets are made at tool time, not at every start; and what a built
person is told and tagged with.

Measured 2026-10-30 (review of 0.2.23): `bestiary._people` built content/npc-builds'
272 people through the engine on every start, 1.90 s of it — the first
`bestiary.imported()` went from 0.34-0.43 s before the builds to 2.07-2.12 s after (2.19-2.33
s on this branch before the fix, 0.17-0.19 s after). tools/build_people_sheets.py writes
what `_people` made to content/npc-builds/people-sheets.json, each stamped with its build.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from django.conf import settings

from rules import bestiary

ROOT = Path(settings.BASE_DIR)


def test_the_precomputed_sheets_are_what_the_engine_makes_now():
    """Stale, the file is slow (a mismatched stamp is built live) but a sheet whose BUILD
    is unchanged while the engine's arithmetic moved would be served wrong — the
    favoured-class hit point of 2026-10-30 was exactly such a change. Every sheet is
    rebuilt here and compared."""
    made = bestiary.built_sheets()
    builds = json.loads((ROOT / "content" / "npc-builds" / "people.json")
                        .read_text(encoding="utf-8"))["builds"]
    assert len(made) == len(builds) == 272, (len(made), len(builds))
    stale = []
    for doc in builds:
        pre = made.get(doc["id"])
        if pre is None or pre["stamp"] != bestiary.build_stamp(doc) \
                or pre["block"] != bestiary.people_block(doc):
            stale.append(doc["id"])
    assert not stale, (f"{len(stale)} stale sheets ({stale[:5]}): run "
                       f"python tools/build_people_sheets.py")


def test_the_store_serves_the_precomputed_sheet():
    store = bestiary.imported()
    made = bestiary.built_sheets()
    assert store["guardsman-level-4"] == made["guardsman-level-4"]["block"]


def test_a_build_edited_since_is_made_live(tmp_path, monkeypatch):
    """A roster re-run without the sheets: the stamp no longer matches, and the build is
    made from the document as it stands, never served from the file."""
    made = bestiary.built_sheets()
    doctored = {k: dict(v) for k, v in made.items()}
    doctored["farmer-level-1"]["block"] = dict(doctored["farmer-level-1"]["block"],
                                               description="from the file")
    monkeypatch.setattr(bestiary, "built_sheets", lambda: doctored)
    out: dict = {}
    bestiary._people(out, [ROOT / "content" / "npc-builds"])
    assert out["farmer-level-1"]["description"] == "from the file", "the file was not read"
    doctored["farmer-level-1"]["stamp"] = "not-this-build"
    out = {}
    bestiary._people(out, [ROOT / "content" / "npc-builds"])
    assert out["farmer-level-1"]["description"] != "from the file"


def test_the_tool_check_says_fresh():
    run = subprocess.run([sys.executable, "tools/build_people_sheets.py", "--check"],
                         cwd=ROOT, capture_output=True, text=True, timeout=300)
    assert run.returncode == 0, run.stdout + run.stderr


# --- what a built person is ------------------------------------------------------------------

def test_built_guards_keep_the_law():
    """The watchman carries `role.guard`; the builds that replaced the adventures' guards
    did not, so measured 2026-10-30 a built guardsman was never "a guard" to the victim
    question (gm/acts_to_ops.py `label`) and never joined a wanted player's fight
    (`Engine._law_joins`). The build's tag reaches the block (the sheet has no field for
    it) and the block's tags are what `standing_tags` reads."""
    from gm import acts_to_ops

    for bid in ("guardsman-level-1", "jailer-level-4", "warden-level-7"):
        a = bestiary.instantiate(bid)
        assert a.has_state("role.guard"), bid
        assert "a guard" in acts_to_ops.label(a), bid
    assert not bestiary.instantiate("farmer-level-1").has_state("role.guard")


def test_a_built_persons_turn_names_what_they_fight_with():
    """`printed_arms` reads a print and a build has none, so every built townsperson's turn
    went out with no "Their attacks" line (gm/prompts.py) and the model guessed."""
    from gm import prompts

    a = bestiary.instantiate("guardsman-level-4")
    assert a.printed_arms() == []
    msgs = prompts.npc_turn_messages("brief", [], "c1", a, 1)
    turn = msgs[-1]["content"]
    assert "Their attacks, by weapon name: masterwork longspear." in turn, turn
    # And the name it is told is one its own sheet swings.
    assert a.weapon("masterwork longspear").get("crafted_base") == "longspear"
