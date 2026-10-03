"""The GM agent: the model-facing half of the intent protocol.

Two calls per mechanical turn and zero for a turn that is only talk. Call 1 is expensive
and carries the world; call 2 is handed a small packet of resolved facts and asked only to
say them well.

Everything the model produces is checked in code before it touches the engine.
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass, field

from django.conf import settings

from rules.intents import (Intent, IntentError, claims_the_engine_backs,
                          cut_outcome_claims, find_outcome_claims)

from . import client, judgement, narration as narration_mod, prompts
from . import intimate as intimate_mod
from . import mentions as mentions_mod
from . import speech as speech_mod


@dataclass
class Attempt:
    """One model call, kept for the log. Play that cannot be audited cannot be
    debugged — and the world clock has to be legible for the same reason."""
    kind: str
    seconds: float
    model: str
    raw: str = ""
    note: str = ""


@dataclass
class TurnPlan:
    narration: str
    intents: list[Intent]
    # Two or three things the player might do. Offered, never enforced: the engine does
    # not read them and the player may type anything at all.
    suggestions: list[str] = field(default_factory=list)
    attempts: list[Attempt] = field(default_factory=list)
    repairs: list[str] = field(default_factory=list)
    rejections: list[str] = field(default_factory=list)
    # A refusal only the PLAYER can fix, when one ended the turn before anything
    # resolved: {"text", "code", "fix"} (docs/fix-interfaces.md §2.6). The view answers
    # it as a 422 — no beat, no clock, no NPC turn. None on every other turn.
    refusal: dict | None = None

    @property
    def seconds(self) -> float:
        return sum(a.seconds for a in self.attempts)


# How long the prose call may wait, by who is being asked. The primary keeps
# `client.chat`'s generous default — a cold load is genuinely slow, and the first turn
# of a session pays it. The FALLBACK does not: measured 2026-09-17 on the first
# sixty-turn run after the narrator guards, the 12B prose call lost the scene, the turn
# was handed to the 4B fallback, and Ollama never answered it — no request line in its
# own log, no error — until the 600-second timeout returned. One turn, ten minutes, while
# the watcher's calls went through the same server the whole time: the hang was the
# model swap under VRAM pressure, not the queue. A rescue that has not arrived in two
# minutes is not a rescue; the floor line is better than the wait.
PRIMARY_TIMEOUT = 600

# The ops a declared entry is the player's character doing, which `_merge_declared` gives
# the PC as actor. The engine refuses these without one (`Engine._check_refs` for check,
# save, attack and move; `_check_cast` for cast). World ops (introduce, found, spawn) are
# not the character's and are left as the model wrote them.
_PLAYERS_OWN = ("check", "save", "attack", "move", "manoeuvre", "cast", "use_item",
                "use_ability")
FALLBACK_TIMEOUT = 120


# The opening of a cast tell: "Ted casts Cure Light Wounds (caster level 1; …)".
_CAST_TELL = re.compile(r"\bcasts ([A-Z][^(.,]*)")


class GMAgent:
    def __init__(self, world, engine, role: str = "narrator"):
        self.world = world
        self.engine = engine
        # From the settings page if the player has set one, from `settings.MODELS`
        # if they have not. Read per agent rather than at import, so changing a model
        # takes effect on the next turn instead of the next restart.
        from play import modelcfg

        cfg = modelcfg.for_role(role)
        self.model = cfg["model"]
        self.host = cfg["host"]
        self.provider = cfg.get("provider", "ollama")
        self.api_key = cfg.get("api_key", "")
        # Call 2 may run on a different model. It writes one or two sentences of prose
        # with no schema to satisfy, which is the half of the job a creative-writing tune
        # is good at and the half where its trouble with structured output cannot bite.
        # Falls back to the narrator, so a config that never heard of this still works.
        prose = modelcfg.for_role("prose") or cfg
        self.prose_model = prose.get("model", self.model)
        self.prose_host = prose.get("host", self.host)
        self.prose_provider = prose.get("provider", self.provider)
        self.prose_key = prose.get("api_key", "")
        self._echoes = None
        # The sentences the pipeline appended to the last beat it produced (a death
        # line, a thread anchor) — ours, not the model's, and kept apart so they are
        # never shown back to it as its own prose.
        self.last_added: list[str] = []
        # Who said which line this turn, from the prose call's own `<say who=…>` tags
        # (`speech.lift`, docs/declared-not-guessed.md). Read by `views._finish` for the
        # hails and the names; reset when a turn is planned.
        self.last_said: list[dict] = []
        # This beat's verdict on the content rule (gm/intimate.py `decide`): set by
        # `narrate_turn`, read by the checks that must not mangle an intimate beat and by
        # the view's turn-log row. Reset when a turn is planned.
        self.intimate = None
        # Who each person-mention in the last groomed beat means (gm/mentions.py,
        # docs/who-the-prose-means.md), and one log row per groomed beat, drained into
        # the turn log by the view.
        self.attribution = None
        self.mention_rows: list[dict] = []
        # The experiment. Off by default and read per agent, so a run can be flipped
        # between turns without a restart — see `prompts.INTENTS_ONLY_EXTRA` for what is
        # being tested and why it is measured rather than argued about.
        # On by default since the player asked for it in as many words: "actors
        # should be at least partially created before I even receive prose back."
        # Call 1 plans ops only, the engine resolves them — spawns included — and
        # the one prose call writes the turn knowing what the dice did and who is
        # actually on the board. GM_INTENTS_FIRST=0 restores the old order.
        self.intents_first = (os.environ.get("GM_INTENTS_FIRST", "1").lower()
                              not in ("", "0", "false", "no"))

    def _undeclared_blows(self, text: str, messages: list, schema: dict):
        """The prose has somebody strike at the player that the engine never rolled.

        Until 2026-09-25 this was a door: `attacked_by` read the blow out of the finished
        prose and `struck_first` opened a fight on it. Measured live on the provoke
        script the same day: the plan declared the real blows itself (the engine rolls a
        declared first blow before the prose now), and the one blow the door read was
        "He doesn't reach for a weapon, but he slams a heavy, calloused fist onto the
        bar" — a fight opened on a man hitting furniture. So what the regex finds is a
        claim the dice never made, and it gets the project's standing repair: one
        targeted rewrite naming the fix, and if that still strikes, the sentence goes.
        A misread now costs a rewrite, never a phantom fight.

        Returns (text, repair note or "", attempts).
        """
        from .narration import unquoted

        scene = self.engine.scene
        # With or without a striker the code can name: a blow thrown by somebody the
        # prose is only now describing — nobody the scene holds yet — is as undeclared
        # as one thrown by the man at the bar (found writing the test, 2026-09-25).
        struck = judgement.attacked_by(scene, text)
        if not struck:
            return text, "", []
        names = ", ".join(dict.fromkeys(
            scene.actors[r].name if r in scene.actors else "somebody"
            for r, _ in struck)) or "somebody"
        correction = (
            f"In this beat {names} strikes at the player, and nothing the engine decided "
            f"has anybody strike: no blow was rolled, so none was thrown and none landed. "
            f"Write the same beat again with {names} threatening, squaring up or "
            f"reaching — as close to violence as you like — but with no blow thrown at "
            f"the player. The same events otherwise.")
        attempts = []
        try:
            again = client.chat(
                messages + [{"role": "assistant", "content": text},
                            {"role": "user", "content": correction}],
                self.prose_model, self.prose_host, as_json=True, think=False,
                temperature=0.7, num_predict=1400, provider=self.prose_provider,
                api_key=self.prose_key, schema=schema, timeout=FALLBACK_TIMEOUT)
            text2 = self._lift(str(again.json().get("narration", "")).strip())
            still = judgement.attacked_by(scene, text2)
            attempts.append(Attempt("prose", again.seconds, again.model, again.text,
                                    note="retry, undeclared blow named"
                                         + (" — still strikes" if still else "")))
            if text2 and not still and not narration_mod.reads_as_a_refusal(text2):
                return text2, f"an undeclared blow by {names}: rewritten without it", attempts
        except Exception as exc:
            attempts.append(Attempt("prose", 0.0, self.prose_model,
                                    note=f"blow retry failed: {str(exc)[:100]}"))
        # The backstop: the sentences that throw the blow are cut.
        gone = {" ".join(s.split()) for _, s in struck}
        kept = [p for p in re.split(r"(?<=[.!?])\s+", text)
                if " ".join(unquoted(p).split()) not in gone]
        cut = " ".join(kept).strip()
        if cut and cut != text:
            return cut, f"an undeclared blow by {names}: the sentence was cut", attempts
        return text, f"an undeclared blow by {names}: could not be removed", attempts

    def _undeclared_arrivals(self, text: str, messages: list, schema: dict):
        """Mid-fight, the prose brings in people the engine never put on the board.

        Item 30 (2026-09-19): "a band of twelve raiders" arrived in the prose mid-battle
        and zero bodies went on the board; the fix then was to promote the prose's
        people into bodies. Ruled 2026-09-27, the prose makes no bodies — so a newcomer
        in a fight's prose is a claim nothing backs, and gets the standing repair: one
        rewrite naming the fix. Arrivals are the plan's or an NPC turn's `spawn`. Out of
        a fight, since the owner's ruling of 2026-10-01 ("if i can see them they should
        be in the scene as a fully made person"), the people a beat shows are given
        bodies after it (play/aftermath/seen_people.py); in a fight they still are not.

        Returns (text, repair note or "", attempts).
        """
        scene = self.engine.scene
        if not getattr(scene, "in_encounter", False):
            return text, "", []
        cast = list(scene.cast)
        try:
            newcomers = judgement.note_cast(scene, text, turn=0)
        finally:
            scene.cast = cast
        if not newcomers:
            return text, "", []
        who = ", ".join(newcomers)
        correction = (
            f"In this beat {who} {'arrives' if len(newcomers) == 1 else 'arrive'} in the "
            f"fight, and nothing the engine decided brought anybody new in: the people in "
            f"this fight are the ones already on the board. Write the same beat again "
            f"with only them — the same blows and events otherwise.")
        attempts = []
        try:
            again = client.chat(
                messages + [{"role": "assistant", "content": text},
                            {"role": "user", "content": correction}],
                self.prose_model, self.prose_host, as_json=True, think=False,
                temperature=0.7, num_predict=1400, provider=self.prose_provider,
                api_key=self.prose_key, schema=schema, timeout=FALLBACK_TIMEOUT)
            text2 = self._lift(str(again.json().get("narration", "")).strip())
            cast = list(scene.cast)
            try:
                still = judgement.note_cast(scene, text2, turn=0)
            finally:
                scene.cast = cast
            attempts.append(Attempt("prose", again.seconds, again.model, again.text,
                                    note="retry, undeclared arrival named"
                                         + (f" — still brings in {', '.join(still)}"
                                            if still else "")))
            if text2 and not still and not narration_mod.reads_as_a_refusal(text2):
                return text2, f"undeclared arrivals in a fight ({who}): rewritten", attempts
        except Exception as exc:
            attempts.append(Attempt("prose", 0.0, self.prose_model,
                                    note=f"arrival retry failed: {str(exc)[:100]}"))
        return text, f"undeclared arrivals in a fight ({who}): could not be removed", attempts

    def _lift(self, text: str) -> str:
        """A reply's narration with its speaker tags taken out, and what they said kept.

        Every reader of a model's narration goes through here, the moment the reply is
        parsed: the tags must never reach a check, a rewrite or the page, and a tag the
        model wrote on any call — the examples teach it to all of them — is lifted the
        same way (`tests/test_speaker_tags.py` holds every reader to it).
        """
        scene = self.engine.scene
        people = {r: a for r, a in scene.actors.items() if not a.is_pc}
        names = {}
        for ref, a in people.items():
            for n in (getattr(a, "name", ""), getattr(a, "true_name", "")):
                n = str(n or "").strip().lower()
                if n:
                    names.setdefault(n, ref)
                    names.setdefault(re.sub(r"^(?:the|a|an)\s+", "", n), ref)
        clean, said = speech_mod.lift(text, refs=people, names=names)
        self.last_said.extend(said)
        return clean

    # --- Call 1 ---------------------------------------------------------------------

    def plan_turn(
        self, player_input: str, history: list[dict], location=None,
        recent_events=None, max_attempts: int = 5, previous_intents=None,
        recent_narration=None,
    ) -> TurnPlan:
        """
        Five attempts, not three. Measured across live turns: the model makes a
        *different* mistake each time rather than repeating one, so each rejection
        genuinely teaches it something and three was cutting it off mid-convergence. A
        warm attempt costs about 4s, so five is a worst case of ~20s — cheap against
        losing the turn.

        And then a different model. A live session hit a turn llama3.1 could not
        produce in any of its five shapes, and the player got a wall of red where the
        game should be. The last two slots on the schedule belong to the configured
        fallback model — a different tune makes different mistakes, which is the whole
        reason to have one — and it inherits the final rejection, so it starts warned
        rather than fresh.
        """
        self.last_said = []
        self.intimate = None
        # Where the party stood when the turn began, and the settlement, for the narrator
        # checks (gm/checks, `BeatContext.was_at`): a refused move is judged against the
        # place the turn started from, whatever the engine did afterwards.
        self._was_at = str(getattr(self.engine.scene, "at", "") or "")
        self._location = location
        # Continue is a directive, never an utterance. The ruling (2026-09-18): "my
        # character should keep doing whatever he is doing and the scene should move
        # forward without any addition from me." So no plan is asked of the model at
        # all: the player's standing action holds (a legal delay in a fight; the NPC
        # loop then runs), the prose call is shown the standing action as a fact, and
        # the directive's own text never reaches the planner as the player's words —
        # measured before this, it came back as `say` of "in their own words…", `give`
        # of "scene on" three times, and `use_item potion_of_rest_01`.
        if player_input == prompts.CARRY_ON:
            return self._continue_plan()
        # Somebody the prose described and the player now turns to walks on with a body
        # first, so the plan can address them by ref. Since 2026-10-01 most of them
        # already have one — people a beat shows are embodied after it — so this is the
        # backstop for the ones it could not (a fight, a heard-of person met at last).
        # The player's sentence, read once into a checked frame (gm/interpret.py,
        # docs/the-interpreter.md): the readers below consult it before their regex, and
        # the planner is shown it. A reading that fails costs nothing but the reading —
        # the turn goes on exactly as it did before the interpreter existed.
        from . import interpret

        self.reading = None
        if interpret.ENABLED:
            try:
                self.reading = interpret.interpret(player_input)
                interpret.remember(player_input, self.reading)
            except Exception as exc:  # noqa: BLE001 — never a reason to lose the turn
                self.reading = {"error": str(exc)[:200]}
        judgement.embody_sought(self.engine.scene, player_input, self.world)
        # The plan sees the situation cards — the GM's secret ones included — keyed
        # off the last few beats the view hands over (`self.recent`).
        brief = prompts.scene_brief(self.world, self.engine.scene, location, recent_events,
                                    here=self.engine.here(), known=self.engine.places(),
                                    recent=getattr(self, "recent", None), secret=True,
                                    turn=getattr(self, "turn", 0),
                                    reading=getattr(self, "reading", None),
                                    player_text=player_input)
        read = interpret.brief_lines(self.reading if isinstance(self.reading, dict)
                                     and "error" not in self.reading else None)
        if read:
            brief += "\n\n" + read
        # A fight is a different job, and gets a different prompt and a different floor.
        fighting = self.engine.scene.in_encounter
        build = (prompts.call_one_intents_only if self.intents_first
                 else prompts.call_one_messages)
        # What the budget had to leave out, so the turn log can say it. Ollama would
        # cut this prompt for us and tell nobody; `prompts.pack` cuts it in a stated
        # order and reports. A cut nobody records is the failure that ends here.
        self.packed: dict = {}
        base = build(brief, history, player_input, in_combat=fighting,
                     enemy=self._current_enemy(), report=self.packed,
                     ledger=getattr(self, "ledger", None))
        messages = base

        attempts: list[Attempt] = []
        rejections: list[str] = []
        # What the player's own words already commit this turn to, read by asking the
        # injectors what they would add. Computed once: it depends on the player's text
        # and the scene, and neither moves between attempts.
        declared = judgement.declared_ops(player_input, self.engine.scene, self.world,
                                          attached=getattr(self, "attachments", ()))
        # And what the reading grounds, joined — the detectors stay a second opinion
        # until each is retired on a measured comparison (docs/the-interpreter.md).
        if isinstance(self.reading, dict) and "error" not in self.reading:
            by_reading = interpret.ops_for(self.reading, self.engine.scene,
                                           self.engine.places())
            self.reading["ops"] = by_reading
            self.reading["detectors"] = list(declared)
            # The reading decides where the two disagree (`interpret.supported`); the
            # overruled op is kept on the record.
            declared, overruled = interpret.supported(declared, self.reading)
            self.reading["overruled"] = overruled
            declared = list(dict.fromkeys([*declared, *by_reading]))
            # Where the reading says the named place is the one the party stands in, no
            # walk is owed. Measured live 2026-09-27: at the market already, "I go to the
            # market and buy a coil of rope" had a detector require `travel`, and with a
            # travel's place held to the OTHER places here the model had to leave — it
            # walked to the merchants row.
            from rules import places as places_mod

            here_named = [a for a in self.reading.get("actions") or []
                          if a.get("act") in ("go", "leave") and a.get("place")
                          and getattr(places_mod.find(self.engine.places(), a["place"]),
                                      "id", None) == self.engine.scene.at]
            if here_named and "travel" not in by_reading:
                declared = [op for op in declared if op != "travel"]

        from play import modelcfg

        schedule = [(self.model, self.host, self.provider, self.api_key)] * max_attempts
        spare = modelcfg.for_role("fallback") or {}
        if spare.get("model") and spare["model"] != self.model:
            schedule += [(spare["model"], spare.get("host", self.host),
                          spare.get("provider", "ollama"),
                          spare.get("api_key", ""))] * 2
        last = len(schedule) - 1

        # A model that could not be reached is not asked again this turn. Measured
        # 2026-09-25: a `ModelUnavailable` inside this loop — a timeout, Ollama restarting
        # under a loaded model — left the loop and aborted the turn, so the fallback model
        # this schedule exists to reach was never tried. Only when every model in it is
        # down does the player get the "start Ollama" answer.
        down: set[str] = set()
        for n, (model, host, provider, key) in enumerate(schedule):
            if model in down:
                continue
            if n == max_attempts:
                rejections.append(f"— handing the turn to {model}")
            # The shape the reply is *allowed* to have, built from this turn's situation
            # rather than fixed. In a fight the intent list may not be empty and
            # `narrate_only` is not among the choices, so the failure that cost this
            # project its whole combat loop — narrating a punch and proposing nothing —
            # is not a reply the sampler can produce. See `prompts.turn_schema`.
            try:
                reply = client.chat(messages, model, host, as_json=True, think=False,
                                temperature=0.8 if n == 0 else 0.5,
                                provider=provider, api_key=key,
                                schema=prompts.turn_schema(
                                    fighting=self.engine.scene.in_encounter,
                                    refs=tuple(self.engine.scene.actors),
                                    # No floor when the prose is not being asked for.
                                    # The schema enforces the minimum at the sampler, so
                                    # leaving it in place would make the empty narration
                                    # this mode requires unsamplable.
                                    min_chars=0 if self.intents_first else
                                    (narration_mod.MIN_COMBAT_CHARS
                                     if self.engine.scene.in_encounter
                                     else narration_mod.MIN_SCENE_CHARS),
                                    # Required up front rather than injected afterwards.
                                    # The injectors still run below as the backstop; this
                                    # gives the model first refusal, with the scene in
                                    # front of it, on choosing the item and the target.
                                    must_contain=tuple(declared),
                                    # A declared travel chooses among the places that
                                    # exist here, by name, and invents none — the list
                                    # is the interpreter's to widen (the ground outside
                                    # the walls, Lane B), so it is asked for there.
                                    places=interpret.travel_choices(
                                        self.reading if isinstance(self.reading, dict)
                                        and "error" not in self.reading else None,
                                        self.engine.scene, self.engine.places(),
                                        location),
                                    # A declared cast's aim chooses among the aims that
                                    # exist here (`areas.legal_aims`) — the people, the
                                    # caster, the features and props, and for a cone or
                                    # a line the map's axes.
                                    aims=self._cast_aims(player_input)
                                    if "cast" in declared else ()))
            except client.ModelUnavailable as exc:
                down.add(model)
                rejections.append(f"attempt {n + 1}: {model} could not be reached: {exc}")
                if all(m in down for m, *_ in schedule):
                    raise
                continue
            attempts.append(Attempt("plan", reply.seconds, reply.model, reply.text))
            # What `own_words_only` changed on this attempt, for the turn log.
            own_words: list[str] = []

            try:
                data = reply.json()
            except ValueError as exc:
                rejections.append(f"attempt {n + 1}: {exc}")
                messages = _with_correction(base, reply.text, str(exc))
                continue

            narration = self._lift(str(data.get("narration", "")).strip())
            try:
                # Checks 1, 2 and 3. A malformed intent has no repairable content, so
                # these are hard rejections that regenerate — but the rejection text
                # names the legal refs and vocabularies, which turns a blind retry into
                # a repair.
                #
                # The target is filled in *before* validation, because the engine refuses
                # an untargeted attack with a `legality` error and legality errors
                # regenerate rather than repair: five attempts, then the turn is gone.
                #
                # Three mechanical repairs, in dependency order. The misaim check first,
                # because it reads the *model's* target before anything fills one in: an
                # attack aimed at a valid ref that is not the person the player named
                # gets the named person spawned and the attack moved onto them — the
                # playtest stabbed a dying gatekeeper three scenes away because the
                # winged woman in the narration had never been made real. Then the
                # lone-candidate fill, then the survival injection, which appends `rest`,
                # `eat` and `drink` for the sleep and meals both models narrate and
                # neither ever proposes, worked example notwithstanding.
                raw = data.get("intents")
                # The ops the player's words committed the turn to, which the schema asks
                # for as required keys because Ollama does not enforce `contains`
                # (`prompts.turn_schema`): merged in where the list left them out.
                raw = self._merge_declared(
                    raw, data.get("declared"),
                    actor=getattr(self.engine.scene.pc(), "ref", ""))
                # A give to the player that the reading never asked for is conjuring.
                raw, conjured = interpret.drop_unread_gifts(
                    raw, self.reading if isinstance(self.reading, dict) else None)
                if conjured:
                    self.reading.setdefault("dropped_gifts", []).extend(conjured)
                # First, because everything downstream reads the shapes this
                # straightens: a target pocketed in params is invisible to the misaim
                # check, and an invented param is a schema refusal five lines later.
                raw = judgement.split_plural_targets(raw)
                # An introduce placeholder nothing introduced (`attack new1`) is the
                # person the plan plainly meant, before anything fills a target or
                # opens a fight around it — or left for validation to refuse.
                raw = judgement.bind_placeholders(raw, player_input, self.engine.scene)
                # The player's own cast, jar or power with no actor written is theirs.
                raw = judgement.fill_missing_actor(raw, player_input, self.engine.scene)
                # In a fight a companion's turn is their own: an order the player gave
                # them reaches it there (gm/companions.py), never as their act on the
                # player's turn. Out of one, a companion the words are spoken TO answers
                # for themselves after the plan resolves (`views._companions_answer`).
                # Noted with the turn's other plan repairs.
                from . import companions as companions_mod

                raw = companions_mod.on_their_own_turn(
                    raw, self.engine.scene, notes=own_words,
                    addressed_refs=companions_mod.addressed(self.engine.scene,
                                                            player_input))
                raw = judgement.repair_bare_spawns(raw, player_input)
                raw = judgement.normalize_attacks(raw, self.engine.scene) or raw
                # A thing thrown or swung is an improvised-weapon attack that names
                # the thing — before the misaim check reads "the man" it was thrown
                # at, and before anything can dress the throw as a spell.
                raw = judgement.inject_improvised(raw, player_input, self.engine.scene)
                raw = judgement.repair_misaimed_attack(
                    raw, player_input, self.engine.scene) or raw
                raw = judgement.fill_obvious_targets(raw, self.engine.scene)
                # The stat block a person the plan introduces walks on with, read off
                # their words the way the prose's people always were (`template_for`).
                raw = judgement.fill_introduce_templates(raw, self.engine.scene)
                # A blow at a thing somebody holds is a blow at that somebody, and
                # a sunder asked for is a sunder: "I strike the weapon and sunder it"
                # died five times on "a sunder needs a target" and then spawned a
                # thug named "weapon" (2026-09-18).
                raw = judgement.aim_at_the_holder(raw, player_input,
                                                  self.engine.scene) or raw
                # Then the target held to the person the player is engaged with —
                # or handed back as a question when two are live and the player
                # named neither. The fight with the challenger that was resolved
                # against the stranger (2026-09-18) is this check's measurement.
                raw = judgement.check_the_target(raw, player_input, self.engine.scene,
                                                 recent=getattr(self, "recent", ())) or raw
                raw = judgement.redirect_attacks_off_corpses(
                    raw, player_input, self.engine.scene) or raw
                # Once the targets are settled: "I finish him" at a body on the floor is
                # 1e's coup de grâce, declared from the words rather than hoped for.
                raw = judgement.declare_coup_de_grace(raw, player_input,
                                                      self.engine.scene)
                raw = judgement.declare_repair(raw, player_input, self.engine.scene)
                raw = judgement.declare_name(raw, player_input, self.engine.scene)
                # Before survival: a drunk potion is the jar door, not a waterskin
                # sip, and never a number the model wrote.
                raw = judgement.declare_use_item(raw, player_input, self.engine.scene)
                # A nibble of a herb is the engine's `taste`, never a meal and never the
                # narrator's guess at what the leaf does (herbalism plan §8.2).
                raw = judgement.declare_taste(raw, player_input, self.engine.scene)
                raw = judgement.inject_survival(raw, player_input, self.engine.scene)
                # Sale first, then goods. Selling is the more specific reading of handing
                # something over and it is the one that pays — and the order was the other
                # way round for exactly as long as it took `declared_ops` to notice: "I
                # sell the Yarow Elixir" matched `_HANDS_OVER`, became a `give`, and the
                # elixir left the satchel for nothing.
                # Coin first: "I pay her ten gold" is a give of gp out of the purse,
                # and a `sell gold_coins_10` the model wrote is the same give — before
                # the sale injector can read "pay" as a sale of stock.
                raw = judgement.inject_payment(raw, player_input, self.engine.scene)
                raw = judgement.inject_sale(raw, player_input, self.engine.scene)
                raw = judgement.inject_goods(raw, player_input, self.engine.scene)
                raw = judgement.inject_ability(raw, player_input, self.engine.scene)
                # And its complement: a power the player named that nobody has is a
                # printed refusal, never the model's guess at what it does.
                raw = judgement.refuse_unknown_ability(raw, player_input,
                                                       self.engine.scene)
                # And its other complement: a power with no name at all. "I read his
                # mind" has nothing capitalised to look up, so it used to reach the
                # narrator as ordinary prose and get written as working.
                raw = judgement.refuse_unnamed_power(raw, player_input,
                                                     self.engine.scene)
                # And the thing summoned rather than the power claimed. The fiat
                # phrasings never reach here — `play/player_input.py` hands those back
                # before any model call — but "I summon a celestial dog" is a real
                # sentence from a summoner and an empty one from a rogue, and only the
                # sheet can tell them apart.
                raw = judgement.refuse_declared_creation(raw, player_input,
                                                         self.engine.scene)
                # And the thing CLAIMED rather than summoned: "I reveal my true form as
                # a divine being" is a Bluff the room rolls to see through. Before the
                # check injector, whose broad verbs would otherwise read it as
                # something else or nothing.
                # With the reading (item 5, 2026-09-30): a take, a pick-up or a plan's give
                # of the thing is acquisition, and the claim the prose was handed before
                # any reading existed is withdrawn when the reading says so.
                reading = self.reading if isinstance(self.reading, dict) else None
                raw = judgement.inject_false_claim(raw, player_input, self.engine.scene,
                                                   reading=reading)
                if getattr(self, "false_claim", "") and not judgement.false_claim(
                        player_input, self.engine.scene, reading=reading, plan=raw):
                    self.false_claim = ""
                # Before `inject_checks`: "I cast charm person on the guard" is a spell,
                # not a Diplomacy check, and the check injector's verbs are broad enough
                # to claim it.
                raw = judgement.inject_cast(raw, player_input, self.engine.scene,
                                            attached=getattr(self, "attachments", ()))
                # The plan's own cast with no aim written takes one from the player's
                # words where they ground it (G2): a name or a thing here, never a guess.
                raw = judgement.aim_the_cast(
                    raw, player_input, self.engine.scene,
                    self.reading if isinstance(self.reading, dict) else None)
                raw = judgement.the_players_spell_dice(raw, player_input, self.engine.scene)
                raw = judgement.inject_checks(raw, player_input, self.engine.scene)
                # After inject_checks so its product is covered too: a check with
                # neither dc nor opposed_by is refused by validation, and the "engine
                # default band" the old docstring promised never existed.
                raw = judgement.drop_premature_end(raw)
                raw = judgement.drop_stray_checks(raw, player_input)
                raw = judgement.fill_bare_checks(raw)
                raw = judgement.inject_travel(raw, player_input, self.engine.scene,
                                              self.world)
                # A place from the exits row is WHERE, as a spell chip is which spell:
                # held to the chip before the travel readers below can ask the player
                # again about a room their words named on the way out.
                raw = judgement.travel_to_the_attached(
                    raw, self.engine.scene, getattr(self, "attachments", ()))
                # A travel the model wrote with nowhere in it takes the place the
                # player named, so validation can find it or name "found it first".
                raw = judgement.fill_empty_travel(raw, player_input, self.engine.scene)
                # A departure that names the room the party is in is asked again with
                # the rooms that would have worked; raises into the correction path.
                raw = judgement.refuse_leaving_in_place(raw, player_input,
                                                        self.engine.scene, self.world,
                                                        reading=reading,
                                                        attached=getattr(self, "attachments", ()))
                # After travel, load-bearing: "go to the forest and forage" must move
                # first or the forage rolls the old ground's tables.
                raw = judgement.inject_forage(raw, player_input, self.engine.scene)
                raw = judgement.inject_prospect(raw, player_input, self.engine.scene)
                raw = judgement.inject_found(raw, player_input, self.engine.scene, self.world)
                raw = judgement.inject_venture(raw, player_input, self.engine.scene)
                raw = judgement.inject_wait(raw, player_input, self.engine.scene)
                raw = judgement.bulk_give_is_a_loot(raw, self.engine.scene)
                raw = judgement.inject_loot(raw, player_input, self.engine.scene)
                # Last, and after the target fills: a fight the player declared and the
                # GM only described. Runs once there is certainly nobody to fight, so it
                # cannot steal a turn from `fill_obvious_targets`.
                raw = judgement.inject_fight(raw, player_input, self.engine.scene)
                # Somebody's house: the engine's knock, in place of a walk into a
                # place that is not one yet (docs/the-population.md, calling on people).
                # Breaking in first: "I break into her house" is not a knock.
                raw = judgement.inject_break_in(raw, player_input, self.engine.scene)
                raw = judgement.inject_call_on(raw, player_input, self.engine.scene)
                # A declared purchase is made on the counter's screen, which the turn
                # opens with the thing picked (play/views.py, `_trade_offer`).
                raw = judgement.strip_counter_buys(raw, player_input)
                # After every attack the turn will hold exists. What strikes is the
                # player's word — "I punch him" is the fist, not the rapier in hand —
                # and then, reading that weapon, to spare or to kill is theirs too; a
                # lethality the model chose for the PC on its own is struck (a -4
                # nobody asked for).
                raw = judgement.declare_unarmed(raw, player_input, self.engine.scene)
                raw = judgement.declare_lethality(raw, player_input, self.engine.scene)
                raw = judgement.inject_company(raw, player_input,
                                               self.engine.scene, self.world)
                # Speech last, because it competes with nothing: "I tell the smith I
                # want the axe" is a sale AND a line of dialogue, and both belong in
                # the turn. Measured on the first live turn after the `say` op landed —
                # the schema asked for one, the model wrote prose instead, and the turn
                # resolved with no `say` at all, which is the whole failure the op
                # exists to end. Detect mechanically, repair with a targeted call.
                # Somebody looked for and not here yet is introduced, before the line
                # addressed to them (the schema already required it; this is the net).
                raw = judgement.inject_introduce(raw, player_input, self.engine.scene,
                                                 self.world)
                # And never somebody the sentence only asks ABOUT, whoever wrote the
                # introduce: "I ask the nearest person about the girl who sells herbs"
                # introduced the herb seller and spoke to her (G3, 2026-09-29).
                raw = judgement.asked_about_not_addressed(raw, player_input,
                                                          self.engine.scene)
                # An insult aimed at somebody provokes them (rules/provocation.py).
                raw = judgement.inject_provoke(raw, player_input, self.engine.scene)
                raw = judgement.inject_say(raw, player_input, self.engine.scene)
                # And the world's answer when the player looked for somebody who is not
                # here, stated whether or not the plan reached for them (item 29). Last,
                # because it reads the player's own sentence and competes with nothing.
                raw = judgement.answer_the_absent(raw, player_input, self.engine.scene,
                                                  self.world)
                # Last of all: a say in the player's character's mouth carries the
                # player's words or none (item 6) — after every injector that can add one.
                raw = judgement.own_words_only(
                    raw, player_input,
                    self.reading if isinstance(self.reading, dict) else None,
                    notes=own_words)
                # And the attached spell or place put where the words do it, after
                # every injector above has appended its own (gm/sequence.py).
                raw = judgement.order_the_attached(
                    raw, player_input, self.engine.scene,
                    getattr(self, "attachments", ()))
                data = dict(data, intents=raw)
                try:
                    intents = self.engine.validate(raw)
                except IntentError as exc:
                    # A refusal only the player can fix, on an op the player declared,
                    # ends the turn here: shown to them once, never retried (item 21.3).
                    # One the plan invented is dropped and the rest validated again.
                    stop, raw = self._players_refusal(exc, raw, declared, player_input)
                    if stop is not None:
                        rejections.append(f"attempt {n + 1} [{exc.check}, "
                                          f"{exc.code}]: {exc} — the player's to fix")
                        return self._refused_plan(stop, attempts, rejections)
                    if raw is None:
                        raise
                    rejections.append(f"attempt {n + 1} [{exc.check}, {exc.code}, "
                                      f"dropped]: {exc} — an op the player never asked for")
                    data = dict(data, intents=raw)
                    intents = self.engine.validate(raw)
            except IntentError as exc:
                # The GM naming people it wanted to exist — "attack thug1" — is the one
                # rejection it will not learn from, hint and example notwithstanding. It
                # is repaired in code instead of asked about again.
                if exc.check == "refs":
                    amended = judgement.repair_unknown_refs(
                        data.get("intents"), player_input, self.engine.scene,
                        world=self.world)
                    if amended:
                        try:
                            intents = self.engine.validate(amended)
                            rejections.append(
                                f"attempt {n + 1} [refs, repaired]: created the people "
                                f"the GM had already described")
                            data = dict(data, intents=amended)
                        except IntentError:
                            amended = None
                    if not amended:
                        # A sale addressed to somebody who is not here is not the
                        # spawn repair's business — a merchant must not pop into
                        # existence because the player addressed one — but it must not
                        # cost the turn either: seven attempts died on exactly this
                        # before the drop existed.
                        amended = judgement.drop_unfulfillable_trades(
                            data.get("intents"), self.engine.scene)
                        if amended:
                            try:
                                intents = self.engine.validate(amended)
                                rejections.append(
                                    f"attempt {n + 1} [refs, dropped]: a trade aimed "
                                    f"at nobody present was dropped")
                                data = dict(data, intents=amended)
                            except IntentError:
                                amended = None
                    if not amended:
                        rejections.append(f"attempt {n + 1} [{exc.check}]: {exc}")
                        messages = _with_correction(base, reply.text, str(exc))
                        continue
                else:
                    rejections.append(f"attempt {n + 1} [{exc.check}]: {exc}")
                    messages = _with_correction(base, reply.text, str(exc))
                    continue

            # Check 5: not "is this legal" but "is this what the player asked for".
            # Corrections are applied in place; an objection sends the turn back once,
            # because we can tell the GM is wrong without being able to tell it what it
            # should have done.
            verdict = judgement.review(player_input, intents, self.engine.scene,
                                        previous=previous_intents)
            repairs = list(verdict.as_log()) + self._context_note() + own_words
            if not verdict.ok and n < last:
                complaint = " ".join(o.message for o in verdict.objections)
                rejections.append(f"attempt {n + 1} [judgement]: {complaint}")
                messages = _with_correction(base, reply.text, complaint)
                continue

            if verdict.corrections:
                # A correction can invalidate what was already checked, and did: cutting
                # a spawn of two down to one left a later `attack c3` pointing at a
                # creature that would now never exist, and the engine raised KeyError
                # mid-resolution. Anything corrected is validated again.
                try:
                    intents = self.engine.validate([i.as_dict() for i in intents])
                except IntentError as exc:
                    rejections.append(f"attempt {n + 1} [after-correction]: {exc}")
                    if n < last:
                        messages = _with_correction(base, reply.text, str(exc))
                        continue
                    raise

            # Every prose repair below has nothing to work on when the prose has not been
            # written yet — and that is the point of the experiment, not a special case
            # bolted round it. `_repair_outcome_claims` in particular exists *only*
            # because narration currently precedes the dice.
            if self.intents_first:
                return TurnPlan(narration="", intents=intents,
                                suggestions=_suggestions(data), attempts=attempts,
                                repairs=repairs, rejections=rejections)

            narration, prose_repairs, prose_attempts = self._groom(
                narration, earlier=recent_narration or [],
                min_chars=(narration_mod.MIN_COMBAT_CHARS if fighting
                           else narration_mod.MIN_SCENE_CHARS),
                max_chars=narration_mod.MAX_COMBAT_CHARS if fighting else 0,
                player_input=player_input, brief=brief, hand_back=True, claims=True,
                ctx=self._beat_context("plan", player_input=player_input, brief=brief,
                                       location=location))
            attempts.extend(prose_attempts)

            return TurnPlan(narration=narration, intents=intents,
                            suggestions=_suggestions(data),
                            attempts=attempts,
                            repairs=repairs + prose_repairs,
                            rejections=rejections)

        # `schedule` holds (model, host, provider, key). Unpacked as a pair, this line
        # raised `ValueError: too many values to unpack` *while reporting that the turn
        # had failed* — so the honest "five attempts, here is what each one got wrong"
        # message the player was owed came out as a 500 and a traceback instead. It only
        # runs when every attempt has failed, which is why nobody had ever reached it.
        # Found by `tools/narrator_audit.py`.
        # Every attempt failed. The player's own ruling on what happens next: "i
        # should get a narrated text like 'you look for a group of guards to fight
        # but none seem to be around' — if that's not the case then this is just an
        # error." So the turn degrades to a narrated nothing instead of a wall of
        # red: a narrate_only plan with an honest sentence, and the full rejection
        # log kept in the plan for the turn ledger, not the transcript.
        asked = " ".join((player_input or "").split())
        return TurnPlan(
            narration=(f"You try — “{asked}” — but the moment does not "
                       f"answer: whatever you were reaching for is not here to be "
                       f"found. What do you do instead?"),
            intents=self.engine.validate([{"op": "narrate_only",
                                           "because": "the turn could not be shaped"}]),
            suggestions=[], attempts=attempts,
            repairs=[f"turn degraded to narration after {len(schedule)} failed "
                     f"attempts"],
            rejections=rejections)

    # --- A refusal the player has to fix ---------------------------------------------

    def _players_refusal(self, exc: IntentError, raw: list, declared, player_input: str
                         ) -> tuple[dict | None, list | None]:
        """What to do with a validation refusal before the plan loop retries it.

        Item 21.3, measured 2026-09-28: "cast: Bobby did not prepare Burning Hands
        today." came back seven times of seven, across two models, and then the turn was
        disguised as "the moment does not answer". No plan could have fixed it — the fix
        was the player's (prepare the spell). Self-correction helps when the feedback is
        reliable and the fix is within reach (Kamoi et al. 2024); here the feedback was
        reliable and the fix was out of the model's reach entirely.

        Returns (refusal, None) when the turn ends here: the code is one only the player
        can fix (`IntentError.fixable_by`, rules/intents.py PLAYER_FIXABLE), the op is
        one the player's words declared, and it is the player's character acting.
        Returns (None, raw without that intent) when the same refusal lands on an op the
        player never asked for — the plan invented it, so it goes and the rest stands.
        (None, None) otherwise: the loop's own retry, as before.

        A weapon is the player's to fix only when the player named it: a plan that
        picked a blade the character does not carry is the plan's mistake, and a retry
        mends it."""
        if exc.fixable_by != "player" or exc.index is None:
            return None, None
        from rules import engine as engine_mod
        from rules.intents import parse_all

        try:
            parsed = parse_all(raw)
            ordered = engine_mod._introduce_after_travel(
                engine_mod._found_before_travel(parsed))
            intent = ordered[exc.index]
            at = next(k for k, p in enumerate(parsed) if p is intent)
        except Exception:  # noqa: BLE001 — unreadable: the loop's own retry answers it
            return None, None
        pc = self.engine.scene.pc()
        players = intent.actor in (None, "", "pc") or (pc is not None
                                                        and intent.actor == pc.ref)
        if not players:
            return None, None
        if exc.code == "no_such_weapon":
            named = str(intent.params.get("weapon") or "").strip().lower()
            if not named or named not in str(player_input or "").lower():
                return None, None
        if intent.op in set(declared or ()):
            text = str(exc.for_a_person or "").strip() or re.sub(
                r"^[a-z_]+:\s*", "", str(exc)).strip()
            return {"text": text, "code": exc.code, "fix": exc.fix}, None
        rest = [r for k, r in enumerate(raw) if k != at]
        return None, (rest or [{"op": "narrate_only",
                                "because": "the only op was one nobody asked for"}])

    def _refused_plan(self, refusal: dict, attempts: list, rejections: list) -> TurnPlan:
        """The turn a player-fixable refusal ends: nothing resolves, the refusal is the
        whole answer, and no second model is asked. The narration is the refusal's own
        sentence — never "the moment does not answer", and never a prose beat for a
        false claim the player did not make (item 21.3)."""
        return TurnPlan(
            narration=refusal["text"],
            intents=self.engine.validate([{"op": "narrate_only",
                                           "because": "refused, for the player to fix"}]),
            suggestions=[], attempts=attempts,
            repairs=[f"refused for the player to fix ({refusal['code']}): "
                     f"{refusal['text']}"],
            rejections=rejections, refusal=dict(refusal))

    # --- An NPC's turn -------------------------------------------------------------------

    def plan_cheat(self, wish: str, location=None, recent_events=None,
                   max_attempts: int = 3) -> TurnPlan:
        """The author's wish, turned into intents the engine will actually run.

        Prior art settled the shape before any of it was written. Inform's PURLOIN moves
        a *real object* into your hands wherever it is; NetHack's #wizwish goes through
        the same object-naming parser an ordinary game uses, and an unparseable wish
        gives you a random real object rather than an invented one; DikuMUD's immortal
        commands are `load obj <vnum>` and `set <player> gold 1000` — typed, targeted,
        and resolved by the same code that runs normal play. Not one tradition lets a
        sentence become fiction directly, and the reason is the one this app already
        knows: a wish the engine did not execute is a fact only the narrator remembers,
        and the narrator forgets.

        So a cheat is an intent list like any other. What it skips is the *fiction's*
        permission — no check, no cost, no refusal for being impossible — and what it
        does NOT skip is a single line of the engine's bookkeeping. It also skips the
        injector chain `plan_turn` runs, deliberately: those read the player's words as a
        declaration of what THEIR CHARACTER does, and `/cheat I defeat all the enemies`
        run through `inject_fight` would spawn somebody to fight.
        """
        brief = prompts.scene_brief(self.world, self.engine.scene, location, recent_events,
                                    here=self.engine.here(), known=self.engine.places(),
                                    reading=None, player_text=wish)
        base = prompts.cheat_messages(brief, wish)
        messages = base
        attempts: list[Attempt] = []
        rejections: list[str] = []

        for n in range(max_attempts):
            reply = client.chat(
                messages, self.model, self.host, as_json=True, think=False,
                temperature=0.3, provider=self.provider, api_key=self.api_key,
                schema=prompts.turn_schema(
                    fighting=False, refs=tuple(self.engine.scene.actors),
                    min_chars=0, ops=prompts.CHEAT_OPS))
            attempts.append(Attempt(kind="cheat", seconds=reply.seconds,
                                    model=self.model, raw=(reply.text or "")[:300]))
            try:
                data = reply.json()
            except ValueError as exc:
                rejections.append(f"attempt {n + 1}: {exc}")
                messages = _with_correction(base, reply.text, str(exc))
                continue
            try:
                raw = judgement.split_plural_targets(data.get("intents") or [])
                data = dict(data, intents=raw)
                # After validation on purpose: the count clamp exists to stop a
                # MODEL minting a million gold, and on this one path the number
                # is the author's own. Applied before, it was clamped straight
                # back and the live probe read identically either way.
                # The author's hand is a source: `/cheat` keeps the amount-ops and
                # the number is theirs, stamped as such.
                intents = judgement.keep_the_authors_numbers(
                    self.engine.validate(raw, origin="author:cheat",
                                         origin_name="the author's word"), wish)
            except IntentError as exc:
                rejections.append(f"attempt {n + 1} [{exc.check}]: {exc}")
                messages = _with_correction(base, reply.text, str(exc))
                continue
            return TurnPlan(narration="", intents=intents, attempts=attempts,
                            rejections=rejections)

        # Every attempt refused. A cheat that cannot be mechanised is still a thing the
        # author said, so it becomes a beat rather than an error: the wish reaches the
        # narrator and nothing pretends a number changed.
        return TurnPlan(
            narration="", intents=self.engine.validate(
                [{"op": "narrate_only",
                  "because": f"the author wrote: {wish}"}]),
            attempts=attempts, rejections=rejections)

    def _continue_plan(self) -> TurnPlan:
        """The plan for a Continue press, written in code: the player holds their
        standing action and the scene moves. One `narrate_only`, no model call.

        In a fight this is the player's legal delay — 1e's delay action, taking no
        action and letting the order run — and `views._finish` then hands the round to
        the NPC loop, which acts with dice; out of a fight the prose call is shown the
        standing action as a fact and the world advances a beat (the engaged NPC goes
        on, `attacked_by` may open a fight from what they do, the watcher ticks)."""
        intents = self.engine.validate([{
            "op": "narrate_only",
            "because": "the player holds their standing action; the scene moves on"}])
        return TurnPlan(narration="", intents=intents,
                        repairs=["continue: no plan asked of the model — the player's "
                                 "standing action holds and the world moves a beat"])

    def npc_turn(self, ref: str, location=None, recent_events=None,
                 max_attempts: int = 3, orders: list[str] | None = None) -> TurnPlan:
        """Act for one creature on its own initiative.

        Same validation as a player turn, so an NPC cannot be talked into a mechanic
        either. Fewer attempts than a player turn: a stalled NPC costs the fight far less
        than a stalled player turn costs the scene, and the caller falls back to the
        creature simply holding its ground.

        A companion's turn (`gm/companions.py`) is told who they are and `orders` — what
        the player has lately said to them — and decides in character what to do with it
        (the owner's ruling, 2026-10-01). Its one mechanical refusal: striking the player
        or the player's side, sent back with the fix named.
        """
        from . import companions

        actor = self.engine.scene.actors[ref]
        brief = prompts.scene_brief(self.world, self.engine.scene, location, recent_events,
                                    here=self.engine.here(), known=self.engine.places(),
                                    reading=getattr(self, "reading", None), player_text="")
        friend = companions.is_companion(actor)
        facts = (companions.turn_facts(self.engine.scene, actor, list(orders or []))
                 if friend else "")
        foes = companions.foes_of(self.engine.scene, ref) if friend else []
        # A disarmed creature re-arms first, by the engine's hand (`judgement.rearm`);
        # the prompt is told so as a fact, or the wind-up raises the fists the tells
        # are about to put a sap in.
        base = prompts.npc_turn_messages(brief, [], ref, actor, self.engine.scene.round,
                                         first=judgement.rearm_note(self.engine.scene, ref),
                                         companion=facts, foe=foes[0] if foes else None)
        # Stage 8's one named exception. A bestiary creature has no path, spellbook
        # or satchel, and its bite's poison lives in a stat block no locator reads
        # yet, so on its turn `damage` and `ability_damage` stay and the origin is
        # its template — the engine names the source, the model still writes the
        # number, and the ratchet lists this door by count until a creature-document
        # stage retires it. A creature WITH a class path uses its documents like
        # anyone else.
        template = str(getattr(actor, "from_template", "") or "")
        bestiary = bool(template) and not getattr(actor, "paths", None)
        ops = prompts._CREATURE_OPS if (bestiary and self.engine.scene.in_encounter) else ()
        # A companion may decline to act at all. The fight schema leaves `narrate_only`
        # out on purpose — the player's own turn narrated a punch and proposed nothing —
        # and so a companion's refusal was unsamplable: told to stay back, a timid drover
        # came back `attack` (4 of 5) or `move` (1 of 5), never the refusal the examples
        # demonstrate (companions replay, 2026-10-01).
        if friend and self.engine.scene.in_encounter:
            ops = tuple(dict.fromkeys((*(ops or prompts._FIGHT_OPS), "narrate_only")))
        origin = f"creature:{template}" if bestiary else ""
        messages = base
        attempts: list[Attempt] = []
        rejections: list[str] = []

        for n in range(max_attempts):
            reply = client.chat(messages, self.model, self.host, as_json=True, think=False,
                                provider=self.provider, api_key=self.api_key,
                                temperature=0.7, num_predict=400,
                                # The same grammar every other turn call carries. This
                                # one ran bare, so none of turn_schema's guarantees —
                                # ref enums, the fight-op restriction, minItems — ever
                                # applied to NPC turns, and malformed shapes cost the
                                # retry loop the schema exists to eliminate.
                                schema=prompts.turn_schema(
                                    fighting=self.engine.scene.in_encounter,
                                    refs=tuple(self.engine.scene.actors), ops=ops))
            attempts.append(Attempt("npc", reply.seconds, reply.model, reply.text))
            try:
                data = reply.json()
                raw, rearmed = judgement.rearm(self.engine.scene, ref, data.get("intents"))
                turned = (companions.turning_on_the_party(self.engine.scene, ref, raw)
                          or (companions.attack_against_its_reason(ref, raw)
                              if friend else "")
                          or (companions.attack_on_a_bystander(
                              self.engine.scene, ref, raw, list(orders or ()))
                              if friend else "")
                          or (companions.move_against_its_reason(
                              self.engine.scene, ref, raw) if friend else ""))
                if turned:
                    raise IntentError(turned, "legality")
                intents = self.engine.validate(raw, origin=origin,
                                               origin_name=actor.name if origin else "")
            except (ValueError, IntentError) as exc:
                rejections.append(f"attempt {n + 1}: {exc}")
                messages = _with_correction(base, reply.text, str(exc))
                continue

            # The census over all seven saves found this was the one door with no review
            # at all: NPC prose reached the transcript having seen only name_refs, the
            # example-cast strip, the claim repair and the bad-question fix — no invented
            # names, no third person, no wrong body, nothing. In a fight, half of what
            # the player reads comes through here.
            #
            # `rewrite=False`: the deterministic backstops close the hole for free, and a
            # ~10s polish call per NPC per round is a price a fight cannot pay.
            # `hand_back=False`: an NPC beat mid-round hands nothing back.
            self._location = location
            windup = self._lift(str(data.get("narration", "")).strip())
            # A companion's wind-up shows who they are in how they do it (the owner's
            # second ruling, 2026-10-01) — detected, repaired by one targeted call when
            # it reads as anybody's, and BEFORE the grooming, so every backstop below
            # also reads the rewrite.
            manner_notes: list[str] = []
            if friend:
                windup, manner_notes, more = self.manner_of(
                    windup, actor, ordered=bool(orders),
                    op=intents[0].op if intents else "", whole=True)
                attempts.extend(more)
            narration, repairs, groom_attempts = self._groom(
                windup,
                earlier=None, min_chars=0,
                max_chars=narration_mod.MAX_COMBAT_CHARS,
                player_input="", brief=brief, hand_back=False, claims=True,
                rewrite=False, acting=actor.name,
                ctx=self._beat_context("npc", player_input="", brief=brief,
                                       location=location, acting=ref))
            attempts.extend(groom_attempts)
            return TurnPlan(narration=narration, intents=intents, attempts=attempts,
                            repairs=[*rearmed, *manner_notes, *repairs],
                            rejections=rejections)

        raise IntentError(
            f"the GM could not act for {ref} in {max_attempts} attempts:\n"
            + "\n".join(rejections)
        )

    # What a companion may do in answer, out of a fight: speak, try something the engine
    # rolls, step somewhere, strike — never travel the party, spend its coin or end its
    # company, which are the player's.
    COMPANION_ANSWER_OPS = ("narrate_only", "say", "check", "move", "attack")

    def companion_answer(self, ref: str, said: str, location=None, recent_events=None,
                         max_attempts: int = 2, not_ready: bool = False) -> TurnPlan:
        """A companion answers the player's words to them, out of a fight: the targeted
        call `companions.addressed` triggers (owner's ruling, 2026-10-01 — they take
        spoken orders "as their character dictates they would or would not").

        The model decides, as the companion, from who they are and what was said; the
        engine decides what lands. Held mechanically to: only their own acts (every
        intent's actor is them), the ops in COMPANION_ANSWER_OPS, no DC of the model's
        (a try is opposed by whoever could stop it), and never a blow at the player.
        Raises IntentError when no attempt passes; the caller lets the prose answer.
        """
        from . import companions

        scene = self.engine.scene
        actor = scene.actors[ref]
        brief = prompts.scene_brief(self.world, scene, location, recent_events,
                                    here=self.engine.here(), known=self.engine.places(),
                                    reading=None, player_text="")
        others = [(r, a.name) for r, a in scene.actors.items()
                  if r != ref and not a.is_pc and scene.conscious(r)
                  and not companions.is_companion(a)]
        pc = scene.pc()
        base = prompts.companion_answer_messages(
            brief, ref, actor, companions.answer_facts(scene, actor, said,
                                                       not_ready=not_ready),
            other=others[0] if others else None, pc_ref=pc.ref if pc else "pc")
        messages = base
        attempts: list[Attempt] = []
        rejections: list[str] = []
        for n in range(max_attempts):
            reply = client.chat(messages, self.model, self.host, as_json=True, think=False,
                                provider=self.provider, api_key=self.api_key,
                                temperature=0.7, num_predict=400,
                                schema=prompts.turn_schema(
                                    fighting=False, refs=tuple(scene.actors),
                                    ops=self.COMPANION_ANSWER_OPS))
            attempts.append(Attempt("companion", reply.seconds, reply.model, reply.text))
            try:
                data = reply.json()
                raw = [dict(r) for r in (data.get("intents") or []) if isinstance(r, dict)]
                for r in raw:
                    r.setdefault("actor", ref)
                    if not r.get("actor"):
                        r["actor"] = ref
                    if r["actor"] != ref and r.get("op") != "narrate_only":
                        raise IntentError(
                            f"{r.get('op')}: only {actor.name} ({ref}) answers here; "
                            f"write {ref} as the actor, or leave the act out.", "legality")
                    params = r.get("params") if isinstance(r.get("params"), dict) else {}
                    if r.get("op") == "check" and "dc" in params:
                        raise IntentError(
                            f"check: {actor.name}'s try names who could stop it "
                            f'("opposed_by": {{"ref": "<ref>", "skill": "<skill>"}}), '
                            f"never a DC.", "schema")
                turned = (companions.turning_on_the_party(scene, ref, raw)
                          or companions.attack_against_its_reason(ref, raw))
                if turned:
                    raise IntentError(turned, "legality")
                intents = self.engine.validate(raw or [{"op": "narrate_only"}])
            except (ValueError, IntentError) as exc:
                rejections.append(f"attempt {n + 1}: {exc}")
                messages = _with_correction(base, reply.text, str(exc))
                continue
            narration = judgement.name_refs(
                self._lift(str(data.get("narration", "")).strip()), scene)
            # How they do it shows who they are (the owner's second ruling, 2026-10-01):
            # detected, and repaired with one targeted call when the answer reads as if
            # anybody could have given it.
            narration, manner_notes, more = self.manner_of(
                narration, actor, ordered=True,
                op=intents[0].op if intents else "", whole=True)
            attempts.extend(more)
            return TurnPlan(narration=narration, intents=intents, attempts=attempts,
                            rejections=rejections, repairs=manner_notes)
        raise IntentError(f"{actor.name} could not answer in {max_attempts} attempts:\n"
                          + "\n".join(rejections))

    def manner_of(self, text: str, actor, *, ordered: bool, op: str = "",
                  whole: bool = False) -> tuple[str, list[str], list[Attempt]]:
        """A companion's deed on the page carries their manner, or is repaired to.

        The owner's second ruling (2026-10-01): "they can comply but it should be narrated
        that they did so in a way that was timid and matched their background." Detected
        mechanically (`companions.shows_manner`, a cue lexicon per temperament); when no
        cue is there, ONE call rewrites only the companion's own sentences — the pattern
        of `_answer_the_question` and `_show_declared`: a backstop under the prose, kept
        only when it holds. Each rewritten sentence must leave the act as it was
        (`companions.act_kept`: the same deed words, nobody added, no blow landed that was
        not), and the result must carry a cue; otherwise the passage stands as written
        and the note says so. A companion whose temper owes no deed-cue owes nothing.

        `whole`: the passage is all theirs (their own fight turn or answer), so when no
        sentence names them the first sentences are theirs anyway."""
        from . import companions

        scene = self.engine.scene
        pole = companions.dominant_pole(scene, actor)
        if not pole or not str(text or "").strip():
            return text, [], []
        if companions.shows_manner(text, actor, pole, whole=whole):
            return text, [f"manner: {actor.name} ({pole}) shown"], []
        mine = companions.their_sentences(text, actor)
        if not mine and whole:
            mine = narration_mod._sentences(text)[:2]
        mine = mine[:3]
        if not mine:
            return text, [], []
        line = companions.manner_line(scene, actor, ordered=ordered, op=op)
        try:
            reply = client.chat(
                prompts.manner_repair_messages(mine, actor.name, line, pole),
                self.prose_model, self.prose_host, as_json=True, think=False,
                temperature=0.5, num_predict=120 + 90 * len(mine),
                provider=self.prose_provider, api_key=self.prose_key,
                schema=mentions_mod.repair_schema(len(mine)))
            attempt = Attempt("manner", reply.seconds, reply.model, reply.text,
                              note=f"manner: {actor.name} ({pole})")
            got = reply.json() or {}
        except Exception as exc:  # noqa: BLE001 — a failed repair must not lose the turn
            return text, [f"manner: {actor.name} ({pole}) not shown — the call failed "
                          f"({type(exc).__name__}); kept as written"], []
        people = list(scene.actors.values())
        fixed, why = text, []
        for i, old in enumerate(mine, 1):
            new = " ".join(str(got.get(f"s{i}") or "").split())
            reason = companions.act_kept(old, new, actor, people)
            if reason or old not in fixed:
                why.append(reason or "sentence moved")
                continue
            fixed = fixed.replace(old, new, 1)
        if fixed == text or not companions.shows_manner(fixed, actor, pole, whole=whole):
            return text, [f"manner: {actor.name} ({pole}) not shown — the rewrite did not "
                          f"hold ({'; '.join(why) or 'still no cue'}); kept as written"], \
                [attempt]
        return fixed, [f"manner: {actor.name} ({pole}) not shown — rewrote "
                       f"{len(mine) - len(why)} sentence(s)"], [attempt]

    def companion_interject(self, ref: str, facts: str, *, known: set[str] | None = None,
                            max_attempts: int = 2) -> tuple[str, list[Attempt], list[str]]:
        """A companion speaks up, unasked: one line in their voice about the moment or
        the place (the owner, 2026-10-01: "they should also interject their opinions on
        the things going on or the places we go"). WHEN is code's
        (`companions.interjection_due`); this writes WHAT, from `facts` — who they are,
        what it is about, who is here — and holds it mechanically to: their words in
        quotation marks, their name on it, short, no number, no name the world does not
        know, no question or advice that hands the player their next move. A second try is
        told what was wrong with the first; a line that never holds is not spoken.

        Returns (line, attempts, rejections); line is "" when nothing held."""
        from . import companions

        actor = self.engine.scene.actors[ref]
        known = set(known or ()) | self._known_names()
        messages = prompts.interject_messages(facts)
        attempts: list[Attempt] = []
        rejections: list[str] = []
        for n in range(max_attempts):
            try:
                reply = client.chat(
                    messages, self.prose_model, self.prose_host, as_json=True,
                    think=False, temperature=0.8, num_predict=200,
                    provider=self.prose_provider, api_key=self.prose_key,
                    schema=prompts.interject_schema())
            except Exception as exc:  # noqa: BLE001 — an unspoken remark costs nothing
                rejections.append(f"attempt {n + 1}: the call failed ({type(exc).__name__})")
                break
            attempts.append(Attempt("interject", reply.seconds, reply.model, reply.text,
                                    note=f"interject: {actor.name}"))
            try:
                line = " ".join(str((reply.json() or {}).get("line") or "").split())
            except ValueError:
                line = ""
            line = judgement.name_refs(line, self.engine.scene) if line else ""
            why = companions.interjection_refusal(line, actor, known)
            if not why:
                return line, attempts, rejections
            rejections.append(f"attempt {n + 1}: {why}: {line[:120]!r}")
            messages = messages + [
                {"role": "assistant", "content": reply.text},
                {"role": "user", "content": f"That line {why}. Write it again."}]
        return "", attempts, rejections

    def companion_confide(self, ref: str, facts: str, plan: dict, *,
                          known: set[str] | None = None,
                          max_attempts: int = 2) -> tuple[str, list[Attempt], list[str]]:
        """A companion says something of their own life: a lead-in, a hint, the share, or
        a bridge from something in the world (the owner's ruling of 2026-10-01; WHEN and
        which is `confide.due`'s). Shown only the asked-for kind's demonstrations; held by
        `confide.refusal` — a lead-in that says what it is, a share that says something
        else, a bridge that forgets what brought it up, a number, an invented name. One
        targeted repair naming what was wrong; a line that never holds is not said, and
        whatever was owed stays owed.

        Returns (line, attempts, rejections); line is "" when nothing held."""
        from . import companions as companions_mod, confide
        from rules import population

        actor = self.engine.scene.actors[ref]
        rec = population.of_ref(self.engine.scene, ref)
        known = set(known or ()) | self._known_names()
        messages = prompts.confide_messages(facts, plan["kind"])
        attempts: list[Attempt] = []
        rejections: list[str] = []
        for n in range(max_attempts):
            try:
                reply = client.chat(
                    messages, self.prose_model, self.prose_host, as_json=True,
                    think=False, temperature=0.8, num_predict=240,
                    provider=self.prose_provider, api_key=self.prose_key,
                    schema=prompts.interject_schema())
            except Exception as exc:  # noqa: BLE001 — an unsaid confidence costs nothing
                rejections.append(f"attempt {n + 1}: the call failed ({type(exc).__name__})")
                break
            attempts.append(Attempt("confide", reply.seconds, reply.model, reply.text,
                                    note=f"confide: {actor.name} ({plan['kind']})"))
            try:
                line = " ".join(str((reply.json() or {}).get("line") or "").split())
            except ValueError:
                line = ""
            line = judgement.name_refs(line, self.engine.scene) if line else ""
            why = confide.refusal(line, actor, known, plan, rec,
                                  others=[a for a in self.engine.scene.actors.values()
                                          if a is not actor and companions_mod.is_companion(a)])
            if not why:
                return line, attempts, rejections
            rejections.append(f"attempt {n + 1}: {why}: {line[:160]!r}")
            messages = messages + [
                {"role": "assistant", "content": reply.text},
                {"role": "user", "content": f"That line {why}. Write it again."}]
        return "", attempts, rejections

    def _context_note(self) -> list[str]:
        """What the context budget left out this turn, for the log and the GM view.

        Silence here is the whole defect being fixed: before `prompts.pack`, the turn
        overflowed the window at turn 46 and Ollama cut it — the worked examples first,
        then one exchange of play per turn — reporting nothing to anyone.
        """
        packed = getattr(self, "packed", None) or {}
        if not packed.get("dropped"):
            return []
        note = (f"context budget: dropped the oldest {packed['dropped']} message(s), "
                f"kept {packed['kept']}")
        if not packed.get("examples"):
            note += "; the worked examples did not fit either"
        return [note]

    def _current_enemy(self) -> str | None:
        """Who the worked examples' {Current Enemy} placeholder should become.

        The first conscious combatant on a side the PC is not on, while a fight is
        declared; otherwise nobody, and the fill falls back to "stranger". Named from
        the sides rather than from `kind`, because the sides are what the fight itself
        declared hostile.
        """
        scene = self.engine.scene
        pc = scene.pc()
        if not scene.in_encounter or pc is None:
            return None
        for side, refs in scene.sides.items():
            if pc.ref in refs:
                continue
            for ref in refs:
                foe = scene.actors.get(ref)
                if foe is not None and foe.hp > 0:
                    return foe.name
        return None

    # --- The prose itself ------------------------------------------------------------

    def _echo_index(self):
        if getattr(self, "_echoes", None) is None:
            # Filled with the fallback word, not the raw token: the index wants the
            # phrasing around the placeholder, and "{Current Enemy}" never appears in
            # a reply — only whatever it was filled with does.
            # And with the speaker tags lifted, as every reply is before this reads it:
            # a phrase running across `<say who=c1 to=you>` would match nothing.
            self._echoes = narration_mod.build_echo_index(
                *[speech_mod.lift(prompts.fill_enemy(e["reply"]["narration"], None))[0]
                  for e in prompts.EXAMPLES],
                *[speech_mod.lift(prompts.fill_enemy(e["reply"]["narration"], None))[0]
                  for e in prompts.NPC_EXAMPLES],
            # The companion examples too: a companion's turn is shown them in place of
            # the creature ones, and a copied line is as much a defect there.
            *[prompts.fill_companion(e["reply"]["narration"], self_ref="c1",
                                     name="stranger", foe_ref="c2", foe="stranger")
              for e in prompts.COMPANION_EXAMPLES],
                prompts.CONSEQUENCE_EXAMPLE["assistant"],
            )
        return self._echoes

    def _known_names(self) -> set[str]:
        """Every name the GM is entitled to use.

        The scene's people, the place and everything containing it, and the world's own
        entities. Anything else in the prose is invented, which is the failure "ground
        every name" exists to catch.
        """
        names = {a.name for a in self.engine.scene.actors.values()}
        names |= {a.heritage for a in self.engine.scene.actors.values() if a.heritage}
        # And the race — the homebrew card sits in `race` with `heritage` blank, and
        # "Asura" was struck as an invented person (2026-09-18) — plus the true names
        # the scene holds behind its descriptors, so a stranger giving his name is not
        # un-named in his own line.
        for a in self.engine.scene.actors.values():
            if a.race:
                names.add(str(a.race).title())
                names.add(str(a.race))
            doc = a._race_doc() if hasattr(a, "_race_doc") else None
            if doc and doc.get("name"):
                names.add(str(doc["name"]))
            if getattr(a, "true_name", ""):
                names.add(a.true_name)
                names |= set(a.true_name.split())
        try:
            world = self.world
            names |= {e.name for e in world.entities.values()}
            names |= {u["name"] for u in world.unwritten}
            names |= {f["name"] for c in world.chronology for f in c.figures}
            # `c.name`: chronology entries are `world.loader.Event` dataclasses. This read
            # `c["name"]` from 2026-08-20, raised TypeError on every call, and the bare
            # `except: pass` below hid it — so every name after this line, every FACTION
            # and the world's own name, was never on the list, and the un-namer was free
            # to strike them as invented. Found 2026-09-25 by the log line that replaced
            # the `pass`, the first time a recording ran.
            names |= {c.name for c in world.chronology}
            names |= {f["name"] for f in world.factions}
            names.add(world.name)
        except Exception:
            # Logged, not passed over: with the world's names missing, the un-namer
            # strips REAL names from the prose as inventions, and nothing said why
            # (2026-09-25).
            import logging

            logging.getLogger("pathfindergm").exception(
                "the world's names could not be read; real names may be un-named")
        # And every capitalised word the world's own prose uses. Titles alone are not the
        # world's vocabulary: measured across two 60-turn runs, `invented-name` fired on
        # 31 tokens and only four were real inventions. The rest were the world's own —
        # Council (184 uses in its prose), Valtorian (107), Kelvaxian (82), Elders (30) —
        # none of which is an *entity*, all of which the world says constantly.
        #
        # Every one of those cost a repair call and asked `polish` to strip real world
        # detail out of the prose, so the check meant to stop invented names was quietly
        # deleting true ones. 940 words for this world, and it contains none of Keldor,
        # Thalassk or Zorath, which were the genuine inventions.
        names |= self._world_vocabulary()
        # And what the player is actually carrying. "Musk Muddle Tincture" is a jar in
        # her own satchel, and `Tincture` was reported as a person the moment she sold
        # one — the catalogue vocabulary covers materials the world sells, not things a
        # character crafted, and the narrator is entitled to name what it can see.
        for actor in self.engine.scene.actors.values():
            for item in (getattr(actor, "stock", {}) or {}).values():
                names.add(str(getattr(item, "name", "")))
                names.add(str(getattr(item, "base", "")))
            # And the spells they can cast. "Prestidigitation" was reported as an
            # invented person the first time one was cast — it is in the app's own spell
            # list, and a wizard naming a spell she has in her book is not inventing
            # anybody. Only what this character knows, not all 3,040: a name is grounded
            # because *she* has it, not because a rulebook somewhere prints it.
            for sid in (list(getattr(actor, "spellbook", []) or [])
                        + list(getattr(actor, "prepared", {}) or {})):
                names.add(str(sid).replace("-", " "))
        names |= self._engine_place_names()
        return {n for n in names if n}

    def _engine_place_names(self) -> set[str]:
        """The places the engine itself made or offers, by name.

        Measured on the 2026-09-30 playtest (item 11): the Velvet Veil was a place the
        player founded (`scene.founded`), and none of the engine's own places were on the
        known list — only the world's entities were — so "Velvet" read as an invented name
        and the un-namer printed "the stranger Veil" twice. The places are the brief's
        own (`engine.places()`, which carries the founded and ventured ground), every
        founded place in any settlement, the exits row's destinations
        (`play.exits.ways_from`, the roads' far ends) and the counters' labels at this
        settlement's market. Each source is read on its own: one that fails costs only
        its names."""
        import logging

        log = logging.getLogger("pathfindergm")
        scene = self.engine.scene
        names: set[str] = set(self._place_names())
        for p in getattr(scene, "founded", None) or []:
            if isinstance(p, dict) and p.get("name"):
                names.add(str(p["name"]))
        try:
            from play.exits import ways_from

            for rows in ways_from(self.engine, self.world, [scene.at]).values():
                names |= {str(r.get("name") or "") for r in rows}
        except Exception:  # noqa: BLE001 — a missing exits row is a missing name, no more
            log.debug("known names: the exits row could not be read", exc_info=True)
        try:
            from rules import market

            location = self.world.get(scene.location_id) if self.world else None
            if location is not None:
                for counter in market.counters(location):
                    names |= {str(counter.label or ""), str(counter.title or "")}
        except Exception:  # noqa: BLE001
            log.debug("known names: the counters could not be read", exc_info=True)
        return {n for n in names if n}

    _VOCAB: dict[int, set[str]] = {}
    _CAPITALISED = re.compile(r"\b[A-Z][a-zA-Z'’-]{2,}\b")

    def _world_vocabulary(self) -> set[str]:
        """Capitalised words the world file itself uses, cached per world.

        Cached because it is a walk over every entity's prose and the answer only changes
        when the world file does, which does not happen while the app is running.
        """
        world = self.world
        key = id(world)
        if key in GMAgent._VOCAB:
            return GMAgent._VOCAB[key]

        found: set[str] = set()
        try:
            chunks = [world.name or "", str(world.secret or "")]
            chunks += [str(v) for v in (world.premise or {}).values()]
            for e in world.entities.values():
                chunks += [e.name or "", str(getattr(e, "summary", "") or ""),
                           str(getattr(e, "prose", "") or "")]
                chunks += [str(v) for v in (getattr(e, "facts", {}) or {}).values()]
                for s in (getattr(e, "sections", []) or []):
                    chunks.append(str(s if isinstance(s, str) else s.get("text", "")))
            for chunk in chunks:
                found |= set(GMAgent._CAPITALISED.findall(chunk))
                # Every word the world uses, in lowercase: a capitalised token is
                # invented only if its lowercase form appears nowhere in the world's
                # text. "the Reeve's men" was struck (2026-09-18, item 11) because the
                # export says "reeve" in lowercase and the model title-cased it — the
                # same class as the Council/Elders false positives, 27 of 31 flags.
                # `invented_names` lowercases what it is handed, so these plain words
                # are allowed by the same comparison the names are.
                found |= {w for w in re.findall(r"[a-z][a-z'-]{3,}", chunk.lower())}
        except Exception:
            pass
        # And the things the game itself ships. "Hypericum" and "Wolfweed" were reported
        # as invented people: they are herbs in `content/ingredients`, which the narrator
        # is entitled to name and which no *world* file mentions. A shelf the app carries
        # is not a name from nowhere.
        try:
            from rules import ingredients as ing_mod

            for i in ing_mod.all_ingredients().values():
                found |= set(GMAgent._CAPITALISED.findall(str(getattr(i, "name", ""))))
        except Exception:
            pass
        try:
            from rules import market as market_mod

            for m in market_mod.everything_priced():
                found |= set(GMAgent._CAPITALISED.findall(str(getattr(m, "name", ""))))
        except Exception:
            pass
        GMAgent._VOCAB[key] = found
        return found

    def _pc_pronouns(self) -> str:
        pc = self.engine.scene.pc()
        return str(getattr(pc, "pronouns", "") or "") if pc else ""

    def _pc_gender(self) -> str:
        """What they are, which the second person never says. See `narration.wrong_body`."""
        pc = self.engine.scene.pc()
        return str(getattr(pc, "gender", "") or "") if pc else ""

    def _other_names(self) -> tuple:
        """Everybody in the scene who is not the player, so a pronoun near their name
        is not read as one of the player's."""
        return tuple(a.name for a in self.engine.scene.actors.values()
                     if not a.is_pc and a.name)

    def _here_name(self) -> str:
        """The name of the place the party is standing in, as the engine holds it."""
        try:
            here = self.engine.here()
        except Exception:      # noqa: BLE001 — a scene with no location has no answer
            return ""
        return str(getattr(here, "name", "") or "")

    def _place_names(self) -> tuple:
        """Every place that exists where the party is, by name — the same list the brief
        states as "THE PLACES HERE (the only ones that exist)". Two readers of one fact:
        the model is told them, and the review checks the prose against them."""
        try:
            return tuple(str(p.name) for p in self.engine.places() if p.name)
        except Exception:      # noqa: BLE001
            return ()

    def _body_count(self) -> dict:
        """Who is standing and who is whole, for the prose reviewer to check against.

        Read off the engine at the moment the prose is judged, never carried forward:
        the whole point is that it is the authority. `alive` means conscious and on
        their feet; `hurt` means anything has actually touched them, which includes
        conditions, so a narrator may say a held creature is straining and may not say
        an untouched one is bleeding.

        The PC is left out. `second_person_narrator` owns how the player is written and
        a player reading "you collapse" about their own 70 hit points has a different
        complaint from the one this answers.
        """
        out = {}
        for ref, a in self.engine.scene.actors.items():
            if a.is_pc or not a.name:
                continue
            try:
                alive = self.engine.scene.conscious(ref)
            except Exception:
                alive = (a.hp or 0) > 0
            # A role (`bystander`) is a condition on the sheet and not a wound: it
            # must not let the prose bleed an untouched merchant.
            touched = [c for c in (getattr(a, "conditions", None) or [])
                       if not str(getattr(c, "key", "")).startswith("bystander")]
            hurt = ((a.hp or 0) < (a.hp_max or 0)
                    or bool(touched)
                    or bool(getattr(a, "nonlethal", 0)))
            out[a.name] = {"alive": bool(alive), "hurt": bool(hurt)}
        return out

    def _alone(self) -> bool:
        """Whether the player has nobody standing beside them.

        Deliberately generous about what counts as company: anybody else still on their
        feet, friend or foe, and the check stays quiet. Only when the player is the last
        one upright is "your companion's next swing" certainly an invention — which is
        exactly the scene it was measured in, a tavern with one thug at -5 hp.
        """
        others = [a for r, a in self.engine.scene.actors.items()
                  if not a.is_pc and not a.is_down]
        return not others

    def _groom(self, text: str, *, earlier: list[str] | None = None,
               min_chars: int = 0, max_chars: int = 0, player_input: str = "",
               brief: str = "", hand_back: bool = True, claims: bool = True,
               rewrite: bool = True, backed=(),
               deaths: list[dict] | None = None,
               pull: dict | None = None,
               claim: str = "",
               blows: list[dict] | None = None,
               cast: list[str] | None = None,
               fire_context: str | None = None,
               facts: list[str] | None = None,
               acting: str = "",
               changes: list[dict] | None = None,
               ctx: "BeatContext | None" = None,
               outcomes: list | None = None) -> tuple[str, list[str], list[Attempt]]:
        """Every mechanical treatment a piece of GM prose gets, in one place.

        `acting` names the creature whose turn this prose is, on an NPC's turn; empty on
        the player's. It arms the `wrong-actor` check and its repair.

        `ctx` is the beat as the narrator checks read it (gm/checks, `BeatContext`), built
        by each of the four callers. With it, the registered checks run once the
        attribution exists (`_truth_pass`); without it — a test, a tool — they do not run
        and nothing else changes.

        `changes` is this turn's effect records (`_changes_from`): what left a hand and
        what condition landed, so the state-claims check can tell reporting from
        invention. None before the dice — setup prose and an NPC's opener — where
        nothing has changed yet and every drop or stun the prose writes is its own.

        There used to be four copies of this chain and they had drifted — the census over
        all seven saved campaigns found that `npc_turn` prose reached the transcript with
        no review at all, and the consequence call had no third-person check for months.
        One rule, one home, per CLAUDE.md's own law about rules with more than one copy.

        Order matters and is deliberate:
          1. `destutter` first, so every sentence-splitting detector below reads repaired
             punctuation — the stray period in "My chest is. muscular" once broke the
             ownership detector itself.
          2. `drop_repeated_beats` before review, so the length floor and the hand-back
             backstop judge the post-cut text.
          3. the claim repair, then the one model rewrite (`polish`).
          4. the deterministic backstops, which run whether or not the rewrite landed —
             46% of everything the reviewer caught used to ship anyway, because the
             rewrite losing was the end of the road.
        """
        repairs: list[str] = []
        attempts: list[Attempt] = []
        if not text:
            return text or "", repairs, attempts

        text, bled = narration_mod.cut_schema_bleed(text)
        if bled:
            repairs.append(f"schema bled into the prose: cut from {bled[0]!r}")
        text, tagged = narration_mod.strip_ref_tags(text)
        if tagged:
            repairs.append(f"the brief's refs on the page: stripped {tagged}")
        text = narration_mod.destutter(text)
        text, cut = narration_mod.drop_repeated_beats(text, earlier)
        if cut:
            repairs.append(f"repeated beats: cut {cut}")
        text = judgement.name_refs(text, self.engine.scene)
        cast = " ".join(a.name for a in self.engine.scene.actors.values())
        text = narration_mod.strip_example_cast(text, f"{player_input} {cast}")
        if claims:
            text, claim_repairs, claim_attempts = self._repair_outcome_claims(
                text, backed, restrained=self._anyone_held())
            repairs += claim_repairs
            attempts += claim_attempts

        # A legacy campaign's woven-in people count as known from here down, so the
        # reviewer stops burning rewrites on Vorgath and the un-namer leaves him be.
        extra = narration_mod.established_names(earlier)
        if rewrite:
            text, p_repairs, p_attempts = self.polish(
                text, earlier=earlier, min_chars=min_chars, max_chars=max_chars,
                player_input=player_input, scene_brief=brief, extra_known=extra,
                facts=facts,
                deaths=deaths, pull=pull, claim=claim, blows=blows,
                # What could have lit anything: the place's brief and the recent
                # beats. None when the caller had no brief (a consequence line),
                # and the fire finding is not judged.
                fire_context=(" ".join([brief] + list(earlier or []))
                              if brief else fire_context))
            repairs += p_repairs
            attempts += p_attempts

        # Who every person the beat mentions is, declared once for the checks below to
        # read instead of guessing from names (gm/mentions.py). After the rewrite, which
        # is the last thing to change most of the text; a sentence cut or rewritten
        # after this is not in the attribution, and the checks fall back to their guess.
        self.attribution = mentions_mod.attribute(
            text, self.engine.scene, acting=acting, facts=facts,
            model=self.prose_model, host=self.prose_host,
            provider=self.prose_provider, api_key=self.prose_key)
        if self.attribution.mentions:
            self.mention_rows.append(self.attribution.as_log())
        # The narrator checks (gm/checks): here and not inside `review()`, because
        # `review()` runs only in `polish`, only when there is a rewrite, and before this
        # attribution exists (docs/fix-interfaces.md §1.1 P2). The context is brought up
        # to the draft as it now stands, with what the rewrite's tags said.
        if ctx is not None:
            from dataclasses import replace

            ctx = replace(ctx, text=text, attribution=self.attribution,
                          said=tuple(dict(r) for r in self.last_said))
            text, truth, truth_attempts = self._truth_pass(ctx)
            repairs += truth
            attempts += truth_attempts
        # A name on the wrong person — the words name one man, the sentence is about
        # another: one targeted rewrite (stage 3 of the note).
        if self.attribution.misnamed():
            text, fixed, fix_attempts = self._repair_misnamed(text, self.attribution)
            repairs += fixed
            attempts += fix_attempts
        attribution = self.attribution
        # A broken construct (the owner's house rule, 2026-10-01) is as inert as a corpse:
        # at exactly 0 hp the "hp < 0" test missed it, and a replay's broken spy tilted its
        # head and glowed on the page.
        dead_refs = {r for r, a in self.engine.scene.actors.items()
                     if not a.is_pc and (a.hp < 0 or a.has_state("state.down.dead") or a.has_state("state.down.broken"))}

        def _alive(sentence: str, words: str) -> bool:
            ref = attribution.who(sentence, words)
            return ref is not None and ref not in dead_refs

        # Before the stranger-renamer, which once half-mangled a leaked option list
        # into "the stranger: * the onlooker off your opponent * ..." — cutting the
        # leak first means there is nothing garbled left to rename.
        # `state.down.dead`, the leaf and not the family: this cuts any sentence in
        # which a named actor does something a corpse could not, so widening it to
        # `state.down` would stop an unconscious NPC stirring or groaning and stop a
        # petrified one being carried. What was missing is the other direction — a
        # Constitution-drained corpse at full hit points, which `hp <= 0` cannot see,
        # and which went on acting in every paragraph for the rest of the session.
        dead = [a.name for r, a in self.engine.scene.actors.items()
                if not a.is_pc and (a.hp < 0 or a.has_state("state.down.dead") or a.has_state("state.down.broken"))]
        # Whoever died THIS turn keeps their killing sentence (see the function): the
        # cut used to delete "the sailor crumples to the deck" as a dead man acting,
        # which is how every one-punch kill ended in the same appended template.
        # And the living beside them: a name the dead share with somebody standing is not
        # a corpse acting (two "thug"s, one dead — the 2026-09-27 fight audit).
        living = [a.name for a in self.engine.scene.actors.values()
                  if not a.is_pc and not (a.hp < 0 or a.has_state("state.down.dead") or a.has_state("state.down.broken"))]
        text, risen = narration_mod.cut_dead_men_walking(
            text, dead, fresh=[str(d.get("name") or "") for d in (deaths or [])],
            living=living, spare=_alive)
        # A claim the engine holds false, written as true anyway: the sentences that
        # make the player a god are cut and the world's answer is written in their
        # place, from a pool that never repeats twice running. The rewrite above had
        # its chance; this is the backstop under it.
        if claim:
            text, granted = narration_mod.cut_granted_nature(
                text, claim, self._other_names(), said=self.engine.scene.said)
            if granted:
                repairs.append(f"the claim was made true: cut {len(granted)} sentence(s) "
                               f"and wrote the world's answer")
        if risen:
            repairs.append(f"the dead stayed dead: cut {len(risen)} sentence(s)")
        # A door the dice held, opened anyway after the rewrite: cut from the opening on.
        text, forced = narration_mod.hold_the_door(text, getattr(self, "doors", None))
        if forced:
            repairs.append("the door stayed shut: cut the beat from where the prose opened it")
        # A purchase settled in the prose, after the rewrite: the handing-over is cut and
        # the keeper showing the goods is kept (the screen is where the coin moves).
        text, handed = narration_mod.keep_the_goods(text, getattr(self, "buying", ""))
        if handed:
            repairs.append(f"the sale waits for the screen: cut {len(handed)} sentence(s)")
        text, leaked = narration_mod.strip_leaked_options(text)
        if leaked:
            repairs.append(f"option menu leaked into prose: cut {len(leaked)} "
                           f"sentence(s)")
        # A name somebody gives is the one the world holds for them — settled BEFORE
        # the un-namer, which struck "Kaelen" inside the stranger's own introduction
        # (2026-09-18). The expected names are the true names behind the descriptors.
        expected = {}
        for a in self.engine.scene.actors.values():
            if not a.is_pc and getattr(a, "true_name", "") and a.true_name != a.name:
                for w in narration_mod._name_stems(a.name) if hasattr(narration_mod, "_name_stems") else []:
                    expected[w] = a.true_name
                expected.setdefault((str(a.name).split() or [""])[-1].lower(), a.true_name)
        text, settled = narration_mod.settle_introductions(
            text, expected,
            # What the story has already said: a name the player was told earlier is
            # not swapped out for the pool's when its bearer finally says it.
            established=" ".join(str(b) for b in (earlier or [])))
        if settled:
            repairs.append(f"the name given is the world's: {', '.join(settled)}")
        # Asked for his name and the beat gave none: he says it himself. The brief was
        # told the name this turn, through the `names_for` argument the view fills from
        # `names_asked_for`; this is the backstop under that — a model with nothing to
        # give refuses, and a refusal
        # for no reason is the bug reported on 2026-09-19. Only the willing get a line —
        # `names_asked_for` returns "" for anyone whose attitude refuses.
        offers = []
        for ref, given in judgement.names_asked_for(self.engine.scene, player_input).items():
            who = self.engine.scene.actors.get(ref)
            if given and who is not None:
                offers.append((str(who.name), given))
        text, told = narration_mod.give_the_name(text, offers)
        if told:
            repairs.append(f"asked and not answered: {', '.join(told)} gives their name")
        # Asked something, and the beat stopped before the answer (owner, 2026-10-01):
        # one small call for the spoken answer alone. After every cut above — in both
        # measured cases our own grooming lost the answer — and before the un-namer, so
        # a name the answer invents is held to the world like any other. Player turns
        # only, and only where a rewrite is allowed at all.
        if rewrite and not acting and player_input and player_input != prompts.CARRY_ON:
            asked = self._who_was_asked(player_input)
            if asked is not None and not narration_mod.answered(
                    text, asked.ref, self.last_said, player_input):
                text, answer_notes, answer_attempts = self._answer_the_question(
                    text, asked, player_input, brief)
                repairs += answer_notes
                attempts += answer_attempts
        # Declared, and the beat picked up after it (owner, 2026-10-01): a deed the player
        # wrote that is nowhere on the page is written, as it played out, where it
        # happened. The same place as the answer and for the same reasons — after every
        # cut, before the un-namer — and only on the player's own turn prose, the one
        # caller that hands over the turn's `outcomes`.
        if (rewrite and not acting and outcomes is not None and player_input
                and player_input != prompts.CARRY_ON):
            owed = self._deeds_owed(player_input, outcomes)
            unshown = narration_mod.unshown_deeds(text, owed)
            if unshown:
                text, deed_notes, deed_attempts = self._show_declared(
                    text, unshown, player_input, earlier=earlier, brief=brief,
                    facts=facts, known=self._known_names() | extra,
                    shown=[d for d in owed if d not in unshown])
                repairs += deed_notes
                attempts += deed_attempts
        # A band the ledger booked keeps the word it was booked under: soldiers do not
        # become raiders between one paragraph and the next (2026-09-19, item 30). Before
        # the un-namer, which works on names rather than roles.
        text, drifted = judgement.hold_the_booked_word(self.engine.scene, text)
        if drifted:
            repairs.append(f"the word they were booked under: {', '.join(drifted)}")
        known = self._known_names() | extra
        text, unnamed = narration_mod.unname_strangers(text, known)
        if unnamed:
            repairs.append(f"people from nowhere: un-named {', '.join(unnamed)}")
        if narration_mod.narrator_in_first_person(text):
            text, fp = narration_mod.second_person_narrator(text)
            if fp:
                repairs.append(f"narrator in the scene: swapped {', '.join(fp)}")
        # A creature's turn told as somebody else's — before the swap below, which would
        # otherwise turn "swinging your blade toward Kesst Vayr" into "toward you" and
        # hide the inversion inside a sentence that reads as sound.
        if acting:
            text, turned, turn_attempts = self._repair_wrong_actor(text, acting, facts)
            repairs += turned
            attempts += turn_attempts
        pc = self.engine.scene.pc()
        if pc is not None:
            text, named = narration_mod.pc_to_second_person(text, pc.name)
            if named:
                repairs.append(f"the player narrated by name: {named} swap(s) "
                               f"to second person")
        # What a hand holds and a body suffers, set against the state and this turn's
        # effect records (gm/state_claims.py). After the name swap, so "your" is the
        # player's; after the rewrite, so the prose it judges is the prose that ships.
        text, held, held_attempts = self._repair_state_claims(text, changes)
        repairs += held
        attempts += held_attempts
        # Agency is a fact of the tell. When every blow this turn was somebody else's
        # and the prose still swings the player's blade, the sentences go and the
        # plain tell stands — the free backstop under `wrong-hands`, the one that
        # runs on the NPC turn where the rewrite never does.
        text, handed = narration_mod.right_hands(text, blows)
        if handed:
            repairs.append(f"wrong hands: cut {len(handed)} sentence(s) that gave the "
                           f"player somebody else's blow")
        # And a spell the engine did not cast: cut, the same shape and for the same reason.
        # The engine is the only thing that casts a spell, so prose asserting one it did
        # not cast is asserting an outcome that never happened — measured on the player's
        # own screen, a level 1 cleric's "wall of flame at 6th level" with the slots panel
        # still reading full afterwards (item 25).
        text, uncast = narration_mod.cut_uncast_spells(text, cast)
        if uncast:
            repairs.append(f"a spell nobody cast: cut {len(uncast)} sentence(s)")
        # And a blow landed on the turn the fight was only declared: cut, the
        # declaration standing in its place.
        text, early = narration_mod.cut_premature_blows(text, blows)
        if early:
            repairs.append(f"swing not yet struck: cut {len(early)} sentence(s) that "
                           f"landed a blow before any die was rolled")
        # Fire with nothing to light it, when the rewrite left it standing: cut. Judged
        # only with a brief in hand, the same gate the finding has.
        lit_by = (" ".join([brief] + list(earlier or [])) if brief else fire_context)
        if lit_by is not None:
            text, lit = narration_mod.cut_fire_from_nowhere(text, lit_by)
            if lit:
                repairs.append(f"fire from nowhere: cut {len(lit)} sentence(s)")
        text, outsourced = narration_mod.fix_hand_back(text)
        if outsourced:
            repairs.append(f"asked the player to narrate: replaced {outsourced!r}")
        if hand_back:
            text, added = narration_mod.ensure_hand_back(text)
            if added:
                repairs.append("no hand-back: added the question")
        text, swapped = narration_mod.right_body(text, self._pc_gender(),
                                                 self._other_names())
        if swapped:
            repairs.append(f"wrong body: replaced {', '.join(swapped)}")
        # The player is never "the beast" in narration when everyone else here is a
        # person: the noun can only mean them, and their name is what it becomes.
        if pc is not None:
            people_only = all(
                (a.from_template in ("guildhand", "watchman", "thug", "") or a.world_entity_id
                 or (a._race_doc() or {}).get("type", "humanoid") in ("humanoid", "outsider", ""))
                and int((a.abilities or {}).get("int", 10) or 10) > 2
                for a in self.engine.scene.actors.values() if not a.is_pc)
            text, beasts = narration_mod.creature_nouns_for_pc(
                text, pc.name, people_only, acting=acting,
                whose=attribution.who, pc_ref=pc.ref)
            if beasts:
                # Into the player's own person, like every other mention of them: this
                # ran after the name swap above, so the name it wrote stayed a name on
                # the page and `third-person-pc` fired on our own repair.
                text, _ = narration_mod.pc_to_second_person(text, pc.name)
                repairs.append(f"the player called a creature: replaced {', '.join(beasts)}")
        # Nobody left standing means nobody "presses forward". Measured: the engine
        # printed "The fight is over" under prose that had officials regaining their
        # composure and pressing forward — combatants the scene never contained. The
        # cut runs only when the scene is genuinely empty of living opposition, so a
        # real second wave (spawned, existing) is never touched.
        alone = not [a for r, a in self.engine.scene.actors.items()
                     if not a.is_pc and not a.is_down]
        if alone:
            text, ghosts = narration_mod.cut_phantom_opposition(text)
            if ghosts:
                repairs.append(
                    f"phantom opposition: cut {len(ghosts)} sentence(s) of enemies "
                    f"who are not in the scene")
        return text, repairs, attempts

    # --- The narrator checks (gm/checks) ------------------------------------------------

    def _beat_context(self, door: str, *, player_input: str, brief: str,
                      outcomes=(), tells=None, pull=None, location=None,
                      acting: str = "") -> "BeatContext":
        """The beat as the narrator checks read it, built at one of `_groom`'s four
        callers. `text` and `attribution` are filled in by `_groom` itself, once the
        draft has been rewritten and attributed.

        What the view hands the agent between turns is read with `getattr`, the way
        `buying` is: `brief_facts` (what each brief section printed) and `attachments`
        arrive from the view in Phase 1 (S3) without any signature here changing."""
        from .checks import BeatContext

        scene = self.engine.scene
        reading = getattr(self, "reading", None)
        if not isinstance(reading, dict) or "error" in reading:
            reading = None
        if location is None:
            location = getattr(self, "_location", None)
        return BeatContext(
            door=door, text="", player_text=str(player_input or ""),
            engine=self.engine, scene=scene, world=self.world, location=location,
            reading=reading, outcomes=tuple(outcomes or ()),
            tells=tuple(str(t) for t in (tells or ())),
            said=tuple(dict(r) for r in self.last_said), attribution=None,
            brief=str(brief or ""),
            brief_facts=dict(getattr(self, "brief_facts", None) or {}),
            pull=pull,
            was_at=str(getattr(self, "_was_at", None) or getattr(scene, "at", "") or ""),
            acting=str(acting or ""), turn=int(getattr(self, "turn", 0) or 0),
            intimate=self._intimate_beat())

    def _ref_named(self, name: str) -> str:
        """The ref of the one person here called `name`; "" when none or several are."""
        if not name:
            return ""
        refs = [r for r, a in self.engine.scene.actors.items() if a.name == name]
        return refs[0] if len(refs) == 1 else ""

    def _truth_pass(self, ctx) -> tuple[str, list[str], list[Attempt]]:
        """Run the registered checks over the beat and hand what they find to the repair.

        Returns (text, repair notes, attempts) — the shape of every other repair `_groom`
        calls, so the notes reach the turn log and the model calls reach the ledger. A
        check that raises costs only its own findings: it is logged as a `check-error`
        row and the turn goes on. The findings themselves are logged as one
        `truth-checks` row per beat, drained into the turn log with the mention rows.
        With no member registered this returns the text untouched and logs nothing.
        """
        from . import checks

        errors: list[dict] = []
        findings = checks.run(ctx, errors=errors)
        self.mention_rows.extend(dict(e, door=ctx.door) for e in errors)
        if not findings:
            return ctx.text, [], []
        text, notes, attempts = self._repair_sentences(ctx.text, findings, ctx)
        self.mention_rows.append({
            "kind": "truth-checks", "door": ctx.door,
            "findings": [{"kind": f.kind, "detail": f.detail,
                          "sentences": list(f.sentences)} for f in findings],
            "repairs": list(notes)})
        return text, list(notes), list(attempts)

    def _repair_sentences(self, text: str, findings: list, ctx
                          ) -> tuple[str, list[str], list[Attempt]]:
        """Repair what the narrator checks found, sentence by sentence.

        The house shape (CLAUDE.md, "detect mechanically, repair with a targeted call"),
        as `_repair_state_claims` has it: each flagged sentence is rewritten ONCE with
        the finding's fact named, and the rewrite is kept only if the member that found
        the fault no longer finds it in the beat with the rewrite in place. What still
        fails goes to that member's deterministic `backstop` (cut, or the engine's own
        sentence), which runs whether or not a rewrite was tried. A finding that names
        no sentence goes straight to its backstop: a whole-passage "make it consistent"
        rewrite is what Re3's own ablation found did nothing (docs/design-a-truth.md §3).

        Heaviest finding first, and at most `_TRUTH_CALLS` model calls a beat — a local
        model's minute is the player's minute; the backstop under every member but
        `face_kept` makes the rest free. Returns (text, notes, attempts).

        **A line of speech is repaired as a speech unit** (2026-09-30 playtest, item 12).
        A flagged string that lies inside a quotation was spliced back with a string
        replace INSIDE the quotation marks, and the rewrite was narration — five
        narration sentences in Gorm Vesper's mouth across beats 51 and 53. So the target
        widens to the quote plus its speech clause (`checks._quotes.unit`: PARC's source,
        cue and content together), and a rewrite that leaves narration in quotes the
        beat did not already have (`narration_in_quotes.quoted_narration`) is refused.
        A member that sets `REWRITE = False` is never sent to the model at all: its
        backstop is the repair."""
        from dataclasses import replace

        from . import checks, speech
        from .checks._page import page_sentences
        from .checks._quotes import unit
        from .checks.narration_in_quotes import quoted_narration

        notes: list[str] = []
        attempts: list[Attempt] = []
        pc = self.engine.scene.pc()
        actors = dict(self.engine.scene.actors)
        calls = 0
        order = sorted(range(len(findings)), key=lambda i: (-int(findings[i].weight or 0), i))
        members = []
        for i in order:
            f = findings[i]
            member = checks.owner_of(f.kind)
            if member is not None and member not in members:
                members.append(member)
            if member is not None and getattr(member, "REWRITE", True) is False:
                continue            # cut-only: the backstop below is the repair
            for sentence in f.sentences:
                if not sentence or sentence not in text:
                    continue
                at = text.find(sentence)
                inner = next(((qa, qb) for qa, qb in speech.spans(text)
                              if qa < at and at + len(sentence) <= qb), None)
                if inner is not None:
                    ua, ub = unit(text, *inner)
                    sentence = text[ua:ub]
                fixed = ""
                if calls < self._TRUTH_CALLS:
                    calls += 1
                    try:
                        reply = client.chat(
                            _truth_repair_messages(sentence, f.fix_hint or f.detail),
                            self.prose_model, self.prose_host, as_json=True, think=False,
                            temperature=0.3, num_predict=240, provider=self.prose_provider,
                            api_key=self.prose_key,
                            schema={"type": "object",
                                    "properties": {"sentence": {"type": "string",
                                                                "maxLength": 500}},
                                    "required": ["sentence"]})
                        attempts.append(Attempt("repair", reply.seconds, reply.model,
                                                reply.text, note=f"truth: {f.kind}"))
                        fixed = self._lift(str(reply.json().get("sentence", "")).strip())
                        if fixed and pc is not None:
                            fixed, _ = narration_mod.pc_to_second_person(fixed, pc.name)
                    except Exception as exc:  # a failed repair must not lose the turn
                        attempts.append(Attempt("repair", 0.0, self.prose_model,
                                                note=f"truth: {f.kind}: failed: {exc}"))
                        fixed = ""
                if not fixed:
                    continue
                candidate = text.replace(sentence, fixed, 1)
                had = {ln for ln, _ in quoted_narration(text, ctx.said, actors)}
                gained = [ln for ln, _ in quoted_narration(candidate, ctx.said, actors)
                          if ln not in had]
                if gained:
                    notes.append(f"{f.kind}: the rewrite put narration in quotes: "
                                 f"{gained[0][:80]!r}")
                    continue
                still = []
                if member is not None:
                    try:
                        still = [g for g in member.find(replace(ctx, text=candidate))
                                 if g.kind == f.kind]
                    except Exception:  # noqa: BLE001 — unjudgeable: keep the original
                        still = [f]
                new = {w for w, _ in page_sentences(fixed)} | {fixed.strip()}
                if any(set(g.sentences) & new or not g.sentences for g in still):
                    notes.append(f"{f.kind}: the rewrite still did it: {fixed[:80]!r}")
                    continue
                text = candidate
                notes.append(f"{f.kind}: {sentence[:80]!r} -> {fixed[:80]!r}")
        # The backstops, over the beat as it now stands: only a member that still finds
        # something is asked, so a rewrite that held costs nothing here.
        for member in members:
            if not callable(getattr(member, "backstop", None)):
                continue
            try:
                left = [g for g in member.find(replace(ctx, text=text))]
            except Exception:  # noqa: BLE001 — a broken member costs its own backstop
                continue
            if not left:
                continue
            try:
                text, cut = member.backstop(replace(ctx, text=text), text, left)
            except Exception as exc:  # noqa: BLE001
                notes.append(f"{left[0].kind}: backstop failed: {type(exc).__name__}")
                continue
            notes += list(cut)
        for i in order:
            f = findings[i]
            member = checks.owner_of(f.kind)
            if member is not None and not callable(getattr(member, "backstop", None)):
                if any(s in text for s in f.sentences):
                    notes.append(f"{f.kind}: no backstop; left as written")
        return re.sub(r"[ \t]{2,}", " ", text or "").strip(), notes, attempts

    # How many sentence rewrites the truth checks may ask for in one beat.
    _TRUTH_CALLS = 3

    # The finding kinds with no deterministic backstop below them — the only ones worth
    # a second model call, because for everything else the backstop repairs for free
    # what the retry would chase. `repeats-an-earlier-beat` left this set the day the
    # cut became mechanical; `no-hand-back` the day the question became appendable.
    _NO_BACKSTOP = frozenset({
        "echoes-the-examples", "misgendered-pc", "formulaic-opening",
        "third-person-pc", "too-short", "too-long-for-a-fight",
        "invented-companion",
        # Prose asserting an outcome the engine did not produce. There is no
        # deterministic repair for it — a sentence saying the guard collapsed cannot be
        # mended by deleting a word — so the rewrite is the only thing that can fix it,
        # and it is the one finding about whether the turn was true rather than how it
        # read.
        "contradicts-the-engine",
        # Stock scene-setting over a square with bodies in it. No deterministic
        # repair either: the opening has to be rewritten, not trimmed.
        "ignores-the-dead",
        # A phrase the narrator keeps reaching for. Cutting a clause out of the middle
        # of a paragraph leaves a hole where a sentence was, so the rewrite is the only
        # repair. `death-left-off-the-page` is deliberately NOT here: it has a
        # deterministic backstop (`press_the_death`), and a kill is nearly always in
        # a fight, where the retry is gated off anyway.
        "recurring-phrase",
        # An open matter the beat should have let show. An appended anchor would be
        # the formula again, so the rewrite is the only repair; the finding is only
        # ever raised out of fights (`views` hands the pick over out of fights only).
        "drops-the-thread",
        # A crowd that saw something and did nothing. Only a rewrite can make somebody
        # act; an appended "the crowd murmurs" would be the anchor formula again.
        "nobody-reacts",
    })

    def polish(self, text: str, earlier: list[str] | None = None,
                min_chars: int = 0, max_chars: int = 0, player_input: str = "",
                scene_brief: str = "",
                extra_known: set[str] | None = None,
                deaths: list[dict] | None = None,
                pull: dict | None = None,
                claim: str = "",
                blows: list[dict] | None = None,
                fire_context: str | None = None,
                facts: list[str] | None = None) -> tuple[str, list[str], list[Attempt]]:
        """A targeted rewrite when the prose breaks a rule about prose.

        Same shape as every fix that has held here: detect mechanically, then ask the
        model to repair only what was found. If the rewrite is no better the original is
        kept — blander prose is worth less than a lost turn.

        One retry, narrowly gated. Measured across the seven saved campaigns, 46% of
        everything the reviewer caught shipped unrepaired, and the losing rewrites were
        the ones handed several findings at once — a model asked for N things answers in
        parallel, which is the five-factions lesson wearing a new hat. The retry names
        ONLY the heaviest finding, and only fires when that finding has no deterministic
        backstop (a backstop repairs for free what the retry would chase) and the scene
        is not a fight (a second ~10s call mid-combat costs more than the finding).
        """
        # The page founds no places (ruled 2026-09-27, option (a) of the declared-not-
        # guessed review): places come from the plan's `found`, the player and venturing
        # out. A beat set somewhere the party is not is `stands-elsewhere` below, and is
        # rewritten to where they are — never kept as a new place.
        made: list[str] = []
        known = self._known_names() | (extra_known or set())
        intimate = self._intimate_beat()
        # Who is alive and unhurt is not judged in an intimate scene between adults.
        # Measured live 2026-10-01 on the first briefed beat: "her body is tense but
        # welcoming" read as Quin Nutmeg "down or dead" (`_FELLED` holds "body", for a
        # corpse), and "cries out", "goes limp", "collapses against you" are the scene's
        # words as much as a wound's. Nobody here is hostile (`intimate.partners`); a
        # death the engine rolls still reaches the page through `press_the_death`.
        bodies = None if intimate else self._body_count()

        def _review(t: str):
            return narration_mod.review(
                t, pc_name=self._pc_name(), echo_index=self._echo_index(),
                known_names=known, earlier=earlier,
                min_chars=min_chars, max_chars=max_chars, alone=self._alone(),
                pronouns=self._pc_pronouns(), others=self._other_names(),
                gender=self._pc_gender(), state=bodies,
                deaths=deaths, pull=pull, claim=claim, blows=blows,
                fire_context=fire_context,
                # The doors this turn forced or picked, and whether they gave.
                doors=getattr(self, "doors", None),
                # The purchase the counter's screen opens for after this beat.
                buying=getattr(self, "buying", ""),
                # Where the party actually is, and what places exist here, so a beat
                # set in a gate this town does not have is caught (items 45 and 38).
                here=self._here_name(), places=self._place_names(),
                # And what this place IS — the Velvet Veil is a tavern — so "the roar of
                # the tavern" said while standing in it is not elsewhere: 13 of 17
                # stands-elsewhere findings in the owner's save were this (2026-10-01).
                **narration_mod.site_words(self.engine),
                # What the crowd just saw, out of fights only: in a fight the NPC
                # turns are the reaction.
                heat=(None if self.engine.scene.in_encounter
                      else (getattr(self.engine.scene, "heat", None) or None)),
            )

        review = _review(text)
        if review.ok:
            return text, made, []
        # Less is not wrong. A draft short of the floor whose only faults are its
        # length and a missing hand-back (which has a free backstop) ships at its own
        # length when it carries events: measured in the brothel (2026-09-18), every
        # prose turn was under 800 characters and went to this rewrite, and the rewrite
        # is where the woman's actions became the timberer's mallet. The floor is for
        # prose that is WRONG, not for prose that is shorter than asked.
        kinds = {f.kind for f in review.findings}
        cast_names = self._other_names()
        if kinds <= {"too-short", "no-hand-back"} and \
                len(narration_mod.action_sentences(text, cast_names)) >= 3:
            return text, made + [f"kept at its own length: {', '.join(sorted(kinds))} only, "
                          f"and the draft carries its events"], []

        # An intimate beat at an explicit table is rewritten by the model the table chose
        # to write prose, told to keep the passage exactly as explicit as it is. The
        # owner's beat "we climax together…" went through this rewrite for a recurring
        # phrase (2026-09-30), on the PLANNER's model with a briefing that says nothing
        # about content — a model the table never picked for this, free to soften it.
        who = ((self.prose_model, self.prose_host, self.prose_provider, self.prose_key)
               if intimate else (self.model, self.host, self.provider, self.api_key))

        def _rewrite(complaint: str, note: str):
            reply = client.chat(
                prompts.narration_repair_messages(
                    text, complaint, player_input, scene_brief, facts=facts,
                    keep=prompts.INTIMATE_KEEP if intimate else ""),
                who[0], who[1], as_json=True, think=False, provider=who[2],
                api_key=who[3], temperature=0.6,
                # An intimate beat runs to 3,000 characters: its rewrite gets the same
                # budget and no grammar ceiling, or a mended phrase would come back cut
                # to 1,800 and lose the end of the scene.
                num_predict=prompts.INTIMATE_NUM_PREDICT if intimate else 900,
                # Structural insurance, not a truncation cure: `as_json` already puts a
                # JSON grammar at the sampler, and the live "Unterminated string" failure
                # was the token budget dying mid-string — which no grammar prevents and
                # the except below still catches. What the schema adds is the required
                # key and a length ceiling the budget can actually afford.
                #
                # 1,800, the grammar ceiling the prose call itself writes under. It was
                # 1,600 — lower than the draft it rewrites — and on 2026-09-30 (item 6)
                # Ollama closed the string at exactly 1,600 characters, mid-word, and
                # the cut rewrite shipped as "…They'. What do you do?".
                schema=prompts.prose_schema(max_chars=prompts.GRAMMAR_MAXLENGTH_CEILING,
                                            unbounded=intimate),
            )
            # Cut back to its last whole sentence, as the prose call's reply is.
            fixed, _gone = narration_mod.trim_unfinished(
                self._lift(str(reply.json().get("narration", "")).strip()))
            return (fixed,
                    Attempt("polish", reply.seconds, reply.model, reply.text, note=note))

        attempts: list[Attempt] = []
        try:
            fixed, attempt = _rewrite(review.complaint(), "; ".join(review.as_log()))
            attempts.append(attempt)
        except Exception as exc:
            return text, made + [f"polish failed: {exc}"], [
                Attempt("polish", 0.0, self.model, note=str(exc)[:120])]

        # Scored, not counted. "One echo finding before, one after" threw away a rewrite
        # that had removed twenty of twenty-one borrowed phrases, and the plagiarised
        # original was kept every single time.
        #
        # But a lower score is not enough on its own. Asked to rewrite without any of the
        # phrases it had copied, the model returned "..." — three characters, which scores
        # far better than the plagiarism and is very much worse. So a repair may not
        # introduce a kind of problem the original did not have.
        was = {f.kind for f in review.findings}

        def _accept(candidate: str) -> bool:
            after = _review(candidate)
            # And it must keep the events of the draft: a rewrite that scored better
            # by replacing what people DID with what the air smelled of is the one
            # measured in the brothel, and it is refused here whatever its score.
            # Nor may it stop mid-sentence: a rewrite the grammar closed mid-word is
            # never better than the draft it was asked to mend (item 6, 2026-09-30).
            return bool(candidate) and not narration_mod.ends_unfinished(candidate) \
                and after.score < review.score \
                and not ({f.kind for f in after.findings} - was) \
                and narration_mod.actions_kept(text, candidate, cast_names) >= 0.6

        if _accept(fixed):
            return fixed, made + review.as_log(), attempts

        heaviest = max(review.findings, key=lambda f: f.weight)
        if (heaviest.kind in self._NO_BACKSTOP
                and not self.engine.scene.in_encounter):
            try:
                second, attempt = _rewrite(
                    heaviest.fix_hint or heaviest.detail,
                    f"retry, {heaviest.kind} only")
                attempts.append(attempt)
                if _accept(second):
                    return second, made + review.as_log(), attempts
            except Exception as exc:
                attempts.append(Attempt("polish", 0.0, self.model,
                                        note=f"retry failed: {str(exc)[:100]}"))

        return text, made + [f"unrepaired: {', '.join(review.as_log())}"], attempts

    def _intimate_beat(self) -> bool:
        """Whether this beat is an intimate scene between adults that the content rule
        briefed explicitly (`intimate.decide`). Read by the checks exempted for it."""
        return bool(getattr(self, "intimate", None) is not None and self.intimate.fired)

    def _pc_name(self) -> str:
        pc = self.engine.scene.pc()
        return pc.name if pc else ""

    def _anyone_held(self) -> bool:
        """Whether anybody here is grappled, pinned or entangled — the only state in
        which prose about slipping free is a claim about a check nobody rolled."""
        return any(a.has_state("state.held")
                   for a in self.engine.scene.actors.values())

    # --- Check 4's repair ---------------------------------------------------------------

    def _repair_outcome_claims(self, narration: str, backed=(),
                               restrained: bool = True) -> tuple[str, list[str], list[Attempt]]:
        claims = find_outcome_claims(narration, backed=backed, restrained=restrained)
        if not claims:
            return narration, [], []

        repairs: list[str] = []
        attempts: list[Attempt] = []
        # One pass. Repairing a repair spends a local model's time on diminishing
        # returns; if it is still claiming outcomes after one targeted rewrite, the
        # sentence is cut instead, which is always safe.
        seen: set[str] = set()
        for claim in claims:
            if claim.sentence in seen or not claim.sentence:
                continue
            seen.add(claim.sentence)
            try:
                reply = client.chat(
                    prompts.repair_messages(claim.sentence, claim.why),
                    self.model, self.host, as_json=True, think=False, temperature=0.3, num_predict=200,
                    # 200 tokens is roomy for one sentence, and the ceiling means the
                    # string closes before the budget can die mid-word — the failure
                    # the census counted six times on the unconstrained calls.
                    schema={"type": "object",
                            "properties": {"sentence": {"type": "string",
                                                        "maxLength": 400}},
                            "required": ["sentence"]},
                )
                attempts.append(Attempt("repair", reply.seconds, reply.model, reply.text,
                                        note=claim.why))
                fixed = str(reply.json().get("sentence", "")).strip()
            except Exception as exc:  # a failed repair must not lose the turn
                attempts.append(Attempt("repair", 0.0, self.model, note=f"failed: {exc}"))
                fixed = ""

            if fixed and not find_outcome_claims(fixed, backed=backed, restrained=restrained):
                narration = narration.replace(claim.sentence, fixed)
                repairs.append(f"{claim.why}: {claim.sentence!r} -> {fixed!r}")
            else:
                narration = narration.replace(claim.sentence, "").strip()
                repairs.append(f"{claim.why}: cut {claim.sentence!r}")

        # Belt and braces, by character span. The `replace` calls above are silent no-ops
        # whenever whitespace shifted between the extracted sentence and the narration it
        # came from — which is how "your blade bites into the joint" reached a live
        # transcript while the pattern for it sat in rules/intents.py, matching. Spans
        # cannot miss: the match position is in the current string by construction.
        narration, force_cut = cut_outcome_claims(narration, restrained=restrained)
        for gone in force_cut:
            repairs.append(f"still claiming an outcome after repair: cut {gone!r}")

        return " ".join(narration.split()), repairs, attempts

    def _repair_state_claims(self, text: str,
                             changes: list[dict] | None) -> tuple[str, list[str], list[Attempt]]:
        """Prose that says a hand holds or loses something, or a body suffers something,
        the state does not carry: one targeted rewrite of the sentence with the fact
        named, checked again, and cut when it still says it.

        The shape of `_repair_outcome_claims`, and for the reason the literature gives
        as well as this project's: edit only the span that disagrees (RARR kept the
        passage's intent in over 90% of cases where whole-passage revisers kept it in
        6-40%), and re-run the detector on the repair, because a repair fixes only some
        of what it is asked to (57.6% in Varshney et al. 2023) — a failed one is cut.
        Two calls a beat at most; a third finding is cut straight away, because a local
        model's minute is the player's minute.
        """
        from .state_claims import state_claims

        scene = self.engine.scene
        # The body's conditions are not judged in an intimate scene (see state_claims).
        bodies = not self._intimate_beat()
        found = state_claims(text, scene, changes, conditions=bodies)
        if not found:
            return text, [], []
        pc = scene.pc()
        repairs: list[str] = []
        attempts: list[Attempt] = []
        for n, (sentence, why) in enumerate(found):
            fixed = ""
            if n < 2:
                try:
                    reply = client.chat(
                        prompts.repair_messages(sentence, why),
                        self.prose_model, self.prose_host, as_json=True, think=False,
                        temperature=0.3, num_predict=200, provider=self.prose_provider,
                        api_key=self.prose_key,
                        schema={"type": "object",
                                "properties": {"sentence": {"type": "string",
                                                            "maxLength": 400}},
                                "required": ["sentence"]})
                    attempts.append(Attempt("repair", reply.seconds, reply.model,
                                            reply.text, note=f"state claim: {why}"))
                    fixed = str(reply.json().get("sentence", "")).strip()
                    if fixed and pc is not None:
                        fixed, _ = narration_mod.pc_to_second_person(fixed, pc.name)
                except Exception as exc:  # a failed repair must not lose the turn
                    attempts.append(Attempt("repair", 0.0, self.prose_model,
                                            note=f"state claim: failed: {exc}"))
                    fixed = ""
            if fixed and not state_claims(fixed, scene, changes, conditions=bodies):
                text = text.replace(sentence, fixed, 1)
                repairs.append(f"state claim: {why}: {sentence!r} -> {fixed!r}")
            else:
                text = text.replace(sentence, "", 1)
                repairs.append(f"state claim: {why}: cut {sentence!r}")
        return " ".join(text.split()), repairs, attempts

    def _repair_wrong_actor(self, text: str, acting: str,
                            tells: list[str] | None) -> tuple[str, list[str], list[Attempt]]:
        """A creature's turn told as somebody else's: detect, one targeted rewrite, and
        the tells under it (`narration.wrong_actor`, `narration.right_actor`).

        The rewrite is the one model call an NPC turn now makes after its prose, and
        only when the check fired — the standing ~10s polish is still off here, for the
        reason `npc_turn` gives. Run BEFORE the player's name is swapped to "you":
        after the swap, "You lunge forward, swinging your blade toward Kesst Vayr" reads
        "…toward you" and the inversion can no longer be told from a sound beat.
        """
        pc = self.engine.scene.pc()
        pc_name = pc.name if pc is not None else ""
        others = tuple(self._other_names())
        # Whether the beat mentions the actor at all, from the attribution rather than
        # the word lists (gm/mentions.py) — only ever able to clear the check.
        acting_ref = next((r for r, a in self.engine.scene.actors.items()
                           if str(a.name) == acting), None)
        named = (self.attribution.mentioned_in(text, acting_ref)
                 if self.attribution is not None and acting_ref else None)
        wrong = narration_mod.wrong_actor(text, acting, pc_name, others, named=named)
        if not wrong:
            return text, [], []
        from play.views import plain_tell

        plain = [narration_mod.pc_to_second_person(plain_tell(t), pc_name)[0]
                 if pc_name else plain_tell(t) for t in (tells or []) if t]
        shown = [narration_mod.pc_to_second_person(t, pc_name)[0] if pc_name else t
                 for t in (tells or []) if t]
        sentence, why = wrong[0]
        attempts: list[Attempt] = []
        try:
            reply = client.chat(
                prompts.actor_repair_messages(text, acting, shown, f"{why}: {sentence!r}"),
                self.prose_model, self.prose_host, as_json=True, think=False,
                temperature=0.4, num_predict=400, provider=self.prose_provider,
                api_key=self.prose_key,
                schema={"type": "object",
                        "properties": {"narration": {"type": "string"}},
                        "required": ["narration"]})
            attempts.append(Attempt("repair", reply.seconds, reply.model, reply.text,
                                    note=f"wrong actor: {why}"))
            fixed = self._lift(str(reply.json().get("narration", "")).strip())
        except Exception as exc:  # a failed repair must not lose the turn
            attempts.append(Attempt("repair", 0.0, self.prose_model,
                                    note=f"wrong actor: failed: {exc}"))
            fixed = ""
        if fixed and not narration_mod.wrong_actor(fixed, acting, pc_name, others):
            return fixed, [f"wrong actor: {why} — rewritten"], attempts
        kept, cut = narration_mod.right_actor(text, acting, pc_name, plain, others,
                                              named=named)
        return kept, [f"wrong actor: {why} — the rewrite failed; cut {len(cut)} "
                      f"sentence(s), the tells stand"], attempts

    def _who_was_asked(self, player_input: str):
        """The person the player's line asks something of, when the beat owes them an
        answer: named by the interpreter's reading, else the one person in conversation.
        None out of a fight's way, when nobody or several could be meant, when they are
        down, when their attitude would refuse a name (`attitude.tells_their_name` — an
        unwilling person's silence is their answer), or when the party moved."""
        from rules import attitude as attitude_mod
        from rules import scope as scope_mod

        scene = self.engine.scene
        if scene.in_encounter or not narration_mod.wants_an_answer(player_input):
            return None
        who = None
        reading = getattr(self, "reading", None)
        if isinstance(reading, dict) and not reading.get("error"):
            for a in reading.get("actions") or ():
                if isinstance(a, dict) and a.get("act") == "talk" \
                        and str(a.get("target") or "").strip():
                    ref = scope_mod.in_the_room(scene, str(a["target"]))
                    who = scene.actors.get(ref) if ref else None
                    break
        if who is None:
            talking = self.engine.talking_to()
            who = talking[0] if len(talking) == 1 else None
        if who is None or who.is_pc or not scene.conscious(who.ref):
            return None
        if not attitude_mod.tells_their_name(who):
            return None
        was = getattr(self, "_was_at", "")
        if was and was != str(getattr(scene, "at", "") or ""):
            return None
        return who

    def _answer_the_question(self, text: str, who, player_input: str,
                             brief: str) -> tuple[str, list[str], list[Attempt]]:
        """`who` was asked something and the beat gave no answer: one small call for
        their spoken answer alone, put before the hand-back. Kept only if it is speech —
        a quotation — and does not hand the turn back itself; otherwise the beat is left
        as written, which the owner accepts: "If not then they can just hit continue",
        and Continue's own words already ask for the answer (`prompts.CARRY_ON`)."""
        try:
            reply = client.chat(
                prompts.answer_messages(str(who.name), player_input, text, brief),
                self.prose_model, self.prose_host, as_json=True, think=False,
                temperature=0.6, num_predict=prompts.ANSWER_NUM_PREDICT,
                provider=self.prose_provider, api_key=self.prose_key,
                schema=prompts.answer_schema())
            attempt = Attempt("answer", reply.seconds, reply.model, reply.text,
                              note=f"unanswered: {who.name}")
            answer = " ".join(str((reply.json() or {}).get("answer") or "").split())
        except Exception as exc:  # noqa: BLE001 — a failed repair must not lose the turn
            return text, [f"unanswered: {who.name} — the call failed "
                          f"({type(exc).__name__}); kept, Continue carries it"], []
        quoted = [answer[s:e] for s, e in speech_mod.spans(answer)]
        if not quoted or narration_mod.HAND_BACK.lower() in answer.lower() \
                or len(answer) > prompts.ANSWER_MAX_CHARS + 40:
            return text, [f"unanswered: {who.name} — the answer did not hold "
                          f"({answer[:60]!r}); kept, Continue carries it"], [attempt]
        self.last_said.append({"who": who.ref, "to": "you",
                               "line": " ".join(q.strip("\"“”'‘’ ") for q in quoted)})
        return (narration_mod.put_before_the_hand_back(text, answer),
                [f"asked and not answered: {who.name} answers"], [attempt])

    def _deeds_owed(self, player_input: str, outcomes) -> list[dict]:
        """The deeds the player declared this turn that the beat must show
        (`narration.owed_deeds`). Nothing in a fight — the combat formula and the blow
        checks own that page — and nothing in an intimate beat, whose briefing, content
        rule and exemptions this small call does not carry."""
        reading = getattr(self, "reading", None)
        if not isinstance(reading, dict) or reading.get("error"):
            return []
        if self.engine.scene.in_encounter:
            return []
        mode = str(getattr(getattr(self, "intimate", None), "mode", "") or "")
        if self._intimate_beat() or mode in ("intimate", "fade"):
            return []
        return narration_mod.owed_deeds(reading, player_input, outcomes)

    def _show_declared(self, text: str, unshown: list[dict], player_input: str, *,
                       earlier: list[str] | None, brief: str, facts: list[str] | None,
                       known: set[str], shown: list[dict] | None = None
                       ) -> tuple[str, list[str], list[Attempt]]:
        """The player declared deeds the beat never wrote (owner, 2026-10-01: "describing
        the action as it plays out instead of picking up after the actions i described
        are finished"). One small call for those deeds alone, in the player's order, put
        where they happened — in front of the departure on a move turn, at the start
        otherwise, before the hand-back for a deed done after arriving.

        Kept only when it shows every deed it was asked for (the same cue words that
        found them missing), hands nothing back, walks nobody anywhere, names nobody the
        scene does not, and — for a blow the dice never rolled — hurts nobody. Otherwise
        the beat stands as written and the repairs say so: the call is a backstop under
        the prose, and a wrong backstop is worse than none."""
        deeds = [str(d.get("span") or d.get("object") or d.get("act")) for d in unshown]
        before = any(d.get("before_move") for d in unshown)
        moved_first = not before and all(d.get("after_move") for d in unshown)
        harmless = any(d.get("act") == "attack" for d in unshown)
        # Where it happens: the scene the player last read, which on a move turn is the
        # place they LEFT — the prose call is shown none of it on an arrival (`stood = []`
        # in `call_prose_messages`), which is half of why the deeds were skipped.
        where = (earlier or [])[-1] if earlier else str(brief or "")[:1400]
        scene = self.engine.scene
        lookup = " ".join([where, text, player_input, " ".join(facts or [])])
        people = [str(a.name) for a in scene.actors.values()
                  if not a.is_pc and a.name and any(
                      re.search(rf"\b{re.escape(w)}\b", lookup)
                      for w in str(a.name).split() if len(w) > 2 and w[:1].isupper())]
        messages = prompts.deeds_messages(
            deeds, player_input, text, where, people, before_move=before,
            harmless=harmless,
            already=[str(d.get("span") or d.get("act")) for d in shown or ()])
        attempts: list[Attempt] = []
        # Two tries, the second told what was wrong with the first: the shape every
        # retry here has (`narrate_turn`'s re-introduction retry). Measured on the owner's
        # turn: one replay in four wrote the smack again beside the thanks it was asked
        # for, with "ALREADY WRITTEN" in front of it, and lost the repair to that.
        for _try in range(2):
            try:
                reply = client.chat(
                    messages, self.prose_model, self.prose_host, as_json=True,
                    think=False, temperature=0.6, num_predict=prompts.DEEDS_NUM_PREDICT,
                    provider=self.prose_provider, api_key=self.prose_key,
                    schema=prompts.deeds_schema())
                attempts.append(Attempt("deeds", reply.seconds, reply.model, reply.text,
                                        note=f"unshown: {'; '.join(deeds)}"))
                passage = " ".join(str((reply.json() or {}).get("passage") or "").split())
            except Exception as exc:  # noqa: BLE001 — a failed repair must not lose the turn
                return text, [f"declared and not shown: {'; '.join(deeds)} — the call "
                              f"failed ({type(exc).__name__}); kept as written"], attempts
            why = self._deeds_refusal(passage, unshown, known | set(people),
                                      before_move=before, harmless=harmless, shown=shown)
            if not why:
                break
            messages = messages + [
                {"role": "assistant", "content": reply.text},
                {"role": "user", "content": f"That passage {why}. Write it again: only "
                                            f"{'; '.join(deeds)}, nothing else."}]
        if why:
            return text, [f"declared and not shown: {'; '.join(deeds)} — the passage did "
                          f"not hold ({why}: {passage[:60]!r}); kept as written"], attempts
        if moved_first:
            fixed = narration_mod.put_before_the_hand_back(text, passage)
        else:
            fixed = narration_mod.put_the_deeds_in(text, passage, before_move=before)
        return fixed, [f"declared and not shown: wrote {'; '.join(deeds)}"
                       + (" before the departure" if before else "")], attempts

    @staticmethod
    def _deeds_refusal(passage: str, unshown: list[dict], known: set[str], *,
                       before_move: bool, harmless: bool,
                       shown: list[dict] | None = None) -> str:
        """Why the deeds passage cannot go in, or "" when it can."""
        if not passage:
            return "empty"
        if len(passage) > prompts.DEEDS_MAX_CHARS + 40:
            return "too long"
        missing = [d for d in unshown if not narration_mod.shows_deed(passage, d)]
        if missing:
            return "does not show " + ", ".join(str(d.get("span") or d["act"]) for d in missing)
        # A deed the beat already wrote, written again: measured twice in four replays of
        # the owner's turn before `already` named them (see `prompts.deeds_messages`).
        again = [d for d in shown or () if narration_mod.shows_deed(passage, d)]
        if again:
            return "writes again " + ", ".join(str(d.get("span") or d["act"]) for d in again)
        # The demonstration copied: the arrival block's own copy of it was written word
        # for word as an opening ("You take his hand, thank him…", to a woman).
        if narration_mod.build_echo_index(prompts.deeds_shape(before_move)) \
                & narration_mod.build_echo_index(passage):
            return "copies the example"
        bare = speech_mod.unquoted(passage)
        if "?" in bare or narration_mod.HAND_BACK.lower() in passage.lower():
            return "hands the turn back"
        if narration_mod.narrator_in_first_person(passage):
            return "first person"
        if before_move and re.search(r"\b(?:arriv\w*|you are (?:now )?(?:at|in)\b)",
                                     bare, re.I):
            return "walks them somewhere"
        if harmless and re.search(r"\b(?:blood\w*|bleed\w*|wound\w*|gash\w*|injur\w*|"
                                  r"bruis\w*|broken|dead|dies|kill\w*)\b", bare, re.I):
            return "hurts somebody the dice did not"
        invented = narration_mod.invented_names(passage, known)
        if invented:
            return "names " + ", ".join(invented)
        return ""

    def _repair_misnamed(self, text: str, attribution) -> tuple[str, list[str], list[Attempt]]:
        """A name written on the wrong person: the words name one person here and the
        sentence is about another (gm/mentions.py `Mention.misnamed`). One targeted
        rewrite of the flagged sentences, kept only if the wrong name is gone from each.

        No mechanical backstop, on purpose: the flag is the labeller's word against the
        name's, and a swap on a wrong flag would write the wrong name — which is exactly
        what `creature_nouns_for_pc` did when it guessed. A failed rewrite leaves the
        sentence and says so in the repairs."""
        from . import mentions as mentions_mod

        names = {r: str(a.name) for r, a in self.engine.scene.actors.items()}
        flagged = attribution.misnamed()
        try:
            reply = client.chat(
                mentions_mod.repair_messages(text, flagged, names),
                self.prose_model, self.prose_host, as_json=True, think=False,
                temperature=0.3, num_predict=120 + 80 * len(flagged),
                provider=self.prose_provider, api_key=self.prose_key,
                schema=mentions_mod.repair_schema(len(flagged)))
            attempt = Attempt("repair", reply.seconds, reply.model, reply.text,
                              note=f"misnamed: {len(flagged)} sentence(s)")
            got = reply.json() or {}
        except Exception as exc:  # a failed repair must not lose the turn
            return text, [f"misnamed: the rewrite failed ({type(exc).__name__}); "
                          f"{len(flagged)} sentence(s) left as written"], []
        fixed, notes = text, []
        for i, m in enumerate(flagged, 1):
            new = str(got.get(f"s{i}") or "").strip()
            wrong = mentions_mod.name_words_of(names.get(m.code, ""))
            if (new and m.sentence in fixed
                    and not wrong & mentions_mod.name_words_of(new)
                    and 0.5 <= len(new) / max(1, len(m.sentence)) <= 2.0):
                fixed = fixed.replace(m.sentence, new, 1)
                notes.append(f"misnamed: {m.phrase!r} was {names.get(m.model, m.model)} "
                             f"— rewritten")
            else:
                notes.append(f"misnamed: {m.phrase!r} may be {names.get(m.model, m.model)}"
                             f" — the rewrite did not hold; left as written")
        return fixed, notes, [attempt]

    # --- Call 2 -------------------------------------------------------------------------

    def narrate_turn(self, outcomes: list, player_input: str, brief: str,
                     earlier: list[str] | None = None, *,
                     scene_now: str = "",
                     pull: dict | None = None,
                     claim: str = "",
                     shown: list[str] | None = None,
                     beat: int = 0) -> tuple[str, list[str], list[Attempt]]:
        """The whole turn as prose, written after the engine has decided it.

        The other half of `intents_first`. Here the prose call is the only one there is,
        so every check that used to run over call 1's narration runs over this instead —
        the prose is still reviewed, still polished, still has the body and hand-back
        backstops under it. What is gone is `_repair_outcome_claims`, and it is gone
        The claim repair runs here too, and did not until stage 6: it was left out
        because "it cannot happen — the model is being shown what the dice did", which
        is the prompt-rule reasoning this repo's first law says fails. Being shown the
        outcome does not stop a model adding a mechanic the outcome never contained;
        measured across the twelve real campaigns, 2.2% of the beats the player read
        carry one. What it DOES mean is that a claim the dice already made is reporting
        rather than invention, so the detector is handed what the engine backed instead
        of being switched off — `rules.intents.claims_the_engine_backs`.
        """
        fighting = self.engine.scene.in_encounter
        tells = [o.tell for o in outcomes if getattr(o, "tell", "")]
        self.last_suggestions: list[str] = []
        # The content rule for THIS beat, decided in code (gm/intimate.py): an intimate
        # scene between adults at an explicit table gets its own briefing and the
        # owner's passages; a child present or named forces the fade; everything else is
        # the ordinary turn. Read from the plain beats, which every check reads.
        # `beat` turns the owner's passages over from one beat to the next.
        self.intimate = intimate_mod.decide(player_input, earlier, self.engine.scene,
                                            beat=beat)
        demos = self.intimate.demonstrations
        # This call is handed NO history at all — `[]` — so the ledger is the only
        # thing standing between it and a campaign with no past. It is cheap and it is
        # numberless, and the prose call is the one that actually writes the page.
        messages = prompts.call_prose_messages(
            brief, [], player_input, tells, in_combat=fighting,
            # `shown`: the same beats with their speaker tags written back, for the
            # model's eyes only (`speech.retag`); every check below reads `earlier`.
            enemy=self._current_enemy(), earlier=shown if shown is not None else earlier,
            ledger=getattr(self, "ledger", None),
            # Last in the prompt, after the tells: the scene this moment and the one
            # open matter nearest to hand (docs/narrator-guards.md D6, D7), and the
            # claim the engine holds false, when the player made one.
            scene_now_block=scene_now, pull=str((pull or {}).get("text") or ""),
            claim=prompts.false_claim_block(claim) if claim else "",
            scene_mode=self.intimate.mode,
            demonstrations=demos.examples if demos is not None else None,
            # What the player did before setting off, in their words: on an arrival it
            # opens the block, so the beat starts where they were (owner, 2026-10-01).
            before_leaving=[str(d.get("span")) for d in self._deeds_owed(
                player_input, outcomes) if d.get("before_move") and d.get("span")])
        schema = prompts.prose_schema(
            narration_mod.MIN_COMBAT_CHARS if fighting
            else narration_mod.MIN_SCENE_CHARS, max_chars=2200,
            # The intimate beat is asked for 3,000 characters (the owner's figure), which
            # the grammar cannot hold (GRAMMAR_MAXLENGTH_CEILING): no `maxLength`, and the
            # token budget bounds it instead. Every other beat is clamped as before.
            unbounded=self._intimate_beat())
        budget = prompts.INTIMATE_NUM_PREDICT if self._intimate_beat() else 1400

        # Prose gets the second model call 1 has always had. It never did, and the
        # gap was invisible until the beat a model declines to write: one call,
        # one whiff, and the turn drops to the holding line with the scene
        # frozen. A tune that will not write a passage is not a broken model —
        # it is the wrong model for that beat, which is the entire reason the
        # fallback role exists. Truncation and junk take the same road out.
        from play import modelcfg

        schedule = [(self.prose_model, self.prose_host, self.prose_provider,
                     self.prose_key)]
        spare = modelcfg.for_role("fallback") or {}
        if spare.get("model") and spare["model"] != self.prose_model:
            schedule.append((spare["model"], spare.get("host", self.prose_host),
                             spare.get("provider", "ollama"),
                             spare.get("api_key", "")))

        attempts: list[Attempt] = []
        text, reply = "", None
        # The best beat the deflection check rejected, kept for the backstop below.
        best_lost: tuple[str, list[str]] | None = None
        present = [a.name for a in self.engine.scene.actors.values() if not a.is_pc]
        thread = str((getattr(self.engine.scene, "thread", None) or {}).get("subject") or "")
        for model, host, provider, key in schedule:
            reply = None
            try:
                # 1400, not 900. Measured 2026-09-04 with the scene floor at 1000
                # characters: two turns in three died "Unterminated string" on
                # BOTH models — the narration ran towards the 2,000-character
                # ceiling, and with the suggestions and the escaped quotes on top
                # the 900-token budget ended inside the string. The grammar can
                # close a string it is given the tokens to close.
                reply = client.chat(
                    messages, model, host, as_json=True, think=False,
                    temperature=0.8, num_predict=budget, provider=provider,
                    api_key=key, schema=schema,
                    timeout=(PRIMARY_TIMEOUT if model == self.prose_model
                             else FALLBACK_TIMEOUT))
                data = reply.json()
                text = self._lift(str(data.get("narration", "")).strip())
                # The prose reply's own "you could". Under intents-first the plan
                # call is told to write nothing, so its suggestions are empty, and
                # this call's — admitted by the schema, and good — were parsed and
                # dropped. Reported at the table, 2026-09-05: "there are no options
                # there should be 3 options".
                self.last_suggestions = _suggestions(data)
            except Exception as exc:
                # The reply itself, and the real elapsed time. The turn log's own
                # comment records learning this once — "the attempts were unpacked
                # into `_` and dropped, so the one diagnosable artefact never
                # existed" — and this path still dropped both, so a live prose
                # failure logged `0.0s` and an empty string. The malformed JSON of
                # 2026-09-04 could only be read by reproducing it.
                # An intimate beat has no `maxLength`, so the budget can end it inside
                # the string: the narration is salvaged and trimmed to a whole sentence
                # below, rather than the beat lost to "Unterminated string".
                salvaged = (intimate_mod.narration_from_cut_reply(reply.text)
                            if reply is not None and self._intimate_beat() else "")
                attempts.append(Attempt(
                    "prose", getattr(reply, "seconds", 0.0), model,
                    getattr(reply, "text", "") or "",
                    note=str(exc)[:120] + (" — budget death, narration salvaged"
                                           if salvaged else "")))
                if not salvaged:
                    continue
                text = self._lift(salvaged)
                self.last_suggestions = []
                break
            declined = narration_mod.reads_as_a_refusal(text)
            # A deflection is a refusal that reads as prose: rather than saying
            # no, the model writes a different scene and re-introduces somebody
            # already standing here as a stranger. It used to get a refusal's
            # answer — hand to the next model, blind — and measured 2026-09-18 that
            # threw away both models' good prose four turns in sixty (four in
            # fourteen in the player's own save), every one a false positive, and
            # shipped the engine's raw lines instead. The check is narrower now
            # (see `reintroduces_the_present`), and what it catches gets the shape
            # every fix here has held: ONE retry on the same model naming who is
            # already present, then the next model, then a deterministic backstop.
            lost = narration_mod.reintroduces_the_present(text, present, thread=thread)
            note = ("declined — handing to the next model" if declined
                    else f"lost the scene, re-introduced {', '.join(lost)}"
                    if lost else "")
            attempts.append(Attempt("prose", reply.seconds, reply.model,
                                    reply.text, note=note))
            if text and not declined and not lost:
                break
            if lost and not declined:
                best_lost = (text, lost)
                who = ", ".join(lost)
                correction = (
                    f"{who} {'is' if len(lost) == 1 else 'are'} already here, standing "
                    f"in this scene from the beat before, and you have written "
                    f"{'them' if len(lost) > 1 else 'them'} in as if newly arrived — "
                    f"'a {lost[0].split()[-1]}'. Write the same beat again with "
                    f"{who} as the person already present: no arrival, no indefinite "
                    f"article, the same events otherwise.")
                try:
                    again = client.chat(
                        messages + [{"role": "assistant", "content": reply.text},
                                    {"role": "user", "content": correction}],
                        model, host, as_json=True, think=False, temperature=0.7,
                        num_predict=budget, provider=provider, api_key=key,
                        schema=schema, timeout=FALLBACK_TIMEOUT)
                    data2 = again.json()
                    text2 = self._lift(str(data2.get("narration", "")).strip())
                    lost2 = narration_mod.reintroduces_the_present(text2, present,
                                                                    thread=thread)
                    attempts.append(Attempt(
                        "prose", again.seconds, again.model, again.text,
                        note="retry, present named"
                             + (f" — still re-introduced {', '.join(lost2)}"
                                if lost2 else "")))
                    if text2 and not lost2 and not narration_mod.reads_as_a_refusal(text2):
                        text = text2
                        self.last_suggestions = _suggestions(data2)
                        break
                    if text2 and lost2:
                        best_lost = (text2, lost2)
                except Exception as exc:
                    attempts.append(Attempt("prose", 0.0, model,
                                            note=f"retry failed: {str(exc)[:100]}"))
            if declined or lost:
                text = ""
        early: list[str] = []
        if not text and best_lost is not None:
            # The backstop: the beat every model wrote and the check rejected, with the
            # one thing the check can name — the indefinite article — made definite.
            # Better than the holding line, and far better than "You eats."
            text, lost = best_lost
            text, made = narration_mod.definite_present(text, lost)
            early.append(f"lost the scene on every model: kept the beat and made "
                         f"{', '.join(made or lost)} the one already here")
        if not text:
            return "", ["prose failed on every model"], attempts
        # A beat the grammar closed mid-word (`maxLength` ends the string cleanly, so the
        # reply parses): cut back to its last whole sentence before anything reads it.
        # 2026-09-30, item 6: "…pick it up. They'" shipped as "They'. What do you do?".
        text, gone = narration_mod.trim_unfinished(text)
        if gone:
            early.append(f"cut off mid-sentence: trimmed {gone[:60]!r}")
        # A blow at the player that nobody declared (docs/declared-not-guessed.md, the
        # blows door): a check now, not a door into a fight. Not in an intimate scene
        # between adults, where nobody here is hostile (`intimate.partners`) and the
        # detector's verbs are the scene's own: probed 2026-10-01, "Mira grabs your hair
        # and pulls you down to her" and "she drives her hips against you" both read as
        # undeclared blows, and the repair asks for the beat again "threatening,
        # squaring up or reaching" — an intimate scene rewritten as a menace, or cut.
        if not self._intimate_beat():
            text, note, struck_attempts = self._undeclared_blows(text, messages, schema)
            attempts.extend(struck_attempts)
            if note:
                early.append(note)
        # And, in a fight, anybody the prose brings in that nobody declared.
        text, note, arrival_attempts = self._undeclared_arrivals(text, messages, schema)
        attempts.extend(arrival_attempts)
        if note:
            early.append(note)
        # No claim repair here on purpose: the engine has already resolved the turn, so
        # "the blow lands" is a fact being reported, not an outcome being invented.
        # Who died, before grooming: the review needs it to ask for the death, the
        # dead-men cut needs it to spare the killing sentence, and the backstop below
        # needs it last.
        deaths = self._deaths_from(outcomes)
        # The doors this turn forced or picked, for the review's held-door check.
        self.doors = self._doors_from(outcomes)
        text, repairs, groom_attempts = self._groom(
            text, earlier=earlier or [],
            min_chars=(narration_mod.MIN_COMBAT_CHARS if fighting
                       else narration_mod.MIN_SCENE_CHARS),
            max_chars=narration_mod.MAX_COMBAT_CHARS if fighting else 0,
            player_input=player_input, brief=brief, hand_back=True, claims=True,
            backed=claims_the_engine_backs(outcomes), deaths=deaths, pull=pull,
            claim=claim, blows=self._blows_from(outcomes),
            cast=self._cast_from(outcomes), facts=tells,
            changes=self._changes_from(outcomes),
            ctx=self._beat_context("turn", player_input=player_input, brief=brief,
                                   outcomes=outcomes, tells=tells, pull=pull),
            outcomes=list(outcomes or []))
        repairs = early + repairs
        attempts.extend(groom_attempts)
        # The backstop, after the rewrite has had its chance: an authored line chosen
        # by the death's own axes and never the same one twice running. What it adds
        # is remembered on `last_added`, so the transcript can mark it and the next
        # prose call is not shown our sentence as its own (docs/narrator-guards.md D4).
        before = text
        text, pressed = narration_mod.press_the_death(text, deaths,
                                                      said=self.engine.scene.said)
        self.last_added = narration_mod.added_sentences(before, text)
        if pressed:
            repairs.append(f"a kill left off the page: wrote the death of "
                           f"{', '.join(pressed)}")
        return text, repairs, attempts

    def _deaths_from(self, outcomes: list) -> list[dict]:
        """Who the engine killed this turn, and by how far — press_the_death's feed.

        Margin is hit points past the death line (-Con), because "just enough" and
        "triple his life in one blow" deserve different sentences on the page.
        """
        deaths = []
        seen = set()
        for o in outcomes or []:
            for e in getattr(o, "effects", None) or []:
                if not (isinstance(e, dict) and e.get("kind") == "condition"
                        and e.get("condition") == "dead"):
                    continue
                a = self.engine.scene.actors.get(e.get("ref"))
                if a is None or getattr(a, "is_pc", False) or a.ref in seen:
                    continue
                seen.add(a.ref)
                pron = str(getattr(a, "pronouns", "") or "").lower()
                subj, _, obj = pron.partition("/")
                poss = {"he": "his", "she": "her", "they": "their"}.get(subj, "their")
                # The blow that did it, for the death line's axes: the heaviest damage
                # this same outcome landed on them, by type. CircleMUD keys its death
                # pool on the attack type and QuickMUD on the share of the victim; both
                # facts are on the outcome already.
                hits = [x for x in (getattr(o, "effects", None) or [])
                        if isinstance(x, dict) and x.get("kind") == "damage"
                        and x.get("ref") == e.get("ref")]
                worst = max(hits, key=lambda x: int(x.get("amount", 0) or 0),
                            default=None)
                deaths.append({
                    "name": a.name,
                    "margin": max(0, -int(a.hp) - int(a.ability_score("con"))),
                    "hp_max": int(a.hp_max),
                    "family": str(worst.get("type") or "") if worst else "",
                    # The weapon's weight, the death pool's third axis: a pebble
                    # does not take a head off.
                    "heft": str(worst.get("heft") or "") if worst else "",
                    "subj": subj or "they", "obj": obj or "them", "poss": poss,
                })
        return deaths

    def _cast_from(self, outcomes) -> list[str]:
        """The spells the engine actually cast this turn, by name.

        Read off the outcomes rather than the intents: an intent that was refused at
        resolution did not cast anything, and it is what HAPPENED that the prose may
        assert (item 25).
        """
        out = []
        for o in outcomes or []:
            if str(getattr(o, "op", "")) != "cast":
                continue
            # The cast tell opens "Ted casts Cure Light Wounds (caster level 1; …)".
            m = _CAST_TELL.search(str(getattr(o, "tell", "") or ""))
            if m:
                out.append(" ".join(m.group(1).split()))
        return out

    def _cast_aims(self, player_input: str) -> tuple[str, ...]:
        """The legal aims for the player's cast this turn (`areas.legal_aims`), for the
        schema's `aim` enum; () when there is no caster to aim for, and the schema then
        falls back to the people, the caster and the directions.

        The spell is the one the reading's cast names, else the sentence's own — so a
        burst is not offered a direction and a cone is offered all of them."""
        from rules import areas

        from . import interpret

        scene = self.engine.scene
        pc = scene.pc() if hasattr(scene, "pc") else None
        if pc is None:
            return ()
        spell = None
        reading = self.reading if isinstance(self.reading, dict) \
            and "error" not in self.reading else None
        for a in (reading or {}).get("actions") or []:
            if isinstance(a, dict) and a.get("act") == "cast":
                for slot in ("object", "target", "place"):
                    spell = interpret.spell_named(scene, a.get(slot))
                    if spell is not None:
                        break
            if spell is not None:
                break
        if spell is None:
            spell = interpret.spell_named(scene, player_input)
        try:
            return tuple(areas.legal_aims(scene, pc.ref, spell))
        except Exception:  # noqa: BLE001 — a schema hint must never take the turn down
            return ()

    @staticmethod
    def _merge_declared(raw, declared, actor: str = "") -> list:
        """The `declared` ops of the reply, added to its intents where missing.

        A declared op the intents already carry is left to the intents' own version: the
        model wrote it twice and the full intent is the richer. A travel is put first,
        because everything else in the turn happens where the party ends up (Inform's
        and TADS's one-command-at-a-time: the meaning of what follows depends on where
        the player is by then)."""
        raw = list(raw) if isinstance(raw, list) else []
        if not isinstance(declared, dict):
            return raw
        have = {str(r.get("op", "")).lower() for r in raw if isinstance(r, dict)}
        for op, body in declared.items():
            if op in have or not isinstance(body, dict):
                continue
            params = dict(body.get("params") or {})
            if op == "say":
                # The words of a declared say are the MODEL's, written into the schema's
                # required key; the player's words are what commit the turn to it.
                # Measured 2026-09-28 (item 6): the watchman's line "She doesn't like
                # the desperate ones…" was minted here as Bobby's say. The say keeps
                # who it is to; its words come from the player's line
                # (`judgement.own_words_only`, last in the chain), or it is dropped.
                params.pop("words", None)
            entry = {"op": op, "params": params,
                     "because": "the player's words commit the turn to it"}
            # The player's own act is the player's: the schema's `declared` bodies carry
            # no actor, and a merged `check` without one was refused "check: unknown
            # actor None" on every attempt (live, 2026-09-29, five of five on gemma).
            if actor and op in _PLAYERS_OWN:
                entry["actor"] = actor
            if body.get("target"):
                entry["target"] = body["target"]
            if op in ("travel", "journey"):
                raw.insert(0, entry)
            elif op == "introduce":
                # Before anything that addresses the person it brings in (new1…), and
                # after the walk. Measured live 2026-09-27: appended last, the model's
                # own `say` to new1 came before the introduce that makes new1, every
                # attempt was refused, and the turn fell back to narrate_only.
                at = next((k for k, r in enumerate(raw) if isinstance(r, dict) and str(
                    r.get("op", "")).lower() not in ("travel", "journey")), len(raw))
                raw.insert(at, entry)
            else:
                raw.append(entry)
        return raw

    def _doors_from(self, outcomes: list) -> list[dict]:
        """The doors this turn forced or picked, and whether each gave — for the review's
        held-door check (`narration.opens_a_held_door`), a repair that runs after the
        prose. Measured live 2026-09-27: the engine rolled "The door ... holds." and the
        prose wrote it flying inward."""
        return [e for o in outcomes if getattr(o, "op", "") == "break_in"
                for e in (getattr(o, "effects", None) or []) if e.get("kind") == "break_in"]

    @staticmethod
    def _changes_from(outcomes: list) -> list[dict]:
        """This turn's effect records, flat — what left a hand, what landed on a body.
        Read off the outcome RECORD, never the tells' text, the way
        `claims_the_engine_backs` is (tests/test_three_laws.py holds it there)."""
        out: list[dict] = []
        for o in outcomes or []:
            effects = o.get("effects") if isinstance(o, dict) else getattr(o, "effects", None)
            out.extend(e for e in (effects or []) if isinstance(e, dict))
        return out

    def _blows_from(self, outcomes: list) -> list[dict]:
        """Who struck this turn, from the attack outcomes that rolled — the reviewer's
        feed for `wrong-hands`. `{"attacker", "pc", "tell"}` per blow; the tell is the
        plain, second-person line the backstop stands in the prose's place."""
        from play.views import plain_tell

        pc = self.engine.scene.pc()
        out = []
        for o in outcomes or []:
            if getattr(o, "op", "") != "attack":
                continue
            # Read off the tell, never the effects: the narrator's side of the house
            # is fed tells and nothing else about mechanics (law three), and the
            # deferred first swing announces itself in the tell's own words.
            joined = str(getattr(o, "tell", "") or "").startswith("Battle is joined")
            if not getattr(o, "rolls", None) and not joined:
                continue
            if joined:
                # The fight declared and the swing deferred: no blow to be in anybody's
                # hands yet, which `premature_blows` reads.
                line = plain_tell(str(getattr(o, "tell", "") or ""))
                if pc is not None:
                    line, _ = narration_mod.pc_to_second_person(line, pc.name)
                out.append({"attacker": "", "pc": True, "joined": True, "tell": line})
                continue
            actor = self.engine.scene.actors.get(getattr(o, "actor", "") or "")
            # The outcome does not carry its actor; the tell opens with their name.
            tell = str(getattr(o, "tell", "") or "")
            attacker = actor.name if actor is not None else tell.split("'")[0].split(" hits ")[0].split(" misses ")[0].strip()
            is_pc = bool(pc is not None and (attacker == pc.name
                                             or tell.startswith(pc.name)))
            line = plain_tell(tell)
            if pc is not None:
                line, _ = narration_mod.pc_to_second_person(line, pc.name)
            out.append({"attacker": attacker or "somebody", "pc": is_pc, "tell": line})
        return out

    def narrate_outcome(self, narration: str, outcomes: list, player_input: str,
                        rewrite: bool = True, acting: str = "",
                        manner: str = "") -> tuple[str, Attempt]:
        """Say the facts the engine handed back.

        Fed only `player_visible()` outcomes, so a hidden roll's number is not in the
        context and cannot be leaked. `acting` is the creature whose turn this was, on
        an NPC's turn: the call is framed as its turn and the prose checked for being
        told the wrong way round (`narration.wrong_actor`). `manner`: on a companion's
        turn, how they do it as a fact (`companions.manner_line`).
        """
        tells = [o.tell for o in outcomes if o.tell]
        because = [o.because for o in outcomes if o.because]
        if not tells:
            return "", Attempt("consequence", 0.0, self.prose_model,
                              note="nothing to narrate")

        pc = self.engine.scene.pc()
        reply = client.chat(
            prompts.call_two_messages(narration, tells, because, player_input,
                                      acting=acting, pc_name=pc.name if pc else "",
                                      manner=manner),
            # 700 rather than 250, and it is free. `num_predict` is a ceiling, not a
            # target: llama3.1 writes its two sentences and stops either way. A reasoning
            # model does not — measured on R4C3R/qwen3-8b-heretic, every consequence call
            # spent the whole 250-token budget on its `<think>` block and returned an
            # empty string once the thinking was stripped. Ollama's `think: false` is
            # accepted by the API and ignored by this tune, so headroom is the fix.
            self.prose_model, self.prose_host, think=False, temperature=0.7, num_predict=700,
            provider=self.prose_provider, api_key=self.prose_key,
        )
        # Mechanical, before anything else sees it: the 4B qwen echoed the whole call-2
        # prompt back as prose — scaffold headers, bullet lists, the worked example's
        # answer word for word, looped four times — and 2,897 characters of it went
        # straight into the transcript, because nothing stood between this return and
        # `c.transcript.append`. An empty answer is safe: the caller renders the tells.
        example = (prompts.CONSEQUENCE_NPC_EXAMPLE if acting
                   else prompts.CONSEQUENCE_EXAMPLE)
        cleaned = narration_mod.clean_consequence(
            self._lift(reply.text.strip()), example["assistant"],
            # So a turn genuinely about the example's scenery keeps its sentences: the
            # marker cut only fires on words absent from the turn itself. The scene's
            # cast counts as the turn — an actor genuinely called "old man" is not the
            # example's old man bleeding through.
            context=f"{player_input} {narration} "
                    + " ".join(a.name for a in self.engine.scene.actors.values()))
        # The full grooming pipeline, which this call went months without — two live
        # consequence beats introduced the player's own character as a stranger and then
        # narrated her fight in the third person, because call 2 got `clean_consequence`,
        # `name_refs` and the hand-back fix and nothing else. Roughly half of what the
        # player reads comes through here.
        #
        # The claim repair, shown what the dice decided. The comment here used to read
        # "`claims=False`: the engine has already resolved the turn, so 'the blow lands'
        # is reporting, not invention" — true, and the reason a blind detector could not
        # run on this door: measured, scrubbing these beats without the outcomes cuts 25
        # of 43 of them below forty characters. The answer was to tell the detector, not
        # to turn it off. `hand_back=False`: two or three sentences about what the dice
        # did hand nothing back. `min_chars` stays 0 for the same reason.
        deaths = self._deaths_from(outcomes)
        # The doors this turn forced or picked, for the review's held-door check.
        self.doors = self._doors_from(outcomes)
        text, repairs, _more = self._groom(
            cleaned, earlier=None, min_chars=0, max_chars=0,
            player_input=player_input, brief="", hand_back=False, claims=True,
            backed=claims_the_engine_backs(outcomes), deaths=deaths,
            blows=self._blows_from(outcomes), cast=self._cast_from(outcomes),
            rewrite=rewrite, facts=tells, acting=acting,
            changes=self._changes_from(outcomes),
            # `acting` arrives as a name here; the context carries the ref, when exactly
            # one person here answers to it.
            ctx=self._beat_context("outcome", player_input=player_input, brief="",
                                   outcomes=outcomes, tells=tells,
                                   acting=self._ref_named(acting)))
        before = text
        text, pressed = narration_mod.press_the_death(text, deaths,
                                                      said=self.engine.scene.said)
        self.last_added = narration_mod.added_sentences(before, text)
        if pressed:
            repairs.append(f"a kill left off the page: wrote the death of "
                           f"{', '.join(pressed)}")
        attempt = Attempt("consequence", reply.seconds, reply.model, reply.text,
                          note="; ".join(repairs))
        return text, attempt


def _suggestions(data: dict, limit: int = 3) -> list[str]:
    """The two or three things the GM offers the player.

    Tolerant, because this is the one field nothing depends on: a model that returns a
    string instead of a list, or eight instead of three, or nothing at all, should cost
    the turn nothing. Anything unusable becomes an empty list and the page simply does not
    draw the row.
    """
    raw = data.get("suggestions")
    if isinstance(raw, str):
        raw = [raw]
    if not isinstance(raw, list):
        return []
    out: list[str] = []
    for item in raw:
        text = " ".join(str(item).split()).strip(" -•*")
        # Long enough to be an action, short enough to sit on a button.
        if 3 <= len(text) <= 120 and text not in out:
            out.append(text)
    return out[:limit]


_TRUTH_REPAIR = """You correct one sentence of a story so it agrees with what actually
happened. You are told what is wrong with it and what is true. Rewrite that sentence only:
keep its voice, its detail and its length, change what is wrong and nothing else. The
player is "you". Do not say how any roll turned out.

Reply with a JSON object: {"sentence": "..."}."""


def _truth_repair_messages(sentence: str, fact: str) -> list[dict]:
    """One flagged sentence and the fact it broke, for `_repair_sentences`. Not
    `prompts.repair_messages`: that briefing is about a roll's outcome, and these facts
    are where the player stands, who was hurt and how somebody looks."""
    return [{"role": "system", "content": _TRUTH_REPAIR},
            {"role": "user", "content": f"What is true: {fact}\n\nThe sentence:\n{sentence}"}]


def _with_correction(base: list[dict], bad_reply: str, problem: str) -> list[dict]:
    """Feed the rejection back so the retry is a repair rather than a fresh guess.

    Built from `base` every time rather than from the previous attempt's messages, so a
    fifth try is not reading four earlier rejected attempts. Accumulating them anchored
    the model to its first structural choice: asked to attack a guildhand it emitted a
    `check`, and then spent four more attempts fixing the params of a `check` rather
    than reaching for `attack`.

    The wording matters for the same reason. "Send the same turn again, corrected" told
    it to keep the shape at the exact moment the rejection was telling it to change —
    the shape of a prompt becoming the shape of the output, in the retry path.
    """
    return base + [
        {"role": "assistant", "content": bad_reply},
        {"role": "user", "content":
            f"The rules engine rejected that: {problem}\n\n"
            f"Send the whole turn again, fixed. If the rejection names a different op or "
            f"a different value, use that one — do not keep the shape that was "
            f"rejected."},
    ]
