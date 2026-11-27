"""Feat loop batch 5, lane b5-maneuver: each feat's numbers measured through the engine.

Before this batch the thirteen elemental style feats (Djinni, Efreeti, Marid and Shaitan)
each carried a `not_yet` saying "Elemental Fist: the feat has no engine yet" — batch 4
built Elemental Fist and nothing of theirs ran: a Djinni Spirit monk's lightning deafened
nobody, an Efreeti Style miss burned nothing, Djinni Spin was refused by name. The rest of
b5-maneuver.tsv had no document at all. The tests make the real swing, use or manoeuvre
and read the terms it rolled with, the damage it dealt and the state it left.
"""
from __future__ import annotations

import pytest

from rules import feats as feats_mod, styles
from tests.test_feats_b4_combat import _attack, _cond, _monk, _tells, _use


def _style(actor, fid):
    actor.apply_effect(styles.stance(feats_mod.get(fid)))


def _damage(res, dtype):
    return [e for o in res.outcomes for e in o.effects
            if e.get("kind") == "damage" and e.get("type") == dtype]


ELEMENTAL = ["Improved Unarmed Strike", "Elemental Fist"]


# --- the elemental styles ---------------------------------------------------------------

def test_each_style_feat_adds_an_elemental_fist_attempt_a_day():
    """Djinni Style and Djinni Spirit each say "You gain one additional Elemental Fist
    attempt per day". Measured before: an 8th-level monk holding both had 8, as without."""
    scene, engine, pc, thug = _monk(ELEMENTAL + ["Djinni Style", "Djinni Spirit"])
    _use(engine, "elemental fist (electricity)")
    assert pc.pool("elemental fist").maximum == 10


def test_djinni_style_holds_the_fist_to_lightning_and_adds_wisdom_to_it():
    """Djinni Style (UC): "While you are in this style you must use Elemental Fist to deal
    electricity damage and you gain a bonus on electricity damage rolls equal to your
    Wisdom bonus." Djinni Spirit: "Creatures that take electricity damage from your
    Elemental Fist attack must succeed at a Fortitude save ... or be deafened for 1d4
    rounds." Measured before: the cold fist was armed in the stance, the lightning rolled
    a bare 1d6, and the thug heard everything."""
    scene, engine, pc, thug = _monk(ELEMENTAL + ["Djinni Style", "Djinni Spirit"],
                                    faces={"Attack with": 18, "Damage": 2,
                                           "Elemental Fist": 4,
                                           "Fortitude save against djinni spirit": 1})
    pc.abilities["wis"] = 16
    _style(pc, "djinni-style")
    assert _use(engine, "elemental fist (cold)").status != "resolved"
    assert _use(engine, "elemental fist (electricity)").status == "resolved"
    res = _attack(engine, weapon="unarmed")
    zap = _damage(res, "electricity")
    assert zap and zap[0]["amount"] == 4 + 3, _tells(res)
    assert _cond(thug, "deafened") is not None, _tells(res)


def test_djinni_spirit_deafens_only_with_the_fists_lightning_in_the_stance():
    """Out of the stance the follow-up feat does nothing (UC: a feat with a style
    prerequisite works "only while in the stance"), and a cold fist deafens nobody."""
    scene, engine, pc, thug = _monk(ELEMENTAL + ["Djinni Style", "Djinni Spirit"],
                                    faces={"Attack with": 18, "Damage": 2,
                                           "Elemental Fist": 4,
                                           "Fortitude save against djinni spirit": 1})
    _use(engine, "elemental fist (electricity)")
    _attack(engine, weapon="unarmed")
    assert _cond(thug, "deafened") is None


def test_djinni_style_dodges_attacks_of_opportunity_while_attempts_remain():
    """Djinni Style: "while you are using this style and have remaining Elemental Fist
    attempts, you also gain a +2 dodge bonus to Armor Class against attacks of
    opportunity." Measured on the AC line: +2 against a swing a move provoked, none
    against an ordinary blow, none with the pool empty."""
    scene, engine, pc, thug = _monk(ELEMENTAL + ["Djinni Style"])
    _style(pc, "djinni-style")
    _use(engine, "elemental fist (electricity)")
    plain = pc.ac(attacker=thug)
    assert pc.ac(attacker=thug, provoked_by="movement") >= plain + 2
    pc.spend_pool("elemental fist", pc.pool("elemental fist").current)
    assert pc.ac(attacker=thug, provoked_by="movement") < plain + 2 or \
        pc.ac(attacker=thug) < plain


def test_efreeti_style_burns_on_a_miss_and_efreeti_stance_sets_the_foe_alight():
    """Efreeti Style: "if your Elemental Fist melee attack misses while you are using it
    to deal fire damage, you still deal 1d6 points of fire damage to your target."
    Efreeti Stance: "Creatures that take fire damage from your Elemental Fist attack must
    succeed at a Reflex save ... or catch on fire." Measured before: the miss spent the
    fist and did nothing; a hit set nobody alight."""
    scene, engine, pc, thug = _monk(ELEMENTAL + ["Efreeti Style", "Efreeti Stance"],
                                    faces={"Attack with": 2, "Damage": 2,
                                           "Elemental Fist": 5,
                                           "Reflex save against catching fire": 1})
    _style(pc, "efreeti-style")
    _use(engine, "elemental fist")                           # flame, the default
    res = _attack(engine, weapon="unarmed")
    fire = _damage(res, "fire")
    assert fire and fire[0]["amount"] == 5 and "still reaches" in _tells(res), _tells(res)
    engine.dice.faces["Attack with"] = 18
    scene.round += 1
    pc.tick_effects()
    _use(engine, "elemental fist")
    res = _attack(engine, weapon="unarmed")
    assert thug.has_state("state.burning"), _tells(res)


def test_marid_style_reaches_further_with_the_cold_fist_and_marid_spirit_ices_the_foe():
    """Marid Style: "While using this style and Elemental Fist to deal cold damage ...
    your reach with your unarmed strike increases by 5 feet." Marid Spirit: Fortitude or
    "entangled in ice for 1d4 rounds ... a break DC of 15 + your base attack bonus or monk
    level" — the escape op's hold."""
    from rules import reactions

    scene, engine, pc, thug = _monk(ELEMENTAL + ["Marid Style", "Marid Spirit"],
                                    faces={"Attack with": 18, "Damage": 2,
                                           "Elemental Fist": 3,
                                           "Fortitude save against marid spirit": 1})
    _style(pc, "marid-style")
    before = reactions.reach_with(pc, "unarmed")[0]
    _use(engine, "elemental fist (cold)")
    assert reactions.reach_with(pc, "unarmed")[0] == before + 5
    assert reactions.reach_with(pc, "longsword")[0] == before
    _attack(engine, weapon="unarmed")
    ice = _cond(thug, "entangled")
    assert ice is not None
    assert (ice.payload or {})["ends_when"]["escape"]["dc"] == 15 + max(pc.bab, 8)


def test_shaitan_skin_staggers_with_the_acid_fist():
    """Shaitan Skin: "Creatures that take acid damage from your Elemental Fist attack must
    succeed at a Reflex save ... or be staggered for 1 round.\""""
    scene, engine, pc, thug = _monk(ELEMENTAL + ["Shaitan Style", "Shaitan Skin"],
                                    faces={"Attack with": 18, "Damage": 2,
                                           "Elemental Fist": 3,
                                           "Reflex save against shaitan skin": 1})
    _style(pc, "shaitan-style")
    _use(engine, "elemental fist (acid)")
    _attack(engine, weapon="unarmed")
    assert _cond(thug, "staggered") is not None


def test_djinni_spin_spends_two_attempts_and_lands_fist_and_lightning_on_the_adjacent():
    """Djinni Spin: "spend two Elemental Fist attempts ... Creatures adjacent to you take
    your unarmed strike damage plus the electricity damage from your Elemental Fist and
    are deafened for 1d4 rounds" (deafened even on a save, by its prerequisite Djinni
    Spirit). Measured before: "use Djinni Spin" was refused by name."""
    scene, engine, pc, thug = _monk(ELEMENTAL + ["Djinni Style", "Djinni Spirit",
                                                 "Djinni Spin"],
                                    faces={"Djinni Spin": 4,
                                           "Fortitude save against Djinni Spin": 20})
    _style(pc, "djinni-style")
    out = _use(engine, "djinni spin")
    assert out.status == "resolved", out.tell
    assert pc.pool("elemental fist").current == pc.pool("elemental fist").maximum - 2
    kinds = {e.get("type") for e in out.effects if e.get("kind") == "damage"
             and e.get("ref") == thug.ref}
    assert {"electricity", "bludgeoning"} <= kinds, out.tell
    assert _cond(thug, "deafened") is not None, out.tell


def test_djinni_spin_is_refused_out_of_the_stance_and_nothing_is_spent():
    scene, engine, pc, thug = _monk(ELEMENTAL + ["Djinni Style", "Djinni Spirit",
                                                 "Djinni Spin"])
    _use(engine, "elemental fist (electricity)")
    left = pc.pool("elemental fist").current
    assert _use(engine, "djinni spin").status != "resolved"
    assert pc.pool("elemental fist").current == left


@pytest.mark.parametrize("feats,style,use,energy,save,check", [
    (["Efreeti Style", "Efreeti Stance", "Efreeti Touch"], "efreeti-style",
     "efreeti touch", "fire", "Reflex", lambda t: t.has_state("state.burning")),
    (["Marid Style", "Marid Spirit", "Marid Coldsnap"], "marid-style",
     "marid coldsnap", "cold", "Reflex",
     lambda t: (_cond(t, "entangled").payload or {}).get("ends_when", {}).get("escape")),
    (["Shaitan Style", "Shaitan Skin", "Shaitan Earthblast"], "shaitan-style",
     "shaitan earthblast", "acid", "Reflex", lambda t: _cond(t, "staggered") is not None),
])
def test_the_two_attempt_areas_land_fist_and_energy_and_their_rider_on_a_failed_save(
        feats, style, use, energy, save, check):
    """Efreeti Touch's 15-foot cone ("catch on fire"), Marid Coldsnap's 30-foot line
    ("entangled in ice as per the Marid Spirit feat"), Shaitan Earthblast's 5-foot column
    within 30 feet ("staggered for 1 round"): two Elemental Fist attempts, the user's
    unarmed strike plus the energy, the rider on a failed save. Measured before: each was
    a feat with no use at all."""
    scene, engine, pc, thug = _monk(ELEMENTAL + feats, level=12,
                                    faces={f"{save} save against": 1})
    _style(pc, style)
    out = _use(engine, use, to=thug.ref)
    assert out.status == "resolved", out.tell
    kinds = {e.get("type") for e in out.effects if e.get("kind") == "damage"
             and e.get("ref") == thug.ref}
    assert {energy, "bludgeoning"} <= kinds, out.tell
    assert check(thug), out.tell
    assert pc.pool("elemental fist").current == pc.pool("elemental fist").maximum - 2


# --- the defence feats --------------------------------------------------------------------

def test_favored_defense_adds_half_the_favored_enemy_bonus_against_that_enemy_only():
    """Favored Defense (APG): "You add half your favored enemy bonus to your CMD and as a
    dodge bonus to AC when attacked by a favored enemy." Measured before: a ranger with a
    +4 against animals had the same AC and CMD against the wolf as against the thug."""
    from rules.sheet import situated
    from tests.test_feats_b4_combat import _fight

    scene, engine, pc, thug = _fight(feats=["Favored Defense (animal)"], cls="ranger",
                                     level=5, second=[("wolf", (5, 10))])
    pc.class_choices = {"favored enemy": [{"pick": "animal", "bonus": 4},
                                          {"pick": "humanoid-human", "bonus": 2}]}
    wolf = next(a for a in scene.actors.values() if a.has_state("type.animal"))
    with situated(scene):
        assert pc.ac(attacker=wolf) == pc.ac(attacker=thug) + 2
        assert sum(m.value for m in pc.cmd_modifiers(attacker=wolf)) == \
            sum(m.value for m in pc.cmd_modifiers(attacker=thug)) + 2
        assert pc.ac(attacker=wolf, flat_footed=True) == pc.ac(attacker=thug, flat_footed=True)


def test_blundering_defense_lends_half_the_dodge_as_luck_to_allies_beside():
    """Blundering Defense (ARG): "Whenever you fight defensively or use the total defense
    action, allies gain a luck bonus to AC and CMD equal to 1/2 the dodge bonus you gain
    from the action ... only while they are adjacent to you." Total defense's +4 (no
    Acrobatics) lends +2; stepping away takes it back."""
    from rules.engine import Engine
    from rules.sheet import situated
    from tests.test_feats_b4_combat import _fight

    scene, engine, pc, thug = _fight(ally=[((6, 11), ["Blundering Defense"])])
    ally = scene.actors["ally0"]
    ally.ranks = {**(ally.ranks or {}), "acrobatics": 0}
    with situated(scene):
        plain = pc.ac()
        ally.apply_effect(Engine.total_defense_effect(ally))
        assert pc.ac() == plain + 2
        assert "Blundering" not in str(ally.ac_modifiers())
        scene.positions["ally0"] = (6, 14)
        assert pc.ac() == plain


# --- Fury's Snare -------------------------------------------------------------------------

def test_furys_snare_lets_the_whip_go_and_entangles_the_tripped_foe():
    """Fury's Snare (Cheliax): "If you successfully use a whip to trip a foe, you can
    choose to drop your whip. Your tripped target gains the entangled condition ... a DC 10
    Strength check or a DC 15 Escape Artist check." Declared with the trip; the escape op
    reads both DCs. Measured before: the feat did nothing and the option did not exist."""
    from tests.test_feats_b4_combat import _fight

    scene, engine, pc, thug = _fight(feats=["Fury's Fall", "Improved Trip", "Fury's Snare"],
                                     faces={"Trip (CMB)": 19})
    pc.weapons = list(pc.weapons) + ["whip"]
    pc.shield = "none"
    pc.equipped = "whip"
    res = _attack(engine, weapon="whip", manoeuvre="trip", furys_snare=True)
    assert thug.has_state("state.position.prone"), _tells(res)
    snare = _cond(thug, "entangled")
    assert snare is not None, _tells(res)
    esc = snare.payload["ends_when"]["escape"]
    assert (esc["dc"], esc["str_dc"]) == (15, 10)
    assert pc.equipped != "whip"
    out = engine.run(engine.validate([{"op": "escape", "actor": "c1",
                                       "visibility": "hidden", "params": {}}])).outcomes[-1]
    assert "against DC 10" in out.tell or "against DC 15" in out.tell, out.tell


def test_furys_snare_is_refused_without_a_whip():
    from tests.test_feats_b4_combat import _fight

    from rules.intents import IntentError

    scene, engine, pc, thug = _fight(feats=["Fury's Fall", "Improved Trip", "Fury's Snare"])
    with pytest.raises(IntentError, match="whip"):
        engine.validate([{"op": "attack", "actor": "pc", "target": "c1",
                          "params": {"manoeuvre": "trip", "furys_snare": True}}])


# --- Snoutgrip, Body Shield ----------------------------------------------------------------

def test_snoutgrip_grapples_the_biter_that_missed_and_shuts_its_jaws():
    """Snoutgrip (Dragonslayer's Handbook): when a foe "misses you with its bite attack,
    you can attempt a grapple with a -5 penalty ... holding its mouth shut, preventing it
    from using its bite attack ... until it escapes your grapple." Measured before: the
    wolf missed, and nothing happened."""
    from tests.test_feats_b4_combat import _fight

    scene, engine, pc, _ = _fight(feats=["Improved Unarmed Strike", "Improved Grapple",
                                         "Snoutgrip"], foe="wolf",
                                  faces={"Attack with bite": 2, "Grapple (CMB)": 20})
    wolf = scene.actors["c1"]
    res = _attack(engine, by="c1", target="pc", weapon="bite")
    grab = [r for o in res.outcomes for r in o.rolls if r.label.startswith("Grapple (CMB)")]
    assert grab and any(m.value == -5 for m in grab[0].modifiers), _tells(res)
    assert wolf.has_state("state.held") and wolf.has_state("state.silenced.mouth-held"), \
        _tells(res)
    engine.dice.faces["Attack with bite"] = 20
    res = _attack(engine, by="c1", target="pc", weapon="bite")
    assert "jaws are held shut" in _tells(res)


def test_body_shield_turns_a_missed_blow_onto_the_creature_held_in_the_way():
    """Body Shield (UC): grappling an adjacent creature, "make a grapple combat maneuver
    check against that creature to gain cover against a single attack. If you are
    successful and the attack misses you, that attack targets the creature you used as
    cover, using the same attack roll." Measured before: the held thug was no cover, and
    the missed blow went nowhere."""
    from rules.engine import _held_by
    from tests.test_feats_b4_combat import _fight

    scene, engine, pc, held = _fight(feats=["Improved Unarmed Strike", "Improved Grapple",
                                            "Body Shield"],
                                     second=[("thug", (5, 10))],
                                     faces={"Borin Achereth grapple": 20,
                                            "Attack with": 12, "Damage": 3})
    held.add_condition("grappled", 10, source="test")
    _held_by(held, "grappled", "pc", grappler="pc")
    other = next(a for r, a in scene.actors.items() if r not in ("pc", "c1"))
    hp = held.hp
    res = _attack(engine, by=other.ref, target="pc")
    said = _tells(res)
    assert "cover, +4" in said, said
    attacks = [r for o in res.outcomes for r in o.rolls if r.label.startswith("Attack with")]
    assert len(attacks) == 2 and "instead (Body Shield)" in said, said
    assert (attacks[1].natural, attacks[1].total) == (attacks[0].natural, attacks[0].total)
    assert held.nonlethal > 0 or held.hp < hp, said


# --- Dampen Presence ----------------------------------------------------------------------

def test_blindsense_pinpoints_a_hider_unless_it_dampens_its_presence():
    """Blindsense (UMR) "notice[s] and pinpoint[s] the location of creatures within
    range"; Dampen Presence: "You may use the Stealth skill to hide from any creature
    attempting to perceive you using blindsight or blindsense." Measured before: no sense
    but scent and tremorsense located a hider, so blindsense saw nothing and the feat had
    nothing to beat."""
    from rules import awareness
    from rules.activeeffect import ActiveEffect
    from tests.test_feats_b4_combat import _fight

    scene, engine, pc, thug = _fight(feats=["Skill Focus (stealth)", "Dampen Presence"])
    thug.apply_effect(ActiveEffect(name="echoes", kind="buff", key="echoes", source="test",
                                   tags=("sense.blindsense.30",)))
    pc.apply_effect(ActiveEffect(name="sneaking", kind="situation", key="sneaking",
                                 source="test", tags=(awareness.SNEAKING,),
                                 payload={"result": 30}))
    assert awareness.senses(scene, thug, pc) == ""
    pc.feats = [f for f in pc.feats if f != "Dampen Presence"]
    assert awareness.senses(scene, thug, pc) == "pinpoint"


# --- Divert Harm --------------------------------------------------------------------------

def test_divert_harm_wrestles_an_adjacent_foe_into_the_fireball():
    """Divert Harm (Bastards of Golarion): against an area attack that halves on a Reflex
    save, "wrestle an adjacent foe into harm's way ... your opponent must attempt a Reflex
    save against the attack in your place. If your opponent fails, it takes half damage
    from the attack and you take none." Measured before: the rogue rolled her own save."""
    from tests.test_audit_magic import _rogue, caster, fight, records, run, said, scene_with

    pc = caster("wizard", 5, book=("fireball",))
    rogue = _rogue()
    rogue.feats = list(rogue.feats) + ["Divert Harm"]
    pal = _rogue(ref="pal")
    pal.name = "Tamsin"
    pal.add_buff("save_mod", "ref", -40, source="test: always fails")
    s, e = scene_with(pc, rogue, pal)
    e._ensure_encounter("pc")
    fight(s)
    s.sides = {"pc": ["pc", "pal"], "them": ["rogue"]}
    s.positions.update({"pc": (2, 2), "rogue": (10, 10), "pal": (11, 10)})
    s.resync_zones()
    for ref in s.actors:                    # past their first turn: not flat-footed
        s.acted.add(ref) if isinstance(s.acted, set) else s.acted.append(ref)
    res = run(e, "cast", spell="fireball", at=rogue.ref)
    assert rogue.hp == 60, said(res)
    assert "wrestles Tamsin into the" in said(res), said(res)
    assert len([h for h in records(res, "damage") if h["ref"] == "pal"]) == 2


# --- Team Pickpocketing, Stealth Synergy ------------------------------------------------

def test_team_pickpocketing_lifts_a_loose_thing_while_the_partners_feint_holds():
    """Team Pickpocketing (UC): "Whenever an ally with this feat succeeds a Bluff check to
    feint an opponent, if you are adjacent to that creature, you can spend an immediate
    action to make a Sleight of Hand check to pickpocket that opponent and gain a +4
    bonus." Measured before: the feint landed and the ally's hands stayed empty."""
    from tests.test_feats_b4_combat import _fight

    scene, engine, pc, thug = _fight(feats=["Team Pickpocketing"],
                                     ally=[((7, 11), ["Team Pickpocketing"])],
                                     faces={"Bluff check": 20, "Kesst": 16})
    ally = scene.actors["ally0"]
    ally.ranks = {**(ally.ranks or {}), "sleight of hand": 2}
    thug.goods = {"pouch of dice": 1}
    res = engine.run(engine.validate([{"op": "check", "actor": "pc", "target": "c1",
                                       "visibility": "hidden",
                                       "params": {"skill": "bluff", "feint": True}}]))
    said = _tells(res)
    assert "Team Pickpocketing" in said, said
    stolen = [e for o in res.outcomes for e in o.effects if e.get("kind") == "stolen"]
    assert stolen and stolen[0]["ref"] == "ally0", said
    assert not thug.goods.get("pouch of dice")
    lift = [r for o in res.outcomes for r in o.rolls if "Sleight of Hand" in r.label]
    assert lift and any(m.value == 4 for m in lift[0].modifiers)


def test_stealth_synergy_lets_each_hider_keep_the_best_die():
    """Stealth Synergy (UC): "whenever you and your allies make a Stealth check, you all
    take the highest roll and add all your modifiers." The ally hid on a 3; Borin's 17
    raises her result by 14, and his own check keeps his 17."""
    from rules import awareness
    from rules.activeeffect import ActiveEffect
    from tests.test_feats_b4_combat import _fight

    scene, engine, pc, thug = _fight(feats=["Stealth Synergy"],
                                     ally=[((5, 10), ["Stealth Synergy"])],
                                     faces={"Stealth check": 17})
    ally = scene.actors["ally0"]
    ally.apply_effect(ActiveEffect(name="Hidden", kind="condition",
                                   key=awareness.SNEAKING_KEY, source=awareness.STEALTH_ORIGIN,
                                   origin=awareness.STEALTH_ORIGIN,
                                   tags=(awareness.SNEAKING,),
                                   payload={"result": 10, "face": 3}))
    from rules import maneuver_feats

    roll = engine.dice.given(17, [], "Stealth check")
    kept = maneuver_feats.stealth_synergy(engine, pc, roll)
    assert kept.natural == 17
    assert awareness.sneaking(ally).payload["result"] == 24
    low = engine.dice.given(2, [], "Stealth check")
    assert maneuver_feats.stealth_synergy(engine, pc, low).natural == 17
