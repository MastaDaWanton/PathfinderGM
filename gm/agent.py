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
        # The plan sees the situation cards — the GM's secret ones included — keyed
        # off the last few beats the view hands over (`self.recent`).
        brief = prompts.scene_brief(self.world, self.engine.scene, location, recent_events,
                                    here=self.engine.here(), known=self.engine.places(),
                                    recent=getattr(self, "recent", None), secret=True,
                                    turn=getattr(self, "turn", 0))
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
        declared = judgement.declared_ops(player_input, self.engine.scene, self.world)

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
                                    must_contain=tuple(declared)))
            except client.ModelUnavailable as exc:
                down.add(model)
                rejections.append(f"attempt {n + 1}: {model} could not be reached: {exc}")
                if all(m in down for m, *_ in schedule):
                    raise
                continue
            attempts.append(Attempt("plan", reply.seconds, reply.model, reply.text))

            try:
                data = reply.json()
            except ValueError as exc:
                rejections.append(f"attempt {n + 1}: {exc}")
                messages = _with_correction(base, reply.text, str(exc))
                continue

            narration = str(data.get("narration", "")).strip()
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
                # First, because everything downstream reads the shapes this
                # straightens: a target pocketed in params is invisible to the misaim
                # check, and an invented param is a schema refusal five lines later.
                raw = judgement.split_plural_targets(raw)
                # The player's own cast, jar or power with no actor written is theirs.
                raw = judgement.fill_missing_actor(raw, player_input, self.engine.scene)
                raw = judgement.repair_bare_spawns(raw, player_input)
                raw = judgement.normalize_attacks(raw, self.engine.scene) or raw
                # A thing thrown or swung is an improvised-weapon attack that names
                # the thing — before the misaim check reads "the man" it was thrown
                # at, and before anything can dress the throw as a spell.
                raw = judgement.inject_improvised(raw, player_input, self.engine.scene)
                raw = judgement.repair_misaimed_attack(
                    raw, player_input, self.engine.scene) or raw
                raw = judgement.fill_obvious_targets(raw, self.engine.scene)
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
                # Before survival: a drunk potion is the jar door, not a waterskin
                # sip, and never a number the model wrote.
                raw = judgement.declare_use_item(raw, player_input, self.engine.scene)
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
                raw = judgement.inject_false_claim(raw, player_input, self.engine.scene)
                # Before `inject_checks`: "I cast charm person on the guard" is a spell,
                # not a Diplomacy check, and the check injector's verbs are broad enough
                # to claim it.
                raw = judgement.inject_cast(raw, player_input, self.engine.scene)
                raw = judgement.inject_checks(raw, player_input, self.engine.scene)
                # After inject_checks so its product is covered too: a check with
                # neither dc nor opposed_by is refused by validation, and the "engine
                # default band" the old docstring promised never existed.
                raw = judgement.drop_premature_end(raw)
                raw = judgement.drop_stray_checks(raw, player_input)
                raw = judgement.fill_bare_checks(raw)
                raw = judgement.inject_travel(raw, player_input, self.engine.scene,
                                              self.world)
                # A departure that names the room the party is in is asked again with
                # the rooms that would have worked; raises into the correction path.
                raw = judgement.refuse_leaving_in_place(raw, player_input,
                                                        self.engine.scene, self.world)
                # After travel, load-bearing: "go to the forest and forage" must move
                # first or the forage rolls the old ground's tables.
                raw = judgement.inject_forage(raw, player_input, self.engine.scene)
                raw = judgement.inject_prospect(raw, player_input, self.engine.scene)
                raw = judgement.inject_found(raw, player_input, self.engine.scene)
                raw = judgement.inject_venture(raw, player_input, self.engine.scene)
                raw = judgement.inject_wait(raw, player_input, self.engine.scene)
                raw = judgement.bulk_give_is_a_loot(raw, self.engine.scene)
                raw = judgement.inject_loot(raw, player_input, self.engine.scene)
                # Last, and after the target fills: a fight the player declared and the
                # GM only described. Runs once there is certainly nobody to fight, so it
                # cannot steal a turn from `fill_obvious_targets`.
                raw = judgement.inject_fight(raw, player_input, self.engine.scene)
                raw = judgement.inject_company(raw, player_input,
                                               self.engine.scene)
                # Speech last, because it competes with nothing: "I tell the smith I
                # want the axe" is a sale AND a line of dialogue, and both belong in
                # the turn. Measured on the first live turn after the `say` op landed —
                # the schema asked for one, the model wrote prose instead, and the turn
                # resolved with no `say` at all, which is the whole failure the op
                # exists to end. Detect mechanically, repair with a targeted call.
                raw = judgement.inject_say(raw, player_input, self.engine.scene)
                # And the world's answer when the player looked for somebody who is not
                # here, stated whether or not the plan reached for them (item 29). Last,
                # because it reads the player's own sentence and competes with nothing.
                raw = judgement.answer_the_absent(raw, player_input, self.engine.scene,
                                                  self.world)
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
            repairs = list(verdict.as_log()) + self._context_note()
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
                player_input=player_input, brief=brief, hand_back=True, claims=True)
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
                                    here=self.engine.here(), known=self.engine.places())
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
                 max_attempts: int = 3) -> TurnPlan:
        """Act for one creature on its own initiative.

        Same validation as a player turn, so an NPC cannot be talked into a mechanic
        either. Fewer attempts than a player turn: a stalled NPC costs the fight far less
        than a stalled player turn costs the scene, and the caller falls back to the
        creature simply holding its ground.
        """
        actor = self.engine.scene.actors[ref]
        brief = prompts.scene_brief(self.world, self.engine.scene, location, recent_events,
                                    here=self.engine.here(), known=self.engine.places())
        base = prompts.npc_turn_messages(brief, [], ref, actor, self.engine.scene.round)
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
                intents = self.engine.validate(data.get("intents"), origin=origin,
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
            narration, repairs, groom_attempts = self._groom(
                str(data.get("narration", "")).strip(),
                earlier=None, min_chars=0,
                max_chars=narration_mod.MAX_COMBAT_CHARS,
                player_input="", brief=brief, hand_back=False, claims=True,
                rewrite=False)
            attempts.extend(groom_attempts)
            return TurnPlan(narration=narration, intents=intents, attempts=attempts,
                            repairs=repairs, rejections=rejections)

        raise IntentError(
            f"the GM could not act for {ref} in {max_attempts} attempts:\n"
            + "\n".join(rejections)
        )

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
            self._echoes = narration_mod.build_echo_index(
                *[prompts.fill_enemy(e["reply"]["narration"], None)
                  for e in prompts.EXAMPLES],
                *[prompts.fill_enemy(e["reply"]["narration"], None)
                  for e in prompts.NPC_EXAMPLES],
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
               facts: list[str] | None = None) -> tuple[str, list[str], list[Attempt]]:
        """Every mechanical treatment a piece of GM prose gets, in one place.

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
                if not a.is_pc and (a.hp < 0 or a.has_state("state.down.dead"))]
        # Whoever died THIS turn keeps their killing sentence (see the function): the
        # cut used to delete "the sailor crumples to the deck" as a dead man acting,
        # which is how every one-punch kill ended in the same appended template.
        text, risen = narration_mod.cut_dead_men_walking(
            text, dead, fresh=[str(d.get("name") or "") for d in (deaths or [])])
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
        pc = self.engine.scene.pc()
        if pc is not None:
            text, named = narration_mod.pc_to_second_person(text, pc.name)
            if named:
                repairs.append(f"the player narrated by name: {named} swap(s) "
                               f"to second person")
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
        ctx = (" ".join([brief] + list(earlier or [])) if brief else fire_context)
        if ctx is not None:
            text, lit = narration_mod.cut_fire_from_nowhere(text, ctx)
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
            text, beasts = narration_mod.creature_nouns_for_pc(text, pc.name, people_only)
            if beasts:
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

    def _found_from_the_page(self, text: str) -> list[str]:
        """A place the page made, before the reviewer reads the draft.

        Ruled 2026-09-23: a place the narration establishes that the settlement does
        not list is FOUNDED, not rewritten away — "what matters is the places being
        remembered, interesting, and at least make sense to be where they are". Every
        such place the engine can make sense of is made (`Engine.found_from_prose`),
        and the review that follows sees it on the list. One a beat: a paragraph that
        names three new buildings is still a paragraph that has wandered. Returns the
        repair-log notes.
        """
        here = self._here_name()
        if not here or not text:
            return []
        # Not in a fight. A brawl's prose reaches for whatever is near — "he slams you
        # back against the forge" — and measured 2026-09-25 this ran on combat prose
        # too, so a fight in the lane could found a smithy the town never had. The
        # ruling was about places the narration ESTABLISHES, which a fight does not do.
        if getattr(self.engine.scene, "in_encounter", False):
            return []
        places = self._place_names()
        real = {narration_mod._bare(p).lower() for p in places}
        for where, sentence in narration_mod.stands_elsewhere(text, here=here,
                                                              places=places):
            if narration_mod._bare(where).lower() in real:
                continue        # a real place walked to without moving: still item 38
            try:
                note, why = self.engine.found_from_prose(
                    where, sentence,
                    standing=narration_mod.claims_standing(sentence, where))
            except Exception as exc:      # noqa: BLE001 — a founding is never worth a turn
                return [f"a place the page made could not be kept: {exc}"]
            if note:
                return [note]
            if why:
                return [f"a place the page made was refused: {why}"]
        return []

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
        # The page may have made a place; the review below must see it on the list.
        made = self._found_from_the_page(text)
        known = self._known_names() | (extra_known or set())

        def _review(t: str):
            return narration_mod.review(
                t, pc_name=self._pc_name(), echo_index=self._echo_index(),
                known_names=known, earlier=earlier,
                min_chars=min_chars, max_chars=max_chars, alone=self._alone(),
                pronouns=self._pc_pronouns(), others=self._other_names(),
                gender=self._pc_gender(), state=self._body_count(),
                deaths=deaths, pull=pull, claim=claim, blows=blows,
                fire_context=fire_context,
                # Where the party actually is, and what places exist here, so a beat
                # set in a gate this town does not have is caught (items 45 and 38).
                here=self._here_name(), places=self._place_names(),
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

        def _rewrite(complaint: str, note: str):
            reply = client.chat(
                prompts.narration_repair_messages(
                    text, complaint, player_input, scene_brief, facts=facts),
                self.model, self.host, as_json=True, think=False, provider=self.provider,
                api_key=self.api_key, temperature=0.6, num_predict=900,
                # Structural insurance, not a truncation cure: `as_json` already puts a
                # JSON grammar at the sampler, and the live "Unterminated string" failure
                # was the token budget dying mid-string — which no grammar prevents and
                # the except below still catches. What the schema adds is the required
                # key and a length ceiling the budget can actually afford.
                schema=prompts.prose_schema(max_chars=1600),
            )
            return (str(reply.json().get("narration", "")).strip(),
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
            return bool(candidate) and after.score < review.score \
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

    # --- Call 2 -------------------------------------------------------------------------

    def narrate_turn(self, outcomes: list, player_input: str, brief: str,
                     earlier: list[str] | None = None, *,
                     scene_now: str = "",
                     pull: dict | None = None,
                     claim: str = "") -> tuple[str, list[str], list[Attempt]]:
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
        # This call is handed NO history at all — `[]` — so the ledger is the only
        # thing standing between it and a campaign with no past. It is cheap and it is
        # numberless, and the prose call is the one that actually writes the page.
        messages = prompts.call_prose_messages(
            brief, [], player_input, tells, in_combat=fighting,
            enemy=self._current_enemy(), earlier=earlier,
            ledger=getattr(self, "ledger", None),
            # Last in the prompt, after the tells: the scene this moment and the one
            # open matter nearest to hand (docs/narrator-guards.md D6, D7), and the
            # claim the engine holds false, when the player made one.
            scene_now_block=scene_now, pull=str((pull or {}).get("text") or ""),
            claim=prompts.false_claim_block(claim) if claim else "")
        schema = prompts.prose_schema(
            narration_mod.MIN_COMBAT_CHARS if fighting
            else narration_mod.MIN_SCENE_CHARS, max_chars=2200)

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
                    temperature=0.8, num_predict=1400, provider=provider,
                    api_key=key, schema=schema,
                    timeout=(PRIMARY_TIMEOUT if model == self.prose_model
                             else FALLBACK_TIMEOUT))
                data = reply.json()
                text = str(data.get("narration", "")).strip()
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
                attempts.append(Attempt(
                    "prose", getattr(reply, "seconds", 0.0), model,
                    getattr(reply, "text", "") or "", note=str(exc)[:120]))
                continue
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
                        num_predict=1400, provider=provider, api_key=key,
                        schema=schema, timeout=FALLBACK_TIMEOUT)
                    data2 = again.json()
                    text2 = str(data2.get("narration", "")).strip()
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
        # No claim repair here on purpose: the engine has already resolved the turn, so
        # "the blow lands" is a fact being reported, not an outcome being invented.
        # Who died, before grooming: the review needs it to ask for the death, the
        # dead-men cut needs it to spare the killing sentence, and the backstop below
        # needs it last.
        deaths = self._deaths_from(outcomes)
        text, repairs, groom_attempts = self._groom(
            text, earlier=earlier or [],
            min_chars=(narration_mod.MIN_COMBAT_CHARS if fighting
                       else narration_mod.MIN_SCENE_CHARS),
            max_chars=narration_mod.MAX_COMBAT_CHARS if fighting else 0,
            player_input=player_input, brief=brief, hand_back=True, claims=True,
            backed=claims_the_engine_backs(outcomes), deaths=deaths, pull=pull,
            claim=claim, blows=self._blows_from(outcomes),
            cast=self._cast_from(outcomes), facts=tells)
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
                        rewrite: bool = True) -> tuple[str, Attempt]:
        """Say the facts the engine handed back.

        Fed only `player_visible()` outcomes, so a hidden roll's number is not in the
        context and cannot be leaked.
        """
        tells = [o.tell for o in outcomes if o.tell]
        because = [o.because for o in outcomes if o.because]
        if not tells:
            return "", Attempt("consequence", 0.0, self.prose_model,
                              note="nothing to narrate")

        reply = client.chat(
            prompts.call_two_messages(narration, tells, because, player_input),
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
        cleaned = narration_mod.clean_consequence(
            reply.text.strip(), prompts.CONSEQUENCE_EXAMPLE["assistant"],
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
        text, repairs, _more = self._groom(
            cleaned, earlier=None, min_chars=0, max_chars=0,
            player_input=player_input, brief="", hand_back=False, claims=True,
            backed=claims_the_engine_backs(outcomes), deaths=deaths,
            blows=self._blows_from(outcomes), cast=self._cast_from(outcomes),
            rewrite=rewrite, facts=tells)
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
