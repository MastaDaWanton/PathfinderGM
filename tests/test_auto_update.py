"""Updates the app offers and never applies behind the player's back.

Asked for on 2026-09-15: "also add automatic updates to PathfinderGM", and then, when the
signing question came up, "i will never pay for that if this app gets verified it will be
through people downloading it."

**The app is unsigned and staying that way, so what is verified is worth writing down.**
`latest.yml` comes from GitHub over TLS and carries a SHA-512 of the installer, which
electron-updater checks after downloading — a network attacker cannot substitute a binary.
What is missing is the Authenticode check: with no certificate there is no publisher name
to compare against, so a release published by somebody who had taken the GitHub account
would be installed. That is the same trust anyone downloading by hand already places in
the releases page; automating it widens who is affected.

Which is the reason for the shape these tests pin: **nothing downloads or installs without
a press.** `autoDownload` and `autoInstallOnAppQuit` are both off. It is the same idiom as
the rest of the app — find out what is missing, say so, offer a button — and here it is
also the mitigation.

These are what Python can hold: that the wiring exists, that the two automatic behaviours
are off, that it cannot fire in the places it would break, and that the dependency is
actually in the build. Whether a real update installs is not testable without publishing
one, and `docs/packaging.md` records that as unproven rather than claiming it.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from django.conf import settings

ELECTRON = Path(settings.BASE_DIR, "electron")


def _main() -> str:
    return (ELECTRON / "main.js").read_text(encoding="utf-8")


def _pkg() -> dict:
    return json.loads((ELECTRON / "package.json").read_text(encoding="utf-8"))


def _code(js: str) -> str:
    """The shell without its comments. Every source-reading test in this repo has now
    been bitten by prose at least once — a CDN named in a docstring, a defect named in a
    comment, an `os.startfile, not subprocess` note — so this file starts with the
    stripper instead of earning it."""
    out, i, n = [], 0, len(js)
    while i < n:
        if js.startswith("/*", i):
            i = js.find("*/", i + 2)
            if i < 0:
                break
            i += 2
        elif js.startswith("//", i):
            i = js.find("\n", i)
            if i < 0:
                break
        else:
            out.append(js[i])
            i += 1
    return "".join(out)


# --- nothing happens without a press --------------------------------------------------------

def test_nothing_downloads_or_installs_on_its_own():
    """The whole design, and the mitigation for an unsigned update. A 115 MB download
    that starts itself on a metered connection, or a version that changes underneath
    somebody mid-campaign, is the opposite of what this app does everywhere else."""
    js = _code(_main())
    assert "updater.autoDownload = false;" in js
    assert "updater.autoInstallOnAppQuit = false;" in js


def test_the_player_is_asked_twice_and_can_refuse_both_times():
    """Once before 115 MB is spent, once before the game closes."""
    js = _code(_main())
    assert js.count("showMessageBox") >= 2, "one of the two questions is not asked"
    for button in ("Download it", "Not now", "Install and restart",
                   "Next time I close it"):
        assert button in _main(), f"no way to answer: {button}"


def test_an_update_check_never_runs_before_the_game_is_on_screen():
    """It is a network call that can hang for its own timeout, and nothing about it is
    worth putting between a player and the thing they double-clicked."""
    js = _code(_main())
    assert re.search(r"showGame\(url\);\s*wireUpdates\(\);", js), \
        "wireUpdates no longer runs after the window has the game in it"


def test_a_failed_check_is_logged_and_never_shown():
    """Offline, GitHub down, a rate limit — all normal, none of them worth a box in
    front of somebody's game."""
    js = _code(_main())
    handler = js[js.index("updater.on('error'"):js.index("updater.on('error'") + 200]
    assert "console.error" in handler
    assert "dialog" not in handler, "an update failure puts a dialog on screen"


# --- where it must not fire -----------------------------------------------------------------

def test_it_does_not_run_unpackaged():
    """There is no `app-update.yml` in a dev tree and electron-updater throws rather than
    shrugging, which would take `prove_shell.py`'s dev-shell run down with it."""
    assert "if (!isPackaged) return;" in _code(_main())


def test_the_provers_can_switch_it_off_and_do():
    """A run whose result depends on whether a newer version happens to exist is not a
    proof of a lifecycle."""
    js = _code(_main())
    assert "PATHFINDER_GM_NO_UPDATE" in js
    prover = (Path(settings.BASE_DIR, "tools", "prove_shell.py")
              .read_text(encoding="utf-8"))
    assert 'PATHFINDER_GM_NO_UPDATE="1"' in prover, "prove_shell no longer switches it off"


def test_installing_goes_out_through_the_same_door_every_exit_uses():
    """`quitAndInstall` quits the app, so `before-quit` fires and the backend is stopped
    the way it is on any other exit. That ordering is the only reason the backend does not
    outlive an update — which is the exact failure `prove_shell.py` exists for."""
    js = _code(_main())
    assert "updater.quitAndInstall();" in js
    assert "app.on('before-quit', stopBackend);" in js


# --- the build has to carry it ---------------------------------------------------------------

def test_electron_updater_ships_inside_the_app():
    """A dependency, not a devDependency: it has to be in the asar at runtime. And named
    in `build.files`, because that list is an explicit allow-list — the kind of thing that
    silently drops a new dependency and produces "Cannot find module" on a machine that is
    not this one."""
    pkg = _pkg()
    assert "electron-updater" in (pkg.get("dependencies") or {}), \
        "electron-updater is not a runtime dependency"
    assert "electron-updater" not in (pkg.get("devDependencies") or {})
    assert "node_modules/**/*" in pkg["build"]["files"], \
        "the asar would not carry node_modules"


def test_the_feed_points_at_this_repository():
    """Without `publish`, electron-builder writes no `latest.yml` beside the installer and
    embeds no `app-update.yml` — and the failure is at runtime on a player's machine
    rather than at build time here."""
    publish = _pkg()["build"]["publish"]
    assert publish and publish[0]["provider"] == "github"
    assert publish[0]["owner"] == "MastaDaWanton"
    assert publish[0]["repo"] == "PathfinderGM"


def test_the_shell_carries_no_control_bytes():
    """Same guard the templates got, for the same reason, on the same day."""
    raw = (ELECTRON / "main.js").read_bytes()
    for bad in (b"\x00", b"\x08", b"\x1b"):
        assert bad not in raw, f"main.js carries a literal {bad!r}"
    raw.decode("utf-8")


def test_the_header_no_longer_says_there_is_nothing_to_update_from():
    """`main.js` opened by listing electron-updater as deliberately not ported: "this repo
    has no release pipeline to update from yet. Thin beats speculative." There is one now,
    and a comment that contradicts the code beneath it is the copy nobody looks at."""
    head = _main()[:2000]
    assert "no release pipeline to update from yet" not in head or \
           "It has one now" in head, "the header still refuses what the file now does"


# --- the manifest has to name a file that exists ---------------------------------------------

def test_the_artifact_name_is_pinned_so_the_manifest_can_find_it():
    """Measured 2026-09-15, before anything was published.

    electron-builder writes the installer's name into `latest.yml` with spaces replaced by
    hyphens, so a product name with spaces in it produces a manifest naming a file that
    does not exist:

        latest.yml wanted   Pathfinder-GM-Setup-0.1.6.exe
        the build produced  Pathfinder GM Setup 0.1.6.exe
        0.1.5 was published PathfinderGM-Setup-0.1.5.exe

    Three different strings for one file. Every auto-update would have fetched the
    manifest, asked GitHub for a name no asset had, and failed — silently, because a
    failed check is logged and never shown, which is right for being offline and exactly
    wrong for this. Pinning `artifactName` makes the file, the manifest and the uploaded
    asset one string with no rename step to forget.
    """
    nsis = _pkg()["build"]["nsis"]
    assert nsis.get("artifactName") == "Pathfinder-GM-Setup-${version}.${ext}", \
        "the artifact name is unpinned; the manifest and the file can drift apart again"


def test_a_built_manifest_names_a_file_that_is_there():
    """The check itself, run against a real build when one is present. Skipped rather than
    faked when `release/` is empty: `dist/` and `release/` are gitignored and a checkout
    has neither, and a test that invents a manifest proves nothing about the build."""
    import pytest

    release = ELECTRON / "release"
    manifest = release / "latest.yml"
    if not manifest.exists():
        pytest.skip("no build in electron/release — run `npm run dist` to check this")
    named = ""
    for line in manifest.read_text(encoding="utf-8").splitlines():
        if line.startswith("path:"):
            named = line.split(":", 1)[1].strip()
    assert named, "latest.yml names no installer at all"
    assert (release / named).exists(), (
        f"latest.yml points at {named!r}, which is not in release/. An update would ask "
        f"GitHub for an asset by that name and get a 404.")
