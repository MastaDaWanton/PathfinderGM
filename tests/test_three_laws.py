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


def test_the_vocabulary_is_the_only_authority_on_acting():
    """The condition rows carried a `can_act` boolean and the tag tree carried
    `state.unable`, both hand-written, and nothing compared them. Measured across the 31
    shipped conditions they disagreed on three — `fascinated` (tagged unable, flagged
    able), `helpless` (flagged unable, untagged) and `nauseated` (flagged unable, and
    wrongly: 1e allows it "a single move action per turn" and the flag refused the move).

    Consumers then read whichever of the two they had heard of, which is how a maneuver
    came to succeed without a roll against a target that was merely distracted.

    A flag is also the wrong shape for the question: it answers "can this creature act?"
    with one bit, and 1e's incapacities are not all total. What a state stops is stated
    in `states.BLOCKS`, per op.
    """
    from rules.tables import CONDITIONS

    flagged = sorted(k for k, v in CONDITIONS.items() if "can_act" in v)
    assert not flagged, (
        f"condition rows carrying a second answer to 'can this creature act': "
        f"{flagged}. What a state stops belongs in rules/states.py BLOCKS, where one "
        f"function answers for the turn gate, the intent guard and the sheet alike.")


def test_being_unable_to_act_is_not_the_same_as_being_out_of_the_fight():
    """Three questions, and the app answered them with two predicates. `Scene.conscious`
    opened with `not a.can_act()` while all five of its callers wanted "still in the
    fight" — so a stunned enemy, who takes no turn and is very much still fighting,
    counted as a side no longer standing: the encounter ended and the XP settled with
    them upright in front of the player.

    The third question — 1e's "immobilized, unconscious, or otherwise incapacitated",
    which makes a combat maneuver succeed with no roll — had no owner at all. The
    condition rows carried `helpless: True` on five rows and NOTHING read it, so
    `_resolve_maneuver` borrowed can-act and auto-grappled the dazed and the cowering.
    """
    from rules.sheet import from_dict
    from rules.tables import CONDITIONS

    def actor():
        return from_dict({"name": "Probe", "kind": "npc", "hp": 20, "hp_max": 20,
                          "abilities": {k: 12 for k in ("str", "dex", "con",
                                                        "int", "wis", "cha")}},
                         ref="c1")

    for key in sorted(CONDITIONS):
        a = actor()
        a.add_condition(key, source="probe")
        if a.is_helpless:
            assert not a.can_act(), f"{key} is helpless but may act"
        if a.is_down:
            assert not a.can_act(), f"{key} is out of the fight but may act"

    # The three that separate the questions, named rather than derived.
    stunned, fascinated = actor(), actor()
    stunned.add_condition("stunned", source="probe")
    fascinated.add_condition("fascinated", source="probe")
    for a, key in ((stunned, "stunned"), (fascinated, "fascinated")):
        assert not a.can_act(), f"{key} should take no turn"
        assert not a.is_down, f"{key} is not out of the fight"
        assert not a.is_helpless, f"{key} must not be auto-grappled without a roll"

    nauseated = actor()
    nauseated.add_condition("nauseated", source="probe")
    assert nauseated.can_act(), "1e gives the nauseated a single move action"
    assert nauseated.blocking_key("attack") == "nauseated"
    assert nauseated.blocking_key("move") == ""


def test_a_state_that_only_a_document_declares_still_stops_actions():
    """`states.stops` promises a document may declare `state.unable.*` and be obeyed
    without a row in the condition table. It was half true: `has_state` saw such an
    effect and `can_act` did not, because the predicate returned the effect's KEY and a
    document-declared state need not have one — so an empty string read as "nothing
    stops you". Found by review, under a green suite, because nothing the app builds
    today lacks a key.
    """
    from rules.activeeffect import ActiveEffect
    from rules.sheet import from_dict

    a = from_dict({"name": "Probe", "kind": "npc", "hp": 20, "hp_max": 20,
                   "abilities": {k: 12 for k in ("str", "dex", "con",
                                                 "int", "wis", "cha")}}, ref="c1")
    a.effects.append(ActiveEffect(name="hexed", kind="condition", key="",
                                  tags=("state.unable.hexed",)))
    assert a.has_state("state.unable")
    assert not a.can_act(), "the vocabulary said no and can_act said yes"
    assert a.blocking_condition() == "hexed", "and the refusal has to name something"


def test_a_vocabulary_addition_reaches_campaigns_already_on_disk():
    """Tags are written into the save, so the vocabulary and a saved condition are two
    copies of one fact — the shape law 1 exists to prevent, hiding in the persistence
    layer. Every test builds its actors fresh, so nothing would ever notice: a `helpless`
    prisoner saved before the vocabulary called them `state.unable` would keep the old
    answer for the life of the campaign.

    Adding is the half that is safe to do. Rebuilding the owned namespaces outright —
    which is the only way to RETIRE an answer — was tried and reverted: an ability
    document appends its own tags in any namespace, so the rebuild deleted them.
    Measured, a grant of `state.unable.trance` blocked actions in session and stopped
    blocking after a restart, and a homebrew condition declaring `recovery.rest` was
    cleared by a night's sleep until the campaign was reloaded. Carrying a stale tag is
    the lesser failure; the greater one is a document whose declaration evaporates on
    the next load, which is precisely what stage 3 and stage 5c promised documents.

    The cost, stated rather than hidden: nothing can withdraw a tag from a condition
    already on disk. Doing that safely needs a document's own tags recorded separately
    from the vocabulary's, which is a save-shape change and not this stage's.
    """
    from rules.activeeffect import from_dict as effect_from_dict
    from rules.states import tags_for

    got = effect_from_dict({
        "kind": "condition", "key": "fascinated", "name": "Fascinated",
        "tags": ["state.unable.fascinated",       # what the save happened to carry
                 "document.own.flourish"]})       # an ability document's own

    assert set(got.tags) >= set(tags_for("fascinated")), (
        "a vocabulary entry added since the save was written did not reach it")
    assert "document.own.flourish" in got.tags, (
        "a document's own tag was destroyed on load")

    # And the same for a tag a document declares INSIDE a namespace the vocabulary
    # uses — the case that made the rebuild untenable.
    doc = effect_from_dict({
        "kind": "condition", "key": "blood rage", "name": "Blood Rage",
        "tags": ["buff.stance.blood-rage", "state.unable.trance",
                 "recovery.rest"]})
    assert "state.unable.trance" in doc.tags and "recovery.rest" in doc.tags, (
        "a document's declared state survived in session and vanished on reload")


# The condition names the four ending-sites each carried before `recovery.*` existed,
# quoted verbatim so the tags can be checked against what they replaced rather than
# against themselves. Copies drift: travel forgot `stable`, and only resurrection was
# ever entitled to remove `dead`.
_WAS_HAND_WRITTEN = {
    "recovery.hit-points": ("dying", "stable", "unconscious", "disabled"),
    "recovery.rest": ("prone", "flat-footed", "shaken", "frightened", "panicked",
                      "dazzled", "entangled", "grappled", "pinned", "staggered",
                      "sickened", "nauseated", "dazed", "cowering", "fascinated"),
}


def test_the_recovery_families_hold_exactly_the_lists_they_replaced():
    """Four sites named the same four conditions between them — `_op_heal`,
    `Actor.rest`, `downed.resolve` and `views.resurrect` — and `Actor.rest` named
    fifteen more. Nineteen literals in one function, and nothing tied any copy to any
    other.

    The families are checked against the lists rather than against themselves, because a
    tag that silently gains or loses a member is the same defect in a new place. And a
    family that grows is how the dangerous version of this arrives: `state.unable`
    contains `dead`, so a `rest()` that swept a `state.*` family would raise a corpse.
    """
    from rules.states import TAGS

    for family, was in _WAS_HAND_WRITTEN.items():
        now = {k for k, tags in TAGS.items() if family in tags}
        assert now == set(was), (
            f"{family} no longer holds the list it replaced. "
            f"gained {sorted(now - set(was))}, lost {sorted(set(was) - now)}")

    assert "dead" not in {k for k, t in TAGS.items() if "recovery.hit-points" in t}, (
        "cure light wounds would raise the dead: resurrection is the only caller "
        "entitled to remove `dead`, which is why it names the key itself")


# Literal condition keys still named in app code, with why each file is entitled to
# them. A ceiling per file rather than a total, because a total cannot tell a site being
# REMOVED from one being MOVED — the same reason `_CLOCK_SITES` is a list of exemptions
# somebody had to write rather than a number.
#
# What is left is almost entirely category (a): the engine's own mechanical writers. 1e
# says a character below 0 hit points is unconscious and dying, and the code that writes
# that has to name those conditions — widening any of these guards to a family is how a
# creature becomes unkillable, because a dying actor would never cross into dead.
_LITERAL_KEY_SITES = {
    "rules/sheet.py": (34, "apply_hp_state, apply_nonlethal_state, bleed_out, the "
                           "ability-zero states and rest's exhausted-to-fatigued "
                           "downgrade — the writers of the 1e ladders themselves"),
    "rules/engine.py": (11, "the dying/stable resolution, flat-footed and stunned as "
                            "combat rules, grappled as a maneuver result, and dead as "
                            "'this square holds a corpse'"),
    "play/downed.py": (6, "the four rungs of the hit-point ladder, read where "
                          "apply_hp_state wrote them; the fifth rung asks the "
                          "vocabulary"),
    "rules/survival.py": (4, "the fatigue ladder: thirst escalates fatigued to "
                             "exhausted, and asks for the key it is about to write"),
    "play/views.py": (3, "resurrection naming `dead` (the only caller entitled to "
                         "remove it), the life-debt it charges for, and the stance "
                         "toggle whose key comes from a class document"),
}


def test_no_new_site_matches_a_condition_by_name():
    """Law 1 in the form that can be checked: systems ask the vocabulary, they do not
    match strings. Measured before this stage, by AST census over the app: 107 literal
    condition-key mentions against 12 tag queries — and ten of those twelve asked the
    same single query, so nine of the eleven tag families rules/states.py ships had no
    readers at all.

    The drift that bought: `play/downed.py` reported seven conditions that cannot act as
    fit for a turn, `gm/watcher.py` missed five of the six `state.down` members, and
    four sites carried the same four condition names between them and had already
    disagreed about which four.

    A ceiling per file, and it may only fall. The remainder is the engine writing the
    conditions 1e names — those must stay literal, because widening a death guard to a
    family means a dying actor never crosses into dead.
    """
    calls = {"has_condition", "add_condition", "remove_condition"}
    found: dict[str, int] = {}
    for folder in ("rules", "play", "gm", "world", "tools"):
        for path in sorted(Path(folder).rglob("*.py")):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            hits = sum(
                1 for node in ast.walk(tree)
                if isinstance(node, ast.Call) and node.args
                and (node.func.attr if isinstance(node.func, ast.Attribute)
                     else getattr(node.func, "id", "")) in calls
                and isinstance(node.args[0], ast.Constant)
                and isinstance(node.args[0].value, str))
            if hits:
                found[path.as_posix()] = hits

    unlisted = {k: v for k, v in found.items() if k not in _LITERAL_KEY_SITES}
    assert not unlisted, (
        f"a new system is matching conditions by name: {unlisted}. Ask the vocabulary "
        f"— has_state('state.down'), clear_states('recovery.rest') — so the next state "
        f"anyone adds participates without editing this file.")

    for path, (ceiling, why) in _LITERAL_KEY_SITES.items():
        hits = found.get(path, 0)
        assert hits <= ceiling, (
            f"{path} names {hits} literal condition keys against a ceiling of "
            f"{ceiling} ({why}).")
        assert hits >= ceiling - 1, (
            f"{path} is down to {hits} — lower the ceiling in _LITERAL_KEY_SITES to "
            f"{hits} so the ratchet keeps its grip.")


# --- law 2: one applicator, one ticker ------------------------------------------------


# Every place in the app that counts a clock down, and the stage that folds it into
# the one ticker. An allowlist rather than a count, because a count cannot tell a site
# being REMOVED from one being MOVED: stage 4c could fold the compulsion clock in and
# introduce another elsewhere, and a count would not notice. Each line is an exemption
# somebody had to write, and deleting one is that stage's own proof.
_CLOCK_SITES = {
    "rules/sheet.py": "tick_effects — the one actor ticker, and the destination",
    # The scene's own ticker, and its destination — the same standing rules/sheet.py
    # has for the actor's. Wards and manifestations had an expiry loop each, three
    # lines apart, disagreeing about teardown and about whether an ending was worth
    # mentioning; `Scene.tick_effects` is now the one, with `_end_standing` as the one
    # door out.
    "rules/engine.py": "Scene.tick_effects — the one scene ticker, and the destination",
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
    gone = set(_CLOCK_SITES) - set(found) - {"rules/sheet.py", "rules/engine.py"}
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


def test_crossing_a_hit_point_threshold_is_said_out_loud():
    """The tell for a killing blow was `'the thug takes 30 slashing damage.'`

    Measured at all three of 1e's thresholds: the condition was written into
    `outcome.effects` and never into `outcome.tell`. The narrator is fed tells and
    nothing else about mechanics, so it was never told anybody died — it wrote
    wounded-man prose about a corpse, and `press_the_death` pressed the death on
    afterwards. A repair that fires because the engine withheld the fact is the
    severing failing in the direction nobody looks: the tell was not wrong, it was
    silent.

    Driven through the engine rather than grepped, because the tell is composed from
    several pieces at five different sites and only the finished sentence matters.
    """
    from rules.dice import Dice
    from rules.engine import Engine, Scene
    from rules.sheet import from_dict

    def fight(hp):
        s = Scene(location_id="5bbd0c40345f")
        for ref, kind, name, h in (("pc", "pc", "Kesst", 20),
                                   ("c1", "npc", "the thug", hp)):
            s.add(from_dict(
                {"name": name, "kind": kind, "hp": h, "hp_max": 20, "level": 1,
                 "class": "rogue" if kind == "pc" else None,
                 "abilities": {k: 12 for k in ("str", "dex", "con",
                                               "int", "wis", "cha")}}, ref=ref))
        return s, Engine(s, Dice(seed=5))

    for amount, expect in ((6, "is disabled"), (9, "is unconscious and dying"),
                           (30, "is dead")):
        scene, engine = fight(6)
        got = engine.run(engine.validate(
            [{"op": "damage", "actor": "pc", "target": "c1", "because": "she hits",
              "params": {"amount": amount, "type": "slashing"}}], origin="author:test"))
        tell = got.outcomes[0].tell
        written = sorted(c.key for c in scene.get("c1").conditions)
        assert written, f"{amount} damage crossed no threshold; this proves nothing"
        assert expect in tell, (
            f"{amount} damage wrote {written} and the narrator was told only: {tell!r}")


def test_the_scrubber_knows_what_the_dice_already_decided():
    """Law 3's third clause, verbatim: prose stating a mechanic **no tell backs** is an
    outcome-claim. The detector had never been shown the engine's answer — it could ask
    "does this sentence assert a mechanic" and never "was that mechanic true" — so the
    two doors the player actually reads ran with it switched off entirely.

    That was a defensible local decision and the comment said so: written after the dice,
    "your blade finds the gap" is reporting rather than invention. Measured on the twelve
    real campaigns, scrubbing those beats blind cuts 25 of 43 below forty characters, and
    deletes 14 of the 18 engine-authored lines. The fix is to tell the detector what
    happened, not to turn it off.

    Backed from the outcome RECORD — op, verdict, effects — and never from the text of
    the tells. Searching a tell's prose for the word "hit" to answer a mechanical
    question is the string-matching stage 5 spent itself removing.
    """
    from rules.bestiary import instantiate
    from rules.dice import Dice
    from rules.engine import Engine, Scene
    from rules.intents import claims_the_engine_backs, find_outcome_claims
    from rules.sheet import load_pc

    def swing(seed):
        scene = Scene(location_id="5bbd0c40345f")
        scene.add(load_pc("fixtures/pc-kesst.json"))
        scene.add(instantiate("guildhand", scene=scene, name="the guildhand"))
        engine = Engine(scene, Dice(seed=seed))
        intent = [{"op": "attack", "actor": "pc", "target": "c1",
                   "visibility": "hidden", "because": "she swings", "params": {}}]
        engine.run(engine.validate(intent, origin="author:test"))        # the battle gate opens the fight
        return engine.run(engine.validate(intent, origin="author:test"))

    found = {}
    for seed in range(1, 60):
        got = swing(seed)
        if got.outcomes and got.outcomes[0].verdict in ("hit", "miss"):
            found.setdefault(got.outcomes[0].verdict, got.outcomes)
        if len(found) == 2:
            break
    assert set(found) == {"hit", "miss"}, "needed one of each to prove both directions"

    invented = "You slip free of the crowd and the purse is in your pocket."
    for verdict, outcomes in found.items():
        backed = claims_the_engine_backs(outcomes)
        true_line = ("Your blade finds the gap under his arm." if verdict == "hit"
                     else "Your point goes wide of him.")

        assert find_outcome_claims(true_line), (
            "this sentence must look like a claim, or the test proves nothing")
        assert not find_outcome_claims(true_line, backed=backed), (
            f"the engine said {verdict} and the scrubber cut the prose reporting it")
        assert find_outcome_claims(invented, backed=backed), (
            "an invented theft survived because an attack happened to land")


def test_a_creature_at_exactly_zero_is_not_a_corpse_to_anybody():
    """Stage 5 claimed no two modules disagreed about "out of the fight" any more, and on
    this case they still did. Exactly 0 hit points is *disabled* in 1e — conscious, on
    its feet, taking initiative turns — and eleven sites spelled the question
    `hp <= 0` instead of asking the vocabulary.

    So a disabled creature was simultaneously: aged out of the scene as a body, left
    behind when the party walked out, named in the walking-dead prose cut so its every
    sentence was deleted, offered to the watcher for looting, stripped by the loot op,
    hidden from the merchant panel, and skinnable — while it was standing there able to
    act. The craft door said "The dead only" in its own docstring.

    One question, `Actor.is_down`, which is `hp < 0 or state.down`.
    """
    from rules.bestiary import instantiate
    from rules.dice import Dice
    from rules.engine import Engine, Scene
    from rules.sheet import load_pc
    from gm import watcher

    scene = Scene(location_id="5bbd0c40345f")
    scene.add(load_pc("fixtures/pc-kesst.json"))
    foe = instantiate("thug", scene=scene, name="the thug")
    scene.add(foe)
    engine = Engine(scene, Dice(seed=2))

    foe.hp = 0
    foe.apply_hp_state()
    assert foe.has_condition("disabled") and foe.can_act(), "not the disabled case"

    assert not foe.is_down, "disabled is not down; it is standing and acting"
    assert scene.conscious("c1"), "and it is still in the fight"
    assert not watcher._down(foe), "offered for looting while on its feet"

    for _ in range(4):
        engine.tidy_the_fallen()
    assert "c1" in scene.actors, "a conscious creature was tidied away as a body"

    engine.leave_behind()
    assert "c1" in scene.actors, "and left behind, though it could have walked"


def test_an_ability_that_deals_damage_can_kill():
    """Found by the stage-6 reconnaissance, and it is not a tell defect at all — it is
    the one underneath.

    `_op_use_ability` rolled the damage, took it off hit points and never ran the
    hit-point ladder. Measured: a level-12 blood bender's Blood Spike Projectile took a
    thug to −22 of 13 against Constitution 13 — nine hit points past its death line —
    and wrote NO condition. Not dead, not dying, not unconscious. The creature was not
    killed quietly; it was not killed at all, and would have taken its next turn.

    The same gap swallowed the ability's own cost: a non-lethal price past the threshold
    could not knock its user out either.
    """
    from rules.bestiary import instantiate
    from rules.dice import Dice
    from rules.engine import Engine, Scene
    from rules.sheet import from_dict

    pc = from_dict({"name": "Kesst", "kind": "pc", "hp": 60, "hp_max": 60,
                    "class": "blood bending", "level": 12,
                    "paths": {"blood spike": 12},
                    "abilities": {k: 14 for k in ("str", "dex", "con",
                                                  "int", "wis", "cha")}}, ref="pc")
    scene = Scene(location_id="5bbd0c40345f")
    scene.add(pc)
    thug = instantiate("thug", scene=scene, name="the thug")
    scene.add(thug)
    engine = Engine(scene, Dice(seed=3))

    got = engine.run(engine.validate(
        [{"op": "use_ability", "actor": "pc", "because": "she strikes",
          "params": {"ability": "blood spike projectile", "to": "c1"}}], origin="author:test"))

    assert thug.hp < 0, "the ability did no damage; this proves nothing"
    written = sorted(c.key for c in thug.conditions)
    assert written, (
        f"the thug is at {thug.hp} of {thug.hp_max} and carries no condition — an "
        f"ability that deals damage cannot take anybody out of the fight")
    assert any(k in written for k in ("dead", "dying", "unconscious"))
    assert "unconscious" in got.outcomes[0].tell, (
        "and the narrator was not told either")


# Who in the GM layer may read an outcome's mechanics instead of its tell, and why.
#
# The seam is not "nothing may read effects" — that would be false to the design, which
# hands `cut_dead_men_walking` the dead on purpose. The line is: **what builds the
# narrator's prompt sees tells; an engine-side repair, applied to the model's output
# afterwards, may know engine facts.** A repair is the engine correcting the model, not
# the model being taught a mechanic.
_READS_MECHANICS = {
    "gm/agent.py:_deaths_from":
        "feeds press_the_death, a repair that runs AFTER the prose — it needs how far "
        "past dead the blow went, and a tell is a sentence, not a number. Making the "
        "narrator parse that back out of English would be a second vocabulary built in "
        "the presentation layer.",
    "gm/judgement.py:note_heat":
        "sets scene.heat, which is world state and not prose — nothing the narrator "
        "reads passes through here.",
}


def test_only_the_named_repairs_read_mechanics_instead_of_tells():
    """The severing itself, and the version of this test that can actually see it.

    The old one inspected a single function and matched the literal text `.effects`.
    Measured: `.effects` appears ZERO times in the whole of `gm/` — both real sites
    spell it `getattr(o, "effects", None)` — so the test was vacuously true and always
    had been. It is why the debt survived five stages: the narrator was reaching past
    the tell in two places and law 3's ratchet could not see either.

    Now every function in `gm/` is checked, both spellings are caught, and the two that
    may is an allowlist with a reason each — the shape `_CLOCK_SITES` uses, because a
    count cannot tell a site being removed from one being moved.
    """
    found: dict[str, int] = {}
    for path in sorted(Path("gm").glob("*.py")):
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source)
        owner: dict[int, str] = {}
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                for inner in ast.walk(node):
                    if hasattr(inner, "lineno"):
                        owner.setdefault(inner.lineno, node.name)
        for node in ast.walk(tree):
            # `o.effects`, and `getattr(o, "effects")` which is how both real sites
            # are written and how they slipped past the old test.
            hit = (isinstance(node, ast.Attribute) and node.attr == "effects") or (
                isinstance(node, ast.Call)
                and getattr(node.func, "id", "") == "getattr"
                and len(node.args) >= 2
                and isinstance(node.args[1], ast.Constant)
                and node.args[1].value == "effects")
            if hit:
                where = f"{path.as_posix()}:{owner.get(node.lineno, '<module>')}"
                found[where] = found.get(where, 0) + 1

    unlisted = sorted(set(found) - set(_READS_MECHANICS))
    assert not unlisted, (
        f"the narrator reaches past the tell in {unlisted}. If prose needs a fact, the "
        f"fact becomes part of a tell; if an engine-side repair needs one, add it to "
        f"_READS_MECHANICS with the reason.")

    gone = sorted(set(_READS_MECHANICS) - set(found))
    assert not gone, (
        f"{gone} no longer reads effects — delete the exemption, that is the win")


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
    # _drain_periodic left this list in stage 4b and the dispel path in stage 5, which
    # was the last one: `rules/engine.py` no longer touches the store at all.
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
