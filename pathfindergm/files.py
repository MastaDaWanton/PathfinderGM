"""Writing the player's files so that no moment exists at which they are half-written.

Measured 2026-09-25: every writer in the app — the campaign save, the roster, the model
settings, house rules, the secret key, every homebrew bench — used `Path.write_text`,
which truncates the file and then writes it. A save is rewritten whole on every turn and
grows with the transcript, and the desktop shell's fallback is a hard `taskkill`, so an
app closed mid-turn could leave the one copy of a campaign as a half-written file.
`Campaign.load` refuses such a file honestly (`UnreadableSave`), but there was nothing to
fall back on. The only atomic writer in the app was the portfile, which mattered least.

The standard shape: write a temporary file in the same directory (so the rename cannot
cross a volume), flush it to disk, and `os.replace` it over the target, which is atomic
on NTFS and POSIX alike. A reader sees the old file or the new one, never a torn one.
"""
from __future__ import annotations

import os
import shutil
import tempfile
import time
from pathlib import Path

# os.replace on Windows fails with PermissionError while another process holds the
# target open — an indexer, an antivirus scan, the player's own editor. Brief and
# transient; a few retries ride it out rather than losing the turn.
_REPLACE_TRIES = 20
_REPLACE_WAIT = 0.05


def _replace(src: str, dst: Path) -> None:
    for attempt in range(_REPLACE_TRIES):
        try:
            os.replace(src, dst)
            return
        except PermissionError:
            if attempt == _REPLACE_TRIES - 1:
                raise
            time.sleep(_REPLACE_WAIT)


def write_text(path, text: str, encoding: str = "utf-8") -> Path:
    """`Path.write_text`, atomically. Same newline handling, so the bytes on disk are
    the ones `write_text` would have written."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding=encoding) as f:
            f.write(text)
            f.flush()
            os.fsync(f.fileno())
        _replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
    return path


def backups(path, keep: int = 3) -> list[Path]:
    """The kept copies of `path`, newest first: `name.1` is the save before this one."""
    path = Path(path)
    return [p for p in (path.with_name(f"{path.name}.{n}") for n in range(1, keep + 1))
            if p.exists()]


def keep_backup(path, keep: int = 3) -> None:
    """Shift `name.1..keep-1` up one and make `name.1` the file as it stands now.

    Called before the new version replaces it, so `name.1` is always the last save that
    was whole. A hard link when the filesystem allows it — no bytes copied, and the
    replace that follows points `name` at the new file while `name.1` keeps the old one —
    and a copy when it does not.
    """
    path = Path(path)
    if not path.exists() or keep < 1:
        return
    oldest = path.with_name(f"{path.name}.{keep}")
    try:
        oldest.unlink(missing_ok=True)
    except OSError:
        return
    for n in range(keep - 1, 0, -1):
        src = path.with_name(f"{path.name}.{n}")
        if src.exists():
            try:
                _replace(str(src), path.with_name(f"{path.name}.{n + 1}"))
            except OSError:
                return
    first = path.with_name(f"{path.name}.1")
    try:
        os.link(path, first)
    except OSError:
        try:
            shutil.copy2(path, first)
        except OSError:
            pass
