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
from pathfindergm import files

APP_NAME = "PathfinderGM"

# To be bumped whenever anything *derived* under the user data directory changes shape.
# World Bible served a five-day-old stylesheet across four versions because a staleness
# check answered "fresh", and CLAUDE.md's rule is that anything cached outside the install
# directory carries a version stamp and is compared by content, not timestamp.
#
# As of the first packaged build (2026-08-24) **nothing derived is written here and this
# constant is therefore unused.** That is a finding, not a gap. Everything under
# `user_data_root()` is authored or chosen by the user — campaigns and characters are
# saves, `worlds/` holds exports they imported, `homebrew/` holds what they built,
# `models.json` and the house rules are settings — so none of it is computed from shipped
# content and none of it can go stale against a newer build. The one cache in the app is
# `world.loader._cached`, which is in-memory, keyed on the source file's mtime, and gone
# when the process exits.
#
# The previous version of this comment claimed that "every derived file we write outside
# the install directory carries this stamp", which was false in a build where no file did.
# A comment promising a guarantee nobody implemented is worse than no comment, because the
# next person reads it as done. `tests/test_packaging.py` pins both halves: that the
# loader's cache is still in-memory, and that this note still admits nothing uses the
# constant. The moment something is derived to disk here, both assertions fail and the
# stamp has to be written and compared before the suite is green again.
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


def secret_key() -> str:
    """This installation's Django secret key, made once and kept.

    The settings comment used to say the key "is regenerated per install in the packaged
    build". Nothing regenerated it: every copy of the exe would have shipped the same
    literal, which is the one thing a secret key must never be. Written to the user's
    own data directory on first run, so it is per install in fact rather than in a
    comment — and read back on every run after, because a key that changes on restart
    logs everyone out of their own session.

    Kept out of the install directory for the reason CLAUDE.md gives about derived
    files: the install directory is replaced wholesale by a reinstall, and a key that
    vanishes with it would invalidate every signed cookie the user still holds.
    """
    import secrets

    path = user_data_root() / "secret.key"
    try:
        existing = path.read_text(encoding="utf-8").strip()
        if len(existing) >= 50:
            return existing
    except OSError:
        pass
    made = secrets.token_urlsafe(64)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        files.write_text(path, made)
        if sys.platform != "win32":
            path.chmod(0o600)
    except OSError:
        # An unwritable data directory is not a reason to refuse to start; the app is
        # a single-user localhost desktop tool, and a per-run key costs a lost session
        # rather than a lost campaign.
        pass
    return made


def campaigns_root() -> Path:
    p = user_data_root() / "campaigns"
    p.mkdir(parents=True, exist_ok=True)
    return p
