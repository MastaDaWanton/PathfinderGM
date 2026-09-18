"""Things and their owners: every object the fiction touches has a record.

The 2026-09-18 play-test, item 15 and item 22's payment (docs/playtest-2026-09-18.md):
a sundered club became "a chunk of wood" the player picked up, then "the smoldering wood
of the table still glowing faintly where his final strike landed" two beats later —
fire from nothing, a table from nothing, because nothing grounded THINGS the way the cast
ledger grounds people. Ownership existed only by containment: an `Item` inside an actor's
gear, nothing about whose it was or what it had been, and nothing at all off a person.
"I pay her ten gold" reached the engine as `sell gold_coins_10` and was refused while the
prose took the coin. "i pick up a chunk of wood and throw it at the man" became a `give`
and a `cast`. And the goods held "scene on" ×3 from the Continue directive.

Prior art the design follows: Creation Kit keeps an owner (NPC or faction) on every
placed object beside the stolen flag; Inform keeps one containment tree, and a dropped
thing lands on the room's floor; Dwarf Fortress tracks claims on items. So: one record
per thing with exactly one of `held_by` / `at`, plus `owner`, `from_`, `state`.
"""
from __future__ import annotations

import pytest

from gm import judgement, narration
from rules.bestiary import instantiate
from rules.dice import Dice
from rules.engine import Engine, Scene
from rules.sheet import load_pc


@pytest.fixture
def ring():
    s = Scene(location_id="5bbd0c40345f")
    s.add(load_pc("fixtures/pc-kesst.json"))
    s.add(instantiate("guildhand", scene=s, name="the challenger"))
    return s


def _sunder_until_destroyed(engine, scene, attacker_ref, defender_ref) -> tuple:
    for seed in range(1, 60):
        engine.dice = Dice(seed=seed)
        res = engine.run(engine.validate([{"op": "attack", "actor": attacker_ref,
                                           "target": defender_ref,
                                           "params": {"manoeuvre": "sunder"}}]))
        out = res.outcomes[0]
        if any(e.get("kind") == "item_damage" and e.get("destroyed") for e in out.effects):
            return out, seed
    raise AssertionError("no seed destroyed the item in sixty tries")


# --- 15: the sunder leaves fragments, whose they are and what they were ----------------------

def test_a_destroyed_weapon_leaves_fragments_at_the_spot_owned_by_its_wielder(ring):
    """A thug's sap against a guildhand's wooden club (hardness 5, 10 hp): hidden dice
    on both sides, so the whole thing resolves; the item's hit points persist across
    swings, so a seed loop reaches destruction."""
    challenger = next(a for a in ring.actors.values() if a.name == "the challenger")
    thug = instantiate("thug", scene=ring, name="the thug")
    ring.add(thug)
    engine = Engine(ring, Dice(seed=1))
    engine.run(engine.validate([{"op": "begin_encounter",
                                 "params": {"sides": {"pc": ["pc", thug.ref],
                                                      "them": [challenger.ref]}}}]))
    out, _ = _sunder_until_destroyed(engine, ring, thug.ref, challenger.ref)
    lying = ring.props_here()
    assert len(lying) == 1
    rec = lying[0]
    assert rec["name"] == "fragments of the challenger's club"
    assert rec["owner"] == challenger.ref and rec["from_"] == "club"
    assert rec["state"] == "fragments" and rec["material"] == "wood"
    assert rec["at"] == ring.at
    assert challenger.equipped == "unarmed", "the hand empties"


def test_picking_up_a_chunk_of_wood_finds_the_fragments_and_keeps_their_provenance(ring):
    pc = ring.pc()
    challenger = next(a for a in ring.actors.values() if a.name == "the challenger")
    ring.place_prop("fragments of the challenger's club", owner=challenger.ref,
                    from_="club", state="fragments")
    ring.prop_named("fragments of the challenger's club")["material"] = "wood"
    engine = Engine(ring, Dice(seed=1))
    res = engine.run(engine.validate([{"op": "give",
                                       "params": {"item": "chunk of wood", "to": "pc"}}]))
    tell = res.outcomes[0].tell
    assert "fragments of the challenger's club" in tell
    assert "the challenger's, not Kesst Vayr's" in tell
    rec = ring.prop_named("fragments of the challenger's club")
    assert rec["held_by"] == "pc" and "at" not in rec
    assert rec["owner"] == challenger.ref and rec["from_"] == "club"
    assert not ring.props_here(), "nothing lies here now"
    assert "fragments of the challenger's club" in pc.goods
    # A thing nobody made real is still taken from the world, as before.
    res = engine.run(engine.validate([{"op": "give", "params": {"item": "pebble", "to": "pc"}}]))
    assert "pebble" in pc.goods and ring.prop_named("pebble") is None


def test_dropping_a_thing_lays_it_here_with_its_record(ring):
    pc = ring.pc()
    pc.goods["lantern"] = 1
    engine = Engine(ring, Dice(seed=1))
    res = engine.run(engine.validate([{"op": "give",
                                       "params": {"item": "lantern", "from_": "pc"}}]))
    assert "sets down lantern; it lies here" in res.outcomes[0].tell
    assert ring.props_here()[0]["name"] == "lantern"
    assert ring.props_here()[0]["owner"] == "pc"
    assert "lantern" not in pc.goods


def test_the_brief_and_the_scene_block_say_what_lies_here_and_what_is_carried(ring):
    from gm import prompts

    challenger = next(a for a in ring.actors.values() if a.name == "the challenger")
    ring.place_prop("fragments of the challenger's club", owner=challenger.ref,
                    from_="club", state="fragments")
    now = prompts.scene_now(ring)
    assert "lying on the ground here" in now
    assert "fragments of the challenger's club (the challenger's)" in now
    pc = ring.pc()
    pc.purse["gp"] = 231
    ring.hold_prop("pebble", "pc")
    pc.goods["pebble"] = 1
    from play import campaign as cm

    world = cm.load_cached(cm._resolve_world_source("fixtures/aurvantis-campaign.json"))
    brief = prompts.scene_brief(world, ring, None, [])
    assert "HAS (fact): purse" in brief and "231" in brief and "pebble" in brief
    assert "Coin leaves the purse only through a give" in brief


def test_props_survive_the_save():
    """The save writes the ledger and the load reads it back — a field added to `Scene`
    and forgotten in `campaign.py` is a ledger that empties on every restart (the
    `spawn_feet` lesson recorded there)."""
    import inspect

    from play import campaign as cm

    assert '"props": [dict(e) for e in self.scene.props]' in inspect.getsource(cm.Campaign.save)
    assert 'props=[dict(e) for e in (s.get("props") or [])]' in inspect.getsource(cm.Campaign.load)


# --- A thing swung or thrown is an improvised-weapon attack ---------------------------------

def test_throwing_a_thing_is_an_improvised_attack_that_names_it_and_leaves_it_where_it_fell(ring):
    pc = ring.pc()
    challenger = next(a for a in ring.actors.values() if a.name == "the challenger")
    ring.place_prop("fragments of the challenger's club", owner=challenger.ref,
                    from_="club", state="fragments")
    ring.prop_named("fragments of the challenger's club")["material"] = "wood"
    judgement.update_thread(ring, "I wait for a challenger")
    judgement.bind_thread(ring, [challenger.ref])
    raw = judgement.inject_improvised(
        [{"op": "cast", "params": {"spell": "fireball"}},
         {"op": "narrate_only", "params": {}}],
        "i pick up a chunk of wood and throw it at the man", ring)
    ops = [r["op"] for r in raw]
    assert "cast" not in ops, "the throw dressed as a spell is the throw"
    give = next(r for r in raw if r["op"] == "give")
    assert give["params"]["item"] == "fragments of the challenger's club"
    attack = next(r for r in raw if r["op"] == "attack")
    assert attack["target"] == challenger.ref
    assert attack["params"] == {"weapon": "improvised", "thrown": True,
                                "item": "fragments of the challenger's club"}

    engine = Engine(ring, Dice(seed=3))
    engine.run(engine.validate([{"op": "begin_encounter",
                                 "params": {"sides": {"pc": ["pc"], "them": [challenger.ref]}}}]))
    res = engine.run(engine.validate(raw))
    # The pick-up happened; the swing asks for the player's die, at -4.
    assert ring.awaiting and "Attack" in ring.awaiting["label"]
    assert any(m["source"].startswith("non") or m["value"] == -4
               for m in ring.awaiting["breakdown"]), ring.awaiting["breakdown"]
    engine.resume(20)
    for _ in range(4):                    # confirm, damage — whatever the die asks
        if ring.awaiting:
            engine.resume(3)
    # Out of the hand and on the ground here, still the challenger's, still a club's.
    rec = ring.prop_named("fragments of the challenger's club")
    assert rec.get("at") == ring.at and "held_by" not in rec
    assert rec["owner"] == challenger.ref and rec["from_"] == "club"
    assert "fragments of the challenger's club" not in pc.goods


def test_swinging_a_carried_thing_keeps_it_in_hand(ring):
    pc = ring.pc()
    pc.goods["chair leg"] = 1
    challenger = next(a for a in ring.actors.values() if a.name == "the challenger")
    raw = judgement.inject_improvised(
        [{"op": "attack", "actor": "pc", "target": challenger.ref, "params": {}}],
        "I hit him with the chair leg", ring)
    assert raw[0]["params"] == {"weapon": "improvised", "item": "chair leg"}
    # A real weapon thrown is that weapon's own attack, not an improvised one.
    raw = [{"op": "attack", "actor": "pc", "target": challenger.ref, "params": {}}]
    assert judgement.inject_improvised(raw, "I throw my dagger at him", ring) is raw


# --- 22: coin leaves the purse by amount ------------------------------------------------------

def test_paying_in_coin_is_a_give_of_the_denomination_to_the_person_paid(ring):
    pc = ring.pc()
    pc.purse["gp"] = 231
    woman = instantiate("guildhand", scene=ring, name="the woman")
    ring.add(woman)
    raw = judgement.inject_payment(
        [{"op": "sell", "actor": "pc", "params": {"item": "gold_coins_10", "count": 10,
                                                  "to": woman.ref}}],
        "I pay the woman ten gold for the night", ring)
    assert [r["op"] for r in raw] == ["give"]
    assert raw[0]["params"] == {"item": "gp", "count": 10, "from_": "pc", "to": woman.ref}
    engine = Engine(ring, Dice(seed=1))
    res = engine.run(engine.validate(raw))
    assert pc.purse["gp"] == 221 and woman.purse.get("gp") == 10
    assert "hands the woman 10 × gp" in res.outcomes[0].tell
    # Said in words, with nobody named: the one other person here is paid.
    raw = judgement.inject_payment([{"op": "narrate_only", "params": {}}],
                                   "I toss her five silver", ring)
    assert raw[-1]["params"] == {"item": "sp", "count": 5, "from_": "pc", "to": woman.ref} \
        or raw[-1]["params"]["item"] == "sp"


def test_words_for_what_is_happening_are_not_things(ring):
    from gm import prompts

    raw = judgement.inject_goods([{"op": "narrate_only", "params": {}}], prompts.CARRY_ON, ring)
    assert [r["op"] for r in raw] == ["narrate_only"], "the Continue directive buys nothing"
    assert not judgement._is_a_thing("scene on")
    assert not judgement._is_a_thing("satisfaction")
    assert judgement._is_a_thing("chunk of wood")


# --- Fire from nowhere ----------------------------------------------------------------------------

def test_fire_with_nothing_to_light_it_is_cut_and_a_forge_grounds_it():
    beat = ("You pick up the chunk of wood. The wood is still smoldering from the impact, "
            "glowing faintly where his strike landed. He staggers back. What do you do?")
    lit = narration.fire_from_nowhere(beat, context="the market, coral and driftwood stalls")
    assert lit == ["The wood is still smoldering from the impact, glowing faintly where "
                   "his strike landed."]
    fixed, cut = narration.cut_fire_from_nowhere(beat, "the market")
    assert "smoldering" not in fixed and "He staggers back." in fixed
    assert narration.fire_from_nowhere(beat, context="near the smithy's forge") == []
    # A source the beat itself establishes first grounds what follows it.
    torch = "A torch guts in its bracket. The rag catches fire and curls."
    assert narration.fire_from_nowhere(torch, "") == []
    assert narration.review(beat, fire_context="the market").findings[0].kind == "fire-from-nowhere"
    assert narration.review(beat).findings == [] or all(
        f.kind != "fire-from-nowhere" for f in narration.review(beat).findings)
