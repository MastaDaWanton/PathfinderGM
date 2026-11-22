"""The first-time cards: their words held to the code, the store held to the player.

The owner, 2026-11-21: "have a tutorial for each section that takes the user through
everything they need to know about a page or menu the first time they interact with it and
then a button to view those tutorials again". Design: docs/tutorials-plan.md.

The danger in writing help down is the one this project keeps measuring: text that drifts
from the thing it describes. CK3's tutorial stopped describing the game it shipped in, and
while this plan was written the Travel panel already said "DC 10, 2 more each hour, 1d6"
in its own words while rules/survival.py owned the numbers (docs/tutorials-plan.md §2). So
every rule of §3.6 is a test here: a step points at a `data-tut` some page draws, names
controls whose labels still stand beside that attribute, carries no digit that is not an
engine placeholder, cites the code behind a rules claim, links a manual anchor that exists,
stays short, and is locked to its version so changed words reach the people who read the
old ones.
"""
from __future__ import annotations

import html
import json
import re
from pathlib import Path

import pytest
from django.test import Client

from play import tutorials
from rules import tutorialfacts

ROOT = Path(__file__).resolve().parent.parent
CONTENT = ROOT / "content" / "tutorials"
LOCK = CONTENT / "versions.lock"
PAGES = [ROOT / "play" / "templates" / "play", ROOT / "play" / "static" / "js"]
CSS = ROOT / "play" / "static" / "css" / "tutorials.css"
MANUAL = ROOT / "play" / "templates" / "play" / "manual.html"

MAX_STEPS = 6     # the plan's 4, raised for the owner's D3 widening ("explain the buttons")
MAX_WORDS = 45    # a step's words (the plan's cap, unchanged)
MAX_BUTTONS = 7   # rows in one "buttons here" step
MAX_BUTTON_WORDS = 14

# Every section of docs/tutorials-plan.md §2, by the id its tutorial carries. A new tab or
# bench without a tutorial is a failing test, not a forgotten one: add its id here and a
# tutorial (or a "none" reason) for it. PENDING is the later phases' list: each lane takes
# its own ids out as it writes them, and phase 6 leaves it empty.
SECTIONS = {"table", "map.places", "map.region", "bench.herbalism",
            # phase 4, feat/tutorials-maps-fights
            "map.ground", "map.march", "map.world", "map.sea", "map.site",
            "fight.bar", "fight.order", "fight.nonlethal"}
PENDING = {
    # phase 2, feat/tutorials-home
    "home.worlds", "home.campaign", "home.import", "home.homebrew", "home.characters",
    "settings.setup", "settings.phone", "settings.jobs", "settings.narrator", "settings.sound",
    "settings.report", "home.manual",
    "create.who", "create.class", "create.abilities", "create.skills", "create.feats",
    "create.outfit", "create.builders",
    # phase 3, feat/tutorials-table
    "table.here", "table.craft", "table.left", "table.right", "table.panels", "table.gmview",
    "table.wrong", "table.dice", "table.clock", "table.talk", "table.music", "table.death",
    "tab.sheet", "tab.levelup", "tab.equipment", "tab.spells", "tab.trade", "tab.journal",
    # phase 5, feat/tutorials-benches
    "bench.forge", "bench.enchant", "bench.alchemy", "bench.leather", "bench.games",
    "bench.perks", "bench.works", "bench.harvest", "bench.craftpage",
}


def _all() -> list[dict]:
    out = []
    for p in sorted(CONTENT.glob("*.json")):
        for t in json.loads(p.read_text(encoding="utf-8")).get("tutorials") or []:
            out.append(t)
    return out


def _ids():
    return [t["id"] for t in _all()]


def _by(tid):
    return next(t for t in _all() if t["id"] == tid)


def _page_files():
    for d in PAGES:
        yield from (p for p in d.rglob("*") if p.suffix in (".html", ".js") and "vendor" not in p.parts)


_SOURCES = None


def _sources() -> dict[Path, list[str]]:
    global _SOURCES
    if _SOURCES is None:
        _SOURCES = {p: p.read_text(encoding="utf-8").splitlines() for p in _page_files()}
    return _SOURCES


def _drawn(tut: str) -> list[tuple[Path, int]]:
    """Every (file, line) where some page draws data-tut="<tut>"."""
    pat = f'data-tut="{tut}"'
    return [(p, i) for p, lines in _sources().items() for i, line in enumerate(lines) if pat in line]


def _texts(t: dict):
    for s in t["steps"]:
        yield s.get("title", "")
        yield s.get("words", "")
        for b in s.get("buttons") or []:
            yield b.get("words", "")


# --- coverage -------------------------------------------------------------------------------

def test_every_section_has_a_tutorial_or_is_pending():
    """Rule 6: every section in the plan's inventory has an entry. Phase 1 wrote four; the
    rest are named in PENDING for the lane that owns them."""
    have = set(_ids())
    assert len(have) == len(_ids()), "a tutorial id is used twice"
    assert SECTIONS <= have, f"no tutorial for {sorted(SECTIONS - have)}"
    assert not (have - SECTIONS - PENDING), f"not a section: {sorted(have - SECTIONS - PENDING)}"
    assert not (SECTIONS & PENDING), f"written and still pending: {sorted(SECTIONS & PENDING)}"


# --- the words ------------------------------------------------------------------------------

@pytest.mark.parametrize("tid", _ids())
def test_each_card_is_short(tid):
    """Rule 6: NN/g found chains of coach marks dismissed and one hint at a time works;
    CK3's 67 boxes are the cautionary tale. Raising a cap is editing this test, on purpose."""
    t = _by(tid)
    assert 1 <= len(t["steps"]) <= MAX_STEPS, f"{tid}: {len(t['steps'])} steps"
    for s in t["steps"]:
        assert s.get("title"), f"{tid}: a step with no title"
        assert s.get("words") or s.get("buttons"), f"{tid}: {s['title']} says nothing"
        n = len(s.get("words", "").split())
        assert n <= MAX_WORDS, f"{tid}: {s['title']} is {n} words; the cap is {MAX_WORDS}"
        assert len(s.get("buttons") or []) <= MAX_BUTTONS, f"{tid}: {s['title']} lists too many buttons"
        for b in s.get("buttons") or []:
            m = len(b["words"].split())
            assert m <= MAX_BUTTON_WORDS, f"{tid}: {b['label']}'s line is {m} words"


@pytest.mark.parametrize("tid", _ids())
def test_no_number_is_written_into_the_words(tid):
    """Rule 3: every number comes from the engine. The Travel panel's own line drifted from
    rules/survival.py before this was written; a digit here would be the same drift."""
    for text in _texts(_by(tid)):
        bare = re.sub(r"\{[a-z_]+\}", "", text)
        assert not re.search(r"\d", bare), f"{tid}: a digit outside a placeholder in {text!r}"
        for name in tutorialfacts.names(text):
            assert name in tutorialfacts.FACTS, f"{tid}: unknown placeholder {{{name}}}"
        tutorialfacts.fill(text)   # every placeholder resolves against the engine


def test_the_placeholders_are_the_engines_numbers():
    """The facts read the engine, not a copy: the forced march is survival's own DC."""
    from rules import hexes, journey, survival

    assert tutorialfacts.fill("{march_dc_first}") == str(survival.forced_march_dc(1))
    assert tutorialfacts.fill("{march_dc_step}") == str(survival.forced_march_dc(2) - survival.forced_march_dc(1))
    assert tutorialfacts.fill("{march_free_hours}") == str(journey.HOURS_PER_DAY)
    assert tutorialfacts.fill("{hex_hours_rough}") == str(hexes.HOURS_ROUGH)


@pytest.mark.parametrize("tid", _ids())
def test_every_anchor_is_drawn_by_some_page(tid):
    """Rule 1: anchors are data-tut attributes, which exist only for this, never ids or
    classes that change for styling reasons. A missing one is a pointer at nothing."""
    t = _by(tid)
    for name in [t["root"]] + [s["anchor"] for s in t["steps"] if s.get("anchor")]:
        assert _drawn(name), (f"tutorial {tid} points at data-tut={name}, which no template "
                              f"or script draws")


@pytest.mark.parametrize("tid", _ids())
def test_every_named_control_still_carries_its_label(tid):
    """Rule 2: a step that names a button must name it as the page labels it. The label
    has to stand within three lines of the control's data-tut, which is where a template
    or a template literal writes a button's text; "the button was renamed and the card
    still says the old name" fails here."""
    for s in _by(tid)["steps"]:
        for c in (s.get("controls") or []) + (s.get("buttons") or []):
            where = _drawn(c["tut"])
            assert where, f"{tid}: {c['label']!r} names data-tut={c['tut']}, which nothing draws"
            near = lambda p, i: html.unescape("\n".join(_sources()[p][max(0, i - 3):i + 4]))
            assert any(c["label"] in near(p, i) for p, i in where), (
                f"{tid}: data-tut={c['tut']} is no longer labelled {c['label']!r}")


@pytest.mark.parametrize("tid", _ids())
def test_every_rules_claim_is_still_in_the_code(tid):
    """Rule 4, as tests/test_skill_help.py does it: a claim names a file and a literal of
    it. A step with an engine number is a rules claim by definition and must cite."""
    for s in _by(tid)["steps"]:
        if tutorialfacts.names(s.get("words", "")):
            assert s.get("source"), f"{tid}: {s['title']} states engine numbers and cites nothing"
        src = s.get("source")
        if not src:
            continue
        f = ROOT / src["file"]
        assert f.is_file(), f"{tid}: {src['file']} does not exist"
        assert src["literal"] in f.read_text(encoding="utf-8"), (
            f"{tid}: {src['file']} no longer contains {src['literal']!r}, which backs "
            f"\"{s['title']}\"")


@pytest.mark.parametrize("tid", _ids())
def test_the_manual_link_lands(tid):
    """Rule 5: "More in the manual" opens an anchor that exists."""
    m = _by(tid).get("manual")
    assert m and f'id="{m}"' in MANUAL.read_text(encoding="utf-8"), f"{tid}: no manual anchor {m!r}"


# --- the versions lock ----------------------------------------------------------------------

def test_words_cannot_change_without_raising_the_version():
    """§3.5: a reader who saw v1 is shown what changed in v2, which only works if v moves.
    The lock keeps each tutorial's v and the hash of what a player reads."""
    lock = json.loads(LOCK.read_text(encoding="utf-8"))
    assert set(lock) == set(_ids()), "versions.lock is out of step: run tools/tutorials_lock.py"
    for t in _all():
        was = lock[t["id"]]
        h = tutorials.content_hash(t)
        if was["hash"] != h:
            assert was["v"] != t["v"], (
                f"{t['id']}: its words, anchors or controls changed and v is still {t['v']}. "
                f"Raise v, set the changed steps' since to it, then run tools/tutorials_lock.py")
            pytest.fail(f"{t['id']}: v raised; run tools/tutorials_lock.py to lock it")
        assert was["v"] == t["v"], f"{t['id']}: v moved with nothing changed; put it back"


@pytest.mark.parametrize("tid", _ids())
def test_a_raised_version_has_a_step_to_show(tid):
    """§3.5: raising v while no step's `since` matches it would show the update as nothing."""
    t = _by(tid)
    sinces = [int(s.get("since", 1)) for s in t["steps"]]
    assert max(sinces) == t["v"], f"{tid}: v is {t['v']} and no step arrived in it"
    assert all(1 <= x <= t["v"] for x in sinces), f"{tid}: a step's since is out of range"


def test_only_the_new_steps_show_after_an_update():
    """Owner decision D6: after an update, the changed steps only, once."""
    t = {"v": 3, "steps": [{"since": 1}, {"since": 3}, {"since": 2}, {"since": 3}]}
    assert tutorials.due_steps(t, None) == [0, 1, 2, 3]
    assert tutorials.due_steps(t, {"v": 1}) == [1, 2, 3]
    assert tutorials.due_steps(t, {"v": 2}) == [1, 3]
    assert tutorials.due_steps(t, {"v": 3}) == []


# --- the page never sees the refs; the CSS never covers the page ------------------------------

def test_the_page_is_never_sent_a_source_or_a_control(isolated):
    """Rule 7 and the refs-never-on-the-page ruling (2026-09-28)."""
    raw = json.dumps(tutorials.for_page())
    assert '"source"' not in raw and '"controls"' not in raw and '"literal"' not in raw
    assert "rules/" not in raw and ".py" not in raw


def test_the_card_css_lays_nothing_over_the_page():
    """0.2.13 shipped an invisible full-screen layer that took every click, and Intro.js
    has the same bug open (#2207). The card is one box in the top layer and the pointer a
    ring on the control: no inset-0 box, no full-viewport size, no backdrop."""
    css = re.sub(r"/\*.*?\*/", "", CSS.read_text(encoding="utf-8"), flags=re.S)
    assert not re.search(r"inset\s*:\s*0", css), "an inset: 0 box"
    assert not re.search(r"100v[wh]", css), "a full-viewport size"
    assert "backdrop" not in css, "a ::backdrop"
    js = (ROOT / "play" / "static" / "js" / "tutorials.js").read_text(encoding="utf-8")
    assert 'popover", "manual"' in js and "showModal" not in js, "the card must be a non-modal popover"
    assert "setInterval" not in js, "no timer moves a card on (WCAG 2.2.1)"


# --- the store ------------------------------------------------------------------------------

@pytest.fixture
def isolated(tmp_path, settings):
    settings.CAMPAIGN_DIR = str(tmp_path / "campaigns")
    return tmp_path


def _store(tmp):
    return tmp / "tutorials.json"


def test_a_missing_file_is_nothing_seen(isolated):
    d = tutorials.read()
    assert d["seen"] == {} and d["off"] is False and d["schema"] == tutorials.SCHEMA


@pytest.mark.parametrize("text", ["{not json", "[1, 2]", '{"schema": 0, "seen": {"table": {"v": 1}}}',
                                  '{"schema": 99, "off": true}', ""])
def test_a_broken_or_foreign_file_reads_as_empty_and_is_rewritten(isolated, text):
    """Derived data in the user directory carries its schema and is never trusted by its
    look (CLAUDE.md, the five-day-old stylesheet). The worst a torn file can do is show the
    tips again; it never fails a page."""
    _store(isolated).write_text(text, encoding="utf-8")
    assert tutorials.read()["seen"] == {}
    tutorials.change({"seen": ["table"]})
    again = json.loads(_store(isolated).read_text(encoding="utf-8"))
    assert again["schema"] == tutorials.SCHEMA and again["seen"]["table"]["v"] == _by("table")["v"]


def test_the_api_marks_seen_resets_and_turns_tips_off(isolated):
    c = Client()
    got = c.get("/api/tutorials").json()
    table = next(t for t in got["tutorials"] if t["id"] == "table")
    assert not table["seen"] and table["due"] == list(range(len(table["steps"])))
    got = c.post("/api/tutorials", {"seen": ["table", "game.grind", "nonsense", 7]},
                 content_type="application/json").json()
    table = next(t for t in got["tutorials"] if t["id"] == "table")
    assert table["seen"] and table["due"] == [] and got["games_seen"] == ["grind"]
    assert c.post("/api/tutorials", {"off": True}, content_type="application/json").json()["off"] is True
    got = c.post("/api/tutorials", {"reset": True}, content_type="application/json").json()
    assert all(not t["seen"] for t in got["tutorials"]) and got["games_seen"] == []
    assert got["off"] is True, "Show all tips again does not turn tips back on by itself"


def test_a_hostile_body_changes_nothing(isolated):
    c = Client()
    for body in ("[1]", "null", '"x"', '{"seen": "table"}', '{"off": "yes"}'):
        r = c.post("/api/tutorials", body, content_type="application/json")
        assert r.status_code == 200
    d = tutorials.read()
    assert d["seen"] == {} and d["off"] is False


def test_an_update_shows_only_the_new_steps_through_the_api(isolated, monkeypatch):
    """D6 end to end: seen at v1, the tutorial now at v2 with one step since 2."""
    tutorials.change({"seen": ["map.region"]})
    real = tutorials.tutorials()
    bumped = json.loads(json.dumps(real))
    bumped["map.region"]["v"] = 2
    bumped["map.region"]["steps"][2]["since"] = 2
    monkeypatch.setattr(tutorials, "tutorials", lambda: bumped)
    t = next(x for x in tutorials.for_page()["tutorials"] if x["id"] == "map.region")
    assert t["updated"] and t["due"] == [2]


def test_a_second_device_sees_what_the_first_dismissed(isolated):
    """The plan's reason for a server store: the LAN phone is another browser on another
    origin. Seen through one client is seen through any, and the LAN door lets a guest
    holding the pass make this write (pathfindergm/lan.py GUEST_WRITES)."""
    from pathfindergm import lan

    Client().post("/api/tutorials", {"seen": ["bench.herbalism"]}, content_type="application/json")
    other = Client(REMOTE_ADDR="192.168.1.50").get("/api/tutorials").json()
    assert next(t for t in other["tutorials"] if t["id"] == "bench.herbalism")["seen"]
    assert lan.guest_may("POST", "/api/tutorials")


def test_both_pages_load_the_cards():
    """The table and the home page (Settings, Tutorials and the welcome line) both run it."""
    for name in ("table.html", "home.html"):
        page = (ROOT / "play" / "templates" / "play" / name).read_text(encoding="utf-8")
        assert "js/tutorials.js" in page and "css/tutorials.css" in page, name


def test_the_shipped_build_carries_the_words():
    spec = (ROOT / "pathfindergm.spec").read_text(encoding="utf-8")
    assert '"tutorials",' in spec


def test_the_march_prompt_carries_its_line_inside_it():
    """Plan §3.1: a prompt that is already on screen (the forced-march line under Travel)
    gets one sentence inside it, never a card over it, and the line is marked seen the
    first time it is drawn. Phase 4 wrote the helper; phase 3 writes the dice popup's."""
    js = (ROOT / "play" / "static" / "js" / "tutorials.js").read_text(encoding="utf-8")
    assert "inline: inline," in js and "post({ seen: [id] })" in js
    m = (ROOT / "play" / "static" / "js" / "table" / "16-tab-map.js").read_text(encoding="utf-8")
    assert 'Tutorials.inline("map.march")' in m
    assert len(_by("map.march")["steps"]) == 1, "an inline line is one step"


def test_the_fight_cards_are_told_by_the_bar():
    """F1-F3 fire from the fight itself: the bar on the player's own turn, non-lethal the
    first time anyone carries some, whose-turn when the ground is looked at in a fight."""
    bar = (ROOT / "play" / "static" / "js" / "table" / "04-combat-and-turns.js").read_text(encoding="utf-8")
    assert 'Tutorials.arrive("fight.bar"' in bar and 'Tutorials.arrive("fight.nonlethal"' in bar
    m = (ROOT / "play" / "static" / "js" / "table" / "16-tab-map.js").read_text(encoding="utf-8")
    assert 'Tutorials.arrive("fight.order"' in m and 'Tutorials.arrive("map.sea")' in m
