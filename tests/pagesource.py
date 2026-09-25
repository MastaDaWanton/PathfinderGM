"""What a page IS, for tests that read its code: the template plus the scripts it loads.

The play table's script moved out of `play/templates/play/table.html` into six classic
script files under `play/static/js/table/` on 2026-09-25. Twenty-seven tests read the
page's JavaScript from the template file or from the served HTML, and every one of them
would have gone on passing or failing against the wrong text. They read it through here.
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TABLE = ROOT / "play" / "templates" / "play" / "table.html"
TABLE_SCRIPTS = ROOT / "play" / "static" / "js" / "table"

_SRC = re.compile(r"<script[^>]*\bsrc=\"([^\"]+)\"")


def table_scripts() -> list[Path]:
    """The play table's script files, in the order the page loads them."""
    return sorted(TABLE_SCRIPTS.glob("*.js"))


def table_source() -> str:
    """The play table's template and every script file it loads, as one text."""
    parts = [TABLE.read_text(encoding="utf-8")]
    parts += [p.read_text(encoding="utf-8") for p in table_scripts()]
    return "\n".join(parts)


def served(client, path: str) -> str:
    """A served page plus the body of every local script it loads, fetched through the
    same client — what the browser ends up running."""
    html = client.get(path).content.decode("utf-8")
    bodies = []
    for src in _SRC.findall(html):
        if src.startswith("/static/"):
            r = client.get(src.split("?", 1)[0])
            if r.status_code == 200:
                bodies.append(b"".join(r.streaming_content).decode("utf-8")
                              if getattr(r, "streaming", False) else r.content.decode("utf-8"))
    return "\n".join([html] + bodies)
