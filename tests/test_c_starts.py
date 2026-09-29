"""Lane C — where a campaign begins (docs/design-c-starts.md; playtest 2026-09-28 items 2, 3).

Every test here records the measurement it prevents. Engine-side only: no model is asked.
"""
from __future__ import annotations

import collections
import json

import pytest
from django.test import override_settings

from play import campaign as cm
from play import opening
from rules import openings
from rules.sheet import load_pc
from world.loader import load_cached

AURVANTIS = "fixtures/aurvantis-campaign.json"
PANGRELLA = "fixtures/pangrella-campaign.json"
SYNTHETIC = "fixtures/synthetic-world.json"


def _pc(path: str = "fixtures/pc-kesst.json", background: str | None = None):
    pc = load_pc(path)
    if background is not None:
        pc.background = background
    return pc


# --- the draw ----------------------------------------------------------------------------------

def test_start_town_is_not_always_the_last_village():
    """Item 2, measured 2026-09-28: every Aurvantis campaign began in Vormoor — 100% —
    because `starting_place` ranked a templated export by summary length and then by
    reverse alphabetical order, and Vormoor is the last of its sixteen villages. Over a
    thousand story seeds the draw now reaches at least forty towns, and none takes more
    than eight per cent (measured at this commit: all 64, the busiest 3.9%)."""
    world = load_cached(AURVANTIS)
    pc = _pc()
    towns = collections.Counter(
        openings.choose(world, pc, openings.rng_for(seed, "start"))[0].name
        for seed in range(1000))
    assert len(towns) >= 40, len(towns)
    name, most = towns.most_common(1)[0]
    assert most <= 80, (name, most)


BACKGROUNDS = ["", "apprenticed", "stallholder", "caravan-hand", "gate-watch",
               "thief-taker", "exile", "pilgrim", "forager", "household", "guild-clerk",
               "innkeepers-child", "bonesetter", "pit-fighter", "ferryman"]


def test_thirty_seeds_across_three_worlds_reach_five_towns_and_eight_kinds():
    """The G2 gate, checked offline before any Ollama time is spent: thirty seeds reach
    at least five towns and eight kinds of start. The measured cause was twelve starts
    that were one start — every edge "something went quiet" — rolled per NAME. Run per
    world, cycling every background and none, because a start is drawn for a
    background (at this commit: Aurvantis 23 towns / 9 kinds, Pangrella 11 / 8,
    the synthetic world 6 / 9 over thirty full campaigns in `narrator_audit --starts`)."""
    for path in (AURVANTIS, PANGRELLA, SYNTHETIC):
        world = load_cached(path)
        towns, kinds = set(), set()
        for seed in range(30):
            pc = _pc(background=BACKGROUNDS[seed % len(BACKGROUNDS)])
            town, doc = openings.choose(world, pc, openings.rng_for(1000 + seed, "start"))
            assert doc is not None, (path, seed)
            assert openings.fits(world, town, doc, pc), (path, doc["id"], town.name)
            towns.add(town.name)
            kinds.add(doc["kind"])
        assert len(towns) >= 5, (path, sorted(towns))
        assert len(kinds) >= 8, (path, sorted(kinds))


def test_the_name_no_longer_decides_the_start():
    """Item 3, measured: the opening was `1d12` seeded from the slugified character NAME,
    so "masta" always got the step in the sun and "john" the work yard — across 12,000
    names the twelve came up evenly, so it was identity, not weighting. One name over
    fifty story seeds now opens on at least six different starts."""
    world = load_cached(PANGRELLA)
    pc = _pc()
    pc.name = "masta"
    got = {openings.choose(world, pc, openings.rng_for(seed, "start"))[1]["id"]
           for seed in range(50)}
    assert len(got) >= 6, got


def test_the_same_seed_opens_the_same_way(tmp_path):
    """A story seed is a story: the same seed gives the same town, start and lead, so a
    reproducible audit and a replayed bug are possible."""
    with override_settings(CAMPAIGN_DIR=str(tmp_path / "campaigns")):
        a = cm.new_campaign("same-a", seed=424242)
        b = cm.new_campaign("same-b", seed=424242)
    assert a.scene.location_id == b.scene.location_id
    assert a.scene.start["id"] == b.scene.start["id"]
    lead_a = a.scene.people[a.scene.start["slots"]["lead"]].name
    lead_b = b.scene.people[b.scene.start["slots"]["lead"]].name
    assert lead_a == lead_b


def test_an_old_save_reopens_the_legacy_opening_byte_for_byte(tmp_path):
    """A campaign from before start documents has an empty `scene.start`: its opening
    card and situation must be what `opening.roll` always gave it, or an old game's
    situation would change under the player on the next load."""
    with override_settings(CAMPAIGN_DIR=str(tmp_path / "campaigns")):
        c = cm.new_campaign("legacy-kesst", seed=5)
    c.scene.start = {}
    assert opening.situation_for(c) == opening.roll(c.id, c.seed)


def test_a_chosen_start_is_honoured_when_it_fits(tmp_path):
    """The picker's path (owner's answer Q20: built, and labelled not built yet on the
    screen): `begin_with(start_town=, start_id=)` opens there when it fits the character,
    and draws around a choice that does not."""
    world = load_cached(PANGRELLA)
    with override_settings(CAMPAIGN_DIR=str(tmp_path / "campaigns")):
        cm._LIVE.clear()
        c = cm.begin_with(_pc(), start_town="Pangrella", start_id="stop-thief")
        assert c.location.name == "Pangrella" and c.start_id == "stop-thief"
        # The cage is the bonesetter's own start: Kesst (a thief-taker) is drawn around.
        c2 = cm.begin_with(_pc(), start_id="called-to-the-cage")
        assert c2.start_id != "called-to-the-cage"
        cm._LIVE.clear()
    assert world.get(c.scene.location_id) is not None


def test_the_new_campaign_screen_path_reaches_the_draw(tmp_path):
    """`/api/start` carries `start_town` and `start_id` through to `begin_with`."""
    from django.test import Client

    with override_settings(CAMPAIGN_DIR=str(tmp_path / "campaigns")):
        cm._LIVE.clear()
        r = Client().post("/api/start", data=json.dumps({
            "world": "pangrella-campaign", "source": "pc-kesst",
            "start_town": "Pangrella", "start_id": "sent-for"}),
            content_type="application/json")
        assert r.status_code == 200, r.content
        c = cm.current()
        assert c.start_id == "sent-for" and c.location.name == "Pangrella"
        cm._LIVE.clear()


# --- the documents -----------------------------------------------------------------------------

def test_every_shipped_start_validates():
    """A start the validator refuses is never drawn; a shipped one must never be refused."""
    docs = openings.all_starts()
    assert len(docs) >= 15
    bad = {sid: openings.validate(d) for sid, d in docs.items() if openings.validate(d)}
    assert bad == {}


def test_ten_kinds_of_start_open_in_town():
    """Item 3.5: varied incident KINDS (attack, injury, offer, chase, …) where the old
    table had one kind twelve times. At least eight in-town kinds are placeable."""
    kinds = {d["kind"] for d in openings.usable().values() if not openings.placeable(d)}
    assert len(kinds) >= 8, kinds


def _valid():
    return json.loads(json.dumps(openings.get("sent-for")))


@pytest.mark.parametrize("change,named", [
    (lambda d: d["lead"].update(label="the watchman waving traffic through"), "look"),
    (lambda d: d["lead"].update(says="Come back in 3 days."), "digit"),
    (lambda d: d["lead"].update(says="Talk to Drenn about it."), "capitalised"),
    (lambda d: d.update(kind="picnic"), "kind"),
    (lambda d: d.update(when="Midnight"), "night"),
    (lambda d: d["fits"].update(backgrounds=["astronaut"], open=True), "not a background"),
    (lambda d: d["hand_off"].update(at="check", skill="heal", on="$nobody"), "slot"),
    (lambda d: d.update(errand="Here for the bread."), "You came"),
    (lambda d: d["lead"].update(look="with his hat in his hands"), "he or she"),
])
def test_the_validator_names_the_fix(change, named):
    """Every rule refuses with the repair named, in the classbuilder style. The first row
    is item 4b: "the watchman waving traffic through" was the watchman's NAME on the
    panel, and the face check keyed him on "through"."""
    doc = _valid()
    assert openings.validate(doc) == []
    change(doc)
    problems = openings.validate(doc)
    assert problems and any(named in p for p in problems), problems


def test_a_road_start_waits_for_the_outskirts():
    """A road start VALIDATES now and is never placed until I1 lands the outskirts: a road
    start with no road to stand on would be the gate wearing a road's name. Over a
    thousand draws for the caravan hand (whose road start is weighted six times),
    none lands on the road."""
    road = [d for d in openings.all_starts().values()
            if (d.get("where") or {}).get("at") == "road"]
    assert road and all(not openings.validate(d) for d in road)
    assert all("outskirts (I1)" in openings.placeable(d) for d in road)
    world = load_cached(AURVANTIS)
    pc = _pc("fixtures/pc-borin.json")
    for seed in range(1000):
        _town, doc = openings.choose(world, pc, openings.rng_for(seed, "start"))
        assert doc["where"]["at"] != "road", seed


def test_the_starts_audit_measures_offline(tmp_path, monkeypatch):
    """`tools/narrator_audit.py --starts N --offline`: the G2 script's engine half, which
    the harness could not express before (it ran thirty turns of one campaign, not one
    turn of thirty). It records town, start, kind and lead, and the checks' verdicts."""
    from tools import narrator_audit as audit

    monkeypatch.setenv("TEMP", str(tmp_path))
    result = audit.starts(3, PANGRELLA, written=False)
    assert len(result["rows"]) == 3
    for row in result["rows"]:
        assert row["town"] and row["start"] and row["kind"] and row["lead"]
        assert row["size_words"] == [] and row["crossed"] == [] and row["face_given"]
    assert set(result["passes"]) >= {"towns >= 5", "kinds >= 8"}


# --- what a start leaves in the engine ---------------------------------------------------------

def _opened(start_id: str, character: str, world: str = PANGRELLA, tmp_path=None):
    with override_settings(CAMPAIGN_DIR=str(tmp_path / "campaigns")):
        c = cm.new_campaign(f"c-{start_id}", seed=77, character=_pc(character),
                            world_source=world, start_id=start_id)
    assert c.start_id == start_id
    return c


def test_the_bonesetter_start_leaves_a_dying_patient(tmp_path):
    """Item 3.3: no start put anything in engine state, so the first turn could only ask
    "what's going on?". The player's own example — the cage owner walking the bonesetter
    to the patient — now leaves a patient really dying (below zero, losing a hit point a
    round), standing on the map beside them, with the damage stamped by the start
    document and nothing written to the turn log (a start with a turn in it is not the
    abandoned start `begin_with` retires)."""
    c = _opened("called-to-the-cage", "fixtures/pc-thessaly.json", tmp_path=tmp_path)
    patient = c.scene.people[c.scene.start["slots"]["patient"]]
    assert patient.hp < 0 and patient.has_state("state.down.dying")
    assert patient.ref in c.scene.positions
    assert c.scene.start["hand_off"]["skill"] == "heal"
    assert c.scene.start["hand_off"]["ref"] == patient.ref
    assert any("called to the cage" in t for t in c.scene.start["tells"])
    assert c.turn_log == []


def test_a_fight_start_opens_the_encounter(tmp_path):
    """The fight hand-off: the encounter is open, initiative is rolled, and the start
    has thrown no blow — the first one belongs to whoever's turn it is."""
    pc = _pc("fixtures/pc-borin.json", background="pit-fighter")
    with override_settings(CAMPAIGN_DIR=str(tmp_path / "campaigns")):
        c = cm.new_campaign("c-bout", seed=77, character=pc, world_source=PANGRELLA,
                            start_id="the-bout-tonight")
    assert c.start_id == "the-bout-tonight"
    assert c.scene.in_encounter
    foe = c.scene.people[c.scene.start["slots"]["challenger"]]
    assert foe.hp == foe.hp_max and c.scene.pc().hp == c.scene.pc().hp_max
    refs = {r for r, _ in c.scene.initiative}
    assert {"pc", foe.ref} <= refs


def test_a_start_grants_its_state_through_the_one_applicator(tmp_path):
    """"Stop, thief" names the character suspected in front of the market: the grant is an
    ActiveEffect with `origin: start:stop-thief`, removable like any other."""
    c = _opened("stop-thief", "fixtures/pc-kesst.json", tmp_path=tmp_path)
    pc = c.scene.pc()
    assert pc.has_state("state.suspected")
    held = [e for e in pc.effects if "state.suspected" in e.tags]
    assert held and all(e.origin == "start:stop-thief" for e in held)


def test_the_template_never_narrates_past_the_hand_off(tmp_path):
    """The opening stops at `hand_off.moment` (Blades' "first serious obstacle"): no
    shipped start's template says the patient is stabilised, the blow landed, or the
    player accepted — the checks that hold the written opening to it hold the floor too."""
    for sid, doc in openings.usable().items():
        if openings.placeable(doc):
            continue
        bgs = (doc.get("fits") or {}).get("backgrounds") or [None]
        pc = _pc("fixtures/pc-thessaly.json", background=bgs[0])
        with override_settings(CAMPAIGN_DIR=str(tmp_path / "campaigns")):
            c = cm.new_campaign(f"t-{sid}", seed=3, character=pc, world_source=SYNTHETIC,
                                start_id=sid)
            if c.start_id != sid:
                continue      # this world has nowhere for it (no lodging, no water)
            cm.open_the_story(c, written=False)
        text = c.transcript[-1]["text"]
        assert openings.crossed(text, c.scene.start) == [], (sid, text)
        assert text.rstrip().endswith("What do you do?"), sid
        assert doc["hand_off"]["moment"] in text, sid
