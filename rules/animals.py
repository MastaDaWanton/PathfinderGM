"""Animals: what words cannot reach, and Handle Animal, which can.

The owner, 2026-11-22: "Companions can still obey in character but companions that are
animals/beasts are unable to communicate without the use of magic. So handle animal
functions almost as diplomacy in many ways." The 2026-10-01 ruling stands beside it — no
control panel; a companion acts as its own character — so for an animal the character is
its tricks and its attitude, and Handle Animal is how the player gets it to act.

**Who understands words** (`wordless`, `understands`). By the book's own record, not a
guess: a stat block prints the creature's languages, and every animal in the bestiary
prints none (dog, horse, wolf, camel: `[]`) while a griffon prints "Common (cannot
speak)" and a worg "Common, Goblin". So a beast (animal, magical beast, vermin) with no
language understands no sentence. An animal companion has no block and the animal tag,
so it is wordless too. Magic bridges it: `permission.speak_with_animals` (the spell's
permission, granted through the cast's one door) lets its holder be understood by
animals — only animals, as the spell says. The engine asks this of the TARGET's tags;
no reader parses English for it.

**Diplomacy cannot reach them.** CRB, Diplomacy: "You cannot use Diplomacy against a
creature that does not understand you or has an Intelligence of 3 or less"
(d20pfsrd.com/skills/diplomacy, read 2026-11-22). A druid's or ranger's wild empathy is
the book's door instead — "functions just like a Diplomacy check made to improve the
attitude of a person" — so it runs through the SAME machinery: `attitude.influence_dc`,
the once-a-day limit (`Engine._sway_refusal`, `Scene.swayed`), and `Engine._sway`, the
one applicator of an attitude step.

**Tricks are tags on the animal** (law 1): `trick.<name>`, laid by an ActiveEffect — a
trick taught (source `taught:<ref>`), a purpose trained (`trained.<purpose>` plus its
tricks), a companion's bonus tricks on its bond (rules/animal_companion.py). Remove the
effect and the trick evaporates (law 2). A handled command is `handled.<trick>` on the
animal, through the same applicator, and every one is told (law 3).

Prior art searched first (2026-11-22): the CRB's Handle Animal, Druid and Ride pages on
d20pfsrd. No Foundry PF1 module automating tricks could be found (only Koboldworks'
companion link, which shares roll data); Owlcat's Kingmaker and Wrath control companions
directly — the shape the 2026-10-01 ruling refused — and I could not confirm whether they
model Handle Animal at all. docs/research/2026-11-22-handle-animal.md has the rest.
"""
from __future__ import annotations

from . import states

TRICK = "trick"
PURPOSE = "trained"
HANDLED = "handled"
DOMESTIC = "animal.domestic"
REAR_TRIED = "animal.rear-tried"
CRAFT = "handler"                         # the In progress section's track id
SOURCE = "rule:skill.handle-animal"
# Bodies the book calls domestic ("The typical domestic animal has a starting attitude of
# indifferent"): the bestiary's working animals. A bought or reared animal holds the tag.
DOMESTIC_TEMPLATES = frozenset({"dog", "dog-riding", "riding-dog", "horse", "light-horse",
                                "heavy-horse", "warhorse", "pony", "donkey", "mule",
                                "camel", "cat"})
# CRB, Attack trick: "Normally, an animal will attack only humanoids, monstrous humanoids,
# giants, or other animals."
ATTACKS_TYPES = ("type.humanoid", "type.monstrous-humanoid", "type.giant", "type.animal")
# The uses a declared Handle Animal check may name (rules/bodyskills.py USES joins them).
USES = ("handle", "push", "teach", "train", "rear")


def _row(use: str) -> dict:
    from . import skilluses

    return skilluses.row(f"skill.handle-animal.{use}")


def tricks() -> dict[str, int]:
    """The CRB's tricks and their teaching DCs (content/rules/skill-uses.json)."""
    return dict(_row("teach").get("tricks") or {})


def purposes() -> dict[str, dict]:
    return dict(_row("train").get("purposes") or {})


def _slug(text: str) -> str:
    return "-".join(str(text or "").lower().split())


# --- who words reach ------------------------------------------------------------------------

def _int(actor):
    from .skilluses import _int_score

    return _int_score(actor)


def languages(actor) -> list[str]:
    doc = actor._creature_doc() if hasattr(actor, "_creature_doc") else None
    return [str(x) for x in ((doc or {}).get("languages") or []) if str(x).strip()]


def wordless(actor) -> bool:
    """A beast with no language: it understands no sentence (see the module's note)."""
    return bool(actor is not None and not getattr(actor, "is_pc", False)
                and states.is_beast(actor) and not languages(actor))


def speaks_with_animals(actor) -> bool:
    from .effectspec import permission_tag

    return bool(actor is not None and actor.has_state(permission_tag("speak_with_animals")))


def understands(listener, speaker) -> bool:
    """Whether `speaker`'s words reach `listener`: always, unless the listener is wordless
    and no magic bridges it (speak with animals reaches animals only)."""
    if not wordless(listener):
        return True
    return speaks_with_animals(speaker) and listener.has_state("type.animal")


def not_understood(listener) -> str:
    """The tell's sentence for words said to a wordless creature."""
    name = str(listener.name)
    return (f"{name[:1].upper()}{name[1:]} does not understand words: only a trick it "
            f"knows, given by Handle Animal, or magic that speaks with animals reaches it.")


def diplomacy_bar(target, speaker) -> str:
    """Why Diplomacy cannot be used on this creature, or "" (CRB, Diplomacy)."""
    if target is None or getattr(target, "is_pc", False):
        return ""
    if not understands(target, speaker):
        return f"{target.name} does not understand you"
    score = _int(target)
    if states.is_beast(target) and score is not None and score <= 3:
        return f"{target.name} has an animal's mind (Intelligence {score})"
    return ""


# --- what an animal knows -------------------------------------------------------------------

def handleable(actor) -> bool:
    """An animal, or another creature of Intelligence 1 or 2 (CRB, Handle Animal,
    Special: "the DC of any such check increases by 5")."""
    if actor is None or getattr(actor, "is_pc", False):
        return False
    return actor.has_state("type.animal") or _int(actor) in (1, 2)


def knows(animal, trick: str) -> bool:
    return animal.has_state(f"{TRICK}.{_slug(trick)}")


def known(animal) -> list[str]:
    return [t for t in tricks() if knows(animal, t)]


def purpose_of(animal) -> str:
    return next((p for p in purposes() if animal.has_state(f"{PURPOSE}.{_slug(p)}")), "")


def combat_trained(animal) -> bool:
    """Trained for combat riding: the purpose, or every one of its tricks known (a
    companion's bonus tricks can be all six — an owner call)."""
    want = purposes()["combat riding"]["tricks"]
    return animal.has_state(f"{PURPOSE}.combat-riding") or all(knows(animal, t) for t in want)


def domestic(animal) -> bool:
    from . import animal_companion

    return bool(animal.has_state(DOMESTIC)
                or str(getattr(animal, "from_template", "") or "") in DOMESTIC_TEMPLATES
                or animal_companion.is_animal_companion(animal))


def _taught(animal) -> list[str]:
    """Tricks that count against the book's limit: taught or trained, never a companion's
    bonus tricks ("they don't count against the normal trick limit")."""
    out: list[str] = []
    for e in animal.effects:
        if str(e.key or "").startswith(("trick:", "purpose:")):
            out += [t.split(".", 1)[1] for t in e.tags or () if t.startswith(TRICK + ".")]
    return list(dict.fromkeys(out))


def room_for(animal, count: int = 1) -> bool:
    """CRB: Int 1 learns three tricks at most, Int 2 six. Int 3 and up: the book names no
    limit here, so none is applied (could not source one)."""
    score = _int(animal)
    most = (_row("teach").get("max_tricks") or {}).get(str(score))
    return most is None or len(_taught(animal)) + count <= int(most)


def _effect(name: str, key: str, tags, by: str, origin: str, payload=None):
    from .activeeffect import ActiveEffect

    return ActiveEffect(name=name, kind="bond", key=key, source=f"taught:{by}",
                        origin=origin, duration="until-dismissed", tags=tuple(tags),
                        payload=dict(payload or {}))


def teach_trick(animal, trick: str, by: str, origin: str = SOURCE + ".teach") -> None:
    t = _slug(trick)
    animal.apply_effect(_effect(f"knows the trick: {trick}", f"trick:{t}",
                                (f"{TRICK}.{t}",), by, origin))


def train_purpose(animal, purpose: str, by: str, origin: str = SOURCE + ".train") -> None:
    """One purpose an animal: a new one replaces the old and its tricks (CRB, combat
    riding's upgrade: "completely replace the animal's previous purpose and any tricks it
    once knew")."""
    row = purposes()[purpose]
    animal.remove_effects(match=lambda e: str(e.key or "").startswith("purpose:"))
    if row.get("upgrade_from"):
        animal.remove_effects(match=lambda e: str(e.key or "").startswith("trick:"))
    animal.apply_effect(_effect(
        f"trained for {purpose}", f"purpose:{_slug(purpose)}",
        (f"{PURPOSE}.{_slug(purpose)}", *(f"{TRICK}.{t}" for t in row["tricks"])),
        by, origin))


def make_domestic(animal, by: str, origin: str) -> None:
    animal.apply_effect(_effect("domesticated", "domestic", (DOMESTIC,), by, origin))


def command(animal):
    """The handled command on this animal: (trick, at ref, pushed), or None."""
    e = next((e for e in getattr(animal, "effects", ()) if e.key == "handled"), None)
    if e is None:
        return None
    pay = e.payload or {}
    return str(pay.get("trick") or ""), str(pay.get("at") or ""), bool(pay.get("pushed"))


def command_words(scene, animal) -> str:
    """The animal's standing command, in words, for its own turn and the brief."""
    got = command(animal)
    if not got:
        return ""
    trick, at, _pushed = got
    who = scene.actors.get(at) if at else None
    return f"{trick}" + (f" {who.name} ({who.ref})" if who is not None else "")


def character_line(scene, actor) -> str:
    """What a wordless creature is, for its own turn: an animal, its tricks, its command.
    No numbers."""
    tricks_known = known(actor)
    knows_line = (f"it knows these tricks: {', '.join(tricks_known)}" if tricks_known
                  else "it knows no tricks")
    cmd = command_words(scene, actor)
    return (f"{actor.name} is an animal: it does not understand words, and {knows_line}. "
            + (f"It was commanded (Handle Animal): {cmd} — that is what it does. "
               if cmd else "Nobody has commanded it; it does what an animal would. "))


# --- the check's doors ----------------------------------------------------------------------

def _link(animal, handler) -> bool:
    """A druid's (or ranger's) own companion with the link: free/move handling, +4."""
    from . import animal_companion

    return (animal_companion.master_ref(animal) == getattr(handler, "ref", None)
            and animal.has_state("companion.link"))


def _wounded(animal) -> bool:
    return (int(animal.hp) < int(animal.hp_max) or int(getattr(animal, "nonlethal", 0) or 0)
            or any(int(v or 0) for v in (getattr(animal, "ability_damage", None) or {}).values()))


def _mods(actor, animal, *, untrained_ok: bool):
    """(the handler's modifiers, label, why not) — the skill, else the book's Charisma
    check on a domestic animal or one's own companion."""
    from .dice import Modifier
    from .sheet import IllegalSheet

    link = _link(animal, actor)
    try:
        mods, label = list(actor.skill_modifiers("handle animal")), "Handle Animal check"
    except IllegalSheet:
        if not untrained_ok or not (domestic(animal) or link):
            return None, "", (f"{actor.name} has no training in Handle Animal: untrained, "
                              f"only a domestic animal (or one's own companion) can be "
                              f"handled or pushed, by a Charisma check, and nothing can be "
                              f"taught, trained or reared. Nothing is rolled.")
        mods, label = (list(actor.ability_check_modifiers("cha")),
                       "Charisma check (Handle Animal, untrained)")
    if link:
        mods.append(Modifier(int(_row("wild-empathy")["link_bonus"]),
                             "the link with an animal companion", "circumstance"))
    # Falconer's Art (ISWG): "+2 bonus on Animal Handling checks made to train or control
    # birds of prey" — its document's tag, and the animal answered by what it is.
    from . import feat_events

    if actor.has_state(feat_events.HANDLES_BIRDS) and feat_events.bird_of_prey(animal):
        mods.append(Modifier(2, "Falconer's Art (a bird of prey)"))
    return mods, label, ""


def _refused(engine, intent, why: str, code: str = ""):
    return engine._refuse(intent, why, code=code)


def check(engine, intent, actor, partial):
    """A Handle Animal check: the use's door (the reader's closed `use`)."""
    use = str(intent.params.get("use") or "handle")
    door = {"handle": handle, "push": handle, "teach": teach, "train": train,
            "rear": rear}.get(use, handle)
    return door(engine, intent, actor, partial)


def _animal(engine, intent, actor):
    from .skilluses import _target

    animal = _target(engine, intent)
    if animal is None:
        return None, "Handle Animal is aimed at an animal here: name it as the target."
    if not handleable(animal):
        return None, (f"{animal.name} is no animal: Handle Animal works on animals and "
                      f"creatures of an animal's mind. Nothing is rolled.")
    if animal.is_down:
        return None, f"{animal.name} is in no state to do anything. Nothing is rolled."
    return animal, ""


def handle(engine, intent, actor, partial):
    """Handle (DC 10, a trick it knows) or push (DC 25, one it does not), CRB Handle
    Animal. A handle of a trick it does not know IS a push: the book has no other way to
    ask for it. Success lays `handled.<trick>` — "the animal performs the task or trick on
    its next action" — which its own turn is told and held to (gm/companions.py); out of a
    fight an attack is made at once, through the battle gate."""
    from . import attitude as attitude_mod
    from . import dc as dc_mod
    from .activeeffect import ActiveEffect
    from .skilluses import _no_action_left, _outcome, _spend_action

    animal, why = _animal(engine, intent, actor)
    if why:
        return _refused(engine, intent, why)
    trick = _slug(intent.params.get("trick"))
    if trick not in tricks():
        return _refused(engine, intent, f"Handle Animal asks for a trick: one of "
                                        f"{', '.join(tricks())}. Nothing is rolled.")
    if attitude_mod.of(animal) == attitude_mod.HOSTILE:
        return _refused(engine, intent, f"{animal.name} is hostile and takes no command "
                                        f"from {actor.name}: calm it first (wild empathy). "
                                        f"Nothing is rolled.")
    at = str(intent.params.get("at") or "")
    target = engine.scene.actors.get(at) if at else None
    if trick == "attack":
        if target is None or target is animal or target is actor:
            return _refused(engine, intent, "The attack trick is pointed at somebody here: "
                                            "name them with `at`. Nothing is rolled.")
        if target.has_state("type") and not any(target.has_state(t) for t in ATTACKS_TYPES):
            # Unless it was taught to attack anything (two tricks), which is not built.
            return _refused(engine, intent, f"{animal.name} will not attack {target.name}: "
                                            f"an animal attacks only humanoids, monstrous "
                                            f"humanoids, giants or other animals. Nothing "
                                            f"is rolled.")
    pushed = str(intent.params.get("use") or "") == "push" or not knows(animal, trick)
    r = _row("push" if pushed else "handle")
    mods, label, why = _mods(actor, animal, untrained_ok=True)
    if why:
        return _refused(engine, intent, why)
    link = _link(animal, actor)
    action = str(r["link_action"] if link else r["action"])
    what = f"{'pushing' if pushed else 'handling'} {animal.name}"
    spent = _no_action_left(engine, actor, action, what)
    if spent:
        return _refused(engine, intent, spent + " Nothing is rolled.", "action_spent")
    value = int(r["dc"])
    basis = [f"{'push' if pushed else 'handle'} {value}"]
    if _wounded(animal):
        value += int(r["wounded"])
        basis.append(f"hurt +{r['wounded']}")
    if not animal.has_state("type.animal"):
        value += int(r["not_an_animal"])
        basis.append(f"not an animal +{r['not_an_animal']}")
    roll = engine._roll_or_suspend(intent, actor, mods, label=label + f" ({trick})",
                                   dc=value, partial=partial)
    _spend_action(engine, actor, action)
    margin = roll.total - value
    doing = f"{trick} {target.name}" if target is not None else trick
    unknown = (f" {animal.name} does not know {trick}, so it is pushed." if pushed
               and not knows(animal, trick) else "")
    if margin < 0:
        return _outcome(intent, rolls=[roll], dc_value=value, basis=", ".join(basis),
                        verdict="failure", margin=margin,
                        tell=f"{actor.name} tries to get {animal.name} to {doing}."
                             f"{unknown} It does not: {label} missed by {-margin}.")
    animal.remove_effects(match=lambda e: e.key == "handled")
    animal.apply_effect(ActiveEffect(
        name=f"commanded: {doing}", kind="situation", key="handled",
        source=f"handled:{actor.ref}", origin=SOURCE + (".push" if pushed else ".handle"),
        duration="until-dismissed", tags=(f"{HANDLED}.{trick}",),
        payload={"trick": trick, "at": target.ref if target is not None else "",
                 "by": actor.ref, "pushed": pushed}))
    effects = [{"ref": animal.ref, "kind": "handled", "trick": trick, "pushed": pushed,
                "at": target.ref if target is not None else "",
                "origin": SOURCE + (".push" if pushed else ".handle")}]
    when = ("on its turn" if engine.scene.in_encounter else "now")
    tell = (f"{actor.name} {'pushes' if pushed else 'handles'} {animal.name}"
            f"{dc_mod.by(margin)}.{unknown} {animal.name} will {doing} {when}.")
    if trick == "attack" and not engine.scene.in_encounter:
        # Out of a fight the blow is struck at once: the animal's own attack, through the
        # battle gate (first violence opens the fight, never resolves it).
        went = engine._run_within(engine.validate(
            [{"op": "attack", "actor": animal.ref, "target": target.ref,
              "visibility": "hidden", "because": f"{actor.name} set it on them"}]))
        for o in went:
            effects += list(o.effects or [])
            tell = f"{tell} {o.tell}".strip()
    out = _outcome(intent, rolls=[roll], dc_value=value, basis=", ".join(basis),
                   verdict="success", margin=margin, effects=effects, tell=tell)
    return out


def _with_you(engine, actor, animal) -> str:
    """Why this animal cannot be worked with for weeks, or ""."""
    from . import animal_companion

    if animal.has_state(states.TRAVELS_WITH_YOU) or \
            animal_companion.master_ref(animal) == actor.ref:
        return ""
    return (f"{animal.name} does not travel with {actor.name}: lessons take weeks, three "
            f"hours a day, with the animal at hand. Nothing is rolled.")


def _lessons_on(actor, animal) -> bool:
    from . import inprogress

    now = None
    for item in (getattr(actor, "stock", None) or {}).values():
        block = inprogress.work_of(item, now)
        if block and block.get("craft") == CRAFT \
                and (block.get("result") or {}).get("animal") == animal.ref:
            return True
    return False


def _long_work(engine, intent, actor, animal, partial, *, use: str, value: int,
               basis: str, weeks: int, label: str, result: dict, success_words: str):
    """Teaching, training and rearing: the check at the start, then the work In progress
    on the world clock. CRB: half the time is spent before the check, and "If the check
    fails, your attempt ... fails and you need not complete the teaching" — so a miss
    holds the animal for half the time and teaches nothing; a make holds it for all of it.
    Collected from the In progress section, with the animal still at hand."""
    from . import dc as dc_mod
    from . import inprogress, sky
    from .crafting import Stock
    from .skilluses import _outcome

    if engine.scene.in_encounter:
        return _refused(engine, intent, f"{label} is weeks of work, not a fight's round. "
                                        f"Nothing is rolled.")
    away = _with_you(engine, actor, animal)
    if away:
        return _refused(engine, intent, away)
    if _lessons_on(actor, animal):
        return _refused(engine, intent, f"{animal.name} is already being worked with; "
                                        f"finish that first (In progress). Nothing is rolled.")
    mods, label_roll, why = _mods(actor, animal, untrained_ok=False)
    if why:
        return _refused(engine, intent, why)
    roll = engine._roll_or_suspend(intent, actor, mods, label=label_roll + f" ({label})",
                                   dc=value, partial=partial)
    margin = roll.total - value
    made = margin >= 0
    minutes = int(weeks) * 7 * 24 * 60 // (1 if made else 2)
    now = int(engine.scene.clock_minutes)
    item = Stock(base=f"{label} ({animal.name})", craft=CRAFT, kind="lessons")
    key = inprogress.fresh_key(actor, f"lessons-{animal.ref}")
    actor.stock[key] = item
    inprogress.begin(actor, key, craft=CRAFT, minutes=minutes, now=now, label=label,
                     doing="teaching", result=dict(result, animal=animal.ref,
                                                   animal_name=animal.name, made=made,
                                                   by=actor.ref))
    span = sky.span_words(minutes)
    if made:
        tell = (f"{actor.name} begins: {label}{dc_mod.by(margin)}. Three hours a day "
                f"for {span}, with {animal.name} at hand; then {success_words}. It waits "
                f"In progress.")
    else:
        tell = (f"{actor.name} begins: {label}, and misses the check by {-margin}: "
                f"after {span} of lessons {animal.name} will not have learned it. It "
                f"waits In progress.")
    return _outcome(intent, rolls=[roll], dc_value=value, basis=basis,
                    verdict="success" if made else "failure", margin=margin,
                    effects=[{"ref": animal.ref, "kind": "lessons", "use": use,
                              "made": made, "minutes": minutes, "key": key,
                              "origin": f"{SOURCE}.{use}"}],
                    tell=tell)


def teach(engine, intent, actor, partial):
    """Teach a trick: a week, the trick's DC (+5 for a creature that is not an animal)."""
    animal, why = _animal(engine, intent, actor)
    if why:
        return _refused(engine, intent, why)
    trick = _slug(intent.params.get("trick"))
    if trick not in tricks():
        return _refused(engine, intent, f"Teach which trick? One of {', '.join(tricks())}. "
                                        f"Nothing is rolled.")
    if knows(animal, trick):
        return _refused(engine, intent, f"{animal.name} already knows {trick}.")
    if not room_for(animal):
        return _refused(engine, intent, f"{animal.name} has learned all the tricks an "
                                        f"animal of its wits can hold. Nothing is rolled.")
    r = _row("teach")
    value = int(tricks()[trick]) + (0 if animal.has_state("type.animal")
                                    else int(r["not_an_animal"]))
    return _long_work(engine, intent, actor, animal, partial, use="teach", value=value,
                      basis=f"the trick's DC {tricks()[trick]}", weeks=int(r["weeks"]),
                      label=f"teaching {animal.name} to {trick}",
                      result={"kind": "teach", "trick": trick},
                      success_words=f"{animal.name} knows {trick}")


def train(engine, intent, actor, partial):
    """Train for a general purpose: the purpose's DC and weeks; combat riding from riding
    is the 3-week upgrade."""
    animal, why = _animal(engine, intent, actor)
    if why:
        return _refused(engine, intent, why)
    purpose = " ".join(str(intent.params.get("purpose") or "").lower().replace("-", " ")
                       .split())
    rows = purposes()
    if purpose not in rows:
        return _refused(engine, intent, f"Train it for which purpose? One of "
                                        f"{', '.join(rows)}. Nothing is rolled.")
    p = rows[purpose]
    if purpose_of(animal) == purpose:
        return _refused(engine, intent, f"{animal.name} is already trained for {purpose}.")
    if len(p["tricks"]) > 3 and (_int(animal) or 0) < 2:
        return _refused(engine, intent, f"{animal.name} has too few wits for {purpose}: "
                                        f"a package of more than three tricks needs an "
                                        f"Intelligence of 2. Nothing is rolled.")
    upgrade = p.get("upgrade_from") and purpose_of(animal) == p["upgrade_from"]
    weeks = int(p["upgrade_weeks"] if upgrade else p["weeks"])
    value = int(p["dc"]) + (0 if animal.has_state("type.animal")
                            else int(_row("train")["not_an_animal"]))
    return _long_work(engine, intent, actor, animal, partial, use="train", value=value,
                      basis=f"{purpose} DC {p['dc']}", weeks=weeks,
                      label=f"training {animal.name} for {purpose}",
                      result={"kind": "train", "purpose": purpose},
                      success_words=f"{animal.name} is trained for {purpose}")


def rear(engine, intent, actor, partial):
    """Rear a wild animal: DC 15 + its Hit Dice, a year, and no second try (CRB). Owner
    call: the world has no young animals, so a wild animal that is at least indifferent
    and travels with you is what can be reared; a year of it domesticates the animal."""
    from . import attitude as attitude_mod

    animal, why = _animal(engine, intent, actor)
    if why:
        return _refused(engine, intent, why)
    if domestic(animal):
        return _refused(engine, intent, f"{animal.name} is no wild animal: there is "
                                        f"nothing to rear. Teach or train it instead.")
    if animal.has_state(REAR_TRIED):
        return _refused(engine, intent, f"{animal.name} was reared once and did not take "
                                        f"to it: rearing is never tried again.")
    if attitude_mod.step_of(attitude_mod.of(animal)) < attitude_mod.step_of("indifferent"):
        return _refused(engine, intent, f"{animal.name} will not be raised by "
                                        f"{actor.name}: it is {attitude_mod.of(animal)}. "
                                        f"Nothing is rolled.")
    r = _row("rear")
    hd = max(1, int(getattr(animal, "level", 1) or 1))
    out = _long_work(engine, intent, actor, animal, partial, use="rear",
                     value=int(r["dc_base"]) + hd,
                     basis=f"{r['dc_base']} + {hd} Hit Dice", weeks=int(r["weeks"]),
                     label=f"rearing {animal.name}", result={"kind": "rear"},
                     success_words=f"{animal.name} is domesticated")
    if out.status == "resolved" and out.verdict in ("success", "failure"):
        animal.apply_effect(_effect("reared once", "rear-tried", (REAR_TRIED,), actor.ref,
                                    SOURCE + ".rear"))
    return out


def _collect(item, actor) -> dict:
    """The work done: the trick, the purpose or the domestication laid on the animal —
    still at hand ("If the time is interrupted ... the attempt automatically fails")."""
    from . import inprogress

    block = inprogress.work_of(item, None) or {}
    res = dict(block.get("result") or {})
    for k, v in list((actor.stock or {}).items()):
        if v is item:
            del actor.stock[k]
    animal = _find_animal(actor, res.get("animal"))
    name = str(res.get("animal_name") or "the animal")
    if not res.get("made"):
        return {"said": f"{name} never took to the lessons: it has learned nothing."}
    if animal is None or animal.is_down:
        return {"said": f"{name} is not at hand, and the lessons were broken off: it has "
                        f"learned nothing."}
    kind = res.get("kind")
    if kind == "teach":
        teach_trick(animal, res["trick"], actor.ref)
        return {"said": f"{animal.name} has learned the trick: {res['trick']}."}
    if kind == "train":
        train_purpose(animal, res["purpose"], actor.ref)
        return {"said": f"{animal.name} is trained for {res['purpose']}: "
                        f"{', '.join(purposes()[res['purpose']]['tricks'])}."}
    make_domestic(animal, actor.ref, SOURCE + ".rear")
    return {"said": f"{animal.name} is domesticated: raised by {actor.name}."}


# The scene the In progress door collects in. shortcut: the collect callback is handed
# the actor only, so the view lends the live scene here before it collects
# (play/works_views.py); upgrade to a `scene` argument on `inprogress.collect` if a second
# craft ever needs a body other than the collector's.
_LENT: dict = {}


def lend_scene(scene) -> None:
    _LENT["scene"] = scene


def _find_animal(actor, ref):
    scene = _LENT.get("scene")
    people = getattr(scene, "people", None) or {}
    animal = people.get(str(ref or ""))
    if animal is None:
        return None
    from . import animal_companion

    with_you = (animal.has_state(states.TRAVELS_WITH_YOU)
                or animal_companion.master_ref(animal) == actor.ref)
    here = getattr(scene, "actors", {}) or {}
    return animal if with_you and animal.ref in here else None


def _register() -> None:
    from . import inprogress

    inprogress.register(CRAFT, collect=_collect, icon="study",
                        stop_words="The lessons end, and nothing is learned.",
                        cancel=lambda item, actor: _cancel(item, actor))


def _cancel(item, actor) -> dict:
    for k, v in list((actor.stock or {}).items()):
        if v is item:
            del actor.stock[k]
    return {"said": "The lessons end, and nothing is learned."}


_register()


# --- wild empathy ---------------------------------------------------------------------------

# Vermin Heart (APG p.173, aonprd 2026-11-26): "You may use wild empathy to influence vermin
# as easily as you influence animals", and target vermin "with spells and special abilities
# that only affect animals" — held as this tag by the feat's document (b3-arcane.json).
VERMIN_AS_ANIMALS = "reach.vermin-as-animals"


def empathy_reaches(target, by=None) -> int | None:
    """The check's term for this creature, or None when wild empathy cannot reach it: an
    animal at +0, a magical beast of Int 1 or 2 at -4 (CRB); vermin at +0 for one who
    holds Vermin Heart."""
    if target is None:
        return None
    if target.has_state("type.animal"):
        return 0
    if target.has_state("type.vermin") and by is not None \
            and by.has_state(VERMIN_AS_ANIMALS):
        return 0
    if target.has_state("type.magical-beast") and _int(target) in (1, 2):
        return int(_row("wild-empathy")["magical_beast"])
    # Feat loop b4-maneuver: Greater Wild Empathy's chosen kind of creature.
    from . import maneuver_feats

    if by is not None and maneuver_feats.empathy_reaches_more(target, by):
        return 0
    return None


def wild_empathy(engine, intent, actor, target, partial, how: str = "diplomacy"):
    """Wild empathy: Diplomacy's Influence Attitude for animals, by the same machinery —
    the attitude's DC, the once-a-day limit, `Engine._sway` (the one applicator). `how`
    "intimidate" is Greater Wild Empathy's "use wild empathy to duplicate an Intimidate
    check rather than a Diplomacy check" (feat loop b4-maneuver): Intimidate's DC and
    Intimidate's consequence, the wild empathy roll."""
    from . import attitude as attitude_mod
    from . import dc as dc_mod
    from .dice import Modifier
    from .skilluses import _outcome

    r = _row("wild-empathy")
    penalty = empathy_reaches(target, actor)
    if penalty is None:
        return _refused(engine, intent, f"Wild empathy reaches animals, and magical beasts "
                                        f"of an animal's mind: not {target.name}. Nothing "
                                        f"is rolled.")
    # Fast Empathy (UM, feat loop b4-other): "Using wild empathy is a standard action for
    # you" — its document's tag lets it into a fight's round, where the check op spends
    # the standard action as any check does.
    if engine.scene.in_encounter and not actor.has_state("empathy.fast"):
        return _refused(engine, intent, f"Wild empathy takes a minute of calm work, not a "
                                        f"fight's round. Nothing is rolled.")
    gap = engine._gap_ft(actor, target)
    if gap is not None and gap > int(r["range_ft"]):
        return _refused(engine, intent, f"{target.name} is {int(gap)} feet away: wild "
                                        f"empathy works within {r['range_ft']} feet. "
                                        f"Nothing is rolled.")
    refused = engine._sway_refusal(intent, actor, target, how)
    if refused is not None:
        return refused
    mods = empathy_mods(actor)
    if penalty:
        mods.append(Modifier(penalty, "a magical beast"))
    if _link(target, actor):
        mods.append(Modifier(int(r["link_bonus"]), "the link with an animal companion",
                             "circumstance"))
    value = (attitude_mod.intimidate_dc(target) if how == "intimidate"
             else attitude_mod.influence_dc(target))
    roll = engine._roll_or_suspend(intent, actor, mods, label="Wild empathy check",
                                   dc=value, partial=partial)
    margin = roll.total - value
    moved, effects = engine._sway(actor, target, how, margin,
                                  intent.because or "wild empathy")
    tell = (f"{actor.name} works on {target.name} with wild empathy"
            + (f"{dc_mod.by(margin)}." if margin >= 0 else f", and misses by {-margin}.")
            + f" {moved}")
    return _outcome(intent, rolls=[roll], dc_value=value,
                    basis="wild empathy: " + attitude_mod.dc_basis(target, how),
                    verdict="success" if margin >= 0 else "failure", margin=margin,
                    effects=effects, tell=tell.strip())


def empathy_mods(actor) -> list:
    """The wild empathy roll's terms: "1d20 and adds his druid level and his Charisma
    modifier" (CRB), and what the funnel aims at it (`wild_empathy`: Greater Wild
    Empathy's +2 insight, feat loop b4-maneuver)."""
    from .dice import Modifier, stack

    return [Modifier(int(actor.level), f"{actor.char_class} level"),
            Modifier(int(actor.ability_mod("cha")), "Charisma"),
            *stack(actor._buff_mods("combat_mod", "wild_empathy"))]


def social_door(engine, intent, actor, skill: str, partial):
    """Diplomacy aimed at a creature Diplomacy cannot reach: wild empathy for those who
    have it, else refused with the fix named. A Handle Animal check: its uses. None for
    everything else, which goes on as it did."""
    skill = str(skill or "").lower()
    if skill == "handle animal":
        return check(engine, intent, actor, partial)
    # Feat loop b4-maneuver: Greater Wild Empathy's Intimidate by wild empathy.
    from . import maneuver_feats

    cowed = maneuver_feats.empathy_intimidates(engine, intent, actor, skill, partial)
    if cowed is not None:
        return cowed
    if skill != "diplomacy" or intent.params.get("opposed_by"):
        return None
    from .skilluses import _target

    target = _target(engine, intent)
    bar = diplomacy_bar(target, actor)
    if not bar:
        return None
    if actor.has_state("class.wild-empathy") and empathy_reaches(target, actor) is not None \
            and not intent.params.get("request"):
        return wild_empathy(engine, intent, actor, target, partial)
    return _refused(engine, intent,
                    f"Diplomacy cannot move {target.name}: {bar}. Handle Animal commands an "
                    f"animal in the tricks it knows; a druid's or ranger's wild empathy can "
                    f"calm one. Nothing is rolled.")
