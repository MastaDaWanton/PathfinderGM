"""The combat rules the engine did not model yet (docs/outstanding-2026-11-13.md C1; the
ponytail audit's "rules not yet modelled" list after 0.2.29).

Each test quotes the rule and the number master 0b5e5be0 (0.3.4) gave before. The "before"
numbers were measured on that commit with the same probe the test runs.
"""
from __future__ import annotations

import pytest

from rules.activeeffect import ActiveEffect
from rules.bestiary import instantiate
from rules.dice import Dice
from rules.engine import Engine, Scene
from rules.sheet import from_dict, load_pc


def _tot(mods) -> int:
    return sum(m.value for m in mods)


def _brakka(*weapons, **extra):
    """A level-1 fighter with Str 16 (+3), Dex 12 and Power Attack (BAB 1: -1/+2)."""
    data = {"name": "Brakka", "kind": "pc", "class": "fighter", "level": 1,
            "abilities": {"str": 16, "dex": 12, "con": 12, "int": 10, "wis": 10, "cha": 10},
            "hp": 12, "weapons": list(weapons), "equipped": weapons[0],
            "feats": ["Power Attack"]}
    data.update(extra)
    return from_dict(data)


def _body(actor, *weapons):
    actor.apply_effect(ActiveEffect(name="beast shape", kind="buff", source="test",
                                    payload={"natural_weapons": list(weapons)}))
    return actor


BITE = {"key": "bite", "name": "bite", "damage": {"medium": "1d4"}, "type": "piercing"}
HOOVES = {"key": "hooves", "name": "hooves", "count": 2, "damage": {"medium": "1d6"},
          "type": "bludgeoning", "secondary": True}


# --- secondary natural attacks --------------------------------------------------------------

def test_a_secondary_natural_attack_is_minus_five_and_half_strength():
    """Bestiary, Natural Attacks: "Secondary attacks are made using the creature's base
    attack bonus –5 ... and add only 1/2 the creature's Strength bonus on damage rolls".
    Before: a horse's secondary hooves rolled +4 to hit and +3 damage, the bite's numbers."""
    pc = _body(_brakka("longsword"), BITE, HOOVES)
    assert _tot(pc.attack_modifiers("hooves")) == 4 - 5
    assert _tot(pc.damage_modifiers("hooves")) == 1          # half of +3, rounded down
    assert _tot(pc.attack_modifiers("bite")) == 4             # primary: untouched
    assert _tot(pc.damage_modifiers("bite")) == 3


def test_a_sole_natural_attack_adds_one_and_a_half_strength():
    """"If a creature has only one natural attack ... adds 1-1/2 times the creature's
    Strength bonus on damage rolls." Before: a lone bite added +3, not +4."""
    pc = _body(_brakka("longsword"), {**BITE, "damage": {"medium": "1d6"}})
    assert _tot(pc.damage_modifiers("bite")) == 4


def test_a_natural_attack_beside_a_weapon_is_secondary():
    """"Creatures with natural attacks and attacks made with weapons ... treat all of
    their available natural attacks as secondary attacks during that attack, regardless of
    the attack's original type." Before: a bite after a longsword in the same turn swung at
    the primary bonus (+4) for the primary's damage."""
    pc = _body(_brakka("longsword"), {**BITE, "damage": {"medium": "1d6"}})
    assert _tot(pc.attack_modifiers("bite", beside_weapons=True)) == 4 - 5
    assert _tot(pc.damage_modifiers("bite", beside_weapons=True)) == 1


def test_the_engine_marks_a_bite_after_a_sword_swing_secondary():
    """The path the player clicks: two blows in one batch, the sword then the bite. The
    bite's roll carries the -5 named."""
    s = Scene(location_id="5bbd0c40345f")
    pc = s.add(_body(_brakka("longsword"), {**BITE, "damage": {"medium": "1d6"}}))
    pc.hp = pc.hp_max = 500
    thug = s.add(instantiate("thug", scene=s, name="the thug"))
    thug.hp = thug.hp_max = 500
    e = Engine(s, Dice(seed=4))
    e._ensure_encounter(pc.ref, thug.ref)
    s.positions[pc.ref], s.positions[thug.ref] = (6, 10), (7, 10)
    s.resync_zones()
    res = e.run(e.validate([
        {"op": "attack", "actor": pc.ref, "target": thug.ref, "visibility": "hidden",
         "params": {"weapon": "longsword"}, "because": "sword"},
        {"op": "attack", "actor": pc.ref, "target": thug.ref, "visibility": "hidden",
         "params": {"weapon": "bite"}, "because": "bite"}]))
    bites = [o for o in res.outcomes if o.op == "attack"][-1]
    sources = [m.source for m in bites.rolls[0].modifiers]
    assert any("secondary natural attack" in src for src in sources), sources


# --- Power Attack on natural attacks ----------------------------------------------------------

def test_power_attack_halves_on_a_secondary_and_grows_on_a_sole_primary():
    """Power Attack (CRB p.131): "increased by half (+50%) if you are making an attack with
    a two-handed weapon ... or a primary natural attack that adds 1-1/2 times your Strength
    modifier ... halved (–50%) if you are making an attack with an off-hand weapon or
    secondary natural attack." At BAB 1 the bonus is +2. Before: the secondary hooves took
    the full +2 (damage 5) and a lone bite only +2 (damage 5)."""
    herd = _body(_brakka("longsword"), BITE, HOOVES)
    assert _tot(herd.damage_modifiers("hooves", power_attack=True)) == 1 + 1
    assert _tot(herd.damage_modifiers("bite", power_attack=True)) == 3 + 2
    lone = _body(_brakka("longsword"), {**BITE, "damage": {"medium": "1d6"}})
    assert _tot(lone.damage_modifiers("bite", power_attack=True)) == 4 + 3


def test_power_attack_two_handed_rung_is_unchanged():
    """The two-handed rung moved from `hands: 2` to `strength_share: 1.5`; a greatsword
    at BAB 1 is still +3 from the feat on top of 1.5x Str (+4)."""
    pc = _brakka("greatsword")
    assert _tot(pc.damage_modifiers("greatsword", power_attack=True)) == 4 + 3
    sword = _brakka("longsword")
    assert _tot(sword.damage_modifiers("longsword", power_attack=True)) == 3 + 2


def test_a_printed_secondary_attack_carries_its_share():
    """A printed block's shares are read off the print: an owlbear's claws and bite are
    primary (1x), a lone printed bite 1.5x, a natural attack beside a weapon 0.5x."""
    from rules import statblock_attacks as sa

    claws = {"natural": True, "kind": "claw", "count": 2, "bonuses": [8], "category": "melee"}
    bite = {"natural": True, "kind": "bite", "count": 1, "bonuses": [8], "category": "melee"}
    assert sa.strength_share(claws, [claws, bite]) == 1.0
    assert sa.strength_share(bite, [bite]) == 1.5
    club = {"natural": False, "kind": "", "count": 1, "bonuses": [7], "category": "melee"}
    assert sa.strength_share(bite, [club, bite]) == 0.5
    assert sa.strength_share(club, [club], hands=2) == 1.5
    wing = {"natural": True, "kind": "wing", "count": 2, "bonuses": [3], "category": "melee"}
    assert sa.strength_share(wing, [bite, wing]) == 0.5


# --- composite bows ---------------------------------------------------------------------------

def test_a_composite_bow_adds_strength_up_to_its_rating():
    """Composite longbow: "add your Strength bonus to damage, up to the maximum bonus
    indicated for the bow." Before: "composite longbow (+2 Str)" was refused as an unknown
    weapon, and a composite bow added nothing at Str 16."""
    pc = _brakka("composite longbow (+2 Str)")
    assert _tot(pc.damage_modifiers("composite longbow (+2 Str)")) == 2
    plain = _brakka("composite longbow")
    assert _tot(plain.damage_modifiers("composite longbow")) == 0   # rated +0


def test_a_composite_bow_below_its_rating_is_minus_two_and_keeps_the_penalty():
    """"If your Strength bonus is less than the strength rating of the composite bow ...
    you take a –2 penalty on attacks with it. The default composite longbow requires a
    Strength modifier of +0 or higher"; "If you have a penalty for low Strength, apply it
    to damage rolls." Before: Str 8 drew a +0 composite at +2 to hit (no -2)."""
    weak = _brakka("composite longbow",
                   abilities={"str": 8, "dex": 12, "con": 12, "int": 10, "wis": 10,
                              "cha": 10})
    assert _tot(weak.attack_modifiers("composite longbow")) == 1 + 1 - 2
    assert _tot(weak.damage_modifiers("composite longbow")) == -1
    assert _tot(_brakka("longbow").attack_modifiers("longbow")) == 2   # no rating


# --- bestiary feats ---------------------------------------------------------------------------

def test_a_bestiary_creature_carries_its_printed_feats():
    """Bestiary stat blocks print feats; `_NOT_ON_THE_SHEET` stripped them, so printed
    Combat Reflexes and Power Attack did nothing. Before: the ogre's sheet held [] where
    the block prints Iron Will and Toughness."""
    ogre = instantiate("ogre")
    assert {"iron will", "toughness"} <= {f.lower() for f in ogre.feats}


def test_printed_feats_do_not_count_twice_in_printed_numbers():
    """A printed total already holds a feat's unconditional terms (`Actor._flat_for`).
    Measured: with the feats on the sheet the ogre read 33 hit points against a printed 30
    until the printed total was read as already holding Toughness (`hp_channels`)."""
    from rules import bestiary

    block = bestiary.raw_block("ogre")
    ogre = instantiate("ogre")
    assert ogre.hp_max == block["hp"]                        # 30, not 33 (Toughness)
    assert _tot(ogre.save_modifiers("will")) == block["flat_saves"]["will"]
    assert _tot(ogre.initiative_modifiers()) == block["flat_initiative"]


# --- a zone move stops a full attack ----------------------------------------------------------

def test_a_zone_move_with_no_map_leaves_one_blow():
    """CRB, Full Attack: "The only movement you can take during a full attack is a 5-foot
    step." Before: with no map, an owlbear moved far -> engaged and still threw claw, claw,
    bite (7 dice rolled); now it is one blow."""
    s = Scene()
    pc = s.add(load_pc("fixtures/pc-kesst.json"))
    pc.hp = pc.hp_max = 500
    s.add(instantiate("owlbear", scene=s, name="the owlbear"))
    e = Engine(s, Dice(seed=3))
    e._ensure_encounter("c1", "pc")
    s.grid = None
    s.positions.clear()
    s.zones["c1"] = "far"
    res = e.run(e.validate([
        {"op": "move", "actor": "c1", "visibility": "hidden",
         "params": {"zone": "engaged"}, "because": "charge"},
        {"op": "attack", "actor": "c1", "target": "pc", "visibility": "hidden",
         "params": {"full_attack": True}, "because": "maul"}]))
    attack = next(o for o in res.outcomes if o.op == "attack")
    blows = [b for b in attack.blows if b.get("result") in ("hit", "miss")]
    assert len(blows) == 1, attack.tell
    assert s.move_spent.get("c1") == s.round


def test_staying_in_the_same_zone_keeps_the_full_attack():
    s = Scene()
    pc = s.add(load_pc("fixtures/pc-kesst.json"))
    pc.hp = pc.hp_max = 500
    s.add(instantiate("owlbear", scene=s, name="the owlbear"))
    e = Engine(s, Dice(seed=3))
    e._ensure_encounter("c1", "pc")
    s.grid = None
    s.positions.clear()
    s.zones["c1"] = "engaged"
    res = e.run(e.validate([
        {"op": "attack", "actor": "c1", "target": "pc", "visibility": "hidden",
         "params": {"full_attack": True}, "because": "maul"}]))
    attack = next(o for o in res.outcomes if o.op == "attack")
    assert len([b for b in attack.blows if b.get("result") in ("hit", "miss")]) == 3


# --- blinded and Perception -------------------------------------------------------------------

def test_blinded_is_minus_four_on_opposed_perception_only():
    """Blinded (CRB): "-4 penalty on most Strength- and Dexterity-based skill checks and on
    opposed Perception skill checks." Before: -4 on every Perception check, a DC to hear a
    door included."""
    k = load_pc("fixtures/pc-kesst.json")
    base = _tot(k.skill_modifiers("perception"))
    k.add_condition("blinded")
    assert _tot(k.skill_modifiers("perception")) == base
    assert _tot(k.skill_modifiers("perception", opposed=True)) == base - 4


def test_the_opposed_check_op_charges_blinded_perception():
    """The check op with `opposed_by` is the opposed roll: its Perception takes the -4."""
    s = Scene(location_id="5bbd0c40345f")
    k = s.add(load_pc("fixtures/pc-kesst.json"))
    s.add(instantiate("thug", scene=s, name="the thug"))
    k.add_condition("blinded")
    e = Engine(s, Dice(seed=2))
    res = e.run(e.validate([{"op": "check", "actor": "pc", "visibility": "hidden",
                             "params": {"skill": "perception",
                                        "opposed_by": {"ref": "c1", "skill": "stealth"}},
                             "because": "listen for him"}]))
    roll = next(o for o in res.outcomes if o.op == "check").rolls[0]
    assert any(m.value == -4 and "blind" in m.source for m in roll.modifiers)


# --- sightless --------------------------------------------------------------------------------

def test_an_ooze_is_sightless_and_color_spray_spares_it_without_blinding_it():
    """Ooze: "Blind (but have the blindsight universal monster rule) ... immune to gaze
    attacks, visual effects"; color spray: "Sightless creatures are not affected". Before:
    a gray ooze was not spared ('' from `spared_by`). Sightless is not the blinded
    condition: the ooze's AC is untouched."""
    from rules import spells, states

    ooze = instantiate("gray-ooze")
    ac = ooze.ac()
    spray = spells.get("color-spray")
    assert states.sightless(ooze)
    assert spells.spared_by(spray, ooze, 3) == "cannot see it"
    assert not ooze.has_state("state.senses.blinded") and ooze.ac() == ac
    assert not states.sightless(instantiate("thug"))


# --- waking a sleeper -------------------------------------------------------------------------

def _sleeper():
    s = Scene(location_id="5bbd0c40345f")
    s.add(load_pc("fixtures/pc-kesst.json"))
    th = s.add(instantiate("thug", scene=s, name="the thug"))
    th.add_condition("helpless", 10, source="the sleep", origin="spell:sleep",
                     payload={"ends_when": {"wounded": True}})
    return s, th


def test_a_magical_sleeper_cannot_wake_itself():
    """Sleep (CRB): "Slapping or wounding awakens an affected creature, but normal noise
    does not." Before: `condition ends` from the sleeper itself lifted it for nothing."""
    s, th = _sleeper()
    e = Engine(s, Dice(seed=3))
    res = e.run(e.validate([{"op": "condition", "actor": "c1", "visibility": "hidden",
                             "params": {"condition": "helpless", "ends": True, "to": "c1"},
                             "because": "wakes up"}]))
    assert res.outcomes[0].status == "refused"
    assert th.has_state("state.helpless") or any(e.key == "helpless" for e in th.effects)


def test_slapping_a_sleeper_awake_is_a_standard_action_in_a_fight():
    """"Awakening a creature is a standard action (an application of the aid another
    action)." Before: free, and the waker still swung after it. Now it spends the
    waker's standard action, and a second standard action is refused."""
    s, th = _sleeper()
    e = Engine(s, Dice(seed=3))
    e._ensure_encounter("pc", "c1")
    s.positions["pc"], s.positions["c1"] = (6, 10), (7, 10)
    s.resync_zones()
    res = e.run(e.validate([{"op": "condition", "actor": "pc", "visibility": "hidden",
                             "params": {"condition": "helpless", "ends": True, "to": "c1"},
                             "because": "slap him awake"}]))
    woke = res.outcomes[0]
    assert woke.status == "resolved" and "slaps" in woke.tell
    assert not any(x.key == "helpless" for x in th.effects)
    assert s.standard_spent.get("pc") == s.round
    th.add_condition("helpless", 10, source="the sleep", origin="spell:sleep",
                     payload={"ends_when": {"wounded": True}})
    again = e.run(e.validate([{"op": "condition", "actor": "pc", "visibility": "hidden",
                               "params": {"condition": "helpless", "ends": True,
                                          "to": "c1"}, "because": "again"}]))
    assert again.outcomes[0].status == "refused"


# --- charm and the player's allies ------------------------------------------------------------

def test_harm_by_the_players_ally_breaks_a_charm():
    """Charm Person: "Any act by you or your apparent allies that threatens the charmed
    person breaks the spell." Before: `attitude.harmed` returned None for any harm not the
    player's own, and the guard stayed friendly with a companion's club in his ribs."""
    from rules import attitude as att

    s = Scene(location_id="5bbd0c40345f")
    s.add(load_pc("fixtures/pc-kesst.json"))
    guard = s.add(instantiate("thug", scene=s, name="the guard"))
    ally = s.add(instantiate("thug", scene=s, name="Dace"))
    stranger = s.add(instantiate("thug", scene=s, name="a stranger"))
    e = Engine(s, Dice(seed=3))
    e._set_attitude(guard, "friendly", 60, "the charm person",
                    payload={"charm": "spell:charm-person"})
    s.sides = {"us": ["pc", ally.ref], "them": []}
    assert att.harmed(e, guard, stranger, "attack:club") is None
    assert att.of(guard) == "friendly"
    got = att.harmed(e, guard, ally, "attack:club")
    assert got["why"] == "charm_broken" and att.of(guard) != "friendly"


# --- a held player's save ---------------------------------------------------------------------

def test_a_held_player_rolls_their_own_save_on_the_popup():
    """Hold person: "Each round on its turn, the subject may attempt a new saving throw to
    end the effect." Before: `Scene._held_saves` rolled the player's Will save hidden
    (rolls 18, 5, 12 over three turns, never shown) and skipped their slot. Now the slot
    stops, and the save is the player's die."""
    s = Scene(location_id="5bbd0c40345f")
    pc = s.add(load_pc("fixtures/pc-kesst.json"))
    s.add(instantiate("thug", scene=s, name="the thug"))
    e = Engine(s, Dice(seed=3))
    e._ensure_encounter("pc", "c1")
    pc.add_condition("paralyzed", 10, source="the hold person", origin="spell:hold-person",
                     payload={"ends_when": {"save_each_turn": {"save": "will", "dc": 15}}})
    seen = [s.advance_turn() for _ in range(2)]
    assert "pc" in seen
    assert not any(h.get("kind") == "held_save" and h.get("ref") == "pc"
                   for h in s.hazards)
    e.held_save_turn("pc")
    assert s.awaiting and s.awaiting["label"] == "Will save" and s.awaiting["dc"] == 15
    done = e.resume(20)
    assert "breaks free" in done.outcomes[0].tell
    assert not any(x.key == "paralyzed" for x in pc.effects)


def test_a_model_cannot_write_breaks_onto_a_save():
    """`breaks` is code's: a planned save naming it does nothing without an engine
    origin."""
    s = Scene(location_id="5bbd0c40345f")
    pc = s.add(load_pc("fixtures/pc-kesst.json"))
    pc.add_condition("paralyzed", 10, source="the hold person",
                     payload={"ends_when": {"save_each_turn": {"save": "will", "dc": 15}}})
    e = Engine(s, Dice(seed=1))
    e.run(e.validate([{"op": "save", "actor": "pc", "visibility": "hidden",
                       "params": {"save": "will", "dc": 1, "breaks": "paralyzed"},
                       "because": "x"}]))
    assert any(x.key == "paralyzed" for x in pc.effects)


# --- a check from words that did nothing ------------------------------------------------------

def test_a_boast_does_not_roll_disable_device():
    """Audit #7's limit: speech backed every detector check. Measured: "I tell the guard I
    pick the lock on that gate every night" declared ['check', 'say'] (the detector's "i
    pick the lock" inside the boast), and a talk-only reading kept the check. Now a check
    of a deed's skill needs a deed; a spoken skill still stands on speech."""
    from gm import interpret, judgement

    s = Scene(location_id="5bbd0c40345f")
    s.add(load_pc("fixtures/pc-kesst.json"))
    text = "I tell the guard I pick the lock on that gate every night"
    assert "check" in judgement.declared_ops(text, s)
    talk = {"question": False, "claims": [], "actions": [
        {"span": text, "says": text, "act": "talk", "cost": "free", "means": "ordinary"}]}
    assert interpret.supported(["check"], talk, check_skill="disable device") == \
        ([], ["check"])
    assert interpret.supported(["check"], talk, check_skill="diplomacy") == (["check"], [])
    assert judgement.declared_ops("I'll never pick the lock", s) == []
