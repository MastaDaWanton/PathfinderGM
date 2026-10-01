"""I3: the table's two scripts — the Spells popover's search and the map's area overlay.

Measured 2026-09-29: typing "burn" into the Spells popover's search still showed Magic
Missile. The match was right; the row stayed on screen because `#spellpop .sp-spell
{ display: flex }` outranks the user agent's `[hidden] { display: none }` — only a level
with no match at all disappeared. And a cast's area (`scene.grid.areas`, filled by Lane E
since Phase 2) was sent with every state and drawn by nothing.

The filter's word-start rule is run in node, as test_f_page runs the clock, so the test
reads the shipped function rather than a copy of it.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
JS = ROOT / "play" / "static" / "js" / "table"


def _js(name: str) -> str:
    return (JS / name).read_text(encoding="utf-8")


def test_i3_the_search_hides_by_display_not_the_attribute_alone():
    code = _js("10-spells.js")
    handler = code[code.index('closest("#spellpick-find")'):]
    handler = handler[:handler.index("});")]
    assert 'b.style.display = hit ? "" : "none"' in handler
    assert "b.hidden = !hit" in handler, "the attribute stays, for assistive tech"


@pytest.mark.skipif(shutil.which("node") is None, reason="node is not on this machine")
def test_i3_burn_finds_burning_hands_and_not_magic_missile(tmp_path):
    code = _js("10-spells.js")
    m = re.search(r"const starts = name => (.+?);\n", code, re.S)
    assert m, "the word-start matcher moved"
    script = tmp_path / "starts.js"
    names = ["burning hands", "magic missile", "mage armor", "ray of frost", "shield"]
    script.write_text(
        "const out = {};\n"
        f"for (const q of {json.dumps(['burn', 'mis', 'and', 'ray fr', ''])}) {{\n"
        f"  const starts = name => {m.group(1)};\n"
        f"  out[q] = {json.dumps(names)}.filter(n => !q || starts(n));\n"
        "}\nconsole.log(JSON.stringify(out));\n", encoding="utf-8")
    done = subprocess.run(["node", str(script)], capture_output=True, text=True)
    assert done.returncode == 0, done.stderr
    got = json.loads(done.stdout)
    assert got["burn"] == ["burning hands"]
    assert got["mis"] == ["magic missile"]
    assert got["and"] == [], "a substring anywhere is a loose filter"
    assert got["ray fr"] == ["ray of frost"]
    assert got[""] == names


def test_i3_a_stable_door_for_attaching_a_chip():
    """I5's spell cards attach through this one name, whatever this file does inside."""
    code = _js("10-spells.js")
    # `range` joined the arguments 2026-10-01, so a personal spell staged in a fight
    # lands on the caster (tests/test_spells_in_the_turn.py).
    assert "window.attachSpellChip = function attachSpellChip(id, name, aim" in code
    assert "AIM_RE.test" in code


def test_i3_the_map_draws_the_latest_areas():
    code = _js("03-offers-and-map.js")
    body = code[code.index("function renderMap("):code.index("function renderRolls(")]
    assert "g.areas" in body and 'class="spellarea' in body
    assert body.index("g.areas") < body.index("for (const a of s.scene.actors)"), \
        "drawn over the tokens, the area would hide who it caught"
