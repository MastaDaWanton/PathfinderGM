"""Enchanting lane C2: the curse readers lane F left, dancing, spell storing, and the
property readers lane C left (docs/enchanting-contracts.md §4, §7, §10).

Each test names what the engine did before its reader existed — measured on the tree the
lane started from (build/enchanting a100384) with the same records, unless it says
otherwise.
"""
from __future__ import annotations

import json

import pytest

from rules import curses, forge_items, inprogress, magic_layer, states
from rules.activeeffect import ActiveEffect
from rules.bestiary import instantiate
from rules.dice import Dice
from rules.engine import Engine, Scene
from rules.sheet import (IllegalSheet, Situation, built, from_dict, full_sheet, load_pc,
                         situated, to_dict)
from tests._board import face_to_face
from tests.test_curses import Script
from tests.test_enchant_engine import (_fight, _foe, _hits, _record, _run, _swing, _table,
                                       _wear)


# --- builders ---------------------------------------------------------------------------------

def _cursed(rid: str, faces, base: str = "longsword", *, gear: str = "weapon",
            props=("keen",), enhancement: int = 1) -> dict:
    """A layered record carrying the curse the scripted dice roll on the REAL table."""
    rec = _record(rid, base, gear=gear, props=props, enhancement=enhancement)
    rec["magic"]["curse"] = curses.roll(Script(*faces), rec, {"caster_level": 10})
    return rec


NIGHT = (36, 51, 12)          # intermittent -> dependent -> during the night
UNRELIABLE = (36, 1)          # intermittent -> unreliable
SPECIFIC = (91,)              # a specific cursed item: -2, clings
DAILY_USE = (46, 35)          # requirement -> used every day
NO_ARCANE = (61, 98)          # drawback -> cannot cast arcane spells
MARK = (61, 32)               # drawback -> a mark anyone can see (noticed)
WILL_INT = (61, 62)           # drawback -> a daily Will save or 1 Int


def _armed_with(rec: dict, seed: int = 4):
    s, e = _table(seed)
    pc = s.pc()
    pc.add_stock(forge_items.stock_item(rec))
    _wear(e, rec["id"])
    return s, e, pc


def _caster(**prepared):
    d = to_dict(load_pc("fixtures/pc-caster.json"))
    d["abilities"]["int"] = 18
    d["prepared"] = dict(prepared or {"magic-missile": 2})
    s = Scene(location_id="5bbd0c40345f")
    s.add(from_dict(d, ref="pc"))
    pc = s.pc()
    pc.add_buff("combat_mod", "attack", 20, source="the test's steady hand", rounds=10_000)
    e = Engine(s, Dice(seed=4))
    e._flat_footed = lambda defender: False
    return s, e, pc


def _gutter_dice(e, face: int):
    """The unreliable item's d% shows `face`; every other die rolls as it would."""
    real = e.dice.roll

    def roll(notation, mods=None, label="", visibility="hidden"):
        if "does it work" in label:
            return e.dice.given_total(face, "1d100", [], label=label)
        return real(notation, mods, label=label, visibility=visibility)

    e.dice.roll = roll


def _all_text(resolution) -> str:
    return json.dumps([o.as_dict() for o in resolution.outcomes], default=str)


# --- dependent curses: the situation a roll is made in ---------------------------------------

def test_a_night_only_blade_is_a_plain_blade_by_day_and_a_keen_one_by_night():
    """Lane F's dependent curse puts its situation on every document's `when`, and
    nothing answered the situation. Measured before C2 on a +1 keen longsword cursed to
    work only by night: its +1 was gone at noon AND at midnight (the clause could never
    be evaluated), while it threatened on 17-20 and struck as magic at both hours (the
    row-level readers never asked a `when`)."""
    s, e, pc = _armed_with(_cursed("nightblade", NIGHT))
    s.clock_minutes = 12 * 60
    with situated(s):
        noon = pc.weapon("nightblade")
        noon_dmg = [m.source for m in pc.damage_modifiers("nightblade")]
    s.clock_minutes = 23 * 60 + 30
    with situated(s):
        night = pc.weapon("nightblade")
        night_dmg = sum(m.value for m in pc.damage_modifiers("nightblade"))
    assert noon["crit_range"] == 19 and "magic" not in (noon.get("strikes_as") or ())
    assert noon_dmg == ["Str"]
    assert night["crit_range"] == 17 and "magic" in night["strikes_as"]
    assert night_dmg == 2                                   # Str +1 and the +1


def test_by_day_the_bearer_is_told_once_that_something_in_the_blade_is_wrong():
    """The curse acts and is not named (law 3, `curses.tell`): by day the swing says that
    something in the blade is wrong — once a day, not on every swing — and its damage is
    the plain blade's; by night the +1 is back. Its id never reaches a tell."""
    s, e, pc = _armed_with(_cursed("nightblade", NIGHT))
    foe = _foe(s)
    _fight(s, e, foe)
    s.clock_minutes = 12 * 60
    first, _ = _swing(s, e, foe, _hits)
    again, _ = _swing(s, e, foe, _hits)
    s.clock_minutes = 22 * 60
    night, _ = _swing(s, e, foe, _hits)
    assert "Something in the nightblade is wrong." in first.tell
    assert "Something in" not in again.tell
    assert "for 2 slashing" in first.tell and "for 3 slashing" in night.tell
    curse_id = pc.item_records("nightblade")[0]["magic"]["curse"]["id"]
    for out in (first, again, night):
        assert curse_id not in json.dumps(out.as_dict(), default=str)


def test_the_situation_facts_come_from_the_scene_clock_and_the_place():
    """`daylight`, `day_phase`, `underground`, `wielder_casts`: read live off the one
    clock and the creature's own place (no copy of either on the Actor); outside a roll
    there is no moment and every one is unknown, which a clause reads as no."""
    s = Scene(location_id="5bbd0c40345f")
    pc = s.add(load_pc("fixtures/pc-kesst.json"))
    s.clock_minutes = 3 * 1440 + 23 * 60 + 40            # day 3, 23:40
    sit = Situation(pc, s)
    assert sit.fact("daylight") is False
    assert sit.fact("day_phase") == "midnight"
    assert sit.fact("wielder_casts") is False
    pc.at = "5bbd0c40345f~underground:the-old-mine"
    assert Situation(pc, s).fact("underground") is True
    pc.at = "5bbd0c40345f~forest:the-approach"
    assert Situation(pc, s).fact("underground") is False
    from rules.sheet import _when_holds, situation_of

    assert situation_of(pc) is None
    assert not _when_holds({"daylight": False}, pc._situation_ctx())
    with situated(s):
        assert _when_holds({"daylight": False}, pc._situation_ctx())


def test_within_ten_feet_of_a_kind_of_creature_is_measured_on_the_board():
    """"Within 10 feet of a creature type" (the dependent table): a skeleton beside the
    bearer answers yes; across the room, no — by type tag (law 1), never a name."""
    s, e = _table()
    pc = s.pc()
    bones = s.add(instantiate("skeleton", scene=s, name="the skeleton"))
    thug = _foe(s)
    _fight(s, e, bones, thug)
    face_to_face(s, b=bones.ref)
    sit = Situation(pc, s)
    assert sit.near({"type": "undead"})
    s.positions[bones.ref] = (s.positions["pc"][0] + 6, s.positions["pc"][1])
    assert not Situation(pc, s).near({"type": "undead"})
    assert not Situation(pc, s).near({"type": "dragon"})


# --- unreliable: one d% a use -------------------------------------------------------------------

def test_an_unreliable_blade_gutters_on_its_roll_and_the_curse_is_found_then():
    """CRB, Cursed Items: "Each time the item is activated, there is a 5% chance (01-05 on
    d%) that it does not function." Lane F wrote `gutters_pct` on every document and
    `curses.gutters`; nothing rolled. A gutter is that swing made without the layer, said
    with the die, and the first one names the curse (the hard way, plan §12.2)."""
    s, e, pc = _armed_with(_cursed("shaky", UNRELIABLE))
    foe = _foe(s)
    _fight(s, e, foe)
    _gutter_dice(e, 3)
    first, _ = _swing(s, e, foe, _hits)
    second, _ = _swing(s, e, foe, _hits)
    assert "The shaky's magic gutters and does nothing this time (3 on d%)." in first.tell
    assert "The shaky is cursed. Unreliable" in first.tell
    assert "gutters" in second.tell and "is cursed" not in second.tell
    assert "for 2 slashing" in first.tell                  # Str only: no +1
    assert pc.item_records("shaky")[0]["magic"]["known"]["curse"] is True
    _gutter_dice(e, 50)
    works, _ = _swing(s, e, foe, _hits)
    assert "gutters" not in works.tell and "for 3 slashing" in works.tell


# --- requirement: the day's facts --------------------------------------------------------------

def test_a_blade_that_must_be_used_daily_sleeps_after_a_day_unused_and_wakes_when_used():
    """`curses.settle_day` was written and nothing gathered its facts: a requirement
    curse never suppressed anything. Now the day boundary settles it — unused, "The magic
    in the Hungry has gone quiet." and the layer is off (keen gone); swung the next day,
    it stirs again at the following boundary."""
    s, e, pc = _armed_with(_cursed("hungry", DAILY_USE))
    s.clock_minutes = 10 * 60
    quiet = s.advance(minutes=24 * 60)
    assert any("gone quiet" in line for line in quiet["ended"])
    with situated(s):
        assert pc.weapon("hungry")["crit_range"] == 19
    foe = _foe(s)
    _fight(s, e, foe)
    _swing(s, e, foe, _hits)
    _run(e, [{"op": "end_encounter", "because": "t", "params": {}}])
    back = s.advance(minutes=24 * 60)
    assert any("stirs again" in line for line in back["ended"])
    with situated(s):
        assert pc.weapon("hungry")["crit_range"] == 17


# --- drawbacks: what the bearer cannot do ------------------------------------------------------

def test_an_arcane_bar_refuses_the_wizard_and_spends_nothing():
    """The drawback "cannot cast arcane spells" laid `curse.bars-casting.arcane` on the
    layer and nothing read it: measured before C2, the cursed wizard cast as ever. Now
    the vocabulary answers (`states.BLOCKS`), the cast is refused before the slot is
    spent, and the refusal is how the curse is found."""
    s, e, pc = _caster()
    rec = _cursed("hex", NO_ARCANE, "dagger")
    pc.add_stock(forge_items.stock_item(rec))
    _wear(e, "hex")
    foe = _foe(s)
    r = _run(e, [{"op": "cast", "actor": "pc", "because": "t",
                  "params": {"spell": "magic-missile", "at": foe.ref}}])
    tell = r.outcomes[0].tell
    assert "the magic will not come. Nothing is spent." in tell
    assert "cannot cast arcane spells" in tell
    assert pc.prepared["magic-missile"] == 2
    assert pc.has_state(states.CURSE_BARS_ARCANE)


def test_the_bars_stop_their_own_tradition_and_no_other():
    """Tags answer by prefix, so a bare `curse.bars-casting` row in BLOCKS would also
    answer for an `.arcane` tag and stop a cleric praying. The no-spells row is the
    sibling `.any` (lane F's data, fixed at this seam)."""
    arcane = (states.CURSE_BARS_ARCANE,)
    assert states.stops(arcane, "cast.arcane") and not states.stops(arcane, "cast.divine")
    assert not states.stops(arcane, "cast")
    assert states.stops((states.CURSE_BARS_ANY,), "cast")
    assert not states.stops(arcane, "any")
    s, e, pc = _caster()
    pc.add_stock(forge_items.stock_item(_cursed("hex", NO_ARCANE, "dagger")))
    _wear(e, "hex")
    assert pc.barred_from_casting(arcane=True) is not None
    assert pc.barred_from_casting(arcane=False) is None


def test_a_mark_anyone_can_see_is_found_the_moment_the_blade_is_drawn():
    """`curses.noticed` was written for the equip door and nothing asked it."""
    s, e = _table()
    pc = s.pc()
    pc.add_stock(forge_items.stock_item(_cursed("marked", MARK)))
    out = _wear(e, "marked")
    assert "The marked is cursed. Drawback: its bearer carries a mark" in out.tell
    assert pc.item_records("marked")[0]["magic"]["known"]["curse"] is True


def test_a_daily_save_names_the_curse_the_first_time_it_is_rolled():
    """"The first time a curse's clause bites (a daily save ...) the curse is known"
    (`knowledge.learn_by_use`): lane C rolled the save each day and the curse stayed
    hidden for ever."""
    s, e, pc = _armed_with(_cursed("whisper", WILL_INT))
    s.advance(minutes=60)                                   # the toll is granted
    day = s.advance(minutes=24 * 60)
    assert any("The whisper is cursed. Drawback: each day its bearer makes a Will save"
               in line for line in day["ended"])
    assert pc.item_records("whisper")[0]["magic"]["known"]["curse"] is True


# --- a specific cursed item clings --------------------------------------------------------------

def test_a_specific_cursed_blade_will_not_leave_the_hand_by_any_door():
    """"Can only be discarded after ... remove curse" (CRB; `curses.clings`). Measured
    before C2: "Kesst Vayr puts the grip away; their hands are empty." Every door that puts
    a thing down asks now — drawing something else, putting it away, dropping it, handing
    it over, selling it — and the first refusal names the curse."""
    s, e, pc = _armed_with(_cursed("grip", SPECIFIC))
    tells = [_run(e, [{"op": op, "actor": "pc", "because": "t", "params": params}])
             .outcomes[0].tell
             for op, params in (("wear", {"item": "unarmed"}), ("wear", {"item": "dagger"}),
                                ("give", {"item": "grip", "from_": "pc"}),
                                ("sell", {"item": "grip"}))]
    assert all("will not leave Kesst Vayr's hand" in t for t in tells), tells
    assert "is cursed. A cursed item" in tells[0]
    assert sum("is cursed" in t for t in tells) == 1
    assert pc.equipped == "grip"


def test_the_equipment_tabs_take_off_asks_as_the_engine_does():
    """Found on the live check (2026-10-06): the Equipment tab takes a slot item off
    through `Actor.take_off` directly, a door the engine's clinging check never saw."""
    s, e = _table()
    pc = s.pc()
    rec = _cursed("grip", SPECIFIC)
    pc.add_stock(forge_items.stock_item(rec))
    pc.wear(dict(rec, slot="hands"))
    with pytest.raises(IllegalSheet, match="will not come off.*is cursed"):
        pc.take_off("Grip")
    assert pc.item_records("grip")[0]["magic"]["known"]["curse"] is True


def test_a_specific_cursed_suit_will_not_come_off():
    s, e = _table()
    pc = s.pc()
    pc.add_stock(forge_items.stock_item(_cursed("clinger", SPECIFIC, "chain shirt",
                                                gear="armour", props=("glamered",))))
    _run(e, [{"op": "wear", "actor": "pc", "because": "t", "params": {"item": "clinger"}}])
    out = _run(e, [{"op": "take_off", "actor": "pc", "because": "t",
                    "params": {"item": "armour"}}]).outcomes[0]
    assert "will not come off Kesst Vayr" in out.tell
    assert pc.armour == "chain shirt"


# --- spell storing ---------------------------------------------------------------------------

def test_a_spell_storing_blade_holds_a_spell_and_releases_it_into_the_creature_it_wounds():
    """Lane A bound spell storing with a `reads_tag` and nothing read it: the property was
    priced and shown and held nothing. Stored through the cast door (the slot pays), held
    on the item's record with the caster's level and DC, released on the first wound
    through the cast door again (`partial["item_cast"]`, origin `item:<id>`)."""
    s, e, pc = _caster(**{"magic-missile": 2})
    pc.add_stock(forge_items.stock_item(_record("stinger", "dagger",
                                                props=("spell-storing",))))
    _wear(e, "stinger")
    stored = _run(e, [{"op": "use_item", "actor": "pc", "because": "t",
                       "params": {"item": "stinger", "power": "spell storing",
                                  "spell": "magic-missile"}}]).outcomes[0]
    assert "casts Magic Missile into the Stinger" in stored.tell
    assert pc.prepared["magic-missile"] == 1
    held = pc.item_records("stinger")[0]["magic"]["stored"]
    assert held["spell"] == "magic-missile" and held["cl"] == 1
    foe = _foe(s)
    _fight(s, e, foe)
    before = foe.hp
    out, _ = _swing(s, e, foe, _hits)
    assert "The Stinger releases the Magic Missile it held into the thug." in out.tell
    released = [x for x in out.effects if x.get("kind") == "spell_released"]
    assert released and released[0]["origin"] == "item:stinger"
    missile = [x for x in out.effects if x.get("kind") == "damage"
               and x.get("origin") == "item:stinger"]
    assert missile, out.effects
    assert foe.hp < before - 1
    assert "stored" not in pc.item_records("stinger")[0]["magic"]


def test_spell_storing_refuses_an_area_spell():
    s, e, pc = _caster(**{"burning-hands": 1})
    pc.add_stock(forge_items.stock_item(_record("stinger", "dagger",
                                                props=("spell-storing",))))
    _wear(e, "stinger")
    out = _run(e, [{"op": "use_item", "actor": "pc", "because": "t",
                    "params": {"item": "stinger", "power": "spell-storing",
                               "spell": "burning-hands"}}]).outcomes[0]
    assert "is not a targeted spell" in out.tell
    assert pc.prepared["burning-hands"] == 1


# --- dancing ---------------------------------------------------------------------------------

def test_a_dancing_blade_fights_four_rounds_at_its_looseners_base_attack_then_drops():
    """Dancing was bound and priced and never danced. Loosed, the loosener is unarmed and
    cannot swing it; it attacks once a round at the loosener's base attack bonus with its
    own +1 and nothing else of theirs (Kesst's +20 steady hand and Dex are not in its
    roll); after its four rounds it lies at their feet, still theirs."""
    s, e, pc = _armed_with(_record("dancer", "longsword", props=("dancing",)))
    foe = _foe(s)
    _fight(s, e, foe)
    face_to_face(s, b=foe.ref)
    r = _run(e, [{"op": "use_item", "actor": "pc", "because": "t",
                  "params": {"item": "dancer", "power": "dancing"}}])
    loosed = r.outcomes[0]
    assert "dances in the air at their side" in loosed.tell
    assert "The Dancer dances in on its own." in loosed.tell
    assert pc.equipped == "unarmed"
    swing = next(x for x in loosed.rolls if str(x.label).startswith("Attack"))
    sources = {m.source for m in swing.modifiers}
    assert f"{pc.name}'s base attack" in sources
    assert "the test's steady hand" not in sources
    by_hand = _run(e, [{"op": "attack", "actor": "pc", "target": foe.ref,
                        "because": "t", "params": {"weapon": "dancer"}}]).outcomes[0]
    assert "is dancing on its own" in by_hand.tell
    danced = []
    for _ in range(4):
        s.round += 1
        danced += [o.tell for o in _run(e, [{"op": "narrate_only", "actor": "pc",
                                             "because": "t", "params": {}}]).outcomes
                   if o.op != "narrate_only"]
    assert sum("dances in on its own" in t for t in danced) == 3
    assert "four rounds are over, and it drops at Kesst Vayr's feet" in danced[-1]
    assert s.out_of_hand("pc", "dancer") is not None
    assert not [x for x in pc.effects if x.kind == "loosed"]


def test_a_dancing_blade_caught_back_cannot_dance_again_for_four_rounds():
    s, e, pc = _armed_with(_record("dancer", "longsword", props=("dancing",)))
    foe = _foe(s)
    _fight(s, e, foe)
    face_to_face(s, b=foe.ref)
    _run(e, [{"op": "use_item", "actor": "pc", "because": "t",
              "params": {"item": "dancer", "power": "dancing"}}])
    caught = _run(e, [{"op": "wear", "actor": "pc", "because": "t",
                       "params": {"item": "dancer"}}]).outcomes[0]
    assert "catches the Dancer out of the air" in caught.tell
    assert pc.equipped == "dancer"
    again = _run(e, [{"op": "use_item", "actor": "pc", "because": "t",
                      "params": {"item": "dancer", "power": "dancing"}}]).outcomes[0]
    assert "cannot dance again until round" in again.tell


# --- thrown, returning and the range increment ------------------------------------------------

def _throw(s, e, target, params):
    s.turn = [r for r, _ in s.initiative].index("pc")
    r = _run(e, [{"op": "attack", "actor": "pc", "target": target.ref,
                  "visibility": "player", "params": params, "because": "t"}])
    labels = []
    for _ in range(20):
        if r.awaiting is None:
            break
        labels.append(r.awaiting)
        r = e.resume(10 if r.awaiting["label"].startswith("Attack")
                     else int(r.awaiting["min"]))
    return next(o for o in r.outcomes if o.op == "attack"), labels


def test_a_returning_dagger_thrown_comes_back_and_a_plain_one_lies_where_it_fell():
    """Before C2 a thrown dagger never left the hand, so returning had nothing to return
    from. Now a thrown weapon lies by the one it was thrown at, still its thrower's, and
    the attack door refuses it until it is picked up; a returning one is back in hand."""
    s, e, pc = _armed_with(_record("homer", "dagger", props=("returning",)))
    pc.add_stock(forge_items.stock_item(_record("plain-knife", "dagger", props=("keen",))))
    foe = _foe(s)
    _fight(s, e, foe)
    s.positions["pc"], s.positions[foe.ref] = (2, 2), (6, 2)
    back, _ = _throw(s, e, foe, {"weapon": "homer", "thrown": True})
    assert "flies back to Kesst Vayr's hand" in back.tell
    assert pc.equipped == "homer" and s.out_of_hand("pc", "homer") is None
    _wear(e, "plain-knife")
    gone, _ = _throw(s, e, foe, {"weapon": "plain-knife", "thrown": True})
    assert "lies where it fell, by the thug" in gone.tell
    assert pc.equipped == "unarmed"
    from rules.intents import IntentError

    with pytest.raises(IntentError, match="lies on the ground"):
        _throw(s, e, foe, {"weapon": "plain-knife", "thrown": True})


def test_each_full_range_increment_past_the_first_costs_two_and_five_is_the_most():
    """No range increment was read anywhere: a shortbow hit as well at 300 feet as at 30,
    and distance's doubled increment was a number on the sheet. CRB: -2 per full
    increment; a thrown weapon reaches five increments."""
    s, e, pc = _armed_with(_record("homer", "dagger", props=("returning",)))
    foe = _foe(s)
    _fight(s, e, foe)
    s.positions["pc"], s.positions[foe.ref] = (2, 2), (6, 2)          # 20 ft
    out, asked = _throw(s, e, foe, {"weapon": "homer", "thrown": True})
    terms = {t["source"]: t["value"] for t in asked[0]["breakdown"]}
    assert terms.get("range (20 ft: 1 increment of 10 ft past the first)") == -2
    s.positions[foe.ref] = (15, 2)                                     # 65 ft
    far, _ = _throw(s, e, foe, {"weapon": "homer", "thrown": True})
    assert "past the homer's reach: 5 range increments of 10 ft is 50 ft" in far.tell


# --- ki focus, wild, ghost touch armour, bashing, animated ------------------------------------

def _monk(level: int = 7):
    d = to_dict(load_pc("fixtures/pc-borin.json"))
    d["class"], d["level"] = "monk", level
    s = Scene(location_id="5bbd0c40345f")
    s.add(from_dict(d, ref="pc"))
    return s, Engine(s, Dice(seed=3)), s.pc()


def test_a_ki_focus_staff_carries_ki_strike_and_a_charge_armed_for_the_fist():
    """`property.ki-focus` had no reader: a monk's ki strike stayed on the fist and a
    stunning fist charge listed unarmed strikes only."""
    s, e, monk = _monk(7)
    monk.add_stock(forge_items.stock_item(_record("kistaff", "quarterstaff",
                                                  props=("ki-focus",))))
    monk.add_stock(forge_items.stock_item(_record("plainstaff", "quarterstaff",
                                                  props=("keen",))))
    _run(e, [{"op": "wear", "actor": "pc", "because": "t", "params": {"item": "kistaff"}}])
    assert {"cold_iron", "silver"} <= set(monk.weapon("kistaff")["strikes_as"])
    assert "cold_iron" not in (monk.weapon("plainstaff").get("strikes_as") or ())
    monk.apply_effect(ActiveEffect(name="Stunning Fist", kind="ability", source="t",
                                   payload={"charge": {"weapons": ["unarmed"]}}))
    assert Engine._charges_for(monk, "kistaff", monk.weapon("kistaff"))
    assert not Engine._charges_for(monk, "plainstaff", monk.weapon("plainstaff"))


def _wild_shape(actor):
    actor.apply_effect(ActiveEffect(name="Wild Shape", kind="buff", key="wild shape",
                                    source="t", tags=("buff.form.wild-shape",)))


def test_in_wild_shape_a_suit_melds_and_gives_nothing_unless_it_is_wild():
    """CRB, Polymorph: armour and shield bonuses "cease to function" while melded. Before
    C2 a druid kept her suit's AC in wild shape (the druid document's own not_yet), so
    the wild property had nothing to keep."""
    s, e = _table()
    pc = s.pc()
    pc.add_stock(forge_items.stock_item(_record("plainmail", "chain shirt", gear="armour",
                                                props=("glamered",))))
    _run(e, [{"op": "wear", "actor": "pc", "because": "t", "params": {"item": "plainmail"}}])
    worn = pc.ac()
    _wild_shape(pc)
    assert pc.ac() == worn - 5                                       # +4 and its +1
    s, e = _table()
    pc = s.pc()
    pc.add_stock(forge_items.stock_item(_record("wildmail", "chain shirt", gear="armour",
                                                props=("wild",))))
    _run(e, [{"op": "wear", "actor": "pc", "because": "t", "params": {"item": "wildmail"}}])
    worn = pc.ac()
    _wild_shape(pc)
    assert pc.ac() == worn


def test_on_an_incorporeal_wearer_only_ghost_touch_armour_gives_its_bonus():
    """Ghost touch armour's second clause ("worn by corporeal and incorporeal creatures
    alike"), which lane C left with no reader."""
    for prop, keeps in (("glamered", False), ("ghost-touch-armour", True)):
        s, e = _table()
        pc = s.pc()
        pc.add_stock(forge_items.stock_item(_record("mail", "chain shirt", gear="armour",
                                                    props=(prop,))))
        _run(e, [{"op": "wear", "actor": "pc", "because": "t", "params": {"item": "mail"}}])
        worn = pc.ac()
        pc.apply_effect(ActiveEffect(name="ghostly", kind="buff", source="t",
                                     tags=("subtype.incorporeal",)))
        assert (pc.ac() == worn) is keeps, prop


def test_a_bashing_shield_bashes_two_sizes_up_as_a_plus_one_weapon():
    """No shield ever bashed: the table's shield rows refused to be wielded. A bash with
    the shield on the arm is now one attack; bashing makes a Medium heavy shield's 1d4 a
    1d8 and lends +1 and `magic` (CRB)."""
    s, e = _table()
    pc = s.pc()
    pc.add_stock(forge_items.stock_item(_record("basher", "heavy steel shield",
                                                gear="shield", props=("bashing",))))
    _run(e, [{"op": "wear", "actor": "pc", "because": "t", "params": {"item": "basher"}}])
    row = pc.weapon("shield bash")
    assert row["damage"] == "1d8" and "magic" in row["strikes_as"]
    assert any(m.source == "Basher (bash), bashing" and m.value == 1
               for m in pc.attack_modifiers("shield bash"))
    foe = _foe(s)
    _fight(s, e, foe)
    out, asked = _swing(s, e, foe, _hits, params={"weapon": "shield bash"})
    assert asked[-1] == "Damage (Basher (bash))" and "bludgeoning" in out.tell
    s, e = _table()
    pc = s.pc()
    pc.shield = "heavy shield"
    assert pc.weapon("shield bash")["damage"] == "1d4"
    pc.shield = "buckler"
    assert pc.shield_bash("shield bash") is None


def test_an_animated_shield_guards_four_rounds_with_both_hands_free_then_drops():
    s, e = _table()
    pc = s.pc()
    pc.add_stock(forge_items.stock_item(_record("floater", "heavy steel shield",
                                                gear="shield", props=("animated",))))
    _run(e, [{"op": "wear", "actor": "pc", "because": "t", "params": {"item": "floater"}}])
    pc.weapons.append("greatsword")
    refused = _run(e, [{"op": "wear", "actor": "pc", "because": "t",
                        "params": {"item": "greatsword"}}]).outcomes[0]
    assert "takes both hands" in refused.tell
    foe = _foe(s)
    _fight(s, e, foe)
    guarded = pc.ac()
    _run(e, [{"op": "use_item", "actor": "pc", "because": "t",
              "params": {"item": "floater", "power": "animated"}}])
    drawn = _run(e, [{"op": "wear", "actor": "pc", "because": "t",
                      "params": {"item": "greatsword"}}]).outcomes[0]
    assert "draws the greatsword" in drawn.tell and pc.ac() == guarded
    for _ in range(4):
        s.round += 1
        _run(e, [{"op": "narrate_only", "actor": "pc", "because": "t", "params": {}}])
    assert pc.shield == "none" and s.out_of_hand("pc", "floater") is not None


# --- a record rewritten under its worn copy (lane E's report) ---------------------------------

def test_a_record_rewritten_in_the_pack_is_what_the_hand_holds_next():
    """Lane E's live check (2026-10-06): after Collect, the drawn sword "kept the old
    unenchanted record until it was drawn again" — `wear` keeps a copy and the bench writes
    the pack's record. The next batch and the sheet read the pack's."""
    s, e = _table()
    pc = s.pc()
    rec = forge_items.record_for_base("longsword", gear="weapon", item_id="vessel",
                                      name="Plain Sword")
    pc.add_stock(forge_items.stock_item(rec))
    _wear(e, "vessel")
    entry = next(v for v in pc.stock.values()
                 if forge_items.record_of(v) and forge_items.record_of(v)["id"] == "vessel")
    new = magic_layer.write(forge_items.record_of(entry), {"enhancement": 1},
                            binding={"quality_index": 3, "level": 20, "perks": {}})
    new["name"] = "Bright Sword"
    entry.record.clear()
    entry.record.update(new)
    full_sheet(pc)
    assert "bright sword" in pc.worn and "plain sword" not in pc.worn
    assert any(w == "Bright Sword" for slot in pc.slots.values() for w in slot) \
        or pc.equipped == "vessel"
    assert magic_layer.has_layer(pc.wielded_record())


def test_a_ring_still_in_progress_cannot_be_put_on_from_the_sheet():
    """The engine's `wear` asked `inprogress.held_back`; the sheet's own door for slot
    items (`Actor.wear`, the Equipment tab) did not."""
    s, e = _table()
    pc = s.pc()
    from rules.crafting import Stock

    ring = Stock(base="Iron Ring", count=1, slot="ring", wearable=True)
    pc.add_stock(ring)
    key = next(k for k, v in pc.stock.items() if v is ring)
    inprogress.begin(pc, key, craft="enchanter", minutes=600, now=0, label="Binding",
                     result={})
    with pytest.raises(IllegalSheet, match="In progress|still"):
        pc.wear(dict(ring.as_dict(), id=key))


# --- the batch memo --------------------------------------------------------------------------

def test_a_build_is_kept_for_the_batch_and_rebuilt_when_the_record_changes():
    """Measured 2026-10-06: 5,689 `forge_items.build` calls in twenty combat turns with a
    layered suit and sword, 2.9 s of 7.5 s. Kept for one moment, by the record's content:
    a changed record is a new key, so the memo can be missed and never stale."""
    s = Scene(location_id="5bbd0c40345f")
    rec = _record("blade", "longsword", props=("flaming",))
    with situated(s):
        a = built(rec)
        assert built(rec) is a
        rec["magic"]["uses"] = {"x": 1}
        assert built(rec) is not a
    assert built(rec) is not built(rec)                     # no moment, nothing kept


def test_the_sheet_the_page_reads_knows_the_hour(monkeypatch):
    """Lane C2's ask: the Sheet and Equipment tabs built `full_sheet(pc)` outside any
    moment, so every situation fact read there was unknown and a night-only blade's
    curse failed closed even at midnight, while the same blade struck with its magic.
    Every sheet the page gets is now built inside the scene's moment."""
    from types import SimpleNamespace

    from play import views
    from rules import sheet as sheet_mod

    s, e, pc = _armed_with(_cursed("nightblade", NIGHT))
    s.clock_minutes = 23 * 60 + 30
    monkeypatch.setattr(views.campaign_mod, "current", lambda: SimpleNamespace(scene=s))
    seen = []
    monkeypatch.setattr(sheet_mod, "full_sheet",
                        lambda actor: seen.append(sheet_mod._MOMENT.get()) or {})
    views._sheet_now(pc)
    assert seen and seen[0] is not None and seen[0].scene is s
    assert Situation(pc, seen[0].scene).fact("day_phase") == "midnight"
