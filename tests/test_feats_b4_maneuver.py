"""Feat loop batch 4, lane b4-maneuver: each feat's numbers measured through the engine.

Before this batch none of these feats had a mechanics document: each was a name on the
sheet that changed no roll (worklist 2026-11-26, b4-maneuver.tsv, 63 feats). The
manoeuvre feats are read off their tags by rules/maneuver_feats.py at three moments of
`Engine._resolve_maneuver` — the CMB die (roll twice), a failed trip's backfire (a trip
weapon let go), and after the manoeuvre (a follow-up, a streak). The tests make the real
manoeuvre and read the terms it rolled with and the state it left.
"""
from __future__ import annotations

import re

from rules.bestiary import instantiate
from rules.dice import Dice
from rules.engine import Engine, Scene
from rules.sheet import load_pc

FOE = "the foe"


class _Faces(Dice):
    """Each roll whose label starts with a key lands on that key's face; the rest roll
    seeded. A list of faces is used up in order (two dice for a roll-twice)."""

    def __init__(self, faces: dict | None = None):
        super().__init__(seed=20261126)
        self.faces = {k: (list(v) if isinstance(v, (list, tuple)) else v)
                      for k, v in (faces or {}).items()}
        self.labels: list[str] = []

    def roll(self, notation, modifiers=None, label="", visibility="hidden"):
        self.labels.append(label or "")
        for prefix, face in self.faces.items():
            if (label or "").startswith(prefix):
                if isinstance(face, list):
                    face = face.pop(0) if len(face) > 1 else face[0]
                if notation == "1d20":
                    return self.given(face, modifiers, label)
                m = re.fullmatch(r"(\d*)d(\d+)", str(notation).strip())
                if m:
                    n = int(m.group(1) or 1)
                    face = max(n, min(face, n * int(m.group(2))))
                return self.given_total(face, notation, modifiers, label)
        return super().roll(notation, modifiers, label, visibility)


def _fight(pc_file="fixtures/pc-borin.json", foe="thug", faces=None, at=((6, 10), (7, 10)),
           feats=(), ally=None, cls=None, level=None, foe_feats=()):
    scene = Scene(location_id="5bbd0c40345f")
    pc = load_pc(pc_file)
    if cls:
        pc.char_class = cls
    if level:
        pc.level = level
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
    for ref in scene.actors:
        scene.acted.add(ref) if isinstance(scene.acted, set) else scene.acted.append(ref)
    return scene, engine, scene.get("pc"), scene.get("c1")


def _settle(engine, res, faces=None):
    faces = list(faces or ())
    while res.awaiting:
        ask = res.awaiting
        label = str(ask.get("label") or "")
        if faces:
            face = faces.pop(0)
        else:
            face = next((f if not isinstance(f, list) else f[0]
                         for k, f in engine.dice.faces.items() if label.startswith(k)), 10)
        res = engine.resume(max(int(ask.get("min") or 1), min(face, int(ask.get("max") or 20))))
    return res


def _maneuver(engine, key, by="pc", target="c1", visibility="hidden", faces=None, **params):
    return _settle(engine, engine.run(engine.validate([{
        "op": "attack", "actor": by, "target": target, "visibility": visibility,
        "params": {"manoeuvre": key, **params}}])), faces)


def _rolls(res, prefix: str) -> list[dict]:
    return [r.as_dict() for o in res.outcomes for r in o.rolls
            if (r.label or "").startswith(prefix)]


def _named(roll: dict, name: str) -> int:
    return sum(int(m["value"]) for m in roll.get("modifiers") or ()
               if str(m.get("source") or m.get("label") or "").startswith(name))


def _effects(res, kind: str) -> list[dict]:
    return [e for o in res.outcomes for e in o.effects if e.get("kind") == kind]


def _tells(res) -> str:
    return " ".join(o.tell or "" for o in res.outcomes)


# --- Tandem Trip: two dice, the better kept ---------------------------------------------

def test_tandem_trip_rolls_twice_only_beside_a_threatening_ally_with_the_feat():
    """Tandem Trip (UC): "Whenever you attempt a trip combat maneuver against an enemy
    threatened by an ally with this feat, you roll twice and take the better result."
    Measured before: one die, a 3, and the trip failed with the feat held by both."""
    for ally_feats, want in ((["Tandem Trip"], 2), ([], 1)):
        scene, engine, pc, thug = _fight(feats=["Tandem Trip"],
                                         faces={"Trip (CMB)": [3, 19]},
                                         ally=((8, 10), ally_feats))
        res = _maneuver(engine, "trip")
        assert sum(1 for lab in engine.dice.labels if lab.startswith("Trip (CMB)")) == want
        if want == 2:
            assert thug.has_state("state.position.prone")
            assert "rolls twice (Tandem Trip): 3 and 19" in _tells(res)


def test_tandem_trip_asks_the_player_for_a_second_die_and_keeps_the_better():
    """The player rolls their own: the popup asks a second die, and the better stands."""
    scene, engine, pc, thug = _fight(feats=["Tandem Trip"],
                                     ally=((8, 10), ["Tandem Trip"]))
    res = engine.run(engine.validate([{"op": "attack", "actor": "pc", "target": "c1",
                                       "visibility": "player",
                                       "params": {"manoeuvre": "trip"}}]))
    res = engine.resume(2)
    assert res.awaiting and "second die (Tandem Trip)" in res.awaiting["label"]
    res = _settle(engine, engine.resume(20))
    assert thug.has_state("state.position.prone")


# --- Topple Foe: flanking allies and the streak -----------------------------------------

def test_topple_foe_needs_a_larger_foe_and_a_flanking_ally_and_grows_each_round():
    """Topple Foe (Rival Guide): +1 with an ally who has the feat flanking a larger foe,
    "+1 per ally" more on each consecutive round's trip at the same foe, +4 at most.
    Measured before: +0 on every trip, an ogre flanked or not."""
    scene, engine, pc, ogre = _fight(foe="ogre", feats=["Topple Foe"],
                                     faces={"Trip (CMB)": 2},
                                     at=((6, 10), (7, 10)), ally=((9, 10), ["Topple Foe"]))
    seen = []
    for rnd in range(5):
        scene.round = 1 + rnd
        ogre.remove_effects(match=lambda e: True)
        res = _maneuver(engine, "trip")
        seen.append(_named(_rolls(res, "Trip (CMB)")[0], "Topple Foe"))
    assert seen == [1, 2, 3, 4, 4]
    # A gap of a round starts the run again; and without the flanking ally, nothing.
    scene.round += 2
    assert _named(_rolls(_maneuver(engine, "trip"), "Trip (CMB)")[0], "Topple Foe") == 1
    scene.positions["ally"] = (2, 2)
    scene.round += 1
    assert _named(_rolls(_maneuver(engine, "trip"), "Trip (CMB)")[0], "Topple Foe") == 0


# --- the trip weapon feature: Tripping Staff ---------------------------------------------

def test_a_trip_weapon_is_let_go_rather_than_fall_and_tripping_staff_makes_a_staff_one():
    """CRB, trip weapons: "If you are tripped during your own trip attempt, you can drop
    the weapon to avoid being tripped." Tripping Staff (UM): quarterstaves have the trip
    feature. Measured before: the trip feature was read by nothing, and a guisarme's wielder
    went down like anybody's."""
    for weapon, feats, prone in (("quarterstaff", [], True),
                                 ("quarterstaff", ["Tripping Staff"], False),
                                 ("guisarme", [], False)):
        scene, engine, pc, ogre = _fight(foe="ogre", feats=feats, faces={"Trip (CMB)": 1})
        pc.weapons = list(pc.weapons) + [weapon]
        pc.equipped = weapon
        res = _maneuver(engine, "trip", weapon=weapon)
        assert pc.has_state("state.position.prone") is prone, (weapon, feats)
        assert (pc.equipped == weapon) is prone
        if not prone:
            assert _effects(res, "dropped")[0]["item"] == weapon


def test_tripping_twirl_trips_every_adjacent_foe_with_a_staff_in_both_hands(monkeypatch):
    """Tripping Twirl (UM): "As a full-round action, while wielding a quarterstaff
    two-handed, you can attempt a trip combat maneuver against each enemy adjacent to you."
    Two thugs beside the fighter: both go down from one declared twirl."""
    from rules import feats as feats_mod

    monkeypatch.setattr(feats_mod, "meets", lambda actor, feat: {"ok": True, "unmet": [],
                                                                  "unknown": []})
    scene, engine, pc, thug = _fight(feats=["Tripping Twirl"], faces={"Trip (CMB)": 19})
    scene.add(instantiate("thug", scene=scene, name="the second"))
    scene.positions["c2"] = (5, 10)
    scene.sides = {"pc": ["pc"], "them": ["c1", "c2"]}
    scene.resync_zones()
    pc.weapons = list(pc.weapons) + ["quarterstaff"]
    pc.equipped = "quarterstaff"
    assert engine._attack_choice_refusal(pc, "longsword", {"tripping_twirl": True})
    res = _settle(engine, engine.run(engine.validate([{
        "op": "attack", "actor": "pc", "target": "c1", "visibility": "hidden",
        "params": {"weapon": "quarterstaff", "tripping_twirl": True}}])))
    assert thug.has_state("state.position.prone")
    assert scene.get("c2").has_state("state.position.prone"), _tells(res)
    assert scene.move_spent.get("pc") == scene.round      # the whole round


# --- follow-ups: Binding Throw, Spinning Throw, Break Guard ------------------------------

def test_binding_throw_grapples_after_a_ki_throw_with_the_swift_action():
    """Binding Throw (UC): "After you successfully use the Ki Throw feat on an opponent,
    you can use a swift action to attempt a grapple combat maneuver against that opponent."
    Measured before: the thrown thug lay prone and free."""
    scene, engine, pc, thug = _fight(feats=["Improved Unarmed Strike", "Ki Throw",
                                            "Binding Throw", "Improved Grapple"],
                                     faces={"Trip (CMB)": 19, "Grapple (CMB)": 19})
    scene.turn = [r for r, _ in scene.initiative].index("pc")
    res = _maneuver(engine, "trip", weapon="unarmed")
    assert thug.has_state("state.position.prone")
    assert thug.has_state("state.held.grappled"), _tells(res)
    assert scene.swift_spent.get("pc") == scene.round
    # No swift left, no grapple: said, not taken.
    scene2, engine2, pc2, thug2 = _fight(feats=["Improved Unarmed Strike", "Ki Throw",
                                               "Binding Throw"],
                                         faces={"Trip (CMB)": 19, "Grapple (CMB)": 19})
    scene2.turn = [r for r, _ in scene2.initiative].index("pc")
    scene2.swift_spent["pc"] = scene2.round
    res2 = _maneuver(engine2, "trip", weapon="unarmed")
    assert not thug2.has_state("state.held.grappled")
    assert "swift action" in _tells(res2)


def test_spinning_throw_bull_rushes_the_tripped_foe_and_leaves_it_prone():
    """Spinning Throw (UC): "On a successful unarmed trip ... against an opponent your size
    or smaller, you can spend a swift action to attempt a bull rush ... push that opponent
    the number of 5-foot increments your successful bull rush allows. The target is then
    knocked prone." Measured before: the thug lay in the square it fell in."""
    scene, engine, pc, thug = _fight(feats=["Improved Unarmed Strike", "Spinning Throw"],
                                     faces={"Trip (CMB)": 19, "Bull Rush (CMB)": 19})
    scene.turn = [r for r, _ in scene.initiative].index("pc")
    res = _maneuver(engine, "trip", weapon="unarmed")
    assert tuple(scene.positions["c1"])[:2] != (7, 10), _tells(res)
    assert thug.has_state("state.position.prone")
    # Not an unarmed trip: no throw.
    scene2, engine2, pc2, thug2 = _fight(feats=["Spinning Throw"],
                                         faces={"Trip (CMB)": 19, "Bull Rush (CMB)": 19})
    scene2.turn = [r for r, _ in scene2.initiative].index("pc")
    _maneuver(engine2, "trip")
    assert tuple(scene2.positions["c1"])[:2] == (7, 10)


def test_break_guard_follows_a_disarm_with_the_off_hand_weapon():
    """Break Guard (UC): "While wielding two weapons, whenever you successfully use one
    weapon to disarm an opponent, you can spend a swift action to attack the opponent you
    attempted to disarm using your other weapon." Measured before: the disarm ended it."""
    scene, engine, pc, thug = _fight(feats=["Two-Weapon Fighting", "Break Guard"],
                                     faces={"Disarm (CMB)": 19, "Attack with": 15})
    scene.turn = [r for r, _ in scene.initiative].index("pc")
    pc.shield = "none"
    res = _maneuver(engine, "disarm", iteration=0, off_hand="dagger")
    assert _rolls(res, "Attack with dagger"), _tells(res)
    assert scene.swift_spent.get("pc") == scene.round


# --- the Stunning Fist variants: Bonebreaker, Neckbreaker --------------------------------

def _monk(feats):
    from tests.test_feats_b2_attack_a import _pc

    monk = _pc("monk", 8, feats=feats)
    monk.abilities["wis"] = 40
    monk.equipped = "unarmed"
    monk.armour = "none"                    # a monk in leather loses the flurry
    return monk


def _bout(monk):
    from tests.test_feats_b2_attack_a import _adjacent, _fight as fight2

    scene, e = fight2(monk)
    _adjacent(scene)
    return scene, e, scene.actors["c1"]


def test_bonebreaker_deals_the_chosen_score_to_a_held_foe_only():
    """Bonebreaker (UC): against an opponent "grappled, helpless, or stunned ... forgo any
    other Stunning Fist effect to deal 1d6 Strength or Dexterity damage." Measured before:
    the feat had no use at all; "use Bonebreaker" was refused by name."""
    from tests.test_feats_b2_attack_a import _swing, _use

    scene, e, thug = _bout(_monk(["Bonebreaker"]))
    _use(e, "Bonebreaker")
    res = _swing(e, face=19)
    assert not thug.ability_damage and "no hold" in _tells(res)
    thug.add_condition("grappled", 10, source="test")
    _use(e, "Bonebreaker (dexterity)")
    res = _swing(e, face=19)
    assert thug.ability_damage.get("dex", 0) >= 1 and not thug.ability_damage.get("str"), \
        _tells(res)
    assert not thug.has_state("state.unable.stunned")


def test_neckbreaker_needs_a_pin_it_holds_and_pours_the_rest_into_constitution():
    """Neckbreaker (UC): against a pinned or helpless foe no larger, "after you initiate or
    maintain a grapple ... a Stunning Fist attempt at a -5 penalty on the attack roll ...
    2d6 Strength or Dexterity damage. If the targeted ability score is reduced to 0, any
    remaining damage is dealt to that opponent's Constitution score.\""""
    from rules.engine import _held_by
    from tests.test_feats_b2_attack_a import _swing, _use

    scene, e, thug = _bout(_monk(["Neckbreaker"]))
    thug.add_condition("pinned", 10, source="test")
    _use(e, "Neckbreaker")
    res = _swing(e, face=19)
    assert not thug.ability_damage and "not grappling" in _tells(res)
    _held_by(thug, "pinned", "pc", grappler="pc")
    thug.abilities["str"] = 3
    _use(e, "Neckbreaker")
    res = _swing(e, face=19)
    hit = [r for o in res.outcomes for r in o.rolls if r.label.startswith("Attack with")]
    assert any(m.value == -5 for m in hit[0].modifiers), "the -5 rides the blow"
    assert thug.ability_score("str") == 0 and thug.ability_damage.get("con", 0) >= 1, \
        _tells(res)


# --- the feint feats ---------------------------------------------------------------------

def _no_prereqs(monkeypatch):
    from rules import feats as feats_mod

    monkeypatch.setattr(feats_mod, "meets", lambda actor, feat: {"ok": True, "unmet": [],
                                                                  "unknown": []})


def _flurry(feats, monkeypatch, **params):
    from tests.test_feats_b2_attack_a import _swing

    _no_prereqs(monkeypatch)
    monk = _monk(feats)
    monk.abilities["cha"] = 40                    # the feint lands
    scene, e, thug = _bout(monk)
    thug.hp = thug.hp_max = 500                   # standing through every blow
    res = _swing(e, face=15, full_attack=True, flurry=True, **params)
    return scene, e, thug, res


def test_feinting_flurry_trades_the_first_blow_for_a_feint_that_opens_the_next():
    """Feinting Flurry (Dragon Empires Primer): "While using flurry of blows to make melee
    attacks, you can forgo your first attack to make a Bluff check to feint." Measured
    before: no flurry could feint; a feint was its own standard action."""
    _s, _e, _t, plain = _flurry(["Feinting Flurry"], monkeypatch=_MP())
    scene, e, thug, res = _flurry(["Feinting Flurry"], _MP(), feinting_flurry=True)
    swings = lambda r: len(_rolls(r, "Attack with"))            # noqa: E731
    assert _rolls(res, "Bluff check (feint)"), _tells(res)
    assert swings(res) == swings(plain) - 1
    assert "feint has drawn" in _tells(res)
    assert not thug.has_state("state.feinted.pc")       # the next blow spent it


def test_improved_feinting_flurry_keeps_the_foe_open_for_the_whole_turn():
    """Improved Feinting Flurry: "if you successfully feint, your opponent is denied its
    Dexterity bonus to AC until the end of your turn" — not only against the next blow."""
    scene, e, thug, res = _flurry(["Feinting Flurry", "Improved Feinting Flurry"], _MP(),
                                  feinting_flurry=True)
    assert thug.has_state("state.feinted.pc"), _tells(res)
    assert _tells(res).count("feint has drawn") >= 1


def test_feinting_flurry_is_refused_without_a_flurry():
    _no = _MP()
    _no_prereqs(_no)
    monk = _monk(["Feinting Flurry"])
    scene, e, thug = _bout(monk)
    assert "flurry" in e._attack_choice_refusal(monk, "unarmed", {"feinting_flurry": True,
                                                                  "full_attack": True})
    _no.undo()


def test_wave_strike_feints_with_the_swift_action_behind_a_first_turn_draw():
    """Wave Strike (UC): "If on your first turn of combat you draw a melee weapon to
    attack an opponent within your reach, you can spend a swift action to make a Bluff
    check to feint against that opponent." Measured before: the draw and the blow only."""
    scene, engine, pc, thug = _fight(feats=["Wave Strike"],
                                     faces={"Bluff check (feint)": 20, "Attack with": 12})
    pc.abilities["cha"] = 40
    pc.equipped = "unarmed"
    scene.acted.discard("pc")
    scene.turn = [r for r, _ in scene.initiative].index("pc")
    res = _settle(engine, engine.run(engine.validate([{
        "op": "attack", "actor": "pc", "target": "c1", "visibility": "hidden",
        "params": {"weapon": "longsword"}}])))
    assert _rolls(res, "Bluff check (feint)"), _tells(res)
    assert scene.swift_spent.get("pc") == scene.round
    assert "feint has drawn" in _tells(res)
    # Not the first turn: no feint.
    scene2, engine2, pc2, thug2 = _fight(feats=["Wave Strike"],
                                         faces={"Bluff check (feint)": 20})
    pc2.equipped = "unarmed"
    res2 = _settle(engine2, engine2.run(engine2.validate([{
        "op": "attack", "actor": "pc", "target": "c1", "visibility": "hidden",
        "params": {"weapon": "longsword"}}])))
    assert not _rolls(res2, "Bluff check (feint)")


def test_disengaging_shot_strikes_the_feinted_foe_open_before_stepping_away():
    """Disengaging Shot (UC): "Whenever you use Disengaging Feint ... you can make a single
    melee attack against one opponent you succeeded at feinting against. That opponent is
    denied his Dexterity bonus to AC against this attack." Measured before: the feint let
    the rogue slip away and struck nothing."""
    scene, engine, pc, thug = _fight("fixtures/pc-kesst.json",
                                     feats=["Disengaging Feint", "Disengaging Shot"],
                                     faces={"Bluff check (feint)": 20, "Attack with": 12})
    scene.turn = [r for r, _ in scene.initiative].index("pc")
    res = _settle(engine, engine.run(engine.validate([{
        "op": "check", "actor": "pc", "target": "c1", "visibility": "hidden",
        "params": {"skill": "bluff", "feint": True, "disengage": True}}])))
    attacks = [o for o in res.outcomes if o.op == "attack"]
    assert attacks and "feint has drawn" in attacks[0].tell, _tells(res)
    assert not thug.has_state("state.feinted.pc")


class _MP:
    """A monkeypatch usable outside the fixture (two set-ups in one test)."""

    def __init__(self):
        import pytest

        self._mp = pytest.MonkeyPatch()

    def setattr(self, *a, **k):
        self._mp.setattr(*a, **k)

    def undo(self):
        self._mp.undo()


# --- Hard-Headed, Human Spirit -----------------------------------------------------------

def test_hard_headed_adds_two_against_what_staggers_or_stuns_and_nothing_else():
    """Hard-Headed (ARG): "+2 bonus on saves against spells and special abilities that
    cause you to become staggered or stunned." Measured before: no save knew what it was
    against beyond "spell", and stunning fist's save knew nothing at all."""
    from rules import effectspec, spells

    dwarf = load_pc("fixtures/pc-borin.json")
    dwarf.feats = list(dwarf.feats) + ["Hard-Headed"]

    def term(spell_id):
        ctx = {"against": effectspec.spell_against(spells.get(spell_id))}
        return sum(m.value for m in dwarf.save_modifiers("will", ctx=ctx)
                   if str(m.source).startswith("Hard-Headed"))

    assert term("color-spray") == 2 and term("slow") == 2
    assert term("daze") == 0 and term("charm-person") == 0


def test_hard_headed_reaches_the_save_against_a_stunning_fist():
    from tests.test_feats_b2_attack_a import _swing, _use

    scene, e, thug = _bout(_monk([]))
    thug.feats = list(thug.feats or ()) + ["Hard-Headed"]
    _use(e, "Stunning Fist")
    res = _swing(e, face=19)
    saves = [e["roll"] for o in res.outcomes for e in o.effects
             if str((e.get("roll") or {}).get("label") or "").startswith("Fortitude save")]
    assert saves and _named(saves[0], "Hard-Headed") == 2, _tells(res)


def test_human_spirit_adds_a_rank_a_hit_die_up_to_four():
    """Human Spirit (ARG): "You receive 1 bonus skill rank. Whenever you gain another Hit
    Die, you gain an additional skill rank. You cannot gain more than four skill ranks in
    this way." Measured before: the ranks a character could place did not move."""
    from rules import leveling

    for level, more in ((1, 1), (3, 3), (6, 4)):
        pc = load_pc("fixtures/pc-kesst.json")
        pc.level = level
        before = leveling.skill_ranks(pc)["total"]
        pc.feats = list(pc.feats) + ["Human Spirit"]
        assert leveling.skill_ranks(pc)["total"] - before == more


# --- Siphon Poison -----------------------------------------------------------------------

def _bitten(scene, pc, vector="injury", dc=14):
    from rules.sheet import situated

    aff = {"kind": "poison", "vector": vector, "save": "fort", "dc": dc, "cure": 1,
           "effects": [{"ability": "str", "dice": "1", "drain": False}]}
    with situated(scene):
        eff, _ = pc.take_affliction(aff, name="spider venom", source="t",
                                    origin="author:test", onset_rounds=1, every_rounds=1,
                                    limit=6)
    return eff


def test_siphon_poison_draws_a_fresh_injury_poison_out_in_a_full_round():
    """Siphon Poison (Champions of Purity): "As a full-round action, you can remove an
    injury poison ... with a successful Heal check. The DC of this check is equal to the
    poison's DC. You can only draw out poison in this way within the first 2 rounds."
    Measured before: Heal on a fresh bite only lent +4 to the next save."""
    from tests.test_body_skills import _check, _run, _scene

    scene, engine, pc = _scene(faces={"Heal": 15}, fight=True)
    pc.feats = list(pc.feats) + ["Siphon Poison"]
    _bitten(scene, pc)
    out = _run(engine, _check(skill="heal", dc={"band": "average"}))[0]
    assert "Siphon Poison" in out.tell and not pc.has_state("state.poisoned"), out.tell
    assert scene.move_spent.get("pc") == scene.round        # the whole round
    # Three rounds on, or an ingested poison: the plain treatment and its +4.
    for later, vector in ((3, "injury"), (0, "ingested")):
        scene, engine, pc = _scene(faces={"Heal": 15}, fight=True)
        pc.feats = list(pc.feats) + ["Siphon Poison"]
        _bitten(scene, pc, vector=vector)
        scene.round += later
        out = _run(engine, _check(skill="heal", dc={"band": "average"}))[0]
        assert "Siphon Poison" not in out.tell and pc.has_state("care.treated.poison")


# --- Greater Wild Empathy ------------------------------------------------------------------

def test_greater_wild_empathy_reaches_the_chosen_kind_adds_two_and_intimidates():
    """Greater Wild Empathy (UM): "+2 insight bonus on wild empathy checks, and you may use
    wild empathy to duplicate an Intimidate check ... choose one of the following kinds of
    creatures: elementals, fey, lycanthropes, plants, or vermin. You may influence
    creatures of that type with wild empathy, if their Intelligence score is 1 or 2, or
    they do not possess an Intelligence score." Measured before: a giant spider was out of
    reach and an Intimidate at a wolf was Kesst's untrained Intimidate."""
    from rules import animals, attitude
    from tests.test_handle_animal import _check as hcheck, _run as hrun, _scene as hscene

    scene, engine, pc, (wolf, spider) = hscene(("wolf", "the wolf"),
                                               ("giant-spider", "the spider"),
                                               faces={"Wild empathy": 18}, druid=True)
    assert animals.empathy_reaches(spider, pc) is None
    plain = sum(m.value for m in animals.empathy_mods(pc))
    pc.feats = list(pc.feats) + ["Greater Wild Empathy (vermin)"]
    assert animals.empathy_reaches(spider, pc) == 0
    assert sum(m.value for m in animals.empathy_mods(pc)) == plain + 2
    out = hrun(engine, hcheck(skill="intimidate", target=wolf.ref))[0]
    assert out.rolls and out.rolls[0].label == "Wild empathy check", out.tell
    assert out.dc["value"] == attitude.intimidate_dc(wolf)


# --- Undermining Exploit --------------------------------------------------------------------

def test_undermining_exploit_adds_four_against_a_foe_on_rocky_difficult_ground():
    """Undermining Exploit (Faiths of Purity): "+4 insight bonus on combat maneuvers
    against opponents that are located in rocky, difficult terrain." Measured before: +0
    with the thug in a rubble square in the hills."""
    from tests._places import stand_on

    for ground, rough, want in (("mountain", True, 4), ("mountain", False, 0),
                                ("forest", True, 0)):
        scene, engine, pc, thug = _fight(feats=["Undermining Exploit"],
                                         faces={"Trip (CMB)": 2})
        stand_on(scene, ground)
        if rough:
            scene.grid.difficult.add((7, 10))
        res = _maneuver(engine, "trip")
        assert _named(_rolls(res, "Trip (CMB)")[0], "Undermining Exploit") == want, ground


# --- Gory Finish -----------------------------------------------------------------------------

def test_gory_finish_shakes_every_foe_who_saw_the_kill():
    """Gory Finish (UC): a single attack with a Weapon Focus weapon; "If you reduce your
    target to negative hit points, you can spend a swift action to make an Intimidate check
    to demoralize all foes within 30 feet who could see your attack." Measured before: the
    second thug watched his friend fall unmoved."""
    scene, engine, pc, thug = _fight(feats=["Dazzling Display", "Gory Finish"],
                                     faces={"Attack with": 18, "Intimidate": 20,
                                            "Damage": 12})
    scene.add(instantiate("thug", scene=scene, name="the second"))
    scene.positions["c2"] = (9, 12)
    scene.sides = {"pc": ["pc"], "them": ["c1", "c2"]}
    scene.resync_zones()
    scene.turn = [r for r, _ in scene.initiative].index("pc")
    thug.hp = 1
    assert engine._attack_choice_refusal(pc, "longsword", {"gory_finish": True,
                                                           "full_attack": True})
    pc.weapons = list(pc.weapons) + ["club"]
    assert engine._attack_choice_refusal(pc, "club", {"gory_finish": True, "weapon": "club"})
    res = _settle(engine, engine.run(engine.validate([{
        "op": "attack", "actor": "pc", "target": "c1", "visibility": "hidden",
        "params": {"gory_finish": True}}])))
    assert thug.hp < 0
    assert scene.get("c2").has_state("state.fear.shaken"), _tells(res)
    assert scene.swift_spent.get("pc") == scene.round


# --- Mounted Shield -------------------------------------------------------------------------

def test_mounted_shield_lends_the_riders_shield_to_the_horses_ac_and_the_ride_check():
    """Mounted Shield (APG): "add your base shield bonus (including the bonus from Shield
    Focus but not including enhancement bonuses) to your mount's AC. In addition, you may
    add this bonus when making a Ride check to negate a hit against your mount using the
    Mounted Combat feat." Measured before: the horse's AC was its own with Borin's heavy
    shield on his arm."""
    from rules import bodyskills
    from rules.sheet import situated
    from tests.test_body_skills import _check as bcheck, _run as brun, _stable

    scene, engine, pc, horse = _stable(faces={"Ride": 20}, fight=False)
    pc.shield = "heavy wooden shield" if "heavy wooden shield" in __import__(
        "rules.tables", fromlist=["SHIELDS"]).SHIELDS else "heavy steel shield"
    brun(engine, bcheck(skill="ride", use="mount"))
    assert bodyskills.mount_of(scene, pc) is horse
    with situated(scene):
        before = horse.ac()
        pc.feats = list(pc.feats) + ["Mounted Combat", "Shield Focus", "Mounted Shield"]
        lent = horse.ac() - before
    assert lent == 2 + 1                                 # heavy shield +2, Shield Focus +1
    from rules import maneuver_feats

    assert sum(m.value for m in maneuver_feats.shield_on_ride(pc)) == 3


# --- Trample, Unseat --------------------------------------------------------------------------

def _mounted_rider(faces, feats):
    from rules import bodyskills
    from tests.test_body_skills import _check as bcheck, _run as brun, _stable

    scene, engine, pc, horse = _stable(faces=faces, fight=True)
    pc.feats = list(pc.feats) + list(feats)
    brun(engine, bcheck(skill="ride", use="mount"))
    assert bodyskills.mount_of(scene, pc) is horse
    foe = scene.get("c2")
    scene.positions["c2"] = (7, 5)
    scene.resync_zones()
    scene.turn = [r for r, _ in scene.initiative].index("pc")
    return scene, engine, pc, horse, foe


def test_trample_lets_the_horse_stamp_on_the_one_its_rider_overran():
    """Trample (CRB): "Your mount may make one hoof attack against any target you knock
    down, gaining the standard +4 bonus on attack rolls against prone targets." Measured
    before: the thug lay prone under the horse and nothing struck him."""
    scene, engine, pc, horse, foe = _mounted_rider({"Ride": 20, "Overrun (CMB)": 20,
                                                    "Attack with": 15},
                                                   ["Mounted Combat", "Trample"])
    res = _settle(engine, engine.run(engine.validate([{
        "op": "attack", "actor": "pc", "target": "c2", "visibility": "hidden",
        "params": {"manoeuvre": "overrun"}}])))
    assert foe.has_state("state.position.prone"), _tells(res)
    hooves = [o for o in res.outcomes if o.op == "attack" and o.actor == horse.ref]
    assert hooves, _tells(res)


def test_unseat_knocks_a_charged_rider_out_of_the_saddle():
    """Unseat (CRB): a mounted lance charge that hits makes "a free bull rush attempt ...
    If successful, the target is knocked off his horse and lands prone in a space adjacent
    to his mount that is directly away from you." Measured before: the foe stayed seated."""
    from rules import bodyskills, maneuver_feats
    from rules.engine import Intent

    scene, engine, pc, horse, foe = _mounted_rider({"Ride": 20, "Bull Rush (CMB)": 20},
                                                   ["Mounted Combat", "Unseat"])
    steed = scene.add(instantiate("heavy-horse", scene=scene, name="the grey"))
    scene.positions[steed.ref] = (8, 5)
    scene.positions["c2"] = (8, 5)
    from rules.activeeffect import ActiveEffect

    foe.apply_effect(ActiveEffect(name="mounted", kind="situation", key="mounted",
                                  source="t", tags=(bodyskills.MOUNTED,),
                                  payload={"mount": steed.ref}))
    steed.apply_effect(ActiveEffect(name="ridden", kind="situation", key="ridden",
                                    source="t", tags=(bodyskills.RIDDEN,),
                                    payload={"by": "c2"}))
    assert bodyskills.mount_of(scene, foe) is steed
    pc.weapons = list(pc.weapons) + ["lance"]
    intent = Intent(op="attack", actor="pc", target="c2", params={"charge": True})
    from rules.sheet import situated

    with situated(scene):
        got = maneuver_feats.unseat(engine, intent, pc, foe, "lance", ("charge",))
    assert bodyskills.mount_of(scene, foe) is None, [g["tell"] for g in got]
    assert foe.has_state("state.position.prone")
    assert tuple(scene.positions["c2"])[:2] != (8, 5)
    # Not a charge, no unseat.
    assert maneuver_feats.unseat(engine, intent, pc, foe, "lance", ()) == []


# --- Cypher Script ----------------------------------------------------------------------------

def test_cypher_script_halves_the_ink_and_writes_in_ten_minutes_a_level():
    """Cypher Script (ISWG): "Any spell you scribe in your spellbook costs half as much as
    normal ... It only takes you 10 minutes per spell level to scribe." Measured before: a
    1st-level copy cost 10 gp and 120 minutes, feat or not."""
    from rules import spellitems
    from tests.test_spell_items import _wizard

    for feats, cost, minutes in (([], 10, 120), (["Cypher Script"], 5, 70)):
        pc = _wizard()
        pc.spellbook = [s for s in pc.spellbook if s != "magic-missile"]
        pc.feats = list(pc.feats) + feats
        pc.add_stock(spellitems.make("scroll", "magic-missile", how="bought"), 1)
        sid = next(k for k, v in pc.stock.items() if spellitems.kind_of(v))
        plan = spellitems.copy_plan(pc, pc.stock[sid], clock=0)
        assert (plan["cost_gp"], plan["minutes"]) == (cost, minutes), plan
