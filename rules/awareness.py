"""Who knows where a hidden creature is — asked of one observer at a time.

The owner's question (2026-10-30): "with potions of invisibility and the stealth skill will
npcs not only fail to see me the turn i take it but also still honor that in the following
turns assuming I have not done anything to reveal myself?" Measured on 0.2.23 (probes in
the investigation's scratchpad, `invis/`): no. The potion's invisible condition gave the
50% miss chance and nothing else — every creature's turn picked the player by ref, closed
on the square they stood in and swung (the fallback 4 of 4 rounds, gemma 3 of 3 turns), a
walk out of reach drew an attack of opportunity, attacking never ended it, and a Stealth
check that was won left nothing behind: the next turn the thug walked up and hit them.

**The rules this module carries** (Core Rulebook; quotes checked against the raw AoN pages
on 2026-10-30, and a second pass corrected two of the brief's paraphrases):

* Invisibility, Combat/Special Abilities (aonprd.com/Rules.aspx?ID=431, CRB p.564): "A
  creature can generally notice the presence of an active invisible creature within 30
  feet with a DC 20 Perception check. The observer gains a hunch that 'something's there'
  but can't see it or target it accurately with an attack." "It's practically impossible
  (+20 DC) to pinpoint an invisible creature's location with a Perception check." "Even
  once a character has pinpointed the square that contains an invisible creature, the
  creature still benefits from total concealment (50% miss chance)." "If an invisible
  creature strikes a character, the character struck knows the location of the creature
  that struck him (until, of course, the invisible creature moves)" — unless its reach is
  more than 5 feet, when the struck one "knows the general location ... but has not
  pinpointed the exact location". The DC table: in combat or speaking -20, moving at half
  speed -5, at full speed -10, running or charging -20, not moving +20, some distance away
  +1 per 10 feet, behind a door +5, behind a stone wall +15. And the guessed square: "have
  the player choose the space where the character will direct the attack ... If the
  enemy's not there, roll the miss chance as if it were there and tell him that the
  character has missed, regardless of the result."
* Concealment (aonprd.com/Rules.aspx?Name=Concealment&Category=Combat%20Modifiers, CRB
  p.196): "You can't attack an opponent that has total concealment, though you can attack
  into a square that you think he occupies", and "You can't execute an attack of
  opportunity against an opponent with total concealment, even if you know what square or
  squares the opponent occupies." Also: "You can use concealment to make a Stealth check.
  Without concealment, you usually need cover to make a Stealth check."
* Stealth (aonprd.com/Skills.aspx?ItemName=Stealth, CRB p.106): "Creatures that fail to
  beat your Stealth check are not aware of you and treat you as if you had total
  concealment." "If people are observing you using any of their senses (but typically
  sight), you can't use Stealth. Against most creatures, finding cover or concealment
  allows you to use Stealth." "You can move up to half your normal speed and use Stealth
  at no penalty." "Your Stealth immediately ends after you make an attack roll, whether or
  not the attack is successful (except when sniping ...)." Sniping: "If you've already
  successfully used Stealth at least 10 feet from your target, you can make one ranged
  attack and then immediately use Stealth again. You take a -20 penalty". And invisible:
  "+40 bonus on Stealth checks if you are immobile, or a +20 bonus ... if you're moving".
* Perception (aonprd.com/Skills.aspx?ItemName=Perception, CRB p.102): "Most Perception
  checks are reactive, made in response to observable stimulus. Intentionally searching
  for stimulus is a move action." (The brief's "as a move action, you can attempt to notice
  something you failed to notice previously" is NOT on the page; this is the line used.)

**The shape is Pathfinder Second Edition's and Ultimate Intrigue's, not one this app
invented.** PF2e's detection states are "relative to the viewer — it's possible for a
creature to be observed to you but hidden from your ally" (2e.aonprd.com/Rules.aspx?
ID=2414), and Ultimate Intrigue (aonprd.com/Rules.aspx?ID=2255, p.187) holds the same four
steps per pair: unaware, aware of presence, aware of location, observing. So the facts live
on the OBSERVER, through the one applicator, as the `knows.*` bridge the design record
promised (docs/states-effects-tells.md, last section):

    knows.where.<ref>   pinpointed: this observer knows the square <ref> stands in. The
                        payload holds the square, and the answer is "no" the moment the
                        square is not that one any more — compared, not trusted, so no
                        door that moves a body can leave a stale pinpoint behind.
    knows.near.<ref>    a hunch: something is there, within 30 ft, and not where.

and the hiding itself lives on the hidden one: `state.hidden.invisible` (the condition)
and `state.hidden.stealth` (a won Stealth check, source `rule:stealth`, the result in the
payload). Every question is asked here, so the targeting gate, the attack of opportunity,
the conversation and the narrator's brief cannot disagree about who can see whom.

Refused, with reasons:

* A second awareness store on the scene (a dict of who-sees-whom). Law 2: every fact is
  an `ActiveEffect`, and a dict beside them is the parallel store the ratchet exists for.
* Rolling every observer every time anything is asked. The book rolls Perception
  reactively, to a stimulus; here that is the start of each creature's turn in a fight,
  an arrival out of one, and an observer's own search — never a query.
* Reading the hiding from the prose. The narrator is told who cannot see the player; it
  is never the authority on it.
"""
from __future__ import annotations

from . import states
from .activeeffect import ActiveEffect

HIDDEN = "state.hidden"
INVISIBLE = "state.hidden.invisible"
SNEAKING = "state.hidden.stealth"
SNEAKING_KEY = "sneaking"
SNEAKING_FAST_KEY = "sneaking-fast"

KNOWS_WHERE = "knows.where"
KNOWS_NEAR = "knows.near"

STEALTH_ORIGIN = "rule:stealth"
PERCEPTION_ORIGIN = "rule:perception"

# The book's numbers (module docstring for the sources).
NOTICE_DC = 20
# Perception's own table (aonprd.com/Skills.aspx?ItemName=Perception, CRB p.102): "Notice
# a visible creature 0", "Notice a creature using Stealth: Opposed by Stealth", and among
# the DC modifiers "Creature or object is invisible +20". NOTICE_DC is the first plus this;
# the Invisibility table's row "Using Stealth: Stealth Check +20" is the second plus this.
INVISIBLE_DC = 20
PINPOINT_STEP = 20
NOTICE_RANGE_FT = 30
MOTION_DC = {"still": 20, "half": -5, "full": -10, "run": -20}
LOUD_DC = -20
WALL_DC = 15
SNIPING_PENALTY = -20
STILL_BONUS = 40
MOVING_BONUS = 20
SNIPE_FROM_FT = 10

# What ends a hiding, in the vocabulary `Engine._ends_on_act` reads off an effect's payload:
# "an attack includes any spell targeting a foe or whose area or effect includes a foe"
# (Invisibility, CRB p.301), and Stealth "immediately ends after you make an attack roll".
ENDS_ON_ATTACK = {"acts": ["attack", "cast_offensive"]}


def where_tag(ref: str) -> str:
    return f"{KNOWS_WHERE}.{ref}"


def near_tag(ref: str) -> str:
    return f"{KNOWS_NEAR}.{ref}"


def _tags_of(actor) -> list[str]:
    out = [str(t) for e in getattr(actor, "effects", ()) or () for t in (e.tags or ())]
    try:
        out.extend(str(t) for t in actor.standing_tags())
    except Exception:  # noqa: BLE001 — a body with no documents stands on nothing
        pass
    return out


def sees_invisible(observer) -> bool:
    """See invisibility, true seeing, blindsight — `Actor.eyes`, the light model's reader."""
    try:
        return bool(observer.eyes().get("see_invisible"))
    except Exception:  # noqa: BLE001
        return False


def sneaking(subject) -> ActiveEffect | None:
    """The won Stealth check this creature is hiding behind, or None."""
    for e in getattr(subject, "effects", ()) or ():
        if any(states.matches(str(t), SNEAKING) for t in e.tags or ()):
            return e
    return None


def _stealth_bonus(subject) -> int:
    try:
        return sum(int(m.value) for m in subject.skill_modifiers("stealth"))
    except Exception:  # noqa: BLE001 — a body with no sheet hides with its 10 alone
        return 0


def stealth_result(subject) -> int | None:
    e = sneaking(subject)
    if e is None:
        return None
    try:
        return int((e.payload or {}).get("result"))
    except (TypeError, ValueError):
        return None


def _spot(scene, subject) -> tuple:
    pos = (getattr(scene, "positions", {}) or {}).get(subject.ref)
    return (getattr(scene, "at", "") or "", list(pos[:2]) if pos else None)


def knows_where(scene, observer, subject) -> bool:
    """Whether `observer` holds a pinpoint on `subject` that is still true: the square it
    was taken on is the square the subject stands in now."""
    if observer is None or subject is None:
        return False
    tag = where_tag(subject.ref)
    at, square = _spot(scene, subject)
    for e in observer.effects:
        if tag in (e.tags or ()):
            p = e.payload or {}
            if p.get("at", at) == at and (p.get("square") == square):
                return True
    return False


def has_hunch(observer, subject) -> bool:
    tag = near_tag(subject.ref)
    return any(tag in (e.tags or ()) for e in getattr(observer, "effects", ()) or ())


def sees(scene, observer, subject) -> bool:
    """Whether `observer` can see `subject` — observing it, in Ultimate Intrigue's word.

    Not hidden: seen. Invisible: seen only by eyes that see invisibility, and never by a
    pinpoint (a pinpointed invisible creature keeps total concealment). Hidden any other
    way — a won Stealth check, a scheme's `state.hidden` — seen by an observer who has
    found it (`knows.where`), and by nobody else."""
    if observer is None or subject is None or observer is subject:
        return True
    if not subject.has_state(HIDDEN):
        return True
    if subject.has_state(INVISIBLE) and not sees_invisible(observer) \
            and not one_sphere(observer, subject):
        return False
    other = [t for t in _tags_of(subject)
             if states.matches(t, HIDDEN) and not states.matches(t, INVISIBLE)]
    if not other:
        return True
    return knows_where(scene, observer, subject)


def group_of(actor) -> dict:
    """The group an invisibility shared by several creatures holds `actor` in — its
    `ends_when` with a `group` id (`Engine._lay_condition`, mass invisibility and
    invisibility sphere) — or {}."""
    for e in getattr(actor, "effects", ()) or ():
        ends = (e.payload or {}).get("ends_when") or {}
        if ends.get("group") and any(states.matches(str(t), INVISIBLE) for t in e.tags or ()):
            return dict(ends)
    return {}


def one_sphere(observer, subject) -> bool:
    """Both inside one invisibility sphere: "Those affected by this spell can see each other
    and themselves as if unaffected by the spell" (Invisibility Sphere, CRB p.302). Mass
    invisibility's group cannot ("Individuals in the group cannot see each other")."""
    a, b = group_of(observer), group_of(subject)
    return bool(a) and a.get("group") == b.get("group") and bool(a.get("see_each_other"))


def locates(scene, observer, subject) -> bool:
    """Whether `observer` knows which square `subject` is in — enough to aim a blow at it
    (with the miss chance invisibility still gives), not enough for an attack of
    opportunity."""
    return sees(scene, observer, subject) or knows_where(scene, observer, subject)


def unseen_by(scene, subject) -> list:
    """The conscious creatures here, not the subject's own side, who cannot see it."""
    out = []
    for ref, a in (getattr(scene, "actors", {}) or {}).items():
        if a is subject or (subject.is_pc and a.is_pc):
            continue
        if not can_perceive(a):
            continue
        if not sees(scene, a, subject):
            out.append(a)
    return out


def can_perceive(observer) -> bool:
    """Awake and in a state to notice anything: not down, not helpless."""
    if observer is None or observer.is_down:
        return False
    try:
        return not observer.is_helpless
    except Exception:  # noqa: BLE001
        return True


# --- motion, for the DC table and the +40 --------------------------------------------------

def _recent(scene, mark: dict | None) -> bool:
    """Whether a motion or loudness mark was made in the subject's most recent turn.

    In a fight: within the last cycle of the order (this round, or last round after this
    slot). Out of one: in this minute of the clock, which is this batch's — a move and the
    check that follows it in one turn are one moment."""
    if not mark:
        return False
    if getattr(scene, "in_encounter", False):
        r, t = int(mark.get("round", -99)), int(mark.get("turn", -99))
        now_r, now_t = int(getattr(scene, "round", 0)), int(getattr(scene, "turn", 0))
        return r == now_r or (r == now_r - 1 and t > now_t)
    return int(mark.get("minute", -1)) == int(getattr(scene, "clock_minutes", 0) or 0)


def _mark(scene, **extra) -> dict:
    return {"round": int(getattr(scene, "round", 0) or 0),
            "turn": int(getattr(scene, "turn", 0) or 0),
            "minute": int(getattr(scene, "clock_minutes", 0) or 0), **extra}


def _hidings(subject) -> list:
    return [e for e in getattr(subject, "effects", ()) or ()
            if any(states.matches(str(t), HIDDEN) for t in e.tags or ())]


def note_motion(scene, subject, feet) -> None:
    """Record, on the subject's own hiding effects, that it just moved `feet`."""
    for e in _hidings(subject):
        e.payload = dict(e.payload or {}, moved=_mark(scene, feet=int(feet or 0)))


def note_loud(scene, subject) -> None:
    """Record that it fought or spoke ("in combat or speaking", -20 to notice)."""
    for e in _hidings(subject):
        e.payload = dict(e.payload or {}, loud=_mark(scene))


def motion(scene, subject) -> str:
    """"still", "half", "full" or "run": how it moved in its most recent turn."""
    best = None
    for e in _hidings(subject):
        m = (e.payload or {}).get("moved")
        if _recent(scene, m) and (best is None or int(m.get("feet", 0)) > int(best.get("feet", 0))):
            best = m
    if best is None or int(best.get("feet", 0) or 0) <= 0:
        return "still"
    speed = max(5, int(getattr(subject, "speed_feet", 30) or 30))
    sneak = sneaking(subject)
    if sneak is not None and any(states.matches(str(t), "state.slowed")
                                 for t in sneak.tags or ()):
        speed *= 2          # the half-speed hiding's own halving is not the measure
    feet = int(best.get("feet", 0))
    if feet > speed:
        return "run"
    return "half" if feet * 2 <= speed else "full"


def loud(scene, subject) -> bool:
    return any(_recent(scene, (e.payload or {}).get("loud")) for e in _hidings(subject))


def invisible_stealth(subject):
    """The invisible condition's Stealth bonus, as a Modifier: +40 holding still, +20
    moving (Stealth, CRB p.106; the spell repeats it). Asked through the moment the roll
    is made in (`sheet.current_moment`); with no moment to ask, the smaller +20 — a
    bonus the engine could not confirm is not handed out."""
    from .dice import Modifier
    from .sheet import current_moment

    moment = current_moment()
    scene = getattr(moment, "scene", None) if moment is not None else None
    if scene is not None and motion(scene, subject) == "still":
        return Modifier(STILL_BONUS, "invisible, holding still")
    return Modifier(MOVING_BONUS, "invisible, moving")


# --- the Perception check --------------------------------------------------------------

def _gap(scene, a, b) -> float | None:
    from .grid import distance_between

    here = (getattr(scene, "positions", {}) or {}).get(a.ref)
    there = (getattr(scene, "positions", {}) or {}).get(b.ref)
    if getattr(scene, "grid", None) is None or not here or not there:
        return None
    return distance_between(tuple(here[:2]), str(a.size or "medium"),
                            tuple(there[:2]), str(b.size or "medium"))


def _walled(scene, a, b) -> bool:
    grid = getattr(scene, "grid", None)
    here = (getattr(scene, "positions", {}) or {}).get(a.ref)
    there = (getattr(scene, "positions", {}) or {}).get(b.ref)
    if grid is None or not here or not there:
        return False
    try:
        return not grid.line_of_sight(tuple(here), tuple(there), solid_only=True)
    except Exception:  # noqa: BLE001
        return False


def notice_dcs(scene, observer, subject) -> tuple[int | None, int | None, list[str]]:
    """(the DC to notice it is there, the DC to pinpoint it, what made them) for this
    observer, or (None, None, why) when it cannot be noticed from here at all."""
    why: list[str] = []
    gap = _gap(scene, observer, subject)
    far = int(gap) // 10 if gap else 0
    wall = WALL_DC if _walled(scene, observer, subject) else 0
    hidden_by_stealth = stealth_result(subject)
    invis = subject.has_state(INVISIBLE) and not sees_invisible(observer)
    if invis:
        if gap is not None and gap > NOTICE_RANGE_FT and hidden_by_stealth is None:
            return None, None, [f"more than {NOTICE_RANGE_FT} ft away"]
        how = motion(scene, subject)
        base = NOTICE_DC + MOTION_DC[how]
        why.append(f"invisible, {'holding still' if how == 'still' else how + ' speed'}")
        noisy = LOUD_DC if loud(scene, subject) else 0
        if noisy:
            base += noisy
            why.append("fighting or speaking")
        # "Using Stealth | Stealth Check +20" (the Invisibility table, CRB p.564). Read
        # until 2026-10-30 as the invisible condition's own +20 on Stealth, already inside
        # the stored result, and so never added. Settled from the pages: the +20 is
        # Perception's DC modifier "Creature or object is invisible +20" — the same +20
        # that makes "Notice a visible creature 0" the table's DC 20 — laid on Perception's
        # "Notice a creature using Stealth: Opposed by Stealth". The condition's Stealth
        # bonus is a different line on a different roll ("If you are invisible, you gain a
        # +40 bonus on Stealth checks if you are immobile, or a +20 bonus on Stealth checks
        # if you're moving", Stealth, CRB p.106), and stays inside the result. So: the
        # result, +20. The motion rows are not laid again: how it moved is already in the
        # check (the +20/+40, half speed or the -5). A Stealth roll worse than the table's
        # own DC does not make an invisible body easier to find — the larger stands.
        if hidden_by_stealth is not None \
                and hidden_by_stealth + INVISIBLE_DC + noisy > base:
            base = hidden_by_stealth + INVISIBLE_DC + noisy
            why.append("hiding as well")
        notice = base + far + wall
        return notice, notice + PINPOINT_STEP, why + (
            [f"{int(gap)} ft away"] if far else []) + (["behind a wall"] if wall else [])
    if hidden_by_stealth is None:
        if not subject.has_state(HIDDEN):
            return None, None, ["nothing to find"]
        # Hidden with no check behind it — a scheme's "hide" (rules/schemes.py), done off
        # the page with nobody's Perception to oppose: taken as the hider's 10 ("Taking
        # 10", CRB p.86: "When your character is not in immediate danger or distracted").
        # Before 2026-10-30 this answered "nothing to find", and a hidden NPC could never
        # be found by anybody's search.
        hidden_by_stealth = 10 + _stealth_bonus(subject)
    dc = hidden_by_stealth + far + wall
    return dc, dc, ["hiding"] + ([f"{int(gap)} ft away"] if far else []) + (
        ["behind a wall"] if wall else [])


def pinpoint(scene, observer, subject, why: str) -> ActiveEffect:
    """`observer` knows the square `subject` stands in, through the one applicator."""
    forget_one(observer, subject, near=True)
    at, square = _spot(scene, subject)
    return observer.apply_effect(ActiveEffect(
        name=f"knows where {subject.name} is", kind="situation",
        key=f"knows-where:{subject.ref}", source=f"{PERCEPTION_ORIGIN}:{subject.ref}",
        origin=PERCEPTION_ORIGIN, duration="until-dismissed",
        tags=(where_tag(subject.ref),),
        payload={"at": at, "square": square, "why": why}))


def hunch(scene, observer, subject) -> ActiveEffect:
    at, _square = _spot(scene, subject)
    return observer.apply_effect(ActiveEffect(
        name=f"senses something unseen", kind="situation",
        key=f"knows-near:{subject.ref}", source=f"{PERCEPTION_ORIGIN}:{subject.ref}",
        origin=PERCEPTION_ORIGIN, duration="until-dismissed",
        tags=(near_tag(subject.ref),), payload={"at": at}))


def forget_one(observer, subject_ref_or_actor, *, near: bool = False) -> list:
    ref = getattr(subject_ref_or_actor, "ref", subject_ref_or_actor)
    tags = {where_tag(ref)} | ({near_tag(ref)} if near else set())
    return observer.remove_effects(kind="situation",
                                   match=lambda e: bool(tags & set(e.tags or ())))


def check(engine, observer, subject, *, searching: bool = False) -> dict | None:
    """One Perception check by `observer` against `subject`'s hiding, rolled by the
    engine (hidden — the player never sees a guard's die), its answer applied to the
    observer through the one applicator. None when there is nothing to roll: the observer
    cannot perceive, already sees or has pinpointed the subject, or it is out of range.

    Returns {"rolls": [...], "effects": [...], "tell": str, "found": "where"|"near"|""}.
    The tell is said only for what was found — a failure changes nothing, and is told
    to the narrator by the brief instead (`brief_line`)."""
    scene = engine.scene
    if not can_perceive(observer) or sees(scene, observer, subject) \
            or knows_where(scene, observer, subject):
        return None
    notice, pin, why = notice_dcs(scene, observer, subject)
    if notice is None:
        return None
    try:
        mods = list(observer.skill_modifiers("perception"))
    except Exception:  # noqa: BLE001 — a body with no sheet notices with its d20 alone
        mods = []
    roll = engine.dice.d20(mods, label=f"{observer.name} Perception"
                           + (" (searching)" if searching else ""), visibility="hidden")
    out = judge(scene, observer, subject, roll.total, searching=searching)
    out["rolls"] = [roll.as_dict()]
    return out


def judge(scene, observer, subject, total: int, *, searching: bool = False) -> dict:
    """What a Perception result of `total` finds of `subject`, applied to `observer`
    through the one applicator — the half of `check` after the die, shared with the
    player's own roll (`Engine._player_finds`), which the player throws themselves.

    Returns {"rolls": [], "effects": [...], "tell": str, "found": "where"|"near"|""}."""
    out = {"rolls": [], "effects": [], "tell": "", "found": ""}
    if not can_perceive(observer) or sees(scene, observer, subject) \
            or knows_where(scene, observer, subject):
        return out
    notice, pin, _why = notice_dcs(scene, observer, subject)
    if notice is None:
        return out
    subject_word = "you" if subject.is_pc else subject.name
    if total >= pin:
        pinpoint(scene, observer, subject, "searched" if searching else "noticed")
        out["found"] = "where"
        out["effects"].append({"kind": "knows_where", "ref": observer.ref,
                               "of": subject.ref, "origin": PERCEPTION_ORIGIN})
        out["tell"] = (f"{observer.name} finds where {subject_word} "
                       f"{'are' if subject.is_pc else 'is'}." if searching else
                       f"{observer.name} fixes on where {subject_word} "
                       f"{'are' if subject.is_pc else 'is'} standing.")
    elif total >= notice and pin != notice and not has_hunch(observer, subject):
        hunch(scene, observer, subject)
        out["found"] = "near"
        out["effects"].append({"kind": "knows_near", "ref": observer.ref,
                               "of": subject.ref, "origin": PERCEPTION_ORIGIN})
        out["tell"] = (f"{observer.name} senses something unseen close by, "
                       f"and cannot tell where.")
    elif searching:
        out["tell"] = (f"{observer.name} searches for whoever is hidden here and finds "
                       f"nothing.")
    return out


def moved_away(scene, subject) -> list[str]:
    """The subject moved: every pinpoint on it is spent. Returns who lost track, by name.

    `knows_where` already answers "no" for a stale square; this takes the stale records
    away so they cannot be told as current, and names them for the tell."""
    lost = []
    for a in list((getattr(scene, "people", None) or getattr(scene, "actors", {})).values()):
        if a is subject:
            continue
        tag = where_tag(subject.ref)
        if any(tag in (e.tags or ()) for e in a.effects):
            if not knows_where(scene, a, subject):
                forget_one(a, subject)
                lost.append(a.name)
    return lost


def sweep(scene) -> None:
    """Take away every `knows.*` whose subject is no longer hidden or no longer here.
    Silent: what ended the hiding was told by its own door."""
    actors = getattr(scene, "people", None) or getattr(scene, "actors", {})
    hidden = {r for r, a in actors.items() if a.has_state(HIDDEN)}
    here = set(getattr(scene, "actors", {}) or {})
    for a in list(actors.values()):
        def stale(e) -> bool:
            for t in e.tags or ():
                t = str(t)
                for root in (KNOWS_WHERE, KNOWS_NEAR):
                    if t.startswith(root + "."):
                        ref = t[len(root) + 1:]
                        return ref not in hidden or ref not in here
            return False
        a.remove_effects(kind="situation", match=stale)


def brief_line(scene, observer, subject) -> str:
    """What the creature's turn prompt is told about a subject it cannot see, plainly.
    "" when it can see them."""
    if sees(scene, observer, subject):
        return ""
    name = "the player's character" if subject.is_pc else subject.name
    how = ("invisible" if subject.has_state(INVISIBLE) and not sees_invisible(observer)
           else "hidden")
    if knows_where(scene, observer, subject):
        return (f"{observer.name} cannot see {name} ({how}), but knows the square they "
                f"are in: it may attack them there, and invisibility still makes half its "
                f"blows miss.")
    hunch_ = has_hunch(observer, subject)
    sensed = " It senses something unseen close by, and cannot tell where." if hunch_ else ""
    # The blind swing only on a hunch, as the engine allows it (`_guess_square`).
    swing = (f"swing blind at where it guesses they are ({guess_fix(observer.ref)}), "
             if hunch_ else "")
    return (f"{observer.name} cannot see {name}: they are {how}, and {observer.name} does "
            f"not know where they are.{sensed} It cannot attack them, cast at them or use an "
            f"ability on them by name, and cannot describe them. It may search (a "
            f"Perception check: {search_fix(observer.ref)}), "
            f"{swing}deal with somebody it can see, or wait.")


# The two things a creature can do about somebody it cannot find, as the JSON its turn copies
# — with its own ref as the actor. Measured live 2026-10-30: shown without one, gemma copied
# the line as written and the first attempt of both raiders' turns was refused for "unknown
# actor None", a retry each.
def search_fix(ref: str) -> str:
    return (f'{{"op": "check", "actor": "{ref}", '
            f'"params": {{"skill": "perception", "search": true}}}}')


def guess_fix(ref: str) -> str:
    return f'{{"op": "attack", "actor": "{ref}", "params": {{"guess": true}}}}'


__all__ = ["HIDDEN", "INVISIBLE", "SNEAKING", "SNEAKING_KEY", "KNOWS_WHERE", "KNOWS_NEAR",
           "STEALTH_ORIGIN", "PERCEPTION_ORIGIN", "ENDS_ON_ATTACK", "SNIPING_PENALTY",
           "SNIPE_FROM_FT", "where_tag", "near_tag", "sees", "locates", "knows_where",
           "has_hunch", "sneaking", "stealth_result", "sees_invisible", "can_perceive",
           "note_motion", "note_loud", "motion", "loud", "invisible_stealth",
           "notice_dcs", "pinpoint", "hunch", "forget_one", "check", "judge", "moved_away",
           "INVISIBLE_DC", "group_of", "one_sphere",
           "sweep", "brief_line", "unseen_by", "search_fix", "guess_fix"]
