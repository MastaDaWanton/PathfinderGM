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


def _fight(pc, *foes, allies=(), seed=11):
    scene = Scene()
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
