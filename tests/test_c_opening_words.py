"""Lane C — what the first screen says (playtest 2026-09-28 items 1 and 4b, and the
owner's opening feedback: describe the room, fix the template's spliced grammar).

Every test records the measurement it prevents. No model is asked; the checks are the
mechanical half that holds the written opening, and the template is the floor.
"""
from __future__ import annotations

import json
import re

from django.test import override_settings

from play import campaign as cm
from play import opening, opening_prose
from rules import geography, places
from rules.sheet import load_pc
from world.loader import load_cached

AURVANTIS = "fixtures/aurvantis-campaign.json"
WORLDS = ("fixtures/aurvantis-campaign.json", "fixtures/pangrella-campaign.json",
          "fixtures/synthetic-world.json")

# The draft of 2026-09-28, as the player read it under a panel saying VORMOOR · VILLAGE.
VORMOOR_DRAFT = ("Vormoor rises from the water on its stilts, a sprawling settlement of "
                 "coral and driftwood, and the city's bustling thoroughfares are already "
                 "full.\n\nYou are Bobby. What do you do?")


# --- item 1: a village is a village --------------------------------------------------------------

def test_the_size_check_records_the_vormoor_draft():
    """Item 1: "a sprawling settlement … the city's bustling thoroughfares" shipped for a
    village, because `problems()` had no size check. It is refused now, hard — a draft
    still wrong after its repair falls to the template, which states the size itself —
    and the repair names the words and the fact."""
    found = opening_prose.problems(VORMOOR_DRAFT, {"Vormoor", "Bobby"}, "Vormoor", "Bobby",
                                   scale="village")
    size = [p for p in found if "sprawling" in p]
    assert size, found
    assert "'city'" in size[0] and "a village of a few hundred people" in size[0]
    assert size[0] in opening_prose.hard_problems(found)
    # A town may have thoroughfares; it may not be "the city".
    assert opening_prose.too_big("the city's walls", "town") == ["the city"]
    assert opening_prose.too_big("busy thoroughfares", "town") == []
    # A world's own name for something is not a claim about size.
    assert opening_prose.too_big("the City Watch came", "village", {"City"}) == []


def test_the_material_says_what_kind_of_place_as_a_fact_to_copy(tmp_path):
    """Item 1: the scale appeared only inside "The template says", the text the model is
    told to rewrite, and the draft made a village a city. The material now carries it as
    a fact to copy, from `places.what_it_is` — the one composer the panel uses."""
    with override_settings(CAMPAIGN_DIR=str(tmp_path / "c")):
        c = cm.new_campaign("mat", seed=9, world_source=AURVANTIS)
    here = opening.situation_for(c)
    text, _allowed = opening_prose.material(c, here, "skeleton")
    scale = places.scale_of(c.location)
    assert (f"What kind of place (a fact; copy it, never make it bigger): "
            f"{c.location.name} is {places.what_it_is(scale)}.") in text


def test_the_example_copies_its_size():
    """The worked example answered "Hollin Stair is a fishing town … Twenty men" from a
    material with no scale line: it demonstrated working the size out. It is a village
    now, its material says so, and its answer copies it."""
    assert "Hollin Stair is a village of a few hundred people" in opening_prose.EXAMPLE["user"]
    answer = json.loads(opening_prose.EXAMPLE["assistant"])["opening"]
    assert answer.startswith("Hollin Stair is a village")
    assert "Twenty men" not in answer
    assert opening_prose.too_big(answer, "village") == []


def test_no_city_words_reach_the_model_for_a_village_or_town(tmp_path):
    """Item 1, measured: the stock "the city's" / "the city" occurs 96 + 12 times in
    Aurvantis's non-city settlements, and the model copied it. None reaches the material
    of a village or a town now, and "Urban Life" is shown as "Daily life"."""
    world = load_cached(AURVANTIS)
    small = [e for e in world.entities.values()
             if (e.scale or "").lower() in ("village", "town")][:12]
    assert small
    for town in small:
        with override_settings(CAMPAIGN_DIR=str(tmp_path / "c")):
            c = cm.new_campaign(f"m-{town.id}", seed=4, world_source=AURVANTIS,
                                start_town=town.id)
        if c.scene.location_id != town.id:
            continue
        text, _ = opening_prose.material(c, opening.situation_for(c), "skeleton")
        assert not re.search(r"\bthe city\b(?!\s+of\b)", text), (town.name, town.scale)
        assert "Urban Life:" not in text


# --- the room ------------------------------------------------------------------------------------

def test_the_architecture_is_what_you_see_not_a_label():
    """The owner, on 2026-09-28's first screen: "among Wooden Khy'vyr-style homes and
    Kelvaxian desert architecture" — "we need descriptions of what the room looks like".
    A style label is dropped; the thing you can see stays."""
    got = opening.built_of("Wooden Khy'vyr-style homes, Kelvaxian desert architecture")
    assert "style" not in got and "architecture" not in got and "Kelvaxian" not in got
    assert "wooden homes" in got
    assert opening.built_of("black basalt blockhouses with narrow windows") == \
        "black basalt blockhouses with narrow windows"
    assert opening.built_of("Towered architecture with ornate windcatchers") == \
        "towered buildings with ornate windcatchers"


def test_every_templated_first_paragraph_describes_the_spot(tmp_path):
    """The template floor carries the spot's own description — its shape (the brief's
    UNDERFOOT), the buildings, the light and the air — in all three worlds, and passes
    the same check a written draft is held to."""
    for path in WORLDS:
        for seed in range(4):
            with override_settings(CAMPAIGN_DIR=str(tmp_path / "c")):
                c = cm.new_campaign(f"room-{seed}", seed=300 + seed, world_source=path)
                cm.open_the_story(c, written=False)
            first = c.transcript[-1]["text"].split("\n\n")[0]
            assert len(opening_prose.physical_detail(first)) >= 3, (path, first)
            assert not re.search(r"-style\b|\barchitecture\b", first, re.I), first


def test_a_first_paragraph_that_names_no_room_is_refused():
    """The check behind the room: a first paragraph with no concrete detail of the spot
    is rewritten, and a style label is named for the repair."""
    bare = ("Mid-morning in Vormoor, among Wooden Khy'vyr-style homes and Kelvaxian "
            "desert architecture.\n\nYou are Bobby. What do you do?")
    found = opening_prose.problems(bare, {"Vormoor", "Bobby", "Wooden", "Khy'vyr",
                                          "Kelvaxian"}, "Vormoor", "Bobby",
                                   room="at the market: stalls and awnings")
    assert any("style as a label" in p for p in found), found
    assert any("shows nothing of the spot itself" in p for p in found), found
    assert all(p in opening_prose.hard_problems(found) for p in found
               if "spot itself" in p or "style" in p)


# --- the template's grammar ----------------------------------------------------------------------

class _Place:
    def __init__(self, facts):
        self.name, self.facts = "Zhilvarnia", facts

    def fact(self, key, default=""):
        return self.facts.get(key, default)


def test_the_template_no_longer_splices_a_sentence_into_a_frame():
    """The owner's screenshot, 2026-09-28: "Zhilvarnia keeps to Council of Elders advises
    on land use and trade" and "The day here is Daily markets, communal gatherings and
    clan rituals". A clause stands alone; a noun phrase gets a frame that fits it, with
    the field's capital lowered."""
    said = opening.the_world_here(_Place({
        "Formal Power": "Council of Elders advises on land use and trade",
        "Daily Norms": "Daily markets, communal gatherings, and clan rituals"}))
    assert "keeps to" not in said and "The day here is" not in said
    assert "Council of Elders advises on land use and trade." in said
    assert "Days here are shaped by daily markets, communal gatherings and clan rituals." \
        in said


def test_the_template_reads_on_every_worlds_first_settlements(tmp_path):
    """The same frames over the three exports' own first settlements: no splice, no
    field capital mid-sentence after a frame, no respelled world name."""
    for path in WORLDS:
        world = load_cached(path)
        towns = [e for e in world.entities.values()
                 if e.kind in opening.SETTLEMENT_KINDS][:6]
        for town in towns:
            said = opening.the_world_here(town, world)
            assert "keeps to" not in said and "The day here is" not in said, said
            m = re.search(r"Days here are shaped by (\S+)", said)
            if m:
                word = m.group(1)
                assert not word[:1].isupper() or word in opening._name_words(world) \
                    or word.split("-")[0] in opening._name_words(world), said


# --- item 4b and the face at first sight ---------------------------------------------------------

def test_the_lead_is_described_at_first_sight(tmp_path):
    """Item 4: the watchman was described on the THIRD beat of talking to him — the
    opening never ran the face check, so the companion it introduced was owed a face on
    turn three. The template now carries the lead's face where they first speak, and
    `described` is set so the later check owes nothing."""
    for path in WORLDS:
        with override_settings(CAMPAIGN_DIR=str(tmp_path / "c")):
            c = cm.new_campaign("face", seed=21, world_source=path)
            cm.open_the_story(c, written=False)
        lead = opening.lead_of(c)
        assert lead is not None and lead.appearance
        text = c.transcript[-1]["text"]
        assert opening_prose.face_given(text, opening.situation_for(c).who, lead.appearance)
        assert lead.described, path


def test_a_role_phrase_is_not_a_name(tmp_path):
    """Item 4b: "the watchman waving traffic through" was the name on the panel and the
    face line. A lead's name is a two- or three-word label with no -ing word in it; the
    phrase lives in `look`."""
    for path in WORLDS:
        for seed in range(6):
            with override_settings(CAMPAIGN_DIR=str(tmp_path / "c")):
                c = cm.new_campaign("label", seed=500 + seed, world_source=path)
            lead = opening.lead_of(c)
            words = lead.name.split()
            assert len(words) <= 3, lead.name
            assert not any(w.endswith("ing") for w in words[1:]), lead.name


def test_a_faceless_draft_is_asked_for_the_face_and_backstopped():
    """The written opening: a soft complaint names the face; if both drafts miss it, the
    world's own face line is added where the lead speaks (`with_face`)."""
    face = "Orc: Powerfully built, prominent lower tusks. A line of blue ink dots."
    text = ("Mid-morning at the market.\n\nThe cage owner pushes through. "
            "“He went down,” the cage owner says.\n\nWhat do you do?")
    found = opening_prose.problems(text, set(), "", "", lead=("the cage owner", face))
    assert any(p.startswith("it never shows what the cage owner looks like") for p in found)
    assert not opening_prose.hard_problems([p for p in found if "looks like" in p])
    fixed = opening_prose.with_face(text, "the cage owner", face)
    assert opening_prose.face_given(fixed, "the cage owner", face)
    assert "tusks" in fixed.split("\n\n")[1]


def test_narrating_past_the_hand_off_is_refused():
    """The cage owner stops where the Heal check begins; a draft that stabilises the
    patient has taken the player's roll from them."""
    start = {"hand_off": {"at": "check", "skill": "heal",
                          "moment": "The cage owner steps back."}}
    crossed = opening_prose.problems("You kneel, and the bleeding stops. What do you do?",
                                     set(), "", "", start=start)
    assert any("narrates past the moment" in p for p in crossed), crossed
    # Offering the act is not doing it.
    fine = opening_prose.problems("You could kneel and stop the bleeding. What do you do?",
                                  set(), "", "", start=start)
    assert not any("narrates past" in p for p in fine)


def test_the_brief_reads_the_other_exports_fact_keys_and_their_size():
    """R0, measured: the brief's fact loop lifted eight keys and never Landscape, Daily
    Life, Customs or Conflict, which the synthetic export (and others) write instead; and
    it showed "Urban Life" and "the city's" on villages."""
    from gm.brief import place_facts

    class Ctx:
        pass

    world = load_cached("fixtures/synthetic-world.json")
    town = next(e for e in world.entities.values() if e.name == "Kestwick")
    ctx = Ctx()
    ctx.location = town
    text, facts = place_facts.section(ctx)
    assert "Daily Life:" in text or "Daily life:" in text
    assert "Customs:" in text
    aur = load_cached(AURVANTIS)
    village = next(e for e in aur.entities.values() if (e.scale or "") == "village")
    ctx.location = village
    text, _ = place_facts.section(ctx)
    assert "Urban Life:" not in text
    assert not re.search(r"\bthe city\b(?!\s+of\b)", text)
    assert geography.display_key("Urban Life") == "Daily life"
