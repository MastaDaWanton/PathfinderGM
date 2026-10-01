"""A blow at somebody already lying there lands, and 1e's coup de grâce exists.

Probed 2026-09-27 through `Engine.run`, visibility hidden: a thug knocked unconscious by
non-lethal damage past his hit points, attacked by the PC with a rapier, came back with 0
rolls, no effects, an empty tell and his hit points unchanged — and a dying thug the same.
`_op_attack` broke out of its swing loop on `defender.is_down` before the FIRST swing, so
"I finish him" never resolved, while `judgement.is_finishing_blow` and
`redirect_attacks_off_corpses` stood guard over a blow that could not land.
`test_battle_gate`'s mercy-stroke test passed only through its `or` branch.

The rule (Core Rulebook p.197, "Helpless Defenders"): an ordinary attack on a helpless
defender is at Dex 0 and -4 AC against melee; a coup de grâce is a full-round action that
hits automatically, is a critical hit, adds a rogue's sneak attack, and a survivor saves
on Fortitude at DC 10 + the damage dealt or dies. None against a creature immune to
critical hits; a bow or crossbow only when adjacent. See `rules/coup_de_grace.py`.
"""
from __future__ import annotations

import pytest

from gm import judgement
from rules import coup_de_grace
from rules.bestiary import instantiate
from rules.dice import Dice
from rules.engine import Engine, Scene
from rules.grid import Grid
from rules.sheet import load_pc


def _scene(template="thug", pc="fixtures/pc-kesst.json"):
    s = Scene(location_id="5bbd0c40345f")
    s.add(load_pc(pc))
    s.add(instantiate(template, scene=s, name=f"the {template}"))
    return s


def _knock_out(foe):
    foe.nonlethal = foe.hp + 3
    foe.apply_hp_state()


def _bleed(foe):
    foe.hp = -3
    foe.apply_hp_state()


def _bind(foe):
    foe.add_condition("helpless", source="bound hand and foot")


def _swing(scene, seed=5, **params):
    weapon = params.pop("weapon", "rapier")
    pc = scene.actors["pc"]
    if weapon not in pc.weapons:
        pc.weapons.append(weapon)                 # handed a sling or a bow for the test
    # And something for it to shoot: since 2026-09-30 a launcher spends a round a shot and
    # refuses with none (tests/test_gear_usable.py).
    from rules import goods, weapons as weapons_mod

    for fam in weapons_mod.ammo_families(weapon)[:1]:
        stock = {"arrows": "arrows-20", "sling bullets": "sling-bullets-10",
                 "bolts": "crossbow-bolts-10"}.get(fam)
        if stock and not goods.ammo_carried(pc, [fam]):
            pc.goods[stock] = 10
    engine = Engine(scene, Dice(seed=seed))
    res = engine.run(engine.validate([
        {"op": "attack", "actor": "pc", "target": "c1", "because": "finish him",
         "visibility": "hidden", "params": {"weapon": weapon, **params}}]))
    return res.outcomes[0]


# --- the defect: the first swing at a body on the floor -------------------------------

@pytest.mark.parametrize("fell", [_knock_out, _bleed], ids=["unconscious", "dying"])
def test_the_first_swing_at_somebody_down_lands(fell):
    """The probe, as a test: 0 rolls, no effects, an empty tell and hit points
    unchanged, for a thug beaten senseless and for one bleeding out."""
    s = _scene()
    foe = s.actors["c1"]
    fell(foe)
    assert foe.is_down
    before = foe.hp
    out = _swing(s)
    assert out.rolls, "the swing rolled nothing"
    assert out.rolls[0].label.startswith("Attack with"), "the first swing was not made"
    assert out.tell, "the narrator was told nothing"
    assert any(e.get("kind") == "damage" for e in out.effects) and foe.hp < before, (
        f"the blow landed on nobody: hp {before} -> {foe.hp}")


def test_the_mercy_stroke_is_offered_to_the_player_not_skipped():
    """`test_battle_gate`'s mercy stroke, without its escape hatch: the player's own
    swing at the dying man must actually ask for the player's d20."""
    s = _scene()
    _bleed(s.actors["c1"])
    engine = Engine(s, Dice(seed=5))
    engine.run(engine.validate([
        {"op": "attack", "actor": "pc", "target": "c1", "because": "out of his misery"}]))
    assert not s.in_encounter
    assert s.awaiting and s.awaiting["die"] == "1d20", "no die was offered"


def test_a_swing_queued_behind_the_one_that_dropped_them_is_still_held():
    """The guard's own reason, kept: a Swift Strikes second swing once asked the
    player for a d20 at a body on the floor and stalled the fight. Now it holds from
    the SECOND swing on. A fighter at 8th level with the foe already down: the first
    iterative lands, the second is held, and the tell says so."""
    s = _scene(pc="fixtures/pc-borin.json")
    s.actors["pc"].level = 8
    assert len(s.actors["pc"].attack_sequence(None, True)) >= 2
    _bleed(s.actors["c1"])
    out = _swing(s, weapon="longsword", full_attack=True)
    attacks = [r for r in out.rolls if r.label.startswith("Attack with")]
    assert len(attacks) == 1, f"{len(attacks)} swings rolled at a body on the floor"
    assert "holds the blow" in out.tell


def test_a_blow_at_the_dead_rolls_nothing_and_says_so():
    """Kicking the fallen is allowed (`redirect_attacks_off_corpses`); a d20 against a
    corpse is not."""
    s = _scene()
    foe = s.actors["c1"]
    foe.hp = -40
    foe.apply_hp_state()
    assert foe.has_state("state.down.dead")
    out = _swing(s)
    assert not out.rolls and not out.effects
    assert "already dead" in out.tell


def test_a_body_out_cold_taken_to_zero_is_not_told_as_standing():
    """The first live coup de grâce in the app (2026-09-28): 13 damage took a thug beaten
    unconscious from 13 hit points to exactly 0, a natural 20 saved him, and the ladder
    wrote `disabled` — whose sentence reads "still standing". Unreachable while blows at
    unconscious bodies never landed; the narrator would have been told he got up."""
    s = _scene()
    foe = s.actors["c1"]
    _knock_out(foe)
    engine = Engine(s, Dice(seed=5))
    got = engine.run(engine.validate(
        [{"op": "damage", "actor": "pc", "target": "c1", "because": "she hits",
          "params": {"amount": foe.hp, "type": "piercing"}}], origin="author:test"))
    tell = got.outcomes[0].tell
    assert foe.hp == 0 and foe.has_state("state.down.unconscious")
    assert "still standing" not in tell, tell
    assert "lies unconscious" in tell, tell


# --- the ordinary blow at a helpless defender -----------------------------------------

def test_a_helpless_defender_is_at_dex_zero_and_minus_four_against_melee():
    """The helpless row's note said "treated as Dex 0; melee attackers gain +4 to hit"
    and nothing read it: an unconscious thug was AC 13 flat-footed, the same as one
    merely surprised. 1e: Dex modifier -5, and -4 more against melee."""
    s = _scene()
    foe = s.actors["c1"]
    awake_flat = foe.ac("melee", flat_footed=True)
    _knock_out(foe)
    assert foe.is_helpless
    assert foe.ac("ranged") == awake_flat - 5
    assert foe.ac("melee") == awake_flat - 9
    sources = [m.source for m in foe.ac_modifiers("melee")]
    assert "Dex 0 (helpless)" in sources and "helpless, against melee" in sources


def test_the_rule_evaporates_when_the_condition_does():
    s = _scene()
    foe = s.actors["c1"]
    before = foe.ac("melee")
    _bind(foe)
    assert foe.ac("melee") < before
    foe.remove_condition("helpless")
    assert foe.ac("melee") == before


# --- the coup de grâce ----------------------------------------------------------------

def test_a_coup_de_grace_rolls_no_attack_and_is_a_critical():
    s = _scene()
    _knock_out(s.actors["c1"])
    out = _swing(s, coup_de_grace=True)
    labels = [r.label for r in out.rolls]
    assert not any(l.startswith(("Attack", "Confirm")) for l in labels), labels
    assert any("CRITICAL" in l for l in labels), labels
    assert "coup de grâce" in out.tell and "critically hits" in out.tell


def test_the_survivor_saves_at_ten_plus_damage_dealt_or_dies():
    """Both branches, across seeds, from a foe sturdy enough to live through the
    blow: an ogre, bound. Whatever the dice, the DC is 10 + the damage the ogre lost,
    and it is alive exactly when the save met it — the death written through
    `Actor.die`, and said once."""
    seen = set()
    for seed in range(1, 40):
        s = _scene("ogre")
        ogre = s.actors["c1"]
        _bind(ogre)
        out = _swing(s, seed=seed, coup_de_grace=True)
        dealt = next(e["amount"] for e in out.effects if e.get("kind") == "damage")
        saves = [r for r in out.rolls if "Fortitude" in r.label]
        if ogre.hp <= -ogre.ability_score("con"):
            continue                              # killed by the damage: no save owed
        assert len(saves) == 1
        assert out.dc["value"] == 10 + dealt
        # A natural 20 lives and a natural 1 dies whatever the total (CRB p.180). The
        # first live run in the app was exactly that: a thug's natural 20 made 23
        # against DC 23.
        nat = saves[0].natural
        lived = nat == 20 or (nat != 1 and saves[0].total >= 10 + dealt)
        assert ogre.has_state("state.down.dead") != lived
        if not lived:
            assert out.tell.count("is dead") == 1, out.tell
            assert "is dying" not in out.tell and "unconscious" not in out.tell, out.tell
        seen.add(lived)
    assert seen == {True, False}, f"only saw {seen} across 39 seeds"


def test_a_rogue_adds_sneak_attack_to_it():
    s = _scene()
    _knock_out(s.actors["c1"])
    out = _swing(s, coup_de_grace=True)
    assert any(r.label.startswith("Sneak attack") for r in out.rolls)


def test_finishing_a_bound_prisoner_opens_no_battle():
    """A coup de grâce is not a fight being started (test_battle_gate's docstring)."""
    s = _scene()
    _bind(s.actors["c1"])
    out = _swing(s, coup_de_grace=True)
    assert not s.in_encounter
    assert not any(e.get("kind") == "battle_joined" for e in out.effects)
    assert any(e.get("kind") == "damage" for e in out.effects)


def test_undead_take_the_blow_and_have_no_save_to_fail():
    """Undead and constructs are NOT immune to critical hits in PF1 (a 3.5 rule, and a
    first reading of the Bestiary page claimed it for constructs; a second read of the
    lists found no such line). They are immune to anything requiring a Fortitude save."""
    s = _scene("zombie")
    _bind(s.actors["c1"])
    out = _swing(s, coup_de_grace=True)
    assert any(e.get("kind") == "damage" for e in out.effects)
    assert not any("Fortitude" in r.label for r in out.rolls)
    assert "undead traits" in out.tell


@pytest.mark.parametrize("state, template, weapon, said", [
    ("standing", "thug", "rapier", "not helpless"),
    ("bound", "stun-jelly", "rapier", "critical hits"),
    ("bound", "thug", "sling", "melee weapon"),
])
def test_what_1e_refuses_is_refused_with_the_reason(state, template, weapon, said):
    s = _scene(template)
    foe = s.actors["c1"]
    if state == "bound":
        _bind(foe)
    before = foe.hp
    out = _swing(s, weapon=weapon, coup_de_grace=True)
    assert out.status == "refused" and not out.rolls
    assert said in out.tell
    assert foe.hp == before


def test_a_bow_must_be_point_blank():
    s = _scene()
    _bind(s.actors["c1"])
    s.grid = Grid(width=12, height=12)
    s.positions["pc"] = [0, 0]
    s.positions["c1"] = [4, 0]
    far = _swing(s, weapon="longbow", coup_de_grace=True)
    assert far.status == "refused" and "ft away" in far.tell
    s.positions["c1"] = [1, 0]
    near = _swing(s, weapon="longbow", coup_de_grace=True)
    assert near.status != "refused"


def test_crit_immunity_reads_the_creatures_own_traits():
    s = Scene(location_id="x")
    assert coup_de_grace.crit_immunity(instantiate("stun-jelly", scene=s))
    assert not coup_de_grace.crit_immunity(instantiate("zombie", scene=s))
    assert not coup_de_grace.crit_immunity(instantiate("thug", scene=s))
    assert coup_de_grace.fortitude_exempt(instantiate("zombie", scene=s)) == "undead traits"


# --- the words become the rule --------------------------------------------------------

def test_finishing_words_declare_the_coup_de_grace():
    s = _scene()
    _knock_out(s.actors["c1"])
    raw = [{"op": "attack", "actor": "pc", "target": "c1", "because": ""}]
    out = judgement.declare_coup_de_grace(raw, "I finish him off", s)
    assert out[0]["params"]["coup_de_grace"] is True


def test_finishing_words_with_no_blow_proposed_add_one_when_one_body_is_meant():
    s = _scene()
    _knock_out(s.actors["c1"])
    out = judgement.declare_coup_de_grace(
        [{"op": "narrate_only", "params": {}}], "i put him out of his misery", s)
    added = [r for r in out if r.get("op") == "attack"]
    assert added and added[0]["target"] == "c1" and added[0]["params"]["coup_de_grace"]


def test_two_bodies_and_no_blow_is_not_a_guess():
    s = _scene()
    s.add(instantiate("thug", scene=s, name="the other thug"))
    _knock_out(s.actors["c1"])
    _knock_out(s.actors["c2"])
    raw = [{"op": "narrate_only", "params": {}}]
    assert judgement.declare_coup_de_grace(raw, "I finish him off", s) == raw


def test_ordinary_words_leave_the_blow_ordinary():
    s = _scene()
    _knock_out(s.actors["c1"])
    raw = [{"op": "attack", "actor": "pc", "target": "c1", "because": ""}]
    assert judgement.declare_coup_de_grace(raw, "I kick him", s) == raw


def test_the_param_survives_validation():
    s = _scene()
    engine = Engine(s, Dice(seed=5))
    got = engine.validate([{"op": "attack", "actor": "pc", "target": "c1",
                            "params": {"coup_de_grace": "yes"}}])
    assert got[0].params["coup_de_grace"] is True
