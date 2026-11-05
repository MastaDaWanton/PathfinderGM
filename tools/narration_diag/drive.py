"""The narration diagnosis bench's driver: plays turns in-process through the real view
endpoints and records everything a turn's narration was made of.

    # one turn, e.g. to build a scenario's snapshot (cwd = the repo):
    python tools/narration_diag/drive.py play <data_dir> <snapshot.json|-> "<line>" <face|-> \\
        <out.jsonl> <tag> [--keep <snapshot_out.json>]
    # a batch of jobs, resumable (a job already in out.jsonl is skipped):
    python tools/narration_diag/drive.py run <data_dir> <jobs.jsonl> <out.jsonl>

A job is one JSON line: {"job", "item", "activity", "snap", "line", "face", "rep", "cond"}.
`cond` picks the levers (`CONDITIONS`): the slot temperature and best-of-N for act slots;
every condition has the tells check on, as the app does. Nothing here changes a default:
the levers are applied by `trace.py`'s wrappers in this process only.

Private saves stay outside the repo: the data dir, snapshots and jobs are scratch paths
given on the command line, and so are the lines (they name the save's people).

Each record holds: the job, the engine's tells (turn, resolution and NPC-turn rows), the
pages shipped this turn, the planned beat (slots, instructions, every answer, the tells
check's reads and remakes), every text change the pipeline made with the function that
made it, every model call's raw reply and who asked, the turn log rows, and the seconds.
Measured why in-process: a fresh process per turn costs 6.5 s of Django and view imports
before the first request (2026-11-04), about an hour over a 700-turn bench."""
from __future__ import annotations

import json
import os
import shutil
import sys
import time
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

CONDITIONS = {
    "base": {"slot_temperature": None, "best_of": 1},
    # The default condition on later code: a before-and-after rerun names its side.
    "fixed": {"slot_temperature": None, "best_of": 1},
    "r2": {"slot_temperature": None, "best_of": 1},
    "t04": {"slot_temperature": 0.4, "best_of": 1},
    "t01": {"slot_temperature": 0.1, "best_of": 1},
    "bo3": {"slot_temperature": None, "best_of": 3},
    # The model arm (2026-11-04, the owner: "include stock gemma4 in the model comparison"):
    # stock gemma4:12b (Apache 2.0) on the prose role, at today's slot temperature and at
    # the temperature arm's best.
    "stock": {"slot_temperature": None, "best_of": 1, "prose_model": "gemma4:12b"},
    "stock-t04": {"slot_temperature": 0.4, "best_of": 1, "prose_model": "gemma4:12b"},
    "stock-t01": {"slot_temperature": 0.1, "best_of": 1, "prose_model": "gemma4:12b"},
}
for _c in CONDITIONS.values():
    _c.setdefault("prose_model", None)


def _setup(data: Path):
    os.environ["PATHFINDER_GM_DATA"] = str(data)
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "pathfindergm.settings")
    # The app's own default: the tells check on (`planned.tells_check_on`), the first read
    # alone (`beat_verify.TELLS_VETO`). A stray bench variable from another shell is cleared.
    for k in ("PATHFINDER_GM_TELLS_CHECK", "PATHFINDER_GM_TELLS_VETO"):
        os.environ.pop(k, None)
    sys.path.insert(0, str(ROOT))
    os.chdir(ROOT)
    import django

    django.setup()
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import diagtrace as diag_trace  # noqa: E402

    diag_trace.install()
    return diag_trace


def _restore(data: Path, snap: str) -> Path:
    """The snapshot as the active campaign, under its own id; returns the save's path."""
    camps = data / "campaigns"
    camps.mkdir(parents=True, exist_ok=True)
    cid = json.loads(Path(snap).read_text(encoding="utf-8"))["id"]
    for old in camps.glob(f"{cid}.json*"):
        old.unlink()
    shutil.copy(snap, camps / f"{cid}.json")
    (camps / "active.txt").write_text(cid, encoding="utf-8")
    return camps / f"{cid}.json"


def _fresh_caches():
    """What a fresh process would not carry from the last turn."""
    from gm import beat_verify
    from play import campaign as cm

    cm._LIVE.clear()
    for name in ("_CACHE", "_FELLED"):
        d = getattr(beat_verify, name, None)
        if isinstance(d, dict):
            d.clear()


def _new_rows(before: dict, after: dict) -> list[dict]:
    """The turn log rows this turn wrote (the log is capped in the save)."""
    tl, n_tl = after.get("turn_log") or [], len(before.get("turn_log") or [])
    if len(tl) > n_tl:
        return tl[n_tl:]
    turns_before = [json.dumps(r, sort_keys=True) for r in before.get("turn_log") or []
                    if r.get("kind") == "turn"]
    last = turns_before[-1] if turns_before else None
    for i in range(len(tl) - 1, -1, -1):
        if json.dumps(tl[i], sort_keys=True) == last:
            cut = next((j for j in range(i + 1, len(tl)) if tl[j].get("kind") == "turn"),
                       len(tl))
            return tl[cut:]
    return tl


def play_one(diag, data: Path, snap: str, line: str, face, *, seed_key: str = "",
             keep: str = "") -> dict:
    from django.test import Client

    camp = _restore(data, snap) if snap != "-" else None
    if camp is None:
        cid = (data / "campaigns" / "active.txt").read_text(encoding="utf-8").strip()
        camp = data / "campaigns" / f"{cid}.json"
    _fresh_caches()
    before = json.loads(camp.read_text(encoding="utf-8"))
    n_tr = len(before["transcript"])
    c = Client()
    c.get("/play/")
    diag.reset(seed_key)
    diag.STATE["on"] = True
    started = time.monotonic()
    rolls, err = [], None
    try:
        r = c.post("/api/say", data=json.dumps({"text": line}),
                   content_type="application/json")
        state = r.json() if r.status_code == 200 else {"error": r.content.decode()[:400]}
        for _ in range(12):
            aw = (state or {}).get("awaiting") or ((state or {}).get("scene") or {}).get(
                "awaiting")
            if not aw:
                break
            rolls.append({"label": aw.get("label"), "dc": aw.get("dc"),
                          "because": aw.get("because")})
            body = {"face": int(face)} if face not in ("-", None, "") else {}
            r = c.post("/api/roll", data=json.dumps(body), content_type="application/json")
            state = r.json() if r.status_code == 200 else {"error": r.content.decode()[:400]}
            if body and "gives a result between" in str(state.get("error") or ""):
                # The face is for the d20; a damage die rolls its own.
                r = c.post("/api/roll", data=json.dumps({}), content_type="application/json")
                state = r.json() if r.status_code == 200 else {
                    "error": r.content.decode()[:400]}
        err = state.get("error") if isinstance(state, dict) else None
    except Exception as exc:  # noqa: BLE001 — a turn that raises is a row, not the end
        err = f"{type(exc).__name__}: {exc}\n{traceback.format_exc()[-1500:]}"
    finally:
        diag.STATE["on"] = False
    wall = time.monotonic() - started
    after = json.loads(camp.read_text(encoding="utf-8"))
    rows = _new_rows(before, after)
    tells = []
    for row in rows:
        if row.get("kind") in ("turn", "resolution", "npc-turn"):
            tells += [{"op": o.get("op"), "status": o.get("status"), "tell": o.get("tell"),
                       "actor": o.get("actor"), "kind": row.get("kind")}
                      for o in row.get("outcomes") or []]
    trace = diag.snapshot()
    if not trace.get("pc"):
        try:
            from play import campaign as cm

            trace["pc"] = cm.current().scene.pc().name
        except Exception:  # noqa: BLE001 — a name to match by, nothing more
            pass
    rec = {"line": line, "snap": snap, "wall": round(wall, 1), "rolls": rolls,
           "error": err, "tells": tells,
           "beats": [{"who": e.get("who"), "kind": e.get("kind"), "text": e.get("text")}
                     for e in after["transcript"][n_tr:]],
           "rows": rows, "trace": trace,
           "clock": after.get("scene", {}).get("clock_minutes")}
    if keep:
        Path(keep).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(camp, keep)
    return rec


def _show(rec: dict, tag: str) -> None:
    print(f"[{tag}] {rec['wall']:.0f}s rolls={len(rec['rolls'])} err={str(rec['error'])[:200]}",
          flush=True)
    for t in rec["tells"]:
        print("  TELL", t["op"], t["status"], "|", (t["tell"] or "")[:240], flush=True)
    for b in rec["beats"]:
        if b.get("who") == "gm":
            print("  PAGE", b.get("kind"), "|", b.get("text"), flush=True)


class _Replayer:
    """Every model call of a recorded turn answered with the reply it got then, so a turn
    can be played again OFFLINE on changed pipeline code (2026-11-05, round 2: "measure
    each decision on the recorded beats … by replaying the slot outputs offline").

    A reply is matched by who asked (the same four gm/ frames `diagtrace` records) and the
    slot, in order: the turn's calls before the code that changed are the same calls, so
    each gets its own reply back, and the engine resolves the same intents with the same
    seeded dice. A call the record never made — a repair the changed code now asks that
    the old one did not — is a miss: refused (the caller's own failure path) or, with
    `live`, sent to the model. Unconsumed replies are the calls the changed code no
    longer makes."""

    def __init__(self, real, live: bool = False):
        self.real, self.live = real, live
        self.queues: dict = {}
        self.served = 0
        self.missed: list[str] = []

    def load(self, rec: dict) -> None:
        self.queues = {}
        self.served, self.missed = 0, []
        for c in (rec.get("trace") or {}).get("chats") or []:
            self.queues.setdefault((c.get("who"), c.get("slot")), []).append(c)

    def __call__(self, messages, model, host="http://localhost:11434", as_json=False,
                 temperature=0.8, *a, **kw):
        import diagtrace as diag_trace  # noqa: E402 — on the path once `_setup` ran
        from gm import client

        who = _who()
        slot = (getattr(diag_trace._LOCAL, "slot", None) or {}).get("key")
        q = self.queues.get((who, slot)) or []
        if q:
            c = q.pop(0)
            self.served += 1
            if c.get("error"):
                raise RuntimeError(f"replayed failure: {c['error']}")
            return client.Reply(text=c.get("raw") or "",
                                seconds=float(c.get("seconds") or 0),
                                model=c.get("model") or model)
        self.missed.append(f"{who} [{slot}]")
        if self.live:
            return self.real(messages, model, host, as_json, temperature, *a, **kw)
        raise RuntimeError(f"replay: no recorded reply for {who} [{slot}]")


def _who() -> str:
    """`diagtrace._caller`, seen from one frame deeper (the replayer sits under its
    wrapper)."""
    names = []
    f = sys._getframe(2)
    while f is not None and len(names) < 4:
        mod = f.f_globals.get("__name__", "")
        if mod.startswith(("gm.", "play.")) and mod != "gm.client" and not mod.startswith(
                "tools."):
            names.append(f"{mod.split('.')[-1]}.{f.f_code.co_name}")
        f = f.f_back
    return " < ".join(names)


def replay(argv: list[str]) -> None:
    """replay <data_dir> <recorded.jsonl> <out.jsonl> <faces.json> [--live] [--only a,b]
    [--snaps <dir>]: every recorded turn played again with its own replies.
    `faces.json` maps item -> the d20 face its job rolled; `--snaps` re-roots the records'
    snapshot paths (a copy of the kit, never the kit itself)."""
    data, recorded, out, faces_path = argv[:4]
    live = "--live" in argv
    only = set(argv[argv.index("--only") + 1].split(",")) if "--only" in argv else None
    snaps = argv[argv.index("--snaps") + 1] if "--snaps" in argv else ""
    faces = json.loads(Path(faces_path).read_text(encoding="utf-8"))
    os.environ["PATHFINDER_GM_DATA"] = str(data)
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "pathfindergm.settings")
    sys.path.insert(0, str(ROOT))
    os.chdir(ROOT)
    import django

    django.setup()
    from gm import client

    rep = _Replayer(client.chat, live=live)
    client.chat = rep
    diag = _setup(Path(data))
    diag.LEVERS.update(CONDITIONS["fixed"], seed=False)
    done = set()
    if Path(out).exists():
        for raw in open(out, encoding="utf-8"):
            try:
                done.add(json.loads(raw)["job"])
            except (ValueError, KeyError):
                pass
    recs = [json.loads(x) for x in open(recorded, encoding="utf-8") if x.strip()]
    for n, rec in enumerate(recs, 1):
        if (only and rec["item"] not in only) or rec["job"] in done:
            continue
        snap = rec["snap"]
        if snaps:
            snap = str(Path(snaps) / Path(snap).parent.name / Path(snap).name)
        rep.load(rec)
        new = play_one(diag, Path(data), snap, rec["line"], faces.get(rec["item"], "-"),
                       seed_key="")
        new.update({k: rec[k] for k in ("job", "item", "activity", "rep")}, cond="replay")
        left = sum(len(q) for q in rep.queues.values())
        was = [b.get("text") for b in rec["beats"] if b.get("who") == "gm"]
        now = [b.get("text") for b in new["beats"] if b.get("who") == "gm"]
        new["replay"] = {"served": rep.served, "missed": rep.missed, "unused": left,
                         "same_page": was == now, "was": was}
        with open(out, "a", encoding="utf-8") as f:
            f.write(json.dumps(new, ensure_ascii=False) + "\n")
        print(f"({n}/{len(recs)}) {rec['job']} served={rep.served} missed={len(rep.missed)}"
              f" unused={left} same={was == now}", flush=True)
    print("REPLAY-DONE", flush=True)


def main(argv: list[str]) -> None:
    mode = argv[0]
    if mode == "replay":
        replay(argv[1:])
        return
    if mode == "play":
        data, snap, line, face, out, tag = argv[1:7]
        keep = argv[argv.index("--keep") + 1] if "--keep" in argv else ""
        cond = argv[argv.index("--cond") + 1] if "--cond" in argv else "base"
        diag = _setup(Path(data))
        diag.LEVERS.update(CONDITIONS[cond])
        rec = play_one(diag, Path(data), snap, line, face, seed_key=tag, keep=keep)
        rec.update(tag=tag, cond=cond)
        with open(out, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        _show(rec, tag)
    elif mode == "run":
        data, jobs, out = argv[1:4]
        done = set()
        if Path(out).exists():
            for raw in open(out, encoding="utf-8"):
                try:
                    done.add(json.loads(raw)["job"])
                except (ValueError, KeyError):
                    pass
        todo = [json.loads(x) for x in open(jobs, encoding="utf-8") if x.strip()]
        todo = [j for j in todo if j["job"] not in done]
        print(f"{len(done)} done, {len(todo)} to run", flush=True)
        diag = _setup(Path(data))
        for n, job in enumerate(todo, 1):
            diag.LEVERS.update(CONDITIONS[job["cond"]])
            # The seed is the item's and the rep's, not the condition's: the levers are
            # compared on common random numbers as far as the sampler allows.
            rec = play_one(diag, Path(data), job["snap"], job["line"], job.get("face", "-"),
                           seed_key=f"{job['item']}|{job['rep']}")
            rec.update({k: job[k] for k in ("job", "item", "activity", "rep", "cond")})
            with open(out, "a", encoding="utf-8") as f:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            print(f"({n}/{len(todo)})", end=" ")
            _show(rec, job["job"])
        print("RUN-DONE", flush=True)
    else:
        raise SystemExit(__doc__)


if __name__ == "__main__":
    main(sys.argv[1:])
