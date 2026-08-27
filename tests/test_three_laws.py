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


def test_the_actor_has_exactly_one_ticker():
    """Before stage 2, tick_conditions held one expiry loop per mechanism — three
    copies of the same six lines — and a mechanism added without a fourth loop was a
    mechanism that never wore off. The scene's standing things (wards, manifests)
    and compulsions keep their own clocks by design; the ACTOR has one. Exactly one
    place in the actor's own modules may decrement rounds_left."""
    sites = []
    for path in ("rules/sheet.py", "rules/activeeffect.py"):
        for n, line in enumerate(Path(path).read_text(encoding="utf-8").splitlines(), 1):
            if "rounds_left -=" in line:
                sites.append(f"{path}:{n}")
    assert len(sites) == 1, (
        f"the actor's clock must tick in one place (tick_effects); found: {sites}")


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
    pattern = re.compile(r"\.(conditions|buffs|temp_pools)\s*=[^=]")
    offenders = []
    for path in Path(".").glob("*/*.py"):
        if path.parts[0] not in ("rules", "gm", "play", "tools", "world"):
            continue
        # survival.Toll carries its own `conditions` — a list of condition NAMES a
        # hardship inflicts, not the Actor view — and is allowed to assign it.
        if path.name == "survival.py":
            continue
        for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if pattern.search(line) and "self.effects" not in line:
                offenders.append(f"{path}:{n}: {line.strip()}")
    assert not offenders, (
        "assignment to a read-only effect view (use apply_effect / remove_effects "
        "/ the shims):\n" + "\n".join(offenders))


def test_every_modifier_list_reads_the_one_funnel():
    """The +damage gap hid for months: `combat_mod` aimed at damage was authored,
    validated, saved, shown — and absent from every damage roll, because
    damage_modifiers never read _buff_mods. Writing this very test found the same
    gap on cmb and cmd. Every builder of an itemised modifier list must read the
    funnel, so an effect's bonus reaches every number it names."""
    source = Path("rules/sheet.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    actor = next(n for n in ast.walk(tree)
                 if isinstance(n, ast.ClassDef) and n.name == "Actor")
    builders = [m for m in actor.body if isinstance(m, ast.FunctionDef)
                and m.name.endswith("_modifiers")]
    assert len(builders) >= 8, "the modifier builders moved; update this test"
    missing = [m.name for m in builders
               if "_buff_mods" not in ast.get_source_segment(source, m)]
    assert not missing, (
        f"modifier builders that never read the funnel — an authored bonus aimed "
        f"at them applies nowhere: {missing}")


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
