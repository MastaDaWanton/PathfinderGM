"""What has to stay true for the .exe to contain a working game.

Every test here pins a failure that is *silent* in the frozen build. That is the whole
character of packaging bugs and the reason they are worth a test file of their own: a
content directory left out of the spec does not raise, it reads as an empty folder, so the
app starts, serves every page, and has no spells in it. Nothing in the normal suite
notices, because the normal suite runs from a source tree where the folder is right there.

Measured on the first real build of this app (2026-08-24), against `dist/PathfinderGM.exe`
run with `PATHFINDER_GM_DATA` pointed at a throwaway directory:

  - the exe reported `resource_root C:\\...\\Temp\\_MEI335482` and found all eight content
    directories, 3,040 spells, and both fixtures — so the `_MEIPASS` half of `paths.py`
    is right and this file guards it rather than proving it;
  - the browser never opened, because `_open_browser_when_up` parsed the port back out of
    the URL and got `"8917/"`. Every HTTP check passed against that build. Only launching
    the packaged exe with the browser path enabled showed it, and `test_the_browser_opens`
    below is that defect written down.

None of these tests build anything. A build takes ~2.5 minutes and cannot run in a suite
that is expected to finish in 30 seconds; what they pin is everything that can be checked
without one, so a broken build is caught at the commit that breaks it rather than at the
next release.
"""
from __future__ import annotations

import ast
import re
import socket
import threading
from importlib import import_module
from pathlib import Path

import pytest
from django.conf import settings

from pathfindergm import paths

ROOT = Path(__file__).resolve().parent.parent
SPEC = ROOT / "pathfindergm.spec"


# --- the spec knows about every content directory that exists ---------------------------

def _spec_content_dirs() -> set[str]:
    """The `CONTENT_DIRS` list out of the spec, read as source rather than executed.

    Executing a spec needs PyInstaller's injected globals (`Analysis`, `EXE`, `PYZ`), so
    it is parsed instead. That also means this test passes on a machine with no
    PyInstaller installed, which matters because the suite has to run in CI where the
    build does not.
    """
    tree = ast.parse(SPEC.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            names = [t.id for t in node.targets if isinstance(t, ast.Name)]
            if "CONTENT_DIRS" in names:
                return set(ast.literal_eval(node.value))
    raise AssertionError("pathfindergm.spec has no CONTENT_DIRS list")


def test_the_spec_ships_every_content_directory_on_disk():
    """A content folder added to the repo and not to the spec vanishes from the build.

    It does not vanish loudly. `registry.content_dir()` returns a path under `_MEIPASS`
    that simply is not there, `read_folder` returns `{}` for a directory that does not
    exist, and the bench draws zero rows — the same page it draws for a user who has
    authored nothing. There are eight content directories today (bestiary, classes,
    feats, ingredients, materials, spells, weapons, world-classes) holding 26 JSON files
    and 23 MB; the ninth is the one this test exists for.
    """
    on_disk = {p.name for p in (ROOT / "content").iterdir() if p.is_dir()}
    in_spec = _spec_content_dirs()

    assert on_disk - in_spec == set(), (
        f"content/{{{', '.join(sorted(on_disk - in_spec))}}} exists on disk but is not in "
        f"pathfindergm.spec — it would be missing from the .exe, silently")
    assert in_spec - on_disk == set(), (
        f"pathfindergm.spec ships content/{{{', '.join(sorted(in_spec - on_disk))}}}, "
        f"which does not exist. PyInstaller fails the build on a missing data path.")


def test_the_spec_ships_the_other_things_read_off_resource_root():
    """Not everything the app opens lives under `content/`.

    `library.shipped_dir()` reads `fixtures/`, `roster.pregens()` globs `fixtures/pc-*`,
    `play.views.licence` reads `OGL.txt` — and the licence one is not merely a bug if it
    is missing. OGL section 10 requires a copy of the licence to ship with every copy of
    the Open Game Content, so a build without it must not be distributed at all.
    """
    text = SPEC.read_text(encoding="utf-8")
    for needed in ('("fixtures", "fixtures")',
                   '("play/templates", "play/templates")',
                   '("play/static", "play/static")',
                   '("OGL.txt", ".")',
                   '("OGL-NOTICE.md", ".")'):
        assert needed in text, f"pathfindergm.spec does not bundle {needed}"


def test_the_spec_names_the_entry_point_that_exists():
    text = SPEC.read_text(encoding="utf-8")
    assert 'Analysis(\n    ["desktop.py"]' in text or '["desktop.py"]' in text
    assert (ROOT / "desktop.py").is_file()


# --- nothing resolves shipped content through __file__ ----------------------------------

# `paths.py` is the one legitimate user: it is where "am I frozen?" is answered, and its
# `__file__` branch is the *not*-frozen one. Everything else must go through it.
_FILE_ANCHOR_ALLOWED = {"pathfindergm/paths.py"}

# Dev-time only, never imported by the running app. `tools/` builds content files from
# PDFs and `reference/` extracts the rulebooks; neither is in the bundle (see the spec's
# "Deliberately NOT bundled" note), so `__file__` in them is correct and cheap.
# `electron/` is the desktop shell: its node_modules vendors third-party Python
# (node-gyp) that this rule has no jurisdiction over, and the shell itself ships no
# Python at all.
_FILE_ANCHOR_IGNORED_DIRS = {"tools", "reference", "tests", "build", "dist", "docs",
                             "electron", ".claude"}


def _shipped_python_files() -> list[Path]:
    out = []
    for p in ROOT.rglob("*.py"):
        rel = p.relative_to(ROOT)
        if rel.parts[0] in _FILE_ANCHOR_IGNORED_DIRS or "__pycache__" in rel.parts:
            continue
        out.append(p)
    return out


def test_no_shipped_module_anchors_a_path_on_dunder_file():
    """`__file__` frozen points inside the unpacked bundle and says nothing about where
    the app was installed — CLAUDE.md's first packaging rule, and the one that cost the
    most in World Bible.

    Checked as source text rather than by running anything, because the failure is not an
    exception: `Path(__file__).parent / "content"` frozen resolves to a directory that
    happens to exist (the bundle's own), so the wrong answer looks exactly like the right
    one until the user's install directory differs from the temp unpack directory — which
    it always does, and which no dev-machine test can notice.
    """
    offenders = []
    for path in _shipped_python_files():
        rel = path.relative_to(ROOT).as_posix()
        if rel in _FILE_ANCHOR_ALLOWED:
            continue
        for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            stripped = line.strip()
            if stripped.startswith("#") or "__file__" not in stripped:
                continue
            # A docstring or comment naming the rule is the point, not a violation.
            if re.search(r"(Path|os\.path|dirname|abspath)\s*\(\s*__file__", stripped):
                offenders.append(f"{rel}:{i}: {stripped}")
    assert offenders == [], (
        "these anchor a path on __file__ and will point inside the PyInstaller bundle:\n"
        + "\n".join(offenders))


def test_resource_root_and_install_root_are_different_questions():
    """Frozen, they are genuinely different directories, and conflating them is the bug.

    `resource_root()` is `_MEIPASS` — a temp directory that exists only while the app is
    running. `install_root()` is where the .exe sits. Measured on the first build:
    `resource_root C:\\Users\\...\\Temp\\_MEI335482` against
    `install_root  H:\\coding\\PathfinderGM\\dist`. Unfrozen they are both the repo root,
    which is exactly why a dev run cannot tell you whether you used the right one.
    """
    src = (ROOT / "pathfindergm" / "paths.py").read_text(encoding="utf-8")
    assert "_MEIPASS" in src, "resource_root must use sys._MEIPASS when frozen"
    assert "sys.executable" in src, "install_root must use the executable's own location"
    # Unfrozen, they agree — and every path in the app is written against that agreement.
    assert paths.resource_root() == paths.install_root() == ROOT
    assert Path(settings.BASE_DIR) == paths.resource_root()


def test_the_user_data_root_is_never_inside_the_bundle(monkeypatch):
    """Saves written under `_MEIPASS` are deleted when the app closes.

    PyInstaller unpacks a one-file build to a temp directory and removes it on exit, so a
    campaign saved relative to `resource_root()` would survive exactly as long as the
    session that wrote it. Everything writable therefore hangs off `user_data_root()`.

    The override is deliberately cleared first. `tests/conftest.py` points
    `PATHFINDER_GM_DATA` at `.test-data` *inside the repository*, which is right for a
    test run and would make this assertion pass for the wrong reason — the question is
    where a real install writes, not where the suite does.
    """
    monkeypatch.delenv("PATHFINDER_GM_DATA", raising=False)

    real = paths.user_data_root()
    assert real != paths.resource_root()
    assert not real.is_relative_to(paths.resource_root()), (
        f"a real install would write saves into the bundle at {real}")
    assert real.name == paths.APP_NAME
    # And the override still works, because proving a build against a scratch directory
    # depends on it.
    monkeypatch.setenv("PATHFINDER_GM_DATA", str(ROOT / ".test-data"))
    assert paths.user_data_root() == ROOT / ".test-data"
    assert Path(settings.CAMPAIGN_DIR).is_relative_to(paths.user_data_root())


def test_the_data_directory_is_overridable_so_a_build_can_be_proved_against_a_scratch_one():
    """CLAUDE.md: prove a packaging fix by running the built exe against a throwaway data
    directory. That is only possible if the exe will accept one, and it has no terminal to
    take a flag from, so it is an environment variable."""
    src = (ROOT / "pathfindergm" / "paths.py").read_text(encoding="utf-8")
    assert "PATHFINDER_GM_DATA" in src


# --- everything imported by string is importable ----------------------------------------

def test_every_registry_loader_imports():
    """`rules/registry.py` names loaders as `"rules.spells:all_spells"` strings.

    PyInstaller's static analysis sees a string literal and bundles nothing. Worse,
    `registry.shipped()` catches every exception and returns `{}` — deliberately, so one
    broken kind cannot take the homebrew page down — which means a module missing from
    the bundle presents as a bench with no shipped content rather than as an error. This
    test resolves each target the way the app does, without the swallow.
    """
    from rules import registry

    for kind_id, kind in registry.KINDS.items():
        for label, target in (("shipped_loader", kind.shipped_loader),
                              ("derive", kind.derive)):
            if not target:
                continue
            module_name, sep, func_name = target.partition(":")
            assert sep, f"{kind_id}.{label} = {target!r} is not 'module:function'"
            module = import_module(module_name)
            assert callable(getattr(module, func_name, None)), (
                f"{kind_id}.{label} names {target!r}, which is not callable")


def test_every_registry_shipped_loader_actually_returns_content():
    """Resolving is not the same as loading. A loader that imports fine but reads a
    content directory the spec forgot returns `{}` — the empty-folder failure again, one
    layer up. The counts are the ones the first build reported: 3,040 spells and 161
    ingredients through the herb shelf.
    """
    from rules import registry

    loaded = {k: registry.shipped(k) for k in registry.KINDS
              if registry.KINDS[k].shipped_loader}
    empty = [k for k, v in loaded.items() if not v]
    assert empty == [], f"shipped loaders returned nothing for: {', '.join(empty)}"
    assert len(loaded["spells"]) >= 3000, len(loaded["spells"])


def test_every_bench_module_imports():
    """`rules/benches.py` routes five crafts and one mode by dotted string, and
    `module_for` converts an ImportError into `UnknownBench` — so a craft missing from
    the bundle reads as "that bench is not built yet" rather than as a broken build.
    """
    from rules import benches

    for track, module_name in benches.BENCHES.items():
        assert import_module(module_name), track
    for mode, (_owner, module_name) in benches.MODES.items():
        assert import_module(module_name), mode


def test_the_craft_page_materials_modules_import():
    """`play/craft_views.py` keeps its own dotted-string map, separate from `benches`.

    Two copies of the same routing table is the shape CLAUDE.md warns about, and the
    consequence here is specific: `_MATERIALS_OF` is what fills the four forge shelves,
    and it is indexed without a fallback, so a name that does not import is a 500 on the
    craft page rather than a quiet empty list.
    """
    from play.craft_views import _MATERIALS_OF

    for track, module_name in _MATERIALS_OF.items():
        module = import_module(module_name)
        assert callable(getattr(module, "materials", None)), (
            f"{module_name} is the shelf for {track} but has no materials()")


def test_the_spec_collects_the_packages_that_hold_the_string_imported_modules():
    """The tests above prove the modules import *in a source tree*. What makes them import
    in the bundle is `collect_submodules`, and losing that line would break the build
    without breaking a single test above."""
    text = SPEC.read_text(encoding="utf-8")
    for package in ("rules", "play", "gm", "world", "pathfindergm"):
        assert f'collect_submodules("{package}")' in text, package


# --- the packaged app serves its own static files ----------------------------------------

def test_static_files_are_routed_without_runserver():
    """`runserver` inserts the static route itself; the frozen exe does not run it.

    Without an explicit route the packaged app loads every page with no backgrounds, no
    fonts and no dice — and does it silently, because a 404 on a CSS background image is
    not an error anywhere the user or the log can see. Verified served by the real exe:
    /static/js/dice3d.js came back 200 at 25,182 bytes and
    /static/img/leather-tile.jpg 200 at 157,383 bytes with a JPEG magic number.
    """
    from django.test import Client

    client = Client()
    response = client.get("/static/js/dice3d.js")
    assert response.status_code == 200
    body = b"".join(response.streaming_content) if response.streaming else response.content
    assert len(body) > 1000


def test_the_static_route_does_not_depend_on_debug():
    """`django.contrib.staticfiles.views.serve` raises Http404 when DEBUG is off unless it
    is passed `insecure=True`. DEBUG is True today; a later build that turns it off for
    the packaged app must not lose its stylesheets on the way."""
    from django.test import Client, override_settings

    with override_settings(DEBUG=False):
        response = Client().get("/static/js/dice3d.js")
        assert response.status_code == 200, (
            "the static route stops working with DEBUG off — pass insecure=True")


# --- the launcher ------------------------------------------------------------------------

def test_the_browser_opens_at_the_url_the_server_bound():
    """The defect this file was written after: the browser thread died on every launch.

    `_open_browser_when_up` parsed the port back out of `"http://127.0.0.1:8917/"` with
    `url.rsplit(":", 1)[1]`, which is `"8917/"`, and `int()` raised ValueError inside a
    daemon thread. The server itself was fine — it answered every one of the fifteen HTTP
    checks driven against the packaged build — so nothing failed except the app's one
    job of opening itself. The port is passed in explicitly now.
    """
    import desktop

    listener = socket.socket()
    listener.bind((desktop.HOST, 0))
    listener.listen(1)
    port = listener.getsockname()[1]

    opened: list[str] = []
    original = desktop.webbrowser.open
    desktop.webbrowser.open = lambda url: opened.append(url) or True
    try:
        url = f"http://{desktop.HOST}:{port}/"
        thread = threading.Thread(target=desktop._open_browser_when_up, args=(url, port))
        thread.start()
        thread.join(timeout=15)
        assert not thread.is_alive(), "the browser thread hung"
    finally:
        desktop.webbrowser.open = original
        listener.close()

    assert opened == [f"http://{desktop.HOST}:{port}/"], opened


def test_the_launcher_falls_back_to_a_free_port():
    """A desktop app that refuses to start because something owns its port is a support
    ticket nobody can answer without a terminal. Binding 8917 twice must give a second
    server on an OS-chosen port, not an exception — and not, as it first did, a second
    server on 8917.

    Django's `WSGIServer` defaults `allow_reuse_address=True`. On Windows that flag means
    "bind even though somebody already has this port", not the Unix TIME_WAIT meaning, so
    the first version of `_bind` cheerfully bound 8917 twice: the fallback branch never
    ran and two live copies of the app split incoming connections between them at random.
    The measurement is the assertion below — the second server's port must differ.
    """
    import desktop

    first = desktop._bind(desktop.HOST, desktop.PREFERRED_PORT)
    try:
        assert first.server_address[1] == desktop.PREFERRED_PORT
        second = desktop._bind(desktop.HOST, desktop.PREFERRED_PORT)
        try:
            assert second.server_address[1] not in (0, desktop.PREFERRED_PORT)
        finally:
            second.server_close()
    finally:
        first.server_close()


def test_the_launcher_never_shells_out_to_runserver():
    """`runserver` brings the autoreloader, which re-executes `sys.executable` with
    Django's own argv. Frozen, `sys.executable` is the app, so the reloader relaunches the
    whole desktop app — the classic frozen-Django fork bomb of windows. The entry point
    uses `ThreadedWSGIServer` directly for that reason and must keep doing so."""
    src = (ROOT / "desktop.py").read_text(encoding="utf-8")
    # Checked against the parsed module with its docstrings removed, rather than the raw
    # text: the docstrings in `desktop.py` explain at length *why* runserver is not used,
    # and a substring search for the word finds the explanation instead of a call.
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef,
                             ast.ClassDef)) and ast.get_docstring(node):
            node.body = node.body[1:]
    code = ast.dump(tree)
    for banned in ("execute_from_command_line", "call_command", "runserver"):
        assert banned not in code, f"desktop.py reaches for {banned}"
    assert "ThreadedWSGIServer" in code


# --- the stale-cache rule ---------------------------------------------------------------

def test_nothing_derived_is_written_into_the_user_data_directory():
    """CLAUDE.md's second packaging rule is about *derived* files outside the install
    directory. As of this build there are none, and that is the finding, not an omission.

    Everything under `%LOCALAPPDATA%\\PathfinderGM\\` is authored or chosen by the user —
    `campaigns/` and `characters/` are saves, `worlds/` holds exports the user imported,
    `homebrew/` holds things they wrote in the builder, `models.json` and the house rules
    are settings. None of it is computed from shipped content, so none of it can go stale
    against a newer build the way World Bible's derived stylesheet did.

    The one cache in the app is `world.loader._cached`, and it is in-memory, keyed on the
    file's mtime, and gone when the process exits. This test pins that: an on-disk cache
    appearing under the user data root is the moment `paths.CACHE_VERSION` has to start
    being written and compared, and a green suite should not be what carries it.
    """
    import inspect

    from world import loader

    source = inspect.getsource(loader)
    assert "lru_cache" in source and "st_mtime" in source, (
        "world.loader's cache changed shape — if it now writes to disk under "
        "user_data_root(), it must carry paths.CACHE_VERSION and compare content")

    # The claim in paths.py must match the code. A comment promising that derived files
    # carry a stamp, in a build where nothing does, is worse than no comment: the next
    # person reads it as a guarantee that has already been implemented.
    doc = (ROOT / "pathfindergm" / "paths.py").read_text(encoding="utf-8")
    assert "CACHE_VERSION" in doc
    assert "nothing derived" in doc.lower() or "no derived" in doc.lower(), (
        "paths.CACHE_VERSION is unused — say so where it is defined, or use it")


@pytest.mark.parametrize("name", ["campaigns", "characters", "worlds", "homebrew"])
def test_the_writable_directories_all_hang_off_the_user_data_root(name):
    """Each of these is created by a different module, and each computes its path from
    `settings.CAMPAIGN_DIR.parent` rather than from a shared helper. Frozen, a single one
    of them anchored anywhere else would write into `_MEIPASS` and lose the user's saves
    when the app closed."""
    from play import homebrew as homebrew_mod
    from play import library, roster

    made = {
        "campaigns": Path(settings.CAMPAIGN_DIR),
        "characters": Path(settings.CAMPAIGN_DIR).parent / "characters",
        "worlds": library.user_dir(),
        "homebrew": homebrew_mod.root(),
    }[name]
    assert made.is_relative_to(paths.user_data_root()), (name, made)
    assert roster is not None  # imported for the side effect of proving it loads

    # And the same four, computed against a data root that is *not* under the repo — which
    # is what a real install has. `conftest.py` puts the test data root inside the
    # repository, so checking "not inside the bundle" against the live value would pass
    # for a reason that has nothing to do with the frozen build.
    from django.test import override_settings

    elsewhere = Path(settings.CAMPAIGN_DIR).parent
    with override_settings(CAMPAIGN_DIR=str(Path("Z:/nowhere/PathfinderGM/campaigns"))):
        moved = {
            "campaigns": Path(settings.CAMPAIGN_DIR),
            "characters": Path(settings.CAMPAIGN_DIR).parent / "characters",
            "worlds": Path(settings.CAMPAIGN_DIR).parent / "worlds",
            "homebrew": Path(settings.CAMPAIGN_DIR).parent / "homebrew",
        }[name]
        assert not moved.is_relative_to(paths.resource_root()), (
            f"{name} would be written inside the bundle and deleted on exit")
        assert moved.is_relative_to(Path("Z:/nowhere/PathfinderGM")), (
            f"{name} does not follow CAMPAIGN_DIR — it is anchored somewhere else, and "
            f"frozen that somewhere is inside the bundle")
    assert Path(settings.CAMPAIGN_DIR).parent == elsewhere


def test_the_frozen_build_turns_debug_off_and_keeps_its_own_key():
    """Two things the first build would have shipped, both found by reading what the
    settings claimed against what they did.

    `DEBUG = True` was unconditional: a 500 in a shipped game would have served source,
    settings and local variables to whatever could reach the port. And the comment said
    the secret key "is regenerated per install in the packaged build" while nothing
    regenerated it — every copy of the exe would have carried one literal key, which is
    the single thing a secret key may not be.

    Asserted against the module's own logic rather than by freezing, because freezing
    inside a test would take a hundred seconds; `docs/packaging.md` records what was
    verified against the real exe.
    """
    import importlib

    from pathfindergm import paths

    src = (Path(__file__).resolve().parent.parent
           / "pathfindergm" / "settings.py").read_text(encoding="utf-8")
    assert "DEBUG = not is_frozen()" in src, "DEBUG is not tied to the frozen build"
    assert "secret_key() if is_frozen()" in src, "the key is not per install"

    # The key is made once and read back, not remade on every call — a key that changed
    # on restart would log the player out of their own session each time.
    importlib.reload(paths)
    first = paths.secret_key()
    assert len(first) >= 50
    assert paths.secret_key() == first, "the key changes between calls"



def test_the_portfile_is_the_handshake_a_shell_can_trust(tmp_path):
    """The Electron shell cannot assume 8917 — the free-port fallback is real — and
    parsing the human banner is how the browser thread died of a ValueError once.
    `server.json` carries port, url and pid; the pid is what lets a shell tell a stale
    file from a crashed run apart from a live one."""
    import json
    import os

    import desktop

    p = desktop._write_portfile(tmp_path, 49221, "http://127.0.0.1:49221/")
    assert p == tmp_path / "server.json"
    d = json.loads(p.read_text(encoding="utf-8"))
    assert d["port"] == 49221
    assert d["pid"] == os.getpid()
    assert d["url"].endswith(":49221/")
    # And no half-written temp file is left beside it.
    assert not list(tmp_path.glob("*.tmp"))


def test_the_log_file_survives_the_console_being_hidden(tmp_path, capsys):
    """`console=False` needs a log file first — packaging.md has said so since the
    first build. Appended across launches with a dated header (the run before the
    crash is the one a bug report needs), truncated at 2 MB rather than rotated, and
    the console still sees everything: the tee is a wrapper, not a redirect, because
    the console window is the unwrapped build's only quit affordance."""
    import sys

    import desktop

    real_out, real_err = sys.stdout, sys.stderr
    try:
        log = desktop._start_log(tmp_path)
        assert log is not None
        print("both places, please")
        sys.stdout.flush()
    finally:
        sys.stdout, sys.stderr = real_out, real_err
        if log:
            log.close()

    body = (tmp_path / "logs" / "pathfindergm.log").read_text(encoding="utf-8")
    assert "=== launch" in body
    assert "both places, please" in body
    assert "both places, please" in capsys.readouterr().out

    # A bloated log is truncated at the next launch, not grown forever.
    big = tmp_path / "logs" / "pathfindergm.log"
    big.write_text("x" * 2_100_000, encoding="utf-8")
    try:
        log = desktop._start_log(tmp_path)
    finally:
        sys.stdout, sys.stderr = real_out, real_err
        if log:
            log.close()
    assert big.stat().st_size < 1_000


def test_the_portfile_is_written_after_bind_and_removed_on_shutdown():
    """Source pin: the handshake must carry the *real* port (after `_bind`, which may
    have fallen back), and a clean shutdown takes the file with it so only crashed
    runs leave one — with a dead pid, which is the tell."""
    import inspect

    import desktop

    src = inspect.getsource(desktop.main)
    assert src.index("_bind(") < src.index("_write_portfile(")
    assert "portfile.unlink()" in src
