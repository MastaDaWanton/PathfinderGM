"""A place made in play stands on its own ground.

The owner, 2026-10-05: "on a mountain still considered farmland". On the save `sammy`,
"i go up the mountain" from the road to Grotburrow planned `found kind="mountain"` (refused:
no such kind of place), then `found name="the mountain"` with no kind, then `travel`.
`places.mint` gave the child its parent's ground, so the id read
`bde94b038cba~farmland:@the-road-to-1cd44ed94902/the-mountain`; the header said "Near
Vormoor. Farmland."; UNDERFOOT said "open, with a wall or a hedge to it"; and the
absent-ground repair, handed "close by, farmland, mountain, desert" as the ground that was
there, wrote boulders "weathered by the desert sun". 'The mountain' read Farmland and the
prose invented a desert.

The rule now (rules/places.py, "a place's own ground"): a place's own words name its ground
from a closed list mapped onto `biomes.BIOMES`; a building, or a name with no ground word,
stands on its parent's — a CircleMUD room carries its own sector type, a sub-hex defaults
to its hex's dominant terrain.
"""
from __future__ import annotations

from gm import prompts
from gm.checks import BeatContext, land_described
from rules import geography, places
from rules.bestiary import instantiate
from rules.dice import Dice
from rules.engine import Engine, Scene
from world.loader import load_cached

AURVANTIS = load_cached("fixtures/aurvantis-campaign.json")
VORMOOR = "bde94b038cba"
GROTBURROW_ROAD = f"{VORMOOR}~farmland:@the-road-to-1cd44ed94902"


class _Quiet:
    """Dice that never meet anything on the way: every d100 check misses."""

    def __init__(self, real):
        self.real = real

    def __getattr__(self, name):
        return getattr(self.real, name)

    def roll(self, notation, modifiers=None, label="", visibility="hidden"):
        if notation == "1d100":
            return self.real.given(100, modifiers, label, notation)
        return self.real.roll(notation, modifiers, label, visibility)


def _party(at_name="", at=""):
    s = Scene(location_id=VORMOOR)
    pc = instantiate("guildhand", scene=s, name="PC")
    pc.kind = "pc"
    pc.hp = pc.hp_base = 60
    s.add(pc)
    e = Engine(s, Dice(seed=3), world=AURVANTIS)
    if at_name:
        at = next(p.id for p in places.home_set(AURVANTIS.get(VORMOOR)) if p.name == at_name)
    e.place_party(at)
    e.dice = _Quiet(e.dice)
    return s, e, pc


def _run(e, pc, op, **params):
    e._journeyed = ""
    return e.run(e.validate([{"op": op, "actor": pc.ref, "because": "t",
                              "params": params}], origin="author:test")).outcomes


def _on_the_road():
    s, e, pc = _party(at=GROTBURROW_ROAD)
    assert s.biome == "farmland"
    return s, e, pc


# --- the owner's turn ----------------------------------------------------------------------

def test_the_mountain_read_farmland_and_the_prose_invented_a_desert():
    """'The mountain' read Farmland and the prose invented a desert. The same two ops the
    owner's plan wrote, from the same road head: the place, the header, the brief and the
    tell all say mountain now."""
    s, e, pc = _on_the_road()
    made = _run(e, pc, "found", name="the mountain", parent="the road to Grotburrow")[0]
    assert made.status == "resolved", made.tell
    assert made.effects[0]["terrain"] == "mountain"
    assert made.effects[0]["setting"] == "outside"
    # The ground in the tell: the narrator is fed tells.
    assert "The ground there is mountain" in made.tell
    went = _run(e, pc, "travel", place="the mountain")[0]
    assert went.status == "resolved", went.tell
    assert s.at == f"{VORMOOR}~mountain:@the-road-to-1cd44ed94902/the-mountain"
    assert s.biome == "mountain"
    # Still outside, still filed under the road it was founded off.
    assert places.setting_of(s.at) == "outside" and places.is_ring(s.at)
    where = geography.where(AURVANTIS, s, e.here())
    assert (where.setting, where.label, where.detail) == ("outside", "near Vormoor",
                                                          "mountain")
    brief = prompts.scene_brief(AURVANTIS, s, AURVANTIS.get(VORMOOR), here=e.here(),
                                known=e.places())
    assert "GROUND at the mountain: mountain" in brief
    assert "UNDERFOOT at the mountain" in brief and "rock" in brief
    assert "hedge" not in brief.split("UNDERFOOT at the mountain", 1)[1].split("\n", 1)[0]


def test_kind_mountain_is_ground_not_a_refused_kind():
    """The owner's plan wrote `kind="mountain"` first and the validator refused it as no
    kind of place; the retry dropped the word that said what the place was. A kind that is
    ground is read through the closed list and stands the place on it."""
    s, e, pc = _on_the_road()
    made = _run(e, pc, "found", name="the high pass", kind="mountain")[0]
    assert made.status == "resolved", made.tell
    assert made.effects[0]["terrain"] == "mountain" and made.effects[0]["is"] == ""
    assert places.ground_kind("mountain") == "mountain"
    assert places.ground_kind("tavern") == "" and places.ground_kind("gizmo") == ""


def test_the_beyond_ground_is_as_far_as_the_world_puts_it():
    """The owner's mountain was a seven-minute walk from the road head. Vormoor's land is
    farmland close by and mountain further out (`geography.land_around`), and a travel onto
    ground beyond is priced at the journey's pace (Q13); a founded place on that ground is
    no nearer."""
    s, e, pc = _on_the_road()
    _run(e, pc, "found", name="the mountain", parent="the road to Grotburrow")
    clock = s.clock_minutes
    went = _run(e, pc, "travel", place="the mountain")[0]
    assert s.clock_minutes - clock >= 60, went.tell


# --- what decides the ground ---------------------------------------------------------------

def test_a_place_whose_words_name_no_ground_stands_on_its_parent_s():
    s, e, pc = _on_the_road()
    made = _run(e, pc, "found", name="the old milestone", kind="milestone")[0]
    assert made.effects[0]["terrain"] == "farmland", made.tell
    barn = _run(e, pc, "found", name="Hobb's lean-to", parent="the road to Grotburrow")[0]
    assert barn.effects[0]["terrain"] == "farmland", barn.tell
    assert "The ground there is" not in barn.tell


def test_a_building_is_not_the_ground_its_name_mentions():
    """"the Forest Inn" is an inn; "the hut on the hill" is a house. Only a name with no
    building in it is read for ground."""
    assert places.ground_named("the Forest Inn") == ""
    assert places.ground_named("the hut on the hill") == ""
    assert places.ground_named("the mine head") == ""
    assert places.ground_named("Grotburrow") == ""          # no burrow inside a name
    assert places.ground_named("the mountain") == "mountain"
    assert places.ground_named("the cave in the hills") == "underground"
    assert places.ground_named("the green hills") == "hills"
    assert places.ground_named("the river") == "coast"      # the bank, not the water
    assert all(b in __import__("rules.biomes", fromlist=["BIOMES"]).BIOMES
               for b in places.PLACE_GROUND.values())


def test_open_ground_founded_in_town_hangs_off_the_way_out():
    """A mountain founded off the market would sit one step from the stalls and parse as
    'under Vormoor' (a long path with no ring at its root). It hangs off the outskirts,
    as a building hangs off the street."""
    s, e, pc = _party(at_name="the market")
    made = _run(e, pc, "found", name="the high peak", kind="mountain")[0]
    assert made.status == "resolved", made.tell
    assert made.effects[0]["parent"] == f"{VORMOOR}~farmland:@the-outskirts"
    assert made.effects[0]["setting"] == "outside"


def test_ground_the_world_does_not_have_is_refused_as_a_travel_onto_it_is():
    """Vormoor has no forest (20.2). Before this, a founded "the woods" stood on farmland;
    reading its own ground must not make it the way into a forest the world lacks."""
    s, e, pc = _on_the_road()
    out = _run(e, pc, "found", name="the woods", parent="the road to Grotburrow")[0]
    assert out.status == "refused" and "no woodland near vormoor" in out.tell.lower(), out.tell
    assert not [p for p in s.founded if p["name"] == "the woods"]


def test_a_venture_keeps_its_seeded_id():
    """Ventures are seeded and saved: the cave off the outskirts has had the same id in
    every save that went in, and a new id would make a second cave next time."""
    s, e, pc = _party(at=f"{VORMOOR}~farmland:@the-outskirts")
    head = places.venture_set(e.here(), "cave")[0]
    assert head.id == f"{VORMOOR}~underground:the-outskirts/the-cave"
    assert places.setting_of(head.id) == "outside"


def test_open_ground_is_never_under_a_town():
    assert places.setting_of(f"{VORMOOR}~mountain:the-glade/the-mountain") == "outside"
    assert places.setting_of(f"{VORMOOR}~underground:the-market/the-sewers") == "under"
    assert places.setting_of(f"{VORMOOR}~ruins:the-temple/the-crypt") == "under"


# --- the narrator ---------------------------------------------------------------------------

def test_the_repair_names_the_ground_underfoot_not_the_whole_land_list():
    """The desert in the owner's beat came from this hint: "Describe the ground that is
    there: close by, farmland, mountain, desert". Stood on the mountain, it names the
    mountain and nothing else."""
    s, e, pc = _on_the_road()
    _run(e, pc, "found", name="the mountain", parent="the road to Grotburrow")
    _run(e, pc, "travel", place="the mountain")
    ctx = BeatContext(
        door="turn", text="The path narrows between dark pines. Rock rises ahead.",
        player_text="", engine=e, scene=s, world=AURVANTIS,
        location=AURVANTIS.get(VORMOOR), reading=None, outcomes=(), tells=(), said=(),
        attribution=None, brief="", brief_facts={}, pull=None, was_at="", acting="",
        turn=1)
    found = [f for f in land_described.find(ctx) if f.kind == "absent-ground"]
    assert found, "pines on a mountain near Vormoor, which has no forest"
    assert "stands on mountain ground" in found[0].fix_hint
    assert "desert" not in found[0].fix_hint
