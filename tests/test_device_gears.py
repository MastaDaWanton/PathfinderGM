"""The engine device's gears turn as one meshing train, and are never drawn turning backwards.

The owner, 2026-10-05: "the gears are not synced correctly and are often spinning the same
direction instead of how they should." The angles were already right (the large gear at
-10/16 of the small one's, half a tooth out of phase at the mesh). What was wrong was the
drawing: a gear is a pattern repeating every tooth, so a frame that moves it half a tooth or
more reads as motion the other way (the wagon wheel). Measured in the running app before the
fix: frames of 20 ms on median, the gears moving 0.56 of a tooth a frame on median and 0.75
at most, 54 of 85 steady frames at half a tooth or more; the small gear had no holes, so its
aliased teeth were all that showed it turning, and it read as turning the large one's way.

These run the module's own gear table (`deviceGears`, from the real device-geometry.js) and
its own frame step (`deviceShow`) in node.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess

import pytest

from pagesource import ROOT, TABLE_SCRIPTS

DEVICE = (TABLE_SCRIPTS / "13-device.js").read_text(encoding="utf-8")
GEOMETRY = (ROOT / "play" / "static" / "img" / "v2" / "device-geometry.js").read_text(encoding="utf-8")
G = json.loads(re.search(r"window\.DEVICE_GEOMETRY = (\{.*\});", GEOMETRY).group(1))
LARGE_RPS = float(re.search(r"const LARGE_RPS = ([0-9.]+);", DEVICE).group(1))

# Enough of a page for the module to load and define its functions; with no geometry and no
# #device the drawing returns at once.
_STUB = r"""
const document = { querySelector: () => null, getElementById: () => null,
                   addEventListener: () => {} };
const window = { DEVICE_GEOMETRY: null, matchMedia: () => ({ matches: false }) };
function onRender() {}
"""

needs_node = pytest.mark.skipif(shutil.which("node") is None, reason="node is not on this machine")


def _node(body: str, tmp_path) -> object:
    f = tmp_path / "gears.js"
    f.write_text(_STUB + DEVICE + f"\nconst G = {json.dumps(G)};\n" + body, encoding="utf-8")
    done = subprocess.run(["node", str(f)], capture_output=True, text=True, timeout=30)
    assert done.returncode == 0, done.stderr
    return json.loads(done.stdout.strip().splitlines()[-1])


@needs_node
def test_two_meshing_gears_never_turn_the_same_direction(tmp_path):
    """Two meshing gears turned the same direction, to the owner's eye. In the table every
    gear that meshes with another turns against it (opposite sign) at the inverse of their
    tooth ratio, its centre is the two pitch radii from the other's (they really touch),
    and every gear has holes, so its turning shows by more than its teeth."""
    gears = _node("console.log(JSON.stringify(deviceGears(G)));", tmp_path)
    assert len(gears) == len(G["gears"]) >= 2
    assert gears[0]["ratio"] == 1, "gear 0 is the driver"
    meshes = [g for g in gears if g["meshes"] is not None]
    assert meshes, "no gear in the train meshes with another"
    for g in meshes:
        p = gears[g["meshes"]]
        assert g["ratio"] * p["ratio"] < 0, f"gear {g['i']} turns the same way as gear {p['i']}"
        assert abs(g["ratio"] / p["ratio"]) == pytest.approx(p["z"] / g["z"])
        dist = ((g["x"] - p["x"]) ** 2 + (g["y"] - p["y"]) ** 2) ** 0.5
        assert dist == pytest.approx(G["m"] * (g["z"] + p["z"]) / 2)
    small, large = gears[0], gears[1]
    assert (small["z"], large["z"]) == (10, 16)
    assert large["ratio"] == pytest.approx(-10 / 16)
    assert all(g["holes"] > 0 for g in gears), "a gear with no holes shows its turning by teeth alone"


@needs_node
def test_a_gear_on_an_axle_turns_with_it(tmp_path):
    """The table's other rule, for a train that grows: a gear on another's axle turns with
    it, at its angle; a gear meshing with that one turns against both."""
    got = _node("""
      const H = { origin: [0, 0], m: 2, gears: [[0, 0, 10], [0, 20, 10], [0, 20, 30], [0, 60, 10]] };
      const t = [{}, { meshes: 0 }, { axle: 1 }, { meshes: 2 }];
      console.log(JSON.stringify(deviceGears(H, t).map(g => g.ratio)));""", tmp_path)
    assert got == pytest.approx([1, -1, -1, 3])


@needs_node
def test_teeth_meet_gaps_at_every_angle(tmp_path):
    """Synced: at the point where two gears touch, a tooth of one sits in a gap of the
    other at every driver angle, not only at rest. Measured in fractions of a pitch along
    the contact line: one gear's fraction past a tooth is half a pitch less the other's."""
    got = _node("""
      const gears = deviceGears(G), out = [];
      const frac = v => ((v % 1) + 1) % 1;
      for (let d = 0; d < 720; d += 7.3) {
        const a = deviceGearAngles(gears, d);
        for (const g of gears) if (g.meshes != null) {
          const p = gears[g.meshes];
          const toward = Math.atan2(g.y - p.y, g.x - p.x) * 180 / Math.PI;
          const fP = frac((toward - a[p.i]) / p.pitch), fC = frac((toward + 180 - a[g.i]) / g.pitch);
          out.push(Math.min(frac(fC + fP - 0.5), 1 - frac(fC + fP - 0.5)));
        }
      }
      console.log(JSON.stringify(out));""", tmp_path)
    assert got and max(got) < 1e-9


@needs_node
@pytest.mark.parametrize("fps", [144, 60, 50, 30, 20])
def test_no_frame_turns_a_gear_half_a_tooth(tmp_path, fps):
    """The wagon wheel. Before: 0.56 of a tooth a frame on median at 50 fps, 0.75 at most,
    and 54 of 85 frames at half a tooth or more, read as turning backwards. Frames at each
    rate, with a fifth of a frame of jitter, at full speed: no gear moves more than a third
    of a tooth in a frame, none ever moves against its own direction, and where the rate is
    fast enough (144 Hz) the drawing keeps the model's speed exactly."""
    omega = LARGE_RPS * 360 * 16 / 10
    got = _node(f"""
      const gears = deviceGears(G), cap = deviceFrameCap(gears), shown = {{ from: 0, angle: 0 }};
      let t = 0, seed = 7, prev = deviceGearAngles(gears, 0);
      const rnd = () => (seed = (seed * 16807) % 2147483647) / 2147483647;
      const worst = gears.map(() => 0), back = gears.map(() => 0);
      for (let f = 0; f < 600; f++) {{
        t += (1000 / {fps}) * (0.8 + 0.4 * rnd());
        const a = deviceGearAngles(gears, deviceShow(shown, {omega} * t / 1000, cap));
        gears.forEach((g, i) => {{
          const teeth = (a[i] - prev[i]) / g.pitch;
          worst[i] = Math.max(worst[i], Math.abs(teeth));
          if (teeth * Math.sign(g.ratio) < 0) back[i]++;
        }});
        prev = a;
      }}
      console.log(JSON.stringify({{ worst, back, shown: shown.angle, model: {omega} * t / 1000 }}));""",
                tmp_path)
    assert max(got["worst"]) <= 1 / 3 + 1e-9, got["worst"]
    assert got["back"] == [0] * len(got["back"]), "a gear was drawn turning against its own direction"
    assert got["shown"] > 0
    if fps >= 144:
        assert got["shown"] == pytest.approx(got["model"])


def test_the_drawing_turns_every_gear_from_one_driver():
    """Every gear's transform is written from `deviceGearAngles` of one capped driver; no
    second angle (the old per-gear MESH arithmetic) remains to drift from it."""
    draw = DEVICE[DEVICE.index("  function draw() {"):DEVICE.index("lever.setAttribute")]
    assert "deviceShow(shown, M.aPrev + (M.aS - M.aPrev) * alpha, FRAME_CAP)" in draw
    assert "deviceGearAngles(GEARS, driver)" in draw
    assert "MESH" not in DEVICE
    assert "alpha = acc / T.STEP;" in DEVICE
