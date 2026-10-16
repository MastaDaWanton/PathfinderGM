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
SLOT_FLOOR = 110
# Which slots go first when the budget is short: the acts are the beat (never dropped), the
# answer to the player's own question next, then the state, the open matter, and somebody
# going on with their business. Agenda-style priorities over content to be said, the shape
# planners have used for length control since Hovy's PAULINE ("Controlling a Language
# Generation Planner", IJCAI 1989); the alternative — every slot shortened in proportion —
# was rejected because a slot squeezed below a sentence is a fragment, and the rule here
# is that no sentence is ever cut mid-way.
PRIORITY = {"fact": 0, "doing": 0, "keeps": 0, "reply": 1, "still": 2, "matter": 3,
            "aside": 4}
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


# --- the plan --------------------------------------------------------------------------

def _talk_only(outcomes) -> bool:
    """Whether everything the engine decided this turn was talk (or nothing at all)."""
    talk = _FAMILIES[0] | {"narrate_only"}
    return all(getattr(o, "op", "") in talk for o in outcomes or []
               if getattr(o, "tell", ""))


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


def build_plan(engine, player_input: str, outcomes, *, pull: str = "",
               last_beat: str = "") -> list[dict]:
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
    # when the engine decided a deed of the body (a blow, a step, a take); on a talk turn
    # or an idle one it says how things stand, as a state from THE SCENE NOW, with the
    # last beat as reference only.
    if last_beat and not fighting and not arriving(outcomes) and _talk_only(outcomes):
        slots.append({
            "key": "still", "want": STILL_WANT,
            "say": "How things stand now, in one short sentence, from THE SCENE NOW and the "
                   "last thing you wrote: who is where, what someone holds, or what is "
                   "still unresolved. A state, not an event: nobody moves, speaks, strikes "
                   "or does anything in it. In new words; never reuse a phrase from the "
                   "last thing you wrote."})
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
        if i == 0 and not carry_on:
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
        else:
            slots.append({"key": "doing", "want": DOING_WANT,
                          "say": "The player's character does what the player said: "
                                 f'"{player_input}". Show exactly that, in the place they '
                                 "are. Nothing more."})
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
        speaker = next((p for p in people if p["ref"] == who), None)
        if speaker is not None:
            slots.append({
                "key": "reply", "want": REPLY_WANT, "speaker": speaker["ref"],
                "speaker_name": speaker["name"],
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


def _reply_ask() -> str:
    return ('Reply with a JSON object: {"words": "...", "manner": "..."} — "words" being '
            'exactly what they say, without quote marks, and "manner" a few words that '
            "follow 'says,' to show how: what they do or how they sound as they say it "
            "(for example 'without looking up from the anvil'), or \"\" for nothing.")


def slot_messages(plan: list[dict], slots: list[dict], i: int, written: list[str], *,
                  suggest: bool = False, redo: str = "") -> list[dict]:
    """The call for slot `i`: the plan, what is already written, and this slot alone."""
    so_far = " ".join(w for w in written if w)
    s = slots[i]
    size = (f" About {s['max']} characters at most: one or two sentences."
            if s.get("max") else "")
    shape = (_reply_ask() if s["key"] == "reply"
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


def slot_schema(max_chars: int, *, suggest: bool = False, reply: bool = False) -> dict:
    room = min(int(max_chars * GRAMMAR_ROOM) if max_chars else prompts.GRAMMAR_MAXLENGTH_CEILING,
               prompts.GRAMMAR_MAXLENGTH_CEILING)
    if reply:
        props: dict = {"words": {"type": "string", "maxLength": room},
                       "manner": {"type": "string", "maxLength": 80}}
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
    other than "said" to carry dialogue), and a fixed verb means the composed line is
    grammatical whatever the model put in `manner` — which only ever follows "says,".
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
    manner = " ".join(str(manner or "").split()).strip().rstrip(".,;:")
    manner = manner[:1].lower() + manner[1:]
    who = narration_mod.definite(str(slot.get("speaker_name") or ""))
    return (f"<say who={slot.get('speaker')} to=you>'{words}'</say> {who} says"
            + (f", {manner}" if manner else "") + ".")


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
          budget: int | None = None) -> Planned:
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
        build_plan(engine, player_input, outcomes, pull=pull, last_beat=last_beat), budget)
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
                                           reply=s["key"] == "reply" and bool(s.get("speaker"))))
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
    out, done = [], set()
    for x, n in zip(sentences, owner):
        if n in new:
            if n not in done:
                out.append(new[n])
                done.add(n)
            continue
        out.append(x)
    # A slot asked again whose sentences no longer stand on the page at all goes where
    # its order puts it: before the first sentence of a later slot.
    for n in sorted(set(new) - done):
        later = next((k for k, o in enumerate(owner) if o is not None and o > n), None)
        if later is None:
            out.append(new[n])
        else:
            out.insert(later, new[n])
    return (" ".join(x for x in out if x).strip(), calls, spent,
            {s["key"]: new.get(n, s["wrote"]) for n, s in enumerate(slots)})
