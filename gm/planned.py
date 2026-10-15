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

A reply slot is judged as it is written by the registered `narration-in-quotes` check and
asked once more if it fails (`write(check=…)`): measured on the first live planned beat
(2026-10-10), the master of the market answered in the third person ("…the master of the
market maintains the order…") and the check, run on the page, cut the whole answer.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field

from . import client, prompts
from . import narration as narration_mod

# The grammar ceiling of each slot, in characters. The bench's numbers; a fact slot grows
# by `FACT_EACH` for every further tell in its act, up to `FACT_CEILING`.
STILL_MAX = 260
FACT_MAX = 480
FACT_EACH = 160
FACT_CEILING = 900
DOING_MAX = 360
KEEPS_MAX = 360
MATTER_MAX = 320
REPLY_MAX = 560
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
    return groups


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

def build_plan(engine, player_input: str, outcomes, *, pull: str = "",
               last_beat: str = "") -> list[dict]:
    """The ordered slots, v2 (the module note). `last_beat` is the beat before this one;
    with none, or on an arrival, there is no "still" slot."""
    slots: list[dict] = []
    carry_on = player_input == prompts.CARRY_ON
    if last_beat and not arriving(outcomes):
        slots.append({
            "key": "still", "max": STILL_MAX,
            "say": "Whatever was going on at the end of the last thing you wrote is still "
                   "going on. One sentence on where it stands now, in new words, changing "
                   "nothing about it. Never reuse a phrase from the last thing you wrote."})
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
                      "max": min(FACT_CEILING, FACT_MAX + FACT_EACH * (len(tells) - 1)),
                      "say": say, "tells": tells})
    if not any(s["key"].startswith("fact") for s in slots):
        if carry_on:
            # Continue moves the scene (the ruling of 2026-09-18): with no tells, the
            # standing action goes on, as THE SCENE NOW says it.
            slots.append({"key": "keeps", "max": KEEPS_MAX,
                          "say": "The player's character keeps on with what they were "
                                 "doing, as THE SCENE NOW says: show the next moment of it. "
                                 "Nothing new happens that the engine did not decide."})
        else:
            slots.append({"key": "doing", "max": DOING_MAX,
                          "say": "The player's character does what the player said: "
                                 f'"{player_input}". Show exactly that, in the place they '
                                 "are. Nothing more."})
    if pull:
        slots.append({"key": "matter", "max": MATTER_MAX,
                      "say": "The engine keeps this matter open; let it touch the scene "
                             "in a sentence, as it says: " + " ".join(pull.split())[:600]})
    people = [p for p in present(engine) if p["can_answer"]]
    if people and not engine.scene.in_encounter:
        names = ", ".join(f'{p["name"]} ({p["ref"]})' for p in people)
        slots.append({
            "key": "reply", "max": REPLY_MAX,
            "say": "If the player spoke to or asked one of the people here "
                   f"({names}), that ONE person answers, in their own voice, as "
                   "themselves (\"I\", never their own name or title), only from what THE "
                   "SCENE says they know; if THE SCENE does not say, they do not know and "
                   "say so. Put what they say inside <say who=REF to=you>'…'</say>, REF "
                   "being their ref, with a few words of how they say it. If the player "
                   "spoke to nobody, one of them goes on with what they were already "
                   "doing."})
    return slots


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


def slot_messages(plan: list[dict], slots: list[dict], i: int, written: list[str], *,
                  suggest: bool = False, redo: str = "") -> list[dict]:
    """The call for slot `i`: the plan, what is already written, and this slot alone."""
    so_far = " ".join(w for w in written if w)
    s = slots[i]
    ask = (plan[1]["content"]
           + ("\n\nWRITTEN SO FAR (do not repeat any of it; carry straight on from it):\n"
              + so_far if so_far else "")
           + f'\n\nNow write slot {i + 1}, "{s["key"]}", and only that slot: {s["say"]}'
           + (f"\n\n{redo}" if redo else "")
           + ('\nReply with a JSON object: {"text": "...", "suggestions": ["...", "..."]} '
              '— "suggestions" being two or three short things the player might do next.'
              if suggest else '\nReply with a JSON object: {"text": "..."}.'))
    return [plan[0], {"role": "user", "content": ask}]


def slot_schema(max_chars: int, *, suggest: bool = False) -> dict:
    props: dict = {"text": {"type": "string",
                            "maxLength": min(int(max_chars),
                                             prompts.GRAMMAR_MAXLENGTH_CEILING)}}
    if suggest:
        props["suggestions"] = {"type": "array", "items": {"type": "string"}}
    return {"type": "object", "properties": props, "required": ["text"]}


def copied_from(text: str, last_beat: str, n: int = COPY_RUN) -> list[str]:
    """The `n`-word runs `text` shares with `last_beat`, as phrases. Flaw (a)'s detector."""
    if not text or not last_beat:
        return []
    shared = narration_mod._ngrams(text, n) & narration_mod._ngrams(last_beat, n)
    return sorted(" ".join(g) for g in shared)


def _fit(text: str, max_chars: int) -> str:
    """A hosted provider ignores the grammar's `maxLength`: a slot that ran long is cut
    back to its last whole sentence inside the ceiling (or kept whole if it has none)."""
    if len(text) <= max_chars * 1.25:
        return text
    kept, out = 0, []
    for s in narration_mod._sentences(text):
        if kept + len(s) > max_chars and out:
            break
        out.append(s)
        kept += len(s) + 1
    return " ".join(out)


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
          pull: str = "", claim: str = "", lift=None, check=None) -> Planned:
    """Plan the beat and write it slot by slot. `who` is (model, host, provider, key) —
    the prose role's, so a hosted narrator writes planned beats too. `last_beat` is the
    beat before as the model is shown it (speaker tags back on); `last_plain` the same
    beat as the page has it, for the copy check. `lift` takes a slot's speaker tags out
    (`GMAgent._lift`). `check(key, text)` returns what is wrong with a slot as written, or
    "": the slot is asked once more with that named (the house's shape — detect in code,
    repair only what was found), and kept either way, for the pipeline's backstops after.
    Raises `PlanFailed` (or the client's own error) when a slot call
    fails or comes back empty: the caller hands the beat to the free narrator."""
    model, host, provider, key = who
    slots = build_plan(engine, player_input, outcomes, pull=pull, last_beat=last_beat)
    people = present(engine)
    plan = plan_messages(brief, slots, people, _place(engine), last_beat=last_beat,
                         since=since, scene_now=scene_now, claim=claim)
    out = Planned(text="", slots=[], messages=plan, model=model)
    try:
        _write_slots(out, plan, slots, who, last_plain or last_beat, lift, check)
    except Exception as exc:
        # The calls made before the failure, for the turn log beside the free beat.
        exc.calls = list(out.calls)
        raise
    out.text = " ".join(s["wrote"] for s in out.slots if s.get("wrote")).strip()
    if not out.text:
        raise PlanFailed("every slot came back empty")
    return out


def _write_slots(out: Planned, plan, slots, who, last: str, lift, check=None) -> None:
    written: list[str] = []
    for i, s in enumerate(slots):
        final = i == len(slots) - 1
        text, data = _ask(out, plan, slots, i, written, who, suggest=final, lift=lift)
        if s["key"] == "still":
            copied = copied_from(text, last)
            if copied:
                # Named, once: the words it took from the last beat. Then dropped, if it
                # takes them again — the slot changes nothing by definition.
                named = "; ".join(f'"{c}"' for c in copied[:4])
                text, data = _ask(out, plan, slots, i, written, who, lift=lift,
                                  redo=f"You wrote: {text!r}. It reuses words from the last "
                                       f"thing you wrote ({named}). Write it again in "
                                       f"entirely new words.")
                again = copied_from(text, last)
                out.calls[-1]["note"] = ("copy named" + (" — still copied, dropped"
                                                         if again else ""))
                if again:
                    out.notes.append(f"the still slot copied the last beat twice "
                                     f"({'; '.join(again[:3])}): dropped")
                    out.slots.append({**s, "wrote": "", "dropped": True})
                    continue
                out.notes.append("the still slot copied the last beat: asked again, "
                                 "in new words")
        wrong = check(s["key"], text) if check is not None else ""
        if wrong:
            text, data2 = _ask(out, plan, slots, i, written, who, suggest=final, lift=lift,
                               redo=f"You wrote: {text!r}. {wrong} Write it again, fixed.")
            data = data2 if final else data
            again = check(s["key"], text)
            out.calls[-1]["note"] = "fault named" + (" — still there" if again else "")
            out.notes.append(f'the "{s["key"]}" slot: {wrong} — asked again'
                             + (", still there" if again else ", fixed"))
        if final:
            from .agent import _suggestions

            out.suggestions = _suggestions(data)
        written.append(text)
        out.slots.append({**s, "wrote": text})


def _ask(out: Planned, plan, slots, i, written, who, *, suggest: bool = False,
         redo: str = "", lift=None) -> tuple[str, dict]:
    model, host, provider, key = who
    s = slots[i]
    messages = slot_messages(plan, slots, i, written, suggest=suggest, redo=redo)
    started = time.monotonic()
    reply = None
    try:
        reply = client.chat(messages, model, host, as_json=True, think=False,
                            temperature=0.8, num_predict=max(200, s["max"] // 2 + 120),
                            provider=provider, api_key=key,
                            schema=slot_schema(s["max"], suggest=suggest))
        data = reply.json()
    except Exception as exc:
        out.calls.append({"key": s["key"], "messages": messages,
                          "raw": getattr(reply, "text", "") or "",
                          "seconds": round(time.monotonic() - started, 1), "model": model,
                          "note": f"failed: {type(exc).__name__}: {str(exc)[:160]}"})
        if isinstance(exc, client.ModelStalled):
            raise
        raise PlanFailed(f'slot "{s["key"]}": {type(exc).__name__}: '
                         f"{str(exc)[:160]}") from exc
    text = " ".join(str(data.get("text", "") or "").split())
    if lift is not None:
        text = lift(text)
    text = _unwrap_quotes(_fit(text, s["max"]))
    out.calls.append({"key": s["key"], "messages": messages, "raw": reply.text,
                      "seconds": round(reply.seconds, 1), "model": reply.model or model,
                      "note": ""})
    if not text:
        raise PlanFailed(f'slot "{s["key"]}" came back empty')
    return text, data
