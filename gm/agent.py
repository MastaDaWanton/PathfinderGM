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

from rules.intents import Intent, IntentError, cut_outcome_claims, find_outcome_claims

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
        self.intents_first = bool(os.environ.get("GM_INTENTS_FIRST"))

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
        brief = prompts.scene_brief(self.world, self.engine.scene, location, recent_events)
        # A fight is a different job, and gets a different prompt and a different floor.
        fighting = self.engine.scene.in_encounter
        build = (prompts.call_one_intents_only if self.intents_first
                 else prompts.call_one_messages)
        base = build(brief, history, player_input, in_combat=fighting,
                     enemy=self._current_enemy())
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
            reply = client.chat(messages, model, host, as_json=True,
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
                raw = judgement.repair_misaimed_attack(
                    raw, player_input, self.engine.scene) or raw
                raw = judgement.fill_obvious_targets(raw, self.engine.scene)
                raw = judgement.inject_survival(raw, player_input, self.engine.scene)
                # Sale first, then goods. Selling is the more specific reading of handing
                # something over and it is the one that pays — and the order was the other
                # way round for exactly as long as it took `declared_ops` to notice: "I
                # sell the Yarow Elixir" matched `_HANDS_OVER`, became a `give`, and the
                # elixir left the satchel for nothing.
                raw = judgement.inject_sale(raw, player_input, self.engine.scene)
                raw = judgement.inject_goods(raw, player_input, self.engine.scene)
                raw = judgement.inject_ability(raw, player_input, self.engine.scene)
                # Before `inject_checks`: "I cast charm person on the guard" is a spell,
                # not a Diplomacy check, and the check injector's verbs are broad enough
                # to claim it.
                raw = judgement.inject_cast(raw, player_input, self.engine.scene)
                raw = judgement.inject_checks(raw, player_input, self.engine.scene)
                raw = judgement.inject_travel(raw, player_input, self.engine.scene,
                                              self.world)
                # Last, and after the target fills: a fight the player declared and the
                # GM only described. Runs once there is certainly nobody to fight, so it
                # cannot steal a turn from `fill_obvious_targets`.
                raw = judgement.inject_fight(raw, player_input, self.engine.scene)
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
            repairs = list(verdict.as_log())
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

            # Check 4 is the only one that gets a targeted repair, because the narration
            # around the claim is worth keeping.
            narration = judgement.name_refs(narration, self.engine.scene)
            # The player's own turn bleeds the worked examples' cast the same way NPC
            # turns do — the player's words join the cast as context, so "I pay the
            # thug" stays sayable even before the thug is an actor.
            narration = narration_mod.strip_example_cast(
                narration,
                player_input + " "
                + " ".join(a.name for a in self.engine.scene.actors.values()))
            narration, claim_repairs, repair_attempts = self._repair_outcome_claims(narration)
            attempts.extend(repair_attempts)
            narration, prose_repairs, prose_attempts = self.polish(
                narration, earlier=recent_narration or [],
                min_chars=(narration_mod.MIN_COMBAT_CHARS if fighting
                           else narration_mod.MIN_SCENE_CHARS),
                max_chars=narration_mod.MAX_COMBAT_CHARS if fighting else 0,
                player_input=player_input, scene_brief=brief)
            attempts.extend(prose_attempts)

            # Last, and unconditional. `polish` keeps the original whenever its rewrite
            # is no better, so a narration that outsources the description can survive
            # the repair — and the one thing that must never reach the player is the GM
            # asking them what they can see.
            narration, outsourced = narration_mod.fix_hand_back(narration)
            if outsourced:
                prose_repairs = prose_repairs + [
                    f"asked the player to narrate: replaced {outsourced!r}"]

            # And the case `fix_hand_back` cannot reach: no question at all. Six of
            # fourteen turns in one live campaign shipped without one, every one logged
            # `unrepaired: no-hand-back` — the model was asked to rewrite and its rewrite
            # lost, six times out of six.
            #
            # Unconditional, like the two backstops above it. Every turn `plan_turn`
            # produces is the player's turn to answer, in a fight or out of one; the
            # consequence call is the one that hands nothing back, and it does not come
            # through here.
            narration, added = narration_mod.ensure_hand_back(narration)
            if added:
                prose_repairs = prose_repairs + ["no hand-back: added the question"]

            # Same reason, same place. Measured on the turn that prompted it: the review
            # found `wrong-body`, the rewrite was asked for, and it lost — the turn
            # carried three findings at once and the repair could not beat all of them —
            # so "your pectoralis major muscles" reached the player for a second time.
            # Telling somebody their character has a body she does not have is not a
            # prose nit to lose a coin-toss over.
            narration, swapped = narration_mod.right_body(
                narration, self._pc_gender(), self._other_names())
            if swapped:
                prose_repairs = prose_repairs + [
                    f"wrong body: replaced {', '.join(repr(s) for s in swapped)}"]

            return TurnPlan(narration=narration, intents=intents,
                            suggestions=_suggestions(data),
                            attempts=attempts,
                            repairs=repairs + claim_repairs + prose_repairs,
                            rejections=rejections)

        # `schedule` holds (model, host, provider, key). Unpacked as a pair, this line
        # raised `ValueError: too many values to unpack` *while reporting that the turn
        # had failed* — so the honest "five attempts, here is what each one got wrong"
        # message the player was owed came out as a 500 and a traceback instead. It only
        # runs when every attempt has failed, which is why nobody had ever reached it.
        # Found by `tools/narrator_audit.py`.
        raise IntentError(
            "the GM could not produce a valid turn in "
            f"{len(schedule)} attempts across "
            f"{len({m for m, *_ in schedule})} model(s):\n" + "\n".join(rejections)
        )

    # --- An NPC's turn -------------------------------------------------------------------

    def npc_turn(self, ref: str, location=None, recent_events=None,
                 max_attempts: int = 3) -> TurnPlan:
        """Act for one creature on its own initiative.

        Same validation as a player turn, so an NPC cannot be talked into a mechanic
        either. Fewer attempts than a player turn: a stalled NPC costs the fight far less
        than a stalled player turn costs the scene, and the caller falls back to the
        creature simply holding its ground.
        """
        actor = self.engine.scene.actors[ref]
        brief = prompts.scene_brief(self.world, self.engine.scene, location, recent_events)
        base = prompts.npc_turn_messages(brief, [], ref, actor, self.engine.scene.round)
        messages = base
        attempts: list[Attempt] = []
        rejections: list[str] = []

        for n in range(max_attempts):
            reply = client.chat(messages, self.model, self.host, as_json=True, provider=self.provider,
                api_key=self.api_key,
                                temperature=0.7, num_predict=400)
            attempts.append(Attempt("npc", reply.seconds, reply.model, reply.text))
            try:
                data = reply.json()
                intents = self.engine.validate(data.get("intents"))
            except (ValueError, IntentError) as exc:
                rejections.append(f"attempt {n + 1}: {exc}")
                messages = _with_correction(base, reply.text, str(exc))
                continue

            narration = judgement.name_refs(
                str(data.get("narration", "")).strip(), self.engine.scene)
            # The worked examples' own cast, playing themselves: a bear's turn narrated
            # as "The thug... swinging the sap". The scene's real cast is the context —
            # a genuine thug keeps his sentences.
            cast = " ".join(a.name for a in self.engine.scene.actors.values())
            narration = narration_mod.strip_example_cast(narration, cast)
            narration, repairs, repair_attempts = self._repair_outcome_claims(narration)
            attempts.extend(repair_attempts)
            narration, outsourced = narration_mod.fix_hand_back(narration)
            if outsourced:
                repairs = repairs + [
                    f"asked the player to narrate: replaced {outsourced!r}"]
            return TurnPlan(narration=narration, intents=intents, attempts=attempts,
                            repairs=repairs, rejections=rejections)

        raise IntentError(
            f"the GM could not act for {ref} in {max_attempts} attempts:\n"
            + "\n".join(rejections)
        )

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
                  if not a.is_pc and a.hp > 0]
        return not others

    def polish(self, text: str, earlier: list[str] | None = None,
               min_chars: int = 0, max_chars: int = 0, player_input: str = "",
               scene_brief: str = "") -> tuple[str, list[str], list[Attempt]]:
        """One targeted rewrite when the prose breaks a rule about prose.

        Same shape as every fix that has held here: detect mechanically, then ask the
        model to repair only what was found. If the rewrite is no better the original is
        kept — blander prose is worth less than a lost turn.
        """
        review = narration_mod.review(
            text, pc_name=self._pc_name(), echo_index=self._echo_index(),
            known_names=self._known_names(), earlier=earlier,
            min_chars=min_chars, max_chars=max_chars, alone=self._alone(),
            pronouns=self._pc_pronouns(), others=self._other_names(),
            gender=self._pc_gender(),
        )
        if review.ok:
            return text, [], []

        try:
            reply = client.chat(
                prompts.narration_repair_messages(
                    text, review.complaint(), player_input, scene_brief),
                self.model, self.host, as_json=True, provider=self.provider,
                api_key=self.api_key, temperature=0.6, num_predict=900,
            )
            attempt = Attempt("polish", reply.seconds, reply.model, reply.text,
                              note="; ".join(review.as_log()))
            fixed = str(reply.json().get("narration", "")).strip()
        except Exception as exc:
            return text, [f"polish failed: {exc}"], [
                Attempt("polish", 0.0, self.model, note=str(exc)[:120])]

        after = narration_mod.review(
            fixed, pc_name=self._pc_name(), echo_index=self._echo_index(),
            known_names=self._known_names(), earlier=earlier,
            min_chars=min_chars, max_chars=max_chars, alone=self._alone(),
            pronouns=self._pc_pronouns(), others=self._other_names(),
            gender=self._pc_gender(),
        )
        # Scored, not counted. "One echo finding before, one after" threw away a rewrite
        # that had removed twenty of twenty-one borrowed phrases, and the plagiarised
        # original was kept every single time.
        #
        # But a lower score is not enough on its own. Asked to rewrite without any of the
        # phrases it had copied, the model returned "..." — three characters, which scores
        # far better than the plagiarism and is very much worse. So a repair may not
        # introduce a kind of problem the original did not have.
        was, now = {f.kind for f in review.findings}, {f.kind for f in after.findings}
        if fixed and after.score < review.score and not (now - was):
            return fixed, review.as_log(), [attempt]
        return text, [f"unrepaired: {', '.join(review.as_log())}"], [attempt]

    def _pc_name(self) -> str:
        pc = self.engine.scene.pc()
        return pc.name if pc else ""

    # --- Check 4's repair ---------------------------------------------------------------

    def _repair_outcome_claims(self, narration: str) -> tuple[str, list[str], list[Attempt]]:
        claims = find_outcome_claims(narration)
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
                    self.model, self.host, as_json=True, temperature=0.3, num_predict=200,
                )
                attempts.append(Attempt("repair", reply.seconds, reply.model, reply.text,
                                        note=claim.why))
                fixed = str(reply.json().get("sentence", "")).strip()
            except Exception as exc:  # a failed repair must not lose the turn
                attempts.append(Attempt("repair", 0.0, self.model, note=f"failed: {exc}"))
                fixed = ""

            if fixed and not find_outcome_claims(fixed):
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
        because it cannot happen: the model is being shown what the dice did.
        """
        fighting = self.engine.scene.in_encounter
        tells = [o.tell for o in outcomes if getattr(o, "tell", "")]
        try:
            reply = client.chat(
                prompts.call_prose_messages(brief, [], player_input, tells,
                                            in_combat=fighting,
                                            enemy=self._current_enemy()),
                self.prose_model, self.prose_host, as_json=True, temperature=0.8,
                num_predict=900, provider=self.prose_provider, api_key=self.prose_key)
            text = str(reply.json().get("narration", "")).strip()
        except Exception as exc:
            return "", [f"prose failed: {exc}"], [
                Attempt("prose", 0.0, self.prose_model, note=str(exc)[:120])]

        attempts = [Attempt("prose", reply.seconds, reply.model, reply.text)]
        text = judgement.name_refs(text, self.engine.scene)
        text = narration_mod.strip_example_cast(
            text, player_input + " "
            + " ".join(a.name for a in self.engine.scene.actors.values()))
        text, repairs, polish_attempts = self.polish(
            text, earlier=earlier or [],
            min_chars=(narration_mod.MIN_COMBAT_CHARS if fighting
                       else narration_mod.MIN_SCENE_CHARS),
            max_chars=narration_mod.MAX_COMBAT_CHARS if fighting else 0,
            player_input=player_input, scene_brief=brief)
        attempts.extend(polish_attempts)
        text, outsourced = narration_mod.fix_hand_back(text)
        if outsourced:
            repairs = repairs + [f"asked the player to narrate: replaced {outsourced!r}"]
        text, added = narration_mod.ensure_hand_back(text)
        if added:
            repairs = repairs + ["no hand-back: added the question"]
        text, swapped = narration_mod.right_body(text, self._pc_gender(),
                                                 self._other_names())
        if swapped:
            repairs = repairs + [f"wrong body: replaced {', '.join(swapped)}"]
        return text, repairs, attempts

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
            self.prose_model, self.prose_host, temperature=0.7, num_predict=700,
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
        text = judgement.name_refs(cleaned, self.engine.scene)
        # Call 2 says what the dice did; it has even less business asking the player
        # what they perceive than call 1 does.
        text, _ = narration_mod.fix_hand_back(text)

        # And every other prose rule, which this call had never been subject to.
        #
        # Found by reading a real transcript: two consequence beats in Thessaly's campaign
        # introduced the player's own character as a stranger — "you notice Thessaly Corr
        # stepping out of the shadows at the edge of the fountain, her eyes fixed on you"
        # — and then narrated the whole fight about her in the third person: "The thug's
        # blow crashes into Thessaly... She gasps in pain as she struggles to sit up."
        #
        # `plan_turn` reviews and polishes call 1's narration. Call 2 got
        # `clean_consequence`, `name_refs` and the hand-back fix, and nothing else — no
        # third-person check, no invented names, no misgendering, no wrong body. Roughly
        # half of what the player reads was never checked at all, which is also why the
        # audit's fault rates rose the moment it started reading both beats instead of
        # one.
        #
        # `min_chars` stays 0: this is meant to be two or three sentences, and a length
        # floor here would pad the one call in the app that should be short.
        text, repairs, more = self.polish(text, player_input=player_input,
                                          scene_brief="")
        text, swapped = narration_mod.right_body(text, self._pc_gender(),
                                                 self._other_names())
        attempt = Attempt("consequence", reply.seconds, reply.model, reply.text,
                          note="; ".join(repairs + ([f"wrong body: {', '.join(swapped)}"]
                                                    if swapped else [])))
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
