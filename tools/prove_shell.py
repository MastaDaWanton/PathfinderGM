"""Prove the Electron shell's lifecycle without needing to see its window.

What a window shows is checkable by a person; what this checks is the half a person
cannot see going wrong until later: that the shell brings the backend up (portfile
appears, HTTP answers), and — the half that has already bitten this repo once — that
no backend outlives the shell. The prove_build harness's terminate() left a
PyInstaller child holding port 8917 for an hour; this exists so the shell can never
ship with that behaviour.

    python tools/prove_shell.py            # dev shell: electron . over python desktop.py
    python tools/prove_shell.py --packaged # the built app in electron/release
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
FAULTS: list[str] = []


def note(name: str, faults: list[str]) -> None:
    mark = "ok " if not faults else "FAULT"
    print(f"  [{mark}] {name}" + (f" -> {'; '.join(faults)}" if faults else ""))
    FAULTS.extend(f"{name}: {f}" for f in faults)


def pid_alive(pid: int) -> bool:
    out = subprocess.run(["tasklist", "/FI", f"PID eq {pid}", "/NH"],
                         capture_output=True, text=True).stdout
    return str(pid) in out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--packaged", action="store_true",
                    help="run the electron-builder output instead of the dev shell")
    args = ap.parse_args()

    data = Path(tempfile.mkdtemp(prefix="pfgm-shell-"))
    env = dict(os.environ, PATHFINDER_GM_DATA=str(data))

    if args.packaged:
        exe = REPO / "electron" / "release" / "win-unpacked" / "Pathfinder GM.exe"
        if not exe.exists():
            print(f"no packaged shell at {exe}"); sys.exit(2)
        cmd, cwd = [str(exe)], exe.parent
    else:
        cmd, cwd = ["npx", "electron", "."], REPO / "electron"

    print(f"shell: {' '.join(cmd)}\ndata:  {data}\n")
    shell = subprocess.Popen(cmd, cwd=cwd, env=env, shell=not args.packaged,
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    portfile = data / "server.json"
    try:
        for _ in range(90):
            if portfile.exists():
                break
            if shell.poll() is not None:
                print(f"the shell exited early ({shell.returncode})"); sys.exit(2)
            time.sleep(1)
        else:
            note("backend came up behind the shell", ["no portfile in 90s"])
            sys.exit(1)
        hand = json.loads(portfile.read_text(encoding="utf-8"))
        pid, url = hand.get("pid"), hand.get("url")
        note("backend came up behind the shell",
             [] if isinstance(pid, int) and pid_alive(pid) else
             [f"portfile pid {pid!r} not alive"])

        try:
            with urllib.request.urlopen(url, timeout=30) as r:
                ok = r.status == 200
        except Exception as exc:
            ok = False
        note("the shell's URL answers", [] if ok else [f"{url} did not answer"])
    finally:
        # Close the way a PERSON does first — CloseMainWindow, the path taskkill can
        # never test. A real user close once left four shell processes and a live
        # backend holding the single-instance lock, and every taskkill-based run of
        # this prover had passed. The axe below stays as cleanup for whatever the
        # polite close missed, which the sweeps then report as the fault it is.
        if args.packaged:
            subprocess.run(
                ["powershell", "-NoProfile", "-Command",
                 "(Get-Process 'Pathfinder GM' -ErrorAction SilentlyContinue | "
                 "Where-Object {$_.MainWindowHandle -ne 0}) | "
                 "ForEach-Object { $_.CloseMainWindow() | Out-Null }"],
                capture_output=True)
            time.sleep(8)
        subprocess.run(["taskkill", "/PID", str(shell.pid), "/T", "/F"],
                       capture_output=True)

    deadline = time.monotonic() + 15
    backend_dead = False
    while time.monotonic() < deadline:
        if isinstance(pid, int) and not pid_alive(pid):
            backend_dead = True
            break
        time.sleep(1)
    note("no backend outlives the shell",
         [] if backend_dead else [f"backend pid {pid} still running — the orphan"])

    # And none AT ALL, not merely not-ours: the single-instance quit path once
    # spawned a backend and abandoned it while app.quit() tore the shell down, which
    # per-pid bookkeeping cannot see. A sweep is the only honest check.
    time.sleep(2)
    stray = subprocess.run(
        ["tasklist", "/FI", "IMAGENAME eq PathfinderGM.exe", "/NH"],
        capture_output=True, text=True).stdout
    note("no stray PathfinderGM.exe anywhere",
         [] if "PathfinderGM.exe" not in stray
         else [f"survivors: {' '.join(stray.split())[:120]}"])
    # The shell's own family too. Four orphaned "Pathfinder GM" processes (gpu,
    # renderer, utility — Electron is many) once sat holding the single-instance lock
    # and the build directory: every later launch quit as a "second instance" and
    # electron-builder could not overwrite its own output. Killing a main process
    # that has already exited leaves its children unparented, and only a sweep sees
    # them.
    if args.packaged:
        stray = subprocess.run(
            ["tasklist", "/FI", "IMAGENAME eq Pathfinder GM.exe", "/NH"],
            capture_output=True, text=True).stdout
        note("no stray shell processes holding the lock",
             [] if "Pathfinder GM.exe" not in stray
             else [f"survivors: {' '.join(stray.split())[:120]}"])

    print(f"\n{'ALL CLEAN' if not FAULTS else f'{len(FAULTS)} FAULT(S)'}")
    for f in FAULTS:
        print(" -", f)
    sys.exit(1 if FAULTS else 0)


if __name__ == "__main__":
    main()
