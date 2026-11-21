"""The tabletop's grain (play/static/js/places-board.js, owner 2026-11-21: "the colors on the
3d tabletop maps are too smooth and need a bit of texture").

One noise tile, made in code, laid in world space over the painted pieces, the Kenney hexes and
the nation plates, on the Continent and the Region (the 12-mile hex map, level "nation") only.
What these hold, each a way it could go wrong:

- the tile is made ONCE and reused: a board is rebuilt on every move, and a 128px tile made per
  build (or, worse, per frame) is the kind of cost that only shows on the owner's laptop;
- the tile tiles: the board samples it with RepeatWrapping every 4 table units, and a tile
  whose edges do not meet draws a grid of seams across every hex;
- it is subtle: the owner asked for "a bit". Measured while building it: one tile per 7 units
  left a miniature (about 3 across) inside a single blotch, as smooth as before; at 4 units a
  piece shows a few. The spread below is what keeps it a bit;
- fog, haze, reach rings and names are never grained: what is known and what can be pressed
  must read exactly as before.
"""
import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
BOARD_JS = ROOT / "play" / "static" / "js" / "places-board.js"


def _src():
    return BOARD_JS.read_text(encoding="utf-8")


def _function(src, name):
    """The text of a top-level `function name(...) { ... }`, by brace counting."""
    start = src.index(f"function {name}(")
    depth, i = 0, src.index("{", start)
    while True:
        if src[i] == "{":
            depth += 1
        elif src[i] == "}":
            depth -= 1
            if depth == 0:
                return src[start:i + 1]
        i += 1


def test_the_tile_is_made_once_and_cached():
    src = _src()
    assert src.count("new THREE.DataTexture(") == 1, "one place makes the grain tile"
    body = _function(src, "grainTexture")
    assert body.splitlines()[1].strip().startswith("if (GRAIN) return GRAIN"), \
        "grainTexture returns the cached tile before making anything"
    assert "grainData(" not in _function(src, "frame"), "nothing about the grain is made per frame"
    assert "grainTexture(" not in _function(src, "frame")
    # clear() disposes a material's own `map`; the grain is a uniform, never a map, so a
    # rebuilt board cannot dispose the shared tile out from under the next one.
    assert "map: grainTexture" not in src and "map: GRAIN" not in src


def test_only_the_continent_and_the_region_are_grained():
    """The owner, 2026-11-21: the grain is for the continental and regional maps. The first
    build grained every level (World, Town and Site too). The materials are shared by every
    level, so one uniform switches it, set when a board is built."""
    src = _src()
    assert 'GRAIN_LEVELS = new Set(["nation", "continent"])' in src
    draw = _function(src, "draw")
    built = draw.index("clear();")
    assert "GRAIN_ON.value = GRAIN_LEVELS.has(level)" in draw[built:built + 200], \
        "switched with the board it belongs to, right after the old one is cleared"
    assert "if (grainOn > .5)" in _function(src, "grained"), "the other levels skip the fetches"


def test_the_right_surfaces_are_grained():
    src = _src()
    assert re.search(r"const mat = .*grained\(new THREE\.MeshStandardMaterial", src), "painted pieces"
    assert re.search(r"const PRIMER = grained\(", src), "grey primer"
    assert "grained(m.material)" in _function(src, "loadKit"), "Kenney hexes and buildings"
    hb = _function(src, "hexBoard")
    plates = next(l for l in hb.splitlines() if "opacity: +op" in l)
    assert "grained(" in plates, "nation plates: most of what the Region and Continent show"
    # The unknown (cloud puffs), seen-but-unsearched haze and the reach rings stay plain.
    for marker in ("puffs.length", "color: 0xf4ecd6", "color: 0xe8c25a"):
        line = next(l for l in hb.splitlines() if marker in l and "InstancedMesh" in l)
        assert "grained(" not in line, f"{marker} must stay ungrained"
    assert "grained(" not in _function(src, "flatName")


def test_the_tile_tiles_and_stays_subtle():
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed; the behaviour check needs a JS engine")
    fn = _function(_src(), "grainData")
    script = fn + """
const n = 128, a = grainData(n), b = grainData(n);
const same = a.every((v, k) => v === b[k]);
let wrap = 0, inner = 0, sum = 0, sq = 0;
for (let y = 0; y < n; y++) {
  wrap += Math.abs(a[y * n + n - 1] - a[y * n]) + Math.abs(a[(n - 1) * n + y] - a[y]);
  inner += Math.abs(a[y * n + 63] - a[y * n + 64]) + Math.abs(a[63 * n + y] - a[64 * n + y]);
}
a.forEach(v => { sum += v; sq += v * v; });
const mean = sum / a.length, sd = Math.sqrt(sq / a.length - mean * mean);
console.log(JSON.stringify({ same, wrap: wrap / (2 * n), inner: inner / (2 * n), mean, sd,
  min: Math.min(...a), max: Math.max(...a) }));
"""
    done = subprocess.run([node, "-e", script], capture_output=True, text=True, timeout=60)
    assert done.returncode == 0, done.stderr[:2000]
    r = json.loads(done.stdout)
    assert r["same"], "the same grain every time"
    # Across the wrap the step is no bigger than across any interior seam: no grid of seams.
    assert r["wrap"] <= r["inner"] * 1.5 + 1, r
    # Centred: the grain darkens as much as it lightens. Uncentred it sat at 120 of 128 and
    # darkened every board by about 1.5%.
    assert 126 <= r["mean"] <= 130, r
    assert 20 <= r["sd"] <= 45, r              # visible, but a bit: sd 37 of 255 is about ±7% at one sigma
    assert r["min"] > 0 and r["max"] < 255, r  # never clipped flat
