"""`_op_cast` rolling a spell's dice instead of printing them.

For as long as there was a spell system, casting spent the slot, stated the caster level
and the save DC, and stopped — because "a parser guessing mechanics out of three thousand
English paragraphs would produce confident wrong numbers". That was right, and it is now
narrower rather than wrong: 354 of the 3,040 carry effects that were read mechanically and
validated against `effectspec`, and 2,686 still do not. The boundary moved from per-corpus
to **per-spell**.

What these tests pin, and why each one is here:

* One roll for the whole spell. A fireball is rolled once and everyone in the area saves
  against that number; rolling per target hands two creatures in one blast different
  damage.
* A successful save halves **the rolled total**, not a second roll of half the dice.
  `effectspec` cannot say "roll and halve" — the stored success branch carries half the
  *dice* — so the engine does it where the number exists.
* The DC is `casting.save_dc(actor, level)` and never the string the spec carries. A spell
  cannot know the caster's ability modifier, so `spells.SAVE_DC_FORMULA` is a placeholder,
  and a placeholder that reached a comparison would be a crash or, worse, a silent one.
* A spell with no effects still narrates and touches nobody's hit points. That is the
  honest signal for the 2,686, and the path they had was already correct.
* The player rolls their own damage. `_op_attack` learned this the hard way: defaulting a
  PC's rolls to hidden "meant the engine silently rolled the player's attacks for them,
  which contradicts the architecture decision outright".
* The slot is spent once across a suspension. A cast that suspends for the player's dice
  and re-spends on the way back costs two slots for one fireball.
"""
from __future__ import annotations

import pytest

from rules import casting, spells as spells_mod
from rules.bestiary import instantiate
from rules.dice import Dice
from rules.engine import Engine, Scene
from rules.sheet import from_dict, load_pc, to_dict


def wizard(level=10, book=("fireball", "magic-missile", "teleport", "bless"),
           prepared=None, int_score=18):
    d = to_dict(load_pc("fixtures/pc-kesst.json"))
    d.update({"class": "wizard", "level": level, "ranks": {}})
    d["abilities"]["int"] = int_score
    d["spellbook"] = list(book)
    d["prepared"] = dict({k: 3 for k in book} if prepared is None else prepared)
    return from_dict(d, ref="pc")


def cleric(level=5, book=("cure-light-wounds",), prepared=None):
    d = to_dict(load_pc("fixtures/pc-kesst.json"))
    d.update({"class": "cleric", "level": level, "ranks": {}})
    d["abilities"]["wis"] = 18
    d["spellbook"] = list(book)
    d["prepared"] = dict({k: 3 for k in book} if prepared is None else prepared)
    return from_dict(d, ref="pc")


def table(caster, seed=5):
    s = Scene(location_id="5bbd0c40345f")
    s.add(caster)
    s.add(instantiate("thug", scene=s, name="the thug"))
    return s, Engine(s, Dice(seed=seed))


def cast(engine, spell, at="c1", visibility=None):
    intent = {"op": "cast", "actor": "pc", "because": "she speaks the word",
              "params": {"spell": spell, "at": at}}
    if visibility:
        intent["visibility"] = visibility
    return engine.run(engine.validate([intent]))


def damage_effects(outcome):
    return [e for e in outcome.effects if e.get("kind") == "damage"]


# --- the dice are rolled, once ---------------------------------------------------------------

def test_a_fireball_at_caster_level_ten_rolls_ten_d6():
    """The spell's own formula, at this caster's level, actually rolled. Before this the
    outcome said "Reflex half, DC 17" and the 10d6 was a sentence in the description that
    nothing read."""
    w = wizard(level=10)
    _, e = table(w)
    out = cast(e, "fireball").outcomes[0]

    assert out.effects[0]["dice"] == "10d6"
    dice_rolls = [r for r in out.rolls if r.die == "10d6"]
    assert len(dice_rolls) == 1, "the spell's dice are rolled once, not per target"
    assert 10 <= dice_rolls[0].total <= 60


def test_the_same_fireball_at_caster_level_five_rolls_five_d6():
    """Scaling reaches the engine rather than stopping at the schema."""
    w = wizard(level=5, prepared={"fireball": 1})
    _, e = table(w)
    out = cast(e, "fireball").outcomes[0]
    assert out.effects[0]["dice"] == "5d6"
    assert [r for r in out.rolls if r.die == "5d6"]


def test_the_target_actually_loses_hit_points():
    w = wizard(level=10)
    s, e = table(w)
    before = s.actors["c1"].hp
    out = cast(e, "fireball").outcomes[0]
    hits = damage_effects(out)
    assert hits, "a fireball that hits nobody is the bug this whole change exists to fix"
    assert s.actors["c1"].hp < before
    assert hits[0]["type"] == "fire"


def test_damage_goes_through_the_one_funnel_every_other_source_uses():
    """`_apply_damage`, so resistance, damage reduction, temporary hit points and
    interception all apply to a spell without a line of their own in `_op_cast`. The
    effect's shape is how you can tell: `rolled` beside `amount` is what that funnel
    produces and nothing else does."""
    w = wizard(level=10)
    _, e = table(w)
    hit = damage_effects(cast(e, "fireball").outcomes[0])[0]
    for key in ("rolled", "amount", "reduced", "absorbed", "hp_after", "lethality"):
        assert key in hit, key


# --- the saving throw ---------------------------------------------------------------------------

@pytest.mark.parametrize("seed", [1, 2, 3, 5, 7, 11, 13, 17, 19, 23])
def test_a_successful_reflex_save_halves_the_rolled_total(seed):
    """Half of the number that was rolled — never a second roll of half the dice.

    Run across ten seeds so both branches are exercised whatever the dice do. The
    invariant is exact: on a failure the target takes the whole rolled total, on a success
    exactly `total // 2`, and there is only ever one damage roll in the outcome.
    """
    w = wizard(level=10)
    _, e = table(w, seed=seed)
    out = cast(e, "fireball").outcomes[0]

    dice_rolls = [r for r in out.rolls if r.die == "10d6"]
    saves = [r for r in out.rolls if r.die == "1d20"]
    assert len(dice_rolls) == 1 and len(saves) == 1
    rolled = dice_rolls[0].total
    dc = out.effects[0]["dc"]
    hit = damage_effects(out)[0]

    if saves[0].total >= dc:
        assert hit["rolled"] == rolled // 2, "a save halves the total that was rolled"
        assert "makes the Reflex save" in out.tell
    else:
        assert hit["rolled"] == rolled, "a failed save takes the whole roll"
        assert "fails the Reflex save" in out.tell


def test_the_dc_is_the_casters_own_and_not_the_formula_string():
    """`spells.SAVE_DC_FORMULA` is a placeholder a spell carries because it cannot know
    the caster's ability modifier. A cast must substitute the real number: 10 + the spell's
    level on this caster's list + their casting modifier. A 10th-level wizard with
    Intelligence 18 casting a 3rd-level spell is 10 + 3 + 4 = 17."""
    w = wizard(level=10, int_score=18)
    _, e = table(w)
    out = cast(e, "fireball").outcomes[0]

    assert out.effects[0]["dc"] == 17
    assert out.effects[0]["dc"] == casting.save_dc(w, 3)
    assert spells_mod.SAVE_DC_FORMULA not in out.tell
    assert "DC 17" in out.tell
    # And the formula string never reaches a comparison as a number.
    assert isinstance(out.effects[0]["dc"], int)


def test_a_higher_casting_stat_raises_the_dc_the_spell_is_saved_against():
    """Proves the DC is computed per caster rather than baked into the spell.

    Intelligence 14 rather than 12, and that is a rule rather than a convenience: 1e wants
    a score of at least 10 + the spell's level to cast it at all, so a wizard with 12
    cannot cast a 3rd-level spell however high their level.
    """
    _, e_low = table(wizard(level=10, int_score=14))
    _, e_high = table(wizard(level=10, int_score=20))
    assert cast(e_low, "fireball").outcomes[0].effects[0]["dc"] == 15
    assert cast(e_high, "fireball").outcomes[0].effects[0]["dc"] == 18


def test_a_spell_with_no_save_damages_without_rolling_one():
    """Magic missile has no saving throw. Rolling one would be the engine inventing a
    mechanic, which is the same defect as printing "DC 17" beside it."""
    w = wizard(level=10)
    _, e = table(w)
    out = cast(e, "magic-missile").outcomes[0]
    assert not [r for r in out.rolls if r.die == "1d20"]
    assert damage_effects(out)
    assert "DC" not in out.tell


# --- the 2,686 that are still prose ---------------------------------------------------------------

def test_a_prose_only_spell_narrates_and_changes_no_hit_points():
    """The honest signal. An empty `spell.effects` means this one's mechanics are English,
    and the narrate-only path it already had is exactly right for it — the outcome states
    the facts and whatever the GM declares arrives as its own validated intent.

    Teleport is the case that made this test worth writing rather than assuming: it *was*
    converted, because its Mishap row says "You each take 1d10 points of damage", and the
    moment casting started rolling, teleporting damaged whatever you aimed at.
    """
    w = wizard(level=10)
    s, e = table(w)
    before = s.actors["c1"].hp
    out = cast(e, "teleport").outcomes[0]

    # "Prose-only" now means "carries no effect the engine executes", not "carries
    # nothing at all". Every spell has a floor of one `narrative` spec so that casting
    # it produces something rather than silence — teleport says what teleporting does
    # and still moves no hit points, which is the thing this test is about.
    fx = spells_mod.get("teleport").effects or []
    assert fx and all(e.get("type") == "narrative" for e in fx)
    assert [x["kind"] for x in out.effects] == ["cast"]
    assert out.rolls == []
    assert s.actors["c1"].hp == before
    assert "casts Teleport" in out.tell


def test_the_slot_is_still_spent_by_a_spell_that_does_nothing_mechanical():
    w = wizard(level=10)
    _, e = table(w)
    before = casting.slots_left(w, 5)
    cast(e, "teleport")
    assert casting.slots_left(w, 5) == before - 1


# --- the player rolls their own -------------------------------------------------------------------

def test_the_player_rolls_their_own_fireball():
    """The architecture decision, enforced the same way attacks enforce it: a PC's roll
    suspends the whole intent list and waits for the popup. An engine that silently rolled
    the player's fireball would contradict it exactly as `_op_attack` once did."""
    w = wizard(level=10)
    _, e = table(w)
    res = cast(e, "fireball", visibility="player")

    assert res.awaiting is not None, "a PC's damage roll must go to the player"
    assert res.awaiting["die"] == "10d6"
    assert res.awaiting["actor"] == w.name
    assert res.awaiting["min"] == 10 and res.awaiting["max"] == 60
    assert res.outcomes == []

    done = e.resume(42)
    assert done.awaiting is None
    out = done.outcomes[0]
    assert [r for r in out.rolls if r.die == "10d6"][0].total == 42


def test_the_slot_is_spent_once_across_a_suspension():
    """`partial` carries the cast's state through the popup. Re-spending on the way back
    would cost two slots for one fireball — and it is the reason the state check guards the
    spend rather than sitting after it."""
    w = wizard(level=10)
    _, e = table(w)
    before = casting.slots_left(w, 3)

    cast(e, "fireball", visibility="player")
    assert casting.slots_left(w, 3) == before - 1, "spent on the way in"
    e.resume(42)
    assert casting.slots_left(w, 3) == before - 1, "and not again on the way back"


def test_an_npcs_save_is_rolled_by_the_engine_even_when_the_caster_is_the_player():
    """The popup only ever asks the player for their own rolls. The caster rolls the
    spell's dice; the thug's Reflex save is the engine's, and asking the player to roll it
    would show them a number nobody at the table rolled."""
    w = wizard(level=10)
    _, e = table(w)
    res = cast(e, "fireball", visibility="player")
    assert res.awaiting["die"] == "10d6"        # the caster's dice, first
    out = e.resume(42).outcomes[0]              # …and then no second prompt
    assert [r for r in out.rolls if r.die == "1d20"], "the save was rolled, by the engine"


# --- healing --------------------------------------------------------------------------------------

def test_a_cure_spell_heals_rather_than_damages():
    """`kind` on the plan is what keeps these apart, and it is not decorative: blaze of
    glory says its healing in the vocabulary of damage — "healed for 1d6 points of
    damage/2 caster levels" — and read as damage it would have burned every good creature
    in range."""
    c = cleric(level=5)
    s, e = table(c)
    c.hp = c.hp - 9
    hurt = c.hp
    out = cast(e, "cure-light-wounds", at="pc").outcomes[0]

    healed = [x for x in out.effects if x.get("kind") == "heal"]
    assert healed and healed[0]["amount"] > 0
    assert c.hp > hurt
    assert not damage_effects(out)
    assert spells_mod.get("blaze-of-glory").scaling["kind"] == "healing"


def test_a_cure_scales_its_flat_bonus_with_caster_level():
    """1d8 + 1 point per caster level, maximum +5 — a different shape from 1d6 per level,
    and the engine has to be handed the right one."""
    c = cleric(level=5)
    _, e = table(c)
    assert e.scene.actors["pc"] is c
    out = cast(e, "cure-light-wounds", at="pc").outcomes[0]
    assert out.effects[0]["dice"] == "1d8+5"


# --- what is carried, and what is deliberately not applied -------------------------------------------

def test_the_outcome_carries_what_a_gm_and_a_player_both_need():
    w = wizard(level=10)
    _, e = table(w)
    cast_effect = cast(e, "fireball").outcomes[0].effects[0]

    assert cast_effect["element"] == "fire"
    assert cast_effect["dice"] == "10d6"
    assert cast_effect["range_feet"] == 800          # long: 400 + 40/level
    assert cast_effect["caster_level"] == 10
    assert cast_effect["effects"], "the specs themselves, for a panel to show"


def test_a_converted_spell_says_so_and_a_hand_written_one_does_not():
    """354 of these numbers were read by a machine and nobody has checked them. A GM who
    cannot tell a conversion from a person's answer is being asked to trust a parse."""
    w = wizard(level=10)
    _, e = table(w)
    assert cast(e, "fireball").outcomes[0].effects[0]["effects_converted"] is True

    w2 = wizard(level=10)
    _, e2 = table(w2)
    assert cast(e2, "magic-missile").outcomes[0].effects[0]["effects_converted"] is False


def test_a_buff_is_shown_to_the_gm_rather_than_invented():
    """Bless's +1 morale bonus is real and is not applied, because applying it needs the
    spell's duration as a number of rounds and "minutes/level (1)" is still prose. Shown
    on the tell instead of given an invented hour — see `spells.casting_plan`."""
    c = cleric(level=5, book=("bless",), prepared={"bless": 1})
    s, e = table(c)
    out = cast(e, "bless", at="pc").outcomes[0]

    assert not damage_effects(out)
    assert "+1 Attack rolls" in out.tell
    plan = spells_mod.casting_plan(spells_mod.get("bless"), 5)
    assert plan["dice"] == "" and len(plan["riders"]) == 2
    assert "duration" in plan["note"]


# --- what a converted formula must never be ---------------------------------------------------------

@pytest.mark.parametrize("spell_id, why", [
    ("teleport", "the 1d10 is its Mishap row, not what teleporting does"),
    ("dream-travel", "same mishap table"),
    ("thorn-body", "damages whoever strikes you, not whoever you cast it at"),
    ("sacred-nimbus", "retribution against an attacker"),
    ("savage-maw", "grants a bite attack; the dice belong to the attack"),
    ("shadow-claws", "grants two claw attacks"),
    ("aspect-of-the-stag", "the dice belong to an attack the spell grants"),
    ("call-the-void", "2d6 at the start of every turn, which one hit understates"),
    ("fire-of-judgment", "per round"),
    ("seer-s-bane", "burns the diviner, not the target"),
    ("blood-crow-strike", "the 2d6 is inside a worked example"),
])
def test_a_formula_the_spell_prints_but_does_not_deal_is_refused(spell_id, why):
    """Thirty-one of these were converted and invisible for as long as nothing rolled them.

    They are the cost of reading prose, and the reason the refusals are keyed on *who takes
    the damage and when* rather than on whether the sentence is conditional: the first
    version of the veto was conditional-based and refused caustic eruption and fire storm,
    both of which deal exactly what they print, once, in an area.
    """
    # The rule is "this spell deals no damage of its own", not "this spell has no
    # mechanics". Asserting the second was a fine proxy while a regex was the only thing
    # writing these — a regex that refused the damage refused everything. Reading them
    # properly made that false: aspect of the stag really does grant +2 dodge AC, +20 ft
    # of speed and a way through undergrowth, and its antler dice are still correctly
    # left as prose. So the assertion is narrowed to what it always meant.
    got = spells_mod.get(spell_id).effects or []
    flat = list(got)
    for spec in got:                      # a save_gate hides its damage one level down
        flat.extend(spec.get("on_failure") or [])
        flat.extend(spec.get("on_success") or [])
    offending = [s for s in flat if s.get("type") in ("damage", "heal")]
    assert offending == [], f"{why}: {offending}"
    assert not spells_mod.get(spell_id).scaling, why


@pytest.mark.parametrize("spell_id", [
    "fireball", "lightning-bolt", "cone-of-cold", "burning-hands", "caustic-eruption",
    "fire-storm", "unlock-flesh", "touch-of-combustion", "disintegrate",
    "cure-light-wounds", "inflict-light-wounds", "searing-light", "magic-missile",
    "flame-strike", "scorching-ray", "shocking-grasp", "lipstitch",
])
def test_the_vetoes_did_not_take_the_real_ones_with_them(spell_id):
    """The other half of the measurement. A veto broad enough to catch teleport's mishap
    is easily broad enough to catch a fireball, and "no false positives" is worth nothing
    on its own."""
    assert spells_mod.get(spell_id).effects, spell_id
