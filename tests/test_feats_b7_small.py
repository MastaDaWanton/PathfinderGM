"""Feat loop batch 7, lane b7-small (2026-11-27): the partial feats whose missing clause
is one small book rule of its own (docs/feats-partial-ledger.md, groups 13-49 this lane
holds). Each test names what the engine did before the clause was built.
"""
from __future__ import annotations

from rules.dice import Dice
from tests.test_feats_b4_moves import _attack, _board, _pc, _tells


def _bleeds(actor):
    return [e for e in actor.effects if e.key == "bleed"]


def test_tiger_style_bleeds_a_slashing_critical_for_two_turns_only():
    """UC, Tiger Style: "Whenever you score a critical hit with your slashing unarmed
    strike, your opponent also takes 1d4 points of bleed damage at the start of his next
    two turns." Measured before: no bleed was laid at all (a bleed here ran until healed,
    so the document could not say "two turns"). Now the crit lays a 1d4 bleed that fires
    twice and ends by itself."""
    pc = _pc("monk", feats=["Improved Unarmed Strike", "Tiger Style"], equipped="unarmed")
    s, e = _board(pc, ("ogre", (6, 5)), faces={"Attack with": 20, "Confirm": 20})
    res = _attack(e, weapon="unarmed")
    foe = s.actors["c1"]
    assert "for 2 rounds" in _tells(res), _tells(res)
    assert len(_bleeds(foe)) == 1
    hp = foe.hp
    fired = [foe.run_periodic("round", 1, Dice(seed=1)) for _ in range(3)]
    hits = [r for rnd in fired for r in rnd if r["kind"] == "damage"]
    assert len(hits) == 2 and foe.hp < hp
    assert not _bleeds(foe)


def test_tiger_style_lays_no_bleed_on_an_ordinary_hit():
    """The bleed is the critical's only: a plain hit (no confirmation) bleeds nobody."""
    pc = _pc("monk", feats=["Improved Unarmed Strike", "Tiger Style"], equipped="unarmed")
    s, e = _board(pc, ("ogre", (6, 5)), faces={"Attack with": 15, "Confirm": 1})
    _attack(e, weapon="unarmed")
    assert not _bleeds(s.actors["c1"])


def _halfling(*feats):
    return _pc("fighter", feats=["Cautious Fighter", *feats], race="halfling")


def _aoo(e, faces=None):
    from rules.intents import Intent
    from tests.test_feats_b4_moves import _settle

    raw = Intent(op="attack", actor="pc", target="c1", visibility="hidden", because="test",
                 params={"reaction": "attack_of_opportunity", "provoked_by": "movement"})
    return _settle(e, e.run([raw]))


def _in_total_defense(e):
    from tests.test_feats_b4_moves import _run

    res = _run(e, {"op": "total_defense", "actor": "pc"})
    assert res.outcomes[-1].status == "resolved", _tells(res)


def test_desperate_swing_lets_one_attack_of_opportunity_through_total_defense():
    """ARG, Desperate Swing: "Once per day, you can make a single melee attack while
    taking the total defense action. You take a -4 penalty". Measured before: total
    defense's `reactions.none` refused every attack of opportunity, the feat's included.
    Now the first is offered at -4 and the day is spent; the second is refused again."""
    from rules import reactions
    from tests.test_feats_b4_moves import _named, _rolls

    pc = _halfling("Desperate Swing")
    s, e = _board(pc, ("thug", (6, 5)), faces={"Attack with": 12})
    _in_total_defense(e)
    assert reactions.reactions_for(pc)
    roll = _rolls(_aoo(e), "Attack with")[0]
    assert _named(roll, "Desperate Swing") == -4
    assert not reactions.reactions_for(pc)

    plain = _halfling()
    s2, e2 = _board(plain, ("thug", (6, 5)))
    _in_total_defense(e2)
    assert not reactions.reactions_for(plain)


def test_desperate_swing_confirms_at_plus_four_while_fighting_defensively():
    """"+4 bonus on critical confirmation rolls made while fighting defensively".
    Measured before: the confirmation carried only the swing's own terms."""
    from tests.test_feats_b4_moves import _named, _rolls

    def confirm(feats):
        pc = _halfling(*feats)
        s, e = _board(pc, ("thug", (6, 5)), faces={"Attack with": 20, "Confirm": 10})
        return _rolls(_attack(e, fighting_defensively=True), "Confirm")[0]

    assert _named(confirm(["Desperate Swing"]), "Desperate Swing") == 4
    assert _named(confirm([]), "Desperate Swing") == 0


def test_surprise_strike_waives_the_desperate_swing_penalty_once_a_day():
    """ARG, Surprise Strike: "Once per day, when fighting defensively or making an attack
    of opportunity while taking the total defense action with the Desperate Swing feat,
    you take no penalty on the attack roll." Measured before: Desperate Swing did not run,
    so there was no penalty to waive. Now the desperate swing carries no -4; and a
    fighting-defensively attack the same day keeps its -4, the day being spent."""
    from tests.test_feats_b4_moves import _named, _rolls
    from tests._board import new_turn

    pc = _halfling("Desperate Swing", "Surprise Strike")
    s, e = _board(pc, ("thug", (6, 5)), faces={"Attack with": 12})
    _in_total_defense(e)
    roll = _rolls(_aoo(e), "Attack with")[0]
    assert _named(roll, "Desperate Swing") == 0
    new_turn(s)
    roll = _rolls(_attack(e, fighting_defensively=True), "Attack with")[0]
    assert _named(roll, "Surprise Strike") == 0 and _named(roll, "Fighting defensively") == -4


def test_surprise_strike_waives_fighting_defensively_s_penalty_on_one_roll():
    """The waiver's other half: the first fighting-defensively attack of the day takes
    no -4 (+4 against the stance's -4), and the next day's is spent."""
    from tests.test_feats_b4_moves import _named, _rolls
    from tests._board import new_turn

    pc = _halfling("Desperate Swing", "Surprise Strike")
    s, e = _board(pc, ("thug", (6, 5)), faces={"Attack with": 12})
    roll = _rolls(_attack(e, fighting_defensively=True), "Attack with")[0]
    assert _named(roll, "Surprise Strike") == 4
    new_turn(s)
    roll = _rolls(_attack(e, fighting_defensively=True), "Attack with")[0]
    assert _named(roll, "Surprise Strike") == 0


def test_blind_fight_takes_an_invisible_attacker_s_melee_edge_away():
    """CRB, Blind-Fight: "An invisible attacker gets no advantages related to hitting you
    in melee. That is, you don't lose your Dexterity bonus to Armor Class, and the
    attacker doesn't get the usual +2 bonus for being invisible. The invisible attacker's
    bonuses do still apply for ranged attacks." Measured before: nothing read the clause,
    so an invisible thug denied the fighter his Dexterity and swung at +2 regardless."""
    from tests.test_feats_b4_moves import _named, _rolls

    def swing(feats):
        pc = _pc("fighter", feats=feats)
        s, e = _board(pc, ("thug", (6, 5)), faces={"Attack with": 12})
        thug = s.actors["c1"]
        thug.add_condition("invisible", 10)
        roll = _rolls(_attack(e, by="c1", target="pc"), "Attack with")[0]
        return e._unseen_attacker(pc, thug, melee=True), \
            e._unseen_attacker(pc, thug, melee=False), _named(roll, "no invisible edge")

    assert swing([]) == (True, True, 0)
    assert swing(["Blind-Fight"]) == (False, True, -2)


def test_extra_channel_gives_a_paladin_four_lay_on_hands_only_for_channelling():
    """CRB, Extra Channel (Special): "If a paladin with the ability to channel positive
    energy takes this feat, she can use lay on hands four additional times a day, but
    only to channel positive energy." Measured before: nothing was added (her uses were
    one pool). Now two channels are paid from the four extra uses, lay on hands itself
    never touches them, and the third channel is paid from lay on hands."""
    from tests._board import new_turn
    from tests.test_feats_b4_moves import _use

    pc = _pc("paladin", level=6, feats=["Extra Channel"])
    pc.rebuild_pools()
    s, e = _board(pc, ("thug", (8, 5)))
    hands = pc.pool("lay on hands").current
    assert pc.pool("extra channel").current == 4
    for _ in range(2):
        _use(e, "Channel Positive Energy")
        new_turn(s)
    assert pc.pool("extra channel").current == 0 and pc.pool("lay on hands").current == hands
    _use(e, "Channel Positive Energy")
    assert pc.pool("lay on hands").current == hands - 2

    plain = _pc("paladin", level=6)
    plain.rebuild_pools()
    assert plain.pool("extra channel").maximum == 0
    assert all(p["id"] != "extra channel" for p in plain.summary()["pools"])


def _two_blades(feats, monkeypatch, **params):
    from tests.test_feats_b2_attack_a import _board as board2, _swing, _wren
    from tests.test_feats_b4_maneuver import _no_prereqs

    _no_prereqs(monkeypatch)
    pc = _wren(["Two-Weapon Fighting", "Combat Expertise", *feats],
               weapons=["shortsword", "dagger"], equipped="shortsword")
    pc.abilities["cha"] = 40                               # the feint lands
    s, e, thug = board2(pc, foes=["thug"])
    thug.hp_max = thug.hp = 500
    e._ensure_encounter("pc")
    s.positions.update({"pc": (5, 5), thug.ref: (6, 5)})
    return thug, _swing(e, target=thug.ref, face=12, full_attack=True, off_hand="dagger",
                        **params)


def test_two_weapon_feint_trades_the_first_primary_blow_for_a_feint(monkeypatch):
    """UC, Two-Weapon Feint: "While using Two-Weapon Fighting to make melee attacks, you
    can forgo your first primary-hand melee attack to make a Bluff check to feint an
    opponent." Measured before: no declared option existed; a feint was its own standard
    action. Now the full attack has one blow fewer, a feint in front of it, and the next
    blow spends the opening."""
    from tests.test_feats_b4_moves import _rolls

    _, plain = _two_blades(["Two-Weapon Feint"], monkeypatch)
    thug, res = _two_blades(["Two-Weapon Feint"], monkeypatch, two_weapon_feint=True)
    swings = lambda r: len(_rolls(r, "Attack with"))            # noqa: E731
    assert _rolls(res, "Bluff check (feint)"), _tells(res)
    assert swings(res) == swings(plain) - 1
    assert not thug.has_state("state.feinted.pc")


def test_improved_two_weapon_feint_keeps_the_foe_open_for_the_turn(monkeypatch):
    """Improved Two-Weapon Feint: "that opponent is denied his Dexterity bonus to AC until
    the end of your turn" — not only against the next blow."""
    thug, res = _two_blades(["Two-Weapon Feint", "Improved Two-Weapon Feint"], monkeypatch,
                            two_weapon_feint=True)
    assert thug.has_state("state.feinted.pc"), _tells(res)


def test_two_weapon_feint_is_refused_without_an_off_hand(monkeypatch):
    from tests.test_feats_b4_maneuver import _no_prereqs
    from tests.test_feats_b2_attack_a import _board as board2, _wren

    _no_prereqs(monkeypatch)
    pc = _wren(["Two-Weapon Fighting", "Two-Weapon Feint"], weapons=["shortsword"],
               equipped="shortsword")
    s, e, thug = board2(pc, foes=["thug"])
    assert "two-weapon full attack" in e._attack_choice_refusal(
        pc, "shortsword", {"two_weapon_feint": True, "full_attack": True})


def test_impact_critical_shot_can_bull_rush_in_place_of_the_trip(monkeypatch):
    """APG, Impact Critical Shot: "you can push your opponent back as if from the bull
    rush combat maneuver or knock that target prone as if from a trip combat maneuver. If
    you choose to bull rush, you cannot move with the target." Measured before: the
    engine always took the trip. Declared, the shot drives the thug back and the archer
    stays where she stood."""
    from tests.test_feats_b2_attack_a import _board as board2, _swing, _wren
    from tests.test_feats_b4_maneuver import _no_prereqs

    _no_prereqs(monkeypatch)
    pc = _wren(["Point-Blank Shot", "Impact Critical Shot"], equipped="longbow")
    pc.abilities["dex"] = 30
    pc.goods["arrows"] = 20
    s, e, thug = board2(pc, foes=["thug"])
    thug.hp_max = thug.hp = 500
    e._ensure_encounter("pc")
    s.positions.update({"pc": (5, 5), thug.ref: (8, 5)})
    res = _swing(e, target=thug.ref, face=20, impact_bull_rush=True)
    assert not thug.has_condition("prone"), _tells(res)
    assert s.positions[thug.ref][0] > 8 and s.positions["pc"][:2] == (5, 5), _tells(res)
    assert "drives" in _tells(res)


def test_raging_throw_slams_a_bull_rushed_foe_into_the_one_behind_it():
    """UC, Raging Throw: "if you bull rush an opponent into a square another creature
    occupies or into a solid object, the opponent and the creature or object take
    bludgeoning damage equal to your Strength modifier + your Constitution modifier."
    Measured before: the push stopped at the body behind and nobody was hurt. Raging, both
    thugs take Str + Con; not raging, the push only stops."""
    from rules.bestiary import instantiate
    from tests.test_feats_b6_partials import _held_by
    from tests.test_maneuver_outcomes import _do, _fight

    def shove(rage):
        scene, engine, pc, thug = _fight(face=20, strength=30)
        pc.feats = list(pc.feats) + ["Raging Throw"]
        if rage:
            _held_by(pc, "rage", ["buff.stance.rage"])
        other = scene.add(instantiate("thug", scene=scene, name="the other thug"),
                          at=(8, 10))
        hp = (thug.hp, other.hp)
        out = _do(engine, "bull rush")
        n = pc.ability_mod("str") + pc.ability_mod("con")
        return hp[0] - thug.hp, hp[1] - other.hp, n, out.tell

    a, b, n, tell = shove(True)
    assert a == n and b == n and "Raging Throw" in tell, tell
    assert shove(False)[:2] == (0, 0)


def _exposed(feats, rule, hours=1):
    from tests.test_feats_b4_moves import _run

    pc = _pc("fighter", feats=feats)
    pc.hp_max = pc.hp = 400                               # standing through the stretch
    s, e = _board(pc)
    s.initiative, s.round = [], 0                          # out of a fight
    res = _run(e, {"op": "hazard", "actor": "pc",
                   "params": {"rule": rule, "hours": hours, "to": "pc"}})
    out = res.outcomes[-1]
    saves = [r for r in out.rolls if "Fortitude" in r.label]
    burns = [r for r in out.rolls if "(no save)" in r.label]
    return pc, out, saves, burns


def test_severe_and_extreme_cold_are_bands_of_their_own():
    """CRB, Cold Dangers: severe cold (below 0 F) saves "once every 10 minutes"; extreme
    cold (below -20 F) "deals 1d6 points of lethal damage per minute (no save)" beside a
    save. Measured before: the engine had one cold band (below 40 F, a save an hour)."""
    _, _, saves, burns = _exposed([], "severe-cold")
    assert len(saves) == 6 and not burns
    pc, out, saves, burns = _exposed([], "extreme-cold")
    assert burns and len(burns) == len(saves)
    assert "lethal damage" in out.tell and pc.hp < 400


def test_rugged_northerner_steps_severe_and_extreme_cold_down_a_band():
    """ISWG, Rugged Northerner: "You treat extreme cold conditions as severe cold," severe
    as cold, "You are not impacted at all by normal cold weather conditions" and "do not
    become fatigued by frostbite or hypothermia". Measured before: only the one band
    existed, so the step-down had nothing to step."""
    pc, out, saves, burns = _exposed(["Rugged Northerner"], "severe-cold")
    assert not saves and "at home in the cold" in out.tell
    pc, out, saves, burns = _exposed(["Rugged Northerner"], "extreme-cold")
    assert len(saves) == 6 and not burns
    assert not pc.has_state("state.impaired.fatigued")


def test_desert_dweller_treats_heat_one_step_less_severe():
    """ISWG, Desert Dweller: "You treat hot environments as though they were one step
    less severe". Measured before: heat was one row (above 90 F) with no tier to step."""
    _, _, saves, burns = _exposed([], "extreme-heat")
    assert len(saves) == 12 and burns
    _, _, saves, burns = _exposed(["Desert Dweller"], "extreme-heat")
    assert len(saves) == 6 and not burns
    _, out, saves, _ = _exposed(["Desert Dweller"], "severe-heat")
    assert not saves and "at home in the heat" in out.tell


def test_cold_celerity_quickens_its_bearer_in_severe_cold():
    """People of the North, Cold Celerity: "When you are in conditions of severe cold
    (below 0 F), you gain a +2 bonus on initiative checks" (and the +1 on attacks).
    Measured before: only a round after cold damage gave them; severe cold did not exist."""
    pc, *_ = _exposed(["Cold Celerity"], "severe-cold")
    terms = sum(m.value for m in pc.initiative_modifiers() if "Cold Celerity" in m.source)
    assert pc.has_state("buff.cold-celerity") and terms == 2
    plain, *_ = _exposed(["Cold Celerity"], "cold")
    assert not any(e.origin == "rule:cold" and e.key == "cold-quickened"
                   for e in plain.effects)


def test_elven_spirit_adds_two_to_spellcraft_identifying_an_item():
    """Half-elf, Elven Spirit: "a +2 racial bonus on Spellcraft checks made to identify
    the properties of magic items." Measured before: the identify door took the skill's
    plain modifiers. The check that names an item now carries the use, and the use the
    +2; a Spellcraft check naming no item does not."""
    from rules.engine import Engine
    from rules.intents import Intent

    pc = _pc("wizard", feats=["Elven Spirit"], race="half-elf", ranks={"spellcraft": 4})
    study = Intent(op="check", actor="pc", params={"skill": "spellcraft", "item": "ring"})
    plain = Intent(op="check", actor="pc", params={"skill": "spellcraft"})
    ctx = Engine._skill_use_ctx(study, "spellcraft")
    assert ctx == {"skill_use": "identify-item"}
    with_use = sum(m.value for m in pc.skill_modifiers("spellcraft", ctx=ctx))
    without = sum(m.value for m in pc.skill_modifiers(
        "spellcraft", ctx=Engine._skill_use_ctx(plain, "spellcraft")))
    assert with_use - without == 2


def test_smell_fear_reads_a_frightened_subject_with_perception():
    """APG, Smell Fear: use "Perception in place of Sense Motive" against a subject that
    is shaken, frightened or panicked or hides its fear. Measured before: the read was
    always Sense Motive. A nose far keener than the eye for lies reads the shaken man by
    Perception; the calm one still by Sense Motive."""
    from tests.test_skill_uses_mind import _check, _here, _person, _run

    scene, engine, pc = _here(rest=10)
    pc.feats = list(pc.feats) + ["Smell Fear"]
    pc.ranks = dict(pc.ranks or {}, perception=8)
    afraid, calm = _person(scene, "Orrin"), _person(scene, "Wen")
    afraid.add_condition("shaken", 10)
    a = _run(engine, {**_check("sense motive"), "target": afraid.ref})[0]
    b = _run(engine, {**_check("sense motive"), "target": calm.ref})[0]
    assert a.rolls[0].label.startswith("Perception check"), a.rolls[0].label
    assert b.rolls[0].label.startswith("Sense Motive check")


def test_shielded_caster_halves_a_disruptive_foe_s_increase():
    """UM, Shielded Caster: "If an enemy threatening you both has the Disruptive feat or
    another ability that increases concentration check DCs, that increase is halved."
    Measured before: DC 21 beside a Disruptive thug, shielded or not. With an ally who
    holds the feat beside her and in the thug's reach too, DC 19; the ally out of the
    thug's reach, DC 21 again."""
    from tests.test_feats_computed import Loaded, _board as cast_board, _cast, _wizard

    def dc(ally_at):
        pc = _wizard("Shielded Caster")
        s, e = cast_board(pc, Loaded(12))
        s.actors["c1"].feats = ["Disruptive"]
        friend = _pc("fighter", feats=["Shielded Caster"])
        friend.ref, friend.kind = "a1", "npc"
        s.add(friend, at=ally_at)
        s.sides = {"us": ["pc", "a1"], "them": ["c1"]}
        res = _cast(e, defensively=True)
        return [r for r in res.outcomes[0].rolls if r.label.startswith("Concentration")][0]

    shielded = dc((6, 6))                 # beside her, beside the thug
    assert "DC 19" in shielded.label, shielded.label
    assert "DC 21" in dc((4, 4)).label    # beside her, out of the thug's reach


def test_a_chokehold_runs_the_suffocation_ladder_out_of_water():
    """UC, Chokehold: the pinned foe "cannot breathe"; CRB, Suffocation: "A character who
    has no air to breathe can hold her breath for 2 rounds per point of Constitution",
    then Constitution checks, then unconscious, dying, dead. Measured before: the breath
    clock ran only under water, so a choked thug breathed on for ever. Now each round in
    the hold is a round of breath; past it the check, failed, leaves him limp; let go,
    the clock stops."""
    from rules import water
    from tests.test_feats_b2_actions import _attack as act, _grappling, _run as run2

    scene, engine, pc, thug = _grappling(feats=["Chokehold"])
    run2(engine, act(manoeuvre="grapple", chokehold=True))
    assert thug.has_state("state.silenced.choked")
    before = thug.held_breath_rounds
    scene.initiative = [("pc", 20), ("c1", 10)]
    scene.turn = 1
    scene._next_able()                                   # the top of the next round
    assert thug.held_breath_rounds == before + 1
    thug.held_breath_rounds = water.breath_rounds(thug) + 1
    from tests.test_feats_b4_moves import _Faces

    engine.dice = _Faces({"": 1})                        # the check fails
    said = " ".join(engine.breathe())
    assert "chokes for air, and goes limp" in said and thug.hp == 0, said
    engine._end_grapple(thug, pc, "test")
    engine.breathe()
    assert thug.held_breath_rounds == 0


def test_endurance_adds_four_to_a_long_swim_s_hourly_check():
    """CRB, Endurance: "+4 bonus on ... Swim checks made to resist nonlethal damage from
    exhaustion". Measured before: the hourly Swim check (`Engine._an_hour_swum`, DC 20 or
    1d6 nonlethal) read the skill's plain modifiers, so Endurance gave nothing there."""
    from tests.test_swim_checks import _face, _in_the_water

    def hourly(feats):
        s, e, pc, _shark, _at = _in_the_water()
        pc.feats = list(feats)
        seen = []
        _face(e, 25, seen)
        e._an_hour_swum(pc, "calm")
        return next(total for label, total, _ in seen if "an hour in" in label)

    assert hourly(["Endurance"]) - hourly([]) == 4


def test_endurance_reaches_the_forced_march_check():
    """CRB, Endurance: "+4 ... Constitution checks made to avoid nonlethal damage from a
    forced march". The ledger line said a journey never marched past eight hours; the
    forced march has been built since 2026-11-21 (`survival.forced_march`), so the line
    was stale. The check carries the +4."""
    from rules import survival
    from tests.test_feats_b4_moves import _Faces

    def total(feats):
        pc = _pc("fighter", feats=feats)
        toll, said = survival.forced_march(pc, 1, _Faces({"": 10}))
        return toll.checks[0]["total"]

    assert total(["Endurance"]) - total([]) == 4


# --- negative levels (ledger group 46) ------------------------------------------------------

def _drained(faces):
    pc = _pc("fighter", level=6)
    pc.hp_max = pc.hp = 60                                # standing through the drain
    s, e = _board(pc, ("wight", (6, 5)), faces=faces)
    return s, e, pc, s.actors["c1"]


def test_a_wight_s_slam_lays_a_negative_level_through_the_funnel():
    """Bestiary, Wight: "Energy drain (1 level, DC 14)"; Energy Drain and Negative Levels:
    "a cumulative -1 penalty on all ability checks, attack rolls, combat maneuver checks,
    Combat Maneuver Defense, saving throws, and skill checks", "reduces its current and
    total hit points by 5", and the drainer "gains 5 temporary hit points". Measured
    before: the rider was a record reading "negative levels are not applied by the
    engine", and the struck fighter's numbers never moved."""
    s, e, pc, wight = _drained({"Attack with": 18, "Confirm": 1})
    before = {"attack": sum(m.value for m in pc.attack_modifiers()),
              "fort": sum(m.value for m in pc.save_modifiers("fort")),
              "cmd": pc.cmd(), "hp_max": pc.hp_max,
              "climb": sum(m.value for m in pc.skill_modifiers("climb"))}
    res = _attack(e, by="c1", target="pc")
    assert pc.has_state("state.drained.negative-level"), _tells(res)
    assert "negative level" in _tells(res)
    after = {"attack": sum(m.value for m in pc.attack_modifiers()),
             "fort": sum(m.value for m in pc.save_modifiers("fort")),
             "cmd": pc.cmd(), "hp_max": pc.hp_max,
             "climb": sum(m.value for m in pc.skill_modifiers("climb"))}
    assert {k: after[k] - before[k] for k in before} == {
        "attack": -1, "fort": -1, "cmd": -1, "hp_max": -5, "climb": -1}
    assert wight.temp_hp == 5


def test_energy_drain_s_one_save_a_day_on_sheds_it_or_makes_it_permanent():
    """UMR, Energy Drain: after 24 hours "the affected creature must make a Fortitude
    save ... A success removes that level harmlessly, and a failure makes it permanent"
    (each level its own save). Measured before: nothing was laid to save against."""
    from rules import drain
    from tests.test_feats_b4_moves import _Faces

    for face, kept in ((20, 0), (1, 1)):
        pc = _pc("fighter", level=6)
        drain.lay(pc, 1, 14, "a wight's energy drain", "creature:wight", once=True)
        pc.run_periodic("day", 1, _Faces({"": face}))
        assert drain.count(pc) == kept
        if kept:
            left = next(e for e in pc.effects if e.key == drain.KEY)
            assert left.payload["permanent"] and not left.periodic
            pc.run_periodic("day", 1, _Faces({"": 20}))
            assert drain.count(pc) == 1                 # no save left to make


def test_negative_levels_equal_to_hit_dice_kill():
    """"If a creature's negative levels equal or exceed its total Hit Dice, it dies.\""""
    from rules import drain

    pc = _pc("fighter", level=3)
    pc.hp_max = pc.hp = 60
    drain.lay(pc, 2, 14, "drain", "author:test")
    assert not pc.is_dead
    drain.lay(pc, 1, 14, "drain", "author:test")
    assert pc.is_dead
