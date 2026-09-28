"""The Bobby playtest of 2026-09-28, as evidence the fix pass is measured against.

Every assertion here is about the RECORDED data, not the code: these pass on the code
that produced the defects, and must go on passing after the fixes, because the recording
does not change. The fixes are proven elsewhere by replaying these same beats through the
fixed detectors (docs/fix-plan-2026-09-28.md, gate G2); this file makes sure the corpus
those proofs read carries what docs/playtest-2026-09-28.md says it measured.
"""
from __future__ import annotations

import re

import pytest

import replays

if not replays.available():
    pytest.skip("the Bobby corpus is not on this disk (kept out of the repository; copy "
                "tests/replays/bobby-2026-09-28/ from the main checkout)",
                allow_module_level=True)

MOVES = ("travel", "found", "journey", "venture")


def test_the_corpus_loads_every_turn_and_every_save():
    """13 player lines, 12 planned turns and one Spells-tab cast; the save and its three
    backups."""
    ts = replays.turns()
    assert [t["n"] for t in ts] == list(range(1, 14))
    assert sum(1 for t in ts if t["plan"]) == 12
    assert [t["n"] for t in ts if t["resolution"]] == [13]
    assert all(t["beats"] for t in ts)
    assert [s["file"] for s in replays.saves()] == [
        "bobby.json", "bobby.json.1", "bobby.json.2", "bobby.json.3"]
    assert replays.opening()["text"].startswith("Vormoor rises from the water")


@pytest.mark.parametrize("case_id", [c["id"] for c in replays.cases()])
def test_every_named_case_points_at_a_turn(case_id):
    c = replays.case(case_id)
    assert c["record"]["n"] == c["turn"]
    assert c["why"] and c["g2"]


def test_drenn_spoke_to_you_twice_and_nobody_hailed_you():
    """Item 13: both of Drenn's lines tagged `who: c4, to: you`, and the speech-tag pass
    recorded `hails_tagged: []`, `hails_guessed: []` — both quotes cross a sentence
    boundary ("'You!" ends one), so no single sentence contained a span."""
    c = replays.case("drenn-hails")
    lines = [s for s in replays.said(c["record"]) if s["who"] == c["speaker"]]
    assert len(lines) == 2
    assert all(s["to"] == "you" for s in lines)
    assert lines[0]["line"].startswith("You!")
    tags = c["record"]["speech_tags"]
    assert len(tags) == 1
    assert tags[0]["tagged"] == 2
    assert tags[0]["hails_tagged"] == [] and tags[0]["hails_guessed"] == []


def test_the_watchman_was_owed_his_face_by_the_word_through():
    """Item 4: the mention key was the name's last word, "through". Beats 1 and 2 speak of
    "the watchman" and never say "through"; beat 3 says "the way through" and is the beat
    the face was spliced into."""
    c = replays.case("watchman-face-through")
    assert c["name"].split()[-1] == c["key"]
    word = re.compile(rf"\b{c['key']}\b", re.I)
    for n in (1, 2):
        text = replays.beat_text(replays.turn(n))
        assert "watchman" in text.lower()
        assert not word.search(text), f"beat {n} already says {c['key']!r}"
        assert not any(b.get("added") for b in replays.turn(n)["beats"])
    beat3 = replays.beat_text(c["record"])
    assert "the way through" in beat3
    added = [a for b in c["record"]["beats"] for a in (b.get("added") or [])]
    assert len(added) == 1 and added[0].startswith(c["name"][:1].upper() + c["name"][1:])


@pytest.mark.parametrize("case_id", ["crossroads-refused-but-moved",
                                     "path-away-refused-but-moved"])
def test_every_move_was_refused_and_the_prose_moved_anyway(case_id):
    """Item 17.5: `found` a crossroads / a road, then `travel`, all refused; no move effect;
    the page nonetheless puts the player somewhere new."""
    c = replays.case(case_id)
    moves = [o for o in replays.outcomes(c["record"]) if o["op"] in MOVES]
    assert moves and all(o["status"] == "refused" for o in moves)
    assert not any(e.get("kind") == "biome" for o in replays.outcomes(c["record"])
                   for e in o.get("effects") or [])
    assert c["quote"] in replays.beat_text(c["record"])


def test_leaving_the_village_went_to_the_way_in_and_was_stopped():
    """Item 16: the reading was `leave: outside it`; the plan travelled to the way in; a
    patrol stopped the party; the prose narrated arriving."""
    c = replays.case("leave-village-stopped")
    plan = c["record"]["plan"]
    assert {"act": "leave", "place": "outside it"} in plan["reading"]["actions"]
    travel = [o for o in plan["outcomes"] if o["op"] == "travel"]
    assert len(travel) == 1 and travel[0]["status"] == "resolved"
    effect = travel[0]["effects"][0]
    assert effect["place"].endswith("urban:the-way-in") and effect["met"] == "patrol"
    assert "You get no further." in travel[0]["tell"]
    assert c["quote"] in replays.beat_text(c["record"])


def test_the_forest_was_filed_under_the_village():
    """Item 20: the biome move worked, but the place id is the village's own."""
    c = replays.case("forest-filed-under-vormoor")
    [o] = [o for o in replays.outcomes(c["record"]) if o["op"] == "travel"]
    effect = o["effects"][0]
    village = replays.save("bobby.json")["location_id"]
    assert effect["biome"] == "forest"
    assert effect["place"] == f"{village}~forest:the-approach"


def test_the_watchmans_words_were_booked_as_bobbys():
    """Item 6: a `say` carrying words the player never typed, told as "Bobby speaks"."""
    c = replays.case("watchman-line-booked-as-bobby")
    says = [o for o in replays.outcomes(c["record"]) if o["op"] == "say"]
    assert len(says) == 1
    words = says[0]["effects"][0]["words"]
    assert words.lower() not in c["record"]["player"].lower()
    assert says[0]["tell"].startswith("Bobby speaks")


def test_asking_about_the_girl_spawned_a_girl():
    """Item 5: the interpreter read `talk` to "him"; the injector spawned "girl", engaged."""
    c = replays.case("girl-spawned-from-ask-about")
    plan = c["record"]["plan"]
    assert plan["reading"]["actions"][0]["target"] == "him"
    [spawn] = [i for i in plan["intents"] if i["op"] == "spawn"]
    assert spawn["params"]["name"] == "girl" and spawn["params"]["zone"] == "engaged"
    girl = next(p for p in replays.save("bobby.json")["people"] if p["name"] == "girl")
    assert girl["pronouns"] == "they/them" and girl["zone"] == "engaged"


def test_the_unprepared_cast_was_refused_seven_times_in_silence():
    """Item 21.3: nothing prepared; seven identical legality refusals, a hand-off to the
    second model, and the turn degraded to narration."""
    c = replays.case("unprepared-burning-hands")
    plan = c["record"]["plan"]
    refused = [r for r in plan["rejections"]
               if "[legality]" in r and "did not prepare Burning Hands today" in r]
    assert len(refused) == 7
    assert len(plan["attempts"]) == 7
    assert len({a["model"] for a in plan["attempts"]}) == 2
    assert plan["repairs"] == ["turn degraded to narration after 7 failed attempts"]
    assert [i["op"] for i in plan["intents"]] == ["narrate_only"]
    assert plan["reading"]["actions"] == [
        {"act": "cast", "object": "burning hands", "target": "the tree tops"}]
    # The backup written after that turn: the spell in the book, nothing prepared.
    before = replays.save("bobby.json.3")
    assert before["pc"]["prepared"] == {}
    assert "burning-hands" in before["pc"]["spellbook"]


def test_into_the_tree_tops_was_read_as_a_false_claim():
    """Item 21.5: the nobody-reacts repair took "into the tree tops" as the player claiming
    to produce tree tops."""
    c = replays.case("tree-tops-false-claim")
    repairs = [r for p in c["record"]["prose"] for r in p["repairs"]]
    assert any(r.startswith("nobody-reacts") and "produce a tree tops" in r for r in repairs)


def test_the_spells_tab_burning_hands_reached_nobody():
    """Item 22: /api/cast resolved Burning Hands with `targets: []` and a bare 1d4 = 1; the
    prose burned the man, who is still at full hit points."""
    c = replays.case("spells-tab-no-targets")
    assert c["record"]["plan"] is None
    [o] = replays.outcomes(c["record"])
    assert o["op"] == "cast" and o["status"] == "resolved"
    cast = o["effects"][0]
    assert cast["spell"] == "burning-hands" and cast["targets"] == []
    assert cast["area"] == "cone-shaped burst"
    assert [r["total"] for r in o["rolls"]] == [1]
    assert o["tell"].endswith("1d4 — 1.")
    assert "his face blackened by soot" in replays.beat_text(c["record"])
    man = next(p for p in replays.save("bobby.json")["people"] if p["ref"] == c["victim"])
    assert man["hp"] == man["hp_max"] == 4
    # The player prepared it in the Spells tab between the two casts.
    assert replays.save("bobby.json.2")["pc"]["prepared"] == {"burning-hands": 1}


def test_every_save_records_where_each_person_stands():
    """The people as each save left them, for the arrival-door and face work to compare
    against. Only the people at the party's own place hold a square. Item 14 (Drenn with
    no square while standing beside the player) cannot be shown from these files: all four
    were written after the party had left the market for the forest."""
    for s in replays.saves():
        here = s["at"]
        for p in s["people"]:
            assert set(p) >= {"ref", "name", "at", "zone", "square", "appearance",
                              "described", "pronouns"}
            if p["square"] is not None:
                assert p["at"] == here, (s["file"], p["ref"])
        assert here.endswith("~forest:the-approach")
