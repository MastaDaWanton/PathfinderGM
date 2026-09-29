"""I3: fire in the world — what a lit patch costs, how long it stands, and what the brief says.

Measured on the fix pass's G2 cast-area run and Bobby's playtest (docs/playtest-2026-09-28.md
items 21.2 and 22.4): Burning Hands licked the undergrowth and a stall's awnings, the tell
said "catches fire", and nothing followed. `Engine._ignite` placed a manifestation with no
ward, so standing in the flames cost nothing; a fight ending wiped it at once
(`Scene.end_encounter` cleared every manifestation); and the next beat's brief never said
anything was burning. The rows are the CRB's (Catching on Fire, aonprd.com/Rules.aspx?ID=331;
Smoke Effects, CRB Environment), and the owner's Q33: a patch, 2d4 × 10 minutes, no spread.
"""
from __future__ import annotations

from gm import brief as brief_mod
from gm.brief import burning
from rules import areas, grid as gridmod, hazards
from rules.bestiary import instantiate
from rules.dice import Dice
from rules.engine import Engine, Scene
from rules.sheet import from_dict, load_pc, to_dict
from tests._places import stand_on

PC_AT = (4, 7)
BRUSH = {(1, 6), (1, 7), (1, 8), (2, 6), (2, 7), (2, 8)}


def caster():
    d = to_dict(load_pc("fixtures/pc-caster.json"))
    d["abilities"]["int"] = 18
    d["prepared"] = {"burning-hands": 2}
    return from_dict(d, ref="pc")


def forest(worlds, fight=True, seed=5):
    """A caster at the edge of a patch of undergrowth, west of her, in this world's first
    settlement's forest — the terrain word, never the world's names."""
    row = (worlds.play.get("settlements") or [])[0]
    s = Scene(location_id=row["id"])
    s.add(caster())
    man = s.add(instantiate("guildhand", scene=s, name="a woodcutter"))
    stand_on(s, "forest")
    s.grid = gridmod.Grid(20, 20)
    s.grid.difficult = set(BRUSH)
    s.positions["pc"] = PC_AT
    s.positions[man.ref] = (12, 12)
    if fight:
        s.initiative = [("pc", 20), (man.ref, 10)]
        s.sides = {"pc": ["pc"], "them": [man.ref]}
        s.round, s.turn = 1, 0
    return s, Engine(s, Dice(seed=seed), world=worlds), man.ref


def cast(e, aim):
    return e.run(e.validate([{"op": "cast", "actor": "pc", "because": "t",
                              "params": {"spell": "burning-hands", "aim": aim}}])).outcomes[0]


def fires(s):
    return [w for w in s.wards if (w.spec or {}).get("hazard")]


# --- the rows ---------------------------------------------------------------------------------

def test_i3_the_fire_rows_are_the_books():
    """Catching on Fire: "a DC 15 Reflex saving throw", "1d6 points of damage immediately".
    Smoke: "Fortitude save each round (DC 15, +1 per previous check)", "1d6 points of
    nonlethal damage" after two rounds of choking. Each row names what it does not yet do."""
    brush, smoke = hazards.get("burning-brush"), hazards.get("smoke")
    assert brush["ward"] == {"save": "ref", "dc": 15, "dice": "1d6", "type": "fire",
                             "lethality": "lethal"}
    assert smoke["ward"]["save"] == "fort" and smoke["ward"]["dc"] == 15
    assert smoke["ward"]["lethality"] == "nonlethal"
    assert "ID=331" in brush["source"] and "20% miss chance" in smoke["source"]
    assert brush["not_yet"] and smoke["not_yet"]
    # As a cited hazard, smoke is the book's own count: 1d6 for each two rounds choked.
    assert hazards.check("smoke", {"rounds": 4}) == ""
    plan = hazards.plan("smoke", {"rounds": 4})
    assert plan["dice"] == "2d6" and plan["lethality"] == "nonlethal"


# --- what burning costs -----------------------------------------------------------------------

def test_i3_lit_brush_carries_the_rows_wards(worlds):
    """The undergrowth caught and nothing followed: `_ignite` placed a manifestation with no
    ward. Now each burning patch carries `burning-brush` and its smoke `smoke`, with the
    rows' saves and DCs — none of them a number the engine or a model wrote."""
    s, e, _ = forest(worlds)
    out = cast(e, "object:undergrowth")
    kinds = [x.get("hazard") for x in out.effects if x.get("kind") == "manifest"]
    assert kinds == ["burning-brush", "smoke"], out.tell
    wards = {(w.spec or {})["hazard"]: w for w in fires(s)}
    assert wards["burning-brush"].dc == 15 and wards["burning-brush"].spec["target"] == "ref"
    assert wards["smoke"].dc == 15 and wards["smoke"].spec["target"] == "fort"
    assert wards["burning-brush"].source == "burning brush"
    assert all(w.spec["at"] == s.at for w in wards.values())
    assert "risks catching fire" in out.tell and "does not spread" in out.tell


def test_i3_standing_in_the_flames_is_asked_each_round(worlds):
    """A creature in the burning squares when the round turns is asked the Reflex save,
    and burns on a failure — through `Scene.tick_standing`, the one ticker."""
    s, e, man = forest(worlds)
    cast(e, "object:undergrowth")
    s.positions[man] = (1, 7)
    got = [r for r in s.tick_standing(1) if r.get("ref") == man]
    asked = [r for r in got if r["kind"] in ("damage", "ward_saved")]
    assert asked, "the woodcutter stood in the fire and nothing was asked"
    assert {r.get("source") for r in asked} <= {"burning brush", "smoke"}
    # Anything else is what the burning did to him (a hit-point state), said from the row.
    assert all(r.get("from") in ("burning brush", "smoke") for r in got
               if r["kind"] == "condition")


def test_i3_the_awnings_burn(worlds):
    """The awnings the flame licked, with no consequence: a canvas thing lying in the cone
    is flammable by the CRB's own list ("Fire might do full damage against parchment,
    cloth"), and lit, it stands as a burning patch with its ward."""
    s, e, _ = forest(worlds)
    s.grid.difficult = set()
    s.place_prop("a canvas awning", at=s.at, square=(2, 7))
    out = cast(e, "object:a canvas awning")
    caught = out.effects[0]["caught_objects"]
    assert {"kind": "prop", "name": "a canvas awning", "burns": True} in caught
    assert [w.spec["what"] for w in fires(s)] == ["a canvas awning"]


# --- how long it stands -----------------------------------------------------------------------

def test_i3_a_fire_outlives_the_fight_and_burns_out_on_the_clock(worlds):
    """"A fire lit outside a fight must outlive that" (docs/design-e-magic.md §6): the end
    of a fight wiped every manifestation, so brush lit in a skirmish went out the moment the
    last blow landed. It stands now, and expires in minutes when time passes — the Q33
    lifetime, 2d4 × 10, so never past eighty."""
    s, e, _ = forest(worlds)
    cast(e, "object:undergrowth")
    s.end_encounter()
    assert len(fires(s)) == 2 and len(s.manifests) == 2
    assert (1, 7) in s.grid.obscuring, "the smoke's concealment went with the fight"
    s.advance(81)
    assert not fires(s) and not s.manifests
    assert (1, 7) not in s.grid.obscuring


def test_i3_a_fight_still_takes_what_it_conjured(worlds):
    """What a fight conjures goes with it (item 28): a fog cloud without a hazard row is
    lifted at the end, as before, while the fire beside it stays."""
    from rules.engine import Manifestation

    s, e, _ = forest(worlds)
    cast(e, "object:undergrowth")
    s.place(Manifestation(what="fog", terrain="obscuring", squares=[(10, 10)],
                          rounds_left=100))
    s.end_encounter()
    assert [m.what for m in s.manifests] == ["burning undergrowth", "smoke"]
    assert (10, 10) not in s.grid.obscuring


def test_i3_a_fire_does_not_follow_the_party(worlds):
    """A fire burns where it was lit. Its squares are the old place's map; left standing,
    they would burn whoever stood on the same numbers in the next place."""
    s, e, _ = forest(worlds, fight=False)
    e._battle_joined = False
    cast(e, "object:undergrowth")
    assert fires(s)
    e._journeyed = ""
    e.run(e.validate([{"op": "travel", "actor": "pc", "because": "t",
                       "params": {"biome": "urban"}}], origin="author:test"))
    assert not fires(s) and not s.manifests


# --- the brief --------------------------------------------------------------------------------

def _ctx(worlds, s):
    return brief_mod.BriefContext(
        world=worlds, scene=s, location=None, here=None, known=(), recent_events=None,
        recent=None, secret=False, turn=1, names_for=None, absent="", buying="",
        reading=None, player_text="")


def test_i3_the_brief_says_what_is_burning(worlds):
    """The next beat's brief said nothing of the fire, and the prose stood the party in a
    quiet wood. One line while it burns, in words: no minutes, no squares, no compass."""
    s, e, _ = forest(worlds)
    assert burning.section(_ctx(worlds, s)) == ("", {})
    cast(e, "object:undergrowth")
    text, facts = burning.section(_ctx(worlds, s))
    assert text == ("  BURNING HERE (fact): the undergrowth nearby is alight, and smoke "
                    "drifts from it.")
    assert facts == {"fires": [{"what": "undergrowth", "smoke": True}]}
    assert not any(ch.isdigit() for ch in text)
    s.advance(81)
    assert burning.section(_ctx(worlds, s)) == ("", {})


def test_i3_the_burning_member_is_registered_in_the_place_slot():
    assert "burning" in [brief_mod.short_name(m) for m in brief_mod.registered("place")]


def test_i3_the_canopy_burns_overhead_and_lays_no_smoke_on_the_ground(worlds):
    """Up into the canopy (Q32: its underside at 10 ft): the canopy burns and its smoke
    rises — none is laid on the ground under it."""
    s, e, _ = forest(worlds)
    s.grid.difficult = set()
    out = cast(e, "dir:up")
    assert out.effects[0].get("no_victim")
    assert [w.spec["hazard"] for w in fires(s)] == ["burning-brush"]
    text, _ = burning.section(_ctx(worlds, s))
    assert "the canopy overhead is alight." in text
    assert areas.CANOPY_FROM == 2
