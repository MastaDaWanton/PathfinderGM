"""The herbalism bench's page, held to its plan (docs/herbalism-ui-plan.md) by static checks.

The bench is a layer over the play table (play/templates/play/table.html `#bench`), drawn by
play/static/js/table/30, 31, 34, 35 and 36, styled by play/static/css/bench.css, with icons
from play/static/js/bench-icons.js. These tests read those files and the served pages; the
flow itself was driven in the running app on a scratch data dir (the lane's hand-back has
the screenshots and the contrast numbers).
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest
from django.contrib.staticfiles import finders
from django.test import Client

ROOT = Path(__file__).resolve().parent.parent
TABLE = ROOT / "play" / "templates" / "play" / "table.html"
CRAFT = ROOT / "play" / "templates" / "play" / "craft.html"
STATIC = ROOT / "play" / "static"
BENCH_JS = [STATIC / "js" / "table" / f for f in (
    "30-bench-shell.js", "31-bench-satchel.js", "34-bench-tag.js", "35-bench-herbarium.js",
    "36-bench-perks.js")] + [STATIC / "js" / "bench-icons.js"]
BENCH_CSS = STATIC / "css" / "bench.css"

# The files other lanes own, which the table names only once they exist (contracts §1,
# "Script tags"; §5, every provider optional).
GUARDED = ["css/bench-games.css", "js/prefs.js", "js/sound.js",
           "js/table/32-bench-stage.js", "js/table/33-bench-games.js"] + [
    f"js/bench-games/{m}.js" for m in ("grind", "mix", "brew", "dry", "reduce", "extract",
                                         "infuse", "steep", "neutralize")]


@pytest.fixture(scope="module")
def table_html():
    return Client().get("/play/").content.decode("utf-8")


def _src(path: Path) -> str:
    return path.read_text(encoding="utf-8")


# --- the layer ----------------------------------------------------------------------------

def test_the_table_serves_the_bench_layer_and_both_ways_in(table_html):
    """The bench opens over the table (UI plan §4.1): one dialog in the page from load, so
    closing it is instant and keeps your place. It is reached from the left column's
    Herbalism button and from the Craft action panel's "Work at the bench", while
    "Crafting bench" stays the way to the old page for the other four crafts. A layer that
    is only built by script would leave the opener's `aria-controls` pointing at nothing."""
    bench = re.search(r'<div id="bench"[^>]*>', table_html)
    assert bench, "the table has no #bench layer"
    tag = bench.group(0)
    assert 'role="dialog"' in tag and 'aria-modal="true"' in tag and "hidden" in tag
    assert 'aria-labelledby="bench-title"' in tag
    for part in ('id="bench-methods"', 'id="bench-satchel"', 'id="bench-stage"', 'id="bench-roll"',
                 'id="bench-game"', 'id="bench-tagcol"', 'id="bench-foot-in"', 'id="bench-pops"',
                 'id="bench-say"'):
        assert part in table_html, part
    assert re.search(r'id="open-bench"[^>]*data-bench-open', table_html), "no Herbalism button"
    assert ">Herbalism</button>" in table_html
    assert 'href="/craft/">Crafting bench</a>' in table_html, "the old bench's door is gone"
    panel = table_html[table_html.index('id="craftpanel"'):]
    panel = panel[:panel.index("</section>")]
    assert "data-bench-open" in panel and "Work at the bench" in panel


def test_the_bench_scripts_load_in_the_contracted_order(table_html):
    """Contracts §1, "Script tags": bench-icons.js, then 30 to 36 in number order, all after
    22-roll-verdict.js (the bench throws the d20 through 22's `showVerdict`), and bench.css
    after the page's own styles so its rules win where a name meets one of the table's
    global ones. Loaded out of order, 30 would find no `BenchIcons` and draw blank tools."""
    order = ["js/table/22-roll-verdict.js", "js/bench-icons.js", "js/table/30-bench-shell.js",
             "js/table/31-bench-satchel.js", "js/table/34-bench-tag.js",
             "js/table/35-bench-herbarium.js", "js/table/36-bench-perks.js"]
    at = [table_html.index(f"/static/{p}?v=") for p in order]
    assert at == sorted(at), "the bench's scripts are out of order"
    assert table_html.index("/static/css/bench.css?v=") > table_html.index("</style>")


def test_another_lanes_file_is_named_only_once_it_exists(table_html):
    """The stage, the games and sound are other lanes' files and optional providers
    (contracts §5). A tag for a file not in the build is a 404 in the console on every load
    and fails test_template_scripts ("every file a page loads is served"), so each is
    emitted only when the asset tag found it: present in the page exactly when the file is
    in play/static."""
    for path in GUARDED:
        exists = bool(finders.find(path))
        named = f"/static/{path}?v=" in table_html
        assert named == exists, f"{path}: on disk {exists}, in the page {named}"
        assert f'"/static/{path}"' not in table_html, f"{path} named without its stamp"


def test_the_icon_registry_and_the_table_agree_on_the_names():
    """bench-icons.js draws a name as art only when the table's BENCH_ICON_URLS stamps it,
    so a name in one list and not the other is an icon that never appears (or a mask over
    a file nobody checked). The 46 names are the lead's (ui/table-v2 b4ea7cf)."""
    js = _src(STATIC / "js" / "bench-icons.js")
    block = js[js.index("var NAMES = ["):js.index("];", js.index("var NAMES = ["))]
    names = set(re.findall(r'"([a-z-]+)"', block))
    html = _src(TABLE)
    urls = html[html.index("window.BENCH_ICON_URLS = {"):]
    urls = urls[:urls.index("};")]
    keys = set(re.findall(r"([a-z]+): \"\{% asset 'img/icons/([a-z]+)\.svg' %\}\"", urls))
    assert all(k == f for k, f in keys), keys
    assert names == {k for k, _ in keys}
    assert len(names) == 46


def test_no_icon_is_hand_drawn():
    """The skill's icon rule (design-taste-frontend §3.C, UI plan §3): no hand-rolled SVG
    paths. Until the art arrived the registry drew a lettered roundel, and it still does
    for an unknown name; a drawn path here would be the placeholder that ships."""
    js = _src(STATIC / "js" / "bench-icons.js")
    for banned in ("<path", "<svg", "createElementNS", " d=\"M", "d='M"):
        assert banned not in js, banned


# --- the copy -----------------------------------------------------------------------------

def _templates_bench_parts() -> list[tuple[str, str]]:
    html = _src(TABLE)
    layer = html[html.index('<div id="bench"'):html.index('<div id="veil">')]
    craft = _src(CRAFT)
    card = craft[craft.index("function renderHerbalismMoved()"):craft.index("function renderLocked()")]
    opener = html[html.index("<!-- Herbalism opens over the table"):html.index("Crafting bench</a>")]
    panel = html[html.index("<!-- The herbalism bench, over the table"):html.index("Open the full bench")]
    return [("table.html #bench", layer), ("craft.html herbalism card", card),
            ("table.html opener", opener), ("table.html craft panel", panel)]


def test_no_new_bench_string_carries_an_em_or_en_dash():
    """UI plan §8 and the skill's §9.G: zero em-dashes and en-dashes on the bench. Checked
    over the whole of every bench file, comments included, rather than over string
    literals only: a parser for "what the player sees" would miss the template literal
    built from three pieces, and a stricter rule costs nothing here."""
    sources = [(p.name, _src(p)) for p in BENCH_JS + [BENCH_CSS]] + _templates_bench_parts()
    found = [(name, ch) for name, text in sources for ch in ("—", "–") if ch in text]
    assert not found, found


def test_the_one_label_per_intent_copy_is_the_plans():
    """UI plan §8's labels, each spelled once: Roll Craft, Taste it / Keep it, Study, Save
    recipe / Load, Close, Forage here, Next: <method>. A second wording of the same intent
    ("Craft", "Begin") is the duplicate-CTA tell the plan's pre-flight forbids."""
    js = "\n".join(_src(p) for p in BENCH_JS)
    html = _src(TABLE)
    assert ">Roll Craft</button>" in html
    for label in ('"Taste it"', '"Keep it"', ">Study<", ">Save recipe<", ">Load<", ">Forage here<", "Next: "):
        assert label in js, label
    assert ">Close</button>" in html[html.index('<div id="bench"'):]


def test_craft_page_herbalism_is_one_card_with_a_way_to_the_table():
    """UI plan §4.1: the old page's Herbalism tab becomes a single card, "Herbalism is at
    the table now", whose button returns to the table with the bench open (`/play/#bench`,
    which 30-bench-shell.js opens on load). The other four crafts keep the old bench, so
    the card is drawn only for herbalism and nothing else about selectCraft changes."""
    craft = _src(CRAFT)
    assert "Herbalism is at the table now" in craft
    assert 'href="/play/#bench">Open the herbalism bench</a>' in craft
    sel = craft[craft.index("async function selectCraft("):craft.index("function renderHerbalismMoved()")]
    assert 'if (CRAFT === "herbalism") { renderHerbalismMoved(); return; }' in sel
    shell = _src(STATIC / "js" / "table" / "30-bench-shell.js")
    assert 'location.hash === "#bench"' in shell
    assert Client().get("/craft/").status_code == 200


# --- layers and motion --------------------------------------------------------------------

def test_every_z_index_in_bench_css_is_a_documented_layer():
    """UI plan §3's layers, slotted into the table's scale: veil 20, popovers 30, BENCH 35,
    deathveil 40, dice mat 60, verdict 65/66. The bench may use 35 (the layer), 66 (the
    product's flight, at the verdict word's height) and 1 to 9 inside its own stacking
    context. A bench at 41 would cover the deathveil, and tasting hemlock could kill you
    behind your own satchel; one at 61 would hide the Craft roll's die."""
    css = _src(BENCH_CSS)
    values = [int(v) for v in re.findall(r"z-index:\s*(-?\d+)", css)]
    assert 35 in values
    bad = [v for v in values if v not in (35, 66) and not 1 <= v <= 9]
    assert not bad, bad
    layer = re.search(r"\.bench \{[^}]*\}", css, re.S).group(0)
    assert "z-index: 35" in layer


def test_a_hidden_bench_layer_is_never_laid_out_over_the_table():
    """0.2.13 shipped an invisible sheet over the whole table that took every click. The
    harvest layer (59-harvest.js) is built hidden at page load, and its injected
    `#harvest.bench{display:grid}` outranked `.bench[hidden]{display:none}` (an id and a class
    beat a class and an attribute), so the "hidden" layer stayed laid out: fixed, inset 0,
    z 35, opacity 0, and no pointer-events rule. Found driving the table in a 601x717 pane,
    where Say and every button under the layer did nothing.

    Hidden must beat any layer's own display rule, which only `!important` guarantees."""
    css = _src(BENCH_CSS)
    rule = re.search(r"\.bench\[hidden\]\s*\{([^}]*)\}", css)
    assert rule, "bench.css has no .bench[hidden] rule"
    assert re.search(r"display:\s*none\s*!important", rule.group(1)), rule.group(0)
    # And every layer the table's scripts build in the page is built hidden, so the rule
    # above is what keeps it off the table until it opens.
    js = _src(STATIC / "js" / "table" / "59-harvest.js")
    assert "layer.hidden = true" in js


def test_nothing_runs_a_loop_while_the_bench_is_idle():
    """UI plan §10 and §13.6: an idle bench draws zero frames. The browser-side measure is
    a frame counter, which needs a live page; this is the static half. No bench file calls
    setInterval or requestAnimationFrame at all: the chrome moves by CSS transitions that
    end, the product's flight is one Web Animations run that ends, and the flourishes are
    22-roll-verdict.js's, whose loop stops itself when its last spark is gone. The stage's
    own on-demand rendering is Lane F's (contracts §5.1). A setInterval here would be the
    first thing on the bench to cost the owner's GPU while they read."""
    for path in BENCH_JS:
        calls = re.findall(r"\b(setInterval|requestAnimationFrame)\s*\(", _src(path))
        assert not calls, f"{path.name} calls {calls}"
    css = _src(BENCH_CSS)
    assert "infinite" not in css, "a CSS animation in bench.css loops"


def test_motion_is_transform_and_opacity_and_reduced_motion_is_honoured():
    """UI plan §10: chrome animates transform and opacity only, at most 200ms, and both
    reduced motion (the OS) and Short flourishes (`.bench-still`, set from PGMPrefs) take
    every transition and animation away. A transition on `width` or `top` is a layout per
    frame, the jank the skill's §6.A bans."""
    css = _src(BENCH_CSS)
    for decl in re.findall(r"transition:\s*([^;]+);", css):
        if decl.strip() in ("none", "none !important"):
            continue
        for part in decl.split(","):
            prop = part.split()[0]
            assert prop in ("opacity", "transform"), decl
            ms = re.search(r"(\.\d+|\d+(?:\.\d+)?)s", part)
            assert ms and float(ms.group(1)) <= 0.22, decl
    for frames in re.findall(r"@keyframes [\w-]+ \{(.*?)\}\s*(?=@|\.|\n)", css, re.S):
        for prop in re.findall(r"([a-z-]+):", frames):
            assert prop in ("opacity", "transform"), prop
    assert "@media (prefers-reduced-motion: reduce)" in css
    assert ".bench.bench-still" in css
    # The preferences and providers moved into 29-bench-core.js with the core split
    # (lane U1, 2026-10-03), which the herb shell runs on: both files are the shell now.
    shell = _src(STATIC / "js" / "table" / "29-bench-core.js") + _src(STATIC / "js" / "table" / "30-bench-shell.js")
    assert 'PGMPrefs.get("flourishes") === "short"' in shell
    assert "prefers-reduced-motion: reduce" in shell


# --- the providers and the fakes ------------------------------------------------------------

def test_the_bench_runs_with_no_stage_no_games_and_no_sound():
    """Contracts §5: every consumer must work when a provider is missing, so each lane can
    be verified alone. Each provider is looked up where it is used and guarded there; the
    stage falls back to the tool's icon at 160px (UI plan §6.3), the games to a middling
    score so a reserved craft is never stranded, and sound and prefs to nothing and to the
    page's own `pgm.steady` key."""
    # The preferences and providers moved into 29-bench-core.js with the core split
    # (lane U1, 2026-10-03), which the herb shell runs on: both files are the shell now.
    shell = _src(STATIC / "js" / "table" / "29-bench-core.js") + _src(STATIC / "js" / "table" / "30-bench-shell.js")
    assert "window.BenchStage" in shell and "s.available()" in shell
    assert 'BenchIcons.el(m, { size: 160 })' in shell
    assert "games && typeof games.play === \"function\"" in shell
    assert "score: 0.5" in shell and "Finish (no minigame yet)" not in shell
    assert 'window.localStorage.getItem("pgm.steady")' in shell
    assert "window.Sound && typeof Sound.play" in shell


def test_the_fake_and_the_dev_fallback_did_not_ship():
    """The `?benchfake=` canned API and the "Finish (no minigame yet)" button existed only
    while lanes B2, C and E were built in parallel, each marked `// MERGE:` so the lead
    could find them in one search. They were removed at the merge (2026-10-02); a stand-in
    that ships is a second, fake answer to every bench call hidden behind a query flag."""
    shell = _src(STATIC / "js" / "table" / "30-bench-shell.js")
    assert "MERGE" not in shell and "benchfake" not in shell and "devFinish" not in shell
