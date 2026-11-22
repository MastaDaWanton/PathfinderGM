"""The first-time cards: their words, and which of them this install has seen.

The owner, 2026-11-21: "have a tutorial for each section that takes the user through
everything they need to know about a page or menu the first time they interact with it
and then a button to view those tutorials again". The design is docs/tutorials-plan.md and
the research behind it docs/research/2026-11-21-tutorials.md: one card at the section, the
first time it is met, never a launch tour (NN/g measured no gain from one, and CK3 cut its
67 boxes to a third), and a "?" and a Settings list to see any of it again.

**The words** are content/tutorials/*.json, one file per group, read once. A step names the
control it is about by a `data-tut` attribute, its numbers are `{placeholders}` filled from
the engine (`rules/tutorialfacts.py`), and a rules claim names the code that makes it true.
tests/test_tutorials.py reads all of that back, the way tests/test_skill_help.py holds the
skill hovers to the code. The page is sent the words only (`for_page`): never `source` or
`controls`, which are for the test (the refs-never-on-the-page ruling, 2026-09-28).

**What has been seen** is `tutorials.json` beside `models.json` in the user's data folder,
not the browser's storage: the desktop shell falls back to another port when 8917 is busy,
and a new port is a new origin with empty storage, and a phone on the LAN is another browser
altogether. One file means a card dismissed on the phone is dismissed on the desktop.
It carries `schema`. A missing, broken or unknown-schema file reads as empty and is written
whole on the next change, so the worst a crash mid-write can do is show the tips again; it
is never fatal and never trusted by its timestamp (CLAUDE.md, the stylesheet that stayed
"fresh" for five days).

**Versions.** Each tutorial has `v` and each step `since`, the `v` it arrived or last
changed in. Seen at an older `v`, a card shows only the steps newer than what was seen,
headed "New since you last looked" (owner decision D6); when no step is newer the seen
mark is brought up to date quietly. No tour vendor does this (Usetiful and PostHog restart
the whole tour), so it is ours, and it falls back to the whole card if `since` is left at 1.
"""
from __future__ import annotations

import datetime
import json
import re
from pathlib import Path

from django.conf import settings
from django.http import JsonResponse

from pathfindergm import files

from .apiutil import read_body

SCHEMA = 1
# The minigames' own first cards (33-bench-games.js) keep their own rule, shown until the
# game is scored well; only the mark lives here, so it follows the player across origins.
GAME_ID = re.compile(r"^game\.[a-z][a-z_-]{0,39}$")

_DATA: list[dict] | None = None


def _content_dir() -> Path:
    return Path(settings.BASE_DIR) / "content" / "tutorials"


def groups() -> list[dict]:
    """Every content file, in name order: {"group", "tutorials": [...]} (the test's view,
    anchors and sources included)."""
    global _DATA
    if _DATA is None:
        # In the order of the plan's §2 (the table, then maps, then benches), which is the
        # order Settings, Tutorials lists them: each file's `order`.
        _DATA = sorted((json.loads(p.read_text(encoding="utf-8"))
                        for p in _content_dir().glob("*.json")),
                       key=lambda g: (g.get("order", 99), g.get("group", "")))
    return _DATA


def tutorials() -> dict[str, dict]:
    """id -> tutorial, with its group's name on it."""
    out = {}
    for g in groups():
        for t in g.get("tutorials") or []:
            out[t["id"]] = dict(t, group=g.get("group", ""))
    return out


def content_hash(t: dict) -> str:
    """What a player reads in `t`, hashed: every step's title, words, anchor and controls,
    and not `since` or `source`. content/tutorials/versions.lock keeps one per tutorial, so
    words changed without raising `v` fail a test instead of never showing anybody
    (tools/tutorials_lock.py writes the file)."""
    import hashlib

    keep = [{k: s.get(k) for k in ("title", "words", "anchor", "controls", "buttons")}
            for s in t.get("steps") or []]
    raw = json.dumps(keep, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


# --- the store -----------------------------------------------------------------------------

def _path() -> Path:
    """Beside models.json, in the user's own data directory. Never in the repo."""
    p = Path(settings.CAMPAIGN_DIR).parent
    p.mkdir(parents=True, exist_ok=True)
    return p / "tutorials.json"


def _empty() -> dict:
    return {"schema": SCHEMA, "off": False, "seen": {}, "welcome_dismissed": False}


def read() -> dict:
    """The store, or an empty one for a file that is missing, broken or of another schema.
    utf-8-sig for the same reason as models.json: Notepad's BOM is an ordinary hand edit."""
    p = _path()
    try:
        raw = json.loads(p.read_text(encoding="utf-8-sig"))
    except FileNotFoundError:
        return _empty()
    except Exception as exc:   # torn by a crash, hand-edited wrong: tips again, never a 500
        files.unreadable(p, exc)
        return _empty()
    if not isinstance(raw, dict) or raw.get("schema") != SCHEMA:
        return _empty()
    out = _empty()
    out["off"] = bool(raw.get("off"))
    out["welcome_dismissed"] = bool(raw.get("welcome_dismissed"))
    seen = raw.get("seen")
    if isinstance(seen, dict):
        for k, e in seen.items():
            if isinstance(k, str) and isinstance(e, dict) and isinstance(e.get("v"), int):
                out["seen"][k] = {"v": e["v"], "at": str(e.get("at") or "")}
    return out


def _write(data: dict) -> None:
    files.write_text(_path(), json.dumps(data, indent=1))


def due_steps(t: dict, seen: dict | None) -> list[int]:
    """Which of `t`'s steps an automatic showing owes: all of them never seen, the ones
    newer than the seen version after an update, none when it is up to date."""
    steps = t.get("steps") or []
    if not seen:
        return list(range(len(steps)))
    if seen.get("v", 0) >= t.get("v", 1):
        return []
    return [i for i, s in enumerate(steps) if int(s.get("since", 1)) > int(seen.get("v", 0))]


def change(body: dict) -> dict:
    """Apply one POST: `seen` (a list of ids), `reset`, `off`, `welcome`. Unknown ids are
    ignored rather than refused: a page a version behind the server must not lose its turn.
    A version bumped by a pure rename (no step newer than the seen `v`) is brought up to
    date here too, quietly, by the page marking it seen."""
    data = read()
    known = tutorials()
    today = datetime.date.today().isoformat()
    if body.get("reset") is True:
        data["seen"] = {}
        data["welcome_dismissed"] = False
    if isinstance(body.get("off"), bool):
        data["off"] = body["off"]
    if body.get("welcome") is True:
        data["welcome_dismissed"] = True
    ids = body.get("seen") if isinstance(body.get("seen"), list) else []
    for tid in ids:
        if not isinstance(tid, str):
            continue
        if tid in known:
            data["seen"][tid] = {"v": int(known[tid].get("v", 1)), "at": today}
        elif GAME_ID.match(tid):
            data["seen"][tid] = {"v": 1, "at": today}
    _write(data)
    return data


# --- what the page is sent -----------------------------------------------------------------

def _page_step(s: dict) -> dict:
    from rules import tutorialfacts

    return {
        "title": s.get("title", ""),
        "words": tutorialfacts.fill(s.get("words", "")),
        "anchor": s.get("anchor", ""),
        "buttons": [{"label": b.get("label", ""), "words": tutorialfacts.fill(b.get("words", "")),
                     "anchor": b.get("tut", "")} for b in s.get("buttons") or []],
    }


def for_page(store: dict | None = None) -> dict:
    """Words only: no `source`, no `controls` (rule 7 of the plan's §3.6)."""
    store = store if store is not None else read()
    out = []
    for t in tutorials().values():
        seen = store["seen"].get(t["id"])
        out.append({
            "id": t["id"], "title": t.get("title", ""), "group": t.get("group", ""),
            "manual": t.get("manual", ""), "root": t.get("root", ""),
            "seen": bool(seen), "due": due_steps(t, seen),
            "updated": bool(seen) and seen.get("v", 0) < t.get("v", 1),
            "steps": [_page_step(s) for s in t.get("steps") or []],
        })
    return {"off": store["off"], "welcome_dismissed": store["welcome_dismissed"],
            "tutorials": out,
            "games_seen": sorted(k[len("game."):] for k in store["seen"] if GAME_ID.match(k))}


def api(request):
    """GET the words and what is seen; POST a change (`change`) and get the same back.
    Guarded like every other POST: Django's CSRF, and a LAN guest may make it
    (pathfindergm/lan.py GUEST_WRITES), because a card dismissed on the phone is the
    player's dismissal."""
    if request.method == "POST":
        return JsonResponse(for_page(change(read_body(request))))
    if request.method != "GET":
        return JsonResponse({"error": "GET or POST"}, status=405)
    return JsonResponse(for_page())
