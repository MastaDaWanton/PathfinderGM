"""The summon tables, and the one reading of a summoning spell's choice.

Summon monster and summon nature's ally carry a `summon` spec naming a table and the
spell's own level (`{"type": "summon", "table": "summon-monster", "level": 3}`); the cast
names the creature (`cast` param `creature`), and this module says whether that creature
is one the spell may call and how many come. Nothing here invents a creature: a name the
table does not carry is refused with the table's own list, before the slot is spent
(`Engine._check_cast`).

Prior art (docs/implementation-audit-2026-11-22.md §4, lesson 8): Foundry PF1 never built a
summon executor — its open issues ask only for reference lists — and Owlcat ships each
summon as its own ability blueprint. Nobody shipped the table as data, so it is written
here: content/spells/summon-tables.json, read from CRB Tables 10-1 and 10-2.

The rules read (Summon Monster I and II, CRB p.351-352):
- I: "one creature" from the 1st-level list.
- II and up: "one creature from the 2nd-level list or 1d3 creatures of the same kind from
  the 1st-level list"; III adds "1d4+1 creatures of the same kind from the 1st-level
  list", and IV on "from any lower-level list". So: the spell's own level → 1, one level
  lower → 1d3, two or more lower → 1d4+1. Summon nature's ally reads the same.
- Starred entries take the celestial template "if you are good", the fiendish "if you
  are evil", and "if you are neutral, you may choose". The app tracks no alignment yet
  (the owner's smite ruling, 2026-10-05, treats every target the permissive way until it
  does), so every caster chooses as a neutral one would: `celestial-dog`, `fiendish-dog`,
  or the bare `dog`, which is celestial.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

_TABLES: dict | None = None
# The templates a starred entry may take (CRB Table 10-1's footnote, Core only).
TEMPLATES = ("celestial", "fiendish")


def tables() -> dict[str, dict[str, list[str]]]:
    """`{"summon-monster": {"1": ["rat-dire*", ...]}, ...}`, read once."""
    global _TABLES
    if _TABLES is None:
        from django.conf import settings

        path = Path(settings.BASE_DIR) / "content" / "spells" / "summon-tables.json"
        _TABLES = json.loads(path.read_text(encoding="utf-8"))["tables"]
    return _TABLES


def _templated(base: str, template: str) -> str:
    """`celestial-dire-rat` for the base `rat-dire`: the derived block's id, which
    `templates.apply_chain` makes from the template and the block's printed name."""
    from . import bestiary

    name = str((bestiary.lookup(base) or {}).get("name") or base)
    return f"{template}-" + re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def options(table: str, level: int) -> list[dict]:
    """Every creature this spell may call, with how many come.

    `[{"creature": "celestial-dog", "from_level": 1, "count": "1"}, ...]`, the spell's own
    level first. A starred entry is offered under both templates."""
    rows = tables().get(table) or {}
    out = []
    for lvl in range(int(level), 0, -1):
        gap = int(level) - lvl
        count = "1" if gap == 0 else "1d3" if gap == 1 else "1d4+1"
        # III: 1d4+1 only from the 1st-level list; IV on: "from any lower-level list" —
        # both are "two or more below", which is the one rule.
        for entry in rows.get(str(lvl)) or ():
            base = entry.rstrip("*")
            ids = [_templated(base, t) for t in TEMPLATES] if entry.endswith("*") else [base]
            out += [{"creature": c, "base": base, "from_level": lvl, "count": count}
                    for c in ids]
    return out


def pick(table: str, level: int, said) -> dict:
    """The option the cast named, or ValueError naming the ones it could have.

    `said` is a bestiary id or a creature's name, either template or none; a bare starred
    base ("dog") is the celestial one (no alignment is tracked: every caster may choose).
    """
    from . import bestiary

    slug = lambda text: re.sub(r"[^a-z0-9]+", "-", str(text or "").lower()).strip("-")
    want = slug(said)
    opts = options(table, level)
    names: dict[str, dict] = {}
    for o in opts:
        for key in (o["creature"], slug((bestiary.lookup(o["creature"]) or {}).get("name"))):
            names.setdefault(key, o)
    for o in opts:
        # A starred base said bare, by id or printed name, is the celestial one.
        if o["creature"].startswith("celestial-") or o["creature"] == o["base"]:
            for key in (o["base"], slug((bestiary.lookup(o["base"]) or {}).get("name"))):
                names.setdefault(key, o)
    if want in names:
        return names[want]
    shown = ", ".join(sorted({o["creature"] for o in opts if o["from_level"] == level}))
    raise ValueError(
        (f"{said!r} is not on the list this spell calls from. " if want else
         "Name the creature to call. ")
        + f"Level {level}: {shown}"
        + (f"; or 1d3 of one kind from level {level - 1}"
           + (", or 1d4+1 from any lower level" if level > 2 else "") if level > 1 else "")
        + ".")


def table_spec(spell) -> dict | None:
    """The spell's table summon, wherever it sits in its effects, or None."""
    def walk(specs):
        for s in specs or ():
            if not isinstance(s, dict):
                continue
            if s.get("type") == "summon" and s.get("table"):
                return s
            got = walk(s.get("effects")) or walk(s.get("options"))
            if got:
                return got
        return None
    return walk(getattr(spell, "effects", None))
