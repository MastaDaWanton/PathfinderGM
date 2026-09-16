"""Somebody behind the counter (`rules/keepers.py`).

The defect, measured 2026-09-16 on the shipped Pangrella export: the party walked into
the market of a town of eleven thousand people and `scene.actors` held one creature —
the player. Twenty-five of the forty-two kinds of settlement place sell something or do
something for money, `rules/places.STAFFED` had named who ought to be standing in each
since the table was written, and nothing built one of them. Whatever served the player
was a sentence the narrator improvised and forgot: no numbers, no name the world uses,
and gone by the next beat.

What is checked here is the four things a keeper has to be, because a shopkeeper that is
only the first of them is the improvised sentence again:

  * **there** — in `Scene.people`, at their own place, so the brief names them;
  * **named out of the world** — the settlement's own families, the world's own given
    names, never a model and never a name the world already gave somebody else;
  * **the same person next time** — seeded off the place id, so no session mints a
    different smith, and remembered in the codex so the numbers do not move either;
  * **mortal** — a keeper who is killed stays killed. The scene remembers which counters
    have been staffed rather than looking to see whether anybody is standing at one,
    because the body is swept out two turns later and the look would cheerfully mint the
    murdered smith again.

Measured while choosing the role words: 23 of the 25 find a real stat block in the
codex, and 2 — the workshops and the warehouses — fall to the hand-written `guildhand`,
which is the right person for both and is why the floor exists.
"""
from __future__ import annotations

import pytest

from rules import keepers, npcs, places
from rules.dice import Dice
from rules.engine import Engine, Scene
from rules.sheet import load_pc
from world import loader

WORLD = loader.load_cached("fixtures/pangrella-campaign.json")
TOWN = "5bbd0c40345f"
MARKET = f"{TOWN}~urban:the-market"
GUILDHALL = f"{TOWN}~urban:the-guildhall"
GATE = f"{TOWN}~urban:the-gate"


def _table(at: str = MARKET, world=WORLD, seed: int = 3):
    scene = Scene(location_id=TOWN)
    scene.add(load_pc("fixtures/pc-kesst.json"))
    engine = Engine(scene, Dice(seed=seed), world=world)
    engine.place_party(at)
    return scene, engine


def _keeper(scene, at: str):
    return keepers.keeper_in(scene, at)


# --- there ----------------------------------------------------------------------------------

def test_the_market_has_somebody_in_it():
    """The measurement. One creature in the room, and it was the player."""
    scene, _ = _table(MARKET)
    who = _keeper(scene, MARKET)
    assert who is not None, [a.name for a in scene.actors.values()]
    assert who.at == MARKET
    assert who.ref in scene.actors, "the keeper is not in the party's own view"


def test_a_place_that_sells_nothing_gets_nobody():
    """A keeper for every room would put a person in every empty street. The gate is
    watched by the guardhouse, not manned by a shopkeeper."""
    scene, _ = _table(GATE)
    assert _keeper(scene, GATE) is None
    assert [a.name for a in scene.actors.values() if not a.is_pc] == []


def test_the_keeper_is_what_the_place_says_they_are():
    """`STAFFED` names one person per place and the note is what the narrator reads."""
    scene, _ = _table(GUILDHALL)
    who = _keeper(scene, GUILDHALL)
    assert who is not None
    assert "clerk of the guild" in who.notes.lower(), who.notes
    assert "guildhall" in who.notes.lower(), who.notes


def test_walking_out_leaves_them_standing_in_their_own_shop():
    """A keeper belongs to the place, not to the party: they stay in the store, out of
    the view, and are still there on the way back. The defect this prevents is the
    opposite of a vanishing NPC — an NPC who follows you home."""
    scene, engine = _table(MARKET)
    who = _keeper(scene, MARKET)
    engine.place_party(GUILDHALL)
    assert who.ref not in scene.actors, "the stallholder came along"
    assert who.ref in scene.people and who.at == MARKET
    engine.place_party(MARKET)
    assert who.ref in scene.actors


def test_a_keeper_at_their_own_counter_is_not_left_behind():
    """Measured the first time this ran end to end: travelling out of the market said
    "Left behind: Gorvothys Vyrnys", which reads as an abandoned companion. She is at
    her own stall; the party is the one who left."""
    scene, engine = _table(MARKET)
    who = _keeper(scene, MARKET)
    intents = engine.validate(
        [{"op": "travel", "actor": "pc", "because": "t", "params": {"place": "the guildhall"}}],
        origin="author:test")
    tell = engine.run(intents).outcomes[-1].tell
    assert who.name not in tell, tell
    assert "guildhall" in tell.lower()


def test_travel_stands_up_the_keeper_of_the_room_walked_into():
    """The other door. `place_party` is placement; a travel is how a player actually
    crosses a town, and a room staffed only on placement would be empty every time it
    was walked to."""
    scene, engine = _table(MARKET)
    intents = engine.validate(
        [{"op": "travel", "actor": "pc", "because": "t", "params": {"place": "the guildhall"}}],
        origin="author:test")
    engine.run(intents)
    assert _keeper(scene, GUILDHALL) is not None


# --- named out of the world -------------------------------------------------------------------

def test_the_name_comes_out_of_the_world_and_not_out_of_nowhere():
    """"Ground every name" — the family is one of the settlement's own and the given
    name is one the export actually uses. An invented name is a person the world does
    not contain, which is the failure this whole app is built around avoiding."""
    scene, _ = _table(MARKET)
    who = _keeper(scene, MARKET)
    given, families, _taken = keepers.name_stock(WORLD, TOWN)
    first, last = who.name.split()[0], who.name.split()[-1]
    assert first in given, (who.name, given[:8])
    assert last in families, (who.name, families)


def test_no_keeper_wears_a_name_the_world_already_gave_somebody():
    """Two people of one name in one town is a ghost as far as the player is concerned,
    and the cast is the half of it this app did not write."""
    _given, _fam, taken = keepers.name_stock(WORLD, TOWN)
    scene, engine = _table(MARKET)
    for place in engine.places():
        engine.place_party(place.id)
    minted = [a.name.lower() for a in scene.people.values() if keepers.is_keeper(
        getattr(a, "world_entity_id", "") or "")]
    assert minted, "nobody was staffed anywhere in the town"
    assert not (set(minted) & taken), set(minted) & taken
    assert len(set(minted)) == len(minted), sorted(minted)


def test_a_world_with_no_names_to_lend_gets_a_keeper_called_what_they_are():
    """Every world-less engine in the suite, and any export that ships no cast. A
    keeper with no name is still a keeper; one with an invented name is not."""
    scene, _ = _table(MARKET, world=None)
    who = _keeper(scene, MARKET)
    assert who is not None
    assert who.name == places.keeper_of("the market")[0]


# --- the same person next time ------------------------------------------------------------------

def test_the_same_shop_has_the_same_keeper_in_a_new_campaign():
    """Seeded off the place id like the floor plan, and for the same reason: the smith
    the party met last week is the smith they meet this week, without anything being
    stored that could drift from the rule that made it."""
    names = []
    for seed in (1, 2, 3):
        scene, _ = _table(MARKET, seed=seed)
        names.append(_keeper(scene, MARKET).name)
    assert len(set(names)) == 1, names


def test_two_shops_in_one_town_are_two_different_people():
    scene, engine = _table(MARKET)
    engine.place_party(GUILDHALL)
    assert _keeper(scene, MARKET).name != _keeper(scene, GUILDHALL).name


def test_the_numbers_come_from_the_codex_and_are_remembered(tmp_path, settings):
    """A keeper is a person the codex chose, filed under their own id, so their numbers
    are the same next session and one file on the NPCs bench corrects them
    (docs/npc-codex.md). The id is stamped `keeper:` because World Bible did not write
    this person and nothing should mistake them for cast."""
    settings.CAMPAIGN_DIR = tmp_path
    scene, _ = _table(MARKET)
    who = _keeper(scene, MARKET)
    wid = keepers.entity_id(MARKET)
    assert who.world_entity_id == wid
    known = npcs.recall(wid)
    assert known is not None, "nothing was written to the codex"
    assert known["creature"] == who.from_template
    assert known["name"] == who.name


def test_a_keeper_is_never_stood_up_twice():
    """Placement happens on every load. Fifty reloads, one smith."""
    scene, engine = _table(MARKET)
    for _ in range(4):
        engine.place_party(MARKET)
    at_market = [a for a in scene.people.values()
                 if keepers.place_of(getattr(a, "world_entity_id", "") or "") == MARKET]
    assert len(at_market) == 1, [a.name for a in at_market]


def test_nobody_is_staffed_into_a_running_fight():
    """The party did not walk in; they are already in the middle of something, and a
    stallholder strolling out to serve them mid-round is a body in an initiative order
    nobody asked for."""
    scene, engine = _table(GATE)
    scene.staffed.clear()
    engine.place_party(GATE)
    scene.round = 1
    scene.initiative = [("pc", 12)]
    scene.turn = 0
    assert scene.in_encounter
    engine.place_party(MARKET)
    assert _keeper(scene, MARKET) is None


# --- mortal ------------------------------------------------------------------------------------

def test_a_keeper_who_is_gone_is_gone():
    """The murdered smith. `tidy_the_fallen` sweeps a body out of the scene two turns
    after it falls, so "is anybody standing here?" is not a question the mint may ask —
    it would answer "no" and put a new smith behind the counter of a shop whose keeper
    the party killed this morning. The ledger is the counter, not the person."""
    scene, engine = _table(MARKET)
    who = _keeper(scene, MARKET)
    scene.depart(who.ref)
    engine.place_party(GUILDHALL)
    engine.place_party(MARKET)
    assert _keeper(scene, MARKET) is None
    assert MARKET in scene.staffed


def test_the_ledger_survives_a_save(tmp_path, settings):
    """And it has to be written down, or the reload is the resurrection."""
    from play import campaign as cm

    settings.CAMPAIGN_DIR = tmp_path
    scene, _ = _table(MARKET)
    saved = {"staffed": list(scene.staffed)}
    assert saved["staffed"] == [MARKET]
    # The round trip the campaign actually performs.
    c = cm.Campaign(id="keepers-test", world_source="fixtures/pangrella-campaign.json",
                    scene=scene)
    c.save()
    back = cm.Campaign.load(c.path())
    assert back.scene.staffed == [MARKET]


# --- the counter the player actually clicks ----------------------------------------------------

def test_the_trade_panel_opens_across_the_keeper_of_a_shop(tmp_path):
    """The path the player clicks, which is the one that was broken.

    `play/views._merchant_here` gates the trade button on the actor's NAME matching
    merchant words — "the stallholder", "a vendor". A keeper is named out of the world
    on purpose, so "Gorvothys Vyrnys" matched nothing and the panel answered "there is
    nobody here to trade with" with the shopkeeper standing in front of the player.
    Building the person and leaving the button blind is the same defect this whole run
    of work keeps finding: a feature described and not delivered.
    """
    import json as _json

    from django.test import Client, override_settings

    from play import campaign as cm
    from play.views import _merchant_here

    with override_settings(CAMPAIGN_DIR=tmp_path / "campaigns"):
        cm._LIVE.clear()
        c = cm.begin_with(load_pc("fixtures/pc-kesst.json"))
        c.scene.location_id = TOWN
        c.engine().place_party(MARKET)
        c.save()
        who = _keeper(c.scene, MARKET)
        assert who is not None
        assert _merchant_here(c.scene) is who, "the counter cannot see its own keeper"
        r = Client().post("/api/trade", data="{}", content_type="application/json")
        assert r.status_code == 200, r.content
        assert Client().get("/api/state").json()["merchant"] == who.name
        cm._LIVE.clear()


def test_the_panel_stays_shut_where_nobody_sells_anything(tmp_path):
    """A gaoler keeps a room too. The trade category is what opens a counter, not the
    fact that somebody is standing there — CircleMUD's shop file names the rooms its
    keeper may sell in for the same reason."""
    from django.test import Client, override_settings

    from play import campaign as cm
    from play.views import _merchant_here

    with override_settings(CAMPAIGN_DIR=tmp_path / "campaigns"):
        cm._LIVE.clear()
        c = cm.begin_with(load_pc("fixtures/pc-kesst.json"))
        c.scene.location_id = TOWN
        c.engine().place_party(GUILDHALL)
        c.save()
        assert _keeper(c.scene, GUILDHALL) is not None, "the guildhall has no clerk"
        assert _merchant_here(c.scene) is None
        r = Client().post("/api/trade", data="{}", content_type="application/json")
        assert r.status_code == 409
        cm._LIVE.clear()


def test_a_keeper_away_from_their_counter_is_not_a_shop():
    """"so trans'ed shopkeepers can't sell in the desert" — the CircleMUD shop file
    names the rooms a keeper works in, and a smith on the road is not a smithy."""
    scene, engine = _table(MARKET)
    who = _keeper(scene, MARKET)
    assert keepers.keeps_a_counter(who)
    who.at = GATE
    assert not keepers.keeps_a_counter(who)


# --- the table itself -----------------------------------------------------------------------

def test_every_staffed_place_names_one_person_and_the_words_to_find_them():
    """Three fields with three jobs: the ledger's prose, the one person the engine
    stands up, and what the codex is asked for."""
    for label, row in places.STAFFED.items():
        who, title, words = row
        assert who and title and words, label
        assert title.startswith("the "), f"{label}: {title!r} is not a person"
        assert all(w == w.lower() and " " not in w for w in words), (label, words)


def test_the_codex_has_somebody_for_almost_every_counter():
    """Measured 2026-09-16: 23 of 25 find a real block; the workshops and the
    warehouses fall to the hand-written `guildhand`, which is what a guild hand is. A
    third falling through would mean the words had drifted from the index."""
    floors = [label for label, (_w, _t, words) in places.STAFFED.items()
              if (npcs.choose(list(words), 3) or {}).get("floor")]
    assert len(floors) <= 2, floors


@pytest.mark.parametrize("label", sorted(places.STAFFED))
def test_no_keeper_is_a_fight_the_party_cannot_have(label):
    """A shopkeeper is a person, not an encounter. The chooser's own band is CR
    level-1 ± 3 (`npcs.MAX_DISTANCE`); this pins that a keeper is inside it rather
    than a story block that happens to share a word."""
    got = npcs.choose(list(places.STAFFED[label][2]), 1) or {}
    cr = got.get("cr_value")
    assert cr is None or cr <= npcs.target_cr(1) + npcs.MAX_DISTANCE, (label, got.get("name"), cr)
