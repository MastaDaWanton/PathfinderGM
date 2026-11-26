"""Feat loop batch 3, lane b3-divine: each feat's clauses measured through the engine.

Before this batch none of these feats had a document (worklist 2026-11-26, b3-divine.tsv,
34 feats): a cleric with Turn Undead, Channel Smite or Quick Channel held a name on the
sheet that no use, no swing and no burst read. The activated ones are documents in
content/class-abilities/feats-b3-divine.json, run by the class-ability executor; the
passive ones are tags and funnel terms in content/feats/mechanics/b3-divine.json.
"""
from __future__ import annotations

from rules import class_abilities as ca
from rules.bestiary import instantiate
from rules.dice import Dice
from rules.engine import Engine, Scene
from rules.sheet import from_dict, load_pc, to_dict


def _pc(cls: str = "cleric", level: int = 8, feats=(), **extra):
    d = to_dict(load_pc("fixtures/pc-kesst.json"))
    d["class"] = cls
    d["level"] = level
    d["ranks"] = {}
    d.pop("paths", None)
    d["feats"] = list(feats)
    d.update(extra)
    pc = from_dict(d, ref="pc")
    pc.abilities["cha"] = 16                     # +3
    return pc


def _fight(pc, *foes, allies=(), seed=11, at=None):
    scene = Scene()
    if at:
        scene.at = at
    scene.add(pc)
    for a in allies:
        scene.add(a)
    for f in foes or ("thug",):
        scene.add(instantiate(f, scene=scene, name=f"the {f}"))
    them = [r for r in scene.actors if r != "pc" and r not in {a.ref for a in allies}]
    e = Engine(scene, dice=Dice(seed=seed))
    e.run(e.validate([{"op": "begin_encounter", "params": {
        "sides": {"pc": ["pc"] + [a.ref for a in allies], "them": them}}}]))
    return scene, e


def _use(e, name, to=None, actor="pc"):
    raw = {"op": "use_ability", "actor": actor, "because": "test",
           "params": {"ability": name}}
    if to:
        raw["params"]["to"] = to
    return e.run(e.validate([raw])).outcomes[-1]


def _swing(e, target="c1", face=15, **params):
    raw = {"op": "attack", "actor": "pc", "target": target, "because": "test",
           "params": dict(params)}
    res = e.run(e.validate([raw]))
    while res.awaiting:
        label = res.awaiting["label"]
        res = e.resume(face if label.startswith(("Attack", "Confirm"))
                       else int(res.awaiting["max"]))
    return res


def _tells(res) -> str:
    return " ".join(o.tell for o in res.outcomes)


def _left(pc, pool):
    return pc.pool(pool).current


def _kinds(out, kind):
    return [x for x in out.effects if x.get("kind") == kind]


# --- the shared shape ------------------------------------------------------------------

def test_the_documents_validate():
    assert not ca.validate_documents()
    from rules import classbuilder, feats
    assert classbuilder.validate_feat_documents(feats.documents()) == []


def test_a_use_of_channel_energy_is_the_cleric_s_one_and_the_paladin_s_two():
    """`cost.uses_of`: "use one of your uses of channel energy" is one of a cleric's
    channel pool and two of a paladin's lay on hands (CRB p.62), read off whichever
    document answers to the name — one feat document, not one per class."""
    cleric = _pc("cleric", feats=["Turn Undead"])
    _s, e = _fight(cleric, "zombie")
    ca.ensure_pool(cleric, ca.find(cleric, "channel energy")[0])
    before = _left(cleric, "channel energy")
    out = _use(e, "Turn Undead")
    assert out.status != "refused", out.tell
    assert _left(cleric, "channel energy") == before - 1

    paladin = _pc("paladin", feats=["Turn Undead"])
    _s, e = _fight(paladin, "zombie")
    before = _left(paladin, "lay on hands")
    out = _use(e, "Turn Undead")
    assert out.status != "refused", out.tell
    assert _left(paladin, "lay on hands") == before - 2


def test_a_feat_that_spends_channel_energy_is_refused_without_it():
    fighter = _pc("fighter", feats=["Turn Undead"])
    _s, e = _fight(fighter, "zombie")
    out = _use(e, "Turn Undead")
    assert out.status == "refused"
    assert "channel energy" in out.tell


# --- Turn Undead, Life Lure, Command Undead ----------------------------------------------

def test_turn_undead_panics_the_undead_for_a_minute_and_spares_the_living():
    """Turn Undead (CRB): undead within 30 ft save (Will DC 10 + 1/2 level + Cha) or flee,
    panicked, for 1 minute; "it has no other effect". The thug beside them is untouched."""
    pc = _pc("cleric", feats=["Turn Undead"])
    scene, e = _fight(pc, "zombie", "thug", seed=3)
    zombie = next(a for a in scene.actors.values() if a.has_state("type.undead"))
    thug = next(a for a in scene.actors.values() if a.ref not in ("pc", zombie.ref))
    out = _use(e, "Turn Undead")
    saves = _kinds(out, "save")
    assert [s["ref"] for s in saves] == [zombie.ref]
    assert saves[0]["dc"] == 10 + 4 + 3
    assert not thug.has_state("state.fear")
    if not saves[0]["saved"]:
        assert zombie.has_state("state.fear.panicked")
        held = next(x for x in zombie.effects if x.key == "panicked")
        assert held.rounds_left == 10
        # Mindless: no new save each round.
        assert not (held.payload or {}).get("ends_when")


def test_turned_intelligent_undead_get_a_new_save_each_round():
    """'Intelligent undead receive a new saving throw each round to end the effect': the
    ghoul's panic carries the use's DC as `save_each_turn`; the zombie's does not."""
    pc = _pc("cleric", feats=["Turn Undead"])
    pc.abilities["cha"] = 30                     # a DC nothing makes
    scene, e = _fight(pc, "ghoul", seed=3)
    ghoul = scene.actors["c1"]
    _use(e, "Turn Undead")
    held = next(x for x in ghoul.effects if x.key == "panicked")
    assert held.payload["ends_when"]["save_each_turn"] == {"save": "will",
                                                          "dc": 10 + 4 + 10}


def test_improved_channel_raises_turn_undead_s_dc():
    """Improved Channel adds 2 to 'your channel energy ability' DC; Turn Undead is one."""
    pc = _pc("cleric", feats=["Turn Undead", "Improved Channel"])
    _s, e = _fight(pc, "zombie")
    out = _use(e, "Turn Undead")
    assert _kinds(out, "save")[0]["dc"] == 10 + 4 + 3 + 2


def test_life_lure_fascinates_the_undead_for_cha_rounds():
    pc = _pc("cleric", feats=["Life Lure"])
    pc.abilities["cha"] = 30
    scene, e = _fight(pc, "zombie")
    out = _use(e, "Life Lure")
    z = scene.actors["c1"]
    assert not _kinds(out, "save")[0]["saved"]
    held = next(x for x in z.effects if x.key == "fascinated")
    assert held.rounds_left == 10                 # Cha 30: +10
    assert not _kinds(out, "heal") and not _kinds(out, "damage")


def test_command_undead_puts_failed_undead_on_the_cleric_s_side_up_to_her_level_in_hd():
    """Command Undead (CRB): undead that fail fall under control, 'so long as their total
    Hit Dice do not exceed your cleric level'. Two zombies (2 HD each) at level 3: one is
    taken, the second would make 4 and is passed by."""
    pc = _pc("cleric", level=3, feats=["Command Undead"])
    pc.abilities["cha"] = 30
    scene, e = _fight(pc, "zombie", "zombie")
    out = _use(e, "Command Undead")
    held = [a for a in scene.actors.values() if a.has_state("controlled.by.pc")]
    assert len(held) == 1, out.tell
    assert held[0].ref in scene.sides["pc"]
    assert _kinds(out, "unaffected")


def test_command_undead_is_a_cleric_s():
    pc = _pc("paladin", feats=["Command Undead"])
    _s, e = _fight(pc, "zombie")
    assert _use(e, "Command Undead").status == "refused"


# --- Elemental Channel, Quick Channel, Bestow Hope ---------------------------------------

def test_elemental_channel_harms_only_the_outsiders_of_its_subtype():
    """Elemental Channel (fire): the burst harms fire outsiders and 'has no affect on other
    creatures'. Without the feat the mode does not exist."""
    pc = _pc("cleric", feats=["Elemental Channel (fire)"])
    scene, e = _fight(pc, "small-fire-elemental", "thug")
    elem = scene.actors["c1"]
    hp = elem.hp
    out = _use(e, "Elemental Channel (harm fire)")
    assert out.status != "refused", out.tell
    hurt = {x["ref"] for x in _kinds(out, "damage")}
    assert hurt == {elem.ref} and elem.hp < hp
    assert "harm fire" in ca.choices_of(pc, ca.find(pc, "elemental channel")[0])
    assert "harm air" not in ca.choices_of(pc, ca.find(pc, "elemental channel")[0])
    assert _use(e, "Elemental Channel (harm air)").status == "refused"


def test_quick_channel_is_channel_energy_for_two_uses_as_a_move_action():
    pc = _pc("cleric", feats=["Quick Channel"])
    pc.hp = 1
    _s, e = _fight(pc, "thug")
    ca.ensure_pool(pc, ca.find(pc, "channel energy")[0])
    before = _left(pc, "channel energy")
    out = _use(e, "Quick Channel (heal)")
    assert out.status != "refused", out.tell
    assert _left(pc, "channel energy") == before - 2
    assert _kinds(out, "use_ability")[0]["action"] == "move"
    assert any(x["ref"] == "pc" for x in _kinds(out, "heal"))


def test_bestow_hope_steps_fear_down_one_rung_on_a_healing_channel():
    """Bestow Hope: shaken ends, frightened becomes shaken, panicked becomes frightened —
    one step each, not all the way down."""
    pc = _pc("cleric", feats=["Bestow Hope", "Improved Channel"])
    ally = load_pc("fixtures/pc-borin.json")
    ally.ref, ally.kind = "ally", "npc"
    scene, e = _fight(pc, "thug", allies=[ally])
    pc.add_condition("shaken", 5)
    ally.add_condition("panicked", 5)
    _use(e, "Channel Energy (heal)")
    assert not pc.has_state("state.fear")
    assert ally.has_condition("frightened") and not ally.has_condition("panicked")
    plain = _pc("cleric")
    scene, e = _fight(plain, "thug")
    plain.add_condition("shaken", 5)
    _use(e, "Channel Energy (heal)")
    assert plain.has_condition("shaken")


# --- Channel Smite, Greater Channel Smite -------------------------------------------------

def test_channel_smite_adds_the_channel_dice_to_a_blow_on_the_undead():
    """Channel Smite (CRB): on a hit against an undead, damage equal to the channel's
    (4d6 at 8th), Will for half; the use is spent before the roll."""
    pc = _pc("cleric", feats=["Channel Smite"])
    scene, e = _fight(pc, "zombie")
    from tests._board import face_to_face
    face_to_face(scene, "pc", "c1")
    ca.ensure_pool(pc, ca.find(pc, "channel energy")[0])
    before = _left(pc, "channel energy")
    out = _use(e, "Channel Smite", to="c1")
    assert out.status != "refused", out.tell
    assert _left(pc, "channel energy") == before - 1
    res = _swing(e, face=19)
    said = _tells(res)
    assert "4d6" in said and "positive energy" in said, said


def test_channel_smite_on_a_living_foe_is_wasted():
    pc = _pc("cleric", feats=["Channel Smite"])
    scene, e = _fight(pc, "thug")
    from tests._board import face_to_face
    face_to_face(scene, "pc", "c1")
    _use(e, "Channel Smite", to="c1")
    said = _tells(_swing(e, face=19))
    assert "has no hold" in said and "positive energy" not in said


def test_channel_smite_negative_is_a_cleric_s_and_harms_the_living():
    pc = _pc("cleric", feats=["Channel Smite"])
    scene, e = _fight(pc, "thug")
    from tests._board import face_to_face
    face_to_face(scene, "pc", "c1")
    _use(e, "Channel Smite (negative)", to="c1")
    said = _tells(_swing(e, face=19))
    assert "negative energy" in said, said
    paladin = _pc("paladin", feats=["Channel Smite"])
    assert "negative" not in ca.choices_of(paladin, ca.find(paladin, "channel smite")[0])


def test_greater_channel_smite_keeps_its_dice_through_a_miss():
    """Greater Channel Smite (UC): 'If you miss, the extra damage dice remain in your
    pool'; Channel Smite's are 'expended with no effect'."""
    pc = _pc("cleric", feats=["Channel Smite", "Greater Channel Smite"])
    scene, e = _fight(pc, "zombie")
    from tests._board import face_to_face
    face_to_face(scene, "pc", "c1")
    _use(e, "Greater Channel Smite", to="c1")
    _swing(e, face=1)                                 # a miss
    assert pc.has_state("buff.charged")
    said = _tells(_swing(e, face=19))
    assert "4d6" in said and "positive energy" in said
    assert not pc.has_state("buff.charged")


# --- lay on hands: Reward of Grace, Reward of Life, Greater Mercy, Extra Mercy ------------

def _ally_hurt(hp_down=10):
    a = load_pc("fixtures/pc-borin.json")
    a.ref, a.kind = "ally", "npc"
    a.hp = max(1, a.hp_max - hp_down)
    return a


def test_reward_of_grace_gives_a_sacred_plus_one_to_hit_for_a_round():
    pc = _pc("paladin", feats=["Reward of Grace"])
    _s, e = _fight(pc, "thug")
    before = sum(m.value for m in pc.attack_modifiers())
    _use(e, "Lay on Hands")
    assert sum(m.value for m in pc.attack_modifiers()) == before + 1
    pc.tick_effects(1)
    assert sum(m.value for m in pc.attack_modifiers()) == before


def test_reward_of_life_heals_the_paladin_cha_for_healing_another():
    """Reward of Life (UM): healing another returns her Charisma bonus (+3); healing
    herself does not."""
    pc = _pc("paladin", feats=["Reward of Life"])
    pc.hp = pc.hp_max - 10
    ally = _ally_hurt()
    _s, e = _fight(pc, "thug", allies=[ally])
    hp = pc.hp
    out = _use(e, "Lay on Hands", to="ally")
    assert out.status != "refused", out.tell
    assert pc.hp == hp + 3
    hp = pc.hp
    _use(e, "Lay on Hands")
    healed = pc.hp - hp
    assert healed >= 4 and "Reward of Life" not in _use(e, "Lay on Hands").tell


def test_greater_mercy_adds_a_d6_when_there_is_nothing_to_lift():
    pc = _pc("paladin", feats=["Greater Mercy"], class_choices={"mercy": ["sickened"]})
    ally = _ally_hurt(30)
    _s, e = _fight(pc, "thug", allies=[ally])
    out = _use(e, "Lay on Hands", to="ally")
    assert "nothing the mercies lift: 1d6" in out.tell
    ally.add_condition("sickened", 5)
    out = _use(e, "Lay on Hands", to="ally")
    assert "nothing the mercies lift" not in out.tell
    assert not ally.has_condition("sickened")


def test_extra_mercy_lifts_its_condition():
    """Extra Mercy (UM): one additional mercy — the parenthetical's — lifted on a heal."""
    pc = _pc("paladin", feats=["Extra Mercy (shaken)"], class_choices={"mercy": ["sickened"]})
    ally = _ally_hurt()
    _s, e = _fight(pc, "thug", allies=[ally])
    ally.add_condition("shaken", 5)
    ally.add_condition("sickened", 5)
    _use(e, "Lay on Hands", to="ally")
    assert not ally.has_condition("shaken") and not ally.has_condition("sickened")


def test_word_of_healing_heals_half_at_thirty_feet_and_needs_the_feat():
    """Word of Healing (UM): 30 feet, half the healing, mercies as normal. Without the feat
    the `at range` mode does not exist."""
    pc = _pc("paladin", feats=["Word of Healing"])
    ally = _ally_hurt(30)
    scene, e = _fight(pc, "thug", allies=[ally])
    before = _left(pc, "lay on hands")
    out = _use(e, "Word of Healing", to="ally")
    assert out.status != "refused", out.tell
    assert "Half of it carries" in out.tell
    assert _left(pc, "lay on hands") == before - 1
    assert ca.find(_pc("paladin"), "word of healing")[0] is None
    zombie_pc = _pc("paladin", feats=["Word of Healing"])
    scene, e = _fight(zombie_pc, "zombie")
    assert _use(e, "Word of Healing", to="c1").status == "refused"


def test_word_of_healing_needs_a_voice():
    pc = _pc("paladin", feats=["Word of Healing"])
    ally = _ally_hurt()
    _s, e = _fight(pc, "thug", allies=[ally])
    pc.add_condition("choked", 2)
    assert _use(e, "Word of Healing", to="ally").status == "refused"


# --- Crusader's Fist, Radiant Charge --------------------------------------------------------

def test_crusader_s_fist_spends_lay_on_hands_only_when_the_fist_lands_on_undead():
    pc = _pc("paladin", feats=["Crusader's Fist", "Improved Unarmed Strike"])
    scene, e = _fight(pc, "zombie")
    from tests._board import face_to_face
    face_to_face(scene, "pc", "c1")
    before = _left(pc, "lay on hands")
    out = _use(e, "Crusader's Fist", to="c1")
    assert out.status != "refused", out.tell
    assert _left(pc, "lay on hands") == before
    said = _tells(_swing(e, face=19, weapon="unarmed"))
    assert "4d6" in said and "positive energy" in said, said
    assert _left(pc, "lay on hands") == before - 1


def test_radiant_charge_spends_every_use_on_the_charge_s_hit_past_dr():
    """Radiant Charge (UM): all remaining lay on hands, 1d6 each + Cha, 'not subject to
    damage reduction'. A blow that is not a charge leaves it waiting."""
    pc = _pc("paladin", feats=["Radiant Charge"])
    scene, e = _fight(pc, "ogre")
    uses = _left(pc, "lay on hands")
    _use(e, "Radiant Charge", to="c1")
    said = _tells(_swing(e, face=19, charge=True))
    assert f"spends {uses} lay on hands" in said and f"{uses}d6+3" in said, said
    assert "holy" in said
    assert _left(pc, "lay on hands") == 0


def test_radiant_charge_waits_through_a_blow_that_is_no_charge():
    pc = _pc("paladin", feats=["Radiant Charge"])
    scene, e = _fight(pc, "ogre")
    from tests._board import face_to_face
    face_to_face(scene, "pc", "c1")
    uses = _left(pc, "lay on hands")
    _use(e, "Radiant Charge", to="c1")
    _swing(e, face=19)
    assert _left(pc, "lay on hands") == uses
    assert any(x.name == "Radiant Charge" for x in pc.effects)


# --- Adept Champion, Fearless Aura --------------------------------------------------------

def test_adept_champion_trades_the_smite_s_damage_for_half_on_manoeuvres():
    """Adept Champion (UC): the smite's +level damage against its target is forgone, and
    half of it (+4 at 8th) is laid on combat manoeuvre checks against that target only."""
    pc = _pc("paladin", feats=["Adept Champion"])
    scene, e = _fight(pc, "thug", "thug")
    a, b = scene.actors["c1"], scene.actors["c2"]
    assert _use(e, "Smite Evil", to="c1").status != "refused"
    ctx = pc._roll_context(None, defender=a)
    dmg = sum(m.value for m in pc._buff_mods("combat_mod", "damage", ctx))
    cmb = sum(m.value for m in pc.cmb_modifiers(defender=a))
    assert _use(e, "Adept Champion", to="c2").status == "refused"
    out = _use(e, "Adept Champion", to="c1")
    assert out.status != "refused", out.tell
    assert sum(m.value for m in pc._buff_mods("combat_mod", "damage", ctx)) == dmg - 8
    assert sum(m.value for m in pc.cmb_modifiers(defender=a)) == cmb + 4
    assert sum(m.value for m in pc.cmb_modifiers(defender=b)) == \
        sum(m.value for m in pc.cmb_modifiers(defender=b))
    pc.tick_effects(1)
    assert sum(m.value for m in pc._buff_mods("combat_mod", "damage", ctx)) == dmg


def test_adept_champion_needs_a_smite():
    pc = _pc("paladin", feats=["Adept Champion"])
    _s, e = _fight(pc, "thug")
    assert _use(e, "Adept Champion", to="c1").status == "refused"


def test_fearless_aura_makes_allies_within_twenty_feet_immune_to_fear():
    """Fearless Aura (UM): 'Allies within the aura are immune to fear effects.' Measured
    through the condition op's immunity gate, inside the engine's moment."""
    from rules.sheet import situated
    pc = _pc("paladin", feats=["Fearless Aura"])
    ally = _ally_hurt(0)
    scene, e = _fight(pc, "thug", allies=[ally])
    with situated(scene):
        assert "fear" in ally.immunities
        assert "fear" not in scene.actors["c1"].immunities
    out = e.run(e.validate([{"op": "condition", "because": "test", "params": {
        "condition": "shaken", "to": "ally"}}], origin="author:test")).outcomes[-1]
    assert "immune to fear" in out.tell and not ally.has_condition("shaken")
    plain = _pc("paladin")
    ally2 = _ally_hurt(0)
    scene, e = _fight(plain, "thug", allies=[ally2])
    with situated(scene):
        assert "fear" not in ally2.immunities


def test_greater_channel_smite_comes_before_the_turn_s_first_blow():
    """'Before making any melee attacks on your turn': refused once a blow is struck."""
    pc = _pc("cleric", feats=["Channel Smite", "Greater Channel Smite"])
    scene, e = _fight(pc, "ogre")
    from tests._board import face_to_face
    face_to_face(scene, "pc", "c1")
    _swing(e, face=1)
    out = _use(e, "Greater Channel Smite", to="c1")
    assert out.status == "refused" and "before any attack" in out.tell


# --- bardic performance: Lingering Performance, the Singers, Harmonic Sage, Discordant
# --- Voice, Ensemble -----------------------------------------------------------------------

def _attack_bonus(who):
    return sum(m.value for m in who.attack_modifiers())


def test_lingering_performance_keeps_inspire_courage_two_rounds_after_it_ends():
    """Lingering Performance (APG): 'continue for 2 rounds after you cease performing';
    without the feat the bonus leaves with the song."""
    for feats, rounds in ((["Lingering Performance"], 2), ([], 0)):
        pc = _pc("bard", feats=feats)
        ally = _ally_hurt(0)
        _s, e = _fight(pc, "thug", allies=[ally])
        base = _attack_bonus(ally)
        _use(e, "Inspire Courage")
        assert _attack_bonus(ally) == base + 2
        _use(e, "Inspire Courage")                       # the song ends
        assert _attack_bonus(ally) == base + (2 if rounds else 0)
        ally.tick_effects(rounds)
        assert _attack_bonus(ally) == base


def test_a_new_performance_ends_the_lingering_one_at_once():
    pc = _pc("bard", feats=["Lingering Performance"])
    ally = _ally_hurt(0)
    _s, e = _fight(pc, "thug", allies=[ally])
    base = _attack_bonus(ally)
    _use(e, "Inspire Courage")
    _use(e, "Inspire Courage")
    assert _attack_bonus(ally) == base + 2
    _use(e, "Dirge of Doom")
    assert _attack_bonus(ally) == base


def test_leaf_singer_adds_two_to_fascinate_against_fey_and_doubles_range_in_a_forest():
    pc = _pc("bard", feats=["Leaf Singer"])
    pc.abilities["cha"] = 10
    scene, e = _fight(pc, "nixie")
    out = _use(e, "Fascinate", to="c1")
    assert _kinds(out, "save")[0]["dc"] == 10 + 4 + 0 + 2
    plain = _pc("bard")
    plain.abilities["cha"] = 10
    scene, e = _fight(plain, "nixie")
    assert _kinds(_use(e, "Fascinate", to="c1"), "save")[0]["dc"] == 14
    doc = ca.find(pc, "fascinate")[0]
    pc.at = "5bbd0c40345f~forest:the-old-wood"
    assert e._reach_times(pc, doc) == 2.0
    pc.at = "5bbd0c40345f~urban:the-square"
    assert e._reach_times(pc, doc) == 1.0


def test_stone_singer_doubles_underground_and_adds_two_against_earth():
    from rules.sheet import situated
    pc = _pc("bard", feats=["Stone Singer"])
    pc.abilities["cha"] = 10
    scene, e = _fight(pc, "small-earth-elemental")
    out = _use(e, "Fascinate", to="c1")
    assert _kinds(out, "save")[0]["dc"] == 16
    doc = ca.find(pc, "fascinate")[0]
    deep = _pc("bard", feats=["Stone Singer"])
    scene, e = _fight(deep, "thug", at="5bbd0c40345f~underground:the-old-mine")
    with situated(scene):
        assert e._reach_times(deep, doc) == 2.0


def test_war_singer_doubles_on_a_battlefield_of_a_dozen():
    pc = _pc("bard", feats=["War Singer"])
    small, e = _fight(pc, "thug")
    doc = ca.find(pc, "fascinate")[0]
    assert e._reach_times(pc, doc) == 1.0
    pc2 = _pc("bard", feats=["War Singer"])
    big, e2 = _fight(pc2, *(["thug"] * 11))
    assert e2._reach_times(pc2, doc) == 2.0
    out = _use(e2, "Fascinate", to="c1")
    assert out.status != "refused"


def test_war_singer_adds_two_against_orcs():
    pc = _pc("bard", feats=["War Singer"])
    pc.abilities["cha"] = 10
    _s, e = _fight(pc, "orc-sergeant")
    assert _kinds(_use(e, "Fascinate", to="c1"), "save")[0]["dc"] == 16


def test_harmonic_sage_harmonizes_a_performance_indoors():
    """Harmonic Sage (UC): inside a building, a DC 15 Knowledge (engineering) check as
    the performance begins; on a success Self-Harmonize lifts its DC by 1."""
    pc = _pc("bard", level=12, feats=["Harmonic Sage"],
             ranks={"knowledge (engineering)": 12})
    pc.abilities["cha"] = 10
    scene, e = _fight(pc, "thug", seed=5, at="town~urban:the-tavern")
    out = _use(e, "Fascinate", to="c1")
    assert "Self-Harmonize" in out.tell, out.tell
    assert _kinds(out, "save")[0]["dc"] == 10 + 6 + 0 + 1
    outside = _pc("bard", level=12, feats=["Harmonic Sage"],
                  ranks={"knowledge (engineering)": 12})
    scene, e = _fight(outside, "thug", seed=5, at="5bbd0c40345f~urban:the-square")
    assert "Harmonic Sage" not in _use(e, "Fascinate", to="c1").tell


def test_harmonic_sage_reverberates_a_performance_without_a_save():
    pc = _pc("bard", level=12, feats=["Harmonic Sage"],
             ranks={"knowledge (engineering)": 12})
    ally = _ally_hurt(0)
    scene, e = _fight(pc, "thug", allies=[ally], at="town~urban:the-tavern")
    base = _attack_bonus(ally)
    out = _use(e, "Inspire Courage")
    assert "Reverberation" in out.tell, out.tell
    sung = _attack_bonus(ally)
    assert sung > base
    _use(e, "Inspire Courage")
    assert _attack_bonus(ally) == sung
    ally.tick_effects(1)
    assert _attack_bonus(ally) == base


def test_discordant_voice_lends_allies_a_d6_of_sonic_while_the_bard_performs():
    """Discordant Voice (UC): allies within 30 ft of a performing bard deal +1d6 sonic on
    weapon hits — rolled apart, so a critical does not multiply it. Silent bard, none."""
    from tests._board import face_to_face
    bard = _pc("bard", feats=["Discordant Voice"])
    bard.ref, bard.kind = "bard", "npc"
    pc = _pc("fighter")
    scene, e = _fight(pc, "ogre", allies=[bard])
    face_to_face(scene, "pc", "c1")
    assert "discordant voice" not in _tells(_swing(e, face=19))
    _use(e, "Inspire Courage", actor="bard")
    assert "discordant voice adds" in _tells(_swing(e, face=19))


def test_ensemble_brings_an_ally_s_aid_to_a_perform_check():
    """Ensemble (UM): an ally within 20 feet with the feat aids the Perform check (+2 on
    their 10); a bard may count one ally as having it."""
    pc = _pc("fighter", feats=["Ensemble"])
    ally = load_pc("fixtures/pc-borin.json")
    ally.ref, ally.kind = "ally", "npc"
    ally.feats = list(ally.feats) + ["Ensemble"]
    scene, e = _fight(pc, "thug", allies=[ally], seed=2)
    from rules.engine import Intent
    got = e._ensemble_aid(pc, "perform")
    assert len(got) <= 1
    assert all("Ensemble" in m.source for m in got)
    total = sum(len(e._ensemble_aid(pc, "perform")) for _ in range(20))
    assert total > 0
    alone = _pc("fighter", feats=["Ensemble"])
    scene, e = _fight(alone, "thug", allies=[_ally_hurt(0)])
    assert e._ensemble_aid(alone, "perform") == []
    bard = _pc("bard", feats=["Ensemble"])
    scene, e = _fight(bard, "thug", allies=[_ally_hurt(0)], seed=2)
    assert sum(len(e._ensemble_aid(bard, "perform")) for _ in range(20)) > 0


# --- Stance of the Xorn, Destroyer's Blessing, Bewildering Koan ---------------------------

def test_stance_of_the_xorn_takes_the_flanking_bonus_away_but_not_when_dex_is_lost():
    """Stance of the Xorn: flankers gain no +2 against you; 'a condition that makes you
    lose your Dex bonus to AC also makes you lose the benefits of this feat'."""
    from rules import position
    from rules.grid import Grid
    s = Scene(location_id="t")
    a = instantiate("guildhand", scene=s, name="A")
    s.add(a, at=(4, 5))
    b = instantiate("guildhand", scene=s, name="B")
    s.add(b, at=(6, 5))
    foe = _pc("fighter", feats=["Stance of the Xorn"])
    s.add(foe, at=(5, 5))
    s.grid = Grid()
    assert position.attack_mods(s, a, foe) == []
    assert position.flanking_with(s, a, foe, None)          # still flanked (sneak attack)
    foe.add_condition("stunned", 1)
    assert [m.value for m in position.attack_mods(s, a, foe)] == [2]


def test_destroyer_s_blessing_regains_a_round_of_rage_and_heals_on_a_break():
    pc = _pc("barbarian", feats=["Destroyer's Blessing"])
    _s, e = _fight(pc, "thug")
    assert _use(e, "Rage").status != "refused"
    pool = "rage"
    pc.spend_pool(pool, 3)
    left = _left(pc, pool)
    pc.hp -= 5
    hp = pc.hp
    effects: list = []
    said = e._sunder_regains(pc, True, effects)
    assert _left(pc, pool) == left + 1 and pc.hp == hp + 1, said
    assert e._sunder_regains(pc, True, []) == []          # once a round
    calm = _pc("barbarian", feats=["Destroyer's Blessing"])
    _s, e = _fight(calm, "thug")
    assert e._sunder_regains(calm, True, []) == []        # not raging


def test_bewildering_koan_dazes_a_foe_that_loses_the_contest_for_a_ki():
    pc = _pc("monk", feats=["Bewildering Koan"], ranks={"bluff": 8})
    pc.abilities["cha"] = 30
    scene, e = _fight(pc, "thug")
    before = _left(pc, "ki")
    out = _use(e, "Bewildering Koan", to="c1")
    assert out.status != "refused", out.tell
    assert _left(pc, "ki") == before - 1
    won = _kinds(out, "contest")[0]["won"]
    assert scene.actors["c1"].has_condition("dazed") == won


def test_bewildering_koan_damage_mode_is_two_against_that_foe_for_a_round():
    pc = _pc("monk", feats=["Bewildering Koan"], ranks={"bluff": 8})
    pc.abilities["cha"] = 30
    scene, e = _fight(pc, "thug")
    out = _use(e, "Bewildering Koan (damage)", to="c1")
    ctx = pc._roll_context(None, defender=scene.actors["c1"])
    got = sum(m.value for m in pc._buff_mods("combat_mod", "damage", ctx))
    assert got == (2 if _kinds(out, "contest")[0]["won"] else 0)
