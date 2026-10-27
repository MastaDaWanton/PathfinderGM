"""Tracking toward what the engine holds, and saying so when it holds nothing (the owner's
report, 2026-10-27, 0.2.21 on Planned narration).

"Finally i have been tracking the caravan but I am seemingly not moving toward the caravan
after the 1st track." What the turn log of that save shows:

  * there was no caravan: the guild clerk's escort job was made up by the narrator over five
    replies, and the engine held no agreement, no caravan and no place for one;
  * row 129, "I look for the caravan I am supposed to guard": the plan's `track` — and the
    beat found "fresh tracks … a caravan has crossed this stretch of earth recently";
  * row 136, "I follow the tracks in search of the caravan": read `follow` (target "the
    tracks", object "the caravan"), which owed no op, so the plan walked the party a quarter
    hour to "the fields" and rolled a bare Survival check;
  * row 146, "I continue to track the caravan": a `track` with no params, which found
    somebody's tracks, called them the caravan's on the page, and moved nobody.

Now a track names what it is after (`quarry`), the engine answers it from what it holds, a
follow walks to where the trail's maker is now, and the plan's own walk for a follow goes.
CircleMUD's `do_track` (tbaMUD src/graph.c) looks the target up world-wide first and answers
"No one is around by that name" with no roll at all.
"""
from __future__ import annotations

from gm import acts_to_ops
from rules import population, tracking

from test_engine_bugs_2026_10_09 import HOUR, KHALMORIN, WORLD, _grasslands

ROW_136 = {"question": False, "claims": [], "actions": [
    {"act": "follow", "target": "the tracks", "object": "the caravan",
     "span": "follow the tracks in search of the caravan"}]}
ROW_146 = {"question": False, "claims": [], "actions": [
    {"act": "track", "object": "the caravan", "span": "continue to track the caravan"}]}


def _track(e, face, **params):
    res = e.run(e.validate([{"op": "track", "actor": "pc", "because": "t",
                             "params": params}], origin="author:test"))
    assert res.awaiting is not None and "Survival" in res.awaiting["label"]
    return e.resume(face)


def _rider(s, place=f"{KHALMORIN}~urban:the-gate"):
    rec = population.note(s, "a lone rider")
    body = population.embody(s, "a lone rider", "guildhand", world=WORLD, rec=rec)
    s.move(body.ref, place)
    s.clock_minutes += 2 * HOUR
    return body


def test_a_quarry_nothing_holds_has_no_trail_and_nothing_to_follow():
    """Row 146: the caravan existed only on the page. The roll is still made (the ground is
    the ground), and the tell says no trail of the caravan crosses it — before any beat can
    lay one. A follow walks nowhere."""
    s, e = _grasslands(717)
    _rider(s)
    at = s.at
    out = _track(e, 18, quarry="the caravan", follow=True).outcomes
    track = out[0]
    assert track.op == "track" and track.effects[0]["quarry"] == {"words": "the caravan",
                                                                   "held": None}
    assert "No trail of the caravan crosses this ground" in track.tell
    assert "there is no trail of the caravan to follow" in track.tell
    assert "go" not in track.effects[0]
    assert [o.op for o in out] == ["track"] and s.at == at


def test_following_a_found_trail_walks_to_where_its_maker_is_now():
    """The trail of somebody the engine holds, read by the roll, is followed to the place
    their own record says they are — the walk next in the queue, the one door walks go by."""
    s, e = _grasslands(717)
    body = _rider(s)
    out = _track(e, 18, follow=True).outcomes
    assert [o.op for o in out][:2] == ["track", "travel"], [o.op for o in out]
    assert out[0].effects[0]["go"] == body.at
    assert f"{body.name}'s trail is followed toward" in out[0].tell
    assert s.at == body.at


def test_a_held_quarry_whose_trail_the_roll_misses_is_not_followed():
    s, e = _grasslands(717)
    body = _rider(s)
    at = s.at
    out = _track(e, 1, quarry="the lone rider", follow=True).outcomes
    assert out[0].effects[0]["quarry"]["held"] == {"ref": body.ref, "name": body.name}
    assert "trail is not to be read from it" in out[0].tell
    assert [o.op for o in out] == ["track"] and s.at == at


def test_a_trail_to_another_settlement_is_a_journey_and_is_said_so():
    s, e = _grasslands(717)
    other = next(x for x in WORLD.play.get("settlements") or [] if x["id"] != KHALMORIN)
    body = _rider(s, place=f"{other['id']}~urban:the-gate")
    at = s.at
    out = _track(e, 18, follow=True).outcomes
    assert "a journey, not a walk" in out[0].tell and body.name in out[0].tell
    assert s.at == at


def test_row_136s_follow_owes_the_track_and_the_plans_walk_to_the_fields_goes():
    """Row 136 owed no op, and the plan walked to "the fields". The follow of a trail owes
    the track, with `follow`, and the plan's walk and its bare Survival check are replaced."""
    s, e = _grasslands(717)
    rows = acts_to_ops.table(ROW_136, s, places=e.places())
    assert [(i["op"], i["params"]) for i in rows[0].intents] == [("track", {"follow": True})]
    plan = [{"op": "travel", "params": {"place": "the fields"}},
            {"op": "check", "actor": "pc", "params": {"skill": "survival"}}]
    notes: list = []
    got = acts_to_ops.apply(plan, rows, ROW_136, s, notes=notes)
    assert [r["op"] for r in got] == ["track"], got
    assert any("follow of a trail" in n for n in notes)


def test_the_quarry_is_the_phrase_the_reader_says_names_the_maker():
    """The reader put "the caravan" in `object` on row 146 and in `object` beside "the
    tracks" in `target` on row 136 (probed live, 2026-10-27). Which phrase names the maker
    is asked, one phrase at a time; with no reader (the suite) no quarry is claimed, and a
    phrase naming somebody the engine holds needs no question."""
    s, e = _grasslands(717)
    asked: list = []

    def ask(span, phrase):
        asked.append(phrase)
        return "the maker" if phrase == "the caravan" else "only the marks"

    rows = acts_to_ops.table(ROW_136, s, places=e.places())
    notes = acts_to_ops.quarries(rows, ROW_136, s, ask=ask, world=WORLD)
    assert rows[0].intents[0]["params"] == {"follow": True, "quarry": "the caravan"}
    assert asked == ["the tracks", "the caravan"] and notes == ["track: after 'the caravan'"]
    rows = acts_to_ops.table(ROW_146, s, places=e.places())
    acts_to_ops.quarries(rows, ROW_146, s, ask=None, world=WORLD)
    assert "quarry" not in rows[0].intents[0]["params"]
    body = _rider(s)
    held = {"question": False, "claims": [], "actions": [
        {"act": "track", "target": "the lone rider", "span": "track the lone rider"}]}
    rows = acts_to_ops.table(held, s, places=e.places())
    asked.clear()
    acts_to_ops.quarries(rows, held, s, ask=ask, world=WORLD)
    assert rows[0].intents[0]["params"]["quarry"] == "the lone rider" and asked == []
    assert tracking.quarry_of(s, "the lone rider", world=WORLD)["ref"] == body.ref
    assert tracking.quarry_of(s, "the caravan", world=WORLD) is None


def test_a_look_for_tracks_then_a_follow_is_one_track_one_roll():
    """Live, 2026-10-27: "I look for tracks of the caravan and follow them" was read
    `track` then `follow`, and the table built two tracks — two d20s for one look. The
    follow rides on the look."""
    s, e = _grasslands(717)
    frame = {"question": False, "claims": [], "actions": [
        {"act": "track", "object": "tracks of the caravan",
         "span": "look for tracks of the caravan"},
        {"act": "follow", "span": "follow them"}]}
    rows = acts_to_ops.table(frame, s, places=e.places())
    built = [i for r in rows for i in r.intents]
    assert [(i["op"], i["params"]) for i in built] == [("track", {"follow": True})]


def test_a_successful_roll_that_found_nothing_is_not_read_as_the_attempt_working():
    """Live, 2026-10-27: Survival 21 against DC 15, and the tell "no trail of the caravan
    crosses this ground". The beat said "you find no tracks of the caravan"; the read
    back's attempts question took the roll's success to mean "the attempt works" and
    repaired the beat into "you find the tracks of the caravan". A track that found
    nothing, or not its quarry, is not asked as an attempt; one that found it is."""
    from gm import beat_verify as bv

    pc = bv.Person("pc", "Borin Achereth", pc=True)

    def track(found, quarry=None):
        eff = {"kind": "tracks", "ref": "pc", "found": found}
        if quarry is not None:
            eff["quarry"] = quarry
        return {"op": "track", "status": "resolved", "verdict": "success", "actor": "pc",
                "because": "t", "rolls": [{"label": "Borin Achereth Survival (tracks)"}],
                "effects": [eff]}

    def asked(*outcomes):
        return bv.attempts_of(bv.Facts(start="the outskirts", end="the outskirts",
                                       places=("the outskirts",), people=(pc,),
                                       outcomes=outcomes))

    rider = {"ref": "c4", "name": "a lone rider", "hours_ago": 1, "here": False}
    assert asked(track([])) == []
    failed = dict(track([]), verdict="failure")
    assert len(asked(failed)) == 1, "a failed roll told as a found trail is still caught"
    assert asked(track([rider], {"words": "the caravan", "held": None})) == []
    assert len(asked(track([rider]))) == 1
    assert len(asked(track([rider], {"words": "the rider",
                                     "held": {"ref": "c4", "name": "a lone rider"}}))) == 1


def test_following_somebody_standing_here_is_not_a_trail():
    """"I follow the guards" with the guards beside you is the thread's, not a track."""
    s, e = _grasslands(717)
    rec = population.note(s, "a lone rider")
    body = population.embody(s, "a lone rider", "guildhand", world=WORLD, rec=rec)
    frame = {"question": False, "claims": [], "actions": [
        {"act": "follow", "target": body.name, "span": f"follow {body.name}"}]}
    rows = acts_to_ops.table(frame, s, places=e.places())
    assert not any(i["op"] == "track" for i in rows[0].intents)
