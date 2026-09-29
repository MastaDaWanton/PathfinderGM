"""Lane E: where a spell's area falls and what it catches (`rules/areas.py`).

Measured 2026-09-28 on the Bobby playtest (docs/playtest-2026-09-28.md item 22): Burning
Hands from the Spells tab resolved with `targets: []`, rolled `1d4 = 1` against nobody, and
the man it was pointed at — c8, fifteen feet west of Bobby at (1,8) — stood at 4 of 4 hit
points while the prose burned his face. The geometry to find him existed (`grid.cone`) and
nothing asked it. And the geometry itself measured from a square's centre: a 20-ft burst
was 61 squares where the book's intersection rule gives 44.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

import replays
from rules import areas, casting, grid as gridmod, spells as spells_mod
from rules.bestiary import instantiate
from rules.dice import Dice
from rules.engine import Engine, Scene
from rules.sheet import from_dict, load_pc, to_dict
from tests._places import stand_on

ROOT = Path(__file__).resolve().parent.parent

# Bobby's board at the Burning Hands turn (turn 13), from the save: the PC at (4,7), the
# man in a stained leather jerkin (c8) at (1,8), 4 of 4 hit points.
PC_AT, MAN_AT = (4, 7), (1, 8)


def caster(prepared=None, int_score=18):
    d = to_dict(load_pc("fixtures/pc-caster.json"))
    d["abilities"]["int"] = int_score
    d["prepared"] = {"burning-hands": 2} if prepared is None else prepared
    return from_dict(d, ref="pc")


def board(fight=True, ground="forest", seed=4):
    s = Scene(location_id="5bbd0c40345f")
    s.add(caster())
    man = s.add(instantiate("guildhand", scene=s, name="the man in a stained jerkin"))
    stand_on(s, ground)
    s.grid = gridmod.Grid(20, 20)
    s.positions["pc"] = PC_AT
    s.positions[man.ref] = MAN_AT
    if fight:
        s.initiative = [("pc", 20), (man.ref, 10)]
        s.sides = {"pc": ["pc"], "them": [man.ref]}
        s.round, s.turn = 1, 0
    return s, Engine(s, Dice(seed=seed)), man.ref


def cast(engine, aim=None, spell="burning-hands", **params):
    p = {"spell": spell, **params}
    if aim:
        p["aim"] = aim
    return engine.run(engine.validate([{"op": "cast", "actor": "pc", "because": "t",
                                        "params": p}])).outcomes[0]


# --- the geometry, by the book ---------------------------------------------------------------

@pytest.mark.parametrize("radius, book, grid_said", [(20, 44, 61), (10, 12, 21), (5, 4, 9)])
def test_e_bursts_measure_from_an_intersection(radius, book, grid_said):
    """Aiming a Spell: the origin "is always a grid intersection" and a square is in when
    its far edge is. Measured: `grid.burst((10,10), 20)` gave 61 squares — 39% larger than
    the rule's 44 — and 21 and 9 for 10 and 5 ft."""
    ground = {c for c in areas.burst_cells((10, 10, 0), radius) if c[2] == 0}
    assert len(ground) == book
    assert len(gridmod.burst((10, 10), radius)) == grid_said


def test_e_cones_start_at_a_corner_of_the_casters_square():
    """A cone "starts from any corner of your square" (Aiming a Spell; owner Q41: one rule
    for every shape). A diagonal 15-ft cone by the far-corner rule is 6 squares;
    `grid.cone`, measuring from the square's centre, gave 12. A straight one is 8 (11)."""
    assert len(areas._cone_flat((5, 5), "ne", 15)) == 6
    assert len(gridmod.cone((5, 5), "ne", 15)) == 12
    assert len(areas._cone_flat((5, 5), "w", 15)) == 8
    assert len(gridmod.cone((5, 5), "w", 15)) == 11


def test_e_burning_hands_is_a_fifteen_foot_cone():
    """The cone's length is the range line — "Range 15 ft., Area cone-shaped burst" —
    which `parse_area` rightly refuses to invent, so `shape_of` reads it off the range."""
    assert areas.shape_of(spells_mod.get("burning-hands"), 1) == {"shape": "cone",
                                                                  "length_ft": 15}
    assert areas.shape_of(spells_mod.get("fireball"), 5)["length_ft"] == 20
    assert areas.shape_of(spells_mod.get("magic-missile"), 1) == {}


def test_e_line_of_effect_ignores_smoke_not_trunks():
    """Line of effect is "a straight, unblocked path": a trunk (`blocked`) stops fire, a
    bank of smoke (`obscuring`) does not — `Grid.line_of_sight` treats both as opaque,
    which is right for sight and wrong for a fireball."""
    s, _e, man = board()
    s.grid.obscuring = {(2, 8), (3, 8), (2, 7), (3, 7)}
    area = areas.lay(s, "pc", spells_mod.get("burning-hands"), 1, areas.Aim("ref", man))
    assert areas.caught(s, area) == [man], "smoke stopped the fire"
    s.grid.obscuring = set()
    s.grid.blocked = {(3, 6), (3, 7), (3, 8), (3, 9), (3, 10)}
    area = areas.lay(s, "pc", spells_mod.get("burning-hands"), 1, areas.Aim("ref", man))
    assert areas.caught(s, area) == [], "fire went through a wall of trunks"
    assert area.fell_short


# --- the man in the cone (item 22.1) -------------------------------------------------------------

def test_e_burning_hands_finds_the_man():
    """Measured 2026-09-28: 1d4 = 1, `targets: []`, the man at 4/4 — the cone that
    contained him was never laid. Laid now, from the corner of Bobby's square, it catches
    him: he saves, and the damage is his."""
    s, e, man = board()
    out = cast(e, f"ref:{man}")
    cast_effect = out.effects[0]
    assert cast_effect["caught"] == cast_effect["targets"] == [man]
    assert cast_effect["area"]["shape"] == "cone" and cast_effect["area"]["measured"]
    saves = [x for x in out.effects if x.get("kind") == "save"]
    assert saves == [{"kind": "save", "ref": man, "save": "ref", "saved": saves[0]["saved"]}]
    assert "dc" not in saves[0] and "total" not in saves[0], "a number outside its roll"
    hurt = [x for x in out.effects if x.get("kind") == "damage"]
    assert [x["ref"] for x in hurt] == [man] or saves[0]["saved"]
    assert s.actors[man].hp < s.actors[man].hp_max or saves[0]["saved"]
    assert "catches the man in a stained jerkin" in out.tell
    assert "westward" not in out.tell and " west" not in out.tell, "a compass word"


def test_e_bobby_board_is_the_saves_board():
    """The board above is the replay's, when the corpus is on this disk (it is kept out of
    the repository — owner, Q2)."""
    if not replays.available():
        pytest.skip("the Bobby corpus is not on this disk")
    people = {p["ref"]: p for p in replays.save("bobby.json")["people"]}
    assert tuple(people["pc"]["square"]) == PC_AT
    assert tuple(people["c8"]["square"]) == MAN_AT
    assert people["c8"]["hp"] == people["c8"]["hp_max"] == 4


def test_e_every_creature_in_a_burst_saves_on_its_own():
    """A fireball "affects whatever it catches"; one roll, a save per creature, and the
    caster's own companions are not spared (friendly fire is 1e)."""
    s, e, man = board()
    s.people["pc"].prepared = {}
    d = to_dict(load_pc("fixtures/pc-caster.json"))
    d.update({"level": 5, "spellbook": ["fireball"], "prepared": {"fireball": 1}})
    d["abilities"]["int"] = 18
    s.people.pop("pc")
    s.add(from_dict(d, ref="pc"))
    s.positions["pc"] = (10, 10)
    other = s.add(instantiate("guildhand", scene=s, name="the second man"))
    s.positions[man], s.positions[other.ref] = (15, 10), (16, 11)
    s.initiative.append((other.ref, 5))
    s.sides["them"].append(other.ref)
    out = cast(e, f"ref:{man}", spell="fireball")
    assert set(out.effects[0]["caught"]) == {man, other.ref}
    assert sorted(x["ref"] for x in out.effects if x.get("kind") == "save") == \
        sorted([man, other.ref])
    assert len([r for r in out.rolls if r.die == "5d6"]) == 1, "rolled once for the area"


# --- no victim, and what burns (21.2, 22.4) ------------------------------------------------------

def test_e_no_victim_rolls_nothing():
    """A cast that caught nobody rolls nothing: the dice line "1d4 — 1." with no victim was
    what the prose dressed as a burned face. Up into the canopy of a forest (canopy at
    10 ft, owner Q32): nobody aloft, the canopy caught and lit, no fight, no attitude."""
    s, e, man = board(fight=False)
    s.positions[man] = (15, 15)
    out = cast(e, "dir:up")
    ce = out.effects[0]
    assert ce["no_victim"] is True and ce["caught"] == [] and "harmful" not in ce
    assert out.rolls == [] and "1d4 —" not in out.tell
    assert "reach nobody" in out.tell
    assert ce["caught_objects"] == [{"kind": "feature", "name": "canopy", "burns": True}]
    fire = [m for m in s.manifests if m.what == "burning canopy"]
    assert fire and all(c[2] >= areas.CANOPY_FROM for c in fire[0].squares)
    assert not s.in_encounter
    assert not any(x.get("kind") == "attitude" for x in out.effects)


def test_e_into_the_tree_tops_is_the_canopy():
    """"I cast burning hands into the tree tops" — the sentence of item 21 — grounds to the
    canopy without a model, and the tell keeps the player's words."""
    s, e, _man = board(fight=False)
    s.positions[_man] = (15, 15)
    assert areas.aim_from_words(s, "pc", "I cast burning hands into the tree tops") == \
        "object:canopy"
    out = cast(e, "object:tree tops")
    assert "up into the tree tops" in out.tell and "canopy catches fire" in out.tell
    assert out.effects[0]["aim"] == {"kind": "object", "value": "canopy",
                                     "said": "the tree tops"}


def test_e_undergrowth_burns_and_smokes():
    """Dry undergrowth lit by the flames: a burning patch and smoke over it (`obscuring`,
    concealment), lasting the CRB forest fire's 2d4 × 10 minutes, and no spread."""
    s, e, man = board(fight=False)
    s.positions[man] = (15, 15)
    s.grid.difficult = {(2, 7), (2, 8)}
    out = cast(e, "object:undergrowth")
    kinds = {m.what for m in s.manifests}
    assert {"burning undergrowth", "smoke"} <= kinds
    smoke = next(m for m in s.manifests if m.what == "smoke")
    assert set(smoke.added) <= {(2, 7), (2, 8)} and smoke.added
    assert 200 <= smoke.rounds_left <= 800
    assert "smoke rises" in out.tell


def test_e_an_aim_at_nothing_here_is_refused_with_what_is_here():
    """In the classbuilder's style: the refusal lists what IS here, coded player-fixable."""
    from rules.intents import IntentError

    s, e, _man = board(ground="grassland")
    with pytest.raises(IntentError) as got:
        cast(e, "object:the well")
    assert got.value.code == "no_such_object" and got.value.fixable_by == "player"
    assert "grass" in str(got.value)


def test_e_an_area_spell_aimed_at_nothing_is_no_aim():
    """The Spells tab sent a cone with no target and it resolved as `targets: []`. Now an
    area spell with no aim is refused `no_aim` — the player's to answer."""
    from rules.intents import IntentError

    _s, e, _man = board()
    with pytest.raises(IntentError) as got:
        cast(e)
    assert got.value.code == "no_aim" and got.value.fixable_by == "player"


def test_e_no_map_means_the_named_creature_alone():
    """Theatre of the mind: with no grid the area is not measured and the aim decides — the
    path every existing cast test (`at: c1`, no map) already takes."""
    s, e, man = board()
    s.grid = None
    s.positions.clear()
    out = cast(e, f"ref:{man}")
    assert out.effects[0]["targets"] == [man]
    assert out.effects[0]["area"]["measured"] is False


# --- one place decides membership ------------------------------------------------------------------

def test_e_one_area_function():
    """Walled Templates offers two definitions of "caught" and Midi-QOL warns against
    running two targeting systems at once; here there is one. No module but `rules/areas.py`
    (and `rules/grid.py`, which defines them) calls the grid's area shapes."""
    pattern = re.compile(r"\b(?:gridmod|grid)\.(?:cone|line|burst|cylinder)\(")
    offenders = []
    for folder in ("rules", "gm", "play", "tools"):
        for path in (ROOT / folder).rglob("*.py"):
            if path.name in ("areas.py", "grid.py"):
                continue
            if pattern.search(path.read_text(encoding="utf-8")):
                offenders.append(str(path.relative_to(ROOT)))
    assert offenders == []


def test_e_the_aim_pattern_is_one_pattern():
    """The door's copy (`views._AIM`) is the canonical one's (§2.7)."""
    from play import views

    assert views._AIM.pattern == areas.AIM_PATTERN
    for good in ("ref:c8", "self", "dir:up", "point:3,4", "point:3,4,1", "object:the cart"):
        assert areas.valid(good)
    for bad in ("at the man", "dir:westward", "point:3", "ref:", ""):
        assert not areas.valid(bad)
