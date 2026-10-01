"""Item 11 of docs/playtest-2026-09-30.md: "the stranger Veil" and "the Great the stranger".

Measured:
  * Sam's save (2026-09-30): the Velvet Veil, a place the player founded, was printed
    "the stranger Veil" twice. `_known_names` held the world's entities and none of the
    engine's own places, so "Velvet" read as invented; `unname_strangers`'s place rule
    needed the preposition directly before the name, so "of the Velvet" was no place.
  * tests/replay/2026-09-25-town-tags-retag-gemma4-12b.jsonl.gz: "the High Houses and
    the Great Cathedral" shipped as "the Great the stranger", six copies across the
    recording's transcripts.
  * The replay corpus (tests/replay/baseline.json): 7 strikes became 4. The three gone
    were all garbage — "the lower veins of the stranger" for the Iron-Vein Ridge, and
    "the High the stranger" for the High Reach.
"""
from __future__ import annotations

import gzip
import json
from pathlib import Path

from gm import narration
from gm.checks._page import page_sentences

from _a_truth import MARKET, scene_at

RETAG = Path(__file__).parent / "replay" / "2026-09-25-town-tags-retag-gemma4-12b.jsonl.gz"

VEIL = ("The woodsmoke and the heavy, sweet musk of bodies huddled together in the heat "
        "hang thick in the air of the Velvet Veil. This tavern, a squat, leaning "
        "structure of lashed-together beams, sits tucked away from the main roads.")


def test_the_velvet_veil_keeps_its_name_even_unknown():
    """With nothing known, "Velvet" is invented by the detector's lights; inside the
    capitalised phrase "the Velvet Veil" it is a named place and is left as written."""
    out, struck = narration.unname_strangers(VEIL, set())
    assert out == VEIL and struck == []


def test_the_great_cathedral_of_the_retag_recording_is_never_half_unnamed():
    """6 copies of "the Great the stranger" in the 2026-09-25 retag recording. The line is
    the recording's own prose; with nothing known the old rule produced the garble."""
    rows = [json.loads(line) for line in gzip.open(RETAG, "rt", encoding="utf-8")]
    raw = next(c["raw"] for r in rows for c in r["calls"] if "Great Cathedral" in c["raw"])
    text = json.loads(raw)["narration"] if raw.lstrip().startswith("{") else raw
    out, _ = narration.unname_strangers(text, set())
    assert "Great the stranger" not in out and "the Great Cathedral" in out
    assert "the High Houses" in out


def test_a_name_inside_a_place_phrase_after_a_preposition_is_not_a_person():
    for text in ("This is deep-vein stuff, pulled from the lower veins of the Iron-Vein "
                 "Ridge. It is stubborn work.",
                 "'North of the gates is the High Reach,' he says, his voice low."):
        out, _ = narration.unname_strangers(text, set())
        assert "the stranger" not in out and "the onlooker" not in out


def test_a_title_and_a_name_are_one_invented_person():
    """Never "Captain the stranger": the phrase goes whole."""
    out, _ = narration.unname_strangers("She nods to Captain Vorgath and waits.", set())
    assert out == "She nods to the stranger and waits."
    # A sentence's first word is capitalised whatever it is, and is not part of a name.
    out, _ = narration.unname_strangers("Rain falls. Yesterday Vorgath came by.", set())
    assert "Yesterday" in out and "Vorgath" not in out


def test_known_names_include_the_engines_own_places():
    """A founded place, the market's counters and the exits row's destinations are names
    the narrator is entitled to: the engine made them."""
    agent, _ = scene_at(MARKET)
    scene = agent.engine.scene
    scene.founded.append({
        "id": f"{scene.at}/the-velvet-veil", "name": "the Velvet Veil", "about": "",
        "terrain": "urban", "exits": [], "described_only": False, "within": "",
        "parent": scene.at, "owner": "", "origin": "found", "kind": "tavern"})
    known = agent._known_names()
    assert "the Velvet Veil" in known
    assert set(agent._place_names()) <= known
    from rules import market

    labels = {c.label for c in market.counters(agent.world.get(scene.location_id))}
    assert labels and labels <= known
    assert narration.invented_names(VEIL, known) == []


def test_the_sentence_the_un_namer_reads_is_unchanged_on_the_page():
    """The phrase rule changes no sentence boundaries: the beat splits as it did."""
    out, _ = narration.unname_strangers(VEIL, set())
    assert [s for s, _ in page_sentences(out)] == [s for s, _ in page_sentences(VEIL)]
