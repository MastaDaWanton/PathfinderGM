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

        for n, (model, host, provider, key) in enumerate(schedule):
            if n == max_attempts:
                rejections.append(f"— handing the turn to {model}")
            # The shape the reply is *allowed* to have, built from this turn's situation
            # rather than fixed. In a fight the intent list may not be empty and
            # `narrate_only` is not among the choices, so the failure that cost this
            # project its whole combat loop — narrating a punch and proposing nothing —
            # is not a reply the sampler can produce. See `prompts.turn_schema`.
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
                raw = judgement.repair_misaimed_attack(
                    raw, player_input, self.engine.scene) or raw
                raw = judgement.fill_obvious_targets(raw, self.engine.scene)
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
                data = dict(data, intents=raw)
                intents = self.engine.validate(raw)
            except IntentError as exc:
                # The GM naming people it wanted to exist — "attack thug1" — is the one
                # rejection it will not learn from, hint and example notwithstanding. It
                # is repaired in code instead of asked about again.
                if exc.check == "refs":
                    amended = judgement.repair_unknown_refs(
                        data.get("intents"), player_input, self.engine.scene)
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
        try:
            world = self.world
            names |= {e.name for e in world.entities.values()}
            names |= {u["name"] for u in world.unwritten}
            names |= {f["name"] for c in world.chronology for f in c.figures}
            names |= {c["name"] for c in world.chronology}
            names |= {f["name"] for f in world.factions}
            names.add(world.name)
        except Exception:
            pass
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
               rewrite: bool = True,
               backed=()) -> tuple[str, list[str], list[Attempt]]:
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
            text, claim_repairs, claim_attempts = self._repair_outcome_claims(text, backed)
            repairs += claim_repairs
            attempts += claim_attempts

        # A legacy campaign's woven-in people count as known from here down, so the
        # reviewer stops burning rewrites on Vorgath and the un-namer leaves him be.
        extra = narration_mod.established_names(earlier)
        if rewrite:
            text, p_repairs, p_attempts = self.polish(
                text, earlier=earlier, min_chars=min_chars, max_chars=max_chars,
                player_input=player_input, scene_brief=brief, extra_known=extra)
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
        text, risen = narration_mod.cut_dead_men_walking(text, dead)
        if risen:
            repairs.append(f"the dead stayed dead: cut {len(risen)} sentence(s)")
        text, leaked = narration_mod.strip_leaked_options(text)
        if leaked:
            repairs.append(f"option menu leaked into prose: cut {len(leaked)} "
                           f"sentence(s)")
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
    })

    def polish(self, text: str, earlier: list[str] | None = None,
               min_chars: int = 0, max_chars: int = 0, player_input: str = "",
               scene_brief: str = "",
               extra_known: set[str] | None = None) -> tuple[str, list[str], list[Attempt]]:
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
        known = self._known_names() | (extra_known or set())

        def _review(t: str):
            return narration_mod.review(
                t, pc_name=self._pc_name(), echo_index=self._echo_index(),
                known_names=known, earlier=earlier,
                min_chars=min_chars, max_chars=max_chars, alone=self._alone(),
                pronouns=self._pc_pronouns(), others=self._other_names(),
                gender=self._pc_gender(),
            )

        review = _review(text)
        if review.ok:
            return text, [], []

        def _rewrite(complaint: str, note: str):
            reply = client.chat(
                prompts.narration_repair_messages(
                    text, complaint, player_input, scene_brief),
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
            return text, [f"polish failed: {exc}"], [
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
            return bool(candidate) and after.score < review.score \
                and not ({f.kind for f in after.findings} - was)

        if _accept(fixed):
            return fixed, review.as_log(), attempts

        heaviest = max(review.findings, key=lambda f: f.weight)
        if (heaviest.kind in self._NO_BACKSTOP
                and not self.engine.scene.in_encounter):
            try:
                second, attempt = _rewrite(
                    heaviest.fix_hint or heaviest.detail,
                    f"retry, {heaviest.kind} only")
                attempts.append(attempt)
                if _accept(second):
                    return second, review.as_log(), attempts
            except Exception as exc:
                attempts.append(Attempt("polish", 0.0, self.model,
                                        note=f"retry failed: {str(exc)[:100]}"))

        return text, [f"unrepaired: {', '.join(review.as_log())}"], attempts

    def _pc_name(self) -> str:
        pc = self.engine.scene.pc()
        return pc.name if pc else ""

    # --- Check 4's repair ---------------------------------------------------------------

    def _repair_outcome_claims(self, narration: str,
                               backed=()) -> tuple[str, list[str], list[Attempt]]:
        claims = find_outcome_claims(narration, backed=backed)
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

            if fixed and not find_outcome_claims(fixed, backed=backed):
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
        narration, force_cut = cut_outcome_claims(narration)
        for gone in force_cut:
            repairs.append(f"still claiming an outcome after repair: cut {gone!r}")

        return " ".join(narration.split()), repairs, attempts

    # --- Call 2 -------------------------------------------------------------------------

    def narrate_turn(self, outcomes: list, player_input: str, brief: str,
                     earlier: list[str] | None = None) -> tuple[str, list[str], list[Attempt]]:
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
            ledger=getattr(self, "ledger", None))
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
                    api_key=key, schema=schema)
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
            # already standing here as a stranger. Same answer as a refusal —
            # ask the next model — because the beat the player declared did not
            # get written either way.
            lost = narration_mod.reintroduces_the_present(
                text, [a.name for a in self.engine.scene.actors.values()
                       if not a.is_pc])
            note = ("declined — handing to the next model" if declined
                    else f"lost the scene, re-introduced {', '.join(lost)}"
                    if lost else "")
            attempts.append(Attempt("prose", reply.seconds, reply.model,
                                    reply.text, note=note))
            if text and not declined and not lost:
                break
            if declined or lost:
                text = ""
        if not text:
            return "", ["prose failed on every model"], attempts
        # No claim repair here on purpose: the engine has already resolved the turn, so
        # "the blow lands" is a fact being reported, not an outcome being invented.
        text, repairs, groom_attempts = self._groom(
            text, earlier=earlier or [],
            min_chars=(narration_mod.MIN_COMBAT_CHARS if fighting
                       else narration_mod.MIN_SCENE_CHARS),
            max_chars=narration_mod.MAX_COMBAT_CHARS if fighting else 0,
            player_input=player_input, brief=brief, hand_back=True, claims=True,
            backed=claims_the_engine_backs(outcomes))
        attempts.extend(groom_attempts)
        # After grooming, never before: cut_dead_men_walking would read a fresh
        # death sentence as a dead man acting.
        text, pressed = narration_mod.press_the_death(text, self._deaths_from(outcomes))
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
                deaths.append({
                    "name": a.name,
                    "margin": max(0, -int(a.hp) - int(a.ability_score("con"))),
                    "hp_max": int(a.hp_max),
                    "subj": subj or "they", "obj": obj or "them", "poss": poss,
                })
        return deaths

    def narrate_outcome(self, narration: str, outcomes: list, player_input: str) -> tuple[str, Attempt]:
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
        text, repairs, _more = self._groom(
            cleaned, earlier=None, min_chars=0, max_chars=0,
            player_input=player_input, brief="", hand_back=False, claims=True,
            backed=claims_the_engine_backs(outcomes))
        text, pressed = narration_mod.press_the_death(text, self._deaths_from(outcomes))
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
