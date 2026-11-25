"""Playtest 2026-11-23, items 1, 2, 13 and the owner's O6: the dark under a ruin, and who
can see in it.

Measured on the owner's save (Shadow, an Aurvantis undine, in the tower NE of Branford):

- #1: every room below the tower's locked trapdoor stood on the ruins' own ground
  (`terrain_of` "ruins", `is_indoors` False), so it was lit by the night sky: six of the
  player's sixteen swings were lost to a 20% starlight miss chance, and the narrator was
  repaired into "a dark, starry sky" over an underground vestibule. Owner, 2026-11-25:
  "yes underground is dark ... make sure the GM notes the total darkness and properly
  acknowledges whether the PC can see."
- #2 / O6: the Undine card states `amphibious` and a swim speed and says "sees clearly
  underwater"; the import gave no sense, `has_state("sense.darkvision")` was False. Owner:
  "if an undine doesn't have darkvision it is an oversight, how could they live underwater
  otherwise." Read by a model at import, validated in code, world-agnostic.
- #13: "/gm I have dark vision dim light doesnt matter to me why did dim light make me
  miss?" was answered "Darkvision ... doesn't give you a bonus to your accuracy" — the rule
  backwards, and the engine's reason (no darkvision) never handed over.
"""
from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from gm import prompts, race_senses
from gm.checks import light_shown as L
from rules import places, races
from rules.activeeffect import ActiveEffect
from rules.bestiary import instantiate
from rules.dice import Dice
from rules.engine import Engine, Scene
from rules.sheet import load_pc

HEX = "5bbd0c40345f~ruins:@hex-m1-1"
TOWER = HEX + "/the-tower"
TOP = TOWER + "/the-top"
NARTHEX = TOWER + "/the-narthex"
MIDNIGHT = 0


def _founded():
    return [
        {"id": TOWER, "name": "the tower", "terrain": "ruins", "origin": "venture",
         "parent": HEX, "exits": []},
        {"id": TOP, "name": "the top", "terrain": "ruins", "origin": "venture",
         "parent": TOWER, "exits": []},
        {"id": NARTHEX, "name": "the narthex", "about": "a vestibule", "terrain": "ruins",
         "origin": "dungeon", "parent": TOWER, "exits": [],
         "dungeon": {"of": TOWER, "role": "entrance", "stock": "empty"}},
    ]


def _board(at=NARTHEX, gap=4, fight=True):
    s = Scene(location_id="5bbd0c40345f")
    pc = s.add(load_pc("fixtures/pc-kesst.json"))
    s.add(instantiate("thug", scene=s, name="the thug"))
    s.founded = _founded()
    e = Engine(s, Dice(seed=5))
    if fight:
        e._ensure_encounter("pc")
    for a in list(s.actors.values()):
        a.at = at
    s.at = at
    s.clock_minutes = MIDNIGHT
    s.positions["pc"] = (2, 10)
    s.positions["c1"] = (2 + gap, 10)
    s.resync_zones()
    s.said = {}
    return s, e, pc, s.actors["c1"]


def _darkvision(actor):
    actor.apply_effect(ActiveEffect(name="Darkvision", kind="effect",
                                    key="sense.darkvision.60", source="the test",
                                    tags=("sense.darkvision.60",)))


# --- #1: below the way down is under the ground -------------------------------------------

def test_a_room_behind_the_way_down_is_dark_and_the_tower_top_is_not():
    """#1: the narthex read the night sky's dim light (a 20% miss chance on six of sixteen
    swings). A dungeon room is under the ground whatever its id's terrain; the tower's own
    top, a venture spot under the sky, keeps the sky."""
    s, e, pc, thug = _board(at=NARTHEX)
    assert s.underground() and s.ambient_light() == "dark"
    assert e._concealment_of(pc, thug) == (50, "darkness")
    s2, *_ = _board(at=TOP)
    assert not s2.underground() and s2.ambient_light() == "dim"


def test_a_dungeon_room_has_a_roof_and_underground_ground():
    """#1: "stacked high toward the open sky" — the room took the ruins' open shape. Its
    Place is the underground shape now, so every reader of the roof says roofed."""
    room = places.from_dict(_founded()[2])
    assert places.is_indoors(room.id, room.terrain, room.shape)
    assert room.shape.about == "close stone, and not much air"
    tower = places.from_dict(_founded()[0])
    assert not places.is_indoors(tower.id, tower.terrain, tower.shape)


def test_blind_in_the_dark_loses_dex_and_two_ac_and_darkvision_takes_it_away():
    """CRB, Vision and Light: in darkness "creatures without darkvision are effectively
    blinded" — Blinded: "-2 penalty to Armor Class, loses its Dexterity bonus to AC". The
    owner, 2026-11-25: combat follows the book; darkvision within its range removes it."""
    s, e, pc, thug = _board(at=NARTHEX)
    assert e.blind_in_the_dark(pc, thug) and e._unseen_attacker(pc, thug)
    assert [m.value for m in e._dark_ac_mods(pc, thug)] == [-2]
    _darkvision(pc)
    assert not e.blind_in_the_dark(pc, thug) and e._dark_ac_mods(pc, thug) == []
    assert e._concealment_of(pc, thug) == (0, "")
    s.positions["c1"] = (16, 10)                    # 70 ft: past the darkvision
    assert e._concealment_of(pc, thug)[0] == 50 and e.blind_in_the_dark(pc, thug)


# --- the page: total darkness said, and whether the player sees in it ---------------------

def _ctx(s, text, *, tells=(), door="turn", outcomes=()):
    return SimpleNamespace(scene=s, text=text, tells=tuple(tells), door=door,
                           outcomes=tuple(outcomes))


def test_a_starry_sky_under_the_ground_is_contradicted_and_cut():
    """#1 (#205 on the transcript): "You fight amidst the rubble and broken walls of the
    narthex under a dark, starry sky." Flagged on any door, darkvision or not."""
    s, e, pc, thug = _board(at=NARTHEX)
    _darkvision(pc)
    text = ("It is pitch dark, and you see the stone in grey. You fight amidst the rubble "
            "under a dark, starry sky. What do you do?")
    found = L.find(_ctx(s, text))
    assert "light-contradicted" in {f.kind for f in found}
    out, notes = L.backstop(_ctx(s, text), text, found)
    assert "starry" not in out and notes


def test_total_darkness_seen_by_darkvision_is_owed_every_beat():
    """The owner: "properly acknowledges whether the PC can see". A quiet beat in the dark
    with darkvision says nothing of the dark: owed, with a grey-sight backstop line."""
    s, e, pc, thug = _board(at=NARTHEX, fight=False)
    _darkvision(pc)
    seen = L.dark_seen(s)
    assert seen and seen["darkvision"] and seen["feet"] == 60
    text = "You step into the narthex and look around. What do you do?"
    found = L.find(_ctx(s, text))
    assert {f.kind for f in found} == {"light-left-off-the-page"}
    out, _ = L.backstop(_ctx(s, text), text, found)
    assert any(line in out for line in L.POOL["gloom:darkvision"])
    line = prompts.light_now(s)
    assert "darkvision" in line and "no colour" in line and "no sky" in line
    assert not any(ch.isdigit() for ch in line)


def test_without_darkvision_the_dark_is_owed_out_of_a_fight_too():
    s, e, pc, thug = _board(at=NARTHEX, fight=False)
    text = "You step into the narthex and look around the carvings. What do you do?"
    assert {f.kind for f in L.find(_ctx(s, text))} == {"light-left-off-the-page"}
    assert "sees nothing at all" in prompts.light_now(s)


# --- #13: the aside reads the engine's reason ---------------------------------------------

def test_the_gm_aside_is_handed_the_players_sight_and_the_reason_for_the_miss():
    """#13: the aside had no sight facts and answered with the rule backwards."""
    from play import gm_answers

    s, e, pc, thug = _board(at=TOP)               # the tower top: night sky, dim
    tell = f"{pc.name} finds nothing there — dim light, 20% miss chance (14)."
    c = SimpleNamespace(scene=s, turn_log=[{"kind": "turn", "outcomes": [{"tell": tell}]}])
    got = "\n".join(gm_answers.sight_facts(c, e))
    assert "no darkvision" in got and f"because {pc.name} has no darkvision" in got
    assert "a target within that range has no miss chance from the light" in got
    _darkvision(pc)
    assert "darkvision out to 60 feet" in "\n".join(gm_answers.sight_facts(c, e))
    s.clock_minutes = 12 * 60                      # noon, no miss: nothing to say
    c.turn_log = []
    assert gm_answers.sight_facts(c, e) == []


def test_poor_light_never_lets_an_unknown_name_past_the_refusal():
    """prove_build on 0.5.1: in the dark, "/gm who is Zorblax Quixbane" skipped the code's
    refusal because the light facts were present, and the model guessed at a nobody. The
    light facts hold the refusal back only for a question that names no one (#13's)."""
    import inspect

    from play import gm_search, views

    assert not gm_search.proper_noun(
        "/gm I have dark vision dim light doesnt matter to me why did dim light make me miss?")
    assert gm_search.proper_noun("/gm who is Zorblax Quixbane")
    src = inspect.getsource(views._ask_the_gm)
    assert "about_sight = bool(sight) and not gm_search.proper_noun(question)" in src
    assert "not crafts and not about_sight:" in src


# --- #2 / O6: senses read from the world's own words -------------------------------------

UNDINE = {"id": "undine", "name": "Undine", "people_id": "p-undine", "size": "medium",
          "speed": "normal", "body": ["Faintly blue-toned skin."],
          "senses": ["Sees clearly underwater.", "Gills at the throat."], "movement": [],
          "about": "From the tidal flats.", "grants": ["amphibious", "move.swim.30"]}


class _World:
    id = "tideworld"
    name = "Tideworld"
    source = "tideworld.json"
    entities = {}
    play = {"races": [UNDINE]}


def _reply(answer):
    return lambda *a, **k: SimpleNamespace(json=lambda: answer)


@pytest.fixture
def benches(tmp_path, settings):
    settings.CAMPAIGN_DIR = str(tmp_path / "campaigns")
    races._READINGS.clear()
    races._CACHE.pop("worlds", None)
    yield tmp_path
    races._READINGS.clear()
    races._CACHE.pop("worlds", None)


def test_a_stated_card_gains_the_senses_its_words_were_read_into(benches):
    """O6: a card that states its tags was read for nothing else, so the undine had no
    darkvision. The model's yes becomes the vocabulary's tag beside the stated ones."""
    before = races.from_world(_World())[0]
    assert "sense.darkvision.60" not in before["tags"]
    said = {"reason": "they live under the water", "sees_in_darkness": True,
            "sees_in_dim_light": False, "keen_scent": False, "senses_without_sight": False}
    got = race_senses.read_world(_World(), "undine", chat=_reply(said), cfg={})
    assert got == {"p-undine": ["sense.darkvision.60"]}
    after = races.from_world(_World())[0]
    assert {"amphibious", "move.swim.30", "sense.darkvision.60"} <= set(after["tags"])
    assert "darkvision 60 ft" in after["traits"]
    # Read once: a second pass asks nothing.
    assert race_senses.read_world(_World(), chat=lambda *a, **k: 1 / 0, cfg={}) == {}


def test_changed_words_are_read_again_and_a_stale_reading_is_not_served(benches):
    """CLAUDE.md: a cache outside the install compares content. A re-exported world whose
    words changed gets no reading until it is read again."""
    said = {"reason": "", "sees_in_darkness": True, "sees_in_dim_light": False,
            "keen_scent": False, "senses_without_sight": False}
    race_senses.read_world(_World(), chat=_reply(said), cfg={})

    class Reworded(_World):
        play = {"races": [{**UNDINE, "senses": ["They keep to the shallows by day."]}]}

    assert "sense.darkvision.60" not in races.from_world(Reworded())[0]["tags"]
    row = races.sense_sources(Reworded())[0]
    assert races.senses_read(row["world"], row["key"], row["words"]) is None


def test_the_reply_is_validated_in_code(benches):
    """No model writes a tag: a reply missing an answer is no reading (nothing stored, so
    the next load asks again), and only the vocabulary's tags are ever kept."""
    assert race_senses.read("Undine", "x", chat=_reply({"reason": "", "sees_in_darkness":
                                                        "yes"}), cfg={}) is None
    assert race_senses.read_world(_World(), chat=_reply({"reason": ""}), cfg={}) == {}
    assert races.valid_senses(["sense.darkvision.120", "move.fly.30", "sense.scent"]) \
        == ["sense.scent"]
    path = races._readings_path()
    races.remember_senses("tideworld", "p-undine", "w", ["sense.darkvision.60", "bogus"])
    rows = json.loads(path.read_text(encoding="utf-8"))
    assert rows["version"] == races.SENSE_READING_VERSION
    assert rows["readings"]["tideworld/p-undine"]["tags"] == ["sense.darkvision.60"]


def test_an_existing_character_gains_darkvision_with_nothing_written_on_it(benches,
                                                                         monkeypatch):
    """O6: "Shadow's save must gain darkvision without a new character." The race is read
    live (`Actor._race_doc` -> `world_shared`), so a reading that lands changes the next
    `has_state` with the save untouched."""
    import play.library as library

    monkeypatch.setattr(library, "world", lambda key: _World() if key == "tideworld" else None)
    pc = load_pc("fixtures/pc-kesst.json")
    pc.race, pc.race_world = "undine", "tideworld"
    assert not pc.has_state("sense.darkvision")
    said = {"reason": "", "sees_in_darkness": True, "sees_in_dim_light": False,
            "keen_scent": False, "senses_without_sight": False}
    race_senses.read_world(_World(), "undine", chat=_reply(said), cfg={})
    assert pc.has_state("sense.darkvision") and pc.eyes()["darkvision"] == 60
