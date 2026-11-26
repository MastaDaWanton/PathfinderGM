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
