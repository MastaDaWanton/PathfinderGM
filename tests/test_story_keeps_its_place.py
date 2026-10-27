"""After a turn the story pane shows the new turn, however long the game has run.

The owner, 2026-10-27: "once the narration goes a few turns When a turn finishes instead of
putting you at the bottom so you can read the new turn it jumps you up for some reason and
you have to scroll down to the new turn."

Measured on the owner's own save (92 beats, 24 of them the narrator's with a "That's wrong"
line under them) at 1366x900: the pane sat at its foot, scrollTop 13689 of 13689. A turn's
draw left it at 13001, 688px up, with the new beats wholly below the pane (the player's line
1192px under its top). render() rebuilds the story with every "That's wrong" slot empty;
23-thats-wrong.js fills them in a render hook AFTER the book's landing hook. In between, the
story is 24 slots (28.7px each) shorter, the browser clamps scrollTop to the shorter foot,
and the landing read the clamped 13001 as a reader who had scrolled back to reread
(13001 < 13689 - 24), so it left the page there. Then the slots filled and the content
grew back above it. The jump is one slot's height per narrated beat, so it grows with the
game: under a turn, unnoticed; a few turns in, the whole new turn is below the pane.

Fixed in 15-book.js: render() tells the book where the reader was before it rebuilds
(`storyKeep`), the reread test reads that, and the landing is made again once every hook
has drawn (a microtask after render), with the slots watched as the beats are.
"""
from __future__ import annotations

import json
import shutil
import subprocess

import pytest

from pagesource import TABLE_SCRIPTS

BOOK = TABLE_SCRIPTS / "15-book.js"
STATE_JS = TABLE_SCRIPTS / "02-state.js"

# A story whose layout is worked out from its parts, with a browser's clamp: scrollTop can
# never be more than scrollHeight - clientHeight, read or written. Each turn is the player's
# line, a narrated beat, and the "That's wrong" slot under it, empty (0px) until painted.
_STUB = r"""
function onRender() {}
const PAD = 22, FOOT = 26, SLOT = 29;
const parts = [];                               // {kind: "beat"|"slot", h, filled}
const story = { id: "story", clientHeight: 587, _top: 0, addEventListener() {},
  style: { overflowY: "auto", paddingTop: PAD + "px" },
  get scrollHeight() { return PAD + parts.reduce((n, p) => n + height(p), 0) + FOOT; },
  get scrollTop() { return Math.max(0, Math.min(this._top, this.scrollHeight - this.clientHeight)); },
  set scrollTop(v) { this._top = Math.max(0, Math.min(v, this.scrollHeight - this.clientHeight)); },
  querySelectorAll: sel => sel === ".beat" ? beatEls() : parts };
function height(p) { return p.kind === "slot" ? (p.filled ? SLOT : 0) : p.h; }
function offsetOf(p) { let y = PAD; for (const q of parts) { if (q === p) return y; y += height(q); } }
function beatEls() { return parts.filter(p => p.kind === "beat").map(p => ({ get offsetTop() { return offsetOf(p); } })); }
const leaf = { id: "bookin", scrollTop: 0, addEventListener() {}, style: { overflowY: "auto" } };
const document = {
  getElementById: id => ({ story, bookin: leaf })[id] || null,
  querySelector: () => null, querySelectorAll: () => [], addEventListener() {}, fonts: null,
};
const getComputedStyle = el => el.style;
class ResizeObserver { constructor(fn) { this.fn = fn; } observe() {} disconnect() {} }
const window = {};

// The game so far, and a turn as render() draws it: the slots emptied by the rebuild, the
// book's hook, then 23-thats-wrong.js's hook filling every slot, then whatever runs after.
let n = 0;
const T = () => ({ transcript: Array.from({ length: n }, (_, i) => ({ text: "b" + i })) });
function addTurn(reply) {
  parts.push({ kind: "beat", h: 40 }); n++;
  parts.push({ kind: "beat", h: reply }); n++;
  parts.push({ kind: "slot", filled: false });
}
function draw(prev, more) {
  if (typeof storyKeep === "function") storyKeep();
  parts.forEach(p => { if (p.kind === "slot") p.filled = false; });   // innerHTML rebuilt
  if (more) more();
  storyLand(T(), prev);
  parts.forEach(p => { if (p.kind === "slot") p.filled = true; });    // the later hook
}
const settle = () => new Promise(r => setTimeout(r, 0));
const at = () => story.scrollTop, foot = () => story.scrollHeight - story.clientHeight;
const firstNewFromTop = k => beatEls()[k].offsetTop - PAD - story.scrollTop;
"""


def _run(tmp_path, body: str) -> dict:
    src = _STUB + BOOK.read_text(encoding="utf-8") + "\n(async () => {\n" + body + "\n})();"
    f = tmp_path / "story_place.js"
    f.write_text(src, encoding="utf-8")
    done = subprocess.run([shutil.which("node"), str(f)], capture_output=True, text=True,
                          timeout=30)
    assert done.returncode == 0, done.stderr[:2000]
    return json.loads(done.stdout.strip().splitlines()[-1])


@pytest.mark.skipif(shutil.which("node") is None, reason="node is not on this machine")
def test_a_turn_late_in_a_game_shows_the_new_turn_not_a_page_up(tmp_path):
    """Twenty-four narrated turns in (the owner's save), the reader at the foot: a short
    turn ends at the foot (it fits the pane), a long one with its first line at the top of
    the pane. Before the fix both were left 24 x 29 = 696px up, the new turn out of sight."""
    got = _run(tmp_path, r"""
    for (let i = 0; i < 24; i++) addTurn(200);
    draw(null); await settle();
    const out = { load: foot() - at() };
    let prev = T(); let k = n;
    draw(prev, () => addTurn(180)); await settle();           // fits the pane
    out.short = { fromFoot: foot() - at(), firstNew: firstNewFromTop(k) };
    prev = T(); k = n;
    draw(prev, () => addTurn(1400)); await settle();          // taller than the pane
    out.long = { fromFoot: foot() - at(), firstNew: firstNewFromTop(k) };
    console.log(JSON.stringify(out));""")
    assert got["load"] == 0, got
    assert got["short"]["fromFoot"] == 0, f"a turn that fits did not end at the foot: {got}"
    assert got["long"]["firstNew"] == 0, f"a long turn did not open at its first line: {got}"


@pytest.mark.skipif(shutil.which("node") is None, reason="node is not on this machine")
def test_a_rereader_and_a_redraw_with_nothing_new_keep_their_place(tmp_path):
    """The rebuild's clamp moved more than the landing. A reader near the foot who had
    scrolled up a little, and a redraw that brings nothing new (a resync, a correction
    marked), were both pulled up by the slots' height. The reader stays exactly where they
    were; a page held at its landing lands again."""
    got = _run(tmp_path, r"""
    for (let i = 0; i < 24; i++) addTurn(200);
    draw(null); await settle();
    const out = {};
    draw(T()); await settle();                                // nothing new, at the foot
    out.resync = foot() - at();
    story.scrollTop = foot() - 300;                           // read back a little
    STORY.holding = false;                                    // their own wheel let go
    const was = at();
    draw(T()); await settle();
    out.resyncReader = at() - was;
    const prev = T();
    draw(prev, () => addTurn(200)); await settle();           // a turn while rereading
    out.turnReader = at() - was;
    console.log(JSON.stringify(out));""")
    assert got == {"resync": 0, "resyncReader": 0, "turnReader": 0}, got


def test_render_tells_the_book_where_the_reader_was_before_it_rebuilds():
    """The keep has to be read before `#story`'s innerHTML is replaced: after it, the
    browser has already clamped the position."""
    src = STATE_JS.read_text(encoding="utf-8")
    keep = src.index('if (typeof storyKeep === "function") storyKeep();')
    assert keep < src.index('$("#story").innerHTML = s.transcript.map(')
    book = BOOK.read_text(encoding="utf-8")
    assert "queueMicrotask" in book and ".beatfix" in book
