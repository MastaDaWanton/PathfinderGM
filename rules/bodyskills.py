"""The body and movement skill uses (round 2 of the 2026-11-22 implementation lanes).

docs/implementation-audit-2026-11-22.md measured Fly and Ride with no resolved use at all,
Climb as a way of moving absent ("climbing is not a way of moving"), Acrobatics' jump and
soften-fall absent, Escape Artist only against a grapple, and Heal's treat poison and treat
disease absent while the affliction executor (`Actor._afflicted`) rolled every save with
nothing a healer could add. This module is those uses' door. Each is a row of
content/rules/skill-uses.json (round 1's table, read by rules/skilluses.py) and resolves
through `Engine._op_check` like lane E's: the row's DC (or the book's table the row
quotes), the row's action, and the consequence through the one applicator.

How a use is chosen: the check's `use` param, a closed word per skill (`USES`), which the
declared-op schema offers the plan as an enum (gm/prompts.py `_declared_op`) — models
read, code validates. Four are the engine's own default when no `use` is named, because
the skill has only the one thing it can mean in that state (`default_use`): a Climb check
is climbing, an Escape Artist check by somebody tied or netted is slipping the bonds, a
Heal check at somebody poisoned or diseased (and not dying) is treating it, and a Ride
check with a mount here and nobody in its saddle is getting on.

The fiction's one scalar: a jump's `distance_ft`, and the `height_ft` of a climb, a drop or
a fall — the same sanctioned shape as the `hazard` op's `distance_ft` (content/rules/
hazards.json: "the one scalar only the fiction supplies, with bounds"), bounded at parse
(rules/intents.py). The DC for a surface (a wall, a ledge) is the plan's band, which is
the Core Rulebook's own table: Climb's DCs are 0/5/10/15/20/25/30 and so are the bands
(rules/tables.py DC_BANDS); Acrobatics' narrow-surface widths are 0/5/10/15/20.

Rules text: the Core Rulebook's, as d20pfsrd.com and aonprd.com print it (read
2026-11-22; docs/research/2026-11-22-skills-body.md says what each use quotes and what
could not be sourced).
"""
from __future__ import annotations

from .skilluses import _no_action_left, _outcome, _spend_action, _target, row

# The closed `use` words, per skill. The row id is `skill.<skill-with-hyphens>.<use>`.
USES: dict[str, tuple[str, ...]] = {
    "acrobatics": ("jump", "high-jump", "soften-fall", "balance"),
    "climb": ("move",),
    "escape artist": ("bonds", "squeeze"),
    "fly": ("slow", "hover", "turn", "turn-about", "fly-up", "wind"),
    "ride": ("mount", "dismount", "spur", "cover", "leap"),
    "heal": ("treat-poison", "treat-disease"),
    # Handle Animal (rules/animals.py, round 3): its uses are declared the same way, and
    # resolved before the skill's training is asked (an untrained handler may still make
    # the book's Charisma check on a domestic animal), by `animals.social_door`.
    "handle animal": ("handle", "push", "teach", "train", "rear"),
}
WINDS = ("light", "moderate", "strong", "severe", "windstorm", "hurricane", "tornado")

CLIMBING = "state.position.climbing"
BALANCING = "state.position.balancing"
MOUNTED = "state.position.mounted"
RIDDEN = "state.position.ridden"
MOUNT_COVER = "state.position.mount-cover"
WIND_HELD = "state.held.wind"
TREATED = "care.treated"
MOUNTED_COMBAT = "skill.ride.mounted-combat"
CLIMB_SOURCE, BALANCE_SOURCE, RIDE_SOURCE = "rule:climb", "rule:balance", "rule:ride"


TRICK_RIDING = "skill.ride.trick-riding"


def _trick_ridden(engine, rider, mods, dc: int, label: str):
    """Trick Riding (CRB): "While wearing light or no armor, you do not need to make Ride
    skill checks for any task listed in the Ride skill with a DC of 15 or lower." The
    task is done without a die: a roll stands in at the face that meets the DC (shown as
    such), so the callers' arithmetic and records stay one shape. None otherwise.
    shortcut: a body whose Ride is so poor that a natural 20 misses DC 15 keeps the 20."""
    from . import armour as armour_mod

    if dc > 15 or not rider.has_state(TRICK_RIDING):
        return None
    worn = armour_mod.row("armour", str(getattr(rider, "armour", "none") or "none"))
    if str(getattr(rider, "armour", "none") or "none") != "none" \
            and str(worn.get("weight") or "") != "light":
        return None
    total = sum(int(getattr(m, "value", 0)) for m in mods or ())
    return engine.dice.given(max(1, min(20, dc - total)), list(mods),
                             label=f"{label} — no check needed (Trick Riding)")


def _prone(actor, source: str, origin: str) -> None:
    """Down on the ground: the one condition 1e names for every way a body here falls."""
    actor.add_condition("prone", source=source, origin=origin)


def use_id(skill: str, use: str) -> str:
    return f"skill.{str(skill).strip().lower().replace(' ', '-')}.{use}"


def _held(actor, tag: str):
    return next((e for e in actor.effects if any(t == tag or t.startswith(tag + ".")
                                                 for t in e.tags or ())), None)


def default_use(engine, intent, actor) -> str:
    """The use a check means when it names none, read off the engine's state — or "".
    Climb is climbing; Escape Artist by somebody tied or netted is slipping it; Heal at
    somebody poisoned or diseased (and not dying) is treating it; Ride with a mount here
    and nobody in its saddle is getting on."""
    skill = str(intent.params.get("skill") or "").lower()
    if skill == "climb" and not actor.has_state("state.position.pit"):
        return "move"
    if skill == "escape artist" and _bonds_on(actor) is not None:
        return "bonds"
    if skill == "ride" and mount_of(engine.scene, actor) is None:
        # Not in the saddle, with a mount here to get on: the Ride check is getting on.
        # Measured live 2026-11-22: "I mount my horse, the bay mare." planned a plain
        # Ride check at "average" and nobody sat on the horse.
        steed = _steed_here(engine, intent, actor)
        if steed is not None and not _rideable(actor, steed):
            return "mount"
    if skill == "heal":
        from . import firstaid

        patient = _patient(engine, intent, actor)
        if patient is not None and not firstaid.needs_aid(patient):
            if _affliction(patient, "poisoned") is not None:
                return "treat-poison"
            if _affliction(patient, "diseased") is not None:
                return "treat-disease"
    return ""


def door_for(engine, intent, actor):
    """The function that resolves this check, or None (the generic check stands)."""
    if intent.params.get("opposed_by") or intent.params.get("aid"):
        return None
    skill = str(intent.params.get("skill") or "").lower()
    if skill == "climb" and actor.has_state("state.position.pit"):
        return None                      # the pit's own climb out (`dungeons.climb_out`)
    use = str(intent.params.get("use") or "") or default_use(engine, intent, actor)
    if use not in USES.get(skill, ()):
        return None
    return DOORS.get(use_id(skill, use))


def _roll(engine, actor, mods, label: str):
    """A roll the use makes after its first (a catch, a save, the next stretch): shown to
    the player when it is theirs, rolled by the engine either way — `_op_move`'s climb's
    shape (the player is not stopped twice inside one deed)."""
    return engine.dice.d20(list(mods), label=label,
                           visibility="player" if actor.is_pc else "hidden")


def _twice(engine, actor, roll, kind: str, against=()):
    """Sure Grasp (UC, feat loop b4-other): "Roll twice while climbing or when making a
    Reflex save to avoid falling, and take the higher result" (`luck.twice`). The second
    die is the engine's, beside the first (the player's own when it is theirs)."""
    from . import luck as luck_mod

    doc = luck_mod.twice(actor, kind, against)
    if doc is None:
        return roll
    again = engine.dice.d20(list(roll.modifiers), label=f"{roll.label} ({doc['name']}, "
                            f"the second die)", visibility="player" if actor.is_pc
                            else "hidden")
    return again if again.total > roll.total else roll


def _band_dc(intent, actor, default: int) -> tuple[int, str]:
    from . import dc as dc_mod

    spec = intent.params.get("dc")
    if not spec:
        return default, f"the book's DC {default}"
    got = dc_mod.resolve(spec, actor.level if actor.is_pc else 1)
    return int(got.value), f"the surface's DC {got.value} ({got.band})"


def _skill_mods(actor, skill: str):
    from .sheet import IllegalSheet

    try:
        return list(actor.skill_modifiers(skill))
    except IllegalSheet:
        return list(actor.ability_check_modifiers("dex"))


def _feet(intent, key: str) -> int | None:
    v = intent.params.get(key)
    return None if v in (None, "") else max(0, int(v))


# --- falling: the one door every use below drops a body through ------------------------------

def fall(engine, actor, feet: int, *, deliberate: bool = False, may_fly: bool = True,
         why: str = "falls") -> tuple[list, list, list[str]]:
    """A body falls `feet` (CRB, Environment: Falling, 1d6 per 10 feet to 20d6, a
    deliberate jump's first die nonlethal) through the `hazard` op's own row, so the dice
    are the row's. A body that can fly may make the DC 10 Fly check "to negate the
    damage" — never "if you are falling due to a failed Fly check" (`may_fly`). Damage
    from a fall leaves the body prone. Whatever held it on the wall or the ledge ends."""
    from .intents import Intent

    actor.remove_effects(match=lambda e: any(t.startswith((CLIMBING, BALANCING))
                                             for t in e.tags or ()))
    rolls, effects, said = [], [], []
    if may_fly and actor.movement_modes().get("fly") and feet >= 10:
        r = row("skill.fly.soft-landing")
        roll = _roll(engine, actor, _skill_mods(actor, "fly"), "Fly check (break the fall)")
        rolls.append(roll)
        if roll.total >= int(r["dc"]):
            return rolls, [{"ref": actor.ref, "kind": "fall", "feet": feet, "flew": True}], [
                f"{actor.name} {why} and catches the air before the ground (Fly "
                f"{roll.total} against DC {r['dc']}): no harm done."]
    if feet < 10:
        return rolls, [{"ref": actor.ref, "kind": "fall", "feet": feet}], [
            f"{actor.name} {why}, too short a drop to hurt."]
    out = engine._op_hazard(Intent(op="hazard", actor=actor.ref, because=why, params={
        "rule": "falling", "distance_ft": min(200, int(feet)), "to": actor.ref,
        **({"deliberate": True} if deliberate else {})}), {})
    rolls.extend(out.rolls or [])
    effects.extend(out.effects or [])
    said.append(f"{actor.name} {why}. {out.tell}")
    if any(e.get("kind") == "damage" and int(e.get("amount") or 0) > 0 for e in effects) \
            and not actor.is_down and not actor.has_state("state.position.prone"):
        _prone(actor, "a fall", origin="rule:falling")
        effects.append({"ref": actor.ref, "kind": "condition", "condition": "prone",
                        "origin": "rule:falling"})
        said.append(f"{actor.name} lands prone.")
    return rolls, effects, said


def _done(intent, roll, value, basis, margin, effects, bits, *, extra_rolls=()):
    return _outcome(intent, rolls=[roll, *extra_rolls], dc_value=value, basis=basis,
                    verdict="success" if margin >= 0 else "failure", margin=margin,
                    effects=effects, tell=" ".join(b for b in bits if b))


# --- Acrobatics -------------------------------------------------------------------------------

RUN_JUMP = "jump.running.run"           # Run's document tag (feat loop b5-spells)


def _run_term(actor, running: bool):
    """Run (CRB): "If you make a jump after a running start (see the Acrobatics skill
    description), you gain a +4 bonus on your Acrobatics check"."""
    from .dice import Modifier

    return [Modifier(4, "Run (a running start)")] \
        if running and actor.has_state(RUN_JUMP) else []


def _jump_term(actor):
    """"+4 racial bonus on Acrobatics checks made to jump for every 10 feet of their speed
    above 30 feet ... –4 racial penalty ... for every 10 feet of speed below 30 feet"."""
    from .dice import Modifier

    steps = int((int(actor.speed_feet) - 30) / 10)
    return [Modifier(4 * steps, f"speed {actor.speed_feet} ft (jumping)", "racial")] \
        if steps else []


def _run_up(engine, actor) -> bool:
    """A running start: out of a fight the jumper takes one (time and room are theirs); in
    a fight it is a move already made this round. shortcut: the book's "at least 10 feet"
    in a straight line is not measured; measure the path when a fight shows a jump from a
    standing start called running."""
    scene = engine.scene
    return not scene.in_encounter or scene.move_spent.get(actor.ref) == scene.round


def jump(engine, intent, actor, mods, partial, *, high: bool = False):
    """Acrobatics to jump (CRB, Acrobatics: Long Jump DC = the distance, High Jump DC = 4 x
    the height, doubled without a running start; the speed term; "No jump can allow you
    to exceed your maximum movement for the round"). A long jump missed by 4 or less is a
    DC 20 Reflex save to grab the far edge, held there as a climb; by 5 or more the body
    falls (into the `height_ft` drop below, else onto its face), a high jump lands prone."""
    from .dice import d20_succeeds
    from . import dc as dc_mod

    uid = use_id("acrobatics", "high-jump" if high else "jump")
    r = row(uid)
    feet = _feet(intent, "distance_ft")
    what = "high jump" if high else "jump"
    if not feet:
        return engine._refuse(intent, f"A {what} is made to a distance: give distance_ft, "
                                      f"the feet the fiction names. Nothing is rolled.")
    scene = engine.scene
    if scene.in_encounter and feet > 2 * int(actor.speed_feet):
        return engine._refuse(intent, f"{feet} feet is more than {actor.name} can cover in a "
                                      f"round ({2 * int(actor.speed_feet)} ft): no jump "
                                      f"exceeds a round's movement. Nothing is rolled.")
    running = _run_up(engine, actor)
    value = int(feet) * int(r["per_foot"]) * (1 if running else 2)
    basis = (f"{what} of {feet} ft: {r['per_foot']} x the distance"
             + ("" if running else ", doubled with no running start"))
    roll = engine._roll_or_suspend(intent, actor, [*mods, *_jump_term(actor),
                                                   *_run_term(actor, running)],
                                   label=f"Acrobatics check ({what})", dc=value,
                                   partial=partial)
    if scene.in_encounter:
        scene.move_spent[actor.ref] = scene.round      # a jump is part of a move
    margin = roll.total - value
    start = "" if running else " from a standing start"
    if margin >= 0:
        return _done(intent, roll, value, basis, margin,
                     [{"ref": actor.ref, "kind": "jump", "feet": feet, "made": True}],
                     [f"{actor.name} makes the {what} of {feet} feet{start}"
                      f"{dc_mod.by(margin)}."])
    if high:
        bits = [f"{actor.name} misses the {what} of {feet} feet by {-margin}."]
        fx = [{"ref": actor.ref, "kind": "jump", "feet": feet, "made": False}]
        if margin <= -5:
            _prone(actor, "a failed jump", origin=f"rule:{uid}")
            fx.append({"ref": actor.ref, "kind": "condition", "condition": "prone",
                       "origin": f"rule:{uid}"})
            bits.append(f"{actor.name} comes down hard and lands prone.")
        return _done(intent, roll, value, basis, margin, fx, bits)
    drop = _feet(intent, "height_ft") or 0
    extra, fx = [], [{"ref": actor.ref, "kind": "jump", "feet": feet, "made": False}]
    bits = [f"{actor.name} falls short of the {feet}-foot jump by {-margin}."]
    if margin >= -4:
        save = _twice(engine, actor, _roll(engine, actor, actor.save_modifiers("ref"),
                                           "Reflex save (grab the far edge)"),
                      "save.ref", ("fall",))
        extra.append(save)
        if d20_succeeds(save, int(r["edge_dc"])):
            if drop:
                _cling(actor, at=drop, top=drop, dc=int(r["edge_climb_dc"]), edge=True)
                fx.append({"ref": actor.ref, "kind": "condition", "condition": "climbing",
                           "origin": f"rule:{uid}"})
            bits.append(f"{actor.name} grabs the far edge (Reflex {save.total} against DC "
                        f"{r['edge_dc']})" + (" and hangs there: pulling up is a Climb "
                                              "check." if drop else " and scrambles up."))
            return _done(intent, roll, value, basis, margin, fx, bits, extra_rolls=extra)
        bits.append(f"The grab for the far edge misses (Reflex {save.total} against DC "
                    f"{r['edge_dc']}).")
    if drop:
        rolls, more, said = fall(engine, actor, drop, why="drops into the gap")
        extra += rolls
        fx += more
        bits += said
    else:
        _prone(actor, "a failed jump", origin=f"rule:{uid}")
        fx.append({"ref": actor.ref, "kind": "condition", "condition": "prone",
                   "origin": f"rule:{uid}"})
        bits.append(f"{actor.name} lands in a sprawl, prone.")
    return _done(intent, roll, value, basis, margin, fx, bits, extra_rolls=extra)


def high_jump(engine, intent, actor, mods, partial):
    return jump(engine, intent, actor, mods, partial, high=True)


def soften_fall(engine, intent, actor, mods, partial):
    """A deliberate jump down (CRB, Acrobatics: "a DC 15 Acrobatics skill check allows you
    to ignore the first 10 feet fallen", and Falling: a deliberate jump's first die is
    nonlethal). The drop is `height_ft`; the rest is the falling row's."""
    from . import dc as dc_mod

    r = row("skill.acrobatics.soften-fall")
    feet = _feet(intent, "height_ft")
    if not feet:
        return engine._refuse(intent, "A jump down is from a height: give height_ft, the "
                                      "feet of the drop. Nothing is rolled.")
    value = int(r["dc"])
    roll = engine._roll_or_suspend(intent, actor, list(mods),
                                   label="Acrobatics check (soften the fall)", dc=value,
                                   partial=partial)
    margin = roll.total - value
    eased = max(0, feet - int(r["ignores_ft"])) if margin >= 0 else feet
    bits = [f"{actor.name} jumps down {feet} feet"
            + (f" and rolls with the landing{dc_mod.by(margin)}, as if the drop were "
               f"{eased} feet." if margin >= 0 else
               f" and misses the Acrobatics check to soften it by {-margin}.")]
    rolls, fx, said = fall(engine, actor, eased, deliberate=True, why="lands")
    return _done(intent, roll, value, "soften a fall: DC 15", margin,
                 [{"ref": actor.ref, "kind": "jump_down", "feet": feet, "as_ft": eased},
                  *fx], bits + said, extra_rolls=rolls)


def balance(engine, intent, actor, mods, partial):
    """Acrobatics across a narrow or uneven surface (CRB: widths 0/5/10/15/20, the plan's
    band). Made: across at half speed, flat-footed while on it this round. Missed: "falling
    or being knocked prone" — into the `height_ft` drop below when there is one."""
    from .activeeffect import ActiveEffect
    from . import dc as dc_mod

    value, basis = _band_dc(intent, actor, int(row("skill.acrobatics.balance")["dc"]))
    roll = engine._roll_or_suspend(intent, actor, list(mods),
                                   label="Acrobatics check (balance)", dc=value,
                                   partial=partial)
    margin = roll.total - value
    scene = engine.scene
    if margin >= 0:
        fx = [{"ref": actor.ref, "kind": "balance", "made": True}]
        if scene.in_encounter:
            # shortcut: 2 rounds on the top-of-round ticker covers "this round" as the
            # feint's clock does; a per-turn clock would end it exactly.
            actor.apply_effect(ActiveEffect(
                name="balancing", kind="situation", key="balancing", source=BALANCE_SOURCE,
                origin=BALANCE_SOURCE, duration="rounds", rounds_left=2,
                tags=(BALANCING, "state.exposed.balancing")))
            fx.append({"ref": actor.ref, "kind": "condition", "condition": "balancing",
                       "origin": BALANCE_SOURCE})
        return _done(intent, roll, value, basis, margin, fx, [
            f"{actor.name} keeps their footing{dc_mod.by(margin)} and goes across at half "
            f"speed" + (", without their Dexterity to their defence while on it."
                        if scene.in_encounter else ".")])
    drop = _feet(intent, "height_ft") or 0
    bits = [f"{actor.name} misses the Acrobatics check by {-margin} and loses their footing."]
    if drop:
        rolls, fx, said = fall(engine, actor, drop, why="falls off")
        return _done(intent, roll, value, basis, margin, fx, bits + said, extra_rolls=rolls)
    _prone(actor, "lost footing", origin=BALANCE_SOURCE)
    return _done(intent, roll, value, basis, margin,
                 [{"ref": actor.ref, "kind": "condition", "condition": "prone",
                   "origin": BALANCE_SOURCE}], bits + [f"{actor.name} goes down prone."])


# --- Climb ------------------------------------------------------------------------------------

def _cling(actor, *, at: int, top, dc: int, edge: bool = False):
    from .activeeffect import ActiveEffect

    from . import feat_moves

    # Monkey Moves: "you retain your Dexterity bonus to AC while climbing" (feat loop b7).
    sure = bool(actor.movement_modes().get("climb")) or feat_moves.monkey_moving(actor)
    actor.apply_effect(ActiveEffect(
        name="climbing", kind="situation", key="climbing", source=CLIMB_SOURCE,
        origin=CLIMB_SOURCE,
        # "You lose your Dexterity bonus to AC" — not a climber by nature, who keeps it.
        # `recovery.rest`: a night's sleep is not spent on a wall.
        tags=(CLIMBING, "recovery.rest") + (() if sure else ("state.exposed.climbing",)),
        payload={"at": int(at), "top": top, "dc": int(dc), "edge": edge}))


def climb(engine, intent, actor, mods, partial):
    """Climbing as a way of moving (CRB, Climb). Each check is a move action's climb at a
    quarter of speed (a climb speed instead, for a climber by nature, with its +8 already
    in `skill_modifiers`); out of a fight the stretches are rolled one after another to
    `height_ft` or the first failure. Missed by 4 or less: no progress, still on the wall.
    By 5 or more: the body falls from the height reached, unless it catches itself — a
    Climb check at the wall's DC + 20 ("practically impossible"). While on the wall the
    climber loses Dexterity to AC (`state.exposed.climbing`)."""
    from . import dc as dc_mod

    r = row("skill.climb.move")
    held = _held(actor, CLIMBING)
    was = dict(held.payload or {}) if held else {}
    value, basis = (_band_dc(intent, actor, int(r["dc"])) if intent.params.get("dc")
                    or not was else (int(was["dc"]), f"the wall's DC {was['dc']}"))
    top = _feet(intent, "height_ft") or was.get("top")
    at = int(was.get("at") or 0)
    scene = engine.scene
    if scene.in_encounter:
        spent = _no_action_left(engine, actor, "move", "climbing")
        if spent:
            return engine._refuse(intent, spent + " Nothing is rolled.", code="action_spent")
    # Feat loop b7-moves: Monkey Moves (UC) climbs "at half your speed" in Monkey Style.
    from . import feat_moves

    share = 2 if feat_moves.monkey_moving(actor) else 4
    speed = int(actor.movement_modes().get("climb") or 0) or max(
        5, int(actor.speed_feet) // share)
    first = _twice(engine, actor, engine._roll_or_suspend(
        intent, actor, list(mods), label="Climb check", dc=value, partial=partial),
        "skill.climb")
    _spend_action(engine, actor, "move")
    rolls, roll, fx, bits = [], first, [], []
    while True:
        margin = roll.total - value
        if margin >= 0:
            at = at + speed if top is None else min(int(top), at + speed)
            if top is None or at >= int(top) or was.get("edge"):
                actor.remove_effects(source=CLIMB_SOURCE)
                fx.append({"ref": actor.ref, "kind": "climb", "made": True, "top": True})
                bits.append(f"{actor.name} climbs{dc_mod.by(margin)} and reaches the top"
                            + (f", {top} feet up" if top else "")
                            + (f", after {len(rolls) + 1} Climb checks." if rolls else "."))
                break
            if scene.in_encounter:
                _cling(actor, at=at, top=top, dc=value)
                fx.append({"ref": actor.ref, "kind": "climb", "made": True, "at": at})
                bits.append(f"{actor.name} climbs {speed} feet{dc_mod.by(margin)}, {at} of "
                            f"{top} feet up, without their Dexterity to their defence "
                            f"while on the wall.")
                break
            roll = _twice(engine, actor, _roll(engine, actor, mods, "Climb check"),
                          "skill.climb")
            rolls.append(roll)
            continue
        if margin >= -4:
            if at or held:
                _cling(actor, at=at, top=top, dc=value)
            fx.append({"ref": actor.ref, "kind": "climb", "made": False, "at": at})
            bits.append(f"{actor.name} misses the Climb check by {-margin} and makes no "
                        f"progress" + (f", {at} feet up." if at else "."))
            break
        if not at:
            fx.append({"ref": actor.ref, "kind": "climb", "made": False, "at": 0})
            bits.append(f"{actor.name} misses the Climb check by {-margin} and slides back "
                        f"to the ground before getting anywhere.")
            break
        catch_dc = value + int(row("skill.climb.catch")["adds"])
        # A feat's term on this roll alone (feat loop b2): Shield Snag's "+4 bonus ... on
        # Climb checks to catch yourself on a wall or slope when falling" with a shield.
        caught = _twice(engine, actor, _roll(engine, actor, list(mods) + actor._feat_mods(
            "skill_mod", "climb", {"skill_use": "catch"}, scoped=True),
            "Climb check (catch yourself)"), "skill.climb")
        rolls.append(caught)
        if caught.total >= catch_dc:
            _cling(actor, at=at, top=top, dc=value)
            fx.append({"ref": actor.ref, "kind": "climb", "made": False, "caught": True})
            bits.append(f"{actor.name} slips {at} feet up and catches the wall again (Climb "
                        f"{caught.total} against DC {catch_dc}).")
            break
        down, more, said = fall(engine, actor, at, why=f"loses their grip {at} feet up "
                                                       f"and falls")
        rolls += down
        fx += more
        bits.append(f"{actor.name} misses the Climb check by {-margin}, and the grab to catch "
                    f"the wall misses too (Climb {caught.total} against DC {catch_dc}).")
        bits += said
        break
    return _done(intent, first, value, basis, first.total - value, fx, bits,
                 extra_rolls=rolls)


# --- Escape Artist ----------------------------------------------------------------------------

def _bonds_on(actor):
    """The restraint an Escape Artist check slips: tied or manacled, or netted/entangled."""
    return _held(actor, "state.held.bound") or _held(actor, "state.held.entangled")


def _bonds_dc(engine, bonds) -> tuple[int, str]:
    """The table's DC for this restraint (CRB, Escape Artist)."""
    p = bonds.payload or {}
    if p.get("escape_dc"):
        return int(p["escape_dc"]), "the restraint's own DC"
    if "state.held.entangled" in " ".join(bonds.tags):
        return int(row("skill.escape-artist.bonds")["net_dc"]), "a net or entangling: DC 20"
    if any(t.startswith("state.held.bound.manacles") for t in bonds.tags):
        return int(row("skill.escape-artist.bonds")["manacles_dc"]), "manacles: DC 30"
    binder = engine.scene.actors.get(str(p.get("by") or ""))
    cmb = sum(m.value for m in binder.cmb_modifiers()) if binder is not None else 0
    return 20 + cmb, (f"rope tied by {binder.name}: 20 + CMB {cmb:+d}" if binder is not None
                      else "rope: 20 + the binder's CMB (+0, nobody's here)")


def bonds(engine, intent, actor, mods, partial):
    """Slip ropes, manacles or a net (CRB, Escape Artist): rope 20 + the binder's CMB, a net
    or entangle 20 (a full-round action), manacles 30; rope and manacles take a minute.
    "If the DC is higher than 20 + your Escape Artist bonus, you cannot escape." Made, the
    restraint's effect comes off."""
    from . import dc as dc_mod

    held = _bonds_on(actor)
    if held is None:
        return engine._refuse(intent, f"{actor.name} is not tied, manacled or netted: there "
                                      f"is nothing to slip. Nothing is rolled.")
    value, basis = _bonds_dc(engine, held)
    netted = "state.held.entangled" in " ".join(held.tags)
    scene = engine.scene
    if not netted and scene.in_encounter:
        return engine._refuse(intent, f"Working free of {held.name.lower()} takes a minute, "
                                      f"and there is a fight on. Nothing is rolled.")
    if netted:
        spent = _no_action_left(engine, actor, "full-round", "slipping a net")
        if spent:
            return engine._refuse(intent, spent, code="action_spent")
    bonus = sum(m.value for m in mods)
    if value > 20 + bonus:
        return engine._refuse(intent, f"{held.name} holds too well for {actor.name} to slip "
                                      f"by skill alone (DC {value}). Nothing is rolled.")
    roll = engine._roll_or_suspend(intent, actor, list(mods),
                                   label="Escape Artist check (bonds)", dc=value,
                                   partial=partial)
    if netted:
        _spend_action(engine, actor, "full-round")
    else:
        scene.advance(int(row("skill.escape-artist.bonds")["minutes"]))
    margin = roll.total - value
    if margin >= 0:
        actor.remove_effects(match=lambda e: e is held)
        return _done(intent, roll, value, basis, margin,
                     [{"ref": actor.ref, "kind": "escape", "from": held.key, "made": True}],
                     [f"{actor.name} works free of {held.name.lower()}{dc_mod.by(margin)}."])
    return _done(intent, roll, value, basis, margin,
                 [{"ref": actor.ref, "kind": "escape", "from": held.key, "made": False}],
                 [f"{actor.name} misses the Escape Artist check by {-margin}: "
                  f"{held.name.lower()} still holds."])


def squeeze(engine, intent, actor, mods, partial):
    """Through a tight space (CRB, Escape Artist: DC 30, at least a minute, a retry after
    a failure). Out of a fight only: a minute is ten rounds."""
    from . import dc as dc_mod

    r = row("skill.escape-artist.squeeze")
    if engine.scene.in_encounter:
        return engine._refuse(intent, "Squeezing through a tight space takes a minute or "
                                      "more, and there is a fight on. Nothing is rolled.")
    value = int(r["dc"])
    roll = engine._roll_or_suspend(intent, actor, list(mods),
                                   label="Escape Artist check (squeeze through)", dc=value,
                                   partial=partial)
    engine.scene.advance(int(r["minutes"]))
    margin = roll.total - value
    return _done(intent, roll, value, "a tight space: DC 30", margin,
                 [{"ref": actor.ref, "kind": "squeeze", "made": margin >= 0}],
                 [f"{actor.name} squeezes through{dc_mod.by(margin)}." if margin >= 0 else
                  f"{actor.name} misses the Escape Artist check by {-margin} and is stuck "
                  f"short of the way through; trying again is allowed."])


# --- Fly --------------------------------------------------------------------------------------

def _wings(actor) -> bool:
    """Flying on wings of its own (a stat block's or a people's fly speed), the book's
    condition for plummeting; a spell's or a potion's flight is not wings."""
    from . import bestiary, races

    doc = actor._creature_doc()
    if doc and bestiary.speeds(doc).get("fly"):
        return True
    race = actor._race_doc()
    return bool(race and races.speeds(race).get("fly"))


def _height(engine, actor, intent) -> int:
    spot = engine.scene.positions.get(actor.ref)
    if spot and len(spot) > 2 and engine.scene.grid is not None:
        return 5 * max(0, int(spot[2]) - int(engine.scene.grid.ground(tuple(spot[:2]))))
    return _feet(intent, "height_ft") or 0


def fly(engine, intent, actor, mods, partial):
    """A Fly check for a manoeuvre (CRB, Fly: slow 10, hover 15, turn 15, turn about 20,
    fly up steeply 20), or against the wind (checked: DC 20 to move at all; blown away:
    DC 25 or blown back 2d6 x 10 ft with 2d6 nonlethal), the wind's penalty on every one.
    Failed by 5 or more on wings, the flier plummets from its height (and may not catch
    the air with a Fly check: "falling due to a failed Fly check")."""
    from .activeeffect import ActiveEffect
    from .dice import Modifier
    from .tables import SIZE_ORDER
    from . import bestiary, dc as dc_mod

    use = str(intent.params.get("use") or "")
    r = row(use_id("fly", use))
    if not actor.movement_modes().get("fly"):
        return engine._refuse(intent, f"{actor.name} has no way to fly: no fly speed of "
                                      f"their own or from magic. Nothing is rolled.")
    winds = row("skill.fly.wind")["winds"]
    wind = str(intent.params.get("wind") or "light")
    force = winds.get(wind, winds["light"])
    mods = list(mods) + ([Modifier(int(force["penalty"]), f"{wind} wind")]
                         if force.get("penalty") else [])
    size = bestiary.body_size(actor) or str(actor.size or "medium")
    at = SIZE_ORDER.index(size) if size in SIZE_ORDER else 4
    def _small(limit):
        return bool(limit) and at <= SIZE_ORDER.index(limit)
    if use == "wind":
        if _small(force.get("blown_away")):
            value, kind = int(r["blown_dc"]), "blown"
        elif _small(force.get("checked")):
            value, kind = int(r["checked_dc"]), "checked"
        else:
            return _outcome(intent, tell=f"The {wind} wind is no trouble to {actor.name}'s "
                                         f"flight at their size.")
    else:
        value, kind = int(r["dc"]), use
    roll = engine._roll_or_suspend(intent, actor, mods, label=f"Fly check ({r['name']})",
                                   dc=value, partial=partial)
    margin = roll.total - value
    basis = f"{r['name']}: DC {value}" + (f", {wind} wind" if force.get("penalty") else "")
    if margin >= 0:
        return _done(intent, roll, value, basis, margin,
                     [{"ref": actor.ref, "kind": "fly", "use": use, "made": True}],
                     [f"{actor.name} {r['made']}{dc_mod.by(margin)}."])
    fx = [{"ref": actor.ref, "kind": "fly", "use": use, "made": False}]
    bits = [f"{actor.name} misses the Fly check ({r['name']}) by {-margin}."]
    extra = []
    if kind == "blown":
        back = engine.dice.roll("2d6", label="blown back (x10 ft)", visibility="hidden")
        hurt = engine.dice.roll("2d6", label="buffeted by the wind", visibility="hidden")
        extra += [back, hurt]
        hit = engine._apply_damage(actor, hurt.total, "bludgeoning", lethality="nonlethal")
        hit["origin"] = "rule:skill.fly.wind"
        fx.append(hit)
        bits.append(f"The wind throws {actor.name} back {back.total * 10} feet. "
                    + engine._damage_tell(hit))
    elif kind == "checked":
        actor.apply_effect(ActiveEffect(
            name="held by the wind", kind="situation", key="wind-checked",
            source="rule:skill.fly.wind", origin="rule:skill.fly.wind", duration="rounds",
            rounds_left=1, tags=(WIND_HELD,)))
        fx.append({"ref": actor.ref, "kind": "condition", "condition": "held by the wind",
                   "origin": "rule:skill.fly.wind"})
        bits.append(f"The {wind} wind holds {actor.name} where they are this round.")
    elif _wings(actor) and margin <= -5:
        down, more, said = fall(engine, actor, _height(engine, actor, intent), may_fly=False,
                                why="plummets")
        extra += down
        fx += more
        bits += said
    else:
        bits.append(f"{actor.name} {r['missed']}.")
    return _done(intent, roll, value, basis, margin, fx, bits, extra_rolls=extra)


# --- Ride -------------------------------------------------------------------------------------

def mount_of(scene, rider):
    """The creature this rider sits on, or None (also when it has fallen out from under
    them — a downed steed carries nobody)."""
    held = _held(rider, MOUNTED)
    steed = scene.actors.get(str((held.payload or {}).get("mount") or "")) if held else None
    return steed if steed is not None and not steed.is_down else None


def rider_of(scene, steed):
    held = _held(steed, RIDDEN)
    return scene.actors.get(str((held.payload or {}).get("by") or "")) if held else None


def _unseat(rider, steed) -> None:
    rider.remove_effects(match=lambda e: MOUNTED in (e.tags or ()))
    if steed is not None:
        steed.remove_effects(match=lambda e: RIDDEN in (e.tags or ()))


def _rideable(rider, steed) -> str:
    """Why this creature cannot carry this rider, or "": a mount is a creature at least one
    size larger (CRB, Mounted Combat: a Medium rider on a Large horse, a Small one on a
    pony or a riding dog), awake, nobody's player and nobody's foe."""
    from .tables import SIZE_ORDER
    from . import bestiary

    if steed is None or steed is rider or steed.is_pc:
        return "There is no mount here to get on."
    if steed.is_down:
        return f"{steed.name} is down and carries nobody."
    if _held(steed, RIDDEN) is not None:
        return f"{steed.name} already has a rider."
    big = bestiary.body_size(steed) or str(steed.size or "medium")
    small = bestiary.body_size(rider) or str(rider.size or "medium")
    if big not in SIZE_ORDER or small not in SIZE_ORDER \
            or SIZE_ORDER.index(big) <= SIZE_ORDER.index(small):
        return f"{steed.name} is too small to carry {rider.name}."
    return ""


def _steed_here(engine, intent, rider):
    from . import journey

    chosen = _target(engine, intent)
    if chosen is not None:
        return chosen
    here = [a for a in engine.scene.actors.values()
            if a is not rider and not a.is_pc and not a.is_down
            and str(getattr(a, "from_template", "") or "") in journey.MOUNTS
            and _held(a, RIDDEN) is None]
    return here[0] if len(here) == 1 else None


def _fast(engine, rider, mods, what: str):
    """In a fight: a DC 20 Ride check to make it a free action, if a move action is still
    there to fall back on ("On failure, mounting or dismounting is a move action")."""
    scene = engine.scene
    if not scene.in_encounter:
        return None, "", ""
    spent = _no_action_left(engine, rider, "move", what)
    if spent:
        return None, "", spent + " Nothing is done."
    r = row("skill.ride.mount")
    roll = _roll(engine, rider, mods, f"Ride check (fast {what})")
    if roll.total >= int(r["fast_dc"]):
        return roll, " in one easy movement, a free action", ""
    _spend_action(engine, rider, "move")
    return roll, f", a move action (the fast {what} missed: Ride {roll.total} against DC " \
                 f"{r['fast_dc']})", ""


def mount(engine, intent, actor, mods, partial):
    """Getting on a mount (CRB, Ride: a move action; the fast mount DC 20 a free action).
    The rider's square is the steed's from here (`carry_rider`), and the two hold each
    other: `state.position.mounted` on the rider, `state.position.ridden` on the steed."""
    from .activeeffect import ActiveEffect

    scene = engine.scene
    if mount_of(scene, actor) is not None:
        return engine._refuse(intent, f"{actor.name} is already mounted.")
    _unseat(actor, None)                      # a saddle left when the steed went down
    steed = _steed_here(engine, intent, actor)
    why = _rideable(actor, steed)
    if why:
        return engine._refuse(intent, why + " Nothing is done.")
    gap = engine._gap_ft(actor, steed)
    # Out of a fight the rider walks over to it first; in one the walk is a move of its own.
    if gap is not None and gap > 5 and scene.in_encounter:
        return engine._refuse(intent, f"{steed.name} is {int(gap)} feet away: get beside it "
                                      f"first. Nothing is done.")
    roll, how, refused = _fast(engine, actor, mods, "mount")
    if refused:
        return engine._refuse(intent, refused, code="action_spent")
    actor.apply_effect(ActiveEffect(
        name=f"riding {steed.name}", kind="situation", key="mounted", source=RIDE_SOURCE,
        origin=RIDE_SOURCE, tags=(MOUNTED,), payload={"mount": steed.ref}))
    steed.apply_effect(ActiveEffect(
        name=f"ridden by {actor.name}", kind="situation", key="ridden", source=RIDE_SOURCE,
        origin=RIDE_SOURCE, tags=(RIDDEN,), payload={"by": actor.ref}))
    carry_rider(scene, steed.ref)
    return _outcome(intent, rolls=[roll] if roll else [],
                    effects=[{"ref": actor.ref, "kind": "condition", "condition": "mounted",
                              "mount": steed.ref, "origin": RIDE_SOURCE}],
                    tell=f"{actor.name} mounts {steed.name}{how}.")


def dismount(engine, intent, actor, mods, partial):
    scene = engine.scene
    steed = mount_of(scene, actor)
    if steed is None:
        _unseat(actor, None)
        return engine._refuse(intent, f"{actor.name} is not mounted.")
    roll, how, refused = _fast(engine, actor, mods, "dismount")
    if refused:
        return engine._refuse(intent, refused, code="action_spent")
    _unseat(actor, steed)
    _step_off(scene, actor, steed)
    return _outcome(intent, rolls=[roll] if roll else [],
                    effects=[{"ref": actor.ref, "kind": "dismount", "mount": steed.ref,
                              "origin": RIDE_SOURCE}],
                    tell=f"{actor.name} gets down from {steed.name}{how}.")


def _step_off(scene, rider, steed) -> None:
    spot = scene.positions.get(steed.ref)
    if scene.grid is None or not spot:
        return
    free = scene._free_spot_at(spot[0], spot[1], 1, scene.occupied(ignore=rider.ref),
                               str(rider.size or "medium"))
    if free is not None:
        scene.positions[rider.ref] = free
        scene.settle_levels()
        scene.resync_zones()


def carry_rider(scene, steed_ref: str) -> None:
    """The rider sits where the steed stands: "you move at its speed" (CRB, Mounted
    Combat). Called wherever the steed's square is written (`Engine._op_move`)."""
    steed = scene.actors.get(steed_ref)
    rider = rider_of(scene, steed) if steed is not None else None
    spot = scene.positions.get(steed_ref)
    if rider is None or not spot or rider.ref not in scene.positions:
        return
    scene.positions[rider.ref] = tuple(spot)


def rides_with(scene, a_ref: str, b_ref: str) -> bool:
    """Whether the two are a rider and the steed under them (they share a square)."""
    a, b = scene.actors.get(a_ref), scene.actors.get(b_ref)
    return a is not None and b is not None and (
        mount_of(scene, a) is b or mount_of(scene, b) is a)


def ridden_move(engine, intent, partial):
    """A mounted rider's move is the steed's: the steed walks (its speed, its route, its
    move action) and carries the rider. None when this move is not a rider's."""
    from .intents import Intent

    params = intent.params or {}
    ref = params.get("who") or intent.actor
    rider = engine.scene.actors.get(ref or "")
    steed = mount_of(engine.scene, rider) if rider is not None else None
    if steed is None or not params.get("square"):
        return None
    out = engine._op_move(Intent(op="move", actor=intent.actor, id=intent.id,
                                 because=intent.because,
                                 params=dict(params, who=steed.ref)), partial)
    if out.status == "resolved":
        carry_rider(engine.scene, steed.ref)
        out.tell = f"{rider.name} rides {steed.name}: {out.tell}"
    return out


def _thrown(engine, rider, steed, why: str):
    """Off the saddle, the soft fall (CRB, Ride: DC 15, no damage; else 1d6 and prone)."""
    r = row("skill.ride.soft-fall")
    _unseat(rider, steed)
    _step_off(engine.scene, rider, steed)
    mods = _skill_mods(rider, "ride")
    roll = _trick_ridden(engine, rider, mods, int(r["dc"]), "Ride check (soft fall)") \
        or _roll(engine, rider, mods, "Ride check (soft fall)")
    if roll.total >= int(r["dc"]):
        return [roll], [{"ref": rider.ref, "kind": "dismount", "fell": True}], [
            f"{rider.name} {why} and lands on their feet (Ride {roll.total} against DC "
            f"{r['dc']})."]
    hurt = engine.dice.roll(str(r["damage"]), label="thrown from the saddle",
                            visibility="hidden")
    hit = engine._apply_damage(rider, hurt.total, "bludgeoning")
    hit["origin"] = "rule:skill.ride.soft-fall"
    fx = [{"ref": rider.ref, "kind": "dismount", "fell": True}, hit,
          *engine._hp_state_effects(rider)]
    if not rider.is_down:
        _prone(rider, "thrown from the saddle",
                            origin="rule:skill.ride.soft-fall")
    return [roll, hurt], fx, [f"{rider.name} {why} and hits the ground (Ride {roll.total} "
                              f"against DC {r['dc']}). " + engine._damage_tell(hit)
                              + (f" {rider.name} is prone." if not rider.is_down else "")]


def _riding(engine, intent, actor, what: str):
    steed = mount_of(engine.scene, actor)
    if steed is None:
        _unseat(actor, None)
        return None, engine._refuse(intent, f"{actor.name} is not mounted: {what} is done "
                                            f"from the saddle. Nothing is rolled.")
    return steed, None


def spur(engine, intent, actor, mods, partial):
    """Spur the mount (CRB, Ride: DC 15, a move action; +10 feet of speed for a round, and
    the mount takes 1d3 damage; "A fatigued mount can't be spurred")."""
    from .activeeffect import ActiveEffect
    from . import dc as dc_mod

    r = row("skill.ride.spur")
    steed, refused = _riding(engine, intent, actor, "spurring")
    if refused:
        return refused
    if steed.has_state("state.impaired"):
        return engine._refuse(intent, f"{steed.name} is spent; a tired mount cannot be "
                                      f"spurred. Nothing is rolled.")
    spent = _no_action_left(engine, actor, "move", "spurring the mount")
    if spent:
        return engine._refuse(intent, spent + " Nothing is rolled.", code="action_spent")
    value = int(r["dc"])
    roll = _trick_ridden(engine, actor, mods, value, "Ride check (spur)") \
        or engine._roll_or_suspend(intent, actor, list(mods), label="Ride check (spur)",
                                   dc=value, partial=partial)
    _spend_action(engine, actor, "move")
    margin = roll.total - value
    if margin < 0:
        return _done(intent, roll, value, "spur: DC 15", margin, [],
                     [f"{actor.name} spurs {steed.name} and gets nothing more out of it "
                      f"(missed by {-margin})."])
    steed.apply_effect(ActiveEffect(
        name="spurred", kind="buff", key="spurred", source="rule:skill.ride.spur",
        origin="rule:skill.ride.spur", duration="rounds", rounds_left=2,
        modifiers=[{"kind": "speed", "target": "land", "amount": int(r["speed_ft"]),
                    "bonus_type": "untyped"}]))
    cut = engine.dice.roll(str(r["damage"]), label="the spurs", visibility="hidden")
    hit = engine._apply_damage(steed, cut.total, "piercing")
    hit["origin"] = "rule:skill.ride.spur"
    return _done(intent, roll, value, "spur: DC 15", margin,
                 [{"ref": steed.ref, "kind": "buff", "speed": int(r["speed_ft"]),
                   "origin": "rule:skill.ride.spur"}, hit, *engine._hp_state_effects(steed)],
                 [f"{actor.name} spurs {steed.name}{dc_mod.by(margin)}: +{r['speed_ft']} feet "
                  f"of speed this round. " + engine._damage_tell(hit)], extra_rolls=[cut])


def cover(engine, intent, actor, mods, partial):
    """Use the mount as cover (CRB, Ride: DC 15, an immediate action; "You can't attack or
    cast spells while using your mount as cover"): +4 AC until the rider's next turn,
    attacking and casting stopped by the tag (`states.BLOCKS`)."""
    from .activeeffect import ActiveEffect
    from . import dc as dc_mod

    r = row("skill.ride.cover")
    steed, refused = _riding(engine, intent, actor, "dropping behind the mount")
    if refused:
        return refused
    value = int(r["dc"])
    roll = _trick_ridden(engine, actor, mods, value, "Ride check (cover)") \
        or engine._roll_or_suspend(intent, actor, list(mods), label="Ride check (cover)",
                                   dc=value, partial=partial)
    margin = roll.total - value
    if margin < 0:
        return _done(intent, roll, value, "cover: DC 15", margin, [],
                     [f"{actor.name} tries to drop down behind {steed.name} and misses the "
                      f"Ride check by {-margin}: no cover."])
    actor.apply_effect(ActiveEffect(
        name=f"behind {steed.name}", kind="situation", key="mount-cover",
        source="rule:skill.ride.cover", origin="rule:skill.ride.cover", duration="rounds",
        rounds_left=2, tags=(MOUNT_COVER,),
        modifiers=[{"kind": "combat_mod", "target": "ac", "amount": int(r["ac"]),
                    "bonus_type": "cover"}]))
    return _done(intent, roll, value, "cover: DC 15", margin,
                 [{"ref": actor.ref, "kind": "condition", "condition": "mount cover",
                   "origin": "rule:skill.ride.cover"}],
                 [f"{actor.name} drops down along {steed.name}'s flank{dc_mod.by(margin)}: "
                  f"+{r['ac']} AC from the mount's cover until their next turn, and no "
                  f"attacking or casting while there."])


def leap(engine, intent, actor, mods, partial):
    """Leap on the mount (CRB, Ride: DC 15 to stay on, failing it "you fall off"; the
    jump is the mount's Acrobatics or the rider's Ride, whichever is lower)."""
    from . import dc as dc_mod

    r = row("skill.ride.leap")
    steed, refused = _riding(engine, intent, actor, "a leap")
    if refused:
        return refused
    feet = _feet(intent, "distance_ft")
    if not feet:
        return engine._refuse(intent, "A leap is made to a distance: give distance_ft. "
                                      "Nothing is rolled.")
    value = int(r["dc"])
    roll = _trick_ridden(engine, actor, mods, value, "Ride check (leap)") \
        or engine._roll_or_suspend(intent, actor, list(mods), label="Ride check (leap)",
                                   dc=value, partial=partial)
    margin = roll.total - value
    if margin < 0:
        rolls, fx, said = _thrown(engine, actor, steed, f"is thrown as {steed.name} leaps")
        return _done(intent, roll, value, "leap: DC 15", margin, fx,
                     [f"{actor.name} misses the Ride check by {-margin}."] + said,
                     extra_rolls=rolls)
    own = _skill_mods(steed, "acrobatics")
    jumper = min((own, list(mods)), key=lambda ms: sum(m.value for m in ms))
    jdc = int(feet) * int(row("skill.acrobatics.jump")["per_foot"])
    jroll = _roll(engine, steed, [*jumper, *_jump_term(steed)],
                  f"{steed.name} Acrobatics (leap)")
    bits = [f"{actor.name} stays on{dc_mod.by(margin)} as {steed.name} leaps."]
    if jroll.total >= jdc:
        bits.append(f"{steed.name} clears {feet} feet (Acrobatics {jroll.total} against DC "
                    f"{jdc}).")
        return _done(intent, roll, value, "leap: DC 15", margin,
                     [{"ref": steed.ref, "kind": "jump", "feet": feet, "made": True}], bits,
                     extra_rolls=[jroll])
    rolls, fx, said = _thrown(engine, actor, steed, f"comes off as {steed.name} falls short")
    _prone(steed, "a failed leap", origin="rule:skill.ride.leap")
    bits.append(f"{steed.name} falls short of {feet} feet (Acrobatics {jroll.total} against "
                f"DC {jdc}) and goes down.")
    return _done(intent, roll, value, "leap: DC 15", margin,
                 [{"ref": steed.ref, "kind": "jump", "feet": feet, "made": False}, *fx],
                 bits + said, extra_rolls=[jroll, *rolls])


def mounted_combat(engine, attacker, defender, atk, state) -> str:
    """Mounted Combat (CRB feat): "Once per round when your mount is hit in combat, you may
    attempt a Ride check (as an immediate action) to negate the hit. The hit is negated if
    your Ride check is greater than the opponent's attack roll." The round's one use is an
    `item_spent` effect the round ticker expires, as arrow deflection's is. The tell when
    the hit was negated, else ""."""
    from .activeeffect import ActiveEffect

    rider = rider_of(engine.scene, defender)
    if rider is None or rider.is_down or not rider.has_state(MOUNTED_COMBAT) \
            or mount_of(engine.scene, rider) is not defender:
        return ""
    # Trick Riding (CRB): "You can make a check using Mounted Combat to negate a hit on
    # your mount twice per round instead of just once" — one spent-marker per use.
    allowed = 2 if rider.has_state(TRICK_RIDING) else 1
    if sum(1 for e in rider.effects
           if e.kind == "item_spent" and str(e.key).startswith("mounted-combat")) >= allowed:
        return ""
    rider.apply_effect(ActiveEffect(
        name="Mounted Combat used this round", kind="item_spent",
        key="mounted-combat" + ("-2" if any(e.kind == "item_spent" and e.key == "mounted-combat"
                                            for e in rider.effects) else ""),
        source="feat:mounted-combat", origin="feat:mounted-combat", duration="rounds",
        rounds_left=1))
    # Feat loop b4-maneuver: Mounted Shield's shield bonus on this Ride check too.
    from . import maneuver_feats

    roll = _roll(engine, rider, _skill_mods(rider, "ride") + maneuver_feats.shield_on_ride(rider),
                 "Ride check (Mounted Combat)")
    state["rolls"].append(roll.as_dict())
    if roll.total > atk.total:
        return (f"{rider.name} turns {defender.name} from the blow (Mounted Combat: Ride "
                f"{roll.total} against the attack's {atk.total}).")
    state["tells"].append(f"{rider.name} cannot turn {defender.name} from the blow (Ride "
                          f"{roll.total} against the attack's {atk.total}).")
    return ""


def control_in_battle(engine, intent, rider):
    """CRB, Ride: "Control Mount in Battle: As a move action, you can attempt to control a
    light horse, pony, heavy horse, or other mount not trained for combat riding while in
    battle. If you fail the Ride check, you can do nothing else in that round. You do not
    need to roll for horses or ponies trained for combat." DC 20.

    Asked by the attack and the cast of a mounted rider in a fight, once a round: the
    round's answer is an `item_spent` effect the round ticker expires, as Mounted
    Combat's is. None when the rider may act (trained mount, made this round, or not
    mounted); else the refusal, its roll on it. A made control is said beside the blow.
    Combat training is the animal's own (`animals.combat_trained`: the purpose, or every
    one of its tricks) — before round 3 nothing recorded it and a bought warhorse lost the
    "(combat-trained)" off its name and nothing else."""
    from .activeeffect import ActiveEffect
    from . import animals
    from .engine import Outcome

    scene = engine.scene
    steed = mount_of(scene, rider) if scene.in_encounter else None
    if steed is None or animals.combat_trained(steed):
        return None
    held = next((e for e in rider.effects if e.kind == "item_spent"
                 and e.key == "mount-control"), None)
    if held is not None:
        if (held.payload or {}).get("made"):
            return None
        return engine._refuse(intent, f"{rider.name} has lost control of {steed.name} this "
                                      f"round and can do nothing else.", code="action_spent")
    r = row("skill.ride.control")
    spent = _no_action_left(engine, rider, "move", "controlling the mount")
    if spent:
        return engine._refuse(intent, f"{steed.name} is not trained for combat: "
                                      f"{rider.name} must spend a move action to control it "
                                      f"before attacking or casting. {spent}",
                              code="action_spent")
    roll = _roll(engine, rider, _skill_mods(rider, "ride"),
                 "Ride check (control the mount in battle)")
    made = roll.total >= int(r["dc"])
    rider.apply_effect(ActiveEffect(
        name="the mount in hand this round" if made else "the mount out of hand this round",
        kind="item_spent", key="mount-control", source="rule:skill.ride.control",
        origin="rule:skill.ride.control", duration="rounds", rounds_left=1,
        payload={"made": made}))
    _spend_action(engine, rider, "move" if made else "full-round")
    said = (f"{steed.name} is not trained for combat: {rider.name} "
            + (f"keeps it in hand (Ride {roll.total} against DC {r['dc']}), a move action."
               if made else
               f"cannot control it (Ride {roll.total} against DC {r['dc']}) and can do "
               f"nothing else this round."))
    fx = [{"ref": rider.ref, "kind": "mount_control", "mount": steed.ref, "made": made,
           "origin": "rule:skill.ride.control"}]
    if made:
        engine._side_outcomes.append(Outcome(
            intent_id=intent.id, op="check", rolls=[roll], effects=fx, tell=said,
            dc={"value": int(r["dc"]), "basis": "control a mount in battle"},
            verdict="success", margin=roll.total - int(r["dc"])))
        return None
    return Outcome(intent_id=intent.id, op=intent.op, status="prevented", rolls=[roll],
                   effects=fx, tell=said, verdict="failure",
                   margin=roll.total - int(r["dc"]), because=intent.because)


def _handled(engine, intent, actor, mods, partial):
    """Handle Animal's uses, should a caller reach them through `DOORS` (the check door
    `animals.social_door` takes them first)."""
    from . import animals

    return animals.check(engine, intent, actor, partial)


# --- Heal: treat poison and disease -----------------------------------------------------------

def _patient(engine, intent, actor):
    named = [r for r in intent.targets() if r and r in engine.scene.actors]
    return engine.scene.actors[named[0]] if named else actor


def _affliction(patient, key: str):
    return next((e for e in patient.effects if e.kind == "affliction" and e.key == key), None)


def _treat(engine, intent, actor, mods, partial, *, key: str):
    """Treat poison or disease (CRB, Heal): the affliction's own save DC; if the Heal check
    exceeds it, "+4 competence bonus on his saving throw against the poison" — laid as a
    `care.treated.<kind>` effect carrying the save term (asked `against` the affliction's
    kind, the context `Actor._afflicted` rolls in) and spent by that save. Treat poison is
    a standard action; treat disease takes 10 minutes, out of a fight."""
    from .activeeffect import ActiveEffect

    kind = "poison" if key == "poisoned" else "disease"
    r = row(use_id("heal", f"treat-{kind}"))
    patient = _patient(engine, intent, actor)
    aff = _affliction(patient, key)
    if aff is None:
        return engine._refuse(intent, f"{patient.name} carries no {kind} to treat. Nothing "
                                      f"is rolled.")
    scene = engine.scene
    if kind == "disease" and scene.in_encounter:
        return engine._refuse(intent, "Treating a disease takes ten minutes, and there is a "
                                      "fight on. Nothing is rolled.")
    if kind == "poison":
        spent = _no_action_left(engine, actor, "standard", "treating poison")
        if spent:
            return engine._refuse(intent, spent + " Nothing is rolled.", code="action_spent")
    # Feat loop b4-maneuver: Siphon Poison draws a fresh injury poison out instead.
    from . import maneuver_feats

    if kind == "poison":
        drawn = maneuver_feats.siphon_poison(engine, intent, actor, patient, aff, mods,
                                             partial)
        if drawn is not None:
            return drawn
    held = (aff.payload or {}).get("affliction") or {}
    value = int(held.get("dc") or 10)
    save = str(held.get("save") or "fort")
    from . import firstaid

    if kind == "poison" and firstaid.medic_takes_ten(actor, patient, mods, value, exceed=True):
        roll = engine.dice.given(10, list(mods), label="Heal check (treat poison, taking 10, "
                                                       "Combat Medic)")
    else:
        roll = engine._roll_or_suspend(intent, actor, list(mods), label=f"Heal check (treat "
                                       f"{kind})", dc=value, partial=partial)
    if kind == "disease":
        scene.advance(int(r["minutes"]))
    else:
        _spend_action(engine, actor, "standard")
    margin = roll.total - value
    basis = f"treat {kind}: the {aff.name}'s save DC {value}"
    whose = "their own" if patient is actor else f"{patient.name}'s"
    if margin <= 0:
        # "exceeds": a tie is not enough (owner call, docs/research/2026-11-22-skills-body.md).
        return _done(intent, roll, value, basis, margin - 1 if margin == 0 else margin,
                     [{"ref": patient.ref, "kind": "treat", "of": kind, "made": False}],
                     [f"{actor.name} tends {whose} {aff.name} and does not beat it (Heal "
                      f"{roll.total} against DC {value}): the next save against it has no "
                      f"help."])
    patient.apply_effect(ActiveEffect(
        name=f"{kind} treated by {actor.name}", kind="situation", key=f"treated-{kind}",
        source=f"rule:skill.heal.treat-{kind}", origin=f"rule:skill.heal.treat-{kind}",
        tags=(f"{TREATED}.{kind}",), payload={"by": actor.ref, "for": aff.payload.get("id")},
        modifiers=[{"kind": "save_mod", "target": save, "amount": int(r["bonus"]),
                    "bonus_type": "competence", "when": {"against": kind}}]))
    return _done(intent, roll, value, basis, margin,
                 [{"ref": patient.ref, "kind": "condition", "condition": f"{kind} treated",
                   "by": actor.ref, "origin": f"rule:skill.heal.treat-{kind}"}],
                 [f"{actor.name} treats {whose} {aff.name} (Heal {roll.total} against DC "
                  f"{value}): +{r['bonus']} on the next save against it."])


def treat_poison(engine, intent, actor, mods, partial):
    return _treat(engine, intent, actor, mods, partial, key="poisoned")


def treat_disease(engine, intent, actor, mods, partial):
    return _treat(engine, intent, actor, mods, partial, key="diseased")


def spend_treatment(patient, kind: str) -> None:
    """The treatment is for the one save it helped (`Actor._afflicted`, after the roll)."""
    tag = f"{TREATED}.{kind}"
    patient.remove_effects(match=lambda e: tag in (e.tags or ()))


DOORS = {
    "skill.acrobatics.jump": jump,
    "skill.acrobatics.high-jump": high_jump,
    "skill.acrobatics.soften-fall": soften_fall,
    "skill.acrobatics.balance": balance,
    "skill.climb.move": climb,
    "skill.escape-artist.bonds": bonds,
    "skill.escape-artist.squeeze": squeeze,
    **{use_id("fly", u): fly for u in USES["fly"]},
    "skill.ride.mount": mount,
    "skill.ride.dismount": dismount,
    "skill.ride.spur": spur,
    "skill.ride.cover": cover,
    "skill.ride.leap": leap,
    "skill.heal.treat-poison": treat_poison,
    "skill.heal.treat-disease": treat_disease,
    **{use_id("handle animal", u): _handled for u in USES["handle animal"]},
}
