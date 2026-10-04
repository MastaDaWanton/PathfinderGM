"""Keepers go by their descriptor until introduced (owner ruling F1, 2026-09-30).

Measured on the 2026-09-30 playtest (docs/playtest-2026-09-30-findings.md item 7): **4 of 4
keepers were shown by full name before any introduction** — Oren Bramble, Soren Moorcock,
Gorm Vesper and Quin Nutmeg — because `keepers._mint` (2026-09-19) set `name = true_name`.
The page then named 2 of them unprompted; Gorm was even made to say "Others, like Gorm
Vesper, require a heavy purse" about somebody else. Every other person the scene makes has
kept their name back since 2026-09-18 (the brief's "The true name is NOT shown").

Evennia's RP system is the precedent: a character is shown by its sdesc until the viewer
`recog`s them. Here the descriptor is `name`, the name is `true_name`, and the ordinary
introduction machinery (`names_asked_for`, `apply_introductions`) carries a keeper exactly
as it carries a stranger. The one exception is the world's: a keeper it marks as publicly
known (`keepers.publicly_known`).
"""
from __future__ import annotations

from types import SimpleNamespace

from gm import judgement
from rules import keepers, places
from rules.dice import Dice
from rules.engine import Engine, Scene
from rules.sheet import load_pc
from world import loader

WORLD = loader.load_cached("fixtures/aurvantis-campaign.json")
LEDGERWARREN = WORLD.by_name("Ledgerwarren", kind="CITY").id
MARKET = f"{LEDGERWARREN}~urban:the-market"
GATE = f"{LEDGERWARREN}~urban:the-gate"


def _table(at: str = MARKET, world=WORLD):
    scene = Scene(location_id=LEDGERWARREN)
    scene.add(load_pc("fixtures/pc-kesst.json"))
    engine = Engine(scene, Dice(seed=3), world=world)
    engine.place_party(at)
    return scene, engine


def _run(e, plan):
    return e.run(e.validate(plan, origin="author:test"))


def _tavern(engine):
    """The Velvet Veil, founded off the gate as Sam founded it, and walked into."""
    _run(engine, [{"op": "found", "because": "t",
                   "params": {"name": "the Velvet Veil", "parent": "the gate",
                              "kind": "tavern"}}])
    veil = places.find(engine.places(), "the Velvet Veil")
    _run(engine, [{"op": "travel", "because": "t", "params": {"place": veil.id}}])
    return veil.id


def _keepers(scene):
    return [a for a in scene.people.values()
            if keepers.is_keeper(str(a.world_entity_id or ""))]


def test_no_keeper_is_shown_by_name_before_introduction():
    """4 of 4 keepers shown by full name before any introduction (Sam's save). Now: the
    market's master and its general store, and the tavern's barkeep, all go by what they
    are, and every one of them still holds a name from the world to give."""
    scene, engine = _table(MARKET)
    engine.place_party(GATE)
    _tavern(engine)
    held = _keepers(scene)
    assert len(held) == 3, [a.name for a in held]
    for k in held:
        assert k.true_name and len(k.true_name.split()) == 2, k.true_name
        assert k.name != k.true_name, f"{k.ref} is shown as {k.name!r}"
        assert k.name.startswith("the "), k.name
        assert k.true_name.split()[0] not in k.name
        assert k.true_name.split()[-1] not in (k.notes or ""), k.notes
    names = {k.name for k in held}
    assert "the master of the market" in names
    assert "the one behind the bar" in names


def test_asked_their_name_a_keeper_gives_it_and_the_panel_learns_it():
    scene, engine = _table(GATE)
    _tavern(engine)
    barkeep = next(a for a in _keepers(scene) if a.at == scene.at)
    asked = judgement.names_asked_for(scene, "What's your name, barkeep?")
    assert asked == {barkeep.ref: barkeep.true_name}
    given = barkeep.true_name
    beat = f"He sets the tankard down. \"{given},\" he says. \"And you are?\""
    from play.aftermath import seen_people
    from tests.beat_reader import stub

    reading = stub.read(beat, scene, names={barkeep.ref: given})
    seen_people.name_them(stub.ctx(scene, reading, text=beat), reading)
    assert barkeep.name == given


def test_a_name_asked_for_and_narrated_is_learned():
    """Live, 2026-09-30, on a copy of Sam's save: "What's your name, sergeant?" — the page
    wrote "The sergeant's name is Caspian Tidestone." in narration, and the panel kept
    "the sergeant of the watch". The asked name on the page is learned however it is
    carried (`play/aftermath/name_given.py`); not asked, it is not."""
    from play.aftermath import name_given

    scene, engine = _table(GATE)
    _tavern(engine)
    barkeep = next(a for a in _keepers(scene) if a.at == scene.at)
    given = barkeep.true_name
    beat = f"The barkeep's name is {given}. He goes back to his tankards."

    def ctx(player_text):
        return SimpleNamespace(scene=scene, text=beat, player_text=player_text)

    assert name_given.step(ctx("I order an ale.")) == []
    assert barkeep.name == "the one behind the bar"
    rows = name_given.step(ctx("What's your name, barkeep?"))
    assert rows == [{"kind": "name-given", "ref": barkeep.ref,
                     "was": "the one behind the bar", "name": given}]
    assert barkeep.name == given


def test_a_keeper_the_world_marks_as_publicly_known_is_named_on_sight():
    """The exception F1 keeps: the name over the shop. Read from the world's own
    `play.places[]` row (``keeper: {name, known: "publicly"}``) or a cast member who
    `keeps` the place; a name with no public marking is not public."""
    play = dict(WORLD.play)
    rows = [dict(r) for r in play.get("places") or []]
    for r in rows:
        if r.get("id") == MARKET:
            r["keeper"] = {"name": "Hal Dunmore", "known": "publicly"}
    play["places"] = rows
    marked = SimpleNamespace(play=play)
    assert keepers.publicly_known(marked, MARKET, keepers.entity_id(MARKET)) == "Hal Dunmore"
    assert keepers.publicly_known(WORLD, MARKET, keepers.entity_id(MARKET)) == ""
    rows2 = [dict(r, keeper={"name": "Hal Dunmore"}) if r.get("id") == MARKET else r
             for r in WORLD.play.get("places") or []]
    unmarked = SimpleNamespace(play=dict(WORLD.play, places=rows2))
    assert keepers.publicly_known(unmarked, MARKET, keepers.entity_id(MARKET)) == ""
    cast = SimpleNamespace(play={"cast": [{"name": "Ula Penn", "keeps": MARKET,
                                           "known": "publicly"}]})
    assert keepers.publicly_known(cast, MARKET, keepers.entity_id(MARKET)) == "Ula Penn"


def test_kinship_names_nobody_by_a_name_not_yet_given():
    """The kin note read the family off the shown name and printed the other keeper's
    full name. With names kept back it reads the true name and prints the descriptor."""
    a = SimpleNamespace(name="the one behind the bar", true_name="Gorm Vesper", at="x",
                        world_entity_id="keeper:T~urban:the-tavern")
    b = SimpleNamespace(name="the master of the market", true_name="Oren Vesper",
                        world_entity_id="keeper:T~urban:the-market")
    scene = SimpleNamespace(people={"c1": a, "c2": b})
    note = keepers.kin_note(scene, a, "T~urban:the-tavern")
    assert "the master of the market" in note
    assert "Vesper" not in note and "Oren" not in note


# --- an older save ---------------------------------------------------------------------------

def _named_on_sight(scene, engine):
    for k in _keepers(scene):
        k.name = k.true_name
    return {k.true_name: k for k in _keepers(scene)}


def test_an_old_save_takes_back_a_name_the_page_never_used():
    """Sam's save, measured: Oren Bramble and Soren Moorcock appear in none of its 82
    transcript entries; Gorm Vesper and Quin Nutmeg were on the page (from the leaked
    brief). A name never on the page goes back to the descriptor; a name the player has
    read is kept — taking it back would contradict the page they read."""
    scene, engine = _table(MARKET)
    engine.place_party(GATE)
    _tavern(engine)
    by_name = _named_on_sight(scene, engine)
    barkeep = next(k for k in by_name.values() if k.name and "market" not in
                   str(k.world_entity_id))
    transcript = [{"who": "gm", "text": "The market is loud."},
                  {"who": "gm", "text": f"Behind the counter, {barkeep.true_name} polishes "
                                        f"a tankard."}]
    done = dict(keepers.unname_on_sight(scene, WORLD, transcript))
    assert done[barkeep.ref] == "kept" and barkeep.name == barkeep.true_name
    restored = [k for k in by_name.values() if k is not barkeep]
    assert len(restored) == 2
    for k in restored:
        assert done[k.ref] == "restored"
        assert k.name.startswith("the ") and k.true_name.split()[0] not in k.name
    # A second load changes nothing.
    assert dict(keepers.unname_on_sight(scene, WORLD, transcript)) == {barkeep.ref: "kept"}


def test_the_given_name_alone_on_the_page_keeps_it():
    """"Gorm's hand pauses on the tankard" — the given name is the name on the page."""
    assert keepers._on_the_page("Gorm Vesper", [{"text": "Gorm's hand pauses."}])
    assert not keepers._on_the_page("Gorm Vesper", [{"text": "The gormless guard."}])
