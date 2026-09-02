"""Stage 7 — refusals are prose, never a spiral.

`docs/stage-7-plan.md` is the record. The measurement that drives all of it: a raise at
RESOLUTION time is caught once by `play/views._advance`, answered as HTTP 502 with the raw
engine string, and the player's own sentence is popped from the transcript. There is no
retry — these fire during `run()`, after `validate()` has passed, so the five-attempt
schedule never sees them. Inform's `check` rulebook is the model the traditions converge
on: an action that cannot happen prints why and stops, and the story never errors.

The plan classified twenty-two resolution raises as "correct — the model can name
another item". That is true at validate time and false at resolution, where nobody is
listening. So every resolution-time refusal now prints, and the cheap checks are also
made at validate, where the model does get its retry.
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

from rules.bestiary import instantiate
from rules.dice import Dice
from rules.engine import Engine, Scene
from rules.intents import IntentError
from rules.sheet import load_pc
from tests._places import stand_on


def _yard():
    s = Scene(location_id="5bbd0c40345f")
    stand_on(s, "urban")
    s.add(load_pc("fixtures/pc-kesst.json"))
    s.add(instantiate("guildhand", scene=s, name="the merchant"))
    return s, Engine(s, Dice(seed=7))


def _run(engine, raw):
    return engine.run(engine.validate([raw])).outcomes[0]


# --- 7b: the four the plan named ------------------------------------------------------

def test_an_empty_or_unknown_pool_is_two_sentences_and_neither_is_an_error():
    """The contract's own worked example, unimplemented for a year: what the app
    printed was `resource: no fury to spend.` as a 502 — the identical sentence whether
    the pool was empty or had never existed."""
    from rules.intents import parse_all

    s, engine = _yard()
    fury = {"op": "resource", "actor": "pc", "because": "t",
            "params": {"pool": "fury", "spend": True, "amount": 1}}
    # Validate says it first, with the pools listed, so the model can name one.
    with pytest.raises(IntentError) as e:
        engine.validate([fury])
    assert "no pool called 'fury'" in str(e.value) and "Their pools are" in str(e.value)
    # And the resolver prints the same when a list reaches it anyway.
    out = engine.run(parse_all([fury])).outcomes[0]
    assert out.effects == [] and "No pool called 'fury'" in out.tell

    s.pc().gain_pool("rage", 2, source="t")
    spend = {"op": "resource", "actor": "pc", "because": "t",
             "params": {"pool": "rage", "spend": True, "amount": 2}}
    _run(engine, spend)
    # Empty is a fact about the sheet the player could not know: printed, not
    # rejected — a rejection would only invite the model to route around it.
    out = _run(engine, dict(spend, params={"pool": "rage", "spend": True, "amount": 1}))
    assert out.effects == [] and "0 left" in out.tell
    assert "No pool called" not in out.tell
    # The mid-list shape: two spends of the same pool in one list each pass validation
    # against the pool as it stands, and the second prints at resolution — distinctly
    # from the pool never having existed.
    s.pc().gain_pool("rage", 2, source="t")
    res = engine.run(engine.validate([
        spend, dict(spend, params={"pool": "rage", "spend": True, "amount": 1})]))
    last = res.outcomes[-1]
    assert last.effects == [] and "cannot spend 1 rage" in last.tell
    assert "No pool called" not in last.tell, "empty and non-existent read the same"


def test_running_out_of_slots_mid_list_keeps_what_was_cast():
    """Measured: six casts in one list PASS validation against two prepared slots,
    because `_check_cast` reads the count before anything runs. The third raised after
    two slots were gone and two fireballs had landed, and the 502 threw all of it
    away. Validate is deliberately not taught to simulate the list."""
    from tests.test_casting_executes import table, wizard

    # A first-level wizard has two first-level slots (one, plus one for Int 18). Six
    # casts in one list pass validation; the third and after print.
    s, engine = table(wizard(level=1, book=("magic-missile",),
                             prepared={"magic-missile": 6}))
    raws = [{"op": "cast", "actor": "pc", "because": "t",
             "params": {"spell": "magic-missile", "at": "c1"}}] * 6
    res = engine.run(engine.validate(raws))
    outcomes = res.outcomes
    assert len(outcomes) == 6, [o.tell for o in outcomes]
    landed = [o for o in outcomes if o.effects]
    refused = [o for o in outcomes if not o.effects]
    assert landed and refused, [o.tell for o in outcomes]
    assert outcomes[:len(landed)] == landed, "a refusal came before a casting that worked"
    assert all("has no" in o.tell and "stands" in o.tell for o in refused), \
        [o.tell for o in refused]


def test_a_thing_not_on_the_counter_today_is_printed_with_the_counter():
    """What is on a counter TODAY is a fact only the engine holds — a seeded shelf keyed
    on the day — so neither the player nor the model could have known."""
    from rules.intents import parse_all

    s, engine = _yard()
    raw = {"op": "buy", "actor": "pc", "because": "t",
           "params": {"item": "moon rock", "from_": "c1"}}
    out = engine.run(engine.validate([raw])).outcomes[0]
    assert out.effects == []
    assert "no moon rock on the counter today" in out.tell and "On the counter:" in out.tell


def test_a_body_that_left_between_validate_and_run_is_printed_not_raised():
    """The fourth: validated a moment ago, gone now. Under containment the body may be
    in the room the party just left, and the refusal says where."""
    s, engine = _yard()
    s.people["c1"].hp = -20
    s.people["c1"].apply_hp_state()
    other = next(p for p in engine.places() if p.id != s.at)
    res = engine.run(engine.validate([
        {"op": "travel", "because": "t", "params": {"place": other.name}},
        {"op": "loot", "actor": "pc", "because": "t", "params": {"from_": "c1"}}]))
    out = res.outcomes[-1]
    assert out.op == "loot" and out.effects == []
    assert "c1" in out.tell and "not here" in out.tell


# --- the ones the plan called "correct to raise", at the door where nobody listens ----

def test_drinking_a_potion_you_do_not_have_is_a_sentence_not_a_502():
    """"I drink my healing potion" with none was the commonest 502 in play, and it
    deleted the player's own line."""
    s, engine = _yard()
    raw = {"op": "use_item", "actor": "pc", "because": "t",
           "params": {"item": "potion of cure light wounds"}}
    # Not rejected at validate: what the satchel holds is a fact about the world, and
    # a live probe showed a validate-time rejection of it only taught the model to
    # emit a bare `heal` and narrate a vial that did not exist. Printed, with the
    # satchel listed, so the player reads the truth.
    out = engine.run(engine.validate([raw])).outcomes[0]
    assert out.effects == [] and "is not carrying" in out.tell and "They have:" in out.tell


def test_an_unknown_ability_names_the_abilities_not_the_paths():
    """`use_ability: … Their paths are none.` named the paths when the names were the
    whole point, and the brief already computed the right list six hundred lines away.
    One helper now, two readers."""
    from rules import leveling

    s, engine = _yard()
    # Printed, not rejected: the name is usually the player's, and the model cannot
    # fix what the player asked for — its answer to being asked to, measured live,
    # was an attack.
    out = _run(engine, {"op": "use_ability", "actor": "pc", "because": "t",
                        "params": {"ability": "Blood Nova"}})
    assert out.effects == []
    assert "They can use:" in out.tell and "paths" not in out.tell
    assert leveling.usable_names(s.pc()) == []


def test_a_swing_at_nobody_is_a_sentence_not_a_502():
    s, engine = _yard()
    from rules.intents import parse_all

    out = engine.run(parse_all([{"op": "attack", "actor": "pc", "because": "t"}])).outcomes[0]
    assert out.effects == [] and "nobody" in out.tell


# --- 7d: the brief names conditions --------------------------------------------------

def test_the_brief_says_what_state_everyone_is_in():
    """Probed with a nauseated PC and a shaken NPC before this: the words "nauseated",
    "shaken" and "condition" were all absent from the player-turn brief, while the
    NPC-turn prompt said "their conditions are: shaken" all along. Both real legality
    firings in 261 turns were the model being corrected for what it could not know."""
    from gm import prompts

    class _W:
        name, premise, secret = "Fantasia", {}, ""

        def ancestors(self, _):
            return []

        def get(self, _):
            return None

    s, engine = _yard()
    s.pc().add_condition("nauseated", rounds=3, source="t")
    s.people["c1"].add_condition("shaken", rounds=3, source="t")
    brief = prompts.scene_brief(_W(), s, None, [], here=engine.here(), known=engine.places())
    assert "nauseated" in brief and "shaken" in brief


# --- 7e: the schema class -----------------------------------------------------------------

def test_a_move_without_a_zone_word_keeps_the_zone_it_had():
    """17 rejections against 2 attempts — 89% — the worst schema rate in play, and the
    reason was what the param is MADE OF: `engaged`/`near`/`far` is engine vocabulary
    the player's sentence never contains."""
    s, engine = _yard()
    s.zones["pc"] = "far"
    out = _run(engine, {"op": "move", "actor": "pc", "because": "t", "params": {}})
    assert out.op == "move" and s.zones["pc"] == "far"
    out = _run(engine, {"op": "move", "actor": "pc", "because": "t",
                        "params": {"zone": "engaged"}})
    assert s.zones["pc"] == "engaged"


# --- 7f: the ratchet ----------------------------------------------------------------------

# Every raise still allowed inside an op resolver, with the reason. A named allowlist,
# not a count. The shape `_CLOCK_SITES` established.
_ALLOWED_RESOLUTION_RAISES = {
    # Unreachable in the app: `Scene.remove` refuses the PC, so the fallback that fires
    # when `scene.pc()` is None cannot happen. Kept as raises because a printable
    # refusal for a scene with no player would be prose addressed to nobody.
    "nobody here to protect", "nobody here to do the work", "nobody to spend it from",
    "nobody here to do the taking", "nobody here to look", "nobody here to use it",
    "nobody here to bleed", "nobody here to wear it", "nobody here to rest",
    # Validated first: `_check_legality`'s travel branch refuses the same things with
    # the list of what would have worked, and the model repairs it there. The copies
    # in the resolver are the floor under a list that changed under itself.
    "say where", "is not a biome", "there is no", "names",
    # Validated first, the same way: refs the list cannot reach.
    "is not on the board at resolution time",
}


def _resolution_raises():
    src = Path("rules/engine.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    out = []
    for fn in ast.walk(tree):
        if not (isinstance(fn, ast.FunctionDef) and fn.name.startswith("_op_")):
            continue
        for node in ast.walk(fn):
            if isinstance(node, ast.Raise) and node.exc is not None:
                seg = ast.get_source_segment(src, node.exc) or ""
                if "IntentError" in seg:
                    out.append((fn.name, node.lineno, " ".join(seg.split())))
    return out


def test_every_raise_left_in_a_resolver_is_on_the_list_with_a_reason():
    """The census counted 37 explicit raises reachable from `run()`. Each one that
    remains either cannot fire or is a floor under a validate-time refusal that already
    named the fix; anything else is a 502 that deletes the player's sentence."""
    unlisted = [
        f"{fn}:{line}: {seg[:100]}"
        for fn, line, seg in _resolution_raises()
        if not any(reason in seg for reason in _ALLOWED_RESOLUTION_RAISES)
    ]
    assert unlisted == [], (
        "a resolution-time raise reaches the player as a 502 with their line "
        f"deleted; make it printable through Engine._refuse or list it with a "
        f"reason: {unlisted}")


def test_no_legality_raise_survives_in_a_resolver():
    """The strongest form: `legality` is the check kind that means "the world says no",
    and the world saying no is always a sentence."""
    left = [f"{fn}:{line}" for fn, line, seg in _resolution_raises()
            if '"legality"' in seg]
    assert left == [], left
