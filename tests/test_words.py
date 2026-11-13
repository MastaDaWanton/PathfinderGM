"""rules/words.py, the one copy of the article and the plural.

Measured 2026-11-13 on the road picker (`ontheway.road`, 1,500 seeds): the tells read "an
unicorn" and "three astomois". Twenty-eight copies of a first-letter article rule lived
across rules/, gm/ and play/; this pins the sound-based rule and that no copy came back.
"""
from __future__ import annotations

import re
from pathlib import Path

from rules import words


def test_the_article_goes_by_the_sound():
    assert words.a("unicorn") == "a unicorn"
    assert words.a("one-eyed giant") == "a one-eyed giant"
    assert words.a("hour") == "an hour"
    assert words.a("owl") == "an owl"
    assert words.a("urchin") == "an urchin"
    assert words.a("hawk") == "a hawk"


def test_a_plural_name_stays_plural():
    assert words.plural("astomoi") == "astomoi"
    assert words.plural("lizardfolk") == "lizardfolk"
    assert words.plural("wolf") == "wolves"
    assert words.plural("harpy") == "harpies"
    assert words.plural("watchman") == "watchmen"
    assert words.plural("human") == "humans"
    assert words.plural("giant ant") == "giant ants"


def test_no_first_letter_copy_is_left():
    root = Path(__file__).resolve().parent.parent
    pat = re.compile(r"""["']an ?["'] if .{1,40}\[:1\].{0,12} in ["']aeiou["']""")
    left = [f"{p.relative_to(root)}:{i}"
            for d in ("rules", "gm", "play") for p in (root / d).rglob("*.py")
            if p.name != "words.py"
            for i, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1)
            if pat.search(line)]
    assert not left, left
