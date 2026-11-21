"""Travel narration with grounded colour (the owner, 2026-11-21: "increase the amount of
fluff in the descriptions"; docs/research/2026-11-21-travel-prose.md).

The travel act's slot is shown THE WAY (`planned.way_lines`): engine-held facts about the
country crossed, turned over between moves; what still repeats is caught in code
(`planned.travel_repeats`); and the hex door's numbers go to the GM's record under the
beat, never the story (`hex_views._tell`). Every engine test runs once
per export (fixes are world-agnostic, 2026-09-28).
"""
from __future__ import annotations

from gm import planned
from play import hex_views
from rules import hexes

from tests.test_hex_travel import _move, _party, quiet_road  # noqa: F401 - the fixture


# The owner's 0.4.4 page (shadow.json, 2026-11-20), the prose and the pasted block.
OWNER_0_4_4 = (
    "You are at the forest 12 miles east of Branford now. The forest 12 miles east of "
    "Branford: Open forest, 12 miles east of Branford, in Faerholt March. Eight hours "
    "through the forest on foot. Looking over the land (27): broken walls show here.")
# The 0.4.8 tell of a move out of a site, from the bench's baseline (travel-bench).
TELL_0_4_8 = (
    "You come out of the ruins. Left behind: the clockwork spy. Eight hours on foot east "
    "through the forest, to the forest 48 miles east of Branford. You set out in the middle "
    "of the day and stop in the evening. At the forest 48 miles east of Branford, a shabti "
    "is near the way; it lets you pass, and you walk on. Looking over the land (Perception "
    "d20 12+16 = 28), nothing new stands out. You gain 125 XP for exploring the forest hex "
    "(125 of 2,000 for level 2).")


def _forced_night(pc_ref="pc", pc_name="Shadow"):
    """The sibling lane's `forced_march` effects (feat/hex-travel-to), one a walker an
    hour, for the five-hour night push the owner's screenshot showed."""
    rows = [{"kind": "forced_march", "ref": pc_ref, "who": pc_name, "ability": "con",
             "hour": h, "extra_hour": h - 8, "dc": 10 + 2 * (h - 9), "total": 15 + h,
             "rolled": 9, "passed": True, "mount": False, "nonlethal": 0, "lethal": 0,
             "conditions": [], "origin": "rule:forced-march"} for h in range(9, 14)]
    rows.append({**rows[-1], "ref": "c2", "who": "Brakka", "hour": 12, "passed": False,
                 "nonlethal": 3, "conditions": ["fatigued"]})
    return rows


def test_a_forced_march_printed_five_constitution_lines_in_the_story(monkeypatch):
    """The owner's screenshot (2026-11-21, feat/hex-travel-to): a forced march printed
    five "Constitution N vs DC M, holds up" lines in the story. The story now holds the
    beat alone and every check rides in the GM's record; and the march is one sentence
    of what it meant, with no figure in it (`march_said`), for the engine's tell."""
    from rules import march_said

    tell = ("Five hours on foot south-east through the grassland, to the grassland 48 "
            "miles east of Branford. You set out in the evening and stop in the dead of "
            "night. " + " ".join(
                f"Hour {w} on the way, a forced march: Shadow Constitution {15 + k} vs DC "
                f"{10 + 2 * k}, holds up." for k, w in enumerate(
                    ("nine", "ten", "eleven", "twelve", "thirteen")))
            + " Looking over the land (Perception d20 7+16 = 23): a cave mouth opens in "
              "the ground to the east.")
    c = _played(monkeypatch, tell, "Your legs burn but carry you on through the dark.")
    story = " ".join(b["text"] for b in c.transcript if b["who"] == "gm")
    assert "vs DC" not in story and "Constitution" not in story and "d20" not in story
    assert c.transcript[1]["record"].count("vs DC") == 5

    line = march_said.said(_forced_night())
    assert line == ("A forced march, five hours past the day's walking: Shadow holds up "
                    "through all of it; Brakka falters in hour twelve and is left "
                    "fatigued.")
    assert not any(ch.isdigit() for ch in line)
    assert march_said.said([{"kind": "hex", "hours": 8}]) == ""


def _played(monkeypatch, tell, closing):
    """The hex door's tail (`hex_views._tell`) over one outcome with this tell, the
    narrator answering `closing`."""
    from types import SimpleNamespace

    from play import craft_views

    class Camp:
        def __init__(self):
            self.transcript, self.history, self.turn_log = [], [], []
            self.scene = SimpleNamespace(pc=lambda: None, clock_minutes=0)

        def save(self):
            pass

    out = SimpleNamespace(tell=tell, status="resolved", as_dict=lambda: {})
    monkeypatch.setattr(craft_views, "_narrate_outcome", lambda *a, **k: closing)
    monkeypatch.setattr(hex_views, "_brief", lambda c: "THE SCENE")
    monkeypatch.setattr("play.history.stamp", lambda c, row: row)
    monkeypatch.setattr("play.views._remember", lambda *a: None)
    c = Camp()
    hex_views._tell(c, SimpleNamespace(outcomes=[out]), "I set out east.")
    return c


def test_the_hex_moves_numbers_go_to_the_gms_record_not_the_story(monkeypatch):
    """The owner, 2026-11-21: numbers and checks go to the GM's section, and the 0.4.4
    page said "12 miles east of Branford" three times, twice in the tell pasted under the
    prose. With a narrated beat the story holds the prose alone; the engine's tell, every
    roll and figure of it, rides under the beat as its record (02-state.js `record`)."""
    c = _played(monkeypatch, TELL_0_4_8, "Eight hours of forest lie behind you.")
    story = [b for b in c.transcript if b["who"] == "gm"]
    assert story[0]["text"] == "Eight hours of forest lie behind you."
    assert story[0]["record"] == TELL_0_4_8
    assert not any(b.get("kind") == "consequence" for b in story)
    assert not any(ch.isdigit() for b in story for ch in b["text"])


def test_with_the_narrator_down_the_engines_lines_are_the_page(monkeypatch):
    """No closing (a model down): the tell is the page, as every door's is; nothing is
    hidden in a record nobody's prose stands over."""
    c = _played(monkeypatch, TELL_0_4_8, "")
    assert [b.get("kind") for b in c.transcript if b["who"] == "gm"][0] == "consequence"


def test_three_consecutive_moves_sharing_one_skeleton_are_caught():
    """The owner's 0.4.4 game: consecutive hex moves came back on one skeleton and one
    stock phrase ("silent monuments" twice in three turns). Caught in code, not asked
    for in the prompt: the shared four-word phrase, the stock phrase, the same opening."""
    one = ("The dense canopy of the Faerholt March looms before you. As you trek through "
           "the open woods, the jagged remains of broken walls rise from the earth, silent "
           "monuments to a forgotten history.")
    two = ("The dense canopy of the forest gives way to open grassland. As you trek "
           "through the swaying grass, broken walls rise in the distance, silent monuments "
           "of an older age.")
    found = planned.travel_repeats(two, one)
    assert any("silent monument" in f for f in found)
    assert any("as you trek through" in f for f in found)
    assert any("opening" in f for f in found)
    assert planned.travel_repeats("Five hours of grass and wind lie behind you.", one) == []


def test_the_way_is_read_off_the_engine_and_turns_over_between_moves(worlds, quiet_road):
    """THE WAY carries the ground crossed every move, and the rest of its material turns
    over (least recently used), so two moves in a row are not shown one set of facts —
    the material is varied at the source rather than by asking for variety."""
    s, e, pc = _party(worlds)
    g = e.hex_world()
    shown = []
    for _ in range(3):
        to = next(h for h in e.hex_reach(g) if hexes.distance(h, e.party_hex(g)) == 1
                  and not g.cell(*h)["town"] and g.cell(*h)["land"])
        out = _move(e, to)
        assert out.status == "resolved", out.tell
        lines = planned.way_lines([out], e, s.said)
        assert lines and lines[0].startswith(
            f"the ground crossed: {g.cell(*to)['ground']}")
        shown.append(tuple(lines[1:]))
    assert len(set(shown)) > 1, shown
    # Nothing the engine does not hold: no number, no refs.
    for lines in shown:
        assert not any(ch.isdigit() for line in lines for ch in line)


def test_the_way_takes_the_place_of_the_see_block_on_the_travel_act(worlds, quiet_road):
    """The see block's "close by" is the nearest town's land, and a hex 48 miles out is
    not close by it; the travel act gets THE WAY instead, and room for it."""
    s, e, pc = _party(worlds)
    g = e.hex_world()
    to = next(h for h in e.hex_reach(g) if not g.cell(*h)["town"])
    out = _move(e, to)
    slots = [{"key": "fact1", "want": planned.FACT_WANT, "say": "", "tells": [out.tell]}]
    assert planned.way_slot(slots, [out], e)
    assert slots[0]["way"] and slots[0]["see"].startswith("THE WAY")
    assert planned.FACT_WANT < slots[0]["want"] <= planned.TRAVEL_CEILING
    assert not planned.way_slot(
        [{"key": "fact1", "want": 220, "say": "", "tells": []}], [], e)
