"""S4 of the 2026-09-28 fix pass: persisted state, one refusal shape, and the arrival door.

docs/fix-interfaces.md §2.4–§2.6 is the contract; docs/playtest-2026-09-28.md item 14 is
the defect. Everything here is Phase 1, which is INERT: new fields default to what a save
without them reads back as, and nothing yet writes them, so an old save must come back
out of load → save byte for byte.

What these record:

  * Item 14. Drenn (c4) stood on the WHO IS HERE list with no square on the board. The
    scheme brought him in through its own `scene.add` + `scene.move` onto the party's own
    place, and `move` drops every square (`_unseat`) without ever giving one back — so
    the one entrance that assigned squares was undone by the second door. The ruling of
    2026-09-28: everyone in a scene has a square from arrival and keeps it until they
    move.
  * The story-seed trap (docs/design-c-starts.md §5). `Campaign.engine()` builds a fresh
    `Dice(self.seed)` on every one of its 31 call sites; the plan's "set `seed` to a fixed
    random value at creation" would have replayed the same dice on every turn. The seed
    the story draws from is `Scene.story_seed`, and `Campaign.seed` is untouched.
"""
from __future__ import annotations

import inspect
import json
import os
import shutil
from pathlib import Path

import pytest
from django.test import override_settings

from play import campaign as cm
from play import opening
from rules import schemes
from rules.bestiary import instantiate
from rules.engine import Engine, Outcome, Scene, _rehydrate
from rules.intents import PLAYER_FIXABLE, IntentError, Intent
from rules.sheet import from_dict, load_pc, to_dict

# The six scene keys this pass adds (register §2.4). A save written by the Phase-1 base
# build has none of them; that is what "an old save" means below.
NEW_SCENE_KEYS = ("story_seed", "start", "spoken_for", "acquainted",
                  "conversation_log", "conversation_seq")


def _unplaced(scene) -> list[str]:
    """Non-PC actors in the party's place, on a gridded scene, with no square."""
    if scene.grid is None:
        return []
    return [r for r, a in scene.actors.items()
            if not a.is_pc and r not in scene.positions]


# --- item 14: the arrival door ------------------------------------------------------------

def test_a_scheme_arrival_onto_the_partys_place_gets_a_square(worlds, tmp_path):
    """Item 14, measured on the owner's save of 2026-09-28: Drenn Ironvale (c4) was listed
    beside the player at the market and had no square — `schemes._role_for` does
    `scene.add(actor)` (which placed him) and then `scene.move(actor.ref, $market)`, and
    `move` popped the square and gave none back although the market was where the party
    stood. Driven through the real scheme function on each of the three worlds. With the
    fix withdrawn this failed on all three, and on Aurvantis the squareless giver it drew
    was Drenn Ironvale himself."""
    with override_settings(CAMPAIGN_DIR=str(tmp_path / "campaigns")):
        c = cm.new_campaign("s4-scheme", seed=7, world_source=str(worlds.source))
        e = c.engine()
        scene = c.scene
        assert scene.grid is not None, "a new campaign stands on laid ground"
        got = schemes._role_for(e, "giver", {"role": "trader", "level": "pc", "at": "$here"},
                                {"here": {"kind": "place", "id": scene.at}}, set())
    assert got and got["ref"], got
    assert scene.people[got["ref"]].at == scene.at
    assert got["ref"] in scene.positions, (
        f"{worlds.name}: {got['name']} ({got['ref']}) arrived at the party's place with "
        f"no square — item 14")
    assert _unplaced(scene) == []


def test_add_then_move_here_is_the_same_as_arriving_here(tmp_path):
    """The bare shape of item 14, outside any scheme: `add` then `move` onto `scene.at`."""
    with override_settings(CAMPAIGN_DIR=str(tmp_path / "campaigns")):
        c = cm.new_campaign("s4-bare", seed=7)
    scene = c.scene
    drenn = scene.add(instantiate("guildhand", scene=scene, name="Drenn Ironvale"))
    assert drenn.ref in scene.positions
    scene.move(drenn.ref, scene.at)
    assert drenn.ref in scene.positions, "move onto the party's place dropped the square"


def test_a_move_elsewhere_still_takes_the_square_away(tmp_path):
    """The other half of the rule: a square is a fact of THIS room. Somebody moved out of
    the party's place holds none, exactly as before."""
    with override_settings(CAMPAIGN_DIR=str(tmp_path / "campaigns")):
        c = cm.new_campaign("s4-away", seed=7)
    scene = c.scene
    other = next(p.id for p in c.engine().places() if p.id != scene.at)
    who = scene.add(instantiate("guildhand", scene=scene, name="Someone"))
    scene.move(who.ref, other)
    assert who.ref not in scene.positions and who.at == other


def test_arrive_elsewhere_records_the_place_and_no_square(tmp_path):
    """Register §2.5: with a `place_id` that is not the party's, the arrival is recorded
    there with no square; absent or equal to `scene.at`, it is today's `add`."""
    with override_settings(CAMPAIGN_DIR=str(tmp_path / "campaigns")):
        c = cm.new_campaign("s4-arrive", seed=7)
    scene = c.scene
    other = next(p.id for p in c.engine().places() if p.id != scene.at)
    away = scene.arrive(instantiate("guildhand", scene=scene, name="Away"), place_id=other)
    assert away.at == other and away.ref in scene.people
    assert away.ref not in scene.positions and away.ref not in scene.actors
    here = scene.arrive(instantiate("guildhand", scene=scene, name="Here"),
                        place_id=scene.at, source="test")
    assert here.at == scene.at and here.ref in scene.positions
    # The mark rises for somebody elsewhere too: a ref worn next door is not free.
    assert scene.minted >= int(away.ref[1:])


def test_add_is_a_thin_alias_of_arrive(monkeypatch):
    """`add` keeps its forty positional/keyword call sites and routes through `arrive`,
    so there is one entrance and not two to keep level. Asserted by behaviour, not by
    reading the source (tests/test_suite_isolation.py's ceiling on source pins)."""
    calls = []
    real = Scene.arrive

    def spy(self, actor, **kw):
        calls.append(kw)
        return real(self, actor, **kw)

    monkeypatch.setattr(Scene, "arrive", spy)
    s = Scene()
    s.add(load_pc("fixtures/pc-kesst.json"), "far", (2, 3))
    assert calls == [{"zone": "far", "at": (2, 3)}]
    params = inspect.signature(real).parameters
    assert list(params) == ["self", "actor", "zone", "at", "place_id", "source"]
    assert all(params[k].kind is inspect.Parameter.KEYWORD_ONLY
               for k in ("zone", "at", "place_id", "source"))


def test_nobody_in_the_partys_place_stands_without_a_square(worlds, tmp_path):
    """The guard the register asks for (§2.5): on a gridded scene, every non-PC actor at
    `scene.at` has a position. Run after every door this pass knows puts people in — the
    opening's company, the keeper behind the counter, a scheme's cast brought to the
    party's own place, and the lost-thing scheme opened at the market — on all three
    worlds. Item 14 is the failure it names: Drenn on the list, not on the map."""
    with override_settings(CAMPAIGN_DIR=str(tmp_path / "campaigns")):
        c = cm.new_campaign("s4-guard", seed=11, world_source=str(worlds.source))
        e = c.engine()
        scene = c.scene
        assert _unplaced(scene) == [], f"{worlds.name}: after the opening"
        market = schemes._place_for(e, "market", {})
        if market and market["id"] != scene.at:
            e.place_party(market["id"])
        assert _unplaced(scene) == [], f"{worlds.name}: after arriving at the market"
        doc = schemes.all_schemes()["the-lost-thing"]
        schemes.open_scheme(e, doc, turn=1)
        schemes._role_for(e, "extra", {"role": "guard", "level": "pc", "at": "$here"},
                          {"here": {"kind": "place", "id": scene.at}}, set())
    assert scene.grid is not None
    assert _unplaced(scene) == [], (
        f"{worlds.name}: {[scene.people[r].name for r in _unplaced(scene)]} stand in the "
        f"party's place with no square")


# --- recognise: the knows-you door (inert until Lane C writes `acquainted`) ---------------

def test_recognise_is_inert_while_nobody_is_acquainted(tmp_path):
    """Phase 1 writes nothing to `acquainted`, so an arrival must gain no bond."""
    from rules import backgrounds

    with override_settings(CAMPAIGN_DIR=str(tmp_path / "campaigns")):
        c = cm.new_campaign("s4-inert", seed=7)
    scene = c.scene
    who = scene.add(instantiate("guildhand", scene=scene, name="Wenna",
                                world_entity_id="ent-wenna"))
    assert scene.acquainted == []
    assert not who.has_state("bond.knows-you")
    assert backgrounds.recognise(scene, who) == ""


def test_an_acquainted_arrival_knows_you_through_the_one_applicator(tmp_path):
    """C's §4.8 step 4: `bind` records each tie's entity id in `scene.acquainted`, and the
    arrival door applies `bond.knows-you` (source `background:<id>`) when that person
    arrives — here, and by `move` into the party's place."""
    with override_settings(CAMPAIGN_DIR=str(tmp_path / "campaigns")):
        c = cm.new_campaign("s4-known", seed=7)
    scene = c.scene
    scene.pc().background = "apprenticed"
    scene.acquainted = ["ent-wenna", "ent-other"]
    who = scene.add(instantiate("guildhand", scene=scene, name="Wenna",
                                world_entity_id="ent-wenna"))
    assert who.has_state("bond.knows-you")
    held = [e for e in who.effects if "bond.knows-you" in e.tags]
    assert [e.source for e in held] == ["background:apprenticed"]
    assert [e.origin for e in held] == ["background:apprenticed"]
    stranger = scene.add(instantiate("guildhand", scene=scene, name="Stranger",
                                     world_entity_id="ent-nobody"))
    assert not stranger.has_state("bond.knows-you")
    other = next(p.id for p in c.engine().places() if p.id != scene.at)
    later = scene.arrive(instantiate("guildhand", scene=scene, name="Other",
                                     world_entity_id="ent-other"), place_id=other)
    scene.move(later.ref, scene.at)
    assert later.has_state("bond.knows-you")
    # Once: a second arrival does not stack a second bond.
    scene.move(who.ref, scene.at)
    assert len([e for e in who.effects if "bond.knows-you" in e.tags]) == 1


# --- refusals: one code, one payload ------------------------------------------------------

def test_player_fixable_is_exactly_the_registers_set():
    """Register §2.6. A code is player-fixable when the refusing fact is the character's
    own state or the player's own words — never the plan's choice of ref or param."""
    assert PLAYER_FIXABLE == frozenset({
        "unprepared", "no_slots", "not_known", "not_on_list", "too_high",
        "ability_too_low", "not_your_turn", "no_aim", "out_of_range",
        "no_line_of_effect", "no_such_object", "no_such_weapon", "out_of_reach",
        "absent_ground"})
    assert "no_such_target" not in PLAYER_FIXABLE and "wrong_aim" not in PLAYER_FIXABLE


def test_intent_error_derives_who_can_fix_it_from_its_code():
    """One stored field (`code`), one derived (`fixable_by`): A's `fixable_by` and E's
    `code` unified, and the existing `for_a_person` reused rather than duplicated."""
    plain = IntentError("no such thing", check="legality")
    assert (plain.code, plain.fix, plain.fixable_by) == ("", None, "plan")
    assert plain.for_a_person == ""
    e = IntentError("burning hands is not prepared", check="legality", index=0,
                    for_a_person="You have not prepared Burning Hands.",
                    code="unprepared", fix={"kind": "prepare", "spell": "burning-hands"})
    assert e.fixable_by == "player"
    assert e.fix == {"kind": "prepare", "spell": "burning-hands"}
    assert e.for_a_person.startswith("You have not")
    assert IntentError("x", code="no_such_target").fixable_by == "plan"
    assert IntentError("x", code="wrong_aim").fixable_by == "plan"
    assert isinstance(e, ValueError) and str(e) == "burning hands is not prepared"


_OLD_OUTCOME_KEYS = ["intent_id", "op", "status", "rolls", "dc", "verdict", "margin",
                     "effects", "tell", "because"]


def test_an_outcome_emits_the_new_keys_only_when_set():
    """§2.0: a new outcome key is emitted only when set, so every turn log and replay
    written before this pass reads back unchanged — the ten keys, in their order."""
    plain = Outcome(intent_id="i1", op="cast")
    assert list(plain.as_dict()) == _OLD_OUTCOME_KEYS
    assert list(_rehydrate(plain.as_dict()).as_dict()) == _OLD_OUTCOME_KEYS
    coded = Outcome(intent_id="i2", op="cast", status="refused", tell="Not prepared.",
                    code="unprepared", for_a_person="You have not prepared it.",
                    fix={"kind": "prepare", "spell": "burning-hands"})
    d = coded.as_dict()
    assert list(d) == _OLD_OUTCOME_KEYS + ["code", "for_a_person", "fix"]
    back = _rehydrate(json.loads(json.dumps(d)))
    assert (back.code, back.for_a_person, back.fix) == (
        "unprepared", "You have not prepared it.",
        {"kind": "prepare", "spell": "burning-hands"})
    assert back.as_dict() == d
    only_code = Outcome(intent_id="i3", op="attack", code="out_of_reach").as_dict()
    assert list(only_code) == _OLD_OUTCOME_KEYS + ["code"]


def test_the_refuse_door_takes_the_code_and_says_nothing_new_without_it():
    """`Engine._refuse(intent, why, *, code, for_a_person, fix)`: the signature only in
    S4, and a refusal made the old way is the same ten keys it always was."""
    params = inspect.signature(Engine._refuse).parameters
    assert list(params) == ["self", "intent", "why", "code", "for_a_person", "fix"]
    assert all(params[k].kind is inspect.Parameter.KEYWORD_ONLY
               for k in ("code", "for_a_person", "fix"))
    s = Scene()
    s.add(load_pc("fixtures/pc-kesst.json"))
    e = Engine(s)
    intent = Intent(op="cast", actor="pc", id="i9", because="t")
    old = e._refuse(intent, "  Not   prepared. ")
    assert list(old.as_dict()) == _OLD_OUTCOME_KEYS
    assert old.status == "refused" and old.tell == "Not prepared."
    new = e._refuse(intent, "Not prepared.", code="unprepared",
                    for_a_person="You have not prepared it.",
                    fix={"kind": "prepare", "spell": "x"})
    assert (new.code, new.fix["kind"]) == ("unprepared", "prepare")


# --- persisted fields ---------------------------------------------------------------------

def test_the_actors_new_fields_are_omitted_at_default_and_round_trip():
    """`Actor.described_as` (A) and `Actor.loadout` (E): absent from a sheet that has
    never had them, so every roster file and save on disk reads back unchanged."""
    pc = load_pc("fixtures/pc-kesst.json")
    d = to_dict(pc)
    assert "described_as" not in d and "loadout" not in d
    assert from_dict(d).described_as == [] and from_dict(d).loadout == {}
    pc.described_as = ["A lean woman with ink on her fingers.", "She squints."]
    pc.loadout = {"magic-missile": 2, "sleep": 1}
    d = to_dict(pc)
    back = from_dict(json.loads(json.dumps(d)))
    assert back.described_as == pc.described_as and back.loadout == pc.loadout


def _as_the_base_build_wrote_it(path: Path) -> str:
    """The same save with the six new scene keys removed, dumped as `save` dumps — which
    is byte for byte what the Phase-1 base build wrote, since the new keys are appended
    after every old one and the rest of the writer is untouched."""
    data = json.loads(path.read_text(encoding="utf-8"))
    for k in NEW_SCENE_KEYS:
        data["scene"].pop(k, None)
    return json.dumps(data, indent=1)


def test_an_old_save_round_trips_byte_identically(worlds, tmp_path):
    """G1 (register §3.5): "Old saves round-trip byte-identically. New keys are omitted
    at default." An old save carries no `story_seed`; load derives it from the campaign
    id (`opening._seed_from`), and save leaves it out again because it still equals that
    derivation — writing it would have changed every one of the owner's saves on the
    first turn after the update."""
    with override_settings(CAMPAIGN_DIR=str(tmp_path / "campaigns")):
        c = cm.new_campaign("s4-old", seed=7, world_source=str(worlds.source))
        path = c.save()
        old = _as_the_base_build_wrote_it(path)
        path.write_text(old, encoding="utf-8")
        again = cm.Campaign.load(path)
        assert again.scene.story_seed == opening._seed_from("s4-old")
        assert again.story_seed == again.scene.story_seed
        assert again.seed == 7
        again.save()
        assert path.read_text(encoding="utf-8") == old


def _owners_saves() -> list[Path]:
    root = Path(os.environ.get("LOCALAPPDATA", "")) / "PathfinderGM" / "campaigns"
    return [root / n for n in ("bobby.json", "bobby.json.1", "bobby.json.2", "bobby.json.3")]


@pytest.mark.parametrize("save", _owners_saves(), ids=lambda p: p.name)
def test_the_owners_real_saves_round_trip_byte_identically(save, tmp_path, monkeypatch):
    """The saves the 2026-09-28 playtest was measured on, read in place and never copied
    into the repository (the owner's ruling: player data stays out). Measured before this
    change: load → save reproduced every scene key of all four exactly, and the file
    differed only in `world_source`, which is the install's own path. So that line is
    set aside and the rest must match byte for byte. Skips on any machine without them."""
    if not save.is_file():
        pytest.skip(f"{save.name} is not on this machine")
    from play import roster

    # Bobby is an asura, a homebrew race: the sheet only validates beside its homebrew.
    data_root = tmp_path / "data"
    (data_root / "campaigns").mkdir(parents=True)
    brew = save.parent.parent / "homebrew"
    if brew.is_dir():
        shutil.copytree(brew, data_root / "homebrew")
    work = data_root / "in" / save.name
    work.parent.mkdir()
    shutil.copy(save, work)
    monkeypatch.setattr(roster, "record", lambda *a, **k: None)
    original = work.read_text(encoding="utf-8")
    with override_settings(CAMPAIGN_DIR=str(data_root / "campaigns")):
        c = cm.Campaign.load(work)
        assert c.scene.story_seed == opening._seed_from(c.id)
        written = c.save().read_text(encoding="utf-8")

    def without_source(text: str) -> str:
        return "\n".join(line for line in text.split("\n")
                         if not line.startswith(' "world_source": '))

    assert not any(f'"{k}":' in written for k in NEW_SCENE_KEYS)
    assert without_source(written) == without_source(original)


def test_new_scene_keys_are_omitted_at_default_and_kept_when_set(tmp_path):
    """Every new key is written only when it differs from its default and read with
    `.get(key, default)`; unknown keys inside a conversation entry are kept (§2.4)."""
    with override_settings(CAMPAIGN_DIR=str(tmp_path / "campaigns")):
        c = cm.new_campaign("s4-keys", seed=None)
        path = c.save()
        scene = json.loads(path.read_text(encoding="utf-8"))["scene"]
        # A fresh campaign's story seed is random, so it is written; the rest are at default.
        assert "story_seed" in scene
        assert not any(k in scene for k in NEW_SCENE_KEYS if k != "story_seed")
        c.scene.start = {"id": "called-to-the-cage", "kind": "injury", "where": "arena",
                         "slots": {"lead": "c2"}, "hand_off": {"kind": "check"},
                         "tells": ["The cage door is open."]}
        c.scene.spoken_for = ["ent-a", "ent-b"]
        c.scene.acquainted = ["ent-a"]
        c.scene.conversation_log = [{"n": 1, "t": 600, "beat": 3, "who": "c2", "name": "Drenn",
                                     "to": "you", "kind": "line", "text": "You!",
                                     "among": ["c2"], "src": "tag", "later_key": 5}]
        c.scene.conversation_seq = 1
        c.save()
        again = cm.Campaign.load(path)
    for k in NEW_SCENE_KEYS:
        assert getattr(again.scene, k) == getattr(c.scene, k), k
    assert again.scene.conversation_log[0]["later_key"] == 5


def test_the_story_seed_is_stable_and_is_not_the_dice_seed(tmp_path):
    """docs/design-c-starts.md §5's trap: `Campaign.engine()` builds `Dice(self.seed)` on
    every call, so a fixed `seed` would replay the same rolls every turn. `seed` stays
    `None` (fresh entropy per engine); the story's seed lives on the scene, survives a
    load, and is read through a property with no stored mirror."""
    with override_settings(CAMPAIGN_DIR=str(tmp_path / "campaigns")):
        c = cm.new_campaign("s4-seed")
        assert c.seed is None
        seed = c.story_seed
        assert isinstance(seed, int) and 0 <= seed < 2 ** 31
        e1, e2 = c.engine(), c.engine()
        rolls_1 = [e1.dice.d20().faces[0] for _ in range(20)]
        rolls_2 = [e2.dice.d20().faces[0] for _ in range(20)]
        assert rolls_1 != rolls_2, "two engines replayed the same dice"
        path = c.save()
        assert json.loads(path.read_text(encoding="utf-8"))["seed"] is None
        again = cm.Campaign.load(path)
        assert again.story_seed == seed and again.seed is None
        again.save()
        assert cm.Campaign.load(path).story_seed == seed
    # Read-only properties; `start_id` too, and neither is a field of the save.
    with pytest.raises(AttributeError):
        again.story_seed = 3
    assert again.start_id == ""
    again.scene.start = {"id": "the-hiring-table"}
    assert again.start_id == "the-hiring-table"
    with pytest.raises(AttributeError):
        again.start_id = "x"
    import dataclasses

    assert {"story_seed", "start_id"}.isdisjoint(f.name for f in dataclasses.fields(cm.Campaign))


def test_a_given_seed_is_the_story_seed_too(tmp_path):
    """`new_campaign(seed=n)` — the tests' and tools' reproducible start — also fixes the
    story: `seed if seed is not None else secrets.randbits(31)`."""
    with override_settings(CAMPAIGN_DIR=str(tmp_path / "campaigns")):
        assert cm.new_campaign("s4-given", seed=7).story_seed == 7
