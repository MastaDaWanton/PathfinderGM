"""The packaged window hands only web and mail links to Windows.

Review 2026-11-11, finding 2: both `setWindowOpenHandler` and `will-navigate` in
`electron/main.js` passed whatever URL the page named to `shell.openExternal`, which
gives it to the Windows shell. With script in the page, `window.open('file:///C:/…exe')`
or a custom protocol was a program run on the player's machine.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

MAIN = Path(__file__).resolve().parent.parent / "electron" / "main.js"


def _src() -> str:
    return MAIN.read_text(encoding="utf-8")


def test_both_handlers_go_through_the_one_filtered_door():
    src = _src()
    # The only raw calls left are inside the two functions that check the URL first.
    assert "shell.openExternal(target);" not in src
    handlers = src[src.index("setWindowOpenHandler("):src.index("wireReportDownloads(mainWindow")]
    assert handlers.count("openOutside(target)") == 2
    assert "shell.openExternal" not in handlers
    # The game's own pages still navigate in the window, judged by origin (below).
    assert "if (!isBackend(target))" in handlers


def test_the_door_drops_everything_but_http_https_and_mailto(tmp_path):
    """Run the real function under node with a recording `shell`."""
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    src = _src()
    m = re.search(r"const OUTSIDE_PROTOCOLS = .*?\nfunction openOutside\(target\) \{.*?\n\}\n", src, re.S)
    assert m, "openOutside is not where this test expects it"
    cases = {
        "https://github.com/MastaDaWanton/World-Bible": True,
        "http://127.0.0.1:8917/manual/": True,
        "mailto:someone@example.com": True,
        "file:///C:/Windows/System32/calc.exe": False,
        "C:\\Windows\\System32\\calc.exe": False,
        "ms-msdt:/id PCWDiagnostic": False,
        "javascript:alert(1)": False,
        "search-ms:query=x": False,
        "not a url": False,
        "": False,
    }
    script = (
        "const opened = [];\n"
        "const shell = { openExternal: (u) => { opened.push(u); return Promise.resolve(); } };\n"
        "const updateLog = () => {};\n"
        + m.group(0)
        + f"for (const u of {json.dumps(list(cases))}) openOutside(u);\n"
        "console.log(JSON.stringify(opened));\n"
    )
    # From a file, as the other node tests do: the script on the command line was
    # refused by Windows outright (WinError 5) for the paths it names.
    f = tmp_path / "door.js"
    f.write_text(script, encoding="utf-8")
    out = subprocess.run([node, str(f)], capture_output=True, text=True, timeout=60)
    assert out.returncode == 0, out.stderr
    assert json.loads(out.stdout) == [u for u, ok in cases.items() if ok]


def test_only_the_backends_own_origin_stays_in_the_window(tmp_path):
    """It was `target.startsWith(backendUrl)`: `http://127.0.0.1:8917@evil.example/` passes
    that (everything before `@` is a user name), so a script in the page could load a
    stranger's page into the game's own window. Run the real function under node."""
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    m = re.search(r"\nfunction isBackend\(target\) \{.*?\n\}\n", _src(), re.S)
    assert m, "isBackend is not where this test expects it"
    cases = {
        "http://127.0.0.1:8917/play/": True,
        "http://127.0.0.1:8917/?tab=settings": True,
        "http://127.0.0.1:8917@evil.example/": False,
        "http://127.0.0.1:89170/": False,
        "http://127.0.0.1:8918/": False,
        "https://127.0.0.1:8917/": False,
        "file:///C:/Windows/": False,
        "not a url": False,
    }
    script = ("let backendUrl = 'http://127.0.0.1:8917';\n" + m.group(0)
              + f"console.log(JSON.stringify({json.dumps(list(cases))}.map(isBackend)));\n"
              + "backendUrl = null; console.log(JSON.stringify(isBackend('http://127.0.0.1:8917/')));\n")
    f = tmp_path / "origin.js"
    f.write_text(script, encoding="utf-8")
    out = subprocess.run([node, str(f)], capture_output=True, text=True, timeout=60)
    assert out.returncode == 0, out.stderr
    first, second = out.stdout.strip().splitlines()
    assert json.loads(first) == list(cases.values())
    assert json.loads(second) is False      # before the backend answers, nothing is ours


def test_the_window_is_sandboxed_and_grants_no_permission():
    """Electron grants camera, microphone and location requests unless a handler says no
    (security checklist item 5); the game asks for none of them."""
    src = _src()
    prefs = src.split("webPreferences", 1)[1].split("});", 1)[0]
    assert "sandbox: true" in prefs and "nodeIntegration: false" in prefs
    assert "contextIsolation: true" in prefs and "preload:" not in prefs
    handler = src[src.index("setPermissionRequestHandler("):][:200]
    assert "callback(false)" in handler
