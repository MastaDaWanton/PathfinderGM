"""Where and when (playtest 2026-10-03, Lane B, items 9-12; docs/where-and-when.md).

Every line below is from the owner's two saves of that day — Kesst Vayr in Zhilvarnia,
`igorls/gemma-4-12B` for every call — read off `turn_log` and `transcript`. The town is
looked up by name, never by its id, and every rule tested here reads the app's own place
vocabulary, so none of it is about Zhilvarnia (docs/where-and-when.md, "world-agnostic").
"""
from __future__ import annotations

import json

import pytest

from gm import agent as agent_mod
from gm import checks, judgement
from gm.checks import setting_kind
from rules import places as places_mod
from rules import states
from rules.bestiary import instantiate
from rules.dice import Dice
from rules.engine import Engine, Scene
from world import loader

WORLD = loader.load_cached("fixtures/pangrella-campaign.json")
TOWN = next(e for e in WORLD.entities.values() if e.name == "Zhilvarnia")


def _at(slug: str, clock: int = 0):
    s = Scene(location_id=TOWN.id)
    pc = instantiate("guildhand", scene=s, name="Kesst Vayr")
    pc.kind = "pc"
    s.add(pc)
    s.clock_minutes = clock
    e = Engine(s, Dice(seed=5), world=WORLD)
    place = places_mod.find(e.places(), slug)
    e.place_party(place.id)
    return s, e


def _known(e):
    return tuple(e.places()) + tuple(e.open_ground())


# --- item 9: a verb of intent founds and enters a place ------------------------------------

ROW_52 = "I take the brunt of the weight and move it toward the storage area."
ROW_106 = "I pocket the coins and head for the side door."


def test_moving_the_crate_toward_the_storage_area_founds_nothing():
    """Row 52: the first plan's `travel` to "the storage area" was refused ("there is no
    'the storage area' here. Name one of: …"), the retry planned `found` + `travel`, and a
    place *the storage area* opened off the docks with the player moved into it. Both
    plans are now the walk across the quay: no travel, no founding."""
    s, e = _at("the docks")
    first = [{"op": "travel", "actor": "pc", "params": {"place": "the storage area"}}]
    retry = [{"op": "found", "actor": "pc", "params": {
                 "name": "the storage area", "kind": "warehouses", "parent": "the docks"}},
             {"op": "travel", "actor": "pc", "params": {"place": "the storage area"}}]
    for plan in (first, retry):
        notes: list[str] = []
        out = judgement.keep_movement_in_the_scene([dict(r) for r in plan], ROW_52, s,
                                                   known=_known(e), notes=notes)
        assert [r["op"] for r in out] == ["narrate_only"], out
        assert "storage area" in out[0]["because"]
        assert notes and "dropped" in notes[0]


def test_heading_for_the_side_door_does_not_found_the_smithy():
    """Row 106. The clerk had said "make your exit through the side door, past the
    smithy"; the player wrote only "head for the side door", and the plan founded *the
    smithy* off the counting house and walked into it — the turn after, the prose had
    them at the forge. A door is a thing in the room (Inform's `thing`, not its
    `room`), so walking to it is no journey."""
    s, e = _at("the counting house")
    plan = [{"op": "found", "actor": "pc", "params": {"name": "the smithy", "kind": "smithy",
                                                      "parent": "the counting house"}},
            {"op": "travel", "params": {"place": "the smithy"}},
            {"op": "give", "params": {"item": "coins", "to": "pc"}}]
    out = judgement.keep_movement_in_the_scene(plan, ROW_106, s, known=_known(e))
    assert [r["op"] for r in out] == ["give", "narrate_only"]


def test_a_place_set_out_to_find_is_still_founded():
    """The owner's 2026-09-30 ruling stands: "I should be able to go anywhere". "I head
    toward the back streets to find the Velvet Veil" walks toward somewhere, AND names
    the place it sets out to find, so the Veil is founded as it was. So is a warehouse
    gone to, a base declared, and a journey through the door rather than to it."""
    s, e = _at("the docks")
    veil = [{"op": "found", "params": {"name": "the Velvet Veil", "kind": "tavern"}},
            {"op": "travel", "params": {"place": "the Velvet Veil"}}]
    assert judgement.keep_movement_in_the_scene(
        list(veil), "I head toward the back streets to find the Velvet Veil.", s,
        known=_known(e)) == veil
    store = [{"op": "found", "params": {"name": "the warehouse", "kind": "warehouses"}},
             {"op": "travel", "params": {"place": "the warehouse"}}]
    assert judgement.keep_movement_in_the_scene(list(store), "I go to the warehouse.", s,
                                                known=_known(e)) == store
    base = [{"op": "found", "params": {"name": "our base"}}]
    assert judgement.keep_movement_in_the_scene(list(base), "We make this our base.", s,
                                                known=_known(e)) == base
    through = [{"op": "travel", "params": {"place": "the smithy"}}]
    assert judgement.keep_movement_in_the_scene(list(through), "I go through the side door.",
                                                s, known=_known(e)) == through


def test_heading_toward_a_real_place_is_a_journey():
    """"toward the market" is a travel when the market is a place here: only a movement
    aimed at something that is NOT a place is held inside the scene."""
    s, e = _at("the docks")
    plan = [{"op": "travel", "params": {"place": "the market"}}]
    assert judgement.keep_movement_in_the_scene(list(plan), "I head toward the market.", s,
                                                known=_known(e)) == plan
    assert judgement.movement_within("I go to the front gate of the house.", _known(e)) == []
    assert judgement.movement_within("I walk to the other side of the square.",
                                     _known(e)) == []


class _Reply:
    def __init__(self, text):
        self.text, self.seconds, self.model = text, 0.0, "fake"

    def json(self):
        return json.loads(self.text)


def test_row_52_through_plan_turn_founds_nothing_and_costs_one_call(monkeypatch):
    """The real path: the planner answering row 52 with the retry's own `found` +
    `travel`. Before, that pair validated and the party walked into a minted place; the
    first attempt's travel cost a refusal and a second planning call. Now one call, no
    found, no travel, and the walk noted on the turn."""
    s, e = _at("the docks")
    calls: list[str] = []

    def fake_chat(messages, model, host, **kw):
        calls.append(model)
        return _Reply(json.dumps({"narration": "", "intents": [
            {"op": "found", "actor": "pc", "params": {
                "name": "the storage area", "kind": "warehouses", "parent": "the docks"}},
            {"op": "travel", "actor": "pc", "params": {"place": "the storage area"}}]}))

    monkeypatch.setattr(agent_mod.client, "chat", fake_chat)
    gm = agent_mod.GMAgent(WORLD, e)
    plan = gm.plan_turn(ROW_52, history=[])
    ops = [i.op for i in plan.intents]
    assert "found" not in ops and "travel" not in ops, ops
    assert not s.founded
    assert not plan.rejections, plan.rejections
    assert any("movement within the scene" in r for r in plan.repairs), plan.repairs


# --- item 10: "You leave X mid-sentence" ----------------------------------------------------

def test_walking_away_does_not_claim_anybody_was_mid_sentence():
    """Every one of the items save's five travel tells said "You leave … mid-sentence",
    the first naming four people — "the servant carrying jugs two at a time, say "just
    trying…", the figure, the man" — three of whom had not spoken for turns: the
    conversation tag is sticky by the 2026-09-24 ruling, so it is held by everybody the
    player ever spoke with here. The engine knows a conversation was open and walking
    off closed it; that is what the tell says now."""
    s, e = _at("the market")
    servant = s.add(instantiate("guildhand", scene=s, name="servant"))
    man = s.add(instantiate("guildhand", scene=s, name="man"))
    for who in (servant, man):
        e.run(e.validate([{"op": "say", "actor": "pc", "because": "t",
                           "params": {"words": "Good evening.", "to": who.ref}}],
                         origin="author:test"))
    assert servant.has_state(states.TALKING) and man.has_state(states.TALKING)
    out = e.run(e.validate([{"op": "travel", "actor": "pc", "because": "t",
                             "params": {"place": "the docks"}}],
                           origin="author:test")).outcomes[-1]
    assert "mid-sentence" not in out.tell, out.tell
    assert ("You walk away from the servant and the man, and the conversation is over."
            in out.tell), out.tell
    assert not man.has_state(states.TALKING)


# --- item 11: the time of day runs backwards ------------------------------------------------

def _ctx(s, e, text, door="turn"):
    return checks.BeatContext(
        door=door, text=text, player_text="", engine=e, scene=s, world=WORLD,
        location=TOWN, reading=None, outcomes=(), tells=(), said=(), attribution=None,
        brief="", brief_facts={}, pull=None, was_at=s.at, acting="", turn=0)


# The hour checks of item 11 retired on 2026-10-03 into the beat read back
# (gm/checks/beat_verified.py): equal on the bench (3 of 3 and 6 of 6 alarms, no false
# alarm either way, docs/beat-verify.md), and the reading of "the pre-dawn gloom" is the
# model's now. The measurement — clock 32 "the work of the morning", 80 "the first hint
# of dawn", 88 "the pre-dawn gloom" — is pinned in tests/test_beat_verify_diff.py.


# --- item 12: the setting drifts -------------------------------------------------------------

MARKET_TURN_0 = ("Behind him, the tavern patrons have stopped their drinking; the clatter of "
                 "mugs has died away. The air in the room feels thick. The man on the stool "
                 "blinks, his eyes darting to the door, then to the man at the bar, and "
                 "finally back to you. The stalls stand dark around you.")
MARKET_TURN_4 = ("He leans back against the bar, the wood groaning under his weight. He "
                 "doesn't move toward you, but the heavy atmosphere of the tavern seems to "
                 "press in on the two of you.")


def test_a_taproom_furnished_round_a_party_at_the_market_is_found():
    """Market-talk: the engine held the party at the market for every turn, and the page
    wrote a tavern round them — "the tavern patrons", "the room", "the man at the bar",
    "leans back against the bar", "the atmosphere of the tavern". `stands-elsewhere`
    stayed silent: Zhilvarnia HAS a tavern, and no sentence said "you are in it". The
    replay of both saves finds 15 such sentences in 8 beats, all at the market, and
    none in the 54 texts set anywhere else."""
    s, e = _at("the market")
    found = setting_kind.find(_ctx(s, e, MARKET_TURN_0))
    assert [f.kind for f in found] == ["wrong-kind-of-place"]
    assert len(found[0].sentences) == 3
    assert "The stalls stand dark around you." not in found[0].sentences
    assert "at the market" in found[0].fix_hint
    fixed, _ = setting_kind.backstop(_ctx(s, e, MARKET_TURN_0), MARKET_TURN_0, found)
    assert fixed == "The stalls stand dark around you."
    assert len(setting_kind.find(_ctx(s, e, MARKET_TURN_4))[0].sentences) == 2


def test_the_same_words_in_the_tavern_or_seen_from_afar_are_not():
    """In the tavern itself the bar is where it should be; a tavern ACROSS the square is
    a view; and a character may speak of any bar they like."""
    s, e = _at("the tavern")
    assert setting_kind.find(_ctx(s, e, MARKET_TURN_0)) == []
    s, e = _at("the market")
    view = ("Across the square, the tavern patrons spill out into the lamplight. "
            "'Meet me at the bar later,' he says.")
    assert setting_kind.find(_ctx(s, e, view)) == []


def test_the_new_checks_are_members():
    names = {m.__name__.rsplit(".", 1)[-1] for m in checks.registered()}
    assert {"beat_verified", "setting_kind"} <= names
    assert "time_of_day" not in names       # retired into beat_verified, see above


def test_a_legacy_opening_stands_the_party_where_its_words_are_set(monkeypatch, tmp_path):
    """The market-talk save opened "Evening … You are in a lit doorway with a room's
    noise behind it … You have just come in out of the weather" with the party at the
    market, and the narrator furnished a taproom round them for six turns. A legacy
    opening (a world no start document fits) now stands the party in a place of the
    kind its row names — the tavern for that doorway — and the clock at its hour."""
    from django.test import override_settings

    from play import campaign as cm, opening
    from rules import openings

    monkeypatch.setattr(openings, "choose", lambda world, pc, rng, **kw: (TOWN, None))
    seed = next(n for n in range(500) if opening.roll("legacy-zh", n).when == "Evening")
    with override_settings(CAMPAIGN_DIR=str(tmp_path / "campaigns")):
        c = cm.new_campaign("legacy-zh", seed=seed)
    here = opening.situation_for(c)
    assert here.kinds == ("lodging",)
    assert c.scene.at.endswith(":the-tavern"), c.scene.at
    assert c.scene.clock_minutes == opening.hour_of(here.when) * 60 == 19 * 60
    watcher = next(a for a in c.scene.people.values() if not a.is_pc)
    assert watcher.at == c.scene.at
    # Every kind the table names is one the start documents' validator accepts.
    assert all(openings._known_kind(k) for s in opening.SITUATIONS for k in s.kinds)
