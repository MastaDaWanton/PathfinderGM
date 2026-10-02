"""The pages' JavaScript must actually parse.

Measured, not theorised: the crafting page and the play page were both shipped dead for
the length of one work session. A patch written through a shell heredoc turned `\\n`
inside a JS string literal into a real newline — three times, in three different files —
and a string broken across two lines is a syntax error that kills the entire script
block. Every function became undefined, so the crafting page rendered as an empty
leather rectangle with no tabs, no shelf and no error in the console, because the code
that would have reported an error had not parsed either.

The whole suite was green throughout. It tests Python, and the Django view still
returned 200 with the broken script inside it; `test_page_wiring` checks that the served
HTML *contains* the endpoints its buttons call, and it did — inside a script that could
not run. That is the gap this file closes: the served page's script is extracted and
handed to a real JavaScript parser.

`node --check` is used when node is on the machine and the test skips when it is not.
Skipping is honest here — the check is a guard against a specific authoring accident,
and a developer without node is not the one who introduced it.
"""
from __future__ import annotations

import re
import shutil
import subprocess

import pytest
from django.test import Client

PAGES = ["/play/", "/craft/", "/"]

# Django's own tags are not JavaScript. Replaced with a literal so the parser sees the
# shape of the code rather than the template that produced it.
_VAR = re.compile(r"\{\{[^}]*\}\}")
_TAG = re.compile(r"\{%[^%]*%\}")
_SCRIPT = re.compile(r"<script(?![^>]*\bsrc=)[^>]*>(.*?)</script>", re.S)


def _scripts_of(html: str) -> str:
    """Every inline script in the page, as one program. Scripts with a `src` are files
    of their own and are checked as files, not as page content."""
    blocks = _SCRIPT.findall(html)
    body = "\n;\n".join(blocks)
    return _TAG.sub("", _VAR.sub("null", body))


@pytest.mark.parametrize("path", PAGES)
def test_the_served_page_is_valid_javascript(tmp_path, path):
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed; the parse check needs a JS parser")

    html = Client().get(path).content.decode("utf-8")
    source = _scripts_of(html)
    if not source.strip():
        pytest.skip(f"{path} has no inline script")

    f = tmp_path / "page.js"
    f.write_text(source, encoding="utf-8")
    done = subprocess.run([node, "--check", str(f)], capture_output=True, text=True)
    assert done.returncode == 0, f"{path} script does not parse:\n{done.stderr[:800]}"


# A node-free heuristic was tried here and removed: counting unmatched quote characters
# flagged 29 lines of ordinary prose ("server's rule", "the target's CMD") and every
# regex literal. A check that cries wolf on comments would be turned off within a week,
# and the parser above is the honest version of the same question.


# --- the script files the pages load ---------------------------------------------------
#
# The play table's script moved into six files under static/js/table/ on 2026-09-25, and a
# test that parsed only INLINE scripts would have passed over a broken file silently. Every
# local script a page loads is fetched through the client — the URL the browser uses, with
# its content stamp — and parsed on its own. Classic scripts, so `node --check` on `.js` is
# the right parser (it would wave through broken module syntax; these are not modules).

_SRC = re.compile(r"<script[^>]*\bsrc=\"(/static/[^\"]+)\"")


@pytest.mark.parametrize("path", PAGES)
def test_every_script_file_a_page_loads_is_valid_javascript(tmp_path, path):
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed; the parse check needs a JS parser")
    client = Client()
    html = client.get(path).content.decode("utf-8")
    for src in _SRC.findall(html):
        r = client.get(src)
        assert r.status_code == 200, f"{path} loads {src}, which is not served"
        body = b"".join(r.streaming_content) if getattr(r, "streaming", False) else r.content
        f = tmp_path / "file.js"
        f.write_bytes(body)
        done = subprocess.run([node, "--check", str(f)], capture_output=True, text=True)
        assert done.returncode == 0, f"{src} does not parse:\n{done.stderr[:800]}"


def test_the_table_scripts_carry_a_content_stamp_and_are_not_trusted_from_cache():
    """The Electron shell's disk cache outlives reinstalls on an origin that never changes —
    World Bible's five-day-old stylesheet. Each script URL carries a hash of its bytes, and
    the static route answers `Cache-Control: no-cache`."""
    client = Client()
    html = client.get("/play/").content.decode("utf-8")
    srcs = [s for s in _SRC.findall(html) if "/js/table/" in s]
    # Ten since the 2026-09-28 panel shell added 07-panels.js and Lane F's three stubs;
    # eleven since I6's exits row (11-exits.js); twenty-one since the table rebuild's
    # shell (12-21: the tabs, the device, the sides, the book's head, one per tab);
    # twenty-two since stage 3's Places chart (16-places-chart.js); twenty-three since the
    # roll's verdict (22-roll-verdict.js, 2026-10-01); twenty-eight and then thirty with
    # the herbalism bench (30-36, 2026-10-02, landing across three lanes). Every file in
    # the folder, so a script added there and not loaded fails here too. Pinned as "all of
    # them, and no fewer than before" rather than a literal, because the literal had to be
    # edited by whoever added a file and the equality with the folder is the real claim.
    from pagesource import table_scripts
    assert len(srcs) == len(table_scripts()) >= 28, srcs
    assert all(re.search(r"\?v=[0-9a-f]{10}$", s) for s in srcs), srcs
    r = client.get(srcs[0])
    assert r["Cache-Control"] == "no-cache"
    assert r["Content-Type"].startswith("text/javascript")


def test_an_edit_is_a_new_stamp(tmp_path, monkeypatch):
    from play.templatetags import assets

    f = tmp_path / "x.js"
    f.write_text("let a = 1;", encoding="utf-8")
    monkeypatch.setattr(assets.finders, "find", lambda p: str(f))
    before = assets.stamp("js/x.js")
    f.write_text("let a = 22;", encoding="utf-8")
    assert assets.stamp("js/x.js") != before
