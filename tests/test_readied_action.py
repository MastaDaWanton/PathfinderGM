"""The readied action (CRB, Combat, "Ready"; feat loop b5-core, rules/readied.py).

Batch 4 left Strike Back, Patient Strike, Spell Bluff's counter clause and every
counterspell PARTIAL on one line: "the engine has no readied action". Measured before this
lane: no op readied anything, a foe walking into a fighter's reach was met by nothing but
the attack of opportunity it never provoked (entering a threatened square provokes
nothing), and a counterspell had no door at all. These tests take each trigger through the
engine: the readied blow lands ahead of the act that triggered it, the readier's count
moves to just ahead of the trigger's maker, and an action not taken lapses at the holder's
next turn.
"""
from __future__ import annotations

from rules import readied
from rules.sheet import from_dict, load_pc, to_dict
from tests.test_feats_b4_moves import _board, _pc, _run, _tells


def _thugs_turn(s, ref="c1"):
    s.turn = [r for r, _ in s.initiative].index(ref)


def _ready(e, trigger="enters_reach", action="attack", **extra):
    return _run(e, {"op": "ready", "actor": "pc",
                    "params": {"trigger": trigger, "action": action, **extra}})


def test_a_foe_walking_into_reach_meets_the_readied_blow_and_the_order_moves():
    """The defect: a thug walked up to a waiting fighter and swung first, every time —
    stepping INTO a threatened square provokes nothing, and nothing else could answer it.
    Readied, the fighter's blow lands as the thug arrives, ahead of the thug's swing, and
    the fighter acts on the thug's count from then on (CRB: "you act immediately ahead of
    the character whose action triggered your readied action")."""
    pc = _pc("fighter", weapons=("longsword",))
    s, e = _board(pc, ("thug", (9, 5)), faces={"Kesst": 15})
    res = _ready(e)
    assert res.outcomes[-1].status == "resolved", _tells(res)
    assert pc.has_state("action.readied.enters_reach")
    assert s.standard_spent.get("pc") == s.round, "readying is the turn's standard action"
    _thugs_turn(s)
    res = _run(e, {"op": "move", "actor": "c1", "params": {"square": [6, 5]}},
               {"op": "attack", "actor": "c1", "target": "pc", "params": {}})
    ops = [(o.op, o.actor) for o in res.outcomes]
    assert ("attack", "pc") in ops, _tells(res)
    assert ops.index(("attack", "pc")) < ops.index(("attack", "c1")), ops
    assert not pc.has_state("action.readied"), "a readied action is spent when taken"
    order = [r for r, _ in s.initiative]
    assert order.index("pc") == order.index("c1") - 1, order


def test_a_readied_action_not_taken_lapses_at_the_holders_next_turn():
    """CRB: "If you come to your next action and have not yet performed your readied
    action, you don't get to take the readied action." Without the lapse the effect would
    sit through the next round's top and fire on the holder's own turn."""
    pc = _pc("fighter", weapons=("longsword",))
    s, e = _board(pc, ("thug", (15, 15)))
    _ready(e)
    assert pc.has_state("action.readied")
    s.advance_turn()                      # the thug's turn
    assert pc.has_state("action.readied"), "still held through the foes' turns"
    s.advance_turn()                      # round 2: the fighter's turn again
    assert not pc.has_state("action.readied")


def test_strike_back_swings_at_a_reach_foe_the_plain_readier_cannot_touch():
    """Strike Back (CRB): "You can ready an action to make a melee attack against any foe
    that attacks you in melee, even if the foe is outside of your reach." An ogre's ten-foot
    reach hits from two squares off; without the feat the readied longsword cannot answer
    it, with it the blow lands first."""
    for feats, swings in (((), False), (("Strike Back",), True)):
        pc = _pc("fighter", level=12, feats=feats, weapons=("longsword",))
        s, e = _board(pc, ("ogre", (8, 5)))
        _ready(e, trigger="attacks_me")
        _thugs_turn(s)
        res = _run(e, {"op": "attack", "actor": "c1", "target": "pc", "params": {}})
        assert (("attack", "pc") in [(o.op, o.actor) for o in res.outcomes]) is swings, \
            (feats, _tells(res))


def test_patient_strike_readies_for_the_whole_round_and_adds_two():
    """Patient Strike: "ready an attack as a full-round action ... +2 bonus on your attack
    roll when your readied action triggers." Without the feat the full-round readying is
    refused; with it both actions are spent and the blow carries +2."""
    plain = _pc("fighter", weapons=("longsword",))
    s, e = _board(plain, ("thug", (9, 5)))
    assert _ready(e, patient=True).outcomes[-1].status == "refused"
    pc = _pc("fighter", feats=("Patient Strike",), weapons=("longsword",))
    s, e = _board(pc, ("thug", (9, 5)))
    assert _ready(e, patient=True).outcomes[-1].status == "resolved"
    assert s.move_spent.get("pc") == s.round == s.standard_spent.get("pc")
    _thugs_turn(s)
    res = _run(e, {"op": "move", "actor": "c1", "params": {"square": [6, 5]}})
    rolls = [r for o in res.outcomes if o.actor == "pc" for r in o.rolls
             if any("Patient Strike" in str(m.source) for m in r.modifiers or ())]
    assert rolls, _tells(res)


def test_a_readied_attack_on_a_caster_forces_the_concentration_check():
    """Distracting spellcasters (CRB, Ready): a readied blow lands before the spell, and
    the caster must make the struck-while-casting check (DC 10 + damage + level)."""
    pc = _pc("fighter", weapons=("longsword",))
    s, e = _board(pc, ("thug", (6, 5)), faces={"Kesst": 18})
    caster = _caster("c1")
    s.people.pop("c1"); s.add(caster, at=(6, 5))
    _ready(e, trigger="casts")
    _thugs_turn(s)
    res = _run(e, {"op": "cast", "actor": "c1", "target": "pc", "visibility": "hidden",
                   "params": {"spell": "magic-missile"}})
    said = _tells(res)
    assert [o.actor for o in res.outcomes][0] == "pc", said
    assert "while casting" in said or "struck" in said, said


def _caster(ref, prepared=("magic-missile", "dispel-magic"), name="Vell the Hedge-Mage",
            feats=()):
    d = to_dict(load_pc("fixtures/pc-kesst.json"))
    d.update({"class": "wizard", "level": 7, "name": name,
              "ranks": {"spellcraft": 7}, "feats": list(feats), "paths": {}})
    a = from_dict(d, ref=ref)
    a.abilities["int"] = 18
    from rules import casting

    casting.define_slots(a)            # the slots of the Intelligence just set
    for sid in prepared:
        a.spellbook = list(dict.fromkeys(list(a.spellbook or ()) + [sid]))
        casting.prepare(a, sid, 1)
    return a


def test_a_readied_counterspell_ruins_the_same_spell():
    """Readying to counterspell (CRB): Spellcraft DC 15 + the spell's level to identify it,
    then the same spell cast to counter it, "automatically ruin[ing] the other
    spellcaster's spell". Both slots are spent, and the cast does nothing."""
    pc = _caster("pc")
    s, e = _board(pc, ("thug", (8, 5)), faces={"Vell": 19})
    foe = _caster("c1")
    s.people.pop("c1"); s.add(foe, at=(8, 5))
    before_pc = pc.pool("spell slot 1").current
    assert _ready(e, trigger="casts", action="counterspell").outcomes[-1].status == "resolved"
    _thugs_turn(s)
    hp = pc.hp
    res = _run(e, {"op": "cast", "actor": "c1", "target": "pc", "visibility": "hidden",
                   "params": {"spell": "magic-missile"}})
    out = res.outcomes[-1]
    assert any(x.get("kind") == "countered" for x in out.effects), out.tell
    assert pc.hp == hp, "a countered missile strikes nobody"
    assert pc.pool("spell slot 1").current == before_pc - 1


def test_a_counterspell_needs_a_caster_and_a_cast_to_answer():
    """The refusals the bar greys with: nobody counters without spells, and a counterspell
    waits on a foe's casting, never on a walk."""
    pc = _pc("fighter", weapons=("longsword",))
    assert readied.refusal(pc, "casts", "counterspell")
    wiz = _caster("pc")
    assert readied.refusal(wiz, "enters_reach", "counterspell")
    assert not readied.refusal(wiz, "casts", "counterspell")
    assert readied.refusal(pc, "whenever", "attack")


def test_a_brace_weapon_set_against_a_charge_deals_double():
    """Readying a weapon against a charge (CRB): "A readied weapon of this type deals
    double damage if you score a hit with it against a charging character." The spear
    carries `brace` (and no reach, which would miss a foe beside it); the thug's charge meets it, and the blow's dice are doubled."""
    pc = _pc("fighter", weapons=("spear",))
    pc.equipped = "spear"
    s, e = _board(pc, ("thug", (11, 5)), faces={"Kesst": 18})
    _ready(e, trigger="charges_me")
    _thugs_turn(s)
    res = _run(e, {"op": "attack", "actor": "c1", "target": "pc",
                   "params": {"charge": True}})
    mine = [o for o in res.outcomes if o.actor == "pc" and o.op == "attack"]
    assert mine, _tells(res)
    dmg = [r for r in mine[0].rolls if "damage" in (r.label or "").lower()]
    assert dmg and dmg[0].die.startswith("2d8"), [r.as_dict() for r in mine[0].rolls]


def test_spell_bluff_masks_the_casting_from_a_counterspeller():
    """Spell Bluff (UM): "If another spellcaster tries to counterspell your casting, she
    adds +4 to her Spellcraft DC when trying to determine your spell." The same roll that
    identifies a magic missile (DC 16) fails at DC 20 against a bluffing caster; with no
    dispel prepared, the missile flies."""
    for feats, countered in (((), True), (("Spell Bluff",), False)):
        pc = _caster("pc", prepared=("magic-missile",), name="Aster")
        s, e = _board(pc, ("thug", (8, 5)), faces={"Aster": 1})
        spellcraft = sum(m.value for m in pc.skill_modifiers(
            "spellcraft", ctx={"skill_use": "identify-casting", "spell_known": True}))
        e.dice.faces["Aster"] = 18 - spellcraft          # a total of 18: 16 <= 18 < 20
        foe = _caster("c1", feats=feats)
        s.people.pop("c1"); s.add(foe, at=(8, 5))
        _ready(e, trigger="casts", action="counterspell")
        _thugs_turn(s)
        res = _run(e, {"op": "cast", "actor": "c1", "target": "pc", "visibility": "hidden",
                       "params": {"spell": "magic-missile"}})
        hit = any(x.get("kind") == "countered" for o in res.outcomes for x in o.effects)
        assert hit is countered, (feats, _tells(res))


def test_wings_of_the_androsphinx_repositions_the_charger_before_its_blow():
    """Wings of the Androsphinx: "If you use a readied action to attack a creature charging
    you, you can roll to attack and then attempt to reposition that creature as a free
    action before it resolves its charge attack." The readied blow, then the reposition,
    both ahead of the charge's own blow, and no swift action spent."""
    pc = _pc("fighter", feats=("Combat Expertise", "Improved Reposition",
                               "Wings of the Androsphinx"), weapons=("longsword",))
    s, e = _board(pc, ("thug", (11, 5)))
    _ready(e, trigger="charges_me")
    _thugs_turn(s)
    res = _run(e, {"op": "attack", "actor": "c1", "target": "pc", "params": {"charge": True}})
    mine = [k for k, o in enumerate(res.outcomes) if o.actor == "pc" and o.op == "attack"]
    theirs = [k for k, o in enumerate(res.outcomes) if o.actor == "c1" and o.op == "attack"]
    assert len(mine) >= 2 and theirs and mine[1] < theirs[0], _tells(res)
    assert "Wings of the Androsphinx" in res.outcomes[mine[1]].because
    assert s.swift_spent.get("pc") is None
