"""What each skill does in this game: the words behind the skill hover, held to the code.

The owner, 2026-10-06: "in the character creator you should be able to hover on the skills
when choosing skill ranks to see what the skill affects in game." Before this the forge
listed 35 bare skill names and the level-up picker the same 35, with nothing on either to
say what a rank bought.

The danger in writing that down is the one this project keeps measuring: text that says
more than the code does. A hover reading "Appraise sets the price you pay" would be a
promise — this game's prices never read Appraise — and nothing would ever notice. So
every use in content/rules/skills-explained.json names the file that makes it and a
literal piece of that file, and these tests read each one back: delete the code and the
sentence fails here instead of lying on the page. Measured when it was written (2026-10-06, a
grep of rules/, gm/, play/ and content/ for every skill id): 20 of the 35 skills have
something the engine or the GM does with them by name; the other 15 (Appraise, Fly,
Handle Animal, seven of the ten Knowledges, Linguistics, Perform, Ride, Sense Motive, Use
Magic Device) reach play only through the GM's ordinary check, and their cards say so.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from rules import skillhelp
from rules.tables import SKILLS

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "content" / "rules" / "skills-explained.json"


def _doc() -> dict:
    return json.loads(DATA.read_text(encoding="utf-8"))


def test_every_skill_has_an_entry_and_nothing_else_does():
    """One entry per skill the engine knows (rules/tables.py SKILLS), named by its id. A
    skill added to the table without words would hover blank in the forge; an entry for
    a skill that does not exist is help for nothing."""
    got = set(_doc()["skills"])
    assert got == set(SKILLS), (
        f"missing: {sorted(set(SKILLS) - got)}; not skills: {sorted(got - set(SKILLS))}")


@pytest.mark.parametrize("sid", sorted(SKILLS))
def test_each_entry_says_what_the_book_says_and_what_this_game_does(sid):
    e = _doc()["skills"][sid]
    assert str(e.get("name") or "").strip(), f"{sid}: no display name"
    book = str(e.get("book") or "").strip()
    assert book, f"{sid}: no book line"
    # One line, read in a hover: the full CRB entry is the book's job.
    assert len(book) <= 220, f"{sid}: book line is {len(book)} chars; one line is the point"
    uses = e.get("uses") or []
    # A skill nothing reads by name says so in not_yet; it never has an empty card.
    assert uses or str(e.get("not_yet") or "").strip(), (
        f"{sid}: no uses and no not_yet — the card would say nothing at all")
    for u in uses:
        assert str(u.get("text") or "").strip(), f"{sid}: a use with no words"
        assert len(u["text"]) <= 240, f"{sid}: use is {len(u['text'])} chars: {u['text'][:60]}…"


@pytest.mark.parametrize("sid", sorted(SKILLS))
def test_every_claimed_use_is_still_in_the_code(sid):
    """The anchor test. Each use names a file and a literal string from it; the string
    must still be there. When this fails, the code that made the claim true has moved or
    gone: find where the use lives now and re-anchor it, or take the sentence out."""
    for u in _doc()["skills"][sid].get("uses") or []:
        where = ROOT / u["file"]
        assert where.is_file(), f"{sid}: {u['file']} does not exist ({u['text'][:50]}…)"
        text = where.read_text(encoding="utf-8")
        assert u["find"] in text, (
            f"{sid}: {u['file']} no longer contains {u['find']!r}, which backs "
            f"\"{u['text']}\"")


def test_the_page_is_never_shown_a_file_or_an_anchor():
    """Refs drive the checks; the player never sees them (the 2026-09-28 ruling). The
    payload the forge and the sheet draw carries words only."""
    page = skillhelp.for_page()
    blob = json.dumps(page)
    assert '"find"' not in blob and '"file"' not in blob
    assert not re.search(r"\b(?:rules|gm|play)/\w+\.py\b", blob), "a file path reached the page"
    assert set(page["skills"]) == set(SKILLS)
    assert page["general"], "the one sentence true of every skill is missing"


def test_the_card_carries_trained_only_and_the_ability_from_the_skill_table():
    """The first cut's shared line read "a skill marked trained only cannot be tried",
    and the live check found the forge's list marks nothing of the kind: the card was
    pointing at a mark that was not on the page. Each card now says it itself, read off
    rules/tables.py so it cannot disagree with the engine that refuses the roll."""
    page = skillhelp.for_page()
    for sid, (ability, trained, _acp) in SKILLS.items():
        card = page["skills"][sid]
        assert card["trained_only"] is trained, sid
        assert card["ability"] == ability.upper(), sid
    assert "marked trained only" not in page["general"]


def test_the_words_say_this_game_not_the_book_where_they_differ():
    """Craft and Profession were the owner's other question that day ("pretty useless"):
    whatever their cards say must be what the code does, and where the book's main use
    is missing here the card says it is not in play yet rather than leaving it to be
    assumed."""
    doc = _doc()["skills"]
    for sid in ("craft", "profession"):
        assert str(doc[sid].get("not_yet") or "").strip(), f"{sid}: say what is not in play"


def test_the_forge_and_the_sheet_are_sent_the_words():
    """Both doors the owner named: the creator (`creation.options`) and the level-up
    picker on the Class tab (`full_sheet`, read by 05-sheet.js lvSkillsBlock)."""
    from rules import creation

    assert set(creation.options()["skill_help"]["skills"]) == set(SKILLS)
    src = (ROOT / "rules" / "sheet.py").read_text(encoding="utf-8")
    assert '"skill_help": skill_help' in src


def test_both_pages_load_the_card_and_draw_rows_for_it():
    """The forge (home.html) and the table (table.html) both load js/skillhelp.js and
    css/skillhelp.css, and both skill lists mark their rows — a page that loads the card
    but draws bare rows shows nothing, with no error anywhere."""
    play = ROOT / "play"
    home = (play / "templates" / "play" / "home.html").read_text(encoding="utf-8")
    table = (play / "templates" / "play" / "table.html").read_text(encoding="utf-8")
    sheet = (play / "static" / "js" / "table" / "05-sheet.js").read_text(encoding="utf-8")
    for page in (home, table):
        assert "js/skillhelp.js" in page and "css/skillhelp.css" in page
    assert "SkillHelp.row(s," in home
    assert "data-skillhelp=" in sheet and "SkillHelp.info(k.name)" in sheet
    js = (play / "static" / "js" / "skillhelp.js").read_text(encoding="utf-8")
    # Not hover-only (WCAG 2.1 SC 1.4.13; Pickering, Inclusive Components): focus and a
    # tap open it too, Escape closes it, and a screen reader is given the words.
    for need in ('"focusin"', '"click"', '"Escape"', "aria-describedby"):
        assert need in js, f"skillhelp.js lost {need}"


def test_the_card_opens_from_the_question_mark_and_never_from_the_row():
    """The owner, 2026-10-08, an emergency: the card opened on hovering anywhere on a skill
    row (and on focusing its checkbox or +/-), covered the next rows, and made skills
    "impossible to select". Every opening listener now resolves its row through the "?"
    (`[data-skillinfo]`); none looks for the row directly."""
    js = (ROOT / "play" / "static" / "js" / "skillhelp.js").read_text(encoding="utf-8")
    for event in ("mouseover", "mouseout", "focusin", "focusout"):
        start = js.index(f'document.addEventListener("{event}"')
        body = js[start:js.index("});", start)]
        assert "infoRow(ev.target)" in body, event
        assert 'closest("[data-skillhelp]")' not in body, event
    assert 'tabindex="-1" data-skillinfo' not in js
