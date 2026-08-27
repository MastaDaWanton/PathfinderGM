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
from pathlib import Path

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
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


def test_a_campaign_can_be_started_in_an_imported_world(client, tmp_path):
    """This used to be refused with "cannot be started in yet".

    `new_campaign` read `settings.WORLD_EXPORT` in the only two places that decided which
    world a new game was in, so choosing another world would have produced a campaign in
    Pangrella wearing the name Elsewhere. `Campaign` already carried `world_source` and
    already loaded its world from it; the setting was only ever the default.
    """
    from play import campaign as cm

    (library.user_dir() / "elsewhere.json").write_text(
        json.dumps({"schema_version": "1.0", "world": {"name": "Elsewhere"},
                    "entities": [], "chronology": []}), encoding="utf-8")
    r = client.post("/api/start",
                    data=json.dumps({"world": "elsewhere", "source": "pc-borin"}),
                    content_type="application/json")
    assert r.status_code == 200, r.json()
    active = cm.current()
    assert active.world.name == "Elsewhere"
    assert "elsewhere.json" in str(active.world_source)


def test_the_world_a_campaign_is_in_survives_a_restart(client):
    """The world has to come back off the save, not off the setting — otherwise a game in
    an imported world silently moves to Pangrella the first time the app is reopened."""
    from play import campaign as cm

    (library.user_dir() / "elsewhere.json").write_text(
        json.dumps({"schema_version": "1.0", "world": {"name": "Elsewhere"},
                    "entities": [], "chronology": []}), encoding="utf-8")
    client.post("/api/start",
                data=json.dumps({"world": "elsewhere", "source": "pc-borin"}),
                content_type="application/json")
    campaign_id = cm.current().id
    cm._LIVE.clear()                                   # as a restart would
    assert cm.current(campaign_id).world.name == "Elsewhere"


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
    # The `waiting` note used to say a class "still cannot declare a path". It can:
    # Blood Bending's four branches ship in the file and the class builder authors
    # them, so the note is gone rather than left saying something that is no longer
    # true. What the bench owes instead is the way in.
    assert d["bench"]["waiting"] == ""
    assert d["bench"]["builder"] == "page"
    assert d["bench"]["builder_url"] == "/homebrew/classes/"
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
    d = client.get("/api/bench/campaigns").json()
    assert d["bench"]["ready"] is False
    assert d["rows"] == []
    assert "campaign format" in d["bench"]["blurb"]


def test_an_unknown_bench_is_a_404(client):
    assert client.get("/api/bench/nonsense").status_code == 404


def test_the_page_carries_everything_it_draws(client):
    """The whole front page is rendered from one embedded payload; a missing key is a
    blank panel with no error anywhere."""
    html = client.get("/").content.decode()
    for key in ('"worlds"', '"recent"', '"benches"', '"continue"', '"pregens"',
                '"authored"'):
        assert key in html


# --- importing a world -----------------------------------------------------------------
#
# "need an import world button". `library.import_world` existed and took a filesystem
# path, which is no use to a packaged app with no terminal: a player who has just exported
# a world from World Bible has a file in Downloads, not a path they want to type.

def _export(name="Elsewhere", schema="1.0"):
    return json.dumps({"schema_version": schema, "world": {"name": name},
                       "entities": [], "chronology": []}).encode("utf-8")


def _upload(client, filename, data):
    return client.post("/api/worlds/import",
                       {"world": SimpleUploadedFile(filename, data,
                                                    content_type="application/json")})


def test_an_uploaded_world_lands_on_the_shelf(client):
    r = _upload(client, "kaelinora.json", _export("Kaelinora"))
    assert r.status_code == 200, r.json()
    assert r.json()["world"]["name"] == "Kaelinora"
    assert "kaelinora" in [w.id for w in library.worlds()]


def test_a_file_that_is_not_a_world_is_refused_before_it_lands(client):
    """Refused at the point the player can still do something about it, rather than
    landing and failing later when somebody tries to play in it."""
    r = _upload(client, "notes.json", b'{"hello": "world"}')
    assert r.status_code == 400
    assert "notes.json" not in [p.name for p in library.user_dir().glob("*.json")]


def test_an_empty_file_is_refused(client):
    assert _upload(client, "empty.json", b"").status_code == 400


def test_a_broken_upload_does_not_destroy_the_world_it_overwrites(client):
    """The import writes to its final path to validate there, because `load_cached` keys
    its cache on the path. Without a rollback that made a bad file cost the player the
    good world of the same name as well as the bad one."""
    assert _upload(client, "shared.json", _export("The Good One")).status_code == 200
    assert _upload(client, "shared.json", b"{ not json").status_code == 400
    assert library.get("shared").name == "The Good One"


@pytest.mark.parametrize("sent,expect", [
    ("../../settings.json", "settings.json"),
    (r"..\..\evil.json", "evil.json"),
    ("/etc/passwd", "passwd.json"),
    ("world.json", "world.json"),
    ("no-extension", "no-extension.json"),
])
def test_an_uploaded_filename_cannot_escape_the_worlds_directory(sent, expect):
    """An upload names its own file, and a browser will send `../../settings.json`
    without complaint if something asks it to."""
    assert library.safe_name(sent) == expect


def test_a_file_larger_than_the_ceiling_is_refused(client, monkeypatch):
    """Not a tight limit — a real export is over a megabyte — but without one the import
    is a way to fill the disk."""
    monkeypatch.setattr(library, "MAX_IMPORT_BYTES", 16)
    r = _upload(client, "huge.json", _export("Too Big"))
    assert r.status_code == 400
    assert "MB" in r.json()["error"]


def test_a_world_written_against_a_schema_this_build_cannot_read_says_so(client):
    r = _upload(client, "future.json", _export("Tomorrow", schema="99.0"))
    assert r.status_code == 400
    assert "99" in r.json()["error"] or "schema" in r.json()["error"].lower()


def test_no_file_at_all_is_a_sentence_rather_than_a_stack_trace(client):
    r = client.post("/api/worlds/import", {})
    assert r.status_code == 400 and "No file" in r.json()["error"]


def test_the_shelf_can_be_reread_without_reloading_the_page(client):
    """The page redraws from this after an import; a full reload would throw away the
    message saying what just happened."""
    before = len(client.get("/api/worlds").json()["worlds"])
    _upload(client, "another.json", _export("Another"))
    assert len(client.get("/api/worlds").json()["worlds"]) == before + 1


def test_the_spells_bench_sends_you_to_the_spell_builder(client):
    """The spell form was a panel underneath a 3,040-row browse table — you reached the
    Name field by scrolling past every spell in the game, and the two halves fought over
    one screen. It has a page of its own now, and the bench's job is the way in."""
    d = client.get("/api/bench/spells").json()
    assert d["bench"]["builder"] == "page"
    assert d["bench"]["builder_url"] == "/homebrew/spells/"


def test_starting_from_a_spell_copies_everything_but_the_name(client):
    """The one field that must not be inherited. A copied name would make Save overwrite
    the spell the author was learning from, which is the single mistake a
    start-from-this feature can make that destroys somebody else's work."""
    d = client.get("/api/spells/start/fireball").json()
    draft = d["draft"]
    assert d["started_from"] == "Fireball"
    assert draft["name"] == ""                    # empty, not absent
    assert "id" not in draft
    assert draft["school"] == "evocation"         # and everything else came along
    assert draft["saving_throw"].lower().startswith("reflex")


def test_the_picker_can_reach_a_spell_past_the_first_four_hundred(client):
    """The list is capped so a select is not a megabyte, which put everything after "C"
    out of reach — the page said "type in the box to narrow it" while having no box.
    Fireball is the proof: it is nowhere near the first 400 by name."""
    plain = client.get("/api/spells/list").json()
    assert plain["total"] == 3040
    assert "fireball" not in {s["id"] for s in plain["spells"]}

    found = client.get("/api/spells/list?q=fireball").json()
    assert "fireball" in {s["id"] for s in found["spells"]}


def test_the_spells_bench_draws_one_list_and_not_two(client):
    """The bench drew the same 3,040 spells twice: `paneSpells()` renders the list the
    search box drives, and the generic `BENCH.rows` table drew a second one underneath —
    the first 200 by name, wired to nothing. Typing "fireball" filtered the top list and
    left the lower one showing Abadar's Truthtelling onward, which reads as a broken
    search. `OWN_LISTING` is what suppresses it; the pane is JS, so the guard is what
    there is to pin."""
    tpl = (Path(__file__).resolve().parents[1]
           / "play" / "templates" / "play" / "home.html").read_text(encoding="utf-8")
    assert 'const OWN_LISTING = ["spells"];' in tpl
    assert "BENCH.rows.length && !OWN_LISTING.includes(b.id)" in tpl
    # And the surviving list scrolls inside itself. It was `max-height:none`, so opening
    # the bench grew the page by 3,040 rows and using the search box scrolled the box
    # itself off the top of the screen.
    assert "max-height:none" not in tpl
    assert ".rows.spellrows" in tpl


def test_the_literal_spell_routes_are_not_read_as_spell_names(client):
    """`api/spells/<spell_id>` already existed, and Django takes the first match — so
    /api/spells/list came back 404 "no spell 'list'". Ordering, pinned."""
    assert client.get("/api/spells/list").status_code == 200
    assert client.get("/api/spells/fireball").status_code == 200



def test_the_spawned_arrive_with_pockets_worth_looting():
    """The loot op made empty pockets visible: "take everything" off a thug who owns a
    sap is a hollow sentence. Kits are tables and never a model's guess — but since
    Schrödinger's pockets, the table is a CLAIM at spawn (kit_pending, tagged with
    the kit that made it) and contents only at first observation: collapse_kit rolls
    the wealth and fills the inventory, once, immutably. Armour and weapons still
    resolve at spawn — combat needs them the same round. Animals carry no claim."""
    from rules.bestiary import collapse_kit, instantiate
    from rules.engine import Scene

    s = Scene()
    thug = instantiate("thug", scene=s, name="the tough")
    assert thug.purse == {} and thug.inventory == {}     # unobserved
    assert thug.kit_pending.get("kit") == "kit.cutpurse"
    assert thug.armour == "leather"                # worn, hence lootable
    made = collapse_kit(thug)
    assert thug.purse.get("sp", 0) >= 2            # 2d4 sp, rolled at first look
    assert thug.inventory and made
    assert collapse_kit(thug) == []                # looked twice, nothing doubles
    dog = instantiate("guard dog", scene=s, name="the dog")
    assert dog.kit_pending == {} and dog.purse == {} and dog.inventory == {}


def test_every_campaign_begins_with_a_live_thread():
    """The event-watcher role was configured and never once called: every campaign
    began with no world state at all. The undercurrent is rolled at creation — the
    world's own unwritten hooks first (name and why, not the bare name), a
    world-agnostic table when the export ships none — and planted in history as the
    GM's private note."""
    from django.conf import settings

    from play import opening
    from world.loader import load_cached

    w = load_cached(settings.WORLD_EXPORT)
    rolled = opening.undercurrent(w, seed=7)
    assert " — " in rolled or rolled                # a name AND its why

    class Bare:
        unwritten = []
    fallback = opening.undercurrent(Bare(), seed=3)
    assert fallback in opening.UNDERCURRENTS

    from play import campaign as cm
    from rules.sheet import load_pc
    c = cm.new_campaign("undercurrent-test", seed=5,
                        character=load_pc("fixtures/pc-kesst.json"))
    notes = [h for h in c.history if "private note" in str(h.get("content", ""))]
    assert len(notes) == 1
    assert "never announce it" in notes[0]["content"]


def test_a_save_anchored_in_a_dead_pyinstaller_temp_dir_still_loads():
    """Measured live 2026-08-27: three saves carried world_source like
    'C:\...\Temp\_MEI267002\fixtures\pangrella-campaign.json' — the per-launch
    extraction dir of the run that wrote them — and the home page 500'd on every
    launch after. The tail past the _MEI dir re-anchors onto the current bundle."""
    from play.campaign import _resolve_world_source, _portable_world_source
    from pathfindergm.paths import resource_root

    poisoned = r"C:\Users\nobody\AppData\Local\Temp\_MEI267002\fixtures\pangrella-campaign.json"
    healed = _resolve_world_source(poisoned)
    assert healed == resource_root() / "fixtures" / "pangrella-campaign.json"
    assert healed.exists()

    # And what gets written from now on is relative for anything under the bundle,
    # absolute (and stable) for an imported world in the user's data directory.
    assert _portable_world_source(resource_root() / "fixtures" / "x.json") == "fixtures/x.json"
    assert _portable_world_source(r"C:\Users\nobody\AppData\Local\PathfinderGM\worlds\w.json") \
        == r"C:\Users\nobody\AppData\Local\PathfinderGM\worlds\w.json"
    assert _resolve_world_source("fixtures/pangrella-campaign.json").exists()
