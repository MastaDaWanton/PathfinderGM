"""The pen's two doors, Ways on and More (the owner, 2026-11-25: "the bar where we are
typing has become very crowded. lets organize and hide the locations and other buttons so
that it feels clean again").

Measured on the owner's own dungeon save at 1400x950 before the change: the desk above the
pen held 836px of controls in a 283px box, eleven of them ways out, so the text box sat
under three screens of buttons. docs/research/2026-11-25-clean-composer.md has the sources.
"""
from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
PAGE = (ROOT / "play/templates/play/table.html").read_text(encoding="utf-8")
EXITS_JS = ROOT / "play/static/js/table/11-exits.js"


def test_the_desk_above_the_pen_no_longer_holds_the_ways_or_the_abilities():
    """The 836px: eleven ways out and the abilities row lived in `.choices`. They live
    behind the pen's doors now, and the doors sit in the pen's own actions."""
    choices = PAGE[PAGE.index('<div class="choices">'):PAGE.index('<div id="err"')]
    assert 'id="exits"' not in choices and 'id="abilities"' not in choices
    actions = PAGE[PAGE.index('data-tut="pen-actions"'):PAGE.index("</form>")]
    for i in ("waysbtn", "wayspop", "exits", "morebtn", "morepop", "craftaction",
              "spellbtn", "abilities", "carryon"):
        assert f'id="{i}"' in actions, i
    # Continue stays a click away from the box: a turn verb (the owner's ruling), not a tray item.
    more = PAGE[PAGE.index('id="morepop"'):PAGE.index("</form>")]
    assert 'id="carryon"' not in more


def test_a_closed_door_lays_nothing_over_the_page():
    """0.2.13: an injected `display` outranked `[hidden]` and an invisible sheet took every
    click. The pen's popovers give their layout only while open, so the UA's own
    `:not(:popover-open) { display: none }` is never outranked."""
    for rule in re.findall(r"\n\s*\.penpop\s*\{([^}]*)\}", PAGE):
        assert "display" not in rule, rule
    assert ".penpop:popover-open { display: grid;" in PAGE


def _fit(spells_hidden: bool, abilities: int) -> dict:
    """Runs 11-exits.js's `fitMore` over a stub of the pen; returns where Craft action is."""
    prelude = r"""
    function node(id, parent) {
      const n = { id, hidden: false, children: [], parentElement: null,
        append(c) { if (c.parentElement) c.parentElement.children =
            c.parentElement.children.filter(x => x !== c); c.parentElement = this;
            this.children.push(c); },
        before(c) { c.parentElement && (c.parentElement.children =
            c.parentElement.children.filter(x => x !== c)); c.parentElement = ACTIONS; },
        addEventListener() {}, matches: () => false };
      if (parent) parent.append(n);
      return n;
    }
    const ACTIONS = node("actions");
    const ELS = {};
    ELS.morebtn = node("morebtn", ACTIONS);
    ELS["pp-craft-g"] = node("pp-craft-g");
    ELS.craftaction = node("craftaction", ELS["pp-craft-g"]);
    ELS["pp-magic-g"] = node("pp-magic-g");
    ELS.spellbtn = node("spellbtn", ELS["pp-magic-g"]);
    ELS.abilities = node("abilities");
    const document = { getElementById: id => ELS[id] || null, querySelector: () => null,
                       querySelectorAll: () => [], addEventListener() {} };
    const window = { addEventListener() {} };
    function onRender() {}
    """
    probe = f"""
    ELS.spellbtn.hidden = {json.dumps(spells_hidden)};
    for (let i = 0; i < {abilities}; i++) ELS.abilities.children.push({{}});
    fitMore();
    const one = {{ craftIn: ELS.craftaction.parentElement.id, more: !ELS.morebtn.hidden,
                   magic: !ELS["pp-magic-g"].hidden }};
    ELS.spellbtn.hidden = false; fitMore();
    one.backIn = ELS.craftaction.parentElement.id;
    console.log(JSON.stringify(one));
    """
    src = prelude + EXITS_JS.read_text(encoding="utf-8") + probe
    out = subprocess.run(["node", "-e", src], capture_output=True, text=True, timeout=60)
    assert out.returncode == 0, out.stderr
    return json.loads(out.stdout.strip().splitlines()[-1])


@pytest.mark.parametrize("spells_hidden,abilities,craft_in,more,magic", [
    (True, 0, "actions", False, False),    # Craft action alone: no one-item menu
    (False, 0, "pp-craft-g", True, True),  # a caster: More holds both
    (True, 2, "pp-craft-g", True, False),  # abilities keep it company; no empty Magic row
])
def test_more_is_never_a_one_item_menu(spells_hidden, abilities, craft_in, more, magic):
    """Discord's users asked why the upload `+` opened a menu holding one item (the critic
    pass on the research): with no spells and no abilities, Craft action stands in More's
    place, and goes back behind More once something else is there."""
    got = _fit(spells_hidden, abilities)
    assert (got["craftIn"], got["more"], got["magic"]) == (craft_in, more, magic)
    assert got["backIn"] == "pp-craft-g"
