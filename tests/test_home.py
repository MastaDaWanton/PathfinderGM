"""The front page: the shelf of worlds, what has been played, and the homebrew benches.

Opening the app should land you on the shelf, not mid-scene, so `/` is this page and the
table moved to `/play/`.

Everything on it is read from something real. A front page that advertises features by
listing them is the easiest thing in an app to let drift, and the first thing a user stops
trusting when it does — so the counts come from the tables and the campaigns come from the
saves, and there is a test here for each.
"""
from __future__ import annotations

import json

import pytest
from django.test import Client, override_settings

from play import library
from rules.sheet import load_pc


@pytest.fixture
def client(tmp_path):
    from play import campaign as cm

    with override_settings(CAMPAIGN_DIR=tmp_path / "campaigns"):
        cm._LIVE.clear()
        cm.begin_with(load_pc("fixtures/pc-kesst.json"))
        yield Client()
        cm._LIVE.clear()


# --- routing ---------------------------------------------------------------------------

def test_the_app_opens_on_the_shelf(client):
    r = client.get("/")
    assert r.status_code == 200
    assert b"Pathfinder GM" in r.content


def test_the_table_moved_rather_than_vanished(client):
    assert client.get("/play/").status_code == 200


def test_the_table_links_back_to_the_shelf(client):
    """The request this page exists to answer: reachable from play, both ways."""
    table = client.get("/play/").content.decode()
    assert 'href="/"' in table
    assert 'href="/craft/"' in table

    bench = client.get("/craft/").content.decode()
    assert 'href="/play/"' in bench and 'href="/"' in bench


# --- the shelf --------------------------------------------------------------------------

def test_the_shipped_world_is_on_the_shelf():
    cards = library.worlds()
    pangrella = next(w for w in cards if w.name == "Pangrella")
    assert pangrella.shipped and pangrella.playable
    assert pangrella.entities == 74 and pangrella.events == 111
    assert "Pangrella" in pangrella.settlements
    assert "Zhilakai" in pangrella.peoples


def test_an_unreadable_world_is_listed_with_the_reason(tmp_path):
    """Listed, never hidden. A world that disappears from the shelf because of a version
    number is indistinguishable from one the user lost."""
    from django.conf import settings

    with override_settings(CAMPAIGN_DIR=tmp_path / "campaigns"):
        (library.user_dir() / "broken.json").write_text(
            json.dumps({"schema_version": "99.0", "world": {"name": "Nowhere"}}),
            encoding="utf-8")
        card = next(w for w in library.worlds() if w.id == "broken")

    assert not card.playable
    assert "schema" in card.problem.lower()


def test_a_world_that_is_not_json_at_all_is_still_listed(tmp_path):
    with override_settings(CAMPAIGN_DIR=tmp_path / "campaigns"):
        (library.user_dir() / "junk.json").write_text("not json", encoding="utf-8")
        card = next(w for w in library.worlds() if w.id == "junk")
    assert not card.playable and card.problem


def test_games_are_read_off_the_saves_not_an_index(client):
    """An index is a second thing to keep true, and it would be wrong the first time
    somebody deleted a save by hand — which is supported, the saves being plain files."""
    games = library.campaigns_in("pangrella-campaign")
    assert len(games) == 1
    assert games[0]["character"] == "Kesst Vayr"
    assert games[0]["active"]
    assert games[0]["kind"] == "sandbox"


def test_the_world_page_answers_with_its_games_and_people(client):
    d = client.get("/api/world/pangrella-campaign").json()
    assert d["world"]["name"] == "Pangrella"
    assert d["campaigns"] and d["characters"]
    assert d["pregens"]


def test_a_world_that_does_not_exist_is_a_404(client):
    assert client.get("/api/world/nowhere").status_code == 404


# --- starting and resuming ----------------------------------------------------------------

def test_starting_needs_somebody_to_play(client):
    r = client.post("/api/start", data=json.dumps({"world": "pangrella-campaign"}),
                    content_type="application/json")
    assert r.status_code == 400
    assert "who is playing" in r.json()["error"].lower()


def test_starting_a_sandbox_enrols_and_switches(client):
    from play import campaign as cm

    r = client.post("/api/start",
                    data=json.dumps({"world": "pangrella-campaign", "source": "pc-borin"}),
                    content_type="application/json")
    assert r.status_code == 200
    assert cm.current().scene.pc().name == "Borin Achereth"


def test_a_world_this_build_cannot_play_in_says_so_rather_than_starting_elsewhere(client, tmp_path):
    """`new_campaign` reads settings.WORLD_EXPORT, so choosing another world would have
    produced a campaign in Pangrella wearing the wrong name."""
    (library.user_dir() / "elsewhere.json").write_text(
        json.dumps({"schema_version": "1.0", "world": {"name": "Elsewhere"},
                    "entities": [], "chronology": []}), encoding="utf-8")
    r = client.post("/api/start",
                    data=json.dumps({"world": "elsewhere", "source": "pc-borin"}),
                    content_type="application/json")
    assert r.status_code == 400
    assert "cannot be started in yet" in r.json()["error"]


def test_resuming_puts_a_character_back_in_the_chair(client):
    from play import campaign as cm

    client.post("/api/start",
                data=json.dumps({"world": "pangrella-campaign", "source": "pc-borin"}),
                content_type="application/json")
    kesst = next(c for c in library.recent_characters() if c["name"] == "Kesst Vayr")

    r = client.post("/api/resume", data=json.dumps({"id": kesst["id"]}),
                    content_type="application/json")
    assert r.status_code == 200
    assert cm.current().scene.pc().name == "Kesst Vayr"


def test_resuming_nobody_is_a_404(client):
    r = client.post("/api/resume", data=json.dumps({"id": "nobody"}),
                    content_type="application/json")
    assert r.status_code == 404


# --- recent characters ---------------------------------------------------------------------

def test_recent_puts_whoever_is_in_play_first(client):
    client.post("/api/start",
                data=json.dumps({"world": "pangrella-campaign", "source": "pc-thessaly"}),
                content_type="application/json")
    recent = library.recent_characters()
    assert recent[0]["name"] == "Thessaly Corr"
    assert recent[0]["active"]
    assert all("world" in c for c in recent)


def test_the_dead_stay_on_the_roster(client):
    from play import campaign as cm
    from play import roster

    c = cm.current()
    pc = c.scene.pc()
    pc.hp = -50
    pc.apply_hp_state()
    roster.bury(c.character_id, pc, epitaph="bled out in a yard")

    entry = next(x for x in library.recent_characters() if x["id"] == c.character_id)
    assert entry["status"] == "dead"
    assert not entry["playable"]
    assert entry["epitaph"] == "bled out in a yard"


# --- homebrew benches -----------------------------------------------------------------------

def test_shipped_content_is_not_counted_as_homebrew(client):
    """The first thing anyone disbelieved on this page: 23 Core Rulebook weapons and four
    bestiary creatures reported as things the user had made. Shipped and authored are two
    numbers, and a fresh install has authored nothing."""
    from rules import ingredients

    d = client.get("/api/bench/ingredients").json()
    assert d["bench"]["ready"]
    assert d["bench"]["shipped"] == len(ingredients.all_ingredients())
    assert d["bench"]["yours"] == 0
    assert all(r["mine"] is False for r in d["rows"])


def test_there_is_a_bench_for_character_classes(client):
    """Blood Bending is a 1e class — hit dice, BAB, saves — and had nowhere to live. The
    world-class bench is a different thing: no BAB, no saves, levels on use."""
    d = client.get("/api/bench/classes").json()
    assert d["bench"]["ready"]
    assert d["bench"]["shipped"] == 4                # the Core Rulebook four
    assert "Blood Bending" in d["bench"]["waiting"]
    assert {r["name"] for r in d["rows"]} >= {"Rogue", "Fighter", "Wizard", "Cleric"}


def test_authored_content_is_counted_and_marked(client, tmp_path):
    from play import homebrew

    (homebrew.folder("classes") / "blood-bending.json").write_text(
        json.dumps({"name": "Blood Bending", "summary": "hit points as a resource"}),
        encoding="utf-8")

    d = client.get("/api/bench/classes").json()
    assert d["bench"]["yours"] == 1
    mine = [r for r in d["rows"] if r["mine"]]
    assert len(mine) == 1 and mine[0]["name"] == "Blood Bending"
    # Yours come first, so a long shipped table never buries what you wrote.
    assert d["rows"][0]["mine"]


def test_the_tab_counts_what_you_wrote(client, tmp_path):
    from play import homebrew

    assert homebrew.authored_total() == 0
    (homebrew.folder("creatures") / "mine.json").write_text(
        json.dumps({"name": "Yard dog"}), encoding="utf-8")
    assert homebrew.authored_total() == 1


def test_every_bench_names_a_real_folder(client):
    from pathlib import Path

    from play import homebrew

    for b in homebrew.benches():
        assert Path(b.as_dict()["path"]).is_dir()


def test_a_bench_lists_what_it_holds(client):
    d = client.get("/api/bench/creatures").json()
    assert any(r["name"] for r in d["rows"])

    items = client.get("/api/bench/items").json()
    assert any(r["kind"] == "weapon" for r in items["rows"])
    assert any(r["kind"] == "armour" for r in items["rows"])


def test_a_bench_with_nothing_behind_it_says_so(client):
    d = client.get("/api/bench/spells").json()
    assert d["bench"]["ready"] is False
    assert d["rows"] == []
    assert "no spell system" in d["bench"]["blurb"]


def test_an_unknown_bench_is_a_404(client):
    assert client.get("/api/bench/nonsense").status_code == 404


def test_the_page_carries_everything_it_draws(client):
    """The whole front page is rendered from one embedded payload; a missing key is a
    blank panel with no error anywhere."""
    html = client.get("/").content.decode()
    for key in ('"worlds"', '"recent"', '"benches"', '"continue"', '"pregens"',
                '"authored"'):
        assert key in html
