"""Whatever door moves the clock, what the stretch ended is told — once, as a sentence.

Law 3: every effect's expiry emits a tell, and the narrator is fed tells. `Scene.advance`
is the one ticker and always expired timed effects; what it returned (`ended`) was told by
two of its two dozen callers — `advance_time` and `rest` — and dropped by the rest: a
journey, a forage, a repair, taking armour off, a bench's hours. And where it WAS told it
was a fragment, "Ended: Kesst Vayr: Prohibited metal.", which a narrator can read as a
state being imposed rather than lifted.

Measured live 2026-10-08 on scratch data (a 20-hour `rule:prohibited-metal` effect on the
player, "We wait here a full day.", the real local model): the plan was `advance_time` 1
day, the tell was "1 day pass. Ended: Kesst Vayr: Prohibited metal.", and the prose wrote
"your presence here is now marked by the restriction of your steel". The leatherworking
metal-readers lane saw the same turn end "has not lifted".

Now `advance` queues `_ward_tell` records (`Scene._ended_said`) and `Engine._ended_settles`
tells them behind the op whose hours they were, in the round tick's own sentences.
"""
from __future__ import annotations

from rules.activeeffect import ActiveEffect
from rules.dice import Dice
from rules.engine import Engine, Scene
from rules.sheet import from_dict, load_pc

DAY_ROUNDS = 24 * 600


def _engine():
    scene = Scene(location_id="5bbd0c40345f")
    pc = scene.add(load_pc("fixtures/pc-kesst.json"))
    # The wait would otherwise eat and drink from the pack and roll thirst; this measures
    # the expiry alone.
    for need in ("needs.no_sleep", "needs.no_food", "needs.no_water"):
        pc.overrides[need] = True
    return Engine(scene, Dice(seed=3)), pc


def _prohibition(rounds):
    return ActiveEffect(name="Prohibited metal", kind="rule", key="prohibited",
                        source="class:druid", origin="rule:prohibited-metal",
                        duration="rounds", rounds_left=rounds)


def _run(engine, ops):
    res = engine.run(engine.validate(ops))
    while res.awaiting:
        res = engine.resume(int(res.awaiting["max"]))
    return res.outcomes


def _tells(outcomes):
    return [o.tell for o in outcomes if o.tell]


def test_a_days_wait_tells_the_prohibition_lifting_as_a_sentence():
    """The live turn's tell was "1 day pass. Ended: Kesst Vayr: Prohibited metal." and the
    prose made the restriction stand. Now the expiry is its own sentence saying what
    happened to whom, and the fragment is gone."""
    engine, pc = _engine()
    pc.apply_effect(_prohibition(20 * 600))
    tells = _tells(_run(engine, [{"op": "advance_time", "actor": "pc",
                                  "params": {"amount": 1, "unit": "day"}}]))
    assert not any(e.origin == "rule:prohibited-metal" for e in pc.effects)
    assert "Prohibited metal wears off Kesst Vayr." in tells, tells
    assert not any("Ended:" in t for t in tells), tells
    # The same live tell said "1 day pass."; the hour it ends at stays (`_hour_now`).
    assert any(t.startswith("1 day passes: ") for t in tells), tells


def test_one_round_passes():
    """A one-round wait read "1 round pass." — a singular count with a plural verb."""
    engine, pc = _engine()
    tells = _tells(_run(engine, [{"op": "advance_time", "actor": "pc",
                                  "params": {"amount": 1, "unit": "round"}}]))
    assert "1 round passes." in tells, tells


def test_an_expiry_is_told_once():
    """`advance_time` said its `ended` list in its own sentence; the settle behind every
    op must not say it a second time."""
    engine, pc = _engine()
    pc.apply_effect(_prohibition(600))
    tells = _tells(_run(engine, [{"op": "rest", "actor": "pc",
                                  "params": {"kind": "night"}}]))
    assert sum("Prohibited metal" in t for t in tells) == 1, tells


def test_a_door_that_dropped_its_expiries_now_tells_them():
    """Taking armour off spends Table 6-8's minutes through `Scene.advance`, which expired
    a five-round effect and threw the list away: no outcome of the batch mentioned it.
    The druid's own door — the one their prohibition starts lapsing from."""
    engine, pc = _engine()
    assert pc.armour, "the fixture wears armour"
    pc.apply_effect(ActiveEffect(name="Shield of faith", kind="buff",
                                 source="spell:shield-of-faith",
                                 origin="spell:shield-of-faith", duration="rounds",
                                 rounds_left=5,
                                 modifiers=[{"target": "ac", "type": "deflection",
                                             "amount": 2}]))
    outcomes = _run(engine, [{"op": "take_off", "actor": "pc",
                              "params": {"item": "armour"}}])
    assert not any(e.name == "Shield of faith" for e in pc.effects)
    told = [o for o in outcomes if any(f.get("kind") == "effect_ended"
                                       for f in (o.effects or []))]
    assert told and "wears off Kesst Vayr" in told[0].tell, _tells(outcomes)
    assert told[0].effects[0]["origin"] == "spell:shield-of-faith"


def test_a_clock_moved_outside_a_batch_is_told_by_the_next_one():
    """A bench or a forge view moves the clock with no batch around it. What it ended
    waits on the scene and the next turn's batch tells it — late, never lost
    (`take_body_said`'s rule)."""
    engine, pc = _engine()
    pc.apply_effect(_prohibition(600))
    engine.scene.advance(120)                       # the bench's hours, no batch
    tells = _tells(_run(engine, [{"op": "narrate_only", "actor": "pc"}]))
    assert "Prohibited metal wears off Kesst Vayr." in tells, tells


def test_somebody_elsewhere_is_not_handed_to_the_narrator():
    """The clock runs for everyone the campaign holds. A narrator told that a buff wore
    off a merchant in another street has been handed somebody to put in the room."""
    engine, pc = _engine()
    far = from_dict({"name": "Gorm the chandler", "kind": "npc", "hp": 8, "hp_max": 8,
                     "level": 1, "abilities": {k: 10 for k in
                                               ("str", "dex", "con", "int", "wis", "cha")}},
                    ref="c9")
    engine.scene.add(far)
    engine.scene.move("c9", "elsewhere")
    assert "c9" not in engine.scene.actors
    far.apply_effect(_prohibition(600))
    tells = _tells(_run(engine, [{"op": "advance_time", "actor": "pc",
                                  "params": {"amount": 2, "unit": "hour"}}]))
    assert not far.effects, "the clock still ran for him"
    assert not any("Gorm" in t for t in tells), tells
