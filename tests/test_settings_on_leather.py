"""Every group of Settings options sits on the light leather card, as everything else does.

The owner, 2026-10-27: "the settings is hard to read against the background lets give the
options the same treatment we give everything else and put them on the light leather
cards." Settings was the one pane whose text sat straight on the black grimoire leather.
Measured with the text removed, against the brightest 2% of what lies under each run of
text: 19 of 99 runs fell under WCAG AA at 1366px (21 at 375px, and 21 embedded over the
table): the italic notes at 2.8-3.4:1, the field labels 3.4-3.9, the API key names 3.4-3.5,
the "optional" pill 1.7. On the cards, 0 of 99 at both widths, standalone and embedded; the
worst run 5.04:1.
"""
from __future__ import annotations

import re
from pathlib import Path

HOME = Path("play/templates/play/home.html")


def _src() -> str:
    return HOME.read_text(encoding="utf-8")


def _settings_js(src: str) -> str:
    """The Settings pane's builders: from the sound panel to the model settings' save."""
    return src[src.index("function soundPanel()"):src.index("async function saveModelSettings()")]


def test_each_group_of_options_is_a_light_leather_card():
    """Before you can play, Play on your phone, Who does which job (with the API keys and
    their Save), How the narrator writes, Sound and motion, and Report a problem: each is a
    `.card.setgroup`, and no section heading in the pane is drawn outside one."""
    src = _src()
    js = _settings_js(src) + src[src.index("function setupPanel()"):src.index("function blockedByModel(")]
    assert 'class="card setgroup"' in src[src.index("function setGroup("):src.index("function paneSettings()")]
    for title in ("Before you can play", "Play on your phone", "How the narrator writes",
                  "Sound and motion", "Report a problem"):
        assert re.search(r'setGroup\("[\w-]+", "' + title + '"', src), title
    jobs = src[src.index('<section class="card setgroup" aria-labelledby="set-jobs">'):]
    jobs = jobs[:jobs.index("</section>")]
    assert "Who does which job" in jobs and "API keys" in jobs and 'id="savemodels"' in jobs
    # Every section heading left in the builders is the one inside setGroup or the jobs card.
    own = src[src.index("function setGroup("):src.index("function paneSettings()")]
    assert js.replace(jobs, "").replace(own, "").count('<h2 class="sect"') == 0, \
        "a section heading is drawn off the cards"


def test_the_column_keeps_the_ironmongery_off_the_pane_edge_and_never_scrolls_sideways():
    """The frames' metal reaches past every card (the 34px note in `narrationPanel`;
    Settings scrolled sideways by 34px at 601px on 2026-10-10). The column keeps 34px a
    side (14px on a phone) and clips the invisible rest of the reach, measured with no
    sideways scroll at 1366px and 375px, standalone and embedded."""
    css = _src()
    col = css[css.index("  .setcol {"):css.index("}", css.index("  .setcol {"))]
    assert "overflow-x: clip" in col and "padding: 14px 34px 24px" in col
    narr = css[css.index("  .narrcards {"):css.index("}", css.index("  .narrcards {"))]
    assert "padding-inline: 34px" in narr and "overflow-x: clip" in narr
    assert ".setcol { padding-inline: 14px;" in css


def test_the_narrators_choices_and_the_controls_keep_working():
    """The narrator's two cards are still the `data-hbnarration` buttons the house-rule
    handler reads, Save is still `#savemodels`, and the switches keep their `data-pref`."""
    src = _src()
    assert 'data-hbnarration="${v}"' in src and 'closest("[data-hbnarration]")' in src
    assert 'closest("#savemodels")' in src
    for pref in ('data-pref="music.on"', 'data-pref="sound.mute"', 'data-pref="steady"',
                 'data-pref="flourishes"'):
        assert pref in src, pref


def test_optional_is_dashed_not_faded():
    """The "optional" pill was the whole pill at .5 opacity: 1.7:1 on the leather."""
    assert ".setgroup .pill.soon { opacity: 1; border-style: dashed; }" in _src()
