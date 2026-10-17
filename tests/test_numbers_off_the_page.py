"""No number the engine rolled or dealt reaches the narrated page.

Measured live 2026-10-17 on the integration branch (free narrator, gemma-4-12B): "I stab
the one behind the bar with my dagger", tell "Kesst Vayr hits the one behind the bar with
the dagger for 5 piercing." The beat left the blow off, the blow pass (`_show_blows`)
handed the engine's line to the model as the deed to write, and the page shipped "You
drive your dagger into the man behind the bar, piercing his flesh for 5 damage."
`play.views.plain_tell` takes off a tell's roll arithmetic and keeps a damage amount on
purpose (the narrator-down fallback, `test_the_players_own_damage_survives`); a line
written INTO prose keeps neither (`narration.page_line`), and the groom's last step on
every door takes off any number this turn's outcome records carry
(`narration.strip_turn_numbers`) — compared with the records, never read off the page.
"""
from __future__ import annotations

from gm import narration
from rules.engine import Outcome

from _a_truth import MARKET, scene_at

TELL = "Kesst Vayr hits the one behind the bar with the dagger for 5 piercing."
# The resolution row of the live turn, as the turn log holds it (rolls trimmed to what the
# guard reads).
HIT = {"intent_id": "i1", "op": "attack", "status": "resolved",
       "rolls": [{"label": "Attack with dagger", "faces": [11], "natural": 11, "total": 14},
                 {"label": "Damage (dagger)", "faces": [4], "total": 5}],
       "dc": {"value": 15}, "verdict": "hit",
       "effects": [{"ref": "c8", "kind": "damage", "amount": 5, "type": "piercing",
                    "hp_after": 12, "hp_max": 23}],
       "tell": TELL, "actor": "pc"}
SHIPPED = ("You drive your dagger into the man behind the bar, piercing his flesh for 5 "
           "damage. The blade finds the gap in his leather jerkin and sinks deep into the meat "
           "of his shoulder. Do you turn to face the second man or move for the exit?")


def test_an_engine_line_written_into_prose_carries_no_number():
    assert narration.page_line(TELL) == (
        "Kesst Vayr hits the one behind the bar with the dagger.")
    assert narration.page_line(
        "the one behind the bar hits Kesst Vayr with the sap for 1 non-lethal bludgeoning "
        "(1, non-lethal now 5).") == "the one behind the bar hits Kesst Vayr with the sap."
    assert narration.page_line(
        "the one behind the bar's attack with the sap misses Kesst Vayr (7 against AC 15).") \
        == "the one behind the bar's attack with the sap misses Kesst Vayr."


def test_the_live_beat_loses_its_number_and_keeps_its_sentence():
    out, removed = narration.strip_turn_numbers(SHIPPED, [HIT])
    assert removed == ["for 5 damage"]
    assert out.startswith("You drive your dagger into the man behind the bar, piercing his "
                          "flesh. The blade finds the gap")
    assert not any(ch.isdigit() for ch in out)


def test_numbers_the_engine_did_not_roll_are_the_pages_own():
    """A price, a count and a line of speech are left: only the turn's own roll faces,
    totals, DC, margin and damage amounts are taken, and only wrapped as the engine wraps
    them ("for 5", "against AC 15", "5 damage")."""
    for page in ("It cost 12 sp.", "The 3 men at the door gasp.",
                 "\"I'll pay 5 for it,\" he says."):
        assert narration.strip_turn_numbers(page, [HIT]) == (page, [])


def test_a_number_that_cannot_be_lifted_out_takes_its_sentence():
    page = "He takes 5 points of damage. You step back."
    out, removed = narration.strip_turn_numbers(page, [HIT])
    assert out == "You step back." and removed == ["He takes 5 points of damage."]


def test_every_door_groom_takes_the_number_off_last():
    agent, _ = scene_at(MARKET)
    out, notes, _ = agent._groom(SHIPPED, outcomes=[Outcome(**{
        k: HIT[k] for k in ("intent_id", "op", "status", "effects", "tell")})],
        rewrite=False, claims=False, hand_back=False)
    assert "5" not in out and "piercing his flesh" in out
    assert any(n.startswith("a number on the page") for n in notes)


def test_the_blow_lines_the_backstops_write_carry_no_number():
    """`_blows_from` feeds `right_hands`, `cut_premature_blows` and the blow pass."""
    agent, _ = scene_at(MARKET)
    o = Outcome(intent_id="i1", op="attack", status="resolved", tell=TELL)
    o.rolls = [{"label": "Attack with dagger", "visibility": "player", "total": 14}]
    lines = agent._blows_from([o])
    assert lines and not any(ch.isdigit() for ch in lines[0]["tell"])
