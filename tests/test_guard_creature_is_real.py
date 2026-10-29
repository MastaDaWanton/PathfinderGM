"""The guard on a herb find is who the beat means, and a creature is never made a person.

The owner's report on 0.2.21 (2026-10-27, Planned narration): *"A Griol which is a medium
sized creature was described and large and then turned into a gnome."* The save (kept out of
the repository; these scenes are synthetic, in the same shape) had the whole path:

1. A forage found "a whole hollow of herbs … and a grioth sitting on it". The grioth was an
   actor (c8), brought in by `_bring_in` and holding its ground (`state.holding-ground`).
2. The excursion's scene call was told "a grioth (medium, monstrous)" — core.json prints
   the type truncated — and wrote "a massive creature … a large, monstrous figure". No
   other narrator was ever told its size.
3. "Approach the Grioth": the move closed on it, the reaction roll said it gave way, and
   `Scene.remove` took it out of the campaign IN THE SAME BATCH. The planned narrator then
   called it "the towering figure" and "the massive creature", with PEOPLE HERE NOW
   "nobody", and the beat reader, whose cast no longer held c8, answered "towering figure"
   new and here.
4. Seen-people made c9, "towering figure", a guildhand, race human, with the village's
   Gnome face; the next beat said "The towering figure is of the Gnome people", and it did
   daily rounds for the rest of the session.

The fixes, each pinned below: the batch's removals are remembered (`Scene.gone`) and shown
to the reader and the planned narrator as gone in this moment (`Scene.gone_in`); the
reader answers a closed question for every newcomer — person or creature — and a creature
is never made a body (play/aftermath/seen_people.py); every narrator is told a creature's
size and kind from its own record (`bestiary.body_words`).
"""
from __future__ import annotations

import pytest

from gm import beat_reader, planned, prompts
from play.aftermath import seen_people
from rules import bestiary, gathering, places
from rules.bestiary import instantiate
from rules.dice import Dice, Roll
from rules.engine import Engine, Outcome, Scene
from rules.sheet import load_pc
from tests.beat_reader import stub
from world.loader import load_cached

WORLD = load_cached("fixtures/aurvantis-campaign.json")
VORMOOR = WORLD.by_name("Vormoor", kind="CITY")

# The owner's beat's shape, written for the test (not copied from the save).
BEAT = ("You walk up to the towering figure. The creature turns away and is lost among the "
        "trees, and the hollow is open to you.")


def _forest():
    s = Scene(location_id=VORMOOR.id)
    s.add(load_pc("fixtures/pc-kesst.json"))
    e = Engine(s, Dice(seed=3), world=WORLD)
    there = places.region_set(VORMOOR.id, "forest")[0].id
    s.at = there
    for a in s.people.values():
        a.at = there
    return s, e


def _guarded(monkeypatch, s, e):
    """The owner's find: a guarded hollow of herbs with a grioth sitting on it."""
    row = bestiary.search(text="grioth", limit=5)
    row = next(r for r in row if r["id"] == "grioth")
    monkeypatch.setattr(gathering, "roll", lambda *a, **k: gathering.Encounter(
        "guarded", 98, creature=row, aggressive=False, yield_times=3))
    effects: list = []
    e._gathering_encounter(s.pc(), "forest", 1, "herbs", found={"monkshood": 6},
                           effects=effects)
    return effects[-1]["ref"]


def _gives_way(monkeypatch, s, e, ref):
    """The player closes on it and the reaction roll says it leaves (9 or more)."""
    real = e.dice.roll

    def roll(notation, *args, **kwargs):
        if str(kwargs.get("label") or "").startswith("how "):
            return Roll(die="2d6", faces=[12], label=kwargs["label"])
        return real(notation, *args, **kwargs)

    monkeypatch.setattr(e.dice, "roll", roll)
    s.zones[ref] = "near"
    return e._holding_ground_settles()


# --- what the grioth is ---------------------------------------------------------------------

def test_the_grioth_is_a_medium_monstrous_humanoid_and_no_person():
    """Bestiary 5's grioth is Medium; core.json prints its type as "monstrous", and the
    scene call was told "a grioth (medium, monstrous)". The kind is said in the book's
    word, with its size from the record.

    The data changed on 2026-10-29: the Bestiaries were re-read with option D
    (docs/bestiary-licensing.md) and core.json now prints the two-word types whole —
    "monstrous humanoid", "magical beast" — where it had "monstrous" and "magical". The
    body words read the same, which is what this still proves."""
    assert bestiary.raw("grioth")["size"] == "medium"
    assert bestiary.raw("grioth")["creature_type"] == "monstrous humanoid"  # no longer cut
    assert not bestiary.has_a_people("grioth")
    assert bestiary.body_words("grioth") == "Medium monstrous humanoid"
    assert bestiary.body_said("Medium monstrous humanoid") == \
        "a Medium monstrous humanoid, about a grown man's height — no bigger"
    # A person's body is their people's and their face's, never a block's.
    assert bestiary.body_words("guildhand") == ""
    # The other truncation, 107 blocks: "magical" is a magical beast (whole in the data
    # since 2026-10-29).
    owlbear = bestiary.raw("owlbear")
    assert owlbear["creature_type"] == "magical beast"
    assert bestiary.body_words("owlbear") == "Large magical beast"


# --- the batch's removals are remembered ----------------------------------------------------

def test_the_guard_that_gives_way_is_gone_in_the_batch_that_tells_it(monkeypatch):
    """Measured on the owner's save: the stance outcome "The grioth gives way as you close
    and leaves the thicket to you" came in the same batch as `Scene.remove`, so nothing the
    beat was read against held c8. `gone_in` answers who the batch's outcomes took."""
    s, e = _forest()
    ref = _guarded(monkeypatch, s, e)
    assert s.actors[ref].size == "medium"
    out = _gives_way(monkeypatch, s, e, ref)
    assert any("gives way" in o.tell for o in out)
    assert ref not in s.people, "it left the campaign, as the engine's rule says"
    gone = s.gone_in(out)
    assert gone == [{"ref": ref, "name": "grioth", "body": "Medium monstrous humanoid",
                     "people": "", "at": s.at, "minute": s.clock_minutes}]
    # Only who THIS batch speaks of: an outcome that names nobody gone names nobody.
    assert s.gone_in([Outcome("i1", "move", effects=[{"ref": "pc", "kind": "position"}])]) == []


def test_the_beat_after_still_knows_who_left_here_within_the_hour(monkeypatch):
    """Measured live on this branch: the turn after the grioth gave way, "I look for the
    towering figure in the trees" came back "tracks left by the towering figure", and with
    only the batch's removals shown (none that turn) the reader answered a newcomer, a
    person. Whoever left THIS place within the hour is still shown; another place's, or an
    older going, is not."""
    s, e = _forest()
    ref = _guarded(monkeypatch, s, e)
    _gives_way(monkeypatch, s, e, ref)
    assert [g["ref"] for g in s.gone_lately()] == [ref]
    s.advance(Scene.GONE_WITHIN + 1, charge_body=False)
    assert s.gone_lately() == []
    s2, e2 = _forest()
    ref2 = _guarded(monkeypatch, s2, e2)
    _gives_way(monkeypatch, s2, e2, ref2)
    s2.at = places.region_set(VORMOOR.id, "hills")[0].id
    assert s2.gone_lately() == [], "somebody who left another place is not here's"


def test_gone_keeps_only_the_latest_removals():
    """Transient and bounded: a removal is told in the batch that made it."""
    s, _ = _forest()
    for i in range(Scene.GONE_KEPT + 5):
        a = instantiate("guildhand", scene=s, name=f"carter {i}")
        s.add(a)
        s.remove(a.ref)
    assert len(s.gone) == Scene.GONE_KEPT


# --- the reader: the gone are offered, and nobody is made of them -------------------------

def test_the_reader_is_shown_the_guard_gone_and_offered_its_code(monkeypatch):
    """The reader's people call is shown "Gone from here just now" with the
    grioth's size and kind, and every mention may be answered with its code — the enum
    is the engine's (Ollama enforces it, 6/6)."""
    s, e = _forest()
    ref = _guarded(monkeypatch, s, e)
    gone = s.gone_in(_gives_way(monkeypatch, s, e, ref))
    calls: list = []
    reading = stub.read(BEAT, s, engine=e, who={"the towering figure": ref,
                                                 "the creature": ref},
                        gone=gone, calls=calls)
    kind, schema, msgs = calls[0]
    assert kind == "people"
    asked = msgs[-1]["content"]
    assert "Gone from here just now" in asked
    assert f"{ref}: grioth — Medium monstrous humanoid" in asked
    for mid in (m.id for m in reading.mentions):
        assert ref in schema["properties"][mid]["enum"]
    assert schema["properties"]["new"]["items"]["properties"]["being"]["enum"] == \
        ["person", "creature"]
    assert reading.gone == {ref}
    assert not reading.newcomers
    assert {m.ref for m in reading.mentions} == {ref}


def test_replay_before_and_after_the_towering_figure_is_no_gnome(monkeypatch):
    """The owner's turn replayed: BEFORE, the reader had no code for the grioth and
    answered "the towering figure" new and here — and seen-people made a person of it with
    this place's people's face (c9 in the save, "of the Gnome people"). AFTER, the same
    words are the gone grioth, and nobody is made."""
    s, e = _forest()
    ref = _guarded(monkeypatch, s, e)
    gone = s.gone_in(_gives_way(monkeypatch, s, e, ref))
    before = set(s.people)

    # Before: the reading the live reader gave, with nothing gone shown to it.
    then = stub.read(BEAT, s, engine=e, who={"the towering figure": "new"},
                     new=[("the towering figure", "here", "towering figure")])
    rows = seen_people.step(stub.ctx(s, then, text=BEAT, engine=e, world=WORLD, turn=7))
    made = [r["made"] for r in rows if r.get("made")]
    assert len(made) == 1, rows
    figure = s.people[made[0]]
    assert figure.from_template == "guildhand" and figure.appearance, \
        "the defect, reproduced: a guildhand with a people's face"

    # After: the same beat read against a fresh copy of the scene, the grioth shown gone.
    s2, e2 = _forest()
    ref2 = _guarded(monkeypatch, s2, e2)
    gone2 = s2.gone_in(_gives_way(monkeypatch, s2, e2, ref2))
    before2 = set(s2.people)
    now = stub.read(BEAT, s2, engine=e2, who={"the towering figure": ref2,
                                               "the creature": ref2}, gone=gone2)
    rows2 = seen_people.step(stub.ctx(s2, now, text=BEAT, engine=e2, world=WORLD, turn=7))
    assert set(s2.people) == before2, rows2
    assert not any(r.get("made") for r in rows2)
    assert gone and before    # the first scene's fixtures were real


def test_a_newcomer_the_reader_calls_a_creature_is_never_made_a_person():
    """Without the gone list (a creature the engine never held), the reader's closed
    answer decides: a creature newcomer makes no body and no population record. A person
    newcomer is still made, as the owner's 2026-10-01 ruling says."""
    s, e = _forest()
    text = ("A towering figure steps out of the thicket. Behind it a woman in a grey cloak "
            "watches from the path.")
    reading = stub.read(text, s, engine=e,
                        who={"a towering figure": "new", "a woman": "new"},
                        new=[("a towering figure", "here", "towering figure", "creature"),
                             ("a woman", "here", "woman in a grey cloak", "person")])
    assert [n.being for n in reading.newcomers] == ["creature", "person"]
    before = set(s.people)
    rows = seen_people.step(stub.ctx(s, reading, text=text, engine=e, world=WORLD, turn=3))
    assert any(r.get("why", "").startswith("a creature, not a person") for r in rows)
    made = [s.people[r] for r in set(s.people) - before]
    assert len(made) == 1 and "woman" in made[0].name
    assert not any("towering" in str(p.get("phrase") or "")
                   for p in (s.population or {}).values())


# --- the narrators are told its size ---------------------------------------------------------

def test_the_planned_narrator_is_told_its_size_and_that_it_is_gone(monkeypatch):
    """No slot gave a size, and on the approach beat PEOPLE HERE NOW was "nobody" while the
    act's tell named the grioth. Now the creature is said with its size and kind while it
    is here, and as gone in this moment on the beat that removes it."""
    s, e = _forest()
    ref = _guarded(monkeypatch, s, e)
    here = {p["ref"]: p["what"] for p in planned.present(e)}
    assert "a Medium monstrous humanoid, about a grown man's height — no bigger" in here[ref]
    out = _gives_way(monkeypatch, s, e, ref)
    msgs = planned.plan_messages("BRIEF", [{"key": "fact1", "say": "x"}], planned.present(e),
                                 "the forest", gone=planned.gone(e, out))
    user = msgs[1]["content"]
    assert "PEOPLE HERE NOW: nobody but the player's character." in user
    assert (f"GONE IN THIS MOMENT (the engine took them out of the scene; write them going, "
            f"never staying): grioth ({ref}; a Medium monstrous humanoid") in user


def test_a_person_is_told_no_size_from_a_block():
    """A person's body is their people's and their face's (rules/faces.py): the size line
    is for creatures only, so a world's Gnome is never told "Medium" by a guildhand
    block's default."""
    s, e = _forest()
    clerk = instantiate("guildhand", scene=s, name="clerk")
    s.add(clerk)
    clerk.at = s.at
    assert planned._body(clerk) == ""
    brief = prompts.scene_brief(WORLD, s, VORMOOR, [])
    assert "What it is (fact" not in brief


def test_the_free_brief_says_what_the_creature_is(monkeypatch):
    s, e = _forest()
    ref = _guarded(monkeypatch, s, e)
    brief = prompts.scene_brief(WORLD, s, VORMOOR, [])
    line = next(ln for ln in brief.splitlines() if ln.strip().startswith(f"{ref} —"))
    assert ("What it is (fact — its size and kind; never write it bigger or smaller): "
            "a Medium monstrous humanoid, about a grown man's height — no bigger.") in line


def test_the_excursion_scene_is_told_the_kind_and_how_big(monkeypatch):
    """The scene call that wrote "a massive creature … a large, monstrous figure" was
    told "a grioth (medium, monstrous)"."""
    from types import SimpleNamespace

    from play import craft_views

    s, e = _forest()
    ref = _guarded(monkeypatch, s, e)
    c = SimpleNamespace(scene=s, location=None, world=WORLD, biome="forest")
    f = craft_views.encounter_facts(c, {"ref": ref, "creature": "grioth", "spot": "thicket",
                                        "stance": "It holds."}, [], "the forest", "noon")
    assert f["kind"] == "monstrous humanoid" and f["size"] == "medium"
    said = craft_views._scene_messages(f)[1]["content"]
    assert "What is there: a grioth (Medium monstrous humanoid)" in said
    assert "How big it is: Medium — about a grown man's height — no bigger." in said
    assert "a medium monstrous humanoid" in craft_views.floor_scene(f)


@pytest.mark.parametrize("template", ["guildhand", "watchman"])
def test_hand_written_townsfolk_are_people(template):
    assert bestiary.body_words(template) == ""


# --- the read back: a size the page gives that the record does not ---------------------------

def _size_ctx(e, text, reading, outcomes=()):
    from gm.checks import BeatContext

    return BeatContext(
        door="turn", text=text, player_text="", engine=e, scene=e.scene, world=WORLD,
        location=None, reading=None, outcomes=tuple(outcomes), tells=(), said=(),
        attribution=reading, brief="", brief_facts={}, pull=None, was_at="", acting="",
        turn=0, reader={"model": "stub", "host": "", "provider": "ollama"})


@pytest.mark.parametrize("said,record,wrong", [
    # The owner's: a Medium grioth written large or huge.
    ("large", "medium", True), ("huge", "medium", True),
    # And the other way: a Large ogre "no taller than your waist".
    ("small", "large", True),
    # Above a man every size is "bigger than a man": a towering ogre read as Huge, a
    # dragon blotting out the sky read as Colossal (probed 2 of 2 each), are prose.
    ("huge", "large", False), ("colossal", "huge", False), ("large", "large", False),
    # At a man's size and below, one step is prose and two is wrong.
    ("small", "medium", False), ("tiny", "small", False), ("tiny", "medium", True),
    ("not said", "medium", False), ("medium", "", False),
])
def test_what_counts_as_the_wrong_size(said, record, wrong):
    from gm.checks import creature_size

    assert creature_size.contradicts(said, record) is wrong


def test_the_read_back_asks_about_the_gone_grioth_by_the_pages_own_words(monkeypatch):
    """The approach beat called the grioth only by what it was not: "the towering figure".
    The check asks one closed question about the sentences the reader gave to the grioth
    (gone in this batch), naming the page's words, and a Large answer for a Medium record is
    a finding whose fix names the record."""
    from gm import beat_verify
    from gm.checks import creature_size

    s, e = _forest()
    ref = _guarded(monkeypatch, s, e)
    out = _gives_way(monkeypatch, s, e, ref)
    text = ("You walk up to the towering figure. The massive creature turns away and is "
            "lost among the trees.")
    reading = stub.read(text, s, engine=e, who={"the towering figure": ref,
                                                 "the massive creature": ref},
                        gone=s.gone_in(out))
    asked = []

    def fake(passage, name, words=(), **kw):
        asked.append((passage, name, tuple(words)))
        return "large"

    monkeypatch.setattr(beat_verify, "ENABLED", True)
    monkeypatch.setattr(creature_size, "ask", fake)
    creature_size._ASKED.clear()
    found = creature_size.find(_size_ctx(e, text, reading, out))
    assert asked == [(text, "the grioth", ("the towering figure", "The massive creature"))]
    assert [f.kind for f in found] == ["creature-size"]
    assert "Medium — about a grown man's height — no bigger" in found[0].fix_hint
    assert found[0].sentences == ("You walk up to the towering figure.",
                                  "The massive creature turns away and is lost among the "
                                  "trees.")


def test_a_person_and_an_unsized_page_are_never_findings(monkeypatch):
    """A person is never asked (their body is their face's); a creature the page gives no
    size is "not said" and passes."""
    from gm import beat_verify
    from gm.checks import creature_size

    s, e = _forest()
    ref = _guarded(monkeypatch, s, e)
    clerk = instantiate("guildhand", scene=s, name="clerk")
    s.add(clerk)
    clerk.at = s.at
    text = "The clerk is a towering man. The grioth watches you from the thicket."
    reading = stub.read(text, s, engine=e, who={"The clerk": clerk.ref, "The grioth": ref})
    asked = []
    monkeypatch.setattr(beat_verify, "ENABLED", True)
    monkeypatch.setattr(creature_size, "ask",
                        lambda p, n, w=(), **kw: asked.append(n) or "not said")
    creature_size._ASKED.clear()
    assert creature_size.find(_size_ctx(e, text, reading)) == []
    assert asked == ["the grioth"]
