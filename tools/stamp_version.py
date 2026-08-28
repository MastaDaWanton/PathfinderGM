"""Stamp the current git hash and commit time into pathfindergm/version.py.

Run before PyInstaller; a frozen app has no git to ask. Restores the
placeholder with `--restore` so the working copy never carries a stale stamp.
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

TARGET = Path(__file__).resolve().parents[1] / "pathfindergm" / "version.py"


def main() -> int:
    text = TARGET.read_text(encoding="utf-8")
    if "--restore" in sys.argv:
        stamped = re.sub(r'BUILD = "[^"]*"', 'BUILD = "unstamped"', text, count=1)
        TARGET.write_text(stamped, encoding="utf-8")
        print("restored placeholder")
        return 0
    out = subprocess.run(
        ["git", "log", "-1", "--format=%h %cd", "--date=format:%Y-%m-%d %H:%M"],
        capture_output=True, text=True)
    if out.returncode != 0 or not out.stdout.strip():
        print("no git — leaving placeholder")
        return 1
    stamp = out.stdout.strip()
    TARGET.write_text(
        re.sub(r'BUILD = "[^"]*"', f'BUILD = "{stamp}"', text, count=1),
        encoding="utf-8")
    print(f"stamped {stamp}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
