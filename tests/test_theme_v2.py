"""The shared theme (`play/static/css/theme-v2.css`) and its textures (`play/static/img/v2`).

Each test names the failure it stands against.

The one that is easiest to reintroduce: a relative url() kept in an ordinary custom
property is resolved against the stylesheet that READS the `var()`, not the one that
defines it. Measured 2026-09-30 in Chrome 154 and in Electron 33.4.11 (Chromium 130, the
packaged app's engine), with a sheet at /css/s.css defining `--u: url("x.png")`: a rule in
that sheet fetched /css/x.png, the page's inline <style> reading the same `var(--u)`
fetched /page/x.png, a 404. Registered with `@property { syntax: "<url>" }` the token
computed to /css/... from both. `syntax: "<image>"` did not help: it resolved against the
reader in both engines. The pages that use the theme style elements their scripts build
from inline styles, so an unregistered image token is a texture that silently fails to
load on every one of them.
"""
from __future__ import annotations

import re
from pathlib import Path

from django.conf import settings

ROOT = Path(settings.BASE_DIR)
STATIC = ROOT / "play" / "static"
THEME = STATIC / "css" / "theme-v2.css"
V2 = STATIC / "img" / "v2"
MOCK = ROOT / "docs" / "mock" / "table-layout"
MOCK_TEXTURES = MOCK / "textures"


def _css() -> str:
    return THEME.read_text(encoding="utf-8")


def _uncommented(css: str) -> str:
    return re.sub(r"/\*.*?\*/", "", css, flags=re.S)


def test_every_image_token_is_registered_as_a_url():
    """The 404 in the module docstring: every custom property whose value is a url() must
    be registered with `syntax: "<url>"`, or a page reading it inline fetches the image
    relative to itself."""
    css = _uncommented(_css())
    tokens = set(re.findall(r"(--[\w-]+)\s*:\s*url\(", css))
    assert len(tokens) >= 15, f"found only {sorted(tokens)}: the pattern has gone stale"
    registered = set(re.findall(r'@property\s+(--[\w-]+)\s*\{[^}]*syntax:\s*"<url>"', css))
    unregistered = sorted(tokens - registered)
    assert not unregistered, (
        f"{unregistered} hold a url() but are not `@property ... syntax: \"<url>\"`: "
        "a page reading them from its own <style> would resolve the path against itself")


def test_every_url_in_the_theme_is_a_file_that_ships():
    """Relative to the stylesheet, as the browser resolves it, under play/static (which
    the spec ships whole, so a file here is a file in the executable). A missing texture
    does not error: the element just paints its fallback colour."""
    css = _uncommented(_css())
    urls = [u for u in re.findall(r'url\("([^"]+)"\)', css) if not u.startswith("data:")]
    assert len(urls) >= 17, f"found only {urls}: the pattern has gone stale"
    missing = sorted(u for u in urls if not (THEME.parent / u).resolve().is_file())
    assert not missing, f"theme-v2.css points at files that are not there: {missing}"


def test_linking_the_theme_changes_nothing_by_itself():
    """The pages link the theme ahead of their own styles and opt in class by class. A
    single element or global selector here (`button`, `*`, `:focus-visible`) would restyle
    every page that links it, including the ones whose buttons and focus rings were never
    swapped. So: only :root, `.v2-*`, `.page-backdrop-*`, and at-rules."""
    css = _uncommented(_css())
    # Drop the at-rules that hold declarations rather than rules, and the preludes of the
    # ones that hold rules (@media), so what is left before each `{` is a selector list.
    css = re.sub(r"@(property|font-face)[^{]*\{[^}]*\}", "", css)
    css = re.sub(r"@media[^{]*\{", "", css)
    bad = []
    selectors = [s.strip() for s in re.findall(r"([^{}]+)\{", css)]
    assert len(selectors) >= 40, f"found only {len(selectors)} rules: the parse has gone stale"
    for sel in selectors:
        for part in sel.split(","):
            part = part.strip()
            if part.startswith(":root"):
                continue
            head = re.split(r"[\s>+~:\[]", part, maxsplit=1)[0]
            # a.v2-btn: an element qualified by a theme class still only matches opted-in
            # elements.
            if not re.search(r"\.(v2-|page-backdrop-)", head):
                bad.append(part)
    assert not bad, f"selectors that match without opting in: {bad}"


def test_the_textures_are_the_mocks_own_bytes():
    """The copies in play/static/img/v2 are the app's; the mock's prepare.py makes the
    originals beside itself (docs/mock/table-layout/textures/). World Bible served a stale
    derived file for five days because nothing compared content; a texture re-made in the
    mock and not copied here fails this instead of shipping the old one."""
    shipped = sorted(p for p in V2.iterdir() if p.name != "CREDITS.md")
    assert len(shipped) >= 19, f"only {len(shipped)} files in img/v2"
    drifted = [p.name for p in shipped
               if not (MOCK_TEXTURES / p.name).is_file()
               or (MOCK_TEXTURES / p.name).read_bytes() != p.read_bytes()]
    assert not drifted, f"img/v2 files that differ from docs/mock/table-layout/textures: {drifted}"
    assert (V2 / "CREDITS.md").is_file(), "the textures ship without their credits"


def test_the_stylesheet_is_served_as_css_whatever_the_registry_says():
    """Django's static view takes a file's type from `mimetypes`, which on Windows reads
    the registry, and on some machines the registry maps `.js` to `text/plain`
    (pathfindergm/urls.py). theme-v2.css is the app's first external stylesheet; answered
    as `text/plain` a standards-mode page refuses it and every material on the page falls
    back to a flat colour with no error on screen. Simulate that registry, re-import the
    URLconf, and the pin must win."""
    import importlib
    import mimetypes

    import pathfindergm.urls as urls
    from django.test import Client

    mimetypes.add_type("text/plain", ".css")
    try:
        importlib.reload(urls)
        assert mimetypes.guess_type("theme-v2.css")[0] == "text/css"
    finally:
        mimetypes.add_type("text/css", ".css")
        importlib.reload(urls)
    r = Client().get("/static/css/theme-v2.css")
    assert r.status_code == 200
    assert r["Content-Type"].startswith("text/css")
    assert r["Cache-Control"] == "no-cache"


PAGES = ["home", "craft", "classbuilder", "racebuilder", "spellbuilder", "manual", "outfit"]
# The files theme v2 replaced (img/v2/CREDITS.md, "Replaces"). grimoire-leather.jpg is not
# here: the owner kept it as every page's backdrop. leather-tile.jpg is the manual's own
# backdrop, kept for the same reason, and nowhere else.
REPLACED = ["img/card-leather.jpg", "img/clasp-", "img/boss-", "img/leather-tile.jpg"]


def test_the_themed_pages_link_it_first_and_read_no_replaced_texture():
    """Two ways the swap goes quietly wrong. Linked after a page's own <style>, the
    theme's :root re-colours the page (its --dim #93866e over the shelf's #8e816a, its
    --accent over theirs): a palette change nobody asked for. And a rule left pointing at
    an old file keeps the old leather on one surface of a page that otherwise wears the
    new: the swap looks done in every screenshot but the one view that shows that
    surface."""
    for name in PAGES:
        text = (ROOT / "play" / "templates" / "play" / f"{name}.html").read_text(encoding="utf-8")
        link = "{% asset 'css/theme-v2.css' %}"
        assert link in text, f"{name}.html does not link the theme"
        assert text.index(link) < text.index("<style>"), f"{name}.html links the theme after its own styles"
        stale = [r for r in REPLACED if r in text
                 and not (name == "manual" and r == "img/leather-tile.jpg")]
        assert not stale, f"{name}.html still reads {stale}"


def test_the_frame_geometry_is_the_approved_mocks():
    """The clasps were placed three times before they sat on the ring (mock README, "The
    clasps registered on the ring"): 24/21px left the arms 3-5px outside it. The theme's
    numbers are the mock's; a change to either without the other is a clasp off its ring
    on one surface and on it on another."""
    def tokens(text: str) -> dict[str, str]:
        line = re.search(r"--ring:[^;]+;[^\n]*--boss-in:[^;]+;", text).group(0)
        return dict(re.findall(r"(--[\w-]+):\s*([^;]+);", line))
    assert tokens(_css()) == tokens((MOCK / "mock.css").read_text(encoding="utf-8"))
