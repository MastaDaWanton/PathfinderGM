""""That's wrong": the player's correction of a narrated beat, put right on the page and
kept as training data for the narrator (the owner, 2026-10-09: "make a that's wrong button
and start logging those to make training data make sure there is a way to handle remakes
that are bad as well").

The narrator (a 12B model on the player's own machine) makes an error within about three
beats. Every error the player notices is two things at once: a page that is wrong now, and
the one kind of label no check in this repo can produce — a human saying *this* sentence is
false. So one click does both. The beat is remade against the engine's facts by the repair
call the narrator's own rewrite already uses (`GMAgent.repair_beat`), and every version is
logged with its verdict to `<data>/training/corrections.jsonl`.

**How it was done before, and what was taken.** SillyTavern's swipes regenerate only the
LAST reply and keep every version to flip between; its Edit works on any message
(docs.sillytavern.app/usage/chatting). Taken: only the latest turn's beats are remade, each
version is kept, and the player can write the beat themselves. An older beat has had later
beats built on it, so here it is marked wrong and logged, never remade (a swipe deep in the
context is a third-party extension, Deep-Swipe, not the tradition). TRL's dataset formats
(huggingface.co/docs/trl/dataset_formats) fix the export: DPO wants an explicit prompt with
`chosen`/`rejected`, KTO an unpaired `{prompt, completion, label}` — which is why a beat that
never got a good version is still worth logging (`tools/corrections_to_pairs.py`).

**Where a beat lives** — every store a remake has to reach, because a wrong beat left in
any of them is continued by the narrator next turn:

  * `c.transcript[i]` — the page, and the source of the narrator's `earlier`
    (`narration.own_prose`), the planner's `recent_narration`, the brief's `recent` and
    the situation cards. Its `added` (our sentences) and `said` (who spoke which line)
    travel with the text.
  * `c.history` — the assistant message `_finish` appended with the beat's text.
  * `scene.conversation_log` — the lines and sounds booked off the beat (`beat == i`),
    rebuilt from the new text by the log's own step.

What is NOT undone: the bookkeeping `_finish` did when the first version landed — people
the beat made real, a conversation it opened, a face it marked described. Those are the
engine's facts now; the remake is held to them, not the other way round.

**The input** that wrote each beat (the prose call's full messages, the tells, the brief)
is kept per campaign in `training/inputs/<campaign>.json` for the last `INPUTS_KEPT`
narrated beats, out of the save so a long campaign does not carry kilobytes of prompt per
beat. A record copies it in when an episode opens, so every line of the log stands alone.

**The log** is one JSON object per correction episode, rewritten in place (by `id`) as the
episode changes and closed when the player moves on — so the file is always a list of
whole episodes, never events to fold.
"""
from __future__ import annotations

import json
import os
import re
import time
from datetime import datetime
from pathlib import Path

from django.conf import settings

from pathfindergm import files

FORMAT = 1
# The owner's figure (2026-10-09): after three remakes the player also rejected, the panel
# stops offering another and offers writing it, putting the first back, or leaving it.
MAX_REMAKES = 3
# How many narrated beats' inputs are kept per campaign. Only the latest turn's beats can
# be remade; the rest are kept so a beat marked wrong a few turns late still logs the
# prompt that wrote it.
INPUTS_KEPT = 12
# The longest beat a player may write. An intimate beat runs to 3,000 characters; this is
# twice that, so nothing the narrator could write is refused when the player retypes it.
MAX_WRITTEN = 6000
MAX_NOTE = 400


# --- where -----------------------------------------------------------------------------

def training_dir() -> Path:
    """`<data>/training`. Read off `CAMPAIGN_DIR` as `report.data_root` and `modelcfg` read
    it, so it is `pathfindergm.paths.user_data_root()` in the app — the executable's data
    folder, never anything beside `__file__`, which lies once frozen — and a test's
    tmp_path in the suite."""
    return Path(settings.CAMPAIGN_DIR).parent / "training"


def log_path() -> Path:
    return training_dir() / "corrections.jsonl"


def _inputs_path(cid: str) -> Path:
    return files.child(training_dir() / "inputs", str(cid))


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _fingerprint(text: str) -> str:
    import hashlib

    return hashlib.sha1(str(text or "").encode("utf-8")).hexdigest()[:16]


# --- the log ---------------------------------------------------------------------------

def read_log(path: Path | None = None) -> list[dict]:
    """Every record in the log, oldest first. A line that does not parse is skipped, not
    fatal: a hand-edited file must not take the table down."""
    path = path or log_path()
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError:
        return []
    out = []
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except ValueError:
            continue
        if isinstance(rec, dict):
            out.append(rec)
    return out


def _write_record(rec: dict) -> None:
    """Put `rec` into the log, replacing the record with its `id` or appending. Whole-file
    and atomic (`files.write_text`): the log is small next to the saves, and a log that is
    always whole episodes is one a trainer can read without folding events."""
    rec["updated"] = _now()
    records = read_log()
    for i, old in enumerate(records):
        if old.get("id") == rec["id"]:
            records[i] = rec
            break
    else:
        records.append(rec)
    files.write_text(log_path(), "".join(json.dumps(r, ensure_ascii=False) + "\n"
                                         for r in records))


def _record(rid: str) -> dict | None:
    return next((r for r in read_log() if r.get("id") == rid), None)


def count() -> dict:
    """How many corrections are logged, for the Settings line."""
    records = read_log()
    return {"episodes": len(records),
            "versions": sum(len(r.get("versions") or []) for r in records),
            "folder": str(training_dir()), "file": str(log_path()),
            "exists": log_path().is_file()}


# --- the input that wrote a beat -------------------------------------------------------

def _read_inputs(cid: str) -> dict:
    try:
        data = json.loads(_inputs_path(cid).read_text(encoding="utf-8"))
    except (OSError, ValueError, files.BadName):
        return {}
    return data if isinstance(data, dict) and data.get("format") == FORMAT else {}


def remember_input(c, beat_index: int, *, agent, player_input: str, brief: str,
                   facts: list[str]) -> None:
    """Keep what wrote the beat at `beat_index`: the prose call's whole messages, the model
    whose beat stood, the engine's tells and the scene brief the repair call is given, and
    whether the content rule fired. Called by `_finish` once the beat is on the
    transcript. Never costs the turn: a disk that will not take it loses the input, not
    the beat."""
    try:
        beat = c.transcript[beat_index]
        intimate = bool(getattr(agent, "_intimate_beat", lambda: False)())
        entry = {
            "beat": beat_index, "fingerprint": _fingerprint(beat.get("text")),
            "at": _now(),
            "messages": list(getattr(agent, "last_prose_messages", None) or []),
            "narrator_model": str(getattr(agent, "last_prose_model", "") or
                                  getattr(agent, "prose_model", "") or ""),
            "draft": str(getattr(agent, "last_prose_draft", "") or ""),
            "player_input": str(player_input or ""), "scene_brief": str(brief or ""),
            "facts": [str(f) for f in (facts or []) if f],
            "intimate": intimate,
        }
        data = _read_inputs(c.id) or {"format": FORMAT, "campaign": c.id, "beats": {}}
        beats = dict(data.get("beats") or {})
        beats[str(beat_index)] = entry
        keep = sorted(beats, key=int)[-INPUTS_KEPT:]
        data["beats"] = {k: beats[k] for k in keep}
        files.write_text(_inputs_path(c.id), json.dumps(data, ensure_ascii=False))
    except Exception as exc:  # noqa: BLE001 — bookkeeping never loses a turn
        c.turn_log.append({"kind": "correction-input-lost", "beat": beat_index,
                           "error": f"{type(exc).__name__}: {str(exc)[:160]}"})


def input_for(c, i: int, original: str | None = None, inputs: dict | None = None
              ) -> dict | None:
    """The kept input for beat `i`, or None — also None when the beat on disk is not the
    beat the input wrote (its first version's fingerprint differs). `inputs` is the file
    already read, for a caller asking about several beats."""
    data = inputs if inputs is not None else _read_inputs(c.id)
    entry = (data.get("beats") or {}).get(str(i))
    if not isinstance(entry, dict):
        return None
    if original is None:
        original = _versions(c.transcript[i])[0]["text"] if i < len(c.transcript) else ""
    if entry.get("fingerprint") != _fingerprint(original):
        return None
    return entry


# --- what a beat is --------------------------------------------------------------------

def _is_narrated(beat) -> bool:
    """The narrator's prose: a GM beat of kind "setup", the beats `narration.own_prose`
    shows the narrator as its own. Never the engine's lines (consequence), asides or the
    player's words."""
    return isinstance(beat, dict) and beat.get("who") == "gm" and beat.get("kind") == "setup"


def last_player_line(c) -> int:
    """The transcript index of the player's last in-fiction line, -1 for none. An aside (a
    question to the GM out of character) is not moving on."""
    for i in range(len(c.transcript) - 1, -1, -1):
        b = c.transcript[i]
        if isinstance(b, dict) and b.get("who") == "player" and b.get("kind") != "aside":
            return i
    return -1


def _versions(beat: dict) -> list[dict]:
    fix = beat.get("fix") or {}
    vs = fix.get("versions")
    if isinstance(vs, list) and vs:
        return vs
    return [{"text": str(beat.get("text") or ""), "by": "narrator",
             **({"added": list(beat["added"])} if beat.get("added") else {}),
             **({"said": [dict(r) for r in beat["said"]]} if beat.get("said") else {})}]


def status(c, i: int, inputs: dict | None = None) -> dict:
    """What the page may offer on beat `i`. `remake` only on the latest turn's beats whose
    input was kept, while no roll waits and the game goes on; `remakes_left` counts down
    from `MAX_REMAKES`; `put_back` once a version other than the first is on the page."""
    if not (0 <= i < len(c.transcript)) or not _is_narrated(c.transcript[i]):
        return {"flaggable": False}
    beat = c.transcript[i]
    fix = beat.get("fix") or {}
    current = i > last_player_line(c) and not c.ended and not c.scene.awaiting
    versions = _versions(beat)
    on = int(fix.get("on", 0) or 0) if fix.get("versions") else 0
    remakes = sum(1 for v in versions if v.get("by") == "remake")
    has_input = current and input_for(c, i, versions[0]["text"], inputs) is not None
    closed = bool(fix.get("closed"))
    by = versions[on].get("by", "narrator") if on < len(versions) else "narrator"
    return {
        # The player's own words are not the narrator's to be marked wrong; they are
        # written again instead.
        "flaggable": not closed and by != "player",
        "current": current,
        "remake": bool(has_input and remakes < MAX_REMAKES and not closed),
        "remakes": remakes,
        "remakes_left": max(0, MAX_REMAKES - remakes) if has_input else 0,
        "write": current and not closed,
        "put_back": current and on != 0 and not closed,
        # A remake on the page, not yet kept by hand.
        "keep": (current and bool(fix.get("open")) and by == "remake"
                 and fix.get("kept") != on),
        "kept": bool(fix.get("open")) and fix.get("kept") == on,
        "by": by,
        "versions": len(versions),
        "open": bool(fix.get("open")),
        "outcome": str(fix.get("outcome") or ""),
    }


def page_state(c) -> dict:
    """For `_state`: what each beat the page needs to know about offers. Every narrated
    beat may be marked wrong; only these carry more than that, so the state stays small
    on a campaign of hundreds of beats — the current turn's beats, and any beat that has
    a correction on it."""
    out: dict[str, dict] = {}
    start = last_player_line(c) + 1
    inputs = _read_inputs(c.id)
    for i, b in enumerate(c.transcript):
        if not _is_narrated(b):
            continue
        if i >= start or b.get("fix"):
            out[str(i)] = status(c, i, inputs)
    return {"beats": out, "max_remakes": MAX_REMAKES}


# --- the stores ------------------------------------------------------------------------

def _kept_said(records, text: str) -> list[dict]:
    """The speaker records whose line still stands in `text`, and a reworded line moved
    onto the one quotation that is mostly its words (`views._realigned`) — the same rule
    `_finish` keeps the records by after a rewrite."""
    from gm import speech as speech_mod

    from .views import _realigned

    lines = speech_mod.lines(text)
    kept = []
    for r in records or []:
        if isinstance(r, dict) and r.get("who") and r not in kept and any(
                speech_mod.speaker([r], ln) for ln in lines):
            kept.append(dict(r))
    return kept + _realigned(list(records or []), kept, text)


def _apply(c, i: int, version: dict) -> None:
    """Put `version` on beat `i` in every store the game keeps a beat in (module doc)."""
    beat = c.transcript[i]
    old = str(beat.get("text") or "")
    text = str(version.get("text") or "")
    beat["text"] = text
    for key in ("added", "said"):
        if version.get(key):
            beat[key] = [dict(x) if isinstance(x, dict) else x for x in version[key]]
        else:
            beat.pop(key, None)
    # The history the planner reads: the assistant message `_finish` wrote with this
    # beat's text. The last one that matches, because an identical earlier beat (a
    # holding line said twice) is not this one.
    for m in reversed(c.history or []):
        if m.get("role") == "assistant" and m.get("content") == old:
            m["content"] = text
            break
    # The conversation log: what the old version booked goes, what this one says is
    # booked by the log's own step. The player's own words (`src: player`) were said
    # before the beat and stay.
    scene = c.scene
    log = [e for e in (getattr(scene, "conversation_log", None) or []) if isinstance(e, dict)]
    scene.conversation_log = [e for e in log
                              if not (e.get("beat") == i and e.get("src") != "player")]
    try:
        from .aftermath import context
        from .aftermath import conversation_log as conv

        conv.step(context("beat", "carry_on", c, text=text,
                          said=list(beat.get("said") or []), beat_index=i, turn=i))
    except Exception as exc:  # noqa: BLE001 — the page change stands without the log
        c.turn_log.append({"kind": "aftermath-error", "member": "conversation_log",
                           "error": f"{type(exc).__name__}: {str(exc)[:160]}"})


# --- an episode ------------------------------------------------------------------------

def _app_version() -> str:
    try:
        from . import report

        return report.app_version()
    except Exception:  # noqa: BLE001
        return "unknown"


def _open(c, i: int) -> tuple[dict, dict]:
    """The beat's open episode (its `fix` and its log record), made on first use: the
    version on the page now becomes version 0, by the narrator."""
    beat = c.transcript[i]
    fix = beat.get("fix") or {}
    rec = _record(fix["id"]) if fix.get("id") and fix.get("open") else None
    if rec is not None and fix.get("versions"):
        return fix, rec
    versions = _versions(beat)
    entry = input_for(c, i, versions[0]["text"])
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    rid = f"{c.id}-{i}-{stamp}-{os.urandom(2).hex()}"
    # An open episode whose record went missing (the folder was emptied mid-turn) starts
    # a new record from the versions the beat still holds, on the one on the page.
    on = int(fix.get("on", 0) or 0) if fix.get("versions") else 0
    fix = {"id": rid, "open": True, "on": min(on, len(versions) - 1), "versions": versions}
    beat["fix"] = fix
    from gm import narration as narration_mod

    rec = {
        "format": FORMAT, "id": rid, "app_version": _app_version(),
        "narrator_model": (entry or {}).get("narrator_model", ""),
        "campaign": c.id, "beat": i, "started": _now(),
        "intimate": bool((entry or {}).get("intimate")),
        "input": ({"captured": True,
                   **{k: entry.get(k) for k in ("messages", "player_input", "scene_brief",
                                                "facts", "draft", "narrator_model")}}
                  if entry else {"captured": False,
                                 # What can still be said about it: the player's line it
                                 # answered. The prompt itself was not kept (an NPC's turn,
                                 # the opening, or a beat older than the inputs kept).
                                 "player_input": _player_line_before(c, i)}),
        "versions": [{"n": n, "by": v.get("by", "narrator"), "text": v["text"],
                      # What the narrator is shown of this beat as its own: our appended
                      # sentences taken back out (`narration.strip_added`).
                      "model_text": narration_mod.strip_added(v["text"], v.get("added")),
                      "at": _now(), "flagged_sentences": [], "note": "",
                      "verdict": None}
                     for n, v in enumerate(versions)],
        "outcome": "open", "closed": False,
    }
    return fix, rec


def _player_line_before(c, i: int) -> str:
    for j in range(i - 1, -1, -1):
        b = c.transcript[j]
        if isinstance(b, dict) and b.get("who") == "player":
            return str(b.get("text") or "")
    return ""


def _flag(rec: dict, on: int, sentences: list[str], note: str) -> None:
    """The version on the page is wrong: its verdict, the sentences and the note."""
    v = rec["versions"][on]
    v["verdict"] = "wrong"
    v.pop("implicit", None)
    seen = list(v.get("flagged_sentences") or [])
    v["flagged_sentences"] = seen + [s for s in sentences if s not in seen]
    if note:
        v["note"] = (v.get("note") + " | " + note) if v.get("note") else note


def _outcome(rec: dict, on: int) -> str:
    """What became of the episode. The player's last decision when they made one (put it
    back, wrote it, kept it, left it); else read off the version on the page."""
    if rec.get("outcome") not in (None, "", "open"):
        return rec["outcome"]
    v = rec["versions"][on]
    if v.get("verdict") == "wrong":
        return "left wrong"
    if v.get("by") == "player":
        return "player wrote"
    if v.get("by") == "remake":
        return "remake kept"
    return "put back" if len(rec["versions"]) > 1 else "left wrong"


def _picked(text: str, sentences) -> list[str]:
    """The sentences the player picked that are really in the beat, in its order. The page
    splits the beat itself; anything that is not a span of the text is dropped."""
    out = []
    for s in sentences or []:
        s = re.sub(r"\s+", " ", str(s or "")).strip()
        if s and s in re.sub(r"\s+", " ", text) and s not in out:
            out.append(s)
    return out[:20]


class Refused(Exception):
    """A correction the page should not have offered, with the sentence to show."""

    def __init__(self, words: str, status: int = 409):
        super().__init__(words)
        self.words, self.status = words, status


def _turn_row(c, i: int, rec: dict, what: str) -> None:
    c.turn_log.append({"kind": "correction", "beat": i, "id": rec["id"], "did": what,
                       "versions": len(rec["versions"]), "outcome": rec["outcome"]})


def mark(c, i: int, sentences=None, note: str = "") -> dict:
    """Marked wrong and left as it is: an older beat (later beats stand on it, so it is not
    remade), or the player choosing to leave it. Closes the episode."""
    st = status(c, i)
    if not st.get("flaggable"):
        raise Refused("That beat cannot be marked.")
    fix, rec = _open(c, i)
    on = fix["on"]
    _flag(rec, on, _picked(fix["versions"][on]["text"], sentences),
          str(note or "")[:MAX_NOTE].strip())
    rec["outcome"] = "left wrong"
    _close(c.transcript[i], rec)
    _write_record(rec)
    _turn_row(c, i, rec, "marked")
    return rec


def remake(c, i: int, sentences=None, note: str = "", *, agent=None) -> dict:
    """Mark the version on the page wrong and have the narrator write the beat again
    against the engine's facts, through the repair call its own rewrite uses
    (`GMAgent.repair_beat`). The remake replaces the beat in every store."""
    st = status(c, i)
    if not st.get("current"):
        raise Refused("Only the latest turn can be remade. Mark this one wrong instead, "
                      "or write it yourself.")
    if not st.get("remake"):
        if st.get("remakes", 0) >= MAX_REMAKES:
            raise Refused(f"It has been remade {MAX_REMAKES} times. Write it yourself, "
                          f"put the first one back, or leave it.")
        raise Refused("The narrator's notes for this beat were not kept, so it cannot be "
                      "remade. Write it yourself, or mark it wrong.")
    fix, rec = _open(c, i)
    on = fix["on"]
    current = fix["versions"][on]
    picked = _picked(current["text"], sentences)
    note = str(note or "")[:MAX_NOTE].strip()
    _flag(rec, on, picked, note)
    entry = input_for(c, i, fix["versions"][0]["text"]) or {}

    from gm import narration as narration_mod
    from gm import prompts
    from gm.agent import GMAgent

    if agent is None:
        agent = GMAgent(c.world, c.engine())
    agent.last_said = []
    earlier = narration_mod.own_prose(c.transcript[:i])
    complaint = prompts.player_marked_wrong(picked, note)
    started = time.monotonic()
    try:
        text, attempt, messages = agent.repair_beat(
            current["text"], complaint, entry.get("player_input", ""),
            entry.get("scene_brief", ""), facts=entry.get("facts") or None,
            intimate=bool(entry.get("intimate")), earlier=earlier,
            note="the player marked it wrong")
    except Exception as exc:
        # Kept: the player DID say the beat is wrong, whatever the model then did.
        rec.setdefault("failed_remakes", []).append(
            {"at": _now(), "error": f"{type(exc).__name__}: {str(exc)[:200]}",
             "seconds": round(time.monotonic() - started, 1)})
        rec["outcome"] = "open"
        _write_record(rec)
        c.save()
        raise
    if not text.strip() or narration_mod.ends_unfinished(text):
        rec.setdefault("failed_remakes", []).append(
            {"at": _now(), "error": "the remake came back empty or cut off",
             "raw": attempt.raw, "repair_messages": messages,
             "seconds": round(attempt.seconds, 1)})
        _write_record(rec)
        c.save()
        raise Refused("The narrator gave back nothing usable, so the beat is as it was. "
                      "Try again, or write it yourself.", status=502)

    added = [s for s in (current.get("added") or [])
             if s in narration_mod._sentences(text)]
    said = _kept_said(list(agent.last_said or []) + list(current.get("said") or []), text)
    version = {"text": text, "by": "remake",
               **({"added": added} if added else {}), **({"said": said} if said else {})}
    fix["versions"].append(version)
    fix["on"] = len(fix["versions"]) - 1
    rec["versions"].append({
        "n": fix["on"], "by": "remake", "text": text,
        "model_text": narration_mod.strip_added(text, added),
        "model": attempt.model, "at": _now(), "seconds": round(attempt.seconds, 1),
        "raw": attempt.raw, "page_notes": attempt.note,
        # The remake call's own prompt: a remake the player rejects is a training
        # example for the repair call as well as the narrator.
        "repair_messages": messages,
        "flagged_sentences": [], "note": "", "verdict": None})
    rec["outcome"] = "open"
    _apply(c, i, version)
    _write_record(rec)
    _turn_row(c, i, rec, "remade")
    return rec


def write(c, i: int, text: str, sentences=None, note: str = "") -> dict:
    """The player's own words become the beat: the best training example there is."""
    st = status(c, i)
    if not st.get("write"):
        raise Refused("Only the latest turn can be rewritten. Mark this one wrong instead.")
    text = re.sub(r"[ \t]+", " ", str(text or "")).strip()
    if not text:
        raise Refused("Write the beat first.", status=400)
    if len(text) > MAX_WRITTEN:
        raise Refused(f"That is longer than a beat can be ({MAX_WRITTEN} characters).",
                      status=400)
    fix, rec = _open(c, i)
    on = fix["on"]
    current = fix["versions"][on]
    if text == current["text"]:
        raise Refused("That is the beat as it stands. Change it, or keep it.", status=400)
    _flag(rec, on, _picked(current["text"], sentences), str(note or "")[:MAX_NOTE].strip())
    said = _kept_said(current.get("said") or [], text)
    version = {"text": text, "by": "player", **({"said": said} if said else {})}
    fix["versions"].append(version)
    fix["on"] = len(fix["versions"]) - 1
    rec["versions"].append({"n": fix["on"], "by": "player", "text": text,
                            "model_text": text, "at": _now(),
                            "flagged_sentences": [], "note": "",
                            # Saved by the player's own hand: an explicit keep.
                            "verdict": "kept", "implicit": False})
    rec["outcome"] = "player wrote"
    _apply(c, i, version)
    _write_record(rec)
    _turn_row(c, i, rec, "written")
    return rec


def put_back(c, i: int) -> dict:
    """The first version back on the page, everywhere. The version it replaces is
    `reverted` unless the player already called it wrong."""
    st = status(c, i)
    if not st.get("put_back"):
        raise Refused("There is nothing to put back.")
    fix, rec = _open(c, i)
    on = fix["on"]
    v = rec["versions"][on]
    if v.get("verdict") != "wrong":
        v["verdict"] = "reverted"
        v.pop("implicit", None)
    fix["on"] = 0
    rec["outcome"] = "put back"
    _apply(c, i, fix["versions"][0])
    _write_record(rec)
    _turn_row(c, i, rec, "put back")
    return rec


def keep(c, i: int) -> dict:
    """The version on the page is right: an explicit keep, which training weighs above the
    implicit one moving on gives."""
    st = status(c, i)
    if not st.get("keep"):
        raise Refused("There is nothing to keep.")
    fix, rec = _open(c, i)
    on = fix["on"]
    v = rec["versions"][on]
    v["verdict"] = "kept"
    v["implicit"] = False
    fix["kept"] = on
    rec["outcome"] = "remake kept"
    _write_record(rec)
    _turn_row(c, i, rec, "kept")
    return rec


def _close(beat: dict, rec: dict) -> None:
    """The episode is over: the record says so, and the beat keeps only a marker. The
    versions came off the save — the log has them, and an old beat is never remade."""
    rec["closed"] = True
    rec["closed_at"] = _now()
    beat["fix"] = {"id": rec["id"], "closed": True, "outcome": rec["outcome"],
                   "versions": len(rec["versions"])}


def settle(c) -> None:
    """The player moved on: every open episode behind their last line is closed, and the
    version on the page is kept — `implicit: true`, because moving on is weaker evidence
    than pressing Keep. Called by `_finish` before the new beat is written; also safe to
    call anywhere else, since it only ever closes what a player line has passed."""
    last = last_player_line(c)
    for i, beat in enumerate(c.transcript):
        if i >= last or not isinstance(beat, dict):
            continue
        fix = beat.get("fix") or {}
        if not fix.get("open"):
            continue
        rec = _record(fix.get("id", ""))
        if rec is None:
            beat["fix"] = {"id": fix.get("id", ""), "closed": True, "outcome": "lost"}
            continue
        on = int(fix.get("on", 0) or 0)
        v = rec["versions"][min(on, len(rec["versions"]) - 1)]
        if v.get("verdict") is None:
            v["verdict"] = "kept"
            v["implicit"] = True
        rec["outcome"] = _outcome(rec, min(on, len(rec["versions"]) - 1))
        _close(beat, rec)
        _write_record(rec)


# --- for the report --------------------------------------------------------------------

def for_report() -> str | None:
    """The log as the developer's report carries it, or None when there is none.

    An intimate beat's input carries the table's own passages (homebrew/style/intimate.txt
    shown to the model as demonstrations), which the turn log has never held ("counts
    only, never the text", gm/intimate.py). The local log keeps them — they are the
    prompt, and a training example without its prompt is worth little — but a report
    leaves the player's machine, so there the messages are withheld and said to be."""
    if not log_path().is_file():
        return None
    out = []
    for rec in read_log():
        if rec.get("intimate") and (rec.get("input") or {}).get("messages"):
            rec = dict(rec)
            rec["input"] = {k: v for k, v in rec["input"].items() if k != "messages"}
            rec["input"]["messages_withheld"] = ("an intimate scene: the table's own "
                                                 "passages stay on this machine")
            rec["versions"] = [{k: v for k, v in ver.items() if k != "repair_messages"}
                               for ver in rec.get("versions") or []]
        out.append(json.dumps(rec, ensure_ascii=False))
    return "".join(line + "\n" for line in out)


def open_folder() -> str:
    """Open the training folder in the system's file browser; the folder's path back.
    `os.startfile` as `preflight` opens the installer: through the shell, as a double-
    click would, with no pipes to hold."""
    folder = training_dir()
    folder.mkdir(parents=True, exist_ok=True)
    if os.name == "nt":
        os.startfile(str(folder))                                      # noqa: S606
    else:
        import subprocess

        subprocess.Popen(["open" if os.uname().sysname == "Darwin" else "xdg-open",
                          str(folder)])
    return str(folder)
