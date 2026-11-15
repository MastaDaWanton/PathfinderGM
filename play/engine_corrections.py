""""That's wrong" on what the ENGINE did: the player pinpoints a wrong line of the turn's
record and it is logged with enough to reproduce the turn (the owner, 2026-11-15: "it needs
to be able to pinpoint an engine mistake, because the narration is fairly locked in and it
is the engine that is making the most mistakes now"; their choice, pinpoint and log — no
undo, no take-back of the turn).

The narration half (`play/corrections.py`) is untouched: the same panel, the same button.
When it opens on a beat, the page also shows what the engine did that turn, one line each,
in the words the house already writes for it:

  * the reading of the player's line — each act the reader took, with the player's own
    words it took it from (`reading.actions[].span`, grounded in the sentence by
    `interpret.ground`, so nothing here is a model's invention);
  * every outcome by its tell (`views.plain_tell`, the page's form of a tell: numbers in
    brackets and every key gone) or, refused, by its page sentence (`for_a_person`), with
    the rolls the Rolls panel would show for it (`views._player_visible_entry`, the
    allow-list that panel is built from);
  * the acts the plan did nothing for (`reading.table` rows with no ops).

**What the page never gets** (refs-never-on-the-page 2026-09-28; shot-in-the-dark
2026-11-06): an outcome by, at or about a creature the PC does not locate is left out
whole, by the board's own question (`awareness.player_locates`, which `views._tactics`
asks of every foe before a ref, a square or a provoker reaches the readout); a hidden roll
never shows a number, and an opposed check's target that IS a hidden roll is withheld as
the Rolls panel withholds it; a check made wholly behind the screen (every roll hidden: the
oracle's odds roll, a secret Sense Motive) shows no line at all. The LOG keeps everything,
hidden outcomes included: the log is for us, the page is for the player.

**How it was done before, and what was taken.**
  * MUDs split the player's report by what is wrong: ``bug`` for "skills, spells, game
    mechanics ... messages during combat", ``typo`` for text (Shattered Kingdoms' help
    "bug idea typo", shatteredkingdoms.org/display-help.php?id=29; MUME's help says a bug
    "which only involves the wrong form of text being output is a typo",
    mume.org/help/typo). That is this split exactly: corrections.py is the typo log, this
    is the bug log. Each MUD report records where the player stood (the room number), and
    an admin noted reports "aren't easily combined" — so every record here stands alone.
  * In-game bug reporters attach the save, because a save is the reproduction (bugnet.io,
    "capturing game state for bug reports", "how to reproduce a bug from a save file";
    Sentry's Unreal "game state capture" attaches a game_state.jsonl to the event,
    docs.sentry.io/platforms/unreal/game-state-capture). Taken: the start-of-turn save
    rides with the record. Their advice to keep snapshots lean is why it is gzipped and
    only the last `SNAPSHOTS_KEPT` are kept.
  * Fine-grained RLHF (Wu et al., arXiv 2306.01693) labels at the sentence/sub-sentence
    span with a small closed set of error types (its abstract names three: factual
    incorrectness, irrelevance, incompleteness). Taken: a mark is on one line, from a
    closed list of six, with an optional short note, never free text alone. I could NOT
    source a measurement of how agreement falls as categories are added, nor a tool that
    publicly dropped a large taxonomy; six is the owner's list, not a measured optimum.
  * VTT chat cards: Foundry ships no way to correct a posted roll; modules (Chronicler's
    Modified Rolls, RSReforged) edit the number in place. Refused here on the owner's
    word — the engine owns every number; a wrong one is logged, never overwritten.

**Which rows are the turn's.** Every event row the engine writes is stamped with
`transcript_at` (`history.stamp`): how long the transcript was when it was written. A beat
belongs to the player line before it, so its turn is every row stamped after that line and
no later than the next one — the creatures' turns included, which follow the player's.

**The log** (`<data>/training/engine-corrections.jsonl`) follows corrections.py's rules: a
`FORMAT`, one whole record per line, appended and never rewritten, read latest by `id`.
"""
from __future__ import annotations

import gzip
import json
import os
from datetime import datetime
from pathlib import Path

from pathfindergm import files

from . import corrections

FORMAT = 1
MAX_NOTE = corrections.MAX_NOTE
# The owner's list (2026-11-15), in their words. "missing" marks the turn, not a line.
KINDS = {
    "shouldnt": "Shouldn't have happened",
    "needs_roll": "Needed a roll",
    "should_work": "Should have worked",
    "wrong_number": "Wrong number",
    "wrong_who": "Wrong person or target",
    "missing": "Something's missing",
}
MISSING = "missing"
# The start-of-turn saves kept beside the log. Measured on a 0.3.5 save of 413,972 bytes
# (merchant-road, 39 turns): 46,201 bytes gzipped. 40 of them is ~2 MB.
SNAPSHOTS_KEPT = 40
EVENT_KINDS = ("turn", "resolution", "npc-turn")


def log_path() -> Path:
    return corrections.training_dir() / "engine-corrections.jsonl"


def snapshot_dir() -> Path:
    return corrections.training_dir() / "engine-snapshots"


# --- the turn's rows -------------------------------------------------------------------

def _player_lines(c) -> list[int]:
    return [i for i, b in enumerate(c.transcript)
            if isinstance(b, dict) and b.get("who") == "player" and b.get("kind") != "aside"]


def turn_of(c, i: int) -> tuple[int, int]:
    """(p, q): the player line beat `i` answers (-1 for none) and the next one (the
    transcript's length for the latest turn)."""
    lines = _player_lines(c)
    p = max((j for j in lines if j < i), default=-1)
    q = min((j for j in lines if j > i), default=len(c.transcript))
    return p, q


def rows_for(c, i: int) -> list[tuple[int, dict]]:
    """The turn log's event rows for beat `i`'s turn, with their index in the log."""
    p, q = turn_of(c, i)
    out = []
    for n, row in enumerate(c.turn_log or []):
        if not isinstance(row, dict) or row.get("kind") not in EVENT_KINDS:
            continue
        at = row.get("transcript_at")
        if isinstance(at, int) and p + 1 <= at <= q:
            out.append((n, row))
    return out


# --- what the player may see ----------------------------------------------------------

def _hidden(scene) -> dict:
    """ref -> name of everybody here the PC does not locate (`awareness.player_locates`)."""
    from rules import awareness

    return {r: str(a.name or "") for r, a in (scene.actors or {}).items()
            if not a.is_pc and not awareness.player_locates(scene, a)}


def _refs_in(value) -> set:
    """Every string anywhere in an outcome's actor, effects or intent: a hidden ref in any
    of them puts the outcome behind the screen."""
    out: set = set()
    if isinstance(value, str):
        out.add(value)
    elif isinstance(value, dict):
        for v in value.values():
            out |= _refs_in(v)
    elif isinstance(value, (list, tuple)):
        for v in value:
            out |= _refs_in(v)
    return out


def _behind_screen(o: dict, intent: dict | None, hidden: dict, shown_names: set) -> bool:
    if hidden and _refs_in([o.get("actor"), o.get("effects"), intent or {}]) & set(hidden):
        return True
    # A hidden creature's own name in the tell, where nobody the player sees shares it.
    tell = str(o.get("tell") or "") + " " + str(o.get("for_a_person") or "")
    if any(n and n not in shown_names and n in tell for n in hidden.values()):
        return True
    rolls = o.get("rolls") or []
    # A check made behind the screen ON THE PLAYER'S BEHALF: every roll hidden, a verdict
    # or a target, and nobody else acting in the open — the oracle's odds roll, a secret
    # Perception. Another creature's swing is hidden-rolled too (every NPC roll is) and
    # is seen happen: the sergeant's longspear miss was dropped by the first cut of this
    # rule, live 2026-11-15. Its numbers never show either way (`_roll_words`).
    return bool(rolls) and all(r.get("visibility") != "player" for r in rolls) \
        and (o.get("dc") is not None or o.get("verdict") is not None) \
        and str(o.get("actor") or "pc") == "pc"


def _sign(v) -> str:
    return f"+{v}" if v >= 0 else f"{v}"


def _roll_words(o: dict) -> list[str]:
    """The rolls exactly as the Rolls panel prints them (03-offers-and-map.js
    `renderRolls`), from the panel's own allow-list (`_player_visible_entry`)."""
    from .views import _player_visible_entry

    seen = _player_visible_entry({"outcomes": [o]})["outcomes"]
    if not seen:
        return []
    v = seen[0]
    dc = v.get("dc")
    out = []
    for r in v.get("rolls") or []:
        vs = (f" vs {dc['value']}" if isinstance(dc, dict) and dc.get("value") is not None
              and r.get("die") == "1d20" else "")
        terms = "".join(f" {_sign(m.get('value', 0))} {m.get('source', '')}"
                        for m in r.get("modifiers") or [])
        out.append(f"{r.get('label') or o.get('op')}: {r.get('total')}{vs} "
                   f"({r.get('raw')}{terms})")
    return out


def _act_words(act: str) -> str:
    return str(act or "").replace("_", " ")


def lines(c, i: int) -> list[dict]:
    """The page's lines for beat `i`'s turn: [{id, kind, text, rolls}], hidden things out."""
    from gm.interpret import acting as interpret_acting

    from .views import plain_tell

    scene = c.scene
    hidden = _hidden(scene)
    shown_names = {str(a.name or "") for r, a in (scene.actors or {}).items() if r not in hidden}
    out: list[dict] = []
    for n, row in rows_for(c, i):
        reading = row.get("reading") if isinstance(row.get("reading"), dict) else None
        if reading:
            acts = [a for a in reading.get("actions") or [] if isinstance(a, dict)]
            table = reading.get("table") or []
            if reading.get("question") and not acts:
                out.append({"id": f"r{n}.q", "kind": "reading",
                            "text": "Read as a question, with nothing done."})
            for k, a in enumerate(acts):
                span = str(a.get("span") or "").strip()
                words = f"“{span}”" if span else "your line"
                verb = _act_words(a.get("act"))
                acting = interpret_acting(a)
                text = (f"Read {words} as: {verb}." if acting
                        else f"Read {words} as a plan to {verb}, not done now.")
                out.append({"id": f"r{n}.a{k}", "kind": "reading", "text": text})
                row_k = table[k] if k < len(table) and isinstance(table[k], dict) else None
                # Neither an op the table names nor one it built whole: the rules never
                # touched this act by the reading (a detector's op may still have — the
                # Perception check under "look out over the harbour", live 2026-11-15 —
                # so the words claim only what is known).
                if acting and row_k is not None and len(table) == len(acts) \
                        and not row_k.get("ops") and not row_k.get("built"):
                    out.append({"id": f"r{n}.d{k}", "kind": "dropped",
                                "text": f"No rule was applied to {words} itself; "
                                        "the narration answered it."})
        intents = {str(x.get("id")): x for x in row.get("intents") or []
                   if isinstance(x, dict)}
        for k, o in enumerate(row.get("outcomes") or []):
            if not isinstance(o, dict):
                continue
            if _behind_screen(o, intents.get(str(o.get("intent_id"))), hidden, shown_names):
                continue
            refused = o.get("status") == "refused"
            said = (str(o.get("for_a_person") or "") if refused else "") or str(o.get("tell") or "")
            said = plain_tell(said, scene)
            if not said:
                continue
            out.append({"id": f"r{n}.o{k}", "kind": "refused" if refused else "outcome",
                        "text": ("Refused: " + said) if refused else said,
                        "rolls": _roll_words(o)})
    return out


def page(c, i: int) -> dict:
    """What `GET api/beat/engine` answers."""
    p, _q = turn_of(c, i)
    return {"beat": i, "lines": lines(c, i), "kinds": KINDS, "max_note": MAX_NOTE,
            # False for a turn with no stamped rows: played before 0.3.6, or one where
            # the engine did nothing (a beat of pure talk the table resolved nothing for).
            "recorded": bool(rows_for(c, i)),
            "player_line": str(c.transcript[p].get("text") or "") if p >= 0 else ""}


# --- the snapshot ---------------------------------------------------------------------

def _snapshot(c, p: int, rid: str) -> dict:
    """The save as it stood when the turn began — a kept backup (`campaign.save` rotates
    once per player line, so `.1` is the end of the turn before), copied gzipped beside
    the log. The backup chosen is the one holding exactly the player lines before `p`, so
    an older beat finds `.2` or `.3`, and a turn whose start has rotated out says so."""
    want = sum(1 for b in c.transcript[:max(p, 0)]
               if isinstance(b, dict) and b.get("who") == "player")
    for path in files.backups(c.path(), keep=3):
        try:
            raw = path.read_bytes()
            got = sum(1 for b in json.loads(raw.decode("utf-8")).get("transcript") or []
                      if isinstance(b, dict) and b.get("who") == "player")
        except (OSError, ValueError):
            continue
        if got != want:
            continue
        packed = gzip.compress(raw, mtime=0)
        dest = files.child(snapshot_dir(), rid, ".json.gz")
        dest.parent.mkdir(parents=True, exist_ok=True)
        files.write_bytes(dest, packed)
        _trim_snapshots()
        return {"file": f"engine-snapshots/{dest.name}", "from": path.name,
                "bytes": len(packed), "raw_bytes": len(raw), "player_lines": got}
    return {"file": None, "why": "the start of this turn is no longer among the kept saves"}


def _trim_snapshots() -> None:
    kept = sorted(snapshot_dir().glob("*.json.gz"), key=lambda f: f.stat().st_mtime)
    for old in kept[:-SNAPSHOTS_KEPT]:
        files.remove(old)


# --- the record -----------------------------------------------------------------------

class Refused(corrections.Refused):
    pass


def log(c, i: int, marks) -> dict:
    """Write one record for the marks on beat `i`'s turn; the record back.

    `marks` is [{"line": id | "missing", "kind": key of KINDS, "note": str}]. A line is
    looked up again here, in the lines the page was shown, so a mark names what the
    player read and nothing else."""
    if not (0 <= i < len(c.transcript)) or not corrections._is_narrated(c.transcript[i]):
        raise Refused("That beat cannot be marked.")
    shown = {ln["id"]: ln for ln in lines(c, i)}
    picked = []
    for m in marks if isinstance(marks, list) else []:
        if not isinstance(m, dict):
            continue
        lid, kind = str(m.get("line") or ""), str(m.get("kind") or "")
        if lid == MISSING:
            kind = MISSING
        elif lid not in shown:
            raise Refused("That line is not in this turn's record.", status=400)
        if kind not in KINDS:
            raise Refused("Pick what kind of mistake it is.", status=400)
        note = str(m.get("note") or "")[:MAX_NOTE].strip()
        picked.append({"line": lid, "kind": kind, "label": KINDS[kind], "note": note,
                       "text": "" if lid == MISSING else shown[lid]["text"],
                       "rolls": [] if lid == MISSING else shown[lid].get("rolls") or []})
    if not picked:
        raise Refused("Mark a line first, or say something is missing.", status=400)
    if len(picked) > 40:
        raise Refused("That is more marks than one turn has lines.", status=400)
    p, q = turn_of(c, i)
    rows = rows_for(c, i)
    reading = next((r["reading"] for _n, r in rows if isinstance(r.get("reading"), dict)),
                   None)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    rid = f"{c.id}-{i}-{stamp}-{os.urandom(2).hex()}"
    entry = corrections.input_for(c, i) or {}
    rec = {
        "format": FORMAT, "kind": "engine", "id": rid,
        "app_version": corrections._app_version(), "campaign": c.id, "beat": i,
        # The turn by the player's line: its transcript index and its number in the game.
        "turn": {"player_at": p, "number": sum(1 for j in _player_lines(c) if j <= p),
                 "beats": [p + 1, q]},
        "at": corrections._now(),
        "player_line": str(c.transcript[p].get("text") or "") if p >= 0 else "",
        "reading": reading,
        "plan": [x for _n, r in rows for x in r.get("intents") or []],
        # Everything, hidden outcomes included: the log is ours, the page the player's.
        "rows": [{"log_index": n, "kind": r.get("kind"), "ref": r.get("ref"),
                  "outcomes": r.get("outcomes") or []} for n, r in rows],
        "shown": list(shown.values()),
        "marks": picked,
        # The narrator's notes for this beat, when kept: what the scene was (the ruling
        # bench's facts) without reading the save.
        "scene_brief": str(entry.get("scene_brief") or ""),
        "snapshot": _snapshot(c, p, rid),
    }
    # The game is not touched: no turn-log row and no save. A save here rotated the
    # backups (live 2026-11-15, the first save after a restart rotates), pushing out the
    # very start-of-turn copy the next mark on the same turn would need.
    _append(rec)
    return rec


def _append(rec: dict) -> None:
    """corrections.py's appender, onto this file: one line, newline-guarded, fsynced."""
    path = log_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    lead = ""
    try:
        with path.open("rb") as fh:
            fh.seek(-1, os.SEEK_END)
            lead = "" if fh.read(1) == b"\n" else "\n"
    except OSError:
        pass
    with path.open("a", encoding="utf-8") as fh:
        fh.write(lead + json.dumps(rec, ensure_ascii=False) + "\n")
        fh.flush()
        os.fsync(fh.fileno())


def read_log(path: Path | None = None) -> list[dict]:
    return corrections.read_log(path or log_path())


def for_report() -> list[tuple[str, str]]:
    """(name in the zip, text) for the log and every snapshot it still has, or []."""
    if not log_path().is_file():
        return []
    out = [("training/engine-corrections.jsonl", log_path().read_text(encoding="utf-8"))]
    for rec in read_log():
        name = ((rec.get("snapshot") or {}).get("file") or "")
        path = corrections.training_dir() / name if name else None
        if path is not None and path.is_file():
            try:
                text = gzip.decompress(path.read_bytes()).decode("utf-8")
            except (OSError, ValueError, EOFError):
                continue
            out.append((f"training/{name[:-3]}", text))
    return out
