"""The character sheet's Spells page, after the owner's mockup (Phase 3 task I5, 2026-09-29).

Three columns: caster stats with the slots drawn as gem sockets, "Prepared today" as spell
cards, and the "Grimoire index" (search, sort, school filter, drag a row in to prepare it).
Art is game-icons.net under CC BY 3.0, stored in `play/static/icons/spells/`.

The tab is rendered here by running `tabSpells` from 05-sheet.js in node against a real
`full_sheet` spells block, then parsed. What node cannot hold (drag and drop with a real
pointer, the redraw keeping its scroll, focus rings, 375px) was driven in the browser
against a live server; the task report has the numbers.

Defects these record, each measured before it was fixed:

  * The Cast button carries `prepbtn` (02-state.js and test_cast_outside_combat find it
    that way), and the old delegated `.prepbtn` click sent it to `/api/spells/prepare`
    with no action. The server reads a missing action as "prepare": a POST with none
    took Sleep from 0 prepared to 1. So every Cast press also prepared the spell again,
    or, with the level full, threw an alert over the chip it had just attached.
  * The brief called cantrips "castable at will"; the engine spent a level-0 slot per
    cast. A level 5 wizard casting Light read 4, 3, 2, 1, 0 slots and the fifth was
    refused. The first build of this page said "each cast spends a cantrip slot"; the
    ENGINE was the one that was wrong (AoN, Wizard: cantrips "are not expended when
    cast"), and since the 2026-09-29 fix the page shows prepared cantrips as at will.
  * At 375px the sheet's one grid column took the header's 414px minimum, and the gilt
    clasps hang 34px outside every card: the tab scrolled 17px sideways. The phone rules
    hold the body to the screen and clip the ornament.
  * 10-spells.js styles `.sp-note` and `.sp-levelhead` for its picker, globally and later
    in the sheet; this tab's first build used the same names and wore the picker's
    underline on its level headings. The tab's classes are `sx-*`.
  * The owner's addition (2026-09-29): "the spell cards need a button to see ... the
    description of what the spell does". One popover, from `GET /api/spells/<id>`.
    Opened from Magic Missile, switched to Daze, shut with Close: the browser's own
    focus restore put focus on Magic Missile. The page returns it to Daze itself.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
from html.parser import HTMLParser
from pathlib import Path

import pytest

from pagesource import ROOT, TABLE, TABLE_SCRIPTS

ICONS = ROOT / "play" / "static" / "icons" / "spells"
SHEET_JS = TABLE_SCRIPTS / "05-sheet.js"
MANUAL = ROOT / "play" / "templates" / "play" / "manual.html"


def _sheet_js() -> str:
    return SHEET_JS.read_text(encoding="utf-8")


def _spells_region() -> str:
    src = _sheet_js()
    return src[src.index("// --- Spells ---"):src.index("// --- Equipment ---")]


def _css() -> str:
    src = TABLE.read_text(encoding="utf-8")
    return src[src.index("<style>"):src.index("</style>")]


# A browser's worth of globals for the spells region alone: nothing in it reaches the
# network or the DOM at render time except these.
_STUBS = r"""
const esc = s => String(s == null ? "" : s).replace(/[&<>"]/g,
  c => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;"}[c]));
const tabEmpty = msg => `<div class="empty">${esc(msg)}</div>`;
const document = { querySelector: () => null, querySelectorAll: () => [],
                   addEventListener: () => {} };
const $ = () => ({});
class MutationObserver { constructor() {} observe() {} }
const CSS = { escape: s => s };
let SHEET = null, STATE = null;
"""


def _wizard_spells() -> dict:
    """A level 5 wizard's own `/api/sheet` spells block, built the way the view builds it."""
    from rules import casting
    from rules.sheet import full_sheet
    from test_casting_executes import wizard

    book = ("acid-splash", "light", "daze", "magic-missile", "burning-hands", "shield",
            "sleep", "mage-armor", "invisibility", "web", "fireball", "haste")
    # Two of the three cantrips prepared, Daze left in the book: cantrips are prepared
    # like any spell and cast at will (2026-09-29, tests/test_cantrips_at_will.py).
    pc = wizard(level=5, book=book, prepared={"magic-missile": 2, "shield": 1,
                                              "invisibility": 1, "fireball": 1,
                                              "acid-splash": 1, "light": 1})
    casting.define_slots(pc)
    return full_sheet(pc)["spells"]


def _render(spells: dict, tmp_path, extra: str = "") -> dict:
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    src = (_STUBS + _spells_region() + f"\nconst SP = {json.dumps(spells)};\n"
           + "const out = { html: tabSpells({ spells: SP, identity: { name: 'Maelis' } }) };\n"
           + extra + "\nconsole.log(JSON.stringify(out));\n")
    f = tmp_path / "spells.js"
    f.write_text(src, encoding="utf-8")
    done = subprocess.run([node, str(f)], capture_output=True, text=True, timeout=30)
    assert done.returncode == 0, done.stderr
    return json.loads(done.stdout.strip().splitlines()[-1])


class _Tree(HTMLParser):
    VOID = {"input", "br", "img", "meta", "link", "hr"}

    def __init__(self):
        super().__init__()
        self.elements, self.stack = [], []

    def handle_starttag(self, tag, attrs):
        el = {"tag": tag, "attrs": dict(attrs), "text": "", "ancestors": list(self.stack)}
        self.elements.append(el)
        if tag not in self.VOID:
            self.stack.append(el)

    def handle_endtag(self, tag):
        for i in range(len(self.stack) - 1, -1, -1):
            if self.stack[i]["tag"] == tag:
                del self.stack[i:]
                break

    def handle_data(self, data):
        for el in self.stack:
            el["text"] += data


def _tree(html: str) -> list[dict]:
    t = _Tree()
    t.feed(html)
    return t.elements


@pytest.fixture(scope="module")
def spells():
    return _wizard_spells()


def test_the_three_columns_are_there_in_the_mockups_order(spells, tmp_path):
    """The owner's mockup: caster stats on the left, prepared today in the middle, the
    grimoire index on the right, in that source order so a phone stacks them the same."""
    els = _tree(_render(spells, tmp_path)["html"])
    sections = [e for e in els if e["tag"] == "section"]
    assert [s["attrs"]["class"] for s in sections] == [
        "card sx-stats", "card sx-today", "card sx-index"]
    heads = [e["text"].strip() for e in els if e["tag"] == "h3"]
    assert heads == ["Caster stats", "Prepared today", "Grimoire index"]
    # The drop target is the middle column, and it prepares.
    today = sections[1]
    assert today["attrs"]["id"] == "sx-today" and today["attrs"]["data-drop"] == "prepare"


def test_the_slots_are_gem_sockets_lit_while_they_last(spells, tmp_path):
    """One socket per slot, in three states since 2026-09-29, and the count in words beside
    them so colour is never the only way to read it.

    This pinned two states (lit = left, dark = spent) until the owner's Ysolde screenshot
    of 2026-09-29: a slot spent today and a slot open for preparing both drew dark, and
    the tab read "1 of 2 left" while that one slot was already full. Now lit = a prepared
    spell waiting, red (`spent`) = cast today, dark = open; the words say "N ready, N
    spent, N open" (tests/test_spells_prepare_midday.py drives the spent case).

    The cantrip row is the exception: a cantrip is "not expended when cast" (AoN,
    Wizard), so its gems are the cantrips PREPARED today (two of four here) and the words
    say at will. It read "4 of 4 left" and drained per cast before."""
    els = _tree(_render(spells, tmp_path)["html"])
    levels = [e for e in els if e["attrs"].get("class") == "sock-level"]
    assert len(levels) == len(spells["slots"])
    held = len([k for k in spells["known"] if k.get("level") == 0 and k["prepared"]])
    assert held == 2
    for lvl, slot in zip(levels, spells["slots"]):
        gems = [e for e in els if lvl in e["ancestors"] and e["tag"] == "i"
                and "gem" in e["attrs"].get("class", "")]
        lit = [g for g in gems if "lit" in g["attrs"]["class"].split()]
        assert f"DC {slot['dc']}" in lvl["text"]
        if slot["level"] == 0:
            assert len(gems) == slot["max"] and len(lit) == held
            assert f"{held} of {slot['max']} prepared, at will" in lvl["text"]
            assert "left" not in lvl["text"]
            continue
        spent = [g for g in gems if "spent" in g["attrs"]["class"].split()]
        ready = min(slot["held"], slot["left"])
        assert len(gems) == slot["max"] and len(lit) == ready
        assert len(spent) == slot["max"] - slot["left"]
        assert (f"{ready} ready, {slot['max'] - slot['left']} spent, "
                f"{slot['left'] - ready} open") in lvl["text"]


def test_prepared_spells_are_cards_with_the_strip_and_both_buttons(spells, tmp_path):
    """One card per prepared spell of level 1 and up; each has the school's colour, a
    glyph, the Range / middle / Save strip, its own prepared count, Cast and Prepare.

    Each card carried "N of M level X slots left" as well until 2026-09-29, so Ysolde's
    two level 1 cards each read "1 of 2 level 1 slots left" and looked like two free
    slots; the count is the level header's now, once (test_spells_prepare_midday.py)."""
    els = _tree(_render(spells, tmp_path)["html"])
    cards = [e for e in els if e["tag"] == "article"]
    want = {k["name"] for k in spells["known"] if k.get("level", 0) and k["prepared"]}
    assert {c["attrs"]["aria-label"] for c in cards} == want
    for c in cards:
        assert re.match(r"--school: var\(--sc-[a-z]+\)", c["attrs"]["style"])
        inside = [e for e in els if c in e["ancestors"]]
        assert [e["text"] for e in inside if e["tag"] == "dt"][0::2] == ["Range", "Save"]
        labels = [e["text"].strip() for e in inside if e["tag"] == "button"]
        assert labels[:2] == ["Cast", "Prepare"]
        assert "prepared" in c["text"] and "slots left" not in c["text"]


def test_cast_attaches_and_never_prepares(spells, tmp_path):
    """Cast keeps the exact class 02-state.js's attach handler and its tests look for,
    and carries no `data-action`; the prepare handler now requires one. Measured before
    the fix: a POST with no action prepared Sleep from 0 to 1."""
    els = _tree(_render(spells, tmp_path)["html"])
    casts = [e for e in els if e["tag"] == "button" and "castbtn" in e["attrs"].get("class", "")]
    assert casts
    for b in casts:
        assert b["attrs"]["class"] == "prepbtn castbtn"
        assert "data-action" not in b["attrs"] and b["attrs"].get("data-name")
    handler = _sheet_js()
    assert '#sheetbody [data-spell][data-action]' in handler
    assert 'e.target.closest(".prepbtn");' not in handler
    # The attach itself stays where it is: 02-state.js, calling 10-spells.js's chip.
    state = (TABLE_SCRIPTS / "02-state.js").read_text(encoding="utf-8")
    assert "attachSpell({ id: cast.dataset.spell" in state


def test_prepared_cantrips_are_at_will_and_the_rest_are_prepared_first(spells, tmp_path):
    """AoN, Wizard: wizards "can prepare a number of cantrips, or 0-level spells, each
    day" and those "are not expended when cast and may be used again".

    This test pinned the opposite until 2026-09-29 ("the page does not promise at
    will"): the engine then skipped the prepared check at level 0 and spent a level-0
    slot per cast — a level 5 wizard's Light went 4, 3, 2, 1, 0 and was refused. Both
    halves were wrong. Now the middle column lists only the PREPARED cantrips, each with
    Cast and Unprepare, under a line saying at will; the unprepared one (Daze) is offered
    in the grimoire with Prepare and can be dragged, like any other spell."""
    html = _render(spells, tmp_path)["html"]
    els = _tree(html)
    rows = [e for e in els if e["attrs"].get("class") == "sx-cantrip"]
    casts = [e for r in rows for e in els if r in e["ancestors"]
             and "castbtn" in e["attrs"].get("class", "")]
    assert {b["attrs"]["data-spell"] for b in casts} == {"acid-splash", "light"}
    for r in rows:
        buttons = [e for e in els if r in e["ancestors"] and e["tag"] == "button"]
        assert [b["text"].strip() for b in buttons] == ["Details", "Cast", "Unprepare"]
    assert "At will: casting one spends nothing." in html
    assert "2 of 4 prepared today" in html
    assert "spends a cantrip slot" not in html
    grim = {e["attrs"]["data-spell"]: e for e in els if e["attrs"].get("class") == "gx-row"}

    def acts(row):
        return [e["text"].strip() for e in els if row in e["ancestors"]
                and e["tag"] == "button" and e["text"].strip() != "Details"]

    for sid in ("acid-splash", "light"):
        assert acts(grim[sid]) == ["Cast"] and "draggable" not in grim[sid]["attrs"]
    assert acts(grim["daze"]) == ["Prepare"] and grim["daze"]["attrs"]["draggable"] == "true"


def test_every_button_and_field_has_a_name(spells, tmp_path):
    """A visible word on every button, with an accessible name that contains it (WCAG
    2.5.3: "Prepare Fireball" for a button reading Prepare), and a visible label on the
    search, the sort and the school filter."""
    els = _tree(_render(spells, tmp_path)["html"])
    buttons = [e for e in els if e["tag"] == "button"]
    assert buttons
    for b in buttons:
        text = b["text"].strip()
        assert text, b
        name = b["attrs"].get("aria-label", text)
        assert name.startswith(text), (name, text)
    for id_ in ("spellfind", "spellsort", "spellschool"):
        field = [e for e in els if e["attrs"].get("id") == id_]
        assert len(field) == 1
        assert any(a["tag"] == "label" and a["text"].strip() for a in field[0]["ancestors"])


def test_every_grimoire_row_offers_the_keyboard_way_in(spells, tmp_path):
    """Dragging is the mockup's gesture; a keyboard or a touch screen has none, so every
    draggable row carries its own Prepare button that does the same thing."""
    els = _tree(_render(spells, tmp_path)["html"])
    rows = [e for e in els if e["attrs"].get("class") == "gx-row"]
    total = sum(len(g["spells"]) for g in spells["choose_from"])
    assert len(rows) == total
    for r in rows:
        if r["attrs"].get("draggable") == "true":
            prep = [e for e in els if r in e["ancestors"] and e["tag"] == "button"
                    and e["attrs"].get("data-action") == "prepare"]
            assert len(prep) == 1 and prep[0]["attrs"]["data-spell"] == r["attrs"]["data-spell"]


def test_search_sort_and_school_filter(spells, tmp_path):
    """The three tools the mockup asks for, run against the real list."""
    extra = """
    SHEET = { spells: SP };
    const names = () => [...grimoireList(SP).matchAll(/data-spell="([^"]+)" data-name/g)].map(m => m[1]);
    SPELL_FIND = "fire"; out.find = names(); SPELL_FIND = "";
    SPELL_SCHOOL = "illusion"; out.school = names(); SPELL_SCHOOL = "";
    SPELL_SORT = "level-desc"; out.desc = names().slice(0, 2);
    SPELL_SORT = "name"; out.name = names().slice(0, 3); SPELL_SORT = "level";
    out.words = [plainMeasure("minutes/level (10)"), plainMeasure("rounds (1)"),
                 plainMeasure("feet (60)"), rangeShort("close (25 feet + 5 feet/2 levels)"),
                 rangePhrase("medium (100 feet + 10 feet/level)"), saveShort("")];
    """
    got = _render(spells, tmp_path, extra)
    assert got["find"] == ["fireball"]
    assert set(got["school"]) == {"invisibility"}
    assert got["desc"] == ["fireball", "haste"]
    assert got["name"] == ["acid-splash", "burning-hands", "daze"]
    assert got["words"] == ["10 minutes per level", "1 round", "60 ft", "Close",
                            "medium range", "None"]


def test_no_new_windows_and_no_dashes_or_arrows_in_the_words(spells, tmp_path):
    """The owner's copy rules: plain sentence-case labels, no em or en dashes and no
    arrows in UI text. And nothing opens a window by script: links use target=_blank,
    which the packaged app hands to the system browser (electron/main.js)."""
    region = _spells_region()
    assert "window.open" not in region
    html = _render(spells, tmp_path)["html"]
    text = re.sub(r"<[^>]+>", " ", html)
    for ch in ("—", "–", "→", "←", "⇒", "->"):
        assert ch not in text, ch


def test_the_table_scripts_share_one_scope_without_a_clash(tmp_path):
    """The ten table scripts are classic scripts in one global scope, so a top-level name
    declared twice is a SyntaxError that kills the LATER file whole. Measured in the
    browser during this task: a `capFirst` helper here collided with 08-conversation.js's
    and the conversation script never ran ("Identifier 'capFirst' has already been
    declared"), while the Spells tab itself looked fine. Parsed as one text, the way the
    browser meets them."""
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    f = tmp_path / "all.js"
    f.write_text("\n;\n".join(p.read_text(encoding="utf-8")
                              for p in sorted(TABLE_SCRIPTS.glob("*.js"))), encoding="utf-8")
    done = subprocess.run([node, "--check", str(f)], capture_output=True, text=True,
                          timeout=30)
    assert done.returncode == 0, done.stderr


def test_every_icon_the_page_can_ask_for_is_on_disk():
    """Each school's sigil and each spell's own icon, named in 05-sheet.js, exists under
    play/static/icons/spells/, recoloured (no black square, fill currentColor)."""
    region = _spells_region()
    names = set(re.findall(r'"((?:lorc|delapouite|sbed|skoll)-[a-z0-9-]+)"', region))
    assert len(names) >= 9 + 20
    for n in names:
        f = ICONS / f"{n}.svg"
        assert f.is_file(), n
        svg = f.read_text(encoding="utf-8")
        assert 'fill="currentColor"' in svg and 'M0 0h512v512H0z' not in svg, n
    schools = re.search(r"const SPELL_SCHOOLS = \{(.*?)\n\};", region, re.S).group(1)
    for school in ("abjuration", "conjuration", "divination", "enchantment", "evocation",
                   "illusion", "necromancy", "transmutation", "universal"):
        assert f"{school}:" in schools
        assert f"--sc-{school}:" in _css()


def test_the_attribution_names_every_author_and_the_licence():
    """CC BY 3.0: the authors, the licence and a note of changes, where the work is used.
    CREDITS.txt lists every file by its author; the manual's licence footer, the
    Background tab's licence note and the grimoire's foot all carry the line."""
    credits = (ICONS / "CREDITS.txt").read_text(encoding="utf-8")
    assert "CC BY 3.0" in credits and "creativecommons.org/licenses/by/3.0" in credits
    assert "background square" in credits
    for f in ICONS.glob("*.svg"):
        assert f.name in credits, f.name
        author = f.name.split("-", 1)[0]
        section = credits[credits.index(f"By {author.capitalize()}"):]
        assert f.name in section.split("\n\n", 1)[0], f.name
    manual = MANUAL.read_text(encoding="utf-8")
    for who in ("Lorc", "Delapouite", "Sbed", "Skoll"):
        assert who in manual
    assert "game-icons.net" in manual and "icons/spells/CREDITS.txt" in manual
    js = _sheet_js()
    assert js.count("${spellIconCredit()}") == 2


def test_the_motion_rule_and_the_phone(spells):
    """Owner, 2026-09-28: nothing slower than about 150ms, nothing that loops, nothing
    that moves under the pointer. And at 375px one column, 16px gutters, and none of
    the 17px of sideways scroll the clasps caused."""
    css = _css()
    region = css[css.index("/* --- The Spells tab"):css.index("#featq {")]
    assert "animation" not in region and "@keyframes" not in region
    assert "transform" not in region
    for dur in re.findall(r"transition-duration:\s*([.\d]+)s", region):
        assert float(dur) <= .15
    phone = css[css.index("#sheetbody:has(> .spells3) { padding"):]
    phone = phone[:phone.index("}\n  }") + 1]
    assert "padding: 18px 16px 60px" in phone
    assert "width: 100vw" in phone and "overflow-x: hidden" in phone
    assert ".spells3 { grid-template-columns: minmax(0, 1fr)" in phone
    # The status line keeps its height, so a message cannot push the cards down.
    assert re.search(r"\.sx-say \{[^}]*min-height", region)


# --- the owner's addition: what the spell does ---------------------------------------------

def test_every_spell_has_a_details_button(spells, tmp_path):
    """Owner, 2026-09-29: a button on every spell card, and on each grimoire row, that
    shows what the spell does. Labelled "Details" in plain words, a disclosure
    (`aria-expanded`, `aria-controls` naming the one popover), and never mistaken for a
    prepare button (no `data-action`)."""
    els = _tree(_render(spells, tmp_path)["html"])

    def details_in(container):
        return [e for e in els if container in e["ancestors"] and e["tag"] == "button"
                and "sx-details" in e["attrs"].get("class", "").split()]

    holders = ([e for e in els if e["tag"] == "article"]
               + [e for e in els if e["attrs"].get("class") in ("gx-row", "sx-cantrip")])
    # 4 cards, 2 prepared cantrip rows (Daze is in the book, not prepared: cantrips are
    # prepared since 2026-09-29), 12 grimoire rows for this wizard.
    assert len(holders) == 4 + 2 + 12
    for h in holders:
        found = details_in(h)
        assert len(found) == 1, h["attrs"]
        b = found[0]
        assert b["text"].strip() == "Details"
        assert b["attrs"]["aria-expanded"] == "false"
        assert b["attrs"]["aria-controls"] == "spelldetail"
        assert b["attrs"]["aria-label"].startswith("Details: ")
        assert "data-action" not in b["attrs"] and "data-spell" not in b["attrs"]


def test_the_details_are_the_catalogues_own_text(tmp_path):
    """Read from the existing `GET /api/spells/<id>` (home_views.spell_detail), not a new
    field: the popover shows the casting time the sheet does not carry, the other facts,
    and the description, escaped."""
    from rules import spells as spells_mod

    region = _spells_region()
    assert "fetch(`/api/spells/${encodeURIComponent(id)}`)" in region
    d = spells_mod.get("magic-missile").as_dict()
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    src = (_STUBS + region + f"\nconst D = {json.dumps(d)};\n"
           + "SHEET = { spells: { known: [{ id: 'magic-missile', level: 1 }] } };\n"
           + "console.log(JSON.stringify({ html: detailHtml('magic-missile', 'Magic Missile', D),"
           + " wait: detailHtml('x', 'X', undefined) }));\n")
    f = tmp_path / "detail.js"
    f.write_text(src, encoding="utf-8")
    done = subprocess.run([node, str(f)], capture_output=True, text=True, timeout=30)
    assert done.returncode == 0, done.stderr
    got = json.loads(done.stdout.strip().splitlines()[-1])
    html = got["html"]
    assert 'id="spelldetail-h">Magic Missile</h4>' in html
    for fact in ("<dt>Level</dt><dd>1</dd>", "<dt>Casting time</dt><dd>Standard action</dd>",
                 "<dt>Spell resistance</dt><dd>Yes</dd>"):
        assert fact in html
    assert "A missile of magical energy darts forth" in html
    assert "Reading the spell." in got["wait"]


def test_esc_shuts_the_details_first_and_gives_focus_back(tmp_path):
    """One Esc, one layer: with the details open, Esc closes them and the sheet stays;
    the next Esc closes the sheet. Focus returns to the button on Esc, Close and the
    same button, and is left alone by a click elsewhere (the browser's light dismiss)."""
    js = _sheet_js()
    esc = js[js.index('document.addEventListener("keydown", e => {\n  if (e.key !== "Escape")'):]
    esc = esc[:esc.index("\n});")]
    assert esc.index("detailOpen()") < esc.index("closeSheet()")
    assert "closeDetail(true)" in esc and "e.preventDefault()" in esc
    closed = js[js.index("function detailClosed()"):]
    closed = closed[:closed.index("\n}")]
    assert "SPELL_DETAIL.returnFocus === true" in closed and "b.focus(" in closed
    # Shown over the page, not inside a card: nothing below it moves.
    assert "document.body.appendChild(p)" in js
    css = _css()
    pop = css[css.index("#spelldetail {\n    position"):]
    pop = pop[:pop.index("}")]
    assert "position: fixed" in pop and "overflow-y: auto" in pop
    assert "calc(100vw - 24px)" in pop
