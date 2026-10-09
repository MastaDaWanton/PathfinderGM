"""The deeds catalogue (content/rules/deeds.json) and the carcass rule, against the
owner's answers of 2026-10-08 (the end of docs/leatherworking-questions.md) and the shipped
bestiary. docs/deeds-plan.md §7, §8, §10.
"""
from __future__ import annotations

import re
from pathlib import Path

from rules import bestiary, deeds


def test_every_row_is_small_signed_and_sourced():
    """A deed is a small number: most acts +-1, the deliberate harms and the life saved
    +-2, nothing past 5 (the owner: "most actions should only have a small impact").
    Every row says where its number comes from, so a retune knows what it overrides."""
    rows = deeds.rows()
    assert len(rows) == 18, sorted(rows)
    for tag, row in rows.items():
        assert tag.startswith("deed."), tag
        assert -5 <= row["value"] <= 5, tag
        assert row["source"].strip() and row["said"].strip(), tag
    small = [t for t, r in rows.items() if abs(r["value"]) <= 1]
    assert len(small) >= len(rows) * 2 // 3, "most acts are +-1"
    assert sum(1 for r in rows.values() if r["value"] < 0) == 11
    assert sum(1 for r in rows.values() if r["value"] > 0) == 6


def test_the_owners_answers_are_the_rows():
    """The owner's answers, 2026-10-08: murder stays -5 in all (1); evil and good spells
    -1/+1, each kind once a game day (2); an accident's harm is nothing (plan §8.3); the
    seven words and the plan's cut-offs (5)."""
    rows = deeds.rows()
    assert rows["deed.violence.unprovoked"]["value"] + rows["deed.kill.unprovoked"]["value"] == -5
    assert (rows["deed.spell.evil"]["value"], rows["deed.spell.good"]["value"]) == (-1, 1)
    assert rows["deed.spell.evil"]["gate"] == rows["deed.spell.good"]["gate"] == "day"
    assert rows["deed.violence.accident"]["value"] == 0
    assert rows["deed.kill.accident"]["value"] == -1
    assert all(rows[t]["gate"] == "none" for t in rows if t.startswith("deed.kill."))
    words = [b["word"] for b in deeds.bands()]
    assert words == ["Cruel", "Callous", "Rough-handed", "Unremarkable", "Decent", "Kind",
                     "Selfless"]
    cuts = {-31: "Cruel", -30: "Cruel", -29: "Callous", -10: "Callous", -9: "Rough-handed",
            -3: "Rough-handed", -2: "Unremarkable", 0: "Unremarkable", 2: "Unremarkable",
            3: "Decent", 9: "Decent", 10: "Kind", 29: "Kind", 30: "Selfless", 99: "Selfless"}
    for total, word in cuts.items():
        assert deeds.word_for(total) == word, total


def test_the_history_lines_read_as_sentences():
    """Every row's line renders with its blanks filled and none left showing — the
    page reads "Took an apple from the fruit seller without asking", never a brace."""
    for tag, row in deeds.rows().items():
        line = deeds.said_of({"tag": tag, "subject_name": "fruit seller", "what": "an apple"})
        assert "{" not in line and "}" not in line, tag
        plain = deeds.said_of({"tag": tag, "subject_name": "Hemmet", "what": ""})
        assert "{" not in plain, tag
        # A row whose line names a thing either always has one (a spell, alms) or says
        # what to write without it.
        if row.get("said_plain"):
            assert "something" not in plain, tag
    assert deeds.said_of({"tag": "deed.theft", "subject_name": "fruit seller",
                          "what": "an apple"}) == \
        "Took an apple from the fruit seller without asking"


def _block(key):
    return bestiary.raw(key)


def test_good_carcasses_counted_on_the_shipped_bestiary():
    """The owner's answer 3: a good outsider is the good subtype OR a printed good
    alignment — 58 outsiders (the subtype alone is 32; three fallen ones print CE and keep
    the subtype). Good dragons by their printed alignment: 9, the faerie dragon, the
    pseudodragon and seven named individuals; no metallic true dragon ships. Counted
    2026-10-08; a change to either count is a change to the bestiary, and says so."""
    blocks = bestiary.imported()
    outsiders = [k for k, v in blocks.items()
                 if deeds.of_carcass(v) == "deed.harvest.good-outsider"]
    dragons = sorted(k for k, v in blocks.items()
                     if deeds.of_carcass(v) == "deed.harvest.good-dragon")
    assert len(outsiders) == 58
    assert len(dragons) == 9 and {"pseudodragon", "dragon-faerie"} <= set(dragons)
    assert deeds.of_carcass(_block("wolf")) is None
    assert deeds.of_carcass(_block("tiefling")) is None


def test_the_carcass_deed_never_reads_the_name():
    """Tags and the printed field only: a renamed good dragon still writes the deed, and a
    wolf called "the angel" does not (plan §10)."""
    renamed = dict(_block("pseudodragon"), name="Mister Biscuits")
    assert deeds.of_carcass(renamed) == "deed.harvest.good-dragon"
    angel = dict(_block("wolf"), name="the angel")
    assert deeds.of_carcass(angel) is None
    from rules.bestiary import instantiate
    from rules.engine import Scene

    s = Scene(location_id="5bbd0c40345f")
    body = s.add(instantiate("pseudodragon", scene=s, name="the little drake"))
    assert deeds.of_carcass(body) == "deed.harvest.good-dragon"


def test_the_native_outsiders_are_never_harvested_like_humanoids():
    """The owner's answer 3b: aasimar, tieflings, sylphs and the other native outsiders
    (225 blocks) are peoples, "banned from skinning like humanoids". The humanoid rule
    alone missed every one: they are outsiders. `never_harvested` is the reader lane C
    asks before it offers a single part."""
    blocks = bestiary.imported()
    native = [k for k, v in blocks.items()
              if str(v.get("creature_type") or "").lower() == "outsider"
              and "native" in str(v.get("subtype") or "").lower()]
    assert len(native) == 225
    assert all(bestiary.never_harvested(blocks[k]) for k in native)
    for key in ("aasimar", "tiefling"):
        assert deeds.never_harvested(_block(key)), key
    assert not bestiary.never_harvested(_block("wolf"))
    assert not bestiary.never_harvested(_block("pseudodragon"))
    humanoids = [v for v in blocks.values()
                 if str(v.get("creature_type") or "").lower() == "humanoid"]
    assert humanoids and all(bestiary.never_harvested(v) for v in humanoids)


def test_printed_alignment_has_one_reader():
    """It lived in rules/engine.py as `_printed_alignment`; the deeds rule needs the same
    answer, and two copies of a rule drift (CLAUDE.md). One reader, in rules/bestiary.py,
    and the engine imports it."""
    engine_src = Path("rules/engine.py").read_text(encoding="utf-8")
    assert "def _printed_alignment" not in engine_src
    assert "from .bestiary import printed_alignment" in engine_src
    # (effectspec's `alignment` keys are a document's `when` condition, not a block read.)
    hits = [p.as_posix() for p in Path("rules").glob("*.py")
            if re.search(r"def \w*alignment\w*\(|_creature_doc\(\)[^\n]*alignment",
                         p.read_text(encoding="utf-8"))]
    assert hits == ["rules/bestiary.py"], hits
    assert bestiary.printed_alignment(_block("pseudodragon")) == "NG"
    assert bestiary.printed_good(_block("pseudodragon"))
    assert not bestiary.printed_good({"alignment": "NG/CN"})
    assert not bestiary.printed_good({})
