"""Stage 8b–8d: actors are contained by places, and everything that fell out of it.

The scene held four spatial authorities and derived none from the others; the roster
was a dict beside the place, so walking out of a room needed the merchant shed by hand,
and four doors each carried their own copy of the shedding rule. The six code maps that
preceded this counted 171 production reads of the roster against 5 writes, and found
five per-ref tables already poisoned by ref recycling. Every tradition consulted holds
the relation on the contained thing and derives presence from it; Bevy shipped the
two-sided version and replaced it. `docs/places-8b-plan.md` is the record; these tests
pin each decision with the measurement that forced it.
"""
from __future__ import annotations

import json

import pytest

from rules import places
from rules.bestiary import instantiate, next_ref
from rules.dice import Dice
from rules.engine import Engine, Scene
from rules.intents import IntentError
from rules.sheet import load_pc
from tests._places import stand_on


def _yard(seed: int = 11):
    s = Scene(location_id="5bbd0c40345f")
    stand_on(s, "urban")
    s.add(load_pc("fixtures/pc-kesst.json"))
    s.add(instantiate("guildhand", scene=s, name="the merchant"))
    s.add(instantiate("thug", scene=s, name="the bravo"))
    return s, Engine(s, Dice(seed=seed))


def _other(engine):
    here = engine.here()
    return next(p for p in engine.places() if p.id != here.id)


# --- the store and the view ------------------------------------------------------------

def test_presence_is_derived_and_the_room_keeps_its_people():
    """The reported bug, in its final form: the merchant stays in his stall because the
    stall is where he IS, not because a door remembered to shed him."""
    s, engine = _yard()
    stall = s.at
    engine.run(engine.validate([{"op": "travel", "because": "she walks out",
                                 "params": {"place": _other(engine).name}}]))
    assert list(s.actors) == ["pc"], "the room's people followed her out"
    assert set(s.people) == {"pc", "c1", "c2"}, "walking out destroyed them"
    assert {s.people[r].at for r in ("c1", "c2")} == {stall}
    engine.run(engine.validate([{"op": "travel", "because": "she comes back",
                                 "params": {"place": places.find(engine.places(), stall).name}}]))
    assert set(s.actors) == {"pc", "c1", "c2"}, "the room forgot its people while she was out"


def test_the_view_is_read_only():
    """Five production sites wrote the roster directly; under a derived view a write
    either vanishes into a computed dict or raises. Raising is the one that gets fixed."""
    s, _ = _yard()
    with pytest.raises(TypeError):
        s.actors["c9"] = s.people["c1"]
    assert not hasattr(s.actors, "pop")
    assert not hasattr(s.actors, "update")
    # The whole read surface the maps found still works.
    assert set(s.actors.keys()) == {"pc", "c1", "c2"}
    assert s.actors.get("c1") is s.people["c1"] and s.actors.get("c9") is None
    assert "c1" in s.actors and "c9" not in s.actors and len(s.actors) == 3
    assert {r for r, _ in s.actors.items()} == {"pc", "c1", "c2"}


def test_the_pc_is_found_through_the_store_not_the_view():
    """"Here" is the PC's place and the view is everyone in the PC's place, so finding the
    PC through the view is circular. Sixty callers dereference `pc()` unguarded."""
    s, _ = _yard()
    s.at = "somewhere~urban:else"           # the party record drifts; the PC does not
    assert s.pc() is not None and s.pc().ref == "pc"


# --- the one mover --------------------------------------------------------------------

def test_move_cleans_every_tactical_table_and_no_relational_one():
    """`depart` left `fallen`, `pools`, `attacked` and `manifests` behind (the map), and
    the first draft of the mover cleaned all four — two of which are facts about the
    ROOM. Pools stay on the floor they were spilled on; guards survive when both ends
    walk through the same door."""
    from rules.engine import BloodPool
    from rules.guards import Guard

    s, engine = _yard()
    engine.run(engine.validate([{"op": "begin_encounter", "because": "t",
                                 "params": {"sides": {"pc": ["pc"], "them": ["c1", "c2"]}}}]))
    s.end_encounter()
    s.zones["c1"] = "far"
    s.positions["c1"] = (3, 3)
    s.spawn_feet["c1"] = 120
    s.fallen["c1"] = 1
    s.reacted["c1:aoo"] = 1
    s.attacked.add("c1>pc")
    s.acted.add("c1")
    s.pools.append(BloodPool(owner="c1", at=(3, 3), place=s.at))
    s.guards.append(Guard(guardian="c1", protects="pc"))

    s.move("c1", "5bbd0c40345f~urban:the-gate")

    for table in ("positions", "spawn_feet", "fallen", "acted"):
        assert "c1" not in getattr(s, table), f"{table} still names a creature who left"
    assert not any(k.startswith("c1:") for k in s.reacted)
    assert not any("c1" in k.split(">") for k in s.attacked)
    # A zone is PC-relative and a fresh one is issued on arrival: not "far" any more.
    assert s.zones.get("c1") == "near"
    assert [b.owner for b in s.pools] == ["c1"], "the blood left the floor with him"
    assert s.guards, "a guard is relational; the per-ref move does not decide it"
    assert not s.settle_relations() == [], "the ends are in different rooms now"
    assert s.guards == []


def test_a_guard_survives_when_both_ends_walk_through_the_door():
    from rules.guards import Guard

    s, engine = _yard()
    s.guards.append(Guard(guardian="c1", protects="pc"))
    engine.run(engine.validate([{"op": "travel", "because": "together",
                                 "params": {"place": _other(engine).name, "with": ["c1"]}}]))
    assert set(s.actors) == {"pc", "c1"}
    assert [g.guardian for g in s.guards] == ["c1"], "an escort's guard was cut in the doorway"


def test_moving_the_pc_moves_the_party_and_empties_the_ledger():
    s, _ = _yard()
    s.cast = [{"who": "a stranger", "turn": 1}]
    s.move("pc", "5bbd0c40345f~urban:the-gate")
    assert s.at == "5bbd0c40345f~urban:the-gate" and s.pc().at == s.at
    assert s.cast == [], "prose-people introduced in the old room came along"


def test_the_pc_does_not_leave_an_initiative_order_by_the_side_door():
    s, engine = _yard()
    engine.run(engine.validate([{"op": "begin_encounter", "because": "t",
                                 "params": {"sides": {"pc": ["pc"], "them": ["c1"]}}}]))
    with pytest.raises(ValueError):
        s.move("pc", "5bbd0c40345f~urban:the-gate")
    assert s.remove("pc") is None and "pc" in s.people


def test_remove_lifts_the_compulsions_a_creature_was_pulling():
    """`compulsion.add(target, by=towards)` lives on the TARGET's effect list, outside
    every scene table — a compeller who ceased to exist left a standing −4 aimed at
    nobody present, and nothing in the engine could find it to lift it."""
    from rules import compulsion

    s, _ = _yard()
    compulsion.add(s.people["pc"], by="c1", rounds=None)
    assert compulsion.pulled_towards(s.people["pc"]) == ["c1"]
    s.remove("c1")
    assert compulsion.pulled_towards(s.people["pc"]) == []


# --- refs ---------------------------------------------------------------------------

def test_refs_are_minted_once_and_never_reused():
    """Five copies of "the lowest cN not in scene.actors" existed; under containment
    every copy would re-mint a ref a living creature in the next room still wears."""
    s, engine = _yard()
    s.remove("c1")
    assert next_ref(s) == "c3", "the destroyer freed a ref"
    engine.run(engine.validate([{"op": "spawn", "because": "t",
                                 "params": {"template": "thug", "count": 2}}]))
    assert {"c3", "c4"} <= set(s.people) and "c1" not in s.people
    # Projection without minting: validation consumes nothing.
    assert next_ref(s) == "c5" and next_ref(s, taken={"c5"}) == "c6"
    assert next_ref(s) == "c5"


def test_a_refused_turn_reissues_the_refs_it_minted():
    """The mark lives in `__dict__`, so the snapshot covers it: a spawn in a turn that
    did not happen leaves no gap in the numbering."""
    s, engine = _yard()
    before = s.snapshot()
    engine.run(engine.validate([{"op": "spawn", "because": "t",
                                 "params": {"template": "thug", "count": 1}}]))
    minted = s.minted
    s.restore(before)
    assert s.minted == minted - 1 and next_ref(s) == f"c{minted}"


def test_no_other_copy_of_the_minting_rule_survives():
    """CLAUDE.md: when you fix a rule, grep for every copy of it. The pattern is the
    f-string that builds a ref, not a loop shape, because the copies did not share one."""
    import re
    from pathlib import Path

    offenders = []
    for folder in ("rules", "gm", "play"):
        for path in Path(folder).rglob("*.py"):
            if path.name == "bestiary.py":
                continue
            for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                if re.search(r'f"c\{', line) and "next_ref" not in line:
                    offenders.append(f"{path}:{n}")
    assert offenders == [], offenders


# --- time and bodies -------------------------------------------------------------------

def test_time_passes_for_the_merchant_in_the_next_room():
    """The world clock ticked only the view. An eight-hour rest kept every timed buff
    on an NPC in the next room — the survival module's own failure, for the absent."""
    s, engine = _yard()
    s.people["c1"].add_condition("shaken", rounds=5, source="t")
    engine.run(engine.validate([{"op": "travel", "because": "out",
                                 "params": {"place": _other(engine).name}}]))
    assert "c1" not in s.actors
    s.advance(minutes=60)
    assert not s.people["c1"].has_condition("shaken"), "time froze for the absent"


def test_a_body_the_party_walked_away_from_still_leaves():
    """Bodies age out wherever they lie; under a here-only ageing loop a corpse in a
    room nobody re-enters would have lain there for the rest of the campaign."""
    s, engine = _yard()
    s.people["c2"].hp = -20
    s.people["c2"].apply_hp_state()
    engine.run(engine.validate([{"op": "travel", "because": "out",
                                 "params": {"place": _other(engine).name}}]))
    assert "c2" in s.people
    for _ in range(4):
        engine.tidy_the_fallen()
    assert "c2" not in s.people, "the corpse in the other room never left"


def test_death_does_not_move_anybody():
    """The two-turn grace is WHY a fresh corpse is still in the view: loot, heat, the
    finishing-blow check and the dead-men-walking cut all read it there."""
    s, engine = _yard()
    s.people["c2"].hp = -20
    s.people["c2"].apply_hp_state()
    assert "c2" in s.actors


# --- travel -----------------------------------------------------------------------------

def test_a_walked_out_fight_pays_out_loud():
    """`_op_travel` called `end_encounter` without `_settle_xp`: a fight you walked out of
    paid nothing, silently. Now it pays first and the tell carries the line."""
    s, engine = _yard()
    s.people["c2"].hp = -20
    s.people["c2"].apply_hp_state()
    engine.run(engine.validate([{"op": "begin_encounter", "because": "t",
                                 "params": {"sides": {"pc": ["pc"], "them": ["c2"]}}}]))
    xp = s.pc().xp
    r = engine.run(engine.validate([{"op": "travel", "because": "out",
                                     "params": {"place": _other(engine).name}}]))
    assert s.pc().xp > xp, "walking out forfeited the XP"
    assert "XP" in r.outcomes[0].tell


def test_the_dying_are_resolved_before_the_party_is_out_of_earshot():
    """Three doors shed people and only two resolved the dying first; travel left them
    bleeding with no tell."""
    s, engine = _yard()
    s.people["c2"].hp = -3
    s.people["c2"].apply_hp_state()
    assert s.people["c2"].has_condition("dying")
    r = engine.run(engine.validate([{"op": "travel", "because": "out",
                                     "params": {"place": _other(engine).name}}]))
    assert not s.people["c2"].has_condition("dying")
    assert "the bravo" in r.outcomes[0].tell


def test_ground_already_underfoot_is_a_no_op():
    """Without the stored biome's equality guard, "I go deeper into the forest" walked the
    party back to the approach and shed the escort."""
    s, engine = _yard()
    engine.run(engine.validate([{"op": "travel", "because": "t", "params": {"biome": "forest"}}]))
    engine.run(engine.validate([{"op": "travel", "because": "t",
                                 "params": {"place": "the heart of it"}}]))
    deep = s.at
    r = engine.run(engine.validate([{"op": "travel", "because": "t", "params": {"biome": "forest"}}]))
    assert s.at == deep and "already" in r.outcomes[0].tell


def test_urban_is_never_a_region():
    """Three production paths send `urban` back to town; every one would have minted a
    region called urban outside the town it was trying to enter."""
    s, engine = _yard()
    home = s.at
    engine.run(engine.validate([{"op": "travel", "because": "t", "params": {"biome": "forest"}}]))
    engine.run(engine.validate([{"op": "travel", "because": "t", "params": {"biome": "urban"}}]))
    assert places.terrain_of(s.at) == "urban" and s.at == home
    assert set(s.actors) == {"pc", "c1", "c2"}, "the town was empty when she came back"


def test_an_escort_in_another_room_cannot_be_named():
    """`with` was read at one line and validated by none."""
    s, engine = _yard()
    engine.run(engine.validate([{"op": "travel", "because": "out",
                                 "params": {"place": _other(engine).name}}]))
    with pytest.raises(IntentError) as e:
        engine.validate([{"op": "travel", "because": "t",
                          "params": {"place": "the market", "with": ["c1"]}}])
    assert "not here" in str(e.value)


def test_somebody_elsewhere_is_refused_as_elsewhere_not_as_unknown():
    """"Unknown ref — create them first with spawn" would invite the model to spawn a
    duplicate of the merchant standing in the next room. And the refusal does not say
    "travel there": a travel and an action on them in one list fails the action's own
    ref check, because validation runs against the view before anything moves."""
    s, engine = _yard()
    engine.run(engine.validate([{"op": "travel", "because": "out",
                                 "params": {"place": _other(engine).name}}]))
    with pytest.raises(IntentError) as e:
        engine.validate([{"op": "attack", "actor": "pc", "target": "c1", "because": "t"}])
    said = str(e.value)
    assert "c1" in said and "not here" in said and "spawn" not in said
    assert "travel there" not in said and "this turn" in said


# --- persistence ------------------------------------------------------------------------

def test_two_actors_in_two_places_survive_the_save(tmp_path):
    """`from_dict` ignores keys it does not know; as first written the save carried `at`
    and the load stamped every actor into one room."""
    from django.test import override_settings

    from play import campaign as cm

    with override_settings(CAMPAIGN_DIR=tmp_path):
        cm._LIVE.clear()
        c = cm.begin_with(load_pc("fixtures/pc-kesst.json"))
        e = c.engine()
        stall = c.scene.at
        e.run(e.validate([{"op": "spawn", "because": "t",
                           "params": {"template": "guildhand", "name": "the merchant"}}]))
        merchant = next(r for r, a in c.scene.actors.items() if a.name == "the merchant")
        other = next(p for p in e.places() if p.id != stall)
        e.run(e.validate([{"op": "travel", "because": "out", "params": {"place": other.name}}]))
        minted = c.scene.minted
        path = c.save()
        cm._LIVE.clear()

        again = cm.Campaign.load(path)
        assert again.scene.at == other.id
        assert again.scene.people[merchant].at == stall
        assert set(again.scene.actors) == {"pc"}
        assert again.scene.minted == minted
        data = json.loads(path.read_text(encoding="utf-8"))
        assert data["save_version"] == 2 and "people" in data["scene"]
        assert "biome" not in data["scene"], "the sibling field is back"
        cm._LIVE.clear()


def test_a_new_campaign_stands_the_company_beside_the_party(tmp_path):
    """`new_campaign` placed the scene after adding everybody: the opening companion was
    stamped with no place and stood out of view on turn one."""
    from django.test import override_settings

    from play import campaign as cm

    with override_settings(CAMPAIGN_DIR=tmp_path):
        cm._LIVE.clear()
        c = cm.new_campaign("fresh")
        assert c.scene.at and places.terrain_of(c.scene.at) == "urban"
        assert len(c.scene.actors) == 2, "the opening companion is standing nowhere"
        assert all(a.at == c.scene.at for a in c.scene.people.values())
        cm._LIVE.clear()


# --- 8d: one writer for where ------------------------------------------------------------

def test_nothing_writes_where_into_the_thread():
    from gm import judgement

    s, _ = _yard()
    judgement.update_thread(s, "I follow the guards into the market", [])
    assert s.thread.get("subject") == "the guards", s.thread
    assert "where" not in s.thread
    judgement.update_thread(s, "I leave and return to the market", [])
    assert "where" not in (s.thread or {})


def test_the_brief_asserts_the_engines_place_once():
    """Two place assertions used to reach one prompt: the engine's `at` and a regex over
    the player's sentence. One now, and it is the engine's."""
    from gm import judgement, prompts

    class _W:
        name, premise, secret = "Fantasia", {}, ""

        def ancestors(self, _):
            return []

        def get(self, _):
            return None

    s, engine = _yard()
    judgement.update_thread(s, "I follow the merchant", [])
    brief = prompts.scene_brief(_W(), s, None, [], here=engine.here(), known=engine.places())
    assert brief.count("ALREADY at") == 1
    assert engine.here().name in brief


def test_leaving_without_naming_a_room_makes_the_schema_ask_for_one():
    """`inject_travel` refuses to guess a place — rightly — so once a room keeps its
    people, nothing moved the PC on "I leave the tavern". The declarer makes the model
    say where; it never guesses."""
    from gm import judgement

    s, _ = _yard()
    assert "travel" in judgement.declared_ops("I leave the tavern", s)
    assert "travel" not in judgement.declared_ops("I look around the tavern", s)
    lone = Scene(location_id=None)
    lone.add(load_pc("fixtures/pc-kesst.json"))
    assert "travel" not in judgement.declared_ops("I leave", lone), \
        "a one-place location has nowhere to go"
