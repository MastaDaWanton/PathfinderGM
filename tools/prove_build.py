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


def run_checks(http: Http, repo: Path) -> None:
    # --- the baseline ---------------------------------------------------------------
    s, body = http.get("/")
    note("home page", [] if s == 200 and len(body) > 50_000 else [f"{s}, {len(body)}b"])
    note("csrf cookie set", [] if http._token() else ["no csrftoken cookie"])

    s, body = http.get("/api/create/options")
    d = j(body)
    note("creation options",
         [] if s == 200 and len(d.get("races", [])) >= 7
         and len(d.get("classes", [])) >= 12
         else [f"{s}: races={len(d.get('races', []))} "
               f"classes={len(d.get('classes', []))}"])

    s, body = http.get("/api/spells?q=fireball")
    note("spell search", [] if s == 200 else [f"{s}"])

    s, body = http.get("/licence")
    note("licence ships", [] if s == 200 and b"Open Game License" in body else [f"{s}"])

    # --- the boundary runs before the model, so no Ollama is needed -------------------
    s, body = http.post("/api/character/create", {
        "name": "Frozen Prover", "race": "dwarf", "class": "fighter",
        "pronouns": "they/them",
        "abilities": {"str": 16, "dex": 14, "con": 14, "int": 10, "wis": 12,
                      "cha": 8},
        "skills": ["climb", "survival"],
        "feats": ["power attack", "weapon focus"],
        "begin": True, "world": ""})
    note("character created and campaign begun",
         [] if s == 200 else [f"{s}: {j(body)}"])

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
    note("free action reaches the engine out of combat",
         [] if s == 400 and "has no ability" in j(body).get("error", "")
         else [f"{s}: {j(body)}"])

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
    proc = subprocess.Popen([str(exe), "--no-browser"], env=env,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    base = f"http://127.0.0.1:{args.port}"
    try:
        http = Http(base)
        for _ in range(120):
            try:
                s, _b = http.get("/")
                if s == 200:
                    break
            except Exception:
                pass
            time.sleep(1)
        else:
            print("the exe never answered"); sys.exit(2)

        run_checks(http, repo)
    finally:
        # The whole tree, not the process. A PyInstaller onefile exe is a bootloader
        # that spawns the real app as a child; terminate() killed the parent and left
        # the child holding port 8917 — which the packaging suite then failed to bind
        # an hour later, two tools away from the cause.
        subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"],
                       capture_output=True)
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()

    print(f"\n{'ALL CLEAN' if not FAULTS else f'{len(FAULTS)} FAULT(S)'}")
    for f in FAULTS:
        print(" -", f)
    sys.exit(1 if FAULTS else 0)


if __name__ == "__main__":
    main()
