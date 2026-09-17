"""Prose that says something the engine never did.

Reported from the table 2026-09-17, with the scene list beside the narration:

    "The guard's scream is cut short as the air is forced from his lungs, and he
     collapses forward into the dirt, his sword clattering against a stone."

    In the scene:  guards (c8) — 11/11

He was standing, whole, and had never been touched. The player's own summary of the
turn: "no rolls were done at all and combat never happened." The same session's
`turn_log` shows why — seven attempts rejected with `attack: unknown actor None`, and a
fall back to narration once the model gave up.

**The third law does not cover this.** "The narrator is fed tells and nothing else about
mechanics" stops the narrator being *told* a number. It does not stop it inventing one,
and when a turn produces no tells there is nothing at all to contradict it with.

Detected by comparing the prose against the engine, because every other shape has failed
here: the brief already names who is alive, and telling the model not to kill them is the
instruction-volume trap CLAUDE.md records. `gm/agent.py::_body_count` reads the scene at
the moment the prose is judged, and the finding carries weight 3 so a rewrite that fixes
only this one still counts as an improvement worth keeping.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from gm import narration

ROOT = Path(__file__).resolve().parent.parent

# The guard as the scene actually held him while the prose was killing him.
STANDING = {"guards": {"alive": True, "hurt": False},
            "the crier working through the notices": {"alive": True, "hurt": False}}

REPORTED = ("You strike. The blow is aimed not for a kill, but for the spine, a "
            "calculated strike to shatter his posture and send him to the ground. The "
            "impact is a wet, dull thud that echoes off the surrounding buildings. The "
            "guard's scream is cut short as the air is forced from his lungs, and he "
            "collapses forward into the dirt, his sword clattering against a stone. "
            "The crier's eyes go wide.")


def test_the_reported_narration_is_caught():
    """The turn from the screenshot. One finding, naming the guard and quoting the
    sentence that felled him, so the repair call has something to rewrite rather than a
    complaint to interpret."""
    found = narration.contradicts_state(REPORTED, STANDING)
    assert found, "the guard collapsed at 11/11 and nothing objected"
    name, claim, sentence = found[0]
    assert name == "guards"
    assert claim == "down or dead"
    assert "collapses forward" in sentence


def test_the_scene_name_and_the_prose_name_need_not_match_exactly():
    """The defect that made the first version of this detector useless.

    The scene calls him `guards`; the prose writes "the guard's scream". Compared as
    whole words those are two different people, and the detector passed the death it was
    written for — which is the way a checker fails without ever looking broken."""
    assert narration.contradicts_state("The guard collapses in the dirt.", STANDING)
    assert narration.contradicts_state(
        "The crier slumps against the post, dead.", STANDING)


def test_prose_that_matches_the_engine_passes():
    """A miss, a parry and a step back are what a turn with no damage in it looks like,
    and the narrator must stay free to write them."""
    assert not narration.contradicts_state(
        "You strike, and the guard turns the blow on his vambrace. He gives ground a "
        "step, breathing hard, and the crier watches from the cobbles.", STANDING)


def test_the_prose_is_allowed_to_say_it_once_it_is_true():
    """The finding is a comparison, never a ban. When the engine has actually felled
    him, the same sentence is the right sentence."""
    assert not narration.contradicts_state(
        REPORTED, {"guards": {"alive": False, "hurt": True}})


def test_a_character_may_say_it_out_loud():
    """Speech is stripped from the whole passage before it is split, not sentence by
    sentence. `The crier shouts, "The guard is dead! He collapsed!"` is two sentences to
    the splitter and one utterance to a reader — stripping per sentence let the second
    half through as though the narrator had asserted it."""
    assert not narration.contradicts_state(
        'The crier shouts, "The guard is dead! He collapsed right there!" and backs '
        'away into the crowd.', STANDING)


@pytest.mark.parametrize("said", [
    # Every one of these uses a felling verb about something that is not a person, and
    # a detector that read the verb without asking who it was about would take the
    # narrator's own language away from it.
    "The sound of the city falls away and his voice dies in his throat.",
    "The light collapses to a single point above the stalls.",
    "The bargain is dead and everyone in the square knows it.",
])
def test_the_narrators_own_language_is_left_alone(said):
    assert not narration.contradicts_state(said, STANDING)


def test_an_untouched_body_may_not_be_described_as_bleeding():
    """The softer half. `hurt` is anything that has actually touched them — damage,
    a condition, non-lethal — so a held creature may be described as straining and an
    untouched one may not be described as bleeding."""
    assert narration.contradicts_state(
        "The guard is bleeding from a gash across his brow.", STANDING)
    assert not narration.contradicts_state(
        "The guard is bleeding from a gash across his brow.",
        {"guards": {"alive": True, "hurt": True}})


def test_no_control_characters_survive_in_the_narration_source():
    """A guard on the trap that broke this very detector while it was being written.

    CLAUDE.md: "Bash heredocs mangle backslashes. `\\b` has been written into source as a
    literal backspace byte more than once, silently breaking a regex while tests still
    passed." It happened again on 2026-09-17, in `_sentences_about`: both word
    boundaries arrived as 0x08, the regex compiled, matched nothing, and the detector
    reported the reported bug as fixed.

    Checked across the modules that are mostly regex, because the failure is invisible
    in an editor and in `git diff` alike — only `cat -A` shows it.
    """
    for name in ("gm/narration.py", "gm/judgement.py", "play/player_input.py",
                 "rules/intents.py"):
        raw = (ROOT / name).read_bytes()
        bad = {b for b in raw if b < 9 or 11 <= b <= 12 or 14 <= b <= 31}
        assert not bad, f"{name} carries control bytes {sorted(bad)!r}"


# --- the square that carried on shopping ---------------------------------------------
#
# Reported in the same session, with the scene list beside the prose: `man (c7) - dead`,
# `guards (c8) - dead`, the crowd scattering, and a turn that opened "The market of
# Vyrakon is a cacophony of commerce - the rhythmic thud of hammers on anvils, the sharp
# cries of vendors hawking salt and textiles". The player: "the place was a screaming
# mess and it's doubtful anyone would have been shopping."
#
# The model was not ignorant of it. The same paragraph later names "the fleeing
# bystanders" and "the dying guard" - it opened on a stock description of the location
# and only then remembered the scene, which is why this is a finding about the prose
# rather than a gap in the brief.

TWO_DOWN = {"man": {"alive": False, "hurt": True},
            "guards": {"alive": False, "hurt": True},
            "merchant": {"alive": True, "hurt": False}}

MARKET_DAY = ("The market of Vyrakon is a cacophony of commerce - the rhythmic thud of "
              "hammers on anvils, the sharp cries of vendors hawking salt and textiles, "
              "and the heavy, earthy scent of livestock.")


def test_stock_scene_setting_over_bodies_is_caught():
    kinds = [f.kind for f in narration.review(MARKET_DAY, state=TWO_DOWN).findings]
    assert "ignores-the-dead" in kinds


def test_the_finding_names_the_phrase_and_who_is_down():
    """So the repair call has something to rewrite. A complaint that only says "be more
    aware of the scene" is the instruction-volume trap wearing a different hat."""
    found = next(f for f in narration.review(MARKET_DAY, state=TWO_DOWN).findings
                 if f.kind == "ignores-the-dead")
    assert "cacophony of commerce" in f"{found.detail}"
    assert "guards" in found.detail and "man" in found.detail


def test_an_ordinary_market_keeps_every_one_of_those_words():
    """The finding is the contradiction, never the vocabulary. A square where nothing
    has happened is entitled to be bustling, and a rule that took `hawking` away from a
    market would be worse than the bug it was written for."""
    nobody_down = {"merchant": {"alive": True, "hurt": False}}
    kinds = [f.kind for f in narration.review(MARKET_DAY, state=nobody_down).findings]
    assert "ignores-the-dead" not in kinds


def test_prose_that_has_noticed_the_bodies_passes():
    aware = ("The stalls nearest the rift have gone quiet. A woman drags her child "
             "behind a cart, and the salt merchant stares at the bodies without moving.")
    kinds = [f.kind for f in narration.review(aware, state=TWO_DOWN).findings]
    assert "ignores-the-dead" not in kinds
