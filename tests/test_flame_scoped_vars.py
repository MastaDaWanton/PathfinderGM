"""The carried flame writes its CSS variables on the elements that read them, never on <html>
(fix/board-fps, 2026-11-21).

Measured on the owner's save in 0.4.9: one custom property set on the root restyled the whole
document, 12.8 ms a write (1,738 nodes, 2,276 rules, 962 var() uses), and the flame wrote three
a frame. The table sat at 28-40 fps with nothing moving (96-117 with the writes stopped), and
the Region board's 3D map, about 2 ms a frame of its own, ran at 28-35 fps in 0.4.8 and 0.4.9
alike. Scoped to #cursorshade, #cursorlight and the few lit materials, the
same flame costs about 0.3 ms and the Region and the Continent draw at the display's 120 fps.

Each copy of the flame (the table, the home page, the crafting page) is run in node against a
stub document: a hundred frames and a pointer move, and not one variable may land on the root.
"""
import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
COPIES = {
    "table": (ROOT / "play" / "static" / "js" / "table" / "06-trade-and-page.js",
              "// The carried flame.", "// The ember under the cursor."),
    "home": (ROOT / "play" / "templates" / "play" / "home.html", "// The carried flame.", "const TABS = ["),
    "craft": (ROOT / "play" / "templates" / "play" / "craft.html", "// The flame, same two channels", "const STATE = "),
}

STUB = """
const rootWrites = [], elWrites = {};
const el = id => ({ id, style: { setProperty: (k, v) => { (elWrites[id] = elWrites[id] || []).push(k); } } });
const els = { cursorshade: el("cursorshade"), cursorlight: el("cursorlight") }, card = el("card");
let tick = null, move = null;
globalThis.document = {
  documentElement: { style: { setProperty: k => rootWrites.push(k) } },
  getElementById: id => els[id] || null,
  querySelectorAll: () => [card],
  addEventListener: (t, f) => { if (t === "pointermove") move = f; },
};
globalThis.innerWidth = 1500; globalThis.innerHeight = 1000;
globalThis.matchMedia = () => ({ matches: false });
globalThis.requestAnimationFrame = f => { tick = f; };
"""
RUN = """
for (let i = 0; i < 100; i++) tick(i * 16.7);
move({ clientX: 300, clientY: 200 });
console.log(JSON.stringify({ rootWrites, elWrites }));
"""


@pytest.mark.parametrize("copy", sorted(COPIES))
def test_the_flame_never_writes_the_root(copy):
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed; the behaviour check needs a JS engine")
    path, start, end = COPIES[copy]
    src = path.read_text(encoding="utf-8")
    a = src.index(start)
    block = src[a:src.index(end, a)]
    done = subprocess.run([node, "-e", STUB + block + RUN], capture_output=True, text=True, timeout=60)
    assert done.returncode == 0, done.stderr[:2000]
    r = json.loads(done.stdout)
    assert r["rootWrites"] == [], f"{copy}: the flame restyles the whole document a frame: {r['rootWrites'][:6]}"
    # And the flame still burns: the light and the shade get the fast channel and the pointer.
    for id_ in ("cursorshade", "cursorlight"):
        assert {"--flick", "--jx", "--jy", "--cx", "--cy"} <= set(r["elWrites"].get(id_, [])), (copy, id_, r)
    if copy != "craft":   # the slow channel's materials (craft has none)
        assert {"--flicks", "--sdx", "--sdy"} <= set(r["elWrites"].get("card", [])), (copy, r)
