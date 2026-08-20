"""Where things live, computed so that it stays true inside a PyInstaller bundle.

`__file__` is never load-bearing here for anything the *user* owns. Frozen, it points
inside the unpacked bundle and says nothing about where the app was installed — this cost
real debugging time in World Bible and is written up in CLAUDE.md. Bundled read-only
resources are the one legitimate use, because those genuinely do live in the bundle.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

APP_NAME = "PathfinderGM"

# Bumped whenever anything cached under the user data directory changes shape. World Bible
# served a five-day-old stylesheet across four versions because a staleness check answered
# "fresh"; every derived file we write outside the install directory carries this stamp.
CACHE_VERSION = 1


def is_frozen() -> bool:
    return getattr(sys, "frozen", False)


def resource_root() -> Path:
    """Read-only files shipped *with* the app (templates, fixtures, rules data).

    Under PyInstaller these really are inside the bundle, so `_MEIPASS` is correct.
    """
    if is_frozen():
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    return Path(__file__).resolve().parent.parent


def install_root() -> Path:
    """Where the app was actually installed — the executable's own location."""
    if is_frozen():
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def user_data_root() -> Path:
    """Per-user writable state: campaign saves, logs, settings.

    Overridable so tests and packaging checks can point at a throwaway directory —
    proving a packaging fix against a seeded bad state is the only thing that has ever
    settled one of these arguments.
    """
    override = os.environ.get("PATHFINDER_GM_DATA")
    if override:
        return Path(override)
    if sys.platform == "win32":
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
    return base / APP_NAME


def campaigns_root() -> Path:
    p = user_data_root() / "campaigns"
    p.mkdir(parents=True, exist_ok=True)
    return p
