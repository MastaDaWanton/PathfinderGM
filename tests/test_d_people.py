"""Lane D, items 5.1–5.3 of docs/playtest-2026-09-28.md: asking about someone is not
addressing them; a person an NPC places elsewhere exists there; a spawn honours the word.

What was measured on the Bobby playtest (tests/replays/bobby-2026-09-28, turns 2–4):

  * "I ask him about the girl in the market." — the reading was right (talk, target
    "him"), and `inject_company`'s regex took "him about the girl in the market" as the
    addressee: a guildhand called *girl* (c2) was spawned, ENGAGED, at the gate — true name
    Korvin Korvath, pronouns they/them, race human, with an Orc face (turn_log 12).
  * The watchman had said "The girl in the market might know…" and "She's in the market,
    near the well". Nothing recorded her; at the market the finder searched
    ["girl", "work:guard", "describ"] — "that the watchman described" read as her trade —
    and missed (`population-miss`).

Every test runs on the three worlds (the `worlds` fixture): nothing here keys on Aurvantis.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

import replays
from gm import interpret, judgement, prompts
from play import aftermath
from rules import population, scope, schemes
from rules.dice import Dice
from rules.engine import Engine, Scene
from rules.sheet import load_pc

WORK_HOUR = 10 * 60


def _town(world):
    """The first settlement, the party at a place that is not the market, mid-morning."""
    row = (world.play.get("settlements") or [])[0]
    s = Scene(location_id=row["id"])
    s.add(load_pc("fixtures/pc-kesst.json"))
    s.clock_minutes = WORK_HOUR
    e = Engine(s, Dice(seed=5), world=world)
    market = schemes._place_for(e, "market", {})
    assert market, f"{world.name}: the first settlement has a market"
    gate = next(p for p in e.places() if p.id != market["id"])
    e.place_party(gate.id)
    population.drain_misses()
    return s, e, market, gate


def _campaign(scene, engine, world):
    return SimpleNamespace(scene=scene, world=world, transcript=[], suggestions=[],
                           engine=lambda: engine)


def _watchman(scene):
    from rules.bestiary import instantiate

    w = instantiate("guildhand", scene=scene, name="the watchman waving traffic through")
    scene.add(w)
    return w


def _beat(scene, engine, world, said, text="", reading=None):
    c = _campaign(scene, engine, world)
    ctx = aftermath.context("beat", "turn", c, engine=engine, text=text, said=said,
                            reading=reading)
    return aftermath.run("beat", ctx), c


# --- 5.1: asking about is not addressing ---------------------------------------------------

ASK_ABOUT = "I ask him about the girl in the market."


def test_asking_him_about_the_girl_spawns_nobody_with_the_reading(worlds):
    """turn_log 12: c2 *girl*, spawned engaged at the gate from "I ask him about the girl
    in the market." The reading (talk, target "him") decides: a pronoun is somebody here."""
    s, e, _m, _g = _town(worlds)
    _watchman(s)
    interpret.remember(ASK_ABOUT, {"question": False, "claims": [], "actions": [
        {"act": "talk", "target": "him", "says": "about the girl in the market"}]})
    assert judgement.inject_company([], ASK_ABOUT, s, worlds) == []


def test_asking_about_spawns_nobody_with_no_reading_either(worlds):
    """With no reading the regex is the fallback, and its capture now stops at the topic
    word: "him about the girl in the market" is "him", and a pronoun makes nobody."""
    s, e, _m, _g = _town(worlds)
    interpret._READINGS.clear()
    for said in (ASK_ABOUT, "I ask the watchman where the girl in the market is.",
                 "I talk to him about the woman at the well"):
        intents = judgement.inject_company([], said, s, worlds)
        assert not any(i.get("op") == "spawn" and i["params"]["name"] in ("girl", "woman")
                       for i in intents), said


def test_the_topic_never_becomes_the_addressee_on_the_replayed_turn():
    """The Bobby turn itself, replayed through the fixed door with its own reading."""
    if not replays.available():
        pytest.skip("the Bobby corpus is not on this disk (kept out of the repository)")
    from world.loader import load_cached

    record = replays.case("girl-spawned-from-ask-about")["record"]
    world = load_cached("fixtures/aurvantis-campaign.json")
    s, e, _m, _g = _town(world)
    _watchman(s)
    reading = {k: v for k, v in record["plan"]["reading"].items()
               if k in ("question", "actions", "claims")}
    interpret.remember(record["player"], reading)
    assert judgement.inject_company([], record["player"], s, world) == []
    # And what the old door made, to name what is gone: a spawn of "girl".
    assert record["plan"]["intents"][0]["params"]["name"] == "girl"


# --- 5.2: the person an NPC places elsewhere exists there ----------------------------------

GIRL_LINE = "The girl in the market might know where the bigger coins are hidden."
SHE_LINE = "She's in the market, near the well. You'd best start moving."


def test_heard_of_is_recorded_at_the_place_heard_from_the_speaker(worlds):
    """Beat 4 of the playtest: the watchman placed "the girl in the market" and nothing was
    recorded. One record now, at the market, heard of and not seen, from the speaker."""
    s, e, market, _g = _town(worlds)
    w = _watchman(s)
    said = [{"who": w.ref, "to": "you", "line": GIRL_LINE},
            {"who": w.ref, "to": "you", "line": SHE_LINE}]
    rows, _c = _beat(s, e, worlds, said, text=" ".join(r["line"] for r in said))
    heard = [r for r in rows if r.get("kind") == "heard-of"]
    assert len(heard) == 1, rows
    rec = s.population[heard[0]["record"]]
    assert rec["spot"] == market["id"] and rec["seen"] is False
    assert rec["heard_from"] == w.ref and heard[0]["from"] == w.ref
    assert "girl" in rec["phrase"] and "market" in rec["phrase"]
    assert "minor" not in rec["life"]["tags"], "Q25: a girl is a young adult by default"
    # Said twice (the pronoun line is hers too): still one person.
    rows, _c = _beat(s, e, worlds, said)
    assert not [r for r in rows if r.get("kind") == "heard-of"]
    assert sum("girl" in r["phrase"] for r in s.population.values()) == 1


def test_a_place_the_town_lacks_makes_nobody(worlds):
    """The engine owns geography: a person placed somewhere this settlement does not have
    is not recorded anywhere."""
    s, e, _m, _g = _town(worlds)
    w = _watchman(s)
    said = [{"who": w.ref, "to": "you",
             "line": "The girl in the glassblowers' quarter might know."}]
    rows, _c = _beat(s, e, worlds, said)
    assert not rows and not s.population


def test_the_players_own_words_and_the_pc_make_nobody(worlds):
    """Only an NPC's line places somebody; the player saying it is a question."""
    s, e, _m, _g = _town(worlds)
    pc = s.pc()
    rows, _c = _beat(s, e, worlds, [{"who": pc.ref, "to": "", "line": GIRL_LINE},
                                    {"who": "you", "to": "", "line": GIRL_LINE}])
    assert not rows and not s.population


def test_heard_of_is_found_on_arrival_and_the_brief_says_so(worlds):
    """The miss ["girl", "work:guard", "describ"]: at the market, "the girl that the
    watchman described to me" is HERE, and the brief's sought line names her."""
    s, e, market, _g = _town(worlds)
    w = _watchman(s)
    _beat(s, e, worlds, [{"who": w.ref, "to": "you", "line": GIRL_LINE}])
    sought = "I head to the market and look for the girl that the watchman described to me"
    # Away from the market she is elsewhere, and where is said. (Asked with the watchman
    # in the room, "…that the watchman described" is read by `scope.in_the_room` as the
    # watchman himself — a word-overlap rule that is not this lane's; the move below
    # leaves him behind, as the playtest's travel did.)
    far = scope.look_for(worlds, "the girl in the market", s, s.location_id)
    assert far["scope"] == scope.ELSEWHERE, far
    assert market["name"] in far["line"], far
    e.place_party(market["id"])
    found = population.find(s, "the girl that the watchman described to me", world=worlds)
    assert found.scope == population.HERE, found
    reading = {"question": False, "claims": [], "actions": [
        {"act": "go", "place": "the market"},
        {"act": "seek", "target": "the girl that the watchman described to me"}]}
    brief = prompts.scene_brief(worlds, s, worlds.get(s.location_id), here=e.here(),
                                known=e.places(), reading=reading, player_text=sought)
    line = next(ln for ln in brief.splitlines() if "CAME LOOKING FOR" in ln)
    assert "girl in the market is here" in line and "she/her" in line
    assert not population.drain_misses()


def test_the_finder_drops_the_that_clause():
    """`population.find` stripped only "who" clauses; "that" and "whom" read as her."""
    from world.loader import load_cached

    world = load_cached("fixtures/aurvantis-campaign.json")
    s, e, _m, _g = _town(world)
    rec = population.note(s, "a girl mending a net")
    assert population.find(s, "the girl that the watchman described").people == [rec]
    assert population.find(s, "the girl whom he mentioned").people == [rec]


def test_the_replayed_watchman_lines_place_the_girl_at_the_market():
    """The Bobby beats themselves (turns 2 and 3), replayed through the step."""
    if not replays.available():
        pytest.skip("the Bobby corpus is not on this disk (kept out of the repository)")
    from world.loader import load_cached

    world = load_cached("fixtures/aurvantis-campaign.json")
    vormoor = world.by_name("Vormoor", kind="CITY").id
    s = Scene(location_id=vormoor)
    s.add(load_pc("fixtures/pc-kesst.json"))
    s.clock_minutes = WORK_HOUR
    e = Engine(s, Dice(seed=5), world=world)
    e.place_party(next(p.id for p in e.places() if "way in" in p.name or "gate" in p.name))
    w = _watchman(s)
    rows = []
    for n in (2, 3):
        beat = replays.turn(n)["beats"][0]
        said = [dict(r, who=w.ref) for r in beat["said"]]
        got, _c = _beat(s, e, world, said, text=beat["text"])
        rows += got
    heard = [r for r in rows if r.get("kind") == "heard-of"]
    assert len(heard) == 1
    assert s.population[heard[0]["record"]]["spot"].endswith("the-market")


# --- 5.3: a spawn honours the word ----------------------------------------------------------

def _spawn(e, name):
    res = e.run(e.validate([{"op": "spawn", "because": "t",
                             "params": {"template": "guildhand", "count": 1, "name": name}}],
                           origin="author:test"))
    out = res.outcomes[0]
    ref = out.effects[0]["actors"][0]["ref"]
    return e.scene.actors[ref], out.effects[0]["actors"][0]


def test_a_spawned_girl_is_she_young_and_of_the_people_her_face_is(worlds):
    """c2: they/them, race human, an Orc face and "old enough to have stopped counting".
    Now: she/her; young; the people whose body the face is drawn from is her people."""
    from rules import faces, person_words

    s, e, _m, _g = _town(worlds)
    girl, row = _spawn(e, "girl")
    assert girl.pronouns == "she/her" and girl.gender == "woman"
    assert row["pronouns"] == "she/her"
    assert row["from_words"]["age"] == "young" and row["from_words"]["minor"] is False
    pid = person_words.people_drawn(worlds, s.location_id)
    if pid:
        assert girl.world_people_id == pid
        people = person_words.people_name(worlds, pid)
        assert girl.heritage == people
        if girl.appearance:
            assert girl.appearance.startswith(f"{people}:"), girl.appearance
    old = [y for i, y in enumerate(faces.YEARS) if i >= 4]
    assert not any(y.lower() in str(girl.appearance).lower() for y in old), girl.appearance


def test_a_spawned_old_man_is_he_and_old(worlds):
    from rules import faces

    s, e, _m, _g = _town(worlds)
    man, row = _spawn(e, "an old man")
    assert man.pronouns == "he/him" and row["from_words"]["age"] == "old"
    if man.appearance:
        assert any(y.lower() in man.appearance.lower()
                   for i, y in enumerate(faces.YEARS) if i in (4, 5, 6)), man.appearance


def test_a_spawn_named_for_nobody_in_particular_keeps_the_old_shape(worlds):
    """A word that says nothing about a person ("thug") emits no new keys (§2.0)."""
    s, e, _m, _g = _town(worlds)
    thug, row = _spawn(e, "thug")
    assert "pronouns" not in row and "from_words" not in row
    assert thug.pronouns == "they/them"


def test_girl_is_a_child_only_when_the_words_say_so():
    """The owner's Q25: "girl" is a young adult unless child, little or kin words say so."""
    from rules import person_words

    assert person_words.from_words("the girl in the market")["minor"] is False
    for child in ("a little girl", "the smith's girl", "his girl", "a girl, a child",
                  "the girl, the baker's daughter"):
        assert person_words.from_words(child)["minor"] is True, child
    # Unchanged: the life tables' boy is a child (tests/test_graphic_narration.py).
    assert person_words.from_words("a boy selling apples")["minor"] is True
