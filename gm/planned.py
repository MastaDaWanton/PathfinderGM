"""Planned narration: the engine lays the beat out, and the narrator writes one slot at a time.

The owner's switch (2026-10-10, "build the switch"): Settings → Narration, Free or Planned
(`houserules.narration()`). Free is the narrator as it has always written — one call, the
whole beat, the scene and the tells in front of it. Planned is this module.

**What was measured** (2026-10-09, three live runs on the owner's gemma-4-12B heretic, every
beat hand-scored against the engine's facts; the bench is the prototype `plan_bench2.py`):

    free narrator:  ~10 errors in 12 town beats, ~8 in 10 conversation beats, ~8-9 in 8
                    fight beats — invented people (an apprentice, a gate guard, a lone
                    rider), invented inns and institutions, a whole window escape written
                    when the engine said only "battle is joined", a beat pasted verbatim
                    as the answer to a new question;
    planned, slots realised one at a time:  ~4 / 12, ~3 / 10, ~2 / 8.

Planned beats ran 380-580 characters against 620-1150, and 5-9 s against ~25 s. The cost
is plainer prose with less colour, and people who are evasive where the world holds no
answer for them. Both halves go in the setting's help text.

**How it was done before.** This is the content-plan-then-realise shape of the classical
NLG pipeline (Reiter & Dale, *Building Natural Language Generation Systems*, 2000:
document planning, microplanning, realisation), with the plan given to a language model
as Narayan et al.'s question-answer *blueprint* (Conditional Generation with a QA
Blueprint, TACL 2023; Text-Blueprint, EACL 2023 demo). Their iterative variant — each
span written against the plan and what is already written — is the one used here: in the
bench it beat writing every slot in one call, which answered the five-factions way
(CLAUDE.md: a model asked for N things answers in parallel).

**The slots** (v2, from the bench's first run):

  * ``still`` — where the last beat's situation stands, changing nothing. Omitted on an
    arrival and when there is no last beat.
  * one slot per ACT the engine decided, the player's own line riding on the FIRST (a
    separate ``doing`` slot only when the engine decided nothing). The player's line and the
    tell each had a slot in the first run and said the same thing twice.
  * ``matter`` — the open matter (`cards.thread_to_pull`), when there is one.
  * ``reply`` — out of fights only: ONE person present answers, only from what the scene
    says they know, or says they do not know.
  * no closing slot: it came back as "…stretches out before you" on every beat.

**An act, not a tell** (flaw (b) of the bench): a goodbye came as three tells — leave
Jarek, leave Arinthal, speak to Jarek — and gave three farewell sentences. Tells are
aggregated before they become slots, which is the classical pipeline's own answer to
repetitive messages (Reiter & Dale's *aggregation*, a microplanning step: messages that
share a participant or an act become one sentence). The test is the engine's, never the
words: outcomes of one intent, consecutive outcomes of one op, or consecutive outcomes of
one family of ops (`_FAMILIES`: talk; places). Each act is ONE slot, shown every tell in
it, and told they are one moment.

**The "still" slot copies** (flaw (a)): in the bench's two runs, 12 of 16 "still" slots
shared a five-word run with the beat before them and 6 of 16 were near-verbatim (9-20
shared runs). The ask now says new words and never a phrase of the last beat — and that is
an instruction, which CLAUDE.md says will not hold alone. So the copy is detected in code
(`copied_from`, shared five-word runs), the slot is asked once more with the copied words
named, and if it still copies it is dropped: by definition it changes nothing.

Everything after the slots is the pipeline's, the same tail `GMAgent.narrate_turn` runs
over a free draft: the page pass, the deterministic backstops, the targeted sentence
repairs and the hand-back. Not the scene-length floor or the whole-beat polish, which would
write free prose back over the plan — the comment at that tail says why, step by step.

**The rough edges** (the owner, 2026-10-16, "fix the planned narration rough edges"; each
measured before and after on the live model, the numbers where the code is):

  1. the "still" slot restated the last beat's action — a state now, and only on a turn
     whose own act does not move the scene (`build_plan`);
  2. answers with nobody saying them — who answers is the engine's (`addressee`), and the
     line is composed in code (`compose_reply`);
  3. a garbled matter sentence — the matter's fact alone, and the page checks on every
     slot as it is written (`page_fault`);
  4. beats of 900 characters — a budget shared out by priority (`allocate`, `_fit`,
     `_hold_to_budget`);
  5. a remake that came back as free prose — the marked slots asked again (`remake`).

A reply slot is judged as it is written by the registered `narration-in-quotes` check and
asked once more if it fails (`write(check=…)`): measured on the first live planned beat
(2026-10-10), the master of the market answered in the third person ("…the master of the
market maintains the order…") and the check, run on the page, cut the whole answer.
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field

from . import client, prompts
from . import narration as narration_mod

# The beat's budget, in characters, and how it is shared out (rough edge 4, 2026-10-16).
# Measured live on 2026-10-10: the gate beat ran to 900 characters across six slots, every
# slot written to its own generous ceiling. A table GM's beat is a paragraph; the free
# narrator's own fight ceiling (`narration.MAX_COMBAT_CHARS`) is the fight budget here, so
# the two narrators share one sense of how long a fight beat is. Out of fights, 650: the
# bench's planned beats that read best ran 380-580 (2026-10-09), and an arrival or a
# question answered needs a little more than a blow.
BEAT_BUDGET = 650
# What each kind of slot is asked to fill, and the least it is worth writing at all. An act
# grows by `FACT_EACH` for each further tell in it, to `FACT_CEILING`.
FACT_WANT = 220
FACT_EACH = 120
FACT_CEILING = 460
DOING_WANT = 220
KEEPS_WANT = 220
REPLY_WANT = 240
STILL_WANT = 140
MATTER_WANT = 160
ASIDE_WANT = 140
# A blow written from its facts (`blow_facts`): two or three sentences, and a little more
# for each further blow in one act; and the fight's surroundings, one clause.
BLOW_WANT = 300
BLOW_EACH = 100
GROUND_WANT = 120
# What the ground clause looks at (see where `build_plan` asks); None is a beat with no
# ground clause at all, and two of them follow each aspect, so a fight hears its ground on
# one beat in three. "What is underfoot" was asked first and wrote "Beneath your feet are
# heavy wooden tables" on the rerun (the tavern's ground is "tables, benches and a hearth"),
# so the floor is asked for as the floor itself, and last.
_GROUND = ("what already stands about here, walls or furniture or whatever is there", None,
           None, "the light here and what it falls on", None, None,
           "the floor itself, the ground the feet are on", None, None)
SLOT_FLOOR = 110
# Which slots go first when the budget is short: the acts are the beat (never dropped), the
# answer to the player's own question next, then the state, the open matter, and somebody
# going on with their business. Agenda-style priorities over content to be said, the shape
# planners have used for length control since Hovy's PAULINE ("Controlling a Language
# Generation Planner", IJCAI 1989); the alternative — every slot shortened in proportion —
# was rejected because a slot squeezed below a sentence is a fragment, and the rule here
# is that no sentence is ever cut mid-way.
PRIORITY = {"fact": 0, "doing": 0, "keeps": 0, "reply": 1, "still": 2, "ground": 2,
            "matter": 3, "aside": 4}
# The grammar ceiling is held above the asked length, so the sampler never closes the
# string mid-word (item 6, 2026-09-30); the slot is then fitted to whole sentences in code.
GRAMMAR_ROOM = 1.6
# How long a run of words the "still" slot may share with the last beat: five, the length
# at which the bench's shared runs were all copying and none were "the crowd" or "you".
COPY_RUN = 5

# Ops that are one act when they come together. Engine vocabulary, never English: a
# goodbye is `leave_talk` x2 and a `say` (measured, the bench's talk run, beat 10); an
# arrival is `found` and `travel` (the fight run, beat 1 — three sentences on one door).
_FAMILIES = (
    frozenset({"say", "leave_talk", "talk"}),
    frozenset({"found", "travel", "journey", "venture", "call_on"}),
)


# The world's own ops that make somebody or somewhere real for the act that follows them.
_MADE_FOR_THE_ACT = frozenset({"introduce", "spawn", "found"})


class PlanFailed(RuntimeError):
    """A slot call failed or came back empty. The beat goes to the free narrator."""


@dataclass
class Planned:
    """One planned beat: the page, and everything that wrote it."""
    text: str
    slots: list[dict]
    # Every model call, in order: {"key", "messages", "raw", "seconds", "model", "note"}.
    calls: list[dict] = field(default_factory=list)
    # The plan as one prompt — the bytes every slot call opens with — for the training
    # log's `messages` (play/corrections.py).
    messages: list[dict] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    suggestions: list[str] = field(default_factory=list)
    model: str = ""


# --- what the engine decided ---------------------------------------------------------

def arriving(outcomes) -> bool:
    """Whether this turn's travel brought the party somewhere new — read off the travel
    outcome's own biome effect, the same test `views._finish` makes for `already_there`.
    The bench read it off the tell's words ("You are at … now."); this does not."""
    return any(
        getattr(o, "op", "") == "travel" and any(
            e.get("kind") == "biome" and e.get("place") != e.get("was_place")
            for e in (getattr(o, "effects", None) or []))
        for o in outcomes or [])


def _family(op: str):
    return next((f for f in _FAMILIES if op in f), None)


def _one_intent(a: str, b: str) -> bool:
    """Whether two outcomes came of one intent: the same id, or one the engine derived
    from the other (`Engine` writes the step a blow needs as "<id>-close"). Measured on the
    first live planned fight (2026-10-10): "closes 10 ft to strike" (i1-close) and the
    blow (i1) were two slots, and the first already landed "a second blow"."""
    a, b = str(a or ""), str(b or "")
    return bool(a and b) and (a == b or a.startswith(b + "-") or b.startswith(a + "-"))


def acts(outcomes) -> list[list]:
    """The outcomes that carry a tell, aggregated into acts (flaw (b), the module note):
    one intent, or consecutive outcomes of one op, or of one family of ops."""
    groups: list[list] = []
    for o in outcomes or []:
        if not getattr(o, "tell", ""):
            continue
        if groups:
            last = groups[-1][-1]
            same_intent = _one_intent(o.intent_id, last.intent_id)
            fam = _family(o.op)
            if same_intent or o.op == last.op or (fam is not None and last.op in fam):
                groups[-1].append(o)
                continue
        groups.append([o])
    # A person or place the world made for the act after it is part of that act: measured
    # live 2026-10-10, "I find whoever keeps watch on the gate and ask them…" came as
    # `introduce` (the guard) then `say`, the player's line rode the introduce slot, and
    # the say slot asked the same question again in the next sentence.
    merged: list[list] = []
    carry: list = []
    for g in groups:
        if all(getattr(o, "op", "") in _MADE_FOR_THE_ACT for o in g):
            carry += g
            continue
        merged.append(carry + g)
        carry = []
    if carry:
        merged.append(carry)
    return merged


def present(engine) -> list[dict]:
    """Everyone here but the player, as the plan names them: ref, name, and what they are
    — down, dead, and their people said as a people, never as a name."""
    from rules import faces

    out = []
    for ref, a in engine.scene.actors.items():
        if a.is_pc or not a.name or a.has_state("state.hidden"):
            continue
        what = []
        dead = a.has_state("state.down.dead") or a.hp < 0
        if dead:
            what.append("dead")
        elif a.is_down:
            what.append("down")
        people = faces.people_of(str(getattr(a, "appearance", "") or ""))
        if people:
            what.append(f"one of the {people} people; {people} is their people, not "
                        f"their name")
        out.append({"ref": ref, "name": a.name, "what": ", ".join(what),
                    "can_answer": not dead and not a.is_down})
    return out


def _place(engine) -> str:
    try:
        here = engine.here()
        return str(getattr(here, "name", "") or getattr(here, "id", "") or "")
    except Exception:  # noqa: BLE001 — a scene with no place still has a beat
        return ""


# --- the blow, from the engine (planned fights, 2026-10-16) ----------------------------------
#
# The owner: "make planned narration fights less plain". Measured on the 2026-10-16 fight
# benches: planned fight beats were accurate (5 errors in 21) and one sentence long, 120-190
# characters, because the slot was handed a tell ("Kesst Vayr hits the guard for 5 non-lethal
# bludgeoning") and told "show it", and a model told nothing more says nothing more.
#
# The colour comes from what the engine knows, so it cannot add an error. How the traditions
# do it, and what was taken:
#   * DikuMUD's descendants (tbaMUD `fight.c`, `dam_message`): a table of nine messages
#     chosen by damage — "misses", up to "OBLITERATES". Taken: a severity tier per blow.
#     Not taken: tbaMUD's thresholds are ABSOLUTE damage (dam <= 2, <= 4 … > 23), so the same
#     blow reads the same against a rat and a dragon; here the tier is the damage against the
#     target's own maximum hit points.
#   * Dungeon Crawl Stone Soup (`attack.cc`): punctuation scaled by damage, and how a miss
#     missed scaled by the margin (`evasion_margin_adverb`: "barely", "closely",
#     "completely"); monsters described by wound level. Taken: the miss told by its margin,
#     and the target's condition after the blow as a band.
#   * Dwarf Fortress: every layer of every body part, weapon and material in the log. Not
#     taken: the log runs to pages and players report scrolling and missing what mattered;
#     the engine here holds no body parts, and inventing one would be the error this avoids.
# I could not confirm DCSS's exact wound thresholds from its source (`mons_get_damage_level`
# is not in the files I could read); the bands are this game's own. They are computed by
# the ENGINE as each swing falls (`rules.engine.blow_severity`, `left_after`, `miss_how`)
# and carried on `Outcome.blows`, the tell's structured twin — the third law's own answer
# ("if the narrator needs a fact, the fact becomes part of a tell"): this reads no effect,
# roll or AC, only the engine's words for them.
#
# Every phrase is ours and comes in three wordings, walked least-recently-used
# (`narration.least_recently_used`, the anchors' and death lines' rule), because a model
# shown "dryly" writes "dryly" nine beats in nine (the talk bench, 2026-10-16).

# The engine's bands (`rules.engine.blow_severity`, `left_after`, `miss_how`, carried on
# `Outcome.blows`), each in three wordings.
_SEVERITY = {
    "glancing": ("a glancing blow that barely bites", "a light touch, more sting than wound",
                 "a scrape of a blow"),
    "solid": ("a solid blow that lands true", "a clean strike with real weight behind it",
              "a hit that tells"),
    "heavy": ("a heavy blow that rocks them", "a hard strike that drives deep",
              "a punishing hit"),
    "brutal": ("a brutal blow that could end it", "a savage strike that tears into them",
               "a devastating hit"),
}
_NONLETHAL = ("it bruises and stuns rather than cuts", "it hurts without drawing blood",
              "a blow meant to drop them, not to kill")
_LEFT = {
    "marked": ("barely marked", "hardly touched", "still fresh"),
    "hurt": ("hurt but steady", "marked but still sure on their feet",
             "wounded, still dangerous"),
    "bloodied": ("bloodied", "hurt and slowing", "badly marked"),
    "badly hurt": ("badly hurt, barely holding on", "staggering under it",
                   "close to falling"),
    "shaken": ("shaken by it", "rattled", "blinking it away"),
    "reeling": ("reeling", "unsteady on their feet", "swaying, close to dropping"),
    "staggering": ("staggering, all but out", "barely upright", "one more and they drop"),
    "down": ("down",),
    "dead": ("dead",),
}
_MISS = {
    "wild": ("badly wide, a clumsy miss", "nowhere near, thrown off balance",
             "a wild swing that finds only air"),
    "cover": ("the cover between them takes it", "it strikes the cover instead",
              "it is turned by what stands between them"),
    "close": ("a near thing, only just turned aside", "it grazes past by a finger's width",
              "so close it stirs the air at their ear"),
    "wide": ("well wide of the mark", "it never comes close", "easily avoided"),
    "plain": ("turned aside", "it misses", "it is evaded"),
}


def _pick(said, key: str, pool) -> str:
    return pool[narration_mod.least_recently_used(said, key, len(pool))]


def blow_facts(outcomes, engine, said=None) -> list[str]:
    """Each blow an act struck or missed, as facts the engine holds — never a number.

    Read off `Outcome.blows`, the tell's structured twin the engine writes as each swing
    falls: a hit's weapon and its wound, its severity against the one struck, a confirmed
    critical, how they are left; a miss's kind. The bands are the engine's; this only
    words them, three ways each, least recently used."""
    out: list[str] = []
    for o in outcomes or []:
        for b in getattr(o, "blows", None) or []:
            if b.get("result") == "hit":
                who = engine.scene.actors.get(b.get("ref"))
                name = (narration_mod.definite(str(who.name))
                        if who is not None and not who.is_pc else "you")
                severity = str(b.get("severity") or "solid")
                bits = [f"weapon: {b.get('weapon') or 'a blow'}"
                        + (f" ({b['type']})" if b.get("type") else ""),
                        _pick(said, f"blow:{severity}",
                              _SEVERITY.get(severity, _SEVERITY["solid"]))]
                if b.get("nonlethal"):
                    bits.append(_pick(said, "blow:nonlethal", _NONLETHAL))
                if b.get("critical"):
                    bits.append("a critical: it finds the gap exactly")
                left = str(b.get("left") or "hurt")
                bits.append(f"{name} after it: "
                            + _pick(said, f"blow:left:{left}", _LEFT.get(left, _LEFT["hurt"])))
                out.append("HIT — " + "; ".join(bits))
            elif b.get("result") == "miss":
                how = str(b.get("how") or "plain")
                # The weapon on a miss too: told only "it misses", the consequence call
                # took the wind-up's invented crossbow and wrote "the heavy bolt whistles
                # past" for a swung sap (the 2026-10-16 planned fight bench).
                out.append("MISS — " + (f"weapon: {b['weapon']}; " if b.get("weapon") else "")
                           + _pick(said, f"blow:miss:{how}", _MISS.get(how, _MISS["plain"])))
    return out


# Where a blow's telling begins, one a blow, least recently used. Measured on the 2026-10-16
# fight rerun: with the wind-up gone, 17 of 21 creature beats opened "The figure behind the
# bar lunges forward, swinging a heavy sap" — the ask ("how it is struck, how it lands, how
# the one struck is left") was walked in its own order every time, so every passage had the
# same first clause. The ask's opening is varied instead of asking the model to vary it.
#
# The creature's call only. It was asked of the player's act slot too, and on the live check
# the same day "The rapier lunges forward, delivering a brutal piercing blow that strikes
# deep into the cutpurse" was cut whole by the dead-men-walking backstop: a blow that drops
# its target names someone down, and that cut spares a sentence the player leads ("You…",
# `narration._PLAYER_ACTS`), not one the weapon leads. The player's blows never had the
# refrain — they open on "you" because the player is the one acting.
_OPENING =("the weapon already moving", "the one it is aimed at",
            "the sound it makes", "the instant it ends", "the attacker's footing")


def blow_opening(said=None) -> str:
    """The line that tells a blow passage where to begin (see `_OPENING`).

    It says to name the attacker in the passage. The first wording ("…, not on the
    attacker's name") was read on the live check as leave the name out: the beat never
    named the master of the market on his own turn, and the wrong-actor backstop rewrote
    it."""
    return (f"Begin on {_pick(said, 'blow:opening', _OPENING)}; name the attacker in the "
            "passage, only not as its first words.")


# --- the plan --------------------------------------------------------------------------

def addressee(engine, outcomes) -> str:
    """Who answers the player this beat, decided in code (rough edge 2): the person the
    player's own `say` was put to — the engine wrote it into the effect — or else the one
    person they are in conversation with. "" when nobody was spoken to."""
    pc = engine.scene.pc()
    mine = {"", "pc", getattr(pc, "ref", "pc")}
    for o in outcomes or []:
        for e in getattr(o, "effects", None) or []:
            if e.get("kind") == "said" and str(e.get("who") or "") in mine \
                    and e.get("to") in engine.scene.actors:
                return str(e["to"])
    talking = [a for a in engine.talking_to() if not a.is_pc]
    return talking[0].ref if len(talking) == 1 else ""


def _master_will_not_answer(engine, ref: str, player_input: str) -> bool:
    """Whether `ref` is the market's master and would not hear the player this beat — the
    same test the brief (`gm/brief/market_master.py`) and the check use."""
    from rules import audience, keepers, places

    scene = engine.scene
    master = keepers.master_here(scene)
    if master is None or master.ref != ref:
        return False
    if not places.has_a_master(places.scale_of(str(getattr(scene, "location_id", "") or ""))):
        return False
    from . import interpret

    reading = interpret.reading_of(player_input) if player_input else None
    if isinstance(reading, dict) and reading.get("error"):
        reading = None
    if audience.addressed(scene, master, player_input, reading):
        return False
    pc = scene.pc()
    return not (pc is not None and audience.grounds(scene, master, pc, player_input,
                                                     reading))


def _means_to_go(reading) -> bool:
    """Whether the interpreter's reading of the player's line commits them to going
    somewhere: the model's reading, held to its closed acts. Going, journeying, leaving,
    calling on — not seeking or following, which a beat shows the player doing where
    they stand ("you scan the stalls for bread")."""
    from . import interpret

    if not isinstance(reading, dict) or reading.get("error"):
        return False
    goes = narration_mod._MOVE_ACTS - {"follow"}
    return any(isinstance(a, dict) and a.get("act") in goes and interpret.acting(a)
               for a in reading.get("actions") or ())


def build_plan(engine, player_input: str, outcomes, *, pull: str = "",
               last_beat: str = "", reading=None) -> list[dict]:
    """The ordered slots (the module note), before the budget (`allocate`). `last_beat` is
    the beat before this one; `pull` the open matter's own fact, never an instruction."""
    slots: list[dict] = []
    carry_on = player_input == prompts.CARRY_ON
    fighting = bool(engine.scene.in_encounter)
    # The "still" slot (rough edge 1). Measured 2026-10-10 on the live fight: the slot was
    # asked to say where the last beat's situation stands, the last beat was an action, and
    # it restated the action — "your fist inches from the Korvu's face" before the move
    # that brought the fist there. A state is only worth a sentence when this turn's own
    # act does not move the scene: so never in a fight, never on an arrival, and never
    # when the engine decided anything at all this turn. It was kept on talk turns at
    # first, and the 2026-10-16 talk bench gave the same sentence on 7 of 9 of them ("The
    # tension of the theft remains palpable", "The lingering weight of the theft hangs in
    # the air") — on a turn the engine decided, the act and the answer are the beat. On an
    # idle turn it says how things stand, as a state from THE SCENE NOW, the last beat as
    # reference only.
    if last_beat and not fighting and not any(getattr(o, "tell", "") for o in outcomes or []):
        slots.append({
            "key": "still", "want": STILL_WANT,
            "say": "How things stand now between the people here, in one short sentence, "
                   "from THE SCENE NOW and the last thing you wrote: what someone holds, "
                   "who is watching whom, or what is still unresolved. A state, not an "
                   "event: nobody moves, speaks, strikes or does anything in it, and it "
                   "does not say where the player is. In new words; never reuse a phrase "
                   "from the last thing you wrote."})
    for i, act in enumerate(acts(outcomes)):
        tells = [o.tell for o in act]
        decided = (tells[0] if len(tells) == 1 else
                   "these, which are ONE moment (show them together, once, not one "
                   "sentence each): " + " ".join(f"({n + 1}) {t}"
                                                 for n, t in enumerate(tells)))
        # A fight declared and not yet struck (the engine's `battle_joined` effect, no
        # dice): "show the player doing it" was the slot's own instruction to land the
        # blow. Measured on the first live planned fight (2026-10-10): "I punch the guard
        # in the face" came back "You lunge forward and strike the Korvu guard across the
        # face", the truth pass cut it, and the beat lost the declaration entirely.
        declared = any(e.get("kind") == "battle_joined"
                       for o in act for e in (getattr(o, "effects", None) or []))
        show = ("Show the player squaring up to do it, and stop there: it has not "
                "happened yet, so no blow lands and nobody is hurt." if declared else
                "Show the player doing it and what came of it, once.")
        # Declared, and the engine moved nobody: the player's own line is left out, because
        # its words carry the walk the engine did not make. Measured live 2026-10-16: "I walk
        # over to the packing trader and punch him" came back "You stride toward the packing
        # trader", the refused-move check cut the beat from there, and the page read "You
        # are still at the market." The tell carries the declaration; nobody moves in it.
        moved = any(getattr(o, "op", "") in ("move", "travel") for o in act)
        blows = [] if declared else blow_facts(act, engine,
                                               getattr(engine.scene, "said", None))
        if blows:
            # The blow from what the engine knows (`blow_facts`): the slot writes the
            # strike itself, two or three sentences, and every word of colour has a fact
            # under it. Measured 2026-10-16 before this: fight beats of 120-190
            # characters, "You lunge forward and strike at the Korvu, but your blow fails
            # to connect" — true, and all there was.
            lead = (f'The player said: "{player_input}". ' if i == 0 and not carry_on
                    else "")
            say = (f"{lead}The engine decided this: {decided}\nTHE BLOW (engine facts, "
                   "in order):\n" + "\n".join(f"- {b}" for b in blows)
                   + "\nWrite the blow itself, in two or three sentences, from these facts "
                     "only: how it is struck, how it lands or misses, and how the one struck "
                     "is left. Nothing the facts and THE SCENE do not give, and never a "
                     "number.")
            slots.append({"key": f"fact{i + 1}",
                          "want": min(FACT_CEILING, BLOW_WANT + BLOW_EACH * (len(blows) - 1)),
                          "say": say, "tells": tells})
            continue
        if declared and not moved:
            say = (f"The engine decided this: {decided} Show the player squaring up to "
                   "them from where they stand, and stop there: nobody moves, no blow lands "
                   "and nobody is hurt.")
        elif i == 0 and not carry_on:
            say = (f'The player said: "{player_input}". The engine decided what came of '
                   f"it: {decided} {show}")
        else:
            say = (f"The engine decided this: {decided} "
                   + ("Show it as it happens: no blow lands yet." if declared
                      else "Show it as it happens."))
        slots.append({"key": f"fact{i + 1}",
                      "want": min(FACT_CEILING, FACT_WANT + FACT_EACH * (len(tells) - 1)),
                      "say": say, "tells": tells})
    if not any(s["key"].startswith("fact") for s in slots):
        if carry_on:
            # Continue moves the scene (the ruling of 2026-09-18): with no tells, the
            # standing action goes on, as THE SCENE NOW says it.
            slots.append({"key": "keeps", "want": KEEPS_WANT,
                          "say": "The player's character keeps on with what they were "
                                 "doing, as THE SCENE NOW says: show the next moment of it. "
                                 "Nothing new happens that the engine did not decide."})
        elif _means_to_go(reading):
            # The reading says the player set out to go somewhere, and the engine moved
            # nobody (no tell at all this turn). Measured 2026-10-16, the planned town
            # bench: "I walk back into town" came back "You turn away from the desert and
            # walk back toward the gate" with the party still on the outskirts — the slot
            # showed "exactly that", a walk the engine never made. So the slot is told
            # what the engine decided instead, and the player's words stay out of it.
            slots.append({"key": "doing", "want": DOING_WANT,
                          "say": "The player meant to go somewhere, and the engine moved "
                                 "nobody: they are still where they were. Show them still "
                                 "here, looking where they meant to go, and nothing more: "
                                 "no walking, no arriving."})
        else:
            slots.append({"key": "doing", "want": DOING_WANT,
                          "say": "The player's character does what the player said: "
                                 f'"{player_input}". Show exactly that, in the place they '
                                 "are. Nothing more."})
    if fighting and any(s["key"].startswith("fact") for s in slots):
        # Where the fight is, in one clause, from the brief's own words for the place
        # (UNDERFOOT, HERE): the ground the blows land on. Never a new thing that matters —
        # a weapon to snatch or a door to run for is the engine's to put there. Lowest
        # but one in the fight's budget: the blows come first.
        #
        # One beat in three, one aspect at a time, walked least-recently-used. The first
        # cut asked for "the floor, the light, what already stands about" every beat, and
        # on the 2026-10-16 fight bench the clause came back as the same tables, benches
        # and hearth on every fight beat. Asking for one aspect a beat (and none every
        # fourth) did not cure it: the rerun still named all three on 4 of 5 beats,
        # because a tavern's UNDERFOOT is that one phrase ("tables, benches and a hearth")
        # and the slot may not invent past it. What varies is how often it is said. A
        # MUD's fight message carries no ground at all; the room is said once on entry.
        focus = _GROUND[narration_mod.least_recently_used(
            getattr(engine.scene, "said", None), "planned.ground", len(_GROUND))]
        if focus:
            slots.append({"key": "ground", "want": GROUND_WANT,
                          "say": "One short sentence of where this fight is happening: "
                                 f"{focus}, from what THE SCENE says is here and nothing "
                                 "else. Nothing new that matters: no new person, weapon, "
                                 "or way out; nobody acts in it."})
    if pull:
        # The engine's fact alone (rough edge 3). It was the pull's whole rendering, whose
        # head is an instruction to the free narrator ("STILL OPEN, NEAREST TO HAND … never
        # to resolve for the player"), and on 2026-10-10 the slot paraphrased the
        # instruction into "…fueled by the fact that and few guards can restrain…".
        slots.append({"key": "matter", "want": MATTER_WANT,
                      "say": "A matter the engine keeps open: " + " ".join(pull.split())[:300]
                             + " Let it touch the scene in one sentence, as a fact, "
                               "without resolving it."})
    people = [p for p in present(engine) if p["can_answer"]]
    if people and not fighting:
        # Who answers is the engine's (rough edge 2): measured live 2026-10-15, "'I have not
        # seen that particular face before today…' What do you do?" — nobody said it. The
        # slot returns the words and how they are said; code writes the speaker in.
        who = addressee(engine, outcomes)
        # The market's master answers only a player who turned to them by the house's own
        # test (`audience.addressed`) or has grounds for a hearing: otherwise every line
        # of theirs is cut on the page (`gm/checks/master_unprompted.py`). Measured on the
        # 2026-10-16 talk bench: the engine's `say` went to the master as the only person
        # in conversation, the reply slot answered as him, and the check cut the answer
        # on 7 of 10 beats. So the slot follows the check: no answer from him then.
        if who and _master_will_not_answer(engine, who, player_input):
            who = ""
        speaker = next((p for p in people if p["ref"] == who), None)
        if speaker is not None:
            # The manner the last beat already gave this speaker, not given again: on the
            # 2026-10-16 talk bench one fishmonger said "dryly" on 9 of 9 beats.
            said_as = narration_mod.definite(speaker["name"]) + " says "
            used = [m for m in MANNERS if m and said_as + m in str(last_beat or "")]
            slots.append({
                "key": "reply", "want": REPLY_WANT, "speaker": speaker["ref"],
                "speaker_name": speaker["name"], **({"not_manner": used} if used else {}),
                "say": f'{speaker["name"]} answers the player, in their own voice, as '
                       "themselves (\"I\", never their own name or title), only from what "
                       "THE SCENE says they know; if THE SCENE does not say, they do not "
                       "know and say so."})
        else:
            names = ", ".join(f'{p["name"]} ({p["ref"]})' for p in people)
            slots.append({"key": "aside", "want": ASIDE_WANT,
                          "say": f"Nobody was spoken to. One of the people here ({names}) "
                                 "goes on with what they were already doing, in one "
                                 "sentence, without speaking."})
    return slots


def budget_for(engine) -> int:
    """The beat's budget: `narration.MAX_COMBAT_CHARS` in a fight, `BEAT_BUDGET` out of it."""
    return narration_mod.MAX_COMBAT_CHARS if engine.scene.in_encounter else BEAT_BUDGET


def allocate(slots: list[dict], budget: int) -> tuple[list[dict], list[str]]:
    """The slots that fit the budget, each given its `max`, and what was dropped.

    The acts and the answer to the player are always written. The rest join in priority order (`PRIORITY`) while what
    they want still fits; a slot that does not fit is dropped whole, never squeezed below a
    sentence (`SLOT_FLOOR`). When the acts alone are over the budget they share it, none
    below the floor — many acts make a long beat, and that is the engine's beat to tell."""
    def prio(s):
        return PRIORITY.get("fact" if s["key"].startswith("fact") else s["key"], 5)

    core = [s for s in slots if prio(s) <= 1]
    need = sum(s["want"] for s in core)
    if need > budget and core:
        scale = budget / need
        for s in core:
            s["want"] = max(SLOT_FLOOR, int(s["want"] * scale))
        need = sum(s["want"] for s in core)
    kept = {id(s) for s in core}
    dropped = []
    for s in sorted((s for s in slots if prio(s) > 1), key=prio):
        if need + s["want"] <= budget:
            kept.add(id(s))
            need += s["want"]
        else:
            dropped.append(s["key"])
    out = []
    for s in slots:
        if id(s) in kept:
            s["max"] = s["want"]
            out.append(s)
    return out, dropped


PLAN_SYSTEM = """You write the prose for one turn of a Pathfinder game. The game engine has \
already decided everything that happens; you only put it into words.

You are given a PLAN of numbered slots. You write the slot you are asked for as one to \
three sentences of vivid, plain prose, second person ("you"), present tense, that shows \
exactly what that slot says and nothing else. The slots are written in order and read as \
one passage.

Hard rules:
- Only the people, places and things named in THE SCENE or in a slot exist. Never add a \
person, a creature, an object, a place, an arrival, a departure, or a sound of someone \
coming.
- Nobody leaves or arrives unless a slot says so. Nobody hands anything over unless a slot \
says so.
- Never write a number, a roll, or how a roll turned out.
- Do not say what the player's character thinks, feels or decides beyond the slot.
- Call each person exactly as PEOPLE HERE names them. A people (Korvu, Orc, Human) is what \
they are, never their name.
- Stop when the slot is written: no closing look at the place, no question to the player.

Reply with the JSON object each request asks for."""


def plan_messages(brief: str, slots: list[dict], people: list[dict], place: str, *,
                  last_beat: str = "", since: list[str] | None = None,
                  scene_now: str = "", claim: str = "") -> list[dict]:
    """The plan as one prompt: [system + the scene, the plan]. Every slot call opens with
    exactly these bytes, so Ollama reuses their cache from the second slot on."""
    scene = f"THE SCENE (reference; the only things that exist):\n{brief}"
    blocks = []
    if last_beat:
        blocks.append("The last thing you wrote. What it shows is still true now unless a "
                      "slot changes it. Do not repeat it, and add no new event to it:\n"
                      + last_beat)
    if since:
        blocks.append("SINCE THEN (engine):\n" + "\n".join(f"- {s}" for s in since if s))
    if place:
        blocks.append(f"WHERE: {place}")
    if people:
        blocks.append("PEOPLE HERE NOW (no one else): " + "; ".join(
            f'{p["name"]} ({p["ref"]}' + (f'; {p["what"]})' if p["what"] else ")")
            for p in people))
    else:
        blocks.append("PEOPLE HERE NOW: nobody but the player's character.")
    if scene_now:
        blocks.append(scene_now.strip())
    if claim:
        blocks.append(claim.strip())
    blocks.append("PLAN:\n" + "\n".join(f'{i + 1}. "{s["key"]}": {s["say"]}'
                                        for i, s in enumerate(slots)))
    return [{"role": "system", "content": PLAN_SYSTEM + "\n\n" + scene},
            {"role": "user", "content": "\n\n".join(b for b in blocks if b)}]


# How an answer is said: one word from a closed set, which Ollama's grammar enforces (an
# enum held on 6 of 6 probes, 2026-10-03; `contains` and `prefixItems` did not), or "" for
# plain "says". It was free text, and of the 9 manners on the 2026-10-16 benches one was a
# second attribution ("the Korvu official says, their voice gravelly…", composed into
# "'…,' the master of the market says, the Korvu official says…") and four were actions
# ("grunting as they adjust a heavy crate"). What a speaker DOES belongs to the act slots;
# how they sound is this word.
MANNERS = ("", "flatly", "quietly", "curtly", "warmly", "wearily", "gruffly", "sharply",
           "slowly", "dryly", "carefully", "coldly", "kindly", "impatiently", "softly")


def _reply_ask(s: dict | None = None) -> str:
    allowed = [m for m in MANNERS if m not in ((s or {}).get("not_manner") or [])]
    return ('Reply with a JSON object: {"words": "...", "manner": "..."} — "words" being '
            'exactly what they say, in their own voice, without quote marks and without '
            'saying who says it; "manner" one word for how they say it, from: '
            + ", ".join(f'"{m}"' for m in allowed) + ".")


def slot_messages(plan: list[dict], slots: list[dict], i: int, written: list[str], *,
                  suggest: bool = False, redo: str = "") -> list[dict]:
    """The call for slot `i`: the plan, what is already written, and this slot alone."""
    so_far = " ".join(w for w in written if w)
    s = slots[i]
    size = (f" About {s['max']} characters at most: one or two sentences."
            if s.get("max") else "")
    shape = (_reply_ask(s) if s["key"] == "reply"
             else 'Reply with a JSON object: {"text": "..."}.')
    if suggest:
        shape = shape.replace('Reply with a JSON object: {', 'Reply with a JSON object: {'
                              '"suggestions": ["...", "..."], ', 1) + (
            ' "suggestions" are two or three short things the player might do next.')
    ask = (plan[1]["content"]
           + ("\n\nWRITTEN SO FAR (do not repeat any of it; carry straight on from it):\n"
              + so_far if so_far else "")
           + f'\n\nNow write slot {i + 1}, "{s["key"]}", and only that slot: {s["say"]}'
           + size
           + (f"\n\n{redo}" if redo else "")
           + "\n" + shape)
    return [plan[0], {"role": "user", "content": ask}]


def slot_schema(max_chars: int, *, suggest: bool = False, reply: bool = False,
                not_manner=()) -> dict:
    room = min(int(max_chars * GRAMMAR_ROOM) if max_chars else prompts.GRAMMAR_MAXLENGTH_CEILING,
               prompts.GRAMMAR_MAXLENGTH_CEILING)
    if reply:
        props: dict = {"words": {"type": "string", "maxLength": room},
                       "manner": {"type": "string",
                                  "enum": [m for m in MANNERS if m not in not_manner]}}
        required = ["words", "manner"]
    else:
        props = {"text": {"type": "string", "maxLength": room}}
        required = ["text"]
    if suggest:
        props["suggestions"] = {"type": "array", "items": {"type": "string"}}
    return {"type": "object", "properties": props, "required": required}


def compose_reply(slot: dict, words: str, manner: str) -> str:
    """The answer as a line of the page, its speaker written in by code (rough edge 2).

    The words are the model's; who says them is the engine's (`addressee`), named by the
    engine's own name, and the verb is "says". "Said" is the one dialogue verb that does
    not draw the eye (Elmore Leonard, "10 Rules of Writing", rule 3: never use a verb
    other than "said" to carry dialogue), and a fixed verb with one word from `MANNERS`
    means the composed line is grammatical whatever the model chose. A manner from outside
    the set (a hosted provider ignores the grammar) is left off.
    The speaker tag goes on, so the line is booked to them exactly as a tagged line is."""
    from . import speech

    words = " ".join(str(words or "").split()).strip()
    if words and speech.spans(words) == [(0, len(words))]:
        words = words[1:-1].strip()
    if not words:
        return ""
    if words[-1] == ".":
        words = words[:-1] + ","
    elif words[-1] not in ",!?…":
        words += ","
    manner = str(manner or "").strip().lower()
    manner = manner if manner in MANNERS and manner not in (
        slot.get("not_manner") or ()) else ""
    who = narration_mod.definite(str(slot.get("speaker_name") or ""))
    return (f"<say who={slot.get('speaker')} to=you>'{words}'</say> {who} says"
            + (f" {manner}" if manner else "") + ".")


def copied_from(text: str, last_beat: str, n: int = COPY_RUN) -> list[str]:
    """The `n`-word runs `text` shares with `last_beat`, as phrases. Flaw (a)'s detector."""
    if not text or not last_beat:
        return []
    shared = narration_mod._ngrams(text, n) & narration_mod._ngrams(last_beat, n)
    return sorted(" ".join(g) for g in shared)


def _fit(text: str, max_chars: int) -> str:
    """A slot that ran past its share is cut back to its last whole sentence inside it,
    and is never cut mid-sentence: the first sentence stays whatever its length. The
    grammar ceiling is held above the share (`GRAMMAR_ROOM`) so it is never what ends the
    slot, and a hosted provider ignores the grammar altogether."""
    if not max_chars or len(text) <= max_chars * 1.15:
        return text
    kept, out = 0, []
    for s in narration_mod._sentences(text):
        if kept + len(s) > max_chars and out:
            break
        out.append(s)
        kept += len(s) + 1
    return " ".join(out)


def page_fault(text: str) -> str:
    """What the house's own page checks find wrong with one slot as written (rough edge 3):
    the schema bled into the prose, or a sentence the grammar or the model left unfinished
    (`narration.cut_schema_bleed`, `narration.ends_unfinished`). "" when it is whole."""
    _, bled = narration_mod.cut_schema_bleed(text)
    if bled:
        return f"Part of the reply's own JSON is in the prose ({bled[0][:40]!r})."
    if narration_mod.ends_unfinished(text):
        return "The last sentence stops before it is finished."
    return ""


# A quotation inside a second pair of quote marks, and nothing else inside them: the model
# put its double quotes round the tag the reply slot asked for (`<say …>'…'</say>`), and
# the page read "'Best? Provisions for the long haul…' " (live, 2026-10-10). Punctuation
# only, found by the one quotation scanner (`speech.spans`, never a second regex): the
# outer pair goes, the speech keeps its own.
def _unwrap_quotes(text: str) -> str:
    from . import speech

    out = str(text or "")
    for a, b in reversed(speech.spans(out)):
        inner = out[a + 1:b - 1].strip()
        if inner and speech.spans(inner) == [(0, len(inner))] and inner[0] != out[a]:
            out = out[:a] + inner + out[b:]
    return out


def write(engine, *, brief: str, outcomes, player_input: str, who: tuple,
          last_beat: str = "", last_plain: str = "", since=None, scene_now: str = "",
          pull: str = "", claim: str = "", lift=None, check=None,
          budget: int | None = None, reading=None) -> Planned:
    """Plan the beat and write it slot by slot. `who` is (model, host, provider, key) —
    the prose role's, so a hosted narrator writes planned beats too. `last_beat` is the
    beat before as the model is shown it (speaker tags back on); `last_plain` the same
    beat as the page has it, for the copy check. `lift` takes a slot's speaker tags out
    (`GMAgent._lift`). `check(key, text)` returns what is wrong with a slot as written, or
    "": the slot is asked once more with that named (the house's shape — detect in code,
    repair only what was found), and kept either way, for the pipeline's backstops after.
    `budget` is the beat's length in characters (`budget_for` when None).
    Raises `PlanFailed` (or the client's own error) when a core slot call fails or comes
    back empty: the caller hands the beat to the free narrator."""
    model, host, provider, key = who
    budget = budget if budget is not None else budget_for(engine)
    slots, dropped = allocate(
        build_plan(engine, player_input, outcomes, pull=pull, last_beat=last_beat,
                   reading=reading), budget)
    people = present(engine)
    plan = plan_messages(brief, slots, people, _place(engine), last_beat=last_beat,
                         since=since, scene_now=scene_now, claim=claim)
    out = Planned(text="", slots=[], messages=plan, model=model)
    if dropped:
        out.notes.append(f"over the {budget}-character budget: no {', '.join(dropped)} slot")
    try:
        _write_slots(out, plan, slots, who, last_plain or last_beat, lift, check)
    except Exception as exc:
        # The calls made before the failure, for the turn log beside the free beat.
        exc.calls = list(out.calls)
        raise
    _hold_to_budget(out, budget)
    out.text = " ".join(s["wrote"] for s in out.slots if s.get("wrote")).strip()
    if not out.text:
        raise PlanFailed("every slot came back empty")
    return out


def _prio(s: dict) -> int:
    return PRIORITY.get("fact" if s["key"].startswith("fact") else s["key"], 5)


def _hold_to_budget(out: Planned, budget: int) -> None:
    """Written over the budget by more than a tenth: the lowest-priority slots go whole,
    lowest first, until it fits or only the acts and the answer are left. Never a cut
    inside a slot — `_fit` already held each to its share at a sentence's end."""
    def total():
        return sum(len(s.get("wrote") or "") + 1 for s in out.slots)

    for s in sorted(out.slots, key=_prio, reverse=True):
        if total() <= budget * 1.1 or _prio(s) <= 1:
            break
        if s.get("wrote"):
            out.notes.append(f'over the {budget}-character budget once written: dropped '
                             f'the "{s["key"]}" slot')
            s["wrote"], s["dropped"] = "", True


def _settle(out: Planned, s: dict, text: str) -> None:
    """The slot as it stands, with the call whose answer stood (for a remake to re-ask)."""
    call = out.calls[-1] if out.calls else {}
    out.slots.append({**s, "wrote": text, "messages": call.get("messages") or [],
                      "reply": call.get("raw") or ""})


def _write_slots(out: Planned, plan, slots, who, last: str, lift, check=None) -> None:
    written: list[str] = []
    for i, s in enumerate(slots):
        final = i == len(slots) - 1
        core = _prio(s) <= 1
        text, data = _ask(out, plan, slots, i, written, who, suggest=final, lift=lift,
                          core=core)
        if not text:
            # Only a slot outside the core can come back empty and live: it is dropped.
            out.notes.append(f'the "{s["key"]}" slot came back empty: dropped')
            out.slots.append({**s, "wrote": "", "dropped": True})
            continue
        if s["key"] == "still":
            copied = copied_from(text, last)
            if copied:
                # Named, once: the words it took from the last beat. Then dropped, if it
                # takes them again — the slot changes nothing by definition.
                named = "; ".join(f'"{c}"' for c in copied[:4])
                text, data = _ask(out, plan, slots, i, written, who, lift=lift, core=False,
                                  redo=f"You wrote: {text!r}. It reuses words from the last "
                                       f"thing you wrote ({named}). Write it again in "
                                       f"entirely new words.")
                again = copied_from(text, last) if text else ["(nothing)"]
                out.calls[-1]["note"] = ("copy named" + (" — still copied, dropped"
                                                         if again else ""))
                if again:
                    out.notes.append(f"the still slot copied the last beat twice "
                                     f"({'; '.join(again[:3])}): dropped")
                    out.slots.append({**s, "wrote": "", "dropped": True})
                    continue
                out.notes.append("the still slot copied the last beat: asked again, "
                                 "in new words")
        # The page's own checks, on the slot as it is written (rough edge 3): asked once
        # more with the fault named; a slot outside the core that is still broken goes,
        # and a core slot is cut back to its last whole sentence.
        fault = page_fault(text)
        if fault:
            text2, data2 = _ask(out, plan, slots, i, written, who, suggest=final, lift=lift,
                                core=core,
                                redo=f"You wrote: {text!r}. {fault} Write it again, whole.")
            again = page_fault(text2) if text2 else fault
            out.calls[-1]["note"] = "page fault named" + (" — still there" if again else "")
            if not again:
                text, data = text2, (data2 if final else data)
                out.notes.append(f'the "{s["key"]}" slot: {fault} — asked again, fixed')
            elif not core:
                out.notes.append(f'the "{s["key"]}" slot: {fault} — asked again, dropped')
                out.slots.append({**s, "wrote": "", "dropped": True})
                continue
            else:
                cut, _bled = narration_mod.cut_schema_bleed(text)
                cut, _gone = narration_mod.trim_unfinished(cut)
                text = cut or text
                out.notes.append(f'the "{s["key"]}" slot: {fault} — cut to whole sentences')
        wrong = check(s["key"], text) if check is not None else ""
        if wrong:
            text2, data2 = _ask(out, plan, slots, i, written, who, suggest=final, lift=lift,
                                core=core,
                                redo=f"You wrote: {text!r}. {wrong} Write it again, fixed.")
            if text2:
                text, data = text2, (data2 if final else data)
            again = check(s["key"], text)
            out.calls[-1]["note"] = "fault named" + (" — still there" if again else "")
            out.notes.append(f'the "{s["key"]}" slot: {wrong} — asked again'
                             + (", still there" if again else ", fixed"))
        if final:
            from .agent import _suggestions

            out.suggestions = _suggestions(data)
        written.append(text)
        _settle(out, s, text)


def realise(s: dict, data: dict, lift=None) -> str:
    """A slot's reply as page text: the prose, or the composed answer (`compose_reply`);
    speaker tags lifted, fitted to the slot's share, doubled quote marks undone."""
    if s["key"] == "reply" and s.get("speaker"):
        text = compose_reply(s, data.get("words", ""), data.get("manner", ""))
    else:
        text = " ".join(str(data.get("text", "") or "").split())
    if lift is not None:
        text = lift(text)
    return _unwrap_quotes(_fit(text, s.get("max") or 0))


def call_slot(s: dict, messages: list[dict], who: tuple, *, suggest: bool = False):
    """One slot call: (reply, data). The one copy of the call, for a beat and a remake."""
    model, host, provider, key = who
    reply = client.chat(messages, model, host, as_json=True, think=False,
                        temperature=0.8,
                        num_predict=max(200, int((s.get("max") or 300) * GRAMMAR_ROOM) // 2
                                        + 120),
                        provider=provider, api_key=key,
                        schema=slot_schema(s.get("max") or 0, suggest=suggest,
                                           reply=s["key"] == "reply" and bool(s.get("speaker")),
                                           not_manner=s.get("not_manner") or ()))
    return reply, reply.json()


def _ask(out: Planned, plan, slots, i, written, who, *, suggest: bool = False,
         redo: str = "", lift=None, core: bool = True) -> tuple[str, dict]:
    model = who[0]
    s = slots[i]
    messages = slot_messages(plan, slots, i, written, suggest=suggest, redo=redo)
    started = time.monotonic()
    reply = None
    try:
        reply, data = call_slot(s, messages, who, suggest=suggest)
    except Exception as exc:
        out.calls.append({"key": s["key"], "messages": messages,
                          "raw": getattr(reply, "text", "") or "",
                          "seconds": round(time.monotonic() - started, 1), "model": model,
                          "note": f"failed: {type(exc).__name__}: {str(exc)[:160]}"})
        if isinstance(exc, client.ModelStalled):
            raise
        if not core:
            return "", {}
        raise PlanFailed(f'slot "{s["key"]}": {type(exc).__name__}: '
                         f"{str(exc)[:160]}") from exc
    text = realise(s, data, lift)
    out.calls.append({"key": s["key"], "messages": messages, "raw": reply.text,
                      "seconds": round(reply.seconds, 1), "model": reply.model or model,
                      "note": ""})
    if not text and core:
        raise PlanFailed(f'slot "{s["key"]}" came back empty')
    return text, data


# --- a remake of a planned beat (rough edge 5) ------------------------------------------

def _same(s: str) -> str:
    return " ".join(str(s or "").split())


def slot_of(sentence: str, slots: list[dict]) -> int | None:
    """Which kept slot wrote this sentence of the page: the slot whose text holds it, or —
    a sentence a backstop touched after — the one sharing the most of its words, if that
    is most of them. None for a sentence no slot wrote (the hand-back, a face line)."""
    want = _same(sentence)
    if not want:
        return None
    for n, s in enumerate(slots):
        if want in _same(s.get("wrote")):
            return n
    words = set(narration_mod._words(want))
    best, share = None, 0.0
    for n, s in enumerate(slots):
        mine = set(narration_mod._words(s.get("wrote") or ""))
        got = len(words & mine) / max(1, len(words))
        if got > share:
            best, share = n, got
    return best if share >= 0.6 else None


def kept_slots(entry: dict, lift=None) -> list[dict]:
    """The slots a planned beat was written from, as "That's wrong" kept them, each with
    its text. An input kept before the slot text was (0.2.16) gives it from the reply."""
    out = []
    for s in entry.get("slots") or []:
        if not isinstance(s, dict) or s.get("dropped"):
            continue
        s = dict(s)
        if not s.get("wrote"):
            try:
                raw = str(s.get("reply") or "")
                data = json.loads(raw[raw.find("{"):raw.rfind("}") + 1]) if "{" in raw else {}
            except ValueError:
                data = {}
            s["wrote"] = realise(s, data, lift) if data else ""
        if s.get("wrote") and s.get("messages"):
            out.append(s)
    return out


def remake(page: str, entry: dict, picked: list[str], complaint: str, who: tuple,
           lift=None, now: dict | None = None) -> tuple[str, list[dict], float, dict]:
    """A planned beat the player marked wrong, remade the planned way: only the slots that
    wrote the sentences they picked are asked again — each its own kept call with the
    player's complaint added — and every other slot's sentences stay on the page exactly
    as they are. Nothing picked: every slot is asked again. Returns (text, the slot calls
    as made, seconds, every slot's text now). `now` is each slot's text as an earlier
    remake left it, so a second remake knows which slot wrote what. Measured 2026-10-15: the remake went through the whole-beat repair
    call and a three-sentence planned miss came back as four sentences of free prose."""
    slots = kept_slots(entry, lift)
    if not slots:
        raise PlanFailed("the beat's slots were not kept")
    for s in slots:
        if (now or {}).get(s["key"]):
            s["wrote"] = now[s["key"]]
    sentences = narration_mod._sentences(page)
    owner = [slot_of(x, slots) for x in sentences]
    marked = {_same(p) for p in picked or []}
    redo = sorted({owner[n] for n, x in enumerate(sentences)
                   if owner[n] is not None and any(m and m in _same(x) for m in marked)})
    if not marked or not redo:
        redo = list(range(len(slots)))
    calls, new, spent = [], {}, 0.0
    for n in redo:
        s = slots[n]
        msgs = [dict(m) for m in s["messages"]]
        msgs[-1]["content"] += (f"\n\nYou wrote: {s['wrote']!r}. {complaint} Write this "
                                f"slot again, fixed, keeping to what the engine decided.")
        started = time.monotonic()
        reply, data = call_slot(s, msgs, who)
        spent += time.monotonic() - started
        text = realise(s, data, lift)
        calls.append({"key": s["key"], "messages": msgs, "reply": reply.text,
                      "model": reply.model or who[0]})
        if not text:
            raise PlanFailed(f'the remade "{s["key"]}" slot came back empty')
        new[n] = text
    now = {s["key"]: new.get(n, s["wrote"]) for n, s in enumerate(slots)}
    if all(o is None for o in owner):
        # Nothing on the page is any slot's any more: what stands is the backstops' alone
        # (measured live 2026-10-16: a refused-move cut left "You are still at the market.
        # What do you do?"). The beat is the slots again, in order; the hand-back is the
        # caller's (`GMAgent.remake_planned`).
        return " ".join(now[s["key"]] for s in slots).strip(), calls, spent, now
    out, done = [], set()
    for x, n in zip(sentences, owner):
        if n in new:
            if n not in done:
                out.append(new[n])
                done.add(n)
            continue
        out.append(x)
    # A slot asked again whose sentences no longer stand on the page at all goes where its
    # order puts it: before the first sentence of a later slot, or else before the closing
    # question — never after it.
    for n in sorted(set(new) - done):
        later = next((k for k, x in enumerate(out)
                      if (owner[sentences.index(x)] if x in sentences else None) is not None
                      and owner[sentences.index(x)] > n), None)
        if later is not None:
            out.insert(later, new[n])
        elif out and out[-1].rstrip().endswith("?"):
            out.insert(len(out) - 1, new[n])
        else:
            out.append(new[n])
    return " ".join(x for x in out if x).strip(), calls, spent, now
