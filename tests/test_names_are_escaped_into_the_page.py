"""Names that reach `innerHTML` go through `esc`.

Review 2026-11-11, finding 15: the board and the combat target chips joined an actor's
condition names straight into `innerHTML` (`a.conditions.join(", ")`), beside a name
that WAS escaped. A condition is a string from a document — a homebrew effect, a
world's creature — so `<img src=x onerror=…>` as a condition name was markup on the
host's table. The actor's ref and a homebrew race's `choose.from` were the same shape.
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TABLE_JS = ROOT / "play" / "static" / "js" / "table"


def _src(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_the_board_escapes_refs_and_conditions():
    src = _src(TABLE_JS / "02-state.js")
    board = src[src.index('$("#board").innerHTML'):src.index("renderTalk(s);")]
    assert "a.conditions.map(esc).join" in board
    assert "${esc(a.ref)}" in board
    assert "a.conditions.join" not in board and "${a.ref}" not in board


def test_the_target_chips_escape_conditions():
    src = _src(TABLE_JS / "04-combat-and-turns.js")
    chips = src[src.index('$("#cb-targets").innerHTML'):src.index("renderPlan();")]
    assert "(f.conditions || []).map(esc).join" in chips
    assert "(f.conditions || []).join" not in chips


def test_no_table_script_joins_conditions_raw():
    """Every copy, not the two the review named: a third would be the same defect."""
    for path in sorted(TABLE_JS.glob("*.js")):
        assert "conditions.join(" not in _src(path), path.name
        assert "conditions || []).join(" not in _src(path), path.name


def test_the_race_card_escapes_what_a_homebrew_race_chooses_from():
    home = _src(ROOT / "play" / "templates" / "play" / "home.html")
    assert "${c.amount} ${c.from}`).join" in home          # the details card: esc(mods)
    assert home.count("${c.amount} ${c.from}") == 1
    assert "${esc(c.amount)} ${esc(c.from)}" in home       # the picker card, inline
    assert "${esc(mods)}" in home
