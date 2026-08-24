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
