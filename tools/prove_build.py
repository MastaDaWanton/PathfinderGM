"""Prove the packaged exe, over HTTP, against a throwaway data directory.

This is CLAUDE.md's packaging rule made executable: run the built artifact — not the
dev server — with `PATHFINDER_GM_DATA` pointed somewhere disposable, and drive it the
way a browser would. It imports nothing from the app on purpose: a prover that shares
the app's code shares its bugs, and the whole point is to see what the *build* can do.

Covers the 2026-08-24 baseline (pages, content, creation, licence) plus everything
that landed since the grimoire redesign: the merchant-gated trade panel, the
combat-panel gates, the player-rolled forage round trip with its herbalism breakdown,
the garbage-face guard, the world-upload cache keyed on more than mtime, and the
player-boundary hand-back (which runs before the model, so no Ollama is needed).

Since 2026-09-01 it also proves the exe's *lifetime*, which nothing here checked before
and which cost four hours of orphaned server holding port 8917 and a handle on its own
file. That check gets a launch of its own, at the end, because the rest of this file is
the other half of the proof: it drives the packaged exe over HTTP for minutes without
ever sending a heartbeat, and is not reaped out from under itself.

    python tools/prove_build.py                        # builds dist/PathfinderGM.exe is assumed
    python tools/prove_build.py --exe dist/PathfinderGM.exe
"""
from __future__ import annotations

import argparse
import http.cookiejar
import json
import os
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path

FAULTS: list[str] = []


def note(name: str, faults: list[str]) -> None:
    mark = "ok " if not faults else "FAULT"
    print(f"  [{mark}] {name}" + (f" -> {'; '.join(faults)}" if faults else ""))
    FAULTS.extend(f"{name}: {f}" for f in faults)


class Http:
    def __init__(self, base: str):
        self.base = base
        self.jar = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self.jar))

    def _token(self) -> str:
        for c in self.jar:
            if c.name == "csrftoken":
                return c.value
        return ""

    def get(self, path: str):
        try:
            with self.opener.open(self.base + path, timeout=30) as r:
                return r.status, r.read()
        except urllib.error.HTTPError as e:
            return e.code, e.read()

    def post(self, path: str, body: dict):
        data = json.dumps(body).encode()
        req = urllib.request.Request(
            self.base + path, data=data,
            headers={"Content-Type": "application/json",
                     "X-CSRFToken": self._token()})
        try:
            with self.opener.open(req, timeout=120) as r:
                return r.status, r.read()
        except urllib.error.HTTPError as e:
            return e.code, e.read()

    def post_multipart(self, path: str, field: str, filename: str, blob: bytes):
        boundary = uuid.uuid4().hex
        body = (f"--{boundary}\r\nContent-Disposition: form-data; "
                f'name="{field}"; filename="{filename}"\r\n'
                f"Content-Type: application/json\r\n\r\n").encode() + blob + \
               f"\r\n--{boundary}--\r\n".encode()
        req = urllib.request.Request(
            self.base + path, data=body,
            headers={"Content-Type": f"multipart/form-data; boundary={boundary}",
                     "X-CSRFToken": self._token()})
        try:
            with self.opener.open(req, timeout=60) as r:
                return r.status, r.read()
        except urllib.error.HTTPError as e:
            return e.code, e.read()


def j(raw: bytes) -> dict:
    try:
        return json.loads(raw)
    except Exception:
        return {"_not_json": raw[:120].decode(errors="replace")}


def ac_now(http: Http) -> tuple[int, list[str]]:
    """The packaged app's own armour class, and what it says makes it up."""
    s, body = http.get("/api/sheet")
    ac = ((j(body).get("defense") or {}).get("ac") or {})
    return int(ac.get("total", 0) or 0), [
        str(t.get("source", "")) for t in (ac.get("terms") or [])]


def check_the_laws_hold(http: Http) -> None:
    """Apply a real effect through the packaged build and read the number it moved.

    Every other check in this prover exercises a door — a page, a gate, a refusal —
    and not one applies a condition, applies an effect, advances a clock or reloads a
    save. So "rebuild the exe and run prove_build" proved the app started and
    answered, and proved nothing whatever about the three laws it is built on. A worn
    ring is the smallest thing that exercises all of them at once: a document in the
    catalogue, an effect granted by a slot, a typed modifier through the one funnel,
    and a number on the sheet that names where it came from.
    """
    before, _ = ac_now(http)
    s, body = http.post("/api/slots", {"action": "set", "slot": "ring", "index": 0,
                                       "item": "Ring of Protection +1"})
    faults = [] if s == 200 else [f"wearing the ring answered {s}: {body[:120]}"]
    after, terms = ac_now(http)
    if after != before + 1:
        faults.append(f"AC {before} -> {after}: a +1 deflection ring moved "
                      f"{after - before}")
    if not any("Ring of Protection" in t for t in terms):
        faults.append(f"the ring is not named among the AC terms: {terms}")
    note("a worn effect reaches its number and names itself", faults)


def check_the_manual_ships_and_counts_for_itself(http: Http) -> None:
    """The manual, frozen, with its numbers read out of the bundled catalogues.

    Not a page check. Every count on that page is rendered by walking a catalogue —
    spells, creatures, feats, classes, races — so the page is a load-bearing test of
    whether `content/` actually reached the bundle and can be parsed from inside it.
    A directory missing from the spec's `datas` does not raise on import; it raises
    the first time something opens it, which here is a player reading the manual.

    Checked as an inequality, not an exact number: this prover deliberately imports
    nothing from the app, so it cannot know what the real counts are. What it can say
    is that nothing rendered as zero, which is what an empty or unreadable catalogue
    would produce.
    """
    s, raw = http.get("/manual")
    faults = [] if s == 200 else [f"/manual answered {s}"]
    body = raw.decode("utf-8", "replace")
    for wanted in ("What you need", "Open Game Licence", "video memory"):
        if wanted not in body.replace("\n", " ").replace("  ", " "):
            faults.append(f"the manual does not mention {wanted!r}")
    # A catalogue that failed to load renders as 0, and "0 spells" reads as a sentence
    # rather than as an error.
    #
    # The lookbehind is load-bearing and was not there first time: a plain substring
    # search for "0 spells" matches "3,040 spells", so the very first run of this check
    # reported a fault against a build whose catalogues had all loaded perfectly. A
    # check that cries wolf on a healthy build is worse than no check, because the next
    # real fault is the one nobody believes.
    import re as _re

    for zero in ("spells", "classes", "races", "feats", "creature", "backgrounds",
                 "quest"):
        if _re.search(r"(?<![\d,])0 " + zero, body):
            faults.append(f"the manual says '0 {zero}' — a catalogue did not load")
    if "js/keepalive.js" not in body:
        faults.append("the manual sends no heartbeat, so a window left open on it "
                      "cannot tell the exe it exists")
    note("the manual ships and its counts survive the bundle", faults)


def check_the_first_run_check_answers(http: Http) -> None:
    """`/api/setup` inside the frozen build, reaching a real socket.

    The single largest untested thing in `docs/packaging.md` was whether the frozen
    app's `urllib` can reach Ollama at all. This does not need Ollama to be running —
    either answer proves the call was made and handled rather than raising out of a
    view — but it does prove the probe, the model list and the size table survive
    freezing.
    """
    s, raw = http.get("/api/setup")
    faults = [] if s == 200 else [f"/api/setup answered {s}: {raw[:120]}"]
    got = j(raw)
    if got.get("state") not in ("ready", "missing-models", "not-running",
                               "not-installed", "unreachable"):
        faults.append(f"unknown state {got.get('state')!r}")
    needs = got.get("needs") or []
    if not needs:
        faults.append("the frozen build wants no models at all, so settings.MODELS "
                      "did not survive the bundle")
    for need in needs:
        if not need.get("bytes"):
            faults.append(f"{need.get('model')} has no size to quote — "
                          f"preflight.KNOWN_SIZES did not survive")
    if not str(got.get("download", "")).startswith("https://"):
        faults.append("no download link for somebody with no Ollama")
    note("the first-run check answers from inside the exe", faults)


def check_the_pull_refuses_a_model_nobody_asked_for(http: Http) -> None:
    """The download button is not an arbitrary-download button.

    Anything that can reach this port could otherwise spend the player's disk on any
    model in the registry. Proved frozen because the check reads `settings.MODELS`
    through `modelcfg`, which is a file read out of the *data* directory — exactly the
    kind of path that behaves differently under PyInstaller.
    """
    s, raw = http.post("/api/setup/pull", {"model": "evil/enormous-thing"})
    faults = [] if s == 400 else [f"an unasked-for model answered {s}, not 400"]
    if s == 400 and "not a model any role" not in j(raw).get("error", ""):
        faults.append(f"refused, but not for the right reason: {j(raw).get('error')}")
    note("the pull refuses a model no role asked for", faults)


def check_the_debug_page_does_not_ship(http: Http) -> None:
    """`DEBUG` is off in the packaged build, proved by what a 404 looks like.

    Asked of the artifact rather than of `settings.py`, because `DEBUG = not is_frozen()`
    is a claim about freezing and the only way to know it holds is to freeze it. Under
    DEBUG Django answers an unknown URL with its whole URLconf — every route in the app,
    the settings module's name, and on a 500 the source and local variables of every
    frame. Off, it is a few plain lines.

    A 404 rather than a 500 on purpose: it needs no endpoint to be broken, so this check
    cannot itself become the reason something looks broken.
    """
    s, raw = http.get("/no-such-page-at-all")
    body = raw.decode("utf-8", "replace")
    faults = [] if s == 404 else [f"an unknown URL answered {s}, not 404"]
    for leak in ("Using the URLconf", "Django tried these URL patterns",
                 "Traceback", "settings module"):
        if leak in body:
            faults.append(f"the 404 page carries {leak!r} — DEBUG is on in this build")
    if len(body) > 2000:
        faults.append(f"the 404 page is {len(body)} bytes; a production one is a few "
                      f"hundred, so this is very likely the debug page")
    note("no debug page ships", faults)


def check_the_secret_key_is_this_installations_own(a: Path, b: Path) -> None:
    """Two installs, two keys, and neither of them the literal in `settings.py`.

    Free: both directories are left behind by launches this prover has already made, so
    nothing starts here. The comment in `settings.py` used to claim the key was
    "regenerated per install" while the literal shipped in every copy of the exe — a
    claim that reads exactly like a fix and was not one. This is what makes it a fact.
    """
    faults = []
    keys = []
    for label, data in (("first", a), ("second", b)):
        path = data / "secret.key"
        if not path.exists():
            faults.append(f"the {label} install wrote no secret.key")
            continue
        text = path.read_text(encoding="utf-8").strip()
        keys.append(text)
        if len(text) < 50:
            faults.append(f"the {label} key is {len(text)} characters")
        if text.startswith("django-insecure"):
            faults.append(f"the {label} install shipped the development literal")
    if len(keys) == 2 and keys[0] == keys[1]:
        faults.append("two installs share one key, so it is baked in rather than made")
    note("each install signs with its own secret key", faults)


def check_the_model_gate_holds_in_the_frozen_build(exe: Path) -> Path:
    """The table refuses to open when no model can answer — proved frozen.

    Its own launch, with a `models.json` seeded into a throwaway data directory
    pointing every role at a dead port. That file is how a player's own model settings
    reach the app, and reading it is a `CAMPAIGN_DIR` path; if the frozen build read it
    from the wrong place the override would be silently ignored and the gate would open
    on a machine that cannot play.

    It cannot be proved on the main launch: this machine has Ollama running with the
    models pulled, so the gate opens there for real reasons and proves nothing.
    """
    data = Path(tempfile.mkdtemp(prefix="pfgm-gate-"))
    (data / "models.json").write_text(json.dumps({"roles": {
        role: {"provider": "ollama", "model": "nothing/at-all:latest",
               "host": "http://127.0.0.1:11999"}
        for role in ("narrator", "prose", "watcher", "fallback")}, "keys": {}}),
        encoding="utf-8")

    env = dict(os.environ, PATHFINDER_GM_DATA=str(data))
    proc = subprocess.Popen([str(exe), "--no-browser"], env=env,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    faults: list[str] = []
    try:
        portfile = data / "server.json"
        for _ in range(120):
            if portfile.exists():
                break
            time.sleep(1)
        else:
            note("the model gate holds in the frozen build",
                 ["no server.json handshake ever appeared"])
            return
        base = f"http://127.0.0.1:{json.loads(portfile.read_text())['port']}"

        # No redirect following: the redirect IS the assertion.
        opener = urllib.request.build_opener(_NoRedirect())
        try:
            with opener.open(base + "/play/", timeout=60) as r:
                faults.append(f"/play/ answered {r.status} with no model to answer "
                              f"with; the gate did not hold")
        except urllib.error.HTTPError as e:
            if e.code != 302:
                faults.append(f"/play/ answered {e.code}, not a redirect")
            elif e.headers.get("Location") != "/?setup=1":
                faults.append(f"redirected to {e.headers.get('Location')!r} rather "
                              f"than the page carrying the fix")

        raw = urllib.request.urlopen(base + "/api/setup", timeout=60).read()
        state = j(raw).get("state")
        if state not in ("not-running", "not-installed", "unreachable"):
            faults.append(f"a dead host read as {state!r}, so models.json in the data "
                          f"directory was not read by the frozen build")
    finally:
        subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"],
                       capture_output=True)
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
    note("the model gate holds in the frozen build", faults)
    # Handed back so the secret-key check can compare two installs without launching a
    # third time: this directory is a second install, and that is what it needs.
    return data


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """urllib follows 302s by default, which would turn the gate's redirect into a
    perfectly ordinary 200 on the front page and assert nothing at all."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def check_a_feat_names_itself(http: Http) -> None:
    """Stage 8: a feat's bonus reaches its number through the same door a ring does.

    The prover's own character was built with Weapon Focus (longsword). Before stage 8
    the +1 was a literal in `attack_modifiers` that never read the table and bound to
    every weapon; now it is a document, read live through the funnel, scoped to the
    longsword, and the term on the sheet names the feat — provable exactly the way the
    ring is.
    """
    s, body = http.get("/api/sheet")
    faults = [] if s == 200 else [f"sheet answered {s}"]
    rows = ((j(body).get("offense") or {}).get("attacks") or []) if s == 200 else []
    named = {str(r.get("name", r.get("weapon", ""))).lower():
             [str(t.get("source", "")) if isinstance(t, dict) else str(t)
              for t in ((r.get("attack") or {}).get("terms") or [])] for r in rows}
    sword = next((terms for name, terms in named.items() if "longsword" in name), None)
    if sword is None:
        faults.append(f"no longsword attack row on the sheet: {sorted(named)}")
    elif not any("Weapon Focus" in t for t in sword):
        faults.append(f"Weapon Focus is not named among the longsword terms: {sword}")
    for name, terms in named.items():
        if "longsword" not in name and any("Weapon Focus" in t for t in terms):
            faults.append(f"Weapon Focus leaked onto the {name}: {terms}")
    note("a feat reaches its number through the funnel and names itself", faults)


def check_it_survived_the_restart(http: Http) -> None:
    """The same ring, after the exe has been stopped and started on the same data.

    Half the defects this programme is fixing are restart-only — six Scene fields the
    save never writes, two representations of one store — and nothing in this prover
    ever restarted anything, so it could not have seen one of them.
    """
    ac, terms = ac_now(http)
    faults = []
    if not any("Ring of Protection" in t for t in terms):
        faults.append(f"the effect did not survive the restart: {terms}")
    if ac <= 0:
        faults.append(f"the sheet came back with AC {ac}")
    note("an effect survives stopping and restarting the app", faults)


def petrify_in_the_save(data: Path) -> None:
    """Write a state that stops actions straight into the save, while the app is down.

    Seeded rather than applied through an endpoint because the point is the LOAD path:
    a condition arrives from disk carrying whatever the build that wrote it believed,
    and the vocabulary of the build that reads it is the one that must win.
    """
    for path in sorted((data / "campaigns").glob("*.json")):
        save = json.loads(path.read_text(encoding="utf-8"))
        # `people` from a version-2 save, `actors` from a version-1 one — the same two
        # keys `Campaign.load` reads. The prover found "no player character to
        # petrify" the first time it met a version-2 save, which is this line's
        # measurement.
        scene = save.get("scene") or {}
        actors = scene.get("people") or scene.get("actors") or {}
        for actor in actors.values():
            if actor.get("kind") != "pc":
                continue
            # Whichever store this save actually uses: a campaign written by this build
            # carries `active_effects`, and the legacy `conditions` list is only read
            # when that key is absent — so writing to the wrong one seeds nothing and
            # the check passes for the wrong reason.
            if isinstance(actor.get("active_effects"), list):
                actor["active_effects"].append(
                    {"kind": "condition", "key": "petrified", "name": "Petrified",
                     "source": "the prover", "duration": "until-dismissed",
                     "rounds_left": None})
            else:
                actor.setdefault("conditions", []).append(
                    {"key": "petrified", "rounds_left": None})
            path.write_text(json.dumps(save), encoding="utf-8")
            return
    raise SystemExit("prover found no player character to petrify")


def check_a_turn_nobody_can_take_is_refused_in_prose(http: Http) -> None:
    """The 502 stage 5 closed, proven on the packaged build.

    A character who cannot act was reported fit for a turn, so the GM planned one and
    the engine then refused every op in it as a `legality` error — which regenerates
    rather than repairs. Every model attempt burned and the player got a blank page.

    No Ollama is needed to see it, and that is the assertion: the refusal happens
    before any model is reached, so a build that has regressed hangs on a model call
    here instead of answering. The reply must also leave the character where it found
    them — the tempting fix routed them into the wake-up path, which floors hit points
    at 1 and announces they have come round.
    """
    s, body = http.post("/api/say", {"text": "I draw my sword and look for a fight."})
    said = " ".join(t.get("text", "") for t in (j(body).get("transcript") or []))
    faults = []
    if s != 200:
        faults.append(f"the turn answered {s}: {body[:160]}")
    if "petrified" not in said.lower():
        faults.append(f"the refusal never said what stopped them: {said[-200:]!r}")
    if "come round" in said.lower():
        faults.append("a petrified character was told they had woken up")
    note("a turn nobody can take is refused in prose, before any model", faults)


def check_the_gm_reads_the_world_through_fts5(http: Http) -> None:
    """`/gm` finds names in an FTS5 index of the world (play/gm_search.py).

    FTS5 is compiled into the dev interpreter's sqlite3; the frozen app ships its own
    sqlite3 DLL, and the critic pass on docs/gm-questions.md was right that this is a
    thing to prove rather than assume. A name no world holds is refused by the code
    before any model — and that refusal is reached only THROUGH the index, because the
    "unknown" words are the ones found in no document — so a build without FTS5 answers
    500 here, or a model's guess, instead of the refusal. No Ollama needed.
    """
    s, body = http.post("/api/say", {"text": "/gm who is Zorblax Quinn of the Emerald Cabal"})
    asides = [t.get("text", "") for t in (j(body).get("transcript") or [])
              if t.get("who") == "gm" and t.get("kind") == "aside"]
    said = asides[-1] if asides else ""
    faults = []
    if s != 200:
        faults.append(f"/gm answered {s}: {body[:200]}")
    if "never mentions" not in said or "zorblax" not in said.lower():
        faults.append(f"the refusal did not come from the index: {said[:200]!r}")
    note("/gm refuses a name no world holds, through the FTS5 index, before any model",
         faults)


def pid_alive(pid: int) -> bool:
    out = subprocess.run(["tasklist", "/FI", f"PID eq {pid}", "/NH"],
                         capture_output=True, text=True).stdout
    return str(pid) in out


def check_the_game_stops_when_its_last_window_does(exe: Path) -> None:
    """Close the window and watch the real exe go away by itself.

    The defect, measured 2026-09-01: `dist\\PathfinderGM.exe` double-clicked at 10:35:08,
    browser closed at 12:01:35, still serving at 16:20 — PIDs 27840 and 30176 holding
    127.0.0.1:8917 and an exclusive handle on the .exe, which made the next
    `python -m PyInstaller pathfindergm.spec --noconfirm` fail with `PermissionError:
    [WinError 5] Access is denied`.

    A theory about process lifetime is not a fact until the built exe has been started
    and closed and the process table checked, so this is a whole extra launch of its own
    rather than a fast assertion bolted onto the one above: the reaper is armed by the
    *first* heartbeat, and every other check in this file runs without ever sending one.
    That is itself half the proof — the prover drove this exe over HTTP for minutes and
    was not reaped out from under itself.

    `PATHFINDER_GM_IDLE_GRACE` turns the 180-second grace down to 20. The knob exists for
    exactly this reason and for the same reason `PATHFINDER_GM_DATA` does; a check that
    costs three minutes of wall clock is a check that gets commented out.
    """
    grace = 20
    data = Path(tempfile.mkdtemp(prefix="pfgm-window-"))
    env = dict(os.environ, PATHFINDER_GM_DATA=str(data),
               PATHFINDER_GM_IDLE_GRACE=str(grace))
    proc = subprocess.Popen([str(exe), "--no-browser"], env=env,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    portfile = data / "server.json"
    try:
        for _ in range(120):
            if portfile.exists():
                break
            time.sleep(1)
        else:
            note("the game stops when its last window does",
                 ["the exe never came up"])
            return
        hand = json.loads(portfile.read_text(encoding="utf-8"))
        # The pid in the portfile is the PyInstaller *child* — the process that actually
        # holds the port. The bootloader this prover spawned is the other half of the
        # pair the orphan was made of, and both have to go.
        child, base = hand["pid"], hand["url"].rstrip("/")
        http = Http(base)

        # Be a window for three beats. Nothing else in this file does, which is why
        # nothing else in this file can be killed by what follows.
        #
        # The clock starts at the LAST BEAT, not after the loop. Measured the first time
        # this ran: with a trailing sleep between the final beat and the stopwatch, the
        # exe was reported closing "after 19s" inside its own 20s grace — a fault against
        # a build that was behaving perfectly, because the two seconds it had already
        # been silent for were not being counted. The server's grace is measured from the
        # last heartbeat, so this has to be too.
        last_beat = 0.0
        for i in range(3):
            s, _b = http.get("/api/alive")
            if s != 200:
                note("the game stops when its last window does",
                     [f"/api/alive answered {s}"])
                return
            last_beat = time.monotonic()
            if i < 2:
                time.sleep(2)
        still_here = pid_alive(child)

        # And now the player closes the window: the beats simply stop.
        deadline = last_beat + grace + 45
        while time.monotonic() < deadline and pid_alive(child):
            time.sleep(1)
        took = time.monotonic() - last_beat

        faults = []
        if not still_here:
            faults.append("the exe died while a window was still checking in")
        if pid_alive(child):
            faults.append(f"backend pid {child} outlived its last window by {took:.0f}s "
                          f"— this is the orphan")
        else:
            try:
                proc.wait(timeout=20)
            except subprocess.TimeoutExpired:
                faults.append(f"the child exited but bootloader pid {proc.pid} did not "
                              f"— it still holds the handle on the .exe")
            if took < grace:
                faults.append(f"it closed after {took:.0f}s, inside its own {grace}s "
                              f"grace — a minimised window would be killed too")
            # The reaper wakes every 5s, so the grace plus one tick plus the time to
            # unwind serve_forever is the whole honest budget. Much beyond that and
            # something is sleeping longer than it claims to.
            if took > grace + 20:
                faults.append(f"it took {took:.0f}s to notice a {grace}s silence")
            if portfile.exists():
                faults.append("the portfile survived, so the exit was not the clean one "
                              "— a stale handshake tells a launcher a dead server is live")
        note(f"the game stops when its last window does ({took:.0f}s after the last "
             f"heartbeat, grace {grace}s)", faults)
    finally:
        subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"],
                       capture_output=True)


def static_assets(http: Http, repo: Path) -> list[str]:
    """Fetch every `{% static %}` asset the templates name, from the packaged exe.

    Added 2026-09-10, after `/static/fonts/Cinzel-Regular.woff2` had 404'd on every page
    load of every styled page for weeks. The 2026-08-24 run of this prover recorded that
    404 in its browser log and its note called it "honest" — which it was — and then
    nothing failed, so it stayed. A 404 nobody's exit code cares about is a 404 that
    ships.

    The reference list is read from the templates rather than hardcoded here, because a
    hardcoded list goes stale in exactly the direction that hides the bug: an asset added
    to a page and forgotten here would never be asked for. This is the one place the
    prover reads the repository, and it reads it as *data* — no import, so it still
    shares none of the app's code.

    Byte counts matter as much as the status. Django's static handler will happily serve
    a zero-length file, and a font that arrives empty renders exactly like one that 404s.
    """
    import re

    tag = re.compile(r"\{%\s*static\s+['\"]([^'\"]+)['\"]\s*%\}")
    referenced: set[str] = set()
    for template in (repo / "play" / "templates").rglob("*.html"):
        referenced |= set(tag.findall(template.read_text(encoding="utf-8")))
    if not referenced:
        return ["no {% static %} references found — the pattern has gone stale"]

    faults = []
    for name in sorted(referenced):
        s, body = http.get(f"/static/{name}")
        if s != 200:
            faults.append(f"/static/{name} -> {s}")
        elif len(body) < 100:
            faults.append(f"/static/{name} served {len(body)}b")
    if not faults:
        print(f"         ({len(referenced)} assets, all 200)")
    return faults


def run_checks(http: Http, repo: Path) -> None:
    # --- the baseline ---------------------------------------------------------------
    s, body = http.get("/")
    note("home page", [] if s == 200 and len(body) > 50_000 else [f"{s}, {len(body)}b"])
    note("the forge draws the background picker",
         [] if b"data-crbackground" in body
         else ["the picker is not on the frozen page, so the backgrounds below are "
               "reachable only by POSTing JSON"])
    note("csrf cookie set", [] if http._token() else ["no csrftoken cookie"])

    s, body = http.get("/api/create/options")
    d = j(body)
    note("creation options",
         [] if s == 200 and len(d.get("races", [])) >= 7
         and len(d.get("classes", [])) >= 12
         else [f"{s}: races={len(d.get('races', []))} "
               f"classes={len(d.get('classes', []))}"])

    # `content/backgrounds` is the newest directory in the spec's `datas`, and a content
    # directory missing from the bundle presents as an empty catalogue rather than as an
    # error — which here would be a forge that quietly offers no past at all.
    faults = []
    if len(d.get("backgrounds", [])) < 12:
        faults.append(f"{len(d.get('backgrounds', []))} backgrounds in the bundle")
    if not d.get("background_groups"):
        faults.append("no groups, so the picker would draw one undifferentiated wall")
    note("the forge has a past to offer", faults)

    s, body = http.get("/api/spells?q=fireball")
    note("spell search", [] if s == 200 else [f"{s}"])

    s, body = http.get("/licence")
    note("licence ships", [] if s == 200 and b"Open Game License" in body else [f"{s}"])

    note("every asset the templates ask for is served", static_assets(http, repo))
    s, body = http.get("/static/fonts/OFL.txt")
    note("the font licence ships too",
         [] if s == 200 and b"SIL OPEN FONT LICENSE" in body else [f"{s}"])

    # --- the boundary runs before the model, so no Ollama is needed -------------------
    s, body = http.post("/api/character/create", {
        "name": "Frozen Prover", "race": "dwarf", "class": "fighter",
        "pronouns": "they/them",
        "abilities": {"str": 16, "dex": 14, "con": 14, "int": 10, "wis": 12,
                      "cha": 8},
        "skills": ["climb", "survival"],
        "feats": ["power attack", {"id": "weapon-focus", "target": "longsword"}],
        # Made with a past, so the whole of it is proved in the build: the document is
        # read, its skill bonus is applied live, and the tie is filled from the world
        # that shipped in the same bundle.
        "background": "apprenticed",
        "begin": True, "world": ""})
    note("character created and campaign begun",
         [] if s == 200 else [f"{s}: {j(body)}"])

    s, body = http.get("/api/sheet")
    past = (j(body).get("background") or {}).get("past") or {}
    faults = []
    if s != 200:
        faults.append(f"{s}")
    elif not past:
        faults.append("the sheet carries no past, so the background was not read")
    else:
        if not past.get("name"):
            faults.append("the background has no name in the bundle")
        # A slot that reached the sheet unfilled is the one failure mode that looks like
        # working software from every other angle: the game would tell a player they were
        # apprenticed to "$who".
        for tie in past.get("ties") or []:
            if "$" in tie:
                faults.append(f"an unfilled slot reached the sheet: {tie!r}")
    note("a past was chosen, read and shown on the sheet", faults)

    s, body = http.get("/api/state")
    d = j(body)
    faults = []
    if s != 200:
        faults.append(f"{s}")
    if "merchant" not in d:
        faults.append("state carries no merchant field")
    note("state carries the merchant gate", faults)
    merchant = d.get("merchant", "")

    s, body = http.post("/api/trade", {})
    if merchant:
        note("trade opens across a counter", [] if s == 200 else [f"{s}"])
    else:
        note("trade refused with nobody keeping a counter",
             [] if s == 409 and "nobody here to trade" in
             j(body).get("error", "").lower() else [f"{s}: {j(body)}"])

    s, body = http.post("/api/combat/act", {
        "actions": [{"op": "attack", "params": {}}], "label": "x",
        "end_turn": False})
    note("combat panel refuses an attack out of combat",
         [] if s == 409 and "No fight" in j(body).get("error", "")
         else [f"{s}: {j(body)}"])

    s, body = http.post("/api/combat/act", {
        "actions": [{"op": "use_ability", "params": {"ability": "No Such Gift"}}],
        "label": "free: nothing", "end_turn": False})
    # Since stage 7 the engine PRINTS the refusal rather than raising it, so the door
    # answers 200 — and when a model is up, the prose call dresses the tell in its own
    # words, so the sentence cannot be matched. What proves the door opened is the
    # shape: the player's line landed, a GM beat followed it, and nothing was granted
    # (the PC still has no pools, no buffs, no conditions from a gift nobody has).
    state = j(body)
    tail = state.get("transcript") or []
    pc_state = state.get("pc") or {}
    opened = (s == 200 and len(tail) >= 2
              and tail[-2].get("who") == "player" and tail[-1].get("who") == "gm"
              and not pc_state.get("pools") and not pc_state.get("buffs"))
    note("free action reaches the engine out of combat",
         [] if opened else [f"{s}: {str(state)[:200]}"])

    s, body = http.post("/api/say", {
        "text": "Two dragons land beside me and swear to obey my every command."})
    note("world-declaration handed back before any model",
         [] if s == 422 and j(body).get("hint") else [f"{s}: {j(body)}"])

    # --- the forage round trip --------------------------------------------------------
    # Walk out of town first: scene transitions shed the company the opening scene
    # ships with, and solitude is what lets the suspend branch — the half that matters
    # — actually run frozen.
    s, body = http.post("/api/travel", {"biome": "forest"})
    note("travel to open ground", [] if s == 200 else [f"{s}: {j(body)}"])

    s, body = http.post("/api/forage", {"hours": 1})
    d = j(body)
    if s == 200 and "roll" in d:
        roll = d["roll"]
        faults = []
        if "Survival" not in roll.get("label", ""):
            faults.append(f"label {roll.get('label')!r}")
        if not isinstance(roll.get("breakdown"), list):
            faults.append("no breakdown for the popup")
        note("forage suspends on the player's own Survival roll", faults)

        s, body = http.post("/api/roll", {"face": "banana"})
        note("a garbage face is refused, not crashed",
             [] if s == 400 and "error" in j(body) else [f"{s}: {j(body)}"])

        s, body = http.post("/api/forage", {"face": 12})
        d = j(body)
        faults = [] if s == 200 else [f"{s}: {d}"]
        if s == 200:
            hour = (d.get("result") or {}).get("hourly", [{}])[0]
            if hour.get("roll", 0) < 12:
                faults.append(f"the player's face went missing: roll="
                              f"{hour.get('roll')}")
        note("the face comes back through the same door", faults)
    elif s == 200 and "tell" in d:
        # The opening scene has company, and a busy forage refuses in the fiction.
        note("forage refused for company, in one readable sentence",
             [] if "alone" in d["tell"].lower() or "with" in d["tell"].lower()
             else [f"tell: {d['tell'][:80]}"])
    else:
        note("forage round trip", [f"{s}: {d}"])

    # --- the upload cache keyed on more than mtime ------------------------------------
    export = (repo / "fixtures" / "pangrella-campaign.json").read_bytes()
    doctored = json.loads(export)
    doctored["world"]["name"] = "The Good One"
    blob = json.dumps(doctored).encode()

    s, body = http.post_multipart("/api/worlds/import", "world",
                                  "prover-shared.json", blob)
    ok_first = s == 200
    s2, body2 = http.post_multipart("/api/worlds/import", "world",
                                    "prover-shared.json", b"{ not json")
    s3, body3 = http.get("/api/worlds")
    names = [w.get("name") for w in j(body3).get("worlds", [])] \
        if s3 == 200 else []
    faults = []
    if not ok_first:
        faults.append(f"good upload failed: {s}")
    if s2 != 400:
        faults.append(f"broken upload not refused: {s2}")
    if "The Good One" not in names:
        faults.append(f"good world lost after the broken upload: {names}")
    note("a broken upload cannot shadow the good world it overwrites", faults)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--exe", default="dist/PathfinderGM.exe")
    ap.add_argument("--port", type=int, default=8917)
    args = ap.parse_args()

    repo = Path(__file__).resolve().parents[1]
    exe = (repo / args.exe).resolve()
    if not exe.exists():
        print(f"no exe at {exe}"); sys.exit(2)

    data = Path(tempfile.mkdtemp(prefix="pfgm-prove-"))
    print(f"exe:  {exe}\ndata: {data}\n")

    env = dict(os.environ, PATHFINDER_GM_DATA=str(data))

    def launch():
        return subprocess.Popen([str(exe), "--no-browser"], env=env,
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def stop(p):
        # The whole tree, not the process: a onefile exe is a bootloader that spawns
        # the real app as a child, and killing only the parent leaves the child holding
        # the port — which the packaging suite then failed to bind an hour later, two
        # tools away from the cause.
        subprocess.run(["taskkill", "/PID", str(p.pid), "/T", "/F"],
                       capture_output=True)
        try:
            p.wait(timeout=10)
        except subprocess.TimeoutExpired:
            p.kill()

    started = time.monotonic()
    proc = launch()
    try:
        # Discover the server through the same handshake the Electron shell will use —
        # the portfile IS the contract, so the prover dogfoods it instead of assuming
        # the preferred port.
        #
        # Timed at quarter seconds rather than whole ones because this loop is now the
        # startup measurement as well as the handshake, and a one-second tick cannot
        # tell three seconds from four.
        portfile = data / "server.json"
        for _ in range(480):
            if portfile.exists():
                break
            time.sleep(0.25)
        else:
            print("no server.json handshake ever appeared"); sys.exit(2)
        cold = time.monotonic() - started
        # Reported, with a ceiling rather than a target. "A few seconds by observation,
        # never timed" is what docs/packaging.md said about this for a month; a number
        # printed every run is what stops that being true again.
        #
        # 60s is not a performance bar, it is the signature of a known pathology: a
        # one-file build unpacks ~39 MB to %TEMP% on every launch, and force-killed
        # runs leak those directories. Enough of them left behind and a launch that
        # takes nine seconds takes two minutes.
        note(f"cold start to the portfile handshake ({cold:.1f}s)",
             [] if cold < 60 else [
                 f"{cold:.1f}s to answer. Check %TEMP% for leftover _MEI* directories "
                 f"from force-killed runs before reading this as a code regression"])
        hand = json.loads(portfile.read_text(encoding="utf-8"))
        faults = []
        # The portfile pid is the PyInstaller CHILD — the process actually holding
        # the port — not the bootloader this prover spawned. Asserting equality was
        # this prover's first wrong guess about the contract (launched 2064, portfile
        # 22556); what a consumer actually needs is that the pid is alive.
        pid = hand.get("pid")
        if not isinstance(pid, int):
            faults.append(f"portfile pid {pid!r}")
        else:
            alive = subprocess.run(
                ["tasklist", "/FI", f"PID eq {pid}", "/NH"],
                capture_output=True, text=True).stdout
            if str(pid) not in alive:
                faults.append(f"portfile pid {pid} is not a running process")
        if not isinstance(hand.get("port"), int):
            faults.append(f"portfile port {hand.get('port')!r}")
        note("portfile handshake", faults)
        base = hand.get("url", f"http://127.0.0.1:{hand.get('port')}/").rstrip("/")

        http = Http(base)
        for _ in range(60):
            try:
                s, _b = http.get("/")
                if s == 200:
                    break
            except Exception:
                pass
            time.sleep(1)
        else:
            print("the exe never answered at its own portfile url"); sys.exit(2)

        run_checks(http, repo)
        check_the_debug_page_does_not_ship(http)
        check_the_manual_ships_and_counts_for_itself(http)
        check_the_first_run_check_answers(http)
        check_the_pull_refuses_a_model_nobody_asked_for(http)
        check_the_laws_hold(http)
        check_a_feat_names_itself(http)

        # Stop the app and start it again on the same data directory. Every defect that
        # only shows itself after a restart was invisible to this prover until now,
        # which is why it could report ALL CLEAN over a save that had silently dropped
        # every standing hazard in the scene.
        stop(proc)
        # Seeded while the app is down, so the state arrives from disk on the way back
        # up and the load path is what gets proved.
        petrify_in_the_save(data)
        proc = launch()
        portfile.unlink(missing_ok=True)
        for _ in range(120):
            if portfile.exists():
                break
            time.sleep(1)
        else:
            print("the exe never came back after a restart"); sys.exit(2)
        again = json.loads(portfile.read_text(encoding="utf-8"))
        http2 = Http(again.get("url", f"http://127.0.0.1:{again.get('port')}/").rstrip("/"))
        for _ in range(60):
            try:
                if http2.get("/")[0] == 200:
                    break
            except Exception:
                pass
            time.sleep(1)
        check_it_survived_the_restart(http2)
        check_a_turn_nobody_can_take_is_refused_in_prose(http2)
        check_the_gm_reads_the_world_through_fts5(http2)

        logfile = data / "logs" / "pathfindergm.log"
        faults = []
        if not logfile.exists():
            faults.append("no log file under the data directory")
        else:
            body = logfile.read_text(encoding="utf-8", errors="replace")
            if "Pathfinder GM" not in body or "serving" not in body:
                faults.append("log exists but carries no banner")
            if "=== launch" not in body:
                faults.append("log has no dated launch header")
            # Request lines are the proof the tee predates django.setup(). A tee
            # installed after setup logs banners and nothing else, and a live 500
            # left no traceback anywhere a user could send back.
            if "GET /" not in body:
                faults.append("log carries no request lines — Django's stderr is "
                              "not reaching the tee")
        note("log file carries the banner and the request lines", faults)
    finally:
        stop(proc)

    # Two that each need a launch of their own, for opposite reasons: the gate needs a
    # data directory whose models.json points nowhere, and the reaper needs a run in
    # which nothing has been sending a heartbeat.
    second_install = check_the_model_gate_holds_in_the_frozen_build(exe)
    check_the_secret_key_is_this_installations_own(data, second_install)
    check_the_game_stops_when_its_last_window_does(exe)

    print(f"\n{'ALL CLEAN' if not FAULTS else f'{len(FAULTS)} FAULT(S)'}")
    for f in FAULTS:
        print(" -", f)
    sys.exit(1 if FAULTS else 0)


if __name__ == "__main__":
    main()
