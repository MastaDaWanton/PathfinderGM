"""The brief-section registry (`gm/brief/`, fix pass S2, docs/fix-interfaces.md §2.2).

Six lanes of the 2026-09-28 fix pass each wanted lines in `prompts.scene_brief`, one
function in a 1,400-line file with one owner. S2 moved three inline blocks out into
members of a registry, and the promise of the move (gate G1, §3.5) is that nothing the
model reads changed: with only those three members registered, the brief is the same
bytes it was at `phase-1-base`.

What these tests prevent, in order: a move that changes a byte of the brief (measured by
the sampler at 657 of 657 briefs identical across every settlement of the three worlds,
and by every `scene_brief` call the existing suite makes); a discovery that globs beside
`__file__` and finds nothing once PyInstaller freezes the app; a helper module run as a
member; an order that depends on the filesystem's listing; facts that do not match what
the brief printed; a scaffold that drifts from the words its section prints, which would
leave Lane A's `brief_verbatim` check blind.
"""
from __future__ import annotations

import ast
import copy
import subprocess
import sys
import types
from pathlib import Path

import pytest

from gm import brief
from gm import prompts
from rules import places as places_mod
from rules.bestiary import instantiate
from rules.dice import Dice
from rules.engine import Engine, Scene

MOVED = ("here", "roads_out", "place_facts")
BASE_REF = "phase-1-base"


@pytest.fixture
def only_the_moved(monkeypatch):
    """The registry as S2 left it: the three moved members and nothing a later lane
    added. G1 is stated for exactly this registry."""
    real = brief.registered

    def moved_only(slot=None):
        return tuple(m for m in real(slot) if brief.short_name(m) in MOVED)

    monkeypatch.setattr(brief, "registered", moved_only)


def _party(world, sid, place_id=""):
    s = Scene(location_id=sid)
    pc = instantiate("guildhand", scene=s, name="PC")
    pc.kind = "pc"
    s.add(pc)
    e = Engine(s, Dice(seed=3), world=world)
    e.place_party(place_id)
    return s, e


def _stands(world, sid):
    """Where to stand in one settlement: its first place, one indoor place, the forest
    outside it — each once with the engine's places and once with the brief's own
    fallback, which is the path the engine-less callers take."""
    s, e = _party(world, sid)
    indoor = next((p for p in e.places() if p.id != e.here().id
                   and places_mod.is_indoors(p.id, p.terrain, p.shape)), None)
    yield "first", s, dict(here=e.here(), known=e.places(), recent=[], turn=1)
    yield "first, no engine", s, {}
    if indoor is not None:
        s, e = _party(world, sid, indoor.id)
        yield "inside", s, dict(here=e.here(), known=e.places(), secret=True)
        yield "inside, no engine", s, {}
    forest = places_mod.region_set(sid, "forest")[0].id
    s, e = _party(world, sid, forest)
    yield "forest", s, dict(here=e.here(), known=e.places())
    yield "forest, no engine", s, {}


# --- the move changed no byte --------------------------------------------------------------

def _old_place_block(world, scene, location, here=None, known=()):
    """`prompts.scene_brief` lines 857–935 at phase-1-base, frozen here verbatim (comments
    dropped) so the move stays checkable after the tag is gone. The one reformatting:
    the HERE line's f-string, which spanned two lines inside its braces, is on one."""
    lines = []
    if location:
        from rules import places as _places_for_scale

        lines.append(f"\nHERE: {location.name}, "
                     f"{_places_for_scale.what_it_is(_places_for_scale.scale_of(location)) or 'a place'}.")
        if not known:
            from rules import places as _places

            known = _places.for_scene(location, getattr(scene, "at", ""))
            here = _places.find(known, getattr(scene, "at", "")) or (known[0] if known else None)
        if here is not None and len(known) > 1:
            others = [p.name for p in known if p.id != here.id]
            lines.append(f"  The party is at {here.name}. Not anywhere else in "
                         f"{location.name}; they are there now.")
            lines.append(f"  THE PLACES HERE (the only ones that exist): "
                         f"{', '.join(p.name for p in known)}. To move between them use "
                         f'{{"op": "travel", "params": {{"place": "{others[0]}"}}}}. '
                         f"Anything else is refused, and so is a SECOND travel in the "
                         f"same plan — one journey a turn.")
            near = [p.name for p in known if p.id in (here.exits or ())]
            if near:
                lines.append(
                    f"  NEXT DOOR to {here.name}, and reached in one step: "
                    f"{', '.join(near)}. Everywhere else here is further off and is "
                    f"reached by walking through these — name the DESTINATION in the "
                    f"travel and the engine walks the way, through every place between, "
                    f"in one turn. Never plan the route yourself.")
            from rules import floorplan as _floorplan

            underfoot = _floorplan.describe(here.id, here.terrain, here.shape)
            if underfoot:
                lines.append(f"  UNDERFOOT at {here.name} (what is physically here, and "
                             f"what the map is drawn from): {underfoot}.")
        if world is not None:
            from rules import journey as _journey

            out = _journey.legs_from(world, getattr(location, "id", "") or "")
            if out:
                lines.append(
                    f"  ROADS OUT OF {location.name.upper()} (the only settlements that "
                    f"can be reached, and only by journey, which takes days): "
                    f"{', '.join(leg.to_name for leg in out)}.")
        # The one deliberate change since the freeze (Lane C, 2026-09-28, fix-interfaces
        # §3.4): the fact loop reads the other exports' keys after the eight, shows
        # "Urban Life" as "Daily life", and puts the stock "the city's" back to the
        # settlement's stated size. Everything above is still the base's bytes.
        from play.opening_prose import stated_scale
        from rules import geography

        scale = stated_scale(location)
        for key in ("Urban Life", "Social Classes", "Architecture", "Governance",
                    "Formal Power", "Shadow Power", "Tension", "Daily Norms",
                    "Daily Life", "Customs", "Conflict", "Landscape"):
            if location.fact(key):
                lines.append(f"  {geography.display_key(key)}: "
                             f"{geography.in_its_own_words(str(location.fact(key)), scale)}")
    return "\n".join(lines)


def _ctx(world, scene, location, here=None, known=(), **_):
    if location and not known:
        known = places_mod.for_scene(location, getattr(scene, "at", ""))
        here = places_mod.find(known, getattr(scene, "at", "")) or (known[0] if known else None)
    return brief.BriefContext(
        world=world, scene=scene, location=location, here=here, known=tuple(known),
        recent_events=None, recent=None, secret=False, turn=0, names_for=None,
        absent="", buying="", reading=None, player_text="")


def test_the_place_slot_is_the_old_inline_block_byte_for_byte(worlds, only_the_moved):
    """The durable half of G1: every settlement of every world, stood in its first
    place, indoors and in the forest, with and without the engine's places. The place
    slot's text is the old inline block's text exactly — a lost space before "ROADS OUT"
    or a reordered UNDERFOOT would each change what the model reads while every
    behavioural test still passed."""
    checked = 0
    for row in worlds.play.get("settlements") or []:
        location = worlds.get(row["id"])
        for label, scene, kw in _stands(worlds, row["id"]):
            want = _old_place_block(worlds, scene, location,
                                    kw.get("here"), kw.get("known", ()))
            got, _facts = brief.run("place", _ctx(worlds, scene, location, **kw))
            assert got == want, f"{location.name}, {label}"
            checked += 1
    assert checked >= 5 * len(worlds.play.get("settlements") or [])


def _base_prompts():
    """`gm/prompts.py` as it stood at the Phase-1 base, loaded as a module beside the
    live one; None when git or the tag is not to hand (a source export, a CI clone
    without tags)."""
    try:
        src = subprocess.run(["git", "show", f"{BASE_REF}:gm/prompts.py"],
                             capture_output=True, check=True, timeout=30).stdout
    except (OSError, subprocess.SubprocessError):
        return None
    mod = types.ModuleType("gm._prompts_at_base")
    mod.__package__ = "gm"
    mod.__file__ = "gm/_prompts_at_base.py"
    sys.modules[mod.__name__] = mod
    exec(compile(src.decode("utf-8"), mod.__file__, "exec"), mod.__dict__)
    return mod


def test_the_whole_brief_is_the_phase_1_base_brief(worlds, only_the_moved):
    """G1 as the register states it (§3.5): with only S2's three moved members
    registered, `scene_brief` is byte-identical to the base — the whole brief, not only
    the slot, because the slot's neighbours (`here` for the thread line, the fallback
    that fills it) moved too. The sampler measured 657 of 657 identical; this repeats it
    per world. It pins `phase-1-base` on purpose, so a Phase-2 lane that changes the
    brief deliberately retires it (the frozen-block test above carries on)."""
    # Retired as its docstring says a Phase-2 lane would: Lane C changed the fact loop
    # on purpose (2026-09-28); the frozen-block test above carries the rest.
    pytest.skip("retired by Lane C's place_facts change (fix-interfaces §3.4); the "
                "frozen-block test above carries on")
    base = _base_prompts()
    if base is None:
        pytest.skip(f"git or the {BASE_REF} tag is not available")
    checked = 0
    for row in worlds.play.get("settlements") or []:
        location = worlds.get(row["id"])
        for label, scene, kw in _stands(worlds, row["id"]):
            was = base.scene_brief(worlds, copy.deepcopy(scene), location, **kw)
            now = prompts.scene_brief(worlds, scene, location, **kw)
            assert now == was, f"{location.name}, {label}"
            checked += 1
    s = Scene(location_id="")
    s.add(instantiate("guildhand", scene=s, name="PC"))
    assert (prompts.scene_brief(worlds, s, None)
            == base.scene_brief(worlds, copy.deepcopy(s), None)), "no location at all"
    assert checked


# --- discovery -----------------------------------------------------------------------------

def test_the_three_moved_members_are_discovered_in_the_order_they_were_written():
    """Today's bytes put HERE before ROADS OUT before the fact keys, so their ORDERs
    must keep them there whatever a later lane registers between them."""
    names = [brief.short_name(m) for m in brief.registered("place")]
    assert [n for n in names if n in MOVED] == list(MOVED)
    orders = [(m.ORDER, brief.short_name(m)) for m in brief.registered()]
    assert orders == sorted(orders), "members run by (ORDER, module name)"
    for m in brief.registered():
        assert m.SLOT in brief.SLOTS and isinstance(m.SCAFFOLD, tuple)


def _fake_package(tmp_path, monkeypatch, files: dict[str, str]):
    root = tmp_path / "fakebrief"
    root.mkdir(parents=True)
    (root / "__init__.py").write_text("", encoding="utf-8")
    for name, body in files.items():
        (root / f"{name}.py").write_text(body, encoding="utf-8")
    monkeypatch.syspath_prepend(str(tmp_path))
    for key in [k for k in sys.modules if k == "fakebrief" or k.startswith("fakebrief.")]:
        monkeypatch.delitem(sys.modules, key)
    import importlib

    return importlib.import_module("fakebrief")


MEMBER = ("ORDER = {order}\nSLOT = 'people'\nSCAFFOLD = ()\n"
          "def section(ctx):\n    return '{name}', {{}}\n")


def test_discovery_orders_by_order_then_name_and_skips_helpers(tmp_path, monkeypatch):
    """Two lanes that pick the same ORDER must still get one answer on every machine —
    `iter_modules` lists in whatever order the directory or the frozen archive gives —
    and `_people.py`-style helpers are imported by members, never run as one."""
    pkg = _fake_package(tmp_path, monkeypatch, {
        "zeta": MEMBER.format(order=5, name="zeta"),
        "alpha": MEMBER.format(order=5, name="alpha"),
        "first": MEMBER.format(order=1, name="first"),
        "_helper": "def useful():\n    return 1\n",
    })
    found = brief.discover(pkg)
    assert [brief.short_name(m) for m in found] == ["first", "alpha", "zeta"]


def test_a_member_missing_its_contract_is_refused_with_the_fix_named(tmp_path, monkeypatch):
    """A file dropped in the package without `section` would otherwise fail on the first
    turn of play, far from the change that caused it."""
    pkg = _fake_package(tmp_path, monkeypatch, {"broken": "ORDER = 1\nSLOT = 'place'\n"})
    with pytest.raises(TypeError, match="leading '_'"):
        brief.discover(pkg)
    pkg = _fake_package(tmp_path / "b", monkeypatch, {
        "wrong": "ORDER = 1\nSLOT = 'room'\nSCAFFOLD = ()\ndef section(c):\n    return '', {}\n"})
    with pytest.raises(ValueError, match="one of"):
        brief.discover(pkg)


def test_discovery_never_reads_the_directory_beside_file():
    """CLAUDE.md: `__file__` lies once PyInstaller freezes the app — the members live in
    an archive with no directory to glob, and a glob there finds nothing and the brief
    silently loses its sections. Discovery goes through the package's `__path__`."""
    tree = ast.parse(Path("gm/brief/__init__.py").read_text(encoding="utf-8"))
    used = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}
    attrs = {n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)}
    assert "__file__" not in used
    assert not {"glob", "listdir", "iterdir", "scandir"} & attrs
    assert "iter_modules" in attrs


def test_run_refuses_a_slot_that_does_not_exist():
    """A typo'd slot would otherwise print nothing, silently."""
    with pytest.raises(ValueError, match="no brief slot"):
        brief.run("plaace", _ctx(None, Scene(location_id=""), None))


# --- the slots sit where the register says ------------------------------------------------

def _member(name, slot, order, text):
    mod = types.ModuleType(f"gm.brief.{name}")
    mod.ORDER, mod.SLOT, mod.SCAFFOLD = order, slot, ()
    mod.section = lambda ctx: (text, {"said": text.strip()})
    return mod


def test_a_new_member_lands_in_its_slot_between_its_neighbours(monkeypatch):
    """Where Phase 2's members will print: `land_around` (place 30) between ROADS OUT
    and the fact keys; a people section after the WHO IS HERE list — its IN
    CONVERSATION line included — and before what the character can do. A slot in the
    wrong place would put a fact where the model reads it as belonging to something
    else."""
    from world.loader import load_cached

    world = load_cached("fixtures/pangrella-campaign.json")
    sid = world.play["settlements"][0]["id"]
    s, e = _party(world, sid)
    real = brief.registered()
    extra = (_member("land_probe", "place", 30, "  LAND PROBE"),
             _member("people_probe", "people", 20, "\nPEOPLE PROBE"))
    everything = tuple(sorted(real + extra, key=lambda m: (m.ORDER, brief.short_name(m))))
    monkeypatch.setattr(brief, "registered",
                        lambda slot=None: tuple(m for m in everything
                                                if slot is None or m.SLOT == slot))
    report: dict = {}
    text = prompts.scene_brief(world, s, world.get(sid), here=e.here(), known=e.places(),
                               report=report)
    assert text.index("ROADS OUT") < text.index("LAND PROBE") < text.index("  Governance:")
    lines = text.split("\n")
    head, probe = lines.index("WHO IS HERE (these refs are the only ones that exist):"), \
        lines.index("PEOPLE PROBE")
    assert head < probe and all(ln.startswith("  ") for ln in lines[head + 1:probe - 1])
    assert lines[probe - 1] == ""  # the probe's own leading "\n"
    assert report["facts"]["land_probe"] == {"said": "LAND PROBE"}
    assert report["facts"]["people_probe"] == {"said": "PEOPLE PROBE"}


# --- the report --------------------------------------------------------------------------

def test_the_report_holds_what_each_section_printed(worlds, only_the_moved):
    """A narrator check reads `brief_facts` to learn what the model was shown (B's
    road_claimed, A's brief_verbatim). Facts that disagree with the printed brief would
    be the first law's error again: one fact, two stores, drifting. And asking for the
    report changes no byte of the brief."""
    row = (worlds.play.get("settlements") or [])[0]
    location = worlds.get(row["id"])
    s, e = _party(worlds, row["id"])
    kw = dict(here=e.here(), known=e.places())
    report: dict = {}
    text = prompts.scene_brief(worlds, s, location, report=report, reading={"x": 1},
                               player_text="I look around", **kw)
    assert text == prompts.scene_brief(worlds, s, location, **kw)
    facts = report["facts"]
    assert set(facts) == set(MOVED)
    here = facts["here"]
    assert here["here"] == e.here().id and here["settlement"] == location.name
    assert f"THE PLACES HERE (the only ones that exist): {', '.join(here['places'])}." in text
    assert f"NEXT DOOR to {here['here_name']}, and reached in one step: " \
           f"{', '.join(here['next_door'])}." in text
    roads = facts["roads_out"].get("roads") or []
    if roads:
        assert f"(the only settlements that can be reached, and only by journey, which " \
               f"takes days): {', '.join(roads)}." in text
    for key, value in (facts["place_facts"].get("facts") or {}).items():
        assert f"  {key}: {value}" in text


def test_a_failed_reading_reaches_no_section(monkeypatch):
    """`agent.reading` is `{"error": ...}` when the interpreter fails; a section reading
    its `actions` would find none and might say so as a fact. It arrives as None."""
    seen = []
    probe = _member("reading_probe", "people", 99, "")
    probe.section = lambda ctx: (seen.append((ctx.reading, ctx.player_text)) or ("", {}))
    monkeypatch.setattr(brief, "registered",
                        lambda slot=None: (probe,) if slot in (None, "people") else ())
    s = Scene(location_id="")
    s.add(instantiate("guildhand", scene=s, name="PC"))

    class World:
        name, secret, premise = "Testholme", "", {}

    prompts.scene_brief(World(), s, None, reading={"error": "timed out"}, player_text="hi")
    prompts.scene_brief(World(), s, None, reading={"actions": []})
    assert seen == [(None, "hi"), ({"actions": []}, "")]


def test_the_agent_hands_the_brief_the_reading_and_the_players_words(monkeypatch):
    """`plan_turn` is where a section keyed on the player's sentence (D's sought, the
    land-around trigger on a `leave`) gets it; a call site that forgot to pass it would
    leave those sections silent in play while every test of the section passed."""
    from gm import agent as agent_mod
    from world.loader import load_cached

    world = load_cached("fixtures/pangrella-campaign.json")
    sid = world.play["settlements"][0]["id"]
    s, e = _party(world, sid)
    got = {}

    class Stop(Exception):
        pass

    def spy(*a, **kw):
        got.update(kw)
        raise Stop

    monkeypatch.setattr(agent_mod.prompts, "scene_brief", spy)
    gm = agent_mod.GMAgent(world, e)
    with pytest.raises(Stop):
        gm.plan_turn("I walk to the gate", [], location=world.get(sid))
    assert got["player_text"] == "I walk to the gate"
    assert "reading" in got and got["reading"] is gm.reading


# --- the scaffold --------------------------------------------------------------------------

def test_the_scaffold_is_the_words_the_sections_print(worlds, only_the_moved):
    """Lane A's `brief_verbatim` flags prose that pastes a 4-gram of a section's fixed
    words (item 17.6). A SCAFFOLD edited apart from the f-string it describes would
    leave the check comparing against words the model never saw. Every gram must be
    found in a real brief where every block printed."""
    grams = brief.scaffold()
    assert grams and all(len(g) == brief.GRAM for g in grams)
    assert ("the", "only", "settlements", "that") in grams
    row = (worlds.play.get("settlements") or [])[0]
    s, e = _party(worlds, row["id"])
    text = prompts.scene_brief(worlds, s, worlds.get(row["id"]),
                               here=e.here(), known=e.places())
    assert "NEXT DOOR" in text and "UNDERFOOT" in text
    printed = brief.grams(text)
    missing = {g for m in brief.registered() for fixed in m.SCAFFOLD
               for g in brief.grams(fixed)} - printed
    if "ROADS OUT" not in text:
        from gm.brief import roads_out

        missing -= {g for f in roads_out.SCAFFOLD for g in brief.grams(f)}
    assert not missing, sorted(missing)
