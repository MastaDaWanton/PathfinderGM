"""The combat bar's Declare door (owner ask 2026-11-26 A1: "put the combat declare section
inside a button as well").

Measured on the owner's Shadow save in a fight at 1400x950 before the change: the Declare
block stood 219px tall under the actions, the combat bar 446px in a desk box of 283px, so
the bar scrolled 490px deep. Behind one door the bar is 219px and the box no longer
scrolls. docs/research/2026-11-26-ui-declare-door.md has the sources.
"""
from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PAGE = (ROOT / "play/templates/play/table.html").read_text(encoding="utf-8")
COMBAT_JS = (ROOT / "play/static/js/table/04-combat-and-turns.js").read_text(encoding="utf-8")
EXITS_JS = (ROOT / "play/static/js/table/11-exits.js").read_text(encoding="utf-8")


def _node(src: str) -> dict:
    out = subprocess.run(["node", "-e", src], capture_output=True, text=True, encoding="utf-8", timeout=60)
    assert out.returncode == 0, out.stderr
    return json.loads(out.stdout.strip().splitlines()[-1])


def test_declare_lives_in_a_popover_behind_a_door_in_the_actions_row():
    """The 219px block went behind one labelled door beside the turn's own buttons, and
    nothing of it is left open in the bar."""
    acts = PAGE[PAGE.index('<div class="cb-row cb-acts">'):PAGE.index('id="cb-menu"')]
    door = re.search(r'<button[^>]*id="cb-declbtn"[^>]*>', acts)
    assert door and 'popovertarget="cb-declpop"' in door.group(0)
    pop = acts[acts.index('id="cb-declpop"'):]
    assert 'popover="auto"' in acts[acts.index('id="cb-declpop"') - 40:acts.index('id="cb-declpop"') + 80]
    for i in ('id="cb-declared"', 'data-group="blow"', 'data-group="act"', 'data-group="move"'):
        assert i in pop, i
    assert PAGE.count('id="cb-declared"') == 1
    # The door follows Free… and comes before Commit turn, so Tab walks door -> popover.
    assert acts.index('id="cb-free"') < acts.index('id="cb-declbtn"') < acts.index('id="cb-commit"')


def test_the_rows_rules_do_not_reach_into_the_popover():
    """The popover sits inside the actions row in the DOM; `.cb-acts button` gave every
    option the row's 8px 14px padding and 13px type. The row's rules take its own children."""
    rules = re.findall(r"#combatbar \.cb-acts ([^{]+)\{", PAGE)
    assert len(rules) >= 4
    for rest in rules:
        assert rest.startswith("> "), rest


def _door(opts: list[dict], on: list[str]) -> dict:
    fn = re.search(r"function renderDeclDoor\(opts\) \{.*?\n\}\n", COMBAT_JS, re.S).group(0)
    src = r"""
    const EL = { "#cb-declbtn": { hidden: false, title: "", cls: new Set(),
                   classList: { toggle(c, v) { v ? EL["#cb-declbtn"].cls.add(c)
                                                 : EL["#cb-declbtn"].cls.delete(c); } } },
                 "#cb-decl-n": { textContent: "" } };
    const $ = s => EL[s];
    let closed = 0;
    function closePenPop() { closed++; }
    """ + f"const COMBAT = {{ opts: new Set({json.dumps(on)}) }};\n" + fn + f"""
    renderDeclDoor({json.dumps(opts)});
    const d = EL["#cb-declbtn"];
    console.log(JSON.stringify({{ hidden: d.hidden, label: EL["#cb-decl-n"].textContent,
      on: d.cls.has("on"), title: d.title, closed }}));
    """
    return _node(src)


OPTS = [{"id": "fighting_defensively", "name": "Fight defensively"},
        {"id": "tumble", "name": "Tumble"}, {"id": "charge", "name": "Charge"}]


def test_the_shut_door_names_what_is_declared():
    """Fight defensively is −4 on every blow staged: once the block was behind a door, a
    player who toggled it and closed the popover had nothing on screen saying it was on.
    The door names one, counts more, and wears the gilt border while any is on."""
    assert _door(OPTS, []) == {"hidden": False, "label": "", "on": False,
                               "title": "Feats and manoeuvres declared before the blow",
                               "closed": 0}
    one = _door(OPTS, ["fighting_defensively"])
    assert (one["label"], one["on"], one["title"]) == (
        "· Fight defensively", True, "Declared: Fight defensively")
    two = _door(OPTS, ["fighting_defensively", "tumble"])
    assert (two["label"], two["title"]) == ("· 2 on", "Declared: Fight defensively, Tumble")


def test_no_options_no_door():
    """A door with nothing behind it is not drawn (the clean-composer rule), and an open
    popover folds when its options go."""
    got = _door([], [])
    assert got["hidden"] is True and got["closed"] == 1


def test_a_browser_without_popover_gets_the_old_band_back():
    """Safari before 17 on the LAN has no popover: the door goes, and the Declare band
    stands inline under the actions row, where it was before."""
    prelude = r"""
    function node(id) {
      return { id, attrs: { popover: "auto" }, classes: new Set(), after: null,
        removeAttribute(a) { delete this.attrs[a]; },
        classList: { add(c) { this.owner.classes.add(c); } },
        addEventListener() {}, matches: () => false };
    }
    const POP = node("cb-declpop"); POP.classList.owner = POP;
    const ROW = { after(n) { ROW.placed = n.id; } };
    POP.closest = sel => sel === ".cb-acts" ? ROW : null;
    const DOOR = { removed: false, remove() { DOOR.removed = true; } };
    const document = {
      getElementById: id => id === "cb-declpop" ? POP : null,
      querySelector: s => s === '[popovertarget="cb-declpop"]' ? DOOR : null,
      querySelectorAll: () => [], addEventListener() {} };
    const window = { addEventListener() {} };
    function onRender() {}
    """
    probe = r"""
    console.log(JSON.stringify({ popover: "popover" in POP.attrs, inline: POP.classes.has("inline"),
                                 doorGone: DOOR.removed, placed: ROW.placed || null }));
    """
    got = _node(prelude + EXITS_JS + probe)
    assert got == {"popover": False, "inline": True, "doorGone": True, "placed": "cb-declpop"}
