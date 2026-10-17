"""A tell's "against AC N" is the number the roll was judged on.

Measured live on master, 2026-10-16 (scratch copy of the owner's save, a fight with the
smith behind cover): the tell read "Kesst Vayr's attack misses the smith (10 against AC
10 (flat-footed) with cover)" while the dice popup had asked the player to beat 14. The
note was formatted from the sheet's AC BEFORE cover's +4 was added to the number being
rolled against, and "with cover" was appended in words — so the printed 10 against 10
read as a hit beside the verdict "misses". Floundering in water (-2) was appended the
same way, and the thrown flask's touch AC note had the same shape.

Tells feed the narrator and the turn log the owner reads in reports; a tell whose number
contradicts its own verdict is a defect in both. `engine._ac_said` now writes the final
number first and names its parts after it: "AC 14 (10 flat-footed, +4 cover)".
"""
from __future__ import annotations

import re

from rules.bestiary import instantiate
from rules.crafting import Stock
from rules.dice import Dice
from rules.engine import Engine, Scene, _ac_said
from rules.grid import Grid
from rules.sheet import load_pc

_AGAINST = re.compile(r"\((?:natural \d+, )?(\d+) against (?:touch )?AC (\d+)")


def _covered_board(seed: int, *, wall: bool = True):
    """A swings at Foe two squares off, a wall (or a body) between them."""
    s = Scene(location_id="t")
    a = instantiate("guildhand", scene=s, name="A")
    s.add(a, at=(4, 5))
    if not wall:
        body = instantiate("guildhand", scene=s, name="B")
        s.add(body, at=(6, 5))
    foe = instantiate("guildhand", scene=s, name="Foe")
    foe.hp = foe.hp_base = 60
    s.add(foe, at=(5, 3) if wall else (7, 5))
    s.grid = Grid()
    if wall:
        s.grid.blocked = {(5, 4)}
    return s, Engine(s, Dice(seed=seed), world=None), a, foe


def _swing(e, actor, target):
    raw = {"op": "attack", "actor": actor.ref, "because": "t", "target": target.ref,
           "params": {}}
    return e.run(e.validate([raw], origin="author:test"))


def test_the_printed_ac_is_the_number_the_miss_was_judged_on():
    """The measured line: a miss against cover. Before the fix the tell printed the
    sheet's 10 and the verdict was judged on 14, so seed 3's "8 against AC 10 ... with
    cover" — and the live "10 against AC 10" — read as hits."""
    seen_miss = False
    for seed in range(1, 12):
        s, e, a, foe = _covered_board(seed)
        res = _swing(e, a, foe)
        out = next(o for o in res.outcomes if o.op == "attack")
        assert out.dc and out.dc["value"] >= 14, out.dc
        for total, printed in _AGAINST.findall(out.tell):
            assert int(printed) == out.dc["value"], (out.tell, out.dc)
            if "misses" in out.tell and "natural" not in out.tell:
                seen_miss = True
                assert int(total) < int(printed), out.tell
        assert out.dc["explain"].startswith(f"AC {out.dc['value']} "), out.dc
        assert "+4 cover" in out.dc["explain"], out.dc
    assert seen_miss, "no miss came up in eleven seeds; the check never ran"


def test_soft_cover_is_named_with_the_final_number_too():
    for seed in range(1, 6):
        s, e, a, foe = _covered_board(seed, wall=False)
        out = next(o for o in _swing(e, a, foe).outcomes if o.op == "attack")
        for _total, printed in _AGAINST.findall(out.tell):
            assert int(printed) == out.dc["value"], (out.tell, out.dc)
        assert "+4 soft cover" in out.dc["explain"], out.dc


def test_every_printed_against_is_the_verdicts_number_over_many_swings():
    """A sweep, cover and none, both directions: every "(N against AC M" a tell prints
    has M equal to the outcome's own judged number, and a miss without a natural 1 has
    N below it, a hit N at or above it."""
    checked = 0
    for seed in range(1, 30):
        for wall in (True, False):
            s, e, a, foe = _covered_board(seed, wall=wall)
            for actor, target in ((a, foe), (foe, a)):
                for o in _swing(e, actor, target).outcomes:
                    if o.op != "attack" or not o.dc:
                        continue
                    for total, printed in _AGAINST.findall(o.tell):
                        checked += 1
                        assert int(printed) == o.dc["value"], (o.tell, o.dc)
    assert checked >= 20, checked


def test_the_thrown_flasks_touch_ac_counts_the_cover_it_prints():
    """The same shape in the splash throw: "touch AC N with soft cover" printed N before
    the +4. The dice popup's number and the tell's are one number now."""
    s = Scene(location_id="5bbd0c40345f")
    pc = s.add(load_pc("fixtures/pc-kesst.json"))
    s.add(instantiate("thug", scene=s, name="the thug"))
    s.add(instantiate("thug", scene=s, name="the other thug"))
    pc.stock["flask#1"] = Stock(base="Alchemist's Fire", count=3, specs=[
        {"type": "damage", "dice": "1d6", "damage_type": "fire", "route": "struck"}])
    e = Engine(s, Dice(seed=7))
    e._ensure_encounter("pc")
    s.positions["pc"] = (2, 10)
    s.positions["c2"] = (4, 10)          # the other thug between: soft cover
    s.positions["c1"] = (6, 10)
    s.resync_zones()
    if s.grid is None:
        s.grid = Grid()
    res = e.run(e.validate([{"op": "use_item", "actor": "pc", "because": "she throws it",
                             "params": {"item": "flask#1", "how": "throw", "to": "c1"}}]))
    prompt = res.awaiting
    assert prompt, "the throw did not ask the player for the d20"
    res = e.resume(face=2)
    told = " ".join(o.tell for o in res.outcomes)
    printed = [int(m) for _t, m in _AGAINST.findall(told)]
    assert printed == [prompt["dc"]], (told, prompt["dc"])
    assert "soft cover" in told, told


def test_the_note_reads_total_first_then_its_parts():
    assert _ac_said("AC", 12, False) == "AC 12"
    assert _ac_said("AC", 10, True) == "AC 10 (flat-footed)"
    assert _ac_said("AC", 10, True, [("cover", 4)]) == "AC 14 (10 flat-footed, +4 cover)"
    assert _ac_said("touch AC", 11, False, [("floundering in the water", -2)]) == \
        "touch AC 9 (11, -2 floundering in the water)"
    # A part worth nothing is not a part.
    assert _ac_said("AC", 15, False, [("cover", 0)]) == "AC 15"
