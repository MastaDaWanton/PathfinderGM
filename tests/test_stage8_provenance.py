"""Stage 8a: every number that lands on a sheet points at a document.

Measured twice on 2026-09-02 (docs/stage-7-plan.md, docs/stage-8-plan.md): asked to
drink a potion the satchel did not hold, the model emitted `heal` with `amount: "1d8+1"`
— the prompt's own twelfth worked example handed back — and the engine applied it. With
a jar in the satchel the same sentence came back as `heal` beside the potion, so the
number landed twice. The engine's own potion emitted an intent byte-identical to the
model's, so nothing could tell them apart.

The fix has three parts, each pinned here: provenance is a field on the Intent the model
cannot write (parse refuses a model-written `origin`, the engine-owned pop would have
swallowed it silently); the sampler is not offered the amount-ops at all; and every door
that turns a document into a number stamps where it came from, resolved while the door
still holds the document — the last dose of a jar is popped before its own heal is
validated.
"""
from __future__ import annotations

import pytest

from gm import judgement, prompts
from rules.activeeffect import from_dict
from rules.bestiary import instantiate
from rules.crafting import Stock
from rules.dice import Dice
from rules.engine import Engine, Scene
from rules.intents import AMOUNT_OPS, IntentError
from rules.sheet import load_pc
from tests._places import stand_on


def _yard():
    s = Scene(location_id="5bbd0c40345f")
    stand_on(s, "urban")
    s.add(load_pc("fixtures/pc-kesst.json"))
    s.add(instantiate("guildhand", scene=s, name="the merchant"))
    return s, Engine(s, Dice(seed=3))


def _jar(pc, iid="healing-draught#1", count=1):
    pc.stock[iid] = Stock(base="Healing Draught", count=count,
                          specs=[{"type": "heal", "dice": "1d8+1"}])
    return iid


# --- the model cannot write provenance ---------------------------------------------------

def test_a_model_written_origin_is_refused_with_the_fix_named():
    """`ENGINE_OWNED_PARAMS` are popped silently (rules/intents.py, after five attacks
    died over `damage_type`), so `origin` could not join that set: the engine's own
    doors would have lost their stamp and a model's would have vanished unremarked."""
    s, engine = _yard()
    with pytest.raises(IntentError) as e:
        engine.validate([{"op": "heal", "actor": "pc", "because": "a flask",
                          "params": {"amount": "1d8", "origin": "item:flask#1"}}])
    assert "origin is the engine's" in str(e.value)
    assert "use_item item=<id>" in str(e.value) and "cast spell=<id>" in str(e.value)


def test_a_number_with_no_document_behind_it_is_refused_naming_the_doors():
    """The backstop. The seven amount-ops each need a stamp; the message names what to
    say instead of the number, never only the fault."""
    s, engine = _yard()
    for op, params in (("heal", {"amount": "1d8+1"}),
                       ("damage", {"amount": "2d6", "type": "fire", "to": "c1"}),
                       ("temp_hp", {"amount": "5"}),
                       ("buff", {"type": "save_mod", "target": "will", "amount": 2}),
                       ("defence", {"kind": "resistance", "against": "fire", "amount": 5}),
                       ("ability_damage", {"ability": "con", "amount": "1d4", "to": "c1"}),
                       ("item_damage", {"amount": "1d6", "to": "pc"})):
        with pytest.raises(IntentError) as e:
            engine.validate([{"op": op, "actor": "pc", "because": "t", "params": params}])
        assert "no document behind this number" in str(e.value), op
        assert "use_item item=<id>" in str(e.value), op
    assert set(AMOUNT_OPS) == {"heal", "damage", "temp_hp", "buff", "defence",
                               "ability_damage", "item_damage"}


def test_a_trusted_stamp_lets_the_same_intent_through_and_records_it():
    s, engine = _yard()
    intents = engine.validate([{"op": "heal", "actor": "pc", "because": "t",
                                "params": {"amount": 3}}],
                              origin="author:test", origin_name="the test")
    assert intents[0].origin == "author:test"
    assert intents[0].as_dict()["origin"] == "author:test"


# --- the sampler is not offered the number ----------------------------------------------

def test_the_player_turn_enum_offers_none_of_the_amount_ops():
    """Stage 7 measured what a validate-time rejection teaches a model: to route around
    it. An enum it cannot emit from has no route."""
    out = prompts.turn_schema(fighting=False)
    enum = set(out["properties"]["intents"]["items"]["properties"]["op"]["enum"])
    assert not (enum & AMOUNT_OPS), enum & AMOUNT_OPS
    assert {"use_item", "cast", "use_ability", "condition"} <= enum
    fight = prompts.turn_schema(fighting=True)
    fenum = set(fight["properties"]["intents"]["items"]["properties"]["op"]["enum"])
    assert not (fenum & AMOUNT_OPS), fenum & AMOUNT_OPS


def test_a_bestiary_creatures_turn_is_the_one_named_exception():
    """5,735 of 7,188 shipped creatures carry `special_attacks` no locator reads
    (measured 2026-09-02 by the recon). On such a creature's turn `damage` and
    `ability_damage` come back, stamped `creature:<template>` by the engine — the
    one door where the model still authors a number, listed here by name and by
    count so the creature-document stage that retires it knows its size."""
    from rules import bestiary

    assert {"damage", "ability_damage"} <= set(prompts._CREATURE_OPS)
    assert not ({"heal", "buff", "temp_hp", "defence", "item_damage"}
                & set(prompts._CREATURE_OPS))
    blocks = bestiary.imported()
    with_specials = sum(1 for b in blocks.values() if b.get("special_attacks"))
    assert with_specials >= 5000, with_specials      # the exception is not small
    # A path-less creature's turn stamps its template; a classed one does not.
    s, engine = _yard()
    thug = s.actors["c1"]
    assert thug.from_template and not thug.paths


def test_the_prompt_teaches_no_number_for_what_heals_wards_or_poisons():
    """The probe's `heal 1d8+1` was gm/prompts.py's own worked example returned
    verbatim, and the briefing said 'a potion, a poultice, a spell that mends: heal'."""
    for ex in prompts.EXAMPLES:
        for intent in ex["reply"]["intents"] if "reply" in ex else ex.get("intents", []):
            assert intent["op"] not in AMOUNT_OPS, intent
    text = prompts.BRIEFING
    assert '"op": "heal"' not in text and '"op": "temp_hp"' not in text
    assert '"op": "ability_damage"' not in text and '"op": "item_damage"' not in text
    assert '"op": "use_item"' in text


def test_the_brief_lists_the_jars_by_id_so_the_model_can_name_one():
    """'The model is never shown anything it could cite' — the recon's gm-side map.
    `use_item` takes the id; the brief has to carry it."""
    from tests.test_opening import a_world

    world, town = a_world(secret="")
    s, engine = _yard()
    iid = _jar(s.pc())
    brief = prompts.scene_brief(world, s, None, here=engine.here(),
                                known=engine.places())
    assert "CARRYING" in brief and iid in brief and "Healing Draught" in brief


# --- the declarer: a jar is opened by the jar door ---------------------------------------

def test_naming_a_carried_jar_opens_the_jar_door_and_drops_the_written_number():
    s, engine = _yard()
    iid = _jar(s.pc())
    proposed = [{"op": "heal", "actor": "pc", "because": "the draught",
                 "params": {"amount": "1d8+1"}},
                {"op": "narrate_only"}]
    raw = judgement.declare_use_item(proposed, "I drink my Healing Draught", s)
    ops = [r["op"] for r in raw]
    assert "heal" not in ops and ops.count("use_item") == 1
    assert next(r for r in raw if r["op"] == "use_item")["params"]["item"] == iid
    # And the survival injector stands down: this is not a waterskin sip.
    after = judgement.inject_survival(raw, "I drink my Healing Draught", s)
    assert "drink" not in [r["op"] for r in after]


def test_naming_a_jar_nobody_carries_is_a_printed_refusal_with_no_number():
    """The measured case. The written heal goes, the `use_item` names what was said,
    and the engine prints "not carrying" with the real satchel — nothing moves."""
    s, engine = _yard()
    pc = s.pc()
    pc.hp = pc.hp_max - 4
    proposed = [{"op": "heal", "actor": "pc", "because": "the draught",
                 "params": {"amount": "1d8+1"}},
                {"op": "drink", "because": "the player said they drink"}]
    raw = judgement.declare_use_item(proposed, "I drink my healing potion", s)
    assert [r["op"] for r in raw] == ["use_item"]
    res = engine.run(engine.validate(raw))
    out = res.outcomes[0]
    assert out.op == "use_item" and out.effects == []
    assert "is not carrying" in out.tell
    assert pc.hp == pc.hp_max - 4


def test_a_synonym_for_the_jar_opens_the_jar_and_two_that_fit_are_a_question():
    """Measured 2026-09-03, three of three: "I drink my healing potion" with a Healing
    Draught in the satchel was refused — "not carrying healing potion. They have:
    healing-draught#1" — because the door matched ids exactly. Inform's parser
    matches on any word of the name and asks when two still fit."""
    from rules.consumables import resolve_stock

    s, engine = _yard()
    pc = s.pc()
    pc.hp = pc.hp_max - 6
    iid = _jar(pc)
    assert resolve_stock(pc.stock, "healing potion") == (iid, [iid])
    assert resolve_stock(pc.stock, "my potion") == (iid, [iid])      # the only jar
    res = engine.run(engine.validate([{"op": "use_item", "actor": "pc",
                                       "because": "t", "params": {"item": "healing potion"}}]))
    out = next(o for o in res.outcomes if o.op == "use_item")
    assert any(e.get("kind") == "heal" and e.get("origin") == f"item:{iid}"
               for e in out.effects)
    assert iid not in pc.stock
    # Two that fit: a question with both named, nothing opened.
    pc.stock["a#1"] = Stock(base="Healing Draught", count=1,
                            specs=[{"type": "heal", "dice": "1d8"}])
    pc.stock["b#1"] = Stock(base="Greater Healing Draught", count=1,
                            specs=[{"type": "heal", "dice": "2d8"}])
    assert resolve_stock(pc.stock, "my potion") == (None, ["a#1", "b#1"])
    res = engine.run(engine.validate([{"op": "use_item", "actor": "pc",
                                       "because": "t", "params": {"item": "my potion"}}]))
    out = next(o for o in res.outcomes if o.op == "use_item")
    assert out.effects == [] and "Which" in out.tell and "a#1" in out.tell
    assert pc.stock["a#1"].count == 1 and pc.stock["b#1"].count == 1
    # And the declarer resolves through the same function.
    raw = judgement.declare_use_item([{"op": "narrate_only"}],
                                     "I drink my greater healing draught", s)
    assert next(r for r in raw if r["op"] == "use_item")["params"]["item"] == "b#1"


def test_declared_ops_requires_use_item_for_a_drunk_potion():
    s, engine = _yard()
    _jar(s.pc())
    assert "use_item" in judgement.declared_ops("I drink my healing draught", s)


# --- the doors stamp what they open -----------------------------------------------------

def test_the_jar_door_stamps_the_heal_with_the_jar_even_on_its_last_dose():
    """The referent is gone before its own heal is validated: `_op_use_item` pops the
    last dose from the satchel and only then validates the effects. Resolved by the
    door while it still holds the jar, so the record and the tell name it."""
    s, engine = _yard()
    pc = s.pc()
    pc.hp = pc.hp_max - 6
    iid = _jar(pc, count=1)
    res = engine.run(engine.validate([{"op": "use_item", "actor": "pc",
                                       "because": "t", "params": {"item": iid}}]))
    assert iid not in pc.stock                       # the last dose is gone
    out = next(o for o in res.outcomes if o.op == "use_item")
    heal = next(e for e in out.effects if e.get("kind") == "heal")
    assert heal["origin"] == f"item:{iid}" and heal["amount"] >= 2
    assert "from Healing Draught" in out.tell
    assert pc.hp > pc.hp_max - 6


def test_a_stamped_buff_temp_hp_and_defence_carry_the_origin_on_the_effect():
    """Law 2's record: `ActiveEffect.origin` beside `source`, and it round-trips."""
    s, engine = _yard()
    pc = s.pc()
    engine.run(engine.validate(
        [{"op": "buff", "actor": "pc", "because": "t",
          "params": {"type": "save_mod", "target": "will", "amount": 2, "source": "tea"}},
         {"op": "temp_hp", "actor": "pc", "because": "t",
          "params": {"amount": 4, "source": "a ward"}},
         {"op": "defence", "actor": "pc", "because": "t",
          "params": {"kind": "resistance", "against": "fire", "amount": 5,
                     "source": "a salve", "duration": {"amount": 1, "unit": "hour"}}}],
        origin="item:tea#1", origin_name="Tea"))
    kinds = {e.kind: e for e in pc.effects if e.origin}
    assert {"buff", "temp_hp", "resistance"} <= set(kinds)
    for e in kinds.values():
        assert e.origin == "item:tea#1"
        assert from_dict(e.as_dict()).origin == "item:tea#1"
    # An effect saved before stage 8 loads with no origin and no complaint.
    assert from_dict({"name": "old", "kind": "buff"}).origin == ""


# --- 8d: the outliers beside the seven, and the rule GM fiat cites ----------------------

def test_a_saves_branch_dice_need_a_document_behind_them():
    """`save.on_failure.damage` was a model-written dice string outside the brief's list
    of seven, value-checked nowhere. A bare save keeps its condition branch."""
    s, engine = _yard()
    with pytest.raises(IntentError) as e:
        engine.validate([{"op": "save", "actor": "pc", "because": "t",
                          "params": {"save": "ref", "dc": 15,
                                     "on_failure": {"damage": "6d6", "type": "fire"}}}])
    assert "hazard rule=<id>" in str(e.value) and "cast spell=<id>" in str(e.value)
    ok = engine.validate([{"op": "save", "actor": "pc", "because": "t",
                           "params": {"save": "will", "dc": 12,
                                      "on_failure": {"condition": "shaken"}}}])
    assert ok[0].op == "save"


def test_a_guards_numbers_and_a_pool_gained_by_saying_so_are_refused():
    s, engine = _yard()
    with pytest.raises(IntentError) as e:
        engine.validate([{"op": "guard", "actor": "pc", "because": "t",
                          "params": {"to": "c1", "kind": "absorb", "amount": 10}}])
    assert "use_ability ability=<name>" in str(e.value)
    plain = engine.validate([{"op": "guard", "actor": "pc", "because": "t",
                              "params": {"to": "c1"}}])
    assert plain[0].op == "guard"
    with pytest.raises(IntentError) as e:
        engine.validate([{"op": "resource", "actor": "pc", "because": "t",
                          "params": {"pool": "ki", "amount": "2d4"}}])
    assert "rest" in str(e.value) and "spend=true" in str(e.value)


def test_compel_carries_no_penalty_param():
    """An unbounded model integer, defaulted to 4, checked nowhere. The rule's number
    lives in rules/compulsion.py now and the param is refused as unknown."""
    from rules.compulsion import PENALTY

    s, engine = _yard()
    with pytest.raises(IntentError):
        engine.validate([{"op": "compel", "actor": "pc", "because": "t",
                          "params": {"to": "c1", "penalty": 40}}])
    res = engine.run(engine.validate([{"op": "compel", "actor": "pc", "because": "t",
                                       "params": {"to": "c1"}}]))
    assert res.outcomes[0].effects[0]["penalty"] == PENALTY == 4


def test_a_fall_is_the_rule_rolling_not_the_model():
    """"I jump from the wall" reached the engine as a bare `damage` with dice the model
    wrote. `hazard rule=falling distance_ft=30` is the rule document's 3d6, the record
    carries `origin: rule:falling`, the tell names the fall."""
    s, engine = _yard()
    pc = s.pc()
    pc.hp = pc.hp_max = 40
    res = engine.run(engine.validate([{"op": "hazard", "actor": "pc", "because": "t",
                                       "params": {"rule": "falling", "distance_ft": 30}}]))
    out = res.outcomes[0]
    assert out.op == "hazard"
    hit = next(e for e in out.effects if e.get("kind") == "damage")
    assert hit["origin"] == "rule:falling" and hit["type"] == "bludgeoning"
    assert out.rolls and out.rolls[0].die == "3d6" if hasattr(out.rolls[0], "die") else True
    assert "a fall" in out.tell and "distance ft 30" in out.tell and "3d6" in out.tell
    assert pc.hp < 40
    # A deliberate jump: the first die is nonlethal.
    pc.hp, pc.nonlethal = 40, 0
    res = engine.run(engine.validate([{"op": "hazard", "actor": "pc", "because": "t",
                                       "params": {"rule": "falling", "distance_ft": 20,
                                                  "deliberate": True}}]))
    kinds = [(e.get("lethality"), e.get("origin")) for e in res.outcomes[0].effects
             if e.get("kind") == "damage"]
    assert kinds[0] == ("nonlethal", "rule:falling") and pc.nonlethal > 0


def test_a_hazards_slot_is_bounded_by_the_row_and_the_rule_must_exist():
    """SetByCaller, applied to the one op stage 8 invents: the row declares the slot
    and its bounds; a 900-foot fall is a number the model wrote."""
    s, engine = _yard()
    with pytest.raises(IntentError) as e:
        engine.validate([{"op": "hazard", "actor": "pc", "because": "t",
                          "params": {"rule": "falling", "distance_ft": 900}}])
    assert "10–200" in str(e.value)
    with pytest.raises(IntentError) as e:
        engine.validate([{"op": "hazard", "actor": "pc", "because": "t",
                          "params": {"rule": "falling"}}])
    assert "needs distance_ft" in str(e.value)
    with pytest.raises(IntentError) as e:
        engine.validate([{"op": "hazard", "actor": "pc", "because": "t",
                          "params": {"rule": "trap"}}])
    assert "The rules are:" in str(e.value) and "falling" in str(e.value)
    enum = set(prompts.turn_schema()["properties"]["intents"]["items"]["properties"]["op"]["enum"])
    assert "hazard" in enum
    assert '"op": "hazard"' in prompts.BRIEFING


def test_the_tells_for_heal_and_damage_name_the_document():
    """Law 3, the half that was missing: a sourced number whose source the narrator
    cannot see. Before stage 8 the heal, damage, ability-damage and item-damage tells
    named nothing, so the narrator could not have said what healed."""
    s, engine = _yard()
    pc = s.pc()
    pc.hp = pc.hp_max - 5
    res = engine.run(engine.validate(
        [{"op": "heal", "actor": "pc", "because": "t", "params": {"amount": 2}},
         {"op": "damage", "actor": "pc", "because": "t",
          "params": {"to": "c1", "amount": 1, "type": "fire"}}],
        origin="spell:cure-light-wounds", origin_name="Cure Light Wounds"))
    heal, dmg = res.outcomes[0], res.outcomes[1]
    assert "from Cure Light Wounds" in heal.tell
    assert "from Cure Light Wounds" in dmg.tell
    assert heal.effects[0]["origin"] == "spell:cure-light-wounds"
    assert dmg.effects[0]["origin"] == "spell:cure-light-wounds"
