"""The combat-manoeuvre feats of feat loop batch 4 (lane b4-maneuver, 2026-11-26).

Each feat is a document in content/feats/mechanics/b4-maneuver.json; the engine reads the
document's TAGS here and never a feat's name (tests/test_feat_documents.py). One reader per
shape, asked from three small hooks in `Engine._resolve_maneuver`:

* `twice` — "roll twice and take the better result" on a manoeuvre's check. Tandem Trip
  (UC): "Whenever you attempt a trip combat maneuver against an enemy threatened by an ally
  with this feat, you roll twice and take the better result" — the tag
  `maneuver.twice.<manoeuvre>.with-ally`, held by both. The roll itself is made at the d20
  door (`Engine._roll_or_suspend_stage`'s `twice`): the player rolls a second die, anybody
  else's is rolled by the engine.
* `formula_names` — `allies_flanking` and `streak`, the two names Topple Foe's formula asks
  (`sheet.FEAT_FORMULA_NAMES`): allies with the feat flanking the foe with you, and how many
  rounds in a row this manoeuvre has been tried at the same foe. The streak is a one-round
  situation effect on the maker (`streak-<feat id>`), laid by `after` and gone on the ticker
  when a round passes without a try, so it is the one effect store and no counter.
* `backfire_spared` — a trip that fails by 10 and would knock its maker prone. The trip
  weapon special feature (CRB, Weapon Qualities): "If you are tripped during your own trip
  attempt, you can drop the weapon to avoid being tripped"; Tripping Staff (UM): "You treat
  quarterstaves as if they had the trip special feature" (`weapon.trip-feature.<key>`).
  Until this the trip feature was a word in weapons.json nothing read.
* `after` — what a held feat makes of a manoeuvre just made: the follow-up manoeuvres
  (Binding Throw's swift grapple after a Ki Throw, Spinning Throw's swift bull rush after an
  unarmed trip), Break Guard's swift blow with the other weapon after a disarm, Tripping
  Twirl's trip at every other adjacent enemy, and the streak.

Prior art (searched 2026-11-26): Foundry PF1 leaves every one of these to the table — a
chat card and the GM's hand; Owlcat's Pathfinder CRPGs make the follow-ups automatic rule
hooks on the manoeuvre's success event (`RuleCombatManeuver` then a free manoeuvre), which
is this module's shape. A follow-up is made the way the engine already makes a feat's free
manoeuvre on a hit (`Engine._rider_feat_maneuver`, Shield Slam): an engine-built intent,
stamped `rule:feat-<id>`, rolled at once, its action spent through the one swift door
(`Engine._spend_swift`). Owner call (taking the rules as written): the swift follow-up is
taken whenever the swift action is free — the book says "can", and the best the roll allows
is the choice made for the player, as the crit-strike feats' already is.
"""
from __future__ import annotations

TWICE = "maneuver.twice"
TRIP_FEATURE = "weapon.trip-feature"
# After a trip that Ki Throw made (an unarmed trip by its holder), a swift grapple:
# Binding Throw. After an unarmed trip, a swift bull rush that ends prone: Spinning Throw.
AFTER_TRIP_GRAPPLE = "maneuver.after-trip.grapple"
AFTER_TRIP_BULL_RUSH = "maneuver.after-trip.bull-rush"
# After a disarm made with one of two weapons, a swift blow with the other: Break Guard.
AFTER_DISARM_STRIKE = "maneuver.after-disarm.strike"
STREAK = "streak-"
# An engine-written blow with the weapon a two-weapon swing declared in the off hand
# (Break Guard's "using your other weapon"): it is in hand by that declaration, so the
# attack does not ask for it to be drawn. Never a param the model may write (parse refuses
# an unknown one).
OFF_HAND_SWING = "off_hand_swing"


def _slug(text: str) -> str:
    return "-".join(str(text or "").strip().lower().split())


def _docs(actor):
    """(document) for every feat this creature holds that has one, once each."""
    from . import feats as feats_mod

    seen: set = set()
    for raw in getattr(actor, "feats", None) or ():
        doc = feats_mod.document(raw)
        if doc and doc["id"] not in seen:
            seen.add(doc["id"])
            yield doc


def _named_by_tag(actor, tag: str) -> str:
    """The display name of the held feat whose document carries `tag`."""
    for doc in _docs(actor):
        if tag in (doc.get("tags") or ()):
            return str(doc["name"])
    return ""


def _scene():
    from .sheet import current_moment

    return getattr(current_moment(), "scene", None)


# --- roll twice ------------------------------------------------------------------------

def twice(engine, actor, defender, key: str) -> str:
    """The feat that has this manoeuvre's check rolled twice, the better kept — or "".

    Tandem Trip: an ally on the same side who also holds the tag threatens the foe
    (`reactions.threatens`, the attack of opportunity's own rule). No board, no threat."""
    from . import position, reactions

    tag = f"{TWICE}.{_slug(key)}.with-ally"
    if defender is None or not actor.has_state(tag):
        return ""
    scene = engine.scene
    square = scene.positions.get(defender.ref) if scene.has_grid else None
    if square is None:
        return ""
    for ref, other in scene.actors.items():
        if ref in (actor.ref, defender.ref) or other.is_down or not other.has_state(tag):
            continue
        if position._same_side(scene, actor.ref, ref) and reactions.threatens(
                scene, ref, square, getattr(defender, "size", "medium")):
            return _named_by_tag(actor, tag) or key
    return ""


# --- Topple Foe's two names --------------------------------------------------------------

def formula_names(actor, fid: str, foe) -> dict:
    """`allies_flanking` and `streak` for a formula of feat `fid` against `foe`.

    `allies_flanking`: allies holding the feat who flank `foe` with this creature on the
    board (`position.flanking_allies`, the +2's own geometry). `streak`: the rounds before
    this one, in an unbroken run, in which this creature tried the formula's manoeuvre at
    `foe` — 0 on the first round, 3 on the fourth (Topple Foe's "Each time you attempt to
    trip the same foe in consecutive rounds, the bonus ... increases by +1 per ally")."""
    from . import feats as feats_mod
    from . import position

    out = {"allies_flanking": 0, "streak": 0}
    scene = _scene()
    if foe is None or scene is None:
        return out
    if getattr(scene, "has_grid", False):
        out["allies_flanking"] = sum(
            1 for a in position.flanking_allies(scene, actor, foe)
            if fid in feats_mod._held(a))
    out["streak"] = streak(actor, fid, foe, getattr(scene, "round", 0))
    return out


def _streak_effect(actor, fid: str):
    return next((e for e in actor.effects if e.key == STREAK + fid), None)


def streak(actor, fid: str, foe, rnd: int) -> int:
    e = _streak_effect(actor, fid)
    p = (e.payload or {}) if e is not None else {}
    if e is None or p.get("vs") != getattr(foe, "ref", None):
        return 0
    if int(p.get("round", -9)) == rnd:
        return int(p.get("count", 0))
    if int(p.get("round", -9)) == rnd - 1:
        return int(p.get("count", 0)) + 1
    return 0


def _keep_streak(engine, actor, defender, key: str) -> None:
    """Record this try at `defender` for every held document whose formula counts a
    streak of this manoeuvre — one situation effect each, two rounds on the ticker (it
    has to outlast the round boundary to be read on the next turn)."""
    from .activeeffect import ActiveEffect

    if not engine.scene.in_encounter:
        return
    rnd = engine.scene.round
    for doc in _docs(actor):
        if not any("streak" in str(m.get("formula") or "")
                   and (m.get("scope") or {}).get("maneuver") == key
                   for m in doc.get("modifiers") or ()):
            continue
        n = streak(actor, doc["id"], defender, rnd)
        actor.remove_effects(match=lambda e, k=STREAK + doc["id"]: e.key == k)
        actor.apply_effect(ActiveEffect(
            name=f"{doc['name']}: {key} at {defender.name}", kind="situation",
            key=STREAK + doc["id"], source=doc["name"], origin=f"rule:feat-{doc['id']}",
            duration="rounds", rounds_left=2,
            payload={"vs": defender.ref, "round": rnd, "count": n}))


# --- the trip weapon feature ------------------------------------------------------------

def trip_feature(actor, weapon_key: str) -> bool:
    """Whether the weapon in hand has the trip special feature, by the weapon table or by
    a held tag lending it (Tripping Staff: `weapon.trip-feature.quarterstaff`)."""
    from . import weapons as weapons_mod

    key = str(weapon_key or "").strip().lower()
    if not key or key in ("unarmed", "improvised"):
        return False
    base = str((actor.weapon(key) or {}).get("crafted_base") or key)
    return weapons_mod.has_trait(base, "trip") or actor.has_state(
        f"{TRIP_FEATURE}.{_slug(base)}")


def backfire_spared(engine, intent, actor, defender, key: str, weapon_key: str,
                    bits: list, effects: list) -> bool:
    """A failed trip that would knock its maker prone: with a trip weapon in hand the
    weapon is let go instead (it lies here, still theirs — `Engine._let_go`). Owner call:
    the drop is always taken, because standing from prone costs a move action and provokes
    while picking a weapon up costs only the move. True when it handled the backfire."""
    if key != "trip" or not trip_feature(actor, weapon_key) \
            or not engine._drops_in_hand(actor, weapon_key):
        return False
    rec = engine._let_go(actor, weapon_key)
    name = str((actor.weapon(weapon_key) or {}).get("name") or weapon_key)
    bits.append(f"{actor.name} lets go of the {weapon_key} rather than be pulled down "
                f"(a trip weapon): it lies on the ground.")
    effects.append({"ref": actor.ref, "kind": "dropped", "item": weapon_key,
                    "prop": rec["name"], "from": f"failed trip with a trip weapon ({name})",
                    "origin": "rule:trip-weapon"})
    return True


# --- follow-ups --------------------------------------------------------------------------

def _sub(engine, intent, actor, defender, key: str, tag: str, word: str, params=None):
    """An engine-built manoeuvre at `defender` (the free-manoeuvre door's shape), resolved
    at once and rolled by the engine. Never through `validate`: the feat's own action is
    what it costs, and no attack of opportunity is owed by a manoeuvre the feat makes
    (each of these feats requires the Improved <manoeuvre> feat that removes the swing)."""
    from .engine import Intent

    doc_id = next((d["id"] for d in _docs(actor) if tag in (d.get("tags") or ())), _slug(word))
    sub = Intent(op="attack", actor=actor.ref, target=defender.ref,
                 because=f"{actor.name}'s {word}", visibility="hidden",
                 id=f"{intent.id}.{_slug(word)}",
                 params={"manoeuvre": key, "rider": word, **(params or {})},
                 origin=f"rule:feat-{doc_id}", origin_name=word)
    return engine._resolve_maneuver(sub, actor, defender, actor.wielded_key()
                                    if key != "grapple" else "unarmed", {})


def _swift(engine, actor, what: str) -> str:
    """Spend the swift action, or say why it cannot be."""
    return engine._spend_swift(actor, False, what) or ""


def after(engine, intent, actor, defender, key: str, verdict: str, weapon_key: str,
          rolled: bool) -> dict:
    """Effects, tells and rolls a held feat adds to the manoeuvre just made."""
    out = {"effects": [], "tells": [], "rolls": []}
    if intent.params.get("rider") or actor is None or defender is None:
        return out                          # a follow-up begets no follow-up
    if rolled:
        _keep_streak(engine, actor, defender, key)
    won = verdict == "success"

    def take(got, tag):
        out["rolls"].extend(got.rolls)
        out["effects"].extend(dict(e, origin=e.get("origin") or got_origin(tag))
                              for e in got.effects)
        out["tells"].append(got.tell)

    def got_origin(tag):
        doc = next((d for d in _docs(actor) if tag in (d.get("tags") or ())), None)
        return f"rule:feat-{doc['id']}" if doc else "rule:maneuver-feat"

    unarmed = str(weapon_key or "").strip().lower() in ("unarmed", "unarmed strike")
    if key == "trip" and won and unarmed and not defender.is_down:
        # Binding Throw (UC): "After you successfully use the Ki Throw feat on an opponent,
        # you can use a swift action to attempt a grapple combat maneuver against that
        # opponent." Ki Throw is an unarmed trip (APG); its holder's trip is its use.
        from . import feats as feats_mod

        if actor.has_state(AFTER_TRIP_GRAPPLE) and "ki-throw" in feats_mod._held(actor) \
                and not engine._holds(actor, defender):
            name = _named_by_tag(actor, AFTER_TRIP_GRAPPLE)
            why = _swift(engine, actor, name)
            if why:
                out["tells"].append(f"{name}: {why}")
            else:
                take(_sub(engine, intent, actor, defender, "grapple", AFTER_TRIP_GRAPPLE,
                          name), AFTER_TRIP_GRAPPLE)
        # Spinning Throw (UC): "On a successful unarmed trip combat maneuver against an
        # opponent your size or smaller, you can spend a swift action to attempt a bull
        # rush ... If your bull rush succeeds, you can move that opponent to any
        # unoccupied square you threaten, then push that opponent the number of 5-foot
        # increments your successful bull rush allows. The target is then knocked prone."
        # Owner call: the move to another threatened square is the player's to offer and
        # is not taken (the book's "can"); the push is the bull rush's own line.
        elif actor.has_state(AFTER_TRIP_BULL_RUSH) and _size_steps(actor, defender) <= 0:
            name = _named_by_tag(actor, AFTER_TRIP_BULL_RUSH)
            why = _swift(engine, actor, name)
            if why:
                out["tells"].append(f"{name}: {why}")
            else:
                got = _sub(engine, intent, actor, defender, "bull rush",
                           AFTER_TRIP_BULL_RUSH, name)
                take(got, AFTER_TRIP_BULL_RUSH)
                if got.verdict == "success" and not defender.is_down \
                        and not defender.has_state("state.position.prone"):
                    from . import bodyskills

                    bodyskills._prone(defender, f"{actor.name}'s {name}",
                                      got_origin(AFTER_TRIP_BULL_RUSH))
                    out["effects"].append({"ref": defender.ref, "kind": "condition",
                                           "condition": "prone",
                                           "origin": got_origin(AFTER_TRIP_BULL_RUSH)})
                    out["tells"].append(f"{defender.name} is thrown down again.")
    if key == "disarm" and won:
        # Break Guard (UC): "While wielding two weapons, whenever you successfully use one
        # weapon to disarm an opponent, you can spend a swift action to attack the
        # opponent you attempted to disarm using your other weapon." The other weapon is
        # the off hand the swing declared (`off_hand`, a two-weapon full attack's).
        off = str(intent.params.get("off_hand") or "").strip().lower()
        if actor.has_state(AFTER_DISARM_STRIKE) and off and off != weapon_key:
            name = _named_by_tag(actor, AFTER_DISARM_STRIKE)
            why = _swift(engine, actor, name)
            if why:
                out["tells"].append(f"{name}: {why}")
            else:
                out["effects"].append({
                    "ref": actor.ref, "kind": "owed_swing", "target": defender.ref,
                    "origin": got_origin(AFTER_DISARM_STRIKE),
                    "attack": {"op": "attack", "actor": actor.ref, "target": defender.ref,
                               "because": f"{actor.name}'s {name}",
                               "visibility": "player" if actor.is_pc else "hidden",
                               "params": {"weapon": off, "full_attack": False,
                                          "reaction": "swift", OFF_HAND_SWING: True}}})
                out["tells"].append(f"{name}: the {off} follows through the opening.")
    for e in trample(engine, actor, defender, key, won):
        out["effects"].append(e)
        out["tells"].append(f"{engine.scene.actors[e['ref']].name} tramples "
                            f"{defender.name} where they fell (Trample).")
    if key == "trip" and won and intent.params.get(FURYS_SNARE):
        for k in out:
            out[k].extend(furys_snare(engine, actor, defender, weapon_key)[k])
    if key == "trip" and intent.params.get("tripping_twirl"):
        out_twirl = _twirl(engine, intent, actor, defender)
        for k in out:
            out[k].extend(out_twirl[k])
    return out


def _size_steps(actor, other) -> int:
    from . import classfeatures

    return classfeatures.size_steps(actor, other)


# Tripping Twirl's declared option (sheet.ATTACK_CHOICES, the feat document's `choice`).
TWIRL = "tripping_twirl"


def _twirl(engine, intent, actor, first) -> dict:
    """Tripping Twirl (UM): "As a full-round action, while wielding a quarterstaff
    two-handed, you can attempt a trip combat maneuver against each enemy adjacent to
    you." The declared trip is the first; one more at each other foe adjacent on the board,
    each its own roll. No board, nobody can be shown to stand adjacent."""
    from . import grid as gridmod
    from . import skilluses

    out = {"effects": [], "tells": [], "rolls": []}
    scene = engine.scene
    skilluses._spend_action(engine, actor, "full-round")
    here = scene.positions.get(actor.ref) if scene.has_grid else None
    if here is None:
        out["tells"].append("With no map to say who stands adjacent, the twirl takes only "
                            "the one foe.")
        return out
    doc = next((d for d in _docs(actor) if d.get("choice") == TWIRL), None)
    name = doc["name"] if doc else "Tripping Twirl"
    for ref, foe in list(scene.actors.items()):
        if ref in (actor.ref, first.ref) or foe.is_down or ref not in scene.positions \
                or not engine._against(actor, foe):
            continue
        if not gridmod.is_adjacent(tuple(here), actor.size or "medium",
                                   tuple(scene.positions[ref]), foe.size or "medium"):
            continue
        if foe.has_state("state.position.prone") or engine._untrippable(foe):
            continue
        from .engine import Intent

        sub = Intent(op="attack", actor=actor.ref, target=ref,
                     because=f"{actor.name}'s {name}", visibility="hidden",
                     id=f"{intent.id}.twirl-{ref}",
                     params={"manoeuvre": "trip", "rider": name},
                     origin=f"rule:feat-{doc['id'] if doc else 'tripping-twirl'}",
                     origin_name=name)
        got = engine._resolve_maneuver(sub, actor, foe, actor.wielded_key(), {})
        out["rolls"].extend(got.rolls)
        out["effects"].extend(got.effects)
        out["tells"].append(got.tell)
    return out


def choice_refusal(actor, weapon: dict, declared, params: dict) -> str:
    """Why a declared option of this lane cannot ride this swing, or "" (asked beside
    `feat_events.choice_refusal`)."""
    if "feinting_flurry" in declared and ("flurry" not in declared
                                          or not params.get("full_attack")):
        return "Feinting Flurry is made with a flurry of blows, as a full attack."
    if GORY in declared:
        from .feat_events import has_weapon_focus

        if params.get("full_attack") or params.get("iteration") is not None:
            return "Gory Finish is the attack action — one blow — not a full attack's."
        key = str(params.get("weapon") or actor.wielded_key() or "").strip().lower()
        if not has_weapon_focus(actor, key):
            return f"Gory Finish is made with a weapon {actor.name} has Weapon Focus in."
    if FURYS_SNARE in declared:
        # Feat loop b5-maneuver: Fury's Snare is a whip's trip.
        if params.get("manoeuvre") not in (None, "", "trip"):
            return "Fury's Snare is made with a trip; declare it with one."
        key = str(params.get("weapon") or actor.wielded_key() or "").strip().lower()
        if "whip" not in (key, str(weapon.get("crafted_base") or "")):
            return "Fury's Snare is a trip made with a whip."
    if TWIRL in declared:
        if params.get("manoeuvre") not in (None, "", "trip"):
            return "Tripping Twirl is a trip at each foe beside you; declare it with a trip."
        key = str(params.get("weapon") or actor.wielded_key() or "").strip().lower()
        if "quarterstaff" not in (key, str(weapon.get("crafted_base") or "")) \
                or int(weapon.get("hands", 1) or 1) < 2:
            return "Tripping Twirl is made with a quarterstaff in both hands."
        if params.get("full_attack") or params.get("iteration") is not None:
            return "Tripping Twirl is its own full-round action; make it on its own."
    return ""


# --- the Stunning Fist variants: Bonebreaker, Neckbreaker --------------------------------
#
# Activated feats in content/class-abilities/feats-b4-maneuver.json, armed through the
# class abilities' one executor like Jawbreaker (feat loop b2). What they add to the charge
# grammar: `on_fail.ability_damage` (`{"dice": "1d6", "overflow": "con"}`, the score the
# choice names in `charge_ability`), `holding_target` (the user must be grappling the foe:
# Neckbreaker's "after you initiate or maintain a grapple") and `no_larger` ("an opponent
# your size or smaller").

ABILITY_WORDS = {"str": "Strength", "dex": "Dexterity", "con": "Constitution"}


def charge_ability_damage(doc: dict, on_fail: dict) -> dict:
    """The armed charge's ability damage, worked out when armed, or {}."""
    spec = on_fail.get("ability_damage")
    if not isinstance(spec, dict):
        return {}
    ab = str(doc.get("charge_ability") or spec.get("ability") or "str")[:3].lower()
    return {"ability_damage": {"dice": str(spec.get("dice") or "1d6"), "ability": ab,
                               "overflow": str(spec.get("overflow") or "")}}


def charge_unfit(engine, actor, c: dict, defender) -> str:
    """Why this armed blow does nothing to the creature it hit (this lane's clauses)."""
    if c.get("holding_target") and not engine._holds(actor, defender):
        return f"{actor.name} is not grappling {defender.name}"
    if c.get("no_larger") and _size_steps(actor, defender) > 0:
        return f"{defender.name} is larger than {actor.name}"
    return ""


def charge_ability_hit(engine, defender, e, spec: dict, line: str) -> list[dict]:
    """The failed save's ability damage, through `Actor.damage_ability` (the one door a
    score is lowered by). Neckbreaker: "If the targeted ability score is reduced to 0, any
    remaining damage is dealt to that opponent's Constitution score.\""""
    ab = spec["ability"]
    roll = engine.dice.roll(spec["dice"], label=f"{e.name}: {ABILITY_WORDS.get(ab, ab)} "
                                                f"damage", visibility="hidden")
    amount = max(0, roll.total)
    here = defender.ability_score(ab)
    first = min(amount, here) if spec.get("overflow") else amount
    hits = [(ab, first)] + ([(spec["overflow"], amount - first)]
                            if spec.get("overflow") and amount > first else [])
    out, said = [], []
    for score, n in hits:
        if n <= 0:
            continue
        res = defender.damage_ability(score, n)
        out.append({"effect": {"ref": defender.ref, "kind": "ability_damage", **res,
                               "origin": e.origin, "roll": roll.as_dict()}, "tell": ""})
        said.append(f"{n} {ABILITY_WORDS.get(score, score)} (now {res['score']})")
        for cond in defender.ability_zero_effects():
            out.append({"effect": {"ref": defender.ref, "kind": "condition",
                                   "condition": cond, "origin": e.origin}, "tell": ""})
    crossed = engine._hp_state_effects(defender)
    out.extend({"effect": x, "tell": ""} for x in crossed)
    out.append({"effect": {"ref": defender.ref, "kind": "charge_spent", "what": e.name,
                           "origin": e.origin},
                "tell": f"{line}; {e.name} deals " + " and ".join(said or ["nothing"]) + "."
                        + engine._hp_state_tell(crossed)})
    return out


# --- the feint feats: Feinting Flurry, Improved Feinting Flurry, Wave Strike,
# --- Disengaging Shot ------------------------------------------------------------------
#
# The feint is lane E's (`skilluses.feint`); these feats change WHEN it is made and what
# it buys. An engine-written feint check is put in front of the blow it belongs to (the
# whirlwind's shape in `Engine._drive`), carrying the code-only param that says which
# action pays for it: `in_flurry` (none: the flurry's first swing is forgone instead) or
# `swift_feint` (Wave Strike's swift action).

FEINTING_FLURRY = "feinting_flurry"
FLURRY_TURN = "skill.bluff.feint.flurry-turn"           # Improved Feinting Flurry
WAVE_STRIKE = "skill.bluff.feint.wave-strike"
DISENGAGING_SHOT = "skill.bluff.feint.disengaging-shot"
IN_FLURRY = "in_flurry"
SWIFT_FEINT = "swift_feint"


def _feint_raw(raw: dict, flag: str, because: str) -> dict:
    return {"op": "check", "actor": raw.get("actor"), "target": raw.get("target"),
            "id": f"{raw.get('id') or 'attack'}-feint", "because": because,
            "visibility": raw.get("visibility", "hidden"),
            "params": {"skill": "bluff", "feint": True, flag: True}}


def feint_before(engine, raw: dict) -> list[dict]:
    """The feint Feinting Flurry (Dragon Empires Primer) puts in front of a declared
    flurry: "While using flurry of blows to make melee attacks, you can forgo your first
    attack to make a Bluff check to feint." [] when the blow declares none."""
    params = raw.get("params") or {}
    if raw.get("op") != "attack" or not params.get(FEINTING_FLURRY) \
            or not params.get("full_attack") or not raw.get("target"):
        return []
    return [_feint_raw(raw, IN_FLURRY, "Feinting Flurry")]


def wave_strike(engine, raw: dict, draw: dict) -> list[dict]:
    """Wave Strike (UC): "If on your first turn of combat you draw a melee weapon to
    attack an opponent within your reach, you can spend a swift action to make a Bluff
    check to feint against that opponent." Put behind the draw and in front of the blow.
    The first turn is one the bearer has not yet acted in (`Scene.acted`, the flat-footed
    record), and the reach is measured from where they stand (`position.out_of_reach`)."""
    from . import position

    scene = engine.scene
    actor = scene.actors.get(str(raw.get("actor") or ""))
    foe = scene.actors.get(str(raw.get("target") or ""))
    params = raw.get("params") or {}
    if actor is None or foe is None or not scene.in_encounter \
            or not actor.has_state(WAVE_STRIKE) or actor.ref in scene.acted \
            or params.get("manoeuvre"):
        return []
    key = str(params.get("weapon") or "").strip().lower()
    w = actor.weapon(key) if key else {}
    if w.get("category") == "ranged" or params.get("thrown") or (
            scene.has_grid and position.out_of_reach(scene, actor, foe, key) is not None):
        return []
    if engine._swift_refusal(actor, False, "Wave Strike"):
        return []
    return [_feint_raw(raw, SWIFT_FEINT, "Wave Strike")]


def feint_action(intent, action: str) -> str:
    """The action an engine-written feint is paid with."""
    if intent.params.get(IN_FLURRY):
        return "none"
    if intent.params.get(SWIFT_FEINT):
        return "swift"
    return action


def whole_turn(intent, actor) -> bool:
    """Improved Feinting Flurry (Dragon Empires Primer): "While using Feinting Flurry, if
    you successfully feint, your opponent is denied its Dexterity bonus to AC until the
    end of your turn" — the feint's effect is not spent by the first blow."""
    return bool(intent.params.get(IN_FLURRY)) and actor.has_state(FLURRY_TURN)


def drop_first_swing(intent, sequence: list, hands: list) -> tuple[list, list]:
    """The flurry's first attack, forgone for the feint (Feinting Flurry)."""
    if intent.params.get(FEINTING_FLURRY) and intent.params.get("full_attack") \
            and len(sequence) > 1:
        return sequence[1:], hands[1:]
    return sequence, hands


def disengaging_shot(engine, actor, target) -> list[dict]:
    """Disengaging Shot (UC): "Whenever you use Disengaging Feint or Disengaging
    Flourish, you can make a single melee attack against one opponent you succeeded at
    feinting against. That opponent is denied his Dexterity bonus to AC against this
    attack." The blow is owed next in the queue (`owed_swing`, a feat's swing's door), the
    target laid open to it by the feint's own tag (`state.feinted.<ref>`, spent by it)."""
    from . import skilluses
    from .activeeffect import ActiveEffect

    if not actor.has_state(DISENGAGING_SHOT):
        return []
    target.apply_effect(ActiveEffect(
        name=f"feinted by {actor.name}", kind="situation", key=f"feinted-by-{actor.ref}",
        source=skilluses.FEINT_SOURCE, origin="rule:feat-disengaging-shot",
        duration="rounds", rounds_left=1, tags=(f"{skilluses.FEINTED}.{actor.ref}",),
        payload={"by": actor.ref}))
    return [{"ref": actor.ref, "kind": "owed_swing", "target": target.ref,
             "origin": "rule:feat-disengaging-shot",
             "attack": {"op": "attack", "actor": actor.ref, "target": target.ref,
                        "because": f"{actor.name}'s Disengaging Shot",
                        "visibility": "player" if actor.is_pc else "hidden",
                        "params": {"full_attack": False, "reaction": "disengaging-shot"}}}]


def charge_save_ctx(c: dict) -> dict:
    """The save against an armed blow, said for what it would leave: a stunning fist that
    stuns or staggers is a save "against ... special abilities that cause you to become
    staggered or stunned" (Hard-Headed, `effectspec.AGAINST`)."""
    if str(c.get("condition") or "") in ("stunned", "staggered"):
        return {"against": ("stun_or_stagger",)}
    return {}


# --- Siphon Poison ------------------------------------------------------------------------

SIPHON_POISON = "skill.heal.siphon-poison"


def contracted_rounds_ago(engine, aff) -> int | None:
    """How many rounds ago this affliction was taken, or None when it cannot be said (no
    record, or the clock has moved a minute or more since: far past any round window)."""
    at = (aff.payload or {}).get("contracted")
    scene = engine.scene
    if not isinstance(at, dict):
        return None
    if int(getattr(scene, "clock_minutes", 0) or 0) != int(at.get("clock", -1)):
        return None
    if at.get("fight") and scene.in_encounter:
        return max(0, int(scene.round) - int(at.get("round", 0)))
    return 0 if not at.get("fight") and not scene.in_encounter else None


def siphon_poison(engine, intent, actor, patient, aff, mods, partial):
    """Siphon Poison (Champions of Purity): "As a full-round action, you can remove an
    injury poison from a helpless or willing creature's bloodstream with a successful Heal
    check. The DC of this check is equal to the poison's DC. You can only draw out poison
    in this way within the first 2 rounds of when the target was poisoned. If the check is
    successful, the creature no longer suffers any additional effects from the poison."

    Asked by the treat-poison door before its own +4: None when it does not apply (no
    feat, not an injury poison, past the window, an unwilling patient, no full round left),
    and the treatment goes on as the book's. Owner call: when it applies it is taken — it
    ends the poison where treating it only helps the next save. Willing is the patient
    themself or one on the healer's side; anybody else must be helpless."""
    from . import skilluses
    from .activeeffect import ActiveEffect  # noqa: F401 — the effect store's own type
    from . import dc as dc_mod

    if not actor.has_state(SIPHON_POISON):
        return None
    held = (aff.payload or {}).get("affliction") or {}
    if "injury" not in str(held.get("vector") or ""):
        return None
    ago = contracted_rounds_ago(engine, aff)
    if ago is None or ago > 1:
        return None
    willing = patient is actor or not engine._against(actor, patient)
    if not willing and not patient.is_helpless:
        return None
    if skilluses._no_action_left(engine, actor, "full-round", "drawing out a poison"):
        return None
    value = int(held.get("dc") or 10)
    roll = engine._roll_or_suspend(intent, actor, list(mods),
                                   label="Heal check (draw out the poison)", dc=value,
                                   partial=partial)
    skilluses._spend_action(engine, actor, "full-round")
    margin = roll.total - value
    whose = "their own" if patient is actor else f"{patient.name}'s"
    if margin >= 0:
        patient.remove_effects(match=lambda e: e is aff)
        effects = [{"ref": patient.ref, "kind": "condition_removed",
                    "conditions": ["poisoned"], "from": aff.name,
                    "origin": "rule:feat-siphon-poison"}]
        tell = (f"{actor.name} draws the {aff.name} out of {whose} blood before it can "
                f"spread (Siphon Poison, Heal {roll.total} against DC {value}"
                f"{dc_mod.by(margin)}): it does nothing more.")
    else:
        effects = [{"ref": patient.ref, "kind": "treat", "of": "poison", "made": False,
                    "origin": "rule:feat-siphon-poison"}]
        tell = (f"{actor.name} tries to draw the {aff.name} out of {whose} blood and "
                f"cannot (Heal {roll.total} against DC {value}).")
    return skilluses._outcome(intent, rolls=[roll], dc_value=value,
                              basis=f"Siphon Poison: the {aff.name}'s DC {value}",
                              verdict="success" if margin >= 0 else "failure",
                              margin=margin, effects=effects, tell=tell)


# --- Greater Wild Empathy -----------------------------------------------------------------
#
# "You gain a +2 insight bonus on wild empathy checks [the `wild_empathy` funnel target,
# `animals.empathy_mods`], and you may use wild empathy to duplicate an Intimidate check
# rather than a Diplomacy check. In addition, choose one of the following kinds of
# creatures: elementals, fey, lycanthropes, plants, or vermin. You may influence creatures
# of that type with wild empathy, if their Intelligence score is 1 or 2, or they do not
# possess an Intelligence score." The kind is the sheet's parenthetical, bound into the tag
# `class.wild-empathy.reaches.<kind>`; a lycanthrope is the shapechanger subtype.

EMPATHY_REACHES = "class.wild-empathy.reaches"
EMPATHY_INTIMIDATE = "class.wild-empathy.intimidate"
_EMPATHY_KINDS = {"elemental": "type.elemental", "fey": "type.fey", "plant": "type.plant",
                  "vermin": "type.vermin", "lycanthrope": "subtype.shapechanger"}


def empathy_reaches_more(target, by) -> bool:
    from . import animals

    score = animals._int(target)
    if score not in (None, 1, 2):
        return False
    for kind, tag in _EMPATHY_KINDS.items():
        if target.has_state(tag) and (by.has_state(f"{EMPATHY_REACHES}.{kind}")
                                      or by.has_state(f"{EMPATHY_REACHES}.{kind}s")):
            return True
    return False


def empathy_intimidates(engine, intent, actor, skill: str, partial):
    """An Intimidate to influence a creature this bearer's wild empathy reaches, out of a
    fight, rolled as wild empathy when that is the better roll (owner call: the feat says
    "may", and the better of two is the player's obvious choice). None otherwise."""
    from . import animals
    from .dice import stack
    from .skilluses import _target

    if skill != "intimidate" or intent.params.get("opposed_by") \
            or not actor.has_state(EMPATHY_INTIMIDATE) \
            or not actor.has_state("class.wild-empathy") or engine.scene.in_encounter:
        return None
    target = _target(engine, intent)
    if target is None or animals.empathy_reaches(target, actor) is None:
        return None
    empathy = sum(m.value for m in animals.empathy_mods(actor))
    try:
        plain = sum(m.value for m in stack(actor.skill_modifiers("intimidate")))
    except Exception:  # noqa: BLE001 — an untrained or missing skill reads as nothing
        plain = -99
    if empathy < plain and not animals.diplomacy_bar(target, actor):
        return None
    return animals.wild_empathy(engine, intent, actor, target, partial, how="intimidate")


# --- Undermining Exploit --------------------------------------------------------------------

# The ground words (`places.terrain_of`) that are stone underfoot: the mountain and hill
# terrains and anything underground (a cave, a dungeon). Owner call: "rocky" is the
# place's own terrain, since the board marks a square difficult without saying of what.
ROCKY_TERRAINS = ("mountain", "mountains", "hills", "underground", "cave", "caves")


def on_rocky_ground(creature) -> bool:
    """Whether this creature stands on a difficult square of the board in a rocky place:
    Undermining Exploit's "opponents that are located in rocky, difficult terrain". No
    moment or no board, no answer (False, the clause failing closed)."""
    from . import places

    scene = _scene()
    grid = getattr(scene, "grid", None)
    if scene is None or grid is None or creature is None:
        return False
    at = scene.positions.get(creature.ref)
    if at is None:
        return False
    word = places.terrain_of(str(getattr(creature, "at", "") or getattr(scene, "at", "")))
    if word not in ROCKY_TERRAINS:
        return False
    return tuple(at)[:2] in grid.difficult


# --- Gory Finish ----------------------------------------------------------------------------

GORY = "gory_finish"


def gory_finish(engine, actor, defender, choices, state) -> list[dict]:
    """Gory Finish (UC): "When you use the attack action, you can use a weapon with which
    you have Weapon Focus to make a single attack at your highest base attack bonus. If you
    reduce your target to negative hit points, you can spend a swift action to make an
    Intimidate check to demoralize all foes within 30 feet who could see your attack."
    The declared option is the single blow (`choice_refusal` holds it to the attack action
    and the Weapon Focus weapon); the demoralize is Dazzling Display's one roll read against
    each foe (`Engine._free_demoralize`), paid with the swift action, taken when it is free."""
    from . import awareness

    if GORY not in (choices or ()) or state.get("gory_finish") \
            or not (defender.is_dead or defender.hp < 0):
        return []
    if engine._spend_swift(actor, False, "Gory Finish"):
        return []
    state["gory_finish"] = True
    foes = [a for a in engine.scene.actors.values()
            if a is not actor and a is not defender and not a.is_down
            and engine._against(actor, a) and awareness.sees(engine.scene, a, actor)
            and ((g := engine._gap_ft(actor, a)) is None or g <= 30)]
    if not foes:
        return []
    return [{"effect": {"ref": actor.ref, "kind": "gory_finish",
                        "origin": "rule:feat-gory-finish"},
             "tell": f"{defender.name} falls in a spray of blood, and {actor.name} rounds on "
                     f"the rest (Gory Finish)."}] + engine._free_demoralize(actor, foes,
                                                                          "Gory Finish")


# --- Mounted Shield -------------------------------------------------------------------------

MOUNTED_SHIELD = "mount.shield-shared"


def shield_lent(rider) -> int:
    """Mounted Shield (APG): "your base shield bonus (including the bonus from Shield
    Focus but not including enhancement bonuses)". The shield's own row (`shield_stats`,
    whose AC is the base and any material, never the magic layer's enhancement) and the
    rider's feat terms that are a bonus for carrying a shield (`when.bearer.shield`, the
    Shield Focus shape) — read off the documents, never by a feat's name."""
    if not rider.has_state(MOUNTED_SHIELD) or str(rider.shield or "none").lower() == "none":
        return 0
    base = int(rider.shield_stats().get("ac") or 0)
    focus = 0
    for doc in _docs(rider):
        for m in doc.get("modifiers") or ():
            if m.get("type") == "combat_mod" and m.get("target") == "ac" \
                    and ((m.get("when") or {}).get("bearer") or {}).get("shield") is True:
                focus += int(m.get("amount") or 0)
    return max(0, base + focus)


def lent_shield(steed) -> list:
    """The shield term a ridden steed's AC takes from its rider (Mounted Shield)."""
    from . import bodyskills
    from .dice import Modifier

    scene = _scene()
    if scene is None or not steed.has_state(bodyskills.RIDDEN):
        return []
    rider = bodyskills.rider_of(scene, steed)
    if rider is None or bodyskills.mount_of(scene, rider) is not steed:
        return []
    n = shield_lent(rider)
    return [Modifier(n, f"{rider.name}'s shield (Mounted Shield)", "shield")] if n else []


def shield_on_ride(rider) -> list:
    """"In addition, you may add this bonus when making a Ride check to negate a hit
    against your mount using the Mounted Combat feat.\""""
    from .dice import Modifier

    n = shield_lent(rider)
    return [Modifier(n, "shield (Mounted Shield)")] if n else []


# --- Trample, Unseat ------------------------------------------------------------------------

TRAMPLE = "mount.trample"
UNSEAT = "mount.unseat"


def trample(engine, actor, defender, key: str, won: bool) -> list[dict]:
    """Trample (CRB): "When you attempt to overrun an opponent while mounted, your target
    may not choose to avoid you [no target here ever chooses to: an avoid is not offered,
    so the clause holds as the engine stands]. Your mount may make one hoof attack against
    any target you knock down, gaining the standard +4 bonus on attack rolls against prone
    targets." The hoof is the steed's own printed attack, owed next in the queue; the +4 is
    the prone row's, which every melee blow at a prone body already takes."""
    from . import bodyskills

    if key != "overrun" or not won or not actor.has_state(TRAMPLE) \
            or not defender.has_state("state.position.prone") or defender.is_down:
        return []
    steed = bodyskills.mount_of(engine.scene, actor)
    if steed is None or steed.stat_block_weapon("hoof") is None:
        return []
    return [{"ref": steed.ref, "kind": "owed_swing", "target": defender.ref,
             "origin": "rule:feat-trample",
             "attack": {"op": "attack", "actor": steed.ref, "target": defender.ref,
                        "because": f"{actor.name}'s Trample",
                        "visibility": "hidden",
                        "params": {"weapon": "hoof", "full_attack": False,
                                   "reaction": "trample"}}}]


def unseat(engine, intent, actor, defender, weapon_key: str, choices) -> list[dict]:
    """Unseat (CRB): "When charging an opponent while mounted and wielding a lance,
    resolve the attack as normal. If it hits, you may immediately make a free bull rush
    attempt in addition to the normal damage. If successful, the target is knocked off his
    horse and lands prone in a space adjacent to his mount that is directly away from you."
    Asked once the charge's lance hit has landed (`feat_events.after_hit`)."""
    from . import bodyskills

    if "charge" not in (choices or ()) or not actor.has_state(UNSEAT) or defender.is_down \
            or "lance" not in str(weapon_key or "").lower() \
            or bodyskills.mount_of(engine.scene, actor) is None:
        return []
    steed = bodyskills.mount_of(engine.scene, defender)
    got = _sub(engine, intent, actor, defender, "bull rush", UNSEAT, "Unseat")
    out = [{"effect": e, "tell": ""} for e in got.effects]
    out.append({"effect": {"ref": defender.ref, "kind": "rider", "rider": "Unseat",
                           "verdict": got.verdict, "origin": "rule:feat-unseat"},
                "tell": got.tell})
    if got.verdict != "success" or steed is None:
        return out
    bodyskills._unseat(defender, steed)
    scene = engine.scene
    here, mount_at = scene.positions.get(actor.ref), scene.positions.get(steed.ref)
    if scene.has_grid and here is not None and mount_at is not None:
        step = ((mount_at[0] > here[0]) - (mount_at[0] < here[0]),
                (mount_at[1] > here[1]) - (mount_at[1] < here[1]))
        if step != (0, 0):
            # The first square straight on past the steed's own footprint (a horse is
            # Large); open, they land there, through the board's one door (`_put`), else
            # where the bull rush's push left them.
            from . import grid as gridmod

            body = set(gridmod.footprint(tuple(mount_at)[:2], steed.size or "medium"))
            landing = tuple(mount_at)[:2]
            while landing in body:
                landing = (landing[0] + step[0], landing[1] + step[1])
            if engine._open_for(defender.ref, landing):
                engine._put(defender.ref, landing)
    bodyskills._prone(defender, f"{actor.name}'s Unseat", "rule:feat-unseat")
    out.append({"effect": {"ref": defender.ref, "kind": "condition", "condition": "prone",
                           "origin": "rule:feat-unseat"},
                "tell": f"{defender.name} is knocked out of the saddle and lands prone beside "
                        f"{steed.name}."})
    return out


# --- Cypher Script ---------------------------------------------------------------------------

CYPHER_SCRIPT = "spellbook.cypher-script"


def cypher_script(actor, plan: dict, level: int) -> None:
    """Cypher Script (ISWG): "Any spell you scribe in your spellbook costs half as much as
    normal and takes up only half the room it normally would (round all fractions up). It
    only takes you 10 minutes per spell level to scribe a spell into your spellbook (5
    minutes for cantrips)." The copy plan's price and minutes (`spellitems.copy_plan`): the
    hour of study stays, the writing is the feat's. The room is not counted anywhere — a
    spellbook here has no page limit — so that clause has nothing to halve."""
    from . import formulae

    if not actor.has_state(CYPHER_SCRIPT):
        return
    plan["cost_gp"] = -(-int(plan.get("cost_gp") or 0) // 2)
    plan["minutes"] = formulae.STUDY_MINUTES + (5 if level <= 0 else 10 * level)


# --- Field Repair --------------------------------------------------------------------------

FIELD_REPAIR = "craft.field-repair"


def field_repair_cost(actor, obj, cost_gp: float) -> float:
    """Field Repair (UC): "If you are trained in a Craft skill appropriate to a broken item,
    you can repair that item with no raw material cost and no penalty on your Craft skill
    check for using improvised tools." The mend's fifth of the price (`Engine._op_mend`),
    waived for a broken thing by a mender with ranks in Craft. Mending here asks no tools,
    so there is no improvised-tools penalty to lift."""
    if not actor.has_state(FIELD_REPAIR) or not getattr(obj, "broken", False) \
            or int((actor.ranks or {}).get("craft", 0) or 0) < 1:
        return cost_gp
    return 0.0


# === Feat loop batch 5, lane b5-maneuver (2026-11-26) =====================================
#
# The elemental style feats finished on Elemental Fist (b4-combat's charge, pool
# `elemental fist`), and the manoeuvre and defence feats of b5-maneuver.tsv. As above, the
# engine reads documents' TAGS and fields here, never a feat's name.

def fist_share(engine, actor, shown: str, rolls: list, tells: list):
    """(amount, type) of the user's unarmed strike, rolled once for an area that deals
    "your unarmed strike damage plus the [energy] damage from your Elemental Fist"
    (Djinni Spin, Efreeti Touch, Marid Coldsnap, Shaitan Earthblast, UC/Champions of
    Balance). The strike's own dice and its damage terms (`Actor.damage_modifiers`, the
    one funnel the punch itself uses); bludgeoning, as an unarmed strike is."""
    from .dice import stack

    notation = actor.damage_dice("unarmed")
    mods = list(stack(actor.damage_modifiers("unarmed")))
    r = engine.dice.roll(notation, mods, label=f"{shown}: unarmed strike", visibility="player")
    rolls.append(r)
    total = max(1, r.total)
    tells.append(f"The unarmed strike behind it: {notation} — {total}.")
    return total, "bludgeoning"


def escape_payload(actor, rule: dict) -> dict | None:
    """The payload a save-or-condition rider lays when its hold is one a check ends
    (`escape_dc`, a formula over the maker's sheet): Marid Spirit's "entangled in ice ...
    a break DC of 15 + your base attack bonus or monk level, whichever is higher.
    Destroying or breaking the ice ends the entangled condition." The `escape` op answers
    it (`Engine._escape_spell_hold`: a combat manoeuvre or Escape Artist against the DC, a
    standard action), as it answers a web. None when the rider names no escape."""
    from . import resources

    if not rule.get("escape_dc"):
        return None
    try:
        dc = int(resources.evaluate(str(rule["escape_dc"]), actor))
    except resources.FormulaError:
        return None
    return {"ends_when": {"escape": {"dc": dc}}}


def rider_catch_fire(engine, intent, actor, defender, rule: dict, origin: str,
                     state: dict) -> list[dict]:
    """Efreeti Stance (UC): "Creatures that take fire damage from your Elemental Fist
    attack must succeed at a Reflex save (DC 10 + 1/2 your character level + your Wis
    modifier) or catch on fire." The catching is the engine's one clinging fire (the `burn`
    op: 1d6 a round, put out by `extinguish` — Reflex DC 15, +4 rolling on the ground), for
    1d4 rounds, the length the Burn rider gives a caught creature (`Engine._rider_burn`).
    Owner call: the CRB's "Catching on Fire" burns until a save puts it out; the engine's
    fire runs a counted number of rounds, so the Burn rider's 1d4 is taken."""
    if defender.hp <= 0 or defender.is_dead:
        return []
    dc = int(rule.get("dc") or 10)
    made, said = engine._rider_save(defender, str(rule.get("save") or "ref"), dc,
                                    "Reflex save against catching fire", state,
                                    attacker=actor)
    word = str(rule.get("name") or rule.get("rider") or "the fire")
    if made:
        return [{"effect": {"ref": defender.ref, "kind": "rider_resisted", "rider": word,
                            "origin": origin},
                 "tell": f"{defender.name} does not catch fire ({said})."}]
    got, said2 = set_alight(engine, actor, defender, origin, word, state)
    return got + [{"effect": {"ref": defender.ref, "kind": "rider", "rider": word,
                              "origin": origin},
                   "tell": f"{defender.name} catches fire ({said}). {said2}".strip()}]


def set_alight(engine, actor, defender, origin: str, word: str, state: dict):
    """(effect/tell pairs, tell) for the engine's one clinging fire laid on `defender`: the
    `burn` op (1d6 fire a round for 1d4 rounds, put out by `extinguish`), as the Burn
    rider lays it. Shared by Efreeti Stance's rider and Efreeti Touch's cone."""
    rounds = engine.dice.roll("1d4", label="burning rounds", visibility="hidden")
    state.setdefault("rolls", []).append(rounds.as_dict())
    res = engine._run_within(engine.validate([{
        "op": "burn", "actor": defender.ref, "visibility": "hidden",
        "because": f"{actor.name}'s {word}",
        "params": {"to": defender.ref, "dice": "1d6", "damage_type": "fire",
                   "rounds": max(1, rounds.total), "put_out_with": "ref",
                   "put_out_dc": 15, "smother_bonus": 4},
    }], origin=origin, origin_name=word))
    out, said = [], []
    for o in res:
        out.extend({"effect": e, "tell": ""} for e in o.effects or [])
        if o.tell:
            said.append(o.tell)
    return out, " ".join(said) or f"{defender.name} is alight."


# --- Favored Defense, Blundering Defense: terms on the AC and CMD lines --------------------

FAVORED_DEFENSE = "defense.favored-enemy"
BLUNDERING = "defense.blundering"


def favored_defense(defender, attacker) -> int:
    """Favored Defense (APG): "Choose one of your favored enemy types. You add half your
    favored enemy bonus to your CMD and as a dodge bonus to AC when attacked by a favored
    enemy." The pick is the feat's parenthetical; the bonus is the ranger's own for that
    pick (`classfeatures._picks`, the +2/+4 the class table paid), and the attacker must
    be of it (`classfeatures.holds` with `$pick`, favored enemy's own reader). "Its effects
    do not stack": the best one pick gives is the one taken. 0 when none applies."""
    from . import classfeatures as cf

    if attacker is None or not defender.has_state(FAVORED_DEFENSE):
        return 0
    wanted = [cf._enemy_clause(str(d["target"])) for d in _docs(defender)
              if FAVORED_DEFENSE in (d.get("tags") or ()) and d.get("target")]
    best = 0
    for leaf, doc in cf.held(defender):
        if str(doc.get("choice") or "") != "favored enemy":
            continue
        for pick, bonus in cf._picks(defender, leaf, doc):
            if cf._enemy_clause(pick) in wanted and cf.holds(
                    {"target": "$pick"}, defender, {"target_actor": attacker}, pick):
                best = max(best, int(bonus or 0) // 2)
    return best


def _stance_dodge(bearer) -> int:
    """The dodge bonus to AC the bearer has from fighting defensively or total defense:
    the action's own (`sheet.defensive_dodge`, +2/+3 or +4/+6 by Acrobatics) and what
    their feat documents add to it while that stance holds (Cautious Fighter's +2, a term
    whose `when.bearer.state` is the stance). 0 in neither stance."""
    from . import states
    from .sheet import defensive_dodge

    for tag, total in ((states.TOTAL_DEFENSE, True), (states.FIGHTING_DEFENSIVELY, False)):
        if not bearer.has_state(tag):
            continue
        n = defensive_dodge(bearer, total=total)
        for doc in _docs(bearer):
            for m in doc.get("modifiers") or ():
                if m.get("type") == "combat_mod" and m.get("target") == "ac" \
                        and m.get("bonus_type") == "dodge" \
                        and ((m.get("when") or {}).get("bearer") or {}).get("state") == tag:
                    n += int(m.get("amount") or 0)
        return n
    return 0


def blundering_defense(creature) -> int:
    """Blundering Defense (ARG): "Whenever you fight defensively or use the total defense
    action, allies gain a luck bonus to AC and CMD equal to 1/2 the dodge bonus you gain
    from the action you are taking. Allies only gain this bonus while they are adjacent
    to you." Asked of the ally's own AC line: the best a bearer beside them on the board
    lends. No board, nobody stands adjacent (0)."""
    from . import grid as gridmod
    from .position import _same_side

    scene = _scene()
    if scene is None or not getattr(scene, "has_grid", False):
        return 0
    here = scene.positions.get(getattr(creature, "ref", ""))
    if here is None:
        return 0
    best = 0
    for ref, other in scene.actors.items():
        if other is creature or other.is_down or not other.has_state(BLUNDERING) \
                or ref not in scene.positions or not _same_side(scene, creature.ref, ref):
            continue
        if not gridmod.is_adjacent(tuple(here), creature.size or "medium",
                                   tuple(scene.positions[ref]), other.size or "medium"):
            continue
        best = max(best, _stance_dodge(other) // 2)
    return best


def ac_terms(defender, attacker, loses_dex: bool) -> list:
    """This lane's terms on the AC line: Favored Defense's dodge (lost with Dex, as every
    dodge bonus is) and Blundering Defense's luck."""
    from .dice import Modifier

    out = []
    n = 0 if loses_dex else favored_defense(defender, attacker)
    if n:
        out.append(Modifier(n, "Favored Defense", "dodge"))
    n = blundering_defense(defender)
    if n:
        out.append(Modifier(n, "Blundering Defense (an ally's guard)", "luck"))
    return out


def cmd_terms(defender, attacker) -> list:
    """Favored Defense's half bonus to CMD against a favored enemy's manoeuvre (untyped:
    the feat names no type). Blundering Defense's luck reaches CMD through the AC line
    (CRB: luck bonuses to AC apply to CMD)."""
    from .dice import Modifier

    n = favored_defense(defender, attacker)
    return [Modifier(n, "Favored Defense")] if n else []



# --- Fury's Snare --------------------------------------------------------------------------

# The declared option (sheet.ATTACK_CHOICES, the feat document's `choice`): the book's "you
# can choose to drop your whip" is the player's to declare, since it costs the weapon.
FURYS_SNARE = "furys_snare"


def furys_snare(engine, actor, defender, weapon_key: str) -> dict:
    """Fury's Snare (Cheliax, Empire of Devils): "If you successfully use a whip to trip a
    foe, you can choose to drop your whip. Your tripped target gains the entangled
    condition. The target can break free of the whip by making a DC 10 Strength check or a
    DC 15 Escape Artist check (add the enhancement bonus of the whip to these DCs)." The
    whip is let go (`Engine._let_go`: it lies here, still its owner's) and the entangled
    condition carries the two DCs the escape op reads (`escape.dc`, `escape.str_dc`)."""
    out = {"effects": [], "tells": [], "rolls": []}
    if defender.is_down or not engine._drops_in_hand(actor, weapon_key):
        return out
    enh = max([m.value for m in actor.attack_modifiers(weapon_key)
               if (m.type or "") == "enhancement"] or [0])
    rec = engine._let_go(actor, weapon_key)
    defender.add_condition("entangled", None, source=f"{actor.name}'s whip",
                           origin="rule:feat-fury-s-snare",
                           payload={"ends_when": {"escape": {"dc": 15 + enh,
                                                             "str_dc": 10 + enh}}})
    out["effects"] += [{"ref": actor.ref, "kind": "dropped", "item": weapon_key,
                        "prop": rec["name"], "from": "Fury's Snare",
                        "origin": "rule:feat-fury-s-snare"},
                       {"ref": defender.ref, "kind": "condition", "condition": "entangled",
                        "origin": "rule:feat-fury-s-snare"}]
    out["tells"].append(f"{actor.name} lets the whip go and it binds {defender.name} where "
                        f"they fell (Fury's Snare): entangled until they break it (Strength "
                        f"DC {10 + enh}) or slip it (Escape Artist DC {15 + enh}).")
    return out


# --- Snoutgrip, Body Shield: what the one attacked does about a blow -------------------------

SNOUTGRIP = "grapple.snoutgrip"
BODY_SHIELD = "grapple.body-shield"
MOUTH_HELD = "state.silenced.mouth-held"
# The d20 a redirected blow keeps, [face, total] (Body Shield's "using the same attack
# roll"): a code-only param on the engine-written swing at the shield, never the model's.
GIVEN_FACE = "body_shield_roll"


def _bite(weapon_key: str, weapon: dict) -> bool:
    return "bite" in (str(weapon_key or "").lower(),
                      str((weapon or {}).get("name") or "").lower())


def mouth_held(actor, weapon_key: str, weapon: dict) -> bool:
    """Whether this swing is a bite from jaws a Snoutgrip holds shut."""
    return _bite(weapon_key, weapon) and actor.has_state(MOUTH_HELD)


def snoutgrip(engine, intent, actor, defender, weapon_key: str, weapon: dict) -> dict:
    """Snoutgrip (Dragonslayer's Handbook): "As an immediate action, whenever an opponent up
    to one size category larger than you misses you with its bite attack, you can attempt a
    grapple with a -5 penalty on the check. If you succeed, you have grappled your opponent
    and are holding its mouth shut, preventing it from using its bite attack, breath
    weapon, or spells with a verbal component until it escapes your grapple. You may make
    this grapple attempt even if the target is out of your reach."

    The grapple is the free-manoeuvre door's (`_sub`: an engine-built manoeuvre, rolled by
    the engine, no attack of opportunity — the feat needs Improved Grapple — and no reach
    asked), paid with the immediate action. The held mouth rides the grapple condition
    itself, as a chokehold's silence rides the pin, so it ends with the hold; `state.
    silenced` is what refuses a spell with a verbal part. Owner call: taken whenever the
    immediate action is free, as Snake Style's is."""
    out = {"effects": [], "tells": [], "rolls": []}
    if not _bite(weapon_key, weapon) or not defender.has_state(SNOUTGRIP) \
            or defender.is_down or _size_steps(defender, actor) > 1 \
            or engine._holds(defender, actor) or not engine.scene.in_encounter:
        return out
    name = _named_by_tag(defender, SNOUTGRIP) or "Snoutgrip"
    if engine._pay_swift(defender, name, immediate=True):
        return out
    got = _sub(engine, intent, defender, actor, "grapple", SNOUTGRIP, name,
               {"rider_bonus": -5})
    out["rolls"].extend(got.rolls)
    out["effects"].extend(got.effects)
    out["tells"].append(f"{defender.name} lunges for the jaws as they snap shut on air "
                        f"({name}): {got.tell}")
    if got.verdict == "success":
        from . import states

        hold = next((e for e in actor.effects if engine._is_grapple(e)
                     and str((e.payload or {}).get("by") or "") == defender.ref), None)
        if hold is not None:
            hold.tags = tuple(hold.tags or ()) + tuple(
                t for t in states.tags_for("mouth held") if t not in (hold.tags or ()))
            out["effects"].append({"ref": actor.ref, "kind": "condition",
                                   "condition": "mouth held", "by": defender.ref,
                                   "origin": "rule:feat-snoutgrip"})
            out["tells"].append(f"{defender.name} clamps {actor.name}'s mouth shut: no "
                                f"bite, no breath, no spoken spell while the hold lasts.")
    return out


def body_shield(engine, actor, defender, state: dict) -> tuple[int, str]:
    """Body Shield (UC): "As an immediate action while you are grappling an adjacent
    creature, you can make a grapple combat maneuver check against that creature to gain
    cover against a single attack. If you are successful and the attack misses you, that
    attack targets the creature you used as cover, using the same attack roll. You cannot
    use this feat against a creature grappling you, and the cover you gain ends after the
    attack you gained cover against is resolved."

    (cover AC, the shield's ref) for this swing, decided once per swing and kept in the
    attack's state. The shield is a creature the bearer holds (`Engine._holds`) and that
    does not hold the bearer, beside them; the check is the bearer's grapple CMB against
    its CMD, rolled by the engine (the immediate action is off the bearer's turn). Owner
    call, as Snake Style's: used on the first blow each round while the immediate action
    is free. Cover is +4 (CRB, Cover)."""
    from . import grid as gridmod
    from .dice import d20_succeeds

    key = f"body_shield:{state['i']}"
    if key in state:
        return tuple(state[key])
    state[key] = (0, "")
    scene = engine.scene
    if not defender.has_state(BODY_SHIELD) or defender.is_down or not scene.has_grid:
        return state[key]
    here = scene.positions.get(defender.ref)
    shield = next((o for r, o in scene.actors.items()
                   if o is not actor and o is not defender and not o.is_down
                   and engine._holds(defender, o) and not engine._holds(o, defender)
                   and here is not None and r in scene.positions
                   and gridmod.is_adjacent(tuple(here), defender.size or "medium",
                                           tuple(scene.positions[r]), o.size or "medium")),
                  None)
    if shield is None:
        return state[key]
    name = _named_by_tag(defender, BODY_SHIELD) or "Body Shield"
    if engine._pay_swift(defender, name, immediate=True):
        return state[key]
    roll = engine.dice.d20(defender.cmb_modifiers("grapple", defender=shield),
                           label=f"{defender.name} grapple ({name})", visibility="hidden")
    state["rolls"].append(roll.as_dict())
    cmd = shield.cmd()
    if not d20_succeeds(roll, cmd):
        state["tells"].append(f"{defender.name} tries to haul {shield.name} into the way "
                              f"({name}, {roll.total} against CMD {cmd}) and cannot.")
        return state[key]
    state["tells"].append(f"{defender.name} hauls {shield.name} into the way ({name}, "
                          f"{roll.total} against CMD {cmd}): cover, +4 to AC.")
    state[key] = (4, shield.ref)
    return state[key]


def shield_struck(engine, actor, defender, weapon_key: str, natural: int,
                  state: dict, total: int = 0) -> list[dict]:
    """The blow Body Shield's cover turned aside, owed at the creature used as cover with
    the same d20 (`GIVEN_FACE`) — an engine-written swing, next in the queue (the owed
    swing door). A natural 1 misses everybody, so it is owed nobody."""
    _, ref = state.get(f"body_shield:{state['i']}") or (0, "")
    if not ref or ref not in engine.scene.actors or natural == 1:
        return []
    shield = engine.scene.actors[ref]
    state["tells"].append(f"The blow meant for {defender.name} goes into {shield.name} "
                          f"instead (Body Shield).")
    return [{"ref": actor.ref, "kind": "owed_swing", "target": ref,
             "origin": "rule:feat-body-shield",
             "attack": {"op": "attack", "actor": actor.ref, "target": ref,
                        "because": f"{defender.name}'s Body Shield",
                        "visibility": "hidden", "origin": "rule:feat-body-shield",
                        "params": {"weapon": weapon_key, "full_attack": False,
                                   "reaction": "body-shield",
                                   GIVEN_FACE: [int(natural), int(total)]}}}]


def given_roll(engine, intent, label: str):
    """The redirected blow's attack roll: the same face and the same total as the one that
    missed the bearer, whatever this target's terms would have made of it."""
    from .dice import Modifier

    face, total = (list(intent.params.get(GIVEN_FACE) or ()) + [0, 0])[:2]
    return engine.dice.given(int(face), [Modifier(int(total) - int(face),
                                                  "the same attack roll (Body Shield)")],
                             label)


def reach_waived(intent) -> bool:
    """A blow the engine wrote that lands whatever the gap: Body Shield's redirected
    attack ("that attack targets the creature you used as cover")."""
    return intent.params.get(GIVEN_FACE) is not None \
        and str(intent.origin or "") == "rule:feat-body-shield"


# --- Divert Harm -----------------------------------------------------------------------------

DIVERT_HARM = "defense.divert-harm"


def divert_harm(engine, target, spell, save_kind: str, save_effect: str, kind: str,
                amount: int, dtype: str, area: bool, dc: int, state: dict):
    """Divert Harm (Bastards of Golarion): "Whenever you are the target of an area-of-effect
    attack that normally deals half damage on a successful Reflex save (such as a fireball
    spell ...), you may, as an immediate action, wrestle an adjacent foe into harm's way
    ... your opponent must attempt a Reflex save against the attack in your place. If your
    opponent fails, it takes half damage from the attack and you take none; if it
    succeeds, it takes no damage and you take damage as normal as though you'd failed your
    saving throw (though this damage is still reduced by abilities such as improved
    evasion) ... only on a foe within one size category of yourself."

    What the target takes, or None when the feat is not used (the cast's own save then
    runs). Decided once per target and kept in the cast's state, so a save popup that
    brings the loop round again rolls nothing twice. Owner call, taking "may" as the
    better odds: used when the foe's Reflex is worse than the bearer's own, since a foe
    who saves leaves the bearer the whole blast. The foe's save is the engine's roll."""
    from . import grid as gridmod
    from .dice import d20_succeeds
    from .position import _same_side

    key = f"divert:{target.ref}"
    if key in state:
        return state[key]
    state[key] = None
    scene = engine.scene
    if save_kind != "ref" or save_effect != "half" or kind != "damage" or not area \
            or not target.has_state(DIVERT_HARM) or target.is_down or not scene.has_grid:
        return None
    here = scene.positions.get(target.ref)
    if here is None:
        return None

    def ref_bonus(a) -> int:
        return sum(m.value for m in a.save_modifiers("ref"))

    foes = [o for r, o in scene.actors.items()
            if o is not target and not o.is_down and r in scene.positions
            and not _same_side(scene, target.ref, r) and abs(_size_steps(target, o)) <= 1
            and gridmod.is_adjacent(tuple(here), target.size or "medium",
                                    tuple(scene.positions[r]), o.size or "medium")]
    foes.sort(key=ref_bonus)
    if not foes or ref_bonus(foes[0]) >= ref_bonus(target):
        return None
    foe = foes[0]
    name = _named_by_tag(target, DIVERT_HARM) or "Divert Harm"
    if engine._pay_swift(target, name, immediate=True):
        return None
    roll = engine.dice.d20(foe.save_modifiers("ref", {"against": "spell"}),
                           label=f"{foe.name} Reflex save ({name})", visibility="hidden")
    state["rolls"].append(roll.as_dict())
    made = d20_succeeds(roll, dc)
    said = f"Reflex {roll.total} against DC {dc}"
    if not made:
        hit = engine._apply_damage(foe, max(0, amount // 2), dtype, traits=("area",))
        hit["origin"] = f"rule:feat-{_slug(name)}"
        state["effects"].append(hit)
        state["tells"].append(f"{target.name} wrestles {foe.name} into the {spell.name} "
                              f"({name}): {foe.name} fails ({said}) and takes {hit['amount']} "
                              f"{hit['type']}; {target.name} takes none.")
        state[key] = 0
        return 0
    share, evaded = engine._evasion(target, "ref", True, False)
    taken = max(0, amount // 2) if share == "half" else amount
    state["tells"].append(f"{target.name} wrestles {foe.name} into the {spell.name} "
                          f"({name}), but {foe.name} twists clear ({said}) and "
                          f"{target.name} takes the blast" + (f" — {evaded}" if evaded
                                                               else "") + ".")
    state[key] = taken
    return taken


# --- Team Pickpocketing ----------------------------------------------------------------------

TEAM_PICKPOCKET = "teamwork.team-pickpocketing"


def team_pickpocket(engine, feinter, target) -> tuple[list, list, list]:
    """Team Pickpocketing (UC): "Whenever an ally with this feat succeeds a Bluff check to
    feint an opponent, if you are adjacent to that creature, you can spend an immediate
    action to make a Sleight of Hand check to pickpocket that opponent and gain a +4 bonus
    on that attempt." (effects, tells, rolls) for each ally who does.

    The check is Sleight of Hand's own (CRB: "DC 20 ... to lift a small object from a
    person"; "the opponent [makes] a Perception check to notice the attempt", opposed),
    trained only. What is lifted is what a steal would take that is not fastened
    (`Engine._steal_choice`), moved by the steal's own door (`_outcome_take`: the thing in
    the lifter's hands, still the victim's, on the props ledger). Owner call: taken
    whenever the immediate action is free and something loose is there to lift."""
    from .dice import Modifier
    from .position import _same_side
    from .sheet import IllegalSheet
    from . import grid as gridmod

    effects, tells, rolls = [], [], []
    scene = engine.scene
    if not feinter.has_state(TEAM_PICKPOCKET) or not scene.has_grid:
        return effects, tells, rolls
    there = scene.positions.get(target.ref)
    for ref, ally in list(scene.actors.items()):
        if ally is feinter or ally.is_down or not ally.has_state(TEAM_PICKPOCKET) \
                or not _same_side(scene, feinter.ref, ref) or ref not in scene.positions \
                or there is None or not gridmod.is_adjacent(
                    tuple(scene.positions[ref]), ally.size or "medium", tuple(there),
                    target.size or "medium"):
            continue
        loot = engine._steal_choice(target, "")
        if not isinstance(loot, dict) or loot.get("fastened"):
            continue
        try:
            mods = list(ally.skill_modifiers("sleight of hand"))
        except IllegalSheet:
            continue                              # trained only (CRB p.104)
        name = _named_by_tag(ally, TEAM_PICKPOCKET) or "Team Pickpocketing"
        if engine._pay_swift(ally, name, immediate=True):
            continue
        check = engine.dice.d20(mods + [Modifier(4, name)],
                                label=f"{ally.name} Sleight of Hand ({name})",
                                visibility="hidden")
        try:
            seen = engine.dice.d20(target.skill_modifiers("perception", opposed=True),
                                   label=f"{target.name} Perception", visibility="hidden")
        except IllegalSheet:
            seen = None
        rolls += [check] + ([seen] if seen is not None else [])
        noticed = seen is not None and seen.total >= check.total
        if check.total < 20:
            tells.append(f"{ally.name} reaches for {target.name}'s {loot['label']} while "
                         f"the feint holds them ({name}, Sleight of Hand {check.total} "
                         f"against DC 20) and comes away empty.")
            continue
        from .tables import MANEUVERS

        _, _, recs = engine._outcome_take(MANEUVERS["steal"], None, ally, target, 0, None, loot,
                                          lambda *a, **k: "")
        effects.extend(dict(r, origin=f"rule:feat-{_slug(name)}") for r in recs)
        tells.append(f"{ally.name} lifts {target.name}'s {loot['label']} while the feint "
                     f"holds them ({name}, Sleight of Hand {check.total} against DC 20)"
                     + (f"; {target.name} feels it go." if noticed else
                        f"; {target.name} never feels it."))
    return effects, tells, rolls


# --- Stealth Synergy -------------------------------------------------------------------------

STEALTH_SYNERGY = "teamwork.stealth-synergy"


def _sees_ally(actor, ally) -> bool:
    """Whether a hider sees an ally beside it: a won Stealth hides from the other side,
    not from the party that watched it slip away — only blindness or invisibility (unseen
    by eyes that cannot see it) takes the ally from view."""
    from . import awareness

    if actor.has_state("state.senses.blinded"):
        return False
    return not ally.has_state(awareness.INVISIBLE) or awareness.sees_invisible(actor)


def stealth_synergy(engine, actor, roll):
    """Stealth Synergy (UC): "While you can see one or more allies who also have this feat,
    whenever you and your allies make a Stealth check, you all take the highest roll and
    add all your modifiers to Stealth." The d20s of the hiders who see each other: this
    check keeps the best face among its own and those its allies hid with (the face is
    kept in each hiding's payload, `Engine._stealth_lands`), and an ally's standing result
    is raised to it when this one rolled higher. Returns the roll to use."""
    from . import awareness
    from .position import _same_side

    if not actor.has_state(STEALTH_SYNERGY):
        return roll
    scene = engine.scene
    mates = [o for r, o in scene.actors.items()
             if o is not actor and not o.is_down and o.has_state(STEALTH_SYNERGY)
             and _same_side(scene, actor.ref, r) and _sees_ally(actor, o)]
    hiding = [(o, awareness.sneaking(o)) for o in mates]
    hiding = [(o, e) for o, e in hiding if e is not None
              and int((e.payload or {}).get("face") or 0) > 0]
    if not hiding:
        return roll
    own = int(roll.natural or 0)
    best = max([own] + [int(e.payload["face"]) for _, e in hiding])
    for o, e in hiding:
        face = int(e.payload["face"])
        if best > face:
            e.payload = dict(e.payload, face=best,
                             result=int(e.payload.get("result") or 0) + best - face)
    if best > own:
        return engine.dice.given(best, list(roll.modifiers),
                                 f"{roll.label} (Stealth Synergy: the best roll, {best})")
    return roll
