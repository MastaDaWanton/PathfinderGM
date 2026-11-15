"""Playtest 2026-11-15, the table's own lane: the home page's count, a feat's name, the
outfit list, the dice mat and the trade counter.

Each test names the item it was found as in the log (C:\\Users\\natha\\pgm-work\\
playtest-2026-11-15.md). The story pane's landing (#66, #87, #91) is in
test_story_keeps_its_place.py, beside the landings it shares a stub with.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
from django.test import Client, override_settings

from pagesource import table_source
from rules.sheet import load_pc

ROOT = Path(__file__).resolve().parents[1]
DICE = (ROOT / "play" / "static" / "js" / "dice3d.js").read_text(encoding="utf-8")


@pytest.fixture
def client(tmp_path):
    from play import campaign as cm

    with override_settings(CAMPAIGN_DIR=tmp_path / "campaigns"):
        cm._LIVE.clear()
        cm.begin_with(load_pc("fixtures/pc-kesst.json"))
        yield Client()
        cm._LIVE.clear()


def test_the_home_page_counts_the_classes_it_offers(client):
    """#1: "Point buy, all eleven classes" beside a forge listing twelve (Blood Bending
    shipped as the twelfth). The number is the class table's length, not a word."""
    from rules import classes

    page = client.get("/").content.decode()
    state = json.loads(re.search(r"const STATE = (\{.*?\});\n", page, re.S).group(1))
    assert state["class_count"] == len(classes.all_classes()) >= 12
    assert "eleven classes" not in page.lower()


def test_no_feat_name_is_two_words_glued_together():
    """#2: "Death Frombelow" beside "Death from Above". The source spreadsheet glued
    three names; the ids keep the glued slug so a saved character still loads."""
    feats = json.loads((ROOT / "content" / "feats" / "feats.json").read_text(
        encoding="utf-8"))["feats"]
    by_id = {f["id"]: f["name"] for f in feats}
    assert by_id["death-frombelow"] == "Death from Below"
    assert by_id["seeds-ofdoubt"] == "Seeds of Doubt"
    assert by_id["wall-offlesh"] == "Wall of Flesh"
    glued = [f["name"] for f in feats
             if re.search(r"\b(?:From|Of)(?:below|doubt|flesh|above)\b", f["name"])]
    assert not glued, glued


def test_the_outfit_list_is_one_case_and_names_every_damage_type():
    """#4: "club", "dagger", "light crossbow" and "padded armour" in lower case among
    "Baston fighting stick". #5: "Kunai 1d4 bludgeoning"; the kunai is B or P (Ranged
    Tactics Toolbox p. 18, as aonprd and d20pfsrd both print it), and the list showed
    only the first of its types."""
    from play import outfit_views

    cat = outfit_views.catalogue()
    rows = [r for kind in ("weapons", "armour", "shields", "gear") for r in cat[kind]]
    lower = [r["name"] for r in rows if r["name"][:1].islower()]
    assert not lower, lower[:10]
    kunai = next(r for r in cat["weapons"] if r["key"] == "kunai")
    assert kunai["type"] == "bludgeoning or piercing", kunai
    club = next(r for r in cat["weapons"] if r["key"] == "club")
    assert (club["name"], club["type"]) == ("Club", "bludgeoning")


def _send_roll() -> str:
    table = table_source()
    at = table.index("async function sendRoll(")
    return table[at:table.index("\n}", at) + 2]


def test_a_throw_still_in_the_air_never_finishes_into_the_next_rolls_mat():
    """#19 and #27. Measured in the page: `land` a Stealth roll, `ask` for Intimidate
    100ms later, and when the Stealth die came down the Intimidate mat read "Cha +1, Dex
    +2, beat 12" with Close where Roll should be. Close shut the mat with nothing sent, so
    the server still waited on the Intimidate roll and the popup came back after a
    reload. `ask` starts a throw of its own now, and `land` writes nothing once the mat
    has moved on (the same test `mark` already made for the verdict)."""
    ask = DICE[DICE.index("function ask(opts)"):]
    ask = ask[:ask.index("var reqSides")]
    assert "throwSeq += 1" in ask
    for name in ("function land(opts)", "function landPercentile(opts)"):
        body = DICE[DICE.index(name):]
        body = body[:body.index("finish(opts")]
        assert "var mine = throwSeq" in body and "if (mine !== throwSeq) return" in body, name


def test_the_mat_says_when_the_turn_waits_on_it():
    """#38: the attack's mat said "Success" and "Close", the damage roll waited for that
    Close, and nothing said so; nine minutes went by. The mat's button reads "Next roll"
    and its note names what is next, from the reply that asked for it."""
    send = _send_roll()
    held = send[send.index("if (state && closing && state.awaiting)"):]
    assert held.index("Dice3D.next(") < held.index("await closing")
    assert 'go.textContent = "Next roll"' in DICE
    assert "showNext();" in DICE[DICE.index("function finish("):DICE.index("function solidFor(")]


def test_a_finished_roll_takes_its_not_yet_done_line_down():
    """#12: after the Stealth roll had resolved the snatch and the walk, "Not yet done:
    snatch a silver bracelet…, walk away quickly without paying" still stood under the
    mat. The reply to the roll ends the turn the line was about."""
    send = _send_roll()
    after = send[send.index('post("/api/roll"'):]
    assert 'classList.contains("hint")' in after[:after.index("attackSounds(")]


def test_leaving_the_keeper_closes_their_counter():
    """#20: the general store's panel was still open after Vesna walked from the market to
    the warrens, where `/api/state` says `merchant: ""` (measured on the playtest's own
    save at beat 16). Any render that shows nobody keeping a counter closes it."""
    table = table_source()
    at = table.index("function reflectMerchant(")
    body = table[at:table.index("\n}", at)]
    assert "!who" in body and "leaveCounter()" in body and 'Shell.show("table")' in body
