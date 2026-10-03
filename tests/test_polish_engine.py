"""The pre-release polish batch, engine and prose side (docs/fix-interfaces.md §3.4, "G3
leftovers", items 2, 3, 4, 5 and 7). Each test names what was measured.
"""
from __future__ import annotations

import json

import pytest

import replays
from gm import interpret, judgement, prompts
from rules import goods, hazards, journey, keepers, names, places as places_mod, population
from rules import states
from rules.activeeffect import ActiveEffect
from rules.bestiary import instantiate
from rules.dice import Dice
from rules.engine import Engine, Scene
from world import loader

from _a_truth import MARKET, VORMOOR, WORLD, scene_at

PANGRELLA = loader.load_cached("fixtures/pangrella-campaign.json")
P_TOWN = "5bbd0c40345f"
P_MARKET = f"{P_TOWN}~urban:the-market"


def _table(name: str = "man"):
    s = Scene(location_id=P_TOWN)
    pc = instantiate("guildhand", scene=s, name="Kesst")
    pc.kind = "pc"
    s.add(pc)
    e = Engine(s, Dice(seed=5), world=PANGRELLA)
    e.place_party(P_MARKET)
    other = s.add(instantiate("guildhand", scene=s, name=name))
    return s, e, pc, other


def _run(e, raws):
    return e.run(e.validate(raws, origin="author:test")).outcomes


# --- (2) people are printed with their article, and booked with their description ------

class TestTheArticle:
    def test_the_measured_tell_reads_the_man(self):
        """Measured live 2026-09-29: the engine's tell "You leave man mid-sentence"."""
        assert names.with_articles("You leave man mid-sentence.", ["man"]) == \
            "You leave the man mid-sentence."

    def test_a_sentence_opening_takes_a_capital(self):
        assert names.with_articles("man takes it badly.", ["man"]) == "The man takes it badly."
        assert names.with_articles("Kesst waits. Man comes round.", ["man"]) == \
            "Kesst waits. The man comes round."

    def test_idempotent_and_never_inside_speech_or_somebody_elses_name(self):
        """Three ways a blind find-and-replace goes wrong: twice, inside the player's own
        quoted words, and inside a longer name that is somebody else ("man" is in "man
        with the ledger")."""
        once = names.with_articles("You leave man mid-sentence.", ["man"])
        assert names.with_articles(once, ["man"]) == once
        said = 'Bobby says to man: "the man at the gate owes me."'
        assert names.with_articles(said, ["man"]) == \
            'Bobby says to the man: "the man at the gate owes me."'
        both = "Left behind: man with the ledger, man."
        assert names.with_articles(both, ["man", "man with the ledger"]) == \
            "Left behind: the man with the ledger, the man."
        assert names.with_articles("You are with Guard, Grix.", ["Guard", "Grix"]) == \
            "You are with Guard, Grix."
        assert names.with_articles("the watchman waving traffic through nods.",
                                   ["the watchman waving traffic through"]) == \
            "the watchman waving traffic through nods."

    def test_walking_away_mid_sentence_names_the_man(self):
        """The live tell, through the engine: an actor booked as a bare "man", in
        conversation, left by walking away. It printed "You leave man mid-sentence"."""
        s, e, pc, man = _table("man")
        _run(e, [{"op": "say", "actor": pc.ref, "because": "t",
                  "params": {"words": "Good morning.", "to": man.ref}}])
        assert man.has_state(states.TALKING)
        far = next(p for p in e.places() if p.id != s.at and not p.described_only
                   and p.terrain == places_mod.URBAN)
        out = _run(e, [{"op": "travel", "actor": pc.ref, "because": "t",
                        "params": {"place": far.name}}])[-1]
        said = "You walk away from the man, and the conversation is over."
        assert said in out.tell, out.tell
        assert "from man" not in out.tell

    def test_the_bobby_corpus_tells_read_with_their_articles(self):
        """The Bobby corpus (2026-09-28) printed "On the board: girl (c2)." and "Bobby
        speaks to man in a stained leather jerkin" — a kind of person, written as if it
        were a proper name."""
        if not replays.available():
            pytest.skip("the owner's corpus is not on this disk")
        people = [p["name"] for p in replays.save("bobby.json")["people"]
                  if p["ref"] != "pc"]
        tells = [o.get("tell", "") for t in replays.turns()
                 for o in (t.get("plan") or {}).get("outcomes") or []]
        bare = [t for t in tells if "On the board: girl (c2)." in t
                or "speaks to man in a stained" in t]
        assert bare, "the corpus no longer carries the measured tells"
        for t in bare:
            fixed = names.with_articles(t, people)
            assert "the girl (c2)" in fixed or "to the man in a stained" in fixed, fixed


class TestTheDescriptionKept:
    def test_introducing_a_bare_man_binds_the_man_the_prose_described(self):
        """Measured live 2026-09-29: a scene entry named just "man". The prose had booked
        "man with the whetstone" (the Bobby corpus's p8 is exactly that record) and the
        plan's `introduce who="man"` made a body called "man"."""
        s, e, pc, _ = _table("Grix")
        rec = population.note(s, "man with the whetstone", turn=1)
        out = _run(e, [{"op": "introduce", "actor": pc.ref, "because": "t",
                        "params": {"who": "man", "how": "already_here"}}])[-1]
        made = s.actors[out.effects[0]["bound"]["new1"]]
        assert made.name == "man with the whetstone", made.name
        assert rec["ref"] == made.ref, "a second person beside the record"
        assert "In the scene: the man with the whetstone" in out.tell, out.tell

    def test_two_described_men_are_not_guessed_between(self):
        s, e, pc, _ = _table("Grix")
        population.note(s, "man with the whetstone", turn=1)
        population.note(s, "man in a stained leather jerkin", turn=1)
        assert population.described_here(s, "man") is None

    def test_the_door_names_a_body_by_its_record(self):
        s, e, pc, _ = _table("Grix")
        rec = population.note(s, "girl selling herbs", turn=1)
        body = population.embody(s, "girl", "guildhand", rec=rec)
        assert body.name == "girl selling herbs"
        assert population.fuller("the girl", {"phrase": "man with a ledger"}) == "the girl"


# --- (3) asking ABOUT somebody is not addressing them ----------------------------------

LINE = "I ask the nearest person about the girl who sells herbs in the market."
# The reading of G3's market-seek turn 1, verbatim from the run's turn log.
READING = {"question": False, "claims": [], "actions": [
    {"act": "talk", "target": "the nearest person",
     "says": "about the girl who sells herbs in the market"}]}
# And the plan that came back for it.
PLAN = [
    {"op": "introduce", "because": "the player's words commit the turn to it",
     "params": {"who": "herbalist vendor", "how": "already_here", "template": "guildhand",
                "count": 1}},
    {"op": "narrate_only"},
    {"op": "say", "actor": "pc", "because": "the player asks about the herb girl",
     "params": {"words": "Tell me about the girl who sells herbs in the market.",
                "to": "new1"}},
]


@pytest.fixture
def market_seek():
    agent, _ = scene_at(MARKET, [("Haven Ironfist", "guildhand"),
                                 ("the guild clerk", "guildhand")])
    s = agent.engine.scene
    haven = next(a for a in s.actors.values() if a.name == "Haven Ironfist")
    clerk = next(a for a in s.actors.values() if a.name == "the guild clerk")
    s.zones[haven.ref], s.zones[clerk.ref] = "engaged", "far"
    s.positions.pop(haven.ref, None)
    s.positions.pop(clerk.ref, None)
    if s.grid is not None:
        s.place_by_zone([haven.ref, clerk.ref])
    interpret.remember(LINE, READING)
    yield agent, s, haven, clerk
    interpret._READINGS.clear()


def test_the_topic_is_not_introduced_or_spoken_to(market_seek):
    """Measured live 2026-09-29, G3 market-seek turn 1: "I ask the nearest person about
    the girl who sells herbs in the market." The reading was right (talk, target: the
    nearest person) and the plan was `introduce who="herbalist vendor"` (c3) plus a `say`
    TO her. Now: no introduce, and the line goes to the person nearest."""
    agent, s, haven, clerk = market_seek
    assert judgement._nearest_here(s) == haven.ref
    out = judgement.asked_about_not_addressed(json.loads(json.dumps(PLAN)), LINE, s)
    assert [r.get("op") for r in out] == ["narrate_only", "say"]
    assert out[1]["params"]["to"] == haven.ref


def test_the_detector_does_not_declare_an_introduce_for_the_nearest_person(market_seek):
    """The same turn's log: `detectors: ["introduce"]` — `inject_introduce` read "nearest
    person" as somebody to bring in, which is what made the schema require the op the
    plan then filled with the herb girl. Four `population-miss` rows for "nearest person"
    followed."""
    agent, s, haven, clerk = market_seek
    assert judgement.inject_introduce([], LINE, s, WORLD) == []
    assert "introduce" not in judgement.declared_ops(LINE, s, WORLD)


def test_without_a_reading_the_sentence_still_names_its_topic():
    assert interpret.topics(None, LINE) == ["the girl who sells herbs in the market"]
    assert interpret.in_topic("herbalist vendor", interpret.topics(None, LINE),
                              "the nearest person")
    # The person asked is never the topic, even when they share a word with it.
    assert not interpret.in_topic("the herb seller", ["the girl who sells bread"],
                                  "the herb seller")


def test_through_the_plan(market_seek, monkeypatch):
    """End to end through `plan_turn`, the model answering with the live plan."""
    from gm import agent as agent_mod

    agent, s, haven, clerk = market_seek

    class _Reply:
        text = json.dumps({"narration": "", "intents": PLAN,
                           "declared": {"say": {"params": {"words": "x"}}}})
        seconds, model = 0.0, "fake"

        def json(self):
            return json.loads(self.text)

    monkeypatch.setattr(interpret, "ENABLED", True)
    monkeypatch.setattr(interpret, "interpret", lambda text, **kw: dict(READING))
    monkeypatch.setattr(agent_mod.client, "chat", lambda *a, **kw: _Reply())
    before = set(s.people)
    plan = agent.plan_turn(LINE, history=[])
    assert "introduce" not in [i.op for i in plan.intents], plan.intents
    says = [i for i in plan.intents if i.op == "say"]
    assert says and says[0].params.get("to") == haven.ref
    assert set(s.people) == before, "a body was made for the topic"


# --- (4) I3's hand-offs -------------------------------------------------------------

def test_the_cast_aim_enum_holds_the_scene_s_own_aims(monkeypatch):
    """I3's hand-off: `turn_schema` took no `aims`, so a declared cast's `aim` enum fell
    back to people, self and the directions — a feature or a prop here could not be
    chosen. The agent now hands it `areas.legal_aims` for the spell the player named."""
    from gm import agent as agent_mod
    from rules import areas, spells

    from rules.sheet import load_pc

    s = Scene(location_id=VORMOOR.id)
    pc = load_pc("fixtures/pc-thessaly.json")
    pc.spellbook = ["burning-hands"]
    pc.prepared = {"burning-hands": 1}
    s.add(pc)
    e = Engine(s, Dice(seed=5), world=WORLD)
    e.place_party(f"{VORMOOR.id}~forest:the-approach")
    agent = agent_mod.GMAgent(WORLD, e)
    seen = {}

    class _Reply:
        text = json.dumps({"narration": "", "intents": [{"op": "narrate_only"}]})
        seconds, model = 0.0, "fake"

        def json(self):
            return json.loads(self.text)

    def chat(messages, model, host, **kw):
        seen.setdefault("schema", kw.get("schema"))
        return _Reply()

    monkeypatch.setattr(agent_mod.client, "chat", chat)
    agent.plan_turn("I cast burning hands into the tree tops", history=[])
    declared = seen["schema"]["properties"].get("declared") or {}
    cast = declared.get("properties", {}).get("cast")
    assert cast is not None, "the cast was not declared"
    enum = cast["properties"]["params"]["properties"]["aim"]["enum"]
    want = areas.legal_aims(s, pc.ref, spells.get("burning-hands"))
    assert enum == list(dict.fromkeys(want))
    assert any(a.startswith("object:") for a in enum) or \
        not any(a.startswith("object:") for a in want)


def test_turn_schema_passes_aims_to_the_cast():
    schema = prompts.turn_schema(refs=("pc", "c1"), must_contain=("cast",),
                                 aims=("ref:c1", "self", "object:the old well"))
    enum = (schema["properties"]["declared"]["properties"]["cast"]["properties"]["params"]
            ["properties"]["aim"]["enum"])
    assert enum == ["ref:c1", "self", "object:the old well"]


def test_the_briefing_lists_every_hazard_rule_in_the_file():
    """The briefing's hazard list was a hand-kept copy of stage 8d's eight rows, and I3
    added `burning-brush` and `smoke` to content/rules/hazards.json without the model
    ever being told it could cite them. Read from the file now."""
    messages = prompts.call_one_messages("SCENE", [], "I look around.")
    system = messages[0]["content"]
    assert prompts.HAZARD_TOKEN not in system
    for rid, row in hazards.rows().items():
        assert f"{rid} ({row['slot']['name']})" in system, rid
    assert "burning-brush (rounds)" in system and "smoke (rounds)" in system


# --- (5) mounts: the donkey and the mule, and their keep --------------------------------

def test_a_donkey_and_a_mule_are_mounts_at_the_pony_s_speed():
    """The stables sold donkeys and mules at 8 gp and `journey.MOUNTS` omitted both, so a
    bought one never sped a journey. Ultimate Equipment: "Donkeys and mules have the same
    statistics as ponies" — 40 ft. Every recorded speed matches the bestiary block."""
    from rules import bestiary

    assert {"donkey", "mule"} <= journey.MOUNTS
    for template, speed in journey.MOUNT_SPEEDS.items():
        block = bestiary.lookup(template)
        if block is not None:
            assert int(block.get("speed") or 0) == speed, template
    assert journey.MOUNT_SPEEDS["donkey"] == journey.MOUNT_SPEEDS["pony"] == 40


def _a_mount(s, template="mule"):
    animal = instantiate(template, scene=s, name=template)
    s.add(animal)
    source = f"company:{animal.ref}"
    animal.apply_effect(ActiveEffect(
        name="travels with you", kind="bond", key=f"{source}:travels", source=source,
        origin="bought:pc", duration="until-dismissed", tags=(states.TRAVELS_WITH_YOU,)))
    return animal


def _town_with_stables(world):
    from rules import market

    for e in sorted(world.entities.values(), key=lambda e: str(e.id)):
        if places_mod.scale_of(e) in ("town", "city") and market.has_stables(e):
            try:
                places_mod.home_set(e)
            except Exception:
                continue
            return e
    return None


def test_a_night_in_town_charges_the_stabling_and_the_feed():
    """Upkeep was never charged (the owner's price source: feed 5 cp a day, stabling 5 sp
    a day). A night slept in a settlement with stables now costs a mount both, out of the
    purse, said in the tell."""
    town = _town_with_stables(WORLD)
    if town is None:
        pytest.skip("no settlement with stables in this world")
    s = Scene(location_id=town.id)
    from rules.sheet import load_pc

    pc = load_pc("fixtures/pc-kesst.json")
    s.add(pc)
    e = Engine(s, Dice(seed=5), world=WORLD)
    e.place_party(next(p.id for p in places_mod.home_set(town) if p.name == "the stables"))
    _a_mount(s)
    pc.purse = {"gp": 1}
    out = _run(e, [{"op": "rest", "actor": "pc", "because": "t",
                    "params": {"kind": "night"}}])[-1]
    assert goods.in_copper(pc.purse) == 100 - 50 - 5, pc.purse
    assert "5 silver pieces for the stabling." in out.tell, out.tell
    assert "5 copper pieces for the feed." in out.tell, out.tell
    kinds = [x.get("what") for x in out.effects if x.get("kind") == "upkeep"]
    assert kinds == ["stabling", "feed"]


def test_an_empty_purse_is_said_and_nothing_else_happens():
    s, e, pc, _ = _table("Grix")
    mule = _a_mount(s)
    pc.purse = {}
    hp = mule.hp
    note, fx = e._keep_the_mounts(2, stabled=True)
    assert "the purse cannot pay it: no stall for mule tonight" in note, note
    assert "mule goes hungry" in note, note
    assert [x["paid"] for x in fx] == [False, False]
    assert mule.hp == hp and not mule.conditions, "a penalty the book does not name"


def test_the_road_charges_a_day_s_feed_for_each_day_on_it():
    s, e, pc, _ = _table("Grix")
    _a_mount(s, "donkey")
    pc.purse = {"sp": 5}
    note, fx = e._keep_the_mounts(3)
    assert note == "1 silver piece, 5 copper pieces for the feed.", note
    assert goods.in_copper(pc.purse) == 50 - 15


# --- (7) an old village save's market master ---------------------------------------------

def _village(world):
    from rules import market

    for e in sorted(world.entities.values(), key=lambda e: str(e.id)):
        if places_mod.scale_of(e) == "village":
            try:
                if any(market.is_market(p.id) for p in places_mod.home_set(e)):
                    return e
            except Exception:
                continue
    return None


def test_an_old_village_master_is_kept_as_a_resident():
    """A save from before I2 holds `keeper:<market>` in a village — a master where a
    village has none (Q28), and not the seller either (I2 sells from the general store's
    holder). Measured at G3: the person the counters could not use. Retired from the
    role on load, never deleted, and recorded as somebody who lives there."""
    village = _village(WORLD)
    if village is None:
        pytest.skip("no village with a market")
    market_id = next(p.id for p in places_mod.home_set(village)
                     if __import__("rules.market", fromlist=["x"]).is_market(p.id))
    s = Scene(location_id=village.id)
    from rules.sheet import load_pc

    s.add(load_pc("fixtures/pc-kesst.json"))
    e = Engine(s, Dice(seed=5), world=WORLD)
    e.place_party(market_id)
    old = instantiate("guildhand", scene=s, name="Ashla Ironvale",
                      world_entity_id=keepers.entity_id(market_id))
    old.true_name = "Ashla Ironvale"
    s.add(old)
    stall = instantiate("guildhand", scene=s, name="Drenn Ironvale",
                        world_entity_id=keepers.holder_id(market_id, "general"))
    s.add(stall)
    retired = keepers.retire_stale_masters(s, WORLD)
    assert retired == [old.ref]
    assert old.ref in s.people and old.name == "Ashla Ironvale"
    assert not keepers.is_keeper(old.world_entity_id or "")
    assert keepers.keeper_in(s, market_id) is None
    rec = population.of_ref(s, old.ref)
    assert rec is not None and rec["spot"] == market_id
    assert rec["life"]["mobility"] == "resident"
    # The counter's own holder is untouched, and a second load retires nobody.
    assert stall.world_entity_id == keepers.holder_id(market_id, "general")
    assert keepers.retire_stale_masters(s, WORLD) == []


def test_the_load_retires_them_and_keeps_them(tmp_path):
    """The same, through `Campaign.load`: the migration runs where an old save is read."""
    from play import campaign as cm
    from rules import market
    from rules.sheet import load_pc

    village = _village(WORLD)
    if village is None:
        pytest.skip("no village with a market")
    market_id = next(p.id for p in places_mod.home_set(village) if market.is_market(p.id))
    s = Scene(location_id=village.id)
    s.add(load_pc("fixtures/pc-kesst.json"))
    Engine(s, Dice(seed=5), world=WORLD).place_party(market_id)
    old = instantiate("guildhand", scene=s, name="Ashla Ironvale",
                      world_entity_id=keepers.entity_id(market_id))
    s.add(old)
    c = cm.Campaign(id="polish-village", world_source=str(WORLD.source), scene=s)
    path = c.save()
    loaded = cm.Campaign.load(path)
    back = loaded.scene.people[old.ref]
    assert back.name == "Ashla Ironvale"
    assert not keepers.is_keeper(back.world_entity_id or "")
    assert population.of_ref(loaded.scene, old.ref) is not None


def test_a_town_master_is_left_alone():
    town = _town_with_stables(WORLD) or VORMOOR
    market_id = next(p.id for p in places_mod.home_set(town)
                     if __import__("rules.market", fromlist=["x"]).is_market(p.id))
    s = Scene(location_id=town.id)
    master = instantiate("guildhand", scene=s, name="Ashla Ironvale",
                         world_entity_id=keepers.entity_id(market_id))
    s.add(master)
    assert keepers.retire_stale_masters(s, WORLD) == []
    assert master.world_entity_id == keepers.entity_id(market_id)
