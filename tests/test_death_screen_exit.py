"""The death screen has a way out that is neither a new body nor a raising.

The owner's ask, 2026-10-08: the death veil offered the roster, a new character and
"Some weeks later..." and nothing else, so a player who only wanted to stop had to pick
somebody or reload the app. The last option is now "Return to the main page": a real link
to `/`, which posts nothing, so the dead character stays dead until raised or switched.

The trap it had to avoid is recorded in 01-core.js: ONE click listener handles every
`.pick` in the panel, and anything it does not recognise falls through to
`/api/character/new`. A link dressed as a pick would have rolled a new character with an
undefined source on its way out, the same double-handling that once made "Never mind"
start a new game.
"""
from __future__ import annotations

import re

from tests.pagesource import TABLE, TABLE_SCRIPTS


def _template() -> str:
    return TABLE.read_text(encoding="utf-8")


def _core() -> str:
    return (TABLE_SCRIPTS / "01-core.js").read_text(encoding="utf-8")


def _state() -> str:
    return (TABLE_SCRIPTS / "02-state.js").read_text(encoding="utf-8")


def _the_link() -> str:
    m = re.search(r"<a\b[^>]*id=\"deathhome\"[^>]*>(.*?)</a>", _template(), re.S)
    assert m, "the death panel has no #deathhome link"
    return m.group(0)


def test_the_way_out_is_a_real_link_to_the_shelf():
    """A link, not a button that sets location: Tab reaches it, Enter follows it, and
    the desktop window's will-navigate handler lets a same-origin path through."""
    link = _the_link()
    assert 'href="/"' in link
    assert "Return to the main page" in link
    assert "target=" not in link, "a new window would be sent to the system browser"
    # No em-dash in UI copy (the owner's standing instruction).
    assert "—" not in link and "&mdash;" not in link


def test_the_link_sits_in_the_death_panel_outside_the_scrolling_list():
    """A long roster must not push the way out below the fold of an 86vh panel."""
    panel = _template().split('<div id="deathveil">', 1)[1].split("<script", 1)[0]
    scroll = panel.split('<div class="deathscroll">', 1)[1]
    inner, after = scroll.split("</div>\n    </div>", 1)
    assert 'id="deathhome"' not in inner
    assert 'id="deathhome"' in after


def test_the_pick_listener_leaves_the_link_alone():
    """Measured on the first draft: the shared `.pick` listener treated the link as a
    "somebody new" pick and posted /api/character/new with source undefined."""
    src = _core()
    body = src.split('const pick = e.target.closest(".pick");', 1)[1]
    guard = body.find('pick.tagName === "A"')
    assert guard != -1, "the .pick listener has no guard for a link"
    assert guard < body.find('post("/api/character/new"')
    assert guard < body.find('post("/api/resurrect"')


def test_it_is_offered_on_a_death_and_not_on_the_roster():
    """The roster has its own "Never mind"; two ways to close one panel is one too many."""
    death = _state().split("function showDeath", 1)[1].split("\n}\n", 1)[0]
    assert '$("#deathhome").hidden = false' in death
    roster = _core().split("async function openRoster", 1)[1].split("\n}\n", 1)[0]
    assert '$("#deathhome").hidden = true' in roster


def test_the_shelf_opens_for_a_dead_character_and_changes_nothing(tmp_path, settings,
                                                                   monkeypatch, client):
    """Following the link must not touch the save: the campaign stays ended, the
    character stays dead on the roster, and the shelf still offers it to come back to."""
    import json

    from play import campaign as campaign_mod, roster, views
    from rules.sheet import load_pc

    settings.CAMPAIGN_DIR = str(tmp_path / "campaigns")
    monkeypatch.setattr(roster, "root", lambda: tmp_path / "roster")
    (tmp_path / "roster").mkdir()
    campaign_mod._LIVE.clear()

    c = campaign_mod.new_campaign("slice", seed=7)
    pc = load_pc("fixtures/pc-kesst.json")
    entry = roster.enrol(pc)
    c.character_id = entry.id
    if not c.scene.pc():
        c.scene.add(pc)
    pc = c.scene.pc()
    pc.hp = -100
    pc.apply_hp_state()
    views._end_campaign(c, pc)
    c.save()
    saves = sorted((tmp_path / "campaigns").rglob("*.json"))
    before = {p: p.read_bytes() for p in saves}

    r = client.get("/")
    assert r.status_code == 200
    boot = re.search(rb"state_json|\"continue\"", r.content)
    assert boot, "the shelf rendered without its state"

    after = {p: p.read_bytes() for p in sorted((tmp_path / "campaigns").rglob("*.json"))}
    assert after == before, "opening the shelf rewrote the save"
    assert roster.load(entry.id).status == roster.DEAD
    c = campaign_mod.current()
    assert c.ended == "died"
    assert c.scene.pc().has_state("state.down.dead")
    # The shelf still knows the game, so Continue leads back to the death screen.
    m = re.search(r'"continue": (\{.*?\})', r.content.decode("utf-8"))
    assert m and json.loads(m.group(1))["ended"] == "died"
