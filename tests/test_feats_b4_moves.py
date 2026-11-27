"""Feat loop batch 4, lane b4-moves: each feat's clauses measured through the engine, and the
turn's action budget a class ability now spends.

Before this batch none of these feats had a document (worklist 2026-11-26, b4-moves.tsv,
52 feats). And a defect batch 3 found: a class ability's declared action was recorded on
its outcome and spent from nothing — Smite Evil, Channel Smite, Bewildering Koan and
Crusader's Fist, each "as a swift action", could all be used in one turn, and
`Scene.swift_spent` never moved. The moving feats answer the outcome of a blow or a walk
(rules/feat_moves.py); the activated ones are documents in
content/class-abilities/feats-b4-moves.json.
"""
from __future__ import annotations

import re

from rules import armour as armour_mod
from rules.bestiary import instantiate
from rules.dice import Dice
from rules.engine import Engine, Scene
from rules.grid import Grid
from rules.sheet import from_dict, load_pc, to_dict
from tests._board import face_to_face, new_turn


class _Faces(Dice):
    """Each roll whose label starts with a key lands on that key's face; the rest roll
    seeded."""

    def __init__(self, faces: dict | None = None):
        super().__init__(seed=20261126)
        self.faces = dict(faces or {})

    def roll(self, notation, modifiers=None, label="", visibility="hidden"):
        for prefix, face in self.faces.items():
            if (label or "").startswith(prefix):
                if notation == "1d20":
                    return self.given(face, modifiers, label)
                m = re.fullmatch(r"(\d*)d(\d+)", str(notation).strip())
                if m:
                    n = int(m.group(1) or 1)
                    face = max(n, min(face, n * int(m.group(2))))
                return self.given_total(face, notation, modifiers, label)
        return super().roll(notation, modifiers, label, visibility)


def _pc(cls: str = "fighter", level: int = 8, feats=(), base="fixtures/pc-kesst.json",
        **extra):
    d = to_dict(load_pc(base))
    d.update({"class": cls, "level": level, "ranks": {}})
    d.pop("paths", None)
    d["feats"] = list(feats)
    d.update(extra)
    pc = from_dict(d, ref="pc")
    pc.abilities["cha"] = 16
    return pc


def _board(pc, *foes, at=(5, 5), faces=None, allies=()):
    """A fight on a 20x20 map, the PC's turn: `foes` are (template, (x, y)), refs c1.."""
    s = Scene(location_id="5bbd0c40345f")
    s.add(pc, at=at)
    for a, square in allies:
        s.add(a, at=square)
    for i, (template, square) in enumerate(foes, start=1):
        s.add(instantiate(template, scene=s, name=f"the {template} {i}"), at=square)
    s.grid = Grid(width=20, height=20)
    them = [r for r in s.actors if r != pc.ref and r not in {a.ref for a, _ in allies}]
    s.initiative = [(pc.ref, 30)] + [(a.ref, 20) for a, _ in allies] + [
        (r, 10 - i) for i, r in enumerate(them)]
    s.sides = {"pc": [pc.ref] + [a.ref for a, _ in allies], "them": them}
    s.round, s.turn = 1, 0
    s.resync_zones()
    for ref in s.actors:                   # everyone has acted: nobody is flat-footed
        s.acted.add(ref) if isinstance(s.acted, set) else s.acted.append(ref)
    return s, Engine(s, dice=_Faces(faces))


def _use(e, name, to=None, actor="pc"):
    raw = {"op": "use_ability", "actor": actor, "because": "test",
           "params": {"ability": name}}
    if to:
        raw["params"]["to"] = to
    return e.run(e.validate([raw])).outcomes[-1]


def _settle(e, res):
    while res.awaiting:
        label = str(res.awaiting.get("label") or "")
        face = next((f for k, f in e.dice.faces.items() if label.startswith(k)), 10)
        res = e.resume(max(int(res.awaiting.get("min") or 1),
                           min(face, int(res.awaiting.get("max") or 20))))
    return res


def _run(e, *raws):
    return _settle(e, e.run(e.validate([dict({"because": "test"}, **r) for r in raws])))


def _attack(e, by="pc", target="c1", **params):
    return _run(e, {"op": "attack", "actor": by, "target": target, "visibility": "hidden",
                    "params": params})


def _tells(res) -> str:
    return " ".join(o.tell or "" for o in res.outcomes)


def _named(roll: dict, name: str) -> int:
    return sum(int(m["value"]) for m in roll.get("modifiers") or ()
               if str(m.get("source") or m.get("label") or "").startswith(name))


def _rolls(res, prefix: str) -> list[dict]:
    return [r.as_dict() for o in res.outcomes for r in o.rolls
            if (r.label or "").startswith(prefix)]


# --- the turn's action budget (the batch-3 defect) -----------------------------------------

def test_a_second_swift_class_ability_in_one_turn_is_refused_with_the_reason():
    """Batch 3 measured it: Smite Evil "as a swift action" twice in one turn, both
    resolved, and `Scene.swift_spent` never moved. Now the first spends the turn's swift
    and the second is refused, naming it."""
    pc = _pc("paladin")
    s, e = _board(pc, ("thug", (6, 5)), ("thug", (5, 6)))
    first = _use(e, "Smite Evil", to="c1")
    assert first.status == "resolved", first.tell
    assert s.swift_spent.get("pc") == s.round
    second = _use(e, "Smite Evil", to="c2")
    assert second.status == "refused" and second.code == "swift_spent", second.tell
    assert "already used the swift action of this turn" in second.tell
    assert "Smite Evil" in second.tell
    new_turn(s)
    assert _use(e, "Smite Evil", to="c2").status == "resolved"


def test_a_swift_class_ability_off_the_users_turn_is_refused():
    """CRB, Action Types: "You can perform only a single swift action per turn" — on
    one's own turn. Before: a paladin smote on the thug's turn."""
    pc = _pc("paladin")
    s, e = _board(pc, ("thug", (6, 5)))
    s.turn = 1
    out = _use(e, "Smite Evil", to="c1")
    assert out.code == "swift_spent" and "only on their own turn" in out.tell, out.tell


def test_a_standard_class_ability_spends_the_standard_and_a_move_one_the_move():
    """A standard-action use after the turn's standard is refused (the drink's record,
    `Scene.standard_spent`); a move action is paid by the move, then by the standard in
    its place, then refused."""
    pc = _pc("cleric", feats=["Quick Channel"])
    s, e = _board(pc, ("thug", (6, 5)))
    assert _use(e, "Channel Positive Energy").status == "resolved"
    assert s.standard_spent.get("pc") == s.round
    again = _use(e, "Channel Positive Energy")
    assert again.code == "standard_spent", again.tell
    new_turn(s)
    assert _use(e, "Quick Channel").status == "resolved"
    assert s.move_spent.get("pc") == s.round and s.standard_spent.get("pc") != s.round
    assert _use(e, "Quick Channel").status == "resolved"        # the standard in its place
    assert s.standard_spent.get("pc") == s.round
    pc.pool("channel energy").current = 9          # the price is not what is measured
    third = _use(e, "Quick Channel")
    assert third.code == "standard_spent" and "move action" in third.tell, third.tell


def test_out_of_a_fight_nothing_is_counted():
    pc = _pc("paladin")
    s = Scene(location_id="5bbd0c40345f")
    s.add(pc)
    e = Engine(s, dice=Dice(seed=3))
    assert _use(e, "Lay on Hands").status == "resolved"
    assert _use(e, "Lay on Hands").status == "resolved"
    assert not s.swift_spent and not s.standard_spent


# --- Arcane Armor Training ---------------------------------------------------------------

def test_arcane_armor_training_takes_ten_off_the_armours_failure_for_a_round():
    """CRB: "As a swift action, reduce the arcane spell failure chance due to the armor
    you are wearing by 10% for any spells you cast this round." A wizard in a chain shirt
    (20%) casts at 10% after it; a round later at 20% again."""
    pc = _pc("wizard", feats=["Arcane Armor Training"], armour="chain shirt")
    s, e = _board(pc, ("thug", (9, 5)))
    from rules import spells

    spell = spells.get("magic-missile")
    before = armour_mod.spell_failure(pc, spell)[0]
    assert before == 20, before
    out = _use(e, "Arcane Armor Training")
    assert out.status == "resolved", out.tell
    assert armour_mod.spell_failure(pc, spell)[0] == 10
    assert s.swift_spent.get("pc") == s.round
    pc.tick_effects(1)
    assert armour_mod.spell_failure(pc, spell)[0] == 20


# --- Spirited Charge and the lance -------------------------------------------------------

def test_spirited_charge_doubles_a_mounted_charge_and_triples_a_lance():
    """CRB, Lance: double damage from a charging mount; Spirited Charge: "double damage
    with a melee weapon (or triple damage with a lance)". Measured through the multiple
    the damage roll takes (`feat_moves.charge_multiple`), and 1e's sum of multiples with a
    critical (x3 lance crit + triple = x5)."""
    from rules import feat_moves
    from rules.activeeffect import ActiveEffect

    pc = _pc("fighter")
    pc.apply_effect(ActiveEffect(name="riding", kind="situation", key="mounted",
                                 source="test", tags=("state.position.mounted",)))
    sword = {"category": "melee", "id": "longsword"}
    lance = {"category": "melee", "id": "lance"}
    assert feat_moves.charge_multiple(pc, sword, "longsword", ("charge",), 1) == 1
    assert feat_moves.charge_multiple(pc, lance, "lance", ("charge",), 1) == 2
    pc.feats = ["Spirited Charge"]
    assert feat_moves.charge_multiple(pc, sword, "longsword", ("charge",), 1) == 2
    assert feat_moves.charge_multiple(pc, lance, "lance", ("charge",), 1) == 3
    assert feat_moves.charge_multiple(pc, lance, "lance", ("charge",), 3) == 5
    assert feat_moves.charge_multiple(pc, sword, "longsword", (), 1) == 1
    pc.effects = [x for x in pc.effects if x.key != "mounted"]
    assert feat_moves.charge_multiple(pc, sword, "longsword", ("charge",), 1) == 1


# --- Death from Above, Wings of the Androsphinx ------------------------------------------

def test_death_from_above_is_plus_five_charging_down_in_place_of_two_and_one():
    """UC: "Whenever you charge an opponent from higher ground ... you gain a +5 bonus on
    attack rolls in place of the bonuses from charging and being on higher ground." The
    roll's terms: charging +2, higher ground +1, the feat +2 — five in all; on level
    ground the feat adds nothing."""
    for feats, high, want in (([], True, 3), (["Death from Above"], True, 5),
                              (["Death from Above"], False, 2)):
        pc = _pc("fighter", feats=feats)
        s, e = _board(pc, ("thug", (6, 5)), faces={"Attack": 10, "Damage": 1})
        if high:
            s.positions["pc"] = (5, 5, 1)
        from rules import position
        from rules.sheet import situated

        with situated(s):
            ctx_mods = pc.attack_modifiers(defender=s.actors["c1"], choices=("charge",))

        board = sum(m.value for m in position.attack_mods(s, pc, s.actors["c1"]))
        got = sum(m.value for m in ctx_mods
                  if m.source in ("charging", "Death from Above")) + board
        assert got == want, (feats, high, got)


def test_wings_of_the_androsphinx_is_plus_two_against_a_charger_and_repositions_a_miss():
    """People of the Sands: "+2 bonus to AC against charge attacks. If a creature charges
    you and fails its attack roll, as an immediate action you can attempt a reposition"."""
    pc = _pc("fighter", feats=["Wings of the Androsphinx"])
    s, e = _board(pc, ("thug", (10, 5)), faces={"Attack": 2, "Damage": 1})
    thug = s.actors["c1"]
    s.turn = 1
    base = pc.ac(attacker=thug)
    res = _attack(e, by="c1", target="pc", charge=True)
    blow = next(o for o in res.outcomes if o.op == "attack" and o.actor == "c1")
    assert f"against AC {base + 2}" in blow.tell, (base, blow.tell)
    moved = [o for o in res.outcomes if o.op == "attack" and o.actor == "pc"]
    assert moved and "Wings of the Androsphinx" in (moved[0].because or ""), _tells(res)
    assert s.swift_spent.get("pc") is not None
    # Only against a charger: the same thug swinging plainly next round meets the base AC.
    thug.effects = [x for x in thug.effects if x.key != "charging"]
    assert pc.ac(attacker=thug) == base


# --- Sidestep, Improved Sidestep, Landing Roll ------------------------------------------

def test_sidestep_steps_five_feet_inside_the_threat_after_a_miss_and_pays_next_turn():
    """APG: a melee miss lets the one missed "move 5 feet as an immediate action so long
    as you remain within that opponent's threatened area"; then "you cannot take a 5-foot
    step during your next turn" and 5 feet less movement — unless Improved Sidestep."""
    from rules import reactions

    for feats, paid in ((["Sidestep"], True), (["Sidestep", "Improved Sidestep"], False)):
        pc = _pc("fighter", feats=feats)
        s, e = _board(pc, ("thug", (6, 5)), faces={"Attack": 2})
        s.turn = 1
        was = tuple(s.positions["pc"][:2])
        res = _attack(e, by="c1", target="pc")
        now = tuple(s.positions["pc"][:2])
        assert now != was, _tells(res)
        assert max(abs(now[0] - was[0]), abs(now[1] - was[1])) == 1
        assert now in reactions.threatened_by(s, "c1", pc.size)
        assert pc.has_state("movement.stepped") is paid, feats


def test_no_sidestep_on_a_hit_or_without_the_feat():
    for feats, face in (([], 2), (["Sidestep"], 19)):
        pc = _pc("fighter", feats=feats)
        s, e = _board(pc, ("thug", (6, 5)), faces={"Attack": face, "Damage": 1})
        pc.hp = pc.hp_max = 200
        s.turn = 1
        was = tuple(s.positions["pc"][:2])
        _attack(e, by="c1", target="pc")
        assert tuple(s.positions["pc"][:2]) == was


def test_landing_roll_rolls_out_of_the_trippers_reach_and_stays_prone():
    """UC: "If you are tripped, you can spend an immediate action to move 5 feet without
    provoking an attack of opportunity ... You fall prone after this movement."."""
    from rules import reactions

    pc = _pc("fighter", feats=["Landing Roll"])
    s, e = _board(pc, ("thug", (6, 5)), faces={"Combat manoeuvre": 20, "CMB": 20,
                                                "Trip": 20})
    s.turn = 1
    res = _attack(e, by="c1", target="pc", manoeuvre="trip")
    assert pc.has_state("state.position.prone"), _tells(res)
    assert tuple(s.positions["pc"][:2]) not in reactions.threatened_by(s, "c1", pc.size), \
        _tells(res)


# --- Lightning Stance --------------------------------------------------------------------

def test_lightning_stance_two_moves_give_fifty_percent_concealment_for_a_round():
    """CRB: "If you take two actions to move ... you gain 50% concealment for 1 round."
    One move gives nothing; the second move action also spends the turn's standard
    (put back in feat loop b5-core, once the reach refusal stopped offering a walk and a
    strike after the move)."""
    pc = _pc("fighter", feats=["Lightning Stance"])
    s, e = _board(pc, ("thug", (18, 18)))
    _run(e, {"op": "move", "actor": "pc", "params": {"square": [8, 5]}})
    assert pc.concealment()[0] == 0
    res = _run(e, {"op": "move", "actor": "pc", "params": {"square": [11, 5]}})
    assert pc.concealment()[0] == 50, _tells(res)
    assert "Lightning Stance" in _tells(res)
    assert s.standard_spent.get("pc") == s.round
    pc.tick_effects(1)
    assert pc.concealment()[0] == 0


# --- Razortusk ---------------------------------------------------------------------------

def test_razortusk_bites_for_1d4_plus_strength_and_is_secondary_beside_a_weapon():
    """ARG: "a bite attack for 1d4 points of damage, plus your Strength modifier ... If
    used as part of a full attack action, the bite is considered a secondary attack ...
    at your full base attack bonus -5, and adds half your Strength modifier"."""
    pc = _pc("fighter", feats=["Razortusk"], race="half-orc")
    bite = pc.natural_weapon("bite")
    assert bite is not None and bite["damage"] == "1d4" and bite["type"] == "piercing"
    assert pc.strength_share(bite) == 1.0
    assert pc.strength_share(bite, beside_weapons=True) == 0.5
    pc.feats = []
    assert pc.natural_weapon("bite") is None


# --- Improved Devastating Strike ---------------------------------------------------------

def test_improved_devastating_strike_adds_its_damage_bonus_to_the_confirmation():
    """UC: "Whenever you use Vital Strike ... you gain a bonus on attack rolls to confirm a
    critical hit equal to the bonus on damage rolls you gain from Devastating Strike" —
    +2 with Vital Strike's one extra die, nothing without Vital Strike."""
    pc = _pc("fighter", level=13, feats=["Vital Strike", "Devastating Strike",
                                         "Improved Devastating Strike"])
    key = pc.wielded_key()
    with_vs = sum(m.value for m in pc.confirm_modifiers(key, None, ("vital_strike",)))
    without = sum(m.value for m in pc.confirm_modifiers(key, None, ()))
    assert with_vs - without == 2, (with_vs, without)


# --- Paired Opportunists -----------------------------------------------------------------

def test_paired_opportunists_is_plus_four_on_opportunity_beside_a_partner_who_threatens():
    pc = _pc("fighter", feats=["Paired Opportunists"])
    ally = _pc("fighter", feats=["Paired Opportunists"])
    ally.ref, ally.kind, ally.name = "ally", "npc", "the partner"
    s, e = _board(pc, ("thug", (6, 5)), allies=[(ally, (5, 6))])
    from rules.sheet import situated

    thug = s.actors["c1"]
    with situated(s):
        ctx = pc._roll_context(pc.wielded_key(), defender=thug)
        ctx["opportunity"] = True
        got = sum(m.value for m in pc._buff_mods("combat_mod", "attack", ctx))
        ctx.pop("opportunity")
        plain = sum(m.value for m in pc._buff_mods("combat_mod", "attack", ctx))
        assert got - plain == 4
        s.positions["ally"] = (4, 4)           # still beside the PC, out of the thug's reach
        ctx["opportunity"] = True
        assert sum(m.value for m in pc._buff_mods("combat_mod", "attack", ctx)) == plain


# --- Combat Patrol, Unsanctioned Detection -----------------------------------------------

def test_combat_patrol_widens_the_ring_for_attacks_of_opportunity_only():
    """APG: "As a full-round action ... increasing your threatened area by 5 feet for
    every 5 points of your base attack bonus. Until the beginning of your next turn"."""
    from rules import reactions

    pc = _pc("fighter", level=10, feats=["Combat Patrol"])
    s, e = _board(pc, ("thug", (8, 5)))
    assert (8, 5) not in reactions.threatened_by(s, "pc")
    out = _use(e, "Combat Patrol")
    assert out.status == "resolved", out.tell
    assert s.standard_spent.get("pc") == s.round and s.move_spent.get("pc") == s.round
    s.turn = 1                                       # the thug's turn: off the PC's own
    assert (8, 5) in reactions.threatened_by(s, "pc")
    pc.tick_effects(1)
    assert (8, 5) not in reactions.threatened_by(s, "pc")


def test_unsanctioned_detection_is_plus_ten_sacred_once_a_day():
    pc = _pc("paladin", feats=["Unsanctioned Detection"])
    s, e = _board(pc, ("thug", (9, 5)))
    before = pc.skill_bonus("perception") if hasattr(pc, "skill_bonus") else None
    out = _use(e, "Unsanctioned Detection")
    assert out.status == "resolved", out.tell
    mods = [m for m in pc.skill_modifiers("perception") if m.type == "sacred"]
    assert sum(m.value for m in mods) == 10, [(m.source, m.value) for m in mods]
    new_turn(s)
    assert _use(e, "Unsanctioned Detection").status == "refused"
    del before


# --- Fast Learner ------------------------------------------------------------------------

def test_fast_learner_takes_both_favoured_bonuses_at_a_level_up():
    """ARG: "When you gain a level in a favored class, you gain both +1 hit point and +1
    skill rank instead of choosing either one or the other". Measured against the same
    fighter without it, taking the hit point: one more skill rank, the same hit points."""
    from rules import leveling

    got = {}
    for feats in ([], ["Fast Learner"]):
        pc = _pc("fighter", level=1, feats=feats, race="human")
        pc.favoured, pc.xp = ["hp"], 10 ** 6
        ranks, hp = leveling.skill_ranks(pc)["total"], pc.hp_max
        out = leveling.level_up(pc, favoured="hp", dice=None)
        assert out.get("ok", True), out
        got[bool(feats)] = (pc.favoured[-1], leveling.skill_ranks(pc)["total"] - ranks,
                            pc.hp_max - hp)
    assert got[False][0] == "hp" and got[True][0] == "both"
    assert got[True][1] == got[False][1] + 1
    assert got[True][2] == got[False][2]


# --- Greater Whip Mastery ----------------------------------------------------------------

def test_greater_whip_mastery_keeps_the_whip_through_a_disarm_failed_by_ten(monkeypatch):
    """UC: "you never drop it due to a failed disarm ... attempt". The same disarm failed
    by ten drops a sap, and dropped the whip before the feat."""
    from rules import reactions

    monkeypatch.setattr(reactions, "provoked_by_maneuver", lambda *a, **k: [])
    for feats, kept in (([], False), (["Greater Whip Mastery"], True)):
        pc = _pc("fighter", feats=feats)
        pc.weapons = list(pc.weapons) + ["whip"]
        pc.equipped = "whip"
        pc.abilities["str"] = 1
        s, e = _board(pc, ("thug", (6, 5)), faces={"Combat": 1, "CMB": 1})
        e.dice.faces = {k: 1 for k in ("Disarm", "Combat manoeuvre")}
        res = e.run(e.validate([{"op": "attack", "actor": "pc", "target": "c1",
                                 "because": "test", "params": {"manoeuvre": "disarm",
                                                               "weapon": "whip"}}]))
        while res.awaiting:
            res = e.resume(1)
        out = next(o for o in res.outcomes if o.op == "attack")
        assert out.margin is not None and out.margin <= -10, out.tell
        assert (pc.equipped == "whip") is kept, (feats, out.tell)
