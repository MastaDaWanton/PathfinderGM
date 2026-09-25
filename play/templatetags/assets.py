"""`{% asset "js/table/01-core.js" %}` — a static URL stamped with its own content.

The play page's script became six files on 2026-09-25, and a file the browser caches is a
file that can be served stale: the Electron shell keeps its disk cache in the user data
directory, which outlives every reinstall, and the origin (127.0.0.1:8917) never changes —
the shape of World Bible's five-day-old stylesheet (CLAUDE.md: "version-stamp anything
cached ... and compare content, not just timestamps"). So each URL carries a hash of the
file's bytes: an edit is a new URL, and nothing has to remember to bump a version.

Hashed once per (path, mtime, size) and kept, so a page render costs a stat per file.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

from django import template
from django.contrib.staticfiles import finders
from django.templatetags.static import static

register = template.Library()

_STAMPS: dict[tuple, str] = {}


def stamp(path: str) -> str:
    """The first ten hex digits of the file's sha256, or "" if it cannot be found."""
    found = finders.find(path)
    if not found:
        return ""
    p = Path(found)
    st = p.stat()
    key = (str(p), st.st_mtime_ns, st.st_size)
    if key not in _STAMPS:
        _STAMPS[key] = hashlib.sha256(p.read_bytes()).hexdigest()[:10]
    return _STAMPS[key]


@register.simple_tag
def asset(path: str) -> str:
    url = static(path)
    v = stamp(path)
    return f"{url}?v={v}" if v else url
