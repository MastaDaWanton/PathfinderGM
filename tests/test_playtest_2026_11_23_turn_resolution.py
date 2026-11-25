"""Turn resolution: playtest 2026-11-23 (the owner's 0.5.0 game, Shadow in the tower), items
3, 4, 11, 12 and 18. Research: docs/research/2026-11-25-fix-turn-resolution.md."""
from __future__ import annotations

from gm import interpret, narration
from tests.test_dungeon_combat import _sewers
from tests.test_playtest_2026_11_16_travel import _run


# --- #3: a blow and a walk in one turn ------------------------------------------------------

def test_a_blow_that_opens_a_fight_holds_the_party_where_it_opened():
    """#3: "I attack the scholar" rode a place chip for the cold hall, and the one batch
    ran `attack` (battle joined) and then `travel` ("The fight is left behind. Left behind:
    the lost scholar"). The fight is joined here; the walk is refused, said."""
    s, e = _sewers()
    here = s.at
    rat = e._bring_in("rat-dire")[0]["ref"]
    outs = _run(e, {"op": "attack", "target": rat},
                {"op": "travel", "params": {"place": "the main channel"}})
    assert s.in_encounter and s.at == here, [o.tell for o in outs]
    walk = next(o for o in outs if o.op == "travel")
    assert walk.status == "refused" and "Battle is joined" in walk.tell, walk.tell
    assert "left behind" not in " ".join(o.tell for o in outs).lower()


def test_a_walk_with_no_fight_in_the_batch_still_walks():
    """The guard is for the batch that joined the fight, not every walk."""
    s, e = _sewers()
    outs = _run(e, {"op": "travel", "params": {"place": "the main channel"}})
    assert s.at.endswith("the-main-channel"), [o.tell for o in outs]


# --- #4: "I finish the ramidreju" ----------------------------------------------------------

def test_the_reader_is_shown_a_bare_finish_as_the_killing_stroke():
    """#4: "i finish the ramidreju", the beast unconscious and dying after the fight, was
    read `consume` (as one finishes a drink) — the frozen reader, 3 of 3 probes; the only
    demonstration of the killing stroke said "finish off". Reworded to the bare verb, the
    live reader read the owner's line `attack, blow: finishing` and still read "I finish my
    ale" `consume` (docs/research). A pin of the demonstration, since the reading itself is
    a model's: the bare verb must stay demonstrated."""
    demos = [d for d, _frame in interpret._DEMOS if d.startswith("I finish the ")]
    assert demos, "no demonstration reads a bare 'finish the <creature>'"
    frame = dict(interpret._DEMOS)[demos[0]]
    blow = frame["actions"][0]
    assert blow["act"] == "attack" and blow["blow"] == "finishing", blow


# --- #18: "landing a blow piercing damage" -------------------------------------------------

def _outcome(tell, amount=15, kind="bludgeoning and piercing"):
    return {"op": "attack", "tell": tell, "rolls": [],
            "effects": [{"kind": "damage", "amount": amount, "type": kind, "ref": "c10"}]}


def test_a_two_type_damage_amount_comes_off_the_page_whole():
    """#18 (#211): the page read "You strike the clockwork spy, landing a blow piercing
    damage." The engine's tell was "for 15 bludgeoning and piercing": the number's words
    were read two deep ("bludgeoning and"), so the guard lifted "for 15 bludgeoning and"
    out of "landing a blow for 15 bludgeoning and piercing damage" and left "piercing
    damage" behind. The amount goes with every word of its type."""
    o = _outcome("Shadow hits the clockwork spy for 15 bludgeoning and piercing.")
    text, gone = narration.strip_turn_numbers(
        "You strike the clockwork spy, landing a blow for 15 bludgeoning and piercing "
        "damage. It reels.", [o])
    assert text == "You strike the clockwork spy, landing a blow. It reels.", (text, gone)


def test_the_and_of_a_type_pair_does_not_eat_the_next_clause():
    """The pair's "and" is lifted only between two of the number's words: the sentence's
    own "and" after the amount stays."""
    o = _outcome("Shadow hits the clockwork spy for 15 bludgeoning and piercing.")
    text, _ = narration.strip_turn_numbers(
        "You hit it for 15 bludgeoning and piercing damage and it falls.", [o])
    assert text == "You hit it and it falls.", text


def test_the_engine_line_handed_to_a_repair_has_no_two_type_amount():
    """#18's source: `page_line` (the blow written onto the page by `_show_blows`) kept
    "for 15 bludgeoning and piercing", three words past the number where its pattern read
    two, so the model was handed the number to copy."""
    line = narration.page_line("You hit the clockwork spy for 15 bludgeoning and piercing.")
    assert line == "You hit the clockwork spy.", line


# --- #11: "already down; holds the blow" on the blow that downed it --------------------------

def _full_attack_that_drops(seed):
    from rules.dice import Dice
    from rules.engine import Engine
    from tests.test_coup_de_grace import _scene

    s = _scene(pc="fixtures/pc-borin.json")
    s.actors["pc"].level = 8
    s.zones["c1"] = "engaged"
    e = Engine(s, Dice(seed=seed))
    e._ensure_encounter("pc", "c1")
    s.actors["c1"].hp = 1
    res = e.run(e.validate([{"op": "attack", "actor": "pc", "target": "c1", "because": "t",
                             "visibility": "hidden",
                             "params": {"weapon": "longsword", "full_attack": True}}]))
    return s, next(o for o in res.outcomes if o.op == "attack")


def test_the_swing_that_drops_them_is_not_told_as_at_a_body_already_down():
    """#11: "Shadow hits the clockwork spy for 15 bludgeoning and piercing. The clockwork
    spy is already down; Shadow holds the blow. The clockwork spy is broken" — the held
    clause belongs to a swing at a body that was down BEFORE the attack (kept, and pinned
    by `test_a_swing_queued_behind_the_one_that_dropped_them_is_still_held`), never to
    the one that put them there. A fighter's full attack whose first swing drops the foe:
    one swing rolled, the fall told, no "already down"."""
    for seed in range(40):
        s, out = _full_attack_that_drops(seed)
        swings = [r for r in out.rolls if r.label.startswith("Attack with")]
        if len(swings) == 1 and s.actors["c1"].is_down:
            break
    else:
        raise AssertionError("no seed dropped the foe on the first swing")
    assert "already down" not in out.tell and "holds the blow" not in out.tell, out.tell
    assert "dying" in out.tell or "dead" in out.tell or "unconscious" in out.tell, out.tell


# --- #12: an opening blow out of reach, and Start a fight -----------------------------------

def _calm(seed=5):
    from rules.bestiary import instantiate
    from rules.dice import Dice
    from rules.engine import Engine, Scene
    from rules.sheet import load_pc

    s = Scene(location_id="5bbd0c40345f")
    s.add(load_pc("fixtures/pc-kesst.json"))
    s.add(instantiate("thug", scene=s, name="the thug"))
    s.zones["c1"] = "far"
    return s, Engine(s, Dice(seed=seed))


def _square_off(s, e):
    return e.run(e.validate([{"op": "attack", "actor": "pc", "target": "c1",
                              "because": "Start a fight", "params": {"squares_off": True}}]))


def test_squaring_off_forms_the_fight_and_strikes_nothing():
    """#12: "I walk over and strike the clockwork spy" (40 ft off) and "I punch the
    poltergeist" (35 ft) only joined battle — by design, the battle gate holds a player's
    blow out of reach for the bar — and the player had to declare it again. The owner's
    note: let the player enter the fight first and plan the strike. Squaring off forms the
    fight a swing would form, and rolls nothing, asks for no die and hurts nobody."""
    s, e = _calm()
    hp = s.actors["c1"].hp
    res = _square_off(s, e)
    out = next(o for o in res.outcomes if o.op == "attack")
    assert s.in_encounter and not s.awaiting and not out.rolls, out.tell
    assert s.actors["c1"].hp == hp
    assert any(fx.get("kind") == "battle_joined" for fx in out.effects)


def test_squaring_off_keeps_the_books_order():
    """No action was declared, so the initiator keeps none: the order is initiative's,
    highest first (CRB, Combat, "How Combat Works"). Over twelve seeds the thug, winning,
    holds the first turn; the player, winning, holds it — and nobody else has begun a turn."""
    tops = set()
    for seed in range(12):
        s, e = _calm(seed)
        _square_off(s, e)
        top = next(r for r, _ in s.initiative if not s.actors[r].has_state("state.unable"))
        assert s.current_ref() == top, (seed, s.initiative, s.current_ref())
        assert s.acted == {top}, s.acted          # the turn begun is the only one
        tops.add(top)
    assert tops == {"pc", "c1"}, tops


def test_squaring_off_is_refused_in_a_fight_and_at_a_body_on_the_floor():
    s, e = _calm()
    _square_off(s, e)
    again = next(o for o in _square_off(s, e).outcomes if o.op == "attack")
    assert again.status == "refused" and "already on" in again.tell
    s, e = _calm()
    s.actors["c1"].hp = -3
    s.actors["c1"].apply_hp_state()
    down = next(o for o in _square_off(s, e).outcomes if o.op == "attack")
    assert down.status == "refused" and not s.in_encounter, down.tell


def test_the_bar_starts_a_fight_out_of_one(tmp_path):
    """The door: `/api/combat/act` refuses everything out of a fight but a free action
    (test_combat_panel), and now also one attack that squares off — the table's Start a
    fight. The fight is on afterwards, nobody hurt, and the turn is the order's."""
    import json

    from django.test import Client, override_settings

    from play import campaign as cm
    from rules.bestiary import instantiate
    from rules.sheet import load_pc

    with override_settings(CAMPAIGN_DIR=tmp_path / "campaigns"):
        cm._LIVE.clear()
        c = cm.begin_with(load_pc("fixtures/pc-kesst.json"))
        c.seed = 20260830
        for ref in [r for r in c.scene.actors if r != "pc"]:
            c.scene.depart(ref)
        thug = instantiate("thug", scene=c.scene, name="the thug")
        c.scene.add(thug)
        c.save()
        r = Client().post("/api/combat/act", content_type="application/json",
                          data=json.dumps({"actions": [{"op": "attack", "target": thug.ref,
                                                        "params": {"squares_off": True}}],
                                           "label": "Start a fight with the thug",
                                           "end_turn": False}))
        scene = cm.current().scene
        cm._LIVE.clear()
    assert r.status_code == 200, r.content[:300]
    assert scene.in_encounter
    assert scene.actors[thug.ref].hp == thug.hp_max, "squaring off struck nobody"
    # Whoever won initiative: the player holds the turn, or the thug took his and the
    # order came back round to the player (`_finish` runs the loop when a foe is first).
    assert scene.current_ref() == "pc", scene.initiative



# --- #12, owner ruling 2026-11-25: the player who starts the fight strikes first -------------

def _far_thug():
    from rules.bestiary import instantiate
    from rules.dice import Dice
    from rules.engine import Engine, Scene
    from rules.sheet import load_pc

    s = Scene(location_id="5bbd0c40345f")
    s.add(load_pc("fixtures/pc-kesst.json"), at=(4, 10))
    s.add(instantiate("thug", scene=s, name="the thug"), at=(12, 10))     # 40 ft off
    from rules.grid import Grid

    s.grid = Grid(width=20, height=20)
    return s, Engine(s, Dice(seed=5))


def test_walk_over_and_strike_walks_then_strikes_the_opening_blow():
    """Owner ruling 2026-11-25, on #12 ("I walk over and strike the clockwork spy" from
    40 ft only joined battle): what the player declares before the hostile act resolves
    first as ordinary action, then the blow lands as the opening strike. The reading's
    `go` (no place) before the blow becomes the walk up to the one struck
    (`acts_to_ops._up_to`), out of the fight and with no speed cap; the blow then opens the
    fight in reach and asks for the player's d20, the thug caught unready (surprised)."""
    from gm import acts_to_ops, judgement
    from rules import states

    s, e = _far_thug()
    said = "I walk over and strike the thug"
    frame = {"question": False, "claims": [], "actions": [
        {"act": "go", "span": "walk over"},
        {"act": "attack", "target": "the thug", "span": "strike the thug"}]}
    rows = acts_to_ops.table(frame, s, sentence=said)
    acts_to_ops.victims(rows, frame, s)
    # The turn's own chain: the plan's blow aimed (`inject_fight`), the built walk added
    # (`apply`, as a copy), and the words' order (`order`). Live on the owner's save the
    # strike ran BEFORE the walk, and the walk spent the surprise round's one action.
    plan = [{"op": "attack", "actor": "pc", "target": "c1", "params": {"full_attack": False}}]
    plan = judgement.inject_fight(plan, said, s, rows=rows, frame=frame)
    plan = acts_to_ops.order(acts_to_ops.apply(plan, rows, frame, s), rows, frame)
    assert [p["op"] for p in plan] == ["move", "attack"], plan
    res = e.run(e.validate([dict(p, visibility="player", because="t") for p in plan]))
    ops = [(o.op, o.status) for o in res.outcomes]
    assert ("move", "resolved") in ops, ops
    assert s.in_encounter and s.awaiting and s.awaiting["label"].startswith("Attack with"), ops
    assert s.actors["c1"].has_state(states.SURPRISED)
    assert s.actors["pc"].has_state(states.ONE_ACTION_TURN)


def test_strike_him_from_forty_feet_still_walks_nobody():
    """The same ruling's other half: "I strike him" from 40 ft says no walk, so nobody is
    walked — the fight opens (the thug unready) and the blow waits for the bar, where the
    book's surprise round gives the player one action: the walk or the blow, not both."""
    from gm import acts_to_ops

    s, e = _far_thug()
    frame = {"question": False, "claims": [], "actions": [
        {"act": "attack", "target": "the thug", "span": "strike the thug"}]}
    rows = acts_to_ops.table(frame, s, sentence="I strike the thug")
    acts_to_ops.victims(rows, frame, s)
    assert not [i for r in rows for i in r.intents if i.get("op") == "move"]
    blow = next(i for r in rows for i in r.intents if i.get("op") == "attack")
    before = s.positions["pc"]
    e.run(e.validate([dict(blow, visibility="player")]))
    assert s.in_encounter and not s.awaiting and s.positions["pc"] == before


def test_an_opening_full_attack_is_one_blow_in_the_surprise_round():
    """The book's limit, said: the surprise round is one standard action (CRB), so an
    opening full attack in reach is one blow, and the tell says why."""
    from rules.bestiary import instantiate
    from rules.dice import Dice
    from rules.engine import Engine, Scene
    from rules.sheet import load_pc

    s = Scene(location_id="5bbd0c40345f")
    s.add(load_pc("fixtures/pc-borin.json"))
    s.actors["pc"].level = 8
    s.add(instantiate("thug", scene=s, name="the thug"))
    s.zones["c1"] = "engaged"
    e = Engine(s, Dice(seed=5))
    res = e.run(e.validate([{"op": "attack", "actor": "pc", "target": "c1", "because": "t",
                             "params": {"weapon": "longsword", "full_attack": True}}]))
    joined = next(o for o in res.outcomes if o.op == "attack")
    assert "time for one blow" in joined.tell, joined.tell
    assert s.awaiting and s.awaiting["label"].startswith("Attack with"), s.awaiting
