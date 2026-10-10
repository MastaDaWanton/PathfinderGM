"""A layer the page hides with the `hidden` attribute stays out of the way of the mouse.

Found live on 0.2.13 (master ec1b4281, 2026-10-09): on /play/ every real click on the table (Say,
the beats, the desk) landed on nothing. `document.elementFromPoint` over the Say button answered
`<div id="harvest" class="bench harvest" hidden>`: display grid, opacity 0, position fixed,
z-index 35, pointer-events auto. 59-harvest.js injects `#harvest.bench{display:grid;...}` at load,
and that id-plus-class rule (1,1,0) outranks bench.css's `.bench[hidden]{display:none}` (0,2,0),
so the `hidden` attribute stopped hiding the layer. It sat invisible over the whole window and
swallowed every pointer event; `element.click()` from script still worked, which is why no test
that clicked through the DOM noticed.

bench.css now says `.bench[hidden]{display:none !important}` (tests/test_bench_ui.py
`test_a_hidden_bench_layer_is_never_laid_out_over_the_table`), which closes it for every bench
layer. The shape is wider than the bench, though: a stylesheet that says
`.X[hidden]{display:none}` is promising that hiding an `.X` works, and any rule on `.X` that sets
`display` at the same or a higher specificity quietly breaks the promise. bench.css alone has
five such promises (.bench, .bench-chips, .tag-batch, .bench-card, .bench-modal) plus
`#bench-game[hidden]`. These checks read every stylesheet the play page can load — the CSS
files, the templates' `<style>` blocks, and the sheets the scripts inject as string literals —
and refuse such a rule unless the promise is `!important` or the rule carries its own
`[hidden]` partner.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
PLAY = ROOT / "play"
STATIC = PLAY / "static"


def _js_code(js: str) -> str:
    """A script without its comments, so CSS quoted in a comment is not read as a rule."""
    js = re.sub(r"/\*.*?\*/", "", js, flags=re.S)
    return "\n".join(ln if "://" in ln else ln.split("//", 1)[0] for ln in js.splitlines())


def _js_css(js: str) -> str:
    """Every string and template literal of a script, each closed with a `;`: the injected sheets
    are arrays of quoted lines (59-harvest.js, 44-forge-ledger.js) or one template literal
    (21-tab-journal.js). The `;` keeps a script's other strings ("use strict", ids, labels) out
    of the next selector, since the rule reader starts a selector after the last `;`; it is
    harmless inside a declaration block, and no injected sheet splits a selector across two
    literals (checked 2026-10-09)."""
    parts = re.findall(
        r'"((?:[^"\\\n]|\\.)*)"|\'((?:[^\'\\\n]|\\.)*)\'|`((?:[^`\\]|\\.)*)`', _js_code(js), flags=re.S)
    return ";\n".join(a or b or c for a, b, c in parts)


def _sources() -> dict[str, str]:
    out: dict[str, str] = {}
    for p in sorted(STATIC.rglob("*.css")):
        out[str(p.relative_to(ROOT))] = p.read_text(encoding="utf-8")
    for p in sorted(STATIC.rglob("*.js")):
        if ".min." in p.name:
            continue
        css = _js_css(p.read_text(encoding="utf-8"))
        if "{" in css:
            out[str(p.relative_to(ROOT))] = css
    for p in sorted((PLAY / "templates").rglob("*.html")):
        blocks = re.findall(r"<style[^>]*>(.*?)</style>", p.read_text(encoding="utf-8"), flags=re.S)
        if blocks:
            out[str(p.relative_to(ROOT))] = "\n".join(blocks)
    return out


def _rules(css: str) -> list[tuple[str, str]]:
    """(selector, declarations) for every innermost rule; an @media wrapper falls away because
    its own `{` stops the selector text, and a selector never holds a `;`, so anything before
    the last one (an @import, a script's other strings) is not part of it."""
    css = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    return [(s.rsplit(";", 1)[-1].strip(), d) for s, d in re.findall(r"([^{}]+)\{([^{}]*)\}", css)]


def _display(decls: str) -> str | None:
    m = re.findall(r"(?:^|;)\s*display\s*:\s*([^;!]+)", decls)
    return m[-1].strip() if m else None


def _important(decls: str) -> bool:
    """Whether the rule's display is `!important`, which only another `!important` can beat."""
    m = re.findall(r"(?:^|;)\s*display\s*:\s*[^;]*", decls)
    return bool(m) and "!important" in m[-1]


def _subject(selector: str) -> str:
    """The compound the rule styles: the part after the last combinator."""
    return re.split(r"\s*[>+~]\s*|\s+", selector.strip())[-1]


def _specificity(compound: str) -> tuple[int, int, int]:
    ids = len(re.findall(r"#[\w-]+", compound))
    # :not(x) counts as x; the :not itself counts nothing.
    flat = re.sub(r":not\(", "(", compound)
    classes = len(re.findall(r"\.[\w-]+|\[[^\]]*\]|:(?!:)[\w-]+", flat))
    elems = len(re.findall(r"(?:^|[\s>+~(])[a-zA-Z][\w-]*", flat))
    return ids, classes, elems


def _simple_tokens(compound: str) -> set[str]:
    return set(re.findall(r"[#.][\w-]+", compound))


def _all_rules() -> list[tuple[str, str, str]]:
    out = []
    for name, css in _sources().items():
        for sel, decls in _rules(css):
            for part in sel.split(","):
                part = part.strip()
                if part and not part.startswith("@"):
                    out.append((name, part, decls))
    return out


def test_the_rule_reader_finds_the_sheets_it_must_read():
    """A checker that read nothing would pass forever. bench.css's promise and the harvest
    sheet's injected grid rule are the two halves of the 0.2.13 defect, so both have to be
    in what it reads."""
    rules = _all_rules()
    assert any(s == ".bench[hidden]" and _display(d) == "none" for _, s, d in rules)
    assert any(n.endswith("59-harvest.js") and s == "#harvest.bench" and _display(d) == "grid"
               for n, s, d in rules)
    assert any(n.endswith("21-tab-journal.js") for n, _, _ in rules), "template literal sheets"


def _broken(rules: list[tuple[str, str, str]]) -> list[str]:
    """Every display rule that beats a `[hidden]{display:none}` promise made for its subject."""
    promises = []        # (tokens, specificity, important) of every `X[hidden]{display:none}`
    hidden_none = set()  # subjects, without [hidden], that are put away when hidden
    for _, sel, decls in rules:
        subj = _subject(sel)
        if "[hidden]" in subj and ":not([hidden])" not in subj and _display(decls) == "none":
            base = subj.replace("[hidden]", "")
            hidden_none.add(base)
            if sel == subj:
                promises.append((_simple_tokens(base), _specificity(subj), _important(decls)))
    assert promises, "no [hidden] promises found: the reader is broken"

    broken = []
    for name, sel, decls in rules:
        shown = _display(decls)
        subj = _subject(sel)
        if shown in (None, "none") or "[hidden]" in subj or subj in hidden_none:
            continue
        toks = _simple_tokens(subj)
        for ptoks, pspec, pimp in promises:
            if not ptoks or not ptoks <= toks:
                continue
            outranks = _important(decls) if pimp else _specificity(subj) >= pspec
            if outranks:
                broken.append(f"{name}: `{sel}{{display:{shown}}}` outranks "
                              f"`{''.join(sorted(ptoks))}[hidden]{{display:none}}`; "
                              f"add `{subj}[hidden]{{display:none}}`")
                break
    return broken


def test_no_display_rule_outranks_a_hidden_promise_without_its_own():
    """`#harvest.bench{display:grid}` beat `.bench[hidden]{display:none}` and left the closed
    harvest sheet over the whole table at opacity 0, taking every real click (0.2.13). For each
    `X[hidden]{display:none}` any stylesheet makes, a rule whose subject includes X and sets a
    display at the same or higher specificity must be beaten anyway: the promise is
    `!important` (and the rule is not), or the rule has a `<that subject>[hidden]{display:none}`
    partner, or it is scoped `:not([hidden])` itself."""
    broken = _broken(_all_rules())
    assert not broken, "\n".join(broken)


def test_the_check_refuses_the_rule_pair_0_2_13_shipped():
    """The live sheets pass now that bench.css's promise is `!important`, so this keeps the
    check itself honest: on 0.2.13's own pair it must refuse, and each of the three ways out
    (an `!important` promise, a `[hidden]` partner, a `:not([hidden])` scope) must clear it.
    Before the bench.css fix, the check above failed on the real tree with exactly this
    message: "59-harvest.js: `#harvest.bench{display:grid}` outranks
    `.bench[hidden]{display:none}`"."""
    promise = ("bench.css", ".bench[hidden]", "display: none")
    shown = ("59-harvest.js", "#harvest.bench", "display:grid;place-items:center")
    assert _broken([promise, shown]) and "#harvest.bench" in _broken([promise, shown])[0]
    assert not _broken([("bench.css", ".bench[hidden]", "display: none !important"), shown])
    assert not _broken([promise, shown, ("59-harvest.js", "#harvest.bench[hidden]", "display:none")])
    assert not _broken([promise, ("59-harvest.js", "#harvest.bench:not([hidden])", "display:grid")])
    # bench.css's own `.bench{display:grid}` (0,1,0) never beat the promise in the first place.
    assert not _broken([promise, ("bench.css", ".bench", "display: grid")])


@pytest.mark.parametrize("compound, expect", [
    (".bench[hidden]", (0, 2, 0)),
    ("#harvest.bench", (1, 1, 0)),
    ("#harvest.bench:not([hidden])", (1, 2, 0)),
    ("div.bench", (0, 1, 1)),
])
def test_specificity_is_counted_the_way_the_cascade_counts_it(compound, expect):
    """The whole check rests on this count; `#harvest.bench` (1,1,0) beating `.bench[hidden]`
    (0,2,0) is the defect itself."""
    assert _specificity(compound) == expect
