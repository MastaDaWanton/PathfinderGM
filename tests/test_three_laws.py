"""The three laws of docs/states-effects-tells.md, enforced by grep rather than memory.

This repo's own finding, measured on its GM: prompt rules fail and keep failing;
mechanical detection holds. A design contract that lives only in prose is a prompt
rule — for the next contributor and for the next model session alike — so every claim
of the contract that CAN be checked by code is checked here. Each test's docstring
names the incident that earned it. The judgment-shaped half of the contract lives in
.claude/skills/states-effects-tells/SKILL.md, and the last test here keeps that file
from rotting: every path and symbol the skill names must still resolve.
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

# --- law 1: one vocabulary ------------------------------------------------------------


def test_every_condition_is_in_the_tag_vocabulary():
    """Stage 1's whole point: a petrified actor was lootable by one hand-rolled test
    and alive by another, because each question matched strings. The unknown-key
    fallback self-tags under `condition.<key>` — which keeps homebrew playing but
    would silently drop a SHIPPED condition out of `state.down` and its family. So
    every key the condition table ships must have a real entry in the vocabulary."""
    from rules.states import TAGS
    from rules.tables import CONDITIONS

    missing = set(CONDITIONS) - set(TAGS)
    assert not missing, (
        f"conditions with no tag entry (they would self-tag and vanish from every "
        f"state.* family question): {sorted(missing)}")


# --- law 2: one applicator, one ticker ------------------------------------------------


# Every place in the app that counts a clock down, and the stage that folds it into
# the one ticker. An allowlist rather than a count, because a count cannot tell a site
# being REMOVED from one being MOVED: stage 4c could fold the compulsion clock in and
# introduce another elsewhere, and a count would not notice. Each line is an exemption
# somebody had to write, and deleting one is that stage's own proof.
_CLOCK_SITES = {
    "rules/sheet.py": "tick_effects — the one actor ticker, and the destination",
    "rules/engine.py": "stage 4c: wards and manifestations become scene effects",
    "rules/guards.py": "stage 4c: a guard's uses_left is a charge, not a clock",
}


def test_every_clock_that_counts_down_is_accounted_for():
    """Before stage 2, `tick_conditions` held one expiry loop per mechanism — three
    copies of the same six lines — and a mechanism added without a fourth loop was one
    that never wore off. The actor has one ticker now; the app still has five clocks.

    The first version of this test read two files and concluded the law held. It could
    see one of the five, which is worse than not testing it at all: three of the four
    it could not see tick only inside an encounter, so a compulsion applied out of a
    fight lasts until the next fight starts."""
    # Both shapes. `x_left -= n` is the obvious one; `x_left = max(0, x_left - n)` is
    # how `tick_pools` writes a cooldown, so the first version of this test could not
    # see the fifth clock at all — it measured four of five and reported the law upheld.
    pattern = re.compile(r"\b\w+_left\s*-=|\b(\w+_left)\s*=.*\1\s*-")
    found: dict[str, list[int]] = {}
    for path in sorted(Path(".").glob("*/*.py")):
        if path.parts[0] not in ("rules", "play", "gm", "world"):
            continue
        # Code, not prose: a comment quoting `rounds_left -= rounds` to explain why a
        # bound exists is documentation, and counting it as a clock made this test fail
        # on its own explanation.
        source = re.sub(r'"""(?:.|\n)*?"""', "", path.read_text(encoding="utf-8"))
        for n, line in enumerate(source.splitlines(), 1):
            if pattern.search(re.sub(r"#.*$", "", line)):
                found.setdefault(path.as_posix(), []).append(n)
    unlisted = {k: found[k] for k in sorted(set(found) - set(_CLOCK_SITES))}
    assert not unlisted, (
        f"a clock counts down outside the one ticker and outside the allowlist: "
        f"{unlisted}. Model it as an ActiveEffect, or add it to _CLOCK_SITES naming "
        f"the stage that will fold it in.")
    gone = set(_CLOCK_SITES) - set(found) - {"rules/sheet.py"}
    assert not gone, (
        f"these clocks are folded in — delete them from _CLOCK_SITES: {sorted(gone)}")


def test_no_fourth_store_grows_back_on_the_actor():
    """Conditions, buffs, temporary hit points and coatings were four separately
    maintained lists before stage 2; `effects` is the one store and the four are
    read-only views. A new dataclass field on Actor holding timed records would be
    the fifth mechanism growing back. Every field whose type mentions the timed
    record classes must be the one store."""
    tree = ast.parse(Path("rules/sheet.py").read_text(encoding="utf-8"))
    actor = next(n for n in ast.walk(tree)
                 if isinstance(n, ast.ClassDef) and n.name == "Actor")
    timed = ("ActiveEffect", "Condition", "Buff", "TempPool")
    offenders = [
        s.target.id for s in actor.body
        if isinstance(s, ast.AnnAssign) and isinstance(s.target, ast.Name)
        and any(t in ast.dump(s.annotation) for t in timed)
    ]
    assert offenders == ["effects"], (
        f"Actor grew a parallel timed store beside `effects`: {offenders}. "
        f"Model it as an ActiveEffect kind instead.")


def test_the_condition_views_are_never_assigned():
    """The one applicator is bypassed the moment somebody assigns a filtered list to
    a view. Found live: a test cleanup wrote `pc.conditions = [...]` — the last
    place anything edited a condition behind the engine's back — and it silently
    did nothing once conditions became a property. Nothing in the app may assign
    to the view names; the store is edited through apply_effect and the shims."""
    # Assignment AND the mutating methods, across every view: `.append` on a view
    # builds a list, mutates it and throws it away, which is how a DR granted in a
    # test silently did nothing until the suite caught it.
    views = "conditions|buffs|temp_pools|immunities|resistances|vulnerabilities|reductions"
    pattern = re.compile(
        rf"\.({views})\s*(?:=[^=]|\.append|\.remove|\.extend|\.pop|\.clear)")
    offenders = []
    for path in Path(".").glob("*/*.py"):
        if path.parts[0] not in ("rules", "gm", "play", "tools", "world"):
            continue
        # survival.Toll carries its own `conditions` — a list of condition NAMES a
        # hardship inflicts, not the Actor view — and is allowed to assign it.
        if path.name == "survival.py":
            continue
        # sheet.py implements the views; an implementation may touch what it implements.
        if path.name == "sheet.py":
            continue
        for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if pattern.search(line) and "self.effects" not in line:
                offenders.append(f"{path}:{n}: {line.strip()}")
    assert not offenders, (
        "assignment to a read-only effect view (use apply_effect / remove_effects "
        "/ the shims):\n" + "\n".join(offenders))


# What an author may aim a bonus at, and how the sheet is asked for the number it
# ought to move. The vocabulary is the promise; this table is whether it is kept.
_REACHES = {
    ("combat_mod", "attack"): lambda a: sum(m.value for m in a.attack_modifiers()),
    ("combat_mod", "damage"): lambda a: sum(m.value for m in a.damage_modifiers()),
    ("combat_mod", "ac"): lambda a: a.ac(),
    ("combat_mod", "cmb"): lambda a: sum(m.value for m in a.cmb_modifiers()),
    ("combat_mod", "cmd"): lambda a: a.cmd(),
    ("combat_mod", "initiative"):
        lambda a: sum(m.value for m in a.initiative_modifiers()),
    ("save_mod", "fort"): lambda a: sum(m.value for m in a.save_modifiers("fort")),
    ("save_mod", "ref"): lambda a: sum(m.value for m in a.save_modifiers("ref")),
    ("save_mod", "will"): lambda a: sum(m.value for m in a.save_modifiers("will")),
    ("combat_mod", "touch_ac"): lambda a: a.touch_ac(),
    ("skill_mod", "stealth"):
        lambda a: sum(m.value for m in a.skill_modifiers("stealth")),
    ("speed", "land"): lambda a: a.speed_feet,
}

# Authorable and inert. Each names the stage that closes it. The list may only get
# shorter: a target that starts working fails the second test below until its line is
# deleted, which is how a ratchet tightens itself rather than asking to be tightened.
_UNREACHED = {
    # touch_ac left this list in stage 2: it reads the typed channels now and drops
    # the three a touch attack ignores, rather than subtracting armour-table numbers
    # from a finished total.
    "caster_level": "stage 9 — no reader consults it; casting has no check to spend "
                    "it on yet",
    "spell_resistance": "stage 9 — no reader consults it; nothing in the app rolls "
                        "to overcome SR (docs/spells.md 5.1)",
}


def _probe():
    from rules.sheet import from_dict

    return from_dict({"name": "probe", "kind": "npc", "hp": 20, "hp_max": 20,
                      "ranks": {"stealth": 1},
                      "abilities": {k: 12 for k in
                                    ("str", "dex", "con", "int", "wis", "cha")}})


def test_every_authorable_target_reaches_the_number_it_names():
    """The +damage gap hid for months: a `combat_mod` aimed at damage was authored,
    validated, saved and rendered on a card — and absent from every damage roll.
    Writing the first version of this test found the identical gap on cmb and cmd.

    That first version asserted each builder's source text CONTAINED `_buff_mods`,
    which is a false positive by construction: `initiative_modifiers` contains the
    call and passes, while deafened's -4 still never arrives because
    `_condition_mods("initiative")` is never read. The presence of a call is not the
    delivery of a number, so this authors a real bonus and reads the real total."""
    for (kind, target), read in sorted(_REACHES.items()):
        # Speed is measured in whole five-foot squares, so a +3 probe would round
        # away and read as "moves nothing" on a channel that works perfectly.
        step = 10 if kind == "speed" else 3
        a = _probe()
        before = read(a)
        a.add_buff(kind, target, step, source="probe")
        assert read(a) == before + step, (
            f"an authored {kind} aimed at {target!r} moves nothing — it can be "
            f"written in the editor, saved and shown, and no roll will ever feel it")


def test_the_inert_targets_are_only_the_ones_we_know_about():
    """The other half of the ratchet. A target the editor offers that moves no number
    is a promise the vocabulary makes and the engine breaks; carrying the list is
    honest, discovering it in play is not. Measured: three of the nine combat targets
    are inert, and every one of them is stage 2's to close."""
    from rules.effectspec import VOCAB

    declared = {o["id"] for o in VOCAB["combat_target"]}
    covered = {t for (k, t) in _REACHES if k == "combat_mod"} | set(_UNREACHED)
    forgotten = declared - covered
    assert not forgotten, (
        f"combat targets the editor offers and no test asks about: {sorted(forgotten)}")
    for target in sorted(_UNREACHED):
        a = _probe()
        a.add_buff("combat_mod", target, 3, source="probe")
        assert not hasattr(a, target), (
            f"{target} has a reader now — delete its line from _UNREACHED")


def test_an_authored_cmb_or_cmd_bonus_actually_moves_the_roll():
    """The behavioural half of the funnel law, for the gap this file's own writing
    found: +2 CMB was in the authoring vocabulary and never moved a manoeuvre."""
    from rules.sheet import from_dict

    a = from_dict({"name": "x", "kind": "npc", "hp": 5, "hp_max": 5,
                   "abilities": {k: 10 for k in
                                 ("str", "dex", "con", "int", "wis", "cha")}})
    cmb0 = sum(m.value for m in a.cmb_modifiers())
    cmd0 = sum(m.value for m in a.cmd_modifiers())
    a.add_buff("combat_mod", "cmb", 2, source="oil of manoeuvring")
    a.add_buff("combat_mod", "cmd", 2, source="stance of roots")
    assert sum(m.value for m in a.cmb_modifiers()) == cmb0 + 2
    assert sum(m.value for m in a.cmd_modifiers()) == cmd0 + 2
    assert any(m.source == "oil of manoeuvring" for m in a.cmb_modifiers())


# --- law 3: severed tells -------------------------------------------------------------


def test_an_outcome_with_literal_effects_carries_a_tell():
    """Every effect application emits a tell; the narrator is fed tells and nothing
    else about mechanics. A canary, not a proof: any `Outcome(...)` built in
    engine.py with a non-empty literal effects list must also pass a tell, so a new
    op cannot ship mechanics the narrator is never told about. (Refusal outcomes
    pass `effects=[]` and are exempt — their tell IS the refusal.)"""
    source = Path("rules/engine.py").read_text(encoding="utf-8")
    offenders = []
    for m in re.finditer(r"Outcome\(", source):
        depth, i = 1, m.end()
        while depth and i < len(source):
            depth += {"(": 1, ")": -1}.get(source[i], 0)
            i += 1
        call = source[m.start():i]
        if re.search(r"effects=\[\s*\{", call) and "tell=" not in call:
            line = source[:m.start()].count("\n") + 1
            offenders.append(f"rules/engine.py:{line}")
    assert not offenders, (
        "an Outcome carries effects the narrator will never hear about — add a "
        "tell:\n" + "\n".join(offenders))


def test_the_narrator_is_fed_tells_and_never_effects():
    """The severing itself: the two functions that build the narrator's view of the
    turn read `.tell` (and `.because`) off outcomes and must never reach for
    `.effects` — prose that knows a mechanic no tell backs is an outcome-claim."""
    source = Path("gm/agent.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    for name in ("narrate_outcome",):
        fn = next((n for n in ast.walk(tree)
                   if isinstance(n, ast.FunctionDef) and n.name == name), None)
        assert fn is not None, f"gm/agent.py lost {name}; update this test"
        body = ast.get_source_segment(source, fn)
        assert ".effects" not in body, (
            f"{name} reads outcome.effects — the narrator may only be fed tells")


# --- the skill cannot rot -------------------------------------------------------------


def test_every_symbol_the_skill_names_still_resolves():
    """The skill file is the one prose copy of this contract outside the design doc,
    and a prose copy is exactly what CLAUDE.md warns drifts. Its checked-refs block
    lists every path:symbol it leans on; each must import and resolve, so renaming
    a function or moving a file breaks this test instead of quietly orphaning the
    guidance."""
    import importlib

    skill = Path(".claude/skills/states-effects-tells/SKILL.md")
    assert skill.is_file(), "the skill this suite guards is missing"
    text = skill.read_text(encoding="utf-8")
    m = re.search(r"<!-- checked-refs\n(.*?)\n-->", text, re.S)
    assert m, "SKILL.md lost its checked-refs block"
    problems = []
    for line in m.group(1).splitlines():
        line = line.strip()
        if not line:
            continue
        path, _, symbol = line.partition(":")
        if not Path(path).exists():
            problems.append(f"{path} does not exist")
            continue
        if not symbol:
            continue
        module = path.replace("/", ".").removesuffix(".py")
        try:
            obj = importlib.import_module(module)
            for part in symbol.split("."):
                obj = getattr(obj, part)
        except (ImportError, AttributeError) as exc:
            problems.append(f"{path}:{symbol} — {exc}")
    assert not problems, "the skill names things that no longer exist:\n" + \
        "\n".join(problems)


# --- the gate itself ------------------------------------------------------------------


def test_every_content_cache_is_isolated_between_tests():
    """The suite is the gate every stage of the compliance work is judged by, and a
    gate that lies teaches you to re-run instead of investigate.

    Sixteen tests assign `settings.CAMPAIGN_DIR` outright rather than through
    `override_settings` and never restore it, and thirteen modules cache shipped
    content merged with a homebrew overlay read from under that directory. A cache
    filled while one test pointed the setting at its own tmp_path was still holding
    that test's homebrew for every test after it.

    `tests/conftest.py` restores the setting and drops the caches whenever it moves.
    This keeps its list honest: a cache is declared `_NAME: type | None = None`, so
    every module holding one of those must be listed, or it silently leaks again.
    """
    import re

    from tests.conftest import _CACHED

    declares = re.compile(r"^(_[A-Z][A-Z_]*)\s*:\s*[^=\n]*\|\s*None\s*=\s*None\s*$",
                          re.M)
    holders = {
        f"rules.{path.stem}"
        for path in Path("rules").glob("*.py")
        if declares.search(path.read_text(encoding="utf-8"))
    }
    missing = holders - set(_CACHED)
    assert not missing, (
        f"module(s) cache content under CAMPAIGN_DIR and are not isolated between "
        f"tests — add them to conftest._CACHED: {sorted(missing)}")
    stale = set(_CACHED) - holders
    assert not stale, f"conftest._CACHED names modules that hold no cache: {sorted(stale)}"


# --- law 2, continued: the applicator is the only door --------------------------------

# Modules allowed to touch Actor.effects directly, and why. `rules/sheet.py` IS the
# applicator's home — apply_effect, remove_effects, tick_effects and the compatibility
# shims are all implemented there, and an implementation may touch what it implements.
# Everything else edits the store behind the engine's back.
_STORE_EDITORS = {
    "rules/sheet.py": "the applicator's own implementation",
    # _drain_periodic left this list in stage 4b — it goes through remove_effects now
    # and says which pool ran dry. One edit remains, and it is the dispel.
    "rules/engine.py": "stage 5: the dispel path removes a record directly instead of "
                       "going through remove_effects",
}


def test_nothing_outside_the_applicator_edits_the_store():
    """Law 2's central claim — every change travels as an effect through one door — had
    no test at all, and the audit measured it as already false: 18 direct mutations of
    `.effects` against 6 calls to the applicator.

    Most of the 18 are the applicator implementing itself. The two that are not live in
    the engine, and both bypass the tell that removal is supposed to emit: a stance that
    ends when its pool runs dry, and a dispel."""
    mutates = re.compile(r"\.effects\s*(?:=[^=]|\.append|\.remove|\.clear|\.extend|\.pop)")
    found: dict[str, list[int]] = {}
    for path in sorted(Path(".").glob("*/*.py")):
        if path.parts[0] not in ("rules", "play", "gm", "world"):
            continue
        for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if mutates.search(line):
                found.setdefault(path.as_posix(), []).append(n)
    unlisted = {k: found[k] for k in sorted(set(found) - set(_STORE_EDITORS))}
    assert not unlisted, (
        f"the effect store is edited outside the applicator: {unlisted}. Use "
        f"apply_effect / remove_effects / tick_effects, so the removal emits its tell.")


# --- law 2, continued: not every channel is a sum -------------------------------------


def test_the_best_only_channels_never_add_up():
    """1e is specific, and the "one funnel" wording invites getting it wrong: two
    concealments are not one bigger concealment. Blur's 20% beside displacement's 50%
    is 50%, not 70% and not 60%; two energy resistances against the same type are the
    better one; several damage reductions are the best applicable one, never the total.

    Written because the funnel law, stated as "every number goes through _buff_mods and
    ends in stack()", reads as licence to sum everything — and `dice.stack` treats
    untyped as self-stacking, so summing is exactly what an executor would get."""
    from rules.sheet import Reduction

    a = _probe()
    a.add_buff("concealment", "miss_chance", 20, source="blur")
    a.add_buff("concealment", "miss_chance", 50, source="displacement")
    assert a.concealment()[0] == 50, "concealment is the best source, never a total"

    a.resistances = {"fire": 10, "Fire": 5}
    assert a.resistance("fire") == 10, "two resistances to one energy take the better"

    a.reductions = [Reduction(3, "", "hide"), Reduction(5, "", "stoneskin")]
    assert a.damage_reduction("slashing").amount == 5, "DR is the best, never the sum"


# --- law 1, continued: the engine names no class --------------------------------------

# Class and feat names still hard-coded in the shared engine, with the stage that turns
# each into a document field. Counted rather than forbidden outright because the number
# is the work remaining, and it may only go down.
_NAMED_IN_ENGINE = {
    "rules/engine.py": 3,     # 'control blood' x1, 'swift strikes' x2 — stage 9
    "rules/sheet.py": 12,     # power attack x6, weapon focus/specialisation x4,
                              # weapon finesse x1, 'blood bending' x1 — stages 8 and 9
}


def test_the_shared_engine_names_fewer_classes_and_feats_than_it_did():
    """A class ability that needs an engine special case actually needs a field in the
    document grammar. Stage 3 proved it for the armament and Blood Rage, and pinned the
    claim with a sweep that read two files for four phrases — which is how ten sites in
    the same two files went unnoticed.

    A ratchet, because the remaining ones are stages 8 and 9's work and the count is
    exactly what is left to do. It may only ever fall."""
    names = ("blood bending", "control blood", "swift strikes", "power attack",
             "weapon finesse", "weapon focus", "weapon specialization",
             "blood armament", "armed punch", "blood rage")
    for path, ceiling in _NAMED_IN_ENGINE.items():
        source = Path(path).read_text(encoding="utf-8")
        source = re.sub(r'"""(?:.|\n)*?"""', "", source)
        code = "\n".join(re.sub(r"#.*$", "", line) for line in source.splitlines())
        hits = sum(code.lower().count(n) for n in names)
        assert hits <= ceiling, (
            f"{path} names {hits} class/feat strings against a ceiling of {ceiling}. "
            f"A named ability belongs in the document grammar, not in the engine.")
        assert hits >= ceiling - 1 or ceiling == 0, (
            f"{path} is down to {hits} — lower the ceiling in _NAMED_IN_ENGINE to "
            f"{hits} so the ratchet keeps its grip")


# --- persistence: what the save forgets -----------------------------------------------

# Scene fields the save does not write, and why. Three are transient scratch rebuilt
# every turn; three are real state that a restart destroys.
_UNSAVED_SCENE_FIELDS = {
    "log": "transient — rebuilt each turn",
    "bleeding": "transient — read and cleared within the turn that fills it",
    "hazards": "transient — read and cleared within the turn that fills it",
    "wards": "stage 4c/5: a restart deletes every thorn body and bleed ward",
    "manifests": "stage 4c/5: a restart deletes the fog and leaves its squares",
    "spawn_feet": "stage 5: lost across exactly the turn boundary it is needed on",
}


def test_every_scene_field_is_saved_or_named_as_lost():
    """Six of the Scene's thirty-one fields are never written to the save, and nobody
    noticed because no test walks the dataclass. Two of them — wards and manifests —
    have `from_dict` constructors with zero call sites anywhere in the repo, so a
    save/reload mid-fight silently deletes every standing hazard while the grid keeps
    the squares they claimed.

    A new field that nobody saves is the same bug arriving again, so this fails until
    it is either written or written down."""
    import dataclasses

    from rules.engine import Scene

    payload = Path("play/campaign.py").read_text(encoding="utf-8")
    named = set(re.findall(r'"(\w+)":', payload))
    fields = [f.name for f in dataclasses.fields(Scene) if not f.name.startswith("_")]
    unsaved = [f for f in fields if f not in named]
    surprises = set(unsaved) - set(_UNSAVED_SCENE_FIELDS)
    assert not surprises, (
        f"Scene field(s) the save never writes and nobody has accounted for: "
        f"{sorted(surprises)}. Save them, or add them to _UNSAVED_SCENE_FIELDS "
        f"with the reason.")
    fixed = set(_UNSAVED_SCENE_FIELDS) - set(unsaved)
    assert not fixed, (
        f"these are saved now — delete them from _UNSAVED_SCENE_FIELDS: {sorted(fixed)}")


# The only two places the world clock may be written: the one door, and the loader that
# restores a saved value. Six sites moved it before stage 4a and four of them expired
# nothing at all.
_CLOCK_WRITERS = {
    "rules/engine.py": "Scene.advance — the one door",
    "play/campaign.py": "the load constructor, restoring a saved value",
}


def test_only_one_function_moves_the_world_clock():
    """Stage 4a's headline property, which nothing measured.

    Six places wrote `scene.clock_minutes` and two of them expired anything: a
    forty-eight-hour forage, a twelve-hour crafting session, an hour spent waking up
    and a resurrection costing up to twenty-seven days all left every timed effect
    where it was. `Scene.advance` is the single door now — and a seventh site could be
    added tomorrow with the whole suite still green, which is exactly the shape of
    rule this project has measured as failing when it lives only in prose."""
    pattern = re.compile(r"\bclock_minutes\s*[+\-]?=")
    found: dict[str, list[int]] = {}
    for path in sorted(Path(".").glob("*/*.py")):
        if path.parts[0] not in ("rules", "play", "gm", "world"):
            continue
        source = re.sub(r'"""(?:.|\n)*?"""', "", path.read_text(encoding="utf-8"))
        for n, line in enumerate(source.splitlines(), 1):
            if pattern.search(re.sub(r"#.*$", "", line)):
                found.setdefault(path.as_posix(), []).append(n)
    unlisted = {k: found[k] for k in sorted(set(found) - set(_CLOCK_WRITERS))}
    assert not unlisted, (
        f"the world clock is moved outside Scene.advance: {unlisted}. Call "
        f"scene.advance(minutes) so the effects, the pools and the body move with it.")
