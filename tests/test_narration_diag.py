"""The narration diagnosis bench's attribution (tools/narration_diag/attribute.py).

The 2026-11-02 read of two player reports found at least 7 of 37 shipped slips were written
by our own repairs, not the model — and found it only by reading every slot draft beside
its page by hand. These pin the mechanical version of that read: a sentence is traced to the
slot that wrote it, to the repair that changed it, and an error to whichever of the two
wrote the words it quotes."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools" / "narration_diag"))

import attribute as A  # noqa: E402

SLOT = "You snatch the silver bracelet from the tray and slip it into your pocket."
REPAIRED = "You fail to snatch the silver bracelet from the tray."


def _rec(page: str) -> dict:
    return {
        "job": "base|theft|r1", "line": "I snatch the bracelet", "cond": "base",
        "tells": [{"op": "give", "status": "resolved",
                   "tell": "Ana takes the silver bracelet from Bel, who did not hand it over."}],
        "beats": [{"who": "player", "text": "I snatch the bracelet"},
                  {"who": "gm", "kind": "setup", "text": page}],
        "trace": {
            "pc": "Ana",
            "asks": [{"key": "fact1", "redo": "", "text": SLOT + " Bel gasps."}],
            "planned": [{"slots": [{"key": "fact1", "say": "Show the player doing it.",
                                    "tells": ["Ana takes the silver bracelet from Bel."],
                                    "wrote": SLOT + " Bel gasps."}],
                         "plan_user": "THE SCENE: a market with a tray.",
                         "plan_system": "", "remade": []}],
            "changes": [{"start": 5, "end": 6, "depth": 3,
                         "fn": "GMAgent._repair_outcome_claims",
                         "before": SLOT + " Bel gasps.", "after": REPAIRED + " Bel gasps."}],
            "chats": [], "bestof": []},
    }


def test_a_sentence_the_slot_wrote_is_the_slots():
    t = A.Turn(_rec(SLOT + " Bel gasps. What do you do?"))
    pv = t.provenance("Bel gasps.")
    assert pv["writer"] == "model: slot first answer" and pv["slot"] == "fact1"


def test_a_sentence_a_repair_rewrote_is_traced_to_the_repair():
    """"The roll succeeded" rewritten into a failure (the attempt repair, 2026-11-02): the
    error's words are the repair's, not the slot's."""
    key = {"D0001": {"job": "base|theft|r1", "item": "theft", "activity": "theft",
                     "rep": 1, "cond": "base"}}
    rec = _rec(REPAIRED + " Bel gasps. What do you do?")
    rows = A.attribute_all(key, {rec["job"]: rec},
                           {"D0001": [("E1", "P1", "You fail to snatch the silver bracelet")]})
    assert rows[0]["writer"] == "repair/backstop: GMAgent._repair_outcome_claims"
    assert rows[0]["slot"] == "fact1"


def test_an_error_in_the_slots_own_words_stays_the_slots_after_an_edit():
    key = {"D0001": {"job": "base|theft|r1", "item": "theft", "activity": "theft",
                     "rep": 1, "cond": "base"}}
    rec = _rec(REPAIRED + " Bel gasps. What do you do?")
    rows = A.attribute_all(key, {rec["job"]: rec},
                           {"D0001": [("E7", "P1", "Bel gasps")]})
    assert rows[0]["writer"] == "model: slot first answer"


def test_an_untold_tell_no_slot_carried_is_the_plans():
    key = {"D0001": {"job": "base|theft|r1", "item": "theft", "activity": "theft",
                     "rep": 1, "cond": "base"}}
    rec = _rec(SLOT + " What do you do?")
    rec["tells"].append({"op": "arrest", "status": "resolved",
                         "tell": "The watch come for Ana: wanted, to be taken in."})
    rows = A.attribute_all(key, {rec["job"]: rec},
                           {"D0001": [("E6", "-", "The watch come for Ana")]})
    assert rows[0]["cause"] == "omission: no slot carried the tell"


def test_scores_read_every_line_shape():
    import tempfile

    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False,
                                     encoding="utf-8") as f:
        f.write('D0001 | none\nD0002 | E5 | P1 | "hands over the coins"\n'
                '`D0003 | Q | P2 | "You. Is held"`\nnoise\n')
    scores, seen = A.load_scores([f.name])
    assert seen == {"D0001", "D0002", "D0003"}
    assert scores["D0002"] == [("E5", "P1", "hands over the coins")]
    assert "D0001" not in scores


def test_a_third_scorer_settles_only_the_beats_two_disagreed_on(tmp_path):
    """The first rerun's two scorers disagreed on 30 of 602 beats (kappa 0.77): the third
    scorer reads those and nothing else, and the final count is theirs only there."""
    import adjudicate as J

    a = tmp_path / "a.txt"
    b = tmp_path / "b.txt"
    c = tmp_path / "c.txt"
    out = tmp_path / "final.txt"
    a.write_text('D0001 | none\nD0001 | P | 3 | ok\nD0002 | E5 | P1 | "pays"\n'
                 'D0002 | P | 2 | x\n', encoding="utf-8")
    b.write_text('D0001 | none\nD0001 | P | 4 | ok\nD0002 | none\nD0002 | P | 3 | x\n',
                 encoding="utf-8")
    c.write_text('D0002 | E5 | P1 | "pays"\nD0002 | E1 | P1 | "the coin"\n',
                 encoding="utf-8")
    assert J.disputed(J._lines(str(a)), J._lines(str(b))) == ["D0002"]
    J.merge([str(a), str(b), str(c), str(out)])
    final = out.read_text(encoding="utf-8")
    assert final.count("D0002 | E") == 2 and "D0001 | none" in final
