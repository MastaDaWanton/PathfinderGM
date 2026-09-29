"""Just enough of the play page for 10-spells.js and 11-exits.js to run in node, together,
as they do on the page: the exits row attaches its places into the spell chip's slot, so a
test of either reads the real functions of both, never copies of them.

`run(tmp_path, steps)` loads both shipped files after the stub and runs `steps`; the last
line `steps` prints (JSON) is what comes back. `click(id)` presses an exit, `clickX()` the
chip's remove button, `key(k, where)` a key in "#input", "#exits" or on the chip, and
`sayBody()` is the body the Say button would post (04's own shape, `attachmentsForSay`).
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TABLE = ROOT / "play" / "static" / "js" / "table"

PRELUDE = r"""
function el(id) {
  return { id, hidden: true, innerHTML: "", textContent: "", placeholder: "", value: "",
    className: "", selectionStart: 0, selectionEnd: 0, dataset: {},
    classList: { on: new Set(), toggle(c, v) { (v === undefined ? !this.on.has(c) : v)
      ? this.on.add(c) : this.on.delete(c); }, add(c) { this.on.add(c); },
      remove(c) { this.on.delete(c); }, contains(c) { return this.on.has(c); } },
    focus() { FOCUS.push(id); }, setAttribute() {}, getAttribute() { return null; } };
}
const FOCUS = [];
const ELS = { exits: el("exits"), attachments: el("attachments"), input: el("input"),
              saystatus: el("saystatus"), err: el("err") };
ELS.input.placeholder = "What do you do?";
const BOX = ELS.exits;
const LISTENERS = {};
const document = {
  getElementById: id => ELS[id] || null,
  querySelector: () => null,
  querySelectorAll: () => [],
  addEventListener: (t, f) => { (LISTENERS[t] = LISTENERS[t] || []).push(f); },
  contains: () => true,
  activeElement: null,
};
const window = { addEventListener() {} };
const $ = sel => document.getElementById(sel.replace(/^#/, ""));
const esc = s => String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;")
  .replace(/>/g, "&gt;").replace(/"/g, "&quot;");
const SENT = [];
function takeTurn(body) { SENT.push(body); }
const RENDERS = [];
function onRender(f) { RENDERS.push(f); }
let STATE = null;
function fire(type, target) {
  const ev = { target, key: target.key, preventDefault() {}, relatedTarget: null };
  (LISTENERS[type] || []).forEach(f => f(ev));
}
function click(id) {
  const btn = { dataset: { exit: id }, getAttribute: () => null };
  fire("click", { closest: sel => sel.includes(".exitbtn") ? btn : null });
}
function clickX() {
  fire("click", { closest: sel => sel.includes(".chip-x") ? {} : null });
}
function key(k, where) {
  const t = { key: k, closest: sel => sel.includes(where) ? ELS.input : null };
  fire("keydown", t);
}
function renderAll(s) { STATE = s; RENDERS.forEach(f => f(s)); }
function sayBody() {
  const text = ELS.input.value.trim();
  const body = { text };
  if (currentAttachments().length) body.attachments = attachmentsForSay();
  return body;
}
// spellSay speaks after 30ms; a probe prints after the last sentence has landed,
// and a function passed to `done` is read then, so it sees that sentence.
function done(obj) {
  setTimeout(() => console.log(JSON.stringify(typeof obj === "function" ? obj() : obj)), 80);
}
"""


def exits_state(fighting: bool, awaiting=None) -> dict:
    """An arena next door, a gate shut for the wanted, and a road that is a journey."""
    return {"awaiting": awaiting, "ended": False, "scene": {
        "in_encounter": fighting, "exits": [
            {"id": "p:arena", "name": "the arena", "group": "next_door",
             "time_words": "a few minutes' walk", "blocked": "", "journey": False},
            {"id": "p:gate", "name": "the gate", "group": "outside",
             "time_words": "a few minutes' walk", "blocked": "The watch has your name.",
             "journey": False},
            {"id": "r:north", "name": "the north road", "group": "road",
             "time_words": "about three days on foot", "blocked": "", "journey": True},
        ]}}


def run(tmp_path: Path, steps: str) -> dict:
    code = "\n".join((TABLE / name).read_text(encoding="utf-8")
                     for name in ("10-spells.js", "11-exits.js"))
    f = tmp_path / "probe.js"
    f.write_text(PRELUDE + code + "\n" + steps, encoding="utf-8")
    done = subprocess.run(["node", str(f)], capture_output=True, text=True,
                          encoding="utf-8")
    assert done.returncode == 0, done.stderr
    return json.loads(done.stdout.strip().splitlines()[-1])
