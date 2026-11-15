"""Nothing reaches `innerHTML` unescaped unless a person has said why it is safe.

The front end builds its pages as strings. What goes into them is mostly not ours: model
narration and NPC names, World Bible world files, the player's typing and homebrew, and on
a LAN game one player's typing drawn on another's screen. None of the ~400 sinks had ever
been audited when `tools/html_sinks.py` first inventoried them (2026-11-15):

    404 sink sites (`innerHTML =`/`+=`, `outerHTML =`, `insertAdjacentHTML`, ...), 415 raw
    mentions, 1,579 markup builders (templates and `+` chains with tags in them);
    785 interpolated values with no escape and no explanation on the first pass.

Most were engine numbers (hit points, DCs, counts) and engine enum strings, but not all: a
house rule's own pronoun sets went raw into the character forge's gender buttons
(`${g}`), a homebrew race's ability keys and the race builder's catalogue lists
(`${t}`, `${l}`, `cap(t)`) into options and labels, an enchantment question's property
and a seat's id into element ids. The live check found one the review had passed: the
sheet's saving throws went through `stat(sv.name, ...)` raw, three `<img>` elements on
the Sheet tab with poisoned save names. After the fix the inventory reads 2,209 escaped,
854 built from escaped parts, 623 composed, 167 numeric, 144 reviewed, 0 unexplained,
with 347 `esc(` calls added (1,412 before, 1,759 after in the front-end files touched).

`tools/html_sinks_reviewed.json` is the allow-list: each entry names why no outside text
can be in that value (a constant table, the renderer's own geometry, an SVG from our own
static files). This test fails on a new unescaped interpolation, and on a reviewed entry
that no longer matches anything, so the list cannot outlive the code it describes.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _tool():
    spec = importlib.util.spec_from_file_location("html_sinks", ROOT / "tools" / "html_sinks.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules.setdefault("html_sinks", mod)
    spec.loader.exec_module(mod)
    return mod


HS = _tool()
INV = HS.inventory()


def test_every_interpolation_into_markup_is_escaped_or_reviewed():
    raw = [f"{l.file}:{l.line}: {l.text[:100]}  ({l.why})" for l in INV["leaves"] if l.cls == "leaf"]
    assert not raw, ("unescaped text into markup; wrap it in esc() or, if no outside text can "
                     "reach it, add it to tools/html_sinks_reviewed.json with the reason:\n"
                     + "\n".join(raw))


def test_no_review_outlives_the_code_it_describes():
    assert not INV["stale"], INV["stale"]


def test_the_scan_still_sees_the_whole_front_end():
    """A tokenizer that silently stopped reading a file would pass the first test with
    nothing in it. The counts were 404 sinks and 1,579 builders when the audit closed."""
    assert INV["sinks"] >= 380 and INV["builders"] >= 1400, (INV["sinks"], INV["builders"])


def _leaves(js: str):
    """Scan one snippet as if it were a file of the front end."""
    c = HS.Corpus()
    c.add_file("snippet.js", js, [(0, len(js))])
    return [(l.cls, l.text) for l in c.finish()]


def test_the_scanner_catches_the_shape_it_exists_for():
    assert ("leaf", "x.name") in _leaves("el.innerHTML = `<b>${x.name}</b>`;")
    assert ("leaf", "x.name") in _leaves("el.innerHTML = '<b>' + x.name + '</b>';")
    assert ("leaf", "x.name") in _leaves(
        "function row(x) { return `<li>${x.name}</li>`; }\nlist.innerHTML = xs.map(row).join('');")
    # ...and a raw value handed to a sink with no markup around it.
    assert ("leaf", "said") in _leaves("const said = d.text;\nbox.innerHTML = said;")


def test_the_scanner_passes_what_is_safe():
    assert all(c != "leaf" for c, _ in _leaves("el.innerHTML = `<b>${esc(x.name)}</b>`;"))
    # `it.index + 1` is addition: a number, and escaping half of it would have joined "0"+"1".
    assert all(c != "leaf" for c, _ in _leaves("el.innerHTML = `<i>${it.index + 1}</i>`;"))
    # A CSS selector with a value in it is not markup: esc() there would break the selector.
    assert _leaves('box.querySelector(`[data-id="${x.id}"]`).focus();') == []
    # A serialized DOM node is escaped by the browser.
    assert all(c != "leaf" for c, _ in _leaves("el.innerHTML = '<p>' + icon(x).outerHTML + '</p>';"))
