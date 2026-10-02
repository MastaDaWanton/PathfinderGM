"""The engine device is heard, quietly, at its own moments.

The owner, 2026-10-02, of the brass status mechanism beside the story: "this needs sound as
well, not too loud". It turns on every single turn, so a sound that is merely fine once
becomes the loudest thing in a session. These tests hold the two promises: every moment the
device has a sound for is a sound that exists, and none of them is louder than the quietest
everyday interface sound.
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SOUND = (ROOT / "play" / "static" / "js" / "sound.js").read_text(encoding="utf-8")
DEVICE = (ROOT / "play" / "static" / "js" / "table" / "13-device.js").read_text(encoding="utf-8")


def _defs() -> dict[str, str]:
    """Each `def("name", n, function (c) { ... });` body, by name."""
    out = {}
    for m in re.finditer(r'def\("([a-z.]+)", \d+, function \(c\) \{(.*?)\n  \}\);', SOUND, re.S):
        out[m.group(1)] = m.group(2)
    return out


def test_every_device_moment_has_a_sound_that_exists():
    names = set(re.findall(r'"(ui\.device\.[a-z]+)"', DEVICE))
    assert {"ui.device.tick", "ui.device.puff", "ui.device.settle", "ui.device.sigh",
            "ui.device.lever"} <= names
    assert names <= set(_defs())


def test_the_device_is_quieter_than_a_click():
    """Every peak in a device sound is under ui.click's loudest (0.07). It was under half a
    click at first; the owner asked for "a bit louder" (2026-10-02) and every peak doubled,
    but a sound heard on every turn must still never be louder than a button."""
    defs = _defs()
    click = max(float(x) for x in re.findall(r"peak: ([0-9.]+)", defs["ui.click"]))
    for name, body in defs.items():
        if name.startswith("ui.device."):
            peaks = [float(x) for x in re.findall(r"peak: ([0-9.]+)", body)]
            assert peaks and max(peaks) < click, (name, peaks)


def test_ticks_follow_the_gear_and_a_returning_tab_does_not_rattle():
    """The ticks are the large gear's teeth passing, so they slow as it eases to a stop;
    and a tab brought back from the background, which catches the model up in one frame,
    must not fire every tick it missed at once."""
    assert "M.largeTurns >= M.nextTick" in DEVICE and "TICK_EVERY" in DEVICE
    assert "now - (lastSaid[name] || -1e9) < (name === \"ui.device.tick\" ? 28 : 70)" in DEVICE


def test_the_running_bed_follows_the_gears_and_stays_a_bed():
    """The owner's reference, 2026-10-02, was a spinning cog machine: a continuous meshing
    whir, not a clock. The bed is built by `Sound.machine()`, its loudness, tooth rate and
    pitch follow the gears' speed, and its ceiling (0.07 of the ui bus, doubled when the
    owner asked for "a bit louder") is a click's peak, so it never rises over the story."""
    assert "function machine()" in SOUND and "machine: machine" in SOUND
    assert "out.gain.setTargetAtTime(0.07 * v" in SOUND
    assert "Sound.machine()" in DEVICE and "bed.speed(v)" in DEVICE and "bed.stop()" in DEVICE
