"""Every person the scene makes has a face that is theirs.

Reported 2026-09-23 with the beat on screen, the sixth orc in a row described as
"Powerfully built, prominent lower tusks, thick hide that resists minor scarring":

    "this is the description of every person who is an orc. descriptions should be
    detailed and unique when possible."

Measured on that save: eight people in the scene, six of them carrying that one sentence
word for word. `play.races` ships ONE body line for the Orc (and for most peoples), and
`names.appearance_for` had nothing but that line and the occasional second one to draw
on — its own docstring promised "two people of one people do not read as twins", and
with one line there was no way to keep it.
"""
from __future__ import annotations

from gm import narration
from rules import faces, names
from world.loader import load_cached

WORLD = load_cached("fixtures/aurvantis-campaign.json")
VORMOOR = next(s["id"] for s in WORLD.play["settlements"] if s.get("name") == "Vormoor")
ORC = next(r for r in WORLD.play["races"] if r.get("name") == "Orc")


class TestTheMeasuredScene:
    def test_eight_people_of_one_people_are_eight_faces(self):
        lines = [names.appearance_for(WORLD, VORMOOR, ORC["people_id"], ref=f"c{i}")
                 for i in range(1, 9)]
        assert all(l.startswith("Orc: ") for l in lines), lines
        assert len(set(lines)) == 8, lines

    def test_the_peoples_own_line_is_still_there(self):
        line = names.appearance_for(WORLD, VORMOOR, ORC["people_id"], ref="c3")
        assert ORC["body"][0] in line

    def test_and_the_backstop_still_reads_it_as_a_sentence(self):
        line = names.appearance_for(WORLD, VORMOOR, ORC["people_id"], ref="c3")
        said = narration.a_face_for("Ashla Ironvale", line)
        assert said.startswith("Ashla Ironvale is an Orc: Powerfully built")
        assert said.count(":") == 1


class TestTheDetails:
    def test_stable_for_a_ref_and_different_across_refs(self):
        a = faces.details_for(ORC["body"][0], "c3", VORMOOR)
        assert a == faces.details_for(ORC["body"][0], "c3", VORMOOR)
        assert a != faces.details_for(ORC["body"][0], "c4", VORMOOR)

    def test_three_things_in_one_sentence(self):
        said = faces.details_for(ORC["body"][0], "c3", VORMOOR)
        assert said.endswith(".") and said[0].isupper()
        assert said.count(";") == 2

    def test_a_feathered_people_is_not_given_hair(self):
        tengu = next(r for r in WORLD.play["races"] if r.get("name") == "Tengu")
        for i in range(40):
            said = faces.details_for(tengu["body"][0], f"c{i}", VORMOOR).lower()
            assert "hair" not in said and "shaved head" not in said, said

    def test_nobody_behind_the_face_means_the_peoples_line_alone(self):
        assert faces.details_for(ORC["body"][0], "", VORMOOR) == ""
        assert names.appearance_for(WORLD, VORMOOR, ORC["people_id"]) == \
            f"Orc: {ORC['body'][0]}"
