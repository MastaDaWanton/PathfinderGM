"""Guided creation: the rules decide, and a refusal names the number.

The output contract is the whole design: a made character is exactly the dict a pregen
file holds, loaded through the same `from_dict`, enrolled through the same roster. If
anything downstream could tell them apart, creation would be a second character system
to keep level with the first.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from django.test import Client, override_settings

from rules import creation
from rules.sheet import from_dict


def spec(**over):
    base = {
        "name": "Durga Stonebrow", "race": "dwarf", "class": "fighter", "pronouns": "she/her",
        "abilities": {"str": 16, "dex": 14, "con": 14, "int": 10, "wis": 12, "cha": 8},
        "skills": ["climb", "intimidate"],
        "feats": ["power attack", {"id": "weapon-focus", "target": "longsword"}],
    }
    base.update(over)
    return base


# --- the numbers -------------------------------------------------------------------------

def test_a_legal_character_builds_and_loads():
    built, problems = creation.build(spec())
    assert problems == []
    actor = from_dict(built["sheet"])
    assert actor.name == "Durga Stonebrow"
    assert actor.hp == 10 + 1 + 2      # max d10, +Con 16 after the dwarf's +2... 13


def test_racial_modifiers_are_baked_into_the_scores():
    built, _ = creation.build(spec())
    ab = built["sheet"]["abilities"]
    assert ab["con"] == 16 and ab["wis"] == 14 and ab["cha"] == 6


def test_the_point_budget_is_a_wall():
    _, problems = creation.build(spec(abilities={
        "str": 18, "dex": 18, "con": 18, "int": 10, "wis": 10, "cha": 10}))
    assert any("points" in p for p in problems)


def test_scores_run_seven_to_eighteen_before_race():
    _, problems = creation.build(spec(abilities={
        "str": 19, "dex": 10, "con": 10, "int": 10, "wis": 10, "cha": 10}))
    assert any("7 to 18" in p for p in problems)


def test_a_human_must_say_where_their_bonus_goes():
    """+2 anywhere is a choice, and silently picking for the player is choosing their
    character."""
    _, problems = creation.build(spec(race="human"))
    assert any("say which ability" in p for p in problems)
    built, problems = creation.build(spec(race="human", bonus_ability="str"))
    assert problems == []
    assert built["sheet"]["abilities"]["str"] == 18


def test_skill_ranks_are_counted_and_named():
    _, problems = creation.build(spec(skills=["climb", "intimidate", "swim"]))
    assert any("ranks" in p for p in problems)
    _, problems = creation.build(spec(skills=["basketweaving"]))
    assert any("not a skill" in p for p in problems)


def test_the_racial_int_pays_for_skill_ranks():
    """Found in live play. A human blood bender bought Int 18 and put the racial +2 there,
    making Int 20 on the finished sheet — and the creation screen showed "ranks (4 class
    +1 human + Int) 10 / 9" in red for the tenth skill. The server accepted all ten.

    `creation.build` applies the racial adjustment and only then reads the modifier, so
    the budget is 4 + 5 + 1 = 10. The page was reading the bought score, 18, for a
    modifier of +4. Pinned on the server, which is the side that was right."""
    built, problems = creation.build(spec(
        race="human", bonus_ability="int", **{"class": "blood bending"},
        # Int 18 is 17 of the 20-point budget on its own; the rest stay at 10.
        abilities={"str": 10, "dex": 10, "con": 10, "int": 18, "wis": 10, "cha": 10},
        paths=["battle blood"],
        # Two feats with no prerequisites. This spec carried Dodge at Dex 10 for as
        # long as feat prerequisites were advisory; the day they became a refusal it
        # was the first thing refused, and this test is about skill ranks.
        feats=["toughness", "improved initiative"],
        skills=["acrobatics", "climb", "craft", "heal", "intimidate",
                "knowledge (nature)", "perception", "profession", "stealth", "survival"],
    ))
    assert problems == [], problems
    assert built["sheet"]["abilities"]["int"] == 20
    assert len(built["sheet"]["ranks"]) == 10


def test_an_elfs_fixed_int_pays_for_skill_ranks_too():
    """The elf is the worse half of the same bug: their +2 Int is fixed in `mods` rather
    than chosen, so no bonus_ability is involved and the page's raw read was short a rank
    in every elf build ever made, with nothing on screen to explain it."""
    built, problems = creation.build(spec(
        race="elf", **{"class": "wizard"},
        abilities={"str": 10, "dex": 10, "con": 10, "int": 18, "wis": 10, "cha": 10},
        skills=["appraise", "craft", "fly", "knowledge (arcana)",
                "linguistics", "perception", "spellcraft"],
        feats=["toughness"],
        spellbook=["mage-armor", "magic-missile", "shield", "sleep",
                   "burning-hands", "charm-person", "grease", "enlarge-person"],
    ))
    assert problems == [], problems
    assert built["sheet"]["abilities"]["int"] == 20
    # 2 class + 5 Int, no human rank: seven, where the raw read allowed six.
    assert len(built["sheet"]["ranks"]) == 7
    # And 3 + 5 spells, where the raw read allowed 3 + 4.
    assert len(built["sheet"].get("spellbook") or []) == 8


def test_a_new_character_has_the_money_their_class_declares():
    """Every class states starting wealth — "1d6 x 10 gp" for Blood Bending, "5d6 x 10
    gp" for a fighter — and `build` never read it, so every character ever made began
    with `purse: {}`. Invisible until the craft hub grew a market, where "Buy from the
    market" handed over Steel, a Steel Crossguard and Tin to a character with nothing in
    their pockets. Four classes had no figure at all; they live in `tables.CLASSES` and
    now carry the Core Rulebook's."""
    for cid, low, high in (("fighter", 50, 300), ("wizard", 30, 180),
                           ("rogue", 40, 240), ("cleric", 40, 240)):
        seen = set()
        for _ in range(40):
            built, problems = creation.build(spec(
                **{"class": cid}, race="human", bonus_ability="str",
                skills=["climb"], feats=["toughness", "dodge"],
                spellbook=(["mage-armor", "magic-missile", "shield"]
                           if cid == "wizard" else []),
                # A cleric takes two domains at creation since 2026-09-19 and is refused
                # without them, the way a wizard with an empty book is refused (item 27).
                domains=creation.starter_domains(cid),
            ))
            assert problems == [], (cid, problems)
            gp = built["sheet"]["purse"].get("gp", 0)
            assert low <= gp <= high, f"{cid} rolled {gp}, outside {low}..{high}"
            seen.add(gp)
        assert len(seen) > 1, f"{cid} starting wealth is not being rolled"


def test_the_creation_page_reads_abilities_after_the_race():
    """The disagreement was only ever in the page: `ranksBudget` and `spellCap` did their
    own `Math.floor((f.abilities.int - 10) / 2)` on the bought score. Both go through
    `abilityMod` now, which applies `mods` and the chosen +2 first. Pinned as source
    because the budget is drawn in JS and cannot be reached from here."""
    tpl = (Path(__file__).resolve().parents[1]
           / "play" / "templates" / "play" / "home.html").read_text(encoding="utf-8")
    assert "function finalAbility(f, opts, ab)" in tpl
    assert 'const intMod = abilityMod(f, opts, "int");' in tpl
    assert 'return 3 + abilityMod(f, opts, "int");' in tpl
    # The raw read is gone from both budgets.
    assert "Math.floor((f.abilities.int - 10) / 2)" not in tpl


def test_a_human_fighter_gets_three_feats_and_a_dwarf_one_fewer():
    """One for everyone, one for a human, one for a fighter — the budget is stated in
    the refusal so the player learns the rule from being refused."""
    _, problems = creation.build(spec(
        feats=["power attack", {"id": "weapon-focus", "target": "longsword"}, "toughness"]))
    assert any("feats against 2" in p for p in problems)
    built, problems = creation.build(spec(
        race="human", bonus_ability="str",
        feats=["power attack", {"id": "weapon-focus", "target": "longsword"}, "toughness"]))
    assert problems == []


def test_spells_known_are_capped_by_the_class():
    _, problems = creation.build(spec(
        race="human", bonus_ability="cha", **{"class": "sorcerer"},
        skills=["bluff", "spellcraft"], feats=["toughness", "dodge"],
        spellbook=["magic-missile", "shield", "grease"]))
    assert any("against 2 known" in p for p in problems)


def test_a_non_caster_picks_no_spells():
    _, problems = creation.build(spec(spellbook=["magic-missile"]))
    assert any("picks no spells" in p for p in problems)


def test_a_spell_off_the_class_list_is_refused():
    _, problems = creation.build(spec(
        race="human", bonus_ability="cha", **{"class": "sorcerer"},
        skills=["bluff", "spellcraft"], feats=["toughness", "dodge"],
        spellbook=["cure-light-wounds"]))
    assert any("not a level 0-1 sorcerer spell" in p for p in problems)


def test_all_the_problems_arrive_at_once():
    """A wizard nobody finishes is a wizard built one error per submit."""
    _, problems = creation.build({"name": "", "race": "orc", "class": "ninja"})
    assert len(problems) >= 3


def test_a_new_character_leaves_the_forge_with_a_purse_and_their_hands():
    """This walked `creation.KITS` — eleven hand-written class kits — until 2026-09-19,
    when the player asked for them to go: "remove the starting items from classes and give
    them extra starting gold, we have the outfitter now".

    Removing them is the Core Rulebook rather than a nerf, and the arithmetic is why:
    starting wealth was ALREADY rolled per class, so a character was getting the book's
    full wealth *and* a free kit on top. A fighter's kit priced at 172 gp against an
    average roll of 175. What the book grants is one line — "each character begins play
    with an outfit worth 10 gp or less" — and that is `OUTFITS`, which stays."""
    for cid in ("fighter", "wizard", "cleric", "rogue", "monk"):
        built, problems = creation.build({
            "name": f"Kit test {cid}", "race": "elf", "class": cid, "pronouns": "she/her",
            "abilities": {"str": 14, "dex": 14, "con": 12, "int": 10,
                          "wis": 10, "cha": 10},
            "skills": [], "feats": [],
            "spellbook": creation.starter_spells(cid, int_mod=1),
            "domains": creation.starter_domains(cid),
        })
        assert problems == [], (cid, problems)
        sheet = built["sheet"]
        assert sheet["weapons"] == ["unarmed"], cid
        assert sheet["equipped"] == "unarmed" and sheet["armour"] == "none"
        assert sheet["shield"] == "none"
        # The outfit, and the purse to buy the rest with.
        assert sheet["goods"] and sum(sheet["purse"].values()) > 0, cid
        from_dict(sheet)
    assert not hasattr(creation, "KITS"), "the kits are gone, not merely unused"


def test_a_body_that_came_with_weapons_keeps_them():
    """The one thing that is not bought: a race built with claws or a bite carries them
    because they are part of it. No SHIPPED race has natural weapons — this is a homebrew
    body's path — so the check is on the code rather than on a character."""
    import inspect

    src = inspect.getsource(creation.build)
    assert 'own = [str(w.get("key")) for w in (race.get("weapons") or [])' in src
    assert 'weapons = own + ["unarmed"] if own else ["unarmed"]' in src


# --- through the wire -----------------------------------------------------------------------

@pytest.fixture
def client(tmp_path, settings):
    settings.CAMPAIGN_DIR = str(tmp_path / "campaigns")
    return Client()


def test_the_wizard_draws_from_one_payload(client):
    d = client.get("/api/create/options").json()
    assert len(d["races"]) == 7
    assert {c["id"] for c in d["classes"]} >= {"barbarian", "monk", "sorcerer"}
    assert d["point_budget"] == 20
    assert "stealth" in d["skills"]


def test_creating_over_the_wire_lands_on_the_roster(client):
    r = client.post("/api/character/create", data=json.dumps(spec()),
                    content_type="application/json")
    assert r.status_code == 200
    d = r.json()
    assert d["ok"] and d["id"] == "durga-stonebrow"

    from play import roster
    entry = roster.load(d["id"])
    assert entry is not None
    assert entry.sheet["class"] == "fighter"
    assert entry.sheet["abilities"]["con"] == 16


def test_a_broken_character_reports_every_problem(client):
    r = client.post("/api/character/create",
                    data=json.dumps({"name": "", "race": "x", "class": "y"}),
                    content_type="application/json")
    assert r.status_code == 400
    assert len(r.json()["problems"]) >= 3


# --- the roster stops multiplying (found in use, 2026-08-22) ---------------------------

def test_an_abandoned_start_is_retired_when_the_next_game_begins(tmp_path):
    """Seven identical "Kesst Vayr · Rogue 1 · 9/9 hp" rows accumulated in one afternoon
    of playtesting, and a roster nobody can read is a roster nobody uses.

    The first fix tried was recycling the entry inside `enrol` — and
    `test_two_characters_of_the_same_name_do_not_collide` caught it immediately, which
    is the test doing its job: two characters who merely share a name must never
    overwrite each other, however empty one of them looks. So the narrower rule stands
    instead, and it is the one this module already applies to the character a reset
    replaces: a start with no turns in it is retired, not deleted and not reused.
    """
    from django.test import override_settings

    from play import campaign as cm, roster
    from rules.sheet import load_pc

    with override_settings(CAMPAIGN_DIR=tmp_path / "campaigns"):
        cm._LIVE.clear()
        first = cm.begin_with(load_pc("fixtures/pc-kesst.json"))
        assert roster.load(first.character_id).status == roster.ALIVE

        second = cm.begin_with(load_pc("fixtures/pc-kesst.json"))
        assert roster.load(first.character_id).status == roster.RETIRED
        living = [e for e in roster.everyone() if e.status == roster.ALIVE]
        assert [e.id for e in living] == [second.character_id]


def test_a_character_who_played_is_never_retired_behind_your_back(tmp_path):
    """The dead and the played stay on the roster: they are the reason the next game
    went the way it did. Only an empty start is swept up."""
    from django.test import override_settings

    from play import campaign as cm, roster
    from rules.sheet import load_pc

    with override_settings(CAMPAIGN_DIR=tmp_path / "campaigns"):
        cm._LIVE.clear()
        first = cm.begin_with(load_pc("fixtures/pc-kesst.json"))
        played = roster.load(first.character_id)
        played.turns_played = 12
        roster.save(played)

        cm.begin_with(load_pc("fixtures/pc-borin.json"))
        assert roster.load(first.character_id).status == roster.ALIVE


def test_the_forge_is_reachable_from_the_shelf_and_from_a_world():
    """Creation shipped and stayed behind one button on the roster tab, while a world's
    own "Start something new" still said full creation was "the next piece" — the exact
    drift this page's module docstring warns about."""
    from pathlib import Path

    page = Path("play/templates/play/home.html").read_text(encoding="utf-8")
    assert page.count("data-forge") >= 3, "shelf, world and roster each need a door"
    assert "next piece; until it lands" not in page
    # And the forge outranks the tab, so it can open from any of them.
    assert "FORGE ? paneForge()\n    : TAB === \"worlds\"" in page


# --- the two buttons that looked broken (found in play, 2026-08-22) --------------------

def test_create_and_play_plays_the_character_it_says_it_made(client, tmp_path, settings):
    """Reported as "does not start a session with the created character".

    `create_character` enrolled the character and then called `begin_with`, which
    enrols one itself — two roster rows per press. Once beginning a game started
    retiring abandoned starts, the first of the pair was retired on the spot and the
    campaign ran on "doubled-twice-2", while the response reported "doubled-twice".
    The id the API hands back must be the id that is actually being played.
    """
    from play import campaign as cm, roster

    cm._LIVE.clear()
    r = client.post("/api/character/create",
                    data=json.dumps(spec(name="Doubled Twice", begin=True)),
                    content_type="application/json")
    assert r.status_code == 200
    made = r.json()["id"]

    assert cm.current().character_id == made
    assert roster.load(made).status == roster.ALIVE
    assert [e.id for e in roster.everyone()] == [made], "one press, one character"


def test_a_character_parked_on_the_roster_survives_the_next_game_starting(client,
                                                                          tmp_path,
                                                                          settings):
    """"Create for the roster" means build them and leave them on the shelf. The
    abandoned-start sweep read every alive character with no turns as walked out on,
    which retired the ones deliberately parked — they have no campaign because they
    are waiting for one, not because anybody abandoned them."""
    from play import campaign as cm, roster
    from rules.sheet import load_pc

    cm._LIVE.clear()
    r = client.post("/api/character/create", data=json.dumps(spec(name="Shelf Sitter")),
                    content_type="application/json")
    parked = r.json()["id"]
    assert roster.load(parked).campaign_id == ""

    cm.begin_with(load_pc("fixtures/pc-kesst.json"))
    assert roster.load(parked).status == roster.ALIVE


def test_the_forge_sends_you_where_the_new_character_is():
    """Reported as "create for roster also does nothing". It did work — it reloaded
    onto the shelf of worlds, and the character it had just made was on a tab nobody
    had opened. The page now opens on the roster and names them."""
    from pathlib import Path

    page = Path("play/templates/play/home.html").read_text(encoding="utf-8")
    assert 'window.location.href = `/?made=${encodeURIComponent(d.id)}`' in page
    # The tab the page opens on. Asserted as the branch rather than the whole line: the
    # first-run redirect (`?setup=1`) took a turn in front of this one, and the string
    # match broke on a change that left the behaviour exactly as it was. What matters
    # is that a freshly forged character still lands on the roster.
    assert 'MADE ? "characters" : "worlds"' in page
    assert "madebanner" in page


# --- the class the wizard could not build (found by mouse, 2026-08-22) ----------------

def test_every_class_on_the_menu_can_actually_be_built():
    """Reported as "I click the button and nothing happens", on a half-orc Blood Bender.

    `test_every_kit_survives_the_sheet_validator` walked `creation.KITS`, and Blood
    Bending has no kit — so the one class that could not be built was the one class
    the loop never tried. This walks what the wizard actually *offers*, which is the
    only list that matches what a player can click.

    The crash: Blood Bending declares `"hit_die": "2d8"` and `int("2d8")` raised a
    ValueError, which reached the browser as a 500 the forge rendered as nothing at all.
    """
    opts = creation.options()
    assert any(c["id"] == "blood bending" for c in opts["classes"])
    for c in opts["classes"]:
        built, problems = creation.build({
            "name": f"Menu test {c['id']}", "race": "human", "bonus_ability": "con",
            "class": c["id"],
            "pronouns": "she/her",
            "abilities": {"str": 12, "dex": 12, "con": 12, "int": 12,
                          "wis": 12, "cha": 12},
            "skills": [], "feats": [],
            # A caster with an empty book cannot take their own turn, so the menu walk
            # gives each one a legal opening spellbook.
            "spellbook": creation.starter_spells(c["id"], int_mod=1),
            "domains": creation.starter_domains(c["id"]),
            # A class that declares branches must have one chosen; one that declares
            # none must carry none. Taking the first offered exercises both sides.
            "paths": creation.leveling.paths_for(c["id"])[:1],
        })
        assert problems == [], (c["id"], problems)
        from_dict(built["sheet"])


def test_a_hit_die_may_be_written_as_notation():
    """Core classes say `8`; a homebrew class may say `2d8`, and its first level takes
    the maximum of it like everybody else's."""
    assert creation.max_hit_die(8) == 8
    assert creation.max_hit_die("8") == 8
    assert creation.max_hit_die("2d8") == 16
    assert creation.max_hit_die("d10") == 10
    assert creation.max_hit_die("1d8+2") == 10
    # Unreadable is a d8 rather than a refusal: losing the character over its hit die
    # would be the worse answer.
    assert creation.max_hit_die("a fistful of dice") == 8


def test_a_blood_bender_gets_the_hit_points_the_class_grants():
    built, problems = creation.build(spec(**{"class": "blood bending"},
                                          skills=[], feats=["toughness"],
                                          paths=["battle blood"]))
    assert problems == [], problems
    # 2d8 maxed is 16, and the dwarf's Con 16 adds 3.
    assert built["sheet"]["hp"] == 16 + 3


def test_a_class_card_never_reads_d2d8():
    assert creation.die_label(8) == "d8"
    assert creation.die_label("2d8") == "2d8"
    labels = {c["id"]: c["die_label"] for c in creation.options()["classes"]}
    assert labels["blood bending"] == "2d8" and labels["fighter"] == "d10"


def test_the_forge_survives_a_server_that_answers_in_html():
    """The 500 was invisible because the page did `await r.json()` on Django's HTML
    debug page: a SyntaxError inside an async click handler is an unhandled rejection,
    and the button did nothing, said nothing and logged nothing."""
    from pathlib import Path

    page = Path("play/templates/play/home.html").read_text(encoding="utf-8")
    assert "const body = await r.text();" in page
    assert "did not answer in JSON" in page


# --- taking a character off the roster --------------------------------------------------

def test_a_character_can_be_deleted(client, tmp_path, settings):
    from play import roster

    r = client.post("/api/character/create", data=json.dumps(spec(name="Gone Soon")),
                    content_type="application/json")
    made = r.json()["id"]
    assert roster.load(made) is not None

    r = client.post("/api/character/delete", data=json.dumps({"id": made}),
                    content_type="application/json")
    assert r.status_code == 200
    assert roster.load(made) is None
    assert made not in [e.id for e in roster.everyone()]


def test_delete_deletes_the_file_and_the_game_and_archives_nothing(client, tmp_path, settings):
    """This used to archive — "the row leaves the page and the file stays on disk" —
    and the user asked in as many words to stop: the archive folders held
    kesst-vayr-2 through -7 and the campaigns directory kept twenty saves for a
    roster of five. Measured on the real data directory, 2026-09-04. The confirmation
    dialog is the guard now; nothing is kept and no archive folder is made."""
    from pathlib import Path
    from play import campaign as cm, roster

    r = client.post("/api/character/create", data=json.dumps(spec(name="Gone")),
                    content_type="application/json")
    made = r.json()["id"]
    # Give them a game, then switch away so they are not the one being played.
    client.post("/api/character/switch", data=json.dumps({"id": made}),
                content_type="application/json")
    save = Path(settings.CAMPAIGN_DIR) / f"{made}.json"
    assert save.exists()
    other = client.post("/api/character/create", data=json.dumps(spec(name="Other")),
                        content_type="application/json").json()["id"]
    client.post("/api/character/switch", data=json.dumps({"id": other}),
                content_type="application/json")

    r = client.post("/api/character/delete", data=json.dumps({"id": made}),
                    content_type="application/json")
    assert r.status_code == 200, r.content
    assert not roster.path_for(made).exists()
    assert not save.exists()
    assert made not in cm._LIVE
    assert not (roster.root() / "archive").exists()


def test_the_character_being_played_cannot_be_deleted(client, tmp_path, settings):
    """Deleting the game under your own cursor is not a tidy-up, it is a bug."""
    from play import campaign as cm, roster

    cm._LIVE.clear()
    r = client.post("/api/character/create",
                    data=json.dumps(spec(name="In The Chair", begin=True)),
                    content_type="application/json")
    made = r.json()["id"]

    r = client.post("/api/character/delete", data=json.dumps({"id": made}),
                    content_type="application/json")
    assert r.status_code == 409
    assert "character you are playing" in r.json()["error"]
    assert roster.load(made) is not None


def test_deleting_somebody_who_is_not_there_says_so(client, tmp_path, settings):
    r = client.post("/api/character/delete", data=json.dumps({"id": "nobody"}),
                    content_type="application/json")
    assert r.status_code == 409
    assert "no character" in r.json()["error"]


def test_the_page_asks_before_it_deletes():
    """One press deletes nothing. The confirm names them, so a misclick on the wrong
    card is caught by reading rather than by regret."""
    from pathlib import Path

    page = Path("play/templates/play/home.html").read_text(encoding="utf-8")
    assert "data-remove" in page
    # Asked in the page rather than by `confirm()`: the native dialog is suppressed
    # in the app's own browser pane, so a real mouse click produced no prompt and no
    # delete, and the button read as broken.
    assert "function askToDelete(" in page
    assert "await askToDelete(who)" in page
    # The *call*, not the word: the comment above it explains the ban.
    assert "if (!confirm(" not in page, "native dialogs die in the packaged app"
    assert "Keep them" in page
    # And the card you are playing offers no button at all.
    assert 'c.active ? "" : `<button class="quiet danger"' in page


def test_gender_is_asked_for_and_never_assumed():
    """Reported from the roster: "she has also not been treated as a woman".

    Thessaly Corr is a wizard with 66 turns played and `pronouns: they/them`, and so was
    every other character made through the forge — a roster of seven had two sets of real
    pronouns and both came off fixture files. The forge's form state carried a pronouns
    field and there was no input for it anywhere, so it defaulted, silently, every time.

    This screen asked for pronouns first and that was not enough, measured within the
    hour: the same character stood in front of a mirror and was given a man's chest in a
    paragraph written end to end in the second person, where no pronoun appears at all.
    So the question is what they *are*, and the pronouns follow from it."""
    _, problems = creation.build(spec(gender="", pronouns=""))
    assert any("woman or a man" in p for p in problems)

    built, problems = creation.build(spec(gender="woman", pronouns=""))
    assert problems == []
    assert built["sheet"]["gender"] == "woman"
    assert built["sheet"]["pronouns"] == "she/her"


def test_the_two_can_no_longer_disagree():
    """"the fact that they are uncoupled is probably a part of the problem. a woman should
    be referred to with the feminine pronouns and a man the masculine ones."

    Two fields meant a save could hold both answers at once — Thessaly's did, a woman with
    they/them beside her — and the narrator then had two sources to choose between."""
    built, _ = creation.build(spec(gender="man", pronouns="she/her"))
    assert built["sheet"]["pronouns"] == "he/him"


def test_a_set_written_on_a_sheet_before_this_still_reads_back():
    """Every character saved when the forge asked for pronouns says only that. she/her and
    he/him each answer the new question on their own, so nothing on the roster needs a
    migration to be understood — reading is not guessing."""
    built, problems = creation.build(spec(gender="", pronouns="he/him"))
    assert problems == []
    assert built["sheet"]["gender"] == "man" and built["sheet"]["pronouns"] == "he/him"


def test_only_two_are_offered_until_a_table_says_otherwise():
    """"male and female should be the only options default and we can add a way to
    create specific pronouns for fantasy/scify races, but should not be used unless
    assigned by the user or set as active in a world".

    A turned-on set is offered as a gender rather than as a second question, because it
    answers both at once — which is the whole reason the two were coupled."""
    from rules import houserules

    assert creation.options()["genders"] == ["woman", "man"]

    houserules.set_active({"pronoun_sets": ["ze/hir"]})
    try:
        assert creation.options()["genders"] == ["woman", "man", "ze/hir"]
        built, problems = creation.build(spec(gender="ze/hir"))
        assert problems == []
        assert built["sheet"]["pronouns"] == "ze/hir"
        assert built["sheet"]["gender"] == "ze/hir"
    finally:
        houserules.set_active({"pronoun_sets": []})


def test_a_gender_nothing_follows_from_is_refused():
    """"elf" says nothing about which words to use, and the forge must not invent a set
    for it — that is the guess the field exists to stop. The house rules are where a
    world adds one, and a set there says both things at once."""
    _, problems = creation.build(spec(gender="elf"))
    assert any("Nothing follows from" in p for p in problems)


def test_a_caster_may_not_walk_out_with_an_empty_spellbook():
    """Thessaly Corr again: a Wizard 1 with three level-0 and two level-1 slots, save DCs
    of 13 and 14, and no spells at all to put in them — 66 turns of a character who could
    not take her own turn. Only wizard, sorcerer and bard declare a cap; everybody else
    prepares from the class list and is never asked."""
    _, problems = creation.build(spec(
        **{"class": "wizard"}, race="human", bonus_ability="int",
        skills=["spellcraft"], feats=["toughness", "dodge"], spellbook=[]))
    assert any("begins knowing spells" in p for p in problems)

    _, problems = creation.build(spec(
        **{"class": "wizard"}, race="human", bonus_ability="int",
        skills=["spellcraft"], feats=["toughness", "dodge"],
        spellbook=creation.starter_spells("wizard")))
    assert problems == [], problems
    # A fighter is not a caster and is not nagged about it.
    assert creation.build(spec())[1] == []



def test_an_extravagant_homebrew_wealth_pays_its_average_instead_of_crashing():
    """A homebrew class declared starting_wealth "300d100 x 100 gp" and the uncaught
    BadDice came out of the forge as a 500 with every pick filled in. The author's
    extravagance is theirs to have; implausible dice pay their expected value."""
    purse = creation.starting_purse({"starting_wealth": "300d100 x 100 gp"})
    assert purse == {"gp": round(300 * 101 / 2) * 100}
    # Plausible wealth still rolls.
    rolled = creation.starting_purse({"starting_wealth": "5d6 x 10 gp"})
    assert 50 <= rolled["gp"] <= 300


def test_a_class_without_a_kit_starts_with_its_hands():
    """The old fallback was a dagger, and a Blood Bending player met it mid-fight: an
    opening attack with a knife they never chose and rightly said they were not
    carrying. No homebrew class has a dagger until somebody writes one down."""
    built, problems = creation.build(spec(**{"class": "blood bending",
                                             "paths": ["battle blood"],
                                             "skills": ["climb", "acrobatics"],
                                             "feats": ["toughness"]}))
    assert problems == []
    assert built["sheet"]["weapons"] == ["unarmed"]
    assert built["sheet"]["equipped"] == "unarmed"


# --- 2026-09-18: a feat the character has not earned --------------------------------------

def test_a_feat_whose_read_prerequisites_are_not_met_is_refused_with_the_fix_named():
    """Reported with a screenshot: "Toughness, great cleave" on a level-one sheet — "I am
    allowed to choose feats I don't meet the prerequisites for." Great Cleave wants Cleave,
    Power Attack and base attack +4; a first-level fighter has none of the three. The
    first version of this check warned instead of refusing, and read a `why` key `meets`
    never returned, so the warning named nothing."""
    _, problems = creation.build(spec(feats=["great cleave",
                                             {"id": "weapon-focus", "target": "longsword"}]))
    assert problems, "an unearned feat must be a refusal, not a warning"
    said = " ".join(problems)
    assert "Great Cleave requires" in said
    for need in ("Cleave", "Power Attack", "base attack bonus +4"):
        assert need in said, (need, said)


def test_a_feat_whose_prerequisites_are_met_still_builds():
    """Power Attack on a Str 16 fighter with base attack +1: read, met, no complaint."""
    built, problems = creation.build(spec())
    assert not problems and built["sheet"]
    assert not any("requires" in w for w in built["warnings"])
