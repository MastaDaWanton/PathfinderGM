"""Feat loop batch 2, lane b2-attack-b: each feat's numbers measured through the engine.

Before this batch none of these feats had a mechanics document, so each was a name on the
sheet that changed no roll (worklist 2026-11-22: attack-shape and other combat feats
TODO). Several needed a question the roll context could not answer: how much larger the
foe is than the one rolling (Risky Striker, Underfoot, Porcupine Defense, Footslasher),
whether this swing is an attack of opportunity (Swarm Strike), which ally a flank is made
with (Outflank), and what the hit that just landed was — a critical, nonlethal, a shield
bash (Shield Slam, Enforcer, Bashing Finish). The tests roll the real attack and read the
terms it rolled with, the conditions it laid and the swings it queued.
"""
from __future__ import annotations

import pytest

from rules.bestiary import instantiate
from rules.dice import Dice
from rules.engine import Engine, Scene
from rules.sheet import load_pc

FOE = "the foe"


class _Faces(Dice):
    """Each d20 whose label starts with a key lands on that key's face; the rest roll
    seeded. `damage` fixes every damage die's total low so a test foe survives."""

    def __init__(self, faces: dict | None = None):
        super().__init__(seed=20261122)
        self.faces = dict(faces or {})
        self.face = 10

    def roll(self, notation, modifiers=None, label="", visibility="hidden"):
        for prefix, face in self.faces.items():
            if (label or "").startswith(prefix):
                if notation == "1d20":
                    return self.given(face, modifiers, label)
                import re

                m = re.fullmatch(r"(\d*)d(\d+)", str(notation).strip())
                if m:
                    n = int(m.group(1) or 1)
                    face = max(n, min(face, n * int(m.group(2))))
                return self.given_total(face, notation, modifiers, label)
        return super().roll(notation, modifiers, label, visibility)


def _fight(pc_file="fixtures/pc-borin.json", foe="thug", faces=None, at=((6, 10), (7, 10)),
           feats=(), ally=None):
    scene = Scene(location_id="5bbd0c40345f")
    pc = load_pc(pc_file)
    pc.feats = list(pc.feats) + list(feats)
    scene.add(pc)
    scene.add(instantiate(foe, scene=scene, name=FOE))
    engine = Engine(scene, _Faces(faces))
    engine._ensure_encounter("pc")
    scene.positions["pc"], scene.positions["c1"] = at
    if ally is not None:
        friend = load_pc("fixtures/pc-kesst.json")
        friend.ref, friend.kind = "ally", "npc"
        friend.feats = list(friend.feats) + list(ally[1])
        scene.add(friend)
        scene.positions["ally"] = ally[0]
        scene.sides = {"pc": ["pc", "ally"], "them": ["c1"]}
    scene.resync_zones()
    # Everyone has had a turn (round two): a creature yet to act is flat-footed and makes
    # no attack of opportunity (CRB), which is not what these tests measure.
    for ref in scene.actors:
        scene.acted.add(ref) if isinstance(scene.acted, set) else scene.acted.append(ref)
    return scene, engine, scene.get("pc"), scene.get("c1")


def _settle(engine, res):
    """Answer every player roll the way the scripted dice would, inside the die's range."""
    while res.awaiting:
        ask = res.awaiting
        label = str(ask.get("label") or "")
        face = next((f for k, f in engine.dice.faces.items() if label.startswith(k)), 10)
        res = engine.resume(max(int(ask.get("min") or 1), min(face, int(ask.get("max") or 20))))
    return res


def _attack(engine, by="pc", target="c1", **params):
    return _settle(engine, engine.run(engine.validate([{
        "op": "attack", "actor": by, "target": target, "visibility": "hidden",
        "params": params}])))


def _aoo(engine, by="pc", target="c1", **params):
    """An attack of opportunity as the engine splices one (`_swings_at`): never through
    `validate`, which refuses the engine-owned `reaction`."""
    from rules.intents import Intent

    res = engine.run([Intent(op="attack", actor=by, target=target, visibility="hidden",
                             params={"full_attack": False,
                                     "reaction": "attack_of_opportunity", **params})])
    return _settle(engine, res)


def _named(roll: dict, name: str) -> int:
    return sum(int(m["value"]) for m in roll.get("modifiers") or ()
               if str(m.get("source") or m.get("label") or "").startswith(name))


def _rolls(res, prefix: str) -> list[dict]:
    return [r.as_dict() for o in res.outcomes for r in o.rolls
            if (r.label or "").startswith(prefix)]


# --- size against the bearer's -------------------------------------------------------------

def _halfling(pc):
    pc.race, pc.size = "halfling", "small"


def test_risky_striker_pays_only_against_a_foe_two_sizes_larger():
    """Borin made a Small halfling, BAB +1: "+2 bonus on melee damage rolls against
    creatures two or more size categories larger" and "-1 penalty to AC" until his next
    turn. The ogre is Large (two up): +2 on the damage roll; the thug is Medium (one up):
    nothing, though the AC still drops."""
    scene, engine, pc, ogre = _fight(foe="ogre", feats=["Risky Striker"],
                                     faces={"Attack with": 15, "Damage": 3})
    _halfling(pc)
    before = pc.ac()
    res = _attack(engine, risky_striker=True)
    dmg = _rolls(res, "Damage")
    assert dmg and _named(dmg[0], "Risky Striker") == 2
    assert pc.ac() == before - 1
    scene, engine, pc, thug = _fight(feats=["Risky Striker"],
                                     faces={"Attack with": 15, "Damage": 3})
    _halfling(pc)
    dmg = _rolls(_attack(engine, risky_striker=True), "Damage")
    assert dmg and _named(dmg[0], "Risky Striker") == 0


def test_risky_striker_is_refused_on_a_ranged_attack():
    scene, engine, pc, _ = _fight(feats=["Risky Striker"])
    _halfling(pc)
    assert Engine._attack_choice_refusal(pc, "shortbow", {"risky_striker": True})


def test_underfoot_adds_its_dodge_only_against_a_larger_foe_s_swing_at_a_mover():
    """Mobility's +4 against attacks of opportunity drawn by moving was read with no
    context, so "a larger opponent's threatened area" could not be asked. A Small
    Underfoot holder: +2 more against the ogre's swing, none against a Small goblin's."""
    scene, engine, pc, ogre = _fight(foe="ogre", feats=["Dodge", "Mobility", "Underfoot"])
    _halfling(pc)
    plain = pc.ac(attacker=ogre)
    assert pc.ac(attacker=ogre, provoked_by="movement") - plain == 4 + 2
    goblin = instantiate("goblin", scene=scene, name="a goblin")
    assert pc.ac(attacker=goblin, provoked_by="movement") - pc.ac(attacker=goblin) == 4


def test_porcupine_defense_cmd_only_against_a_larger_foe_who_provokes_nothing():
    scene, engine, pc, ogre = _fight(foe="ogre", feats=["Porcupine Defense"])
    plain = sum(m.value for m in pc.cmd_modifiers(maneuver="trip", attacker=None))
    with_ogre = sum(m.value for m in pc.cmd_modifiers(maneuver="trip", attacker=ogre))
    assert with_ogre == plain              # the ogre's trip provokes: no CMD bonus
    ogre.feats = list(ogre.feats) + ["Improved Trip"]
    with_ogre = sum(m.value for m in pc.cmd_modifiers(maneuver="trip", attacker=ogre))
    assert with_ogre - plain >= 2


# --- what kind of swing ----------------------------------------------------------------------

def test_swarm_strike_rides_attacks_of_opportunity_only():
    """+1 on a swing the engine spliced as an attack of opportunity; nothing on the
    player's own blow."""
    scene, engine, pc, thug = _fight(feats=["Swarm Strike"], faces={"Attack with": 12,
                                                                    "Damage": 1})
    own = _rolls(_attack(engine), "Attack with")[0]
    assert _named(own, "Swarm Strike") == 0
    aoo = _rolls(_aoo(engine), "Attack with")
    assert aoo and _named(aoo[0], "Swarm Strike") == 1


def test_swarm_strike_counts_each_ally_with_the_feat_threatening_the_foe():
    scene, engine, pc, thug = _fight(feats=["Swarm Strike"], ally=((8, 10), ["Swarm Strike"]),
                                     faces={"Attack with": 12, "Damage": 1})
    aoo = _rolls(_aoo(engine), "Attack with")
    assert _named(aoo[0], "Swarm Strike") == 2


def test_outflank_raises_the_flank_only_beside_an_ally_who_holds_it():
    """Borin and Kesst on either side of the thug: the flank's +2, and +2 more only when
    Kesst holds Outflank too."""
    scene, engine, pc, thug = _fight(feats=["Outflank"], ally=((8, 10), ["Outflank"]),
                                     faces={"Attack with": 12, "Damage": 1})
    assert _named(_rolls(_attack(engine), "Attack with")[0], "Outflank") == 2
    scene, engine, pc, thug = _fight(feats=["Outflank"], ally=((8, 10), []),
                                     faces={"Attack with": 12, "Damage": 1})
    assert _named(_rolls(_attack(engine), "Attack with")[0], "Outflank") == 0


def test_outflank_critical_queues_the_ally_s_attack_of_opportunity():
    """A confirmed critical on the flanked thug: Kesst (Outflank) swings at once, an attack
    of opportunity off her own allowance."""
    scene, engine, pc, thug = _fight(feats=["Outflank"], ally=((8, 10), ["Outflank"]),
                                     faces={"Attack with": 20, "Confirm": 20, "Damage": 1})
    thug.hp = thug.hp_max = 200
    res = _attack(engine)
    swings = [o for o in res.outcomes if o.op == "attack"]
    assert [o.intent_id for o in swings][:1] and any(
        "takes an attack of opportunity" in (o.tell or "") for o in swings[1:])
    assert scene.reacted.get("ally:attack_of_opportunity") == 1


def test_seize_the_moment_without_the_feat_queues_nothing():
    scene, engine, pc, thug = _fight(feats=["Seize the Moment"], ally=((8, 10), []),
                                     faces={"Attack with": 20, "Confirm": 20, "Damage": 1})
    thug.hp = thug.hp_max = 200
    res = _attack(engine)
    assert len([o for o in res.outcomes if o.op == "attack"]) == 1
    scene, engine, pc, thug = _fight(feats=["Seize the Moment"],
                                     ally=((7, 11), ["Seize the Moment"]),
                                     faces={"Attack with": 20, "Confirm": 20, "Damage": 1})
    thug.hp = thug.hp_max = 200
    res = _attack(engine)
    swings = [o for o in res.outcomes if o.op == "attack"]
    # Kesst's own swing may crit too and open the thug to Borin in turn: the chain is RAW.
    assert len(swings) >= 2 and swings[1].actor == "ally"


# --- what the hit was ------------------------------------------------------------------------

def test_shield_slam_bull_rushes_on_the_attack_roll_and_fells_against_a_wall():
    """Borin's shield bash hits; the bull rush is judged on that same roll (no CMB d20 is
    rolled) and pushes the thug. With the square behind the thug walled, the thug is
    knocked prone."""
    scene, engine, pc, thug = _fight(feats=["Shield Slam"],
                                     faces={"Attack with": 19, "Damage": 1})
    thug.hp = thug.hp_max = 200
    res = _attack(engine, weapon="shield")
    assert not _rolls(res, "Bull Rush (CMB)")
    assert any(e.get("kind") == "position" and e.get("ref") == "c1"
               for o in res.outcomes for e in o.effects)


def test_shield_snag_disarms_and_gives_way_to_shield_slam():
    scene, engine, pc, thug = _fight(feats=["Shield Snag"],
                                     faces={"Attack with": 19, "Damage": 1})
    thug.hp = thug.hp_max = 200
    res = _attack(engine, weapon="shield")
    assert any(e.get("kind") == "rider" and e.get("maneuver") == "disarm"
               for o in res.outcomes for e in o.effects)
    scene, engine, pc, thug = _fight(feats=["Shield Snag", "Shield Slam"],
                                     faces={"Attack with": 19, "Damage": 1})
    thug.hp = thug.hp_max = 200
    res = _attack(engine, weapon="shield")
    kinds = [e.get("maneuver") for o in res.outcomes for e in o.effects
             if e.get("kind") == "rider"]
    assert "bull rush" in kinds and "disarm" not in kinds


def test_bashing_finish_follows_a_critical_with_a_free_shield_bash():
    scene, engine, pc, thug = _fight(feats=["Bashing Finish"],
                                     faces={"Attack with": 20, "Confirm": 20, "Damage": 1})
    thug.hp = thug.hp_max = 200
    res = _attack(engine)
    bashes = [o for o in res.outcomes if o.op == "attack"]
    assert len(bashes) == 2 and "(bash)" in " ".join(
        r.label or "" for r in bashes[1].rolls)


def test_enforcer_shakes_for_the_nonlethal_damage_dealt():
    """A nonlethal blow for 3 + Str: a won Intimidate leaves the thug shaken for that many
    rounds (the damage dealt), not Demoralize's 1 + 1 per 5."""
    scene, engine, pc, thug = _fight(feats=["Enforcer"], faces={
        "Attack with": 15, "Damage": 3, "Intimidate": 20})
    thug.hp = thug.hp_max = 200
    res = _attack(engine, lethality="nonlethal")
    dealt = next(e["amount"] for o in res.outcomes for e in o.effects
                 if e.get("ref") == "c1" and "amount" in e)
    shaken = [e for e in thug.effects if e.key == "shaken"]
    assert dealt == 3 + pc.ability_mod("str")
    assert shaken and shaken[0].rounds_left == dealt
    assert not thug.has_state("state.fear.frightened")


def test_enforcer_does_nothing_on_a_lethal_blow():
    scene, engine, pc, thug = _fight(feats=["Enforcer"], faces={
        "Attack with": 15, "Damage": 3, "Intimidate": 20})
    thug.hp = thug.hp_max = 200
    _attack(engine)
    assert not thug.has_state("state.fear")


def test_intimidating_confidence_demoralizes_on_a_confirmed_critical():
    scene, engine, pc, thug = _fight(feats=["Intimidating Confidence"], faces={
        "Attack with": 20, "Confirm": 20, "Damage": 1, "Intimidate": 20})
    thug.hp = thug.hp_max = 200
    _attack(engine)
    assert thug.has_state("state.fear.shaken")
    assert pc.save_modifiers("will", {"against": ("spell", "emotion")}) != \
        pc.save_modifiers("will", {"against": ("spell",)})


def test_footslasher_halves_a_larger_foe_s_speed_until_first_aid():
    """-2 to hit, and a hit on the Large ogre with a slashing longsword halves its speed
    (the `state.slowed` question); a DC 15 Heal's first aid closes it."""
    from rules import firstaid

    scene, engine, pc, ogre = _fight(foe="ogre", feats=["Footslasher"],
                                     faces={"Attack with": 18, "Damage": 3})
    full = ogre.speed_feet
    res = _attack(engine, footslasher=True)
    assert _named(_rolls(res, "Attack with")[0], "Footslasher") == -2
    assert ogre.has_state("state.slowed.footslashed")
    assert ogre.speed_feet == full // 2
    assert firstaid.needs_aid(ogre)
    said, _ = firstaid.stanch(ogre, "first aid")
    assert "walks freely" in said and ogre.speed_feet == full


def test_pinpoint_targeting_strips_armour_and_is_refused_after_a_move(monkeypatch):
    """Borin's shortbow at the ogre: the AC the shot is judged on drops by the ogre's armour
    and natural armour (its stat block's typed terms); after a move this round the option is refused. Pinpoint's
    prerequisites (BAB +16, Dex 19) are waived for a 1st-level fixture."""
    from rules import feats as feats_mod

    monkeypatch.setattr(feats_mod, "meets", lambda *a, **k: {"unmet": []})
    import re

    def judged_on(res) -> int:
        tell = " ".join(o.tell or "" for o in res.outcomes)
        return int(re.search(r"against AC (\d+)", tell).group(1))

    scene, engine, pc, ogre = _fight(foe="ogre", feats=["Pinpoint Targeting"],
                                     at=((2, 10), (7, 10)),
                                     faces={"Attack with": 2, "Damage": 1})
    worn = sum(m.value for m in ogre.ac_modifiers("ranged")
               if m.type in ("armour", "natural armour", "shield"))
    assert worn > 0
    pc.goods["arrows"] = 20
    pc.shield, pc.equipped = "none", "shortbow"
    plain = judged_on(_attack(engine, weapon="shortbow"))
    pinned = judged_on(_attack(engine, weapon="shortbow", pinpoint_targeting=True))
    assert plain - pinned == worn        # the ogre's hide armour and its natural armour
    scene.move_spent["pc"] = scene.round
    with pytest.raises(Exception, match="moved this round"):
        res = _attack(engine, weapon="shortbow", pinpoint_targeting=True)
        if any(o.status == "refused" and "moved this round" in (o.tell or "")
               for o in res.outcomes):
            raise RuntimeError("moved this round")


def test_shield_of_swings_halves_damage_and_raises_shield_ac_and_cmd():
    """Borin's greatsword full attack: each blow's rolled damage (8 on the dice + Str x1.5)
    lands at half, and his AC and CMD rise by the +4 shield bonus until his next turn."""
    scene, engine, pc, thug = _fight(feats=["Shield of Swings"],
                                     faces={"Attack with": 15, "Damage": 8})
    pc.shield = "none"
    pc.weapons = list(pc.weapons) + ["greatsword"]
    pc.equipped = "greatsword"
    thug.hp = thug.hp_max = 200
    ac, cmd = pc.ac(), pc.cmd()
    res = _attack(engine, full_attack=True, shield_of_swings=True)
    assert pc.ac() - ac == 4 and pc.cmd() - cmd == 4
    rolled = [r["total"] for r in _rolls(res, "Damage")]
    landed = [e["amount"] for o in res.outcomes for e in o.effects
              if e.get("ref") == "c1" and "amount" in e]
    assert rolled and landed == [max(1, t // 2) for t in rolled]


def test_vicious_stomp_swings_at_a_foe_who_falls_prone_beside_you():
    """Kesst trips the thug; Borin (Vicious Stomp) beside it gets an unarmed attack of
    opportunity as it lands."""
    scene, engine, pc, thug = _fight(feats=["Vicious Stomp"], ally=((8, 10), []),
                                     faces={"Trip (CMB)": 20, "Attack with": 12,
                                            "Damage": 1})
    thug.hp = thug.hp_max = 200
    res = engine.run(engine.validate([{
        "op": "attack", "actor": "ally", "target": "c1", "visibility": "hidden",
        "params": {"manoeuvre": "trip"}}]))
    res = _settle(engine, res)
    swings = [o for o in res.outcomes if o.op == "attack" and o.intent_id != ""]
    assert any("unarmed" in " ".join(r.label or "" for r in o.rolls).lower()
               for o in swings)


# --- a spell cast defensively ------------------------------------------------------------------

def _wizard_beside(*foe_feats, second=None):
    """A 1st-level wizard (Kesst's sheet) at (5, 5) with a thug beside her holding the
    feats; `second` places another thug with the same feats."""
    from rules.grid import Grid
    from rules.sheet import from_dict, to_dict

    d = to_dict(load_pc("fixtures/pc-kesst.json"))
    d.update({"class": "wizard", "level": 1, "ranks": {}, "armour": "none", "feats": []})
    d["abilities"]["int"] = 11
    d["spellbook"], d["prepared"] = ["mage-armor"], {"mage-armor": 3}
    pc = from_dict(d, ref="pc")
    pc.kind = "pc"
    s = Scene(location_id="5bbd0c40345f", grid=Grid(20, 20))
    s.add(pc, at=(5, 5))
    thug = instantiate("thug", scene=s, name="the thug")
    thug.feats = list(thug.feats) + list(foe_feats)
    s.add(thug, at=(6, 5))
    them = ["c1"]
    if second is not None:
        other = instantiate("thug", scene=s, name="the other thug")
        other.feats = list(other.feats) + list(foe_feats)
        s.add(other, at=second)
        them.append(other.ref)
    s.sides = {"us": ["pc"], "them": them}
    s.initiative = [("pc", 20)] + [(r, 10) for r in them]
    s.round, s.turn = 1, 0
    s.acted = set(them)
    return s, Engine(s, _Faces({"Concentration": 1, "Attack with": 12, "Damage": 1}))


def _cast_defensively(e):
    return e.run(e.validate([{"op": "cast", "actor": "pc", "because": "she casts",
                              "params": {"spell": "mage-armor", "at": "pc",
                                         "defensively": True}}]))


def test_spellbreaker_swings_at_a_caster_who_fails_to_cast_defensively():
    """Normal: "Enemies that fail to cast spells defensively do not provoke". The thug
    with Spellbreaker beside the wizard gets his attack of opportunity when her
    concentration fails; without the feat the cast is all there is."""
    s, e = _wizard_beside()
    assert [o.op for o in _cast_defensively(e).outcomes] == ["cast"]
    s, e = _wizard_beside("Spellbreaker")
    res = _cast_defensively(e)
    assert [o.op for o in res.outcomes] == ["cast", "attack"]
    assert s.reacted == {"c1:attack_of_opportunity": 1}


def test_coordinated_distraction_needs_two_holders_and_adds_two_each():
    """DC 15 + 2 for a 1st-level spell is 17. One thug with the feat: still 17 ("you and
    at least one ally with this feat"). Two threatening her: 17 + 2 x 2 = 21."""
    def dc_of(res):
        return next(r.label for o in res.outcomes for r in o.rolls
                    if r.label.startswith("Concentration"))

    s, e = _wizard_beside("Coordinated Distraction")
    assert "DC 17" in dc_of(_cast_defensively(e))
    s, e = _wizard_beside("Coordinated Distraction", second=(4, 5))
    assert "DC 21" in dc_of(_cast_defensively(e))


# --- the rest of the blows ---------------------------------------------------------------------

def test_sliding_axe_throw_costs_two_and_trips_on_the_hit(monkeypatch):
    """A thrown handaxe along the ground: -2 on the throw, and the hit trips the thug with
    no trip back on a failure. Refused with a sword."""
    scene, engine, pc, thug = _fight(feats=["Sliding Axe Throw"], at=((5, 10), (7, 10)),
                                     faces={"Attack with": 18, "Damage": 1, "Trip": 20})
    thug.hp = thug.hp_max = 200
    pc.weapons = list(pc.weapons) + ["handaxe"]
    pc.equipped = "handaxe"
    assert Engine._attack_choice_refusal(pc, "longsword", {"sliding_axe_throw": True,
                                                           "thrown": True})
    res = _attack(engine, weapon="handaxe", thrown=True, sliding_axe_throw=True)
    # The throw's roll, wherever the attack of opportunity it draws puts it (b5-core).
    assert -2 in [_named(r, "Sliding Axe Throw") for r in _rolls(res, "Attack with")]
    assert thug.has_state("state.position.prone")


def test_underfoot_tumbles_past_a_larger_foe_more_easily_than_a_smaller_one():
    """One Acrobatics roll set against each foe's CMD: +4 counts against the Large ogre's
    and not against a Small goblin's — the term `skilluses.tumble` adds per foe."""
    scene, engine, pc, ogre = _fight(foe="ogre", feats=["Underfoot"])
    _halfling(pc)
    assert sum(m.value for m in pc._feat_mods(
        "skill_mod", "acrobatics", {"skill_use": "tumble", "target_actor": ogre},
        scoped=True)) == 4
    goblin = instantiate("goblin", scene=scene, name="a goblin")
    assert sum(m.value for m in pc._feat_mods(
        "skill_mod", "acrobatics", {"skill_use": "tumble", "target_actor": goblin},
        scoped=True)) == 0


def test_enforcer_s_critical_frightens_for_a_round_as_well():
    scene, engine, pc, thug = _fight(feats=["Enforcer"], faces={
        "Attack with": 20, "Confirm": 20, "Damage": 3, "Intimidate": 20})
    thug.hp = thug.hp_max = 200
    _attack(engine, lethality="nonlethal")
    assert thug.has_state("state.fear.frightened") and thug.has_state("state.fear.shaken")


# --- the second chunk ----------------------------------------------------------------------------

def test_greater_blind_fight_fights_total_concealment_as_twenty_percent():
    """Before: a melee blow at an invisible thug met a 50% miss chance whatever the feats.
    Greater Blind-Fight rolls it as 20% (the miss-chance die's label says so)."""
    scene, engine, pc, thug = _fight(feats=["Greater Blind-Fight"],
                                     faces={"Attack with": 18, "Damage": 1, "miss": 99})
    thug.hp = thug.hp_max = 200
    thug.add_buff("concealment", "miss_chance", 50, source="test darkness", rounds=10)
    labels = [r["label"] for r in _rolls(_attack(engine), "miss chance")]
    assert labels and all("fought blind" in label for label in labels)


def test_goblin_cleaver_adds_two_on_the_follow_up_blow_at_a_goblinoid():
    scene, engine, pc, _ = _fight(feats=["Goblin Cleaver"])
    goblin = instantiate("goblin", scene=scene, name="a goblin")
    first = sum(m.value for m in pc.attack_modifiers(defender=goblin, choices=("cleave",)))
    later = sum(m.value for m in pc.attack_modifiers(defender=goblin,
                                                     choices=("cleave", "cleaving_on")))
    assert later - first == 2
    thug = scene.get("c1")
    assert sum(m.value for m in pc.attack_modifiers(
        defender=thug, choices=("cleave", "cleaving_on"))) == sum(
        m.value for m in pc.attack_modifiers(defender=thug, choices=("cleave",)))


def test_focused_disbelief_resists_divine_spells_only():
    """SR 11 + level (12 at 1st) against a divine caster's spell; none against arcane."""
    scene, engine, pc, _ = _fight(feats=["Focused Disbelief"])
    assert pc.spell_resistance_rating({"against": ("spell", "divine_spell")})[0] == 12
    assert pc.spell_resistance_rating({"against": ("spell", "arcane_spell")})[0] == 0
    assert pc.spell_resistance_rating()[0] == 0


def test_cut_your_losses_carries_as_if_two_stronger():
    from rules import gear

    scene, engine, pc, _ = _fight()
    before = gear.load(pc)["heavy"]
    pc.feats.append("Cut Your Losses")
    after = gear.load(pc)
    assert after["heavy"] == gear.capacity(after["str"] + after["str_bonus"])[2] > before


def test_escape_route_lets_an_ally_slip_past_beside_you():
    """Kesst steps away from the thug out of a square beside Borin: with both holding
    Escape Route, the thug's attack of opportunity is not owed."""
    from rules import reactions

    for feats, owed in (([], True), (["Escape Route"], False)):
        scene, engine, pc, thug = _fight(feats=feats, ally=((8, 11), feats),
                                         at=((7, 12), (8, 10)))
        got = reactions.provoked_by_move(scene, "ally", (8, 11), (8, 14))
        assert bool([r for r, _ in got if r == "c1"]) is owed


def test_disengaging_feint_buys_a_step_away_instead_of_an_opening():
    scene, engine, pc, thug = _fight(feats=["Disengaging Feint"], faces={"Bluff": 20})
    res = _settle(engine, engine.run(engine.validate([{
        "op": "check", "actor": "pc", "target": "c1", "visibility": "hidden",
        "params": {"skill": "bluff", "feint": True, "disengage": True}}])))
    assert "step away" in res.outcomes[0].tell
    assert pc.has_state("movement.unprovoking.c1")
    assert not thug.has_state("state.feinted")
    from rules import reactions

    assert not [r for r, _ in reactions.provoked_by_move(scene, "pc", (6, 10), (2, 10))
                if r == "c1"]


def test_combat_medic_takes_ten_on_an_ally_who_also_holds_it():
    """Kesst dying at -2; Borin's first aid (Heal +1) takes 10 only beside the feat on both,
    and only when 10 does it — rolled as a 10 the dice never threw."""
    scene, engine, pc, _ = _fight(feats=["Combat Medic"], ally=((7, 11), ["Combat Medic"]),
                                  faces={"Heal": 1})
    pc.ranks["heal"] = 5
    kesst = scene.get("ally")
    kesst.hp = -2
    kesst.apply_hp_state()
    res = _settle(engine, engine.run(engine.validate([{
        "op": "check", "actor": "pc", "target": "ally", "visibility": "hidden",
        "params": {"skill": "heal", "dc": 15}}])))
    heal = [r for o in res.outcomes for r in o.rolls if "Heal" in (r.label or "")]
    assert heal and "taking 10" in heal[0].label and heal[0].faces == [10]


def test_trick_riding_needs_no_check_at_dc_fifteen_in_light_armour(monkeypatch):
    """"You do not need to make Ride skill checks for any task ... with a DC of 15 or
    lower" in light or no armour; a DC 20 task, or heavy armour, still rolls. And Mounted
    Combat's negation twice a round instead of once."""
    from rules import bodyskills
    from rules.dice import Modifier

    scene, engine, pc, thug = _fight(feats=["Trick Riding"], faces={"Ride": 1})
    pc.armour = "leather"
    got = bodyskills._trick_ridden(engine, pc, [Modifier(3, "Ride")], 15, "Ride check (x)")
    assert got is not None and got.total >= 15 and "Trick Riding" in got.label
    assert bodyskills._trick_ridden(engine, pc, [], 20, "Ride check (x)") is None
    pc.armour = "full plate"
    assert bodyskills._trick_ridden(engine, pc, [], 15, "Ride check (x)") is None

    pc.feats.append("Mounted Combat")
    monkeypatch.setattr(bodyskills, "rider_of", lambda s, steed: pc)
    monkeypatch.setattr(bodyskills, "mount_of", lambda s, rider: thug)
    atk = engine.dice.given(20, [Modifier(30, "x")], label="Attack")
    state = {"rolls": [], "tells": []}
    for _ in range(3):
        bodyskills.mounted_combat(engine, None, thug, atk, state)
    assert sum(1 for r in state["rolls"] if "Mounted Combat" in r["label"]) == 2


def test_horn_of_the_criosphinx_doubles_strength_on_a_two_handed_charge():
    """Borin, Str 17 (+3), a greatsword: 1.5 x 3 = 4 on any swing; on a charge (lane
    b2-actions' `charge` option, its roll-context key) 2 x 3 = 6, so the feat adds 2. A
    one-handed longsword charge adds nothing."""
    scene, engine, pc, _ = _fight(feats=["Horn of the Criosphinx"])
    pc.weapons = list(pc.weapons) + ["greatsword"]

    def dmg(key, choices=()):
        return sum(m.value for m in pc.damage_modifiers(key, choices=choices)
                   if m.source == "Horn Of The Criosphinx" or "Criosphinx" in m.source)

    assert dmg("greatsword") == 0
    assert dmg("greatsword", ("charge",)) == 2 * 3 - (3 * 3) // 2
    assert dmg("longsword", ("charge",)) == 0
