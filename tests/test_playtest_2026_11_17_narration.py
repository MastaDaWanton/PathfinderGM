"""Narration, playtest 2026-11-17 (round 3 of that night) and the N-items of 2026-11-16.

Each test names the item and what the page said.
"""
from gm import narration
from tests.test_an_asked_question_is_answered import bar  # noqa: F401
from tests.test_law_and_services import quiet  # noqa: F401

PC = "Vesna Kroll"


def test_a_beast_the_tells_name_is_never_the_player():
    """Playtest 2026-11-17 #37: the travel tell read "A good wooden door leads to the
    beast's pool"; with only the smuggler in the scene the creature-noun swap took "the
    beast" for the player, and the page said "two stuck wooden doors lead to your pool"
    and "The roar of you in the pool echoes"."""
    tell = "A good wooden door leads to the beast's pool; it is stuck."
    text = ("Two stuck wooden doors lead to the beast's pool and the oubliette. "
            "The roar of the beast in the pool echoes faintly.")
    kept, beasts = narration.creature_nouns_for_pc(text, PC, True, grounded=tell)
    assert kept == text and beasts == []
    # Ungrounded, the old swap still runs (the 2026-09-18 asura case).
    swapped, beasts = narration.creature_nouns_for_pc(text, PC, True)
    assert beasts


def test_a_paid_cure_carries_no_stat_block_on_the_page(quiet):
    """Playtest 2026-11-17 #9 and 2026-11-16 N9: the temple's paid Cure Moderate Wounds
    landed on the story page as "casts Cure Moderate Wounds (caster level 3; Will half
    (harmless) (see text), DC 12; spell resistance yes (harmless) (see text);
    instantaneous)". A harmless spell offers its willing target no save; the book's
    cross-references are not the cast's."""
    from rules import services
    from tests.test_law_and_services import _priest
    from tests.test_ships_at_sea import _at_port

    scene, engine, pc = _at_port(gp=12)
    _priest(engine)
    pc.hp = max(1, pc.hp_max - 6)
    res = engine.run(engine.validate(
        [{"op": "buy", "actor": "pc", "because": "healing",
          "params": {"item": services.PREFIX + "cure-light-wounds"}}],
        origin="author:test"))
    tell = res.outcomes[0].tell
    assert "casts Cure Light Wounds (caster level 1; instantaneous)" in tell, tell
    assert "see text" not in tell and "harmless" not in tell, tell


def test_an_orphan_close_after_a_possessive_gets_no_runaway_marks():
    """Playtest 2026-11-17 #6: "the Burrowers'' Guild" on the page, and the 0.4.0 bench's
    "''''''''". A possessive ("Burrowers' Guild") paired with the line's opening mark, so
    the mark the orphan-close repair put in never paired, and each pass added another."""
    text = "We work for the Burrowers' Guild,' the mason says. Fine."
    assert narration.mend_orphan_close(text) == text
    # The repair it was built for still opens the line (2026-11-15 #71).
    lost = "Then silence is your defense. If you cannot find the words,' the sergeant says."
    assert narration.mend_orphan_close(lost) == (
        "Then silence is your defense. 'If you cannot find the words,' the sergeant says.")


def test_back_in_a_stocked_room_its_creature_is_in_the_tell(monkeypatch):
    """Playtest 2026-11-17 #27: she walked back into the turnkey's room by torchlight
    with the dire rat that had bitten her standing in it, and the arrival tell said only
    "The turnkey's room: a stool, a rack for keys, a slot in the door" — so the beat never
    mentioned the rat. The stocking's line is told on the first entry; a revisit said
    nobody."""
    from rules import dungeons
    from tests.test_dungeon_quest import _found_cave, _rooms, _run

    monkeypatch.setattr(dungeons, "chance", lambda *a, **k: 100)
    s, engine, head, _ = _found_cave()
    monkeypatch.setattr(type(s), "sees_nothing", lambda self, who: False)  # by torchlight
    first = next(r for r in _rooms(s, head) if r["dungeon"]["role"] == "entrance")
    s.pc().hp = s.pc().hp_max = 500
    _run(engine, "travel", {"place": first["id"]})
    if s.in_encounter:
        s.end_encounter()
    rat = engine._bring_in("dire rat", count=1)[0]["ref"]
    s.move(rat, first["id"])
    first["dungeon"].update(stocked=True, foes=[rat])
    _run(engine, "travel", {"place": head["id"]})
    tell = " ".join(o.tell for o in _run(engine, "travel", {"place": first["id"]}))
    assert "The dire rat is here." in tell, tell


def test_a_disabled_creatures_turn_is_told_it_stands():
    """Playtest 2026-11-17 #29: the dire rat at 0 hp, disabled ("still standing, but any
    real effort now costs blood"), was told only "conditions: disabled" on its own turn;
    it gave "it is too weak to stand" as its reason and the page said "The dire rat
    remains where it lies, its body slumped and motionless". CRB p.190: a disabled
    creature takes a move or a standard action."""
    from gm import prompts
    from tests.test_grapple_held import _scene

    s, e, rat = _scene(template="thug", name="Lila")
    rat.hp = 0
    rat.apply_hp_state()
    assert rat.has_state("state.impaired.disabled")
    note = prompts.stuck_note(rat)
    assert "still on their feet" in note and "not lying down" in note
    rat.hp = -1
    rat.apply_hp_state()
    assert "DISABLED" not in prompts.stuck_note(rat)


def test_the_strain_of_a_disabled_blow_is_told_after_it():
    """Playtest 2026-11-17 #30: the bite and the hit point it cost were fused, "lunges and
    snaps its teeth at you … remains unconscious and dying on the ground as it struggles
    to strike", from the tell "The effort costs dire rat a hit point … dire rat is
    unconscious and dying." The cost comes after the act (CRB p.190), and says so."""
    from tests.test_grapple_held import _scene

    s, e, rat = _scene(template="thug", name="Lila")
    rat.hp = 0
    rat.apply_hp_state()
    out = e.run(e.validate([{"op": "attack", "actor": rat.ref, "target": "pc",
                             "visibility": "hidden", "params": {}}],
                           origin=f"creature:{rat.from_template}"))
    strain = next(o for o in out.outcomes if o.op == "strain")
    assert strain.tell.startswith("Then, the act done, the effort costs Lila"), strain.tell


def test_a_body_left_dying_is_told_where_it_lies(monkeypatch):
    """Playtest 2026-11-17 #31: the walk's tell said "The dire rat stabilises where they
    lie", and the arrival in the cells was told "the hall of the cells, where the dire rat
    lies still on the ground" — the rat was dying back in the turnkey's room."""
    from rules import dungeons
    from tests.test_dungeon_quest import _found_cave, _rooms, _run

    monkeypatch.setattr(dungeons, "chance", lambda *a, **k: 100)
    s, engine, head, _ = _found_cave()
    s.pc().hp = s.pc().hp_max = 500
    rat = engine._bring_in("dire rat", count=1)[0]["ref"]
    if s.in_encounter:
        s.end_encounter()
    body = s.actors[rat]
    body.hp = -1
    body.apply_hp_state()
    assert body.has_state("state.down.dying")
    here = engine.here().name
    first = next(r for r in _rooms(s, head) if r["dungeon"]["role"] == "entrance")
    tell = " ".join(o.tell for o in _run(engine, "travel", {"place": first["id"]}))
    assert f", back in {here}." in tell, tell


def test_walking_on_with_the_man_you_talk_to_takes_no_leave_of_him():
    """Playtest 2026-11-17 #39: "I go to the broken pen, and the smuggler comes with me"
    was planned as a travel with c28, and the leave-by-deed rule took her leave of him
    first: "You take your leave of the starving smuggler." The page then wrote "leaving
    the starving smuggler behind" of the man walking beside her, and its repair was
    refused for breaking that tell."""
    from gm import judgement
    from tests.test_leave_by_deed import _inn

    s, e, keeper = _inn()
    read = {"actions": [{"act": "go", "place": "the cellar", "span": "go to the cellar"}]}
    raw = [{"op": "travel", "actor": "pc", "params": {"place": "the cellar",
                                                      "with": [keeper.ref]}}]
    assert [r["op"] for r in judgement.leave_before_leaving(raw, "", s, read)] == ["travel"]
    # Alone, the walk still takes its leave first (ruling 2026-10-17).
    alone = [{"op": "travel", "actor": "pc", "params": {"place": "the cellar"}}]
    assert [r["op"] for r in judgement.leave_before_leaving(alone, "", s, read)] == [
        "leave_talk", "travel"]


def test_a_take_from_a_chest_is_not_also_a_take_off():
    """Playtest 2026-11-17 #49: "I take the coin from the crew's cargo chest" was planned
    as take_off "cargo_chest_coins" beside the give the table built; the take-off
    resolved "Vesna Kroll is wearing nothing called cargo_chest_coins", got a fact slot
    of its own, and the page told the one take three times."""
    from gm import acts_to_ops
    from tests.test_leave_by_deed import _inn

    s, e, _keeper = _inn(talking=False)
    frame = {"question": False, "claims": [], "actions": [
        {"act": "take", "object": "the coin", "target": "the crew's cargo chest",
         "span": "take the coin from the crew's cargo chest"}]}
    give = {"op": "give", "actor": "pc", "params": {"item": "coin", "to": "pc",
                                                     "from_": "crew's cargo chest"}}
    rows = [acts_to_ops.Row(index=0, act="take", intents=[dict(give)])]
    raw = [{"op": "take_off", "actor": "pc", "params": {"item": "cargo_chest_coins"}},
           dict(give)]
    out = acts_to_ops.apply(raw, rows, frame, s, notes=[])
    assert [r["op"] for r in out] == ["give"], out
    # A take-off with an act of its own stands.
    frame["actions"].append({"act": "use", "object": "my shield",
                             "span": "take off my shield"})
    raw[0]["params"]["item"] = "shield"
    out = acts_to_ops.apply(raw, rows, frame, s, notes=[])
    assert "take_off" in [r["op"] for r in out], out


def test_a_pursuers_cut_lunge_leaves_the_pursuit_on_the_page():
    """Playtest 2026-11-16 N1: a pursuing dire rat's lunge was cut by the read-back as an
    unrolled blow at the player, and the page then never said the rat had come after her
    at all. The cut sentence's place takes the engine's half that is true."""
    from gm import beat_verify as bv
    from tests.test_struck_at_early import LUNGE, _facts

    walk = {"intent_id": "i1", "op": "travel", "status": "resolved", "actor": "pc",
            "effects": [{"kind": "biome", "pursued_by": ["c8"]}],
            "tell": "You are at the cellar now. The one behind the bar comes after you."}
    c = bv.Claim("at_you", {"who": "c8"}, "swinging the heavy sap", LUNGE, True)
    found = bv.diff([c], _facts((walk,)))
    assert found and found[0].line == "The one behind the bar comes after you.", found
    assert "has come after you" in found[0].fact
    # No pursuit, no line: the sentence simply goes, as before.
    assert bv.diff([c], _facts(()))[0].line == ""


def test_a_question_asked_before_walking_off_is_still_answered(bar):
    """Playtest 2026-11-16 N6: "I go up on deck, ask the deckhand what's in the hold, then
    go ashore and walk to the cathedral" chained the walk, and the deckhand's answer was
    dropped: a party that had moved asked nobody. Asked before a walk the reading puts
    after the asking, the person left behind answers, before the departure."""
    from types import SimpleNamespace

    gm, gorm, _calls, _reply = bar
    s = gm.engine.scene
    deck, shore = "ship~deck:the-deck", "town~urban:the-cathedral"
    gorm.at = deck
    s.at = shore
    gm._was_at = "ship~deck:below-decks"
    walk = SimpleNamespace(status="resolved", effects=[
        {"kind": "biome", "was_place": "ship~deck:below-decks", "place": deck},
        {"kind": "biome", "was_place": deck, "place": shore}])
    said = "I go up on deck, ask Gorm what's in the hold, then walk to the cathedral."
    gm.reading = {"question": False, "actions": [
        {"act": "go", "place": "deck", "span": "go up on deck"},
        {"act": "talk", "target": "Gorm", "says": "what's in the hold",
         "span": "ask Gorm what's in the hold"},
        {"act": "go", "place": "the cathedral", "span": "walk to the cathedral"}]}
    assert gorm.ref not in s.actors
    assert gm._who_was_asked(said, [walk]) is gorm
    # Asked where they arrived (no walk after the asking): not this door's.
    gm.reading["actions"] = gm.reading["actions"][:2]
    assert gm._who_was_asked(said, [walk]) is None


def test_a_towns_strain_does_not_reach_a_cell_under_it():
    """Playtest 2026-11-17 #35: in a dungeon cell under the town the page read "The
    heavy, oppressive silence of the underground feels weighted by the whispered rumors of
    the bribes and backroom deals … fueling the rivalry between the local lords": a
    settlement-wide strain with nobody there to have heard it. In the streets it stands."""
    from rules import cards
    from rules.engine import Scene

    strain = cards.Card(id="strain-1", title="The rivalry between the local lords",
                        facts=["Bribes and backroom deals fuel it."])
    assert cards.standing(strain) == cards.SITUATION
    s = Scene(location_id="7ef5e373c993")
    s.at = "7ef5e373c993~underground:the-gardens/the-sewers/the-cells"
    assert cards._pull_one(s, strain, ("near",), player_text="", turn=10, world=None) is None
    s.at = "7ef5e373c993~urban:the-market"
    assert cards._pull_one(s, strain, ("near",), player_text="", turn=10,
                           world=None) is not None
