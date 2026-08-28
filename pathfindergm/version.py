"""The build the player is actually running, printed where they can see it.

Asked for in as many words: "add a version tracker to the main page and i dont
have to wonder" — after a session of findings filed against a build that had
already been superseded. `BUILD` is stamped by `tools/stamp_version.py` as part
of packaging; in a working copy it reads git directly so dev always shows the
truth without a stamp step.
"""
from __future__ import annotations

import subprocess

# Overwritten by tools/stamp_version.py at package time. The placeholder is what
# ships if somebody builds without stamping — visibly wrong beats silently stale.
BUILD = "unstamped"


def build() -> str:
    if BUILD != "unstamped":
        return BUILD
    try:
        out = subprocess.run(
            ["git", "log", "-1", "--format=%h %cd", "--date=format:%Y-%m-%d %H:%M"],
            capture_output=True, text=True, timeout=5)
        if out.returncode == 0 and out.stdout.strip():
            return out.stdout.strip() + " (dev)"
    except Exception:
        pass
    return BUILD
