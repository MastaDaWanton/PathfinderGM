"""A grapple, once taken, is kept, broken and ended by the rules (CRB p.200).

Measured on the owner's report of 2026-11-01 (Corvin T., the shrine), after 0.2.25's grab
rider made grapples common:

  * nothing ENDED one — the condition's only tags were `state.held.grappled` and
    `recovery.rest`, `end_encounter` did not touch it, and the giant rot grub, dying at -1,
    kept the player grappled after the fight was over;
  * nothing MAINTAINED one — `_on_hold` said "the grapple maintained on later turns has no
    executor", so the grub's later turns were ordinary bites;
  * nothing ESCAPED one — "excape grap[ple" read as `other`, the planner's grapple at the
    grub was refused five times as "already grappled" and the turn degraded to narration,
    and a plain Escape Artist check at DC 10 succeeded and removed nothing.

The book: "If you are grappled, you can attempt to break free from the grapple as a
standard action by making a combat maneuver check (DC equal to your opponent's CMD; this
does not provoke an attack of opportunity) or Escape Artist check (with a DC equal to your
opponent's CMD). If you succeed, you break the grapple"; the holder "must continue to make
a check each round, as a standard action, to maintain the hold", +5 against the same target
in later rounds; Grab (Bestiary UMR): "each successful grapple check it makes during
successive rounds automatically deals the damage indicated for the attack that established
the hold".
"""
from __future__ import annotations

import pytest

from rules.bestiary import instantiate
from rules.dice import Dice
from rules.engine import Engine, Scene, _held_by
from rules.grid import Grid
from rules.sheet import load_pc


def _scene(seed=7, template="giant-rot-grub", name="giant rot grub"):
    s = Scene()
    s.grid = Grid(width=20, height=20)
    s.add(load_pc("fixtures/pc-kesst.json"), at=(5, 5))
    grub = s.add(instantiate(template, scene=s, name=name), at=(6, 5))
    e = Engine(s, dice=Dice(seed=seed))
    e.run(e.validate([{"op": "begin_encounter",
                       "params": {"sides": {"pc": ["pc"], "them": [grub.ref]}}}]))
    return s, e, grub


def _grabbed(s, holder, held, *, weapon="bite", bonus=4):
    """The state the grab rider leaves (`_resolve_maneuver` + `_rider_maneuver`): the
    grappled condition on both, holder and grappler written, the hold's attack noted."""
    held.add_condition("grappled", source=f"grapple by {holder.name}")
    _held_by(held, "grappled", holder.ref, grappler=holder.ref)
    holder.add_condition("grappled", source=f"grappling {held.name}")
    _held_by(holder, "grappled", held.ref, grappler=holder.ref)
    for e in held.effects:
        if e.kind == "condition" and e.key == "grappled":
            e.payload = dict(e.payload, hold_weapon=weapon, hold_bonus=bonus,
                             hold_rider="grab", hold_then=[],
                             hold_origin=f"creature:{holder.from_template}")


def _grappled(a) -> bool:
    return a.has_state("state.held.grappled")


def test_the_grab_rider_writes_whose_hold_it_is_and_what_it_does():
    """The real rider, rolled until the grub's grab lands: both grappled, the grub the
    grappler, and the bite that seized written onto the hold."""
    for seed in range(60):
        s, e, grub = _scene(seed)
        s.pc().hp = s.pc().hp_max = 200
        e.run(e.validate([{"op": "attack", "actor": grub.ref, "target": "pc",
                           "visibility": "hidden", "params": {}}],
                         origin=f"creature:{grub.from_template}"))
        if _grappled(s.pc()):
            break
    else:
        pytest.skip("no seed landed the grab")
    pc = s.pc()
    assert e._holds(grub, pc) and not e._holds(pc, grub)
    hold = next(x for x in pc.effects if x.kind == "condition" and x.key == "grappled")
    assert hold.payload["by"] == grub.ref and hold.payload["grappler"] == grub.ref
    assert hold.payload["hold_rider"] == "grab" and hold.payload["hold_bonus"] == 4
    assert pc.held_in_grapple and not grub.held_in_grapple


def test_the_grapple_ends_when_the_holder_goes_down():
    """The report's own shape: the grub dropped to -1, dying; the player stayed held."""
    s, e, grub = _scene()
    pc = s.pc()
    _grabbed(s, grub, pc)
    out = e.run(e.validate([{"op": "damage", "actor": "pc", "target": grub.ref,
                             "params": {"amount": grub.hp + 1, "type": "bludgeoning"}}],
                           origin="author:test"))
    assert grub.is_down and not grub.is_dead
    assert not _grappled(pc) and not _grappled(grub)
    told = " ".join(o.tell for o in out.outcomes)
    assert "The grapple between" in told and "is down" in told
    # With its article, as every tell names a person (`Engine._articled`): the live check
    # printed "and giant rot grub ends".
    assert "and the giant rot grub ends" in told
    # And on the page in the second person: "You strains" reached it in the live check.
    from gm import narration

    said, _ = narration.pc_to_second_person(
        "Kesst Vayr strains against the giant rot grub's hold. Kesst Vayr breaks free.",
        "Kesst Vayr")
    assert "You strain against" in said and "You break free" in said


def test_the_grapple_ends_with_the_fight():
    s, e, grub = _scene()
    pc = s.pc()
    _grabbed(s, grub, pc)
    s.end_encounter()
    assert not _grappled(pc) and not _grappled(grub)
    assert any(r.get("op") == "grapple-ended" for r in s.log)


def test_the_grapple_ends_when_they_are_moved_apart():
    s, e, grub = _scene()
    pc = s.pc()
    _grabbed(s, grub, pc)
    s.positions[grub.ref] = (12, 5)
    out = e.run(e.validate([{"op": "narrate_only"}]))
    e.run(e.validate([{"op": "check", "actor": "pc", "visibility": "hidden",
                       "params": {"skill": "perception", "dc": 10}}]))
    assert not _grappled(pc), [o.tell for o in out.outcomes]


def test_escape_rolls_against_the_holders_cmd_and_ends_it_for_both():
    """The player's own d20 (the dice popup), Escape Artist or the manoeuvre, against the
    grub's CMD; success takes the grappled condition off both."""
    s, e, grub = _scene()
    pc = s.pc()
    _grabbed(s, grub, pc)
    cmd = sum(m.value for m in grub.cmd_modifiers(maneuver="grapple"))
    res = e.run(e.validate([{"op": "escape", "actor": "pc", "params": {}}]))
    assert res.awaiting and res.awaiting["dc"] == cmd
    assert "break the grapple" in res.awaiting["label"]
    res = e.resume(20)
    out = res.outcomes[-1]
    assert out.op == "escape" and out.verdict == "success", out.tell
    assert not _grappled(pc) and not _grappled(grub)
    assert f"against CMD {cmd}" in out.tell and "breaks free" in out.tell


def test_a_failed_escape_leaves_the_hold():
    s, e, grub = _scene()
    pc = s.pc()
    _grabbed(s, grub, pc)
    res = e.run(e.validate([{"op": "escape", "actor": "pc", "params": {"how": "cmb"}}]))
    res = e.resume(1)
    assert res.outcomes[-1].verdict == "failure"
    assert _grappled(pc) and _grappled(grub)


def test_escaping_with_nobody_holding_is_refused_in_words():
    s, e, grub = _scene()
    out = e.run(e.validate([{"op": "escape", "actor": "pc", "params": {}}])).outcomes[-1]
    assert out.status == "refused" and "Nobody is holding" in out.tell


def test_the_grappled_penalty_stays_off_the_grapple_and_the_escape():
    """CRB, Grappled: "-2 penalty on all attack rolls and combat maneuver checks, except
    those made to grapple or escape a grapple"."""
    s, e, grub = _scene()
    pc = s.pc()
    _grabbed(s, grub, pc)
    plain = sum(m.value for m in pc.cmb_modifiers("trip"))
    assert sum(m.value for m in pc.cmb_modifiers("escape")) == plain + 2
    assert sum(m.value for m in pc.cmb_modifiers("grapple")) == plain + 2


def test_the_planners_grapple_at_the_holder_is_the_escape_not_a_refusal():
    """Measured: five attempts "attack: giant rot grub is already grappled", then the
    turn degraded. A grapple from the one held at its holder is the escape check."""
    s, e, grub = _scene()
    pc = s.pc()
    _grabbed(s, grub, pc)
    res = e.run(e.validate([{"op": "attack", "actor": "pc", "target": grub.ref,
                             "params": {"manoeuvre": "grapple"}}]))
    assert res.awaiting and "break the grapple" in res.awaiting["label"]
    res = e.resume(20)
    assert not _grappled(pc)


def test_the_holder_keeps_the_hold_on_its_turn_and_the_bite_lands():
    """`grapple_turn`: CMB +5 (+4 grab) against the player's CMD; kept, the bite that
    seized deals its damage; the turn is the rule's, no model asked."""
    for seed in range(40):
        s, e, grub = _scene(seed)
        pc = s.pc()
        pc.hp = pc.hp_max = 200
        _grabbed(s, grub, pc)
        res = e.grapple_turn(grub.ref)
        out = res.outcomes[-1]
        if out.verdict == "success":
            break
    assert out.verdict == "success", out.tell
    labels = [r.label for r in out.rolls]
    assert any("keeping hold" in lbl for lbl in labels)
    hit = next(x for x in out.effects if x.get("kind") == "damage")
    assert hit["ref"] == "pc" and hit["weapon"] == "bite" and pc.hp == 200 - hit["amount"]
    check = next(r for r in out.rolls if "keeping hold" in r.label)
    sources = {m.source for m in check.modifiers}
    assert "maintaining the hold" in sources and "grab" in sources
    assert _grappled(pc)


def test_a_failed_keeping_check_lets_go():
    for seed in range(80):
        s, e, grub = _scene(seed)
        pc = s.pc()
        _grabbed(s, grub, pc, bonus=0)
        pc.flat_cmd = 60                      # beyond any roll but a natural 20
        out = e.grapple_turn(grub.ref).outcomes[-1]
        if out.verdict == "failure":
            break
    assert out.verdict == "failure"
    assert not _grappled(pc) and not _grappled(grub)
    assert "the grapple ends" in out.tell


def test_a_creature_that_holds_nobody_plans_its_own_turn():
    s, e, grub = _scene()
    assert e.grapple_turn(grub.ref) is None


def test_the_reader_has_an_escape_act_and_it_builds_the_escape_op():
    """"escape grapple" reads `escape`, a closed act with a closed way; the table builds
    the engine's `escape` op whole, and the plan's own Escape Artist check is replaced."""
    from gm import acts_to_ops, interpret

    assert "escape" in interpret.ACTS and interpret.ESCAPE_WAYS == ("either", "force", "slip")
    s, e, grub = _scene()
    _grabbed(s, grub, s.pc())
    frame = {"question": False, "claims": [], "actions": [
        {"act": "escape", "way": "slip", "span": "escape grapple"}]}
    rows = acts_to_ops.table(frame, s, sentence="escape grapple")
    assert rows[0].intents == [{"op": "escape", "actor": "pc",
                                "params": {"how": "escape artist"},
                                "because": "the player breaks the hold"}]
    plan = [{"op": "check", "actor": "pc",
             "params": {"skill": "escape artist", "dc": {"band": "average"}}}]
    notes: list = []
    out = acts_to_ops.apply(plan, rows, frame, s, notes=notes)
    assert [r["op"] for r in out] == ["escape"], out
    assert any("replaced by the reading's escape" in n for n in notes)


def test_a_disabled_creature_pays_a_hit_point_for_a_standard_action():
    """Measured on the report (Corvin T., the marsh, log rows 315 and 320): Lila Duskwatch at
    0 hit points — disabled — swung twice and paid nothing. CRB p.190, Disabled: "if you
    perform any standard action ... you take 1 point of damage after completing the act"."""
    s, e, grub = _scene(template="thug", name="Lila")
    lila = grub
    lila.hp = 0
    lila.apply_hp_state()
    assert lila.has_state("state.impaired.disabled")
    out = e.run(e.validate([{"op": "attack", "actor": lila.ref, "target": "pc",
                             "visibility": "hidden", "params": {}}],
                           origin=f"creature:{lila.from_template}"))
    strain = [o for o in out.outcomes if o.op == "strain"]
    assert len(strain) == 1 and lila.hp == -1, [o.tell for o in out.outcomes]
    assert lila.has_state("state.down.dying") or lila.is_down
    assert "costs Lila a hit point" in strain[0].tell
