"""Stage 3 of docs/states-effects-tells.md: abilities as documents.

The defect, measured before this existed: Blood Rage's own +2/+2/−2 was authored in
`content/classes/blood-bending.json` and applied by nothing — `_op_use_ability` printed
"+2 attack" into prose and changed no roll, ran three temp-hp specs in sequence so only
the last survived non-stacking, and never touched the rage pool the class declares. The
armament's weapon-swap was a name list and a table column hard-coded in `Actor.weapon`.
Both are class documents now (`paths.<path>.grants`), applied by engine code that does
not know whose class they came from.
"""
from __future__ import annotations

from rules.bestiary import instantiate
from rules.dice import Dice
from rules.engine import Engine, Scene
from rules.sheet import from_dict, load_pc, to_dict


def _bender(level=1):
    d = to_dict(load_pc("fixtures/pc-kesst.json"))
    d["class"] = "blood bending"
    d["level"] = level
    d["ranks"] = {}
    d["paths"] = ["battle blood"]
    return from_dict(d, ref="pc")


def _fight():
    scene = Scene()
    scene.add(_bender())
    scene.add(instantiate("thug", scene=scene, name="the thug"))
    e = Engine(scene, dice=Dice(seed=11))
    e.run(e.validate([{"op": "begin_encounter",
                       "params": {"sides": {"pc": ["pc"], "them": ["c1"]}}}]))
    return scene, e


def _rage(e):
    return e.run(e.validate([{"op": "use_ability", "actor": "pc",
                              "params": {"ability": "Blood Rage"},
                              "because": "test"}])).outcomes[-1]


def test_blood_rage_finally_moves_the_rolls_it_always_claimed():
    """Before: nine specs ran, six produced prose, zero moved a number. Now the
    document's modifiers ride the sheet's own modifier lists, each named in the dice
    popup as the class ability that granted it."""
    scene, e = _fight()
    pc = scene.actors["pc"]
    attack_before = sum(m.value for m in pc.attack_modifiers())
    ac_before = pc.ac()

    out = _rage(e)
    assert out.tell and "rage" in out.tell.lower()
    assert pc.has_condition("blood rage")
    assert pc.has_state("buff.stance.blood-rage")
    assert sum(m.value for m in pc.attack_modifiers()) == attack_before + 2
    assert pc.ac() == ac_before - 2
    assert any(m.source == "Blood Rage" for m in pc.attack_modifiers())
    assert any(m.source == "Blood Rage" for m in pc.damage_modifiers())


def test_blood_rage_banks_temp_hp_per_hit_die_not_a_flat_die():
    """The class says "+2 Temp HP per Hit Die" and a level-1 bender has two Hit Dice
    (2d8 per level), so tier 1 is 4 — not the flat 2, 3 and 4 the old spec list
    rolled in sequence with only the last surviving."""
    scene, e = _fight()
    pc = scene.actors["pc"]
    _rage(e)
    assert pc.temp_hp == 2 * pc.hit_dice
    assert pc.temp_hp_source == "Blood Rage"


def test_blood_rage_spends_the_pool_the_class_declares():
    """The rage pool existed since the class was imported and nothing ever spent it."""
    scene, e = _fight()
    pc = scene.actors["pc"]
    before = pc.pool("rage").current
    _rage(e)
    assert pc.pool("rage").current == before - 1


def test_rage_burns_a_round_per_round_and_ends_when_the_pool_runs_dry():
    """The document's drain, run by the round clock: when the last rage round is
    spent the stance ends and takes its temporary hit points with it — they were
    the rage's, not the character's."""
    scene, e = _fight()
    pc = scene.actors["pc"]
    pc.pool("rage").current = 3
    _rage(e)                                     # costs 1, leaves 2
    assert pc.temp_hp > 0
    for _ in range(2):
        assert pc.has_condition("blood rage")
        scene.round += 0                         # documentation: drain rides rollover
        scene._drain_periodic(pc)
    scene._drain_periodic(pc)                    # pool empty: the stance ends
    assert not pc.has_condition("blood rage")
    assert pc.temp_hp == 0
    assert not any(m.source == "Blood Rage" for m in pc.attack_modifiers())


def test_a_failed_requirement_refuses_gracefully_never_an_intent_error():
    """Required-op meets hard-refusal is the 502 class this repo has buried four
    times: the schema may REQUIRE the op the player declared, so a refusal must be
    an Outcome with the reason printed, never a raise."""
    scene, e = _fight()
    pc = scene.actors["pc"]
    pc.add_condition("fatigued")
    out = _rage(e)
    assert out.op == "use_ability" and out.effects == []
    assert "state.impaired.fatigued" in out.tell
    assert not pc.has_condition("blood rage")


def test_an_empty_pool_refuses_with_the_cost_named():
    scene, e = _fight()
    pc = scene.actors["pc"]
    pc.pool("rage").current = 0
    out = _rage(e)
    assert out.effects == []
    assert "rage pool" in out.tell and "has 0" in out.tell
    assert not pc.has_condition("blood rage")


def test_toggling_off_evaporates_everything_the_document_granted():
    scene, e = _fight()
    pc = scene.actors["pc"]
    _rage(e)
    assert pc.temp_hp > 0
    out = _rage(e)                               # a toggle: using it again ends it
    assert "rage" in out.tell.lower()
    assert not pc.has_condition("blood rage")
    assert pc.temp_hp == 0
    assert not any(m.source == "Blood Rage" for m in pc.attack_modifiers())


def test_greater_and_mighty_rage_are_tier_rungs_not_separate_code():
    """+2 at Control Blood 1, +3 at 3, +4 at 5 — the document's by_tier map through
    the same resolve_effect every tiered ability uses."""
    scene = Scene()
    pc = _bender(level=9)
    # Control Blood is granted by the level table; a level-9 bender's first path has
    # reached at least tier 3.
    from rules import leveling

    tier = leveling.control_blood_for(pc, "battle blood")
    assert tier >= 3
    scene.add(pc)
    scene.add(instantiate("thug", scene=scene, name="the thug"))
    e = Engine(scene, dice=Dice(seed=11))
    e.run(e.validate([{"op": "begin_encounter",
                       "params": {"sides": {"pc": ["pc"], "them": ["c1"]}}}]))
    before = sum(m.value for m in pc.attack_modifiers())
    _rage(e)
    expected = {1: 2, 2: 2, 3: 3, 4: 3, 5: 4}[min(5, tier)]
    assert sum(m.value for m in pc.attack_modifiers()) == before + expected


def test_the_engine_carries_zero_armament_or_rage_special_cases():
    """The stage's own claim, checked mechanically: outside comments, neither
    rules/sheet.py nor rules/engine.py names the armament, the armed punch or blood
    rage. Before this stage, Actor.weapon carried the alias list and the blood
    column by name and the engine's gates matched the strings."""
    import re
    from pathlib import Path

    for path in ("rules/sheet.py", "rules/engine.py"):
        source = Path(path).read_text(encoding="utf-8")
        # Comments and docstrings are welcome to explain the history; only *code* —
        # including the string literals the old gates matched on — must be clean.
        source = re.sub(r'"""(?:.|\n)*?"""', "", source)
        code = "\n".join(
            re.sub(r"#.*$", "", line) for line in source.splitlines())
        for phrase in ("blood armament", "armed punch", "blood rage",
                       "blood gauntlets"):
            assert phrase not in code.lower(), f"{path} still special-cases {phrase!r}"


def test_a_homebrew_document_with_a_bad_pool_is_refused_with_the_fix():
    """The classbuilder's job: a cost naming a pool the class never declares is an
    ability that always refuses with nothing anywhere saying why."""
    import json

    from rules import classbuilder as cb

    d = json.load(open("content/classes/blood-bending.json", encoding="utf-8"))
    assert cb.validate_class(d) == []            # the shipped document is legal
    doc = d["paths"]["battle blood"]["grants"]["Blood Rage"]
    doc["cost"] = {"pool": "fury", "amount": 1}
    problems = cb.validate_class(d)
    assert any("no pool called 'fury'" in p for p in problems)
    assert any("rage" in p for p in problems)    # the fix names the real pools


# --- the coagulator's plate: the first document authored after the grammar shipped ---

def _coagulator(level=1, armour="none"):
    d = to_dict(load_pc("fixtures/pc-kesst.json"))
    d["class"] = "blood bending"
    d["level"] = level
    d["ranks"] = {}
    d["paths"] = ["coagulator"]
    d["armour"] = armour
    return from_dict(d, ref="pc")


def _plate(e):
    return e.run(e.validate([{"op": "use_ability", "actor": "pc",
                              "params": {"ability": "coagulated plate"},
                              "because": "test"}])).outcomes[-1]


def test_coagulated_plate_is_a_document_not_an_engine_branch():
    """The proof the grammar expands without code: this ability was authored as pure
    data after stage 3 shipped. Measured before the fix elsewhere: the tell said
    '+4 ac' while pc.ac() stayed 13 — the effectspec branch reported, never applied."""
    pc = _coagulator()
    scene = Scene(); scene.add(pc)
    e = Engine(scene, dice=Dice(seed=11))
    before = pc.ac()
    _plate(e)
    assert pc.has_state("buff.stance.coagulated-plate")
    assert pc.ac() == before + 4
    assert any(m.source == "Coagulated Plate" for m in pc.ac_modifiers())
    _plate(e)
    assert pc.ac() == before
    assert not pc.has_state("buff.stance.coagulated-plate")


def test_coagulated_plate_scales_with_control_blood():
    """'Armor Bonus to AC equal to 3+ControlBloodLevel' — level 9 is tier 4, +7."""
    pc = _coagulator(level=9)
    scene = Scene(); scene.add(pc)
    e = Engine(scene, dice=Dice(seed=11))
    before = pc.ac()
    _plate(e)
    assert pc.ac() == before + 7


def test_coagulated_plate_does_not_stack_with_worn_armour():
    """Armour-typed on purpose. A breastplate is +6; the tier-1 plate is +4; 1e says
    the better of the two, not ten. Before typing, this test would have read 23."""
    pc = _coagulator(armour="breastplate")
    scene = Scene(); scene.add(pc)
    e = Engine(scene, dice=Dice(seed=11))
    before = pc.ac()
    _plate(e)
    assert pc.ac() == before


def test_iron_clot_is_live_read_dr_that_follows_the_level():
    """Before the `dr` document field, Actor.reductions was statblock-only and the
    old effectspec branch printed 'DR 2/—' without persisting anything. The rungs
    are the class text's own: DR 2/5/8/12 at tiers 1/2/3/5 — and tier 4 keeps DR 8,
    because a tier that grants no new rung leaves the one below in force."""
    for level, want in ((1, 2), (3, 5), (5, 8), (9, 8), (20, 12)):
        pc = _coagulator(level=level)
        dr = pc.damage_reduction("slashing")
        assert dr is not None and dr.amount == want, (level, want, dr)
        assert dr.source == "Iron Clot"


def test_iron_clot_never_touches_energy_and_never_stacks():
    """1e's two easy-to-get-generous rules: DR ignores energy damage, and multiple
    DRs give the best one only — a statblock DR 3/— beside Iron Clot's 2 is 3."""
    pc = _coagulator(level=1)
    assert pc.damage_reduction("fire") is None
    from rules.sheet import Reduction
    pc.reductions.append(Reduction(3, "", "thick hide"))
    assert pc.damage_reduction("bludgeoning").amount == 3


def test_iron_clot_is_never_a_button():
    """A passive is never used, it simply happens — using it must refuse, not spend
    the turn Swift Strikes once swallowed.

    Refuse, but as an Outcome. This asserted `pytest.raises(IntentError)`, which is the
    502 shape: the intent schema may REQUIRE the op the player declared, so every
    regeneration of the turn carries it, every one is refused for company, and the turn
    dies with a 502 where a sentence would have done. Nine ability names in the shipped
    class file reach this branch. The raise sat twenty lines above the comment in
    _op_use_ability that states this exact rule."""
    pc = _coagulator(level=1)
    scene = Scene(); scene.add(pc)
    e = Engine(scene, dice=Dice(seed=11))
    out = e.run(e.validate([{"op": "use_ability", "actor": "pc",
                             "params": {"ability": "iron clot"},
                             "because": "t"}])).outcomes[-1]
    assert out.effects == [], "a refused passive may not change anything"
    assert "always active" in out.tell and "never used" in out.tell
    assert not out.rolls, "and it may not spend a die either"


def _commander(level=1):
    d = to_dict(load_pc("fixtures/pc-kesst.json"))
    d["class"] = "blood bending"
    d["level"] = level
    d["ranks"] = {}
    d["paths"] = ["blood commander"]
    d["armour"] = "none"
    return from_dict(d, ref="pc")


def test_blood_buffer_guards_incoming_nonlethal_by_the_printed_rungs():
    """'Reduce incoming Non-Lethal Damage by 2 (Lvl 1) or 3 (Lvl 3)' — a dr with
    against: nonlethal, the first document to use the lethality channel."""
    for level, want in ((1, 4), (5, 3)):
        got = _commander(level).take_damage(6, "bludgeoning", lethality="nonlethal")
        assert got["taken"] == want, (level, got)
        assert got["reduced_by"].startswith("DR")


def test_blood_buffer_never_touches_lethal_hits_or_the_benders_own_costs():
    """Incoming means incoming: a lethal sword takes full effect, and the class's
    own ability costs go straight to take_nonlethal and are never discounted —
    a buffer that cheapened costs would quietly rewrite the class economy."""
    assert _commander(1).take_damage(6, "slashing")["taken"] == 6
    assert _commander(1).take_nonlethal(6)["taken"] == 6
