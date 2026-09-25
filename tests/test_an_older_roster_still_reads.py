"""An entry written by an older build is still on the shelf; only a newer one is refused.

Measured 2026-09-25: `roster.load` compared `roster_version != ROSTER_VERSION`, the bug
`Campaign.load` had already been fixed for — bumping the version would have made every
character disappear from the list at once.
"""
from __future__ import annotations

import json

from django.test import override_settings


def test_older_is_read_and_newer_is_refused(tmp_path):
    from play import roster
    from rules.sheet import load_pc

    with override_settings(CAMPAIGN_DIR=str(tmp_path / "campaigns")):
        entry = roster.enrol(load_pc("fixtures/pc-kesst.json"))
        p = roster.path_for(entry.id)
        raw = json.loads(p.read_text(encoding="utf-8"))

        raw["roster_version"] = roster.ROSTER_VERSION - 1
        p.write_text(json.dumps(raw), encoding="utf-8")
        assert roster.load(entry.id) is not None, "an older entry vanished"

        raw.pop("roster_version")
        p.write_text(json.dumps(raw), encoding="utf-8")
        assert roster.load(entry.id) is not None, "an entry from before versions vanished"

        raw["roster_version"] = roster.ROSTER_VERSION + 1
        p.write_text(json.dumps(raw), encoding="utf-8")
        assert roster.load(entry.id) is None, "a newer build's entry must not be guessed at"
