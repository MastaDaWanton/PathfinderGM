"""Making three thousand spells castable.

`content/spells/` has held 3,040 spells since they were indexed, and nothing could use one.
The wizard and the cleric shipped as a d6 and a d8 with a skill list and no magic at all,
which made half the Core Rulebook's classes unplayable in an app about playing Pathfinder.

**The boundary this file is really about.** The engine owns everything derivable from the
sheet and the spell's structured fields — slots, caster level, save DC, whether this caster
may cast this spell at all — and it owns those completely. It does *not* own what a spell
does. That lives in the spell's prose, and a parser guessing mechanics out of three thousand
English paragraphs would produce confident wrong numbers, which is the failure this project
has been bitten by most. The `cast` outcome states the facts; any damage or condition that
follows arrives as its own validated intent.

The measurement that mattered most while building this: a rogue was issued spell slots.
`data.get("progression", "full")` reads "full" off an empty dict, so every non-caster in the
game got the wizard's table. It was caught by a resource test noticing an extra pool, not by
anything looking at casting.
"""
from __future__ import annotations

import pytest

from rules import casting, spells as spells_mod
from rules.bestiary import instantiate
from rules.dice import Dice
from rules.engine import Engine, Scene
from rules.intents import IntentError
from rules.sheet import from_dict, full_sheet, load_pc, to_dict


def wizard(level=5, int_score=18, book=("magic-missile", "fireball", "sleep",
                                        "mage-armor"),
           prepared=None):
    d = to_dict(load_pc("fixtures/pc-kesst.json"))
    d.update({"class": "wizard", "level": level, "ranks": {}})
    d["abilities"]["int"] = int_score
    d["spellbook"] = list(book)
    # `prepared or {...}` was the first version and it is wrong in the way CLAUDE.md warns
    # about: an explicitly empty dict is falsy, so every test asking for a wizard with
    # nothing prepared silently got the default three spells instead.
    d["prepared"] = dict({"magic-missile": 2, "fireball": 1, "sleep": 1}
                         if prepared is None else prepared)
    return from_dict(d, ref="pc")


def table(caster):
    s = Scene(location_id="5bbd0c40345f")
    s.add(caster)
    s.add(instantiate("thug", scene=s, name="the thug"))
    return s, Engine(s, Dice(seed=5))


def cast(engine, spell, at="c1"):
    return engine.run(engine.validate([
        {"op": "cast", "actor": "pc", "because": "she speaks the word",
         "params": {"spell": spell, "at": at}}]))


# --- who casts ---------------------------------------------------------------------------

def test_a_rogue_is_not_issued_spell_slots():
    """The bug this file opens with. `data.get("progression", "full")` on an empty dict
    answers "full", so every fighter and rogue in the game was handed the wizard's table —
    and it surfaced as an unrelated resource test noticing a stray pool."""
    rogue = load_pc("fixtures/pc-kesst.json")
    assert not casting.is_caster(rogue)
    assert casting.slots_for(rogue) == {}
    assert casting.highest_spell_level(rogue) == 0
    assert not [p for p in rogue.pools if "spell slot" in p]


def test_a_wizard_is():
    w = wizard()
    assert casting.is_caster(w)
    assert casting.casting_ability(w) == "int"
    assert casting.caster_level(w) == 5


def test_the_sheet_says_nothing_rather_than_nothing_prepared_for_a_fighter():
    """None, not an empty structure. "Does not cast" and "casts nothing today" look
    identical on a page and are not the same fact."""
    assert full_sheet(load_pc("fixtures/pc-kesst.json"))["spells"] is None
    assert full_sheet(wizard())["spells"] is not None


# --- slots -------------------------------------------------------------------------------

def test_the_slot_table_is_the_books():
    """Typed rather than derived: 0-level slots stop at 4, and the first slot of each new
    spell level arrives on its own schedule. Every attempt to generate this table is right
    for eight levels and wrong for the rest."""
    assert casting.FULL_CASTER[0] == [3, 1, 0, 0, 0, 0, 0, 0, 0, 0]
    assert casting.FULL_CASTER[4] == [4, 3, 2, 1, 0, 0, 0, 0, 0, 0]
    assert casting.FULL_CASTER[19] == [4] * 10


def test_a_high_ability_buys_bonus_slots():
    """"one bonus spell of a given level if your ability modifier is at least equal to
    that level, plus one more for every four points beyond"."""
    assert casting.bonus_slots(1, 1) == 1                # Int 12
    assert casting.bonus_slots(1, 2) == 0
    assert casting.bonus_slots(5, 1) == 2                # Int 20
    assert casting.bonus_slots(5, 5) == 1


def test_zero_level_slots_never_get_a_bonus():
    assert casting.bonus_slots(9, 0) == 0


def test_a_level_five_wizard_with_intelligence_eighteen():
    """Base [4,3,2,1] plus a +4 modifier's bonus at levels 1, 2 and 3."""
    assert casting.slots_for(wizard(5, 18)) == {0: 4, 1: 4, 2: 3, 3: 2}


def test_a_bonus_slot_never_grants_a_level_you_cannot_reach():
    """1e grants bonus spells for levels you already have access to. A high Intelligence
    does not let a 1st-level wizard cast fireball."""
    w = wizard(1, 20)
    assert casting.highest_spell_level(w) == 1
    assert set(casting.slots_for(w)) == {0, 1}


def test_a_low_casting_ability_caps_the_spell_levels_outright():
    """"To cast a spell, you must have an ability score of at least 10 + the spell level."
    A wizard with Intelligence 11 never casts a 2nd-level spell however high they get."""
    w = wizard(5, 11)
    assert casting.slots_for(w) == {0: 4, 1: 3}
    assert not casting.can_cast_level(w, 2)


def test_slots_are_ordinary_pools():
    """So they refresh on a night, survive a save and show on the sheet with no second
    mechanism for any of it."""
    w = wizard()
    assert w.pool("spell slot 3").maximum == 2
    assert w.pool("spell slot 3").refresh == "rest.night"


def test_slots_survive_a_save_half_spent():
    w = wizard()
    w.spend_pool("spell slot 1", 3)
    back = from_dict(to_dict(w), ref="pc")
    assert back.pool("spell slot 1").current == 1
    assert back.pool("spell slot 1").maximum == 4


def test_a_night_refills_them():
    w = wizard()
    w.spend_pool("spell slot 3", 2)
    w.refresh_pools("rest.night")
    assert casting.slots_left(w, 3) == 2


# --- the save DC -------------------------------------------------------------------------

def test_the_dc_is_ten_plus_level_plus_the_ability():
    w = wizard(5, 18)
    assert casting.save_dc(w, 3) == 17                   # 10 + 3 + 4
    assert casting.save_dc(w, 0) == 14


def test_the_dc_uses_the_level_on_this_casters_own_list():
    """Hold person is 2nd for a cleric and 3rd for a wizard. Using the lowest level on any
    list would quietly make every wizard's DCs a point light."""
    spell = spells_mod.get("hold-person")
    assert casting.level_on_list(spell, "cleric") == 2
    assert casting.level_on_list(spell, "wizard") == 3
    assert casting.spell_level_for(wizard(), spell) == 3


# --- casting ---------------------------------------------------------------------------------

def test_casting_spends_the_slot():
    w = wizard()
    _, e = table(w)
    before = casting.slots_left(w, 3)
    cast(e, "fireball")
    assert casting.slots_left(w, 3) == before - 1


def test_casting_spends_the_preparation_too():
    """A prepared caster's slot holds one named spell. Spending the slot and leaving the
    preparation would let a wizard cast the same fireball out of every slot they own."""
    w = wizard(prepared={"magic-missile": 2})
    _, e = table(w)
    cast(e, "magic-missile")
    assert casting.prepared_count(w, "magic-missile") == 1


def test_the_tell_carries_the_numbers_a_player_needs():
    w = wizard()
    _, e = table(w)
    tell = cast(e, "fireball").outcomes[0].tell
    assert "casts Fireball" in tell
    assert "caster level 5" in tell
    assert "DC 17" in tell
    assert "Reflex half" in tell


def test_a_spell_with_no_save_does_not_invent_one():
    """Magic missile has no saving throw. Printing "DC 17" beside it is the engine
    inventing a mechanic."""
    w = wizard()
    _, e = table(w)
    assert "DC" not in cast(e, "magic-missile").outcomes[0].tell


def test_the_outcome_states_the_facts_and_not_the_damage():
    """The boundary. The engine will not read "1d6 per caster level" out of English prose
    and turn it into a number — anything mechanical arrives as its own validated intent."""
    w = wizard()
    _, e = table(w)
    effect = cast(e, "fireball").outcomes[0].effects[0]
    assert effect["dc"] == 17 and effect["caster_level"] == 5
    assert effect["save"] == "Reflex half"
    assert "damage" not in effect
    assert "amount" not in effect


# --- what casting refuses -------------------------------------------------------------------

def test_a_non_caster_cannot_cast():
    s, e = table(load_pc("fixtures/pc-kesst.json"))
    with pytest.raises(IntentError, match="does not cast spells"):
        e.validate([{"op": "cast", "actor": "pc", "params": {"spell": "fireball"}}])


def test_a_spell_off_your_list_is_refused_by_name():
    """A rejection the model cannot act on costs a whole regeneration, so it says which
    list."""
    _, e = table(wizard())
    with pytest.raises(IntentError, match="not on the wizard list"):
        e.validate([{"op": "cast", "actor": "pc",
                     "params": {"spell": "cure-light-wounds"}}])


def test_a_spell_past_your_level_is_refused_with_both_numbers():
    _, e = table(wizard())
    with pytest.raises(IntentError, match="level 9 spell.*they reach level 3"):
        e.validate([{"op": "cast", "actor": "pc", "params": {"spell": "wish"}}])


def test_a_spell_not_in_the_book_is_refused():
    _, e = table(wizard(book=("magic-missile",), prepared={"magic-missile": 1}))
    with pytest.raises(IntentError, match="not in .* spellbook"):
        e.validate([{"op": "cast", "actor": "pc", "params": {"spell": "fireball"}}])


def test_a_spell_in_the_book_but_never_prepared_is_refused():
    """The whole point of a prepared caster. Without this the spellbook is the spell list
    and the wizard is a sorcerer."""
    _, e = table(wizard(prepared={"fireball": 1}))
    with pytest.raises(IntentError, match="did not prepare Mage Armor"):
        e.validate([{"op": "cast", "actor": "pc", "params": {"spell": "mage-armor"}}])


def test_running_out_of_slots_is_refused():
    w = wizard(prepared={"fireball": 2})
    _, e = table(w)
    cast(e, "fireball")
    w.prepared["fireball"] = 1
    cast(e, "fireball")
    w.prepared["fireball"] = 1
    with pytest.raises(IntentError, match="no level 3 slots left"):
        e.validate([{"op": "cast", "actor": "pc", "params": {"spell": "fireball"}}])


def test_a_spell_that_does_not_exist_is_refused():
    _, e = table(wizard())
    with pytest.raises(IntentError, match="no spell"):
        e.validate([{"op": "cast", "actor": "pc",
                     "params": {"spell": "summon-bigger-fireball"}}])


# --- preparation ---------------------------------------------------------------------------------

def test_a_night_clears_what_was_prepared():
    """Slots refill and preparation does not. Leaving them prepared would let a wizard
    sleep off their spending and keep the spells they had already cast."""
    w = wizard()
    w.rest("night")
    assert w.prepared == {}
    assert casting.slots_left(w, 3) == 2


def test_preparing_the_same_spell_twice_holds_two_copies():
    """A prepared caster may hold one spell in several slots, which is why this counts
    rather than being a set."""
    w = wizard(prepared={})
    casting.prepare(w, "magic-missile", 2)
    assert casting.prepared_count(w, "magic-missile") == 2


def test_unpreparing_past_zero_does_not_go_negative():
    w = wizard(prepared={"sleep": 1})
    casting.unprepare(w, "sleep", 5)
    assert casting.prepared_count(w, "sleep") == 0
    assert "sleep" not in w.prepared


def test_the_book_and_the_preparation_both_survive_a_save():
    w = wizard()
    back = from_dict(to_dict(w), ref="pc")
    assert back.spellbook == list(w.spellbook)
    assert back.prepared == w.prepared


def test_a_sheet_written_before_spellcasting_existed_still_loads():
    d = to_dict(load_pc("fixtures/pc-kesst.json"))
    d.pop("spellbook", None)
    d.pop("prepared", None)
    a = from_dict(d)
    assert a.spellbook == [] and a.prepared == {}


# --- the sheet ---------------------------------------------------------------------------------------

def test_the_sheet_lists_the_book_with_what_is_prepared():
    sheet = full_sheet(wizard())["spells"]
    by_name = {s["name"]: s for s in sheet["known"]}
    assert by_name["Fireball"]["level"] == 3
    assert by_name["Fireball"]["prepared"] == 1
    assert by_name["Mage Armor"]["prepared"] == 0


def test_the_sheet_carries_a_dc_per_slot_level():
    """The number the player is about to make somebody roll against, without arithmetic."""
    slots = {s["level"]: s for s in full_sheet(wizard())["spells"]["slots"]}
    assert slots[3]["dc"] == 17
    assert slots[3]["max"] == 2 and slots[3]["left"] == 2


def test_a_spell_this_build_does_not_ship_shows_as_a_gap():
    """A book naming a spell a later build removed is worth showing. A silently shorter
    list is not a thing anyone notices."""
    w = wizard(book=("magic-missile", "spell-that-went-away"))
    entries = {s["id"]: s for s in full_sheet(w)["spells"]["known"]}
    assert entries["spell-that-went-away"]["missing"] is True


# --- the prepare endpoint --------------------------------------------------------------------------------

@pytest.fixture
def wizard_campaign(tmp_path, settings):
    settings.CAMPAIGN_DIR = str(tmp_path)
    from play import campaign as campaign_mod

    return campaign_mod.begin_with(wizard(prepared={}))


def test_preparing_over_the_wire(client, wizard_campaign):
    res = client.post("/api/spells/prepare",
                      data={"action": "prepare", "spell": "fireball"},
                      content_type="application/json")
    assert res.status_code == 200
    known = {s["name"]: s for s in res.json()["spells"]["known"]}
    assert known["Fireball"]["prepared"] == 1


def test_you_cannot_prepare_more_copies_than_you_have_slots(client, wizard_campaign):
    """A wizard cannot memorise five fireballs into two slots."""
    for _ in range(2):
        client.post("/api/spells/prepare",
                    data={"action": "prepare", "spell": "fireball"},
                    content_type="application/json")
    res = client.post("/api/spells/prepare",
                      data={"action": "prepare", "spell": "fireball"},
                      content_type="application/json")
    assert res.status_code == 409
    assert "already prepared 2" in res.json()["error"]


def test_you_cannot_prepare_a_spell_off_your_list(client, wizard_campaign):
    res = client.post("/api/spells/prepare",
                      data={"action": "prepare", "spell": "cure-light-wounds"},
                      content_type="application/json")
    assert res.status_code == 400
    assert "not on the wizard list" in res.json()["error"]


def test_you_cannot_prepare_a_spell_past_your_level(client, wizard_campaign):
    res = client.post("/api/spells/prepare",
                      data={"action": "prepare", "spell": "wish"},
                      content_type="application/json")
    assert res.status_code == 400
    assert "reaches level 3" in res.json()["error"]


def test_learning_adds_to_the_book(client, wizard_campaign):
    res = client.post("/api/spells/prepare",
                      data={"action": "learn", "spell": "shield"},
                      content_type="application/json")
    assert res.status_code == 200
    assert "shield" in {s["id"] for s in res.json()["spells"]["known"]}


def test_forgetting_removes_it_and_anything_prepared_from_it(client, wizard_campaign):
    client.post("/api/spells/prepare",
                data={"action": "prepare", "spell": "fireball"},
                content_type="application/json")
    res = client.post("/api/spells/prepare",
                      data={"action": "forget", "spell": "fireball"},
                      content_type="application/json")
    assert "fireball" not in {s["id"] for s in res.json()["spells"]["known"]}


def test_a_stale_spell_id_in_a_prepared_list_does_not_break_the_page(client,
                                                                    wizard_campaign):
    """Raising here would make the whole spell page 500 over one id a later build
    renamed."""
    wizard_campaign.scene.pc().prepared["spell-that-went-away"] = 1
    wizard_campaign.save()
    res = client.post("/api/spells/prepare",
                      data={"action": "prepare", "spell": "magic-missile"},
                      content_type="application/json")
    assert res.status_code == 200
