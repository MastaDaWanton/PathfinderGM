"""The button that gets Ollama, and the four things that make it safe to press.

Asked for on 2026-09-15: "I want a button that will install Ollama similar to how we pull
the models with a button. I dont want the user to have to leave the app to set it up if
they dont have the models or Ollama because that can be confusing for people."

This reverses one line of `docs/first-run.md`, which had the app link to the download page
"rather than fetching and running OllamaSetup.exe itself", because an unsigned app that
runs a second installer is a shape antivirus heuristics watch for. The worry was right and
is answered rather than dropped, so these tests are about the answer:

1. **The URL is a constant.** The endpoint takes no parameters, so it cannot be pointed
   anywhere. `setup_pull` needs a guard for this — it takes a model name, and without a
   check it is an arbitrary-download button on a localhost port. This one has nothing to
   check because it has nothing to take.
2. **Nothing runs unverified.** A PE header, a plausible size, and then Windows' own
   WinVerifyTrust, which must return a trusted signature naming Ollama. Anything else is
   deleted rather than executed.
3. **It opens visibly, through the shell.** `os.startfile`, so the player sees Ollama's
   own signed installer and agrees to it — and so there is no pipe to deadlock on, which
   `pathfindergm/version.py` records four hours of.
4. **It refuses when Ollama is already there**, because the only cost of this button is a
   1.5 GB download and spending that for somebody who is merely missing a model is the
   kind of thing nobody reports and everybody resents.
"""
from __future__ import annotations

import inspect
import json
from pathlib import Path

import pytest

from play import preflight, setup_views


def _code(src: str) -> str:
    """Python source with its comments and docstrings gone.

    Because a test that reads prose fires on the sentence describing the rule it
    enforces, and this is the THIRD time in one day: `test_it_carries_no_third_party_code`
    tripped on a docstring saying a CDN is not available, the exe content check tripped on
    one naming the old `.face-a` defect, and the first version of
    `test_it_is_opened_through_the_shell_and_never_as_a_pipe` below failed on the comment
    reading "`os.startfile`, not `subprocess`".
    """
    import io
    import tokenize

    out = []
    for tok in tokenize.generate_tokens(io.StringIO(src).readline):
        if tok.type in (tokenize.COMMENT, tokenize.STRING):
            continue
        out.append(tok.string)
    return " ".join(out)


# --- what it cannot be talked into doing --------------------------------------------------

def test_the_endpoint_takes_nothing_and_so_cannot_be_aimed():
    """The pull endpoint has to validate its `model` against what a role is configured to
    use, or it is an arbitrary download on a localhost port. This one closes that hole by
    construction: there is no input to validate."""
    src = inspect.getsource(setup_views.setup_install)
    assert "read_body" not in src, "the install endpoint has started taking a body"
    assert "preflight.fetch_and_run_installer()" in src, \
        "it no longer calls the installer with no arguments"


def test_the_url_is_a_constant_pointed_at_ollama_over_https():
    assert preflight.INSTALLER_URL.startswith("https://ollama.com/")
    assert preflight.INSTALLER_URL.endswith(".exe")


def test_it_refuses_when_ollama_is_already_installed(monkeypatch, rf):
    """A 1.5 GB download for somebody who is only missing a model."""
    for state in ("ready", "not-running", "missing-models", "unreachable"):
        monkeypatch.setattr(
            preflight, "check",
            lambda timeout=3, s=state: preflight.Report(state=s, host="http://x"))
        resp = setup_views.setup_install(rf.post("/api/setup/install"))
        assert resp.status_code == 409, state


# --- what it refuses to run ----------------------------------------------------------------

def _frames(monkeypatch, tmp_path, payload: bytes, *, signed=(True, "Ollama"),
            claimed: int | None = None):
    """Drive the generator with a fake download and a fake signature."""
    target = tmp_path / "OllamaSetup.exe"
    monkeypatch.setattr(preflight, "installer_path", lambda: target)
    monkeypatch.setattr(preflight, "signature_of", lambda p: signed)
    monkeypatch.setattr(preflight, "on_windows", lambda: True)

    class FakeResponse:
        url = "https://release-assets.githubusercontent.com/whatever"
        headers = {"Content-Length": str(claimed if claimed is not None
                                          else len(payload))}

        def __init__(self):
            self._data = payload

        def read(self, n=-1):
            out, self._data = self._data[:n], self._data[n:]
            return out

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    monkeypatch.setattr(preflight.urllib.request, "urlopen",
                        lambda *a, **k: FakeResponse())
    opened = []
    monkeypatch.setattr(preflight.os, "startfile", lambda p: opened.append(p),
                        raising=False)
    # Stop the wait loop from running for ten minutes in a unit test.
    monkeypatch.setattr(
        preflight, "check",
        lambda timeout=3: preflight.Report(state="missing-models", host="http://x"))
    return list(preflight.fetch_and_run_installer(wait_seconds=0)), opened, target


def test_a_file_that_is_not_a_windows_program_is_deleted_unrun(monkeypatch, tmp_path):
    """A captive portal or a proxy answering instead of ollama.com. The size check alone
    would pass this if the portal's page were large enough, which is why the magic number
    is read too."""
    html = b"<html>a hotel wifi login page</html>" + b"x" * preflight.SMALLEST_PLAUSIBLE
    frames, opened, target = _frames(monkeypatch, tmp_path, html)
    assert opened == [], "it ran something that is not a program"
    assert not target.exists(), "the refused download was left on disk"
    assert any("not a Windows program" in f.get("error", "") for f in frames), frames


def test_an_unsigned_download_is_deleted_unrun(monkeypatch, tmp_path):
    """The check that answers the objection in `docs/first-run.md`. We cannot make
    ourselves signed from in here; we can refuse to execute what Windows will not vouch
    for, which is stronger than a digest fetched over the same connection."""
    exe = b"MZ" + b"\0" * preflight.SMALLEST_PLAUSIBLE
    frames, opened, target = _frames(monkeypatch, tmp_path, exe, signed=(False, ""))
    assert opened == [], "it ran a binary Windows would not vouch for"
    assert not target.exists()
    assert any("would not vouch" in f.get("error", "") for f in frames), frames


def test_a_signature_by_somebody_else_is_refused(monkeypatch, tmp_path):
    """Valid, trusted, and not Ollama's. A signature check that only asks "is it signed"
    accepts anything signed by anyone, which is most malware worth worrying about."""
    exe = b"MZ" + b"\0" * preflight.SMALLEST_PLAUSIBLE
    frames, opened, _ = _frames(monkeypatch, tmp_path, exe,
                                signed=(True, "Some Other Publisher Ltd"))
    assert opened == []
    assert any("Some Other Publisher" in f.get("error", "") for f in frames), frames


def test_an_implausible_content_length_is_refused_before_a_byte_is_written(
        monkeypatch, tmp_path):
    """The cheap half: a 2 KB answer is refused from the header, without spending the
    download to discover it."""
    frames, opened, target = _frames(monkeypatch, tmp_path, b"nope" * 100)
    assert opened == []
    assert not target.exists(), "a refused download should not have been started"
    assert any("not the shape of the installer" in f.get("error", "") for f in frames), \
        frames


def test_a_download_that_stops_early_is_deleted_unrun(monkeypatch, tmp_path):
    """And the half the header cannot catch: `Content-Length` promised the real size, the
    connection dropped, and only the file on disk knows."""
    frames, opened, target = _frames(monkeypatch, tmp_path, b"MZ" + b"\0" * 4096,
                                     claimed=1_501_000_000)
    assert opened == []
    assert not target.exists()
    assert any("stopped at" in f.get("error", "") for f in frames), frames


def test_a_good_download_is_opened_and_the_bar_gets_frames(monkeypatch, tmp_path):
    """The happy path: progress the page can draw, then the installer opened."""
    exe = b"MZ" + b"\0" * preflight.SMALLEST_PLAUSIBLE
    frames, opened, target = _frames(monkeypatch, tmp_path, exe)
    assert len(opened) == 1 and opened[0] == str(target), opened
    assert target.exists(), "the installer was deleted before it could be run"
    progress = [f for f in frames if f.get("total") and f.get("completed") is not None]
    assert progress, "nothing for the progress bar to draw"
    assert progress[-1]["completed"] == len(exe)
    assert any("signed by Ollama" in f.get("status", "") for f in frames), frames


def test_it_is_opened_through_the_shell_and_never_as_a_pipe():
    """`os.startfile`, not `subprocess`. `pathfindergm/version.py` records what shelling
    out from the frozen build under the Electron shell cost last time: git hung on the
    Windows pipes and `communicate()` waited on them forever (bpo-38207). A 1.5 GB
    installer that a player watches is the same shape and a worse place to learn it."""
    src = _code(inspect.getsource(preflight.fetch_and_run_installer))
    assert "startfile" in src
    for banned in ("subprocess", "Popen", "communicate"):
        assert banned not in src, banned


def test_it_says_so_rather_than_failing_quietly_off_windows(monkeypatch):
    """`on_windows` is its own function so this can be asked without patching `os.name`,
    which `pathlib` also reads — the first version of this test got
    `cannot instantiate 'PosixPath' on your system` from code that never mentioned it."""
    monkeypatch.setattr(preflight, "on_windows", lambda: False)
    frames = list(preflight.fetch_and_run_installer())
    assert len(frames) == 1 and "Windows-only" in frames[0]["error"], frames


# --- the page ------------------------------------------------------------------------------

def _page() -> str:
    from django.conf import settings

    return Path(settings.BASE_DIR, "play", "templates", "play",
                "home.html").read_text(encoding="utf-8")


def test_the_button_is_on_the_page_and_the_link_survives_beside_it():
    """Both, deliberately. The button cannot serve macOS or Linux, and some players would
    simply rather install it themselves."""
    page = _page()
    assert "data-install" in page, "no install button"
    assert "/api/setup/install" in page, "the button posts nowhere"
    assert "or get it yourself" in page, "the manual route was removed"
    assert "SETUP.download" in page, "the download link lost its href"


def test_both_downloads_read_the_stream_in_one_place():
    """The chunk-boundary rule — "a chunk boundary lands anywhere, including mid-object" —
    was learned once. A second copy of the reader is a second chance to lose it."""
    page = _page()
    assert page.count("getReader()") == 1, "the NDJSON reader has been copied"
    assert "async function streamSetup(" in page


def test_the_template_carries_no_control_bytes():
    """Measured 2026-09-15: writing this feature put a literal NUL byte into the file,
    where a space was meant, in `const INSTALLING = " ollama"`. It was invisible in every
    editor and `grep` reported the whole template as binary. CLAUDE.md warns about exactly
    this — "`\\b` has been written into source as a literal backspace byte more than once,
    silently breaking a regex while tests still passed" — so now something checks."""
    from django.conf import settings

    for name in ("home.html", "table.html", "manual.html"):
        raw = Path(settings.BASE_DIR, "play", "templates", "play", name).read_bytes()
        for bad in (b"\x00", b"\x08", b"\x1b", b"\x07"):
            assert bad not in raw, f"{name} carries a literal {bad!r}"
        raw.decode("utf-8")        # and it is still text


@pytest.fixture
def rf():
    from django.test import RequestFactory

    return RequestFactory()
