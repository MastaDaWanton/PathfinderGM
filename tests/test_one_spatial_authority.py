"""Stage 8e — the ratchet: there is one spatial authority, and the engine holds it.

The diagnosis that started the place work (docs/places-plan.md): four independent
spatial authorities on the scene, none derived from the others, and two writers of
"where the party is" reaching one prompt. These are the assertions that keep it at one.
Each names what it prevents; a test that only asserts behaviour gets deleted by the next
person, one that records what went wrong survives.
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

PRODUCTION = ("rules", "gm", "play")

# Every site allowed to assign an actor's or the scene's place, with the reason. A named
# allowlist rather than a count, because a count cannot tell a removal from a relocation
# — the shape `_CLOCK_SITES` established for the world clock.
_PLACE_WRITERS = {
    ("rules/engine.py", "add"): "a creature arrives HERE; the first writer",
    ("rules/engine.py", "move"): "the one mover; the second writer",
    ("rules/engine.py", "place_party"): "placement, not movement: a loaded or new scene "
                                        "stood somewhere real without unseating anybody",
    ("rules/engine.py", "_heal_places"): "",
}
# `scene.at` itself — the party record — has the same three, plus the load-failure floor.
_SCENE_AT_WRITERS = {
    ("rules/engine.py", "move"): "the PC moved, so the party moved",
    ("rules/engine.py", "place_party"): "placement",
    ("play/campaign.py", "_heal_places"): "a world that will not load leaves the party at "
                                          "'here' rather than nowhere on the way to the "
                                          "sentence that says so",
}


def _assignments(attr: str):
    """Every `X.<attr> = ...` in production, as (file, enclosing function, target text)."""
    out = []
    for folder in PRODUCTION:
        for path in Path(folder).rglob("*.py"):
            src = path.read_text(encoding="utf-8")
            tree = ast.parse(src)
            for fn in ast.walk(tree):
                if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    continue
                for node in ast.walk(fn):
                    if not isinstance(node, (ast.Assign, ast.AugAssign, ast.AnnAssign)):
                        continue
                    targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                    for t in targets:
                        if isinstance(t, ast.Attribute) and t.attr == attr:
                            out.append((path.as_posix(), fn.name,
                                        ast.get_source_segment(src, t) or ""))
    return out


def test_an_actors_place_has_three_writers_and_they_are_named():
    """Under containment `Actor.at` is the one spatial fact about anybody. A fourth
    writer is the free-text `spot` coming back through a side door."""
    found = {}
    for file, fn, target in _assignments("at"):
        # `self.at` inside Scene is the party record (checked below); `BloodPool.at` is a
        # grid square with an unlucky name and is constructed, never assigned.
        if target in ("self.at", "self.scene.at"):
            continue
        found.setdefault((file, fn), []).append(target)
    unexpected = {k: v for k, v in found.items() if k not in _PLACE_WRITERS}
    assert not unexpected, (
        f"new writer(s) of an actor's place: {unexpected}. A place is written by "
        f"Scene.add, Scene.move and Engine.place_party, and nothing else.")


def test_the_party_record_has_three_writers_and_they_are_named():
    found = {(file, fn) for file, fn, target in _assignments("at")
             if target in ("self.at", "self.scene.at")}
    unexpected = found - set(_SCENE_AT_WRITERS)
    assert not unexpected, f"new writer(s) of scene.at: {sorted(unexpected)}"


def test_nothing_writes_the_ground_beside_the_place():
    """`scene.biome` was a sibling field, written by travel and healed by the campaign,
    and "both are urban" is what let walking out of a stall change nothing."""
    assert _assignments("biome") == [], _assignments("biome")


def test_nothing_writes_where_into_the_thread():
    """Two writers of one fact reached one prompt: `scene.at` and a regex over the
    player's own sentence, and a single brief could assert two rooms."""
    offenders = []
    for folder in PRODUCTION:
        for path in Path(folder).rglob("*.py"):
            for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                if re.search(r"""thread\s*\[\s*["']where["']\s*\]\s*=|["']where["']\s*:""", line):
                    if "thread" in line or "scene.thread" in line:
                        offenders.append(f"{path.as_posix()}:{n}: {line.strip()}")
    assert offenders == [], offenders


def test_nothing_writes_the_roster_directly():
    """Five sites did. Under a derived view a write either vanishes into a computed
    dict or raises; the ratchet is that none exist to do either."""
    offenders = []
    pattern = re.compile(r"\.actors\s*(\[[^\]]*\]\s*=[^=]|\.pop\(|\.update\(|\.clear\(|\.setdefault\()"
                         r"|del\s+[\w.]*\.actors\[")
    for folder in PRODUCTION:
        for path in Path(folder).rglob("*.py"):
            for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                if pattern.search(line) and not line.strip().startswith("#"):
                    offenders.append(f"{path.as_posix()}:{n}: {line.strip()}")
    assert offenders == [], offenders


def test_the_place_the_brief_states_comes_from_the_engine():
    """`gm/prompts.py` used to derive the place list itself — a second copy of
    `Engine.places()`, keyed on a different argument. It receives it now."""
    src = Path("gm/prompts.py").read_text(encoding="utf-8")
    assert "spots_for(" not in src, "the brief grew its own derivation again"
    assert "here=None" in src and "known=()" in src
    for caller in ("gm/agent.py", "play/views.py"):
        text = Path(caller).read_text(encoding="utf-8")
        for m in re.finditer(r"scene_brief\(", text):
            window = text[m.start():m.start() + 400]
            assert "here=" in window and "known=" in window, (
                f"{caller}: a scene_brief call without the engine's place")


def test_only_the_engine_moves_people():
    """`Scene.move` cannot validate a place id — Scene has no world — so the door that
    can is the Engine's. A `move(` on a scene from gm/ or play/ is a writer that skipped
    the registry."""
    offenders = []
    for folder in ("gm", "play"):
        for path in Path(folder).rglob("*.py"):
            for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                if re.search(r"scene\.move\(|\.scene\.move\(", line):
                    offenders.append(f"{path.as_posix()}:{n}: {line.strip()}")
    assert offenders == [], offenders
