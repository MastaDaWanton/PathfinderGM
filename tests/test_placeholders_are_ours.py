"""`new1` is ours: a placeholder never becomes a name, and a dangling one makes nobody.

Measured live 2026-09-27 (`narrator_audit.py --script fight --turns 12`, gemma-4-12B, on
twin-names): turn 2, "I punch him in the face", came back from the planner as
`attack pc -> new1` with no `introduce` in the plan. `new1` is the local id `introduce`
hands out (rules.intents.INTRODUCED_REFS). The ref check refused it, the invented-ref
repair stripped the digit, and a 13-hp thug called **new** was spawned for the punch to
land on — "Battle is joined: Kesst Vayr squares off against new" — beside Borin Lyraxys,
the one man in the tavern, whom the player had actually punched and whom `inject_fight`
had also, correctly, put a second attack on. The wrong-actor check then logged "it was
new's turn, and the beat never names new". Turn 1 had already written `say to new1` about
the same man. Both times the placeholder meant somebody already standing there.

The same line turned `npc1` into somebody called "npc", `enemy1` into "enemy" and
`target1` into "target".

Both turns are kept in tests/replay/plans/ and replayed here through the real
`plan_turn`, with the model's recorded replies standing in for the model.
"""
from __future__ import annotations

import pytest

from gm import judgement
from rules.bestiary import instantiate
from rules.dice import Dice
from rules.engine import Engine, Scene
from rules.intents import IntentError
from rules.sheet import load_pc
from tests._replay import recorded, replay_plan

RECORDED = "2026-09-27-fight-new1-gemma4-12b.jsonl.gz"


def _scene(*names):
    s = Scene(location_id="5bbd0c40345f")
    s.add(load_pc("fixtures/pc-kesst.json"))
    for name in names:
        s.add(instantiate("thug", scene=s, name=name))
    return s


# --- the name --------------------------------------------------------------------------

@pytest.mark.parametrize("label", ["npc1", "enemy1", "target1", "enemy_2", "foe1"])
def test_a_label_is_never_the_name_of_whoever_is_made(label):
    """`npc1` spawned somebody called "npc" (2026-09-27), then a nameless thug once the
    label check landed. Since 2026-10-09 the refs repair makes nobody at all — the misaim
    repair's twin made a thug called "top of his skull" on 2026-10-08 — so a label is
    neither a name nor a body: validation's refusal names the refs that exist."""
    assert judgement.repair_unknown_refs(
        [{"op": "attack", "actor": label, "target": "pc"}],
        "Somebody comes at me out of the alley.", _scene()) is None


def test_a_ref_that_describes_somebody_still_names_them():
    """The GM's `winged_woman` was made a thug called "winged woman" here until
    2026-10-09. The owner's ruling: nobody is minted from words. A winged woman the
    narration showed is the beat reader's newcomer, a full actor whose ref the plan's
    enum offers; a ref nobody holds is refused with the real refs named."""
    assert judgement.repair_unknown_refs(
        [{"op": "attack", "actor": "winged_woman", "target": "pc"}],
        "Somebody drops out of the sky at me.", _scene()) is None


def test_a_placeholder_is_never_spawned_at_all():
    """`new1` is not somebody the GM described; it is our id with nothing behind it.
    The repair declines, and validation's refusal carries the fix."""
    raw = [{"op": "attack", "actor": "pc", "target": "new1"}]
    assert judgement.repair_unknown_refs(raw, "Somebody comes at me.", _scene()) is None


# --- what it binds to -----------------------------------------------------------------

def test_the_punch_lands_on_the_man_in_the_room():
    """Turn 2's plan, bound before validation: the one man present is who "him" means."""
    scene = _scene("Borin Lyraxys")
    raw = [{"op": "attack", "actor": "pc", "target": "new1",
            "params": {"weapon": "unarmed"}}]
    out = judgement.bind_placeholders(raw, "I punch him in the face.", scene)
    assert out[0]["target"] == "c1"


def test_say_to_new1_reaches_him_too():
    """Turn 1's plan wrote the placeholder into `say`'s `to`, a pocket the ref swap did
    not reach."""
    scene = _scene("Borin Lyraxys")
    raw = [{"op": "say", "actor": "pc", "params": {"words": "Enough.", "to": "new1"}}]
    out = judgement.bind_placeholders(raw, "I pick a fight with the biggest man here.",
                                      scene)
    assert out[0]["params"]["to"] == "c1"


def test_two_people_and_a_pronoun_is_not_a_choice_made_for_the_player():
    scene = _scene("Borin Lyraxys", "Hesk")
    raw = [{"op": "attack", "actor": "pc", "target": "new1"}]
    assert judgement.bind_placeholders(raw, "I punch him.", scene) == raw


def test_the_player_naming_one_of_two_decides_it():
    scene = _scene("Borin Lyraxys", "Hesk")
    raw = [{"op": "attack", "actor": "pc", "target": "enemy1"}]
    out = judgement.bind_placeholders(raw, "I punch Hesk in the jaw.", scene)
    assert out[0]["target"] == "c2"


def test_somebody_arriving_is_not_bound_to_the_man_already_there():
    """The case the invented-ref repair exists for: the player describes an arrival and
    the GM names the newcomer with a label. "Him" is the newcomer, so the label is left
    for the plan to fix — never turned into the man at the bar, and (since 2026-10-09)
    never made by the refs repair either: nobody is minted from words."""
    scene = _scene("Borin Lyraxys")
    raw = [{"op": "attack", "actor": "pc", "target": "enemy1"}]
    text = "A second man bursts in through the door and I hit him."
    assert judgement.bind_placeholders(raw, text, scene) == raw
    assert judgement.repair_unknown_refs(raw, text, scene) is None


def test_a_placeholder_written_for_a_spawn_is_that_spawn():
    """The placeholder of the wrong op: the plan declared the body with `spawn` and
    addressed it as introduce's `new1`. Declared, just misnamed — so it is the ref the
    spawn will mint, never the man already there."""
    scene = _scene("Borin Lyraxys")
    raw = [{"op": "spawn", "params": {"template": "thug", "count": 1}},
           {"op": "attack", "actor": "pc", "target": "new1"}]
    out = judgement.bind_placeholders(raw, "I punch the newcomer.", scene)
    assert out[1]["target"] == "c2"


def test_an_introduced_placeholder_is_left_alone():
    scene = _scene("Borin Lyraxys")
    raw = [{"op": "introduce", "params": {"who": "a ferryman"}},
           {"op": "say", "actor": "pc", "params": {"words": "Hello.", "to": "new1"}}]
    assert judgement.bind_placeholders(raw, "I hail the ferryman.", scene) == raw


# --- the refusal ----------------------------------------------------------------------

def test_a_dangling_placeholder_is_refused_with_the_fix_named():
    """Before, the refusal was the generic "unknown target 'new1'; known refs are [...]"
    plus the spawn hint — which read as an invitation to spawn somebody."""
    scene = _scene("Borin Lyraxys")
    engine = Engine(scene, Dice(seed=1))
    with pytest.raises(IntentError) as err:
        engine.validate([{"op": "attack", "actor": "pc", "target": "new1"}])
    msg = str(err.value)
    assert "placeholder introduce hands out" in msg
    assert "c1 (Borin Lyraxys)" in msg and "introduce written before it" in msg
    with pytest.raises(IntentError) as err:
        engine.validate([{"op": "say", "actor": "pc",
                          "params": {"words": "Hi.", "to": "new2"}}])
    assert "placeholder introduce hands out" in str(err.value)


# --- the recorded turns, through the real planner ---------------------------------------

def test_the_recorded_punch_makes_nobody_called_new(tmp_path, monkeypatch):
    """Turn 2 as the model wrote it. Before: a spawn of "new" (c3), an attack on c3, and
    `inject_fight`'s second attack on c2. After: one attack, on Borin Lyraxys."""
    rec = recorded(RECORDED)[1]
    assert rec["player"] == "I punch him in the face."
    assert '"target": "new1"' in rec["calls"][1]["raw"]
    plan, scene = replay_plan(rec, tmp_path, monkeypatch)

    ops = [(i.op, i.actor, i.target) for i in plan.intents]
    assert all(op != "spawn" for op, _, _ in ops), ops
    attacks = [t for op, _, t in ops if op == "attack"]
    assert attacks == ["c2"], ops
    # The barkeep, by the name the world holds for them; on the panel they are "the one
    # behind the bar" until they give it (owner ruling F1, 2026-09-30).
    assert scene.actors["c2"].true_name == "Borin Lyraxys"
    assert not any("repaired" in r for r in plan.rejections), plan.rejections
